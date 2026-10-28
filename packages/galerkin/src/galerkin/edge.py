# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Lowest-order Nedelec (Whitney) edge elements — 2D H(curl).

Why they exist
--------------
Maxwell's electric field E is only tangentially continuous across material
interfaces. Nodal (P1) vector elements enforce full continuity and thereby
produce non-physical solutions (spurious modes) in eigenvalue problems.
Edge elements place the unknowns on *edges* — the tangential circulation
along each edge — enforcing exactly the right amount of continuity: the
proper discretization of H(curl).

Basis functions (Whitney 1-forms)
---------------------------------
For the edge joining nodes i and j (lambda = barycentric coordinates):
    W_ij = lambda_i grad lambda_j - lambda_j grad lambda_i
Properties: int over edge (i,j) of W_ij . t ds = 1, zero on other edges,
    curl W_ij = 2 (grad lambda_i x grad lambda_j)   <- constant per triangle.

Global degrees of freedom are *oriented* edges, so each triangle must track a
sign (+-1) recording whether its local edge direction agrees with the global
convention (low node id -> high node id). Managing these signs is half of the
practical difficulty of implementing edge elements.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from .core import forms, kernels
from .core.checks import refuse_live
from .mesh import Mesh


class EdgeSpace:
    """Global edge numbering plus per-triangle orientation signs."""

    def __init__(self, mesh: Mesh):
        self.mesh = mesh
        tris = mesh.triangles
        # Local edge e is the edge opposite node e: (e+1, e+2) mod 3
        loc = np.stack([tris[:, [1, 2]], tris[:, [2, 0]], tris[:, [0, 1]]],
                       axis=1)                       # (T, 3, 2)
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


def assemble_curlcurl(space: EdgeSpace, coeff=1.0) -> sp.csr_matrix:
    """S_ee' = int c (curl W_e)(curl W_e') dx — closed form since curls are constant.

    coeff: scalar or per-triangle array (T,). For Maxwell this is 1/mu_r.
    """
    refuse_live(coeff, "assemble_curlcurl coeff")
    te = space.tri_edges
    return forms.matrix(te, te, kernels.nedelec_curlcurl(space, coeff), (space.num_edges,) * 2).to_scipy()


def assemble_edge_mass(space: EdgeSpace, coeff=1.0) -> sp.csr_matrix:
    """M_ee' = int c W_e . W_e' dx — 3-point edge-midpoint rule (exact to degree 2).

    W_e . W_e' is quadratic in the barycentric coordinates and the midpoint rule
    integrates degree 2 exactly, so this matrix is exact, not approximate.
    coeff: scalar, per-triangle (T,), or tensor (T, 2, 2); complex allowed.
    """
    refuse_live(coeff, "assemble_edge_mass coeff")
    te = space.tri_edges
    return forms.matrix(te, te, kernels.nedelec_mass(space, coeff), (space.num_edges,) * 2).to_scipy()


def assemble_edge_grad(space: EdgeSpace, coeff=1.0) -> sp.csr_matrix:
    """Coupling matrix G_en = int c W_e . grad phi_n dx, shape (num_edges, num_nodes).

    This is the bridge between the H(curl) edge space and the H1 nodal space —
    the block that couples the transverse and longitudinal field components of a
    waveguide mode. It has a closed form: grad lambda is constant on a triangle
    and int_T lambda_i dx = A/3, so for the local edge (i, j)

        int_T W_ij . grad lambda_k dx = (A/3) (grad lambda_j - grad lambda_i) . grad lambda_k

    coeff: scalar, per-triangle (T,), or tensor (T, 2, 2); complex allowed.
    """
    refuse_live(coeff, "assemble_edge_grad coeff")
    mesh = space.mesh
    return forms.matrix(space.tri_edges, mesh.triangles, kernels.nedelec_grad(space, coeff),
                        (space.num_edges, mesh.num_nodes)).to_scipy()


def eval_edge_field(space: EdgeSpace, dofs: np.ndarray) -> np.ndarray:
    """Edge dofs -> vector field evaluated at triangle centroids, (T, 2)."""
    mesh = space.mesh
    g, _ = kernels.triangle_gradients(mesh)
    lam_c = np.full(3, 1.0 / 3.0)                # centroid
    i_loc = [1, 2, 0]
    j_loc = [2, 0, 1]
    vals = np.zeros((mesh.num_triangles, 2), dtype=dofs.dtype)
    for e, (i, j) in enumerate(zip(i_loc, j_loc)):
        We = lam_c[i] * g[:, j, :] - lam_c[j] * g[:, i, :]
        coef = (space.signs[:, e] * dofs[space.tri_edges[:, e]])
        vals += coef[:, None] * We
    return vals
