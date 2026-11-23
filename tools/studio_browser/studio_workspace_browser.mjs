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
  // P2: the Library's one "Open session file…" is at the top of the page, under no card, at
  // 1440 × 900 and on a 390 × 844 phone; back to 1280 × 800 after
  const libraryOpenFile = async tag => {
    for (const [width, height, mobile] of [[1440, 900, false], [390, 844, true]]) {
      await page.call('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile}); await sleep(300);
      const seen = await page.eval("(()=>{const all=[...document.querySelectorAll('#canvas button')].filter(b=>/Open session file/.test(b.textContent)),b=all[0],r=b?.getBoundingClientRect(),first=document.querySelector('#canvas>*:not(.library-files)')?.getBoundingClientRect();return {count:all.length,id:b?.id,underCard:!!b?.closest('.card-slot,.resume-card,[data-template]'),above:!!(r&&first&&r.bottom<=first.top),left:Math.round(r?.left??-1),right:Math.round(r?.right??-1),width:innerWidth}})()");
      stage('P2 one Open session file ' + tag, {width, height, ...seen});
      assert.deepEqual([seen.count, seen.id, seen.underCard, seen.above], [1, 'library-open-file', false, true], `${tag} at ${width} × ${height}`);
      assert.ok(seen.left >= 0 && seen.right <= seen.width, `${tag}: the button is inside the page at ${width}`);
    }
    await page.call('Emulation.setDeviceMetricsOverride', {width: 1280, height: 800, deviceScaleFactor: 1, mobile: false}); await sleep(300);
  };
  // round 11 (L6): on Results and Compare no tree node is marked, and a node under the pointer does not look selected
  const treeMarks = async tag => {
    const marks = await page.eval("(()=>{const items=[...document.querySelectorAll('#tree [role=treeitem]:not(.tree-heading)')];const mesh=items.find(b=>b.dataset.node==='Mesh'),geo=items.find(b=>b.dataset.node==='Geometry');const r=mesh.getBoundingClientRect();return {selected:items.filter(b=>b.getAttribute('aria-selected')==='true').map(b=>b.textContent.trim()),shown:r.width>0,x:r.left+r.width/2,y:r.top+r.height/2,plain:getComputedStyle(geo).backgroundColor}})()");
    stage('L6 tree on ' + tag, marks); assert.deepEqual(marks.selected, [], `no tree node is selected on ${tag}`);
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
  assert.equal(startPage.tab, 'Library'); assert.equal(startPage.heading, 'Choose a starting model'); assert.equal(startPage.view, 'Model library · Choose a model');
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
  await libraryOpenFile('without offers');
  assert.equal(await text('#file-status'), 'Choose a model to begin. Save session keeps the inputs with the optical or multiphysics runs; heat and Joule heating results stay in this tab.');
  const icons = await page.eval("Object.fromEntries([...document.querySelectorAll('.cards [data-template]')].map(b=>[b.dataset.template,getComputedStyle(b,'::before').content]))");
  stage('model card icons', icons); assert.notEqual(icons.joule, icons.optical); assert.equal(new Set(Object.values(icons)).size, Object.keys(icons).length);
  await page.click('[data-template=optical]'); await page.until("!!document.querySelector('#shape-w')", 'optical template');
  // before any edit or run: a new model, and the dock and footer keep the words before a run
  const opticalSequence = () => page.eval("({heading:document.querySelector('.dock-title>span').textContent,status:document.getElementById('status').textContent})");
  assert.equal(await page.eval("document.getElementById('project').textContent"), 'Optical waveguide / New model · not saved');
  assert.deepEqual(await opticalSequence(), {heading: 'Nothing is computed until you press Run', status: 'Optical adapter ready · explicit Run required'});
  // round 12 (N7; pre-registered): the page tabs are a tablist named Pages, Library first, the shown
  // page's tab selected and the one tab stop; Left, Right, Home and End move between them and open the page
  const tabState = async () => ({ax: (await page.axTree(['tablist', 'tab'])).map(n => [n.role, n.name, n.selected === true]),
    stops: await page.eval("[...document.querySelectorAll('nav [role=tab]')].filter(b=>b.tabIndex===0).map(b=>b.textContent)"), focus: (await focused()).name,
    page: await page.eval("document.querySelector('main').dataset.page")});
  let tabs = await tabState(); stage('N7 page tabs', tabs);
  assert.deepEqual(tabs.ax, [['tablist', 'Pages', false], ['tab', 'Library', false], ['tab', 'Model', true], ['tab', 'Connections', false], ['tab', 'Results', false], ['tab', 'Compare', false]]);
  assert.deepEqual(tabs.stops, ['Model']);
  await page.eval("document.querySelector('nav [data-page=Model]').focus()");
  for (const [key, name, shown] of [['ArrowRight', 'Connections', 'Connections'], ['ArrowLeft', 'Model', 'Model'], ['End', 'Compare', 'Compare'], ['ArrowRight', 'Library', 'Applications'], ['Home', 'Library', 'Applications'], ['ArrowLeft', 'Compare', 'Compare'], ['Home', 'Library', 'Applications'], ['ArrowRight', 'Model', 'Model']]) {
    await press(key); tabs = await tabState(); stage('N7 ' + key, tabs);
    assert.deepEqual([tabs.focus, tabs.stops, tabs.page], [name, [name], shown], key);
    assert.deepEqual(tabs.ax.filter(n => n[2]).map(n => n[1]), [name], key + ': one tab selected');
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
  const afterRun = await page.eval("({study:[...document.querySelectorAll('#workflow .workflow-step')][3]?.innerText.replace(/\\s+/g,' '),title:document.getElementById('project').textContent})");
  stage('first run complete', afterRun); assert.match(afterRun.study, /Run complete/); assert.doesNotMatch(afterRun.title, /Revision/);
  // one save indicator: before a file save it says which copy exists, and the footer repeats it
  await page.until("document.getElementById('project').textContent==='Optical waveguide / Not saved to a file · kept for recovery in this browser'", 'save indicator after a run', 20000);
  assert.equal(await page.eval("document.getElementById('autosave-status').textContent"), 'Not saved to a file · kept for recovery in this browser');
  // n_eff with 8 decimals in the mode list as in the modes table; plot axes and the inspector in nm
  const resultsView = await page.eval("({options:[...document.querySelectorAll('#field-mode option')].map(o=>o.textContent),values:[...document.querySelectorAll('#modes-table [data-neff]')].map(e=>e.textContent),polarization:[...document.querySelectorAll('#modes-table [data-polarization]')].map(e=>e.textContent),loss:[...document.querySelectorAll('#modes-table [data-loss]')].map(e=>e.textContent),area:[...document.querySelectorAll('#modes-table [data-area]')].map(e=>({text:e.textContent,value:Number(e.dataset.areaValue),title:e.title})),areaSource:[...document.querySelectorAll('#run-details .pair')].map(e=>e.textContent).find(t=>/^Effective area/.test(t))||null,head:[...document.querySelectorAll('#modes-table thead th')].map(e=>e.firstChild.textContent),hint:document.querySelector('#modes-table [data-group-index-hint]')?.textContent??null,lossless:document.getElementById('lossless-note')?.textContent||null,probe:[...document.querySelectorAll('.probe-controls label')].map(l=>l.firstChild.textContent),pin:document.getElementById('pin-run')?.textContent||null,imports:document.getElementById('import-runs')?.textContent})");
  stage('results view', resultsView);
  for (const option of resultsView.options) assert.match(option, /^Mode \d · (TE-like|TM-like|hybrid|pair) · n_eff \d\.\d{8}$/);
  assert.deepEqual(resultsView.head, ['Mode', 'n_eff', 'Polarization', 'Absorption loss (dB/cm)', 'A_eff (µm²)', 'n_g']);
  assert.equal(resultsView.hint, 'Off · turn on in Study or Optical modes', 'round 12 (N4): the n_g header says how to turn it on');
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
  // round 12 (N1): the run names are in the line above the table, the headers short and grouped A | B
  assert.deepEqual(neffTable.head.slice(4, 6), ['n_eff A', 'n_eff B']); assert.deepEqual(neffTable.runs, ['A · Run 1 · design A · 600 × 300 nm · Silicon · λ 1550 nm', 'B · Run 2 · 700 × 300 nm · Silicon · λ 1550 nm']);
  assert.deepEqual(neffTable.head.slice(8), ['A_eff A (µm²)', 'A_eff B (µm²)', 'Absorption loss A (dB/cm)', 'Absorption loss B (dB/cm)', 'n_g A', 'n_g B']);
  // both sides of a matched row give their A_eff in µm²
  for (const row of neffTable.rows) assert.match(row[8] + ' ' + row[9], /^\d\.\d{4} \d\.\d{4}$/);
  assert.equal(neffTable.rows[0][0], 'A mode 1 ↔ B mode 1'); assert.equal(neffTable.short[0], '1 ↔ 1');
  assert.equal(neffTable.rows[0][6], before, 'the table and the sentence give the same Δn_eff');
  // the field panels do not repeat the name, and come before the n_eff table
  const panels = await page.eval("({headings:[...document.querySelectorAll('.compare-grid h3')].map(h=>h.textContent),plotsFirst:!!(document.querySelector('.compare-grid').compareDocumentPosition(document.getElementById('compare-neff'))&Node.DOCUMENT_POSITION_FOLLOWING),plotTop:Math.round(document.getElementById('compare-field-a').getBoundingClientRect().top+scrollY),viewport:innerHeight})");
  stage('compare panels', panels);
  assert.deepEqual(panels.headings, ['A · Run 1 · design A · 600 × 300 nm · Silicon · λ 1550 nm', 'B · Run 2 · 700 × 300 nm · Silicon · λ 1550 nm']);
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
    await page.onElement('function(selector){[...this.querySelectorAll(selector)].find(b=>/^Run 2 · 700/.test(b.textContent)).click();return true}', '.run-item'); await sleep(200);
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
  assert.deepEqual(await pressedPage(), ['Results']); assert.match(await page.eval("document.querySelector('.dock-title>span').textContent"), /^Run 1 · design A · /);
  // round 10 (K6): on Results the tree marks no optical node (the optical tree has no Results node), not Study
  assert.deepEqual((await page.axTree()).filter(n => n.role === 'treeitem' && n.selected === true).map(n => n.name), []);
  assert.deepEqual(await cardLook(), {pressed: 1, looks: 1, hovered: 1});
  // round 10 (K10): a run with other inputs than the current ones is information: the step bar is neutral
  const tone = await page.eval("(()=>{const b=[...document.querySelectorAll('#workflow .workflow-step')][4];return {tone:b.dataset.tone,state:b.dataset.state,color:getComputedStyle(b.querySelector('span')).color,muted:getComputedStyle(document.querySelector('.muted')||document.body).color}})()");
  stage('K10 neutral step', tone); assert.deepEqual([tone.state, tone.tone], ['attention', 'info']); assert.equal(tone.color, 'rgb(97, 112, 134)', 'the muted colour, not the warning colour');
  // back to Compare with Run 2 selected, as before this stage
  await page.click('nav [data-page=Compare]'); await page.until("!!document.getElementById('compare-neff')", 'Compare again');
  await page.onElement('function(selector){[...this.querySelectorAll(selector)].find(b=>/^Run 2 · 700/.test(b.textContent)).click();return true}', '.run-item'); await sleep(300);
  assert.deepEqual(await pressedPage(), ['Compare']); assert.match(await text('.run-item[aria-pressed=true]'), /^Run 2 · 700/);
  await page.click('#save-session'); await confirmName('first save');
  let sessionFile;
  for (let i = 0; i < 100 && !sessionFile; i++) { sessionFile = (await readdir(downloads)).find(f => f.endsWith('.json')); if (!sessionFile) await sleep(100); }
  assert.ok(sessionFile, 'Save session downloaded a file');
  const session = JSON.parse(await readFile(join(downloads, sessionFile), 'utf8'));
  const savedHeader = await page.eval("document.getElementById('project').textContent"), savedMessage = await page.eval("document.getElementById('file-status').textContent");
  stage('session saved', {file: sessionFile, runs: session.runs?.length, header: savedHeader, message: savedMessage});
  assert.equal(session.runs?.length, 2);
  assert.match(sessionFile, /^optical-waveguide-session-\d{4}-\d{2}-\d{2}-\d{4}\.json$/);
  assert.ok(savedMessage.startsWith(`Session file ${sessionFile} sent to your browser's Downloads: `), savedMessage);
  assert.ok(savedHeader.startsWith(`Optical waveguide / ${sessionFile} · saved `) && savedHeader.endsWith(' (download)'), savedHeader);
  // round 13 (O1): the title names the file and "saved … (download)", never that it reached the disk
  assert.doesNotMatch(savedHeader, /disk/i, 'the title never claims the file reached the disk');
  // the footer repeats the title's save indicator and never says "pending"
  const savedFooter = await page.eval("document.getElementById('autosave-status').textContent");
  assert.equal('Optical waveguide / ' + savedFooter, savedHeader); assert.doesNotMatch(savedFooter, /pending/i);
  // round 10 (K3): a page, a run or a mode chosen is not a change: the title still names the file
  await page.click('nav [data-page=Results]'); await page.until("!!document.getElementById('field-mode')", 'Results after save');
  await page.choose('#field-mode', '1'); await sleep(300);
  const keptName = await page.eval("document.getElementById('project').textContent"); stage('K3 title after a mode change', {keptName});
  assert.ok(keptName.startsWith(`Optical waveguide / ${sessionFile} · saved `) && keptName.endsWith(' (download)'), keptName);
  await page.choose('#field-mode', '0'); await page.click('nav [data-page=Compare]'); await page.until("!!document.getElementById('compare-neff')", 'Compare after save');
  assert.ok((await page.eval("document.getElementById('project').textContent")).startsWith(`Optical waveguide / ${sessionFile} · saved `));
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
  const routes = await page.eval("({latest:document.getElementById('resume-optical').textContent,listed:[...document.querySelectorAll('[data-resume-record]:not(#resume-optical)')].map(b=>b.textContent),box:!!document.querySelector('.resume-card'),open:document.getElementById('library-open-file').textContent,beside:!!document.getElementById('library-open-file').closest('.card-slot,.resume-card'),top:document.getElementById('canvas').firstElementChild?.contains(document.getElementById('library-open-file')),count:[...document.querySelectorAll('button')].filter(b=>/Open session file/.test(b.textContent)).length,note:document.querySelector('.library-portable')?.textContent,footer:document.getElementById('autosave-status').textContent})");
  stage('routes back', routes);
  // the offer names the session file the record was last sent to
  // round 10 (K3, K7): one phrase for browser recovery, and the file the record still matched
  // round 11 (L9): the record is the same as the file, so the offer names the file's save time, not the record's
  assert.ok(routes.latest.startsWith('Restore from this browser · Optical waveguide · Run 1 · design A, Run 2 · same as file ' + sessionFile + ', saved '), routes.latest);
  assert.match(routes.latest, /, saved \d{1,2}:\d\d(?: [AP]M)?$/);
  assert.doesNotMatch(await text('#canvas'), /Recover|\(this browser/, 'the Library page says Restore from this browser'); assert.equal(routes.open, 'Open session file…');
  assert.deepEqual(routes.listed, [], 'the record the card resumes is not listed again above it'); assert.equal(routes.box, false);
  assert.equal(routes.beside, false, 'Open session file is not under a card'); assert.equal(routes.top, true, 'Open session file is at the top of the Library'); assert.equal(routes.count, 1);
  await libraryOpenFile('with a resume offer');
  assert.equal(routes.note, 'A session file is the copy that moves between computers; browser recovery stays in this browser.');
  assert.equal(routes.footer, 'Last session kept in this browser · 2 runs');
  await page.screenshot('resume-card');
  // a fresh page holds nothing an open would lose, so recovery asks nothing
  await page.click('#resume-optical'); await page.until("!!document.getElementById('compare-neff')", 'recovered comparison');
  await treeMarks('Compare after a restore');
  assert.equal(await page.eval("!!document.querySelector('dialog[open]')"), false, 'no confirmation over an untouched workspace');
  const after = await delta(), recoveredHeader = await page.eval("document.getElementById('project').textContent");
  stage('comparison recovered', {deltaNeff: after, header: recoveredHeader}); assert.equal(after, before);
  // round 10 (K3): the record still matched the file it was sent to: the title says so
  assert.equal(recoveredHeader, `Optical waveguide / Recovered from this browser · same as file ${sessionFile}`);
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
  // round 11 (L3): a short suffix on Results
  assert.match(viewed.header, / · viewing Run 1 · design A \(other inputs\)$/); assert.doesNotMatch(viewed.header, /Unsaved inputs/);
  assert.equal(await page.eval("document.getElementById('autosave-status').textContent"), viewed.header.replace(/^Optical waveguide \/ /, ''));
  // round 11 (L6): on Results no tree node is marked, and a node under the pointer does not look selected
  await treeMarks('Results');
  // round 11 (L3): on the Model tab the title describes the current inputs only, and the Study
  // settings say which geometry the next run uses
  await page.click('nav [data-page=Model]'); await sleep(200);
  assert.doesNotMatch(await page.eval("document.getElementById('project').textContent"), /viewing/);
  await page.clickTreeItem('Study'); await page.until("!!document.getElementById('next-run-inputs')", 'L3 study settings');
  assert.match(await text('#next-run-inputs'), /^Next run uses 700 × 300 nm · Silicon · λ 1550 nm · /);
  // Use this run's inputs: run 1's inputs become the current ones at once (no question: the runs
  // stay), the title and the step bar agree, and Undo takes them back
  await page.click('nav [data-page=Results]'); await page.until("!!document.getElementById('restore-run-input')", 'L3 Use this run\'s inputs');
  assert.equal(await text('#restore-run-input'), 'Use this run’s inputs'); assert.match(await text('#restore-run-input-hint'), /^The next run uses the current inputs \(700 × 300 nm · Silicon\)\. This loads Run 1 · design A’s inputs instead; Undo takes them back\.$/);
  await page.click('#restore-run-input'); await page.until("!document.getElementById('restore-run-input')&&/Same as the current inputs/.test(document.getElementById('inspector').textContent)", 'L3 inputs used');
  const used = await page.eval("({dialog:!!document.querySelector('dialog[open]'),header:document.getElementById('project').textContent,step:[...document.querySelectorAll('#workflow .workflow-step')][4]?.innerText.replace(/\\s+/g,' '),runs:document.querySelectorAll('.run-item').length,page:[...document.querySelectorAll('nav [data-page]')].filter(b=>b.getAttribute('aria-selected')==='true').map(b=>b.dataset.page),message:document.getElementById('file-status').textContent})");
  stage('L3 run inputs used', used);
  assert.equal(used.dialog, false); assert.doesNotMatch(used.header, /viewing/); assert.equal(used.step, '5. Results Result for these inputs'); assert.equal(used.runs, 2); assert.deepEqual(used.page, ['Results']);
  // round 13 (O5): only the settings that change, from → to (Width 700 → 600 nm keeps the centre, so Left x moves too)
  assert.equal(used.message, 'Current inputs set from Run 1 · design A: Width 700 → 600 nm · Left x −350 → −300 nm. The next run uses them; Undo takes them back.');
  await page.click('nav [data-page=Model]'); await sleep(200); await page.clickTreeItem('Study'); await page.until("!!document.getElementById('next-run-inputs')", 'L3 study after use');
  assert.match(await text('#next-run-inputs'), /^Next run uses 600 × 300 nm · Silicon · /);
  await page.click('#undo-edit'); await sleep(200);
  assert.match(await text('#next-run-inputs'), /^Next run uses 700 × 300 nm · Silicon · /, 'Undo takes the run\'s inputs back');
  await page.click('nav [data-page=Results]'); await page.until("!!document.getElementById('restore-run-input')", 'L3 back on Results');
  assert.match(await page.eval("document.getElementById('project').textContent"), / · viewing Run 1 · design A \(other inputs\)$/);
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
  // round 10 (K3): a run chosen on Results is not a change: the recovered title still names the file
  assert.ok(viewed.header.startsWith(`Optical waveguide / Recovered from this browser · same as file ${sessionFile}`), viewed.header);
  // round 10 (K6): restoring opens the page shown when the record was written (Results, Run 1), not Compare or the newest run
  // the stored record names the page shown and the run selected (read back from browser storage)
  await page.until("import('/workspace-assets/workspace-notebook-recovery.mjs').then(async m=>{const r=await m.indexedNotebookStore().load();const d=JSON.parse(r.session);return r.page==='Results'&&d.selected===d.runs[0].job;})", 'recovery of the Results page', 20000);
  await page.call('Page.reload'); await page.until("!!document.querySelector('#resume-optical')", 'resume offer after Results');
  await page.click('#resume-optical'); await page.until("!!document.getElementById('optical-field')", 'restored on Results');
  const restored = await page.eval("({page:[...document.querySelectorAll('nav [data-page]')].filter(b=>b.getAttribute('aria-selected')==='true').map(b=>b.dataset.page),heading:document.querySelector('.dock-title>span').textContent,pressed:[...document.querySelectorAll('.run-item[aria-pressed=true]')].map(b=>b.textContent),header:document.getElementById('project').textContent})");
  stage('K6 restored on Results', restored);
  assert.deepEqual(restored.page, ['Results']); assert.match(restored.heading, /^Run 1 · design A · /); assert.equal(restored.pressed.length, 1); assert.match(restored.pressed[0], /^Pinned · Run 1 · design A/);
  assert.ok(restored.header.startsWith(`Optical waveguide / Recovered from this browser · same as file ${sessionFile}`), restored.header);
  // round 10 (K3): a change of the model or a run ends "same as file". An input edit reads
  // "Unsaved inputs" (the existing words for edited inputs); a run renamed reads "Changed since
  // session file …"; the same content again names the file again
  const header = () => page.eval("document.getElementById('project').textContent");
  await toGeometry(); await page.type('#shape-w', 750);
  const editedHeader = await header(); stage('K3 after an input edit', {editedHeader}); assert.equal(editedHeader, 'Optical waveguide / Unsaved inputs');
  await page.type('#shape-w', 700); assert.ok((await header()).startsWith(`Optical waveguide / Recovered from this browser · same as file ${sessionFile}`), await header());
  await page.click('nav [data-page=Results]'); await page.until("!!document.querySelector('.run-item')", 'run list again');
  await renameOnBlur('design A3'); await sleep(300);
  const renamedHeader = await header(); stage('K3 after a run renamed', {renamedHeader});
  assert.ok(renamedHeader.startsWith(`Optical waveguide / Changed since session file ${sessionFile} (`), renamedHeader);
  await renameOnBlur('design A'); await sleep(300); assert.ok((await header()).startsWith(`Optical waveguide / Recovered from this browser · same as file ${sessionFile}`), await header());
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
  assert.equal(switchedParts.line, 'Heated silicon waveguide ready. Edit settings and couplings, then press Run. Optical waveguide runs stay in this tab · Library › Optical waveguide returns to them');
  assert.equal(switchedParts.summary, 'More');
  assert.match(switchedParts.more, /^This tab holds 2 runs until it is closed or reloaded\. After that, Library › Optical waveguide › Restore from this browser \(browser recovery, which keeps the four newest sessions\)(?: or Open session with \S+\.json)? brings them back\.$/);
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
  assert.deepEqual(matched.head.slice(4, 6), ['n_eff A', 'n_eff B']); assert.match(matched.runs[0], /^A · Run 3 · 500 × 300 nm/); assert.match(matched.runs[1], /^B · Run 4 · 450 × 300 nm/);
  assert.deepEqual(matched.matched, ['0:0', '1:1']); assert.deepEqual(matched.rows.map(r => r[0]), ['A mode 1 ↔ B mode 1', 'A mode 2 ↔ B mode 2']); assert.deepEqual(matched.short, ['1 ↔ 1', '2 ↔ 2']);
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
  assert.ok(!offers.top.some(t => t.record === offers.card.record), 'the box above does not list the record the card resumes');
  // compared by the stored inputs and runs themselves, not by the sessionKey under test
  assert.equal(new Set(offers.keys).size, offers.keys.length, 'every offered entry is another session');
  assert.ok(!offers.top.some(t => t.text.includes('Optical waveguide · 2 runs · Run 1 · design A, Run 2')), JSON.stringify(offers.top));
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
  assert.equal(m4study.value, '8'); assert.match(m4study.text, /Window and boundaries are fixed\./); assert.doesNotMatch(m4study.text, /mode count are fixed|candidate count/i);
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
  let listed = await listDownloads(); await page.click('#save-session'); await confirmName('V17 save');
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
  await page.click('#save-session'); await page.until("document.getElementById('session-overflow').open", 'M4-e overflow question');
  const question = await page.eval("({text:document.getElementById('session-overflow-description').textContent,buttons:[...document.querySelectorAll('#session-overflow button')].map(b=>b.textContent)})");
  stage('M4-e overflow question', question);
  assert.match(question.text, /^Session is \d\d MB; the limit is 16 MiB\. Keep the fields of the selected and pinned runs only\? The other runs keep n_eff, the TE fractions and the effective areas, but not their fields\.$/);
  assert.deepEqual(question.buttons, ['Cancel', 'Keep fields for selected and pinned runs']);
  listed = await listDownloads(); await page.click('#overflow-cancel'); await sleep(500);
  assert.match(await text('#file-status'), /^Session not saved: nothing was written\./); assert.deepEqual(await listDownloads(), listed, 'Cancel writes nothing');
  await page.click('#save-session'); await page.until("document.getElementById('session-overflow').open", 'M4-e overflow question again');
  // round 13 (O1): the file opened above is the current file, so Save downloads under its name with no dialog
  await page.click('#overflow-keep'); for (let i = 0; i < 5; i++) { assert.equal(await page.eval("!!document.getElementById('save-name-dialog').open"), false, 'M4-e: no name dialog'); await sleep(100); }
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
  const GROUP_NOTE = 'Also solves at λ ± 1 nm and takes n_g from the change (about 3× slower). Off: one solve, no n_g.';
  const groupOn = 'Group index on: the next run also solves at λ ± 1 nm and gives n_g (about 3× slower).', groupOff = 'Group index off: the next run is one solve, without n_g.';
  const m5note = () => page.eval("document.getElementById('group-index-check').closest('label').nextElementSibling.textContent");
  const message = () => page.eval("document.getElementById('file-status').textContent");
  assert.equal(await m5note(), GROUP_NOTE);
  await toNode('Optical modes'); assert.deepEqual(await m5box(), m5off, 'the box in Optical modes'); assert.equal(await m5note(), GROUP_NOTE);
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
  const ngCells = () => page.eval("({head:[...document.querySelectorAll('#modes-table thead th')].map(e=>e.firstChild.textContent),hint:(()=>{const h=document.querySelector('#modes-table [data-group-index-hint]');return h?{text:h.textContent,height:h.getBoundingClientRect().height}:null})(),cells:[...document.querySelectorAll('#modes-table [data-group-index]')].map(e=>({text:e.textContent,title:e.title,value:e.dataset.groupIndexValue??null})),neff:[...document.querySelectorAll('#modes-table [data-neff]')].map(e=>e.textContent)})");
  const offView = await ngCells(); stage('M5 results off', offView);
  assert.equal(offView.head.at(-1), 'n_g');
  assert.equal(offView.hint?.text, 'Off · turn on in Study or Optical modes'); assert.ok(offView.hint.height > 0, 'the hint is visible');
  assert.ok(offView.cells.length >= 1 && offView.cells.every(c => c.text === '—' && c.title === 'Turn on Also compute group index in Study'), JSON.stringify(offView.cells));
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
  // Compare: the off run as A, the on run as B
  await page.click('nav [data-page=Compare]'); await page.until("!!document.getElementById('compare-neff')", 'M5 Compare');
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
  // round 13 (O1): the model file opened last is the current file: Save downloads under its name, no dialog
  const p1Before = await listDownloads(); await page.click('#save-session');
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
    for (const [role, name] of [['button', 'File'], ['button', 'Edit'], ['button', 'Open'], ['button', 'Save']]) assert.equal(await axNamed(role, name), 1, `${role} ${name}`);
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
    assert.equal(saveDialog.title, 'Save'); assert.match(saveDialog.name, /^optical-waveguide-session-\d{4}-\d{2}-\d{2}-\d{4}\.json$/); assert.equal(saveDialog.label, 'File name');
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
    assert.match(fallbackMessage, /^Session file my runx\.json sent to your browser's Downloads: current inputs, \d+ runs and the comparison\./);
    assert.doesNotMatch(fallbackMessage, /^Saved to/);
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
    await key('s', ['Control', 'Shift']); await page.until("/^Saved to /.test(document.getElementById('file-status').textContent)", 'F3 Save As');
    let p3 = await picker(); const saveAsMessage = await status();
    stage('F3 Save As', {calls: p3.calls, writes: p3.writes, message: saveAsMessage});
    assert.equal(p3.calls.length, 1); assert.equal(p3.writes, 1);
    // round 13 (F3): no startIn before a file is chosen, so the id alone restores the last folder;
    // (O1) the suggested name is the current file's, my runx.json from F2
    assert.deepEqual({...p3.calls[0], suggestedName: undefined}, {suggestedName: undefined, types: [{description: 'OpenPhysics session file (JSON)', accept: {'application/json': ['.json']}}], id: 'openphysics-project'});
    assert.equal('startIn' in p3.calls[0], false); assert.equal(p3.calls[0].suggestedName, 'my runx.json');
    assert.equal(p3.content, fallbackText, 'the picker file has the bytes of the download of the same state');
    assert.match(saveAsMessage, /^Saved to chosen\.json: current inputs, \d+ runs and the comparison\./);
    assert.deepEqual(await listDownloads(), before, 'a picker save downloads nothing');
    assert.match(await page.eval("document.getElementById('project').textContent"), /^Optical waveguide \/ chosen\.json · saved [^(]+$/, 'the header names the file written, not as a download');
    // Save: the same file again, no dialog
    await page.eval("document.getElementById('file-status').textContent=''");
    await page.click('#menu-save'); await page.until("/^Saved to chosen\\.json/.test(document.getElementById('file-status').textContent)", 'F3 Save');
    p3 = await picker(); stage('F3 Save again', {calls: p3.calls.length, writes: p3.writes});
    assert.equal(p3.calls.length, 1, 'Save asks nothing'); assert.equal(p3.writes, 2); assert.equal(p3.content, fallbackText);
    // a cancel writes nothing and says so
    await page.eval("window.__picker.mode='abort'"); await key('s', ['Control', 'Shift']); await sleep(400);
    p3 = await picker(); stage('F3 cancel', {calls: p3.calls.length, writes: p3.writes, message: await status()});
    assert.equal(await status(), 'Save As cancelled; nothing was written.'); assert.equal(p3.writes, 2); assert.equal(p3.calls[1].startIn, 'handle:chosen.json', 'Save As starts in the current file');
    // a failed write leaves the file whole and says so
    await page.eval("window.__picker.mode='ok';window.__picker.files['chosen.json']='OLD CONTENT';window.__picker.failWrite=true");
    await key('s', ['Control']); await sleep(400);
    p3 = await picker(); const failMessage = await status(); stage('F3 failed write', {writes: p3.writes, aborts: p3.aborts, content: p3.content, message: failMessage});
    assert.equal(failMessage, 'Session not saved: chosen.json could not be written (Disk full); the file is unchanged.');
    assert.equal(p3.content, 'OLD CONTENT'); assert.equal(p3.aborts, 1); assert.equal(p3.writes, 2);
    // F4: a picker that refuses falls back to the name dialog, which says so
    await page.eval("window.__picker.failWrite=false;window.__picker.mode='deny'"); before = await listDownloads();
    await key('s', ['Control', 'Shift']); await page.until("document.getElementById('save-name-dialog').open", 'F4 name dialog');
    const refused = await page.eval("document.getElementById('save-name-unavailable').textContent");
    stage('F4 picker refused', {refused});
    assert.equal(refused, "The browser's save dialog was not available (Not allowed in this browser.), so the file is downloaded instead.");
    await page.click('#save-name-download'); const f4Name = await newDownload(before);
    assert.match(f4Name, /^chosen\.json$|^optical-waveguide-session-/); assert.match(await status(), /sent to your browser's Downloads/);
    await page.eval("delete window.showSaveFilePicker");
    // round 13 (O1; pre-registered): with no picker, Save remembers the Save As name. Save and
    // Ctrl+S download under it again with no dialog; the header names the file and its state; File ›
    // Open sets the name to the opened file's; Reset design drops it, so Save asks again
    const header = () => page.eval("document.getElementById('project').textContent");
    const noDialog = async label => { for (let i = 0; i < 10; i++) { assert.equal(await page.eval("!!document.getElementById('save-name-dialog').open"), false, label + ': no name dialog'); await sleep(100); } };
    const savedWidth = name => readFile(join(downloads, name), 'utf8').then(t => JSON.parse(t).input.model.shapes[0].w);
    before = await listDownloads();
    await key('s', ['Control', 'Shift']); await page.until("document.getElementById('save-name-dialog').open", 'O1 Save As');
    await page.eval("(()=>{const i=document.getElementById('save-name-input');i.value='';i.focus();})()"); await page.call('Input.insertText', {text: 'design-a-ng'});
    await page.click('#save-name-download'); const o1First = await newDownload(before), o1FirstMessage = await status();
    assert.equal(o1First, 'design-a-ng.json'); assert.match(o1FirstMessage, /^Session file design-a-ng\.json sent to your browser's Downloads: /, 'the first download says where it went');
    assert.match(await header(), /^Optical waveguide \/ design-a-ng\.json · saved .+ \(download\)$/);
    await toGeometry(); await page.type('#shape-w', 650); await sleep(300);
    const o1Edited = await header(); assert.equal(o1Edited, 'Optical waveguide / design-a-ng.json · changed since saved');
    before = await listDownloads(); await page.click('nav [data-page=Model]'); await page.click('#menu-save');
    await noDialog('O1 Save'); const o1Second = await newDownload(before), o1SecondMessage = await status(), o1SecondHeader = await header();
    stage('O1 Save under the Save As name', {first: o1First, edited: o1Edited, second: o1Second, message: o1SecondMessage, header: o1SecondHeader});
    assert.match(o1Second, /^design-a-ng(?: \(\d\))?\.json$/); assert.equal(await savedWidth(o1Second), 650, 'the second file holds Width 650');
    assert.match(o1SecondMessage, /^Downloaded design-a-ng\.json again: current inputs, \d+ runs? and the comparison\.(?: Fields not kept for [^.]+\.)? A download cannot replace the earlier file, so your browser may name it design-a-ng \(1\)\.json\.$/);
    assert.match(o1SecondHeader, /^Optical waveguide \/ design-a-ng\.json · saved .+ \(download\)$/); assert.doesNotMatch(o1SecondHeader, /Unsaved inputs/);
    // Ctrl+S after another edit: the same, no dialog
    await toGeometry(); await page.type('#shape-w', 660); await sleep(300); before = await listDownloads();
    await page.eval("document.activeElement?.blur()"); await key('s', ['Control']); await noDialog('O1 Ctrl+S');
    const o1Third = await newDownload(before); assert.match(o1Third, /^design-a-ng(?: \(\d\))?\.json$/); assert.equal(await savedWidth(o1Third), 660);
    // Save As is prefilled with the current name; Cancel writes nothing
    await key('s', ['Control', 'Shift']); await page.until("document.getElementById('save-name-dialog').open", 'O1 Save As again');
    assert.equal(await page.eval("document.getElementById('save-name-input').value"), 'design-a-ng.json'); await page.click('#save-name-cancel'); await sleep(300);
    // File › Open of that file: the name is the opened file's; an edit and Save keep it, with no dialog
    await page.eval("document.getElementById('autosave-status').textContent=''");
    await setFile('#session-file', join(downloads, o1First));
    await answerDialogs("/^Opened design-a-ng\\.json/.test(document.getElementById('autosave-status').textContent)", 'O1 open');
    await page.click('nav [data-page=Model]'); await sleep(200); const o1Opened = await header(); assert.equal(o1Opened, 'Optical waveguide / Opened design-a-ng.json');
    await toGeometry(); await page.type('#shape-w', 640); await sleep(300);
    const o1OpenedEdited = await header(); assert.equal(o1OpenedEdited, 'Optical waveguide / design-a-ng.json · changed since opened');
    before = await listDownloads(); await page.click('#menu-save'); await noDialog('O1 Save after Open');
    const o1Fourth = await newDownload(before); assert.match(o1Fourth, /^design-a-ng(?: \(\d\))?\.json$/); assert.equal(await savedWidth(o1Fourth), 640);
    assert.match(await status(), /^Session file design-a-ng\.json sent to your browser's Downloads: .* A download cannot replace the earlier file, so your browser may name it design-a-ng \(1\)\.json\.$/);
    // Reset design drops the name: the header no longer names it and Save asks, with the model-based name
    await page.click('#reset'); await sleep(300); const o1Reset = await header();
    assert.doesNotMatch(o1Reset, /design-a-ng/); assert.match(o1Reset, /^[A-Za-z ]+ \/ (?:Unsaved inputs|No unsaved input changes|Changed since session file .*|Not saved to a file.*)$/);
    await page.click('#menu-save'); await page.until("document.getElementById('save-name-dialog').open", 'O1 Save after reset');
    assert.match(await page.eval("document.getElementById('save-name-input').value"), /^[a-z-]+-session-\d{4}-\d{2}-\d{2}-\d{4}\.json$/); await page.click('#save-name-cancel'); await sleep(300);
    stage('O1 open and reset', {opened: o1Opened, openedEdited: o1OpenedEdited, fourth: o1Fourth, reset: o1Reset});
    // F2 (round 13): a model file over 64 KiB opened through File › Open is refused by the model reader
    const bigModel = JSON.parse(await readFile(join(out, 'p1-four.json'), 'utf8')); bigModel.padding = 'x'.repeat(70 * 1024);
    const bigPath = join(out, 'model-over-64k.json'); await writeFile(bigPath, JSON.stringify(bigModel));
    await setFile('#session-file', bigPath); await page.until("/^Open failed/.test(document.getElementById('file-status').textContent)", 'F2 big model file');
    assert.equal(await status(), 'Open failed: Model file exceeds 64 KiB. Current inputs kept.'); stage('F2 model file over 64 KiB', {message: await status()});
    await noOverflow('P2 File menu');
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
