// Real-browser checks of the experimental 3D mesh job and mesh view on the geometry lab page (W12, W14).
// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
//
// A local check, not wired into CI: it needs Playwright with a Chromium it can launch
// (not a repository dependency) and meshloom's compiled kernel on the server. From the
// repository root, with a Studio server running:
//   python -m simcase.studio --no-browser --port 8765 &
//   node tools/studio_browser/model3d_mesh_browser.mjs http://127.0.0.1:8765 out-dir
// Pre-registered checks (thresholds fixed before measuring):
//  W12 the first mesh view at 1440 x 900 and 390 x 844 (the card, meshed): no console error, no CSP
//      violation (script-src 'self'), the mesh canvas visible and not empty, no horizontal scroll at
//      390, the faces list reachable by Tab; screenshots stored;
//  W14 performance at the card at about 48,000 tetrahedra (element size 0.375 um, meshed) and at
//      150,000 surface triangles (a mesh answer made here by subdividing the card's display
//      triangles, served to the page in place of the server's): the mesh answer time, the mesh
//      view's frame time (median of 120 frames, rotating) and the tab's JS heap. Recorded with the
//      machine and browser; the gate (JS heap <= 300 MB, median frame <= 33 ms) holds only in
//      Chromium with hardware GL, so with a software renderer the numbers are recorded and the
//      gate is reported as not run.
// Also (not pre-registered): the estimate line, Mesh disabled with the refusal above the limit,
// the steps and Cancel meshing on a job estimated at about a minute, and a pick on the mesh view
// gives the same face as on the 3D view.
// It writes report.json and screenshots to out-dir and exits non-zero if a check fails.
import {createRequire} from 'node:module';
import {mkdir, writeFile} from 'node:fs/promises';
import {cpus, totalmem, platform, release} from 'node:os';
import {join} from 'node:path';
import assert from 'node:assert/strict';

const require = createRequire(import.meta.url);
const {chromium} = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:8765';
const out = process.argv[3] || 'model3d-mesh-browser';
await mkdir(out, {recursive: true});
const origin = new URL(base).origin;
const report = {base, machine: {platform: platform(), release: release(), cpu: cpus()[0]?.model, cpus: cpus().length,
  memoryGiB: +(totalmem() / 2 ** 30).toFixed(1)}, checks: {}, measurements: {}};
const card = await (await fetch(base + '/model3d-assets/model3d-via-stack.json')).json();
const withMesh = mesh => ({...structuredClone(card), mesh: {...card.mesh, ...mesh}});

async function open(browser, viewport) {
  const page = await browser.newPage({viewport});
  const seen = {console: [], pageErrors: [], foreign: []};
  page.on('console', m => { if (m.type() === 'error') seen.console.push(m.text()); });
  page.on('pageerror', e => seen.pageErrors.push(String(e)));
  page.on('request', r => { if (/^(https?|wss?):/.test(r.url()) && new URL(r.url()).origin !== origin) seen.foreign.push(r.url()); });
  await page.addInitScript(() => {
    window.__csp = [];
    document.addEventListener('securitypolicyviolation', e => window.__csp.push(e.violatedDirective + ' ' + e.blockedURI));
  });
  const response = await page.goto(base + '/geometry-lab');
  assert.equal(response.status(), 200);
  return {page, seen};
}

const shown = page => page.waitForFunction(() => /^Shown /.test(document.querySelector('#status').textContent), null, {timeout: 60000});
const estimated = page => page.waitForFunction(() => /^(Estimate |Mesh is not available)/.test(document.querySelector('#mesh-estimate').textContent), null, {timeout: 60000});
const meshed = (page, timeout = 600000) => page.waitForFunction(() => /^Meshed /.test(document.querySelector('#status').textContent), null, {timeout});

async function openDocument(page, doc, name) {
  await page.setInputFiles('#file', {name, mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(doc))});
  await shown(page);
  await estimated(page);
}

async function canvasState(page, id) {
  return page.evaluate(id => {
    const c = document.getElementById(id), r = c.getBoundingClientRect();
    const probe = document.createElement('canvas');
    probe.width = c.width; probe.height = c.height;
    const g = probe.getContext('2d'); g.drawImage(c, 0, 0);
    const data = g.getImageData(0, 0, probe.width, probe.height).data;
    let drawn = 0;
    for (let i = 0; i < data.length; i += 4)
      if (Math.abs(data[i] - 0xfb) + Math.abs(data[i + 1] - 0xfc) + Math.abs(data[i + 2] - 0xfd) > 24) drawn++;
    const style = getComputedStyle(c);
    return {x: r.x + scrollX, y: r.y + scrollY, width: r.width, height: r.height,
      visible: style.display !== 'none' && style.visibility !== 'hidden' && r.width > 0 && r.height > 0,
      drawnPixels: drawn, pixels: data.length / 4, scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth};
  }, id);
}

async function heapMB(page) {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('HeapProfiler.collectGarbage');
  const usage = await cdp.send('Runtime.getHeapUsage');
  await cdp.detach();
  const mb = x => x === undefined ? null : +(x / 2 ** 20).toFixed(1);
  // usedSize: the V8 heap; backingStorageSize: ArrayBuffer stores (the mesh's typed arrays live there)
  return {usedMB: mb(usage.usedSize), backingStorageMB: mb(usage.backingStorageSize),
    embedderMB: mb(usage.embedderHeapUsedSize),
    totalMB: mb(usage.usedSize + (usage.backingStorageSize || 0) + (usage.embedderHeapUsedSize || 0))};
}

// rotate the mesh view one step per animation frame (its own keyboard control) and time 120 frames
async function frameTimes(page) {
  return page.evaluate(() => new Promise(resolve => {
    const c = document.getElementById('canvas-mesh'), times = [];
    let last = performance.now(), n = 0;
    const step = () => {
      c.dispatchEvent(new KeyboardEvent('keydown', {key: n % 2 ? 'ArrowLeft' : 'ArrowRight', bubbles: true}));
      const t1 = performance.now();
      times.push(t1 - last); last = t1;
      if (++n < 121) requestAnimationFrame(step);
      else {
        const med = a => { const s = [...a].sort((x, y) => x - y); return s[s.length >> 1]; };
        resolve({frames: 120, medianFrameMs: +med(times.slice(1)).toFixed(1), worstFrameMs: +Math.max(...times.slice(1)).toFixed(1)});
      }
    };
    requestAnimationFrame(step);
  }));
}

async function renderer(page) {
  return page.evaluate(() => {
    const gl = document.createElement('canvas').getContext('webgl2');
    const info = gl && gl.getExtension('WEBGL_debug_renderer_info');
    return info ? {vendor: gl.getParameter(info.UNMASKED_VENDOR_WEBGL), renderer: gl.getParameter(info.UNMASKED_RENDERER_WEBGL)}
      : {vendor: null, renderer: gl ? gl.getParameter(gl.RENDERER) : null};
  });
}

// a mesh answer of about `target` surface triangles from the card's display answer: each display
// triangle is split into four until the count is reached (the last pass splits only the first ones)
function subdivided(display, target) {
  const b64 = (text, T) => { const b = Buffer.from(text, 'base64'); return new T(b.buffer, b.byteOffset, b.byteLength / T.BYTES_PER_ELEMENT); };
  let P = [...b64(display.positions, Float32Array)], tris = [];
  const idx = b64(display.indices, Uint32Array), own = b64(display.triangle_faces, Uint32Array);
  for (let t = 0; t < own.length; t++) tris.push([idx[3 * t], idx[3 * t + 1], idx[3 * t + 2], own[t]]);
  const mid = new Map();
  const m = (a, b) => { const k = a < b ? a + ',' + b : b + ',' + a; if (!mid.has(k)) { mid.set(k, P.length / 3);
    for (let i = 0; i < 3; i++) P.push((P[3 * a + i] + P[3 * b + i]) / 2); } return mid.get(k); };
  while (tris.length < target) {
    const split = Math.min(tris.length, Math.ceil((target - tris.length) / 3)), next = [];
    tris.forEach((t, i) => {
      if (i >= split) { next.push(t); return; }
      const [a, b, c, f] = t, ab = m(a, b), bc = m(b, c), ca = m(c, a);
      next.push([a, ab, ca, f], [ab, b, bc, f], [ca, bc, c, f], [ab, bc, ca, f]);
    });
    tris = next.sort((x, y) => x[3] - y[3]);
  }
  const faces = display.faces.map(f => ({...f}));
  const regionIndex = Object.fromEntries(display.regions.map((r, i) => [r.name, i]));
  const counts = new Array(faces.length).fill(0);
  for (const t of tris) counts[t[3]]++;
  let first = 0;
  for (const f of faces) { f.first_triangle = first; f.triangle_count = counts[f.id]; first += counts[f.id]; }
  const edges = new Map();
  for (const [a, b, c, f] of tris) for (const [p, q] of [[a, b], [b, c], [c, a]]) { const k = p < q ? p * 4294967296 + q : q * 4294967296 + p; if (!edges.has(k)) edges.set(k, [Math.min(p, q), Math.max(p, q), f]); }
  const enc = (T, arr) => Buffer.from(new T(arr).buffer).toString('base64');
  const regionOf = f => { const face = faces[f]; const n = [...face.plus, ...face.minus].find(r => !display.regions[regionIndex[r]].void); return regionIndex[n] ?? -1; };
  const E = [...edges.values()];
  return {...display, mesh: true, key: 'synthetic-150k', region_names: display.regions.map(r => r.name), faces,
    counts: {faces: faces.length, triangles: tris.length, vertices: P.length / 3, edges: E.length},
    positions: enc(Float32Array, P), indices: enc(Uint32Array, tris.flatMap(t => t.slice(0, 3))),
    triangle_faces: enc(Uint32Array, tris.map(t => t[3])), triangle_regions: enc(Int32Array, tris.map(t => regionOf(t[3]))),
    edge_indices: enc(Uint32Array, E.flatMap(e => [e[0], e[1]])), edge_faces: enc(Uint32Array, E.map(e => e[2])),
    stats: {nodes: P.length / 3, tetrahedra: 0, regions: 3, quality_min: 1, quality_median: 1, surface_triangles: tris.length},
    estimate: 0, diagnostics: [], edges: undefined, summary: undefined};
}

const browser = await chromium.launch();
report.browser = {name: 'chromium', version: browser.version()};
let failed = false;
const record = (name, ok, detail) => { report.checks[name] = {ok, ...detail}; if (!ok) failed = true; };
try {
  // ---- W12: the first mesh view at 1440 x 900 and 390 x 844 --------------------------------
  for (const viewport of [{width: 1440, height: 900}, {width: 390, height: 844}]) {
    const {page, seen} = await open(browser, viewport);
    await page.selectOption('#starter', 'model3d_via_stack');
    await shown(page);
    await estimated(page);
    const estimate = await page.textContent('#mesh-estimate');
    await page.click('#mesh-start');
    await meshed(page);
    const state = await canvasState(page, 'canvas-mesh');
    const steps = await page.$$eval('#mesh-steps li', l => l.map(e => [e.textContent, e.className]));
    const stats = await page.$$eval('#mesh-stats dt, #mesh-stats dd', l => l.map(e => e.textContent));
    await page.locator('#mesh3d').scrollIntoViewIfNeeded();
    await page.screenshot({path: join(out, `w12-mesh-view-${viewport.width}x${viewport.height}.png`), fullPage: true});
    await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });
    let tabs = 0, reached = false;
    for (; tabs < 80 && !reached; tabs++) {
      await page.keyboard.press('Tab');
      reached = await page.evaluate(() => !!document.activeElement?.closest('#faces'));
    }
    const csp = await page.evaluate(() => window.__csp);
    const result = {viewport, estimate, steps, stats, canvas: state, tabsToFacesList: reached ? tabs : null,
      console: seen.console, pageErrors: seen.pageErrors, csp, foreign: seen.foreign};
    const ok = !seen.console.length && !seen.pageErrors.length && !csp.length && !seen.foreign.length && state.visible
      && state.drawnPixels > 0.02 * state.pixels && reached && (viewport.width !== 390 || state.scrollWidth <= state.innerWidth);
    record(`W12 mesh view ${viewport.width}x${viewport.height}`, ok, result);

    if (viewport.width === 1440) {
      // a pick at the centre of the mesh view gives the face the 3D view gives there (smoke)
      const view = await canvasState(page, 'canvas3d');
      const face = async () => page.evaluate(() => document.querySelector('#names').dataset.face);
      await page.locator('#canvas3d').click({position: {x: view.width * 0.45, y: view.height * 0.55}});
      const inView = await face();
      await page.locator('#canvas-mesh').click({position: {x: state.width * 0.45, y: state.height * 0.55}});
      const inMesh = await face();
      const names = await page.$$eval('#face-names code', l => l.map(e => e.textContent));
      record('pick on the mesh view (smoke)', inView !== '' && inView === inMesh && names.length > 0, {inView, inMesh, names});
      // Mesh disabled with the reason above the limit; the steps and Cancel meshing (smoke)
      await openDocument(page, withMesh({element_count_limit: 10000}), 'over-limit.json');
      const blocked = {disabled: await page.isDisabled('#mesh-start'), text: await page.textContent('#mesh-estimate'),
        title: await page.getAttribute('#mesh-start', 'title')};
      await openDocument(page, withMesh({element_size: '0.28 um'}), 'long.json');
      const longEstimate = await page.textContent('#mesh-estimate');
      await page.click('#mesh-start');
      await page.waitForFunction(() => /Meshing \(expected about 1 min\) · 0:0[3-9]/.test(document.querySelector('#mesh-progress').textContent), null, {timeout: 60000});
      const during = {progress: await page.textContent('#mesh-progress'), cancel: await page.isVisible('#mesh-cancel'),
        cancelLabel: await page.textContent('#mesh-cancel'), percent: await page.$$eval('progress, [role=progressbar]', l => l.length)};
      await page.screenshot({path: join(out, 'meshing-progress.png')});
      await page.click('#mesh-cancel');
      await page.waitForFunction(() => document.querySelector('#mesh-progress').textContent === 'Meshing cancelled; nothing kept.', null, {timeout: 10000});
      const after = {progress: await page.textContent('#mesh-progress'), cancelHidden: await page.isHidden('#mesh-cancel'),
        meshEnabled: await page.isEnabled('#mesh-start')};
      await page.screenshot({path: join(out, 'meshing-cancelled.png')});
      record('estimate, refusal, steps and cancel (smoke)', blocked.disabled && /^Mesh is not available: .*about 20160 tetrahedra.*the limit is 10000/.test(blocked.text)
        && /^Estimate 110,000 tetrahedra · about 1 min$/.test(longEstimate) && during.cancel && during.cancelLabel === 'Cancel meshing'
        && during.percent === 0 && after.cancelHidden && after.meshEnabled && /^Estimate 48,000|^Estimate 20,000/.test(estimate),
      {estimate, blocked, longEstimate, during, after});
    }
    await page.close();
  }

  // ---- W14: performance ---------------------------------------------------------------------
  const display = await (await fetch(base + '/api/model3d/display')).json();
  const synthetic = subdivided(display, 150000);
  for (const which of ['card-48k-tetrahedra', 'surface-150k-triangles']) {
    const {page, seen} = await open(browser, {width: 1440, height: 900});
    report.measurements.renderer = await renderer(page);
    if (which === 'card-48k-tetrahedra') {
      await page.selectOption('#starter', 'model3d_via_stack');
      await shown(page);
      await openDocument(page, withMesh({element_size: '0.375 um'}), 'card-48k.json');
    } else {
      const body = JSON.stringify(synthetic);
      await page.route('**/api/model3d/mesh', r => r.fulfill({status: 200, contentType: 'application/json',
        body: JSON.stringify({job: 'm3d-000000000000', status: 'done', reused: true, estimate: {tetrahedra: 0, seconds: 0}})}));
      await page.route('**/api/model3d/jobs/m3d-000000000000/result', r => r.fulfill({status: 200, contentType: 'application/json', body}));
      await page.selectOption('#starter', 'model3d_via_stack');
      await shown(page);
      await estimated(page);
    }
    const heapBefore = await heapMB(page);
    const t0 = Date.now();
    await page.click('#mesh-start');
    await meshed(page);
    const toDrawn = Date.now() - t0;
    const triangles = await page.$$eval('#mesh-stats dt, #mesh-stats dd', l => l.map(e => e.textContent).join(' '));
    // the mesh answer: request to last byte (resource timing) and its size
    const answer = await page.evaluate(() => performance.getEntriesByType('resource')
      .filter(e => /\/api\/model3d\/jobs\/[^/]+\/result$/.test(e.name))
      .map(e => ({ms: +e.duration.toFixed(1), bytes: e.encodedBodySize || e.decodedBodySize || null}))[0] ?? null);
    const frames = await frameTimes(page);
    const heap = await heapMB(page);
    await page.screenshot({path: join(out, `w14-${which}.png`)});
    report.measurements[which] = {meshAnswer: answer, clickToMeshDrawnMs: toDrawn, ...frames, jsHeap: heap,
      jsHeapBeforeMesh: heapBefore, stats: triangles, console: seen.console, pageErrors: seen.pageErrors};
    await page.close();
  }
  const r = report.measurements.renderer?.renderer || '';
  const hardware = !/swiftshader|llvmpipe|software|softpipe/i.test(r);
  const gate = ['card-48k-tetrahedra', 'surface-150k-triangles'].every(k => report.measurements[k].jsHeap.totalMB <= 300
    && report.measurements[k].medianFrameMs <= 33);
  report.checks['W14'] = {ok: true, recorded: true, hardwareGL: hardware, gateRun: hardware, gateHolds: hardware ? gate : null,
    note: hardware ? 'gate run in Chromium with hardware GL' : `software renderer (${r}): numbers recorded, gate not run`};
  if (hardware && !gate) { report.checks['W14'].ok = false; failed = true; }
} finally {
  await writeFile(join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}
for (const [name, c] of Object.entries(report.checks)) console.log(`${c.ok ? 'PASS' : 'FAIL'} ${name}`);
console.log(JSON.stringify(report.measurements, null, 1));
if (failed) process.exit(1);
