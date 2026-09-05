"""Tetrahedral mesh data structure and a structured generator for boxes.

The 3D counterpart of mesh.py. What changes going from triangles to tetrahedra:

  - an element has four vertices and six edges instead of three and three
  - orientation is a sign of a 3x3 determinant rather than of a cross product
  - "the boundary" is a set of triangular faces, and an edge lies on the boundary
    only if it lies *in* one of those faces. In 2D "both endpoints on the
    boundary" was equivalent; in 3D it is not — an edge can join two boundary
    nodes while passing through the interior — and getting that wrong silently
    over-constrains a PEC problem.

Boxes are triangulated in-house with the Kuhn (Freudenthal) subdivision: each
cube is cut into six tetrahedra, one per ordering of the three axis directions,
each following a monotone path from the (0,0,0) corner to the (1,1,1) corner.
Neighbouring cubes then agree face for face, so the mesh is conforming without
any bookkeeping, and the subdivision is self-similar, so element quality does not
degrade under refinement.
"""

from __future__ import annotations

from itertools import permutations

import numpy as np


class Mesh3D:
    def __init__(self, nodes: np.ndarray, tets: np.ndarray,
                 boundary: dict[str, np.ndarray] | None = None):
        self.nodes = np.asarray(nodes, dtype=float)
        self.tets = np.asarray(tets, dtype=int)
        self.boundary = {k: np.asarray(v, dtype=int)
                         for k, v in (boundary or {}).items()}
        self._faces = None
        self._fix_orientation()

    @property
    def num_nodes(self) -> int:
        return len(self.nodes)

    @property
    def num_tets(self) -> int:
        return len(self.tets)

    def _edge_matrix(self) -> np.ndarray:
        """(T, 3, 3) with rows p1-p0, p2-p0, p3-p0."""
        p = self.nodes[self.tets]
        return np.stack([p[:, 1] - p[:, 0], p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]],
                        axis=1)

    def _fix_orientation(self):
        """Swap two vertices so that every tetrahedron has a positive volume."""
        flipped = np.linalg.det(self._edge_matrix()) < 0.0
        self.tets[flipped] = self.tets[flipped][:, [0, 1, 3, 2]]

    def volumes(self) -> np.ndarray:
        return np.abs(np.linalg.det(self._edge_matrix())) / 6.0

    def faces(self):
        """(unique sorted faces, how many tetrahedra each belongs to)."""
        if self._faces is None:
            t = self.tets
            f = np.concatenate([t[:, [1, 2, 3]], t[:, [0, 2, 3]],
                                t[:, [0, 1, 3]], t[:, [0, 1, 2]]])
            self._faces = np.unique(np.sort(f, axis=1), axis=0, return_counts=True)
        return self._faces

    def boundary_faces(self) -> np.ndarray:
        """(F, 3) faces belonging to exactly one tetrahedron."""
        uniq, count = self.faces()
        return uniq[count == 1]

    def boundary_nodes(self) -> np.ndarray:
        return np.unique(self.boundary_faces())


def box_mesh(lx: float, ly: float, lz: float,
             nx: int, ny: int, nz: int) -> Mesh3D:
    """Kuhn subdivision of [0,lx] x [0,ly] x [0,lz] into 6 nx ny nz tetrahedra.

    Boundary tags: 'x0', 'x1', 'y0', 'y1', 'z0', 'z1'.
    """
    x = np.linspace(0.0, lx, nx + 1)
    y = np.linspace(0.0, ly, ny + 1)
    z = np.linspace(0.0, lz, nz + 1)
    X, Y, Z = np.meshgrid(x, y, z, indexing="ij")
    nodes = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])

    def nid(i, j, k):
        return (i * (ny + 1) + j) * (nz + 1) + k

    I, J, K = (a.ravel() for a in np.meshgrid(np.arange(nx), np.arange(ny),
                                              np.arange(nz), indexing="ij"))
    tets = []
    for order in permutations(range(3)):
        # cumulative unit steps along the axes in this order: (0,0,0) -> (1,1,1)
        step = np.zeros((4, 3), dtype=int)
        for s, axis in enumerate(order):
            step[s + 1:] += np.eye(3, dtype=int)[axis]
        tets.append(np.stack([nid(I + d[0], J + d[1], K + d[2]) for d in step],
                             axis=1))

    i, j, k = (np.arange(nx + 1), np.arange(ny + 1), np.arange(nz + 1))
    JJ, KK = (a.ravel() for a in np.meshgrid(j, k, indexing="ij"))
    II, KK2 = (a.ravel() for a in np.meshgrid(i, k, indexing="ij"))
    II2, JJ2 = (a.ravel() for a in np.meshgrid(i, j, indexing="ij"))
    boundary = {
        "x0": nid(0, JJ, KK),   "x1": nid(nx, JJ, KK),
        "y0": nid(II, 0, KK2),  "y1": nid(II, ny, KK2),
        "z0": nid(II2, JJ2, 0), "z1": nid(II2, JJ2, nz),
    }
    return Mesh3D(nodes, np.concatenate(tets), boundary)
