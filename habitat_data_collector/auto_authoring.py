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
    "025_mug": TargetAffordance(
        "025_mug",
        anchor_kinds=("counter", "island", "dining_table", "table",
                      "coffee_table", "desk", "nightstand", "sideboard",
                      "shelf", "cabinet", "tv_stand"),
        rooms=_FOOD_ROOMS + ("office", "bedroom"),
        preferred_rooms=("kitchen", "office", "living_room"),
    ),
    "029_plate": TargetAffordance(
        "029_plate",
        anchor_kinds=_FOOD_PREP_SURFACES,
        rooms=_FOOD_ROOMS,
        preferred_rooms=("kitchen", "dining_room"),
    ),
    "037_scissors": TargetAffordance(
        "037_scissors",
        anchor_kinds=("desk", "table", "counter", "island", "coffee_table",
                      "sideboard", "shelf", "cabinet", "chest", "nightstand",
                      "tv_stand"),
        rooms=("kitchen", "dining_room", "living_room", "office", "bedroom"),
        preferred_rooms=("office", "kitchen"),
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
) -> LayoutPlan:
    """Assign as many targets as possible to semantically valid anchors.

    Targets with the fewest valid anchors are assigned first so that a scarce
    anchor is not consumed by a target that had alternatives.
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
        affordance = affordance_for(target.handle)
        best = max(
            choices,
            key=lambda candidate: (
                candidate_score(candidate, affordance)
                # Spread objects over anchors and rooms before doubling up.
                - 1.5 * used.get(candidate.object_id, 0)
                - 0.4 * used_regions.get(candidate.region_id, 0)
                + rng.random() * 0.25
            ),
        )
        plan.assignments[target.semantic_id] = best
        used[best.object_id] = used.get(best.object_id, 0) + 1
        used_regions[best.region_id] = used_regions.get(best.region_id, 0) + 1

    if len(plan.assignments) < minimum_placed:
        return LayoutPlan()
    return plan


def plan_cross_anchor_layout(
    baseline: Mapping[int, AnchorCandidate],
    handles: Mapping[int, str],
    candidates: Sequence[AnchorCandidate],
    rng: random.Random,
    *,
    max_per_anchor: int = 2,
    min_move_distance: float = 1.0,
    avoid: Sequence[Mapping[int, AnchorCandidate]] = (),
) -> LayoutPlan:
    """Move every target onto a different but still sensible anchor.

    ``avoid`` holds anchor assignments from sibling layouts so the three
    cross-anchor layouts of a scene do not collapse onto the same answer.
    """

    plan = LayoutPlan()
    used: Dict[str, int] = {}
    order = sorted(baseline, key=lambda sid: len(allowed_anchors(candidates, handles[sid])))

    for semantic_id in order:
        origin = baseline[semantic_id]
        affordance = affordance_for(handles[semantic_id])
        choices = [
            candidate
            for candidate in allowed_anchors(candidates, handles[semantic_id])
            if candidate.object_id != origin.object_id
            and used.get(candidate.object_id, 0) < max_per_anchor
        ]
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
            score -= 1.5 * used.get(candidate.object_id, 0)
            return score + rng.random() * 0.25

        best = max(choices, key=rank)
        plan.assignments[semantic_id] = best
        used[best.object_id] = used.get(best.object_id, 0) + 1

    return plan


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
