"""Render the Poisson experiment and the current site model from the same cameras (headless Blender).

  blender --background --factory-startup --python render_compare.py -- ply <mesh.ply> <out_prefix>
  blender --background <y1_context.blend> --python render_compare.py -- blend - <out_prefix>
"""
import sys

import bpy
from mathutils import Vector

kind, src, prefix = sys.argv[sys.argv.index("--") + 1:][:3]
scn = bpy.context.scene

if kind == "ply":
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.ops.wm.ply_import(filepath=src)
    ob = bpy.context.selected_objects[0]
    for p in ob.data.polygons:
        p.use_smooth = True
    color_type = "VERTEX"
else:
    for name in ("Trees",):  # keep everything the experiment also contains
        pass
    color_type = "MATERIAL"

cam = bpy.data.objects.new("CompareCam", bpy.data.cameras.new("CompareCam"))
scn.collection.objects.link(cam)
scn.camera = cam
cam.data.lens = 35
cam.data.clip_end = 5000
scn.render.engine = "BLENDER_WORKBENCH"
sh = scn.display.shading
sh.light, sh.color_type, sh.show_shadows, sh.show_cavity = "STUDIO", color_type, True, True
scn.render.resolution_x, scn.render.resolution_y = 1400, 900

VIEWS = {
    "oblique": (Vector((25, -15, 98)), Vector((95, -75, 45))),     # from the Historic Core side, over Y-1
    "close": (Vector((-5, 35, 104)), Vector((38, -40, 22))),       # Angels Flight / north retaining wall
}
for name, (target, offset) in VIEWS.items():
    cam.location = target + offset
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    scn.render.filepath = f"{prefix}_{name}.png"
    bpy.ops.render.render(write_still=True)
    print("rendered", scn.render.filepath)
