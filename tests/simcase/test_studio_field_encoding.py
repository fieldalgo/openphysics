# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Compact field encoding, F5 (pre-registered): one encoding, two writers.

Studio's encoder (workspace-field-encoding.mjs, run in Node) and a NumPy reference
(``astype('<f4')``, ``'<f8'``, ``'<u4'`` and ``base64.b64encode``; NumPy only) write the same strings
for every field of the session fixtures, and the compact fixture's strings are NumPy's encoding of
the values they decode to. With STUDIO_RETENTION_RESULTS set to a folder of
``tools/studio_run_retention.mjs engine`` results, the five T18 results' fields are compared too.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
from pathlib import Path

import numpy as np
import pytest

from open_boundary_fixtures import STATIC, node

FIXTURES = Path(__file__).parent / "studio_session_fixtures"
SESSION = '{"format":"openphysics-studio-session"'

# Every field in a fixture: an object holding node_coordinates, triangles, real and imag of nested
# numbers, found in the file and in any session text a file holds (sessions-rewritten-13f07f4.json).
# Each is encoded by Studio's encoder; its path is printed so this test finds the same field.
_ENCODE = r"""
import fs from 'node:fs';
const E = await import(process.argv[1]);
const out = [];
const walk = (value, file, path) => {
  if (typeof value === 'string' && value.startsWith('{"format":"openphysics-studio-session"')) return walk(JSON.parse(value), file, [...path, '#']);
  if (!value || typeof value !== 'object') return;
  if (!Array.isArray(value) && ['node_coordinates', 'triangles', 'real', 'imag'].every(k => Array.isArray(value[k]))) {
    try { out.push({file, path, encoded: E.encodeField(value)}); } catch (e) { out.push({file, path, refused: e.message}); }
    return;
  }
  for (const [k, v] of Object.entries(value)) walk(v, file, [...path, k]);
};
for (const file of process.argv.slice(2)) walk(JSON.parse(fs.readFileSync(file, 'utf8')), file, []);
process.stdout.write(JSON.stringify(out));
"""


def _load(text: str):
    # "-0" keeps its sign, as JavaScript's JSON.parse keeps it
    return json.loads(text, parse_int=lambda s: -0.0 if s == "-0" else int(s))


def _numpy(field) -> dict:
    """The compact record's four strings, written by NumPy."""
    b64 = lambda a: base64.b64encode(a.tobytes()).decode("ascii")
    return {
        "node_coordinates": b64(np.asarray(field["node_coordinates"], dtype=float).astype("<f8")),
        "triangles": b64(np.asarray(field["triangles"], dtype=np.int64).astype("<u4")),
        "real": b64(np.asarray(field["real"], dtype=float).astype("<f4")),
        "imag": b64(np.asarray(field["imag"], dtype=float).astype("<f4")),
    }


def _at(document, path):
    for key in path:
        document = _load(document) if key == "#" else document[int(key) if isinstance(document, list) else key]
    return document


def _studio(files):
    done = subprocess.run([node(), "--input-type=module", "-e", _ENCODE, (STATIC / "workspace-field-encoding.mjs").as_uri(), *map(str, files)],
                          capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def _compare(files):
    documents = {str(f): _load(Path(f).read_text(encoding="utf-8")) for f in files}
    encoded = _studio(files)
    for item in encoded:
        field = _at(documents[item["file"]], item["path"])
        if "refused" in item:
            # a sample beyond single precision: Studio refuses to encode it, and NumPy's float32 is not finite
            assert item["refused"] == "A field sample is beyond single precision.", item
            with np.errstate(over="ignore"):
                assert not all(np.isfinite(np.asarray(field[k], dtype=float).astype("<f4")).all() for k in ("real", "imag")), item
            continue
        expected = _numpy(field)
        for key, text in expected.items():
            assert item["encoded"][key] == text, (item["file"], item["path"], key)
        assert item["encoded"]["counts"] == {"modes": len(field["real"]), "nodes": len(field["node_coordinates"]), "triangles": len(field["triangles"])}
    return encoded


def test_f5_fixture_fields_have_the_same_strings_in_studio_and_numpy():
    files = sorted(p for p in FIXTURES.glob("*.json") if p.name != "optical-v14-compact.json")
    encoded = _compare(files)
    # every fixture that holds a field is covered: the optical files of versions 6 to 13 and the session texts
    covered = {Path(item["file"]).name for item in encoded if "encoded" in item}
    # project-v1.json's synthetic samples hold 1e308 (beyond float32): its two fields are refused
    assert sorted(Path(item["file"]).name for item in encoded if "refused" in item) == ["project-v1.json", "project-v1.json"]
    assert {"optical-v6-one.json", "optical-v7-three.json", "optical-v10-open-full-083e151.json", "optical-v12-numbers.json",
            "optical-v13-nine-runs.json", "sessions-rewritten-13f07f4.json"} <= covered
    assert sum("encoded" in item for item in encoded) >= 20
    # a -0 sample is encoded with its sign (its float32 bytes are 00 00 00 80)
    assert any(base64.b64decode(item["encoded"]["real"])[8:12] == b"\x00\x00\x00\x80" for item in encoded if Path(item["file"]).name == "optical-v13-nine-runs.json" and "encoded" in item)


def test_f5_the_compact_fixture_holds_numpy_strings_of_its_decoded_values():
    session = _load((FIXTURES / "optical-v14-compact.json").read_text(encoding="utf-8"))
    compact = [run["field"] for run in session["runs"] if "encoding" in run["field"]]
    assert len(compact) == 2
    for record in compact:
        c = record["counts"]
        coordinates = np.frombuffer(base64.b64decode(record["node_coordinates"], validate=True), dtype="<f8").reshape(c["nodes"], 2)
        triangles = np.frombuffer(base64.b64decode(record["triangles"], validate=True), dtype="<u4").reshape(c["triangles"], 3)
        real = np.frombuffer(base64.b64decode(record["real"], validate=True), dtype="<f4").reshape(c["modes"], c["triangles"], 3)
        imag = np.frombuffer(base64.b64decode(record["imag"], validate=True), dtype="<f4").reshape(c["modes"], c["triangles"], 3)
        again = _numpy({"node_coordinates": coordinates, "triangles": triangles, "real": real.astype(float), "imag": imag.astype(float)})
        assert all(record[key] == again[key] for key in again)
        assert triangles.max() < c["nodes"] and np.isfinite(real).all() and np.isfinite(imag).all()
    # the open run is a0000004 of the version 10 file: its samples are the float32 roundings, its mesh exact
    source = next(r for r in _load((FIXTURES / "optical-v10-open-full-083e151.json").read_text(encoding="utf-8"))["runs"] if r["job"] == "a0000004")["field"]
    assert compact[0] == {"encoding": "f32-base64-v1", "counts": compact[0]["counts"], **_numpy(source)}


# Defined only with engine results to compare (as test_units_batch_equivalence.py defines its
# harness tests), so a run without them, such as the installed-package suite, records no skip.
if os.environ.get("STUDIO_RETENTION_RESULTS"):

    def test_f5_t18_results_have_the_same_strings_in_studio_and_numpy(tmp_path):
        folder = Path(os.environ["STUDIO_RETENTION_RESULTS"])
        files = []
        for case in ["t18closed2", "t18closed4", "t18near", "t16", "t18open"]:
            result = _load(next(folder.glob(f"{case}.*.result.json")).read_text(encoding="utf-8"))
            f = result["vector_fields"][0]
            path = tmp_path / f"{case}.json"
            path.write_text(json.dumps({"node_coordinates": result["node_coordinates"], "triangles": result["triangles"], "real": f["real"], "imag": f["imag"]}), encoding="utf-8")
            files.append(path)
        assert len(_compare(files)) == 5
