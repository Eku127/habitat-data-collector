#!/usr/bin/env python3
"""Reload authored DualMap layouts in Habitat and check they are sound.

``scripts/validate_dualmap_authoring.py`` checks the JSON: counts, anchors,
static/dynamic consistency.  This script checks the *physics and semantics* of
what was written, by loading each layout the way the collector loads it:

* every object is reloaded at its saved pose through the same code path as
  ``load_from_config=true``;
* physics is stepped, and an object that falls, sinks, or drifts is reported;
* the recorded anchor is re-checked against the live HM3D semantic scene, so a
  layout claiming ``table_188`` really does sit on ``table_188``;
* every placement is re-tested against the affordance rules, which catches a
  layout authored before the rules were tightened.

Needs a GL context; run under ``xvfb-run`` on a headless host.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("MAGNUM_LOG", "quiet")
os.environ.setdefault("HABITAT_SIM_LOG", "quiet")

import magnum as mn  # noqa: E402

from habitat_data_collector.authoring import (  # noqa: E402
    discover_layout_slots,
    layout_output_path,
    targets_from_config,
)
from habitat_data_collector.auto_authoring import (  # noqa: E402
    FloorLevel,
    affordance_for,
    anchor_kind,
    floor_index_for,
    infer_room_type,
)

from auto_dualmap_authoring import (  # noqa: E402
    detect_floors,
    is_upright,
    is_visible,
    load_config,
    navigable_floor,
    object_base_y,
    open_simulator,
    region_room_types,
    register_targets,
)

def semantic_index(scene) -> Dict[str, object]:
    return {str(obj.id): obj for obj in scene.objects if obj is not None}


def check_layout(
    sim,
    data: dict,
    id_handle: Dict[int, str],
    objects_by_id,
    rooms: Dict[str, str],
    *,
    settle_steps: int,
    drift_tolerance: float,
    surface_tolerance: float,
    levels: Sequence[FloorLevel] = (),
    max_per_anchor: int = 2,
    min_separation: float = 0.35,
) -> List[str]:
    """Reload one layout and report everything wrong with it."""

    problems: List[str] = []
    rom = sim.get_rigid_object_manager()
    for handle in list(rom.get_object_handles()):
        rom.remove_object_by_handle(handle)

    loaded = []
    for record in data.get("objects", []):
        semantic_id = int(record["semantic_id"])
        handle = id_handle.get(semantic_id)
        if handle is None:
            problems.append(f"semantic id {semantic_id} has no registered template")
            continue
        rigid_object = rom.add_object_by_template_handle(handle)
        rigid_object.translation = mn.Vector3(*record["translation"])
        rotation = record["rotation"]
        rigid_object.rotation = mn.Quaternion(
            mn.Vector3(rotation[0], rotation[1], rotation[2]), rotation[3]
        )
        loaded.append((record, rigid_object, [float(v) for v in record["translation"]]))

    # Anchor and affordance checks use the live semantic scene, not the file.
    for record, rigid_object, _ in loaded:
        name = id_handle[int(record["semantic_id"])]
        anchor = record.get("anchor") or {}
        anchor_id = str(anchor.get("object_id"))
        semantic_object = objects_by_id.get(anchor_id)
        if semantic_object is None:
            problems.append(f"{name}: anchor {anchor_id} is not in the semantic scene")
            continue
        live_category = (
            semantic_object.category.name() if semantic_object.category else ""
        )
        if str(anchor.get("category")) != str(live_category):
            problems.append(
                f"{name}: anchor {anchor_id} category is {live_category!r}, "
                f"file says {anchor.get('category')!r}"
            )
        kind = anchor_kind(live_category)
        region_id = str(getattr(semantic_object.region, "id", "?"))
        room = rooms.get(region_id, "unknown")
        if kind is None:
            problems.append(
                f"{name}: anchor {anchor_id} ({live_category}) is not a support surface"
            )
        elif not affordance_for(name).allows(kind, room):
            problems.append(
                f"{name}: implausible placement on {anchor_id} "
                f"({live_category}) in a {room}"
            )

        top_y = float(semantic_object.aabb.center[1]) + float(
            semantic_object.aabb.sizes[1]
        ) / 2.0
        if abs(object_base_y(rigid_object) - top_y) > surface_tolerance:
            problems.append(
                f"{name}: does not rest on {anchor_id} "
                f"(base {object_base_y(rigid_object):.2f} vs top {top_y:.2f})"
            )

        # The saved storey is what the review document reports, so check it
        # against the live navmesh rather than trusting the file.
        if levels and "floor_index" in anchor:
            snapped, _ = navigable_floor(
                sim, [float(v) for v in semantic_object.aabb.center]
            )
            if snapped is not None:
                live_floor = floor_index_for(levels, snapped)
                if live_floor != int(anchor["floor_index"]):
                    problems.append(
                        f"{name}: anchor {anchor_id} is on storey {live_floor} "
                        f"({snapped:.2f} m), file says {anchor['floor_index']}"
                    )

    # The review reads these off the renders; check them here so a regression
    # is caught by a script rather than by a person scrolling 45 contact sheets.
    for record, rigid_object, _ in loaded:
        name = id_handle[int(record["semantic_id"])]
        if not is_upright(rigid_object):
            problems.append(f"{name}: is tipped over")
        elif not is_visible(sim, rigid_object):
            problems.append(f"{name}: not visible from any navigable viewpoint")

    # Crowding is what a reviewer notices before anything else: four objects on
    # one table, or two close enough to read as a single pile.
    by_anchor: Dict[str, List[str]] = {}
    for record, _, _ in loaded:
        anchor_id = str((record.get("anchor") or {}).get("object_id"))
        by_anchor.setdefault(anchor_id, []).append(
            id_handle[int(record["semantic_id"])]
        )
    for anchor_id, names in sorted(by_anchor.items()):
        if len(names) > max_per_anchor:
            problems.append(
                f"{len(names)} targets share {anchor_id}: {sorted(names)}"
            )
    for index, (record, _, position) in enumerate(loaded):
        for other_record, _, other_position in loaded[index + 1:]:
            gap = math.dist(position, other_position)
            if gap < min_separation:
                problems.append(
                    f"{id_handle[int(record['semantic_id'])]} and "
                    f"{id_handle[int(other_record['semantic_id'])]} are "
                    f"{gap:.2f} m apart, closer than {min_separation:.2f} m"
                )

    # Then let physics run: a placement that collapses is not usable data.
    for _ in range(settle_steps):
        sim.step_physics(1.0 / 60.0)
    for record, rigid_object, original in loaded:
        name = id_handle[int(record["semantic_id"])]
        moved = math.dist(
            (
                float(rigid_object.translation[0]),
                float(rigid_object.translation[1]),
                float(rigid_object.translation[2]),
            ),
            tuple(original),
        )
        if moved > drift_tolerance:
            problems.append(f"{name}: drifted {moved:.2f} m after settling")
    return problems


def check_storey_rules(
    static_data: dict,
    data: dict,
    layout_type: str,
    id_handle: Dict[int, str],
    cross_floor_moves_range: Tuple[int, int],
) -> List[str]:
    """Enforce the storey policy the dataset promises.

    In-anchor layouts keep every object on the storey the static layout put it
    on; cross-anchor layouts of a multi-storey scene move a bounded handful to
    the other storey.  Reported here rather than in the JSON validator too,
    because this is the check a reviewer will look for after a rebuild.
    """

    if layout_type == "static":
        return []
    baseline = {
        int(obj["semantic_id"]): obj.get("anchor", {})
        for obj in static_data.get("objects", [])
    }
    changed = [
        int(obj["semantic_id"])
        for obj in data.get("objects", [])
        if "floor_index" in obj.get("anchor", {})
        and "floor_index" in baseline.get(int(obj["semantic_id"]), {})
        and obj["anchor"]["floor_index"]
        != baseline[int(obj["semantic_id"])]["floor_index"]
    ]
    names = [id_handle.get(sid, str(sid)) for sid in sorted(changed)]

    if layout_type == "in_anchor":
        if changed:
            return [f"in-anchor layout changed the storey of {names}"]
        return []

    if not static_data.get("authoring", {}).get("multifloor"):
        return []
    low, high = cross_floor_moves_range
    if not low <= len(changed) <= high:
        return [
            f"moves {len(changed)} target(s) to another storey, expected "
            f"{low}-{high} ({names})"
        ]
    return []


def verify_scene(
    scene_root: Path,
    split: str,
    *,
    config_path: Path,
    settle_steps: int,
    drift_tolerance: float,
    surface_tolerance: float,
    cross_floor_moves_range: Tuple[int, int] = (1, 3),
    max_per_anchor: int = 2,
    min_separation: float = 0.35,
) -> List[str]:
    static_path = scene_root / "static_scene_config.json"
    if not static_path.is_file():
        return [f"{scene_root.name}: no static_scene_config.json"]
    static_data = json.loads(static_path.read_text())
    scene_path = Path(static_data["scene"]["scene_path"])
    if not scene_path.is_file():
        return [f"{scene_root.name}: scene mesh not found at {scene_path}"]

    cfg = load_config(config_path, scene_path, scene_root.parent)
    cfg.scene_name = scene_root.name
    targets = targets_from_config(cfg.authoring.targets)
    sim = open_simulator(cfg)
    problems: List[str] = []
    try:
        id_handle = register_targets(sim, cfg.objects_path, targets)
        objects_by_id = semantic_index(sim.semantic_scene)
        rooms = region_room_types(sim.semantic_scene)
        levels = detect_floors(sim)
        slots = discover_layout_slots(scene_root.parent, scene_root.name)
        for kind in ("in_anchor", "cross_anchor"):
            if not any(layout_type == kind for layout_type, _ in slots):
                problems.append(f"{scene_root.name}: no {kind} layout")
        for layout_type, layout_index in slots:
            path = layout_output_path(
                scene_root.parent, scene_root.name, layout_type, layout_index
            )
            data = json.loads(path.read_text())
            label = (
                layout_type
                if layout_index is None
                else f"{layout_type}_{layout_index}"
            )
            problems.extend(
                f"{scene_root.name} {label}: {problem}"
                for problem in check_layout(
                    sim,
                    data,
                    id_handle,
                    objects_by_id,
                    rooms,
                    settle_steps=settle_steps,
                    drift_tolerance=drift_tolerance,
                    surface_tolerance=surface_tolerance,
                    levels=levels,
                    max_per_anchor=max_per_anchor,
                    min_separation=min_separation,
                )
            )
            problems.extend(
                f"{scene_root.name} {label}: {problem}"
                for problem in check_storey_rules(
                    static_data,
                    data,
                    layout_type,
                    id_handle,
                    cross_floor_moves_range,
                )
            )
    finally:
        sim.close()
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=REPO_ROOT / "outputs" / "dualmap_authoring"
    )
    parser.add_argument("--scene", default=None)
    parser.add_argument("--split", default="val")
    parser.add_argument(
        "--config", type=Path, default=REPO_ROOT / "config" / "habitat_data_collector.yaml"
    )
    parser.add_argument("--settle-steps", type=int, default=60)
    parser.add_argument("--drift-tolerance", type=float, default=0.05)
    parser.add_argument("--surface-tolerance", type=float, default=0.16)
    parser.add_argument(
        "--max-per-anchor",
        type=int,
        default=2,
        help="Most targets allowed to share one surface.",
    )
    parser.add_argument(
        "--min-separation",
        type=float,
        default=0.35,
        help="Closest two targets may be, centre to centre, in metres.",
    )
    parser.add_argument(
        "--cross-floor-moves",
        type=int,
        nargs=2,
        metavar=("MIN", "MAX"),
        default=(1, 3),
        help="Storey changes a multifloor cross-anchor layout must have.",
    )
    args = parser.parse_args()

    if not args.root.is_dir():
        print(f"Authoring root does not exist: {args.root}", file=sys.stderr)
        return 1
    if args.scene:
        roots = [args.root / args.scene]
        if not roots[0].is_dir():
            roots = sorted(
                {*args.root.glob(f"*-{args.scene}"), *args.root.glob(f"{args.scene}-*")}
            )[:1]
    else:
        roots = sorted(path for path in args.root.iterdir() if path.is_dir())
    if not roots:
        print("No authored scenes found.", file=sys.stderr)
        return 1

    total = 0
    for scene_root in roots:
        problems = verify_scene(
            scene_root,
            args.split,
            config_path=args.config,
            settle_steps=args.settle_steps,
            drift_tolerance=args.drift_tolerance,
            surface_tolerance=args.surface_tolerance,
            cross_floor_moves_range=tuple(args.cross_floor_moves),
            max_per_anchor=args.max_per_anchor,
            min_separation=args.min_separation,
        )
        if problems:
            total += len(problems)
            print(f"[FAIL] {scene_root.name}")
            for problem in problems:
                print(f"  - {problem}")
        else:
            print(f"[OK] {scene_root.name}")
    print(f"\nVerified {len(roots)} scene(s) with {total} problem(s).")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
