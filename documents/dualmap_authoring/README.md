# DualMap HM3D Dataset Authoring Mode

This mode creates reviewable HM3D scene configurations for DualMap-style
static and dynamic object experiments. It limits object placement to the eight
YCB choices used by the released DualMap data and requires at least six unique
objects in each scene.

Authoring mode is opt-in. Normal data collection controls and output behavior
are unchanged when `authoring.enabled=false`.

> To build a multi-scene dataset without running one GUI session per layout,
> see [Automated DualMap Dataset Authoring](automated_dataset.md). It writes the
> same files headlessly and additionally rejects placements that make no
> semantic sense, such as a soup can on a bed.

## Target menu

Use the number keys to select an object:

| Key | YCB handle | Authoring semantic ID |
|-----|------------|-----------------------|
| `1` | `003_cracker_box` | `50001` |
| `2` | `005_tomato_soup_can` | `50002` |
| `3` | `011_banana` | `50007` |
| `4` | `019_pitcher_base` | `50003` |
| `5` | `024_bowl` | `50004` |
| `6` | `025_mug` | `50008` |
| `7` | `029_plate` | `50005` |
| `8` | `037_scissors` | `50006` |

The `50001`–`50008` IDs are reserved authoring IDs. Do not replace them with
IDs copied from an existing DualMap scene. Values such as `95` for
`003_cracker_box` are local to scene `00829`; the released scenes use different
semantic IDs for the same YCB handle.

Every saved configuration contains all eight entries in `id_handle_mapping`,
but its `objects` array contains only the six, seven, or eight objects actually
selected for that scene.

## Prerequisites

Run the mode inside the existing container. The launcher expects the repository
at `/app` and requires:

- an installed HM3D `val`, `train`, or `minival` split;
- the annotated HM3D scene dataset configuration;
- all eight YCB object configurations under `/app/data/objects/ycb/configs`;
- a working graphical `DISPLAY` value.

Open the running container from the host if needed:

```bash
docker ps --format '{{.Names}}'
docker exec -it <container-name> bash
```

Then prepare the shell inside the container:

```bash
cd /app
export DISPLAY=:4  # replace :4 if the container uses another display
```

You can check the required data before starting:

```bash
test -f data/scene_datasets/hm3d/hm3d_annotated_basis.scene_dataset_config.json
test -d data/objects/ycb/configs
scripts/list_hm3d_scenes.sh val
```

## Launcher

The launcher interface is:

```text
scripts/run_dualmap_authoring.sh \
  <scene-or-hash> \
  <static|in_anchor|cross_anchor> \
  [layout-index] \
  [val|train|minival] \
  [--overwrite]
```

The split defaults to `val`. The scene argument can be a numeric prefix such as
`00829`, a full folder name such as `00829-QaLdnwvtxbs`, or the Matterport hash
`QaLdnwvtxbs`.

Static authoring has no layout index. Dynamic authoring requires index `1`,
`2`, or `3`.

## Controls

| Key | Action |
|-----|--------|
| `1`–`8` | Select a target from the menu |
| `p` | Place the selected missing target on the visible surface nearest the camera center |
| `v` | Relocate the selected existing target |
| `-` | Delete the selected target |
| `u` | Undo the last placement, deletion, or relocation |
| `e` | Validate and save the current slot |
| `w`, `a`, `s`, `d` | Move forward/backward and turn |
| Arrow keys | Turn or look up/down |
| `q` | Exit |

Aim the center of the camera at the desired table, counter, shelf, or other
configured placeable surface before pressing `p` or `v`. The closest visible
surface center is chosen deterministically.

Only one instance of each target is allowed. Random add, grab/release, and
recording controls are disabled in this mode so that undo and anchor history
remain correct.

The HUD always shows:

- the current layout slot;
- the selected target;
- how many of the eight choices are placed, with a minimum of six;
- relocation progress for dynamic layouts;
- choices not currently placed;
- the latest validation or save result.

## Step 1: author the static layout

Start with the raw HM3D scene:

```bash
cd /app
export DISPLAY=:4
scripts/run_dualmap_authoring.sh 00829 static
```

In the simulator:

1. Select an object with `1`–`8`.
2. Aim at a visible supporting surface.
3. Press `p` to place it.
4. Repeat for any six, seven, or all eight unique objects.
5. Press `e` to validate and save.

The save is blocked if fewer than six choices are present, an object is
duplicated, an unexpected rigid object exists, or any placed object lacks anchor
metadata.

The result is:

```text
/app/outputs/dualmap_authoring/00829-QaLdnwvtxbs/static_scene_config.json
```

## Step 2: author the dynamic layouts

The static configuration must exist first. The launcher automatically loads it
as the baseline for every dynamic session.

Create the three in-anchor layouts:

```bash
scripts/run_dualmap_authoring.sh 00829 in_anchor 1
scripts/run_dualmap_authoring.sh 00829 in_anchor 2
scripts/run_dualmap_authoring.sh 00829 in_anchor 3
```

Create the three cross-anchor layouts:

```bash
scripts/run_dualmap_authoring.sh 00829 cross_anchor 1
scripts/run_dualmap_authoring.sh 00829 cross_anchor 2
scripts/run_dualmap_authoring.sh 00829 cross_anchor 3
```

For each session, select every object that was placed in the static scene and
relocate it with `v`. Press `e` after the HUD shows that every required object
has been relocated.

Dynamic layouts must contain exactly the same object subset as the static
layout. An unused menu choice cannot be introduced only in a dynamic layout.

### In-anchor rule

Every object must move with `v` but remain on the same HM3D semantic support
object as in the static layout. Anchor identity is the HM3D semantic
`object_id`, not merely its category. Two different tables are different
anchors even if both have category `table`.

### Cross-anchor rule

Every object must move with `v` to an HM3D semantic support object whose
`object_id` differs from its static anchor. Moving to another position on the
same table does not satisfy this rule.

Deleting an object and adding it again with `p` does not count as a successful
dynamic relocation. Use `v` so the operation is tracked atomically. If a
relocation attempt fails, the original object is preserved.

## Output structure

Authoring files are staged under `/app/outputs/dualmap_authoring`:

```text
/app/outputs/dualmap_authoring/<scene>/
├── static_scene_config.json
└── dynamic_scene_config/
    ├── in_anchor/
    │   ├── layout_01.json
    │   ├── layout_02.json
    │   └── layout_03.json
    └── cross_anchor/
        ├── layout_01.json
        ├── layout_02.json
        └── layout_03.json
```

One complete scene therefore requires seven saved files: one static layout and
six dynamic layouts. Twelve new scenes require 84 authoring sessions/files.

Files are written atomically. Existing slots are protected by default. To
intentionally replace one, relaunch that exact slot with `--overwrite`:

```bash
scripts/run_dualmap_authoring.sh 00829 cross_anchor 2 --overwrite
```

## Validate the staged data

Validate one completed scene:

```bash
cd /app
python scripts/validate_dualmap_authoring.py --scene 00829
```

Validate every scene under the staging root:

```bash
python scripts/validate_dualmap_authoring.py
```

Use a different staging root if necessary:

```bash
python scripts/validate_dualmap_authoring.py \
  --root /app/outputs/dualmap_authoring \
  --scene 00829-QaLdnwvtxbs
```

The validator returns a nonzero exit code for missing layout files, malformed
JSON or poses, invalid target counts, duplicates, unexpected objects, missing
anchors, mismatched static/dynamic subsets, incomplete relocation, or violated
anchor rules.

`--skip-path-checks` is available only when validating configurations on a
machine that does not have the serialized HM3D asset paths. It does not relax
object or anchor validation.

## Inspect a saved configuration

Pretty-print a file in the terminal:

```bash
python -m json.tool \
  outputs/dualmap_authoring/00829-QaLdnwvtxbs/static_scene_config.json \
  | less
```

Show only the target mapping and placed semantic IDs:

```bash
python - <<'PY'
import json
from pathlib import Path

path = Path(
    "outputs/dualmap_authoring/00829-QaLdnwvtxbs/"
    "static_scene_config.json"
)
data = json.loads(path.read_text())
print(json.dumps(data["id_handle_mapping"], indent=2))
print("placed:", [obj["semantic_id"] for obj in data["objects"]])
PY
```

Each object record includes its pose and supporting anchor:

```json
{
  "semantic_id": 50001,
  "translation": [1.0, 0.8, 2.0],
  "rotation": [0.0, 0.0, 0.0, 1.0],
  "anchor": {
    "object_id": "HM3D-semantic-object-id",
    "category": "table"
  }
}
```

## Troubleshooting

### `DISPLAY is not set`

Export the display configured for the running container before launching:

```bash
export DISPLAY=:4
```

### Scene not found

Confirm the split and exact installed name:

```bash
scripts/list_hm3d_scenes.sh val
```

Pass `train` or `minival` after the layout arguments when the scene is not in
`val`.

### Missing YCB configuration

Authoring startup intentionally fails unless all eight menu templates are
available. Check the directory or install the assets:

```bash
ls data/objects/ycb/configs/{003_cracker_box,005_tomato_soup_can,011_banana,019_pitcher_base,024_bowl,025_mug,029_plate,037_scissors}.object_config.json
scripts/download_ycb.sh
```

### No placeable surface is visible

Move or rotate the camera until the center of a configured support surface is
inside the view, then retry `p` or `v`.

### Save reports fewer than six targets

Select another unused menu choice, place it with `p`, and retry `e`. Deleting an
object can reduce the current count below six.

### Dynamic save reports targets not relocated

Select each object from the static subset and use `v`. The HUD relocation count
must reach the size of that subset before saving.

### Output already exists

Inspect the existing file first. If replacement is intentional, exit and run
the same launcher command with `--overwrite`.

## Recommended completion checklist

For every scene:

- [ ] Static layout contains 6–8 unique menu objects and saves successfully.
- [ ] In-anchor layouts 1, 2, and 3 exist and pass validation.
- [ ] Cross-anchor layouts 1, 2, and 3 exist and pass validation.
- [ ] The complete scene passes `validate_dualmap_authoring.py`.
- [ ] Generated JSON has been reviewed before promotion from the staging tree.

Promotion into the final dataset tree and automated navigation experiment
execution are separate from this authoring mode.
