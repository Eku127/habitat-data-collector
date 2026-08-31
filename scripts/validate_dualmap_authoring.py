#!/usr/bin/env python3
"""Validate staged DualMap authoring configurations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from habitat_data_collector.authoring import (  # noqa: E402
    DUALMAP_TARGETS,
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


def validate_scene(scene_root: Path, require_existing_paths: bool) -> List[str]:
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

    for layout_type in ("in_anchor", "cross_anchor"):
        for layout_index in (1, 2, 3):
            path = (
                scene_root
                / "dynamic_scene_config"
                / layout_type
                / f"layout_{layout_index:02d}.json"
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
