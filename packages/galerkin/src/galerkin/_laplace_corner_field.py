# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Internal corner-field assembly; only admitted panel geometry reaches helpers.

Local offsets and exact constant moments preserve small cross-current terms.
Scalar per-pair reductions are retained within bounded vectorized batches.
This module is internal; use laplace_two_ground's explicit solver entry point.
"""
from functools import lru_cache
import math
import numpy as np
from scipy.linalg import cho_factor, cho_solve
from . import _laplace_panels as kernel
from . import laplace_two_ground as two
from .laplace_corner import power_panel_quadrature, power_panel_gram
from .laplace_corner import (
    graded_power_rule as _graded_power_rule,
    constant_segment_log as _constant_segment_log)
from .laplace_corner_geometry import prepare_two_ground_corner_panels
from .laplace_corner_assembly import (
    constant_half as _constant_half,
    offsets as _offsets,
    weighted_pair as _weighted_pair)
from .dense_residual import bounded_dense_residual

__all__ = []


def _constant_means(a, b, offset):
    a, b, o = [np.asarray(x, dtype=float) for x in (a, b, offset)]
    assert a.shape == b.shape == o.shape and a.ndim == 2 and (a.shape[1] == 2)
    if not all((np.isfinite(x).all() for x in (a, b, o))):
        raise ValueError('finite geometry required')
    la, lb = (np.hypot(*a.T), np.hypot(*b.T))
    if np.any(np.minimum(la, lb) <= 0) or np.any(np.minimum(la, lb) / np.maximum(la, lb) < 1e-06):
        raise ValueError('unresolved panel length or ratio')
    same = np.all(o == 0, axis=1) & np.all(a == b, axis=1) | np.all(o == a, axis=1) & np.all(b == -a, axis=1)
    coarse = np.empty(len(a))
    fine = np.empty(len(a))
    coarse[same] = fine[same] = np.log(la[same]) - 1.5
    selected = np.flatnonzero(~same)
    for first in range(0, len(selected), 512):
        ix = selected[first:first + 512]
        swap = la[ix] > lb[ix]
        aa = np.where(swap[:, None], b[ix], a[ix])
        bb = np.where(swap[:, None], a[ix], b[ix])
        oo = np.where(swap[:, None], -o[ix], o[ix])
        source_length = np.maximum(la[ix], lb[ix])
        scale = np.maximum(source_length, np.hypot(*oo.T))
        aa = aa / scale[:, None]
        bb = bb / scale[:, None]
        oo = oo / scale[:, None]
        direction = bb[:, 0] + 1j * bb[:, 1]
        estimates = []
        for order in (64, 128):
            u, w = _graded_power_rule(1.0, order)
            if abs(w.sum() - 1) > 1e-12:
                raise ValueError('quadrature normalization failed')
            delta = oo[None] - u[:, None, None] * aa[None]
            z = (delta[:, :, 0] + 1j * delta[:, :, 1]) / direction[None]
            if not np.isfinite(z).all():
                raise ValueError('source coordinates unresolved')
            estimates.append(np.log(source_length) + w @ _constant_segment_log(z))
        x, y = estimates
        if not np.isfinite(x).all() or not np.isfinite(y).all() or np.any(abs(x - y) > 1e-12 * np.maximum(1, abs(y))):
            raise ValueError('constant panel integration did not converge')
        coarse[ix] = x
        fine[ix] = y
    return (coarse, fine)

def _power_constant_means(a, b, offset, image_offset, heights, p):
    a, b, o, oi, h = [np.asarray(x, dtype=float) for x in (a, b, offset, image_offset, heights)]
    if not (a.shape == b.shape == o.shape == oi.shape == h.shape and a.ndim == 2 and (a.shape[1] == 2)):
        raise ValueError('pair arrays required')
    if not all((np.isfinite(x).all() for x in (a, b, o, oi, h))) or not math.isfinite(p) or (not 0.5 < p <= 1):
        raise ValueError('finite admitted pairs required')
    if len(a) > 128:
        raise ValueError('batch limit is 128 pairs')
    scales = []
    for aa, bb, oo, image, hh in zip(a, b, o, oi, h):
        la, lb = (math.hypot(*aa), math.hypot(*bb))
        if min(la, lb) <= 0 or min(la, lb) / max(la, lb) < 1e-06:
            raise ValueError('unresolved lengths')
        if min(*hh, hh[0] + aa[1], hh[1] + bb[1]) <= 0:
            raise ValueError('panels must be above ground')
        scales.append(max(la, lb, math.hypot(*oo), math.hypot(*image), float(max(hh))))
    scale = np.array(scales)[:, None]
    a, b, o, oi, h = [x / scale for x in (a, b, o, oi, h)]
    direction = np.empty(len(b), dtype=complex)
    direction.real = b[:, 0]
    direction.imag = b[:, 1]
    image_direction = np.conj(direction)

    def integrand(u):
        u = np.atleast_1d(u)
        real = o[:, None] - u[None, :, None] * a[:, None]
        image = oi[:, None] - u[None, :, None] * a[:, None]
        z = (real[:, :, 0] + 1j * real[:, :, 1]) / direction[:, None]
        zi = (image[:, :, 0] + 1j * image[:, :, 1]) / image_direction[:, None]
        far = (abs(z) > 2) & (abs(zi) > 2)
        out = np.empty(z.shape)
        out[~far] = _constant_segment_log(zi[~far]) - _constant_segment_log(z[~far])
        if np.any(far):
            inverse, ii = (1 / z[far], 1 / zi[far])
            power, ip = (inverse.copy(), ii.copy())
            series = np.zeros(len(inverse), dtype=complex)
            for k in range(1, 49):
                series += (-1) ** (k + 1) / (k * (k + 1)) * (ip - power)
                power *= inverse
                ip *= ii
            yt = (h[:, 0, None] + u[None, :] * a[:, 1, None])[far]
            ys = np.broadcast_to(h[:, 1, None], far.shape)[far]
            distance = np.sum(real[far] * real[far], axis=1)
            out[far] = 0.5 * np.log1p(4 * yt * ys / distance) + series.real
        return out
    anchor = integrand([0.0])[:, 0]
    estimates = []
    for order in (64, 128):
        u, w = _graded_power_rule(p, order)
        if abs(w.sum() - 1) > 1e-12:
            raise ValueError('quadrature normalization failed')
        differences = integrand(u) - anchor[:, None]
        estimates.append(np.array([float(value + w @ row) for value, row in zip(anchor, differences)]))
    coarse, fine = estimates
    if not all((np.isfinite(x).all() for x in estimates)) or np.any(abs(fine - coarse) > 1e-12 * np.maximum(1, abs(fine))):
        raise ValueError('half-space quadrature did not converge')
    return (coarse, fine)

def _half(a, b, p, g):
    coarse, fine = (_constant_half(a, g, 6), _constant_half(a, g, 8))
    v = g['direction']
    length = np.linalg.norm(v, axis=1)
    mid = a + 0.5 * v
    limit = 8 * np.maximum(length[:, None], length[None])
    near = (np.linalg.norm(mid[:, None] - mid[None], axis=-1) <= limit) | (np.linalg.norm(mid[:, None] - mid[None] * [1.0, -1.0], axis=-1) <= limit)
    near &= (p[:, None] == 1) & (p[None, :] == 1)
    i, j = np.nonzero(near)
    real = _constant_means(v[i], v[j], _offsets(g, i, j))
    image = _constant_means(v[i], v[j] * [1.0, -1.0], _offsets(g, i, j, True))
    coarse[i, j] = image[0] - real[0]
    fine[i, j] = image[1] - real[1]
    selected = set(map(int, np.flatnonzero(p < 1)))
    constant = np.flatnonzero(p == 1)
    for i in sorted(selected):
        for first in range(0, len(constant), 128):
            j = constant[first:first + 128]
            ii = np.full(len(j), i)
            x, y = _power_constant_means(g['direction'][ii], g['direction'][j], _offsets(g, ii, j), _offsets(g, ii, j, True), np.column_stack((a[ii, 1], a[j, 1])), p[i])
            coarse[i, j] = x
            fine[i, j] = y
            coarse[j, i] = x
            fine[j, i] = y
        for j in sorted(selected):
            real = _weighted_pair(g, i, j, p[i], p[j])
            image = _weighted_pair(g, i, j, p[i], p[j], True)
            coarse[i, j] = image[0] - real[0]
            fine[i, j] = image[1] - real[1]
    return (coarse, fine)

def _mixed_difference(matrix, left, right, anchor):
    total = np.zeros_like(matrix)
    correction = np.zeros_like(matrix)
    for value in (matrix, -left[:, None], -right[None, :], anchor):
        updated = total + value
        correction += np.where(abs(total) >= abs(value), total - updated + value, value - updated + total)
        total = updated
    return total + correction

def _centered_projection(_projection, matrix, left, right, anchor):
    if np.max(abs(_projection.sum(axis=1) - 1)) > 1e-12:
        raise ValueError('interpolant constant moment unresolved')
    mixed = _mixed_difference(matrix, left, right, anchor)
    out = _projection @ mixed @ _projection.T
    first = _projection @ (left - anchor)
    second = _projection @ (right - anchor)
    out += first[:, None]
    out += second[None, :]
    out += anchor
    if not np.isfinite(out).all():
        raise ValueError('smooth projection is not finite')
    return out

def _smooth(a, b, grid, _projection, width, height, images):
    from galerkin import laplace_two_ground as two
    points = np.concatenate((a, b))
    center = (points.min(axis=0) + points.max(axis=0)) / 2
    matrix = two.smooth(grid, grid, width, height, images)
    left = two.smooth(grid, center[None], width, height, images)[:, 0]
    right = two.smooth(center[None], grid, width, height, images)[0]
    anchor = float(two.smooth(center[None], center[None], width, height, images)[0, 0])
    return _centered_projection(_projection, matrix, left, right, anchor)

@lru_cache(maxsize=128)
def _rule(p, order):
    return power_panel_quadrature(p, order)

def _projection(a, b, p, degree, direction):
    allpoints = np.concatenate((a, b))
    lower, upper = (allpoints.min(axis=0), allpoints.max(axis=0))
    grid, _ = kernel.tensor_basis((a + b) / 2, lower, upper, degree)
    result = np.zeros((len(a), degree ** 2))
    for exponent in np.unique(p):
        mask = p == exponent
        x, weights = _rule(float(exponent), degree)
        for u, w in zip(x, weights):
            _, values = kernel.tensor_basis(a[mask] + u * direction[mask], lower, upper, degree)
            result[mask] += w * values
    return (grid, result)

def _ground(a, b, p, charges, width, height, modes, order, direction):
    k = np.arange(1, modes + 1) * np.pi / width
    integrated = np.zeros((2, modes + 1, len(a)))
    for exponent in np.unique(p):
        mask = p == exponent
        xx, weights = _rule(float(exponent), order)
        local = np.zeros((2, modes + 1, np.count_nonzero(mask)))
        for u, w in zip(xx, weights):
            points = a[mask] + u * direction[mask]
            x, y = points.T
            local[0, 0] += w * (1 - y / height) / width
            local[1, 0] += w * y / (height * width)
            common = 2 / width * np.cos(k[:, None] * x) / (1 - np.exp(-2 * k[:, None] * height))
            local[0, 1:] += w * common * np.exp(-k[:, None] * y) * (1 - np.exp(-2 * k[:, None] * (height - y)))
            local[1, 1:] += w * common * np.exp(-k[:, None] * (height - y)) * (1 - np.exp(-2 * k[:, None] * y))
        integrated[:, :, mask] = local
    return -integrated @ charges


def _require(error, message, limit=1e-10):
    if not np.isfinite(error) or error > limit:
        raise ValueError(f'{message}: {error}')


def _gram_checks(parts):
    if not np.isfinite(parts).all():
        raise ValueError('current Gram must be finite')
    symmetry = two.entrywise_relative(parts, parts.swapaxes(-1, -2))
    _require(symmetry, 'current Gram reciprocity failed')
    scale = np.max(abs(parts), axis=(-1, -2))
    eigenvalues = np.linalg.eigvalsh(parts)
    scaled = np.divide(eigenvalues, scale[:, None], out=np.zeros_like(eigenvalues),
                       where=scale[:, None] != 0)
    minimum = float(np.min(scaled))
    if minimum < -1e-10:
        raise ValueError('current Gram must be positive semidefinite')
    return symmetry, minimum


def solve(polygons, *, width, height, panels_per_edge, ground_modes,
          interpolation_degree):
    """Internal implementation of the explicitly bounded all-active solve."""
    if not isinstance(polygons, (list, tuple)) or not 1 <= len(polygons) <= 2:
        raise ValueError('corner field requires one or two all-active conductors')
    width, height = two.positive(width, 'width'), two.positive(height, 'height')
    count = two.integer(panels_per_edge, 'panels_per_edge', 16, 512)
    modes = two.integer(ground_modes, 'ground_modes', 64, 4096)
    degree = two.integer(interpolation_degree, 'interpolation_degree', 24, 24)
    if count % 2 or modes % 2:
        raise ValueError('panel subdivisions and ground modes must be even')
    geometry = prepare_two_ground_corner_panels(polygons, width=width,
        height=height, panels_per_edge=count)
    if geometry.panel_count > 4096:
        raise ValueError('corner field panel budget exceeds 4096')
    a, b = geometry.normalized_starts, geometry.normalized_ends
    p, owners, faces = geometry.exponents, geometry.owners, geometry.faces
    g = dict(anchor=geometry.normalized_anchors,
             local=geometry.normalized_local_starts,
             direction=geometry.normalized_directions,
             starts=geometry.endpoint_ids[:, 0], ends=geometry.endpoint_ids[:, 1])
    direction = g['direction']
    length = np.linalg.norm(direction, axis=1)
    unit, w, h = (geometry.length_unit_m, geometry.normalized_width,
                  geometry.normalized_height)
    halves = _half(a, b, p, g)
    matrices, reciprocity = [], []
    images = max(8, int(np.ceil(h / w * np.log(1e14) / np.pi)) + 1)
    for half_matrix, d, im in zip(halves, (degree-4, degree), (images, images+2)):
        grid, project = _projection(a, b, p, d, direction)
        matrix = half_matrix + _smooth(a, b, grid, project, w, h, im)
        if not np.isfinite(matrix).all():
            raise ValueError('corner field matrix must be finite')
        reciprocity.append(float(np.max(abs(matrix-matrix.T))/np.max(abs(matrix))))
        matrices.append((matrix+matrix.T)/2)
    matrix_error = float(np.max(abs(matrices[0]-matrices[1]))/np.max(abs(matrices[1])))
    _require(max(matrix_error, *reciprocity), 'corner matrix refinement/reciprocity failed')
    matrix = matrices[1]
    factor = cho_factor(matrix)
    inverse = cho_solve(factor, np.eye(len(a)))
    condition = float(np.linalg.norm(matrix, np.inf)*np.linalg.norm(inverse, np.inf))
    if not np.isfinite(condition) or condition >= 1e10:
        raise ValueError('corner field condition bound exceeded')
    n = len(polygons)
    values = (owners[:, None] == np.arange(n)).astype(float)
    q = cho_solve(factor, 2*np.pi*values)
    for _ in range(2):
        residual = bounded_dense_residual(matrix, q, 2*np.pi*values)
        q = q + cho_solve(factor, residual)
    compensated = float(np.max(abs(bounded_dense_residual(matrix, q, 2*np.pi*values)))/(2*np.pi))
    capacitance = values.T @ q
    direct = float(np.max(abs(matrix@q-2*np.pi*values))/(2*np.pi))
    energy = two.entrywise_relative(q.T@matrix@q/(2*np.pi), capacitance)
    cap_reciprocity = two.entrywise_relative(capacitance, capacitance.T)
    _require(max(compensated, direct, energy, cap_reciprocity), 'corner capacitance consistency failed')
    np.linalg.cholesky((capacitance+capacitance.T)/2)
    # Normalize charges before the Gram products; no fixed-ground reduction.
    currents = q @ np.linalg.inv(capacitance)
    gram = np.array([power_panel_gram(l*unit, exponent) for l, exponent in zip(length, p)])
    face_parts = np.array([currents[faces == j].T @ (currents[faces == j]*gram[faces == j, None])
                           for j in np.unique(faces)])
    whole_parts = np.array([currents[owners == j].T @ (currents[owners == j]*gram[owners == j, None])
                            for j in range(n)])
    integrals = np.array([currents[owners == j].sum(axis=0) for j in range(n)])
    face_integrals = np.array([currents[faces == j].sum(axis=0) for j in np.unique(faces)])
    coefficients = [_ground(a, b, p, currents, w, h, modes, order, direction)
                    for order in (16, 32)]
    def ground_parts(c):
        return w/unit*(np.einsum('bi,bj->bij', c[:, 0], c[:, 0])
            + .5*np.einsum('bni,bnj->bij', c[:, 1:], c[:, 1:]))
    planes = ground_parts(coefficients[1])
    ground_error = two.entrywise_relative(ground_parts(coefficients[0]), planes)
    mode_error = two.entrywise_relative(ground_parts(coefficients[1][:, :modes//2+1]), planes)
    ground_integrals = w*coefficients[1][:, 0]
    current_error = max(float(np.max(abs(integrals-np.eye(n)))),
        float(np.max(abs(w*coefficients[1][:, 0].sum(axis=0)+integrals.sum(axis=0)))))
    _require(max(ground_error, mode_error, current_error), 'corner ground refinement/current conservation failed')
    first = np.r_[0, np.flatnonzero(faces[1:] != faces[:-1])+1]
    last = np.r_[first[1:]-1, len(faces)-1]
    edge_owners = owners[first]
    combined = np.array([face_parts[edge_owners == j].sum(axis=0) for j in range(n)])
    integrated = np.array([face_integrals[edge_owners == j].sum(axis=0) for j in range(n)])
    partition = two.entrywise_relative(combined, whole_parts)
    partition_current = float(np.max(abs(integrated-integrals)))
    _require(max(partition, partition_current), 'corner edge partition failed')
    all_parts = np.concatenate((whole_parts, planes))
    all_integrals = np.concatenate((integrals, ground_integrals))
    symmetry, minimum = _gram_checks(np.concatenate((all_parts, face_parts)))
    whole = two.TwoGroundRectangleResult(capacitance, all_parts, all_integrals,
        len(a), condition, max(*reciprocity, cap_reciprocity, symmetry),
        max(direct, compensated, energy), max(current_error, partition_current),
        matrix_error, max(ground_error, mode_error), minimum)
    return two.TwoGroundRectangleEdgesResult(whole, edge_owners,
        g['anchor'][first]*unit, g['anchor'][last]*unit,
        face_parts, face_integrals, partition)


# Public names of helpers shared with other galerkin panel modules (tests/galerkin/test_layers.py).
gram_checks = _gram_checks
mixed_difference = _mixed_difference
require = _require
