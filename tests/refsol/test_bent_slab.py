# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Self-checks of the bent-slab pole reference; skipped without the optional mpmath."""

import sys

import numpy as np
import pytest

from refsol import bent_slab as bs, slab

mpmath = pytest.importorskip("mpmath")

FILM, CLAD, D, WL = 3.48, 1.444, 0.22, 1.55


@pytest.mark.parametrize("pol", ["TE", "TM"])
def test_pole_has_small_residual_and_radiates(pol):
    n = bs.mode(FILM, CLAD, D, 2.0, WL, pol)
    assert n.imag < 0
    assert bs.residual(n, FILM, CLAD, D, 2.0, WL, pol) <= 1e-12
    assert abs(bs.characteristic(n, FILM, CLAD, D, 2.0, WL, pol)) <= 1e-12
    # the index referred to the inner radius exceeds the straight-slab value: the
    # field centroid sits outside R, so the phase advances faster at R
    straight = slab.modes(FILM, CLAD, CLAD, D, WL, pol)[0]
    assert straight < n.real < FILM


def test_large_radius_recovers_the_straight_slab_at_first_order_in_1_over_r():
    # n(R) = n_straight + a/R + O(1/R^2): the products (n - n_straight) R converge
    straight = slab.modes(FILM, CLAD, CLAD, D, WL, "TE")[0]
    radii = np.array([10.0, 20.0, 40.0, 80.0])
    values = np.array([bs.mode(FILM, CLAD, D, r, WL, "TE") for r in radii])
    shifts = values.real - straight
    assert np.all(shifts > 0) and np.all(np.diff(shifts) < 0)
    products = shifts * radii
    steps = abs(np.diff(products))
    assert steps[0] > steps[1] > steps[2]           # second-order remainder halves per doubling
    assert steps[2] / steps[1] == pytest.approx(0.5, abs=0.1)
    # Richardson in 1/R: 2 n(2R) - n(R) = n_straight + O(1/R^2); measured 5.8e-6 at R = 40/80
    # against a shift of 3.9e-3 at R = 80
    extrapolated = 2 * values[-1].real - values[-2].real
    assert abs(extrapolated - straight) < 2e-5
    assert abs(extrapolated - straight) < shifts[-1] / 100
    assert np.all(abs(values.imag) < 1e-15)        # radiation loss vanishes faster than any power


def test_bend_loss_grows_as_the_radius_shrinks():
    radii = (1.0, 1.5, 2.0, 3.0)
    loss = np.array([-bs.mode(FILM, CLAD, D, r, WL, "TM").imag for r in radii])
    assert np.all(loss > 0) and np.all(np.diff(loss) < 0)
    # exponential in the radius: successive log ratios grow in magnitude
    log_ratio = np.diff(np.log(loss)) / np.diff(radii)
    assert np.all(log_ratio < 0)
    te = -bs.mode(FILM, CLAD, D, 2.0, WL, "TE").imag
    assert te < loss[2]                             # the TE mode is better confined than TM


def test_guess_and_order_are_honoured():
    direct = bs.mode(FILM, CLAD, D, 2.0, WL, "TM")
    guessed = bs.mode(FILM, CLAD, D, 2.0, WL, "TM", guess=direct + 0.002 - 0.0005j)
    assert abs(guessed - direct) < 1e-12
    with pytest.raises(ValueError, match="guides only"):
        bs.mode(FILM, CLAD, D, 2.0, WL, "TE", order=3)
    with pytest.raises(ValueError, match="exceed"):
        bs.mode(1.0, CLAD, D, 2.0, WL)
    with pytest.raises(ValueError, match="pol"):
        bs.mode(FILM, CLAD, D, 2.0, WL, "TEM")
    with pytest.raises(RuntimeError, match="no bent-slab pole"):
        bs.mode(FILM, CLAD, D, 2.0, WL, "TE", guess=3.3 + 0.5j, tol=1e-300)


def test_missing_mpmath_is_reported(monkeypatch):
    monkeypatch.setitem(sys.modules, "mpmath", None)
    with pytest.raises(ImportError, match="mpmath"):
        bs.characteristic(3.0, FILM, CLAD, D, 2.0, WL)
    with pytest.raises(ImportError, match="not a galerkin-refsol dependency"):
        bs.mode(FILM, CLAD, D, 2.0, WL)
