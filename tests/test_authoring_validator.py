import json
import tempfile
import unittest
from pathlib import Path

from habitat_data_collector.authoring import DUALMAP_MINIMUM_PLACED, DUALMAP_TARGETS
from scripts.validate_dualmap_authoring import validate_scene


def make_layout(layout_type, layout_index=None, anchor_prefix="static"):
    placed_targets = DUALMAP_TARGETS[:DUALMAP_MINIMUM_PLACED]
    return {
        "scene": {
            "scene_path": "/scene.glb",
            "scene_dataset_config": "/dataset.json",
        },
        "id_handle_mapping": {
            str(target.semantic_id): target.handle for target in DUALMAP_TARGETS
        },
        "authoring": {
            "layout_type": layout_type,
            "layout_index": layout_index,
            "reference_static_config": (
                None if layout_type == "static" else "../../static_scene_config.json"
            ),
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


class AuthoringTreeValidatorTest(unittest.TestCase):
    def test_complete_scene_tree(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_root = Path(temp_dir) / "scene"
            scene_root.mkdir()
            (scene_root / "static_scene_config.json").write_text(
                json.dumps(make_layout("static"))
            )
            for layout_type in ("in_anchor", "cross_anchor"):
                for layout_index in (1, 2, 3):
                    path = (
                        scene_root
                        / "dynamic_scene_config"
                        / layout_type
                        / f"layout_{layout_index:02d}.json"
                    )
                    path.parent.mkdir(parents=True, exist_ok=True)
                    prefix = "static" if layout_type == "in_anchor" else "cross"
                    path.write_text(
                        json.dumps(make_layout(layout_type, layout_index, prefix))
                    )
            self.assertEqual([], validate_scene(scene_root, False))

    def test_missing_dynamic_layout_is_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            scene_root = Path(temp_dir) / "scene"
            scene_root.mkdir()
            (scene_root / "static_scene_config.json").write_text(
                json.dumps(make_layout("static"))
            )
            errors = validate_scene(scene_root, False)
            self.assertEqual(6, len(errors))
            self.assertTrue(all("Missing file" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
