"""Split each LARIAC footprint into height tiers measured from the 2023 LiDAR DSM.

LARIAC gives one height per footprint (its highest point), so tower + podium complexes become one
tall slab. Here every footprint is clustered by LiDAR roof height into 1..MAX_TIERS levels, each
level is polygonized and later extruded on its own.

Input : data/buildings.geojson, data/dem.tif, data/dsm.tif
Output: data/buildings_tiered.geojson  (EPSG:26911; properties BLD_ID, tier, top_m, src)
"""
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize, shapes
from scipy import ndimage
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from sklearn.cluster import KMeans

DATA = Path(__file__).resolve().parent.parent / "data"
FT = 0.3048006096
MAX_TIERS = 5
MAX_STD = 3.0       # m, a tier's roof spread must stay under this
MIN_TIER_M2 = 40    # smaller tiers merge into the nearest level
MIN_HEIGHT = 2.5    # m above ground; lower cells inside a footprint are open plaza, not building
MIN_PIECE_M2 = 25
MIN_WIDTH = 4.0     # m

dem_ds = rasterio.open(DATA / "dem.tif")
T, SHAPE = dem_ds.transform, dem_ds.shape
dem = dem_ds.read(1)
dsm = rasterio.open(DATA / "dsm.tif").read(1)
# Knock down antennas / edge spikes, keep NaN where no returns
dsm_f = ndimage.median_filter(np.nan_to_num(dsm, nan=-9999), size=3)
dsm_f[np.isnan(dsm)] = np.nan
dsm_f[dsm_f < -1000] = np.nan


def pick_tiers(h):
    """Cluster 1-D heights; smallest k whose tiers all have std < MAX_STD."""
    h2 = h.reshape(-1, 1)
    for k in range(1, MAX_TIERS + 1):
        if k > 1 and len(h) < k * 10:
            break
        km = KMeans(n_clusters=k, n_init=4, random_state=0).fit(h2)
        lab = km.labels_
        if all(h[lab == i].std() < MAX_STD for i in range(k)):
            break
    # merge tiny tiers into the closest level
    centers = np.array([h[lab == i].mean() for i in range(lab.max() + 1)])
    sizes = np.bincount(lab)
    for i in np.argsort(sizes):
        if sizes[i] < MIN_TIER_M2 and (sizes >= MIN_TIER_M2).any():
            others = [j for j in range(len(centers)) if j != i and sizes[j] >= MIN_TIER_M2]
            j = min(others, key=lambda j: abs(centers[j] - centers[i]))
            lab[lab == i] = j
            sizes[j] += sizes[i]
            sizes[i] = 0
    return lab


out, stats = [], {"single": 0, "tiered": 0, "fallback": 0}
for n, f in enumerate(json.loads((DATA / "buildings.geojson").read_text())["features"]):
    p = dict(f["properties"])
    p["BLD_ID"] = p["BLD_ID"] or f"noid{n}"  # ~20 LARIAC outlines have no ID; keep their tiers grouped
    fp = shape(f["geometry"]).buffer(0)
    mask = rasterize([(fp, 1)], out_shape=SHAPE, transform=T).astype(bool)
    rows, cols = np.nonzero(mask)
    vals = dsm_f[rows, cols]
    ground = dem[rows, cols]
    valid = np.isfinite(vals)
    if valid.sum() < 10:
        stats["fallback"] += 1
        if fp.buffer(-MIN_WIDTH / 2).area == 0:
            continue
        top = (p["ELEV"] or 0) * FT or float(ground.min()) + max((p["HEIGHT"] or 0) * FT, 3)
        out.append({"type": "Feature", "geometry": mapping(fp),
                    "properties": {"BLD_ID": p["BLD_ID"], "tier": 0, "top_m": round(top, 2), "src": "LARIAC"}})
        continue
    # fill no-return cells from the nearest valid cell inside the footprint
    if not valid.all():
        sub = np.full(mask.shape, np.nan, dtype=np.float32)
        sub[rows, cols] = vals
        r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
        win = sub[r0:r1, c0:c1]
        idx = ndimage.distance_transform_edt(np.isnan(win), return_distances=False, return_indices=True)
        vals = win[tuple(idx)][rows - r0, cols - c0]
    built = vals - ground >= MIN_HEIGHT
    if built.sum() < 10:
        stats["fallback"] += 1
        continue
    lab = np.full(len(vals), -1)
    lab[built] = pick_tiers(vals[built])
    levels = sorted(set(lab[built]))
    stats["tiered" if len(levels) > 1 else "single"] += 1

    # Nested tiers: tier t covers every cell at level t or higher and is extruded from the ground,
    # so the lowest tier keeps the clean LARIAC outline and upper tiers stack inside it.
    levels.sort(key=lambda lv: vals[lab == lv].mean())
    rank = {lv: i for i, lv in enumerate(levels)}
    r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
    rank_img = np.full((r1 - r0, c1 - c0), -1, dtype=np.int32)
    rank_img[rows - r0, cols - c0] = [rank.get(v, -1) for v in lab]
    wT = T * rasterio.Affine.translation(c0, r0)
    for t, lv in enumerate(levels):
        top = float(np.percentile(vals[lab == lv], 90))
        m = ndimage.binary_opening(rank_img >= t, iterations=2)
        if t == 0 and m.sum() >= 0.85 * len(vals):
            poly = fp  # podium fills the footprint: use the surveyed outline as is
        else:
            geoms = [shape(g) for g, v in shapes(m.astype(np.uint8), mask=m, transform=wT) if v == 1]
            if not geoms:
                continue
            poly = unary_union(geoms).buffer(1.0).buffer(-1.0).simplify(1.2).intersection(fp)
        polys = [g for g in getattr(poly, "geoms", [poly]) if g.geom_type == "Polygon" and g.area >= MIN_PIECE_M2]
        # drop slivers (< MIN_WIDTH wide): their cells are mostly filled from a neighbouring tower edge
        polys = [g for g in polys if g.buffer(-MIN_WIDTH / 2).area > 0]
        for g in polys:
            out.append({"type": "Feature", "geometry": mapping(g),
                        "properties": {"BLD_ID": p["BLD_ID"], "tier": t, "top_m": round(top, 2), "src": "LiDAR2023"}})

(DATA / "buildings_tiered.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": out}))
print(stats, "prisms:", len(out))
