"""Build Angels Flight and the Metro Pershing Square portal into the 'Landmarks' collection.

Run inside Blender (MCP or Text Editor) after build_blender.py. Reads data/landmarks.json.
"""
import json
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

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
L = json.loads((ROOT / "data" / "landmarks.json").read_text())
scn = bpy.context.scene

col = bpy.data.collections.get("Landmarks") or bpy.data.collections.new("Landmarks")
if col.name not in scn.collection.children:
    scn.collection.children.link(col)
for ob in list(col.objects):
    bpy.data.objects.remove(ob, do_unlink=True)


def material(name, rgb, alpha=1.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, alpha)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Alpha"].default_value = alpha
    bsdf.inputs["Roughness"].default_value = 0.6 if alpha == 1 else 0.1
    if alpha < 1 and hasattr(m, "surface_render_method"):
        m.surface_render_method = "BLENDED"
    return m


M_STRUCT = material("AF_Structure", (0.25, 0.25, 0.25))
M_CAR = material("AF_Car", (0.85, 0.33, 0.08))
M_STATION = material("AF_Station", (0.80, 0.42, 0.20))
M_GLASS = material("Portal_Glass", (0.62, 0.76, 0.82), alpha=0.45)


def mesh_object(name, verts, faces, mat, props=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    bm = bmesh.new()  # consistent outward normals (needed by the boolean below)
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    for k, v in (props or {}).items():
        ob[k] = v
    col.objects.link(ob)
    return ob


BOX_FACES = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]

# ---------------- Angels Flight ----------------
af = L["angels_flight"]
O = Vector((*af["origin"], 0))
U = Vector((*af["dir"], 0))
N = Vector((-U.y, U.x, 0))
z_at = lambda s: af["z0"] + af["slope"] * (s - af["s0"])
P = lambda s, t, z: O + U * s + N * t + Vector((0, 0, z))


def sheared_box(s0, s1, t0, t1, bot, top):
    """bot/top: functions of s giving z; box ends are vertical."""
    return [P(s0, t0, bot(s0)), P(s1, t0, bot(s1)), P(s1, t1, bot(s1)), P(s0, t1, bot(s0)),
            P(s0, t0, top(s0)), P(s1, t0, top(s1)), P(s1, t1, top(s1)), P(s0, t1, top(s0))]


w, th = af["deck_width"] / 2, af["deck_thick"]
mesh_object("AF_Track_Deck", sheared_box(af["s0"], af["s1"], -w, w, lambda s: z_at(s) - th, z_at), BOX_FACES,
            M_STRUCT, {"source": "alignment: Wood plot plan; grade: LiDAR 2023 (rise 29.4 m)"})
for k, p in enumerate(af["piers"]):
    top = z_at(p["s"]) - th
    if top - p["ground"] > 0.6:
        s = p["s"]
        mesh_object(f"AF_Pier_{k:02d}", sheared_box(s - 0.2, s + 0.2, -w + 0.2, w - 0.2,
                                                    lambda _s: p["ground"] - 0.3, lambda _s: top),
                    BOX_FACES, M_STRUCT)
for k, t in enumerate((-0.7, 0.7)):  # two rails, read as track at web scale
    mesh_object(f"AF_Rail_{k}", sheared_box(af["s0"], af["s1"], t - 0.05, t + 0.05, z_at,
                                           lambda s: z_at(s) + 0.15), BOX_FACES, M_STRUCT)

c = af["car"]
for car in af["cars"]:
    s0, s1 = car["s"] - c["len"] / 2, car["s"] + c["len"] / 2
    mesh_object(f"AF_{car['name']}", sheared_box(s0, s1, -c["wid"] / 2, c["wid"] / 2,
                                                lambda s: z_at(s) + 0.3, lambda s: z_at(s) + 0.3 + c["hgt"]),
                BOX_FACES, M_CAR, {"note": "approximate car massing"})

st = af["upper_station"]
s0, s1, hw = st["s"] - st["len"] / 2, st["s"] + st["len"] / 2, st["wid"] / 2
v = sheared_box(s0, s1, -hw, hw, lambda s: st["base"], lambda s: st["eave"])
v.append(P(st["s"], 0, st["ridge"]))
mesh_object("AF_Upper_Station", v, [(0, 1, 2, 3), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0),
                                    (4, 8, 5), (5, 8, 6), (6, 8, 7), (7, 8, 4)],
            M_STATION, {"note": "approximate; top from LiDAR (~124.5 m)"})

st = af["lower_station"]
s0, s1, hw = st["s"] - st["len"] / 2, st["s"] + st["len"] / 2, st["wid"] / 2
low = mesh_object("AF_Lower_Station", sheared_box(s0, s1, -hw, hw, lambda s: st["base"], lambda s: st["top"]),
                  BOX_FACES, M_STATION, {"note": "approximate arch gateway; top from LiDAR (~95.5 m)"})
# arch opening along the track: box + half cylinder, subtracted
r = st["arch_w"] / 2
spring = st["base"] + st["arch_h"] - r
cut = mesh_object("_arch_cut", sheared_box(s0 - 1, s1 + 1, -r, r, lambda s: st["base"] - 0.5, lambda s: spring),
                  BOX_FACES, M_STATION)
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=r, radius2=r, depth=st["len"] + 2)
me = bpy.data.meshes.new("_arch_cyl")
bm.to_mesh(me)
bm.free()
cyl = bpy.data.objects.new("_arch_cyl", me)
col.objects.link(cyl)
cyl.location = P(st["s"], 0, spring)
cyl.rotation_euler = U.to_track_quat("Z", "Y").to_euler()
for cutter in (cut, cyl):
    mod = low.modifiers.new("arch", "BOOLEAN")
    mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", cutter
    with bpy.context.temp_override(object=low, active_object=low):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)

# ---------------- Metro Pershing Square portal (NW entrance, Hill & 4th) ----------------
pt = L["metro_portal"]
M_GRANITE = material("Granite", (0.42, 0.33, 0.31))
M_STEEL = material("Steel", (0.55, 0.56, 0.58))
M_DARK = material("Well_Dark", (0.08, 0.08, 0.09))
G = pt["ground"]
PC = Vector((*pt["center"], 0))
EL, EW = Vector((*pt["eL"], 0)), Vector((*pt["eW"], 0))
Q = lambda l, w, z: PC + EL * l + EW * w + Vector((0, 0, z))  # portal frame: l along well (N->S), w across
hl, hw = pt["well_len"] / 2, pt["well_wid"] / 2


def qbox(name, l0, l1, w0, w1, z0, z1, mat, zl1=None):
    """Box in the portal frame; zl1 = optional top z at l1 (sloped top, e.g. escalator)."""
    z1b = z1 if zl1 is None else zl1
    v = [Q(l0, w0, z0), Q(l1, w0, z0 if zl1 is None else zl1 - (z1 - z0)), Q(l1, w1, z0 if zl1 is None else zl1 - (z1 - z0)),
         Q(l0, w1, z0), Q(l0, w0, z1), Q(l1, w0, z1b), Q(l1, w1, z1b), Q(l0, w1, z1)]
    return mesh_object(name, v, BOX_FACES, mat)


# 1. open the terrain over the well (faces whose centre falls inside it)
for ter in [o for o in (bpy.data.objects.get("Terrain"), bpy.data.objects.get("Terrain_Y1")) if o]:
    bm = bmesh.new()
    bm.from_mesh(ter.data)
    kill = []
    for f in bm.faces:
        c = f.calc_center_median() - PC
        if abs(c.dot(EL)) < hl + 0.6 and abs(c.dot(EW)) < hw + 0.6:
            kill.append(f)
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(ter.data)
    bm.free()

# 2. well: top landing at the north end, escalators/stairs falling south at 30 deg
tan = math.tan(math.radians(pt["escalator_deg"]))
land, wall = 1.8, 0.3
l_top, l_bot = -hl + wall + land, hl - wall
drop = (l_bot - l_top) * tan
floor_z = lambda l: G - max(0.0, l - l_top) * tan
DEEP = G - drop - 1.0
qbox("Metro_Well_Floor_Landing", -hl + wall, l_top, -hw + wall, hw - wall, G - 0.4, G - 0.05, M_GRANITE)
# granite apron around the well hides the 2 m terrain grid's ragged hole edge
ap = 2.2
for k, (l0, l1, w0, w1) in enumerate(((-hl - ap, -hl, -hw - ap, hw + ap), (hl, hl + ap, -hw - ap, hw + ap),
                                      (-hl, hl, -hw - ap, -hw), (-hl, hl, hw, hw + ap))):
    qbox(f"Metro_Apron_{k}", l0, l1, w0, w1, G - 0.6, G + 0.05, M_GRANITE)
for k, (w0, w1) in enumerate(((-hw - 0.0, -hw + wall), (hw - wall, hw))):  # long walls with parapet
    qbox(f"Metro_Well_Wall_{k}", -hl, hl, w0, w1, DEEP, G + pt["parapet_h"], M_GRANITE)
qbox("Metro_Well_Wall_S", hl - wall, hl, -hw, hw, DEEP, G + pt["parapet_h"], M_GRANITE)
qbox("Metro_Well_Wall_N_low", -hl, -hl + wall, -hw, hw, G - 0.4, G + 0.05, M_GRANITE)  # open entry side
qbox("Metro_Well_Tunnel", l_bot - 0.6, l_bot, -hw + wall, hw - wall, DEEP, floor_z(l_bot) + 2.6, M_DARK)
# lanes across the well (w): stair | balustrade | escalator | centre | escalator | balustrade | stair
lanes = [("Stair", -hw + wall, -1.6), ("Bal", -1.6, -1.3), ("Esc", -1.3, -0.3), ("Bal", -0.3, 0.3),
         ("Esc", 0.3, 1.3), ("Bal", 1.3, 1.6), ("Stair", 1.6, hw - wall)]
for k, (kind, w0, w1) in enumerate(lanes):
    if kind == "Esc":
        qbox(f"Metro_Escalator_{k}", l_top, l_bot, w0, w1, floor_z(l_top) - 0.3, floor_z(l_top), M_STEEL,
             zl1=floor_z(l_bot))
    elif kind == "Bal":
        qbox(f"Metro_Balustrade_{k}", l_top - 0.8, l_bot, w0, w1, floor_z(l_top) - 0.3, floor_z(l_top) + 1.0,
             M_STEEL, zl1=floor_z(l_bot) + 1.0)
    else:
        run, rise = 0.30, 0.30 * tan
        n = int((l_bot - l_top) / run)
        verts, faces = [], []
        for s in range(n):
            l0, z = l_top + s * run, G - (s + 1) * rise
            b = len(verts)
            verts += [Q(l0, w0, DEEP), Q(l0 + run, w0, DEEP), Q(l0 + run, w1, DEEP), Q(l0, w1, DEEP),
                      Q(l0, w0, z), Q(l0 + run, w0, z), Q(l0 + run, w1, z), Q(l0, w1, z)]
            faces += [tuple(b + i for i in f) for f in BOX_FACES]
        mesh_object(f"Metro_Stair_{k}", verts, faces, M_GRANITE)

# 3. canopy: elliptical rim tube (~0.6 m) around a glass louvre field; top of rim ~5.2 m (LiDAR 4.75-5.23)
a, b, top = pt["canopy_a"], pt["canopy_b"], G + pt["canopy_top"]
rim_r, rim_z = 0.3, top - 0.3
M_RIM = material("Canopy_Rim", (0.62, 0.63, 0.64))
segs, tube = 64, 8
verts, faces = [], []
for j in range(segs):
    t = 2 * math.pi * j / segs
    cen = Q(a * math.cos(t), b * math.sin(t), rim_z)
    nrm = (EL * (math.cos(t) / a) + EW * (math.sin(t) / b)).normalized()  # outward in plan
    for k in range(tube):
        p = 2 * math.pi * k / tube
        verts.append(cen + nrm * rim_r * math.cos(p) + Vector((0, 0, rim_r * math.sin(p))))
for j in range(segs):
    for k in range(tube):
        j1, k1 = (j + 1) % segs, (k + 1) % tube
        faces.append((j * tube + k, j1 * tube + k, j1 * tube + k1, j * tube + k1))
mesh_object("Metro_Canopy_Rim", verts, faces, M_RIM)
verts = [Q(0, 0, rim_z - 0.05)] + [Q((a - rim_r) * math.cos(2 * math.pi * j / segs),
                                       (b - rim_r) * math.sin(2 * math.pi * j / segs), rim_z) for j in range(segs)]
faces = [(0, 1 + j, 1 + (j + 1) % segs) for j in range(segs)]
mesh_object("Metro_Canopy_Glass", verts, faces, M_GLASS,
            {"source": "photo (mast-suspended elliptical canopy); Griffith Co. 2013 ~70x44 ft; height LiDAR 2023"})


def strut(name, p0, p1, r0, r1, mat, square=False):
    d = p1 - p0
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=4 if square else 12, radius1=r0, radius2=r1, depth=d.length)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = p0 + d / 2
    ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    col.objects.link(ob)
    return ob


# 4. one mast on the Hill St (east, +w) side at mid-length, leaning slightly over the canopy; two stays from
#    its head to the rim at both ends of the long axis; a short post under the north end (all from the photo)
mast_foot, mast_head = Q(0, b + 0.6, G - 0.3), Q(0, b - 0.4, G + 10.0)
strut("Metro_Canopy_Mast", mast_foot, mast_head, 0.32, 0.26, M_STEEL, square=True)
for k, l in enumerate((-a + 0.3, a - 0.3)):
    strut(f"Metro_Canopy_Stay_{k}", mast_head, Q(l, 0, rim_z + rim_r), 0.05, 0.05, M_STEEL)
strut("Metro_Canopy_Post_N", Q(-a + 1.4, 0.8, G - 0.3), Q(-a + 1.4, 0.8, rim_z - rim_r), 0.15, 0.15, M_DARK)

# ---------------- MOCA: LiDAR heightfield inside the OSM outline (prep_moca.py) ----------------
hf_path = ROOT / "data" / "moca_heightfield.npz"
if hf_path.exists():
    import numpy as np
    hf = np.load(hf_path)
    z, inside, res = hf["z"], hf["inside"], float(hf["res"])
    ny, nx = z.shape
    xs = float(hf["x0"]) + np.arange(nx) * res
    ys = float(hf["y1"]) - np.arange(ny) * res
    X, Y = np.meshgrid(xs, ys)
    base = float(hf["base"])
    # closed slab: roof heightfield on top, flat bottom at base, skirt around the grid edge
    top = np.column_stack([X.ravel(), Y.ravel(), z.ravel()])
    idx = np.arange(nx * ny).reshape(ny, nx)
    faces = np.column_stack([idx[1:, :-1].ravel(), idx[1:, 1:].ravel(), idx[:-1, 1:].ravel(),
                             idx[:-1, :-1].ravel()]).tolist()
    ring = list(idx[0, :]) + list(idx[1:, -1]) + list(idx[-1, -2::-1]) + list(idx[-2:0:-1, 0])
    bot0 = len(top)
    bottom = top[ring].copy()
    bottom[:, 2] = base
    faces += [(ring[i], bot0 + i, bot0 + (i + 1) % len(ring), ring[(i + 1) % len(ring)]) for i in range(len(ring))]
    faces.append(tuple(bot0 + i for i in range(len(ring))))
    me = bpy.data.meshes.new("MOCA")
    me.from_pydata(np.vstack([top, bottom]).tolist(), [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material("MOCA_Sandstone", (0.55, 0.24, 0.17)))
    moca = bpy.data.objects.new("MOCA", me)
    moca["source"] = "outline OSM way 206463626; roof USGS 3DEP 2023 LiDAR (0.5 m); Isozaki 1986"
    col.objects.link(moca)
    # cutter: the exact OSM outline extruded well above the roof
    outline = json.loads((ROOT / "data" / "moca.json").read_text())["outline"][:-1]
    n = len(outline)
    cv = [(x, y, base - 1) for x, y in outline] + [(x, y, float(z.max()) + 5) for x, y in outline]
    cf = [tuple(range(n))[::-1], tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    cutter = mesh_object("_moca_cut", cv, cf, M_STRUCT)
    mod = moca.modifiers.new("outline", "BOOLEAN")
    mod.operation, mod.solver, mod.object = "INTERSECT", "EXACT", cutter
    with bpy.context.temp_override(object=moca, active_object=moca):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    dec = moca.modifiers.new("planar", "DECIMATE")
    dec.decimate_type, dec.angle_limit = "DISSOLVE", math.radians(3)
    with bpy.context.temp_override(object=moca, active_object=moca):
        bpy.ops.object.modifier_apply(modifier=dec.name)
    # pyramid skylights fitted to the LiDAR (prep_moca.py), as clean square pyramids
    M_SKY = material("MOCA_Skylight", (0.22, 0.32, 0.30))
    for k, p in enumerate(json.loads((ROOT / "data" / "moca.json").read_text())["pyramids"]):
        v = [(x, y, p["base_z"] - 0.2) for x, y in p["base"]] + [tuple(p["apex"])]
        mesh_object(f"MOCA_Pyramid_{k:02d}", v, [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (3, 2, 1, 0)], M_SKY,
                    {"height_m": p["height"], "base_m": p["side"], "source": "pyramid fit to LiDAR 2023"})

print("landmarks:", [o.name for o in col.objects if not o.name.startswith("AF_Pier")],
      "+", sum(o.name.startswith("AF_Pier") for o in col.objects), "piers")
