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
} finally {
  await writeFile(join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}
if (failed) process.exit(1);
