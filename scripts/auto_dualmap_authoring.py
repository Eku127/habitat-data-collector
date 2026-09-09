#!/usr/bin/env python3
"""Generate DualMap HM3D scene layouts without the interactive authoring GUI.

The interactive mode in ``documents/dualmap_authoring/README.md`` needs 7 saved
slots per scene (1 static + 3 in-anchor + 3 cross-anchor), which is 105 manual
sessions for a 15-scene dataset.  This script performs the same placements
headlessly and writes byte-compatible configurations, with two differences that
matter for benchmark quality:

* anchors are filtered by :mod:`habitat_data_collector.auto_authoring`, so a
  soup can is never placed on a bed and a plate is never placed in a bathroom;
* cross-anchor relocations must land on another *semantically valid* support,
  which is what the released DualMap data gets wrong.

Sub-commands
------------
``scan``   rank installed HM3D scenes by how many usable anchors they contain.
``build``  author the full 7-file layout set for one or more scenes.

Both need a GL context.  On a headless host run them under ``xvfb-run``::

    xvfb-run -a python scripts/auto_dualmap_authoring.py scan --split val
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("MAGNUM_LOG", "quiet")
os.environ.setdefault("HABITAT_SIM_LOG", "quiet")

import numpy as np  # noqa: E402
from omegaconf import OmegaConf  # noqa: E402

import habitat_sim  # noqa: E402
import magnum as mn  # noqa: E402

from habitat_data_collector.authoring import (  # noqa: E402
    AnchorInfo,
    layout_output_path,
    targets_from_config,
    validate_saved_config,
)
from habitat_data_collector.auto_authoring import (  # noqa: E402
    LayoutPlan,
    ROOM_UNKNOWN,
    AnchorCandidate,
    FloorLevel,
    anchor_is_usable,
    anchor_kind,
    allowed_anchors,
    balanced_floor_quota,
    cluster_floor_levels,
    cross_floor_moves,
    floor_index_for,
    floor_occupancy,
    floors_by_anchor_count,
    infer_room_type,
    normalize_category,
    spread_limit,
    plan_cross_anchor_layout,
    plan_static_layout,
    restrict_to_floors,
)
from habitat_data_collector.utils.config_factory import ConfigFactory  # noqa: E402

import habitat.sims.habitat_simulator.sim_utilities as sutils  # noqa: E402


#: Human-readable names for the three layout kinds, shared with the renderer.
LAYOUT_LABELS = {
    "static": "STATIC",
    "in_anchor": "IN-ANCHOR (same surface)",
    "cross_anchor": "CROSS-ANCHOR (different surface)",
}

#: How many anchors one target may try before the layout gives up.
MAX_ANCHOR_FALLBACKS = 5

DEFAULT_CONFIG = REPO_ROOT / "config" / "habitat_data_collector.yaml"
SCENE_ROOT = REPO_ROOT / "data" / "scene_datasets" / "hm3d"
DATASET_CONFIG = SCENE_ROOT / "hm3d_annotated_basis.scene_dataset_config.json"


# ---------------------------------------------------------------------------
# Scene discovery
# ---------------------------------------------------------------------------


def scene_glb(split: str, folder: str) -> Path:
    return SCENE_ROOT / split / folder / f"{folder.split('-', 1)[1]}.basis.glb"


def resolve_scene(token: str, split: str) -> Optional[str]:
    """Accept ``00829``, ``00829-QaLdnwvtxbs``, or ``QaLdnwvtxbs``."""

    split_dir = SCENE_ROOT / split
    if not split_dir.is_dir():
        return None
    folders = sorted(path.name for path in split_dir.iterdir() if path.is_dir())
    if token in folders:
        return token
    for folder in folders:
        prefix, _, suffix = folder.partition("-")
        if token in (prefix, suffix):
            return folder
    return None


def list_scenes(split: str) -> List[str]:
    split_dir = SCENE_ROOT / split
    if not split_dir.is_dir():
        return []
    return sorted(path.name for path in split_dir.iterdir() if path.is_dir())


# ---------------------------------------------------------------------------
# Simulator setup
# ---------------------------------------------------------------------------


def load_config(config_path: Path, scene_path: Path, output_root: Path):
    cfg = OmegaConf.load(str(config_path))
    cfg.load_from_config = False
    cfg.scene_path = str(scene_path)
    cfg.scene_dataset_config = str(DATASET_CONFIG)
    cfg.authoring.enabled = True
    cfg.authoring.output_root = str(output_root)
    cfg.show_placable_categories = False
    return cfg


def open_simulator(cfg, *, small_sensors: bool = True):
    """Open a scene.  The semantic mesh only yields AABBs when sensors exist."""

    if small_sensors:
        cfg = OmegaConf.create(OmegaConf.to_container(cfg, resolve=True))
        cfg.data_cfg.resolution.w = 256
        cfg.data_cfg.resolution.h = 192
    return habitat_sim.Simulator(ConfigFactory.create_simulator_config(cfg))


def register_targets(sim, objects_path: str, targets) -> Dict[int, str]:
    """Register the YCB templates under stable handles with authoring IDs."""

    otm = sim.get_object_template_manager()
    otm.load_configs(str(objects_path))
    available = {
        os.path.basename(str(handle)).split(".")[0]: str(handle)
        for handle in otm.get_file_template_handles()
    }
    missing = [target.handle for target in targets if target.handle not in available]
    if missing:
        raise RuntimeError(
            "Missing YCB object configs: " + ", ".join(missing)
        )
    id_handle: Dict[int, str] = {}
    for target in targets:
        template = otm.get_template_by_handle(available[target.handle])
        template.semantic_id = target.semantic_id
        otm.register_template(template, target.handle)
        id_handle[target.semantic_id] = target.handle
    return id_handle


# ---------------------------------------------------------------------------
# Anchor extraction
# ---------------------------------------------------------------------------


def region_room_types(scene) -> Dict[str, str]:
    rooms: Dict[str, str] = {}
    for region in scene.regions:
        categories = [
            obj.category.name()
            for obj in region.objects
            if obj is not None and obj.category is not None
        ]
        rooms[str(region.id)] = infer_room_type(categories)
    return rooms


def region_floor_heights(scene) -> Dict[str, float]:
    floors: Dict[str, float] = {}
    for region in scene.regions:
        height = float(getattr(region, "floor_height", float("nan")))
        if math.isfinite(height):
            floors[str(region.id)] = height
    return floors


def eligible_cross_floor_targets(
    baseline: Mapping[int, AnchorCandidate],
    handles: Mapping[int, str],
    candidates: Sequence[AnchorCandidate],
) -> int:
    """How many placed targets could legally move to another storey."""

    total = 0
    for semantic_id, origin in baseline.items():
        options = allowed_anchors(candidates, handles[semantic_id])
        if any(c.floor_index != origin.floor_index for c in options):
            total += 1
    return total


def multifloor_is_viable(
    candidates: Sequence[AnchorCandidate],
    targets: Sequence["object"],
    floors: Sequence[int],
    *,
    min_targets_per_floor: int = 2,
) -> bool:
    """Can a static layout really put objects on every one of ``floors``?

    Counting anchors is not enough: a storey full of bathroom cabinets is
    useless if no YCB target is allowed to sit there.  This counts distinct
    *targets* with at least one affordable anchor per storey.
    """

    for floor in floors:
        on_floor = [c for c in candidates if c.floor_index == floor]
        placeable = sum(
            1
            for target in targets
            if allowed_anchors(on_floor, target.handle)
        )
        if placeable < min_targets_per_floor:
            return False
    return True


def detect_floors(sim) -> List[FloorLevel]:
    """Read the scene's storeys off the navmesh.

    The navigable vertices of a house cluster tightly at each storey height
    with only stairs between them, which is a far more reliable storey signal
    than the semantic regions: ``region.floor_height`` is missing or wrong in a
    good number of HM3D scenes.
    """

    try:
        vertices = np.asarray(sim.pathfinder.build_navmesh_vertices())
        indices = np.asarray(sim.pathfinder.build_navmesh_vertex_indices())
    except Exception:  # pragma: no cover - navmesh not loaded
        vertices, indices = np.empty((0, 3)), np.empty(0, dtype=int)
    if vertices.size == 0:
        base = float(sim.pathfinder.get_bounds()[0][1])
        return [FloorLevel(index=0, height=base, y_min=base, y_max=base, share=1.0)]

    if indices.size >= 3:
        # Weight each height by the navigable area at it.  A staircase is
        # navigable at every height between two storeys but covers almost no
        # area, which is exactly what separates the storeys.
        triangles = vertices[indices[: (indices.size // 3) * 3].reshape(-1, 3)]
        edge_a = triangles[:, 1] - triangles[:, 0]
        edge_b = triangles[:, 2] - triangles[:, 0]
        areas = 0.5 * np.linalg.norm(np.cross(edge_a, edge_b), axis=1)
        heights = triangles[:, :, 1].mean(axis=1)
        return cluster_floor_levels(heights.tolist(), areas.tolist())
    return cluster_floor_levels(vertices[:, 1].tolist())


def navigable_floor(sim, center: Sequence[float], max_offset: float = 2.0):
    """Nearest navigable point to a support, used for reachability and floor."""

    point = np.array([center[0], center[1], center[2]], dtype=np.float32)
    snapped = sim.pathfinder.snap_point(point)
    snapped = np.array(snapped, dtype=np.float32)
    if not np.all(np.isfinite(snapped)):
        return None, False
    horizontal = math.dist((center[0], center[2]), (float(snapped[0]), float(snapped[2])))
    return float(snapped[1]), horizontal <= max_offset


def collect_anchor_candidates(
    sim,
    *,
    verbose: bool = False,
    levels: Optional[Sequence[FloorLevel]] = None,
) -> List[AnchorCandidate]:
    scene = sim.semantic_scene
    rooms = region_room_types(scene)
    floors = region_floor_heights(scene)
    levels = list(levels) if levels is not None else detect_floors(sim)
    candidates: List[AnchorCandidate] = []

    for obj in scene.objects:
        if obj is None or obj.category is None:
            continue
        category = obj.category.name()
        kind = anchor_kind(category)
        if kind is None:
            continue
        size = [float(value) for value in obj.aabb.sizes]
        center = [float(value) for value in obj.aabb.center]
        if all(value == 0.0 for value in size):
            continue
        region_id = str(getattr(obj.region, "id", "?")) if obj.region else "?"
        room = rooms.get(region_id, ROOM_UNKNOWN)
        floor, reachable = navigable_floor(sim, center)
        if floor is None:
            floor = floors.get(region_id)
        if floor is None:
            floor = float(sim.pathfinder.get_bounds()[0][1])
        candidate = AnchorCandidate(
            object_id=str(obj.id),
            category=str(category),
            kind=kind,
            center=(center[0], center[1], center[2]),
            size=(abs(size[0]), abs(size[1]), abs(size[2])),
            region_id=region_id,
            room=room,
            navigable=bool(reachable),
            floor_index=floor_index_for(levels, float(floor)),
            floor_height=float(floor),
        )
        if anchor_is_usable(candidate, floor_height=float(floor)):
            candidates.append(candidate)
        elif verbose:
            print(f"    reject {candidate.object_id} ({kind}, {room})")
    return candidates


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------


def object_base_y(rigid_object) -> float:
    aabb = rigid_object.root_scene_node.compute_cumulative_bb()
    return float(aabb.min[1]) + float(rigid_object.translation[1])


#: Semantic categories that are structure rather than clutter.  A placement is
#: allowed to be near a wall; it is not allowed to be inside a table lamp.
_STRUCTURE_KEYWORDS: Tuple[str, ...] = (
    "wall", "floor", "ceiling", "door", "doorway", "window", "stairs",
    "staircase", "railing", "beam", "column", "unknown", "remove", "void",
)


#: Why candidate poses were thrown away, for ``--verbose``.  Placement quality
#: is mostly a question of which gate is too tight, and that is invisible
#: without counting.
REJECTIONS: Counter = Counter()


def is_upright(rigid_object, max_tilt_degrees: float = 28.0) -> bool:
    """Has the object stayed the way up it was placed?

    Every YCB target here is authored upright -- the templates are upright at
    identity and the drop only randomises yaw -- but physics can still tip a
    can onto its side or flip a bowl while it settles.  A soup can lying down
    is a different object to a perception system, so reject the pose rather
    than ship it.
    """

    up = rigid_object.rotation.transform_vector(mn.Vector3(0.0, 1.0, 0.0))
    cosine = max(-1.0, min(1.0, float(up[1]) / max(float(up.length()), 1e-6)))
    return math.degrees(math.acos(cosine)) <= max_tilt_degrees


def _overlaps_anchor(center, size, anchor: AnchorCandidate) -> bool:
    """Is this annotation just another label on the same piece of furniture?

    HM3D frequently annotates a worktop, the cabinet under it and the run of
    units around it as separate objects with heavily overlapping boxes.  Those
    are not obstacles to place around -- treating them as such rejects every
    pose on the surface.
    """

    inside = all(
        abs(center[axis] - anchor.center[axis]) <= size[axis] / 2.0
        for axis in (0, 2)
    )
    if inside:
        return True
    overlap = 1.0
    for axis in (0, 2):
        low = max(center[axis] - size[axis] / 2.0,
                  anchor.center[axis] - anchor.size[axis] / 2.0)
        high = min(center[axis] + size[axis] / 2.0,
                   anchor.center[axis] + anchor.size[axis] / 2.0)
        overlap *= max(0.0, high - low)
    return overlap > 0.5 * max(anchor.footprint, 1e-6)


def obstacles_for(
    obstacles: Sequence[Tuple],
    anchor: AnchorCandidate,
) -> List[Tuple]:
    """The obstacles that matter for one anchor."""

    return [
        (center, size)
        for center, size in obstacles
        if not _overlaps_anchor(center, size, anchor)
    ]


def semantic_obstacles(sim, anchor_ids: Sequence[str] = ()) -> List[Tuple]:
    """AABBs of scene objects a target must not be buried in or behind.

    HM3D annotates the lamp, the sink, the plant and the pile of clutter on a
    worktop as their own objects, so the geometry the review kept complaining
    about is already labelled -- it was simply never consulted.  The anchor
    itself and the building structure are excluded.
    """

    blocked = set(anchor_ids)
    obstacles = []
    for obj in sim.semantic_scene.objects:
        if obj is None or obj.category is None:
            continue
        if str(obj.id) in blocked:
            continue
        category = normalize_category(obj.category.name())
        if any(word in category for word in _STRUCTURE_KEYWORDS):
            continue
        size = [abs(float(v)) for v in obj.aabb.sizes]
        if all(value == 0.0 for value in size):
            continue
        center = [float(v) for v in obj.aabb.center]
        obstacles.append((center, size))
    return obstacles


def is_clear_of_obstacles(
    rigid_object,
    obstacles: Sequence[Tuple],
    *,
    margin: float = 0.03,
) -> bool:
    """Reject a pose that intersects another annotated object.

    This is what stops a target landing in a sink, on a stove, inside a pile of
    worktop clutter, or hard against a table lamp -- the placements the review
    flagged as "too close to" or "blocked by" something.
    """

    aabb = rigid_object.root_scene_node.compute_cumulative_bb()
    translation = rigid_object.translation
    low = [float(aabb.min[i]) + float(translation[i]) - margin for i in range(3)]
    high = [float(aabb.max[i]) + float(translation[i]) + margin for i in range(3)]
    for center, size in obstacles:
        if all(
            low[axis] < center[axis] + size[axis] / 2.0
            and high[axis] > center[axis] - size[axis] / 2.0
            for axis in range(3)
        ):
            return False
    return True


def is_visible(
    sim,
    rigid_object,
    *,
    eye_height: float = 1.4,
    radii: Sequence[float] = (1.0, 1.5, 2.1, 2.8),
    azimuth_step: int = 30,
    same_floor_tolerance: float = 1.2,
) -> bool:
    """Can an agent standing on the navmesh actually see this object?

    An object recessed into a shelf, tucked behind a cabinet door, or wedged
    against a wall passes every geometric test and is still useless: the
    recording pass never observes it, so it can never be queried.  The check is
    the renderer's: cast a ray from a navigable viewpoint and require the first
    thing it hits to be this object.

    The viewpoints are a fixed ring sweep rather than random navigable points,
    so the answer is the same every time it is asked.  A sampler would let a
    placement pass at authoring time and fail the same test during
    verification, which is a coin toss dressed up as a check.
    """

    target = rigid_object.translation
    centre = np.array(
        [float(target[0]), float(target[1]), float(target[2])], dtype=np.float64
    )
    object_id = int(rigid_object.object_id)

    for radius in radii:
        for degrees in range(0, 360, azimuth_step):
            angle = math.radians(degrees)
            probe = np.array(
                [
                    centre[0] + radius * math.cos(angle),
                    centre[1],
                    centre[2] + radius * math.sin(angle),
                ],
                dtype=np.float32,
            )
            point = np.asarray(sim.pathfinder.snap_point(probe), dtype=np.float64)
            if not np.all(np.isfinite(point)):
                continue
            # A viewpoint on the storey below is not a viewpoint on this one.
            if abs(point[1] - centre[1]) > same_floor_tolerance + eye_height:
                continue
            eye = np.array([point[0], point[1] + eye_height, point[2]])
            direction = centre - eye
            distance = float(np.linalg.norm(direction))
            if distance < 1e-3:
                continue
            ray = habitat_sim.geo.Ray(
                mn.Vector3(*eye), mn.Vector3(*(direction / distance))
            )
            hits = sim.cast_ray(ray, max_distance=distance * 1.3).hits
            if hits and int(hits[0].object_id) == object_id:
                return True
    return False


def place_on_anchor(
    sim,
    handle: str,
    anchor: AnchorCandidate,
    rng: random.Random,
    *,
    placed: Sequence,
    attempts: int = 40,
    shrink: float = 0.62,
    surface_tolerance: float = 0.14,
    #: Centre-to-centre.  A cracker box is 0.21 m across and a toy airplane
    #: 0.26 m, so anything under a third of a metre reads as one pile.
    min_separation: float = 0.35,
    min_shift_from: Optional[Sequence[float]] = None,
    min_shift: float = 0.10,
    obstacles: Sequence[Tuple] = (),
    require_visible: bool = True,
):
    """Drop one target onto ``anchor`` and verify it really landed on it.

    Landing on the right surface is necessary but not sufficient.  A pose is
    only kept if the object is also still upright, clear of the lamps, sinks
    and clutter HM3D annotates around it, and actually visible from somewhere
    an agent can stand -- the three things a human reviewer notices
    immediately and no geometric test caught.
    """

    rom = sim.get_rigid_object_manager()
    set_motion(placed, habitat_sim.physics.MotionType.STATIC)
    approach = approach_direction(sim, anchor)
    nearby = obstacles_for(obstacles, anchor)
    for attempt in range(attempts):
        rigid_object = rom.add_object_by_template_handle(handle)
        offset_x, offset_z = sample_offset(anchor, approach, rng, shrink=shrink)
        x = anchor.center[0] + offset_x
        z = anchor.center[2] + offset_z
        y = anchor.top_y + 0.18
        rigid_object.translation = mn.Vector3(x, y, z)
        rigid_object.rotation = mn.Quaternion.rotation(
            mn.Rad(rng.uniform(0.0, 2.0 * math.pi)), mn.Vector3(0.0, 1.0, 0.0)
        )

        snapped = sutils.snap_down(sim, rigid_object, [habitat_sim.stage_id])
        reason = None
        if not snapped:
            reason = "snap_down"
        elif not _accept_placement(
            sim,
            rigid_object,
            anchor,
            placed=placed,
            surface_tolerance=surface_tolerance,
            min_separation=min_separation,
            min_shift_from=min_shift_from,
            min_shift=min_shift,
        ):
            reason = "off_anchor"
        # A pose that only holds until physics runs is not usable data: the
        # collector steps physics continuously while recording.
        elif not settle_object(sim, rigid_object, anchor):
            reason = "unsettled"
        elif not is_upright(rigid_object):
            reason = "tipped_over"
        elif not is_clear_of_obstacles(rigid_object, nearby):
            reason = "blocked_by_scene"
        elif require_visible and not is_visible(sim, rigid_object):
            reason = "not_visible"

        if reason is None:
            rigid_object.motion_type = habitat_sim.physics.MotionType.STATIC
            REJECTIONS["accepted"] += 1
            return rigid_object
        REJECTIONS[reason] += 1
        rom.remove_object_by_id(rigid_object.object_id)
    return None


def approach_direction(sim, anchor: AnchorCandidate) -> Optional[Tuple[float, float]]:
    """Unit XZ vector from the anchor centre towards where an agent stands.

    Objects the review called "too inside" were pushed to the back of a shelf
    or cabinet, away from the room.  Biasing towards the navigable side puts
    them where they can be seen and reached.
    """

    point = sim.pathfinder.snap_point(
        np.array(anchor.center, dtype=np.float32)
    )
    point = np.asarray(point, dtype=np.float32)
    if not np.all(np.isfinite(point)):
        return None
    dx = float(point[0]) - anchor.center[0]
    dz = float(point[2]) - anchor.center[2]
    length = math.hypot(dx, dz)
    if length < 1e-3:
        return None
    return dx / length, dz / length


def sample_offset(
    anchor: AnchorCandidate,
    approach: Optional[Tuple[float, float]],
    rng: random.Random,
    *,
    shrink: float,
    edge_margin: float = 0.06,
    front_bias: float = 0.25,
    bias_reach: float = 0.5,
) -> Tuple[float, float]:
    """Pick a spot on the anchor top, biased away from the back and the rim.

    ``edge_margin`` keeps the object off the lip -- the review found a mug
    perched on the edge of a desk next to a stairwell -- while ``front_bias``
    pulls it towards the side an agent approaches from.  The bias aims at
    ``bias_reach`` of the way out, not at the edge: aiming at the rim simply
    pushed objects off the surface and physics rejected the pose.
    """

    half_x = max(anchor.size[0] * shrink / 2.0 - edge_margin, 0.0)
    half_z = max(anchor.size[2] * shrink / 2.0 - edge_margin, 0.0)
    offset_x = (rng.random() * 2.0 - 1.0) * half_x
    offset_z = (rng.random() * 2.0 - 1.0) * half_z
    if approach is not None:
        # Blend towards the navigable side rather than snapping to it, so the
        # placements on one surface do not all end up in a line at the front.
        target_x = approach[0] * half_x * bias_reach
        target_z = approach[1] * half_z * bias_reach
        offset_x = offset_x * (1.0 - front_bias) + target_x * front_bias
        offset_z = offset_z * (1.0 - front_bias) + target_z * front_bias
    return offset_x, offset_z


def translation_of(rigid_object) -> Tuple[float, float, float]:
    return (
        float(rigid_object.translation[0]),
        float(rigid_object.translation[1]),
        float(rigid_object.translation[2]),
    )


def set_motion(rigid_objects: Sequence, motion_type) -> None:
    for rigid_object in rigid_objects:
        rigid_object.motion_type = motion_type


def step_physics(sim, steps: int) -> None:
    for _ in range(steps):
        sim.step_physics(1.0 / 60.0)


def settle_object(
    sim,
    rigid_object,
    anchor: AnchorCandidate,
    *,
    settle_steps: int = 180,
    check_steps: int = 60,
    max_residual_drift: float = 0.01,
    surface_tolerance: float = 0.14,
) -> bool:
    """Settle one candidate pose, then confirm it is genuinely at rest.

    The settle window has to suit the least stable object in the set, not the
    average one.  A 19 cm mustard bottle on a narrow base rocks for well over
    a second before it comes to rest, and measuring too early rejects a pose
    that was going to be perfectly stable.

    ``snap_down`` leaves a small gap above the surface, so every object drops a
    few centimetres on the first physics steps.  That first settle is expected;
    what must not happen is continued motion afterwards, which means the object
    is rolling, sliding, or toppling.  Callers freeze the already-accepted
    objects first, so this measures one pose rather than the whole scene.
    """

    step_physics(sim, settle_steps)
    if abs(object_base_y(rigid_object) - anchor.top_y) > surface_tolerance:
        return False
    if abs(float(rigid_object.translation[0]) - anchor.center[0]) > anchor.size[0] / 2.0:
        return False
    if abs(float(rigid_object.translation[2]) - anchor.center[2]) > anchor.size[2] / 2.0:
        return False
    settled = translation_of(rigid_object)
    step_physics(sim, check_steps)
    return math.dist(translation_of(rigid_object), settled) <= max_residual_drift


def _accept_placement(
    sim,
    rigid_object,
    anchor: AnchorCandidate,
    *,
    placed: Sequence,
    surface_tolerance: float,
    min_separation: float,
    min_shift_from: Optional[Sequence[float]],
    min_shift: float,
) -> bool:
    translation = rigid_object.translation
    # It must rest on this anchor's top surface, not on the floor beside it and
    # not stacked on an object placed earlier.
    if abs(object_base_y(rigid_object) - anchor.top_y) > surface_tolerance:
        return False
    # It must stay inside the support footprint.
    if abs(float(translation[0]) - anchor.center[0]) > anchor.size[0] / 2.0:
        return False
    if abs(float(translation[2]) - anchor.center[2]) > anchor.size[2] / 2.0:
        return False
    for other in placed:
        if other.object_id == rigid_object.object_id:
            continue
        distance = math.dist(
            (float(translation[0]), float(translation[1]), float(translation[2])),
            (
                float(other.translation[0]),
                float(other.translation[1]),
                float(other.translation[2]),
            ),
        )
        if distance < min_separation:
            return False
    if min_shift_from is not None:
        moved = math.dist(
            (float(translation[0]), float(translation[2])),
            (float(min_shift_from[0]), float(min_shift_from[2])),
        )
        if moved < min_shift:
            return False
    # ``snap_down`` already rejects placements that penetrate anything other
    # than the stage, which covers stacking on a previously placed target.
    return True


def pose_of(rigid_object) -> Tuple[List[float], List[float]]:
    translation = [
        float(rigid_object.translation[0]),
        float(rigid_object.translation[1]),
        float(rigid_object.translation[2]),
    ]
    rotation = [
        float(rigid_object.rotation.vector[0]),
        float(rigid_object.rotation.vector[1]),
        float(rigid_object.rotation.vector[2]),
        float(rigid_object.rotation.scalar),
    ]
    norm = math.sqrt(sum(value ** 2 for value in rotation))
    if norm > 0:
        rotation = [value / norm for value in rotation]
    return translation, rotation


def clear_rigid_objects(sim) -> None:
    rom = sim.get_rigid_object_manager()
    for object_id in list(rom.get_object_handles()):
        rom.remove_object_by_handle(object_id)


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def anchor_record(record: Mapping[str, object]) -> dict:
    """The saved anchor block, enriched with what the review report needs.

    ``AnchorInfo.from_mapping`` reads only ``object_id`` and ``category`` and
    ignores the rest, so the extra fields cost the validators nothing while
    saving the report from having to reopen the scene in Habitat to recover the
    room, the storey, and the surface geometry.
    """

    anchor: AnchorCandidate = record["anchor_candidate"]  # type: ignore[assignment]
    return {
        "object_id": anchor.object_id,
        "category": anchor.category,
        "kind": anchor.kind,
        "room": anchor.room,
        "region_id": anchor.region_id,
        "floor_index": int(anchor.floor_index),
        "floor_height": round(float(anchor.floor_height), 4),
        "top_y": round(float(anchor.top_y), 4),
        "footprint": round(float(anchor.footprint), 4),
    }


def build_config(
    *,
    cfg,
    targets,
    id_handle: Mapping[int, str],
    records: Sequence[dict],
    layout_type: str,
    layout_index: Optional[int],
    minimum_placed: int,
    relocated: Sequence[int],
    floors: Sequence[FloorLevel] = (),
    multifloor: bool = False,
    cross_floor_ids: Sequence[int] = (),
    seed: Optional[int] = None,
) -> dict:
    data = {
        "scene": {
            "scene_path": str(cfg.scene_path),
            "scene_dataset_config": str(cfg.scene_dataset_config),
        },
        "id_handle_mapping": {
            str(target.semantic_id): target.handle for target in targets
        },
        "objects": [],
    }
    for record in sorted(records, key=lambda item: item["semantic_id"]):
        data["objects"].append(
            {
                "object_id": record["object_id"],
                "translation": record["translation"],
                "rotation": record["rotation"],
                "semantic_id": record["semantic_id"],
                "anchor": anchor_record(record),
            }
        )
    data["authoring"] = {
        "layout_type": layout_type,
        "layout_index": layout_index,
        "reference_static_config": (
            None if layout_type == "static" else "../../static_scene_config.json"
        ),
        "relocated_semantic_ids": sorted(int(value) for value in relocated),
        "minimum_placed": int(minimum_placed),
        "placed_target_semantic_ids": sorted(
            int(record["semantic_id"]) for record in records
        ),
        "multifloor": bool(multifloor),
        "floors": [
            {
                "index": int(level.index),
                "height": round(float(level.height), 4),
                "y_min": round(float(level.y_min), 4),
                "y_max": round(float(level.y_max), 4),
                "navmesh_share": round(float(level.share), 4),
            }
            for level in floors
        ],
        "generated_by": "scripts/auto_dualmap_authoring.py",
        # Recorded per scene: a scene whose physics did not settle is
        # re-authored with a different seed, so one dataset-wide number would
        # not reproduce it.
        "seed": seed,
    }
    if layout_type == "cross_anchor":
        data["authoring"]["cross_floor_semantic_ids"] = sorted(
            int(value) for value in cross_floor_ids
        )
    return data


def write_json(path: Path, data: dict, overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {path}")
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w") as handle:
        json.dump(data, handle, indent=4)
    temp.replace(path)


def save_scene_metadata(sim, scene_dir: Path, cfg) -> None:
    """Mirror the metadata the interactive collector writes per scene."""

    scene = sim.semantic_scene
    class_bbox = defaultdict(list)
    class_count: Counter = Counter()
    for region in scene.regions:
        for obj in region.objects:
            if obj is None:
                continue
            name = obj.category.name() if obj.category else "unknown"
            class_bbox[name].append(
                {
                    "center": [float(value) for value in obj.aabb.center],
                    "sizes": [float(value) for value in obj.aabb.sizes],
                }
            )
            class_count[name] += 1
    scene_dir.mkdir(parents=True, exist_ok=True)
    (scene_dir / "class_bbox.json").write_text(json.dumps(dict(class_bbox), indent=4))
    (scene_dir / "class_num.json").write_text(
        json.dumps(class_count.most_common(), indent=4)
    )

    render_camera = sim._sensors["color_sensor"]._sensor_object.render_camera
    projection = render_camera.projection_matrix
    width, height = render_camera.viewport
    intrinsics = {
        "fx": float(projection[0, 0] * width / 2.0),
        "fy": float(projection[1, 1] * height / 2.0),
        "cx": float((projection[2, 0] + 1.0) * width / 2.0),
        "cy": float((projection[2, 1] + 1.0) * height / 2.0),
        "width": int(width),
        "height": int(height),
    }
    (scene_dir / "camera_intrinsics.json").write_text(json.dumps(intrinsics, indent=4))


# ---------------------------------------------------------------------------
# Layout authoring
# ---------------------------------------------------------------------------


def realise_plan(
    sim,
    plan: LayoutPlan,
    id_handle: Mapping[int, str],
    rng: random.Random,
    *,
    alternatives: Optional[Mapping[int, Sequence[AnchorCandidate]]] = None,
    previous_poses: Optional[Mapping[int, Sequence[float]]] = None,
    min_shift: float = 0.10,
    required: bool = True,
    minimum_placed: int = 6,
    keep_floor: bool = False,
    obstacles: Sequence[Tuple] = (),
    max_per_anchor: int = 2,
) -> Optional[List[dict]]:
    """Physically place the planned assignments.

    A semantically valid anchor is not always a physically usable one: the
    support may be cluttered, sloped, or too shallow for the object to come to
    rest on.  Each target therefore falls back to its next-best anchor from
    ``alternatives`` before the layout is abandoned.

    With ``required=False`` (static layouts) a target that cannot be placed
    anywhere is simply dropped, as long as ``minimum_placed`` survive.  Dynamic
    layouts must reproduce the static subset exactly, so they use
    ``required=True``.

    ``keep_floor`` confines those fallbacks to the storey the plan chose, so a
    deliberate cross-floor relocation is not quietly undone by a cluttered
    upstairs table.
    """

    alternatives = alternatives or {}
    clear_rigid_objects(sim)
    placed: List = []
    records: List[dict] = []
    anchors_by_object: Dict[int, AnchorCandidate] = {}
    # The planner caps how many targets may share a surface, but a target whose
    # planned anchor fails physically falls back to its next-best one -- and
    # that list is not filtered, so the cap was quietly bypassed and four
    # objects could end up on the same table.
    used_anchors: Dict[str, int] = {}

    for semantic_id in sorted(plan.assignments):
        handle = id_handle[semantic_id]
        shift_from = (
            previous_poses.get(semantic_id) if previous_poses is not None else None
        )
        # Relax the required displacement before giving up on a small support:
        # a crowded night stand may have no second pose 10 cm away.
        shift_schedule = (
            (min_shift, min_shift * 0.6, min_shift * 0.35)
            if shift_from is not None
            else (0.0,)
        )
        planned = plan.assignments[semantic_id]
        options = [planned, *alternatives.get(semantic_id, ())]
        if keep_floor:
            options = [
                anchor
                for anchor in options
                if anchor.floor_index == planned.floor_index
            ]
        options = [
            anchor
            for anchor in options
            if used_anchors.get(anchor.object_id, 0) < max_per_anchor
        ]
        rigid_object = None
        used_anchor = None
        for anchor in options[:MAX_ANCHOR_FALLBACKS]:
            for shift in shift_schedule:
                rigid_object = place_on_anchor(
                    sim,
                    handle,
                    anchor,
                    rng,
                    placed=placed,
                    min_shift_from=shift_from,
                    min_shift=shift,
                    obstacles=obstacles,
                )
                if rigid_object is not None:
                    used_anchor = anchor
                    break
            if rigid_object is not None:
                break

        if rigid_object is None:
            if required:
                return None
            continue

        placed.append(rigid_object)
        used_anchors[used_anchor.object_id] = (
            used_anchors.get(used_anchor.object_id, 0) + 1
        )
        anchors_by_object[int(rigid_object.object_id)] = used_anchor
        records.append(
            {
                "object_id": int(rigid_object.object_id),
                "semantic_id": int(semantic_id),
                "rigid_object": rigid_object,
                "anchor_candidate": used_anchor,
                "anchor": AnchorInfo(
                    object_id=used_anchor.object_id, category=used_anchor.category
                ).to_dict(),
                "room": used_anchor.room,
                "anchor_kind": used_anchor.kind,
            }
        )

    if len(records) < minimum_placed:
        return None

    # Settle the completed layout once more: objects placed later can nudge
    # earlier ones, and only the final equilibrium pose is worth saving.
    if not settle_layout(sim, placed, anchors_by_object):
        return None
    for record in records:
        rigid_object = record.pop("rigid_object")
        translation, rotation = pose_of(rigid_object)
        record["translation"] = translation
        record["rotation"] = rotation
    return records


def settle_layout(
    sim,
    placed: Sequence,
    anchors_by_object: Mapping[int, AnchorCandidate],
    *,
    steps: int = 180,
    max_drift: float = 0.01,
    min_separation: float = 0.35,
) -> bool:
    """Step physics over the whole layout and reject it if anything shifts.

    Each object was upright when it was accepted, but the objects placed after
    it can nudge it over, so the final equilibrium is checked again here.
    """

    set_motion(placed, habitat_sim.physics.MotionType.DYNAMIC)
    # Objects were frozen while later ones were placed, so let the whole set
    # settle together first and only then measure residual motion.
    step_physics(sim, steps)
    before = {int(obj.object_id): translation_of(obj) for obj in placed}
    step_physics(sim, steps)
    for obj in placed:
        object_id = int(obj.object_id)
        drift = math.dist(translation_of(obj), before[object_id])
        if drift > max_drift:
            return False
        anchor = anchors_by_object.get(object_id)
        if anchor is not None and abs(object_base_y(obj) - anchor.top_y) > 0.14:
            return False
        if not is_upright(obj):
            return False

    # Separation was checked as each object was dropped, but settling moves
    # them; the guarantee has to hold for the poses that actually get saved.
    for index, first in enumerate(placed):
        for second in placed[index + 1:]:
            if math.dist(translation_of(first), translation_of(second)) < min_separation:
                return False
    return True


def author_scene(
    folder: str,
    split: str,
    *,
    config_path: Path,
    output_root: Path,
    seed: int,
    overwrite: bool,
    minimum_placed: int,
    maximum_placed: int,
    multifloor: str,
    cross_floor_moves_range: Tuple[int, int],
    layouts_per_kind: int,
    verbose: bool,
) -> dict:
    """Author a scene, leaving nothing behind if any of its layouts fails.

    A scene is only useful with all seven layouts, so a partial directory would
    just make the validators fail later.
    """

    written: List[Path] = []
    report = _author_scene(
        folder,
        split,
        config_path=config_path,
        output_root=output_root,
        seed=seed,
        overwrite=overwrite,
        minimum_placed=minimum_placed,
        maximum_placed=maximum_placed,
        multifloor=multifloor,
        cross_floor_moves_range=cross_floor_moves_range,
        layouts_per_kind=layouts_per_kind,
        verbose=verbose,
        written=written,
    )
    report["placement_rejections"] = dict(REJECTIONS)
    if verbose:
        print(f"     placement rejections: {dict(REJECTIONS)}")
    if not report.get("ok"):
        for path in written:
            path.unlink(missing_ok=True)
        scene_dir = output_root / folder
        for name in ("in_anchor", "cross_anchor"):
            directory = scene_dir / "dynamic_scene_config" / name
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        for directory in (scene_dir / "dynamic_scene_config", scene_dir):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
    return report


def _author_scene(
    folder: str,
    split: str,
    *,
    config_path: Path,
    output_root: Path,
    seed: int,
    overwrite: bool,
    minimum_placed: int,
    maximum_placed: int,
    multifloor: str,
    cross_floor_moves_range: Tuple[int, int],
    layouts_per_kind: int,
    verbose: bool,
    written: List[Path],
) -> dict:
    """Author the static layout and all six dynamic layouts for one scene."""

    glb = scene_glb(split, folder)
    report: dict = {"scene": folder, "split": split, "ok": False, "layouts": {}}
    if not glb.is_file():
        report["error"] = f"Scene mesh not found: {glb}"
        return report

    cfg = load_config(config_path, glb, output_root)
    cfg.scene_name = folder
    targets = targets_from_config(cfg.authoring.targets)
    REJECTIONS.clear()
    sim = open_simulator(cfg)
    try:
        id_handle = register_targets(sim, cfg.objects_path, targets)
        levels = detect_floors(sim)
        candidates = collect_anchor_candidates(sim, verbose=verbose, levels=levels)
        wanted_floors = 1 if multifloor == "off" else 2
        candidates = restrict_to_floors(candidates, max_floors=wanted_floors)

        used_floors = sorted({c.floor_index for c in candidates})
        spread = (
            multifloor != "off"
            and len(used_floors) >= 2
            and multifloor_is_viable(candidates, targets, used_floors)
        )
        if multifloor == "require" and not spread:
            report["error"] = (
                "Scene has no second storey with enough placeable targets "
                f"(storeys with anchors: {used_floors})."
            )
            return report
        if not spread:
            # A single-storey dataset entry: keep only the densest floor so the
            # recording trajectory does not have to climb stairs for one object.
            candidates = restrict_to_floors(candidates, max_floors=1)
            used_floors = sorted({c.floor_index for c in candidates})

        report["floors"] = [
            {"index": level.index, "height": round(level.height, 3)}
            for level in levels
        ]
        report["used_floors"] = used_floors
        report["multifloor"] = bool(spread)
        report["usable_anchors"] = len(candidates)
        report["anchors_per_floor"] = dict(floors_by_anchor_count(candidates))
        report["anchor_rooms"] = dict(Counter(c.room for c in candidates))
        report["anchor_kinds"] = dict(Counter(c.kind for c in candidates))

        handles = {target.semantic_id: target.handle for target in targets}
        coverage = {
            target.handle: len(allowed_anchors(candidates, target.handle))
            for target in targets
        }
        report["target_coverage"] = coverage

        # Every annotated object that is not one of our supports is something a
        # target can be buried in or hidden behind.
        obstacles = semantic_obstacles(
            sim, anchor_ids=[candidate.object_id for candidate in candidates]
        )
        report["obstacles"] = len(obstacles)

        rng = random.Random(f"{seed}:{folder}")
        per_anchor = spread_limit(candidates, len(targets))
        report["max_per_anchor"] = per_anchor
        quota = (
            balanced_floor_quota(used_floors, maximum_placed) if spread else None
        )
        static_plan = LayoutPlan()
        for attempt_index in range(24):
            attempt = plan_static_layout(
                targets,
                candidates,
                rng,
                minimum_placed=minimum_placed,
                maximum_placed=maximum_placed,
                max_per_anchor=per_anchor if attempt_index < 12 else per_anchor + 1,
                floor_quota=quota,
            )
            if attempt.assignments:
                static_plan = attempt
                break
        if not static_plan.assignments and spread:
            # The storey split is the ambition, not the requirement: fall back
            # to a single-floor entry rather than losing the scene entirely.
            spread = False
            report["multifloor"] = False
            candidates = restrict_to_floors(candidates, max_floors=1)
            used_floors = sorted({c.floor_index for c in candidates})
            report["used_floors"] = used_floors
            report["usable_anchors"] = len(candidates)
            for _ in range(24):
                attempt = plan_static_layout(
                    targets,
                    candidates,
                    rng,
                    minimum_placed=minimum_placed,
                    maximum_placed=maximum_placed,
                    max_per_anchor=per_anchor,
                )
                if attempt.assignments:
                    static_plan = attempt
                    break
        if not static_plan.assignments:
            report["error"] = (
                f"Fewer than {minimum_placed} targets have a semantically valid "
                f"anchor ({len(candidates)} usable anchors)."
            )
            return report

        fallbacks = {
            target.semantic_id: allowed_anchors(candidates, target.handle)
            for target in targets
        }

        def alternatives_for(
            assignments: Mapping[int, AnchorCandidate],
            forbidden: Optional[Mapping[int, AnchorCandidate]] = None,
        ) -> Dict[int, List[AnchorCandidate]]:
            """Other valid anchors for each target, best fit first."""

            result: Dict[int, List[AnchorCandidate]] = {}
            for semantic_id, assigned in assignments.items():
                blocked = {assigned.object_id}
                if forbidden and semantic_id in forbidden:
                    blocked.add(forbidden[semantic_id].object_id)
                result[semantic_id] = [
                    candidate
                    for candidate in fallbacks.get(semantic_id, ())
                    if candidate.object_id not in blocked
                ]
            return result

        static_records = None
        for _ in range(6):
            static_records = realise_plan(
                sim,
                static_plan,
                id_handle,
                rng,
                alternatives=alternatives_for(static_plan.assignments),
                required=False,
                minimum_placed=minimum_placed,
                obstacles=obstacles,
                max_per_anchor=per_anchor,
            )
            if static_records is not None:
                break
        if static_records is None:
            report["error"] = (
                f"Fewer than {minimum_placed} targets could be physically placed "
                f"on a semantically valid anchor."
            )
            return report

        scene_dir = output_root / folder
        save_scene_metadata(sim, scene_dir, cfg)
        written.extend(
            scene_dir / name
            for name in ("class_bbox.json", "class_num.json", "camera_intrinsics.json")
        )
        static_data = build_config(
            cfg=cfg,
            targets=targets,
            id_handle=id_handle,
            records=static_records,
            layout_type="static",
            layout_index=None,
            minimum_placed=minimum_placed,
            relocated=[],
            floors=levels,
            multifloor=spread,
            seed=seed,
        )
        static_path = layout_output_path(output_root, folder, "static", None)
        write_json(static_path, static_data, overwrite)
        written.append(static_path)
        report["layouts"]["static"] = [
            {
                "target": id_handle[record["semantic_id"]],
                "anchor": record["anchor"]["object_id"],
                "category": record["anchor"]["category"],
                "room": record["room"],
                "floor": record["anchor_candidate"].floor_index,
            }
            for record in static_records
        ]
        static_ids = sorted(record["semantic_id"] for record in static_records)
        static_anchors = {
            record["semantic_id"]: record["anchor_candidate"]
            for record in static_records
        }
        static_poses = {
            record["semantic_id"]: record["translation"] for record in static_records
        }

        # In-anchor layouts: same support object, a genuinely different pose.
        for index in range(1, layouts_per_kind + 1):
            records = None
            for _ in range(8):
                records = realise_plan(
                    sim,
                    LayoutPlan(dict(static_anchors)),
                    id_handle,
                    rng,
                    previous_poses=static_poses,
                    min_shift=0.10,
                    minimum_placed=len(static_anchors),
                    obstacles=obstacles,
                    max_per_anchor=per_anchor + 1,
                )
                if records is not None:
                    break
            if records is None:
                report["error"] = f"in_anchor layout {index} could not be placed."
                return report
            data = build_config(
                cfg=cfg,
                targets=targets,
                id_handle=id_handle,
                records=records,
                layout_type="in_anchor",
                layout_index=index,
                minimum_placed=minimum_placed,
                relocated=static_ids,
                floors=levels,
                multifloor=spread,
                seed=seed,
            )
            path = layout_output_path(output_root, folder, "in_anchor", index)
            write_json(path, data, overwrite)
            written.append(path)
            report["layouts"][f"in_anchor_{index}"] = [
                {
                    "target": id_handle[record["semantic_id"]],
                    "anchor": record["anchor"]["object_id"],
                    "room": record["room"],
                }
                for record in records
            ]

        # Cross-anchor layouts: a different, still sensible support object, and
        # in a multi-storey scene a few of those supports are on the other floor.
        previous_plans: List[Mapping[int, AnchorCandidate]] = []
        movable = eligible_cross_floor_targets(static_anchors, handles, candidates)
        low, high = cross_floor_moves_range
        for index in range(1, layouts_per_kind + 1):
            records = None
            cross_floor_ids: List[int] = []
            # Ask for as many floor changes as the scene can actually support;
            # a scene where only one target has an upstairs home still counts.
            wanted = min(rng.randint(low, high), movable) if spread else 0
            for attempt_index in range(12):
                # Later attempts relax the quota rather than lose the layout.
                quota_now = max(1, wanted - attempt_index // 5) if wanted else 0
                # One target per surface is the goal, but a scene whose
                # affordable anchors are scarce would otherwise be lost
                # entirely; doubling up beats dropping the scene.
                per_anchor_now = per_anchor if attempt_index < 6 else per_anchor + 1
                cross_plan = plan_cross_anchor_layout(
                    static_anchors,
                    handles,
                    candidates,
                    rng,
                    avoid=previous_plans,
                    cross_floor_quota=quota_now,
                    max_per_anchor=per_anchor_now,
                )
                if not cross_plan.assignments:
                    continue
                records = realise_plan(
                    sim,
                    cross_plan,
                    id_handle,
                    rng,
                    alternatives=alternatives_for(
                        cross_plan.assignments, forbidden=static_anchors
                    ),
                    minimum_placed=len(static_anchors),
                    keep_floor=True,
                    obstacles=obstacles,
                    max_per_anchor=per_anchor_now,
                )
                if records is not None:
                    placed_anchors = {
                        record["semantic_id"]: record["anchor_candidate"]
                        for record in records
                    }
                    cross_floor_ids = cross_floor_moves(static_anchors, placed_anchors)
                    if wanted and not low <= len(cross_floor_ids) <= high:
                        # Too few and the layout is single-floor in disguise --
                        # a physical fallback pulled the movers back to their
                        # own storey.  Too many and it is a different scene
                        # rather than a change to this one: the planner's
                        # storey penalty is a preference, not a guarantee, so
                        # the count has to be checked on the placed result.
                        records = None
                        continue
                    previous_plans.append(placed_anchors)
                    break
            if records is None:
                report["error"] = (
                    f"cross_anchor layout {index} has no valid alternative anchors."
                )
                return report
            data = build_config(
                cfg=cfg,
                targets=targets,
                id_handle=id_handle,
                records=records,
                layout_type="cross_anchor",
                layout_index=index,
                minimum_placed=minimum_placed,
                relocated=static_ids,
                floors=levels,
                multifloor=spread,
                cross_floor_ids=cross_floor_ids,
                seed=seed,
            )
            path = layout_output_path(output_root, folder, "cross_anchor", index)
            write_json(path, data, overwrite)
            written.append(path)
            report["layouts"][f"cross_anchor_{index}"] = [
                {
                    "target": id_handle[record["semantic_id"]],
                    "anchor": record["anchor"]["object_id"],
                    "category": record["anchor"]["category"],
                    "room": record["room"],
                    "floor": record["anchor_candidate"].floor_index,
                    "cross_floor": record["semantic_id"] in cross_floor_ids,
                }
                for record in records
            ]
            report.setdefault("cross_floor_moves", {})[f"cross_anchor_{index}"] = [
                id_handle[sid] for sid in cross_floor_ids
            ]

        report["placed_targets"] = [id_handle[sid] for sid in static_ids]
        report["ok"] = True
        return report
    finally:
        sim.close()


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------


def command_scan(args: argparse.Namespace) -> int:
    folders = list_scenes(args.split)
    if args.scenes:
        folders = [
            folder
            for folder in (resolve_scene(token, args.split) for token in args.scenes)
            if folder
        ]
    if args.limit:
        folders = folders[: args.limit]

    results: List[dict] = []
    for folder in folders:
        glb = scene_glb(args.split, folder)
        if not glb.is_file():
            continue
        cfg = load_config(args.config, glb, args.output_root)
        cfg.scene_name = folder
        targets = targets_from_config(cfg.authoring.targets)
        started = time.time()
        try:
            sim = open_simulator(cfg)
        except Exception as exc:  # pragma: no cover - scene load failures
            print(f"[skip] {folder}: {exc}")
            continue
        try:
            levels = detect_floors(sim)
            everywhere = collect_anchor_candidates(sim, levels=levels)
            wanted_floors = 1 if args.multifloor == "off" else 2
            candidates = restrict_to_floors(everywhere, max_floors=wanted_floors)
            used_floors = sorted({c.floor_index for c in candidates})
            multifloor = (
                args.multifloor != "off"
                and len(used_floors) >= 2
                and multifloor_is_viable(candidates, targets, used_floors)
            )
            if not multifloor:
                candidates = restrict_to_floors(candidates, max_floors=1)
                used_floors = sorted({c.floor_index for c in candidates})
            coverage = {
                target.handle: len(allowed_anchors(candidates, target.handle))
                for target in targets
            }
            feasible = sum(1 for count in coverage.values() if count >= 1)
            cross_ready = sum(1 for count in coverage.values() if count >= 2)
            entry = {
                "scene": folder,
                "usable_anchors": len(candidates),
                "distinct_anchor_objects": len({c.object_id for c in candidates}),
                "rooms": dict(Counter(c.room for c in candidates)),
                "kinds": dict(Counter(c.kind for c in candidates)),
                "target_coverage": coverage,
                "targets_placeable": feasible,
                "targets_cross_anchor_ready": cross_ready,
                "navmesh_floors": len(levels),
                "floor_heights": [round(level.height, 3) for level in levels],
                "used_floors": used_floors,
                "anchors_per_floor": dict(floors_by_anchor_count(candidates)),
                "multifloor": bool(multifloor),
                "eligible": feasible >= args.minimum_placed
                and cross_ready >= args.minimum_placed,
                "load_s": round(time.time() - started, 1),
            }
            entry["multifloor_eligible"] = bool(multifloor and entry["eligible"])
            results.append(entry)
            flag = "OK " if entry["eligible"] else "-- "
            storeys = "MF" if entry["multifloor_eligible"] else "  "
            print(
                f"{flag}{storeys} {folder}  anchors={entry['usable_anchors']:3d}  "
                f"placeable={feasible}/8  cross_ready={cross_ready}/8  "
                f"floors={len(levels)}  rooms={sorted(entry['rooms'])}"
            )
        finally:
            sim.close()

    results.sort(
        key=lambda entry: (
            entry["eligible"],
            entry["targets_cross_anchor_ready"],
            entry["targets_placeable"],
            entry["distinct_anchor_objects"],
        ),
        reverse=True,
    )
    # Multi-storey scenes are the scarce resource, so surface them separately
    # rather than burying them in a list sorted by anchor count.
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(results, indent=2))
        print(f"\nWrote scan report to {args.report}")
    eligible = [entry for entry in results if entry["eligible"]]
    multifloor = [entry for entry in eligible if entry["multifloor_eligible"]]
    print(f"\n{len(eligible)} of {len(results)} scanned scenes are eligible.")
    print(f"{len(multifloor)} of those are multi-storey.")
    if eligible:
        print("Best scenes:")
        for entry in eligible[: args.top]:
            print(
                f"  {entry['scene']}  anchors={entry['usable_anchors']}  "
                f"cross_ready={entry['targets_cross_anchor_ready']}/8"
                f"{'  multifloor' if entry['multifloor_eligible'] else ''}"
            )
    return 0


def scene_pools(
    entries: Sequence[Mapping[str, object]],
) -> Tuple[List[str], List[str]]:
    """The eligible scenes from a scan, split into multi-storey and the rest.

    Both lists come out of the scan report already sorted best-first.  They are
    *pools*, not a final selection: a scene can still turn out to be
    unauthorable at build time, and the build works down the pool until it has
    the scenes it needs.
    """

    eligible = [entry for entry in entries if entry.get("eligible")]
    return (
        [str(e["scene"]) for e in eligible if e.get("multifloor_eligible")],
        [str(e["scene"]) for e in eligible if not e.get("multifloor_eligible")],
    )


def command_build(args: argparse.Namespace) -> int:
    if args.scenes:
        folders = [
            folder
            for folder in (resolve_scene(token, args.split) for token in args.scenes)
            if folder
        ]
        missing = set(args.scenes) - {
            token
            for token in args.scenes
            if resolve_scene(token, args.split)
        }
        for token in sorted(missing):
            print(f"[skip] scene not installed in {args.split}: {token}")
    elif args.from_scan:
        entries = json.loads(args.from_scan.read_text())
        multifloor_pool, single_pool = scene_pools(entries)
        if len(multifloor_pool) < args.multifloor_count:
            # Say so before spending minutes authoring: a short multi-storey
            # count is a dataset-composition decision, not a silent shortfall.
            print(
                f"[warn] the scan found only {len(multifloor_pool)} multi-storey "
                f"scenes, {args.multifloor_count} were requested.  Scan another "
                f"split and pass the extra scenes with --scenes.",
                file=sys.stderr,
            )
        folders = None
    else:
        print("Pass --scenes or --from-scan.", file=sys.stderr)
        return 2

    reports: List[dict] = []
    succeeded: List[str] = []
    multifloor_built = 0

    if folders is not None:
        phases = [(folders, len(folders))]
    else:
        # Two phases, so the dataset gets the storey mix that was asked for
        # rather than however many multi-storey scenes happen to rank highest.
        # A scene whose placements cannot meet the quality gates is replaced by
        # the next one from its pool rather than lowering the bar: the scan
        # finds far more eligible scenes than a dataset needs.
        phases = [
            (multifloor_pool, args.multifloor_count),
            (single_pool, args.count - args.multifloor_count),
            # Last resort: if there are not enough single-storey scenes, top up
            # from the multi-storey pool rather than return a short dataset.
            (multifloor_pool, args.count),
        ]

    for pool, quota in phases:
        built_here = 0
        for folder in pool:
            if folder in succeeded or len(succeeded) >= args.count:
                continue
            if built_here >= quota:
                break
            print(f"\n=== {folder} ===")
            started = time.time()
            try:
                report = author_scene(
                    folder,
                    args.split,
                    config_path=args.config,
                    output_root=args.output_root,
                    seed=args.seed,
                    overwrite=args.overwrite,
                    minimum_placed=args.minimum_placed,
                    maximum_placed=args.maximum_placed,
                    multifloor=args.multifloor,
                    cross_floor_moves_range=tuple(args.cross_floor_moves),
                    layouts_per_kind=args.layouts_per_kind,
                    verbose=args.verbose,
                )
            except FileExistsError as exc:
                report = {"scene": folder, "ok": False, "error": str(exc)}
            report["seconds"] = round(time.time() - started, 1)
            reports.append(report)
            if report.get("ok"):
                succeeded.append(folder)
                built_here += 1
                if report.get("multifloor"):
                    multifloor_built += 1
                print(
                    f"[ok] {folder}: {len(report['placed_targets'])} targets, "
                    f"{report['usable_anchors']} usable anchors, "
                    f"{report['seconds']}s"
                )
                for line in report["layouts"]["static"]:
                    print(
                        f"     static  {line['target']:<22} -> "
                        f"{line['anchor']:<18} ({line['room']})"
                    )
            else:
                print(f"[fail] {folder}: {report.get('error')}")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(reports, indent=2))
        print(f"\nWrote build report to {args.report}")

    # Validate everything that was written, using the shared offline validator.
    failures = 0
    for folder in succeeded:
        scene_root = args.output_root / folder
        static_data = json.loads((scene_root / "static_scene_config.json").read_text())
        targets = targets_from_config(
            OmegaConf.load(str(args.config)).authoring.targets
        )
        result = validate_saved_config(
            static_data, targets, expected_layout_type="static"
        )
        if not result.valid:
            failures += 1
            print(f"[invalid] {folder} static: {result.message}")
        for layout_type in ("in_anchor", "cross_anchor"):
            for index in range(1, args.layouts_per_kind + 1):
                path = layout_output_path(
                    args.output_root, folder, layout_type, index
                )
                data = json.loads(path.read_text())
                result = validate_saved_config(
                    data,
                    targets,
                    expected_layout_type=layout_type,
                    expected_layout_index=index,
                    baseline_data=static_data,
                )
                if not result.valid:
                    failures += 1
                    print(f"[invalid] {folder} {layout_type} {index}: {result.message}")

    print(
        f"\nAuthored {len(succeeded)} scenes, {multifloor_built} multi-storey, "
        f"from {len(reports)} attempted ({failures} validation error(s))."
    )
    return 1 if failures or not succeeded else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / "outputs" / "dualmap_authoring",
    )
    parser.add_argument("--split", default="val", choices=("val", "train", "minival"))
    parser.add_argument("--seed", type=int, default=20260828)
    parser.add_argument("--minimum-placed", type=int, default=6)
    parser.add_argument("--maximum-placed", type=int, default=8)
    parser.add_argument(
        "--multifloor",
        choices=("auto", "off", "require"),
        default="auto",
        help=(
            "auto: spread a scene over two storeys when it has them; "
            "off: keep every scene on its densest storey; "
            "require: fail a scene that has no usable second storey."
        ),
    )
    parser.add_argument(
        "--all-floors",
        dest="multifloor",
        action="store_const",
        const="auto",
        help="Deprecated alias for --multifloor auto.",
    )
    parser.add_argument(
        "--single-floor",
        dest="multifloor",
        action="store_const",
        const="off",
        help="Alias for --multifloor off.",
    )
    parser.add_argument(
        "--layouts-per-kind",
        type=int,
        default=1,
        help=(
            "Dynamic layouts per kind, so N=1 gives the three-layout scene "
            "(static, in-anchor, cross-anchor) and N=3 the seven-layout scene "
            "the released DualMap data ships."
        ),
    )
    parser.add_argument(
        "--cross-floor-moves",
        type=int,
        nargs=2,
        metavar=("MIN", "MAX"),
        default=(1, 3),
        help=(
            "How many targets a cross-anchor layout moves to the other storey. "
            "A handful of deliberate floor changes is the point; relocating "
            "everything upstairs would just be a second scene."
        ),
    )
    parser.add_argument("--verbose", action="store_true")

    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Rank scenes by usable, sensible anchors.")
    scan.add_argument("--scenes", nargs="*", default=None)
    scan.add_argument("--limit", type=int, default=None)
    scan.add_argument("--top", type=int, default=20)
    scan.add_argument("--report", type=Path, default=None)
    scan.set_defaults(func=command_scan)

    build = sub.add_parser("build", help="Author 7 layout files per scene.")
    build.add_argument("--scenes", nargs="*", default=None)
    build.add_argument("--from-scan", type=Path, default=None)
    build.add_argument("--count", type=int, default=15)
    build.add_argument(
        "--multifloor-count",
        type=int,
        default=5,
        help="How many of --count scenes must be multi-storey (from --from-scan).",
    )
    build.add_argument("--overwrite", action="store_true")
    build.add_argument("--report", type=Path, default=None)
    build.set_defaults(func=command_build)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
