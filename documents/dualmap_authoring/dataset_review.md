# DualMap dataset review

_Generated 2026-09-09 by `scripts/report_dualmap_dataset.py` from `outputs/dualmap_authoring`._

Every placement in the authored dataset, so a layout can be judged without opening Habitat. Each scene shows a static baseline, an in-anchor layout (every object moved, same surface) and a cross-anchor layout (every object moved to a different but still sensible surface).

**Semantic correspondence** is how well an object suits the surface it was placed on, on a 0–1 scale. It is the generator's own ranking (`candidate_score` in `habitat_data_collector/auto_authoring.py`) rescaled, so the review and the generator cannot disagree: 1.00 is a target in its preferred room, on one of its top-three surface kinds, on a sensibly sized surface; 0.25 is a placement that only just cleared the affordance gate.

**Multifloor scenes** spread the static layout over two storeys. In-anchor layouts keep every object on its own storey; cross-anchor layouts move one to three objects to the other storey, and those rows are marked ⬆/⬇ with the height change.

## What is already checked

Every placement below has passed these automatically, so they should not need re-reporting — if one is wrong, the check is wrong and worth saying so:

- **Upright** — the object is within 28° of the way up it was placed, measured after physics settled the whole layout. Nothing is lying on its side or upside down.
- **Visible** — a ray from a navigable viewpoint at eye height hits the object first, tested over a fixed ring of viewpoints at 1.0–2.8 m. Nothing is buried in a shelf or hidden behind a door.
- **Clear of clutter** — the object's bounding box does not intersect any other annotated object, so nothing sits in a sink, on a stove, or inside a lamp.
- **On its surface** — it rests on the recorded anchor's top, inside the footprint and off the rim, and does not drift once physics runs.
- **Uncrowded** — at most two targets per surface, and one wherever the scene has enough of them; the `distinct surfaces` figure per scene shows how it landed.
- **Not touching** — no two targets are closer than 0.35 m centre to centre, so nothing reads as a single pile.

**Not** checked, and still worth your eye: whether the object reads against the colour and texture of the surface it is on, whether the surface suits the object in a way the affordance rules miss, and whether the viewpoint the renderer chose flatters a bad placement.

## Dataset at a glance

- **15 scenes**, 5 of them multifloor
- **45 layouts**, 333 object placements
- mean semantic correspondence **0.76**
- mean in-anchor move **0.26 m**, mean cross-anchor move **5.32 m**
- **11** cross-floor relocations across the dataset

Each scene records the seed it was authored with, so it can be reproduced on its own: `xvfb-run -a python scripts/auto_dualmap_authoring.py --split val --seed <seed> build --scenes <scene> --overwrite`. A scene whose physics did not settle was re-authored with a different seed, which is why the seed is per scene rather than per dataset.

| Scene | Floors | Multifloor | Targets | Mean semantic corr. | Mean in-anchor move (m) | Mean cross-anchor move (m) | Cross-floor moves |
|---|---|---|---|---|---|---|---|
| [00800-TEEsavR23oF](#00800-teesavr23of) | 2 | **yes** | 6 | 0.75 | 0.28 | 4.75 | 2 |
| [00802-wcojb4TFT35](#00802-wcojb4tft35) | 3 | no | 8 | 0.74 | 0.27 | 4.98 | 0 |
| [00808-y9hTuugGdiq](#00808-y9htuuggdiq) | 3 | **yes** | 8 | 0.62 | 0.45 | 5.52 | 2 |
| [00810-CrMo8WxCyVb](#00810-crmo8wxcyvb) | 1 | no | 8 | 0.83 | 0.22 | 3.97 | 0 |
| [00814-p53SfW6mjZe](#00814-p53sfw6mjze) | 3 | no | 7 | 0.85 | 0.46 | 8.98 | 0 |
| [00821-eF36g7L6Z9M](#00821-ef36g7l6z9m) | 2 | **yes** | 8 | 0.74 | 0.22 | 6.29 | 2 |
| [00823-7MXmsvcQjpJ](#00823-7mxmsvcqjpj) | 3 | no | 7 | 0.81 | 0.13 | 2.98 | 0 |
| [00824-Dd4bFSTQ8gi](#00824-dd4bfstq8gi) | 1 | no | 7 | 0.85 | 0.28 | 5.95 | 0 |
| [00848-ziup5kvtCCR](#00848-ziup5kvtccr) | 1 | no | 7 | 0.85 | 0.30 | 3.84 | 0 |
| [00869-MHPLjHsuG27](#00869-mhpljhsug27) | 1 | no | 7 | 0.68 | 0.29 | 4.93 | 0 |
| [00871-VBzV5z6i1WS](#00871-vbzv5z6i1ws) | 1 | no | 7 | 0.80 | 0.18 | 4.33 | 0 |
| [00873-bxsVRursffK](#00873-bxsvrursffk) | 2 | **yes** | 7 | 0.84 | 0.17 | 4.77 | 2 |
| [00876-mv2HUxq3B53](#00876-mv2huxq3b53) | 1 | no | 8 | 0.71 | 0.28 | 8.50 | 0 |
| [00878-XB4GS9ShBRE](#00878-xb4gs9shbre) | 2 | **yes** | 8 | 0.66 | 0.22 | 4.49 | 3 |
| [00891-cvZr5TUy5C5](#00891-cvzr5tuy5c5) | 3 | no | 8 | 0.72 | 0.18 | 5.15 | 0 |

## 00800-TEEsavR23oF

**multifloor** · 6 targets · 3 layouts · seed 20260828 · 6 distinct surfaces · mean semantic correspondence 0.75 · mean cross-anchor move 4.75 m · 2 cross-floor relocation(s)

| Floor | Height (m) | Navmesh share | Used by this dataset |
|---|---|---|---|
| F0 | +0.19 | 62% | yes |
| F1 | +3.21 | 33% | yes |

### 00800-TEEsavR23oF — Static layout

**6 objects** · mean semantic corr. 0.75 · min 0.50 · 6 distinct surfaces

![00800-TEEsavR23oF static objects](../../outputs/dualmap_authoring/00800-TEEsavR23oF/renders/static_objects.png)

![00800-TEEsavR23oF static top-down](../../outputs/dualmap_authoring/00800-TEEsavR23oF/renders/static_topdown_f0.png)

![00800-TEEsavR23oF static top-down](../../outputs/dualmap_authoring/00800-TEEsavR23oF/renders/static_topdown_f1.png)

| Target | Surface | Category | Room | Floor | y (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `003_cracker_box` | `worktop_336` | worktop | kitchen | F0 (+0.19 m) | 1.04 | 0.88 |
| `005_tomato_soup_can` | `table_452` | table | kitchen | F0 (+0.19 m) | 0.87 | 0.88 |
| `011_banana` | `table_267` | table | living_room | F0 (+0.19 m) | 0.71 | 0.50 |
| `019_pitcher_base` | `cabinet_454` | cabinet | kitchen | F0 (+0.19 m) | 1.22 | 0.88 |
| `024_bowl` | `table_280` | table | living_room | F0 (+0.19 m) | 0.64 | 0.50 |
| `072-a_toy_airplane` | `wardrobe_11` | wardrobe | bedroom | F1 (+3.21 m) | 4.05 | 0.88 |

### 00800-TEEsavR23oF — In-anchor layout 01

**6 objects** · mean move 0.28 m · median 0.20 m · max 0.71 m · mean \|Δz\| 0.00 m · mean semantic corr. 0.75 · min 0.50 · 6 distinct surfaces

![00800-TEEsavR23oF in_anchor_01 objects](../../outputs/dualmap_authoring/00800-TEEsavR23oF/renders/in_anchor_01_objects.png)

![00800-TEEsavR23oF in_anchor_01 top-down](../../outputs/dualmap_authoring/00800-TEEsavR23oF/renders/in_anchor_01_topdown_f0.png)

![00800-TEEsavR23oF in_anchor_01 top-down](../../outputs/dualmap_authoring/00800-TEEsavR23oF/renders/in_anchor_01_topdown_f1.png)

| Target | Surface | Δ move (m) | Δ horizontal (m) | Δz (m) | Floor |
|---|---|---|---|---|---|
| `003_cracker_box` | `worktop_336` | 0.71 | 0.71 | -0.00 | F0 (+0.19 m) |
| `005_tomato_soup_can` | `table_452` | 0.29 | 0.29 | -0.00 | F0 (+0.19 m) |
| `011_banana` | `table_267` | 0.08 | 0.08 | -0.00 | F0 (+0.19 m) |
| `019_pitcher_base` | `cabinet_454` | 0.46 | 0.46 | -0.00 | F0 (+0.19 m) |
| `024_bowl` | `table_280` | 0.04 | 0.04 | -0.00 | F0 (+0.19 m) |
| `072-a_toy_airplane` | `wardrobe_11` | 0.11 | 0.11 | -0.00 | F1 (+3.21 m) |

### 00800-TEEsavR23oF — Cross-anchor layout 01

**6 objects** · mean move 4.75 m · median 4.75 m · max 8.29 m · mean \|Δz\| 1.14 m · mean semantic corr. 0.75 · min 0.50 · 6 distinct surfaces · **2 floor change(s):** `003_cracker_box` F0→F1 (Δz +2.76 m), `072-a_toy_airplane` F1→F0 (Δz -3.10 m)

![00800-TEEsavR23oF cross_anchor_01 objects](../../outputs/dualmap_authoring/00800-TEEsavR23oF/renders/cross_anchor_01_objects.png)

![00800-TEEsavR23oF cross_anchor_01 top-down](../../outputs/dualmap_authoring/00800-TEEsavR23oF/renders/cross_anchor_01_topdown_f0.png)

![00800-TEEsavR23oF cross_anchor_01 top-down](../../outputs/dualmap_authoring/00800-TEEsavR23oF/renders/cross_anchor_01_topdown_f1.png)

| Target | Surface: from → to | Room | Floor | Δ move (m) | Δz (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `003_cracker_box` | `worktop_336` → `table_178` | kitchen → office | **⬆ F0 → F1** | 4.08 | 2.76 | 0.88 → 0.50 |
| `005_tomato_soup_can` | `table_452` → `worktop_336` | kitchen | F0 (+0.19 m) | 5.51 | 0.11 | 0.88 → 0.88 |
| `011_banana` | `table_267` → `table_280` | living_room | F0 (+0.19 m) | 3.42 | -0.10 | 0.50 → 0.50 |
| `019_pitcher_base` | `cabinet_454` → `table_452` | kitchen | F0 (+0.19 m) | 1.76 | -0.29 | 0.88 → 0.88 |
| `024_bowl` | `table_280` → `cabinet_454` | living_room → kitchen | F0 (+0.19 m) | 8.29 | 0.48 | 0.50 → 0.88 |
| `072-a_toy_airplane` | `wardrobe_11` → `dresser_480` | bedroom | **⬇ F1 → F0** | 5.41 | -3.10 | 0.88 → 0.88 |

## 00802-wcojb4TFT35

**single floor** · 8 targets · 3 layouts · seed 3 · 8 distinct surfaces · mean semantic correspondence 0.74 · mean cross-anchor move 4.98 m · 0 cross-floor relocation(s)

| Floor | Height (m) | Navmesh share | Used by this dataset |
|---|---|---|---|
| F0 | -2.21 | 26% | no |
| F1 | +0.01 | 42% | yes |
| F2 | +2.69 | 26% | no |

### 00802-wcojb4TFT35 — Static layout

**8 objects** · mean semantic corr. 0.69 · min 0.38 · 8 distinct surfaces

![00802-wcojb4TFT35 static objects](../../outputs/dualmap_authoring/00802-wcojb4TFT35/renders/static_objects.png)

![00802-wcojb4TFT35 static top-down](../../outputs/dualmap_authoring/00802-wcojb4TFT35/renders/static_topdown.png)

| Target | Surface | Category | Room | Floor | y (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `table_339` | table | living_room | F1 (+0.01 m) | 0.70 | 0.50 |
| `003_cracker_box` | `worktop_485` | worktop | kitchen | F1 (+0.01 m) | 1.06 | 1.00 |
| `005_tomato_soup_can` | `table_417` | table | unknown | F1 (+0.01 m) | 0.83 | 0.38 |
| `006_mustard_bottle` | `table_430` | table | unknown | F1 (+0.01 m) | 0.71 | 0.38 |
| `011_banana` | `table_503` | table | kitchen | F1 (+0.01 m) | 0.96 | 0.88 |
| `019_pitcher_base` | `cabinet_438` | cabinet | unknown | F1 (+0.01 m) | 0.79 | 0.38 |
| `024_bowl` | `worktop_475` | worktop | kitchen | F1 (+0.01 m) | 0.98 | 1.00 |
| `072-a_toy_airplane` | `table_346` | table | living_room | F1 (+0.01 m) | 0.72 | 1.00 |

### 00802-wcojb4TFT35 — In-anchor layout 01

**8 objects** · mean move 0.27 m · median 0.20 m · max 0.62 m · mean \|Δz\| 0.03 m · mean semantic corr. 0.69 · min 0.38 · 8 distinct surfaces

![00802-wcojb4TFT35 in_anchor_01 objects](../../outputs/dualmap_authoring/00802-wcojb4TFT35/renders/in_anchor_01_objects.png)

![00802-wcojb4TFT35 in_anchor_01 top-down](../../outputs/dualmap_authoring/00802-wcojb4TFT35/renders/in_anchor_01_topdown.png)

| Target | Surface | Δ move (m) | Δ horizontal (m) | Δz (m) | Floor |
|---|---|---|---|---|---|
| `002_master_chef_can` | `table_339` | 0.24 | 0.24 | -0.01 | F1 (+0.01 m) |
| `003_cracker_box` | `worktop_485` | 0.32 | 0.32 | 0.00 | F1 (+0.01 m) |
| `005_tomato_soup_can` | `table_417` | 0.15 | 0.15 | 0.00 | F1 (+0.01 m) |
| `006_mustard_bottle` | `table_430` | 0.14 | 0.13 | -0.05 | F1 (+0.01 m) |
| `011_banana` | `table_503` | 0.47 | 0.47 | -0.00 | F1 (+0.01 m) |
| `019_pitcher_base` | `cabinet_438` | 0.16 | 0.16 | 0.00 | F1 (+0.01 m) |
| `024_bowl` | `worktop_475` | 0.62 | 0.60 | -0.14 | F1 (+0.01 m) |
| `072-a_toy_airplane` | `table_346` | 0.09 | 0.09 | 0.00 | F1 (+0.01 m) |

### 00802-wcojb4TFT35 — Cross-anchor layout 01

**8 objects** · mean move 4.98 m · median 4.36 m · max 9.50 m · mean \|Δz\| 0.21 m · mean semantic corr. 0.86 · min 0.50 · 8 distinct surfaces

![00802-wcojb4TFT35 cross_anchor_01 objects](../../outputs/dualmap_authoring/00802-wcojb4TFT35/renders/cross_anchor_01_objects.png)

![00802-wcojb4TFT35 cross_anchor_01 top-down](../../outputs/dualmap_authoring/00802-wcojb4TFT35/renders/cross_anchor_01_topdown.png)

| Target | Surface: from → to | Room | Floor | Δ move (m) | Δz (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `table_339` → `cabinet_472` | living_room → kitchen | F1 (+0.01 m) | 9.50 | 0.32 | 0.50 → 0.75 |
| `003_cracker_box` | `worktop_485` → `table_503` | kitchen | F1 (+0.01 m) | 3.63 | -0.01 | 1.00 → 0.88 |
| `005_tomato_soup_can` | `table_417` → `worktop_485` | unknown → kitchen | F1 (+0.01 m) | 5.50 | 0.18 | 0.38 → 1.00 |
| `006_mustard_bottle` | `table_430` → `cabinet_500` | unknown → kitchen | F1 (+0.01 m) | 3.94 | 0.33 | 0.38 → 0.88 |
| `011_banana` | `table_503` → `table_339` | kitchen → living_room | F1 (+0.01 m) | 8.08 | -0.32 | 0.88 → 0.50 |
| `019_pitcher_base` | `cabinet_438` → `worktop_475` | unknown → kitchen | F1 (+0.01 m) | 3.22 | 0.28 | 0.38 → 1.00 |
| `024_bowl` | `worktop_475` → `cabinet_487` | kitchen | F1 (+0.01 m) | 1.20 | 0.00 | 1.00 → 0.88 |
| `072-a_toy_airplane` | `table_346` → `table_357` | living_room | F1 (+0.01 m) | 4.78 | 0.20 | 1.00 → 1.00 |

## 00808-y9hTuugGdiq

**multifloor** · 8 targets · 3 layouts · seed 20260828 · 8 distinct surfaces · mean semantic correspondence 0.62 · mean cross-anchor move 5.52 m · 2 cross-floor relocation(s)

| Floor | Height (m) | Navmesh share | Used by this dataset |
|---|---|---|---|
| F0 | -2.73 | 28% | no |
| F1 | +0.10 | 41% | yes |
| F2 | +3.13 | 24% | yes |

### 00808-y9hTuugGdiq — Static layout

**8 objects** · mean semantic corr. 0.59 · min 0.38 · 8 distinct surfaces

![00808-y9hTuugGdiq static objects](../../outputs/dualmap_authoring/00808-y9hTuugGdiq/renders/static_objects.png)

![00808-y9hTuugGdiq static top-down](../../outputs/dualmap_authoring/00808-y9hTuugGdiq/renders/static_topdown_f1.png)

![00808-y9hTuugGdiq static top-down](../../outputs/dualmap_authoring/00808-y9hTuugGdiq/renders/static_topdown_f2.png)

| Target | Surface | Category | Room | Floor | y (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `shelving_142` | shelving | unknown | F2 (+3.13 m) | 3.83 | 0.38 |
| `003_cracker_box` | `coffee table_229` | coffee table | living_room | F1 (+0.10 m) | 0.56 | 0.50 |
| `005_tomato_soup_can` | `shelving_129` | shelving | unknown | F2 (+3.13 m) | 3.81 | 0.38 |
| `006_mustard_bottle` | `shelving_145` | shelving | unknown | F2 (+3.13 m) | 3.90 | 0.38 |
| `011_banana` | `kitchen counter_332` | kitchen counter | kitchen | F1 (+0.10 m) | 0.98 | 0.88 |
| `019_pitcher_base` | `kitchen cabinet_292` | kitchen cabinet | kitchen | F1 (+0.10 m) | 1.09 | 0.88 |
| `024_bowl` | `cabinet_263` | cabinet | living_room | F1 (+0.10 m) | 0.80 | 0.50 |
| `072-a_toy_airplane` | `sideboard_39` | sideboard | bedroom | F2 (+3.13 m) | 4.09 | 0.88 |

### 00808-y9hTuugGdiq — In-anchor layout 01

**8 objects** · mean move 0.45 m · median 0.14 m · max 2.36 m · mean \|Δz\| 0.01 m · mean semantic corr. 0.59 · min 0.38 · 8 distinct surfaces

![00808-y9hTuugGdiq in_anchor_01 objects](../../outputs/dualmap_authoring/00808-y9hTuugGdiq/renders/in_anchor_01_objects.png)

![00808-y9hTuugGdiq in_anchor_01 top-down](../../outputs/dualmap_authoring/00808-y9hTuugGdiq/renders/in_anchor_01_topdown_f1.png)

![00808-y9hTuugGdiq in_anchor_01 top-down](../../outputs/dualmap_authoring/00808-y9hTuugGdiq/renders/in_anchor_01_topdown_f2.png)

| Target | Surface | Δ move (m) | Δ horizontal (m) | Δz (m) | Floor |
|---|---|---|---|---|---|
| `002_master_chef_can` | `shelving_142` | 0.15 | 0.15 | -0.01 | F2 (+3.13 m) |
| `003_cracker_box` | `coffee table_229` | 0.20 | 0.20 | 0.00 | F1 (+0.10 m) |
| `005_tomato_soup_can` | `shelving_129` | 0.14 | 0.14 | 0.00 | F2 (+3.13 m) |
| `006_mustard_bottle` | `shelving_145` | 0.13 | 0.11 | -0.06 | F2 (+3.13 m) |
| `011_banana` | `kitchen counter_332` | 2.36 | 2.36 | -0.01 | F1 (+0.10 m) |
| `019_pitcher_base` | `kitchen cabinet_292` | 0.39 | 0.39 | -0.00 | F1 (+0.10 m) |
| `024_bowl` | `cabinet_263` | 0.08 | 0.08 | 0.00 | F1 (+0.10 m) |
| `072-a_toy_airplane` | `sideboard_39` | 0.12 | 0.12 | 0.00 | F2 (+3.13 m) |

### 00808-y9hTuugGdiq — Cross-anchor layout 01

**8 objects** · mean move 5.52 m · median 5.52 m · max 8.53 m · mean \|Δz\| 0.90 m · mean semantic corr. 0.67 · min 0.38 · 8 distinct surfaces · **2 floor change(s):** `006_mustard_bottle` F2→F1 (Δz -2.85 m), `072-a_toy_airplane` F2→F1 (Δz -3.14 m)

![00808-y9hTuugGdiq cross_anchor_01 objects](../../outputs/dualmap_authoring/00808-y9hTuugGdiq/renders/cross_anchor_01_objects.png)

![00808-y9hTuugGdiq cross_anchor_01 top-down](../../outputs/dualmap_authoring/00808-y9hTuugGdiq/renders/cross_anchor_01_topdown_f1.png)

![00808-y9hTuugGdiq cross_anchor_01 top-down](../../outputs/dualmap_authoring/00808-y9hTuugGdiq/renders/cross_anchor_01_topdown_f2.png)

| Target | Surface: from → to | Room | Floor | Δ move (m) | Δz (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `shelving_142` → `shelving_129` | unknown | F2 (+3.13 m) | 5.03 | -0.00 | 0.38 → 0.38 |
| `003_cracker_box` | `coffee table_229` → `kitchen cabinet_292` | living_room → kitchen | F1 (+0.10 m) | 5.58 | 0.51 | 0.50 → 0.88 |
| `005_tomato_soup_can` | `shelving_129` → `shelving_145` | unknown | F2 (+3.13 m) | 2.14 | -0.02 | 0.38 → 0.38 |
| `006_mustard_bottle` | `shelving_145` → `kitchen cabinet_306` | unknown → kitchen | **⬇ F2 → F1** | 8.53 | -2.85 | 0.38 → 0.75 |
| `011_banana` | `kitchen counter_332` → `coffee table_229` | kitchen → living_room | F1 (+0.10 m) | 5.46 | -0.51 | 0.88 → 0.50 |
| `019_pitcher_base` | `kitchen cabinet_292` → `kitchen counter_332` | kitchen | F1 (+0.10 m) | 2.33 | -0.01 | 0.88 → 0.88 |
| `024_bowl` | `cabinet_263` → `kitchen cabinet_299` | living_room → kitchen | F1 (+0.10 m) | 7.75 | 0.18 | 0.50 → 0.75 |
| `072-a_toy_airplane` | `sideboard_39` → `chest of drawers_476` | bedroom | **⬇ F2 → F1** | 7.31 | -3.14 | 0.88 → 0.88 |

## 00810-CrMo8WxCyVb

**single floor** · 8 targets · 3 layouts · seed 20260828 · 8 distinct surfaces · mean semantic correspondence 0.83 · mean cross-anchor move 3.97 m · 0 cross-floor relocation(s)

| Floor | Height (m) | Navmesh share | Used by this dataset |
|---|---|---|---|
| F0 | -1.34 | 96% | yes |

### 00810-CrMo8WxCyVb — Static layout

**8 objects** · mean semantic corr. 0.81 · min 0.50 · 8 distinct surfaces

![00810-CrMo8WxCyVb static objects](../../outputs/dualmap_authoring/00810-CrMo8WxCyVb/renders/static_objects.png)

![00810-CrMo8WxCyVb static top-down](../../outputs/dualmap_authoring/00810-CrMo8WxCyVb/renders/static_topdown.png)

| Target | Surface | Category | Room | Floor | y (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `kitchen cabinet_389` | kitchen cabinet | kitchen | F0 (-1.34 m) | -2.01 | 0.88 |
| `003_cracker_box` | `cabinet_393` | cabinet | kitchen | F0 (-1.34 m) | -1.96 | 0.88 |
| `005_tomato_soup_can` | `table_333` | table | living_room | F0 (-1.34 m) | -2.45 | 0.50 |
| `006_mustard_bottle` | `table_390` | table | kitchen | F0 (-1.34 m) | -1.98 | 0.88 |
| `011_banana` | `table_376` | table | kitchen | F0 (-1.34 m) | -2.06 | 0.75 |
| `019_pitcher_base` | `kitchen cabinet_363` | kitchen cabinet | kitchen | F0 (-1.34 m) | -1.95 | 0.88 |
| `024_bowl` | `table_377` | table | kitchen | F0 (-1.34 m) | -2.05 | 0.88 |
| `072-a_toy_airplane` | `cabinet_67` | cabinet | bedroom | F0 (-1.34 m) | 0.91 | 0.88 |

### 00810-CrMo8WxCyVb — In-anchor layout 01

**8 objects** · mean move 0.22 m · median 0.21 m · max 0.47 m · mean \|Δz\| 0.00 m · mean semantic corr. 0.81 · min 0.50 · 8 distinct surfaces

![00810-CrMo8WxCyVb in_anchor_01 objects](../../outputs/dualmap_authoring/00810-CrMo8WxCyVb/renders/in_anchor_01_objects.png)

![00810-CrMo8WxCyVb in_anchor_01 top-down](../../outputs/dualmap_authoring/00810-CrMo8WxCyVb/renders/in_anchor_01_topdown.png)

| Target | Surface | Δ move (m) | Δ horizontal (m) | Δz (m) | Floor |
|---|---|---|---|---|---|
| `002_master_chef_can` | `kitchen cabinet_389` | 0.25 | 0.25 | 0.00 | F0 (-1.34 m) |
| `003_cracker_box` | `cabinet_393` | 0.34 | 0.34 | 0.00 | F0 (-1.34 m) |
| `005_tomato_soup_can` | `table_333` | 0.06 | 0.06 | -0.00 | F0 (-1.34 m) |
| `006_mustard_bottle` | `table_390` | 0.24 | 0.24 | 0.00 | F0 (-1.34 m) |
| `011_banana` | `table_376` | 0.47 | 0.47 | 0.00 | F0 (-1.34 m) |
| `019_pitcher_base` | `kitchen cabinet_363` | 0.10 | 0.10 | 0.00 | F0 (-1.34 m) |
| `024_bowl` | `table_377` | 0.19 | 0.19 | 0.00 | F0 (-1.34 m) |
| `072-a_toy_airplane` | `cabinet_67` | 0.12 | 0.12 | -0.01 | F0 (-1.34 m) |

### 00810-CrMo8WxCyVb — Cross-anchor layout 01

**8 objects** · mean move 3.97 m · median 2.91 m · max 8.77 m · mean \|Δz\| 0.47 m · mean semantic corr. 0.86 · min 0.75 · 8 distinct surfaces

![00810-CrMo8WxCyVb cross_anchor_01 objects](../../outputs/dualmap_authoring/00810-CrMo8WxCyVb/renders/cross_anchor_01_objects.png)

![00810-CrMo8WxCyVb cross_anchor_01 top-down](../../outputs/dualmap_authoring/00810-CrMo8WxCyVb/renders/cross_anchor_01_topdown.png)

| Target | Surface: from → to | Room | Floor | Δ move (m) | Δz (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `kitchen cabinet_389` → `table_376` | kitchen | F0 (-1.34 m) | 1.85 | 0.00 | 0.88 → 0.75 |
| `003_cracker_box` | `cabinet_393` → `kitchen cabinet_389` | kitchen | F0 (-1.34 m) | 2.43 | -0.01 | 0.88 → 0.88 |
| `005_tomato_soup_can` | `table_333` → `table_377` | living_room → kitchen | F0 (-1.34 m) | 8.77 | 0.42 | 0.50 → 0.88 |
| `006_mustard_bottle` | `table_390` → `kitchen cabinet_364` | kitchen | F0 (-1.34 m) | 1.76 | 0.00 | 0.88 → 0.75 |
| `011_banana` | `table_376` → `table_390` | kitchen | F0 (-1.34 m) | 2.01 | -0.00 | 0.75 → 0.88 |
| `019_pitcher_base` | `kitchen cabinet_363` → `cabinet_393` | kitchen | F0 (-1.34 m) | 4.15 | 0.01 | 0.88 → 0.88 |
| `024_bowl` | `table_377` → `kitchen cabinet_363` | kitchen | F0 (-1.34 m) | 3.39 | -0.00 | 0.88 → 0.88 |
| `072-a_toy_airplane` | `cabinet_67` → `table_333` | bedroom → living_room | F0 (-1.34 m) | 7.40 | -3.32 | 0.88 → 1.00 |

## 00814-p53SfW6mjZe

**single floor** · 7 targets · 3 layouts · seed 20260828 · 7 distinct surfaces · mean semantic correspondence 0.85 · mean cross-anchor move 8.98 m · 0 cross-floor relocation(s)

| Floor | Height (m) | Navmesh share | Used by this dataset |
|---|---|---|---|
| F0 | -2.96 | 20% | no |
| F1 | +0.07 | 36% | yes |
| F2 | +3.13 | 37% | no |

### 00814-p53SfW6mjZe — Static layout

**7 objects** · mean semantic corr. 0.84 · min 0.50 · 7 distinct surfaces

![00814-p53SfW6mjZe static objects](../../outputs/dualmap_authoring/00814-p53SfW6mjZe/renders/static_objects.png)

![00814-p53SfW6mjZe static top-down](../../outputs/dualmap_authoring/00814-p53SfW6mjZe/renders/static_topdown.png)

| Target | Surface | Category | Room | Floor | y (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `kitchen cabinet_334` | kitchen cabinet | kitchen | F1 (+0.07 m) | 1.03 | 0.88 |
| `003_cracker_box` | `cabinet_312` | cabinet | kitchen | F1 (+0.07 m) | 1.07 | 0.88 |
| `005_tomato_soup_can` | `cabinet_244` | cabinet | kitchen | F1 (+0.07 m) | 0.99 | 0.75 |
| `006_mustard_bottle` | `table_449` | table | living_room | F1 (+0.07 m) | 0.64 | 0.50 |
| `019_pitcher_base` | `kitchen cabinet_335` | kitchen cabinet | kitchen | F1 (+0.07 m) | 1.08 | 0.88 |
| `024_bowl` | `kitchen counter_363` | kitchen counter | kitchen | F1 (+0.07 m) | 0.99 | 1.00 |
| `072-a_toy_airplane` | `desk_178` | desk | bedroom | F1 (+0.07 m) | 0.90 | 1.00 |

### 00814-p53SfW6mjZe — In-anchor layout 01

**7 objects** · mean move 0.46 m · median 0.28 m · max 1.27 m · mean \|Δz\| 0.00 m · mean semantic corr. 0.84 · min 0.50 · 7 distinct surfaces

![00814-p53SfW6mjZe in_anchor_01 objects](../../outputs/dualmap_authoring/00814-p53SfW6mjZe/renders/in_anchor_01_objects.png)

![00814-p53SfW6mjZe in_anchor_01 top-down](../../outputs/dualmap_authoring/00814-p53SfW6mjZe/renders/in_anchor_01_topdown.png)

| Target | Surface | Δ move (m) | Δ horizontal (m) | Δz (m) | Floor |
|---|---|---|---|---|---|
| `002_master_chef_can` | `kitchen cabinet_334` | 0.13 | 0.13 | -0.00 | F1 (+0.07 m) |
| `003_cracker_box` | `cabinet_312` | 0.31 | 0.31 | 0.00 | F1 (+0.07 m) |
| `005_tomato_soup_can` | `cabinet_244` | 1.27 | 1.27 | 0.00 | F1 (+0.07 m) |
| `006_mustard_bottle` | `table_449` | 0.20 | 0.20 | -0.00 | F1 (+0.07 m) |
| `019_pitcher_base` | `kitchen cabinet_335` | 0.15 | 0.15 | -0.00 | F1 (+0.07 m) |
| `024_bowl` | `kitchen counter_363` | 0.91 | 0.91 | 0.00 | F1 (+0.07 m) |
| `072-a_toy_airplane` | `desk_178` | 0.28 | 0.28 | -0.00 | F1 (+0.07 m) |

### 00814-p53SfW6mjZe — Cross-anchor layout 01

**7 objects** · mean move 8.98 m · median 9.49 m · max 19.51 m · mean \|Δz\| 0.10 m · mean semantic corr. 0.88 · min 0.75 · 7 distinct surfaces

![00814-p53SfW6mjZe cross_anchor_01 objects](../../outputs/dualmap_authoring/00814-p53SfW6mjZe/renders/cross_anchor_01_objects.png)

![00814-p53SfW6mjZe cross_anchor_01 top-down](../../outputs/dualmap_authoring/00814-p53SfW6mjZe/renders/cross_anchor_01_topdown.png)

| Target | Surface: from → to | Room | Floor | Δ move (m) | Δz (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `kitchen cabinet_334` → `kitchen lower cabinet_343` | kitchen | F1 (+0.07 m) | 4.09 | -0.00 | 0.88 → 0.75 |
| `003_cracker_box` | `cabinet_312` → `kitchen counter_363` | kitchen | F1 (+0.07 m) | 3.64 | 0.00 | 0.88 → 1.00 |
| `005_tomato_soup_can` | `cabinet_244` → `cabinet_312` | kitchen | F1 (+0.07 m) | 9.49 | 0.02 | 0.75 → 0.88 |
| `006_mustard_bottle` | `table_449` → `kitchen cabinet_334` | living_room → kitchen | F1 (+0.07 m) | 10.65 | 0.41 | 0.50 → 0.88 |
| `019_pitcher_base` | `kitchen cabinet_335` → `cabinet_244` | kitchen | F1 (+0.07 m) | 11.90 | -0.02 | 0.88 → 0.75 |
| `024_bowl` | `kitchen counter_363` → `kitchen cabinet_335` | kitchen | F1 (+0.07 m) | 3.56 | -0.01 | 1.00 → 0.88 |
| `072-a_toy_airplane` | `desk_178` → `table_449` | bedroom → living_room | F1 (+0.07 m) | 19.51 | -0.26 | 1.00 → 1.00 |

## 00821-eF36g7L6Z9M

**multifloor** · 8 targets · 3 layouts · seed 20260828 · 8 distinct surfaces · mean semantic correspondence 0.74 · mean cross-anchor move 6.29 m · 2 cross-floor relocation(s)

| Floor | Height (m) | Navmesh share | Used by this dataset |
|---|---|---|---|
| F0 | -3.42 | 35% | yes |
| F1 | +0.17 | 61% | yes |

### 00821-eF36g7L6Z9M — Static layout

**8 objects** · mean semantic corr. 0.72 · min 0.38 · 8 distinct surfaces

![00821-eF36g7L6Z9M static objects](../../outputs/dualmap_authoring/00821-eF36g7L6Z9M/renders/static_objects.png)

![00821-eF36g7L6Z9M static top-down](../../outputs/dualmap_authoring/00821-eF36g7L6Z9M/renders/static_topdown_f0.png)

![00821-eF36g7L6Z9M static top-down](../../outputs/dualmap_authoring/00821-eF36g7L6Z9M/renders/static_topdown_f1.png)

| Target | Surface | Category | Room | Floor | y (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `kitchen cabinet_86` | kitchen cabinet | kitchen | F1 (+0.17 m) | 1.07 | 0.88 |
| `003_cracker_box` | `kitchen cabinet_619` | kitchen cabinet | living_room | F0 (-3.42 m) | -2.45 | 0.50 |
| `005_tomato_soup_can` | `table_348` | table | unknown | F1 (+0.17 m) | 0.89 | 0.38 |
| `006_mustard_bottle` | `table_654` | table | living_room | F0 (-3.42 m) | -2.97 | 0.50 |
| `011_banana` | `coffee table_223` | coffee table | kitchen | F1 (+0.17 m) | 0.64 | 0.75 |
| `019_pitcher_base` | `kitchen cabinet lower_137` | kitchen cabinet lower | kitchen | F1 (+0.17 m) | 1.09 | 0.88 |
| `024_bowl` | `kitchen cabinet_85` | kitchen cabinet | kitchen | F1 (+0.17 m) | 1.01 | 0.88 |
| `072-a_toy_airplane` | `side table_288` | side table | living_room | F1 (+0.17 m) | 0.66 | 1.00 |

### 00821-eF36g7L6Z9M — In-anchor layout 01

**8 objects** · mean move 0.22 m · median 0.17 m · max 0.67 m · mean \|Δz\| 0.00 m · mean semantic corr. 0.72 · min 0.38 · 8 distinct surfaces

![00821-eF36g7L6Z9M in_anchor_01 objects](../../outputs/dualmap_authoring/00821-eF36g7L6Z9M/renders/in_anchor_01_objects.png)

![00821-eF36g7L6Z9M in_anchor_01 top-down](../../outputs/dualmap_authoring/00821-eF36g7L6Z9M/renders/in_anchor_01_topdown_f0.png)

![00821-eF36g7L6Z9M in_anchor_01 top-down](../../outputs/dualmap_authoring/00821-eF36g7L6Z9M/renders/in_anchor_01_topdown_f1.png)

| Target | Surface | Δ move (m) | Δ horizontal (m) | Δz (m) | Floor |
|---|---|---|---|---|---|
| `002_master_chef_can` | `kitchen cabinet_86` | 0.15 | 0.15 | -0.01 | F1 (+0.17 m) |
| `003_cracker_box` | `kitchen cabinet_619` | 0.67 | 0.67 | -0.01 | F0 (-3.42 m) |
| `005_tomato_soup_can` | `table_348` | 0.21 | 0.21 | 0.00 | F1 (+0.17 m) |
| `006_mustard_bottle` | `table_654` | 0.20 | 0.20 | -0.00 | F0 (-3.42 m) |
| `011_banana` | `coffee table_223` | 0.10 | 0.10 | -0.00 | F1 (+0.17 m) |
| `019_pitcher_base` | `kitchen cabinet lower_137` | 0.10 | 0.10 | 0.00 | F1 (+0.17 m) |
| `024_bowl` | `kitchen cabinet_85` | 0.10 | 0.10 | 0.00 | F1 (+0.17 m) |
| `072-a_toy_airplane` | `side table_288` | 0.19 | 0.19 | -0.00 | F1 (+0.17 m) |

### 00821-eF36g7L6Z9M — Cross-anchor layout 01

**8 objects** · mean move 6.29 m · median 5.20 m · max 16.01 m · mean \|Δz\| 0.99 m · mean semantic corr. 0.80 · min 0.50 · 8 distinct surfaces · **2 floor change(s):** `003_cracker_box` F0→F1 (Δz +3.53 m), `072-a_toy_airplane` F1→F0 (Δz -3.63 m)

![00821-eF36g7L6Z9M cross_anchor_01 objects](../../outputs/dualmap_authoring/00821-eF36g7L6Z9M/renders/cross_anchor_01_objects.png)

![00821-eF36g7L6Z9M cross_anchor_01 top-down](../../outputs/dualmap_authoring/00821-eF36g7L6Z9M/renders/cross_anchor_01_topdown_f0.png)

![00821-eF36g7L6Z9M cross_anchor_01 top-down](../../outputs/dualmap_authoring/00821-eF36g7L6Z9M/renders/cross_anchor_01_topdown_f1.png)

| Target | Surface: from → to | Room | Floor | Δ move (m) | Δz (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `kitchen cabinet_86` → `kitchen cabinet lower_96` | kitchen | F1 (+0.17 m) | 3.14 | -0.03 | 0.88 → 0.88 |
| `003_cracker_box` | `kitchen cabinet_619` → `kitchen cabinet lower_97` | living_room → kitchen | **⬆ F0 → F1** | 7.27 | 3.53 | 0.50 → 0.88 |
| `005_tomato_soup_can` | `table_348` → `kitchen cabinet_85` | unknown → kitchen | F1 (+0.17 m) | 16.01 | 0.14 | 0.38 → 0.88 |
| `006_mustard_bottle` | `table_654` → `kitchen cabinet_619` | living_room | F0 (-3.42 m) | 5.63 | 0.51 | 0.50 → 0.50 |
| `011_banana` | `coffee table_223` → `side table_305` | kitchen → living_room | F1 (+0.17 m) | 6.12 | -0.07 | 0.75 → 0.50 |
| `019_pitcher_base` | `kitchen cabinet lower_137` → `kitchen cabinet_86` | kitchen | F1 (+0.17 m) | 4.77 | 0.02 | 0.88 → 0.88 |
| `024_bowl` | `kitchen cabinet_85` → `kitchen cabinet lower_137` | kitchen | F1 (+0.17 m) | 2.89 | -0.00 | 0.88 → 0.88 |
| `072-a_toy_airplane` | `side table_288` → `table_654` | living_room | **⬇ F1 → F0** | 4.51 | -3.63 | 1.00 → 1.00 |

## 00823-7MXmsvcQjpJ

**single floor** · 7 targets · 3 layouts · seed 20260828 · 7 distinct surfaces · mean semantic correspondence 0.81 · mean cross-anchor move 2.98 m · 0 cross-floor relocation(s)

| Floor | Height (m) | Navmesh share | Used by this dataset |
|---|---|---|---|
| F0 | -1.97 | 41% | yes |
| F1 | +1.52 | 32% | no |
| F2 | +4.63 | 17% | no |

### 00823-7MXmsvcQjpJ — Static layout

**7 objects** · mean semantic corr. 0.75 · min 0.25 · 7 distinct surfaces

![00823-7MXmsvcQjpJ static objects](../../outputs/dualmap_authoring/00823-7MXmsvcQjpJ/renders/static_objects.png)

![00823-7MXmsvcQjpJ static top-down](../../outputs/dualmap_authoring/00823-7MXmsvcQjpJ/renders/static_topdown.png)

| Target | Surface | Category | Room | Floor | y (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `003_cracker_box` | `cabinet_1157` | cabinet | office | F0 (-1.97 m) | -1.12 | 0.50 |
| `005_tomato_soup_can` | `kitchen counter_936` | kitchen counter | kitchen | F0 (-1.97 m) | -0.98 | 1.00 |
| `006_mustard_bottle` | `cabinet_1659` | cabinet | unknown | F0 (-1.97 m) | -1.40 | 0.25 |
| `011_banana` | `table_983` | table | living_room | F0 (-1.97 m) | -1.59 | 0.50 |
| `019_pitcher_base` | `kitchen counter_880` | kitchen counter | kitchen | F0 (-1.97 m) | -1.08 | 1.00 |
| `024_bowl` | `dining table_893` | dining table | kitchen | F0 (-1.97 m) | -1.31 | 1.00 |
| `072-a_toy_airplane` | `table_984` | table | living_room | F0 (-1.97 m) | -1.52 | 1.00 |

### 00823-7MXmsvcQjpJ — In-anchor layout 01

**7 objects** · mean move 0.13 m · median 0.12 m · max 0.24 m · mean \|Δz\| 0.00 m · mean semantic corr. 0.75 · min 0.25 · 7 distinct surfaces

![00823-7MXmsvcQjpJ in_anchor_01 objects](../../outputs/dualmap_authoring/00823-7MXmsvcQjpJ/renders/in_anchor_01_objects.png)

![00823-7MXmsvcQjpJ in_anchor_01 top-down](../../outputs/dualmap_authoring/00823-7MXmsvcQjpJ/renders/in_anchor_01_topdown.png)

| Target | Surface | Δ move (m) | Δ horizontal (m) | Δz (m) | Floor |
|---|---|---|---|---|---|
| `003_cracker_box` | `cabinet_1157` | 0.07 | 0.06 | 0.02 | F0 (-1.97 m) |
| `005_tomato_soup_can` | `kitchen counter_936` | 0.18 | 0.18 | 0.00 | F0 (-1.97 m) |
| `006_mustard_bottle` | `cabinet_1659` | 0.00 | 0.00 | -0.00 | F0 (-1.97 m) |
| `011_banana` | `table_983` | 0.11 | 0.11 | -0.00 | F0 (-1.97 m) |
| `019_pitcher_base` | `kitchen counter_880` | 0.21 | 0.21 | -0.00 | F0 (-1.97 m) |
| `024_bowl` | `dining table_893` | 0.24 | 0.24 | 0.00 | F0 (-1.97 m) |
| `072-a_toy_airplane` | `table_984` | 0.12 | 0.12 | 0.00 | F0 (-1.97 m) |

### 00823-7MXmsvcQjpJ — Cross-anchor layout 01

**7 objects** · mean move 2.98 m · median 1.72 m · max 8.49 m · mean \|Δz\| 0.12 m · mean semantic corr. 0.93 · min 0.50 · 5 distinct surfaces

![00823-7MXmsvcQjpJ cross_anchor_01 objects](../../outputs/dualmap_authoring/00823-7MXmsvcQjpJ/renders/cross_anchor_01_objects.png)

![00823-7MXmsvcQjpJ cross_anchor_01 top-down](../../outputs/dualmap_authoring/00823-7MXmsvcQjpJ/renders/cross_anchor_01_topdown.png)

| Target | Surface: from → to | Room | Floor | Δ move (m) | Δz (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `003_cracker_box` | `cabinet_1157` → `kitchen counter_880` | office → kitchen | F0 (-1.97 m) | 5.82 | 0.03 | 0.50 → 1.00 |
| `005_tomato_soup_can` | `kitchen counter_936` → `kitchen counter_880` | kitchen | F0 (-1.97 m) | 2.00 | -0.17 | 1.00 → 1.00 |
| `006_mustard_bottle` | `cabinet_1659` → `dining table_893` | unknown → kitchen | F0 (-1.97 m) | 8.49 | 0.15 | 0.25 → 1.00 |
| `011_banana` | `table_983` → `table_984` | living_room | F0 (-1.97 m) | 0.80 | -0.01 | 0.50 → 0.50 |
| `019_pitcher_base` | `kitchen counter_880` → `dining table_893` | kitchen | F0 (-1.97 m) | 1.20 | -0.14 | 1.00 → 1.00 |
| `024_bowl` | `dining table_893` → `kitchen counter_936` | kitchen | F0 (-1.97 m) | 1.72 | 0.31 | 1.00 → 1.00 |
| `072-a_toy_airplane` | `table_984` → `table_983` | living_room | F0 (-1.97 m) | 0.85 | 0.01 | 1.00 → 1.00 |

## 00824-Dd4bFSTQ8gi

**single floor** · 7 targets · 3 layouts · seed 20260828 · 5 distinct surfaces · mean semantic correspondence 0.85 · mean cross-anchor move 5.95 m · 0 cross-floor relocation(s)

| Floor | Height (m) | Navmesh share | Used by this dataset |
|---|---|---|---|
| F0 | +0.06 | 99% | yes |

### 00824-Dd4bFSTQ8gi — Static layout

**7 objects** · mean semantic corr. 0.82 · min 0.50 · 5 distinct surfaces

![00824-Dd4bFSTQ8gi static objects](../../outputs/dualmap_authoring/00824-Dd4bFSTQ8gi/renders/static_objects.png)

![00824-Dd4bFSTQ8gi static top-down](../../outputs/dualmap_authoring/00824-Dd4bFSTQ8gi/renders/static_topdown.png)

| Target | Surface | Category | Room | Floor | y (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `kitchen lower cabinet_186` | kitchen lower cabinet | kitchen | F0 (+0.06 m) | 1.04 | 0.88 |
| `003_cracker_box` | `table_172` | table | kitchen | F0 (+0.06 m) | 0.94 | 0.88 |
| `005_tomato_soup_can` | `kitchen lower cabinet_184` | kitchen lower cabinet | kitchen | F0 (+0.06 m) | 1.02 | 0.88 |
| `006_mustard_bottle` | `kitchen lower cabinet_186` | kitchen lower cabinet | kitchen | F0 (+0.06 m) | 1.07 | 0.88 |
| `019_pitcher_base` | `table_33` | table | living_room | F0 (+0.06 m) | 0.50 | 0.50 |
| `024_bowl` | `kitchen lower cabinet_184` | kitchen lower cabinet | kitchen | F0 (+0.06 m) | 0.96 | 0.88 |
| `072-a_toy_airplane` | `cabinet_338` | cabinet | bedroom | F0 (+0.06 m) | 0.93 | 0.88 |

### 00824-Dd4bFSTQ8gi — In-anchor layout 01

**7 objects** · mean move 0.28 m · median 0.19 m · max 0.56 m · mean \|Δz\| 0.01 m · mean semantic corr. 0.82 · min 0.50 · 5 distinct surfaces

![00824-Dd4bFSTQ8gi in_anchor_01 objects](../../outputs/dualmap_authoring/00824-Dd4bFSTQ8gi/renders/in_anchor_01_objects.png)

![00824-Dd4bFSTQ8gi in_anchor_01 top-down](../../outputs/dualmap_authoring/00824-Dd4bFSTQ8gi/renders/in_anchor_01_topdown.png)

| Target | Surface | Δ move (m) | Δ horizontal (m) | Δz (m) | Floor |
|---|---|---|---|---|---|
| `002_master_chef_can` | `kitchen lower cabinet_186` | 0.56 | 0.56 | 0.02 | F0 (+0.06 m) |
| `003_cracker_box` | `table_172` | 0.16 | 0.15 | 0.01 | F0 (+0.06 m) |
| `005_tomato_soup_can` | `kitchen lower cabinet_184` | 0.19 | 0.19 | 0.00 | F0 (+0.06 m) |
| `006_mustard_bottle` | `kitchen lower cabinet_186` | 0.41 | 0.41 | -0.01 | F0 (+0.06 m) |
| `019_pitcher_base` | `table_33` | 0.04 | 0.04 | 0.00 | F0 (+0.06 m) |
| `024_bowl` | `kitchen lower cabinet_184` | 0.54 | 0.54 | 0.04 | F0 (+0.06 m) |
| `072-a_toy_airplane` | `cabinet_338` | 0.08 | 0.08 | 0.01 | F0 (+0.06 m) |

### 00824-Dd4bFSTQ8gi — Cross-anchor layout 01

**7 objects** · mean move 5.95 m · median 4.93 m · max 15.71 m · mean \|Δz\| 0.22 m · mean semantic corr. 0.89 · min 0.88 · 5 distinct surfaces

![00824-Dd4bFSTQ8gi cross_anchor_01 objects](../../outputs/dualmap_authoring/00824-Dd4bFSTQ8gi/renders/cross_anchor_01_objects.png)

![00824-Dd4bFSTQ8gi cross_anchor_01 top-down](../../outputs/dualmap_authoring/00824-Dd4bFSTQ8gi/renders/cross_anchor_01_topdown.png)

| Target | Surface: from → to | Room | Floor | Δ move (m) | Δz (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `kitchen lower cabinet_186` → `kitchen lower cabinet_197` | kitchen | F0 (+0.06 m) | 2.59 | 0.00 | 0.88 → 0.88 |
| `003_cracker_box` | `table_172` → `kitchen lower cabinet_184` | kitchen | F0 (+0.06 m) | 6.22 | 0.14 | 0.88 → 0.88 |
| `005_tomato_soup_can` | `kitchen lower cabinet_184` → `table_172` | kitchen | F0 (+0.06 m) | 6.42 | -0.14 | 0.88 → 0.88 |
| `006_mustard_bottle` | `kitchen lower cabinet_186` → `table_172` | kitchen | F0 (+0.06 m) | 3.36 | -0.14 | 0.88 → 0.88 |
| `019_pitcher_base` | `table_33` → `kitchen lower cabinet_184` | living_room → kitchen | F0 (+0.06 m) | 4.93 | 0.59 | 0.50 → 0.88 |
| `024_bowl` | `kitchen lower cabinet_184` → `kitchen lower cabinet_186` | kitchen | F0 (+0.06 m) | 2.43 | 0.06 | 0.88 → 0.88 |
| `072-a_toy_airplane` | `cabinet_338` → `table_33` | bedroom → living_room | F0 (+0.06 m) | 15.71 | -0.44 | 0.88 → 1.00 |

## 00848-ziup5kvtCCR

**single floor** · 7 targets · 3 layouts · seed 20260828 · 7 distinct surfaces · mean semantic correspondence 0.85 · mean cross-anchor move 3.84 m · 0 cross-floor relocation(s)

| Floor | Height (m) | Navmesh share | Used by this dataset |
|---|---|---|---|
| F0 | +0.06 | 98% | yes |

### 00848-ziup5kvtCCR — Static layout

**7 objects** · mean semantic corr. 0.82 · min 0.38 · 7 distinct surfaces

![00848-ziup5kvtCCR static objects](../../outputs/dualmap_authoring/00848-ziup5kvtCCR/renders/static_objects.png)

![00848-ziup5kvtCCR static top-down](../../outputs/dualmap_authoring/00848-ziup5kvtCCR/renders/static_topdown.png)

| Target | Surface | Category | Room | Floor | y (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `table_64` | table | kitchen | F0 (+0.06 m) | 0.89 | 0.88 |
| `003_cracker_box` | `kitchen cabinet_109` | kitchen cabinet | kitchen | F0 (+0.06 m) | 1.05 | 0.88 |
| `005_tomato_soup_can` | `cabinet_143` | cabinet | unknown | F0 (+0.06 m) | 0.85 | 0.38 |
| `006_mustard_bottle` | `sideboard_12` | sideboard | kitchen | F0 (+0.06 m) | 1.12 | 0.88 |
| `011_banana` | `kitchen counter_97` | kitchen counter | kitchen | F0 (+0.06 m) | 0.99 | 1.00 |
| `019_pitcher_base` | `kitchen counter_83` | kitchen counter | kitchen | F0 (+0.06 m) | 1.06 | 0.88 |
| `024_bowl` | `kitchen cabinet_85` | kitchen cabinet | kitchen | F0 (+0.06 m) | 0.97 | 0.88 |

### 00848-ziup5kvtCCR — In-anchor layout 01

**7 objects** · mean move 0.30 m · median 0.18 m · max 0.64 m · mean \|Δz\| 0.00 m · mean semantic corr. 0.82 · min 0.38 · 7 distinct surfaces

![00848-ziup5kvtCCR in_anchor_01 objects](../../outputs/dualmap_authoring/00848-ziup5kvtCCR/renders/in_anchor_01_objects.png)

![00848-ziup5kvtCCR in_anchor_01 top-down](../../outputs/dualmap_authoring/00848-ziup5kvtCCR/renders/in_anchor_01_topdown.png)

| Target | Surface | Δ move (m) | Δ horizontal (m) | Δz (m) | Floor |
|---|---|---|---|---|---|
| `002_master_chef_can` | `table_64` | 0.57 | 0.57 | 0.00 | F0 (+0.06 m) |
| `003_cracker_box` | `kitchen cabinet_109` | 0.18 | 0.18 | -0.00 | F0 (+0.06 m) |
| `005_tomato_soup_can` | `cabinet_143` | 0.12 | 0.12 | -0.00 | F0 (+0.06 m) |
| `006_mustard_bottle` | `sideboard_12` | 0.30 | 0.30 | 0.00 | F0 (+0.06 m) |
| `011_banana` | `kitchen counter_97` | 0.11 | 0.11 | -0.00 | F0 (+0.06 m) |
| `019_pitcher_base` | `kitchen counter_83` | 0.64 | 0.64 | -0.00 | F0 (+0.06 m) |
| `024_bowl` | `kitchen cabinet_85` | 0.18 | 0.18 | 0.00 | F0 (+0.06 m) |

### 00848-ziup5kvtCCR — Cross-anchor layout 01

**7 objects** · mean move 3.84 m · median 3.81 m · max 5.81 m · mean \|Δz\| 0.11 m · mean semantic corr. 0.89 · min 0.88 · 7 distinct surfaces

![00848-ziup5kvtCCR cross_anchor_01 objects](../../outputs/dualmap_authoring/00848-ziup5kvtCCR/renders/cross_anchor_01_objects.png)

![00848-ziup5kvtCCR cross_anchor_01 top-down](../../outputs/dualmap_authoring/00848-ziup5kvtCCR/renders/cross_anchor_01_topdown.png)

| Target | Surface: from → to | Room | Floor | Δ move (m) | Δz (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `table_64` → `kitchen cabinet_85` | kitchen | F0 (+0.06 m) | 2.37 | 0.13 | 0.88 → 0.88 |
| `003_cracker_box` | `kitchen cabinet_109` → `sideboard_12` | kitchen | F0 (+0.06 m) | 5.74 | 0.08 | 0.88 → 0.88 |
| `005_tomato_soup_can` | `cabinet_143` → `kitchen counter_97` | unknown → kitchen | F0 (+0.06 m) | 5.54 | 0.15 | 0.38 → 1.00 |
| `006_mustard_bottle` | `sideboard_12` → `kitchen counter_101` | kitchen | F0 (+0.06 m) | 5.81 | -0.08 | 0.88 → 0.88 |
| `011_banana` | `kitchen counter_97` → `kitchen counter_102` | kitchen | F0 (+0.06 m) | 2.94 | 0.17 | 1.00 → 0.88 |
| `019_pitcher_base` | `kitchen counter_83` → `table_64` | kitchen | F0 (+0.06 m) | 3.81 | -0.13 | 0.88 → 0.88 |
| `024_bowl` | `kitchen cabinet_85` → `kitchen counter_83` | kitchen | F0 (+0.06 m) | 0.70 | -0.00 | 0.88 → 0.88 |

## 00869-MHPLjHsuG27

**single floor** · 7 targets · 3 layouts · seed 20260828 · 7 distinct surfaces · mean semantic correspondence 0.68 · mean cross-anchor move 4.93 m · 0 cross-floor relocation(s)

| Floor | Height (m) | Navmesh share | Used by this dataset |
|---|---|---|---|
| F0 | -0.20 | 97% | yes |

### 00869-MHPLjHsuG27 — Static layout

**7 objects** · mean semantic corr. 0.66 · min 0.50 · 7 distinct surfaces

![00869-MHPLjHsuG27 static objects](../../outputs/dualmap_authoring/00869-MHPLjHsuG27/renders/static_objects.png)

![00869-MHPLjHsuG27 static top-down](../../outputs/dualmap_authoring/00869-MHPLjHsuG27/renders/static_topdown.png)

| Target | Surface | Category | Room | Floor | y (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `003_cracker_box` | `chest of drawers_31` | chest of drawers | living_room | F0 (-0.20 m) | -0.49 | 0.50 |
| `005_tomato_soup_can` | `side table_39` | side table | living_room | F0 (-0.20 m) | -0.84 | 0.50 |
| `006_mustard_bottle` | `kitchen shelf_130` | kitchen shelf | kitchen | F0 (-0.20 m) | 0.03 | 0.88 |
| `011_banana` | `side table_43` | side table | living_room | F0 (-0.20 m) | -0.80 | 0.50 |
| `019_pitcher_base` | `table_18` | table | living_room | F0 (-0.20 m) | -0.51 | 0.50 |
| `024_bowl` | `kitchen counter_99` | kitchen counter | kitchen | F0 (-0.20 m) | -0.48 | 0.88 |
| `072-a_toy_airplane` | `chest of drawers_529` | chest of drawers | bedroom | F0 (-0.20 m) | 2.57 | 0.88 |

### 00869-MHPLjHsuG27 — In-anchor layout 01

**7 objects** · mean move 0.29 m · median 0.13 m · max 1.36 m · mean \|Δz\| 0.02 m · mean semantic corr. 0.66 · min 0.50 · 7 distinct surfaces

![00869-MHPLjHsuG27 in_anchor_01 objects](../../outputs/dualmap_authoring/00869-MHPLjHsuG27/renders/in_anchor_01_objects.png)

![00869-MHPLjHsuG27 in_anchor_01 top-down](../../outputs/dualmap_authoring/00869-MHPLjHsuG27/renders/in_anchor_01_topdown.png)

| Target | Surface | Δ move (m) | Δ horizontal (m) | Δz (m) | Floor |
|---|---|---|---|---|---|
| `003_cracker_box` | `chest of drawers_31` | 0.11 | 0.09 | -0.06 | F0 (-0.20 m) |
| `005_tomato_soup_can` | `side table_39` | 0.07 | 0.07 | 0.00 | F0 (-0.20 m) |
| `006_mustard_bottle` | `kitchen shelf_130` | 0.06 | 0.06 | 0.02 | F0 (-0.20 m) |
| `011_banana` | `side table_43` | 0.15 | 0.14 | -0.02 | F0 (-0.20 m) |
| `019_pitcher_base` | `table_18` | 0.19 | 0.19 | -0.01 | F0 (-0.20 m) |
| `024_bowl` | `kitchen counter_99` | 1.36 | 1.36 | 0.00 | F0 (-0.20 m) |
| `072-a_toy_airplane` | `chest of drawers_529` | 0.13 | 0.13 | 0.00 | F0 (-0.20 m) |

### 00869-MHPLjHsuG27 — Cross-anchor layout 01

**7 objects** · mean move 4.93 m · median 4.63 m · max 7.69 m · mean \|Δz\| 0.71 m · mean semantic corr. 0.71 · min 0.50 · 6 distinct surfaces

![00869-MHPLjHsuG27 cross_anchor_01 objects](../../outputs/dualmap_authoring/00869-MHPLjHsuG27/renders/cross_anchor_01_objects.png)

![00869-MHPLjHsuG27 cross_anchor_01 top-down](../../outputs/dualmap_authoring/00869-MHPLjHsuG27/renders/cross_anchor_01_topdown.png)

| Target | Surface: from → to | Room | Floor | Δ move (m) | Δz (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `003_cracker_box` | `chest of drawers_31` → `side table_43` | living_room | F0 (-0.20 m) | 4.60 | -0.24 | 0.50 → 0.50 |
| `005_tomato_soup_can` | `side table_39` → `kitchen shelf_130` | living_room → kitchen | F0 (-0.20 m) | 7.69 | 0.84 | 0.50 → 0.88 |
| `006_mustard_bottle` | `kitchen shelf_130` → `kitchen counter_99` | kitchen | F0 (-0.20 m) | 1.87 | -0.44 | 0.88 → 0.88 |
| `011_banana` | `side table_43` → `side table_39` | living_room | F0 (-0.20 m) | 2.64 | -0.07 | 0.50 → 0.50 |
| `019_pitcher_base` | `table_18` → `kitchen counter_99` | living_room → kitchen | F0 (-0.20 m) | 6.62 | 0.13 | 0.50 → 0.88 |
| `024_bowl` | `kitchen counter_99` → `table_18` | kitchen → living_room | F0 (-0.20 m) | 6.46 | -0.13 | 0.88 → 0.50 |
| `072-a_toy_airplane` | `chest of drawers_529` → `chest of drawers_31` | bedroom → living_room | F0 (-0.20 m) | 4.63 | -3.13 | 0.88 → 0.88 |

## 00871-VBzV5z6i1WS

**single floor** · 7 targets · 3 layouts · seed 20260828 · 7 distinct surfaces · mean semantic correspondence 0.80 · mean cross-anchor move 4.33 m · 0 cross-floor relocation(s)

| Floor | Height (m) | Navmesh share | Used by this dataset |
|---|---|---|---|
| F0 | +0.07 | 100% | yes |

### 00871-VBzV5z6i1WS — Static layout

**7 objects** · mean semantic corr. 0.77 · min 0.50 · 7 distinct surfaces

![00871-VBzV5z6i1WS static objects](../../outputs/dualmap_authoring/00871-VBzV5z6i1WS/renders/static_objects.png)

![00871-VBzV5z6i1WS static top-down](../../outputs/dualmap_authoring/00871-VBzV5z6i1WS/renders/static_topdown.png)

| Target | Surface | Category | Room | Floor | y (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `kitchen cabinet_463` | kitchen cabinet | kitchen | F0 (+0.07 m) | 1.01 | 0.88 |
| `003_cracker_box` | `table_384` | table | kitchen | F0 (+0.07 m) | 0.88 | 0.88 |
| `005_tomato_soup_can` | `table_458` | table | kitchen | F0 (+0.07 m) | 0.83 | 0.88 |
| `006_mustard_bottle` | `display cabinet_568` | display cabinet | living_room | F0 (+0.07 m) | 1.39 | 0.50 |
| `019_pitcher_base` | `table_542` | table | living_room | F0 (+0.07 m) | 0.56 | 0.50 |
| `024_bowl` | `cabinet_471` | cabinet | kitchen | F0 (+0.07 m) | 0.99 | 0.88 |
| `072-a_toy_airplane` | `dresser_44` | dresser | bedroom | F0 (+0.07 m) | 1.18 | 0.88 |

### 00871-VBzV5z6i1WS — In-anchor layout 01

**7 objects** · mean move 0.18 m · median 0.14 m · max 0.38 m · mean \|Δz\| 0.01 m · mean semantic corr. 0.77 · min 0.50 · 7 distinct surfaces

![00871-VBzV5z6i1WS in_anchor_01 objects](../../outputs/dualmap_authoring/00871-VBzV5z6i1WS/renders/in_anchor_01_objects.png)

![00871-VBzV5z6i1WS in_anchor_01 top-down](../../outputs/dualmap_authoring/00871-VBzV5z6i1WS/renders/in_anchor_01_topdown.png)

| Target | Surface | Δ move (m) | Δ horizontal (m) | Δz (m) | Floor |
|---|---|---|---|---|---|
| `002_master_chef_can` | `kitchen cabinet_463` | 0.22 | 0.22 | 0.00 | F0 (+0.07 m) |
| `003_cracker_box` | `table_384` | 0.21 | 0.21 | -0.00 | F0 (+0.07 m) |
| `005_tomato_soup_can` | `table_458` | 0.14 | 0.14 | -0.00 | F0 (+0.07 m) |
| `006_mustard_bottle` | `display cabinet_568` | 0.08 | 0.08 | 0.01 | F0 (+0.07 m) |
| `019_pitcher_base` | `table_542` | 0.12 | 0.12 | -0.00 | F0 (+0.07 m) |
| `024_bowl` | `cabinet_471` | 0.38 | 0.38 | -0.02 | F0 (+0.07 m) |
| `072-a_toy_airplane` | `dresser_44` | 0.13 | 0.13 | -0.02 | F0 (+0.07 m) |

### 00871-VBzV5z6i1WS — Cross-anchor layout 01

**7 objects** · mean move 4.33 m · median 2.87 m · max 11.38 m · mean \|Δz\| 0.26 m · mean semantic corr. 0.86 · min 0.75 · 7 distinct surfaces

![00871-VBzV5z6i1WS cross_anchor_01 objects](../../outputs/dualmap_authoring/00871-VBzV5z6i1WS/renders/cross_anchor_01_objects.png)

![00871-VBzV5z6i1WS cross_anchor_01 top-down](../../outputs/dualmap_authoring/00871-VBzV5z6i1WS/renders/cross_anchor_01_topdown.png)

| Target | Surface: from → to | Room | Floor | Δ move (m) | Δz (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `kitchen cabinet_463` → `kitchen cabinet_411` | kitchen | F0 (+0.07 m) | 2.48 | -0.01 | 0.88 → 0.75 |
| `003_cracker_box` | `table_384` → `kitchen cabinet_463` | kitchen | F0 (+0.07 m) | 2.87 | 0.17 | 0.88 → 0.88 |
| `005_tomato_soup_can` | `table_458` → `cabinet_471` | kitchen | F0 (+0.07 m) | 2.27 | 0.16 | 0.88 → 0.88 |
| `006_mustard_bottle` | `display cabinet_568` → `table_459` | living_room → kitchen | F0 (+0.07 m) | 4.58 | -0.36 | 0.50 → 0.75 |
| `019_pitcher_base` | `table_542` → `table_384` | living_room → kitchen | F0 (+0.07 m) | 4.46 | 0.34 | 0.50 → 0.88 |
| `024_bowl` | `cabinet_471` → `table_458` | kitchen | F0 (+0.07 m) | 2.31 | -0.17 | 0.88 → 0.88 |
| `072-a_toy_airplane` | `dresser_44` → `table_542` | bedroom → living_room | F0 (+0.07 m) | 11.38 | -0.63 | 0.88 → 1.00 |

## 00873-bxsVRursffK

**multifloor** · 7 targets · 3 layouts · seed 20260828 · 7 distinct surfaces · mean semantic correspondence 0.84 · mean cross-anchor move 4.77 m · 2 cross-floor relocation(s)

| Floor | Height (m) | Navmesh share | Used by this dataset |
|---|---|---|---|
| F0 | -2.90 | 47% | yes |
| F1 | +0.09 | 48% | yes |

### 00873-bxsVRursffK — Static layout

**7 objects** · mean semantic corr. 0.84 · min 0.38 · 7 distinct surfaces

![00873-bxsVRursffK static objects](../../outputs/dualmap_authoring/00873-bxsVRursffK/renders/static_objects.png)

![00873-bxsVRursffK static top-down](../../outputs/dualmap_authoring/00873-bxsVRursffK/renders/static_topdown_f0.png)

![00873-bxsVRursffK static top-down](../../outputs/dualmap_authoring/00873-bxsVRursffK/renders/static_topdown_f1.png)

| Target | Surface | Category | Room | Floor | y (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `kitchen cabinet_391` | kitchen cabinet | kitchen | F0 (-2.90 m) | -2.02 | 0.88 |
| `003_cracker_box` | `table_133` | table | unknown | F1 (+0.09 m) | 0.71 | 0.38 |
| `005_tomato_soup_can` | `dining table_321` | dining table | kitchen | F0 (-2.90 m) | -2.20 | 1.00 |
| `006_mustard_bottle` | `kitchen counter_374` | kitchen counter | kitchen | F0 (-2.90 m) | -2.01 | 0.88 |
| `019_pitcher_base` | `kitchen island_364` | kitchen island | kitchen | F0 (-2.90 m) | -1.99 | 1.00 |
| `024_bowl` | `coffee table_331` | coffee table | kitchen | F0 (-2.90 m) | -2.52 | 0.88 |
| `072-a_toy_airplane` | `cabinet_71` | cabinet | bedroom | F1 (+0.09 m) | 1.25 | 0.88 |

### 00873-bxsVRursffK — In-anchor layout 01

**7 objects** · mean move 0.17 m · median 0.15 m · max 0.34 m · mean \|Δz\| 0.00 m · mean semantic corr. 0.84 · min 0.38 · 7 distinct surfaces

![00873-bxsVRursffK in_anchor_01 objects](../../outputs/dualmap_authoring/00873-bxsVRursffK/renders/in_anchor_01_objects.png)

![00873-bxsVRursffK in_anchor_01 top-down](../../outputs/dualmap_authoring/00873-bxsVRursffK/renders/in_anchor_01_topdown_f0.png)

![00873-bxsVRursffK in_anchor_01 top-down](../../outputs/dualmap_authoring/00873-bxsVRursffK/renders/in_anchor_01_topdown_f1.png)

| Target | Surface | Δ move (m) | Δ horizontal (m) | Δz (m) | Floor |
|---|---|---|---|---|---|
| `002_master_chef_can` | `kitchen cabinet_391` | 0.14 | 0.14 | 0.00 | F0 (-2.90 m) |
| `003_cracker_box` | `table_133` | 0.34 | 0.34 | -0.00 | F1 (+0.09 m) |
| `005_tomato_soup_can` | `dining table_321` | 0.18 | 0.18 | -0.00 | F0 (-2.90 m) |
| `006_mustard_bottle` | `kitchen counter_374` | 0.10 | 0.10 | -0.00 | F0 (-2.90 m) |
| `019_pitcher_base` | `kitchen island_364` | 0.17 | 0.17 | -0.00 | F0 (-2.90 m) |
| `024_bowl` | `coffee table_331` | 0.15 | 0.15 | -0.00 | F0 (-2.90 m) |
| `072-a_toy_airplane` | `cabinet_71` | 0.09 | 0.09 | -0.00 | F1 (+0.09 m) |

### 00873-bxsVRursffK — Cross-anchor layout 01

**7 objects** · mean move 4.77 m · median 3.58 m · max 9.22 m · mean \|Δz\| 0.95 m · mean semantic corr. 0.84 · min 0.38 · 7 distinct surfaces · **2 floor change(s):** `002_master_chef_can` F0→F1 (Δz +2.69 m), `003_cracker_box` F1→F0 (Δz -2.71 m)

![00873-bxsVRursffK cross_anchor_01 objects](../../outputs/dualmap_authoring/00873-bxsVRursffK/renders/cross_anchor_01_objects.png)

![00873-bxsVRursffK cross_anchor_01 top-down](../../outputs/dualmap_authoring/00873-bxsVRursffK/renders/cross_anchor_01_topdown_f0.png)

![00873-bxsVRursffK cross_anchor_01 top-down](../../outputs/dualmap_authoring/00873-bxsVRursffK/renders/cross_anchor_01_topdown_f1.png)

| Target | Surface: from → to | Room | Floor | Δ move (m) | Δz (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `kitchen cabinet_391` → `table_133` | kitchen → unknown | **⬆ F0 → F1** | 5.02 | 2.69 | 0.88 → 0.38 |
| `003_cracker_box` | `table_133` → `kitchen island_364` | unknown → kitchen | **⬇ F1 → F0** | 3.49 | -2.71 | 0.38 → 1.00 |
| `005_tomato_soup_can` | `dining table_321` → `coffee table_331` | kitchen | F0 (-2.90 m) | 3.18 | -0.30 | 1.00 → 0.88 |
| `006_mustard_bottle` | `kitchen counter_374` → `dining table_321` | kitchen | F0 (-2.90 m) | 6.87 | -0.15 | 0.88 → 1.00 |
| `019_pitcher_base` | `kitchen island_364` → `kitchen counter_374` | kitchen | F0 (-2.90 m) | 2.06 | 0.00 | 1.00 → 0.88 |
| `024_bowl` | `coffee table_331` → `kitchen cabinet_391` | kitchen | F0 (-2.90 m) | 3.58 | 0.46 | 0.88 → 0.88 |
| `072-a_toy_airplane` | `cabinet_71` → `cabinet_256` | bedroom | F1 (+0.09 m) | 9.22 | -0.32 | 0.88 → 0.88 |

## 00876-mv2HUxq3B53

**single floor** · 8 targets · 3 layouts · seed 20260828 · 8 distinct surfaces · mean semantic correspondence 0.71 · mean cross-anchor move 8.50 m · 0 cross-floor relocation(s)

| Floor | Height (m) | Navmesh share | Used by this dataset |
|---|---|---|---|
| F0 | +0.11 | 98% | yes |

### 00876-mv2HUxq3B53 — Static layout

**8 objects** · mean semantic corr. 0.62 · min 0.38 · 8 distinct surfaces

![00876-mv2HUxq3B53 static objects](../../outputs/dualmap_authoring/00876-mv2HUxq3B53/renders/static_objects.png)

![00876-mv2HUxq3B53 static top-down](../../outputs/dualmap_authoring/00876-mv2HUxq3B53/renders/static_topdown.png)

| Target | Surface | Category | Room | Floor | y (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `shelf_74` | shelf | kitchen | F0 (+0.11 m) | 1.18 | 0.88 |
| `003_cracker_box` | `shelf_70` | shelf | kitchen | F0 (+0.11 m) | 1.04 | 0.88 |
| `005_tomato_soup_can` | `shelf_501` | shelf | unknown | F0 (+0.11 m) | 1.00 | 0.38 |
| `006_mustard_bottle` | `table_499` | table | unknown | F0 (+0.11 m) | 0.58 | 0.38 |
| `011_banana` | `table_180` | table | kitchen | F0 (+0.11 m) | 0.81 | 0.88 |
| `019_pitcher_base` | `table_439` | table | unknown | F0 (+0.11 m) | 0.60 | 0.38 |
| `024_bowl` | `table_19` | table | unknown | F0 (+0.11 m) | 0.87 | 0.38 |
| `072-a_toy_airplane` | `cabinet_219` | cabinet | bedroom | F0 (+0.11 m) | 1.06 | 0.88 |

### 00876-mv2HUxq3B53 — In-anchor layout 01

**8 objects** · mean move 0.28 m · median 0.18 m · max 0.65 m · mean \|Δz\| 0.01 m · mean semantic corr. 0.62 · min 0.38 · 8 distinct surfaces

![00876-mv2HUxq3B53 in_anchor_01 objects](../../outputs/dualmap_authoring/00876-mv2HUxq3B53/renders/in_anchor_01_objects.png)

![00876-mv2HUxq3B53 in_anchor_01 top-down](../../outputs/dualmap_authoring/00876-mv2HUxq3B53/renders/in_anchor_01_topdown.png)

| Target | Surface | Δ move (m) | Δ horizontal (m) | Δz (m) | Floor |
|---|---|---|---|---|---|
| `002_master_chef_can` | `shelf_74` | 0.65 | 0.65 | 0.06 | F0 (+0.11 m) |
| `003_cracker_box` | `shelf_70` | 0.21 | 0.21 | -0.00 | F0 (+0.11 m) |
| `005_tomato_soup_can` | `shelf_501` | 0.53 | 0.53 | 0.00 | F0 (+0.11 m) |
| `006_mustard_bottle` | `table_499` | 0.10 | 0.10 | -0.00 | F0 (+0.11 m) |
| `011_banana` | `table_180` | 0.15 | 0.15 | -0.01 | F0 (+0.11 m) |
| `019_pitcher_base` | `table_439` | 0.13 | 0.13 | -0.00 | F0 (+0.11 m) |
| `024_bowl` | `table_19` | 0.16 | 0.16 | 0.00 | F0 (+0.11 m) |
| `072-a_toy_airplane` | `cabinet_219` | 0.32 | 0.32 | -0.01 | F0 (+0.11 m) |

### 00876-mv2HUxq3B53 — Cross-anchor layout 01

**8 objects** · mean move 8.50 m · median 7.88 m · max 14.93 m · mean \|Δz\| 0.16 m · mean semantic corr. 0.89 · min 0.88 · 8 distinct surfaces

![00876-mv2HUxq3B53 cross_anchor_01 objects](../../outputs/dualmap_authoring/00876-mv2HUxq3B53/renders/cross_anchor_01_objects.png)

![00876-mv2HUxq3B53 cross_anchor_01 top-down](../../outputs/dualmap_authoring/00876-mv2HUxq3B53/renders/cross_anchor_01_topdown.png)

| Target | Surface: from → to | Room | Floor | Δ move (m) | Δz (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `shelf_74` → `table_147` | kitchen | F0 (+0.11 m) | 5.66 | 0.03 | 0.88 → 0.88 |
| `003_cracker_box` | `shelf_70` → `shelf_125` | kitchen | F0 (+0.11 m) | 7.65 | 0.02 | 0.88 → 0.88 |
| `005_tomato_soup_can` | `shelf_501` → `shelf_70` | unknown → kitchen | F0 (+0.11 m) | 8.92 | -0.02 | 0.38 → 0.88 |
| `006_mustard_bottle` | `table_499` → `shelf_69` | unknown → kitchen | F0 (+0.11 m) | 13.23 | 0.45 | 0.38 → 0.88 |
| `011_banana` | `table_180` → `table_79` | kitchen | F0 (+0.11 m) | 7.46 | -0.00 | 0.88 → 0.88 |
| `019_pitcher_base` | `table_439` → `table_180` | unknown → kitchen | F0 (+0.11 m) | 8.11 | 0.30 | 0.38 → 0.88 |
| `024_bowl` | `table_19` → `shelf_74` | unknown → kitchen | F0 (+0.11 m) | 2.07 | 0.34 | 0.38 → 0.88 |
| `072-a_toy_airplane` | `cabinet_219` → `table_524` | bedroom | F0 (+0.11 m) | 14.93 | -0.11 | 0.88 → 1.00 |

## 00878-XB4GS9ShBRE

**multifloor** · 8 targets · 3 layouts · seed 3 · 8 distinct surfaces · mean semantic correspondence 0.66 · mean cross-anchor move 4.49 m · 3 cross-floor relocation(s)

| Floor | Height (m) | Navmesh share | Used by this dataset |
|---|---|---|---|
| F0 | -0.71 | 61% | yes |
| F1 | +2.73 | 31% | yes |

### 00878-XB4GS9ShBRE — Static layout

**8 objects** · mean semantic corr. 0.66 · min 0.25 · 8 distinct surfaces

![00878-XB4GS9ShBRE static objects](../../outputs/dualmap_authoring/00878-XB4GS9ShBRE/renders/static_objects.png)

![00878-XB4GS9ShBRE static top-down](../../outputs/dualmap_authoring/00878-XB4GS9ShBRE/renders/static_topdown_f0.png)

![00878-XB4GS9ShBRE static top-down](../../outputs/dualmap_authoring/00878-XB4GS9ShBRE/renders/static_topdown_f1.png)

| Target | Surface | Category | Room | Floor | y (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `cabinet_164` | cabinet | unknown | F1 (+2.73 m) | 4.17 | 0.25 |
| `003_cracker_box` | `cabinet_289` | cabinet | kitchen | F0 (-0.71 m) | 1.05 | 0.88 |
| `005_tomato_soup_can` | `table_385` | table | living_room | F0 (-0.71 m) | -2.35 | 0.50 |
| `006_mustard_bottle` | `table_252` | table | living_room | F0 (-0.71 m) | 0.90 | 0.50 |
| `011_banana` | `coffee table_228` | coffee table | living_room | F0 (-0.71 m) | 0.48 | 0.50 |
| `019_pitcher_base` | `cabinet_81` | cabinet | kitchen | F1 (+2.73 m) | 3.72 | 0.88 |
| `024_bowl` | `table_297` | table | kitchen | F0 (-0.71 m) | 0.84 | 0.88 |
| `072-a_toy_airplane` | `nightstand_136` | nightstand | bedroom | F1 (+2.73 m) | 3.54 | 0.88 |

### 00878-XB4GS9ShBRE — In-anchor layout 01

**8 objects** · mean move 0.22 m · median 0.20 m · max 0.54 m · mean \|Δz\| 0.00 m · mean semantic corr. 0.66 · min 0.25 · 8 distinct surfaces

![00878-XB4GS9ShBRE in_anchor_01 objects](../../outputs/dualmap_authoring/00878-XB4GS9ShBRE/renders/in_anchor_01_objects.png)

![00878-XB4GS9ShBRE in_anchor_01 top-down](../../outputs/dualmap_authoring/00878-XB4GS9ShBRE/renders/in_anchor_01_topdown_f0.png)

![00878-XB4GS9ShBRE in_anchor_01 top-down](../../outputs/dualmap_authoring/00878-XB4GS9ShBRE/renders/in_anchor_01_topdown_f1.png)

| Target | Surface | Δ move (m) | Δ horizontal (m) | Δz (m) | Floor |
|---|---|---|---|---|---|
| `002_master_chef_can` | `cabinet_164` | 0.18 | 0.18 | 0.00 | F1 (+2.73 m) |
| `003_cracker_box` | `cabinet_289` | 0.15 | 0.15 | -0.00 | F0 (-0.71 m) |
| `005_tomato_soup_can` | `table_385` | 0.26 | 0.26 | 0.01 | F0 (-0.71 m) |
| `006_mustard_bottle` | `table_252` | 0.27 | 0.27 | 0.00 | F0 (-0.71 m) |
| `011_banana` | `coffee table_228` | 0.12 | 0.12 | -0.00 | F0 (-0.71 m) |
| `019_pitcher_base` | `cabinet_81` | 0.54 | 0.54 | 0.00 | F1 (+2.73 m) |
| `024_bowl` | `table_297` | 0.07 | 0.07 | -0.00 | F0 (-0.71 m) |
| `072-a_toy_airplane` | `nightstand_136` | 0.22 | 0.22 | -0.02 | F1 (+2.73 m) |

### 00878-XB4GS9ShBRE — Cross-anchor layout 01

**8 objects** · mean move 4.49 m · median 4.55 m · max 6.74 m · mean \|Δz\| 2.09 m · mean semantic corr. 0.67 · min 0.25 · 8 distinct surfaces · **3 floor change(s):** `002_master_chef_can` F1→F0 (Δz -6.50 m), `005_tomato_soup_can` F0→F1 (Δz +6.01 m), `072-a_toy_airplane` F1→F0 (Δz -2.98 m)

![00878-XB4GS9ShBRE cross_anchor_01 objects](../../outputs/dualmap_authoring/00878-XB4GS9ShBRE/renders/cross_anchor_01_objects.png)

![00878-XB4GS9ShBRE cross_anchor_01 top-down](../../outputs/dualmap_authoring/00878-XB4GS9ShBRE/renders/cross_anchor_01_topdown_f0.png)

![00878-XB4GS9ShBRE cross_anchor_01 top-down](../../outputs/dualmap_authoring/00878-XB4GS9ShBRE/renders/cross_anchor_01_topdown_f1.png)

| Target | Surface: from → to | Room | Floor | Δ move (m) | Δz (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `cabinet_164` → `table_385` | unknown → living_room | **⬇ F1 → F0** | 6.71 | -6.50 | 0.25 → 0.50 |
| `003_cracker_box` | `cabinet_289` → `table_252` | kitchen → living_room | F0 (-0.71 m) | 4.71 | -0.14 | 0.88 → 0.50 |
| `005_tomato_soup_can` | `table_385` → `cabinet_81` | living_room → kitchen | **⬆ F0 → F1** | 6.74 | 6.01 | 0.50 → 0.88 |
| `006_mustard_bottle` | `table_252` → `cabinet_248` | living_room | F0 (-0.71 m) | 1.62 | 0.09 | 0.50 → 0.50 |
| `011_banana` | `coffee table_228` → `table_297` | living_room → kitchen | F0 (-0.71 m) | 4.38 | 0.35 | 0.50 → 0.88 |
| `019_pitcher_base` | `cabinet_81` → `cabinet_164` | kitchen → unknown | F1 (+2.73 m) | 4.36 | 0.50 | 0.88 → 0.25 |
| `024_bowl` | `table_297` → `cabinet_289` | kitchen | F0 (-0.71 m) | 2.41 | 0.13 | 0.88 → 0.88 |
| `072-a_toy_airplane` | `nightstand_136` → `coffee table_228` | bedroom → living_room | **⬇ F1 → F0** | 4.96 | -2.98 | 0.88 → 1.00 |

## 00891-cvZr5TUy5C5

**single floor** · 8 targets · 3 layouts · seed 20260828 · 8 distinct surfaces · mean semantic correspondence 0.72 · mean cross-anchor move 5.15 m · 0 cross-floor relocation(s)

| Floor | Height (m) | Navmesh share | Used by this dataset |
|---|---|---|---|
| F0 | -2.92 | 32% | no |
| F1 | +0.11 | 32% | yes |
| F2 | +3.12 | 29% | no |

### 00891-cvZr5TUy5C5 — Static layout

**8 objects** · mean semantic corr. 0.69 · min 0.38 · 8 distinct surfaces

![00891-cvZr5TUy5C5 static objects](../../outputs/dualmap_authoring/00891-cvZr5TUy5C5/renders/static_objects.png)

![00891-cvZr5TUy5C5 static top-down](../../outputs/dualmap_authoring/00891-cvZr5TUy5C5/renders/static_topdown.png)

| Target | Surface | Category | Room | Floor | y (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `cabinet_499` | cabinet | living_room | F1 (+0.11 m) | 1.06 | 0.50 |
| `003_cracker_box` | `cabinet_202` | cabinet | office | F1 (+0.11 m) | 0.91 | 0.50 |
| `005_tomato_soup_can` | `kitchen shelf_170` | kitchen shelf | kitchen | F1 (+0.11 m) | 1.00 | 0.88 |
| `006_mustard_bottle` | `table_87` | table | living_room | F1 (+0.11 m) | 0.82 | 0.38 |
| `011_banana` | `table_495` | table | living_room | F1 (+0.11 m) | 0.57 | 0.50 |
| `019_pitcher_base` | `kitchen shelf_131` | kitchen shelf | kitchen | F1 (+0.11 m) | 1.06 | 0.88 |
| `024_bowl` | `kitchen shelf_141` | kitchen shelf | kitchen | F1 (+0.11 m) | 0.97 | 0.88 |
| `072-a_toy_airplane` | `table_498` | table | living_room | F1 (+0.11 m) | 0.79 | 1.00 |

### 00891-cvZr5TUy5C5 — In-anchor layout 01

**8 objects** · mean move 0.18 m · median 0.16 m · max 0.30 m · mean \|Δz\| 0.00 m · mean semantic corr. 0.69 · min 0.38 · 8 distinct surfaces

![00891-cvZr5TUy5C5 in_anchor_01 objects](../../outputs/dualmap_authoring/00891-cvZr5TUy5C5/renders/in_anchor_01_objects.png)

![00891-cvZr5TUy5C5 in_anchor_01 top-down](../../outputs/dualmap_authoring/00891-cvZr5TUy5C5/renders/in_anchor_01_topdown.png)

| Target | Surface | Δ move (m) | Δ horizontal (m) | Δz (m) | Floor |
|---|---|---|---|---|---|
| `002_master_chef_can` | `cabinet_499` | 0.10 | 0.10 | 0.00 | F1 (+0.11 m) |
| `003_cracker_box` | `cabinet_202` | 0.29 | 0.29 | -0.00 | F1 (+0.11 m) |
| `005_tomato_soup_can` | `kitchen shelf_170` | 0.11 | 0.11 | -0.00 | F1 (+0.11 m) |
| `006_mustard_bottle` | `table_87` | 0.07 | 0.07 | -0.00 | F1 (+0.11 m) |
| `011_banana` | `table_495` | 0.30 | 0.30 | 0.00 | F1 (+0.11 m) |
| `019_pitcher_base` | `kitchen shelf_131` | 0.26 | 0.26 | -0.00 | F1 (+0.11 m) |
| `024_bowl` | `kitchen shelf_141` | 0.21 | 0.21 | -0.00 | F1 (+0.11 m) |
| `072-a_toy_airplane` | `table_498` | 0.11 | 0.11 | -0.00 | F1 (+0.11 m) |

### 00891-cvZr5TUy5C5 — Cross-anchor layout 01

**8 objects** · mean move 5.15 m · median 5.08 m · max 9.93 m · mean \|Δz\| 0.08 m · mean semantic corr. 0.80 · min 0.50 · 8 distinct surfaces

![00891-cvZr5TUy5C5 cross_anchor_01 objects](../../outputs/dualmap_authoring/00891-cvZr5TUy5C5/renders/cross_anchor_01_objects.png)

![00891-cvZr5TUy5C5 cross_anchor_01 top-down](../../outputs/dualmap_authoring/00891-cvZr5TUy5C5/renders/cross_anchor_01_topdown.png)

| Target | Surface: from → to | Room | Floor | Δ move (m) | Δz (m) | Semantic corr. |
|---|---|---|---|---|---|---|
| `002_master_chef_can` | `cabinet_499` → `kitchen shelf_141` | living_room → kitchen | F1 (+0.11 m) | 7.77 | -0.05 | 0.50 → 0.88 |
| `003_cracker_box` | `cabinet_202` → `kitchen shelf_129` | office → kitchen | F1 (+0.11 m) | 5.72 | 0.14 | 0.50 → 0.75 |
| `005_tomato_soup_can` | `kitchen shelf_170` → `kitchen shelf_131` | kitchen | F1 (+0.11 m) | 3.82 | -0.01 | 0.88 → 0.88 |
| `006_mustard_bottle` | `table_87` → `kitchen shelf_130` | living_room → kitchen | F1 (+0.11 m) | 5.11 | 0.22 | 0.38 → 0.75 |
| `011_banana` | `table_495` → `table_498` | living_room | F1 (+0.11 m) | 2.13 | 0.15 | 0.50 → 0.50 |
| `019_pitcher_base` | `kitchen shelf_131` → `kitchen shelf_166` | kitchen | F1 (+0.11 m) | 5.04 | 0.05 | 0.88 → 0.88 |
| `024_bowl` | `kitchen shelf_141` → `kitchen shelf_170` | kitchen | F1 (+0.11 m) | 1.70 | 0.00 | 0.88 → 0.88 |
| `072-a_toy_airplane` | `table_498` → `table_87` | living_room | F1 (+0.11 m) | 9.93 | 0.02 | 1.00 → 0.88 |
