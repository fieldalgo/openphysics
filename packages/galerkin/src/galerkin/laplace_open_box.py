# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Homogeneous 2D Laplace panels in a rectangle with zero normal flux on every wall.

Internal module, consistent units: not part of galerkin's public API (the ``__all__``
of its public modules).

There is no grounded plane: the reference is one or more conductors held at
zero potential (for example the grounds of an unbacked coplanar line). This
explicit API does not change the grounded-bottom, two-ground or volume solvers.
Coordinates are metres; capacitance divided by permittivity is dimensionless.
"""
from dataclasses import dataclass
from numbers import Integral

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.linalg import cho_factor, cho_solve

from . import _laplace_panels as kernel

__all__ = ['OpenRectangleResult', 'solve_open_rectangle']

MAX_ASPECT = 16


@dataclass(frozen=True)
class OpenRectangleResult:
    """Read-only snapshots for conductors in a rectangle with Neumann walls.

    ``capacitance_per_permittivity`` maps signal voltages to signal charges,
    divided by permittivity, with every ground conductor at zero voltage.
    ``current_gram[k]`` is integral(j_i*j_j ds) over input conductor k, in
    1/metre, for unit integrated current on signal i and its return on the
    grounds. ``current_integrals[k, i]`` is the signed integrated current on
    conductor k. Walls carry no current. These are homogeneous static
    boundary factors, not frequency-domain loss.
    """

    capacitance_per_permittivity: np.ndarray
    current_gram: np.ndarray
    current_integrals: np.ndarray
    signal_indices: tuple
    ground_indices: tuple
    panel_count: int
    condition_bound: float
    reciprocity_error: float
    residual_error: float
    charge_sum_error: float
    current_error: float
    matrix_refinement_error: float
    minimum_scaled_eigenvalue: float
    smooth_interpolation_boxes: int = 1

    def __post_init__(self):
        for name in ('capacitance_per_permittivity', 'current_gram', 'current_integrals'):
            value = np.asarray(getattr(self, name), dtype=float)
            frozen = np.frombuffer(value.tobytes(), dtype=float).reshape(value.shape)
            object.__setattr__(self, name, frozen)


def _strip(dx, v, k):
    """-1/2 log(cosh(k dx) - cos v) of the 2H-periodic strip, smooth in dx for v != 0 mod 2pi."""
    u = np.abs(k * dx)
    small = u < 20
    near = -0.5 * np.log(2 * np.sinh(np.where(small, u, 0.0) / 2) ** 2 + 2 * np.sin(v / 2) ** 2)
    e = np.exp(-u)
    far = -u / 2 + 0.5 * np.log(2) - 0.5 * np.log1p(-2 * e * np.cos(v) + e * e)
    return np.where(small, near, far)


def _strip_tail(dx, v, k):
    """_strip without its linear far-field part -|k dx|/2 + log(2)/2."""
    e = np.exp(-np.abs(k * dx))
    return -0.5 * np.log1p(-2 * e * np.cos(v) + e * e)


def _direct_minus_log(dx, dy, k):
    """_strip(dx, k dy, k) + log|(dx, dy)|, up to a constant, without cancellation."""
    u, v = k * dx, k * dy
    sinhc = np.ones_like(u)
    np.divide(np.sinh(u / 2), u / 2, out=sinhc, where=u != 0)
    sinc = np.sinc(v / (2 * np.pi))
    denominator = u * u + v * v
    ratio = np.ones_like(denominator)
    np.divide(u * u * sinhc * sinhc + v * v * sinc * sinc, denominator, out=ratio, where=denominator != 0)
    return -0.5 * np.log(ratio)


def smooth_neumann(targets, sources, width, height, images):
    """Neumann rectangle kernel minus -log|r-r'|, up to terms f(r)+f(r').

    The 2H-periodic strip with images at y' and -y' has zero normal flux on
    both horizontal walls; mirrored copies at 2nW +/- x' add the side walls.
    The linear far field of every copy except the direct one is separable,
    so it is omitted; with zero total charge a separable term only shifts the
    common potential. ``images`` is the number of periods on each side.
    """
    k = np.pi / height
    dx = targets[:, None, 0] - sources[None, :, 0]
    sx = targets[:, None, 0] + sources[None, :, 0]
    dy = targets[:, None, 1] - sources[None, :, 1]
    vm = k * dy
    vp = k * (targets[:, None, 1] + sources[None, :, 1])
    out = _direct_minus_log(dx, dy, k) + _strip(dx, vp, k)
    for n in range(-images, images + 1):
        if n:
            out += _strip_tail(dx - 2 * n * width, vm, k) + _strip_tail(dx - 2 * n * width, vp, k)
        out += _strip_tail(sx - 2 * n * width, vm, k) + _strip_tail(sx - 2 * n * width, vp, k)
    return out


def point_kernel(targets, sources, width, height, images=None):
    """2*pi times the Neumann rectangle Green function, up to terms f(r)+f(r')."""
    targets = np.asarray(targets, dtype=float)
    sources = np.asarray(sources, dtype=float)
    distance = np.linalg.norm(targets[:, None] - sources[None], axis=-1)
    if np.any(distance == 0):
        raise ValueError('point Green function is singular at its source')
    if images is None:
        images = _images(width, height) + 2
    return -np.log(distance) + smooth_neumann(targets, sources, width, height, images)


def _images(width, height):
    return max(8, int(np.ceil(height / width * np.log(1e14) / np.pi)) + 1)


def _free_matrix(a, b, *, order):
    """Galerkin mean of -log|r-r'| over target and source panels."""
    length = np.linalg.norm(b - a, axis=1)
    mid = (a + b) / 2
    near = np.linalg.norm(mid[:, None] - mid[None], axis=-1) <= 8 * np.maximum(length[:, None], length[None])
    value = np.zeros((len(a), len(a)))
    nodes, weights = leggauss(order)
    for u, wu in zip(nodes, weights / 2):
        target = a + (u + 1) / 2 * (b - a)
        for v, wv in zip(nodes, weights / 2):
            source = a + (v + 1) / 2 * (b - a)
            dx = target[:, None, 0] - source[None, :, 0]
            dy = target[:, None, 1] - source[None, :, 1]
            value -= wu * wv * 0.5 * np.log(np.where(near, 1.0, dx * dx + dy * dy))
    i, j = np.nonzero(near)
    value[i, j] = -kernel.mean_log_pairs(a[i], b[i], a[j], b[j], order=order)
    return value


def _matrix(a, b, width, height, *, degree, order, images, labels):
    smooth = kernel.blockwise(a, b, labels, width, height, degree,
                               lambda t, s: smooth_neumann(t, s, width, height, images))
    result = _free_matrix(a, b, order=order) + smooth
    reciprocity = kernel.relative(result, result.T)
    if not np.isfinite(reciprocity) or reciprocity > 1e-10:
        raise ValueError('raw matrix reciprocity failed')
    return (result + result.T) / 2, reciprocity


def _grounds(grounds, count):
    if isinstance(grounds, (str, bytes)) or not hasattr(grounds, '__iter__'):
        raise ValueError('grounds must be a sequence of conductor indices')
    out = []
    for index in grounds:
        if isinstance(index, (bool, np.bool_)) or not isinstance(index, Integral) or not 0 <= index < count:
            raise ValueError(f'grounds must hold distinct conductor indices in [0, {count - 1}]')
        out.append(int(index))
    if len(set(out)) != len(out) or not out:
        raise ValueError('grounds must hold at least one distinct conductor index')
    if len(out) == count:
        raise ValueError('at least one conductor must be a signal')
    return tuple(sorted(out))


def _null_basis(n):
    """Orthonormal basis of the zero-sum subspace (Householder reflection of e1 onto 1/sqrt(n))."""
    v = np.full(n, 1 / np.sqrt(n))
    v[0] += 1
    v /= np.linalg.norm(v)
    return (np.eye(n) - 2 * np.outer(v, v))[:, 1:]


def solve_open_rectangle(polygons, *, width, height, grounds, panels_per_edge=32, interpolation_degree=12):
    """Solve convex closed conductors in a rectangle whose four walls have zero normal flux.

    ``grounds`` lists the input conductors held at zero potential (at least
    one, and at least one signal remains). The walls are not grounded, so the
    total charge is zero and the grounds are the only return path. Accept 1..16
    disjoint strictly convex polygons strictly inside a rectangle with
    width/height in [0.25, 16], at most 2048 cubic-graded panels in total. A
    cluster closer to any wall than its extent is interpolated on wall-scaled
    boxes (at most 256; closer conductors are refused).

    interpolation_degree explicitly selects 10, 12, 14 or 16 (default 12) and
    is compared with degree-2; matrix refinement, reciprocity, residual,
    charge-sum, energy and current-conservation checks use 1e-10 and the
    reduced matrix condition bound must be below 1e10. These checks do not
    establish panel or outer-domain convergence. No fallback occurs.
    """
    width, height = kernel.positive(width, 'width'), kernel.positive(height, 'height')
    count = kernel.integer(panels_per_edge, 'panels_per_edge', 1, 256)
    degree = kernel.integer(interpolation_degree, 'interpolation_degree', 10, 16)
    if degree % 2:
        raise ValueError('interpolation_degree must be one of 10, 12, 14, 16')
    polygons, unit, w, h = kernel.admit_polygons(polygons, width, height, count, max_aspect=MAX_ASPECT)
    grounded = _grounds(grounds, len(polygons))
    signals = tuple(i for i in range(len(polygons)) if i not in grounded)
    points = np.concatenate(polygons)
    lower, upper = points.min(axis=0), points.max(axis=0)
    clear = bool(kernel.wall_distance(lower, upper, w, h, bottom=True) >= np.max(upper - lower))
    if not clear and kernel.wall_box_count(polygons, w, h, bottom=True) > kernel.WALL_BOXES:
        raise ValueError('conductors are too close to the walls for wall-scaled interpolation')
    a, b, owners = kernel.panels(polygons, count, 'cubic')
    length = np.linalg.norm(b - a, axis=1)
    if np.any(length <= 128 * np.finfo(float).eps):
        raise ValueError('graded panel length is unresolved at the domain scale')
    labels = np.zeros(len(a), dtype=int) if clear else kernel.wall_labels(a, b, owners, w, h, bottom=True)
    images = _images(w, h)
    coarse, _ = _matrix(a, b, w, h, degree=degree - 2, order=6, images=images, labels=labels)
    matrix, reciprocity = _matrix(a, b, w, h, degree=degree, order=8, images=images + 2, labels=labels)
    matrix_error = kernel.relative(coarse, matrix)
    if not np.isfinite(matrix_error) or matrix_error > 1e-10:
        raise ValueError('boundary matrix quadrature/interpolation did not converge')
    basis = _null_basis(len(a))
    reduced = basis.T @ matrix @ basis
    reduced = (reduced + reduced.T) / 2
    values = (owners[:, None] == np.asarray(signals)[None]).astype(float)
    rhs = 2 * np.pi * values
    try:
        factor = cho_factor(reduced)
        inverse = cho_solve(factor, np.eye(len(reduced)))
        condition = float(np.linalg.norm(reduced, np.inf) * np.linalg.norm(inverse, np.inf))
        if not np.isfinite(condition) or condition >= 1e10:
            raise ValueError('boundary matrix condition bound exceeded')
        charges = basis @ cho_solve(factor, basis.T @ rhs)
        constant = (rhs - matrix @ charges).mean(axis=0)
        residual = kernel.relative(matrix @ charges + constant, rhs)
        selection = (owners[:, None] == np.asarray(signals)[None]).astype(float)
        capacitance = selection.T @ charges
        charge_sum = float(np.max(abs(charges.sum(axis=0))) / np.max(abs(capacitance)))
        symmetry = kernel.relative(capacitance, capacitance.T)
        energy = kernel.relative(charges.T @ matrix @ charges / (2 * np.pi), capacitance)
        if max(residual, charge_sum, symmetry, energy) > 1e-10:
            raise ValueError('boundary solve residual, charge sum or capacitance reciprocity exceeded')
        capacitance = (capacitance + capacitance.T) / 2
        np.linalg.cholesky(capacitance)
        current = np.linalg.solve(capacitance.T, charges.T).T
    except np.linalg.LinAlgError as exc:
        raise ValueError('boundary system must be positive definite on zero total charge') from exc
    parts, integrated = [], []
    for i in range(len(polygons)):
        use = owners == i
        j = current[use]
        parts.append(j.T @ (j / length[use, None]) / unit)
        integrated.append(j.sum(axis=0))
    parts, integrated = np.asarray(parts), np.asarray(integrated)
    current_error = max(float(np.max(abs(integrated[list(signals)] - np.eye(len(signals))))),
                        float(np.max(abs(integrated.sum(axis=0)))))
    if not np.isfinite(current_error) or current_error > 1e-10 or not np.all(np.isfinite(parts)):
        raise ValueError('boundary currents must be finite and conserved')
    scale = np.max(abs(parts), axis=(-1, -2))
    eigenvalues = np.linalg.eigvalsh(parts)
    scaled = np.divide(eigenvalues, scale[:, None], out=np.zeros_like(eigenvalues), where=scale[:, None] != 0)
    minimum = float(np.min(scaled))
    if minimum < -1e-10:
        raise ValueError('boundary current Gram must be positive semidefinite')
    return OpenRectangleResult(
        capacitance, parts, integrated, signals, grounded, len(a), condition,
        max(reciprocity, symmetry), residual, charge_sum, current_error, matrix_error, minimum,
        int(labels.max() + 1))
