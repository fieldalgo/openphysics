# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""heat -> n(T) -> optical modes (D2, the first coupling): validation V1 to V3, pre-registered.

The geometry (``multiphysics_fixtures``): a 0.22 um core (n0 3.48, dn/dT 1.8e-4 1/K) across the
whole 1.0 um width of a 2.4 um tall window of cladding (n0 1.444, dn/dT 1.0e-5 1/K), T_ref 300 K,
lambda 1.55 um, scalar formulation, PMC left and right, PEC top and bottom. With PMC sides the
mode does not depend on x, so the 2D problem is the 1D TE slab between PEC walls.

V1  uniform temperature rise: the n_eff shift against the exact PEC-bounded slab dispersion.
V2a linear temperature: the heat solution against the closed-form series-layer profile.
V2b mesh convergence of the coupled n_eff against an independent 1D P1 FEM reference.
V3  controls: dn/dT = 0, and a uniform T_ref, give the uncoupled result bit for bit.
"""
import copy
import math

import numpy as np
import pytest
import scipy.sparse as sp
import scipy.sparse.linalg as sla
from scipy.optimize import brentq

from simcase import Document, multiphysics, run

from multiphysics_fixtures import CLAD, CORE, heated_slab, uncoupled_modes

LAMBDA = 1.55          # um
K0 = 2 * math.pi / LAMBDA
D, T_SUB, T_COVER = 0.22, 1.2, 0.98          # core thickness and the cladding up to each PEC wall, um
N_CORE, N_CLAD, DNDT_CORE, DNDT_CLAD = 3.48, 1.444, 1.8e-4, 1.0e-5
K_CORE, K_CLAD = 148.0, 1.38                  # W/(m K)


def coupled(tree):
    result = multiphysics.run(Document.from_dict(tree), verbose=False)
    return result, result.results["modes1"]


def neff(modes):
    return float(np.real(modes.effective_index[0, 0]))


# -- V1: a uniform temperature rise on the slab ------------------------------------------------

def exact_te0(n_core, n_clad):
    """TE0 of the three-layer slab between PEC walls: k d = atan(g coth(g t_s)/k) + atan(g coth(g t_c)/k),
    k = k0 sqrt(n_core^2 - n^2), g = k0 sqrt(n^2 - n_clad^2) (the field vanishes on each wall)."""
    def f(n):
        k = K0 * math.sqrt(n_core ** 2 - n ** 2)
        g = K0 * math.sqrt(n ** 2 - n_clad ** 2)
        return k * D - math.atan(g / math.tanh(g * T_SUB) / k) - math.atan(g / math.tanh(g * T_COVER) / k)
    return brentq(f, n_clad + 1e-12, n_core - 1e-12, xtol=1e-15)


def test_v1_the_exact_slab_reference():
    base = exact_te0(N_CORE, N_CLAD)
    hot = exact_te0(N_CORE + DNDT_CORE * 10, N_CLAD + DNDT_CLAD * 10)
    assert base == pytest.approx(2.851738985, abs=1e-9)
    assert hot == pytest.approx(2.853529512, abs=1e-9)
    assert hot - base == pytest.approx(1.79053e-3, rel=1e-5)


@pytest.mark.parametrize("h, neff_tol, shift_tol", [(0.04, 3e-3, 5e-3), (0.02, 1e-3, 2e-3)])
def test_v1_uniform_temperature_rise_shifts_neff_as_the_exact_slab(h, neff_tol, shift_tol):
    """310 K on top and bottom, insulated sides, no source: T = 310 K, dT = 10 K, every index
    raised by (dn/dT) dT. The shift is measured against the 300 K run (zero rise) of the same mesh."""
    base, hot = exact_te0(N_CORE, N_CLAD), exact_te0(N_CORE + DNDT_CORE * 10, N_CLAD + DNDT_CLAD * 10)
    result, modes = coupled(heated_slab(h, bottom="310 K", top="310 K"))
    heat = result.results["heat1"]
    assert np.array_equal(np.asarray(heat.temperature), np.full(len(heat.temperature), 310.0))
    _r, cold = coupled(heated_slab(h, bottom="300 K", top="300 K"))
    n_hot, n_cold = neff(modes), neff(cold)
    assert abs(n_cold - base) / base <= neff_tol
    assert abs(n_hot - hot) / hot <= neff_tol
    assert abs((n_hot - n_cold) - (hot - base)) / (hot - base) <= shift_tol


def _raised(record, dndt):
    out = dict(record)
    out["refractive_index"] = record["refractive_index"] + dndt * (310.0 - 300.0)
    return out


@pytest.mark.parametrize("formulation", ["scalar", "vector"])
def test_v1_consistency_the_coupled_index_equals_the_raised_index_written_in(formulation):
    """Not independent: the coupled run at T = 310 K against a single-physics run with the raised
    indices written in, |d n_eff| <= 1e-12 (the vector formulation as well, h = 0.04 um)."""
    _r, modes = coupled(heated_slab(0.04, formulation=formulation))
    direct = run(Document.from_dict(uncoupled_modes(0.04, formulation=formulation,
                                                    core=_raised(CORE, DNDT_CORE), clad=_raised(CLAD, DNDT_CLAD))),
                 verbose=False)
    assert np.max(np.abs(modes.effective_index - direct.effective_index)) <= 1e-12


# -- V2a: a closed-form temperature ---------------------------------------------------------------

LAYERS = [(-1.2, 0.0, K_CLAD), (0.0, 0.22, K_CORE), (0.22, 1.2, K_CLAD)]
T_BOTTOM, T_TOP = 300.0, 400.0


def exact_temperature(y):
    """The series-layer conduction profile: 300 K at y = -1.2 um, 400 K at y = 1.2 um, insulated
    sides, continuous flux q = dT / sum(t_i / k_i); piecewise linear in y."""
    y = np.asarray(y, dtype=float)
    q = (T_TOP - T_BOTTOM) / sum((b - a) / k for a, b, k in LAYERS)
    out, start = np.empty_like(y), T_BOTTOM
    for a, b, k in LAYERS:
        inside = (y >= a) & (y <= b)
        out[inside] = start + q * (y[inside] - a) / k
        start += q * (b - a) / k
    return out


def test_v2a_linear_temperature_matches_the_closed_form_at_every_node():
    result, _m = coupled(heated_slab(0.02, bottom="300 K", top="400 K"))
    heat = result.results["heat1"]
    y_um = np.asarray(heat.mesh.nodes)[:, 1] * 1e6
    assert np.max(np.abs(np.asarray(heat.temperature) - exact_temperature(y_um))) <= 1e-8


# -- V2b: mesh convergence of the coupled n_eff ----------------------------------------------------

def index_profile(y):
    core = (y > 0.0) & (y < 0.22)
    t = exact_temperature(y) - 300.0
    return np.where(core, N_CORE + DNDT_CORE * t, N_CLAD + DNDT_CLAD * t)


def reference_1d(n_elements):
    """TE0 of -E'' - k0^2 n(y)^2 E = -k0^2 n_eff^2 E on [-1.2, 1.2] um, E = 0 at both walls: P1
    elements on a uniform grid (every layer interface on a node), Gauss 8 point quadrature of n^2."""
    y = np.linspace(-1.2, 1.2, n_elements + 1)
    h = y[1] - y[0]
    g, w = np.polynomial.legendre.leggauss(8)
    a, b = y[:-1], y[1:]
    yq = (a + b)[:, None] / 2 + (b - a)[:, None] / 2 * g[None, :]
    wq = w[None, :] * (b - a)[:, None] / 2
    phi = [(b[:, None] - yq) / h, (yq - a[:, None]) / h]
    n2 = index_profile(yq) ** 2
    rows, cols, kv, mv, nv = [], [], [], [], []
    e = np.arange(n_elements)
    for i in range(2):
        for j in range(2):
            rows.append(e + i)
            cols.append(e + j)
            kv.append(np.full(n_elements, (1.0 if i == j else -1.0) / h))
            mv.append(np.sum(phi[i] * phi[j] * wq, axis=1))
            nv.append(np.sum(phi[i] * phi[j] * wq * n2, axis=1))
    shape = (n_elements + 1, n_elements + 1)
    r, c = np.concatenate(rows), np.concatenate(cols)
    K, M, Mn = (sp.csc_matrix((np.concatenate(v), (r, c)), shape=shape)[1:-1, 1:-1] for v in (kv, mv, nv))
    value = sla.eigsh(K0 ** 2 * Mn - K, k=1, M=M, sigma=K0 ** 2 * 3.0 ** 2, return_eigenvectors=False)[0]
    return math.sqrt(value) / K0


def test_v2b_coupled_neff_converges_to_the_1d_reference():
    n24, n48 = reference_1d(24000), reference_1d(48000)
    assert abs(n48 - n24) <= 1e-7                          # the reference is converged far below the checks
    reference = n48 + (n48 - n24) / 3
    assert reference == pytest.approx(2.86159710, abs=2e-8)
    n = {h: neff(coupled(heated_slab(h, bottom="300 K", top="400 K"))[1]) for h in (0.04, 0.02, 0.01)}
    order = math.log2(abs(n[0.04] - n[0.02]) / abs(n[0.02] - n[0.01]))
    assert 1.8 <= order <= 2.2
    estimate = abs(n[0.01] - n[0.02]) / 3                  # Richardson's error estimate of the finest mesh
    error = abs(n[0.01] - reference)
    assert 0.5 * estimate <= error <= 2.0 * estimate
    extrapolated = n[0.01] + (n[0.01] - n[0.02]) / 3
    assert abs(extrapolated - reference) / reference <= 1e-5
    assert error / reference <= 2.5e-4


# -- V3: controls, bit for bit --------------------------------------------------------------------

def _zero_dndt(record):
    out = dict(record)
    out["thermo_optic_coefficient"] = "0 1/K"
    return out


def assert_same_modes(coupled_modes, uncoupled):
    for name in ("effective_index", "node_coordinates", "triangles", "regions", "vacuum_wavelength"):
        a, b = getattr(coupled_modes, name), getattr(uncoupled, name)
        assert a.dtype == b.dtype and np.array_equal(a, b), name
    if uncoupled.vector_fields is None:
        assert len(coupled_modes.mode_fields) == len(uncoupled.mode_fields)
        for a, b in zip(coupled_modes.mode_fields, uncoupled.mode_fields):
            assert np.array_equal(a, b)
    else:
        for a, b in zip(coupled_modes.vector_fields, uncoupled.vector_fields):
            for part in ("edges", "transverse", "longitudinal", "electric"):
                assert np.array_equal(getattr(a, part), getattr(b, part)), part
    assert set(coupled_modes.postprocessing) == set(uncoupled.postprocessing)
    for key, value in uncoupled.postprocessing.items():
        assert np.array_equal(coupled_modes.postprocessing[key], value), key
    assert coupled_modes.summary()["effective_index"] == uncoupled.summary()["effective_index"]


@pytest.mark.parametrize("formulation", ["scalar", "vector"])
def test_v3a_zero_thermo_optic_coefficient_gives_the_uncoupled_result(formulation):
    tree = heated_slab(0.04, bottom="300 K", top="400 K", formulation=formulation,
                       core=_zero_dndt(CORE), clad=_zero_dndt(CLAD))
    _r, modes = coupled(tree)
    assert np.ptp(modes.coupled_inputs["temperature"]) > 50          # the heat really is not uniform
    uncoupled = run(Document.from_dict(uncoupled_modes(0.04, formulation=formulation)), verbose=False)
    assert_same_modes(modes, uncoupled)


def test_v3b_a_uniform_reference_temperature_without_power_gives_the_uncoupled_result():
    result, modes = coupled(heated_slab(0.04, bottom="300 K", top="300 K", sides="300 K"))
    heat = result.results["heat1"]
    assert np.array_equal(np.asarray(heat.temperature), np.full(len(heat.temperature), 300.0))
    assert np.array_equal(modes.coupled_inputs["temperature"], np.full(len(modes.triangles), 300.0))
    uncoupled = run(Document.from_dict(uncoupled_modes(0.04)), verbose=False)
    assert_same_modes(modes, uncoupled)


# -- the result ------------------------------------------------------------------------------------

def test_the_multiphysics_result_is_saved(tmp_path):
    import json
    result, modes = coupled(heated_slab(0.04, bottom="300 K", top="400 K"))
    out = result.save(tmp_path / "out")
    summary = json.loads((out / "summary.json").read_text())
    assert summary["result"] == "multiphysics-run-v1" and summary["format"] == multiphysics.ENVELOPE
    assert summary["solve_order"] == [["heat1"], ["modes1"]]
    assert summary["physics"]["heat1"]["folder"] == "heat1" and summary["physics"]["modes1"]["folder"] == "modes1"
    record = summary["couplings"]["heat_to_optics"]
    assert record["mesh_signature"] == "match" and record["max_abs_difference"] == {"value": 0.0, "unit": "K"}
    assert record["conservation_residual"] is None and summary["loops"] == []
    assert sorted(p.name for p in out.iterdir()) == ["heat1", "log.txt", "model.json", "modes1", "summary.json"]
    assert not (out / "heat1" / "model.json").exists() and not (out / "modes1" / "model.json").exists()
    with np.load(out / "modes1" / "fields.npz") as fields:
        assert fields["temperature"].shape == (len(modes.triangles),)
        assert fields["refractive_index"].shape == (1, len(modes.triangles))
        assert np.array_equal(fields["temperature"], modes.coupled_inputs["temperature"])
        meta = json.loads(str(fields["metadata_json"]))
        assert meta["field_units"]["temperature"] == "K" and meta["field_units"]["refractive_index"] == "1"
    with np.load(out / "heat1" / "fields.npz") as fields:
        nodes = np.asarray(result.results["heat1"].mesh.nodes)
        triangles = np.asarray(result.results["heat1"].mesh.triangles)
        mean = fields["temperature"][triangles].mean(axis=1)
        assert np.array_equal(mean, modes.coupled_inputs["temperature"])     # the P1 mean of the sent field
        assert nodes.shape[0] == fields["temperature"].shape[0]
    core = modes.regions == list(modes.region_names).index("core")
    expected = N_CORE + DNDT_CORE * (modes.coupled_inputs["temperature"][core] - 300.0)
    assert np.allclose(modes.coupled_inputs["refractive_index"][0][core], expected, rtol=0, atol=1e-15)
