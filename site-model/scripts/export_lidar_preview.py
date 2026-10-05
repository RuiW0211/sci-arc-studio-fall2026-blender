"""Pack the 2023 LiDAR (800 m site box) into a compact binary for the web preview.

Output: web/data/lidar_points.bin + lidar_points.json
  per point: int16 x, y, z in decimetres relative to the scene origin (z relative to Z_BASE),
             uint8 classification, uint8 intensity (scaled)
Every STRIDE-th point is kept (spatially uniform thinning on the original acquisition order).
"""
import json
from pathlib import Path

import laspy
import numpy as np

from lidar_labels import label_points

ROOT = Path(__file__).resolve().parent.parent          # site-model/
DATA, OUT = ROOT / "data", ROOT.parent / "web" / "data"  # repo-root web/ is what GitHub Pages serves
OUT.mkdir(parents=True, exist_ok=True)
STRIDE = 3
Z_BASE = 60.0

site = json.loads((DATA / "site.json").read_text())
ox, oy = site["origin"]
x0, y0, x1, y1 = site["extent"]
las = laspy.read(next((DATA / "lidar").glob("*.laz")))
x, y, z = np.asarray(las.x), np.asarray(las.y), np.asarray(las.z)
cl = np.asarray(las.classification)
m = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1) & ~np.isin(cl, (7, 18))
idx = np.nonzero(m)[0][::STRIDE]
it = np.asarray(las.intensity)[idx].astype(float)
it = np.clip(it / np.percentile(it, 99) * 255, 0, 255).astype(np.uint8)
rec = np.zeros(len(idx), dtype=[("x", "<i2"), ("y", "<i2"), ("z", "<i2"), ("c", "u1"), ("i", "u1")])
rec["x"] = np.round((x[idx] - ox) * 10)
rec["y"] = np.round((y[idx] - oy) * 10)
rec["z"] = np.round((z[idx] - Z_BASE) * 10)
rec["c"], rec["i"] = cl[idx], it
rec.tofile(OUT / "lidar_points.bin")

# Extra per-point attributes: one binary channel per attribute, described in the meta "attributes" table.
# "object" = the Blender object each point belongs to (lidar_labels.py); value -> names[value], layers[value].
names, layers, labels = label_points(x[idx] - ox, y[idx] - oy, z[idx], cl[idx])
labels.astype("<u2").tofile(OUT / "lidar_object.bin")
(OUT / "lidar_points.json").write_text(json.dumps({
    "count": int(len(idx)), "stride": STRIDE, "scale": 0.1, "z_base": Z_BASE, "origin_utm": [ox, oy],
    "z_range": [float(z[idx].min()), float(z[idx].max())], "record_bytes": 8,
    "attributes": {"object": {"file": "lidar_object.bin", "type": "uint16", "names": names, "layers": layers,
                              "source": "lidar_labels.py (footprints, crowns and landmark outlines from the model)"}},
    "source": "USGS 3DEP CA_LosAngeles_B23 (2023), tile 11SLT038400376800, public domain"}, indent=1))
# Y-1 outline for the viewer (draped ring from prep_blender.py, local metres)
scene = json.loads((DATA / "scene.json").read_text())
(OUT / "y1_parcel.json").write_text(json.dumps(
    {p["apn"]: p["ring"] for p in scene["parcels"]}))
print(f"{len(idx):,} points -> {(OUT / 'lidar_points.bin').stat().st_size / 1e6:.1f} MB")
