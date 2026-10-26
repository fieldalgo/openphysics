# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Complex dispersion oracles; no production eigenvalues used as references."""

import copy
import json

import numpy as np
import pytest
from scipy.optimize import root

from simcase import Document, examples, run
from simcase.physics_em_modes2d import vector_pencil_residuals
from galerkin import Mesh


def dispersion(wavelength=1.55, kappa=.01, pol="TE"):
    ef, ec = (3.48 - 1j*kappa)**2, 1.444**2
    k0, half = 2*np.pi/wavelength, .11

    def equation(v):
        n = v[0] + 1j*v[1]
        h, q = k0*np.sqrt(ef-n*n), k0*np.sqrt(n*n-ec)
        f = h*np.tan(h*half) - q*(ef/ec if pol == "TM" else 1)
        return [f.real, f.imag]

    ans = root(equation, [2.85 if pol == "TE" else 2.05, -.01], tol=1e-11)
    assert ans.success and np.linalg.norm(equation(ans.x)) < 1e-9
    return complex(*ans.x)


def document(formulation="vector", pol="TE", h=.012, kappa=.01):
    d = copy.deepcopy(examples.VECTOR_SLAB)
    d["materials"]["film"] = {"n": 3.48, "k": kappa}
    d["physics"]["em1"]["formulation"] = formulation
    d["physics"]["em1"]["num_modes"] = 1
    d["geometry"]["shapes"][0]["mesh_size"] = h
    d["mesh"]["size"] = 5*h
    d["mesh"]["grading"].update(near=h, far=5*h)
    if pol == "TM" or formulation == "scalar":
        d["physics"]["em1"]["boundary"].update(left="pmc", right="pmc")
    d["study"] = {"type": "single"}
    d["results"] = {"plots": False}
    return Document.from_dict(d)


@pytest.mark.parametrize("formulation,pol", [("scalar", "TE"), ("vector", "TE"), ("vector", "TM")])
def test_complex_slab_convergence_and_lossless_limit(formulation, pol):
    exact = dispersion(pol=pol)
    errors = []
    for h in (.024, .012, .006):
        result = run(document(formulation, pol, h), False)
        n = result.neff[0, 0]
        assert n.imag < 0
        errors.append(abs(n-exact))
    print(formulation, pol, exact, n, errors)
    assert errors[-1] < 2e-4
    assert errors[0] > errors[1] > errors[2]
    assert np.log2(errors[-2]/errors[-1]) > 1.7
    assert abs(n.imag/exact.imag-1) < 2e-3
    zero = run(document(formulation, pol, kappa=0), False)
    small = run(document(formulation, pol, kappa=1e-7), False)
    assert np.max(abs(small.neff.real-zero.neff)) < 1e-9
    assert small.neff[0, 0].imag < 0
    # Independent weak-loss coefficient, from the complex slab dispersion.
    expected = dispersion(kappa=1e-7, pol=pol).imag
    assert abs(small.neff[0, 0].imag/expected-1) < 2e-3


@pytest.mark.parametrize("formulation", ["scalar", "vector"])
def test_complex_output_units_fields_and_pencil(tmp_path, formulation):
    doc = document(formulation)
    result = run(doc, False)
    summary = result.summary()
    json.dumps(summary, allow_nan=False)
    assert np.array_equal(summary["neff_imag"], result.neff.imag)
    expected = -20/np.log(10)*(2*np.pi/(1.55e-6))*result.neff.imag/100
    np.testing.assert_allclose(result.propagation_loss_db_cm(), expected, rtol=1e-14)
    assert np.all(expected > 0)
    result.save(tmp_path)
    with np.load(tmp_path/"fields.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["neff"], result.neff)
        if formulation == "scalar":
            np.testing.assert_array_equal(saved["fields"], np.stack(result.fields))
            assert np.max(abs(saved["fields"].imag)) > 1e-6
        else:
            np.testing.assert_array_equal(saved["vector_electric"], result.vector_fields[0].electric[None])
    if formulation == "scalar":
        return
    from simcase import build_mesh
    model = build_mesh(doc)
    residual = vector_pencil_residuals(model.mesh, model.eps_per_triangle(1.55).conj(), 1.55,
                                      doc.sole_physics()[1]["boundary"], result.neff[0], result.vector_fields[0])
    assert residual.max() < 1e-10


@pytest.mark.parametrize("formulation", ["scalar", "vector"])
def test_complex_sweep_keeps_imaginary_derivative(formulation, tmp_path):
    d = document(formulation).data
    d["study"] = dict(type="sweep", parameter="physics.em1.wavelength", values=[1.54, 1.55, 1.56])
    result = run(Document.from_dict(d), False)
    oracle = np.array([dispersion(w) for w in result.values])
    np.testing.assert_allclose(result.neff[:, 0], oracle, atol=8e-4, rtol=0)
    expected = oracle - np.array(result.values)*np.gradient(oracle, result.values, edge_order=2)
    np.testing.assert_allclose(result.group_index()[:, 0], expected, atol=2e-3, rtol=0)
    assert np.any(result.group_index().imag != 0)
    json.dumps(result.summary(), allow_nan=False)
    result.save(tmp_path)
    with np.load(tmp_path / "fields.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["group_index"], result.group_index())
        assert json.loads(str(saved["mode_tracking_json"])) == result.mode_tracking


def test_metal_interface_spp_convergence():
    from galerkin import rectangle_mesh
    from simcase.physics_em_modes2d import solve
    metal, dielectric = -10-.5j, 1.
    expected = np.sqrt(metal*dielectric/(metal+dielectric))
    errors = []
    for count in (40, 80, 160):
        mesh = rectangle_mesh(.1, 2., 1, 2*count)
        t = mesh.nodes[:, 1]-1
        mesh.nodes[:, 1] = 6*np.sign(t)*np.expm1(5*abs(t))/np.expm1(5)
        eps = np.where(mesh.nodes[mesh.triangles, 1].mean(axis=1) < 0, metal, dielectric)
        boundary = dict(left="pmc", right="pmc", top="pec", bottom="pec")
        result = solve(mesh, eps, 1.55, boundary, 1, "vector", 1., n_target=expected.real)
        n = result["neff"][0]
        errors.append(abs(n-expected))
        assert vector_pencil_residuals(mesh, eps, 1.55, boundary, result["neff"], result["vector_field"]).max() < 1e-10
    print("SPP", expected, n, errors)
    assert errors[0] > errors[1] > errors[2]
    assert errors[-1] < 2e-4
    assert np.log2(errors[-2]/errors[-1]) > 1.7
    assert n.imag < 0


@pytest.mark.parametrize("formulation", ["scalar", "vector"])
def test_absorbing_units_are_equivalent(formulation):
    from test_length_canonical import _written_in
    doc = document(formulation)
    reference = run(doc, False)
    for symbol, scale in [("nm", "1000"), ("m", "1e-6")]:
        other = run(Document.from_dict(_written_in(doc.data, symbol, scale)), False)
        np.testing.assert_array_equal(other.neff, reference.neff)
        np.testing.assert_array_equal(other.propagation_loss_db_cm(), reference.propagation_loss_db_cm())


@pytest.mark.parametrize("pol", ["TE", "TM"])
def test_absorbing_slab_window_convergence(pol):
    values = []
    for pad in (1.5, 2.5):
        d = document(pol=pol).data
        d["geometry"]["domain"].update(ymin=-pad, ymax=.22+pad)
        values.append(run(Document.from_dict(d), False).neff[0, 0])
    assert abs(values[0]-values[1]) < 2e-5
    assert abs(values[0].imag-values[1].imag) < 2e-6


def test_real_spectrum_subspace_method_explicitly_refuses_loss():
    from simcase import ModeTrackingError
    d = document().data
    d["study"] = dict(type="sweep", parameter="physics.em1.wavelength", values=[1.54, 1.55, 1.56],
                      tracking=dict(method="electric-l2-subspace-v1", cluster_span_max=1e-5,
                                    external_gap_min=1e-3))
    with pytest.raises(ModeTrackingError, match="requires a real spectrum"):
        run(Document.from_dict(d), False)


@pytest.mark.parametrize("formulation", ["scalar", "vector"])
def test_uniform_pec_box_complex_cutoff_convergence(formulation):
    from galerkin import rectangle_mesh
    from simcase.physics_em_modes2d import solve
    eps, wavelength = 4.-.1j, 1.55
    cutoff = 1/2**2 + (1/1**2 if formulation == "scalar" else 0)
    expected = np.sqrt(eps-wavelength**2*cutoff/4)
    errors = []
    for count in (8, 16, 32):
        mesh = rectangle_mesh(2., 1., 2*count, count)
        result = solve(mesh, np.full(mesh.num_triangles, eps), wavelength,
                       dict(left="pec", right="pec", top="pec", bottom="pec"), 1,
                       formulation, 1.)
        errors.append(abs(result["neff"][0]-expected))
    print("uniform PEC", formulation, errors)
    assert errors[0] > errors[1] > errors[2]
    assert errors[-1] < 1e-3
    assert np.log2(errors[-2]/errors[-1]) > 1.7
