# sci-arc-studio-fall2026

Work for the Syracuse Visiting Studio, Fall 2026 (Prof. David Ruy): **Angels Knoll / Bunker Hill Parcel Y-1**,
NW corner of 4th and Hill Streets, Downtown Los Angeles.

Live site: https://ruiw0211.github.io/sci-arc-studio-fall2026/

**Join the project:** [docs/SETUP.md](docs/SETUP.md) (install on macOS) and
[docs/WORKFLOW.md](docs/WORKFLOW.md) (branch → pull request → discuss → merge).

## What is here

| Folder | Contents |
|---|---|
| `web/` | The public website (GitHub Pages serves this folder). `viewer.html` is the site model viewer, `lidar_preview.html` the LiDAR viewer. |
| `web/research/` | The Y-1 research database: `data.json` holds every finding (sources, status, confidence); `index.html` searches and filters it. Link to one finding with `research/#<id>`. |
| `site-model/scripts/` | Data pipeline (Python) and Blender build scripts for the 3D site model. |
| `site-model/data/` | Small processed inputs the Blender scripts need (terrain grids, building tiers, landmarks, trees). |
| `site-model/exports/` | `context.glb`, the site model for the web (Draco-compressed). |
| `site-model/BACKLOG.md` | Refinement to-do list (in Chinese). |

All geometry shares one frame: **EPSG:26911 (NAD83 / UTM 11N), metres, NAVD88 heights**, with local origin
**E 384580, N 3768520**. In Blender, Z is up; in the web viewer (three.js), x = east, y = up, z = −north.

## Rebuilding the site model

Python pipeline (run from `site-model/`, Python 3.10+, `pip install -r requirements.txt`; on macOS type
`python3` for `python`):

```
python scripts/fetch_data.py          # DEM, LA County buildings + parcels
python scripts/fetch_lidar.py         # 2023 USGS LiDAR tile -> data/lidar/ (67 MB, not in git)
python scripts/lidar_dsm.py           # roof DSM from LiDAR
python scripts/lidar_tiers.py         # split buildings into height tiers
python scripts/prep_moca.py           # MOCA heightfield + pyramid fits
python scripts/prep_blender.py        # terrain (2 m + 0.5 m patch), buildings, parcels -> data/scene.json
python scripts/prep_landmarks.py      # Angels Flight, Metro portal
python scripts/prep_trees.py          # trees from LiDAR canopy
python scripts/export_lidar_preview.py  # web/data/lidar_points.bin + lidar_object.bin (labels)
```

Then build the Blender file. `build_all_blender.py` runs `build_blender.py`, `build_landmarks.py` and
`build_trees.py` in an empty scene, saves `site-model/blender/y1_context.blend` and exports the GLB (about
20 s). The `.blend` itself is not committed. Don't run this over a `.blend` that holds your own collections.

```
blender --background --factory-startup --python site-model/scripts/build_all_blender.py
```

(`blender` is `/Applications/Blender.app/Contents/MacOS/Blender` on macOS and `blender.exe` on Windows.)

**Exporting for the web (one click):** run `site-model/scripts/export_glb.py` in Blender, or headless:

```
blender --background site-model/blender/y1_context.blend --python site-model/scripts/export_glb.py
```

It writes `site-model/exports/context.glb` and tags every object with its collection; the viewer turns
collections into layer toggles. Put hand-made work in its own collection (e.g. `Design`); the build scripts
rebuild `Terrain`, `Buildings`, `Y1_Parcel`, `Landmarks`, `Trees` from scratch.

`export_lidar_preview.py` also labels every LiDAR point with the Blender object it belongs to
(`lidar_labels.py`, using the exported GLB's object names and layers). Run it after `export_glb.py` so
the labels match the current model. In the viewer the labels drive layer toggles, "Object" colouring and
click-to-identify in LiDAR mode.

`site-model/experiments/poisson_y1.py` reconstructs a mesh straight from the LiDAR with Poisson, for
comparison. Airborne LiDAR melts trees into one surface and keeps only roof skins, which is why the pipeline
models terrain, buildings, trees and landmarks separately.

## Previewing the website locally

```
python web/serve.py
```

Then open http://localhost:8766/ . `serve.py` serves `site-model/exports/` under `/assets/`, exactly as
the Pages deploy does, so the viewer (`web/viewer.html`) loads the same model locally and online.

## Data sources and licences

- USGS 3DEP 1 m DEM and 2023 LiDAR (`CA_LosAngeles_B23`): public domain.
- LA County GIS: LARIAC 2020 building outlines, Assessor parcels.
- OpenStreetMap (MOCA outline): © OpenStreetMap contributors, ODbL.
- Reference drawings and photographs used while modelling (EIR appendices, press and archive images) are
  **not** in this repository and must not be added; see `.gitignore`.

## Working together

Branch, commit, open a pull request; the owner merges after discussion. See [CONTRIBUTING.md](CONTRIBUTING.md),
[docs/WORKFLOW.md](docs/WORKFLOW.md) and `CLAUDE.md`.
