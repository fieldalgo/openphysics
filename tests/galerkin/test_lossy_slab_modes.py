# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Complex effective indices of galerkin's mode solvers graded against refsol.lossy_slab.

Two structures, lengths in micrometres at 1.55 um: a bound symmetric SOI slab
whose film absorbs (n = 3.48 - 0.01i, cladding 1.444, 0.22 um) solved in a
closed PEC strip, and the substrate-leaky slab of tests/galerkin/test_pml_modes.py
(film 0.22 um, 0.25 um low-index gap, silicon substrate) solved with the
complex-coordinate PML. The references are the transfer-matrix roots on the
decaying sheet (bound) and on the outgoing sheet (leaky).

Measured on the three strips below (h = 0.04, 0.02, 0.01; nodes 332/972/3553
bound and 456/1350/4928 leaky), the complex error |n - n_ref| was
    bound  TE scalar 6.59e-3 1.88e-3 4.73e-4   (orders 1.81, 1.99)
    bound  TE vector 5.57e-3 1.57e-3 3.93e-4   (orders 1.83, 2.00)
    bound  TM vector 8.57e-3 2.68e-3 6.80e-4   (orders 1.68, 1.98)
    leaky  TE scalar 6.39e-3 1.85e-3 4.72e-4   (orders 1.79, 1.97)
    leaky  TE vector 5.31e-3 1.53e-3 3.90e-4   (orders 1.80, 1.97)
    leaky  TM vector 8.18e-3 2.54e-3 6.43e-4   (orders 1.69, 1.98)
and the relative error of Im n_eff at h = 0.01 was at most 2.9e-4 (bound TE),
1.8e-3 (bound TM), 1.6e-3 (leaky TE vector) and 3.7e-3 (leaky TM). The bounds
below leave about a factor three on the finest error and a factor 2.5 on the
imaginary part; the order floor 1.7 is the finest pair rounded down.
"""

import math

import numpy as np
import pytest

from galerkin import rectangle_mesh, solve_modes
from galerkin.mode_coordinates import mode_coordinates, solve_scalar_coordinates
from conftest import rate

WL = 1.55
K0 = 2 * math.pi / WL
STEPS = (0.04, 0.02, 0.01)
CASES = [("TE", False), ("TE", True), ("TM", True)]


def strip(breaks, step, width=0.1):
    """Structured strip whose x rows fall on every material or PML face in breaks."""
    x = np.concatenate([np.linspace(a, b, int(np.ceil((b - a) / step)) + 1)[:-1]
                        for a, b in zip(breaks[:-1], breaks[1:])] + [[breaks[-1]]])
    mesh = rectangle_mesh(len(x) - 1, width, len(x) - 1, max(2, int(np.ceil(width / step))))
    mesh.nodes[:, 0] = x[mesh.nodes[:, 0].astype(int)]
    return mesh, mesh.nodes[mesh.triangles, 0].mean(axis=1)


def pec_nodes(mesh, pol, vector):
    # the vector TE family needs PEC top/bottom walls; TM leaves them natural (PMC)
    sides = ["left", "right", "top", "bottom"] if vector and pol == "TE" else ["left", "right"]
    return np.unique(np.concatenate([mesh.boundary[s] for s in sides]))


def nearest(values, expected):
    return values[np.argmin(abs(values - expected))]


def solve_bound(step, pol, vector, expected, pad=1.5):
    mesh, centers = strip([-pad, 0.0, 0.22, 0.22 + pad], step)
    eps = np.where((centers > 0) & (centers < 0.22), (3.48 - 0.01j) ** 2, 1.444**2 + 0j)
    fixed = pec_nodes(mesh, pol, vector)
    if vector:
        n, *_ = solve_modes(mesh, eps, K0, expected.real, num_modes=4, pec_nodes=fixed)
    else:
        n, _ = solve_scalar_coordinates(mesh, eps, K0, expected.real, np.ones((mesh.num_triangles, 3)),
                                        num_modes=4, fixed_nodes=fixed)
    return nearest(n, expected)


def solve_leaky(step, pol, vector, expected, pml=1.0, pad=1.0):
    mesh, centers = strip([-pad - pml, -pad, 0.0, 0.22, 0.47, 0.47 + pad, 0.47 + pad + pml], step)
    eps = np.where(((centers > 0) & (centers < 0.22)) | (centers > 0.47), 3.48**2, 1.444**2)
    coords = mode_coordinates(mesh, thickness=dict(left=pml, right=pml), strength=3.0)
    fixed = pec_nodes(mesh, pol, vector)
    if vector:
        n, *_ = solve_modes(mesh, eps, K0, expected.real, num_modes=6, pec_nodes=fixed,
                            coordinate_factors=coords.factors)
    else:
        n, _ = solve_scalar_coordinates(mesh, eps, K0, expected.real, coords.factors, fixed_nodes=fixed)
    return nearest(n, expected)


def check_convergence(errors, imag_relative, label):
    assert errors[0] > errors[1] > errors[2], f"{label}: errors {errors}"
    assert errors[-1] < 2e-3, f"{label}: finest error {errors[-1]:.3e}"
    assert rate(errors)[-1] > 1.7, f"{label}: orders {rate(errors)}"
    assert imag_relative < 1e-2, f"{label}: Im n_eff relative error {imag_relative:.3e}"


@pytest.mark.parametrize("pol,vector", CASES)
def test_absorbing_slab_converges_to_the_decaying_sheet_root(refsol, pol, vector):
    expected = refsol.lossy_slab.three_layer_modes(3.48 - 0.01j, 1.444, 1.444, 0.22, WL, pol)[0]
    assert expected.imag < 0
    values = [solve_bound(h, pol, vector, expected) for h in STEPS]
    assert all(v.imag < 0 for v in values)
    errors = [abs(v - expected) for v in values]
    check_convergence(errors, abs(values[-1].imag / expected.imag - 1), f"bound {pol} vector={vector}")


@pytest.mark.parametrize("pol,vector", CASES)
def test_pml_leaky_slab_converges_to_the_outgoing_sheet_root(refsol, pol, vector):
    expected = refsol.lossy_slab.substrate_leaky_mode(3.48, 1.444, 3.48, 0.22, 0.25, WL, pol=pol)
    assert expected.imag < 0
    values = [solve_leaky(h, pol, vector, expected) for h in STEPS]
    assert all(v.imag < 0 for v in values)
    errors = [abs(v - expected) for v in values]
    check_convergence(errors, abs(values[-1].imag / expected.imag - 1), f"leaky {pol} vector={vector}")


def test_lossless_film_recovers_the_real_slab_reference(refsol):
    # the complex reference with zero loss is the existing real one, and the
    # closed strip then returns a real spectrum
    reference = refsol.slab.modes(3.48, 1.444, 1.444, 0.22, WL, "TE")[0]
    expected = refsol.lossy_slab.three_layer_modes(3.48, 1.444, 1.444, 0.22, WL, "TE")[0]
    assert expected == reference
    mesh, centers = strip([-1.5, 0.0, 0.22, 1.72], 0.02)
    eps = np.where((centers > 0) & (centers < 0.22), 3.48**2, 1.444**2)
    n, *_ = solve_modes(mesh, eps, K0, reference, num_modes=4, pec_nodes=pec_nodes(mesh, "TE", True))
    value = nearest(n, expected)
    assert abs(value - reference) < 2e-3 and abs(value.imag) < 1e-10
