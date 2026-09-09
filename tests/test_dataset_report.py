import pathlib
import unittest

from habitat_data_collector.authoring import (
    discover_layout_slots,
    layout_slots,
    slot_name,
)
from habitat_data_collector.dataset_report import (
    MAX_CANDIDATE_SCORE,
    DatasetSummary,
    build_placements,
    build_scene_report,
    parse_slot,
    semantic_correspondence,
    sort_key,
)


def anchor(
    object_id="counter_1",
    category="kitchen counter",
    kind="counter",
    room="kitchen",
    floor=0,
    footprint=1.5,
    top_y=0.9,
):
    return {
        "object_id": object_id,
        "category": category,
        "kind": kind,
        "room": room,
        "region_id": "_1",
        "floor_index": floor,
        "floor_height": floor * 3.0,
        "top_y": top_y,
        "footprint": footprint,
    }


def layout(objects, layout_type="static", index=None, floors=(0, 1), multifloor=True):
    return {
        "id_handle_mapping": {"50008": "002_master_chef_can", "50002": "005_tomato_soup_can"},
        "objects": objects,
        "authoring": {
            "layout_type": layout_type,
            "layout_index": index,
            "multifloor": multifloor,
            "seed": 20260828,
            "floors": [
                {"index": f, "height": f * 3.0, "navmesh_share": 0.5} for f in floors
            ],
        },
    }


def obj(semantic_id, translation, anchor_block):
    return {
        "object_id": 1,
        "translation": list(translation),
        "rotation": [0.0, 0.0, 0.0, 1.0],
        "semantic_id": semantic_id,
        "anchor": anchor_block,
    }


class SemanticCorrespondenceTest(unittest.TestCase):
    def test_a_perfect_placement_scores_one(self):
        score = semantic_correspondence("005_tomato_soup_can", anchor())
        self.assertEqual(score, 1.0)

    def test_every_score_is_within_the_unit_range(self):
        for room in ("kitchen", "living_room", "unknown"):
            for kind, category in (("counter", "counter"), ("shelf", "shelf")):
                score = semantic_correspondence(
                    "002_master_chef_can", anchor(kind=kind, category=category, room=room)
                )
                self.assertGreaterEqual(score, 0.0)
                self.assertLessEqual(score, 1.0)

    def test_a_preferred_room_beats_an_unknown_one(self):
        preferred = semantic_correspondence("002_master_chef_can", anchor(room="kitchen"))
        unknown = semantic_correspondence("002_master_chef_can", anchor(room="unknown"))
        self.assertGreater(preferred, unknown)

    def test_a_top_ranked_surface_beats_a_marginal_one(self):
        best = semantic_correspondence("002_master_chef_can", anchor(kind="counter"))
        marginal = semantic_correspondence(
            "002_master_chef_can", anchor(kind="tv_stand", category="tv stand")
        )
        self.assertGreater(best, marginal)

    def test_a_degenerate_surface_still_scores(self):
        score = semantic_correspondence("002_master_chef_can", anchor(footprint=0.0))
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    def test_the_maximum_matches_the_scoring_rule(self):
        self.assertEqual(MAX_CANDIDATE_SCORE, 4.0)


class PlacementDiffTest(unittest.TestCase):
    def setUp(self):
        self.static = layout(
            [
                obj(50002, (0.0, 0.95, 0.0), anchor()),
                obj(
                    50008,
                    (1.0, 3.95, 0.0),
                    anchor("desk_1", "desk", "desk", "office", floor=1, top_y=3.9),
                ),
            ]
        )

    def test_a_static_layout_has_no_movement(self):
        placements = build_placements(self.static)
        self.assertTrue(all(p.distance is None for p in placements))
        self.assertTrue(all(not p.changed_floor for p in placements))

    def test_movement_is_measured_against_the_static_layout(self):
        moved = layout(
            [
                obj(50002, (3.0, 0.95, 4.0), anchor("table_1", "table", "table")),
                obj(
                    50008,
                    (1.0, 3.95, 0.0),
                    anchor("desk_1", "desk", "desk", "office", floor=1, top_y=3.9),
                ),
            ],
            layout_type="cross_anchor",
            index=1,
        )
        by_id = {p.semantic_id: p for p in build_placements(moved, self.static)}
        self.assertAlmostEqual(by_id[50002].distance, 5.0, places=3)
        self.assertAlmostEqual(by_id[50002].horizontal, 5.0, places=3)
        self.assertAlmostEqual(by_id[50002].dz, 0.0, places=3)
        self.assertTrue(by_id[50002].changed_anchor)
        self.assertAlmostEqual(by_id[50008].distance, 0.0, places=3)

    def test_a_storey_change_is_detected_with_its_height_delta(self):
        upstairs = layout(
            [
                obj(
                    50002,
                    (0.0, 3.95, 0.0),
                    anchor("counter_2", "counter", "counter", floor=1, top_y=3.9),
                ),
                obj(
                    50008,
                    (1.0, 3.95, 0.0),
                    anchor("desk_1", "desk", "desk", "office", floor=1, top_y=3.9),
                ),
            ],
            layout_type="cross_anchor",
            index=1,
        )
        by_id = {p.semantic_id: p for p in build_placements(upstairs, self.static)}
        self.assertTrue(by_id[50002].changed_floor)
        self.assertAlmostEqual(by_id[50002].dz, 3.0, places=3)
        self.assertFalse(by_id[50008].changed_floor)


class SceneReportTest(unittest.TestCase):
    def scene(self):
        static = layout(
            [
                obj(50002, (0.0, 0.95, 0.0), anchor()),
                obj(
                    50008,
                    (1.0, 3.95, 0.0),
                    anchor("desk_1", "desk", "desk", "office", floor=1, top_y=3.9),
                ),
            ]
        )
        cross = layout(
            [
                obj(50002, (4.0, 0.95, 0.0), anchor("table_1", "table", "table")),
                obj(
                    50008,
                    (2.0, 0.95, 0.0),
                    anchor("counter_1", "kitchen counter", "counter"),
                ),
            ],
            layout_type="cross_anchor",
            index=1,
        )
        return build_scene_report("00844-test", {"static": static, "cross_anchor_01": cross})

    def test_missing_slots_are_skipped_rather_than_fabricated(self):
        report = self.scene()
        self.assertEqual(len(report.layouts), 2)
        self.assertIsNone(report.layout("in_anchor_01"))

    def test_the_scene_reports_its_storeys_and_targets(self):
        report = self.scene()
        self.assertTrue(report.multifloor)
        self.assertEqual(report.seed, 20260828)
        self.assertEqual(report.placed_targets, 2)
        self.assertEqual(report.floors_used, [0, 1])
        self.assertEqual(report.floor_height, {0: 0.0, 1: 3.0})

    def test_cross_floor_relocations_are_counted(self):
        report = self.scene()
        self.assertEqual(report.cross_floor_moves, 1)
        moves = report.cross_anchor[0].floor_changes
        self.assertEqual([p.handle for p in moves], ["002_master_chef_can"])

    def test_layout_metrics_summarise_the_movement(self):
        cross = self.scene().cross_anchor[0]
        self.assertAlmostEqual(cross.max_move, 4.0, places=3)
        self.assertAlmostEqual(cross.mean_abs_dz, 1.5, places=3)
        self.assertEqual(cross.distinct_anchors, 2)

    def test_dataset_summary_aggregates_every_scene(self):
        summary = DatasetSummary([self.scene(), self.scene()])
        self.assertEqual(len(summary.multifloor_scenes), 2)
        self.assertEqual(summary.layout_count, 4)
        self.assertEqual(summary.placement_count, 8)
        self.assertEqual(summary.cross_floor_moves, 2)
        self.assertGreater(summary.mean_correspondence, 0.0)
        self.assertIsNone(summary.mean_in_anchor_move)


class SlotNameTest(unittest.TestCase):
    def test_slot_names_match_the_files_on_disk(self):
        self.assertEqual(slot_name("static", None), "static")
        self.assertEqual(slot_name("in_anchor", 2), "in_anchor_02")
        self.assertEqual(slot_name("cross_anchor", 3), "cross_anchor_03")

    def test_parsing_a_slot_name_round_trips(self):
        for layout_type, index in layout_slots(3):
            self.assertEqual(parse_slot(slot_name(layout_type, index)),
                             (layout_type, index))

    def test_layouts_are_reviewed_baseline_first(self):
        names = ["cross_anchor_01", "in_anchor_02", "static", "in_anchor_01"]
        self.assertEqual(
            sorted(names, key=sort_key),
            ["static", "in_anchor_01", "in_anchor_02", "cross_anchor_01"],
        )

    def test_one_layout_per_kind_is_a_three_slot_scene(self):
        self.assertEqual(
            layout_slots(1),
            (("static", None), ("in_anchor", 1), ("cross_anchor", 1)),
        )

    def test_a_scene_needs_at_least_one_layout_of_each_kind(self):
        with self.assertRaises(ValueError):
            layout_slots(0)


class DiscoverLayoutsTest(unittest.TestCase):
    """The tools read the layout count off disk instead of assuming one."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)

    def write(self, per_kind):
        scene = self.root / "scene"
        (scene).mkdir(parents=True, exist_ok=True)
        (scene / "static_scene_config.json").write_text("{}")
        for kind in ("in_anchor", "cross_anchor"):
            directory = scene / "dynamic_scene_config" / kind
            directory.mkdir(parents=True, exist_ok=True)
            for index in range(1, per_kind + 1):
                (directory / f"layout_{index:02d}.json").write_text("{}")

    def test_a_three_layout_scene_reports_three_slots(self):
        self.write(1)
        self.assertEqual(
            discover_layout_slots(self.root, "scene"),
            (("static", None), ("in_anchor", 1), ("cross_anchor", 1)),
        )

    def test_a_seven_layout_scene_reports_seven_slots(self):
        self.write(3)
        self.assertEqual(len(discover_layout_slots(self.root, "scene")), 7)

    def test_an_unauthored_scene_reports_nothing(self):
        self.assertEqual(discover_layout_slots(self.root, "scene"), ())


if __name__ == "__main__":
    unittest.main()
