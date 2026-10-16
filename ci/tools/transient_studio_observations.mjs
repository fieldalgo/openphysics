// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Assertions for recorded browser observations, not a solver or wire parser.
import assert from 'node:assert/strict';

const identityKeys = ['kind', 'job', 'result_id', 'client_revision', 'request_seq',
  'result_format', 'field_layout', 'display_length_in_m'];

function identity(manifest, reply, selection) {
  assert.equal(manifest.payload_format, 'studio-thermal-transient-v1');
  assert.equal(manifest.kind, 'thermal.transient2d');
  assert.ok(typeof manifest.result_id === 'string' && manifest.result_id.length);
  for (const key of identityKeys) assert.deepEqual(reply[key], manifest[key], key);
  assert.ok(Number.isSafeInteger(selection.frameSeq) && selection.frameSeq >= 0);
  assert.equal(reply.frame_seq, selection.frameSeq, 'view sequence');
  assert.equal(reply.field, selection.field, 'selected field');
  const times = manifest.time_s;
  assert.ok(Array.isArray(times) && times.length >= 2);
  assert.ok(times.every((t, i) => Number.isFinite(t) && (i === 0 || t > times[i-1])));
  const descriptor = manifest.fields[selection.field];
  assert.ok(descriptor, 'selected descriptor exists');
  assert.equal(reply.unit, descriptor.unit);
  assert.equal(reply.location, descriptor.location);
  assert.ok(['time_s', 'time_s[1:]'].includes(descriptor.axis));
  assert.equal(descriptor.shape[0], times.length - (descriptor.axis === 'time_s[1:]' ? 1 : 0));
  return descriptor;
}

function numericShape(value, shape) {
  if (!shape.length) {
    assert.equal(typeof value, 'number');
    assert.ok(Number.isFinite(value));
    return;
  }
  assert.ok(Array.isArray(value));
  assert.equal(value.length, shape[0]);
  for (const row of value) numericShape(row, shape.slice(1));
}

export function assertFrameObservation(manifest, frame, selection) {
  const descriptor = identity(manifest, frame, selection);
  assert.equal(frame.payload_format, 'studio-thermal-transient-frame-v1');
  assert.ok(descriptor.available_views.includes('frame'));
  const i = selection.timeIndex;
  assert.ok(Number.isSafeInteger(i) && i >= 0 && i < manifest.time_s.length);
  assert.equal(frame.time_index, i);
  assert.equal(frame.time_s, manifest.time_s[i], 'exact stored time');
  if (descriptor.axis === 'time_s[1:]') {
    assert.ok(i >= 1, 'initial rate is unavailable');
    assert.equal(frame.interval_start_s, manifest.time_s[i-1]);
    assert.equal(frame.interval_end_s, manifest.time_s[i]);
  }
  assert.deepEqual(frame.shape, descriptor.shape.slice(1));
  assert.deepEqual(Object.keys(frame.arrays), [selection.field]);
  numericShape(frame.arrays[selection.field], frame.shape);
  if (Object.hasOwn(selection, 'shownTimeS')) assert.equal(selection.shownTimeS, frame.time_s);
  return frame.arrays[selection.field];
}

export function assertCurrentFrameRange(manifest, frame, selection, observed) {
  const values = assertFrameObservation(manifest, frame, selection);
  assert.ok(['temperature_k', 'heat_flux_w_m2'].includes(selection.field));
  let scalars = values;
  if (selection.field === 'heat_flux_w_m2') {
    assert.ok(['qx', 'qy', 'magnitude'].includes(selection.component));
    scalars = values.map(([x, y]) => selection.component === 'qx' ? x :
      selection.component === 'qy' ? y : Math.hypot(x, y));
  }
  assert.ok(scalars.length && scalars.every(Number.isFinite), 'finite display derivative');
  let minimum = Infinity, maximum = -Infinity;
  for (const value of scalars) { minimum = Math.min(minimum, value); maximum = Math.max(maximum, value); }
  assert.equal(observed.minimum, minimum, 'current frame minimum');
  assert.equal(observed.maximum, maximum, 'current frame maximum');
  assert.equal(observed.unit, frame.unit);
  assert.equal(observed.rangePolicy, 'current-frame');
}

export function assertHistoryObservation(manifest, page, selection) {
  const descriptor = identity(manifest, page, selection);
  assert.equal(page.payload_format, 'studio-thermal-transient-history-v1');
  assert.ok(descriptor.available_views.includes('history'));
  const {start, stop} = selection;
  assert.ok(Number.isSafeInteger(start) && Number.isSafeInteger(stop));
  assert.ok(start >= 0 && start < stop && stop <= manifest.time_s.length && stop-start <= 16);
  if (descriptor.axis === 'time_s[1:]') assert.ok(start >= 1, 'initial rate is unavailable');
  assert.equal(page.start, start); assert.equal(page.stop, stop);
  assert.deepEqual(page.time_indices, Array.from({length: stop-start}, (_, i) => start+i));
  assert.deepEqual(page.time_s, manifest.time_s.slice(start, stop));
  assert.deepEqual(page.shape, [stop-start, ...descriptor.shape.slice(1)]);
  assert.deepEqual(Object.keys(page.arrays), [selection.field]);
  numericShape(page.arrays[selection.field], page.shape);
  return page.arrays[selection.field];
}
