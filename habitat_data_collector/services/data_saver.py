"""Data saving service."""

import json
import os
from pathlib import Path
from typing import Dict, List
import cv2
import numpy as np
from tqdm import tqdm
from omegaconf import DictConfig, OmegaConf
from scipy.spatial.transform import Rotation as R

from ..config.settings import DEFAULT_SAVE_MODE, ACTION_CODE_MAP, ACTION_CODE_STOP
from ..core.state_manager import ActionRecord
from ..utils.coordinate_transform import CoordinateTransform


class DataSaver:
    """Service for saving collected data."""

    def __init__(self, cfg: DictConfig, scene_dir: Path):
        """Initialize data saver.
        
        Args:
            cfg: Configuration
            scene_dir: Directory to save data
        """
        self.cfg = cfg
        self.scene_dir = scene_dir
        self.save_mode = cfg.get("save_mode", DEFAULT_SAVE_MODE)
    
    def save_camera_intrinsics(self, fx: float, fy: float, cx: float, cy: float,
                               width: int, height: int):
        """Save camera intrinsics to JSON file."""
        intrinsics_data = {
            "fx": float(fx),
            "fy": float(fy),
            "cx": float(cx),
            "cy": float(cy),
            "width": int(width),
            "height": int(height)
        }
        
        intrinsics_file = self.scene_dir / "camera_intrinsics.json"
        with open(intrinsics_file, "w") as f:
            json.dump(intrinsics_data, f, indent=4)
        
        print(f"Saved camera intrinsics to {intrinsics_file}")
    
    def save_scene_config(self, id_handle_dict: Dict, all_rigid_objects: List):
        """Save scene configuration.
        
        Args:
            id_handle_dict: Mapping of semantic IDs to handles
            all_rigid_objects: List of all rigid objects
        """
        # Convert DictConfig to standard dict if needed
        if OmegaConf.is_config(id_handle_dict):
            id_handle_dict_plain = OmegaConf.to_container(id_handle_dict, resolve=True)
        else:
            id_handle_dict_plain = dict(id_handle_dict)
        
        config_data = {
            'scene': {
                'scene_path': self.cfg.scene_path,
                'scene_dataset_config': self.cfg.scene_dataset_config
            },
            'id_handle_mapping': id_handle_dict_plain,
            'objects': []
        }
        
        for obj in all_rigid_objects:
            translation_list = [obj.translation.x, obj.translation.y, obj.translation.z]
            rotation_list = [
                obj.rotation.vector.x,
                obj.rotation.vector.y,
                obj.rotation.vector.z,
                obj.rotation.scalar
            ]
            
            config_data['objects'].append({
                'object_id': obj.object_id,
                'translation': translation_list,
                'rotation': rotation_list,
                'semantic_id': obj.semantic_id
            })
        
        config_file = self.scene_dir / "scene_config.json"
        with open(config_file, "w") as file:
            json.dump(config_data, file, indent=4)
        
        print(f"Configuration saved to {config_file}")
    
    def save_observation(self, observations: Dict, timestamp: float, 
                        frame_index: int = None, next_action: str = None):
        """Save RGB and depth observations.
        
        Args:
            observations: Dictionary of sensor observations
            timestamp: Action timestamp
            frame_index: Optional frame index for action mode naming
            next_action: Next action to be executed (for action mode naming)
        """
        # Determine file naming
        if self.save_mode == "action" and frame_index is not None:
            # Get action code for next action
            action_code = ACTION_CODE_MAP.get(next_action, ACTION_CODE_STOP)
            formatted_name = f"{frame_index:06d}_{action_code}"
        else:
            formatted_name = f"{timestamp:015.7f}"
        
        # Save RGB
        if self.cfg.data_cfg.rgb and "color_sensor" in observations:
            save_dir = self.scene_dir / "rgb"
            os.makedirs(save_dir, exist_ok=True)
            save_path = save_dir / f"{formatted_name}.png"
            rgb_img = observations["color_sensor"][:, :, [2, 1, 0]]  # RGB to BGR
            cv2.imwrite(str(save_path), rgb_img)
        
        # Save depth
        if self.cfg.data_cfg.depth and "depth_sensor" in observations:
            save_dir = self.scene_dir / "depth"
            os.makedirs(save_dir, exist_ok=True)
            save_path = save_dir / f"{formatted_name}.png"
            depth_img = (observations["depth_sensor"] * 1000).astype(np.uint16)
            cv2.imwrite(str(save_path), depth_img)
    
    def save_agent_pose(self, sensor_state, timestamp: float, 
                       frame_index: int = None, next_action: str = None) -> str:
        """Save agent pose as transformation matrix.
        
        Args:
            sensor_state: Sensor state from agent
            timestamp: Timestamp
            frame_index: Optional frame index
            next_action: Next action to be executed (for action mode naming)
            
        Returns:
            Formatted pose string
        """
        position = sensor_state.position
        rotation = sensor_state.rotation
        
        # Convert to transformation matrix in system coordinates
        rotation_matrix = R.from_quat([rotation.x, rotation.y, rotation.z, rotation.w]).as_matrix()
        
        cam_habi_to_world_habi = np.eye(4)
        cam_habi_to_world_habi[:3, :3] = rotation_matrix
        cam_habi_to_world_habi[:3, 3] = [position[0], position[1], position[2]]
        
        cam_sys_to_world_sys = (
            CoordinateTransform.WORLD_HABI_TO_WORLD_SYS @
            cam_habi_to_world_habi @
            CoordinateTransform.CAM_SYS_TO_CAM_HABI
        )
        
        transform_matrix_flat = cam_sys_to_world_sys.flatten()
        
        # Format based on save mode
        if self.save_mode == "action" and frame_index is not None:
            action_code = ACTION_CODE_MAP.get(next_action, ACTION_CODE_STOP)
            return f"{frame_index:06d}_{action_code}\t" + "\t".join(map(str, transform_matrix_flat))
        else:
            return f"{timestamp:015.7f}\t" + "\t".join(map(str, transform_matrix_flat))
    
    def replay_and_save(self, sim, actions_list: List[ActionRecord],
                       init_state, init_time: float):
        """Replay actions and save data.
        
        Args:
            sim: Simulator service
            actions_list: List of recorded actions
            init_state: Initial agent state
            init_time: Initial recording time
        """
        print(f"Replaying and saving... (save_mode: {self.save_mode})")
        
        # Filter None actions for action mode
        if self.save_mode == "action":
            original_count = len(actions_list)
            actions_list = [a for a in actions_list if a.action is not None]
            filtered_count = original_count - len(actions_list)
            if filtered_count > 0:
                print(f"  -> Filtered {filtered_count} idle frames, keeping {len(actions_list)} action frames")
        
        agent_states = []
        
        # Reset scene
        rigid_obj_mgr = sim.get_rigid_object_manager()
        rigid_obj_mgr.remove_all_objects()
        
        if self.cfg.load_from_config:
            print("Loading objects from configuration...")
            sim.load_objects_from_config(self.cfg.id_handle_dict)
        
        # Set initial state
        agent = sim.sim.get_agent(self.cfg.default_agent)
        agent.set_state(init_state)
        
        # Ensure sensor states are properly set
        agent_state = agent.get_state()
        for sensor_name in ["color_sensor", "depth_sensor", "semantic_sensor"]:
            if sensor_name in init_state.sensor_states:
                agent_state.sensor_states[sensor_name].position = init_state.sensor_states[sensor_name].position
                agent_state.sensor_states[sensor_name].rotation = init_state.sensor_states[sensor_name].rotation
        
        agent.set_state(agent_state, reset_sensors=True, infer_sensor_states=False)
        
        # Replay loop
        import time as time_module
        replay_start_time = time_module.time()
        target_fps = self.cfg.frame_rate
        frame_interval = 1 / target_fps
        
        total_frames = len(actions_list)
        
        for idx, action_entry in enumerate(tqdm(actions_list, desc="Replaying and saving")):
            action = action_entry.action
            action_timestamp = action_entry.timestamp
            
            # Determine next_action for file naming
            # Each frame stores the NEXT action to be executed
            # Last frame stores stop (None -> 0)
            if idx < total_frames - 1:
                next_action = actions_list[idx + 1].action
                # For object actions, we treat them as None (stop) for naming
                if next_action in ["add_object", "place_in_view", "remove_object"]:
                    next_action = None
            else:
                next_action = None  # Last frame -> stop (0)
            
            # Physics step
            sim.step_physics(frame_interval)
            
            # Timing
            if idx > 0:
                prev_timestamp = actions_list[idx - 1].timestamp
                elapsed_time = action_timestamp - prev_timestamp
                current_time = time_module.time()
                sleep_time = elapsed_time - (current_time - replay_start_time)
                if sleep_time > 0:
                    time_module.sleep(sleep_time)
            
            # Execute action
            if action is not None:
                if action in ["add_object", "place_in_view"]:
                    semantic_id = action_entry.semantic_id
                    object_handle = self.cfg.id_handle_dict.get(semantic_id)
                    if object_handle:
                        self._add_object_with_pose(
                            sim,
                            object_handle,
                            action_entry.translation,
                            action_entry.rotation
                        )
                elif action == "remove_object":
                    object_id = action_entry.object_id
                    rigid_obj_mgr.remove_object_by_id(object_id)
                else:
                    sim.step(action)
            
            # Get observations and save
            obs = sim.get_observations()
            self.save_observation(obs, action_timestamp, frame_index=idx, next_action=next_action)
            
            # Save pose
            sensor_state = agent.get_state().sensor_states["color_sensor"]
            pose_str = self.save_agent_pose(sensor_state, action_timestamp, frame_index=idx, next_action=next_action)
            agent_states.append(pose_str)
            
            replay_start_time = time_module.time()
        
        # Save all poses
        pose_file = self.scene_dir / "pose.txt"
        with open(pose_file, "w") as f:
            f.write("\n".join(agent_states))
        
        print(f"Replay and saving completed in {self.scene_dir}")
    
    def _add_object_with_pose(self, sim, object_handle: str, translation: List, rotation: List):
        """Add object with specific pose during replay."""
        import magnum as mn
        rigid_obj_mgr = sim.get_rigid_object_manager()
        
        rigid_object = rigid_obj_mgr.add_object_by_template_handle(object_handle)
        rigid_object.translation = mn.Vector3(*translation)
        
        rotation_vector = mn.Vector3(rotation[0], rotation[1], rotation[2])
        rotation_scalar = rotation[3]
        rigid_object.rotation = mn.Quaternion(rotation_vector, rotation_scalar)
        
        return rigid_object

