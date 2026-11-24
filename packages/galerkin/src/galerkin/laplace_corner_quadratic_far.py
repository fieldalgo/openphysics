# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Far logarithmic blocks for three physical radial-density modes.

Internal module, consistent units: not part of galerkin's public API (the ``__all__``
of its public modules).
"""
from functools import lru_cache
from dataclasses import dataclass
import math
import numpy as np
from galerkin.laplace_corner import (
    cached_power_rule as _cached_power_rule,
    frozen as _frozen,
    power as _power,
    order as _order)
from galerkin.laplace_corner_harmonic_interactions import (
    power_panel_harmonic_far_log,
    vectors as _vectors,
    real_log1p as _real_log1p)


__all__ = ['QuadraticPanelLogResult', 'power_panel_quadratic_far_log']


@dataclass(frozen=True)
class QuadraticPanelLogResult:
    """Immutable dimensionless 3x3 blocks, modes ordered by radial degree."""
    mean_log_distance: np.ndarray
    coarse_mean_log_distance: np.ndarray
    quadrature_order: int
    mass_error: float

    def __post_init__(self):
        for name in ('mean_log_distance', 'coarse_mean_log_distance'):
            object.__setattr__(self, name, _frozen(getattr(self, name)).reshape(3, 3))


@lru_cache(maxsize=128)
def _rule(p, n):
    branches = [_cached_power_rule(k*p, n) for k in (1, 2, 3)]
    nodes = np.concatenate([u for u, _ in branches])
    weights = np.zeros((3, 3*n))
    transform = np.array([[1., 0., 0.], [-math.sqrt(3), math.sqrt(3), 0.],
                          [math.sqrt(5), -3*math.sqrt(5), 2*math.sqrt(5)]])
    for k, (_, physical) in enumerate(branches):
        weights[:, k*n:(k+1)*n] = transform[:, k, None]*physical
    error = max([abs(math.fsum(w)-1) for _, w in branches]
                +[abs(math.fsum(weights[k])) for k in (1, 2)])
    if not np.isfinite(weights).all() or error > 1e-12:
        raise ValueError('quadratic physical masses are unresolved')
    return _frozen(nodes), _frozen(weights).reshape(3, 3*n), error


def _block(first, second, offset, p, q, order):
    a, b, o = (complex(*v) for v in (first, second, offset))
    u, left, mass0 = _rule(p, order)
    v, right, mass1 = _rule(q, order)
    s, t = a*u[:, None], b*v[None, :]
    result = np.zeros((3, 3))
    result[0, 2] = left[0]@_real_log1p(t/(o-s))@right[2]
    result[2, 0] = left[2]@_real_log1p(-s/(o+t))@right[0]
    centered = _real_log1p(s*t/((o-s)*(o+t)))
    for i, j in ((1, 2), (2, 1), (2, 2)):
        result[i, j] = left[i]@centered@right[j]
    return result, max(mass0, mass1)


def power_panel_quadratic_far_log(first, second, offset, first_exponent, second_exponent, *, quadrature_order=32):
    """Far log(|x-y| / 1 metre) blocks for three static radial modes.

    Modes are rho_p, sqrt(3)*(rho_2p-rho_p), and
    sqrt(5)*(2*rho_3p-3*rho_2p+rho_p), with physical masses [1,0,0].
    Vectors are planar metres: first starts at zero, second at offset.
    Require0.5<p,q<=1, lengthratio<=64 and offset length at least four
    times the sum of panel lengths. Explicit n/2n rules, n=4..64, retain
    physical weights with no mass rescaling. Unresolved masses or entrywise
    differences above1e-12*max(1,abs(fine)) are refused without retry.
    Both upper2x2 blocks retain the existing harmonic results exactly.
    Only00 changes under a common length scale. This is a primitive bound,
    not relative accuracy for tiny entries or a complete field method.
    """
    p, q = _power(first_exponent), _power(second_exponent)
    order = _order(quadrature_order, 64)
    lower = power_panel_harmonic_far_log(first, second, offset, p, q, quadrature_order=order)
    (a, b, o), lengths = _vectors(first, second, offset)
    scale = max(lengths)
    a, b, o = a/scale, b/scale, o/scale
    coarse, mass0 = _block(a, b, o, p, q, order)
    fine, mass1 = _block(a, b, o, p, q, 2*order)
    coarse[:2, :2] = lower.coarse_mean_log_distance
    fine[:2, :2] = lower.mean_log_distance
    if (not np.isfinite(coarse).all() or not np.isfinite(fine).all()
            or np.any(abs(fine-coarse) > 1e-12*np.maximum(1, abs(fine)))):
        raise ValueError('quadratic far interaction quadrature did not converge')
    return QuadraticPanelLogResult(fine, coarse, order, max(lower.mass_error, mass0, mass1))
