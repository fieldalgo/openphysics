# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The vector search never asks ARPACK for the static beta^2 = 0 family (galerkin._waveguide_kernels).

P [x_t; x_z] = [x_t; -N^-1 G^T x_t] (N = K - k0^2 M on the free nodes) annihilates the family
[0, e_z], keeps every other eigenvector and commutes with the shift-invert operator; the search
runs on P op from P(ones) and keeps the roots nearer the shift than the family. Near a TM cutoff of
the PEC box N is nearly singular: below STATIC_DEFLATION_MIN_CUTOFF_DISTANCE (1e-5, the relative
distance of k0^2 from it) the search is not deflated, with a StaticFamilyNearCutoffWarning.
Lengths in micrometres; the slab of test_pml_modes. Check P8 is registered for TM-cutoff distances
1e-2 to 1e-8: on the real path every one is built; on the PML path every nodal eigenvalue is complex
(the nearest Im/Re ~1e-3 on this slab), so a real k0^2 comes no nearer than about 1e-3 and only
1e-2 is built there.
"""
import warnings

import numpy as np
import pytest
import scipy.sparse.linalg as spla

import galerkin._waveguide_kernels as waveguide
from galerkin.kernels import solve_modes
from test_waveguide_static_roots import N_TARGET, slab, undeflated
from test_pml_modes import K0


def pencil(mesh, eps, walls, factors, k0=K0, n_target=N_TARGET):
    A, B, space, M = waveguide._assembled(mesh, eps, k0, 1.0, None, factors)
    free = waveguide._free_dofs(mesh, space, walls, None)
    A, B = A[free][:, free].tocsc(), B[free][:, free].tocsc()
    sigma = -(k0 * n_target) ** 2
    lu = spla.splu((A - sigma * B).tocsc())
    return A, B, space, M, free, sigma, lu


def free_vector(space, free, et, ez, beta):
    x = np.concatenate([et * beta, ez])
    return x[free]


@pytest.mark.parametrize("path", ["real", "pml"])
def test_the_projector_commutes_with_the_search_and_keeps_its_modes(path):
    mesh, eps, walls, coords = slab()
    factors = coords.factors if path == "pml" else None
    A, B, space, M, free, sigma, lu = pencil(mesh, eps, walls, factors)
    project = waveguide._static_projector(B, free, space.num_edges, K0, M)
    op = lambda x: lu.solve(B @ x)          # noqa: E731
    rng = np.random.default_rng(5)
    for _ in range(3):
        x = rng.standard_normal(len(free)).astype(lu.L.dtype)
        left, right = project(op(x)), op(project(x))
        assert np.linalg.norm(left - right) <= 1e-10 * np.linalg.norm(left)
        assert np.linalg.norm(project(project(x)) - project(x)) <= 1e-10 * np.linalg.norm(project(x))
    n, space, et, ez = solve_modes(mesh, eps, K0, N_TARGET, num_modes=6, pec_nodes=walls, coordinate_factors=factors)
    assert len(n) > 0
    for i in range(len(n)):
        x = free_vector(space, free, et[i], ez[i], n[i] * K0)
        # P is linear; on the real path it acts on real vectors, and a mode carries a phase
        px = project(x) if np.iscomplexobj(lu.L.dtype.type(0)) else project(x.real) + 1j * project(x.imag)
        assert np.linalg.norm(px - x) <= 1e-10 * np.linalg.norm(x)


def nearest_cutoff(mesh, eps, walls, factors):
    """The nodal eigenvalue mu of K e = mu M e (free nodes) nearest K0^2."""
    _, B0, space, M = waveguide._assembled(mesh, eps, 0.0, 1.0, None, factors)
    free = waveguide._free_dofs(mesh, space, walls, None)
    nodes = free >= space.num_edges
    ids = free[nodes] - space.num_edges
    K = B0[free][:, free][nodes][:, nodes].tocsc()
    Mz = M.tocsr()[ids][:, ids].tocsc()
    lu = spla.splu((K - K0 ** 2 * Mz).tocsc())
    theta = spla.eigs(spla.LinearOperator(K.shape, matvec=lambda x: lu.solve(Mz @ x), dtype=lu.L.dtype),
                      k=1, which="LM", v0=np.ones(K.shape[0]))[0][0]
    return K0 ** 2 + 1 / theta


def residuals(mesh, eps, walls, factors, k0, n, space, et, ez):
    A, B, *_ = pencil(mesh, eps, walls, factors, k0=k0)
    free = waveguide._free_dofs(mesh, space, walls, None)
    out = []
    for i in range(len(n)):
        x, lam = free_vector(space, free, et[i], ez[i], n[i] * k0), -(n[i] * k0) ** 2
        out.append(np.linalg.norm(A @ x - lam * (B @ x)) / np.linalg.norm(lam * (B @ x)))
    return np.array(out)


CASES = [("real", d) for d in (1e-2, 1e-4, 1e-6, 1e-8)] + [("pml", 1e-2)]


@pytest.mark.parametrize("path,distance", CASES)
def test_near_a_tm_cutoff(monkeypatch, path, distance):
    """P8: deflated at a cutoff distance >= 1e-5, with the undeflated search's values within 1e-12
    and residuals <= 1e-9; undeflated below it, bit for bit, with the warning; the estimate of the
    distance within a factor 2 below 1e-3."""
    mesh, eps, walls, coords = slab()
    factors = coords.factors if path == "pml" else None
    mu = nearest_cutoff(mesh, eps, walls, factors)
    k0 = float(np.sqrt(mu.real / (1 + distance)))
    true = abs(mu - k0 ** 2) / k0 ** 2
    A, B, space, M, free, sigma, lu = pencil(mesh, eps, walls, factors, k0=k0)
    nodes = free >= space.num_edges
    N = spla.splu(B[nodes][:, nodes].tocsc())
    estimate = waveguide._cutoff_distance(B[nodes][:, nodes].tocsc(), N,
                                          (k0 ** 2 * M.tocsr()[free[nodes] - space.num_edges][:, free[nodes] - space.num_edges]).tocsc())
    print(f"{path} registered {distance:g}: true {true:.3g}, estimate {estimate:.3g}")
    if true < 1e-3:
        assert true / 2 <= estimate <= 2 * true
    kwargs = dict(num_modes=6, pec_nodes=walls, coordinate_factors=factors)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        n, space, et, ez = solve_modes(mesh, eps, k0, N_TARGET, **kwargs)
    warned = [w for w in caught if issubclass(w.category, waveguide.StaticFamilyNearCutoffWarning)]
    with monkeypatch.context() as m:
        undeflated(m)
        with pytest.warns(waveguide.StaticFamilyNearCutoffWarning):
            ref = solve_modes(mesh, eps, k0, N_TARGET, **kwargs)
    if true >= waveguide.STATIC_DEFLATION_MIN_CUTOFF_DISTANCE:
        assert not warned
        assert len(n) == len(ref[0]) > 0
        np.testing.assert_allclose(n, ref[0], rtol=1e-12, atol=0)
        res = residuals(mesh, eps, walls, factors, k0, n, space, et, ez)
        print(f"  residual max {res.max():.2g}")
        assert res.max() <= 1e-9
    else:
        assert len(warned) == 1
        np.testing.assert_array_equal(n, ref[0])
        np.testing.assert_array_equal(et, ref[2])
        np.testing.assert_array_equal(ez, ref[3])
