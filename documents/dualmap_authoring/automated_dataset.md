# Automated DualMap Dataset Authoring

The interactive authoring mode in [`README.md`](README.md) needs one saved GUI
session per layout. A 15-scene dataset is therefore **45 GUI sessions** at one
layout per kind, and 105 at the three the released DualMap data ships.

`scripts/auto_dualmap_authoring.py` performs the same placements headlessly. It
writes the identical JSON schema, and every file it produces is checked with the
same `scripts/validate_dualmap_authoring.py` used for hand-authored layouts.

A full scene takes about **5–8 seconds** instead of a manual session per layout.

## How many layouts per scene

Each scene holds a **static** baseline plus one or more **in-anchor** and
**cross-anchor** layouts, set by `--layouts-per-kind` (default **1**, giving a
three-layout scene):

| Layout | What changed |
|--------|--------------|
| `static` | The baseline the map is built against. |
| `in_anchor/layout_01.json` | Every object moved, but each is still on the surface it started on. Does the map update a pose without losing the anchoring? |
| `cross_anchor/layout_01.json` | Every object moved to a *different* but still sensible surface. Does the map re-anchor it? |

With 15 scenes and 8 targets each that is 45 layouts and 240 object-level
queries — 120 in-anchor and 120 cross-anchor. `--layouts-per-kind 3` reproduces
the released DualMap structure instead: 105 layouts, 720 queries.

The count is a property of the dataset, not of the code. The review, render and
verification tools read the layouts off disk (`discover_layout_slots` in
`habitat_data_collector/authoring.py`) rather than assuming a number, so a tree
authored at either setting works with all of them.

The dataset staged under `outputs/dualmap_authoring/` is produced by the two
commands in Steps 1–2 below, and every placement in it is shown in
[`dataset_review.md`](dataset_review.md) so a layout can be judged without
opening Habitat.

## The eight targets

| Key | Handle | Semantic ID | Shape family | Silhouette | Height |
|-----|--------|-------------|--------------|-----------:|-------:|
| `1` | `003_cracker_box` | `50001` | printed box | 350 cm² | 21.3 cm |
| `2` | `005_tomato_soup_can` | `50002` | small can | 69 cm² | 10.2 cm |
| `3` | `011_banana` | `50007` | fruit | 66 cm² | 3.7 cm |
| `4` | `019_pitcher_base` | `50003` | handled jug | 361 cm² | 24.2 cm |
| `5` | `024_bowl` | `50004` | open vessel | 89 cm² | 5.5 cm |
| `6` | `072-a_toy_airplane` | `50008` | toy | 482 cm² | 18.3 cm |
| `7` | `002_master_chef_can` | `50005` | large can | 144 cm² | 14.0 cm |
| `8` | `006_mustard_bottle` | `50006` | bottle | 186 cm² | 19.1 cm |

Four of the original eight were replaced, in two rounds, for two different
reasons. **The reserved semantic IDs never changed**, so a slot is stable even
when the object in it is not.

**Round 1 — too small to detect.** `037_scissors` and `025_mug` were the two
smallest objects in the set. Scissors lying flat present a 1.6 cm edge to a
camera at standing height, and a mug's identifying feature is a handle it hides
from half of all viewpoints.

| | silhouette | height |
|---|---|---|
| `037_scissors` → `006_mustard_bottle` | 31 cm² → 186 cm² | 1.6 cm → 19.1 cm |
| `025_mug` → `021_bleach_cleanser` | 95 cm² → 257 cm² | 8.1 cm → 25.1 cm |

**Round 2 — too alike to tell apart.** That left two pairs sharing a
silhouette: `029_plate` read as a second `024_bowl` (both flat discs) and
`021_bleach_cleanser` as a second `006_mustard_bottle` (both tall bottles). A
detector that cannot separate two targets makes the relocation queries
ambiguous, so one of each pair was replaced with a different shape family.

| | silhouette | height | why this one stayed |
|---|---|---|---|
| `029_plate` → `002_master_chef_can` | 70 cm² → 144 cm² | 2.7 cm → 14.0 cm | the bowl is deeper and larger than the plate |
| `021_bleach_cleanser` → `072-a_toy_airplane` | 257 cm² → 482 cm² | 25.1 cm → 18.3 cm | the mustard bottle placed in 15/15 scenes, the cleanser in 12/15 |

No two of the eight now share a silhouette; the two cans are the closest pair,
and they differ by 2× in size and in colour.

The affordances differ with them. `002_master_chef_can` is food and inherits
the plate's kitchen and dining rules. `072-a_toy_airplane` is the only
non-kitchen target: it belongs on a living-room shelf, a bedroom chest or a
desk, and never on a kitchen counter or a laid dining table. That deliberately
pulls one target out of the kitchen in every scene, which spreads the layout
instead of piling everything onto the worktop.

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
| Target affordance | Each YCB target declares which anchor kinds and room types it accepts. A soup can never lands in a bathroom; a mustard bottle may sit on a dining table; a toy airplane may not. |
| Geometry | The support top must be 0.30–1.45 m above **its own** floor, have a 0.10–12 m² footprint, and have a navigable point within 2 m. |
| Physics | Each drop is verified: the object must rest on that anchor's top surface (not the floor beside it, not stacked on an earlier target) and stay inside its footprint. The settle window is 3 seconds of simulated time, sized for the least stable object in the set — a 19 cm mustard bottle on a narrow base rocks for well over a second, and measuring too early rejects a pose that was going to be perfectly stable. |
| Upright | The pose is rejected if physics tipped the object over. The YCB templates are upright at identity and only yaw is randomised, but a can can still roll onto its side while it settles, and a can lying down is a different object to a perception system. |
| Clear of clutter | HM3D annotates the lamp, the sink, the stove, the television and the pile of clutter on a worktop as their own objects, so a pose whose bounding box intersects one is rejected. Annotations that merely overlap the anchor itself — HM3D labels a worktop, the cabinet under it and the run of units around it separately — are excluded, or nothing could be placed at all. |
| Visible | The object must be visible from somewhere an agent can stand: a ray from a navigable viewpoint at eye height has to hit it first. An object recessed into a shelf or wedged against a wall passes every geometric test and is still useless, because the recording pass never observes it. |
| Not crowded | At most one target per surface while the scene has twice as many usable anchors as targets, so eight objects do not end up on one worktop where nothing can be told apart. The cap is enforced again when a placement falls back to its next-best anchor, not only when the layout is planned. |
| Not touching | Targets are kept 0.35 m apart centre to centre. A plate is 0.26 m across and a cracker box 0.21 m, so anything closer reads as a single pile in a render whatever the physics says. |

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
  --count 15 --multifloor-count 5 \
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
| `--seed N` | Changes the layout sampling. The same seed and scene always reproduce the same layouts, and the seed is written into every file's `authoring` block, so a single scene can be rebuilt on its own. |
| `--minimum-placed N` | Targets required per scene (default 6, as in the interactive mode). |
| `--maximum-placed N` | Cap on targets per scene (default 8). |
| `--multifloor` | `auto` (default) spreads a scene over two storeys when it has them, `off` keeps every scene on its densest storey, `require` fails a scene without a usable second storey. `--all-floors` and `--single-floor` are aliases for `auto` and `off`. |
| `--cross-floor-moves MIN MAX` | How many targets a cross-anchor layout moves to the other storey (default `1 3`). |
| `--multifloor-count N` | On `build --from-scan`, how many of `--count` scenes must be multi-storey (default 5). |
| `--layouts-per-kind N` | Dynamic layouts of each kind per scene (default 1). |
| `--verbose` | Print each rejected anchor with its reason. |

## Multifloor scenes

Roughly two thirds of the annotated HM3D `val` scenes have more than one
storey, and a benchmark that never leaves the ground floor never tests whether
a map can re-localise an object that went upstairs.

**Detecting the storeys.** HM3D carries no storey annotation and
`region.floor_height` is missing or wrong in a good number of scenes, so the
storeys are read off the navmesh instead. Each navmesh triangle contributes its
*area* to a histogram of heights; a bin holding less than 1% of the navigable
area is a stair tread rather than a floor and separates the clusters. Weighting
by area matters: a staircase is navigable at every height between two storeys,
and a vertex-count histogram chains the whole house into one cluster. The
result is in `cluster_floor_levels()` in
`habitat_data_collector/auto_authoring.py`, unit tested without a simulator.

**What each layout does.** The policy is deliberately asymmetric, so a floor
change is a signal rather than noise:

| Layout | Storey behaviour |
|--------|------------------|
| `static` | Targets are split roughly evenly over the two storeys with the most usable anchors, with a floor of 2 targets per storey. A scene that cannot manage that falls back to a single-floor entry rather than being dropped. |
| `in_anchor` | Same support object, so nothing changes storey. The validators check this. |
| `cross_anchor` | Every target changes surface, and **1–3 of them change storey** — chosen from the targets that actually have an affordable anchor upstairs, and rotated across the three layouts so they do not repeat the same answer. |

Anchor heights are still measured against the anchor's *own* floor, so an
upstairs table is judged as a table and not as a 3 m shelf.

Scenes are marked in the scan output with `MF`, and `build --from-scan` takes
`--multifloor-count` of them before filling the rest:

```text
OK MF 00844-q5QZSEeHe5g  anchors= 44  placeable=8/8  cross_ready=8/8  floors=3  rooms=[...]
OK    00876-mv2HUxq3B53  anchors= 36  placeable=8/8  cross_ready=8/8  floors=1  rooms=[...]
```

If the split has fewer multi-storey scenes than requested, `build` says so
before it starts authoring rather than quietly returning a short dataset.

## Step 3: validate

`build` validates everything it wrote before exiting, and a scene whose layouts
cannot all be produced is rolled back so the staging tree never holds a partial
scene.

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
physics runs, an object that ended up tipped over or invisible from every
navigable viewpoint, and any placement that violates the affordance rules. The
last of these is what catches a dataset authored before the rules were
tightened, so run it after editing `auto_authoring.py`.

The upright and visibility tests are the same functions the generator gates on,
and the viewpoints are a fixed ring sweep rather than random navigable points,
so authoring and verification cannot disagree. A sampler would let a placement
pass when it is written and fail when it is checked, which is a coin toss
dressed up as a check.

It also re-derives each anchor's storey from the live navmesh and checks the
multifloor policy: an in-anchor layout that moved something between floors, or
a cross-anchor layout outside the `--cross-floor-moves` band, is a finding.

## Step 4: look at it

Category names hide a lot: `029_plate on shelf` reads fine whether the plate sits
squarely on a clear shelf or is buried in mesh clutter. To see the placements:

```bash
xvfb-run -a python scripts/render_dualmap_layouts.py --scene 00844-q5QZSEeHe5g
```

For each layout this writes into
`outputs/dualmap_authoring/<scene>/renders/`:

- `<layout>_objects.png` — a contact sheet with one close-up per target, shot
  from a navigable viewpoint that is ray-tested to actually see the object. Each
  target is ringed, with a zoom inset, and captioned with its surface, its
  storey and (for dynamic layouts) how far it moved from the static layout and
  whether it changed floor.
- `<layout>_topdown.png` — the navmesh with the targets marked, or
  `<layout>_topdown_f0.png`, `<layout>_topdown_f1.png`, … one per storey the
  layout occupies. A single slice at the scene's lowest point would draw an
  upstairs object onto the ground-floor navmesh, which is exactly the mistake a
  review is meant to catch.

## Step 5: read the whole dataset in one document

```bash
python scripts/report_dualmap_dataset.py
```

This writes [`dataset_review.md`](dataset_review.md): every scene, every
layout, the renders, and a table per layout giving each object's surface, room,
storey, how far it moved, its height change, and its **semantic
correspondence** — how well the object suits the surface it landed on, on a
0–1 scale.

That number is `candidate_score()` from
`habitat_data_collector/auto_authoring.py` rescaled by its maximum of 4.0. It
is the generator's own ranking, so the review and the generator cannot disagree
about what a good placement is: 1.00 is a target in its preferred room, on one
of its top-three surface kinds, on a sensibly sized surface; 0.25 is a
placement that only just cleared the affordance gate.

Cross-floor relocations are marked ⬆/⬇ with the height change, and each layout
carries a metrics line: mean, median and maximum move distance, mean |Δz|, mean
and minimum semantic correspondence, and the number of distinct surfaces used.

The report reads only JSON and image paths — no Habitat, no GL, no `xvfb-run` —
so it reruns in a second after any edit. `outputs/` is gitignored, so the
images it links resolve locally but not in a fresh clone; pass `--copy-images`
to copy them next to the document instead.

## Output tree

Identical to the interactive mode, plus the per-scene metadata the collector
normally writes:

```text
outputs/dualmap_authoring/<scene>/
├── static_scene_config.json
├── class_bbox.json
├── class_num.json
├── camera_intrinsics.json
├── renders/                       # from render_dualmap_layouts.py
└── dynamic_scene_config/
    ├── in_anchor/layout_01.json
    └── cross_anchor/layout_01.json
```

With `--layouts-per-kind 3` each dynamic directory holds
`layout_{01,02,03}.json` instead.

`id_handle_mapping` always lists all eight reserved authoring IDs
(`50001`–`50008`); `objects` holds only the six to eight actually placed.

Each object's `anchor` block carries what the review needs without reopening
the scene in Habitat. `AnchorInfo.from_mapping` reads only `object_id` and
`category` and ignores the rest, so the extra fields cost the validators and
the collector nothing:

```jsonc
"anchor": {
    "object_id": "kitchen island_771",
    "category": "kitchen island",
    "kind": "island",          // normalised support kind
    "room": "kitchen",         // inferred from the region's contents
    "region_id": "12",
    "floor_index": 1,          // storey, 0 is the lowest
    "floor_height": 0.2179,    // navigable height of that storey
    "top_y": 0.9412,           // support surface height
    "footprint": 1.8203        // m^2
}
```

`authoring` additionally records `multifloor`, the `floors` the scene was
detected to have, the `seed` the scene was authored with, and — on
cross-anchor layouts — `cross_floor_semantic_ids`, the targets that changed
storey.

The seed is recorded per scene rather than per dataset because
`verify_dualmap_layouts.py` occasionally finds an object that creeps a few
centimetres once physics runs on the reloaded layout — a bowl on a slightly
sloped surface, say. The fix is to re-author that one scene with a different
seed until it settles:

```bash
xvfb-run -a python scripts/auto_dualmap_authoring.py \
  --split val --seed 7 build --scenes 00823 --overwrite
```

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
    for path in sorted((scene / "dynamic_scene_config" / "cross_anchor").glob("*.json")):
        for obj in json.loads(path.read_text())["objects"]:
            print(
                f"{scene.name} {path.stem} {names[obj['semantic_id']]:<22}"
                f"{base[obj['semantic_id']]:<18} -> {obj['anchor']['object_id']}"
            )
PY
```

If a placement still looks wrong, adjust `TARGET_AFFORDANCES` or
`_ROOM_INDICATORS` in `habitat_data_collector/auto_authoring.py` and rebuild
that scene with `--overwrite`. The rules are unit tested in
`tests/test_auto_authoring.py`.

### When a scene cannot be placed well

`--verbose` prints why candidate poses were thrown away, which is the fastest
way to tell a bad scene from a gate that is too tight:

```text
     placement rejections: {'snap_down': 177, 'off_anchor': 88, 'not_visible': 9,
                            'tipped_over': 7, 'unsettled': 1, 'accepted': 24}
```

A scene that still cannot fill its layouts is **replaced by the next one from
the scan** rather than authored to a lower standard — the scan finds around 35
eligible scenes for a 15-scene dataset, so there is room to be strict. `build`
works down the multi-storey pool until `--multifloor-count` scenes are built,
then down the single-storey pool for the rest, and reports what it attempted:

```text
Authored 15 scenes, 5 multi-storey, from 19 attempted (0 validation error(s)).
```

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
