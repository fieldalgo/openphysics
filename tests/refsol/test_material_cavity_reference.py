# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Self-checks of the slab-loaded and uniformly filled cavity references.

The public functions follow exp(-i omega t) since the galerkin step (L3 commit 12): a passive
material is ``eps' + i eps''`` and a decaying resonance has ``Im(resonant_frequency) < 0``.
"""

import cmath
import math

import numpy as np
import pytest

from refsol import cavity, material_cavity as mc

LENGTHS = (1.0, 0.8, 0.6)


def test_vacuum_slab_reproduces_complete_cartesian_spectrum():
    ceiling = 500e6
    expected = cavity.rectangular_cavity_modes(box_size=LENGTHS, frequency_limit=ceiling)
    modes = mc.slab_loaded_cavity_modes(box_size=LENGTHS, thickness=0.3, frequency_limit=ceiling,
                                        relative_permittivity=(1.0, 1.0))
    assert len(modes) == len(expected) == 15
    np.testing.assert_allclose([m.wavenumber_squared.real for m in modes],
                               [m.wavenumber_squared for m in expected], rtol=1e-13)
    assert all(m.wavenumber_squared.imag == 0 and m.quality_factor == math.inf for m in modes)
    # TE-to-z needs a positive z index; TM-to-z also exists at p = 0.
    te = sorted(m.indices for m in modes if m.family == "TE_z")
    assert (0, 1) in te and (1, 0) in te


def test_identical_lossy_regions_match_uniform_rescaling():
    eps, mu = 2.0 + 0.1j, 1.3 + 0.02j
    vacuum = cavity.rectangular_cavity_modes(box_size=LENGTHS, frequency_limit=400e6)
    modes = mc.slab_loaded_cavity_modes(
        box_size=LENGTHS, thickness=0.25, frequency_limit=400e6 / math.sqrt(2 * 1.3) * 1.001,
        relative_permittivity=(eps, eps), relative_permeability=(mu, mu))
    expected = sorted((mc.uniformly_filled_eigenvalue(wavenumber_squared=m.wavenumber_squared,
                                                      relative_permittivity=eps, relative_permeability=mu)
                       for m in vacuum), key=lambda v: v.real)
    assert len(modes) == len(expected)
    np.testing.assert_allclose([m.wavenumber_squared for m in modes], expected, rtol=1e-12)
    phase = -cmath.phase(1 / cmath.sqrt(eps * mu))       # the loss angle, positive under exp(-i omega t)
    for mode in modes:
        assert mode.resonant_frequency.imag < 0
        assert mode.quality_factor == pytest.approx(1 / (2 * math.tan(phase)), rel=1e-11)


def test_uniform_dielectric_quality_factor_closed_form():
    for tan_delta in (1e-4, 0.01, 0.3):
        eigenvalue = mc.uniformly_filled_eigenvalue(wavenumber_squared=np.pi**2 * 2,
                                                    relative_permittivity=3.0 * (1 + 1j * tan_delta))
        q = mc.quality_factor(resonant_frequency=mc.complex_frequency_from_eigenvalue(wavenumber_squared=eigenvalue))
        assert q == pytest.approx(mc.dielectric_loss_quality_factor(loss_tangent=tan_delta), rel=1e-12)
    assert mc.dielectric_loss_quality_factor(loss_tangent=1e-4) == pytest.approx(1e4, rel=1e-8)


def test_small_loss_matches_energy_filling_perturbation():
    """Q^-1 = tan_delta * p_e, with p_e = -(eps'/k0^2) d(k0^2)/d eps' (Hellmann-Feynman).

    The derivative uses independent lossless roots at eps' +/- h, so this checks
    the complex continuation against the real dispersion relation.
    """
    eps, tan_delta, h = 4.0, 1e-4, 1e-4
    box = dict(box_size=LENGTHS, thickness=0.3, frequency_limit=300e6)
    lossy = mc.slab_loaded_cavity_modes(**box, relative_permittivity=(eps * (1 + 1j * tan_delta), 1.0))
    plus = mc.slab_loaded_cavity_modes(**box, relative_permittivity=(eps + h, 1.0))
    minus = mc.slab_loaded_cavity_modes(**box, relative_permittivity=(eps - h, 1.0))
    assert len(lossy) == len(plus) == len(minus) >= 6
    for mode, up, down in zip(lossy, plus, minus):
        assert (mode.family, mode.indices) == (up.family, up.indices) == (down.family, down.indices)
        derivative = (up.wavenumber_squared.real - down.wavenumber_squared.real) / (2 * h)
        filling = -eps * derivative / mode._lossless_wavenumber_squared       # the lossless root (internal)
        assert 0 < filling < 1
        assert 1 / mode.quality_factor == pytest.approx(tan_delta * filling, rel=2e-3)


def test_slab_raises_lowest_quality_factor_above_uniform_bound():
    tan_delta = 0.01
    modes = mc.slab_loaded_cavity_modes(box_size=LENGTHS, thickness=0.3, frequency_limit=300e6,
                                        relative_permittivity=(4 * (1 + 1j * tan_delta), 1.0))
    bound = mc.dielectric_loss_quality_factor(loss_tangent=tan_delta)
    assert all(m.quality_factor > bound and m.resonant_frequency.imag < 0 for m in modes)


@pytest.mark.parametrize("kwargs", [
    {"relative_permittivity": (2 - 0.1j, 1.0)},                     # a gain under exp(-i omega t)
    {"relative_permittivity": (-1.0, 1.0)},
    {"relative_permittivity": (True, 1.0)},
    {"relative_permittivity": (2.0, 1.0), "relative_permeability": (float("nan"), 1.0)},
    {"relative_permittivity": 2.0},                                 # one value: the pair (slab, background)
])
def test_invalid_materials(kwargs):
    with pytest.raises(ValueError, match="relative_perm"):
        mc.slab_loaded_cavity_modes(box_size=LENGTHS, thickness=0.3, frequency_limit=300e6, **kwargs)


def test_invalid_geometry():
    with pytest.raises(ValueError, match="smaller"):
        mc.slab_loaded_cavity_modes(box_size=LENGTHS, thickness=0.6, frequency_limit=300e6,
                                    relative_permittivity=(2.0, 1.0))
    with pytest.raises(ValueError, match="box_size"):
        mc.slab_loaded_cavity_modes(box_size=(1, 1), thickness=0.3, frequency_limit=300e6,
                                    relative_permittivity=(2.0, 1.0))
    with pytest.raises(ValueError, match="wavenumber_squared"):
        mc.uniformly_filled_eigenvalue(wavenumber_squared=-1.0, relative_permittivity=2.0)
    with pytest.raises(ValueError, match="subdivision_count"):
        mc.slab_loaded_cavity_modes(box_size=LENGTHS, thickness=0.3, frequency_limit=300e6,
                                    relative_permittivity=(2.0, 1.0), subdivision_count=0)


def test_public_values_are_the_conjugates_of_the_exp_plus_j_omega_t_closed_forms():
    """Under exp(-i omega t) every complex output is the conjugate of the formula's exp(+j omega t) value."""
    eps, mu, k2 = 2.2 + 0.044j, 1.1 + 0.01j, 2 * np.pi ** 2
    kernel = k2 / (eps.conjugate() * mu.conjugate())            # Python complex arithmetic, as the module's
    public = mc.uniformly_filled_eigenvalue(wavenumber_squared=k2, relative_permittivity=eps,
                                            relative_permeability=mu)
    assert public == kernel.conjugate()
    assert public.imag < 0
    f = mc.complex_frequency_from_eigenvalue(wavenumber_squared=public)
    assert f == (cavity.C0 * cmath.sqrt(kernel) / (2 * math.pi)).conjugate()
    assert f.imag < 0
    assert mc.quality_factor(resonant_frequency=f) == f.real / (-2 * f.imag)
    assert mc.quality_factor(resonant_frequency=f) > 0
    assert mc.quality_factor(resonant_frequency=f.real) == math.inf


@pytest.mark.parametrize("call,name", [
    (lambda: mc.quality_factor(resonant_frequency="1 GHz"), "resonant_frequency"),
    (lambda: mc.complex_frequency_from_eigenvalue(wavenumber_squared="2"), "wavenumber_squared"),
    (lambda: mc.uniformly_filled_eigenvalue(wavenumber_squared=2.0, relative_permittivity="4"),
     "relative_permittivity"),
    (lambda: mc.dielectric_loss_quality_factor(loss_tangent="0.01"), "loss_tangent"),
    (lambda: mc.slab_loaded_cavity_modes(box_size=LENGTHS, thickness="0.3 m", frequency_limit=300e6,
                                         relative_permittivity=(2.0, 1.0)), "thickness"),
])
def test_text_for_a_quantity_is_a_type_error(call, name):
    with pytest.raises(TypeError, match=name):
        call()
