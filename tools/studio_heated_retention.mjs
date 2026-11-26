// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
//
// Engine results for the heated model's run-retention checks (design "Keeping more runs", section 7,
// slice H1): HK1 (sizes at 20 runs) and HK5 (recomputed maps equal the original). Each case is a
// multiphysics document solved by the Studio server's own job (simcase.studio.multiphysics_api.Jobs),
// whose reply body is what /api/multiphysics/jobs/<id>/result sends.
//
//   node tools/studio_heated_retention.mjs engine <dir> <tag> [--python python] [--only a,b]
//   node tools/studio_heated_retention.mjs hk1 <dir> <out>
//   node tools/studio_heated_retention.mjs hk5 <dir> <out>          (one-b against one-a)
//   node tools/studio_heated_retention.mjs hq <dir> <out>           (HQ1 to HQ4: compact maps, session version 17)
//   node tools/studio_heated_retention.mjs hq5 <dir> <out>          (HQ5: the Results page with compact maps)
//   node tools/studio_heated_retention.mjs hq6 <dir> <out>          (HQ6: maps kept at 20 results with compact maps)
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

// HK5 (measured): a recompute equals the original. Each case's run of the first solve (one-a) has its
// maps let go; the second solve of the same document (one-b, a separate process) is the recomputed
// result: every checked value within 1e-12 relative (1e-15 absolute below 1e-3), counts exact, the
// mesh identical, each map's max |Δ| / max |x| recorded.
export async function hk5(dir, out = null) {
  const M = await page('workspace-multiphysics-session.mjs');
  const report = {check: 'HK5', cases: {}, failures: []};
  for (const name of ['tpl-p2', 'tpl4-p2', 'v012', 'slab']) {
    const run = await runOf(dir, name, {number: 4, job: 'mp-00000000a004', completedAt: '2026-11-25T04:00:00.000Z', pinned: true, label: 'Design ' + name});
    const original = structuredClone(run.result), fresh = JSON.parse(await readFile(join(dir, `${name}.one-b.result.json`), 'utf8'));
    M.letGoMaps(run);
    const before = M.sessionJson(M.sessionRun(run)), mismatch = M.recomputeMapsMismatch(run, fresh);
    const sameMesh = ['node_coordinates', 'triangles', 'regions'].every(k => JSON.stringify(original.mesh[k]) === JSON.stringify(fresh.mesh[k]));
    const maps = {};
    for (const [label, get] of [['heat temperature', r => r.physics.heat1.temperature.values], ['coupled temperature', r => r.physics.modes1.coupled.temperature.values],
      ['n', r => r.physics.modes1.coupled.refractive_index.n], ['index_change', r => r.physics.modes1.coupled.index_change]]) {
      const a = get(original), b = get(fresh); if (!a || !b) {maps[label] = null; continue;}
      let max = 0, d = 0; a.forEach((v, i) => {max = Math.max(max, Math.abs(v)); d = Math.max(d, Math.abs(v - b[i]));}); maps[label] = d / max;
    }
    const attached = mismatch === null && M.attachMaps(run, fresh);
    const entry = {match: mismatch === null, mismatch, sameMesh, maps, attached, identity: [run.job, run.number, run.label, run.pinned, run.completedAt].join(' '),
      recordUnchangedOnRefusal: mismatch === null ? null : before === M.sessionJson(M.sessionRun(run))};
    report.cases[name] = entry; console.log(name, JSON.stringify(entry));
    if (!entry.match) report.failures.push(name + ': ' + JSON.stringify(mismatch));
    if (!entry.sameMesh) report.failures.push(name + ': node_coordinates, triangles or regions differ');
    if (entry.match && !attached) report.failures.push(name + ': the maps were not attached');
  }
  if (out) {await mkdir(out, {recursive: true}); await writeFile(join(out, 'hk5.json'), JSON.stringify(report, null, 1) + '\n');}
  console.log(JSON.stringify({failures: report.failures}));
  return report;
}

// HQ1 to HQ4 (design "Session versions 16 and 17", section 3.4, pre-registered limits): each case's
// maps made compact (workspace-map-encoding.mjs) and read back from a version 17 file. HQ1: every
// decoded sample is bitwise base + fround(x − base), the coordinates, triangles and regions bitwise
// equal; HQ2: |ΔT| of each node ≤ 2^-24·(range.max − range.min) + 2^-52·|T|; HQ3: the coupled
// (triangle) temperature against the server's within the same bound; HQ4: |Δ| of n, k and
// index_change ≤ 2^-24·max over the region |x − base| + 2^-52·|x|. The worst of each is recorded.
export async function hqAccuracy(dir, out = null, cases = ['tpl-p2', 'tpl4-p2', 'v012', 'v008', 'slab']) {
  const M = await page('workspace-multiphysics-session.mjs'), N = await page('workspace-notebook.mjs'), E = await page('workspace-map-encoding.mjs');
  const report = {check: 'HQ1-HQ4', cases: {}, failures: []};
  for (const name of cases) {
    const run = await runOf(dir, name, {number: 1, job: 'mp-00000000b001', completedAt: '2026-11-26T01:00:00.000Z'});
    const server = structuredClone(run.result);
    if (!M.compactRunMaps(run)) {report.failures.push(name + ': maps not compact'); continue;}
    const text = M.writeMultiphysicsSession({document: run.doc, runs: [run], baselines: {}, selected: run.job, view}).text;
    const read = N.parseSession(text).runs[0].result, fail = what => report.failures.push(`${name}: ${what}`);
    if (JSON.parse(text).version !== 17) fail('not version 17');
    const m = server.mesh, d = read.mesh;
    if (JSON.stringify(m.node_coordinates) !== JSON.stringify(d.node_coordinates) || !m.node_coordinates.flat().every((x, i) => Object.is(x, d.node_coordinates.flat()[i]))) fail('HQ1 node coordinates differ');
    if (JSON.stringify(m.triangles) !== JSON.stringify(d.triangles) || JSON.stringify(m.regions) !== JSON.stringify(d.regions)) fail('HQ1 triangles or regions differ');
    const entry = {nodes: m.node_coordinates.length, triangles: m.triangles.length};
    const R = m.regions, names = m.region_names.length;
    for (const [pname, p] of Object.entries(server.physics)) {
      if (p.type === 'thermal.steady2d') {
        const T = p.temperature.values, D = read.physics[pname].temperature.values, base = p.range.min, span = p.range.max - p.range.min;
        let worst = 0, ratio = 0;
        T.forEach((x, i) => {
          if (!Object.is(D[i], base + Math.fround(x - base))) fail(`HQ1 ${pname} node ${i} is not base + fround(x − base)`);
          const e = Math.abs(D[i] - x), bound = 2 ** -24 * span + 2 ** -52 * Math.abs(x); worst = Math.max(worst, e); ratio = Math.max(ratio, e / bound);
          if (e > bound) fail(`HQ2 ${pname} node ${i}: |ΔT| ${e} > ${bound}`);
        });
        entry[pname] = {span, nodeT_abs: worst, nodeT_bound_ratio: ratio, rangeMinExact: Math.min(...D) === base, rangeMaxRule: Math.max(...D) === base + Math.fround(span)};
      } else if (p.coupled) {
        const c = p.coupled, k = read.physics[pname].coupled, src = server.physics.heat1 ?? Object.values(server.physics).find(q => q.type === 'thermal.steady2d');
        const span = src.range.max - src.range.min;
        let worst = 0;
        c.temperature.values.forEach((x, i) => {const e = Math.abs(k.temperature.values[i] - x), bound = 2 ** -24 * span + 2 ** -52 * Math.abs(x); worst = Math.max(worst, e); if (e > bound) fail(`HQ3 ${pname} triangle ${i}: |ΔT| ${e} > ${bound}`);});
        entry[pname] = {coupledT_abs: worst};
        for (const [label, a, b] of [['n', c.refractive_index.n, k.refractive_index.n], ['k', c.refractive_index.k, k.refractive_index.k], ['index_change', c.index_change, k.index_change]]) {
          if (a == null) {if (b != null) fail(`${label} appeared`); continue;}
          const base = E.regionBases(a, R, names), spread = new Array(names).fill(0);
          a.forEach((x, i) => {spread[R[i]] = Math.max(spread[R[i]], Math.abs(x - base[R[i]]));});
          let w = 0;
          a.forEach((x, i) => {
            if (!Object.is(b[i], base[R[i]] + Math.fround(x - base[R[i]]))) fail(`HQ1 ${label} triangle ${i} is not base + fround(x − base)`);
            const e = Math.abs(b[i] - x), bound = 2 ** -24 * spread[R[i]] + 2 ** -52 * Math.abs(x); w = Math.max(w, e); if (e > bound) fail(`HQ4 ${label} triangle ${i}: ${e} > ${bound}`);
          });
          entry[pname][label + '_abs'] = w;
        }
      }
    }
    report.cases[name] = entry; console.log(name, JSON.stringify(entry));
  }
  if (out) {await mkdir(out, {recursive: true}); await writeFile(join(out, 'hq-accuracy.json'), JSON.stringify(report, null, 1) + '\n');}
  console.log(JSON.stringify({failures: report.failures}));
  return report;
}

// HQ5 (pre-registered): the Results page of each case with compact maps against the server's maps:
// (a) Minimum T and Maximum T (0.001 K) identical; (b) every map's colour-bar labels and accessible
// name identical; (c) no triangle's colour changes by more than 1 level of 255 per channel; (d) at most
// 0.1 % of triangles change colour on the heat map and the n and Δn maps, at most 5 % on the core T
// map. The maps are the page's (workspace-multiphysics.mjs: mapValues, mapColour, mapLegend).
export async function hq5(dir, out = null, cases = ['tpl-p2', 'v012', 'v008', 'slab']) {
  const M = await page('workspace-multiphysics-session.mjs'), N = await page('workspace-notebook.mjs'), MP = await page('workspace-multiphysics.mjs');
  const report = {check: 'HQ5', cases: {}, failures: []};
  for (const name of cases) {
    const run = await runOf(dir, name, {number: 1, job: 'mp-00000000b005', completedAt: '2026-11-26T05:00:00.000Z'}), server = structuredClone(run.result);
    if (!M.compactRunMaps(run)) {report.failures.push(name + ': maps not compact'); continue;}
    const read = N.parseSession(M.writeMultiphysicsSession({document: run.doc, runs: [run], baselines: {}, selected: run.job, view}).text).runs[0].result;
    const entry = {}, fail = what => report.failures.push(`${name}: ${what}`);
    const heat = Object.keys(server.physics).find(k => server.physics[k].type === 'thermal.steady2d'), em = Object.keys(server.physics).find(k => server.physics[k].coupled);
    const range = r => [r.physics[heat].range.min.toFixed(3) + ' K', r.physics[heat].range.max.toFixed(3) + ' K'];
    entry.range = range(read); if (JSON.stringify(range(read)) !== JSON.stringify(range(server))) fail('(a) Minimum or Maximum T differs');
    const region = server.mesh.region_names.includes('core') ? 'core' : null;
    const maps = {heat: [r => r.physics[heat].temperature.values, {nodal: true}, 'Temperature in K', 0.001],
      T_core: [r => r.physics[em].coupled.temperature.values, {region}, 'Temperature in K', 0.05],
      n_core: [r => r.physics[em].coupled.refractive_index.n, {region}, 'Refractive index', 0.001],
      dn_core: [r => r.physics[em].coupled.index_change, {region}, 'Index change n − n₀', 0.001]};
    for (const [key, [get, options, label, share]] of Object.entries(maps)) {
      const a = MP.mapValues(server, get(server), options), b = MP.mapValues(read, get(read), options);
      const legend = [MP.mapLegend(a.lo, a.hi), MP.mapLegend(b.lo, b.hi)], aria = [MP.mapAriaLabel(label, a.lo, a.hi), MP.mapAriaLabel(label, b.lo, b.hi)];
      let changed = 0, maxLevel = 0;
      for (const i of a.tris) {
        const x = MP.mapColour(a.hi > a.lo ? (a.tv(i) - a.lo) / (a.hi - a.lo) : .5), y = MP.mapColour(b.hi > b.lo ? (b.tv(i) - b.lo) / (b.hi - b.lo) : .5);
        const d = Math.max(...x.map((v, k) => Math.abs(v - y[k]))); if (d) {changed++; maxLevel = Math.max(maxLevel, d);}
      }
      const e = {triangles: a.tris.length, changed, share: changed / a.tris.length, maxLevel, legend: legend[1], sameLegend: legend[0].join() === legend[1].join(), sameAria: aria[0] === aria[1]};
      entry[key] = e;
      if (!e.sameLegend) fail(`(b) ${key} legend ${legend[0]} → ${legend[1]}`);
      if (!e.sameAria) fail(`(b) ${key} accessible name ${aria[0]} → ${aria[1]}`);
      if (maxLevel > 1) fail(`(c) ${key} a colour changes by ${maxLevel} levels`);
      if (e.share > share) fail(`(d) ${key} ${(100 * e.share).toFixed(2)} % of triangles change colour (limit ${100 * share} %)`);
    }
    report.cases[name] = entry; console.log(name, JSON.stringify(entry));
  }
  if (out) {await mkdir(out, {recursive: true}); await writeFile(join(out, 'hq5.json'), JSON.stringify(report, null, 1) + '\n');}
  console.log(JSON.stringify({failures: report.failures}));
  return report;
}

// HQ6 (pre-registered counts): HK1's sequences of 20 results through the tab's rule with compact maps
// (compactMaps at each arrival, then the order of 3.2): the maps kept at 20 results (template 20, 0.12
// µm 20, 0.08 µm 15, slab 17), each session within the budget, the maps kept those of the reference
// (each tried with the session text written in full, after the conversion), the cached sum the written
// length, and each compact record's strings exactly compactMapChars of its counts.
export async function hq6(dir, out = null) {
  const M = await page('workspace-multiphysics-session.mjs'), B = await page('workspace-budget.mjs'), E = await page('workspace-map-encoding.mjs');
  const report = {check: 'HQ6', budget: B.FIELD_BUDGET_BYTES, sequences: {}, failures: []};
  const sequences = {template: () => 'tpl-p2', v012: () => 'v012', v008: () => 'v008', slab: () => 'slab'};
  const prediction = {template: 20, v012: 20, v008: 15, slab: 17};
  for (const [kind, pick] of Object.entries(sequences)) {
    let runs = [];
    const steps = [];
    for (let n = 1; n <= 20; n++) {
      const run = await runOf(dir, pick(n), {number: n, job: 'mp-' + (0xc00000000000 + n).toString(16), completedAt: new Date(Date.UTC(2026, 10, 26, 1, n)).toISOString()});
      runs = M.appendMultiphysicsRun(runs, run);
      const state = {document: run.doc, runs, baselines: {}, selected: run.job, view};
      const {converted} = M.compactMaps(state);
      const order = B.budgetOrder(runs.filter(r => r.maps !== 'not kept'), {selected: run.job}), keep = new Set();
      if (M.writeMultiphysicsSession(state, {limit: Infinity}).bytes > B.FIELD_BUDGET_BYTES) order.forEach((r, i) => {const trial = new Set([...keep, r.job]);
        const b = bytesOf(M.sessionText(state, trial)); if (b <= B.FIELD_BUDGET_BYTES || (i === 0 && r.job === run.job)) keep.add(r.job);});
      else for (const r of order) keep.add(r.job);
      const chosen = M.keepMapsAtArrival(state), text = M.writeMultiphysicsSession(state).text, bytes = bytesOf(text);
      const kept = runs.filter(r => r.maps !== 'not kept').map(r => r.number).sort((a, b) => a - b), want = runs.filter(r => keep.has(r.job)).map(r => r.number).sort((a, b) => a - b);
      if (bytes > B.FIELD_BUDGET_BYTES) report.failures.push(`${kind} ${n}: ${bytes} bytes > budget`);
      if (JSON.stringify(kept) !== JSON.stringify(want)) report.failures.push(`${kind} ${n}: kept ${kept}, the order picks ${want}`);
      if (chosen.total !== null && chosen.total !== bytes) report.failures.push(`${kind} ${n}: cached sum ${chosen.total} != written ${bytes}`);
      for (const r of runs.filter(x => x.maps === 'compact')) {
        const rec = E.compactMapsRecord(r.result), c = rec.mesh.counts, k = Object.values(rec.physics).find(p => p.coupled)?.coupled;
        const maps = k ? 1 + (k.refractive_index.k !== null) + (k.index_change !== null) : 0, heat = Object.values(rec.physics).filter(p => p.type === 'thermal.steady2d').length;
        if (E.recordMapChars(rec) !== E.compactMapChars(c, {heat, triangleMaps: maps})) report.failures.push(`${kind} ${n}: Run ${r.number}'s strings are not compactMapChars of its counts`);
      }
      steps.push({result: n, bytes, version: JSON.parse(text).version, converted: converted.map(r => r.number), kept: kept.length, keptRuns: kept, letGo: chosen.letGo.map(r => r.number), cachedSum: chosen.total,
        mapBytes: M.mapBytes(run)});
    }
    const last = steps.at(-1);
    report.sequences[kind] = {mapsKeptAt20: last.kept, prediction: prediction[kind], firstConversion: steps.find(s => s.converted.length)?.result ?? null, compactMapBytes: last.mapBytes, maxBytes: Math.max(...steps.map(s => s.bytes)), steps};
    if (last.kept !== prediction[kind]) report.failures.push(`${kind}: ${last.kept} maps kept at 20, pre-registered ${prediction[kind]}`);
    console.log(kind, JSON.stringify({mapsKeptAt20: last.kept, prediction: prediction[kind], firstConversion: report.sequences[kind].firstConversion, compactMapBytes: last.mapBytes, maxBytes: report.sequences[kind].maxBytes}));
  }
  if (out) {await mkdir(out, {recursive: true}); await writeFile(join(out, 'hq6.json'), JSON.stringify(report, null, 1) + '\n');}
  console.log(JSON.stringify({failures: report.failures}));
  return report;
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [command, dir, arg, ...rest] = process.argv.slice(2);
  if (command === 'engine') await engine(resolve(dir), arg, rest);
  else if (command === 'hk1') {if ((await hk1(resolve(dir), resolve(arg))).failures.length) process.exitCode = 1;}
  else if (command === 'hk5') {if ((await hk5(resolve(dir), resolve(arg))).failures.length) process.exitCode = 1;}
  else if (command === 'hq') {if ((await hqAccuracy(resolve(dir), resolve(arg))).failures.length) process.exitCode = 1;}
  else if (command === 'hq5') {if ((await hq5(resolve(dir), resolve(arg))).failures.length) process.exitCode = 1;}
  else if (command === 'hq6') {if ((await hq6(resolve(dir), resolve(arg))).failures.length) process.exitCode = 1;}
  else throw new Error('usage: engine <dir> <tag> | hk1 <dir> <out> | hk5 <dir> <out> | hq <dir> <out> | hq5 <dir> <out> | hq6 <dir> <out>');
}
