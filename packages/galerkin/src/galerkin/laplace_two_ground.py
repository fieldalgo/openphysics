# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Homogeneous 2D Laplace panels between two grounded planes.

This explicit API does not change the bottom-ground or volume solvers.
Coordinates are metres; capacitance divided by permittivity is dimensionless.
"""
from dataclasses import dataclass
import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.linalg import cho_factor, cho_solve
from . import _laplace_panels as kernel
from .laplace_boundary import _positive, _integer, _relative, _cross

@dataclass(frozen=True)
class TwoGroundRectangleResult:
    """Immutable snapshots, ordered conductors, bottom ground, top ground.

    current_gram[k] is integral(j_i*j_j ds), in 1/metre, for unit integrated
    signal currents. current_integrals[k,i] is that surface's signed return.
    These homogeneous static factors contain no frequency or material law.
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
    minimum_scaled_eigenvalue: float

    def __post_init__(self):
        for name in ('capacitance_per_permittivity', 'current_gram', 'current_integrals'):
            value = np.asarray(getattr(self, name), dtype=float)
            frozen = np.frombuffer(value.tobytes(), dtype=float).reshape(value.shape)
            object.__setattr__(self, name, frozen)

def _admit(polygons, width, height, count):
    if not isinstance(polygons, (list, tuple)) or not 1 <= len(polygons) <= 16:
        raise ValueError('polygons must be a list or tuple of 1..16 convex conductor boundaries')
    unit = max(width, height)
    w, h = (width / unit, height / unit)
    if not 0.25 <= w / h <= 16:
        raise ValueError('width/height must lie in [0.25, 16]')
    accepted = []
    vertices = 0
    tolerance = 128 * np.finfo(float).eps
    for polygon in polygons:
        raw = np.asarray(polygon)
        if raw.ndim != 2 or raw.shape[1] != 2 or raw.shape[0] < 3:
            raise ValueError('each polygon needs at least three 2D vertices without a closing duplicate')
        vertices += len(raw)
        if vertices * count > 2048:
            raise ValueError('total boundary panel count exceeds 2048')
        if raw.dtype.kind not in 'fiu' or not np.all(np.isfinite(raw)):
            raise ValueError('polygon coordinates must be finite real numbers')
        points = np.asarray(raw, dtype=float) / unit
        if np.any(points <= 0) or np.any(points[:, 0] >= w) or np.any(points[:, 1] >= h):
            raise ValueError('conductors must lie strictly inside the rectangle')
        edges = np.roll(points, -1, axis=0) - points
        lengths = np.linalg.norm(edges, axis=1)
        if np.any(lengths <= tolerance):
            raise ValueError('polygon edge is unresolved at the domain scale')
        turns = _cross(edges, np.roll(edges, -1, axis=0))
        turn_scale = lengths * np.roll(lengths, -1)
        if np.all(turns < -tolerance * turn_scale):
            points = points[::-1].copy()
            edges = np.roll(points, -1, axis=0) - points
            lengths = np.linalg.norm(edges, axis=1)
        elif not np.all(turns > tolerance * turn_scale):
            raise ValueError('polygons must be strictly convex, without collinear edges')
        distances = _cross(edges[:, None], points[None] - points[:, None]) / lengths[:, None]
        if np.any(distances < -tolerance):
            raise ValueError('polygon boundary must be simple and convex')
        accepted.append(points.copy())
    for i, first in enumerate(accepted):
        for second in accepted[i + 1:]:
            separated = False
            for polygon in (first, second):
                edge = np.roll(polygon, -1, axis=0) - polygon
                normals = np.column_stack((-edge[:, 1], edge[:, 0]))
                normals /= np.linalg.norm(normals, axis=1)[:, None]
                p, q = (first @ normals.T, second @ normals.T)
                if np.any(p.max(axis=0) < q.min(axis=0) - tolerance) or np.any(q.max(axis=0) < p.min(axis=0) - tolerance):
                    separated = True
            if not separated:
                raise ValueError('conductor boundaries must be disjoint and separated')
    points = np.concatenate(accepted)
    lower, upper = (points.min(axis=0), points.max(axis=0))
    if min(lower[0], w - upper[0]) < np.max(upper - lower):
        raise ValueError('conductor cluster must be one cluster extent away from side walls')
    return (accepted, unit, w, h)

def _smooth(targets, sources, width, height, images):
    dx = targets[:, None, 0] - sources[None, :, 0]
    yt = targets[:, None, 1]
    ys = sources[None, :, 1]
    out = kernel._dd_minus_half(dx, yt, ys, height / 2)
    for n in range(-images, images + 1):
        if n:
            out += kernel._dd(dx - 2 * n * width, yt, ys, height / 2)
        out += kernel._dd(targets[:, None, 0] + sources[None, :, 0] - 2 * n * width, yt, ys, height / 2)
    return out

def _point_green(targets, sources, width, height, images=8):
    targets = np.asarray(targets, dtype=float)
    sources = np.asarray(sources, dtype=float)
    dx = targets[:, None, 0] - sources[None, :, 0]
    dy = targets[:, None, 1] - sources[None, :, 1]
    distance = dx * dx + dy * dy
    if np.any(distance == 0):
        raise ValueError('point Green function is singular at its source')
    half = 0.5 * np.log1p(4 * targets[:, None, 1] * sources[None, :, 1] / distance)
    return half + _smooth(targets, sources, width, height, images)

def _matrix(a, b, width, height, *, degree, order, images):
    points = np.concatenate((a, b))
    lower = points.min(axis=0)
    upper = points.max(axis=0)
    if np.any(upper <= lower) or lower[1] <= 0 or upper[1] >= height or (lower[0] <= 0) or (upper[0] >= width):
        raise ValueError('panels must be strictly inside the two-plane rectangle')
    grid, _ = kernel.tensor_basis((a + b) / 2, lower, upper, degree)
    projection = np.zeros((len(a), degree ** 2))
    nodes, weights = leggauss(degree)
    for node, weight in zip(nodes, weights / 2):
        _, values = kernel.tensor_basis(a + (node + 1) / 2 * (b - a), lower, upper, degree)
        projection += weight * values
    result = kernel.half_matrix(a, b, order=order) + projection @ _smooth(grid, grid, width, height, images) @ projection.T
    reciprocity = _relative(result, result.T)
    if not np.isfinite(reciprocity) or reciprocity > 1e-10:
        raise ValueError('raw matrix reciprocity failed')
    return ((result + result.T) / 2, reciprocity)

def _solve(polygons, *, width, height, panels_per_edge=32, interpolation_degree=12):
    width = _positive(width, 'width')
    height = _positive(height, 'height')
    count = _integer(panels_per_edge, 'panels_per_edge', 1, 256)
    degree = _integer(interpolation_degree, 'interpolation_degree', 10, 16)
    if degree % 2:
        raise ValueError('even interpolation degree required')
    polygons, unit, w, h = _admit(polygons, width, height, count)
    a, b, owners = kernel.panels(polygons, count, 'cubic')
    length = np.linalg.norm(b - a, axis=1)
    if np.any(length <= 128 * np.finfo(float).eps):
        raise ValueError('unresolved graded panel length')
    images = max(8, int(np.ceil(h / w * np.log(100000000000000.0) / np.pi)) + 1)
    coarse, _ = _matrix(a, b, w, h, degree=degree - 2, order=6, images=images)
    fine, reciprocity = _matrix(a, b, w, h, degree=degree, order=8, images=images + 2)
    error = _relative(coarse, fine)
    if not np.isfinite(error) or error > 1e-10:
        raise ValueError(f'matrix quadrature/interpolation failed: {error}')
    factor = cho_factor(fine)
    inverse = cho_solve(factor, np.eye(len(a)))
    condition = float(np.linalg.norm(fine, np.inf) * np.linalg.norm(inverse, np.inf))
    if not np.isfinite(condition) or condition >= 10000000000.0:
        raise ValueError('condition bound exceeded')
    values = (owners[:, None] == np.arange(len(polygons))[None]).astype(float)
    charges = cho_solve(factor, 2 * np.pi * values)
    capacitance = values.T @ charges
    residual = _relative(fine @ charges, 2 * np.pi * values)
    symmetry = _relative(capacitance, capacitance.T)
    energy = charges.T @ fine @ charges / (2 * np.pi)
    energy_error = _relative(energy, capacitance)
    if max(residual, symmetry, energy_error) > 1e-10:
        raise ValueError('capacitance solve consistency failed')
    np.linalg.cholesky((capacitance + capacitance.T) / 2)
    return dict(capacitance_per_permittivity=capacitance, panel_charge_per_permittivity=charges, normalized_panel_starts=a, normalized_panel_ends=b, owners=owners, length_unit_m=unit, checks=dict(matrix_error=error, raw_matrix_reciprocity=reciprocity, residual=residual, capacitance_reciprocity=symmetry, charge_energy=energy_error, condition=condition), panels=len(a))

def _ground_coefficients(a, b, charges, width, height, *, modes, order):
    """Cosine coefficients of the two grounded-plane charge densities.

    Charges are integrated panel charges. The strip Poisson kernels have
    zero modes (1-y/H)/W and y/(HW), and positive modes
    2 cos(k xs) sinh(k(H-y))/(W sinh(kH)), with the reversed top ratio.
    No sampled ground differentiation or FEM quantities enter this expansion.
    """
    k = np.arange(1, modes + 1) * np.pi / width
    integrated = np.zeros((2, modes + 1, len(a)))
    nodes, weights = leggauss(order)
    for node, weight in zip(nodes, weights / 2):
        p = a + (node + 1) / 2 * (b - a)
        x = p[:, 0]
        y = p[:, 1]
        integrated[0, 0] += weight * (1 - y / height) / width
        integrated[1, 0] += weight * y / (height * width)
        common = 2 / width * np.cos(k[:, None] * x) / (1 - np.exp(-2 * k[:, None] * height))
        integrated[0, 1:] += weight * common * np.exp(-k[:, None] * y) * (1 - np.exp(-2 * k[:, None] * (height - y)))
        integrated[1, 1:] += weight * common * np.exp(-k[:, None] * (height - y)) * (1 - np.exp(-2 * k[:, None] * y))
    return -integrated @ charges

def _factors(solution, width, height, *, modes=256, order=16):
    a = solution['normalized_panel_starts']
    b = solution['normalized_panel_ends']
    owner = solution['owners']
    unit = solution['length_unit_m']
    w = width / unit
    h = height / unit
    charges = solution['panel_charge_per_permittivity'] @ np.linalg.inv(solution['capacitance_per_permittivity'])
    length = np.linalg.norm(b - a, axis=1) * unit
    parts = []
    integrals = []
    for name in range(charges.shape[1]):
        selected = owner == name
        q = charges[selected]
        parts.append(q.T @ (q / length[selected, None]))
        integrals.append(q.sum(axis=0))
    coeff = _ground_coefficients(a, b, charges, w, h, modes=modes, order=order)
    ground_parts = w / unit * (np.einsum('bi,bj->bij', coeff[:, 0], coeff[:, 0]) + 0.5 * np.einsum('bni,bnj->bij', coeff[:, 1:], coeff[:, 1:]))
    parts.append(ground_parts.sum(axis=0))
    integrals.append(w * coeff[:, 0].sum(axis=0))
    return dict(parts=np.array(parts), current_integrals=np.array(integrals), ground_parts=ground_parts, ground_integrals=w * coeff[:, 0], _ground_coefficients=coeff)

def solve_two_ground_rectangle(polygons, *, width, height, panels_per_edge=32, ground_modes=128, interpolation_degree=12):
    """Solve convex closed conductors with grounded bottom and top planes.

    Side normal flux is zero. Accept 1..16 disjoint convex polygons, strictly
    inside a rectangle of width/height in [0.25,16], separated from side walls
    by at least the cluster extent. At most 2048 cubic-graded panels are used.
    Interpolation degree explicitly selects 10,12,14,16; ground_modes selects
    64..4096 cosine modes, compared with twice that number. No fallback occurs.

    Matrix and ground refinement, reciprocity, charge conservation and energy
    checks use 1e-10; condition bound must be below 1e10. These internal checks
    do not establish panel or outer-domain convergence. Callers must compare
    resolutions and finite outer dimensions for their geometry and quantity.
    """
    return _rectangle_result(polygons, width=width, height=height,
        panels_per_edge=panels_per_edge, ground_modes=ground_modes,
        interpolation_degree=interpolation_degree)[0]

def _rectangle_result(polygons, *, width, height, panels_per_edge, ground_modes, interpolation_degree):
    """One original checked solve; retain charges for optional edge output."""
    width, height = (_positive(width, 'width'), _positive(height, 'height'))
    modes = _integer(ground_modes, 'ground_modes', 64, 4096)
    try:
        raw = _solve(polygons, width=width, height=height, panels_per_edge=panels_per_edge, interpolation_degree=interpolation_degree)
        coarse = _factors(raw, width, height, modes=modes, order=12)
        fine = _factors(raw, width, height, modes=2 * modes, order=16)
    except np.linalg.LinAlgError as exc:
        raise ValueError('boundary system must be positive definite and nonsingular') from exc
    ground_error = _entrywise_relative(coarse['ground_parts'], fine['ground_parts'])
    if not np.isfinite(ground_error) or ground_error > 1e-10:
        raise ValueError('ground Fourier/quadrature refinement did not converge')
    parts = np.concatenate((fine['parts'][:-1], fine['ground_parts']))
    integrated = np.concatenate((fine['current_integrals'][:-1], fine['ground_integrals']))
    n = len(raw['capacitance_per_permittivity'])
    current_error = max(float(np.max(abs(integrated[:n] - np.eye(n)))), float(np.max(abs(integrated.sum(axis=0)))))
    if not np.isfinite(current_error) or current_error > 1e-10 or (not np.isfinite(parts).all()):
        raise ValueError('boundary currents must be finite and conserved')
    scale = np.max(abs(parts), axis=(-1, -2))
    eigenvalues = np.linalg.eigvalsh(parts)
    scaled = np.divide(eigenvalues, scale[:, None], out=np.zeros_like(eigenvalues), where=scale[:, None] != 0)
    minimum = float(np.min(scaled))
    if minimum < -1e-10:
        raise ValueError('boundary current Gram must be positive semidefinite')
    checks = raw['checks']
    return TwoGroundRectangleResult(raw['capacitance_per_permittivity'], parts, integrated, raw['panels'], checks['condition'], max(checks['raw_matrix_reciprocity'], checks['capacitance_reciprocity']), checks['residual'], current_error, checks['matrix_error'], ground_error, minimum), raw

@dataclass(frozen=True)
class TwoGroundRectangleEdgesResult:
    """Whole surfaces and their straight conductor-edge decomposition.

    Edges follow conductor order and its admitted CCW boundary. A clockwise
    input is reversed; the first vertex is not otherwise canonicalized.
    Endpoints are in metres, Gram entries in 1/metre, and signed integrals
    dimensionless for unit total conductor currents. Grounded planes are
    retained separately as the last two surfaces of ``whole``.
    """
    whole: TwoGroundRectangleResult
    edge_owners: np.ndarray
    edge_starts: np.ndarray
    edge_ends: np.ndarray
    edge_current_gram: np.ndarray
    edge_current_integrals: np.ndarray
    partition_error: float

    def __post_init__(self):
        for name in ('edge_owners', 'edge_starts', 'edge_ends',
                     'edge_current_gram', 'edge_current_integrals'):
            dtype = np.int64 if name == 'edge_owners' else float
            value = np.asarray(getattr(self, name), dtype=dtype)
            frozen = np.frombuffer(value.tobytes(), dtype=dtype).reshape(value.shape)
            object.__setattr__(self, name, frozen)

def solve_two_ground_rectangle_edges(polygons, *, width, height,
        panels_per_edge=32, ground_modes=128, interpolation_degree=12):
    """Add straight-edge currents to one original checked rectangle solve.

    The domain, admission rules, defaults and all whole-surface checks are
    those of :func:`solve_two_ground_rectangle`. Each edge Gram is integrated
    directly from its panel currents; no normal-flux finite difference or
    material weighting is used. Edge sums must reproduce each whole conductor
    at entrywise relative 1e-10, without a diagonal floor. Signed sums and
    scaled PSD/reciprocity checks also use 1e-10. Failure raises ValueError,
    without fallback. These consistency checks are not convergence estimates:
    independently refine panels and outer bounds for each edge quantity.
    """
    whole, raw = _rectangle_result(polygons, width=width, height=height,
        panels_per_edge=panels_per_edge, ground_modes=ground_modes,
        interpolation_degree=interpolation_degree)
    n = len(whole.capacitance_per_permittivity)
    count = panels_per_edge  # Already admitted by the original solve.
    q = raw['panel_charge_per_permittivity'] @ np.linalg.inv(
        raw['capacitance_per_permittivity'])
    a, b = raw['normalized_panel_starts'], raw['normalized_panel_ends']
    unit = raw['length_unit_m']
    lengths = np.linalg.norm(b-a, axis=1) * unit
    owners = raw['owners'][::count]
    grams, currents = [], []
    for first in range(0, len(a), count):
        selected = slice(first, first+count)
        edge_q = q[selected]
        grams.append(edge_q.T @ (edge_q / lengths[selected, None]))
        currents.append(edge_q.sum(axis=0))
    grams, currents = np.asarray(grams), np.asarray(currents)
    if not np.isfinite(grams).all() or not np.isfinite(currents).all():
        raise ValueError('edge currents must be finite')
    combined = np.asarray([grams[owners == i].sum(axis=0) for i in range(n)])
    integrated = np.asarray([currents[owners == i].sum(axis=0) for i in range(n)])
    partition = _entrywise_relative(combined, whole.current_gram[:n])
    current_error = float(np.max(abs(integrated-whole.current_integrals[:n])))
    if partition > 1e-10 or current_error > 1e-10:
        raise ValueError('edge partition does not preserve whole-surface currents')
    symmetry = _entrywise_relative(grams, grams.swapaxes(-1, -2))
    scale = np.max(abs(grams), axis=(-1, -2))
    eigenvalues = np.linalg.eigvalsh(grams)
    scaled = np.divide(eigenvalues, scale[:, None], out=np.zeros_like(eigenvalues),
                       where=scale[:, None] != 0)
    if symmetry > 1e-10 or np.min(scaled) < -1e-10:
        raise ValueError('edge current Gram must be reciprocal and positive semidefinite')
    return TwoGroundRectangleEdgesResult(whole, owners, a[::count]*unit,
        b[count-1::count]*unit, grams, currents, partition)

def _entrywise_relative(a, b):
    """No diagonal floor: each finite entry retains its own relative scale."""
    difference = abs(a - b)
    scale = np.maximum(abs(a), abs(b))
    if not np.isfinite(difference).all():
        return float('inf')
    return float(np.max(np.divide(difference, scale, out=np.zeros_like(difference), where=scale != 0)))
