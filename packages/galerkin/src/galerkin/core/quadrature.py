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


# Dunavant (1985) fully symmetric rules on the triangle: barycentric orbits and
# weights normalised to sum to 1 (multiply by the triangle's area). Degree 4 has
# 6 points, degree 6 has 12; the 15-digit constants are the published ones.
_SYMMETRIC_RULES = {
    4: (((0.223381589678011, (0.108103018168070, 0.445948490915965, 0.445948490915965)),
         (0.109951743655322, (0.816847572980459, 0.091576213509771, 0.091576213509771)))),
    6: (((0.116786275726379, (0.501426509658179, 0.249286745170910, 0.249286745170910)),
         (0.050844906370207, (0.873821971016996, 0.063089014491502, 0.063089014491502)),
         (0.082851075618374, (0.053145049844817, 0.310352451033784, 0.636502499121399)))),
}


def _orbit(point):
    """The distinct permutations of a barycentric triple, in a fixed order."""
    a, b, c = point
    perms = ((a, b, c), (b, c, a), (c, a, b), (a, c, b), (c, b, a), (b, a, c))
    seen, out = set(), []
    for p in perms:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def triangle_symmetric_rule(degree: int):
    """Barycentric points (Q, 3) and weights (Q,) of a symmetric rule exact to ``degree``.

    degree 4: Dunavant's 6-point rule; degree 6: the 12-point rule. Weights sum
    to 1, so multiply by a triangle's area, as for ``triangle_product_rule``.
    """
    if degree not in _SYMMETRIC_RULES:
        raise ValueError("degree must be " + " or ".join(str(d) for d in sorted(_SYMMETRIC_RULES)))
    bary, weights = [], []
    for w, point in _SYMMETRIC_RULES[degree]:
        orbit = _orbit(point)
        bary.extend(orbit)
        weights.extend([w] * len(orbit))
    return np.asarray(bary, dtype=float), np.asarray(weights, dtype=float)
