"""Build a 1 m roof DSM (max single-return non-ground point per cell) from the 2023 3DEP LiDAR tile, on the dem.tif grid.

Input : data/lidar/*.laz  (EPSG:6340 NAD83(2011) UTM 11N + NAVD88 Geoid18, meters)
Output: data/dsm.tif      same grid/CRS as dem.tif; NaN where no returns
"""
from pathlib import Path

import laspy
import numpy as np
import rasterio

DATA = Path(__file__).resolve().parent.parent / "data"
KEEP = (1, 17)  # unclassified (buildings, vegetation) + bridge deck; drops ground 2 and noise 7/18

with rasterio.open(DATA / "dem.tif") as ds:
    profile, transform, shape = ds.profile, ds.transform, ds.shape
dsm = np.full(shape, np.nan, dtype=np.float32)

for f in sorted((DATA / "lidar").glob("*.laz")):
    las = laspy.read(f)
    # Single-return pulses only: roofs give one return, tree canopy mostly gives several
    m = np.isin(np.asarray(las.classification), KEEP) & (np.asarray(las.number_of_returns) == 1)
    x, y, z = np.asarray(las.x)[m], np.asarray(las.y)[m], np.asarray(las.z)[m].astype(np.float32)
    col = ((x - transform.c) / transform.a).astype(np.int64)
    row = ((y - transform.f) / transform.e).astype(np.int64)
    ok = (row >= 0) & (row < shape[0]) & (col >= 0) & (col < shape[1])
    flat = row[ok] * shape[1] + col[ok]
    out = np.full(shape[0] * shape[1], -np.inf, dtype=np.float32)
    np.maximum.at(out, flat, z[ok])
    out = out.reshape(shape)
    dsm = np.where(np.isfinite(out), np.fmax(dsm, out), dsm)
    print(f.name, "kept", int(ok.sum()), "points")

profile.update(dtype="float32", nodata=np.nan)
with rasterio.open(DATA / "dsm.tif", "w", **profile) as dst:
    dst.write(dsm, 1)
print("dsm cells with data:", f"{np.isfinite(dsm).mean():.1%}")
