# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady isotropic DC conduction on a tagged tetrahedral mesh."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from scipy.sparse.csgraph import connected_components

from ._public import ResultSurface, refuse_text
from .assembly3d import assemble_stiffness_3d as _assemble_stiffness_3d
from .core.checks import readonly_copy, real_scalar
from ._tetra_materials import element_conductivity
from .core.solve import scipy_solve_dirichlet
from .core.tets import tet_gradients as _tet_gradients
from .mesh3d import Mesh3D

__all__ = ["SteadyElectric3DResult", "solve_steady_electric_3d"]


@dataclass(frozen=True)
class SteadyElectric3DResult(ResultSurface):
    """Nodal potential, tetrahedral fields and integrated terminal quantities in SI.

    Terminal current is positive into the conductor. Joule power is integrated
    over the tetrahedra and inward electric power is summed over the terminals.
    """

    mesh: Mesh3D
    electric_potential: np.ndarray
    electric_field: np.ndarray
    current_density: np.ndarray
    electrical_conductivity: np.ndarray
    joule_power_density: np.ndarray
    inward_current: Mapping[str, float]
    joule_power: float
    inward_electric_power: float

    BASIS = "3d"
    UNITS = MappingProxyType({
        "electric_potential": "V", "electric_field": "V/m", "current_density": "A/m^2",
        "electrical_conductivity": "S/m", "joule_power_density": "W/m^3",
        "inward_current": "A", "joule_power": "W", "inward_electric_power": "W",
    })


def _terminals(mesh, values):
    name = "prescribed_electric_potential"
    if not isinstance(values, Mapping) or not values:
        raise ValueError(f"{name} must map at least one exterior face tag to volts")
    terminals = {}
    occupied = np.zeros(mesh.num_nodes, dtype=bool)
    for tag, value in values.items():
        faces = mesh.tagged_faces.get(tag)
        if faces is None or not len(faces):
            raise ValueError(f"terminal {tag!r} needs a nonempty exterior face tag")
        nodes = np.unique(faces)
        if np.any(occupied[nodes]):
            raise ValueError(f"terminal {tag!r} shares nodes with another terminal")
        occupied[nodes] = True
        terminals[tag] = (nodes, real_scalar(value, f"{name}[{tag!r}]"))
    return terminals, occupied


def solve_steady_electric_3d(mesh: Mesh3D, *, electrical_conductivity,
                             prescribed_electric_potential) -> SteadyElectric3DResult:
    """Solve div(-sigma grad V)=0 with P1 tetrahedra and metre coordinates.

    Set positive conductivity in S/m as a scalar, a table keyed by region
    name, or an array of shape (T,) in tetrahedron order.
    Prescribe scalar volts by nonempty exterior face tag. Terminal node sets
    must be disjoint and every connected component needs a terminal. The
    remaining faces are insulated through the natural boundary condition.

    Element arrays follow mesh.tets exactly. Pass joule_power_density (W/m^3)
    directly to the heat solver on the same mesh. This solver uses NumPy/SciPy.
    """
    refuse_text("electrical_conductivity", electrical_conductivity)
    refuse_text("prescribed_electric_potential", prescribed_electric_potential)
    if not isinstance(mesh, Mesh3D):
        raise TypeError("solve_steady_electric_3d takes a galerkin.Mesh3D (use from_mesher)")
    mesh.check()
    if not mesh.num_tets or not np.all(np.isfinite(mesh.nodes)):
        raise ValueError("electric solve requires a nonempty mesh with finite coordinates")
    terminals, fixed = _terminals(mesh, prescribed_electric_potential)
    sigma = element_conductivity(mesh, electrical_conductivity)

    try:
        gradients, volumes = _tet_gradients(mesh)
    except np.linalg.LinAlgError as exc:
        raise ValueError("electric mesh has a singular tetrahedron") from exc
    if np.any(volumes <= 0) or not np.all(np.isfinite(volumes)):
        raise ValueError("electric mesh must have positive finite tetrahedron volumes")
    stiffness = _assemble_stiffness_3d(mesh, sigma)
    if not np.all(np.isfinite(stiffness.data)):
        raise ValueError("assembled electric stiffness exceeds floating-point range")

    # Assembly keeps the structural couplings, including explicitly stored zeros.
    count, labels = connected_components(stiffness, directed=False)
    anchors = np.flatnonzero(fixed)
    anchored, first = np.unique(labels[anchors], return_index=True)
    if len(anchored) != count:
        raise ValueError("each connected mesh component needs a prescribed electric potential")
    voltage = np.zeros(mesh.num_nodes)
    for nodes, value in terminals.values():
        voltage[nodes] = value
    # Remove the common voltage datum before computing gradients and reactions.
    offset = voltage[anchors[first]][labels]
    bc = {tuple(nodes): voltage[nodes] - offset[nodes] for nodes, _ in terminals.values()}
    increment = voltage - offset
    if not fixed.all():
        try:
            increment = scipy_solve_dirichlet(stiffness, np.zeros(mesh.num_nodes), bc, factor=True)
        except ValueError as exc:
            raise ValueError("singular electric system") from exc

    potential = np.where(fixed, voltage, increment + offset)
    residual = stiffness @ increment
    current = {tag: float(residual[nodes].sum()) for tag, (nodes, _) in terminals.items()}
    local = increment[mesh.tets]
    electric = -np.einsum("ti,tij->tj", local[:, 1:] - local[:, :1], gradients[:, 1:])
    density = sigma[:, None] * electric
    heat = np.einsum("ti,ti->t", density, electric)
    dissipated = float(volumes @ heat)
    supplied = float(increment[fixed] @ residual[fixed])
    for value in (potential, residual, list(current.values()), electric, density, heat, dissipated, supplied):
        if not np.all(np.isfinite(value)):
            raise ValueError("electric solution or Joule power exceeds floating-point range")
    free_residual = np.max(np.abs(residual[~fixed]), initial=0.0)
    residual_scale = np.max(abs(stiffness) @ np.abs(increment))
    if free_residual > 1e-10 * residual_scale:
        raise ValueError("electric solve failed the normalized free residual tolerance")
    if abs(dissipated - supplied) > 1e-10 * max(dissipated, abs(supplied)):
        raise ValueError("electric solve failed discrete power balance")
    return SteadyElectric3DResult(
        mesh, *map(readonly_copy, (potential, electric, density, sigma, heat)),
        MappingProxyType(current), dissipated, supplied,
    )
