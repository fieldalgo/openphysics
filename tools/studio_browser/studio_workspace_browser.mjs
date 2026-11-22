// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Real-browser check of the installed Studio workspace (/workspace) on this OS:
// two optical designs (a Width edit keeps the core centred), Compare with its n_eff
// table, Save session under a dated name, a server restart with the page open,
// recovery from the start page without a confirmation (with the round-3 labels: one save indicator
// in the title and footer, the routes back, nm plot axes, n_eff digits, the wavelength in the step bar,
// Compare headings and Unpin only); then the Joule heating application (Picard,
// Newton, a refusal shown, constant materials). Drives a preinstalled Chrome through the
// DevTools protocol with Node's built-in fetch and WebSocket; no npm package and
// no browser download. Fails, never skips, when no browser is found.
//
//   node tools/studio_browser/studio_workspace_browser.mjs --python <venv python> --output <dir> [--chrome <path>]
import assert from 'node:assert/strict';
import {spawn, spawnSync} from 'node:child_process';
import {existsSync} from 'node:fs';
import {mkdir, mkdtemp, readdir, readFile, rm, writeFile} from 'node:fs/promises';
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
const stage = (name, data = {}) => { report.stages.push({name, ...data}); console.log('[workspace browser]', name, JSON.stringify(data)); };

function findChrome() {
  const candidates = [args.chrome, process.env.CHROME_PATH];
  if (process.platform === 'win32') {
    for (const base of [process.env.PROGRAMFILES, process.env['PROGRAMFILES(X86)'], process.env.LOCALAPPDATA])
      if (base) candidates.push(join(base, 'Google', 'Chrome', 'Application', 'chrome.exe'), join(base, 'Microsoft', 'Edge', 'Application', 'msedge.exe'));
  } else if (process.platform === 'darwin') {
    candidates.push('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium');
  } else {
    const found = spawnSync('which', ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'], {encoding: 'utf8'});
    candidates.push(...found.stdout.split('\n'));
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
// What a participant does with Ctrl+C. Windows has no SIGINT for a child process,
// so the process is terminated there; both end the server.
async function stopServer(child) {
  child.kill(process.platform === 'win32' ? undefined : 'SIGINT');
  const started = Date.now();
  await Promise.race([child.done, sleep(15000)]);
  return {exit: child.exitCode, signal: child.signalCode, ms: Date.now() - started};
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
    while (Date.now() < end) { if (await this.eval(expression).catch(() => false)) return; await sleep(200); }
    throw new Error('timed out waiting for ' + label);
  }
  // Runs a fixed function on the page's document with the selector as an argument, so no
  // page code is built from values.
  async onElement(declaration, selector) {
    const {result: document} = await this.call('Runtime.evaluate', {expression: 'document'});
    const result = await this.call('Runtime.callFunctionOn', {objectId: document.objectId, functionDeclaration: declaration,
      arguments: [{value: selector}], awaitPromise: true, returnByValue: true});
    if (result.exceptionDetails) throw new Error('page: ' + (result.exceptionDetails.exception?.description || result.exceptionDetails.text));
    return result.result.value;
  }
  // Chooses an option as a user does: set the value, then the change event the page listens to.
  async choose(selector, value) {
    const {result: document} = await this.call('Runtime.evaluate', {expression: 'document'});
    const result = await this.call('Runtime.callFunctionOn', {objectId: document.objectId,
      functionDeclaration: 'function(selector,value){const e=this.querySelector(selector);if(!e)throw Error("missing "+selector);e.value=value;e.dispatchEvent(new Event("change",{bubbles:true}));return e.value}',
      arguments: [{value: selector}, {value}], returnByValue: true});
    if (result.exceptionDetails) throw new Error('page: ' + (result.exceptionDetails.exception?.description || result.exceptionDetails.text));
    assert.equal(result.result.value, value, 'option ' + value + ' of ' + selector);
    await sleep(150);
  }
  click(selector) { return this.onElement('function(selector){const e=this.querySelector(selector);if(!e)throw Error("missing "+selector);e.click();return true}', selector); }
  // Typing as a user does: focus, select, insert text, leave the field.
  async type(selector, text) {
    await this.onElement('function(selector){const e=this.querySelector(selector);if(!e)throw Error("missing "+selector);e.focus();e.select();return true}', selector);
    await this.call('Input.insertText', {text: String(text)});
    await this.onElement('function(selector){this.querySelector(selector).blur();return true}', selector);
    await sleep(150);
  }
  async screenshot(name) { const png = await this.call('Page.captureScreenshot', {format: 'png'}); await writeFile(join(out, name + '.png'), Buffer.from(png.data, 'base64')); }
}

const profile = await mkdtemp(join(tmpdir(), 'openphysics-workspace-browser-'));
const downloads = join(out, 'downloads');
await mkdir(downloads, {recursive: true});
try {
  const chrome = findChrome();
  report.chrome = chrome || null;
  if (!chrome) throw new Error('No preinstalled Chrome, Chromium or Edge found; set --chrome or CHROME_PATH. No browser is downloaded.');
  const apiPort = await freePort(), debugPort = await freePort(), base = `http://127.0.0.1:${apiPort}`;
  const startServer = async name => {
    const child = launch(args.python, ['-I', '-m', 'simcase.studio', '--workspace', '--no-browser', '--port', String(apiPort)], name);
    for (let i = 0; i < 240; i++) { try { if ((await fetch(base + '/workspace')).ok) return child; } catch {} await sleep(250); }
    throw new Error('Studio did not start: ' + name);
  };
  let server = await startServer('server-1');
  // Chrome refuses to run as root with its sandbox (containers); CI runners are not root.
  const sandbox = process.getuid?.() === 0 ? ['--no-sandbox'] : [];
  launch(chrome, ['--headless=new', '--disable-gpu', ...sandbox, '--no-first-run', '--no-default-browser-check', '--remote-debugging-address=127.0.0.1',
    '--remote-debugging-port=' + debugPort, '--user-data-dir=' + profile, '--window-size=1280,800', 'about:blank'], 'browser');
  let target;
  for (let i = 0; i < 120 && !target; i++) { try { target = (await (await fetch(`http://127.0.0.1:${debugPort}/json/list`)).json()).find(t => t.type === 'page'); } catch {} if (!target) await sleep(250); }
  if (!target) throw new Error('Browser DevTools endpoint unavailable');
  const page = new Page(target.webSocketDebuggerUrl); await page.ready;
  await page.call('Runtime.enable'); await page.call('Page.enable');
  await page.call('Emulation.setDeviceMetricsOverride', {width: 1280, height: 800, deviceScaleFactor: 1, mobile: false});
  await page.call('Page.setDownloadBehavior', {behavior: 'allow', downloadPath: downloads});
  report.browserVersion = (await page.call('Browser.getVersion').catch(() => ({}))).product || null;

  const runAndWait = async () => {
    await page.until("!document.getElementById('run-optical').disabled", 'Run enabled');
    await page.click('#run-optical');
    await page.until("/complete/i.test(document.getElementById('job-message').textContent)&&document.getElementById('run-optical').textContent==='Run optical study'", 'optical run', 120000);
  };
  const toGeometry = async () => { await page.click('nav [data-page=Model]'); await sleep(200); await page.click('#tree [data-node="Geometry"]'); await page.until("!!document.querySelector('#shape-w')", 'geometry inspector'); };
  const text = selector => page.onElement('function(selector){const e=this.querySelector(selector);return e?e.innerText.replace(/\\s+/g," ").trim():null}', selector);
  // no horizontal document overflow at 1440 × 900 and on a 390 × 844 phone; back to 1280 × 800 after
  const noOverflow = async tag => {
    for (const [width, height, mobile] of [[1440, 900, false], [390, 844, true]]) {
      await page.call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile}); await sleep(300);
      const over = await page.eval('document.documentElement.scrollWidth-document.documentElement.clientWidth');
      stage('overflow ' + tag, {width, height, over}); assert.ok(over <= 0, `${tag} at ${width} × ${height} overflows by ${over}px`);
    }
    await page.call('Emulation.setDeviceMetricsOverride', {width: 1280, height: 800, deviceScaleFactor: 1, mobile: false}); await sleep(300);
  };
  const delta = () => page.eval("(document.getElementById('compare-description')?.textContent.match(/^.* Shown: A mode 1 ↔ B mode 1, overlap [0-9.]+, Δn_eff \\(B − A\\) ([+−][0-9]+\\.[0-9]+)\\./)||[])[1]||null");
  const compareTableRows = () => page.eval("(()=>{const t=document.getElementById('compare-neff');return t&&{caption:t.caption?.textContent,head:[...t.tHead.rows[0].cells].map(c=>c.innerText.replace(/\\s+/g,' ')),rows:[...t.tBodies[0].rows].map(r=>[...r.cells].map(c=>c.textContent)),matched:[...t.tBodies[0].rows].map(r=>r.dataset.match||null),overlap:[...t.querySelectorAll('[data-overlap]')].map(c=>Number(c.dataset.overlap)),note:document.getElementById('compare-match-note')?.textContent,picker:[...document.querySelectorAll('#compare-mode option')].map(o=>o.textContent)}})()");

  await page.call('Page.navigate', {url: base + '/workspace'});
  await page.until("/^Connected/.test(document.getElementById('connection-status').textContent)&&!!document.querySelector('[data-template=optical]')", 'connected start page');
  const startPage = await page.eval("({heading:document.querySelector('#canvas h2').textContent,resumeCard:!!document.querySelector('.resume-card'),status:document.getElementById('status').textContent,steps:document.querySelectorAll('#sequence b').length,tab:document.querySelector('nav [data-page=Applications]').textContent,view:document.getElementById('view-title').textContent+' · '+document.getElementById('view-detail').textContent,footer:document.getElementById('autosave-status').textContent})");
  stage('start page', startPage);
  // before an application is chosen: a neutral status and no study steps
  assert.equal(startPage.status, 'Choose a model to start'); assert.equal(startPage.steps, 0);
  // one word for one thing on the start page: model
  assert.equal(startPage.tab, 'Models'); assert.equal(startPage.heading, 'Choose a starting model'); assert.equal(startPage.view, 'Model library · Choose a model');
  assert.doesNotMatch(await text('#canvas'), /template|application/i, 'the start page says model');
  assert.equal(startPage.footer, 'No model chosen · nothing to save yet');
  // the chooser: a plain sentence about choosing, and Joule heating with its own card icon
  assert.match(await text('.application-contract'), /Choosing a model sets which physics it solves\. Dimensions you entered and runs you completed are kept, and Undo takes the choice back/);
  // every chooser sentence says what Save session keeps today; no sentence about other views
  const chooser = await text('.application-contract'); stage('chooser notes', {chooser, message: await text('#file-status')});
  assert.match(chooser, /Heated silicon waveguide: .*Save session keeps the model with its runs, their names and pins, and the without-heater results\./);
  assert.match(chooser, /Save session keeps the plate inputs; heat results stay in this tab\./); assert.match(chooser, /Save session keeps the inputs; Joule heating results stay in this tab\./);
  assert.match(chooser, /The heated silicon waveguide has its own Undo for its edits: to leave it, choose another model here\./);
  assert.doesNotMatch(chooser, /Save model file keeps|Results stay in the tab|Existing thermal Studio views/);
  assert.equal(await text('#file-status'), 'Choose a model to begin. Save session keeps the inputs with the optical or multiphysics runs; heat and Joule heating results stay in this tab.');
  const icons = await page.eval("Object.fromEntries([...document.querySelectorAll('.cards [data-template]')].map(b=>[b.dataset.template,getComputedStyle(b,'::before').content]))");
  stage('model card icons', icons); assert.notEqual(icons.joule, icons.optical); assert.equal(new Set(Object.values(icons)).size, Object.keys(icons).length);
  await page.click('[data-template=optical]'); await page.until("!!document.querySelector('#shape-w')", 'optical template');
  // before any edit or run: a new model, and the dock and footer keep the words before a run
  const opticalSequence = () => page.eval("({heading:document.querySelector('.dock-title>span').textContent,status:document.getElementById('status').textContent})");
  assert.equal(await page.eval("document.getElementById('project').textContent"), 'Optical waveguide / New model · not saved');
  assert.deepEqual(await opticalSequence(), {heading: 'Nothing is computed until you press Run', status: 'Optical adapter ready · explicit Run required'});
  await page.type('#shape-w', 600);
  assert.equal(await page.eval("document.getElementById('project').textContent"), 'Optical waveguide / Unsaved inputs');
  // Messages says the edit and the Left x it moved, instead of keeping "Model ready…"
  assert.equal(await text('#file-status'), 'Width set to 600 nm. Left x moved to −300 nm to keep the centre. Run explicitly to compute new results.');
  await page.type('#shape-h', 300);
  assert.equal(await text('#file-status'), 'Height set to 300 nm. Run explicitly to compute new results.');
  // a Width edit keeps the core centred on x = 0; a Height edit keeps it on y = 0
  const sized = await page.eval("({x:document.getElementById('shape-x').value,y:document.getElementById('shape-y').value,study:[...document.querySelectorAll('#workflow .workflow-step')][3]?.innerText.replace(/\\s+/g,' ')})");
  stage('600 × 300 nm design', sized); assert.deepEqual([sized.x, sized.y], ['-300', '0']); assert.match(sized.study, /Ready to run/);
  // the step bar's wavelength opens the wavelength field under Physics › Optical modes
  assert.equal(await text('#workflow-wavelength'), 'λ 1550 nm');
  await page.click('#workflow-wavelength'); await sleep(200);
  const wavelengthField = await page.eval("({heading:document.querySelector('#inspector h2')?.textContent,focused:document.activeElement?.id,tree:document.querySelector('#tree [aria-current],#tree .selected,#tree [aria-selected=true]')?.textContent?.trim()||null})");
  stage('wavelength from the step bar', wavelengthField); assert.equal(wavelengthField.heading, 'Optical modes'); assert.equal(wavelengthField.focused, 'wavelength-number');
  // the Study settings show the wavelength and open its one field under Optical modes
  await page.click('nav [data-page=Model]'); await sleep(200); await page.click('#tree [data-node="Study"]'); await page.until("!!document.getElementById('study-edit-wavelength')", 'optical study settings');
  assert.match(await text('#inspector'), /Wavelength 1550 nm Set in Physics › Optical modes\. Edit in Optical modes/);
  await noOverflow('optical study');
  await page.click('#study-edit-wavelength'); await sleep(200);
  const studyWavelength = await page.eval("({heading:document.querySelector('#inspector h2')?.textContent,focused:document.activeElement?.id,fields:document.querySelectorAll('input[id*=wavelength]').length})");
  stage('wavelength from Study settings', studyWavelength); assert.deepEqual(studyWavelength, {heading: 'Optical modes', focused: 'wavelength-number', fields: 1});
  await toGeometry();
  await runAndWait();
  // the dock heading and the footer say what was computed, naming the same run
  stage('sequence after run 1', await opticalSequence());
  assert.deepEqual(await opticalSequence(), {heading: 'Run 1 · solved from the current inputs', status: 'Run 1 · solved from the current inputs · press Run to solve again'});
  await noOverflow('optical results');
  // after a run of these inputs the Study step says so, and the title carries no revision counter
  const afterRun = await page.eval("({study:[...document.querySelectorAll('#workflow .workflow-step')][3]?.innerText.replace(/\\s+/g,' '),title:document.getElementById('project').textContent})");
  stage('first run complete', afterRun); assert.match(afterRun.study, /Run complete/); assert.doesNotMatch(afterRun.title, /Revision/);
  // one save indicator: before a file save it says which copy exists, and the footer repeats it
  await page.until("document.getElementById('project').textContent==='Optical waveguide / Not saved to a file · kept for recovery in this browser'", 'save indicator after a run', 20000);
  assert.equal(await page.eval("document.getElementById('autosave-status').textContent"), 'Not saved to a file · kept for recovery in this browser');
  // n_eff with 8 decimals in the mode list as in the modes table; plot axes and the inspector in nm
  const resultsView = await page.eval("({options:[...document.querySelectorAll('#field-mode option')].map(o=>o.textContent),values:[...document.querySelectorAll('#modes-table [data-neff]')].map(e=>e.textContent),polarization:[...document.querySelectorAll('#modes-table [data-polarization]')].map(e=>e.textContent),loss:[...document.querySelectorAll('#modes-table [data-loss]')].map(e=>e.textContent),area:[...document.querySelectorAll('#modes-table [data-area]')].map(e=>({text:e.textContent,value:Number(e.dataset.areaValue),title:e.title})),areaSource:[...document.querySelectorAll('#run-details .pair')].map(e=>e.textContent).find(t=>/^Effective area/.test(t))||null,head:[...document.querySelectorAll('#modes-table thead th')].map(e=>e.textContent),lossless:document.getElementById('lossless-note')?.textContent||null,probe:[...document.querySelectorAll('.probe-controls label')].map(l=>l.firstChild.textContent),pin:document.getElementById('pin-run')?.textContent||null,imports:document.getElementById('import-runs')?.textContent})");
  stage('results view', resultsView);
  for (const option of resultsView.options) assert.match(option, /^Mode \d · (TE-like|TM-like|hybrid|pair) · n_eff \d\.\d{8}$/);
  assert.deepEqual(resultsView.head, ['Mode', 'n_eff', 'Polarization', 'Loss', 'A_eff (µm²)']);
  // A_eff of each mode in µm² from the engine's saved value (a 600 × 300 nm strip: a few tenths of a µm²)
  assert.equal(resultsView.area.length, 2);
  assert.equal(resultsView.areaSource, 'Effective areacomputed by the engine from the saved field');
  for (const a of resultsView.area) {
    assert.match(a.text, /^\d\.\d{4}$/); assert.ok(a.value > 0.05e-12 && a.value < 1e-12, a.value);
    assert.equal(a.text, (a.value * 1e12).toPrecision(4)); assert.equal(a.title, 'Effective area (∫|E|²)²/∫|E|⁴ over the window, all three field components');
  }
  // a TM-like cell names its TM share first: "TM-like · 96.9 % TM (3.1 % TE)"
  assert.equal(resultsView.polarization.length, 2); for (const p of resultsView.polarization) assert.match(p, /^(?:(?:TE-like|hybrid) · \d+\.\d % TE|TM-like · \d+\.\d % TM \(\d+\.\d % TE\))$/);
  // the modes table first, then the field plot with its sample and line profile
  const order = await page.eval("({table:!!(document.getElementById('modes-table').compareDocumentPosition(document.querySelector('.field-result'))&Node.DOCUMENT_POSITION_FOLLOWING)})");
  stage('modes table first', order); assert.ok(order.table, 'the modes table comes before the field plot');
  // round 9 (J8): a lossless result reads 0 dB/cm; the cell's help and the note say it is absorption only
  assert.deepEqual(resultsView.loss, ['0 dB/cm', '0 dB/cm']); assert.match(resultsView.lossless, /^Absorption only: all materials have k = 0/);
  const lossTitles = await page.eval("[...document.querySelectorAll('#modes-table [data-loss]')].map(e=>e.title)");
  assert.deepEqual(lossTitles, [resultsView.lossless, resultsView.lossless]);
  assert.equal(resultsView.options[0].split('n_eff ')[1], resultsView.values[0]);
  assert.deepEqual(resultsView.probe, ['x [nm]', 'y [nm]']);
  // an unnamed run offers no separate Pin button: naming it pins it
  assert.equal(resultsView.pin, null); assert.equal(resultsView.imports, 'Add runs from file (inputs unchanged)');
  await page.onElement('function(selector){const c=this.querySelector(selector),r=c.getBoundingClientRect();c.dispatchEvent(new MouseEvent("click",{bubbles:true,clientX:r.left+r.width/2,clientY:r.top+r.height/2}));return true}', '#optical-field'); await sleep(200);
  const probed = await page.eval("({x:document.getElementById('probe-x').value,out:document.getElementById('field-probe').textContent})");
  stage('probe in nm', probed); assert.match(probed.out, /^At \(−?\d+(\.\d)?, −?\d+(\.\d)?\) nm: /); assert.ok(Math.abs(Number(probed.x)) <= 1500, probed.x);
  // naming a run with Enter pins it
  await page.onElement('function(selector){const e=this.querySelector(selector);e.focus();e.select();return true}', '#run-name-input');
  await page.call('Input.insertText', {text: 'design A'});
  for (const type of ['keyDown', 'keyUp']) await page.call('Input.dispatchKeyEvent', {type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, text: type === 'keyDown' ? '\r' : undefined});
  await sleep(150);
  const named = await text('.run-item'); stage('run named', {item: named}); assert.match(named, /^Pinned · Run 1 · design A · 600 × 300 nm/);
  // the run list gives the time with seconds, so runs of the same minute read apart
  assert.match(named, / · \d{1,2}:\d\d:\d\d(?: [AP]M)?$/);
  // a pinned run offers Unpin; after it, Enter in Run name pins it again
  assert.equal(await text('#pin-run'), 'Unpin this run'); await page.click('#pin-run'); await sleep(150);
  assert.equal(await page.eval("document.getElementById('pin-run')"), null); assert.match(await text('.run-item'), /^Run 1 · design A · /);
  await page.onElement('function(selector){const e=this.querySelector(selector);e.focus();return true}', '#run-name-input');
  for (const type of ['keyDown', 'keyUp']) await page.call('Input.dispatchKeyEvent', {type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, text: type === 'keyDown' ? '\r' : undefined});
  await sleep(150); assert.match(await text('.run-item'), /^Pinned · Run 1 · design A · /); assert.equal(await text('#pin-run'), 'Unpin this run');
  await toGeometry(); await page.type('#shape-w', 700); assert.equal(await page.eval("document.getElementById('shape-x').value"), '-350');
  assert.match(await text('#file-status'), /^Width set to 700 nm\. Left x moved to −350 nm to keep the centre\. /);
  // an input edit takes the Study step back from Run complete to Ready to run
  const edited = await text('#workflow .workflow-step:nth-child(4)'); stage('input edited after run', {study: edited}); assert.match(edited, /Ready to run/);
  assert.deepEqual(await opticalSequence(), {heading: 'Run 1 · design A · current inputs differ from this run', status: 'Run 1 · design A · current inputs differ from this run · press Run to compute them'});
  // while an input error holds Run, the heading repeats the footer instead of asking for a Run
  await page.type('#shape-w', 99999);
  const held = await opticalSequence(); stage('input error holds Run', held);
  assert.deepEqual(held, {heading: 'Input errors · correct or restore the last valid values', status: 'Input errors · correct or restore the last valid values'});
  await page.type('#shape-w', 700);
  assert.deepEqual(await opticalSequence(), {heading: 'Run 1 · design A · current inputs differ from this run', status: 'Run 1 · design A · current inputs differ from this run · press Run to compute them'});
  await runAndWait();
  await page.click('nav [data-page=Compare]'); await sleep(500);
  const before = await delta(); assert.ok(before, 'comparison shows a delta n_eff');
  const neffTable = await compareTableRows();
  stage('two designs compared', {deltaNeff: before, table: neffTable});
  assert.ok(neffTable, 'Compare shows the n_eff table'); assert.equal(neffTable.rows.length, 2);
  assert.equal(neffTable.caption, 'Modes of A and B matched by field overlap');
  assert.deepEqual(neffTable.head.slice(0, 4), ['Modes', 'Polarization A', 'Polarization B', 'Overlap']);
  assert.match(neffTable.head[4], /^n_eff A Run 1 · design A · 600 × 300 nm · Silicon · λ 1550 nm$/); assert.match(neffTable.head[5], /^n_eff B Run 2 · 700 × 300 nm · Silicon · λ 1550 nm$/);
  assert.deepEqual(neffTable.head.slice(8), ['A_eff A (µm²)', 'A_eff B (µm²)']);
  // both sides of a matched row give their A_eff in µm²
  for (const row of neffTable.rows) assert.match(row[8] + ' ' + row[9], /^\d\.\d{4} \d\.\d{4}$/);
  assert.equal(neffTable.rows[0][0], 'A mode 1 ↔ B mode 1');
  assert.equal(neffTable.rows[0][6], before, 'the table and the sentence give the same Δn_eff');
  // the field panels do not repeat the name, and come before the n_eff table
  const panels = await page.eval("({headings:[...document.querySelectorAll('.compare-grid h3')].map(h=>h.textContent),plotsFirst:!!(document.querySelector('.compare-grid').compareDocumentPosition(document.getElementById('compare-neff'))&Node.DOCUMENT_POSITION_FOLLOWING),plotTop:Math.round(document.getElementById('compare-field-a').getBoundingClientRect().top+scrollY),viewport:innerHeight})");
  stage('compare panels', panels);
  assert.deepEqual(panels.headings, ['A · Run 1 · design A · 600 × 300 nm · Silicon · λ 1550 nm', 'B · Run 2 · 700 × 300 nm · Silicon · λ 1550 nm']);
  assert.ok(panels.plotsFirst, 'field plots before the n_eff table');
  await page.screenshot('compare');
  await page.click('#save-session');
  let sessionFile;
  for (let i = 0; i < 100 && !sessionFile; i++) { sessionFile = (await readdir(downloads)).find(f => f.endsWith('.json')); if (!sessionFile) await sleep(100); }
  assert.ok(sessionFile, 'Save session downloaded a file');
  const session = JSON.parse(await readFile(join(downloads, sessionFile), 'utf8'));
  const savedHeader = await page.eval("document.getElementById('project').textContent"), savedMessage = await page.eval("document.getElementById('file-status').textContent");
  stage('session saved', {file: sessionFile, runs: session.runs?.length, header: savedHeader, message: savedMessage});
  assert.equal(session.runs?.length, 2);
  assert.match(sessionFile, /^optical-waveguide-session-\d{4}-\d{2}-\d{2}-\d{4}\.json$/);
  assert.ok(savedMessage.startsWith(`Session file ${sessionFile} sent to the browser's downloads (check your Downloads folder)`), savedMessage);
  assert.ok(savedHeader.startsWith(`Optical waveguide / Session file ${sessionFile} sent to your browser's Downloads · `), savedHeader);
  assert.doesNotMatch(savedHeader, /saved|disk/i, 'the title never claims the file reached the disk');
  // the footer repeats the title's save indicator and never says "pending"
  const savedFooter = await page.eval("document.getElementById('autosave-status').textContent");
  assert.equal('Optical waveguide / ' + savedFooter, savedHeader); assert.doesNotMatch(savedFooter, /pending/i);
  await page.until("/^Browser recovery updated/.test(document.getElementById('notebook-recovery-detail').textContent)", 'browser recovery updated', 20000);

  // Restart with the page open: Run reconnects and asks to run again.
  const stopped = await stopServer(server);
  stage('server stopped', stopped);
  // a server still running would answer the restart check and hide a failed restart
  if (stopped.exit === null && stopped.signal === null) throw new Error('Studio did not stop within 15 s');
  server = await startServer('server-2');
  await toGeometry(); await page.click('#run-optical');
  await page.until("/Studio was restarted/.test(document.getElementById('job-message').textContent)&&/^Connected/.test(document.getElementById('connection-status').textContent)", 'reconnect after restart', 20000);
  stage('reconnected after restart', {message: await page.eval("document.getElementById('job-message').textContent")});

  // Reload: the start page offers the last session; recovering it restores the comparison.
  await page.call('Page.reload');
  // round 9 (J3): the one stored session is the optical one, so the Optical waveguide card resumes
  // it and no box above lists it again; the session file route and its note are beside the card's offer
  await page.until("!!document.querySelector('#resume-optical')", 'resume offer');
  const card = await page.eval("(()=>{const r=document.getElementById('resume-optical').getBoundingClientRect();return {top:Math.round(r.top),bottom:Math.round(r.bottom),inView:r.top>=0&&r.bottom<=innerHeight}})()");
  stage('resume card', card); assert.ok(card.inView, 'the Optical waveguide resume offer inside the first viewport');
  // the routes back say which copy is durable
  const routes = await page.eval("({latest:document.getElementById('resume-optical').textContent,listed:[...document.querySelectorAll('[data-resume-record]:not(#resume-optical)')].map(b=>b.textContent),box:!!document.querySelector('.resume-card'),open:document.getElementById('resume-open-file').textContent,beside:!!document.getElementById('resume-optical').closest('.card-slot').querySelector('#resume-open-file'),note:document.querySelector('.resume-portable')?.textContent,footer:document.getElementById('autosave-status').textContent})");
  stage('routes back', routes);
  // the offer names the session file the record was last sent to
  assert.ok(routes.latest.startsWith(`Resume Optical waveguide · Run 1 · design A, Run 2 · file ${sessionFile} · `), routes.latest); assert.equal(routes.open, 'Open session file (portable)…');
  assert.deepEqual(routes.listed, [], 'the record the card resumes is not listed again above it'); assert.equal(routes.box, false);
  assert.ok(routes.beside, 'Open session file is beside the card\'s Resume');
  assert.equal(routes.note, 'A session file is the copy that moves between computers; browser recovery stays in this browser.');
  assert.equal(routes.footer, 'Last session kept in this browser · 2 runs');
  await page.screenshot('resume-card');
  // a fresh page holds nothing an open would lose, so recovery asks nothing
  await page.click('#resume-optical'); await page.until("!!document.getElementById('compare-neff')", 'recovered comparison');
  assert.equal(await page.eval("!!document.querySelector('dialog[open]')"), false, 'no confirmation over an untouched workspace');
  const after = await delta(), recoveredHeader = await page.eval("document.getElementById('project').textContent");
  stage('comparison recovered', {deltaNeff: after, header: recoveredHeader}); assert.equal(after, before);
  assert.ok(recoveredHeader.includes(`Recovered from this browser (last sent to a file: ${sessionFile} at `), 'the recovered title says it was recovered and names the last session file as history: ' + recoveredHeader);
  // the recovered run is current, and the dock and footer say where it came from
  const recoveredSequence = await opticalSequence(); stage('recovered sequence', recoveredSequence);
  assert.deepEqual(recoveredSequence, {heading: 'Run 2 · recovered from this browser, not recomputed', status: 'Run 2 · recovered from this browser, not recomputed · press Run to compute it here'});
  // the older run viewed: the step bar, the result and its settings all say the current inputs
  // differ from this run, naming both, and none speaks of edits (there were none)
  await page.click('nav [data-page=Results]'); await page.until("!!document.querySelector('.run-item')", 'run list');
  await page.onElement('function(selector){[...this.querySelectorAll(selector)].find(b=>/^Pinned · Run 1 · design A/.test(b.textContent)).click();return true}', '.run-item');
  await page.until("/600 × 300 nm/.test(document.querySelector('#canvas p')?.textContent||'')", 'older run shown');
  const viewed = await page.eval("({step:[...document.querySelectorAll('#workflow .workflow-step')][4]?.innerText.replace(/\\s+/g,' '),result:document.querySelector('#canvas p').textContent,inputs:[...document.querySelectorAll('#inspector .pair')].find(p=>p.firstElementChild?.textContent==='Inputs')?.lastElementChild.textContent,header:document.getElementById('project').textContent})");
  stage('older run viewed', viewed);
  assert.equal(viewed.step, '5. Results Current inputs differ from this run');
  // round 9 (J4): the line under the heading names each difference once
  assert.match(viewed.result, /^Current inputs differ from this run: this run 600 × 300 nm · Silicon, current 700 × 300 nm · Silicon; unchanged: λ 1550 nm · core mesh \d+ nm$/);
  for (const part of ['600 × 300 nm', '700 × 300 nm', 'λ 1550 nm']) assert.equal(viewed.result.split(part).length, 2, part);
  assert.equal(viewed.inputs, 'Current inputs differ from this run: this run 600 × 300 nm · Silicon, current 700 × 300 nm · Silicon');
  for (const t of Object.values(viewed)) assert.doesNotMatch(t, /edits are kept/);
  // round 9 (J5): the dock, the footer, the title and the step bar describe the viewed run, run 1
  const viewedNames = await opticalSequence(); stage('older run named', {...viewedNames, header: viewed.header});
  assert.deepEqual(viewedNames, {heading: 'Run 1 · design A · current inputs differ from this run', status: 'Run 1 · design A · current inputs differ from this run · Run 2 has them'});
  assert.match(viewed.header, / · viewing Run 1 · design A, which used other inputs$/); assert.doesNotMatch(viewed.header, /Unsaved inputs/);
  assert.equal(await page.eval("document.getElementById('autosave-status').textContent"), viewed.header.replace(/^Optical waveguide \/ /, ''));
  assert.match(await text('.run-item[aria-pressed=true]'), /^Pinned · Run 1 · design A · /);
  // a name applied on leaving the field (change, no redraw) reaches the dock, the footer and the title too
  // the name is passed as an argument to a fixed function, so no page code is built from it
  const renameOnBlur = name => page.onElement("function(name){const e=this.getElementById('run-name-input');e.value=name;e.dispatchEvent(new Event('change'));return true}", name);
  await renameOnBlur('design A2'); await sleep(200);
  const blurNamed = await page.eval("({heading:document.querySelector('.dock-title>span').textContent,status:document.getElementById('status').textContent,header:document.getElementById('project').textContent})");
  stage('renamed on blur', blurNamed);
  for (const t of Object.values(blurNamed)) assert.match(t, /Run 1 · design A2\b/);
  await renameOnBlur('design A'); await sleep(200); assert.match(await page.eval("document.querySelector('.dock-title>span').textContent"), /^Run 1 · design A · /);
  // round 9 (J1): the dock note on Results says Compare matches modes by field overlap
  assert.match(await text('#sequence'), /Compare matches modes by field overlap/); assert.doesNotMatch(await text('#sequence'), /not matched between runs/);
  // round 9 (J4): the Inputs label of Selected run is one line at 1440 × 900 and 390 × 844
  const labelLines = () => page.eval("(()=>{const s=[...document.querySelectorAll('#inspector .pair>span')].find(e=>e.textContent==='Inputs');const r=document.createRange();r.selectNodeContents(s);return new Set([...r.getClientRects()].map(x=>Math.round(x.top))).size})()");
  for (const [width, height, mobile] of [[1440, 900, false], [390, 844, true]]) {
    await page.call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile}); await sleep(300);
    const lines = await labelLines(); stage('Inputs label lines', {width, lines}); assert.equal(lines, 1, `the Inputs label wraps at ${width} px`);
  }
  await noOverflow('older run viewed');
  // the newer run viewed: every place says it is the result of the current inputs
  await page.onElement('function(selector){[...this.querySelectorAll(selector)].find(b=>/^Run 2 · 700 × 300 nm/.test(b.textContent)).click();return true}', '.run-item');
  await page.until("/^Result for the current inputs/.test(document.querySelector('#canvas p')?.textContent||'')", 'newer run shown');
  assert.equal(await page.eval("[...document.querySelectorAll('#workflow .workflow-step')][4]?.innerText.replace(/\\s+/g,' ')"), '5. Results Result for these inputs');
  // switching to the heated model says where the optical runs stay, and they come back
  await page.click('nav [data-page=Applications]'); await page.until("!!document.querySelector('[data-template=heated-waveguide]')", 'models page');
  await page.click('[data-template=heated-waveguide]');
  await page.until("/^Heated silicon waveguide ready\\./.test(document.getElementById('file-status').textContent)", 'heated model', 30000);
  const switched = await text('#file-status'); stage('switched to the heated model', {message: switched, header: await page.eval("document.getElementById('project').textContent")});
  // round 9 (J7): one short line, the rest behind More
  const switchedParts = await page.eval("({line:[...document.getElementById('file-status').childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join('').trim(),summary:document.querySelector('#file-status details.message-more>summary')?.textContent,more:document.querySelector('#file-status .message-more-text')?.textContent})");
  stage('switch message parts', switchedParts);
  assert.equal(switchedParts.line, 'Heated silicon waveguide ready. Edit settings and couplings, then press Run. Optical waveguide runs stay in this tab · Models › Optical waveguide returns to them');
  assert.equal(switchedParts.summary, 'More');
  assert.match(switchedParts.more, /^This tab holds 2 runs until it is closed or reloaded\. After that, Models › Optical waveguide › Resume \(browser recovery, which keeps the four newest sessions\)(?: or Open session with \S+\.json)? brings them back\.$/);
  await noOverflow('heated model after optical runs');
  await page.click('nav [data-page=Applications]'); await page.until("!!document.querySelector('[data-template=optical]')", 'models page again');
  await page.click('[data-template=optical]'); await page.until("!!document.querySelector('#shape-w')", 'optical model again');
  assert.equal((await opticalSequence()).heading, 'Run 2 · recovered from this browser, not recomputed', 'the optical runs came back');
  // V17-M2: Compare matches the modes of two runs by field overlap, 500 → 450 nm (both modes
  // matched with overlap >= 0.95, as V15 (a) on the engine); the picker lists matched pairs and
  // the old rank note is gone; the Results sentence names the matching
  for (const width of [500, 450]) { await toGeometry(); await page.type('#shape-w', width); await runAndWait(); }
  const resultsNote = await text('#canvas'); assert.match(resultsNote, /Modes are ranked by effective index\. Compare matches them between runs by field overlap\./);
  await page.click('nav [data-page=Compare]'); await page.until("!!document.getElementById('compare-neff')", 'Compare 500 → 450 nm');
  const matched = await compareTableRows(); stage('V17-M2 Compare 500 → 450 nm', matched);
  assert.match(matched.head[4], /^n_eff A Run 3 · 500 × 300 nm/); assert.match(matched.head[5], /^n_eff B Run 4 · 450 × 300 nm/);
  assert.deepEqual(matched.matched, ['0:0', '1:1']); assert.deepEqual(matched.rows.map(r => r[0]), ['A mode 1 ↔ B mode 1', 'A mode 2 ↔ B mode 2']);
  assert.ok(matched.overlap.length === 2 && matched.overlap.every(v => v >= 0.95), 'overlap >= 0.95: ' + matched.overlap);
  // the polarization cells use the modes table's words: a TM-like cell names its TM share first
  const polarizationCell = /^(?:(?:TE-like|hybrid) · \d+\.\d % TE|TM-like · \d+\.\d % TM \(\d+\.\d % TE\))$/;
  for (const r of matched.rows) { assert.match(r[1], polarizationCell); assert.match(r[2], polarizationCell); assert.match(r[6], /^[+−]\d\.\d{8}$/); }
  assert.equal(matched.note, 'Matched by field overlap ≥ 0.8 on a common grid. A low overlap means the mode changed shape between designs.');
  assert.deepEqual(matched.picker.map(o => o.replace(/ · overlap .*$/, '')), ['A mode 1 ↔ B mode 1', 'A mode 2 ↔ B mode 2']);
  assert.doesNotMatch(await text('#canvas'), /compared by rank|not matched modes|mode rank/i);
  await page.eval("(()=>{const s=document.getElementById('compare-mode');s.value='1';s.dispatchEvent(new Event('change'));})()"); await sleep(300);
  assert.match(await text('#compare-shown-a'), /^Mode 2 · /, 'the plots show the chosen matched pair');
  assert.match(await text('#compare-shown-b'), /^Mode 2 · /); assert.match(await text('#compare-description'), /Shown: A mode 2 ↔ B mode 2, overlap /);
  // round 9 (J1): the dock note on Compare agrees with the table caption
  assert.match(await text('#sequence'), /Compare matches modes by field overlap/); assert.doesNotMatch(await text('#sequence'), /not matched between runs/);
  // round 9 (J6, J4): the closed picker shows the whole pair with its overlap and polarization, and
  // every number cell keeps its value and unit on one line, at 1440 × 900 and 390 × 844
  const closedPicker = () => page.eval(`(()=>{const s=document.getElementById('compare-mode'),o=s.options[s.selectedIndex],c=document.createElement('canvas').getContext('2d'),st=getComputedStyle(s);c.font=st.font;
    const lines=e=>{const r=document.createRange();r.selectNodeContents(e);return new Set([...r.getClientRects()].map(x=>Math.round(x.top))).size};
    return {text:o.textContent,need:Math.ceil(c.measureText(o.textContent).width)+32,width:s.clientWidth,cells:[...document.querySelectorAll('#compare-neff td.num')].map(e=>[e.textContent,lines(e)]).filter(x=>x[1]!==1),percent:[...document.querySelectorAll('#compare-neff [data-delta-percent]')].map(e=>e.textContent)}})()`);
  for (const [width, height, mobile] of [[1440, 900, false], [390, 844, true]]) {
    await page.call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile}); await sleep(300);
    const picker = await closedPicker(); stage('closed matched-modes picker', {width, ...picker});
    assert.match(picker.text, /^A mode 2 ↔ B mode 2 · overlap \d\.\d\d · (?:TE-like|TM-like|hybrid|A \S+, B \S+)$/);
    assert.ok(picker.need <= picker.width, `the closed picker needs ${picker.need} px, has ${picker.width} px at ${width}`);
    assert.deepEqual(picker.cells, [], `number cells wrap at ${width} px`); assert.ok(picker.percent.length === 2 && picker.percent.every(t => / %$/.test(t)), JSON.stringify(picker.percent));
  }
  await noOverflow('compare matched');
  await page.screenshot('compare-matched');
  // Results: the line profile follows the Mode picker (it read the mode once before this check)
  await page.click('nav [data-page=Results]'); await page.until("!!document.getElementById('field-mode')", 'Results field');
  await page.eval("(()=>{const d=document.querySelector('.line-profile');if(!d.open)d.querySelector('summary').click();})()"); await sleep(300);
  await page.eval("(()=>{const s=document.getElementById('field-mode');s.value='1';s.dispatchEvent(new Event('change'));})()"); await sleep(300);
  const profileMode = await page.eval("document.querySelector('.line-profile p[role=status]').textContent"); stage('Results profile after Mode 2', {profileMode});
  assert.match(profileMode, / · mode 2 · /, 'the profile shows the chosen mode');
  await page.eval("(()=>{const s=document.getElementById('field-mode');s.value='0';s.dispatchEvent(new Event('change'));document.querySelector('.line-profile summary').click();})()"); await sleep(300);

  // Joule heating (checks JB1-JB7, pre-registered 2026-11-21 with values measured on Linux): the
  // default two-material strip by Picard and by Newton, a server refusal shown with its text, and
  // constant materials. The region mesh of the same document is not the same on every platform
  // (Linux x86-64: 288 nodes, 526 triangles; macOS arm64: 289, 528), so values that depend on the
  // mesh are checked within the discretization error at this element size (about 2e-3 of the
  // temperature rise in the strip convergence study of test_joule_temperature_regions.py, so about
  // 0.04 K of this 22 K rise; 0.01 K is allowed), and the checks that do
  // not depend on it stay tight: the power balance on each mesh, Newton against Picard on the same
  // mesh, the potential's fixed values and the uniform strip's exact power. Bit-for-bit equality
  // with simcase.run on one mesh is tests/simcase/test_studio_joule_regions.py.
  const canvasRange = async () => {
    const label = await page.eval("document.getElementById('joule-field-canvas')?.getAttribute('aria-label')||''");
    const m = label.match(/^(.*) (\S+) to (\S+) (\S+)$/); assert.ok(m, 'result canvas label: ' + label);
    return {field: m[1], min: Number(m[2]), max: Number(m[3]), unit: m[4]};
  };
  const jouleRun = async (expected, label) => {
    await page.until("!document.getElementById('run-joule').hidden&&!document.getElementById('run-joule').disabled", 'Joule run enabled');
    await page.click('#run-joule');
    await page.until(`document.getElementById('run-joule').textContent==='Run Joule heating study'&&(${expected})`, label, 120000);
    await sleep(300);
  };
  const toJoule = async node => { await page.click('nav [data-page=Model]'); await sleep(200); await page.click(`#tree [data-node="${node}"]`); await sleep(200); };
  const logIs = pattern => `${pattern}.test(document.querySelector('#solver-log summary')?.textContent||'')&&!document.getElementById('solver-log').hidden`;

  await page.click('nav [data-page=Applications]'); await page.until("!!document.querySelector('[data-template=joule]')", 'applications page');
  await page.click('[data-template=joule]');
  await page.until("!!document.querySelector('svg[data-geometry-view=joule]')&&!document.getElementById('run-joule').hidden", 'Joule application');
  const drawn = await page.eval("({shapes:document.querySelectorAll('svg[data-geometry-view=joule] [data-joule-pick]').length,sides:document.querySelectorAll('svg[data-geometry-view=joule] [data-joule-side]').length})");
  stage('JB1 Joule application', drawn); assert.deepEqual(drawn, {shapes: 1, sides: 4});
  // choosing a template opens no confirmation (workspace-app.mjs); a dialog here would be a change to check
  assert.equal(await page.eval("!!document.querySelector('dialog[open]')"), false, 'no dialog after choosing Joule heating');
  await page.screenshot('joule-model');

  await jouleRun(logIs('/Picard \\d+ iterations/'), 'Joule Picard run');
  const picardLog = await text('#solver-log summary'), picardSettings = await text('#inspector');
  const picardN = Number(picardLog.match(/Picard (\d+) iterations/)[1]), picardT = await canvasRange();
  stage('JB2 Picard result', {log: picardLog, temperature: picardT, settings: picardSettings.slice(0, 260)});
  assert.ok(picardN >= 28 && picardN <= 34, 'Picard iterations ' + picardN);
  // the displayed values (7 significant digits), parsed and compared within a tolerance
  const shown = (settings, label, unit) => Number(settings.match(new RegExp(label + ' (\\S+) ' + unit))?.[1]);
  const nodes = shown(picardSettings, 'Nodes', 'Triangles'), triangles = Number(picardSettings.match(/Triangles (\d+)/)?.[1]);
  assert.ok(nodes >= 270 && nodes <= 310 && triangles >= 500 && triangles <= 560, `mesh ${nodes} nodes, ${triangles} triangles`);
  const balances = ['Supplied electric power', 'Joule power', 'Outward heat'].map(label => shown(picardSettings, label, 'W/m'));
  // the balance on each mesh to the display's resolution; the value within 1e-4 of Linux's 16.67289 W/m
  assert.ok(Math.max(...balances) - Math.min(...balances) <= 2e-5 && Math.abs(balances[0] - 16.67289) <= 16.67289e-4, 'balances ' + balances);
  const tmax = shown(picardSettings, 'Maximum temperature', 'K');
  assert.ok(Math.abs(tmax - 321.827) <= 0.01, 'maximum temperature ' + tmax);
  assert.equal(picardT.field, 'Temperature T'); assert.equal(picardT.unit, 'K');
  assert.ok(Math.abs(picardT.min - 300) <= 1e-9 && Math.abs(picardT.max - tmax) <= 1e-4, 'temperature range ' + JSON.stringify(picardT));
  await page.screenshot('joule-picard');
  await page.choose('#joule-field', 'electric_potential'); await sleep(300);
  const potential = await canvasRange();
  stage('JB3 potential field', potential);
  assert.equal(potential.field, 'Electric potential V'); assert.equal(potential.unit, 'V');
  assert.ok(Math.abs(potential.min) <= 1e-12 && Math.abs(potential.max - 0.2) <= 1e-12, 'potential range ' + JSON.stringify(potential));
  await page.choose('#joule-field', 'temperature'); await sleep(300);

  await toJoule('Study');
  await page.choose('[data-joule-select="iteration.method"]', 'newton');
  const newtonForm = await page.eval("({relaxation:!!document.querySelector('[data-joule=\"iteration.relaxation_factor\"]'),limit:document.querySelector('[data-joule=\"iteration.iteration_limit\"]').value})");
  stage('JB4 Newton chosen', newtonForm); assert.deepEqual(newtonForm, {relaxation: false, limit: '17'});
  await jouleRun(logIs('/Newton \\d+ steps?/'), 'Joule Newton run');
  const newtonLog = await text('#solver-log summary'), newtonT = await canvasRange();
  const newtonM = Number(newtonLog.match(/Newton (\d+) step/)[1]);
  const table = await page.eval("document.querySelector('#solver-log table')?.getAttribute('aria-label')");
  stage('JB4 Newton result', {log: newtonLog, temperature: newtonT, table});
  assert.ok(newtonM >= 2 && newtonM <= 5, 'Newton steps ' + newtonM); assert.equal(table, 'Newton steps');
  assert.match(await text('#inspector'), /Newton steps \d+/);
  assert.ok(Math.abs(newtonT.max - picardT.max) <= 1e-6 && Math.abs(newtonT.min - picardT.min) <= 1e-6, 'Newton and Picard temperatures');
  await page.screenshot('joule-newton');

  await toJoule('Study'); await page.type('[data-joule="iteration.iteration_limit"]', 1);
  await page.until("!document.getElementById('run-joule').hidden&&!document.getElementById('run-joule').disabled", 'Joule run enabled');
  await page.click('#run-joule');
  await page.until("/Newton iteration did not converge/.test(document.body.innerText)&&document.getElementById('run-joule').textContent==='Run Joule heating study'", 'Newton refusal shown', 120000);
  const refusal = await page.eval("(document.body.innerText.match(/the Newton iteration did not converge[^\\n]*/)||[''])[0]");
  stage('JB5 refusal shown', {message: refusal});
  assert.match(refusal, /^the Newton iteration did not converge after 1 steps: maximum iterations exceeded\. Inputs and earlier results are unchanged\.$/);
  await page.click('nav [data-page=Results]'); await sleep(300);
  assert.match(await text('#solver-log summary'), new RegExp('Newton ' + newtonM + ' step'), 'the earlier result is kept');

  await toJoule('Materials');
  for (const i of [0, 1]) await page.choose(`[data-joule-select="materials.${i}.sigma.model"]`, 'constant');
  await toJoule('Study');
  const steady = await text('#inspector');
  stage('JB6 constant materials', {physics: steady.match(/Physics (\S+)/)?.[1], iteration: /Iteration method/.test(steady)});
  assert.match(steady, /Physics joule\.steady2d/); assert.doesNotMatch(steady, /Iteration method/);
  await jouleRun(logIs('/One coupled solve/'), 'Joule steady run');
  // Choosing "constant" gives each material 1000 S/m, so the strip is uniform: the power per
  // depth is V^2 sigma h / L = 0.2^2 V^2 x 1000 S/m x 1 mm / 2 mm = 20 W/m (P1 is exact here).
  const steadySettings = await text('#inspector');
  const power = Number(steadySettings.match(/Joule power (\S+) W\/m/)?.[1]);
  stage('JB6 steady result', {log: await text('#solver-log summary'), jouleW_per_m: power});
  assert.ok(Math.abs(power - 20) <= 20e-6, 'uniform strip Joule power ' + power);
  await page.screenshot('joule-steady');

  // Round 9 (J2, J3): the same two runs opened from their session file, recovered, and opened again
  // on new pages are one session: the Models page offers them once, on the Optical waveguide card
  // (which names the file), and the box above lists only other sessions. Before round 9 each open
  // or recovery re-marked the runs' origin, so the store kept the earlier copy as another session.
  const setFile = async (selector, path) => {
    const {root} = await page.call('DOM.getDocument');
    const {nodeId} = await page.call('DOM.querySelector', {nodeId: root.nodeId, selector});
    await page.call('DOM.setFileInputFiles', {nodeId, files: [path]});
  };
  const answerDialogs = async (done, label) => {
    const end = Date.now() + 60000;
    while (Date.now() < end) {
      if (await page.eval(done)) return;
      if (await page.eval("!!document.getElementById('leave-confirm')?.open")) await page.click('#leave-go');
      else if (await page.eval("!!document.getElementById('load-confirm')?.open")) await page.click('#confirm-load');
      await sleep(150);
    }
    throw new Error('timed out: ' + label);
  };
  const recoveryUpdated = "/^Browser recovery updated/.test(document.getElementById('notebook-recovery-detail').textContent)";
  const freshPage = async label => { await page.call('Page.reload'); await page.until("/^Connected/.test(document.getElementById('connection-status').textContent)&&!!document.querySelector('[data-template=optical]')&&!document.getElementById('recover-notebook').disabled", label, 30000); };
  const openFile = async label => {
    await page.eval("document.getElementById('notebook-recovery-detail').textContent=''");
    await setFile('#session-file', join(downloads, sessionFile));
    await answerDialogs(`/^Opened /.test(document.getElementById('autosave-status').textContent)&&${recoveryUpdated}`, label);
  };
  await freshPage('J2 page 1'); await openFile('J2 open 1');
  await freshPage('J2 page 2'); await page.until("!!document.getElementById('resume-optical')", 'J2 resume offer');
  await page.eval("document.getElementById('notebook-recovery-detail').textContent=''"); await page.click('#resume-optical');
  await answerDialogs(`/^Recovered from this browser/.test(document.getElementById('autosave-status').textContent)&&${recoveryUpdated}`, 'J2 resumed');
  await freshPage('J2 page 3'); await openFile('J2 open 2');
  await freshPage('J2 page 4'); await page.until("!!document.getElementById('resume-optical')", 'J2 Models page');
  await sleep(500);
  const offers = await page.eval(`import('/workspace-assets/workspace-notebook-recovery.mjs').then(async m=>{const s=m.indexedNotebookStore();const latest=await s.load(),earlier=await s.loadEarlier();
    const record=i=>Number(i)<0?latest:earlier[Number(i)],card=document.getElementById('resume-optical');
    const top=[...document.querySelectorAll('.resume-card [data-resume-record]')].map(b=>({record:b.dataset.resumeRecord,text:b.textContent}));
    return {card:{record:card.dataset.resumeRecord,text:card.textContent},top,keys:[card.dataset.resumeRecord,...top.map(t=>t.record)].map(i=>{const d=JSON.parse(record(i).session);return JSON.stringify({model:d.input??d.document,runs:(d.runs||[]).map(r=>[r.job,r.label||'',r.pinned===true])});}),stored:earlier.length};})`);
  stage('J2 one entry per session', offers);
  assert.ok(offers.card.text.startsWith('Resume Optical waveguide · Run 1 · design A, Run 2 · file ' + sessionFile + ' · '), offers.card.text);
  assert.ok(!offers.top.some(t => t.record === offers.card.record), 'the box above does not list the record the card resumes');
  // compared by the stored inputs and runs themselves, not by the sessionKey under test
  assert.equal(new Set(offers.keys).size, offers.keys.length, 'every offered entry is another session');
  assert.ok(!offers.top.some(t => t.text.includes('Optical waveguide · 2 runs · Run 1 · design A, Run 2')), JSON.stringify(offers.top));
  await noOverflow('J2 Models page');

  assert.deepEqual(report.exceptions, [], 'no uncaught page exceptions');
  assert.deepEqual(report.consoleErrors, [], 'no console.error calls');
  await stopServer(server);
  report.status = 'passed';
} catch (error) {
  report.status = 'failed'; report.error = String(error?.stack || error);
  process.exitCode = 1;
} finally {
  for (const child of owned) if (child.exitCode === null && child.signalCode === null) child.kill();
  await Promise.race([Promise.all(owned.map(c => c.done)), sleep(10000)]);
  await rm(profile, {recursive: true, force: true}).catch(() => {});
  await save();
  console.log('[workspace browser]', report.status, report.error || '');
}
