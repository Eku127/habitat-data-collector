#!/usr/bin/env python3
"""Render authored DualMap layouts so the placements can be reviewed by eye.

Category names only go so far: ``029_plate on shelf`` reads fine but may be a
plate wedged against a wall or floating off the edge of the surface.  This
script reloads each layout and renders it:

* one **contact sheet** per layout — a close-up of every placed target, framed
  from a navigable viewpoint and labelled with the surface it rests on;
* one **top-down map** per layout, with the targets marked, showing how the
  objects are spread through the scene.

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
SCRIPTS = str(Path(__file__).resolve().parent)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

os.environ.setdefault("MAGNUM_LOG", "quiet")
os.environ.setdefault("HABITAT_SIM_LOG", "quiet")

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import habitat_sim  # noqa: E402
import magnum as mn  # noqa: E402
from habitat_sim.utils.common import quat_from_angle_axis  # noqa: E402

from habitat_data_collector.authoring import (  # noqa: E402
    layout_output_path,
    targets_from_config,
)
from habitat_data_collector.config.settings import TOPDOWN_METERS_PER_PIXEL  # noqa: E402
from habitat_data_collector.utils.coordinate_transform import (  # noqa: E402
    CoordinateTransform,
)
from habitat_data_collector.utils.topdown_map import render_topdown_map  # noqa: E402

from auto_dualmap_authoring import (  # noqa: E402
    LAYOUT_LABELS,
    load_config,
    open_simulator,
    register_targets,
)

#: Candidate stand-off distances, closest first: a table-top object should
#: fill enough of the frame to be judged.
VIEW_DISTANCES = (1.0, 1.3, 1.6, 0.8, 2.0, 2.5)
#: Azimuths tried around the object, so the camera can walk around an obstacle.
VIEW_AZIMUTHS = tuple(math.radians(angle) for angle in range(0, 360, 20))
FONT = cv2.FONT_HERSHEY_SIMPLEX


def has_line_of_sight(sim, origin: np.ndarray, target: np.ndarray, object_id: int) -> bool:
    """True when nothing sits between the camera and the target object.

    The targets are loaded as rigid objects, so the test is exact: the first
    thing the ray hits must be the object we are trying to photograph.
    """

    direction = target - origin
    distance = float(np.linalg.norm(direction))
    if distance < 1e-3:
        return False
    ray = habitat_sim.geo.Ray(
        mn.Vector3(*origin.tolist()), mn.Vector3(*(direction / distance).tolist())
    )
    results = sim.cast_ray(ray, max_distance=distance + 0.5)
    if not results.has_hits():
        return False
    return results.hits[0].object_id == object_id


def aim_at(
    sim,
    agent,
    target: Sequence[float],
    camera_height: float,
    object_id: int,
) -> bool:
    """Frame ``target`` from the nearest navigable spot that can actually see it.

    Standing back along the open floor is not enough: a wall, a doorway, or the
    supporting furniture itself often blocks the view.  Candidate viewpoints are
    swept around the object and each is ray-tested before it is accepted.
    """

    point = np.array(target, dtype=np.float32)
    nav = np.array(sim.pathfinder.snap_point(point), dtype=np.float32)
    if not np.all(np.isfinite(nav)):
        return False
    floor_y = float(nav[1])
    eye = np.array([0.0, floor_y + camera_height, 0.0], dtype=np.float32)

    # Start from the direction of open floor, then sweep around the object.
    away = math.atan2(float(nav[0] - point[0]), float(nav[2] - point[2]))
    best = None
    for distance in VIEW_DISTANCES:
        for offset in VIEW_AZIMUTHS:
            angle = away + offset
            candidate = np.array(
                [
                    point[0] + math.sin(angle) * distance,
                    floor_y,
                    point[2] + math.cos(angle) * distance,
                ],
                dtype=np.float32,
            )
            snapped = np.array(sim.pathfinder.snap_point(candidate), dtype=np.float32)
            if not np.all(np.isfinite(snapped)):
                continue
            if float(np.linalg.norm(snapped[[0, 2]] - candidate[[0, 2]])) > 0.35:
                continue
            eye[0], eye[1], eye[2] = snapped[0], float(snapped[1]) + camera_height, snapped[2]
            if has_line_of_sight(sim, eye, point, object_id):
                best = snapped
                break
        if best is not None:
            break
    if best is None:
        best = nav

    delta_x = float(point[0] - best[0])
    delta_z = float(point[2] - best[2])
    horizontal = math.hypot(delta_x, delta_z)
    if horizontal < 1e-3:
        return False

    # The agent looks along -Z, so this yaw turns that axis onto the object.
    state = habitat_sim.AgentState()
    state.position = best
    state.rotation = quat_from_angle_axis(
        math.atan2(-delta_x, -delta_z), np.array([0.0, 1.0, 0.0])
    )
    agent.set_state(state)

    pitch = math.atan2(float(point[1]) - (float(best[1]) + camera_height), horizontal)
    for sensor in sim._sensors.values():
        sensor._sensor_object.node.rotation = mn.Quaternion.rotation(
            mn.Rad(pitch), mn.Vector3(1.0, 0.0, 0.0)
        )
    return True


def project_to_screen(sim, point: Sequence[float]) -> Optional[Tuple[int, int]]:
    """Pixel coordinates of a world point in the colour sensor, if in frame."""

    camera = sim._sensors["color_sensor"]._sensor_object.render_camera
    projected = camera.projection_matrix.transform_point(
        camera.camera_matrix.transform_point(mn.Vector3(*point))
    )
    screen = mn.Vector2(projected[0], -projected[1]) / camera.projection_size()[0]
    screen += mn.Vector2(0.5)
    screen *= camera.viewport
    x, y = int(screen[0]), int(screen[1])
    width, height = camera.viewport
    if 0 <= x < width and 0 <= y < height:
        return x, y
    return None


def mark_object(
    image: np.ndarray,
    position: Optional[Tuple[int, int]],
    *,
    crop: int = 150,
    inset: int = 168,
) -> np.ndarray:
    """Ring the target and inset a zoom of it.

    Table-top YCB objects are small, and from a metre away a mug is a handful of
    pixels.  The inset is what makes "is this really on that surface" reviewable.
    """

    if position is None:
        cv2.putText(
            image, "target not in frame", (10, 24), FONT, 0.5,
            (60, 60, 235), 2, cv2.LINE_AA,
        )
        return image
    height, width = image.shape[:2]
    x, y = position

    half = crop // 2
    x0, y0 = max(0, x - half), max(0, y - half)
    x1, y1 = min(width, x + half), min(height, y + half)
    patch = image[y0:y1, x0:x1].copy()

    cv2.circle(image, (x, y), 30, (60, 230, 255), 2, cv2.LINE_AA)
    cv2.drawMarker(image, (x, y), (60, 230, 255), cv2.MARKER_CROSS, 14, 1, cv2.LINE_AA)

    if patch.size:
        zoom = cv2.resize(patch, (inset, inset), interpolation=cv2.INTER_LINEAR)
        centre = inset // 2
        cv2.circle(zoom, (centre, centre), int(30 * inset / crop), (60, 230, 255), 2, cv2.LINE_AA)
        cv2.rectangle(zoom, (0, 0), (inset - 1, inset - 1), (60, 230, 255), 2)
        image[4 : 4 + inset, width - inset - 4 : width - 4] = zoom
    return image


def label_image(image: np.ndarray, title: str, subtitle: str) -> np.ndarray:
    """Draw a caption bar under one close-up."""

    height, width = image.shape[:2]
    bar = np.full((54, width, 3), 32, dtype=np.uint8)
    cv2.putText(bar, title, (10, 22), FONT, 0.52, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(bar, subtitle, (10, 43), FONT, 0.46, (140, 220, 140), 1, cv2.LINE_AA)
    framed = np.vstack([image, bar])
    return cv2.copyMakeBorder(
        framed, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=[70, 70, 70]
    )


def contact_sheet(tiles: List[np.ndarray], columns: int = 4) -> np.ndarray:
    if not tiles:
        return np.zeros((10, 10, 3), dtype=np.uint8)
    height = max(tile.shape[0] for tile in tiles)
    width = max(tile.shape[1] for tile in tiles)
    padded = []
    for tile in tiles:
        canvas = np.full((height, width, 3), 20, dtype=np.uint8)
        canvas[: tile.shape[0], : tile.shape[1]] = tile
        padded.append(canvas)
    while len(padded) % columns:
        padded.append(np.full((height, width, 3), 20, dtype=np.uint8))
    rows = [
        np.hstack(padded[index : index + columns])
        for index in range(0, len(padded), columns)
    ]
    return np.vstack(rows)


def banner(width: int, text: str) -> np.ndarray:
    bar = np.full((46, width, 3), 15, dtype=np.uint8)
    cv2.putText(bar, text, (12, 31), FONT, 0.72, (255, 255, 255), 2, cv2.LINE_AA)
    return bar


def render_layout(
    sim,
    agent,
    data: dict,
    id_handle: Dict[int, str],
    camera_height: float,
    title: str,
    baseline: Optional[Dict[int, dict]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    rom = sim.get_rigid_object_manager()
    for handle in list(rom.get_object_handles()):
        rom.remove_object_by_handle(handle)

    positions = []
    object_ids: Dict[int, int] = {}
    for record in data["objects"]:
        rigid_object = rom.add_object_by_template_handle(
            id_handle[int(record["semantic_id"])]
        )
        rigid_object.translation = mn.Vector3(*record["translation"])
        rotation = record["rotation"]
        rigid_object.rotation = mn.Quaternion(
            mn.Vector3(rotation[0], rotation[1], rotation[2]), rotation[3]
        )
        rigid_object.motion_type = habitat_sim.physics.MotionType.STATIC
        object_ids[int(record["semantic_id"])] = int(rigid_object.object_id)
        positions.append(record["translation"])

    tiles = []
    for record in sorted(data["objects"], key=lambda item: item["semantic_id"]):
        name = id_handle[int(record["semantic_id"])]
        anchor = record["anchor"]
        object_id = object_ids[int(record["semantic_id"])]
        if not aim_at(sim, agent, record["translation"], camera_height, object_id):
            continue
        frame = sim.get_sensor_observations()["color_sensor"]
        frame = cv2.cvtColor(np.asarray(frame)[:, :, :3], cv2.COLOR_RGB2BGR)
        frame = mark_object(frame, project_to_screen(sim, record["translation"]))
        subtitle = f"on {anchor['category']}  [{anchor['object_id']}]"
        if baseline is not None:
            previous = baseline.get(int(record["semantic_id"]))
            if previous is not None:
                moved = math.dist(record["translation"], previous["translation"])
                subtitle += f"   moved {moved:.2f} m"
        tiles.append(label_image(frame, name, subtitle))

    sheet = contact_sheet(tiles)
    sheet = np.vstack([banner(sheet.shape[1], title), sheet])

    floor = float(sim.pathfinder.get_bounds()[0][1])
    topdown = sim.pathfinder.get_topdown_view(TOPDOWN_METERS_PER_PIXEL, floor)
    marks = [
        CoordinateTransform.convert_to_topdown(
            sim.pathfinder, np.array(position), TOPDOWN_METERS_PER_PIXEL
        )
        for position in positions
    ]
    map_image = render_topdown_map(topdown, object_positions=marks)
    scale = max(1, int(900 / max(map_image.shape[1], 1)))
    map_image = cv2.resize(
        map_image,
        (map_image.shape[1] * scale, map_image.shape[0] * scale),
        interpolation=cv2.INTER_NEAREST,
    )
    map_image = np.vstack([banner(map_image.shape[1], title), map_image])
    return sheet, map_image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", required=True)
    parser.add_argument(
        "--root", type=Path, default=REPO_ROOT / "outputs" / "dualmap_authoring"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / "config" / "habitat_data_collector.yaml",
    )
    parser.add_argument("--width", type=int, default=520)
    parser.add_argument("--height", type=int, default=390)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    scene_root = args.root / args.scene
    if not scene_root.is_dir():
        matches = sorted(
            {*args.root.glob(f"*-{args.scene}"), *args.root.glob(f"{args.scene}-*")}
        )
        if not matches:
            print(f"No authored scene named {args.scene}", file=sys.stderr)
            return 1
        scene_root = matches[0]

    static_data = json.loads((scene_root / "static_scene_config.json").read_text())
    cfg = load_config(
        args.config, Path(static_data["scene"]["scene_path"]), args.root
    )
    cfg.scene_name = scene_root.name
    cfg.data_cfg.resolution.w = args.width
    cfg.data_cfg.resolution.h = args.height
    targets = targets_from_config(cfg.authoring.targets)

    out_dir = args.out or (scene_root / "renders")
    out_dir.mkdir(parents=True, exist_ok=True)

    sim = open_simulator(cfg, small_sensors=False)
    try:
        id_handle = register_targets(sim, cfg.objects_path, targets)
        agent = sim.get_agent(0)
        camera_height = float(cfg.data_cfg.camera_height)
        baseline = {int(o["semantic_id"]): o for o in static_data["objects"]}

        for layout_type, layout_index in LAYOUT_SLOTS:
            path = layout_output_path(
                args.root, scene_root.name, layout_type, layout_index
            )
            if not path.is_file():
                continue
            data = json.loads(path.read_text())
            name = (
                layout_type
                if layout_index is None
                else f"{layout_type}_{layout_index:02d}"
            )
            title = f"{scene_root.name}   {LAYOUT_LABELS.get(layout_type, layout_type)}"
            if layout_index is not None:
                title += f"  layout {layout_index}"
            sheet, map_image = render_layout(
                sim,
                agent,
                data,
                id_handle,
                camera_height,
                title,
                baseline=None if layout_type == "static" else baseline,
            )
            cv2.imwrite(str(out_dir / f"{name}_objects.png"), sheet)
            cv2.imwrite(str(out_dir / f"{name}_topdown.png"), map_image)
            print(f"wrote {name}_objects.png and {name}_topdown.png")
    finally:
        sim.close()
    print(f"\nRenders in {out_dir}")
    return 0


LAYOUT_SLOTS = (
    ("static", None),
    ("in_anchor", 1),
    ("in_anchor", 2),
    ("in_anchor", 3),
    ("cross_anchor", 1),
    ("cross_anchor", 2),
    ("cross_anchor", 3),
)


if __name__ == "__main__":
    raise SystemExit(main())
