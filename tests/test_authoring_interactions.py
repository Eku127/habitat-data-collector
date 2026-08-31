import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from omegaconf import OmegaConf

from habitat_data_collector.authoring import AnchorInfo, DUALMAP_TARGETS
from habitat_data_collector.core.event_dispatcher import Event, EventDispatcher, EventType
from habitat_data_collector.core.state_manager import StateManager
from habitat_data_collector.handlers.input_handler import InputHandler
from habitat_data_collector.handlers.object_handler import ObjectHandler
from habitat_data_collector.handlers.recording_handler import RecordingHandler
from habitat_data_collector.services.data_saver import DataSaver


class FakeObject:
    next_id = 1

    def __init__(self, semantic_id, translation=(0.0, 1.0, 0.0), rotation=(0, 0, 0, 1)):
        self.object_id = FakeObject.next_id
        FakeObject.next_id += 1
        self.semantic_id = semantic_id
        self.translation = SimpleNamespace(
            x=float(translation[0]), y=float(translation[1]), z=float(translation[2])
        )
        self.rotation = SimpleNamespace(
            vector=SimpleNamespace(
                x=float(rotation[0]), y=float(rotation[1]), z=float(rotation[2])
            ),
            scalar=float(rotation[3]),
        )


class FakeManager:
    def __init__(self):
        self.removed = []

    def remove_object_by_id(self, object_id):
        self.removed.append(object_id)


class FakeSimulator:
    def __init__(self, targets):
        self.manager = FakeManager()
        self.handle_to_id = {target.handle: target.semantic_id for target in targets}
        self.place_result = True
        self.place_calls = 0

    def place_object_in_bbox(self, handle, bbox, max_attempts=1):
        self.place_calls += 1
        if not self.place_result:
            return None
        return FakeObject(
            self.handle_to_id[handle],
            translation=(bbox["center"][0], 1.0, bbox["center"][2]),
        )

    def add_object_with_pose(self, handle, translation, rotation):
        return FakeObject(self.handle_to_id[handle], translation, rotation)

    def get_rigid_object_manager(self):
        return self.manager


def configured_state(layout_type="static"):
    state = StateManager()
    state.authoring.enabled = True
    state.authoring.targets = list(DUALMAP_TARGETS)
    state.authoring.layout_type = layout_type
    if layout_type != "static":
        state.authoring.baseline_semantic_ids = {
            target.semantic_id for target in DUALMAP_TARGETS[:6]
        }
    return state


def bbox(object_id="surface-1"):
    return {
        "Object_ID": object_id,
        "Category": "table",
        "center": [2.0, 0.5, 3.0],
        "size": [1.0, 0.2, 1.0],
        "_screen_distance_sq": 4.0,
    }


class InputAndObjectInteractionTest(unittest.TestCase):
    def setUp(self):
        FakeObject.next_id = 1
        self.state = configured_state()
        self.events = EventDispatcher()
        self.sim = FakeSimulator(DUALMAP_TARGETS)
        self.handler = ObjectHandler(self.state, self.sim, self.events)

    def test_number_key_selects_target(self):
        input_handler = InputHandler(self.state, self.sim, self.events)
        with patch("cv2.waitKey", return_value=ord("3")):
            self.assertTrue(input_handler.poll())
        self.assertEqual(2, self.state.authoring.selected_index)
        self.assertEqual("011_banana", self.state.authoring.selected_target.handle)

    def test_keys_seven_and_eight_select_the_new_menu_entries(self):
        input_handler = InputHandler(self.state, self.sim, self.events)
        with patch("cv2.waitKey", return_value=ord("8")):
            self.assertTrue(input_handler.poll())
        self.assertEqual("037_scissors", self.state.authoring.selected_target.handle)

    def test_duplicate_place_is_rejected(self):
        target = self.state.authoring.selected_target
        self.state.objects.all_rigid_objects.append(FakeObject(target.semantic_id))
        self.handler._handle_authoring_place(bbox())
        self.assertEqual(0, self.sim.place_calls)
        self.assertIn("already exists", self.state.authoring.last_status)

    def test_add_and_undo_remove_new_object(self):
        target = self.state.authoring.selected_target
        self.handler._handle_authoring_place(bbox())
        self.assertEqual(1, len(self.state.objects.all_rigid_objects))
        self.assertEqual("surface-1", self.state.authoring.anchors[target.semantic_id].object_id)

        self.handler.handle_undo(Event(EventType.OBJECT_UNDO, 0.0))
        self.assertEqual([], self.state.objects.all_rigid_objects)
        self.assertNotIn(target.semantic_id, self.state.authoring.anchors)

    def test_delete_then_add_does_not_count_as_dynamic_relocation(self):
        self.state.authoring.layout_type = "in_anchor"
        target = self.state.authoring.selected_target
        self.state.authoring.baseline_semantic_ids = {target.semantic_id}
        current = FakeObject(target.semantic_id)
        self.state.objects.all_rigid_objects.append(current)
        self.state.authoring.anchors[target.semantic_id] = AnchorInfo("old", "table")

        self.handler.handle_remove_object(Event(EventType.OBJECT_REMOVE, 0.0))
        self.handler._handle_authoring_place(bbox("old"))
        self.assertNotIn(target.semantic_id, self.state.authoring.relocated_semantic_ids)

    def test_dynamic_layout_cannot_add_option_absent_from_static(self):
        self.state.authoring.layout_type = "in_anchor"
        self.state.authoring.baseline_semantic_ids = {
            target.semantic_id for target in DUALMAP_TARGETS[:6]
        }
        self.state.authoring.selected_index = 7
        self.handler._handle_authoring_place(bbox())
        self.assertEqual(0, self.sim.place_calls)
        self.assertIn("not selected in the static layout", self.state.authoring.last_status)

    def test_centered_bbox_is_selected(self):
        selected = self.handler._select_centered_bbox([
            {"_screen_distance_sq": 10.0},
            {"_screen_distance_sq": 1.0},
        ])
        self.assertEqual(1.0, selected["_screen_distance_sq"])

    def test_failed_relocation_preserves_original(self):
        target = self.state.authoring.selected_target
        original = FakeObject(target.semantic_id, translation=(9, 1, 9))
        self.state.objects.all_rigid_objects.append(original)
        self.state.authoring.anchors[target.semantic_id] = AnchorInfo("old", "table")
        self.state.objects.all_bboxes_for_place = [bbox()]
        self.sim.place_result = False
        with patch.object(self.handler, "_filter_bboxes_in_view", return_value=[bbox()]):
            self.handler.handle_relocate_object(Event(EventType.OBJECT_RELOCATE, 0.0))
        self.assertEqual([original], self.state.objects.all_rigid_objects)
        self.assertEqual([], self.sim.manager.removed)
        self.assertEqual([], self.state.authoring.history)

    def test_relocation_and_undo_restore_pose_anchor_and_flag(self):
        self.state.authoring.layout_type = "in_anchor"
        target = self.state.authoring.selected_target
        original = FakeObject(target.semantic_id, translation=(9, 1, 9))
        self.state.objects.all_rigid_objects.append(original)
        self.state.authoring.anchors[target.semantic_id] = AnchorInfo("old", "table")
        with patch.object(self.handler, "_filter_bboxes_in_view", return_value=[bbox("new")]):
            self.handler.handle_relocate_object(Event(EventType.OBJECT_RELOCATE, 0.0))

        self.assertEqual(1, len(self.state.objects.all_rigid_objects))
        replacement = self.state.objects.all_rigid_objects[0]
        self.assertNotEqual(original.object_id, replacement.object_id)
        self.assertEqual("new", self.state.authoring.anchors[target.semantic_id].object_id)
        self.assertIn(target.semantic_id, self.state.authoring.relocated_semantic_ids)

        self.handler.handle_undo(Event(EventType.OBJECT_UNDO, 0.0))
        restored = self.state.objects.all_rigid_objects[0]
        self.assertEqual(9.0, restored.translation.x)
        self.assertEqual("old", self.state.authoring.anchors[target.semantic_id].object_id)
        self.assertNotIn(target.semantic_id, self.state.authoring.relocated_semantic_ids)

    def test_repeated_relocation_undo_restores_previous_relocated_flag(self):
        self.state.authoring.layout_type = "cross_anchor"
        target = self.state.authoring.selected_target
        original = FakeObject(target.semantic_id, translation=(9, 1, 9))
        self.state.objects.all_rigid_objects.append(original)
        self.state.authoring.anchors[target.semantic_id] = AnchorInfo("static", "table")

        with patch.object(self.handler, "_filter_bboxes_in_view", return_value=[bbox("first")]):
            self.handler.handle_relocate_object(Event(EventType.OBJECT_RELOCATE, 0.0))
        with patch.object(self.handler, "_filter_bboxes_in_view", return_value=[bbox("second")]):
            self.handler.handle_relocate_object(Event(EventType.OBJECT_RELOCATE, 0.0))

        self.handler.handle_undo(Event(EventType.OBJECT_UNDO, 0.0))
        self.assertEqual("first", self.state.authoring.anchors[target.semantic_id].object_id)
        self.assertIn(target.semantic_id, self.state.authoring.relocated_semantic_ids)

        self.handler.handle_undo(Event(EventType.OBJECT_UNDO, 0.0))
        self.assertEqual("static", self.state.authoring.anchors[target.semantic_id].object_id)
        self.assertNotIn(target.semantic_id, self.state.authoring.relocated_semantic_ids)

    def test_delete_and_undo_restore_object(self):
        self.state.authoring.layout_type = "in_anchor"
        target = self.state.authoring.selected_target
        original = FakeObject(target.semantic_id)
        self.state.objects.all_rigid_objects.append(original)
        self.state.authoring.anchors[target.semantic_id] = AnchorInfo("old", "table")
        self.state.authoring.relocated_semantic_ids.add(target.semantic_id)
        self.handler.handle_remove_object(Event(EventType.OBJECT_REMOVE, 0.0))
        self.assertEqual([], self.state.objects.all_rigid_objects)
        self.assertNotIn(target.semantic_id, self.state.authoring.relocated_semantic_ids)
        self.handler.handle_undo(Event(EventType.OBJECT_UNDO, 0.0))
        self.assertEqual(1, len(self.state.objects.all_rigid_objects))
        self.assertEqual("old", self.state.authoring.anchors[target.semantic_id].object_id)
        self.assertIn(target.semantic_id, self.state.authoring.relocated_semantic_ids)


class DataSaverAuthoringTest(unittest.TestCase):
    def test_atomic_named_save_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cfg = OmegaConf.create({
                "scene_name": "scene",
                "scene_path": "/scene.glb",
                "scene_dataset_config": "/dataset.json",
                "save_mode": "action",
                "authoring": {
                    "output_root": temp_dir,
                    "overwrite": False,
                },
            })
            state = configured_state()
            state.authoring.anchors = {
                target.semantic_id: AnchorInfo(f"anchor-{target.key}", "table")
                for target in DUALMAP_TARGETS[:6]
            }
            objects = [FakeObject(target.semantic_id) for target in DUALMAP_TARGETS[:6]]
            mapping = {
                target.semantic_id: target.handle for target in DUALMAP_TARGETS
            }
            saver = DataSaver(cfg, Path(temp_dir))
            path = saver.save_scene_config(mapping, objects, state.authoring)
            self.assertEqual(Path(temp_dir) / "scene" / "static_scene_config.json", path)
            self.assertTrue(path.is_file())
            self.assertFalse(path.with_suffix(".json.tmp").exists())
            saved_data = json.loads(path.read_text())
            self.assertEqual(8, len(saved_data["id_handle_mapping"]))
            self.assertEqual(6, len(saved_data["objects"]))
            with self.assertRaises(FileExistsError):
                saver.save_scene_config(mapping, objects, state.authoring)


class DisabledModeCompatibilityTest(unittest.TestCase):
    def test_normal_input_controls_are_still_dispatched(self):
        state = StateManager()
        events = EventDispatcher()
        received = []
        events.subscribe(EventType.OBJECT_ADD, lambda event: received.append(event.event_type))
        events.subscribe(EventType.RECORDING_START, lambda event: received.append(event.event_type))
        input_handler = InputHandler(state, SimpleNamespace(), events)

        with patch("cv2.waitKey", return_value=ord("=")):
            self.assertTrue(input_handler.poll())
        with patch("cv2.waitKey", return_value=ord(" ")):
            self.assertTrue(input_handler.poll())
        self.assertEqual([EventType.OBJECT_ADD, EventType.RECORDING_START], received)

    def test_recording_handler_rejects_external_start_in_authoring(self):
        state = configured_state()
        sim = SimpleNamespace(cfg={"save_mode": "action"})
        events = EventDispatcher()
        RecordingHandler(state, sim, events)
        events.dispatch(Event(EventType.RECORDING_START, 0.0))
        self.assertFalse(state.app.recording)
        self.assertIn("disabled", state.authoring.last_status)


if __name__ == "__main__":
    unittest.main()
