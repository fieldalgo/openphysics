# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded single-parameter impedance design with a separate mesh check."""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real

from .crosssection import CrossSection
from .document import CrossSectionDocument

__all__ = ['ImpedanceDesign', 'DesignEvaluation', 'GoalSeekError', 'seek_impedance']


@dataclass(frozen=True)
class DesignEvaluation:
    parameter: float
    impedance: float
    stage: str


@dataclass(frozen=True)
class ImpedanceDesign:
    """Successful target on both requested and refined meshes.

    impedances and residuals are in ohms; parameter has the units of the
    caller's factory. document is the requested-mesh input, not the refined
    one. This is a numerical check, not a certified manufacturing tolerance.
    """
    parameter: float
    target: float
    impedance: float
    refined_impedance: float
    quantity: str
    document: CrossSectionDocument
    history: tuple[DesignEvaluation, ...]

    @property
    def residual(self):
        return self.impedance-self.target

    @property
    def refined_residual(self):
        return self.refined_impedance-self.target

    @property
    def mesh_change(self):
        return self.refined_impedance-self.impedance


class GoalSeekError(RuntimeError):
    """A bounded search failed; history contains completed solves only."""
    def __init__(self, message, history):
        super().__init__(message)
        self.history = tuple(history)


def _positive(name, value):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value <= 0:
        raise ValueError(f'{name} must be a positive finite real number')
    return float(value)


def seek_impedance(factory, bounds, target, *, quantity='z0', tolerance=0.1,
                   mesh=None, max_evaluations=40):
    """Bisect a positive parameter range, then check a refined mesh.

    factory(parameter) returns a CrossSection. quantity is z0 (one signal) or
    z_diff (a symmetric pair). bounds have the factory parameter's units;
    target/tolerance are ohms. Factory errors propagate unchanged.

    Both endpoints must be valid. Apart from an endpoint already within
    tolerance, their residuals must bracket zero. Reserve one solve for a final
    refinement (edge_size, far_size and grade halved). Both the requested and
    refined impedances must be within tolerance of target, or GoalSeekError is
    raised. Tighten mesh options and rerun if refinement misses the target.
    No function promises monotonicity for an arbitrary factory.
    """
    if not callable(factory):
        raise TypeError('factory must be callable')
    if quantity not in ('z0', 'z_diff'):
        raise ValueError('quantity must be z0 or z_diff')
    try:
        lower, upper = bounds
    except (TypeError, ValueError) as exc:
        raise ValueError('bounds must contain two positive finite numbers') from exc
    lower, upper = _positive('lower bound', lower), _positive('upper bound', upper)
    if lower >= upper:
        raise ValueError('lower bound must be smaller than upper bound')
    target, tolerance = _positive('target', target), _positive('tolerance', tolerance)
    if isinstance(max_evaluations, bool) or not isinstance(max_evaluations, int) or max_evaluations < 3:
        raise ValueError('max_evaluations must be an integer >= 3')
    options = {} if mesh is None else dict(mesh)
    history = []

    def evaluate(parameter):
        if len(history) >= max_evaluations-1:
            raise GoalSeekError('evaluation limit reached before target convergence', history)
        section = factory(parameter)
        doc = CrossSectionDocument(section, mesh=options)
        value = impedance(doc.analyze())
        history.append(DesignEvaluation(parameter, value, 'search'))
        return value-target, doc

    def impedance(line):
        value = line.z0 if quantity == 'z0' else line.even_odd()['z_diff']
        if not math.isfinite(value) or value <= 0:
            raise GoalSeekError('solver returned invalid impedance', history)
        return float(value)

    fl, dl = evaluate(lower)
    fu, du = evaluate(upper)
    if abs(fl) <= tolerance or abs(fu) <= tolerance:
        x, residual, doc = (lower, fl, dl) if abs(fl) <= abs(fu) else (upper, fu, du)
    else:
        if (fl > 0) == (fu > 0):
            raise GoalSeekError('target is not bracketed by the endpoint impedances', history)
        while True:
            x = lower+(upper-lower)/2
            if x == lower or x == upper:
                raise GoalSeekError('parameter resolution exhausted before target convergence', history)
            residual, doc = evaluate(x)
            if abs(residual) <= tolerance:
                break
            if (residual > 0) == (fl > 0):
                lower, fl = x, residual
            else:
                upper = x

    section = doc.section
    fine = section.mesh_settings(**doc.mesh_options)
    for key in ('edge_size', 'far_size', 'grade'):
        fine[key] /= 2
    refined = impedance(section.analyze(**fine))
    history.append(DesignEvaluation(x, refined, 'refinement'))
    if abs(refined-target) > tolerance:
        raise GoalSeekError('refined mesh misses target; tighten mesh settings and rerun', history)
    return ImpedanceDesign(x, target, residual+target, refined, quantity, doc, tuple(history))
