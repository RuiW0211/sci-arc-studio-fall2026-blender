"""Build the Y-1 context model inside a running Blender (run via Blender MCP or the Text Editor).

Reads data/scene.json + data/terrain.npy (made by prep_blender.py). 1 Blender unit = 1 m,
local origin = site.json origin in EPSG:26911. Georef is stored the BlenderGIS way.
"""
import json
from pathlib import Path

import bmesh
import bpy
import numpy as np

def _site_root():
    """site-model/ folder: from this script's own path when run with __file__ (MCP / command line),
    otherwise from the open .blend, which lives in site-model/blender/."""
    f = globals().get("__file__")
    if f and Path(f).is_absolute() and Path(f).exists():
        return Path(f).resolve().parent.parent
    if bpy.data.filepath:
        return Path(bpy.data.filepath).resolve().parent.parent
    raise RuntimeError("Open site-model/blender/y1_context.blend first, or exec this file with __file__ set")


ROOT = _site_root()
DATA = ROOT / "data"
Y1_APN = "5149-010-951"

S = json.loads((DATA / "scene.json").read_text())
scn = bpy.context.scene

# Units and BlenderGIS georeference
scn.unit_settings.system = "METRIC"
scn.unit_settings.scale_length = 1.0
scn.unit_settings.length_unit = "METERS"
scn["SRID"] = S["crs"]
scn["crs x"], scn["crs y"] = float(S["origin"][0]), float(S["origin"][1])
scn["latitude"], scn["longitude"] = S["center_latlon"]


def collection(name):
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if col.name not in scn.collection.children:
        scn.collection.children.link(col)
    for ob in list(col.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    return col


def material(name, rgb, alpha=1.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, alpha)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*rgb, 1)
        bsdf.inputs["Roughness"].default_value = 0.9
    return m


MAT_TERRAIN = material("Terrain", (0.78, 0.76, 0.72))
MAT_BLD = material("Building", (0.93, 0.93, 0.92))
MAT_Y1 = material("Y1_Parcel", (0.85, 0.12, 0.10))
MAT_ADJ = material("Adjacent_Public_Parcel", (0.95, 0.55, 0.10))

# Terrain: 2 m grid everywhere, with the cells around Y-1 replaced by the 0.5 m LiDAR patch
def grid_mesh(name, grid, x0, y0, step, skip=None):
    rows, cols = grid.shape
    X, Y = np.meshgrid(x0 + np.arange(cols) * step, y0 - np.arange(rows) * step)
    verts = np.column_stack([X.ravel(), Y.ravel(), grid.ravel()]).astype(np.float32)
    idx = np.arange(rows * cols).reshape(rows, cols)
    quads = np.column_stack([idx[1:, :-1].ravel(), idx[1:, 1:].ravel(),
                             idx[:-1, 1:].ravel(), idx[:-1, :-1].ravel()])
    if skip is not None:  # (r0, r1, c0, c1) cell range left to the fine patch
        rr, cc = np.divmod(np.arange(len(quads)), cols - 1)
        r0, r1, c0, c1 = skip
        quads = quads[~((rr >= r0) & (rr < r1) & (cc >= c0) & (cc < c1))]
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.ravel())
    me.loops.add(quads.size)
    me.loops.foreach_set("vertex_index", quads.ravel().astype(np.int32))
    me.polygons.add(len(quads))
    me.polygons.foreach_set("loop_start", np.arange(0, quads.size, 4, dtype=np.int32))
    me.update(calc_edges=True)
    me.materials.append(MAT_TERRAIN)
    me.polygons.foreach_set("use_smooth", np.ones(len(quads), dtype=bool))
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


t = S["terrain"]
col = collection("Terrain")
fine = t.get("fine")
grid_mesh("Terrain", np.load(DATA / "terrain.npy"), t["x0"], t["y0"], t["step"],
          skip=fine["coarse_cells"] if fine else None)
if fine:
    ob = grid_mesh("Terrain_Y1", np.load(DATA / "terrain_fine.npy"), fine["x0"], fine["y0"], fine["step"])
    ob["source"] = "0.5 m from USGS 3DEP 2023 LiDAR ground returns (1 m DEM where none)"

# Buildings: one object per footprint polygon
col = collection("Buildings")
for i, b in enumerate(S["buildings"]):
    bm = bmesh.new()
    rings = [b["outer"]] + b["holes"]
    top_edges, bot_edges = [], []
    for ring in rings:
        bot = [bm.verts.new((x, y, b["base"])) for x, y in ring]
        top = [bm.verts.new((x, y, b["top"])) for x, y in ring]
        n = len(ring)
        for k in range(n):
            j = (k + 1) % n
            try:
                bm.faces.new((bot[k], bot[j], top[j], top[k]))
            except ValueError:
                pass
            top_edges.append(bm.edges.get((top[k], top[j])) or bm.edges.new((top[k], top[j])))
            bot_edges.append(bm.edges.get((bot[k], bot[j])) or bm.edges.new((bot[k], bot[j])))
    # closed solids (top and bottom caps) so the tier union below is reliable
    bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=True, edges=top_edges)
    bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=True, edges=bot_edges)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.01)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(f"BLD_{b['id']}")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(MAT_BLD)
    ob = bpy.data.objects.new(f"BLD_{b['id'] or i}_t{b.get('tier', 0)}", me)
    ob["height_m"] = b["height_m"]
    ob["roof_elev_m"] = b["top"]
    ob["source"] = b.get("src", "LARIAC")
    col.objects.link(ob)

# Tiers are nested prisms all starting at the ground; union each building's tiers into one solid
groups = {}
for ob in col.objects:
    groups.setdefault(ob.name.rsplit("_t", 1)[0], []).append(ob)
for name, obs in groups.items():
    if len(obs) == 1:
        obs[0].name = name
        continue
    obs.sort(key=lambda o: o["height_m"])
    keep = obs[0]  # lowest tier = widest footprint
    for other in obs[1:]:
        mod = keep.modifiers.new("union", "BOOLEAN")
        mod.operation, mod.solver, mod.object = "UNION", "EXACT", other
        with bpy.context.temp_override(object=keep, active_object=keep):
            bpy.ops.object.modifier_apply(modifier=mod.name)
    keep["height_m"] = max(o["height_m"] for o in obs)
    keep["roof_elev_m"] = max(o["roof_elev_m"] for o in obs)
    keep["tiers"] = len(obs)
    for other in obs[1:]:
        bpy.data.objects.remove(other, do_unlink=True)
    keep.name = name

# Y-1 parcel outlines, draped on terrain
col = collection("Y1_Parcel")
for p in S["parcels"]:
    cu = bpy.data.curves.new(f"PCL_{p['apn']}", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.4 if p["apn"] == Y1_APN else 0.25
    sp = cu.splines.new("POLY")
    sp.points.add(len(p["ring"]) - 1)
    for pt, (x, y, z) in zip(sp.points, p["ring"]):
        pt.co = (x, y, z, 1)
    sp.use_cyclic_u = True
    cu.materials.append(MAT_Y1 if p["apn"] == Y1_APN else MAT_ADJ)
    ob = bpy.data.objects.new(f"PCL_{p['apn']}", cu)
    ob["apn"] = p["apn"]
    ob["area_m2"] = p["area_m2"]
    col.objects.link(ob)

# Viewport: far clip for an 800 m site
for area in bpy.context.screen.areas if bpy.context.screen else []:
    if area.type == "VIEW_3D":
        area.spaces.active.clip_end = 10000
        area.spaces.active.shading.type = "SOLID"

print("built:", len(bpy.data.collections["Buildings"].objects), "buildings,",
      len(bpy.data.collections["Y1_Parcel"].objects), "parcels")
