# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Cavity resonances with dielectric/magnetic, possibly lossy, regions and impedance walls:
galerkin's public material cavity API, in SI and exp(-i omega t).

``solve_material_cavity_box`` places axis-aligned material boxes (``CavityMaterialRegion``) in
its own Kuhn box; ``solve_material_cavity`` takes any tetrahedral mesh of the format in
docs/packages/galerkin/mesh3d_format.md with materials per named region and walls per face
tag. Both share the assembly, search and checks below.

Units and convention
--------------------
Quantities are keyword-only registry names in SI units: ``box_size`` (m), ``mode_count``,
``target_frequency`` (Hz), ``electrical_conductivity`` (S/m per wall), the region corners
``lower_corner_position`` and ``upper_corner_position`` (m) and the material constants
``relative_permittivity`` and ``relative_permeability``. Complex values follow exp(-i omega t):
a passive material has eps_r = eps' + i eps'' with eps'' >= 0 (likewise mu_r), and a decaying
resonance has Im(resonant_frequency) < 0, with the quality factor
Q = Re(f) / (-2 Im(f)) > 0. The returned ``MaterialCavityResult`` is frozen and names its
fields by the registry, with ``.units``.

The solver computes in exp(+j omega t) (below), and the public functions convert in one place,
``galerkin._conventions``: every complex input reaches the private bodies
(``_solve_material_cavity_box``, ``_solve_material_cavity``) through ``to_kernel``, and every
complex output is ``to_public`` of the body's, never re-derived (rule 5 of the galerkin step).
The bodies keep the solver's code and names (the box lengths, the subdivisions, ``num_modes``,
``target_frequency_hz``, ``wall_conductivity_s_per_m``, ``walls``; the regions as the private
``_KernelRegion`` with ``bounds_m``) and return the private record
``_MaterialCavityKernelResult``. There is no kernel export of the cavity solvers (spec 4.3);
refusals name the public quantities.

The solver's convention exp(+j*omega*t): passive materials have eps_r = eps' - j*eps''
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

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, ClassVar

import numpy as np
import scipy.linalg as la
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .mesh3d import Mesh3D
from .edge3d import (EdgeSpace3D, assemble_curlcurl_3d as _assemble_curlcurl_3d,
                     assemble_edge_mass_3d as _assemble_edge_mass_3d, eval_edge_field_3d as _eval_edge_field_3d)
from .core.spaces import edge_ids
from ._cavity_common import (C0, DENSE_LIMIT, GRADIENT_LIMIT, RESIDUAL_LIMIT, cavity_mesh,
                             face_edge_ids, gradient_incidence, gradient_potentials,
                             normalized_mesh, refuse_live_mesh_inputs, search_parameters)
from .core.checks import positive_integer, positive_real, refuse_live, triple
from .core.eigen import arpack_rng
from ._conventions import to_kernel, to_public
from ._public import refuse_text

__all__ = ["WALLS", "CavityMaterialRegion", "MaterialCavityResult", "solve_material_cavity_box",
           "solve_material_cavity"]

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


def _public_material(value, name):
    """A finite passive complex constant under exp(-i omega t) (Re > 0, Im >= 0), as complex."""
    refuse_text(name, value)
    refuse_live(value, name)
    if isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (int, float, complex, np.integer, np.floating, np.complexfloating)):
        raise ValueError(f"{name} must be a finite complex number")
    value = complex(value)
    if not (np.isfinite(value) and value.real > 0 and value.imag >= 0):
        raise ValueError(f"{name} must be finite with positive real part and non-negative "
                         "imaginary part (passive under exp(-i omega t): a loss is Im >= 0)")
    return value


def _corner(value, name):
    """Three finite real coordinates in m, as a tuple of floats."""
    refuse_text(name, value)
    refuse_live(value, name)
    try:
        values = tuple(value)
    except TypeError:
        raise ValueError(f"{name} must be three coordinates (x, y, z) in m") from None
    if len(values) != 3:
        raise ValueError(f"{name} must be three coordinates (x, y, z) in m")
    for v in values:
        if (isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, float, np.integer, np.floating))
                or not np.isfinite(v)):
            raise ValueError(f"{name} must be three finite real coordinates in m")
    return tuple(float(v) for v in values)


@dataclass(frozen=True, kw_only=True)
class CavityMaterialRegion:
    """An axis-aligned box ``[x0, x1] x [y0, y1] x [z0, z1]`` of one material; frozen.

    lower_corner_position: (x0, y0, z0) and upper_corner_position: (x1, y1, z1), in m from the
        origin corner of ``solve_material_cavity_box``'s box. Every coordinate must lie on a mesh
        grid plane (the solver checks it), so the mesh conforms to the region.
    relative_permittivity, relative_permeability: finite complex constants under
        exp(-i omega t): Re > 0 and Im >= 0 (passive, a loss is eps' + i eps''); default 1.0.

    The constructor refuses text (TypeError), JAX or PyTorch values (TypeError; the cavity
    solvers run on NumPy) and other invalid values (ValueError).
    """

    lower_corner_position: tuple
    upper_corner_position: tuple
    relative_permittivity: complex = 1.0
    relative_permeability: complex = 1.0

    def __post_init__(self):
        for name in ("lower_corner_position", "upper_corner_position"):
            object.__setattr__(self, name, _corner(getattr(self, name), name))
        for name in ("relative_permittivity", "relative_permeability"):
            object.__setattr__(self, name, _public_material(getattr(self, name), name))


@dataclass(frozen=True)
class _KernelRegion:
    """A material box as the private bodies take it (the former ``CavityMaterialRegion``):
    ``bounds_m`` the three (low, high) pairs in m, the constants under exp(+j*omega*t)."""

    bounds_m: tuple
    relative_permittivity: complex = 1.0
    relative_permeability: complex = 1.0


@dataclass(frozen=True)
class MaterialCavityResult:
    """Complex resonances of a box or mesh with piecewise-constant materials; frozen.

    resonant_frequency: (K,) complex f in Hz, ascending Re f > 0; under exp(-i omega t) a decaying
        mode has Im f < 0. quality_factor: (K,) Re f / (-2 Im f) > 0, infinite when every
        material and wall is lossless. wavenumber_squared: (K,) complex k0^2 in 1/m^2.
    mass_normalized_electric_field_line_integral: (E, K) complex edge coefficients with the
        Hermitian vacuum-mass normalization q^H M0 q = 1 (1/m^(1/2)) and the largest-magnitude
        coefficient real and positive; mass_normalized_electric_field: (K, T, 3) complex centroid
        fields (1/m^(3/2)). Not V/m or power.
    relative_residual: (K,); relative_permittivity, relative_permeability: (T,) complex, the
        material of each tetrahedron (exp(-i omega t)); electrical_conductivity: {wall or face
        tag: S/m, or None for PEC}; iteration_count: (K,) fixed-point iterations, zero without
        lossy walls; lossless: no lossy material and no conducting wall.
    mesh, space, pec_edges, mode_count, target_frequency and gradient_kernel_dimension as in
    ``galerkin.CavityResult``. ``.units`` maps each quantity field to its SI unit.
    """

    mesh: Mesh3D
    space: EdgeSpace3D
    resonant_frequency: Any                    # (K,) complex
    quality_factor: Any                        # (K,)
    wavenumber_squared: Any                    # (K,) complex
    mass_normalized_electric_field_line_integral: Any   # (E, K) complex
    mass_normalized_electric_field: Any        # (K, T, 3) complex, centroids
    relative_residual: Any                     # (K,)
    pec_edges: np.ndarray
    relative_permittivity: Any                 # (T,) complex
    relative_permeability: Any                 # (T,) complex
    mode_count: int
    target_frequency: float
    lossless: bool
    electrical_conductivity: Mapping           # wall or face tag -> S/m, or None for PEC
    iteration_count: Any                       # (K,), zero without lossy walls
    gradient_kernel_dimension: int = 0

    time_convention: ClassVar[str] = "exp(-i omega t)"
    search: ClassVar[str] = "near_target"
    cluster_completeness: ClassVar[str] = "not_certified"
    mode_count_policy: ClassVar[str] = "exact_count_may_split_cluster"
    UNITS: ClassVar = MappingProxyType({
        "resonant_frequency": "Hz", "quality_factor": "1", "wavenumber_squared": "1/m^2",
        "mass_normalized_electric_field_line_integral": "1/m^(1/2)",
        "mass_normalized_electric_field": "1/m^(3/2)", "relative_residual": "1",
        "relative_permittivity": "1", "relative_permeability": "1", "mode_count": "1",
        "target_frequency": "Hz", "electrical_conductivity": "S/m", "iteration_count": "1"})

    @property
    def units(self):
        """{field: canonical SI unit} of every quantity field (read-only)."""
        return self.UNITS


@dataclass
class _MaterialCavityKernelResult:
    """The private bodies' record (the former ``MaterialCavityResult``), under exp(+j*omega*t).

    ``eigenvalues_m2`` are complex k0^2 (m^-2); ``frequencies_hz`` complex
    ``c0*sqrt(k0**2)/(2*pi)`` with Re > 0; ``quality_factors`` Re f / (2 Im f),
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
    gradient_kernel_dimension: int = 0


def _public_result(result: _MaterialCavityKernelResult) -> MaterialCavityResult:
    """The public, frozen result of a private body's record: every complex value is ``to_public`` of
    the body's (exp(+j omega t) to exp(-i omega t)), never re-derived. The quality factor is real:
    the body's Re f / (2 Im f) is the same double as Re f / (-2 Im f) of the public frequency."""
    return MaterialCavityResult(
        mesh=result.mesh, space=result.space, resonant_frequency=to_public(result.frequencies_hz),
        quality_factor=result.quality_factors, wavenumber_squared=to_public(result.eigenvalues_m2),
        mass_normalized_electric_field_line_integral=to_public(result.edge_coefficients),
        mass_normalized_electric_field=to_public(result.electric_field),
        relative_residual=result.relative_residuals, pec_edges=result.pec_edge_ids,
        relative_permittivity=to_public(result.tet_relative_permittivity),
        relative_permeability=to_public(result.tet_relative_permeability),
        mode_count=result.requested_modes, target_frequency=result.target_frequency_hz,
        lossless=result.lossless, electrical_conductivity=MappingProxyType(dict(result.wall_conductivity_s_per_m)),
        iteration_count=result.fixed_point_iterations,
        gradient_kernel_dimension=result.gradient_kernel_dimension)


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
    """The kernel regions (``_KernelRegion``) as grid planes and constants, checked against the box."""
    if isinstance(regions, _KernelRegion):
        raise ValueError("regions must be a sequence of CavityMaterialRegion")
    try:
        regions = tuple(regions)
    except TypeError:
        raise ValueError("regions must be a sequence of CavityMaterialRegion") from None
    checked = []
    for r, region in enumerate(regions):
        if not isinstance(region, _KernelRegion):
            raise ValueError(f"regions[{r}] must be a CavityMaterialRegion")
        refuse_live([region.bounds_m, region.relative_permittivity, region.relative_permeability],
                    f"regions[{r}]")
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
                        f"(multiples of {lengths[axis] / cells[axis]:g} m); adjust subdivision_count")
                grid.append(index)
            if not 0 <= grid[0] < grid[1] <= cells[axis]:
                raise ValueError(f"regions[{r}] needs 0 <= lower_corner_position < upper_corner_position "
                                 f"<= box_size on axis {axis}")
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
        stiffness = stiffness + (_assemble_curlcurl_3d(space, mask)[free][:, free]
                                 / mu_value).tocsc()
        mass = mass + (_assemble_edge_mass_3d(space, mask)[free][:, free] * eps_value).tocsc()
    return stiffness.tocsc(), mass.tocsc()


def _wall_conductivities(value):
    if value is None:
        return dict.fromkeys(WALLS)
    if isinstance(value, dict):
        unknown = sorted(set(value) - set(WALLS), key=str)
        if unknown:
            raise ValueError(f"unknown walls {unknown}; use {WALLS}")
        return {wall: (None if value.get(wall) is None
                       else positive_real(value[wall], f"electrical_conductivity[{wall}]"))
                for wall in WALLS}
    sigma = positive_real(value, "electrical_conductivity")
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
    return np.unique(edge_ids(space, pairs))


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
    ids = edge_ids(space, np.stack([low.ravel(), high.ravel()], axis=1)).reshape(-1, 3)
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
            ncv=min(stiffness.shape[0], subspace), tol=1e-10, maxiter=50000, **arpack_rng())
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



def _kernel_regions(regions):
    """The public regions as the bodies take them: ``_KernelRegion`` with ``bounds_m`` and the
    constants through ``to_kernel``."""
    if isinstance(regions, (CavityMaterialRegion, str, bytes, Mapping)):
        raise ValueError("regions must be a sequence of CavityMaterialRegion")
    try:
        regions = list(regions)
    except TypeError:
        raise ValueError("regions must be a sequence of CavityMaterialRegion") from None
    out = []
    for r, region in enumerate(regions):
        if not isinstance(region, CavityMaterialRegion):
            raise ValueError(f"regions[{r}] must be a CavityMaterialRegion")
        out.append(_KernelRegion(tuple(zip(region.lower_corner_position, region.upper_corner_position)),
                                 to_kernel(region.relative_permittivity),
                                 to_kernel(region.relative_permeability)))
    return out


def solve_material_cavity_box(*, box_size, subdivision_count, regions=(), mode_count=6, target_frequency,
                              electrical_conductivity=None) -> MaterialCavityResult:
    """Solve a rectangular box filled with vacuum and box-shaped material regions.

    box_size, subdivision_count, mode_count and target_frequency follow
    ``solve_cavity_box``; the mesh is the same alternating Kuhn mesh.
    regions: sequence of ``CavityMaterialRegion``; later regions override earlier
        ones where they overlap, and uncovered space is vacuum. Each tetrahedron
        takes the material containing its centroid. Corners must be grid planes.
    electrical_conductivity: None (all walls PEC), one positive conductivity in S/m
        for every wall, or a dict over ``WALLS`` ('x0', 'x1', ..., 'z1') whose
        missing or None entries are PEC. Finite walls use the Leontovich impedance
        condition; each mode is then converged by fixed-point iteration in k0.

    Select modes nearest the real target in complex squared wave number,
    ``|k0^2 - (2*pi*f_target/c0)^2|``, then return them in ascending real
    frequency. Complex values follow exp(-i omega t) (the module docstring). Text for a
    quantity and JAX or PyTorch values raise TypeError, other invalid inputs ValueError;
    nonconvergence, insufficient modes or failed quality checks raise RuntimeError
    without a partial result.
    See docs/packages/galerkin/material_cavity.md for the conventions and validation.
    """
    for name, value in (("box_size", box_size), ("mode_count", mode_count),
                        ("target_frequency", target_frequency),
                        ("electrical_conductivity", electrical_conductivity)):
        refuse_text(name, value)
    return _public_result(_solve_material_cavity_box(
        box_size, subdivision_count, regions=_kernel_regions(regions), num_modes=mode_count,
        target_frequency_hz=target_frequency, wall_conductivity_s_per_m=electrical_conductivity))


def _solve_material_cavity_box(lengths_m, subdivisions, *, regions=(), num_modes=6, target_frequency_hz,
                               wall_conductivity_s_per_m=None) -> _MaterialCavityKernelResult:
    """The body of ``solve_material_cavity_box`` (the solver's own order and names; ``regions`` of
    ``_KernelRegion`` under exp(+j omega t))."""
    refuse_live(subdivisions, "subdivision_count")
    refuse_live(num_modes, "mode_count")
    lengths = np.asarray(triple(lengths_m, "box_size", positive_real))
    cells = triple(subdivisions, "subdivision_count", positive_integer)
    count = positive_integer(num_modes, "mode_count")
    target = positive_real(target_frequency_hz, "target_frequency")
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

    mesh = cavity_mesh(normalized_lengths, cells)
    centroid_grid = (mesh.nodes[mesh.tets].mean(axis=1) / normalized_lengths * np.asarray(cells))
    eps = np.ones(mesh.num_tets, dtype=complex)
    mu = np.ones(mesh.num_tets, dtype=complex)
    for planes, eps_value, mu_value in materials:
        inside = np.all((centroid_grid > planes[:, 0]) & (centroid_grid < planes[:, 1]), axis=1)
        eps[inside], mu[inside] = eps_value, mu_value

    space = EdgeSpace3D(mesh)
    walls = _wall_faces(mesh, normalized_lengths)
    pec_faces = [walls[w] for w in WALLS if conductivity[w] is None]
    pec = (_face_edge_ids(space, np.concatenate(pec_faces)) if pec_faces
           else np.array([], dtype=int))
    # Gradients of interior nodal potentials are the kernel with any wall mix:
    # their tangential traces vanish on every wall.
    interior = np.setdiff1d(np.arange(mesh.num_nodes), mesh.boundary_nodes())
    interior_count = int(np.prod(np.asarray(cells, dtype=object) - 1))
    mesh_si = Mesh3D(mesh.nodes * length_scale, mesh.tets.copy(), mesh.boundary, mesh.regions,
                     mesh.region_names, tagged_faces=mesh.tagged_faces)
    return _solve_material_cavity_numpy(
        space, eps, mu, pec, walls, conductivity, lossy_walls, interior, [], interior_count,
        count, target, sigma, fundamental, length_scale, eigenvalue_scale, field_scale, mesh_si)


def _region_materials(mesh, regions):
    """Per-tetrahedron complex (eps, mu) from {region name: (eps_r, mu_r) or eps_r} (exp(+j omega t))."""
    if mesh.regions is None or mesh.region_names is None:
        raise ValueError("solve_material_cavity needs mesh.regions and mesh.region_names")
    if not isinstance(regions, dict):
        raise ValueError("relative_permittivity must map every mesh region name to a value")
    names = list(mesh.region_names)
    unknown = [k for k in regions if k not in names]
    missing = [n for n in names if n not in regions]
    if unknown or missing:
        raise ValueError(f"relative_permittivity must name the regions of mesh.region_names exactly; "
                         f"missing {missing}, unknown {unknown}")
    eps_table, mu_table = [], []
    for name in names:
        value = regions[name]
        refuse_live_mesh_inputs("solve_material_cavity", value)
        if isinstance(value, (tuple, list)):
            if len(value) != 2:
                raise ValueError(f"regions[{name!r}] must be (eps_r, mu_r) or a single eps_r")
            eps_value, mu_value = value
        else:
            eps_value, mu_value = value, 1.0
        eps_table.append(_material(eps_value, f"relative_permittivity[{name!r}]"))
        mu_table.append(_material(mu_value, f"relative_permeability[{name!r}]"))
    ids = mesh.regions
    return np.asarray(eps_table)[ids], np.asarray(mu_table)[ids]


def _wall_table(mesh, walls):
    """{tag: conductivity or None} over every tagged face, PEC where not listed."""
    tags = list(mesh.tagged_faces)
    if walls is None:
        return dict.fromkeys(tags)
    if not isinstance(walls, dict):
        raise ValueError("electrical_conductivity must map face tags to a conductivity in S/m or None for PEC")
    unknown = sorted(set(walls) - set(tags), key=str)
    if unknown:
        raise ValueError(f"electrical_conductivity: unknown face tag(s) {unknown}; this mesh carries "
                         f"{sorted(tags)}")
    return {tag: (None if walls.get(tag) is None
                  else positive_real(walls[tag], f"electrical_conductivity[{tag!r}]")) for tag in tags}


def solve_material_cavity(mesh, *, relative_permittivity, relative_permeability=None,
                          electrical_conductivity=None, mode_count=6, target_frequency) -> MaterialCavityResult:
    """Solve a cavity on an external mesh with materials per region and walls per face tag.

    mesh: ``galerkin.Mesh3D`` in metres with regions and tagged outward faces
        (docs/packages/galerkin/mesh3d_format.md); checked on entry.
    relative_permittivity: ``{region name: eps_r}`` for every ``mesh.region_names`` entry;
        relative_permeability: None (mu_r = 1 everywhere) or ``{region name: mu_r}``, the
        regions left out nonmagnetic. Complex under exp(-i omega t), passive (Re > 0, Im >= 0).
    electrical_conductivity: None (every tagged face PEC) or ``{face tag: S/m or None}``;
        tags not listed are PEC, listed finite conductivities take the Leontovich
        impedance condition of the box solver.
    mode_count, target_frequency: as in ``solve_material_cavity_box``.

    Every tagged face is a wall (PEC or impedance), so the gradient kernel is
    spanned by the potentials constant on each boundary component; its dimension
    is counted from the mesh and verified on the dense path. NumPy only: JAX or
    PyTorch values raise TypeError. The returned mesh is the one given.
    """
    for name, value in (("relative_permittivity", relative_permittivity),
                        ("relative_permeability", relative_permeability),
                        ("electrical_conductivity", electrical_conductivity), ("mode_count", mode_count),
                        ("target_frequency", target_frequency)):
        refuse_text(name, value)
    if not isinstance(relative_permittivity, Mapping):
        raise ValueError("relative_permittivity must map every mesh region name to a value")
    permeability = {} if relative_permeability is None else relative_permeability
    if not isinstance(permeability, Mapping):
        raise ValueError("relative_permeability must be None or map mesh region names to values")
    unknown = [name for name in permeability if name not in relative_permittivity]
    if unknown:
        raise ValueError(f"relative_permeability: unknown region(s) {unknown}; relative_permittivity names "
                         f"{list(relative_permittivity)}")
    refuse_live_mesh_inputs("solve_material_cavity", *relative_permittivity.values(), *permeability.values())
    regions = {name: (to_kernel(_public_material(eps, f"relative_permittivity[{name!r}]")),
                      to_kernel(_public_material(permeability.get(name, 1.0), f"relative_permeability[{name!r}]")))
               for name, eps in relative_permittivity.items()}
    walls = dict(electrical_conductivity) if isinstance(electrical_conductivity, Mapping) else electrical_conductivity
    return _public_result(_solve_material_cavity(mesh, regions=regions, walls=walls, num_modes=mode_count,
                                                 target_frequency_hz=target_frequency))


def _solve_material_cavity(mesh, *, regions, walls=None, num_modes=6,
                           target_frequency_hz) -> _MaterialCavityKernelResult:
    """The body of ``solve_material_cavity``: ``regions`` {name: (eps_r, mu_r) or eps_r} and ``walls``
    {face tag: S/m or None} under the solver's own names and exp(+j omega t)."""
    refuse_live_mesh_inputs("solve_material_cavity", target_frequency_hz, num_modes)
    scaled, length_scale, lengths = normalized_mesh(mesh, "solve_material_cavity")
    count, target, sigma, fundamental, eigenvalue_scale, field_scale = search_parameters(
        lengths, length_scale, target_frequency_hz, num_modes)
    eps, mu = _region_materials(scaled, regions)
    conductivity = _wall_table(scaled, walls)
    tags = list(scaled.tagged_faces)
    lossy_walls = [tag for tag in tags if conductivity[tag] is not None]
    space = EdgeSpace3D(scaled)
    faces = dict(scaled.tagged_faces)
    pec_faces = [faces[t] for t in tags if conductivity[t] is None]
    pec = (face_edge_ids(space, np.concatenate(pec_faces)) if pec_faces
           else np.array([], dtype=int))
    unit_nodes, components, kernel_count = gradient_potentials(scaled, scaled.faces_tagged(*tags))
    return _solve_material_cavity_numpy(
        space, eps, mu, pec, faces, conductivity, lossy_walls, unit_nodes, components, kernel_count,
        count, target, sigma, fundamental, length_scale, eigenvalue_scale, field_scale, mesh)


def _solve_material_cavity_numpy(space, eps, mu, pec, walls, conductivity, lossy_walls, unit_nodes,
                                 components, interior_count, count, target, sigma, fundamental,
                                 length_scale, eigenvalue_scale, field_scale, mesh_si):
    """Assembly, search and checks on a normalized mesh; shared by both entry points."""
    lossless = bool(np.all(eps.imag == 0) and np.all(mu.imag == 0) and not lossy_walls)
    free = np.setdiff1d(np.arange(space.num_edges), pec)
    physical_count = len(free) - interior_count
    if count > physical_count:
        raise RuntimeError(f"requested {count} modes but this mesh has only "
                           f"{physical_count} physical degrees of freedom; refine subdivisions")
    stiffness, mass = _material_matrices(space, free, eps, mu)
    vacuum_mass = _assemble_edge_mass_3d(space)[free][:, free].tocsc()
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
        gradient = gradient_incidence(space, free, unit_nodes, components)
        # Complex-symmetric projector P = I - C (C^T M C)^-1 C^T M (no conjugation).
        mass_gradient = (mass @ gradient).tocsc()
        gradient_lu = (spla.splu((gradient.T @ mass_gradient).tocsc(), permc_spec=_ORDERING)
                       if gradient.shape[1] else None)
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
    electric = np.stack([_eval_edge_field_3d(space, coefficients[:, j]) for j in range(count)])
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
    return _MaterialCavityKernelResult(mesh_si, EdgeSpace3D(mesh_si), frequencies, frequencies.real.copy(),
                                       quality, eigenvalues, coefficients, electric, residuals, pec,
                                       eps, mu, count, target, lossless, dict(conductivity), iterations,
                                       gradient_kernel_dimension=int(interior_count))
