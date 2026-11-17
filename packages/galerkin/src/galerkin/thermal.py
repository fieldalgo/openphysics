# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady isotropic heat conduction on conforming P1 triangles.

Conductivity is scalar or piecewise constant on named regions (galerkin.materials).
Heat sources may also be mesh-bound ElementHeatSource values or coordinate callbacks. Import this submodule explicitly. See
docs/packages/galerkin/thermal_steady2d.md and
docs/packages/galerkin/multimaterial.md for SI units, boundary signs and
validation limits. No other physics module is required.

Conductivity, heat source, Dirichlet temperatures and boundary data may be JAX
or PyTorch values (callbacks may return them); the result arrays are then in
that library and carry derivatives. NumPy inputs compute exactly as before.

The public function takes keyword-only SI quantities under registry names, with the
inward heat flux (positive enters the body). It negates the inward values once and
calls the internal ``solve_steady_heat_outward`` (outside ``__all__``), which keeps the
outward form galerkin's own callers use (``joule_heating``, the workflows and the
moving-mesh solve).
"""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

import numpy as np
from scipy.sparse import issparse

from .mesh import Mesh
from .heat_source import ElementHeatSource
from .materials import is_per_region, region_property
from .postprocess import element_gradient
from .core import forms, kernels
from .core.backend import is_live, lift, live_namespace, scatter_add, to_numpy
from .core.boundary import scalar_boundary_samples
from .core.checks import real_value
from .core.loads import ElementSource, source_load
from .core.measure import ScalarMeasure
from .core import solve as core_solve
from .core.sparse import CooMatrix
from .core.triangles import triangle_geometry
from ._heat_kernels import component_offsets as _offsets, scalar_boundary_system as _scalar_boundary_system
from ._public import ResultSurface, outward_from_inward, refuse_text

# Public names. Internal: the boundary system (galerkin._heat_kernels, re-exported by galerkin.kernels) and
# solve_steady_heat_outward, the outward-form body that galerkin's own callers use (outside __all__).
__all__ = ["SteadyHeatResult", "PlanarSteadyHeatResult", "AxisymmetricSteadyHeatResult", "solve_steady_heat",
           "ElementHeatSource"]


def _numbers(matrix):
    """A NumPy snapshot of a CooMatrix as SciPy CSR, for checks."""
    return CooMatrix(matrix.rows, matrix.cols, to_numpy(matrix.values), matrix.shape).to_scipy()


def _coo(xp, matrix):
    """A CooMatrix in ``xp`` from a CooMatrix or SciPy matrix.

    A canonical SciPy CSR (summed, sorted) returns from ``to_scipy`` unchanged.
    """
    if issparse(matrix):
        matrix = matrix.tocoo()
        return CooMatrix(matrix.row, matrix.col, lift(xp, matrix.data), matrix.shape)
    return CooMatrix(matrix.rows, matrix.cols, lift(xp, matrix.values), matrix.shape)


class SteadyHeatResult(ResultSurface):
    """Base of the steady heat results: ``PlanarSteadyHeatResult`` (``coordinate_system``
    "cartesian", nodal rates per metre of depth) and ``AxisymmetricSteadyHeatResult``
    ("axisymmetric", nodal rates over the full revolution). Not constructed itself.

    Fields: temperature (N,) K and heat_flux (M,2) W/m^2, then the nodal heat rates
    (N,): generated (the source load), reaction (residual=(K+H)*T-applied on fixed
    nodes, zero on free nodes; positive injects heat, so the Dirichlet thermostat's
    outward contribution is -reaction), residual, outward_prescribed (G),
    ambient_convective (B), outward_convective (C=H*T-B) and applied (load+B-G, the
    system right-hand side). Total outward heat is -reaction+G+C. ``.units`` maps
    every field to its SI unit.
    """


_RATES = ("generated_heat_rate", "reaction_heat_rate", "residual_heat_rate", "outward_prescribed_heat_rate",
          "ambient_convective_heat_rate", "outward_convective_heat_rate", "applied_heat_rate")


@dataclass
class PlanarSteadyHeatResult(SteadyHeatResult):
    """A Cartesian (planar) steady heat result: nodal heat rates in W per metre of depth.

    See ``SteadyHeatResult``. The optional rates are None when built without them.
    """
    temperature: np.ndarray
    heat_flux: np.ndarray
    generated_heat_rate_per_depth: np.ndarray
    reaction_heat_rate_per_depth: np.ndarray
    residual_heat_rate_per_depth: np.ndarray
    outward_prescribed_heat_rate_per_depth: np.ndarray | None = None
    ambient_convective_heat_rate_per_depth: np.ndarray | None = None
    outward_convective_heat_rate_per_depth: np.ndarray | None = None
    applied_heat_rate_per_depth: np.ndarray | None = None

    coordinate_system = "cartesian"
    BASIS = "planar"
    UNITS = MappingProxyType({"temperature": "K", "heat_flux": "W/m^2",
                              **{f"{name}_per_depth": "W/m" for name in _RATES}})


@dataclass
class AxisymmetricSteadyHeatResult(SteadyHeatResult):
    """An axisymmetric steady heat result: nodal heat rates in W over the full revolution.

    See ``SteadyHeatResult``. Its fields have no ``_per_depth``; asking for one raises
    AttributeError, which says why.
    """
    temperature: np.ndarray
    heat_flux: np.ndarray
    generated_heat_rate: np.ndarray
    reaction_heat_rate: np.ndarray
    residual_heat_rate: np.ndarray
    outward_prescribed_heat_rate: np.ndarray | None = None
    ambient_convective_heat_rate: np.ndarray | None = None
    outward_convective_heat_rate: np.ndarray | None = None
    applied_heat_rate: np.ndarray | None = None

    coordinate_system = "axisymmetric"
    BASIS = "axisymmetric"
    UNITS = MappingProxyType({"temperature": "K", "heat_flux": "W/m^2", **{name: "W" for name in _RATES}})


def _steady_result(coordinate_system):
    """The result class of a solve in ``coordinate_system`` (validated by ScalarMeasure)."""
    return AxisymmetricSteadyHeatResult if coordinate_system == "axisymmetric" else PlanarSteadyHeatResult


def _element_source(heat_source, mesh):
    """An ElementHeatSource as the checked element values core.loads takes; other sources unchanged."""
    if isinstance(heat_source, ElementHeatSource):
        return ElementSource(heat_source.on_mesh(mesh))
    return heat_source


def solve_steady_heat(mesh, *, thermal_conductivity, prescribed_temperature, heat_source_density=None,
                      inward_heat_flux=None, convection=None, coordinate_system="cartesian", motion=None):
    """Solve -div(k grad T)=Q with prescribed temperatures, inward heat flux and Robin data, in SI.

    thermal_conductivity is a finite scalar k>0 in W/(m K), or {region name: k}
    with every mesh.region_names entry. heat_source_density is Q in W/m^3: a
    scalar, {region name: Q}, a callback receiving (Q,2) metre coordinates
    (positions) and returning (Q,) W/m^3, or ElementHeatSource(mesh, values) with
    (M,) W/m^3 in exact cell order; None (the default) is no source.
    prescribed_temperature maps integer node indices (exterior or interior: a
    prescribed temperature on an internal surface is an ordinary constraint, and
    its reaction is the heat that surface injects) to scalar temperatures in K;
    every disconnected component requires a prescribed temperature or positive
    Robin support. inward_heat_flux maps edge tags to the normal heat flux
    entering the body (W/m^2, positive in); convection maps tags to
    (heat_transfer_coefficient h, ambient_temperature) in W/(m^2 K) and K,
    h>=0, so that the heat leaving the body is h*(T-ambient) less the inward
    flux. Boundary values are scalars or callbacks(position, outward_normal)->(Q,).
    Untagged natural edges are insulated. See docs/packages/galerkin/thermal_flux_robin.md.
    coordinate_system="axisymmetric" interprets coordinates as (r,z), r>=0,
    and uses the full 2*pi*r volume and surface measure: the result is then an
    AxisymmetricSteadyHeatResult with nodal heat rates in W over the revolution,
    otherwise a PlanarSteadyHeatResult with rates in W per metre of depth.
    motion=galerkin.shape.MeshMotion(design_velocity, t) solves on the nodes
    X0 + t*design_velocity and carries the derivative with respect to the JAX or
    PyTorch scalar t (a shape derivative); see docs/packages/galerkin/shape_derivative.md.

    A str for a quantity raises TypeError (SI numbers only). The inward flux is
    negated once, as 0.0 - x (a callback's checked float result likewise), and the
    outward-form solve runs exactly as before; see galerkin._public.
    """
    outward_flux = outward_from_inward(inward_heat_flux, "inward_heat_flux")     # a non-mapping: ValueError
    for name, value in (("thermal_conductivity", thermal_conductivity),
                        ("prescribed_temperature", prescribed_temperature),
                        ("heat_source_density", heat_source_density), ("inward_heat_flux", inward_heat_flux),
                        ("convection", convection)):
        refuse_text(name, value)
    return solve_steady_heat_outward(mesh, conductivity=thermal_conductivity, dirichlet=prescribed_temperature,
                              heat_source=0.0 if heat_source_density is None else heat_source_density,
                              outward_flux=outward_flux, convection=convection,
                              coordinate_system=coordinate_system, motion=motion)


def solve_steady_heat_outward(mesh, *, conductivity, dirichlet, heat_source=0.0,
                       outward_flux=None, convection=None, coordinate_system="cartesian", motion=None):
    """Solve -div(k grad T)=Q with Dirichlet, outward flux and Robin data (the outward form).

    The body of solve_steady_heat before the galerkin step, for galerkin's own callers.

    conductivity is finite scalar k>0 in W/(m K), or {region name: k} with
    every mesh.region_names entry. heat_source is scalar Q, {region name: Q},
    a callback receiving (Q,2) metre coordinates and returning (Q,) W/m^3,
    or ElementHeatSource(mesh, values) with (M,) W/m^3 in exact cell order.
    dirichlet maps integer node indices (exterior or interior: a prescribed
    temperature on an internal surface is an ordinary constraint, and its
    reaction is the heat that surface injects) to scalar temperatures in K;
    every disconnected component requires Dirichlet or positive Robin support.
    outward_flux maps edge tags to g; convection maps tags to (h, ambient).
    q.n = g+h*(T-ambient), h>=0. Boundary scalars or callbacks
    (points_m, outward_normals)->(Q,) use W/m^2, W/(m^2 K), K respectively.
    Untagged natural edges are insulated. See docs/packages/galerkin/thermal_flux_robin.md.
    coordinate_system="axisymmetric" interprets coordinates as (r,z), r>=0,
    and uses the full 2*pi*r volume and surface measure. Nodal heat rates then
    have units W, recorded on the result, instead of the Cartesian W/m.
    motion=galerkin.shape.MeshMotion(design_velocity, t) solves on the nodes
    X0 + t*design_velocity and carries the derivative with respect to the JAX or
    PyTorch scalar t (a shape derivative); see docs/packages/galerkin/shape_derivative.md.
    """
    if motion is not None:
        from ._moving import solve_steady_heat_moving
        return solve_steady_heat_moving(mesh, motion, thermal_conductivity=conductivity,
                                        prescribed_temperature=dirichlet, heat_source_density=heat_source,
                                        outward_heat_flux=outward_flux, convection=convection,
                                        coordinate_system=coordinate_system)
    if not is_per_region(conductivity):
        k = real_value(conductivity, "thermal_conductivity")
        if tuple(k.shape) != () or to_numpy(k) <= 0:
            raise ValueError("thermal_conductivity must be a finite scalar > 0")
        k = k if is_live(k) else float(k)
    p, t, area, boundary, count, labels = triangle_geometry(mesh)
    measure = ScalarMeasure(mesh, coordinate_system)
    if is_per_region(conductivity):
        k = region_property(mesh, conductivity, "thermal_conductivity", positive=True, live=True)
    if not isinstance(dirichlet, Mapping):
        raise ValueError("prescribed_temperature must map node indices to temperatures in K")
    prescribed = {}
    anchors = [0.0]*count
    constrained = np.zeros(count, dtype=bool)
    for node, value in dirichlet.items():
        if isinstance(node, (bool, np.bool_)) or not isinstance(node, (int, np.integer)):
            raise ValueError("prescribed_temperature node indices must be integers")
        if not 0 <= node < len(p):
            raise ValueError(f"prescribed_temperature node {node} is outside the mesh's {len(p)} nodes")
        value = real_value(value, "prescribed_temperature value")
        if tuple(value.shape) != ():
            raise ValueError("prescribed_temperature values must be scalar")
        prescribed[int(node)] = value if is_live(value) else float(value)
        component = labels[node]
        if not constrained[component]:
            anchors[component] = value
            constrained[component] = True
    measure.check_axis_dirichlet(prescribed)
    samples = measure.boundary_samples(
        scalar_boundary_samples(mesh, p, t, prescribed, outward_flux, convection, live=True))
    H, G, B, shifted_B = _scalar_boundary_system(samples, len(p), labels, anchors, constrained)
    missing = np.flatnonzero(~constrained)
    if len(missing):
        raise ValueError("each connected component requires prescribed_temperature or a positive convection "
                         f"heat_transfer_coefficient; missing {missing.tolist()}")
    cells = np.asarray(mesh.triangles)
    element = kernels.p1_stiffness(mesh, k)
    if measure.axisymmetric:
        xp = live_namespace(element)
        element = element*xp.asarray(measure.cell_factor())[:, None, None]
    stiffness = forms.matrix(cells, cells, element, (len(p), len(p)))
    load = source_load(mesh, p, t, area, _element_source(heat_source, mesh), live=True, measure=measure)
    # One array library for everything from here on (NumPy objects stay as they are).
    xp = live_namespace(k, load, G, B, shifted_B, None if issparse(H) else H.values,
                        *anchors, *prescribed.values())
    k, load, G, B, shifted_B = (lift(xp, a) for a in (k, load, G, B, shifted_B))
    offsets = _offsets(xp, anchors)
    stiffness, H = _coo(xp, stiffness), _coo(xp, H)
    rhs = load+B-G
    shifted_rhs = load+shifted_B-G
    K_numbers, H_numbers = _numbers(stiffness), _numbers(H)
    if not all(np.all(np.isfinite(a)) for a in
               (K_numbers.data, H_numbers.data,
                *map(to_numpy, (load, G, B, shifted_B, rhs, shifted_rhs)))):
        raise ValueError("assembled heat system exceeds floating-point range")
    shifted_bc = {(node,): value-offsets[labels[node]] for node, value in prescribed.items()}
    try:
        increment = core_solve.solve_dirichlet([stiffness, H], shifted_rhs, shifted_bc)
    except (RuntimeError, ValueError) as exc:
        raise ValueError("singular or ill-conditioned constrained heat system") from exc
    temperature = increment+offsets[labels]
    # K annihilates constants; H does not. shifted_B integrates h*(ambient-offset).
    # Evaluate derivatives and convection before restoring absolute temperature.
    convective = H.matvec(increment)-shifted_B
    residual = stiffness.matvec(increment)+convective-load+G
    flux = -(k[:, None] if getattr(k, "ndim", 0) else k)*element_gradient(mesh, increment)
    numbers = {name: to_numpy(a) for name, a in (("temperature", temperature), ("residual", residual),
               ("flux", flux), ("convective", convective), ("increment", increment),
               ("shifted_rhs", shifted_rhs), ("load", load), ("G", G))}
    if not all(np.all(np.isfinite(numbers[a])) for a in ("temperature", "residual", "flux", "convective")):
        raise ValueError("nonfinite heat solution, residual or heat flux")
    fixed = np.array(sorted(prescribed), dtype=int)
    free = np.setdiff1d(np.arange(len(p)), fixed)
    scale = max(np.linalg.norm(abs(K_numbers+H_numbers)@abs(numbers["increment"])
                               + abs(numbers["shifted_rhs"]), np.inf),
                np.finfo(float).tiny)
    if len(free) and np.linalg.norm(numbers["residual"][free], np.inf) > 1e-10*scale:
        raise ValueError("heat solve failed the normalized free residual tolerance")
    reaction = np.zeros(len(p))
    reaction[fixed] = numbers["residual"][fixed]
    for component in range(count):
        nodes = labels == component
        balance_scale = max(sum(np.sum(abs(a[nodes])) for a in
                                (numbers["load"], reaction, numbers["G"], numbers["convective"])),
                            np.finfo(float).tiny)
        if abs(np.sum((numbers["load"]+reaction-numbers["G"]-numbers["convective"])[nodes])) > 1e-10*balance_scale:
            raise ValueError("heat solve failed the normalized component heat balance tolerance")
    if is_live(residual):
        reaction = scatter_add(xp, len(p), fixed, residual[fixed])
    return _steady_result(coordinate_system)(temperature, flux, load, reaction, residual, G, B, convective, rhs)
