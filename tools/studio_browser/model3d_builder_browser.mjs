// Real-browser checks of the 3D model in the workspace (slice B of the Studio 3D view).
// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
//
// A local check, not wired into CI: it needs Playwright with a Chromium it can launch
// (not a repository dependency). From the repository root, with a Studio server running:
//   python -m simcase.studio --no-browser --port 8765 &
//   node tools/studio_browser/model3d_builder_browser.mjs http://127.0.0.1:8765 out-dir
// Pre-registered checks (thresholds fixed before measuring):
//  W4  each of 10 listed faces of the card layer-stack-3d picked (in the view where it is visible,
//      else in the faces list), Use for → New selection; the selection the page writes and the
//      listed name typed by hand resolve (server check) to the picked face: 10/10;
//  W5  one model3d session per E-3D-COMBINATION stem the check raises: Messages shows the
//      engine's words as written and the code under Details, and the tree marks features[i]: 100%;
//  W11 without runs: the document digest is equal after Save and Open, for the project and for the
//      session; a version 1 project without 3D opened and saved stays version 1 with its entries'
//      bytes and digests unchanged (the byte-for-byte check is studio_model3d_files.cjs);
//  W12 the Library, and the Model with the card, at 1440 × 900 and 390 × 844: no console error, no
//      CSP violation, the canvas visible and not empty, no horizontal scroll at 390, the faces list
//      reachable by Tab; screenshots stored;
//  W13 keyboard only: open the card, rotate, view 5, select via.z1 from the list, Use for → New
//      selection; no pointer event.
// It writes report.json and screenshots to out-dir and exits non-zero if a check fails.
import {createRequire} from 'node:module';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';

const require = createRequire(import.meta.url);
const {chromium} = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:8765';
const out = process.argv[3] || 'model3d-builder-browser';
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
await mkdir(out, {recursive: true});
const CARD = JSON.parse(await readFile(join(ROOT, 'packages/simcase/src/simcase/studio/static/model3d-layer-stack-3d.json'), 'utf8'));
const V1 = await readFile(join(ROOT, 'tests/simcase/studio_session_fixtures/project-v1.json'), 'utf8');
const W4_NAMES = ['stack.sub.domain.x0', 'stack.oxide.domain.y1', 'stack.top.domain.x1', 'stack.top.top', 'via.x0', 'via.x1',
  'via.y0', 'via.y1', 'via.z0', 'via.z1'];
const IN_VIEW = new Set(['stack.top.top', 'stack.top.domain.x1']);      // visible from the isometric camera
const origin = new URL(base).origin;
const report = {base, checks: {}};
let failed = false;
const record = (name, ok, detail) => { report.checks[name] = {ok, ...detail}; if (!ok) failed = true; console.log(`${ok ? 'PASS' : 'FAIL'} ${name}`); };
const sha = text => createHash('sha256').update(text, 'utf8').digest('hex');
const session = doc => JSON.stringify({format: 'openphysics-studio-session', version: 1, application: 'model3d', document: doc});

async function open(browser, viewport) {
  const page = await browser.newPage({viewport, acceptDownloads: true});
  const seen = {console: [], pageErrors: [], foreign: []};
  page.on('console', m => { if (m.type() === 'error') seen.console.push(m.text()); });
  page.on('pageerror', e => seen.pageErrors.push(String(e)));
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
async function canvasState(page, selector) {
  return page.evaluate(sel => {
    const c = document.querySelector(sel), r = c.getBoundingClientRect(), probe = document.createElement('canvas');
    probe.width = c.width; probe.height = c.height; const g = probe.getContext('2d'); g.drawImage(c, 0, 0);
    const d = g.getImageData(0, 0, probe.width, probe.height).data; let drawn = 0;
    for (let i = 0; i < d.length; i += 4) if (Math.abs(d[i] - 0xfb) + Math.abs(d[i + 1] - 0xfc) + Math.abs(d[i + 2] - 0xfd) > 24) drawn++;
    return {x: r.x, y: r.y, width: r.width, height: r.height, visible: r.width > 0 && r.height > 0 && getComputedStyle(c).display !== 'none',
      drawn, pixels: d.length / 4, scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth};
  }, selector);
}
async function tabTo(page, test, limit = 160) {
  for (let i = 1; i <= limit; i++) { await page.keyboard.press('Tab'); if (await page.evaluate(test)) return i; }
  return null;
}
async function serverCheck(page, doc) {
  return page.evaluate(async d => (await fetch('/api/model3d/check', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({doc: d})})).json(), doc);
}
// A save: the name dialog when Studio asks for a name, else a direct download under the name it
// remembers (a project opened from a file is saved again under that name).
async function download(page, trigger) {
  const done = page.waitForEvent('download', {timeout: 30000});
  await trigger();
  const asked = await page.waitForSelector('#save-name-dialog[open]', {timeout: 3000}).then(() => true, () => false);
  if (asked) await page.click('#save-name-download');
  return readFile(await (await done).path(), 'utf8');
}
async function openFile(page, name, text) {
  await page.setInputFiles('#session-file', {name, mimeType: 'application/json', buffer: Buffer.from(text)});
}

const browser = await chromium.launch();
try {
  // ---- W12: the Library and the Model with the card -------------------------------------------
  for (const viewport of [{width: 1440, height: 900}, {width: 390, height: 844}]) {
    const tag = `${viewport.width}x${viewport.height}`;
    const {page, seen} = await open(browser, viewport);
    const lib = await page.evaluate(() => ({scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth,
      card: !!document.querySelector('.library-3d [data-model3d-card="layer-stack-3d"]'), text: document.querySelector('.library-3d')?.textContent || ''}));
    await page.screenshot({path: join(out, `w12-library-${tag}.png`), fullPage: true});
    await page.click('[data-model3d-card]'); await checked(page);
    const state = await canvasState(page, '#m3-canvas');
    await page.screenshot({path: join(out, `w12-model-${tag}.png`), fullPage: true});
    await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });
    const tabs = await tabTo(page, () => !!document.activeElement?.closest('#m3-faces'));
    const c = await csp(page);
    const ok = lib.card && /Square via/.test(lib.text) && !seen.console.length && !seen.pageErrors.length && !c.length && !seen.foreign.length
      && state.visible && state.drawn > 0.02 * state.pixels && tabs !== null
      && (viewport.width !== 390 || (lib.scrollWidth <= lib.innerWidth && state.scrollWidth <= state.innerWidth));
    record(`W12 ${tag}`, ok, {library: lib, canvas: state, tabsToFacesList: tabs, console: seen.console, pageErrors: seen.pageErrors, csp: c, foreign: seen.foreign});
    if (viewport.width === 1440) {
      // the tree of design 5.2 for this step, with the server's coverage and Form result counts
      const tree = await page.evaluate(() => ({heading: document.querySelector('#tree .tree-heading')?.textContent || '', project: document.getElementById('project').textContent,
        rows: [...document.querySelectorAll('#tree [data-m3-node]')].map(b => [b.dataset.m3Node, b.querySelector('.m3-note')?.textContent || ''])}));
      const notes = Object.fromEntries(tree.rows), answer = await serverCheck(page, CARD);
      tree.server = {regions: answer.regions.length, faces: answer.display.faces.length};
      const treeOk = tree.heading.endsWith('Component 1 · 3D · µm') && tree.project.startsWith('Untitled project · not saved to a file')
        && JSON.stringify(tree.rows.map(r => r[0])) === JSON.stringify(['parameters', 'geometry', 'domain', 'feature:0', 'feature:1', 'form', 'materials'])
        && notes['feature:0'] === 'sub · oxide · top (covered in part by 2 (via))' && notes['feature:1'] === '20 × 20 × 10 µm'
        && notes.form === `${tree.server.regions} regions · ${tree.server.faces} faces` && notes.materials === 'Si · SiO2 · Cu';
      record('Tree (design 5.2)', treeOk, tree);
    }
    await page.close();
  }

  // ---- W4: pick → Use for → New selection, 10 listed faces -------------------------------------
  {
    const {page, seen} = await open(browser, {width: 1440, height: 900});
    await page.click('[data-model3d-card]'); await checked(page);
    const answer = await serverCheck(page, CARD);
    const faceOf = Object.fromEntries(answer.display.faces.flatMap(f => f.alone.map(n => [n, f.id])));
    const rows = [];
    for (const [i, name] of W4_NAMES.entries()) {
      const id = faceOf[name];
      let how;
      await checked(page);                // the check after the last edit has answered; the layout is settled
      if (IN_VIEW.has(name)) {
        // the face's centroid on the canvas, by the camera contract (model3d-model.mjs)
        const point = await page.evaluate(async ({id, view}) => {
          const M = await import('/model3d-assets/model3d-model.mjs');
          const c = document.getElementById('m3-canvas');c.scrollIntoView({block: 'center'});const r = c.getBoundingClientRect();
          const pos = M.decode(view.positions, Float32Array), idx = M.decode(view.indices, Uint32Array), f = view.faces[id];
          let s = [0, 0, 0], n = 0;
          for (let t = f.first_triangle; t < f.first_triangle + f.triangle_count; t++) for (let k = 0; k < 3; k++) { const v = idx[3 * t + k]; for (let a = 0; a < 3; a++) s[a] += pos[3 * v + a]; n++; }
          s = s.map(x => x / n);
          const fr = M.frameOf(M.viewCamera(view, 'iso'), r.width, r.height);
          const u = M.dot(s, fr.x) / fr.halfWidth, w = M.dot(s, fr.y) / fr.halfHeight;
          return {x: r.x + (u + 1) * r.width / 2, y: r.y + (1 - w) * r.height / 2};
        }, {id, view: answer.display});
        await page.mouse.click(point.x, point.y); how = 'view';
      } else {
        await page.click(`#m3-faces li[data-face="${id}"]`); how = 'faces list';
      }
      const picked = await page.evaluate(() => document.getElementById('m3-names').dataset.face);
      await page.fill('#m3-use-name', `w4_${i}`);
      await page.click('#m3-use-go');
      await page.waitForSelector(`[data-m3-selection="w4_${i}"]`, {timeout: 15000});
      await checked(page);
      const written = JSON.parse(await page.evaluate(k => document.querySelector(`[data-m3-selection="${k}"] .m3-sel-entry`).textContent, `w4_${i}`));
      rows.push({name, id, how, picked: picked === '' ? null : Number(picked), written});
    }
    // resolve: the written selection and the listed name typed by hand, in one document
    const doc = structuredClone(CARD), sel = doc.geometry.components.stack3d.selections = {};
    rows.forEach((r, i) => { sel[`made_${i}`] = r.written; sel[`hand_${i}`] = {boundary: r.name}; });
    const resolved = await serverCheck(page, doc);
    const entries = Object.fromEntries(resolved.selections.map(s => [s.name, s.entries]));
    let matched = 0;
    rows.forEach((r, i) => { r.made = entries[`made_${i}`]; r.hand = entries[`hand_${i}`];
      r.ok = r.picked === r.id && JSON.stringify(r.made) === JSON.stringify([r.id]) && JSON.stringify(r.hand) === JSON.stringify([r.id]); matched += r.ok; });
    await page.screenshot({path: join(out, 'w4-selections.png')});
    record('W4', matched === 10 && !seen.pageErrors.length, {matched, rows, pageErrors: seen.pageErrors});
    await page.close();
  }

  // ---- W5: one session per stem -------------------------------------------------------------
  {
    const box = (name, lo, hi) => ({name, type: 'box', xmin: lo[0], xmax: hi[0], ymin: lo[1], ymax: hi[1], zmin: lo[2], zmax: hi[2], material: 'm'});
    const docOf = (features, footprint) => {
      const comps = {c: {dimension: '3d', length_unit: 'um', domain: {xmin: 0, xmax: 10, ymin: 0, ymax: 10, zmin: 0, zmax: 5}, background: {material: 'air'}, features}};
      if (footprint) comps.fp = {dimension: '2d', length_unit: 'um', depth: null, domain: {xmin: 0, xmax: 10, ymin: 0, ymax: 10}, background: {material: 'air'},
        features: [{name: 'pad', type: 'rect', x: 2, y: 2, w: 2, h: 2, material: 'm'}]};
      return {openphysics: '0.3', materials: {m: {}, air: {}}, geometry: {version: 1, components: comps}};
    };
    const FOOT = {name: 'f', type: 'layers', z0: 0, layers: [{name: 'a', thickness: 1, footprint: 'fp'}]};
    const cases = {
      'S1 footprint layers alone': [docOf([FOOT], true), 0],
      'S2 footprint layers beside other features': [docOf([box('b0', [0, 0, 0], [1, 1, 1]), FOOT], true), 1],
      'S3 extrude': [docOf([box('b0', [0, 0, 0], [1, 1, 1]), {name: 'e', type: 'extrude', zmin: 0, zmax: 1, material: 'm', profile: {type: 'rect', x: 0, y: 0, w: 1, h: 1}}]), 1],
      'S3 cylinder': [docOf([{name: 'pin', type: 'cylinder', axis: 'z', cx: 5, cy: 5, r: 1, zmin: 0, zmax: 1, material: 'm'}]), 0],
      'S3 sphere': [docOf([box('b0', [0, 0, 0], [1, 1, 1]), box('b1', [1, 1, 1], [2, 2, 2]), {name: 'ball', type: 'sphere', cx: 5, cy: 5, cz: 2, r: 1, material: 'm'}]), 2],
    };
    const {page, seen} = await open(browser, {width: 1440, height: 900});
    const rows = [];
    for (const [label, [doc, index]] of Object.entries(cases)) {
      const expected = await page.evaluate(async d => (await fetch('/api/model3d/check', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({doc: d, component: 'c'})})).json(), doc);
      await openFile(page, 'stem.json', session(doc));
      await page.waitForSelector('[data-m3-refusal]', {timeout: 15000});
      const shown = await page.evaluate(() => ({text: document.querySelector('[data-m3-refusal] p').textContent,
        details: document.querySelector('[data-m3-refusal] details')?.textContent || '',
        marked: [...document.querySelectorAll('[data-m3-node].has-problem')].map(b => b.dataset.m3Node),
        block: document.getElementById('m3-block')?.textContent || '', stale: !!document.querySelector('.m3-stage.stale')}));
      const ok = expected.code === 'E-3D-COMBINATION' && shown.text === expected.refused && shown.details.includes('E-3D-COMBINATION')
        && JSON.stringify(shown.marked) === JSON.stringify([`feature:${index}`]) && shown.block === 'Fix 1 problem in Messages to mesh';
      rows.push({label, index, expected: expected.refused, shown, ok});
      await page.screenshot({path: join(out, `w5-${label.replace(/[^a-z0-9]+/gi, '-')}.png`)});
    }
    const passed = rows.filter(r => r.ok).length;
    record('W5', passed === rows.length && !seen.pageErrors.length, {passed, of: rows.length, rows, pageErrors: seen.pageErrors,
      notApplicable: ['"... round to the same coordinate" and circle_segments: raised by build_mesh3d when meshing (slice C), not by the check']});
    await page.close();
  }

  // ---- W11: Save and Open, project and session -----------------------------------------------
  {
    const {page, seen} = await open(browser, {width: 1440, height: 900});
    await page.click('[data-model3d-card]'); await checked(page);
    // an edit, so the document is not the card's: a parameter
    await page.click('[data-m3-node="parameters"]');
    await page.fill('.m3-param-add input[name=name]', 'w'); await page.fill('.m3-param-add input[name=value]', '20 um');
    await page.click('.m3-param-add button[type=submit]'); await checked(page);
    const save = () => download(page, async () => { await page.click('#file-menu-button'); await page.click('#menu-save'); });
    const first = await save();
    await openFile(page, 'project.json', first); await checked(page);
    const second = await save();
    const entry = t => JSON.parse(t).models.find(m => m.kind === 'model3d');
    const a = entry(first), b = entry(second);
    const projectOk = JSON.parse(first).version === 2 && a.digest === b.digest && sha(JSON.stringify(a.session.document)) === sha(JSON.stringify(b.session.document))
      && a.session.document.geometry.parameters?.w?.value === '20 um';
    // the session: Export › Model with runs, open it, export again
    const exportSession = () => download(page, async () => { await page.click('#file-menu-button'); await page.click('#menu-export'); await page.click('#menu-export-session'); });
    const s1 = await exportSession();
    await openFile(page, 'model3d-session.json', s1); await checked(page);
    const s2 = await exportSession();
    const sessionOk = s1 === s2 && JSON.parse(s1).application === 'model3d' && sha(JSON.stringify(JSON.parse(s1).document)) === sha(JSON.stringify(a.session.document));
    // a version 1 project without 3D: opened and saved, still version 1 with the same entries
    await openFile(page, 'project-v1.json', V1);
    await page.waitForFunction(() => /Opened project/.test(document.getElementById('file-status').textContent), null, {timeout: 30000});
    const v1Again = await save();
    // version 1, no 3D entry, the multiphysics entry unchanged; the optical entry is written again from
    // the tab's state as before this change (measured on main 7a565bf: 7649 bytes, sha256:b94ec466...)
    const strip = t => JSON.parse(t).models.map(m => [m.id, m.kind, m.bytes, m.digest]);
    const again = strip(v1Again), fixture = strip(V1);
    const v1Ok = JSON.parse(v1Again).version === 1 && JSON.stringify(again.map(m => m[1])) === '["workspace","multiphysics"]'
      && JSON.stringify(again[1]) === JSON.stringify(fixture[1]) && again[0][2] === 7649 && again[0][3].startsWith('sha256:b94ec466');
    await writeFile(join(out, 'w11-project.json'), first); await writeFile(join(out, 'w11-session.json'), s1); await writeFile(join(out, 'w11-v1-again.json'), v1Again);
    record('W11', projectOk && sessionOk && v1Ok && !seen.pageErrors.length, {projectOk, sessionOk, v1Ok,
      projectDigest: [a.digest, b.digest], sessionSha: [sha(s1), sha(s2)], pageErrors: seen.pageErrors});
    await page.close();
  }

  // ---- W13: keyboard only -------------------------------------------------------------------
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
    steps.viaFocused = await tabTo(page, () => !!document.activeElement?.closest('#m3-faces') && document.activeElement.getAttribute('aria-label').split(': ')[1].split(', ').includes('via.z1')) !== null;
    await page.keyboard.press('Enter');
    steps.viaSelected = (await page.evaluate(() => [...document.querySelectorAll('#m3-names code')].map(e => e.textContent))).includes('via.z1');
    steps.applyFocused = await tabTo(page, () => document.activeElement?.id === 'm3-use-go', 60) !== null;
    await page.keyboard.press('Enter');
    await page.waitForSelector('[data-m3-selection]', {timeout: 15000});
    steps.selection = await page.evaluate(() => document.querySelector('[data-m3-selection] .m3-sel-entry').textContent);
    steps.pointerEvents = await page.evaluate(() => window.__pointer);
    await page.screenshot({path: join(out, 'w13-keyboard.png')});
    const ok = steps.cardFocused && steps.canvasFocused && steps.rotated && steps.view5 && steps.viaFocused && steps.viaSelected && steps.applyFocused
      && steps.selection === '{"boundary":"via.z1"}' && steps.pointerEvents === 0 && !seen.console.length && !seen.pageErrors.length;
    record('W13', ok, {steps, console: seen.console, pageErrors: seen.pageErrors});
    await page.close();
  }
} finally {
  await writeFile(join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}
if (failed) process.exit(1);
