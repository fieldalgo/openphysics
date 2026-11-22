// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Real-browser check of multiphysics session files (version 8): Save session and Open session in
// every model, a multiphysics model saved with its runs and opened again, the run list with names
// and pins, browser recovery, the 16 MiB limit and the refusals of a damaged or newer file. The
// checks S1, S2 and S5-S8 and S10 of docs/packages/simcase/workspace.md ("Session files"): every
// stored array is compared as Float64 bytes with the server's own reply for the run, fetched
// separately (in Node and again in Python), and a file saved again after an open is
// byte-identical. Any page exception or console.error fails the check.
// Drives a preinstalled Chrome through the DevTools protocol with Node's built-in fetch and
// WebSocket; no npm package and no browser download. Fails, never skips, when no browser is found.
//
//   node tools/studio_browser/studio_multiphysics_session_browser.mjs --python <python> --output <dir> [--chrome <path>]
import assert from 'node:assert/strict';
import {readdir, readFile, rename} from 'node:fs/promises';
import {basename} from 'node:path';
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
const stage = (name, data = {}) => { report.stages.push({name, ...data}); console.log('[session browser]', name, JSON.stringify(data)); };

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
  // the accessible name Chrome computes, as a screen reader gets it
  async axName(selector) {
    const {root} = await this.call('DOM.getDocument');
    const {nodeId} = await this.call('DOM.querySelector', {nodeId: root.nodeId, selector});
    const {nodes} = await this.call('Accessibility.getPartialAXTree', {nodeId, fetchRelatives: false});
    return nodes[0]?.name?.value ?? null;
  }
  async screenshot(name) { const png = await this.call('Page.captureScreenshot', {format: 'png', captureBeyondViewport: true}); await writeFile(join(out, name + '.png'), Buffer.from(png.data, 'base64')); }
}

let diagnose = async () => null;
const profile = await mkdtemp(join(tmpdir(), 'openphysics-session-browser-'));
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
  const notice = () => page.text('#file-status');
  diagnose = () => page.eval("({notice:document.getElementById('file-status').textContent,dock:document.querySelector('.dock-title>span')?.textContent,status:document.getElementById('status').textContent,saved:document.getElementById('autosave-status').textContent,dialogs:[...document.querySelectorAll('dialog[open]')].map(d=>d.id||d.className),reason:document.getElementById('run-multiphysics-reason')?.textContent})");
  const clearNotice = () => page.eval("document.getElementById('file-status').textContent=''");
  await size(1440, 900);
  const downloads = join(out, 'downloads');
  await mkdir(downloads, {recursive: true});
  await page.call('Page.setDownloadBehavior', {behavior: 'allow', downloadPath: downloads});
  const listed = async () => new Set(await readdir(downloads));
  await mkdir(join(out, 'saved'), {recursive: true});
  let savedCount = 0;
  // the next file the page sends to the browser's downloads
  async function nextDownload(before, label) {
    const end = Date.now() + 60000;
    while (Date.now() < end) {
      // the session file only: Chrome on Windows can leave other files there (downloads.htm)
      const fresh = [...await listed()].filter(f => !before.has(f) && f.endsWith('.json'));
      if (fresh.length) {
        const path = join(downloads, fresh[0]);
        let text = '', last = -1;
        for (let i = 0; i < 40; i++) { text = await readFile(path, 'utf8'); if (text.length === last && text.length) break; last = text.length; await sleep(150); }
        // kept under a name of its own: the next file of the same minute has the same name
        const kept = join(out, 'saved', String(++savedCount).padStart(2, '0') + '-' + fresh[0]);
        await rename(path, kept);
        return {path: kept, name: fresh[0], text};
      }
      await sleep(150);
    }
    throw new Error('no download: ' + label);
  }
  async function saveSession(label) {
    const before = await listed(); await clearNotice(); await page.click('#save-session');
    const file = await nextDownload(before, label);
    await page.until("/^Session file .* sent to the browser's downloads/.test(document.getElementById('file-status').textContent)", 'save notice ' + label);
    return file;
  }
  const setFile = async (selector, path) => {
    const {root} = await page.call('DOM.getDocument');
    const {nodeId} = await page.call('DOM.querySelector', {nodeId: root.nodeId, selector});
    await page.call('DOM.setFileInputFiles', {nodeId, files: [path]});
  };
  // Open session with a file: answers the leave and open questions, then waits for the notice
  async function openSession(path, {expectFailure = false} = {}) {
    await clearNotice(); await setFile('#session-file', path);
    const end = Date.now() + 60000;
    while (Date.now() < end) {
      const state = await page.eval("({leave:document.getElementById('leave-confirm').open,load:document.getElementById('load-confirm').open,notice:document.getElementById('file-status').textContent})");
      if (state.leave) await page.click('#leave-go');
      else if (state.load) await page.click('#confirm-load');
      else if (/^Session open failed: /.test(state.notice)) { if (!expectFailure) throw new Error(state.notice); return state.notice; }
      else if (/^Opened /.test(state.notice)) { if (expectFailure) throw new Error('opened: ' + state.notice); return state.notice; }
      await sleep(150);
    }
    throw new Error('open did not finish: ' + path);
  }
  const replies = new Map();
  // the server's reply for a job, as raw text: fetched separately from the page's own copy
  async function fetchReplies(sessionText) {
    const session = JSON.parse(sessionText);
    for (const job of [...session.runs.map(r => r.job), ...Object.values(session.baselines).map(b => b.job)])
      if (!replies.has(job)) replies.set(job, await page.on('function(j){return fetch("/api/multiphysics/jobs/"+j+"/result").then(r=>{if(!r.ok)throw Error("no reply "+j);return r.text()})}', job));
    for (const [job, text] of replies) await writeFile(join(out, 'replies', job + '.json'), text, 'utf8');
  }
  await mkdir(join(out, 'replies'), {recursive: true});
  // S1: every stored array against the server's reply, as Float64 bytes (Node's JSON.parse)
  const ARRAYS = [['mesh', 'node_coordinates'], ['mesh', 'triangles'], ['mesh', 'regions'], ['physics', 'heat1', 'temperature', 'values'],
    ['physics', 'modes1', 'coupled', 'temperature', 'values'], ['physics', 'modes1', 'coupled', 'refractive_index', 'n'], ['physics', 'modes1', 'coupled', 'refractive_index', 'k'],
    ['physics', 'modes1', 'coupled', 'index_change'], ['physics', 'modes1', 'effective_index', 'values']];
  const bytesOf = value => value === null ? 'null' : Buffer.from(new Float64Array([value].flat(Infinity)).buffer).toString('hex');
  function compareArrays(sessionText, {valuesOnly = []} = {}) {
    const session = JSON.parse(sessionText);
    let arrays = 0, values = 0;
    for (const run of session.runs) {
      const reply = JSON.parse(replies.get(run.job));
      const residuals = r => (r.loops || []).map(l => l.residuals.map(x => x.value));
      assert.equal(bytesOf(residuals(run.result)), bytesOf(residuals(reply)), `run ${run.number} loop residuals`);
      for (const path of ARRAYS) {
        // a run whose maps were not kept holds n_eff and the loop residuals of its arrays
        if (run.maps === 'not kept' && path.join('.') !== 'physics.modes1.effective_index.values') continue;
        const get = o => path.reduce((x, k) => x?.[k], o), stored = get(run.result), sent = get(reply);
        if (sent === undefined) continue;
        assert.equal(bytesOf(stored), bytesOf(sent), `run ${run.number} ${path.join('.')}`); arrays++; values += sent === null ? 0 : [sent].flat(Infinity).length;
      }
      if (valuesOnly.includes(run.number)) assert.equal(run.maps, 'not kept');
    }
    for (const [name, b] of Object.entries(session.baselines)) {
      const reply = JSON.parse(replies.get(b.job));
      assert.equal(bytesOf(b.result.effective_index.values), bytesOf(reply.physics[name].effective_index.values), 'baseline ' + name); arrays++; values++;
    }
    return {arrays, values};
  }
  // the same comparison in Python: json.loads and float.hex, independent of the browser and Node
  function comparePython(sessionPath) {
    const code = `import json,sys,os
s=json.load(open(sys.argv[1],encoding='utf-8'));d=sys.argv[2];n=0
def flat(x): return [v for i in x for v in flat(i)] if isinstance(x,list) else [x]
def hexes(x): return None if x is None else [float(v).hex() for v in flat(x)]
paths=[p.split('.') for p in sys.argv[3].split(',')]
for run in s['runs']:
  reply=json.load(open(os.path.join(d,run['job']+'.json'),encoding='utf-8'))
  for p in paths:
    def get(o):
      for k in p: o=o.get(k) if isinstance(o,dict) else None
      return o
    sent,stored=get(reply),get(run['result'])
    if sent is None and stored is None: continue
    if run['maps']=='not kept' and p!=['physics','modes1','effective_index','values']: continue
    assert hexes(sent)==hexes(stored),(run['number'],p);n+=1
for name,b in s['baselines'].items():
  reply=json.load(open(os.path.join(d,b['job']+'.json'),encoding='utf-8'))
  assert hexes(b['result']['effective_index']['values'])==hexes(reply['physics'][name]['effective_index']['values']);n+=1
print(n)`;
    const done = spawnSync(args.python, ['-I', '-c', code, sessionPath, join(out, 'replies'), ARRAYS.map(p => p.join('.')).join(',')], {encoding: 'utf8'});
    assert.equal(done.status, 0, done.stderr);
    return Number(done.stdout.trim());
  }
  const shown = () => page.eval("['[data-neff=\"1\"]','[data-neff-alone=\"1\"]','[data-neff-shift=\"1\"]'].map(s=>document.querySelector(s)?.textContent??null)");
  const runAndWait = async number => {
    await runReady(); await clearNotice(); await page.click('#run-multiphysics');
    await page.until(`/^Run ${number} · /.test(document.querySelector('.dock-title>span').textContent)`, 'run ' + number, 180000);
    await runReady();     // the without-heater solve that may follow is done too
  };
  // the template card: waits for the template's own notice (another model has the same tree)
  const openTemplate = async (on = page) => {
    await on.eval("document.getElementById('file-status').textContent=''");
    await on.click('[data-template=heated-waveguide]');
    const end = Date.now() + 60000;
    while (Date.now() < end) {
      if (await on.eval("document.getElementById('leave-confirm').open")) await on.click('#leave-go');
      if (await on.eval("/^Heated silicon waveguide ready\\./.test(document.getElementById('file-status').textContent)")) return;
      await sleep(150);
    }
    throw new Error('template not opened');
  };
  const workspace = () => page.eval("({tree:document.getElementById('tree').innerText,project:document.getElementById('project').textContent,undo:document.getElementById('undo-edit').disabled,redo:document.getElementById('redo-edit').disabled})");
  const template = JSON.parse(await (await fetch(base + '/api/multiphysics/template')).text());
  const variant = (size, near) => { const d = structuredClone(template); d.mesh.element_size = size; for (const c of d.mesh.controls) { c.near = near; c.far = size; } return d; };
  const openInputs = async (name, doc) => {
    const path = join(out, name); await writeFile(path, JSON.stringify(doc, null, 2), 'utf8');
    await clearNotice(); await setFile('#project-file', path);
    const end = Date.now() + 60000;
    while (Date.now() < end) {
      if (await page.eval("document.getElementById('leave-confirm').open")) await page.click('#leave-go');
      if (/ ready\. Edit settings/.test(await notice())) return;
      await sleep(150);
    }
    throw new Error('inputs file not opened: ' + name);
  };

  // S10: one Open session and one Save session in every model, the inputs file in More, no
  // "Runs stay in this tab", no horizontal overflow, at 1440 x 900 and 390 x 844
  await page.call('Page.navigate', {url: base + '/workspace'});
  await page.until("!!document.querySelector('[data-template=heated-waveguide]')", 'start page');
  const words = {};
  for (const [width, height, tag, mobile] of [[1440, 900, 'wide', false], [390, 844, 'phone', true]]) {
    await size(width, height, mobile); await sleep(300);
    for (const card of ['optical', 'heat', 'joule', 'heated-waveguide']) {
      await page.click('nav [data-page=Applications]');
      await page.until(`!!document.querySelector('[data-template="${card}"]')`, 'card ' + card);
      await page.click(`[data-template="${card}"]`);
      if (await page.eval("document.getElementById('leave-confirm').open")) await page.click('#leave-go');
      await page.until(card === 'heated-waveguide' ? "!!document.querySelector('#tree [data-mp-node=\"physics:heat1\"]')" : "!document.querySelector('[data-template]')", 'model ' + card);
      await sleep(300);
      const seen = await page.eval(`(()=>{const visible=b=>!b.hidden&&getComputedStyle(b).display!=='none'&&b.getClientRects().length>0;
        const all=[...document.querySelectorAll('button')].filter(visible).map(b=>b.innerText.trim());
        const group=[...document.getElementById('open-session').parentElement.children].filter(b=>b.tagName==='BUTTON'&&visible(b)).map(b=>b.innerText.trim());
        const menu=[...document.querySelector('.file-menu-items').children].filter(b=>!b.hidden).map(b=>b.textContent.trim());
        return {open:all.filter(t=>t==='Open session').length,save:all.filter(t=>t==='Save session').length,first:group.slice(0,2),menu:menu.slice(0,2),
          stay:/runs stay in this tab/i.test(document.body.innerText+document.body.textContent),overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth}})()`);
      words[`${tag}-${card}`] = seen;
      assert.deepEqual([seen.open, seen.save, seen.first, seen.menu, seen.stay, seen.overflow], [1, 1, ['Open session', 'Save session'], ['Save inputs only', 'Open inputs file'], false, 0], `${tag} ${card}: ${JSON.stringify(seen)}`);
      await page.screenshot(`s10-${tag}-${card}`);
    }
  }
  await size(1440, 900); await sleep(300);
  stage('S10 words', words);

  // a coupling added and undone leaves no selection the file could not hold: the file reopens
  await page.click('#tree [data-mp-node="coupling:heat1_to_modes1"]');
  await page.until("!!document.querySelector('[data-mp-remove-coupling]')", 'coupling settings');
  await page.click('[data-mp-remove-coupling]');
  await page.until("!!document.querySelector('#mp-messages [data-mp-add-coupling]')", 'suggestion');
  await page.click('#mp-messages [data-mp-add-coupling]');
  await page.until("!!document.querySelector('dialog.mp-dialog #mp-to')", 'coupling dialog');
  await page.click('#mp-coupling-add');
  await page.until("!document.querySelector('dialog[open]')&&!!document.querySelector('#tree [data-mp-node=\"coupling:heat1_to_modes1\"]')", 'coupling added');
  await page.click('#undo-edit');
  await page.until("!document.querySelector('#tree [data-mp-node=\"coupling:heat1_to_modes1\"]')", 'undone');
  const undone = await saveSession('after undo');
  assert.equal(JSON.parse(undone.text).view.selection, 'model');
  await openSession(undone.path);
  await page.click('nav [data-page=Applications]');
  await openTemplate();
  stage('selection after Undo', {selection: JSON.parse(undone.text).view.selection});

  // S1 and S2, the template: run, save, open, save again
  await runAndWait(1);
  await page.until("/^[+−]0\\.\\d{8}$/.test(document.querySelector('[data-neff-shift=\"1\"]')?.textContent||'')", 'heater-off column', 180000);
  await runReady();
  const before = await shown();
  // the values shown are the installed engine's runs of the template and of its optical model
  // alone (the mesh, and so n_eff, depends on the installed mesher: 2.44565013 / 2.44349927 /
  // +0.00215086 with one, 2.44556247 / 2.44341167 / +0.00215081 on the Linux and Windows runners,
  // 2.44564247 / 2.44349160 / +0.00215087 on the macOS runner)
  const engineNeff = tree => {
    const done = spawnSync(args.python, ['-I', '-c', 'import json,sys\nfrom simcase import Document, multiphysics, run\nd=Document.from_dict(json.loads(sys.stdin.read()))\nr=multiphysics.run(d,verbose=False).results["modes1"] if d["openphysics"]==multiphysics.ENVELOPE else run(d,verbose=False)\nprint(repr(float(r.effective_index[0][0])))'],
      {input: JSON.stringify(tree), encoding: 'utf8'});
    assert.equal(done.status, 0, done.stderr);
    return Number(done.stdout.trim());
  };
  const alone = await page.on('function(t){return import("/workspace-assets/workspace-multiphysics.mjs").then(m=>m.uncoupledDocument(t,"modes1"))}', template);
  const coupledEngine = engineNeff(template), aloneEngine = engineNeff(alone), shiftEngine = coupledEngine - aloneEngine;
  assert.deepEqual(before, [coupledEngine.toFixed(8), aloneEngine.toFixed(8), (shiftEngine < 0 ? '−' : '+') + Math.abs(shiftEngine).toFixed(8)], 'the template values are the engine runs');
  await page.until("/kept for recovery in this browser/.test(document.getElementById('autosave-status').textContent)", 'recovery kept');
  assert.equal(await page.text('#autosave-status'), 'Not saved to a file · kept for recovery in this browser');
  const a1 = await saveSession('template');
  assert.match(a1.name, /^heated-silicon-waveguide-session-\d{4}-\d\d-\d\d-\d{4}\.json$/);
  assert.match(await notice(), /^Session file heated-silicon-waveguide-session-.*\.json sent to the browser's downloads \(check your Downloads folder\): the model, 1 run and the without-heater result\.$/);
  assert.match(await page.text('#autosave-status'), /^Session file heated-silicon-waveguide-session-.*\.json sent to your browser's Downloads · \d{1,2}:\d\d(?: [AP]M)?$/);
  await fetchReplies(a1.text);
  const openedA = await openSession(a1.path);
  assert.equal(openedA, `Opened ${basename(a1.path)}. Its results were read from the file, not recomputed; input undo starts here.`);
  assert.equal(await page.text('#autosave-status'), `Opened ${basename(a1.path)}`);
  await page.click('#tree [data-mp-node="results:modes1"]');
  await page.until("!!document.querySelector('[data-neff-shift=\"1\"]')", 'opened results');
  const after = await shown();
  assert.deepEqual(after, before, 'S2: the same strings after the open');
  assert.match(await page.text('[data-mp-run-line]'), /Loaded from file, not recomputed; the file passed its damage check \(this does not show who made it\)\.$/);
  // the dock, the footer and the step rows say the result was read from the file, with no solve times
  const openedDock = await page.eval("({heading:document.querySelector('.dock-title>span').textContent,status:document.getElementById('status').textContent,sequence:document.getElementById('sequence').textContent})");
  stage('opened run status', openedDock);
  assert.equal(openedDock.heading, 'Run 1 · read from file, not recomputed');
  assert.equal(openedDock.status, 'Run 1 · read from file, not recomputed · press Run to compute it here');
  assert.match(openedDock.sequence, /Heat 1 · From file.*Modes 1 · From file/); assert.doesNotMatch(openedDock.sequence, /Done in/);
  const a2 = await saveSession('template again');
  assert.equal(a2.text, a1.text, 'S1: the second file is byte-identical');
  const s1Template = {...compareArrays(a1.text), python: comparePython(a1.path), bytes: Buffer.byteLength(a1.text)};
  stage('S1 S2 template', {before, after, ...s1Template});

  // the 0.12 µm variant
  await openInputs('variant-012.json', variant('0.12 um', '0.015 um'));
  await runAndWait(1);
  await page.until("/^[+−]0\\.\\d{8}$/.test(document.querySelector('[data-neff-shift=\"1\"]')?.textContent||'')", 'heater-off 0.12', 180000);
  await runReady();
  const b0 = await shown(), b1 = await saveSession('0.12');
  await fetchReplies(b1.text);
  await openSession(b1.path);
  await page.click('#tree [data-mp-node="results:modes1"]');
  await page.until("!!document.querySelector('[data-neff-shift=\"1\"]')", 'opened 0.12');
  assert.deepEqual(await shown(), b0);
  const b2 = await saveSession('0.12 again');
  assert.equal(b2.text, b1.text, 'S1: 0.12 µm second file byte-identical');
  const s1Fine = {...compareArrays(b1.text), python: comparePython(b1.path), bytes: Buffer.byteLength(b1.text), triangles: JSON.parse(b1.text).runs[0].result.mesh.triangles.length};
  stage('S1 0.12 um', {shown: b0, ...s1Fine});

  // two runs, the first named and pinned
  await page.click('nav [data-page=Applications]');
  await openTemplate();
  await runAndWait(1);
  await page.until("/^[+−]0\\.\\d{8}$/.test(document.querySelector('[data-neff-shift=\"1\"]')?.textContent||'')", 'heater-off two runs', 180000);
  await runReady();
  await page.click('#tree [data-mp-node="results:runs"]');
  await page.until("!!document.getElementById('mp-run-name-input')", 'run list');
  await page.type('#mp-run-name-input', 'Heater 2e14');
  await page.click('#mp-rename-run');
  await page.until("/^Run named “Heater 2e14” and pinned/.test(document.getElementById('file-status').textContent)", 'named');
  await page.click('#tree [data-mp-node="physics:heat1"]');
  await page.until("!!document.getElementById('mp-f-physics-heat1-heat_source_density-heater')", 'heat settings');
  await page.type('#mp-f-physics-heat1-heat_source_density-heater', '1e14');
  await runAndWait(2);
  await page.click('#tree [data-mp-node="results:runs"]');
  await page.until("document.querySelectorAll('[data-mp-run]').length===2", 'two runs listed');
  const listedRuns = await page.eval("[...document.querySelectorAll('[data-mp-run]')].map(b=>b.textContent)");
  assert.match(listedRuns[0], /^Run 2 · \d{1,2}:\d\d(?: [AP]M)?$/); assert.match(listedRuns[1], /^Pinned · Run 1 · Heater 2e14 · \d{1,2}:\d\d(?: [AP]M)?$/);
  assert.match(await page.text('#mp-run-list-heading'), /^Runs · 2 of 6 · 1 pinned$/);
  const c1 = await saveSession('two runs');
  assert.match(await notice(), /the model, 2 runs and the without-heater result\.$/);
  await fetchReplies(c1.text);
  await page.click('nav [data-page=Applications]');
  await page.click('[data-template=heated-waveguide]');
  // the runs are in a session file: no question
  await page.until("/^Heated silicon waveguide ready\\./.test(document.getElementById('file-status').textContent)&&!document.getElementById('leave-confirm').open", 'a fresh template');
  // the open question names the runs that come back
  await runAndWait(1);
  await page.until("/^[+−]0\\.\\d{8}$/.test(document.querySelector('[data-neff-shift=\"1\"]')?.textContent||'')", 'heater-off before the open', 180000);
  await runReady();
  await setFile('#session-file', c1.path);
  await page.until("document.getElementById('leave-confirm').open", 'leave question before the open');
  assert.equal(await page.text('#leave-confirm-title'), 'Leave this model?');
  assert.equal(await page.text('#leave-confirm-description'), '1 run is only in this tab and in browser recovery. Save session first to keep it in a file.');
  assert.deepEqual(await page.eval("[...document.querySelectorAll('#leave-confirm button')].filter(b=>!b.hidden).map(b=>b.textContent)"), ['Cancel', 'Save session', 'Leave']);
  await page.click('#leave-stay');
  await page.until("document.getElementById('file-status').textContent==='Kept the current model and its runs.'", 'kept');
  await openSession(c1.path);
  await page.click('#tree [data-mp-node="results:runs"]');
  await page.until("document.querySelectorAll('[data-mp-run]').length===2", 'two runs back');
  const back = await page.eval("[...document.querySelectorAll('[data-mp-run]')].map(b=>b.textContent)");
  assert.match(back[0], /^Run 2 · \d{1,2}:\d\d(?: [AP]M)? · from file$/); assert.match(back[1], /^Pinned · Run 1 · Heater 2e14 · \d{1,2}:\d\d(?: [AP]M)? · from file$/);
  const c2 = await saveSession('two runs again');
  assert.equal(c2.text, c1.text, 'S1: the two-run file byte-identical');
  // the next run is numbered after the highest stored
  await runAndWait(3);
  const s1Two = {...compareArrays(c1.text), python: comparePython(c1.path), bytes: Buffer.byteLength(c1.text)};
  stage('S1 two runs', {listed: back, ...s1Two});

  // S6 and S7: each damaged or newer file is refused by name; the tab stays as it was
  const {recordDigest, sessionJson} = await import(new URL('../../packages/simcase/src/simcase/studio/static/workspace-multiphysics-session.mjs', import.meta.url));
  const redigest = d => { for (const r of d.runs) r.digest = recordDigest(r); for (const b of Object.values(d.baselines)) b.digest = recordDigest(b); return d; };
  // the node count of the template's mesh, from the file (it depends on the installed mesher)
  const N = JSON.parse(c1.text).runs[0].result.mesh.node_coordinates.length;
  const MUTATIONS = [
    ['S6 an array value changed', d => { d.runs[0].result.physics.modes1.coupled.refractive_index.n[5] += 1e-6; }, /Run 1 changed after it was saved \(its check value does not match\)\./, false],
    ['S6 one array shortened', d => { d.runs[0].result.physics.heat1.temperature.values.pop(); }, new RegExp(`Run 1's stored maps are not well formed: Heat 1 node temperature has ${N - 1} values for ${N} nodes\\.`)],
    ['S6 a triangle index out of range', d => { d.runs[0].result.mesh.triangles[7][2] = N; }, new RegExp(`Run 1's stored maps are not well formed: triangle 7 names node ${N}, outside 0–${N - 1}\\.`)],
    ['S6 a non-finite value', d => { d.runs[0].result.physics.modes1.coupled.refractive_index.n[3] = 7777.25; }, /Run 1's stored maps are not well formed: refractive_index\.n holds a value that is not a finite number\./, true, t => t.replace('7777.25', '1e999')],
    ['S6 a solve order swapped', d => { d.runs[0].result.solve_order.reverse(); }, /Run 1's solve order \[\["modes1"\],\["heat1"\]\] is not the order of its model \(\[\["heat1"\],\["modes1"\]\]\)\./],
    ['S6 a coupling renamed', d => { const c = d.runs[0].result.couplings; c.renamed = c.heat1_to_modes1; delete c.heat1_to_modes1; }, /Run 1's coupling records do not match its model's couplings\./],
    ['S6 a duplicate job', d => { d.runs[1].job = d.runs[0].job; }, /Two runs have the same job identifier mp-[0-9a-f]{12}\./],
    ['S6 a model that fails the check', d => { d.runs[0].document.physics.modes1.vacuum_wavelength = 'warm'; }, /Run 1's model does not pass today's check: physics\.modes1\.vacuum_wavelength: /],
    ['S6 a baseline document changed', d => { d.baselines.modes1.document.physics.modes1.vacuum_wavelength = '1551 nm'; }, /The without-heater result of Modes 1 belongs to no run in this file and not to its model\./],
    // version 9 is an optical session since the number of modes: a newer file is version 10, and a
    // multiphysics layout under version 9 is refused by its first key
    ['S7 version 10', d => { d.version = 10; }, /This session file is version 10, newer than this Studio reads \(versions 6–9\)\. Open it in a newer Studio\./],
    ['S7 a version 8 layout under version 9', d => { d.version = 9; }, /Unknown key "document" in the session file\./],
    ['S7 another application', d => { d.application = 'other'; }, /This session file holds a “other” model, which this Studio does not read\./],
    ['S7 another result', d => { d.runs[0].result.result = 'multiphysics-run-v2'; }, /Run 1 was saved as result “multiphysics-run-v2”, which this Studio does not read\./],
    ['S7 another document envelope', d => { d.runs[0].document.openphysics = '0.3/multiphysics.2'; }, /Run 1's model does not pass today's check: openphysics: openphysics is "0\.3\/multiphysics\.2"; this reader reads the format "0\.3"\./],
  ];
  await page.click('#tree [data-mp-node="results:modes1"]');
  await page.until("/kept for recovery in this browser$/.test(document.getElementById('autosave-status').textContent)", 'recovery settled before the refusals');
  const kept = await workspace(), refusals = {};
  for (const [what, change, message, recompute = true, finish = t => t] of MUTATIONS) {
    const d = JSON.parse(c1.text); change(d); if (recompute) redigest(d);
    const path = join(out, what.replace(/\W+/g, '-') + '.json'); await writeFile(path, finish(sessionJson(d)), 'utf8');
    const said = await openSession(path, {expectFailure: true});
    assert.match(said, message, what); assert.match(said, /Current inputs and results kept\.$/);
    assert.deepEqual(await workspace(), kept, what + ': the workspace, runs and Undo are unchanged');
    refusals[what] = said;
  }
  stage('S6 S7 refusals', refusals);

  // S8: browser recovery after a reload: the runs come back as recovered, with S1 identity
  await page.until("/kept for recovery in this browser/.test(document.getElementById('autosave-status').textContent)", 'recovery of three runs');
  await page.call('Page.reload');
  await page.until("!!document.querySelector('[data-template=heated-waveguide]')&&!document.getElementById('recover-notebook').disabled", 'reload');
  await clearNotice(); await page.click('#recover-notebook');
  await page.until("/^Recovered from this browser/.test(document.getElementById('file-status').textContent)", 'recovered');
  assert.match(await notice(), /^Recovered from this browser \(Browser recovery · .*\), not recomputed\. Last session file .*; changed since\. Input undo starts here\.$/);
  await page.click('#tree [data-mp-node="results:runs"]');
  await page.until("document.querySelectorAll('[data-mp-run]').length===3", 'three runs recovered');
  const recoveredRuns = await page.eval("[...document.querySelectorAll('[data-mp-run]')].map(b=>b.textContent)");
  assert.ok(recoveredRuns.every(t => / · recovered$/.test(t)), JSON.stringify(recoveredRuns));
  await page.click('#tree [data-mp-node="results:modes1"]');
  assert.match(await page.text('[data-mp-run-line]'), /Recovered from this browser, not recomputed\.$/);
  const recoveredDock = await page.eval("({heading:document.querySelector('.dock-title>span').textContent,sequence:document.getElementById('sequence').textContent})");
  stage('recovered run status', recoveredDock);
  assert.match(recoveredDock.heading, /^Run \d · recovered from this browser, not recomputed$/);
  assert.match(recoveredDock.sequence, /Heat 1 · From this browser.*Modes 1 · From this browser/); assert.doesNotMatch(recoveredDock.sequence, /Done in/);
  const r1 = await saveSession('recovered');
  await fetchReplies(r1.text);
  const s8Identity = {...compareArrays(r1.text), python: comparePython(r1.path)};
  stage('S8 recovered', {runs: recoveredRuns, ...s8Identity});

  // S8: three earlier sessions, from four pages that each edited the model
  for (const power of ['3e14', '4e14', '5e14', '6e14']) {
    await page.call('Page.reload');
    await page.until("!!document.querySelector('[data-template=heated-waveguide]')&&!document.getElementById('recover-notebook').disabled", 'reload ' + power);
    await openTemplate();
    await page.click('#tree [data-mp-node="physics:heat1"]');
    await page.until("!!document.getElementById('mp-f-physics-heat1-heat_source_density-heater')", 'heat settings ' + power);
    await page.type('#mp-f-physics-heat1-heat_source_density-heater', power);
    await page.until("/kept for recovery in this browser/.test(document.getElementById('autosave-status').textContent)", 'edited model kept ' + power);
  }
  await page.call('Page.reload');
  await page.until("document.querySelectorAll('#earlier-sessions button').length===3", 'three earlier sessions');
  const earlier = await page.eval("[...document.querySelectorAll('#earlier-sessions button')].map(b=>b.textContent)");
  assert.ok(earlier.every(t => /^Recover earlier session · Heated silicon waveguide · \d+ runs · /.test(t)), JSON.stringify(earlier));
  // every entry names its runs: one name (or "Run N") per run
  for (const t of earlier) {
    const m = /^Recover earlier session · Heated silicon waveguide · (\d+) runs?(?: · (.+?))? · ([^·]+)$/.exec(t);
    assert.ok(m, t); assert.equal(m[2] ? m[2].split(', ').length : 0, Number(m[1]), t);
  }
  await page.click('#earlier-sessions button');
  await page.until("/^Recovered from this browser \\(Earlier browser session/.test(document.getElementById('file-status').textContent)", 'earlier recovered');
  stage('S8 earlier sessions', {earlier});

  // S8: two tabs: another tab writes browser recovery, then this one finds the conflict
  const second = await (await fetch(`http://127.0.0.1:${debugPort}/json/new?${encodeURIComponent(base + '/workspace')}`, {method: 'PUT'})).json();
  const other = new Page(second.webSocketDebuggerUrl); await other.ready; await other.call('Runtime.enable');
  await other.until("!!document.querySelector('[data-template=heated-waveguide]')&&!document.getElementById('recover-notebook').disabled", 'second tab');
  await openTemplate(other);
  await other.click('#tree [data-mp-node="physics:heat1"]');
  await other.until("!!document.getElementById('mp-f-physics-heat1-heat_source_density-heater')", 'second tab settings');
  await other.type('#mp-f-physics-heat1-heat_source_density-heater', '7e14');
  await other.until("/kept for recovery in this browser/.test(document.getElementById('autosave-status').textContent)", 'second tab kept');
  await page.click('#tree [data-mp-node="physics:heat1"]');
  await page.until("!!document.getElementById('mp-f-physics-heat1-heat_source_density-heater')", 'first tab settings');
  await page.type('#mp-f-physics-heat1-heat_source_density-heater', '8e14');
  await page.until("/browser recovery changed in another tab/.test(document.getElementById('autosave-status').textContent)", 'conflict');
  const conflict = await page.text('#autosave-status');
  await fetch(`http://127.0.0.1:${debugPort}/json/close/${second.id}`).catch(() => {});
  stage('S8 two tabs', {conflict});

  // R1-R3, a restart: two optical runs, then the two-run heated session file opened over them.
  // After a reload and the same file opened again, the Optical waveguide card offers the optical
  // runs before Start new (R1), every recovery entry is shown once (R2), and a tab click keeps
  // the opened file in the title (R3).
  await page.call('Page.reload');
  await page.until("!!document.querySelector('[data-template=optical]')", 'start page for R1');
  await page.click('[data-template=optical]');
  if (await page.eval("document.getElementById('leave-confirm').open")) await page.click('#leave-go');
  await page.until("!!document.getElementById('shape-w')&&!document.getElementById('run-optical').disabled", 'optical model for R1', 60000);
  const runOptical = async label => {
    await page.eval("document.getElementById('job-message').textContent=''"); await page.click('#run-optical');
    await page.until("/complete/i.test(document.getElementById('job-message').textContent)&&document.getElementById('run-optical').textContent==='Run optical study'", 'optical ' + label, 120000);
  };
  await runOptical('run 1');
  await page.click('nav [data-page=Model]'); await sleep(200); await page.click('#tree [data-node="Geometry"]'); await page.until("!!document.getElementById('shape-w')", 'geometry inspector');
  await page.type('#shape-w', 600);
  await runOptical('run 2');
  const opticalNeff = () => page.eval("[...document.querySelectorAll('#modes-table [data-neff]')].map(e=>e.textContent)");
  await page.until("!!document.getElementById('modes-table')", 'optical results'); const neffBefore = await opticalNeff();
  await page.until("/kept for recovery in this browser/.test(document.getElementById('autosave-status').textContent)", 'optical runs kept');
  await page.click('nav [data-page=Applications]'); await page.until("!!document.querySelector('[data-template=heated-waveguide]')", 'models page R1');
  // the tab holds the optical runs, so the card offers nothing yet
  assert.equal(await page.exists('#resume-optical'), false);
  // the switch note says the tab holds the runs until it is closed or reloaded, then how to get them back
  await openTemplate();
  // round 9 (J7): one short line, the rest behind More
  assert.match(await page.eval("document.getElementById('file-status').textContent"), / Optical waveguide runs stay in this tab · Models › Optical waveguide returns to them More\s*This tab holds 2 runs until it is closed or reloaded\. After that, Models › Optical waveguide › Resume \(browser recovery, which keeps the four newest sessions\) brings them back\.$/);
  assert.equal(await page.eval("document.querySelector('#file-status details.message-more')?.open"), false, 'the rest is behind More, closed');
  await openSession(c1.path);
  await page.until("/kept for recovery in this browser/.test(document.getElementById('autosave-status').textContent)||/^Opened /.test(document.getElementById('autosave-status').textContent)", 'heated session kept');
  await page.until("/^Browser recovery updated/.test(document.getElementById('notebook-recovery-detail').textContent)", 'heated session in browser recovery', 20000);
  // the restart, and the same file opened again
  await page.call('Page.reload');
  await page.until("!!document.querySelector('[data-template=optical]')&&!document.getElementById('recover-notebook').disabled", 'reload R1');
  await openSession(c1.path);
  await page.until("/^Browser recovery updated/.test(document.getElementById('notebook-recovery-detail').textContent)", 'reopened session in browser recovery', 20000);
  const openedTitle = `Opened ${basename(c1.path)}`;
  assert.equal(await page.text('#autosave-status'), openedTitle);
  // R3: tab clicks are not edits: the opened file stays in the title and the footer
  const titles = {};
  for (const tab of ['Applications', 'Connections', 'Results', 'Model', 'Applications']) {
    await page.click(`nav [data-page=${tab}]`); await sleep(300);
    titles[tab] = {project: await page.text('#project'), footer: await page.text('#autosave-status')};
    assert.equal(titles[tab].footer, openedTitle, tab); assert.ok(titles[tab].project.endsWith(' / ' + openedTitle), titles[tab].project);
  }
  // R1: the Optical waveguide card offers the runs from browser recovery first, then Start new
  await page.until("!!document.getElementById('resume-optical')", 'optical resume offer');
  const offer = await page.eval("({resume:document.getElementById('resume-optical').textContent,next:document.getElementById('resume-optical').nextElementSibling?.textContent,card:document.getElementById('resume-optical').closest('.card-slot')?.querySelector('[data-template]')?.dataset.template})");
  assert.match(offer.resume, /^Resume Optical waveguide · Run 1, Run 2 · \d{1,2}:\d\d(?: [AP]M)? \(this browser\)$/); assert.equal(offer.next, 'Start new'); assert.equal(offer.card, 'optical');
  // R2: each stored session once, newest first, the file named where a record came from one
  const lists = await page.eval("({resume:[...document.querySelectorAll('.resume-actions [data-resume-earlier], #resume-latest')].map(b=>b.textContent),earlier:[...document.querySelectorAll('#earlier-sessions button')].map(b=>b.textContent)})");
  stage('R1 R2 R3 restart', {titles, offer, lists, neffBefore});
  // the sessions behind the listed entries, as stored: no two are the same session (compared
  // without their view), and none is the session this tab wrote as the latest record. Their texts
  // can read alike (two unedited 0-run models of different heat power), so the check reads storage.
  const stored = await page.eval(`import('/workspace-assets/workspace-notebook-recovery.mjs').then(async m=>{const s=m.indexedNotebookStore();const latest=await s.load(),earlier=await s.loadEarlier();
    const listed=[...document.querySelectorAll('#earlier-sessions button')].map(b=>Number(b.dataset.earlier));
    const keys=listed.map(i=>m.sessionKey(earlier[i].session));return {listed,stored:earlier.length,distinct:new Set(keys).size,latestListed:keys.includes(m.sessionKey(latest.session))};})`);
  stage('R2 stored sessions', stored);
  assert.equal(stored.distinct, stored.listed.length, JSON.stringify(stored)); assert.equal(stored.latestListed, false);
  // the resume card lists the same entries, but for the one the Optical waveguide card resumes (round 9, J3)
  const onCard = await page.eval("document.getElementById('resume-optical').dataset.resumeRecord");
  assert.equal(lists.resume.length, stored.listed.length - (stored.listed.includes(Number(onCard)) ? 1 : 0), 'the resume card lists the same entries');
  assert.ok(!lists.resume.some(t => /Optical waveguide · 2 runs · Run 1, Run 2/.test(t)), 'the optical session is offered once, on its card: ' + JSON.stringify(lists.resume));
  // the heated session open in this tab is not offered again, and its earlier copy is gone
  assert.ok(!lists.earlier.some(t => t.includes('Heated silicon waveguide · 2 runs · Run 2, Run 1 · Heater 2e14')), JSON.stringify(lists.earlier));
  assert.ok(lists.earlier.some(t => /^Recover earlier session · Optical waveguide · 2 runs · Run 1, Run 2 · /.test(t)), JSON.stringify(lists.earlier));
  for (const [width, height, mobile, tag] of [[1440, 900, false, 'wide'], [390, 844, true, 'phone']]) {
    await size(width, height, mobile); await sleep(300); assert.equal(await overflow(), 0, 'R1 ' + tag); await page.screenshot('r1-' + tag);
  }
  await size(1440, 900); await sleep(300);
  // Resume brings the two optical runs back, not recomputed, with the same n_eff
  await clearNotice(); await page.click('#resume-optical');
  const end = Date.now() + 60000;
  while (Date.now() < end && !/^Recovered from this browser/.test(await notice())) { if (await page.eval("document.getElementById('load-confirm').open")) await page.click('#confirm-load'); if (await page.eval("document.getElementById('leave-confirm').open")) await page.click('#leave-go'); await sleep(150); }
  assert.match(await notice(), /^Recovered from this browser \(Earlier browser session · /);
  await page.click('nav [data-page=Results]'); await page.until("document.querySelectorAll('.run-item').length===2&&!!document.getElementById('modes-table')", 'optical runs back');
  assert.deepEqual(await opticalNeff(), neffBefore);
  stage('R1 resumed', {neff: await opticalNeff()});

  // S5: six runs of the 0.08 µm mesh, about 22 MB with their maps
  await page.call('Page.reload');
  await page.until("!!document.querySelector('[data-template=heated-waveguide]')", 'reload for S5');
  await openTemplate();
  await openInputs('variant-008.json', variant('0.08 um', '0.01 um'));
  for (let n = 1; n <= 6; n++) await runAndWait(n);
  await page.until("/^[+−]0\\.\\d{8}$/.test(document.querySelector('[data-neff-shift=\"1\"]')?.textContent||'')", 'heater-off 0.08', 180000);
  await page.until("/kept for recovery in this browser without the maps of 5 runs · Save session to keep them$/.test(document.getElementById('autosave-status').textContent)", 'recovery without five maps', 60000);
  const recoveryPartial = await page.text('#autosave-status');
  // Save session asks; Cancel writes nothing
  const unchanged = await listed();
  await clearNotice(); await page.click('#save-session');
  await page.until("document.getElementById('session-overflow').open", 'overflow question');
  const question = await page.text('#session-overflow-description');
  assert.match(question, /^Session is 2\d MB; the limit is 16 MiB\. Keep the maps of the selected and pinned runs only\? The other runs keep n_eff, the coupling check and the iteration history, but not their maps\.$/);
  assert.deepEqual(await page.eval("[...document.querySelectorAll('#session-overflow button')].map(b=>b.textContent)"), ['Cancel', 'Keep maps for selected and pinned runs']);
  await page.click('#overflow-cancel');
  assert.equal(await notice(), 'Session not saved: nothing was written.');
  await sleep(1000); assert.deepEqual([...await listed()].filter(f => !unchanged.has(f)), [], 'Cancel writes nothing');
  // Keep maps for selected and pinned runs: the file fits and says which runs keep values only
  const before5 = await listed(); await clearNotice(); await page.click('#save-session');
  await page.until("document.getElementById('session-overflow').open", 'overflow question again');
  await page.click('#overflow-keep');
  const big = await nextDownload(before5, 'six 0.08 runs');
  await page.until("/keep values only, without maps\\.$/.test(document.getElementById('file-status').textContent)", 'values-only notice');
  const bigNotice = await notice(), bigSession = JSON.parse(big.text);
  assert.ok(Buffer.byteLength(big.text) <= 16 * 1024 * 1024);
  assert.deepEqual(bigSession.runs.map(r => r.maps), ['not kept', 'not kept', 'not kept', 'not kept', 'not kept', 'kept']);
  assert.match(bigNotice, /: the model, 6 runs and the without-heater result\. 5 runs \(Run 1, Run 2, Run 3, Run 4, Run 5\) keep values only, without maps\.$/);
  await fetchReplies(big.text);
  const s5Arrays = {...compareArrays(big.text, {valuesOnly: [1, 2, 3, 4, 5]}), python: comparePython(big.path)};
  // pinned runs: five pinned, with their maps, are over the limit together
  for (const n of [1, 2, 3, 4, 5]) {
    await page.click('#tree [data-mp-node="results:runs"]');
    await page.until("document.querySelectorAll('[data-mp-run]').length===6", 'run list for pins');
    await page.click(`[data-mp-run]:nth-last-of-type(${n})`);
    await page.until(`/^Run ${n} shown under Results/.test(document.getElementById('file-status').textContent)`, 'run ' + n + ' shown');
    await page.click('#tree [data-mp-node="results:runs"]');
    await page.until("!!document.getElementById('mp-run-name-input')", 'run name ' + n);
    await page.type('#mp-run-name-input', 'kept ' + n); await page.click('#mp-rename-run');
    await page.until(`/^Run named “kept ${n}” and pinned/.test(document.getElementById('file-status').textContent)`, 'pinned ' + n);
    // each write lands before the next pin (rapid edits are coalesced into one write)
    // with runs 1-n pinned and run n shown, the maps of the 6 - n others are left out
    if (n < 5) await page.until(`/kept for recovery in this browser without the maps of ${6 - n} runs/.test(document.getElementById('autosave-status').textContent)`, 'recovery with ' + n + ' pinned', 60000);
  }
  // browser recovery writes nothing new and says so; the record before stays
  await page.until("/ · browser recovery unavailable: session over 16 MiB$/.test(document.getElementById('autosave-status').textContent)", 'recovery over the limit', 60000);
  const recoveryOver = await page.text('#autosave-status');
  await clearNotice(); await page.click('#save-session');
  await page.until("/^Session not saved: /.test(document.getElementById('file-status').textContent)", 'refused by name');
  const refusal = await notice();
  assert.match(refusal, /^Session not saved: The selected and pinned runs \(Run 1, Run 2, Run 3, Run 4, Run 5\) are 1\d MB with their maps, over the 16 MiB session limit\. Unpin some of them\.$/);
  await page.call('Page.reload');
  await page.until("!!document.querySelector('[data-template=heated-waveguide]')&&!document.getElementById('recover-notebook').disabled", 'reload after the limit');
  await clearNotice(); await page.click('#recover-notebook');
  await page.until("/^Recovered from this browser/.test(document.getElementById('file-status').textContent)", 'the record before the limit');
  await page.click('#tree [data-mp-node="results:runs"]');
  await page.until("document.querySelectorAll('[data-mp-run]').length===6", 'six runs recovered');
  const recoveredBig = await page.eval("[...document.querySelectorAll('[data-mp-run]')].map(b=>b.textContent)");
  // the last record written: four pinned with their maps; runs 5 and 6 values only
  assert.deepEqual(recoveredBig.map(t => [/^Pinned · /.test(t), / · values only$/.test(t)]), [[false, true], [false, true], [true, false], [true, false], [true, false], [true, false]], JSON.stringify(recoveredBig));
  // opened, the saved file's values-only runs say so in the list and on their map pages
  await openSession(big.path);
  await page.click('#tree [data-mp-node="results:runs"]');
  await page.until("document.querySelectorAll('[data-mp-run]').length===6", 'six runs opened');
  const bigList = await page.eval("[...document.querySelectorAll('[data-mp-run]')].map(b=>b.textContent)");
  assert.equal(bigList.filter(t => / · values only$/.test(t)).length, 5, JSON.stringify(bigList));
  await page.click('[data-mp-run]:last-of-type');
  await page.until("!!document.querySelector('[data-mp-values-only]')", 'values-only run shown');
  await page.click('#tree [data-mp-node="results:heat1"]');
  await page.until("!!document.querySelector('[data-mp-no-maps]')", 'values-only heat page');
  assert.equal(await page.text('[data-mp-no-maps]'), 'Maps not kept in this file: n_eff, the coupling check and the iteration history are.');
  assert.equal(await page.exists('canvas[data-mp-map]'), false);
  await page.click('#tree [data-mp-node="results:modes1"]');
  await page.until("!!document.querySelector('[data-mp-no-maps]')&&!!document.querySelector('[data-neff=\"1\"]')", 'values-only modes page');
  await page.click('#tree [data-mp-node="results:check"]');
  await page.until("/Coupling check/.test(document.getElementById('canvas').innerText)", 'values-only coupling check');
  const counts = bigSession.runs[0].counts, us = n => n.toLocaleString('en-US');
  assert.match(await page.text('.mp-check tbody'), new RegExp(`${us(counts.nodes)} node temperatures, 300\\.0–[0-9.]+ K .*${us(counts.triangles)} triangle means \\(mean of 3 nodes\\) Passed · max \\|received − sent\\| = 0 K`));
  await page.screenshot('s5-values-only');
  stage('S5', {question, bigNotice, bytes: Buffer.byteLength(big.text), recoveryPartial, recoveryOver, refusal, recovered: recoveredBig, list: bigList, ...s5Arrays});

  assert.deepEqual(report.exceptions, []); assert.deepEqual(report.consoleErrors, []);
  report.status = 'passed';
} catch (error) {
  report.status = 'failed'; report.error = String(error?.stack || error);
  // what the page said when it failed
  try { report.screen = await diagnose(); } catch {}
  process.exitCode = 1;
} finally {
  for (const child of owned) child.kill();
  await save();
  await rm(profile, {recursive: true, force: true}).catch(() => {});
  console.log('[session browser]', report.status, report.error || '');
}
