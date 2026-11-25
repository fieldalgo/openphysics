// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
//
// Engine results for the run-retention checks (design "Keeping more runs"): K1 (sizes at 20 runs of
// the T18 mix) and K5 (a recomputed field equals the original). Each case is the document Studio's
// builder writes for it (workspace-optical.mjs), solved by the Studio server's own optical job
// (simcase.studio.server._run_job), as tools/studio_open_field_size.mjs does.
//
//   node tools/studio_run_retention.mjs engine <dir> <tag> [--threads default] [--python python] [--only a,b]
//   node tools/studio_run_retention.mjs k1 <dir> <out>
//   node tools/studio_run_retention.mjs k5 <dir> <out> [<tag> [<base tag> [cases]]]   (default: one-b against one-a, every case)
//
// writes <dir>/<case>.document.json and <dir>/<case>.<tag>.result.json (the body /api/jobs/<id>/result
// sends) and appends one line per case to <dir>/<tag>.times.json. By default the solve is single
// threaded (OMP_NUM_THREADS, OPENBLAS_NUM_THREADS and MKL_NUM_THREADS = 1, as the agent rounds run);
// --threads default leaves the three variables as they are. The K1 and K5 tests read <dir> from
// STUDIO_RETENTION_RESULTS (tests/simcase/studio_run_retention_engine.cjs).
//
// The cases: a 500 × 220 nm silicon strip in silica over a silicon substrate x −1500, y −1200,
// 3000 × 700 nm (T18), 1550 nm, core mesh 30 nm.
//   t18closed2   closed window, 2 modes
//   t18closed4   closed window, 4 modes
//   t18near      closed window, Search near n_eff 2.46, 4 modes
//   t16          open on all four edges (PML 1 µm), 2 modes
//   t18open      t16 with Also compute group index
import {spawnSync} from 'node:child_process';
import {appendFile, mkdir, readFile, writeFile} from 'node:fs/promises';
import {join, resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const ROOT = resolve(new URL('..', import.meta.url).pathname);
const STATIC = join(ROOT, 'packages/simcase/src/simcase/studio/static');
const page = name => import(pathToFileURL(join(STATIC, name)).href);
const ALL = {left: 'open', right: 'open', bottom: 'open', top: 'open'};
const strip = {name: 'Core', type: 'rect', material: 'Silicon', x: -250, y: 0, w: 500, h: 220};
const substrate = {name: 'Substrate', type: 'rect', material: 'Silicon', x: -1500, y: -1200, w: 3000, h: 700};
export const CASES = Object.freeze({
  t18closed2: {shapes: [strip, substrate], coreMesh: 30, modeCount: 2},
  t18closed4: {shapes: [strip, substrate], coreMesh: 30, modeCount: 4},
  t18near: {shapes: [strip, substrate], coreMesh: 30, modeCount: 4, searchTarget: 2.46},
  t16: {shapes: [strip, substrate], coreMesh: 30, modeCount: 2, open: ALL},
  t18open: {shapes: [strip, substrate], coreMesh: 30, modeCount: 2, open: ALL, groupIndex: true},
});
export const SETUP = Object.freeze({materials: {Core: 'Silicon', Oxide: 'Silica', Heater: ''}});
/** The page state of a case (the Model tab's inputs). */
export const caseState = c => ({electric: false, heat: false, structure: false, optics: true, wavelength: 1550, coreMesh: c.coreMesh,
  modeCount: c.modeCount, shapes: c.shapes, ...(c.groupIndex ? {groupIndex: true} : {}), ...(c.open ? {openBoundary: {edges: c.open}} : {}),
  ...(c.searchTarget != null ? {searchTarget: c.searchTarget} : {})});

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
sys.stdout.buffer.write(JSONResponse(jsonable_encoder(job["result"])).body)
`;

async function engine(dir, tag, rest) {
  const option = (name, fallback) => {const i = rest.indexOf(name); return i < 0 ? fallback : rest[i + 1];};
  const python = option('--python', 'python'), threaded = option('--threads', 'one') === 'default';
  const only = option('--only', null)?.split(',') ?? Object.keys(CASES);
  const O = await page('workspace-optical.mjs');
  await mkdir(dir, {recursive: true});
  const env = threaded ? {...process.env} : {...process.env, OPENBLAS_NUM_THREADS: '1', OMP_NUM_THREADS: '1', MKL_NUM_THREADS: '1'};
  for (const name of only) {
    const doc = JSON.stringify(O.opticalDocument(caseState(CASES[name]), SETUP));
    await writeFile(join(dir, name + '.document.json'), doc);
    const started = Date.now();
    const done = spawnSync(python, ['-I', '-c', ENGINE], {input: doc, maxBuffer: 1 << 30, cwd: ROOT, env});
    if (done.status !== 0) throw new Error(name + ': ' + done.stderr.toString());
    await writeFile(join(dir, `${name}.${tag}.result.json`), done.stdout);
    const line = {case: name, tag, threads: threaded ? 'default' : 1, bytes: done.stdout.length, seconds: +((Date.now() - started) / 1000).toFixed(1)};
    await appendFile(join(dir, tag + '.times.json'), JSON.stringify(line) + '\n');
    console.log(JSON.stringify(line));
  }
}

// ---- the runs the page keeps of these results ------------------------------------------------
const UNITS = {height: 'nm', width: 'nm', wavelength: 'nm', core_mesh: 'nm', shapes: 'nm', thermal_length: 'mm', joule_length: 'mm', voltage: 'V', temperature: 'K'};
let TEMPLATE = null;
async function template() {
  // the other inputs of a run (thermal and Joule panels): those of the committed version 10 fixture
  if (!TEMPLATE) TEMPLATE = JSON.parse(await readFile(join(ROOT, 'tests/simcase/studio_session_fixtures/optical-v10-open-f8ece10.json'), 'utf8')).runs[0].input;
  return TEMPLATE;
}
/** The job record of a case as the page writes it before the run (workspace-app.mjs, runOptical):
 * the captured inputs (version 7), the mode count, the open boundary and the closed-window target. */
export async function pendingOf(name, job, serverVersion = '0.0.2') {
  const P = await page('workspace-project.mjs'), R = await page('workspace-open-run.mjs'), c = CASES[name], t = await template();
  const input = P.validateProject({format: 'openphysics-studio-workspace', version: 7, units: UNITS, model: {...t.model, coreMesh: c.coreMesh, shapes: c.shapes}, setup: t.setup});
  const ob = c.open ? R.builderBoundary({edges: c.open}, c.shapes) : null;
  return {job, input, modeCount: c.modeCount, serverVersion, ...(ob ? {openBoundary: {edges: ob.edges, target: ob.target}} : {}), ...(c.searchTarget != null ? {searchTarget: c.searchTarget} : {})};
}
/** The inputs file of the tab with a case's study settings (Modes to find, group index, boundary). */
export async function inputsOf(name, run) {
  const P = await page('workspace-project.mjs'), c = CASES[name];
  return P.withStudy(run.input, {modeCount: c.modeCount, groupIndex: !!c.groupIndex, openBoundary: c.open ? {edges: c.open} : null});
}
const bytesOf = text => Buffer.byteLength(text, 'utf8');

// K1 (blind bounds, measured counts): 20 results of the T18 mix, cycling closed 2 modes, closed 4
// modes, closed near 2.46 (4 modes) and open + n_g, Run 2 pinned, each new result selected and
// compared with the one before, as the page does (applyFieldBudget at each result).
async function k1(dir, out) {
  const N = await page('workspace-notebook.mjs'), X = await page('workspace-retention.mjs'), W = await page('workspace-workflow.mjs'), RR = await page('workspace-result-run.mjs');
  const cycle = ['t18closed2', 't18closed4', 't18near', 't18open'], view = {mode: 0, component: 'magnitude', window: 'Core region'};
  const results = {};
  for (const name of cycle) results[name] = JSON.parse(await readFile(join(dir, `${name}.one-a.result.json`), 'utf8'));
  let runs = [], used = 0, comparison = [null, null];
  const steps = [], failures = [];
  for (let n = 1; n <= 20; n++) {
    const name = cycle[(n - 1) % cycle.length], job = (0xb0000000 + n).toString(16);
    const run = RR.runOfResult(results[name], await pendingOf(name, job), {completedAt: new Date(Date.UTC(2026, 10, 25, 0, n)).toISOString()});
    used = W.numberRuns([run], used); if (n === 2) run.pinned = true;
    runs = N.appendRun(runs, run, N.RUN_LIMIT);
    comparison = [comparison[1] ?? job, job];
    const input = await inputsOf(name, run), selected = job;
    // the reference (independent of the cached sums): the same order, each field tried with the
    // session text written in full
    const order = X.fieldOrder(runs, selected), keep = new Set(), expected = [];
    const full = bytesOf(N.sessionText(input, runs, selected, comparison, view));
    if (full > X.FIELD_BUDGET_BYTES) {
      order.forEach((r, i) => {const trial = new Set([...keep, r.job]); const b = bytesOf(N.sessionText(input, runs, selected, comparison, view, {keep: trial}));
        if (b <= X.FIELD_BUDGET_BYTES || (i === 0 && r.job === selected)) {keep.add(r.job); expected.push(r.number);}});
    } else for (const r of order) expected.push(r.number);
    const chosen = X.chooseFields(input, runs, selected, comparison, view);
    for (const r of chosen.letGo) X.letGoField(r);
    const text = N.sessionText(input, runs, selected, comparison, view), bytes = bytesOf(text);
    const kept = runs.filter(r => r.field).map(r => r.number).sort((a, b) => a - b), want = [...expected].sort((a, b) => a - b);
    const withoutFields = N.sessionBytesWithoutFields(input, runs, selected, comparison, view) - N.sessionBytesWithoutFields(input, [], null, [null, null], view);
    const step = {result: n, case: name, bytes, version: JSON.parse(text).version, kept, letGo: chosen.letGo.map(r => r.number), cachedSum: chosen.fits ? null : chosen.total, recordsWithoutFields: withoutFields};
    if (bytes > N.MAX_SESSION_BYTES) failures.push(`result ${n}: ${bytes} bytes > 16,777,216`);
    if (JSON.stringify(kept) !== JSON.stringify(want)) failures.push(`result ${n}: kept ${kept}, the order picks ${want}`);
    if (!chosen.fits && chosen.total !== bytes) failures.push(`result ${n}: cached sum ${chosen.total} != written ${bytes}`);
    steps.push(step); console.log(JSON.stringify(step));
  }
  const last = steps.at(-1);
  if (last.recordsWithoutFields > 500000) failures.push(`the 20 records without fields are ${last.recordsWithoutFields} bytes > 0.5 MB`);
  const report = {check: 'K1', budget: X.FIELD_BUDGET_BYTES, limit: N.MAX_SESSION_BYTES, steps, fieldsKeptAt20: last.kept.length, prediction: 4, failures};
  await mkdir(out, {recursive: true}); await writeFile(join(out, 'k1.json'), JSON.stringify(report, null, 1) + '\n');
  console.log(JSON.stringify({fieldsKeptAt20: report.fieldsKeptAt20, maxBytes: Math.max(...steps.map(s => s.bytes)), recordsWithoutFields: last.recordsWithoutFields, failures}));
  if (failures.length) process.exitCode = 1;
}

// K5 (blind): a recomputed field equals the original. Each case's run is the page's run of the first
// single-threaded solve (one-a), named, pinned and numbered; the document Recompute Run N's fields
// builds from its stored inputs must be the case's document byte for byte; its field is let go; the
// second solve of that document (one-b, a separate process) is the recomputed result: every stored
// value within 1e-12 relative (1e-15 absolute below 1e-3), node_coordinates and triangles identical,
// the field samples' max |Δ| / max |E| recorded, the run's job, number, name, pin and completedAt
// unchanged. With --threads the same comparison of one-a against the default-thread solve is
// recorded as measured only.
async function k5(dir, out, against = 'one-b', base = 'one-a', only = null) {
  const N = await page('workspace-notebook.mjs'), X = await page('workspace-retention.mjs'), RR = await page('workspace-result-run.mjs');
  const report = {check: 'K5', base, against, cases: {}, failures: []};
  for (const name of only ?? ['t18closed2', 't18closed4', 't18near', 't16', 't18open']) {
    const first = JSON.parse(await readFile(join(dir, `${name}.${base}.result.json`), 'utf8'));
    const second = JSON.parse(await readFile(join(dir, `${name}.${against}.result.json`), 'utf8'));
    const pending = await pendingOf(name, 'a0000004');
    const run = RR.runOfResult(first, pending, {completedAt: '2026-11-25T04:00:00.000Z'});
    Object.assign(run, {label: 'Design ' + name, pinned: true}); run.number = 4;
    const original = run.field, identity = JSON.stringify([run.job, run.number, run.label, run.pinned, run.completedAt, run.origin]);
    const document = JSON.stringify(X.recomputeDocument(run)), expected = await readFile(join(dir, `${name}.document.json`), 'utf8');
    X.letGoField(run);
    const fresh = RR.runOfResult(second, {...pending, job: run.job}, {completedAt: run.completedAt});
    const mismatch = X.recomputeMismatch(run, fresh);
    // the largest relative difference of the stored values (measured)
    let worst = 0;
    const values = r => [...r.effective_index, ...(r.effective_index_im ?? []), ...(r.te_polarization_fraction ?? []), ...(r.effective_area ?? []), ...(r.group_index ?? []), ...(r.group_index_im ?? []),
      ...(r.open_boundary?.candidates ?? []).flatMap(c => [c.effective_index.re, c.effective_index.im])];
    const a = values(run), b = values(fresh);
    a.forEach((v, i) => { if (v !== null && b[i] !== null) worst = Math.max(worst, Math.abs(b[i] - v) / Math.max(Math.abs(v), 1e-300)); });
    const sameMesh = JSON.stringify(original.node_coordinates) === JSON.stringify(fresh.field.node_coordinates) && JSON.stringify(original.triangles) === JSON.stringify(fresh.field.triangles);
    let maxE = 0, maxD = 0;
    for (const part of ['real', 'imag']) original[part].forEach((mode, m) => mode.forEach((t, i) => t.forEach((v, c) => { maxE = Math.max(maxE, Math.abs(v)); maxD = Math.max(maxD, Math.abs(v - fresh.field[part][m][i][c])); })));
    if (!mismatch) X.attachField(run, fresh.field);
    const after = JSON.stringify([run.job, run.number, run.label, run.pinned, run.completedAt, run.origin]);
    const entry = {documentEqual: document === expected, match: mismatch === null, mismatch, worstRelative: worst, sameMesh, fieldMaxDeltaOverMaxE: maxD / maxE, identityKept: after === identity, attached: run.field === fresh.field,
      modes: run.effective_index.length, values: a.length};
    report.cases[name] = entry; console.log(name, JSON.stringify(entry));
    if (against === 'one-b' && base === 'one-a') {
      if (!entry.documentEqual) report.failures.push(name + ': the recompute document differs from the run\'s');
      if (!entry.match) report.failures.push(name + ': ' + JSON.stringify(mismatch));
      if (!entry.sameMesh) report.failures.push(name + ': node_coordinates or triangles differ');
      if (!entry.identityKept || !entry.attached) report.failures.push(name + ': the run changed identity or the field was not attached');
    }
  }
  await mkdir(out, {recursive: true}); await writeFile(join(out, `k5-${base}-${against}.json`), JSON.stringify(report, null, 1) + '\n');
  console.log(JSON.stringify({base, against, failures: report.failures}));
  if (report.failures.length) process.exitCode = 1;
}

const [command, ...rest] = process.argv.slice(2);
if (command === 'engine') await engine(resolve(rest[0]), rest[1], rest.slice(2));
else if (command === 'k1') await k1(resolve(rest[0]), resolve(rest[1]));
else if (command === 'k5') await k5(resolve(rest[0]), resolve(rest[1]), rest[2] ?? 'one-b', rest[3] ?? 'one-a', rest[4] ? rest[4].split(',') : null);
else if (command !== undefined) throw new Error('usage: node tools/studio_run_retention.mjs engine <dir> <tag> [options] | k1 <dir> <out> | k5 <dir> <out> [one-b|threads]');
