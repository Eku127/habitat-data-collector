#!/usr/bin/env python3
"""Write one markdown document that shows every placement in the dataset.

Reviewing authored layouts otherwise means opening seven configs and fourteen
renders per scene in Habitat.  This walks the staging tree and emits a single
document with, for each of the seven layouts of each scene, the contact sheet,
the top-down map of every storey it uses, and a table of where each object sits
-- its surface, its room, its storey, how far it moved, and how well the object
suits the surface.

Reads only JSON and image paths.  No Habitat, no GL, no ``xvfb-run``: rerun it
after any edit and it finishes in a second.

    python scripts/report_dualmap_dataset.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from habitat_data_collector.authoring import (  # noqa: E402
    discover_layout_slots,
    layout_output_path,
    slot_name,
)
from habitat_data_collector.dataset_report import (  # noqa: E402
    DatasetSummary,
    LayoutReport,
    Placement,
    SceneReport,
    build_scene_report,
)

DEFAULT_ROOT = REPO_ROOT / "outputs" / "dualmap_authoring"
DEFAULT_OUT = REPO_ROOT / "documents" / "dualmap_authoring" / "dataset_review.md"

#: Human-readable heading per layout slot.
SLOT_HEADINGS = {
    "static": "Static layout",
    "in_anchor": "In-anchor layout",
    "cross_anchor": "Cross-anchor layout",
}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_scene(scene_dir: Path) -> Optional[SceneReport]:
    """Parse one scene's layouts, or ``None`` if it has no static layout."""

    configs: Dict[str, Mapping] = {}
    for layout_type, index in discover_layout_slots(scene_dir.parent, scene_dir.name):
        path = layout_output_path(
            scene_dir.parent, scene_dir.name, layout_type, index
        )
        configs[slot_name(layout_type, index)] = json.loads(path.read_text())
    if "static" not in configs:
        return None
    return build_scene_report(scene_dir.name, configs)


def scene_dirs(root: Path, only: Sequence[str] = ()) -> List[Path]:
    wanted = set(only)
    found = [
        path
        for path in sorted(root.iterdir())
        if path.is_dir() and (path / "static_scene_config.json").is_file()
    ]
    if wanted:
        found = [
            path
            for path in found
            if path.name in wanted or path.name.split("-", 1)[0] in wanted
        ]
    return found


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


def render_paths(scene_dir: Path, layout: str) -> Dict[str, List[Path]]:
    """The contact sheet and the top-down map(s) rendered for one layout."""

    renders = scene_dir / "renders"
    objects = renders / f"{layout}_objects.png"
    topdowns = sorted(renders.glob(f"{layout}_topdown_f*.png"))
    if not topdowns:
        single = renders / f"{layout}_topdown.png"
        topdowns = [single] if single.is_file() else []
    return {
        "objects": [objects] if objects.is_file() else [],
        "topdown": topdowns,
    }


def link_target(path: Path, out_dir: Path, assets: Optional[Path]) -> str:
    """Relative markdown path, copying the image next to the doc if asked."""

    if assets is not None:
        destination = assets / path.parent.parent.name / path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.is_file() or (
            destination.stat().st_mtime < path.stat().st_mtime
        ):
            destination.write_bytes(path.read_bytes())
        path = destination
    return os.path.relpath(path, out_dir).replace(os.sep, "/")


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def fmt(value: Optional[float], digits: int = 2, dash: str = "—") -> str:
    if value is None:
        return dash
    return f"{value:.{digits}f}"


def anchor_label(scene: str) -> str:
    """GitHub-style heading anchor for the table of contents."""

    return scene.lower().replace(" ", "-")


def floor_tag(scene: SceneReport, floor: int) -> str:
    height = scene.floor_height.get(floor)
    return f"F{floor}" if height is None else f"F{floor} ({height:+.2f} m)"


def static_table(scene: SceneReport, layout: LayoutReport) -> List[str]:
    lines = [
        "| Target | Surface | Category | Room | Floor | y (m) | Semantic corr. |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in layout.placements:
        lines.append(
            f"| `{p.handle}` | `{p.anchor_id}` | {p.category} | {p.room} | "
            f"{floor_tag(scene, p.floor)} | {p.translation[1]:.2f} | "
            f"{p.correspondence:.2f} |"
        )
    return lines


def in_anchor_table(scene: SceneReport, layout: LayoutReport) -> List[str]:
    lines = [
        "| Target | Surface | Δ move (m) | Δ horizontal (m) | Δz (m) | Floor |",
        "|---|---|---|---|---|---|",
    ]
    for p in layout.placements:
        lines.append(
            f"| `{p.handle}` | `{p.anchor_id}` | {fmt(p.distance)} | "
            f"{fmt(p.horizontal)} | {fmt(p.dz)} | {floor_tag(scene, p.floor)} |"
        )
    return lines


def cross_anchor_table(scene: SceneReport, layout: LayoutReport) -> List[str]:
    lines = [
        "| Target | Surface: from → to | Room | Floor | Δ move (m) | Δz (m) | "
        "Semantic corr. |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in layout.placements:
        if p.changed_floor:
            arrow = "⬆" if (p.dz or 0) > 0 else "⬇"
            floor = f"**{arrow} F{p.from_floor} → F{p.floor}**"
        else:
            floor = floor_tag(scene, p.floor)
        room = (
            f"{p.from_room} → {p.room}" if p.from_room != p.room else p.room
        )
        lines.append(
            f"| `{p.handle}` | `{p.from_anchor_id}` → `{p.anchor_id}` | {room} | "
            f"{floor} | {fmt(p.distance)} | {fmt(p.dz)} | "
            f"{fmt(p.from_correspondence)} → {p.correspondence:.2f} |"
        )
    return lines


def metrics_line(layout: LayoutReport) -> str:
    parts = [f"**{len(layout.placements)} objects**"]
    if layout.is_dynamic:
        parts.append(f"mean move {fmt(layout.mean_move)} m")
        parts.append(f"median {fmt(layout.median_move)} m")
        parts.append(f"max {fmt(layout.max_move)} m")
        parts.append(f"mean \\|Δz\\| {fmt(layout.mean_abs_dz)} m")
    parts.append(f"mean semantic corr. {layout.mean_correspondence:.2f}")
    parts.append(f"min {layout.min_correspondence:.2f}")
    parts.append(f"{layout.distinct_anchors} distinct surfaces")
    if layout.floor_changes:
        moves = ", ".join(
            f"`{p.handle}` F{p.from_floor}→F{p.floor} (Δz {p.dz:+.2f} m)"
            for p in layout.floor_changes
        )
        parts.append(f"**{len(layout.floor_changes)} floor change(s):** {moves}")
    return " · ".join(parts)


def scene_section(
    scene: SceneReport,
    scene_dir: Path,
    out_dir: Path,
    assets: Optional[Path],
) -> List[str]:
    tag = "multifloor" if scene.multifloor else "single floor"
    static = scene.static
    static_surfaces = static.distinct_anchors if static else 0
    lines = [
        f"## {scene.scene}",
        "",
        f"**{tag}** · {scene.placed_targets} targets · "
        f"{len(scene.layouts)} layouts · "
        f"seed {scene.seed if scene.seed is not None else '—'} · "
        f"{static_surfaces} distinct surfaces · "
        f"mean semantic correspondence {scene.mean_correspondence:.2f} · "
        f"mean cross-anchor move {fmt(scene.mean_cross_anchor_move)} m · "
        f"{scene.cross_floor_moves} cross-floor relocation(s)",
        "",
    ]

    if scene.floors:
        used = set(scene.floors_used)
        lines += [
            "| Floor | Height (m) | Navmesh share | Used by this dataset |",
            "|---|---|---|---|",
        ]
        for level in scene.floors:
            index = int(level["index"])
            lines.append(
                f"| F{index} | {float(level['height']):+.2f} | "
                f"{float(level.get('navmesh_share', 0.0)) * 100:.0f}% | "
                f"{'yes' if index in used else 'no'} |"
            )
        lines.append("")

    for layout in scene.layouts:
        heading = SLOT_HEADINGS[layout.layout_type]
        if layout.layout_index is not None:
            heading = f"{heading} {layout.layout_index:02d}"
        lines += [f"### {scene.scene} — {heading}", "", metrics_line(layout), ""]

        images = render_paths(scene_dir, layout.name)
        for path in images["objects"]:
            src = link_target(path, out_dir, assets)
            lines += [f"![{scene.scene} {layout.name} objects]({src})", ""]
        for path in images["topdown"]:
            src = link_target(path, out_dir, assets)
            lines += [f"![{scene.scene} {layout.name} top-down]({src})", ""]
        if not images["objects"] and not images["topdown"]:
            lines += [
                "> No renders on disk for this layout — run "
                f"`xvfb-run -a python scripts/render_dualmap_layouts.py "
                f"--scene {scene.scene}`.",
                "",
            ]

        if layout.layout_type == "static":
            lines += static_table(scene, layout)
        elif layout.layout_type == "in_anchor":
            lines += in_anchor_table(scene, layout)
        else:
            lines += cross_anchor_table(scene, layout)
        lines.append("")

    return lines


def summary_table(summary: DatasetSummary) -> List[str]:
    lines = [
        "| Scene | Floors | Multifloor | Targets | Mean semantic corr. | "
        "Mean in-anchor move (m) | Mean cross-anchor move (m) | Cross-floor moves |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for scene in summary.scenes:
        in_anchor = [
            p.distance
            for layout in scene.in_anchor
            for p in layout.placements
            if p.distance is not None
        ]
        mean_in = sum(in_anchor) / len(in_anchor) if in_anchor else None
        lines.append(
            f"| [{scene.scene}](#{anchor_label(scene.scene)}) | "
            f"{len(scene.floors)} | {'**yes**' if scene.multifloor else 'no'} | "
            f"{scene.placed_targets} | {scene.mean_correspondence:.2f} | "
            f"{fmt(mean_in)} | {fmt(scene.mean_cross_anchor_move)} | "
            f"{scene.cross_floor_moves} |"
        )
    return lines


def render_document(
    summary: DatasetSummary,
    dirs: Mapping[str, Path],
    out_dir: Path,
    assets: Optional[Path],
    root: Path,
) -> str:
    scenes = summary.scenes
    lines = [
        "# DualMap dataset review",
        "",
        f"_Generated {date.today().isoformat()} by "
        "`scripts/report_dualmap_dataset.py` from "
        f"`{os.path.relpath(root, REPO_ROOT)}`._",
        "",
        "Every placement in the authored dataset, so a layout can be judged "
        "without opening Habitat. Each scene shows a static baseline, an "
        "in-anchor layout (every object moved, same surface) and a "
        "cross-anchor layout (every object moved to a different but still "
        "sensible surface).",
        "",
        "**Semantic correspondence** is how well an object suits the surface it "
        "was placed on, on a 0–1 scale. It is the generator's own ranking "
        "(`candidate_score` in `habitat_data_collector/auto_authoring.py`) "
        "rescaled, so the review and the generator cannot disagree: 1.00 is a "
        "target in its preferred room, on one of its top-three surface kinds, "
        "on a sensibly sized surface; 0.25 is a placement that only just "
        "cleared the affordance gate.",
        "",
        "**Multifloor scenes** spread the static layout over two storeys. "
        "In-anchor layouts keep every object on its own storey; cross-anchor "
        "layouts move one to three objects to the other storey, and those rows "
        "are marked ⬆/⬇ with the height change.",
        "",
        "## What is already checked",
        "",
        "Every placement below has passed these automatically, so they should "
        "not need re-reporting — if one is wrong, the check is wrong and worth "
        "saying so:",
        "",
        "- **Upright** — the object is within 28° of the way up it was placed, "
        "measured after physics settled the whole layout. Nothing is lying on "
        "its side or upside down.",
        "- **Visible** — a ray from a navigable viewpoint at eye height hits "
        "the object first, tested over a fixed ring of viewpoints at 1.0–2.8 m. "
        "Nothing is buried in a shelf or hidden behind a door.",
        "- **Clear of clutter** — the object's bounding box does not intersect "
        "any other annotated object, so nothing sits in a sink, on a stove, or "
        "inside a lamp.",
        "- **On its surface** — it rests on the recorded anchor's top, inside "
        "the footprint and off the rim, and does not drift once physics runs.",
        "- **Uncrowded** — at most two targets per surface, and one wherever the "
        "scene has enough of them; the `distinct surfaces` figure per scene "
        "shows how it landed.",
        "- **Not touching** — no two targets are closer than 0.35 m centre to "
        "centre, so nothing reads as a single pile.",
        "",
        "**Not** checked, and still worth your eye: whether the object reads "
        "against the colour and texture of the surface it is on, whether the "
        "surface suits the object in a way the affordance rules miss, and "
        "whether the viewpoint the renderer chose flatters a bad placement.",
        "",
        "## Dataset at a glance",
        "",
        f"- **{len(scenes)} scenes**, "
        f"{len(summary.multifloor_scenes)} of them multifloor",
        f"- **{summary.layout_count} layouts**, "
        f"{summary.placement_count} object placements",
        f"- mean semantic correspondence **{summary.mean_correspondence:.2f}**",
        f"- mean in-anchor move **{fmt(summary.mean_in_anchor_move)} m**, "
        f"mean cross-anchor move **{fmt(summary.mean_cross_anchor_move)} m**",
        f"- **{summary.cross_floor_moves}** cross-floor relocations across the "
        "dataset",
        "",
        "Each scene records the seed it was authored with, so it can be "
        "reproduced on its own: "
        "`xvfb-run -a python scripts/auto_dualmap_authoring.py --split val "
        "--seed <seed> build --scenes <scene> --overwrite`. A scene whose "
        "physics did not settle was re-authored with a different seed, which "
        "is why the seed is per scene rather than per dataset.",
        "",
    ]
    lines += summary_table(summary)
    lines.append("")

    for scene in scenes:
        lines += scene_section(scene, dirs[scene.scene], out_dir, assets)

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--scene",
        nargs="*",
        default=(),
        help="Limit the report to these scenes (folder name or 5-digit id).",
    )
    parser.add_argument(
        "--copy-images",
        action="store_true",
        help=(
            "Copy the renders next to the document instead of linking into "
            "outputs/, which is gitignored.  Makes the document portable at "
            "the cost of duplicating a few hundred megabytes."
        ),
    )
    args = parser.parse_args()

    if not args.root.is_dir():
        print(f"No such dataset root: {args.root}", file=sys.stderr)
        return 2

    dirs = {path.name: path for path in scene_dirs(args.root, args.scene)}
    if not dirs:
        print(f"No authored scenes under {args.root}", file=sys.stderr)
        return 2

    scenes: List[SceneReport] = []
    for name, path in dirs.items():
        report = load_scene(path)
        if report is None:
            print(f"[skip] {name}: no static layout", file=sys.stderr)
            continue
        scenes.append(report)

    summary = DatasetSummary(scenes)
    out_dir = args.out.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    assets = (out_dir / "review_assets") if args.copy_images else None

    args.out.write_text(
        render_document(summary, dirs, out_dir, assets, args.root)
    )
    missing = sum(
        1
        for scene in scenes
        for layout in scene.layouts
        if not render_paths(dirs[scene.scene], layout.name)["objects"]
    )
    print(
        f"Wrote {args.out} — {len(scenes)} scenes, "
        f"{summary.layout_count} layouts, "
        f"{len(summary.multifloor_scenes)} multifloor, "
        f"{summary.cross_floor_moves} cross-floor relocations."
    )
    if missing:
        print(f"[warn] {missing} layout(s) have no contact sheet rendered yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
