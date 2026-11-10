// Real-browser check of the experimental geometry lab (/geometry-lab).
// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
//
// A local check, not wired into CI: it needs Playwright with a Chromium it can launch
// (not a repository dependency). From the repository root, with a Studio server running:
//   python -m simcase.studio --no-browser --port 8765 &
//   node tools/studio_browser/geometry_lab_browser.mjs http://127.0.0.1:8765 out-dir
// It loads both starters, edits a parameter with the slider and the text field, checks the
// lists against the server's answer, provokes a refusal, saves the document and checks that
// the page logged no console error and no Content-Security-Policy violation.
import {createRequire} from 'node:module';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import assert from 'node:assert/strict';

const require = createRequire(import.meta.url);
const {chromium} = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:8765';
const out = process.argv[3] || 'geometry-lab-browser';
await mkdir(out, {recursive: true});

const report = {base, console: [], pageErrors: [], cspViolations: [], stages: []};
const browser = await chromium.launch();
try {
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}, acceptDownloads: true});
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') report.console.push(`${m.type()}: ${m.text()}`); });
  page.on('pageerror', e => report.pageErrors.push(String(e)));
  await page.addInitScript(() => document.addEventListener('securitypolicyviolation',
    e => (window.__csp = window.__csp || []).push(e.violatedDirective + ' ' + e.blockedURI)));
  const response = await page.goto(base + '/geometry-lab');
  const policy = response.headers()['content-security-policy'] || '';
  assert.match(policy, /script-src 'self'/);

  const api = async doc => page.evaluate(async d => {
    const r = await fetch('/api/geometry-lab/evaluate', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({doc: d})});
    return {status: r.status, body: await r.json()};
  }, doc);
  const lists = () => page.evaluate(() => Object.fromEntries(['regions', 'selections', 'tags'].map(id =>
    [id, [...document.querySelectorAll('#' + id + ' li code')].map(e => e.textContent)])));
  const docOf = () => page.evaluate(async () => (await import('/geometry-lab-assets/geometry-lab-starters.mjs')).STARTERS);
  const settled = async () => { await page.waitForFunction(() => !/Evaluating/.test(document.querySelector('#status').textContent)); };

  for (const starter of ['geometry_v1_soi_strip', 'geometry_v1_imprint_rib']) {
    await page.selectOption('#starter', starter);
    await settled();
    const doc = (await docOf())[starter];
    const answer = await api(doc);
    assert.equal(answer.status, 200); assert.equal(answer.body.ok, true);
    const shown = await lists();
    assert.deepEqual(shown.regions, answer.body.regions.map(r => r.name));
    assert.deepEqual(shown.selections, answer.body.selections.length ? answer.body.selections.map(s => s.name) : []);
    assert.deepEqual(shown.tags, answer.body.tags.map(t => t.tag));
    assert.equal(await page.textContent('#summary'), answer.body.summary);
    const cells = await page.locator('#view path.cell').count(), curves = await page.locator('#view path.curve').count();
    assert.equal(cells, answer.body.cells.length); assert.equal(curves, answer.body.curves.length);
    await page.screenshot({path: join(out, starter + '.png')});
    report.stages.push({starter, regions: shown.regions, selections: shown.selections, cells, curves});
  }

  // The imprinted rib is loaded: move w with the slider to its upper end, then type 0.4.
  const slider = page.locator('input[aria-label="w slider"]');
  await slider.focus(); await page.keyboard.press('End'); await settled();
  assert.equal(await page.inputValue('#param-w'), '0.9 um');
  const wide = await page.textContent('#summary');
  await page.fill('#param-w', '0.4'); await page.press('#param-w', 'Enter'); await settled();
  const narrow = await page.textContent('#summary');
  assert.notEqual(wide, narrow);
  const edited = structuredClone((await docOf()).geometry_v1_imprint_rib); edited.geometry.parameters.w.value = '0.4 um';
  assert.equal(narrow, (await api(edited)).body.summary);
  report.stages.push({edit: 'w = 0.9 by slider, then 0.4 typed', summaryChanged: true});

  // A highlighted selection follows the current answer after an edit, not the old indices.
  await page.click('#selections li[data-key="selection:rib_walls"]');
  const lit = () => page.evaluate(() => [...document.querySelectorAll('#view path.curve.lit')].map(p => Number(p.dataset.curve)));
  const wallsNow = async () => (await api(edited)).body.selections.find(x => x.name === 'rib_walls').entries;
  assert.deepEqual(await lit(), await wallsNow());
  edited.geometry.parameters.slab.value = '0.15 um';
  await page.fill('#param-slab', '0.15'); await page.press('#param-slab', 'Enter'); await settled();
  assert.deepEqual(await lit(), await wallsNow());
  report.stages.push({highlightFollowsEdit: await lit()});

  // A local refusal (overflow) is not hidden by an answer already on its way, and the field
  // goes back to the value the document holds.
  await page.fill('#param-slab', '0.12'); await page.press('#param-slab', 'Enter');
  await page.fill('#param-slab', '1e999'); await page.press('#param-slab', 'Enter');
  await page.waitForTimeout(800);
  assert.ok(await page.isVisible('#refusal'));
  assert.match(await page.textContent('#refusal'), /too large/);
  assert.equal(await page.inputValue('#param-slab'), '0.12 um');
  edited.geometry.parameters.slab.value = '0.12 um';
  report.stages.push({localRefusalKept: true});

  // A refusal by name: an expression naming an unknown parameter.
  await page.fill('#param-w', 'nope * 2'); await page.press('#param-w', 'Enter'); await settled();
  const refusal = await page.textContent('#refusal');
  assert.ok(await page.isVisible('#refusal'));
  assert.match(refusal, /nope/);
  assert.ok(await page.locator('#view.stale').count());
  report.stages.push({refusal});
  await page.screenshot({path: join(out, 'refusal.png')});
  await page.fill('#param-w', '0.4'); await page.press('#param-w', 'Enter'); await settled();
  assert.ok(!(await page.isVisible('#refusal')));

  // Save: the downloaded text is the edited document.
  const [download] = await Promise.all([page.waitForEvent('download'), page.click('#save-file')]);
  const saved = join(out, download.suggestedFilename());
  await download.saveAs(saved);
  assert.deepEqual(JSON.parse(await readFile(saved, 'utf8')), edited);
  report.stages.push({saved, equalsEditedDocument: true});

  report.cspViolations = await page.evaluate(() => window.__csp || []);
  assert.deepEqual(report.pageErrors, []);
  assert.deepEqual(report.console.filter(x => x.startsWith('error')), []);
  assert.deepEqual(report.cspViolations, []);
  report.status = 'passed';
} catch (error) {
  report.status = 'failed'; report.error = String(error && error.stack || error);
  process.exitCode = 1;
} finally {
  await browser.close();
  await writeFile(join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
}
