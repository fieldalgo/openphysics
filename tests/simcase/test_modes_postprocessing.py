# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Mode power, confinement, overlaps and Gaussian coupling saved with ``em.modes2d`` results.

Pre-registered gates (kept as written; every measured value is printed):

Q1  the saved ``mode_power``, ``confinement``, ``field_overlap`` and ``coupling_efficiency``
    are byte-identical to direct ``galerkin.mode_overlap`` calls on the saved mesh, edges
    and fields (the recipe of ``simcase.mode_postprocessing``), for scalar and vector results;
Q2  the saved key set is the former one plus exactly the new keys, PML results gain none
    (the other mode test modules keep passing unchanged);
Q3  a 220 nm SOI slab (materials n = 3.48 / 1.444, as the galerkin mode_overlap tests):
    the film confinement against the quad integral of ``refsol.slab.field_te`` converges
    at order >= 1.8 over mesh sizes 0.04, 0.02, 0.01 um with the finest error <= 1e-3,
    scalar (plain |phi|^2) and vector (Re eps_r |E|^2 weighting);
Q4  the Gaussian coupling (waist 0.22 um at the film centre) of that slab equals the
    separable 2D quad reference (the A5 setup of tests/galerkin/test_mode_overlap.py
    times the x factor of the strip) within 1e-3;
Q5  confinement rows sum to 1 +- 1e-12; the overlap diagonal is the mass norm (scalar:
    exactly ``mode_power``; vector: ``vector_field_overlap`` of the mode with itself, and
    dividing the mode by sqrt(Re mode_power) gives Re vector_power = 1 +- 1e-12); for the
    TE slab P / <E, E> = n_eff / (2 Z0) within 1e-3, the unit statement of ``mode_power``;
Q6  ``results.mode_overlap`` schema refusals.
"""
import json
from pathlib import Path

import numpy as np
import pytest
import refsol
from scipy.constants import c as C_LIGHT, mu_0 as MU_0
from scipy.integrate import quad

from galerkin import EdgeSpace, Mesh
from galerkin.mode_overlap import (confinement_factor, coupling_efficiency, interpolate_vector_field,
                                   overlap_matrix, scalar_confinement_factor, scalar_coupling_efficiency,
                                   scalar_overlap, scalar_power, vector_field_overlap, vector_power)
from simcase import Document, DocumentError
from simcase.runner import build_mesh, micrometre_document, run

ROOT = Path(__file__).resolve().parents[2]
N_FILM, N_CLAD, THICKNESS, WAVELENGTH = 3.48, 1.444, 0.22, 1.55
PAD, HALF_WIDTH = 1.1, 0.05
SIZES = (0.04, 0.02, 0.01)
WAIST, CENTER = THICKNESS, (0.0, THICKNESS / 2)
NEW_KEYS = {"mode_power", "confinement", "field_overlap"}
COMMON_KEYS = {"nodes", "triangles", "regions", "region_names", "values", "neff", "field_layout",
               "mesh_length_unit", "length_unit_to_m", "study_parameter"}
VECTOR_KEYS = {"field_representation", "edges", "vector_transverse", "vector_longitudinal", "vector_electric"}


def slab_document(formulation, size, *, unit="um", gaussian=True, lossy=False, modes=1):
    """The SOI slab along y in a thin strip; lengths in ``unit`` (um or nm)."""
    f = 1000.0 if unit == "nm" else 1.0
    d = {"openphysics": "0.2", "name": f"slab {formulation}", "units": {"length": unit},
         "geometry": {"domain": {"xmin": -HALF_WIDTH * f, "xmax": HALF_WIDTH * f, "ymin": -PAD * f,
                                 "ymax": (THICKNESS + PAD) * f},
                      "background": {"material": "clad"},
                      "shapes": [{"name": "film", "type": "rect", "x": -HALF_WIDTH * f, "y": 0.0,
                                  "w": 2 * HALF_WIDTH * f, "h": THICKNESS * f, "material": "film"}]},
         "materials": {"film": {"n": N_FILM, **({"k": 1e-3} if lossy else {})}, "clad": {"n": N_CLAD}},
         "physics": {"em1": {"type": "em.modes2d", "formulation": formulation, "wavelength": WAVELENGTH * f,
                             "num_modes": modes,
                             "boundary": {"left": "pec" if formulation == "vector" else "pmc",
                                          "right": "pec" if formulation == "vector" else "pmc",
                                          "top": "pec", "bottom": "pec"}}},
         "mesh": {"size": size * f}, "study": {"type": "single"},
         "results": {"plots": False}}
    if formulation == "vector":
        d["physics"]["em1"]["n_cladding"] = N_CLAD
    if gaussian:
        d["results"]["mode_overlap"] = {"gaussian": {"waist": WAIST * f, "center": [CENTER[0] * f, CENTER[1] * f]}}
    return d


@pytest.fixture(scope="module")
def reference():
    """quad integrals of the exact TE0 profile, never through the module under test."""
    n_eff = refsol.slab.modes(N_FILM, N_CLAD, N_CLAD, THICKNESS, WAVELENGTH, "TE")[0]

    def profile(y):
        return refsol.slab.field_te(y - THICKNESS / 2, n_eff, N_FILM, N_CLAD, N_CLAD, THICKNESS, WAVELENGTH)
    pieces = [(-PAD, 0.0, N_CLAD ** 2), (0.0, THICKNESS, N_FILM ** 2), (THICKNESS, THICKNESS + PAD, N_CLAD ** 2)]
    energy = [quad(lambda y: profile(y) ** 2, a, b)[0] for a, b, _ in pieces]
    norm2 = sum(energy)
    gamma = energy[1] / norm2
    gamma_eps = energy[1] * pieces[1][2] / sum(e * eps for e, (_, _, eps) in zip(energy, pieces))

    def gy(y):
        return np.exp(-(y - CENTER[1]) ** 2 / WAIST ** 2)

    def gx(x):
        return np.exp(-(x - CENTER[0]) ** 2 / WAIST ** 2)
    overlap = quad(lambda y: profile(y) * gy(y), -PAD, THICKNESS + PAD, points=[0.0, THICKNESS], limit=200)[0]
    eta_1d = overlap ** 2 / (norm2 * quad(lambda y: gy(y) ** 2, -PAD, THICKNESS + PAD)[0])
    # the strip adds a separable x factor: (int g_x)^2 / (width int g_x^2)
    eta_2d = eta_1d * quad(gx, -HALF_WIDTH, HALF_WIDTH)[0] ** 2 / (
        2 * HALF_WIDTH * quad(lambda x: gx(x) ** 2, -HALF_WIDTH, HALF_WIDTH)[0])
    print(f"reference n_eff {n_eff:.9f}, Gamma_film {gamma:.9f} (eps-weighted {gamma_eps:.9f}), "
          f"eta_gauss 1D {eta_1d:.9f}, 2D {eta_2d:.9f}")
    return {"n_eff": n_eff, "gamma": gamma, "gamma_eps": gamma_eps, "eta": eta_2d}


def _orders(errors):
    return [float(np.log2(errors[i] / errors[i + 1])) for i in range(len(errors) - 1)]


@pytest.fixture(scope="module", params=["scalar", "vector"])
def study(request, reference, tmp_path_factory):
    """Three meshes per formulation: results, saved archives and the reference errors."""
    formulation = request.param
    rows = []
    for size in SIZES:
        doc = Document.from_dict(slab_document(formulation, size))
        result = run(doc, verbose=False)
        out = result.save(tmp_path_factory.mktemp(f"{formulation}_{size}"))
        with np.load(out / "fields.npz", allow_pickle=False) as archive:
            saved = {key: archive[key] for key in archive.files}
        pp = result.postprocessing
        film = result.region_names.index("film")
        gamma_ref = reference["gamma_eps"] if formulation == "vector" else reference["gamma"]
        rows.append({"size": size, "doc": doc, "result": result, "saved": saved, "out": out,
                     "gamma_err": abs(pp["confinement"][0, 0, film] - gamma_ref),
                     "eta_err": abs(pp["coupling_efficiency"][0, 0] - reference["eta"]),
                     "neff_rel": abs(result.neff[0, 0] - reference["n_eff"]) / reference["n_eff"]})
        print(f"{formulation} slab h={size}: {len(result.mesh_triangles)} triangles, n_eff rel err "
              f"{rows[-1]['neff_rel']:.3e}, |Gamma - ref| {rows[-1]['gamma_err']:.3e}, "
              f"|eta - ref| {rows[-1]['eta_err']:.3e}, mode_power {pp['mode_power'][0, 0]}")
    return formulation, rows


# -- Q1 -----------------------------------------------------------------------------

def test_q1_saved_values_are_byte_identical_to_galerkin_calls(study):
    formulation, rows = study
    for row in rows:
        saved, doc = row["saved"], row["doc"]
        mesh = Mesh(saved["nodes"], saved["triangles"], {})
        regions, names = saved["regions"], list(saved["region_names"])
        masks = [regions == r for r in range(len(names))]
        wavelength = float(doc.sole_physics()[1]["wavelength"])
        gauss = doc["results"]["mode_overlap"]["gaussian"]
        w0, (cx, cy) = gauss["waist"], gauss["center"]

        def g(x, y):
            return np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / w0 ** 2)
        if formulation == "scalar":
            phi = saved["fields"][0].T
            power = np.array([scalar_power(mesh, p) for p in phi])
            conf = np.array([[scalar_confinement_factor(mesh, p, m) for m in masks] for p in phi])
            overlap = np.array([[scalar_overlap(mesh, a, b) for b in phi] for a in phi])
            eta = np.array([scalar_coupling_efficiency(mesh, p, g(mesh.nodes[:, 0], mesh.nodes[:, 1])) for p in phi])
        else:
            space = EdgeSpace(mesh)
            assert np.array_equal(space.edges, saved["edges"])
            et, ez = saved["vector_transverse"][0].T, -1j * saved["vector_longitudinal"][0].T
            k0 = 2 * np.pi / wavelength
            eps = build_mesh(doc).eps_per_triangle(wavelength)
            power = np.array([vector_power(space, et[m], ez[m], saved["neff"][0, m], k0, 1.0) for m in range(len(et))])
            conf = np.array([[confinement_factor(space, et[m], ez[m], eps.real, mask) for mask in masks]
                             for m in range(len(et))])
            overlap = overlap_matrix(space, et, ez, "field")
            et_in, ez_in = interpolate_vector_field(space, lambda x, y: np.stack([g(x, y), np.zeros_like(x)], axis=-1))
            assert ez_in is None
            eta = np.array([coupling_efficiency(space, et[m], ez[m], et_in) for m in range(len(et))])
        for key, direct in (("mode_power", power), ("confinement", conf), ("field_overlap", overlap),
                            ("coupling_efficiency", eta)):
            assert saved[key][0].dtype == direct.dtype, key
            assert saved[key][0].tobytes() == direct.tobytes(), key
            assert np.array_equal(row["result"].postprocessing[key][0], direct), key


# -- Q2 -----------------------------------------------------------------------------

def test_q2_saved_keys_gain_exactly_the_new_ones(study):
    formulation, rows = study
    saved = rows[0]["saved"]
    former = COMMON_KEYS | (VECTOR_KEYS if formulation == "vector" else {"fields"})
    assert set(saved) == former | NEW_KEYS | {"coupling_efficiency"}
    summary = json.loads((rows[0]["out"] / "summary.json").read_text(encoding="utf-8"))
    block = summary["mode_postprocessing"]
    assert set(block) == NEW_KEYS | {"coupling_efficiency", "recipe"}
    for key in NEW_KEYS | {"coupling_efficiency"}:
        assert "unit" in block[key] and "description" in block[key], key
    assert block["confinement"]["regions"] == list(saved["region_names"])
    assert block["coupling_efficiency"]["gaussian"]["waist"] == WAIST
    if formulation == "vector":
        assert block["mode_power"]["unit"] == "W for amplitudes in V/um (x length_unit_to_m^2 for V/m)"
        assert np.array_equal(block["mode_power"]["imag"], saved["mode_power"].imag)
    else:
        assert block["mode_power"]["unit"] == "um^2" and "imag" not in block["mode_power"]
    assert summary["field_layout"] == str(saved["field_layout"]) == "em-modes2d-p1-node-centroid-v1"
    assert summary["normalization"] == "max_centroid_magnitude" if formulation == "vector" else "normalization" not in summary


def test_q2_no_gaussian_means_no_coupling_key(tmp_path):
    result = run(Document.from_dict(slab_document("scalar", 0.04, gaussian=False)), verbose=False)
    assert set(result.postprocessing) == NEW_KEYS
    result.save(tmp_path)
    with np.load(tmp_path / "fields.npz", allow_pickle=False) as archive:
        assert set(archive.files) == COMMON_KEYS | {"fields"} | NEW_KEYS
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert "coupling_efficiency" not in summary["mode_postprocessing"]


def test_q2_pml_results_gain_no_keys(tmp_path):
    d = json.loads((ROOT / "examples/simcase/pml_leaky_slab.json").read_text(encoding="utf-8"))
    d["results"] = {"plots": False, "mode_overlap": {"gaussian": {"waist": 0.22, "center": [0.0, 0.11]}}}
    d["mesh"]["size"] = 0.1
    result = run(Document.from_dict(d), verbose=False)
    assert result.postprocessing is None and result.open_boundary is not None
    result.save(tmp_path)
    with np.load(tmp_path / "fields.npz", allow_pickle=False) as archive:
        assert not (set(archive.files) & (NEW_KEYS | {"coupling_efficiency"}))
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert "mode_postprocessing" not in summary


# -- Q3, Q4 --------------------------------------------------------------------------

def test_q3_film_confinement_converges_to_the_quad_integral(study):
    formulation, rows = study
    errors = [r["gamma_err"] for r in rows]
    orders = _orders(errors)
    # measured scalar 3.11e-3, 7.36e-4, 1.92e-4 (orders 2.08, 1.93);
    # vector 6.16e-4, 1.51e-4, 3.81e-5 (orders 2.02, 1.99)
    print(f"Q3 {formulation} |Gamma_film - ref| {errors}, orders {orders}")
    assert orders[-1] >= 1.8, (errors, orders)
    assert errors[-1] <= 1e-3, errors


def test_q4_gaussian_coupling_matches_the_quad_reference(study):
    formulation, rows = study
    errors = [r["eta_err"] for r in rows]
    # measured scalar 5.05e-4, 1.30e-4, 3.38e-5; vector 8.52e-5, 3.01e-5, 8.65e-6
    print(f"Q4 {formulation} |eta_gauss - ref| {errors}, orders {_orders(errors)}")
    assert errors[-1] <= 1e-3, errors


# -- Q5 -----------------------------------------------------------------------------

def test_q5_confinement_rows_sum_to_one_and_overlap_diagonal_is_the_mass_norm(study):
    formulation, rows = study
    for row in rows:
        pp, saved = row["result"].postprocessing, row["saved"]
        sums = pp["confinement"].sum(axis=-1)
        print(f"Q5 {formulation} h={row['size']}: confinement row sums - 1 = {sums - 1.0}")
        assert np.all(np.abs(sums - 1.0) <= 1e-12), sums
        diagonal = np.einsum("pmm->pm", pp["field_overlap"])
        assert np.all(diagonal.imag == 0.0)
        if formulation == "scalar":
            assert pp["mode_power"].dtype == float
            assert np.array_equal(diagonal.real, pp["mode_power"])
            continue
        mesh = Mesh(saved["nodes"], saved["triangles"], {})
        space = EdgeSpace(mesh)
        et, ez = saved["vector_transverse"][0, :, 0], -1j * saved["vector_longitudinal"][0, :, 0]
        assert diagonal[0, 0] == vector_field_overlap(space, et, ez, et, ez)
        k0, n_eff, p = 2 * np.pi / WAVELENGTH, saved["neff"][0, 0], pp["mode_power"][0, 0]
        assert p.real > 0 and abs(p.imag) <= 1e-12 * p.real, p
        scale = np.sqrt(p.real)
        unit = vector_power(space, et / scale, ez / scale, n_eff, k0, 1.0)
        print(f"Q5 vector h={row['size']}: Re P after dividing by sqrt(Re P) = {unit.real!r}")
        assert abs(unit.real - 1.0) <= 1e-12, unit
        # TE slab: E_z ~ 0, so P = beta/(2 omega mu0) int |E_t|^2 = n_eff/(2 Z0) <E, E> (Z0 = c mu0, ohm)
        ratio = p.real / diagonal[0, 0].real
        expected = n_eff.real / (2 * C_LIGHT * MU_0)
        print(f"Q5 vector h={row['size']}: P/<E,E> = {ratio:.6e} S, n_eff/(2 Z0) = {expected:.6e}")
        assert abs(ratio / expected - 1.0) <= 1e-3, (ratio, expected)


def test_q5_lossy_vector_power_is_complex_and_scalar_power_real(tmp_path):
    result = run(Document.from_dict(slab_document("vector", 0.04, lossy=True)), verbose=False)
    assert np.iscomplexobj(result.neff) and result.neff[0, 0].imag < 0
    p = result.postprocessing["mode_power"][0, 0]
    print(f"lossy vector slab (k = 1e-3): n_eff {result.neff[0, 0]}, mode_power {p}")
    assert p.dtype == complex and p.real > 0 and p.imag != 0.0
    result.save(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["mode_postprocessing"]["mode_power"]["imag"][0][0] == p.imag
    scalar = run(Document.from_dict(slab_document("scalar", 0.04, lossy=True)), verbose=False)
    assert np.iscomplexobj(scalar.fields[0])
    assert scalar.postprocessing["mode_power"].dtype == float
    assert scalar.postprocessing["field_overlap"].dtype == complex


def test_unit_statement_holds_for_a_nanometre_document():
    """The same slab in nm: dimensionless values equal, powers and overlaps scale with the unit."""
    um = run(Document.from_dict(slab_document("vector", 0.04)), verbose=False).postprocessing
    nm = run(Document.from_dict(slab_document("vector", 0.04, unit="nm")), verbose=False).postprocessing
    assert np.allclose(nm["confinement"], um["confinement"], rtol=0, atol=1e-9)
    assert np.allclose(nm["coupling_efficiency"], um["coupling_efficiency"], rtol=0, atol=1e-9)
    # amplitudes in V/nm are 1e3 V/um: W for V/nm = 1e6 W for V/um; (nm)^2 = 1e6 (um)^2
    assert np.allclose(nm["mode_power"], 1e6 * um["mode_power"], rtol=1e-9)
    assert np.allclose(nm["field_overlap"], 1e6 * um["field_overlap"], rtol=1e-9)
    canonical = micrometre_document(Document.from_dict(slab_document("vector", 0.04, unit="nm")))
    assert canonical["results"]["mode_overlap"]["gaussian"] == {"waist": WAIST, "center": list(CENTER)}


def test_two_mode_results_have_a_hermitian_overlap_matrix():
    result = run(Document.from_dict(slab_document("scalar", 0.04, modes=2)), verbose=False)
    pp = result.postprocessing
    assert pp["field_overlap"].shape == (1, 2, 2) and pp["confinement"].shape == (1, 2, 2)
    o = pp["field_overlap"][0]
    assert np.allclose(o, o.conj().T)
    assert abs(o[0, 1]) <= 1e-8 * np.sqrt(o[0, 0].real * o[1, 1].real)   # distinct scalar modes are mass-orthogonal


# -- Q6 -----------------------------------------------------------------------------

@pytest.mark.parametrize("spec, message", [
    ({"gaussian": {"waist": 0.2, "center": [0.0, 0.1]}, "extra": 1}, "unknown key"),
    ({"gaussian": {"waist": 0.2, "center": [0.0, 0.1], "power": 1}}, "unknown key"),
    ({"gaussian": {"waist": 0.2}}, "missing"),
    ({"gaussian": {"waist": 0.0, "center": [0.0, 0.1]}}, "positive finite"),
    ({"gaussian": {"waist": "0.2", "center": [0.0, 0.1]}}, "positive finite"),
    ({"gaussian": {"waist": True, "center": [0.0, 0.1]}}, "positive finite"),
    ({"gaussian": {"waist": 0.2, "center": [0.0]}}, r"\[x, y\]"),
    ({"gaussian": {"waist": 0.2, "center": [0.0, float("nan")]}}, r"\[x, y\]"),
    ({"gaussian": {"waist": 0.2, "center": [0.0, 5.0]}}, "outside the geometry window"),
    ({"gaussian": {"waist": 0.2, "center": [-0.0501, 0.1]}}, "outside the geometry window"),
    ({"gaussian": [0.2, 0.0, 0.1]}, "must be an object"),
    ({"lorentzian": {"waist": 0.2}}, "unknown key"),
    ({}, "needs 'gaussian'"),
    ([], "must be an object"),
])
def test_q6_schema_refusals(spec, message):
    d = slab_document("scalar", 0.04, gaussian=False)
    d["results"]["mode_overlap"] = spec
    with pytest.raises(DocumentError, match=message):
        Document.from_dict(d)


def test_q6_window_edges_are_inside():
    d = slab_document("scalar", 0.04, gaussian=False)
    d["results"]["mode_overlap"] = {"gaussian": {"waist": 0.2, "center": [HALF_WIDTH, -PAD]}}
    Document.from_dict(d)
