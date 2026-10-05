"""MOCA (250 S Grand Ave) as a LiDAR heightfield clipped to its OpenStreetMap outline.

LARIAC's MOCA outline misses most of the building, and a flat extrusion would lose the pyramid
skylights, the barrel vault and the gallery roof lights, all of which the 2023 LiDAR resolves at 0.5 m.

Inputs : data/osm_moca.json (OSM way 206463626), LiDAR tile, dem.tif
Outputs: data/moca_heightfield.npz  (z grid, local origin, cell size, inside mask)
         data/moca.json             (outline; prep_blender.py subtracts it from the generic buildings)
"""
import json
from pathlib import Path

import laspy
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import rasterize
from scipy import ndimage
from shapely.geometry import Polygon, shape

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RES = 0.5
ox, oy = json.loads((DATA / "site.json").read_text())["origin"]

osm = json.loads((DATA / "osm_moca.json").read_text())
way = next(e for e in osm["elements"] if e["type"] == "way" and e["id"] == 206463626)
t = Transformer.from_crs(4326, 26911, always_xy=True)
outline = Polygon([t.transform(p["lon"], p["lat"]) for p in way["geometry"]]).buffer(0)

x0, y0, x1, y1 = (v + s for v, s in zip(outline.bounds, (-2, -2, 2, 2)))
nx, ny = int((x1 - x0) / RES) + 1, int((y1 - y0) / RES) + 1
T = rasterio.Affine(RES, 0, x0, 0, -RES, y1)

las = laspy.read(next((DATA / "lidar").glob("*.laz")))
X, Y, Z, C = np.asarray(las.x), np.asarray(las.y), np.asarray(las.z), np.asarray(las.classification)
m = (X > x0) & (X < x1) & (Y > y0) & (Y < y1) & ~np.isin(C, (7, 18))
col = ((X[m] - x0) / RES).astype(int).clip(0, nx - 1)
row = ((y1 - Y[m]) / RES).astype(int).clip(0, ny - 1)
dsm = np.full(nx * ny, -np.inf)
np.maximum.at(dsm, row * nx + col, Z[m])
dsm = dsm.reshape(ny, nx)
idx = ndimage.distance_transform_edt(~np.isfinite(dsm), return_distances=False, return_indices=True)
dsm = dsm[tuple(idx)]
dsm = ndimage.median_filter(dsm, size=3)  # drops railings/noise, keeps pyramid edges sharp

inside = rasterize([(outline.buffer(-0.8), 1)], out_shape=(ny, nx), transform=T).astype(bool)

# Pyramid skylights: seeds = prominent local maxima; each seed is fitted with a square pyramid sitting on
# a flat roof, z = max(roof, apex - s * max(|u|, |v|)) clipped at half-size b, in a frame rotated by th.
# Only good fits with plausible slope/size are kept (boxes and vaults fit badly and drop out).
from scipy.optimize import least_squares
from shapely.geometry import MultiPoint

rect = np.array(outline.minimum_rotated_rectangle.exterior.coords)
TH0 = float(np.arctan2(*(rect[1] - rect[0])[::-1]))  # building grid orientation
CX = x0 + (np.arange(nx) + 0.5) * RES
CY = y1 - (np.arange(ny) + 0.5) * RES
GX, GY = np.meshgrid(CX, CY)
peak = (dsm == ndimage.maximum_filter(dsm, size=11)) & inside
prom = dsm - ndimage.minimum_filter(dsm, size=21)
seeds = np.argwhere(peak & (prom > 1.5))


def model(p, x, y):
    cx_, cy_, apex, s, b, roof, th = p
    u = (x - cx_) * np.cos(th) + (y - cy_) * np.sin(th)
    v = -(x - cx_) * np.sin(th) + (y - cy_) * np.cos(th)
    d = np.maximum(np.abs(u), np.abs(v))
    return np.where(d < b, np.maximum(apex - s * d, roof), roof)


pyramids, taken = [], np.zeros_like(inside)
for r, c in sorted(seeds.tolist(), key=lambda rc: -prom[rc[0], rc[1]]):
    if taken[r, c]:
        continue
    win = (np.abs(GX - CX[c]) < 11) & (np.abs(GY - CY[r]) < 11) & inside
    x, y, zz = GX[win], GY[win], dsm[win]
    roof0 = float(np.percentile(zz, 15))
    p0 = [CX[c], CY[r], dsm[r, c], 1.0, float(np.clip(dsm[r, c] - roof0, 1.5, 10.5)), roof0, TH0]
    fit = least_squares(lambda p: model(p, x, y) - zz, p0, loss="soft_l1", f_scale=0.3,
                        bounds=([CX[c] - 3, CY[r] - 3, roof0, 0.3, 1.2, roof0 - 3, TH0 - 0.3],
                                [CX[c] + 3, CY[r] + 3, dsm[r, c] + 1, 3.0, 11, dsm[r, c], TH0 + 0.3]))
    cx_, cy_, apex, s, b, roof, th = fit.x
    b = min(b, (apex - roof) / s)  # a full pyramid, not a truncated one spanning two neighbours
    fit.x[4] = b
    near = (np.abs(x - cx_) < b * 1.42) & (np.abs(y - cy_) < b * 1.42)
    rmse = float(np.sqrt(np.median((model(fit.x, x, y) - zz)[near] ** 2)))
    h = apex - roof
    ok = rmse < 0.4 and h > 1.5 and 0.5 < s < 2.5
    print(f"  seed ({CX[c]-ox:6.1f},{CY[r]-oy:6.1f}) h {h:5.1f} base {2*b:4.1f} slope {s:4.2f} rmse {rmse:.2f} {'OK' if ok else '-'}")
    if not ok:
        continue
    corners = [(cx_ + du * b * np.cos(th) - dv * b * np.sin(th), cy_ + du * b * np.sin(th) + dv * b * np.cos(th))
               for du, dv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    pyramids.append({"base": [[px - ox, py - oy] for px, py in corners], "base_z": float(roof),
                     "apex": [cx_ - ox, cy_ - oy, float(roof + h)], "height": round(float(h), 2),
                     "side": round(float(2 * b), 1)})
    foot = rasterize([(Polygon(corners).buffer(0.4), 1)], out_shape=(ny, nx), transform=T).astype(bool)
    dsm[foot] = roof  # heightfield goes flat under the clean pyramid
    taken |= foot
pyramids.sort(key=lambda p: -p["height"])
dsm = ndimage.gaussian_filter(dsm, sigma=0.7)  # soften what is left (vaults, roof lights, parapets)
# extend the roof outward from the inner cells so the surface runs past the outline; build_landmarks.py
# then cuts it with the exact OSM outline (clean straight walls instead of a raster staircase)
near = ndimage.distance_transform_edt(~inside, return_distances=False, return_indices=True)
dsm = dsm[tuple(near)]
with rasterio.open(DATA / "dem.tif") as ds:
    dem = ds.read(1)
    cx = x0 + (np.arange(nx) + 0.5) * RES
    cy = y1 - (np.arange(ny) + 0.5) * RES
    rr = ((cy - ds.transform.f) / ds.transform.e).astype(int).clip(0, dem.shape[0] - 1)
    cc = ((cx - ds.transform.c) / ds.transform.a).astype(int).clip(0, dem.shape[1] - 1)
    ground = dem[np.ix_(rr, cc)]
base = float(ground[inside].min()) - 0.5
z = dsm

np.savez_compressed(DATA / "moca_heightfield.npz", z=z.astype(np.float32), inside=inside,
                    x0=x0 - ox + RES / 2, y1=y1 - oy - RES / 2, res=RES, base=base)
(DATA / "moca.json").write_text(json.dumps({
    "outline": [[x - ox, y - oy] for x, y in outline.exterior.coords], "pyramids": pyramids,
    "source": "outline: OSM way 206463626; roof: USGS 3DEP 2023 LiDAR, 0.5 m max-return DSM"}, indent=1))
print(f"grid {nx}x{ny}, roof z {dsm[inside].min():.1f}-{dsm[inside].max():.1f} m, base {base:.1f} m "
      f"(prep_blender.py cuts this outline out of the generic buildings)")
print(f"{len(pyramids)} pyramids (height m, base sides m):", [(p["height"], p["side"]) for p in pyramids])
