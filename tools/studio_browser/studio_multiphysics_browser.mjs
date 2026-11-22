// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Real-browser check of the Studio workspace's multiphysics model (contract D2): the Heated
// silicon waveguide template, its Connections view, a coupling removed and added back through
// the port pickers, a material problem and its one-click fix, a Run with per-physics progress,
// the coupled n_eff (exactly the engine's for the same document), the coupling check, and the
// optical model run alone. Then the same screens at 1440 x 900 and 390 px wide with no
// horizontal document overflow. Any page exception or console.error fails the check.
// Drives a preinstalled Chrome through the DevTools protocol with Node's built-in fetch and
// WebSocket; no npm package and no browser download. Fails, never skips, when no browser is found.
//
//   node tools/studio_browser/studio_multiphysics_browser.mjs --python <python> --output <dir> [--chrome <path>]
import assert from 'node:assert/strict';
import {spawn, spawnSync} from 'node:child_process';
import {existsSync} from 'node:fs';
import {mkdir, mkdtemp, rm, writeFile} from 'node:fs/promises';
import {createServer} from 'node:net';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';

const args = Object.fromEntries(process.argv.slice(2).reduce((pairs, value, index, all) =>
  index % 2 ? pairs : [...pairs, [value.replace(/^--/, ''), all[index + 1]]], []));
if (!args.python || !args.output) throw new Error('usage: --python <python> --output <dir> [--chrome <path>]');
const out = resolve(args.output);
await mkdir(out, {recursive: true});
const report = {status: 'incomplete', node: process.version, platform: process.platform, stages: [], exceptions: [], consoleErrors: []};
const sleep = ms => new Promise(r => setTimeout(r, ms));
const save = () => writeFile(join(out, 'report.json'), JSON.stringify(report, null, 1) + '\n', 'utf8');
const stage = (name, data = {}) => { report.stages.push({name, ...data}); console.log('[multiphysics browser]', name, JSON.stringify(data)); };

function findChrome() {
  const candidates = [args.chrome, process.env.CHROME_PATH];
  if (process.platform === 'win32') {
    for (const base of [process.env.PROGRAMFILES, process.env['PROGRAMFILES(X86)'], process.env.LOCALAPPDATA])
      if (base) candidates.push(join(base, 'Google', 'Chrome', 'Application', 'chrome.exe'), join(base, 'Microsoft', 'Edge', 'Application', 'msedge.exe'));
  } else if (process.platform === 'darwin') {
    candidates.push('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium');
  } else {
    const found = spawnSync('which', ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'], {encoding: 'utf8'});
    candidates.push(...found.stdout.split('\n'), '/opt/pw-browsers/chromium');
  }
  return candidates.find(path => path && existsSync(path.trim()))?.trim();
}
async function freePort() {
  const server = createServer();
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const port = server.address().port;
  await new Promise(r => server.close(r));
  return port;
}
const owned = [];
function launch(command, argv, name) {
  const child = spawn(command, argv, {stdio: ['ignore', 'pipe', 'pipe'], env: {...process.env, OPENBLAS_NUM_THREADS: '1', OMP_NUM_THREADS: '1', MKL_NUM_THREADS: '1'}});
  owned.push(child);
  let log = '';
  child.stdout.on('data', x => { log += x; });
  child.stderr.on('data', x => { log += x; });
  child.on('error', e => { log += String(e); });
  child.done = new Promise(r => child.on('close', (exit, signal) => { report[name] = {exit, signal}; writeFile(join(out, name + '.log'), log, 'utf8').then(r, r); }));
  return child;
}

class Page {
  constructor(url) {
    this.id = 0; this.pending = new Map(); this.ws = new WebSocket(url);
    this.ready = new Promise((r, j) => { this.ws.addEventListener('open', r, {once: true}); this.ws.addEventListener('error', j, {once: true}); });
    this.ws.addEventListener('message', event => {
      const message = JSON.parse(event.data);
      if (message.id) {
        const call = this.pending.get(message.id); if (!call) return;
        this.pending.delete(message.id); clearTimeout(call.timer);
        message.error ? call.reject(new Error(JSON.stringify(message.error))) : call.resolve(message.result);
      } else if (message.method === 'Runtime.exceptionThrown') report.exceptions.push(message.params.exceptionDetails?.exception?.description || message.params.exceptionDetails?.text);
      else if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error') report.consoleErrors.push(message.params.args.map(a => a.value ?? a.description).join(' '));
    });
  }
  call(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.pending.delete(id); reject(new Error('timeout: ' + method)); }, 60000);
      this.pending.set(id, {resolve, reject, timer});
      this.ws.send(JSON.stringify({id, method, params}));
    });
  }
  async eval(expression) {
    const result = await this.call('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true});
    if (result.exceptionDetails) throw new Error('page: ' + (result.exceptionDetails.exception?.description || result.exceptionDetails.text));
    return result.result.value;
  }
  async until(expression, label, ms = 60000) {
    const end = Date.now() + ms;
    while (Date.now() < end) { if (await this.eval(expression).catch(() => false)) return; await sleep(150); }
    throw new Error('timed out waiting for ' + label);
  }
  // Runs a fixed function on the document with the arguments as values, so no page code is built from them.
  async on(declaration, ...values) {
    const {result: document} = await this.call('Runtime.evaluate', {expression: 'document'});
    const result = await this.call('Runtime.callFunctionOn', {objectId: document.objectId, functionDeclaration: declaration,
      arguments: values.map(value => ({value})), awaitPromise: true, returnByValue: true});
    if (result.exceptionDetails) throw new Error('page: ' + (result.exceptionDetails.exception?.description || result.exceptionDetails.text));
    return result.result.value;
  }
  click(selector) { return this.on('function(s){const e=this.querySelector(s);if(!e)throw Error("missing "+s);e.click();return true}', selector); }
  text(selector) { return this.on('function(s){const e=this.querySelector(s);return e?e.innerText.replace(/\\s+/g," ").trim():null}', selector); }
  attr(selector, name) { return this.on('function(s,n){const e=this.querySelector(s);return e?e.getAttribute(n):null}', selector, name); }
  exists(selector) { return this.on('function(s){return !!this.querySelector(s)}', selector); }
  async type(selector, text) {
    await this.on('function(s){const e=this.querySelector(s);if(!e)throw Error("missing "+s);e.focus();e.select();return true}', selector);
    await this.call('Input.insertText', {text: String(text)});
    await this.on('function(s){const e=this.querySelector(s);e.dispatchEvent(new Event("change",{bubbles:true}));e.blur();return true}', selector);
    await sleep(150);
  }
  async choose(selector, value) {
    await this.on('function(s,v){const e=this.querySelector(s);if(!e)throw Error("missing "+s);e.value=v;e.dispatchEvent(new Event("change",{bubbles:true}));return true}', selector, value);
    await sleep(150);
  }
  async screenshot(name) { const png = await this.call('Page.captureScreenshot', {format: 'png', captureBeyondViewport: true}); await writeFile(join(out, name + '.png'), Buffer.from(png.data, 'base64')); }
}

const profile = await mkdtemp(join(tmpdir(), 'openphysics-multiphysics-browser-'));
try {
  const chrome = findChrome();
  report.chrome = chrome || null;
  if (!chrome) throw new Error('No preinstalled Chrome, Chromium or Edge found; set --chrome or CHROME_PATH. No browser is downloaded.');
  const apiPort = await freePort(), debugPort = await freePort(), base = `http://127.0.0.1:${apiPort}`;
  launch(args.python, ['-I', '-m', 'simcase.studio', '--workspace', '--no-browser', '--port', String(apiPort)], 'server');
  let up = false;
  for (let i = 0; i < 240 && !up; i++) { try { up = (await fetch(base + '/workspace')).ok; } catch {} if (!up) await sleep(250); }
  if (!up) throw new Error('Studio did not start');
  const sandbox = process.getuid?.() === 0 ? ['--no-sandbox'] : [];
  launch(chrome, ['--headless=new', '--disable-gpu', ...sandbox, '--no-first-run', '--no-default-browser-check', '--remote-debugging-address=127.0.0.1',
    '--remote-debugging-port=' + debugPort, '--user-data-dir=' + profile, '--window-size=1440,900', 'about:blank'], 'browser');
  let target;
  for (let i = 0; i < 120 && !target; i++) { try { target = (await (await fetch(`http://127.0.0.1:${debugPort}/json/list`)).json()).find(t => t.type === 'page'); } catch {} if (!target) await sleep(250); }
  if (!target) throw new Error('Browser DevTools endpoint unavailable');
  const page = new Page(target.webSocketDebuggerUrl); await page.ready;
  await page.call('Runtime.enable'); await page.call('Page.enable'); await page.call('DOM.enable');
  const size = (width, height, mobile = false) => page.call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile});
  const overflow = () => page.eval('document.documentElement.scrollWidth-document.documentElement.clientWidth');
  const runReady = () => page.until("!document.getElementById('run-multiphysics').disabled", 'Run enabled', 60000);
  await size(1440, 900);

  // MB1: the template card opens a checked multiphysics model; the tree has order badges
  await page.call('Page.navigate', {url: base + '/workspace'});
  await page.until("!!document.querySelector('[data-template=heated-waveguide]')", 'start page');
  assert.match(await page.text('[data-template=heated-waveguide]'), /Heated silicon waveguide.*Heat → optical modes · coupled/);
  assert.equal(await page.exists('[data-template=multi]'), false, 'the setup-only card is replaced');
  await page.click('[data-template=heated-waveguide]');
  await page.until("!!document.querySelector('#tree [data-mp-node=\"physics:heat1\"]')", 'multiphysics tree');
  await runReady();
  assert.match(await page.text('#tree [data-mp-node="physics:heat1"]'), /^∿ 1 Heat 1 · Heat transfer$/);
  assert.match(await page.text('#tree [data-mp-node="physics:modes1"]'), /^∿ 2 Modes 1 · Optical modes$/);
  assert.equal(await page.text('#tree [data-mp-node="coupling:heat1_to_modes1"]'), '⇄ Heat 1 temperature → Modes 1 temperature');
  assert.equal(await page.text('#project'), 'Multiphysics model / Not saved to a file · runs stay in this tab');
  assert.equal(await page.eval("document.getElementById('run-optical').hidden&&document.getElementById('run-heat').hidden&&document.getElementById('run-joule').hidden"), true);
  stage('MB1 template', {tree: await page.text('#tree')});

  // MB2: Connections is drawn from the couplings: two nodes in order, one temperature wire
  await page.click('nav [data-page=Connections]');
  await page.until("document.querySelectorAll('.mp-stage .graph-wires path.temperature').length===1", 'one wire');
  assert.deepEqual(await page.eval("[...document.querySelectorAll('.mp-stage .graph-node-title')].map(e=>e.innerText.split('\\n')[0].trim())"), ['1Heat 1', '2Modes 1']);
  assert.equal(await page.eval("document.querySelector('.mp-stage .graph-wires path.temperature').dataset.coupling"), 'heat1_to_modes1');
  stage('MB2 connections');

  // MB3: remove the coupling, get the suggestion, add it back through the dialog; Undo/Redo
  await page.click('#tree [data-mp-node="coupling:heat1_to_modes1"]');
  await page.until("/Remove coupling/.test(document.getElementById('inspector').innerText)", 'coupling settings');
  assert.match(await page.text('#inspector'), /Transfer Same mesh \(both use Mesh 1\).*each triangle gets the mean of its 3 nodes.*Name in file heat1_to_modes1/);
  await page.click('[data-mp-remove-coupling]');
  await page.until("/Modes 1 can take its temperature from Heat 1/.test(document.getElementById('mp-messages').innerText)", 'suggestion');
  await runReady();          // two physics without a coupling still run; nothing is coupled silently
  await page.click('#mp-messages [data-mp-add-coupling]');
  await page.until("!!document.querySelector('dialog.mp-dialog #mp-to')", 'coupling dialog');
  assert.equal(await page.eval("document.querySelector('#mp-from').value"), 'heat1.temperature');
  assert.equal(await page.eval("[...document.querySelectorAll('#mp-from option')].find(o=>o.value==='modes1.effective_index').disabled"), true);
  assert.match(await page.text('dialog.mp-dialog'), /each triangle gets the mean of its 3 nodes/);
  await page.click('#mp-coupling-add');
  await page.until("!!document.querySelector('#tree [data-mp-node=\"coupling:heat1_to_modes1\"]')&&!document.querySelector('dialog[open]')", 'coupling added');
  await page.click('#undo-edit');
  await page.until("!document.querySelector('#tree [data-mp-node=\"coupling:heat1_to_modes1\"]')", 'undo');
  await page.click('#redo-edit');
  await page.until("!!document.querySelector('#tree [data-mp-node=\"coupling:heat1_to_modes1\"]')", 'redo');
  stage('MB3 coupling removed and added');

  // MB4: a missing thermo-optic value is one problem in four places; Fill from physmat fixes it
  await page.click('nav [data-page=Model]');
  await page.click('#tree [data-mp-node="material:heater"]');
  await page.until("!!document.querySelector('[data-mp-quantity*=thermo_optic_coefficient]')", 'heater settings');
  await page.type('[data-mp-quantity*=thermo_optic_coefficient]', '');
  await page.until("document.getElementById('run-multiphysics-reason').textContent==='Fix 1 problem in Messages to run'", 'Run blocked');
  assert.equal(await page.eval("document.getElementById('run-multiphysics').disabled"), true);
  assert.match(await page.text('#mp-messages'), /Heater gives a reference temperature but no thermo-optic coefficient/);
  assert.equal(await page.text('#tree [data-mp-node="material:heater"] .problem-badge'), '1');
  assert.equal(await page.attr('[data-mp-quantity*=thermo_optic_coefficient]', 'aria-invalid'), 'true');
  await page.screenshot('mb4-material-problem');
  await page.click('#mp-messages [data-mp-fix]');
  await runReady();
  assert.match(await page.text('#inspector'), /thermo-optic data copied from physmat:SiO2/);
  stage('MB4 material problem fixed');

  // MB5: Run: per-physics progress, the coupled n_eff, exactly the engine's for the same document
  await page.click('#run-multiphysics');
  await page.until("!!document.querySelector('[data-neff=\"1\"]')", 'result', 120000);
  assert.match(await page.text('#sequence'), /Heat 1 · Done in [0-9.]+ s.*Modes 1 · Done in [0-9.]+ s/);
  const shown = await page.attr('[data-neff="1"]', 'data-neff-value');
  const documentSent = JSON.parse(await page.eval("fetch('/api/multiphysics/template').then(r=>r.text())"));
  documentSent.materials.heater.thermo_optic_coefficient = '1.0e-5 1/K';
  documentSent.materials.heater.source += '; thermo-optic data copied from physmat:SiO2 (physmat)';
  const engine = spawnSync(args.python, ['-I', '-c', 'import json,sys\nfrom simcase import Document, multiphysics\nr=multiphysics.run(Document.from_dict(json.loads(sys.stdin.read())),verbose=False)\nprint(repr(float(r.results["modes1"].effective_index[0][0])))'],
    {input: JSON.stringify(documentSent), encoding: 'utf8'});
  assert.equal(engine.status, 0, engine.stderr);
  assert.equal(shown, engine.stdout.trim(), 'the coupled n_eff is the engine run of the same document');
  stage('MB5 run', {coupled_neff: shown, engine_neff: engine.stdout.trim()});
  await page.click('[data-mp-node="results:check"]');
  await page.until("/Coupling check/.test(document.getElementById('canvas').innerText)", 'coupling check');
  assert.match(await page.text('.mp-check tbody'), /node temperatures, 300\.0–[0-9.]+ K .*triangle means \(mean of 3 nodes\) Passed · max \|received − sent\| = 0 K/);

  // MB6: the optical model alone adds the uncoupled column; the heater shifts n_eff upward
  await page.click('[data-mp-node="results:modes1"]');
  await page.until("!!document.getElementById('mp-run-alone')", 'modes page');
  await page.click('#mp-run-alone');
  await page.until("!!document.querySelector('[data-neff-alone=\"1\"]')", 'uncoupled result', 120000);
  const alone = Number(await page.attr('[data-neff-alone="1"]', 'data-neff-value'));
  assert.ok(Number(shown) > alone, `coupled ${shown} above uncoupled ${alone}`);
  stage('MB6 uncoupled comparison', {uncoupled_neff: alone, shift: Number(shown) - alone});

  // MB7a: Open model file: the server's reader sees the text; a duplicate key is refused by
  // name and the model stays; the shipped heated slab example then opens as a model
  const setFile = async path => {
    const {root} = await page.call('DOM.getDocument');
    const {nodeId} = await page.call('DOM.querySelector', {nodeId: root.nodeId, selector: '#project-file'});
    await page.call('DOM.setFileInputFiles', {nodeId, files: [path]});
  };
  const duplicate = join(out, 'duplicate-key.json');
  await writeFile(duplicate, '{"openphysics": "0.3/multiphysics.1", "name": "a", "name": "b"}', 'utf8');
  await setFile(duplicate);
  await page.until("/Open failed: .*appears more than once/.test(document.getElementById('file-status').textContent)", 'duplicate key refused');
  assert.equal(await page.text('#project'), 'Multiphysics model / Not saved to a file · runs stay in this tab');
  await setFile(resolve('examples/simcase/multiphysics_heated_slab.json'));
  await page.until("!!document.querySelector('#tree [data-mp-node=\"coupling:heat_to_optics\"]')", 'example opened');
  await runReady();
  assert.match(await page.text('#project'), /^Multiphysics model \/ Opened from multiphysics_heated_slab\.json$/);
  stage('MB7a open model file');

  // MB7: the screens at 1440 x 900 and 390 px: no document overflow
  const screens = {};
  for (const [width, height, tag, mobile] of [[1440, 900, 'wide', false], [390, 844, 'phone', true]]) {
    await size(width, height, mobile); await sleep(300);
    for (const pageName of ['Model', 'Connections', 'Results']) {
      await page.click(`nav [data-page=${pageName}]`); await sleep(400);
      screens[`${tag}-${pageName}`] = await overflow();
      await page.screenshot(`mb7-${tag}-${pageName.toLowerCase()}`);
    }
  }
  assert.deepEqual(Object.values(screens).filter(v => v > 0), [], JSON.stringify(screens));
  stage('MB7 screens', screens);

  assert.deepEqual(report.exceptions, []); assert.deepEqual(report.consoleErrors, []);
  report.status = 'passed';
} catch (error) {
  report.status = 'failed'; report.error = String(error?.stack || error);
  process.exitCode = 1;
} finally {
  for (const child of owned) child.kill();
  await save();
  await rm(profile, {recursive: true, force: true}).catch(() => {});
  console.log('[multiphysics browser]', report.status, report.error || '');
}
