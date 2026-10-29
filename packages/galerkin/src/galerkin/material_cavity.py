# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""PEC box resonances with box-shaped dielectric/magnetic, possibly lossy, regions.

Time convention exp(+j*omega*t): passive materials have eps_r = eps' - j*eps''
with eps'' >= 0 (likewise mu_r), and decaying resonances have Im(omega) > 0.
The weak form curl(mu_r^-1 curl E) = k0^2 eps_r E gives the complex-symmetric
(non-Hermitian) generalized problem S(1/mu_r) q = k0^2 M(eps_r) q. The quality
factor is Q = Re(omega) / (2 Im(omega)).

Walls are perfect conductors unless a finite conductivity is given. A finite
wall uses the Leontovich impedance condition E_t = Zs H x n with
Zs = sqrt(j omega mu0 / sigma), which adds sqrt(j k0 eta0 sigma) B(wall) to the
stiffness side, B the tangential edge mass of that wall. Zs depends on omega, so
the problem is nonlinear and each mode is found by fixed-point iteration.
"""

from dataclasses import dataclass

import numpy as np
import scipy.linalg as la
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .mesh3d import Mesh3D
from .edge3d import (EdgeSpace3D, assemble_curlcurl_3d, assemble_edge_mass_3d,
                     eval_edge_field_3d)
from ._cavity_common import C0, DENSE_LIMIT, GRADIENT_LIMIT, RESIDUAL_LIMIT, cavity_mesh
from .core.checks import positive_integer, positive_real, triple

_INDEPENDENCE_LIMIT = 1e-6
_BIORTHOGONALITY_LIMIT = 1e-7
_SEPARATION = 1e-6
_LOSSLESS_IMAG_LIMIT = 1e-9
_GRID_TOLERANCE = 1e-9
# Symmetric sparsity: minimum degree on A^T+A gives far less fill than COLAMD.
_ORDERING = "MMD_AT_PLUS_A"
_MU0 = 1.25663706212e-6           # vacuum permeability (CODATA 2018), H/m
_ETA0 = _MU0 * C0
WALLS = ("x0", "x1", "y0", "y1", "z0", "z1")
_FIXED_POINT_TOLERANCE = 1e-12
_FIXED_POINT_ITERATIONS = 50
_DEGENERATE = 1e-8
# Stop rule of the nonlinear iteration; roundoff floors near 1e-13 with large wall terms.
_ITERATION_RESIDUAL = 1e-10
_FACE_EDGES = ((0, 1), (0, 2), (1, 2))


@dataclass(frozen=True)
class CavityMaterialRegion:
    """Axis-aligned box ``[x0,x1] x [y0,y1] x [z0,z1]`` (metres) of one material.

    Relative constants are complex under exp(+j*omega*t): ``eps' - j*eps''``.
    Every bound must lie on a mesh grid plane, so the mesh conforms to the region.
    """

    bounds_m: tuple
    relative_permittivity: complex = 1.0
    relative_permeability: complex = 1.0


@dataclass
class MaterialCavityResult:
    """Complex resonances of a PEC box with piecewise-constant materials.

    ``eigenvalues_m2`` are complex k0^2 (m^-2); ``frequencies_hz`` complex
    ``c0*sqrt(k0^2)/(2*pi)`` with Re > 0; ``quality_factors`` Re f / (2 Im f),
    infinite when every material and wall is lossless. Edge coefficients are complex with
    the Hermitian vacuum-mass normalization q^H M0 q = 1 (units m^-1/2) and the
    largest-magnitude coefficient real and positive; not V/m or power.
    """

    mesh: Mesh3D
    space: EdgeSpace3D
    frequencies_hz: np.ndarray                 # (K,) complex
    resonant_frequencies_hz: np.ndarray        # (K,) real part
    quality_factors: np.ndarray                # (K,)
    eigenvalues_m2: np.ndarray                 # (K,) complex
    edge_coefficients: np.ndarray              # (E, K) complex
    electric_field: np.ndarray                 # (K, T, 3) complex, centroids
    relative_residuals: np.ndarray             # (K,)
    pec_edge_ids: np.ndarray
    tet_relative_permittivity: np.ndarray      # (T,) complex
    tet_relative_permeability: np.ndarray      # (T,) complex
    requested_modes: int
    target_frequency_hz: float
    lossless: bool
    wall_conductivity_s_per_m: dict          # wall name -> S/m, or None for PEC
    fixed_point_iterations: np.ndarray       # (K,), zero without lossy walls
    time_convention: str = "exp(+j*omega*t)"
    search: str = "near_target"
    cluster_completeness: str = "not_certified"
    mode_count_policy: str = "exact_count_may_split_cluster"


def _material(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (int, float, complex, np.integer, np.floating, np.complexfloating)):
        raise ValueError(f"{name} must be a finite complex number")
    value = complex(value)
    if not (np.isfinite(value) and value.real > 0 and value.imag <= 0):
        raise ValueError(f"{name} must be finite with positive real part and non-positive "
                         "imaginary part (passive under exp(+j*omega*t))")
    return value


def _regions(regions, lengths, cells):
    if isinstance(regions, CavityMaterialRegion):
        raise ValueError("regions must be a sequence of CavityMaterialRegion")
    try:
        regions = tuple(regions)
    except TypeError:
        raise ValueError("regions must be a sequence of CavityMaterialRegion") from None
    checked = []
    for r, region in enumerate(regions):
        if not isinstance(region, CavityMaterialRegion):
            raise ValueError(f"regions[{r}] must be a CavityMaterialRegion")
        try:
            bounds = tuple(tuple(pair) for pair in region.bounds_m)
        except TypeError:
            raise ValueError(f"regions[{r}].bounds_m must be three (low, high) pairs") from None
        if len(bounds) != 3 or any(len(pair) != 2 for pair in bounds):
            raise ValueError(f"regions[{r}].bounds_m must be three (low, high) pairs")
        planes = []
        for axis, pair in enumerate(bounds):
            grid = []
            for value in pair:
                if (isinstance(value, (bool, np.bool_))
                        or not isinstance(value, (int, float, np.integer, np.floating))
                        or not np.isfinite(value)):
                    raise ValueError(f"regions[{r}].bounds_m must be finite real numbers")
                position = float(value) / lengths[axis] * cells[axis]
                index = round(position)
                if abs(position - index) > _GRID_TOLERANCE * max(1, cells[axis]):
                    raise ValueError(
                        f"regions[{r}] bound {value!r} on axis {axis} is not a mesh grid plane "
                        f"(multiples of {lengths[axis] / cells[axis]:g} m); adjust subdivisions")
                grid.append(index)
            if not 0 <= grid[0] < grid[1] <= cells[axis]:
                raise ValueError(f"regions[{r}] needs 0 <= low < high <= length on axis {axis}")
            planes.append(grid)
        checked.append((np.array(planes),
                        _material(region.relative_permittivity,
                                  f"regions[{r}].relative_permittivity"),
                        _material(region.relative_permeability,
                                  f"regions[{r}].relative_permeability")))
    return checked


def _material_matrices(space, free, eps, mu):
    """Sum real indicator assemblies times complex constants, one per material."""
    pairs, labels = np.unique(np.column_stack([eps, mu]), axis=0, return_inverse=True)
    labels = labels.ravel()
    stiffness = sp.csc_matrix((len(free), len(free)), dtype=complex)
    mass = sp.csc_matrix((len(free), len(free)), dtype=complex)
    for label, (eps_value, mu_value) in enumerate(pairs):
        mask = (labels == label).astype(float)
        stiffness = stiffness + (assemble_curlcurl_3d(space, mask)[free][:, free]
                                 / mu_value).tocsc()
        mass = mass + (assemble_edge_mass_3d(space, mask)[free][:, free] * eps_value).tocsc()
    return stiffness.tocsc(), mass.tocsc()


def _wall_conductivities(value):
    if value is None:
        return dict.fromkeys(WALLS)
    if isinstance(value, dict):
        unknown = sorted(set(value) - set(WALLS), key=str)
        if unknown:
            raise ValueError(f"unknown walls {unknown}; use {WALLS}")
        return {wall: (None if value.get(wall) is None
                       else positive_real(value[wall], f"wall_conductivity_s_per_m[{wall}]"))
                for wall in WALLS}
    sigma = positive_real(value, "wall_conductivity_s_per_m")
    return dict.fromkeys(WALLS, sigma)


def _wall_faces(mesh, lengths):
    """Boundary faces grouped by Cartesian wall, from coordinates of normalized nodes."""
    faces = mesh.boundary_faces()
    coordinates = mesh.nodes[faces]                     # (F, 3 nodes, 3)
    groups = {}
    for axis in range(3):
        for side, position in enumerate((0.0, lengths[axis])):
            on = np.all(np.abs(coordinates[:, :, axis] - position) <= 1e-12, axis=1)
            groups[WALLS[2 * axis + side]] = faces[on]
    if sum(len(f) for f in groups.values()) != len(faces):
        raise RuntimeError("boundary faces do not partition into the six box walls")
    return groups


def _face_edge_ids(space, faces):
    pairs = np.concatenate([faces[:, list(e)] for e in _FACE_EDGES])
    return np.unique(space._ids(pairs))


def _wall_mass(space, faces):
    """Exact tangential Whitney mass int_wall W_e . W_f dS over the given triangles.

    The tangential trace of a tetrahedral Whitney function is the triangle's
    Whitney function, with int lambda_a lambda_b dA = A (1 + delta_ab) / 12.
    """
    points = space.mesh.nodes[faces]
    first, second = points[:, 1] - points[:, 0], points[:, 2] - points[:, 0]
    surface = np.linalg.pinv(np.stack([first, second], axis=2))     # (F, 2, 3)
    grads = np.stack([-surface[:, 0] - surface[:, 1], surface[:, 0], surface[:, 1]], axis=1)
    area = 0.5 * np.linalg.norm(np.cross(first, second), axis=1)
    g = np.einsum("fad,fbd->fab", grads, grads)
    d = np.eye(3)
    i = np.array([e[0] for e in _FACE_EDGES])[:, None]
    j = np.array([e[1] for e in _FACE_EDGES])[:, None]
    k, l = i.T, j.T
    local = ((1 + d[i, k]) * g[:, j, l] - (1 + d[i, l]) * g[:, j, k]
             - (1 + d[j, k]) * g[:, i, l] + (1 + d[j, l]) * g[:, i, k])
    local *= (area / 12.0)[:, None, None]
    low, high = faces[:, i.ravel()], faces[:, j.ravel()]
    signs = np.where(low < high, 1.0, -1.0)
    local *= signs[:, :, None] * signs[:, None, :]
    ids = space._ids(np.stack([low.ravel(), high.ravel()], axis=1)).reshape(-1, 3)
    return sp.coo_matrix((local.ravel(), (np.repeat(ids, 3, axis=1).ravel(),
                                          np.tile(ids, (1, 3)).ravel())),
                         shape=(space.num_edges,) * 2).tocsc()


def _nearest_eigenpairs(stiffness, mass, projector, sigma, count, dense, interior_count,
                        kernel_cutoff, physical_count, start=None):
    """Physical eigenpairs of stiffness q = k^2 mass q nearest a (possibly complex) shift.

    Returned sorted by |k^2 - sigma|. Dense up to DENSE_LIMIT free edges, with an
    exact gradient-kernel count; otherwise ARPACK on the standard problem
    T = P (A - sigma M)^-1 M P, because ARPACK's generalized mode needs a
    Hermitian positive M and this M is complex symmetric. ``start`` (a previous
    eigenvector estimate) selects a small refinement subspace for fixed-point steps.
    """
    gradient, mass_gradient, gradient_lu = projector
    if dense:
        values, vectors = la.eig(stiffness.toarray(), mass.toarray())
        if not np.isfinite(values).all():
            raise RuntimeError("dense cavity eigensolver returned non-finite eigenvalues")
        if np.count_nonzero(np.abs(values) <= kernel_cutoff) != interior_count:
            raise RuntimeError("computed gradient kernel dimension does not match the PEC box")
    else:
        if start is None:
            candidates = min(max(2 * count, count + 8), physical_count, stiffness.shape[0] - 2)
            subspace = max(6 * candidates, 90)
            start = np.random.default_rng(0).standard_normal(stiffness.shape[0])
        else:
            candidates = min(count + 2, physical_count, stiffness.shape[0] - 2)
            subspace = max(4 * candidates, 20)
        shifted_lu = spla.splu((stiffness - sigma * mass).tocsc(), permc_spec=_ORDERING)

        def apply(x):
            # P^T M = M P, so T = P A^-1 P^T M annihilates gradients (nu = 0) and keeps
            # physical values nu = 1/(k^2 - sigma); no penalty alters Maxwell.
            rhs = mass @ np.asarray(x, dtype=complex).ravel()
            if gradient_lu is not None:
                rhs = rhs - mass_gradient @ gradient_lu.solve(gradient.T @ rhs)
            result = shifted_lu.solve(rhs)
            if gradient_lu is not None:
                result = result - gradient @ gradient_lu.solve(mass_gradient.T @ result)
            return result

        operator = spla.LinearOperator(stiffness.shape, matvec=apply, dtype=complex)
        transformed, vectors = spla.eigs(
            operator, k=candidates, which="LM",
            v0=np.asarray(start, dtype=complex),
            ncv=min(stiffness.shape[0], subspace), tol=1e-10, maxiter=50000)
        keep = np.abs(transformed) > 1e-12 * np.max(np.abs(transformed))
        values, vectors = sigma + 1 / transformed[keep], vectors[:, keep]
    if not np.isfinite(values).all() or not np.isfinite(vectors).all():
        raise RuntimeError("cavity eigensolver returned non-finite eigenpairs")
    physical = np.flatnonzero(np.abs(values) > kernel_cutoff)
    if np.any(values[physical].imag < -_LOSSLESS_IMAG_LIMIT * np.abs(values[physical])):
        raise RuntimeError("cavity eigensolver returned a growing (active) resonance")
    if np.any(values[physical].real <= 0):
        raise RuntimeError("cavity eigensolver returned a non-positive real eigenvalue")
    if len(physical) < count:
        raise RuntimeError(f"requested {count} modes but found only {len(physical)} physical "
                           "candidates near the target; change target or refine subdivisions")
    order = physical[np.argsort(np.abs(values[physical] - sigma), kind="stable")]
    return values[order], vectors[:, order].astype(complex)


def _residual_inverse_iteration(eigenvalue, vector, stiffness, mass, wall_mass, coefficient,
                                operator_at, projector):
    """Nonlinear eigenpair T(l) x = 0, T(l) = S + sum_w c_w(l) B_w - l M (Neumaier 1985).

    One LU of T(l0) at the starting estimate. Each step solves the scalar equation
    x^T T(l) x = 0 for l by Newton (c_w is proportional to l^(1/4)), then corrects
    x <- x - P T(l0)^-1 P^T T(l) x within the gradient-free subspace.
    """
    gradient, mass_gradient, gradient_lu = projector
    factor = spla.splu((operator_at(np.sqrt(eigenvalue)) - eigenvalue * mass).tocsc(),
                       permc_spec=_ORDERING)
    x = np.asarray(vector, dtype=complex).copy()
    value = complex(eigenvalue)
    for step in range(1, _FIXED_POINT_ITERATIONS + 1):
        sx, mx = stiffness @ x, mass @ x
        bx = {wall: matrix @ x for wall, matrix in wall_mass.items()}
        a, m = x @ sx, x @ mx
        b = {wall: x @ product for wall, product in bx.items()}
        previous = value
        for _ in range(100):
            c = coefficient(value)
            wall = sum(c[w] * b[w] for w in b)
            f = a + wall - value * m
            derivative = wall / (4 * value) - m
            delta = f / derivative
            value -= delta
            if abs(delta) <= 1e-15 * abs(value):
                break
        else:
            raise RuntimeError("surface-impedance scalar Newton step did not converge")
        c = coefficient(value)
        residual = sx + sum(c[w] * bx[w] for w in bx) - value * mx
        left = np.linalg.norm(sx + sum(c[w] * bx[w] for w in bx))
        relative = np.linalg.norm(residual) / (left + abs(value) * np.linalg.norm(mx))
        if relative <= _ITERATION_RESIDUAL and abs(value - previous) <= _FIXED_POINT_TOLERANCE * abs(value):
            return value, x, step
        rhs = residual
        if gradient_lu is not None:
            rhs = rhs - mass_gradient @ gradient_lu.solve(gradient.T @ rhs)
        correction = factor.solve(rhs)
        if gradient_lu is not None:
            correction = correction - gradient @ gradient_lu.solve(mass_gradient.T @ correction)
        x = x - correction
        x /= x[np.argmax(np.abs(x))]
    raise RuntimeError("surface-impedance residual inverse iteration did not converge in "
                       f"{_FIXED_POINT_ITERATIONS} iterations")



def solve_material_cavity_box(lengths_m, subdivisions, *, regions=(), num_modes=6,
                              target_frequency_hz,
                              wall_conductivity_s_per_m=None) -> MaterialCavityResult:
    """Solve a rectangular box filled with vacuum and box-shaped material regions.

    lengths_m, subdivisions, num_modes and target_frequency_hz follow
    ``solve_cavity_box``; the mesh is the same alternating Kuhn mesh.
    regions: sequence of ``CavityMaterialRegion``; later regions override earlier
        ones where they overlap, and uncovered space is vacuum. Each tetrahedron
        takes the material containing its centroid. Bounds must be grid planes.
    wall_conductivity_s_per_m: None (all walls PEC), one positive conductivity
        for every wall, or a dict over ``WALLS`` ('x0', 'x1', ..., 'z1') whose
        missing or None entries are PEC. Finite walls use the Leontovich impedance
        condition; each mode is then converged by fixed-point iteration in k0.

    Select modes nearest the real target in complex squared wave number,
    ``|k0^2 - (2*pi*f_target/c0)^2|``, then return them in ascending real
    frequency. Invalid inputs raise ValueError; nonconvergence, insufficient
    modes or failed quality checks raise RuntimeError without a partial result.
    See docs/packages/galerkin/material_cavity.md for the conventions and validation.
    """
    lengths = np.asarray(triple(lengths_m, "lengths_m", positive_real))
    cells = triple(subdivisions, "subdivisions", positive_integer)
    count = positive_integer(num_modes, "num_modes")
    target = positive_real(target_frequency_hz, "target_frequency_hz")
    materials = _regions(regions, lengths, cells)
    conductivity = _wall_conductivities(wall_conductivity_s_per_m)
    lossy_walls = [wall for wall in WALLS if conductivity[wall] is not None]
    length_scale = float(lengths.max())
    with np.errstate(over="ignore", under="ignore", divide="ignore", invalid="ignore"):
        normalized_lengths = lengths / length_scale
        target_k = (2 * np.pi / C0) * target * length_scale
        sigma = target_k * target_k
        fundamental = np.pi**2 * np.sort(1 / normalized_lengths**2)[:2].sum()
        eigenvalue_scale = 1 / np.float64(length_scale)**2
        field_scale = np.float64(length_scale)**-1.5
    if (not np.isfinite([sigma, fundamental, eigenvalue_scale, field_scale]).all()
            or min(sigma, eigenvalue_scale, field_scale) <= 0):
        raise ValueError("box lengths and target exceed the supported floating-point range")

    normalized_mesh = cavity_mesh(normalized_lengths, cells)
    centroid_grid = (normalized_mesh.nodes[normalized_mesh.tets].mean(axis=1)
                     / normalized_lengths * np.asarray(cells))
    eps = np.ones(normalized_mesh.num_tets, dtype=complex)
    mu = np.ones(normalized_mesh.num_tets, dtype=complex)
    for planes, eps_value, mu_value in materials:
        inside = np.all((centroid_grid > planes[:, 0]) & (centroid_grid < planes[:, 1]), axis=1)
        eps[inside], mu[inside] = eps_value, mu_value
    lossless = bool(np.all(eps.imag == 0) and np.all(mu.imag == 0) and not lossy_walls)

    space = EdgeSpace3D(normalized_mesh)
    walls = _wall_faces(normalized_mesh, normalized_lengths)
    pec_faces = [walls[w] for w in WALLS if conductivity[w] is None]
    pec = (_face_edge_ids(space, np.concatenate(pec_faces)) if pec_faces
           else np.array([], dtype=int))
    free = np.setdiff1d(np.arange(space.num_edges), pec)
    # Gradients of interior nodal potentials are the kernel with any wall mix:
    # their tangential traces vanish on every wall.
    interior_count = int(np.prod(np.asarray(cells, dtype=object) - 1))
    physical_count = len(free) - interior_count
    if count > physical_count:
        raise RuntimeError(f"requested {count} modes but this mesh has only "
                           f"{physical_count} physical degrees of freedom; refine subdivisions")
    stiffness, mass = _material_matrices(space, free, eps, mu)
    vacuum_mass = assemble_edge_mass_3d(space)[free][:, free].tocsc()
    wall_mass = {w: _wall_mass(space, walls[w])[free][:, free].tocsc() for w in lossy_walls}
    # Physical k0^2 are at least about the vacuum fundamental / max|eps mu|.
    kernel_cutoff = 1e-8 * fundamental / float(np.max(np.abs(eps * mu)))
    dense = len(free) <= DENSE_LIMIT

    def wall_coefficient(eigenvalue):
        """Per-wall L*sqrt(j k eta0 sigma) at normalized k^2, with SI k = sqrt(k^2)/L.

        With the edge basis scaled by L, S scales as 1/L and B as L^2 relative to
        the normalized matrices, so the wall term carries one factor of L.
        """
        k = np.sqrt(complex(eigenvalue)) / length_scale
        return {wall: length_scale * np.sqrt(1j * k * _ETA0 * conductivity[wall])
                for wall in lossy_walls}

    def operator_at(k_normalized):
        result = stiffness
        for wall, value in wall_coefficient(complex(k_normalized) ** 2).items():
            result = result + value * wall_mass[wall]
        return result.tocsc()

    try:
        mesh = space.mesh
        interior = np.setdiff1d(np.arange(mesh.num_nodes), mesh.boundary_nodes())
        gradient = sp.coo_matrix(
            (np.tile([-1.0, 1.0], len(free)),
             (np.repeat(np.arange(len(free)), 2), space.edges[free].ravel())),
            shape=(len(free), mesh.num_nodes)).tocsc()[:, interior]
        # Complex-symmetric projector P = I - C (C^T M C)^-1 C^T M (no conjugation).
        mass_gradient = (mass @ gradient).tocsc()
        gradient_lu = (spla.splu((gradient.T @ mass_gradient).tocsc(), permc_spec=_ORDERING)
                       if len(interior) else None)
        projector = (gradient, mass_gradient, gradient_lu)
        def solve(matrix, shift, wanted, start=None):
            return _nearest_eigenpairs(matrix, mass, projector, shift, wanted, dense,
                                       interior_count, kernel_cutoff, physical_count, start)

        values, vectors = solve(operator_at(np.sqrt(sigma + 0j)), sigma, count)
        values, vectors = values[:count], vectors[:, :count]
        iterations = np.zeros(count, dtype=int)
        operators = [None] * count
        if lossy_walls:
            # Converge each degenerate group with Zs at its own k0. Members of a group
            # within _DEGENERATE share Zs: their k0 differ below that relative level.
            order = np.argsort(values.real, kind="stable")
            groups, start = [], 0
            for position in range(1, count + 1):
                if (position == count or abs(values[order[position]] - values[order[start]])
                        > _DEGENERATE * abs(values[order[start]])):
                    groups.append(order[start:position])
                    start = position
            for group in groups:
                if len(group) == 1:
                    j = group[0]
                    values[j], vectors[:, j], iterations[j] = _residual_inverse_iteration(
                        values[j], vectors[:, j], stiffness, mass, wall_mass, wall_coefficient,
                        operator_at, projector)
                    operators[j] = operator_at(np.sqrt(values[j]))
                    continue
                # Exactly degenerate members: repeated shifted solves with a shared Zs.
                current = values[group].mean()
                for step in range(1, _FIXED_POINT_ITERATIONS + 1):
                    matrix = operator_at(np.sqrt(current))
                    guess = vectors[:, group] if step == 1 else new_vectors
                    new_values, new_vectors = solve(matrix, current, len(group),
                                                    guess.sum(axis=1))
                    new_values, new_vectors = new_values[:len(group)], new_vectors[:, :len(group)]
                    updated = new_values.mean()
                    converged = abs(updated - current) <= _FIXED_POINT_TOLERANCE * abs(updated)
                    current = updated
                    if converged:
                        break
                else:
                    raise RuntimeError("surface-impedance fixed point did not converge in "
                                       f"{_FIXED_POINT_ITERATIONS} iterations")
                values[group], vectors[:, group] = new_values, new_vectors
                iterations[group] = step
                for member in group:
                    operators[member] = matrix
        else:
            operators = [stiffness] * count
        selected = np.argsort(values.real, kind="stable")
        values, vectors, iterations = values[selected], vectors[:, selected], iterations[selected]
        operators = [operators[i] for i in selected]
        if lossless:
            if np.any(np.abs(values.imag) > _LOSSLESS_IMAG_LIMIT * np.abs(values)):
                raise RuntimeError("lossless cavity returned a complex eigenvalue")
            values = values.real.astype(complex)
        norms = np.sqrt(np.real(np.sum(vectors.conj() * (vacuum_mass @ vectors), axis=0)))
        if not np.isfinite(norms).all() or np.any(norms <= 0):
            raise RuntimeError("cavity eigensolver returned a zero or non-finite mass norm")
        vectors /= norms
        pivots = vectors[np.argmax(np.abs(vectors), axis=0), np.arange(count)]
        vectors *= (np.abs(pivots) / pivots)[None, :]
        gram = vectors.conj().T @ (vacuum_mass @ vectors)
        if np.linalg.eigvalsh(0.5 * (gram + gram.conj().T)).min() < _INDEPENDENCE_LIMIT:
            raise RuntimeError("cavity eigenvectors are not linearly independent")
        mass_vectors = mass @ vectors
        if not lossy_walls:
            # A linear complex-symmetric problem has M-biorthogonal eigenvectors.
            # With impedance walls each mode solves its own operator, so this
            # identity does not apply.
            separated = (np.abs(values[:, None] - values[None, :])
                         > _SEPARATION * np.abs(values)[:, None])
            bilinear = np.abs(vectors.T @ mass_vectors)
            magnitude = np.abs(vectors)
            diagonal = np.sum(magnitude * (abs(mass) @ magnitude), axis=0)
            scale = np.sqrt(np.outer(diagonal, diagonal))
            if np.any(bilinear[separated] > _BIORTHOGONALITY_LIMIT * scale[separated]):
                raise RuntimeError("cavity eigenvectors of distinct resonances are not "
                                   "M-biorthogonal")
        if gradient_lu is not None:
            leakage = gradient @ gradient_lu.solve(gradient.T @ mass_vectors)
            leakage_norm = np.sqrt(np.maximum(np.real(
                np.sum(leakage.conj() * (vacuum_mass @ leakage), axis=0)), 0))
            if np.max(leakage_norm) > GRADIENT_LIMIT:
                raise RuntimeError(f"cavity gradient component exceeds {GRADIENT_LIMIT:g}")
        left = np.column_stack([operators[j] @ vectors[:, j] for j in range(count)])
        right = mass_vectors * values
        residuals = np.linalg.norm(left - right, axis=0) / (
            np.linalg.norm(left, axis=0) + np.linalg.norm(right, axis=0))
        if lossy_walls:
            # Nonlinear residual: each mode against the operator at its own final k0.
            exact = np.column_stack([operator_at(np.sqrt(values[j])) @ vectors[:, j]
                                     for j in range(count)])
            residuals = np.maximum(residuals, np.linalg.norm(exact - right, axis=0) / (
                np.linalg.norm(exact, axis=0) + np.linalg.norm(right, axis=0)))
        if not np.isfinite(residuals).all() or np.max(residuals) > RESIDUAL_LIMIT:
            raise RuntimeError(f"cavity Maxwell relative residual exceeds {RESIDUAL_LIMIT:g}")
    except (RuntimeError, la.LinAlgError, ValueError) as exc:
        raise RuntimeError(f"material cavity solve failed near {target:g} Hz: {exc}") from exc

    coefficients = np.zeros((space.num_edges, count), dtype=complex)
    coefficients[free] = vectors
    electric = np.stack([eval_edge_field_3d(space, coefficients[:, j]) for j in range(count)])
    mesh_si = Mesh3D(normalized_mesh.nodes * length_scale, normalized_mesh.tets.copy(),
                     normalized_mesh.boundary, normalized_mesh.regions, normalized_mesh.region_names)
    eigenvalues = values * eigenvalue_scale
    frequencies = (C0 / (2 * np.pi)) * np.sqrt(eigenvalues)
    with np.errstate(divide="ignore"):
        quality = np.where(frequencies.imag == 0, np.inf,
                           frequencies.real / (2 * np.where(frequencies.imag == 0, 1,
                                                            frequencies.imag)))
    coefficients /= np.sqrt(length_scale)
    electric *= field_scale
    if not all(np.isfinite(array).all() for array in (eigenvalues, frequencies, coefficients,
                                                      electric)):
        raise RuntimeError("cavity SI output exceeds the supported floating-point range")
    return MaterialCavityResult(mesh_si, EdgeSpace3D(mesh_si), frequencies, frequencies.real.copy(),
                                quality, eigenvalues, coefficients, electric, residuals, pec,
                                eps, mu, count, target, lossless, conductivity, iterations)
