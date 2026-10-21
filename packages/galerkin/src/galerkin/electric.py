# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady isotropic electric conduction; see electric_steady2d.md for SI contracts."""
from collections.abc import Mapping
from dataclasses import dataclass
import warnings

import numpy as np
from scipy.sparse.linalg import MatrixRankWarning

from .assembly import assemble_stiffness, assemble_load
from .materials import region_property, element_values
from .mesh import Mesh
from .postprocess import element_gradient
from .solver import solve_dirichlet
from .thermal import _mesh_geometry, _boundary_samples, _real


def _readonly(value):
    out = np.array(value, copy=True)
    out.flags.writeable = False
    return out


def _snapshot(mesh):
    copy = Mesh(mesh.nodes.copy(), mesh.triangles.copy(),
                {k: v.copy() for k, v in mesh.boundary.items()},
                {k: v.copy() for k, v in mesh.boundary_edges.items()},
                None if mesh.regions is None else mesh.regions.copy(), mesh.region_names)
    for a in [copy.nodes, copy.triangles, copy.regions,
              *copy.boundary.values(), *copy.boundary_edges.values()]:
        if a is not None:
            a.flags.writeable = False
    return copy


@dataclass(frozen=True)
class SteadyElectricResult:
    """Nodal volts, element V/m, A/m² and W/m³; integrated rates are per metre.

    Arrays are independent read-only snapshots in the returned mesh's order.
    reaction is injected current at physical voltage nodes only, never gauges.
    """
    mesh: Mesh
    potential: np.ndarray
    electric_field: np.ndarray
    current_density: np.ndarray
    conductivity: np.ndarray
    joule_heating: np.ndarray
    joule_load: np.ndarray
    joule_power_per_length: float
    reaction: np.ndarray
    prescribed_outward_load: np.ndarray
    residual: np.ndarray
    supplied_power_per_length: float


def _potentials(data, n, name, boundary=None):
    if not isinstance(data, Mapping):
        raise ValueError(f"{name} must map node indices to scalar volts")
    out = {}
    for node, value in data.items():
        if (isinstance(node, (bool, np.bool_))
                or not isinstance(node, (int, np.integer)) or not 0 <= node < n):
            raise ValueError(f"{name} node indices must be integers within the mesh")
        if boundary is not None and node not in boundary:
            raise ValueError("Dirichlet node must lie on the exterior mesh boundary")
        v = _real(value, name)
        if v.shape != ():
            raise ValueError(f"{name} values must be scalar volts")
        out[int(node)] = float(v)
    return out


def solve_steady_electric(mesh, *, conductivity, dirichlet, outward_current=None,
                          reference_potential=None):
    """Solve div(-sigma grad V)=0 on a conforming 2D P1 mesh in metres.

    conductivity: positive scalar or exact region-name table, S/m.
    dirichlet: exterior node -> scalar voltage in V.
    outward_current: edge tag -> scalar J.n in A/m², or callback
        (points_m, outward_normals) -> (Q,). Unspecified edges are insulated.
    reference_potential: node -> volts, exactly one gauge per component without
        Dirichlet support. Each such component must have zero net imposed current
        to 1e-12 relative to integral(abs(J.n)); incompatible data is never repaired.
    """
    p, t, area, boundary, count, labels = _mesh_geometry(mesh)
    sigma = region_property(mesh, conductivity, "conductivity", positive=True)
    sigma = element_values(mesh, sigma)
    prescribed = _potentials(dirichlet, len(p), "dirichlet", boundary)
    gauges = _potentials({} if reference_potential is None else reference_potential,
                         len(p), "reference_potential")
    anchored = np.zeros(count, dtype=bool)
    offsets = np.zeros(count)
    for node, value in prescribed.items():
        if not anchored[labels[node]]:
            offsets[labels[node]] = value
            anchored[labels[node]] = True
    # Only physical voltage constraints exclude natural edges; gauges do not.
    samples = _boundary_samples(mesh, p, t, prescribed, outward_current, None)
    outward = np.zeros(len(p))
    absolute_current = np.zeros(count)
    for _, edges, shape, weights, values in samples:
        local = np.einsum("eq,qa,eq->ea", weights, shape, values[0])
        np.add.at(outward, edges.ravel(), local.ravel())
        np.add.at(absolute_current, labels[edges[:, 0]],
                  np.sum(weights*np.abs(values[0]), axis=1))
    if not np.all(np.isfinite(outward)) or not np.all(np.isfinite(absolute_current)):
        raise ValueError("assembled current exceeds floating-point range")
    for component in range(count):
        selected = [node for node in gauges if labels[node] == component]
        if anchored[component]:
            if selected:
                raise ValueError("reference_potential is unnecessary on a Dirichlet component")
        else:
            net = np.sum(outward[labels == component])
            if abs(net) > 1e-12*absolute_current[component]:
                raise ValueError(f"incompatible Neumann current on component {component}")
            if len(selected) != 1:
                raise ValueError("exactly one reference_potential node is required per Neumann component")
            offsets[component] = gauges[selected[0]]
    stiffness = assemble_stiffness(mesh, sigma)
    if not np.all(np.isfinite(stiffness.data)):
        raise ValueError("assembled electric stiffness exceeds floating-point range")
    bc = {(node,): value-offsets[labels[node]]
          for node, value in (prescribed | gauges).items()}
    with warnings.catch_warnings():
        warnings.simplefilter("error", MatrixRankWarning)
        try:
            increment = solve_dirichlet(stiffness, -outward, bc)
        except (RuntimeError, MatrixRankWarning) as exc:
            raise ValueError("singular or ill-conditioned electric system") from exc
    potential = increment+offsets[labels]
    residual = stiffness@increment+outward
    fixed = np.array(sorted(prescribed), dtype=int)
    free = np.setdiff1d(np.arange(len(p)), fixed)  # Includes gauges: no hidden current.
    scale = max(np.max(abs(stiffness)@abs(increment)+abs(outward)), np.finfo(float).tiny)
    if not np.all(np.isfinite(potential)) or not np.all(np.isfinite(residual)):
        raise ValueError("nonfinite electric solution or residual")
    if len(free) and np.max(abs(residual[free])) > 1e-10*scale:
        raise ValueError("electric solve failed the normalized free residual tolerance")
    reaction = np.zeros(len(p))
    reaction[fixed] = residual[fixed]
    for component in range(count):
        nodes = labels == component
        balance_scale = max(np.sum(abs(reaction[nodes])+abs(outward[nodes])),
                            np.finfo(float).tiny)
        if abs(np.sum(reaction[nodes]-outward[nodes])) > 1e-10*balance_scale:
            raise ValueError("electric solve failed component current balance")
    electric = -element_gradient(mesh, increment)
    current = sigma[:, None]*electric
    heat = np.einsum("ij,ij->i", current, electric)
    load = assemble_load(mesh, heat)
    power = float(area@heat)
    supplied = float(increment@(reaction-outward))
    if not all(np.all(np.isfinite(v)) for v in (electric, current, heat, load, power, supplied)):
        raise ValueError("electric fields or Joule power exceed floating-point range")
    if abs(power-supplied) > 1e-10*max(abs(power), abs(supplied), np.finfo(float).tiny):
        raise ValueError("electric solve failed discrete power balance")
    return SteadyElectricResult(
        _snapshot(mesh), *map(_readonly, (potential, electric, current, sigma, heat, load)),
        power, *map(_readonly, (reaction, outward, residual)), supplied)
