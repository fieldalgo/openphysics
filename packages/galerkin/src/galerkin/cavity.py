# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Vacuum PEC resonances near a specified frequency: galerkin's public cavity API, in SI.

``solve_cavity_box`` builds its own alternating Kuhn box; ``solve_cavity`` takes
any tetrahedral mesh of the format in docs/packages/galerkin/mesh3d_format.md
and applies PEC on the tagged faces named (all of them by default). Both share
the assembly, the gradient-kernel projection and the search below.

Units and convention
--------------------
Quantities are keyword-only registry names in SI units: ``box_size`` (the three
side lengths in m; the box starts at the origin), ``mode_count`` (the exact number
of modes returned), ``target_frequency`` (Hz); the mesh of ``solve_cavity`` is in
metres. The vacuum PEC cavity is lossless: every result is real and carries no
time convention, so nothing is converted between conventions here. The returned
``CavityResult`` is frozen and names its fields by the registry
(``resonant_frequency``, ``wavenumber_squared``, ...), with ``.units``.

The public functions are thin: they refuse text (``TypeError``) and call the
private bodies ``_solve_cavity_box`` and ``_solve_cavity``, which keep the solver's
code and positional order (the box lengths, the subdivisions, ``num_modes`` and
``target_frequency_hz``) and return the private record ``_CavityKernelResult``. There
is no kernel export of the cavity solvers (spec 4.3); refusals name the public
quantities.

Derivatives
-----------
box_size may hold JAX or PyTorch values: frequencies, eigenvalues, edge
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
from types import MappingProxyType
from typing import Any, ClassVar

import numpy as np
import scipy.linalg as la
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .mesh3d import Mesh3D
from ._cavity_common import (C0, DENSE_LIMIT, GRADIENT_LIMIT, RESIDUAL_LIMIT, cavity_mesh,
                             face_edge_ids, face_tags, gradient_incidence, gradient_potentials,
                             normalized_mesh, refuse_live_mesh_inputs, search_parameters)
from .edge3d import (LOCAL_EDGES, EdgeSpace3D, assemble_curlcurl_3d as _assemble_curlcurl_3d,
                     assemble_edge_mass_3d as _assemble_edge_mass_3d, eval_edge_field_3d as _eval_edge_field_3d)
from .core.tets import tet_gradients as _tet_gradients
from .core import eigen, forms, kernels
from .core import live as live_inputs
from .core import solve as core_solve
from .core.backend import lift, live_namespace, scatter_add
from .core.checks import contains_live, positive_integer, positive_real, real_value, triple
from .core.eigen import DEGENERATE_GAP, DegenerateModeWarning, arpack_rng  # noqa: F401 (public here)
from .core.sparse import CooMatrix
from ._public import refuse_text

__all__ = ["CavityResult", "solve_cavity_box", "solve_cavity", "DegenerateModeWarning"]

_ORTHOGONALITY_LIMIT = 1e-7


@dataclass(frozen=True)
class CavityResult:
    """The modes of ``solve_cavity_box`` or ``solve_cavity``: individual real standing-wave
    eigenfields, not unique polarization labels; frozen.

    resonant_frequency: (K,) Hz, ascending; wavenumber_squared: (K,) k0^2 in 1/m^2.
    mass_normalized_electric_field_line_integral: (E, K), the full edge vectors (edge
        orientation low node id to high node id; PEC coefficients are zero); SI mass
        orthonormality Q^T M Q = I gives them the unit 1/m^(1/2).
    mass_normalized_electric_field: (K, T, 3), the field at the tetrahedron centroids,
        1/m^(3/2). This arbitrary normalization is not V/m or power.
    relative_residual: (K,), the free-edge equations' relative residuals.
    mesh, space: the solve's mesh in metres and its edge space; pec_edges: the edge ids
        constrained by PEC; pec_faces: the face tags that carry it.
    mode_count, target_frequency: as given; gradient_kernel_dimension: the dimension of
        the discrete gradient kernel the search projected out.

    A finite near-target selection may cut a degenerate cluster (``search``,
    ``cluster_completeness`` and ``mode_count_policy`` say so). Every value is real: the
    lossless vacuum cavity has no time convention. ``.units`` maps each quantity field to
    its SI unit.
    """

    mesh: Mesh3D
    space: EdgeSpace3D
    resonant_frequency: Any                      # (K,)
    wavenumber_squared: Any                      # (K,)
    mass_normalized_electric_field_line_integral: Any   # (E, K), full edge vectors
    mass_normalized_electric_field: Any          # (K, T, 3), tetrahedron centroids
    relative_residual: Any                       # (K,), free-edge equations
    pec_edges: np.ndarray
    mode_count: int
    target_frequency: float
    pec_faces: tuple = ()
    gradient_kernel_dimension: int = 0

    search: ClassVar[str] = "near_target"
    cluster_completeness: ClassVar[str] = "not_certified"
    mode_count_policy: ClassVar[str] = "exact_count_may_split_cluster"
    UNITS: ClassVar = MappingProxyType({
        "resonant_frequency": "Hz", "wavenumber_squared": "1/m^2",
        "mass_normalized_electric_field_line_integral": "1/m^(1/2)",
        "mass_normalized_electric_field": "1/m^(3/2)", "relative_residual": "1", "mode_count": "1",
        "target_frequency": "Hz"})

    @property
    def units(self):
        """{field: canonical SI unit} of every quantity field (read-only)."""
        return self.UNITS


@dataclass
class _CavityKernelResult:
    """The private bodies' record: the solver's own field names (the former ``CavityResult``).

    Coordinates are metres; eigenvalues_m2 are squared wave numbers in m^-2.
    SI mass orthonormality gives edge_coefficients units m^-1/2 and
    electric_field units m^-3/2. Every value is real.
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
    pec_face_tags: tuple = ()
    gradient_kernel_dimension: int = 0


def _public_result(result: _CavityKernelResult) -> CavityResult:
    """The public, frozen result of a private body's record: the same arrays under registry names.

    Every value is real (a lossless vacuum cavity), so nothing changes convention.
    """
    return CavityResult(mesh=result.mesh, space=result.space, resonant_frequency=result.frequencies_hz,
                        wavenumber_squared=result.eigenvalues_m2,
                        mass_normalized_electric_field_line_integral=result.edge_coefficients,
                        mass_normalized_electric_field=result.electric_field,
                        relative_residual=result.relative_residuals, pec_edges=result.pec_edge_ids,
                        mode_count=result.requested_modes, target_frequency=result.target_frequency_hz,
                        pec_faces=result.pec_face_tags,
                        gradient_kernel_dimension=result.gradient_kernel_dimension)


def _gradient_space(space, free, mass, unit_nodes, components):
    """Nodal gradients in the PEC-constrained edge space (``_cavity_common`` docstring).

    C maps the potential basis (unit potentials on unconstrained nodes plus the
    indicators of the further PEC components) to edge circulations. On the PEC
    box that is one dimension per interior node. C^T M C is positive definite,
    even though curl-curl is singular.
    """
    incidence = gradient_incidence(space, free, unit_nodes, components)
    mass_gradient = mass @ incidence
    factor = spla.splu((incidence.T @ mass_gradient).tocsc()) if incidence.shape[1] else None
    return incidence, mass_gradient, factor


def solve_cavity_box(*, box_size, subdivision_count, mode_count=6, target_frequency) -> CavityResult:
    """Solve a vacuum rectangular box with PEC on all six walls.

    box_size: the three finite positive side lengths in m; the box starts at the
        origin. It may hold JAX or PyTorch values (see the module docstring); the
        target only selects modes and carries no derivative.
    subdivision_count: three positive integers; each cell becomes six tetrahedra,
        with Kuhn diagonals reflected according to the cell's coordinate parity.
    mode_count: number of individual eigenpairs returned, including multiplicities.
    target_frequency: required finite positive search target in Hz.

    Select modes nearest the target in squared frequency, then return them in
    ascending frequency order. This is a finite candidate search, not a complete
    lowest spectrum, interval enumeration, or complete-degeneracy guarantee.

    SI edge mass normalization is Q.T @ M_SI @ Q = I; each real mode's largest
    absolute edge coefficient is positive. Degenerate bases remain nonunique.
    Text for a quantity raises TypeError, other invalid inputs ValueError.
    Insufficient physical modes, nonconvergence, factorization failures, or
    failed residual/orthogonality checks raise RuntimeError without a partial
    result. See docs/packages/galerkin/cavity_solver.md for the fixed search and
    validation policy.
    """
    for name, value in (("box_size", box_size), ("mode_count", mode_count),
                        ("target_frequency", target_frequency)):
        refuse_text(name, value)
    return _public_result(_solve_cavity_box(box_size, subdivision_count, num_modes=mode_count,
                                            target_frequency_hz=target_frequency))


def _solve_cavity_box(lengths_m, subdivisions, *, num_modes=6, target_frequency_hz) -> _CavityKernelResult:
    """The body of ``solve_cavity_box`` (its arguments in the solver's own order and names)."""
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
    lengths = xp.reshape(real_value(lengths_m, "box_size"), (3,))
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
    g, _ = _tet_gradients(space.mesh)
    local = np.asarray(LOCAL_EDGES)
    basis = lift(xp, 0.25 * (g[:, local[:, 1], :] - g[:, local[:, 0], :]))   # (T, 6, 3) at centroids
    signs = lift(xp, space.signs)
    electric = xp.stack([xp.einsum("te,ted->td", signs * coefficients[:, k][space.tet_edges], basis)
                         for k in range(count)]) / scale
    return _CavityKernelResult(result.mesh, space, (C0 / (2 * np.pi)) * xp.sqrt(eigenvalues), eigenvalues,
                               coefficients, electric, lift(xp, result.relative_residuals),
                               result.pec_edge_ids, count, result.target_frequency_hz)


def _solve_cavity_box_numpy(lengths_m, subdivisions, *, num_modes, target_frequency_hz):
    """The NumPy solve of ``solve_cavity_box`` (NumPy inputs only; refusals name the public quantities)."""
    lengths = np.asarray(triple(lengths_m, "box_size", positive_real))
    cells = triple(subdivisions, "subdivision_count", positive_integer)
    count = positive_integer(num_modes, "mode_count")
    target = positive_real(target_frequency_hz, "target_frequency")
    length_scale = float(lengths.max())
    with np.errstate(over="ignore", under="ignore", divide="ignore", invalid="ignore"):
        normalized_lengths = lengths / length_scale
        target_k = (2 * np.pi / C0) * target * length_scale
        sigma = target_k * target_k
        fundamental = np.pi**2 * np.sort(1 / normalized_lengths**2)[:2].sum()
        eigenvalue_scale = 1 / np.float64(length_scale)**2
        field_scale = np.float64(length_scale)**-1.5
        reciprocal_lengths = 1 / normalized_lengths
    if (not np.isfinite([sigma, fundamental, eigenvalue_scale, field_scale]).all()
            or min(sigma, eigenvalue_scale, field_scale) <= 0
            or not np.isfinite(reciprocal_lengths).all()):
        raise ValueError("box lengths and target exceed the supported floating-point range")

    mesh = cavity_mesh(normalized_lengths, cells)
    space = EdgeSpace3D(mesh)
    pec = space.boundary_edge_ids()
    interior = np.setdiff1d(np.arange(mesh.num_nodes), mesh.boundary_nodes())
    interior_count = int(np.prod(np.asarray(cells, dtype=object) - 1))
    mesh_si = Mesh3D(mesh.nodes * length_scale, mesh.tets.copy(), mesh.boundary, mesh.regions,
                     mesh.region_names, tagged_faces=mesh.tagged_faces)
    return _solve_cavity_numpy(space, pec, interior, [], interior_count, count, target, sigma,
                               fundamental, length_scale, eigenvalue_scale, field_scale, mesh_si,
                               tuple(mesh.tagged_faces))


def solve_cavity(mesh, *, pec_faces=None, mode_count=6, target_frequency) -> CavityResult:
    """Solve a vacuum cavity on an external tetrahedral mesh with PEC on tagged faces.

    mesh: a ``galerkin.Mesh3D`` with tagged outward faces (``from_mesher`` of a
        meshine or gmshio mesh, or ``box_mesh``), coordinates in metres; it is
        checked against docs/packages/galerkin/mesh3d_format.md.
    pec_faces: face tag names that carry the perfect conductor; None means every
        tagged face. Faces left out are natural (perfect magnetic conductor).
    mode_count, target_frequency: as in ``solve_cavity_box``.

    The mesh is scaled by its longest bounding-box edge, assembled, searched and
    checked exactly as the box solver does, including the projection onto the
    complement of the discrete gradient kernel, whose dimension is counted from
    the PEC surface (``_cavity_common``) and verified by the dense path. The
    kernel cutoff is relative to the lowest resonance of the bounding box.
    NumPy only: JAX or PyTorch values raise TypeError; derivatives with respect
    to the geometry exist only on ``solve_cavity_box``. The returned mesh is the
    one given.
    """
    for name, value in (("mode_count", mode_count), ("target_frequency", target_frequency)):
        refuse_text(name, value)
    return _public_result(_solve_cavity(mesh, pec_faces=pec_faces, num_modes=mode_count,
                                        target_frequency_hz=target_frequency))


def _solve_cavity(mesh, *, pec_faces=None, num_modes=6, target_frequency_hz) -> _CavityKernelResult:
    """The body of ``solve_cavity`` (its arguments under the solver's own names)."""
    refuse_live_mesh_inputs("solve_cavity", target_frequency_hz, num_modes)
    scaled, length_scale, lengths = normalized_mesh(mesh, "solve_cavity")
    tags = tuple(scaled.tagged_faces) if pec_faces is None else face_tags(scaled, pec_faces, "pec_faces")
    count, target, sigma, fundamental, eigenvalue_scale, field_scale = search_parameters(
        lengths, length_scale, target_frequency_hz, num_modes)
    space = EdgeSpace3D(scaled)
    faces = scaled.faces_tagged(*tags)
    pec = face_edge_ids(space, faces)
    unit_nodes, components, kernel_count = gradient_potentials(scaled, faces)
    return _solve_cavity_numpy(space, pec, unit_nodes, components, kernel_count, count, target,
                               sigma, fundamental, length_scale, eigenvalue_scale, field_scale,
                               mesh, tags)


def _solve_cavity_numpy(space, pec, unit_nodes, components, interior_count, count, target, sigma,
                        fundamental, length_scale, eigenvalue_scale, field_scale, mesh_si, tags):
    """Assembly, search and checks on a normalized mesh; shared by both entry points."""
    free = np.setdiff1d(np.arange(space.num_edges), pec)
    physical_count = len(free) - interior_count
    if count > physical_count:
        raise RuntimeError(f"requested {count} modes but this PEC mesh has only "
                           f"{physical_count} physical degrees of freedom; refine subdivisions")
    stiffness = _assemble_curlcurl_3d(space)[free][:, free].tocsc()
    mass = _assemble_edge_mass_3d(space)[free][:, free].tocsc()
    kernel_cutoff = 1e-8 * fundamental  # independent of the requested target

    try:
        gradient, mass_gradient, gradient_lu = _gradient_space(space, free, mass, unit_nodes,
                                                               components)
        if len(free) <= DENSE_LIMIT:
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
                ncv=min(len(free), max(6 * candidates, 90)), tol=1e-10, maxiter=50000,
                **arpack_rng("eigsh"))
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
            if np.max(leakage_norm) > GRADIENT_LIMIT:
                raise RuntimeError(f"cavity gradient component exceeds {GRADIENT_LIMIT:g}")
        left, right = stiffness @ vectors, mass_vectors * values
        residuals = np.linalg.norm(left - right, axis=0) / (
            np.linalg.norm(left, axis=0) + np.linalg.norm(right, axis=0))
        if not np.isfinite(residuals).all() or np.max(residuals) > RESIDUAL_LIMIT:
            raise RuntimeError(f"cavity Maxwell relative residual exceeds {RESIDUAL_LIMIT:g}")
    except (RuntimeError, la.LinAlgError, ValueError) as exc:
        raise RuntimeError(f"PEC cavity solve failed near {target:g} Hz: {exc}") from exc

    coefficients = np.zeros((space.num_edges, count))
    coefficients[free] = vectors
    electric = np.stack([_eval_edge_field_3d(space, coefficients[:, j]) for j in range(count)])
    eigenvalues = values * eigenvalue_scale
    frequencies = (C0 / (2 * np.pi)) * np.sqrt(eigenvalues)
    coefficients /= np.sqrt(length_scale)
    electric *= field_scale
    if not all(np.isfinite(array).all() for array in (eigenvalues, frequencies, coefficients, electric)):
        raise RuntimeError("cavity SI output exceeds the supported floating-point range")
    return _CavityKernelResult(mesh_si, EdgeSpace3D(mesh_si), frequencies, eigenvalues,
                               coefficients, electric, residuals, pec, count, target,
                               pec_face_tags=tuple(tags), gradient_kernel_dimension=int(interior_count))
