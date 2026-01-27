"""Object manipulation handler."""

import random
import time
from typing import List, Optional
import numpy as np

from .base_handler import BaseHandler
from ..core.event_dispatcher import Event, EventType
from ..config.settings import BBOX_REDUCTION_FACTOR


class ObjectHandler(BaseHandler):
    """Handler for object manipulation."""

    def __init__(self, *args, recording_handler=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.recording_handler = recording_handler
        
        # Subscribe to events
        self.events.subscribe(EventType.OBJECT_ADD, self.handle_add_object)
        self.events.subscribe(EventType.OBJECT_REMOVE, self.handle_remove_object)
        self.events.subscribe(EventType.OBJECT_PLACE_IN_VIEW, self.handle_place_in_view)
        self.events.subscribe(EventType.OBJECT_GRAB, self.handle_grab_object)
        self.events.subscribe(EventType.OBJECT_RELEASE, self.handle_release_object)
    
    def handle_add_object(self, event: Event):
        """Handle random object addition."""
        print("Adding object to scene...")
        
        handle_list = list(self.state.objects.id_handle_dict.values())
        if not handle_list:
            print("No object handles available")
            return
        
        obj_handle = random.choice(handle_list)
        bbox = random.choice(self.state.objects.all_bboxes_for_place)
        
        placed_object = self.sim.place_object_in_bbox(
            obj_handle,
            bbox,
            max_attempts=1
        )
        
        if placed_object:
            self.state.objects.all_rigid_objects.append(placed_object)
            handle_list.remove(obj_handle)
            print("Object added and recorded.")
            
            # Record action
            if self.recording_handler:
                self.recording_handler.add_object_action(
                    "add_object",
                    placed_object,
                    event.timestamp
                )
        else:
            print("Failed to place object.")
    
    def handle_remove_object(self, event: Event):
        """Handle object removal."""
        if not self.state.objects.all_rigid_objects:
            print("No objects to remove.")
            return
        
        obj_to_remove = random.choice(self.state.objects.all_rigid_objects)
        
        # Record action first
        if self.recording_handler:
            self.recording_handler.add_object_action(
                "remove_object",
                obj_to_remove,
                event.timestamp
            )
        
        # Then remove
        obj_id = obj_to_remove.object_id
        self.sim.get_rigid_object_manager().remove_object_by_id(obj_id)
        self.state.objects.all_rigid_objects.remove(obj_to_remove)
        
        remaining = len(self.state.objects.all_rigid_objects)
        print(f"Removed object ID {obj_id}, remaining {remaining} objects.")
    
    def handle_place_in_view(self, event: Event):
        """Handle placing object in camera view."""
        # Filter bboxes in view
        bboxes_in_view = self._filter_bboxes_in_view(
            self.state.objects.all_bboxes_for_place
        )
        
        if not bboxes_in_view:
            print("Error: No bounding boxes in view. Cannot place object.")
            return
        
        handle_list = list(self.state.objects.id_handle_dict.values())
        if not handle_list:
            print("No object handles available")
            return
        
        obj_handle = random.choice(handle_list)
        bbox = random.choice(bboxes_in_view)
        
        placed_object = self.sim.place_object_in_bbox(
            obj_handle,
            bbox,
            max_attempts=1
        )
        
        if placed_object:
            self.state.objects.all_rigid_objects.append(placed_object)
            print("Object placed within camera view.")
            
            # Record action
            if self.recording_handler:
                self.recording_handler.add_object_action(
                    "place_in_view",
                    placed_object,
                    event.timestamp
                )
        else:
            print("Failed to place object in camera view.")
    
    def handle_grab_object(self, event: Event):
        """Handle grabbing nearest object."""
        if not self.state.objects.all_rigid_objects:
            print("No objects to grab.")
            return
        
        nearest_obj = self._find_nearest_object()
        if nearest_obj is None:
            print("No object found nearby.")
            return
        
        obj_id = nearest_obj.object_id
        semantic_id = nearest_obj.semantic_id
        obj_handle = self.state.objects.id_handle_dict.get(semantic_id, "unknown")
        
        # Remove from scene
        self.sim.get_rigid_object_manager().remove_object_by_id(obj_id)
        self.state.objects.all_rigid_objects.remove(nearest_obj)
        
        # Remember what was grabbed
        self.state.objects.grabbed_object_semantic_id = semantic_id
        
        print(f"Object ID: {obj_id}, {obj_handle} grabbed, press 'r' to release")
    
    def handle_release_object(self, event: Event):
        """Handle releasing grabbed object."""
        if self.state.objects.grabbed_object_semantic_id is None:
            print("No grabbed object. Please grab object first.")
            return
        
        # Find nearest bbox
        nearest_bbox = self._find_nearest_bbox(
            self.state.objects.all_bboxes_for_place
        )
        
        if nearest_bbox is None:
            print("No suitable placement location found.")
            return
        
        # Get grabbed object handle
        grabbed_handle = self.state.objects.id_handle_dict.get(
            self.state.objects.grabbed_object_semantic_id
        )
        
        if grabbed_handle is None:
            print("Error: Grabbed object handle not found.")
            self.state.objects.grabbed_object_semantic_id = None
            return
        
        # Place object
        placed_object = self.sim.place_object_in_bbox(
            grabbed_handle,
            nearest_bbox,
            max_attempts=1
        )
        
        if placed_object:
            self.state.objects.all_rigid_objects.append(placed_object)
            self.state.objects.grabbed_object_semantic_id = None
            print(f"Object {grabbed_handle} released.")
        else:
            print("Failed to release object. Try again.")
    
    def _find_nearest_object(self):
        """Find nearest object to agent."""
        current_position = self.sim.get_agent_state().position
        current_position = np.array(current_position)
        
        nearest_dist = float('inf')
        nearest_obj = None
        
        for rigid_object in self.state.objects.all_rigid_objects:
            obj_pos = np.array(rigid_object.translation)
            dist = np.linalg.norm(current_position - obj_pos)
            
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_obj = rigid_object
        
        return nearest_obj
    
    def _find_nearest_bbox(self, bbox_list: List) -> Optional[dict]:
        """Find nearest bounding box to agent."""
        current_position = self.sim.get_agent_state().position
        current_position = np.array(current_position)
        
        nearest_bbox = None
        nearest_distance = float('inf')
        
        for bbox in bbox_list:
            bbox_center = np.array(bbox["center"])
            distance = np.linalg.norm(current_position - bbox_center)
            
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_bbox = bbox
        
        if nearest_bbox is not None:
            reduced_size = np.array(nearest_bbox["size"]) * 0.7
            return {
                "center": nearest_bbox["center"],
                "size": reduced_size.tolist()
            }
        
        return None
    
    def _filter_bboxes_in_view(self, bbox_list: List) -> List:
        """Filter bounding boxes that are in camera view."""
        in_view_bboxes = []
        
        agent = self.sim.sim.get_agent(0)
        render_camera = agent.scene_node.node_sensor_suite.get("color_sensor")
        render_cam = render_camera.render_camera
        
        viewport_width, viewport_height = render_cam.viewport
        
        for bbox in bbox_list:
            # Reduce bbox size
            reduced_size = [dim * BBOX_REDUCTION_FACTOR for dim in bbox["size"]]
            reduced_bbox = {
                "center": bbox["center"],
                "size": reduced_size
            }
            
            # Project to 2D
            import magnum as mn
            center_mn_vector = mn.Vector3(reduced_bbox["center"])
            projected_point_3d = render_cam.projection_matrix.transform_point(
                render_cam.camera_matrix.transform_point(center_mn_vector)
            )
            
            point_2d = mn.Vector2(projected_point_3d[0], -projected_point_3d[1])
            point_2d = point_2d / render_cam.projection_size()[0]
            point_2d += mn.Vector2(0.5)
            point_2d *= render_cam.viewport
            point_2d_int = mn.Vector2i(point_2d)
            
            # Check if in view
            if 0 <= point_2d_int.x < viewport_width and 0 <= point_2d_int.y < viewport_height:
                in_view_bboxes.append(reduced_bbox)
        
        return in_view_bboxes
    
    def update(self):
        """Update object states (remove objects on ground)."""
        objects_to_remove = []
        
        for rigid_object in self.state.objects.all_rigid_objects:
            if self.sim.is_object_on_ground(rigid_object):
                objects_to_remove.append(rigid_object)
                print(f"Object ID {rigid_object.object_id} fell to ground, removing.")
        
        for obj in objects_to_remove:
            self.state.objects.all_rigid_objects.remove(obj)
            self.sim.get_rigid_object_manager().remove_object_by_id(obj.object_id)

