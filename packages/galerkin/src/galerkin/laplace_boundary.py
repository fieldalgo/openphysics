# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Homogeneous 2D Laplace boundary panels in a grounded rectangle.

Use ``solve_grounded_rectangle`` explicitly; this does not change the P1
volume electrostatics API. Coordinates are metres. The returned capacitance
is divided by homogeneous absolute permittivity, and is dimensionless.
"""
from dataclasses import dataclass
from numbers import Integral, Real

import numpy as np
from scipy.linalg import cho_factor, cho_solve

from . import _laplace_panels as kernel


@dataclass(frozen=True)
class RectangleBoundaryResult:
    """Read-only snapshots; surface order is input conductors then ground.

    ``capacitance_per_permittivity`` maps conductor voltage to charge divided
    by permittivity. ``current_gram[k]`` is integral(j_i*j_j ds) in 1/metre
    for unit integrated current on conductor i, with grounded return current.
    These are homogeneous static boundary factors, not frequency-domain loss.
    """

    capacitance_per_permittivity: np.ndarray
    current_gram: np.ndarray
    current_integrals: np.ndarray
    panel_count: int
    condition_bound: float
    reciprocity_error: float
    residual_error: float
    current_error: float
    matrix_refinement_error: float
    ground_refinement_error: float

    def __post_init__(self):
        for name in ("capacitance_per_permittivity", "current_gram", "current_integrals"):
            value = np.asarray(getattr(self, name), dtype=float)
            # An immutable bytes owner also prevents re-enabling writes.
            frozen = np.frombuffer(value.tobytes(), dtype=float).reshape(value.shape)
            object.__setattr__(self, name, frozen)


def _positive(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite positive real number")
    value = float(value)
    if not np.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive real number")
    return value


def _integer(value, name, low, high):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    if not low <= value <= high:
        raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    return int(value)


def _cross(a, b):
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


def _admit(polygons, width, height, count):
    if not isinstance(polygons, (list, tuple)) or not 1 <= len(polygons) <= 16:
        raise ValueError("polygons must be a list or tuple of 1..16 convex conductor boundaries")
    unit = max(width, height)
    w, h = width / unit, height / unit
    if not .25 <= w / h <= 4:
        raise ValueError("width/height must lie in [0.25, 4]")
    accepted = []
    vertices = 0
    tolerance = 128 * np.finfo(float).eps
    for polygon in polygons:
        raw = np.asarray(polygon)
        if raw.ndim != 2 or raw.shape[1] != 2 or raw.shape[0] < 3:
            raise ValueError("each polygon needs at least three 2D vertices without a closing duplicate")
        vertices += len(raw)
        if vertices * count > 2048:
            raise ValueError("total boundary panel count exceeds 2048")
        if raw.dtype.kind not in "fiu" or not np.all(np.isfinite(raw)):
            raise ValueError("polygon coordinates must be finite real numbers")
        points = np.asarray(raw, dtype=float) / unit
        if np.any(points <= 0) or np.any(points[:, 0] >= w) or np.any(points[:, 1] >= h):
            raise ValueError("conductors must lie strictly inside the rectangle")
        edges = np.roll(points, -1, axis=0) - points
        lengths = np.linalg.norm(edges, axis=1)
        if np.any(lengths <= tolerance):
            raise ValueError("polygon edge is unresolved at the domain scale")
        turns = _cross(edges, np.roll(edges, -1, axis=0))
        turn_scale = lengths * np.roll(lengths, -1)
        if np.all(turns < -tolerance * turn_scale):
            points = points[::-1].copy()
            edges = np.roll(points, -1, axis=0) - points
            lengths = np.linalg.norm(edges, axis=1)
        elif not np.all(turns > tolerance * turn_scale):
            raise ValueError("polygons must be strictly convex, without collinear edges")
        # Local turns alone also admit star polygons; every vertex must lie
        # in every oriented edge's closed interior half-plane.
        distances = _cross(edges[:, None], points[None] - points[:, None]) / lengths[:, None]
        if np.any(distances < -tolerance):
            raise ValueError("polygon boundary must be simple and convex")
        accepted.append(points.copy())
    for i, first in enumerate(accepted):
        for second in accepted[i + 1:]:
            separated = False
            for polygon in (first, second):
                edge = np.roll(polygon, -1, axis=0) - polygon
                normals = np.column_stack((-edge[:, 1], edge[:, 0]))
                normals /= np.linalg.norm(normals, axis=1)[:, None]
                p, q = first @ normals.T, second @ normals.T
                if np.any(p.max(axis=0) < q.min(axis=0) - tolerance) or np.any(q.max(axis=0) < p.min(axis=0) - tolerance):
                    separated = True
            if not separated:
                raise ValueError("conductor boundaries must be disjoint and separated")
    points = np.concatenate(accepted)
    lower, upper = points.min(axis=0), points.max(axis=0)
    if min(lower[0], w - upper[0], h - upper[1]) < np.max(upper - lower):
        raise ValueError("conductor cluster must be one cluster extent away from side/top walls")
    return accepted, unit, w, h


def _relative(a, b):
    return float(np.max(abs(a - b)) / np.max(abs(b)))


def solve_grounded_rectangle(polygons, *, width, height, panels_per_edge=32, ground_modes=512,
                             interpolation_degree=10):
    """Solve convex closed conductors over a grounded bottom in a rectangle.

    Side/top normal flux is zero. All lengths are metres. Each polygon is a
    real (n,2) vertex array, implicitly closed. No touching, nested, concave,
    zero-thickness or side/top-near conductors are accepted. There are at most
    16 conductors and 2048 total panels, with cubic endpoint grading on each
    edge. Width/height is in [0.25,4]. The total height includes all material
    layers when this homogeneous kernel is composed with a dielectric model.

    interpolation_degree explicitly selects 10, 12, 14 or 16 (default 10).
    Compare degree-2 with degree; never change the requested degree silently.
    Quadrature/interpolation and ground Fourier refinement must agree to
    1e-10; these checks do not replace panel and outer-domain convergence.
    Ill-conditioned or unresolved inputs raise ValueError without fallback.
    """
    width, height = _positive(width, "width"), _positive(height, "height")
    count = _integer(panels_per_edge, "panels_per_edge", 1, 256)
    modes = _integer(ground_modes, "ground_modes", 64, 4096)
    degree = _integer(interpolation_degree, "interpolation_degree", 10, 16)
    if degree % 2:
        raise ValueError("interpolation_degree must be one of 10, 12, 14, 16")
    polygons, unit, w, h = _admit(polygons, width, height, count)
    a, b, owners = kernel.panels(polygons, count, "cubic")
    length = np.linalg.norm(b - a, axis=1)
    if np.any(length <= 128 * np.finfo(float).eps):
        raise ValueError("graded panel length is unresolved at the domain scale")
    images = max(8, int(np.ceil((h / w) * np.log(1e14) / np.pi)) + 1)
    coarse, _ = kernel.matrix(a, b, w, h, degree=degree - 2, order=6, images=images)
    matrix, reciprocity = kernel.matrix(a, b, w, h, degree=degree, order=8, images=images + 2)
    matrix_error = _relative(coarse, matrix)
    if not np.isfinite(matrix_error) or matrix_error > 1e-10:
        raise ValueError("boundary matrix quadrature/interpolation did not converge")
    try:
        factor = cho_factor(matrix)
        inverse = cho_solve(factor, np.eye(len(a)))
        condition = float(np.linalg.norm(matrix, np.inf) * np.linalg.norm(inverse, np.inf))
        if not np.isfinite(condition) or condition >= 1e10:
            raise ValueError("boundary matrix condition bound exceeded")
        values = (owners[:, None] == np.arange(len(polygons))[None]).astype(float)
        charges = cho_solve(factor, 2 * np.pi * values)
        residual = _relative(matrix @ charges, 2 * np.pi * values)
        capacitance = values.T @ charges
        capacitance_reciprocity = _relative(capacitance, capacitance.T)
        if max(residual, capacitance_reciprocity) > 1e-10:
            raise ValueError("boundary solve residual or capacitance reciprocity exceeded")
        capacitance = (capacitance + capacitance.T) / 2
        np.linalg.cholesky(capacitance)
        current = np.linalg.solve(capacitance.T, charges.T).T
    except np.linalg.LinAlgError as exc:
        raise ValueError("boundary system must be positive definite and nonsingular") from exc
    parts, integrated = [], []
    for i in range(len(polygons)):
        use = owners == i
        j = current[use]
        parts.append(j.T @ (j / length[use, None]) / unit)
        integrated.append(j.sum(axis=0))
    ground_coarse = kernel.ground_part(a, b, current, w, h, modes=modes, order=6)
    ground = kernel.ground_part(a, b, current, w, h, modes=2 * modes, order=8)
    ground_error = _relative(ground_coarse, ground)
    if not np.isfinite(ground_error) or ground_error > 1e-10:
        raise ValueError("ground Fourier/quadrature refinement did not converge")
    parts.append(ground / unit)
    integrated.append(-current.sum(axis=0))
    integrated = np.asarray(integrated)
    expected = np.vstack((np.eye(len(polygons)), -np.ones((1, len(polygons)))))
    current_error = float(np.max(abs(integrated - expected)))
    if current_error > 1e-10 or not np.all(np.isfinite(parts)):
        raise ValueError("boundary currents must be finite and conserved")
    return RectangleBoundaryResult(
        capacitance, np.asarray(parts), integrated, len(a), condition,
        max(reciprocity, capacitance_reciprocity), residual, current_error,
        matrix_error, ground_error,
    )
