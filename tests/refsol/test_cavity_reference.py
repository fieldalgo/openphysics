# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

import math

import numpy as np
import pytest

from refsol import cavity, metallic


def test_cube_first_two_clusters_and_polarizations():
    modes = cavity.rectangular_cavity_modes(box_size=(1, 1, 1), frequency_limit=cavity.C0 * math.sqrt(3) / 2)
    assert len(modes) == 5
    assert [mode.indices for mode in modes[:3]] == [(0, 1, 1), (1, 0, 1), (1, 1, 0)]
    assert [mode.polarization for mode in modes[3:]] == [0, 1]
    np.testing.assert_allclose([mode.wavenumber_squared for mode in modes],
                               np.pi ** 2 * np.array([2, 2, 2, 3, 3]))
    assert cavity.rectangular_cavity_modes(box_size=(1, 1, 1), frequency_limit=cavity.C0 / 2) == []


def test_cartesian_enumeration_agrees_with_independent_te_tm_reference():
    lengths = (1.0, 0.8, 0.6)
    ceiling = 2 * cavity.C0
    modes = cavity.rectangular_cavity_modes(box_size=lengths, frequency_limit=ceiling)
    expected = [k2 for k2, _ in metallic.rect_cavity_resonances(box_size=lengths, n_max=5)
                if cavity.C0 * math.sqrt(k2) / (2 * math.pi) <= ceiling * (1 + 1e-14)]
    assert len(modes) == len(expected)
    np.testing.assert_allclose([mode.wavenumber_squared for mode in modes], expected, rtol=1e-14)


def test_physical_scaling_preserves_indices_and_multiplicity():
    modes = cavity.rectangular_cavity_modes(box_size=(1, 0.8, 0.6), frequency_limit=2 * cavity.C0)
    small = cavity.rectangular_cavity_modes(box_size=(1e-6, 0.8e-6, 0.6e-6), frequency_limit=2e6 * cavity.C0)
    assert [(m.indices, m.polarization) for m in modes] == [(m.indices, m.polarization) for m in small]
    np.testing.assert_allclose([m.frequency for m in small],
                               np.array([m.frequency for m in modes]) * 1e6)
    np.testing.assert_allclose([m.wavenumber_squared for m in small],
                               np.array([m.wavenumber_squared for m in modes]) * 1e12)


@pytest.mark.parametrize("lengths", [(1, 1), (1, 1, 0), (1, -1, 1), (1, math.inf, 1),
                                    (1, math.nan, 1), (True, 1, 1), None])
def test_invalid_lengths(lengths):
    with pytest.raises(ValueError, match="box_size"):
        cavity.rectangular_cavity_modes(box_size=lengths, frequency_limit=1e9)


@pytest.mark.parametrize("ceiling", [0, -1, math.inf, math.nan, True])
def test_invalid_frequency_ceiling(ceiling):
    with pytest.raises(ValueError, match="frequency_limit"):
        cavity.rectangular_cavity_modes(box_size=(1, 1, 1), frequency_limit=ceiling)


@pytest.mark.parametrize("name,kwargs", [("box_size", dict(box_size=("1", 1, 1), frequency_limit=1e9)),
                                         ("frequency_limit", dict(box_size=(1, 1, 1), frequency_limit="100"))])
def test_text_for_a_quantity_is_a_type_error(name, kwargs):
    # a str was refused with ValueError before the galerkin step; the scan's string rule makes it TypeError
    with pytest.raises(TypeError, match=name):
        cavity.rectangular_cavity_modes(**kwargs)
