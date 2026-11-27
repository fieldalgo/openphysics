// Real-browser part of check W16: Studio's vendored three.js 0.186.1, loaded by a Studio page.
// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
//
// A local check, not wired into CI: it needs Playwright with a Chromium it can launch
// (not a repository dependency). From the repository root, with a Studio server running:
//   python -m simcase.studio --no-browser --port 8765 &
//   node tools/studio_browser/studio_vendor_three_browser.mjs http://127.0.0.1:8765 out-dir
// It opens the geometry lab (policy script-src 'self'), imports three.module.js from Studio's
// own origin, renders one box with a WebGLRenderer and reads a pixel back, then checks:
//   - the SHA-256 of every file the browser received equals tools/third_party_licenses.json;
//   - LICENSE is served;
//   - the page made 0 requests to any other origin, logged no console error, threw nothing
//     and reported no Content-Security-Policy violation.
// It writes report.json and a screenshot to out-dir.
import {createRequire} from 'node:module';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';

const require = createRequire(import.meta.url);
const {chromium} = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:8765';
const out = process.argv[3] || 'studio-vendor-three-browser';
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
await mkdir(out, {recursive: true});

const inventory = JSON.parse(await readFile(join(ROOT, 'tools', 'third_party_licenses.json'), 'utf8'));
const three = inventory.browser_served.three;
const prefix = `/vendor/three-${three.version}/`;
const origin = new URL(base).origin;
const report = {base, version: three.version, requests: [], foreign: [], console: [], pageErrors: [],
  cspViolations: [], served: {}, render: null, ok: false};

const browser = await chromium.launch();
try {
  const page = await browser.newPage({viewport: {width: 1440, height: 900}});
  page.on('request', r => {
    report.requests.push(r.url());
    // data: and blob: URLs never leave the browser; every network request must go to Studio.
    if (/^(https?|wss?):/.test(r.url()) && new URL(r.url()).origin !== origin) report.foreign.push(r.url());
  });
  page.on('console', m => { if (m.type() === 'error') report.console.push(m.text()); });
  page.on('pageerror', e => report.pageErrors.push(String(e)));
  await page.addInitScript(() => document.addEventListener('securitypolicyviolation',
    e => (window.__csp = window.__csp || []).push(e.violatedDirective + ' ' + e.blockedURI)));
  const response = await page.goto(base + '/geometry-lab');
  assert.equal(response.status(), 200);
  const policy = response.headers()['content-security-policy'] || '';
  const scriptSrc = policy.split(';').map(d => d.trim()).find(d => d.startsWith('script-src '));
  assert.equal(scriptSrc, "script-src 'self'");
  report.policy = policy;

  report.render = await page.evaluate(async url => {
    const THREE = await import(url);
    const canvas = document.createElement('canvas');
    canvas.width = 320; canvas.height = 240; canvas.id = 'w16-canvas';
    document.body.prepend(canvas);
    const renderer = new THREE.WebGLRenderer({canvas, preserveDrawingBuffer: true});
    renderer.setClearColor(0x000000, 1);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, 320 / 240, 0.1, 10);
    camera.position.set(1.6, 1.2, 2.0); camera.lookAt(0, 0, 0);
    scene.add(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial({color: 0x33aa55})));
    renderer.render(scene, camera);
    const gl = renderer.getContext(), pixel = new Uint8Array(4);
    gl.readPixels(160, 120, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
    return {revision: THREE.REVISION, centre: [...pixel], webgl2: typeof WebGL2RenderingContext !== 'undefined'
      && gl instanceof WebGL2RenderingContext};
  }, prefix + 'three.module.js');
  assert.equal(report.render.revision, three.version.split('.')[1]);
  assert.ok(report.render.centre[1] > 0, 'the box is drawn at the canvas centre');

  for (const [name, record] of Object.entries(three.files)) {
    const got = await page.evaluate(async url => {
      const r = await fetch(url);
      const bytes = new Uint8Array(await r.arrayBuffer());
      const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))]
        .map(b => b.toString(16).padStart(2, '0')).join('');
      return {status: r.status, bytes: bytes.length, sha256: digest, type: r.headers.get('content-type'),
        cache: r.headers.get('cache-control'), sniff: r.headers.get('x-content-type-options'),
        text: url.endsWith('LICENSE') ? new TextDecoder().decode(bytes) : null};
    }, prefix + name);
    report.served[name] = {status: got.status, bytes: got.bytes, sha256: got.sha256, type: got.type,
      cache: got.cache, sniff: got.sniff};
    assert.equal(got.status, 200, name);
    assert.equal(got.bytes, record.bytes, name);
    assert.equal(got.sha256, record.sha256, name);
    assert.equal(got.cache, 'no-store', name);
    assert.equal(got.sniff, 'nosniff', name);
    if (name === 'LICENSE') assert.match(got.text, /The MIT License/);
  }
  await page.screenshot({path: join(out, 'vendor-three.png')});
  report.cspViolations = await page.evaluate(() => window.__csp || []);
  assert.ok(report.requests.some(u => u === origin + prefix + 'three.module.js'));
  assert.ok(report.requests.some(u => u === origin + prefix + 'three.core.js'));
  assert.deepEqual(report.foreign, [], 'requests to another origin');
  assert.deepEqual(report.cspViolations, []);
  assert.deepEqual(report.pageErrors, []);
  assert.deepEqual(report.console, []);
  report.ok = true;
} finally {
  await writeFile(join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}
console.log(`W16 browser: ${report.requests.length} requests, ${report.foreign.length} to another origin; `
  + `three r${report.render?.revision}; served SHA-256 match for ${Object.keys(report.served).length} files`);
