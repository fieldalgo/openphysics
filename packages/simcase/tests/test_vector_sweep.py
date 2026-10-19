# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Tracked document sweeps against independent slab dispersion derivatives."""

import copy
import json

import numpy as np
import pytest
from scipy.sparse.linalg import ArpackNoConvergence

from galerkin import EdgeSpace, Mesh, eval_edge_field
from refsol import slab
from simcase import Document, DocumentError, ModeTrackingError, examples, run
from simcase.cli import main
import simcase.runner as runner


def sweep_data(h=0.012, values=(1.54, 1.55, 1.56), dispersive=False):
    d = copy.deepcopy(examples.VECTOR_SLAB_SWEEP)
    d["geometry"]["shapes"][0]["mesh_size"] = h
    d["mesh"]["size"] = 5 * h
    d["mesh"]["grading"].update(near=h, far=5 * h)
    d["study"]["values"] = list(values)
    if dispersive:
        d["materials"]["film"] = {"sellmeier": {"A": 1.0, "B": [11.0], "C": [0.02]}}
    return d


def analytic_te(wavelength, dispersive=False, mode=0):
    """Implicit derivative of the symmetric TE dispersion equation, not FD.

    F = (2*pi*d/lambda)*p - 2*atan(q/p) - mode*pi = 0,
    p=sqrt(nf**2-neff**2), q=sqrt(neff**2-nc**2).
    The optional film Sellmeier derivative is evaluated independently of physmat.
    """
    nf, dnf, nc, thickness = 3.48, 0.0, 1.444, 0.22
    if dispersive:
        nf = np.sqrt(1 + 11 * wavelength**2 / (wavelength**2 - 0.02))
        dnf = -11 * 0.02 * wavelength / (nf * (wavelength**2 - 0.02)**2)
    n = slab.modes(nf, nc, nc, thickness, wavelength, "TE")[mode]
    p, q = np.sqrt(nf**2 - n**2), np.sqrt(n**2 - nc**2)
    kd = 2 * np.pi * thickness / wavelength
    partial_n = -kd * n / p - 2 * n / (p * q)
    partial_nf = kd * nf / p + 2 * nf * q / (p * (nf**2 - nc**2))
    total_wavelength = -kd * p / wavelength + partial_nf * dnf
    return n, n + wavelength * total_wavelength / partial_n


@pytest.mark.parametrize("dispersive", [False, True])
def test_vector_group_index_matches_implicit_dispersion_and_mesh_converges(dispersive):
    errors = []
    exact_n, exact_ng = analytic_te(1.55, dispersive)
    for h in (0.024, 0.012, 0.006):
        result = run(Document.from_dict(sweep_data(h=h, dispersive=dispersive)), False)
        assert abs(result.neff[1, 0] - exact_n) < 0.003
        errors.append(abs(result.group_index()[1, 0] - exact_ng))
        assert min(p["overlaps"][0] for p in result.mode_tracking["points"][1:]) > 0.99
    assert errors[-1] < 3e-4
    assert errors[2] < 0.4 * errors[1] < 0.16 * errors[0]


def test_vector_group_index_wavelength_spacing_converges_independently():
    exact = analytic_te(1.55)[1]
    errors = []
    for step in (0.3, 0.15, 0.075):
        result = run(Document.from_dict(sweep_data(h=0.006, values=(1.55-step, 1.55, 1.55+step))), False)
        errors.append(abs(result.group_index()[1, 0] - exact))
    assert errors[2] < 0.5 * errors[1] < 0.25 * errors[0]
    assert errors[-1] < 5e-4  # remaining mesh error is not a time-step error


def test_vector_nonuniform_increasing_and_decreasing_wavelengths_agree():
    values = [1.45, 1.49, 1.55, 1.62, 1.65]
    forward = run(Document.from_dict(sweep_data(values=values)), False)
    backward = run(Document.from_dict(sweep_data(values=values[::-1])), False)
    np.testing.assert_allclose(forward.neff, backward.neff[::-1], atol=1e-10, rtol=0)
    np.testing.assert_allclose(forward.group_index(), backward.group_index()[::-1], atol=1e-9, rtol=0)
    # This includes endpoint derivatives: first-order endpoints miss this bound.
    exact = [analytic_te(wl)[1] for wl in values]
    assert np.max(abs(forward.group_index()[:, 0] - exact)) < 1.2e-3


@pytest.mark.parametrize("unit,ratio", [("nm", 1e3), ("um", 1.0), ("m", 1e-6)])
def test_vector_sweep_units_saved_tracking_and_raw_fields(unit, ratio, tmp_path):
    d = sweep_data()
    d["units"]["length"] = unit
    d["geometry"]["domain"] = {k: v * ratio for k, v in d["geometry"]["domain"].items()}
    for shape in d["geometry"]["shapes"]:
        for key in ("x", "y", "w", "h", "mesh_size"):
            shape[key] *= ratio
    d["mesh"]["size"] *= ratio
    gr = d["mesh"]["grading"]
    gr["center"] = [v * ratio for v in gr["center"]]
    for key in ("near", "far", "distance"):
        gr[key] *= ratio
    d["physics"]["em1"]["wavelength"] *= ratio
    d["study"]["values"] = [v * ratio for v in d["study"]["values"]]
    result = run(Document.from_dict(d), False)
    assert abs(result.group_index()[1, 0] - analytic_te(1.55)[1]) < 1.2e-3
    output = result.save(tmp_path / unit)
    summary = json.loads((output / "summary.json").read_text())
    json.dumps(summary, allow_nan=False)
    assert summary["mode_tracking"] == result.mode_tracking
    assert summary["units"] == {"length": unit}
    assert (output / "results.png").stat().st_size > 0
    with np.load(output / "fields.npz", allow_pickle=False) as arrays:
        assert json.loads(str(arrays["mode_tracking_json"])) == result.mode_tracking
        np.testing.assert_array_equal(arrays["group_index"], result.group_index())
        space = EdgeSpace(Mesh(arrays["nodes"], arrays["triangles"], {}))
        for i in range(3):
            electric = arrays["vector_electric"][i]
            np.testing.assert_allclose(eval_edge_field(space, arrays["vector_transverse"][i, :, 0]),
                                       electric[:, 0, :2], atol=1e-12)
            ez = arrays["vector_longitudinal"][i]
            np.testing.assert_allclose(ez[space.mesh.triangles].mean(axis=1), electric[:, :, 2], atol=1e-12)
            np.testing.assert_allclose(np.linalg.norm(electric, axis=2).max(axis=0), 1.0)


def test_actual_slab_cutoff_fails_at_the_lost_point_and_cli_writes_no_result(tmp_path, capsys):
    d = sweep_data(values=[1.25, 1.35, 1.45])
    d["physics"]["em1"]["num_modes"] = 2
    assert [len(slab.modes(3.48, 1.444, 1.444, .22, wl)) for wl in d["study"]["values"]] == [2, 2, 1]
    model = tmp_path / "cutoff.json"
    Document.from_dict(d).save(model)
    output = tmp_path / "out"
    assert main(["run", str(model), "-q", "-o", str(output)]) == 1
    error = capsys.readouterr().err
    assert "wavelength 1.45 um" in error and "cutoff" in error and "Traceback" not in error
    assert not output.exists()


def test_fiber_rejects_unselected_degenerate_partner_even_for_one_requested_mode():
    d = copy.deepcopy(examples.VECTOR_FIBER)
    d["physics"]["em1"]["num_modes"] = 1
    d["study"] = dict(type="sweep", parameter="physics.em1.wavelength", values=[1.5, 1.55, 1.6])
    with pytest.raises(ModeTrackingError, match="wavelength 1.5 um.*mode 1.*near-degenerate"):
        run(Document.from_dict(d), False)


@pytest.mark.parametrize("failure", [RuntimeError("factor is exactly singular"),
    ArpackNoConvergence("no convergence", np.empty(0), None)])
def test_numerical_solve_failure_keeps_wavelength_context_without_partial_output(failure, monkeypatch, tmp_path, capsys):
    # A tracked sweep solves in micrometres and converts fields once, after tracking.
    original = runner._solve_in_micrometres

    def failing_point(model, physics):
        if physics["wavelength"] == 1.55:
            raise failure
        return original(model, physics)

    monkeypatch.setattr(runner, "_solve_in_micrometres", failing_point)
    model = tmp_path / "numerical-failure.json"
    Document.from_dict(sweep_data()).save(model)
    output = tmp_path / "out"
    assert main(["run", str(model), "-q", "-o", str(output)]) == 1
    error = capsys.readouterr().err
    assert "wavelength 1.55 um" in error and str(failure) in error
    assert "Traceback" not in error and not output.exists()


@pytest.mark.parametrize("values", [[1.5, 1.6], [1.5, 1.5, 1.6], [1.5, 1.7, 1.6],
    [1.5, 0, 1.6], [1.5, float("inf"), 1.6], [1.5, float("nan"), 1.6], [1.5, True, 1.6],
    [1.5, "1.55", 1.6], None])
def test_vector_sweep_rejects_invalid_wavelength_samples(values):
    d = sweep_data()
    d["study"]["values"] = values
    with pytest.raises(DocumentError):
        Document.from_dict(d)


@pytest.mark.parametrize("settings", [{"search_modes": 1}, {"search_modes": 2.5}, {"search_modes": True},
    {"min_overlap": 0}, {"min_overlap": 1.1}, {"min_margin": 0}, {"degeneracy_tolerance": -1},
    {"min_margin": float("nan")}, {"unknown": 1}, []])
def test_vector_sweep_validates_tracking_settings(settings):
    d = sweep_data()
    d["study"]["tracking"] = settings
    with pytest.raises(DocumentError, match="study.tracking"):
        Document.from_dict(d)


@pytest.mark.parametrize("parameter", ["physics.em1.num_modes", "physics.em1.n_cladding", "physics.em1.formulation"])
def test_vector_sweep_rejects_non_wavelength_parameters(parameter):
    d = sweep_data()
    d["study"]["parameter"] = parameter
    with pytest.raises(DocumentError, match="only the wavelength"):
        Document.from_dict(d)
