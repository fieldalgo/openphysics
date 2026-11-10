# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The static beta^2 = 0 family of the vector mode pencil is never returned as a mode.

Every vector [0, e_z] satisfies A x = 0, so beta^2 = 0 is an eigenvalue of high
multiplicity. A search for more modes than lie between the target and this family
reaches it; its computed beta^2 is at rounding level and only sometimes exactly 0.
Before STATIC_ROOT_TOL, an exact 0 stopped a PML solve with a RuntimeError and the
other paths returned beta ~ 1e-6 roots as modes, depending on the last bits.
Lengths in micrometres; the slab of test_pml_modes.
"""
import numpy as np
import pytest

import galerkin.waveguide as waveguide
from galerkin.mode_coordinates import mode_coordinates
from galerkin.waveguide import STATIC_ROOT_TOL, solve_modes
from test_pml_modes import K0, slab_mesh

N_TARGET = 2.85
SIGMA = -(K0 * N_TARGET) ** 2


def slab(step=.05):
    mesh, eps = slab_mesh(step)
    walls = np.unique(np.concatenate([mesh.boundary[s] for s in ('left', 'right', 'top', 'bottom')]))
    coords = mode_coordinates(mesh, thickness=dict(left=1., right=1.), strength=3.)
    return mesh, eps, walls, coords


def recorded_eigs(monkeypatch, change=None, replay=None):
    """Record every ARPACK result of solve_modes; optionally change nu before it is used.

    With replay, ARPACK is not called again: the recorded (nu, vectors) are used.
    """
    calls = []
    original = waveguide.spla.eigs

    def eigs(*args, **kwargs):
        nu, vectors = (replay[0].copy(), replay[1].copy()) if replay else original(*args, **kwargs)
        if change is not None:
            nu = change(nu.copy())
        calls.append((nu, vectors))
        return nu, vectors
    monkeypatch.setattr(waveguide.spla, "eigs", eigs)
    return calls


def static(nu):
    return np.abs(-(SIGMA + 1 / nu)) <= STATIC_ROOT_TOL * abs(SIGMA)


def exact_static_nu():
    """A float nu for which the code's beta^2 = -(sigma + 1/nu) is exactly 0.

    beta^2 grows with nu (d beta^2 / d nu = 1/nu^2), so a positive value steps nu down.
    """
    nu = -1 / SIGMA
    for _ in range(64):
        if -(SIGMA + 1 / nu) == 0:
            return nu
        nu = np.nextafter(nu, -np.inf if -(SIGMA + 1 / nu) > 0 else np.inf)
    raise AssertionError("no float nu gives beta^2 == 0 exactly for this sigma")


@pytest.mark.parametrize("path", ["real", "pml"])
def test_static_roots_are_the_nodal_family(monkeypatch, path):
    mesh, eps, walls, coords = slab()
    factors = coords.factors if path == "pml" else None
    calls = recorded_eigs(monkeypatch)
    n, space, *_ = solve_modes(mesh, eps, K0, N_TARGET, num_modes=24, pec_nodes=walls,
                               coordinate_factors=factors)
    nu, vectors = calls[0]
    found = static(nu)
    assert 0 < found.sum() < len(nu)  # this search reaches the family
    free = waveguide._free_dofs(mesh, space, walls, None)
    transverse = free < space.num_edges
    for j in np.flatnonzero(found):
        v = vectors[:, j]
        assert np.linalg.norm(v[transverse]) <= 1e-6 * np.linalg.norm(v)
    assert len(n) == len(nu) - found.sum()
    assert np.all(np.abs(n) > 1e-5 * N_TARGET)


@pytest.mark.parametrize("path", ["real", "lossy", "pml"])
def test_large_search_returns_no_static_root(path):
    mesh, eps, walls, coords = slab()
    kwargs = dict(pec_nodes=walls)
    if path == "lossy":
        eps = eps - .01j
    if path == "pml":
        kwargs["coordinate_factors"] = coords.factors
    few, *_ = solve_modes(mesh, eps, K0, N_TARGET, num_modes=10, **kwargs)
    many, *_ = solve_modes(mesh, eps, K0, N_TARGET, num_modes=24, **kwargs)
    assert np.all(np.abs(many) > 1e-5 * N_TARGET)
    # The roots nearer the target than the static family are the same modes.
    for value in few:
        assert np.min(np.abs(many - value)) <= 1e-9 * abs(value)


def test_exactly_zero_static_root_is_not_an_error(monkeypatch):
    mesh, eps, walls, coords = slab()
    kwargs = dict(pec_nodes=walls, coordinate_factors=coords.factors)
    first = recorded_eigs(monkeypatch)
    reference, *_ = solve_modes(mesh, eps, K0, N_TARGET, num_modes=16, **kwargs)
    exact = exact_static_nu()

    def to_exact(nu):
        found = static(nu)
        assert found.any()
        nu[found] = exact  # what exact arithmetic gives for these roots
        return nu
    # The same ARPACK result, with the static roots exactly 0 (the old RuntimeError).
    recorded_eigs(monkeypatch, to_exact, replay=first[0])
    n, *_ = solve_modes(mesh, eps, K0, N_TARGET, num_modes=16, **kwargs)
    np.testing.assert_array_equal(n, reference)


def test_nonfinite_root_is_still_an_error(monkeypatch):
    mesh, eps, walls, coords = slab()

    def to_zero_nu(nu):
        nu[-1] = 0
        return nu
    recorded_eigs(monkeypatch, to_zero_nu)
    with np.errstate(divide="ignore", invalid="ignore"), pytest.raises(RuntimeError, match="nonfinite propagation root"):
        solve_modes(mesh, eps, K0, N_TARGET, num_modes=6, pec_nodes=walls, coordinate_factors=coords.factors)
