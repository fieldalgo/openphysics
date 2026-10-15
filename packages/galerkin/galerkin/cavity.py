# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Vacuum PEC box resonances near a specified frequency, with SI output."""

from dataclasses import dataclass
from numbers import Integral, Real

import numpy as np
import scipy.linalg as la
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .mesh3d import Mesh3D, box_mesh
from .edge3d import (EdgeSpace3D, assemble_curlcurl_3d, assemble_edge_mass_3d,
                     eval_edge_field_3d)

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
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite positive number")
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f"{name} must be a finite positive number") from None
    if not np.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return value


def _positive_integer(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value <= 0:
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


def solve_cavity_box(lengths_m, subdivisions, *, num_modes=6,
                     target_frequency_hz) -> CavityResult:
    """Solve a vacuum rectangular box with PEC on all six walls.

    lengths_m: three finite positive SI lengths. The box starts at the origin.
    subdivisions: three positive integers; each cell becomes six tetrahedra.
    num_modes: number of individual eigenpairs, including multiplicities.
    target_frequency_hz: required finite positive search target in Hz.

    Select modes nearest the target in squared frequency, then return them in
    ascending frequency order. This is a finite candidate search, not a complete
    lowest spectrum, interval enumeration, or complete-degeneracy guarantee.

    SI edge mass normalization is Q.T @ M_SI @ Q = I; each real mode's largest
    absolute edge coefficient is positive. Degenerate bases remain nonunique.
    Invalid inputs raise ValueError. Insufficient physical modes, nonconvergence,
    factorization failures, or failed residual/orthogonality checks raise
    RuntimeError without a partial result. See docs/cavity_solver.md for the
    fixed search and validation policy.
    """
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

    normalized_mesh = box_mesh(*normalized_lengths, *cells)
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
