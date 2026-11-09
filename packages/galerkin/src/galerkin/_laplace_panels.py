# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Internal constant-panel Green integrals for a grounded rectangle.

The side and top walls have zero normal flux. The singular half-space
contribution is integrated on both source and target panels; only the smooth
image correction is interpolated. See the public laplace_boundary contract.
"""
import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.special import xlogy

def _dd(dx, yt, ys, H):
    """Dirichlet strip Green function of height 2H, with common log(cosh) terms cancelled before evaluation."""
    k = np.pi / (2 * H)
    e = np.exp(-abs(k * dx))
    plus = -2 * e * np.cos(k * (yt + ys)) + e * e
    minus = -2 * e * np.cos(k * (yt - ys)) + e * e
    return 0.5 * (np.log1p(plus) - np.log1p(minus))

def _dd_minus_half(dx, yt, ys, H):
    """Smooth strip correction after removing the singular grounded half-space kernel."""
    k = np.pi / (2 * H)
    u = k * dx / 2
    sinhc = np.ones_like(u)
    np.divide(np.sinh(u), u, out=sinhc, where=u != 0)

    def ratio(dy):
        v = k * dy / 2
        denominator = dx * dx + dy * dy
        result = np.ones_like(denominator)
        np.divide(dx * dx * sinhc * sinhc + dy * dy * np.sinc(v / np.pi) ** 2, denominator, out=result, where=denominator != 0)
        return result
    return 0.5 * np.log(ratio(yt + ys) / ratio(yt - ys))

def _dn(dx, yt, ys, H):
    """Bottom Dirichlet/top Neumann strip via reflection in the top wall."""
    return _dd(dx, yt, ys, H) + _dd(dx, yt, 2 * H - ys, H)

def ground_part(a, b, current, W, H, *, modes=512, order=8):
    """Parseval sum of Neumann cosine harmonic measure on grounded bottom."""
    nodes, weights = leggauss(order)
    p = (a[:, None] + (nodes[None, :, None] + 1) / 2 * (b - a)[:, None]).reshape(-1, 2)
    q = (current[:, None, :] * (weights[None, :, None] / 2)).reshape(-1, current.shape[1])
    total = current.sum(axis=0)
    result = np.outer(total, total) / W
    for first in range(1, modes + 1, 128):
        k = (np.arange(first, min(first + 128, modes + 1)) * np.pi / W)[:, None]
        ratio = np.exp(-k * p[None, :, 1]) * (1 + np.exp(-2 * k * (H - p[None, :, 1]))) / (1 + np.exp(-2 * k * H))
        coefficients = np.cos(k * p[None, :, 0]) * ratio @ q
        result += 2 / W * (coefficients.T @ coefficients)
    return (result + result.T) / 2

def nodes_and_basis(points, lo, hi, degree):
    theta = (np.arange(degree) + 0.5) * np.pi / degree
    nodes = np.cos(theta)
    weights = (-1.0) ** np.arange(degree) * np.sin(theta)
    x = 2 * (np.asarray(points) - lo) / (hi - lo) - 1
    delta = x[:, None] - nodes[None]
    exact = delta == 0
    safe = np.where(exact, 1.0, delta)
    v = weights[None] / safe
    v /= v.sum(axis=1)[:, None]
    hit = np.any(exact, axis=1)
    v[hit] = exact[hit].astype(float)
    return ((lo + hi) / 2 + (hi - lo) / 2 * nodes, v)

def tensor_basis(points, lower, upper, degree):
    x, bx = nodes_and_basis(points[:, 0], lower[0], upper[0], degree)
    y, by = nodes_and_basis(points[:, 1], lower[1], upper[1], degree)
    grid = np.stack(np.meshgrid(x, y, indexing='ij'), axis=-1).reshape(-1, 2)
    return (grid, np.einsum('pi,pj->pij', bx, by).reshape(len(points), -1))

def smooth_correction(targets, sources, W, H, images):
    dx = targets[:, None, 0] - sources[None, :, 0]
    yt = targets[:, None, 1]
    ys = sources[None, :, 1]
    out = _dd_minus_half(dx, yt, ys, H) + _dd(dx, yt, 2 * H - ys, H)
    for n in range(-images, images + 1):
        if n:
            out += _dn(dx - 2 * n * W, yt, ys, H)
        out += _dn(targets[:, None, 0] + sources[None, :, 0] - 2 * n * W, yt, ys, H)
    return out

def _unequal_panel_integral(a, b, c, d):
    """Mean log distance for unequal panels. Normalize the longer source to unit length before subtracting its one-dimensional primitive. Integrate the shorter target with a cubic endpoint map; require the 32/64-point estimates to agree to 1e-12."""
    swap = np.linalg.norm(b - a, axis=1) > np.linalg.norm(d - c, axis=1)
    aa = np.where(swap[:, None], c, a)
    bb = np.where(swap[:, None], d, b)
    cc = np.where(swap[:, None], a, c)
    dd = np.where(swap[:, None], b, d)
    length = np.linalg.norm(dd - cc, axis=1)
    direction = (dd - cc) / length[:, None]

    def primitive(u, h):
        return 0.5 * xlogy(u, u * u + h * h) - u + h * np.arctan2(u, h)

    def integrate(order):
        nodes, weights = leggauss(order)
        result = np.zeros(len(aa))
        for t, weight in zip((nodes + 1) / 2, weights / 2):
            p, q = (t ** 3, (1 - t) ** 3)
            u = p / (p + q)
            jacobian = 3 * t * t * (1 - t) ** 2 / (p + q) ** 2
            target = aa + u * (bb - aa)
            offset = (cc - target) / length[:, None]
            longitudinal = np.einsum('ij,ij->i', offset, direction)
            height = abs(offset[:, 0] * direction[:, 1] - offset[:, 1] * direction[:, 0])
            mean = np.log(length) + primitive(longitudinal + 1, height) - primitive(longitudinal, height)
            result += weight * jacobian * mean
        return result
    coarse, fine = (integrate(32), integrate(64))
    if np.any(abs(fine - coarse) > 1e-12 * np.maximum(1.0, abs(fine))):
        raise ValueError('unequal-panel quadrature did not converge')
    return fine

def exact_double_log(a, b, c, d):
    """Double mean log distance. The self integral is log(length)-3/2. Balanced disjoint pairs use the second primitive F(z)=z^2*(log(z)-3/2)/2 in a separating half-plane to avoid crossing the logarithm branch cut. Length ratios above 64 use the independently refined stable integral."""
    a, b, c, d = map(lambda p: np.asarray(p, dtype=float), (a, b, c, d))
    z = a[:, 0] - c[:, 0] + 1j * (a[:, 1] - c[:, 1])
    A = b[:, 0] - a[:, 0] + 1j * (b[:, 1] - a[:, 1])
    B = d[:, 0] - c[:, 0] + 1j * (d[:, 1] - c[:, 1])
    if np.any(abs(A) == 0) or np.any(abs(B) == 0):
        raise ValueError('positive panel lengths required')
    same = np.all(a == c, axis=1) & np.all(b == d, axis=1) | np.all(a == d, axis=1) & np.all(b == c, axis=1)
    result = np.empty(len(a))
    result[same] = np.log(abs(A[same])) - 1.5
    unequal = ~same & (np.maximum(abs(A), abs(B)) / np.minimum(abs(A), abs(B)) > 64)
    if np.any(unequal):
        result[unequal] = _unequal_panel_integral(a[unequal], b[unequal], c[unequal], d[unequal])
    use = ~(same | unequal)
    if not np.any(use):
        return result
    z, A, B = (z[use], A[use], B[use])
    corners = np.stack([z, z + A, z - B, z + A - B], axis=1)
    scale = np.maximum.reduce([abs(A), abs(B), np.max(abs(corners), axis=1)])
    rotation = np.ones(len(z), dtype=complex)
    found = np.zeros(len(z), dtype=bool)
    for axis in [A, 1j * A, B, 1j * B, z + (A - B) / 2]:
        length = abs(axis)
        rot = np.conj(axis) / np.where(length > 0, length, 1.0)
        projection = (corners * rot[:, None]).real
        for sign in [1.0, -1.0]:
            values = sign * projection
            selected = ~found & (length > 0) & (values.min(axis=1) >= -1e-12 * scale) & (values.max(axis=1) > 1e-12 * scale)
            rotation[selected] = sign * rot[selected]
            found[selected] = True
    if not np.all(found):
        raise ValueError('distinct panels must not overlap or cross')
    z = z * rotation / scale
    A = A * rotation / scale
    B = B * rotation / scale

    def F(value):
        safe = np.where(value == 0, 1.0 + 0j, value)
        return 0.5 * value * value * (np.log(safe) - 1.5)
    result[use] = np.log(scale) + ((F(z + A) + F(z - B) - F(z + A - B) - F(z)) / (A * B)).real
    return result

def mean_log_pairs(a, b, c, d, *, order=8):
    a, b, c, d = map(np.asarray, (a, b, c, d))
    la = np.linalg.norm(b - a, axis=1)
    lb = np.linalg.norm(d - c, axis=1)
    near = np.linalg.norm((a + b - c - d) / 2, axis=1) <= 8 * np.maximum(la, lb)
    result = np.empty(len(a))
    if np.any(near):
        result[near] = exact_double_log(a[near], b[near], c[near], d[near])
    if np.any(~near):
        aa, bb, cc, dd = (a[~near], b[~near], c[~near], d[~near])
        value = np.zeros(len(aa))
        nodes, weights = leggauss(order)
        for u, wu in zip(nodes, weights / 2):
            target = aa + (u + 1) / 2 * (bb - aa)
            for v, wv in zip(nodes, weights / 2):
                source = cc + (v + 1) / 2 * (dd - cc)
                delta = target - source
                value += wu * wv * 0.5 * np.log(np.sum(delta * delta, axis=1))
        result[~near] = value
    return result

def half_matrix(a, b, *, order=8):
    """Source-and-target averaged image Green function above a grounded line. Use log1p for distant pairs and the double integral for near pairs."""
    a, b = (np.asarray(a), np.asarray(b))
    length = np.linalg.norm(b - a, axis=1)
    mid = (a + b) / 2
    if np.any(a[:, 1] <= 0) or np.any(b[:, 1] <= 0):
        raise ValueError('panels must be above ground')
    image_mid = mid.copy()
    image_mid[:, 1] *= -1
    limit = 8 * np.maximum(length[:, None], length[None])
    near = (np.linalg.norm(mid[:, None] - mid[None], axis=-1) <= limit) | (np.linalg.norm(mid[:, None] - image_mid[None], axis=-1) <= limit)
    value = np.zeros((len(a), len(a)))
    nodes, weights = leggauss(order)
    for u, wu in zip(nodes, weights / 2):
        target = a + (u + 1) / 2 * (b - a)
        for v, wv in zip(nodes, weights / 2):
            source = a + (v + 1) / 2 * (b - a)
            dx = target[:, None, 0] - source[None, :, 0]
            dy = target[:, None, 1] - source[None, :, 1]
            distance = np.where(near, 1.0, dx * dx + dy * dy)
            value += wu * wv * 0.5 * np.log1p(4 * target[:, None, 1] * source[None, :, 1] / distance)
    i, j = np.nonzero(near)
    aa, bb, cc, dd = (a[i], b[i], a[j], b[j])
    ci, di = (cc.copy(), dd.copy())
    ci[:, 1] *= -1
    di[:, 1] *= -1
    value[i, j] = mean_log_pairs(aa, bb, ci, di, order=order) - mean_log_pairs(aa, bb, cc, dd, order=order)
    return value

def matrix(a, b, W, H, *, degree=10, order=8, images=8):
    """Symmetric Galerkin energy matrix. Interpolate only the smooth wall correction; verify raw reciprocity before averaging roundoff. Return the matrix and raw relative residual."""
    points = np.concatenate((a, b))
    lower = points.min(axis=0)
    upper = points.max(axis=0)
    span = upper - lower
    if np.any(span <= 0) or lower[1] <= 0:
        raise ValueError('positive-height two-dimensional panel cluster required')
    if min(lower[0], W - upper[0], H - upper[1]) < max(span):
        raise ValueError('panel cluster too close to side/top walls')
    grid, _ = tensor_basis((a + b) / 2, lower, upper, degree)
    S = np.zeros((len(a), degree ** 2))
    nodes, weights = leggauss(degree)
    for node, weight in zip(nodes, weights / 2):
        _, values = tensor_basis(a + (node + 1) / 2 * (b - a), lower, upper, degree)
        S += weight * values
    result = half_matrix(a, b, order=order) + S @ smooth_correction(grid, grid, W, H, images) @ S.T
    symmetry = float(np.max(abs(result - result.T)) / np.max(abs(result)))
    if symmetry > 1e-10:
        raise ValueError('panel integration reciprocity residual exceeded')
    return ((result + result.T) / 2, symmetry)

def panels(polygons, count, grading):
    """Subdivide polygon edges with explicit uniform or cubic endpoint grading."""
    u = np.linspace(0.0, 1.0, count + 1)
    if grading == 'cubic':
        u = u ** 3 / (u ** 3 + (1 - u) ** 3)
    elif grading != 'uniform':
        raise ValueError('explicit uniform or cubic grading required')
    aa = []
    bb = []
    owners = []
    for owner, polygon in enumerate(polygons):
        polygon = np.asarray(polygon, dtype=float)
        for first, last in zip(polygon, np.roll(polygon, -1, axis=0)):
            points = first[None] + u[:, None] * (last - first)[None]
            aa.extend(points[:-1])
            bb.extend(points[1:])
            owners.extend([owner] * count)
    return (np.asarray(aa), np.asarray(bb), np.asarray(owners))
