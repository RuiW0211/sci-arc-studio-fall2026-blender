"""Place the LiDAR-detected trees (data/trees.json, from prep_trees.py) into the 'Trees' collection.

Every tree links the same crown and trunk meshes (one copy in the GLB), scaled to its measured
height and crown radius. Run inside Blender after build_blender.py.
"""
import json
from pathlib import Path

import bmesh
import bpy

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
trees = json.loads((ROOT / "data" / "trees.json").read_text())["trees"]
scn = bpy.context.scene

col = bpy.data.collections.get("Trees") or bpy.data.collections.new("Trees")
if col.name not in scn.collection.children:
    scn.collection.children.link(col)
for ob in list(col.objects):
    bpy.data.objects.remove(ob, do_unlink=True)


def material(name, rgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
    m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.95
    return m


def unit_mesh(name, build, mat):
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    bm = bmesh.new()
    build(bm)
    bm.to_mesh(me)
    bm.free()
    me.materials.clear()
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    return me


# unit crown: sphere radius 1 at origin; unit trunk: cylinder radius 1, z 0..1
crown = unit_mesh("TreeCrown", lambda bm: bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0),
                  material("Tree_Foliage", (0.50, 0.58, 0.45)))
def _trunk(bm):
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=1.0, radius2=0.7, depth=1.0)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 0.5))
trunk = unit_mesh("TreeTrunk", _trunk, material("Tree_Trunk", (0.30, 0.26, 0.22)))

for i, t in enumerate(trees):
    h, r = t["height"], t["crown_r"]
    rz = min(max(0.3 * h, 0.8 * r), 1.6 * r, 0.45 * h)  # vertical crown semi-axis (crown ~60% of height)
    cz = t["ground"] + h - rz              # crown centre so the top meets the measured height
    c = bpy.data.objects.new(f"Tree_{i:03d}", crown)
    c.location = (t["x"], t["y"], cz)
    c.scale = (r, r, rz)
    c["height_m"], c["crown_r_m"], c["in_Y1"] = h, r, t["in_y1"]
    col.objects.link(c)
    tr = bpy.data.objects.new(f"Tree_{i:03d}_trunk", trunk)
    tr.location = (t["x"], t["y"], t["ground"] - 0.3)
    tr.scale = (0.1 + 0.012 * h, 0.1 + 0.012 * h, cz - t["ground"] + 0.3)
    col.objects.link(tr)
print("trees:", len(trees))
