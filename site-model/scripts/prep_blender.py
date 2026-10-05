"""Convert data/ into Blender-ready local coordinates (meters, origin from site.json).

Outputs:
  data/terrain.npy   float32 grid of NAVD88 elevations (m), row 0 = north, TERRAIN_STEP spacing
  data/terrain_fine.npy  0.5 m patch around Y-1 from LiDAR ground returns (replaces those coarse cells)
  data/scene.json    terrain grid info, building prisms, Y-1 parcel outlines
"""
import json
from pathlib import Path

import laspy
import numpy as np
import rasterio
from scipy import ndimage
from shapely.geometry import shape, box, Polygon, MultiPolygon
from shapely.ops import unary_union

DATA = Path(__file__).resolve().parent.parent / "data"
FT = 0.3048006096  # US survey foot (EPSG:2229 source data)
TERRAIN_STEP = 2   # terrain mesh spacing, meters

site = json.loads((DATA / "site.json").read_text())
ox, oy = site["origin"]
xmin, ymin, xmax, ymax = site["extent"]
clip = box(xmin, ymin, xmax, ymax)

ds = rasterio.open(DATA / "dem.tif")
dem = ds.read(1)


def z_at(x, y):
    r, c = ds.index(x, y)
    r = min(max(r, 0), dem.shape[0] - 1)
    c = min(max(c, 0), dem.shape[1] - 1)
    return float(dem[r, c])


# Terrain grid sampled on pixel centers every TERRAIN_STEP m
grid = dem[::TERRAIN_STEP, ::TERRAIN_STEP].astype(np.float32)
np.save(DATA / "terrain.npy", grid)
x0, y0 = ds.xy(0, 0)  # center of top-left pixel
terrain = {"x0": x0 - ox, "y0": y0 - oy, "step": TERRAIN_STEP,
           "rows": grid.shape[0], "cols": grid.shape[1]}

# Fine patch around Y-1: 0.5 m grid from 2023 LiDAR ground returns (DEM where no ground return),
# on a box snapped to the coarse lattice; its border follows the coarse edges so the two meshes meet.
FINE_STEP, FINE_MARGIN = 0.5, 20.0
k = int(TERRAIN_STEP / FINE_STEP)
pb = unary_union([shape(f["geometry"]) for f in json.loads((DATA / "parcels_y1.geojson").read_text())["features"]]).bounds
gx0, gy0 = x0 - ox, y0 - oy
c0 = int(np.floor((pb[0] - ox - FINE_MARGIN - gx0) / TERRAIN_STEP))
c1 = int(np.ceil((pb[2] - ox + FINE_MARGIN - gx0) / TERRAIN_STEP))
r0 = int(np.floor((gy0 - (pb[3] - oy + FINE_MARGIN)) / TERRAIN_STEP))
r1 = int(np.ceil((gy0 - (pb[1] - oy - FINE_MARGIN)) / TERRAIN_STEP))
fx = gx0 + c0 * TERRAIN_STEP + np.arange((c1 - c0) * k + 1) * FINE_STEP
fy = gy0 - r0 * TERRAIN_STEP - np.arange((r1 - r0) * k + 1) * FINE_STEP
FX, FY = np.meshgrid(fx, fy)
pc = (FX + ox - ds.transform.c) / ds.transform.a - 0.5
pr = (FY + oy - ds.transform.f) / ds.transform.e - 0.5
fine = ndimage.map_coordinates(dem, [pr, pc], order=1, mode="nearest")
las = laspy.read(next((DATA / "lidar").glob("*.laz")))
gm = np.asarray(las.classification) == 2
lx, ly, lz = np.asarray(las.x)[gm] - ox, np.asarray(las.y)[gm] - oy, np.asarray(las.z)[gm]
ci = np.round((lx - fx[0]) / FINE_STEP).astype(int)
ri = np.round((fy[0] - ly) / FINE_STEP).astype(int)
ok = (ci >= 0) & (ci < len(fx)) & (ri >= 0) & (ri < len(fy))
cell = ri[ok] * len(fx) + ci[ok]
order = np.argsort(cell)
cell, zs = cell[order], lz[ok][order]
uniq, start, cnt = np.unique(cell, return_index=True, return_counts=True)
med = np.array([np.median(zs[s:s + n]) for s, n in zip(start, cnt)])
flat = fine.ravel()
flat[uniq[cnt >= 2]] = med[cnt >= 2]
fine = flat.reshape(fine.shape)
# border = straight interpolation along the coarse edges (no cracks against the 2 m mesh)
cxs = gx0 + np.arange(c0, c1 + 1) * TERRAIN_STEP
cys = gy0 - np.arange(r0, r1 + 1) * TERRAIN_STEP
fine[0, :] = np.interp(fx, cxs, grid[r0, c0:c1 + 1])
fine[-1, :] = np.interp(fx, cxs, grid[r1, c0:c1 + 1])
fine[:, 0] = np.interp(-fy, -cys, grid[r0:r1 + 1, c0])
fine[:, -1] = np.interp(-fy, -cys, grid[r0:r1 + 1, c1])
np.save(DATA / "terrain_fine.npy", fine.astype(np.float32))
terrain["fine"] = {"x0": float(fx[0]), "y0": float(fy[0]), "step": FINE_STEP, "rows": len(fy), "cols": len(fx),
                   "coarse_cells": [r0, r1, c0, c1], "ground_cells": f"{(cnt >= 2).sum() / fine.size:.0%}"}


def z_fine(xl, yl):
    """Bilinear height on the fine patch (local coords), or None outside it."""
    c, r = (xl - fx[0]) / FINE_STEP, (fy[0] - yl) / FINE_STEP
    if 0 <= c < len(fx) - 1 and 0 <= r < len(fy) - 1:
        return float(ndimage.map_coordinates(fine, [[r], [c]], order=1)[0])
    return None


def rings(geom):
    polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    for p in polys:
        if isinstance(p, Polygon) and p.area > 1:
            yield p


def local(coords):
    return [[round(x - ox, 3), round(y - oy, 3)] for x, y in list(coords)[:-1]]


buildings = []
tiered = DATA / "buildings_tiered.geojson"  # from lidar_tiers.py; top_m already absolute meters
src = tiered if tiered.exists() else DATA / "buildings.geojson"
# Landmarks modelled separately (prep_moca.py) are cut out of the generic building prisms
holes = []
if (DATA / "moca.json").exists():
    holes.append(Polygon([(x + ox, y + oy) for x, y in json.loads((DATA / "moca.json").read_text())["outline"]]).buffer(0.3))
for f in json.loads(src.read_text())["features"]:
    p = f["properties"]
    g = shape(f["geometry"]).buffer(0).intersection(clip)
    for h in holes:
        if g.intersects(h):  # cut, then drop the < 4 m slivers left along the cut
            g = g.difference(h).buffer(-2).buffer(2).intersection(g.difference(h))
    if g.is_empty:
        continue
    for poly in rings(g):
        pts = list(poly.exterior.coords) + [c for h in poly.interiors for c in h.coords]
        base = min(z_at(x, y) for x, y in pts) - 0.5  # sink slightly so no gap on slopes
        if "top_m" in p:
            top = p["top_m"]
        else:
            top = (p["ELEV"] or 0) * FT  # LARIAC ELEV = absolute roof elevation, ft
            if top <= base + 2:
                top = base + max((p["HEIGHT"] or 0) * FT, 3)
        if top <= base + 2:
            top = base + 3
        buildings.append({"id": p["BLD_ID"], "tier": p.get("tier", 0), "src": p.get("src", "LARIAC"),
                          "height_m": round(top - base - 0.5, 2), "base": round(base, 2),
                          "top": round(top, 2), "outer": local(poly.exterior.coords),
                          "holes": [local(r.coords) for r in poly.interiors]})


def drape(poly, step=1.0, lift=0.3):
    line = poly.exterior
    n = max(int(line.length / step), 4)
    out = []
    for i in range(n):
        pt = line.interpolate(i / n, normalized=True)
        zf = z_fine(pt.x - ox, pt.y - oy)
        z = zf if zf is not None else z_at(pt.x, pt.y)
        out.append([round(pt.x - ox, 3), round(pt.y - oy, 3), round(z + lift, 3)])
    return out


parcels = []
for f in json.loads((DATA / "parcels_y1.geojson").read_text())["features"]:
    g = shape(f["geometry"])
    for poly in rings(g):
        parcels.append({"apn": f["properties"]["APN"], "area_m2": round(poly.area, 1),
                        "ring": drape(poly)})

(DATA / "scene.json").write_text(json.dumps({
    "origin": [ox, oy], "crs": site["crs"], "center_latlon": site["center_latlon"],
    "terrain": terrain, "buildings": buildings, "parcels": parcels}))
print(f"terrain {grid.shape}, z {grid.min():.1f}-{grid.max():.1f} m; fine patch {fine.shape} "
      f"({terrain['fine']['ground_cells']} cells from LiDAR ground); "
      f"buildings {len(buildings)}; parcels {[p['apn'] for p in parcels]}")
