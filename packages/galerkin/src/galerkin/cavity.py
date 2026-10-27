# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Vacuum PEC box resonances near a specified frequency, with SI output.

Derivatives
-----------
lengths_m may hold JAX or PyTorch values: frequencies, eigenvalues, edge
coefficients and centroid fields are then in that library with reverse-mode
derivatives with respect to the three lengths
(docs/packages/galerkin/differentiation.md). Moving the box walls moves every
node, but only by an axis scaling x_a -> d_a x_a, under which the edge-element
matrices are exactly sum_a d_a^2 / (d_x d_y d_z) K_a and
(d_x d_y d_z) sum_a M_a / d_a^2 with fixed component matrices
(galerkin.core.kernels.nedelec3d_components). The NumPy solve runs on the
numbers; each mode then takes the bordered Newton step of galerkin.core.eigen
with those live matrices. Its normalization x^T M x = 1 is the solver's, and the
sign rule is locally constant. A mode within DEGENERATE_GAP of another eigenvalue
(cubes and many boxes have them) gets NaN derivatives and a
DegenerateModeWarning. The mesh and space in the result hold numbers.
"""

import warnings
from dataclasses import dataclass

import numpy as np
import scipy.linalg as la
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .mesh3d import Mesh3D, box_mesh
from .edge3d import (LOCAL_EDGES, EdgeSpace3D, assemble_curlcurl_3d, assemble_edge_mass_3d,
                     eval_edge_field_3d)
from .assembly3d import tet_gradients
from .core import eigen, forms, kernels
from .core import live as live_inputs
from .core import solve as core_solve
from .core.backend import lift, live_namespace, scatter_add
from .core.checks import contains_live, real_value
from .core.eigen import DEGENERATE_GAP, DegenerateModeWarning  # noqa: F401 (public here)
from .core.sparse import CooMatrix

_C0 = 299792458.0
_RESIDUAL_LIMIT = 1e-8
_ORTHOGONALITY_LIMIT = 1e-7
_GRADIENT_LIMIT = 1e-9
_DENSE_LIMIT = 256


@dataclass
class CavityResult:
    """Individual real standing-wave eigenfields, not unique polarization labels.

    Coordinates are metres; eigenvalues_m2 are squared wave numbers in m^-2.
    SI mass orthonormality gives edge_coefficients units m^-1/2 and
    electric_field units m^-3/2. This arbitrary normalization is not V/m or power.
    Edge orientation is low node id to high node id. PEC coefficients are zero.
    A finite near-target selection may cut a degenerate cluster.
    """

    mesh: Mesh3D
    space: EdgeSpace3D
    frequencies_hz: np.ndarray                 # (K,)
    eigenvalues_m2: np.ndarray                 # (K,)
    edge_coefficients: np.ndarray              # (E, K), full edge vectors
    electric_field: np.ndarray                 # (K, T, 3), tetrahedron centroids
    relative_residuals: np.ndarray             # (K,), free-edge equations
    pec_edge_ids: np.ndarray
    requested_modes: int
    target_frequency_hz: float
    search: str = "near_target"
    cluster_completeness: str = "not_certified"
    mode_count_policy: str = "exact_count_may_split_cluster"


def _positive_real(value, name):
    if (isinstance(value, (bool, np.bool_))
            or not isinstance(value, (int, float, np.integer, np.floating))):
        raise ValueError(f"{name} must be a finite positive number")
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f"{name} must be a finite positive number") from None
    if not np.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return value


def _positive_integer(value, name):
    if (isinstance(value, (bool, np.bool_))
            or not isinstance(value, (int, np.integer)) or value <= 0):
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def _triple(values, name, validate):
    try:
        values = tuple(values)
    except TypeError:
        raise ValueError(f"{name} must contain three values") from None
    if len(values) != 3:
        raise ValueError(f"{name} must contain three values")
    return tuple(validate(value, f"{name}[{i}]") for i, value in enumerate(values))


def _gradient_space(space, free, mass):
    """Interior nodal gradients in the PEC-constrained edge space.

    C maps nodal potentials (zero on the boundary) to edge circulations.
    The kernel on this simply connected box has exactly one dimension per
    interior node. C^T M C is positive definite, even though curl-curl is singular.
    """
    mesh = space.mesh
    interior = np.setdiff1d(np.arange(mesh.num_nodes), mesh.boundary_nodes())
    incidence = sp.coo_matrix(
        (np.tile([-1.0, 1.0], len(free)),
         (np.repeat(np.arange(len(free)), 2), space.edges[free].ravel())),
        shape=(len(free), mesh.num_nodes)).tocsc()[:, interior]
    mass_gradient = mass @ incidence
    factor = spla.splu((incidence.T @ mass_gradient).tocsc()) if len(interior) else None
    return incidence, mass_gradient, factor


def _cavity_mesh(lengths, cells):
    """Alternate Kuhn diagonals without changing cells, vertices or tet shapes.

    Reflect local coordinates along axis a whenever the cell index on a is odd.
    Two cells sharing a face have the same tangential parities, hence the same
    face diagonal: this is a conforming triangulation. Even subdivision counts
    restore coordinate-reflection symmetry across the box. No refinement or
    spectral information enters the mesh construction.
    """
    base = box_mesh(*lengths, *cells)
    shape = tuple(n + 1 for n in cells)
    grid = np.stack(np.unravel_index(base.tets, shape), axis=-1)
    lower = grid.min(axis=1)[:, None, :]
    local = grid - lower
    reflected = lower + np.where(lower % 2, 1 - local, local)
    tets = (reflected[:, :, 0] * shape[1] + reflected[:, :, 1]) * shape[2] + reflected[:, :, 2]
    return Mesh3D(base.nodes, tets, base.boundary, base.regions, base.region_names)


def solve_cavity_box(lengths_m, subdivisions, *, num_modes=6,
                     target_frequency_hz) -> CavityResult:
    """Solve a vacuum rectangular box with PEC on all six walls.

    lengths_m may hold JAX or PyTorch values (see the module docstring); the
    target only selects modes and carries no derivative.

    lengths_m: three finite positive SI lengths. The box starts at the origin.
    subdivisions: three positive integers; each cell becomes six tetrahedra,
        with Kuhn diagonals reflected according to the cell's coordinate parity.
    num_modes: number of individual eigenpairs, including multiplicities.
    target_frequency_hz: required finite positive search target in Hz.

    Select modes nearest the target in squared frequency, then return them in
    ascending frequency order. This is a finite candidate search, not a complete
    lowest spectrum, interval enumeration, or complete-degeneracy guarantee.

    SI edge mass normalization is Q.T @ M_SI @ Q = I; each real mode's largest
    absolute edge coefficient is positive. Degenerate bases remain nonunique.
    Invalid inputs raise ValueError. Insufficient physical modes, nonconvergence,
    factorization failures, or failed residual/orthogonality checks raise
    RuntimeError without a partial result. See docs/packages/galerkin/cavity_solver.md for the
    fixed search and validation policy.
    """
    result = _solve_cavity_box_numpy(live_inputs.numbers(lengths_m), subdivisions,
                                     num_modes=num_modes,
                                     target_frequency_hz=live_inputs.numbers(target_frequency_hz))
    if not contains_live(lengths_m):
        return result
    return _live_result(lengths_m, result)


def _restricted(matrix, free, size):
    position = np.full(size, -1)
    position[free] = np.arange(len(free))
    keep = np.flatnonzero((position[matrix.rows] >= 0) & (position[matrix.cols] >= 0))
    return CooMatrix(position[matrix.rows[keep]], position[matrix.cols[keep]],
                     matrix.values[keep], (len(free), len(free)))


def _live_result(lengths_m, result):
    """The NumPy result with derivatives with respect to the box lengths (module docstring)."""
    leaves = live_inputs.leaves(lengths_m)
    xp = live_namespace(*leaves)
    lengths = xp.reshape(real_value(lengths_m, "lengths_m"), (3,))
    scale = lengths / lift(xp, np.asarray(live_inputs.numbers(lengths_m), dtype=float).reshape(3))
    volume = scale[0] * scale[1] * scale[2]
    space, count = result.space, result.requested_modes
    free = np.setdiff1d(np.arange(space.num_edges), result.pec_edge_ids)
    curl_parts, mass_parts = kernels.nedelec3d_components(space)

    def matrix(parts, factors):
        element = sum(factor * lift(xp, part) for factor, part in zip(factors, parts))
        full = forms.matrix(space.tet_edges, space.tet_edges, element,
                            (space.num_edges, space.num_edges)).coalesce()
        return _restricted(full, free, space.num_edges)
    stiffness = matrix(curl_parts, [scale[a] ** 2 / volume for a in range(3)])
    mass = matrix(mass_parts, [volume / scale[a] ** 2 for a in range(3)])
    degenerate = eigen.degenerate_modes(eigen.scipy_matrix(stiffness), eigen.scipy_matrix(mass),
                                        result.eigenvalues_m2)
    if degenerate:
        warnings.warn(f"modes {degenerate} belong to degenerate eigenvalues (relative gap <= "
                      f"{DEGENERATE_GAP:g}); their derivatives are NaN", DegenerateModeWarning,
                      stacklevel=3)
    coefficients, eigenvalues = [], []
    for k in range(count):
        if k in degenerate:
            x = core_solve.nan_derivative(xp, result.edge_coefficients[free, k], leaves)
            lam = core_solve.nan_derivative(xp, np.asarray(result.eigenvalues_m2[k]), leaves)
        else:
            x, lam = eigen.refine(xp, stiffness, mass, result.edge_coefficients[free, k],
                                  result.eigenvalues_m2[k])
        coefficients.append(scatter_add(xp, space.num_edges, free, x))
        eigenvalues.append(lam)
    eigenvalues = xp.stack(eigenvalues)
    coefficients = xp.stack(coefficients, axis=1)
    g, _ = tet_gradients(space.mesh)
    local = np.asarray(LOCAL_EDGES)
    basis = lift(xp, 0.25 * (g[:, local[:, 1], :] - g[:, local[:, 0], :]))   # (T, 6, 3) at centroids
    signs = lift(xp, space.signs)
    electric = xp.stack([xp.einsum("te,ted->td", signs * coefficients[:, k][space.tet_edges], basis)
                         for k in range(count)]) / scale
    return CavityResult(result.mesh, space, (_C0 / (2 * np.pi)) * xp.sqrt(eigenvalues), eigenvalues,
                        coefficients, electric, lift(xp, result.relative_residuals),
                        result.pec_edge_ids, count, result.target_frequency_hz)


def _solve_cavity_box_numpy(lengths_m, subdivisions, *, num_modes, target_frequency_hz):
    """The NumPy solve of ``solve_cavity_box`` (NumPy inputs only)."""
    lengths = np.asarray(_triple(lengths_m, "lengths_m", _positive_real))
    cells = _triple(subdivisions, "subdivisions", _positive_integer)
    count = _positive_integer(num_modes, "num_modes")
    target = _positive_real(target_frequency_hz, "target_frequency_hz")
    length_scale = float(lengths.max())
    with np.errstate(over="ignore", under="ignore", divide="ignore", invalid="ignore"):
        normalized_lengths = lengths / length_scale
        target_k = (2 * np.pi / _C0) * target * length_scale
        sigma = target_k * target_k
        fundamental = np.pi**2 * np.sort(1 / normalized_lengths**2)[:2].sum()
        eigenvalue_scale = 1 / np.float64(length_scale)**2
        field_scale = np.float64(length_scale)**-1.5
        reciprocal_lengths = 1 / normalized_lengths
    if (not np.isfinite([sigma, fundamental, eigenvalue_scale, field_scale]).all()
            or min(sigma, eigenvalue_scale, field_scale) <= 0
            or not np.isfinite(reciprocal_lengths).all()):
        raise ValueError("box lengths and target exceed the supported floating-point range")

    normalized_mesh = _cavity_mesh(normalized_lengths, cells)
    space = EdgeSpace3D(normalized_mesh)
    pec = space.boundary_edge_ids()
    free = np.setdiff1d(np.arange(space.num_edges), pec)
    interior_count = int(np.prod(np.asarray(cells, dtype=object) - 1))
    physical_count = len(free) - interior_count
    if count > physical_count:
        raise RuntimeError(f"requested {count} modes but this PEC mesh has only "
                           f"{physical_count} physical degrees of freedom; refine subdivisions")
    stiffness = assemble_curlcurl_3d(space)[free][:, free].tocsc()
    mass = assemble_edge_mass_3d(space)[free][:, free].tocsc()
    kernel_cutoff = 1e-8 * fundamental  # independent of the requested target

    try:
        gradient, mass_gradient, gradient_lu = _gradient_space(space, free, mass)
        if len(free) <= _DENSE_LIMIT:
            values, vectors = la.eigh(stiffness.toarray(), mass.toarray())
            if np.count_nonzero(np.abs(values) <= kernel_cutoff) != interior_count:
                raise RuntimeError("computed gradient kernel dimension does not match the PEC box")
        else:
            candidates = min(max(2 * count, count + 8), physical_count, len(free) - 1)
            shifted_lu = spla.splu(stiffness - sigma * mass)

            def inverse(rhs):
                # P = I - C (C.T M C)^-1 C.T M. OPinv=P A^-1 P.T is
                # symmetric, and OPinv M annihilates gradients. Its physical
                # eigenvalues remain 1/(k^2-sigma); no penalty alters Maxwell.
                if gradient_lu is not None:
                    rhs = rhs - mass_gradient @ gradient_lu.solve(gradient.T @ rhs)
                result = shifted_lu.solve(rhs)
                if gradient_lu is not None:
                    result -= gradient @ gradient_lu.solve(mass_gradient.T @ result)
                return result

            operator = spla.LinearOperator(stiffness.shape, matvec=inverse, dtype=float)
            values, vectors = spla.eigsh(
                stiffness, k=candidates, M=mass, sigma=sigma, which="LM", OPinv=operator,
                v0=np.random.default_rng(0).standard_normal(len(free)),
                ncv=min(len(free), max(6 * candidates, 90)), tol=1e-10, maxiter=50000)
        if not np.isfinite(values).all() or not np.isfinite(vectors).all():
            raise RuntimeError("cavity eigensolver returned non-finite eigenpairs")
        if np.any(values < -kernel_cutoff):
            raise RuntimeError("cavity eigensolver returned a negative physical eigenvalue")
        physical = np.flatnonzero(values > kernel_cutoff)
        if len(physical) < count:
            raise RuntimeError(f"requested {count} modes but found only {len(physical)} physical "
                               "candidates near the target; change target or refine subdivisions")
        nearest = physical[np.argsort(np.abs(values[physical] - sigma), kind="stable")[:count]]
        selected = nearest[np.argsort(values[nearest], kind="stable")]
        values, vectors = values[selected], vectors[:, selected].copy()
        norms = np.sqrt(np.sum(vectors * (mass @ vectors), axis=0))
        if not np.isfinite(norms).all() or np.any(norms <= 0):
            raise RuntimeError("cavity eigensolver returned a zero or non-finite mass norm")
        vectors /= norms
        pivots = vectors[np.argmax(np.abs(vectors), axis=0), np.arange(count)]
        vectors *= np.where(pivots < 0, -1.0, 1.0)
        mass_vectors = mass @ vectors
        orthogonality = np.max(np.abs(vectors.T @ mass_vectors - np.eye(count)))
        if orthogonality > _ORTHOGONALITY_LIMIT:
            raise RuntimeError(f"cavity mass orthogonality error {orthogonality:.3g} exceeds "
                               f"{_ORTHOGONALITY_LIMIT:g}")
        if gradient_lu is not None:
            leakage = gradient @ gradient_lu.solve(gradient.T @ mass_vectors)
            leakage_norm = np.sqrt(np.maximum(np.sum(leakage * (mass @ leakage), axis=0), 0))
            if np.max(leakage_norm) > _GRADIENT_LIMIT:
                raise RuntimeError(f"cavity gradient component exceeds {_GRADIENT_LIMIT:g}")
        left, right = stiffness @ vectors, mass_vectors * values
        residuals = np.linalg.norm(left - right, axis=0) / (
            np.linalg.norm(left, axis=0) + np.linalg.norm(right, axis=0))
        if not np.isfinite(residuals).all() or np.max(residuals) > _RESIDUAL_LIMIT:
            raise RuntimeError(f"cavity Maxwell relative residual exceeds {_RESIDUAL_LIMIT:g}")
    except (RuntimeError, la.LinAlgError, ValueError) as exc:
        raise RuntimeError(f"PEC cavity solve failed near {target:g} Hz: {exc}") from exc

    coefficients = np.zeros((space.num_edges, count))
    coefficients[free] = vectors
    electric = np.stack([eval_edge_field_3d(space, coefficients[:, j]) for j in range(count)])
    mesh_si = Mesh3D(normalized_mesh.nodes * length_scale, normalized_mesh.tets.copy(),
                     normalized_mesh.boundary, normalized_mesh.regions, normalized_mesh.region_names)
    eigenvalues = values * eigenvalue_scale
    frequencies = (_C0 / (2 * np.pi)) * np.sqrt(eigenvalues)
    coefficients /= np.sqrt(length_scale)
    electric *= field_scale
    if not all(np.isfinite(array).all() for array in (eigenvalues, frequencies, coefficients, electric)):
        raise RuntimeError("cavity SI output exceeds the supported floating-point range")
    return CavityResult(mesh_si, EdgeSpace3D(mesh_si), frequencies, eigenvalues,
                        coefficients, electric, residuals, pec, count, target)
