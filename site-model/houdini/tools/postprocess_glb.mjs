// Post-process the Houdini glTF ROP export for the web viewer (site-model/houdini/out/context_raw.glb -> context.glb).
// Houdini's exporter has no Draco quantization controls and drops material doubleSided, so:
//   1. every material doubleSided = true (as in the Blender export)
//   2. emissive off: Houdini writes emissiveFactor 1 with KHR_materials_emissive_strength 0; set the factor to 0 and drop the extension
//   3. alphaMode OPAQUE (Houdini marks every material BLEND, which breaks depth sorting; none of these is transparent)
//   4. weld + re-encode Draco with the Blender exporter's quantization (position 14, normal 10, texcoord 12 bits)
//   5. far trees (option b, 2026-10-05): the scene extras carry "trees_instanced" (name, x, base y, z, height, crown_r,
//      on_structure). Each becomes its own named node that reuses the mesh of the "Tree_unit" node (unit height, unit crown
//      radius) with translation (x, base, z) and scale (crown_r, height, crown_r); then Tree_unit and the list are removed.
// Node names, node extras (layer, source) and scene extras (georeference) are kept untouched otherwise.
//   node postprocess_glb.mjs <in.glb> <out.glb>
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS, KHRDracoMeshCompression } from "@gltf-transform/extensions";
import { draco, weld } from "@gltf-transform/functions";
import draco3d from "draco3dgltf";

const [, , src, dst] = process.argv;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({
  "draco3d.decoder": await draco3d.createDecoderModule(),
  "draco3d.encoder": await draco3d.createEncoderModule(),
});
const doc = await io.read(src);
for (const m of doc.getRoot().listMaterials()) { m.setDoubleSided(true); m.setEmissiveFactor([0, 0, 0]); m.setAlphaMode("OPAQUE"); }
for (const ext of doc.getRoot().listExtensionsUsed()) if (ext.extensionName === "KHR_materials_emissive_strength") ext.dispose();
const root = doc.getRoot(), scene = root.listScenes()[0];
const sx = scene.getExtras(), ti = sx.trees_instanced;
const unit = root.listNodes().find((n) => n.getName() === "Tree_unit");
if (ti && unit) {
  const mesh = unit.getMesh();
  ti.name.forEach((name, i) => {
    const node = doc.createNode(name).setMesh(mesh)
      .setTranslation([ti.x[i], ti.y[i], ti.z[i]]).setScale([ti.crown_r[i], ti.height[i], ti.crown_r[i]])
      .setExtras({ layer: "Trees", height_m: ti.height[i].toFixed(2), crown_r_m: ti.crown_r[i].toFixed(2), on_structure: ti.on_structure[i], generic: 1 });
    scene.addChild(node);
  });
  unit.dispose();
  delete sx.trees_instanced;
  sx.trees_generic_note = "Trees farther than 250 m from Y-1 reuse one generic tree mesh scaled to their measured height and crown radius (extras.generic = 1).";
  scene.setExtras(sx);
  console.log(`instanced ${ti.name.length} far trees from Tree_unit`);
}
await doc.transform(weld(), draco({ method: "edgebreaker", quantizePosition: 14, quantizeNormal: 10, quantizeTexcoord: 12 }));
await io.write(dst, doc);
console.log(`${src} -> ${dst}: ${doc.getRoot().listNodes().length} nodes, ${doc.getRoot().listMaterials().length} materials`);
