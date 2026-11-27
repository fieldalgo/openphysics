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
from .core.checks import positive_real, readonly_copy, real_array, real_scalar
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


def _region_names(mesh, values):
    names = mesh.region_names
    if names is None or mesh.regions is None:
        raise ValueError("electrical_conductivity by region requires named tetrahedral regions")
    if set(values) != set(names):
        raise ValueError("electrical_conductivity keys must match mesh.region_names exactly")
    return names


def _conductivity(mesh, values):
    name = "electrical_conductivity"
    if isinstance(values, Mapping):
        names = _region_names(mesh, values)
        return mesh.by_region([positive_real(values[key], f"{name}[{key!r}]") for key in names])
    if isinstance(values, (list, tuple, np.ndarray)):
        sigma = real_array(values, name)
        if sigma.shape != (mesh.num_tets,) or np.any(sigma <= 0):
            raise ValueError(f"{name} must have shape (T,) and contain positive values")
        return sigma
    return np.full(mesh.num_tets, positive_real(values, name))


def _conductivity_at_temperature_3d(mesh, electrical_conductivity, temperature):
    """Evaluate the DC material law on the tetrahedral means of nodal Kelvin values."""
    from .temperature_joule_heating import ConductivityModel, _sigma

    refuse_text("electrical_conductivity", electrical_conductivity)
    refuse_text("temperature", temperature)
    if not isinstance(mesh, Mesh3D):
        raise TypeError("conductivity evaluation takes a galerkin.Mesh3D")
    nodal = real_array(temperature, "temperature")
    if nodal.shape != (mesh.num_nodes,) or np.any(nodal < 0):
        raise ValueError("temperature must have shape (N,) and contain nonnegative Kelvin values")
    material = electrical_conductivity
    if isinstance(material, Mapping):
        names = _region_names(mesh, material)
        groups = ((name, mesh.regions == i, material[name]) for i, name in enumerate(names))
    else:
        groups = (("all", slice(None), material),)

    sigma = np.empty(mesh.num_tets)
    for name, cells, law in groups:
        if not isinstance(law, ConductivityModel):
            sigma[cells] = positive_real(law, f"electrical_conductivity[{name!r}]")
            continue
        values = nodal[mesh.tets[cells]]
        if not values.size:
            continue
        lo, hi = law.temperature_range
        if np.any((values < lo) | (values > hi)):
            raise ValueError(f"material {name!r}: temperature [{values.min()}, {values.max()}] K "
                             f"outside [{lo}, {hi}] K")
        sigma[cells] = _sigma(law, np.sum(values / 4., axis=1), name)
    return sigma


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
    sigma = _conductivity(mesh, electrical_conductivity)

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
