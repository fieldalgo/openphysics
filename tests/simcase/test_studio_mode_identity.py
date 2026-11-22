# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""V13: Studio's TE fraction and effective area (workspace-modes.mjs, in Node) equal the engine's
saved ``te_polarization_fraction`` and ``effective_area`` on the same samples, to 1e-12 relative.

The samples are what Studio holds of a run: node_coordinates in metres, the triangles and the
complex centroid field per mode. The cases: the optical template as Studio builds it
(workspace-optical.mjs, 500 x 220 nm silicon strip, 30 nm core mesh) and the V4 wide cores
(tests/simcase/test_mode_polarization.py). Skipped without node, like the other Python tests
that call the Studio modules; the .cjs suite runs the module's own checks.
"""
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

import simcase
from simcase import Document, run

HERE = Path(__file__).resolve().parent
STATIC = Path(simcase.__file__).resolve().parent / "studio" / "static"

_TEMPLATE = r"""
const O = await import(process.argv[1]);
const doc = O.opticalDocument({height: 220, width: 500, wavelength: 1550, coreMesh: 30, electric: false, heat: false,
  structure: false, optics: true, shapes: [{name: 'Core', type: 'rect', material: 'Silicon', x: -250, y: 0, w: 500, h: 220}]},
  {materials: {Core: 'Silicon', Oxide: 'Silica', Heater: ''}});
process.stdout.write(JSON.stringify(doc));
"""

_FRACTIONS = r"""
import fs from 'node:fs';
const M = await import(process.argv[1]);
const cases = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = cases.map(c => ({
  fractions: c.field.real.map((_, i) => M.teFraction(c.field, i)),
  areas: c.field.real.map((_, i) => M.effectiveArea(c.field, i)),
  groups: M.degenerateGroups(c.neff),
  labels: c.neff.map((_, i) => M.modeOptionLabel(i, c.neff.map((re, j) => ({re, fte: M.teFraction(c.field, j)})))),
  loss: c.loss === null ? null : M.lossText(c.loss.im, c.loss.db_per_m)}));
process.stdout.write(JSON.stringify(out));
"""


def node():
    found = shutil.which("node")
    if found is None:
        pytest.skip("node is not installed; studio_mode_identity.cjs runs in the cjs suite")
    return found


def call(script, *args):
    done = subprocess.run([node(), "--input-type=module", "-e", script, *args], capture_output=True, text=True,
                          encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    return json.loads(done.stdout)


def polarization_module():
    spec = importlib.util.spec_from_file_location("mode_polarization", HERE / "test_mode_polarization.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def samples(result):
    """The run as Studio keeps it: (modes, triangles, components) real and imaginary parts."""
    e = result.vector_fields[0].electric.transpose(1, 0, 2)
    return {"node_coordinates": result.node_coordinates.tolist(), "triangles": result.triangles.tolist(),
            "real": e.real.tolist(), "imag": e.imag.tolist()}


def case(result, loss=False):
    n = result.effective_index[0]
    return {"field": samples(result), "neff": np.real(n).tolist(),
            "loss": {"im": float(n[0].imag), "db_per_m": float(result.propagation_loss()[0, 0])} if loss else None}


@pytest.mark.slow
def test_v13_studio_te_fraction_equals_the_engine(tmp_path):
    template = Document.from_dict(call(_TEMPLATE, (STATIC / "workspace-optical.mjs").as_uri()))
    results = [run(template, verbose=False)]
    T = polarization_module()
    for w in (1.0, 2.0, 4.0):
        half = w / 2 + 1.5
        results.append(run(T.document(0.03, window=(-half, half, -1.2, 1.2), mode_count=40,
                                      shapes=[{"name": "core", "type": "rect", "x": -w / 2, "y": 0.0, "w": w,
                                               "h": T.THICKNESS, "material": "physmat:Si"}]), verbose=False))
    lossy = run(T.strip(0.02, 1e-4), verbose=False)
    cases = [case(r) for r in results] + [case(lossy, loss=True)]
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    studio = call(_FRACTIONS, (STATIC / "workspace-modes.mjs").as_uri(), str(path))
    worst = 0.0
    for result, got in zip(results + [lossy], studio):
        engine = result.postprocessing["te_polarization_fraction"][0]
        assert len(got["fractions"]) == len(engine)
        for a, b in zip(got["fractions"], engine):
            assert np.isfinite(b) and a is not None
            worst = max(worst, abs(a - b) / abs(b) if b else abs(a))
    print(f"\nV13 worst relative difference Studio vs engine over {sum(len(g['fractions']) for g in studio)} modes: "
          f"{worst:.2e}")
    assert worst <= 1e-12
    worst_area = 0.0
    for result, got in zip(results + [lossy], studio):
        engine = result.postprocessing["effective_area"][0]
        assert len(got["areas"]) == len(engine)
        for a, b in zip(got["areas"], engine):
            assert np.isfinite(b) and b > 0 and a is not None
            worst_area = max(worst_area, abs(a - b) / b)
    print(f"V13 worst relative difference of A_eff Studio vs engine over {sum(len(g['areas']) for g in studio)} "
          f"modes: {worst_area:.2e}")
    assert worst_area <= 1e-12
    # the template's picker and the k = 1e-4 strip's loss text
    assert studio[0]["labels"][0].startswith("Mode 1 · TE-like · n_eff ")
    assert studio[0]["labels"][1].startswith("Mode 2 · TM-like · n_eff ")
    assert studio[0]["groups"] == []
    assert studio[-1]["loss"] == "37.49 dB/cm"


_GROUPS = r"""
const M = await import(process.argv[1]);
process.stdout.write(JSON.stringify(JSON.parse(process.argv[2]).map(re => M.degenerateGroups(re))));
"""


@pytest.mark.slow
def test_v5_studio_flags_the_square_pair_and_v5b_not_distinct_modes():
    """Studio's pair rule on the engine's n_eff: the 400 x 400 nm square is one pair at 40, 20 and
    10 nm for both grading centres (V5); the template strip and the 400 x 380 nm core are not (V5b)."""
    T = polarization_module()
    square = [run(T.square(h, centre), verbose=False).effective_index[0].real.tolist()
              for centre in (T.THICKNESS / 2, 0.2) for h in T.SIZES]
    distinct = [run(T.strip(h, mode_count=2), verbose=False).effective_index[0].real.tolist() for h in T.SIZES]
    distinct += [run(T.square(h, 0.19, h=0.38), verbose=False).effective_index[0].real.tolist() for h in T.SIZES]
    groups = call(_GROUPS, (STATIC / "workspace-modes.mjs").as_uri(), json.dumps(square + distinct))
    assert groups[:len(square)] == [[[0, 1]]] * len(square)
    assert groups[len(square):] == [[]] * len(distinct)
