# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Self-consistency of the exact vector fiber mode fields (no FEM involved)."""

import numpy as np
import pytest

from refsol import fiber

A, N1, N2, WL = 4.0, 1.45, 1.44, 1.55
LABELS = ["HE11", "TE01", "TM01", "HE21"]


def _mode(label):
    return next(md for md in fiber.vector_modes(A, N1, N2, WL, l_max=3) if md.label == label)


@pytest.mark.parametrize("label", LABELS)
def test_continuity_conditions_are_singular_exactly_at_the_root(label):
    mode = _mode(label)
    s = np.linalg.svd(fiber._continuity_matrix(mode, A, N1, N2, WL), compute_uv=False)
    assert s[-1] < 1e-9 * s[0]
    shifted = fiber.Mode(mode.label, mode.l, mode.m, mode.neff + 1e-4,
                         *(lambda n: (2 * np.pi * A / WL * np.sqrt(N1 ** 2 - n ** 2),
                                      2 * np.pi * A / WL * np.sqrt(n ** 2 - N2 ** 2)))(mode.neff + 1e-4))
    s_off = np.linalg.svd(fiber._continuity_matrix(shifted, A, N1, N2, WL), compute_uv=False)
    assert s_off[-1] > 1e3 * s[-1]


def _polar(field, phi):
    Ex, Ey, Ez = field[..., 0], field[..., 1], field[..., 2]
    return Ex * np.cos(phi) + Ey * np.sin(phi), -Ex * np.sin(phi) + Ey * np.cos(phi), Ez


@pytest.mark.parametrize("label", LABELS)
def test_interface_conditions_hold_across_the_core_boundary(label):
    """E_phi and E_z continuous, n^2 E_r continuous (normal D) at r = a."""
    phi = np.linspace(0.1, 2 * np.pi, 13)
    inner, outer = A * (1 - 1e-9), A * (1 + 1e-9)
    for p in range(1 if fiber.mode_l(label) == 0 else 2):
        fi = fiber.vector_mode_field(A, N1, N2, WL, label, inner * np.cos(phi), inner * np.sin(phi), p)
        fo = fiber.vector_mode_field(A, N1, N2, WL, label, outer * np.cos(phi), outer * np.sin(phi), p)
        (ri, ti, zi), (ro, to, zo) = _polar(fi, phi), _polar(fo, phi)
        scale = np.abs(fi).max()
        np.testing.assert_allclose(ti, to, atol=1e-7 * scale)
        np.testing.assert_allclose(zi, zo, atol=1e-7 * scale)
        np.testing.assert_allclose(N1 ** 2 * ri, N2 ** 2 * ro, atol=1e-7 * N1 ** 2 * scale)
        if np.abs(ri).max() > 1e-3 * scale:
            assert np.abs(ri - ro).max() > 1e-4 * scale          # E_r itself jumps


def test_te_has_no_ez_and_tm_has_no_ephi():
    x, y = np.array([1.0, 2.5, 5.0]), np.array([0.5, -1.0, 3.0])
    te = fiber.vector_mode_field(A, N1, N2, WL, "TE01", x, y)
    tm = fiber.vector_mode_field(A, N1, N2, WL, "TM01", x, y)
    phi = np.arctan2(y, x)
    assert np.abs(te).max() > 0 and np.abs(tm).max() > 0
    assert np.abs(te[:, 2]).max() < 1e-12 * np.abs(te).max()
    assert np.abs(_polar(tm, phi)[1]).max() < 1e-12 * np.abs(tm).max()


@pytest.mark.parametrize("label", ["HE11", "HE21"])
def test_the_two_polarizations_are_independent_and_rotated(label):
    """p = pi/2 is the p = 0 field rotated by pi/(2l) in the plane."""
    l = fiber.mode_l(label)
    rng = np.random.default_rng(1)
    r, phi = rng.uniform(0.5, 9, 20), rng.uniform(0, 2 * np.pi, 20)
    f0 = fiber.vector_mode_field(A, N1, N2, WL, label, r * np.cos(phi), r * np.sin(phi), 0)
    f1 = fiber.vector_mode_field(A, N1, N2, WL, label, r * np.cos(phi), r * np.sin(phi), 1)
    assert np.linalg.matrix_rank(np.stack([f0.ravel(), f1.ravel()]), tol=1e-6 * np.abs(f0).max()) == 2
    shift = np.pi / (2 * l)
    rotated = fiber.vector_mode_field(A, N1, N2, WL, label, r * np.cos(phi + shift), r * np.sin(phi + shift), 0)
    # field of p = pi/2 at angle phi equals the p = 0 field at phi + pi/(2l), with E_t rotated back
    rr0, rt0, rz0 = _polar(rotated, phi + shift)
    rr1, rt1, rz1 = _polar(f1, phi)
    np.testing.assert_allclose(np.stack([rr1, rt1, rz1]), np.stack([rr0, rt0, rz0]), atol=1e-10 * np.abs(f0).max())


def test_single_polarization_and_unguided_requests_are_refused():
    with pytest.raises(ValueError, match="single polarization"):
        fiber.vector_mode_field(A, N1, N2, WL, "TE01", [1.0], [0.0], 1)
    with pytest.raises(ValueError, match="not guided"):
        fiber.vector_mode_field(A, N1, N2, WL, "EH11", [1.0], [0.0])


@pytest.mark.parametrize("label", ["HE", "HE1", "XY11", "HE1a"])
def test_malformed_labels_are_refused(label):
    with pytest.raises(ValueError, match="malformed"):
        fiber.mode_l(label)
