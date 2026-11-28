// Real-browser checks of the 3D model's heat, Run and Results in the workspace (slice D, UI).
// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
//
// A local check, not wired into CI: it needs Playwright with a Chromium it can launch
// (not a repository dependency). From the repository root, with a Studio server running:
//   python -m simcase.studio --no-browser --port 8765 &
//   node tools/studio_browser/model3d_heat_browser.mjs http://127.0.0.1:8765 out-dir
// Pre-registered checks (thresholds fixed before measuring):
//  W10 "No need to run" is shown exactly when the document equals a kept run's, in 6 states: after
//      the run, after an edit, after Undo, after Redo, after "Use this run's inputs", after Save and
//      Open of the project: 6/6;
//  W11 with runs: after Save and Open (project, and session), the document digest, the run's values
//      and its surface-map digest are equal; a version 1 project without 3D is saved as before;
//  W12 Results (Run 1 of the card: the surface temperature, the colour bar and the values table) at
//      1440 × 900 and 390 × 844: no console error, no CSP violation, the result canvas visible and not
//      empty, no horizontal scroll at 390; the table's 6 rows with (X7) "Heat source" after Tmin reading
//      "4 W in Si (top)" from the record; screenshots stored;
//  W13 keyboard only: open the card, rotate, view 5, select via.z1 from the faces list, Use for →
//      Fixed temperature, and Messages shows "Fixed temperature needs an outer face; via.z1 is
//      inside" (the document unchanged); select stack.top.top from the list, Use for → Fixed
//      temperature; set a section; Run to completion (the table's rows, with X7's "Heat source" after
//      Tmin reading "4 W in Si (top)" from the record); no pointer event;
//  W14 recorded only (SwiftShader here): the time from Run to the drawn result, and of a cut.
// Card 2, Copper via through a slab (E2-UI), with the same thresholds: W12 (Library, Model, Mesh view,
// Result at 1440 x 900 and 390 x 844, and the display note on the curved face via.side), W6-UI (Run 1's
// values table equals /api/model3d/runs/{id}/values through the page's rows), W11 (Save and Open with
// the run, the project naming card via-slab-3d), F2 (Add feature → Sphere shown refused in the engine's
// words, not silently fixed), W13 (keyboard only: via.side → Use for → Fixed temperature gives "Fixed
// temperature needs an outer face; via.side is inside" with the document unchanged, then Run) and W14.
// It writes report.json and screenshots to out-dir and exits non-zero if a check fails.
import {createRequire} from 'node:module';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';

const require = createRequire(import.meta.url);
const {chromium} = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:8765';
const out = process.argv[3] || 'model3d-heat-browser';
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
await mkdir(out, {recursive: true});
const V1 = await readFile(join(ROOT, 'tests/simcase/studio_session_fixtures/project-v1.json'), 'utf8');
const CARD2 = JSON.parse(await readFile(join(ROOT, 'packages/simcase/src/simcase/studio/static/model3d-via-slab-3d.json'), 'utf8'));
const INSIDE = 'Fixed temperature needs an outer face; via.z1 is inside';
const origin = new URL(base).origin;
const report = {base, checks: {}};
let failed = false;
const record = (name, ok, detail) => { report.checks[name] = {ok, ...detail}; if (!ok) failed = true; console.log(`${ok ? 'PASS' : 'FAIL'} ${name}`); };
const sha = text => createHash('sha256').update(text, 'utf8').digest('hex');
// key order does not count (the page's canonical JSON)
const canonical = v => Array.isArray(v) ? `[${v.map(canonical).join(',')}]`
  : v && typeof v === 'object' ? `{${Object.keys(v).sort().map(k => `${JSON.stringify(k)}:${canonical(v[k])}`).join(',')}}` : JSON.stringify(v);

async function open(browser, viewport) {
  const page = await browser.newPage({viewport, acceptDownloads: true});
  const seen = {console: [], pageErrors: [], foreign: []};
  page.on('console', m => { if (m.type() === 'error') seen.console.push(m.text()); });
  page.on('pageerror', e => seen.pageErrors.push(String(e)));
  // X7: the runs started, so a check can read the last run's record
  seen.runs = [];
  page.on('response', async r => { if (r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/model3d/run') { const id = (await r.json().catch(() => ({}))).run; if (id) seen.runs.push(id); } });
  page.on('request', r => { if (/^(https?|wss?):/.test(r.url()) && new URL(r.url()).origin !== origin) seen.foreign.push(r.url()); });
  await page.addInitScript(() => {
    delete window.showSaveFilePicker; delete Window.prototype.showSaveFilePicker;
    window.__csp = []; document.addEventListener('securitypolicyviolation', e => window.__csp.push(e.violatedDirective + ' ' + e.blockedURI));
    window.__pointer = 0;
    for (const type of ['pointerdown', 'pointerup', 'mousedown', 'mouseup', 'click', 'wheel', 'touchstart'])
      document.addEventListener(type, e => { if (e.isTrusted && (type !== 'click' || e.detail > 0)) window.__pointer++; }, true);
  });
  await page.goto(base + '/workspace');
  await page.waitForSelector('[data-model3d-card]');
  return {page, seen};
}
const checked = page => page.waitForFunction(() => { const box = document.getElementById('mp-messages');
  return box && !box.hidden && box.dataset.m3State === 'checked' && document.querySelector('#m3-faces li'); }, null, {timeout: 30000});
const csp = page => page.evaluate(() => window.__csp);
const completed = (page, n) => page.waitForFunction(n => (document.getElementById('mp-messages')?.textContent || '').includes(`Run ${n} complete`)
  && document.getElementById('m3-result-canvas'), n, {timeout: 180000});
// the document equals a kept run: "No need to run: …", or for the run just finished "Run N is up to date …" (U4)
const noNeed = page => page.evaluate(() => /^(No need to run|Run \d+ is up to date with these inputs)/.test(document.getElementById('m3-run-why')?.textContent || ''));
async function canvasState(page, selector) {
  return page.evaluate(sel => {
    const c = document.querySelector(sel), r = c.getBoundingClientRect(), probe = document.createElement('canvas');
    probe.width = c.width; probe.height = c.height; const g = probe.getContext('2d'); g.drawImage(c, 0, 0);
    const d = g.getImageData(0, 0, probe.width, probe.height).data; let drawn = 0;
    const [r0, g0, b0] = [d[0], d[1], d[2]];
    for (let i = 0; i < d.length; i += 4) if (Math.abs(d[i] - r0) + Math.abs(d[i + 1] - g0) + Math.abs(d[i + 2] - b0) > 24) drawn++;
    return {width: r.width, height: r.height, visible: r.width > 0 && r.height > 0 && getComputedStyle(c).display !== 'none',
      drawn, pixels: d.length / 4, scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth};
  }, selector);
}
async function tabTo(page, test, limit = 200, arg = null) {
  for (let i = 1; i <= limit; i++) { await page.keyboard.press('Tab'); if (await page.evaluate(test, arg)) return i; }
  return null;
}
async function download(page, trigger) {
  const done = page.waitForEvent('download', {timeout: 30000});
  await trigger();
  const asked = await page.waitForSelector('#save-name-dialog[open]', {timeout: 3000}).then(() => true, () => false);
  if (asked) await page.click('#save-name-download');
  return readFile(await (await done).path(), 'utf8');
}
// X7: the run table's Heat source cell, built from the last run's record: total source and its document's regions
async function sourceFromRecord(page, seen) {
  const rec = await page.evaluate(async id => (await fetch(`/api/model3d/runs/${id}/record?maps=kept`)).json(), seen.runs.at(-1));
  return `${Number(rec.values.total_source.value.toPrecision(6))} ${rec.values.total_source.unit} in ${Object.keys(rec.document.physics.heat.heat_source_density || {}).join(', ')}`;
}
async function openFile(page, name, text) {
  await page.setInputFiles('#session-file', {name, mimeType: 'application/json', buffer: Buffer.from(text)});
}
const save = page => download(page, async () => { await page.click('#file-menu-button'); await page.click('#menu-save'); });
const exportSession = page => download(page, async () => { await page.click('#file-menu-button'); await page.click('#menu-export'); await page.click('#menu-export-session'); });
const entry = text => JSON.parse(text).models.find(m => m.kind === 'model3d');
const runDigests = session => (session.runs || []).map(r => ({values: sha(canonical(r.values)), surface: sha(r.surface?.temperature || '') + ':' + sha(r.surface?.positions || '')}));

const browser = await chromium.launch();
try {
  // ---- W12 Results, and W14 recorded ------------------------------------------------------------
  for (const viewport of [{width: 1440, height: 900}, {width: 390, height: 844}]) {
    const tag = `${viewport.width}x${viewport.height}`;
    const {page, seen} = await open(browser, viewport);
    await page.click('[data-model3d-card]'); await checked(page);
    const t0 = Date.now();
    await page.click('#m3-run'); await completed(page, 1);
    await page.waitForTimeout(300);
    const toResult = Date.now() - t0;
    const state = await canvasState(page, '#m3-result-canvas');
    const shown = await page.evaluate(() => ({bar: document.querySelector('.m3-colourbar')?.getAttribute('aria-label') || '',
      values: [...document.querySelectorAll('#m3-values tr')].map(r => [r.querySelector('th').textContent, r.querySelector('td').textContent]),
      selected: document.querySelector('#tree [aria-selected="true"]')?.dataset.m3Node}));
    await page.screenshot({path: join(out, `w12-results-${tag}.png`), fullPage: true});
    const c = await csp(page);
    shown.source = await sourceFromRecord(page, seen);
    const ok = !seen.console.length && !seen.pageErrors.length && !c.length && !seen.foreign.length && state.visible && state.drawn > 0.02 * state.pixels
      && /^Surface temperature from 300 K \(blue\) to 1127\.33 K \(red\)$/.test(shown.bar) && shown.values.length === 6 && shown.selected === 'run:1'
      && shown.source === '4 W in Si (top)' && JSON.stringify(shown.values[2]) === JSON.stringify(['Heat source', shown.source])
      && (viewport.width !== 390 || state.scrollWidth <= state.innerWidth);
    record(`W12 results ${tag}`, ok, {canvas: state, ...shown, console: seen.console, pageErrors: seen.pageErrors, csp: c, foreign: seen.foreign});
    if (viewport.width === 1440) {
      const t1 = Date.now();
      await page.selectOption('#m3-section-axis', 'z'); await page.fill('#m3-section-at', '505'); await page.click('#m3-section-go');
      await page.waitForFunction(() => /^Cut z = 505/.test(document.querySelector('#mp-messages .mp-message.info p')?.textContent || ''), null, {timeout: 30000});
      const cut = Date.now() - t1;
      await page.screenshot({path: join(out, 'w14-cut.png')});
      report.checks.W14 = {ok: true, recordedOnly: true, renderer: 'SwiftShader (headless Chromium)', runToDrawnResultMs: toResult, cutMs: cut};
      console.log(`W14 recorded: run to result ${toResult} ms, cut ${cut} ms`);
    }
    await page.close();
  }

  // ---- W10 "No need to run", and W11 with runs ---------------------------------------------------
  {
    const {page, seen} = await open(browser, {width: 1440, height: 900});
    await page.click('[data-model3d-card]'); await checked(page);
    await page.click('#m3-run'); await completed(page, 1);
    const states = {};
    states.afterRun = await noNeed(page);
    // an edit: the fixed temperature 300 K → 301 K
    await page.click('[data-m3-node="heat:fixed:z0"]');
    await page.fill('[data-m3-heat="fixed"][data-m3-key="z0"]', '301'); await page.press('[data-m3-heat="fixed"][data-m3-key="z0"]', 'Enter');
    await checked(page);
    states.afterEdit = await noNeed(page);
    await page.click('#undo-edit'); await checked(page);
    states.afterUndo = await noNeed(page);
    await page.click('#redo-edit'); await checked(page);
    states.afterRedo = await noNeed(page);
    await page.click('[data-m3-node="run:1"]');
    await page.click('[data-m3-run-act="inputs"]'); await checked(page);
    states.afterUseInputs = await noNeed(page);
    // one Undo step takes "Use this run's inputs" back
    await page.click('#undo-edit'); await checked(page);
    const undoInputs = await noNeed(page);
    await page.click('#redo-edit'); await checked(page);
    const first = await save(page);
    await openFile(page, 'project.json', first); await checked(page);
    states.afterSaveOpen = await noNeed(page);
    const expected = {afterRun: true, afterEdit: false, afterUndo: true, afterRedo: false, afterUseInputs: true, afterSaveOpen: true};
    const matched = Object.keys(expected).filter(k => states[k] === expected[k]).length;
    record('W10', matched === 6 && undoInputs === false && !seen.pageErrors.length, {matched, of: 6, states, undoInputsTakesItBack: undoInputs === false, pageErrors: seen.pageErrors});

    // W11: the project saved again, and a session export opened and exported again
    await page.click('[data-m3-node="run:1"]');
    const recompute = await page.evaluate(() => document.getElementById('m3-recompute-why')?.textContent || '');
    const second = await save(page);
    const a = entry(first), b = entry(second);
    const projectOk = JSON.parse(first).version === 2 && a.digest === b.digest && a.session.runs?.length === 1
      && sha(canonical(a.session.document)) === sha(canonical(b.session.document))
      && JSON.stringify(runDigests(a.session)) === JSON.stringify(runDigests(b.session));
    const s1 = await exportSession(page);
    await openFile(page, 'model3d-session.json', s1); await checked(page);
    const s2 = await exportSession(page);
    const sessionOk = s1 === s2 && JSON.parse(s1).runs?.length === 1 && JSON.stringify(runDigests(JSON.parse(s1))) === JSON.stringify(runDigests(a.session))
      && sha(canonical(JSON.parse(s1).document)) === sha(canonical(a.session.document));
    await openFile(page, 'project-v1.json', V1);
    await page.waitForFunction(() => /Opened project/.test(document.getElementById('file-status').textContent), null, {timeout: 30000});
    const v1Again = await save(page);
    const strip = t => JSON.parse(t).models.map(m => [m.id, m.kind, m.bytes, m.digest]);
    const again = strip(v1Again), fixture = strip(V1);
    const v1Ok = JSON.parse(v1Again).version === 1 && JSON.stringify(again.map(m => m[1])) === '["workspace","multiphysics"]'
      && JSON.stringify(again[1]) === JSON.stringify(fixture[1]) && again[0][2] === 7649 && again[0][3].startsWith('sha256:b94ec466');
    await writeFile(join(out, 'w11-project.json'), first); await writeFile(join(out, 'w11-session.json'), s1);
    record('W11 with runs', projectOk && sessionOk && v1Ok && recompute === 'Recompute this run to cut, probe or export CSV.' && !seen.pageErrors.length,
      {projectOk, sessionOk, v1Ok, recompute, projectDigest: [a.digest, b.digest], runs: runDigests(a.session), sessionSha: [sha(s1), sha(s2)], pageErrors: seen.pageErrors});
    await page.close();
  }

  // ---- W13: keyboard only ------------------------------------------------------------------------
  {
    const {page, seen} = await open(browser, {width: 1440, height: 900});
    const steps = {};
    steps.cardFocused = await tabTo(page, () => document.activeElement?.dataset?.model3dCard === 'layer-stack-3d') !== null;
    await page.keyboard.press('Enter'); await checked(page);
    steps.canvasFocused = await tabTo(page, () => document.activeElement?.id === 'm3-canvas') !== null;
    await page.keyboard.press('ArrowLeft');
    steps.rotated = await page.evaluate(() => document.getElementById('m3-canvas').dataset.camera) === 'rotate';
    await page.keyboard.press('5');
    steps.view5 = await page.evaluate(() => document.getElementById('m3-canvas').dataset.camera) === '+z';
    const pickFromList = async name => {
      const found = await tabTo(page, n => !!document.activeElement?.closest('#m3-faces') && document.activeElement.getAttribute('aria-label').split(': ')[1].split(', ').includes(n), 200, name);
      await page.keyboard.press('Enter');
      return found !== null && (await page.evaluate(() => [...document.querySelectorAll('#m3-names code')].map(e => e.textContent))).includes(name);
    };
    const useForFixed = async () => {
      const onUse = await tabTo(page, () => document.activeElement?.id === 'm3-use', 60) !== null;
      await page.keyboard.press('ArrowDown');                       // New selection → Fixed temperature
      const fixed = await page.evaluate(() => document.getElementById('m3-use').value === 'fixed');
      const name = await page.evaluate(() => document.getElementById('m3-use-name').value);
      // V1: the temperature is typed in the Use row before Apply (by keyboard)
      const onTemp = await tabTo(page, () => document.activeElement?.id === 'm3-use-temp', 10) !== null;
      await page.keyboard.type('300');
      const onApply = onTemp && await tabTo(page, () => document.activeElement?.id === 'm3-use-go', 10) !== null;
      await page.keyboard.press('Enter');
      return {onUse, fixed, name, onApply};
    };
    const before = JSON.stringify(await page.evaluate(() => document.querySelector('[data-m3-node="heat:fixed:z0"]')?.textContent));
    steps.viaSelected = await pickFromList('via.z1');
    steps.viaUse = await useForFixed();
    await page.waitForSelector('[data-m3-use-refusal]', {timeout: 30000});
    steps.refusal = await page.evaluate(() => document.querySelector('[data-m3-use-refusal] > p').textContent);
    steps.refusalFocused = await page.evaluate(() => !!document.activeElement?.closest('[data-m3-use-refusal]'));
    steps.unchanged = !(await page.evaluate(() => [...document.querySelectorAll('#tree [data-m3-node]')].some(b => b.dataset.m3Node === 'heat:fixed:via.z1')))
      && JSON.stringify(await page.evaluate(() => document.querySelector('[data-m3-node="heat:fixed:z0"]')?.textContent)) === before;
    steps.topSelected = await pickFromList('stack.top.top');
    steps.topUse = await useForFixed();
    await page.waitForSelector('[data-m3-node="heat:fixed:stack.top.top"]', {timeout: 30000}); await checked(page);
    // a section: z = 300 µm
    steps.sectionAxis = await tabTo(page, () => document.activeElement?.id === 'm3-section-axis', 200) !== null;
    await page.keyboard.press('ArrowDown'); await page.keyboard.press('ArrowDown'); await page.keyboard.press('ArrowDown');   // none → x → y → z
    await page.keyboard.press('Tab'); await page.keyboard.type('300'); await page.keyboard.press('Tab'); await page.keyboard.press('Enter');
    await page.waitForTimeout(800);
    steps.section = await page.evaluate(() => [document.getElementById('m3-section-axis').value, document.getElementById('m3-section-at').value]);
    // Run, to completion
    steps.runFocused = await tabTo(page, () => document.activeElement?.id === 'm3-run', 200) !== null;
    await page.keyboard.press('Enter');
    await completed(page, 1);
    // two fixed temperatures (z0 and stack.top.top): max, min, a heat rate through each, the source, the balance
    steps.values = await page.evaluate(() => [...document.querySelectorAll('#m3-values tr')].map(r => [r.querySelector('th').textContent, r.querySelector('td').textContent]));
    steps.source = await sourceFromRecord(page, seen);
    steps.pointerEvents = await page.evaluate(() => window.__pointer);
    await page.screenshot({path: join(out, 'w13-keyboard.png')});
    const ok = steps.cardFocused && steps.canvasFocused && steps.rotated && steps.view5 && steps.viaSelected
      && steps.viaUse.onUse && steps.viaUse.fixed && steps.viaUse.name === 'via.z1' && steps.viaUse.onApply
      && steps.refusal === INSIDE && steps.refusalFocused && steps.unchanged
      && steps.topSelected && steps.topUse.fixed && steps.topUse.name === 'stack.top.top' && steps.topUse.onApply
      && steps.sectionAxis && steps.section[0] === 'z' && steps.section[1] === '300' && steps.runFocused
      && JSON.stringify(steps.values.map(v => v[0])) === JSON.stringify(['Temperature, max (whole model)', 'Temperature, min (whole model)', 'Heat source', 'Heat rate through z0',
        'Heat rate through stack.top.top', 'Total heat source', 'Energy balance residual']) && steps.source === '4 W in Si (top)' && steps.values[2][1] === steps.source && steps.pointerEvents === 0 && !seen.console.length && !seen.pageErrors.length;
    record('W13', ok, {steps, console: seen.console, pageErrors: seen.pageErrors});
    await page.close();
  }

  // ---- card 2, Copper via through a slab (E2-UI): W12, W6-UI, W14, F2, W11, W13 ----------------
  const NOTE = 'Shape drawn for display; the mesh follows it to within its size';
  for (const viewport of [{width: 1440, height: 900}, {width: 390, height: 844}]) {
    const tag = `${viewport.width}x${viewport.height}`;
    const {page, seen} = await open(browser, viewport);
    let runId = null;
    page.on('response', async r => { if (r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/model3d/run') runId = (await r.json().catch(() => ({}))).run || runId; });
    const lib = await page.evaluate(() => ({card: !!document.querySelector('.library-3d [data-model3d-card="via-slab-3d"]'),
      scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth}));
    await page.click('[data-model3d-card="via-slab-3d"]'); await checked(page);
    const geometry = await canvasState(page, '#m3-canvas');
    await page.screenshot({path: join(out, `w12-card2-model-${tag}.png`), fullPage: true});
    // the display note, on the curved face via.side (the names panel, as main shows it)
    const side = await page.evaluate(() => [...document.querySelectorAll('#m3-faces li')].find(li => li.getAttribute('aria-label').endsWith(': via.side'))?.dataset.face);
    await page.click(`#m3-faces li[data-face="${side}"]`);
    const note = await page.evaluate(() => document.getElementById('m3-names').textContent);
    await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });
    const tabs = await tabTo(page, () => !!document.activeElement?.closest('#m3-faces'));
    // Mesh 1, Mesh: the mesh view
    await page.click('[data-m3-node="mesh"]'); await page.click('#m3-mesh');
    await page.waitForFunction(() => /^Meshed /.test(document.getElementById('mp-messages')?.textContent || '') && document.getElementById('m3-mesh-canvas'), null, {timeout: 180000});
    await page.waitForTimeout(300);
    const meshView = await canvasState(page, '#m3-mesh-canvas');
    await page.screenshot({path: join(out, `w12-card2-mesh-${tag}.png`), fullPage: true});
    // Run: the result
    const t0 = Date.now();
    await page.click('#m3-run'); await completed(page, 1); await page.waitForTimeout(300);
    const toResult = Date.now() - t0;
    const result = await canvasState(page, '#m3-result-canvas');
    await page.screenshot({path: join(out, `w12-card2-result-${tag}.png`), fullPage: true});
    const c = await csp(page);
    const ok = lib.card && !seen.console.length && !seen.pageErrors.length && !c.length && !seen.foreign.length
      && [geometry, meshView, result].every(st => st.visible && st.drawn > 0.02 * st.pixels) && tabs !== null && note.includes(NOTE)
      && (viewport.width !== 390 || [geometry, meshView, result].every(st => st.scrollWidth <= st.innerWidth) && lib.scrollWidth <= lib.innerWidth);
    record(`W12 card 2 ${tag}`, ok, {library: lib, geometry, meshView, result, tabsToFacesList: tabs, note: note.includes(NOTE), console: seen.console,
      pageErrors: seen.pageErrors, csp: c, foreign: seen.foreign});
    if (viewport.width === 1440) {
      // W6-UI: Run 1's values table equals the run route's /values, through the page's own rows
      const values = await page.evaluate(async id => (await fetch(`/api/model3d/runs/${id}/values`)).json(), runId);
      const table = await page.evaluate(() => [...document.querySelectorAll('#m3-values tr')].map(r => [r.querySelector('th').textContent, r.querySelector('td').textContent]));
      // the route's values through the page's rows, with the expected heat rate of the run's document beside z0
      const fromRoute = await page.evaluate(async ([v, d]) => { const M = await import('/workspace-assets/workspace-model3d.mjs');
        return M.valuesRows(v, 'm', {expected: M.expectedHeatRate(d)}); }, [values, CARD2]);
      const expectedLine = table.find(r => r[0] === 'Expected heat rate')?.join(' ');
      record('W6-UI card 2', JSON.stringify(table) === JSON.stringify(fromRoute) && table.length === 7
        && expectedLine === 'Expected heat rate 31.99 W (parallel formula)', {run: runId, table, fromRoute, expectedLine,
        heatRates: values.heat_rate_by_selection, relativeResidual: values.relative_balance_residual});
      // W14 (recorded only)
      const t1 = Date.now();
      await page.selectOption('#m3-section-axis', 'x'); await page.fill('#m3-section-at', '0'); await page.click('#m3-section-go');
      await page.waitForFunction(() => /^Cut x = 0/.test(document.querySelector('#mp-messages .mp-message.info p')?.textContent || ''), null, {timeout: 30000});
      const cut = Date.now() - t1;
      await page.screenshot({path: join(out, 'w14-card2-cut.png')});
      report.checks['W14 card 2'] = {ok: true, recordedOnly: true, renderer: 'SwiftShader (headless Chromium)', runToDrawnResultMs: toResult, cutMs: cut};
      console.log(`W14 card 2 recorded: run to result ${toResult} ms, cut ${cut} ms`);
      // W11: Save and Open with the run, project and session
      const first = await save(page);
      await openFile(page, 'project.json', first); await checked(page);
      const second = await save(page);
      const a = entry(first), b = entry(second);
      const projectOk = JSON.parse(first).version === 2 && a.card === 'via-slab-3d' && b.card === 'via-slab-3d' && a.digest === b.digest && a.session.runs?.length === 1
        && sha(canonical(a.session.document)) === sha(canonical(b.session.document)) && JSON.stringify(runDigests(a.session)) === JSON.stringify(runDigests(b.session));
      const s1 = await exportSession(page);
      await openFile(page, 'card2-session.json', s1); await checked(page);
      const s2 = await exportSession(page);
      const sessionOk = s1 === s2 && JSON.parse(s1).runs?.length === 1 && JSON.stringify(runDigests(JSON.parse(s1))) === JSON.stringify(runDigests(a.session));
      await openFile(page, 'project-v1.json', V1);
      await page.waitForFunction(() => /Opened project/.test(document.getElementById('file-status').textContent), null, {timeout: 30000});
      const v1Again = await save(page);
      const strip = t => JSON.parse(t).models.map(m => [m.id, m.kind, m.bytes, m.digest]);
      const v1Ok = JSON.parse(v1Again).version === 1 && JSON.stringify(strip(v1Again)[1]) === JSON.stringify(strip(V1)[1]);
      await writeFile(join(out, 'w11-card2-project.json'), first);
      record('W11 card 2', projectOk && sessionOk && v1Ok && !seen.pageErrors.length, {projectOk, sessionOk, v1Ok, card: a.card,
        projectDigest: [a.digest, b.digest], runs: runDigests(a.session), sessionSha: [sha(s1), sha(s2)]});
    }
    await page.close();
  }
  // F2 on card 2: Add feature → Sphere is shown refused in the engine's words, not silently fixed
  {
    const {page, seen} = await open(browser, {width: 1440, height: 900});
    await page.click('[data-model3d-card="via-slab-3d"]'); await checked(page);
    await page.click('[data-m3-node="geometry"]');
    const offered = await page.evaluate(() => [...document.querySelectorAll('[data-m3-add]')].map(b => b.textContent));
    await page.click('[data-m3-add="sphere"]');
    await page.waitForSelector('[data-m3-refusal]', {timeout: 30000});
    const shown = await page.evaluate(() => ({text: document.querySelector('[data-m3-refusal] p').textContent,
      rows: [...document.querySelectorAll('#tree [data-m3-node^="feature:"]')].map(b => b.textContent),
      marked: [...document.querySelectorAll('[data-m3-node].has-problem')].map(b => b.dataset.m3Node)}));
    const ok = JSON.stringify(offered) === JSON.stringify(['Box', 'Layers', 'Cylinder', 'Sphere'])
      && shown.text === "sphere 'sphere' is not taken yet in a 3d component; boxes and slab layers are, and cylinders and spheres in meshloom's builder shapes only (one cylinder through the whole slab, one sphere, concentric spheres)"
      && shown.rows.length === 2 && /2 Sphere sphere/.test(shown.rows[1]) && JSON.stringify(shown.marked) === '["feature:1"]' && !seen.pageErrors.length;
    record('F2 card 2', ok, {offered, ...shown});
    await page.close();
  }
  // W13 on card 2: keyboard only; Use for → Fixed temperature on via.side is the kind's refusal; Run
  {
    const {page, seen} = await open(browser, {width: 1440, height: 900});
    const steps = {};
    steps.cardFocused = await tabTo(page, () => document.activeElement?.dataset?.model3dCard === 'via-slab-3d') !== null;
    await page.keyboard.press('Enter'); await checked(page);
    steps.canvasFocused = await tabTo(page, () => document.activeElement?.id === 'm3-canvas') !== null;
    await page.keyboard.press('ArrowLeft');
    steps.rotated = await page.evaluate(() => document.getElementById('m3-canvas').dataset.camera) === 'rotate';
    await page.keyboard.press('5');
    steps.view5 = await page.evaluate(() => document.getElementById('m3-canvas').dataset.camera) === '+z';
    steps.sideFocused = await tabTo(page, n => !!document.activeElement?.closest('#m3-faces') && document.activeElement.getAttribute('aria-label').split(': ')[1].split(', ').includes(n), 200, 'via.side') !== null;
    await page.keyboard.press('Enter');
    steps.onUse = await tabTo(page, () => document.activeElement?.id === 'm3-use', 60) !== null;
    await page.keyboard.press('ArrowDown');
    steps.fixed = await page.evaluate(() => document.getElementById('m3-use').value === 'fixed');
    steps.name = await page.evaluate(() => document.getElementById('m3-use-name').value);
    // V1: the temperature is typed in the Use row before Apply (by keyboard)
    steps.onTemp = await tabTo(page, () => document.activeElement?.id === 'm3-use-temp', 10) !== null;
    await page.keyboard.type('300');
    steps.onApply = await tabTo(page, () => document.activeElement?.id === 'm3-use-go', 10) !== null;
    await page.keyboard.press('Enter');
    await page.waitForSelector('[data-m3-use-refusal]', {timeout: 30000});
    steps.refusal = await page.evaluate(() => document.querySelector('[data-m3-use-refusal] > p').textContent);
    steps.unchanged = await page.evaluate(() => [...document.querySelectorAll('#tree [data-m3-node^="heat:fixed:"]')].map(b => b.dataset.m3Node));
    steps.runFocused = await tabTo(page, () => document.activeElement?.id === 'm3-run', 200) !== null;
    await page.keyboard.press('Enter');
    await completed(page, 1);
    steps.values = await page.evaluate(() => document.querySelectorAll('#m3-values tr').length);
    steps.pointerEvents = await page.evaluate(() => window.__pointer);
    await page.screenshot({path: join(out, 'w13-card2-keyboard.png')});
    const ok = steps.cardFocused && steps.canvasFocused && steps.rotated && steps.view5 && steps.sideFocused && steps.onUse && steps.fixed
      && steps.name === 'via.side' && steps.onApply && steps.refusal === 'Fixed temperature needs an outer face; via.side is inside'
      && JSON.stringify(steps.unchanged) === '["heat:fixed:z0","heat:fixed:z1"]' && steps.runFocused && steps.values === 7
      && steps.pointerEvents === 0 && !seen.console.length && !seen.pageErrors.length;
    record('W13 card 2', ok, {steps, console: seen.console, pageErrors: seen.pageErrors});
    await page.close();
  }
} finally {
  await writeFile(join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}
if (failed) process.exit(1);
