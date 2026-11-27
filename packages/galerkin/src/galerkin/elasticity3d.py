# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Small-strain isotropic linear elasticity with P1 tetrahedra in SI units."""
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components

from ._public import ResultSurface, refuse_text
from .core.checks import finite_scalar, real_array
from .core.solve import scipy_solve_dirichlet
from .core.tets import tet_gradients as _tet_gradients
from .mesh3d import Mesh3D
from .thermal3d import _per_region

__all__ = ["Elasticity3DResult", "solve_elasticity_3d"]


@dataclass(frozen=True, eq=False)
class Elasticity3DResult(ResultSurface):
    """Nodal displacement (N, 3) and total element strain and stress (T, 3, 3).

    Force arrays are (N, 3) in N. Applied force includes body and surface loads.
    Residual force is internal minus applied force, and reaction force is its
    restriction to prescribed components, with zero at all other components.
    """

    displacement: np.ndarray
    strain: np.ndarray
    stress: np.ndarray
    applied_force: np.ndarray
    reaction_force: np.ndarray
    residual_force: np.ndarray

    BASIS = "3d"
    UNITS = MappingProxyType({"displacement": "m", "strain": "1", "stress": "Pa",
                              "applied_force": "N", "reaction_force": "N", "residual_force": "N"})


def solve_elasticity_3d(mesh, *, youngs_modulus, poisson_ratio, prescribed_displacement,
                        body_force_density=None, traction=None):
    """Solve static 3D elasticity on a Mesh3D in metres.

    Give E in Pa and Poisson ratio in (-1, 0.5), as scalars or mappings from
    region names. Prescribe displacement with {(node, component): metres},
    where the Cartesian components are indexed 0, 1, 2. Each disconnected
    component must have all six rigid modes constrained. Body force density
    is a constant Cartesian vector in N/m^3. Traction maps exterior face
    tags to constant Cartesian vectors in Pa. All quantities are SI numbers.
    """
    return _solve_elasticity_3d(
        mesh, youngs_modulus=youngs_modulus, poisson_ratio=poisson_ratio,
        prescribed_displacement=prescribed_displacement, body_force_density=body_force_density,
        traction=traction)


def _fixed_dofs(mesh, prescribed):
    if not isinstance(prescribed, Mapping):
        raise ValueError("prescribed_displacement must map (node, component) to metres")
    fixed = {}
    for key, value in prescribed.items():
        if not isinstance(key, tuple) or len(key) != 2 or any(
                isinstance(i, (bool, np.bool_)) or not isinstance(i, (int, np.integer)) for i in key):
            raise ValueError("prescribed_displacement keys must be integer (node, component) pairs")
        node, axis = map(int, key)
        if not 0 <= node < mesh.num_nodes or not 0 <= axis < 3:
            raise ValueError("prescribed_displacement node or component is out of range")
        fixed[3 * node + axis] = finite_scalar(value, "prescribed_displacement")
    return fixed


def _check_constraints(mesh, fixed):
    tets = mesh.tets
    graph = sparse.csr_matrix((np.ones(tets.size, dtype=bool),
                               (np.repeat(tets[:, 0], 4), tets.ravel())),
                              shape=(mesh.num_nodes, mesh.num_nodes))
    count, labels = connected_components(graph, directed=False)
    dofs = np.array(list(fixed), dtype=int)
    nodes, axes = np.divmod(dofs, 3)
    basis = np.eye(3)
    for label in range(count):
        selected = labels[nodes] == label
        component_nodes = nodes[selected]
        component_axes = axes[selected]
        if len(component_nodes) >= 6:
            points = mesh.nodes[component_nodes]
            relative = points - points[0]
            length = np.max(np.abs(relative))
            if length > 0:
                translation = basis[component_axes]
                rotation = np.cross(relative / length, translation)
                if np.linalg.matrix_rank(np.column_stack((translation, rotation))) == 6:
                    continue
        raise ValueError(f"component {label} has unconstrained rigid-body modes")


def _vector(value, label):
    vector = real_array(value, label)
    if vector.shape != (3,):
        raise ValueError(f"{label} must be a Cartesian vector of three components")
    return vector


def _applied_load(mesh, volumes, body_force_density, traction):
    force = np.zeros((mesh.num_nodes, 3))
    if body_force_density is not None:
        body = _vector(body_force_density, "body_force_density")
        np.add.at(force, mesh.tets, volumes[:, None, None] * body / 4)
    if traction is None:
        return force
    if not isinstance(traction, Mapping):
        raise ValueError("traction must map exterior face tags to Cartesian vectors")
    for tag, value in traction.items():
        if tag not in mesh.tagged_faces or not len(mesh.tagged_faces[tag]):
            raise ValueError(f"traction requires a nonempty exterior face tag, got {tag!r}")
        faces = mesh.tagged_faces[tag]
        points = mesh.nodes[faces]
        area = np.linalg.norm(np.cross(points[:, 1] - points[:, 0],
                                       points[:, 2] - points[:, 0]), axis=1) / 2
        np.add.at(force, faces, area[:, None, None] * _vector(value, "traction") / 3)
    return force


def _stiffness(mesh, gradients, volumes, shear, lame):
    """Assemble C acting on the symmetric gradients of the 12 local vector bases."""
    direct = np.einsum("tai,tbj->taibj", gradients, gradients)
    swapped = direct.transpose(0, 1, 4, 3, 2)
    dot = np.einsum("tai,tbi->tab", gradients, gradients)
    identity = np.eye(3)
    blocks = ((lame * volumes)[:, None, None, None, None] * direct
              + (shear * volumes)[:, None, None, None, None]
              * (swapped + dot[:, :, None, :, None] * identity[None, :, None, :]))
    indices = (3 * mesh.tets[:, :, None] + np.arange(3)).reshape(-1, 12)
    return sparse.coo_matrix((blocks.ravel(), (np.repeat(indices, 12, axis=1).ravel(),
                                                np.tile(indices, (1, 12)).ravel())),
                             shape=(3 * mesh.num_nodes, 3 * mesh.num_nodes)).tocsr()


def _solve_elasticity_3d(mesh, *, youngs_modulus, poisson_ratio, prescribed_displacement,
                         body_force_density=None, traction=None, thermal_strain=None):
    """Internal solve with an optional (T,) isotropic eigenstrain in mesh order."""
    for name, value in (("youngs_modulus", youngs_modulus), ("poisson_ratio", poisson_ratio),
                        ("prescribed_displacement", prescribed_displacement),
                        ("body_force_density", body_force_density), ("traction", traction),
                        ("thermal_strain", thermal_strain)):
        refuse_text(name, value)
    if not isinstance(mesh, Mesh3D):
        raise TypeError("solve_elasticity_3d takes a galerkin.Mesh3D")
    mesh.check()
    if not mesh.num_tets:
        raise ValueError("elasticity needs at least one tetrahedron")
    young = _per_region(mesh, youngs_modulus, "youngs_modulus", positive=True)
    poisson = _per_region(mesh, poisson_ratio, "poisson_ratio", positive=False)
    if np.any((poisson <= -1) | (poisson >= 0.5)):
        raise ValueError("poisson_ratio must lie strictly between -1 and 0.5")
    fixed = _fixed_dofs(mesh, prescribed_displacement)
    _check_constraints(mesh, fixed)
    try:
        gradients, volumes = _tet_gradients(mesh)
    except np.linalg.LinAlgError as exc:
        raise ValueError("elasticity needs nondegenerate tetrahedra") from exc
    if not np.all(np.isfinite(gradients)) or not np.all(np.isfinite(volumes) & (volumes > 0)):
        raise ValueError("elasticity needs finite tetrahedra with positive volumes")
    shear = young / (2 * (1 + poisson))
    lame = young * poisson / ((1 + poisson) * (1 - 2 * poisson))
    applied = _applied_load(mesh, volumes, body_force_density, traction)
    rhs = applied.copy()
    if thermal_strain is not None:
        thermal_strain = real_array(thermal_strain, "thermal_strain")
        if thermal_strain.shape != (mesh.num_tets,):
            raise ValueError("thermal_strain must have shape (T,) in tetrahedron order")
        pressure = young / (1 - 2 * poisson) * thermal_strain
        np.add.at(rhs, mesh.tets, (pressure * volumes)[:, None, None] * gradients)
    stiffness = _stiffness(mesh, gradients, volumes, shear, lame)
    displacement = scipy_solve_dirichlet(stiffness, rhs.ravel(), fixed, factor=True).reshape(-1, 3)
    gradient = np.einsum("tai,taj->tij", displacement[mesh.tets], gradients)
    strain = (gradient + gradient.transpose(0, 2, 1)) / 2
    elastic_strain = strain
    if thermal_strain is not None:
        elastic_strain = strain - thermal_strain[:, None, None] * np.eye(3)
    stress = (2 * shear[:, None, None] * elastic_strain
              + (lame * np.trace(elastic_strain, axis1=1, axis2=2))[:, None, None] * np.eye(3))
    residual = (stiffness @ displacement.ravel() - rhs.ravel()).reshape(-1, 3)
    if not all(np.all(np.isfinite(value)) for value in (displacement, strain, stress, residual)):
        raise ValueError("elasticity solve produced nonfinite results")
    reaction = np.zeros_like(residual)
    indices = np.array(list(fixed), dtype=int)
    reaction.ravel()[indices] = residual.ravel()[indices]
    return Elasticity3DResult(displacement, strain, stress, applied, reaction, residual)
