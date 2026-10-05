"""Individual trees in the fine-terrain patch around Y-1, detected from the 2023 LiDAR.

Canopy height model (0.5 m) = max non-ground return - ground (terrain_fine), with buildings, the
Angels Flight deck and the Metro canopy masked out. Tree tops = local maxima > MIN_H whose
neighbourhood is mostly multi-return pulses (foliage); crown radius = mean distance, over 16 rays,
to where the canopy falls below half the tree height (capped by half the gap to the next top).

Output: data/trees.json  [{x, y, ground, height, crown_r, in_y1}] in local coordinates
"""
import json
from pathlib import Path

import laspy
import numpy as np
from rasterio import Affine
from rasterio.features import rasterize
from scipy import ndimage
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point, Polygon, shape

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MIN_H, MAX_H, MIN_FOLIAGE = 3.0, 28.0, 0.25

S = json.loads((DATA / "scene.json").read_text())
ox, oy = S["origin"]
F = S["terrain"]["fine"]
ground = np.load(DATA / "terrain_fine.npy")
res, gx0, gy0 = F["step"], F["x0"], F["y0"]
ny, nx = ground.shape
T = Affine(res, 0, gx0 - res / 2, 0, -res, gy0 + res / 2)  # cell-centred on the fine vertices

las = laspy.read(next((DATA / "lidar").glob("*.laz")))
cl = np.asarray(las.classification)
m = (cl == 1)
x, y, z = np.asarray(las.x)[m] - ox, np.asarray(las.y)[m] - oy, np.asarray(las.z)[m]
multi = np.asarray(las.number_of_returns)[m] > 1
c = np.round((x - gx0) / res).astype(int)
r = np.round((gy0 - y) / res).astype(int)
ok = (c >= 0) & (c < nx) & (r >= 0) & (r < ny)
c, r, z, multi = c[ok], r[ok], z[ok], multi[ok]
flat = r * nx + c
dsm = np.full(nx * ny, -np.inf)
np.maximum.at(dsm, flat, z)
n_all = np.bincount(flat, minlength=nx * ny)
n_multi = np.bincount(flat, weights=multi, minlength=nx * ny)
chm = np.where(np.isfinite(dsm), dsm, -np.inf).reshape(ny, nx) - ground
chm[~np.isfinite(chm)] = 0
foliage = (ndimage.uniform_filter(n_multi.reshape(ny, nx), 5) /
           np.maximum(ndimage.uniform_filter(n_all.reshape(ny, nx).astype(float), 5), 1e-6))

# mask structures: buildings, Angels Flight deck, Metro canopy
masks = [Polygon(b["outer"]).buffer(0.8) for b in S["buildings"]]
L = json.loads((DATA / "landmarks.json").read_text())
af = L["angels_flight"]
o, u = np.array(af["origin"]), np.array(af["dir"])
masks.append(LineString([o + u * (af["s0"] - 12), o + u * (af["s1"] + 6)]).buffer(3.5))
p = L["metro_portal"]
masks.append(Point(p["center"]).buffer(1).simplify(0.1).buffer(p["canopy_a"] + 1.0))
blocked = rasterize([(g, 1) for g in masks if not g.is_empty], out_shape=(ny, nx), transform=T).astype(bool)
chm[blocked] = 0

chm_s = ndimage.gaussian_filter(chm, 1.0)
tops = (chm_s == ndimage.maximum_filter(chm_s, size=7)) & (chm_s > MIN_H) & (foliage > MIN_FOLIAGE)
rr, cc = np.nonzero(tops)
pts = np.column_stack([gx0 + cc * res, gy0 - rr * res])
gap = cKDTree(pts).query(pts, k=2)[0][:, 1] if len(pts) > 1 else np.full(len(pts), 10.0)

y1 = shape(next(f for f in json.loads((DATA / "parcels_y1.geojson").read_text())["features"]
                if f["properties"]["APN"] == "5149-010-951")["geometry"])
trees = []
angles = np.linspace(0, 2 * np.pi, 16, endpoint=False)
for (r0, c0), (px, py), g in zip(zip(rr, cc), pts, gap):
    h = float(chm[max(r0 - 1, 0):r0 + 2, max(c0 - 1, 0):c0 + 2].max())
    radii = []
    for a in angles:
        for step in range(1, 30):
            rc = int(round(r0 - np.sin(a) * step)), int(round(c0 + np.cos(a) * step))
            if not (0 <= rc[0] < ny and 0 <= rc[1] < nx) or chm_s[rc] < h * 0.5:
                break
        radii.append(step * res)
    cr = float(np.clip(np.mean(radii), 1.0, min(8.0, max(g * 0.6, 1.0))))
    # tower facades/edges that slipped past the building mask: implausibly tall, or tall and needle-thin
    if h > MAX_H or (h > 12 and cr <= 1.05):
        continue
    trees.append({"x": round(float(px), 2), "y": round(float(py), 2), "ground": round(float(ground[r0, c0]), 2),
                  "height": round(h, 2), "crown_r": round(cr, 2),
                  "in_y1": bool(y1.contains(Point(px + ox, py + oy)))})

(DATA / "trees.json").write_text(json.dumps({"source": "USGS 3DEP 2023 LiDAR canopy height model (0.5 m)",
                                             "trees": trees}, indent=1))
hs = np.array([t["height"] for t in trees])
print(f"{len(trees)} trees ({sum(t['in_y1'] for t in trees)} inside APN 951); height p10/p50/p90 "
      f"{np.percentile(hs, [10, 50, 90]).round(1)} m; crown r median {np.median([t['crown_r'] for t in trees]):.1f} m")
