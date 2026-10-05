"""Label LiDAR points with the Blender object they belong to (names match the GLB / Blender exactly).

Every model object was derived from this LiDAR, so the labels can be assigned back: footprints, crowns
and landmark outlines are rasterized to a 0.25 m label grid, and each point takes the label of its cell
when its height fits that object. Priority: landmarks > trees > buildings > ground; anything left
(cars, poles, street furniture) is "_other". Layers come from the GLB (extras.layer), never hard-coded.

Used by export_lidar_preview.py:  names, layers, labels = label_points(x, y, z, cls)   (local metres)
"""
import json
import struct
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from shapely.geometry import LineString, Point, Polygon

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RES = 0.25
OTHER = "_other"


def glb_layers(path=ROOT / "exports" / "context.glb"):
    """Object name -> layer, read from the exported GLB node extras."""
    with open(path, "rb") as f:
        f.read(12)
        n, _ = struct.unpack("<II", f.read(8))
        nodes = json.loads(f.read(n))["nodes"]
    return {nd["name"]: nd.get("extras", {}).get("layer") for nd in nodes if "name" in nd}


def _shapes():
    """(name, polygon, z_min_rel, z_max_rel, kind) in local coords; z relative to ground unless kind == 'abs'."""
    S = json.loads((DATA / "scene.json").read_text())
    L = json.loads((DATA / "landmarks.json").read_text())
    moca = json.loads((DATA / "moca.json").read_text())
    trees = json.loads((DATA / "trees.json").read_text())["trees"]
    out = {"landmark": [], "tree": [], "building": []}

    af = L["angels_flight"]
    o, u = np.array(af["origin"]), np.array(af["dir"])
    nrm = np.array([-u[1], u[0]])
    out["landmark"].append(("AF_Track_Deck", LineString([o + u * af["s0"], o + u * af["s1"]]).buffer(af["deck_width"] / 2 + 0.6, cap_style=2), 0.3, 12, "rel"))
    for key, name in (("upper_station", "AF_Upper_Station"), ("lower_station", "AF_Lower_Station")):
        st = af[key]
        c = o + u * st["s"]
        hl, hw = st["len"] / 2 + 0.5, st["wid"] / 2 + 0.5
        out["landmark"].append((name, Polygon([c - u * hl - nrm * hw, c + u * hl - nrm * hw, c + u * hl + nrm * hw, c - u * hl + nrm * hw]), 0.3, 12, "rel"))
    p = L["metro_portal"]
    cen, eL, eW = np.array(p["center"]), np.array(p["eL"]), np.array(p["eW"])
    ell = Polygon([cen + eL * p["canopy_a"] * np.cos(t) + eW * p["canopy_b"] * np.sin(t) for t in np.linspace(0, 2 * np.pi, 48)])
    out["landmark"].append(("Metro_Canopy_Glass", ell.buffer(0.5), 3.0, 7.5, "rel"))
    for k, pyr in enumerate(moca["pyramids"]):
        out["landmark"].append((f"MOCA_Pyramid_{k:02d}", Polygon(pyr["base"]).buffer(0.3), pyr["base_z"] - 0.5, pyr["apex"][2] + 1.0, "abs"))
    out["landmark"].append(("MOCA", Polygon(moca["outline"]), 0.8, 40, "rel"))

    for i, t in enumerate(trees):
        out["tree"].append((f"Tree_{i:03d}", Point(t["x"], t["y"]).buffer(t["crown_r"] * 1.15, 16), 1.0, t["height"] + 1.5, "rel"))

    tops = {}
    for b in S["buildings"]:
        tops[b["id"]] = max(tops.get(b["id"], 0), b["top"])
    for b in S["buildings"]:
        poly = Polygon(b["outer"], b["holes"]).buffer(0.4)
        out["building"].append((f"BLD_{b['id']}", poly, 0.5, tops[b["id"]] + 5, "abs_top"))
    return out, S["terrain"].get("fine")


def label_points(x, y, z, cls):
    shapes, fine = _shapes()
    layer_of = glb_layers()
    x0, y0, x1, y1 = x.min() - 1, y.min() - 1, x.max() + 1, y.max() + 1
    W, H = int((x1 - x0) / RES) + 1, int((y1 - y0) / RES) + 1
    T = rasterio.Affine(RES, 0, x0, 0, -RES, y1)
    col = ((x - x0) / RES).astype(np.int64)
    row = ((y1 - y) / RES).astype(np.int64)

    site = json.loads((DATA / "site.json").read_text())
    ox, oy = site["origin"]
    with rasterio.open(DATA / "dem.tif") as ds:
        dem = ds.read(1)
        r = np.clip(((y + oy - ds.transform.f) / ds.transform.e).astype(int), 0, dem.shape[0] - 1)
        c = np.clip(((x + ox - ds.transform.c) / ds.transform.a).astype(int), 0, dem.shape[1] - 1)
        ground = dem[r, c]
    hrel = z - ground

    names = [OTHER]
    labels = np.zeros(len(x), dtype=np.uint16)
    unset = np.ones(len(x), dtype=bool)
    nonground = cls != 2
    for kind in ("landmark", "tree", "building"):
        items = shapes[kind]
        base = len(names)
        names += [s[0] for s in items]
        grid = rasterize([(s[1], base + k) for k, s in enumerate(items) if not s[1].is_empty],
                         out_shape=(H, W), transform=T, fill=0, dtype="int32")
        hit = grid[row, col]
        cand = unset & nonground & (hit > 0)
        idx = np.nonzero(cand)[0]
        k = hit[idx] - base
        zmin = np.array([s[2] for s in items])[k]
        zmax = np.array([s[3] for s in items])[k]
        mode = np.array([s[4] for s in items])[k]
        zz = np.where(mode == "rel", hrel[idx], z[idx])
        ok = np.where(mode == "abs_top", (hrel[idx] > zmin) & (z[idx] < zmax), (zz > zmin) & (zz < zmax))
        labels[idx[ok]] = hit[idx[ok]]
        unset[idx[ok]] = False

    # facades and overhangs land just outside the footprints: give raised leftovers to a building within 2.5 m
    items = shapes["building"]
    first = names.index(items[0][0])
    grid = rasterize([(s[1].buffer(2.5), first + k) for k, s in enumerate(items) if not s[1].is_empty],
                     out_shape=(H, W), transform=T, fill=0, dtype="int32")
    hit = grid[row, col]
    late = unset & nonground & (hit > 0) & (hrel > 2.0)
    labels[late] = hit[late]
    unset[late] = False

    # ground: class 2 plus unclassified returns hugging the surface (pavement, kerbs); the fine 0.5 m
    # patch around Y-1 is its own object
    g = unset & ((cls == 2) | (hrel < 0.5))
    in_fine = np.zeros(len(x), dtype=bool)
    if fine:
        fx0, fy0 = fine["x0"], fine["y0"]
        fx1, fy1 = fx0 + (fine["cols"] - 1) * fine["step"], fy0 - (fine["rows"] - 1) * fine["step"]
        in_fine = (x >= fx0) & (x <= fx1) & (y <= fy0) & (y >= fy1)
    for name, sel in (("Terrain_Y1", g & in_fine), ("Terrain", g & ~in_fine)):
        names.append(name)
        labels[sel] = len(names) - 1
        unset[sel] = False

    # compact the table to labels that occur; unknown names fall back to their own layer name
    used = np.unique(labels)
    remap = np.zeros(len(names), dtype=np.uint16)
    remap[used] = np.arange(len(used))
    names = [names[i] for i in used]
    layers = [layer_of.get(nm) or (OTHER if nm == OTHER else "Unknown") for nm in names]
    return names, layers, remap[labels]


if __name__ == "__main__":
    import laspy
    site = json.loads((DATA / "site.json").read_text())
    ox, oy = site["origin"]
    xa, ya, xb, yb = site["extent"]
    las = laspy.read(next((DATA / "lidar").glob("*.laz")))
    X, Y, Z, C = np.asarray(las.x), np.asarray(las.y), np.asarray(las.z), np.asarray(las.classification)
    m = (X >= xa) & (X <= xb) & (Y >= ya) & (Y <= yb) & ~np.isin(C, (7, 18))
    names, layers, lab = label_points(X[m] - ox, Y[m] - oy, Z[m], C[m])
    counts = np.bincount(lab, minlength=len(names))
    per_layer = {}
    for nm, L, n in zip(names, layers, counts):
        per_layer[L] = per_layer.get(L, 0) + int(n)
    print(f"{m.sum():,} points, {len(names)} labels; per layer:", {k: f"{v:,}" for k, v in per_layer.items()})
