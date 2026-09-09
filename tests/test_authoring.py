import json
import tempfile
import unittest
from pathlib import Path

from habitat_data_collector.authoring import (
    AnchorInfo,
    AuthoringTarget,
    DUALMAP_MINIMUM_PLACED,
    DUALMAP_TARGETS,
    layout_output_path,
    target_template_handles,
    targets_from_config,
    validate_authoring_layout,
    validate_saved_config,
)


def anchors(prefix="anchor"):
    return {
        target.semantic_id: AnchorInfo(
            object_id=f"{prefix}-{target.semantic_id}",
            category="table",
        )
        for target in DUALMAP_TARGETS
    }


def selected_targets(count=DUALMAP_MINIMUM_PLACED):
    return DUALMAP_TARGETS[:count]


class AuthoringHelpersTest(unittest.TestCase):
    def test_canonical_targets_are_unique(self):
        parsed = targets_from_config([
            {
                "key": target.key,
                "semantic_id": target.semantic_id,
                "handle": target.handle,
            }
            for target in DUALMAP_TARGETS
        ])
        self.assertEqual(list(DUALMAP_TARGETS), parsed)

    def test_duplicate_target_definition_is_rejected(self):
        with self.assertRaises(ValueError):
            targets_from_config([
                {"key": 1, "semantic_id": 1, "handle": "first"},
                {"key": 1, "semantic_id": 2, "handle": "second"},
            ])

    def test_target_keys_must_be_consecutive_digits(self):
        with self.assertRaisesRegex(ValueError, "consecutive digits"):
            targets_from_config([
                {"key": 1, "semantic_id": 1, "handle": "first"},
                {"key": 3, "semantic_id": 2, "handle": "second"},
            ])

    def test_target_template_filtering_and_missing_target(self):
        available = [
            f"/objects/{target.handle}.object_config.json"
            for target in DUALMAP_TARGETS
        ] + ["/objects/999_unrelated.object_config.json"]
        resolved = target_template_handles(available, DUALMAP_TARGETS)
        self.assertEqual(
            {target.semantic_id for target in DUALMAP_TARGETS},
            set(resolved),
        )
        self.assertFalse(any("999_unrelated" in value for value in resolved.values()))

        with self.assertRaisesRegex(ValueError, "006_mustard_bottle"):
            target_template_handles(available[:-2], DUALMAP_TARGETS)

    def test_layout_output_paths(self):
        root = Path("/tmp/authoring")
        self.assertEqual(
            root / "scene" / "static_scene_config.json",
            layout_output_path(root, "scene", "static", None),
        )
        self.assertEqual(
            root
            / "scene"
            / "dynamic_scene_config"
            / "cross_anchor"
            / "layout_03.json",
            layout_output_path(root, "scene", "cross_anchor", 3),
        )
        with self.assertRaises(ValueError):
            layout_output_path(root, "scene", "in_anchor", None)


class RuntimeValidationTest(unittest.TestCase):
    def setUp(self):
        self.ids = [target.semantic_id for target in DUALMAP_TARGETS]
        self.static_anchors = anchors("static")

    def test_valid_static_layout(self):
        result = validate_authoring_layout(
            targets=DUALMAP_TARGETS,
            object_semantic_ids=self.ids[:6],
            anchors=self.static_anchors,
            layout_type="static",
        )
        self.assertTrue(result.valid, result.message)

    def test_fewer_than_six_duplicate_and_unexpected_targets(self):
        result = validate_authoring_layout(
            targets=DUALMAP_TARGETS,
            object_semantic_ids=self.ids[:5] + [self.ids[0], 99999],
            anchors=self.static_anchors,
            layout_type="static",
        )
        self.assertFalse(result.valid)
        self.assertIn("At least 6", result.message)
        self.assertIn("Duplicate target", result.message)
        self.assertIn("Unexpected target", result.message)

    def test_any_six_to_eight_unique_targets_are_valid(self):
        for count in (6, 7, 8):
            with self.subTest(count=count):
                ids = self.ids[-count:]
                result = validate_authoring_layout(
                    targets=DUALMAP_TARGETS,
                    object_semantic_ids=ids,
                    anchors=self.static_anchors,
                    layout_type="static",
                )
                self.assertTrue(result.valid, result.message)

    def test_missing_anchor_is_rejected(self):
        current = dict(self.static_anchors)
        current.pop(self.ids[0])
        result = validate_authoring_layout(
            targets=DUALMAP_TARGETS,
            object_semantic_ids=self.ids,
            anchors=current,
            layout_type="static",
        )
        self.assertFalse(result.valid)
        self.assertIn("Missing anchor metadata", result.message)

    def test_valid_in_anchor_requires_all_relocated(self):
        selected_ids = self.ids[:6]
        result = validate_authoring_layout(
            targets=DUALMAP_TARGETS,
            object_semantic_ids=selected_ids,
            anchors=self.static_anchors,
            baseline_anchors=self.static_anchors,
            baseline_semantic_ids=set(selected_ids),
            relocated_semantic_ids=set(selected_ids),
            layout_type="in_anchor",
        )
        self.assertTrue(result.valid, result.message)

        incomplete = validate_authoring_layout(
            targets=DUALMAP_TARGETS,
            object_semantic_ids=selected_ids,
            anchors=self.static_anchors,
            baseline_anchors=self.static_anchors,
            baseline_semantic_ids=set(selected_ids),
            relocated_semantic_ids=set(selected_ids[:-1]),
            layout_type="in_anchor",
        )
        self.assertFalse(incomplete.valid)
        self.assertIn("not relocated", incomplete.message)

    def test_in_anchor_rejects_changed_anchor(self):
        selected_ids = self.ids[:6]
        current = dict(self.static_anchors)
        current[self.ids[0]] = AnchorInfo("different", "table")
        result = validate_authoring_layout(
            targets=DUALMAP_TARGETS,
            object_semantic_ids=selected_ids,
            anchors=current,
            baseline_anchors=self.static_anchors,
            baseline_semantic_ids=set(selected_ids),
            relocated_semantic_ids=set(selected_ids),
            layout_type="in_anchor",
        )
        self.assertFalse(result.valid)
        self.assertIn("different anchor", result.message)

    def test_cross_anchor_requires_every_anchor_to_change(self):
        selected_ids = self.ids[:6]
        current = anchors("cross")
        valid = validate_authoring_layout(
            targets=DUALMAP_TARGETS,
            object_semantic_ids=selected_ids,
            anchors=current,
            baseline_anchors=self.static_anchors,
            baseline_semantic_ids=set(selected_ids),
            relocated_semantic_ids=set(selected_ids),
            layout_type="cross_anchor",
        )
        self.assertTrue(valid.valid, valid.message)

        current[self.ids[0]] = self.static_anchors[self.ids[0]]
        invalid = validate_authoring_layout(
            targets=DUALMAP_TARGETS,
            object_semantic_ids=selected_ids,
            anchors=current,
            baseline_anchors=self.static_anchors,
            baseline_semantic_ids=set(selected_ids),
            relocated_semantic_ids=set(selected_ids),
            layout_type="cross_anchor",
        )
        self.assertFalse(invalid.valid)
        self.assertIn("still on static anchor", invalid.message)

    def test_dynamic_layout_must_match_static_subset(self):
        selected_ids = set(self.ids[:6])
        result = validate_authoring_layout(
            targets=DUALMAP_TARGETS,
            object_semantic_ids=self.ids[1:7],
            anchors=self.static_anchors,
            baseline_anchors=self.static_anchors,
            baseline_semantic_ids=selected_ids,
            relocated_semantic_ids=selected_ids,
            layout_type="in_anchor",
        )
        self.assertFalse(result.valid)
        self.assertIn("from static layout are missing", result.message)
        self.assertIn("not present in static layout were added", result.message)

    def test_dynamic_layout_rejects_relocation_metadata_for_optional_target(self):
        selected_ids = set(self.ids[:6])
        result = validate_authoring_layout(
            targets=DUALMAP_TARGETS,
            object_semantic_ids=list(selected_ids),
            anchors=self.static_anchors,
            baseline_anchors=self.static_anchors,
            baseline_semantic_ids=selected_ids,
            relocated_semantic_ids=selected_ids | {self.ids[6]},
            layout_type="in_anchor",
        )
        self.assertFalse(result.valid)
        self.assertIn("not in the static layout", result.message)


class SerializedValidationTest(unittest.TestCase):
    def make_data(
        self,
        layout_type="static",
        layout_index=None,
        anchor_prefix="static",
        target_count=DUALMAP_MINIMUM_PLACED,
    ):
        placed_targets = selected_targets(target_count)
        return {
            "scene": {
                "scene_path": "/nonexistent/scene.glb",
                "scene_dataset_config": "/nonexistent/dataset.json",
            },
            "id_handle_mapping": {
                str(target.semantic_id): target.handle
                for target in DUALMAP_TARGETS
            },
            "authoring": {
                "layout_type": layout_type,
                "layout_index": layout_index,
                "relocated_semantic_ids": (
                    []
                    if layout_type == "static"
                    else [target.semantic_id for target in placed_targets]
                ),
            },
            "objects": [
                {
                    "object_id": index,
                    "semantic_id": target.semantic_id,
                    "translation": [float(index), 1.0, 0.0],
                    "rotation": [0.0, 0.0, 0.0, 1.0],
                    "anchor": {
                        "object_id": f"{anchor_prefix}-{target.semantic_id}",
                        "category": "table",
                    },
                }
                for index, target in enumerate(placed_targets)
            ],
        }

    def test_saved_static_round_trip(self):
        data = self.make_data()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "scene.json"
            path.write_text(json.dumps(data))
            loaded = json.loads(path.read_text())
        result = validate_saved_config(
            loaded,
            DUALMAP_TARGETS,
            expected_layout_type="static",
        )
        self.assertTrue(result.valid, result.message)

    def test_saved_cross_anchor_against_static(self):
        static = self.make_data()
        cross = self.make_data("cross_anchor", 1, "cross")
        result = validate_saved_config(
            cross,
            DUALMAP_TARGETS,
            expected_layout_type="cross_anchor",
            expected_layout_index=1,
            baseline_data=static,
        )
        self.assertTrue(result.valid, result.message)

    def test_invalid_quaternion_is_rejected(self):
        data = self.make_data()
        data["objects"][0]["rotation"] = [0.0, 0.0, 0.0, 0.5]
        result = validate_saved_config(data, DUALMAP_TARGETS)
        self.assertFalse(result.valid)
        self.assertIn("quaternion norm", result.message)

    def test_schema_errors_are_reported_without_crashing(self):
        data = self.make_data()
        data["scene"] = []
        data["authoring"] = []
        data["objects"] = "not-an-array"
        result = validate_saved_config(data, DUALMAP_TARGETS)
        self.assertFalse(result.valid)
        self.assertIn("scene must be an object", result.message)
        self.assertIn("authoring must be an object", result.message)
        self.assertIn("objects must be an array", result.message)

        top_level = validate_saved_config([], DUALMAP_TARGETS)
        self.assertFalse(top_level.valid)
        self.assertIn("Top-level JSON", top_level.message)

    def test_invalid_translation_is_rejected(self):
        data = self.make_data()
        data["objects"][0]["translation"] = [0.0, float("inf"), 0.0]
        result = validate_saved_config(data, DUALMAP_TARGETS)
        self.assertFalse(result.valid)
        self.assertIn("invalid translation", result.message)


if __name__ == "__main__":
    unittest.main()
