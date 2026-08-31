import random
import unittest

from habitat_data_collector.authoring import DUALMAP_TARGETS
from habitat_data_collector.auto_authoring import (
    AnchorCandidate,
    ROOM_UNKNOWN,
    SUPPORT_KINDS,
    affordance_for,
    allowed_anchors,
    anchor_is_usable,
    anchor_kind,
    infer_room_type,
    normalize_category,
    plan_cross_anchor_layout,
    plan_static_layout,
)


def anchor(
    object_id,
    category="table",
    room="kitchen",
    region="_1",
    center=(0.0, 0.4, 0.0),
    size=(1.0, 0.8, 1.0),
):
    return AnchorCandidate(
        object_id=object_id,
        category=category,
        kind=anchor_kind(category) or "table",
        center=center,
        size=size,
        region_id=region,
        room=room,
    )


class CategoryNormalisationTest(unittest.TestCase):
    def test_real_stands_survive_the_stand_blocklist(self):
        self.assertEqual(anchor_kind("tv stand"), "tv_stand")
        self.assertEqual(anchor_kind("night stand"), "nightstand")

    def test_support_categories_map_to_kinds(self):
        self.assertEqual(anchor_kind("kitchen counter"), "counter")
        self.assertEqual(anchor_kind("Dining Table"), "dining_table")
        self.assertEqual(anchor_kind("bedside cabinet"), "nightstand")
        self.assertEqual(anchor_kind("bookshelf"), "shelf")
        self.assertEqual(anchor_kind("chest of drawers"), "chest")

    def test_decorations_that_contain_support_words_are_rejected(self):
        for category in (
            "table lamp",
            "desk lamp",
            "cabinet door",
            "picture frame",
            "tablecloth",
            "pool table",
            "wine rack",
            "coat rack",
            "desk chair",
            "office chair",
            "kitchen countertop items",
            "table stand",
            "baby changing table",
        ):
            self.assertIsNone(anchor_kind(category), category)

    def test_soft_furniture_is_never_a_support_kind(self):
        for category in ("bed", "sofa", "armchair", "chair", "toilet"):
            self.assertNotIn(anchor_kind(category), SUPPORT_KINDS)

    def test_normalisation_squashes_punctuation(self):
        self.assertEqual(normalize_category("Kitchen-Counter  "), "kitchen counter")


class RoomInferenceTest(unittest.TestCase):
    def test_rooms_are_inferred_from_contents(self):
        self.assertEqual(
            infer_room_type(["toilet", "sink", "towel", "mirror"]), "bathroom"
        )
        self.assertEqual(
            infer_room_type(["dishwasher", "oven", "kitchen counter"]), "kitchen"
        )
        self.assertEqual(infer_room_type(["bed", "pillow", "wardrobe"]), "bedroom")
        self.assertEqual(infer_room_type(["sofa", "television"]), "living_room")

    def test_weak_evidence_stays_unknown(self):
        self.assertEqual(infer_room_type(["wall", "floor", "ceiling"]), ROOM_UNKNOWN)


class AffordanceTest(unittest.TestCase):
    def test_food_never_lands_on_soft_furniture(self):
        soup = affordance_for("005_tomato_soup_can")
        self.assertFalse(soup.allows("bed", "bedroom"))
        self.assertFalse(soup.allows("sofa", "living_room"))

    def test_food_never_lands_in_a_bathroom(self):
        for handle in (
            "005_tomato_soup_can",
            "029_plate",
            "024_bowl",
            "011_banana",
        ):
            self.assertFalse(affordance_for(handle).allows("table", "bathroom"), handle)

    def test_tableware_stays_out_of_bedrooms_but_a_mug_may_stay(self):
        self.assertFalse(affordance_for("029_plate").allows("table", "bedroom"))
        self.assertTrue(affordance_for("025_mug").allows("nightstand", "bedroom"))

    def test_unknown_rooms_are_allowed_when_the_surface_fits(self):
        self.assertTrue(affordance_for("024_bowl").allows("counter", ROOM_UNKNOWN))

    def test_every_dualmap_target_has_an_affordance(self):
        for target in DUALMAP_TARGETS:
            self.assertTrue(affordance_for(target.handle).anchor_kinds, target.handle)


class UsabilityTest(unittest.TestCase):
    def test_reachable_mid_height_surface_is_usable(self):
        self.assertTrue(anchor_is_usable(anchor("table_1"), floor_height=0.0))

    def test_surface_that_is_too_high_is_rejected(self):
        high = anchor("shelf_1", "shelf", center=(0.0, 2.4, 0.0), size=(1.0, 0.4, 0.4))
        self.assertFalse(anchor_is_usable(high, floor_height=0.0))

    def test_unreachable_surface_is_rejected(self):
        candidate = anchor("table_2")
        candidate = AnchorCandidate(**{**candidate.__dict__, "navigable": False})
        self.assertFalse(anchor_is_usable(candidate, floor_height=0.0))

    def test_tiny_surface_is_rejected(self):
        tiny = anchor("table_3", size=(0.15, 0.8, 0.15))
        self.assertFalse(anchor_is_usable(tiny, floor_height=0.0))

    def test_upper_storey_surface_is_measured_against_its_own_floor(self):
        upstairs = anchor("table_4", center=(0.0, 3.4, 0.0), size=(1.0, 0.8, 1.0))
        self.assertFalse(anchor_is_usable(upstairs, floor_height=0.0))
        self.assertTrue(anchor_is_usable(upstairs, floor_height=3.0))


class PlanningTest(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(0)
        self.candidates = [
            anchor("counter_1", "kitchen counter", "kitchen", "_1", (0.0, 0.45, 0.0)),
            anchor("table_1", "dining table", "dining_room", "_2", (4.0, 0.4, 0.0)),
            anchor("table_2", "table", "living_room", "_3", (8.0, 0.4, 0.0)),
            anchor("desk_1", "desk", "office", "_4", (12.0, 0.4, 0.0)),
            anchor("shelf_1", "shelf", "kitchen", "_1", (1.0, 0.5, 2.0)),
            anchor("cabinet_1", "cabinet", "kitchen", "_1", (2.0, 0.5, 2.0)),
            anchor("bed_1", "bed", "bedroom", "_5", (16.0, 0.3, 0.0)),
        ]
        self.handles = {t.semantic_id: t.handle for t in DUALMAP_TARGETS}

    def test_static_plan_meets_the_minimum(self):
        plan = plan_static_layout(DUALMAP_TARGETS, self.candidates, self.rng)
        self.assertGreaterEqual(len(plan.assignments), 6)

    def test_static_plan_never_uses_a_bed(self):
        plan = plan_static_layout(DUALMAP_TARGETS, self.candidates, self.rng)
        for candidate in plan.assignments.values():
            self.assertNotEqual(candidate.object_id, "bed_1")

    def test_static_plan_respects_each_target_affordance(self):
        plan = plan_static_layout(DUALMAP_TARGETS, self.candidates, self.rng)
        for semantic_id, candidate in plan.assignments.items():
            affordance = affordance_for(self.handles[semantic_id])
            self.assertTrue(
                affordance.allows(candidate.kind, candidate.room),
                f"{self.handles[semantic_id]} on {candidate.object_id}",
            )

    def test_static_plan_fails_when_no_sensible_anchor_exists(self):
        only_beds = [anchor("bed_1", "bed", "bedroom")]
        plan = plan_static_layout(DUALMAP_TARGETS, only_beds, self.rng)
        self.assertEqual(plan.assignments, {})

    def test_cross_anchor_moves_every_target_to_a_different_anchor(self):
        static = plan_static_layout(DUALMAP_TARGETS, self.candidates, self.rng)
        cross = plan_cross_anchor_layout(
            static.assignments, self.handles, self.candidates, self.rng
        )
        self.assertEqual(set(cross.assignments), set(static.assignments))
        for semantic_id, candidate in cross.assignments.items():
            self.assertNotEqual(
                candidate.object_id, static.assignments[semantic_id].object_id
            )

    def test_cross_anchor_keeps_placements_sensible(self):
        static = plan_static_layout(DUALMAP_TARGETS, self.candidates, self.rng)
        cross = plan_cross_anchor_layout(
            static.assignments, self.handles, self.candidates, self.rng
        )
        for semantic_id, candidate in cross.assignments.items():
            affordance = affordance_for(self.handles[semantic_id])
            self.assertTrue(affordance.allows(candidate.kind, candidate.room))

    def test_allowed_anchors_are_ordered_by_semantic_fit(self):
        ranked = allowed_anchors(self.candidates, "005_tomato_soup_can")
        self.assertTrue(ranked)
        self.assertEqual(ranked[0].room, "kitchen")


if __name__ == "__main__":
    unittest.main()
