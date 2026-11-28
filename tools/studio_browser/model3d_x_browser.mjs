// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Studio 3D fixes X1–X7 (agent round 3D-3) in a real browser, against a local Studio on this branch:
//   node tools/studio_browser/model3d_x_browser.mjs http://127.0.0.1:8765 out-dir [X1,X2,...]
// Pre-registered checks (thresholds fixed before measuring, accepted by the coordinator):
//  X1  card 2: a cylinder across each domain side (cx 0.8, −0.8; cy 0.8, −0.8): each value Messages names
//      as forming ("cx = 0.69 m forms") is fed back to the server's check, which answers ok with a mesh
//      estimate; the r value of the x1 case too; and cx = 0.7 (touching x1): plain words ("touches the
//      domain side x = 1 m along a line") and a value that forms: 6/6.
//  X2  card 1, P05's path (face 5 in the Faces list, Use for → Fixed temperature 330, Apply, Run, the
//      Result view): the top face's projected centre pixel at Iso and at +z is within 12/255 per channel
//      of the legend's 330 K colour; the bottom face's from −z within 12/255 of the 300 K colour;
//      /surface at the top face's nodes is exactly 330 K; face 5 stays selected and its outline shows
//      (≥ 20 near-black pixels): 5/5.
//  X2b Si (top) hidden with Regions: "Hidden: Si (top). Faces shown where it was are interior." above
//      the view and "Regions (1 hidden)"; shown again: neither: 2/2.
//  X3  card 1 with a run, then the Library: card 2's action reads "Open model", with no reason line and
//      no separate Replace button; a click opens the question: its title "Open Copper via through a slab
//      (3D heat)?", its lines equal openOtherQuestion for the unsaved state, its buttons Save and replace /
//      Replace without saving / Open in a new tab / Cancel; Cancel changes nothing; Open in a new tab opens
//      /workspace?card=via-slab-3d&fresh=1 with card 2 while this tab keeps card 1; Save and replace saves
//      the project file (holding card 1) and only then shows card 2, and Messages' Undo brings card 1
//      back; Replace without saving shows card 2 with no download: 6/6.
//  X4  card 1, Mesh element size 2 µm: Messages reads meshRefusalText of the server's reply, of the form
//      "Element size N µm: about … tetrahedra (estimated about … min). M µm: under a minute (estimated
//      about … s)."; it has the buttons "Use N µm" and "Use M µm"; Use M µm sets the Mesh field to M, and
//      the server's check there is ok with an estimate of at most 45 s; Use N µm (after Undo) sets N and
//      the check is ok within the limit: 3/3.
//  X5  card 1, face 5 fixed at 330 K (P05), Run 1, Fixed temperature z0 310 K, Run 2, Compare Runs 1 and 2: the Tmax and Tmin cells of A
//      and B equal each run's own run-table cells (the /extremes words: "… K at the SiO2 / Si (top)
//      interface, (…) µm" for Tmax); after File › Save and opening that file in a new page (kept
//      records, no live run), Compare's Tmax cells read "… K in <region> at (…) µm": 2/2.
//  X6  card 1, Run 1, the Result view: the line under the surface bar reads "Colours span the surface,
//      <lo>–<hi> K; the whole model reaches <Tmax> K (Tmax).", lo and hi the record's surface
//      temperature_min and temperature_max and Tmax its values' temperature_max (6 significant digits): 1/1.
// It writes report.json to out-dir and exits non-zero if a check fails.
import {createRequire} from 'node:module';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';

const require = createRequire(import.meta.url);
const {chromium} = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:8765';
const out = process.argv[3] || 'model3d-x-browser';
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
await mkdir(out, {recursive: true});
const CARD = JSON.parse(await readFile(join(ROOT, 'packages/simcase/src/simcase/studio/static/model3d-layer-stack-3d.json'), 'utf8'));
const CARD2 = JSON.parse(await readFile(join(ROOT, 'packages/simcase/src/simcase/studio/static/model3d-via-slab-3d.json'), 'utf8'));
const origin = new URL(base).origin;
const report = {base, checks: {}};
let failed = false;
const record = (name, ok, detail) => { report.checks[name] = {ok, ...detail}; if (!ok) failed = true; console.log(`${ok ? 'PASS' : 'FAIL'} ${name}`); };

async function open(browser, viewport = {width: 1440, height: 900}, url = '/workspace', context = null) {
  const ctx = context || await browser.newContext({viewport, acceptDownloads: true});
  const page = await ctx.newPage();
  const seen = {console: [], pageErrors: [], foreign: []};
  page.on('console', m => { if (m.type() === 'error') seen.console.push(m.text()); });
  page.on('pageerror', e => seen.pageErrors.push(String(e)));
  page.on('request', r => { if (/^(https?|wss?):/.test(r.url()) && new URL(r.url()).origin !== origin) seen.foreign.push(r.url()); });
  await page.addInitScript(() => {
    delete window.showSaveFilePicker; delete Window.prototype.showSaveFilePicker;
    window.__csp = []; document.addEventListener('securitypolicyviolation', e => window.__csp.push(e.violatedDirective + ' ' + e.blockedURI));
  });
  await page.goto(base + url);
  return {page, seen, ctx};
}
const checked = page => page.waitForFunction(() => { const box = document.getElementById('mp-messages');
  return box && !box.hidden && box.dataset.m3State === 'checked' && document.querySelector('#m3-faces li'); }, null, {timeout: 30000});
const serverCheck = (page, doc) => page.evaluate(async d => (await fetch('/api/model3d/check', {method: 'POST', headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({doc: d})})).json(), doc);
async function setField(page, key, value) {
  const sel = `[data-m3-field="${key}"]`;
  await page.fill(sel, value); await page.press(sel, 'Enter');
  await page.waitForFunction(() => document.getElementById('mp-messages')?.dataset.m3State === 'checked', null, {timeout: 30000});
  await page.waitForTimeout(200);
}
// occurrences of a text in the page's rendered text (Details closed or open both count once)
const occurrences = (page, text) => page.evaluate(t => document.body.innerText.split(t).length - 1 + [...document.querySelectorAll('details:not([open])')]
  .reduce((n, d) => n + ([...d.childNodes].filter(c => c.nodeName !== 'SUMMARY').map(c => c.textContent).join('').split(t).length - 1), 0), text);

async function download(page, trigger) {
  const done = page.waitForEvent('download', {timeout: 30000});
  await trigger();
  const asked = await page.waitForSelector('#save-name-dialog[open]', {timeout: 3000}).then(() => true, () => false);
  if (asked) await page.click('#save-name-download');
  return readFile(await (await done).path(), 'utf8');
}
const openFile = (page, name, text) => page.setInputFiles('#session-file', {name, mimeType: 'application/json', buffer: Buffer.from(text)});
const session = doc => JSON.stringify({format: 'openphysics-studio-session', version: 1, application: 'model3d', document: doc});
const save = page => download(page, async () => { await page.click('#file-menu-button'); await page.click('#menu-save'); });
const completed = (page, n) => page.waitForFunction(n => (document.getElementById('mp-messages')?.textContent || '').includes(`Run ${n} complete`)
  && document.getElementById('m3-result-canvas'), n, {timeout: 180000});

const only = process.argv[4] ? new Set(process.argv[4].split(',')) : null;
const want = name => !only || only.has(name);
const CARD2X = JSON.parse(await readFile(join(ROOT, 'packages/simcase/src/simcase/studio/static/model3d-via-slab-3d.json'), 'utf8'));
const browser = await chromium.launch();
try {
  // ---- X1: the cylinder advice names only values the engine takes ----
  if (want('X1')) {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card="via-slab-3d"]');
    await page.click('[data-model3d-card="via-slab-3d"]'); await checked(page);
    await page.click('[data-m3-node="feature:0"]');
    const cases = [['cx', '0.8', 'x1'], ['cx', '-0.8', 'x0'], ['cy', '0.8', 'y1'], ['cy', '-0.8', 'y0'], ['cx', '0.7', 'x1 touch']];
    const results = [];
    for (const [field, value, label] of cases) {
      const sel = `[data-m3-field="features[0].${field}"]`;
      await page.fill(sel, value); await page.press(sel, 'Enter');
      await page.waitForSelector('[data-m3-refusal]', {timeout: 30000});
      // the server's confirmations arrive after the refusal: wait for the named values (cx/cy and r)
      await page.waitForFunction(() => (document.querySelector('[data-m3-refusal] > p')?.textContent.match(/ forms/g) || []).length >= 2, null, {timeout: 30000}).catch(() => {});
      const text = await page.evaluate(() => document.querySelector('[data-m3-refusal] > p')?.textContent || '');
      const named = [...text.matchAll(/(c[xy]|r) = (−?[\d.]+) m forms/g)].map(m => [m[1], Number(m[2].replace('−', '-'))]);
      const fed = [];
      for (const [f, v] of named) {
        const doc = structuredClone(CARD2X); doc.geometry.components.c.features[0][field] = Number(value); doc.geometry.components.c.features[0][f] = v;
        const a = await serverCheck(page, doc); fed.push([f, v, a.ok === true && a.mesh?.ok === true]);
      }
      results.push({label, text, fed});
      // back to the card's value before the next case
      await page.fill(sel, '0'); await page.press(sel, 'Enter'); await checked(page);
    }
    const byLabel = Object.fromEntries(results.map(r => [r.label, r]));
    const centreOk = l => byLabel[l].fed.some(([f, , ok]) => f.startsWith('c') && ok) && byLabel[l].fed.every(([, , ok]) => ok);
    const rows = [centreOk('x1'), centreOk('x0'), centreOk('y1'), centreOk('y0'),
      byLabel.x1.fed.some(([f, , ok]) => f === 'r' && ok),
      /^Cylinder via touches the domain side x = 1 m along a line\. Keep cx < 0\.7 m/.test(byLabel['x1 touch'].text) && centreOk('x1 touch')];
    record('X1', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 6, results});
    await ctx.close();
  }
  // ---- X2: a selected face keeps its temperature colours in the Result view (P05's path) ----
  if (want('X2')) {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card="layer-stack-3d"]');
    await page.click('[data-model3d-card="layer-stack-3d"]'); await checked(page);
    let runId = null;
    page.on('response', async r => { if (r.url().endsWith('/api/model3d/run') && r.request().method() === 'POST') { try { runId = (await r.json()).run; } catch {} } });
    // P05: face 5 in the Faces list, Use for → Fixed temperature 330, Apply, Run, Result at Iso
    await page.click('#m3-faces li[data-face="5"]'); await page.selectOption('#m3-use', 'fixed');
    await page.fill('#m3-use-temp', '330'); await page.click('#m3-use-go');
    await page.waitForFunction(() => /Fixed temperature 330 K on /.test(document.getElementById('mp-messages')?.textContent || ''), null, {timeout: 30000}); await checked(page);
    await page.click('#m3-run'); await completed(page, 1); await page.waitForTimeout(500);
    const selected = await page.evaluate(() => document.getElementById('m3-names')?.dataset.face);
    const sample = async view => { await page.click(`[data-m3-view="${view}"]`); await page.waitForTimeout(300);
      return page.evaluate(async ([id, view]) => {
        const M = await import('/model3d-assets/model3d-model.mjs'), W = await import('/workspace-assets/workspace-model3d.mjs');
        const s = await (await fetch(`/api/model3d/runs/${id}/surface`)).json();
        const pos = M.decode(s.positions, Float32Array), T = M.decode(s.temperature, Float32Array), idx = M.decode(s.indices, Uint32Array), own = M.decode(s.triangle_faces, Uint32Array);
        const face = name => s.faces.find(f => f.names.includes(name)).id;
        const nodesT = id => { const out = new Set(); for (let t = 0; t < idx.length / 3; t++) if (own[t] === id) for (let k = 0; k < 3; k++) out.add(T[idx[3 * t + k]]); return [...out]; };
        const c = document.getElementById('m3-result-canvas'), w = c.width, h = c.height;
        // the face's centroid on the canvas by the camera contract (the result view's display box: the half extents about origin_m)
        const half = [0, 0, 0]; for (let i = 0; i < pos.length; i++) half[i % 3] = Math.max(half[i % 3], Math.abs(pos[i]));
        const v = {...s, metres_per_unit: 1e-6, half_extent_m: half};
        const centroid = id => { let q = [0, 0, 0], n = 0; for (let t = 0; t < idx.length / 3; t++) if (own[t] === id) for (let k = 0; k < 3; k++) { const i = idx[3 * t + k]; for (let a = 0; a < 3; a++) q[a] += pos[3 * i + a]; n++; } return q.map(x => x / n); };
        const pixel = id => { const fr = M.frameOf(M.viewCamera(v, view), c.clientWidth, c.clientHeight), q = centroid(id);
          const x = (M.dot(q, fr.x) / fr.halfWidth + 1) / 2 * w, y = (1 - M.dot(q, fr.y) / fr.halfHeight) / 2 * h;
          const t = document.createElement('canvas'); t.width = w; t.height = h; const g = t.getContext('2d'); g.drawImage(c, 0, 0);
          return [...g.getImageData(Math.round(x), Math.round(y), 1, 1).data].slice(0, 3); };
        const lo = s.temperature_min.value, hi = s.temperature_max.value, colour = K => W.temperatureColor(K, lo, hi).map(x => Math.round(x * 255));
        const t = document.createElement('canvas'); t.width = w; t.height = h; const g = t.getContext('2d'); g.drawImage(c, 0, 0); const d = g.getImageData(0, 0, w, h).data;
        let dark = 0; for (let i = 0; i < d.length; i += 4) if (d[i] < 70 && d[i + 1] < 70 && d[i + 2] < 70) dark++;
        const top = face('stack.top.top'), bottom = face('stack.sub.bottom');
        return {top: view === '-z' ? null : pixel(top), bottom: view === '-z' ? pixel(bottom) : null, want330: colour(330), want300: colour(300), topT: nodesT(top), dark};
      }, [runId, view]); };
    const iso = await sample('iso'), pz = await sample('+z'), mz = await sample('-z');
    const near = (p, q) => p && Math.max(...p.map((v, k) => Math.abs(v - q[k]))) <= 12;
    await page.click('[data-m3-view="iso"]'); await page.waitForTimeout(300);
    await page.screenshot({path: join(out, 'x2-result-iso.png')});
    const rows = [near(iso.top, iso.want330), near(pz.top, pz.want330), near(mz.bottom, mz.want300),
      iso.topT.length === 1 && iso.topT[0] === 330, selected === '5' && iso.dark >= 20];
    record('X2', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 5, selected, iso, pz, mz});
    // the hidden-region note: Si (top) hidden → the line and "Regions (1 hidden)"; shown again → neither
    await page.evaluate(() => { document.getElementById('m3-regions').open = true; });
    await page.click('#m3-regions [data-m3-region="Si (top)"]'); await page.waitForTimeout(200);
    const hiddenNote = await page.evaluate(() => ({line: document.getElementById('m3-hidden-note')?.textContent || '', summary: document.querySelector('#m3-regions summary')?.textContent || ''}));
    await page.click('#m3-regions [data-m3-region="Si (top)"]'); await page.waitForTimeout(200);
    const shownNote = await page.evaluate(() => ({line: document.getElementById('m3-hidden-note')?.textContent ?? null, summary: document.querySelector('#m3-regions summary')?.textContent || ''}));
    const rowsB = [hiddenNote.line === 'Hidden: Si (top). Faces shown where it was are interior.' && hiddenNote.summary === 'Regions (1 hidden)',
      shownNote.line === null && shownNote.summary === 'Regions'];
    record('X2b', rowsB.every(Boolean) && !seen.pageErrors.length, {passed: rowsB.filter(Boolean).length, of: 2, hiddenNote, shownNote});
    await ctx.close();
  }
  if (want('X3')) {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card="layer-stack-3d"]');
    await page.click('[data-model3d-card="layer-stack-3d"]'); await checked(page);
    await page.click('#m3-run'); await completed(page, 1); await page.waitForTimeout(300);
    const held = () => page.evaluate(() => document.querySelector('.m3-head h2')?.textContent || '');
    await page.click('[data-page="Applications"]');
    const card = await page.evaluate(() => { const b = document.querySelector('[data-model3d-card="via-slab-3d"]');
      return {action: b?.querySelector('.card-action')?.textContent || '', why: !!b?.querySelector('.card-why'), replace: !!document.querySelector('[data-m3-replace]')}; });
    const ask = async () => { await page.click('[data-page="Applications"]').catch(() => {}); await page.click('[data-model3d-card="via-slab-3d"]'); await page.waitForSelector('#m3-replace-dialog[open]'); };
    await ask();
    const q = await page.evaluate(() => ({title: document.querySelector('#m3-replace-dialog h2')?.textContent || '',
      lines: [...document.querySelectorAll('#m3-replace-dialog p')].map(p => p.textContent),
      buttons: [...document.querySelectorAll('#m3-replace-dialog .dialog-actions button')].map(b => b.textContent)}));
    const want = await page.evaluate(async () => (await import('/workspace-assets/workspace-model3d.mjs'))
      .openOtherQuestion({from: 'Via in a layer stack (3D heat)', to: 'Copper via through a slab (3D heat)', runs: 1, saved: 'none'}));
    await page.click('#m3-replace-dialog [data-act="cancel"]'); await page.waitForTimeout(200);
    const afterCancel = {dialog: await page.evaluate(() => !!document.getElementById('m3-replace-dialog')), held: (await page.click('[data-page="Model"]').catch(() => {}), await held())};
    // Open in a new tab
    await ask();
    const popup = ctx.waitForEvent('page', {timeout: 30000});
    await page.click('#m3-replace-dialog [data-act="tab"]');
    const tab = await popup; await tab.waitForLoadState();
    await tab.waitForFunction(() => document.getElementById('mp-messages')?.dataset.m3State === 'checked', null, {timeout: 30000});
    const fresh = await tab.evaluate(() => ({url: location.pathname + location.search, title: document.querySelector('.m3-head h2')?.textContent || ''}));
    await tab.close();
    await page.click('[data-page="Model"]').catch(() => {});
    const keptAfterTab = await held();
    // Save and replace: the file is written (holding card 1), then card 2 shows; Undo brings card 1 back
    await ask();
    const file = await download(page, () => page.click('#m3-replace-dialog [data-act="save"]'));
    await page.waitForFunction(() => document.querySelector('.m3-head h2')?.textContent === 'Copper via through a slab (3D heat)', null, {timeout: 30000});
    await checked(page);
    const saved = JSON.parse(file), m3 = saved.models.find(m => m.kind === 'model3d');
    await page.click('#file-status button[data-m3-undo-replace]');
    await page.waitForFunction(() => document.querySelector('.m3-head h2')?.textContent === 'Via in a layer stack (3D heat)', null, {timeout: 30000});
    await checked(page);
    // Replace without saving: no download
    let downloads = 0; page.on('download', () => downloads++);
    await ask();
    await page.click('#m3-replace-dialog [data-act="replace"]');
    await page.waitForFunction(() => document.querySelector('.m3-head h2')?.textContent === 'Copper via through a slab (3D heat)', null, {timeout: 30000});
    await checked(page); await page.waitForTimeout(500);
    const rows = [
      card.action === 'Open model' && !card.why && !card.replace,
      q.title === want.title && JSON.stringify(q.lines) === JSON.stringify(want.lines),
      JSON.stringify(q.buttons) === JSON.stringify(want.buttons.map(b => b.label)) && !afterCancel.dialog && afterCancel.held === 'Via in a layer stack (3D heat)',
      fresh.url === '/workspace?card=via-slab-3d&fresh=1' && fresh.title === 'Copper via through a slab (3D heat)' && keptAfterTab === 'Via in a layer stack (3D heat)',
      m3?.card === 'layer-stack-3d',
      downloads === 0,
    ];
    record('X3', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 6, card, q, afterCancel, fresh, keptAfterTab, savedCard: m3?.card, downloads, errors: seen.pageErrors});
    await ctx.close();
  }
  if (want('X4')) {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card="layer-stack-3d"]');
    await page.click('[data-model3d-card="layer-stack-3d"]'); await checked(page);
    await page.click('[data-m3-node="mesh"]'); await setField(page, 'mesh.element_size', '2');
    const doc = structuredClone(CARD); doc.mesh.element_size = '2 um';
    const mesh = (await serverCheck(page, doc)).mesh;
    const plain = await page.evaluate(async m => (await import('/workspace-assets/workspace-model3d.mjs')).meshRefusalText(m, 'um'), mesh);
    await page.waitForSelector('[data-m3-mesh-refusal]');
    const shown = await page.evaluate(() => ({text: document.querySelector('[data-m3-mesh-refusal] > p')?.textContent || '',
      buttons: [...document.querySelectorAll('[data-m3-mesh-refusal] [data-m3-use-size]')].map(b => b.textContent)}));
    const field = () => page.evaluate(() => document.querySelector('[data-m3-field="mesh.element_size"]')?.value ?? null);
    const docSize = async () => { await page.waitForFunction(() => !document.querySelector('[data-m3-mesh-refusal]'), null, {timeout: 30000}).catch(() => {}); return field(); };
    const at = async size => { const d = structuredClone(CARD); d.mesh.element_size = `${size} um`; return (await serverCheck(page, d)).mesh; };
    const N = mesh.suggested_size, M = mesh.suggested_minute;
    let useM = null, useN = null, thereM = null, thereN = null;
    if (shown.buttons.length === 2) {
      await page.click(`[data-m3-use-size="${M}"]`); await checked(page); useM = await docSize(); thereM = await at(M);
      await page.click('#undo-edit'); await page.waitForSelector('[data-m3-mesh-refusal]', {timeout: 30000}).catch(() => {});
      await page.click(`[data-m3-use-size="${N}"]`); await checked(page); useN = await docSize(); thereN = await at(N);
    }
    const rows = [
      shown.text === plain && new RegExp(`Element size ${N} µm: about [\\d,]+ tetrahedra \\(estimated about \\d+ min\\)\\. ${M} µm: under a minute \\(estimated about \\d+ s\\)\\.$`).test(shown.text),
      JSON.stringify(shown.buttons) === JSON.stringify([`Use ${N} µm`, `Use ${M} µm`]) && useM === `${M} um` && thereM?.ok === true && thereM.estimate.seconds <= 45,
      useN === `${N} um` && thereN?.ok === true && thereN.estimate.tetrahedra <= mesh.limit,
    ];
    record('X4', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 3, shown, N, M, useM, useN,
      server: {suggested_seconds: mesh.suggested_seconds, minute_seconds: mesh.minute_seconds}, thereM: thereM?.estimate, thereN: thereN?.estimate});
    await ctx.close();
  }
  if (want('X5')) {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card="layer-stack-3d"]');
    await page.click('[data-model3d-card="layer-stack-3d"]'); await checked(page);
    // P05's path (Tmax then sits on the SiO2 / Si (top) interface): face 5 fixed at 330 K
    await page.click('#m3-faces li[data-face="5"]'); await page.selectOption('#m3-use', 'fixed');
    await page.fill('#m3-use-temp', '330'); await page.click('#m3-use-go');
    await page.waitForFunction(() => /Fixed temperature 330 K on /.test(document.getElementById('mp-messages')?.textContent || ''), null, {timeout: 30000}); await checked(page);
    await page.click('#m3-run'); await completed(page, 1); await page.waitForTimeout(300);
    await page.click('#tree [data-m3-node="heat:fixed:z0"]');
    await page.fill('[data-m3-heat="fixed"][data-m3-key="z0"]', '310'); await page.press('[data-m3-heat="fixed"][data-m3-key="z0"]', 'Enter');
    await page.waitForTimeout(150); await checked(page);
    await page.click('#m3-run'); await completed(page, 2); await page.waitForTimeout(800);
    const LABELS = ['Temperature, max (whole model)', 'Temperature, min (whole model)'];
    const table = async n => { await page.click(`#tree [data-m3-node="run:${n}"]`); await page.waitForSelector('#m3-values');
      return page.evaluate(L => Object.fromEntries([...document.querySelectorAll('#m3-values tr')].map(r => [r.querySelector('th').textContent, r.querySelector('td').textContent]).filter(([k]) => L.includes(k))), LABELS); };
    const t1 = await table(1), t2 = await table(2);
    const compareCells = async pg => { await pg.click('[data-page="Compare"]'); await pg.waitForSelector('#m3-compare-values');
      await pg.selectOption('#m3-compare-a', '0'); await pg.waitForTimeout(100); await pg.selectOption('#m3-compare-b', '1'); await pg.waitForTimeout(300);
      return pg.evaluate(L => Object.fromEntries([...document.querySelectorAll('#m3-compare-values tbody tr')].map(r => [r.querySelector('th').textContent, [...r.querySelectorAll('td')].map(t => t.textContent)]).filter(([k]) => L.includes(k))), LABELS); };
    const live = await compareCells(page);
    await page.click('[data-page="Model"]'); await checked(page);
    const file = await save(page);
    const second = await open(browser);
    await second.page.waitForSelector('[data-model3d-card="layer-stack-3d"]');
    await openFile(second.page, 'x5-project.json', file); await second.page.waitForSelector('.m3-head h2'); await checked(second.page);
    const kept = await compareCells(second.page);
    await second.ctx.close();
    const tmax = LABELS[0], tmin = LABELS[1];
    const rows = [
      live[tmax]?.[0] === t1[tmax] && live[tmax]?.[1] === t2[tmax] && live[tmin]?.[0] === t1[tmin] && live[tmin]?.[1] === t2[tmin]
        && / K at the SiO2 \/ Si \(top\) interface, \(/.test(live[tmax][0]) && / K at the SiO2 \/ Si \(top\) interface, \(/.test(live[tmax][1]),
      kept[tmax]?.length === 3 && / K in [^,()]+ at \(/.test(kept[tmax][0]) && / K in [^,()]+ at \(/.test(kept[tmax][1]) && !/interface/.test(kept[tmax].join(' ')),
    ];
    record('X5', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 2, t1, t2, live, kept});
    await ctx.close();
  }
  if (want('X6')) {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card="layer-stack-3d"]');
    await page.click('[data-model3d-card="layer-stack-3d"]'); await checked(page);
    let runId = null;
    page.on('response', async r => { if (r.url().endsWith('/api/model3d/run') && r.request().method() === 'POST') { try { runId = (await r.json()).run; } catch {} } });
    await page.click('#m3-run'); await completed(page, 1); await page.waitForTimeout(500);
    await page.click('[data-m3-pane="result"]').catch(() => {}); await page.waitForTimeout(300);
    const line = await page.evaluate(() => document.getElementById('m3-surface-span')?.textContent ?? null);
    const rec = await page.evaluate(async id => (await fetch(`/api/model3d/runs/${id}/record?maps=kept`)).json(), runId);
    const six = x => String(Number(x.toPrecision(6)));
    const want = `Colours span the surface, ${six(rec.surface.temperature_min.value)}–${six(rec.surface.temperature_max.value)} K; the whole model reaches ${six(rec.values.temperature_max.value)} K (Tmax).`;
    const rows = [line === want];
    record('X6', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 1, line, want});
    await ctx.close();
  }
} finally {
  await writeFile(join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}
if (failed) process.exit(1);
