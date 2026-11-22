// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Real-browser check of the Studio workspace's multiphysics model (contract D2): the Heated
// silicon waveguide template, its Connections view, a coupling removed and added back through
// the port pickers, a material problem and its one-click fix, a Run with per-physics progress,
// the coupled n_eff (exactly the engine's for the same document), the coupling check, and the
// optical model run alone. Round 4: an edit marks the run out of date, a removed coupling
// leaves a warning and Undo, the heater-off column is solved with the run ("Also solve without
// heater") and stays valid when the same model is run again, and Δn_eff (coupled − without
// heater) equals the engine's runs of the same documents exactly. Round 5: the wire leaves from
// the coupled port's dot on the node edge, the Run buttons' accessible names are their labels,
// the heater-off option stays visible (disabled with its reason) without a temperature coupling,
// the n_eff table comes before the maps, the model back at the last run says so in one sentence
// everywhere, and leaving a model whose runs only this tab holds asks first. Then the same
// screens at 1440 x 900 and 390 px wide with no horizontal document overflow. Any page exception or console.error fails the check.
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
import {fileURLToPath} from 'node:url';

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
  // A model tree node by role and accessible name, as assistive technology finds it (the
  // accessibility tree): exactly one tree item must have the name.
  async treeItem(name) {
    const {result: document} = await this.call('Runtime.evaluate', {expression: 'document'});
    const {nodes} = await this.call('Accessibility.queryAXTree', {objectId: document.objectId, accessibleName: name, role: 'treeitem'});
    const found = nodes.filter(n => !n.ignored);
    if (found.length !== 1) throw new Error(`${found.length} tree items named ${JSON.stringify(name)}`);
    const {object} = await this.call('DOM.resolveNode', {backendNodeId: found[0].backendDOMNodeId});
    return object.objectId;
  }
  async clickTreeItem(name) {
    const result = await this.call('Runtime.callFunctionOn', {objectId: await this.treeItem(name), functionDeclaration: 'function(){this.click();return true}', returnByValue: true});
    if (result.exceptionDetails) throw new Error('page: ' + result.exceptionDetails.text);
  }
  // Every tree item and the tree itself in the accessibility tree: [{role, name, level, selected, expanded}]
  async axTree() {
    const {result: document} = await this.call('Runtime.evaluate', {expression: 'document'});
    const prop = (n, key) => n.properties?.find(p => p.name === key)?.value?.value;
    const read = async role => (await this.call('Accessibility.queryAXTree', {objectId: document.objectId, role})).nodes.filter(n => !n.ignored)
      .map(n => ({role, name: n.name?.value ?? '', level: prop(n, 'level') ?? null, selected: prop(n, 'selected') ?? null, expanded: prop(n, 'expanded') ?? null}));
    return [...await read('tree'), ...await read('treeitem')];
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
  // the accessible name Chrome computes, as a screen reader gets it
  async axName(selector) {
    const {root} = await this.call('DOM.getDocument');
    const {nodeId} = await this.call('DOM.querySelector', {nodeId: root.nodeId, selector});
    const {nodes} = await this.call('Accessibility.getPartialAXTree', {nodeId, fetchRelatives: false});
    return nodes[0]?.name?.value ?? null;
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
  await page.call('Runtime.enable'); await page.call('Page.enable'); await page.call('DOM.enable'); await page.call('Accessibility.enable');
  const size = (width, height, mobile = false) => page.call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile});
  const overflow = () => page.eval('document.documentElement.scrollWidth-document.documentElement.clientWidth');
  const runReady = () => page.until("!document.getElementById('run-multiphysics').disabled", 'Run enabled', 60000);
  await size(1440, 900);

  // MB1: the template card opens a checked multiphysics model; the tree has order badges
  await page.call('Page.navigate', {url: base + '/workspace'});
  await page.until("!!document.querySelector('[data-template=heated-waveguide]')", 'start page');
  assert.match(await page.text('[data-template=heated-waveguide]'), /Heated silicon waveguide.*Heat → optical modes · coupled/);
  assert.equal(await page.exists('[data-template=multi]'), false, 'the setup-only card is replaced');
  assert.equal(await page.axName('#run-optical'), 'Run optical study');
  await page.click('[data-template=heated-waveguide]');
  await page.until("!!document.querySelector('#tree [data-mp-node=\"physics:heat1\"]')", 'multiphysics tree');
  await runReady();
  assert.match(await page.text('#tree [data-mp-node="physics:heat1"]'), /^∿ 1 Heat 1 · Heat transfer$/);
  assert.match(await page.text('#tree [data-mp-node="physics:modes1"]'), /^λ 2 Modes 1 · Optical modes$/);
  // the ribbon: Run as Run optical study draws it, the heater-off option on, Open session and Save session in Project
  // the ▶ is decoration with an empty alternative text: the accessible names are the labels
  assert.equal(await page.eval("getComputedStyle(document.getElementById('run-multiphysics'),'::before').content"), '"▶" / ""');
  assert.equal(await page.axName('#run-multiphysics'), 'Run');
  assert.equal(await page.eval("getComputedStyle(document.getElementById('run-multiphysics')).fontWeight"), await page.eval("getComputedStyle(document.getElementById('run-optical')).fontWeight"));
  assert.equal(await page.eval("!document.getElementById('run-baseline-option').hidden&&document.getElementById('run-baseline').checked"), true);
  assert.equal(await page.text('#run-baseline-option'), 'Also solve without heater ~1 s');
  assert.deepEqual(await page.eval("[...document.getElementById('open-session').parentElement.children].filter(b=>b.tagName==='BUTTON'&&!b.hidden).map(b=>b.innerText.trim())"), ['Open session', 'Save session']);
  // the model file alone is More › Save inputs only and Open inputs file
  assert.deepEqual(await page.eval("['save-project','open-project'].map(id=>document.getElementById(id).textContent+':'+!document.getElementById(id).hidden+':'+!!document.getElementById(id).closest('.file-menu'))"),
    ['Save inputs only:true:true', 'Open inputs file:true:true']);
  assert.doesNotMatch(await page.eval('document.body.innerText'), /runs stay in this tab/i);
  assert.equal(await page.text('.dock-title>span'), 'Nothing is computed until you press Run');
  assert.equal(await page.text('#status'), 'Model checked · press Run');
  assert.equal(await page.text('#tree [data-mp-node="coupling:heat1_to_modes1"]'), '⇄ Heat 1 temperature → Modes 1 temperature');
  // round 10 (K9): the multiphysics model builder is an ARIA tree, used with the keyboard alone
  const KEYS = {ArrowDown: 40, ArrowUp: 38, ArrowLeft: 37, ArrowRight: 39, Home: 36, End: 35, Enter: 13, ' ': 32, Tab: 9};
  const press = async key => {
    for (const type of ['keyDown', 'keyUp']) await page.call('Input.dispatchKeyEvent', {type, key, code: key === ' ' ? 'Space' : key, windowsVirtualKeyCode: KEYS[key], ...(type === 'keyDown' && (key === 'Enter' || key === ' ') ? {text: key === 'Enter' ? '\r' : ' '} : {})});
    await sleep(150);
  };
  // the focused element's name without its hidden icon, and its tree attributes
  const focused = () => page.eval("(()=>{const e=document.activeElement,c=e?.cloneNode(true);c?.querySelectorAll('[aria-hidden=true]').forEach(x=>x.remove());return {role:e?.getAttribute('role')||null,name:c?.textContent.replace(/\\s+/g,' ').trim()||null,tabindex:e?.getAttribute('tabindex'),selected:e?.getAttribute('aria-selected'),expanded:e?.getAttribute('aria-expanded')}})()");
  const checkTree = async (tag, names) => {
    const ax = await page.axTree(), trees = ax.filter(n => n.role === 'tree'), items = ax.filter(n => n.role === 'treeitem');
    const stops = await page.eval("document.querySelectorAll('#tree [role=treeitem][tabindex=\"0\"]').length");
    stage('tree ' + tag, {trees, items, stops});
    assert.deepEqual(trees.map(t => t.name), ['Model tree'], tag + ': one tree named Model tree');
    assert.equal(new Set(items.map(i => i.name)).size, items.length, tag + ': tree item names are unique');
    assert.ok(items.every(i => Number.isInteger(i.level) && i.level >= 1), tag + ': every tree item has a level');
    assert.ok(items.filter(i => i.selected === true).length <= 1, tag + ': at most one selected item');
    assert.equal(stops, 1, tag + ': one tab stop');
    for (const name of names) await page.treeItem(name);
    return items;
  };
  const mpNodes = ['Heated silicon waveguide', 'Component 1', 'Geometry 1', 'Materials', 'Silicon (core)', 'Heater', 'Silica (background)', 'Mesh 1 · shared', 'Physics',
    'solve order 1 Heat 1 · Heat transfer', 'solve order 2 Modes 1 · Optical modes', 'Couplings', 'Heat 1 temperature → Modes 1 temperature', 'Study', 'Study 1', 'Solve order (from couplings)'];
  const mpItems = await checkTree('multiphysics', mpNodes);
  assert.deepEqual(mpItems.map(i => [i.name, i.level]), mpNodes.map(n => [n, ['Heated silicon waveguide', 'Component 1', 'Physics', 'Couplings', 'Study'].includes(n) ? 1 : ['Silicon (core)', 'Heater', 'Silica (background)', 'Solve order (from couplings)'].includes(n) ? 3 : 2]));
  assert.deepEqual(mpItems.filter(i => i.selected === true).map(i => i.name), ['Heated silicon waveguide']);
  await page.on('function(s){const t=this.querySelector(s);const all=[...this.querySelectorAll("button,select,input,[tabindex]")].filter(e=>e.tabIndex>=0&&!e.disabled&&e.offsetParent&&(t.compareDocumentPosition(e)&Node.DOCUMENT_POSITION_PRECEDING));all.at(-1).focus();return true}', '#tree');
  await press('Tab'); let at = await focused(); stage('K9 multiphysics tab into the tree', at);
  assert.deepEqual([at.role, at.name, at.tabindex, at.selected], ['treeitem', 'Heated silicon waveguide', '0', 'true']);
  await press('ArrowDown'); assert.equal((await focused()).name, 'Component 1');
  await press('End'); assert.equal((await focused()).name, 'Solve order (from couplings)');
  await press('Home'); assert.equal((await focused()).name, 'Heated silicon waveguide');
  await press('ArrowDown'); await press('ArrowDown'); await press('Enter'); at = await focused();
  assert.deepEqual([at.name, at.selected], ['Geometry 1', 'true']);
  await press('ArrowDown'); await press(' '); at = await focused(); assert.deepEqual([at.name, at.selected], ['Materials', 'true']);
  assert.equal(await page.eval("document.querySelectorAll('#tree [aria-selected=true]').length"), 1);
  // Left from a node to its group, Left closes it, Down skips its hidden nodes, Right opens it and enters it
  await press('ArrowLeft'); at = await focused(); assert.deepEqual([at.name, at.expanded], ['Component 1', 'true']);
  await press('ArrowLeft'); assert.equal((await focused()).expanded, 'false');
  await press('ArrowDown'); assert.equal((await focused()).name, 'Physics', 'Down skips the nodes of a closed group');
  await press('ArrowUp'); await press('ArrowRight'); assert.equal((await focused()).expanded, 'true'); await press('ArrowRight'); assert.equal((await focused()).name, 'Geometry 1');
  // a node under another (level 3): Left goes to the node above it at level 2
  await press('ArrowDown'); await press('ArrowDown'); assert.equal((await focused()).name, 'Silicon (core)'); await press('ArrowLeft'); assert.equal((await focused()).name, 'Materials');
  await press('Home'); await press('Enter'); at = await focused(); assert.deepEqual([at.name, at.selected], ['Heated silicon waveguide', 'true']);
  await checkTree('multiphysics after keys', mpNodes);
  assert.equal(await page.text('#project'), 'Multiphysics model / No unsaved input changes');
  assert.equal(await page.eval("document.getElementById('run-optical').hidden&&document.getElementById('run-heat').hidden&&document.getElementById('run-joule').hidden"), true);
  stage('MB1 template', {tree: await page.text('#tree')});

  // MB2: Connections is drawn from the couplings: two nodes in order, one temperature wire
  await page.click('nav [data-page=Connections]');
  await page.until("document.querySelectorAll('.mp-stage .graph-wires path.temperature').length===1", 'one wire');
  assert.deepEqual(await page.eval("[...document.querySelectorAll('.mp-stage .graph-node-title')].map(e=>e.innerText.split('\\n')[0].trim())"), ['1Heat 1', '2Modes 1']);
  assert.equal(await page.eval("document.querySelector('.mp-stage .graph-wires path.temperature').dataset.coupling"), 'heat1_to_modes1');
  assert.equal(await page.text('#view-detail'), 'Drawn from the couplings');
  // the port dots are not dragged: a static cursor and a pointer to Add coupling
  assert.equal(await page.eval("getComputedStyle(document.querySelector('.mp-stage .graph-port')).cursor"), 'default');
  assert.match(await page.attr('.mp-stage .graph-port', 'title'), /To connect ports, use Add coupling…$/);
  // the wire starts at the temperature port's dot, on the node's right edge, not at heat flux
  const wire = await page.eval(`(()=>{const st=document.querySelector('.mp-stage').getBoundingClientRect(),dot=s=>{const r=document.querySelector(s+' .port-dot').getBoundingClientRect();return [r.x+r.width/2-st.x,r.y+r.height/2-st.y]};
    const start=document.querySelector('.mp-stage .graph-wires path.temperature').getAttribute('d').match(/^M ([-\\d.]+) ([-\\d.]+)/).slice(1).map(Number);
    return {start,temperature:dot('[data-port="heat1--output--temperature"]'),flux:dot('[data-port="heat1--output--heat_flux"]'),right:document.querySelector('[data-mp-node=heat1]').getBoundingClientRect().right-st.x}})()`);
  assert.ok(Math.hypot(wire.start[0] - wire.temperature[0], wire.start[1] - wire.temperature[1]) < 0.5, JSON.stringify(wire));
  assert.ok(Math.abs(wire.temperature[0] - wire.right) < 6, 'the temperature dot is on the node edge: ' + JSON.stringify(wire));
  assert.ok(Math.abs(wire.flux[1] - wire.temperature[1]) > 20, 'heat flux has its own row: ' + JSON.stringify(wire));
  stage('MB2 connections', wire);

  // MB3: remove the coupling, get the suggestion, add it back through the dialog; Undo/Redo
  await page.clickTreeItem('Heat 1 temperature → Modes 1 temperature');
  await page.until("/Remove coupling/.test(document.getElementById('inspector').innerText)", 'coupling settings');
  assert.match(await page.text('#inspector'), /Transfer Same mesh \(both use Mesh 1\).*each triangle gets the mean of its 3 nodes/);
  // the names the file uses are under a closed File details: the same rows, collapsed
  const fileDetails = () => page.eval("[...document.querySelectorAll('#inspector details.mp-file-details')].map(d=>({open:d.open,summary:d.querySelector('summary').textContent,rows:[...d.querySelectorAll('.pair')].map(p=>p.textContent)}))");
  assert.deepEqual(await fileDetails(), [{open: false, summary: 'File details', rows: ['Input takesone source', 'Name in fileheat1_to_modes1']}]);
  assert.doesNotMatch(await page.text('#inspector'), /heat1_to_modes1|Input takes/);
  await page.clickTreeItem('solve order 1 Heat 1 · Heat transfer'); await page.until("/Heat source per region/.test(document.getElementById('inspector').innerText)", 'physics settings');
  assert.deepEqual(await fileDetails(), [{open: false, summary: 'File details', rows: ['Typethermal.steady2d', 'Name in fileheat1']}]);
  assert.doesNotMatch(await page.text('#inspector'), /thermal\.steady2d|Name in file/);
  await page.clickTreeItem('Heated silicon waveguide'); await page.until("!!document.querySelector('[data-mp-text]')", 'model settings');
  assert.deepEqual(await fileDetails(), [{open: false, summary: 'File details', rows: ['FormatMultiphysics model · 0.3/multiphysics.1']}]);
  assert.doesNotMatch(await page.text('#inspector'), /0\.3\/multiphysics\.1/);
  await page.clickTreeItem('Heat 1 temperature → Modes 1 temperature'); await page.until("!!document.querySelector('[data-mp-remove-coupling]')", 'coupling settings back');
  await page.click('[data-mp-remove-coupling]');
  await page.until("/Modes 1 can take its temperature from Heat 1/.test(document.getElementById('mp-messages').innerText)", 'suggestion');
  await runReady();          // two physics without a coupling still run; nothing is coupled silently
  // the input without a source is a warning in Messages, the tree and the node; the removal offers Undo
  const unsourced = 'Temperature input has no source: uses n₀ at T_ref (300 K)';
  assert.equal(await page.text('#mp-messages [data-mp-warning="modes1"] p'), 'Modes 1: ' + unsourced + '.');
  assert.equal(await page.attr('#tree [data-mp-node="physics:modes1"] .warn-badge', 'title'), unsourced);
  assert.equal(await page.text('.mp-stage [data-mp-warning="modes1"]'), '! ' + unsourced);
  assert.equal(await page.text('#view-detail'), '2 physics · no couplings');
  // the heater-off option stays where it was, disabled, and says why
  assert.equal(await page.eval("!document.getElementById('run-baseline-option').hidden&&document.getElementById('run-baseline').disabled&&!document.getElementById('run-baseline').checked"), true);
  assert.equal(await page.text('#run-baseline-option'), 'Also solve without heater needs a temperature coupling');
  assert.equal(await page.axName('#run-baseline'), 'Also solve without heater needs a temperature coupling', 'the reason is read with the option');
  assert.equal(await page.text('#mp-messages [data-mp-removal] p'), 'Coupling Heat 1 temperature → Modes 1 temperature removed.');
  assert.match(await page.text('#file-status'), /removed\. Undo restores it\./);
  await page.click('#mp-messages [data-mp-undo]');
  await page.until("!!document.querySelector('#tree [data-mp-node=\"coupling:heat1_to_modes1\"]')&&!document.querySelector('#tree .warn-badge')", 'removal undone');
  // the heater-off option comes back ticked, and Messages says so
  assert.match(await page.text('#file-status'), /“Also solve without heater” is ticked again\.$/);
  assert.equal(await page.eval("document.getElementById('run-baseline').checked"), true);
  await page.clickTreeItem('Heat 1 temperature → Modes 1 temperature');
  await page.until("!!document.querySelector('[data-mp-remove-coupling]')", 'coupling settings again');
  await page.click('[data-mp-remove-coupling]');
  await page.until("!!document.querySelector('#mp-messages [data-mp-add-coupling]')", 'suggestion again');
  await page.click('#mp-messages [data-mp-add-coupling]');
  await page.until("!!document.querySelector('dialog.mp-dialog #mp-to')", 'coupling dialog');
  assert.equal(await page.eval("document.querySelector('#mp-from').value"), 'heat1.temperature');
  assert.equal(await page.eval("[...document.querySelectorAll('#mp-from option')].find(o=>o.value==='modes1.effective_index').disabled"), true);
  assert.equal(await page.eval("[...document.querySelectorAll('#mp-from option')].find(o=>o.value==='modes1.effective_index').textContent"), 'Modes 1 effective index (single numbers, not a map)');
  assert.match(await page.text('dialog.mp-dialog'), /each triangle gets the mean of its 3 nodes/);
  await page.click('#mp-coupling-add');
  await page.until("!!document.querySelector('#tree [data-mp-node=\"coupling:heat1_to_modes1\"]')&&!document.querySelector('dialog[open]')", 'coupling added');
  assert.match(await page.text('#file-status'), /added\..*“Also solve without heater” is ticked again\.$/);
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
  // the engine's n_eff of a document: the coupled run, or the optical model alone (format 0.3)
  const engineNeff = tree => {
    const done = spawnSync(args.python, ['-I', '-c', 'import json,sys\nfrom simcase import Document, multiphysics, run\nd=Document.from_dict(json.loads(sys.stdin.read()))\nr=multiphysics.run(d,verbose=False).results["modes1"] if d["openphysics"]==multiphysics.ENVELOPE else run(d,verbose=False)\nprint(repr(float(r.effective_index[0][0])))'],
      {input: JSON.stringify(tree), encoding: 'utf8'});
    assert.equal(done.status, 0, done.stderr);
    return done.stdout.trim();
  };
  const uncoupledOf = tree => page.on('function(t){return import("/workspace-assets/workspace-multiphysics.mjs").then(m=>m.uncoupledDocument(t,"modes1"))}', tree);
  await page.click('#run-multiphysics');
  await page.until("!!document.querySelector('[data-neff=\"1\"]')", 'result', 120000);
  assert.match(await page.text('#sequence'), /Heat 1 · Done in [0-9.]+ s.*Modes 1 · Done in [0-9.]+ s/);
  // Also solve without heater: the heater-off column follows by itself
  await page.until("/^[+−]0\\.\\d{8}$/.test(document.querySelector('[data-neff-shift=\"1\"]')?.textContent||'')", 'heater-off column', 120000);
  assert.equal(await page.text('.mp-neff thead'), 'Mode n_eff (coupled) Polarization Absorption loss (dB/cm) A_eff (µm²) n_eff without heater Δn_eff (coupled − without heater)');
  // A_eff of each mode in µm², the engine's value from this run
  const areas = await page.eval("[...document.querySelectorAll('.mp-neff [data-area]')].map(e=>({text:e.textContent,value:Number(e.dataset.areaValue)}))");
  stage('multiphysics A_eff', {areas}); assert.equal(areas.length, 2);
  for (const a of areas) { assert.match(a.text, /^\d\.\d{4}$/); assert.equal(a.text, (a.value * 1e12).toPrecision(4)); }
  assert.match(await page.text('[data-mp-area-note]'), /^A_eff: Effective area \(∫\|E\|²\)²\/∫\|E\|⁴ over the window, all three field components; computed by the engine from the saved field\.$/);
  // the rows are modes, with the engine's polarization, lossless, the ranking sentence and the mode count the model asks for
  // the template asks for two modes: TE-like first, then TM-like, whose cell names its TM share first
  assert.deepEqual(await page.eval("[...document.querySelectorAll('.mp-neff tbody tr')].map(r=>r.cells[0].textContent)"), ['Mode 1', 'Mode 2']);
  assert.match(await page.text('[data-polarization="1"]'), /^TE-like · \d+\.\d % TE$/);
  assert.match(await page.text('[data-polarization="2"]'), /^TM-like · (\d+\.\d) % TM \((\d+\.\d) % TE\)$/);
  // round 9 (J8): the template is lossless, its n_eff real: each mode reads 0 dB/cm, absorption only
  assert.equal(await page.text('[data-loss="1"]'), '0 dB/cm'); assert.equal(await page.text('[data-loss="2"]'), '0 dB/cm');
  assert.equal(await page.text('[data-mp-lossless]'), 'Absorption loss counts material absorption (k) only: all materials have k = 0 at this wavelength, so it is 0 dB/cm. Leakage and radiation are not computed in a closed window.');
  // round 10 (K2): every loss cell and the header give the absorption-only help
  const absorptionHelp = 'Absorption (material k) only; leakage and radiation are not computed in a closed window';
  assert.equal(await page.attr('[data-loss="1"]', 'title'), absorptionHelp); assert.equal(await page.attr('[data-loss="2"]', 'title'), absorptionHelp);
  assert.equal(await page.eval("[...document.querySelectorAll('.mp-neff thead th')].find(t=>/^Absorption loss/.test(t.textContent)).title"), absorptionHelp);
  assert.doesNotMatch(await page.eval('document.body.innerText'), /not matched between runs|(?:matched|compared) by rank/i);
  assert.equal(await page.text('#mp-candidate-note'), 'Modes are ranked by effective index. This model asks for 2 modes: Modes 1 › Modes to find');
  assert.equal(await page.text('#mp-baseline-note'), 'without heater = Modes 1 alone with no temperature input: every material keeps n₀, its index at T_ref = 300 K.');
  const shown = await page.attr('[data-neff="1"]', 'data-neff-value');
  const documentSent = JSON.parse(await page.eval("fetch('/api/multiphysics/template').then(r=>r.text())"));
  documentSent.materials.heater.thermo_optic_coefficient = '1.0e-5 1/K';
  documentSent.materials.heater.source += '; thermo-optic data copied from physmat:SiO2 (physmat)';
  const engine = engineNeff(documentSent), engineAlone = engineNeff(await uncoupledOf(documentSent));
  assert.equal(shown, engine, 'the coupled n_eff is the engine run of the same document');
  assert.equal(await page.attr('[data-neff-alone="1"]', 'data-neff-value'), engineAlone, 'the heater-off n_eff is the engine run of the optical model alone');
  const d = Number(engine) - Number(engineAlone), shiftShown = await page.text('[data-neff-shift="1"]');
  assert.equal(shiftShown, (d < 0 ? '−' : '+') + Math.abs(d).toFixed(8), 'Δn_eff is the difference of the two engine runs');
  assert.equal(await page.text('.dock-title>span'), 'Run 1 · solved from the current model');
  // round 10 (K6): on Results the tree marks the results page shown, not Study
  const onResults = await page.eval("({page:[...document.querySelectorAll('nav [data-page]')].filter(b=>b.getAttribute('aria-pressed')==='true').map(b=>b.dataset.page),selected:[...document.querySelectorAll('#tree [aria-selected=true]')].map(e=>e.dataset.mpNode)})");
  stage('K6 tree on Results', onResults); assert.deepEqual(onResults.page, ['Results']);
  assert.equal(onResults.selected.length, 1); assert.match(onResults.selected[0], /^results:/);
  assert.deepEqual((await page.axTree()).filter(n => n.role === 'treeitem' && n.name === 'Study 1').map(n => n.selected), [false]);
  // the answer first: the n_eff table above the maps, whole on a 1440 × 900 screen
  const answer = await page.eval("({first:!!(document.querySelector('.mp-neff').compareDocumentPosition(document.querySelector('.mp-maps'))&Node.DOCUMENT_POSITION_FOLLOWING),bottom:document.querySelector('.mp-neff').getBoundingClientRect().bottom})");
  assert.ok(answer.first && answer.bottom <= 900, JSON.stringify(answer));
  stage('MB5 run', {coupled_neff: shown, engine_neff: engine, without_heater_neff: engineAlone, shift: shiftShown});
  await page.clickTreeItem('Coupling check');
  await page.until("/Coupling check/.test(document.getElementById('canvas').innerText)", 'coupling check');
  assert.match(await page.text('.mp-check tbody'), /node temperatures, 300\.0–[0-9.]+ K .*triangle means \(mean of 3 nodes\) Passed · max \|received − sent\| = 0 K/);

  // MB6: an edit marks the run out of date; the same model again is current, and a second Run
  // keeps the heater-off column valid (same content) without solving it again
  await page.click('nav [data-page=Connections]');
  await page.clickTreeItem('Heat 1 temperature → Modes 1 temperature');
  await page.until("!!document.querySelector('[data-mp-remove-coupling]')", 'coupling settings after the run');
  await page.click('[data-mp-remove-coupling]');
  await page.until("/Out of date/.test(document.getElementById('sequence').innerText)", 'out of date');
  // per step: the heat inputs did not change, so only the optical modes are out of date
  assert.match(await page.text('#sequence'), /^1 Heat 1 · Done in [0-9.]+ s 2 Modes 1 · Out of date \(last run: Done in [0-9.]+ s\)$/);
  assert.match(await page.text('.mp-stage [data-mp-node="heat1"] .mp-state'), /^Done in/);
  assert.equal(await page.text('.dock-title>span'), 'Run 1 · the model changed since; press Run to update');
  await page.until("document.getElementById('status').textContent==='Model edited since run 1 · press Run to update'", 'footer out of date');
  assert.match(await page.text('.mp-stage [data-mp-node="modes1"] .mp-state'), /^Out of date/);
  assert.equal(await page.text('#mp-messages [data-mp-warning="modes1"] p'), 'Modes 1: ' + unsourced + '.');
  await page.click('#mp-messages [data-mp-add-coupling]');
  await page.until("!!document.querySelector('dialog.mp-dialog #mp-to')", 'coupling dialog after the run');
  await page.click('#mp-coupling-add');
  await page.until("!document.querySelector('dialog[open]')&&!/Out of date/.test(document.getElementById('sequence').innerText)", 'same model again');
  await runReady();
  // one sentence in Messages, the dock heading and the status bar; the notice asks for no Run
  const again = 'Model matches run 1 again: its results are current. Run makes a new run with the same inputs';
  assert.equal(await page.text('#file-status'), 'Coupling Heat 1 temperature → Modes 1 temperature added. ' + again + '. “Also solve without heater” is ticked again.');
  assert.equal(await page.text('#status'), again);
  assert.equal(await page.text('.dock-title>span'), again);
  assert.equal(await page.text('#run-baseline-option'), 'Also solve without heater ~1 s');
  await page.click('#run-multiphysics');
  await page.until("/^Run 2 complete/.test(document.getElementById('file-status').textContent)", 'second run', 120000);
  // the kept column has the same content, so no heater-off solve follows
  assert.equal(await page.text('#file-status'), 'Run 2 complete. Its results belong to that run; editing the model does not change them.');
  await page.until("!!document.querySelector('[data-neff-shift=\"1\"]')", 'results of run 2');
  assert.equal(await page.text('#mp-baseline-note'), 'without heater = Modes 1 alone with no temperature input: every material keeps n₀, its index at T_ref = 300 K.');
  assert.equal(await page.text('[data-neff-shift="1"]'), shiftShown);
  assert.equal(await page.exists('#mp-run-alone'), false, 'a valid column needs no refresh');
  assert.doesNotMatch(await page.text('#canvas'), /different optical model|earlier model/);
  assert.equal(await page.text('#status'), 'Run 2 matches the model · press Run to solve again');
  stage('MB6 out of date, then the same model again');

  // MB6b: the template as shipped: Δn_eff of the heater, exactly the engine's
  await page.click('nav [data-page=Applications]');
  await page.until("!!document.querySelector('[data-template=heated-waveguide]')", 'start page again');
  // the cards line up: one row, the same header heights and title tops, all above the fold at 1440 × 900
  const cards = await page.eval("[...document.querySelectorAll('.cards button')].map(b=>{const r=b.getBoundingClientRect(),t=b.querySelector('strong').getBoundingClientRect();return {top:Math.round(r.top),bottom:Math.round(r.bottom),title:Math.round(t.top)}})");
  assert.equal(new Set(cards.map(c => c.top)).size, 1, JSON.stringify(cards));
  assert.equal(new Set(cards.map(c => c.title)).size, 1, JSON.stringify(cards));
  assert.ok(cards.every(c => c.top < 900), JSON.stringify(cards));
  await page.screenshot('mb6b-start-page');
  // runs 1 and 2 are in no session file: opening the template again asks first
  await page.click('[data-template=heated-waveguide]');
  await page.until("document.getElementById('leave-confirm').open", 'leave confirmation');
  assert.equal(await page.text('#leave-confirm-title'), 'Leave this model?');
  assert.equal(await page.text('#leave-confirm-description'), '2 runs are only in this tab and in browser recovery. Save session first to keep them in a file.');
  assert.deepEqual(await page.eval("[...document.querySelectorAll('#leave-confirm button')].filter(b=>!b.hidden).map(b=>b.textContent)"), ['Cancel', 'Save session', 'Leave']);
  await page.screenshot('mb6b-leave-confirm');
  await page.click('#leave-stay');
  await page.until("!document.getElementById('leave-confirm').open&&document.getElementById('file-status').textContent==='Kept the current model and its runs.'", 'kept');
  assert.equal(await page.exists('[data-mp-node="results:check"]'), true, 'run 2 is still there');
  await page.click('[data-template=heated-waveguide]');
  await page.until("document.getElementById('leave-confirm').open", 'leave confirmation again');
  await page.click('#leave-go');
  await page.until("/^Heated silicon waveguide ready\\./.test(document.getElementById('file-status').textContent)", 'template opened again');
  await runReady();
  assert.equal(await page.text('.dock-title>span'), 'Nothing is computed until you press Run');
  await page.click('#run-multiphysics');
  await page.until("/^[+−]0\\.\\d{8}$/.test(document.querySelector('[data-neff-shift=\"1\"]')?.textContent||'')", 'template heater-off column', 120000);
  const template = JSON.parse(await page.eval("fetch('/api/multiphysics/template').then(r=>r.text())"));
  const tCoupled = engineNeff(template), tAlone = engineNeff(await uncoupledOf(template)), td = Number(tCoupled) - Number(tAlone);
  const tShift = await page.text('[data-neff-shift="1"]');
  assert.equal(await page.attr('[data-neff="1"]', 'data-neff-value'), tCoupled);
  assert.equal(await page.attr('[data-neff-alone="1"]', 'data-neff-value'), tAlone);
  assert.equal(tShift, (td < 0 ? '−' : '+') + Math.abs(td).toFixed(8));
  await page.screenshot('mb6b-template-results');
  stage('MB6b template Δn_eff', {coupled: tCoupled, without_heater: tAlone, shift: tShift});

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
  // the template's run lives only in this tab: the open asks first
  await page.until("document.getElementById('leave-confirm').open", 'leave confirmation before an open');
  assert.equal(await page.text('#leave-confirm-description'), '1 run is only in this tab and in browser recovery. Save session first to keep it in a file.');
  await page.click('#leave-go');
  await page.until("/Open failed: .*appears more than once/.test(document.getElementById('file-status').textContent)", 'duplicate key refused');
  assert.match(await page.text('#project'), /^Multiphysics model \/ Not saved to a file · (kept for recovery in this browser|updating browser recovery)$/);
  // the checkout's example, found from this script: the check runs outside the checkout
  await setFile(fileURLToPath(new URL('../../examples/simcase/multiphysics_heated_slab.json', import.meta.url)));
  await page.until("document.getElementById('leave-confirm').open", 'leave confirmation: the refused open kept the run');
  await page.click('#leave-go');
  await page.until("!!document.querySelector('#tree [data-mp-node=\"coupling:heat_to_optics\"]')", 'example opened');
  await runReady();
  assert.equal(await page.text('#project'), 'Multiphysics model / Opened multiphysics_heated_slab.json');
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

  // MB8: leaving for a single-physics model puts the session commands and the menu back
  await size(1440, 900);
  await page.click('nav [data-page=Applications]');
  await page.until("!!document.querySelector('[data-template=optical]')", 'start page before leaving');
  await page.click('[data-template=optical]');
  await page.until("!document.getElementById('open-session').hidden&&!document.getElementById('save-session').hidden", 'session commands back');
  assert.deepEqual(await page.eval("[...document.querySelector('.file-menu-items').children].slice(0,3).map(b=>b.id+':'+b.textContent+':'+!b.hidden)"),
    ['save-project:Save inputs only:true', 'open-project:Open inputs file:true', 'save-draft:Save browser draft:true']);
  assert.match(await page.attr('#save-project', 'aria-description'), /^Saves the model inputs only/);
  assert.equal(await page.eval("document.getElementById('run-baseline-option').hidden&&document.getElementById('run-multiphysics').hidden"), true);
  assert.equal(await page.text('.dock-title>span'), 'Nothing is computed until you press Run');
  stage('MB8 back to a single-physics model');

  // MB9: optical runs in no session file: opening the heated model names them and offers Save
  // session; they stay in this tab and come back with the optical model
  await page.until("!document.getElementById('run-optical').disabled", 'optical Run', 60000);
  await page.click('#run-optical');
  await page.until("/complete/i.test(document.getElementById('job-message').textContent)&&document.getElementById('run-optical').textContent==='Run optical study'", 'optical run', 120000);
  await page.click('nav [data-page=Applications]');
  await page.click('[data-template=heated-waveguide]');
  await page.until("document.getElementById('leave-confirm').open", 'optical leave confirmation');
  assert.equal(await page.text('#leave-confirm-title'), 'Open Heated silicon waveguide?');
  assert.equal(await page.text('#leave-confirm-description'), '1 optical run is in no file. It stays in this tab while Heated silicon waveguide is open and comes back with the optical model, but closing the tab can lose it. Save session keeps it in a file.');
  assert.equal(await page.text('#leave-save'), 'Save session, then continue');
  await page.click('#leave-go');
  await page.until("!!document.querySelector('#tree [data-mp-node=\"physics:heat1\"]')", 'heated model after the optical run');
  stage('MB9 optical runs named before leaving');

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
