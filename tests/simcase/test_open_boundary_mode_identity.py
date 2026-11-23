# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Slice P3: mode identity under an open boundary (PML), on the documents Studio's
optical-shapes-v9 builder writes (tests/simcase/open_boundary_fixtures.py).

The physical window of an open result is the set of triangles whose centroid lies inside its
``physical_bounds``; the TE fraction and the effective area are the closed-window formulas summed
there (simcase.mode_postprocessing), and n_g is the complex central difference of
``results.group_index`` (simcase.group_index). Registered before the results unless marked:

- V9: TE fraction on the physical window. The V1 film (220 nm Si over a 500 nm silica gap and an
  Si substrate through the bottom PML, PEC side walls, TE, target 2.85) at every element length
  x 1, 1/2, 1/4 against the exact slab limit f_TE = 1: 1 - f_TE <= 1e-3 at each level and
  strictly decreasing (x 1 measured before, 5.7e-4; the halvings blind). The template open
  against closed: |delta f_TE| <= 1e-3 for both modes (measured before, 1.7e-4).
- V10: effective area, the template open against closed: relative difference <= 1e-2 for both
  modes (measured before, 7e-4).
- V11 (n_g under the PML): tests/simcase/test_open_boundary_group_index.py.
- V12 (blind): Studio's teFraction and effectiveArea (workspace-modes.mjs, in Node) on the
  physical window of the saved samples equal the engine's values to 1e-12 relative, on the
  template and the strip over a substrate, all edges open; the window equals galerkin's own
  physical mask of the solve.
- V13 (registered after the result, decision pml-p3-v13-v11-reregistration): P2's blind check
  (closed against open, eta >= 0.99) failed with 0.9903 / 0.9875; the diagnosis found the default
  mesh's discretization error, not the PML. Not blind; measured values in the commit:
  - V13a: the open template against the same document with the PML removed (PEC at the outer
    edge, the same mesh), both on the physical window: eta >= 0.9999 for both modes.
  - V13b: the template closed against open at x 1: both modes paired with their own counterpart
    by Studio's rule (eta >= 0.8, margin >= 0.1).
  - V13c: TE-like, 1 - eta(closed, open) decreasing over x 1, 1/2, 1/4; TM-like reported where
    the open run returns it (before the gain bound of pml_modes.md the filter dropped it on refined
    meshes; since, it is returned at every level).
"""
from __future__ import annotations

import copy
import json
import subprocess

import numpy as np
import pytest

from open_boundary_fixtures import ALL, CLOSED, STATIC, TOP_BOTTOM, build, node, scaled
from simcase import Document, run
from simcase.mode_postprocessing import physical_window
from simcase.physics_pml_modes import coordinates
from simcase.runner import build_mesh


def solve(d):
    d = copy.deepcopy(d)
    d.setdefault("results", {})["plots"] = False
    return run(Document.from_dict(d), False)


def template(edges, factor=1):
    return scaled(build("template", 2, edges=edges, single=True), factor)


def without_pml(d):
    """The open document with its PML removed: PEC at the outer edge, the same mesh."""
    d = copy.deepcopy(d)
    del d["physics"]["em1"]["pml"], d["physics"]["em1"]["target_effective_index"]
    return d


def bounds(result):
    return result.open_boundary[0]["physical_bounds"]["values"]


def studio_side(result, physical_bounds=None):
    """A run as Studio's matching reads it (workspace-match.mjs matchSide)."""
    e = result.vector_fields[0].electric.transpose(1, 0, 2)
    side = {"settings": {"boundary": "PEC"}, "input": {"model": {"coreMesh": 30}},
            "effective_index": np.real(result.effective_index[0]).tolist(),
            "field": {"node_coordinates": result.node_coordinates.tolist(), "triangles": result.triangles.tolist(),
                      "real": e.real.tolist(), "imag": e.imag.tolist()}}
    if physical_bounds is not None:
        side["settings"] = {"boundary": "PML"}
        side["open_boundary"] = {"physical_bounds": {"unit": "m", "values": physical_bounds}}
    return side


_NODE = r"""
import fs from 'node:fs';
const M = await import(process.argv[1]);
const X = await import(process.argv[2]);
const job = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
let out;
if (job.kind === 'identity') {
  out = job.runs.map(r => {
    const w = M.physicalWindow(r.field, M.physicalBounds(r.open_boundary));
    return {window: w, te: r.effective_index.map((_, i) => M.teFraction(r.field, i, w)),
            area: r.effective_index.map((_, i) => M.effectiveArea(r.field, i, w))};
  });
} else {
  out = job.pairs.map(([a, b]) => {
    const m = X.opticalMatch(a, b);
    return {eta: m.eta, pairs: m.pairs.map(p => ({a: p.unitA, b: p.unitB, eta: p.eta, accepted: p.accepted})),
            disabled: m.disabled ?? null};
  });
}
process.stdout.write(JSON.stringify(out));
"""


def studio(job, tmp_path):
    path = tmp_path / "job.json"
    path.write_text(json.dumps(job), encoding="utf-8")
    done = subprocess.run([node(), "--input-type=module", "-e", _NODE, (STATIC / "workspace-modes.mjs").as_uri(),
                           (STATIC / "workspace-match.mjs").as_uri(), str(path)],
                          capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    return json.loads(done.stdout)


def te_fraction(result):
    return result.postprocessing["te_polarization_fraction"][0]


def area(result):
    return result.postprocessing["effective_area"][0]


# -- V9, V10: the template open against closed ---------------------------------------------------

@pytest.fixture(scope="module")
def template_runs():
    return solve(template(CLOSED)), solve(template(ALL))


def test_v9_v10_template_open_against_closed(template_runs):
    closed, opened = template_runs
    assert opened.open_boundary is not None and closed.open_boundary is None
    # the closed run is unchanged: the physical window of a closed run is the whole window
    assert set(closed.postprocessing) >= {"te_polarization_fraction", "effective_area", "unnormalized_mode_power"}
    df = np.abs(te_fraction(opened) - te_fraction(closed))
    da = np.abs(area(opened) / area(closed) - 1)
    print(f"\nV9 template f_TE closed {te_fraction(closed)}, open {te_fraction(opened)}, |delta| {df}")
    print(f"V10 template A_eff closed {area(closed)}, open {area(opened)}, relative {da}")
    assert np.all(df <= 1e-3), df
    assert np.all(da <= 1e-2), da
    assert set(opened.postprocessing) == {"te_polarization_fraction", "effective_area"}
    block = opened.summary()["mode_postprocessing"]
    assert list(block) == ["te_polarization_fraction", "effective_area", "integration_region"]
    assert block["integration_region"] == "physical_window"
    assert "integration_region" not in closed.summary()["mode_postprocessing"]


# -- V9: the film ----------------------------------------------------------------------------------

@pytest.mark.slow
def test_v9_film_te_fraction_converges_to_one():
    text = build("slab", 1, target=2.85, edges=TOP_BOTTOM, single=True)
    deficits = []
    for factor in (1, 0.5, 0.25):
        result = solve(scaled(text, factor))
        deficits.append(float(1 - te_fraction(result)[0]))
    print(f"\nV9 film 1 - f_TE at x 1, 1/2, 1/4: {deficits}")
    assert all(d <= 1e-3 for d in deficits), deficits
    assert deficits[0] > deficits[1] > deficits[2], deficits


# -- V12: the same formula in the engine and in Studio ----------------------------------------------

@pytest.mark.parametrize("kind", ["template", "strip_substrate"])
def test_v12_studio_equals_the_engine_on_the_physical_window(kind, tmp_path):
    d = json.loads(build(kind, 2, edges=ALL, single=True))
    result = solve(d)
    side = studio_side(result, bounds(result))
    got = studio({"kind": "identity", "runs": [side]}, tmp_path)[0]
    window = physical_window(result.node_coordinates, result.triangles, bounds(result))
    # the window is galerkin's own physical mask of the solve (in the micrometre frame)
    model = build_mesh(Document.from_dict({**d, "results": {"plots": False}}))
    kp = model.kernel_doc.sole_physics()[1]
    assert np.array_equal(window, coordinates(model.solver_mesh, kp["pml"], kp.get("bend")).physical)
    assert got["window"] == window.tolist()
    te = np.abs(np.array(got["te"]) / te_fraction(result) - 1)
    a = np.abs(np.array(got["area"]) / area(result) - 1)
    print(f"\nV12 {kind}: {int(window.sum())} of {len(window)} triangles; relative f_TE {te}, A_eff {a}")
    assert np.all(te <= 1e-12) and np.all(a <= 1e-12), (te, a)


# -- V13: matching a closed and an open run -------------------------------------------------------

def test_v13a_v13b_the_pml_changes_no_overlap_and_the_modes_pair(template_runs, tmp_path):
    closed, opened = template_runs
    pec = solve(without_pml(template(ALL)))
    assert np.array_equal(pec.triangles, opened.triangles)
    b = bounds(opened)
    a13, b13 = studio({"kind": "match", "pairs": [[studio_side(pec, b), studio_side(opened, b)],
                                                  [studio_side(closed), studio_side(opened, b)]]}, tmp_path)
    eta_a = [a13["eta"][i][i] for i in range(2)]
    print(f"\nV13a eta(PEC outer edge, open) {eta_a}")
    print(f"V13b closed vs open: {b13['pairs']}")
    assert all(e >= 0.9999 for e in eta_a), eta_a
    assert b13["disabled"] is None
    assert sorted((p["a"], p["b"], p["accepted"]) for p in b13["pairs"]) == [([0], [0], True), ([1], [1], True)], b13


@pytest.mark.slow
def test_v13c_the_overlap_deficit_converges(tmp_path):
    deficits, tm = [], []
    for factor in (1, 0.5, 0.25):
        closed, opened = solve(template(CLOSED, factor)), solve(template(ALL, factor))
        m = studio({"kind": "match", "pairs": [[studio_side(closed), studio_side(opened, bounds(opened))]]},
                   tmp_path)[0]
        deficits.append(1 - m["eta"][0][0])
        found = te_fraction(opened) <= 0.1
        tm.append((factor, np.real(opened.effective_index[0]).tolist(),
                   1 - m["eta"][1][int(np.flatnonzero(found)[0])] if found.any() else "not returned"))
    print(f"\nV13c TE-like 1 - eta at x 1, 1/2, 1/4: {deficits}")
    print(f"V13c TM-like (factor, open n_eff, 1 - eta or not returned): {tm}")
    assert deficits[0] > deficits[1] > deficits[2], deficits
