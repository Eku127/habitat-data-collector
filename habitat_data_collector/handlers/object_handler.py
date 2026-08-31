"""Object manipulation handler."""

import random
import time
from typing import List, Optional
import numpy as np

from .base_handler import BaseHandler
from ..core.event_dispatcher import Event, EventType
from ..config.settings import BBOX_REDUCTION_FACTOR
from ..authoring import AnchorInfo, MutationRecord, ObjectSnapshot


class ObjectHandler(BaseHandler):
    """Handler for object manipulation."""

    def __init__(self, *args, recording_handler=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.recording_handler = recording_handler
        
        # Subscribe to events
        self.events.subscribe(EventType.OBJECT_ADD, self.handle_add_object)
        self.events.subscribe(EventType.OBJECT_REMOVE, self.handle_remove_object)
        self.events.subscribe(EventType.OBJECT_PLACE_IN_VIEW, self.handle_place_in_view)
        self.events.subscribe(EventType.OBJECT_SELECT, self.handle_select_object)
        self.events.subscribe(EventType.OBJECT_RELOCATE, self.handle_relocate_object)
        self.events.subscribe(EventType.OBJECT_UNDO, self.handle_undo)
        self.events.subscribe(EventType.OBJECT_GRAB, self.handle_grab_object)
        self.events.subscribe(EventType.OBJECT_RELEASE, self.handle_release_object)

    def _set_authoring_status(self, message: str, ok: Optional[bool] = None):
        self.state.authoring.last_status = message
        self.state.authoring.last_status_ok = ok
        print(message)

    def handle_select_object(self, event: Event):
        """Select one of the fixed targets using its zero-based key index."""
        if not self.state.authoring.enabled:
            return
        index = int((event.data or {}).get("index", -1))
        if index < 0 or index >= len(self.state.authoring.targets):
            self._set_authoring_status("Invalid authoring target selection.", False)
            return
        self.state.authoring.selected_index = index
        target = self.state.authoring.selected_target
        self._set_authoring_status(
            f"Selected [{target.key}]: {target.handle}", True
        )
    
    def handle_add_object(self, event: Event):
        """Handle random object addition."""
        if self.state.authoring.enabled:
            self._set_authoring_status(
                "Random object addition is disabled; select 1-8 and press p.",
                False,
            )
            return
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
        if self.state.authoring.enabled:
            self._handle_authoring_remove()
            return
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
            message = "Error: No placeable surface is visible."
            if self.state.authoring.enabled:
                self._set_authoring_status(message, False)
            else:
                print(message)
            return

        if self.state.authoring.enabled:
            self._handle_authoring_place(self._select_centered_bbox(bboxes_in_view))
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

    def _handle_authoring_place(self, bbox: dict):
        target = self.state.authoring.selected_target
        if target is None:
            self._set_authoring_status("No authoring target is selected.", False)
            return
        if self._find_object_by_semantic_id(target.semantic_id) is not None:
            self._set_authoring_status(
                f"{target.handle} already exists; press v to relocate it.",
                False,
            )
            return
        authoring = self.state.authoring
        if (
            authoring.layout_type != "static"
            and target.semantic_id not in authoring.baseline_semantic_ids
        ):
            self._set_authoring_status(
                f"{target.handle} was not selected in the static layout.",
                False,
            )
            return

        was_relocated = target.semantic_id in authoring.relocated_semantic_ids
        placed_object = self.sim.place_object_in_bbox(target.handle, bbox, max_attempts=1)
        if placed_object is None:
            self._set_authoring_status(
                f"Failed to place {target.handle} on the selected surface.",
                False,
            )
            return

        self.state.objects.all_rigid_objects.append(placed_object)
        self.state.authoring.anchors[target.semantic_id] = self._anchor_from_bbox(bbox)
        self.state.authoring.history.append(MutationRecord(
            semantic_id=target.semantic_id,
            before=None,
            was_relocated=was_relocated,
        ))
        self._set_authoring_status(f"Placed {target.handle}.", True)

    def handle_relocate_object(self, event: Event):
        """Atomically move the selected target to the centered visible surface."""
        if not self.state.authoring.enabled:
            return
        target = self.state.authoring.selected_target
        if target is None:
            self._set_authoring_status("No authoring target is selected.", False)
            return
        current = self._find_object_by_semantic_id(target.semantic_id)
        if current is None:
            self._set_authoring_status(
                f"{target.handle} is missing; press p to add it first.", False
            )
            return
        bboxes = self._filter_bboxes_in_view(
            self.state.objects.all_bboxes_for_place
        )
        if not bboxes:
            self._set_authoring_status("No placeable surface is visible.", False)
            return
        bbox = self._select_centered_bbox(bboxes)
        before = self._snapshot(current, target.handle)
        was_relocated = target.semantic_id in self.state.authoring.relocated_semantic_ids

        replacement = self.sim.place_object_in_bbox(
            target.handle, bbox, max_attempts=1
        )
        if replacement is None:
            self._set_authoring_status(
                f"Relocation failed; original {target.handle} was preserved.",
                False,
            )
            return

        self.sim.get_rigid_object_manager().remove_object_by_id(current.object_id)
        self.state.objects.all_rigid_objects.remove(current)
        self.state.objects.all_rigid_objects.append(replacement)
        self.state.authoring.anchors[target.semantic_id] = self._anchor_from_bbox(bbox)
        if self.state.authoring.layout_type != "static":
            self.state.authoring.relocated_semantic_ids.add(target.semantic_id)
        self.state.authoring.history.append(MutationRecord(
            semantic_id=target.semantic_id,
            before=before,
            was_relocated=was_relocated,
        ))
        self._set_authoring_status(
            f"Relocated {target.handle} to anchor {bbox['Object_ID']}.", True
        )

    def handle_undo(self, event: Event):
        """Undo the most recent authoring add, delete, or relocation."""
        if not self.state.authoring.enabled:
            return
        if not self.state.authoring.history:
            self._set_authoring_status("Nothing to undo.", False)
            return
        mutation = self.state.authoring.history.pop()
        current = self._find_object_by_semantic_id(mutation.semantic_id)
        restored = None
        if mutation.before is not None:
            try:
                restored = self.sim.add_object_with_pose(
                    mutation.before.handle,
                    list(mutation.before.translation),
                    list(mutation.before.rotation),
                )
            except Exception as exc:
                self.state.authoring.history.append(mutation)
                self._set_authoring_status(
                    f"Undo failed; the current object was preserved: {exc}",
                    False,
                )
                return

        if current is not None:
            self.sim.get_rigid_object_manager().remove_object_by_id(current.object_id)
            self.state.objects.all_rigid_objects.remove(current)

        if restored is None:
            self.state.authoring.anchors.pop(mutation.semantic_id, None)
        else:
            self.state.objects.all_rigid_objects.append(restored)
            if mutation.before.anchor is None:
                self.state.authoring.anchors.pop(mutation.semantic_id, None)
            else:
                self.state.authoring.anchors[mutation.semantic_id] = (
                    mutation.before.anchor
                )

        if mutation.was_relocated:
            self.state.authoring.relocated_semantic_ids.add(mutation.semantic_id)
        else:
            self.state.authoring.relocated_semantic_ids.discard(
                mutation.semantic_id
            )
        self._set_authoring_status("Undid the last authoring change.", True)

    def _handle_authoring_remove(self):
        target = self.state.authoring.selected_target
        if target is None:
            self._set_authoring_status("No authoring target is selected.", False)
            return
        current = self._find_object_by_semantic_id(target.semantic_id)
        if current is None:
            self._set_authoring_status(f"{target.handle} is not present.", False)
            return
        before = self._snapshot(current, target.handle)
        was_relocated = target.semantic_id in self.state.authoring.relocated_semantic_ids
        self.sim.get_rigid_object_manager().remove_object_by_id(current.object_id)
        self.state.objects.all_rigid_objects.remove(current)
        self.state.authoring.anchors.pop(target.semantic_id, None)
        self.state.authoring.relocated_semantic_ids.discard(target.semantic_id)
        self.state.authoring.history.append(MutationRecord(
            semantic_id=target.semantic_id,
            before=before,
            was_relocated=was_relocated,
        ))
        self._set_authoring_status(f"Removed {target.handle}.", True)

    def _find_object_by_semantic_id(self, semantic_id: int):
        return next(
            (
                obj
                for obj in self.state.objects.all_rigid_objects
                if int(obj.semantic_id) == int(semantic_id)
            ),
            None,
        )

    def _snapshot(self, rigid_object, handle: str) -> ObjectSnapshot:
        semantic_id = int(rigid_object.semantic_id)
        return ObjectSnapshot(
            semantic_id=semantic_id,
            handle=handle,
            translation=(
                float(rigid_object.translation.x),
                float(rigid_object.translation.y),
                float(rigid_object.translation.z),
            ),
            rotation=(
                float(rigid_object.rotation.vector.x),
                float(rigid_object.rotation.vector.y),
                float(rigid_object.rotation.vector.z),
                float(rigid_object.rotation.scalar),
            ),
            anchor=self.state.authoring.anchors.get(semantic_id),
        )

    @staticmethod
    def _anchor_from_bbox(bbox: dict) -> AnchorInfo:
        return AnchorInfo(
            object_id=str(bbox["Object_ID"]),
            category=str(bbox["Category"]),
        )

    @staticmethod
    def _select_centered_bbox(bboxes: List[dict]) -> dict:
        return min(bboxes, key=lambda bbox: bbox["_screen_distance_sq"])
    
    def handle_grab_object(self, event: Event):
        """Handle grabbing nearest object."""
        if self.state.authoring.enabled:
            self._set_authoring_status(
                "Grab/release is disabled in authoring mode; use v.", False
            )
            return
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
        if self.state.authoring.enabled:
            self._set_authoring_status(
                "Grab/release is disabled in authoring mode; use v.", False
            )
            return
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
        screen_center_x = viewport_width / 2.0
        screen_center_y = viewport_height / 2.0
        
        for bbox in bbox_list:
            # Reduce bbox size
            reduced_size = [dim * BBOX_REDUCTION_FACTOR for dim in bbox["size"]]
            reduced_bbox = {
                "Object_ID": bbox["Object_ID"],
                "Category": bbox["Category"],
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
                reduced_bbox["_screen_distance_sq"] = (
                    (float(point_2d_int.x) - screen_center_x) ** 2
                    + (float(point_2d_int.y) - screen_center_y) ** 2
                )
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
            if self.state.authoring.enabled:
                self.state.authoring.anchors.pop(int(obj.semantic_id), None)
                self.state.authoring.relocated_semantic_ids.discard(
                    int(obj.semantic_id)
                )
                self._set_authoring_status(
                    f"Object {obj.semantic_id} fell to the ground and was removed.",
                    False,
                )
            self.state.objects.all_rigid_objects.remove(obj)
            self.sim.get_rigid_object_manager().remove_object_by_id(obj.object_id)
