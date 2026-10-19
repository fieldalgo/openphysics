# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Self-checks of the slab-loaded and uniformly filled cavity references."""

import cmath
import math

import numpy as np
import pytest

from refsol import cavity, material_cavity as mc

LENGTHS = (1.0, 0.8, 0.6)


def test_vacuum_slab_reproduces_complete_cartesian_spectrum():
    ceiling = 500e6
    expected = cavity.rectangular_cavity_modes(LENGTHS, ceiling)
    modes = mc.slab_loaded_cavity_modes(LENGTHS, 0.3, ceiling, slab_permittivity=1.0)
    assert len(modes) == len(expected) == 15
    np.testing.assert_allclose([m.eigenvalue_m2.real for m in modes],
                               [m.eigenvalue_m2 for m in expected], rtol=1e-13)
    assert all(m.eigenvalue_m2.imag == 0 and m.quality_factor == math.inf for m in modes)
    # TE-to-z needs a positive z index; TM-to-z also exists at p = 0.
    te = sorted(m.indices for m in modes if m.family == "TE_z")
    assert (0, 1) in te and (1, 0) in te


def test_identical_lossy_regions_match_uniform_rescaling():
    eps, mu = 2.0 - 0.1j, 1.3 - 0.02j
    vacuum = cavity.rectangular_cavity_modes(LENGTHS, 400e6)
    modes = mc.slab_loaded_cavity_modes(
        LENGTHS, 0.25, 400e6 / math.sqrt(2 * 1.3) * 1.001, slab_permittivity=eps,
        slab_permeability=mu, background_permittivity=eps, background_permeability=mu)
    expected = sorted((mc.uniformly_filled_eigenvalue(m.eigenvalue_m2, eps, mu) for m in vacuum),
                      key=lambda v: v.real)
    assert len(modes) == len(expected)
    np.testing.assert_allclose([m.eigenvalue_m2 for m in modes], expected, rtol=1e-12)
    phase = cmath.phase(1 / cmath.sqrt(eps * mu))
    for mode in modes:
        assert mode.frequency_hz.imag > 0
        assert mode.quality_factor == pytest.approx(1 / (2 * math.tan(phase)), rel=1e-11)


def test_uniform_dielectric_quality_factor_closed_form():
    for tan_delta in (1e-4, 0.01, 0.3):
        eigenvalue = mc.uniformly_filled_eigenvalue(np.pi**2 * 2, 3.0 * (1 - 1j * tan_delta))
        q = mc.quality_factor(mc.complex_frequency_from_eigenvalue(eigenvalue))
        assert q == pytest.approx(mc.dielectric_loss_quality_factor(tan_delta), rel=1e-12)
    assert mc.dielectric_loss_quality_factor(1e-4) == pytest.approx(1e4, rel=1e-8)


def test_small_loss_matches_energy_filling_perturbation():
    """Q^-1 = tan_delta * p_e, with p_e = -(eps'/k0^2) d(k0^2)/d eps' (Hellmann-Feynman).

    The derivative uses independent lossless roots at eps' +/- h, so this checks
    the complex continuation against the real dispersion relation.
    """
    eps, tan_delta, h = 4.0, 1e-4, 1e-4
    lossy = mc.slab_loaded_cavity_modes(LENGTHS, 0.3, 300e6,
                                        slab_permittivity=eps * (1 - 1j * tan_delta))
    plus = mc.slab_loaded_cavity_modes(LENGTHS, 0.3, 300e6, slab_permittivity=eps + h)
    minus = mc.slab_loaded_cavity_modes(LENGTHS, 0.3, 300e6, slab_permittivity=eps - h)
    assert len(lossy) == len(plus) == len(minus) >= 6
    for mode, up, down in zip(lossy, plus, minus):
        assert (mode.family, mode.indices) == (up.family, up.indices) == (down.family, down.indices)
        derivative = (up.eigenvalue_m2.real - down.eigenvalue_m2.real) / (2 * h)
        filling = -eps * derivative / mode.lossless_eigenvalue_m2
        assert 0 < filling < 1
        assert 1 / mode.quality_factor == pytest.approx(tan_delta * filling, rel=2e-3)


def test_slab_raises_lowest_quality_factor_above_uniform_bound():
    tan_delta = 0.01
    modes = mc.slab_loaded_cavity_modes(LENGTHS, 0.3, 300e6,
                                        slab_permittivity=4 * (1 - 1j * tan_delta))
    bound = mc.dielectric_loss_quality_factor(tan_delta)
    assert all(m.quality_factor > bound and m.frequency_hz.imag > 0 for m in modes)


@pytest.mark.parametrize("kwargs", [
    {"slab_permittivity": 2 + 0.1j},                    # active under exp(+j omega t)
    {"slab_permittivity": -1.0},
    {"slab_permittivity": True},
    {"slab_permittivity": 2.0, "slab_permeability": float("nan")},
])
def test_invalid_materials(kwargs):
    with pytest.raises(ValueError):
        mc.slab_loaded_cavity_modes(LENGTHS, 0.3, 300e6, **kwargs)


def test_invalid_geometry():
    with pytest.raises(ValueError, match="smaller"):
        mc.slab_loaded_cavity_modes(LENGTHS, 0.6, 300e6, slab_permittivity=2.0)
    with pytest.raises(ValueError):
        mc.slab_loaded_cavity_modes((1, 1), 0.3, 300e6, slab_permittivity=2.0)
    with pytest.raises(ValueError):
        mc.uniformly_filled_eigenvalue(-1.0, 2.0)
