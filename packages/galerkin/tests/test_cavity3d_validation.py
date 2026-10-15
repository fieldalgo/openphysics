# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent gates for the published vacuum PEC box contract.

No solver implementation or analytic oracle is imported from examples.
Run from the repository root with pytest, or with unittest and package roots on
PYTHONPATH. API absence is an error, never a skip or an oracle-only pass.
"""
from itertools import combinations, product
import unittest

import numpy as np
import scipy.linalg as la
import scipy.sparse as sp

import galerkin
from refsol.metallic import rect_cavity_resonances

C0 = 299792458.0
LOCAL_EDGES = tuple(combinations(range(4), 2))


def oracle(sides, cap=4):
    """Amplitude counting, independently cross-checked against TE/TM refsol."""
    values = []
    for indices in product(range(cap + 1), repeat=3):
        positive = sum(i > 0 for i in indices)
        multiplicity = {0: 0, 1: 0, 2: 1, 3: 2}[positive]
        value = sum((np.pi * i / side)**2 for i, side in zip(indices, sides))
        values.extend([value] * multiplicity)
    values = np.sort(values)
    reference = np.sort([value for value, _ in
                         rect_cavity_resonances(*sides, n_max=cap)])
    np.testing.assert_allclose(values, reference, rtol=1e-13, atol=0)
    return values


def clusters(sides, take):
    groups = []
    for value in oracle(sides):
        if groups and abs(value / groups[-1][0] - 1) < 1e-12:
            groups[-1][1] += 1
        else:
            groups.append([value, 1])
    # Every omitted index is above the selected comparison band.
    assert (5 * np.pi / max(sides))**2 > groups[take - 1][0]
    return groups[:take]


def independent_topology(mesh):
    tets = np.asarray(mesh.tets)
    local = np.stack([tets[:, pair] for pair in LOCAL_EDGES], axis=1)
    pairs = np.sort(local, axis=2)
    edges, inverse = np.unique(pairs.reshape(-1, 2), axis=0,
                               return_inverse=True)
    signs = np.where(local[:, :, 0] == pairs[:, :, 0], 1, -1)
    tet_edges = inverse.reshape(-1, 6)
    owners = {}
    for ti, tet in enumerate(tets):
        for local_face in combinations(range(4), 3):
            face = tuple(sorted(tet[list(local_face)]))
            owners.setdefault(face, []).append(ti)
    boundary = [(face, adjacent[0]) for face, adjacent in owners.items()
                if len(adjacent) == 1]
    assert all(len(adjacent) in (1, 2) for adjacent in owners.values())
    lookup = {tuple(edge): i for i, edge in enumerate(edges)}
    pec = np.array(sorted({lookup[tuple(pair)] for face, _ in boundary
                           for pair in combinations(face, 2)}), dtype=int)
    return edges, tet_edges, signs, boundary, pec


def vertex_fields(mesh, coefficients, tet_edges, signs):
    """Whitney reconstruction using independent geometry at all tet vertices."""
    points = np.asarray(mesh.nodes)[mesh.tets]
    matrix = points[:, 1:] - points[:, :1]
    gradients = np.empty((len(points), 4, 3))
    gradients[:, 1:] = np.linalg.inv(matrix).transpose(0, 2, 1)
    gradients[:, 0] = -gradients[:, 1:].sum(axis=1)
    basis = np.zeros((len(points), 4, 6, 3))
    for ei, (i, j) in enumerate(LOCAL_EDGES):
        basis[:, i, ei] += gradients[:, j]
        basis[:, j, ei] -= gradients[:, i]
    local = coefficients[tet_edges] * signs[:, :, None]
    return np.einsum("tqed,tek->tqdk", basis, local)


def check_result(result, expected_count):
    mesh, space = result.mesh, result.space
    q = np.asarray(result.edge_coefficients)
    values = np.asarray(result.eigenvalues_m2)
    frequencies = np.asarray(result.frequencies_hz)
    assert q.shape == (space.num_edges, expected_count)
    assert values.shape == frequencies.shape == (expected_count,)
    assert np.isfinite(q).all() and np.isfinite(values).all()
    assert (values > 0).all() and (np.diff(values) >= 0).all()
    assert result.requested_modes == expected_count
    assert result.search == "near_target"
    np.testing.assert_allclose(frequencies, C0 * np.sqrt(values) / (2 * np.pi),
                               rtol=1e-12, atol=0)

    edges, tet_edges, signs, faces, pec = independent_topology(mesh)
    np.testing.assert_array_equal(space.edges, edges)
    np.testing.assert_array_equal(space.tet_edges, tet_edges)
    np.testing.assert_array_equal(space.signs, signs)
    np.testing.assert_array_equal(np.sort(result.pec_edge_ids), pec)
    assert np.max(np.abs(q)) > 0
    assert np.max(np.abs(q[pec])) / np.max(np.abs(q)) <= 1e-12
    free = np.setdiff1d(np.arange(len(edges)), pec)
    mass = galerkin.assemble_edge_mass_3d(space)
    stiff = galerkin.assemble_curlcurl_3d(space)
    u = q[free]
    mf = mass[free][:, free]
    kf = stiff[free][:, free]
    ku, mu = kf @ u, mf @ u
    residuals = np.linalg.norm(ku - mu * values, axis=0) / (
        np.linalg.norm(ku, axis=0) + abs(values) * np.linalg.norm(mu, axis=0))
    assert np.max(residuals) <= 1e-9, residuals
    # The returned diagnostics must match the independently recomputed ones to
    # numerical roundoff, rather than merely containing a plausible small value.
    np.testing.assert_allclose(result.relative_residuals, residuals,
                               rtol=1e-3, atol=1e-12)
    assert np.max(abs(q.conj().T @ (mass @ q) - np.eye(expected_count))) <= 1e-8

    boundary_nodes = np.unique([node for face, _ in faces for node in face])
    interior = np.setdiff1d(np.arange(len(mesh.nodes)), boundary_nodes)
    row = np.arange(len(edges))
    incidence = sp.coo_matrix(
        (np.r_[-np.ones(len(edges)), np.ones(len(edges))],
         (np.r_[row, row], np.r_[edges[:, 0], edges[:, 1]])),
        shape=(len(edges), len(mesh.nodes))).tocsr()[free][:, interior]
    if len(interior):
        energy = np.asarray(incidence.multiply(mf @ incidence).sum(axis=0)).ravel()
        norm_u = np.real(np.sum(u.conj() * mu, axis=0))
        coupling = abs(incidence.conj().T @ mu) / np.sqrt(energy[:, None] * norm_u)
        assert np.max(coupling) <= 1e-9, np.max(coupling)

    field = vertex_fields(mesh, q, tet_edges, signs)
    np.testing.assert_allclose(np.asarray(result.electric_field),
                               field.mean(axis=1).transpose(2, 0, 1),
                               rtol=1e-12, atol=1e-12 * np.max(abs(field)))
    scale = np.max(np.linalg.norm(field, axis=2))
    assert scale > 0
    trace = 0.
    for face, ti in faces:
        face_nodes = np.asarray(face)
        points = mesh.nodes[face_nodes]
        normal = np.cross(points[1] - points[0], points[2] - points[0])
        normal /= np.linalg.norm(normal)
        local_ids = [int(np.flatnonzero(mesh.tets[ti] == node)[0])
                     for node in face_nodes]
        samples = field[ti, local_ids].transpose(0, 2, 1)
        samples = np.concatenate([samples, samples.mean(axis=0, keepdims=True)])
        trace = max(trace, np.max(np.linalg.norm(
            np.cross(normal, samples), axis=-1)))
    assert trace / scale <= 1e-10, trace / scale
    return mass


class IndependentOracleValidation(unittest.TestCase):
    def test_amplitude_enumeration_and_cube_multiplicity(self):
        for sides in ((1., 1., 1.), (1., .8, .6)):
            self.assertEqual(len(oracle(sides)), 176)
        self.assertEqual([m for _, m in clusters((1., 1., 1.), 3)], [3, 2, 6])

    def test_small_generalized_kernel_and_boundary_endpoint_trap(self):
        for n in (2, 3, 4):
            mesh = galerkin.box_mesh(1., 1., 1., n, n, n)
            space = galerkin.EdgeSpace3D(mesh)
            edges, _, _, faces, pec = independent_topology(mesh)
            free = np.setdiff1d(np.arange(len(edges)), pec)
            k = galerkin.assemble_curlcurl_3d(space)[free][:, free]
            m = galerkin.assemble_edge_mass_3d(space)[free][:, free]
            values = la.eigvalsh(k.toarray(), m.toarray())
            self.assertFalse(np.any(values < -1e-9 * max(abs(values))))
            self.assertEqual(int(np.count_nonzero(abs(values) <=
                             1e-9 * max(abs(values)))), (n - 1)**3)
            boundary_nodes = np.unique([node for face, _ in faces for node in face])
            endpoints_on_wall = np.isin(edges[free], boundary_nodes).all(axis=1)
            self.assertTrue(np.any(endpoints_on_wall))


class PublishedCavityAPIValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        api = getattr(galerkin, "solve_cavity_box", None)
        if not callable(api):
            raise AssertionError(
                "Published solve_cavity_box API is absent from this source SHA; "
                "oracle passes do not establish product acceptance.")
        cls.solve = staticmethod(api)

    def test_explicit_search_and_cluster_metadata(self):
        result = self.solve((1., 1., 1.), (3, 3, 3), num_modes=2,
                            target_frequency_hz=C0 / np.sqrt(2))
        self.assertEqual(result.cluster_completeness, "not_certified")
        self.assertEqual(result.mode_count_policy, "exact_count_may_split_cluster")
        self.assertEqual(len(result.frequencies_hz), 2)

    def test_raw_fields_free_residual_gradient_and_pec(self):
        for sides in ((1., 1., 1.), (1., .8, .6)):
            target = C0 * np.sqrt(1.3 * oracle(sides)[0]) / (2 * np.pi)
            result = self.solve(sides, (4, 4, 4), num_modes=5,
                                target_frequency_hz=target)
            check_result(result, 5)

    def test_complete_clusters_and_fixed_convergence(self):
        for sides, take in (((1., 1., 1.), 3), ((1., .8, .6), 4)):
            groups = clusters(sides, take)
            count = sum(mult for _, mult in groups)
            target = C0 * np.sqrt(1.3 * groups[0][0]) / (2 * np.pi)
            errors, widths = [], []
            for n in (4, 8, 16):
                result = self.solve(sides, (n, n, n), num_modes=count,
                                    target_frequency_hz=target)
                check_result(result, count)
                values = result.eigenvalues_m2
                row, split, offset = [], [], 0
                for exact, mult in groups:
                    numerical = values[offset:offset + mult]
                    self.assertEqual(len(numerical), mult)
                    row.append(abs(numerical.mean() / exact - 1))
                    split.append(np.ptp(numerical) / exact)
                    if n == 16:
                        self.assertLess(np.max(abs(np.sqrt(numerical / exact) - 1)), .01)
                    offset += mult
                errors.append(row)
                widths.append(split)
            errors, widths = np.asarray(errors), np.asarray(widths)
            self.assertTrue(np.all(np.diff(errors, axis=0) < 0), errors)
            orders = np.log(errors[-2] / errors[-1]) / np.log(2)
            self.assertTrue(np.all(orders > 1.8), orders)
            for previous, current in zip(widths[-2], widths[-1]):
                if current >= 1e-10:
                    self.assertGreater(np.log(previous / current) / np.log(2), 1.8)

    def test_geometric_scaling_and_degenerate_subspace(self):
        sides = np.ones(3)
        target = C0 / np.sqrt(2)
        base = self.solve(sides, (4, 4, 4), num_modes=3,
                          target_frequency_hz=target)
        mass = check_result(base, 3)
        stiff = galerkin.assemble_curlcurl_3d(base.space)
        for scale in (1e-6, 1e3):
            result = self.solve(sides * scale, (4, 4, 4), num_modes=3,
                                target_frequency_hz=target / scale)
            check_result(result, 3)
            np.testing.assert_allclose(result.frequencies_hz * scale,
                                       base.frequencies_hz, rtol=1e-9, atol=0)
            mapped = result.edge_coefficients * np.sqrt(scale)
            overlap = base.edge_coefficients.conj().T @ (mass @ mapped)
            self.assertGreaterEqual(np.linalg.svd(overlap, compute_uv=False).min(),
                                    1 - 1e-7)
            scaled_m = galerkin.assemble_edge_mass_3d(result.space) / scale
            scaled_k = galerkin.assemble_curlcurl_3d(result.space) * scale
            self.assertLessEqual(abs(scaled_m - mass).max() / abs(mass).max(), 1e-11)
            self.assertLessEqual(abs(scaled_k - stiff).max() / abs(stiff).max(), 1e-11)


if __name__ == "__main__":
    unittest.main()
