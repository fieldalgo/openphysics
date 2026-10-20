// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// Exercise the shipped inline script with deterministic DOM/canvas capture.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const html = fs.readFileSync(path.join(__dirname, '../../packages/simcase/src/simcase/studio/static/index.html'), 'utf8');

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

function trackedSweep() {
  const data = structuredClone(result);
  data.parameter = 'physics.em1.wavelength';
  data.values = [1500, 1550, 1600];
  // Response columns are already in branch order, even when candidate ranks swap.
  data.neff = [[2.1, 2.0], [1.95, 2.05], [1.9, 2.0]];
  data.group_index = [[4.1, 4.4], [4.2, 4.5], [4.3, 4.6]];
  data.vector_fields = [
    { ...vector, real: [[[0.6, 0, 0], [0.3, 0, 0]], [[0.8, 0, 0], [0.4, 0, 0]]],
      imag: [[[0, 0, 0.8], [0, 0, 0.4]], [[0, 0, 0.6], [0, 0, 0.3]]] },
    { ...vector, real: [[[0.8, 0, 0], [0.4, 0, 0]], [[0.6, 0, 0], [0.3, 0, 0]]],
      imag: [[[0, 0, 0.6], [0, 0, 0.3]], [[0, 0, 0.8], [0, 0, 0.4]]] },
    { ...vector, real: [[[0.8, 0, 0], [0.4, 0, 0]], [[1, 0, 0], [0.5, 0, 0]]],
      imag: [[[0, 0, 0.6], [0, 0, 0.3]], [[0, 0, 0], [0, 0, 0]]] },
  ];
  data.summary.mode_tracking = {
    method: 'electric-l2-assignment-v1',
    settings: { search_modes: 4, min_overlap: 0.8, min_margin: 0.1, degeneracy_tolerance: 1e-5 },
    points: [
      { candidate_count: 4, candidate_ranks: [1, 2], overlaps: null, margins: null },
      { candidate_count: 4, candidate_ranks: [2, 1], overlaps: [0.98, 0.97], margins: [0.7, 0.6] },
      { candidate_count: 4, candidate_ranks: [2, 1], overlaps: [0.96, 0.95], margins: [0.6, 0.5] },
    ],
  };
  return data;
}

test('sweep selectors preserve tracked branch identity and report the selected point overlap', () => {
  const p = page();
  p.run(`resultData = ${JSON.stringify(trackedSweep())}; populateResultSelectors();`);
  assert(p.element('modeSel').innerHTML.includes('branch 2'));
  p.element('ptSel').value = '1'; p.element('modeSel').value = '1'; p.element('componentSel').value = '2';
  p.run('drawField()');
  assert.deepEqual(p.colors, [0.8, 0.4]);
  assert(p.element('resInfo').textContent.includes('tracked branch 2'));
  assert(p.element('resInfo').textContent.includes('1550'));
  assert(p.element('resInfo').textContent.includes('n_eff = 2.050000'));
  assert(p.element('resInfo').textContent.includes('overlap 0.970'));
  p.colors.length = 0; p.element('ptSel').value = '0'; p.run('drawField()');
  assert.deepEqual(p.colors, [0.6, 0.3]);
  assert(p.element('resInfo').textContent.includes('seed point'));
  assert(!p.element('resInfo').textContent.includes('overlap'));
});

test('the result table shows group index for every tracked branch', () => {
  const p = page();
  p.run(`resultData = ${JSON.stringify(trackedSweep())}; fillResultTable();`);
  const table = p.element('resTable').innerHTML;
  assert(table.includes('<th>n_g branch 1</th><th>n_g branch 2</th>'));
  assert(table.includes('<td>1.950000</td><td>2.050000</td><td>4.2000</td><td>4.5000</td>'));
  assert(table.includes('Refine the wavelength spacing'));
});

test('scalar sweep table keeps its existing group-index column', () => {
  const p = page(), data = trackedSweep();
  delete data.summary.mode_tracking;
  delete data.vector_fields;
  p.run(`resultData = ${JSON.stringify(data)}; fillResultTable();`);
  const table = p.element('resTable').innerHTML;
  assert(table.includes('<th>n_g 1</th>'));
  assert(!table.includes('n_g 2'));
  assert(table.includes('<td>4.2000</td>'));
  assert(!table.includes('<td>4.5000</td>'));
});

for (const failure of ['validation', 'tracking']) {
  test(`a new run clears previous results before a ${failure} failure`, async () => {
    const p = page();
    p.run(`resultData = ${JSON.stringify(trackedSweep())}; populateResultSelectors(); fillResultTable(); drawField();`);
    const message = failure === 'validation' ? 'vector wavelength sweep needs at least three points' :
      'mode tracking failed at 1550 nm: branch 2 is ambiguous';
    if (failure === 'validation') p.run(`api.post = async () => { throw new Error(${JSON.stringify(message)}); };`);
    else p.run(`api.post = async () => ({job:'test-job'});
      api.get = async url => { if (url.endsWith('/result')) throw new Error('failed jobs must not fetch a result');
        return {status:'error', log:[], error:${JSON.stringify(message)}}; };`);
    const running = p.run('doRun()');
    assert.equal(p.run('resultData'), null);
    assert.equal(p.element('resTable').innerHTML, '');
    assert.equal(p.element('ptSel').innerHTML, '');
    assert.equal(p.element('modeSel').innerHTML, '');
    assert.equal(p.element('componentLabel').hidden, true);
    assert.equal(p.element('resInfo').textContent, 'no results available');
    await running;
    assert.equal(p.element('status').textContent, 'run failed');
    assert.equal(p.element('runBtn').disabled, false);
    assert(p.element('log').children.some(line => line.textContent.includes(message)));
    assert.equal(p.run('resultData'), null);
  });
}

function subspaceSweep() {
  const data = structuredClone(result);
  delete data.vector_fields;
  data.parameter = 'physics.em1.wavelength';
  data.values = [1500, 1550, 1600];
  data.neff = null; data.group_index = null; data.fields = [];
  data.summary.field_representation = 'vector-subspace-edge-nodal-v1';
  data.summary.mode_tracking = { method: 'electric-l2-subspace-v1', points: [
    { clusters: [{ rank: 2 }] },
    { clusters: [{ rank: 2, min_principal_squared: 0.9991 }] },
    { clusters: [{ rank: 2, min_principal_squared: 0.9987 }] }] };
  data.subspace = { field_representation: 'vector-subspace-edge-nodal-v1',
    clusters: [{ id: 1, rank: 2, columns: [0, 2] }],
    raw_neff: [[2.1, 2.09], [2.05, 2.04], [2.0, 1.99]],
    cluster_mean_neff: [[2.095], [2.045], [1.995]],
    cluster_mean_group_index: [[4.1], [4.2], [4.3]],
    density: [[[1, 0.25]], [[0.5, 1]], [[1, 0.75]]],
    density_label: 'normalized subspace field density' };
  return data;
}

test('cluster sweeps show the invariant density and cluster statistics, not member branches', () => {
  const p = page();
  p.run(`resultData = ${JSON.stringify(subspaceSweep())}; populateResultSelectors();`);
  assert.equal(p.element('componentLabel').hidden, true);
  assert(p.element('modeSel').innerHTML.includes('cluster 1 (rank 2)'));
  assert(!p.element('modeSel').innerHTML.includes('branch'));
  p.element('ptSel').value = '1'; p.element('modeSel').value = '0';
  p.run('drawField()');
  assert.deepEqual(p.colors, [0.5, 1]);
  const info = p.element('resInfo').textContent;
  assert(info.includes('normalized subspace field density, cluster 1 (rank 2)'));
  assert(info.includes('n_eff 2.040000 to 2.050000, mean 2.045000'));
  assert(info.includes('mean-index derivative n_g 4.2000'));
  assert(info.includes('smallest principal value² 0.9991'));
  assert(info.includes('not energy density'));
  p.element('ptSel').value = '0'; p.run('drawField()');
  assert(p.element('resInfo').textContent.includes('seed point (arbitrary frame)'));
});

test('cluster table reports mean index, band width and mean-index group index only', () => {
  const p = page();
  p.run(`resultData = ${JSON.stringify(subspaceSweep())}; fillResultTable();`);
  const table = p.element('resTable').innerHTML;
  assert(table.includes('<th>mean n_eff cluster 1 (rank 2)</th><th>band width 1</th><th>mean-index n_g 1</th>'));
  assert(table.includes('<td>1550</td><td>2.045000</td><td>1.00e-2</td><td>4.2000</td>'));
  assert(!table.includes('branch'));
  assert(table.includes('no member group index'));
});

test('an unknown cluster layout version is refused instead of displayed', () => {
  const p = page(), data = subspaceSweep();
  data.subspace.field_representation = 'vector-subspace-edge-nodal-v2';
  assert.throws(() => p.run(`resultData = ${JSON.stringify(data)}; populateResultSelectors();`), /unsupported cluster result layout/);
});

test('a failed cluster run clears the previous cluster display', async () => {
  const p = page();
  p.run(`resultData = ${JSON.stringify(subspaceSweep())}; populateResultSelectors(); fillResultTable(); drawField();`);
  const message = 'vector subspace sweep at wavelength 1600 nm: cluster 1 has weakest principal value squared 0.1';
  p.run(`api.post = async () => ({job:'test-job'});
    api.get = async url => { if (url.endsWith('/result')) throw new Error('failed jobs must not fetch a result');
      return {status:'error', log:[], error:${JSON.stringify(message)}}; };`);
  const running = p.run('doRun()');
  assert.equal(p.run('resultData'), null);
  assert.equal(p.element('resTable').innerHTML, '');
  assert.equal(p.element('modeSel').innerHTML, '');
  await running;
  assert.equal(p.element('status').textContent, 'run failed');
  assert(p.element('log').children.some(line => line.textContent.includes(message)));
});

test('circles on a hidden zero-size canvas do not throw', () => {
  const p = page();
  // Browsers reject a negative arc radius; a zero-size canvas gives a negative scale.
  p.run(`const strict = { beginPath() {}, arc(x, y, r) { if (r < 0) throw new RangeError('negative radius ' + r); } };
    shapePath(strict, { type: 'circle', cx: 0, cy: 0, r: 4 }, transformFor({ xmin: -20, xmax: 20, ymin: -20, ymax: 20 }, 0, 0));`);
});
