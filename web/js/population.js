// Population layer: a MODELED typical day on the site, one point per person.
// Data from site-model/scripts/prep_population.py (web/data/population.{json,bin}); nothing here is observed.
// Each person has weekday / weekend trips: spot (home desk, work desk, place) -> door node -> OSM network ->
// node -> spot. Between trips they stay where the last trip ended; "off site" hides them.
import * as THREE from "three";

const HIDDEN = 0, HOME = 1, WORK = 2, PLACE = 3;
const F_REV = 16, F_ATTEND = 32, F_EVENT = 64;
const BODY = 1.0;        // point height above the floor / ground, m
const VERT = 0.5;        // vertical metres count half (elevators are faster than walking)
const OFF = -1e5;

function hash(a, b) {
  let h = (Math.imul(a, 374761393) + Math.imul(b, 668265263)) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}
const hhmm = (s) => { const m = Math.floor(s / 60) % 1440; return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`; };

export async function createPopulation({ cfg, scene, camera, renderer, layers, y1Url, onInfo, onStatus }) {
  const pc = cfg.population;
  const meta = await (await fetch(pc.meta)).json();
  const buf = await (await fetch(pc.meta.replace(/[^/]*$/, "") + meta.bin)).arrayBuffer();
  const sec = (name) => {
    const s = meta.sections[name];
    const T = { float32: Float32Array, uint32: Uint32Array, uint16: Uint16Array, int16: Int16Array, uint8: Uint8Array }[s.type];
    return new T(buf, s.offset, s.count);
  };
  const nodes = sec("nodes"), pOff = sec("pathOffsets"), pNodes = sec("pathNodes");
  const type = sec("type"), mode = sec("mode"), sector = sec("sector"), rank = sec("rank");
  const homeBld = sec("homeBld"), workBld = sec("workBld"), homeSpot = sec("homeSpot"), workSpot = sec("workSpot");
  const distKm = sec("distKm"), bearing = sec("bearing"), tract = sec("tract");
  const days = {};
  for (const d of ["weekday", "weekend"]) {
    days[d] = { off: sec(`${d}.offsets`), t0: sec(`${d}.t0`), t1: sec(`${d}.t1`), path: sec(`${d}.path`),
                flags: sec(`${d}.flags`), purpose: sec(`${d}.purpose`), orig: sec(`${d}.orig`), dest: sec(`${d}.dest`) };
  }
  const A = meta.count, TU = meta.time_unit_s;
  // cumulative length along every path
  const pCum = new Float32Array(pNodes.length);
  for (let p = 0; p + 1 < pOff.length; p++) {
    let acc = 0;
    for (let k = pOff[p]; k < pOff[p + 1]; k++) {
      if (k > pOff[p]) { const a = 3 * pNodes[k - 1], b = 3 * pNodes[k]; acc += Math.hypot(nodes[b] - nodes[a], nodes[b + 1] - nodes[a + 1], nodes[b + 2] - nodes[a + 2]); }
      pCum[k] = acc;
    }
  }
  const lateral = new Float32Array(A);
  for (let i = 0; i < A; i++) lateral[i] = (hash(i, 7) - 0.5) * 3.6;  // spread across the sidewalk, m
  const eligible = new Set(meta.remoteEligible.map((s) => meta.sectors.indexOf(s)));

  // ---------- state ----------
  const st = { day: "weekday", t: (pc.start ?? 8.5) * 3600, speed: pc.speed ?? 300, playing: false,
               attendance: meta.officeAttendance, event: false, xray: true, neon: pc.neon ?? true, selected: -1, dirty: true };
  const present = new Uint8Array(A);
  function updatePresence() {
    for (let i = 0; i < A; i++) {
      const thr = eligible.has(sector[i]) ? st.attendance : meta.otherAttendance;
      present[i] = rank[i] < thr * 256 ? 1 : 0;
    }
  }
  updatePresence();
  const active = (D, i, k) => { const f = D.flags[k]; return !((f & F_ATTEND) && !present[i]) && !((f & F_EVENT) && !st.event); };
  const defaultSpot = (i) => (type[i] === 0 || type[i] === 2 ? HOME : HIDDEN);

  // where person i is at time T (seconds): {k: trip index or -1, moving, spot}
  function locate(D, i, T) {
    const lo = D.off[i], hi = D.off[i + 1], tu = T / TU;
    let last = -1, lastEnd = -1;
    for (let k = lo; k < hi; k++) {
      if (!active(D, i, k)) continue;
      if (D.t0[k] <= tu) { last = k; }
      if (lastEnd < 0 || D.t1[k] >= D.t1[lastEnd]) lastEnd = k;
    }
    if (last >= 0 && tu < D.t1[last]) return { k: last, moving: true };
    const k = last >= 0 ? last : lastEnd;  // before the first trip: where the day's last trip ended
    return { k, moving: false, spot: k >= 0 ? (D.flags[k] >> 2) & 3 : defaultSpot(i) };
  }

  const tmp = new THREE.Vector3();
  function spotPos(i, kind, node, out) {
    if (kind === HOME) return out.set(homeSpot[3 * i] / 10, homeSpot[3 * i + 1] / 10 + BODY, homeSpot[3 * i + 2] / 10);
    if (kind === WORK) return out.set(workSpot[3 * i] / 10, workSpot[3 * i + 1] / 10 + BODY, workSpot[3 * i + 2] / 10);
    const a = hash(i, node) * 6.283, r = 1.5 + hash(node, i) * 5;  // a spot beside the place's node
    return out.set(nodes[3 * node] + Math.cos(a) * r, nodes[3 * node + 1] + BODY, nodes[3 * node + 2] + Math.sin(a) * r);
  }
  const ends = (D, k) => {
    const p = D.path[k], rev = D.flags[k] & F_REV, a = pNodes[pOff[p]], b = pNodes[pOff[p + 1] - 1];
    return rev ? [b, a] : [a, b];
  };
  const S = new THREE.Vector3(), E = new THREE.Vector3();
  // position along trip k at fraction f: spot -> (lift) -> node A -> path -> node B -> (lift) -> spot
  function along(D, i, k, f, out) {
    const p = D.path[k], rev = D.flags[k] & F_REV, fk = D.flags[k] & 3, tk = (D.flags[k] >> 2) & 3;
    const [na, nb] = ends(D, k);
    const L = pCum[pOff[p + 1] - 1];
    let preH = 0, preV = 0, postH = 0, postV = 0;
    if (fk !== HIDDEN) { spotPos(i, fk, na, S); preV = Math.abs(S.y - nodes[3 * na + 1] - BODY); preH = Math.hypot(S.x - nodes[3 * na], S.z - nodes[3 * na + 2]); }
    if (tk !== HIDDEN) { spotPos(i, tk, nb, E); postV = Math.abs(E.y - nodes[3 * nb + 1] - BODY); postH = Math.hypot(E.x - nodes[3 * nb], E.z - nodes[3 * nb + 2]); }
    const total = preV * VERT + preH + L + postH + postV * VERT || 1;
    let s = f * total;
    if (fk !== HIDDEN) {
      if (s < preV * VERT) return out.set(S.x, S.y + (nodes[3 * na + 1] + BODY - S.y) * (s / (preV * VERT || 1)), S.z);
      s -= preV * VERT;
      if (s < preH) { const g = s / (preH || 1); return out.set(S.x + (nodes[3 * na] - S.x) * g, nodes[3 * na + 1] + BODY, S.z + (nodes[3 * na + 2] - S.z) * g); }
      s -= preH;
    }
    if (s <= L) {
      const q = rev ? L - s : s;
      let lo = pOff[p], hi = pOff[p + 1] - 1;
      while (hi - lo > 1) { const m = (lo + hi) >> 1; if (pCum[m] <= q) lo = m; else hi = m; }
      const a = 3 * pNodes[lo], b = 3 * pNodes[hi], seg = pCum[hi] - pCum[lo] || 1, g = Math.min(Math.max((q - pCum[lo]) / seg, 0), 1);
      const dx = nodes[b] - nodes[a], dz = nodes[b + 2] - nodes[a + 2], dl = Math.hypot(dx, dz) || 1, o = lateral[i];
      return out.set(nodes[a] + dx * g - (dz / dl) * o, nodes[a + 1] + (nodes[b + 1] - nodes[a + 1]) * g + BODY, nodes[a + 2] + dz * g + (dx / dl) * o);
    }
    s -= L;
    if (tk === HIDDEN) return out.set(nodes[3 * nb], nodes[3 * nb + 1] + BODY, nodes[3 * nb + 2]);
    if (s < postH) { const g = s / (postH || 1); return out.set(nodes[3 * nb] + (E.x - nodes[3 * nb]) * g, nodes[3 * nb + 1] + BODY, nodes[3 * nb + 2] + (E.z - nodes[3 * nb + 2]) * g); }
    s -= postH;
    const g = Math.min(s / (postV * VERT || 1), 1);
    return out.set(E.x, nodes[3 * nb + 1] + BODY + (E.y - nodes[3 * nb + 1] - BODY) * g, E.z);
  }
  let lastTrip = -1;  // the trip position() found the person moving on (for trails)
  function position(D, i, T, out) {
    const loc = locate(D, i, T);
    lastTrip = loc.moving ? loc.k : -1;
    if (loc.moving) { const k = loc.k; along(D, i, k, (T / TU - D.t0[k]) / Math.max(D.t1[k] - D.t0[k], 1), out); return 2; }
    if (loc.spot === HIDDEN) return 0;
    const node = loc.k >= 0 ? ends(D, loc.k)[1] : 0;
    spotPos(i, loc.spot, node, out);
    return loc.spot === PLACE ? 3 : 1;   // 1 indoors (home / work), 3 at a place
  }

  // ---------- points ----------
  const pos = new Float32Array(A * 3), col = new Float32Array(A * 3);
  const colors = meta.types.map((t) => new THREE.Color(pc.colors?.[t] ?? "#888"));
  for (let i = 0; i < A; i++) colors[type[i]].toArray(col, 3 * i);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3).setUsage(THREE.DynamicDrawUsage));
  geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
  geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 100, 0), 900);
  const uniforms = { size: { value: pc.size ?? 0.7 }, scale: { value: 1 }, minPx: { value: 2.0 }, alpha: { value: 1 } };
  const material = new THREE.ShaderMaterial({
    uniforms, vertexColors: true,
    vertexShader: `uniform float size; uniform float scale; uniform float minPx; varying vec3 vC;
      void main() { vC = color; vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = max(size * scale / -mv.z, minPx); gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform float alpha; varying vec3 vC; void main() { if (length(gl_PointCoord - vec2(0.5)) > 0.5) discard; gl_FragColor = vec4(vC, alpha); }`,
    transparent: true,
  });
  const points = new THREE.Points(geo, material);
  points.frustumCulled = false;
  points.renderOrder = 2;
  scene.add(points);
  // the selected person: a bigger highlight point plus today's route
  const HILITE = new THREE.Color(cfg.linked?.highlight ?? "#FF3EA5");
  const selGeo = new THREE.BufferGeometry().setAttribute("position", new THREE.BufferAttribute(new Float32Array(3), 3));
  selGeo.setAttribute("color", new THREE.BufferAttribute(new Float32Array(HILITE.toArray()), 3));
  const selMat = material.clone();
  selMat.uniforms = { size: { value: 2.2 }, scale: uniforms.scale, minPx: { value: 9 }, alpha: { value: 1 } };
  const selPoint = new THREE.Points(selGeo, selMat);
  selPoint.visible = false;
  selPoint.frustumCulled = false;
  selPoint.renderOrder = 3;
  scene.add(selPoint);
  const selPos = new THREE.Vector3();   // the selected person, where the viewer's floating tag points (kept up to date)
  // route = a thin line, plus an optional neon "light wall" and floor trace (Tron light-cycle trail):
  // faint for the rest of the day, lit where the person has already been, brightest at their current spot
  const NEON = new THREE.Color(pc.routeColor ?? "#00E5FF");
  const routeU = { now: { value: 0 }, color: { value: NEON }, strength: { value: pc.neonStrength ?? 1 } };
  const neonVert = `attribute float aT; attribute float aA; varying float vT; varying float vA;
    void main() { vT = aT; vA = aA; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
  const neonFrag = (shape) => `uniform float now; uniform vec3 color; uniform float strength; varying float vT; varying float vA;
    void main() { float done = step(vT, now), head = done * exp(-(now - vT) / 150.0);
      float a = (${shape}) * (0.04 + 0.10 * done + 0.18 * head) * strength;
      gl_FragColor = vec4(mix(color, vec3(1.0), 0.5 * head), clamp(a, 0.0, 1.0)); }`;
  const neonMat = (shape) => new THREE.ShaderMaterial({ uniforms: routeU, vertexShader: neonVert, fragmentShader: neonFrag(shape),
    transparent: true, depthWrite: false, side: THREE.DoubleSide });
  const wall = new THREE.Mesh(new THREE.BufferGeometry(), neonMat("pow(1.0 - vA, 1.5) * (0.85 + 0.15 * step(0.5, fract(vA * 6.0)))"));
  const glow = new THREE.Mesh(new THREE.BufferGeometry(), neonMat("exp(-vA * vA * 4.0)"));
  const line = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: NEON, transparent: true, opacity: 0.7, depthTest: false }));
  const route = new THREE.Group();
  for (const o of [wall, glow, line]) { o.frustumCulled = false; o.renderOrder = 3; route.add(o); }
  route.visible = false;
  scene.add(route);
  const WALL_H = 2.4, GLOW_W = 1.4;

  // trails while playing: every moving person draws a short light wall behind them, in their type colour,
  // fading out over the last `tail` simulated seconds (longer at faster speeds)
  const MAXT = pc.maxTrails ?? 8000, TS = 6;  // people with a trail, segments per trail
  const tP = new Float32Array(MAXT * TS * 6 * 3), tC = new Float32Array(MAXT * TS * 6 * 3), tT = new Float32Array(MAXT * TS * 6), tA = new Float32Array(MAXT * TS * 6);
  const tGeo = new THREE.BufferGeometry();
  tGeo.setAttribute("position", new THREE.BufferAttribute(tP, 3).setUsage(THREE.DynamicDrawUsage));
  tGeo.setAttribute("color", new THREE.BufferAttribute(tC, 3).setUsage(THREE.DynamicDrawUsage));
  tGeo.setAttribute("aT", new THREE.BufferAttribute(tT, 1).setUsage(THREE.DynamicDrawUsage));
  tGeo.setAttribute("aA", new THREE.BufferAttribute(tA, 1).setUsage(THREE.DynamicDrawUsage));
  const trailU = { now: { value: 0 }, tail: { value: 600 }, strength: { value: pc.neonStrength ?? 1 } };
  const trails = new THREE.Mesh(tGeo, new THREE.ShaderMaterial({
    uniforms: trailU, vertexColors: true, transparent: true, depthWrite: false, side: THREE.DoubleSide,
    vertexShader: `attribute float aT; attribute float aA; varying float vT; varying float vA; varying vec3 vC;
      void main() { vT = aT; vA = aA; vC = color; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `uniform float now; uniform float tail; uniform float strength; varying float vT; varying float vA; varying vec3 vC;
      void main() { float age = clamp((now - vT) / tail, 0.0, 1.0);
        float a = pow(1.0 - vA, 1.5) * (1.0 - age) * 0.22 * strength;
        gl_FragColor = vec4(mix(vC, vec3(1.0), 0.35 * (1.0 - age)), a); }`,
  }));
  trails.frustumCulled = false;
  trails.renderOrder = 2;
  trails.visible = false;
  scene.add(trails);
  const ta = new THREE.Vector3(), tb = new THREE.Vector3();
  function buildTrails(movers) {
    const D = days[st.day], T = st.t, tail = Math.min(Math.max(st.speed * 0.8, 60), 2400);
    trailU.now.value = T; trailU.tail.value = tail;
    let v = 0;
    for (let m = 0; m < movers.length && m < MAXT * 2; m += 2) {
      const i = movers[m], k = movers[m + 1], T0 = D.t0[k] * TU, dur = Math.max((D.t1[k] - D.t0[k]) * TU, 1);
      const start = Math.max(T - tail, T0), c = colors[type[i]];
      along(D, i, k, (start - T0) / dur, ta);
      let tPrev = start;
      for (let s = 1; s <= TS; s++) {
        const tn = start + ((T - start) * s) / TS;
        along(D, i, k, (tn - T0) / dur, tb);
        if (Math.hypot(tb.x - ta.x, tb.z - ta.z) > 0.02) {
          const q = [[ta.x, ta.y - BODY, ta.z], [tb.x, tb.y - BODY, tb.z], [ta.x, ta.y - BODY + WALL_H, ta.z], [tb.x, tb.y - BODY + WALL_H, tb.z]];
          const qt = [tPrev, tn, tPrev, tn], qa = [0, 0, 1, 1];
          for (const j of [0, 1, 2, 2, 1, 3]) {
            tP.set(q[j], 3 * v); tC[3 * v] = c.r; tC[3 * v + 1] = c.g; tC[3 * v + 2] = c.b; tT[v] = qt[j]; tA[v] = qa[j]; v++;
          }
        }
        ta.copy(tb); tPrev = tn;
      }
    }
    tGeo.setDrawRange(0, v);
    for (const a of Object.values(tGeo.attributes)) a.needsUpdate = true;
  }

  // Y-1 outline (scene-local [x, north, z]) for the "on Y-1" count
  const y1 = Object.values(await (await fetch(y1Url)).json()).map((ring) => ring.map(([x, n]) => [x, -n]));
  const inY1 = (x, z) => y1.some((r) => { let c = false; for (let a = 0, b = r.length - 1; a < r.length; b = a++) { if ((r[a][1] > z) !== (r[b][1] > z) && x < ((r[b][0] - r[a][0]) * (z - r[a][1])) / (r[b][1] - r[a][1]) + r[a][0]) c = !c; } return c; });

  const counts = { total: 0, byType: [0, 0, 0, 0], indoors: 0, outdoors: 0, y1: 0 };
  function update() {
    const D = days[st.day], T = st.t;
    counts.total = counts.indoors = counts.outdoors = counts.y1 = 0;
    counts.byType.fill(0);
    const wantTrails = st.playing && st.neon && st.selected < 0 && points.visible, movers = [];
    for (let i = 0; i < A; i++) {
      const r = position(D, i, T, tmp);
      if (wantTrails && lastTrip >= 0) movers.push(i, lastTrip);
      if (r === 0) { pos[3 * i + 1] = OFF; continue; }
      pos[3 * i] = tmp.x; pos[3 * i + 1] = tmp.y; pos[3 * i + 2] = tmp.z;
      counts.total++; counts.byType[type[i]]++;
      if (r === 1) counts.indoors++;
      else { counts.outdoors++; if (inY1(tmp.x, tmp.z)) counts.y1++; }
    }
    geo.attributes.position.needsUpdate = true;
    trails.visible = wantTrails;
    if (wantTrails) buildTrails(movers);
    if (st.selected >= 0) {
      const ok = position(D, st.selected, T, tmp);
      selPoint.visible = points.visible && ok !== 0;
      selGeo.attributes.position.array.set([tmp.x, tmp.y, tmp.z]);
      selPos.copy(tmp);
      selGeo.attributes.position.needsUpdate = true;
    }
    st.dirty = false;
    ui.refresh();
  }

  // 24 h curve for the current settings, by type (people on site per 15 min)
  function curve() {
    const D = days[st.day], out = meta.types.map(() => new Float32Array(96));
    for (let b = 0; b < 96; b++) {
      const T = (b + 0.5) * 900;
      for (let i = 0; i < A; i++) {
        const loc = locate(D, i, T);
        if (loc.moving || loc.spot !== HIDDEN) out[type[i]][b]++;
      }
    }
    return out;
  }

  // ---------- see-through buildings (people indoors are visible in Model · Mesh) ----------
  const saved = new Map();
  function setXray(on) {
    const L = layers.get("Buildings");
    if (!L) return;
    for (const m of L.meshes) {
      if (!saved.has(m)) { saved.set(m, m.material); m.material = m.material.clone(); }
      const mat = m.material;
      if (on) { mat.transparent = true; mat.opacity = 0.22; mat.depthWrite = false; }
      else { const o = saved.get(m); mat.transparent = o.transparent; mat.opacity = o.opacity; mat.depthWrite = o.depthWrite; }
      mat.needsUpdate = true;
    }
  }

  // ---------- story for a clicked person ----------
  const B = meta.buildings, labelType = { resident: "Resident", worker: "Worker", hotel: "Hotel guest", visitor: "Visitor" };
  const compass = (deg) => ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][Math.round(deg / 45) % 8];
  const bname = (k) => (k >= 0 ? (B[k].addr[0]?.replace(/ LOS ANGELES CA \d+$/, "") || `BLD_${B[k].id}`) : "–");
  const floorOf = (k, spot, i) => (k >= 0 ? Math.max(1, Math.round((spot[3 * i + 1] / 10 - B[k].base) / B[k].fh) + 1) : 0);
  const anchor = (a) => (a >= 0 ? meta.anchors[a] : "");
  function story(i) {
    const D = days[st.day], t = meta.types[type[i]], rows = [];
    const sl = meta.sectorLabels[sector[i]];
    if (workBld[i] >= 0) rows.push(["Works at", `${bname(workBld[i])}, floor ${floorOf(workBld[i], workSpot, i)}`]);
    if (sl) rows.push(["Industry", sl]);
    if (homeBld[i] >= 0) rows.push([t === "hotel" ? "Staying at" : "Lives at", `${bname(homeBld[i])}, floor ${floorOf(homeBld[i], homeSpot, i)}`]);
    else if (t === "worker") rows.push(["Lives", `about ${(distKm[i] / 100).toFixed(1)} km ${compass((bearing[i] / 255) * 360)} (tract ${meta.tracts[tract[i]].slice(5)})`]);
    if (mode[i]) rows.push(["Gets here by", meta.modes[mode[i]]]);
    const trips = [];
    let attendDep = false;
    for (let k = D.off[i]; k < D.off[i + 1]; k++) {
      if (D.flags[k] & F_ATTEND) attendDep = true;
      if (!active(D, i, k)) continue;
      const curb = !(D.dest[k] >= 0 || D.orig[k] >= 0) && (((D.flags[k] >> 2) & 3) === HIDDEN || (D.flags[k] & 3) === HIDDEN);
      const where = anchor(D.dest[k]) || anchor(D.orig[k]) || (curb ? (mode[i] === 5 ? "building garage" : "car / taxi at the door") : "");
      trips.push(`${hhmm(D.t0[k] * TU)} ${meta.purposes[D.purpose[k]]}${where ? ` · ${where}` : ""}`);
    }
    if (attendDep && !present[i]) rows.push(["Today", "working remotely (office attendance setting)"]);
    if (!trips.length && !(attendDep && !present[i])) rows.push(["Today", st.day === "weekend" && t === "worker" ? "not working today" : "stays put"]);
    const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]);
    const title = t === "worker" && eligible.has(sector[i]) ? "Office worker" : labelType[t];
    return `<h2>${esc(title)} <span style="font-weight:400;color:var(--muted)">#${i}</span></h2><table>${rows.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join("")}</table>` +
      (trips.length ? `<div class="label">Today (${st.day})</div><div class="trips">${trips.map(esc).join("<br>")}</div>` : "") +
      `<div class="note">Modeled person, not a real individual. Data: LODES, ACS, NHTS, Assessor, OSM.</div>`;
  }
  function drawRoute(i) {
    const D = days[st.day], seg = [], w = { p: [], t: [], a: [] }, g = { p: [], t: [], a: [] };
    const a = new THREE.Vector3(), b = new THREE.Vector3();
    const quad = (o, p, t, v) => { for (const k of [0, 1, 2, 2, 1, 3]) { o.p.push(...p[k]); o.t.push(t[k]); o.a.push(v[k]); } };
    for (let k = D.off[i]; k < D.off[i + 1]; k++) {
      if (!active(D, i, k)) continue;
      const steps = 80, T0 = D.t0[k] * TU, dT = (D.t1[k] - D.t0[k]) * TU;
      along(D, i, k, 0, a);
      for (let s = 1; s <= steps; s++) {
        along(D, i, k, s / steps, b);
        seg.push(a.x, a.y, a.z, b.x, b.y, b.z);
        const dx = b.x - a.x, dz = b.z - a.z, hl = Math.hypot(dx, dz);
        if (hl > 0.02) {  // horizontal stretch: a light wall standing on the floor and a glow on it
          const ta = T0 + dT * (s - 1) / steps, tb = T0 + dT * s / steps, ya = a.y - BODY, yb = b.y - BODY;
          quad(w, [[a.x, ya, a.z], [b.x, yb, b.z], [a.x, ya + WALL_H, a.z], [b.x, yb + WALL_H, b.z]], [ta, tb, ta, tb], [0, 0, 1, 1]);
          const nx = (-dz / hl) * GLOW_W, nz = (dx / hl) * GLOW_W;
          quad(g, [[a.x - nx, ya + 0.04, a.z - nz], [b.x - nx, yb + 0.04, b.z - nz], [a.x + nx, ya + 0.04, a.z + nz], [b.x + nx, yb + 0.04, b.z + nz]], [ta, tb, ta, tb], [-1, -1, 1, 1]);
        }
        a.copy(b);
      }
    }
    const set = (mesh, o) => {
      mesh.geometry.dispose();
      mesh.geometry = new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(o.p, 3))
        .setAttribute("aT", new THREE.Float32BufferAttribute(o.t, 1)).setAttribute("aA", new THREE.Float32BufferAttribute(o.a, 1));
    };
    set(wall, w);
    set(glow, g);
    line.geometry.dispose();
    line.geometry = new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(seg, 3));
    wall.visible = glow.visible = st.neon;
    route.visible = points.visible && seg.length > 0;
  }
  function select(i) {
    st.selected = i;
    // isolate the selected person: everyone else fades and loses their trail
    uniforms.alpha.value = i < 0 ? 1 : pc.isolateAlpha ?? 0.15;
    material.depthWrite = i < 0;
    st.dirty = true;
    if (i < 0) { selPoint.visible = route.visible = false; return; }
    drawRoute(i);
    onInfo(story(i), selPos);
    st.dirty = true;
  }

  // ---------- UI ----------
  const $ = (s) => document.querySelector(s);
  const chart = $("#popChart"), ctx = chart.getContext("2d");
  let curveData = null, curveTimer = 0;
  const recurve = () => { clearTimeout(curveTimer); curveTimer = setTimeout(() => { curveData = curve(); ui.drawChart(); }, 60); };
  const ui = {
    refresh() {
      $("#popClock").textContent = hhmm(st.t);
      $("#popTime").value = st.t;
      const c = counts;
      $("#popCounts").innerHTML = meta.types.map((t, k) => `<span><i class="sw" style="display:inline-block;background:${pc.colors[t]}"></i>${labelType[t]} ${c.byType[k].toLocaleString()}</span>`).join("") +
        `<span class="tot">On site ${c.total.toLocaleString()} · outdoors ${c.outdoors.toLocaleString()} · on Y-1 ${c.y1.toLocaleString()}</span>`;
      ui.drawChart();
    },
    drawChart() {
      const w = (chart.width = chart.clientWidth * devicePixelRatio), h = (chart.height = chart.clientHeight * devicePixelRatio);
      ctx.clearRect(0, 0, w, h);
      if (!curveData) return;
      let max = 1;
      for (let b = 0; b < 96; b++) { let s = 0; for (const c of curveData) s += c[b]; max = Math.max(max, s); }
      for (let k = curveData.length - 1; k >= 0; k--) {
        ctx.beginPath(); ctx.moveTo(0, h);
        for (let b = 0; b < 96; b++) { let s = 0; for (let j = 0; j <= k; j++) s += curveData[j][b]; ctx.lineTo(((b + 0.5) / 96) * w, h - (s / max) * (h - 2)); }
        ctx.lineTo(w, h); ctx.closePath(); ctx.fillStyle = pc.colors[meta.types[k]]; ctx.fill();
      }
      const fg = getComputedStyle(document.documentElement).getPropertyValue("--fg");
      ctx.fillStyle = fg; ctx.fillRect((st.t / 86400) * w - devicePixelRatio / 2, 0, devicePixelRatio, h);
      ctx.font = `${10 * devicePixelRatio}px -apple-system, sans-serif`; ctx.globalAlpha = 0.7;
      ctx.fillText(`peak ${Math.round(max).toLocaleString()}`, 3 * devicePixelRatio, 11 * devicePixelRatio); ctx.globalAlpha = 1;
    },
  };
  $("#popTime").oninput = (e) => { st.t = +e.target.value; st.dirty = true; };
  $("#popPlay").onclick = () => { st.playing = !st.playing; st.dirty = true; $("#popPlay").textContent = st.playing ? "Pause" : "Play"; };
  document.querySelectorAll("#popSpeed button").forEach((b) => (b.onclick = () => {
    st.speed = +b.dataset.s;
    document.querySelectorAll("#popSpeed button").forEach((x) => x.classList.toggle("on", x === b));
  }));
  document.querySelectorAll("#popDay button").forEach((b) => (b.onclick = () => {
    st.day = b.dataset.d; st.dirty = true; recurve();
    document.querySelectorAll("#popDay button").forEach((x) => x.classList.toggle("on", x === b));
    if (st.selected >= 0) select(st.selected);
  }));
  $("#popAttend").value = Math.round(st.attendance * 100);
  $("#popAttendV").textContent = `${Math.round(st.attendance * 100)}%`;
  $("#popAttend").oninput = (e) => {
    st.attendance = +e.target.value / 100; $("#popAttendV").textContent = `${e.target.value}%`;
    updatePresence(); st.dirty = true; recurve(); if (st.selected >= 0) select(st.selected);
  };
  $("#popEvent").onchange = (e) => { st.event = e.target.checked; st.dirty = true; recurve(); };
  $("#popXray").onchange = (e) => { st.xray = e.target.checked; if (points.visible) setXray(st.xray); };
  $("#popNeon").checked = st.neon;
  $("#popNeon").onchange = (e) => { st.neon = wall.visible = glow.visible = e.target.checked; st.dirty = true; };
  $("#popEventLabel").textContent = meta.event;
  $("#popSpeed button[data-s='" + st.speed + "']")?.classList.add("on");
  $(`#popDay button[data-d='${st.day}']`).classList.add("on");
  $("#popMethod").innerHTML = methodHtml(meta);

  // ---------- public ----------
  let lastNow = 0;
  const api = {
    meta, state: st,
    setVisible(on) {
      points.visible = on;
      selPoint.visible = on && st.selected >= 0;
      route.visible = on && st.selected >= 0;
      setXray(on && st.xray);
      if (!on) trails.visible = false;
      if (on) { st.dirty = true; if (!curveData) recurve(); }
    },
    get visible() { return points.visible; },
    tick(now) {
      const dt = lastNow ? Math.min((now - lastNow) / 1000, 0.25) : 0;
      lastNow = now;
      uniforms.scale.value = renderer.domElement.height / (2 * Math.tan((camera.fov * Math.PI) / 360));
      if (!points.visible) return;
      if (st.playing) { st.t = (st.t + dt * st.speed) % 86400; st.dirty = true; }
      if (st.dirty) update();
      routeU.now.value = st.t;
    },
    // returns true if the click hit a person
    pick(ray) {
      if (!points.visible) return false;
      ray.params.Points.threshold = 1.2;
      const hit = ray.intersectObject(points, false).find((h) => pos[3 * h.index + 1] > OFF / 2);
      if (!hit) { if (st.selected >= 0) select(-1); return false; }
      selPos.copy(hit.point);
      select(hit.index);
      return true;
    },
    clearSelection() { if (st.selected >= 0) select(-1); },
    select,  // select(i): show person i's day (debugging / links)
  };
  onStatus?.("");
  return api;
}

function methodHtml(meta) {
  const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]);
  const t = meta.totals;
  const src = Object.entries(meta.sources).map(([k, v]) => `<li><b>${esc(k)}</b>: ${esc(v)}</li>`).join("");
  const asm = Object.entries(meta.assumptions).map(([k, v]) => `<li><b>${esc(k)}</b>: ${esc(JSON.stringify(v.value))}. ${esc(v.note)}</li>`).join("");
  return `<p><b>A modeled typical day, not real-time or observed data.</b> One point per person:
    ${t.by_type.worker.toLocaleString()} jobs placed in buildings (LODES ${t.lodes_jobs_in_blocks.toLocaleString()} jobs in the blocks touching the site,
    scaled by each block's share inside the 800 m square), ${t.by_type.resident.toLocaleString()} residents (2020 Census),
    ${t.by_type.hotel.toLocaleString()} hotel guests and ${t.by_type.visitor.toLocaleString()} visitors across both day types.
    Schedules are sampled from ACS commute times and NHTS trip times; routes follow OpenStreetMap paths.</p>
    <p><b>Sources</b></p><ul>${src}</ul><p><b>Assumptions</b> (site-model/data/population/assumptions.json)</p><ul>${asm}</ul>
    <p><b>Known limits</b>: LODES counts jobs where employers report them; office floor area is from the Assessor, not
    listings; commute modes and arrival times are City of LA averages, not Downtown-specific (CTPP needs an interactive download);
    hotel rooms are estimated from floor area (historic hotels with ballrooms come out high).</p>`;
}
