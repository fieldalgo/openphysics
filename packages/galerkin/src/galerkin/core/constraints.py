# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Dirichlet constraints for two-component nodal fields."""
from typing import Mapping

import numpy as np

from .checks import real_array


def vector_dirichlet(dirichlet, p, boundary, count, labels):
    """Fixed DOFs and values of a {(node, component): value} displacement mapping.

    Nodes must be exterior; every connected component must be held against all
    three planar rigid motions. DOF numbering is 2*node+component.
    """
    if not isinstance(dirichlet, Mapping):
        raise ValueError("dirichlet must map (node, component) to displacement in metres")
    fixed, values = [], []
    for key, value in dirichlet.items():
        if (not isinstance(key, tuple) or len(key) != 2
                or any(isinstance(k, (bool, np.bool_)) or not isinstance(k, (int, np.integer)) for k in key)):
            raise ValueError("Dirichlet keys must be integer (node, component) tuples")
        node, component = key
        if not 0 <= node < len(p) or component not in (0, 1):
            raise ValueError("Dirichlet node/component index out of range")
        if node not in boundary:
            raise ValueError("Dirichlet nodes must lie on the exterior mesh boundary")
        v = real_array(value, "Dirichlet displacement")
        if v.shape != ():
            raise ValueError("each Dirichlet displacement must be scalar")
        fixed.append(2*node+component)
        values.append(float(v))
    fixed = np.asarray(fixed, dtype=int)
    values = np.asarray(values)
    for c in range(count):
        nodes = np.flatnonzero(labels == c)
        local = fixed[labels[fixed//2] == c]
        xy = p[local//2]-p[nodes].mean(axis=0)
        xy /= np.ptp(p[nodes], axis=0).max()
        rigid = np.column_stack([local % 2 == 0, local % 2 == 1,
                                 np.where(local % 2 == 0, -xy[:, 1], xy[:, 0])])
        if len(local) < 3 or np.linalg.matrix_rank(rigid, tol=1e-10) < 3:
            raise ValueError(f"insufficient Dirichlet constraints: rigid modes in component {c}")
    return fixed, values
