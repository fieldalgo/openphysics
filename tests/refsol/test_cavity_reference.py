# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

import math

import numpy as np
import pytest

from refsol import cavity, metallic


def test_cube_first_two_clusters_and_polarizations():
    modes = cavity.rectangular_cavity_modes((1, 1, 1), cavity.C0 * math.sqrt(3) / 2)
    assert len(modes) == 5
    assert [mode.indices for mode in modes[:3]] == [(0, 1, 1), (1, 0, 1), (1, 1, 0)]
    assert [mode.polarization for mode in modes[3:]] == [0, 1]
    np.testing.assert_allclose([mode.eigenvalue_m2 for mode in modes],
                               np.pi ** 2 * np.array([2, 2, 2, 3, 3]))
    assert cavity.rectangular_cavity_modes((1, 1, 1), cavity.C0 / 2) == []


def test_cartesian_enumeration_agrees_with_independent_te_tm_reference():
    lengths = (1.0, 0.8, 0.6)
    ceiling = 2 * cavity.C0
    modes = cavity.rectangular_cavity_modes(lengths, ceiling)
    expected = [k2 for k2, _ in metallic.rect_cavity_resonances(*lengths, n_max=5)
                if cavity.C0 * math.sqrt(k2) / (2 * math.pi) <= ceiling * (1 + 1e-14)]
    assert len(modes) == len(expected)
    np.testing.assert_allclose([mode.eigenvalue_m2 for mode in modes], expected, rtol=1e-14)


def test_physical_scaling_preserves_indices_and_multiplicity():
    modes = cavity.rectangular_cavity_modes((1, 0.8, 0.6), 2 * cavity.C0)
    small = cavity.rectangular_cavity_modes((1e-6, 0.8e-6, 0.6e-6), 2e6 * cavity.C0)
    assert [(m.indices, m.polarization) for m in modes] == [(m.indices, m.polarization) for m in small]
    np.testing.assert_allclose([m.frequency_hz for m in small],
                               np.array([m.frequency_hz for m in modes]) * 1e6)
    np.testing.assert_allclose([m.eigenvalue_m2 for m in small],
                               np.array([m.eigenvalue_m2 for m in modes]) * 1e12)


@pytest.mark.parametrize("lengths", [(1, 1), (1, 1, 0), (1, -1, 1), (1, math.inf, 1),
                                    (1, math.nan, 1), (True, 1, 1), ("1", 1, 1), None])
def test_invalid_lengths(lengths):
    with pytest.raises(ValueError):
        cavity.rectangular_cavity_modes(lengths, 1e9)


@pytest.mark.parametrize("ceiling", [0, -1, math.inf, math.nan, True, "100"])
def test_invalid_frequency_ceiling(ceiling):
    with pytest.raises(ValueError):
        cavity.rectangular_cavity_modes((1, 1, 1), ceiling)
