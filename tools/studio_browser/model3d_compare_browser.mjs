// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Studio 3D Compare (C3) in a real browser, against a local Studio server on this branch:
//   node tools/studio_browser/model3d_compare_browser.mjs http://127.0.0.1:8765 out-dir
// Card 2 (Copper via through a slab), three runs: Run 1 as the card (300 K / 301 K); Run 2 with every
// fixed temperature raised by 10 K (310 K / 311 K, the same mesh); Run 3 as Run 2 with element size
// 0.12 m (another mesh). Pre-registered checks (thresholds fixed before measuring):
//  C3-1  Runs 1 and 2: every cell of the values table equals compareRows of the two runs' /values
//        answers and documents (A, B and B − A): 100%.
//  C3-2  the inputs that differ: Runs 1 → 2 "Fixed temperature z0: 300 K → 310 K", "Fixed temperature
//        z1: 301 K → 311 K"; Runs 2 → 3 "Mesh element size: 0.1 m → 0.12 m"; Run 1 → 1 "Same inputs.".
//  C3-3  the mesh-differs notice: none for Runs 1 and 2 (a ΔT map shown), the notice for Runs 2 and 3
//        (no ΔT map): 2/2.
//  C3-4  Runs 1 and 2: the ΔT legend equals deltaLegend(surfaceDelta(...)) of the two /surface answers.
//  C3-5  Runs 1 and 2: the legend reads "ΔT (B − A): 10–10 K · largest |ΔT| 10 K" (superposition; the
//        float64 threshold, 1e-8 K, is test_studio_model3d_compare_superposition.py's).
//  C3-6  keyboard only on Compare (the pickers by arrow keys, the tab by Enter): 0 pointer events; no
//        console error or CSP violation; no horizontal scroll at 390 × 844 or 1440 × 900; one run:
//        "Compare needs two runs of this 3D model.".
// It writes report.json and screenshots to out-dir and exits non-zero if a check fails.
import {createRequire} from 'node:module';
import {mkdir, writeFile} from 'node:fs/promises';
import {join} from 'node:path';

const require = createRequire(import.meta.url);
const {chromium} = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:8765';
const out = process.argv[3] || 'model3d-compare-browser';
await mkdir(out, {recursive: true});
const origin = new URL(base).origin;
const report = {base, checks: {}};
let failed = false;
const record = (name, ok, detail) => { report.checks[name] = {ok, ...detail}; if (!ok) failed = true; console.log(`${ok ? 'PASS' : 'FAIL'} ${name}`); };

async function open(browser, viewport) {
  const page = await browser.newPage({viewport});
  const seen = {console: [], pageErrors: [], foreign: []};
  page.on('console', m => { if (m.type() === 'error') seen.console.push(m.text()); });
  page.on('pageerror', e => seen.pageErrors.push(String(e)));
  page.on('request', r => { if (/^(https?|wss?):/.test(r.url()) && new URL(r.url()).origin !== origin) seen.foreign.push(r.url()); });
  await page.addInitScript(() => {
    window.__csp = []; document.addEventListener('securitypolicyviolation', e => window.__csp.push(e.violatedDirective + ' ' + e.blockedURI));
    window.__pointer = 0;
    for (const type of ['pointerdown', 'pointerup', 'mousedown', 'mouseup', 'click', 'wheel', 'touchstart'])
      document.addEventListener(type, e => { if (e.isTrusted && (type !== 'click' || e.detail > 0)) window.__pointer++; }, true);
  });
  await page.goto(base + '/workspace');
  await page.waitForSelector('[data-model3d-card="via-slab-3d"]');
  return {page, seen};
}
const checked = page => page.waitForFunction(() => { const box = document.getElementById('mp-messages');
  return box && !box.hidden && box.dataset.m3State === 'checked' && document.querySelector('#m3-faces li'); }, null, {timeout: 30000});
const completed = (page, n) => page.waitForFunction(n => (document.getElementById('mp-messages')?.textContent || '').includes(`Run ${n} complete`)
  && document.getElementById('m3-result-canvas'), n, {timeout: 180000});
async function setInput(page, selector, value) {
  await page.fill(selector, value); await page.press(selector, 'Enter');
  await page.waitForTimeout(150); await checked(page);
}
async function run(page, n) { await page.click('#m3-run'); await completed(page, n); await page.waitForTimeout(300); }
const toModel = async page => { await page.click('[data-page="Model"]'); await checked(page); };
const toCompare = async page => { await page.click('[data-page="Compare"]'); await page.waitForSelector('#m3-compare-values, #m3-compare-none'); };
async function pick(page, a, b) {
  await page.selectOption('#m3-compare-a', String(a)); await page.waitForTimeout(100);
  await page.selectOption('#m3-compare-b', String(b)); await page.waitForTimeout(300);
}
const shownPage = page => page.evaluate(() => ({
  heads: [...document.querySelectorAll('#m3-compare-values thead th')].map(t => t.textContent),
  rows: [...document.querySelectorAll('#m3-compare-values tbody tr')].map(r => [r.querySelector('th').textContent, ...[...r.querySelectorAll('td')].map(t => t.textContent)]),
  inputs: [...document.querySelectorAll('#m3-compare-inputs li')].map(l => l.textContent).concat(document.querySelector('p#m3-compare-inputs')?.textContent ?? []),
  notice: document.getElementById('m3-compare-mesh')?.textContent ?? null,
  canvas: !!document.getElementById('m3-compare-canvas'),
  legend: document.querySelector('#m3-compare-legend .m3-cb-title')?.textContent ?? null}));
// the expected page, from the server's answers for the two live runs (ids read from the page's export links)
const expected = (page, ids) => page.evaluate(async ids => {
  const C = await import('/workspace-assets/workspace-model3d-compare.mjs'), M = await import('/model3d-assets/model3d-model.mjs');
  const get = async (id, what) => (await fetch(`/api/model3d/runs/${id}/${what}`)).json();
  const rec = async id => { const r = await get(id, 'record?maps=kept'); return {run: r.run ?? id, values: await get(id, 'values'), document: r.document, surface: await get(id, 'surface')}; };
  const [A, B] = [await rec(ids[0]), await rec(ids[1])];
  const d = C.sameMesh(A.values, B.values) ? C.surfaceDelta(M.decode(A.surface.temperature, Float32Array), M.decode(B.surface.temperature, Float32Array)) : null;
  return {rows: C.compareRows(A, B, B.surface.unit), inputs: C.inputChanges(A.document, B.document), notice: C.meshNotice(A, B), legend: d ? C.deltaLegend(d) : null};
}, ids);
const liveIds = page => page.evaluate(() => window.__m3ids);

const browser = await chromium.launch();
try {
  const {page, seen} = await open(browser, {width: 1440, height: 900});
  await page.click('[data-model3d-card="via-slab-3d"]'); await checked(page);
  // the run ids, as each run completes (the run started by #m3-run answers {run})
  await page.evaluate(() => { window.__m3ids = []; const f = window.fetch; window.fetch = async (...a) => { const r = await f(...a);
    if (String(a[0]).endsWith('/api/model3d/run') && (a[1]?.method || 'GET') === 'POST') r.clone().json().then(j => j.run && window.__m3ids.push(j.run)).catch(() => {});
    return r; }; });
  await run(page, 1);
  await page.click('#tree [data-m3-node="heat:fixed:z0"]'); await setInput(page, '[data-m3-heat="fixed"][data-m3-key="z0"]', '310');
  await page.click('#tree [data-m3-node="heat:fixed:z1"]'); await setInput(page, '[data-m3-heat="fixed"][data-m3-key="z1"]', '311');
  await run(page, 2);
  await page.click('#tree [data-m3-node="mesh"]'); await setInput(page, '[data-m3-field="mesh.element_size"]', '0.12');
  await run(page, 3);
  const ids = await liveIds(page);
  await toCompare(page);

  // C3-1, C3-3 (same mesh), C3-4, C3-5: Runs 1 and 2
  await pick(page, 0, 1);
  const p12 = await shownPage(page), e12 = await expected(page, [ids[0], ids[1]]);
  await page.screenshot({path: join(out, 'compare-1-2.png')});
  const cells = p12.rows.flat().length, same = p12.rows.flat().filter((c, i) => c === e12.rows.flat()[i]).length;
  record('C3-1', cells > 0 && JSON.stringify(p12.rows) === JSON.stringify(e12.rows) && p12.heads.join('|') === 'Quantity|Run 1 (A)|Run 2 (B)|B − A',
    {cells, same, heads: p12.heads, rows: p12.rows});
  // C3-2: three pairs
  await pick(page, 1, 2); const p23 = await shownPage(page), e23 = await expected(page, [ids[1], ids[2]]);
  await page.screenshot({path: join(out, 'compare-2-3.png')});
  await pick(page, 0, 0); const p11 = await shownPage(page);
  const inputsOk = JSON.stringify(p12.inputs) === JSON.stringify(['Fixed temperature z0: 300 K → 310 K', 'Fixed temperature z1: 301 K → 311 K'])
    && JSON.stringify(p23.inputs) === JSON.stringify(['Mesh element size: 0.1 m → 0.12 m']) && JSON.stringify(p11.inputs) === JSON.stringify(['Same inputs.'])
    && JSON.stringify(p12.inputs) === JSON.stringify(e12.inputs) && JSON.stringify(p23.inputs) === JSON.stringify(e23.inputs);
  record('C3-2', inputsOk, {p12: p12.inputs, p23: p23.inputs, p11: p11.inputs});
  record('C3-3', p12.notice === null && p12.canvas && e12.notice === null && p23.notice !== null && p23.notice === e23.notice && !p23.canvas,
    {same: {notice: p12.notice, canvas: p12.canvas}, different: {notice: p23.notice, canvas: p23.canvas}});
  record('C3-4', p12.legend !== null && p12.legend === e12.legend, {shown: p12.legend, direct: e12.legend});
  record('C3-5', p12.legend === 'ΔT (B − A): 10–10 K · largest |ΔT| 10 K', {legend: p12.legend});

  // C3-6: keyboard only on Compare; the pickers by arrow keys; widths
  await page.evaluate(() => { window.__pointer = 0; });
  await page.focus('#page-tab-Model'); await page.keyboard.press('Enter'); await checked(page);
  await page.focus('#page-tab-Compare'); await page.keyboard.press('Enter'); await page.waitForSelector('#m3-compare-values');
  await page.focus('#m3-compare-a'); await page.keyboard.press('ArrowDown'); await page.waitForTimeout(300);
  await page.focus('#m3-compare-b'); await page.keyboard.press('ArrowDown'); await page.waitForTimeout(300);
  await page.keyboard.press('ArrowDown'); await page.waitForTimeout(300);
  const keyed = await page.evaluate(() => ({heads: [...document.querySelectorAll('#m3-compare-values thead th')].map(t => t.textContent),
    focus: document.activeElement?.id, pointer: window.__pointer, csp: window.__csp,
    scroll: document.documentElement.scrollWidth - window.innerWidth}));
  await page.setViewportSize({width: 390, height: 844}); await page.waitForTimeout(400);
  const narrow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  await page.screenshot({path: join(out, 'compare-390.png'), fullPage: true});
  // one run: the page says Compare needs two
  const one = await open(browser, {width: 1440, height: 900});
  await one.page.click('[data-model3d-card="via-slab-3d"]'); await checked(one.page); await run(one.page, 1);
  await toCompare(one.page);
  const needs = await one.page.evaluate(() => document.getElementById('m3-compare-none')?.textContent ?? '');
  await one.page.close();
  record('C3-6', keyed.pointer === 0 && keyed.heads.join('|') === 'Quantity|Run 2 (A)|Run 3 (B)|B − A' && keyed.focus === 'm3-compare-b'
    && !seen.console.length && !seen.pageErrors.length && !keyed.csp.length && !seen.foreign.length && keyed.scroll <= 0 && narrow <= 0
    && needs === 'Compare needs two runs of this 3D model.' && !one.seen.console.length && !one.seen.pageErrors.length,
    {keyed, narrow, needs, console: seen.console, pageErrors: seen.pageErrors});
  await page.close();
} finally {
  await writeFile(join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}
if (failed) process.exit(1);
