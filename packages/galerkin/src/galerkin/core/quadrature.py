# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Quadrature on triangles."""
import numpy as np


def triangle_product_rule():
    """Barycentric points (36,3) and weights (36,) of the 6x6 Gauss Duffy product rule.

    The rule integrates over the unit triangle; weights sum to 1, so multiply by
    a triangle's area.
    """
    x, w = np.polynomial.legendre.leggauss(6)
    x, w = (x+1)/2, w/2
    a, b = np.meshgrid(x, x, indexing="ij")
    bary = np.stack([(1-a)*(1-b), a, (1-a)*b], axis=-1).reshape(-1, 3)
    weights = (2*w[:, None]*w[None, :]*(1-a)).ravel()
    return bary, weights
