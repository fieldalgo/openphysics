# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""M3-prep: Nedelec edge elements on a PEC waveguide cross-section.

The point of the milestone is not just that edge elements are accurate, but that
nodal vector elements are structurally wrong: they invent eigenvalues between
the physical ones. Both halves are graded here.
"""

import numpy as np
import pytest
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from galerkin import (Mesh, rectangle_mesh, EdgeSpace, assemble_curlcurl,
                      assemble_edge_mass, assemble_mass, eval_edge_field)
from conftest import assert_second_order

A_WG, B_WG = 1.0, 0.5


@pytest.mark.parametrize("seed", [0, 17, 42])
def test_edge_numbering_and_physical_orientation_after_mesh_reordering(seed):
    mesh = rectangle_mesh(A_WG, B_WG, 5, 3)
    rng = np.random.default_rng(seed)
    nodes = rng.permutation(mesh.num_nodes)
    inverse = np.argsort(nodes)
    triangles = inverse[mesh.triangles[rng.permutation(mesh.num_triangles)]]
    # Cycle local vertices without changing their physical orientation.
    for triangle in triangles:
        triangle[:] = np.roll(triangle, rng.integers(3))
    mesh = Mesh(mesh.nodes[nodes], triangles, {})
    space = EdgeSpace(mesh)
    expected = sorted({tuple(sorted((int(t[i]), int(t[(i + 1) % 3]))))
                       for t in mesh.triangles for i in range(3)})
    np.testing.assert_array_equal(space.edges, expected)
    for triangle, edge_ids in zip(mesh.triangles, space.tri_edges):
        for opposite, edge_id in enumerate(edge_ids):
            endpoints = sorted(np.delete(triangle, opposite))
            np.testing.assert_array_equal(space.edges[edge_id], endpoints)
    # The circulation of grad(2x - 3y) must reconstruct the same constant field
    # regardless of global node ids, triangle order and local edge directions.
    potential = mesh.nodes @ np.array([2.0, -3.0])
    dofs = potential[space.edges[:, 1]] - potential[space.edges[:, 0]]
    field = eval_edge_field(space, dofs)
    np.testing.assert_allclose(field, np.tile([2.0, -3.0], (mesh.num_triangles, 1)), atol=1e-13)
    np.testing.assert_allclose(assemble_curlcurl(space) @ dofs, 0, atol=1e-10)


def test_empty_edge_space_has_valid_empty_maps():
    mesh = Mesh(np.empty((0, 2)), np.empty((0, 3), dtype=int), {})
    space = EdgeSpace(mesh)
    assert space.edges.shape == (0, 2)
    assert space.tri_edges.shape == space.signs.shape == (0, 3)
    assert space.boundary_edge_ids().size == 0


def _nedelec(nx, ny, k=10, sigma=60.0):
    mesh = rectangle_mesh(A_WG, B_WG, nx, ny)
    space = EdgeSpace(mesh)
    S, M = assemble_curlcurl(space), assemble_edge_mass(space)
    nodes = np.unique(np.concatenate([mesh.boundary[t] for t in mesh.boundary]))
    free = np.setdiff1d(np.arange(space.num_edges),
                        space.boundary_edge_ids(nodes))
    S, M = S[free][:, free], M[free][:, free]
    vals = spla.eigsh(S, k=k, M=M, sigma=sigma, which="LM",
                      v0=np.ones(S.shape[0]),
                      ncv=min(S.shape[0], max(4 * k, 40)), maxiter=20000,
                      return_eigenvectors=False)
    return mesh, space, free, np.sort(vals)


def test_cutoffs_match_the_analytic_spectrum(refsol):
    exact = refsol.metallic.rect_waveguide_cutoffs(A_WG, B_WG, n_max=4)
    _, _, _, vals = _nedelec(60, 30, k=14, sigma=60.0)
    got = vals[vals > 1.0]
    for (kc2, label), v in zip(exact[:6], got[:6]):
        rel = abs(v - kc2) / kc2
        assert rel < 1e-3, f"{label}: {v:.6f} vs {kc2:.6f} ({rel:.2e})"


def test_te10_converges_at_second_order(refsol):
    te10 = refsol.metallic.rect_waveguide_cutoffs(A_WG, B_WG, n_max=2)[0][0]
    errors = []
    for nx in (10, 20, 40):
        _, _, _, vals = _nedelec(nx, nx // 2, k=6, sigma=12.0)
        errors.append(abs(np.sort(vals[vals > 1.0])[0] - te10) / te10)
    assert_second_order(errors, name="TE10 cutoff")


def test_boundary_edges_are_exactly_the_topological_boundary():
    """'Both endpoints on the boundary' is a different set: the diagonal of a
    corner cell joins two boundary nodes while running through the interior."""
    for nx, ny in ((6, 4), (30, 15)):
        mesh = rectangle_mesh(A_WG, B_WG, nx, ny)
        space = EdgeSpace(mesh)
        nodes = np.unique(np.concatenate([mesh.boundary[t] for t in mesh.boundary]))
        count = np.bincount(space.tri_edges.ravel(), minlength=space.num_edges)
        assert set(space.boundary_edge_ids(nodes).tolist()) == \
            set(np.where(count == 1)[0].tolist())


def test_nodal_vector_elements_produce_spurious_modes(refsol):
    """The deliberately wrong discretization, kept as a permanent counter-example."""
    exact = [k for k, _ in refsol.metallic.rect_waveguide_cutoffs(
        A_WG, B_WG, n_max=6, include_tm=True)]
    nx, ny = 40, 20
    mesh = rectangle_mesh(A_WG, B_WG, nx, ny)
    p = mesh.nodes[mesh.triangles]
    x, y = p[:, :, 0], p[:, :, 1]
    b = np.stack([y[:, 1]-y[:, 2], y[:, 2]-y[:, 0], y[:, 0]-y[:, 1]], axis=1)
    c = np.stack([x[:, 2]-x[:, 1], x[:, 0]-x[:, 2], x[:, 1]-x[:, 0]], axis=1)
    area = np.abs(0.5*(b[:, 0]*c[:, 1] - b[:, 1]*c[:, 0]))
    gx, gy = b/(2*area[:, None]), c/(2*area[:, None])

    def gradmat(ga, gb):
        Ke = area[:, None, None]*ga[:, :, None]*gb[:, None, :]
        t = mesh.triangles
        return sp.coo_matrix((Ke.ravel(), (np.repeat(t, 3, axis=1).ravel(),
                                           np.tile(t, (1, 3)).ravel())),
                             shape=(mesh.num_nodes,)*2).tocsr()

    S = sp.bmat([[gradmat(gy, gy), -gradmat(gy, gx)],
                 [-gradmat(gx, gy), gradmat(gx, gx)]]).tocsr()
    Mn = assemble_mass(mesh)
    M2 = sp.block_diag([Mn, Mn]).tocsr()
    n = mesh.num_nodes
    fixed = np.unique(np.concatenate([
        mesh.boundary["top"], mesh.boundary["bottom"],
        n + mesh.boundary["left"], n + mesh.boundary["right"]]))
    free = np.setdiff1d(np.arange(2*n), fixed)
    vals = spla.eigsh(S[free][:, free], k=14, M=M2[free][:, free], sigma=60.0,
                      which="LM", v0=np.ones(len(free)),
                      ncv=min(len(free), 60), maxiter=20000,
                      return_eigenvectors=False)
    vals = np.sort(vals[vals > 1.0])
    spurious = [v for v in vals
                if min(abs(v - e) / e for e in exact) > 0.02]
    assert len(spurious) >= 3, (
        "nodal vector elements are supposed to fail here; if they no longer do, "
        "the counter-example has stopped testing anything")
