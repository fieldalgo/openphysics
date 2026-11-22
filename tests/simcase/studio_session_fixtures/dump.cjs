// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// A dump that keeps what JSON loses: typed arrays by type, and -0.
exports.dump = value => JSON.stringify(value, function (key, v) {
  const raw = this[key];
  if (ArrayBuffer.isView(raw)) return {typed: raw.constructor.name, values: Array.from(raw, x => Object.is(x, -0) ? '-0' : x)};
  if (Object.is(raw, -0)) return '-0';
  return v;
}, 1);
