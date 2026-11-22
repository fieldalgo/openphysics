# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The open boundary of Studio's optical document (adapter optical-shapes-v9, capabilities v9).

The document builder is tests/simcase/studio_open_boundary.cjs; here the capabilities, the server's
refusal of other workspace PMLs, the adapter's index table against physmat, and the validation of
the documents it writes:

- V1/V2: a leaky slab in the app's window (220 nm Si film, 500 nm silica gap, Si substrate through
  the bottom PML) against ``refsol.lossy_slab.substrate_leaky_mode``, TE with PEC side walls and TM
  with PMC side walls (edited in the built document), every element length x 1, 1/2, 1/4;
- V4: PML independence of a strip over a Si substrate (all edges open);
- V5: no false leakage of the template strip in silica;
- V6: mesh convergence of the strip over a substrate, every element length x 1, 0.7, 0.5;
- V7: with every edge closed, the optical-shapes-v8 result;
- V8: the candidate filter (physical fraction 0.5, a search of 16).

Mesh scaling multiplies every element length of the built document (mesh.element_size, the
grading's near and far, each shape's element_size); refinement_distance is a distance and stays.
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

import physmat
import refsol.lossy_slab
from simcase import Document, run

HERE = Path(__file__).resolve().parent
STATIC = HERE.parents[1] / "packages" / "simcase" / "src" / "simcase" / "studio" / "static"
FIXTURES = HERE / "studio_session_fixtures"
WAVELENGTH = 1.55e-6
DB = 10 * np.log10(np.e)

_BUILD = r"""
const O = await import(process.argv[1]);
const [kind, modes, t, target, edges] = process.argv.slice(2);
const strip = {name: 'Core', type: 'rect', material: 'Silicon', x: -250, y: 0, w: 500, h: 220};
const film = {name: 'Film', type: 'rect', material: 'Silicon', x: -1500, y: 0, w: 3000, h: 220};
const substrate = {name: 'Substrate', type: 'rect', material: 'Silicon', x: -1500, y: -1200, w: 3000, h: 700};
const shapes = {template: [strip], slab: [film, substrate], strip_substrate: [strip, substrate]}[kind];
const openBoundary = {edges: JSON.parse(edges), thickness: Number(t)};
if (target !== '-') openBoundary.target = Number(target);
const doc = O.opticalDocument({electric: false, heat: false, structure: false, optics: true, wavelength: 1550, coreMesh: 30,
  modeCount: Number(modes), shapes, openBoundary}, {materials: {Core: 'Silicon', Oxide: 'Silica', Heater: ''}});
process.stdout.write(JSON.stringify(doc));
"""
ALL = {"left": "open", "right": "open", "bottom": "open", "top": "open"}
TOP_BOTTOM = {"left": "closed", "right": "closed", "bottom": "open", "top": "open"}
CLOSED = {"left": "closed", "right": "closed", "bottom": "closed", "top": "closed"}


def node():
    found = shutil.which("node")
    if found is None:
        pytest.skip("node is not installed; the studio_open_boundary.cjs suite checks the page modules")
    return found


def build(kind, modes, thickness=1000, target="-", edges=ALL, script=_BUILD):
    """The document Studio's optical-shapes-v9 builder writes (exact text and parsed)."""
    done = subprocess.run([node(), "--input-type=module", "-e", script, (STATIC / "workspace-optical.mjs").as_uri(),
                           kind, str(modes), str(thickness), str(target), json.dumps(edges)],
                          capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout


def scaled(text, factor):
    d = json.loads(text)
    nm = lambda v: f"{float(v.split()[0]) * factor:g} nm"       # noqa: E731
    d["mesh"]["element_size"] = nm(d["mesh"]["element_size"])
    for key in ("near", "far"):
        d["mesh"]["grading"][key] = nm(d["mesh"]["grading"][key])
    for shape in d["geometry"]["shapes"]:
        if "element_size" in shape:
            shape["element_size"] = nm(shape["element_size"])
    return d


def solve(d):
    d = copy.deepcopy(d)
    d["results"] = {"plots": False}
    r = run(Document.from_dict(d), False)
    point = r.open_boundary[0]
    chosen = {c["candidate"]: c for c in point["candidates"]}
    fraction = [chosen[i]["physical_l2_fraction"] for i in point["selected_candidates"]]
    return r.effective_index[0], r.propagation_loss()[0] / 100, np.asarray(fraction), point["candidates"]


def silicon_and_silica():
    return tuple(complex(physmat.material(name).refractive_index(vacuum_wavelength=WAVELENGTH))
                 for name in ("Si", "SiO2"))


def slab_reference(pol):
    si, sio2 = silicon_and_silica()
    return refsol.lossy_slab.substrate_leaky_mode(refractive_index=(sio2, si, sio2, si), thickness=(0.22e-6, 0.5e-6),
                                                  vacuum_wavelength=WAVELENGTH, pol=pol)


def db_per_cm(n):
    return 4 * np.pi * n.imag / WAVELENGTH * DB / 100


# -- contract ------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from simcase.studio import app
    return TestClient(app)


def test_capabilities_v9_is_v8_with_the_open_boundary(client):
    v8 = client.get("/api/workspace/capabilities/v8").json()
    v9 = client.get("/api/workspace/capabilities/v9").json()
    assert v9.pop("open_boundary") == {
        "edges": ["left", "right", "bottom", "top"], "edge_states": ["closed", "open"], "edge_default": "closed",
        "pml_thickness_range": ["1 um", "2 um"], "pml_thickness_default": "1 um", "pml_strength": 3, "pml_order": 2,
        "pml_minimum_physical_fraction": 0.5, "pml_search_mode_count": 16,
        "target_effective_index_default": "(n_max + n_SiO2) / 2 at 1550 nm, two decimals",
        "target_effective_index_bounds": "above 1.45 and below n_max"}
    assert (v9.pop("schema_version"), v9.pop("adapter")) == (9, "optical-shapes-v9")
    assert (v8.pop("schema_version"), v8.pop("adapter")) == (8, "optical-shapes-v8")
    assert v9 == v8


def test_the_index_table_is_physmat_at_1550_nm():
    script = "const B = await import(process.argv[1]); process.stdout.write(JSON.stringify(B.INDEX_1550));"
    done = subprocess.run([node(), "--input-type=module", "-e", script, (STATIC / "workspace-open-boundary.mjs").as_uri()],
                          capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
    table = json.loads(done.stdout)
    shapes = subprocess.run([node(), "--input-type=module", "-e",
                             "const S = await import(process.argv[1]); process.stdout.write(JSON.stringify(S.SHAPE_MATERIALS));",
                             (STATIC / "workspace-shapes.mjs").as_uri()], capture_output=True, text=True, encoding="utf-8")
    materials = json.loads(shapes.stdout)
    assert set(table) == set(materials)
    for display, name in materials.items():
        n = complex(physmat.material(name.removeprefix("physmat:")).refractive_index(vacuum_wavelength=WAVELENGTH))
        assert table[display] == round(n.real, 4), display


def _instance(client):
    return {"workspace_instance": client.get("/api/workspace/capabilities/v9").json()["server_instance"]}


@pytest.mark.parametrize("change", [
    {"pml_strength": 6}, {"pml_order": 3}, {"pml_minimum_physical_fraction": 0.1}, {"pml_search_mode_count": 6},
    {"pml_search_mode_count": 16.0}, {"pml_order": True}, {"pml_thickness": {"top": "999 nm"}},
    {"pml_thickness": {"top": "2001 nm"}}, {"pml_thickness": {"top": "1 um"}}, {"pml_thickness": {"top": "1000 nm", "bottom": "1500 nm"}},
    {"extra": 1},
    {"target_effective_index": 1.45}, {"target_effective_index": True},
    {"domain": {"xmin": -1500, "xmax": 2500, "ymin": -2200, "ymax": 2200}},
    {"domain": {"xmin": -2500, "xmax": 2500, "ymin": -2200, "ymax": 2300}},
    {"length_unit": "um"},
])
def test_the_server_refuses_another_workspace_pml(client, change):
    doc = json.loads(build("template", 2, edges=ALL))
    if "target_effective_index" in change:
        doc["physics"]["em1"].update(change)
    elif "domain" in change:
        doc["geometry"]["domain"] = change["domain"]
    elif "length_unit" in change:
        doc["geometry"]["length_unit"] = change["length_unit"]
    else:
        doc["physics"]["em1"]["pml"].update(change)
    for route in ("/api/validate", "/api/run"):
        response = client.post(route, params=_instance(client), json={"doc": doc})
        assert response.status_code == 400 and "open boundary of a workspace run" in response.text, response.text


def test_the_server_takes_the_v9_document(client):
    doc = json.loads(build("strip_substrate", 2, thickness=1500, edges=TOP_BOTTOM))
    response = client.post("/api/validate", params=_instance(client), json={"doc": doc})
    assert response.status_code == 200 and response.json()["ok"], response.text


# -- V7: closed window --------------------------------------------------------------------------

def _without_timing(value):
    if isinstance(value, dict):
        return {k: _without_timing(v) for k, v in value.items() if k != "timing"}
    if isinstance(value, list):
        return [_without_timing(v) for v in value]
    return value


def _saved(text, folder):
    run(Document.from_dict(json.loads(text)), False).save(folder)
    summary = _without_timing(json.loads((folder / "summary.json").read_text(encoding="utf-8")))
    with np.load(folder / "fields.npz") as archive:
        arrays = {k: archive[k].tobytes() for k in archive.files if k != "metadata_json"}
        metadata = _without_timing(json.loads(str(archive["metadata_json"])))
    return summary, metadata, arrays


@pytest.mark.parametrize("modes,fixture", [(1, "optical-document-template-v8-1.json"), (2, "optical-document-template-v7.json"),
                                           (8, "optical-document-template-v8-8.json")])
def test_v7_every_edge_closed_is_the_v8_document_and_result(tmp_path, modes, fixture):
    text = build("template", modes, edges=CLOSED)
    expected = (FIXTURES / fixture).read_text(encoding="utf-8")
    assert text == expected
    if modes == 2:
        # the same document gives the same result (wall-clock timings aside)
        assert _saved(text, tmp_path / "v9") == _saved(expected, tmp_path / "v8")


# -- V1/V2: leaky slab in the app's window -------------------------------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("pol,target", [("TE", 2.85), ("TM", 2.06)])
def test_v1_v2_leaky_slab_converges_to_the_analytic_pole(pol, target):
    expected = slab_reference(pol)
    text = build("slab", 1, target=target, edges=TOP_BOTTOM)
    loss_errors, re_errors = [], []
    for factor in (1, 0.5, 0.25):
        d = scaled(text, factor)
        if pol == "TM":
            d["physics"]["em1"]["boundary"].update(left="pmc", right="pmc")
        n, loss, _, _ = solve(d)
        loss_errors.append(abs(loss[0] / db_per_cm(expected) - 1))
        re_errors.append(abs(n[0].real - expected.real))
    assert loss_errors[0] > loss_errors[1] > loss_errors[2], loss_errors
    assert loss_errors[0] <= 0.035 and loss_errors[2] <= 0.005, loss_errors
    assert re_errors[2] <= 1e-3, re_errors


# -- V4: PML independence ------------------------------------------------------------------------

@pytest.mark.slow
def test_v4_strip_over_substrate_does_not_depend_on_the_pml():
    base_n, base_loss, _, _ = solve(json.loads(build("strip_substrate", 2)))
    variants = [json.loads(build("strip_substrate", 2, thickness=t)) for t in (1500, 2000)]
    for key, value in (("pml_strength", 1.5), ("pml_strength", 6), ("pml_order", 3)):
        d = json.loads(build("strip_substrate", 2))
        d["physics"]["em1"]["pml"][key] = value
        variants.append(d)
    for d in variants:
        n, loss, _, _ = solve(d)
        assert len(n) == 2
        assert np.all(abs(loss / base_loss - 1) <= 0.01), (d["physics"]["em1"]["pml"], loss, base_loss)
        assert np.all(abs(n.real - base_n.real) <= 5e-4), (d["physics"]["em1"]["pml"], n, base_n)


# -- V5: no false leakage ------------------------------------------------------------------------

@pytest.mark.slow
def test_v5_the_template_strip_in_silica_does_not_leak():
    losses, resolved = [], []
    for t in (1000, 1500, 2000):
        n, loss, fraction, _ = solve(json.loads(build("template", 2, thickness=t)))
        assert len(n) == 2 and np.all(fraction >= 0.5)
        assert np.all(loss < 0.01), loss
        losses.append(loss)
        resolved.append(abs(n.imag) > 1e-10 * np.maximum(1, abs(n.real)))
    for m in range(2):
        if resolved[0][m] and resolved[2][m]:
            assert losses[2][m] < losses[0][m], [x[m] for x in losses]


# -- V6: mesh convergence ------------------------------------------------------------------------

def richardson(h, values):
    """L0 of L = L0 + C h**p through three points (p by bisection on the ratio of differences)."""
    (h1, h2, h3), (l1, l2, l3) = h, values
    ratio = (l1 - l2) / (l2 - l3)
    lo, hi = 1e-3, 20.
    f = lambda p: (h1 ** p - h2 ** p) / (h2 ** p - h3 ** p) - ratio      # noqa: E731
    assert f(lo) * f(hi) < 0, "the three values are not monotone in h"
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(lo) * f(mid) > 0 else (lo, mid)
    p = (lo + hi) / 2
    c = (l2 - l3) / (h2 ** p - h3 ** p)
    return l3 - c * h3 ** p


@pytest.mark.slow
def test_v6_strip_over_substrate_mesh_convergence():
    text = build("strip_substrate", 2)
    h = (1, 0.7, 0.5)
    runs = [solve(scaled(text, factor))[1] for factor in h]
    for m in range(2):
        values = [loss[m] for loss in runs]
        assert abs(values[0] - values[1]) > abs(values[1] - values[2]), values
        extrapolated = richardson(h, values)
        assert abs(values[2] / extrapolated - 1) <= 0.02, (values, extrapolated)


# -- V8: the candidate filter --------------------------------------------------------------------

def _physical(candidates):
    return [complex(c["effective_index"]["re"], c["effective_index"]["im"]) for c in candidates
            if c["physical_l2_fraction"] >= 0.97 and c["effective_index"]["re"] > 1.45 and c["relative_residual"] <= 1e-8
            and "negative_imaginary_index" not in c["reasons"]]


def _check_filter(text, modes, target, reference_text, analytic=None):
    n, _, fraction, _ = solve(json.loads(text))
    assert len(n) <= modes
    assert np.all(fraction >= 0.5) and np.all(n.real > 1.45), (n, fraction)
    wide = json.loads(reference_text)
    wide["physics"]["em1"]["pml"]["pml_search_mode_count"] = 32
    physical = sorted(_physical(solve(wide)[3]), key=lambda z: abs(z - target))
    for z in physical[:modes]:
        assert np.min(abs(n - z)) <= 1e-6, (z, n)
    if analytic is not None:
        assert np.min(abs(n - analytic)) <= 1e-3, (analytic, n)


@pytest.mark.slow
@pytest.mark.parametrize("kind,modes", [("slab", 1), ("slab", 2), ("slab", 3), ("slab", 4), ("template", 4),
                                        ("strip_substrate", 2), ("strip_substrate", 8)])
def test_v8_the_filter_returns_physical_modes_only(kind, modes):
    edges = TOP_BOTTOM if kind == "slab" else ALL
    target = 2.85 if kind == "slab" else 2.46
    text = build(kind, modes, target=target if kind == "slab" else "-", edges=edges)
    reference = build(kind, 8, target=target if kind == "slab" else "-", edges=edges)
    _check_filter(text, modes, target, reference, slab_reference("TE") if kind == "slab" else None)
