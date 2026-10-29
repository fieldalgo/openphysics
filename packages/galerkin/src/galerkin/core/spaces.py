# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Edge numbering for the lowest-order Nédélec (Whitney) spaces.

An edge-element degree of freedom is an oriented mesh edge. ``EdgeSpace``
numbers the edges of a triangle mesh and ``EdgeSpace3D`` those of a
tetrahedron mesh; each records, per element, the global id of every local edge
and its sign against the global direction (low node id to high). The edge
kernels in ``kernels`` read ``mesh`` and ``signs`` from them, and
``galerkin.edge`` and ``galerkin.edge3d`` export both classes under their
public names.
"""
from __future__ import annotations

import numpy as np

from ..mesh import Mesh
from ..mesh3d import Mesh3D

# Local edge e of a triangle is the edge opposite node e: (e+1, e+2) mod 3.
TRI_LOCAL_EDGES = ((1, 2), (2, 0), (0, 1))
# Local edges of a tetrahedron.
TET_LOCAL_EDGES = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))


class EdgeSpace:
    """Global edge numbering plus per-triangle orientation signs."""

    def __init__(self, mesh: Mesh):
        self.mesh = mesh
        tris = mesh.triangles
        loc = np.stack([tris[:, list(e)] for e in TRI_LOCAL_EDGES], axis=1)  # (T, 3, 2)
        lo = loc.min(axis=2)
        hi = loc.max(axis=2)
        key = np.stack([lo, hi], axis=2).reshape(-1, 2)   # (3T, 2)

        # Sort integer columns directly: np.unique(axis=0) uses a slower
        # structured-row sort. Keep exactly its lexicographic edge numbering,
        # without packing node ids into an integer that could overflow.
        order = np.lexsort((key[:, 1], key[:, 0]))
        ordered = key[order]
        first = np.empty(len(key), dtype=bool)
        first[:1] = True
        first[1:] = np.any(ordered[1:] != ordered[:-1], axis=1)
        inv = np.empty(len(key), dtype=int)
        inv[order] = np.cumsum(first) - 1
        self.edges = ordered[first]                  # (E, 2)  global: low -> high
        self.tri_edges = inv.reshape(-1, 3)          # (T, 3)  global edge ids
        # +1 when the local direction (i -> j) matches the global (lo -> hi)
        self.signs = np.where(loc[:, :, 0] == lo, 1.0, -1.0)  # (T, 3)

    @property
    def num_edges(self) -> int:
        return len(self.edges)

    def boundary_edge_ids(self, node_set: np.ndarray | None = None) -> np.ndarray:
        """Global ids of edges lying ON the boundary (n x E = 0 constrains these).

        Boundary membership is topology, not node membership: an edge belongs to
        the boundary when exactly one triangle owns it. "Both endpoints are
        boundary nodes" is a different and wrong test — the diagonal of a corner
        cell joins two boundary nodes while running through the interior, and
        constraining it over-determines the problem. On a plain nx x ny rectangle
        exactly two such diagonals exist, one at each of two opposite corners.

        node_set: restrict to edges with both endpoints in this set, so a PEC
                  condition can be applied to some walls only.
        """
        count = np.bincount(self.tri_edges.ravel(), minlength=self.num_edges)
        ids = np.where(count == 1)[0]
        if node_set is not None:
            keep = np.isin(self.edges[ids], np.asarray(node_set, dtype=int)).all(axis=1)
            ids = ids[keep]
        return ids


class EdgeSpace3D:
    """Global edge numbering plus per-tetrahedron orientation signs."""

    def __init__(self, mesh: Mesh3D):
        self.mesh = mesh
        loc = np.stack([mesh.tets[:, list(e)] for e in TET_LOCAL_EDGES], axis=1)  # (T,6,2)
        lo, hi = loc.min(axis=2), loc.max(axis=2)
        key = np.stack([lo, hi], axis=2).reshape(-1, 2)
        uniq, inv = np.unique(key, axis=0, return_inverse=True)
        self.edges = uniq                              # (E, 2) global: low -> high
        self.tet_edges = inv.reshape(-1, 6)            # (T, 6)
        self.signs = np.where(loc[:, :, 0] == lo, 1.0, -1.0)

    @property
    def num_edges(self) -> int:
        return len(self.edges)

    def _ids(self, pairs: np.ndarray) -> np.ndarray:
        """Global ids of node pairs. self.edges is lexsorted, so a key search works."""
        n = self.mesh.num_nodes
        key = self.edges[:, 0].astype(np.int64) * n + self.edges[:, 1]
        p = np.sort(np.asarray(pairs, dtype=np.int64), axis=1)
        idx = np.searchsorted(key, p[:, 0] * n + p[:, 1])
        return idx

    def boundary_edge_ids(self, node_set: np.ndarray | None = None) -> np.ndarray:
        """Ids of edges lying in the boundary surface (n x E = 0 constrains these).

        node_set: restrict to boundary faces entirely inside this node set, so a
                  PEC condition can be applied to some walls only.
        """
        faces = self.mesh.boundary_faces()
        if node_set is not None:
            keep = np.isin(faces, np.asarray(node_set, dtype=int)).all(axis=1)
            faces = faces[keep]
        pairs = np.concatenate([faces[:, [0, 1]], faces[:, [0, 2]], faces[:, [1, 2]]])
        return np.unique(self._ids(np.unique(pairs, axis=0)))
