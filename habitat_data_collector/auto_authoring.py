"""Semantic planning for automated DualMap scene authoring.

Pure data and logic.  Nothing here imports Habitat, so the placement rules can
be unit tested without a simulator or a display.

The interactive authoring mode lets a human decide *where* each YCB target
belongs.  This module encodes that judgement so layouts can be generated in
batch:

* HM3D support objects are normalised into a small set of anchor kinds.
* Each region is classified into a room type from the categories it contains.
* Each YCB target declares the anchor kinds and room types that make sense for
  it, so a soup can never lands on a bed and a plate never lands in a bathroom.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


# ---------------------------------------------------------------------------
# Category normalisation
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[^a-z0-9]+")


def normalize_category(name: object) -> str:
    """Lower-case and squash punctuation in a raw HM3D category string."""

    text = _WORD_RE.sub(" ", str(name).lower()).strip()
    return re.sub(r"\s+", " ", text)


#: Categories that contain a support word but are not support surfaces.
#: Without this guard ``table lamp`` matches the ``table`` rule and a pair of
#: scissors ends up balanced on a lampshade.
_NON_SUPPORT_KEYWORDS: Tuple[str, ...] = (
    "lamp", "chandelier", "light", "curtain", "cloth", "tablecloth", "mat",
    "rug", "carpet", "door", "handle", "knob", "leg", "frame", "mirror",
    "picture", "poster", "painting", "sign", "plant", "flowerpot", "vase",
    "cushion", "pillow", "blanket", "runner", "cover", "skirt", "football",
    "tennis", "billiard", "pool table", "radiator", "heater", "fan", "clock",
    "shelf bracket", "cabinet door", "drawer front",
    # Racks hold bottles, coats, or plates on edge; nothing rests flat on them.
    "rack",
    # No chair is a support surface, and "desk chair" would match ``desk``.
    "chair",
    # HM3D labels clutter on a surface as its own object; that blob is not an
    # anchor, and "kitchen countertop items" would match ``counter``.
    "item", "items", "clutter", "objects",
    # Stands that support one specific thing.  ``tv stand`` and ``night stand``
    # are real supports and are matched by their own rules below, so only the
    # single-purpose compounds are listed here.
    "table stand", "plant stand", "umbrella stand", "coat stand",
    "monitor stand", "lamp stand", "music stand",
    # A nursery changing table is not a place for kitchenware.
    "changing table",
)

# Anchor kinds are ordered most specific first: the first rule that matches a
# raw HM3D category wins.  HM3D annotations are free text, so matching is done
# on keywords rather than on an exact vocabulary.
_ANCHOR_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("counter", ("kitchen counter", "counter top", "countertop", "worktop",
                 "kitchen worktop", "bar counter", "counter")),
    ("island", ("kitchen island", "island")),
    ("dining_table", ("dining table", "kitchen table", "breakfast table")),
    ("coffee_table", ("coffee table", "side table", "end table")),
    ("nightstand", ("nightstand", "night stand", "bedside table",
                    "bedside cabinet", "bed side table")),
    ("desk", ("desk", "writing table", "computer table", "office table")),
    ("tv_stand", ("tv stand", "tv cabinet", "tv table", "media console",
                  "television stand")),
    ("sideboard", ("sideboard", "buffet", "credenza", "console table")),
    ("chest", ("chest of drawers", "dresser", "drawer unit", "drawers")),
    ("shelf", ("bookshelf", "book shelf", "shelving", "shelf", "bookcase",
               "book case", "cupboard shelf")),
    ("cabinet", ("kitchen cabinet", "cabinet", "cupboard", "wardrobe")),
    ("table", ("table",)),
    ("stool", ("stool", "ottoman")),
    ("bench", ("bench",)),
    # Recognised but never used as supports; listed so they can be reported.
    ("bed", ("bed",)),
    ("sofa", ("sofa", "couch", "armchair")),
    ("chair", ("chair",)),
    ("toilet", ("toilet",)),
    ("sink", ("sink", "washbasin", "wash basin")),
    ("bathtub", ("bathtub", "bath tub", "shower")),
)


def anchor_kind(raw_category: object) -> Optional[str]:
    """Map a raw HM3D category onto a normalised anchor kind."""

    text = normalize_category(raw_category)
    if not text:
        return None
    for keyword in _NON_SUPPORT_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", text):
            return None
    for kind, keywords in _ANCHOR_RULES:
        for keyword in keywords:
            if keyword == text or re.search(rf"\b{re.escape(keyword)}\b", text):
                return kind
    return None


#: Anchor kinds a YCB target may ever rest on.  ``bed``/``sofa``/``chair`` are
#: deliberately excluded: the released DualMap data places table-top objects on
#: soft furniture, which produces nonsensical queries such as a soup can on a
#: bed.
SUPPORT_KINDS: Tuple[str, ...] = (
    "counter",
    "island",
    "dining_table",
    "coffee_table",
    "table",
    "desk",
    "nightstand",
    "sideboard",
    "chest",
    "shelf",
    "cabinet",
    "tv_stand",
)


# ---------------------------------------------------------------------------
# Room inference
# ---------------------------------------------------------------------------

#: HM3D region annotations carry no category name, so the room type is inferred
#: from the categories of the objects the region contains.
_ROOM_INDICATORS: Dict[str, Tuple[Tuple[str, float], ...]] = {
    "bathroom": (
        ("toilet", 4.0), ("bathtub", 3.0), ("bath tub", 3.0), ("shower", 3.0),
        ("washbasin", 2.0), ("towel", 1.0), ("toilet paper", 2.0),
        ("bidet", 3.0), ("shower curtain", 2.0),
    ),
    "kitchen": (
        ("dishwasher", 3.0), ("oven", 3.0), ("stove", 3.0), ("microwave", 2.5),
        ("refrigerator", 3.0), ("fridge", 3.0), ("kitchen appliance", 2.5),
        ("ventilation hood", 3.0), ("extractor hood", 3.0), ("range hood", 3.0),
        ("coffee machine", 2.0), ("kitchen counter", 3.0), ("kitchen cabinet", 2.0),
        ("pot", 1.0), ("pan", 1.0), ("kettle", 1.5), ("toaster", 1.5),
        ("cutting board", 1.5), ("dish", 1.0), ("kitchen island", 3.0),
    ),
    "dining_room": (
        ("dining table", 3.0), ("dining chair", 2.0), ("tableware", 1.5),
        ("wine glass", 1.5), ("candlestick", 1.0), ("placemat", 1.5),
    ),
    "bedroom": (
        ("bed", 4.0), ("nightstand", 2.0), ("bedside", 2.0), ("wardrobe", 1.5),
        ("pillow", 1.0), ("blanket", 1.0), ("mattress", 2.5), ("headboard", 2.0),
    ),
    "living_room": (
        ("sofa", 3.0), ("couch", 3.0), ("coffee table", 2.0), ("tv", 2.0),
        ("television", 2.0), ("armchair", 1.5), ("fireplace", 1.5),
        ("tv stand", 1.5),
    ),
    "office": (
        ("desk", 2.5), ("computer", 2.5), ("monitor", 2.5), ("laptop", 2.0),
        ("keyboard", 1.5), ("office chair", 2.5), ("printer", 2.0),
        ("bookshelf", 1.0),
    ),
    "hallway": (
        ("stairs", 2.0), ("staircase", 2.0), ("banister", 1.5),
        ("coat rack", 1.5), ("shoe", 1.0), ("elevator", 2.0),
    ),
    "utility": (
        ("washing machine", 3.0), ("dryer", 2.5), ("laundry basket", 2.0),
        ("boiler", 2.0), ("water heater", 2.0), ("tool", 1.0),
    ),
    "garage": (
        ("car", 3.0), ("bicycle", 1.5), ("garage door", 3.0),
        ("cans of paint", 1.0),
    ),
}

#: Rooms where table-top kitchenware never belongs.
UNSUITABLE_ROOMS: Tuple[str, ...] = ("bathroom", "garage", "utility")

ROOM_UNKNOWN = "unknown"


def infer_room_type(
    categories: Iterable[object],
    *,
    minimum_score: float = 3.0,
) -> str:
    """Classify a region from the raw categories of the objects it contains."""

    normalized = [normalize_category(value) for value in categories]
    scores: Dict[str, float] = {}
    for room, indicators in _ROOM_INDICATORS.items():
        total = 0.0
        for keyword, weight in indicators:
            pattern = re.compile(rf"\b{re.escape(keyword)}\b")
            hits = sum(1 for text in normalized if pattern.search(text))
            if hits:
                # Repeated evidence helps, but a wall of chairs must not
                # outweigh a single toilet.
                total += weight * (1.0 + math.log(hits))
        if total:
            scores[room] = total
    if not scores:
        return ROOM_UNKNOWN
    room, score = max(scores.items(), key=lambda item: item[1])
    if score < minimum_score:
        return ROOM_UNKNOWN
    return room


# ---------------------------------------------------------------------------
# Target affordances
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TargetAffordance:
    """Where one YCB target is allowed to be placed."""

    handle: str
    anchor_kinds: Tuple[str, ...]
    rooms: Tuple[str, ...]
    preferred_rooms: Tuple[str, ...] = ()

    def allows(self, kind: str, room: str) -> bool:
        if kind not in self.anchor_kinds:
            return False
        if room in UNSUITABLE_ROOMS:
            return False
        if room == ROOM_UNKNOWN:
            return True
        return room in self.rooms


#: Surfaces where food and tableware belong.  ``tv_stand`` is deliberately
#: absent: a plate or a soup can on a television stand is the kind of
#: placement that makes the released DualMap queries read as nonsense.
_FOOD_PREP_SURFACES = (
    "counter", "island", "dining_table", "table", "sideboard", "shelf",
    "cabinet", "coffee_table",
)
_FOOD_ROOMS = ("kitchen", "dining_room", "living_room")

#: Keyed by YCB handle, matching ``authoring.targets`` in the collector config.
TARGET_AFFORDANCES: Dict[str, TargetAffordance] = {
    "003_cracker_box": TargetAffordance(
        "003_cracker_box",
        anchor_kinds=_FOOD_PREP_SURFACES + ("chest", "tv_stand"),
        rooms=_FOOD_ROOMS + ("office",),
        preferred_rooms=("kitchen", "dining_room"),
    ),
    "005_tomato_soup_can": TargetAffordance(
        "005_tomato_soup_can",
        anchor_kinds=_FOOD_PREP_SURFACES,
        rooms=_FOOD_ROOMS,
        preferred_rooms=("kitchen",),
    ),
    "011_banana": TargetAffordance(
        "011_banana",
        anchor_kinds=("counter", "island", "dining_table", "table",
                      "coffee_table", "sideboard"),
        rooms=_FOOD_ROOMS,
        preferred_rooms=("kitchen", "dining_room"),
    ),
    "019_pitcher_base": TargetAffordance(
        "019_pitcher_base",
        anchor_kinds=("counter", "island", "dining_table", "table",
                      "sideboard", "shelf", "cabinet"),
        rooms=_FOOD_ROOMS,
        preferred_rooms=("kitchen", "dining_room"),
    ),
    "024_bowl": TargetAffordance(
        "024_bowl",
        anchor_kinds=_FOOD_PREP_SURFACES,
        rooms=_FOOD_ROOMS,
        preferred_rooms=("kitchen", "dining_room"),
    ),
    # A toy, and the only target that is not kitchen goods.  It belongs where
    # people keep and play with things -- a living room shelf, a bedroom chest,
    # a desk -- and not on a kitchen counter or a laid dining table.  That
    # deliberately pulls one target out of the kitchen in every scene, which
    # spreads the layout instead of piling everything onto the worktop.
    "072-a_toy_airplane": TargetAffordance(
        "072-a_toy_airplane",
        anchor_kinds=("table", "coffee_table", "desk", "shelf", "cabinet",
                      "chest", "nightstand", "tv_stand", "sideboard"),
        rooms=("living_room", "bedroom", "office"),
        preferred_rooms=("living_room", "bedroom"),
    ),
    "002_master_chef_can": TargetAffordance(
        "002_master_chef_can",
        anchor_kinds=_FOOD_PREP_SURFACES,
        rooms=_FOOD_ROOMS,
        preferred_rooms=("kitchen", "dining_room"),
    ),
    # A condiment: the same reach as the other food items, and at home on a
    # dining table in a way the scissors it replaced never were.
    "006_mustard_bottle": TargetAffordance(
        "006_mustard_bottle",
        anchor_kinds=_FOOD_PREP_SURFACES,
        rooms=_FOOD_ROOMS,
        preferred_rooms=("kitchen", "dining_room"),
    ),
}


def affordance_for(handle: str) -> TargetAffordance:
    """Return the affordance for a YCB handle, or a permissive table-top rule."""

    try:
        return TARGET_AFFORDANCES[handle]
    except KeyError:
        return TargetAffordance(
            handle,
            anchor_kinds=_FOOD_PREP_SURFACES,
            rooms=_FOOD_ROOMS + ("office", "bedroom"),
        )


# ---------------------------------------------------------------------------
# Storeys
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FloorLevel:
    """One storey of a scene, derived from the navigable heights."""

    index: int
    #: Representative navigable height, the mean of the cluster.
    height: float
    y_min: float
    y_max: float
    #: Fraction of the navmesh that sits on this storey.
    share: float

    def contains(self, y: float, tolerance: float = 0.6) -> bool:
        return self.y_min - tolerance <= y <= self.y_max + tolerance


def cluster_floor_levels(
    heights: Sequence[float],
    weights: Optional[Sequence[float]] = None,
    *,
    min_gap: float = 1.3,
    min_share: float = 0.04,
    bin_share: float = 0.01,
    bin_size: float = 0.10,
) -> List[FloorLevel]:
    """Group navigable heights into storeys.

    HM3D scenes carry no storey annotation, so the storeys are read off the
    navmesh: a house has navigable area concentrated at a few heights.

    Simply merging neighbouring heights does not work, because a staircase is
    navigable at *every* height in between and chains the storeys into one
    cluster.  Instead the histogram is thresholded first: a bin holding less
    than ``bin_share`` of the navigable area is a stair tread, not a floor, and
    acts as a separator.  ``weights`` should therefore be navmesh triangle
    areas -- vertex counts describe boundary detail, not area, and a large open
    floor may have fewer vertices than a cluttered landing.

    Returns at least one level whenever ``heights`` is non-empty, ordered from
    the lowest storey up, so callers never have to special-case a flat scene.
    """

    samples = [
        (float(height), float(weight))
        for height, weight in zip(
            heights,
            weights if weights is not None else [1.0] * len(heights),
        )
        if math.isfinite(float(height)) and math.isfinite(float(weight))
    ]
    if not samples:
        return []

    buckets: Dict[int, List[Tuple[float, float]]] = {}
    for height, weight in samples:
        buckets.setdefault(int(math.floor(height / bin_size)), []).append(
            (height, weight)
        )

    total = sum(weight for _, weight in samples) or 1.0
    dense = [
        key
        for key in sorted(buckets)
        if sum(weight for _, weight in buckets[key]) / total >= bin_share
    ]
    if not dense:
        dense = [max(buckets, key=lambda key: sum(w for _, w in buckets[key]))]

    groups: List[List[int]] = [[dense[0]]]
    for key in dense[1:]:
        if (key - groups[-1][-1]) * bin_size <= min_gap:
            groups[-1].append(key)
        else:
            groups.append([key])

    levels: List[Tuple[float, float, float, float]] = []
    for group in groups:
        entries = [entry for key in group for entry in buckets[key]]
        mass = sum(weight for _, weight in entries)
        if mass / total < min_share:
            continue
        centre = sum(h * w for h, w in entries) / mass
        levels.append(
            (centre, min(h for h, _ in entries), max(h for h, _ in entries), mass / total)
        )

    if not levels:
        entries = [entry for key in max(groups, key=len) for entry in buckets[key]]
        mass = sum(weight for _, weight in entries) or 1.0
        levels = [
            (
                sum(h * w for h, w in entries) / mass,
                min(h for h, _ in entries),
                max(h for h, _ in entries),
                1.0,
            )
        ]

    return [
        FloorLevel(index=index, height=centre, y_min=low, y_max=high, share=share)
        for index, (centre, low, high, share) in enumerate(levels)
    ]


def floor_index_for(floors: Sequence[FloorLevel], y: float) -> int:
    """Storey whose navigable height is closest to ``y``."""

    if not floors:
        return 0
    return min(floors, key=lambda floor: abs(floor.height - y)).index


# ---------------------------------------------------------------------------
# Anchor candidates
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AnchorCandidate:
    """One HM3D semantic object usable as a support surface."""

    object_id: str
    category: str
    kind: str
    center: Tuple[float, float, float]
    size: Tuple[float, float, float]
    region_id: str
    room: str
    navigable: bool = True
    #: Index of the storey this anchor stands on, 0 for the lowest.
    floor_index: int = 0
    #: Navigable height of that storey, used for the reachability test.
    floor_height: float = 0.0

    @property
    def top_y(self) -> float:
        return self.center[1] + self.size[1] / 2.0

    @property
    def footprint(self) -> float:
        return self.size[0] * self.size[2]

    def horizontal_distance(self, other: "AnchorCandidate") -> float:
        return math.dist(
            (self.center[0], self.center[2]), (other.center[0], other.center[2])
        )


def anchor_is_usable(
    candidate: AnchorCandidate,
    *,
    floor_height: float,
    min_top_height: float = 0.30,
    max_top_height: float = 1.45,
    min_footprint: float = 0.10,
    max_footprint: float = 12.0,
) -> bool:
    """Reject supports that are unreachable, too small, or degenerate.

    ``floor_height`` is the height of the floor the anchor stands on, so the
    test still works in multi-storey scenes.
    """

    if candidate.kind not in SUPPORT_KINDS:
        return False
    if not candidate.navigable:
        return False
    if any(not math.isfinite(value) or value <= 0.0 for value in candidate.size):
        return False
    height = candidate.top_y - floor_height
    if not min_top_height <= height <= max_top_height:
        return False
    if not min_footprint <= candidate.footprint <= max_footprint:
        return False
    return True


def candidate_score(
    candidate: AnchorCandidate,
    affordance: TargetAffordance,
) -> float:
    """Rank an allowed anchor.  Higher is a better semantic fit."""

    score = 1.0
    if candidate.room in affordance.preferred_rooms:
        score += 2.0
    elif candidate.room != ROOM_UNKNOWN:
        score += 0.5
    if candidate.kind in affordance.anchor_kinds[:3]:
        score += 0.5
    # Mid-sized surfaces are the most natural place for table-top objects.
    if 0.2 <= candidate.footprint <= 3.0:
        score += 0.5
    return score


def allowed_anchors(
    candidates: Sequence[AnchorCandidate],
    handle: str,
) -> List[AnchorCandidate]:
    """All anchors a target may use, best semantic fit first."""

    affordance = affordance_for(handle)
    allowed = [
        candidate
        for candidate in candidates
        if affordance.allows(candidate.kind, candidate.room)
    ]
    allowed.sort(key=lambda c: -candidate_score(c, affordance))
    return allowed


def floors_by_anchor_count(
    candidates: Sequence[AnchorCandidate],
) -> List[Tuple[int, int]]:
    """``(floor_index, usable anchor count)`` pairs, densest storey first."""

    counts: Dict[int, int] = {}
    for candidate in candidates:
        counts[candidate.floor_index] = counts.get(candidate.floor_index, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def restrict_to_floors(
    candidates: Sequence[AnchorCandidate],
    *,
    max_floors: int = 1,
    min_anchors: int = 3,
) -> List[AnchorCandidate]:
    """Keep the anchors on the ``max_floors`` densest storeys.

    One storey is the default: it keeps a single recording trajectory viable.
    A multi-storey dataset asks for two, and a storey with almost no usable
    anchors is not worth walking upstairs for, hence ``min_anchors``.
    """

    if not candidates:
        return []
    ranked = floors_by_anchor_count(candidates)
    chosen = {floor for floor, count in ranked[:1]}
    for floor, count in ranked[1:max_floors]:
        if count >= min_anchors:
            chosen.add(floor)
    return [
        candidate for candidate in candidates if candidate.floor_index in chosen
    ]


# ---------------------------------------------------------------------------
# Layout planning
# ---------------------------------------------------------------------------


@dataclass
class LayoutPlan:
    """Anchor assignment for one layout slot."""

    assignments: Dict[int, AnchorCandidate] = field(default_factory=dict)

    @property
    def semantic_ids(self) -> Set[int]:
        return set(self.assignments)


def plan_static_layout(
    targets: Sequence["object"],
    candidates: Sequence[AnchorCandidate],
    rng: random.Random,
    *,
    minimum_placed: int = 6,
    maximum_placed: int = 8,
    max_per_anchor: int = 2,
    floor_quota: Optional[Mapping[int, int]] = None,
    min_per_floor: int = 2,
) -> LayoutPlan:
    """Assign as many targets as possible to semantically valid anchors.

    Targets with the fewest valid anchors are assigned first so that a scarce
    anchor is not consumed by a target that had alternatives.

    ``floor_quota`` maps a storey index to the number of targets that should
    land on it.  A multi-storey scene passes one so the static layout actually
    spreads over both floors instead of collapsing onto whichever storey scores
    best; the plan is rejected if any quota floor ends up with fewer than
    ``min_per_floor`` targets, since a single object upstairs is not enough to
    exercise a cross-floor query.
    """

    options = {
        target.semantic_id: allowed_anchors(candidates, target.handle)
        for target in targets
    }
    order = sorted(
        targets,
        key=lambda target: (len(options[target.semantic_id]), target.key),
    )
    plan = LayoutPlan()
    used: Dict[str, int] = {}
    used_regions: Dict[str, int] = {}
    remaining = dict(floor_quota) if floor_quota else {}

    for target in order:
        if len(plan.assignments) >= maximum_placed:
            break
        choices = [
            candidate
            for candidate in options[target.semantic_id]
            if used.get(candidate.object_id, 0) < max_per_anchor
        ]
        if not choices:
            continue
        if remaining:
            # Prefer a storey that still owes targets, but never drop a target
            # only because its affordable anchors all sit on a filled floor.
            hungry = [
                candidate
                for candidate in choices
                if remaining.get(candidate.floor_index, 0) > 0
            ]
            choices = hungry or choices
        affordance = affordance_for(target.handle)
        best = max(
            choices,
            key=lambda candidate: (
                candidate_score(candidate, affordance)
                # Spread objects over anchors and rooms before doubling up.
                # Eight targets on one worktop is a scene where nothing can be
                # told apart, so the penalties are heavier than the score.
                - 4.0 * used.get(candidate.object_id, 0)
                - 1.2 * used_regions.get(candidate.region_id, 0)
                + rng.random() * 0.25
            ),
        )
        plan.assignments[target.semantic_id] = best
        used[best.object_id] = used.get(best.object_id, 0) + 1
        used_regions[best.region_id] = used_regions.get(best.region_id, 0) + 1
        if best.floor_index in remaining:
            remaining[best.floor_index] -= 1

    if len(plan.assignments) < minimum_placed:
        return LayoutPlan()
    if floor_quota:
        occupancy = floor_occupancy(plan.assignments)
        if any(
            occupancy.get(floor, 0) < min_per_floor for floor in floor_quota
        ):
            return LayoutPlan()
    return plan


def spread_limit(
    candidates: Sequence[AnchorCandidate],
    target_count: int,
) -> int:
    """How many targets may share one surface.

    One each is what a reviewer wants -- eight objects on a single worktop is a
    scene where nothing can be told apart -- but a scene with barely more
    anchors than targets cannot honour that, and losing the scene is worse than
    doubling up on one surface.
    """

    distinct = len({candidate.object_id for candidate in candidates})
    return 1 if distinct >= 2 * max(target_count, 1) else 2


def floor_occupancy(
    assignments: Mapping[int, AnchorCandidate],
) -> Dict[int, int]:
    """How many targets sit on each storey."""

    counts: Dict[int, int] = {}
    for anchor in assignments.values():
        counts[anchor.floor_index] = counts.get(anchor.floor_index, 0) + 1
    return counts


def balanced_floor_quota(
    floors: Sequence[int],
    total: int,
) -> Dict[int, int]:
    """Split ``total`` targets as evenly as possible over ``floors``."""

    ordered = sorted(set(floors))
    if not ordered:
        return {}
    base, extra = divmod(total, len(ordered))
    return {
        floor: base + (1 if position < extra else 0)
        for position, floor in enumerate(ordered)
    }


def plan_cross_anchor_layout(
    baseline: Mapping[int, AnchorCandidate],
    handles: Mapping[int, str],
    candidates: Sequence[AnchorCandidate],
    rng: random.Random,
    *,
    max_per_anchor: int = 2,
    min_move_distance: float = 1.0,
    avoid: Sequence[Mapping[int, AnchorCandidate]] = (),
    cross_floor_quota: int = 0,
) -> LayoutPlan:
    """Move every target onto a different but still sensible anchor.

    ``avoid`` holds anchor assignments from sibling layouts so the three
    cross-anchor layouts of a scene do not collapse onto the same answer.

    ``cross_floor_quota`` is how many targets should end up on a *different
    storey* than the static layout put them on.  In a multi-storey scene a
    handful of deliberate floor changes is what makes the benchmark test
    vertical re-localisation; moving everything upstairs would instead just be
    a second scene.  The rest of the targets are pushed to stay on their own
    storey, so the count is exact and reviewable.
    """

    plan = LayoutPlan()
    used: Dict[str, int] = {}
    order = sorted(baseline, key=lambda sid: len(allowed_anchors(candidates, handles[sid])))

    movers = (
        select_cross_floor_movers(
            baseline,
            handles,
            candidates,
            rng,
            quota=cross_floor_quota,
            avoid=avoid,
        )
        if cross_floor_quota > 0
        else set()
    )
    if cross_floor_quota > 0 and not movers:
        return LayoutPlan()

    for semantic_id in order:
        origin = baseline[semantic_id]
        affordance = affordance_for(handles[semantic_id])
        choices = [
            candidate
            for candidate in allowed_anchors(candidates, handles[semantic_id])
            if candidate.object_id != origin.object_id
            and used.get(candidate.object_id, 0) < max_per_anchor
        ]
        if semantic_id in movers:
            off_floor = [
                candidate
                for candidate in choices
                if candidate.floor_index != origin.floor_index
            ]
            # ``movers`` was chosen from anchors that were free at selection
            # time; if this scene's earlier assignments have since consumed
            # them all, the layout is not the one we promised.
            if not off_floor:
                return LayoutPlan()
            choices = off_floor
        if not choices:
            return LayoutPlan()
        seen = {
            other[semantic_id].object_id
            for other in avoid
            if semantic_id in other
        }

        def rank(candidate: AnchorCandidate) -> float:
            score = candidate_score(candidate, affordance)
            # A relocation the mapper cannot distinguish from noise is useless.
            if candidate.horizontal_distance(origin) >= min_move_distance:
                score += 1.5
            if candidate.region_id != origin.region_id:
                score += 1.0
            if candidate.object_id in seen:
                score -= 2.5
            score -= 4.0 * used.get(candidate.object_id, 0)
            if (
                semantic_id not in movers
                and candidate.floor_index != origin.floor_index
            ):
                # Keep the non-movers downstairs so the floor changes stay a
                # deliberate, countable signal.  This has to outweigh the
                # anchor-reuse penalty or crowding pushes targets upstairs.
                score -= 8.0
            return score + rng.random() * 0.25

        best = max(choices, key=rank)
        plan.assignments[semantic_id] = best
        used[best.object_id] = used.get(best.object_id, 0) + 1

    return plan


def select_cross_floor_movers(
    baseline: Mapping[int, AnchorCandidate],
    handles: Mapping[int, str],
    candidates: Sequence[AnchorCandidate],
    rng: random.Random,
    *,
    quota: int,
    avoid: Sequence[Mapping[int, AnchorCandidate]] = (),
) -> Set[int]:
    """Choose which targets change storey, best semantic fit first.

    A target is only eligible if it has an affordable anchor on another floor:
    a soup can with nothing but a bathroom upstairs stays where it is.  Targets
    that already crossed in a sibling layout are demoted so the three
    cross-anchor layouts of a scene do not repeat the same floor change.
    """

    already = [
        semantic_id
        for other in avoid
        for semantic_id, anchor in other.items()
        if semantic_id in baseline
        and anchor.floor_index != baseline[semantic_id].floor_index
    ]
    repeats = {semantic_id: already.count(semantic_id) for semantic_id in already}

    ranked: List[Tuple[float, int]] = []
    for semantic_id, origin in baseline.items():
        affordance = affordance_for(handles[semantic_id])
        off_floor = [
            candidate
            for candidate in allowed_anchors(candidates, handles[semantic_id])
            if candidate.floor_index != origin.floor_index
        ]
        if not off_floor:
            continue
        best = max(candidate_score(c, affordance) for c in off_floor)
        ranked.append(
            (best - 1.5 * repeats.get(semantic_id, 0) + rng.random() * 0.5, semantic_id)
        )

    ranked.sort(reverse=True)
    return {semantic_id for _, semantic_id in ranked[:quota]}


def cross_floor_moves(
    baseline: Mapping[int, AnchorCandidate],
    assignments: Mapping[int, AnchorCandidate],
) -> List[int]:
    """Semantic IDs whose storey differs from the static layout."""

    return sorted(
        semantic_id
        for semantic_id, anchor in assignments.items()
        if semantic_id in baseline
        and anchor.floor_index != baseline[semantic_id].floor_index
    )


def describe_plan(
    plan: LayoutPlan,
    handles: Mapping[int, str],
) -> List[str]:
    """Human-readable placement lines for review output."""

    lines = []
    for semantic_id in sorted(plan.assignments):
        anchor = plan.assignments[semantic_id]
        lines.append(
            f"{handles.get(semantic_id, semantic_id)} -> "
            f"{anchor.object_id} ({anchor.category}, {anchor.room})"
        )
    return lines
