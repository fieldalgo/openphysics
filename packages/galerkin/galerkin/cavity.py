# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Vacuum rectangular PEC cavity modes, with explicit SI output contracts."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.linalg as la
import scipy.sparse.linalg as spla

from .mesh3d import Mesh3D, box_mesh
from .edge3d import (EdgeSpace3D, assemble_curlcurl_3d,
                     assemble_edge_mass_3d, eval_edge_field_3d)


_C0 = 299792458.0  # Exact vacuum speed of light, m/s.
_RESIDUAL_TOL = 1e-8
_ORTHOGONALITY_TOL = 1e-7


@dataclass
class CavityResult:
    """Near-target cavity eigenpairs; see ``docs/cavity3d.md`` for units.

    Columns of ``edge_coefficients`` are full-edge vectors including PEC zeros.
    ``electric_field`` has shape (modes, tetrahedra, 3), at element centroids.
    Mass normalization is mathematical: these fields are not calibrated V/m.
    """

    mesh: Mesh3D
    space: EdgeSpace3D
    frequencies_hz: np.ndarray
    eigenvalues_m2: np.ndarray
    edge_coefficients: np.ndarray
    electric_field: np.ndarray
    relative_residuals: np.ndarray
    pec_edge_ids: np.ndarray
    target_frequency_hz: float
    requested_modes: int
    search: str = "near_target"


def solve_cavity_box(lengths_m, subdivisions, *, num_modes=6,
                     target_frequency_hz) -> CavityResult:
    """Solve a vacuum box with PEC on all six faces, using tetrahedral edges.

    ``lengths_m`` contains three positive side lengths in metres;
    ``subdivisions`` contains three positive integer cell counts. The origin is
    (0, 0, 0). ``target_frequency_hz`` is required, finite and positive.

    Select ``num_modes`` positive eigenpairs nearest the target in *squared*
    frequency, then return them in ascending frequency order. This is a bounded
    near-target search, not a claim of the complete lowest spectrum. Repeated
    eigenvalues retain independent eigenvectors; a count may cut a cluster.

    Invalid inputs raise ValueError. Insufficient physical candidates,
    nonconvergence or failed eigenpair checks raise RuntimeError, without
    returning partial results. No material or open-boundary options are offered.
    """
    try:
        lengths = np.asarray(lengths_m, dtype=float)
        counts = np.asarray(subdivisions)
    except (TypeError, ValueError) as exc:
        raise ValueError("lengths_m and subdivisions must be numeric triples") from exc
    if (lengths.shape != (3,) or not np.all(np.isfinite(lengths))
            or np.any(lengths <= 0)):
        raise ValueError("lengths_m must contain three finite positive metres values")
    if (counts.shape != (3,) or counts.dtype.kind not in "iu"
            or np.any(counts <= 0)):
        raise ValueError("subdivisions must contain three positive integers")
    if (isinstance(num_modes, (bool, np.bool_))
            or not isinstance(num_modes, (int, np.integer)) or num_modes < 1):
        raise ValueError("num_modes must be a positive integer")
    if (isinstance(target_frequency_hz, (bool, np.bool_))
            or not np.isscalar(target_frequency_hz)
            or not np.isrealobj(target_frequency_hz)):
        raise ValueError("target_frequency_hz must be finite and positive")
    try:
        target = float(target_frequency_hz)
    except (TypeError, ValueError) as exc:
        raise ValueError("target_frequency_hz must be finite and positive") from exc
    if not np.isfinite(target) or target <= 0:
        raise ValueError("target_frequency_hz must be finite and positive")

    # Uniform nondimensionalization keeps numerical checks independent of the
    # physical length scale. Only this private assembly mesh is dimensionless.
    scale = float(lengths.max())
    with np.errstate(over="ignore", under="ignore", invalid="ignore", divide="ignore"):
        sides = lengths / scale
        sigma = np.square((2 * np.pi / _C0) * target * scale)
        inverse_squares = np.sort(1 / sides**2)
        fundamental = np.pi**2 * inverse_squares[:2].sum()
    if (not np.isfinite(sigma) or sigma <= 0
            or not np.isfinite(fundamental) or not np.all(sides > 0)):
        raise ValueError("box scale or target is outside the supported numeric range")
    mesh = box_mesh(*sides, *counts)
    space = EdgeSpace3D(mesh)
    pec = space.boundary_edge_ids()
    free = np.setdiff1d(np.arange(space.num_edges), pec)
    interior_nodes = int(np.prod(counts - 1))
    if num_modes > len(free) - interior_nodes:
        raise RuntimeError("insufficient physical cavity modes on this mesh; refine subdivisions")
    stiffness = assemble_curlcurl_3d(space)[free][:, free].tocsc()
    mass = assemble_edge_mass_3d(space)[free][:, free].tocsc()
    try:
        if len(free) <= 128:
            values, vectors = la.eigh(stiffness.toarray(), mass.toarray())
        else:
            candidates = min(len(free) - 1, max(2 * num_modes + 8, 20))
            values, vectors = spla.eigsh(
                stiffness, k=candidates, M=mass, sigma=sigma, which="LM",
                v0=np.random.default_rng(0).standard_normal(len(free)),
                ncv=min(len(free), max(6 * candidates, 90)),
                tol=1e-11, maxiter=50000)
    except (spla.ArpackError, RuntimeError, la.LinAlgError) as exc:
        raise RuntimeError("cavity eigensolve failed; adjust target or mesh") from exc

    # The exact box fundamental is a scale for rejecting the discrete gradient
    # kernel only, never a source of returned eigenvalues or multiplicities.
    physical = np.flatnonzero(np.isfinite(values) & (values > 1e-8 * fundamental))
    if len(physical) < num_modes:
        raise RuntimeError(
            f"insufficient physical cavity candidates: found {len(physical)}, "
            f"requested {num_modes}; adjust target_frequency_hz or request fewer modes")
    nearest = physical[np.argsort(abs(values[physical] - sigma), kind="stable")[:num_modes]]
    selected = nearest[np.argsort(values[nearest], kind="stable")]
    values, vectors = values[selected], vectors[:, selected]
    vectors /= np.sqrt(np.einsum("ij,ij->j", vectors, mass @ vectors))[None, :]
    # A reproducible sign convention, not an identity for a degenerate mode.
    pivots = np.argmax(abs(vectors), axis=0)
    vectors *= np.sign(vectors[pivots, np.arange(num_modes)])[None, :]
    aq, mq = stiffness @ vectors, mass @ vectors
    residuals = np.linalg.norm(aq - mq * values[None, :], axis=0) / (
        np.linalg.norm(aq, axis=0) + abs(values) * np.linalg.norm(mq, axis=0))
    orthogonality = np.max(abs(vectors.T @ mq - np.eye(num_modes)))
    if (not np.all(np.isfinite(residuals)) or np.max(residuals) > _RESIDUAL_TOL
            or not np.isfinite(orthogonality) or orthogonality > _ORTHOGONALITY_TOL):
        raise RuntimeError("cavity eigenpairs failed residual or mass-orthogonality checks")

    si_mesh = Mesh3D(mesh.nodes * scale, mesh.tets.copy(), mesh.boundary,
                     mesh.regions, mesh.region_names)
    si_space = EdgeSpace3D(si_mesh)
    coefficients = np.zeros((space.num_edges, num_modes))
    coefficients[free] = vectors / np.sqrt(scale)
    fields = np.stack([eval_edge_field_3d(si_space, q) for q in coefficients.T])
    with np.errstate(over="ignore", under="ignore", invalid="ignore", divide="ignore"):
        eigenvalues = values / scale / scale
        frequencies = (_C0 / (2 * np.pi)) * np.sqrt(values) / scale
    if (not np.all(np.isfinite(eigenvalues)) or not np.all(eigenvalues > 0)
            or not np.all(np.isfinite(frequencies)) or not np.all(np.isfinite(fields))):
        raise RuntimeError("cavity result is outside the supported numeric range")
    return CavityResult(si_mesh, si_space, frequencies, eigenvalues,
                         coefficients, fields, residuals, pec, target, int(num_modes))
