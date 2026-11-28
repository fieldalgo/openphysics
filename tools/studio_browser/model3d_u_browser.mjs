// Real-browser checks of the Studio 3D fixes U1–U8 (the first agent round's findings).
// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
//
// A local check, not wired into CI: it needs Playwright with a Chromium it can launch
// (not a repository dependency). From the repository root, with a Studio server running:
//   python -m simcase.studio --no-browser --port 8765 &
//   node tools/studio_browser/model3d_u_browser.mjs http://127.0.0.1:8765 out-dir
// Pre-registered checks (thresholds fixed before measuring), one row per item:
//  U1  card 1 at element size 2 µm: the plain refusal ("Component 1 needs about N tetrahedra; the
//      limit is L. Use an element size of at least S µm.") appears exactly once on the page, the
//      engine's sentence under Details; typing S (the server's suggestion, read at test time)
//      enables Mesh: 100%.
//  U2  card 1, stack.top.top from the faces list, Use for → Fixed temperature, Apply: the tree selects
//      heat:fixed:stack.top.top, its Temperature input has the focus, typing 310 + Enter makes Messages
//      read "Fixed temperature 310 K on stack.top.top." with no 300 K line left, and the name box
//      beside the select has a label element as its accessible name: 4/4.
//  U4  card 1, Run: right after Run 1 completes #m3-run-why reads "Run 1 is up to date with these
//      inputs."; after an edit and Undo it reads "No need to run: Run 1 already has these results.": 2/2.
//  U3  card 1 with 300 K on z0 and z1 (Tmax on the oxide's top), Run: Tmax's row reads "at the SiO2 /
//      Si (top) interface" with "(whole model)" in its label, the sign line is shown, and the colour bar
//      is titled "Surface temperature"; after Save and Open the reopened run (no mesh) reads "in SiO2"
//      until Recompute: 4/4.
//  U5  card 1 (300 K on z0 and z1), Run, Section z = 505 Apply: the cut's legend reads "Cut z = 505 µm:
//      a–b K" with a and b the cut's own range (the /cut answer, read at test time), not the surface's;
//      "µm" stands beside the Section box; the Layers row reads "sub · 0–500 µm · oxide · 500–510 µm ·
//      top · 510–610 µm"; Cut (CSV) stands in the Section group; clicking it saves
//      "via-in-a-layer-stack-3d-heat-cut-z-505um.csv" with the metre columns (F7); and Messages reads
//      "Cut (CSV) saved as …": 6/6.
//  U6  card 1 open, then card 2 from the Library: the refusal has "Open in a new tab"; it opens
//      /workspace?card=via-slab-3d&fresh=1 in a new tab showing card 2 with no refusal, while the
//      first tab keeps card 1; with an optical run's recovery record from the first tab, the new tab
//      offers no recovery (Recover disabled, its note says so) and, after an edit of its 3D model, the
//      latest record (savedAt and session) reads the same; card 1's note has no "Copper via": 4/4.
//  U7  card 1: the view toolbar's Regions control has a checkbox per drawn region of the server's check,
//      all checked; in the +z view a click at via.z1's projected centroid does not pick via.z1 with
//      every region shown, and picks it once Si (top) (the region above it) is unchecked; Names then
//      reads "Any of these names selects this face." under its names, via.z1 among them: 3/3.
// It writes report.json and screenshots to out-dir and exits non-zero if a check fails.
import {createRequire} from 'node:module';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';

const require = createRequire(import.meta.url);
const {chromium} = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:8765';
const out = process.argv[3] || 'model3d-u-browser';
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

const browser = await chromium.launch();
try {
  // ---- U1: the mesh refusal, once, in plain words; the suggested size enables Mesh -----------------
  {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card="layer-stack-3d"]');
    await page.click('[data-model3d-card="layer-stack-3d"]'); await checked(page);
    await page.click('[data-m3-node="mesh"]');
    await setField(page, 'mesh.element_size', '2');
    const doc = structuredClone(CARD); doc.mesh.element_size = '2 um';
    const mesh = (await serverCheck(page, doc)).mesh;
    const plain = await page.evaluate(async m => (await import('/workspace-assets/workspace-model3d.mjs')).meshRefusalText(m, 'um'), mesh);
    const shown = await page.evaluate(() => ({text: document.querySelector('[data-m3-mesh-refusal] > p')?.textContent || '',
      details: document.querySelector('[data-m3-mesh-refusal] details')?.textContent || '',
      block: document.getElementById('m3-block')?.textContent || '', estimate: document.getElementById('m3-estimate')?.textContent || '',
      runWhy: document.getElementById('m3-run-why')?.textContent || '', meshDisabled: document.getElementById('m3-mesh')?.disabled === true,
      label: document.querySelector('label[for="m3f-mesh-element-size"] > span')?.textContent || ''}));
    const count = await occurrences(page, `about ${Number(mesh.tetrahedra).toLocaleString('en-US')} tetrahedra`);
    await page.screenshot({path: join(out, 'u1-refusal.png')});
    await setField(page, 'mesh.element_size', String(mesh.suggested_size));
    const after = await page.evaluate(() => ({meshDisabled: document.getElementById('m3-mesh')?.disabled === true,
      refusal: !!document.querySelector('[data-m3-mesh-refusal]')}));
    const ok = mesh.code === 'E-MESH-ESTIMATE' && typeof mesh.suggested_size === 'number' && shown.text === plain
      && /^Component 1 needs about [\d,]+ tetrahedra; the limit is 600,000\. Use an element size of at least [\d.]+ µm\.$/.test(plain)
      && shown.details.includes(mesh.refused) && shown.details.includes('E-MESH-ESTIMATE') && count === 1
      && shown.block === 'Fix 1 problem in Messages to mesh' && shown.runWhy === 'Fix 1 problem in Messages to run'
      && shown.estimate === 'Mesh is not available: see Messages.' && shown.meshDisabled && shown.label === 'Element size'
      && !after.meshDisabled && !after.refusal && !seen.pageErrors.length;
    record('U1', ok, {plain, shown, count, suggested: mesh.suggested_size, after, pageErrors: seen.pageErrors});
    await ctx.close();
  }
  // ---- U2: Use for → Fixed temperature opens the new node, focused; Messages follows ----------------
  {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card="layer-stack-3d"]');
    await page.click('[data-model3d-card="layer-stack-3d"]'); await checked(page);
    const top = await page.evaluate(() => [...document.querySelectorAll('#m3-faces li')].find(li => li.getAttribute('aria-label').split(': ')[1].split(', ').includes('stack.top.top'))?.dataset.face);
    await page.click(`#m3-faces li[data-face="${top}"]`);
    await page.selectOption('#m3-use', 'fixed');
    const label = await page.evaluate(() => { const i = document.getElementById('m3-use-name');
      return {aria: i.getAttribute('aria-label'), labels: [...(i.labels || [])].map(l => l.textContent.trim())}; });
    await page.click('#m3-use-go');
    await page.waitForSelector('[data-m3-node="heat:fixed:stack.top.top"]', {timeout: 30000});
    await page.waitForTimeout(300);
    const state = await page.evaluate(() => ({selected: document.querySelector('#tree [aria-selected="true"]')?.dataset.m3Node,
      focus: document.activeElement?.dataset?.m3Heat + ':' + document.activeElement?.dataset?.m3Key}));
    await page.keyboard.press('Control+A'); await page.keyboard.type('310'); await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.getElementById('mp-messages')?.dataset.m3State === 'checked', null, {timeout: 30000});
    await page.waitForTimeout(300);
    const messages = await page.evaluate(() => document.getElementById('mp-messages').textContent);
    const rows = [
      state.selected === 'heat:fixed:stack.top.top',
      state.focus === 'fixed:stack.top.top',
      messages.includes('Fixed temperature 310 K on stack.top.top.') && !messages.includes('300 K on stack.top.top'),
      label.aria === null && label.labels.length === 1 && label.labels[0].length > 0,
    ];
    record('U2', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 4, state, label, messages: messages.slice(0, 300)});
    await ctx.close();
  }
  // ---- U4: the run just finished is up to date; after an edit and Undo: no need to run -------------
  {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card="layer-stack-3d"]');
    await page.click('[data-model3d-card="layer-stack-3d"]'); await checked(page);
    await page.click('#m3-run');
    await page.waitForFunction(() => (document.getElementById('mp-messages')?.textContent || '').includes('Run 1 complete'), null, {timeout: 180000});
    await page.waitForTimeout(300);
    const why = () => page.evaluate(() => (document.getElementById('m3-run-why')?.textContent || '').replace(/Show Run \d+$/, '').trim());
    const after = await why();
    await page.click('[data-m3-node="heat:fixed:z0"]');
    await page.fill('[data-m3-heat="fixed"][data-m3-key="z0"]', '301'); await page.press('[data-m3-heat="fixed"][data-m3-key="z0"]', 'Enter');
    await page.waitForFunction(() => document.getElementById('mp-messages')?.dataset.m3State === 'checked', null, {timeout: 30000});
    await page.click('#undo-edit');
    await page.waitForFunction(() => document.getElementById('mp-messages')?.dataset.m3State === 'checked', null, {timeout: 30000});
    await page.waitForTimeout(300);
    const undone = await why();
    const rows = [after === 'Run 1 is up to date with these inputs.', undone === 'No need to run: Run 1 already has these results.'];
    record('U4', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 2, after, undone});
    await ctx.close();
  }
  // ---- U3: interface wording on a live run, the sign line, the surface legend; reopened: as before ----
  {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card]');
    const doc = structuredClone(CARD); doc.physics.heat.prescribed_temperature = {z0: '300 K', z1: '300 K'};
    await openFile(page, 'u3.json', session(doc)); await checked(page);
    await page.click('#m3-run'); await completed(page, 1); await page.waitForTimeout(300);
    const live = await page.evaluate(() => ({tmax: [...document.querySelectorAll('#m3-values tr')].map(r => [r.querySelector('th').textContent, r.querySelector('td').textContent])[0],
      sign: document.getElementById('m3-sign')?.textContent || '', bar: document.querySelector('.m3-cb-title')?.textContent || ''}));
    const text = await save(page);
    await openFile(page, 'u3-project.json', text); await checked(page);
    await page.click('[data-m3-node="run:1"]'); await page.waitForTimeout(300);
    const reopened = await page.evaluate(() => [...document.querySelectorAll('#m3-values tr')].map(r => r.querySelector('td').textContent)[0]);
    const rows = [
      live.tmax[0] === 'Temperature, max (whole model)' && /^[\d.]+ K at the SiO2 \/ Si \(top\) interface, \(.*\) µm$/.test(live.tmax[1]),
      live.sign === 'Heat rate: positive into the model, negative out of it (a fixed temperature that removes heat shows a negative rate).',
      live.bar === 'Surface temperature',
      /^[\d.]+ K in SiO2 at \(.*\) µm$/.test(reopened),
    ];
    record('U3', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 4, live, reopened});
    await ctx.close();
  }
  // ---- U5: the section: the cut's own range and legend, the unit, the layers' z, Cut (CSV) and its name ----
  {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card]');
    const doc = structuredClone(CARD); doc.physics.heat.prescribed_temperature = {z0: '300 K', z1: '300 K'};
    await openFile(page, 'u5.json', session(doc)); await checked(page);
    const layers = await page.evaluate(() => document.querySelector('#tree [data-m3-node="feature:0"] .m3-note')?.textContent || '');
    await page.click('#m3-run'); await completed(page, 1); await page.waitForTimeout(300);
    await page.selectOption('#m3-section-axis', 'z'); await page.fill('#m3-section-at', '505'); await page.click('#m3-section-go');
    await page.waitForSelector('#m3-cut-bar', {timeout: 30000});
    const run = await page.evaluate(() => document.querySelector('[data-m3-cut-csv]')?.getAttribute('href')?.split('/')[4]);
    const direct = await page.evaluate(async r => (await fetch(`/api/model3d/runs/${r}/cut`, {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({axis: 'z', at: 505})})).json(), run);
    const shown = await page.evaluate(() => ({bar: document.getElementById('m3-cut-bar')?.getAttribute('aria-label') || '',
      title: document.querySelector('#m3-cut-bar .m3-cb-title')?.textContent || '', surface: document.querySelector('.m3-colourbar:not(.m3-cut-bar)')?.getAttribute('aria-label') || '',
      unit: document.querySelector('.m3-section #m3-section-unit')?.textContent || '', csv: !!document.querySelector('.m3-section #m3-section-csv[data-m3-cut-csv]')}));
    const fmt = x => String(Number(x.toPrecision(6)));
    const legend = `Cut z = 505 µm: ${fmt(direct.temperature_min.value)}–${fmt(direct.temperature_max.value)} K`;
    const saved = page.waitForEvent('download', {timeout: 30000});
    await page.click('#m3-section-csv');
    const dl = await saved, name = dl.suggestedFilename(), csv = await readFile(await dl.path(), 'utf8');
    await page.waitForTimeout(200);
    const messages = await page.evaluate(() => document.getElementById('mp-messages')?.textContent || '');
    const rows = [
      shown.bar === `${legend} (blue to red)` && shown.title === 'Cut z = 505 µm' && shown.surface !== '' && !shown.surface.includes(fmt(direct.temperature_min.value) + ' K (blue)'),
      shown.unit === 'µm',
      layers === 'sub · 0–500 µm · oxide · 500–510 µm · top · 510–610 µm (covered in part by 2 (via))',
      shown.csv,
      name === 'via-in-a-layer-stack-3d-heat-cut-z-505um.csv' && csv.split('\n').includes('x_m,y_m,z_m,temperature_K'),
      messages.includes(`Cut (CSV) saved as ${name}.`),
    ];
    record('U5', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 6, layers, shown, legend, name, messages: messages.slice(0, 300)});
    await ctx.close();
  }
  // ---- U6: a second 3D card: Open in a new tab → a fresh workspace with that card; recovery untouched ----
  {
    const {page, seen, ctx} = await open(browser);
    await page.waitForFunction(() => /^Connected/.test(document.getElementById('connection-status').textContent) && !!document.querySelector('[data-template=optical]'));
    // the original tab: an optical run, so browser recovery holds a record (written 0.7 s after it)
    await page.click('[data-template=optical]'); await page.waitForFunction(() => !document.getElementById('run-optical').disabled, null, {timeout: 30000});
    await page.click('#run-optical');
    await page.waitForFunction(() => /complete/i.test(document.getElementById('job-message').textContent), null, {timeout: 180000});
    await page.waitForFunction(() => /^Browser recovery updated/.test(document.getElementById('notebook-recovery-detail').textContent), null, {timeout: 20000});
    await page.click('[data-page="Applications"]');
    const note = await page.evaluate(() => document.querySelector('[data-model3d-card="layer-stack-3d"] .card-scope')?.textContent || '');
    await page.click('[data-model3d-card="layer-stack-3d"]'); await checked(page);
    // the latest recovery record (savedAt and session), read from the store the tabs of this origin share
    const latest = pg => pg.evaluate(() => new Promise((resolve, reject) => { const o = indexedDB.open('openphysics-studio-notebook', 1);
      o.onsuccess = () => { const r = o.result.transaction('snapshots', 'readonly').objectStore('snapshots').get('latest');
        r.onsuccess = () => { o.result.close(); const v = r.result; resolve(v ? JSON.stringify({savedAt: v.savedAt, session: v.session ?? v.text ?? null}) : null); };
        r.onerror = () => reject(r.error); }; o.onerror = () => reject(o.error); }));
    const before = await latest(page);
    await page.click('[data-page="Applications"]'); await page.click('[data-model3d-card="via-slab-3d"]');
    const refusal = await page.evaluate(() => ({text: document.getElementById('file-status')?.textContent || '',
      button: document.querySelector('#file-status button[data-m3-new-tab="via-slab-3d"]')?.textContent || ''}));
    const popup = ctx.waitForEvent('page', {timeout: 30000});
    await page.click('#file-status button[data-m3-new-tab="via-slab-3d"]');
    const tab = await popup; await tab.waitForLoadState();
    await tab.waitForFunction(() => document.getElementById('mp-messages')?.dataset.m3State === 'checked', null, {timeout: 30000});
    const fresh = await tab.evaluate(() => ({url: location.pathname + location.search, title: document.querySelector('.m3-head h2')?.textContent || '',
      status: document.getElementById('file-status')?.textContent || '', recover: document.getElementById('recover-notebook')?.disabled === true,
      detail: document.getElementById('notebook-recovery-detail')?.textContent || ''}));
    // the new tab's 3D work: an edit, then time for any recovery write (0.7 s after a change)
    await tab.click('[data-m3-node="mesh"]'); await setField(tab, 'mesh.element_size', '0.2'); await tab.waitForTimeout(2000);
    const after = await latest(tab);
    await page.click('[data-page="Model"]').catch(() => {});
    const original = await page.evaluate(() => document.querySelector('.m3-head h2')?.textContent || '');
    const rows = [
      refusal.button === 'Open in a new tab' && refusal.text.includes('a project holds one 3D model'),
      fresh.url === '/workspace?card=via-slab-3d&fresh=1' && fresh.title === 'Copper via through a slab (3D heat)' && !/already holds/.test(fresh.status)
        && original === 'Via in a layer stack (3D heat)',
      before !== null && before === after && fresh.recover && fresh.detail.startsWith('This tab was opened for one 3D model: it offers no browser recovery'),
      note !== '' && !note.includes('Copper via'),
    ];
    record('U6', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 4, note, refusal, fresh, original,
      same: before === after, before: before && before.slice(0, 80)});
    await ctx.close();
  }
  // ---- U7: Regions in the view toolbar; hiding the regions above via.z1 lets a click find it ----
  {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card="layer-stack-3d"]');
    await page.click('[data-model3d-card="layer-stack-3d"]'); await checked(page);
    const answer = await serverCheck(page, CARD);
    const target = answer.display.faces.find(f => f.alone.includes('via.z1')).id;
    const boxes = await page.evaluate(() => [...document.querySelectorAll('.m3-views #m3-regions [data-m3-region]')].map(b => [b.dataset.m3Region, b.checked]));
    await page.click('[data-m3-view="+z"]'); await page.waitForTimeout(200);
    // the face's centroid on the canvas in the +z view, by the camera contract (model3d-model.mjs)
    const centroid = () => page.evaluate(async ({id, view}) => {
      const M = await import('/model3d-assets/model3d-model.mjs');
      const c = document.getElementById('m3-canvas'); c.scrollIntoView({block: 'center'}); const r = c.getBoundingClientRect();
      const pos = M.decode(view.positions, Float32Array), idx = M.decode(view.indices, Uint32Array), f = view.faces[id];
      let s = [0, 0, 0], n = 0;
      for (let t = f.first_triangle; t < f.first_triangle + f.triangle_count; t++) for (let k = 0; k < 3; k++) { const v = idx[3 * t + k]; for (let a = 0; a < 3; a++) s[a] += pos[3 * v + a]; n++; }
      s = s.map(x => x / n);
      const fr = M.frameOf(M.viewCamera(view, '+z'), r.width, r.height);
      const u = M.dot(s, fr.x) / fr.halfWidth, w = M.dot(s, fr.y) / fr.halfHeight;
      return {x: r.x + (u + 1) * r.width / 2, y: r.y + (1 - w) * r.height / 2};
    }, {id: target, view: answer.display});
    const pickAt = async () => { const point = await centroid(); await page.mouse.click(point.x, point.y); await page.waitForTimeout(150);
      const v = await page.evaluate(() => document.getElementById('m3-names').dataset.face); return v === '' ? null : Number(v); };
    const hide = async names => { await page.evaluate(() => { const d = document.getElementById('m3-regions'); if (d && !d.open) d.querySelector('summary').click(); });
      for (const [name] of boxes) { const box = page.locator(`#m3-regions [data-m3-region="${name}"]`); if (names.includes(name) === await box.isChecked()) await box.click(); }
      await page.evaluate(() => { const d = document.getElementById('m3-regions'); if (d?.open) d.querySelector('summary').click(); });
      await page.waitForTimeout(150); };
    const shown = await pickAt();
    await hide(['Si', 'SiO2']); const withoutSiSiO2 = await pickAt();
    await hide(['Si', 'SiO2', 'Si (top)']); const withoutTop = await pickAt();
    const names = await page.evaluate(() => ({any: document.getElementById('m3-names-any')?.textContent || '',
      list: [...document.querySelectorAll('#m3-names li code')].map(c => c.textContent)}));
    const rows = [
      JSON.stringify(boxes) === JSON.stringify(answer.display.regions.filter(r => !r.void).map(r => [r.name, true])),
      shown !== target && withoutTop === target,
      names.any === 'Any of these names selects this face.' && names.list.includes('via.z1'),
    ];
    record('U7', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 3, boxes, target, shown, withoutSiSiO2, withoutTop, names});
    await ctx.close();
  }
} finally {
  await writeFile(join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}
if (failed) process.exit(1);
