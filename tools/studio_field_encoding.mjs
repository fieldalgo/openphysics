// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
//
// Measurements of design "Compact field encoding" on the engine results of
// tools/studio_run_retention.mjs engine (the T18 cases, one thread):
//
//   node tools/studio_field_encoding.mjs f9 <dir> <out>     fields kept at 20 runs (F9)
//   node tools/studio_field_encoding.mjs f16 <dir> <out>    deflate of each compact part (F16)
//   node tools/studio_field_encoding.mjs sizes <dir> <out>  each case's field as text and compact
//   node tools/studio_field_encoding.mjs f14 <dir> <out>    Recompute Run N's fields in a compact tab (F14)
//
// F9 (blind bounds, measured count): run retention's K1 sequence (20 results cycling closed 2 modes,
// closed 4 modes, closed near 2.46 with 4 modes and open + n_g; Run 2 pinned; each new result
// selected and compared with the one before) with the conversion of the tab at the first arrival
// that does not fit as text (workspace-retention.mjs chooseFieldsAtArrival, as applyFieldBudget
// calls it). After every result: the session at most 16,777,216 bytes, the fields kept exactly the
// order's choice (each field tried with the session text written in full), and the cached sum equal
// to the written length. The count kept at 20 runs is recorded (prediction 11: Runs 2 and 11–20).
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {join, resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {deflateSync} from 'node:zlib';
import {pendingOf, inputsOf, CASES} from './studio_run_retention.mjs';

const ROOT = resolve(new URL('..', import.meta.url).pathname);
const STATIC = join(ROOT, 'packages/simcase/src/simcase/studio/static');
const page = name => import(pathToFileURL(join(STATIC, name)).href);
const bytesOf = text => Buffer.byteLength(text, 'utf8');
const VIEW = {mode: 0, component: 'magnitude', window: 'Core region'};

async function resultOf(dir, name) {
  return JSON.parse(await readFile(join(dir, `${name}.one-a.result.json`), 'utf8'));
}
// the page's run of a case's result (workspace-result-run.mjs, as runOptical makes it)
async function runOf(dir, name, job, minute) {
  const RR = await page('workspace-result-run.mjs');
  return RR.runOfResult(await resultOf(dir, name), await pendingOf(name, job), {completedAt: new Date(Date.UTC(2026, 10, 25, 0, minute)).toISOString()});
}

async function f9(dir, out) {
  const N = await page('workspace-notebook.mjs'), X = await page('workspace-retention.mjs'), W = await page('workspace-workflow.mjs'), E = await page('workspace-field-encoding.mjs');
  const cycle = ['t18closed2', 't18closed4', 't18near', 't18open'];
  let runs = [], used = 0, comparison = [null, null], conversions = 0;
  const steps = [], failures = [];
  for (let n = 1; n <= 20; n++) {
    const name = cycle[(n - 1) % cycle.length], job = (0xb0000000 + n).toString(16);
    const run = await runOf(dir, name, job, n);
    used = W.numberRuns([run], used); if (n === 2) run.pinned = true;
    runs = N.appendRun(runs, run, N.RUN_LIMIT);
    comparison = [comparison[1] ?? job, job];
    const input = await inputsOf(name, run), selected = job;
    // the text sizes are computed (and cached) first, so the time is the conversion's alone
    X.chooseFields(input, runs, selected, comparison, VIEW);
    const started = performance.now();
    const {converted, started: first} = X.compactFields(input, runs, selected, comparison, VIEW);
    const convertMs = performance.now() - started;
    if (first) conversions++;
    // the reference (independent of the cached sums), after the conversion
    const order = X.fieldOrder(runs, selected), keep = new Set(), expected = [];
    const full = bytesOf(N.sessionText(input, runs, selected, comparison, VIEW));
    if (full > X.FIELD_BUDGET_BYTES) {
      order.forEach((r, i) => {const trial = new Set([...keep, r.job]); const b = bytesOf(N.sessionText(input, runs, selected, comparison, VIEW, {keep: trial}));
        if (b <= X.FIELD_BUDGET_BYTES || (i === 0 && r.job === selected)) {keep.add(r.job); expected.push(r.number);}});
    } else for (const r of order) expected.push(r.number);
    const chosen = X.chooseFields(input, runs, selected, comparison, VIEW);
    for (const r of chosen.letGo) X.letGoField(r);
    const text = N.sessionText(input, runs, selected, comparison, VIEW), bytes = bytesOf(text);
    const kept = runs.filter(r => r.field).map(r => r.number).sort((a, b) => a - b), want = [...expected].sort((a, b) => a - b);
    const step = {result: n, case: name, bytes, version: JSON.parse(text).version, compact: runs.filter(r => E.isCompactField(r.field)).length,
      converted: converted.map(r => r.number), firstConversion: first, convertMs: Math.round(convertMs), kept, letGo: chosen.letGo.map(r => r.number), cachedSum: chosen.fits ? null : chosen.total};
    if (bytes > N.MAX_SESSION_BYTES) failures.push(`result ${n}: ${bytes} bytes > 16,777,216`);
    if (JSON.stringify(kept) !== JSON.stringify(want)) failures.push(`result ${n}: kept ${kept}, the order picks ${want}`);
    if (!chosen.fits && chosen.total !== bytes) failures.push(`result ${n}: cached sum ${chosen.total} != written ${bytes}`);
    if (runs.some(r => r.field && !E.isCompactField(r.field)) && conversions) failures.push(`result ${n}: a text field in a compact tab`);
    steps.push(step); console.log(JSON.stringify(step));
  }
  if (conversions !== 1) failures.push(`${conversions} conversions (expected one)`);
  const last = steps.at(-1);
  const report = {check: 'F9', budget: X.FIELD_BUDGET_BYTES, limit: N.MAX_SESSION_BYTES, steps, fieldsKeptAt20: last.kept.length, keptAt20: last.kept, prediction: 11, stopBelow: 8, failures};
  await mkdir(out, {recursive: true}); await writeFile(join(out, 'f9.json'), JSON.stringify(report, null, 1) + '\n');
  console.log(JSON.stringify({fieldsKeptAt20: report.fieldsKeptAt20, keptAt20: last.kept, maxBytes: Math.max(...steps.map(s => s.bytes)), failures}));
  if (failures.length || report.fieldsKeptAt20 < 8) process.exitCode = 1;
}

// each case's field: its bytes in a session as text and compact (runFieldBytes), and its counts
async function sizes(dir, out) {
  const N = await page('workspace-notebook.mjs'), E = await page('workspace-field-encoding.mjs');
  const rows = [];
  for (const [i, name] of Object.keys(CASES).entries()) {
    const run = await runOf(dir, name, (0xc0000000 + i).toString(16), i);
    const text = N.runFieldBytes(run);
    N.compactRunField(run);
    const counts = E.compactRecord(run.field).counts, compact = N.runFieldBytes(run);
    rows.push({case: name, counts, textBytes: text, compactBytes: compact, ratio: +(text / compact).toFixed(3), formula: E.compactFieldChars(counts)});
  }
  await mkdir(out, {recursive: true}); await writeFile(join(out, 'sizes.json'), JSON.stringify(rows, null, 1) + '\n');
  for (const r of rows) console.log(JSON.stringify(r));
}

// F16 (measured, for Q3): deflate (level 6) of each compact part, with and without a byte shuffle
// (byte k of every sample together), and the share of exact zeros in each field's samples
function shuffle(bytes, size) {
  const n = bytes.length / size, out = new Uint8Array(bytes.length);
  for (let i = 0; i < n; i++) for (let b = 0; b < size; b++) out[b * n + i] = bytes[i * size + b];
  return out;
}
async function f16(dir, out) {
  const N = await page('workspace-notebook.mjs'), E = await page('workspace-field-encoding.mjs');
  const rows = [];
  for (const [i, name] of Object.keys(CASES).entries()) {
    const run = await runOf(dir, name, (0xd0000000 + i).toString(16), i);
    N.compactRunField(run);
    const r = E.compactRecord(run.field), row = {case: name, counts: r.counts, parts: {}};
    for (const [key, size] of [['node_coordinates', 8], ['triangles', 4], ['real', 4], ['imag', 4]]) {
      const raw = Buffer.from(r[key], 'base64');
      row.parts[key] = {bytes: raw.length, base64: r[key].length, deflate: deflateSync(raw, {level: 6}).length, shuffledDeflate: deflateSync(shuffle(raw, size), {level: 6}).length};
    }
    let zeros = 0, total = 0;
    for (const part of [run.field.real, run.field.imag]) for (const mode of part) for (const v of mode) for (const x of v) {total++; if (x === 0) zeros++;}
    row.zeroShare = +(zeros / total).toFixed(4);
    rows.push(row); console.log(JSON.stringify(row));
  }
  await mkdir(out, {recursive: true}); await writeFile(join(out, 'f16.json'), JSON.stringify(rows, null, 1) + '\n');
}

// F14 (blind): run retention's K5 in a compact tab. Each case's run of the first solve (one-a) is
// named, pinned and numbered, beside a second run of the same case so that the tab is compact; its
// compact field's strings are kept and the field let go. Recompute Run N's fields with the second
// solve (one-b, a separate process): the stored values match (1e-12), the document is the run's,
// the field is attached to the same run and, at the arrival, made compact; its strings equal those
// of the field let go (the same build and thread setting).
async function f14(dir, out) {
  const N = await page('workspace-notebook.mjs'), X = await page('workspace-retention.mjs'), RR = await page('workspace-result-run.mjs'), E = await page('workspace-field-encoding.mjs');
  const report = {check: 'F14', cases: {}, failures: []};
  for (const name of Object.keys(CASES)) {
    const first = await resultOf(dir, name), second = JSON.parse(await readFile(join(dir, `${name}.one-b.result.json`), 'utf8'));
    const pending = await pendingOf(name, 'a0000004');
    const run = RR.runOfResult(first, pending, {completedAt: '2026-11-25T04:00:00.000Z'});
    Object.assign(run, {label: 'Design ' + name, pinned: true}); run.number = 4;
    const other = RR.runOfResult(first, await pendingOf(name, 'a0000005'), {completedAt: '2026-11-25T04:01:00.000Z'}); other.number = 5;
    const runs = [run, other], input = await inputsOf(name, run);
    // the tab is compact (the conversion of this tab, here forced by a budget no text fits)
    const converted = X.compactFields(input, runs, other.job, [run.job, other.job], VIEW, {budget: 1});
    const record = E.compactRecord(run.field), identity = JSON.stringify([run.job, run.number, run.label, run.pinned, run.completedAt, run.origin]);
    const stored = N.sessionText(input, [run], null, [null, null], VIEW, {keep: new Set()});
    const document = JSON.stringify(X.recomputeDocument(run)), expected = await readFile(join(dir, `${name}.document.json`), 'utf8');
    X.letGoField(run);
    const fresh = RR.runOfResult(second, {...pending, job: run.job}, {completedAt: run.completedAt});
    const mismatch = X.recomputeMismatch(run, fresh);
    if (!mismatch) X.attachField(run, fresh.field);
    // the arrival: the recomputed field comes into a compact tab
    const arrival = X.chooseFieldsAtArrival(input, runs, other.job, [run.job, other.job], VIEW, {first: [run.job]});
    const again = E.compactRecord(run.field);
    const entry = {converted: converted.converted.length, documentEqual: document === expected, match: mismatch === null, mismatch, compact: E.isCompactField(run.field),
      sameStrings: !!again && ['node_coordinates', 'triangles', 'real', 'imag'].every(k => again[k] === record[k]), sameRecord: N.sessionText(input, [run], null, [null, null], VIEW, {keep: new Set()}) === stored,
      identityKept: JSON.stringify([run.job, run.number, run.label, run.pinned, run.completedAt, run.origin]) === identity, arrivalConverted: arrival.converted.map(r => r.number)};
    report.cases[name] = entry; console.log(name, JSON.stringify(entry));
    for (const [key, text] of [['documentEqual', 'the recompute document differs'], ['match', 'the values do not match'], ['compact', 'the recomputed field is not compact'],
      ['sameStrings', 'the strings differ from those of the field let go'], ['sameRecord', 'the stored values changed'], ['identityKept', 'the run changed identity']])
      if (!entry[key]) report.failures.push(`${name}: ${text}`);
  }
  await mkdir(out, {recursive: true}); await writeFile(join(out, 'f14.json'), JSON.stringify(report, null, 1) + '\n');
  console.log(JSON.stringify({failures: report.failures}));
  if (report.failures.length) process.exitCode = 1;
}

const [command, ...rest] = process.argv.slice(2);
if (command === 'f9') await f9(resolve(rest[0]), resolve(rest[1]));
else if (command === 'f16') await f16(resolve(rest[0]), resolve(rest[1]));
else if (command === 'f14') await f14(resolve(rest[0]), resolve(rest[1]));
else if (command === 'sizes') await sizes(resolve(rest[0]), resolve(rest[1]));
else throw new Error('usage: node tools/studio_field_encoding.mjs f9|f14|f16|sizes <dir> <out>');
