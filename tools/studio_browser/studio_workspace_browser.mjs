// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Real-browser check of the installed Studio workspace (/workspace) on this OS:
// two optical designs, Compare, Save session, a server restart with the page
// open, recovery from the start page. Drives a preinstalled Chrome through the
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
  click(selector) { return this.eval(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw Error('missing '+${JSON.stringify(selector)});e.click();return true})()`); }
  // Typing as a user does: focus, select, insert text, leave the field.
  async type(selector, text) {
    await this.eval(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.focus();e.select();return true})()`);
    await this.call('Input.insertText', {text: String(text)});
    await this.eval(`(()=>{document.querySelector(${JSON.stringify(selector)}).blur();return true})()`);
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
  const delta = () => page.eval("(document.getElementById('canvas').innerText.match(/Δn_eff \\(B − A\\), candidate rank 1: (-?[0-9]+\\.[0-9]+)/)||[])[1]||null");

  await page.call('Page.navigate', {url: base + '/workspace'});
  await page.until("/^Connected/.test(document.getElementById('connection-status').textContent)&&!!document.querySelector('[data-template=optical]')", 'connected start page');
  stage('start page', {heading: await page.eval("document.querySelector('#canvas h2').textContent"), resumeCard: await page.eval("!!document.querySelector('.resume-card')")});
  await page.click('[data-template=optical]'); await page.until("!!document.querySelector('#shape-w')", 'optical template');
  await page.type('#shape-w', 600); await page.type('#shape-h', 300); await runAndWait();
  await toGeometry(); await page.type('#shape-w', 700); await runAndWait();
  await page.click('nav [data-page=Compare]'); await sleep(500);
  const before = await delta(); assert.ok(before, 'comparison shows a delta n_eff');
  stage('two designs compared', {deltaNeff: before});
  await page.screenshot('compare');
  await page.click('#save-session');
  let sessionFile;
  for (let i = 0; i < 100 && !sessionFile; i++) { sessionFile = (await readdir(downloads)).find(f => f.endsWith('.json')); if (!sessionFile) await sleep(100); }
  assert.ok(sessionFile, 'Save session downloaded a file');
  const session = JSON.parse(await readFile(join(downloads, sessionFile), 'utf8'));
  stage('session saved', {file: sessionFile, runs: session.runs?.length, header: await page.eval("document.getElementById('project').textContent")});
  assert.equal(session.runs?.length, 2);
  await page.until("/Browser recovery saved/.test(document.getElementById('autosave-status').textContent)", 'browser recovery saved', 20000);

  // Restart with the page open: Run reconnects and asks to run again.
  stage('server stopped', await stopServer(server));
  server = await startServer('server-2');
  await toGeometry(); await page.click('#run-optical');
  await page.until("/Studio was restarted/.test(document.getElementById('job-message').textContent)&&/^Connected/.test(document.getElementById('connection-status').textContent)", 'reconnect after restart', 20000);
  stage('reconnected after restart', {message: await page.eval("document.getElementById('job-message').textContent")});

  // Reload: the start page offers the last session; recovering it restores the comparison.
  await page.call('Page.reload');
  await page.until("!!document.querySelector('#resume-latest')", 'resume card');
  const card = await page.eval("(()=>{const r=document.querySelector('.resume-card').getBoundingClientRect();return {top:Math.round(r.top),bottom:Math.round(r.bottom),inView:r.top>=0&&r.bottom<=innerHeight}})()");
  stage('resume card', card); assert.ok(card.inView, 'resume card inside the first viewport');
  await page.screenshot('resume-card');
  await page.click('#resume-latest'); await page.until("!!document.querySelector('dialog[open] #confirm-load')", 'replacement dialog');
  await page.click('dialog[open] #confirm-load'); await sleep(800);
  await page.click('nav [data-page=Compare]'); await sleep(500);
  const after = await delta();
  stage('comparison recovered', {deltaNeff: after}); assert.equal(after, before);
  assert.deepEqual(report.exceptions, [], 'no uncaught page exceptions');
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
