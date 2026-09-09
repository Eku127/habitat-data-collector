#!/usr/bin/env python3
"""Validate staged DualMap authoring configurations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from habitat_data_collector.authoring import (  # noqa: E402
    DUALMAP_TARGETS,
    discover_layout_slots,
    layout_output_path,
    validate_saved_config,
)


def load_json(path: Path, errors: List[str]) -> Optional[Any]:
    try:
        with path.open("r") as file:
            return json.load(file)
    except FileNotFoundError:
        errors.append(f"Missing file: {path}")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Cannot read {path}: {exc}")
    return None


def validate_scene(
    scene_root: Path,
    require_existing_paths: bool,
    cross_floor_moves_range: Tuple[int, int] = (1, 3),
) -> List[str]:
    errors: List[str] = []
    static_path = scene_root / "static_scene_config.json"
    static_data = load_json(static_path, errors)
    if static_data is None:
        return errors
    if not isinstance(static_data, dict):
        errors.append(f"{static_path}: top-level JSON value must be an object.")
        return errors

    result = validate_saved_config(
        static_data,
        DUALMAP_TARGETS,
        expected_layout_type="static",
        require_existing_paths=require_existing_paths,
    )
    errors.extend(f"{static_path}: {error}" for error in result.errors)
    static_authoring = static_data.get("authoring", {})
    if not isinstance(static_authoring, dict):
        static_authoring = {}
    if static_authoring.get("layout_index") is not None:
        errors.append(f"{static_path}: static layout_index must be null.")

    slots = discover_layout_slots(scene_root.parent, scene_root.name)
    for layout_type in ("in_anchor", "cross_anchor"):
        indices = [index for kind, index in slots if kind == layout_type]
        if not indices:
            # A dataset may carry one dynamic layout per kind or several, but
            # never none: without both kinds the scene tests no change at all.
            errors.append(f"{scene_root}: no {layout_type} layout.")
        for layout_index in indices:
            path = layout_output_path(
                scene_root.parent, scene_root.name, layout_type, layout_index
            )
            data = load_json(path, errors)
            if data is None:
                continue
            if not isinstance(data, dict):
                errors.append(f"{path}: top-level JSON value must be an object.")
                continue
            result = validate_saved_config(
                data,
                DUALMAP_TARGETS,
                expected_layout_type=layout_type,
                expected_layout_index=layout_index,
                baseline_data=static_data,
                require_existing_paths=require_existing_paths,
            )
            errors.extend(f"{path}: {error}" for error in result.errors)
            expected_reference = "../../static_scene_config.json"
            dynamic_authoring = data.get("authoring", {})
            if not isinstance(dynamic_authoring, dict):
                dynamic_authoring = {}
            actual_reference = dynamic_authoring.get("reference_static_config")
            if actual_reference != expected_reference:
                errors.append(
                    f"{path}: reference_static_config must be "
                    f"{expected_reference}."
                )
            errors.extend(
                f"{path}: {error}"
                for error in floor_errors(
                    static_data, data, layout_type, cross_floor_moves_range
                )
            )
    errors.extend(f"{static_path}: {error}" for error in anchor_field_errors(static_data))
    return errors


def anchor_field_errors(data: Any) -> List[str]:
    """The extra anchor fields the review report reads must be present.

    A layout authored before the fields existed still loads in Habitat, but the
    report would silently show every object on floor 0 in an unknown room, so
    say so rather than publish a plausible-looking lie.

    Only headless output is held to this.  The interactive authoring mode
    captures an anchor from the aimed-at bounding box and has no storey model,
    so demanding the fields there would fail every hand-authored scene; the
    report degrades to "floor 0, unknown room" for those and says so.
    """

    authoring = data.get("authoring", {})
    if not isinstance(authoring, dict) or "generated_by" not in authoring:
        return []

    errors: List[str] = []
    floors = authoring.get("floors")
    if not isinstance(floors, list) or not floors:
        errors.append(
            "authoring.floors is missing; re-author this scene with "
            "scripts/auto_dualmap_authoring.py."
        )
    known = {int(level["index"]) for level in floors or [] if "index" in level}
    for obj in data.get("objects", []):
        anchor = obj.get("anchor", {})
        semantic_id = obj.get("semantic_id")
        for field in ("kind", "room", "floor_index"):
            if field not in anchor:
                errors.append(f"Object {semantic_id} anchor is missing '{field}'.")
        floor = anchor.get("floor_index")
        if known and isinstance(floor, int) and floor not in known:
            errors.append(
                f"Object {semantic_id} sits on floor {floor}, which is not in "
                f"authoring.floors ({sorted(known)})."
            )
    return errors


def floor_errors(
    static_data: Any,
    data: Any,
    layout_type: str,
    cross_floor_moves_range: Tuple[int, int],
) -> List[str]:
    """Check the storey rules a dynamic layout has to obey.

    In-anchor means the same support object, so nothing can change storey.
    Cross-anchor in a multi-storey scene is where the floor changes live, and
    the count is bounded on both sides: zero makes the scene single-floor in
    practice, and moving everything upstairs is a different scene rather than a
    change to this one.
    """

    baseline = {
        int(obj["semantic_id"]): obj.get("anchor", {})
        for obj in static_data.get("objects", [])
    }
    changed = []
    for obj in data.get("objects", []):
        semantic_id = int(obj["semantic_id"])
        before = baseline.get(semantic_id, {})
        if "floor_index" not in before or "floor_index" not in obj.get("anchor", {}):
            continue
        if before["floor_index"] != obj["anchor"]["floor_index"]:
            changed.append(semantic_id)

    if layout_type == "in_anchor":
        return [
            f"in-anchor layout changed the storey of {sorted(changed)}."
        ] if changed else []

    if not static_data.get("authoring", {}).get("multifloor"):
        return []

    recorded = sorted(data.get("authoring", {}).get("cross_floor_semantic_ids", []))
    low, high = cross_floor_moves_range
    errors = []
    if sorted(changed) != recorded:
        errors.append(
            f"cross_floor_semantic_ids says {recorded} but the anchors say "
            f"{sorted(changed)}."
        )
    if not low <= len(changed) <= high:
        errors.append(
            f"a multifloor scene should move {low}-{high} targets to another "
            f"storey, this layout moves {len(changed)}."
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("/app/outputs/dualmap_authoring"),
        help="Root containing one directory per authored HM3D scene.",
    )
    parser.add_argument(
        "--scene",
        help="Validate only this scene folder or Matterport hash.",
    )
    parser.add_argument(
        "--cross-floor-moves",
        type=int,
        nargs=2,
        metavar=("MIN", "MAX"),
        default=(1, 3),
        help="Storey changes a multifloor cross-anchor layout must have.",
    )
    parser.add_argument(
        "--skip-path-checks",
        action="store_true",
        help="Do not require serialized scene asset paths to exist locally.",
    )
    args = parser.parse_args()

    if not args.root.is_dir():
        print(f"Authoring root does not exist: {args.root}", file=sys.stderr)
        return 1

    if args.scene:
        scene_roots = [args.root / args.scene]
        if not scene_roots[0].is_dir():
            matches = sorted({
                *args.root.glob(f"*-{args.scene}"),
                *args.root.glob(f"{args.scene}-*"),
            })
            scene_roots = matches[:1]
    else:
        scene_roots = sorted(path for path in args.root.iterdir() if path.is_dir())

    if not scene_roots:
        print("No authored scene directories were found.", file=sys.stderr)
        return 1

    all_errors: List[str] = []
    for scene_root in scene_roots:
        scene_errors = validate_scene(
            scene_root,
            require_existing_paths=not args.skip_path_checks,
            cross_floor_moves_range=tuple(args.cross_floor_moves),
        )
        if scene_errors:
            all_errors.extend(scene_errors)
            print(f"[FAIL] {scene_root.name}")
        else:
            print(f"[OK] {scene_root.name}")

    if all_errors:
        for error in all_errors:
            print(f"  - {error}", file=sys.stderr)
        print(f"Validation failed with {len(all_errors)} error(s).", file=sys.stderr)
        return 1
    print(f"Validated {len(scene_roots)} scene(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
