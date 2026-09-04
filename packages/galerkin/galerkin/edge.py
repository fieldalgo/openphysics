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

        uniq, inv = np.unique(key, axis=0, return_inverse=True)
        self.edges = uniq                            # (E, 2)  global: low -> high
        self.tri_edges = inv.reshape(-1, 3)          # (T, 3)  global edge ids
        # +1 when the local direction (i -> j) matches the global (lo -> hi)
        self.signs = np.where(loc[:, :, 0] == lo, 1.0, -1.0)  # (T, 3)

    @property
    def num_edges(self) -> int:
        return len(self.edges)

    def boundary_edge_ids(self, node_set: np.ndarray) -> np.ndarray:
        """Global ids of edges whose both endpoints lie in node_set (PEC walls)."""
        s = set(np.asarray(node_set).tolist())
        mask = np.array([(a in s) and (b in s) for a, b in self.edges])
        return np.where(mask)[0]


def _tri_grads(mesh: Mesh):
    """Barycentric gradients grad lambda (T, 3, 2) and triangle areas."""
    p = mesh.nodes[mesh.triangles]
    x, y = p[:, :, 0], p[:, :, 1]
    b = np.stack([y[:, 1] - y[:, 2], y[:, 2] - y[:, 0], y[:, 0] - y[:, 1]], axis=1)
    c = np.stack([x[:, 2] - x[:, 1], x[:, 0] - x[:, 2], x[:, 1] - x[:, 0]], axis=1)
    area = np.abs(0.5 * (b[:, 0] * c[:, 1] - b[:, 1] * c[:, 0]))
    grads = np.stack([b, c], axis=2) / (2.0 * area)[:, None, None]
    return grads, area


def assemble_curlcurl(space: EdgeSpace) -> sp.csr_matrix:
    """S_ee' = int (curl W_e)(curl W_e') dx — closed form since curls are constant."""
    mesh = space.mesh
    g, area = _tri_grads(mesh)

    # Local edge e = (i, j) = (e+1, e+2) mod 3
    i_loc = [1, 2, 0]
    j_loc = [2, 0, 1]
    curls = np.stack([
        2.0 * (g[:, i, 0] * g[:, j, 1] - g[:, i, 1] * g[:, j, 0])
        for i, j in zip(i_loc, j_loc)], axis=1)      # (T, 3)
    curls = curls * space.signs

    Se = area[:, None, None] * curls[:, :, None] * curls[:, None, :]

    te = space.tri_edges
    rows = np.repeat(te, 3, axis=1).ravel()
    cols = np.tile(te, (1, 3)).ravel()
    S = sp.coo_matrix((Se.ravel(), (rows, cols)),
                      shape=(space.num_edges, space.num_edges))
    return S.tocsr()


def assemble_edge_mass(space: EdgeSpace) -> sp.csr_matrix:
    """M_ee' = int W_e . W_e' dx — 3-point edge-midpoint rule (exact to degree 2)."""
    mesh = space.mesh
    g, area = _tri_grads(mesh)
    T = len(area)

    # Quadrature points: edge midpoints. Barycentric values (3 points x 3 nodes)
    lam = 0.5 * (np.ones((3, 3)) - np.eye(3))   # point m: lambda_m = 0, others 1/2

    i_loc = [1, 2, 0]
    j_loc = [2, 0, 1]
    # W_e(qp) = lambda_i(qp) grad lambda_j - lambda_j(qp) grad lambda_i
    #   -> (T, 3 edges, 3 qp, 2)
    W = np.empty((T, 3, 3, 2))
    for e, (i, j) in enumerate(zip(i_loc, j_loc)):
        W[:, e] = (lam[None, :, i, None] * g[:, None, j, :]
                   - lam[None, :, j, None] * g[:, None, i, :])
    W *= space.signs[:, :, None, None]

    # M^e = (A/3) sum_qp W_e(qp) . W_e'(qp)
    Me = np.einsum("teqd,tfqd->tef", W, W) * (area / 3.0)[:, None, None]

    te = space.tri_edges
    rows = np.repeat(te, 3, axis=1).ravel()
    cols = np.tile(te, (1, 3)).ravel()
    M = sp.coo_matrix((Me.ravel(), (rows, cols)),
                      shape=(space.num_edges, space.num_edges))
    return M.tocsr()


def eval_edge_field(space: EdgeSpace, dofs: np.ndarray) -> np.ndarray:
    """Edge dofs -> vector field evaluated at triangle centroids, (T, 2)."""
    mesh = space.mesh
    g, _ = _tri_grads(mesh)
    lam_c = np.full(3, 1.0 / 3.0)                # centroid
    i_loc = [1, 2, 0]
    j_loc = [2, 0, 1]
    vals = np.zeros((mesh.num_triangles, 2), dtype=dofs.dtype)
    for e, (i, j) in enumerate(zip(i_loc, j_loc)):
        We = lam_c[i] * g[:, j, :] - lam_c[j] * g[:, i, :]
        coef = (space.signs[:, e] * dofs[space.tri_edges[:, e]])
        vals += coef[:, None] * We
    return vals
