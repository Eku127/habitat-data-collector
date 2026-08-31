# Automated DualMap Dataset Authoring

The interactive authoring mode in [`README.md`](README.md) needs seven saved
slots per scene — one static layout plus three in-anchor and three cross-anchor
layouts. A 15-scene dataset is therefore **105 GUI sessions**.

`scripts/auto_dualmap_authoring.py` performs the same placements headlessly. It
writes the identical JSON schema, and every file it produces is checked with the
same `scripts/validate_dualmap_authoring.py` used for hand-authored layouts.

A full scene takes about **7–10 seconds** instead of seven manual sessions.

The 21-scene dataset currently staged under `outputs/dualmap_authoring/` was
produced by two commands in under four minutes: 147 layouts, 1176 object
placements, all eight YCB targets in every scene, and zero findings from both
validators.

## Why not just reuse the released layouts

The released DualMap HM3D data places table-top YCB objects on whatever support
surface happened to be in view, including beds and sofas. That produces
cross-anchor queries such as *"the tomato soup can is on the bed"*, which are
not meaningful navigation targets and make the semantic-relation part of the
benchmark unreliable.

This tool constrains every placement with an explicit affordance model in
`habitat_data_collector/auto_authoring.py`:

| Layer | Rule |
|-------|------|
| Anchor kind | Raw HM3D categories are normalised (`kitchen counter` → `counter`, `bedside cabinet` → `nightstand`). Beds, sofas, armchairs, chairs and sanitary ware are **never** supports. |
| Decoy filter | Categories that merely contain a support word are rejected, so `table lamp`, `cabinet door`, `tablecloth` and `pool table` are not anchors. |
| Room type | HM3D regions carry no category label, so the room is inferred from the categories the region contains (`toilet` + `sink` + `towel` → bathroom). |
| Target affordance | Each YCB target declares which anchor kinds and room types it accepts. A plate never lands in a bathroom; a mug may sit on a bedroom nightstand; a soup can may not. |
| Geometry | The support top must be 0.30–1.45 m above **its own** floor, have a 0.10–12 m² footprint, and have a navigable point within 2 m. |
| Physics | Each drop is verified: the object must rest on that anchor's top surface (not the floor beside it, not stacked on an earlier target) and stay inside its footprint. |

The same affordance check is applied to cross-anchor relocations, which is the
part the released data gets wrong: an object moves to a *different* support that
is still sensible for it.

## Prerequisites

- an installed HM3D split with semantic annotations (`scripts/download_hm3d.sh val`);
- the annotated scene dataset config at
  `data/scene_datasets/hm3d/hm3d_annotated_basis.scene_dataset_config.json`;
- all eight YCB object configs (`scripts/download_ycb.sh`);
- a GL context.

Habitat-Sim in this image is **not** built with headless EGL support, so run
both sub-commands under `xvfb-run`. No physical display or `DISPLAY` export is
needed:

```bash
cd /app
xvfb-run -a python scripts/auto_dualmap_authoring.py --help
```

Only about a third of HM3D `val` ships semantic annotations; scenes without them
are reported as having zero anchors and are skipped.

## Step 1: scan for eligible scenes

```bash
xvfb-run -a python scripts/auto_dualmap_authoring.py \
  --split val scan \
  --report outputs/dualmap_authoring/scan_val.json
```

Each line reports the usable anchors, how many of the eight targets have at
least one valid anchor (`placeable`), and how many have at least two
(`cross_ready`, required for cross-anchor layouts):

```text
OK 00829-QaLdnwvtxbs  anchors= 16  placeable=8/8  cross_ready=8/8  rooms=[...]
-- 00801-HaxA7YrQdEC  anchors=  0  placeable=0/8  cross_ready=0/8  rooms=[]
```

A scene is `eligible` when at least six targets are both placeable and
cross-anchor ready. The report is sorted best-first. Scanning all 102 installed
`val` scenes takes about 7 minutes and yields roughly 31 eligible scenes, so
there is comfortable headroom over the 15 you need.

A semantically valid anchor is not always a physically usable one, so ask for a
few more scenes than you need (`--count 22` produced 21 usable scenes).

## Step 2: build the layouts

Take the top scenes straight from the scan report:

```bash
xvfb-run -a python scripts/auto_dualmap_authoring.py \
  --split val build \
  --from-scan outputs/dualmap_authoring/scan_val.json \
  --count 15 \
  --report outputs/dualmap_authoring/build_val.json
```

Or name scenes explicitly:

```bash
xvfb-run -a python scripts/auto_dualmap_authoring.py \
  --split val build --scenes 00829 00800 00802 --overwrite
```

Each scene prints its static placements for review:

```text
[ok] 00829-QaLdnwvtxbs: 8 targets, 16 usable anchors, 3.4s
     static  003_cracker_box        -> table_188          (living_room)
     static  005_tomato_soup_can    -> cabinet_66         (unknown)
```

Existing files are protected; pass `--overwrite` to replace a scene.

### Useful options

| Option | Effect |
|--------|--------|
| `--seed N` | Changes the layout sampling. The same seed and scene always reproduce the same dataset. |
| `--minimum-placed N` | Targets required per scene (default 6, as in the interactive mode). |
| `--maximum-placed N` | Cap on targets per scene (default 8). |
| `--all-floors` | Use anchors on every storey. By default only the storey with the densest anchor cluster is used, which keeps one recording trajectory viable. |
| `--verbose` | Print each rejected anchor with its reason. |

## Step 3: validate

`build` validates everything it wrote before exiting, and a scene whose seven
layouts cannot all be produced is rolled back so the staging tree never holds a
partial scene.

Two checks are available afterwards. The first re-reads the JSON:

```bash
python scripts/validate_dualmap_authoring.py
```

The second reloads every layout in Habitat and checks what the JSON cannot
show — that the physics and the semantics actually hold:

```bash
xvfb-run -a python scripts/verify_dualmap_layouts.py
```

It reports an object that does not rest on its recorded anchor, an anchor whose
category no longer matches the live semantic scene, a placement that drifts once
physics runs, and any placement that violates the affordance rules. The last of
these is what catches a dataset authored before the rules were tightened, so run
it after editing `auto_authoring.py`.

## Step 4: look at it

Category names hide a lot: `029_plate on shelf` reads fine whether the plate sits
squarely on a clear shelf or is buried in mesh clutter. To see the placements:

```bash
xvfb-run -a python scripts/render_dualmap_layouts.py --scene 00844-q5QZSEeHe5g
```

For each of the seven layouts this writes two images into
`outputs/dualmap_authoring/<scene>/renders/`:

- `<layout>_objects.png` — a contact sheet with one close-up per target, shot
  from a navigable viewpoint that is ray-tested to actually see the object. Each
  target is ringed, with a zoom inset, and captioned with its surface and (for
  dynamic layouts) how far it moved from the static layout.
- `<layout>_topdown.png` — the navmesh with the targets marked.

## Output

Identical to the interactive mode, plus the per-scene metadata the collector
normally writes:

```text
outputs/dualmap_authoring/<scene>/
├── static_scene_config.json
├── class_bbox.json
├── class_num.json
├── camera_intrinsics.json
└── dynamic_scene_config/
    ├── in_anchor/layout_{01,02,03}.json
    └── cross_anchor/layout_{01,02,03}.json
```

`id_handle_mapping` always lists all eight reserved authoring IDs
(`50001`–`50008`); `objects` holds only the six to eight actually placed.

## Reviewing semantics before you commit to a dataset

The build report records the anchor, its category, and the inferred room for
every placement in every layout. To list all cross-anchor relocations:

```bash
python - <<'PY'
import json
from pathlib import Path

for scene in sorted(Path("outputs/dualmap_authoring").iterdir()):
    static = scene / "static_scene_config.json"
    if not static.is_file():
        continue
    data = json.loads(static.read_text())
    names = {int(k): v for k, v in data["id_handle_mapping"].items()}
    base = {o["semantic_id"]: o["anchor"]["object_id"] for o in data["objects"]}
    for index in (1, 2, 3):
        path = scene / "dynamic_scene_config" / "cross_anchor" / f"layout_{index:02d}.json"
        for obj in json.loads(path.read_text())["objects"]:
            print(
                f"{scene.name} L{index} {names[obj['semantic_id']]:<22}"
                f"{base[obj['semantic_id']]:<18} -> {obj['anchor']['object_id']}"
            )
PY
```

If a placement still looks wrong, adjust `TARGET_AFFORDANCES` or
`_ROOM_INDICATORS` in `habitat_data_collector/auto_authoring.py` and rebuild
that scene with `--overwrite`. The rules are unit tested in
`tests/test_auto_authoring.py`.

## What this does not do

It authors **layouts**, matching the scope of the interactive authoring mode.
The released DualMap scenes also ship a recorded RGB-D trajectory (`data.zip`),
a built `global_map`, and `rosbag2_odom`. Those still come from running the
collector over each authored configuration:

```bash
python -m habitat_data_collector.main \
  load_from_config=true \
  scene_config=outputs/dualmap_authoring/<scene>/static_scene_config.json
```

Automating that pass is a separate task: it needs a viewpoint policy that
observes every placed target, not just a valid layout.
