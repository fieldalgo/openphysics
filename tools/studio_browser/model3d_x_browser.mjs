// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Studio 3D fixes X1–X7 (agent round 3D-3) in a real browser, against a local Studio on this branch:
//   node tools/studio_browser/model3d_x_browser.mjs http://127.0.0.1:8765 out-dir [X1,X2,...]
// Pre-registered checks (thresholds fixed before measuring, accepted by the coordinator):
//  X1  card 2: a cylinder across each domain side (cx 0.8, −0.8; cy 0.8, −0.8): each value Messages names
//      as forming ("cx = 0.69 m forms") is fed back to the server's check, which answers ok with a mesh
//      estimate; the r value of the x1 case too; and cx = 0.7 (touching x1): plain words ("touches the
//      domain side x = 1 m along a line") and a value that forms: 6/6.
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
} finally {
  await writeFile(join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}
if (failed) process.exit(1);
