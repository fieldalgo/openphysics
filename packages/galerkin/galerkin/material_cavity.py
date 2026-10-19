# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""PEC box resonances with box-shaped dielectric/magnetic, possibly lossy, regions.

Time convention exp(+j*omega*t): passive materials have eps_r = eps' - j*eps''
with eps'' >= 0 (likewise mu_r), and decaying resonances have Im(omega) > 0.
The weak form curl(mu_r^-1 curl E) = k0^2 eps_r E gives the complex-symmetric
(non-Hermitian) generalized problem S(1/mu_r) q = k0^2 M(eps_r) q. The quality
factor is Q = Re(omega) / (2 Im(omega)).
"""

from dataclasses import dataclass

import numpy as np
import scipy.linalg as la
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .mesh3d import Mesh3D
from .edge3d import (EdgeSpace3D, assemble_curlcurl_3d, assemble_edge_mass_3d,
                     eval_edge_field_3d)
from .cavity import (_C0, _DENSE_LIMIT, _GRADIENT_LIMIT, _RESIDUAL_LIMIT,
                     _cavity_mesh, _positive_integer, _positive_real, _triple)

_INDEPENDENCE_LIMIT = 1e-6
_BIORTHOGONALITY_LIMIT = 1e-7
_SEPARATION = 1e-6
_LOSSLESS_IMAG_LIMIT = 1e-9
_GRID_TOLERANCE = 1e-9
# Symmetric sparsity: minimum degree on A^T+A gives far less fill than COLAMD.
_ORDERING = "MMD_AT_PLUS_A"


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
    infinite when every material is lossless. Edge coefficients are complex with
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


def solve_material_cavity_box(lengths_m, subdivisions, *, regions=(), num_modes=6,
                              target_frequency_hz) -> MaterialCavityResult:
    """Solve a PEC rectangular box filled with vacuum and box-shaped material regions.

    lengths_m, subdivisions, num_modes and target_frequency_hz follow
    ``solve_cavity_box``; the mesh is the same alternating Kuhn mesh.
    regions: sequence of ``CavityMaterialRegion``; later regions override earlier
        ones where they overlap, and uncovered space is vacuum. Each tetrahedron
        takes the material containing its centroid. Bounds must be grid planes.

    Select modes nearest the real target in complex squared wave number,
    ``|k0^2 - (2*pi*f_target/c0)^2|``, then return them in ascending real
    frequency. Invalid inputs raise ValueError; nonconvergence, insufficient
    modes or failed quality checks raise RuntimeError without a partial result.
    See docs/material_cavity.md for the conventions and validation.
    """
    lengths = np.asarray(_triple(lengths_m, "lengths_m", _positive_real))
    cells = _triple(subdivisions, "subdivisions", _positive_integer)
    count = _positive_integer(num_modes, "num_modes")
    target = _positive_real(target_frequency_hz, "target_frequency_hz")
    materials = _regions(regions, lengths, cells)
    length_scale = float(lengths.max())
    with np.errstate(over="ignore", under="ignore", divide="ignore", invalid="ignore"):
        normalized_lengths = lengths / length_scale
        target_k = (2 * np.pi / _C0) * target * length_scale
        sigma = target_k * target_k
        fundamental = np.pi**2 * np.sort(1 / normalized_lengths**2)[:2].sum()
        eigenvalue_scale = 1 / np.float64(length_scale)**2
        field_scale = np.float64(length_scale)**-1.5
    if (not np.isfinite([sigma, fundamental, eigenvalue_scale, field_scale]).all()
            or min(sigma, eigenvalue_scale, field_scale) <= 0):
        raise ValueError("box lengths and target exceed the supported floating-point range")

    normalized_mesh = _cavity_mesh(normalized_lengths, cells)
    centroid_grid = (normalized_mesh.nodes[normalized_mesh.tets].mean(axis=1)
                     / normalized_lengths * np.asarray(cells))
    eps = np.ones(normalized_mesh.num_tets, dtype=complex)
    mu = np.ones(normalized_mesh.num_tets, dtype=complex)
    for planes, eps_value, mu_value in materials:
        inside = np.all((centroid_grid > planes[:, 0]) & (centroid_grid < planes[:, 1]), axis=1)
        eps[inside], mu[inside] = eps_value, mu_value
    lossless = bool(np.all(eps.imag == 0) and np.all(mu.imag == 0))

    space = EdgeSpace3D(normalized_mesh)
    pec = space.boundary_edge_ids()
    free = np.setdiff1d(np.arange(space.num_edges), pec)
    interior_count = int(np.prod(np.asarray(cells, dtype=object) - 1))
    physical_count = len(free) - interior_count
    if count > physical_count:
        raise RuntimeError(f"requested {count} modes but this PEC mesh has only "
                           f"{physical_count} physical degrees of freedom; refine subdivisions")
    stiffness, mass = _material_matrices(space, free, eps, mu)
    vacuum_mass = assemble_edge_mass_3d(space)[free][:, free].tocsc()
    # Physical k0^2 are at least about the vacuum fundamental / max|eps mu|.
    kernel_cutoff = 1e-8 * fundamental / float(np.max(np.abs(eps * mu)))

    try:
        mesh = space.mesh
        interior = np.setdiff1d(np.arange(mesh.num_nodes), mesh.boundary_nodes())
        gradient = sp.coo_matrix(
            (np.tile([-1.0, 1.0], len(free)),
             (np.repeat(np.arange(len(free)), 2), space.edges[free].ravel())),
            shape=(len(free), mesh.num_nodes)).tocsc()[:, interior]
        # Complex-symmetric projector P = I - C (C^T M C)^-1 C^T M (no conjugation).
        mass_gradient = (mass @ gradient).tocsc()
        gradient_lu = (spla.splu((gradient.T @ mass_gradient).tocsc(),
                                  permc_spec=_ORDERING)
                       if len(interior) else None)
        if len(free) <= _DENSE_LIMIT:
            values, vectors = la.eig(stiffness.toarray(), mass.toarray())
            if not np.isfinite(values).all():
                raise RuntimeError("dense cavity eigensolver returned non-finite eigenvalues")
            if np.count_nonzero(np.abs(values) <= kernel_cutoff) != interior_count:
                raise RuntimeError("computed gradient kernel dimension does not match the PEC box")
        else:
            candidates = min(max(2 * count, count + 8), physical_count, len(free) - 2)
            shifted_lu = spla.splu((stiffness - sigma * mass).tocsc(), permc_spec=_ORDERING)

            def inverse(rhs):
                # OPinv = P (S - sigma M)^-1 P^T; P^T M = M P, so T = OPinv M = P A^-1 M P
                # annihilates gradients and keeps physical values 1/(k^2 - sigma).
                rhs = np.asarray(rhs, dtype=complex).ravel()
                if gradient_lu is not None:
                    rhs = rhs - mass_gradient @ gradient_lu.solve(gradient.T @ rhs)
                result = shifted_lu.solve(rhs)
                if gradient_lu is not None:
                    result = result - gradient @ gradient_lu.solve(mass_gradient.T @ result)
                return result

            # ARPACK's generalized mode needs a Hermitian positive M; this M is complex
            # symmetric, so solve the standard problem for T = OPinv M directly.
            operator = spla.LinearOperator(stiffness.shape, matvec=lambda x: inverse(mass @ x),
                                           dtype=complex)
            transformed, vectors = spla.eigs(
                operator, k=candidates, which="LM",
                v0=np.random.default_rng(0).standard_normal(len(free)).astype(complex),
                ncv=min(len(free), max(6 * candidates, 90)), tol=1e-10, maxiter=50000)
            # Gradients map to transformed value 0, i.e. an infinite k^2; drop them.
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
        nearest = physical[np.argsort(np.abs(values[physical] - sigma), kind="stable")[:count]]
        selected = nearest[np.argsort(values[nearest].real, kind="stable")]
        values, vectors = values[selected], vectors[:, selected].astype(complex)
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
            if np.max(leakage_norm) > _GRADIENT_LIMIT:
                raise RuntimeError(f"cavity gradient component exceeds {_GRADIENT_LIMIT:g}")
        left, right = stiffness @ vectors, mass_vectors * values
        residuals = np.linalg.norm(left - right, axis=0) / (
            np.linalg.norm(left, axis=0) + np.linalg.norm(right, axis=0))
        if not np.isfinite(residuals).all() or np.max(residuals) > _RESIDUAL_LIMIT:
            raise RuntimeError(f"cavity Maxwell relative residual exceeds {_RESIDUAL_LIMIT:g}")
    except (RuntimeError, la.LinAlgError, ValueError) as exc:
        raise RuntimeError(f"material cavity solve failed near {target:g} Hz: {exc}") from exc

    coefficients = np.zeros((space.num_edges, count), dtype=complex)
    coefficients[free] = vectors
    electric = np.stack([eval_edge_field_3d(space, coefficients[:, j]) for j in range(count)])
    mesh_si = Mesh3D(normalized_mesh.nodes * length_scale, normalized_mesh.tets.copy(),
                     normalized_mesh.boundary, normalized_mesh.regions, normalized_mesh.region_names)
    eigenvalues = values * eigenvalue_scale
    frequencies = (_C0 / (2 * np.pi)) * np.sqrt(eigenvalues)
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
                                eps, mu, count, target, lossless)
