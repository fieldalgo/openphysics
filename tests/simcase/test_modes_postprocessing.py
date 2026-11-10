# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Mode power, confinement, overlaps and Gaussian coupling saved with ``em.modes2d`` results.

Pre-registered gates (kept as written; every measured value is printed):

Q1  the saved ``unnormalized_mode_power`` (vector; ``unnormalized_mode_field_square_integral``
    for scalar results), ``confinement_factor``, ``unnormalized_field_overlap`` and
    ``coupling_efficiency`` are byte-identical to direct ``galerkin.mode_overlap`` calls in
    the kernel frame (the micrometre mesh, edges and fields of the solve), converted once:
    areas x 1e-12 and complex values conjugated (the recipe of ``simcase.mode_postprocessing``;
    format 0.3 re-registered the frame, units batch C8), for scalar and vector results;
Q2  the saved key set is the result's plus exactly the post-processing keys, PML results gain
    none (the other mode test modules keep passing unchanged);
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
from simcase.runner import _kernel_solve, build_mesh, run

ROOT = Path(__file__).resolve().parents[2]
N_FILM, N_CLAD, THICKNESS, WAVELENGTH = 3.48, 1.444, 0.22, 1.55
PAD, HALF_WIDTH = 1.1, 0.05
SIZES = (0.04, 0.02, 0.01)
WAIST, CENTER = THICKNESS, (0.0, THICKNESS / 2)
POST_KEYS = {"vector": {"unnormalized_mode_power", "confinement_factor", "unnormalized_field_overlap"},
             "scalar": {"unnormalized_mode_field_square_integral", "confinement_factor", "unnormalized_field_overlap"}}
COMMON_KEYS = {"node_coordinates", "triangles", "regions", "region_names", "vacuum_wavelength", "effective_index",
               "field_layout", "study_parameter", "metadata_json"}
VECTOR_KEYS = {"field_representation", "edges", "unnormalized_electric_field_line_integral",
               "unnormalized_electric_field_z", "unnormalized_electric_field"}


def slab_document(formulation, size, *, unit="um", gaussian=True, lossy=False, modes=1):
    """The SOI slab along y in a thin strip; shape numbers in ``unit`` (um or nm), every tagged
    length in um."""
    from decimal import Decimal
    f = Decimal(1000) if unit == "nm" else Decimal(1)

    def n(x):                       # the same length, written exactly in ``unit``
        return float(Decimal(repr(x)) * f)
    d = {"openphysics": "0.3", "name": f"slab {formulation}",
         "geometry": {"length_unit": unit, "depth": None,
                      "domain": {"xmin": n(-HALF_WIDTH), "xmax": n(HALF_WIDTH), "ymin": n(-PAD),
                                 "ymax": n(THICKNESS + PAD)},
                      "background": {"material": "clad"},
                      "shapes": [{"name": "film", "type": "rect", "x": n(-HALF_WIDTH), "y": 0.0,
                                  "w": n(2 * HALF_WIDTH), "h": n(THICKNESS), "material": "film"}]},
         "materials": {"film": {"refractive_index": {"n": N_FILM, "k": 1e-3} if lossy else N_FILM},
                       "clad": {"refractive_index": N_CLAD}},
         "physics": {"em1": {"type": "em.modes2d", "formulation": formulation, "vacuum_wavelength": "1.55 um",
                             "mode_count": modes,
                             "boundary": {"left": "pec" if formulation == "vector" else "pmc",
                                          "right": "pec" if formulation == "vector" else "pmc",
                                          "top": "pec", "bottom": "pec"}}},
         "mesh": {"element_size": f"{size!r} um"}, "study": {"type": "single"},
         "results": {"plots": False}}
    if formulation == "vector":
        d["physics"]["em1"]["effective_index_threshold"] = N_CLAD
    if gaussian:
        d["results"]["mode_overlap"] = {"gaussian": {"beam_waist_radius": "0.22 um", "position": ["0 um", "0.11 um"]}}
    return d


def kernel_point(doc):
    """(model, kernel answer) of the document's one solve, in the kernel frame (micrometres,
    exp(+i omega t)): what the post-processing calls receive."""
    model = build_mesh(doc)
    return model, _kernel_solve(model, model.kernel_doc.sole_physics()[1])


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
                     "gamma_err": abs(pp["confinement_factor"][0, 0, film] - gamma_ref),
                     "eta_err": abs(pp["coupling_efficiency"][0, 0] - reference["eta"]),
                     "neff_rel": abs(result.effective_index[0, 0] - reference["n_eff"]) / reference["n_eff"]})
        power = pp.get("unnormalized_mode_power", pp.get("unnormalized_mode_field_square_integral"))
        print(f"{formulation} slab h={size}: {len(result.triangles)} triangles, n_eff rel err "
              f"{rows[-1]['neff_rel']:.3e}, |Gamma - ref| {rows[-1]['gamma_err']:.3e}, "
              f"|eta - ref| {rows[-1]['eta_err']:.3e}, mode power {power[0, 0]}")
    return formulation, rows


# -- Q1 -----------------------------------------------------------------------------

def test_q1_saved_values_are_byte_identical_to_galerkin_calls(study):
    formulation, rows = study
    for row in rows:
        saved, doc = row["saved"], row["doc"]
        model, res = kernel_point(doc)
        tri = model.kernel_tri
        mesh = Mesh(tri.nodes, tri.triangles, {})
        assert (tri.nodes * 1e-6).tobytes() == saved["node_coordinates"].tobytes()
        regions, names = saved["regions"], list(saved["region_names"])
        masks = [regions == r for r in range(len(names))]
        wavelength = model.kernel_doc.sole_physics()[1]["wavelength"]       # micrometres
        gauss = model.kernel_doc["results"]["mode_overlap"]["gaussian"]
        w0, (cx, cy) = gauss["waist"], gauss["center"]

        def g(x, y):
            return np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / w0 ** 2)
        if formulation == "scalar":
            phi = res["fields"].T
            power = np.array([scalar_power(mesh, p) for p in phi])
            conf = np.array([[scalar_confinement_factor(mesh, p, m) for m in masks] for p in phi])
            overlap = np.array([[scalar_overlap(mesh, a, b) for b in phi] for a in phi])
            eta = np.array([scalar_coupling_efficiency(mesh, p, g(mesh.nodes[:, 0], mesh.nodes[:, 1])) for p in phi])
            converted = {"unnormalized_mode_field_square_integral": power * 1e-12}
        else:
            space = EdgeSpace(mesh)
            vf = res["vector_field"]
            assert np.array_equal(space.edges, saved["edges"])
            et, ez = vf.transverse.T, -1j * vf.longitudinal.T
            k0 = 2 * np.pi / wavelength
            eps = model.relative_permittivity(1.55e-6)
            power = np.array([vector_power(space, et[m], ez[m], res["neff"][m], k0, 1.0) for m in range(len(et))])
            conf = np.array([[confinement_factor(space, et[m], ez[m], eps.real, mask) for mask in masks]
                             for m in range(len(et))])
            overlap = overlap_matrix(space, et, ez, "field")
            et_in, ez_in = interpolate_vector_field(space, lambda x, y: np.stack([g(x, y), np.zeros_like(x)], axis=-1))
            assert ez_in is None
            eta = np.array([coupling_efficiency(space, et[m], ez[m], et_in) for m in range(len(et))])
            converted = {"unnormalized_mode_power": np.conj(power) * 1e-12}
        converted.update(confinement_factor=conf, unnormalized_field_overlap=np.conj(overlap) * 1e-12,
                         coupling_efficiency=eta)
        for key, direct in converted.items():
            assert saved[key][0].dtype == direct.dtype, key
            assert saved[key][0].tobytes() == direct.tobytes(), key
            assert np.array_equal(row["result"].postprocessing[key][0], direct), key


# -- Q2 -----------------------------------------------------------------------------

def test_q2_saved_keys_gain_exactly_the_new_ones(study):
    formulation, rows = study
    saved = rows[0]["saved"]
    former = COMMON_KEYS | (VECTOR_KEYS if formulation == "vector" else {"unnormalized_mode_field"})
    assert set(saved) == former | POST_KEYS[formulation] | {"coupling_efficiency"}
    summary = json.loads((rows[0]["out"] / "summary.json").read_text(encoding="utf-8"))
    block = summary["mode_postprocessing"]
    assert set(block) == POST_KEYS[formulation] | {"coupling_efficiency", "recipe"}
    for key in POST_KEYS[formulation] | {"coupling_efficiency"}:
        assert "unit" in block[key] and "description" in block[key], key
        assert summary["field_units"][key] == block[key]["unit"], key
    assert block["confinement_factor"]["regions"] == list(saved["region_names"])
    # the Gaussian the kernel used, in metres: its micrometre waist times 1e-6
    assert block["coupling_efficiency"]["gaussian"]["beam_waist_radius"] == {"value": WAIST * 1e-6, "unit": "m"}
    assert block["coupling_efficiency"]["gaussian"]["position"] == {"unit": "m",
                                                                     "values": [0.0, CENTER[1] * 1e-6]}
    if formulation == "vector":
        assert block["unnormalized_mode_power"]["unit"] == "W"
        assert np.array_equal(block["unnormalized_mode_power"]["im"], saved["unnormalized_mode_power"].imag)
    else:
        assert block["unnormalized_mode_field_square_integral"]["unit"] == "m^2"
        assert "im" not in block["unnormalized_mode_field_square_integral"]
    assert summary["field_layout"] == str(saved["field_layout"]) == "em-modes2d-p1-node-centroid-v2"
    assert summary["normalization"] == "max_centroid_magnitude" if formulation == "vector" else "normalization" not in summary


def test_q2_no_gaussian_means_no_coupling_key(tmp_path):
    result = run(Document.from_dict(slab_document("scalar", 0.04, gaussian=False)), verbose=False)
    assert set(result.postprocessing) == POST_KEYS["scalar"]
    result.save(tmp_path)
    with np.load(tmp_path / "fields.npz", allow_pickle=False) as archive:
        assert set(archive.files) == COMMON_KEYS | {"unnormalized_mode_field"} | POST_KEYS["scalar"]
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert "coupling_efficiency" not in summary["mode_postprocessing"]


def test_q2_pml_results_gain_no_keys(tmp_path):
    d = json.loads((ROOT / "examples/simcase/pml_leaky_slab.json").read_text(encoding="utf-8"))
    d["results"] = {"plots": False, "mode_overlap": {"gaussian": {"beam_waist_radius": "0.22 um",
                                                                  "position": ["0 um", "0.11 um"]}}}
    d["mesh"]["element_size"] = "0.1 um"
    result = run(Document.from_dict(d), verbose=False)
    assert result.postprocessing is None and result.open_boundary is not None
    result.save(tmp_path)
    with np.load(tmp_path / "fields.npz", allow_pickle=False) as archive:
        assert not (set(archive.files) & (POST_KEYS["vector"] | POST_KEYS["scalar"] | {"coupling_efficiency"}))
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
        sums = pp["confinement_factor"].sum(axis=-1)
        print(f"Q5 {formulation} h={row['size']}: confinement row sums - 1 = {sums - 1.0}")
        assert np.all(np.abs(sums - 1.0) <= 1e-12), sums
        diagonal = np.einsum("pmm->pm", pp["unnormalized_field_overlap"])
        assert np.all(diagonal.imag == 0.0)
        if formulation == "scalar":
            assert pp["unnormalized_mode_field_square_integral"].dtype == float
            assert np.array_equal(diagonal.real, pp["unnormalized_mode_field_square_integral"])
            continue
        # the mass norm and the power normalization in the kernel frame (micrometres)
        model, res = kernel_point(row["doc"])
        space = EdgeSpace(Mesh(model.kernel_tri.nodes, model.kernel_tri.triangles, {}))
        vf = res["vector_field"]
        et, ez = vf.transverse[:, 0], -1j * vf.longitudinal[:, 0]
        kernel_diagonal = vector_field_overlap(space, et, ez, et, ez)
        assert diagonal[0, 0] == np.conj(kernel_diagonal) * 1e-12
        k0, n_eff, p = 2 * np.pi / WAVELENGTH, res["neff"][0], np.conj(pp["unnormalized_mode_power"][0, 0])
        assert p.real > 0 and abs(p.imag) <= 1e-12 * p.real, p
        scale = np.sqrt(p.real / 1e-12)                 # the kernel's power, in W for V/um
        unit = vector_power(space, et / scale, ez / scale, n_eff, k0, 1.0)
        print(f"Q5 vector h={row['size']}: Re P after dividing by sqrt(Re P) = {unit.real!r}")
        assert abs(unit.real - 1.0) <= 1e-12, unit
        # TE slab: E_z ~ 0, so P = beta/(2 omega mu0) int |E_t|^2 = n_eff/(2 Z0) <E, E> (Z0 = c mu0, ohm):
        # both saved values are SI (W and m^2), so their ratio is in siemens
        ratio = p.real / diagonal[0, 0].real
        expected = n_eff.real / (2 * C_LIGHT * MU_0)
        print(f"Q5 vector h={row['size']}: P/<E,E> = {ratio:.6e} S, n_eff/(2 Z0) = {expected:.6e}")
        assert abs(ratio / expected - 1.0) <= 1e-3, (ratio, expected)


def test_q5_lossy_vector_power_is_complex_and_scalar_power_real(tmp_path):
    result = run(Document.from_dict(slab_document("vector", 0.04, lossy=True)), verbose=False)
    assert np.iscomplexobj(result.effective_index) and result.effective_index[0, 0].imag > 0
    p = result.postprocessing["unnormalized_mode_power"][0, 0]
    print(f"lossy vector slab (k = 1e-3): n_eff {result.effective_index[0, 0]}, mode power {p}")
    assert p.dtype == complex and p.real > 0 and p.imag != 0.0
    result.save(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["mode_postprocessing"]["unnormalized_mode_power"]["im"][0][0] == p.imag
    scalar = run(Document.from_dict(slab_document("scalar", 0.04, lossy=True)), verbose=False)
    assert np.iscomplexobj(scalar.mode_fields[0])
    assert scalar.postprocessing["unnormalized_mode_field_square_integral"].dtype == float
    assert scalar.postprocessing["unnormalized_field_overlap"].dtype == complex


def test_a_nanometre_document_gives_the_same_values():
    """The same slab with its shape numbers in nm: every saved value is the same SI double
    (check P2-5; format 0.2 saved powers and overlaps per document unit squared)."""
    um = run(Document.from_dict(slab_document("vector", 0.04)), verbose=False)
    nm = run(Document.from_dict(slab_document("vector", 0.04, unit="nm")), verbose=False)
    for key, value in um.postprocessing.items():
        assert nm.postprocessing[key].tobytes() == value.tobytes(), key
    assert nm.summary()["mode_postprocessing"] == um.summary()["mode_postprocessing"]


def test_two_mode_results_have_a_hermitian_overlap_matrix():
    result = run(Document.from_dict(slab_document("scalar", 0.04, modes=2)), verbose=False)
    pp = result.postprocessing
    assert pp["unnormalized_field_overlap"].shape == (1, 2, 2) and pp["confinement_factor"].shape == (1, 2, 2)
    o = pp["unnormalized_field_overlap"][0]
    assert np.allclose(o, o.conj().T, rtol=1e-5, atol=1e-8 * 1e-12)
    assert abs(o[0, 1]) <= 1e-8 * np.sqrt(o[0, 0].real * o[1, 1].real)   # distinct scalar modes are mass-orthogonal


# -- Q6 -----------------------------------------------------------------------------

GAUSSIAN = {"beam_waist_radius": "0.2 um", "position": ["0 um", "0.1 um"]}


@pytest.mark.parametrize("spec, code, path", [
    ({"gaussian": GAUSSIAN, "extra": 1}, "E-KEY-UNKNOWN", "results.mode_overlap.extra"),
    ({"gaussian": {**GAUSSIAN, "power": 1}}, "E-KEY-UNKNOWN", "results.mode_overlap.gaussian.power"),
    ({"gaussian": {"beam_waist_radius": "0.2 um"}}, "E-KEY-MISSING", "results.mode_overlap.gaussian.position"),
    ({"gaussian": {**GAUSSIAN, "beam_waist_radius": "0 um"}}, "E-DOMAIN",
     "results.mode_overlap.gaussian.beam_waist_radius"),
    ({"gaussian": {**GAUSSIAN, "beam_waist_radius": 0.2}}, "E-UNIT-MISSING",
     "results.mode_overlap.gaussian.beam_waist_radius"),
    ({"gaussian": {**GAUSSIAN, "beam_waist_radius": True}}, "E-VALUE-FORM",
     "results.mode_overlap.gaussian.beam_waist_radius"),
    ({"gaussian": {**GAUSSIAN, "waist": "0.2 um"}}, "E-KEY-UNKNOWN", "results.mode_overlap.gaussian.waist"),
    ({"gaussian": {**GAUSSIAN, "position": ["0 um"]}}, "E-VALUE-FORM", "results.mode_overlap.gaussian.position"),
    ({"gaussian": {**GAUSSIAN, "position": ["0 um", "5 um"]}}, "E-CONTRACT",
     "results.mode_overlap.gaussian.position"),
    ({"gaussian": {**GAUSSIAN, "position": ["-0.0501 um", "0.1 um"]}}, "E-CONTRACT",
     "results.mode_overlap.gaussian.position"),
    ({"gaussian": [0.2, 0.0, 0.1]}, "E-VALUE-FORM", "results.mode_overlap.gaussian"),
    ({"lorentzian": GAUSSIAN}, "E-KEY-UNKNOWN", "results.mode_overlap.lorentzian"),
    ({}, "E-KEY-MISSING", "results.mode_overlap.gaussian"),
    ([], "E-VALUE-FORM", "results.mode_overlap"),
])
def test_q6_schema_refusals(spec, code, path):
    d = slab_document("scalar", 0.04, gaussian=False)
    d["results"]["mode_overlap"] = spec
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(d)
    found = [(x.code, x.path) for x in caught.value.diagnostics] or [(caught.value.code, caught.value.path)]
    assert (code, path) in found, found


def test_q6_window_edges_are_inside():
    d = slab_document("scalar", 0.04, gaussian=False)
    d["results"]["mode_overlap"] = {"gaussian": {"beam_waist_radius": "0.2 um",
                                                 "position": [f"{HALF_WIDTH!r} um", f"{-PAD!r} um"]}}
    Document.from_dict(d)
