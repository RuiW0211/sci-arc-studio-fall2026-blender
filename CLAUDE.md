# CLAUDE.md

Guidance for Claude Code (and humans) working in this repository. Owner: Rui Wang (GitHub RuiW0211).

## Project

Syracuse Visiting Studio, Fall 2026: Angels Knoll / Bunker Hill Parcel Y-1 (APN 5149-010-951), Los Angeles.
The repo holds the whole semester's work. The current focus is an interactive web site model with three
modes switched in one click: (1) Blender mesh, (2) a point cloud sampled from that mesh in the browser,
(3) the 2023 USGS LiDAR. Long-term goal: a realistic mesh, plus a high-precision point cloud that stays in
sync with mesh edits. See `site-model/BACKLOG.md`.

## Collaboration rules (apply to every contributor and every Claude session)

- Never commit or push directly to `main`. Work on a branch named `<your-name>/<topic>` and open a pull request; the owner reviews and merges.
- Never force-push, rewrite published history, or delete branches you did not create.
- Keep a pull request to one topic. Prefer editing files in your own area rather than reformatting shared files.
- Never add copyrighted material: EIR appendices, Getty/press/archive photos, ArchEyes/SubwayNut images, Esri or Google imagery, or anything from `site-model/references/` or `site-model/checks/`. Those stay local (they are git-ignored).
- Never commit `.blend` files or raw LiDAR (`*.laz`). Do not add files over 50 MB; ask the owner first.
- Never put credentials, tokens, or personal emails in the repo.

## Layout

- `web/` is the GitHub Pages root. Plain HTML + ES modules; three.js comes from jsDelivr through an import map. There is no build step: open a page through a local server (for example `python -m http.server` from the repo root) and reload.
- `site-model/scripts/`: the Python pipeline (`fetch_data`, `fetch_lidar`, `lidar_dsm`, `lidar_tiers`, `prep_*`, `export_lidar_preview`) runs with system Python. The `build_*.py` scripts run inside Blender; `build_all_blender.py` runs all three headless from an empty scene, saves `site-model/blender/y1_context.blend` and exports the GLB.
- Contributor docs: `docs/SETUP.md` (install, macOS-first) and `docs/WORKFLOW.md` (branch → PR → discuss → owner merges). Keep them in sync when tools or steps change.
- `site-model/data/`: small processed inputs, committed so Blender builds work without the raw LiDAR.
- `site-model/exports/context.glb`: the web model.

## Blender → web workflow (the current standard; do not change it without the owner's agreement)

1. **Collections are the web layers.** `site-model/scripts/export_glb.py`, run inside Blender, tags every object with `extras.layer = <innermost collection name>` and exports `site-model/exports/context.glb` (Draco, +Y up, extras). It skips the default `Collection` and any collection whose name starts with `_`.
2. **The viewer builds its layer toggles from the GLB at load time.** Never hard-code layer lists. `web/config.json` holds only optional display names, order and default visibility, and unknown layers appear under their raw name.
3. **Generated vs manual.** `Terrain`, `Buildings`, `Y1_Parcel`, `Landmarks` and `Trees` are cleared and rebuilt by the `build_*.py` scripts. Put manual work (design options, hand-refined buildings) in your own collections, such as `Design` or `Option_A`. The scripts never touch those.
4. **One GLB location.** The GLB lives only in `site-model/exports/`. The Pages workflow copies it into the deployed site, and `web/serve.py` does the same locally. Do not commit a second copy under `web/`.
5. **All viewer modes share the layers.** The mesh-sampled point cloud is generated from the same GLB, so it follows Blender edits and layer toggles. The LiDAR mode is independent.
6. **Update path:** edit in Blender → run `export_glb.py` → branch + PR → owner merges → Pages redeploys in about a minute.

## Conventions

- One coordinate frame everywhere: EPSG:26911, metres, NAVD88. The local origin is E 384580 / N 3768520 (`site-model/data/site.json`). three.js: x = east, y = up, z = −north.
- Pipeline scripts find their folder from `__file__`. The Blender build scripts find `site-model/` from `__file__` when executed with it set (for example through the Blender MCP: `exec(compile(src, path, "exec"), {"__name__": "__main__", "__file__": path})`), otherwise from the open `.blend`, which must live in `site-model/blender/`.
- Every derived dataset records its source in a `source` field or the script docstring. Keep doing that.
- Blender object names are stable IDs (`MOCA`, `AF_Track_Deck`, `Tree_042`, `BLD_<LARIAC id>`); the web viewer and future point-cloud attributes rely on them.
- Web style: minimal, system font, light/dark via `prefers-color-scheme`, matching the studio site.

## Data provenance

- LiDAR: USGS 3DEP `CA_LosAngeles_B23` (2023), tile `USGS_LPC_CA_LosAngeles_B23_11SLT038400376800.laz`, from https://rockyweb.usgs.gov/vdelivery/Datasets/Staged/Elevation/LPC/Projects/CA_LosAngeles_B23/CA_LosAngeles_1_B23/LAZ/ (public domain).
- DEM: USGS 3DEP 1 m ImageServer. Buildings: LA County LARIAC 2020. Parcels: LA County Assessor. MOCA outline: OSM way 206463626.
