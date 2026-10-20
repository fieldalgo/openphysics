# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent geometric/topological checks on the mesh returned by the API.

These checks do not reproduce the alternating mesh construction. Volume and
pairwise tetrahedron separation establish cell partitions; oriented face pairing
and connectivity check conformity. Odd/even subdivision counts are included.
"""
from itertools import combinations
import unittest

import numpy as np
import scipy.linalg as la
import scipy.sparse as sp

import galerkin

SIDES = np.array((1., .8, .6))
FACES = ((1, 2, 3), (0, 3, 2), (0, 1, 3), (0, 2, 1))
EDGES = tuple(combinations(range(4), 2))


def face_owners(tets):
    result = {}
    for ti, tet in enumerate(tets):
        for order in FACES:
            vertices = [int(tet[i]) for i in order]
            inversions = sum(vertices[i] > vertices[j]
                             for i in range(3) for j in range(i + 1, 3))
            result.setdefault(tuple(sorted(vertices)), []).append((ti, (-1)**inversions))
    return result


def interiors_separated(a, b):
    """Separating-axis test: tetrahedra may touch, but interiors cannot overlap."""
    ea = np.array([a[j] - a[i] for i, j in EDGES])
    eb = np.array([b[j] - b[i] for i, j in EDGES])
    axes = [np.cross(tet[j] - tet[i], tet[k] - tet[i])
            for tet in (a, b) for i, j, k in combinations(range(4), 3)]
    axes.extend(np.cross(ea[:, None, :], eb[None, :, :]).reshape(-1, 3))
    axes = np.asarray(axes)
    norm = np.linalg.norm(axes, axis=1)
    axes = axes[norm > 1e-12] / norm[norm > 1e-12, None]
    pa, pb = a @ axes.T, b @ axes.T
    overlap = np.minimum(pa.max(axis=0), pb.max(axis=0)) - np.maximum(
        pa.min(axis=0), pb.min(axis=0))
    return bool(np.any(overlap <= 1e-11))


class IndependentReturnedCavityMeshValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = []
        fundamental = np.pi**2 * sum(sorted(1 / SIDES**2)[:2])
        for cells in ((2, 2, 2), (3, 3, 3), (4, 3, 2)):
            result = galerkin.solve_cavity_box(
                SIDES, cells, num_modes=3,
                target_frequency_hz=299792458 * np.sqrt(1.3 * fundamental)/(2*np.pi))
            cls.results.append((np.asarray(cells), result))

    def test_counts_volume_oriented_faces_connectivity_and_six_walls(self):
        for cells, result in self.results:
            with self.subTest(cells=cells.tolist()):
                mesh = result.mesh
                self.assertEqual(len(mesh.nodes), int(np.prod(cells + 1)))
                self.assertEqual(len(mesh.tets), 6 * int(np.prod(cells)))
                self.assertEqual(len(np.unique(mesh.nodes, axis=0)), len(mesh.nodes))
                grid_coordinates = mesh.nodes / SIDES * cells
                np.testing.assert_allclose(grid_coordinates, np.rint(grid_coordinates),
                                           rtol=0, atol=1e-12)
                self.assertTrue(np.all(mesh.nodes >= 0))
                self.assertTrue(np.all(mesh.nodes <= SIDES + 1e-14))
                points = mesh.nodes[mesh.tets]
                volumes = np.linalg.det(points[:, 1:] - points[:, :1]) / 6
                np.testing.assert_allclose(volumes, SIDES.prod()/np.prod(cells)/6,
                                           rtol=1e-12, atol=0)
                self.assertAlmostEqual(volumes.sum(), SIDES.prod(), places=12)
                owners = face_owners(mesh.tets)
                adjacency = [set() for _ in mesh.tets]
                wall_counts = np.zeros((3, 2), dtype=int)
                boundary_faces = []
                for face, adjacent in owners.items():
                    self.assertIn(len(adjacent), (1, 2))
                    if len(adjacent) == 2:
                        self.assertEqual(sum(sign for _, sign in adjacent), 0)
                        a, b = [ti for ti, _ in adjacent]
                        adjacency[a].add(b)
                        adjacency[b].add(a)
                    else:
                        boundary_faces.append(face)
                        coordinates = mesh.nodes[list(face)]
                        walls = [(axis, side) for axis in range(3) for side in (0, 1)
                                 if np.allclose(coordinates[:, axis], side*SIDES[axis],
                                                rtol=0, atol=1e-13)]
                        self.assertEqual(len(walls), 1)
                        wall_counts[walls[0]] += 1
                for axis in range(3):
                    self.assertTrue(np.all(wall_counts[axis] ==
                                          2 * np.prod(np.delete(cells, axis))))
                reached, stack = {0}, [0]
                while stack:
                    for ti in adjacency[stack.pop()] - reached:
                        reached.add(ti)
                        stack.append(ti)
                self.assertEqual(len(reached), len(mesh.tets))
                vertices = np.unique(boundary_faces)
                surface_edges = {tuple(edge) for face in boundary_faces
                                 for edge in combinations(face, 2)}
                self.assertEqual(len(vertices) - len(surface_edges) + len(boundary_faces), 2)

    def test_each_cell_is_a_nonoverlapping_six_tetrahedron_partition(self):
        for cells, result in self.results:
            with self.subTest(cells=cells.tolist()):
                points = result.mesh.nodes[result.mesh.tets] / SIDES * cells
                cell_ids = np.floor(points.mean(axis=1) + 1e-12).astype(int)
                groups = {}
                for ti, cell in enumerate(cell_ids):
                    groups.setdefault(tuple(cell), []).append(ti)
                self.assertEqual(len(groups), int(np.prod(cells)))
                for cell, ids in groups.items():
                    self.assertEqual(len(ids), 6)
                    local = points[ids] - cell
                    self.assertTrue(np.all(local >= -1e-12))
                    self.assertTrue(np.all(local <= 1 + 1e-12))
                    for a, b in combinations(local, 2):
                        self.assertTrue(interiors_separated(a, b),
                                        f"overlapping tetrahedra in cell {cell}")

    def test_dense_generalized_kernel_on_actual_returned_topology(self):
        for cells, result in self.results:
            with self.subTest(cells=cells.tolist()):
                space, mesh = result.space, result.mesh
                free = np.setdiff1d(np.arange(space.num_edges), result.pec_edge_ids)
                stiff = galerkin.assemble_curlcurl_3d(space)[free][:, free]
                mass = galerkin.assemble_edge_mass_3d(space)[free][:, free]
                values = la.eigvalsh(stiff.toarray(), mass.toarray())
                tolerance = 1e-9 * max(abs(values))
                self.assertFalse(np.any(values < -tolerance))
                self.assertEqual(np.count_nonzero(abs(values) <= tolerance),
                                 int(np.prod(cells - 1)))
                boundary = np.unique([face for face, owners in face_owners(mesh.tets).items()
                                      if len(owners) == 1])
                interior = np.setdiff1d(np.arange(len(mesh.nodes)), boundary)
                edges, row = space.edges, np.arange(space.num_edges)
                incidence = sp.coo_matrix(
                    (np.r_[-np.ones(len(edges)), np.ones(len(edges))],
                     (np.r_[row, row], np.r_[edges[:, 0], edges[:, 1]])),
                    shape=(len(edges), len(mesh.nodes))).tocsr()[free][:, interior]
                self.assertLessEqual(abs(stiff @ incidence).max()/abs(stiff).max(), 1e-11)


if __name__ == "__main__":
    unittest.main()
