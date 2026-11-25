# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""A vector mode search that stops at its restart cap (SEARCH_RESTARTS).

A search for more roots than lie between the shift and the static beta^2 = 0 family
asks ARPACK for vectors of that exactly degenerate family. Whether it converges them,
and how fast, depends on the last bits of the pencil: the bent slab of
tests/simcase/test_pml_gain_bound.py with 64 roots converged in 67 s under one NumPy
CPU dispatch and had not converged after 30 min under another (2026-11-25). At the cap
the converged pairs are kept, with a PartialSearchWarning, only when the search has
reached the family: at least one static root converged, every other converged root is
nearer the shift (|nu| > 1/|sigma|) and has a relative residual <= PARTIAL_RESIDUAL_TOL.
Otherwise ARPACK's ArpackNoConvergence is raised as before.
Lengths in micrometres; the slab of test_pml_modes.
"""
import numpy as np
import pytest
import scipy.sparse as sp
import scipy.sparse.linalg as spla

import galerkin._waveguide_kernels as waveguide
from galerkin.kernels import solve_modes
from galerkin.waveguide import PartialSearchWarning, STATIC_ROOT_TOL
from test_waveguide_static_roots import N_TARGET, SIGMA, recorded_eigs, slab, static
from test_pml_modes import K0

SHIFT = -4.0          # sigma of the synthetic pencils: the static family is nu = 1/4


def diagonal(lams):
    """A x = lambda B x with B = I: the eigenvectors are the unit vectors, the residuals are 0."""
    lams = np.asarray(lams, dtype=complex)
    return sp.diags(lams).tocsc(), sp.identity(len(lams), dtype=complex, format="csc"), lams


def stopped(lams, columns):
    """ArpackNoConvergence holding the pairs ``columns`` of the diagonal pencil ``lams``."""
    vectors = np.eye(len(lams), dtype=complex)[:, columns]
    nu = 1 / (np.asarray(lams, dtype=complex)[columns] - SHIFT)
    return spla.ArpackNoConvergence("ARPACK error -1: No convergence", nu, vectors)


# lambda: -3.5 and -4.6 are nearer the shift -4 than 0 is (|nu| = 2, 1.67 > 1/4); 0, 0 static;
# -9 and 1.5 are farther (|nu| = 0.2, 0.18 < 1/4)
LAMS = [-3.5, -4.6, 0.0, 0.0, -9.0, 1.5]


def test_the_converged_pairs_are_kept_when_only_static_roots_are_missing():
    A, B, lams = diagonal(LAMS)
    with pytest.warns(PartialSearchWarning, match=r"stopped after 200 restarts with 3 of 4 roots converged; "
                                                  r"the missing values were static roots"):
        nu, vectors = waveguide._partial_search(stopped(lams, [0, 1, 2]), A, B, SHIFT, 4)
    np.testing.assert_array_equal(nu, 1 / (lams[[0, 1, 2]] - SHIFT))
    np.testing.assert_array_equal(vectors, np.eye(6, dtype=complex)[:, [0, 1, 2]])


def test_a_search_that_has_not_reached_the_static_family_raises():
    # a non-static root is missing (the search stopped before the family): no static root converged
    A, B, lams = diagonal(LAMS)
    error = stopped(lams, [0])
    with pytest.raises(spla.ArpackNoConvergence) as raised:
        waveguide._partial_search(error, A, B, SHIFT, 3)
    assert raised.value is error


def test_a_converged_root_beyond_the_static_family_raises():
    # -9 has |nu| = 0.2 <= 1/|sigma| = 0.25: ARPACK passed the family, so roots can be missing anywhere
    A, B, lams = diagonal(LAMS)
    error = stopped(lams, [0, 2, 4])
    with pytest.raises(spla.ArpackNoConvergence) as raised:
        waveguide._partial_search(error, A, B, SHIFT, 4)
    assert raised.value is error


def test_a_root_at_the_static_family_modulus_raises():
    # |nu| = 1/|sigma| exactly but lambda = -8, not static: refused (the bound is strict)
    A, B, lams = diagonal([-3.5, 0.0, -8.0])
    with pytest.raises(spla.ArpackNoConvergence):
        waveguide._partial_search(stopped(lams, [0, 1, 2]), A, B, SHIFT, 4)


def test_a_root_with_a_large_residual_raises():
    A, B, lams = diagonal(LAMS)
    error = stopped(lams, [0, 1, 2])
    error.eigenvectors[3, 0] = 1e-6        # the first pair is no longer an eigenpair (residual ~ 1e-6)
    with pytest.raises(spla.ArpackNoConvergence) as raised:
        waveguide._partial_search(error, A, B, SHIFT, 4)
    assert raised.value is error


def test_nothing_converged_raises():
    A, B, lams = diagonal(LAMS)
    error = stopped(lams, [])
    with pytest.raises(spla.ArpackNoConvergence):
        waveguide._partial_search(error, A, B, SHIFT, 4)


def test_the_search_asks_for_the_restart_cap(monkeypatch):
    mesh, eps, walls, coords = slab()
    asked = []
    original = waveguide.spla.eigs

    def eigs(*args, **kwargs):
        asked.append(kwargs["maxiter"])
        return original(*args, **kwargs)
    monkeypatch.setattr(waveguide.spla, "eigs", eigs)
    solve_modes(mesh, eps, K0, N_TARGET, num_modes=6, pec_nodes=walls, coordinate_factors=coords.factors)
    assert asked == [waveguide.SEARCH_RESTARTS] == [200]


@pytest.mark.parametrize("path", ["real", "pml"])
def test_a_stopped_search_missing_static_roots_returns_the_full_search_modes(monkeypatch, path):
    """The slab's 24-root search reaches the family. Replayed as a search that stopped with
    some static roots unconverged, it returns the same modes, bit for bit, and warns."""
    mesh, eps, walls, coords = slab()
    kwargs = dict(pec_nodes=walls, coordinate_factors=coords.factors if path == "pml" else None)
    full = recorded_eigs(monkeypatch)
    reference = solve_modes(mesh, eps, K0, N_TARGET, num_modes=24, **kwargs)
    nu, vectors = full[0]
    found = static(nu)
    assert found.sum() >= 2
    kept = np.flatnonzero(~found | (np.cumsum(found) == 1))   # every non-static root and one static root

    def stop(*args, **kw):
        raise spla.ArpackNoConvergence("ARPACK error -1: No convergence", nu[kept].copy(), vectors[:, kept].copy())
    monkeypatch.setattr(waveguide.spla, "eigs", stop)
    with pytest.warns(PartialSearchWarning) as caught:
        n, space, et, ez = solve_modes(mesh, eps, K0, N_TARGET, num_modes=24, **kwargs)
    assert len(caught) == 1 and f"with {len(kept)} of 24 roots converged" in str(caught[0].message)
    np.testing.assert_array_equal(n, reference[0])
    np.testing.assert_array_equal(et, reference[2])
    np.testing.assert_array_equal(ez, reference[3])


def test_a_stopped_search_without_a_static_root_still_raises(monkeypatch):
    mesh, eps, walls, coords = slab()
    full = recorded_eigs(monkeypatch)
    solve_modes(mesh, eps, K0, N_TARGET, num_modes=24, pec_nodes=walls, coordinate_factors=coords.factors)
    nu, vectors = full[0]
    kept = np.flatnonzero(~static(nu))

    def stop(*args, **kw):
        raise spla.ArpackNoConvergence("ARPACK error -1: No convergence", nu[kept].copy(), vectors[:, kept].copy())
    monkeypatch.setattr(waveguide.spla, "eigs", stop)
    with pytest.raises(spla.ArpackNoConvergence):
        solve_modes(mesh, eps, K0, N_TARGET, num_modes=24, pec_nodes=walls, coordinate_factors=coords.factors)


def test_the_static_tolerance_is_the_kernels():
    assert STATIC_ROOT_TOL == 1e-10 and waveguide.PARTIAL_RESIDUAL_TOL == 1e-10 and SIGMA < 0
