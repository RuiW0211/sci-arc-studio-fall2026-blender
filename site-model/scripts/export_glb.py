"""One-click export of the site model to site-model/exports/context.glb (run inside Blender).

Standard workflow (see CLAUDE.md): every object is tagged with extras.layer = the innermost collection it
belongs to, and the web viewer builds its layer toggles from those tags. Skipped: the default
"Collection", any collection whose name starts with "_", cameras and lights.

Run from Blender's Text Editor (with site-model/blender/y1_context.blend open), via the MCP, or headless:
  blender --background site-model/blender/y1_context.blend --python site-model/scripts/export_glb.py
"""
import contextlib
import io
import os
from pathlib import Path

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
OUT = ROOT / "exports" / "context.glb"
SKIP_TYPES = {"CAMERA", "LIGHT", "LIGHT_PROBE", "SPEAKER"}


def skipped(col):
    return col.name == "Collection" or col.name.startswith("_")


def innermost_layer(scene_root):
    """Map object -> innermost exported collection name (depth-first, deepest wins)."""
    layer = {}

    def walk(col, depth):
        if skipped(col):
            return
        for ob in col.objects:
            if ob.type not in SKIP_TYPES and layer.get(ob, (None, -1))[1] < depth:
                layer[ob] = (col.name, depth)
        for child in col.children:
            walk(child, depth + 1)

    for top in scene_root.children:
        walk(top, 0)
    return {ob: name for ob, (name, _) in layer.items()}


scn = bpy.context.scene
layers = innermost_layer(scn.collection)
if bpy.context.object and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.select_all(action="DESELECT")
for ob, name in layers.items():
    ob["layer"] = name
    ob.select_set(True)
bpy.context.view_layer.objects.active = next(iter(layers))

OUT.parent.mkdir(parents=True, exist_ok=True)
with contextlib.redirect_stdout(io.StringIO()):
    bpy.ops.export_scene.gltf(filepath=str(OUT), export_format="GLB", use_selection=True,
                              export_apply=True, export_yup=True, export_cameras=False, export_lights=False,
                              export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
                              export_extras=True)
bpy.ops.object.select_all(action="DESELECT")

counts = {}
for name in layers.values():
    counts[name] = counts.get(name, 0) + 1
print(f"exported {len(layers)} objects -> {OUT} ({os.path.getsize(OUT) / 1e6:.2f} MB); layers: {counts}")
