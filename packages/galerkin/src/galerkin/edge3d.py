# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Lowest-order Nedelec (Whitney) edge elements on tetrahedra — 3D H(curl).

The same idea as edge.py one dimension up, and the same reason for existing: the
electric field is only tangentially continuous across a material interface, so
its degrees of freedom belong on edges, not nodes.

Basis
-----
For the edge joining local vertices i and j,
    W_ij = lambda_i grad lambda_j - lambda_j grad lambda_i
    curl W_ij = 2 (grad lambda_i x grad lambda_j)      <- a constant VECTOR now,
                                                          where in 2D it was a scalar
A tetrahedron has six edges rather than three, and each carries a sign recording
whether the local direction agrees with the global convention (low node id -> high).

Element matrices
----------------
Everything is closed form. With g_ab = grad lambda_a . grad lambda_b and
int_T lambda_a lambda_b dV = V (1 + delta_ab) / 20, for e = (i,j), f = (k,l):

    S^e_ef = c V (curl W_e) . (curl W_f)
    M^e_ef = c V/20 [ (1+d_ik) g_jl - (1+d_il) g_jk - (1+d_jk) g_il + (1+d_jl) g_ik ]
    G^e_en = c V/4  (grad lambda_j - grad lambda_i) . grad lambda_n

No quadrature is needed anywhere, and the mass matrix is exact rather than merely
accurate — the same situation as the 2D midpoint rule, but written out directly.

Boundary edges
--------------
In 2D an edge lies on the boundary exactly when both its endpoints do. In 3D that
is false: an edge can join two boundary nodes and still pass through the interior.
Boundary edges are therefore taken from the boundary *faces* — the triangles that
belong to only one tetrahedron — which is both correct and mesh-agnostic.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from .mesh3d import Mesh3D
from .assembly3d import _scatter
from .core.tets import tet_gradients

LOCAL_EDGES = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
_I = np.array([e[0] for e in LOCAL_EDGES])
_J = np.array([e[1] for e in LOCAL_EDGES])


class EdgeSpace3D:
    """Global edge numbering plus per-tetrahedron orientation signs."""

    def __init__(self, mesh: Mesh3D):
        self.mesh = mesh
        loc = np.stack([mesh.tets[:, list(e)] for e in LOCAL_EDGES], axis=1)  # (T,6,2)
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


def _edge_scatter(space: EdgeSpace3D, Me):
    te = space.tet_edges
    return _scatter(Me, np.repeat(te, 6, axis=1), np.tile(te, (1, 6)),
                    (space.num_edges,) * 2)


def assemble_curlcurl_3d(space: EdgeSpace3D, coeff=1.0) -> sp.csr_matrix:
    """S_ef = int c (curl W_e) . (curl W_f) dV — closed form, curls are constant."""
    mesh = space.mesh
    g, vol = tet_gradients(mesh)
    c = np.broadcast_to(np.asarray(coeff, dtype=float), (mesh.num_tets,))

    curls = 2.0 * np.cross(g[:, _I, :], g[:, _J, :])          # (T, 6, 3)
    curls = curls * space.signs[:, :, None]
    Se = np.einsum("ted,tfd->tef", curls, curls) * (c * vol)[:, None, None]
    return _edge_scatter(space, Se)


def assemble_edge_mass_3d(space: EdgeSpace3D, coeff=1.0) -> sp.csr_matrix:
    """M_ef = int c W_e . W_f dV — exact closed form (see the module docstring)."""
    mesh = space.mesh
    g, vol = tet_gradients(mesh)
    c = np.broadcast_to(np.asarray(coeff, dtype=float), (mesh.num_tets,))

    G = np.einsum("tad,tbd->tab", g, g)                       # (T, 4, 4)
    d = np.eye(4)
    i, j = _I[:, None], _J[:, None]                           # edge e
    k, l = _I[None, :], _J[None, :]                           # edge f
    Me = ((1 + d[i, k]) * G[:, j, l] - (1 + d[i, l]) * G[:, j, k]
          - (1 + d[j, k]) * G[:, i, l] + (1 + d[j, l]) * G[:, i, k])
    Me *= (c * vol / 20.0)[:, None, None]
    Me *= space.signs[:, :, None] * space.signs[:, None, :]
    return _edge_scatter(space, Me)


def assemble_edge_grad_3d(space: EdgeSpace3D, coeff=1.0) -> sp.csr_matrix:
    """G_en = int c W_e . grad phi_n dV, shape (num_edges, num_nodes)."""
    mesh = space.mesh
    g, vol = tet_gradients(mesh)
    c = np.broadcast_to(np.asarray(coeff, dtype=float), (mesh.num_tets,))

    Ge = np.einsum("ted,tnd->ten", g[:, _J, :] - g[:, _I, :], g)   # (T, 6, 4)
    Ge *= (c * vol / 4.0)[:, None, None]
    Ge *= space.signs[:, :, None]
    return _scatter(Ge, np.repeat(space.tet_edges, 4, axis=1),
                    np.tile(mesh.tets, (1, 6)),
                    (space.num_edges, mesh.num_nodes))


def eval_edge_field_3d(space: EdgeSpace3D, dofs: np.ndarray) -> np.ndarray:
    """Edge dofs -> vector field at tetrahedron centroids, (T, 3).

    At the centroid every barycentric coordinate is 1/4, so W_ij reduces to
    (grad lambda_j - grad lambda_i)/4.
    """
    g, _ = tet_gradients(space.mesh)
    W = 0.25 * (g[:, _J, :] - g[:, _I, :])                    # (T, 6, 3)
    coef = space.signs * dofs[space.tet_edges]                # (T, 6)
    return np.einsum("te,ted->td", coef, W).astype(dofs.dtype)
