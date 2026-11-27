# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Homogeneous 2D Laplace panels between two grounded planes.

Internal module, consistent units: not part of galerkin's public API (the ``__all__``
of its public modules).

This explicit API does not change the bottom-ground or volume solvers.
Coordinates are metres; capacitance divided by permittivity is dimensionless.
"""
from dataclasses import dataclass
import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.linalg import cho_factor, cho_solve
from . import _laplace_panels as kernel

_positive, _integer, _relative, _cross = kernel.positive, kernel.integer, kernel.relative, kernel.cross

@dataclass(frozen=True)
class TwoGroundRectangleResult:
    """Immutable snapshots, ordered conductors, bottom ground, top ground.

    current_gram[k] is integral(j_i*j_j ds), in 1/metre, for unit integrated
    signal currents. current_integrals[k,i] is that surface's signed return.
    These homogeneous static factors contain no frequency or material law.
    smooth_interpolation_boxes is 1 when one bounding box met the matrix check;
    otherwise the check was repeated on plane-scaled boxes, and
    single_box_matrix_error keeps the failed one-box value.
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
    smooth_interpolation_boxes: int = 1
    single_box_matrix_error: float | None = None

    def __post_init__(self):
        for name in ('capacitance_per_permittivity', 'current_gram', 'current_integrals'):
            value = np.asarray(getattr(self, name), dtype=float)
            frozen = np.frombuffer(value.tobytes(), dtype=float).reshape(value.shape)
            object.__setattr__(self, name, frozen)

def _admit(polygons, width, height, count, side_walls=True, max_aspect=16):
    accepted, unit, w, h = kernel.admit_polygons(polygons, width, height, count, max_aspect=max_aspect)
    points = np.concatenate(accepted)
    lower, upper = (points.min(axis=0), points.max(axis=0))
    if side_walls and min(lower[0], w - upper[0]) < np.max(upper - lower):
        raise ValueError('conductor cluster must be one cluster extent away from side walls')
    return (accepted, unit, w, h)

def _image_bound(low, high, height):
    """Upper bound of |dd| for every horizontal shift in [low, high].

    dd is half the difference of log1p(-2e cos(a)+e^2) and log1p(-2e cos(b)+e^2)
    with e = exp(-pi |shift| / height), so |dd| <= x/(1-x), x = 2e+e^2.
    """
    nearest = 0.0 if low <= 0 <= high else min(abs(low), abs(high))
    e = np.exp(-np.pi * nearest / height)
    x = 2 * e + e * e
    return x / (1 - x) if x < 1 else np.inf

def _add_image(out, bound, term):
    """Add one image term unless it cannot change any entry of ``out``.

    fl(v + t) == v whenever |t| < |v| 2**-54 (below half an ulp of v), so an
    image whose doubled bound is below 2**-54 min|out| is skipped with a
    bit-identical result. Laterally distant images of wide, low rectangles
    are far below that; the image count itself is unchanged.
    """
    if out.size and 2 * bound < 2.0 ** -54 * np.min(np.abs(out)):
        return out
    out += term()
    return out

def _smooth(targets, sources, width, height, images):
    dx = targets[:, None, 0] - sources[None, :, 0]
    yt = targets[:, None, 1]
    ys = sources[None, :, 1]
    out = kernel.dd_minus_half(dx, yt, ys, height / 2)
    t_low, t_high = targets[:, 0].min(), targets[:, 0].max()
    s_low, s_high = sources[:, 0].min(), sources[:, 0].max()
    for n in range(-images, images + 1):
        shift = 2 * n * width
        if n:
            out = _add_image(out, _image_bound(t_low - s_high - shift, t_high - s_low - shift, height),
                             lambda: kernel.dd(dx - shift, yt, ys, height / 2))
        out = _add_image(out, _image_bound(t_low + s_low - shift, t_high + s_high - shift, height),
                         lambda: kernel.dd(targets[:, None, 0] + sources[None, :, 0] - shift, yt, ys, height / 2))
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

def _projection(a, b, lower, upper, degree):
    grid, _ = kernel.tensor_basis((a + b) / 2, lower, upper, degree)
    projection = np.zeros((len(a), degree ** 2))
    nodes, weights = leggauss(degree)
    for node, weight in zip(nodes, weights / 2):
        _, values = kernel.tensor_basis(a + (node + 1) / 2 * (b - a), lower, upper, degree)
        projection += weight * values
    return grid, projection

def _clusters(a, b, owners, width, height):
    """Panel groups of each conductor no wider than its distance to the nearest
    plane or side wall (kernel.wall_labels with the bottom plane included).

    The smooth kernel holds the plane and side-wall images. Interpolating it over
    one box much wider than a conductor's distance from them converges slowly
    (coupled, layered and broadside striplines, conductors near a side wall).
    """
    return kernel.wall_labels(a, b, owners, width, height, bottom=True)

def _matrix(a, b, width, height, *, degree, order, images, labels=None):
    points = np.concatenate((a, b))
    lower = points.min(axis=0)
    upper = points.max(axis=0)
    if np.any(upper <= lower) or lower[1] <= 0 or upper[1] >= height or (lower[0] <= 0) or (upper[0] >= width):
        raise ValueError('panels must be strictly inside the two-plane rectangle')
    if labels is None:
        grid, _ = kernel.tensor_basis((a + b) / 2, lower, upper, degree)
        projection = np.zeros((len(a), degree ** 2))
        nodes, weights = leggauss(degree)
        for node, weight in zip(nodes, weights / 2):
            _, values = kernel.tensor_basis(a + (node + 1) / 2 * (b - a), lower, upper, degree)
            projection += weight * values
        result = kernel.half_matrix(a, b, order=order) + projection @ _smooth(grid, grid, width, height, images) @ projection.T
    else:
        groups = [np.flatnonzero(labels == label) for label in np.unique(labels)]
        boxes = []
        for group in groups:
            box = np.concatenate((a[group], b[group]))
            if np.any(box.max(axis=0) <= box.min(axis=0)):
                raise ValueError('plane-scaled interpolation box has zero extent')
            boxes.append(_projection(a[group], b[group], box.min(axis=0), box.max(axis=0), degree))
        result = kernel.half_matrix(a, b, order=order)
        for i, rows in enumerate(groups):
            for j, columns in enumerate(groups):
                result[np.ix_(rows, columns)] += boxes[i][1] @ _smooth(boxes[i][0], boxes[j][0], width, height, images) @ boxes[j][1].T
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
    polygons, unit, w, h = _admit(polygons, width, height, count, side_walls=False, max_aspect=64)
    points = np.concatenate(polygons)
    lower, upper = (points.min(axis=0), points.max(axis=0))
    clear = bool(min(lower[0], w - upper[0]) >= np.max(upper - lower))
    if not clear and kernel.wall_box_count(polygons, w, h, bottom=True) > kernel.WALL_BOXES:
        raise ValueError('conductors are too close to the side walls for wall-scaled interpolation')
    a, b, owners = kernel.panels(polygons, count, 'cubic')
    length = np.linalg.norm(b - a, axis=1)
    if np.any(length <= 128 * np.finfo(float).eps):
        raise ValueError('unresolved graded panel length')
    images = max(8, int(np.ceil(h / w * np.log(100000000000000.0) / np.pi)) + 1)
    clustered = {}
    if clear:
        coarse, _ = _matrix(a, b, w, h, degree=degree - 2, order=6, images=images)
        fine, reciprocity = _matrix(a, b, w, h, degree=degree, order=8, images=images + 2)
        error = _relative(coarse, fine)
    if not clear or not np.isfinite(error) or error > 1e-10:
        # The one-box check failed, or the cluster is nearer a side wall than its
        # extent: use boxes scaled to each conductor's plane and wall distance.
        labels = _clusters(a, b, owners, w, h)
        if labels.max() > 0 or not clear:
            coarse, _ = _matrix(a, b, w, h, degree=degree - 2, order=6, images=images, labels=labels)
            fine, reciprocity = _matrix(a, b, w, h, degree=degree, order=8, images=images + 2, labels=labels)
            clustered = dict(single_box_matrix_error=error if clear else None,
                             smooth_interpolation_boxes=int(labels.max() + 1))
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
    return dict(capacitance_per_permittivity=capacitance, panel_charge_per_permittivity=charges, normalized_panel_starts=a, normalized_panel_ends=b, owners=owners, length_unit_m=unit, checks=dict(matrix_error=error, raw_matrix_reciprocity=reciprocity, residual=residual, capacitance_reciprocity=symmetry, charge_energy=energy_error, condition=condition, **clustered), panels=len(a))

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
    inside a rectangle of width/height in [0.25,64], separated from side walls
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
    return TwoGroundRectangleResult(raw['capacitance_per_permittivity'], parts, integrated, raw['panels'], checks['condition'], max(checks['raw_matrix_reciprocity'], checks['capacitance_reciprocity']), checks['residual'], current_error, checks['matrix_error'], ground_error, minimum, checks.get('smooth_interpolation_boxes', 1), checks.get('single_box_matrix_error')), raw

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


def solve_two_ground_corner_rectangle_edges(polygons, *, width, height,
        panels_per_edge=128, ground_modes=256, interpolation_degree=24):
    """Explicit corner-power field for one or two all-active convex conductors.

    Coordinates are metres. The homogeneous static rectangle has grounded
    bottom/top planes and zero side normal flux. Geometry admission is the
    same as the original rectangle solver; this separate method accepts only
    1..2 conductor voltage/current bases and no fixed-ground trace reduction.
    Require even cubic subdivisions 16..512, merged to n-6 panels per edge,
    at most 4096 panels. Corner density is p*u**(p-1), with
    p=pi/(2*pi-interior_angle); interior panels are constant. The normalized
    densities' analytic squared-current moments are integrated per edge.

    Interpolation degree is fixed at 24, checked against 20. ground_modes is
    the actual fine Fourier count (even 64..4096), compared with half that
    count; power quadrature compares 16/32. Two fixed portable residual
    corrections precede unit-current normalization. Internal refinement,
    reciprocity, conservation, energy, edge partition and PSD checks retain
    1e-10 and condition <1e10. Failure raises ValueError, with no fallback.
    These gates do not estimate discretization or outer-domain error: refine
    panels and outer dimensions independently for every requested quantity.

    Return the immutable whole/edge result contract of the existing solver.
    A corner exponent is valid here only in a homogeneous exterior medium;
    this does not model metal/dielectric interface corners or finite-metal
    diffusion. Existing solvers, resolutions and defaults remain unchanged.
    """
    from ._laplace_corner_field import solve
    try:
        return solve(polygons, width=width, height=height,
            panels_per_edge=panels_per_edge, ground_modes=ground_modes,
            interpolation_degree=interpolation_degree)
    except np.linalg.LinAlgError as exc:
        raise ValueError('corner boundary system must be positive definite and nonsingular') from exc


# Public names of helpers shared with other galerkin panel modules (tests/galerkin/test_layers.py).
admit = _admit
entrywise_relative = _entrywise_relative
integer = _integer
positive = _positive
smooth = _smooth
