// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// Run with node --test packages/simcase/tests/studio_units.cjs (no npm dependencies).
// Execute the actual page script; capture text written to its canvas and DOM.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const html = fs.readFileSync(path.join(__dirname, '../simcase/studio/static/index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const example = JSON.parse(fs.readFileSync(path.join(__dirname, '../examples/slab_te_check.json'), 'utf8'));

function page() {
  const elements = new Map(), text = [];
  const canvas = new Proxy({ fillText: value => text.push(String(value)) }, {
    get: (target, key) => key in target ? target[key] : () => {},
  });
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      innerHTML: '', textContent: '', value: '0', width: 640, height: 400,
      querySelectorAll: () => [], getContext: () => canvas,
      getBoundingClientRect: () => ({ width: 640, height: 400 }),
    });
    return elements.get(id);
  }
  const context = vm.createContext({
    document: { getElementById: element, querySelectorAll: () => [] },
    window: { addEventListener() {}, devicePixelRatio: 1 },
    // Leave the asynchronous startup idle; each test supplies its own document/result.
    fetch: () => new Promise(() => {}),
  });
  vm.runInContext(script, context);
  return { element, text, run: code => vm.runInContext(code, context) };
}

for (const [declaration, label] of [
  ['nm', 'nm'], ['um', 'um'], ['µm', 'µm'], ['m', 'm'], [{ in_m: 1e-10 }, '1e-10 m'],
  [{ in_m: 1.23456789e-10 }, '1.23456789e-10 m'],
]) {
  test(`document and result labels use ${label}`, () => {
    const p = page();
    const doc = structuredClone(example);
    doc.units.length = declaration;
    p.run(`doc = ${JSON.stringify(doc)}; drawGeometry(); renderProps();`);
    assert(p.text.includes(`x: -0.5 … 0.5 (${label})`));
    assert(p.text.includes(`y: -1.2 … 1.2 (${label})`));
    assert(p.element('props').innerHTML.includes(`length unit: ${label}`));
    p.run("selected = 'physics:em1'; renderProps();");
    assert(p.element('props').innerHTML.includes(`wavelength (${label})`));

    const result = {
      parameter: 'physics.em1.wavelength', values: [1.5, 1.6],
      neff: [[2.8], [2.7]], group_index: null, timings: { mesh: 0, solve: 0 },
      nodes: [[0, 0], [1, 0], [0, 1]], triangles: [[0, 1, 2]],
      fields: [[[1, 2, 3]], [[2, 3, 4]]], summary: { units: doc.units },
    };
    p.run(`resultData = ${JSON.stringify(result)};
      populateResultSelectors(); drawField(); drawSweep(); fillResultTable();`);
    assert(p.element('resInfo').textContent.includes(`physics.em1.wavelength (${label})`));
    assert(p.text.includes(`physics.em1.wavelength (${label})`));
    assert(p.element('resTable').innerHTML.includes(`<th>physics.em1.wavelength (${label})</th>`));
    assert(p.element('ptSel').innerHTML.includes(`1.5 [${label}]`));

    // A completed result carries its units; an edited document cannot relabel it.
    p.text.length = 0;
    p.run("doc.units.length = 'km'; drawField(); fillResultTable();");
    assert(p.text.includes(`x: -0.5 … 0.5 (${label})`));
    assert(p.element('resTable').innerHTML.includes(`(${label})`));

    p.run("resultData.parameter = null; resultData.values = [1.55]; populateResultSelectors(); drawField(); fillResultTable();");
    assert(p.element('resInfo').textContent.includes(`λ (${label}) = 1.55`));
    assert(p.element('resTable').innerHTML.includes(`<th>λ (${label})</th>`));

    p.run("resultData.parameter = 'physics.em1.num_modes'; resultData.values = [1, 2]; drawSweep(); fillResultTable();");
    assert(p.element('resTable').innerHTML.includes('<th>physics.em1.num_modes</th>'));
    assert(p.text.includes('physics.em1.num_modes'));
  });
}

test('material database wavelengths retain their native micrometre unit', () => {
  const p = page();
  p.run(`doc = ${JSON.stringify(example)}; doc.units.length = 'nm';
    materials = [{name: 'Si', aliases: [], range_um: [1.2, 14], source: 'fixture'}];
    selected = 'materials'; renderProps();`);
  assert(p.element('props').innerHTML.includes('1.2–14 um'));
});
