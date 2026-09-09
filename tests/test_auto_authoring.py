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
    balanced_floor_quota,
    cluster_floor_levels,
    cross_floor_moves,
    floor_index_for,
    floor_occupancy,
    infer_room_type,
    normalize_category,
    plan_cross_anchor_layout,
    plan_static_layout,
    restrict_to_floors,
    select_cross_floor_movers,
)


def anchor(
    object_id,
    category="table",
    room="kitchen",
    region="_1",
    center=(0.0, 0.4, 0.0),
    size=(1.0, 0.8, 1.0),
    floor=0,
):
    return AnchorCandidate(
        object_id=object_id,
        category=category,
        kind=anchor_kind(category) or "table",
        center=center,
        size=size,
        region_id=region,
        room=room,
        floor_index=floor,
        floor_height=floor * 3.0,
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
            "002_master_chef_can",
            "024_bowl",
            "011_banana",
            "006_mustard_bottle",
        ):
            self.assertFalse(affordance_for(handle).allows("table", "bathroom"), handle)

    def test_tableware_stays_out_of_bedrooms(self):
        self.assertFalse(affordance_for("024_bowl").allows("nightstand", "bedroom"))
        self.assertFalse(
            affordance_for("002_master_chef_can").allows("table", "bedroom")
        )

    def test_a_condiment_belongs_wherever_food_is_served(self):
        mustard = affordance_for("006_mustard_bottle")
        self.assertTrue(mustard.allows("dining_table", "dining_room"))
        self.assertTrue(mustard.allows("counter", "kitchen"))
        self.assertFalse(mustard.allows("nightstand", "bedroom"))
        self.assertFalse(mustard.allows("table", "bathroom"))

    def test_a_toy_lives_away_from_the_kitchen(self):
        toy = affordance_for("072-a_toy_airplane")
        self.assertTrue(toy.allows("shelf", "living_room"))
        self.assertTrue(toy.allows("chest", "bedroom"))
        self.assertTrue(toy.allows("desk", "office"))
        # Not where food is prepared or served.
        self.assertFalse(toy.allows("counter", "kitchen"))
        self.assertFalse(toy.allows("dining_table", "dining_room"))

    def test_no_two_targets_share_a_room_and_surface_profile(self):
        """The set is chosen so the targets are not interchangeable."""
        profiles = {
            target.handle: (
                frozenset(affordance_for(target.handle).anchor_kinds),
                frozenset(affordance_for(target.handle).rooms),
            )
            for target in DUALMAP_TARGETS
        }
        self.assertNotEqual(profiles["072-a_toy_airplane"], profiles["024_bowl"])
        self.assertNotEqual(
            profiles["072-a_toy_airplane"], profiles["006_mustard_bottle"]
        )

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


class FloorClusteringTest(unittest.TestCase):
    """The navmesh heights of a two-storey house, with a staircase between."""

    def two_storey(self):
        heights = [0.0, 3.1]
        areas = [60.0, 40.0]
        for step in range(12):
            heights.append(0.3 + 0.25 * step)
            areas.append(0.4)
        return heights, areas

    def test_a_staircase_does_not_merge_two_storeys(self):
        levels = cluster_floor_levels(*self.two_storey())
        self.assertEqual(len(levels), 2)
        self.assertAlmostEqual(levels[0].height, 0.0, places=2)
        self.assertAlmostEqual(levels[1].height, 3.1, places=2)

    def test_levels_are_ordered_from_the_ground_up(self):
        levels = cluster_floor_levels(*self.two_storey())
        self.assertEqual([level.index for level in levels], [0, 1])
        self.assertLess(levels[0].height, levels[1].height)

    def test_a_flat_scene_is_one_storey(self):
        levels = cluster_floor_levels([0.0, 0.02, -0.01], [10.0, 10.0, 10.0])
        self.assertEqual(len(levels), 1)

    def test_no_heights_means_no_levels(self):
        self.assertEqual(cluster_floor_levels([]), [])

    def test_floor_index_snaps_to_the_nearest_storey(self):
        levels = cluster_floor_levels(*self.two_storey())
        self.assertEqual(floor_index_for(levels, 0.4), 0)
        self.assertEqual(floor_index_for(levels, 2.9), 1)
        self.assertEqual(floor_index_for(levels, 99.0), 1)

    def test_floor_index_without_levels_is_the_ground_floor(self):
        self.assertEqual(floor_index_for([], 12.0), 0)


class FloorRestrictionTest(unittest.TestCase):
    def setUp(self):
        self.candidates = [
            anchor("counter_1", "kitchen counter", "kitchen", "_1", floor=0),
            anchor("table_1", "dining table", "dining_room", "_2", floor=0),
            anchor("shelf_1", "shelf", "kitchen", "_1", floor=0),
            anchor("desk_1", "desk", "office", "_3", floor=1),
            anchor("table_2", "table", "living_room", "_4", floor=1),
            anchor("nightstand_1", "night stand", "bedroom", "_5", floor=1),
            anchor("shelf_2", "shelf", "bedroom", "_6", floor=2),
        ]

    def test_one_floor_keeps_only_the_densest_storey(self):
        kept = restrict_to_floors(self.candidates, max_floors=1)
        self.assertEqual({c.floor_index for c in kept}, {0})

    def test_two_floors_keeps_the_two_densest_storeys(self):
        kept = restrict_to_floors(self.candidates, max_floors=2)
        self.assertEqual({c.floor_index for c in kept}, {0, 1})

    def test_a_nearly_empty_storey_is_not_worth_the_stairs(self):
        kept = restrict_to_floors(self.candidates, max_floors=2, min_anchors=4)
        self.assertEqual({c.floor_index for c in kept}, {0})

    def test_no_candidates_is_not_an_error(self):
        self.assertEqual(restrict_to_floors([], max_floors=2), [])


class MultifloorPlanningTest(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(7)
        self.handles = {t.semantic_id: t.handle for t in DUALMAP_TARGETS}
        self.candidates = [
            anchor("counter_1", "kitchen counter", "kitchen", "_1", (0.0, 0.45, 0.0), floor=0),
            anchor("island_1", "kitchen island", "kitchen", "_1", (2.0, 0.45, 0.0), floor=0),
            anchor("table_1", "dining table", "dining_room", "_2", (4.0, 0.4, 0.0), floor=0),
            anchor("shelf_1", "shelf", "kitchen", "_1", (1.0, 0.5, 2.0), floor=0),
            anchor("desk_1", "desk", "office", "_3", (12.0, 3.4, 0.0), floor=1),
            anchor("table_2", "table", "living_room", "_4", (8.0, 3.4, 0.0), floor=1),
            anchor("counter_2", "counter", "kitchen", "_5", (9.0, 3.45, 2.0), floor=1),
            anchor("cabinet_2", "cabinet", "kitchen", "_5", (10.0, 3.5, 2.0), floor=1),
        ]

    def test_a_floor_quota_spreads_the_static_layout_over_both_storeys(self):
        plan = plan_static_layout(
            DUALMAP_TARGETS,
            self.candidates,
            self.rng,
            floor_quota=balanced_floor_quota([0, 1], 8),
        )
        occupancy = floor_occupancy(plan.assignments)
        self.assertGreaterEqual(occupancy.get(0, 0), 2)
        self.assertGreaterEqual(occupancy.get(1, 0), 2)

    def test_a_quota_that_cannot_be_met_rejects_the_plan(self):
        single_storey = [c for c in self.candidates if c.floor_index == 0]
        plan = plan_static_layout(
            DUALMAP_TARGETS,
            single_storey,
            self.rng,
            floor_quota={0: 4, 1: 4},
        )
        self.assertEqual(plan.assignments, {})

    def test_balanced_quota_splits_evenly(self):
        self.assertEqual(balanced_floor_quota([0, 1], 8), {0: 4, 1: 4})
        self.assertEqual(balanced_floor_quota([2, 0], 7), {0: 4, 2: 3})
        self.assertEqual(balanced_floor_quota([], 8), {})

    def static_plan(self):
        plan = plan_static_layout(
            DUALMAP_TARGETS,
            self.candidates,
            self.rng,
            floor_quota=balanced_floor_quota([0, 1], 8),
        )
        self.assertTrue(plan.assignments)
        return plan

    def test_cross_anchor_moves_the_requested_number_of_storeys(self):
        static = self.static_plan()
        cross = plan_cross_anchor_layout(
            static.assignments,
            self.handles,
            self.candidates,
            self.rng,
            cross_floor_quota=2,
        )
        self.assertTrue(cross.assignments)
        self.assertEqual(len(cross_floor_moves(static.assignments, cross.assignments)), 2)

    def test_cross_anchor_still_changes_every_anchor(self):
        static = self.static_plan()
        cross = plan_cross_anchor_layout(
            static.assignments,
            self.handles,
            self.candidates,
            self.rng,
            cross_floor_quota=2,
        )
        for semantic_id, candidate in cross.assignments.items():
            self.assertNotEqual(
                candidate.object_id, static.assignments[semantic_id].object_id
            )

    def test_a_cross_floor_destination_is_still_affordance_valid(self):
        static = self.static_plan()
        cross = plan_cross_anchor_layout(
            static.assignments,
            self.handles,
            self.candidates,
            self.rng,
            cross_floor_quota=3,
        )
        for semantic_id, candidate in cross.assignments.items():
            affordance = affordance_for(self.handles[semantic_id])
            self.assertTrue(affordance.allows(candidate.kind, candidate.room))

    def test_without_a_quota_nothing_changes_storey(self):
        static = self.static_plan()
        cross = plan_cross_anchor_layout(
            static.assignments,
            self.handles,
            self.candidates,
            self.rng,
        )
        self.assertEqual(cross_floor_moves(static.assignments, cross.assignments), [])

    def test_a_quota_on_a_single_storey_scene_has_no_movers(self):
        ground = [c for c in self.candidates if c.floor_index == 0]
        static = plan_static_layout(DUALMAP_TARGETS, ground, self.rng)
        self.assertEqual(
            select_cross_floor_movers(
                static.assignments, self.handles, ground, self.rng, quota=2
            ),
            set(),
        )

    def test_sibling_layouts_do_not_repeat_the_same_floor_change(self):
        static = self.static_plan()
        first = plan_cross_anchor_layout(
            static.assignments,
            self.handles,
            self.candidates,
            self.rng,
            cross_floor_quota=1,
        )
        second = plan_cross_anchor_layout(
            static.assignments,
            self.handles,
            self.candidates,
            self.rng,
            avoid=[first.assignments],
            cross_floor_quota=1,
        )
        self.assertNotEqual(
            cross_floor_moves(static.assignments, first.assignments),
            cross_floor_moves(static.assignments, second.assignments),
        )


if __name__ == "__main__":
    unittest.main()
