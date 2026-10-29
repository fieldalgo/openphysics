# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""P1 tetrahedron element data shared by the 3D assembly modules and core kernels."""
import numpy as np

from ..mesh3d import Mesh3D


def edge_matrix(mesh: Mesh3D):
    """(T, 3, 3) with rows p1-p0, p2-p0, p3-p0 of each tetrahedron."""
    p = mesh.nodes[mesh.tets]
    return np.stack([p[:, 1] - p[:, 0], p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]], axis=1)


def tet_gradients(mesh: Mesh3D):
    """Barycentric gradients (T, 4, 3) and volumes (T,).

    With E the matrix whose rows are p1-p0, p2-p0, p3-p0, a point satisfies
    x - p0 = (lam1, lam2, lam3) E, so grad lam_{i+1} is column i of E^-1 and
    grad lam_0 = -(grad lam_1 + grad lam_2 + grad lam_3).
    """
    E = edge_matrix(mesh)                         # (T, 3, 3)
    vol = np.abs(np.linalg.det(E)) / 6.0
    grads = np.empty((mesh.num_tets, 4, 3))
    grads[:, 1:, :] = np.transpose(np.linalg.inv(E), (0, 2, 1))
    grads[:, 0, :] = -grads[:, 1:, :].sum(axis=1)
    return grads, vol
