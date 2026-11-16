# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit static wedge-harmonic logarithmic interaction blocks."""
from dataclasses import dataclass
from functools import lru_cache
import math

import numpy as np

from .laplace_corner import (
    _cached_power_rule, _cached_graded_rule, _constant_segment_log,
    _constant_linear_segment_log, _frozen, _power, _order,
    _separated_distance, _require_disjoint_or_endpoint,
)
from .laplace_corner_partitioned import _partition

__all__ = [
    'HarmonicPanelLogResult', 'power_panel_harmonic_far_log',
    'power_panel_harmonic_shared_vertex_log', 'power_panel_harmonic_separated_log',
    'power_panel_harmonic_constant_log_partitioned',
]


@dataclass(frozen=True)
class HarmonicPanelLogResult:
    """Immutable dimensionless blocks ordered by constant/zero-mass modes."""
    mean_log_distance: np.ndarray
    coarse_mean_log_distance: np.ndarray
    quadrature_order: int
    subintervals: int = 1
    mass_error: float = 0.0

    def __post_init__(self):
        for name in ('mean_log_distance', 'coarse_mean_log_distance'):
            object.__setattr__(self, name, _frozen(getattr(self, name)).reshape(2, 2))


def _vectors(*values):
    result = []
    for value in values:
        raw = np.asarray(value)
        if raw.shape != (2,) or raw.dtype.kind not in 'fiu' or not np.isfinite(raw).all():
            raise ValueError('finite real planar vectors are required')
        result.append(np.asarray(raw, dtype=float))
    lengths = [math.hypot(*value) for value in result]
    if not all(math.isfinite(x) for x in lengths) or min(lengths[:2]) <= 0:
        raise ValueError('panel geometry is unrepresentable')
    return result, lengths


def _finish(coarse, fine, order, subintervals=1, mass_error=0.0):
    if (not np.isfinite(coarse).all() or not np.isfinite(fine).all()
            or np.any(abs(fine-coarse) > 1e-12*np.maximum(1, abs(fine)))):
        raise ValueError('harmonic interaction quadrature did not converge')
    return HarmonicPanelLogResult(fine, coarse, order, subintervals, mass_error)


@lru_cache(maxsize=128)
def _rule(p, n):
    u, w = _cached_power_rule(p, n)
    v, z = _cached_power_rule(2*p, n)
    nodes = np.r_[u, v]
    weights = np.zeros((2, 2*n))
    weights[0, :n] = w
    weights[1, :n] = -math.sqrt(3)*w
    weights[1, n:] = math.sqrt(3)*z
    error = max(abs(math.fsum(w)-1), abs(math.fsum(z)-1),
                abs(math.fsum(weights[1])))
    if not np.isfinite(weights).all() or error > 1e-12:
        raise ValueError('harmonic physical masses are unresolved')
    return _frozen(nodes), _frozen(weights).reshape(2, 2*n), error


def _real_log1p(z):
    # Preserve the small real modulus increment; complex log1p may first
    # round the magnitude of 1+z. This is an exact algebraic identity.
    return .5*np.log1p(2*z.real + z.real*z.real + z.imag*z.imag)


def _centered_block(first, second, offset, p, q, order):
    a, b, o = (complex(*v) for v in (first, second, offset))
    u, left, mass0 = _rule(p, order)
    v, right, mass1 = _rule(q, order)
    s, t = a*u[:, None], b*v[None, :]
    result = np.zeros((2, 2))
    result[0, 0] = math.log(abs(o)) + left[0] @ _real_log1p((t-s)/o) @ right[0]
    result[0, 1] = left[0] @ _real_log1p(t/(o-s)) @ right[1]
    result[1, 0] = left[1] @ _real_log1p(-s/(o+t)) @ right[0]
    result[1, 1] = left[1] @ _real_log1p(s*t/((o-s)*(o+t))) @ right[1]
    return result, max(mass0, mass1)


def _separated(first, second, offset, p, q, order, far):
    (a, b, o), (la, lb, lo) = _vectors(first, second, offset)
    size = max(la, lb)
    if min(la, lb)/size < 1/64:
        raise ValueError('panel length ratio must not exceed64')
    if lo <= 0:
        raise ValueError('panel offset must be positive')
    if far:
        if lo/4 < la+lb:
            raise ValueError('far offset must be at least four times both lengths')
    elif lo/4 < size and _separated_distance(a/size, b/size, o/size) < .5:
        raise ValueError('separation must be at least half the longer length')
    scale = max(size, lo)
    a, b, o = a/scale, b/scale, o/scale
    if not np.any(a) or not np.any(b):
        raise ValueError('normalized panel direction is unrepresentable')
    coarse, mass0 = _centered_block(a, b, o, p, q, order)
    fine, mass1 = _centered_block(a, b, o, p, q, 2*order)
    coarse[0, 0] += math.log(scale)
    fine[0, 0] += math.log(scale)
    return _finish(coarse, fine, order, mass_error=max(mass0, mass1))


def power_panel_harmonic_far_log(first, second, offset, first_exponent,
                                 second_exponent, *, quadrature_order=32):
    """Far blocks for rho_p and sqrt(3)*(rho_2p-rho_p), masses [1,0].

    All vectors are planar metres; first starts at zero, second at offset.
    Exponents lie in(0.5,1], length ratio<=64, and offset length is at least
    four times the sum of panel lengths. Explicit n/2n rules with n=4..64
    retain physical weights and compare at1e-12*max(1,abs(fine)). Only00
    changes with log(length scale). No fallback or field-error guarantee.
    """
    return _separated(first, second, offset, _power(first_exponent),
                      _power(second_exponent), _order(quadrature_order, 64), True)


def power_panel_harmonic_separated_log(first, second, offset, first_exponent,
                                       second_exponent, *, quadrature_order=32):
    """Same physical harmonic modes on non-touching separated segments.

    Length ratio<=64 and segment separation>=half the longer length.
    Planar metre inputs, exponents(0.5,1], explicit n/2n with n=4..64,
    normalized primitive comparison1e-12 and no automatic retry. This does
    not admit closer/touching pairs or establish a field solution.
    """
    return _separated(first, second, offset, _power(first_exponent),
                      _power(second_exponent), _order(quadrature_order, 64), False)


def _vertex_block(a, b, p, q, order):
    raw = np.zeros((2, 2))
    error = 0.0
    for i, alpha in enumerate((p, 2*p)):
        u, w = _cached_power_rule(alpha, order)
        error = max(error, abs(math.fsum(w)-1))
        jb = math.fsum(w*np.log(np.hypot(*(b[None]-u[:, None]*a).T)))
        for j, beta in enumerate((q, 2*q)):
            v, z = _cached_power_rule(beta, order)
            error = max(error, abs(math.fsum(z)-1))
            ja = math.fsum(z*np.log(np.hypot(*(a[None]-v[:, None]*b).T)))
            raw[i, j] = (-1 + alpha*ja + beta*jb)/(alpha+beta)
    if error > 1e-12:
        raise ValueError('harmonic physical masses are unresolved')
    transform = np.array([[1., 0.], [-math.sqrt(3), math.sqrt(3)]])
    value = np.array([[math.fsum(transform[i,r]*transform[j,s]*raw[r,s]
                               for r in range(2) for s in range(2))
                       for j in range(2)] for i in range(2)])
    return value, error


def power_panel_harmonic_shared_vertex_log(first, second, first_exponent,
                                           second_exponent, *, quadrature_order=64):
    """Harmonic log block for distinct rays sharing their singular origin.

    Planar metre vectors, exponents(0.5,1], length ratio<=64, no overlapping
    rays. Duffy radial integration is analytic; angular n/2n rules use
    n=4..64 and physical normalization. Unresolved quadrature is refused.
    """
    p, q = _power(first_exponent), _power(second_exponent)
    order = _order(quadrature_order, 64)
    (a, b), (la, lb) = _vectors(first, second)
    scale = max(la, lb)
    if min(la, lb)/scale < 1/64:
        raise ValueError('panel length ratio must not exceed64')
    a, b = a/scale, b/scale
    cross = a[0]*b[1]-a[1]*b[0]
    if float(a@b) >= 0 and abs(cross) <= 128*np.finfo(float).eps*(la/scale)*(lb/scale):
        raise ValueError('rays must not overlap')
    coarse, mass0 = _vertex_block(a, b, p, q, order)
    fine, mass1 = _vertex_block(a, b, p, q, 2*order)
    coarse[0, 0] += math.log(scale)
    fine[0, 0] += math.log(scale)
    return _finish(coarse, fine, order, mass_error=max(mass0, mass1))


def _measure(exponent, cuts, order):
    points, weights = [], []
    for left, right in zip(cuts, cuts[1:]):
        span = right-left
        if left == 0:
            nodes, physical = _cached_graded_rule(exponent, order)
            parameter, physical = span*nodes, physical*span**exponent
        else:
            nodes, physical = _cached_graded_rule(1., order)
            parameter = left+span*nodes
            physical = physical*exponent*parameter**(exponent-1)*span
        points.extend(parameter)
        weights.extend(physical)
    return np.asarray(points), np.asarray(weights)


def _mixed_block(a, b, o, p, cuts, order, source_length):
    direction = complex(*b)
    anchor = complex(*o)/direction
    anchor0, anchor1 = float(_constant_segment_log(anchor)), float(_constant_linear_segment_log(anchor))
    zero, one, masses = [], [], []
    value = np.zeros((2, 2))
    for branch, exponent in enumerate((p, 2*p)):
        u, weights = _measure(exponent, cuts, order)
        masses.append(math.fsum(weights))
        delta = o-u[:, None]*a
        z = (delta[:, 0]+1j*delta[:, 1])/direction
        if not np.isfinite(z).all() or not np.isfinite(weights).all():
            raise ValueError('harmonic mixed coordinates or measure are unrepresentable')
        constant, linear = _constant_segment_log(z), _constant_linear_segment_log(z)
        if branch == 0:
            value[0] = [math.log(source_length)+math.fsum(weights*constant),
                        math.sqrt(3)*math.fsum(weights*linear)]
        sign = -1 if branch == 0 else 1
        zero.extend(sign*math.sqrt(3)*weights*(constant-anchor0))
        one.extend(sign*3*weights*(linear-anchor1))
    value[1] = [math.fsum(zero), math.fsum(one)]
    error = max(abs(masses[0]-1), abs(masses[1]-1),
                abs(math.sqrt(3)*(masses[1]-masses[0])))
    if error > 1e-12:
        raise ValueError('harmonic physical masses are unresolved')
    return value, error


def power_panel_harmonic_constant_log_partitioned(first, second, offset, exponent):
    """Harmonic target and uniform linear source with explicit bounded cuts.

    Planar metre geometry, exponent(0.5,1], length ratio<=1e6. Exact binary
    topology admits disjoint segments or common endpoints; crossings and
    overlaps are refused. At most128graded intervals use fixed64/128cubic
    measures. Every physical density factor is retained without weight-sum
    normalization. Refuse unresolved mass or primitive refinement. This
    explicit method is not a fallback or a complete field approximation.
    """
    p = _power(exponent)
    (a, b, o), (la, lb, lo) = _vectors(first, second, offset)
    size = max(la, lb)
    if min(la, lb)/size < 1e-6:
        raise ValueError('panel length ratio must not exceed1e6')
    if lo/4 < size:
        _require_disjoint_or_endpoint(a, b, o)
    scale = max(size, lo)
    a, b, o = a/scale, b/scale, o/scale
    if not np.any(a) or not np.any(b):
        raise ValueError('normalized panel direction is unrepresentable')
    cuts = _partition(a, b, o)
    coarse, mass0 = _mixed_block(a, b, o, p, cuts, 64, lb)
    fine, mass1 = _mixed_block(a, b, o, p, cuts, 128, lb)
    return _finish(coarse, fine, 64, len(cuts)-1, max(mass0, mass1))
