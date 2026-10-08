# CLAUDE.md

Guidance for Claude Code (and humans) working in this repository. Owner: Rui Wang (GitHub RuiW0211).

## Project

Syracuse Visiting Studio, Fall 2026: Angels Knoll / Bunker Hill Parcel Y-1 (APN 5149-010-951), Los Angeles.
The repo holds the whole semester's work. The current focus is an interactive web site model (`web/viewer.html`) with
two modes: the 2023 USGS LiDAR point cloud, labelled by object, and the mesh model. Long-term goal: points that carry
research attributes and respond to designed buildings. See `site-model/BACKLOG.md`.

**Moving from Blender to Houdini (decided 2026-10-05).** New 3D work, including everyone's design work, is done in
Houdini (`site-model/houdini/`, see its README). The website still shows the Blender model and point cloud until the
Houdini version reaches the same level; then it replaces them. Until then the Blender pipeline stays as it is.

## Collaboration rules (apply to every contributor and every Claude session)

- Never commit or push directly to `main`. Work on a branch named `<your-name>/<topic>` and open a pull request; the owner reviews and merges.
- Never force-push, rewrite published history, or delete branches you did not create.
- Keep a pull request to one topic. Prefer editing files in your own area rather than reformatting shared files.
- Never add copyrighted material: EIR appendices, Getty/press/archive photos, ArchEyes/SubwayNut images, Esri or Google imagery, or anything from `site-model/references/` or `site-model/checks/`. Those stay local (they are git-ignored).
- Never commit `.hip` / `.hipnc` / `.hiplc` or `.blend` files, or raw LiDAR tiles. Do not add files over 50 MB; ask the owner first.
- Never put credentials, tokens, or personal emails in the repo.

## Layout

- `web/` is the GitHub Pages root. Plain HTML + ES modules; three.js comes from jsDelivr through an import map. There is no build step: open a page through a local server (for example `python -m http.server` from the repo root) and reload.
- `site-model/scripts/`: the Python pipeline (`fetch_data`, `fetch_lidar`, `lidar_dsm`, `lidar_tiers`, `prep_*`, `export_lidar_preview`, `fetch_population`) runs with system Python. The `build_*.py` scripts run inside Blender; `build_all_blender.py` runs all three headless from an empty scene, saves `site-model/blender/y1_context.blend` and exports the GLB.
- Contributor docs: `docs/SETUP.md` (install, macOS-first) and `docs/WORKFLOW.md` (branch → PR → discuss → owner merges). Keep them in sync when tools or steps change.
- `site-model/data/`: small processed inputs, committed so Blender builds work without the raw LiDAR.
- `site-model/houdini/`: the Houdini work. `tools/` (Python pipeline and `new_design_scene.py`), `vex/`, `annotations/entities.json` (building entities), `handoff/` (buildings + terrain for analysis layers). `in/`, `work/`, `out/` and all scenes are git-ignored.
- `site-model/exports/context.glb`: the web model of the site. `site-model/exports/design_<name>.glb`: one design file per person.

## Houdini → web workflow (the current standard; do not change it without the owner's agreement)

1. **Two kinds of GLB.** `site-model/exports/context.glb` is the site, written only by the site pipeline (today the Blender build, later Houdini). `site-model/exports/design_<name>.glb` is one person's design, exported from their own scene (`site-model/houdini/designs/<name>.hipnc`, made by `tools/new_design_scene.py`) with its ROP `/out/export_design`. Each person commits only their own design file, so merges never overwrite someone else's work. Never re-export the site into a design file or a design into `context.glb`.
2. **The viewer loads every design file by itself.** The Pages workflow and `web/serve.py` list `site-model/exports/*.glb` in `assets/models.json`; the viewer adds each `design_*.glb` on top of the site, also over the point cloud, and design meshes are clickable there.
3. **Layers come from glTF extras.** Every node carries `extras.layer`; in a design scene the `web_tags` wrangle sets it from the primitive attribute `layer` (default `Design_<name>`), and `name` makes separate nodes. The viewer builds its layer toggles from the GLBs at load time: never hard-code layer lists. `web/config.json` holds only optional display names, order, colours and default visibility; unknown layers appear under their raw name.
4. **One GLB location.** GLBs live only in `site-model/exports/`. The Pages workflow copies them into the deployed site, and `web/serve.py` does the same locally. Do not commit a second copy under `web/`.
5. **Frame.** Houdini's axes are the viewer's: x = east, y = up, z = −north, metres, NAVD88, from the site origin. Design at real heights against `/obj/Site_context`.
6. **Update path:** model in Houdini → Render `/out/export_design` → branch + PR → owner merges → Pages redeploys in about a minute.
7. **Houdini licence:** everyone uses Houdini Apprentice (`.hipnc`); files from other licence types can't be opened in Apprentice. Claude reaches Houdini through the houdini-mcp server and `hrpyc` on port 18811 (`docs/SETUP.md` §7); Apprentice has no command-line `hython`, so scripts run inside the Houdini session.

**Blender (until the switch).** The current `context.glb` comes from `site-model/scripts/build_all_blender.py` + `export_glb.py`: Blender collections become `extras.layer`; `Terrain`, `Buildings`, `Y1_Parcel`, `Landmarks` and `Trees` are rebuilt from scratch, so hand-made work goes in its own collection.

## Conventions

- One coordinate frame everywhere: EPSG:26911, metres, NAVD88. The local origin is E 384580 / N 3768520 (`site-model/data/site.json`). three.js: x = east, y = up, z = −north.
- Pipeline scripts find their folder from `__file__`. The Blender build scripts find `site-model/` from `__file__` when executed with it set (for example through the Blender MCP: `exec(compile(src, path, "exec"), {"__name__": "__main__", "__file__": path})`), otherwise from the open `.blend`, which must live in `site-model/blender/`.
- Every derived dataset records its source in a `source` field or the script docstring. Keep doing that.
- Object names are stable IDs (`MOCA`, `AF_Track_Deck`, `BLD_<LARIAC id>`, `PC_<x>_<z>` for LiDAR-only structures); the web viewer, the point-cloud labels and `entities.json` rely on them. Numbered names (`Tree_0042`, `Vehicle_…`, `Shrub_…`) change on every rebuild: never reference them from other files.
- Web style: minimal, system font, light/dark via `prefers-color-scheme`, matching the studio site.

## Data provenance

- LiDAR: USGS 3DEP `CA_LosAngeles_B23` (2023), tile `USGS_LPC_CA_LosAngeles_B23_11SLT038400376800.laz`, from https://rockyweb.usgs.gov/vdelivery/Datasets/Staged/Elevation/LPC/Projects/CA_LosAngeles_B23/CA_LosAngeles_1_B23/LAZ/ (public domain).
- DEM: USGS 3DEP 1 m ImageServer. Buildings: LA County LARIAC 2020. Parcels: LA County Assessor. MOCA outline: OSM way 206463626.
