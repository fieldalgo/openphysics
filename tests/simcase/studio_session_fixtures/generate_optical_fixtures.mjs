// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Writes the optical session fixtures of tests/simcase/studio_workspace_multiphysics_session.cjs
// (checks S3 and S4) with the Studio static modules of a given checkout: the files that build
// writes, what its parseSession reads from them, its open dialog texts and its refusals.
// The committed fixtures were written by the Studio before version 8 sessions (commit 0606859,
// the base of the change that added them):
//
//   git worktree add /tmp/pre 0606859
//   node tests/simcase/studio_session_fixtures/generate_optical_fixtures.mjs /tmp/pre/packages/simcase/src/simcase/studio/static <out dir>
import {mkdir, writeFile} from 'node:fs/promises';
import {join, resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import dumpModule from './dump.cjs';
const {dump} = dumpModule;

const [staticDir, outDir] = process.argv.slice(2).map(p => resolve(p));
if (!staticDir || !outDir) throw new Error('usage: <static dir> <out dir>');
const load = name => import(pathToFileURL(join(staticDir, name)).href);
const {snapshot} = await load('workspace-project.mjs');
const {opticalSettings, createSession, parseSession} = await load('workspace-notebook.mjs');
const {sessionLoadText} = await load('workspace-persistence.mjs');
await mkdir(outDir, {recursive: true});

const input = (width = 500, shapes = null) => {
  const doc = snapshot({width, voltage: 1, electric: false, heat: false, structure: false, optics: true, wavelength: 1550, coreMesh: 30},
    {materials: {Core: 'Silicon', Oxide: 'Silica', Heater: ''}, temperature: 293.15, cooling: '', fixed: '', terminal: ''});
  if (shapes) doc.model.shapes = shapes;
  return doc;
};
// a field of four nodes and two triangles per mode, with values of every sign
const field = k => ({node_coordinates: [[0, 0], [1e-6, 0], [0, 1e-6], [1e-6, 1e-6]], triangles: [[0, 1, 2], [1, 3, 2]],
  real: [[[1, 0.25 * k, 0], [0.5, -0.125, 1e-3]], [[0, 1, 2.5e-7], [-0.75, 0.3, 0]]],
  imag: [[[0, 0, 1e-9], [0, 0, 0]], [[1e-12, 0, 0], [0, -2e-3, 0]]]});
const run = (job, k, extra = {}) => ({job, completedAt: `2026-10-2${k}T0${k}:00:00.000Z`, settings: opticalSettings(1550, 30), input: input(500 + 20 * k),
  effective_index: [2.4 + 0.01 * k, 1.7 - 0.003 * k], field: field(k), origin: 'local', ...extra});
const states = {
  empty: {input: input(), runs: [], selected: null, comparison: [null, null], view: {mode: 0, component: 'magnitude', window: 'Core region'}},
  one: {input: input(520), runs: [run('0a1b2c3d', 1, {label: 'Reference', pinned: true, serverVersion: '0.0.2'})], selected: '0a1b2c3d',
    comparison: ['0a1b2c3d', null], view: {mode: 1, component: 'Ey', window: 'Full window', probe: {x: 0.25, y: -0.4, active: true}, profile: {axis: 'y', coordinate: 0.15, open: true}}},
  three: {input: input(480), runs: [run('00000001', 1), run('00000002', 2, {label: 'Wide, "core"', pinned: true}), run('abcdef12', 3, {label: 'Narrow', serverVersion: '0.0.1'})],
    selected: '00000002', comparison: ['00000001', 'abcdef12'], view: {mode: 0, component: 'magnitude', window: 'Core region', probe: {x: -1.25, y: 1.1, active: false}}},
};
const refusals = {};
for (const version of [1, 2, 3, 4, 5]) {
  try { parseSession(JSON.stringify({format: 'openphysics-studio-session', version, input: {}, runs: []})); } catch (e) { refusals[version] = e.message; }
}
await writeFile(join(outDir, 'refusals.json'), JSON.stringify(refusals, null, 1) + '\n');
for (const [name, s] of Object.entries(states)) {
  await writeFile(join(outDir, `state-${name}.json`), JSON.stringify(s, null, 1) + '\n');
  const text = JSON.stringify(createSession(s.input, s.runs, s.selected, s.comparison, s.view));
  await writeFile(join(outDir, `optical-v7-${name}.json`), text);
  // version 6: the same runs, the input as a version 6 project (no Joule inputs)
  const six = JSON.parse(text); six.version = 6; six.input.version = 6; delete six.input.model.joule; delete six.input.units.joule_length;
  const sixText = JSON.stringify(six);
  await writeFile(join(outDir, `optical-v6-${name}.json`), sixText);
  for (const [version, t] of [[7, text], [6, sixText]]) {
    const parsed = parseSession(t), recovered = parseSession(t, {recovered: true});
    const texts = {file: sessionLoadText(parsed), fileOverRuns: sessionLoadText(parsed, {runs: 2, unsaved: true}), browser: sessionLoadText(recovered, {runs: 1}, 'browser')};
    await writeFile(join(outDir, `expected-v${version}-${name}.json`), dump({parsed, recovered, texts}) + '\n');
  }
}
console.log('fixtures written to', outDir);
