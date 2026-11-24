// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
//
// The field size of open-boundary runs (lab design "Field size of open-boundary runs", slices S1
// and S2): the T16 and T19 runs and the six-run workload, run by the engine on this machine and
// kept as Studio keeps a new result, then written as Studio writes a session.
//
//   node tools/studio_open_field_size.mjs engine <dir> [--python python]
//   node tools/studio_open_field_size.mjs measure <dir> <out> [--static <studio static dir>] [--crop centroid|meets [--margin <nm>]]
//   node tools/studio_open_field_size.mjs checks <dir> <out> [the same options]
//
// `engine` solves the six documents (the ones Studio's builder writes) with the Studio server's own
// optical job (simcase.studio.server._run_job) and stores each result as /api/jobs/<id>/result
// sends it (<dir>/<case>.result.json). It takes several minutes; run it once.
// `measure` turns each result into a run with the page modules of --static (default: this
// checkout's), as the page's result handler does (openResultValues, readOpticalField, validateRun),
// and writes into <out> (new or empty): each case alone as a session, the workload session, and
// report.json with the sizes, the triangle counts, Save session, browser recovery, the project
// entry and the round trip of the workload. `checks` writes checks.json: the values the crop must
// keep (TE fraction, A_eff, matching eta, normalized field, probe). Run them with the modules of two
// commits to compare them (e.g. a `git worktree` of the base); on a base without the crop, --crop
// applies one here: centroid (C5), meets (the window, C5'), or meets with --margin (C5'': the window
// grown by that margin; Studio's is 1/150 of the window's longer side, 20 nm for 3 × 2.4 µm).
//
// The cases (decision of 2026-11-24): a 500 × 220 nm silicon strip in silica, 1550 nm, core mesh
// 30 nm; T16/T18 add a silicon substrate x −1500, y −1200, 3000 × 700 nm under it.
//   strip30, strip40  the template strip, closed window, core mesh 30 and 40 nm, 2 modes
//   t18closed         the T18 structure in a closed window, 2 modes
//   t16               T18 open on all four edges (PML 1 µm, both searches), 2 modes (pinned)
//   t18open           t16 with Also compute group index (pinned)
//   t19               t16 with 3 modes and the group index (selected)
// The workload is these six, appended in this order, t16 and t18open pinned and t19 selected.
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {mkdir, readdir, readFile, writeFile} from 'node:fs/promises';
import {join, resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const ROOT = resolve(new URL('..', import.meta.url).pathname);
const [command, ...rest] = process.argv.slice(2);
const option = (name, fallback) => {const i = rest.indexOf(name); return i < 0 ? fallback : rest[i + 1];};
const VALUED = ['--static', '--python', '--crop', '--margin'];
const positional = rest.filter((v, i) => !v.startsWith('--') && !(i > 0 && VALUED.includes(rest[i - 1])));
const STATIC = resolve(option('--static', join(ROOT, 'packages/simcase/src/simcase/studio/static')));
const CROP = option('--crop', null), MARGIN = Number(option('--margin', '0'));
const page = name => import(pathToFileURL(join(STATIC, name)).href);

const ALL = {left: 'open', right: 'open', bottom: 'open', top: 'open'};
const strip = {name: 'Core', type: 'rect', material: 'Silicon', x: -250, y: 0, w: 500, h: 220};
const substrate = {name: 'Substrate', type: 'rect', material: 'Silicon', x: -1500, y: -1200, w: 3000, h: 700};
export const CASES = {
  strip30: {shapes: [strip], coreMesh: 30, modeCount: 2},
  strip40: {shapes: [strip], coreMesh: 40, modeCount: 2},
  t18closed: {shapes: [strip, substrate], coreMesh: 30, modeCount: 2},
  t16: {shapes: [strip, substrate], coreMesh: 30, modeCount: 2, open: ALL, pinned: true},
  t18open: {shapes: [strip, substrate], coreMesh: 30, modeCount: 2, open: ALL, groupIndex: true, pinned: true},
  t19: {shapes: [strip, substrate], coreMesh: 30, modeCount: 3, open: ALL, groupIndex: true},
};
// fixed job ids (8 hex digits, as the server's), in case order
const JOBS = Object.fromEntries(Object.keys(CASES).map((name, i) => [name, 'a0000000'.slice(0, 7) + (i + 1)]));
const SETUP = {materials: {Core: 'Silicon', Oxide: 'Silica', Heater: ''}};
const state = c => ({electric: false, heat: false, structure: false, optics: true, wavelength: 1550, coreMesh: c.coreMesh,
  modeCount: c.modeCount, shapes: c.shapes, ...(c.groupIndex ? {groupIndex: true} : {}), ...(c.open ? {openBoundary: {edges: c.open}} : {})});

const ENGINE = String.raw`
import json, sys
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from simcase import Document
from simcase.studio import server
doc = Document.from_dict(json.loads(sys.stdin.read()))
server._jobs["job"] = {"status": "running", "log": [], "result": None, "error": None}
server._run_job("job", doc)
job = server._jobs["job"]
if job["status"] != "done":
    sys.exit("engine: " + str(job["error"]))
# the body /api/jobs/<id>/result sends (FastAPI's encoder and JSON response)
sys.stdout.buffer.write(JSONResponse(jsonable_encoder(job["result"])).body)
`;

async function engine(dir) {
  const python = option('--python', 'python');
  const O = await page('workspace-optical.mjs');
  await mkdir(dir, {recursive: true});
  for (const [name, c] of Object.entries(CASES)) {
    const doc = JSON.stringify(O.opticalDocument(state(c), SETUP));
    await writeFile(join(dir, name + '.document.json'), doc);
    const started = Date.now();
    const done = spawnSync(python, ['-I', '-c', ENGINE], {input: doc, maxBuffer: 1 << 30, cwd: ROOT,
      env: {...process.env, OPENBLAS_NUM_THREADS: '1', OMP_NUM_THREADS: '1', MKL_NUM_THREADS: '1'}});
    if (done.status !== 0) throw new Error(name + ': ' + done.stderr.toString());
    await writeFile(join(dir, name + '.result.json'), done.stdout);
    console.log(name, done.stdout.length, 'B', ((Date.now() - started) / 1000).toFixed(0), 's');
  }
}

/** The run the page keeps of a result: the result handler of workspace-app.mjs (onResult), step by step. */
export async function keptRun(result, name, {serverVersion = '0.0.2'} = {}) {
  const N = await page('workspace-notebook.mjs'), R = await page('workspace-open-run.mjs'), F = await page('workspace-field.mjs'), P = await page('workspace-project.mjs');
  const c = CASES[name], asked = c.modeCount, e = result.effective_index;
  const re = Array.isArray(e?.values) ? e.values[0] : e?.re?.[0], im = Array.isArray(e?.im) ? e.im[0] : null;
  const ob = c.open ? {edges: c.open, target: R.effectiveTarget({edges: c.open}, c.shapes)} : null;
  const open = ob ? R.openResultValues(result, re, im, ob.target) : null;
  const kept = open ? open.re : re, keptIm = open ? open.im : im;
  const input = P.validateProject({format: 'openphysics-studio-workspace', version: 7, units: UNITS, model: {...MODEL, coreMesh: c.coreMesh, shapes: c.shapes}, setup: STUDY_SETUP});
  const closed = N.opticalSettings(1550, c.coreMesh, asked), settings = open ? R.openSettings(closed, ob, c.shapes) : closed;
  const run = N.validateRun({job: JOBS[name], completedAt: '2026-11-24T00:00:00.000Z', settings, input,
    effective_index: keptIm ? {re: [...kept], im: [...keptIm]} : [...kept], field: F.readOpticalField(open ? open.data : result, kept.length, {open: !!open}),
    origin: 'local', serverVersion,
    ...(open ? {open_boundary: open.record, ...R.keptValues({...N.engineRunValues(result.summary, re.length), ...N.engineGroupIndex(result.summary, re.length)}, open.keep)}
      : {...N.engineRunValues(result.summary, re.length), ...N.engineGroupIndex(result.summary, re.length)})});
  if (c.pinned) run.pinned = true;
  return run;
}
const UNITS = {height: 'nm', width: 'nm', wavelength: 'nm', core_mesh: 'nm', shapes: 'nm', thermal_length: 'mm', joule_length: 'mm', voltage: 'V', temperature: 'K'};
let MODEL, STUDY_SETUP;
async function template() {
  // the other inputs of a run (thermal and Joule panels): those of the committed version 10 fixture
  const fixture = JSON.parse(await readFile(join(ROOT, 'tests/simcase/studio_session_fixtures/optical-v10-open-f8ece10.json'), 'utf8'));
  MODEL = fixture.runs[0].input.model; STUDY_SETUP = fixture.runs[0].input.setup;
}

export async function workload(dir) {
  await template();
  const N = await page('workspace-notebook.mjs');
  const runs = {};
  for (const name of Object.keys(CASES)) runs[name] = await keptRun(JSON.parse(await readFile(join(dir, name + '.result.json'), 'utf8')), name);
  if (CROP) {
    const M = await page('workspace-modes.mjs'), F = await page('workspace-field.mjs');
    for (const run of Object.values(runs)) if (run.settings.boundary === 'PML') {
      const b = M.physicalBounds(run.open_boundary), m = MARGIN * 1e-9, grown = [[b[0][0] - m, b[0][1] - m], [b[1][0] + m, b[1][1] + m]];
      const f = cropField(run.field, CROP === 'meets' ? grown : b, CROP === 'meets' ? meetsWindow : M.physicalWindow);
      run.field = F.readOpticalField({vector_fields: [{...F.PML_FIELD_METADATA, real: f.real, imag: f.imag}], node_coordinates: f.node_coordinates, field_units: {node_coordinates: 'm'}, triangles: f.triangles}, f.real.length, {open: true});
    }
  }
  let list = [];
  for (const name of Object.keys(CASES)) list = N.appendRun(list, runs[name]);
  return {runs, list};
}

const bytes = text => Buffer.byteLength(text, 'utf8');
async function measure(dir, out) {
  await mkdir(out, {recursive: true});
  if ((await readdir(out)).length) throw new Error(out + ' is not empty');
  const N = await page('workspace-notebook.mjs'), P = await page('workspace-project.mjs');
  const {runs, list} = await workload(dir);
  const view = {mode: 0, component: 'magnitude', window: 'Core region'};
  const report = {static: STATIC, crop: CROP, cases: {}, workload: {}};
  for (const [name, run] of Object.entries(runs)) {
    const input = run.settings.boundary === 'PML' ? P.withStudy(run.input, {modeCount: CASES[name].modeCount, groupIndex: !!CASES[name].groupIndex, openBoundary: {edges: CASES[name].open}}) : run.input;
    const text = N.sessionText(input, [run], run.job, [run.job, null], view);
    await writeFile(join(out, name + '.session.json'), text);
    const field = JSON.stringify({real: run.field.real, imag: run.field.imag});
    report.cases[name] = {bytes: bytes(text), triangles: run.field.triangles.length, nodes: run.field.node_coordinates.length,
      fieldShare: +(bytes(field) / bytes(text)).toFixed(4), open: run.settings.boundary === 'PML'};
  }
  const selected = runs.t19.job, comparison = [runs.t16.job, runs.t19.job];
  const input = P.withStudy(runs.t19.input, {modeCount: 3, groupIndex: true, openBoundary: {edges: ALL}});
  const write = N.writeOpticalSession(input, list, selected, comparison, view);
  report.workload = {order: list.map(r => r.job), pinned: list.filter(r => r.pinned).map(r => r.job), selected,
    bytes: write.bytes, fits: write.ok, notKept: write.ok ? write.notKept : write.reduced?.notKept ?? null, refusal: write.refusal ?? null,
    limit: N.MAX_SESSION_BYTES};
  const text = N.sessionText(input, list, selected, comparison, view);
  await writeFile(join(out, 'workload.session.json'), text);
  // F1: browser recovery keeps the text with every field; F1/F5: the project entry written and read
  // back; F5: the file read and written again is the first write but for origin and its digest
  let recovered = null, recoveryError = null;
  try {recovered = N.captureSession(input, list, selected, comparison, view)();} catch (error) {recoveryError = error.message;}
  const PF = await page('workspace-project-file.mjs');
  let project;
  try {
    project = PF.writeProject({name: 'Field size', savedAt: '2026-11-24T00:00:00.000Z', studio: '0.0.2', active: 'm1',
      entries: [PF.projectEntry({id: 'm1', kind: 'workspace', title: 'Optical waveguide', card: 'optical', text})]});
  } catch (error) {project = {ok: false, error: error.message};}
  let projectRead = null;
  if (project.ok) {const r = PF.readProject(project.text); projectRead = {models: r.models.length, same: r.models[0].text === text, bytes: bytes(project.text)};}
  report.workload.recovery = recovered === null ? {error: recoveryError} : {bytes: bytes(recovered), sameAsSave: recovered === text, withEveryField: JSON.parse(recovered).runs.every(r => 'field' in r)};
  report.workload.project = {written: project.ok, error: project.error ?? null, read: projectRead};
  if (write.ok) {
    const read = N.parseSession(text), again = N.sessionText(read.input, read.runs, read.selected, read.comparison, read.view);
    const strip = t => JSON.parse(t).runs.map(({origin, digest, ...r}) => JSON.stringify(r)).join('\n') + JSON.stringify({...JSON.parse(t), runs: null});
    const third = (() => {const r = N.parseSession(again); return N.sessionText(r.input, r.runs, r.selected, r.comparison, r.view);})();
    report.workload.roundTrip = {sameButOrigin: strip(again) === strip(text), origins: JSON.parse(again).runs.map(r => r.origin), againByteForByte: third === again,
      triangles: read.runs.map(r => r.field?.triangles.length ?? null)};
  } else report.workload.roundTrip = null;
  await writeFile(join(out, 'report.json'), JSON.stringify(report, null, 1) + '\n');
  console.log(JSON.stringify(report, null, 1));
}

/** The values S1 must keep (checks F2 to F4) of the runs as the page modules of --static keep them:
 * per open run and mode the engine's and Studio's TE fraction and A_eff (Studio's on the physical
 * window), the matching eta of three pairs, the normalized |E| and Ex/Ey/Ez of each window triangle
 * (by its centroid) and the probe at the window's corners and edge midpoints (µm). --crop applies
 * a crop rule here (the prediction for a base without S1). */
async function checks(dir, out) {
  const M = await page('workspace-modes.mjs'), X = await page('workspace-match.mjs'), F = await page('workspace-field.mjs'), Q = await page('workspace-probe.mjs');
  const {runs} = await workload(dir);
  const result = {static: STATIC, crop: CROP, modes: {}, eta: {}, field: {}, probe: {}};
  for (const name of ['t16', 't18open', 't19']) {
    const run = runs[name], bounds = M.physicalBounds(run.open_boundary), window = M.physicalWindow(run.field, bounds);
    result.modes[name] = run.effective_index.map((_, i) => ({
      engineTe: run.te_polarization_fraction?.[i] ?? null, engineArea: run.effective_area?.[i] ?? null,
      studioTe: M.teFraction(run.field, i, window), studioArea: M.effectiveArea(run.field, i, window)}));
    result.field[name] = {triangles: run.field.triangles.length, inWindow: window.filter(Boolean).length};
  }
  for (const [a, b] of [['t16', 't19'], ['t18closed', 't18open'], ['strip30', 't18closed']]) {
    const m = X.opticalMatch(runs[a], runs[b]);
    result.eta[a + '/' + b] = {pairs: m.pairs ?? null, rows: m.rows?.map(r => ({unit: r.unit, match: r.match, best: r.best})) ?? null, error: m.error ?? null, disabled: m.disabled ?? null};
  }
  // the normalized values of mode 1 of T16 keyed by centroid, inside the window
  const run = runs.t16, bounds = M.physicalBounds(run.open_boundary), window = M.physicalWindow(run.field, bounds);
  const X0 = run.field.node_coordinates, key = t => [0, 1].map(k => (X0[t[0]][k] + X0[t[1]][k] + X0[t[2]][k]) / 3).join(',');
  for (const component of ['magnitude', 'Ex', 'Ey', 'Ez']) for (let mode = 0; mode < 2; mode++) {
    const {values, maximum} = F.fieldScalars(run.field, mode, component);
    const inside = {};run.field.triangles.forEach((t, i) => {if (window[i]) inside[key(t)] = values[i];});
    result.field.t16[component + mode] = {maximum, sha: sha(JSON.stringify(Object.entries(inside).sort(([p], [q]) => p < q ? -1 : p > q ? 1 : 0))), count: Object.keys(inside).length};
    if (mode === 0) for (const [x, y] of [[-1.5, -1.2], [1.5, -1.2], [-1.5, 1.2], [1.5, 1.2], [0, -1.2], [0, 1.2], [-1.5, 0], [1.5, 0]]) {
      const p = Q.probeField(run.field, values, x, y);
      result.probe[component + ' ' + x + ',' + y] = p ? {value: p.value, centroid: p.centroid} : null;
    }
  }
  await mkdir(out, {recursive: true});
  await writeFile(join(out, 'checks.json'), JSON.stringify(result, null, 1) + '\n');
  console.log(JSON.stringify({modes: result.modes, field: result.field, probe: result.probe}, null, 1));
}
/** Whether each triangle meets the closed window bounds (separating axes: x, y and its edge normals), metres. */
function meetsWindow(field, [[x0, y0], [x1, y1]]) {
  const corners = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
  return field.triangles.map(t => {
    const p = t.map(k => field.node_coordinates[k]), xs = p.map(q => q[0]), ys = p.map(q => q[1]);
    if (Math.max(...xs) < x0 || Math.min(...xs) > x1 || Math.max(...ys) < y0 || Math.min(...ys) > y1) return false;
    for (let e = 0; e < 3; e++) {
      const a = p[e], c = p[(e + 1) % 3], o = p[(e + 2) % 3], nx = c[1] - a[1], ny = a[0] - c[0], side = q => (q[0] - a[0]) * nx + (q[1] - a[1]) * ny, so = side(o);
      if (corners.every(q => so > 0 ? side(q) < 0 : side(q) > 0)) return false;
    }
    return true;
  });
}
const sha = text => createHash('sha256').update(text).digest('hex');
/** A crop rule written out here (for --crop): keep the triangles the rule keeps (physicalWindow: the
 * centroid inside the bounds; meetsWindow: meeting them), in order; nodes renumbered in first-use
 * order; values unchanged. */
function cropField(field, bounds, physicalWindow) {
  const inside = physicalWindow(field, bounds), index = new Map(), nodes = [], triangles = [];
  field.triangles.forEach((t, i) => {if (inside[i]) triangles.push(t.map(n => {if (!index.has(n)) {index.set(n, nodes.length); nodes.push(field.node_coordinates[n]);} return index.get(n);}));});
  const keep = mode => mode.filter((_, i) => inside[i]);
  return {node_coordinates: nodes, triangles, real: field.real.map(keep), imag: field.imag.map(keep)};
}

if (command === 'engine' && positional[0]) await engine(resolve(positional[0]));
else if (command === 'checks' && positional[1]) await checks(resolve(positional[0]), resolve(positional[1]));
else if (command === 'measure' && positional[1]) await measure(resolve(positional[0]), resolve(positional[1]));
else if (command) {console.error('usage: engine <dir> | measure <dir> <out> [--static dir]'); process.exit(2);}
