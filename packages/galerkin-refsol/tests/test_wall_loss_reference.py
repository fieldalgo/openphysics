# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Self-checks of the conductor-loss perturbation reference."""

import math

import numpy as np
import pytest

from refsol import wall_loss as wl

COPPER = 5.8e7


@pytest.mark.parametrize("lengths", [(1.0, 0.5, 0.8), (0.02286, 0.01016, 0.03), (1, 1, 1)])
def test_te101_matches_pozar(lengths):
    a, b, d = lengths
    f101 = wl.C0 / 2 * math.hypot(1 / a, 1 / d)
    modes = [m for m in wl.wall_loss_modes(lengths, f101 * 1.0001, COPPER)
             if m.indices == (1, 0, 1)]
    assert len(modes) == 1
    assert modes[0].polarization == (0.0, 1.0, 0.0)
    assert modes[0].quality_factor == pytest.approx(
        wl.pozar_te101_quality_factor(a, b, d, COPPER), rel=1e-12)


def _numerical_q(lengths, indices, amplitude, sigma, points=12):
    """Gauss quadrature of a finite-difference curl, independent of the closed forms."""
    k = np.array(indices) * np.pi / np.array(lengths)
    ax, ay, az = amplitude

    def field(x, y, z):
        return np.stack([ax * np.cos(k[0] * x) * np.sin(k[1] * y) * np.sin(k[2] * z),
                         ay * np.sin(k[0] * x) * np.cos(k[1] * y) * np.sin(k[2] * z),
                         az * np.sin(k[0] * x) * np.sin(k[1] * y) * np.cos(k[2] * z)])

    def curl(x, y, z, h=1e-6):
        def partial(axis):
            shift = [np.zeros_like(x), np.zeros_like(x), np.zeros_like(x)]
            shift[axis] = shift[axis] + h
            plus = field(x + shift[0], y + shift[1], z + shift[2])
            minus = field(x - shift[0], y - shift[1], z - shift[2])
            return (plus - minus) / (2 * h)
        d = [partial(axis) for axis in range(3)]   # d[axis][component]
        return np.stack([d[1][2] - d[2][1], d[2][0] - d[0][2], d[0][1] - d[1][0]])

    nodes, weights = np.polynomial.legendre.leggauss(points)
    grid = [(nodes + 1) * L / 2 for L in lengths]
    wts = [weights * L / 2 for L in lengths]
    X, Y, Z = np.meshgrid(*grid, indexing="ij")
    W = np.einsum("i,j,k->ijk", *wts)
    volume = np.sum(W * np.sum(curl(X, Y, Z) ** 2, axis=0))
    wall = 0.0
    for axis in range(3):
        others = [a for a in range(3) if a != axis]
        U, V = np.meshgrid(grid[others[0]], grid[others[1]], indexing="ij")
        WA = np.outer(wts[others[0]], wts[others[1]])
        for position in (0.0, lengths[axis]):
            coords = [None] * 3
            coords[axis] = np.full_like(U, position)
            coords[others[0]], coords[others[1]] = U, V
            c = curl(*coords)
            wall += np.sum(WA * (c[others[0]] ** 2 + c[others[1]] ** 2))
    omega = wl.C0 * np.linalg.norm(k)
    rs = math.sqrt(omega * wl.MU0 / (2 * sigma))
    return omega * wl.MU0 * volume / (rs * wall)


def test_closed_forms_match_numerical_quadrature_including_split_polarizations():
    lengths = (1.0, 0.8, 0.6)
    modes = wl.wall_loss_modes(lengths, 400e6, COPPER)
    checked = 0
    for mode in modes:
        numeric = _numerical_q(lengths, mode.indices, mode.polarization, COPPER)
        assert mode.quality_factor == pytest.approx(numeric, rel=1e-6)
        checked += 1
    doublet = [m for m in modes if m.indices == (1, 1, 1)]
    assert len(doublet) == 2
    assert abs(doublet[0].quality_factor / doublet[1].quality_factor - 1) > 0.1
    # With three positive indices the stored energy is isotropic in the amplitude
    # plane, so the loss-diagonal polarizations are Euclidean-orthogonal.
    assert abs(np.dot(doublet[0].polarization, doublet[1].polarization)) < 1e-12
    assert checked == len(modes) == 7


def test_cube_triplet_and_doublet_are_degenerate():
    modes = wl.wall_loss_modes((1, 1, 1), 300e6, COPPER)
    q = [m.quality_factor for m in modes]
    assert len(modes) == 5
    np.testing.assert_allclose(q[:3], q[0], rtol=1e-13)
    np.testing.assert_allclose(q[3:], q[3], rtol=1e-13)
    assert abs(np.dot(modes[3].polarization, modes[4].polarization)) < 1e-12


def test_wall_losses_add_and_scale_with_conductivity():
    lengths = (1.0, 0.45, 0.8)
    total = wl.wall_loss_modes(lengths, 400e6, COPPER)
    per_wall = [wl.wall_loss_modes(lengths, 400e6, {w: COPPER}) for w in wl.WALLS]
    for i, mode in enumerate(total):
        assert sum(1 / modes[i].quality_factor for modes in per_wall) == pytest.approx(
            1 / mode.quality_factor, rel=1e-12)
    quadruple = wl.wall_loss_modes(lengths, 400e6, 4 * COPPER)
    np.testing.assert_allclose([m.quality_factor for m in quadruple],
                               [2 * m.quality_factor for m in total], rtol=1e-12)
    mode = total[0]
    assert mode.complex_frequency_hz == pytest.approx(
        mode.frequency_hz * (1 + (1j - 1) / (2 * mode.quality_factor)), rel=1e-15)
    pec = wl.wall_loss_modes(lengths, 400e6, {"x0": None})
    assert all(m.quality_factor == math.inf for m in pec)


def test_uniform_filling_rescales_frequency_and_quality_factor():
    lengths, eps, mu = (1.0, 0.45, 0.8), 2.2, 1.3
    vacuum = wl.wall_loss_modes(lengths, 400e6, COPPER)
    filled = wl.wall_loss_modes(lengths, 400e6 / math.sqrt(eps * mu), COPPER,
                                relative_permittivity=eps, relative_permeability=mu)
    assert len(filled) == len(vacuum)
    for v, f in zip(vacuum, filled):
        assert f.frequency_hz == pytest.approx(v.frequency_hz / math.sqrt(eps * mu), rel=1e-13)
        assert f.quality_factor == pytest.approx(
            v.quality_factor * mu * (eps * mu) ** -0.25, rel=1e-12)


@pytest.mark.parametrize("sigma", [0.0, -1.0, True, {"top": 1.0}, {"x0": -2.0}])
def test_invalid_conductivity(sigma):
    with pytest.raises(ValueError):
        wl.wall_loss_modes((1, 1, 1), 300e6, sigma)
