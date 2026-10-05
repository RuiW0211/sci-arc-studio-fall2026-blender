// Y-1 site viewer: Blender mesh / points sampled from that mesh / 2023 LiDAR, one camera.
// Layers are read from the GLB (extras.layer = Blender collection); config.json only adds labels.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { MeshSurfaceSampler } from "three/addons/math/MeshSurfaceSampler.js";

const $ = (s) => document.querySelector(s);
const status = (t) => { $("#status").textContent = t || ""; };
const cfg = await (await fetch("config.json")).json();

// ---------- renderer / scene / camera ----------
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
document.body.prepend(renderer.domElement);
const scene = new THREE.Scene();
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
scene.background = new THREE.Color(css("--bg3d"));
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => scene.background.set(css("--bg3d")));
const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.5, 6000);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.maxDistance = 2500;
scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8478, 2.2));
const sun = new THREE.DirectionalLight(0xffffff, 1.6);
sun.position.set(300, 500, 200);
scene.add(sun);
const v0 = cfg.views[0];
camera.position.fromArray(v0.position);
controls.target.fromArray(v0.target);

// ---------- model + layers ----------
const draco = new DRACOLoader().setDecoderPath("https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/libs/draco/gltf/");
const gltf = await new GLTFLoader().setDRACOLoader(draco).loadAsync(cfg.model, (e) => {
  if (e.total) status(`Loading model… ${Math.round((e.loaded / e.total) * 100)}%`);
});
const model = gltf.scene;
model.updateMatrixWorld(true);
scene.add(model);

const layers = new Map(); // name -> { cfg, objects, meshes, visible, points }
model.traverse((o) => {
  const name = o.userData.layer;
  if (!name || layers.get(name)?.objects.includes(o)) return;
  if (!layers.has(name)) {
    const c = cfg.layers[name] || {};
    layers.set(name, { name, cfg: c, objects: [], meshes: [], visible: c.visible ?? true, points: null });
  }
  const L = layers.get(name);
  L.objects.push(o);
  o.traverse((m) => m.isMesh && L.meshes.push(m));
});
// LiDAR layers that have no mesh counterpart (e.g. "_other") get a toggle too; the LiDAR meta is tiny
const lidarMeta = await (await fetch(cfg.lidar.meta)).json();
for (const name of new Set(lidarMeta.attributes?.object?.layers ?? [])) {
  if (!layers.has(name)) {
    const c = cfg.layers[name] || {};
    layers.set(name, { name, cfg: c, objects: [], meshes: [], visible: c.visible ?? true, points: null });
  }
}
const ordered = [...layers.values()].sort((a, b) => (a.cfg.order ?? 99) - (b.cfg.order ?? 99) || a.name.localeCompare(b.name));

let mode = null;
const pointsGroup = new THREE.Group();
scene.add(pointsGroup);
const lidarGroup = new THREE.Group();
scene.add(lidarGroup);
let lidar = null;

function applyVisibility() {
  for (const L of ordered) {
    // strict booleans: three.js only skips objects whose visible === false (undefined still renders)
    const showMesh = Boolean(L.visible && (mode === "mesh" || L.cfg.overlay));
    for (const o of L.objects) o.visible = showMesh;
    if (L.points) L.points.visible = Boolean(L.visible && mode === "points" && !L.cfg.overlay);
    if (L.lidar) L.lidar.visible = Boolean(L.visible && mode === "lidar");
  }
}

$("#layers").innerHTML = "";
for (const L of ordered) {
  const row = document.createElement("label");
  row.className = "layer";
  const n = L.objects.length ? L.objects.length : "LiDAR";
  row.innerHTML = `<input type="checkbox" ${L.visible ? "checked" : ""}> ${L.cfg.label || L.name} <span class="n">${n}</span>`;
  row.querySelector("input").onchange = (e) => { L.visible = e.target.checked; applyVisibility(); };
  $("#layers").append(row);
}

// ---------- point material: size in metres (perspective), never smaller than 1 px ----------
function pointMaterial(sizeMetres) {
  const mat = new THREE.PointsMaterial({ size: sizeMetres, vertexColors: true, sizeAttenuation: true });
  mat.onBeforeCompile = (shader) => {
    shader.vertexShader = shader.vertexShader.replace(
      "#include <fog_vertex>", "gl_PointSize = max(gl_PointSize, 1.0);\n#include <fog_vertex>");
    // round points instead of squares
    shader.fragmentShader = shader.fragmentShader.replace(
      "#include <clipping_planes_fragment>",
      "if (length(gl_PointCoord - vec2(0.5)) > 0.5) discard;\n#include <clipping_planes_fragment>");
  };
  return mat;
}

// ---------- model points: sampled from the same GLB, per layer ----------
const LIGHT = new THREE.Vector3(0.45, 0.8, 0.35).normalize();
function worldArea(mesh) {
  const g = mesh.geometry, p = g.attributes.position, idx = g.index;
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  const tri = idx ? idx.count / 3 : p.count / 3;
  let area = 0;
  for (let t = 0; t < tri; t++) {
    const i0 = idx ? idx.getX(3 * t) : 3 * t, i1 = idx ? idx.getX(3 * t + 1) : 3 * t + 1, i2 = idx ? idx.getX(3 * t + 2) : 3 * t + 2;
    a.fromBufferAttribute(p, i0).applyMatrix4(mesh.matrixWorld);
    b.fromBufferAttribute(p, i1).applyMatrix4(mesh.matrixWorld);
    c.fromBufferAttribute(p, i2).applyMatrix4(mesh.matrixWorld);
    area += b.sub(a).cross(c.sub(a)).length() / 2;
  }
  return area;
}

async function buildModelPoints() {
  const mp = cfg.modelPoints;
  const jobs = [];
  const sphere = new THREE.Sphere();
  for (const L of ordered) {
    if (L.cfg.overlay) continue;
    const w = mp.layerWeight?.[L.name] ?? 1;
    for (const m of L.meshes) {
      if (!m.geometry.boundingSphere) m.geometry.computeBoundingSphere();
      sphere.copy(m.geometry.boundingSphere).applyMatrix4(m.matrixWorld);
      const d = Math.hypot(sphere.center.x, sphere.center.z);  // horizontal distance from the site origin
      const fall = 1 / (1 + (d / (mp.falloff || 1e9)) ** 2);
      jobs.push({ L, m, area: worldArea(m) * w * fall });
    }
  }
  const total = jobs.reduce((s, j) => s + j.area, 0);
  const buffers = new Map(ordered.map((L) => [L, { pos: [], col: [] }]));
  const p = new THREE.Vector3(), n = new THREE.Vector3(), nm = new THREE.Matrix3();
  for (let k = 0; k < jobs.length; k++) {
    const { L, m, area } = jobs[k];
    let count = (mp.budget * area) / total;
    count = Math.floor(count) + (Math.random() < count % 1 ? 1 : 0);
    if (count > 0) {
      const geo = m.geometry.index ? m.geometry.toNonIndexed() : m.geometry;
      const sampler = new MeshSurfaceSampler(new THREE.Mesh(geo)).build();
      const mat = Array.isArray(m.material) ? m.material[0] : m.material;
      const base = mat?.color ?? new THREE.Color(0.8, 0.8, 0.8);
      nm.getNormalMatrix(m.matrixWorld);
      const buf = buffers.get(L);
      for (let i = 0; i < count; i++) {
        sampler.sample(p, n);
        p.applyMatrix4(m.matrixWorld);
        n.applyMatrix3(nm).normalize();
        // simple lambert so forms read without lights, plus a little per-point grain so it reads as points
        const shade = (0.6 + 0.4 * Math.max(0, n.dot(LIGHT))) * (0.82 + 0.3 * Math.random());
        buf.pos.push(p.x, p.y, p.z);
        buf.col.push(base.r * shade, base.g * shade, base.b * shade);
      }
      if (geo !== m.geometry) geo.dispose();
    }
    // yield with a timer, not requestAnimationFrame: rAF never fires in a hidden tab
    if (k % 25 === 0) { status(`Sampling points… ${Math.round((k / jobs.length) * 100)}%`); await new Promise((r) => setTimeout(r, 0)); }
  }
  const material = pointMaterial(mp.size);
  let n_total = 0;
  for (const [L, buf] of buffers) {
    if (!buf.pos.length) continue;
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(buf.pos, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(buf.col, 3));
    g.userData.materialColor = Float32Array.from(buf.col);  // kept for switching colour modes
    L.points = new THREE.Points(g, material);
    pointsGroup.add(L.points);
    n_total += buf.pos.length / 3;
  }
  pointsGroup.userData.material = material;
  pointsGroup.userData.count = n_total;
  status("");
}

// ---------- LiDAR (2023 USGS), loaded on first use ----------
// Points are split per layer (from the "object" attribute) so layer toggles apply to the LiDAR too.
async function loadLidar() {
  status("Loading LiDAR…");
  const meta = lidarMeta;
  const base = cfg.lidar.meta.replace(/[^/]*$/, "");
  const objAttr = meta.attributes?.object;
  const [buf, objBuf] = await Promise.all([
    fetch(cfg.lidar.points).then((r) => r.arrayBuffer()),
    objAttr ? fetch(base + objAttr.file).then((r) => r.arrayBuffer()) : null,
  ]);
  const n = meta.count, dv = new DataView(buf);
  const obj = objBuf ? new Uint16Array(objBuf) : new Uint16Array(n);
  const objNames = objAttr?.names ?? ["_other"], objLayers = objAttr?.layers ?? ["_other"];
  const material = pointMaterial(cfg.lidar.size ?? 0.3);
  // bucket point indices by layer
  const byLayer = new Map();
  for (let i = 0; i < n; i++) {
    const L = objLayers[obj[i]];
    if (!byLayer.has(L)) byLayer.set(L, []);
    byLayer.get(L).push(i);
  }
  const parts = [];
  for (const [name, idx] of byLayer) {
    const m = idx.length;
    const pos = new Float32Array(m * 3), zs = new Float32Array(m), cls = new Uint8Array(m), inten = new Uint8Array(m), ob = new Uint16Array(m);
    for (let j = 0; j < m; j++) {
      const i = idx[j], o = i * meta.record_bytes;
      const z = dv.getInt16(o + 4, true) * meta.scale + meta.z_base;
      pos[3 * j] = dv.getInt16(o, true) * meta.scale;
      pos[3 * j + 1] = z;
      pos[3 * j + 2] = -dv.getInt16(o + 2, true) * meta.scale;
      zs[j] = z; cls[j] = dv.getUint8(o + 6); inten[j] = dv.getUint8(o + 7); ob[j] = obj[i];
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const col = new Float32Array(m * 3);
    g.setAttribute("color", new THREE.BufferAttribute(col, 3));
    const pts = new THREE.Points(g, material);
    pts.userData.part = { name, zs, cls, inten, ob, col, n: m };
    lidarGroup.add(pts);
    parts.push(pts.userData.part);
    const L = layers.get(name);
    if (L) L.lidar = pts;
  }
  const objCount = new Uint32Array(objNames.length);
  for (let i = 0; i < n; i++) objCount[obj[i]]++;
  lidar = { parts, material, objNames, objLayers, objCount, count: n, how: "height", selected: -1 };
  paintLidar("height");
  status("");
}
function hashColor(k) {  // stable, well-spread colour per object id
  const h = ((k * 0.61803398875) % 1 + 1) % 1;
  return new THREE.Color().setHSL(h, 0.62, 0.55);
}
const RAMP = [[0.18, 0.2, 0.45], [0.13, 0.55, 0.6], [0.55, 0.78, 0.35], [0.98, 0.85, 0.3], [0.85, 0.35, 0.2]];
function ramp(t) {
  t = Math.min(Math.max(t, 0), 1) * (RAMP.length - 1);
  const k = Math.min(Math.floor(t), RAMP.length - 2), f = t - k, a = RAMP[k], b = RAMP[k + 1];
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
}
const HILITE = [1.0, 0.42, 0.12];
function paintLidar(how = lidar.how) {
  lidar.how = how;
  const sel = lidar.selected;
  const tmp = new THREE.Color();
  for (const { zs, cls, inten, ob, col, n } of lidar.parts) {
    for (let i = 0; i < n; i++) {
      let c;
      if (ob[i] === sel) c = HILITE;
      else if (how === "height") c = ramp((zs[i] - 78) / 60);
      else if (how === "class") c = cls[i] === 2 ? [0.72, 0.6, 0.42] : zs[i] > 140 ? [0.55, 0.58, 0.62] : [0.3, 0.52, 0.36];
      else if (how === "object") { tmp.copy(lidar.objLayers[ob[i]] === "_other" ? new THREE.Color(0.35, 0.35, 0.35) : hashColor(ob[i])); c = [tmp.r, tmp.g, tmp.b]; }
      else { const v = 0.15 + (inten[i] / 255) * 0.85; c = [v, v, v]; }
      col.set(c, 3 * i);
    }
  }
  for (const p of lidarGroup.children) p.geometry.attributes.color.needsUpdate = true;
  document.querySelectorAll("#lidarColors button").forEach((b) => b.classList.toggle("on", b.dataset.c === how));
}
document.querySelectorAll("#lidarColors button").forEach((b) => (b.onclick = () => paintLidar(b.dataset.c)));

// model points colour: material colours (from Blender) or the same height ramp as the LiDAR
function paintModelPoints(how) {
  for (const L of ordered) {
    if (!L.points) continue;
    const g = L.points.geometry, col = g.attributes.color.array, pos = g.attributes.position.array;
    if (how === "material") col.set(g.userData.materialColor);
    else for (let i = 0; i < col.length; i += 3) col.set(ramp((pos[i + 1] - 78) / 60), i);
    g.attributes.color.needsUpdate = true;
  }
  document.querySelectorAll("#ptsColors button").forEach((b) => b.classList.toggle("on", b.dataset.c === how));
}
document.querySelectorAll("#ptsColors button").forEach((b) => (b.onclick = () => paintModelPoints(b.dataset.c)));

// ---------- modes ----------
let busy = false;
async function setMode(m) {
  if (busy || m === mode) return;
  busy = true;
  document.querySelectorAll("#modes button").forEach((b) => (b.disabled = true));
  if (m === "points" && !pointsGroup.children.length) { await buildModelPoints(); paintModelPoints("material"); }
  if (m === "lidar" && !lidar) await loadLidar();
  mode = m;
  applyVisibility();
  document.querySelectorAll("#modes button").forEach((b) => { b.disabled = false; b.classList.toggle("on", b.dataset.mode === m); });
  $("#ptsOpts").hidden = m === "mesh";
  $("#lidarOpts").hidden = m !== "lidar";
  $("#ptsColorOpts").hidden = m !== "points";
  const mat = m === "lidar" ? lidar.material : pointsGroup.userData.material;
  if (mat) $("#ptSize").value = mat.size;
  if (m !== "mesh") hideInfo();
  busy = false;
}
document.querySelectorAll("#modes button").forEach((b) => (b.onclick = () => setMode(b.dataset.mode)));
$("#ptSize").oninput = (e) => {
  const mat = mode === "lidar" ? lidar?.material : pointsGroup.userData.material;
  if (mat) mat.size = +e.target.value;
};

// ---------- views ----------
let tween = null;
function goTo(v) {
  tween = { t0: performance.now(), dur: 900,
    p0: camera.position.clone(), p1: new THREE.Vector3().fromArray(v.position),
    q0: controls.target.clone(), q1: new THREE.Vector3().fromArray(v.target) };
}
for (const v of cfg.views) {
  const b = document.createElement("button");
  b.textContent = v.name;
  b.onclick = () => goTo(v);
  $("#views").append(b);
}

// ---------- click for details (mesh mode) ----------
const ray = new THREE.Raycaster();
const SKIP_KEYS = new Set(["layer", "name", "scatter5"]);
let down = null;
renderer.domElement.addEventListener("pointerdown", (e) => (down = [e.clientX, e.clientY]));
renderer.domElement.addEventListener("pointerup", (e) => {
  if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4 || mode === "points") return;
  ray.setFromCamera(new THREE.Vector2((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1), camera);
  const visible = (o) => { for (; o; o = o.parent) if (!o.visible) return false; return true; };
  if (mode === "lidar") return pickLidar();
  const hit = ray.intersectObject(model, true).find((h) => visible(h.object));
  if (!hit) return hideInfo();
  let node = hit.object;
  while (node && !node.userData.layer) node = node.parent;
  showInfo(node || hit.object, hit.point);

  // LiDAR: the clicked point's object label -> the same Blender object; highlight all its points
  function pickLidar() {
    ray.params.Points.threshold = 0.6;
    const hit = ray.intersectObjects(lidarGroup.children.filter((p) => p.visible), false)[0];
    if (!hit) { lidar.selected = -1; paintLidar(); return hideInfo(); }
    const id = hit.object.userData.part.ob[hit.index], name = lidar.objNames[id];
    const node = model.getObjectByName(name) || { name: name === "_other" ? "Unassigned LiDAR points" : name,
                                                  userData: { layer: lidar.objLayers[id] } };
    lidar.selected = name === "_other" ? -1 : id;
    paintLidar();
    showInfo(node, hit.point, [["LiDAR points (shown)", lidar.objCount[id].toLocaleString()]]);
  }
});
function fmt(v) { return typeof v === "number" ? (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(2)) : String(v); }
function showInfo(node, point, extra = []) {
  const L = layers.get(node.userData.layer);
  const rows = [["Layer", L?.cfg.label || node.userData.layer || "–"], ["Elevation here", `${point.y.toFixed(1)} m`], ...extra];
  for (const [k, v] of Object.entries(node.userData)) {
    if (SKIP_KEYS.has(k) || v === null || typeof v === "object") continue;
    rows.push([k.replace(/_m$/, " (m)").replace(/_/g, " "), fmt(v)]);
  }
  const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]);
  $("#info").innerHTML = `<h2>${esc(node.name)}</h2><table>${rows.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join("")}</table>`;
  $("#info").style.display = "block";
}
function hideInfo() { $("#info").style.display = "none"; }

// ---------- misc ui ----------
function collapse(on) { $("#ui").classList.toggle("collapsed", on); $("#toggle").textContent = on ? "+" : "–"; }
$("#toggle").onclick = () => collapse(!$("#ui").classList.contains("collapsed"));
if (innerWidth < 560) collapse(true);  // phones: start with the panel folded
addEventListener("resize", () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });

await setMode(cfg.defaultMode || "mesh");
status("");
renderer.setAnimationLoop((now) => {
  if (tween) {
    const t = Math.min((now - tween.t0) / tween.dur, 1), e = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
    camera.position.lerpVectors(tween.p0, tween.p1, e);
    controls.target.lerpVectors(tween.q0, tween.q1, e);
    if (t === 1) tween = null;
  }
  controls.update();
  renderer.render(scene, camera);
});
window.__viewer = { layers, get mode() { return mode; }, setMode, pointsGroup, get lidar() { return lidar; } };
