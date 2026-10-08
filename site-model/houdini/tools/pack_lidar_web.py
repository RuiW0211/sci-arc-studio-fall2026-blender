"""Pack the Houdini-labelled LiDAR for the web viewer (same format as site-model/scripts/export_lidar_preview.py).

Input : site-model/houdini/out/lidar_web.geo  (Houdini JSON geometry written by /obj/lidar/lidar_web_write:
        every 3rd point of the cropped, de-noised 2023 tile, with P, class_index, intensity, segc, hag, lname)
        (each point carries its object name s@lname and web layer s@llayer; out/context.glb, if present, is only compared)
Output: site-model/houdini/out/data/
        lidar_points.bin   per point: int16 x, y (north), z in decimetres (z relative to Z_BASE), uint8 class, uint8 intensity
        lidar_object.bin   uint16 per point -> names[] / layers[] in the meta (the "object" attribute the viewer reads)
        lidar_segment.bin  uint8 per point  -> Houdini segment (ground, low, building, tree, unsure, podium_tree, porous_facade,
                                         shrub, vehicle, wall, street_furniture)
        lidar_hag.bin      int16 per point  -> height above ground, decimetres
        lidar_points.json  meta, same keys as the Blender export plus the two extra attribute channels
Also prints a per-point comparison with the Blender labels in web/data (if present).

  python site-model/houdini/tools/pack_lidar_web.py          (every 3rd point, as the Blender export)
  python site-model/houdini/tools/pack_lidar_web.py --full   (every site point)
"""
import json
import struct
from pathlib import Path

import numpy as np

HZ = Path(__file__).resolve().parent.parent          # site-model/houdini/
REPO = HZ.parent.parent
OUT = HZ / "out" / "data"
OUT.mkdir(parents=True, exist_ok=True)
Z_BASE, SCALE = 60.0, 0.1
SEGMENTS = ["ground", "low", "building", "tree", "unsure", "podium_tree", "porous_facade", "shrub", "vehicle", "wall", "street_furniture"]


def geo_point_attribs(path):
    """Houdini ASCII .geo (JSON) -> {name: numpy array} for point attributes; strings as (strings, indices)."""
    g = json.load(open(path))
    d = dict(zip(g[0::2], g[1::2]))
    att = dict(zip(d["attributes"][0::2], d["attributes"][1::2]))
    out = {}
    for meta, body in att["pointattributes"]:
        meta = dict(zip(meta[0::2], meta[1::2]))
        body = dict(zip(body[0::2], body[1::2]))
        if meta["type"] == "string":
            out[meta["name"]] = (body["strings"], np.asarray(body["indices"]["arrays"][0] if isinstance(body["indices"], dict) else body["indices"][5][0]))
            continue
        vals = dict(zip(body["values"][0::2], body["values"][1::2]))
        arr = np.asarray(vals["tuples"] if "tuples" in vals else vals["arrays"][0])
        out[meta["name"]] = arr
    return out, d["pointcount"]


def string_indices(entry):
    strings, idx = entry
    return strings, idx


def glb_layers(path):
    b = open(path, "rb").read()
    jl = struct.unpack("<I", b[12:16])[0]
    g = json.loads(b[20:20 + jl])
    return {n["name"]: (n.get("extras") or {}).get("layer") for n in g["nodes"]}


import sys
FULL = "--full" in sys.argv   # every site point; positions / class / intensity straight from the raw LAZ
site = json.load(open(REPO / "site-model" / "data" / "site.json"))
ox, oy = site["origin"]
rec_dtype = [("x", "<i2"), ("y", "<i2"), ("z", "<i2"), ("c", "u1"), ("i", "u1")]
if FULL:
    # labels from /obj/lidar/lidar_full_write (P zeroed, hag as integer decimetres); the points themselves from the LAZ with the
    # same crop (+-400 m around the origin) and de-noising (classes 7 / 18) as /obj/lidar/site_crop, in the same order
    import laspy
    A, n = geo_point_attribs(HZ / "out" / "lidar_full_labels.geo")
    las = laspy.read(REPO / "site-model" / "data" / "lidar" / "USGS_LPC_CA_LosAngeles_B23_11SLT038400376800.laz")   # the centre tile (/obj/lidar/laz_points)
    x, y, z, cl = np.asarray(las.x), np.asarray(las.y), np.asarray(las.z), np.asarray(las.classification)
    m = (np.abs(x - ox) <= 400) & (np.abs(y - oy) <= 400) & ~np.isin(cl, (7, 18))
    idx = np.nonzero(m)[0]
    assert len(idx) == n, f"LAZ crop {len(idx)} != Houdini {n}"
    P = np.column_stack([x[idx] - ox, z[idx], -(y[idx] - oy)])
    cls = cl[idx].astype(np.uint8)
    it = np.asarray(las.intensity)[idx].astype(float)
    hag = np.clip(A["hagdm"], -32768, 32767).astype("<i2")
    STRIDE = 1
else:
    A, n = geo_point_attribs(HZ / "out" / "lidar_web.geo")
    P = A["P"]
    cls = A["class_index"].astype(np.uint8)
    it = A["intensity"].astype(float)
    hag = np.clip(np.round(A["hag"] * 10), -32768, 32767).astype("<i2")
    STRIDE = 3
seg = A["segc"].astype(np.uint8)
it = np.clip(it / np.percentile(it, 99) * 255, 0, 255).astype(np.uint8)
strings, sidx = A["lname"]

rec = np.zeros(n, dtype=rec_dtype)
rec["x"] = np.round(P[:, 0] / SCALE)            # east
rec["y"] = np.round(-P[:, 2] / SCALE)           # north (Houdini z = -north)
rec["z"] = np.round((P[:, 1] - Z_BASE) / SCALE)
rec["c"], rec["i"] = cls, it
rec.tofile(OUT / "lidar_points.bin")

# object names: "_other" first (the viewer's default). Each point carries its web layer (s@llayer from
# /obj/lidar/lidar_layers), so the point cloud no longer needs the model GLB; one layer per object name is checked.
names = ["_other"] + sorted(s for s in set(strings) if s != "_other")
remap = np.array([names.index(s) for s in strings], dtype="<u2")
labels = remap[sidx]
lstrings, lidx = A["llayer"]
pairs = np.unique(np.stack([labels, lidx.astype(np.int64)]), axis=1)
layer_by_id = {}
for o, l in pairs.T:
    if layer_by_id.setdefault(int(o), lstrings[int(l)]) != lstrings[int(l)]:
        raise SystemExit(f"object {names[o]} has points in two layers: {layer_by_id[int(o)]}, {lstrings[int(l)]}")
layers = [layer_by_id.get(i, "_other") for i in range(len(names))]

# while the model GLB still exists, report objects whose GLB layer differs from the point layer
glb = HZ / "out" / "context.glb"
if glb.exists():
    layer_of = glb_layers(glb)
    diff = [(nm, ly, layer_of[nm]) for nm, ly in zip(names, layers) if nm in layer_of and layer_of[nm] and layer_of[nm] != ly]
    print(f"layers vs {glb.name}: {len(diff)} objects differ" + (f", e.g. {diff[:5]}" if diff else ""))
labels.tofile(OUT / "lidar_object.bin")
seg.tofile(OUT / "lidar_segment.bin")
hag.tofile(OUT / "lidar_hag.bin")
meta = {
    "count": int(n), "stride": STRIDE, "scale": SCALE, "z_base": Z_BASE, "origin_utm": [ox, oy],
    "z_range": [float(P[:, 1].min()), float(P[:, 1].max())], "record_bytes": 8,
    "attributes": {
        "object": {"file": "lidar_object.bin", "type": "uint16", "names": names, "layers": layers,
                   "source": "Houdini (site-model/houdini/y1_lidar.hipnc, lidar_web_labels): point-cloud segmentation, "
                             "massing ownership, tree segmentation and landmark meshes"},
        "segment": {"file": "lidar_segment.bin", "type": "uint8", "names": SEGMENTS,
                    "source": "Houdini point segmentation (PCA shape + multi-return + height above ground)"},
        "hag": {"file": "lidar_hag.bin", "type": "int16", "scale": 0.1, "unit": "m",
                "source": "height above the Houdini ground heightfield"},
    },
    "source": "USGS 3DEP CA_LosAngeles_B23 (2023), tile 11SLT038400376800, public domain; labels by Houdini",
}
if "--laz" in sys.argv:
    # One compressed LAZ instead of the raw binaries: LAS point format 0 in the LOCAL frame (x east, y north from the site origin,
    # z NAVD88, 1 cm), intensity already scaled to 0-255, and the labels as LAS extra bytes (object uint16, segment uint8,
    # hag int16 decimetres). The viewer decodes it in a worker with laz-perf (WebAssembly).
    import laspy
    hdr = laspy.LasHeader(point_format=0, version="1.2")
    hdr.scales = np.array([0.01, 0.01, 0.01]); hdr.offsets = np.array([0.0, 0.0, 0.0])
    hdr.add_extra_dims([laspy.ExtraBytesParams(name="object", type=np.uint16),
                        laspy.ExtraBytesParams(name="segment", type=np.uint8),
                        laspy.ExtraBytesParams(name="hag", type=np.int16)])
    las_out = laspy.LasData(hdr)
    las_out.x, las_out.y, las_out.z = P[:, 0], -P[:, 2], P[:, 1]
    las_out.intensity = it.astype(np.uint16)
    las_out.classification = cls
    las_out.object, las_out.segment, las_out.hag = labels, seg, hag
    las_out.write(OUT / "lidar_points.laz")
    for f in ("lidar_points.bin", "lidar_object.bin", "lidar_segment.bin", "lidar_hag.bin"):
        (OUT / f).unlink(missing_ok=True)
    meta = {
        "format": "laz", "file": "lidar_points.laz", "count": int(n), "stride": STRIDE, "frame": "local",
        "origin_utm": [ox, oy], "z_range": [float(P[:, 1].min()), float(P[:, 1].max())],
        "point_format": 0, "point_length": 20 + 5,
        "extra_bytes": {"object": {"offset": 20, "type": "uint16"}, "segment": {"offset": 22, "type": "uint8"},
                        "hag": {"offset": 23, "type": "int16", "scale": 0.1, "unit": "m"}},
        "attributes": {k: {kk: vv for kk, vv in v.items() if kk != "file"} for k, v in meta["attributes"].items()},
        "source": meta["source"] + "; LAZ (LAS 1.2 format 0 + extra bytes), local frame, 1 cm",
    }
    (OUT / "lidar_points.json").write_text(json.dumps(meta, indent=1))
    print(f"LAZ: {(OUT / 'lidar_points.laz').stat().st_size / 1e6:.1f} MB")
else:
    (OUT / "lidar_points.json").write_text(json.dumps(meta, indent=1))
print(f"{n:,} points, {len(names)} objects -> {OUT}")

# comparison with the Blender labels (same point set: same crop, same de-noising, same stride)
old_meta = REPO / "web" / "data" / "lidar_points.json"
if old_meta.exists():
    om = json.load(open(old_meta))
    if om["count"] == n and not FULL:
        oo = np.fromfile(REPO / "web" / "data" / "lidar_object.bin", dtype="<u2")
        old_layer = np.array(om["attributes"]["object"]["layers"])[oo]
        new_layer = np.array(layers)[labels]
        same_pos = np.fromfile(REPO / "web" / "data" / "lidar_points.bin", dtype=rec.dtype)
        dpos = np.abs(same_pos["x"].astype(int) - rec["x"]).max(), np.abs(same_pos["y"].astype(int) - rec["y"]).max(), np.abs(same_pos["z"].astype(int) - rec["z"]).max()
        print("max position difference vs the Blender export (decimetres):", dpos)
        print(f"same layer for {np.mean(old_layer == new_layer):.1%} of points")
        keys = sorted(set(old_layer) | set(new_layer))
        print("rows = Blender layer, columns = Houdini layer (thousand points)")
        print(" " * 22 + "".join(f"{k[:12]:>13}" for k in keys))
        for a in keys:
            row = [np.sum((old_layer == a) & (new_layer == b)) / 1000 for b in keys]
            print(f"{a[:20]:>20}  " + "".join(f"{v:13.0f}" for v in row))
