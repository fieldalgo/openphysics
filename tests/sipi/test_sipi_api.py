# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""sipi API behaviour: input checks, matrix properties, losses, defaults."""

import numpy as np
import pytest
from scipy.constants import c as SPEED_OF_LIGHT
from scipy.constants import epsilon_0, mu_0

from galerkin import rectangle_mesh
from sipi import CrossSection, Layer, Trace, capacitance_matrix, line_parameters

H = 0.2e-3


def microstrip(width=0.35e-3, thickness=0.0, tan_delta=0.0, **kw):
    return CrossSection([Layer("FR-4", H, eps_r=4.3, tan_delta=tan_delta), Layer("air", 10 * H)],
                        [Trace("sig", 0.0, width, H, thickness)], width=20 * H, **kw)


def test_default_mesh_is_within_one_percent_of_the_reference_cases():
    # Same references as V3/V5 in test_sipi_references.py, default mesh options.
    from test_sipi_references import hammerstad_jensen, stripline_z0
    p = CrossSection([Layer("substrate", 1e-3, 4.3), Layer("air", 20e-3)],
                     [Trace("s", 0.0, 1e-3, 1e-3)], width=40e-3).analyze()
    z, eps = hammerstad_jensen(1.0, 4.3)
    assert p.z0 == pytest.approx(z, rel=1e-2)
    assert p.eps_eff == pytest.approx(eps, rel=1e-2)
    b = 1e-3
    p = CrossSection([Layer("lo", b / 2, 4.0), Layer("hi", b / 2, 4.0)],
                     [Trace("s", 0.0, 0.5e-3, b / 2)], width=12 * b, top="ground").analyze()
    assert p.z0 == pytest.approx(stripline_z0(0.5e-3, b, 4.0), rel=1e-2)


def test_single_line_quantities_are_consistent():
    p = microstrip().analyze()
    assert p.names == ("sig",)
    assert 1.0 < p.eps_eff < 4.3
    assert p.z0 == pytest.approx(1.0 / (SPEED_OF_LIGHT * np.sqrt(p.C[0, 0] * p.C0[0, 0])), rel=1e-12)
    assert p.L[0, 0] == pytest.approx(mu_0 * epsilon_0 / p.C0[0, 0], rel=1e-12)
    assert p.phase_velocity == pytest.approx(SPEED_OF_LIGHT / np.sqrt(p.eps_eff), rel=1e-12)
    assert p.delay == pytest.approx(1.0 / p.phase_velocity, rel=1e-12)
    assert np.all(p.C_loss == 0.0)
    assert np.all(p.G(1e9) == 0.0)


def test_dielectric_loss_scales_with_frequency_and_filling():
    p = microstrip(tan_delta=0.02).analyze()
    assert p.G(2e9)[0, 0] == pytest.approx(2 * p.G(1e9)[0, 0], rel=1e-12)
    # Only the substrate is lossy, so the effective loss tangent lies between
    # 0 and 0.02, weighted by the share of the electric energy in the substrate.
    assert 0.0 < p.loss_tangent() < 0.02
    lossless = microstrip().analyze()
    assert p.C[0, 0] == pytest.approx(lossless.C[0, 0], rel=1e-3)


def test_trace_thickness_lowers_the_impedance():
    thin = microstrip().analyze()
    thick = microstrip(thickness=35e-6).analyze()
    assert thick.z0 < thin.z0
    assert thick.z0 == pytest.approx(thin.z0, rel=0.1)


def test_coupled_pair_matrices_and_modes():
    w, s = 0.2e-3, 0.2e-3
    cs = CrossSection([Layer("FR-4", H, 4.3), Layer("air", 10 * H)],
                      [Trace("p", -(w + s) / 2, w, H), Trace("n", (w + s) / 2, w, H)],
                      width=20 * H)
    p = cs.analyze()
    assert p.names == ("p", "n")
    for M in (p.C, p.C0, p.L):
        np.testing.assert_allclose(M, M.T, rtol=0, atol=1e-12 * abs(M).max())
    assert p.C[0, 1] < 0 < p.C[0, 0]            # Maxwell form
    assert p.L[0, 1] > 0
    eo = p.even_odd()
    assert eo["z_even"] > eo["z_odd"]
    assert eo["z_diff"] == 2 * eo["z_odd"] and eo["z_common"] == eo["z_even"] / 2
    # Microstrip odd mode has more field in air: faster, smaller eps_eff.
    assert eo["eps_eff_odd"] < eo["eps_eff_even"]
    eps_modes, vectors = p.modes()
    np.testing.assert_allclose(sorted(eps_modes), sorted([eo["eps_eff_odd"], eo["eps_eff_even"]]),
                               rtol=1e-2)
    assert abs(vectors[0, 0]) == pytest.approx(abs(vectors[1, 0]), rel=1e-2)
    with pytest.raises(ValueError, match="single signal conductor"):
        p.z0


def test_ground_trace_is_a_reference_conductor():
    w, g = 0.3e-3, 0.15e-3
    cs = CrossSection([Layer("FR-4", H, 4.3), Layer("air", 10 * H)],
                      [Trace("gl", -(w / 2 + g + 0.5e-3), 1e-3, H, ground=True),
                       Trace("sig", 0.0, w, H),
                       Trace("gr", w / 2 + g + 0.5e-3, 1e-3, H, ground=True)],
                      width=20 * H, bottom="open")
    p = cs.analyze()
    assert p.names == ("sig",)
    assert p.z0 > 0 and 1.0 < p.eps_eff < 4.3


@pytest.mark.parametrize("kwargs, message", [
    (dict(layers=[], traces=[Trace("s", 0, 1e-4, 1e-4)]), "at least one layer"),
    (dict(traces=[Trace("s", 0, 1e-4, H, ground=True)]), "signal trace"),
    (dict(traces=[Trace("s", 0, 1e-4, 0.0)]), "strictly between"),
    (dict(traces=[Trace("s", 0, 20 * H, H)]), "inside the side walls"),
    (dict(traces=[Trace("a", 0, 2e-4, H), Trace("b", 1e-4, 2e-4, H)]), "touch or overlap"),
    (dict(traces=[Trace("a", 0, 1e-4, H), Trace("a", 1e-3, 1e-4, H)]), "unique"),
    (dict(top="wall"), "top must be one of"),
    (dict(bottom="open"), "no reference conductor"),
])
def test_cross_section_rejects_bad_input(kwargs, message):
    args = dict(layers=[Layer("FR-4", H, 4.3), Layer("air", 10 * H)],
                traces=[Trace("s", 0.0, 1e-4, H)], width=20 * H)
    args.update(kwargs)
    with pytest.raises(ValueError, match=message):
        CrossSection(args.pop("layers"), args.pop("traces"), args.pop("width"), **args)


@pytest.mark.parametrize("kwargs, message", [
    (dict(name="x", thickness=0.0), "thickness must be > 0"),
    (dict(name="x", thickness=1e-3, eps_r=0.5), "eps_r must be >= 1"),
    (dict(name="x", thickness=1e-3, tan_delta=-0.1), "tan_delta"),
])
def test_layer_rejects_bad_input(kwargs, message):
    with pytest.raises(ValueError, match=message):
        Layer(**kwargs)


def test_trace_rejects_bad_input():
    with pytest.raises(ValueError, match="width must be > 0"):
        Trace("s", 0.0, 0.0, 1e-3)
    with pytest.raises(ValueError, match="thickness must be >= 0"):
        Trace("s", 0.0, 1e-3, 1e-3, thickness=-1e-6)


def test_capacitance_matrix_rejects_bad_input():
    mesh = rectangle_mesh(1.0, 1.0, 4, 4)
    left, right = mesh.boundary["left"], mesh.boundary["right"]
    with pytest.raises(ValueError, match="at least one signal"):
        capacitance_matrix(mesh, 1.0, {}, left)
    with pytest.raises(ValueError, match="must not touch"):
        capacitance_matrix(mesh, 1.0, {"a": right, "b": right}, left)
    with pytest.raises(ValueError, match="passive"):
        capacitance_matrix(mesh, 2.0 + 0.1j, {"a": right}, left)
    with pytest.raises(ValueError, match="one value per triangle"):
        capacitance_matrix(mesh, np.ones(3), {"a": right}, left)
    with pytest.raises(ValueError, match="tan_delta"):
        line_parameters(mesh, 1.0, {"a": right}, left, tan_delta=-1.0)
