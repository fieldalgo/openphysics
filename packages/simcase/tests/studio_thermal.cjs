// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// Exercise the shipped inline script: headless refusal and stale async responses.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const html = fs.readFileSync(path.join(__dirname, '../simcase/studio/static/index.html'), 'utf8');

function page() {
  const elements = new Map(), colors = [];
  const canvas = new Proxy({}, { get: (target, key) => target[key] || (() => {}),
    set: (target, key, value) => { target[key] = value; return true; } });
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      innerHTML: '', textContent: '', value: '', hidden: false, width: 640, height: 400,
      children: [], appendChild(child) { this.children.push(child); },
      querySelectorAll: () => [], getContext: () => canvas,
      getBoundingClientRect: () => ({ width: 640, height: 400 }),
    });
    return elements.get(id);
  }
  const ctx = vm.createContext({ document: { getElementById: element, querySelectorAll: () => [], createElement: () => ({}) },
    window: { addEventListener() {}, devicePixelRatio: 1 }, fetch: () => new Promise(() => {}),
    setTimeout: callback => callback(),
    capture: value => colors.push(value) });
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], ctx);
  vm.runInContext(`doc = {geometry:{domain:{xmin:0,xmax:1,ymin:0,ymax:1},shapes:[]}};
    drawTriangles = (ctx, T, nodes, tris, color) => tris.forEach((_, i) => capture(color(i)));
    drawAxes = () => {}; cmap = value => value;`, ctx);
  return { element, colors, run: code => vm.runInContext(code, ctx) };
}

const thermal = {physics:{heat1:{type:'thermal.steady2d'}},units:{length:'mm',temperature:'K'}};
const tick = () => new Promise(resolve => setImmediate(resolve));
function assertCleared(p) {
  assert.equal(p.run('resultData'), null); assert.equal(p.run('meshData'), null);
  assert.equal(p.run('currentJob'), null);
  assert.equal(p.element('runBtn').disabled, true); assert.equal(p.element('meshBtn').disabled, true);
  assert.equal(p.element('ptSel').innerHTML, ''); assert.equal(p.element('modeSel').innerHTML, '');
}
function importThermal(p) { p.run(`doc = ${JSON.stringify(thermal)}; invalidateDocument(); refresh();`); }

test('thermal JSON import clears old optical fields and makes no API request', async () => {
  const p=page();
  p.run(`resultData={old:true}; meshData={old:true}; currentJob='old'; api.post=()=>{throw Error('no thermal request')};`);
  p.element('json').value=JSON.stringify(thermal);
  await p.element('applyJson').onclick(); assertCleared(p);
  assert.match(p.element('status').textContent, /headless thermal/);
  await p.run('doRun()'); await p.run('doMesh()'); assertCleared(p);
});

test('late mesh and validation replies cannot restore stale optical state', async () => {
  for (const action of ['doMesh()', 'doValidate()']) {
    const p=page();p.run('api.post=()=>new Promise(resolve=>globalThis.reply=resolve)');
    const pending=p.run(action);importThermal(p);
    p.run("reply({ok:true,doc:{geometry:{}},stats:{nodes:3,triangles:1,min_angle:45}})");
    await pending;assertCleared(p);assert.equal(p.run('isHeadlessThermal()'),true);
  }
});

for (const stage of ['submit','status','result']) test(`late run ${stage} reply is ignored after thermal import`, async () => {
  const p=page();
  p.run(`api.post=()=>${stage==='submit'?'new Promise(resolve=>globalThis.reply=resolve)':"Promise.resolve({job:'old'})"};
    api.get=url=>${stage==='status'?'new Promise(resolve=>globalThis.reply=resolve)':"url.endsWith('/result') ? new Promise(resolve=>globalThis.reply=resolve) : Promise.resolve({status:'done',log:[]})"};`);
  const pending=p.run('doRun()');await tick();importThermal(p);
  p.run("reply({job:'old',status:'done',log:[],summary:{},fields:[]})");await pending;assertCleared(p);
});

test('pending example load and file import cannot replace a newer thermal document', async () => {
  const p=page();p.run('api.get=()=>new Promise(resolve=>globalThis.reply=resolve)');
  const pending=p.run("loadExample('old')");importThermal(p);p.run('reply({old:true})');await pending;
  assert.equal(p.run('isHeadlessThermal()'),true);assertCleared(p);
  let reply;const file={name:'old.json',text:()=>new Promise(resolve=>reply=resolve)};
  const loading=p.element('fileInput').onchange({target:{files:[file]}});importThermal(p);reply('{"old":true}');await loading;
  assert.equal(p.run('isHeadlessThermal()'),true);assertCleared(p);
});
