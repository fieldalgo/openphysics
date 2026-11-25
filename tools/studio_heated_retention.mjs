// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
//
// Engine results for the heated model's run-retention checks (design "Keeping more runs", section 7,
// slice H1): HK1 (sizes at 20 runs). Each case is a
// multiphysics document solved by the Studio server's own job (simcase.studio.multiphysics_api.Jobs),
// whose reply body is what /api/multiphysics/jobs/<id>/result sends.
//
//   node tools/studio_heated_retention.mjs engine <dir> <tag> [--python python] [--only a,b]
//   node tools/studio_heated_retention.mjs hk1 <dir> <out>
//
// writes <dir>/<case>.document.json ({document, events}) and <dir>/<case>.<tag>.result.json, and
// appends one line per case to <dir>/<tag>.times.json. The solve is single threaded (OMP, OpenBLAS
// and MKL threads 1, as the agent rounds run). The HK1 and HK5 tests read <dir> from
// STUDIO_HEATED_RETENTION_RESULTS (tests/simcase/studio_heated_retention_engine.cjs).
//
// The cases: the Studio template (Library › Heated silicon waveguide) with heater powers 1e14 to
// 9e14 W/m^3 and Modes to find 2 (tpl-p1 … tpl-p9) or 4 (tpl4-p1 … tpl4-p9); the template at a
// 0.12 µm and a 0.08 µm mesh (core near 0.015 µm); and examples/simcase/multiphysics_heated_slab.json.
import {spawnSync} from 'node:child_process';
import {appendFile, mkdir, readFile, writeFile} from 'node:fs/promises';
import {join, resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const ROOT = resolve(new URL('..', import.meta.url).pathname);
const STATIC = join(ROOT, 'packages/simcase/src/simcase/studio/static');
const page = name => import(pathToFileURL(join(STATIC, name)).href);
const POWERS = [1, 2, 3, 4, 5, 6, 7, 8, 9];
export const CASE_NAMES = Object.freeze([...POWERS.map(p => 'tpl-p' + p), ...POWERS.map(p => 'tpl4-p' + p), 'v012', 'v008', 'slab']);

/** The document of a case. */
export async function caseDocument(name) {
  const template = JSON.parse(await readFile(join(STATIC, 'multiphysics-template.json'), 'utf8'));
  if (name === 'slab') return JSON.parse(await readFile(join(ROOT, 'examples/simcase/multiphysics_heated_slab.json'), 'utf8'));
  const d = structuredClone(template);
  if (name === 'v012' || name === 'v008') {
    const size = name === 'v012' ? '0.12 um' : '0.08 um';
    d.mesh.element_size = size; for (const c of d.mesh.controls) { c.near = '0.015 um'; c.far = size; }
    return d;
  }
  const m = /^tpl(4?)-p(\d)$/.exec(name); if (!m) throw new Error('unknown case ' + name);
  d.physics.heat1.heat_source_density.heater = `${m[2]}e14 W/m^3`;
  if (m[1]) d.physics.modes1.mode_count = 4;
  return d;
}

const ENGINE = String.raw`
import json, sys
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from simcase import Document
from simcase.studio import multiphysics_api as mp
cases = json.loads(sys.stdin.read())
for name, tree in cases.items():
    jobs = mp.Jobs()
    jobs.jobs["j"] = {"status": "running", "events": [], "solving": None, "stop": False, "error": None, "result": None}
    jobs.work("j", Document.from_dict(tree))
    job = jobs.jobs["j"]
    if job["status"] != "done":
        sys.exit(name + ": " + str(job["error"]))
    sys.stdout.write(json.dumps({"case": name, "events": job["events"], "body": JSONResponse(jsonable_encoder(job["result"])).body.decode()}) + "\n")
    sys.stdout.flush()
`;

async function engine(dir, tag, rest) {
  const option = (name, fallback) => {const i = rest.indexOf(name); return i < 0 ? fallback : rest[i + 1];};
  const python = option('--python', 'python'), only = option('--only', null)?.split(',') ?? CASE_NAMES;
  await mkdir(dir, {recursive: true});
  const env = {...process.env, OPENBLAS_NUM_THREADS: '1', OMP_NUM_THREADS: '1', MKL_NUM_THREADS: '1'};
  for (const name of only) {
    const doc = await caseDocument(name), started = Date.now();
    const done = spawnSync(python, ['-I', '-c', ENGINE], {input: JSON.stringify({[name]: doc}), maxBuffer: 1 << 30, cwd: ROOT, env});
    if (done.status !== 0) throw new Error(name + ': ' + done.stderr.toString());
    const line = JSON.parse(done.stdout.toString());
    await writeFile(join(dir, name + '.document.json'), JSON.stringify({document: doc, events: line.events}));
    await writeFile(join(dir, `${name}.${tag}.result.json`), line.body);
    const times = {case: name, tag, threads: 1, bytes: Buffer.byteLength(line.body), seconds: +((Date.now() - started) / 1000).toFixed(1)};
    await appendFile(join(dir, tag + '.times.json'), JSON.stringify(times) + '\n');
    console.log(JSON.stringify(times));
  }
}

/** A case's run as the page keeps it after the result (workspace-multiphysics-view.mjs, finish). */
export async function runOf(dir, name, {tag = 'one-a', number, job, completedAt, pinned = false, label = ''}) {
  const {document, events} = JSON.parse(await readFile(join(dir, name + '.document.json'), 'utf8'));
  const result = JSON.parse(await readFile(join(dir, `${name}.${tag}.result.json`), 'utf8'));
  return {job, number, label, pinned, completedAt, serverVersion: '0.0.2', doc: document, events, order: result.solve_order, result, maps: 'kept', origin: 'local'};
}
const bytesOf = text => Buffer.byteLength(text, 'utf8');
const view = {page: 'Results', selection: 'results:modes1', index_map: 'change', baseline_option: false};

// HK1 (measured): 20 results of each kind and of the template mix, through the tab's arrival rule
// (keepMapsAtArrival); the session text after every result within the budget, the maps kept those of
// the selected run and the newest that fit (the reference tries each run in the order with the
// session text written in full), the cached sum equal to the written length.
export async function hk1(dir, out = null) {
  const M = await page('workspace-multiphysics-session.mjs'), B = await page('workspace-budget.mjs');
  const report = {check: 'HK1', budget: B.FIELD_BUDGET_BYTES, sequences: {}, failures: []};
  const sequences = {template: () => 'tpl-p2', template4: () => 'tpl4-p2', v012: () => 'v012', slab: () => 'slab', v008: () => 'v008',
    mix: n => (n % 2 ? 'tpl-p' : 'tpl4-p') + (1 + (n - 1) % 9)};
  const prediction = {template: 20, template4: 20, v012: 10, slab: 6, v008: 5, mix: null};
  for (const [kind, pick] of Object.entries(sequences)) {
    let runs = [];
    const steps = [];
    for (let n = 1; n <= 20; n++) {
      const run = await runOf(dir, pick(n), {number: n, job: 'mp-' + (0xa00000000000 + n).toString(16), completedAt: new Date(Date.UTC(2026, 10, 25, 1, n)).toISOString(), pinned: kind === 'mix' && n === 2});
      runs = M.appendMultiphysicsRun(runs, run);
      const state = {document: run.doc, runs, baselines: {}, selected: run.job, view};
      // the reference: the order of 3.2, each map tried with the file written in full
      const order = B.budgetOrder(runs.filter(r => r.maps !== 'not kept'), {selected: run.job}), keep = new Set();
      const fullBytes = M.writeMultiphysicsSession(state, {limit: Infinity}).bytes;
      if (fullBytes > B.FIELD_BUDGET_BYTES) order.forEach((r, i) => {const trial = new Set([...keep, r.job]);
        const b = bytesOf(M.sessionText(state, trial)); if (b <= B.FIELD_BUDGET_BYTES || (i === 0 && r.job === run.job)) keep.add(r.job);});
      else for (const r of order) keep.add(r.job);
      const chosen = M.keepMapsAtArrival(state);
      const text = M.writeMultiphysicsSession(state).text, bytes = bytesOf(text);
      const kept = runs.filter(r => r.maps !== 'not kept').map(r => r.number).sort((a, b) => a - b), want = runs.filter(r => keep.has(r.job)).map(r => r.number).sort((a, b) => a - b);
      const step = {result: n, case: pick(n), bytes, version: JSON.parse(text).version, kept: kept.length, keptRuns: kept, letGo: chosen.letGo.map(r => r.number), cachedSum: chosen.total};
      if (bytes > B.FIELD_BUDGET_BYTES) report.failures.push(`${kind} ${n}: ${bytes} bytes > budget`);
      if (runs.length !== n) report.failures.push(`${kind} ${n}: ${runs.length} runs`);
      if (JSON.stringify(kept) !== JSON.stringify(want)) report.failures.push(`${kind} ${n}: kept ${kept}, the order picks ${want}`);
      if (chosen.total !== null && chosen.total !== bytes) report.failures.push(`${kind} ${n}: cached sum ${chosen.total} != written ${bytes}`);
      steps.push(step);
    }
    const valuesOnly = runs.reduce((t, r) => t + bytesOf(M.sessionJson(M.sessionRun(r, false))), 0);
    const last = steps.at(-1);
    report.sequences[kind] = {mapsKeptAt20: last.kept, prediction: prediction[kind], maxBytes: Math.max(...steps.map(s => s.bytes)), valuesOnlyRecords20: valuesOnly, steps};
    console.log(kind, JSON.stringify({mapsKeptAt20: last.kept, prediction: prediction[kind], maxBytes: report.sequences[kind].maxBytes, valuesOnlyRecords20: valuesOnly}));
  }
  if (out) {await mkdir(out, {recursive: true}); await writeFile(join(out, 'hk1.json'), JSON.stringify(report, null, 1) + '\n');}
  console.log(JSON.stringify({failures: report.failures}));
  return report;
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [command, dir, arg, ...rest] = process.argv.slice(2);
  if (command === 'engine') await engine(resolve(dir), arg, rest);
  else if (command === 'hk1') {if ((await hk1(resolve(dir), resolve(arg))).failures.length) process.exitCode = 1;}
  else throw new Error('usage: engine <dir> <tag> | hk1 <dir> <out>');
}
