// Real-browser checks of the experimental 3D view on the geometry lab page (W3, W12, W13).
// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
//
// A local check, not wired into CI: it needs Playwright with a Chromium it can launch
// (not a repository dependency). From the repository root, with a Studio server running:
//   python -m simcase.studio --no-browser --port 8765 &
//   node tools/studio_browser/model3d_view_browser.mjs http://127.0.0.1:8765 out-dir
// Pre-registered checks (thresholds fixed before measuring):
//  W3  picking at the 40 points of tests/simcase/studio_model3d_pick_points.json (written by an
//      independent ray cast against the exact complex before the view existed), 1440 x 900
//      window, isometric camera, card document: face id and first name, 40/40;
//  W12 the first view at 1440 x 900 and 390 x 844: no console error, no CSP violation, the canvas
//      visible and not empty, no horizontal scroll at 390, the faces list reachable by Tab;
//      screenshots stored;
//  W13 keyboard only: rotate, choose an axis view, select via.z1 from the faces list, with no
//      pointer event.
// Also (not pre-registered): a section outline is drawn, and hiding regions exposes the via.
// It writes report.json and screenshots to out-dir and exits non-zero if a check fails.
import {createRequire} from 'node:module';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';

const require = createRequire(import.meta.url);
const {chromium} = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:8765';
const out = process.argv[3] || 'model3d-view-browser';
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
await mkdir(out, {recursive: true});
const expected = JSON.parse(await readFile(join(ROOT, 'tests', 'simcase', 'studio_model3d_pick_points.json'), 'utf8'));
const origin = new URL(base).origin;
const report = {base, checks: {}, stages: []};

async function open(browser, viewport) {
  const page = await browser.newPage({viewport});
  const seen = {console: [], pageErrors: [], foreign: []};
  page.on('console', m => { if (m.type() === 'error') seen.console.push(m.text()); });
  page.on('pageerror', e => seen.pageErrors.push(String(e)));
  page.on('request', r => { if (/^(https?|wss?):/.test(r.url()) && new URL(r.url()).origin !== origin) seen.foreign.push(r.url()); });
  await page.addInitScript(() => {
    window.__csp = [];
    document.addEventListener('securitypolicyviolation', e => window.__csp.push(e.violatedDirective + ' ' + e.blockedURI));
    window.__pointer = 0;
    for (const type of ['pointerdown', 'pointerup', 'mousedown', 'mouseup', 'click', 'wheel', 'touchstart'])
      document.addEventListener(type, e => { if (e.isTrusted && (type !== 'click' || e.detail > 0)) window.__pointer++; }, true);
  });
  const response = await page.goto(base + '/geometry-lab');
  assert.equal(response.status(), 200);
  return {page, seen};
}

const shown = page => page.waitForFunction(() => /^Shown /.test(document.querySelector('#status').textContent), null, {timeout: 30000});

async function canvasState(page) {
  return page.evaluate(() => {
    const c = document.querySelector('#canvas3d'), r = c.getBoundingClientRect();
    const probe = document.createElement('canvas');
    probe.width = c.width; probe.height = c.height;
    const g = probe.getContext('2d'); g.drawImage(c, 0, 0);
    const data = g.getImageData(0, 0, probe.width, probe.height).data;
    let drawn = 0;
    for (let i = 0; i < data.length; i += 4)
      if (Math.abs(data[i] - 0xfb) + Math.abs(data[i + 1] - 0xfc) + Math.abs(data[i + 2] - 0xfd) > 24) drawn++;
    const style = getComputedStyle(c);
    return {x: r.x, y: r.y, width: r.width, height: r.height, visible: style.display !== 'none' && style.visibility !== 'hidden' && r.width > 0 && r.height > 0,
      drawnPixels: drawn, pixels: data.length / 4, scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth};
  });
}

const selected = page => page.evaluate(() => {
  const face = document.querySelector('#names').dataset.face;
  const first = document.querySelector('#face-names li code');
  return {face: face === '' || face === undefined ? null : Number(face), first: first ? first.textContent : null};
});

const browser = await chromium.launch();
let failed = false;
const record = (name, ok, detail) => { report.checks[name] = {ok, ...detail}; if (!ok) failed = true; };
try {
  // ---- W12 and W3 at 1440 x 900 ----------------------------------------------------------
  for (const viewport of [{width: 1440, height: 900}, {width: 390, height: 844}]) {
    const {page, seen} = await open(browser, viewport);
    await page.selectOption('#starter', 'model3d_via_stack');
    await shown(page);
    const state = await canvasState(page);
    await page.screenshot({path: join(out, `w12-first-view-${viewport.width}x${viewport.height}.png`), fullPage: true});
    // the faces list by Tab from the top of the page
    await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });
    let tabs = 0, reached = false;
    for (; tabs < 80 && !reached; tabs++) {
      await page.keyboard.press('Tab');
      reached = await page.evaluate(() => !!document.activeElement?.closest('#faces'));
    }
    const csp = await page.evaluate(() => window.__csp);
    const result = {viewport, canvas: state, tabsToFacesList: reached ? tabs : null, console: seen.console,
      pageErrors: seen.pageErrors, csp, foreign: seen.foreign};
    const ok = !seen.console.length && !seen.pageErrors.length && !csp.length && !seen.foreign.length && state.visible
      && state.drawnPixels > 0.02 * state.pixels && reached && (viewport.width !== 390 || state.scrollWidth <= state.innerWidth);
    record(`W12 ${viewport.width}x${viewport.height}`, ok, result);

    if (viewport.width === 1440) {
      assert.deepEqual([state.width, state.height], [expected.canvas.width, expected.canvas.height],
        'the canvas size the W3 oracle assumed');
      const misses = [];
      for (const p of expected.points) {
        await page.mouse.click(state.x + p.px, state.y + p.py);
        const got = await selected(page);
        if (got.face !== p.face || got.first !== p.first_name) misses.push({...p, got});
      }
      await page.screenshot({path: join(out, 'w3-after-picks.png')});
      record('W3', misses.length === 0, {points: expected.points.length, matched: expected.points.length - misses.length, misses,
        excluded: expected.excluded.length});
      // section and hidden regions (smoke)
      await page.selectOption('#section-axis', 'x');
      await page.waitForFunction(() => /^Section x = /.test(document.querySelector('#status').textContent));
      const section = await page.textContent('#status');
      await page.screenshot({path: join(out, 'section-x.png')});
      await page.selectOption('#section-axis', '');
      for (const name of ['silicon', 'silicon_dioxide']) await page.uncheck(`input[aria-label="show region ${name}"]`);
      await page.mouse.click(state.x + state.width / 2, state.y + state.height / 2);
      const via = {...await selected(page), names: await page.evaluate(() => [...document.querySelectorAll('#face-names code')].map(e => e.textContent))};
      await page.screenshot({path: join(out, 'via-only.png')});
      record('section and hide (smoke)', /cuts \d+ faces/.test(section) && via.face !== null && via.names.some(n => n.startsWith('via.')),
        {section, viaPick: via});
    }
    await page.close();
  }

  // ---- W13: keyboard only ------------------------------------------------------------------
  {
    const {page, seen} = await open(browser, {width: 1440, height: 900});
    const focusBy = async (test, limit = 120) => {
      for (let i = 0; i < limit; i++) {
        await page.keyboard.press('Tab');
        if (await page.evaluate(test)) return true;
      }
      return false;
    };
    const steps = {};
    steps.starterFocused = await focusBy(() => document.activeElement?.id === 'starter');
    await page.keyboard.type('Via');                                   // type-ahead in the closed select
    await page.evaluate(() => { const s = document.querySelector('#starter'); if (s.value !== 'model3d_via_stack') throw new Error('starter not chosen: ' + s.value); });
    await shown(page);
    steps.canvasFocused = await focusBy(() => document.activeElement?.id === 'canvas3d');
    await page.keyboard.press('ArrowLeft');
    steps.rotated = await page.evaluate(() => document.querySelector('#canvas3d').dataset.camera) === 'rotate';
    await page.keyboard.press('5');
    steps.axisView = await page.evaluate(() => document.querySelector('#canvas3d').dataset.camera) === '+z';
    await page.screenshot({path: join(out, 'w13-axis-view.png')});
    steps.viaFocused = await focusBy(() => !!document.activeElement?.closest('#faces')
      && document.activeElement.getAttribute('aria-label').split(': ')[1].split(', ').includes('via.z1'));
    await page.keyboard.press('Enter');
    const got = await selected(page);
    steps.viaSelected = got.face !== null && (await page.evaluate(() => [...document.querySelectorAll('#face-names code')].map(e => e.textContent))).includes('via.z1');
    steps.pointerEvents = await page.evaluate(() => window.__pointer);
    await page.screenshot({path: join(out, 'w13-via-z1.png')});
    const ok = steps.starterFocused && steps.canvasFocused && steps.rotated && steps.axisView && steps.viaFocused && steps.viaSelected
      && steps.pointerEvents === 0 && !seen.console.length && !seen.pageErrors.length;
    record('W13', ok, {steps, selected: got, console: seen.console, pageErrors: seen.pageErrors});
    await page.close();
  }
} finally {
  await writeFile(join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}
for (const [name, c] of Object.entries(report.checks)) console.log(`${c.ok ? 'PASS' : 'FAIL'} ${name}`);
if (failed) process.exit(1);
