// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Real-browser check of the installed Studio workspace (/workspace) on this OS:
// two optical designs (a Width edit keeps the core centred), Compare with its n_eff
// table, Save session under a dated name, a server restart with the page open,
// recovery from the start page without a confirmation (with the round-3 labels: one save indicator
// in the title and footer, the routes back, nm plot axes, n_eff digits, the wavelength in the step bar,
// Compare headings and Unpin only); then the Joule heating application (Picard,
// Newton, a refusal shown, constant materials), and the File menu (Save As through a stubbed
// save picker, Save again, a cancel, a failed write, the name dialog where the picker is missing
// or refused, the menus by keyboard). Drives a preinstalled Chrome through the
// DevTools protocol with Node's built-in fetch and WebSocket; no npm package and
// no browser download. Fails, never skips, when no browser is found.
//
//   node tools/studio_browser/studio_workspace_browser.mjs --python <venv python> --output <dir> [--chrome <path>]
import assert from 'node:assert/strict';
import {spawn, spawnSync} from 'node:child_process';
import {existsSync} from 'node:fs';
import {mkdir, mkdtemp, readdir, readFile, rm, stat, writeFile} from 'node:fs/promises';
import {createServer} from 'node:net';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {launchBrowser} from './browser_launch.mjs';

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
  async axTree(roles = ['tree', 'treeitem']) {
    const {result: document} = await this.call('Runtime.evaluate', {expression: 'document'});
    const prop = (n, key) => n.properties?.find(p => p.name === key)?.value?.value;
    const read = async role => (await this.call('Accessibility.queryAXTree', {objectId: document.objectId, role})).nodes.filter(n => !n.ignored)
      .map(n => ({role, name: n.name?.value ?? '', level: prop(n, 'level') ?? null, selected: prop(n, 'selected') ?? null, expanded: prop(n, 'expanded') ?? null}));
    return (await Promise.all(roles.map(read))).flat();
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
  const apiPort = await freePort(), base = `http://127.0.0.1:${apiPort}`;
  const startServer = async name => {
    const child = launch(args.python, ['-I', '-m', 'simcase.studio', '--workspace', '--no-browser', '--port', String(apiPort)], name);
    for (let i = 0; i < 240; i++) { try { if ((await fetch(base + '/workspace')).ok) return child; } catch {} await sleep(250); }
    throw new Error('Studio did not start: ' + name);
  };
  let server = await startServer('server-1');
  // Chrome refuses to run as root with its sandbox (containers); CI runners are not root.
  const sandbox = process.getuid?.() === 0 ? ['--no-sandbox'] : [];
  // the launch alone is retried once when the DevTools endpoint does not answer (browser_launch.mjs)
  const {target, port: debugPort} = await launchBrowser({launch: (command, argv, attempt) => launch(command, argv, attempt === 1 ? 'browser' : 'browser-' + attempt), command: chrome, freePort, report,
    argv: (port, attempt) => ['--headless=new', '--disable-gpu', ...sandbox, '--no-first-run', '--no-default-browser-check', '--remote-debugging-address=127.0.0.1',
      '--remote-debugging-port=' + port, '--user-data-dir=' + join(profile, 'attempt-' + attempt), '--window-size=1280,800', 'about:blank']});
  const page = new Page(target.webSocketDebuggerUrl); await page.ready;
  await page.call('Runtime.enable'); await page.call('Page.enable'); await page.call('DOM.enable'); await page.call('Accessibility.enable');
  await page.call('Emulation.setDeviceMetricsOverride', {width: 1280, height: 800, deviceScaleFactor: 1, mobile: false});
  await page.call('Page.setDownloadBehavior', {behavior: 'allow', downloadPath: downloads});
  // This browser has a save picker on 127.0.0.1, which a headless run cannot answer: it is removed
  // at document start, so Save asks for a name in Studio's dialog and the browser downloads the
  // file under the name Studio suggests, as before the File menu. Stage F stubs the picker.
  await page.call('Page.addScriptToEvaluateOnNewDocument', {source: 'delete window.showSaveFilePicker;delete Window.prototype.showSaveFilePicker;'});
  report.browserVersion = (await page.call('Browser.getVersion').catch(() => ({}))).product || null;

  // File › Save without a chosen file asks for a name: Download keeps the name Studio suggests
  const confirmName = async label => { await page.until("document.getElementById('save-name-dialog')?.open", label + ': name dialog'); await page.click('#save-name-download'); };
  const runAndWait = async () => {
    await page.until("!document.getElementById('run-optical').disabled", 'Run enabled');
    await page.click('#run-optical');
    // round 19 (Y4): with six runs kept, Run study asks before dropping one; these stages answer Run
    if (await page.eval("!!document.getElementById('run-drop-confirm')?.open")) await page.click('#run-drop-confirm-run');
    await page.until("/complete/i.test(document.getElementById('job-message').textContent)&&document.getElementById('run-optical').textContent==='Run study'", 'optical run', 120000);
  };
  const toGeometry = async () => { await page.click('nav [data-page=Model]'); await sleep(200); await page.clickTreeItem('Geometry'); await page.until("!!document.querySelector('#shape-w')", 'geometry inspector'); };
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
  // P2: the Library's one "Open file…" (P3: it opens project files too, and the project's name
  // sits at the right of its row) is at the top of the page, under no card, at
  // 1440 × 900 and on a 390 × 844 phone; back to 1280 × 800 after
  const libraryOpenFile = async tag => {
    for (const [width, height, mobile] of [[1440, 900, false], [390, 844, true]]) {
      await page.call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile}); await sleep(300);
      const seen = await page.eval("(()=>{const all=[...document.querySelectorAll('#canvas button')].filter(b=>/^Open file…$/.test(b.textContent)),b=all[0],r=b?.getBoundingClientRect(),first=document.querySelector('#canvas>*:not(.library-files)')?.getBoundingClientRect();return {count:all.length,id:b?.id,underCard:!!b?.closest('.card-slot,.resume-card,[data-template]'),above:!!(r&&first&&r.bottom<=first.top),left:Math.round(r?.left??-1),right:Math.round(r?.right??-1),width:innerWidth}})()");
      stage('P2 one Open file ' + tag, {width, height, ...seen});
      assert.deepEqual([seen.count, seen.id, seen.underCard, seen.above], [1, 'library-open-file', false, true], `${tag} at ${width} × ${height}`);
      assert.ok(seen.left >= 0 && seen.right <= seen.width, `${tag}: the button is inside the page at ${width}`);
    }
    await page.call('Emulation.setDeviceMetricsOverride', {width: 1280, height: 800, deviceScaleFactor: 1, mobile: false}); await sleep(300);
  };
  // round 11 (L6): on Results and Compare no model node is marked, and a node under the pointer does
  // not look selected; since round 14 (Q9) the Results group's node of that page is: Runs on
  // Results, Compare on Compare (where the tree is hidden)
  const treeMarks = async tag => {
    const marks = await page.eval("(()=>{const items=[...document.querySelectorAll('#tree [role=treeitem]:not(.tree-heading)')];const mesh=items.find(b=>b.dataset.node==='Mesh'),geo=items.find(b=>b.dataset.node==='Geometry');const r=mesh.getBoundingClientRect();return {selected:items.filter(b=>b.getAttribute('aria-selected')==='true').map(b=>b.dataset.node),shown:r.width>0,x:r.left+r.width/2,y:r.top+r.height/2,plain:getComputedStyle(geo).backgroundColor}})()");
    stage('L6 tree on ' + tag, marks); assert.deepEqual(marks.selected, [tag.startsWith('Compare') ? 'results:compare' : 'results:runs'], `only the Results node of the page is selected on ${tag}`);
    if (!marks.shown) return; // Compare hides the tree
    await page.call('Input.dispatchMouseEvent', {type: 'mouseMoved', x: marks.x, y: marks.y}); await sleep(150);
    const hovered = await page.eval("(()=>{const m=document.querySelector('#tree [data-node=Mesh]');return {hover:m.matches(':hover'),background:getComputedStyle(m).backgroundColor,weight:getComputedStyle(m).fontWeight}})()");
    await page.call('Input.dispatchMouseEvent', {type: 'mouseMoved', x: 1, y: 1});
    stage('L6 hover on ' + tag, hovered);
    assert.ok(hovered.hover, 'the pointer is over Mesh'); assert.equal(hovered.background, marks.plain, `a hovered node keeps the plain fill on ${tag}`); assert.notEqual(hovered.weight, '600');
  };
  const delta = () => page.eval("(document.getElementById('compare-description')?.textContent.match(/^.* Shown: A mode 1 ↔ B mode 1, overlap [0-9.]+, Δn_eff \\(B − A\\) ([+−][0-9]+\\.[0-9]+)\\./)||[])[1]||null");
  // round 10: a key as a user presses it (keyDown and keyUp on the focused element)
  const KEYS = {ArrowDown: 40, ArrowUp: 38, ArrowLeft: 37, ArrowRight: 39, Home: 36, End: 35, Enter: 13, ' ': 32, Tab: 9};
  const press = async key => {
    for (const type of ['keyDown', 'keyUp']) await page.call('Input.dispatchKeyEvent', {type, key, code: key === ' ' ? 'Space' : key, windowsVirtualKeyCode: KEYS[key], ...(type === 'keyDown' && (key === 'Enter' || key === ' ') ? {text: key === 'Enter' ? '\r' : ' '} : {})});
    await sleep(120);
  };
  // the focused element's name without its hidden icon (the tree items' marks are aria-hidden)
  const focused = () => page.eval("(()=>{const e=document.activeElement,c=e?.cloneNode(true);c?.querySelectorAll('[aria-hidden=true]').forEach(x=>x.remove());return {role:e?.getAttribute('role')||null,name:c?.textContent.replace(/\\s+/g,' ').trim()||null,tabindex:e?.getAttribute('tabindex'),selected:e?.getAttribute('aria-selected'),expanded:e?.getAttribute('aria-expanded')}})()");
  // round 10 (K9): the model builder in the accessibility tree: one tree named "Model tree", every
  // item found by its role and name exactly once, at most one selected, one tab stop
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
  const compareTableRows = () => page.eval("(()=>{const t=document.getElementById('compare-neff');return t&&{caption:t.caption?.textContent,head:(()=>{const leaf=[...t.tHead.rows[1].cells],h=[];for(const c of t.tHead.rows[0].cells)h.push(...(c.colSpan>1?leaf.splice(0,c.colSpan):[c]).map(x=>x.dataset.column));return h})(),runs:[...document.querySelectorAll('#compare-table-runs [data-side]')].map(e=>e.textContent),rows:[...t.tBodies[0].rows].map(r=>[...r.cells].map((c,i)=>i?c.textContent:c.getAttribute('aria-label'))),short:[...t.tBodies[0].rows].map(r=>r.cells[0].textContent),matched:[...t.tBodies[0].rows].map(r=>r.dataset.match||null),overlap:[...t.querySelectorAll('[data-overlap]')].map(c=>Number(c.dataset.overlap)),note:document.getElementById('compare-match-note')?.textContent,picker:[...document.querySelectorAll('#compare-mode option')].map(o=>o.textContent)}})()");

  await page.call('Page.navigate', {url: base + '/workspace'});
  await page.until("/^Connected/.test(document.getElementById('connection-status').textContent)&&!!document.querySelector('[data-template=optical]')", 'connected start page');
  const startPage = await page.eval("({heading:document.querySelector('#canvas h2').textContent,resumeCard:!!document.querySelector('.resume-card'),status:document.getElementById('status').textContent,steps:document.querySelectorAll('#sequence b').length,tab:document.querySelector('nav [data-page=Applications]').textContent,view:document.getElementById('view-title').textContent+' · '+document.getElementById('view-detail').textContent,footer:document.getElementById('autosave-status').textContent})");
  stage('start page', startPage);
  // before an application is chosen: a neutral status and no study steps
  assert.equal(startPage.status, 'Choose a model to start'); assert.equal(startPage.steps, 0);
  // one word for one thing on the start page: model
  assert.equal(startPage.tab, 'Library'); assert.equal(startPage.heading, 'Choose a starting model'); assert.equal(startPage.view, 'Model library · Untitled project · no model chosen', 'P3: the Library is headed by the project line');
  assert.doesNotMatch(await text('#canvas'), /template|application/i, 'the start page says model');
  assert.equal(startPage.footer, 'No model chosen · nothing to save yet');
  // the chooser: a plain sentence about choosing, and Joule heating with its own card icon
  assert.match(await text('.application-contract'), /Choosing a model sets which physics it solves\. Dimensions you entered and runs you completed are kept, and Undo takes the choice back/);
  // every chooser sentence says what File › Save keeps today; no sentence about other views
  const chooser = await text('.application-contract'); stage('chooser notes', {chooser, message: await text('#file-status')});
  assert.match(chooser, /Heated silicon waveguide: .*File › Save keeps the model with its runs, their names and pins, and the without-heater results\./);
  assert.match(chooser, /File › Save keeps the plate inputs; heat results stay in this tab\./); assert.match(chooser, /File › Save keeps the inputs; Joule heating results stay in this tab\./);
  assert.match(chooser, /The heated silicon waveguide has its own Undo for its edits: to leave it, choose another model here\./);
  assert.doesNotMatch(chooser, /Save model file keeps|Results stay in the tab|Existing thermal Studio views/);
  await libraryOpenFile('without offers');
  assert.equal(await text('#file-status'), 'Choose a model to begin. File › Save keeps every model of this tab in one project file, with the optical and multiphysics runs; heat and Joule heating results stay in this tab.');
  const icons = await page.eval("Object.fromEntries([...document.querySelectorAll('.cards [data-template]')].map(b=>[b.dataset.template,getComputedStyle(b,'::before').content]))");
  stage('model card icons', icons); assert.notEqual(icons.joule, icons.optical); assert.equal(new Set(Object.values(icons)).size, Object.keys(icons).length);
  await page.click('[data-template=optical]'); await page.until("!!document.querySelector('#shape-w')", 'optical template');
  // before any edit or run: a new model, and the dock and footer keep the words before a run
  const opticalSequence = () => page.eval("({heading:document.querySelector('.dock-title>span').textContent,status:document.getElementById('status').textContent})");
  assert.equal(await page.eval("document.getElementById('autosave-status').textContent"), 'New model · not saved');
  // P3: the title bar names the project; an untitled one says it is in no file
  assert.match(await page.eval("document.getElementById('project').textContent"), /^Untitled project · not saved to a file · /);
  assert.deepEqual(await opticalSequence(), {heading: 'Nothing is computed until you press Run', status: 'Optical adapter ready · explicit Run required'});
  // round 12 (N7; pre-registered): the page tabs are a tablist named Pages, Library first, the shown
  // page's tab selected and the one tab stop; Left, Right, Home and End move between them and open the page
  const tabState = async () => ({ax: (await page.axTree(['tablist', 'tab'])).map(n => [n.role, n.name, n.selected === true]),
    stops: await page.eval("[...document.querySelectorAll('nav [role=tab]')].filter(b=>b.tabIndex===0).map(b=>b.textContent)"), focus: (await focused()).name,
    page: await page.eval("document.querySelector('main').dataset.page"),
    // round 13 (F4): one page panel, role=tabpanel, that every tab controls and the selected tab names
    panel: (await page.axTree(['tabpanel'])).map(n => n.name), controls: await page.eval("[...new Set([...document.querySelectorAll('nav [role=tab]')].map(b=>b.getAttribute('aria-controls')))]"),
    labelledby: await page.eval("(()=>{const p=document.getElementById('workspace-panel');return [p.getAttribute('role'),p.getAttribute('aria-labelledby')]})()")});
  let tabs = await tabState(); stage('N7 page tabs', tabs);
  assert.deepEqual(tabs.ax, [['tablist', 'Pages', false], ['tab', 'Library', false], ['tab', 'Model', true], ['tab', 'Connections', false], ['tab', 'Results', false], ['tab', 'Compare', false]]);
  assert.deepEqual(tabs.stops, ['Model']);
  await page.eval("document.querySelector('nav [data-page=Model]').focus()");
  for (const [key, name, shown] of [['ArrowRight', 'Connections', 'Connections'], ['ArrowLeft', 'Model', 'Model'], ['End', 'Compare', 'Compare'], ['ArrowRight', 'Library', 'Applications'], ['Home', 'Library', 'Applications'], ['ArrowLeft', 'Compare', 'Compare'], ['Home', 'Library', 'Applications'], ['ArrowRight', 'Model', 'Model']]) {
    await press(key); tabs = await tabState(); stage('N7 ' + key, tabs);
    assert.deepEqual([tabs.focus, tabs.stops, tabs.page], [name, [name], shown], key);
    assert.deepEqual(tabs.ax.filter(n => n[2]).map(n => n[1]), [name], key + ': one tab selected');
    assert.deepEqual(tabs.panel, [name], key + ': the tab panel is named by the selected tab'); assert.deepEqual(tabs.controls, ['workspace-panel']);
    assert.deepEqual(tabs.labelledby, ['tabpanel', 'page-tab-' + shown]);
  }
  await page.clickTreeItem('Geometry'); await page.until("!!document.querySelector('#shape-w')", 'N7 back on Geometry');
  // round 10 (K9): the optical model builder is an ARIA tree, used with the keyboard alone
  const opticalNodes = ['Component 1', 'Geometry', 'Materials', 'Physics', 'Optical modes', 'Analysis', 'Mesh', 'Study'];
  const opticalItems = await checkTree('optical', opticalNodes);
  assert.deepEqual(opticalItems.map(i => [i.name, i.level]), [['Component 1', 1], ['Geometry', 2], ['Materials', 2], ['Physics', 1], ['Optical modes', 2], ['Analysis', 1], ['Mesh', 2], ['Study', 2]]);
  assert.deepEqual(opticalItems.filter(i => i.selected === true).map(i => i.name), ['Geometry']);
  // Tab from the control before the tree lands on the selected node, the one tab stop
  await page.onElement('function(s){const t=this.querySelector(s);const all=[...this.querySelectorAll("button,select,input,[tabindex]")].filter(e=>e.tabIndex>=0&&!e.disabled&&e.offsetParent&&(t.compareDocumentPosition(e)&Node.DOCUMENT_POSITION_PRECEDING));all.at(-1).focus();return true}', '#tree');
  await press('Tab'); let at = await focused(); stage('K9 tab into the tree', at);
  assert.deepEqual([at.role, at.name, at.tabindex, at.selected], ['treeitem', 'Geometry', '0', 'true']);
  await press('ArrowDown'); assert.equal((await focused()).name, 'Materials');
  await press('ArrowUp'); await press('ArrowUp'); assert.equal((await focused()).name, 'Component 1');
  await press('End'); assert.equal((await focused()).name, 'Study');
  await press('Home'); assert.equal((await focused()).name, 'Component 1');
  // Enter selects a node (the inspector shows it); Space too; focus stays on the node
  await press('ArrowDown'); await press('ArrowDown'); await press('Enter'); at = await focused();
  assert.deepEqual([at.name, at.selected], ['Materials', 'true']); assert.match(await page.eval("document.querySelector('#inspector h2').textContent"), /materials/i);
  await press('End'); await press('ArrowUp'); await press(' '); at = await focused();
  assert.deepEqual([at.name, at.selected], ['Mesh', 'true']); assert.match(await page.eval("document.querySelector('#inspector h2').textContent"), /mesh/i);
  assert.equal(await page.eval("document.querySelectorAll('#tree [aria-selected=true]').length"), 1);
  // Left from a node goes to its group; Left on an open group closes it, Right opens it, Right again enters it
  await press('ArrowLeft'); at = await focused(); assert.deepEqual([at.name, at.expanded], ['Analysis', 'true']);
  await press('ArrowLeft'); at = await focused(); assert.deepEqual([at.name, at.expanded], ['Analysis', 'false']);
  assert.equal(await page.eval("[...document.querySelectorAll('#tree [data-node=Mesh],#tree [data-node=Study]')].every(e=>e.hidden)"), true);
  await press('End'); assert.equal((await focused()).name, 'Analysis', 'End skips the nodes of a closed group');
  await press('ArrowRight'); assert.equal((await focused()).expanded, 'true'); await press('ArrowRight'); assert.equal((await focused()).name, 'Mesh');
  // Enter and Space on a group heading close and open it once each (no second, native click)
  await press('ArrowLeft'); at = await focused(); assert.deepEqual([at.name, at.expanded], ['Analysis', 'true']);
  await press('Enter'); assert.equal((await focused()).expanded, 'false'); await press(' '); assert.equal((await focused()).expanded, 'true');
  await press('Home'); await press('ArrowDown'); await press('Enter'); at = await focused();
  assert.deepEqual([at.name, at.selected], ['Geometry', 'true']); await page.until("!!document.querySelector('#shape-w')", 'Geometry by keyboard');
  // the tab stop goes back to the selected node when the focus leaves the tree
  await page.onElement('function(s){const e=[...this.querySelectorAll(s)].find(b=>b.dataset.node==="Geometry");e.focus();return true}', '#tree [role=treeitem]');
  await press('ArrowDown'); await press('ArrowDown'); assert.equal((await focused()).name, 'Physics'); await press('Tab');
  assert.deepEqual(await page.eval("[...document.querySelectorAll('#tree [role=treeitem][tabindex=\"0\"]')].map(e=>e.dataset.node)"), ['Geometry']);
  await checkTree('optical after keys', opticalNodes);
  await page.type('#shape-w', 600);
  assert.equal(await page.eval("document.getElementById('autosave-status').textContent"), 'Unsaved inputs');
  // Messages says the edit and the Left x it moved, instead of keeping "Model ready…"
  assert.equal(await text('#file-status'), 'Width set to 600 nm. Left x moved to −300 nm to keep the centre. Run explicitly to compute new results.');
  await page.type('#shape-h', 300);
  assert.equal(await text('#file-status'), 'Height set to 300 nm. Run explicitly to compute new results.');
  // a Width edit keeps the core centred on x = 0; a Height edit keeps it on y = 0
  const sized = await page.eval("({x:document.getElementById('shape-x').value,y:document.getElementById('shape-y').value,study:[...document.querySelectorAll('#workflow .workflow-step')][3]?.innerText.replace(/\\s+/g,' ')})");
  stage('600 × 300 nm design', sized); assert.deepEqual([sized.x, sized.y], ['-300', '0']); assert.match(sized.study, /Ready to run/);
  // the step bar's wavelength opens the wavelength field under Physics › Optical modes
  assert.equal(await text('#workflow-wavelength'), 'λ 1550 nm');
  // round 15 (R8): a real button whose accessible name says what it does, as assistive technology finds it
  {const {result: doc} = await page.call('Runtime.evaluate', {expression: 'document'});
   const {nodes} = await page.call('Accessibility.queryAXTree', {objectId: doc.objectId, accessibleName: 'Wavelength 1550 nm, edit', role: 'button'});
   const found = nodes.filter(n => !n.ignored); assert.equal(found.length, 1, 'R8: one button named "Wavelength 1550 nm, edit"');
   const {object} = await page.call('DOM.resolveNode', {backendNodeId: found[0].backendDOMNodeId});
   const chip = await page.call('Runtime.callFunctionOn', {objectId: object.objectId, functionDeclaration: 'function(){return this.id+" "+this.tagName+" "+this.type}', returnByValue: true});
   stage('R8 wavelength chip', {ax: found[0].name?.value, element: chip.result.value}); assert.equal(chip.result.value, 'workflow-wavelength BUTTON button');}
  await page.click('#workflow-wavelength'); await sleep(200);
  const wavelengthField = await page.eval("({heading:document.querySelector('#inspector h2')?.textContent,focused:document.activeElement?.id,tree:document.querySelector('#tree [aria-current],#tree .selected,#tree [aria-selected=true]')?.textContent?.trim()||null})");
  stage('wavelength from the step bar', wavelengthField); assert.equal(wavelengthField.heading, 'Optical modes'); assert.equal(wavelengthField.focused, 'wavelength-number');
  // round 11 (L9): the Study settings edit the wavelength in the same field as Physics › Optical
  // modes (as Modes to find), and name the inputs the next run uses
  await page.click('nav [data-page=Model]'); await sleep(200); await page.clickTreeItem('Study'); await page.until("!!document.getElementById('wavelength-number')&&!!document.getElementById('next-run-inputs')", 'optical study settings');
  assert.match(await text('#next-run-inputs'), /^Next run uses \d+ × \d+ nm · Silicon · λ 1550 nm · core mesh \d+ nm · Modes to find 2$/);
  assert.equal(await page.eval("document.querySelectorAll('input[id*=wavelength]').length"), 1);
  await noOverflow('optical study');
  await page.type('#wavelength-number', 1560); await sleep(200);
  assert.match(await text('#next-run-inputs'), / · λ 1560 nm · /);
  // a value out of range is refused here as in Physics › Optical modes, and holds Run
  await page.type('#wavelength-number', 1300); await sleep(200);
  const refused = await page.eval("({invalid:document.getElementById('wavelength-number').getAttribute('aria-invalid'),run:document.getElementById('run-optical').disabled,hint:document.getElementById('wavelength-number-hint')?.textContent})");
  stage('wavelength refused in Study', refused); assert.deepEqual(refused, {invalid: 'true', run: true, hint: 'Wavelength must be between 1400–1700 nm.'});
  await page.type('#wavelength-number', 1550); await sleep(200);
  await page.clickTreeItem('Optical modes'); await page.until("document.querySelector('#inspector h2')?.textContent==='Optical modes'", 'Optical modes settings');
  assert.equal(await page.eval("document.getElementById('wavelength-number').value"), '1550', 'one wavelength in Study and in Optical modes');
  assert.equal(await page.eval("document.getElementById('run-optical').disabled"), false);
  await toGeometry();
  await runAndWait();
  // the dock heading and the footer say what was computed, naming the same run
  stage('sequence after run 1', await opticalSequence());
  assert.deepEqual(await opticalSequence(), {heading: 'Run 1 · solved from the current inputs', status: 'Run 1 · solved from the current inputs · press Run to solve again'});
  await noOverflow('optical results');
  // after a run of these inputs the Study step says so, and the title carries no revision counter
  const afterRun = await page.eval("({study:[...document.querySelectorAll('#workflow .workflow-step')][3]?.innerText.replace(/\\s+/g,' '),title:document.getElementById('autosave-status').textContent})");
  stage('first run complete', afterRun); assert.match(afterRun.study, /Run complete/); assert.doesNotMatch(afterRun.title, /Revision/);
  // one save indicator: before a file save it says which copy exists, and the footer repeats it
  await page.until("document.getElementById('autosave-status').textContent==='Not saved to a file · kept for recovery in this browser'", 'save indicator after a run', 20000);
  assert.equal(await page.eval("document.getElementById('autosave-status').textContent"), 'Not saved to a file · kept for recovery in this browser');
  // n_eff with 8 decimals in the mode list as in the modes table; plot axes and the inspector in nm
  const resultsView = await page.eval("({options:[...document.querySelectorAll('#field-mode option')].map(o=>o.textContent),values:[...document.querySelectorAll('#modes-table [data-neff]')].map(e=>e.textContent),polarization:[...document.querySelectorAll('#modes-table [data-polarization]')].map(e=>e.textContent),loss:[...document.querySelectorAll('#modes-table [data-loss]')].map(e=>e.textContent),area:[...document.querySelectorAll('#modes-table [data-area]')].map(e=>({text:e.textContent,value:Number(e.dataset.areaValue),title:e.title})),areaSource:[...document.querySelectorAll('#run-details .pair')].map(e=>e.textContent).find(t=>/^Effective area/.test(t))||null,head:[...document.querySelectorAll('#modes-table thead th')].map(e=>e.firstChild.textContent),hint:document.querySelector('#modes-table-hint [data-group-index-hint]')?.textContent??null,headText:[...document.querySelectorAll('#modes-table thead th')].map(e=>e.textContent),hintInTable:!!document.querySelector('#modes-table [data-group-index-hint]'),hintAbove:(()=>{const h=document.getElementById('modes-table-hint'),t=document.getElementById('modes-table');return !!h&&!!t&&h.nextElementSibling===t&&h.getBoundingClientRect().bottom<=t.getBoundingClientRect().top})(),lossless:document.getElementById('lossless-note')?.textContent||null,probe:[...document.querySelectorAll('.probe-controls label')].map(l=>l.firstChild.textContent),pin:document.getElementById('pin-run')?.textContent||null,imports:document.getElementById('import-runs')?.textContent})");
  stage('results view', resultsView);
  for (const option of resultsView.options) assert.match(option, /^Mode \d · (TE-like|TM-like|hybrid|pair) · n_eff \d\.\d{8}$/);
  assert.deepEqual(resultsView.head, ['Mode', 'n_eff', 'Polarization', 'Absorption loss (dB/cm)', 'A_eff (µm²)', 'n_g']);
  assert.equal(resultsView.hint, 'Off · turn on in Study or Optical modes', 'round 12 (N4): the table says how to turn n_g on');
  // round 15 (R3): the header reads just "n_g"; the hint is the line above the table, as on Compare
  assert.deepEqual(resultsView.headText, ['Mode', 'n_eff', 'Polarization', 'Absorption loss (dB/cm)', 'A_eff (µm²)', 'n_g']);
  assert.deepEqual([resultsView.hintInTable, resultsView.hintAbove], [false, true], 'R3: the n_g hint is above the table, not in it');
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
  // (round 10: the column is "Absorption loss (dB/cm)" and every cell's help says absorption only)
  assert.deepEqual(resultsView.loss, ['0 dB/cm', '0 dB/cm']); assert.match(resultsView.lossless, /^Absorption loss counts material absorption \(k\) only: all materials have k = 0/);
  const lossTitles = await page.eval("[...document.querySelectorAll('#modes-table [data-loss]')].map(e=>e.title)");
  const absorptionHelp = 'Absorption (material k) only; leakage and radiation are not computed in a closed window';
  assert.deepEqual(lossTitles, [absorptionHelp, absorptionHelp]);
  assert.equal(await page.eval("document.querySelector('#modes-table thead th:nth-child(4)').title"), absorptionHelp);
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
  const named = await text('.run-item'); stage('run named', {item: named}); assert.match(named, /^Pinned · Run 1 · design A · closed · 600 × 300 nm/);
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
  assert.deepEqual(await opticalSequence(), {heading: 'Run 1 · design A 600 × 300 nm · current inputs 700 × 300 nm', status: 'Run 1 · design A 600 × 300 nm · current inputs 700 × 300 nm · press Run to compute them'});
  // while an input error holds Run, the heading repeats the footer instead of asking for a Run
  await page.type('#shape-w', 99999);
  const held = await opticalSequence(); stage('input error holds Run', held);
  assert.deepEqual(held, {heading: 'Input errors · correct or restore the last valid values', status: 'Input errors · correct or restore the last valid values'});
  await page.type('#shape-w', 700);
  assert.deepEqual(await opticalSequence(), {heading: 'Run 1 · design A 600 × 300 nm · current inputs 700 × 300 nm', status: 'Run 1 · design A 600 × 300 nm · current inputs 700 × 300 nm · press Run to compute them'});
  await runAndWait();
  await page.click('nav [data-page=Compare]'); await sleep(500);
  const before = await delta(); assert.ok(before, 'comparison shows a delta n_eff');
  // round 14 (Q8): the run list's Compare A / Compare B is a badge of its own after the label, and the
  // button's accessible name still ends in "· Compare A" / "· Compare B"
  const badges = await page.eval("[...document.querySelectorAll('.run-item')].filter(b=>b.querySelector('.compare-side')).map(b=>{const t=b.querySelector('.compare-side'),c=getComputedStyle(t),r=t.getBoundingClientRect(),br=b.getBoundingClientRect(),range=document.createRange();range.setStart(b.firstChild,0);range.setEnd(b.firstChild,b.firstChild.length);const label=[...range.getClientRects()].at(-1);return {text:t.textContent,inside:r.left>=br.left-0.5&&r.right<=br.right+0.5,after:r.left>=label.right-0.5||r.top>=label.bottom-0.5,border:parseFloat(c.borderTopWidth)>0&&c.borderTopStyle!=='none',fill:c.backgroundColor!==getComputedStyle(b).backgroundColor}})");
  const badgeNames = (await page.axTree(['button', 'toggleButton'])).filter(n => / · Compare [AB]$/.test(n.name || '')).map(n => n.name.slice(-11));
  stage('Q8 Compare badges', {badges, badgeNames});
  assert.deepEqual(badges.map(b => b.text).sort(), ['Compare A', 'Compare B']);
  assert.ok(badges.every(b => b.inside && b.after && b.border && b.fill), JSON.stringify(badges));
  assert.deepEqual(badgeNames.sort(), ['· Compare A', '· Compare B']);
  const neffTable = await compareTableRows();
  stage('two designs compared', {deltaNeff: before, table: neffTable});
  assert.ok(neffTable, 'Compare shows the n_eff table'); assert.equal(neffTable.rows.length, 2);
  assert.equal(neffTable.caption, 'Modes of A and B matched by field overlap');
  assert.deepEqual(neffTable.head.slice(0, 4), ['Modes', 'Polarization A', 'Polarization B', 'Overlap']);
  // round 12 (N1): the run names are in the line above the table, the headers short and grouped A | B
  assert.deepEqual(neffTable.head.slice(4, 6), ['n_eff A', 'n_eff B']); assert.deepEqual(neffTable.runs, ['A · Run 1 · design A · closed · 600 × 300 nm · Silicon · λ 1550 nm', 'B · Run 2 · closed · 700 × 300 nm · Silicon · λ 1550 nm']);
  assert.deepEqual(neffTable.head.slice(8), ['A_eff A (µm²)', 'A_eff B (µm²)', 'Absorption loss A (dB/cm)', 'Absorption loss B (dB/cm)', 'n_g A', 'n_g B']);
  // both sides of a matched row give their A_eff in µm²
  for (const row of neffTable.rows) assert.match(row[8] + ' ' + row[9], /^\d\.\d{4} \d\.\d{4}$/);
  assert.equal(neffTable.rows[0][0], 'A mode 1 ↔ B mode 1'); assert.equal(neffTable.short[0], '1 ↔ 1');
  assert.equal(neffTable.rows[0][6], before, 'the table and the sentence give the same Δn_eff');
  // the field panels do not repeat the name, and come before the n_eff table
  const panels = await page.eval("({headings:[...document.querySelectorAll('.compare-grid h3')].map(h=>h.textContent),plotsFirst:!!(document.querySelector('.compare-grid').compareDocumentPosition(document.getElementById('compare-neff'))&Node.DOCUMENT_POSITION_FOLLOWING),plotTop:Math.round(document.getElementById('compare-field-a').getBoundingClientRect().top+scrollY),viewport:innerHeight})");
  stage('compare panels', panels);
  assert.deepEqual(panels.headings, ['A · Run 1 · design A · closed · 600 × 300 nm · Silicon · λ 1550 nm', 'B · Run 2 · closed · 700 × 300 nm · Silicon · λ 1550 nm']);
  assert.ok(panels.plotsFirst, 'field plots before the n_eff table');
  await page.screenshot('compare');
  // round 10 (K1): absorption loss A and B on every row, from the saved indices, with the absorption-only help
  const lossCells = await page.eval("[...document.querySelectorAll('#compare-neff tbody tr')].map(r=>[r.querySelector('[data-loss-a]')?.textContent,r.querySelector('[data-loss-b]')?.textContent,r.querySelector('[data-loss-a]')?.title,r.querySelector('[data-loss-b]')?.title])");
  stage('K1 Compare loss', lossCells); assert.equal(lossCells.length, neffTable.rows.length);
  for (const row of lossCells) assert.deepEqual(row, ['0 dB/cm', '0 dB/cm', absorptionHelp, absorptionHelp]);
  // the two Absorption loss headers (n_g A and n_g B follow them since M5)
  assert.deepEqual(await page.eval("[...document.querySelectorAll('#compare-neff thead th')].filter(t=>/^Absorption loss /.test(t.dataset.column||t.textContent)).map(t=>t.title)"), [absorptionHelp, 'Absorption loss A (dB/cm): ' + absorptionHelp, 'Absorption loss B (dB/cm): ' + absorptionHelp]);
  await noOverflow('Compare with loss columns');
  // round 10 (K5): the plots are framed on the core as Results frames it, and the probe line sits under each plot
  // Compare opened afresh (from Results) at 1440 × 900 and at 1280 × 800
  const overlaps = (p, q) => p[0] < q[2] && q[0] < p[2] && p[1] < q[3] && q[1] < p[3];
  let compareFrame;
  for (const [width, height] of [[1440, 900], [1280, 800]]) {
    await page.call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile: false}); await sleep(300);
    await page.click('nav [data-page=Results]'); await page.until("!!document.getElementById('optical-field')", 'Results before Compare');
    await page.click('nav [data-page=Compare]'); await page.until("!!document.getElementById('compare-neff')", 'Compare opened'); await sleep(300);
    compareFrame = await page.eval("(()=>{const r=e=>{const b=e.getBoundingClientRect();return [b.left,b.top,b.right,b.bottom]};const pane=document.getElementById('canvas').getBoundingClientRect();return ['a','b'].map(s=>({bounds:document.getElementById('compare-field-'+s).dataset.viewBounds,canvas:r(document.getElementById('compare-field-'+s)),probe:r(document.getElementById('compare-probe-'+s)),pane:[pane.top,pane.bottom],picker:r(document.getElementById('compare-mode'))}))})()");
    stage('K5 Compare plots', {width, height, compareFrame}); if (width === 1440) await page.screenshot('compare-framed-1440');
    for (const f of compareFrame) {
      assert.ok(!overlaps(f.canvas, f.probe), 'the probe line is outside the plot');
      // the middle of the plot (the window is centred on the core) is in view when Compare opens, and so is the matched-modes picker
      const middle = (f.canvas[1] + f.canvas[3]) / 2;
      assert.ok(middle > f.pane[0] && middle < f.pane[1], `the plot's middle is in the first view of the pane at ${width} × ${height}: ${f.canvas} / ${f.pane}`);
      assert.ok(f.picker[1] >= f.pane[0], `the matched-modes picker stays in view at ${width} × ${height}`);
    }
  }
  // the plots of Compare are drawn on the window Results draws for the same run, and that window
  // holds the core, at 1440 × 900 and at 390 × 844 (the 1280 × 800 frame above is checked the same way)
  const sameWindowAsResults = async tag => {
    const compareBounds = await page.eval("document.getElementById('compare-field-a').dataset.viewBounds");
    await page.onElement('function(selector){[...this.querySelectorAll(selector)].find(b=>/Run 1 · design A/.test(b.textContent)).click();return true}', '.run-item'); await sleep(200);
    await page.click('#open-in-results'); await page.until("!!document.getElementById('optical-field')", 'Run 1 in Results ' + tag);
    const resultsBounds = await page.eval("document.getElementById('optical-field').dataset.viewBounds");
    // Run 1's core, from its shapes (nm → µm): the drawn window holds all of it
    stage('K5 Compare and Results windows ' + tag, {compareBounds, resultsBounds});
    assert.equal(compareBounds, resultsBounds, `Compare A (Run 1) and Results of Run 1 draw the same window at ${tag}`);
    const [x0, x1, y0, y1] = compareBounds.split(',').map(Number);
    // Run 1 is 600 × 300 nm centred on x = 0, with its bottom at y = 0 (y from 0 to 300 nm)
    assert.ok(x0 <= -0.3 && x1 >= 0.3 && y0 <= 0 && y1 >= 0.3, `the core is inside the drawn window at ${tag}: ${compareBounds}`);
    await page.click('nav [data-page=Compare]'); await page.until("!!document.getElementById('compare-neff')", 'Compare again ' + tag);
    await page.onElement('function(selector){[...this.querySelectorAll(selector)].find(b=>/^Run 2 · closed · 700/.test(b.textContent)).click();return true}', '.run-item'); await sleep(200);
  };
  assert.equal(compareFrame[0].bounds, (await page.eval("document.getElementById('compare-field-a').dataset.viewBounds")));
  await sameWindowAsResults('1280 × 800');
  for (const [width, height, mobile] of [[1440, 900, false], [390, 844, true]]) {
    await page.call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile}); await sleep(300);
    await sameWindowAsResults(`${width} × ${height}`);
    if (mobile) {
    const phone = await page.eval("['a','b'].map(s=>{const c=document.getElementById('compare-field-'+s).getBoundingClientRect(),p=document.getElementById('compare-probe-'+s).getBoundingClientRect();return {canvas:[c.left,c.top,c.right,c.bottom],probe:[p.left,p.top,p.right,p.bottom]}})");
    stage('K5 Compare plots at 390', phone); for (const f of phone) assert.ok(!overlaps(f.canvas, f.probe), 'the probe line is outside the plot at 390 px');
    }
    await page.call('Emulation.setDeviceMetricsOverride', {width: 1280, height: 800, deviceScaleFactor: 1, mobile: false}); await sleep(300);
  }
  // round 10 (K4): a run clicked on Compare is selected and Compare stays; Open in Results shows it there
  const pressedPage = () => page.eval("[...document.querySelectorAll('nav [data-page]')].filter(b=>b.getAttribute('aria-selected')==='true').map(b=>b.dataset.page)");
  await page.onElement('function(selector){[...this.querySelectorAll(selector)].find(b=>/Run 1 · design A/.test(b.textContent)).click();return true}', '.run-item'); await sleep(300);
  const k4 = await page.eval("({pressed:[...document.querySelectorAll('.run-item[aria-pressed=true]')].map(b=>b.textContent),table:!!document.getElementById('compare-neff'),open:document.getElementById('open-in-results')?.textContent})");
  stage('K4 run clicked on Compare', {...k4, page: await pressedPage()});
  assert.deepEqual(await pressedPage(), ['Compare']); assert.ok(k4.table); assert.equal(k4.pressed.length, 1); assert.match(k4.pressed[0], /^Pinned · Run 1 · design A/);
  assert.equal(k4.open, 'Open Run 1 · design A in Results');
  // round 10 (K6): with the pointer over the other card, exactly one card reads as selected
  const cardLook = async () => {
    const other = await page.eval("(()=>{const b=[...document.querySelectorAll('.run-item')].find(e=>e.getAttribute('aria-pressed')!=='true').getBoundingClientRect();return {x:b.left+b.width/2,y:b.top+b.height/2}})()");
    await page.call('Input.dispatchMouseEvent', {type: 'mouseMoved', x: other.x, y: other.y}); await sleep(150);
    return page.eval("(()=>{const sel=getComputedStyle(document.querySelector('.run-item[aria-pressed=true]'));return {pressed:document.querySelectorAll('.run-item[aria-pressed=true]').length,looks:[...document.querySelectorAll('.run-item')].filter(e=>{const c=getComputedStyle(e);return c.backgroundColor===sel.backgroundColor&&c.boxShadow===sel.boxShadow}).length,hovered:[...document.querySelectorAll('.run-item:hover')].length}})()");
  };
  const look = await cardLook(); stage('K6 one card selected', look); assert.deepEqual(look, {pressed: 1, looks: 1, hovered: 1});
  await page.click('#open-in-results'); await page.until("!!document.getElementById('optical-field')", 'Open in Results');
  assert.deepEqual(await pressedPage(), ['Results']); assert.match(await page.eval("document.querySelector('.dock-title>span').textContent"), /^Run 1 · design A 600 × 300 nm · current inputs 700 × 300 nm$/);
  // round 10 (K6): on Results the tree marks no model node, not Study; since round 14 (Q9) it marks Results › Runs
  assert.deepEqual((await page.axTree()).filter(n => n.role === 'treeitem' && n.selected === true).map(n => n.name), ['Runs · 2 of 6']);
  assert.deepEqual(await cardLook(), {pressed: 1, looks: 1, hovered: 1});
  // round 10 (K10): a run with other inputs than the current ones is information: the step bar is neutral
  const tone = await page.eval("(()=>{const b=[...document.querySelectorAll('#workflow .workflow-step')][4];return {tone:b.dataset.tone,state:b.dataset.state,color:getComputedStyle(b.querySelector('span')).color,muted:getComputedStyle(document.querySelector('.muted')||document.body).color}})()");
  stage('K10 neutral step', tone); assert.deepEqual([tone.state, tone.tone], ['attention', 'info']); assert.equal(tone.color, 'rgb(97, 112, 134)', 'the muted colour, not the warning colour');
  // back to Compare with Run 2 selected, as before this stage
  await page.click('nav [data-page=Compare]'); await page.until("!!document.getElementById('compare-neff')", 'Compare again');
  await page.onElement('function(selector){[...this.querySelectorAll(selector)].find(b=>/^Run 2 · closed · 700/.test(b.textContent)).click();return true}', '.run-item'); await sleep(300);
  assert.deepEqual(await pressedPage(), ['Compare']); assert.match(await text('.run-item[aria-pressed=true]'), /^Run 2 · closed · 700/);
  // P3: File › Save writes the project file; the session file of this model is File › Export ›
  // Model with runs, which this stage and the recovery stages after it check
  await page.click('#menu-export-session'); await confirmName('first save');
  let sessionFile;
  for (let i = 0; i < 100 && !sessionFile; i++) { sessionFile = (await readdir(downloads)).find(f => f.endsWith('.json')); if (!sessionFile) await sleep(100); }
  assert.ok(sessionFile, 'Save session downloaded a file');
  const session = JSON.parse(await readFile(join(downloads, sessionFile), 'utf8'));
  const savedHeader = await page.eval("document.getElementById('autosave-status').textContent"), savedMessage = await page.eval("document.getElementById('file-status').textContent");
  stage('session saved', {file: sessionFile, runs: session.runs?.length, header: savedHeader, message: savedMessage});
  assert.equal(session.runs?.length, 2);
  assert.match(sessionFile, /^optical-waveguide-session-\d{4}-\d{2}-\d{2}-\d{4}\.json$/);
  assert.ok(savedMessage.startsWith(`Session file ${sessionFile} sent to your browser's Downloads: `), savedMessage);
  assert.doesNotMatch(savedMessage, /have no run yet/, 'Q2: Run 2 has the current inputs');
  // round 14 (Q1): a download reads "<name> · downloaded <time>", with the " (1)" note as title text
  const savedPrefix = `${sessionFile} · downloaded `;
  assert.ok(savedHeader.startsWith(savedPrefix), savedHeader); assert.match(savedHeader.slice(savedPrefix.length), /^\d{1,2}:\d\d(?: [AP]M)?$/, savedHeader);
  // the footer is the model's indicator; the title bar names the project, which no file holds yet
  assert.deepEqual(await page.eval("[document.getElementById('project').hasAttribute('title'),document.getElementById('autosave-status').title]"), [false, 'Your browser may have added “ (1)” to the file name.']);
  assert.match(await page.eval("document.getElementById('project').textContent"), /^Untitled project · not saved to a file · /);
  // the title names the file and that it was downloaded, never that it reached the disk
  assert.doesNotMatch(savedHeader, /disk/i, 'the title never claims the file reached the disk');
  // the footer repeats the title's save indicator and never says "pending"
  const savedFooter = await page.eval("document.getElementById('autosave-status').textContent");
  assert.equal(savedFooter, savedHeader); assert.doesNotMatch(savedFooter, /pending/i);
  // round 10 (K3): a page, a run or a mode chosen is not a change: the title still names the file
  await page.click('nav [data-page=Results]'); await page.until("!!document.getElementById('field-mode')", 'Results after save');
  await page.choose('#field-mode', '1'); await sleep(300);
  const keptName = await page.eval("document.getElementById('autosave-status').textContent"); stage('K3 title after a mode change', {keptName});
  assert.ok(keptName.startsWith(`${sessionFile} · downloaded `), keptName);
  await page.choose('#field-mode', '0'); await page.click('nav [data-page=Compare]'); await page.until("!!document.getElementById('compare-neff')", 'Compare after save');
  assert.ok((await page.eval("document.getElementById('autosave-status').textContent")).startsWith(`${sessionFile} · downloaded `));
  await page.until("/^Browser recovery updated/.test(document.getElementById('notebook-recovery-detail').textContent)", 'browser recovery updated', 20000);

  // Restart with the page open: Run reconnects and asks to run again.
  const stopped = await stopServer(server);
  stage('server stopped', stopped);
  // a server still running would answer the restart check and hide a failed restart
  if (stopped.exit === null && stopped.signal === null) throw new Error('Studio did not stop within 15 s');
  server = await startServer('server-2');
  await toGeometry(); await page.click('#run-optical'); if (await page.eval("!!document.getElementById('run-drop-confirm')?.open")) await page.click('#run-drop-confirm-run');
  await page.until("/Studio was restarted/.test(document.getElementById('job-message').textContent)&&/^Connected/.test(document.getElementById('connection-status').textContent)", 'reconnect after restart', 20000);
  stage('reconnected after restart', {message: await page.eval("document.getElementById('job-message').textContent")});

  // round 10 (K6): browser recovery keeps the page shown; Compare again before the reload, so the
  // restore below opens Compare because it was the page shown, not because there are two runs
  await page.click('nav [data-page=Compare]'); await page.until("!!document.getElementById('compare-neff')", 'Compare before reload');
  await page.until("/^Browser recovery updated/.test(document.getElementById('notebook-recovery-detail').textContent)", 'browser recovery updated', 20000); await sleep(1500);
  // Reload: the start page offers the last session; recovering it restores the comparison.
  await page.call('Page.reload');
  // round 9 (J3): the one stored session is the optical one, so the Optical waveguide card resumes
  // it and no box above lists it again; the session file route and its note are at the top of the page (P2)
  await page.until("!!document.querySelector('#resume-optical')", 'resume offer');
  const card = await page.eval("(()=>{const r=document.getElementById('resume-optical').getBoundingClientRect();return {top:Math.round(r.top),bottom:Math.round(r.bottom),inView:r.top>=0&&r.bottom<=innerHeight}})()");
  stage('resume card', card); assert.ok(card.inView, 'the Optical waveguide resume offer inside the first viewport');
  // the routes back say which copy is durable
  const routes = await page.eval("({latest:document.getElementById('resume-optical').textContent,listed:[...document.querySelectorAll('[data-resume-record]:not(#resume-optical)')].map(b=>b.textContent),box:!!document.querySelector('.resume-card'),open:document.getElementById('library-open-file').textContent,beside:!!document.getElementById('library-open-file').closest('.card-slot,.resume-card'),top:document.getElementById('canvas').firstElementChild?.contains(document.getElementById('library-open-file')),count:[...document.querySelectorAll('button')].filter(b=>/^Open file…$/.test(b.textContent)).length,note:document.querySelector('.library-portable')?.textContent,footer:document.getElementById('autosave-status').textContent})");
  stage('routes back', routes);
  // the offer names the session file the record was last sent to
  // round 10 (K3, K7): one phrase for browser recovery, and the file the record still matched
  // round 11 (L9): the record is the same as the file, so the offer names the file's save time, not the record's
  assert.ok(routes.latest.startsWith('Restore from this browser · Optical waveguide · Run 1 · design A, Run 2 · same as file ' + sessionFile + ', saved '), routes.latest);
  assert.match(routes.latest, /, saved \d{1,2}:\d\d(?: [AP]M)?$/);
  assert.doesNotMatch(await text('#canvas'), /Recover|\(this browser/, 'the Library page says Restore from this browser'); assert.equal(routes.open, 'Open file…');
  // round 19 (Y1): the box above leads with the newest stored session, the record the card resumes
  assert.equal(routes.listed.length, 1, JSON.stringify(routes.listed)); assert.equal(routes.box, true);
  assert.ok(routes.listed[0].startsWith('Restore newest from this browser: Optical waveguide · 2 runs · Run 1 · design A, Run 2 · '), routes.listed[0]);
  assert.equal(routes.beside, false, 'Open file is not under a card'); assert.equal(routes.top, true, 'Open file is at the top of the Library'); assert.equal(routes.count, 1);
  await libraryOpenFile('with a resume offer');
  assert.equal(routes.note, 'A project file is the copy that moves between computers; browser recovery stays in this browser.');
  assert.equal(routes.footer, 'Last session kept in this browser · 2 runs');
  await page.screenshot('resume-card');
  // a fresh page holds nothing an open would lose, so recovery asks nothing
  await page.click('#resume-optical'); await page.until("!!document.getElementById('compare-neff')", 'recovered comparison');
  await treeMarks('Compare after a restore');
  assert.equal(await page.eval("!!document.querySelector('dialog[open]')"), false, 'no confirmation over an untouched workspace');
  const after = await delta(), recoveredHeader = await page.eval("document.getElementById('autosave-status').textContent");
  stage('comparison recovered', {deltaNeff: after, header: recoveredHeader}); assert.equal(after, before);
  // round 10 (K3): the record still matched the file it was sent to: the title says so
  assert.equal(recoveredHeader, `Recovered from this browser · same as file ${sessionFile}`);
  // round 14 (Q3): the file the restored record still matched is the current file: Save As suggests it
  await page.click('#menu-export-session'); await page.until("document.getElementById('save-name-dialog').open", 'Q3 Save As after a restore');
  assert.equal(await page.eval("document.getElementById('save-name-input').value"), sessionFile, 'Q3 Save As prefill');
  await page.click('#save-name-cancel'); await page.until("!document.getElementById('save-name-dialog').open", 'Q3 Save As cancelled');
  assert.equal(await page.eval("document.getElementById('autosave-status').textContent"), `Recovered from this browser · same as file ${sessionFile}`, 'a cancelled Save As changes nothing');
  // the recovered run is current, and the dock and footer say where it came from
  const recoveredSequence = await opticalSequence(); stage('recovered sequence', recoveredSequence);
  assert.deepEqual(recoveredSequence, {heading: 'Run 2 · recovered from this browser, not recomputed', status: 'Run 2 · recovered from this browser, not recomputed · press Run to compute it here'});
  // the older run viewed: the step bar, the result and its settings all say the current inputs
  // differ from this run, naming both, and none speaks of edits (there were none)
  await page.click('nav [data-page=Results]'); await page.until("!!document.querySelector('.run-item')", 'run list');
  await page.onElement('function(selector){[...this.querySelectorAll(selector)].find(b=>/^Pinned · Run 1 · design A/.test(b.textContent)).click();return true}', '.run-item');
  await page.until("/600 × 300 nm/.test(document.querySelector('#canvas p')?.textContent||'')", 'older run shown');
  const viewed = await page.eval("({step:[...document.querySelectorAll('#workflow .workflow-step')][4]?.innerText.replace(/\\s+/g,' '),result:document.querySelector('#canvas p').textContent,inputs:[...document.querySelectorAll('#inspector .pair')].find(p=>p.firstElementChild?.textContent==='Inputs')?.lastElementChild.textContent,header:document.getElementById('autosave-status').textContent})");
  stage('older run viewed', viewed);
  assert.equal(viewed.step, '5. Results Current inputs differ from this run');
  // round 9 (J4): the line under the heading names each difference once
  assert.match(viewed.result, /^Current inputs differ from this run: this run 600 × 300 nm · Silicon, current 700 × 300 nm · Silicon; unchanged: λ 1550 nm · core mesh \d+ nm$/);
  for (const part of ['600 × 300 nm', '700 × 300 nm', 'λ 1550 nm']) assert.equal(viewed.result.split(part).length, 2, part);
  assert.equal(viewed.inputs, 'Current inputs differ from this run: this run 600 × 300 nm · Silicon, current 700 × 300 nm · Silicon');
  for (const t of Object.values(viewed)) assert.doesNotMatch(t, /edits are kept/);
  // round 9 (J5): the dock, the footer, the title and the step bar describe the viewed run, run 1
  const viewedNames = await opticalSequence(); stage('older run named', {...viewedNames, header: viewed.header});
  assert.deepEqual(viewedNames, {heading: 'Run 1 · design A 600 × 300 nm · current inputs 700 × 300 nm', status: 'Run 1 · design A 600 × 300 nm · current inputs 700 × 300 nm · current inputs from Run 2'});
  // round 11 (L3): a short suffix on Results
  assert.match(viewed.header, / · viewing Run 1 · design A \(other inputs\)$/); assert.doesNotMatch(viewed.header, /Unsaved inputs/);
  assert.equal(await page.eval("document.getElementById('autosave-status').textContent"), viewed.header.replace(/^Optical waveguide \/ /, ''));
  // round 11 (L6): on Results no tree node is marked, and a node under the pointer does not look selected
  await treeMarks('Results');
  // round 14 (Q9; pre-registered): the optical tree has a Results group, as the multiphysics tree:
  // Runs · N of 6 (the run limit) and, with two runs, Compare, in the same ARIA tree and keys
  const q9Items = await checkTree('optical with runs', [...opticalNodes, 'Results · run 1', 'Runs · 2 of 6', 'Compare']);
  assert.deepEqual(q9Items.slice(-3).map(i => [i.name, i.level, i.selected === true]), [['Results · run 1', 1, false], ['Runs · 2 of 6', 2, true], ['Compare', 2, false]]);
  assert.equal(await page.eval("document.querySelector('#tree [role=treeitem][tabindex=\"0\"]').dataset.node"), 'results:runs', 'the tab stop is the selected Runs node');
  await page.onElement('function(s){this.querySelector(s).focus();return true}', '#tree [data-node="results:runs"]');
  await press('ArrowUp'); assert.deepEqual([(await focused()).name, (await focused()).expanded], ['Results · run 1', 'true']);
  await press('End'); assert.equal((await focused()).name, 'Compare'); await press('Enter'); await page.until("!!document.getElementById('compare-neff')", 'Q9 Compare from the tree');
  assert.deepEqual(await pressedPage(), ['Compare']);
  await page.click('nav [data-page=Model]'); await sleep(200);
  await page.onElement('function(s){this.querySelector(s).focus();return true}', '#tree [data-node="results:runs"]'); await press('Enter');
  await page.until("!!document.getElementById('optical-field')", 'Q9 Results from the tree');
  assert.deepEqual(await pressedPage(), ['Results']); assert.match(await page.eval("document.querySelector('.dock-title>span').textContent"), /^Run 1 · design A 600 × 300 nm · /, 'the shown run is kept');
  stage('Q9 Results group', {items: q9Items.slice(-3)});
  // round 11 (L3): on the Model tab the title describes the current inputs only, and the Study
  // settings say which geometry the next run uses
  await page.click('nav [data-page=Model]'); await sleep(200);
  assert.doesNotMatch(await page.eval("document.getElementById('autosave-status').textContent"), /viewing/);
  await page.clickTreeItem('Study'); await page.until("!!document.getElementById('next-run-inputs')", 'L3 study settings');
  assert.match(await text('#next-run-inputs'), /^Next run uses 700 × 300 nm · Silicon · λ 1550 nm · /);
  // Use this run's inputs: run 1's inputs become the current ones at once (no question: the runs
  // stay), the title and the step bar agree, and Undo takes them back
  await page.click('nav [data-page=Results]'); await page.until("!!document.getElementById('restore-run-input')", 'L3 Use this run\'s inputs');
  assert.equal(await text('#restore-run-input'), 'Use this run’s inputs'); assert.match(await text('#restore-run-input-hint'), /^The next run uses the current inputs \(700 × 300 nm · Silicon\)\. This loads Run 1 · design A’s inputs instead; Undo takes them back\.$/);
  const useSlot = await page.eval("document.getElementById('restore-run-input').parentElement.id||document.getElementById('restore-run-input').parentElement.className");
  await page.click('#restore-run-input'); await page.until("!document.getElementById('restore-run-input')&&/Same as the current inputs/.test(document.getElementById('inspector').textContent)", 'L3 inputs used');
  const used = await page.eval("({dialog:!!document.querySelector('dialog[open]'),header:document.getElementById('autosave-status').textContent,step:[...document.querySelectorAll('#workflow .workflow-step')][4]?.innerText.replace(/\\s+/g,' '),runs:document.querySelectorAll('.run-item').length,page:[...document.querySelectorAll('nav [data-page]')].filter(b=>b.getAttribute('aria-selected')==='true').map(b=>b.dataset.page),message:document.getElementById('file-status').textContent})");
  stage('L3 run inputs used', used);
  assert.equal(used.dialog, false); assert.doesNotMatch(used.header, /viewing/); assert.equal(used.step, '5. Results Result for these inputs'); assert.equal(used.runs, 2); assert.deepEqual(used.page, ['Results']);
  // round 13 (O5): only the settings that change, from → to (Width 700 → 600 nm keeps the centre, so Left x moves too)
  assert.equal(used.message, 'Current inputs set from Run 1 · design A: Width 700 → 600 nm · Left x −350 → −300 nm. The next run uses them; Undo takes them back.');
  // round 14 (Q4): the same change list stays where the button was, until the next input edit
  const usedNote = () => page.eval("(()=>{const e=document.getElementById('restore-run-input-done');return e&&{text:e.textContent,slot:e.parentElement.id||e.parentElement.className,inPanel:document.getElementById('inspector').contains(e)}})()");
  const q4 = await usedNote(); stage('Q4 change list by the button', {q4, useSlot});
  assert.deepEqual(q4, {text: used.message, slot: useSlot, inPanel: true});
  await page.click('nav [data-page=Model]'); await sleep(200); await page.clickTreeItem('Study'); await page.until("!!document.getElementById('next-run-inputs')", 'L3 study after use');
  assert.match(await text('#next-run-inputs'), /^Next run uses 600 × 300 nm · Silicon · /);
  // a page change is not an edit: the change list is still there on Results
  await page.click('nav [data-page=Results]'); await page.until("!!document.getElementById('restore-run-input-done')", 'Q4 change list after a page change');
  assert.equal((await usedNote()).text, used.message);
  await page.click('nav [data-page=Model]'); await sleep(200); await page.clickTreeItem('Study'); await page.until("!!document.getElementById('next-run-inputs')", 'Q4 study again');
  await page.click('#undo-edit'); await sleep(200);
  assert.match(await text('#next-run-inputs'), /^Next run uses 700 × 300 nm · Silicon · /, 'Undo takes the run\'s inputs back');
  await page.click('nav [data-page=Results]'); await page.until("!!document.getElementById('restore-run-input')", 'L3 back on Results');
  assert.equal(await usedNote(), null, 'Q4: the next input edit (Undo) ends the change list');
  assert.match(await page.eval("document.getElementById('autosave-status').textContent"), / · viewing Run 1 · design A \(other inputs\)$/);
  assert.match(await text('.run-item[aria-pressed=true]'), /^Pinned · Run 1 · design A · /);
  // a name applied on leaving the field (change, no redraw) reaches the dock, the footer and the title too
  // the name is passed as an argument to a fixed function, so no page code is built from it
  const renameOnBlur = name => page.onElement("function(name){const e=this.getElementById('run-name-input');e.value=name;e.dispatchEvent(new Event('change'));return true}", name);
  await renameOnBlur('design A2'); await sleep(200);
  const blurNamed = await page.eval("({heading:document.querySelector('.dock-title>span').textContent,status:document.getElementById('status').textContent,header:document.getElementById('autosave-status').textContent})");
  stage('renamed on blur', blurNamed);
  for (const t of Object.values(blurNamed)) assert.match(t, /Run 1 · design A2\b/);
  await renameOnBlur('design A'); await sleep(200); assert.match(await page.eval("document.querySelector('.dock-title>span').textContent"), /^Run 1 · design A 600 × 300 nm · current inputs 700 × 300 nm$/);
  // round 9 (J1): the dock note on Results says Compare matches modes by field overlap
  assert.match(await text('#sequence'), /Compare matches modes by field overlap/); assert.doesNotMatch(await text('#sequence'), /not matched between runs/);
  // round 9 (J4): the Inputs label of Selected run is one line at 1440 × 900 and 390 × 844
  const labelLines = () => page.eval("(()=>{const s=[...document.querySelectorAll('#inspector .pair>span')].find(e=>e.textContent==='Inputs');const r=document.createRange();r.selectNodeContents(s);return new Set([...r.getClientRects()].map(x=>Math.round(x.top))).size})()");
  for (const [width, height, mobile] of [[1440, 900, false], [390, 844, true]]) {
    await page.call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile}); await sleep(300);
    const lines = await labelLines(); stage('Inputs label lines', {width, lines}); assert.equal(lines, 1, `the Inputs label wraps at ${width} px`);
  }
  await noOverflow('older run viewed');
  // round 10 (K3): a run chosen on Results is not a change: the recovered title still names the file
  assert.ok(viewed.header.startsWith(`Recovered from this browser · same as file ${sessionFile}`), viewed.header);
  // round 10 (K6): restoring opens the page shown when the record was written (Results, Run 1), not Compare or the newest run
  // the stored record names the page shown and the run selected (read back from browser storage)
  await page.until("import('/workspace-assets/workspace-notebook-recovery.mjs').then(async m=>{const r=await m.indexedNotebookStore().load();const d=JSON.parse(r.session);return r.page==='Results'&&d.selected===d.runs[0].job;})", 'recovery of the Results page', 20000);
  await page.call('Page.reload'); await page.until("!!document.querySelector('#resume-optical')", 'resume offer after Results');
  await page.click('#resume-optical'); await page.until("!!document.getElementById('optical-field')", 'restored on Results');
  const restored = await page.eval("({page:[...document.querySelectorAll('nav [data-page]')].filter(b=>b.getAttribute('aria-selected')==='true').map(b=>b.dataset.page),heading:document.querySelector('.dock-title>span').textContent,pressed:[...document.querySelectorAll('.run-item[aria-pressed=true]')].map(b=>b.textContent),header:document.getElementById('autosave-status').textContent})");
  stage('K6 restored on Results', restored);
  assert.deepEqual(restored.page, ['Results']); assert.match(restored.heading, /^Run 1 · design A 600 × 300 nm · current inputs 700 × 300 nm$/); assert.equal(restored.pressed.length, 1); assert.match(restored.pressed[0], /^Pinned · Run 1 · design A/);
  assert.ok(restored.header.startsWith(`Recovered from this browser · same as file ${sessionFile}`), restored.header);
  // round 10 (K3): a change of the model or a run ends "same as file". Since round 14 (Q3) the
  // file the record matched is the current file, so an input edit and a run renamed both read
  // "<file> · changed since restored"; the same content again names the file again
  const header = () => page.eval("document.getElementById('autosave-status').textContent");
  await toGeometry(); await page.type('#shape-w', 750);
  const editedHeader = await header(); stage('K3 after an input edit', {editedHeader}); assert.equal(editedHeader, `${sessionFile} · changed since restored`);
  await page.type('#shape-w', 700); assert.ok((await header()).startsWith(`Recovered from this browser · same as file ${sessionFile}`), await header());
  await page.click('nav [data-page=Results]'); await page.until("!!document.querySelector('.run-item')", 'run list again');
  await renameOnBlur('design A3'); await sleep(300);
  const renamedHeader = await header(); stage('K3 after a run renamed', {renamedHeader});
  assert.ok(renamedHeader.startsWith(`${sessionFile} · changed since restored · `), renamedHeader);
  await renameOnBlur('design A'); await sleep(300); assert.ok((await header()).startsWith(`Recovered from this browser · same as file ${sessionFile}`), await header());
  // the newer run viewed: every place says it is the result of the current inputs
  await page.onElement('function(selector){[...this.querySelectorAll(selector)].find(b=>/^Run 2 · closed · 700 × 300 nm/.test(b.textContent)).click();return true}', '.run-item');
  await page.until("/^Result for the current inputs/.test(document.querySelector('#canvas p')?.textContent||'')", 'newer run shown');
  assert.equal(await page.eval("[...document.querySelectorAll('#workflow .workflow-step')][4]?.innerText.replace(/\\s+/g,' ')"), '5. Results Result for these inputs');
  // switching to the heated model says where the optical runs stay, and they come back
  await page.click('nav [data-page=Applications]'); await page.until("!!document.querySelector('[data-template=heated-waveguide]')", 'models page');
  await page.click('[data-template=heated-waveguide]');
  await page.until("/^Heated silicon waveguide ready\\./.test(document.getElementById('file-status').textContent)", 'heated model', 30000);
  const switched = await text('#file-status'); stage('switched to the heated model', {message: switched, header: await page.eval("document.getElementById('autosave-status').textContent")});
  // round 9 (J7): one short line, the rest behind More
  const switchedParts = await page.eval("({line:[...document.getElementById('file-status').childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join('').trim(),summary:document.querySelector('#file-status details.message-more>summary')?.textContent,more:document.querySelector('#file-status .message-more-text')?.textContent})");
  stage('switch message parts', switchedParts);
  assert.equal(switchedParts.line, 'Heated silicon waveguide ready. Edit settings and couplings, then press Run. Optical waveguide runs stay in this tab · Library › Optical waveguide returns to them');
  assert.equal(switchedParts.summary, 'More');
  assert.match(switchedParts.more, /^This tab holds 2 runs until it is closed or reloaded\. After that, Library › Optical waveguide › Restore from this browser \(browser recovery, which keeps the four newest sessions\)(?: or Open session with \S+\.json)? brings them back\.$/);
  await noOverflow('heated model after optical runs');
  await page.click('nav [data-page=Applications]'); await page.until("!!document.querySelector('[data-template=optical]')", 'models page again');
  // round 16 (S9): the optical model returns to the page it was left on, Results with Run 2
  await page.click('[data-template=optical]'); await page.until("document.querySelector('nav [data-page][aria-selected=true]')?.dataset.page==='Results'&&!!document.getElementById('modes-table')", 'optical model again, on its Results');
  assert.ok((await page.eval("document.querySelector('.run-item[aria-pressed=true]')?.textContent??''")).includes('Run 2 · '), 'the run last viewed');
  await page.click('nav [data-page=Model]'); await page.until("!!document.querySelector('#shape-w')", 'optical model again');
  assert.equal((await opticalSequence()).heading, 'Run 2 · recovered from this browser, not recomputed', 'the optical runs came back');
  // V17-M2: Compare matches the modes of two runs by field overlap, 500 → 450 nm (both modes
  // matched with overlap >= 0.95, as V15 (a) on the engine); the picker lists matched pairs and
  // the old rank note is gone; the Results sentence names the matching
  // round 14 (Q6; pre-registered): the run banner takes no layout space and covers no control. At
  // 1440 × 900 (the 500 nm run) and 390 × 844 (the 450 nm run): the tree, the settings pane and the
  // workspace keep their boxes exactly before the banner, while it shows (running, then "Optical
  // run complete…") and after it leaves (an input edit, then the width back) (on a phone the
  // workspace's height follows the page shown, Results after the run, so there its place is
  // compared); hiding the banner while it shows changes no box at all; while it shows, every
  // tab, ribbon button, the File menu button and the tree's first item is the element at its
  // centre, no visible control outside the banner intersects it, and its own buttons are clickable
  const layoutBoxes = () => page.eval("JSON.stringify(['#tree','.settings-pane','.workspace'].map(s=>{const r=document.querySelector(s).getBoundingClientRect();return [r.left,r.top+scrollY,r.width,r.height]}))");
  // the boxes with the banner as it is and with it hidden by the check: the banner's own effect
  const withoutBanner = () => page.eval("(()=>{const b=document.getElementById('job-panel'),boxes=()=>JSON.stringify(['#tree','.settings-pane','.workspace'].map(s=>{const r=document.querySelector(s).getBoundingClientRect();return [r.left,r.top+scrollY,r.width,r.height]}));const shown=boxes();b.hidden=true;const hidden=boxes();b.hidden=false;return {shown,hidden}})()");
  // the tree, the settings pane, and the workspace's place (its height follows the page shown on a phone)
  const place = boxes => JSON.parse(boxes).map((r, i) => i < 2 ? r : r.slice(0, 3));
  const bannerCover = () => page.eval(`(()=>{const banner=document.getElementById('job-panel'),b=banner.getBoundingClientRect();
    const clip=e=>{let r=e.getBoundingClientRect(),box={l:r.left,t:r.top,r:r.right,b:r.bottom};for(let a=e.parentElement;a;a=a.parentElement){const c=getComputedStyle(a);if(c.overflowX!=='visible'||c.overflowY!=='visible'){const q=a.getBoundingClientRect();box={l:Math.max(box.l,q.left),t:Math.max(box.t,q.top),r:Math.min(box.r,q.right),b:Math.min(box.b,q.bottom)};}}
      box={l:Math.max(box.l,0),t:Math.max(box.t,0),r:Math.min(box.r,innerWidth),b:Math.min(box.b,innerHeight)};return box.r-box.l>1&&box.b-box.t>1?box:null;};
    const shown=e=>!e.closest('[hidden]')&&getComputedStyle(e).visibility!=='hidden'&&e.getClientRects().length>0&&!!clip(e);
    const name=e=>e.id||e.dataset.page||e.dataset.node||e.textContent.trim().slice(0,40);
    const hit=e=>{const c=clip(e),t=document.elementFromPoint((c.l+c.r)/2,(c.t+c.b)/2);return !!t&&(t===e||e.contains(t));};
    const named=[...document.querySelectorAll('nav [data-page]'),...document.querySelectorAll('.ribbon-commands>button'),document.getElementById('file-menu-button'),document.querySelector('#tree [role=treeitem]')].filter(e=>e&&shown(e));
    const controls=[...document.querySelectorAll('button,select,input,a[href],summary,[role=treeitem],[role=tab],[tabindex]:not([tabindex="-1"])')].filter(e=>!banner.contains(e)&&shown(e));
    const under=controls.filter(e=>{const c=clip(e);return c.l<b.right&&c.r>b.left&&c.t<b.bottom&&c.b>b.top;}).map(name);
    const own=[...banner.querySelectorAll('button')].filter(shown);
    // round 15 (R2): the panel headings (the view title row, the pane titles, the headings and captions of the view and the settings)
    const headings=[document.getElementById('view-title'),document.getElementById('view-detail'),...document.querySelectorAll('.pane-title,#canvas h2,#canvas h3,#canvas caption,#inspector h2,#inspector h3')].filter(e=>e&&shown(e));
    const overlaps=e=>{const c=clip(e);return c.l<b.right&&c.r>b.left&&c.t<b.bottom&&c.b>b.top;};
    const title=document.getElementById('view-title'),detail=document.getElementById('view-detail'),d=detail.getBoundingClientRect();
    return {banner:!banner.hidden&&b.width>0,inView:b.left>=0&&b.right<=innerWidth&&b.top>=0,message:document.getElementById('job-message').textContent,named:named.length,covered:named.filter(e=>!hit(e)).map(name),under,own:own.map(name),ownBlocked:own.filter(e=>!hit(e)).map(name),
      headings:headings.map(name),headingsUnder:headings.filter(overlaps).map(name),headingsBlocked:headings.filter(e=>!hit(e)).map(name),title:{text:title.textContent,shown:shown(title),hit:shown(title)&&hit(title)},detail:{text:detail.textContent,width:d.width,scrollWidth:detail.scrollWidth},bannerBox:[b.left,b.top,b.width,b.height],viewport:[innerWidth,innerHeight]}})()`);
  // the document-tab row, the view title and the view below it, with the banner as it is and hidden by the check
  const rowOwn = () => page.eval("(()=>{const b=document.getElementById('job-panel'),boxes=()=>JSON.stringify(['.document-tab','#view-title','#canvas'].map(s=>{const r=document.querySelector(s).getBoundingClientRect();return [r.left,r.top+scrollY,r.width,r.height]}));const shown=boxes();b.hidden=true;const hidden=boxes();b.hidden=false;return {shown,hidden}})()");
  // when the banner shows and leaves, and when a pointer was last pressed (performance.now() in the page)
  const watchBanner = () => page.eval("(()=>{window.__r2=[];window.__r2press=null;if(!window.__r2watch){window.__r2watch=true;const p=document.getElementById('job-panel'),m=document.getElementById('job-message'),log=()=>window.__r2.push({t:performance.now(),hidden:p.hidden,text:m.textContent});new MutationObserver(log).observe(p,{attributes:true,attributeFilter:['hidden']});new MutationObserver(log).observe(m,{childList:true,characterData:true,subtree:true});document.addEventListener('pointerdown',()=>{window.__r2press=performance.now();},true);}return true})()");
  const bannerTimes = () => page.eval("(()=>{const log=window.__r2,done=log.find(e=>e.text.startsWith('Optical run complete')),gone=done?log.find(e=>e.t>=done.t&&e.hidden):null;return {done:done?.t??null,gone:gone?.t??null,press:window.__r2press,shownUntilGone:!!done&&!log.some(e=>e.t>=done.t&&e.hidden&&e!==gone&&e.t<(gone?.t??Infinity))}})()");
  const checkCover = (seen, tag) => {
    assert.ok(seen.banner && seen.inView, tag + ': the banner shows inside the page');
    assert.ok(seen.named >= 10, tag + ': the tabs, ribbon buttons, File and the tree are checked');
    assert.deepEqual([seen.covered, seen.under, seen.ownBlocked], [[], [], []], tag + ': the banner covers no control and its own buttons are clickable');
  };
  // round 15 (R2): with the banner scrolled into the middle of the view, it covers no control and no
  // panel heading, and the view title is visible and on top
  const checkHeadings = (seen, tag) => {
    assert.ok(seen.banner && seen.inView, tag + ': the banner shows inside the page');
    assert.deepEqual([seen.covered, seen.under, seen.ownBlocked], [[], [], []], tag + ': the banner covers no control and its own buttons are clickable');
    assert.ok(seen.bannerBox[1] >= 0 && seen.bannerBox[1] + seen.bannerBox[3] <= seen.viewport[1], tag + ': the banner is in the viewport');
    assert.ok(seen.headings.length >= 3 && seen.headings.includes('view-title'), tag + ': the headings are checked: ' + seen.headings);
    assert.deepEqual([seen.headingsUnder, seen.headingsBlocked], [[], []], tag + ': the banner covers no panel heading');
    assert.deepEqual(seen.title, {text: seen.title.text, shown: true, hit: true}, tag + ': the view title is visible');
  };
  const centredCover = async () => { await page.eval("document.getElementById('job-panel').scrollIntoView({block:'center'})"); const seen = await bannerCover(); await page.eval('scrollTo(0,0)'); return seen; };
  for (const [width, w, h, mobile] of [[500, 1440, 900, false], [450, 390, 844, true]]) {
    await page.call('Emulation.setDeviceMetricsOverride', {width: w, height: h, deviceScaleFactor: 1, mobile}); await sleep(300);
    await toGeometry(); await page.type('#shape-w', width); await sleep(300);
    const before = await layoutBoxes(); await watchBanner();
    await page.until("!document.getElementById('run-optical').disabled", 'Q6 Run enabled'); await page.click('#run-optical'); if (await page.eval("!!document.getElementById('run-drop-confirm')?.open")) await page.click('#run-drop-confirm-run');
    await page.until("!document.getElementById('job-panel').hidden", 'Q6 banner shown');
    await page.eval('scrollTo(0,0)');
    const running = await layoutBoxes(), runningCover = await bannerCover(), runningOwn = await withoutBanner(), runningRow = await rowOwn(), runningHeadings = await centredCover();
    await page.until("/complete/i.test(document.getElementById('job-message').textContent)&&document.getElementById('run-optical').textContent==='Run study'", 'Q6 optical run', 120000);
    await sleep(200); await page.eval('scrollTo(0,0)'); const done = await layoutBoxes(), doneCover = await bannerCover(), doneOwn = await withoutBanner(), doneRow = await rowOwn(), doneHeadings = await centredCover();
    // round 15 (R2): with no input the complete banner leaves 6 s after it appears (wide); a pointer
    // press leaves it at once (phone): a real mouse press on the Results tab, where the page already is
    let leaves;
    if (!mobile) { await page.until("document.getElementById('job-panel').hidden", 'R2 banner leaves by itself', 10000); leaves = await bannerTimes(); }
    else {
      const at = await page.eval("(()=>{const r=document.querySelector('nav [data-page=Results]').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()");
      for (const type of ['mousePressed', 'mouseReleased']) await page.call('Input.dispatchMouseEvent', {type, x: at.x, y: at.y, button: 'left', clickCount: 1});
      await page.until("document.getElementById('job-panel').hidden", 'R2 banner leaves at a pointer press', 2000); leaves = await bannerTimes();
    }
    const gone = await layoutBoxes();
    await toGeometry(); await page.type('#shape-w', width + 2); await page.until("document.getElementById('job-panel').hidden", 'Q6 banner gone after an edit');
    const after = await layoutBoxes(); await page.type('#shape-w', width); await sleep(200);
    await page.click('nav [data-page=Results]'); await page.until("!!document.getElementById('optical-field')", 'Q6 back on Results');
    stage('Q6 banner ' + w, {before, running, done, after, gone, runningCover, doneCover, runningOwn, doneOwn, runningRow, doneRow, runningHeadings, doneHeadings, leaves});
    assert.deepEqual([runningRow.hidden, doneRow.hidden], [runningRow.shown, doneRow.shown], `R2 at ${w} × ${h}: the title row, the view title and the view keep their boxes with the banner`);
    assert.ok(leaves.done !== null && leaves.gone !== null && leaves.shownUntilGone, `R2 at ${w}: the complete banner was seen and left: ${JSON.stringify(leaves)}`);
    if (!mobile) assert.ok(leaves.gone - leaves.done >= 5900 && leaves.gone - leaves.done <= 6600, `R2 at ${w}: the banner leaves 6 s after it appears, by itself: ${leaves.gone - leaves.done} ms`);
    else assert.ok(leaves.press !== null && leaves.press > leaves.done && leaves.gone - leaves.press <= 300 && leaves.gone - leaves.done < 5900, `R2 at ${w}: a pointer press removes the banner at once: ${JSON.stringify(leaves)}`);
    assert.deepEqual(place(gone), place(before), `R2 at ${w} × ${h}: no layout shift when the banner leaves`);
    assert.deepEqual([running, done, after].map(place), [before, before, before].map(place), `Q6 at ${w} × ${h}: no layout shift`);
    if (!mobile) assert.deepEqual([running, done, after], [before, before, before], `Q6 at ${w} × ${h}: the same boxes`);
    assert.deepEqual([runningOwn.hidden, doneOwn.hidden], [runningOwn.shown, doneOwn.shown], `Q6 at ${w} × ${h}: the banner itself moves and resizes nothing`);
    checkCover(runningCover, `Q6 ${w} running`); checkCover(doneCover, `Q6 ${w} complete`);
    checkHeadings(runningHeadings, `R2 ${w} running`); checkHeadings(doneHeadings, `R2 ${w} complete`);
    assert.match(doneCover.message, /^Optical run complete\./);
    assert.ok(await page.eval('document.documentElement.scrollWidth-document.documentElement.clientWidth') <= 0, `Q6 at ${w}: no horizontal overflow`);
  }
  await page.call('Emulation.setDeviceMetricsOverride', {width: 1280, height: 800, deviceScaleFactor: 1, mobile: false}); await sleep(300);
  const resultsNote = await text('#canvas'); assert.match(resultsNote, /Modes are ranked by effective index\. Compare matches them between runs by field overlap\./);
  await page.click('nav [data-page=Compare]'); await page.until("!!document.getElementById('compare-neff')", 'Compare 500 → 450 nm');
  const matched = await compareTableRows(); stage('V17-M2 Compare 500 → 450 nm', matched);
  assert.deepEqual(matched.head.slice(4, 6), ['n_eff A', 'n_eff B']); assert.match(matched.runs[0], /^A · Run 3 · closed · 500 × 300 nm/); assert.match(matched.runs[1], /^B · Run 4 · closed · 450 × 300 nm/);
  assert.deepEqual(matched.matched, ['0:0', '1:1']); assert.deepEqual(matched.rows.map(r => r[0]), ['A mode 1 ↔ B mode 1', 'A mode 2 ↔ B mode 2']); assert.deepEqual(matched.short, ['1 ↔ 1', '2 ↔ 2']);
  assert.ok(matched.overlap.length === 2 && matched.overlap.every(v => v >= 0.95), 'overlap >= 0.95: ' + matched.overlap);
  // the polarization cells use the modes table's words: a TM-like cell names its TM share first
  // round 15 (R5): a hybrid cell names both shares, "hybrid · 21.7 % TE / 78.3 % TM"
  const polarizationCell = /^(?:TE-like · \d+\.\d % TE|hybrid · \d+\.\d % TE \/ \d+\.\d % TM|TM-like · \d+\.\d % TM \(\d+\.\d % TE\))$/;
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
  // round 12 (N1; pre-registered): the Compare table fits at 1440 × 900 and 390 × 844: two header
  // rows (short labels, then A | B), the first column frozen while the others scroll inside the
  // table box (at 390; since round 13 nothing scrolls at 1440, see O2 above), every column reachable there, headers and row headers on one line, and the n_g
  // hint visible while neither run computed n_g
  const compareFit = () => page.eval(`(()=>{const t=document.getElementById('compare-neff'),box=t.closest('.compare-table-scroll'),rows=[...t.tBodies[0].rows];
    const linesOf=r=>new Set([...r.getClientRects()].map(x=>Math.round(x.top))).size,range=n=>{const r=document.createRange();r.selectNodeContents(n);return r};
    box.scrollIntoView({block:'start'});box.scrollLeft=0;const b0=box.getBoundingClientRect(),f0=rows[0].cells[0].getBoundingClientRect();
    box.scrollLeft=box.scrollWidth;const b1=box.getBoundingClientRect(),f1=rows[0].cells[0].getBoundingClientRect(),side=[...t.tHead.rows[1].cells],m=t.tHead.rows[0].cells[0].getBoundingClientRect(),hit=document.elementFromPoint(m.left+m.width/2,m.bottom-4);
    const out={top:[...t.tHead.rows[0].cells].map(c=>c.firstChild.textContent),sides:side.map(c=>c.textContent),sticky:[t.tHead.rows[0].cells[0],...rows.map(r=>r.cells[0])].map(c=>getComputedStyle(c).position).filter(p=>p!=='sticky'),unpinned:side.map(c=>getComputedStyle(c).position).filter(p=>p==='sticky').length,
      firstLeft:[f0.left-b0.left,f1.left-b1.left,m.left-b1.left],modesOnTop:hit===t.tHead.rows[0].cells[0]||t.tHead.rows[0].cells[0].contains(hit),lastRight:Math.max(side.at(-1).getBoundingClientRect().right,...rows.map(r=>r.cells[r.cells.length-1].getBoundingClientRect().right))-b1.right,scroll:[box.scrollWidth,box.clientWidth,box.scrollLeft],
      wrapped:[...[...t.tHead.rows[0].cells].map(c=>[c.firstChild.textContent,linesOf(range(c.firstChild))]),...[...side,...rows.map(r=>r.cells[0])].map(c=>[c.textContent,linesOf(range(c))])].filter(x=>x[1]!==1),
      hint:(()=>{const h=document.querySelector('#compare-table-runs [data-group-index-hint]');return h?{text:h.textContent,height:h.getBoundingClientRect().height}:null})()};
    box.scrollLeft=0;return out})()`);
  // round 13 (O2; pre-registered, with the coordinator's 24 px margin): at 1440 × 900 with the tree
  // panel open every column is visible without scrolling, with at least 24 px to spare (the box's
  // clientWidth minus the table's width: the box's scrollWidth is never below its clientWidth), no
  // header or cell text clipped or outside its cell, every cell inside the box, and no scroll cue;
  // at 390 × 844 the table scrolls inside the box, Modes frozen (N1 below), with the cue: the line
  // and the right-edge shadow, gone at the right end. The Polarization cells have two lines.
  const compareFits = () => page.eval(`(()=>{const t=document.getElementById('compare-neff'),box=t.closest('.compare-table-scroll'),frame=box.parentElement,b=box.getBoundingClientRect();
    box.scrollLeft=0;const tree=document.getElementById('tree'),cells=[...t.querySelectorAll('th,td')],hint=document.querySelector('[data-scroll-hint]');
    const texts=c=>{const w=document.createTreeWalker(c,NodeFilter.SHOW_TEXT),out=[];while(w.nextNode()){const n=w.currentNode;if(!n.textContent.trim()||n.parentElement.closest('.pol-sep'))continue;const r=document.createRange();r.selectNodeContents(n);out.push(...[...r.getClientRects()].filter(x=>x.width>0));}return out};
    const lines=c=>new Set(texts(c).map(x=>Math.round(x.top))).size;
    const out={slack:box.clientWidth-Math.ceil(t.getBoundingClientRect().width),scroll:[box.scrollWidth,box.clientWidth],tree:getComputedStyle(tree).display,comparing:tree.parentElement.classList.contains('comparing'),pane:Math.round(document.querySelector('main>.settings-pane')?.getBoundingClientRect().width||0),
      clipped:cells.filter(c=>c.scrollWidth>c.clientWidth).map(c=>c.textContent),
      textOutside:cells.filter(c=>{const r=c.getBoundingClientRect();return texts(c).some(x=>x.left<r.left-0.5||x.right>r.right+0.5)}).map(c=>c.textContent),
      cellOutside:cells.filter(c=>{const r=c.getBoundingClientRect();return r.left<b.left-0.5||r.right>b.right+0.5}).map(c=>c.textContent),
      hint:hint?{hidden:hint.hidden,height:hint.getBoundingClientRect().height,text:hint.textContent}:null,shadowStart:frame.classList.contains('more-right'),
      polLines:[...t.querySelectorAll('td.pol')].filter(c=>c.textContent.includes(' · ')).map(c=>lines(c)),polText:[...t.querySelectorAll('td.pol')].map(c=>c.textContent)};
    return out})()`);
  const shadowAt = async end => { await page.eval(`(()=>{const s=document.querySelector('.compare-table-scroll');s.scrollLeft=${end ? 's.scrollWidth' : '0'};s.dispatchEvent(new Event('scroll'));})()`); await sleep(300);
    return page.eval("(()=>{const f=document.querySelector('.compare-table-frame');return {more:f.classList.contains('more-right'),opacity:getComputedStyle(f,'::after').opacity}})()"); };
  const checkCompareFit = async tag => {
    const result = {};
    for (const [width, height, mobile] of [[1440, 900, false], [390, 844, true]]) {
      await page.call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile}); await sleep(400);
      const fit = await compareFits(); result[width] = fit;
      assert.deepEqual(fit.clipped, [], `${tag}: no clipped cell at ${width}`); assert.deepEqual(fit.textOutside, [], `${tag}: no text outside its cell at ${width}`);
      assert.ok(fit.polLines.every(n => n === 2), `${tag}: Polarization cells on two lines at ${width}: ${fit.polLines}`);
      if (width === 1440) {
        // Compare hides the model tree (main.comparing) and keeps the run list pane open: the box is
        // as wide as Compare ever makes it at 1440, with the pane at its width
        assert.equal(fit.comparing, true); assert.equal(fit.tree, 'none', `${tag}: Compare shows no model tree`); assert.ok(fit.pane > 0, `${tag}: the run list pane is open`);
        assert.ok(fit.scroll[0] <= fit.scroll[1], `${tag}: the table box scrolls at 1440: ${fit.scroll}`);
        assert.ok(fit.slack >= 24, `${tag}: ${fit.slack} px to spare at 1440 (24 px pre-registered)`);
        assert.deepEqual(fit.cellOutside, [], `${tag}: every cell inside the box at 1440`);
        assert.equal(fit.hint.hidden, true, `${tag}: no scroll cue at 1440`); assert.equal(fit.shadowStart, false);
      } else {
        assert.ok(fit.scroll[0] > fit.scroll[1], `${tag}: the table scrolls inside its box at 390`);
        assert.equal(fit.hint.hidden, false); assert.ok(fit.hint.height > 0); assert.equal(fit.hint.text, 'Scroll sideways for all 14 columns ›');
        const start = await shadowAt(false), end = await shadowAt(true); result[width].shadow = {start, end};
        assert.deepEqual([start.more, start.opacity], [true, '1'], `${tag}: the right-edge shadow while columns are hidden`);
        assert.deepEqual([end.more, end.opacity], [false, '0'], `${tag}: no shadow at the right end`);
        await shadowAt(false);
      }
    }
    stage('O2 Compare table fit ' + tag, {slack: result[1440].slack, pane: result[1440].pane, scroll1440: result[1440].scroll, scroll390: result[390].scroll, shadow: result[390].shadow, polText: result[1440].polText});
    return result;
  };
  await checkCompareFit('500 → 450 nm');
  for (const [width, height, mobile] of [[1440, 900, false], [390, 844, true]]) {
    await page.call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile}); await sleep(300);
    const fit = await compareFit(); stage('N1 Compare table fit', {width, ...fit});
    assert.deepEqual(fit.top, ['Modes', 'Polarization', 'Overlap', 'n_eff', 'Δn_eff (B − A)', 'Δ % (of A)', 'A_eff (µm²)', 'Absorption loss (dB/cm)', 'n_g']);
    assert.deepEqual(fit.sides, ['A', 'B', 'A', 'B', 'A', 'B', 'A', 'B', 'A', 'B']);
    assert.deepEqual(fit.sticky, [], `the first column is sticky at ${width}`); assert.equal(fit.unpinned, 0, 'the A | B headers scroll');
    assert.ok(fit.modesOnTop, `the Modes header is not covered when the box is scrolled at ${width}`);
    assert.ok(fit.firstLeft.every(x => Math.abs(x) <= 1), `the first column stays at the box's left edge at ${width}: ${fit.firstLeft}`);
    assert.ok(fit.lastRight <= 1, `the last column is reachable inside the box at ${width}: ${fit.lastRight}`);
    assert.deepEqual(fit.wrapped, [], `headers and row headers on one line at ${width}`);
    assert.deepEqual(fit.hint?.text, 'Off · turn on in Study or Optical modes'); assert.ok(fit.hint.height > 0 && fit.hint.height <= 32, `the n_g hint is visible, on at most two lines: ${fit.hint.height}px`);
    await page.screenshot('compare-table-' + width);
  }
  await page.call('Emulation.setDeviceMetricsOverride', {width: 1280, height: 800, deviceScaleFactor: 1, mobile: false}); await sleep(300);
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
    await page.until(`document.getElementById('run-joule').textContent==='Run study'&&(${expected})`, label, 120000);
    await sleep(300);
  };
  const toJoule = async node => { await page.click('nav [data-page=Model]'); await sleep(200); await page.clickTreeItem(node); await sleep(200); };
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

  // round 10 (K9): the Joule heating model builder is the same ARIA tree, every node found by role and name
  await page.click('nav [data-page=Model]'); await sleep(200);
  await checkTree('Joule heating', ['Component 1', 'Geometry', 'Materials', 'Physics', 'Electric currents', 'Heat transfer', 'Analysis', 'Mesh', 'Study']);
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
  await page.until("/Newton iteration did not converge/.test(document.body.innerText)&&document.getElementById('run-joule').textContent==='Run study'", 'Newton refusal shown', 120000);
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
  // on new pages are one session: the Library page offers them once, on the Optical waveguide card
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
  await freshPage('J2 page 4'); await page.until("!!document.getElementById('resume-optical')", 'J2 Library page');
  await sleep(500);
  const offers = await page.eval(`import('/workspace-assets/workspace-notebook-recovery.mjs').then(async m=>{const s=m.indexedNotebookStore();const latest=await s.load(),earlier=await s.loadEarlier();
    const record=i=>Number(i)<0?latest:earlier[Number(i)],card=document.getElementById('resume-optical');
    const top=[...document.querySelectorAll('.resume-card [data-resume-record]')].map(b=>({record:b.dataset.resumeRecord,text:b.textContent}));
    return {card:{record:card.dataset.resumeRecord,text:card.textContent},top,keys:[card.dataset.resumeRecord,...top.map(t=>t.record)].map(i=>{const d=JSON.parse(record(i).session);return JSON.stringify({model:d.input??d.document,runs:(d.runs||[]).map(r=>[r.job,r.label||'',r.pinned===true])});}),stored:earlier.length};})`);
  stage('J2 one entry per session', offers);
  // the record matched the file it was opened from, which has no save time here: the time is the browser copy's
  assert.ok(offers.card.text.startsWith('Restore from this browser · Optical waveguide · Run 1 · design A, Run 2 · browser copy ') && offers.card.text.endsWith(' · same as file ' + sessionFile), offers.card.text);
  // round 19 (Y1): the box leads with the newest stored session, which the card also resumes
  assert.equal(offers.top[0]?.record, offers.card.record, 'the box leads with the record the card resumes');
  // compared by the stored inputs and runs themselves, not by the sessionKey under test: the box's entries
  assert.equal(new Set(offers.keys.slice(1)).size, offers.keys.length - 1, 'every entry of the box is another session');
  assert.deepEqual(offers.top.map((t, i) => [i, t.text.includes('Optical waveguide · 2 runs · Run 1 · design A, Run 2')]).filter(([, has]) => has).map(([i]) => i), [0], JSON.stringify(offers.top));
  await noOverflow('J2 Library page');

  // M4 (number of modes; pre-registered, blind except the template's count of guided modes, which
  // the engine run before this check showed to be 3 of 8): Modes to find in Optical modes and in
  // Study (M4-d), fewer found than asked (M4-c), Compare of 8-mode runs (M4-f), a version 9
  // session saved and opened (V17), and a session over 16 MiB (M4-e).
  await page.eval("document.getElementById('notebook-recovery-detail').textContent=''");
  await page.click('[data-template=optical]');
  await answerDialogs("!!document.querySelector('#shape-w')", 'M4 optical model');
  const toNode = async node => { await page.click('nav [data-page=Model]'); await sleep(200); await page.clickTreeItem(node); await page.until("!!document.getElementById('mode-count-number')", node + ' Modes to find'); };
  const modeField = () => page.eval("(()=>{const e=document.getElementById('mode-count-number'),p=document.getElementById('input-problems');return {label:e.closest('label').firstChild.textContent,value:e.value,min:e.min,max:e.max,step:e.step,invalid:e.getAttribute('aria-invalid'),problems:p.hidden?'':p.innerText.replace(/\\s+/g,' ').trim(),run:document.getElementById('run-optical').disabled}})()");
  await toNode('Optical modes');
  const m4field = await modeField(); stage('M4-d Modes to find', m4field);
  assert.deepEqual([m4field.label, m4field.value, m4field.min, m4field.max, m4field.step, m4field.run], ['Modes to find', '2', '1', '8', '1', false]);
  const m4refused = {};
  for (const raw of ['0', '9', '2.5']) {
    await page.type('#mode-count-number', raw); const seen = m4refused[raw] = await modeField();
    assert.match(seen.problems, /Modes to find must be a whole number from 1 to 8\. Last valid value is retained\./, raw);
    assert.equal(seen.run, true, raw + ': Run is held'); assert.equal(seen.invalid, 'true', raw);
  }
  for (const raw of ['1', '8']) { await page.type('#mode-count-number', raw); const seen = m4refused[raw] = await modeField(); assert.equal(seen.problems, '', raw); assert.equal(seen.run, false, raw); }
  stage('M4-d refused and accepted', m4refused);
  await toNode('Study');
  const m4study = await page.eval("({value:document.getElementById('mode-count-number').value,text:document.getElementById('inspector').innerText})");
  assert.equal(m4study.value, '8'); assert.ok(m4study.text.includes('The window is fixed; the outer boundary is chosen in Physics › Optical modes.'), m4study.text); // round 17 U5 (pre-registered; was /Window and boundaries are fixed\./) assert.doesNotMatch(m4study.text, /mode count are fixed|candidate count/i);
  await noOverflow('M4 Study');
  // M4-c: the template (500 x 220 nm) asking for 8
  await runAndWait();
  await page.until("!!document.getElementById('modes-table')", 'M4 results');
  const m4found = await page.eval("({found:document.getElementById('modes-found')?.textContent??null,rows:document.querySelectorAll('#modes-table tbody tr').length,options:document.querySelectorAll('#field-mode option').length})");
  stage('M4-c fewer found than asked', m4found);
  const k = Number(m4found.found?.match(/^Found (\d) of 8 modes above n = 1\.45\.$/)?.[1]);
  assert.ok(k >= 1 && k < 8, m4found.found); assert.equal(m4found.rows, k); assert.equal(m4found.options, k);
  await noOverflow('M4 results 3 of 8');
  // M4-f: two 2000 x 400 nm cores asking for 8 (λ 1550 and 1560 nm), and the template run against one
  await toGeometry(); await page.type('#shape-w', 2000); await page.type('#shape-h', 400);
  await runAndWait();
  await toNode('Optical modes'); await page.type('#wavelength-number', 1560); await runAndWait();
  const wide = await page.eval("({found:document.getElementById('modes-found')?.textContent??null,rows:document.querySelectorAll('#modes-table tbody tr').length})");
  stage('M4-f wide core', wide); assert.equal(wide.found, null); assert.equal(wide.rows, 8);
  const pickerFits = () => page.eval(`(()=>{const s=document.getElementById('compare-mode'),c=document.createElement('canvas').getContext('2d');c.font=getComputedStyle(s).font;
    return {options:[...s.options].map(o=>o.textContent),width:s.clientWidth,need:Math.max(...[...s.options].map(o=>Math.ceil(c.measureText(o.textContent).width)+32))}})()`);
  const m4compare = {};
  for (const [name, a] of [['wide 1550 → 1560', null], ['template → wide 1560', 0]]) {
    await page.click('nav [data-page=Compare]'); await page.until("!!document.getElementById('compare-neff')", 'M4 Compare ' + name);
    if (a !== null) { const job = await page.eval(`document.getElementById('compare-a').options[${a}].value`); await page.choose('#compare-a', job); await page.until("!!document.getElementById('compare-neff')", 'M4 Compare A'); }
    const rows = await compareTableRows(), accepted = rows.matched.filter(Boolean);
    m4compare[name] = {rows: rows.rows.map(r => r[0]), picker: rows.picker};
    stage('M4-f Compare rows ' + name, m4compare[name]);
    // every matched pair is listed; with none, the picker says so (and is disabled)
    assert.deepEqual(rows.picker.length ? rows.picker.map(o => o.replace(/ · overlap .*$/, '')) : [], accepted.length ? rows.rows.filter((r, i) => rows.matched[i]).map(r => r[0]) : ['No matched modes'], name + ': the picker lists every matched pair');
    assert.ok(rows.rows.filter((r, i) => !rows.matched[i]).every(r => /: no match in [AB]/.test(r[0])), name);
    for (const [width, height, mobile] of [[1440, 900, false], [390, 844, true]]) {
      await page.call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile}); await sleep(300);
      const fit = await pickerFits(); m4compare[name]['fit ' + width] = {width: fit.width, need: fit.need};
      assert.ok(fit.need <= fit.width, `${name}: the widest matched pair needs ${fit.need} px, the picker has ${fit.width} px at ${width}`);
    }
    // round 13 (O2): the 8-mode tables fit at 1440 × 900 with the same margin
    m4compare[name].slack = (await checkCompareFit('M4 ' + name))[1440].slack;
    await page.call('Emulation.setDeviceMetricsOverride', {width: 1280, height: 800, deviceScaleFactor: 1, mobile: false}); await sleep(300);
    await noOverflow('M4 Compare ' + name);
  }
  stage('M4-f Compare', m4compare);
  assert.equal(m4compare['wide 1550 → 1560'].picker.length, 8, 'eight modes of the wide core matched');
  assert.ok(m4compare['template → wide 1560'].rows.some(r => /^B mode \d: no match in A/.test(r)), 'a wide mode without a template partner reads no match');
  await page.screenshot('m4-compare');
  // V17: the session of these runs is version 9; opened again it reads the same runs
  // the downloads as {name: modification time}: a save in the same minute may reuse a file name
  const listDownloads = async () => Object.fromEntries(await Promise.all((await readdir(downloads)).filter(n => n.endsWith('.json')).map(async n => [n, (await stat(join(downloads, n))).mtimeMs])));
  const newDownload = async before => { for (let i = 0; i < 300; i++) { const now = await listDownloads(), f = Object.keys(now).find(n => before[n] !== now[n]); if (f) { await sleep(500); return f; } await sleep(100); } throw new Error('no new download: ' + await text('#file-status')); };
  // (P3: the session file is File › Export › Model with runs; File › Save writes the project file)
  let listed = await listDownloads(); await page.click('#menu-export-session'); await confirmName('V17 save');
  const v9File = await newDownload(listed), v9Text = await readFile(join(downloads, v9File), 'utf8'), v9 = JSON.parse(v9Text);
  stage('V17 version 9 saved', {file: v9File, bytes: Buffer.byteLength(v9Text), version: v9.version, counts: v9.runs.map(r => [r.settings.mode_count, Array.isArray(r.effective_index) ? r.effective_index.length : r.effective_index.re.length])});
  assert.equal(v9.version, 9); assert.equal(v9.application, 'optical');
  assert.ok(v9.runs.every(r => /^sha256:[0-9a-f]{64}$/.test(r.digest) && r.settings.adapter === 'optical-shapes-v8' && Array.isArray(r.te_polarization_fraction) && Array.isArray(r.effective_area)));
  await page.eval("document.getElementById('notebook-recovery-detail').textContent=''");
  await setFile('#session-file', join(downloads, v9File));
  await answerDialogs(`/^Opened /.test(document.getElementById('autosave-status').textContent)`, 'V17 open version 9');
  await page.click('nav [data-page=Results]'); await page.until("!!document.getElementById('modes-table')", 'V17 results');
  const reopened = await page.eval("({rows:document.querySelectorAll('#modes-table tbody tr').length,details:document.getElementById('run-details').textContent})");
  stage('V17 version 9 opened', reopened); assert.equal(reopened.rows, 8); assert.match(reopened.details, /computed by the engine from the saved field/);
  await toNode('Optical modes'); assert.equal(await page.eval("document.getElementById('mode-count-number').value"), '8', 'Modes to find follows the selected run');
  // review: Use this run's inputs restores its Modes to find; the inputs words name the count
  await page.type('#mode-count-number', 2); await page.click('nav [data-page=Results]'); await page.until("!!document.getElementById('restore-run-input')", 'Restore button');
  assert.match(await text('#canvas'), /Modes to find 8/, 'the inputs line names the run\'s count');
  // round 11 (L3): no question, since the runs stay; the page stays on Results
  await page.click('#restore-run-input'); await page.until("/Same as the current inputs/.test(document.getElementById('inspector').textContent)", 'restore run inputs');
  assert.equal(await page.eval("!!document.querySelector('dialog[open]')"), false);
  await page.click('nav [data-page=Results]'); await page.until("/Same as the current inputs/.test(document.getElementById('inspector').textContent)", 'restored run is current');
  await toNode('Optical modes'); assert.equal(await page.eval("document.getElementById('mode-count-number').value"), '8', 'Restore sets Modes to find');
  // M4-e: five more wide runs (6 kept: the newest unpinned replace the oldest) are over 16 MiB
  for (const wl of [1570, 1580, 1590, 1600]) { await toNode('Optical modes'); await page.type('#wavelength-number', wl); await runAndWait(); }
  await page.click('#menu-export-session'); await page.until("document.getElementById('session-overflow').open", 'M4-e overflow question');
  const question = await page.eval("({text:document.getElementById('session-overflow-description').textContent,buttons:[...document.querySelectorAll('#session-overflow button')].map(b=>b.textContent)})");
  stage('M4-e overflow question', question);
  assert.match(question.text, /^Session is \d\d MB; the limit is 16 MiB\. Keep the fields of the selected and pinned runs only\? The other runs keep n_eff, the TE fractions and the effective areas, but not their fields\.$/);
  assert.deepEqual(question.buttons, ['Cancel', 'Keep fields for selected and pinned runs']);
  listed = await listDownloads(); await page.click('#overflow-cancel'); await sleep(500);
  assert.match(await text('#file-status'), /^Session not saved: nothing was written\./); assert.deepEqual(await listDownloads(), listed, 'Cancel writes nothing');
  // P3 (V-P6): File › Save of the project asks the same question, naming the model
  await page.click('#save-session'); await page.until("document.getElementById('session-overflow').open", 'M4-e project overflow question');
  assert.equal(await page.eval("document.getElementById('session-overflow-description').textContent"), 'Optical waveguide: ' + question.text);
  await page.click('#overflow-cancel'); await sleep(300); assert.equal(await text('#file-status'), 'Project not saved: nothing was written.'); assert.deepEqual(await listDownloads(), listed, 'Cancel writes nothing');
  await page.click('#menu-export-session'); await page.until("document.getElementById('session-overflow').open", 'M4-e overflow question again');
  // round 13 (O1): the file opened above is the current file, which the name dialog offers
  await page.click('#overflow-keep'); await page.until("document.getElementById('save-name-dialog')?.open", 'M4-e name dialog');
  assert.equal(await page.eval("document.getElementById('save-name-input').value"), v9File); await page.click('#save-name-download');
  const reducedFile = await newDownload(listed), reduced = JSON.parse(await readFile(join(downloads, reducedFile), 'utf8'));
  { const stem = v9File.replace(/\.json$/, ''); // the opened name, or the browser's "name (1).json" (compared as text, no regex built from it)
    assert.ok(reducedFile === v9File || (reducedFile.startsWith(stem + ' (') && /^ \(\d+\)\.json$/.test(reducedFile.slice(stem.length))), 'the reduced session keeps the opened file name: ' + reducedFile); }
  const keptFields = reduced.runs.map(r => [r.job === reduced.selected, r.pinned, 'field' in r]);
  stage('M4-e reduced session', {file: reducedFile, bytes: (await readFile(join(downloads, reducedFile))).length, keptFields, message: await text('#file-status')});
  assert.equal(reduced.version, 9); assert.ok(keptFields.every(([selected, pinned, field]) => field === (selected || pinned)), JSON.stringify(keptFields));
  assert.ok(keptFields.some(([, , field]) => !field), 'some runs were written without fields');
  assert.match(await text('#file-status'), /Fields not kept for Run \d/);
  // the reduced file opened: a run without fields shows its modes, no field view, and Compare says why
  await setFile('#session-file', join(downloads, reducedFile));
  await answerDialogs(`/^Opened /.test(document.getElementById('autosave-status').textContent)`, 'M4-e open reduced');
  const bare = reduced.runs.findIndex(r => !('field' in r));
  await page.click('nav [data-page=Results]'); await page.until("document.querySelectorAll('.run-item').length===6", 'M4-e run list');
  await page.click(`.run-item[data-run="${reduced.runs[bare].job}"]`); await page.until("!!document.getElementById('fields-not-kept')", 'M4-e field-less run');
  const bareView = await page.eval("({rows:document.querySelectorAll('#modes-table tbody tr').length,field:!!document.getElementById('optical-field'),details:document.getElementById('run-details').textContent})");
  stage('M4-e field-less run', bareView); assert.equal(bareView.rows, 8); assert.equal(bareView.field, false); assert.match(bareView.details, /saved in the session file; its fields were not kept/);
  await page.click('nav [data-page=Compare]'); await page.until("!!document.querySelector('.compare-no-fields')||!!document.getElementById('compare-neff')", 'M4-e Compare');
  await page.choose('#compare-b', reduced.runs[bare].job); await page.until("!!document.querySelector('.compare-no-fields')", 'M4-e Compare without fields');
  assert.match(await text('.compare-no-fields'), /^Run \d has no saved fields, so its modes cannot be matched by overlap\.$/);
  await noOverflow('M4-e Compare without fields');

  // M5-s (group index; pre-registered): Also compute group index in Study, off by default; a run
  // with it off shows "—" with the help, a run with it on shows the engine's n_g (a real 3-solve job,
  // checked against a direct engine run of the same document to 4 decimals); Compare n_g A and B;
  // no horizontal overflow at 390 × 844.
  await page.click('nav [data-page=Applications]'); await page.until("!!document.querySelector('[data-template=optical]')", 'M5 models page');
  await page.click('[data-template=optical]');
  await answerDialogs("!!document.querySelector('#shape-w')", 'M5 optical model');
  await toNode('Study');
  const m5box = () => page.eval("(()=>{const e=document.getElementById('group-index-check');return e?{label:e.closest('label').textContent.trim(),checked:e.checked}:null})()");
  const m5off = await m5box(); stage('M5 Study checkbox', m5off);
  assert.deepEqual(m5off, {label: 'Also compute group index (3 solves)', checked: false});
  // round 12 (N2–N4; pre-registered): the box's plain note; the same box in Physics › Optical modes,
  // synced with Study both ways and through Undo; a message each way; the next run naming the option
  const GROUP_NOTE = 'Also solves at λ ± 1 nm and takes n_g from the change (about 3× slower). Off: one solve, no n_g. n_g includes the dispersion of the materials (evaluated at λ ± 1 nm).';
  const groupOn = 'Group index on: the next run also solves at λ ± 1 nm and gives n_g (about 3× slower).', groupOff = 'Group index off: the next run is one solve, without n_g.';
  const m5note = () => page.eval("document.getElementById('group-index-check').closest('label').nextElementSibling.textContent");
  const message = () => page.eval("document.getElementById('file-status').textContent");
  assert.equal(await m5note(), GROUP_NOTE);
  await toNode('Optical modes'); assert.deepEqual(await m5box(), m5off, 'the box in Optical modes'); assert.equal(await m5note(), GROUP_NOTE);
  // round 15 (R4): the materials come from physmat and are evaluated at each wavelength solved
  {const pairs = await page.eval("[...document.querySelectorAll('#inspector .pair')].map(e=>e.textContent)"); stage('R4 Optical modes material data', {pairs});
   assert.ok(pairs.includes('Material dataphysmat materials, evaluated at each wavelength solved'), JSON.stringify(pairs));}
  await page.click('#group-index-check'); await sleep(200); assert.equal(await message(), groupOn);
  await toNode('Study'); assert.equal((await m5box()).checked, true, 'Study shows the box ticked in Optical modes');
  assert.match(await text('#next-run-inputs'), / · Modes to find 2 · group index on$/);
  await page.click('#group-index-check'); await sleep(200); assert.equal(await message(), groupOff);
  assert.doesNotMatch(await text('#next-run-inputs'), /group index/);
  await toNode('Optical modes'); assert.equal((await m5box()).checked, false, 'Optical modes shows the box cleared in Study');
  await page.click('#undo-edit'); await sleep(200); assert.equal((await m5box()).checked, true, 'Undo ticks it again in Optical modes');
  await page.click('#group-index-check'); await sleep(200); assert.equal((await m5box()).checked, false);
  await noOverflow('N3 Optical modes with the group index box');
  await toNode('Study'); assert.deepEqual(await m5box(), m5off);
  await runAndWait(); await page.until("!!document.getElementById('modes-table')", 'M5 results off');
  const ngCells = () => page.eval("({head:[...document.querySelectorAll('#modes-table thead th')].map(e=>e.firstChild.textContent),hint:(()=>{const h=document.querySelector('#modes-table-hint [data-group-index-hint]');return h?{text:h.textContent,height:h.getBoundingClientRect().height}:null})(),headText:[...document.querySelectorAll('#modes-table thead th')].map(e=>e.textContent),cells:[...document.querySelectorAll('#modes-table [data-group-index]')].map(e=>({text:e.textContent,title:e.title,value:e.dataset.groupIndexValue??null})),neff:[...document.querySelectorAll('#modes-table [data-neff]')].map(e=>e.textContent)})");
  const offView = await ngCells(); stage('M5 results off', offView);
  assert.equal(offView.head.at(-1), 'n_g'); assert.equal(offView.headText.at(-1), 'n_g', 'R3: the n_g header holds no hint');
  assert.equal(offView.hint?.text, 'Off · turn on in Study or Optical modes'); assert.ok(offView.hint.height > 0, 'the hint is visible');
  assert.ok(offView.cells.length >= 1 && offView.cells.every(c => c.text === '—' && c.title === 'Turn on Also compute group index in Study or Optical modes'), JSON.stringify(offView.cells));
  await toNode('Study'); await page.click('#group-index-check'); await page.until("document.getElementById('group-index-check')?.checked===true", 'M5 checkbox on');
  // the document the page submits, read from its /api/run request
  await page.eval("(()=>{const f=window.fetch;window.__m5Runs=[];window.fetch=(u,o)=>{if(String(u).includes('/api/run'))window.__m5Runs.push(o.body);return f(u,o);};})()");
  const t0 = Date.now(); await runAndWait(); const onSeconds = (Date.now() - t0) / 1000;
  await page.until("!!document.querySelector('#modes-table [data-group-index-value]')", 'M5 results on');
  const onView = await ngCells(); stage('M5 results on', {...onView, seconds: onSeconds}); assert.equal(onView.hint, null, 'no hint on a run with n_g');
  // the submitted document run directly by the engine
  const doc = JSON.stringify(JSON.parse(await page.eval('window.__m5Runs.at(-1)')).doc);
  const engine = spawnSync(args.python, ['-c', 'import json,sys\nfrom simcase import Document, run\nr=run(Document.from_dict(json.loads(sys.stdin.read())),False)\ns=r.summary()\nprint(json.dumps({"ng":s["group_index"]["values"][0],"neff":s["effective_index"]["values"][0],"method":s["group_index_method"]}))'], {input: doc, encoding: 'utf8'});
  assert.equal(engine.status, 0, engine.stderr);
  const direct = JSON.parse(engine.stdout); stage('M5 direct engine run', direct);
  assert.deepEqual(JSON.parse(doc).results, {save_fields: true, plots: false, group_index: {wavelength_step: '1 nm'}});
  assert.equal(onView.cells.length, direct.ng.length);
  onView.cells.forEach((c, i) => {
    assert.equal(c.text, direct.ng[i] === null ? '—' : direct.ng[i].toFixed(4), 'mode ' + (i + 1));
    assert.ok(direct.ng[i] === null || /central difference over λ0 ± 1 nm \(3 solves\)/.test(c.title), c.title);
  });
  assert.deepEqual(onView.neff, offView.neff, 'the option leaves n_eff as it was');
  assert.deepEqual(onView.neff, direct.neff.map(n => n.toFixed(8)), 'the engine run is of the same document');
  await noOverflow('M5 results with n_g');
  // Compare: the off run as A, the on run as B. Round 16 (S3): a pair picked on Compare earlier
  // stays when new runs come, so the two newest runs are picked here with the A and B selects
  await page.click('nav [data-page=Compare]'); await page.until("!!document.getElementById('compare-neff')", 'M5 Compare');
  for (const [id, back] of [['compare-a', 2], ['compare-b', 1]]) {
    await page.eval(`(()=>{const s=document.getElementById('${id}');s.value=s.options[s.options.length-${back}].value;s.dispatchEvent(new Event('change'));return true})()`);
    await page.until("!!document.getElementById('compare-neff')", 'M5 Compare ' + id);
  }
  const m5compare = await page.eval("({head:[...document.querySelectorAll('#compare-neff thead [data-column]')].map(e=>e.dataset.column),hint:!!document.querySelector('#compare-neff [data-group-index-hint]'),a:[...document.querySelectorAll('#compare-neff [data-group-index-a]')].map(e=>e.textContent),b:[...document.querySelectorAll('#compare-neff [data-group-index-b]')].map(e=>e.textContent)})");
  stage('M5 Compare', m5compare);
  assert.deepEqual(m5compare.head.slice(-2), ['n_g A', 'n_g B']); assert.equal(m5compare.hint, false, 'no hint when run B computed n_g');
  assert.ok(m5compare.a.length && m5compare.a.every(t => t === '—'), JSON.stringify(m5compare.a));
  assert.ok(m5compare.b.some(t => /^\d\.\d{4}$/.test(t)), JSON.stringify(m5compare.b));
  await noOverflow('M5 Compare with n_g');
  await page.screenshot('m5-compare');

  // P1 (study settings with the inputs; pre-registered): Undo and Redo cover Modes to find, the
  // group index box and Use this run's inputs; Save inputs only writes version 7 byte for byte with
  // 2 modes and the box off, version 8 otherwise, and Open inputs file sets both from the file.
  const study = () => page.eval("({modes:document.getElementById('mode-count-number').value,box:document.getElementById('group-index-check').checked})");
  const undo = async () => { await page.click('#undo-edit'); await sleep(200); }, redo = async () => { await page.click('#redo-edit'); await sleep(200); };
  await toNode('Study'); assert.deepEqual(await study(), {modes: '2', box: true}, 'P1 start: the M5 inputs');
  await page.type('#mode-count-number', 4); assert.deepEqual(await study(), {modes: '4', box: true});
  await undo(); const u1 = await study(); await redo(); const r1 = await study(); stage('P1 U1 Modes to find', {undo: u1, redo: r1});
  assert.deepEqual(u1, {modes: '2', box: true}); assert.deepEqual(r1, {modes: '4', box: true});
  await page.click('#group-index-check'); assert.deepEqual(await study(), {modes: '4', box: false});
  await undo(); const u2 = await study(); await redo(); const r2 = await study(); stage('P1 U2 group index box', {undo: u2, redo: r2});
  assert.deepEqual(u2, {modes: '4', box: true}); assert.deepEqual(r2, {modes: '4', box: false});
  const saveInputs = async () => { const before = await listDownloads(); await page.click('#save-project'); const name = await newDownload(before); assert.equal(name, 'optical-waveguide.json'); return readFile(join(downloads, name), 'utf8'); };
  const fourText = await saveInputs(), four = JSON.parse(fourText);
  await page.click('#group-index-check'); await page.type('#mode-count-number', 2); assert.deepEqual(await study(), {modes: '2', box: true});
  const boxText = await saveInputs(), box = JSON.parse(boxText);
  await page.click('#group-index-check'); const plainText = await saveInputs();
  // the same inputs as version 7 writes them (the key order of before: the settings keys are the
  // last of model); the node suite checks the template's file against the fixture of the writer before version 8
  const {modeCount: _m, ...fourModel} = four.model, version7Text = JSON.stringify({...four, version: 7, model: fourModel}, null, 2) + '\n';
  stage('P1 inputs files', {four: [four.version, four.model.modeCount, four.model.groupIndex ?? null], box: [box.version, box.model.modeCount ?? null, box.model.groupIndex], plain: [JSON.parse(plainText).version, Buffer.byteLength(plainText)]});
  assert.equal(plainText, version7Text, '2 modes and the box off: a version 7 file, byte for byte');
  assert.deepEqual([four.version, four.model.modeCount, 'groupIndex' in four.model], [8, 4, false]);
  assert.deepEqual([box.version, 'modeCount' in box.model, box.model.groupIndex], [8, false, true]);
  // each file opened again sets Modes to find and the box from it
  await writeFile(join(out, 'p1-four.json'), fourText); await writeFile(join(out, 'p1-box.json'), boxText);
  for (const [name, expected] of [['p1-four.json', {modes: '4', box: false}], ['p1-box.json', {modes: '2', box: true}], ['p1-four.json', {modes: '4', box: false}]]) {
    await setFile('#project-file', join(out, name));
    await answerDialogs(`/^Model inputs restored · ${name}/.test(document.getElementById('file-status').textContent)`, 'P1 open ' + name);
    await toNode('Study'); const opened = await study(); stage('P1 reopened ' + name, opened); assert.deepEqual(opened, expected);
  }
  // a session of these inputs holds them as an input of version 8
  // round 13 (O1): the model file opened last is the current file, which Export › Model with runs offers
  const p1Before = await listDownloads(); await page.click('#menu-export-session');
  await page.until("document.getElementById('save-name-dialog')?.open", 'P1 export name dialog');
  assert.equal(await page.eval("document.getElementById('save-name-input').value"), 'p1-four.json'); await page.click('#save-name-download');
  const p1Name = await newDownload(p1Before), p1Session = JSON.parse(await readFile(join(downloads, p1Name), 'utf8'));
  assert.match(p1Name, /^p1-four(?: \(\d\))?\.json$/); assert.equal(await page.eval("!!document.getElementById('save-name-dialog').open"), false);
  stage('P1 session input', {version: p1Session.version, input: p1Session.input.version, modeCount: p1Session.input.model.modeCount});
  assert.deepEqual([p1Session.version, p1Session.input.version, p1Session.input.model.modeCount], [9, 8, 4]);
  // U3: Use this run's inputs with a run of other Modes to find and box (the M5 run with the box off)
  await page.type('#mode-count-number', 5); await page.click('#group-index-check'); assert.deepEqual(await study(), {modes: '5', box: true});
  await page.click('nav [data-page=Results]'); await page.until("document.querySelectorAll('.run-item').length>=2", 'P1 run list');
  // any run but the newest (the M5 run with the box on): its box is off
  const offJob = await page.eval("(()=>{const items=[...document.querySelectorAll('.run-item')].map(e=>({job:e.dataset.run,n:Number(/Run (\\d+)/.exec(e.textContent)?.[1])}));const newest=Math.max(...items.map(i=>i.n));return items.find(i=>i.n!==newest).job;})()");
  await page.click(`.run-item[data-run="${offJob}"]`); await page.until("!!document.getElementById('restore-run-input')", 'P1 Use this run\'s inputs');
  await page.click('#restore-run-input'); await page.until("!document.getElementById('restore-run-input')", 'P1 inputs used');
  const usedMessage = await text('#file-status');
  await toNode('Study'); const used3 = await study(); await undo(); const u3 = await study(); await redo(); const r3 = await study();
  stage('P1 U3 Use this run\'s inputs', {message: usedMessage, used: used3, undo: u3, redo: r3});
  // the run's count, from the message (the M5 runs have the box off on one of them; the run list
  // order is not assumed): another count and box than the current 5 and on
  // round 13 (O5): the message lists Modes to find 5 → N and Group index on → off, from → to
  const runModes = /(?:: | · )Modes to find 5 → (\d)(?: · |\.)/.exec(usedMessage)?.[1]; assert.match(usedMessage, / · Group index on → off\. The next run uses them; Undo takes them back\.$/);
  assert.ok(runModes && runModes !== '5', usedMessage);
  assert.deepEqual(used3, {modes: runModes, box: false}); assert.deepEqual(u3, {modes: '5', box: true}); assert.deepEqual(r3, used3);
  await noOverflow('P1 study settings');

  {
    // P2 F: the File menu. F1 by keyboard and by role and name in the accessibility tree; F2 the name
    // dialog where the browser has no save picker (removed at document start); F3 Save As, Save,
    // a cancel and a failed write through window.showSaveFilePicker stubbed at the boundary (its
    // file changes only on close, as in Chromium); F4 a picker that refuses (NotAllowedError) falls
    // back to the name dialog. The real picker in desktop Chrome is not driven here.
    const MOD = {Control: 2, Shift: 8};
    const key = async (name, mods = [], code = name) => {
      const vk = {...KEYS, Escape: 27, s: 83, o: 79}[name], modifiers = mods.reduce((m, k) => m | MOD[k], 0);
      for (const type of ['rawKeyDown', 'keyUp']) await page.call('Input.dispatchKeyEvent', {type, key: name, code: code.length === 1 ? 'Key' + code.toUpperCase() : code, windowsVirtualKeyCode: vk, modifiers});
      await sleep(200);
    };
    const axNamed = async (role, name) => {
      const {result: document} = await page.call('Runtime.evaluate', {expression: 'document'});
      const {nodes} = await page.call('Accessibility.queryAXTree', {objectId: document.objectId, accessibleName: name, role});
      return nodes.filter(n => !n.ignored).length;
    };
    const status = () => text('#file-status');
    await page.click('nav [data-page=Model]'); await sleep(200);
    // round 17 (U10): the toolbar Open… button's name is its visible text, "Open…" (was "Open")
    for (const [role, name] of [['button', 'File'], ['button', 'Edit'], ['button', 'Open…'], ['button', 'Save']]) assert.equal(await axNamed(role, name), 1, `${role} ${name}`);
    await page.eval("document.getElementById('file-menu-button').focus()"); await press('Enter');
    const fileMenu = await page.eval("(()=>{const m=document.getElementById('file-menu');return {open:!m.hidden,expanded:document.getElementById('file-menu-button').getAttribute('aria-expanded'),role:m.getAttribute('role'),label:m.getAttribute('aria-label'),items:[...m.querySelectorAll(':scope>[role=menuitem],:scope>[role=none]>[role=menuitem]')].map(b=>[b.querySelector('span').textContent,b.getAttribute('aria-keyshortcuts'),b.querySelector('.menu-keys')?.textContent??null])}})()");
    // the shortcuts as the platform writes them: ⌘ on macOS, Ctrl elsewhere
    const apple = await page.eval("/Mac|iPhone|iPad/.test(navigator.platform||navigator.userAgent||'')");
    stage('F1 File menu', {...fileMenu, apple});
    const shown = apple ? ['⌘O', '⌘S', '⇧⌘S'] : ['Ctrl+O', 'Ctrl+S', 'Shift+Ctrl+S'];
    assert.deepEqual(fileMenu, {open: true, expanded: 'true', role: 'menu', label: 'File', items: [['Open…', 'Control+O Meta+O', shown[0]], ['Save', 'Control+S Meta+S', shown[1]], ['Save As…', 'Control+Shift+S Meta+Shift+S', shown[2]], ['Export', null, null], ['Browser copy', null, null]]});
    assert.equal(await axNamed('menu', 'File'), 1);
    for (const name of ['Open…', 'Save', 'Save As…', 'Export', 'Browser copy']) assert.equal(await axNamed('menuitem', name), 1, 'menuitem ' + name);
    const focusId = () => page.eval("document.activeElement.id");
    const walk = [];
    walk.push(await focusId()); await press('ArrowDown'); walk.push(await focusId()); await press('End'); walk.push(await focusId()); await press('Home'); walk.push(await focusId());
    await press('ArrowUp'); walk.push(await focusId()); await press('ArrowUp'); walk.push(await focusId()); await press('ArrowRight'); walk.push(await focusId());
    const exportItems = await page.eval("[...document.querySelectorAll('#export-menu [role=menuitem]')].map(b=>b.textContent)");
    await press('ArrowDown'); walk.push(await focusId()); await key('Escape'); walk.push(await focusId());
    const subClosed = await page.eval("document.getElementById('export-menu').hidden&&!document.getElementById('file-menu').hidden");
    await press('ArrowDown'); await press('ArrowRight'); walk.push(await focusId());
    const browserCopy = await page.eval("[...document.querySelectorAll('#browser-copy-menu [role=menuitem]')].map(b=>b.textContent)");
    await press('ArrowLeft'); walk.push(await focusId()); await press('ArrowRight'); await press('ArrowLeft');
    await key('Escape'); walk.push(await focusId());
    const closed = await page.eval("document.getElementById('file-menu').hidden&&document.getElementById('file-menu-button').getAttribute('aria-expanded')==='false'");
    await press('ArrowDown'); await key('ArrowRight', [], 'ArrowRight'); walk.push(await focusId());
    const editMenu = [await axNamed('menu', 'Edit'), await axNamed('menuitem', 'Reset design')];
    await key('Escape'); walk.push(await focusId());
    stage('F1 keyboard', {walk, exportItems, browserCopy, subClosed, closed, editMenu});
    assert.deepEqual(walk, ['menu-open', 'menu-save', 'menu-browser-copy', 'menu-open', 'menu-browser-copy', 'menu-export', 'save-project', 'menu-export-session', 'menu-export', 'save-draft', 'menu-browser-copy', 'file-menu-button', 'reset', 'edit-menu-button']);
    assert.deepEqual(exportItems, ['Model file…', 'Model with runs (session file)…']); assert.deepEqual(browserCopy, ['Save browser draft', 'Restore browser draft']);
    assert.equal(subClosed, true, 'Escape closes the submenu only'); assert.equal(closed, true, 'Escape closes the File menu');
    assert.deepEqual(editMenu, [1, 1], 'the Edit menu and Reset design by role and name');
    // the menus fit the page, opened with a submenu, at 1440 × 900 and 390 × 844
    for (const [width, height, mobile] of [[1440, 900, false], [390, 844, true]]) {
      await page.call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile}); await sleep(300);
      await page.eval("document.getElementById('file-menu-button').focus()"); await press('Enter'); await press('End'); await press('ArrowUp'); await press('ArrowRight');
      const fit = await page.eval("({over:document.documentElement.scrollWidth-document.documentElement.clientWidth,menus:[...document.querySelectorAll('.menu-list:not([hidden])')].map(m=>{const r=m.getBoundingClientRect();return [Math.round(r.left),Math.round(r.right)]}),width:innerWidth})");
      stage('F1 menu fits', {width, height, ...fit}); await page.screenshot(`f1-menu-${width}`);
      assert.ok(fit.over <= 0, `the open menu overflows by ${fit.over}px at ${width}`); assert.equal(fit.menus.length, 2);
      assert.ok(fit.menus.every(([l, r]) => l >= 0 && r <= fit.width), JSON.stringify(fit));
      await key('Escape'); await key('Escape');
    }
    await page.call('Emulation.setDeviceMetricsOverride', {width: 1280, height: 800, deviceScaleFactor: 1, mobile: false}); await sleep(300);
    // round 13 (O1): P1's Save left a current file (p1-four.json); the Optical waveguide card opens
    // the model afresh, which drops it, so F2 starts with no file name as before
    await page.click('nav [data-page=Applications]'); await page.until("!!document.querySelector('[data-template=optical]')", 'F Library');
    await page.click('[data-template=optical]'); await page.until("!!document.querySelector('#shape-w')||document.querySelector('nav [data-page=Model][aria-selected=true]')", 'F optical model');
    await answerDialogs("!document.querySelector('dialog[open]')", 'F optical card');
    // F2: no picker here. Save without a chosen file asks for a name (the " (1)" note); Cancel writes nothing
    assert.equal(await page.eval("typeof window.showSaveFilePicker"), 'undefined');
    let before = await listDownloads();
    await page.eval("document.getElementById('file-menu-button').focus()"); await key('s', ['Control']);
    await page.until("document.getElementById('save-name-dialog').open", 'F2 Save name dialog');
    const saveDialog = await page.eval("({title:document.getElementById('save-name-title').textContent,name:document.getElementById('save-name-input').value,note:document.getElementById('save-name-note').textContent,unavailable:document.getElementById('save-name-unavailable').hidden,buttons:[...document.querySelectorAll('#save-name-dialog button')].map(b=>b.textContent),label:document.querySelector('#save-name-dialog label').textContent})");
    stage('F2 Save dialog', saveDialog);
    // P3: Save writes the project file; an untitled project suggests untitled-project.json, never a model file's name
    assert.equal(saveDialog.title, 'Save'); assert.equal(saveDialog.name, 'untitled-project.json'); assert.equal(saveDialog.label, 'File name');
    assert.equal(saveDialog.note, 'Your browser saves to its Downloads folder, or asks where if you set it to. If that folder already has a file of this name, the browser may add “ (1)” to the new one.');
    assert.deepEqual(saveDialog.buttons, ['Cancel', 'Download']); assert.equal(saveDialog.unavailable, true);
    await page.click('#save-name-cancel'); await sleep(400);
    assert.equal(await status(), 'Save cancelled; nothing was written.'); assert.deepEqual(await listDownloads(), before, 'Cancel downloads nothing');
    // Save As: the typed name, sanitised, with .json added
    await key('s', ['Control', 'Shift']); await page.until("document.getElementById('save-name-dialog').open", 'F2 Save As name dialog');
    assert.equal(await page.eval("document.getElementById('save-name-title').textContent"), 'Save As');
    await page.eval("(()=>{const i=document.getElementById('save-name-input');i.value='';i.focus();})()");
    await page.call('Input.insertText', {text: 'my run/<x>?'}); await sleep(200);
    const typed = await page.eval("document.getElementById('save-name-input').value");
    await page.click('#save-name-download');
    const fallbackName = await newDownload(before), fallbackText = await readFile(join(downloads, fallbackName), 'utf8');
    const fallbackMessage = await status();
    stage('F2 name dialog download', {typed, file: fallbackName, message: fallbackMessage, bytes: Buffer.byteLength(fallbackText)});
    assert.equal(typed, 'my runx'); assert.equal(fallbackName, 'my runx.json');
    assert.match(fallbackMessage, /^Project file my runx\.json sent to your browser's Downloads: Optical waveguide \(\d+ runs, the comparison\)/);
    assert.doesNotMatch(fallbackMessage, /^Saved /); assert.doesNotMatch(fallbackMessage, /not in this file/);
    // an untitled project takes the file's stem as its name on its first save (P3)
    assert.match(await page.eval("document.getElementById('project').textContent"), /^my runx · my runx\.json · downloaded /);
    assert.equal(JSON.parse(fallbackText).name, 'my runx'); assert.equal(JSON.parse(fallbackText).format, 'openphysics-studio-project');
    // F5 (C1(f)): an automated browser (navigator.webdriver true, as Playwright and WebDriver set it;
    // this harness's Chrome, started with --headless=new over DevTools, reports false, so the value
    // is set at that boundary): with a picker stub that throws if called, Save As asks for a name
    // and downloads, and the stub is never called
    report.harnessWebdriver = await page.eval("navigator.webdriver");
    await page.eval("Object.defineProperty(navigator,'webdriver',{get:()=>true,configurable:true})");
    await page.eval("window.__pickerCalls=0;window.showSaveFilePicker=()=>{window.__pickerCalls++;throw new Error('the picker must not be called');}");
    before = await listDownloads();
    await key('s', ['Control', 'Shift']); await page.until("document.getElementById('save-name-dialog').open", 'F5 automated name dialog');
    const automated = {unavailable: await page.eval("document.getElementById('save-name-unavailable').hidden")};
    await page.click('#save-name-download'); automated.file = await newDownload(before); automated.calls = await page.eval('window.__pickerCalls');
    stage('F5 automated browser', automated);
    assert.equal(automated.calls, 0); assert.equal(automated.unavailable, true, 'the same dialog as a browser without the picker');
    // round 13 (O1): Save As is prefilled with the current file name, F2's my runx.json
    assert.match(automated.file, /^my runx(?: \(\d\))?\.json$/); assert.match(await status(), /sent to your browser's Downloads/);
    // F3: the picker stubbed at both boundaries, window.showSaveFilePicker (R8) and
    // navigator.webdriver (false, as in a browser people use)
    await page.eval("Object.defineProperty(navigator,'webdriver',{get:()=>false,configurable:true})");
    await page.eval(`(()=>{window.__picker={calls:[],files:{'chosen.json':'OLD CONTENT'},writes:0,aborts:0,mode:'ok',failWrite:false};
      window.showSaveFilePicker=async options=>{const p=window.__picker;p.calls.push({...options,...('startIn' in options?{startIn:typeof options.startIn==='string'?options.startIn:'handle:'+options.startIn.name}:{})});
        if(p.mode==='abort')throw new DOMException('The user aborted a request.','AbortError');if(p.mode==='deny')throw new DOMException('Not allowed in this browser.','NotAllowedError');
        const name='chosen.json';return {kind:'file',name,createWritable:async()=>{let buffer='';return {write:async t=>{if(p.failWrite)throw new DOMException('Disk full','QuotaExceededError');buffer+=t;},close:async()=>{p.files[name]=buffer;p.writes++;},abort:async()=>{p.aborts++;}};}};};})()`);
    const picker = () => page.eval("JSON.parse(JSON.stringify({calls:window.__picker.calls,writes:window.__picker.writes,aborts:window.__picker.aborts,content:window.__picker.files['chosen.json']}))");
    before = await listDownloads();
    await key('s', ['Control', 'Shift']); await page.until("/^Saved chosen to /.test(document.getElementById('file-status').textContent)", 'F3 Save As');
    let p3 = await picker(); const saveAsMessage = await status();
    stage('F3 Save As', {calls: p3.calls, writes: p3.writes, message: saveAsMessage});
    assert.equal(p3.calls.length, 1); assert.equal(p3.writes, 1);
    // round 13 (F3): no startIn before a file is chosen, so the id alone restores the last folder;
    // (O1) the suggested name is the current file's, my runx.json from F2
    assert.deepEqual({...p3.calls[0], suggestedName: undefined}, {suggestedName: undefined, types: [{description: 'OpenPhysics project file (JSON)', accept: {'application/json': ['.json']}}], id: 'openphysics-project'});
    assert.equal('startIn' in p3.calls[0], false); assert.equal(p3.calls[0].suggestedName, 'my runx.json');
    // the save time is for display only and in no digest: every other byte is the download's
    const withoutTime = t => String(t).replace(/"savedAt":"[^"]*"/, '"savedAt":""');
    // round 16 (S6): the name my runx came from a file name, so it follows Save As to chosen.json;
    // every other byte is the download's
    const withoutName = t => withoutTime(t).replace(/"name":"[^"]*"/, '"name":""');
    assert.equal(JSON.parse(p3.content).name, 'chosen');
    assert.equal(withoutName(p3.content), withoutName(fallbackText), 'the picker file has the bytes of the download of the same state');
    assert.match(saveAsMessage, /^Saved chosen to chosen\.json: Optical waveguide \(\d+ runs, the comparison\)/);
    assert.deepEqual(await listDownloads(), before, 'a picker save downloads nothing');
    assert.match(await page.eval("document.getElementById('project').textContent"), /^chosen · chosen\.json · saved [^(]+$/, 'the header names the file written, not as a download');
    assert.equal(await page.eval("document.getElementById('project').hasAttribute('title')"), false, 'no (1) title text on the picker path');
    // Save: the same file again, no dialog
    await page.eval("document.getElementById('file-status').textContent=''");
    await page.click('#menu-save'); await page.until("/^Saved chosen to chosen\\.json/.test(document.getElementById('file-status').textContent)", 'F3 Save');
    p3 = await picker(); stage('F3 Save again', {calls: p3.calls.length, writes: p3.writes});
    assert.equal(p3.calls.length, 1, 'Save asks nothing'); assert.equal(p3.writes, 2); assert.equal(withoutName(p3.content), withoutName(fallbackText));
    // a cancel writes nothing and says so
    await page.eval("window.__picker.mode='abort'"); await key('s', ['Control', 'Shift']); await sleep(400);
    p3 = await picker(); stage('F3 cancel', {calls: p3.calls.length, writes: p3.writes, message: await status()});
    assert.equal(await status(), 'Save As cancelled; nothing was written.'); assert.equal(p3.writes, 2); assert.equal(p3.calls[1].startIn, 'handle:chosen.json', 'Save As starts in the current file');
    // a failed write leaves the file whole and says so
    await page.eval("window.__picker.mode='ok';window.__picker.files['chosen.json']='OLD CONTENT';window.__picker.failWrite=true");
    await key('s', ['Control']); await sleep(400);
    p3 = await picker(); const failMessage = await status(); stage('F3 failed write', {writes: p3.writes, aborts: p3.aborts, content: p3.content, message: failMessage});
    assert.equal(failMessage, 'Project not saved: chosen.json could not be written (Disk full); the file is unchanged.');
    assert.equal(p3.content, 'OLD CONTENT'); assert.equal(p3.aborts, 1); assert.equal(p3.writes, 2);
    // F4: a picker that refuses falls back to the name dialog, which says so
    await page.eval("window.__picker.failWrite=false;window.__picker.mode='deny'"); before = await listDownloads();
    await key('s', ['Control', 'Shift']); await page.until("document.getElementById('save-name-dialog').open", 'F4 name dialog');
    const refused = await page.eval("document.getElementById('save-name-unavailable').textContent");
    stage('F4 picker refused', {refused});
    assert.equal(refused, "The browser's save dialog was not available (Not allowed in this browser.), so the file is downloaded instead.");
    await page.click('#save-name-download'); const f4Name = await newDownload(before);
    assert.match(f4Name, /^chosen\.json$/); assert.match(await status(), /sent to your browser's Downloads/);
    await page.eval("delete window.showSaveFilePicker");
    // round 13 (O1; pre-registered): with no picker, Save remembers the Save As name. Save and
    // Ctrl+S download under it again with no dialog; the header names the file and its state; File ›
    // Open sets the name to the opened file's; Reset design drops it, so Save asks again
    const header = () => page.eval("document.getElementById('project').textContent");
    const noDialog = async label => { for (let i = 0; i < 10; i++) { assert.equal(await page.eval("!!document.getElementById('save-name-dialog').open"), false, label + ': no name dialog'); await sleep(100); } };
    const savedWidth = name => readFile(join(downloads, name), 'utf8').then(t => JSON.parse(t).models.find(m => m.kind === 'workspace').session.input.model.shapes[0].w);
    before = await listDownloads();
    await key('s', ['Control', 'Shift']); await page.until("document.getElementById('save-name-dialog').open", 'O1 Save As');
    // round 14 (Q1): the Save As name dialog says later saves download again under this name; round 16
    // (S11): that this browser cannot write to the file (the Chrome and Edge sentence is in the docs only)
    assert.equal(await page.eval("document.getElementById('save-name-note').textContent"), 'Your browser saves to its Downloads folder, or asks where if you set it to. This browser cannot write to the file, so later saves download again under this name and may add “ (1)”.');
    await page.eval("(()=>{const i=document.getElementById('save-name-input');i.value='';i.focus();})()"); await page.call('Input.insertText', {text: 'design-a-ng'});
    await page.click('#save-name-download'); const o1First = await newDownload(before), o1FirstMessage = await status();
    assert.equal(o1First, 'design-a-ng.json'); assert.match(o1FirstMessage, /^Project file design-a-ng\.json sent to your browser's Downloads: /, 'the first download says where it went');
    // round 16 (S6): a name from a file name follows Save As (P3 kept it)
    assert.match(await header(), /^design-a-ng · design-a-ng\.json · downloaded \d{1,2}:\d\d(?: [AP]M)?$/);
    assert.equal(await page.eval("document.getElementById('project').title"), 'Your browser may have added “ (1)” to the file name.');
    await toGeometry(); await page.type('#shape-w', 650); await sleep(300);
    const o1Edited = await header(); assert.match(o1Edited, /^design-a-ng · design-a-ng\.json · changed since downloaded \d{1,2}:\d\d(?: [AP]M)? · /);
    assert.equal(await page.eval("document.getElementById('project').title"), 'Your browser may have added “ (1)” to the file name.');
    before = await listDownloads(); await page.click('nav [data-page=Model]'); await page.click('#menu-save');
    await noDialog('O1 Save'); const o1Second = await newDownload(before), o1SecondMessage = await status(), o1SecondHeader = await header();
    stage('O1 Save under the Save As name', {first: o1First, edited: o1Edited, second: o1Second, message: o1SecondMessage, header: o1SecondHeader});
    assert.match(o1Second, /^design-a-ng(?: \(\d\))?\.json$/); assert.equal(await savedWidth(o1Second), 650, 'the second file holds Width 650');
    // round 14 (Q2): Width 650 (650 × 400 nm here) has no run, and the save notice says so
    assert.match(o1SecondMessage, /^Downloaded design-a-ng\.json again: Optical waveguide \(\d+ runs?(?:, the comparison)?\)(?: and [^.]+)?\.(?: Optical waveguide keeps values only for [^.]+\.)? Current inputs \(650 × 400 nm\) have no run yet\. A download cannot replace the earlier file, so your browser may add a number such as “ \(1\)” to its name\.$/);
    assert.match(o1SecondHeader, /^design-a-ng · design-a-ng\.json · downloaded \d{1,2}:\d\d(?: [AP]M)?$/); assert.doesNotMatch(o1SecondHeader, /Unsaved inputs/);
    // Ctrl+S after another edit: the same, no dialog
    await toGeometry(); await page.type('#shape-w', 660); await sleep(300); before = await listDownloads();
    await page.eval("document.activeElement?.blur()"); await key('s', ['Control']); await noDialog('O1 Ctrl+S');
    const o1Third = await newDownload(before); assert.match(o1Third, /^design-a-ng(?: \(\d\))?\.json$/); assert.equal(await savedWidth(o1Third), 660);
    // Save As is prefilled with the current name; Cancel writes nothing
    await key('s', ['Control', 'Shift']); await page.until("document.getElementById('save-name-dialog').open", 'O1 Save As again');
    assert.equal(await page.eval("document.getElementById('save-name-input').value"), 'design-a-ng.json'); await page.click('#save-name-cancel'); await sleep(300);
    // File › Open of that project file: the name is the opened file's; an edit and Save keep it, with no dialog
    await page.eval("document.getElementById('autosave-status').textContent=''");
    await setFile('#session-file', join(downloads, o1First));
    await answerDialogs("/^Opened design-a-ng\\.json/.test(document.getElementById('autosave-status').textContent)", 'O1 open');
    await page.click('nav [data-page=Model]'); await sleep(200); const o1Opened = await header(); assert.equal(o1Opened, 'design-a-ng · design-a-ng.json · opened');
    assert.equal(await page.eval("document.getElementById('autosave-status').textContent"), 'Opened design-a-ng.json');
    await toGeometry(); await page.type('#shape-w', 640); await sleep(300);
    const o1OpenedEdited = await header(); assert.match(o1OpenedEdited, /^design-a-ng · design-a-ng\.json · changed since opened · /);
    before = await listDownloads(); await page.click('#menu-save'); await noDialog('O1 Save after Open');
    const o1Fourth = await newDownload(before); assert.match(o1Fourth, /^design-a-ng(?: \(\d\))?\.json$/); assert.equal(await savedWidth(o1Fourth), 640);
    assert.match(await status(), /^Project file design-a-ng\.json sent to your browser's Downloads: .* A download cannot replace the earlier file, so your browser may add a number such as “ \(1\)” to its name\.$/);
    // P3 (intended change): Reset design edits a model of the project, so the project file is
    // kept: the header still names it, changed, and Save downloads under it with no dialog
    await page.click('#reset'); await sleep(300); const o1Reset = await header();
    assert.match(o1Reset, /^design-a-ng · design-a-ng\.json · changed since downloaded \d{1,2}:\d\d(?: [AP]M)? · /);
    before = await listDownloads(); await page.click('#menu-save'); await noDialog('O1 Save after reset');
    assert.match(await newDownload(before), /^design-a-ng(?: \(\d\))?\.json$/);
    stage('O1 open and reset', {opened: o1Opened, openedEdited: o1OpenedEdited, fourth: o1Fourth, reset: o1Reset});
    // F2 (round 13): a model file over 64 KiB opened through File › Open is refused by the model reader
    const bigModel = JSON.parse(await readFile(join(out, 'p1-four.json'), 'utf8')); bigModel.padding = 'x'.repeat(70 * 1024);
    const bigPath = join(out, 'model-over-64k.json'); await writeFile(bigPath, JSON.stringify(bigModel));
    await setFile('#session-file', bigPath); await page.until("/^Open failed/.test(document.getElementById('file-status').textContent)", 'F2 big model file');
    assert.equal(await status(), 'Open failed: Model file exceeds 64 KiB. Current inputs kept.'); stage('F2 model file over 64 KiB', {message: await status()});
    await noOverflow('P2 File menu');
  }

  // OB (optical open boundary, slice P2; pre-registered): in a browser context of its own (a fresh
  // start page, its own storage and downloads): the Outer boundary choice and Search near n_eff in
  // Physics › Optical modes, an edge closed again in Geometry › Boundaries, the Study summary and
  // the PML check, the template run all open (found line, loss cells, other candidates, the check
  // column), a session of version 10, Compare with a closed run of the template (matched on the physical
  // windows since slice P3; per-side loss headers, the note, O2's 24 px), and the leakage case built here: a
  // silicon substrate under a 500 nm BOX.
  {
    const devtools = await (await fetch(`http://127.0.0.1:${debugPort}/json/version`)).json();
    const browserPage = new Page(devtools.webSocketDebuggerUrl); await browserPage.ready;
    const {browserContextId} = await browserPage.call('Target.createBrowserContext');
    const {targetId} = await browserPage.call('Target.createTarget', {url: 'about:blank', browserContextId});
    const ob = new Page(`ws://127.0.0.1:${debugPort}/devtools/page/${targetId}`); await ob.ready;
    await ob.call('Runtime.enable'); await ob.call('Page.enable'); await ob.call('DOM.enable'); await ob.call('Accessibility.enable');
    const obSize = async (width, height, mobile = false) => { await ob.call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile}); await sleep(300); };
    await obSize(1280, 800);
    const obDownloads = join(out, 'downloads-open-boundary'); await mkdir(obDownloads, {recursive: true});
    await browserPage.call('Browser.setDownloadBehavior', {behavior: 'allow', downloadPath: obDownloads, browserContextId});
    await ob.call('Page.addScriptToEvaluateOnNewDocument', {source: 'delete window.showSaveFilePicker;delete Window.prototype.showSaveFilePicker;'});
    const obText = selector => ob.onElement('function(selector){const e=this.querySelector(selector);return e?e.innerText.replace(/\\s+/g," ").trim():null}', selector);
    const obValue = selector => ob.onElement('function(selector){const e=this.querySelector(selector);return e?e.value:null}', selector);
    // a control by role and accessible name in the accessibility tree: how many there are, and whether checked
    const control = async (role, name) => {
      const {result: document} = await ob.call('Runtime.evaluate', {expression: 'document'});
      const {nodes} = await ob.call('Accessibility.queryAXTree', {objectId: document.objectId, accessibleName: name, role});
      const found = nodes.filter(n => !n.ignored);
      return {count: found.length, checked: found[0]?.properties?.find(p => p.name === 'checked')?.value?.value ?? null, disabled: found[0]?.properties?.find(p => p.name === 'disabled')?.value?.value ?? false};
    };
    const obOverflow = async tag => {
      for (const [width, height, mobile] of [[1440, 900, false], [390, 844, true]]) {
        await obSize(width, height, mobile);
        const over = await ob.eval('document.documentElement.scrollWidth-document.documentElement.clientWidth');
        stage('OB overflow ' + tag, {width, height, over}); assert.ok(over <= 0, `${tag} at ${width} × ${height} overflows by ${over}px`);
      }
      await obSize(1280, 800);
    };
    const toTree = async (name, ready) => { await ob.click('nav [data-page=Model]'); await sleep(200); await ob.clickTreeItem(name); await ob.until(ready, name); };
    const solverDocument = async () => { await toTree('Study', "!!document.querySelector('details.solver-document pre')"); return JSON.parse(await ob.eval("document.querySelector('details.solver-document pre').textContent")); };
    const obRun = async () => {
      await ob.until("!document.getElementById('run-optical').disabled", 'OB Run enabled');
      const before = await ob.eval("document.querySelectorAll('.run-item').length");
      const started = Date.now(); await ob.click('#run-optical'); if (await ob.eval("!!document.getElementById('run-drop-confirm')?.open")) await ob.click('#run-drop-confirm-run');
      await ob.until(`document.querySelectorAll('.run-item').length>${before}&&!document.getElementById('run-optical').disabled&&document.getElementById('run-optical').textContent==='Run study'&&!!document.getElementById('modes-table')`, 'OB run', 300000);
      return Math.round((Date.now() - started) / 1000);
    };
    const resultsView = () => ob.eval(`(()=>{const t=document.getElementById('modes-table');const rows=[...t.tBodies[0].rows];
      return {caption:t.caption.textContent,head:[...t.tHead.rows[0].cells].map(c=>c.textContent),lossTitle:t.tHead.rows[0].cells[3].title,
       neff:rows.map(r=>r.querySelector('[data-neff]').textContent),loss:rows.map(r=>r.querySelector('[data-loss]').textContent),lossTitles:rows.map(r=>r.querySelector('[data-loss]').title),
       pol:rows.map(r=>[r.querySelector('[data-polarization]')?.textContent,r.querySelector('[data-polarization]')?.title]),area:rows.map(r=>r.querySelector('[data-area]').textContent),areaTitles:rows.map(r=>r.querySelector('[data-area]').title),
       ng:rows.map(r=>r.querySelector('[data-group-index]').textContent),ngTitles:rows.map(r=>r.querySelector('[data-group-index]').title),
       check:rows.map(r=>{const c=r.querySelector('[data-pml-check]');return c?[c.dataset.pmlCheckStatus,c.textContent]:null}),italic:rows.map(r=>!!r.querySelector('[data-loss] em')),
       found:document.getElementById('modes-found')?.textContent??null,note:document.getElementById('loss-note')?.textContent??document.getElementById('lossless-note')?.textContent??null,
       candidates:(()=>{const d=document.getElementById('other-candidates');if(!d)return null;const head=[...d.querySelectorAll('thead th')].map(c=>c.textContent),rows=[...d.querySelectorAll('tbody tr')],col=head.indexOf('Search');
        return {summary:d.querySelector('summary').textContent,head,rows:rows.length,reasons:[...new Set(rows.map(r=>r.cells[r.cells.length-1].textContent))],searches:col<0?null:[...new Set(rows.map(r=>r.cells[col].textContent))].sort(),controls:d.querySelectorAll('button,canvas,a').length}})()};})()`);

    await ob.call('Page.navigate', {url: base + '/workspace'});
    await ob.until("/^Connected/.test(document.getElementById('connection-status').textContent)&&!!document.querySelector('[data-template=optical]')", 'OB connected start page');
    await ob.click('[data-template=optical]'); await ob.until("!!document.querySelector('#shape-w')", 'OB optical template');

    // 1. Physics › Optical modes: Closed window by default; Open shows PML 1 µm and Search near n_eff 2.460
    await toTree('Optical modes', "!!document.getElementById('outer-boundary')");
    const closedChoice = {closed: await control('radio', 'Closed window (PEC)'), open: await control('radio', 'Open boundary (PML)'), help: await obText('#open-boundary-help')};
    stage('OB choice, closed', closedChoice);
    assert.deepEqual([closedChoice.closed.count, closedChoice.closed.checked, closedChoice.open.count, closedChoice.open.checked], [1, 'true', 1, 'false']);
    assert.equal(closedChoice.help, 'Open boundary adds an absorbing layer (PML) outside the window, so light that leaves the window is lost. Loss then includes leakage. Shapes touching an open edge continue through the layer.');
    await ob.click('input[name="outer-boundary"][value="open"]'); await ob.until("!!document.getElementById('target-number')", 'OB Open chosen');
    const openChoice = {open: await control('radio', 'Open boundary (PML)'), target: await control('spinbutton', 'Search near n_eff'), value: await obValue('#target-number'),
      thickness: await obText('#pml-thickness'), groupIndex: await control('checkbox', 'Also compute group index (3 solves)'), groupNote: await obText('#group-index-open-note'),
      details: await ob.eval("document.querySelector('#pml-details p').textContent"), targetHelp: await obText('#target-help'), lower: await obText('#lower-target')};
    stage('OB choice, open', openChoice);
    assert.deepEqual([openChoice.open.checked, openChoice.target.count, openChoice.value, openChoice.thickness], ['true', 1, '2.460', 'PML thickness PML 1 µm']);
    // slice P3: the group index box stays enabled with an open boundary, without P2's note
    assert.deepEqual([openChoice.groupIndex.count, openChoice.groupIndex.disabled], [1, false]);
    assert.equal(openChoice.groupNote, null);
    // slice T2 (pre-registered): the second search near (2.46 + 1.444) / 2 = 1.95, shown as text
    assert.equal(openChoice.details, 'PML 1 µm (fixed) · strength 3, order 2 · minimum physical fraction 0.5 · 32 candidates searched near n_eff, 16 near the second index');
    assert.equal(openChoice.lower, 'Also searches near 1.95, for modes close to the silica index.');
    assert.equal(openChoice.targetHelp, 'Studio searches for modes near this index and near a second index halfway to the silica index (1.95). Modes are listed by n_eff, highest first. The default is halfway between the core and silica indices: (n_core + 1.444)/2.');
    assert.equal(await ob.eval("document.getElementById('target-number').getAttribute('aria-describedby')"), 'lower-target target-help');
    await obOverflow('Physics › Optical modes, Open');

    // 2. the drawing: a grey band outside each open edge; Geometry › Boundaries closes the bottom edge
    const drawing = () => ob.eval("({bands:[...document.querySelectorAll('[data-pml]')].map(b=>b.dataset.pml),labels:[...document.querySelectorAll('[data-pml] text')].map(t=>t.textContent),section:[...document.querySelectorAll('svg[data-geometry-view=physical] text')].map(t=>t.textContent).find(t=>t.startsWith('x: '))})");
    await toTree('Geometry', "!!document.querySelector('#shape-w')");
    const four = await drawing(); stage('OB drawing, four edges', four);
    assert.deepEqual(four.bands, ['left', 'right', 'bottom', 'top']); assert.deepEqual(four.labels, ['PML 1 µm', 'PML 1 µm', 'PML 1 µm', 'PML 1 µm']);
    assert.equal(four.section, 'x: −1500 … +1500 nm · y: −1200 … +1200 nm · silica background · open boundary (PML 1 µm) on 4 edges');
    const bottomEdge = async () => { await ob.click('[data-pick-mode=Boundaries]'); await sleep(200); await ob.onElement('function(selector){this.querySelector(selector).dispatchEvent(new MouseEvent("click",{bubbles:true}));return true}', '[data-pick-edge=optical-bottom]'); await ob.until("!!document.getElementById('close-edge')", 'OB bottom edge'); };
    await bottomEdge();
    const edgeOpen = {heading: await obText('.boundary-selection h3'), toggle: await control('switch', 'Close this edge')};
    stage('OB bottom edge open', edgeOpen);
    assert.deepEqual([edgeOpen.heading, edgeOpen.toggle.count, edgeOpen.toggle.checked], ['Optical bottom boundary · Open (PML)', 1, 'false']);
    await ob.click('#close-edge'); await ob.until("document.querySelectorAll('[data-pml]').length===3", 'OB bottom closed');
    const three = await drawing(), closedEdge = {heading: await obText('.boundary-selection h3'), toggle: await control('switch', 'Close this edge')};
    stage('OB bottom edge closed', {three, closedEdge});
    assert.deepEqual(three.bands, ['left', 'right', 'top']); assert.match(three.section, / · open boundary \(PML 1 µm\) on 3 edges$/);
    assert.deepEqual([closedEdge.heading, closedEdge.toggle.checked], ['Optical bottom boundary', 'true']);
    const threeDoc = await solverDocument(); stage('OB document, bottom closed', {pml: threeDoc.physics.em1.pml.pml_thickness, domain: threeDoc.geometry.domain});
    assert.deepEqual(Object.keys(threeDoc.physics.em1.pml.pml_thickness), ['left', 'right', 'top']); assert.deepEqual(threeDoc.geometry.domain, {xmin: -2500, xmax: 2500, ymin: -1200, ymax: 2200});
    await toTree('Geometry', "!!document.querySelector('svg[data-geometry-view=physical]')"); await bottomEdge(); await ob.click('#close-edge');
    await ob.until("document.querySelectorAll('[data-pml]').length===4", 'OB bottom open again');
    await ob.click('[data-pick-mode=Bodies]'); await sleep(200);
    await obOverflow('Geometry with PML bands');

    // 3. Search near n_eff: an edit changes target_effective_index; the default document is P1's
    const defaultDoc = await solverDocument(); assert.equal(defaultDoc.physics.em1.target_effective_index, 2.46);
    assert.deepEqual(defaultDoc.physics.em1.pml.pml_additional_searches, [{target_effective_index: 1.95, pml_search_mode_count: 16}]);
    await toTree('Optical modes', "!!document.getElementById('target-number')"); await ob.type('#target-number', '2.3');
    const lowerEdited = await obText('#lower-target');
    const editedDoc = await solverDocument(); stage('OB Search near n_eff 2.3', {target: editedDoc.physics.em1.target_effective_index, searches: editedDoc.physics.em1.pml.pml_additional_searches, lower: lowerEdited});
    assert.equal(editedDoc.physics.em1.target_effective_index, 2.3);
    // slice T2: the second search follows the target, (2.3 + 1.444) / 2 = 1.872 -> 1.87
    assert.equal(lowerEdited, 'Also searches near 1.87, for modes close to the silica index.');
    assert.deepEqual(editedDoc.physics.em1.pml.pml_additional_searches, [{target_effective_index: 1.87, pml_search_mode_count: 16}]);
    assert.deepEqual({...editedDoc, physics: {em1: {...editedDoc.physics.em1, target_effective_index: 2.46, pml: {...editedDoc.physics.em1.pml, pml_additional_searches: defaultDoc.physics.em1.pml.pml_additional_searches}}}}, defaultDoc);
    // an edited target that a material edit puts out of range (silicon nitride: n_max 1.9963) goes back
    // to the new design's default, with a message, and every input write keeps working
    await toTree('Geometry', "!!document.querySelector('#shape-w')"); await ob.choose('#shape-material', 'Silicon nitride');
    const stale = await obText('#file-status');
    await toTree('Optical modes', "!!document.getElementById('target-number')"); const reset = await obValue('#target-number');
    stage('OB stale target', {message: stale, value: reset});
    assert.equal(stale, 'Search near n_eff 2.300 is outside this design\'s range: back to the default 1.720.'); assert.equal(reset, '1.720');
    await toTree('Geometry', "!!document.querySelector('#shape-w')"); await ob.choose('#shape-material', 'Silicon');
    await toTree('Optical modes', "!!document.getElementById('target-number')"); assert.equal(await obValue('#target-number'), '2.460');
    await ob.type('#target-number', '2.46');
    assert.equal(await obValue('#target-number'), '2.460');

    // 4. Study: the summary line and the PML check option; the template run, all edges open, with the check
    await toTree('Study', "!!document.getElementById('open-boundary-summary')");
    const studyView = {summary: await obText('#open-boundary-summary'), check: await control('checkbox', 'Also check the PML (2 more solves)')};
    stage('OB Study', studyView);
    assert.deepEqual([studyView.summary, studyView.check.count, studyView.check.checked], ['Open boundary · PML 1 µm · searches near 2.46 and 1.95', 1, 'false']);
    await ob.click('#pml-check'); assert.equal((await control('checkbox', 'Also check the PML (2 more solves)')).checked, 'true');
    await obOverflow('Study with the PML check');
    // slice P3: the template run also computes the group index (complex with an open boundary)
    await toTree('Optical modes', "!!document.getElementById('group-index-check')"); await ob.click('#group-index-check');
    assert.equal((await control('checkbox', 'Also compute group index (3 solves)')).checked, 'true');
    const templateDoc = await solverDocument();
    assert.deepEqual(templateDoc.results.group_index, {wavelength_step: '1 nm'}); assert.equal(templateDoc.physics.em1.pml.pml_strength, 3);
    const templateSeconds = await obRun();
    await ob.until("document.querySelectorAll('[data-pml-check]').length===2&&!document.getElementById('run-optical').disabled", 'OB PML check', 300000);
    const template = await resultsView(); stage('OB template, all open, PML check', {...template, seconds: templateSeconds});
    assert.equal(template.caption, 'Modes (open boundary, PML 1 µm)');
    assert.deepEqual(template.head, ['Mode', 'n_eff', 'Polarization', 'Loss (dB/cm)', 'A_eff (µm²)', 'n_g', 'PML check']);
    assert.equal(template.lossTitle, 'Material absorption (k) and leakage into the PML of the open boundary');
    assert.equal(template.found, 'Found 2 of 2 modes near n_eff 2.46 and 1.95. Move Search near n_eff to find other modes.');
    // pre-registered: both modes below what the open boundary resolves
    assert.deepEqual(template.loss, ['< 0.01 dB/cm', '< 0.01 dB/cm']);
    template.lossTitles.forEach((t, i) => assert.equal(t, template.check[i][0] === 'depends' ? 'This loss changes with the PML; it is not a converged leakage loss.' : 'Below what this open boundary resolves for a 3 × 2.4 µm window (0.01 dB/cm). The mode does not leak measurably here.'));
    assert.deepEqual(template.italic, template.check.map(([status]) => status === 'depends'));
    // slice P3: polarization, A_eff and Re n_g on the physical window: the strings of the engine run
    // of the same document on this machine, formatted by the page's own functions
    const templateEngine = spawnSync(args.python, ['-c', [
      'import json,sys,pathlib,simcase',
      'from simcase import Document, run',
      's=run(Document.from_dict(json.loads(sys.stdin.read())),False).summary()',
      'p=s["mode_postprocessing"]',
      'ob=s["open_boundary"][0]',
      'print(json.dumps({"te":p["te_polarization_fraction"]["values"][0],"area":p["effective_area"]["values"][0],"region":p["integration_region"],"ng":s["group_index"]["re"][0],"static":str(pathlib.Path(simcase.__file__).parent/"studio"/"static"),',
      '"schema":ob["schema"],"searches":ob["searches"],"candidates":len(ob["candidates"]),"duplicates":sum("duplicate_of" in c for c in ob["candidates"]),"selected":len(ob["selected_candidates"]),',
      '"listed":sorted({c["search"] for c in ob["candidates"] if "duplicate_of" not in c and c["candidate"] not in ob["selected_candidates"]})}))'].join('\n')],
      {input: JSON.stringify(templateDoc), encoding: 'utf8', maxBuffer: 1 << 26, env: {...process.env, OPENBLAS_NUM_THREADS: '1', OMP_NUM_THREADS: '1', MKL_NUM_THREADS: '1'}});
    assert.equal(templateEngine.status, 0, templateEngine.stderr);
    const tEngine = JSON.parse(templateEngine.stdout), pageModes = await import(pathToFileURL(join(tEngine.static, 'workspace-modes.mjs')).href);
    const expectedTemplate = {pol: tEngine.te.map(f => `${pageModes.polarizationWord(f)} · ${pageModes.polarizationShare(f)}`), area: tEngine.area.map(pageModes.areaText), ng: tEngine.ng.map(g => g.toFixed(4))};
    stage('OB template, engine on this machine', {...expectedTemplate, region: tEngine.region});
    assert.equal(tEngine.region, 'physical_window');
    assert.deepEqual({pol: template.pol.map(([text]) => text), area: template.area, ng: template.ng}, expectedTemplate);
    assert.deepEqual(template.pol.map(([, title]) => title), ['TE = share of |E_x|² in |E_x|² + |E_y|², x horizontal, over the 3 × 2.4 µm window, PML excluded', 'TE = share of |E_x|² in |E_x|² + |E_y|², x horizontal, over the 3 × 2.4 µm window, PML excluded']);
    assert.deepEqual(template.pol.map(([text]) => text.split(' · ')[0]), ['TE-like', 'TM-like']);
    assert.ok(template.areaTitles.every(t => t === 'Effective area over the 3 × 2.4 µm window, PML excluded. For a strongly leaking mode it depends on the window.'), JSON.stringify(template.areaTitles));
    assert.ok(template.ngTitles.every(t => /: Re n_g is shown; Im n_g -?\d\.\d{2}e[-+]\d+\. At the default mesh n_g is about 5e-3 low in the slab check; the error comes from n_eff and shrinks when the core mesh is refined\.$/.test(t)), JSON.stringify(template.ngTitles));
    assert.ok(template.neff.every(t => /^\d\.\d{8} [+−] \d\.\d{2}e-\d+i$/.test(t)), 'n_eff with its Im part');
    // both modes found again by the per-mode check. Below the display floor with check losses under
    // 0.05 dB/cm: no verdict (decided after the TM-like result 0.00480 -> 0.01706 dB/cm, registered as
    // independent; the engine gives 0.0048 and below for both, and 0.017 at most on the check)
    assert.deepEqual(template.check, [['unresolved', 'PML check: no leakage resolved (both solves below 0.05 dB/cm)'], ['unresolved', 'PML check: no leakage resolved (both solves below 0.05 dB/cm)']]);
    assert.equal(template.note, 'Loss includes material absorption (k) and leakage into the PML of the open boundary. Leakage depends on what lies outside the window: shapes touching an open edge continue through the PML.');
    // pre-registered (P2): 32 searched, 2 shown, 30 other candidates, none with a field view. Slice T2
    // (pre-registered): 32 near 2.46 and 16 near 1.95; the list leaves out the 2 shown and the
    // candidates both searches found, counted in the title, as the engine run of the same document
    // on this machine records them
    assert.deepEqual([tEngine.schema, tEngine.searches.map(x => [x.search, x.target_effective_index, x.search_mode_count]), tEngine.selected],
      ['openphysics.pml-candidates/3', [[1, 2.46, 32], [2, 1.95, 16]], 2]);
    assert.equal(tEngine.candidates, tEngine.searches[0].candidate_count + tEngine.searches[1].candidate_count);
    const otherCount = tEngine.candidates - 2 - tEngine.duplicates;
    stage('OB template candidates, engine on this machine', {candidates: tEngine.candidates, duplicates: tEngine.duplicates, other: otherCount});
    assert.deepEqual([template.candidates.summary, template.candidates.rows, template.candidates.controls],
      [`Other candidates (${otherCount}) — not shown as modes` + (tEngine.duplicates ? ` · ${tEngine.duplicates} found by both searches` : ''), otherCount, 0]);
    assert.deepEqual(template.candidates.head, ['Candidate', 'Search', 'n_eff', 'Physical share', 'Reason']);
    // the searches of the listed candidates, as the engine's record gives them (for the template every
    // candidate of the search near 1.95 repeats one of the search near 2.46: 16 duplicates)
    assert.deepEqual(template.candidates.searches, tEngine.listed.map(k => 'near ' + ['2.46', '1.95'][k - 1]).sort());
    await obOverflow('Results, open run');

    // 5. Save: the project file (P3) holds the workspace model as a session of version 10 with the
    // run's open boundary and PML check
    const obFiles = async () => (await readdir(obDownloads)).filter(n => n.endsWith('.json'));
    // File › Save: the name dialog the first time, then the remembered name; the new download's name and text
    // (a download under a name already there may replace it: a new file or a new modification time)
    const obStamps = async () => Object.fromEntries(await Promise.all((await obFiles()).map(async n => [n, (await stat(join(obDownloads, n))).mtimeMs])));
    const obSave = async label => {
      const before = await obStamps(); await ob.click('#save-session'); let saved = null;
      for (let i = 0; i < 600 && !saved; i++) {
        if (await ob.eval("!!document.getElementById('save-name-dialog')?.open")) await ob.click('#save-name-download');
        const now = await obStamps(); saved = Object.keys(now).find(n => before[n] !== now[n]) ?? null; if (!saved) await sleep(100);
      }
      assert.ok(saved, label + ': downloaded; ' + await obText('#file-status') + ' · ' + JSON.stringify(await obFiles())); await sleep(500);
      return {name: saved, text: await readFile(join(obDownloads, saved), 'utf8')};
    };
    const workspaceSession = text => JSON.parse(text).models.find(m => m.kind === 'workspace').session;
    const saved = (await obSave('OB first save')).name;
    const v10 = workspaceSession(await readFile(join(obDownloads, saved), 'utf8'));
    stage('OB version 10 saved', {file: saved, version: v10.version, settings: v10.runs[0].settings.pml, check: v10.runs[0].pml_check, candidates: v10.runs[0].open_boundary.candidates.length});
    assert.deepEqual([v10.version, v10.runs[0].settings.adapter, v10.runs[0].settings.boundary], [10, 'optical-shapes-v9', 'PML']);
    assert.deepEqual(v10.runs[0].settings.pml, {thickness: '1000 nm', open_edges: ['left', 'right', 'bottom', 'top'], target: '2.460'});
    // slice T2: the run's settings are P2's; its record is the engine's /3 of both searches
    assert.equal(v10.runs[0].pml_check.pml_strength, 6); assert.equal(v10.runs[0].pml_check.paired.length, 2);
    assert.equal(v10.runs[0].open_boundary.schema, 'openphysics.pml-candidates/3'); assert.equal(v10.runs[0].open_boundary.candidates.length, tEngine.candidates);

    // 6. the closed template run, and Compare: matched on the physical windows (slice P3) and the per-side words
    await toTree('Optical modes', "!!document.getElementById('outer-boundary')");
    await ob.click('input[name="outer-boundary"][value="closed"]'); await ob.until("!document.getElementById('target-number')", 'OB Closed chosen');
    await obRun();
    const closedView = await resultsView(); stage('OB template, closed', closedView);
    assert.equal(closedView.caption, 'Computed modes'); assert.equal(closedView.head[3], 'Absorption loss (dB/cm)');
    assert.match(closedView.note, / For leakage, choose Open boundary in Physics › Optical modes\.$/);
    // Run 1 is the open run, Run 2 the closed one: A closed, B open
    const jobs = await ob.eval("Object.fromEntries([...document.querySelectorAll('.run-item')].map(e=>[Number(/Run (\\d+)/.exec(e.textContent)?.[1]),e.dataset.run]))");
    await ob.click('nav [data-page=Compare]'); await ob.until("!!document.getElementById('compare-a')", 'OB Compare');
    await ob.choose('#compare-a', jobs[2]); await ob.choose('#compare-b', jobs[1]); await ob.until("!!document.getElementById('compare-neff')", 'OB Compare table');
    await obSize(1440, 900); await sleep(300);
    const compared = await ob.eval(`(()=>{const t=document.getElementById('compare-neff'),box=t.closest('.compare-table-scroll');return {
      sides:[...t.tHead.rows[1].cells].map(c=>c.dataset.column),top:[...t.tHead.rows[0].cells].map(c=>c.textContent),matched:[...t.tBodies[0].rows].filter(r=>r.dataset.match).map(r=>[r.dataset.match,Number(r.querySelector('[data-overlap]').dataset.overlap)]),
      unmatched:[...t.tBodies[0].rows].filter(r=>!r.dataset.match).length,runs:[...document.querySelectorAll('#compare-table-runs [data-side]')].map(e=>e.textContent),
      lossNote:document.getElementById('compare-loss-note')?.textContent,matchNote:document.getElementById('compare-match-note')?.textContent,
      lossA:[...t.querySelectorAll('[data-loss-a]')].map(c=>c.textContent),lossB:[...t.querySelectorAll('[data-loss-b]')].map(c=>c.textContent),
      slack:box.clientWidth-Math.ceil(t.getBoundingClientRect().width),comparing:document.getElementById('tree').parentElement.classList.contains('comparing')}})()`);
    stage('OB Compare closed vs open', compared);
    // Slice P3: matching with an open run is on, on the physical windows. P2's blind V13 (eta >= 0.99)
    // failed at 0.9903 / 0.9875; the cause was the default mesh's discretization error, and the checks
    // registered after that result pass (V13a-c, tests/simcase/test_open_boundary_mode_identity.py).
    // V13b in the page: both modes paired with their own counterpart by Studio's rule
    assert.deepEqual(compared.matched.map(([id]) => id), ['0:0', '1:1']); assert.equal(compared.unmatched, 0);
    assert.ok(compared.matched.every(([, eta]) => eta >= 0.8), JSON.stringify(compared.matched));
    assert.equal(compared.matchNote, 'Matched by field overlap ≥ 0.8 on a common grid. A low overlap means the mode changed shape between designs.');
    assert.ok(compared.sides.includes('Absorption loss A (dB/cm)') && compared.sides.includes('Loss B (dB/cm)'), JSON.stringify(compared.sides));
    assert.equal(compared.lossNote, 'A counts material absorption only; B also counts leakage. Their difference is not a leakage loss.');
    assert.ok(compared.runs[0].includes(' · closed · ') && compared.runs[1].includes(' · open (PML 1 µm) · '), JSON.stringify(compared.runs));
    assert.deepEqual(compared.lossA, ['0 dB/cm', '0 dB/cm']); assert.deepEqual(compared.lossB, ['< 0.01 dB/cm', '< 0.01 dB/cm']);
    // O2 (round 13): at 1440 × 900 the Compare table keeps at least 24 px to spare
    assert.equal(compared.comparing, true); assert.ok(compared.slack >= 24, `OB Compare: ${compared.slack} px to spare at 1440`);
    await ob.screenshot('open-boundary-compare-1440');
    await obOverflow('Compare closed vs open');

    // 7. the leakage case built in Geometry: a silicon substrate x −1500, y −1200, 3000 × 700 nm under the core (BOX 500 nm).
    // The group index ticked for the template run (slice P3: it stays on with Open) is turned off first,
    // so that the page's document is P1's byte for byte
    await toTree('Optical modes', "!!document.getElementById('group-index-check')"); await ob.click('#group-index-check');
    assert.equal((await control('checkbox', 'Also compute group index (3 solves)')).checked, 'false');
    await toTree('Geometry', "!!document.querySelector('#shape-w')");
    await ob.click('[data-add-shape=rect]'); await ob.until("document.querySelectorAll('.shape-item').length===2", 'OB substrate added');
    await ob.type('#shape-name', 'Substrate'); await ob.choose('#shape-material', 'Silicon');
    // round 16 (S2): T16's entry order, typed key by key (one input event per character): Left x
    // −1500, Bottom y −1200, Width 3000 (centred it would leave the window, so Left x is kept),
    // Height 700. A Width once refused is tried again when Left x changes.
    const typeKeys = async (selector, text) => {
      await ob.onElement('function(selector){const e=this.querySelector(selector);e.focus();e.select();return true}', selector);
      for (const ch of String(text)) await ob.call('Input.insertText', {text: ch});
      await ob.onElement('function(selector){this.querySelector(selector).blur();return true}', selector); await sleep(150);
    };
    const obStatus = () => ob.eval("document.getElementById('file-status').textContent");
    await typeKeys('#shape-x', -1500); await typeKeys('#shape-y', -1200); await typeKeys('#shape-w', 3000);
    const widthNotice = await obStatus();
    await typeKeys('#shape-h', 700);
    const substrate = await ob.eval("['shape-x','shape-y','shape-w','shape-h'].map(id=>document.getElementById(id).value)");
    const substrateInvalid = await ob.eval("[...document.querySelectorAll('#inspector input[aria-invalid=true]')].map(e=>e.id)");
    stage('OB substrate', {substrate, widthNotice, invalid: substrateInvalid}); assert.deepEqual(substrate, ['-1500', '-1200', '3000', '700']);
    assert.ok(widthNotice.startsWith('Width set to 3000 nm. Left x kept at −1500 nm: centred, the shape would leave the window. '), widthNotice);
    assert.deepEqual(substrateInvalid, []);
    await toTree('Optical modes', "!!document.getElementById('outer-boundary')");
    await ob.click('input[name="outer-boundary"][value="open"]'); await ob.until("!!document.getElementById('target-number')", 'OB leakage Open');
    // the document the browser sends is build("strip_substrate", 2) (tests/simcase/open_boundary_fixtures.py), byte
    // for byte: P1's strip over a substrate with the second search near 1.95 (slice T2; the fixture is P1's
    // optical-document-strip-substrate-open.json with that key only, tests/simcase/test_studio_open_boundary_p2.py)
    const leakDoc = await solverDocument();
    const p1Leak = await readFile(new URL('../../tests/simcase/studio_session_fixtures/optical-document-strip-substrate-open-searches.json', import.meta.url), 'utf8');
    stage('OB leakage document', {domain: leakDoc.geometry.domain, shapes: leakDoc.geometry.shapes.length, same: JSON.stringify(leakDoc) === p1Leak});
    assert.equal(JSON.stringify(leakDoc), p1Leak, 'the UI-built leakage document is P1\'s strip over a substrate with both searches');
    // the PML check on (one solve per mode): pre-registered, both modes found again and PML-independent,
    // the loss changing by less than 2 %
    await toTree('Study', "!!document.getElementById('pml-check')");
    if (!(await ob.eval("document.getElementById('pml-check').checked"))) await ob.click('#pml-check');
    const leakSeconds = await obRun();
    await ob.until("document.querySelectorAll('[data-pml-check]').length===2&&!document.getElementById('run-optical').disabled", 'OB leakage PML check', 600000);
    const leak = await resultsView(); stage('OB leakage case', {...leak, seconds: leakSeconds});
    assert.deepEqual(leak.check.map(([status]) => status), ['independent', 'independent']);
    for (const [, words] of leak.check) { const m = /^PML check: loss changes (\d+(?:\.\d+)?) %$/.exec(words); assert.ok(m && Number(m[1]) < 2, words); }
    // Re-registered after the result (decision 2026-11-23-openphysics-pml-p2-browser-values-per-platform).
    // As registered, the stage asserted the Linux-container values 2.441263 / 29.15 dB/cm and 1.772790 /
    // 1006 dB/cm on every platform; the pre-registration wrongly assumed platform-independent literals.
    // CI failed on them: ubuntu-24.04 TE Re 2.44128662 (dRe 2.3e-5), macos-15 TE "29.18 dB/cm" (+0.10 %)
    // and Re 2.44113899. Now the strings on screen must equal, exactly, those of the engine run of P1's
    // document (the one the page sends, byte for byte, checked above) on this machine, formatted by the
    // page's own formatter (workspace-open-run.mjs of the installed simcase). Slice T2: the expected
    // strings move with the document (both searches).
    const engineStrings = spawnSync(args.python, ['-c', [
      'import json,sys,pathlib,simcase',
      'from simcase import Document, run',
      's=run(Document.from_dict(json.loads(sys.stdin.read())),False).summary()',
      'ob=s["open_boundary"][0]["candidates"];re=s["effective_index"]["re"][0];im=s["effective_index"]["im"][0]',
      'st=[next((c.get("attenuation_status") for c in ob if c["selected"] and c["effective_index"]["re"]==a and c["effective_index"]["im"]==b),None) for a,b in zip(re,im)]',
      'print(json.dumps({"re":re,"im":im,"status":st,"static":str(pathlib.Path(simcase.__file__).parent/"studio"/"static")}))'].join('\n')],
      {input: p1Leak, encoding: 'utf8', maxBuffer: 1 << 26, env: {...process.env, OPENBLAS_NUM_THREADS: '1', OMP_NUM_THREADS: '1', MKL_NUM_THREADS: '1'}});
    assert.equal(engineStrings.status, 0, engineStrings.stderr);
    const engine = JSON.parse(engineStrings.stdout);
    const pageFormat = await import(pathToFileURL(join(engine.static, 'workspace-open-run.mjs')).href);
    const expectedLeak = {neff: engine.re.map((r, i) => pageFormat.openIndexText(r, engine.im[i])), loss: engine.re.map((_, i) => pageFormat.openLoss(engine.im[i], 1.55e-6, engine.status[i]).text)};
    stage('OB leakage case, engine on this machine', {...expectedLeak, linuxContainer: {neff: ['2.44126325 + 8.28e-5i', '1.77279036 + 2.86e-3i'], loss: ['29.15 dB/cm', '1006 dB/cm']}});
    assert.deepEqual({neff: leak.neff, loss: leak.loss}, expectedLeak, 'the screen strings are the engine run of the same document on this machine');
    assert.ok(leak.lossTitles.every(t => t.endsWith('At the default mesh this loss is about 3 % above the converged value (TE-like +2.8 %, TM-like +1.8 % on a strip over a substrate).')));
    // round 16 (S8): the multi-shape label in the run list, the Results status line and the Compare
    // headings, with no page overflow at 390 × 844
    {
      const label = 'Core 500 × 220 + Substrate 3000 × 700 nm · Silicon', over = () => ob.eval('document.documentElement.scrollWidth-document.documentElement.clientWidth');
      await obSize(390, 844, true);
      const results = {item: await ob.eval("document.querySelector('.run-item[aria-pressed=true]')?.textContent??''"), status: await ob.eval("document.getElementById('status').textContent"), over: await over()};
      await ob.click('nav [data-page=Compare]'); await ob.until("!!document.getElementById('compare-b')", 'S8 Compare');
      await ob.eval("(()=>{const s=document.getElementById('compare-b');s.value=s.options[s.options.length-1].value;s.dispatchEvent(new Event('change'));return true})()");
      await ob.until("!!document.querySelector('.compare-grid article h3')", 'S8 Compare headings');
      const compare = {headings: await ob.eval("[...document.querySelectorAll('.compare-grid article h3, #compare-table-runs [data-side]')].map(e=>e.textContent)"), picker: await ob.eval("document.getElementById('compare-b').selectedOptions[0].textContent"), over: await over()};
      stage('S8 multi-shape label at 390 × 844', {results, compare});
      assert.ok(results.item.includes('Run ') && results.item.includes(' · open (PML 1 µm) · ' + label + ' · '), results.item);
      assert.equal(results.over <= 0, true, `Results overflows by ${results.over}px`);
      assert.ok(compare.headings.some(h => h.includes(label)), JSON.stringify(compare.headings)); assert.ok(compare.picker.includes('open (PML 1 µm) · ' + label), compare.picker);
      assert.equal(compare.over <= 0, true, `Compare overflows by ${compare.over}px`);
      await ob.click('nav [data-page=Results]'); await ob.until("!!document.getElementById('modes-table')", 'S8 back to Results'); await obSize(1280, 800);
    }

    // V15 with P3 (pre-registered by the coordinator): the project file with the open leakage run and
    // its PML check, saved, opened and saved again, follows V-P1: (a) save 1 -> open -> save 2 differ
    // only in savedAt, the workspace entry's bytes and digest and each run's origin and digest; (b)
    // save 2 -> open -> save 3 are byte-identical but for savedAt; and the run's n_eff, loss and check
    // strings read the same after the open
    const obOpen = async (path, label) => {
      await ob.eval("document.getElementById('file-status').textContent=''");
      const {root} = await ob.call('DOM.getDocument'); const {nodeId} = await ob.call('DOM.querySelector', {nodeId: root.nodeId, selector: '#session-file'});
      await ob.call('DOM.setFileInputFiles', {nodeId, files: [path]});
      const end = Date.now() + 60000;
      while (!(await ob.eval("/^Opened project /.test(document.getElementById('file-status').textContent)"))) {
        assert.ok(Date.now() < end, label + ': ' + await obText('#file-status'));
        if (await ob.eval("!!document.getElementById('leave-confirm')?.open")) await ob.click('#leave-go');
        else if (await ob.eval("!!document.getElementById('load-confirm')?.open")) await ob.click('#confirm-load');
        await sleep(150);
      }
    };
    const differing = (x, y, path = '') => {
      if (Object.is(x, y)) return [];
      if (x && y && typeof x === 'object' && typeof y === 'object' && Array.isArray(x) === Array.isArray(y)) {
        const keys = Array.isArray(x) ? (x.length === y.length ? [...x.keys()] : null) : [...new Set([...Object.keys(x), ...Object.keys(y)])];
        if (keys) return keys.flatMap(k => differing(x[k], y[k], Array.isArray(x) ? `${path}[${k}]` : `${path}.${k}`));
      }
      return [path];
    };
    const withoutTime = text => String(text).replace(/"savedAt":"[^"]*"/, '"savedAt":""');
    const first = await obSave('OB V15 save 1');
    await obOpen(join(obDownloads, first.name), 'OB V15 open 1');
    const second = await obSave('OB V15 save 2');
    const w = JSON.parse(first.text).models.findIndex(m => m.kind === 'workspace'), runCount = workspaceSession(first.text).runs.length;
    const paths = differing(JSON.parse(first.text), JSON.parse(second.text));
    const expectedPaths = ['.savedAt', `.models[${w}].bytes`, `.models[${w}].digest`, ...Array.from({length: runCount}, (_, i) => [`.models[${w}].session.runs[${i}].origin`, `.models[${w}].session.runs[${i}].digest`]).flat()];
    await obOpen(join(obDownloads, second.name), 'OB V15 open 2');
    const third = await obSave('OB V15 save 3');
    await ob.click('nav [data-page=Results]'); await ob.until("!!document.getElementById('modes-table')", 'OB V15 Results');
    const reopened = await resultsView();
    stage('OB V15 project round trip', {paths, runs: runCount, versions: [workspaceSession(first.text).version, workspaceSession(third.text).version], neff: reopened.neff, loss: reopened.loss, check: reopened.check});
    assert.deepEqual([...paths].sort(), [...expectedPaths].sort(), 'V-P1 (a) with the open run');
    assert.equal(withoutTime(third.text), withoutTime(second.text), 'V-P1 (b): byte-identical but for savedAt');
    assert.deepEqual(workspaceSession(third.text).runs.map(r => r.origin), Array(runCount).fill('imported'));
    assert.deepEqual([reopened.neff, reopened.loss, reopened.check], [leak.neff, leak.loss, leak.check], 'the open run reads the same after the open');
    assert.equal(leak.found, 'Found 2 of 2 modes near n_eff 2.46 and 1.95. Move Search near n_eff to find other modes.');

    // W1 through the builder (slice T2, pre-registered): the strip over a substrate asking for 8 modes
    // returns all three modes, the one near the cladding index included (1.4864 + 7.92e-3i), with the
    // strings of the engine run of the same document on this machine
    await toTree('Optical modes', "!!document.getElementById('target-number')"); await ob.type('#mode-count-number', 8);
    await toTree('Study', "!!document.getElementById('pml-check')"); if (await ob.eval("document.getElementById('pml-check').checked")) await ob.click('#pml-check');
    const eightDoc = await solverDocument();
    assert.deepEqual({...eightDoc, physics: {em1: {...eightDoc.physics.em1, mode_count: 2}}}, JSON.parse(p1Leak));
    const eightSeconds = await obRun();
    const eight = await resultsView();
    const eightEngine = spawnSync(args.python, ['-c', [
      'import json,sys',
      'from simcase import Document, run',
      's=run(Document.from_dict(json.loads(sys.stdin.read())),False).summary()',
      'ob=s["open_boundary"][0]["candidates"];re=s["effective_index"]["re"][0];im=s["effective_index"]["im"][0]',
      'st=[next((c.get("attenuation_status") for c in ob if c["selected"] and c["effective_index"]["re"]==a and c["effective_index"]["im"]==b),None) for a,b in zip(re,im)]',
      'print(json.dumps({"re":re,"im":im,"status":st}))'].join('\n')],
      {input: JSON.stringify(eightDoc), encoding: 'utf8', maxBuffer: 1 << 26, env: {...process.env, OPENBLAS_NUM_THREADS: '1', OMP_NUM_THREADS: '1', MKL_NUM_THREADS: '1'}});
    assert.equal(eightEngine.status, 0, eightEngine.stderr);
    const e8 = JSON.parse(eightEngine.stdout), keep8 = e8.re.map((r, i) => r > 1.45 ? i : -1).filter(i => i >= 0);
    const expectedEight = {neff: keep8.map(i => pageFormat.openIndexText(e8.re[i], e8.im[i])), loss: keep8.map(i => pageFormat.openLoss(e8.im[i], 1.55e-6, e8.status[i]).text)};
    stage('W1 strip over a substrate, 8 modes', {neff: eight.neff, loss: eight.loss, found: eight.found, engine: expectedEight, seconds: eightSeconds});
    assert.deepEqual({neff: eight.neff, loss: eight.loss}, expectedEight, 'the screen strings are the engine run of the same document on this machine');
    assert.equal(eight.neff.length, 3, JSON.stringify(eight.neff));
    assert.equal(eight.found, 'Found 3 of 8 modes near n_eff 2.46 and 1.95. Move Search near n_eff to find other modes.');
    const cladding = eight.neff.map(t => /^(\d\.\d{8}) ([+−]) (\d\.\d{2}e-\d+)i$/.exec(t)).map(m => ({re: Number(m[1]), im: (m[2] === '−' ? -1 : 1) * Number(m[3])}));
    assert.deepEqual(eight.neff.slice(0, 2), leak.neff, 'TE-like and TM-like first, as with 2 modes');
    assert.ok(Math.abs(cladding[2].re - 1.4864) <= 5e-4 && Math.abs(cladding[2].im / 7.92e-3 - 1) <= 0.05, JSON.stringify(cladding));

    // 8. Search near n_eff lowered to 1.600 with 4 modes finds the mode near the cladding index
    // (pre-registered: within 5e-4 of Re 1.4864 and 5 % of Im 7.92e-3, about 2789 dB/cm)
    await toTree('Optical modes', "!!document.getElementById('target-number')"); await ob.type('#target-number', '1.6'); await ob.type('#mode-count-number', 4);
    await toTree('Study', "!!document.getElementById('pml-check')"); if (await ob.eval("document.getElementById('pml-check').checked")) await ob.click('#pml-check');
    const lowSeconds = await obRun();
    const low = await resultsView(); stage('OB leakage case, search near 1.600', {...low, seconds: lowSeconds});
    const near = low.neff.map((t, i) => [t, low.loss[i]]).map(([t, loss]) => { const m = /^(\d\.\d{8}) ([+−]) (\d\.\d{2}e-\d+)i$/.exec(t); return {re: Number(m[1]), im: (m[2] === '−' ? -1 : 1) * Number(m[3]), loss}; })
      .find(m => Math.abs(m.re - 1.4864) <= 5e-4);
    assert.ok(near, 'the near-cladding mode is shown: ' + JSON.stringify(low.neff));
    assert.ok(Math.abs(near.im / 7.92e-3 - 1) <= 0.05, JSON.stringify(near)); assert.ok(Math.abs(Number(near.loss.split(' ')[0]) / 2789 - 1) <= 0.05, JSON.stringify(near));
    // slice T2: the search near 1.600 is paired with one near (1.600 + 1.444) / 2 = 1.52
    assert.match(low.found, /^Found \d of 4 modes near n_eff 1\.60 and 1\.52\. Move Search near n_eff to find other modes\.$/);
    // review: choosing the optical model again clears the PML check option with the open boundary
    await toTree('Study', "!!document.getElementById('pml-check')"); await ob.click('#pml-check'); assert.equal(await ob.eval("document.getElementById('pml-check').checked"), true);
    await ob.click('nav [data-page=Applications]'); await ob.until("!!document.querySelector('[data-template=optical]')", 'OB Library');
    await ob.click('[data-template=optical]'); await ob.until("!!document.querySelector('#shape-w')", 'OB optical template again');
    await toTree('Optical modes', "!!document.getElementById('outer-boundary')"); assert.equal((await control('radio', 'Closed window (PEC)')).checked, 'true');
    await ob.click('input[name="outer-boundary"][value="open"]'); await toTree('Study', "!!document.getElementById('pml-check')");
    const afterReset = await ob.eval("document.getElementById('pml-check').checked"); stage('OB the template clears the PML check option', {afterReset});
    assert.equal(afterReset, false);

    // Amendment (a) of slice T2 (pre-registered): a version 10 file written by P2's Studio (f8ece10;
    // runs of one search, records /2) opens with P2's words, and its run's inputs make the document
    // of both searches. The words are those f8ece10's page showed for the strip over a substrate.
    {
      await ob.eval("document.getElementById('file-status').textContent=''");
      const {root} = await ob.call('DOM.getDocument'); const {nodeId} = await ob.call('DOM.querySelector', {nodeId: root.nodeId, selector: '#session-file'});
      await ob.call('DOM.setFileInputFiles', {nodeId, files: [fileURLToPath(new URL('../../tests/simcase/studio_session_fixtures/optical-v10-open-f8ece10.json', import.meta.url))]});
      const end = Date.now() + 60000;
      while (!(await ob.eval("/^Opened /.test(document.getElementById('file-status').textContent)"))) {
        assert.ok(Date.now() < end, 'P2 file: ' + await obText('#file-status'));
        if (await ob.eval("!!document.getElementById('leave-confirm')?.open")) await ob.click('#leave-go');
        else if (await ob.eval("!!document.getElementById('load-confirm')?.open")) await ob.click('#confirm-load');
        await sleep(150);
      }
      await ob.click('nav [data-page=Results]'); await ob.until("!!document.getElementById('modes-table')", 'P2 file Results');
      const p2 = await resultsView(); stage('T2 (a) a P2 file opened', {found: p2.found, neff: p2.neff, loss: p2.loss, check: p2.check, candidates: p2.candidates});
      assert.equal(p2.found, 'Found 2 of 2 modes near n_eff 2.460. Move Search near n_eff (Physics › Optical modes) to find other modes.');
      assert.deepEqual([p2.neff, p2.loss, p2.check], [['2.44126325 + 8.28e-5i', '1.77279036 + 2.86e-3i'], ['29.15 dB/cm', '1006 dB/cm'],
        [['independent', 'PML check: loss changes 0.0038 %'], ['independent', 'PML check: loss changes 0.016 %']]]);
      assert.deepEqual([p2.candidates.summary, p2.candidates.rows, p2.candidates.head, p2.candidates.searches], ['Other candidates (30) — not shown as modes', 30, ['Candidate', 'n_eff', 'Physical share', 'Reason'], null]);
      if (await ob.eval("!!document.getElementById('restore-run-input')")) { await ob.click('#restore-run-input'); await sleep(300); }
      const again = await solverDocument(); stage('T2 (a) the P2 run\'s inputs, run again', {target: again.physics.em1.target_effective_index, searches: again.physics.em1.pml.pml_additional_searches});
      assert.equal(JSON.stringify(again), p1Leak, 'running the P2 run again sends the document of both searches');
    }
    await browserPage.call('Target.disposeBrowserContext', {browserContextId});
  }

  // R17 (round 17, pre-registered), in a browser context of its own: stable run numbers over the
  // six-run limit and the dropped-run message (U2), the slow options beside Run study (U3), the
  // boundary words (U5), the Compare pickers' names (U9), the closed-window modes in the substrate
  // (U1), the status line's shape names (U14) and the best overlap of unmatched rows with O2's 24 px (U4).
  {
    const devtools = await (await fetch(`http://127.0.0.1:${debugPort}/json/version`)).json();
    const browserPage = new Page(devtools.webSocketDebuggerUrl); await browserPage.ready;
    const {browserContextId} = await browserPage.call('Target.createBrowserContext');
    const {targetId} = await browserPage.call('Target.createTarget', {url: 'about:blank', browserContextId});
    const r = new Page(`ws://127.0.0.1:${debugPort}/devtools/page/${targetId}`); await r.ready;
    await r.call('Runtime.enable'); await r.call('Page.enable'); await r.call('DOM.enable'); await r.call('Accessibility.enable');
    const rSize = async (width, height, mobile = false) => { await r.call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile}); await sleep(300); };
    await rSize(1280, 800);
    const rText = selector => r.onElement('function(selector){const e=this.querySelector(selector);return e?e.textContent:null}', selector);
    const rOverflow = async tag => {
      for (const [width, height, mobile] of [[1440, 900, false], [390, 844, true]]) {
        await rSize(width, height, mobile);
        const over = await r.eval('document.documentElement.scrollWidth-document.documentElement.clientWidth');
        stage('R17 overflow ' + tag, {width, height, over}); assert.ok(over <= 0, `${tag} at ${width} × ${height} overflows by ${over}px`);
      }
      await rSize(1280, 800);
    };
    const rTree = async (name, ready) => { await r.click('nav [data-page=Model]'); await sleep(200); await r.clickTreeItem(name); await r.until(ready, name); };
    const rRun = async () => {
      await r.until("!document.getElementById('run-optical').disabled", 'R17 Run enabled');
      const before = await r.eval("JSON.stringify([...document.querySelectorAll('.run-item')].map(b=>b.textContent))");
      await r.click('#run-optical');
      // round 19 (Y4): with six runs kept, Run study asks before dropping one; these stages answer Run
      if (await r.eval("!!document.getElementById('run-drop-confirm')?.open")) await r.click('#run-drop-confirm-run');
      await r.until(`JSON.stringify([...document.querySelectorAll('.run-item')].map(b=>b.textContent))!==${JSON.stringify(before)}&&!document.getElementById('run-optical').disabled&&document.getElementById('run-optical').textContent==='Run study'&&!!document.getElementById('modes-table')`, 'R17 run', 300000);
    };
    const pressEnter = async () => { for (const type of ['keyDown', 'keyUp']) await r.call('Input.dispatchKeyEvent', {type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, text: type === 'keyDown' ? '\r' : undefined}); await sleep(150); };
    const nameRun = async name => { await r.onElement('function(selector){const e=this.querySelector(selector);e.focus();e.select();return true}', '#run-name-input'); await r.call('Input.insertText', {text: name}); await pressEnter(); };
    const runItems = () => r.eval("[...document.querySelectorAll('.run-item')].map(b=>b.textContent)");
    await r.call('Page.navigate', {url: base + '/workspace'});
    await r.until("/^Connected/.test(document.getElementById('connection-status').textContent)&&!!document.querySelector('[data-template=optical]')", 'R17 connected start page');
    await r.click('[data-template=optical]'); await r.until("!!document.querySelector('#shape-w')", 'R17 optical template');
    // U5: the workspace note and the closed Study panel
    const u5 = {note: await rText('.workspace > .note')};
    await rTree('Study', "!!document.querySelector('#inspector h2')"); u5.study = await r.eval("document.getElementById('inspector').textContent");
    stage('R17 U5 boundary words', {note: u5.note});
    assert.equal(u5.note, 'Optical cross section uses the submitted geometry, in nm. Shapes, materials, wavelength and core mesh editable; window fixed; outer boundary chosen in Physics › Optical modes.');
    assert.ok(u5.study.includes('The window is fixed; the outer boundary is chosen in Physics › Optical modes.'), u5.study); assert.ok(!u5.study.includes('Window and boundaries are fixed.'));
    // U3: the group index option, ticked, is named beside Run study; cleared, the line no longer names it
    await rTree('Optical modes', "!!document.getElementById('group-index-check')"); await r.click('#group-index-check');
    const u3 = {on: await r.eval("({text:document.getElementById('run-options').textContent,hidden:document.getElementById('run-options').hidden})")};
    await rOverflow('U3 slow options');
    await r.click('#group-index-check'); u3.off = await r.eval("({text:document.getElementById('run-options').textContent,hidden:document.getElementById('run-options').hidden})");
    stage('R17 U3 slow options', u3);
    // round 18 (X2): the line is always there and names the whole run; the group index with its solves
    assert.equal(u3.on.hidden, false); assert.ok(u3.on.text.startsWith('Closed window · group index on (3 solves) · '), u3.on.text);
    assert.equal(u3.off.hidden, false); assert.ok(u3.off.text.startsWith('Closed window · ') && !u3.off.text.includes('group index'), u3.off.text);
    // U2: seven runs of the template (core mesh 30, 32, …, 42 nm): the seventh drops Run 1 and
    // renumbers nothing; Messages names it
    for (let i = 0; i < 7; i++) {
      if (i) { await rTree('Mesh', "!!document.getElementById('core-mesh-number')"); await r.type('#core-mesh-number', 30 + 2 * i); }
      await rRun();
    }
    const u2 = {items: await runItems(), message: await rText('#file-status'), status: await rText('#status')};
    stage('R17 U2 seven runs', u2);
    assert.deepEqual(u2.items.map(t => t.split(' · ')[0]), ['Run 7', 'Run 6', 'Run 5', 'Run 4', 'Run 3', 'Run 2']);
    assert.ok(u2.message.endsWith(' Run 1 (500 × 220 nm · 2 modes) was dropped: up to six runs are kept; pin a run to keep it.'), u2.message);
    assert.ok(u2.status.startsWith('Run 7 · '), u2.status);
    // Run 5 and Run 6 named (pinned) on Compare; an eighth run drops Run 2, keeps the pair and says Run 8 is newer
    await r.click('nav [data-page=Results]'); await r.until("!!document.getElementById('modes-table')", 'R17 Results');
    const showRun = async n => { await r.onElement('function(n){const b=[...this.querySelectorAll(".run-item")].find(b=>b.textContent.split(" · ").includes(n));b.click();return true}', 'Run ' + n); await sleep(200); };
    await showRun(5); await nameRun('Design A'); await showRun(6); await nameRun('Design B');
    await r.click('nav [data-page=Compare]'); await r.until("!!document.getElementById('compare-a')", 'R17 Compare');
    await r.choose('#compare-a', await r.eval("[...document.getElementById('compare-a').options].find(o=>o.textContent.startsWith('Run 5 · Design A · ')).value"));
    await r.choose('#compare-b', await r.eval("[...document.getElementById('compare-b').options].find(o=>o.textContent.startsWith('Run 6 · Design B · ')).value"));
    await rTree('Mesh', "!!document.getElementById('core-mesh-number')"); await r.type('#core-mesh-number', 44); await rRun();
    const dropped2 = await rText('#file-status');
    await r.click('nav [data-page=Compare]'); await r.until("!!document.getElementById('compare-newer')", 'R17 Compare newer');
    const u2b = {items: await runItems(), dropped: dropped2, newer: await rText('#compare-newer'),
      options: await r.eval("[...document.getElementById('compare-a').options].map(o=>o.textContent.split(' · ').slice(0,2).join(' · '))"),
      headings: await r.eval("[...document.querySelectorAll('#compare-table-runs [data-side]')].map(s=>s.textContent.split(' · ').slice(0,3).join(' · '))")};
    stage('R17 U2 eighth run', u2b);
    assert.deepEqual(u2b.items.map(t => t.replace('Pinned · ', '').split(' · ')[0]), ['Run 8', 'Run 7', 'Run 6', 'Run 5', 'Run 4', 'Run 3']);
    assert.ok(u2b.dropped.endsWith(' Run 2 (500 × 220 nm · 2 modes) was dropped: up to six runs are kept; pin a run to keep it.'), u2b.dropped);
    assert.equal(u2b.newer, 'Run 8 is newer than this pair · Compare Run 8 with B');
    assert.deepEqual(u2b.headings, ['A · Run 5 · Design A', 'B · Run 6 · Design B']);
    // U9: the pickers are named Run A and Run B; the run number and name fit their visible width
    for (const [width, height, mobile] of [[1440, 900, false], [390, 844, true]]) {
      await rSize(width, height, mobile);
      const pick = await r.eval(`(()=>{const c=document.createElement('canvas').getContext('2d');return ['compare-a','compare-b'].map(id=>{const s=document.getElementById(id),cs=getComputedStyle(s);c.font=cs.font;
        const prefix=s.selectedOptions[0].textContent.split(' · ').slice(0,2).join(' · ');const room=s.clientWidth-parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight)-20;
        return {label:s.getAttribute('aria-label'),title:s.title===s.selectedOptions[0].textContent,prefix,fits:c.measureText(prefix).width<=room,room:Math.round(room)};});})()`);
      stage('R17 U9 Compare pickers', {width, pick});
      assert.deepEqual(pick.map(p => [p.label, p.title, p.fits]), [['Run A', true, true], ['Run B', true, true]], JSON.stringify(pick));
      assert.equal((await r.eval('document.documentElement.scrollWidth-document.documentElement.clientWidth')) <= 0, true);
    }
    await rSize(1280, 800);
    for (const name of ['Run A', 'Run B']) {
      const {result: document} = await r.call('Runtime.evaluate', {expression: 'document'});
      const {nodes} = await r.call('Accessibility.queryAXTree', {objectId: document.objectId, accessibleName: name, role: 'combobox'});
      assert.equal(nodes.filter(n => !n.ignored).length, 1, name);
    }
    // U1 and U14: the T18 structure in a closed window, a silicon substrate x −1500, y −1200, 3000 × 700 nm
    await rTree('Geometry', "!!document.querySelector('#shape-w')");
    await r.click('[data-add-shape=rect]'); await r.until("document.querySelectorAll('.shape-item').length===2", 'R17 substrate added');
    await r.type('#shape-name', 'Substrate'); await r.choose('#shape-material', 'Silicon');
    for (const [id, value] of [['#shape-x', -1500], ['#shape-y', -1200], ['#shape-w', 3000], ['#shape-h', 700]]) await r.type(id, value);
    assert.deepEqual(await r.eval("['shape-x','shape-y','shape-w','shape-h'].map(id=>document.getElementById(id).value)"), ['-1500', '-1200', '3000', '700']);
    await rTree('Mesh', "!!document.getElementById('core-mesh-number')"); await r.type('#core-mesh-number', 30);
    await rRun();
    const u1 = await r.eval(`(()=>{const notes=[...document.querySelectorAll('#modes-table td[data-edge-note]')];return {notes:notes.map(n=>[n.dataset.edgeNote,n.textContent]),
      described:[...document.querySelectorAll('#modes-table tbody th[aria-describedby]')].map(th=>th.textContent),neff:[...document.querySelectorAll('#modes-table [data-neff]')].map(c=>c.textContent)};})()`);
    stage('R17 U1 closed window, substrate', u1);
    assert.deepEqual(u1.notes.map(n => n[0]), ['1', '2']); assert.deepEqual(u1.described, ['Mode 1', 'Mode 2']);
    for (const [mode, text] of u1.notes) {
      const m = /^Mode (\d) is mostly in Substrate \((\d+) % of \|E\|²\), which touches the window edge; its n_eff depends on the closed window\. Use Open boundary, or ask for more modes to reach the core mode\.$/.exec(text);
      assert.ok(m && m[1] === mode && Number(m[2]) > 50, text);
    }
    await rOverflow('U1 Results notes');
    // U14: after an edit the status line names the viewed run's shapes
    await rTree('Optical modes', "!!document.getElementById('wavelength-number')"); await r.type('#wavelength-number', 1540);
    await r.click('nav [data-page=Results]'); await r.until("!!document.getElementById('modes-table')", 'R17 Results after edit');
    const u14 = await rText('#status'); stage('R17 U14 status line', {status: u14});
    assert.ok(u14.startsWith('Run 9 · Core 500 × 220 + Substrate 3000 × 700 nm'), u14);
    await rTree('Optical modes', "!!document.getElementById('wavelength-number')"); await r.type('#wavelength-number', 1550);
    // the template core alone (Run 8) against the substrate run (Run 9): the note for B, the best overlap of each unmatched row
    await r.click('nav [data-page=Compare]'); await r.until("!!document.getElementById('compare-a')", 'R17 Compare U1');
    await r.choose('#compare-a', await r.eval("[...document.getElementById('compare-a').options].find(o=>o.textContent.startsWith('Run 8 · ')).value"));
    await r.choose('#compare-b', await r.eval("[...document.getElementById('compare-b').options].find(o=>o.textContent.startsWith('Run 9 · ')).value"));
    await r.until("!!document.getElementById('compare-neff')", 'R17 Compare table');
    await rSize(1440, 900);
    const u4 = await r.eval(`(()=>{const t=document.getElementById('compare-neff'),box=t.closest('.compare-table-scroll');
      return {note:document.getElementById('compare-edge-note')?.textContent??null,unmatched:[...t.querySelectorAll('tr[data-no-match]')].map(tr=>[tr.dataset.noMatch,tr.cells[3].textContent,tr.cells[3].dataset.bestOverlap??null]),
       slack:box.clientWidth-Math.ceil(t.getBoundingClientRect().width)};})()`);
    stage('R17 U1 U4 Compare', u4);
    assert.ok(u4.note && u4.note.startsWith('B · Run 9: Mode 1 is mostly in Substrate ('), u4.note);
    assert.ok(u4.unmatched.length > 0, 'the substrate modes match none of the template core');
    for (const [, text, eta] of u4.unmatched) {
      if (eta === null) { assert.equal(text, '—'); continue; }
      const m = /^best (\d\.\d{2,3}) \((?:< 0\.8|margin < 0\.1), not matched\)$/.exec(text); assert.ok(m, text);
    }
    assert.ok(u4.unmatched.some(([, , eta]) => eta !== null), 'an unmatched row shows its best overlap');
    assert.ok(u4.slack >= 24, `R17 Compare: ${u4.slack} px to spare at 1440 (O2, 24 px)`);
    await rOverflow('U4 Compare');
    await browserPage.call('Target.disposeBrowserContext', {browserContextId});
  }

  // R18 (round 18, pre-registered), in a browser context of its own: the Run study box and its
  // layout (X2, X3), "No need to run" (X1), the boundary tag (X6), the source of the current inputs
  // (X11), the closed-window note's shortcuts (X9), the Search near n_eff help (X12), with no
  // horizontal overflow and O2's 24 px on Compare.
  {
    const devtools = await (await fetch(`http://127.0.0.1:${debugPort}/json/version`)).json();
    const browserPage = new Page(devtools.webSocketDebuggerUrl); await browserPage.ready;
    const {browserContextId} = await browserPage.call('Target.createBrowserContext');
    const {targetId} = await browserPage.call('Target.createTarget', {url: 'about:blank', browserContextId});
    const r = new Page(`ws://127.0.0.1:${debugPort}/devtools/page/${targetId}`); await r.ready;
    await r.call('Runtime.enable'); await r.call('Page.enable'); await r.call('DOM.enable'); await r.call('Accessibility.enable');
    const rSize = async (width, height, mobile = false) => { await r.call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile}); await sleep(300); };
    await rSize(1440, 900);
    const rText = selector => r.onElement('function(selector){const e=this.querySelector(selector);return e?e.textContent:null}', selector);
    const rOverflow = async tag => {
      for (const [width, height, mobile] of [[1440, 900, false], [390, 844, true]]) {
        await rSize(width, height, mobile);
        const over = await r.eval('document.documentElement.scrollWidth-document.documentElement.clientWidth');
        stage('R18 overflow ' + tag, {width, height, over}); assert.ok(over <= 0, `${tag} at ${width} × ${height} overflows by ${over}px`);
      }
      await rSize(1440, 900);
    };
    // the ribbon's Compute group and Run study, per size: equal (within 0.5 px) whatever the box says
    const ribbon = async () => {
      const out = {};
      for (const [width, height, mobile] of [[1440, 900, false], [390, 844, true]]) {
        await rSize(width, height, mobile);
        out[width] = await r.eval("(()=>{const g=document.querySelector('.solve-commands').getBoundingClientRect(),b=document.getElementById('run-optical').getBoundingClientRect(),o=document.getElementById('run-options').getBoundingClientRect();return {group:[g.height,g.top],run:[b.left,b.top,b.width,b.height],box:[o.width,o.height]}})()");
      }
      await rSize(1440, 900); return out;
    };
    const sameRibbon = (a, b, tag) => { for (const w of ['1440', '390']) for (const key of ['group', 'run', 'box']) a[w][key].forEach((v, i) => assert.ok(Math.abs(v - b[w][key][i]) <= 0.5, `${tag}: ${key} at ${w} moved (${JSON.stringify(a[w])} → ${JSON.stringify(b[w])})`)); };
    const rTree = async (name, ready) => { await r.click('nav [data-page=Model]'); await sleep(200); await r.clickTreeItem(name); await r.until(ready, name); };
    const rRun = async () => {
      await r.until("!document.getElementById('run-optical').disabled", 'R18 Run enabled');
      const before = await r.eval("JSON.stringify([...document.querySelectorAll('.run-item')].map(b=>b.textContent))");
      await r.click('#run-optical'); if (await r.eval("!!document.getElementById('run-drop-confirm')?.open")) await r.click('#run-drop-confirm-run');
      await r.until(`JSON.stringify([...document.querySelectorAll('.run-item')].map(b=>b.textContent))!==${JSON.stringify(before)}&&!document.getElementById('run-optical').disabled&&document.getElementById('run-optical').textContent==='Run study'&&!!document.getElementById('modes-table')`, 'R18 run done', 600000);
    };
    const runItems = () => r.eval("[...document.querySelectorAll('.run-item')].map(b=>b.textContent)");
    const plan = () => rText('#run-plan');
    const mesh = async nm => { await rTree('Mesh', "!!document.getElementById('core-mesh-number')"); await r.type('#core-mesh-number', nm); await sleep(400); };
    await r.call('Page.navigate', {url: base + '/workspace'});
    await r.until("/^Connected/.test(document.getElementById('connection-status').textContent)&&!!document.querySelector('[data-template=optical]')", 'R18 start page');
    await r.click('[data-template=optical]'); await r.until("!!document.getElementById('shape-w')", 'R18 optical model');
    // X2: the box before any run, then the group index and Open boundary (the warning in Messages)
    const x2 = {fresh: await plan(), shown: await r.eval("!document.getElementById('run-options').hidden")}; const ribbonFresh = await ribbon();
    await rTree('Optical modes', "!!document.getElementById('group-index-check')"); await r.click('#group-index-check'); await sleep(200);
    x2.group = await plan(); sameRibbon(ribbonFresh, await ribbon(), 'X2 group index');
    await r.click('input[name="outer-boundary"][value="open"]'); await sleep(400);
    x2.open = await plan(); x2.warning = await rText('#file-status .message-warning');
    x2.warningStyle = await r.eval("(()=>{const w=getComputedStyle(document.querySelector('#file-status .message-warning')),m=getComputedStyle(document.getElementById('file-status'));return [w.color!==m.color,w.backgroundColor!==m.backgroundColor,w.fontWeight]})()");
    x2.help = await rText('#target-help'); sameRibbon(ribbonFresh, await ribbon(), 'X2 open boundary');
    stage('R18 X2 Run study box', x2);
    assert.equal(x2.shown, true); assert.equal(x2.fresh, 'Closed window · no timed run in this tab yet');
    assert.equal(x2.group, 'Closed window · group index on (3 solves) · no timed run in this tab yet');
    assert.equal(x2.open, 'Open boundary · 2 searches · group index on (3 solves) · no timed run in this tab yet');
    assert.equal(x2.warning, 'Group index is on: open-boundary runs with it take about three times as long.');
    assert.deepEqual(x2.warningStyle.slice(0, 2), [true, true]);
    // X12: the help says where 2.46 comes from
    assert.ok(x2.help.endsWith(' The default is halfway between the core and silica indices: (n_core + 1.444)/2.'), x2.help);
    await rOverflow('X2 open boundary');
    await r.click('input[name="outer-boundary"][value="closed"]'); await sleep(200); await r.click('#group-index-check'); await sleep(200);
    assert.equal(await plan(), 'Closed window · no timed run in this tab yet');
    // runs 1 and 2 (core mesh 30 and 32): the box names the last such run's time; X6 tags
    await mesh(30); await rRun(); x2.afterRun = await plan();
    assert.ok(/^Closed window · last such run \d+:\d\d$/.test(x2.afterRun), x2.afterRun);
    await mesh(32);
    // X1: back to Run 1's inputs: No need to run, with Show Run 1; Run study is not blocked
    await mesh(30);
    const x1 = {message: await rText('#file-status'), button: await rText('#file-status [data-show-run]'), runEnabled: await r.eval("!document.getElementById('run-optical').disabled")};
    await r.click('#file-status [data-show-run]'); await sleep(300);
    x1.shown = {message: await rText('#file-status'), page: await r.eval("document.querySelector('nav [data-page][aria-selected=true]')?.dataset.page"), pressed: await rText('.run-item[aria-pressed=true]')};
    stage('R18 X1 no need to run', x1);
    assert.ok(x1.message.includes(' No need to run: Run 1 already has these results. Run study adds a copy with the same values. '), x1.message);
    assert.equal(x1.button, 'Show Run 1'); assert.equal(x1.runEnabled, true);
    assert.equal(x1.shown.message, 'Run 1 shown under Results; the inputs are unchanged.'); assert.equal(x1.shown.page, 'Results');
    // X6: a closed run carries "closed" right after its number
    assert.ok(x1.shown.pressed.startsWith('Run 1 · closed · 500 × 220 nm · Silicon · λ 1550 nm · '), x1.shown.pressed);
    await mesh(32); await rRun();
    // X11: Run 1 viewed, the current inputs are Run 2's
    await r.click('nav [data-page=Results]'); await r.until("!!document.querySelector('.run-item')", 'R18 run list');
    await r.onElement('function(){[...this.querySelectorAll(".run-item")].find(b=>b.textContent.startsWith("Run 1 · ")).click();return true}', 'body'); await sleep(300);
    const x11 = await rText('#status'); stage('R18 X11 status', {status: x11});
    assert.ok(x11.endsWith(' · current inputs from Run 2'), x11);
    // X3: runs 3 to 6: the box names the run the next one drops, with Pin Run 1; the ribbon does not move
    const ribbonBefore = await ribbon();
    for (const nm of [34, 36, 38, 40]) { await mesh(nm); await rRun(); }
    const x3 = {drop: await rText('#run-drop-text'), pin: await rText('#run-drop-pin'), plan: await plan()};
    sameRibbon(ribbonBefore, await ribbon(), 'X3 drop line');
    await rOverflow('X3 drop line');
    await r.click('#run-drop-pin'); await sleep(300);
    x3.afterPin = {drop: await rText('#run-drop-text'), pin: await rText('#run-drop-pin'), message: await rText('#file-status'), items: await runItems()};
    stage('R18 X3 drop warning', x3);
    assert.equal(x3.drop, 'Running drops Run 1 (500 × 220 nm · 2 modes) · pin it to keep it'); assert.equal(x3.pin, 'Pin Run 1');
    assert.equal(x3.afterPin.drop, 'Running drops Run 2 (500 × 220 nm · 2 modes) · pin it to keep it'); assert.equal(x3.afterPin.pin, 'Pin Run 2');
    assert.equal(x3.afterPin.message, 'Run pinned: new runs will not replace it. File › Save keeps it in a file.');
    assert.ok(x3.afterPin.items.some(t => t.startsWith('Pinned · Run 1 · closed · ')), JSON.stringify(x3.afterPin.items));
    // X9: the strip over a substrate in a closed window (run 7, which drops Run 2): the note's shortcuts
    await rTree('Geometry', "!!document.querySelector('#shape-w')");
    await r.click('[data-add-shape=rect]'); await r.until("document.querySelectorAll('.shape-item').length===2", 'R18 substrate added');
    await r.type('#shape-name', 'Substrate'); await r.choose('#shape-material', 'Silicon');
    for (const [id, value] of [['#shape-x', -1500], ['#shape-y', -1200], ['#shape-w', 3000], ['#shape-h', 700]]) await r.type(id, value);
    await mesh(30); await rRun();
    const x9 = {buttons: await r.eval("[...document.querySelectorAll('#edge-actions button')].map(b=>b.textContent)"), items: (await runItems()).length};
    await r.click('#edge-find-modes'); await sleep(300);
    x9.find = {message: await rText('#file-status'), buttons: await r.eval("[...document.querySelectorAll('#edge-actions button')].map(b=>b.textContent)"), items: (await runItems()).length};
    await r.click('#edge-use-open'); await sleep(400);
    x9.open = {message: await rText('#file-status'), actions: await r.eval("!!document.getElementById('edge-actions')"), plan: await plan(), items: (await runItems()).length, busy: await r.eval("document.getElementById('run-optical').textContent")};
    stage('R18 X9 note shortcuts', x9);
    assert.deepEqual(x9.buttons, ['Use Open boundary', 'Find 4 modes']);
    assert.ok(x9.find.message.startsWith('Modes to find set to 4.'), x9.find.message); assert.deepEqual(x9.find.buttons, ['Use Open boundary']); assert.equal(x9.find.items, x9.items);
    assert.ok(x9.open.message.startsWith('Open boundary: a PML of 1 µm outside every edge;'), x9.open.message); assert.equal(x9.open.actions, false);
    assert.ok(x9.open.plan.startsWith('Open boundary · '), x9.open.plan); assert.equal(x9.open.items, x9.items); assert.equal(x9.open.busy, 'Run study');
    await rOverflow('X9 Results');
    // X6 on Compare: the pickers and headings carry the tag; O2's 24 px
    await r.click('nav [data-page=Compare]'); await r.until("!!document.getElementById('compare-neff')||!!document.getElementById('compare-a')", 'R18 Compare');
    await r.until("!!document.getElementById('compare-neff')", 'R18 Compare table');
    const x6 = await r.eval(`(()=>{const t=document.getElementById('compare-neff'),box=t.closest('.compare-table-scroll');
      return {picker:document.getElementById('compare-b').selectedOptions[0].textContent,heads:[...document.querySelectorAll('.compare-grid article h3, #compare-table-runs [data-side]')].map(e=>e.textContent),slack:box.clientWidth-Math.ceil(t.getBoundingClientRect().width)};})()`);
    stage('R18 X6 Compare', x6);
    assert.ok(x6.picker.startsWith('Run 7 · closed · Core 500 × 220 + Substrate 3000 × 700 nm · '), x6.picker);
    assert.ok(x6.heads.length > 0 && x6.heads.every(h => h.includes(' · closed · ')), JSON.stringify(x6.heads));
    assert.ok(x6.slack >= 24, `R18 Compare: ${x6.slack} px to spare at 1440 (O2, 24 px)`);
    await rOverflow('X6 Compare');
    await browserPage.call('Target.disposeBrowserContext', {browserContextId});
  }

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
