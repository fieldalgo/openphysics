// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// Exercise the shipped inline script with deterministic DOM/canvas capture.
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
      querySelectorAll: () => [], getContext: () => canvas,
      getBoundingClientRect: () => ({ width: 640, height: 400 }),
    });
    return elements.get(id);
  }
  const ctx = vm.createContext({ document: { getElementById: element, querySelectorAll: () => [] },
    window: { addEventListener() {}, devicePixelRatio: 1 }, fetch: () => new Promise(() => {}),
    capture: value => colors.push(value) });
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], ctx);
  vm.runInContext(`doc = {geometry:{domain:{xmin:0,xmax:1,ymin:0,ymax:1},shapes:[]}};
    drawTriangles = (ctx, T, nodes, tris, color) => tris.forEach((_, i) => capture(color(i)));
    drawAxes = () => {}; cmap = value => value;`, ctx);
  return { element, colors, run: code => vm.runInContext(code, ctx) };
}

const vector = { location: 'triangle_centroids', components: ['Ex', 'Ey', 'Ez'],
  real: [[[0.6, 0, 0], [0.3, 0, 0]]], imag: [[[0, 0, 0.8], [0, 0, 0.4]]] };
const result = { nodes:[[0,0],[1,0],[1,1],[0,1]], triangles:[[0,1,2],[0,2,3]],
  fields:[], vector_fields:[vector], parameter:null, values:[1550], neff:[[2.05]],
  summary:{units:{length:'nm'}}, timings:{mesh:0,solve:0}, group_index:null };

test('complex vector components retain their common magnitude scale', () => {
  const p = page();
  p.run(`resultData = ${JSON.stringify(result)}; populateResultSelectors(); drawField();`);
  assert.equal(p.element('componentLabel').hidden, false);
  assert.deepEqual(p.colors, [1, 0.5]);
  p.colors.length = 0; p.element('componentSel').value = '2'; p.run('drawField()');
  assert.deepEqual(p.colors, [0.8, 0.4]);
  assert(p.element('resInfo').textContent.includes('|Ez|'));
  assert(p.element('resInfo').textContent.includes('nm'));
  p.colors.length = 0; p.element('componentSel').value = '0'; p.run('drawField()');
  assert.deepEqual(p.colors, [0.6, 0.3]);
});

test('vector triangle samples are not averaged through shared nodes', () => {
  const p = page(), data = structuredClone(result);
  data.vector_fields[0].real = [[[1, 0, 0], [0, 0, 0]]];
  data.vector_fields[0].imag = [[[0, 0, 0], [0, 0, 0]]];
  p.run(`resultData = ${JSON.stringify(data)}; populateResultSelectors(); drawField();`);
  assert.deepEqual(p.colors, [1, 0]);
});

test('scalar responses still use nodal fields and hide the component selector', () => {
  const p = page(), data = structuredClone(result);
  delete data.vector_fields;
  data.fields = [[[1, 1, 1, 1]]];
  p.run(`resultData = ${JSON.stringify(data)}; populateResultSelectors(); drawField();`);
  assert.equal(p.element('componentLabel').hidden, true);
  assert.deepEqual(p.colors, [1, 1]);
});
