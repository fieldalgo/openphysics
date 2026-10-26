# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady isotropic electric conduction; see electric_steady2d.md for SI contracts.

Conductivity (scalar or region table), Dirichlet and reference potentials and
outward current may be JAX or PyTorch values (callbacks may return them); the
result arrays are then in that library and carry derivatives. NumPy inputs
compute exactly as before.
"""
from collections.abc import Mapping
from dataclasses import dataclass
import warnings

import numpy as np
from scipy.sparse.linalg import MatrixRankWarning

from .assembly import assemble_load
from .materials import region_property, element_values
from .mesh import Mesh
from .heat_source import ElementHeatSource
from .postprocess import element_gradient
from .solver import solve_dirichlet
from .core import forms, kernels
from .core import solve as core_solve
from .core.backend import Backend, backend_of, is_live, lift, live_namespace, scatter_add, to_numpy
from .core.boundary import scalar_boundary_samples
from .core.checks import readonly_copy, real_value
from .core.sparse import CooMatrix
from .core.triangles import triangle_geometry


@dataclass(frozen=True, init=False)
class ElementConductivity:
    """Positive finite element S/m bound to an exact mesh geometry and order."""
    _field: ElementHeatSource

    def __init__(self, mesh, values):
        field = ElementHeatSource(mesh, values)
        if np.any(field.values <= 0):
            raise ValueError("element conductivity must be strictly positive")
        object.__setattr__(self, "_field", field)

    @property
    def values(self):
        return self._field.values

    def on_mesh(self, mesh):
        return self._field.on_mesh(mesh)


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
        v = real_value(value, name)
        if tuple(v.shape) != ():
            raise ValueError(f"{name} values must be scalar volts")
        out[int(node)] = v if is_live(v) else float(v)
    return out


def _frozen(value):
    """A read-only NumPy copy; a JAX or PyTorch result is returned as it is."""
    return value if is_live(value) else readonly_copy(value)


def solve_steady_electric(mesh, *, conductivity, dirichlet, outward_current=None,
                          reference_potential=None):
    """Solve div(-sigma grad V)=0 on a conforming 2D P1 mesh in metres.

    conductivity: positive scalar, exact region-name table or mesh-bound
        ElementConductivity, S/m. Bare element arrays remain invalid.
    dirichlet: exterior node -> scalar voltage in V.
    outward_current: edge tag -> scalar J.n in A/m², or callback
        (points_m, outward_normals) -> (Q,). Unspecified edges are insulated.
    reference_potential: node -> volts, exactly one gauge per component without
        Dirichlet support. Each such component must have zero net imposed current
        to 1e-12 relative to integral(abs(J.n)); incompatible data is never repaired.
    """
    p, t, area, boundary, count, labels = triangle_geometry(mesh)
    sigma = (conductivity.on_mesh(mesh) if isinstance(conductivity, ElementConductivity)
             else region_property(mesh, conductivity, "conductivity", positive=True, live=True))
    sigma = element_values(mesh, sigma)
    prescribed = _potentials(dirichlet, len(p), "dirichlet", boundary)
    gauges = _potentials({} if reference_potential is None else reference_potential,
                         len(p), "reference_potential")
    anchored = np.zeros(count, dtype=bool)
    offsets = [0.0]*count
    for node, value in prescribed.items():
        if not anchored[labels[node]]:
            offsets[labels[node]] = value
            anchored[labels[node]] = True
    # Only physical voltage constraints exclude natural edges; gauges do not.
    samples = scalar_boundary_samples(mesh, p, t, prescribed, outward_current, None, live=True)
    xp = live_namespace(sigma, *prescribed.values(), *gauges.values(), *(s[4][0] for s in samples))
    outward = lift(xp, np.zeros(len(p)))
    absolute_current = np.zeros(count)
    for _, edges, shape, weights, values in samples:
        local = xp.einsum("eq,qa,eq->ea", *(lift(xp, a) for a in (weights, shape, values[0])))
        outward = scatter_add(xp, len(p), edges.ravel(), xp.reshape(local, (-1,)), base=outward)
        np.add.at(absolute_current, labels[edges[:, 0]],
                  np.sum(weights*np.abs(to_numpy(values[0])), axis=1))
    outward_numbers = to_numpy(outward)
    if not np.all(np.isfinite(outward_numbers)) or not np.all(np.isfinite(absolute_current)):
        raise ValueError("assembled current exceeds floating-point range")
    for component in range(count):
        selected = [node for node in gauges if labels[node] == component]
        if anchored[component]:
            if selected:
                raise ValueError("reference_potential is unnecessary on a Dirichlet component")
        else:
            net = np.sum(outward_numbers[labels == component])
            if abs(net) > 1e-12*absolute_current[component]:
                raise ValueError(f"incompatible Neumann current on component {component}")
            if len(selected) != 1:
                raise ValueError("exactly one reference_potential node is required per Neumann component")
            offsets[component] = gauges[selected[0]]
    if any(is_live(o) for o in offsets):
        offsets = xp.stack([lift(xp, o, xp.float64) for o in offsets])
    else:
        offsets = lift(xp, np.array(offsets, dtype=float))
    sigma = lift(xp, sigma)
    cells = np.asarray(mesh.triangles)
    stiffness = forms.matrix(cells, cells, kernels.p1_stiffness(mesh, sigma), (len(p), len(p)))
    K_numbers = CooMatrix(stiffness.rows, stiffness.cols, to_numpy(stiffness.values),
                          stiffness.shape).to_scipy()
    if not np.all(np.isfinite(K_numbers.data)):
        raise ValueError("assembled electric stiffness exceeds floating-point range")
    bc = {(node,): value-offsets[labels[node]]
          for node, value in (prescribed | gauges).items()}
    with warnings.catch_warnings():
        warnings.simplefilter("error", MatrixRankWarning)
        try:
            if backend_of(xp) is Backend.NUMPY:
                increment = solve_dirichlet(K_numbers, -outward, bc)
            else:
                increment = core_solve.solve_dirichlet(stiffness, -outward, bc)
        except (RuntimeError, MatrixRankWarning, ValueError) as exc:
            raise ValueError("singular or ill-conditioned electric system") from exc
    potential = increment+offsets[labels]
    residual = stiffness.matvec(increment)+outward
    fixed = np.array(sorted(prescribed), dtype=int)
    free = np.setdiff1d(np.arange(len(p)), fixed)  # Includes gauges: no hidden current.
    increment_numbers, residual_numbers = to_numpy(increment), to_numpy(residual)
    scale = max(np.max(abs(K_numbers)@abs(increment_numbers)+abs(outward_numbers)), np.finfo(float).tiny)
    if not np.all(np.isfinite(to_numpy(potential))) or not np.all(np.isfinite(residual_numbers)):
        raise ValueError("nonfinite electric solution or residual")
    if len(free) and np.max(abs(residual_numbers[free])) > 1e-10*scale:
        raise ValueError("electric solve failed the normalized free residual tolerance")
    reaction = np.zeros(len(p))
    reaction[fixed] = residual_numbers[fixed]
    for component in range(count):
        nodes = labels == component
        balance_scale = max(np.sum(abs(reaction[nodes])+abs(outward_numbers[nodes])),
                            np.finfo(float).tiny)
        if abs(np.sum(reaction[nodes]-outward_numbers[nodes])) > 1e-10*balance_scale:
            raise ValueError("electric solve failed component current balance")
    if is_live(residual):
        reaction = scatter_add(xp, len(p), fixed, residual[fixed])
    electric = -element_gradient(mesh, increment)
    current = sigma[:, None]*electric
    heat = xp.einsum("ij,ij->i", current, electric)
    if backend_of(xp) is Backend.NUMPY:
        load = assemble_load(mesh, heat)
        power = float(area@heat)
        supplied = float(increment@(reaction-outward))
    else:
        load = forms.vector(cells, kernels.p1_load(mesh, heat), len(p), order="columns")
        power = lift(xp, area)@heat
        supplied = increment@(reaction-outward)
    power_number, supplied_number = float(to_numpy(power)), float(to_numpy(supplied))
    if not all(np.all(np.isfinite(to_numpy(v))) for v in (electric, current, heat, load, power, supplied)):
        raise ValueError("electric fields or Joule power exceed floating-point range")
    if abs(power_number-supplied_number) > 1e-10*max(abs(power_number), abs(supplied_number), np.finfo(float).tiny):
        raise ValueError("electric solve failed discrete power balance")
    return SteadyElectricResult(
        _snapshot(mesh), *map(_frozen, (potential, electric, current, sigma, heat, load)),
        power, *map(_frozen, (reaction, outward, residual)), supplied)
