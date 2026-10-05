"""Rebuild site-model/blender/y1_context.blend from scratch, headless, then export the GLB.

The .blend is not in git (binary, unmergeable); everything in it is generated from site-model/data/ by
build_blender.py, build_landmarks.py and build_trees.py. This runs the three in order in an empty scene,
saves the .blend, and runs export_glb.py so site-model/exports/context.glb matches.

  macOS:   /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
             --python site-model/scripts/build_all_blender.py
  Windows: "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" --background --factory-startup ^
             --python site-model/scripts/build_all_blender.py

Hand-made collections (Design, Option_A ...) live only in your own .blend: this script starts from an
empty scene, so do not run it over a file that holds manual work you have not exported or copied.
"""
import os
import time
from pathlib import Path

import bpy

SCRIPTS = Path(globals().get("__file__", "")).resolve().parent
ROOT = SCRIPTS.parent
BLEND = ROOT / "blender" / "y1_context.blend"


def run(name):
    path = str(SCRIPTS / name)
    t = time.time()
    with open(path, encoding="utf-8") as f:
        exec(compile(f.read(), path, "exec"), {"__name__": "__main__", "__file__": path})
    print(f"  {name}: {time.time() - t:.1f} s")


for ob in list(bpy.data.objects):  # factory scene: cube, camera, light
    bpy.data.objects.remove(ob, do_unlink=True)
print("building site model ...")
for name in ("build_blender.py", "build_landmarks.py", "build_trees.py"):
    run(name)
BLEND.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
print(f"saved {BLEND} ({os.path.getsize(BLEND) / 1e6:.1f} MB)")
run("export_glb.py")
