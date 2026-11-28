// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Studio 3D fixes V1–V11 (agent round 3D-2) in a real browser, against a local Studio on this branch:
//   node tools/studio_browser/model3d_v_browser.mjs http://127.0.0.1:8765 out-dir [V5,V4,...]
// Pre-registered checks (thresholds fixed before measuring, accepted by the coordinator), one row
// per item (the rows run in the order given; a third argument runs only the rows named):
//  V5  card 1 with 300 K on z0 and z1, Run: Messages reads "Run 1 complete: maximum <T> K at the SiO2 /
//      Si (top) interface." with the same place words as the Settings row (whole model): 1/1.
//  V4  card 1, every face picked in the Faces list in turn: no "um" in the visible text of the Names
//      box or the Faces list ("z = 510 µm", "area 400 µm²"): 1/1.
//  V7  card 1: Mesh, Run, size 30 µm, Mesh, then size 2 µm (refused): the Mesh 1 page labels the
//      earlier stats "Kept mesh (before the last change)"; the run status line is gone after the new
//      mesh; Messages reads "Meshed Component 1 …" (no "stack3d"); the line gives the elapsed time
//      ("… in 1.2 s: …"): 4/4.
//  V11 at 1440 × 900: card 1's Parameters table has no Use cell clipped and no horizontal scroll in
//      its pane; the ribbon's Compute shows Run for the 3D model and it runs (Run 1 completes), while
//      the optical model shows none; card 1's note says "Preset: heat source 1e12 W/m³ in Si (top)
//      (4 W)": 3/3.
//  V6  card 2: Run 1, z1 302 K, Run 2, Compare: right under the table one line reads "Heat rates keep
//      the run table's sign … B − A is run B minus run A, so −… W through z0 means more heat leaves
//      through z0 in run B."; it equals the helper on the two runs' /values: 2/2.
//  V9  card 1: via.z1's names each say "only this face" or "also face N" exactly as the server's check
//      display gives them (one of each kind), with "Interior face: hide Si (top), the region above
//      it, with Regions in the view toolbar to see it."; stack.top.top (exterior): its scopes equal
//      the check's and no interior line: 3/3.
//  V1  card 1, stack.top.top, Use for → Fixed temperature: a "Temperature (K)" box with a label, empty,
//      placeholder "e.g. 330"; Apply disabled with "Type a temperature in K to apply." (then the parser's
//      own reason for -5) by aria-describedby; 330 + Apply: the node reads "stack.top.top · 330 K" and
//      one Undo removes it; Messages "Fixed temperature 330 K on stack.top.top." (no 300 K); the node is
//      selected with its Temperature 330: 5/5.
//  V10 card 2, cx = 0.8: Messages reads "Cylinder via crosses the domain side x = 1 m. Keep cx ≤ 0.7 m
//      (cx + r ≤ 1 m), or r ≤ 0.2 m.", with the engine's sentence and code under Details: 1/1.
//  V3  card 1 at 2 µm: Messages equals meshRefusalText of the server's refusal and names both sizes
//      (the smallest the limit takes, and one estimated at about a minute, each with its estimate);
//      the check at the minute size answers the refusal's tetrahedra and at most 60 s; the tree's Mesh 1
//      note reads "too fine": 3/3. All numbers are the server's at test time.
//  V8  card 1 (300 K on z0 and z1), Run, Section z = 505, view +z zoomed (6 × +): the cut's pixels (every one) reach the colour
//      map's blue and red ends within 12/255 per channel; their mean HSV saturation is ≥ 0.25; the cut's
//      legend is in view without scrolling at 1440 × 900: 3/3. Screenshots: v8-surface.png, v8-cut.png.
//  V2a an optical run (a recovery record), then card 1 with a run; in the Library card 2 reads "Open in
//      a new tab" with "This project holds Via in a layer stack (3D heat); a project holds one 3D
//      model."; one click opens /workspace?card=via-slab-3d&fresh=1 with card 2 (no Messages step);
//      the first tab keeps both models and the recovery record (session) unchanged; in the new tab,
//      card 1 reads the same with card 2's title: 4/4.
//  V2b "Replace the 3D model…": the dialog's lines equal replaceLines for the unsaved state, and after
//      its File › Save for the saved state (that file's name); Cancel changes nothing; Replace opens
//      card 2 and leaves the recovery record's session as it was; Messages' Undo brings card 1 back:
//      a new File › Save has the same model3d digest (document and runs) and the same workspace digest
//      as the save before Replace, with the recovery session unchanged; the save holds card 1 and the
//      optical model: 5/5.
// It writes report.json to out-dir and exits non-zero if a check fails.
import {createRequire} from 'node:module';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';

const require = createRequire(import.meta.url);
const {chromium} = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:8765';
const out = process.argv[3] || 'model3d-v-browser';
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
const browser = await chromium.launch();
try {
  // ---- V5: the line after a run uses the Settings table's place words ----
  if (want('V5')) {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card]');
    const doc = structuredClone(CARD); doc.physics.heat.prescribed_temperature = {z0: '300 K', z1: '300 K'};
    await openFile(page, 'v5.json', session(doc)); await checked(page);
    await page.click('#m3-run'); await completed(page, 1); await page.waitForTimeout(300);
    const got = await page.evaluate(() => ({messages: document.getElementById('mp-messages')?.textContent || '',
      row: [...document.querySelectorAll('#m3-values tr')].map(r => r.querySelector('td').textContent)[0]}));
    const place = /K (at the .+ interface), \(/.exec(got.row)?.[1];
    const line = /Run 1 complete: maximum [\d.]+ K ([^.]+)\./.exec(got.messages)?.[1];
    const rows = [!!place && line === place && place === 'at the SiO2 / Si (top) interface'];
    record('V5', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 1, place, line, row: got.row});
    await ctx.close();
  }
  // ---- V4: µm in the Names box and the Faces list, every face of card 1 picked in turn ----
  if (want('V4')) {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card="layer-stack-3d"]');
    await page.click('[data-model3d-card="layer-stack-3d"]'); await checked(page);
    const ids = await page.evaluate(() => [...document.querySelectorAll('#m3-faces li')].map(li => li.dataset.face));
    const um = [];
    const scan = async label => { const t = await page.evaluate(() => (document.getElementById('m3-names')?.innerText || '') + '\n' + (document.getElementById('m3-faces')?.innerText || ''));
      for (const m of t.matchAll(/.{0,25}\bum\b.{0,10}/g)) um.push([label, m[0]]); };
    await scan('none');
    for (const id of ids) { await page.click(`#m3-faces li[data-face="${id}"]`); await page.waitForTimeout(60); await scan(`face ${id}`); }
    const sample = await page.evaluate(() => document.getElementById('m3-names')?.innerText.split('\n').slice(0, 3).join(' | '));
    const rows = [ids.length > 0 && um.length === 0];
    record('V4', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 1, faces: ids.length, um: um.slice(0, 6), sample});
    await ctx.close();
  }
  // ---- V7: mesh status: Component 1 with the elapsed time; the run line cleared; kept stats labelled ----
  if (want('V7')) {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card="layer-stack-3d"]');
    await page.click('[data-model3d-card="layer-stack-3d"]'); await checked(page);
    const meshed = () => page.waitForFunction(() => /Meshed Component 1/.test(document.getElementById('mp-messages')?.textContent || ''), null, {timeout: 180000});
    const message = () => page.evaluate(() => [...document.querySelectorAll('#mp-messages .mp-message p')].map(p => p.textContent).find(t => t.startsWith('Meshed')) || '');
    await page.click('#m3-mesh'); await meshed(); const first = await message();
    await page.click('#m3-run'); await completed(page, 1); await page.waitForTimeout(300);
    const runLine = await page.evaluate(() => !!document.getElementById('m3-run-progress'));
    await page.click('[data-m3-node="mesh"]'); await setField(page, 'mesh.element_size', '30');
    await page.click('#m3-mesh'); await meshed(); await page.waitForTimeout(300);
    const second = await message();
    const afterMesh = await page.evaluate(() => !!document.getElementById('m3-run-progress'));
    await page.click('[data-m3-node="mesh"]'); await setField(page, 'mesh.element_size', '2');
    await page.click('[data-m3-node="mesh"]'); await page.waitForTimeout(200);
    const kept = await page.evaluate(() => ({label: document.getElementById('m3-kept-mesh')?.textContent || '',
      stats: !!document.querySelector('#m3-kept-mesh + .m3-mesh-stats')}));
    const rows = [
      kept.label === 'Kept mesh (before the last change)' && kept.stats,
      runLine && !afterMesh,
      /^Meshed Component 1\b/.test(first) && /^Meshed Component 1\b/.test(second) && !/stack3d/.test(first + second),
      /^Meshed Component 1 in (\d+(\.\d)? s|\d+ min \d+ s): /.test(second),
    ];
    record('V7', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 4, first, second, runLine, afterMesh, kept});
    await ctx.close();
  }
  // ---- V11: the Parameters table's Use column not clipped; the ribbon's Run; card 1's preset source ----
  if (want('V11')) {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card="layer-stack-3d"]');
    const note = await page.evaluate(() => document.querySelector('[data-model3d-card="layer-stack-3d"] .card-scope')?.textContent || '');
    await page.click('[data-model3d-card="layer-stack-3d"]'); await checked(page);
    await page.click('[data-m3-node="parameters"]'); await page.waitForTimeout(200);
    const table = await page.evaluate(() => { const t = document.querySelector('.m3-params'), pane = document.getElementById('inspector');
      const cells = [...document.querySelectorAll('.m3-params .m3-param-use')];
      const box = c => c.getBoundingClientRect(), pb = box(pane);
      return {tableWidth: t?.scrollWidth, pane: pane.clientWidth, paneScroll: pane.scrollWidth - pane.clientWidth,
        use: cells.map(c => c.textContent), clipped: cells.filter(c => c.scrollWidth > c.clientWidth + 1 || box(c).right > pb.right + 1).length}; });
    // the ribbon's Run in a 3D model: shown, and it starts the run (Run 1 completes)
    const ribbon = await page.evaluate(() => { const b = document.getElementById('run-model3d'); return {shown: !!b && !b.hidden && b.offsetParent !== null, text: b?.textContent || ''}; });
    let ran = false;
    if (ribbon.shown) { await page.click('#run-model3d'); ran = await completed(page, 1).then(() => true, () => false); }
    await ctx.close();
    // a 2D model: no 3D Run in the ribbon
    const d2 = await open(browser);
    await d2.page.waitForFunction(() => !!document.querySelector('[data-template=optical]'));
    await d2.page.click('[data-template=optical]'); await d2.page.waitForTimeout(500);
    const flat = await d2.page.evaluate(() => { const b = document.getElementById('run-model3d'); return !b || b.hidden || b.offsetParent === null; });
    await d2.ctx.close();
    const rows = [
      table.use.length === 2 && table.clipped === 0 && table.paneScroll <= 0,
      ribbon.shown && ribbon.text === 'Run' && ran && flat,
      note.includes('Preset: heat source 1e12 W/m³ in Si (top) (4 W)'),
    ];
    record('V11', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 3, table, ribbon, ran, flat, note});
  }
  // ---- V6: Compare's line on the heat-rate sign ----
  if (want('V6')) {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card="via-slab-3d"]');
    await page.click('[data-model3d-card="via-slab-3d"]'); await checked(page);
    const ids = [];
    page.on('response', async r => { if (r.url().endsWith('/api/model3d/run') && r.request().method() === 'POST') { try { ids.push((await r.json()).run); } catch {} } });
    await page.click('#m3-run'); await completed(page, 1); await page.waitForTimeout(300);
    await page.click('#tree [data-m3-node="heat:fixed:z1"]');
    await page.fill('[data-m3-heat="fixed"][data-m3-key="z1"]', '302'); await page.press('[data-m3-heat="fixed"][data-m3-key="z1"]', 'Enter');
    await page.waitForTimeout(200); await checked(page);
    await page.click('#m3-run'); await completed(page, 2); await page.waitForTimeout(300);
    await page.click('[data-page="Compare"]'); await page.waitForSelector('#m3-compare-values');
    const line = await page.evaluate(() => document.getElementById('m3-compare-sign')?.textContent || '');
    const under = await page.evaluate(() => document.getElementById('m3-compare-values')?.nextElementSibling?.id || '');
    const direct = await page.evaluate(async ids => { const C = await import('/workspace-assets/workspace-model3d-compare.mjs');
      const v = async id => (await fetch(`/api/model3d/runs/${id}/values`)).json(); return C.heatRateNote(await v(ids[0]), await v(ids[1])); }, ids);
    const rows = [under === 'm3-compare-sign' && /means more heat leaves through z0 in run B\.$/.test(line), line === direct];
    record('V6', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 2, line, direct, under});
    await ctx.close();
  }
  // ---- V9: names marked "only this face" or "also face N"; an interior face says how to see it ----
  if (want('V9')) {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card="layer-stack-3d"]');
    await page.click('[data-model3d-card="layer-stack-3d"]'); await checked(page);
    const answer = await serverCheck(page, CARD);
    const expect = id => { const f = answer.display.faces[id];
      return f.names.map(n => { const o = answer.display.faces.filter(g => g.id !== id && g.names.includes(n)).map(g => `face ${g.id}`); return [n, o.length ? `also ${o.join(', ')}` : 'only this face']; }); };
    const shown = async id => { await page.click(`#m3-faces li[data-face="${id}"]`); await page.waitForTimeout(80);
      return page.evaluate(() => ({scopes: [...document.querySelectorAll('#m3-names li')].map(li => [li.querySelector('code').textContent, li.querySelector('.m3-name-scope')?.textContent || '']),
        hint: document.getElementById('m3-names-interior')?.textContent ?? null})); };
    const z1 = answer.display.faces.find(f => f.alone.includes('via.z1')).id, top = answer.display.faces.find(f => f.alone.includes('stack.top.top')).id;
    const a = await shown(z1), b = await shown(top);
    const rows = [
      JSON.stringify(a.scopes) === JSON.stringify(expect(z1)) && a.scopes.some(s => s[1] === 'only this face') && a.scopes.some(s => s[1].startsWith('also face')),
      a.hint === 'Interior face: hide Si (top), the region above it, with Regions in the view toolbar to see it.',
      JSON.stringify(b.scopes) === JSON.stringify(expect(top)) && b.hint === null,
    ];
    record('V9', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 3, z1: a, top: b});
    await ctx.close();
  }
  // ---- V1: Use for → Fixed temperature takes its value in the Use row ----
  if (want('V1')) {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card="layer-stack-3d"]');
    await page.click('[data-model3d-card="layer-stack-3d"]'); await checked(page);
    const top = await page.evaluate(() => [...document.querySelectorAll('#m3-faces li')].find(li => li.getAttribute('aria-label').split(': ')[1].split(', ').includes('stack.top.top'))?.dataset.face);
    await page.click(`#m3-faces li[data-face="${top}"]`);
    await page.selectOption('#m3-use', 'fixed');
    const box = await page.evaluate(() => { const i = document.getElementById('m3-use-temp'), b = document.getElementById('m3-use-temp-box');
      return {shown: !!b && !b.hidden && i.offsetParent !== null, label: [...(i?.labels || [])].map(l => l.textContent.trim()), value: i?.value, placeholder: i?.placeholder}; });
    const gate = () => page.evaluate(() => { const g = document.getElementById('m3-use-go'), d = g.getAttribute('aria-describedby');
      return {disabled: g.disabled, why: d ? document.getElementById(d)?.textContent : null}; });
    const empty = await gate();
    await page.fill('#m3-use-temp', '-5'); const bad = await gate();
    await page.fill('#m3-use-temp', '330'); const good = await gate();
    await page.click('#m3-use-go');
    await page.waitForSelector('[data-m3-node="heat:fixed:stack.top.top"]', {timeout: 30000}); await checked(page); await page.waitForTimeout(300);
    const after = await page.evaluate(() => ({note: document.querySelector('[data-m3-node="heat:fixed:stack.top.top"] .m3-note')?.textContent || '',
      messages: document.getElementById('mp-messages')?.textContent || '', selected: document.querySelector('#tree [aria-selected="true"]')?.dataset.m3Node,
      input: document.querySelector('[data-m3-heat="fixed"][data-m3-key="stack.top.top"]')?.value || ''}));
    await page.click('#undo-edit'); await checked(page); await page.waitForTimeout(200);
    const undone = await page.evaluate(() => !document.querySelector('[data-m3-node="heat:fixed:stack.top.top"]'));
    const rows = [
      box.shown && box.label.length === 1 && box.label[0] === 'Temperature (K)' && box.value === '' && box.placeholder === 'e.g. 330',
      empty.disabled && empty.why === 'Type a temperature in K to apply.' && bad.disabled && !!bad.why && bad.why !== empty.why && !good.disabled,
      after.note === 'stack.top.top · 330 K' && undone,
      after.messages.includes('Fixed temperature 330 K on stack.top.top.') && !after.messages.includes('300 K'),
      after.selected === 'heat:fixed:stack.top.top' && /^330( K)?$/.test(after.input),
    ];
    record('V1', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 5, box, empty, bad, good, after: {...after, messages: after.messages.slice(0, 200)}, undone});
    await ctx.close();
  }
  // ---- V10: a cylinder across a domain side: Studio's suggestion, the engine's words under Details ----
  if (want('V10')) {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card="via-slab-3d"]');
    await page.click('[data-model3d-card="via-slab-3d"]'); await checked(page);
    await page.click('[data-m3-node="feature:0"]');
    const sel = '[data-m3-field="features[0].cx"]';
    await page.fill(sel, '0.8'); await page.press(sel, 'Enter');
    await page.waitForSelector('[data-m3-refusal]', {timeout: 30000});
    await page.waitForFunction(() => document.getElementById('mp-messages').dataset.m3State === 'checked');
    const shown = await page.evaluate(() => ({text: document.querySelector('[data-m3-refusal] > p')?.textContent || '',
      details: document.querySelector('[data-m3-refusal] details')?.textContent || ''}));
    // X1: strict bounds; values the server confirmed are named after them
    const rows = [/^Cylinder via crosses the domain side x = 1 m\. Keep cx < 0\.7 m \(cx \+ r < 1 m\)(: cx = [\d.]+ m forms)?\. Or r < 0\.2 m(: r = [\d.]+ m forms)?\.$/.test(shown.text)
      && shown.details.includes('E-3D-COMBINATION') && shown.details.includes("cylinder 'via' crosses the side domain.x1")];
    record('V10', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 1, shown});
    await ctx.close();
  }
  // ---- V3: the estimate refusal gives two sizes with their estimates; the tree says "too fine" ----
  if (want('V3')) {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card="layer-stack-3d"]');
    await page.click('[data-model3d-card="layer-stack-3d"]'); await checked(page);
    await page.click('[data-m3-node="mesh"]'); await setField(page, 'mesh.element_size', '2');
    const doc = structuredClone(CARD); doc.mesh.element_size = '2 um';
    const mesh = (await serverCheck(page, doc)).mesh;
    const plain = await page.evaluate(async m => (await import('/workspace-assets/workspace-model3d.mjs')).meshRefusalText(m, 'um'), mesh);
    const shown = await page.evaluate(() => ({text: document.querySelector('[data-m3-mesh-refusal] > p')?.textContent || '',
      note: document.querySelector('[data-m3-node="mesh"] .m3-note')?.textContent || ''}));
    // the minute size, typed: the check's estimate there is the refusal's, at most 60 s
    const at = structuredClone(CARD); at.mesh.element_size = `${mesh.suggested_minute} um`;
    const there = (await serverCheck(page, at)).mesh;
    const rows = [
      shown.text === plain && shown.text.includes(`${mesh.suggested_size} µm`) && shown.text.includes(`${mesh.suggested_minute} µm`) && /estimated about \d+ min\)/.test(shown.text),
      there.ok === true && there.estimate.tetrahedra === mesh.minute_tetrahedra && there.estimate.seconds <= 60 && mesh.suggested_minute > mesh.suggested_size,
      shown.note === 'too fine',
    ];
    record('V3', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 3, shown,
      server: {suggested_size: mesh.suggested_size, suggested_tetrahedra: mesh.suggested_tetrahedra, suggested_seconds: mesh.suggested_seconds,
        suggested_minute: mesh.suggested_minute, minute_tetrahedra: mesh.minute_tetrahedra, minute_seconds: mesh.minute_seconds}, there: there.estimate});
    await ctx.close();
  }
  // ---- V8: the cut drawn in its colour map (not near white); its legend beside the view ----
  if (want('V8')) {
    const {page, seen, ctx} = await open(browser);
    await page.waitForSelector('[data-model3d-card]');
    const doc = structuredClone(CARD); doc.physics.heat.prescribed_temperature = {z0: '300 K', z1: '300 K'};
    await openFile(page, 'v8.json', session(doc)); await checked(page);
    await page.click('#m3-run'); await completed(page, 1); await page.waitForTimeout(300);
    await page.screenshot({path: join(out, 'v8-surface.png')});
    await page.selectOption('#m3-section-axis', 'z'); await page.fill('#m3-section-at', '505'); await page.click('#m3-section-go');
    await page.waitForSelector('#m3-cut-bar', {timeout: 30000});
    await page.click('[data-m3-view="+z"]'); await page.focus('#m3-result-canvas');
    for (let i = 0; i < 6; i++) await page.keyboard.press('+');                 // zoom in: the cut fills the view
    await page.waitForTimeout(400);
    await page.screenshot({path: join(out, 'v8-cut.png')});
    const px = await page.evaluate(async () => {
      const M = await import('/workspace-assets/workspace-model3d.mjs');
      const c = document.getElementById('m3-result-canvas'), w = c.width, h = c.height;
      const t = document.createElement('canvas'); t.width = w; t.height = h; const g = t.getContext('2d'); g.drawImage(c, 0, 0);
      const d = g.getImageData(0, 0, w, h).data, bg = [0xfb, 0xfc, 0xfd], pts = [];
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
        const i = 4 * (y * w + x), p = [d[i], d[i + 1], d[i + 2]];
        if (Math.max(...p.map((v, k) => Math.abs(v - bg[k]))) > 6) pts.push(p); }
      const sat = p => { const mx = Math.max(...p), mn = Math.min(...p); return mx ? (mx - mn) / mx : 0; };
      const ends = [M.temperatureColor(0, 0, 1), M.temperatureColor(1, 0, 1)].map(c => c.map(v => Math.round(v * 255)));
      const dist = (p, e) => Math.max(...p.map((v, k) => Math.abs(v - e[k])));
      const near = e => pts.reduce((m, p) => Math.min(m, dist(p, e)), 255);
      const best = e => pts.reduce((b, p) => dist(p, e) < dist(b, e) ? p : b, pts[0]);
      const bar = document.getElementById('m3-cut-bar').getBoundingClientRect(), cv = c.getBoundingClientRect();
      return {bestHot: best(ends[1]), bestCold: best(ends[0]), n: pts.length, meanSat: pts.reduce((s, p) => s + sat(p), 0) / Math.max(1, pts.length), ends, nearCold: near(ends[0]), nearHot: near(ends[1]),
        legendInView: bar.top < innerHeight && bar.bottom <= innerHeight, legendBeside: bar.top < cv.bottom && bar.left >= cv.right - 1 || (bar.top >= cv.top && bar.top <= cv.bottom + 40),
        bar: [bar.left, bar.top, bar.right, bar.bottom].map(Math.round), canvas: [cv.left, cv.top, cv.right, cv.bottom].map(Math.round), inner: innerHeight}; });
    const rows = [px.n > 100 && px.nearCold <= 12 && px.nearHot <= 12, px.meanSat >= 0.25, px.legendInView];
    record('V8', rows.every(Boolean) && !seen.pageErrors.length, {passed: rows.filter(Boolean).length, of: 3, ...px});
    await ctx.close();
  }
  // ---- V2: another 3D card opens in a new tab at one click; Replace names what is dropped; Undo ----
  if (want('V2')) {
    const {page, seen, ctx} = await open(browser);
    await page.waitForFunction(() => /^Connected/.test(document.getElementById('connection-status').textContent) && !!document.querySelector('[data-template=optical]'));
    // the project: an optical run (a browser recovery record), then card 1 with one run
    await page.click('[data-template=optical]'); await page.waitForFunction(() => !document.getElementById('run-optical').disabled, null, {timeout: 30000});
    await page.click('#run-optical');
    await page.waitForFunction(() => /complete/i.test(document.getElementById('job-message').textContent), null, {timeout: 180000});
    await page.waitForFunction(() => /^Browser recovery updated/.test(document.getElementById('notebook-recovery-detail').textContent), null, {timeout: 20000});
    await page.click('[data-page="Applications"]'); await page.click('[data-model3d-card="layer-stack-3d"]'); await checked(page);
    await page.click('#m3-run'); await completed(page, 1); await page.waitForTimeout(300);
    const session = pg => pg.evaluate(() => new Promise((resolve, reject) => { const o = indexedDB.open('openphysics-studio-notebook', 1);
      o.onsuccess = () => { const r = o.result.transaction('snapshots', 'readonly').objectStore('snapshots').get('latest');
        r.onsuccess = () => { o.result.close(); resolve(r.result?.session ?? null); }; r.onerror = () => reject(r.error); }; o.onerror = () => reject(o.error); }));
    const recBefore = await session(page);
    // (a) card 2 reads "Open in a new tab" with the reason, and one click opens it
    await page.click('[data-page="Applications"]');
    const cardA = await page.evaluate(() => { const b = document.querySelector('[data-model3d-card="via-slab-3d"]');
      return {action: b?.querySelector('.card-action')?.textContent || '', why: b?.querySelector('.card-why')?.textContent || '', status: document.getElementById('file-status')?.textContent || ''}; });
    const popup = ctx.waitForEvent('page', {timeout: 30000});
    await page.click('[data-model3d-card="via-slab-3d"]');
    const tab = await popup; await tab.waitForLoadState();
    await tab.waitForFunction(() => document.getElementById('mp-messages')?.dataset.m3State === 'checked', null, {timeout: 30000});
    const fresh = await tab.evaluate(() => ({url: location.pathname + location.search, title: document.querySelector('.m3-head h2')?.textContent || ''}));
    const statusAfter = await page.evaluate(() => document.getElementById('file-status')?.textContent || '');
    // the reverse: in the new tab (card 2 held), card 1 reads the same with card 2's title
    await tab.click('[data-page="Applications"]');
    const reverse = await tab.evaluate(() => { const b = document.querySelector('[data-model3d-card="layer-stack-3d"]');
      return {action: b?.querySelector('.card-action')?.textContent || '', why: b?.querySelector('.card-why')?.textContent || ''}; });
    await tab.close();
    const recAfterTab = await session(page);
    const rowsA = [
      cardA.action === 'Open in a new tab' && cardA.why === 'This project holds Via in a layer stack (3D heat); a project holds one 3D model.',
      fresh.url === '/workspace?card=via-slab-3d&fresh=1' && fresh.title === 'Copper via through a slab (3D heat)' && statusAfter === cardA.status,
      recBefore !== null && recAfterTab === recBefore && await page.evaluate(() => document.querySelectorAll('[data-model3d-card]').length) === 2,
      reverse.action === 'Open in a new tab' && reverse.why === 'This project holds Copper via through a slab (3D heat); a project holds one 3D model.',
    ];
    record('V2a', rowsA.every(Boolean) && !seen.pageErrors.length, {passed: rowsA.filter(Boolean).length, of: 4, cardA, fresh, reverse, sameRecord: recAfterTab === recBefore});
    // (b) Replace: the question, Cancel, File › Save, Replace, Undo
    const dialogText = () => page.evaluate(() => [...document.querySelectorAll('#m3-replace-dialog p')].map(p => p.textContent));
    const expected = (saved, file) => page.evaluate(async ([s, f]) => (await import('/workspace-assets/workspace-model3d.mjs'))
      .replaceLines({from: 'Via in a layer stack (3D heat)', to: 'Copper via through a slab (3D heat)', runs: 1, saved: s, file: f}), [saved, file]);
    await page.click('[data-m3-replace="via-slab-3d"]'); await page.waitForSelector('#m3-replace-dialog[open]');
    const unsaved = await dialogText();
    await page.click('#m3-replace-dialog [data-act="cancel"]'); await page.waitForTimeout(200);
    const afterCancel = await page.evaluate(() => ({dialog: !!document.getElementById('m3-replace-dialog'), card1: document.querySelector('[data-model3d-card="layer-stack-3d"] .card-action')?.textContent}));
    await page.click('[data-m3-replace="via-slab-3d"]'); await page.waitForSelector('#m3-replace-dialog[open]');
    const file1 = await download(page, () => page.click('#m3-replace-dialog [data-act="save"]'));
    await page.waitForTimeout(300);
    const savedName = await page.evaluate(() => document.querySelector('#m3-replace-dialog p:nth-of-type(2)')?.textContent.match(/saved in (.+) with no changes since\./)?.[1] || '');
    const saved = await dialogText();
    const p1 = JSON.parse(file1), entry = (p, kind) => p.models.find(m => m.kind === kind);
    await page.click('#m3-replace-dialog [data-act="replace"]');
    await page.waitForFunction(() => document.querySelector('.m3-head h2')?.textContent === 'Copper via through a slab (3D heat)', null, {timeout: 30000});
    await checked(page);
    const recAfterReplace = await session(page);
    await page.click('#file-status button[data-m3-undo-replace]');
    await page.waitForFunction(() => document.querySelector('.m3-head h2')?.textContent === 'Via in a layer stack (3D heat)', null, {timeout: 30000});
    await checked(page);
    // after Undo the project equals the saved one (the footer says so, and Save has nothing to write): Save As writes it
    const footer = await page.evaluate(() => document.getElementById('autosave-status')?.textContent || '');
    const file2 = await download(page, async () => { await page.click('#file-menu-button'); await page.click('#menu-save-as'); }), p2 = JSON.parse(file2);
    const recAfterUndo = await session(page);
    const rowsB = [
      JSON.stringify(unsaved) === JSON.stringify(await expected('none')) && savedName !== '' && JSON.stringify(saved) === JSON.stringify(await expected('saved', savedName)),
      !afterCancel.dialog && afterCancel.card1 === 'Return to the 3D model',
      recAfterReplace === recBefore,
      entry(p1, 'model3d')?.digest === entry(p2, 'model3d')?.digest && entry(p1, 'workspace')?.digest === entry(p2, 'workspace')?.digest
        && p1.models.length === p2.models.length && recAfterUndo === recBefore && footer === '3D model saved in the project file',
      entry(p1, 'model3d')?.card === 'layer-stack-3d' && !!entry(p1, 'workspace'),
    ];
    record('V2b', rowsB.every(Boolean) && !seen.pageErrors.length, {passed: rowsB.filter(Boolean).length, of: 5, unsaved, saved, savedName, afterCancel,
      digests: {m3: [entry(p1, 'model3d')?.digest, entry(p2, 'model3d')?.digest], ws: [entry(p1, 'workspace')?.digest, entry(p2, 'workspace')?.digest]},
      footer, record: {afterTab: recAfterTab === recBefore, afterReplace: recAfterReplace === recBefore, afterUndo: recAfterUndo === recBefore}});
    await ctx.close();
  }
} finally {
  await writeFile(join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}
if (failed) process.exit(1);
