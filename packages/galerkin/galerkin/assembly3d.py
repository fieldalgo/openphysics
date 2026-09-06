# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""P1 (linear tetrahedron) assembly: stiffness and mass.

The 3D counterpart of assembly.py. On a linear tetrahedron the barycentric
gradients are constant, so both element matrices are closed forms:

    K^e_mn = V (grad lambda_m)^T Lam (grad lambda_n)
    M^e_mn = c V (1 + delta_mn) / 20          from  int_T lam_a lam_b dV = V(1+delta)/20

The 1/20 is the only thing that changes from the triangle's 1/12; everything else
is the same algebra one dimension up.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from .mesh3d import Mesh3D


def tet_gradients(mesh: Mesh3D):
    """Barycentric gradients (T, 4, 3) and volumes (T,).

    With E the matrix whose rows are p1-p0, p2-p0, p3-p0, a point satisfies
    x - p0 = (lam1, lam2, lam3) E, so grad lam_{i+1} is column i of E^-1 and
    grad lam_0 = -(grad lam_1 + grad lam_2 + grad lam_3).
    """
    E = mesh._edge_matrix()                       # (T, 3, 3)
    vol = np.abs(np.linalg.det(E)) / 6.0
    grads = np.empty((mesh.num_tets, 4, 3))
    grads[:, 1:, :] = np.transpose(np.linalg.inv(E), (0, 2, 1))
    grads[:, 0, :] = -grads[:, 1:, :].sum(axis=1)
    return grads, vol


def _scatter(vals, rows, cols, shape):
    return sp.coo_matrix((vals.ravel(), (rows.ravel(), cols.ravel())),
                         shape=shape).tocsr()


def assemble_stiffness_3d(mesh: Mesh3D, eps=1.0) -> sp.csr_matrix:
    """K_mn = int (eps grad phi_n) . grad phi_m dV.

    eps: scalar, per-tetrahedron (T,), or per-tetrahedron 3x3 tensors (T, 3, 3).
    """
    g, vol = tet_gradients(mesh)
    eps = np.asarray(eps)
    if eps.ndim == 3:
        Ke = np.einsum("tmd,tde,tne->tmn", g, eps, g) * vol[:, None, None]
    else:
        c = np.broadcast_to(eps, (mesh.num_tets,))
        Ke = np.einsum("tmd,tnd->tmn", g, g) * (c * vol)[:, None, None]
    t = mesh.tets
    return _scatter(Ke, np.repeat(t, 4, axis=1), np.tile(t, (1, 4)),
                    (mesh.num_nodes,) * 2)


def assemble_mass_3d(mesh: Mesh3D, coeff=1.0) -> sp.csr_matrix:
    """M_mn = int c phi_m phi_n dV, exact: M^e = c V/20 * (1 + delta_mn)."""
    vol = mesh.volumes()
    c = np.broadcast_to(np.asarray(coeff), (mesh.num_tets,))
    base = (np.ones((4, 4)) + np.eye(4)) / 20.0
    Me = (c * vol)[:, None, None] * base
    t = mesh.tets
    return _scatter(Me, np.repeat(t, 4, axis=1), np.tile(t, (1, 4)),
                    (mesh.num_nodes,) * 2)
