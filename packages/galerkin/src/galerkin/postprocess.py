# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Post-processing: field evaluation and error measurement.

E = -grad V. With P1 elements grad V is constant per triangle, so the field
comes out piecewise constant (one vector per element).
"""

from __future__ import annotations

import numpy as np

from .core.backend import is_live, namespace
from .core.checks import refuse_live
from .mesh import Mesh


def element_gradient(mesh: Mesh, V: np.ndarray) -> np.ndarray:
    """Per-triangle grad V as a (T, 2) array. The electric field is E = -grad V.

    V may be a JAX or PyTorch array; the result is then in its library and
    carries its derivative (mesh geometry stays NumPy).
    """
    tris = mesh.triangles
    p = mesh.nodes[tris]
    x, y = p[:, :, 0], p[:, :, 1]

    b = np.stack([y[:, 1] - y[:, 2], y[:, 2] - y[:, 0], y[:, 0] - y[:, 1]], axis=1)
    c = np.stack([x[:, 2] - x[:, 1], x[:, 0] - x[:, 2], x[:, 1] - x[:, 0]], axis=1)
    area = mesh.areas()

    if is_live(V):
        xp = namespace(V)
        Ve = V[tris]
        twice = xp.asarray(2.0 * area)
        grad_x = xp.sum(xp.asarray(b) * Ve, axis=1) / twice
        grad_y = xp.sum(xp.asarray(c) * Ve, axis=1) / twice
        return xp.stack([grad_x, grad_y], axis=1)
    Ve = V[tris]  # (T, 3)
    grad_x = (b * Ve).sum(axis=1) / (2.0 * area)
    grad_y = (c * Ve).sum(axis=1) / (2.0 * area)
    return np.column_stack([grad_x, grad_y])


def l2_error(mesh: Mesh, V: np.ndarray, exact) -> float:
    """|| V_h - V_exact ||_L2, approximated by a one-point centroid rule.

    exact: vectorized callable exact(x, y) returning the analytical solution.
    NumPy only: JAX and PyTorch values raise TypeError.
    """
    refuse_live(V, "l2_error V")
    tris = mesh.triangles
    centroid = mesh.nodes[tris].mean(axis=1)
    Vh_c = V[tris].mean(axis=1)              # centroid value of the P1 interpolant
    Ve_c = exact(centroid[:, 0], centroid[:, 1])
    refuse_live(Ve_c, "l2_error exact values")
    return float(np.sqrt(np.sum(mesh.areas() * np.abs(Vh_c - Ve_c) ** 2)))
