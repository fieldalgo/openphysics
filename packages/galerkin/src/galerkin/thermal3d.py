# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady P1 heat conduction on tetrahedral meshes with boundary data in SI.

The equation is -div(k grad T) = Q. Prescribe temperatures at exterior nodes
and flux or Robin data on tagged exterior triangles. Unspecified faces are
insulated. With Q constant on each tetrahedron the exact nodal load is Q V / 4.

See docs/packages/galerkin/thermal3d.md for the Mesh3D input and sign conventions.
The source load and the face-tag Dirichlet map live in the package-private
``galerkin._heat_kernels`` and are re-exported by ``galerkin.kernels``.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

from .assembly3d import assemble_stiffness_3d as _assemble_stiffness_3d
from .core.tets import tet_gradients as _tet_gradients
from .mesh3d import Mesh3D
from .solver import solve_dirichlet as _solve_dirichlet
from ._heat_kernels import source_load_3d as _source_load_3d
from ._thermal3d import boundary_system, element_source, natural_faces, prescribed_nodes
from ._tetra_materials import region_property
from ._public import ResultSurface, refuse_text

# Public names. The source load and face-tag map are internal: galerkin.kernels re-exports them.
__all__ = ["SteadyHeat3DResult", "solve_steady_heat_3d"]

_RESIDUAL_TOLERANCE = 1e-10
_BALANCE_TOLERANCE = 1e-10


@dataclass(frozen=True, eq=False)
class SteadyHeat3DResult(ResultSurface):
    """temperature (N,) K, heat_flux (T, 3) W/m^2, the generated, reaction and residual heat rates (N,) W.

    thermal_conductivity and heat_source_density are the per-tetrahedron values used,
    in W/(m K) and W/m^3. Both outward boundary rate arrays are (N,) W.
    The reaction is positive into the domain and is zero at free nodes.
    The balance is generated plus reaction minus both outward rates, normalized
    by the sum of absolute nodal rates (<= 1e-10 or the solve raises).
    prescribed_node_ids are the fixed nodes. Rates are totals (W): asking for a
    ``*_per_depth`` field raises AttributeError, which says why. ``.units`` maps every
    quantity field to its SI unit.
    """
    temperature: np.ndarray
    heat_flux: np.ndarray
    generated_heat_rate: np.ndarray
    reaction_heat_rate: np.ndarray
    residual_heat_rate: np.ndarray
    thermal_conductivity: np.ndarray
    heat_source_density: np.ndarray
    relative_conservation_residual: float
    prescribed_node_ids: np.ndarray

    outward_prescribed_heat_rate: np.ndarray | None = None
    outward_convective_heat_rate: np.ndarray | None = None

    BASIS = "3d"
    UNITS = MappingProxyType({"temperature": "K", "heat_flux": "W/m^2", "generated_heat_rate": "W",
                              "reaction_heat_rate": "W", "residual_heat_rate": "W",
                              "thermal_conductivity": "W/(m K)", "heat_source_density": "W/m^3",
                              "relative_conservation_residual": "1", "outward_prescribed_heat_rate": "W",
                              "outward_convective_heat_rate": "W"})


def solve_steady_heat_3d(mesh: Mesh3D, *, thermal_conductivity, prescribed_temperature,
                         heat_source_density=None, motion=None, inward_heat_flux=None,
                         convection=None) -> SteadyHeat3DResult:
    """Solve -div(k grad T) = Q with Dirichlet, flux and Robin boundaries.

    mesh: ``galerkin.Mesh3D`` in metres (``from_mesher`` of a meshine or gmshio
        mesh, or ``box_mesh``). Natural data use ``mesh.tagged_faces``.
    thermal_conductivity: finite k > 0 in W/(m K), or {region name: k} over every
        ``mesh.region_names`` entry.
    prescribed_temperature: {node index: temperature K}; every node must lie on the
        exterior boundary. Each component needs a fixed node or positive convection.
    heat_source_density: Q in W/m^3, {region name: Q}, or a callable taking the
        (T, 3) tetrahedron centroids (read-only) and returning (T,) values; None
        (the default) is no source. A (T,) array supplies one value per tetrahedron
        in mesh order.
    inward_heat_flux: {exterior face tag: W/m^2}, positive into the mesh.
    convection: {exterior face tag: (h W/(m^2 K), ambient K)}, with finite h >= 0.
        Flux and convection on the same face are additive. Unspecified faces are
        insulated. These options require a static mesh.

    motion: ``galerkin.shape.MeshMotion(design_velocity=W, t=t)`` with W (N, 3) solves on
        the nodes X0 + t W and carries the derivative with respect to the JAX or PyTorch
        scalar t (a shape derivative; docs/packages/galerkin/shape_derivative.md). The
        inputs stay NumPy constants or region tables, or a source callback, which is called
        again at the live centroids and must compute with the JAX or PyTorch array it gets.

    NumPy only otherwise: JAX or PyTorch values raise TypeError, and so does a str for a
    quantity (SI numbers only). Raises ValueError on invalid input, a singular
    system, or a failed residual or heat-balance check.
    """
    for name, value in (("thermal_conductivity", thermal_conductivity),
                        ("prescribed_temperature", prescribed_temperature),
                        ("heat_source_density", heat_source_density), ("inward_heat_flux", inward_heat_flux),
                        ("convection", convection)):
        refuse_text(name, value)
    if not isinstance(mesh, Mesh3D):
        raise TypeError("solve_steady_heat_3d takes a galerkin.Mesh3D (use from_mesher)")
    if motion is not None:
        if any(data is not None and (not isinstance(data, Mapping) or data)
               for data in (inward_heat_flux, convection)):
            raise ValueError("motion does not support 3D flux or convection boundary data")
        from ._moving import solve_steady_heat_3d_moving
        return solve_steady_heat_3d_moving(mesh, motion, thermal_conductivity=thermal_conductivity,
                                           prescribed_temperature=prescribed_temperature,
                                           heat_source_density=heat_source_density)
    k = region_property(mesh, thermal_conductivity, "thermal_conductivity", positive=True)
    source = element_source(mesh, 0.0 if heat_source_density is None else heat_source_density)
    exterior_faces = mesh.boundary_faces()
    prescribed = prescribed_nodes(mesh, exterior_faces, prescribed_temperature)
    fixed = np.array(sorted(prescribed), dtype=int)
    pairs = mesh.tets[:, [[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3]]].reshape(-1, 2)
    graph = sp.coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])),
                          shape=(mesh.num_nodes,) * 2)
    count, labels = connected_components(graph, directed=False)
    anchored = np.zeros(count, dtype=bool)
    samples = list(natural_faces(mesh, exterior_faces, prescribed, inward_heat_flux, convection))
    offsets = np.zeros(count)
    if samples:
        # Conduction annihilates constants. Use a component reference temperature
        # to avoid subtracting large absolute-temperature terms in the Robin rates.
        for node, value in prescribed.items():
            component = labels[node]
            if not anchored[component]:
                offsets[component] = value
                anchored[component] = True
        for kind, faces, _, value in samples:
            if kind == "convection" and value[0] > 0:
                components = np.unique(labels[faces[:, 0]])
                unanchored = components[~anchored[components]]
                offsets[unanchored] = value[1]
                anchored[unanchored] = True
    else:
        anchored[labels[fixed]] = True
    if not anchored.all():
        raise ValueError("each connected component of the mesh needs a Dirichlet node or positive convection; "
                         f"components {np.flatnonzero(~anchored).tolist()} have neither")

    stiffness = _assemble_stiffness_3d(mesh, k).tocsr()
    load = _source_load_3d(mesh, source)
    robin, outward, ambient = boundary_system(samples, labels, offsets)
    node_offsets = offsets[labels]
    rhs = load
    if samples:
        rhs = load - outward + ambient
        stiffness = stiffness + robin
    if not (np.all(np.isfinite(stiffness.data)) and np.all(np.isfinite(rhs))):
        raise ValueError("assembled heat system exceeds floating-point range")
    fixed_values = {(node,): value - node_offsets[node] if samples else value
                    for node, value in prescribed.items()}
    try:
        increment = _solve_dirichlet(stiffness, rhs, fixed_values)
    except (RuntimeError, ValueError) as exc:
        raise ValueError("singular or ill-conditioned constrained heat system") from exc
    temperature = increment
    if samples:
        temperature = increment + node_offsets
        temperature[fixed] = [prescribed[node] for node in fixed]
    residual = stiffness @ increment - rhs
    if not (np.all(np.isfinite(temperature)) and np.all(np.isfinite(residual))):
        raise ValueError("nonfinite heat solution or residual")
    free = np.setdiff1d(np.arange(mesh.num_nodes), fixed)
    scale = max(float(np.linalg.norm(abs(stiffness) @ np.abs(increment) + np.abs(rhs), np.inf)),
                np.finfo(float).tiny)
    if len(free) and np.linalg.norm(residual[free], np.inf) > _RESIDUAL_TOLERANCE * scale:
        raise ValueError("heat solve failed the normalized free residual tolerance")
    reaction = np.zeros(mesh.num_nodes)
    reaction[fixed] = residual[fixed]
    convective = robin @ increment - ambient
    rates = (load, reaction, -outward, -convective)
    balance_scale = max(sum(float(np.abs(rate).sum()) for rate in rates), np.finfo(float).tiny)
    balance_error = abs(sum(float(rate.sum()) for rate in rates)) / balance_scale
    if not np.isfinite(balance_scale) or not np.isfinite(balance_error) or balance_error > _BALANCE_TOLERANCE:
        raise ValueError("heat solve failed the normalized heat balance tolerance")
    gradients, _ = _tet_gradients(mesh)
    flux = -k[:, None] * np.einsum("tnd,tn->td", gradients, increment[mesh.tets])
    return SteadyHeat3DResult(temperature, flux, load, reaction, residual, k, source,
                              balance_error, fixed, outward, convective)
