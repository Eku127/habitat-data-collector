"""Metrics and markdown for reviewing an authored DualMap dataset.

Reading a dataset today means opening seven JSON files and fourteen renders per
scene in Habitat.  This module turns the same files into numbers a reviewer can
scan: how far each object actually moved, whether it changed storey, and how
well its new surface matches what the object is for.

Pure data, like :mod:`habitat_data_collector.auto_authoring`.  Nothing here
imports Habitat or reads an image, so the report can be regenerated in seconds
and unit tested without a simulator.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from habitat_data_collector.authoring import (
    DYNAMIC_LAYOUT_TYPES,
    slot_name,
)
from habitat_data_collector.auto_authoring import (
    ROOM_UNKNOWN,
    AnchorCandidate,
    affordance_for,
    candidate_score,
)

#: The largest value :func:`candidate_score` can return: 1.0 base, +2.0 for a
#: preferred room, +0.5 for a top-three anchor kind, +0.5 for a mid-sized
#: surface.  Dividing by it turns the planner's ranking into a 0-1 score that
#: means the same thing in every scene.
MAX_CANDIDATE_SCORE = 4.0

#: Order the layout kinds are reviewed in: the baseline, then what changed.
LAYOUT_ORDER: Tuple[str, ...] = ("static",) + DYNAMIC_LAYOUT_TYPES


def parse_slot(name: str) -> Tuple[str, Optional[int]]:
    """``"in_anchor_02"`` -> ``("in_anchor", 2)``."""

    if name == "static":
        return "static", None
    layout_type, _, index = name.rpartition("_")
    return layout_type, int(index)


def sort_key(name: str) -> Tuple[int, int]:
    layout_type, index = parse_slot(name)
    order = (
        LAYOUT_ORDER.index(layout_type)
        if layout_type in LAYOUT_ORDER
        else len(LAYOUT_ORDER)
    )
    return order, index or 0


# ---------------------------------------------------------------------------
# Semantic correspondence
# ---------------------------------------------------------------------------


def anchor_from_mapping(anchor: Mapping[str, Any]) -> AnchorCandidate:
    """Rebuild a scoreable anchor from a saved ``anchor`` block.

    Only the fields the score needs are reconstructed; the centre and size are
    synthesised from the saved footprint so :attr:`AnchorCandidate.footprint`
    reports what the planner actually saw.
    """

    footprint = float(anchor.get("footprint", 0.0) or 0.0)
    side = math.sqrt(footprint) if footprint > 0 else 0.0
    top_y = float(anchor.get("top_y", 0.0) or 0.0)
    return AnchorCandidate(
        object_id=str(anchor.get("object_id", "?")),
        category=str(anchor.get("category", "")),
        kind=str(anchor.get("kind", "")),
        center=(0.0, top_y, 0.0),
        size=(side, 0.0, side),
        region_id=str(anchor.get("region_id", "?")),
        room=str(anchor.get("room", ROOM_UNKNOWN)),
        floor_index=int(anchor.get("floor_index", 0)),
        floor_height=float(anchor.get("floor_height", 0.0) or 0.0),
    )


def semantic_correspondence(handle: str, anchor: Mapping[str, Any]) -> float:
    """How well ``handle`` suits the surface it was placed on, in 0.0-1.0.

    This is :func:`candidate_score` -- the same ranking that chose the anchor in
    the first place -- rescaled, so the review never disagrees with the
    generator about what a good placement is.  1.0 is a target on its preferred
    room, on one of its top-three surface kinds, on a surface of a sensible
    size; 0.25 is a placement that only just cleared the affordance gate.
    """

    candidate = anchor_from_mapping(anchor)
    score = candidate_score(candidate, affordance_for(handle))
    return round(min(score, MAX_CANDIDATE_SCORE) / MAX_CANDIDATE_SCORE, 3)


# ---------------------------------------------------------------------------
# Per-object and per-layout metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Placement:
    """One target in one layout, and how it differs from the static layout."""

    semantic_id: int
    handle: str
    translation: Tuple[float, float, float]
    anchor_id: str
    category: str
    kind: str
    room: str
    floor: int
    correspondence: float

    # Filled in for dynamic layouts only.
    from_anchor_id: Optional[str] = None
    from_category: Optional[str] = None
    from_room: Optional[str] = None
    from_floor: Optional[int] = None
    from_correspondence: Optional[float] = None
    distance: Optional[float] = None
    horizontal: Optional[float] = None
    dz: Optional[float] = None

    @property
    def changed_floor(self) -> bool:
        return self.from_floor is not None and self.from_floor != self.floor

    @property
    def changed_anchor(self) -> bool:
        return (
            self.from_anchor_id is not None
            and self.from_anchor_id != self.anchor_id
        )


@dataclass
class LayoutReport:
    """One of the seven layout slots of a scene."""

    layout_type: str
    layout_index: Optional[int]
    placements: List[Placement] = field(default_factory=list)

    @property
    def name(self) -> str:
        return slot_name(self.layout_type, self.layout_index)

    @property
    def is_dynamic(self) -> bool:
        return self.layout_type != "static"

    @property
    def floor_changes(self) -> List[Placement]:
        return [p for p in self.placements if p.changed_floor]

    @property
    def floors_used(self) -> List[int]:
        return sorted({p.floor for p in self.placements})

    def _distances(self) -> List[float]:
        return [p.distance for p in self.placements if p.distance is not None]

    @property
    def mean_move(self) -> Optional[float]:
        values = self._distances()
        return statistics.fmean(values) if values else None

    @property
    def median_move(self) -> Optional[float]:
        values = self._distances()
        return statistics.median(values) if values else None

    @property
    def max_move(self) -> Optional[float]:
        values = self._distances()
        return max(values) if values else None

    @property
    def mean_abs_dz(self) -> Optional[float]:
        values = [abs(p.dz) for p in self.placements if p.dz is not None]
        return statistics.fmean(values) if values else None

    @property
    def mean_correspondence(self) -> float:
        return statistics.fmean(p.correspondence for p in self.placements)

    @property
    def min_correspondence(self) -> float:
        return min(p.correspondence for p in self.placements)

    @property
    def distinct_anchors(self) -> int:
        return len({p.anchor_id for p in self.placements})

    @property
    def rooms(self) -> List[str]:
        return sorted({p.room for p in self.placements})


@dataclass
class SceneReport:
    """Every layout of one scene, plus the storeys it was authored over."""

    scene: str
    floors: List[Mapping[str, Any]] = field(default_factory=list)
    multifloor: bool = False
    #: RNG seed this scene was authored with.  Recorded per scene because a
    #: scene whose physics did not settle is re-authored with a different one.
    seed: Optional[int] = None
    layouts: List[LayoutReport] = field(default_factory=list)

    def layout(self, name: str) -> Optional[LayoutReport]:
        for report in self.layouts:
            if report.name == name:
                return report
        return None

    @property
    def static(self) -> Optional[LayoutReport]:
        return self.layout("static")

    @property
    def cross_anchor(self) -> List[LayoutReport]:
        return [r for r in self.layouts if r.layout_type == "cross_anchor"]

    @property
    def in_anchor(self) -> List[LayoutReport]:
        return [r for r in self.layouts if r.layout_type == "in_anchor"]

    @property
    def placed_targets(self) -> int:
        static = self.static
        return len(static.placements) if static else 0

    @property
    def floors_used(self) -> List[int]:
        return sorted({p.floor for r in self.layouts for p in r.placements})

    @property
    def floor_height(self) -> Dict[int, float]:
        return {int(f["index"]): float(f["height"]) for f in self.floors}

    @property
    def cross_floor_moves(self) -> int:
        return sum(len(r.floor_changes) for r in self.cross_anchor)

    @property
    def mean_correspondence(self) -> float:
        return statistics.fmean(
            p.correspondence for r in self.layouts for p in r.placements
        )

    @property
    def mean_cross_anchor_move(self) -> Optional[float]:
        values = [
            p.distance
            for r in self.cross_anchor
            for p in r.placements
            if p.distance is not None
        ]
        return statistics.fmean(values) if values else None


def build_placements(
    data: Mapping[str, Any],
    baseline: Optional[Mapping[str, Any]] = None,
) -> List[Placement]:
    """Turn one layout config into per-object records, diffed against static."""

    handles = {int(k): v for k, v in data.get("id_handle_mapping", {}).items()}
    before: Dict[int, Mapping[str, Any]] = {}
    if baseline is not None:
        before = {int(o["semantic_id"]): o for o in baseline.get("objects", [])}

    placements: List[Placement] = []
    for obj in data.get("objects", []):
        semantic_id = int(obj["semantic_id"])
        handle = handles.get(semantic_id, str(semantic_id))
        anchor = obj.get("anchor", {})
        translation = tuple(float(v) for v in obj["translation"])
        common = dict(
            semantic_id=semantic_id,
            handle=handle,
            translation=translation,
            anchor_id=str(anchor.get("object_id", "?")),
            category=str(anchor.get("category", "")),
            kind=str(anchor.get("kind", "")),
            room=str(anchor.get("room", ROOM_UNKNOWN)),
            floor=int(anchor.get("floor_index", 0)),
            correspondence=semantic_correspondence(handle, anchor),
        )

        origin = before.get(semantic_id)
        if origin is None:
            placements.append(Placement(**common))
            continue

        start = tuple(float(v) for v in origin["translation"])
        origin_anchor = origin.get("anchor", {})
        placements.append(
            Placement(
                **common,
                from_anchor_id=str(origin_anchor.get("object_id", "?")),
                from_category=str(origin_anchor.get("category", "")),
                from_room=str(origin_anchor.get("room", ROOM_UNKNOWN)),
                from_floor=int(origin_anchor.get("floor_index", 0)),
                from_correspondence=semantic_correspondence(handle, origin_anchor),
                distance=math.dist(translation, start),
                horizontal=math.dist(
                    (translation[0], translation[2]), (start[0], start[2])
                ),
                dz=translation[1] - start[1],
            )
        )

    placements.sort(key=lambda p: p.handle)
    return placements


def build_scene_report(
    scene: str,
    configs: Mapping[str, Mapping[str, Any]],
) -> SceneReport:
    """Assemble one scene from its seven parsed layout configs.

    ``configs`` is keyed by slot name (``"static"``, ``"in_anchor_01"``, ...)
    and whatever it holds is what gets reported: how many dynamic layouts a
    scene carries is a property of the dataset, not of this code.
    """

    static = configs.get("static")
    authoring = (static or {}).get("authoring", {})
    report = SceneReport(
        scene=scene,
        floors=list(authoring.get("floors", [])),
        multifloor=bool(authoring.get("multifloor", False)),
        seed=authoring.get("seed"),
    )
    for name in sorted(configs, key=sort_key):
        layout_type, layout_index = parse_slot(name)
        data = configs[name]
        report.layouts.append(
            LayoutReport(
                layout_type=layout_type,
                layout_index=layout_index,
                placements=build_placements(
                    data, baseline=None if layout_type == "static" else static
                ),
            )
        )
    return report


# ---------------------------------------------------------------------------
# Dataset-level aggregates
# ---------------------------------------------------------------------------


@dataclass
class DatasetSummary:
    scenes: List[SceneReport]

    @property
    def multifloor_scenes(self) -> List[SceneReport]:
        return [scene for scene in self.scenes if scene.multifloor]

    @property
    def layout_count(self) -> int:
        return sum(len(scene.layouts) for scene in self.scenes)

    @property
    def placement_count(self) -> int:
        return sum(
            len(layout.placements)
            for scene in self.scenes
            for layout in scene.layouts
        )

    @property
    def mean_correspondence(self) -> float:
        values = [
            p.correspondence
            for scene in self.scenes
            for layout in scene.layouts
            for p in layout.placements
        ]
        return statistics.fmean(values) if values else 0.0

    @property
    def mean_cross_anchor_move(self) -> Optional[float]:
        values = [
            p.distance
            for scene in self.scenes
            for layout in scene.cross_anchor
            for p in layout.placements
            if p.distance is not None
        ]
        return statistics.fmean(values) if values else None

    @property
    def mean_in_anchor_move(self) -> Optional[float]:
        values = [
            p.distance
            for scene in self.scenes
            for layout in scene.in_anchor
            for p in layout.placements
            if p.distance is not None
        ]
        return statistics.fmean(values) if values else None

    @property
    def cross_floor_moves(self) -> int:
        return sum(scene.cross_floor_moves for scene in self.scenes)
