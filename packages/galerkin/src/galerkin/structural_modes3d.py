# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Undamped natural frequencies and mass-normalized modes of a supported 3D solid."""
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from scipy import linalg, sparse
from scipy.sparse.linalg import eigsh

from . import _elasticity3d
from ._public import ResultSurface, refuse_text
from ._tetra_materials import region_property
from .core.checks import positive_integer
from .core.eigen import arpack_rng

__all__ = ["StructuralModes3DResult", "solve_structural_modes_3d"]


@dataclass(frozen=True, eq=False)
class StructuralModes3DResult(ResultSurface):
    """Ascending frequencies, nodal Cartesian modes (mode, node, xyz) and free-DOF residuals."""

    frequency: np.ndarray
    mass_normalized_displacement: np.ndarray
    relative_residual: np.ndarray

    BASIS = "3d"
    UNITS = MappingProxyType({"frequency": "Hz", "mass_normalized_displacement": "1/kg^(1/2)",
                              "relative_residual": "1"})


def _solve_block(stiffness, mass, count):
    size = stiffness.shape[0]
    # Use a direct symmetric solver for tiny pencils or a requested full spectrum.
    if size <= 96 or count == size:
        values, vectors = linalg.eigh(stiffness.toarray(), mass.toarray(),
                                      subset_by_index=(0, count - 1))
    else:
        values, vectors = eigsh(stiffness, k=count, M=mass, sigma=0.0, which="LM",
                                v0=np.random.default_rng(0).standard_normal(size),
                                **arpack_rng("eigsh"))
    order = np.argsort(values)
    values, vectors = values[order], vectors[:, order]
    return values, vectors


def _lowest_modes(stiffness, mass, count):
    # Separate uncoupled blocks before using Lanczos: a single starting vector
    # can miss copies of an exactly repeated eigenvalue on identical solids.
    graph = stiffness.astype(bool) + mass.astype(bool)
    blocks, labels = sparse.csgraph.connected_components(graph, directed=False)
    if blocks == 1:
        return _solve_block(stiffness, mass, count)
    ordering = np.argsort(labels, kind="stable")
    groups = np.split(ordering, np.flatnonzero(np.diff(labels[ordering])) + 1)
    solutions = []
    candidates = []
    for block, dofs in enumerate(groups):
        values, vectors = _solve_block(stiffness[dofs][:, dofs], mass[dofs][:, dofs],
                                       min(count, len(dofs)))
        solutions.append(vectors)
        candidates.extend((value, block, mode) for mode, value in enumerate(values))
    lowest = sorted(candidates)[:count]
    vectors = np.zeros((len(labels), count))
    for column, (_, block, mode) in enumerate(lowest):
        vectors[groups[block], column] = solutions[block][:, mode]
    return np.array([value for value, _, _ in lowest]), vectors


def solve_structural_modes_3d(mesh, *, youngs_modulus, poisson_ratio, mass_density,
                              prescribed_displacement, mode_count=1):
    """Solve K u = (2 pi f)^2 M u on the free DOFs of a tetrahedral Mesh3D in metres.

    E (Pa), Poisson ratio and density (kg/m^3) are scalars or region mappings.
    Use zero prescribed displacements to remove the six rigid motions of each
    component. Modes have unit generalized mass. Their sign and the basis of a
    repeated frequency have no physical significance.
    """
    for name, value in (("youngs_modulus", youngs_modulus), ("poisson_ratio", poisson_ratio),
                        ("mass_density", mass_density), ("prescribed_displacement", prescribed_displacement),
                        ("mode_count", mode_count)):
        refuse_text(name, value)
    count = positive_integer(mode_count, "mode_count")
    gradients, volumes = _elasticity3d.element_geometry(mesh)
    _, _, shear, lame = _elasticity3d.elastic_moduli(mesh, youngs_modulus, poisson_ratio)
    density = region_property(mesh, mass_density, "mass_density", positive=True)
    _, free = _elasticity3d.supported_dofs(mesh, prescribed_displacement)
    if count > free.size:
        raise ValueError(f"mode_count must not exceed the number of free displacement components ({free.size})")
    stiffness = _elasticity3d.stiffness_matrix(mesh, gradients, volumes, shear, lame)[free][:, free]
    mass = _elasticity3d.mass_matrix(mesh, density)[free][:, free]

    values, vectors = _lowest_modes(stiffness, mass, count)
    if not np.all(np.isfinite(values) & (values > 0)):
        raise ValueError("expected finite positive eigenvalues for a supported solid")

    # Both symmetric eigensolvers return M-orthonormal columns. Check equilibrium
    # only on free DOFs since constrained rows include the support reactions.
    elastic = stiffness @ vectors
    inertial = (mass @ vectors) * values
    residual = np.linalg.norm(elastic - inertial, axis=0) / (
        np.linalg.norm(elastic, axis=0) + np.linalg.norm(inertial, axis=0))
    if not np.all(np.isfinite(residual) & (residual <= 1e-6)):
        raise ValueError("structural eigenpair residual exceeds 1e-6; check supports and mesh conditioning")
    shapes = np.zeros((count, 3 * mesh.num_nodes))
    shapes[:, free] = vectors.T
    return StructuralModes3DResult(np.sqrt(values) / (2 * np.pi),
                                   shapes.reshape(count, mesh.num_nodes, 3), residual)
