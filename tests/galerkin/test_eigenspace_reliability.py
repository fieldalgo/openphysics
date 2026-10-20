# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Span, not just eigenvalue count or individual residual, must survive output."""

import numpy as np
import pytest
from scipy.optimize import linear_sum_assignment

from galerkin import disk_mesh, solve_modes
from galerkin.assembly import assemble_mass
from galerkin.edge import assemble_edge_mass
import galerkin.waveguide as waveguide
from eigenspace_reliability_oracle import fiber_electric, sampled_spans, span_error


def fixture(scale=1):
    mesh = disk_mesh((4, 8, 24), (4*scale, 4*scale, 16*scale), 32*scale)
    return mesh, mesh.by_region([1.45**2, 1.44**2, 1.44**2])


def gram(space, et, ez):
    return (et.conj() @ (assemble_edge_mass(space, 1.) @ et.T)
            + ez.conj() @ (assemble_mass(space.mesh, 1.) @ ez.T))


def normalized_gram(space, et, ez):
    g = gram(space, et, ez)
    return g / np.sqrt(np.outer(g.diagonal().real, g.diagonal().real))


def pencil(mesh, eps, space):
    a, b, _ = waveguide.assemble_mode_system(mesh, eps, 2*np.pi/1.5, space=space)
    nodes = mesh.boundary['outer']
    fixed = np.r_[space.boundary_edge_ids(nodes), space.num_edges+nodes]
    free = np.setdiff1d(np.arange(a.shape[0]), fixed)
    return a[free][:, free], b[free][:, free], free


@pytest.mark.parametrize('wavelength', [1.50, 1.55, 1.60])
@pytest.mark.parametrize('repeat', range(2))
def test_eigenspace_reliability_fiber_rank_and_pencil(wavelength, repeat):
    mesh, eps = fixture()
    k0 = 2*np.pi/wavelength
    neff, space, et, ez = solve_modes(mesh, eps, k0, 1.45, 10)
    assert np.linalg.matrix_rank(np.c_[et[:2], ez[:2]]) == 2
    # This checks retained rank, not orthogonality: ARPACK's degenerate basis
    # need not be orthogonal in the physical positive electric-L2 metric.
    assert np.linalg.eigvalsh(normalized_gram(space, et[:2], ez[:2]))[0] > 1e-8
    a, b, _ = waveguide.assemble_mode_system(mesh, eps, k0, space=space)
    nodes = mesh.boundary['outer']
    fixed = np.r_[space.boundary_edge_ids(nodes), space.num_edges+nodes]
    free = np.setdiff1d(np.arange(a.shape[0]), fixed)
    for n, t, z in zip(neff, et, ez):
        beta = k0*n
        x = np.r_[beta*t, z][free]
        ax, bx = a[free][:, free]@x, b[free][:, free]@x
        residual = np.linalg.norm(ax+beta**2*bx)/(np.linalg.norm(ax)+beta**2*np.linalg.norm(bx))
        assert residual < 1e-9


def test_eigenspace_reliability_phase_order_and_complex_basis(monkeypatch):
    mesh, eps = fixture()
    original = waveguide.spla.eigs
    captured = {}

    def capture(*args, **kwargs):
        nu, vecs = original(*args, **kwargs)
        captured.update(nu=nu.copy(), vecs=vecs.copy())
        return nu, vecs

    monkeypatch.setattr(waveguide.spla, 'eigs', capture)
    neff, space, et, ez = solve_modes(mesh, eps, 2*np.pi/1.5, 1.45, 10)
    a, b, free = pencil(mesh, eps, space)
    beta = 2*np.pi/1.5*neff
    x = np.concatenate((et*beta[:, None], ez), axis=1)[:, free].T
    # Equal eigenvalues have no unique column order: sorting lambda ascending
    # and sorting -lambda descending can reverse ties. Match actual columns
    # bijectively, then require preservation up to phase, not only equal spans.
    vectors = captured['vecs']
    overlap = abs(vectors.conj().T @ x)
    overlap /= np.linalg.norm(vectors, axis=0)[:, None]*np.linalg.norm(x, axis=0)[None, :]
    raw_ids, output_ids = linear_sum_assignment(-overlap)
    assert len(output_ids) == x.shape[1] == vectors.shape[1]
    order = np.empty(x.shape[1], dtype=int)
    order[output_ids] = raw_ids
    raw = vectors[:, order]
    expected_beta2 = -(-(1.45*2*np.pi/1.5)**2+1/captured['nu'][order]).real
    np.testing.assert_allclose(beta**2, expected_beta2, rtol=1e-13, atol=0)
    for u, v in zip(x.T, raw.T):
        c = np.vdot(v, u)/np.vdot(v, v)
        np.testing.assert_allclose(abs(c), 1.0, rtol=1e-12, atol=0)
        assert np.linalg.norm(u-c*v) < 1e-12*np.linalg.norm(u)

    # Build an exact common-eigenvalue input fixture from the observed pair's
    # span. Only this test double mixes the pair; production never does.
    q, _ = np.linalg.qr(raw[:, :2])
    unitary = np.array([[1, 1j], [1j, 1]])/np.sqrt(2)
    pair = q@unitary
    for seed in range(3):
        rng = np.random.default_rng(seed)
        nu = captured['nu'].copy()
        vectors = captured['vecs'].copy()
        nu[order[:2]] = np.mean(nu[order[:2]]).real
        vectors[:, order[:2]] = pair*np.exp(1j*rng.uniform(-np.pi, np.pi, 2))
        permutation = rng.permutation(len(nu))

        def supplied(*args, **kwargs):
            return nu[permutation], vectors[:, permutation]

        monkeypatch.setattr(waveguide.spla, 'eigs', supplied)
        n, s, t, z = solve_modes(mesh, eps, 2*np.pi/1.5, 1.45, 10)
        y = np.c_[t[:2]*(2*np.pi/1.5*n[:2, None]), z[:2]][:, free].T
        assert np.linalg.matrix_rank(y) == 2
        assert np.linalg.norm(y-q@(q.conj().T@y)) < 1e-12*np.linalg.norm(y)
        assert np.linalg.eigvalsh(normalized_gram(s, t[:2], z[:2]))[0] > 0.9
        for j in range(2):
            lam = -(2*np.pi/1.5*n[j])**2
            ay, by = a@y[:, j], b@y[:, j]
            assert np.linalg.norm(ay-lam*by)/(np.linalg.norm(ay)+abs(lam)*np.linalg.norm(by)) < 1e-9


def test_eigenspace_reliability_analytic_oracle_interface_and_maxwell(refsol):
    mode = next(m for m in refsol.fiber.vector_modes(4, 1.45, 1.44, 1.5) if m.label == 'HE11')
    # At phi=0 the Cartesian components are Er, Ephi, Ez.
    sides = fiber_electric(np.array([[4-1e-8, 0.], [4+1e-8, 0.]]), mode)
    assert np.allclose(sides[0, 1:], sides[1, 1:], rtol=1e-7, atol=1e-8)
    assert np.allclose(1.45**2*sides[0, 0], 1.44**2*sides[1, 0], rtol=1e-7)
    points = np.array([[1.3, .7], [6., 1.1]])
    h = 1e-4
    e = fiber_electric(points, mode)
    derivatives, laplacian = [], np.zeros_like(e)
    for axis in range(2):
        step = np.eye(2)[axis]*h
        plus, minus = fiber_electric(points+step, mode), fiber_electric(points-step, mode)
        derivatives.append((plus-minus)/(2*h))
        laplacian += (plus-2*e+minus)/h**2
    beta = 2*np.pi/1.5*mode.neff
    divergence = derivatives[0][:, 0]+derivatives[1][:, 1]-1j*beta*e[:, 2]
    assert np.linalg.norm(divergence)/np.linalg.norm(e) < 1e-7
    q2 = (2*np.pi/1.5)**2*np.array([1.45**2, 1.44**2])-beta**2
    assert np.linalg.norm(laplacian+q2[:, None, None]*e)/np.linalg.norm(e) < 1e-6


@pytest.mark.slow
def test_eigenspace_reliability_analytic_degenerate_span_converges(refsol):
    mode = next(m for m in refsol.fiber.vector_modes(4, 1.45, 1.44, 1.5) if m.label == 'HE11')
    errors = []
    for scale in (1, 2, 3):
        mesh, eps = fixture(scale)
        neff, space, et, ez = solve_modes(mesh, eps, 2*np.pi/1.5, 1.45, 10)
        f, exact = sampled_spans(mesh, space, et[:2], ez[:2], mode, order=6)
        assert np.linalg.matrix_rank(exact) == 2
        g = normalized_gram(space, et[:2], ez[:2])
        assert np.linalg.eigvalsh(g)[0] > 1e-8
        error = span_error(f, exact)
        f4, exact4 = sampled_spans(mesh, space, et[:2], ez[:2], mode, order=4)
        assert abs(error-span_error(f4, exact4)) < 1e-3*error
        errors.append(error)
        # +/-l analytic basis rotation/complex phases cannot change the span.
        u = np.array([[1, 1j], [1j, 1]])/np.sqrt(2)
        assert abs(error-span_error(f, exact@u)) < 1e-11
    # Lowest-order edge-field convergence, separate from eigenvalue accuracy.
    assert np.all(np.diff(errors) < 0)
    assert np.log(errors[-2]/errors[-1])/np.log(3/2) > 0.8
