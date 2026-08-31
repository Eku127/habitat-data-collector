"""Simulator service encapsulating Habitat simulator operations."""

import json
import os
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import habitat_sim
import magnum as mn
import numpy as np
from omegaconf import DictConfig

from ..config.settings import (
    TOPDOWN_METERS_PER_PIXEL,
    GROUND_TOLERANCE,
    OBJECT_PLACEMENT_HEIGHT_OFFSET,
)
from ..utils.coordinate_transform import CoordinateTransform
from ..utils.topdown_map import shrink_false_areas, check_valid_in_topdown
from ..authoring import target_template_handles, targets_from_config


class SimulatorService:
    """Service for managing Habitat simulator operations."""

    def __init__(self, sim: habitat_sim.Simulator, cfg: DictConfig):
        """Initialize simulator service.
        
        Args:
            sim: Habitat simulator instance
            cfg: Configuration
        """
        self.sim = sim
        self.cfg = cfg
        self.agent = sim.initialize_agent(cfg.default_agent)
        
        # Get scene information
        self.scene = sim.semantic_scene
        self.floor_height = sim.pathfinder.get_bounds()[0][1]
        
        # Generate topdown map once
        self.topdown_map = sim.pathfinder.get_topdown_view(
            TOPDOWN_METERS_PER_PIXEL, 
            self.floor_height
        )
        self.shrunk_map = shrink_false_areas(self.topdown_map, 2, 3)
        
    def get_observations(self) -> Dict:
        """Get sensor observations."""
        return self.sim.get_sensor_observations()
    
    def step(self, action: str):
        """Execute an action in the simulator."""
        self.sim.step(action)
    
    def step_physics(self, dt: float):
        """Step physics simulation."""
        self.sim.step_physics(dt)
    
    def get_agent_state(self) -> habitat_sim.AgentState:
        """Get current agent state."""
        return self.agent.get_state()
    
    def set_agent_state(self, state: habitat_sim.AgentState):
        """Set agent state."""
        self.agent.set_state(state)
    
    def get_agent_pose(self) -> List[float]:
        """Get agent pose in system coordinates."""
        sensor_state = self.agent.get_state().sensor_states["color_sensor"]
        return CoordinateTransform.get_agent_pose_in_system(sensor_state)
    
    def get_camera_intrinsics(self, sensor_name: str = "color_sensor") -> Tuple[float, float, float, float, int, int]:
        """Get camera intrinsics.
        
        Returns:
            (fx, fy, cx, cy, width, height)
        """
        render_camera = self.sim._sensors[sensor_name]._sensor_object.render_camera
        projection_matrix = render_camera.projection_matrix
        width, height = render_camera.viewport
        
        fx = projection_matrix[0, 0] * width / 2.0
        fy = projection_matrix[1, 1] * height / 2.0
        cx = (projection_matrix[2, 0] + 1.0) * width / 2.0
        cy = (projection_matrix[2, 1] + 1.0) * height / 2.0
        
        return fx, fy, cx, cy, int(width), int(height)
    
    def set_random_agent_position(self):
        """Set agent to a random navigable position."""
        agent_state = habitat_sim.AgentState()
        self.sim.pathfinder.seed(self.cfg.data_cfg.seed)
        random_pt = self.sim.pathfinder.get_random_navigable_point()
        agent_state.position = random_pt
        self.agent.set_state(agent_state)
        return agent_state
    
    def convert_to_topdown(self, point: np.ndarray) -> np.ndarray:
        """Convert 3D point to topdown map coordinates."""
        return CoordinateTransform.convert_to_topdown(
            self.sim.pathfinder, 
            point, 
            TOPDOWN_METERS_PER_PIXEL
        )
    
    def get_rigid_object_manager(self):
        """Get rigid object manager."""
        return self.sim.get_rigid_object_manager()
    
    def get_object_template_manager(self):
        """Get object template manager."""
        return self.sim.get_object_template_manager()
    
    def is_object_on_ground(self, rigid_object, tolerance: float = GROUND_TOLERANCE) -> bool:
        """Check if object is on the ground.
        
        Args:
            rigid_object: The rigid object to check
            tolerance: Tolerance for ground detection
            
        Returns:
            True if object is on ground
        """
        aabb = rigid_object.root_scene_node.compute_cumulative_bb()
        object_min_y = aabb.min[1] + rigid_object.translation[1]
        return abs(object_min_y - self.floor_height) <= tolerance
    
    def place_object_in_bbox(
        self,
        obj_handle: str,
        bbox: Dict,
        max_attempts: int = 1
    ) -> Optional[habitat_sim.physics.ManagedRigidObject]:
        """Place an object within a bounding box.
        
        Args:
            obj_handle: Object template handle
            bbox: Bounding box with 'center' and 'size'
            max_attempts: Maximum placement attempts
            
        Returns:
            Placed object or None if failed
        """
        rigid_obj_mgr = self.get_rigid_object_manager()
        
        for _ in range(max_attempts):
            # Create object
            rigid_object = rigid_obj_mgr.add_object_by_template_handle(obj_handle)
            
            # Generate random position on top of bbox
            x = np.random.uniform(
                bbox['center'][0] - bbox['size'][0] / 2,
                bbox['center'][0] + bbox['size'][0] / 2
            )
            y = bbox['center'][1] + bbox['size'][1] / 2 + OBJECT_PLACEMENT_HEIGHT_OFFSET
            z = np.random.uniform(
                bbox['center'][2] - bbox['size'][2] / 2,
                bbox['center'][2] + bbox['size'][2] / 2
            )
            rigid_object.translation = mn.Vector3(x, y, z)
            
            # Check if position is valid in topdown map
            xy_point = self.convert_to_topdown(rigid_object.translation)
            if check_valid_in_topdown(xy_point, self.shrunk_map):
                # Snap object down to surface
                import habitat.sims.habitat_simulator.sim_utilities as sutils
                snap_success = sutils.snap_down(self.sim, rigid_object, [habitat_sim.stage_id])
                
                if snap_success and not self.is_object_on_ground(rigid_object):
                    print(f"Object placed successfully. ID: {rigid_object.object_id}, Semantic ID: {rigid_object.semantic_id}")
                    return rigid_object
            
            # Failed, remove object
            rigid_obj_mgr.remove_object_by_id(rigid_object.object_id)
        
        print("Warning: Failed to place object after maximum attempts.")
        return None
    
    def compute_random_navigation_path(self) -> Tuple[Optional[np.ndarray], Optional[List]]:
        """Compute a random navigation path.
        
        Returns:
            Tuple of (goal, path_points) or (None, None) if failed
        """
        if not self.sim.pathfinder.is_loaded:
            print("Pathfinder not initialized, aborting.")
            return None, None
        
        goal = self.sim.pathfinder.get_random_navigable_point()
        current_state = self.agent.get_state()
        
        path = habitat_sim.ShortestPath()
        path.requested_start = current_state.position
        path.requested_end = goal
        
        found_path = self.sim.pathfinder.find_path(path)
        path_points = path.points
        
        if len(path_points) == 0:
            print("No valid path found.")
            return None, None
        
        return goal, path_points
    
    def register_object_templates(self) -> Dict[int, str]:
        """Register object templates from config.
        
        Returns:
            Dictionary mapping semantic_id to handle
        """
        obj_attr_mgr = self.get_object_template_manager()
        obj_attr_mgr.load_configs(self.cfg.objects_path)
        
        file_obj_handles = obj_attr_mgr.get_file_template_handles()
        id_handle_dict = {}

        authoring_cfg = self.cfg.get("authoring")
        if authoring_cfg and bool(authoring_cfg.get("enabled", False)):
            targets = targets_from_config(authoring_cfg.targets)
            try:
                resolved_handles = target_template_handles(
                    file_obj_handles,
                    targets,
                )
            except ValueError as exc:
                raise RuntimeError(str(exc)) from exc

            for target in targets:
                key_element = target.handle
                semantic_id = target.semantic_id
                obj_template = obj_attr_mgr.get_template_by_handle(
                    resolved_handles[semantic_id]
                )
                obj_template.semantic_id = semantic_id
                obj_attr_mgr.register_template(obj_template, key_element)
                id_handle_dict[semantic_id] = key_element
                print(
                    f"Registered authoring target {key_element} "
                    f"with semantic ID: {semantic_id}"
                )
            return id_handle_dict
        
        # Load existing mappings if from config
        config_data = {}
        if self.cfg.load_from_config:
            with open(self.cfg.scene_config, "r") as file:
                config_data = json.load(file).get("id_handle_mapping", {})
        
        for handle in file_obj_handles:
            obj_template = obj_attr_mgr.get_template_by_handle(handle)
            filename = os.path.basename(handle)
            key_element = filename.split(".")[0]
            
            # Determine semantic ID
            semantic_id = next(
                (int(k) for k, v in config_data.items() if key_element in v),
                random.randint(0, 100)
            )
            
            obj_template.semantic_id = semantic_id
            obj_attr_mgr.register_template(obj_template, key_element)
            id_handle_dict[semantic_id] = key_element
            
            print(f"Registered {key_element} with semantic ID: {semantic_id}")
        
        return id_handle_dict
    
    def add_object_with_pose(
        self,
        handle: str,
        translation: List[float],
        rotation: List[float],
    ):
        """Add an object using a serialized Habitat pose."""
        rigid_object = self.get_rigid_object_manager().add_object_by_template_handle(
            handle
        )
        rigid_object.translation = mn.Vector3(*translation)
        rigid_object.rotation = mn.Quaternion(
            mn.Vector3(rotation[:3]), rotation[3]
        )
        return rigid_object

    def load_objects_from_config(
        self,
        id_handle_dict: Dict[int, str],
        include_metadata: bool = False,
    ) -> Union[List, Tuple[List, Dict[int, Dict[str, Any]]]]:
        """Load objects from scene configuration file.
        
        Args:
            id_handle_dict: Mapping of semantic IDs to handles
            
        Returns:
            List of added objects
        """
        with open(self.cfg.scene_config, "r") as file:
            config_data = json.load(file)
        
        objects_info = config_data.get("objects", [])
        added_objects = []
        object_metadata: Dict[int, Dict[str, Any]] = {}
        
        for obj_data in objects_info:
            semantic_id = obj_data["semantic_id"]
            handle = id_handle_dict.get(semantic_id)
            
            if handle:
                rigid_object = self.add_object_with_pose(
                    handle,
                    obj_data["translation"],
                    obj_data["rotation"],
                )
                
                added_objects.append(rigid_object)
                if isinstance(obj_data.get("anchor"), dict):
                    object_metadata[semantic_id] = obj_data["anchor"]
                print(f"Added object with ID {rigid_object.object_id}, Semantic ID {semantic_id}")
            else:
                print(f"Warning: Semantic ID {semantic_id} does not have a matching handle.")
        
        if include_metadata:
            return added_objects, object_metadata
        return added_objects
