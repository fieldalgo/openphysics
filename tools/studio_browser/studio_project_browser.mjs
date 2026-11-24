// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Real-browser check of project files (P3, docs/packages/simcase/workspace.md "Project files"):
// every model of a Studio tab in one file. At 1440 × 900 and at 390 × 844, by role and accessible
// name (the accessibility tree), with no horizontal page overflow at any step (V-P13):
//   Optical waveguide, 600 × 300 nm, run; 700 × 300 nm with Modes to find 4, run; Heated silicon
//   waveguide, run (with the without-heater result); the project named "Heater study" and File ›
//   Save As heater-study.json (its suggested name); then (V-P7)
//   the Studio server restarted and a new browser with a new profile; File › Open of the file; both
//   models read back the same value strings, marked as read from the file, and no run starts
//   (every POST after the open is a model check, /api/multiphysics/validate).
// Also: V-P1 the file opened and saved again equals the first save but for its save time; V-P11
// the name dialog, Save again under the remembered name and the "downloaded" title; V-P10 the save
// picker stubbed at window.showSaveFilePicker (navigator.webdriver false): Save As writes the
// project, Save writes it again with no dialog, a cancel writes nothing, a failed write leaves the
// old file whole; V-P3 three damaged files refused by name with the tab unchanged. With
// --old-python <python> (a Python whose simcase is an older checkout's), V-P9: that Studio
// refuses the project file with its existing message and keeps its workspace.
// Drives a preinstalled Chrome through the DevTools protocol with Node's built-in fetch and
// WebSocket; no npm package and no browser download. Fails, never skips, when no browser is found.
//
//   node tools/studio_browser/studio_project_browser.mjs --python <python> --output <dir> [--chrome <path>] [--old-python <python>]
import assert from 'node:assert/strict';
import {spawn, spawnSync} from 'node:child_process';
import {existsSync} from 'node:fs';
import {mkdir, mkdtemp, readdir, readFile, rm, stat, writeFile} from 'node:fs/promises';
import {createServer} from 'node:net';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {endScript, launchBrowser} from './browser_launch.mjs';

const args = Object.fromEntries(process.argv.slice(2).reduce((pairs, value, index, all) =>
  index % 2 ? pairs : [...pairs, [value.replace(/^--/, ''), all[index + 1]]], []));
if (!args.python || !args.output) throw new Error('usage: --python <python> --output <dir> [--chrome <path>] [--old-python <python>]');
const out = resolve(args.output);
await mkdir(out, {recursive: true});
const report = {status: 'incomplete', node: process.version, platform: process.platform, stages: [], exceptions: [], consoleErrors: []};
const sleep = ms => new Promise(r => setTimeout(r, ms));
const save = () => writeFile(join(out, 'report.json'), JSON.stringify(report, null, 1) + '\n', 'utf8');
const stage = (name, data = {}) => { report.stages.push({name, ...data}); console.log('[project browser]', name, JSON.stringify(data)); };

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
function launch(command, argv, name, env = {}) {
  const child = spawn(command, argv, {stdio: ['ignore', 'pipe', 'pipe'], env: {...process.env, OPENBLAS_NUM_THREADS: '1', OMP_NUM_THREADS: '1', MKL_NUM_THREADS: '1', ...env}});
  owned.push(child);
  let log = '';
  child.stdout.on('data', x => { log += x; });
  child.stderr.on('data', x => { log += x; });
  child.on('error', e => { log += String(e); });
  child.done = new Promise(r => child.on('close', (exit, signal) => { report[name] = {exit, signal}; writeFile(join(out, name + '.log'), log, 'utf8').then(r, r); }));
  return child;
}
async function stopProcess(child) {
  child.kill(process.platform === 'win32' ? undefined : 'SIGINT');
  await Promise.race([child.done, sleep(15000)]);
  if (child.exitCode === null && child.signalCode === null) { child.kill('SIGKILL'); await Promise.race([child.done, sleep(5000)]); }
}

class Page {
  constructor(url) {
    this.id = 0; this.pending = new Map(); this.ws = new WebSocket(url); this.events = [];
    this.ready = new Promise((r, j) => { this.ws.addEventListener('open', r, {once: true}); this.ws.addEventListener('error', j, {once: true}); });
    this.ws.addEventListener('message', event => {
      const message = JSON.parse(event.data);
      if (message.id) {
        const call = this.pending.get(message.id); if (!call) return;
        this.pending.delete(message.id); clearTimeout(call.timer);
        message.error ? call.reject(new Error(JSON.stringify(message.error))) : call.resolve(message.result);
      } else if (message.method === 'Runtime.exceptionThrown') report.exceptions.push(message.params.exceptionDetails?.exception?.description || message.params.exceptionDetails?.text);
      else if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error') report.consoleErrors.push(message.params.args.map(a => a.value ?? a.description).join(' '));
      else if (message.method === 'Network.requestWillBeSent' || message.method === 'Page.fileChooserOpened') this.events.push(message);
      else if (message.method && this.onEvent) this.onEvent(message);
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
    throw new Error('timed out waiting for ' + label + ' · ' + await this.eval("document.getElementById('file-status')?.textContent").catch(() => ''));
  }
  // Runs a fixed function on the document with the arguments as values, so no page code is built from them.
  async on(declaration, ...values) {
    const {result: document} = await this.call('Runtime.evaluate', {expression: 'document'});
    const result = await this.call('Runtime.callFunctionOn', {objectId: document.objectId, functionDeclaration: declaration,
      arguments: values.map(value => ({value})), awaitPromise: true, returnByValue: true});
    if (result.exceptionDetails) throw new Error('page: ' + (result.exceptionDetails.exception?.description || result.exceptionDetails.text));
    return result.result.value;
  }
  text(selector) { return this.on('function(s){const e=this.querySelector(s);return e?e.textContent:null}', selector); }
  texts(selector) { return this.on('function(s){return [...this.querySelectorAll(s)].map(e=>e.textContent)}', selector); }
  click(selector) { return this.on('function(s){const e=this.querySelector(s);if(!e)throw Error("missing "+s);e.click();return true}', selector); }
  // The one element with this role and accessible name, as assistive technology finds it (the
  // accessibility tree). match: 'exact', or 'start' for a card whose name begins with its title.
  async role(role, name, match = 'exact') {
    const {result: document} = await this.call('Runtime.evaluate', {expression: 'document'});
    const query = match === 'exact' ? {objectId: document.objectId, accessibleName: name, role} : {objectId: document.objectId, role};
    const {nodes} = await this.call('Accessibility.queryAXTree', query);
    // 'start': the name begins with the text, after a card's icon character
    const found = nodes.filter(n => !n.ignored && (match === 'exact' || (n.name?.value ?? '').replace(/^[^\p{L}\p{N}]+/u, '').startsWith(name)));
    if (found.length !== 1) throw new Error(`${found.length} ${role} named ${JSON.stringify(name)}`);
    const {object} = await this.call('DOM.resolveNode', {backendNodeId: found[0].backendDOMNodeId});
    return object.objectId;
  }
  async act(objectId, declaration, ...values) {
    // userGesture: a click by role is a user's click (File › Open's file chooser needs one)
    const result = await this.call('Runtime.callFunctionOn', {objectId, functionDeclaration: declaration, arguments: values.map(value => ({value})), awaitPromise: true, returnByValue: true, userGesture: true});
    if (result.exceptionDetails) throw new Error('page: ' + (result.exceptionDetails.exception?.description || result.exceptionDetails.text));
    return result.result.value;
  }
  async press(role, name, match) { await this.act(await this.role(role, name, match), 'function(){this.click();return true}'); await sleep(200); }
  // typing as a user does: focus, select, insert the text, leave the field
  async fill(role, name, text, match = 'exact') {
    const id = await this.role(role, name, match);
    await this.act(id, 'function(){this.focus();this.select();return true}');
    await this.call('Input.insertText', {text: String(text)});
    await this.act(id, 'function(){this.dispatchEvent(new Event("change",{bubbles:true}));this.blur();return true}');
    await sleep(200);
  }
  async screenshot(name) { const png = await this.call('Page.captureScreenshot', {format: 'png'}); await writeFile(join(out, name + '.png'), Buffer.from(png.data, 'base64')); }
}

const profiles = await mkdtemp(join(tmpdir(), 'openphysics-project-browser-'));
const downloads = join(out, 'downloads');
await mkdir(downloads, {recursive: true});
let browser = null;
try {
  const chrome = findChrome();
  report.chrome = chrome || null;
  if (!chrome) throw new Error('No preinstalled Chrome, Chromium or Edge found; set --chrome or CHROME_PATH. No browser is downloaded.');
  const apiPort = await freePort(), base = `http://127.0.0.1:${apiPort}`;
  // python: another Python, whose simcase is an older checkout's (V-P9)
  const startServer = async (name, python = args.python) => {
    const child = launch(python, ['-I', '-m', 'simcase.studio', '--workspace', '--no-browser', '--port', String(apiPort)], name);
    for (let i = 0; i < 240; i++) { try { if ((await fetch(base + '/workspace')).ok) return child; } catch {} await sleep(250); }
    throw new Error('Studio did not start: ' + name);
  };
  const sandbox = process.getuid?.() === 0 ? ['--no-sandbox'] : [];
  // a browser with a profile of its own; the save picker removed at document start (a headless run
  // cannot answer it), so Save asks for a name in Studio's dialog and the browser downloads the file
  // reuse: the number of an earlier profile, to start the browser again on it (its browser recovery kept)
  let browsers = 0;
  const startBrowser = async (reuse = null) => {
    const n = reuse ?? ++browsers, dir = join(profiles, 'profile-' + n);
    const {target} = await launchBrowser({launch: (command, argv, attempt) => launch(command, argv, `browser-${n}-${attempt}`), command: chrome, freePort, report,
      argv: (port, attempt) => ['--headless=new', '--disable-gpu', ...sandbox, '--no-first-run', '--no-default-browser-check', '--remote-debugging-address=127.0.0.1',
        '--remote-debugging-port=' + port, '--user-data-dir=' + join(dir, 'attempt-' + attempt), '--window-size=1440,900', 'about:blank']});
    const page = new Page(target.webSocketDebuggerUrl); await page.ready;
    for (const domain of ['Runtime', 'Page', 'DOM', 'Accessibility', 'Network']) await page.call(domain + '.enable');
    await page.call('Page.setDownloadBehavior', {behavior: 'allow', downloadPath: downloads});
    await page.call('Page.addScriptToEvaluateOnNewDocument', {source: 'delete window.showSaveFilePicker;delete Window.prototype.showSaveFilePicker;'});
    await page.call('Page.setInterceptFileChooserDialog', {enabled: true});
    page.process = owned.at(-1);
    return page;
  };
  const stopBrowser = async page => { try { await page.call('Browser.close'); } catch {} await Promise.race([page.process.done, sleep(10000)]); };
  const listDownloads = async () => Object.fromEntries(await Promise.all((await readdir(downloads)).filter(n => n.endsWith('.json')).map(async n => [n, (await stat(join(downloads, n))).mtimeMs])));
  const newDownload = async before => { for (let i = 0; i < 300; i++) { const now = await listDownloads(), f = Object.keys(now).find(n => before[n] !== now[n]); if (f) { await sleep(500); return f; } await sleep(100); } throw new Error('no new download'); };
  const withoutTime = text => String(text).replace(/"savedAt":"[^"]*"/, '"savedAt":""');

  let server = await startServer('server-1');
  let page = await startBrowser();
  const size = (width, height, mobile) => page.call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile});
  const overflow = () => page.eval('document.documentElement.scrollWidth-document.documentElement.clientWidth');
  const noOverflow = async label => { const over = await overflow(); assert.ok(over <= 0, `${label}: the page overflows by ${over}px`); };
  const status = () => page.text('#file-status');
  const title = () => page.text('#project');
  const footer = () => page.text('#autosave-status');
  // File › Open by role and name: the file chooser it opens is answered at the DevTools boundary
  const openFile = async path => {
    const seen = page.events.length;
    await page.press('button', 'File'); await page.press('menuitem', 'Open…');
    for (let i = 0; i < 100 && !page.events.slice(seen).some(e => e.method === 'Page.fileChooserOpened'); i++) await sleep(100);
    const chooser = page.events.slice(seen).find(e => e.method === 'Page.fileChooserOpened');
    assert.ok(chooser, 'File › Open opens a file chooser');
    await page.call('DOM.setFileInputFiles', {files: [path], backendNodeId: chooser.params.backendNodeId});
  };
  const opticalValues = () => page.eval("({neff:[...document.querySelectorAll('#modes-table [data-neff]')].map(e=>e.textContent),te:[...document.querySelectorAll('#modes-table tbody tr')].map(r=>r.cells[2]?.textContent??null)})");
  const heatedValues = () => page.eval("['[data-neff=\"1\"]','[data-neff-alone=\"1\"]','[data-neff-shift=\"1\"]'].map(s=>document.querySelector(s)?.textContent??null)");
  const runOptical = async label => {
    await page.until("!document.getElementById('run-optical').disabled", label + ': Run enabled', 60000);
    await page.eval("document.getElementById('job-message').textContent=''");
    await page.press('button', 'Run study');
    await page.until("/complete/i.test(document.getElementById('job-message').textContent)&&document.getElementById('run-optical').textContent==='Run study'", label, 180000);
    await page.until("!!document.getElementById('modes-table')", label + ': modes table');
  };
  // the run list item whose text begins with the run's number, by its own text
  const showRun = async number => {
    await page.on('function(prefix){const b=[...this.querySelectorAll(".run-item")].find(e=>e.textContent.startsWith(prefix)||e.textContent.includes(" · "+prefix));if(!b)throw Error("no "+prefix);b.click();return true}', `Run ${number} `);
    await sleep(400); await page.until("!!document.getElementById('modes-table')", 'run ' + number + ' shown');
  };

  const values = {};
  for (const [width, height, mobile, tag] of [[1440, 900, false, 'wide'], [390, 844, true, 'phone']]) {
    if (tag === 'phone') { await stopBrowser(page); page = await startBrowser(); }
    await size(width, height, mobile);
    await page.call('Page.navigate', {url: base + '/workspace'});
    await page.until("/^Connected/.test(document.getElementById('connection-status').textContent)&&!!document.querySelector('[data-template=optical]')", 'start page ' + tag);
    // V-P13: every step by role and name, no horizontal overflow at any of them
    await page.press('button', 'Optical waveguide', 'start'); await page.until("!!document.getElementById('shape-w')", 'optical model ' + tag); await noOverflow(tag + ' optical');
    assert.match(await title(), /^Untitled project · not saved to a file · /);
    await page.fill('spinbutton', 'Width [nm]', 600); await page.fill('spinbutton', 'Height [nm]', 300); await noOverflow(tag + ' 600 × 300');
    await runOptical(tag + ' run 1'); await noOverflow(tag + ' run 1');
    const run1 = await opticalValues();
    await page.press('tab', 'Model'); await page.press('treeitem', 'Geometry'); await page.until("!!document.getElementById('shape-w')", 'geometry ' + tag);
    await page.fill('spinbutton', 'Width [nm]', 700);
    await page.press('treeitem', 'Optical modes'); await page.until("!!document.getElementById('mode-count-number')", 'optical modes ' + tag);
    await page.fill('spinbutton', 'Modes to find', 4, 'start'); await noOverflow(tag + ' Modes to find 4');
    await runOptical(tag + ' run 2'); await noOverflow(tag + ' run 2');
    const run2 = await opticalValues();
    await page.press('tab', 'Library'); await page.until("!!document.querySelector('[data-template=heated-waveguide]')", 'Library ' + tag); await noOverflow(tag + ' Library');
    await page.press('button', 'Heated silicon waveguide', 'start');
    await page.until("/^Heated silicon waveguide ready\\./.test(document.getElementById('file-status').textContent)", 'heated model ' + tag, 60000);
    assert.equal(await page.eval("!!document.querySelector('dialog[open]')"), false, 'switching models inside a project asks nothing');
    await page.until("!document.getElementById('run-multiphysics').disabled", 'heated Run ' + tag, 60000); await noOverflow(tag + ' heated');
    await page.press('button', 'Run study');
    await page.until("/^[+−]0\\.\\d{8}$/.test(document.querySelector('[data-neff-shift=\"1\"]')?.textContent||'')", 'heated run with the without-heater result ' + tag, 240000);
    await page.until("!document.getElementById('run-multiphysics').disabled", 'heated run done ' + tag, 60000); await noOverflow(tag + ' heated results');
    const heated = await heatedValues();
    // an untitled project suggests untitled-project.json; Cancel writes nothing
    let before = await listDownloads();
    await page.press('button', 'File'); await page.press('menuitem', 'Save As…');
    await page.until("document.getElementById('save-name-dialog').open", 'Save As name dialog ' + tag); await noOverflow(tag + ' name dialog');
    assert.equal(await page.eval("document.getElementById('save-name-input').value"), 'untitled-project.json', 'an untitled project suggests untitled-project.json');
    await page.press('button', 'Cancel'); assert.equal(await status(), 'Save As cancelled; nothing was written.');
    // the project named "Heater study" in the Library (Project name, Rename); File › Save As then
    // suggests its slug, heater-study.json, which Download keeps (the name dialog; no picker here)
    await page.press('tab', 'Library'); await page.until("!!document.getElementById('project-name-input')", 'Library project name ' + tag);
    await page.fill('textbox', 'Project name', 'Heater study'); await page.press('button', 'Rename');
    assert.equal(await status(), 'Project renamed to “Heater study”. File › Save writes the new name.');
    assert.match(await title(), /^Heater study · not saved to a file · /); await noOverflow(tag + ' renamed');
    await page.press('button', 'File'); await page.press('menuitem', 'Save As…');
    await page.until("document.getElementById('save-name-dialog').open", 'Save As name dialog ' + tag);
    assert.equal(await page.eval("document.getElementById('save-name-input').value"), 'heater-study.json', 'the slug of the project name');
    await page.press('button', 'Download');
    const fileName = await newDownload(before), path = join(downloads, fileName), text = await readFile(path, 'utf8'), message = await status();
    stage(`V-P13 ${tag} saved`, {fileName, bytes: Buffer.byteLength(text), message, title: await title(), run1, run2, heated});
    assert.equal(fileName, 'heater-study.json');
    assert.equal(message, "Project file heater-study.json sent to your browser's Downloads: Optical waveguide (2 runs, the comparison) and Heated silicon waveguide (1 run, the without-heater result).");
    assert.ok(!message.includes('not in this file') && !(await page.eval('document.body.innerText')).includes('not in this file'), 'no "not in this file" after Save');
    assert.match(await title(), /^Heater study · heater-study\.json · downloaded \d{1,2}:\d\d(?: [AP]M)?$/);
    assert.equal(await page.eval("document.getElementById('project').title"), 'Your browser may have added “ (1)” to the file name.');
    const doc = JSON.parse(text);
    assert.deepEqual([doc.format, doc.version, doc.name, doc.active, doc.models.map(m => [m.id, m.kind, m.title, m.card])],
      ['openphysics-studio-project', 1, 'Heater study', 'm2', [['m1', 'workspace', 'Optical waveguide', 'optical'], ['m2', 'multiphysics', 'Heated silicon waveguide', 'heated-waveguide']]]);
    assert.equal(doc.models[0].session.input.model.modeCount, 4); assert.equal(doc.models[0].session.version, 9); assert.equal(doc.models[1].session.version, 8);
    // V-P11: Save again downloads under the remembered name with no dialog
    if (tag === 'wide') {
      before = await listDownloads(); await page.press('button', 'File'); await page.press('menuitem', 'Save');
      for (let i = 0; i < 5; i++) { assert.equal(await page.eval("!!document.getElementById('save-name-dialog').open"), false, 'Save: no name dialog'); await sleep(100); }
      const again = await newDownload(before), againMessage = await status();
      stage('V-P11 Save again', {again, message: againMessage, title: await title()});
      assert.match(again, /^heater-study(?: \(\d\))?\.json$/);
      assert.equal(againMessage, "Downloaded heater-study.json again: Optical waveguide (2 runs, the comparison) and Heated silicon waveguide (1 run, the without-heater result). A download cannot replace the earlier file, so your browser may add a number such as “ (1)” to its name.");
      assert.equal(withoutTime(await readFile(join(downloads, again), 'utf8')), withoutTime(text), 'the same project but for its save time');
    }
    // V-P7: the server restarted, a new browser with a new profile, then File › Open
    await stopBrowser(page); await stopProcess(server); server = await startServer('server-' + tag + '-restarted');
    page = await startBrowser(); await size(width, height, mobile);
    await page.call('Page.navigate', {url: base + '/workspace'});
    await page.until("/^Connected/.test(document.getElementById('connection-status').textContent)&&!!document.querySelector('[data-template=optical]')", 'fresh start page ' + tag);
    const posts = page.events.length;
    await openFile(path);
    await page.until("/^Opened project Heater study \\(heater-study\\.json\\)/.test(document.getElementById('file-status').textContent)", 'project opened ' + tag, 60000);
    const opened = {message: await status(), title: await title(), footer: await footer()};
    assert.equal(opened.message, 'Opened project Heater study (heater-study.json): Optical waveguide (2 runs, the comparison) and Heated silicon waveguide (1 run, the without-heater result). Results were read from the file, not recomputed; nothing was run.');
    assert.equal(opened.title, 'Heater study · heater-study.json · opened');
    // round 18 (X8): the heated model is shown, with the other model in the project: its status bar speaks about it in the project
    assert.equal(opened.footer, 'Heated silicon waveguide · in project heater-study.json · opened');
    await noOverflow(tag + ' opened');
    if (tag === 'wide') {
      // V-P1 (a): the opened project saved again at once differs from the first save only in its
      // save time and, in the workspace model, each optical run's origin ("local" → "imported", as
      // a session file opened and saved again has since version 9) with that run's digest, and so
      // the model's size and check value
      const save = async () => { const before = await listDownloads(); await page.press('button', 'File'); await page.press('menuitem', 'Save');
        const name = await newDownload(before); return {name, text: await readFile(join(downloads, name), 'utf8')}; };
      const second = await save();
      // the JSON paths whose values differ (keys and array lengths included), listed and compared
      const differing = (x, y, path = '') => {
        if (Object.is(x, y)) return [];
        if (x && y && typeof x === 'object' && typeof y === 'object' && Array.isArray(x) === Array.isArray(y)) {
          const keys = Array.isArray(x) ? (x.length === y.length ? [...x.keys()] : null) : [...new Set([...Object.keys(x), ...Object.keys(y)])];
          if (keys) return keys.flatMap(k => differing(x[k], y[k], Array.isArray(x) ? `${path}[${k}]` : `${path}.${k}`));
        }
        return [path];
      };
      const origins = t => JSON.parse(t).models.find(m => m.kind === 'workspace').session.runs.map(r => r.origin);
      await writeFile(join(out, 'v-p1-first.json'), text); await writeFile(join(out, 'v-p1-second.json'), second.text);
      const paths = differing(JSON.parse(text), JSON.parse(second.text)), w = JSON.parse(text).models.findIndex(m => m.kind === 'workspace');
      const runCount = JSON.parse(text).models[w].session.runs.length;
      const expected = ['.savedAt', `.models[${w}].bytes`, `.models[${w}].digest`, ...Array.from({length: runCount}, (_, i) => [`.models[${w}].session.runs[${i}].origin`, `.models[${w}].session.runs[${i}].digest`]).flat()];
      stage('V-P1 (a) differing paths', {paths, bytes: [JSON.parse(text).models[w].bytes, JSON.parse(second.text).models[w].bytes]});
      assert.deepEqual([...paths].sort(), [...expected].sort(), 'V-P1 (a): save, open, save differ only in savedAt and, in the workspace entry, each run\'s origin and digest and the entry\'s bytes and digest');
      assert.deepEqual([origins(text), origins(second.text)], [['local', 'local'], ['imported', 'imported']]);
      assert.equal(JSON.stringify(JSON.parse(second.text).models[1]), JSON.stringify(JSON.parse(text).models[1]), 'the multiphysics model unchanged');
      // V-P1 (b): opened and saved again, byte-identical but for the save time
      await openFile(join(downloads, second.name));
      await page.until("/^Opened project Heater study/.test(document.getElementById('file-status').textContent)", 'V-P1 second open');
      const third = await save(); await writeFile(join(out, 'v-p1-third.json'), third.text);
      stage('V-P1 save, open, save', {first: Buffer.byteLength(text), second: Buffer.byteLength(second.text), third: Buffer.byteLength(third.text), origins: [origins(text), origins(second.text)]});
      assert.equal(withoutTime(third.text), withoutTime(second.text), 'V-P1 (b): byte-identical but for savedAt');
      assert.notEqual(JSON.parse(third.text).savedAt, JSON.parse(second.text).savedAt);
    }
    // the heated model is shown (active in the file): its values and the checksum words
    await page.press('tab', 'Results'); await page.until("!!document.querySelector('[data-neff-shift=\"1\"]')", 'heated results after the open ' + tag);
    const heatedBack = await heatedValues();
    const heatedWords = await page.eval('document.getElementById("canvas").innerText');
    assert.deepEqual(heatedBack, heated, 'the heated values read back as the same strings');
    assert.ok(heatedWords.includes("Loaded from file, not recomputed. Results match the file's checksum."), 'the heated results are marked as read from the file');
    // the optical model of the project: its card reads "In this project · 2 runs"
    await page.press('tab', 'Library'); await page.until("!!document.querySelector('[data-template=optical] .card-project')", 'optical card in the project ' + tag);
    assert.equal(await page.text('[data-template=optical] .card-project'), 'In this project · 2 runs');
    assert.equal(await page.text('#view-detail'), await title(), 'the Library is headed by the project line');
    assert.match(await title(), tag === 'wide' ? /^Heater study · heater-study\.json · downloaded / : /^Heater study · heater-study\.json · opened$/); await noOverflow(tag + ' Library after the open');
    await page.press('button', 'Optical waveguide', 'start'); await page.press('tab', 'Results');
    await page.until("document.querySelectorAll('.run-item').length===2", 'two optical runs back ' + tag);
    await showRun(1); const run1Back = await opticalValues(); await showRun(2); const run2Back = await opticalValues();
    assert.deepEqual(run1Back, run1); assert.deepEqual(run2Back, run2);
    const later = page.events.slice(posts).filter(e => e.method === 'Network.requestWillBeSent' && e.params.request.method === 'POST').map(e => new URL(e.params.request.url).pathname);
    stage(`V-P7 ${tag} reopened`, {opened, heated: heatedBack, run1: run1Back, run2: run2Back, posts: later});
    assert.ok(later.every(p => p === '/api/multiphysics/validate'), 'no run starts after the open: ' + JSON.stringify(later));
    assert.equal(await page.eval("document.getElementById('job-message').textContent"), '');
    values[tag] = {run1, run2, heated};
  }
  stage('V-P13 values', values);
  assert.deepEqual(values.phone, values.wide, 'the same values at both sizes');

  // V-P3: three damaged files refused by name; the tab unchanged (the runs, the inputs, Undo, the title)
  const saved = join(downloads, 'heater-study.json'), goodText = await readFile(saved, 'utf8'), good = JSON.parse(goodText);
  const snapshot = () => page.eval("({runs:[...document.querySelectorAll('.run-item')].map(b=>b.textContent),width:document.getElementById('shape-w')?.value??null,undo:document.getElementById('undo-edit').disabled,redo:document.getElementById('redo-edit').disabled,title:document.getElementById('project').textContent,footer:document.getElementById('autosave-status').textContent})");
  // each damage made on the text (the first occurrence of a literal, so every other byte, -0.0
  // included, is as written)
  const once = (t, from, to) => { const i = t.indexOf(from); assert.ok(i >= 0, from); return t.slice(0, i) + to + t.slice(i + from.length); };
  const damaged = [
    ['value', t => once(t, '"completedAt":"2026', '"completedAt":"2027'), 'Project not opened: Optical waveguide changed after it was saved (its check value does not match). The current project is unchanged.'],
    ['duplicate id', t => once(t, '"id":"m2"', '"id":"m1"'), 'Project not opened: Two models have the same id m1. The current project is unchanged.'],
    ['unknown key', t => once(t, '{"format":', '{"comparisons":[],"format":'), 'Project not opened: Unknown key "comparisons" in the project file. The current project is unchanged.']];
  await page.press('tab', 'Results'); await page.until("document.querySelectorAll('.run-item').length===2", 'runs before V-P3');
  for (const [name, change, expected] of damaged) {
    const before = await snapshot();
    const file = join(out, 'damaged-' + name.replace(/ /g, '-') + '.json'); await writeFile(file, change(goodText), 'utf8');
    await page.eval("document.getElementById('file-status').textContent=''");
    await openFile(file); await page.until("/^Project not opened: /.test(document.getElementById('file-status').textContent)", 'refusal ' + name);
    const message = await status(), after = await snapshot();
    stage('V-P3 ' + name, {message});
    assert.equal(message, expected); assert.deepEqual(after, before, name + ': the tab unchanged');
  }
  // a project file newer than this Studio
  { const file = join(out, 'project-v2.json'); await writeFile(file, once(goodText, '"version":1,', '"version":2,'), 'utf8');
    await page.eval("document.getElementById('file-status').textContent=''"); await openFile(file); await page.until("/^Project not opened: /.test(document.getElementById('file-status').textContent)", 'newer version');
    assert.equal(await status(), 'Project not opened: This project file is version 2, newer than this Studio reads (version 1). Open it in a newer Studio. The current project is unchanged.'); }

  // V-P10: the save picker, stubbed at window.showSaveFilePicker with navigator.webdriver false
  await page.eval("Object.defineProperty(navigator,'webdriver',{get:()=>false,configurable:true})");
  await page.eval(`(()=>{window.__picker={calls:[],files:{'study.json':'OLD CONTENT'},writes:0,aborts:0,mode:'ok',failWrite:false};
    window.showSaveFilePicker=async options=>{const p=window.__picker;p.calls.push({suggestedName:options.suggestedName,types:options.types,id:options.id,startIn:options.startIn?'handle:'+options.startIn.name:null});
      if(p.mode==='abort')throw new DOMException('The user aborted a request.','AbortError');
      const name='study.json';return {kind:'file',name,createWritable:async()=>{let buffer='';return {write:async t=>{if(p.failWrite)throw new DOMException('Disk full','QuotaExceededError');buffer+=t;},close:async()=>{p.files[name]=buffer;p.writes++;},abort:async()=>{p.aborts++;}};}};};})()`);
  const picker = () => page.eval("JSON.parse(JSON.stringify({calls:window.__picker.calls,writes:window.__picker.writes,aborts:window.__picker.aborts,content:window.__picker.files['study.json']}))");
  let before = await listDownloads();
  await page.press('button', 'File'); await page.press('menuitem', 'Save As…');
  await page.until("/^Saved Heater study to study\\.json: /.test(document.getElementById('file-status').textContent)", 'V-P10 Save As');
  let p = await picker();
  assert.equal(p.calls.length, 1); assert.equal(p.writes, 1);
  assert.deepEqual(p.calls[0], {suggestedName: 'heater-study.json', types: [{description: 'OpenPhysics project file (JSON)', accept: {'application/json': ['.json']}}], id: 'openphysics-project', startIn: null});
  // the same models (the view and the model shown differ from the first save's)
  assert.deepEqual(JSON.parse(p.content).models.map(m => [m.id, m.kind, m.title]), good.models.map(m => [m.id, m.kind, m.title]), 'the picker file is the project file');
  assert.equal(await status(), 'Saved Heater study to study.json: Optical waveguide (2 runs, the comparison) and Heated silicon waveguide (1 run, the without-heater result).');
  assert.match(await title(), /^Heater study · study\.json · saved \d{1,2}:\d\d(?: [AP]M)?$/); assert.equal(await page.eval("document.getElementById('project').hasAttribute('title')"), false);
  assert.deepEqual(await listDownloads(), before, 'a picker save downloads nothing');
  await page.eval("document.getElementById('file-status').textContent=''");
  await page.press('button', 'File'); await page.press('menuitem', 'Save');
  await page.until("/^Saved Heater study to study\\.json/.test(document.getElementById('file-status').textContent)", 'V-P10 Save');
  p = await picker(); assert.equal(p.calls.length, 1, 'Save asks nothing'); assert.equal(p.writes, 2);
  await page.eval("window.__picker.mode='abort'"); await page.press('button', 'File'); await page.press('menuitem', 'Save As…'); await sleep(500);
  p = await picker(); assert.equal(await status(), 'Save As cancelled; nothing was written.'); assert.equal(p.writes, 2); assert.equal(p.calls[1].startIn, 'handle:study.json');
  await page.eval("window.__picker.mode='ok';window.__picker.files['study.json']='OLD CONTENT';window.__picker.failWrite=true");
  await page.press('button', 'File'); await page.press('menuitem', 'Save'); await sleep(500);
  p = await picker(); stage('V-P10 picker', {calls: p.calls.length, writes: p.writes, aborts: p.aborts, message: await status()});
  assert.equal(await status(), 'Project not saved: study.json could not be written (Disk full); the file is unchanged.');
  assert.equal(p.content, 'OLD CONTENT'); assert.equal(p.aborts, 1); assert.equal(p.writes, 2);
  assert.deepEqual(await listDownloads(), before, 'nothing downloaded on the picker path');
  await stopBrowser(page);

  // Round 16 (pre-registered), at 1440 × 900 in a new profile: Library › Open returns to a model's
  // page and run (S9); a pair of two named runs stays on Compare when a third run comes, and the
  // project file keeps it (S3); a project save relinks the record of the model not shown (S5); a
  // restore of a record that matched its project file names that file again (S4)
  {
    page = await startBrowser(); await size(1440, 900, false);
    await page.call('Page.navigate', {url: base + '/workspace'});
    await page.until("/^Connected/.test(document.getElementById('connection-status').textContent)&&!!document.querySelector('[data-template=optical]')", 'R16 start page');
    // a model's browser recovery record is written 0.7 s after a change: each model shown waits for it
    const recorded = async label => { await page.until("/^Browser recovery updated/.test(document.getElementById('notebook-recovery-detail').textContent)", label, 20000); await sleep(500); };
    await page.eval("document.getElementById('notebook-recovery-detail').textContent=''");
    await openFile(saved); await page.until("/^Opened project Heater study/.test(document.getElementById('file-status').textContent)", 'R16 open', 60000);
    await recorded('R16 heated record');
    const shownPage = () => page.eval("document.querySelector('nav [data-page][aria-selected=true]')?.dataset.page??null");
    const pressedRun = () => page.eval("document.querySelector('.run-item[aria-pressed=true]')?.textContent??null");
    // the heated model is shown (active in the file): to its Results; then the optical model's Run 1 in Results
    await page.press('tab', 'Results'); await page.until("!!document.querySelector('[data-neff-shift=\"1\"]')", 'R16 heated results');
    await page.press('tab', 'Library'); await page.until("!!document.querySelector('[data-template=optical]')", 'R16 Library');
    await page.eval("document.getElementById('notebook-recovery-detail').textContent=''");
    await page.press('button', 'Optical waveguide', 'start'); await page.until("document.querySelectorAll('.run-item').length===2", 'R16 optical runs');
    await recorded('R16 optical record');
    await page.press('tab', 'Results'); await showRun(1);
    // S9: Library › Heated silicon waveguide lands on its Results; Library › Optical waveguide on Results with Run 1
    await page.press('tab', 'Library'); await page.until("!!document.querySelector('[data-template=heated-waveguide]')", 'R16 Library 2');
    await page.eval("document.getElementById('notebook-recovery-detail').textContent=''");
    await page.press('button', 'Heated silicon waveguide', 'start'); await page.until("!!document.querySelector('[data-neff-shift=\"1\"]')", 'R16 heated back on Results');
    await recorded('R16 heated record again');
    const heatedBack = await shownPage();
    await page.press('tab', 'Library'); await page.until("!!document.querySelector('[data-template=optical]')", 'R16 Library 3');
    await page.press('button', 'Optical waveguide', 'start'); await page.until("!!document.getElementById('modes-table')", 'R16 optical back on Results');
    const opticalBack = {page: await shownPage(), run: await pressedRun()};
    stage('R16 S9 return', {heated: heatedBack, optical: opticalBack});
    assert.equal(heatedBack, 'Results'); assert.equal(opticalBack.page, 'Results'); assert.ok(opticalBack.run.includes('Run 1 · '), opticalBack.run);
    // S3: Run 1 named Design A, Run 2 Design B; a third run keeps them on Compare
    await page.fill('textbox', 'Run name', 'Design A'); await showRun(2); await page.fill('textbox', 'Run name', 'Design B');
    await page.press('tab', 'Model'); await page.press('treeitem', 'Geometry'); await page.until("!!document.getElementById('shape-w')", 'R16 geometry');
    await page.fill('spinbutton', 'Width [nm]', 650); await runOptical('R16 run 3');
    await page.press('tab', 'Compare'); await page.until("!!document.getElementById('compare-a')", 'R16 Compare');
    const pair = () => page.eval("['compare-a','compare-b'].map(id=>document.getElementById(id).selectedOptions[0].textContent)");
    const kept = {pair: await pair(), newer: await page.eval("document.getElementById('compare-newer')?.textContent??null")};
    stage('R16 S3 kept pair', kept);
    assert.ok(kept.pair[0].startsWith('Run 1 · Design A · ') && kept.pair[1].startsWith('Run 2 · Design B · '), JSON.stringify(kept.pair));
    assert.equal(kept.newer, 'Run 3 is newer than this pair · Compare Run 3 with B');
    await noOverflow('R16 Compare with the newer line');
    // S5 and S6: Save As design-ab.json with the optical model shown; the name set in the file
    // (Heater study, not the file's stem) stays
    await page.eval("document.getElementById('notebook-recovery-detail').textContent=''");
    let before = await listDownloads();
    await page.press('button', 'File'); await page.press('menuitem', 'Save As…'); await page.until("document.getElementById('save-name-dialog').open", 'R16 Save As');
    await page.fill('textbox', 'File name', 'design-ab'); await page.press('button', 'Download');
    const abName = await newDownload(before), ab = JSON.parse(await readFile(join(downloads, abName), 'utf8'));
    assert.equal(abName, 'design-ab.json'); assert.equal(ab.name, 'Heater study');
    assert.match(await title(), /^Heater study · design-ab\.json · downloaded /);
    const abSession = ab.models.find(m => m.kind === 'workspace').session, jobs = abSession.runs.map(r => r.job);
    assert.deepEqual(abSession.comparison, [jobs[0], jobs[1]], 'the project file keeps the pair Design A, Design B');
    await page.until("/^Browser recovery updated/.test(document.getElementById('notebook-recovery-detail').textContent)", 'R16 recovery updated', 20000); await sleep(1500);
    // S5: after a reload the heated card names the newest project file, although the heated model was not shown when it was saved
    await page.call('Page.reload');
    try { await page.until("!!document.getElementById('resume-optical')&&!!document.getElementById('resume-heated-waveguide')", 'R16 card offers', 30000); }
    catch (error) { stage('R16 card offers missing', {buttons: await page.eval("[...document.querySelectorAll('button')].map(b=>(b.id||'')+': '+b.textContent.slice(0,120))"), page: await page.eval("document.querySelector('nav [data-page][aria-selected=true]')?.dataset.page??null")}); throw error; }
    const offers = await page.eval("['resume-optical','resume-heated-waveguide'].map(id=>document.getElementById(id).textContent)");
    stage('R16 S5 cards', {offers});
    assert.ok(offers[1].includes(' · same as file design-ab.json'), offers[1]); assert.ok(offers[0].includes(' · same as file design-ab.json'), offers[0]);
    // round 18 (X7): each offer also names the project's other model with its runs; its button restores its own model
    stage('R18 X7 offers', {offers});
    assert.ok(offers[0].startsWith('Restore from this browser · Optical waveguide · ') && offers[0].includes(' · also in this project: Heated silicon waveguide · Run ') && offers[0].endsWith(' (restored separately)'), offers[0]);
    assert.ok(offers[1].startsWith('Restore from this browser · Heated silicon waveguide · ') && offers[1].includes(' · also in this project: Optical waveguide · Run ') && offers[1].endsWith(' (restored separately)'), offers[1]);
    // S4: restore the optical session; the header names the project file and Save suggests it
    await page.press('button', offers[0]);
    if (await page.eval("!!document.getElementById('load-confirm')?.open")) await page.eval("document.getElementById('confirm-load').click()");
    await page.until("/^Recovered from this browser/.test(document.getElementById('file-status').textContent)", 'R16 restored', 30000);
    const restoredTitle = await title();
    await page.press('button', 'File'); await page.press('menuitem', 'Save As…'); await page.until("document.getElementById('save-name-dialog').open", 'R16 Save As after restore');
    const prefill = await page.eval("document.getElementById('save-name-input').value"); await page.press('button', 'Cancel');
    stage('R16 S4 restore', {title: restoredTitle, prefill});
    assert.match(restoredTitle, /^Heater study · design-ab\.json · saved \d{1,2}:\d\d(?: [AP]M)?$/); assert.equal(prefill, 'design-ab.json');
    // S3: the project file opened again shows that pair
    await openFile(join(downloads, abName)); await sleep(500); if (await page.eval("document.getElementById('leave-confirm').open")) await page.eval("document.getElementById('leave-go').click()");
    await page.until("/^Opened project Heater study \\(design-ab\\.json\\)/.test(document.getElementById('file-status').textContent)", 'R16 reopen', 60000);
    await page.press('tab', 'Library'); await page.press('button', 'Optical waveguide', 'start'); await page.press('tab', 'Compare'); await page.until("!!document.getElementById('compare-a')", 'R16 Compare reopened');
    const reopened = await pair(); stage('R16 S3 reopened', {pair: reopened});
    assert.ok(reopened[0].startsWith('Run 1 · Design A · ') && reopened[1].startsWith('Run 2 · Design B · '), JSON.stringify(reopened));
    // round 17 (U7, pre-registered): the optical model left on Compare comes back on Results with the
    // run last viewed, and each model switched to starts at the top of its page
    const viewed = await page.eval("document.querySelector('.compare-selection')?document.getElementById('compare-b').selectedOptions[0].textContent.split(' · ').slice(0,2).join(' · '):null");
    await page.eval("document.getElementById('canvas').scrollTop=400");
    await page.press('tab', 'Library'); await page.press('button', 'Heated silicon waveguide', 'start'); await page.until("!!document.querySelector('[data-neff-shift=\"1\"]')", 'R17 heated on Results');
    const heated = {page: await shownPage(), top: await page.eval("document.getElementById('canvas').scrollTop")};
    await page.eval("document.getElementById('canvas').scrollTop=400");
    await page.press('tab', 'Library'); await page.press('button', 'Optical waveguide', 'start'); await page.until("!!document.getElementById('modes-table')", 'R17 optical back on Results');
    const optical = {page: await shownPage(), run: await pressedRun(), top: await page.eval("document.getElementById('canvas').scrollTop")};
    stage('R17 U7 Library › Open', {viewed, heated, optical});
    assert.equal(heated.page, 'Results'); assert.equal(heated.top, 0);
    assert.equal(optical.page, 'Results'); assert.equal(optical.top, 0); assert.ok(optical.run && optical.run.replace('Pinned · ', '').startsWith('Run '), optical.run);
    await stopBrowser(page);
  }

  // Round 17 (U8, pre-registered), a new profile at 1440 × 900: a project file saved by download with
  // the optical model alone; after the heated model joins, Save asks (Save As, prefilled, saying why);
  // Cancel writes nothing; saved under that name, the next Save downloads at once
  {
    page = await startBrowser(); await size(1440, 900, false);
    await page.call('Page.navigate', {url: base + '/workspace'});
    await page.until("/^Connected/.test(document.getElementById('connection-status').textContent)&&!!document.querySelector('[data-template=optical]')", 'R17 start page');
    await page.click('[data-template=optical]'); await page.until("!!document.getElementById('shape-w')", 'R17 optical model');
    let before = await listDownloads();
    await page.press('button', 'File'); await page.press('menuitem', 'Save As…'); await page.until("document.getElementById('save-name-dialog').open", 'R17 Save As');
    // round 18 (X5): the dialog names what the file will hold, also when the model list did not change
    const holds1 = await page.eval("document.getElementById('save-name-contents').hidden?null:document.getElementById('save-name-contents').textContent");
    assert.equal(holds1, 'The file will hold Optical waveguide (no runs).');
    await page.fill('textbox', 'File name', 'u8-optical'); await page.press('button', 'Download');
    assert.equal(await newDownload(before), 'u8-optical.json');
    await page.press('tab', 'Library'); await page.press('button', 'Heated silicon waveguide', 'start'); await page.until("!document.querySelector('[data-template=optical]')", 'R17 heated added');
    // round 18 (X8): the heated model's status bar speaks about the model within the project, as the header does
    const joined = {title: await title(), footer: await footer()}; stage('R18 X8 joined', joined);
    assert.ok(joined.title.includes(' · u8-optical.json · changed since downloaded '), joined.title);
    assert.ok(joined.footer.startsWith('Heated silicon waveguide · in project u8-optical.json · not saved since it joined · '), joined.footer);
    before = await listDownloads();
    await page.press('button', 'File'); await page.press('menuitem', 'Save'); await page.until("document.getElementById('save-name-dialog').open", 'R17 Save asks');
    const asked = await page.eval("({title:document.getElementById('save-name-title').textContent,prefill:document.getElementById('save-name-input').value,why:document.getElementById('save-name-unavailable').hidden?null:document.getElementById('save-name-unavailable').textContent})");
    assert.equal(await page.eval("document.getElementById('save-name-contents').textContent"), 'The file will hold Optical waveguide (no runs) and Heated silicon waveguide (no runs).');
    await page.press('button', 'Cancel'); await sleep(500);
    const cancelled = {downloads: await listDownloads(), status: await status()};
    stage('R17 U8 Save asks', {asked, cancelled: cancelled.status});
    assert.deepEqual(asked, {title: 'Save As', prefill: 'u8-optical.json', why: 'This project now holds Optical waveguide and Heated silicon waveguide; u8-optical.json holds Optical waveguide. Save under this name or another.'});
    assert.deepEqual(cancelled.downloads, before, 'Cancel downloads nothing'); assert.equal(cancelled.status, 'Save As cancelled; nothing was written.');
    await page.press('button', 'File'); await page.press('menuitem', 'Save'); await page.until("document.getElementById('save-name-dialog').open", 'R17 Save asks again');
    await page.press('button', 'Download'); const both = await newDownload(before);
    before = await listDownloads();
    await page.press('button', 'File'); await page.press('menuitem', 'Save'); const again = await newDownload(before);
    const dialogAgain = await page.eval("document.getElementById('save-name-dialog').open");
    stage('R17 U8 saved with both models', {both, again, dialogAgain});
    // round 18 (X8): saved with both models, the status bar says so in the header's words
    const savedBoth = {title: await title(), footer: await footer()}; stage('R18 X8 saved', savedBoth);
    assert.ok(/^Heated silicon waveguide · in project u8-optical\.json · downloaded \d{1,2}:\d\d(?: [AP]M)?$/.test(savedBoth.footer), savedBoth.footer);
    assert.ok(savedBoth.title.includes(' · u8-optical.json · downloaded '), savedBoth.title);
    // round 18 (X10): on the Library, both models of the project read Return to model
    await page.press('tab', 'Library'); await page.until("!!document.querySelector('[data-template=optical] .card-action')", 'R18 Library');
    const actions = await page.eval("Object.fromEntries([...document.querySelectorAll('.cards [data-template]')].map(b=>[b.dataset.template,b.querySelector('.card-action').textContent]))");
    stage('R18 X10 cards', actions);
    assert.deepEqual(actions, {optical: 'Return to Optical waveguide', heat: 'Open model', joule: 'Open model', 'heated-waveguide': 'Return to Heated silicon waveguide'});
    // a download cannot replace the earlier file: a browser may add " (1)" (headless Chromium here writes the name again)
    assert.equal(dialogAgain, false); assert.ok(both.startsWith('u8-optical') && again.startsWith('u8-optical'), JSON.stringify({both, again}));
    const file = JSON.parse(await readFile(join(downloads, both), 'utf8')); assert.deepEqual(file.models.map(m => m.kind).sort(), ['multiphysics', 'workspace']);
    await noOverflow('R17 U8');
    await stopBrowser(page);
  }

  // R19 Y3 (round 19, pre-registered): a browser restore keeps the project's name and file, or names
  // its source. Opened: the record holds the file it was opened from, not the project's name.
  {
    page = await startBrowser(); await size(1440, 900, false);
    await page.call('Page.navigate', {url: base + '/workspace'});
    await page.until("/^Connected/.test(document.getElementById('connection-status').textContent)&&!!document.querySelector('[data-template=optical]')", 'R19 start page');
    const recorded = async label => { await page.until("/^Browser recovery updated/.test(document.getElementById('notebook-recovery-detail').textContent)", label, 30000); await sleep(800); };
    const clearRecorded = () => page.eval("document.getElementById('notebook-recovery-detail').textContent=''");
    const restoreOptical = async label => {
      await page.call('Page.reload'); await page.until("!!document.getElementById('resume-optical')", label + ': card offer', 30000);
      await page.eval("document.getElementById('file-status').textContent=''"); await page.click('#resume-optical');
      await page.until("/^Recovered from this browser/.test(document.getElementById('file-status').textContent)", label + ': restored', 30000);
      await page.press('tab', 'Library'); await page.until("!!document.querySelector('[data-template=optical]')", label + ': Library');
      return {title: await title(), footer: await footer(), message: await status()};
    };
    await openFile(saved); await page.until("/^Opened project Heater study/.test(document.getElementById('file-status').textContent)", 'R19 open', 60000);
    await page.press('tab', 'Library'); await page.until("!!document.querySelector('[data-template=optical]')", 'R19 Library');
    await page.press('button', 'Optical waveguide', 'start'); await page.until("document.querySelectorAll('.run-item').length===2", 'R19 optical runs');
    await clearRecorded();
    await page.press('tab', 'Model'); await page.press('treeitem', 'Geometry'); await page.until("!!document.getElementById('shape-w')", 'R19 geometry');
    await page.fill('spinbutton', 'Width [nm]', 640); await runOptical('R19 run 3'); await recorded('R19 opened record');
    const opened = await restoreOptical('R19 opened');
    // Saved: Save As r19-saved.json, run again, restore: the name and file come back, changed since
    let before = await listDownloads();
    await page.press('button', 'File'); await page.press('menuitem', 'Save As…'); await page.until("document.getElementById('save-name-dialog').open", 'R19 Save As');
    await page.fill('textbox', 'File name', 'r19-saved'); await page.press('button', 'Download');
    const savedName = await newDownload(before); assert.equal(savedName, 'r19-saved.json');
    await clearRecorded();
    await page.press('tab', 'Model'); await page.press('treeitem', 'Geometry'); await page.until("!!document.getElementById('shape-w')", 'R19 geometry 2');
    await page.fill('spinbutton', 'Width [nm]', 660); await runOptical('R19 run after save'); await recorded('R19 saved record');
    const savedCase = await restoreOptical('R19 saved');
    stage('R19 Y3 restore names', {opened, saved: savedCase});
    // since session version 12 the record keeps the project's name (Heater study, from the file
    // opened), so the header names it; a record without a name still reads "recovered from a copy of"
    // round 23 (E5): the record no longer matched the file it was opened from (it read "not saved to a file")
    assert.match(opened.title, /^Heater study · recovered from this browser · changed since heater-study\.json, not saved · /);
    assert.equal(opened.footer, 'Recovered from this browser (opened from heater-study.json; changed since)');
    // the restored name Heater study is the user's (set with Rename), so Save As r19-saved.json keeps it
    assert.match(savedCase.title, /^Heater study · r19-saved\.json · changed since saved \d\d:\d\d(?: [AP]M)? · /);
    assert.match(savedCase.footer, /^Recovered from this browser \(last sent to a file: r19-saved\.json at \d\d:\d\d(?: [AP]M)?; changed since\)$/);
    await noOverflow('R19 Y3 Library');
    await stopBrowser(page);
  }

  // R20 (round 20, pre-registered): Z2 the newest offer of a project with both models restores both
  // in one click; Z4 the box and the card name one time for one record; Z3 the return cards name
  // their model. A new profile: heater-study.json opened, both models shown (each writes its record),
  // saved as r20-both.json (the record of the model not shown is linked to the file), then a reload.
  {
    page = await startBrowser(); await size(1440, 900, false);
    await page.call('Page.navigate', {url: base + '/workspace'});
    await page.until("/^Connected/.test(document.getElementById('connection-status').textContent)&&!!document.querySelector('[data-template=optical]')", 'R20 start page');
    const recorded = async label => { await page.until("/^Browser recovery updated/.test(document.getElementById('notebook-recovery-detail').textContent)", label, 30000); await sleep(800); };
    const clearRecorded = () => page.eval("document.getElementById('notebook-recovery-detail').textContent=''");
    const shownPage = () => page.eval("document.querySelector('nav [data-page][aria-selected=true]')?.dataset.page??null");
    await openFile(saved); await page.until("/^Opened project Heater study/.test(document.getElementById('file-status').textContent)", 'R20 open', 60000);
    await clearRecorded();
    await page.press('tab', 'Library'); await page.until("!!document.querySelector('[data-template=optical]')", 'R20 Library');
    await page.press('button', 'Heated silicon waveguide', 'start'); await page.until("!!document.querySelector('[data-neff-shift=\"1\"]')", 'R20 heated');
    await recorded('R20 heated record');
    // Z4 needs the heated record and the file save in different minutes: wait for the next minute
    await sleep(61000 - Date.now() % 60000);
    await page.press('tab', 'Library'); await page.until("!!document.querySelector('[data-template=optical]')", 'R20 Library 2');
    await page.press('button', 'Optical waveguide', 'start'); await page.until("document.querySelectorAll('.run-item').length===2", 'R20 optical runs');
    await recorded('R20 optical record');
    const before = await listDownloads();
    await page.press('button', 'File'); await page.press('menuitem', 'Save As…'); await page.until("document.getElementById('save-name-dialog').open", 'R20 Save As');
    await clearRecorded();
    await page.fill('textbox', 'File name', 'r20-both'); await page.press('button', 'Download');
    assert.equal(await newDownload(before), 'r20-both.json');
    await recorded('R20 records after the save'); await sleep(1500);
    await page.call('Page.reload');
    await page.until("!!document.getElementById('resume-newest')&&!!document.getElementById('resume-optical')&&!!document.getElementById('resume-heated-waveguide')", 'R20 offers', 30000);
    const offers = await page.eval("({newest:document.getElementById('resume-newest').textContent,pair:document.getElementById('resume-newest').dataset.resumePair??null,box:[...document.querySelectorAll('.resume-actions button')].map(b=>b.textContent),optical:document.getElementById('resume-optical').textContent,heated:document.getElementById('resume-heated-waveguide').textContent})");
    stage('R20 Z2 Z4 offers', offers);
    assert.match(offers.newest, /^Restore newest from this browser: Optical waveguide \(2 runs\) and Heated silicon waveguide \(1 run\) · same as file r20-both\.json · saved \d{1,2}:\d\d(?: [AP]M)?$/);
    assert.equal(offers.pair, 'true');
    // round 21 (W4, pre-registered): while the newest offer restores the pair, the box does not list the
    // heated record again; its card still offers it
    assert.equal(offers.box.find(t => t.startsWith('Restore from this browser: Heated silicon waveguide · ')), undefined, JSON.stringify(offers.box));
    assert.ok(offers.heated.startsWith('Restore from this browser · Heated silicon waveguide · '), offers.heated);
    // Z4: the heated record (relinked by the save) names on its card the time the newest offer names
    const savedTime = text => text.split(', saved ').at(-1).split(' · ')[0];
    const cardTime = savedTime(offers.heated);
    stage('R20 Z4 times', {cardTime});
    assert.match(cardTime, /^\d{1,2}:\d\d(?: [AP]M)?$/);
    // the file's save time, a minute after the heated record was written
    const newestTime = offers.newest.split(' · saved ').at(-1); assert.equal(cardTime, newestTime);
    await noOverflow('R20 offers');
    await page.eval("document.getElementById('file-status').textContent=''");
    // the server's model check answers after 2 s, as on a slower machine: longer than the first
    // restored model's automatic recovery save (0.7 s), which then writes during the second restore
    await page.call('Fetch.enable', {patterns: [{urlPattern: '*/api/multiphysics/validate*'}]});
    page.onEvent = message => { if (message.method === 'Fetch.requestPaused') setTimeout(() => page.call('Fetch.continueRequest', {requestId: message.params.requestId}).catch(() => {}), 2000); };
    await page.click('#resume-newest');
    for (let i = 0; i < 2; i++) { await sleep(800); if (await page.eval("!!document.getElementById('load-confirm')?.open")) await page.eval("document.getElementById('confirm-load').click()"); }
    await page.until("/^Restored Optical waveguide \\(2 runs\\) and Heated silicon waveguide \\(1 run\\) from this browser/.test(document.getElementById('file-status').textContent)", 'R20 both restored', 60000);
    const restored = {message: await status(), title: await title(), page: await shownPage(), optical: await page.eval("document.querySelectorAll('.run-item').length")};
    await page.call('Fetch.disable'); page.onEvent = null;
    await page.press('tab', 'Library'); await page.until("!!document.querySelector('[data-template=optical] .card-action')", 'R20 Library after');
    const after = await page.eval("({actions:Object.fromEntries([...document.querySelectorAll('.cards [data-template]')].map(b=>[b.dataset.template,b.querySelector('.card-action').textContent])),offers:[...document.querySelectorAll('.resume-actions button,.card-resume button')].map(b=>b.textContent),names:[...document.querySelectorAll('.cards [data-template]')].map(b=>b.querySelector('.card-action').textContent)})");
    stage('R20 Z2 restored', {restored, after});
    assert.equal(restored.message, 'Restored Optical waveguide (2 runs) and Heated silicon waveguide (1 run) from this browser, not recomputed.');
    assert.match(restored.title, /^Heater study · r20-both\.json · saved \d{1,2}:\d\d(?: [AP]M)?$/);
    assert.equal(restored.page, 'Results'); assert.equal(restored.optical, 2);
    // Z3: both return cards, each naming its model; no restore offer is left
    assert.deepEqual(after.actions, {optical: 'Return to Optical waveguide (2 runs)', heat: 'Open model', joule: 'Open model', 'heated-waveguide': 'Return to Heated silicon waveguide (1 run)'});
    assert.deepEqual(after.offers, []);
    assert.equal(new Set(after.names.filter(n => n.startsWith('Return to '))).size, 2);
    await noOverflow('R20 Library 1440');
    await size(390, 844, true); await sleep(400); await noOverflow('R20 Library 390');
    // round 20 follow-up (pre-registered): after the pair restore browser recovery keeps writing in
    // this one tab: the restores' own records, then an edit, are written with no "changed in another
    // tab", and after a reload the newest record holds that edit
    await size(1440, 900, false);
    const recoveryNow = () => page.eval("({title:document.getElementById('project').textContent,footer:document.getElementById('autosave-status').textContent,detail:document.getElementById('notebook-recovery-detail').textContent})");
    await sleep(3000); const settled = await recoveryNow();
    await page.eval("document.getElementById('notebook-recovery-detail').textContent=''");
    await page.press('tab', 'Model'); await page.press('treeitem', 'Optical modes'); await page.until("!!document.getElementById('mode-count-number')", 'R20 Optical modes');
    await page.fill('spinbutton', 'Modes to find', 3);
    await page.until("/^Browser recovery updated/.test(document.getElementById('notebook-recovery-detail').textContent)||/another tab/.test(document.getElementById('autosave-status').textContent+document.getElementById('project').textContent)", 'R20 edit recorded', 30000);
    await sleep(1500); const edited = await recoveryNow();
    stage('R20 pair restore keeps recovery', {settled, edited});
    for (const state of [settled, edited]) { assert.ok(!(state.title + state.footer).includes('another tab'), JSON.stringify(state)); }
    assert.match(edited.detail, /^Browser recovery updated /);
    await page.call('Page.reload'); await page.until("!!document.getElementById('resume-optical')", 'R20 offers after the edit', 30000);
    await page.click('#resume-optical'); if (await page.eval("!!document.getElementById('load-confirm')?.open")) await page.eval("document.getElementById('confirm-load').click()");
    await page.until("/^Recovered from this browser/.test(document.getElementById('file-status').textContent)", 'R20 edited record restored', 30000);
    await page.press('tab', 'Model'); await page.press('treeitem', 'Optical modes'); await page.until("!!document.getElementById('mode-count-number')", 'R20 Optical modes again');
    const kept = await page.eval("document.getElementById('mode-count-number').value"); stage('R20 edit kept', {kept});
    assert.equal(kept, '3');
    // round 21 (W3, pre-registered): the run of Modes to find 4 says so in the run list and the Compare
    // pickers, before the geometry, so a picker cut at its end at 390 px still shows it
    // (the optical model restored by the stage above is shown)
    await page.press('tab', 'Results'); await page.until("document.querySelectorAll('.run-item').length===2", 'R21 optical runs');
    const w3items = await page.eval("[...document.querySelectorAll('.run-item')].map(b=>b.textContent)");
    await page.press('tab', 'Compare'); await page.until("!!document.getElementById('compare-a')", 'R21 Compare');
    const w3 = {items: w3items};
    for (const [width, height, mobile] of [[1440, 900, false], [390, 844, true]]) {
      await size(width, height, mobile); await sleep(400);
      w3[width] = await page.eval("[...document.querySelectorAll('#compare-a,#compare-b')].map(s=>{const t=s.selectedOptions[0].textContent,c=document.createElement('canvas').getContext('2d');c.font=getComputedStyle(s).font;const i=t.indexOf(' modes'),tags=i>0?t.slice(0,i+6):t;return {text:t,title:s.title,tagsWidth:Math.ceil(c.measureText(tags).width),room:s.clientWidth-28}})");
      await noOverflow('R21 W3 Compare ' + width);
    }
    stage('R21 W3 run labels', w3);
    assert.equal(w3items.filter(t => t.includes(' · closed · 4 modes · ')).length, 1, JSON.stringify(w3items));
    assert.equal(w3items.filter(t => t.includes(' · closed · ') && !t.includes(' modes · ')).length, 1, JSON.stringify(w3items));
    for (const width of [1440, 390]) for (const picker of w3[width]) {
      assert.equal(picker.title, picker.text);
      if (picker.text.includes(' · 4 modes · ')) assert.ok(picker.tagsWidth <= picker.room, `${width}: "${picker.text}" shows ${picker.room} px, its tags need ${picker.tagsWidth}`);
    }
    await size(1440, 900, false);
    await stopBrowser(page);
  }

  // Stable run numbers and the project name after recovery (pre-registered K4 and K5, the T17 and
  // T20 flows): heater-study.json opened, the project renamed both-models, five more optical runs
  // (seven in all, so Run 1 is dropped) and the project saved as both-models.json; the browser closed
  // and started again on its profile, File › Open: the run list, the drop line, "Pin Run N", the
  // Compare picker and "No need to run: Run N" read the same numbers, no numbering sentence is said,
  // and the next run is Run 8 (K4). Then the browser closed again and Restore newest from this browser
  // (both models): the same numbers for both models, and the header names the recovered project (K5).
  {
    page = await startBrowser(); const profile = browsers; await size(1440, 900, false);
    const recorded = async label => { await page.until("/^Browser recovery updated/.test(document.getElementById('notebook-recovery-detail').textContent)", label, 30000); await sleep(800); };
    const clearRecorded = () => page.eval("document.getElementById('notebook-recovery-detail').textContent=''");
    const runItems = () => page.eval("[...document.querySelectorAll('.run-item')].map(b=>b.textContent)");
    const startPage = async label => { await page.call('Page.navigate', {url: base + '/workspace'}); await page.until("/^Connected/.test(document.getElementById('connection-status').textContent)&&!!document.querySelector('[data-template=optical]')", label); };
    const width = async w => { await page.press('tab', 'Model'); await page.press('treeitem', 'Geometry'); await page.until("!!document.getElementById('shape-w')", 'geometry ' + w); await page.fill('spinbutton', 'Width [nm]', w); };
    // what names the optical runs by number: the run list, the drop line and its pin button (new
    // inputs, 640 nm), "No need to run: Run 5" (Run 5's inputs, 560 nm) and the Compare picker
    const numbersNow = async label => {
      await width(640); await sleep(300);
      const drop = await page.eval("({hidden:document.getElementById('run-drop').hidden,text:document.getElementById('run-drop-text').textContent,pin:document.getElementById('run-drop-pin').textContent})");
      await page.eval("document.getElementById('file-status').textContent=''");
      await width(560); await page.until("!!document.getElementById('match-offer')", label + ': No need to run');
      const need = await page.eval("({text:document.getElementById('match-offer').textContent,show:document.querySelector('#match-offer button').textContent})");
      await page.press('tab', 'Results'); await page.until("document.querySelectorAll('.run-item').length===6", label + ': six runs');
      const items = await runItems();
      await page.press('tab', 'Compare'); await page.until("!!document.getElementById('compare-a')", label + ': Compare');
      const compare = await page.eval("[...document.getElementById('compare-a').options].map(o=>o.textContent)");
      await noOverflow(label + ' 1440'); await size(390, 844, true); await sleep(400); await noOverflow(label + ' 390'); await size(1440, 900, false);
      // a run read from a file or recovered ends with its origin (· from file, · recovered): left out,
      // since the numbers and the runs are what is compared
      const plain = list => list.map(t => t.replace(/ · (?:from file|recovered)$/, ''));
      return {items: plain(items), drop, need, compare: plain(compare)};
    };
    const heatedItems = async label => {
      await page.press('tab', 'Library'); await page.until("!!document.querySelector('[data-template=optical]')", label + ': Library');
      await page.press('button', 'Heated silicon waveguide', 'start'); await page.until("/^Heated silicon waveguide shown/.test(document.getElementById('file-status').textContent)||!!document.querySelector('[data-mp-node]')", label + ': heated model');
      await sleep(400); await page.press('tab', 'Results'); await page.until("!!document.querySelector('[data-mp-node=\"results:runs\"]')", label + ': heated Results');
      await page.click('[data-mp-node="results:runs"]'); await page.until("!!document.querySelector('[data-mp-run]')", label + ': heated runs');
      return page.eval("[...document.querySelectorAll('[data-mp-run]')].map(b=>b.textContent)");
    };
    const toOptical = async label => {
      await page.press('tab', 'Library'); await page.until("!!document.querySelector('[data-template=optical]')", label + ': Library');
      await page.press('button', 'Optical waveguide', 'start'); await page.until("document.querySelectorAll('.run-item').length>0", label + ': optical runs');
    };
    await startPage('K4 start page');
    await openFile(saved); await page.until("/^Opened project Heater study/.test(document.getElementById('file-status').textContent)", 'K4 open heater-study', 60000);
    await page.press('tab', 'Library'); await page.until("!!document.getElementById('project-name-input')", 'K4 project name');
    await page.fill('textbox', 'Project name', 'both-models'); await page.press('button', 'Rename');
    await toOptical('K4 optical');
    for (const w of [520, 540, 560, 580, 620]) { await width(w); await runOptical('K4 run at ' + w); }
    const k4 = {before: await numbersNow('K4 before')};
    await recorded('K4 optical record'); const before = await listDownloads();
    await page.press('button', 'File'); await page.press('menuitem', 'Save As…'); await page.until("document.getElementById('save-name-dialog').open", 'K4 Save As');
    await clearRecorded();
    // the project opened from heater-study.json offers that file; the new name is typed
    await page.fill('textbox', 'File name', 'both-models'); await page.press('button', 'Download'); assert.equal(await newDownload(before), 'both-models.json');
    await recorded('K4 saved');
    await stopBrowser(page); page = await startBrowser(profile); await size(1440, 900, false); await startPage('K4 start page again');
    await openFile(join(downloads, 'both-models.json')); await page.until("/^Opened project both-models/.test(document.getElementById('file-status').textContent)", 'K4 open both-models', 60000);
    k4.opened = await status();
    // both models write their records from the file opened: the heated one first, then the optical one
    await clearRecorded(); k4.heated = await heatedItems('K4'); await recorded('K4 heated record');
    await toOptical('K4 optical again');
    k4.after = await numbersNow('K4 after');
    await width(660); await clearRecorded(); await runOptical('K4 next run'); await recorded('K4 next run recorded'); await page.press('tab', 'Results'); k4.next = await runItems();
    stage('K4 numbers after Open project', k4);
    assert.deepEqual(k4.after, k4.before);
    assert.deepEqual(k4.before.items.map(t => t.replace('Pinned · ', '').split(' · ')[0]), ['Run 7', 'Run 6', 'Run 5', 'Run 4', 'Run 3', 'Run 2']);
    assert.deepEqual(k4.before.drop, {hidden: false, text: k4.before.drop.text, pin: 'Pin Run 2'}); assert.match(k4.before.drop.text, /^If you run: drops Run 2 \(/);
    assert.match(k4.before.need.text, /No need to run: Run 5 /); assert.equal(k4.before.need.show, 'Show Run 5');
    assert.deepEqual(k4.before.compare.map(t => t.split(' · ')[0]), ['Run 2', 'Run 3', 'Run 4', 'Run 5', 'Run 6', 'Run 7']);
    assert.doesNotMatch(k4.opened, /numbered from 1/); assert.match(k4.opened, /^Opened project both-models \(both-models\.json\): /);
    assert.equal(k4.next[0].split(' · ')[0], 'Run 8'); assert.equal(k4.next.length, 6);
    // K5: the browser closed and started again; Restore newest restores both models with their numbers
    await clearRecorded(); const k5 = {before: await numbersNow('K5 before')}; await recorded('K5 record');
    await stopBrowser(page); page = await startBrowser(profile); await size(1440, 900, false); await startPage('K5 start page');
    await page.until("!!document.getElementById('resume-newest')", 'K5 offers', 30000);
    k5.offer = {text: await page.text('#resume-newest'), pair: await page.eval("document.getElementById('resume-newest').dataset.resumePair??null")};
    await page.eval("document.getElementById('file-status').textContent=''");
    await page.click('#resume-newest');
    for (let i = 0; i < 2; i++) { await sleep(800); if (await page.eval("!!document.getElementById('load-confirm')?.open")) await page.eval("document.getElementById('confirm-load').click()"); }
    await page.until("/^Restored Optical waveguide \\(6 runs\\) and Heated silicon waveguide \\(1 run\\) from this browser/.test(document.getElementById('file-status').textContent)", 'K5 both restored', 60000);
    // round 23 (E5): the record no longer matched both-models.json, opened from disk: the header says so,
    // read once browser recovery has kept the restored session
    await page.until("/ · kept for recovery in this browser$/.test(document.getElementById('project').textContent)", 'K5 header kept', 30000);
    k5.message = await status(); k5.title = await title();
    await noOverflow('K5 restored 1440'); await size(390, 844, true); await sleep(400); await noOverflow('K5 restored 390'); await size(1440, 900, false);
    k5.heated = await heatedItems('K5'); await toOptical('K5 optical');
    k5.after = await numbersNow('K5 after');
    stage('K5 numbers after Restore newest', k5);
    assert.equal(k5.offer.pair, 'true', JSON.stringify(k5.offer));
    assert.equal(k5.message, 'Restored Optical waveguide (6 runs) and Heated silicon waveguide (1 run) from this browser, not recomputed.');
    assert.equal(k5.title, 'both-models · recovered from this browser · changed since both-models.json, not saved · kept for recovery in this browser');
    assert.deepEqual(k5.after, k5.before); assert.deepEqual(k5.heated.map(t => t.replace(/ · (?:from file|recovered)$/, '')), k4.heated.map(t => t.replace(/ · (?:from file|recovered)$/, ''))); assert.match(k5.heated[0], /^Run 1 /);
    assert.deepEqual(k5.before.items.map(t => t.replace('Pinned · ', '').split(' · ')[0]), ['Run 8', 'Run 7', 'Run 6', 'Run 5', 'Run 4', 'Run 3']);
    // after a change the header is the ordinary one (the drop-line check above ends on the restored
    // inputs, 560 nm, so the header still reads as recovered there, as loadedSession does)
    assert.match(await title(), /^both-models · recovered from this browser · /);
    await width(600); await sleep(300); k5.changed = await title(); stage('K5 header after a change', {title: k5.changed});
    assert.match(k5.changed, /^both-models · not saved to a file · /);
    await stopBrowser(page);
  }

  // V-P9: an older Studio given the project file: its existing refusal, its workspace unchanged
  if (args['old-python']) {
    await stopProcess(server); server = await startServer('server-old', args['old-python']);
    page = await startBrowser(); await page.call('Page.navigate', {url: base + '/workspace'});
    await page.until("!!document.querySelector('[data-template=optical]')", 'older Studio start page');
    await page.click('[data-template=optical]'); await page.until("!!document.getElementById('shape-w')", 'older Studio optical model');
    const beforeOld = await page.eval("({title:document.getElementById('project').textContent,width:document.getElementById('shape-w').value})");
    await page.on('function(){document.getElementById("file-status").textContent="";return true}');
    const {root} = await page.call('DOM.getDocument'); const {nodeId} = await page.call('DOM.querySelector', {nodeId: root.nodeId, selector: '#session-file'});
    await page.call('DOM.setFileInputFiles', {nodeId, files: [saved]});
    await page.until("document.getElementById('file-status').textContent.length>0", 'older Studio refusal');
    const old = {message: await status(), after: await page.eval("({title:document.getElementById('project').textContent,width:document.getElementById('shape-w').value})"), before: beforeOld};
    stage('V-P9 older Studio', old); report.olderStudio = old;
    assert.deepEqual(old.after, old.before, 'the older workspace is unchanged');
    await stopBrowser(page);
  } else stage('V-P9 older Studio not run here (no --old-python)');

  assert.deepEqual(report.exceptions, [], 'no uncaught page exceptions');
  assert.deepEqual(report.consoleErrors, [], 'no console.error calls');
  await stopProcess(server);
  report.status = 'passed';
} catch (error) {
  report.status = 'failed'; report.error = String(error?.stack || error);
  process.exitCode = 1;
} finally {
  for (const child of owned) if (child.exitCode === null && child.signalCode === null) child.kill();
  await Promise.race([Promise.all(owned.map(c => c.done)), sleep(10000)]);
  await rm(profiles, {recursive: true, force: true}).catch(() => {});
  await save();
  await endScript(owned, ['[project browser]', report.status, report.error || ''].join(' '));
}
