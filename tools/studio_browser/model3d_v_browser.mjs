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
} finally {
  await writeFile(join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}
if (failed) process.exit(1);
