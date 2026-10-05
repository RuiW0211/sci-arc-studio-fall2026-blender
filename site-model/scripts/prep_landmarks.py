"""Landmark geometry inputs (local scene coordinates, meters) -> data/landmarks.json

Angels Flight: track alignment from the georeferenced Wood plot plan (IS-3 p.191); elevations from
the 2023 LiDAR profile (upper platform 118.0 m at California Plaza, lower end 88.6 m at Hill St,
rise 29.4 m = 96.5 ft vs. the published 96 ft).
Metro Pershing Square portal: ellipse fitted to the plan's arcs; height from LiDAR (~5 m).
Station and car sizes are approximate massing values, not surveyed.
"""
import json
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
site = json.loads((DATA / "site.json").read_text())
ox, oy = site["origin"]
g = json.loads((DATA / "plotplan_georef.json").read_text())


def plan(x, y):
    """Plot plan PDF point (y down) -> local scene XY."""
    return [g["a"] * x + g["b"] * y + g["tx"] - ox, g["b"] * x - g["a"] * y + g["ty"] - oy]


ds = rasterio.open(DATA / "dem.tif")
dem = ds.read(1)


def ground(xl, yl):
    r, c = ds.index(xl + ox, yl + oy)
    return float(dem[r, c])


# Angels Flight: s measured from the plan's upper track end toward Hill St
upper, lower = np.array(plan(332.7, 64.9)), np.array(plan(824.2, 64.9))
u = (lower - upper) / np.linalg.norm(lower - upper)
S0, Z0, S1, Z1 = -4.0, 118.0, 80.0, 88.6  # LiDAR profile: deck ends (s, z)
slope = (Z1 - Z0) / (S1 - S0)
angels_flight = {
    "origin": upper.tolist(), "dir": u.tolist(), "s0": S0, "z0": Z0, "s1": S1, "z1": Z1, "slope": slope,
    "deck_width": 3.0, "deck_thick": 0.5,
    "piers": [{"s": s, "ground": ground(*(upper + u * s))} for s in np.arange(S0 + 3, S1 - 1, 5.0)],
    "upper_station": {"s": -9.5, "len": 7.0, "wid": 7.0, "base": 118.0, "eave": 122.5, "ridge": 124.5},
    "lower_station": {"s": 83.5, "len": 6.0, "wid": 6.5, "base": 88.4, "top": 95.5,
                      "arch_w": 3.2, "arch_h": 4.6},
    "cars": [{"name": "Car_Upper", "s": 3.5}, {"name": "Car_Lower", "s": 72.0}],
    "car": {"len": 7.6, "wid": 2.4, "hgt": 3.0},
}

# Metro portal (NW entrance, Hill & 4th): open escalator well drawn on the plan as a 12.0 x 7.8 m
# rectangle (corners in pt below; A-B = north end, D-C = south end). LiDAR returns over the well sit
# ~5.2 m above grade = the 2013 glass canopy (Griffith Co.: elliptical, ~70 x 44 ft, 15 ft high,
# cantilever tripod). Escalator direction (top landing at the north end) is assumed.
A_, B_, C_, D_ = (np.array(plan(*p)) for p in ((694, 538.1), (727.3, 505.7), (780.4, 553.4), (747.1, 585.8)))
center = (A_ + B_ + C_ + D_) / 4
eL = (C_ - B_) / np.linalg.norm(C_ - B_)  # north end -> south end
eW = (B_ - A_) / np.linalg.norm(B_ - A_)
portal = {"center": center.tolist(), "eL": eL.tolist(), "eW": eW.tolist(),
          "well_len": float(np.linalg.norm(C_ - B_)), "well_wid": float(np.linalg.norm(B_ - A_)),
          "ground": ground(*center), "canopy_a": 70 * 0.3048 / 2, "canopy_b": 44 * 0.3048 / 2,
          "canopy_top": 5.2, "escalator_deg": 30.0, "parapet_h": 1.1}

(DATA / "landmarks.json").write_text(json.dumps({"angels_flight": angels_flight, "metro_portal": portal}, indent=1))
print("Angels Flight: horizontal", round(S1 - S0, 1), "m, rise", Z0 - Z1, "m, slope", round(-slope * 100), "%;",
      len(angels_flight["piers"]), "piers; portal well", round(portal["well_len"], 1), "x",
      round(portal["well_wid"], 1), "m at ground", round(portal["ground"], 1))
