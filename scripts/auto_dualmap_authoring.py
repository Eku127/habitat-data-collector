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
    AnchorCandidate,
    LayoutPlan,
    ROOM_UNKNOWN,
    anchor_is_usable,
    anchor_kind,
    allowed_anchors,
    infer_room_type,
    plan_cross_anchor_layout,
    plan_static_layout,
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


def navigable_floor(sim, center: Sequence[float], max_offset: float = 2.0):
    """Nearest navigable point to a support, used for reachability and floor."""

    point = np.array([center[0], center[1], center[2]], dtype=np.float32)
    snapped = sim.pathfinder.snap_point(point)
    snapped = np.array(snapped, dtype=np.float32)
    if not np.all(np.isfinite(snapped)):
        return None, False
    horizontal = math.dist((center[0], center[2]), (float(snapped[0]), float(snapped[2])))
    return float(snapped[1]), horizontal <= max_offset


def collect_anchor_candidates(sim, *, verbose: bool = False) -> List[AnchorCandidate]:
    scene = sim.semantic_scene
    rooms = region_room_types(scene)
    floors = region_floor_heights(scene)
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
        )
        if anchor_is_usable(candidate, floor_height=float(floor)):
            candidates.append(candidate)
        elif verbose:
            print(f"    reject {candidate.object_id} ({kind}, {room})")
    return candidates


def restrict_to_floor(
    candidates: Sequence[AnchorCandidate],
    tolerance: float = 1.6,
) -> List[AnchorCandidate]:
    """Keep the storey holding the largest usable anchor cluster."""

    if not candidates:
        return []
    heights = sorted(candidate.top_y for candidate in candidates)
    best: List[AnchorCandidate] = []
    for height in heights:
        group = [
            candidate
            for candidate in candidates
            if abs(candidate.top_y - height) <= tolerance
        ]
        if len(group) > len(best):
            best = group
    return best


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------


def object_base_y(rigid_object) -> float:
    aabb = rigid_object.root_scene_node.compute_cumulative_bb()
    return float(aabb.min[1]) + float(rigid_object.translation[1])


def place_on_anchor(
    sim,
    handle: str,
    anchor: AnchorCandidate,
    rng: random.Random,
    *,
    placed: Sequence,
    attempts: int = 22,
    shrink: float = 0.62,
    surface_tolerance: float = 0.14,
    min_separation: float = 0.16,
    min_shift_from: Optional[Sequence[float]] = None,
    min_shift: float = 0.10,
):
    """Drop one target onto ``anchor`` and verify it really landed on it."""

    rom = sim.get_rigid_object_manager()
    set_motion(placed, habitat_sim.physics.MotionType.STATIC)
    for _ in range(attempts):
        rigid_object = rom.add_object_by_template_handle(handle)
        offset_x = (rng.random() - 0.5) * anchor.size[0] * shrink
        offset_z = (rng.random() - 0.5) * anchor.size[2] * shrink
        x = anchor.center[0] + offset_x
        z = anchor.center[2] + offset_z
        y = anchor.top_y + 0.18
        rigid_object.translation = mn.Vector3(x, y, z)
        rigid_object.rotation = mn.Quaternion.rotation(
            mn.Rad(rng.uniform(0.0, 2.0 * math.pi)), mn.Vector3(0.0, 1.0, 0.0)
        )

        snapped = sutils.snap_down(sim, rigid_object, [habitat_sim.stage_id])
        if (
            snapped
            and _accept_placement(
                sim,
                rigid_object,
                anchor,
                placed=placed,
                surface_tolerance=surface_tolerance,
                min_separation=min_separation,
                min_shift_from=min_shift_from,
                min_shift=min_shift,
            )
            # A pose that only holds until physics runs is not usable data:
            # the collector steps physics continuously while recording.
            and settle_object(sim, rigid_object, anchor)
        ):
            rigid_object.motion_type = habitat_sim.physics.MotionType.STATIC
            return rigid_object
        rom.remove_object_by_id(rigid_object.object_id)
    return None


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
    settle_steps: int = 60,
    check_steps: int = 60,
    max_residual_drift: float = 0.01,
    surface_tolerance: float = 0.14,
) -> bool:
    """Settle one candidate pose, then confirm it is genuinely at rest.

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
                "anchor": record["anchor"],
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
        "generated_by": "scripts/auto_dualmap_authoring.py",
    }
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
    """

    alternatives = alternatives or {}
    clear_rigid_objects(sim)
    placed: List = []
    records: List[dict] = []
    anchors_by_object: Dict[int, AnchorCandidate] = {}

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
        options = [plan.assignments[semantic_id], *alternatives.get(semantic_id, ())]
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
    steps: int = 60,
    max_drift: float = 0.01,
) -> bool:
    """Step physics over the whole layout and reject it if anything shifts."""

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
    single_floor: bool,
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
        single_floor=single_floor,
        verbose=verbose,
        written=written,
    )
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
    single_floor: bool,
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
    sim = open_simulator(cfg)
    try:
        id_handle = register_targets(sim, cfg.objects_path, targets)
        candidates = collect_anchor_candidates(sim, verbose=verbose)
        if single_floor:
            candidates = restrict_to_floor(candidates)
        report["usable_anchors"] = len(candidates)
        report["anchor_rooms"] = dict(Counter(c.room for c in candidates))
        report["anchor_kinds"] = dict(Counter(c.kind for c in candidates))

        handles = {target.semantic_id: target.handle for target in targets}
        coverage = {
            target.handle: len(allowed_anchors(candidates, target.handle))
            for target in targets
        }
        report["target_coverage"] = coverage

        rng = random.Random(f"{seed}:{folder}")
        static_plan = LayoutPlan()
        for _ in range(24):
            attempt = plan_static_layout(
                targets,
                candidates,
                rng,
                minimum_placed=minimum_placed,
                maximum_placed=maximum_placed,
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
        for index in (1, 2, 3):
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

        # Cross-anchor layouts: a different, still sensible support object.
        previous_plans: List[Mapping[int, AnchorCandidate]] = []
        for index in (1, 2, 3):
            records = None
            for _ in range(12):
                cross_plan = plan_cross_anchor_layout(
                    static_anchors,
                    handles,
                    candidates,
                    rng,
                    avoid=previous_plans,
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
                )
                if records is not None:
                    previous_plans.append(
                        {
                            record["semantic_id"]: record["anchor_candidate"]
                            for record in records
                        }
                    )
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
                }
                for record in records
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
            candidates = collect_anchor_candidates(sim)
            if args.single_floor:
                candidates = restrict_to_floor(candidates)
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
                "eligible": feasible >= args.minimum_placed
                and cross_ready >= args.minimum_placed,
                "load_s": round(time.time() - started, 1),
            }
            results.append(entry)
            flag = "OK " if entry["eligible"] else "-- "
            print(
                f"{flag}{folder}  anchors={entry['usable_anchors']:3d}  "
                f"placeable={feasible}/8  cross_ready={cross_ready}/8  "
                f"rooms={sorted(entry['rooms'])}"
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
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(results, indent=2))
        print(f"\nWrote scan report to {args.report}")
    eligible = [entry for entry in results if entry["eligible"]]
    print(f"\n{len(eligible)} of {len(results)} scanned scenes are eligible.")
    if eligible:
        print("Best scenes:")
        for entry in eligible[: args.top]:
            print(
                f"  {entry['scene']}  anchors={entry['usable_anchors']}  "
                f"cross_ready={entry['targets_cross_anchor_ready']}/8"
            )
    return 0


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
        folders = [
            entry["scene"] for entry in entries if entry.get("eligible")
        ][: args.count]
    else:
        print("Pass --scenes or --from-scan.", file=sys.stderr)
        return 2

    reports: List[dict] = []
    succeeded: List[str] = []
    for folder in folders:
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
                single_floor=args.single_floor,
                verbose=args.verbose,
            )
        except FileExistsError as exc:
            report = {"scene": folder, "ok": False, "error": str(exc)}
        report["seconds"] = round(time.time() - started, 1)
        reports.append(report)
        if report.get("ok"):
            succeeded.append(folder)
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
            for index in (1, 2, 3):
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
        f"\nAuthored {len(succeeded)}/{len(folders)} scenes "
        f"({failures} validation error(s))."
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
        "--all-floors",
        dest="single_floor",
        action="store_false",
        help="Use anchors on every storey instead of the densest one.",
    )
    parser.add_argument("--verbose", action="store_true")
    parser.set_defaults(single_floor=True)

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
    build.add_argument("--overwrite", action="store_true")
    build.add_argument("--report", type=Path, default=None)
    build.set_defaults(func=command_build)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
