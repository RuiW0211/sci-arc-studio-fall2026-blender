"""Georeference the Wood geotechnical Plot Plan (IS-3 p.191, 1"=40') to EPSG:26911.

The plan's property boundary (black 1.44 pt dash-dot) is fitted to Assessor parcels 951+952 with
ICP + a similarity transform (rotation, scale, translation). The printed scale is the check:
1 pt = 40 ft / 72 = 0.16933 m.

Output: data/plotplan_georef.json  {a, b, tx, ty}: E = a*x - b*y' + tx, N = b*x + a*y' + ty, with y' = -y_pdf
"""
import json
from pathlib import Path

import numpy as np
import pymupdf
from scipy.spatial import cKDTree
from shapely.geometry import shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent
DATA, REF = ROOT / "data", ROOT / "references"
PAGE = 190  # 0-based index of p.191
FT = 0.3048
EXPECTED = 40 * FT / 72  # m per pt

pg = pymupdf.open(REF / "AngelsLanding_IS-3_Geotechnical.pdf")[PAGE]
pts = []
for d in pg.get_drawings():
    if d["type"] == "s" and round(d.get("width") or 0, 2) == 1.44 and d.get("color") == (0.0, 0.0, 0.0):
        for it in d["items"]:
            seq = [it[1], it[2]] if it[0] == "l" else list(it[1:]) if it[0] == "c" else []
            for p0, p1 in zip(seq, seq[1:]):
                n = max(int(abs(p1 - p0) / 2), 1)
                pts += [(p0.x + (p1.x - p0.x) * t / n, -(p0.y + (p1.y - p0.y) * t / n)) for t in range(n + 1)]
src = np.array(pts)

P = {f["properties"]["APN"]: shape(f["geometry"]) for f in json.loads((DATA / "parcels_y1.geojson").read_text())["features"]}
target = unary_union([P["5149-010-951"], P["5149-010-952"]]).exterior
dst = np.array([target.interpolate(t).coords[0] for t in np.arange(0, target.length, 0.3)])
tree = cKDTree(dst)


def similarity(a, b):
    """Umeyama: find s, R, t minimising |s R a + t - b|."""
    ma, mb = a.mean(0), b.mean(0)
    A, B = a - ma, b - mb
    U, S, Vt = np.linalg.svd(B.T @ A)
    R = U @ Vt
    if np.linalg.det(R) < 0:
        U[:, -1] *= -1
        R = U @ Vt
    s = S.sum() / (A ** 2).sum()
    return s, R, mb - s * R @ ma


# initial guess: printed scale, plan-up along Hill St (bearing ~51.5 deg from east), centroids matched
th = np.radians(51.5 - 90)
R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
s = EXPECTED
t = dst.mean(0) - s * R @ src.mean(0)
for it in range(60):
    cur = (s * (R @ src.T)).T + t
    dist, idx = tree.query(cur)
    keep = dist < np.percentile(dist, 90) + 0.5  # trim outliers (boundary bits beyond the parcel)
    s, R, t = similarity(src[keep], dst[idx[keep]])
cur = (s * (R @ src.T)).T + t
dist, _ = tree.query(cur)
a, b = s * R[0, 0], s * R[1, 0]
out = {"a": a, "b": b, "tx": t[0], "ty": t[1], "scale_m_per_pt": s, "expected_m_per_pt": EXPECTED,
       "rotation_deg": float(np.degrees(np.arctan2(b, a))),
       "residual_median_m": float(np.median(dist)), "residual_p90_m": float(np.percentile(dist, 90))}
(DATA / "plotplan_georef.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
