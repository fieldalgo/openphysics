# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicitly partitioned mixed linear-power logarithmic panel blocks.

Internal module, consistent units: not part of galerkin's public API (the ``__all__``
of its public modules).
"""
from dataclasses import dataclass
import math

import numpy as np

from .laplace_corner import (
    constant_linear_segment_log as _constant_linear_segment_log,
    constant_segment_log as _constant_segment_log,
    frozen as _frozen,
    graded_power_rule as _graded_power_rule,
    power as _power,
    require_disjoint_or_endpoint as _require_disjoint_or_endpoint)


def _partition(first, second, offset):
    direction = complex(*first)
    points = [0.0, 1.0]
    for endpoint in (offset, offset + second):
        coordinate = complex(*endpoint) / direction
        if not math.isfinite(coordinate.real) or not math.isfinite(coordinate.imag):
            raise ValueError("partition coordinates are unrepresentable")
        # This is a quadrature parameter, not a change to an endpoint.
        center = min(1.0, max(0.0, coordinate.real))
        radius = math.hypot(coordinate.real - center, coordinate.imag)
        points.append(center)
        if radius == 0:
            continue
        while radius < 1:
            for point in (center - radius, center + radius):
                if 0 < point < 1:
                    points.append(point)
            if len(set(points)) > 129:
                raise ValueError("partition exceeds 128 intervals")
            radius *= 2
    ordered = sorted(set(points))
    # Bound density variation away from the target's singular origin.
    # No cut is removed, and no physical weight is rescaled.
    graded = [ordered[0]]
    extras = 0
    for left, right in zip(ordered, ordered[1:]):
        intermediate = []
        upper = right
        while left > 0 and upper > 2 * left:
            upper /= 2
            intermediate.append(upper)
            extras += 1
            if len(ordered) + extras > 129:
                raise ValueError("partition exceeds 128 intervals")
        graded.extend(reversed(intermediate))
        graded.append(right)
    return np.asarray(graded)


def _integrate(first, second, offset, exponent, cuts, order, source_length):
    points, weights = [], []
    for left, right in zip(cuts, cuts[1:]):
        span = right - left
        if left == 0:
            nodes, physical = _graded_power_rule(exponent, order)
            parameter = span * nodes
            physical = physical * span**exponent
        else:
            nodes, physical = _graded_power_rule(1.0, order)
            parameter = left + span * nodes
            physical = physical * exponent * parameter**(exponent - 1) * span
        points.extend(parameter)
        weights.extend(physical)
    u, weights = np.asarray(points), np.asarray(weights)
    p = exponent
    zero_mass = weights * math.sqrt(p * (p + 2)) * ((p + 1) / p * u - 1)
    mass_error = max(abs(math.fsum(weights) - 1), abs(math.fsum(zero_mass)))
    if not np.isfinite(weights).all() or mass_error > 1e-12:
        raise ValueError("partitioned target mass is unresolved")
    direction = complex(*second)
    anchor = complex(*offset) / direction
    anchor0 = float(_constant_segment_log(anchor))
    anchor1 = float(_constant_linear_segment_log(anchor))
    delta = offset - u[:, None] * first
    z = (delta[:, 0] + 1j * delta[:, 1]) / direction
    if not np.isfinite(z).all():
        raise ValueError("partitioned source coordinates are unrepresentable")
    constant = _constant_segment_log(z)
    linear = _constant_linear_segment_log(z)
    value = np.array([
        [math.log(source_length) + math.fsum(weights * constant),
         math.sqrt(3) * math.fsum(weights * linear)],
        [math.fsum(zero_mass * (constant - anchor0)),
         math.sqrt(3) * math.fsum(zero_mass * (linear - anchor1))],
    ])
    return value, mass_error


@dataclass(frozen=True)
class PartitionedPowerPanelLinearLogResult:
    """Immutable 2x2 physical-mode means and the explicit quadrature budget."""

    mean_log_distance: np.ndarray
    coarse_mean_log_distance: np.ndarray
    quadrature_order: int
    subintervals: int
    mass_error: float

    def __post_init__(self):
        for name in ("mean_log_distance", "coarse_mean_log_distance"):
            object.__setattr__(self, name, _frozen(getattr(self, name)).reshape(2, 2))


def power_panel_linear_constant_log_partitioned(first, second, offset, exponent):
    """Integrate power-target/unit-source linear modes on bounded parameter cuts.

    The target is [0, first]; the source is [offset, offset+second], in planar
    metres. The target exponent lies in (0.5, 1], the source exponent is 1,
    and physical length ratio is at most 1e6. Disjoint segments and common
    endpoints are allowed; interior crossings and overlaps are refused by
    exact binary-input topology. Modes have analytic masses [1, 0].

    Project source endpoints onto the target line only to select integration
    cuts. Add dyadic distances and grade positive intervals to upper/lower
    <=2. At most 128 subintervals use fixed 64/128 double-ended cubic rules.
    The first interval retains its power measure; subsequent ones retain
    the physical power density. Weights, geometry and returned moments are
    never normalized or clipped. Refuse unresolved analytic masses or
    entrywise refinement above 1e-12*max(1, abs(fine)).

    This separate method is not a fallback for the existing unpartitioned
    primitive. Its finite resource bound can refuse valid geometry; a pass
    does not establish complete field or physical accuracy.
    """
    p = _power(exponent)
    vectors = []
    for value in (first, second, offset):
        raw = np.asarray(value)
        if raw.shape != (2,) or raw.dtype.kind not in "fiu" or not np.isfinite(raw).all():
            raise ValueError("finite real planar vectors are required")
        vectors.append(np.asarray(raw, dtype=float))
    a, b, o = vectors
    la, lb, lo = (math.hypot(*v) for v in vectors)
    if min(la, lb) <= 0 or not all(math.isfinite(x) for x in (la, lb, lo)):
        raise ValueError("panel geometry is unrepresentable")
    size = max(la, lb)
    if min(la, lb) / size < 1e-6:
        raise ValueError("panel length ratio exceeds 1e6")
    if lo / 4 < size:
        _require_disjoint_or_endpoint(a, b, o)
    scale = max(size, lo)
    a, b, o = a / scale, b / scale, o / scale
    if not np.any(a) or not np.any(b):
        raise ValueError("normalized directions are unrepresentable")
    cuts = _partition(a, b, o)
    coarse, mass0 = _integrate(a, b, o, p, cuts, 64, lb)
    fine, mass1 = _integrate(a, b, o, p, cuts, 128, lb)
    if (not np.isfinite(coarse).all() or not np.isfinite(fine).all()
            or np.any(abs(fine - coarse) > 1e-12 * np.maximum(1, abs(fine)))):
        raise ValueError("partitioned power-constant quadrature did not converge")
    return PartitionedPowerPanelLinearLogResult(fine, coarse, 64, len(cuts) - 1,
                                                max(mass0, mass1))


__all__ = ["PartitionedPowerPanelLinearLogResult", "power_panel_linear_constant_log_partitioned"]


# Public names of helpers shared with other galerkin panel modules (tests/galerkin/test_layers.py).
partition = _partition
