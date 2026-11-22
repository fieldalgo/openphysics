# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The moving-mesh solves of galerkin.shape's motion= route (package-private).

``solve_steady_heat_moving``, ``solve_transient_heat_moving``,
``solve_steady_electric_moving``, ``solve_elasticity_moving``,
``solve_thermoelasticity_moving`` and ``solve_steady_thermoelasticity_moving`` solve on
X0 + t W and attach the derivative with respect to the motion's t. They were names of
``galerkin.shape`` until the galerkin step: D21 makes them internal, so they live here
since L2 commit 8 and ``galerkin.kernels`` re-exports them unchanged. The public route
is ``motion=`` on the public solver, which refuses text and negates inward data first:
the heat mirrors take the outward heat flux (``outward_heat_flux``), the electric
mirror the outward current density (``outward_current_density``), and every other
quantity has its registry name. Mechanics has no inward or outward sign.

The motion helpers ``galerkin.shape`` shares with them are here too, under the
package-private names ``live_t``, ``checked_velocity``, ``checked_step``,
``moved_mesh``, ``signed_area`` and ``live_bc``. Consistent units: SI from the solvers.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from . import _mechanics_kernels as _mechanics
from .core import solve as core_solve
from .core.backend import is_live, lift, namespace, require_float64, scatter_add, to_numpy
from .core.materials import is_per_region, region_property
from .core.sparse import CooMatrix
from .mesh import Mesh

if TYPE_CHECKING:                      # annotations only: galerkin.shape imports this module's helpers
    from .shape import MeshMotion

__all__ = ["solve_steady_heat_moving", "solve_transient_heat_moving", "solve_steady_electric_moving",
           "solve_elasticity_moving", "solve_thermoelasticity_moving", "solve_steady_thermoelasticity_moving",
           "live_t", "checked_velocity", "checked_step", "moved_mesh", "signed_area", "live_bc", "cross"]

_EDGE_MASS = np.array([[2.0, 1.0], [1.0, 2.0]]) / 6.0

# ----------------------------------------------------------------------------- steady heat

def solve_steady_heat_moving(mesh: Mesh, motion: MeshMotion, *, thermal_conductivity, prescribed_temperature,
                             heat_source_density=0.0, outward_heat_flux=None, convection=None,
                             coordinate_system="cartesian"):
    """``thermal.solve_steady_heat`` on X0 + t W with the derivative with respect to ``motion.t``.

    Internal (galerkin.kernels): reached through ``motion=``, after the public solver has
    negated the inward flux, so this takes the outward heat flux (positive leaves the body).
    The numbers come from the ordinary solve on the moved mesh, with all its checks;
    the derivative is attached by one more live solve of the system assembled from
    the live node coordinates, on the increment over each component's offset (as the
    solver): u = u0 + A(t)^-1 (b_shifted(t) - A(t) u0), T = u + offset, equal to T0 up to
    rounding."""
    from . import thermal
    from .shape import ElementInversion, admissible_interval

    conductivity, dirichlet, heat_source, outward_flux = (thermal_conductivity, prescribed_temperature,
                                                          heat_source_density, outward_heat_flux)

    xp, t = _live_t(motion.t)
    W = _velocity(mesh, motion.design_velocity)
    axisymmetric = _axisymmetric(mesh, W, coordinate_system, t)
    _coefficient(conductivity, "thermal_conductivity")
    _numpy_data(heat_source, "heat_source_density")
    for name, table in (("outward_flux", outward_flux), ("convection", convection)):
        for tag, value in _tags(table, name).items():
            _numpy_data(value, _boundary_label(name, tag))
    if not isinstance(dirichlet, Mapping):
        raise ValueError("prescribed_temperature must map node indices to temperatures in K")
    for node, value in dirichlet.items():
        _numpy_data(value, "prescribed_temperature", sampled=False)
    t0 = float(to_numpy(t))
    if not math.isfinite(t0):
        raise ValueError(f"motion: t must be finite, got {t0!r}")
    lo, hi = admissible_interval(mesh, design_velocity=W)
    if not lo < t0 < hi:
        raise ElementInversion(f"motion: the step t = {t0:g} inverts an element (admissible interval "
                               f"({lo:g}, {hi:g}))")
    moved = _moved_mesh(mesh, W, t0)
    base = thermal.solve_steady_heat_outward(moved, conductivity=conductivity, dirichlet=dirichlet,
                                      heat_source=heat_source, outward_flux=outward_flux, convection=convection,
                                      coordinate_system=coordinate_system)
    n = mesh.num_nodes
    X = lift(xp, mesh.nodes) + t * lift(xp, W)
    tris = mesh.triangles
    b, c, area = _live_bc(xp, X, tris, np.sign(_signed_area(moved.nodes, tris)))
    k = _per_triangle(mesh, conductivity, "thermal_conductivity", positive=True)
    Q = _per_triangle(mesh, heat_source, "heat_source_density")
    kk = lift(xp, k)[:, None, None]
    element = kk * (b[:, :, None] * b[:, None, :] + c[:, :, None] * c[:, None, :]) / (4.0 * area)[:, None, None]
    if axisymmetric:
        element = element * _cell_factor(xp, X, tris)[:, None, None]
    K = CooMatrix(np.repeat(tris, 3, axis=1).ravel(), np.tile(tris, (1, 3)).ravel(),
                  xp.reshape(element, (-1,)), (n, n))
    load = scatter_add(xp, n, tris.ravel(), xp.reshape(_cell_load(xp, X, tris, area, lift(xp, Q), axisymmetric),
                                                       (-1,)))
    # Work with the increment over each component's offset, as thermal.py does: K annihilates
    # constants, so a large common temperature times a rounding-level sum must not reach the
    # residual, reactions, convection or flux. The offset of a component is its first Dirichlet
    # value, else the ambient of its first convection edge with h > 0 (thermal.py's anchors).
    # The plain solve above refuses a component with neither, so the last rule is only a guard.
    from .core.triangles import triangle_geometry
    _p, _t, _a, _b, count, labels = triangle_geometry(moved)
    offsets = np.zeros(count)
    anchored = np.zeros(count, dtype=bool)
    for node, value in dirichlet.items():
        if not anchored[labels[node]]:
            offsets[labels[node]], anchored[labels[node]] = float(value), True
    for tag, (h, ambient) in (convection or {}).items():
        if float(h) > 0:
            for node in np.asarray(mesh.boundary_edges[tag], dtype=int).ravel():
                if not anchored[labels[node]]:
                    offsets[labels[node]], anchored[labels[node]] = float(ambient), True
    for component in np.flatnonzero(~anchored):
        offsets[component] = float(base.temperature[np.flatnonzero(labels == component)[0]])
    H_terms, B, shifted_B, G = [], None, None, None
    for tag, g in (outward_flux or {}).items():
        edges, length = _boundary_edges(xp, mesh, X, tag)
        G = scatter_add(xp, n, edges.ravel(), xp.reshape(_edge_load(xp, X, edges, length, float(g), axisymmetric),
                                                          (-1,)), base=G)
    for tag, (h, ambient) in (convection or {}).items():
        edges, length = _boundary_edges(xp, mesh, X, tag)
        local = _edge_mass(xp, X, edges, length, float(h), axisymmetric)
        H_terms.append(CooMatrix(np.repeat(edges, 2, axis=1).ravel(), np.tile(edges, (1, 2)).ravel(),
                                 xp.reshape(local, (-1,)), (n, n)))
        B = scatter_add(xp, n, edges.ravel(), xp.reshape(_edge_load(xp, X, edges, length,
                                                                    float(h) * float(ambient), axisymmetric),
                                                         (-1,)), base=B)
        # h (ambient - offset): an edge lies in one component, so both its nodes share the offset
        shift = float(h) * (float(ambient) - offsets[labels[edges[:, 0]]])
        shifted_B = scatter_add(xp, n, edges.ravel(), xp.reshape(_edge_load(xp, X, edges, length, lift(xp, shift),
                                                                            axisymmetric), (-1,)),
                                base=shifted_B)
    zero = xp.zeros(n, dtype=xp.float64)
    G = zero if G is None else G
    B = zero if B is None else B
    shifted_B = zero if shifted_B is None else shifted_B
    rhs = load + B - G
    shifted_rhs = load + shifted_B - G
    terms = [K, *H_terms]

    def apply(u):
        return sum((term.matvec(u) for term in terms[1:]), terms[0].matvec(u))
    u0 = lift(xp, np.asarray(base.temperature, dtype=float) - offsets[labels])
    fixed = {(int(node),): 0.0 for node in dirichlet}
    delta = core_solve.solve_dirichlet(terms, shifted_rhs - apply(u0), fixed)
    increment = u0 + delta
    temperature = increment + lift(xp, offsets[labels])
    residual = apply(increment) - shifted_rhs
    convective = (sum((term.matvec(increment) for term in terms[1:]), zero) - shifted_B) if H_terms else zero
    fixed_nodes = np.array(sorted(int(i) for i in dirichlet), dtype=int)
    reaction = scatter_add(xp, n, fixed_nodes, residual[fixed_nodes])
    grad_x = xp.sum(b * increment[tris], axis=1) / (2.0 * area)
    grad_y = xp.sum(c * increment[tris], axis=1) / (2.0 * area)
    flux = -lift(xp, k)[:, None] * xp.stack([grad_x, grad_y], axis=1)
    result = thermal.AxisymmetricSteadyHeatResult if axisymmetric else thermal.PlanarSteadyHeatResult
    return result(temperature, flux, load, reaction, residual, G, B, convective, rhs)


def solve_steady_heat_3d_moving(mesh, motion: MeshMotion, *, thermal_conductivity, prescribed_temperature,
                                heat_source_density=None):
    """``thermal3d.solve_steady_heat_3d`` on X0 + t W with the derivative with respect to ``motion.t``.

    Internal: reached through ``motion=``. The ordinary solve on the moved Mesh3D gives the
    numbers and every check; one more live solve of the P1 system assembled from the live node
    coordinates attaches the derivative, on the increment over each component's first
    Dirichlet value: u = u0 + K(t)^-1 (b(t) - K(t) u0), T = u + offset. The barycentric
    gradients are the cofactor rows (e2 x e3, e3 x e1, e1 x e2) / det, the volume det / 6."""
    from . import thermal3d

    xp, t = _live_t(motion.t)
    W = _velocity(mesh, motion.design_velocity)
    _coefficient(thermal_conductivity, "thermal_conductivity")
    source = 0.0 if heat_source_density is None else heat_source_density
    if callable(source) and not is_per_region(source):
        raise TypeError("motion: heat_source_density is a callback; with a moving mesh its sample points move "
                        "too, which this slice does not differentiate. Give a scalar or a region table")
    _numpy_data(source, "heat_source_density")
    if not isinstance(prescribed_temperature, Mapping):
        raise ValueError("prescribed_temperature must map exterior node indices to temperatures in K")
    for node, value in prescribed_temperature.items():
        _numpy_data(value, "prescribed_temperature", sampled=False)
    moved = _checked_step(mesh, W, t)
    base = thermal3d.solve_steady_heat_3d(moved, thermal_conductivity=thermal_conductivity,
                                          prescribed_temperature=prescribed_temperature,
                                          heat_source_density=heat_source_density)
    n = mesh.num_nodes
    tets = mesh.tets
    X = lift(xp, mesh.nodes) + t * lift(xp, W)
    p = [X[tets[:, i]] for i in range(4)]
    e1, e2, e3 = p[1] - p[0], p[2] - p[0], p[3] - p[0]
    rows = [_cross3(xp, e2, e3), _cross3(xp, e3, e1), _cross3(xp, e1, e2)]
    det = xp.sum(e1 * rows[0], axis=1)
    g = xp.stack(rows, axis=1) / det[:, None, None]                                  # (T, 3, 3)
    grads = xp.concatenate([-xp.sum(g, axis=1)[:, None, :], g], axis=1)              # (T, 4, 3)
    volume = det / 6.0
    k = lift(xp, np.asarray(base.thermal_conductivity, dtype=float))
    Q = lift(xp, np.asarray(base.heat_source_density, dtype=float))
    element = (k * volume)[:, None, None] * xp.sum(grads[:, :, None, :] * grads[:, None, :, :], axis=3)
    K = CooMatrix(np.repeat(tets, 4, axis=1).ravel(), np.tile(tets, (1, 4)).ravel(),
                  xp.reshape(element, (-1,)), (n, n))
    load = scatter_add(xp, n, tets.ravel(), xp.reshape((Q * volume / 4.0)[:, None]
                                                       * xp.ones((1, 4), dtype=xp.float64), (-1,)))
    # increments over each component's first Dirichlet value (K annihilates constants)
    from scipy.sparse.csgraph import connected_components
    import scipy.sparse as _sp
    pairs = tets[:, [[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3]]].reshape(-1, 2)
    graph = _sp.coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
    count, labels = connected_components(graph, directed=False)
    offsets = np.zeros(count)
    anchored = np.zeros(count, dtype=bool)
    for node, value in prescribed_temperature.items():
        if not anchored[labels[int(node)]]:
            offsets[labels[int(node)]], anchored[labels[int(node)]] = float(value), True
    u0 = lift(xp, np.asarray(base.temperature, dtype=float) - offsets[labels])
    fixed = {(int(node),): 0.0 for node in prescribed_temperature}
    delta = core_solve.solve_dirichlet([K], load - K.matvec(u0), fixed)
    increment = u0 + delta
    temperature = increment + lift(xp, offsets[labels])
    residual = K.matvec(increment) - load
    fixed_nodes = np.asarray(base.prescribed_node_ids, dtype=int)
    reaction = scatter_add(xp, n, fixed_nodes, residual[fixed_nodes])
    flux = -k[:, None] * xp.sum(grads * increment[tets][:, :, None], axis=1)
    return thermal3d.SteadyHeat3DResult(temperature, flux, load, reaction, residual, base.thermal_conductivity,
                                        base.heat_source_density, base.relative_conservation_residual,
                                        base.prescribed_node_ids)


def _cross3(xp, u, v):
    return xp.stack([u[:, 1] * v[:, 2] - u[:, 2] * v[:, 1], u[:, 2] * v[:, 0] - u[:, 0] * v[:, 2],
                     u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]], axis=1)


# ----------------------------------------------------------------------------- steady electric

def solve_steady_electric_moving(mesh: Mesh, motion: MeshMotion, *, electrical_conductivity,
                                 prescribed_electric_potential, outward_current_density=None,
                                 reference_electric_potential=None):
    """``electric.solve_steady_electric`` on X0 + t W with the derivative with respect to ``motion.t``.

    Internal (galerkin.kernels): reached through ``motion=``, after the public solver has
    negated the inward current density, so this takes the outward current density
    (A/m^2, positive leaves the body). As for heat: the ordinary solve on the moved mesh
    gives the numbers and all checks, and one live solve of the system assembled from
    the live coordinates attaches the derivative to every result field."""
    from . import electric
    from .shape import ElementInversion, admissible_interval

    conductivity, dirichlet, outward_current, reference_potential = (
        electrical_conductivity, prescribed_electric_potential, outward_current_density, reference_electric_potential)

    xp, t = _live_t(motion.t)
    W = _velocity(mesh, motion.design_velocity)
    if type(conductivity).__name__ == "ElementConductivity":
        raise TypeError("motion: electrical_conductivity is an ElementConductivity; give a scalar or a region table")
    _coefficient(conductivity, "electrical_conductivity")
    for tag, value in _tags(outward_current, "outward_current_density").items():
        _numpy_data(value, f"the current density on {tag!r}")
    for name, table in (("prescribed_electric_potential", dirichlet),
                        ("reference_electric_potential", reference_potential or {})):
        if not isinstance(table, Mapping):
            raise ValueError(f"{name} must map node indices to scalar volts")
        for value in table.values():
            _numpy_data(value, name, sampled=False)
    t0 = float(to_numpy(t))
    if not math.isfinite(t0):
        raise ValueError(f"motion: t must be finite, got {t0!r}")
    lo, hi = admissible_interval(mesh, design_velocity=W)
    if not lo < t0 < hi:
        raise ElementInversion(f"motion: the step t = {t0:g} inverts an element (admissible interval "
                               f"({lo:g}, {hi:g}))")
    moved = _moved_mesh(mesh, W, t0)
    base = electric.solve_steady_electric_outward(moved, conductivity=conductivity, dirichlet=dirichlet,
                                                  outward_current=outward_current,
                                                  reference_potential=reference_potential)
    n = mesh.num_nodes
    X = lift(xp, mesh.nodes) + t * lift(xp, W)
    tris = mesh.triangles
    b, c, area = _live_bc(xp, X, tris, np.sign(_signed_area(moved.nodes, tris)))
    sigma = lift(xp, _per_triangle(mesh, conductivity, "electrical_conductivity", positive=True))
    element = sigma[:, None, None] * (b[:, :, None] * b[:, None, :] + c[:, :, None] * c[:, None, :]) \
        / (4.0 * area)[:, None, None]
    K = CooMatrix(np.repeat(tris, 3, axis=1).ravel(), np.tile(tris, (1, 3)).ravel(),
                  xp.reshape(element, (-1,)), (n, n))
    outward = xp.zeros(n, dtype=xp.float64)
    for tag, g in (outward_current or {}).items():
        edges, length = _boundary_edges(xp, mesh, X, tag)
        outward = scatter_add(xp, n, edges.ravel(), xp.reshape((float(g) * length / 2.0)[:, None]
                                                                * xp.ones((1, 2), dtype=xp.float64), (-1,)),
                              base=outward)
    # Work with the increment over each component's offset, as electric.py does: a large
    # common-mode voltage times a rounding-level sum must not reach residual or power.
    from .core.triangles import triangle_geometry
    _p, _t, _a, _b, count, labels = triangle_geometry(moved)
    gauges = reference_potential or {}
    offsets = np.zeros(count)
    anchored = np.zeros(count, dtype=bool)
    for node, value in (*dirichlet.items(), *gauges.items()):
        if not anchored[labels[node]]:
            offsets[labels[node]], anchored[labels[node]] = float(value), True
    _check_neumann_balance(mesh, W, moved, labels, count, anchored, dirichlet, outward_current)
    I0 = lift(xp, np.asarray(base.electric_potential) - offsets[labels])
    fixed = {(int(node),): 0.0 for node in (*dirichlet, *gauges)}
    delta = core_solve.solve_dirichlet(K, -outward - K.matvec(I0), fixed)
    increment = I0 + delta
    potential = increment + lift(xp, offsets[labels])
    residual = K.matvec(increment) + outward
    prescribed = np.array(sorted(int(i) for i in dirichlet), dtype=int)
    reaction = scatter_add(xp, n, prescribed, residual[prescribed])
    gx = xp.sum(b * increment[tris], axis=1) / (2.0 * area)
    gy = xp.sum(c * increment[tris], axis=1) / (2.0 * area)
    field = -xp.stack([gx, gy], axis=1)
    current = sigma[:, None] * field
    heat = xp.sum(current * field, axis=1)
    load = scatter_add(xp, n, tris.ravel(), xp.reshape((heat * area / 3.0)[:, None]
                                                       * xp.ones((1, 3), dtype=xp.float64), (-1,)))
    power = xp.sum(area * heat)
    supplied = xp.sum(increment * (reaction - outward))
    return electric.SteadyElectricResult(base.mesh, potential, field, current, sigma, heat, load, power, reaction,
                                         outward, residual, supplied)


# ----------------------------------------------------------------------------- elasticity

def solve_elasticity_moving(mesh: Mesh, motion: MeshMotion, *, youngs_modulus, poisson_ratio, plane,
                            prescribed_displacement, body_force_density=(0.0, 0.0), traction=None):
    """``elasticity.solve_elasticity`` on X0 + t W with the derivative with respect to ``motion.t``.

    Internal (galerkin.kernels): reached through ``motion=``. The ordinary solve on the moved
    mesh gives the numbers and all checks; one live solve of the system assembled from the live
    coordinates (P1 strain matrices, element areas, the constant body force and the constant
    tractions on moving edges) attaches the derivative to the displacement, strain, stress, applied
    force, reaction and residual."""
    from . import elasticity

    young_modulus, dirichlet, body_force = youngs_modulus, prescribed_displacement, body_force_density
    xp, t = _live_t(motion.t)
    W = _velocity(mesh, motion.design_velocity)
    _check_elastic_data(young_modulus, poisson_ratio, body_force, traction, dirichlet)
    moved = _checked_step(mesh, W, t)
    base = elasticity.solve_elasticity(moved, youngs_modulus=young_modulus, poisson_ratio=poisson_ratio, plane=plane,
                                       prescribed_displacement=dirichlet, body_force_density=body_force,
                                       traction=traction)
    live = _elastic_live(xp, mesh, moved, t, W, young_modulus, poisson_ratio, plane, body_force, traction)
    load = live.body + live.line
    u, residual, reaction = _corrected(xp, live, base.displacement, load, dirichlet)
    strain = xp.einsum("tij,tj->ti", live.B, u[live.dofs])
    stress = strain @ live.d.T if live.d.ndim == 2 else xp.einsum("tij,tj->ti", live.d, strain)
    return elasticity.ElasticityResult(xp.reshape(u, (-1, 2)), strain, stress, xp.reshape(load, (-1, 2)),
                                       xp.reshape(reaction, (-1, 2)), xp.reshape(residual, (-1, 2)), plane)

# ----------------------------------------------------------------------------- transient heat

def solve_transient_heat_moving(mesh: Mesh, motion: MeshMotion, *, thermal_conductivity, volumetric_heat_capacity,
                                time, initial_temperature, prescribed_temperature, heat_source_density=0.0,
                                outward_heat_flux=None, convection=None, checkpoint_every=None,
                                coordinate_system="cartesian"):
    """``transient_heat.solve_transient_heat`` on X0 + t W with the derivative with respect to ``motion.t``.

    Internal (galerkin.kernels): reached through ``motion=``, after the public solver has
    negated the inward flux, so this takes the outward heat flux (positive leaves the body).

    The ordinary solve on the moved mesh gives the numbers and every step check. The
    initial temperatures and Dirichlet values stay attached to their nodes. Each
    backward-Euler step then gets one live correction x_n = x0_n + A(t)^-1 (b_n(t) - A(t) x0_n),
    with the mass, stiffness, Robin matrix and loads assembled from the live coordinates,
    so every history carries the derivative (decision 2026-11-10 for attached nodal data)."""
    from . import transient_heat
    from .core.triangles import triangle_geometry

    conductivity, time_s, initial_temperature_k, dirichlet, heat_source, outward_flux = (
        thermal_conductivity, time, initial_temperature, prescribed_temperature, heat_source_density,
        outward_heat_flux)
    xp, t = _live_t(motion.t)
    W = _velocity(mesh, motion.design_velocity)
    axisymmetric = _axisymmetric(mesh, W, coordinate_system, t)
    if checkpoint_every is not None:
        raise ValueError("motion: checkpoint_every is not supported with a motion in this slice; every step is "
                         "kept")
    _coefficient(conductivity, "thermal_conductivity")
    _coefficient(volumetric_heat_capacity, "volumetric_heat_capacity")
    _numpy_data(heat_source, "heat_source_density")
    if is_live(initial_temperature_k) or (isinstance(initial_temperature_k, (list, tuple))
                                          and any(is_live(v) for v in initial_temperature_k)):
        raise TypeError("motion: initial_temperature is live; in this slice only the motion's t carries a "
                        "derivative")
    if not isinstance(dirichlet, Mapping):
        raise ValueError("prescribed_temperature must map integer nodes to Kelvin values")
    for node, value in dirichlet.items():
        _time_only(value, "prescribed_temperature")
    tables = {}
    for name, table in (("outward_flux", outward_flux), ("convection", convection)):
        for tag, condition in _tags(table, name).items():
            values = condition if isinstance(condition, (tuple, list)) else (condition,)
            for value in values:
                _time_only(value, _boundary_label(name, tag))
        tables[name] = _tags(table, name)
    moved = _checked_step(mesh, W, t)
    base = transient_heat.solve_transient_heat_outward(
        moved, conductivity=conductivity, volumetric_heat_capacity=volumetric_heat_capacity, time_s=time_s,
        initial_temperature_k=initial_temperature_k, dirichlet=dirichlet, heat_source=heat_source,
        outward_flux=outward_flux, convection=convection, coordinate_system=coordinate_system)
    if is_live(base.temperature):
        raise TypeError("motion: a callback returned a JAX or PyTorch value; with a motion, callbacks of time "
                        "must return NumPy numbers (t is the one live input)")

    n = mesh.num_nodes
    tris = mesh.triangles
    times = np.asarray(base.time, dtype=float)
    fixed = np.asarray(base.prescribed_node_ids, dtype=int)
    bc_history = np.asarray(base.prescribed_temperature, dtype=float)
    initial = np.asarray(base.temperature[0], dtype=float)
    _p, _t, _area, _exterior, count, labels = triangle_geometry(mesh)
    representatives = np.array([np.flatnonzero(labels == c)[0] for c in range(count)])
    offsets = initial[representatives][labels]

    X = lift(xp, mesh.nodes) + t * lift(xp, W)
    b, c, area = _live_bc(xp, X, tris, np.sign(_signed_area(moved.nodes, tris)))
    k = _per_triangle(mesh, conductivity, "thermal_conductivity", positive=True)
    capacity = _per_triangle(mesh, volumetric_heat_capacity, "volumetric_heat_capacity", positive=True)
    Q = _per_triangle(mesh, heat_source, "heat_source_density")
    rows, cols = np.repeat(tris, 3, axis=1).ravel(), np.tile(tris, (1, 3)).ravel()
    stiff_e = lift(xp, k)[:, None, None] * (b[:, :, None] * b[:, None, :] + c[:, :, None] * c[:, None, :]) \
        / (4.0 * area)[:, None, None]
    if axisymmetric:
        stiff_e = stiff_e * _cell_factor(xp, X, tris)[:, None, None]
    mass_e = _cell_mass(xp, X, tris, area, lift(xp, capacity), axisymmetric)
    K = CooMatrix(rows, cols, xp.reshape(stiff_e, (-1,)), (n, n))
    M = CooMatrix(rows, cols, xp.reshape(mass_e, (-1,)), (n, n))
    load = scatter_add(xp, n, tris.ravel(), xp.reshape(_cell_load(xp, X, tris, area, lift(xp, Q), axisymmetric),
                                                       (-1,)))
    edges_of = {}
    for name in ("outward_flux", "convection"):
        for tag in tables[name]:
            if tag not in edges_of:
                edges_of[tag] = _boundary_edges(xp, mesh, X, tag)

    def at(value, now):
        return float(value(now)) if callable(value) else float(to_numpy(value))

    def natural(now):
        """Live (H terms, G, shifted B) of the boundary data at ``now``."""
        G = xp.zeros(n, dtype=xp.float64)
        shifted = xp.zeros(n, dtype=xp.float64)
        H_terms = []
        for tag, g in tables["outward_flux"].items():
            edges, length = edges_of[tag]
            G = scatter_add(xp, n, edges.ravel(), xp.reshape(_edge_load(xp, X, edges, length, at(g, now),
                                                                        axisymmetric), (-1,)), base=G)
        for tag, (h, ambient) in tables["convection"].items():
            edges, length = edges_of[tag]
            h_now, ambient_now = at(h, now), at(ambient, now)
            local = _edge_mass(xp, X, edges, length, h_now, axisymmetric)
            H_terms.append(CooMatrix(np.repeat(edges, 2, axis=1).ravel(), np.tile(edges, (1, 2)).ravel(),
                                     xp.reshape(local, (-1,)), (n, n)))
            shift = h_now * (ambient_now - offsets[edges[:, 0]])
            shifted = scatter_add(xp, n, edges.ravel(), xp.reshape(_edge_load(xp, X, edges, length,
                                                                              lift(xp, shift), axisymmetric),
                                                                   (-1,)), base=shifted)
        return H_terms, G, shifted

    has_natural = bool(tables["outward_flux"] or tables["convection"])
    offsets_l = lift(xp, offsets)

    def centered(values):
        return values - values[representatives][labels]

    def gradient_flux(increment):
        u = centered(increment)
        gx = xp.sum(b * u[tris], axis=1) / (2.0 * area)
        gy = xp.sum(c * u[tris], axis=1) / (2.0 * area)
        return -lift(xp, k)[:, None] * xp.stack([gx, gy], axis=1)

    def recorded(absolute, increment):
        mtemp = M.matvec(absolute)
        return absolute, gradient_flux(increment), xp.sum(mtemp), 0.5 * xp.sum(absolute * mtemp)

    first_abs = lift(xp, initial)
    history = {"T": [], "flux": [], "content": [], "quadratic": [], "storage": [], "residual": [],
               "reaction": [], "G": [], "C": []}
    for key, value in zip(("T", "flux", "content", "quadratic"), recorded(first_abs, first_abs - offsets_l)):
        history[key].append(value)
    previous = lift(xp, initial - offsets)
    mask = np.zeros(n, dtype=bool)
    mask[fixed] = True
    mask_l = lift(xp, mask)
    zero = xp.zeros(n, dtype=xp.float64)
    for index in range(1, len(times)):
        step = float(times[index] - times[index - 1])
        terms = [CooMatrix(M.rows, M.cols, M.values / step + K.values, (n, n))]
        rhs = load + M.matvec(previous) / step
        if has_natural:
            H_terms, G, shifted = natural(float(times[index]))
            terms += H_terms
            rhs = rhs + shifted - G
        x0 = lift(xp, np.asarray(base.temperature[index], dtype=float) - offsets)
        A_x0 = sum((term.matvec(x0) for term in terms[1:]), terms[0].matvec(x0))
        target = bc_history[index] - offsets[fixed] - to_numpy(x0)[fixed]
        delta = core_solve.solve_dirichlet(terms, rhs - A_x0, {tuple(fixed): target} if len(fixed) else {})
        current = x0 + delta
        stored = M.matvec((current - previous) / step)
        residual = stored + K.matvec(centered(current)) - load
        if has_natural:
            convective = sum((term.matvec(current) for term in H_terms), zero) - shifted
            residual = residual + convective + G
            history["G"].append(G)
            history["C"].append(convective)
        absolute = current + offsets_l
        for key, value in zip(("T", "flux", "content", "quadratic"), recorded(absolute, current)):
            history[key].append(value)
        history["storage"].append(stored)
        history["residual"].append(residual)
        history["reaction"].append(xp.where(mask_l, residual, zero))
        previous = current
    stack = xp.stack
    loads = stack([load] * len(times))
    extra = (stack(history["G"]), stack(history["C"])) if has_natural else ()
    result = transient_heat.AxisymmetricTransientHeatResult if axisymmetric else \
        transient_heat.PlanarTransientHeatResult
    return result(
        times, stack(history["T"]), stack(history["flux"]), loads, stack(history["reaction"]),
        stack(history["residual"]), stack(history["storage"]), stack(history["content"]),
        stack(history["quadratic"]), fixed, bc_history, np.asarray(base.node_coordinates),
        np.asarray(base.triangles), base.thermal_conductivity, base.volumetric_heat_capacity, *extra)


def _boundary_label(name, tag):
    """The message label of boundary data: the heat flux by its edge tag, as the public solvers take it
    inward and hand it here outward (so neither keyword names it), convection by its keyword."""
    return f"the heat flux on {tag!r}" if name == "outward_flux" else f"{name}[{tag!r}]"


def _time_only(value, name):
    """With a motion, a value is a constant or a callback of time alone (it does not depend on node positions)."""
    import inspect

    if not callable(value):
        _numpy_data(value, name, sampled=False)
        return
    try:
        parameters = list(inspect.signature(value).parameters.values())
    except (TypeError, ValueError):
        parameters = None
    required = None if parameters is None else [
        p for p in parameters if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) and p.default is p.empty]
    if required is not None and len(required) in (2, 3) and not any(p.kind is p.VAR_POSITIONAL for p in parameters):
        raise TypeError(f"motion: {name} is a callback of coordinates; with a moving mesh its sample points move "
                        "too, which this slice does not differentiate. Give a constant or a callback(time)")
    if required is None or len(required) != 1 or any(p.kind is p.VAR_POSITIONAL for p in parameters):
        raise TypeError(f"motion: {name} must be a constant or a callback(time) with one positional parameter")


# ----------------------------------------------------------------------------- thermoelasticity

def solve_thermoelasticity_moving(mesh: Mesh, temperature_snapshot, motion: MeshMotion, *, stress_free_temperature,
                                  linear_expansion_coefficient, youngs_modulus, poisson_ratio, plane,
                                  prescribed_displacement, body_force_density=(0.0, 0.0), traction=None):
    """``thermoelasticity.solve_thermoelasticity`` on X0 + t W with the derivative with respect to ``motion.t``.

    Internal (galerkin.kernels): reached through ``motion=``. The snapshot belongs to the mesh as
    given (X0) and is checked against it. Its nodal temperatures stay attached to their nodes as
    they move, as prescribed displacements do, so the derivative comes from the geometry alone
    (decision 2026-11-10)."""
    from . import thermoelasticity
    from .core.triangles import triangle_geometry

    reference_temperature_k, thermal_expansion_per_k = stress_free_temperature, linear_expansion_coefficient
    young_modulus, dirichlet, body_force = youngs_modulus, prescribed_displacement, body_force_density
    xp, t = _live_t(motion.t)
    W = _velocity(mesh, motion.design_velocity)
    _check_thermal_constants(reference_temperature_k, thermal_expansion_per_k)
    _check_elastic_data(young_modulus, poisson_ratio, body_force, traction, dirichlet)
    p, tris, *_ = triangle_geometry(mesh, counterclockwise=False)
    _mechanics.verify_snapshot(temperature_snapshot, p, tris)
    moved = _checked_step(mesh, W, t)
    base = thermoelasticity.solve_thermoelasticity(
        moved, thermoelasticity.freeze_temperature(moved, temperature=temperature_snapshot.temperature),
        stress_free_temperature=reference_temperature_k, linear_expansion_coefficient=thermal_expansion_per_k,
        youngs_modulus=young_modulus, poisson_ratio=poisson_ratio, plane=plane, prescribed_displacement=dirichlet,
        body_force_density=body_force, traction=traction)
    return _thermoelastic_live(xp, mesh, moved, t, W, base, lift(xp, np.array(temperature_snapshot.temperature)),
                               dirichlet, body_force, traction)


def solve_steady_thermoelasticity_moving(mesh: Mesh, motion: MeshMotion, *, thermal_conductivity,
                                         prescribed_temperature, heat_source_density=0.0, youngs_modulus,
                                         poisson_ratio, plane, linear_expansion_coefficient, stress_free_temperature,
                                         prescribed_displacement, body_force_density=(0.0, 0.0)):
    """``thermal_mechanical.solve_steady_thermoelasticity`` on X0 + t W, derivative with respect to ``motion.t``.

    Internal (galerkin.kernels): reached through ``motion=``. The ordinary workflow on the moved
    mesh gives the numbers, every stage check and the manifest. The heat stage is then solved again on the moving mesh (shape derivative of
    steady heat) and its live temperature drives the live mechanical stage, so the
    derivative includes the change of the temperature field (decision 2026-11-10)."""
    from . import thermal_mechanical
    from ._thermal_mechanical_common import dirichlet_supports

    conductivity, thermal_dirichlet, heat_source = thermal_conductivity, prescribed_temperature, heat_source_density
    young_modulus, mechanical_dirichlet, body_force = youngs_modulus, prescribed_displacement, body_force_density
    reference_temperature_k, thermal_expansion_per_k = stress_free_temperature, linear_expansion_coefficient
    xp, t = _live_t(motion.t)
    W = _velocity(mesh, motion.design_velocity)
    _coefficient(conductivity, "thermal_conductivity")
    _numpy_data(heat_source, "heat_source_density")
    _check_thermal_constants(reference_temperature_k, thermal_expansion_per_k)
    _check_elastic_data(young_modulus, poisson_ratio, body_force, None, mechanical_dirichlet)
    if not isinstance(thermal_dirichlet, Mapping):
        raise ValueError("prescribed_temperature must map node indices to temperatures in K")
    for value in thermal_dirichlet.values():
        _numpy_data(value, "prescribed_temperature", sampled=False)
    moved = _checked_step(mesh, W, t)
    base = thermal_mechanical.solve_steady_thermoelasticity(
        moved, thermal_conductivity=conductivity, prescribed_temperature=thermal_dirichlet,
        heat_source_density=heat_source, youngs_modulus=young_modulus, poisson_ratio=poisson_ratio, plane=plane,
        linear_expansion_coefficient=thermal_expansion_per_k, stress_free_temperature=reference_temperature_k,
        prescribed_displacement=mechanical_dirichlet, body_force_density=body_force)
    # The heat stage is solved once more here (the workflow's own heat result is NumPy); both solves take the
    # same inputs and agree to rounding. The snapshot and manifest stay those of the workflow above.
    heat = solve_steady_heat_moving(mesh, motion, thermal_conductivity=conductivity,
                                    prescribed_temperature=dirichlet_supports(thermal_dirichlet),
                                    heat_source_density=heat_source)
    mechanics = _thermoelastic_live(xp, mesh, moved, t, W, base.mechanics, heat.temperature,
                                    dirichlet_supports(mechanical_dirichlet, vector=True), body_force, None)
    return thermal_mechanical.SteadyThermoelasticResult(base.reference_mesh, heat, base.temperature_snapshot,
                                                        mechanics, base.manifest_json)


def _thermoelastic_live(xp, mesh, moved, t, W, base, temperature, dirichlet, body_force, traction):
    """The live mechanical stage for a nodal temperature (NumPy or live), corrected from ``base``."""
    from . import thermoelasticity

    e = base.youngs_modulus
    nu = base.poisson_ratio
    alpha = base.linear_expansion_coefficient
    tref = float(base.stress_free_temperature)
    plane = base.plane
    live = _elastic_live(xp, mesh, moved, t, W, e, nu, plane, body_force, traction)
    cells = mesh.num_triangles
    e_t, nu_t = (np.asarray(v, dtype=float) for v in _mechanics.element_materials(mesh, e, nu))
    alpha_t = _per_triangle(mesh, alpha, "linear_expansion_coefficient")
    coefficient = np.broadcast_to(_mechanics.thermal_coefficient(e_t, nu_t, plane), (cells,))
    a = lift(xp, alpha_t)[:, None] * (temperature[mesh.triangles] - tref)        # (T, 3) nodal values per element
    q = lift(xp, np.array(coefficient))[:, None] * a
    ac, qc = xp.mean(a, axis=1), xp.mean(q, axis=1)
    m_vector = lift(xp, _mechanics.ISOTROPIC_STRAIN)
    local = xp.einsum("tji,j,t->ti", live.B, m_vector, live.area * qc)
    thermal = scatter_add(xp, 2 * mesh.num_nodes, live.dofs.ravel(), xp.reshape(local, (-1,)))
    external = live.body + live.line
    load = external + thermal
    u, residual, reaction = _corrected(xp, live, base.displacement, load, dirichlet)
    strain = xp.einsum("tij,tj->ti", live.B, u[live.dofs])
    th = ac[:, None] * m_vector
    elastic = strain - th
    stress = (strain @ live.d.T if live.d.ndim == 2 else xp.einsum("tij,tj->ti", live.d, strain)) \
        - qc[:, None] * m_vector
    trace = strain[:, 0] + strain[:, 1]
    e_l, nu_l = (lift(xp, np.array(np.broadcast_to(v, (cells,)))) for v in (e_t, nu_t))
    if plane == "strain":
        zz = _mechanics.lame(e_l, nu_l, "strain")[0] * trace - qc
        ez = xp.zeros_like(qc)
    else:
        zz = xp.zeros_like(qc)
        ez = ((1 + nu_l) * ac - nu_l * trace) / (1 - nu_l)
    energy = _mechanics.physical_energy(xp, strain, a, live.area, live.d, e_l, nu_l, plane)
    return thermoelasticity.ThermoelasticResult(
        xp.reshape(u, (-1, 2)), strain, th, elastic, stress, zz, ez,
        *(xp.reshape(v, (-1, 2)) for v in (external, thermal, reaction, residual)),
        energy, base.temperature_snapshot, base.stress_free_temperature, base.linear_expansion_coefficient,
        base.youngs_modulus, base.poisson_ratio, plane, xp.reshape(live.body, (-1, 2)), xp.reshape(live.line, (-1, 2)))


@dataclass(frozen=True)
class _ElasticLive:
    B: object
    d: object
    area: object
    dofs: np.ndarray
    K: CooMatrix
    body: object
    line: object


def _elastic_live(xp, mesh, moved, t, W, young_modulus, poisson_ratio, plane, body_force, traction):
    """Live P1 strain matrices, constitutive matrix, stiffness, body and traction loads on X0 + t W."""
    n = mesh.num_nodes
    X = lift(xp, mesh.nodes) + t * lift(xp, W)
    tris = mesh.triangles
    b, c, area = _live_bc(xp, X, tris, np.sign(_signed_area(moved.nodes, tris)))
    gx, gy = b / (2.0 * area)[:, None], c / (2.0 * area)[:, None]
    zero = xp.zeros_like(gx)
    # B (T, 3, 6) with DOF order 2*node + component: rows exx, eyy, gamma_xy
    exx = xp.reshape(xp.stack([gx, zero], axis=2), (-1, 6))
    eyy = xp.reshape(xp.stack([zero, gy], axis=2), (-1, 6))
    gxy = xp.reshape(xp.stack([gy, gx], axis=2), (-1, 6))
    B = xp.stack([exx, eyy, gxy], axis=1)
    e, nu = _mechanics.element_materials(mesh, young_modulus, poisson_ratio)
    d = lift(xp, np.asarray(_mechanics.constitutive(np, np.asarray(e, dtype=float), np.asarray(nu, dtype=float),
                                                    plane)))
    if d.ndim == 2:
        ke = xp.einsum("tji,jk,tkl,t->til", B, d, B, area)
    else:
        ke = xp.einsum("tji,tjk,tkl,t->til", B, d, B, area)
    dofs = (2 * tris[:, :, None] + np.arange(2)).reshape(-1, 6)
    size = 2 * n
    K = CooMatrix(np.repeat(dofs, 6, axis=1).ravel(), np.tile(dofs, (1, 6)).ravel(), xp.reshape(ke, (-1,)),
                  (size, size))
    f = np.asarray(to_numpy(body_force), dtype=float).reshape(2)
    body = scatter_add(xp, size, dofs.ravel(),
                       xp.reshape((area / 3.0)[:, None, None] * lift(xp, np.broadcast_to(f, (1, 3, 2))), (-1,)))
    line = xp.zeros(size, dtype=xp.float64)
    for tag, value in _tags(traction, "traction").items():
        g = np.asarray(value, dtype=float).reshape(2)
        edges, length = _boundary_edges(xp, mesh, X, tag)
        edofs = (2 * edges[:, :, None] + np.arange(2)).reshape(-1)
        local = (length / 2.0)[:, None, None] * lift(xp, np.broadcast_to(g, (1, 2, 2)))
        line = scatter_add(xp, size, edofs, xp.reshape(local, (-1,)), base=line)
    return _ElasticLive(B, d, area, dofs, K, body, line)


def _corrected(xp, live, u_base, load, dirichlet):
    """u = u0 + K^-1 (load - K u0) with the fixed DOFs held; residual and reaction at the fixed DOFs."""
    size = live.K.shape[0]
    u0 = lift(xp, np.asarray(to_numpy(u_base), dtype=float).reshape(-1))
    fixed_dofs = np.array(sorted(2 * int(k[0]) + int(k[1]) for k in dirichlet), dtype=int)
    delta = core_solve.solve_dirichlet(live.K, load - live.K.matvec(u0),
                                       {tuple(fixed_dofs): 0.0} if len(fixed_dofs) else {})
    u = u0 + delta
    residual = live.K.matvec(u) - load
    mask = np.zeros(size, dtype=bool)
    mask[fixed_dofs] = True
    reaction = xp.where(lift(xp, mask), residual, xp.zeros_like(residual))
    return u, residual, reaction


def _check_elastic_data(young_modulus, poisson_ratio, body_force, traction, dirichlet):
    for name, value in (("youngs_modulus", young_modulus), ("poisson_ratio", poisson_ratio)):
        _coefficient(value, name)
    if callable(body_force):
        raise TypeError("motion: body_force_density is a callback; with a moving mesh its sample points move too, "
                        "which this slice does not differentiate. Give a constant (2,) vector")
    if is_live(body_force) or (isinstance(body_force, (tuple, list)) and any(is_live(v) for v in body_force)):
        raise TypeError("motion: body_force_density is live; in this slice only the motion's t carries a "
                        "derivative")
    for tag, value in _tags(traction, "traction").items():
        if callable(value):
            raise TypeError(f"motion: traction[{tag!r}] is a callback; with a moving mesh its sample points move "
                            "too, which this slice does not differentiate. Give a constant (2,) vector")
        if is_live(value) or (isinstance(value, (tuple, list)) and any(is_live(v) for v in value)):
            raise TypeError(f"motion: traction[{tag!r}] is live; in this slice only the motion's t carries a "
                            "derivative")
    if not isinstance(dirichlet, Mapping):
        raise ValueError("prescribed_displacement must map (node, component) to displacement in metres")
    for value in dirichlet.values():
        _numpy_data(value, "prescribed_displacement", sampled=False)


def _check_thermal_constants(reference_temperature_k, thermal_expansion_per_k):
    if callable(reference_temperature_k):
        raise _CoefficientCallbackRefused("motion: stress_free_temperature is a callback; with a motion it must "
                                          "be a finite nonnegative real scalar")
    if is_live(reference_temperature_k):
        raise TypeError("motion: stress_free_temperature is live; in this slice only the motion's t carries a "
                        "derivative")
    _coefficient(thermal_expansion_per_k, "linear_expansion_coefficient")


def _checked_step(mesh, W, t):
    """The moved NumPy mesh at the step t, refused when t is not finite or an element inverts."""
    from .shape import ElementInversion, admissible_interval

    t0 = float(to_numpy(t))
    if not math.isfinite(t0):
        raise ValueError(f"motion: t must be finite, got {t0!r}")
    lo, hi = admissible_interval(mesh, design_velocity=W)
    if not lo < t0 < hi:
        raise ElementInversion(f"motion: the step t = {t0:g} inverts an element (admissible interval "
                               f"({lo:g}, {hi:g}))")
    from .mesh3d import Mesh3D
    if isinstance(mesh, Mesh3D):
        # the cubic's roots are rounded: test the moved volumes themselves (same sign as at t = 0)
        p0, p1 = mesh.nodes[mesh.tets], (mesh.nodes + t0 * W)[mesh.tets]

        def volumes(p):
            return np.einsum("td,td->t", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))
        if np.any(volumes(p1) * np.sign(volumes(p0)) <= 0):
            raise ElementInversion(f"motion: the step t = {t0:g} inverts an element (a moved tetrahedron has "
                                   "zero or reversed volume)")
    return _moved_mesh(mesh, W, t0)

# ----------------------------------------------------------------------------- helpers

def _axisymmetric(mesh, W, coordinate_system, t):
    """True for an axisymmetric heat motion; nodes on the symmetry axis at the step t must stay on it."""
    if coordinate_system not in ("cartesian", "axisymmetric"):
        raise ValueError("coordinate_system must be 'cartesian' or 'axisymmetric'")
    if coordinate_system == "cartesian":
        return False
    t0 = float(to_numpy(t))
    if not math.isfinite(t0):
        return True                     # the step check refuses it by name
    on_axis = np.flatnonzero((mesh.nodes[:, 0] + t0 * W[:, 0]) == 0)
    moving = on_axis[W[on_axis, 0] != 0]
    if len(moving):
        raise ValueError(f"motion: the design velocity moves {len(moving)} node(s) on the symmetry axis off it "
                         f"(first {int(moving[0])}); its radial component must be 0 where r = 0 at the step t")
    return True


# int_T phi_i phi_j phi_m / |T| = a! b! c! / 60 for the multiplicities of the vertices (core.kernels has the
# same table for the NumPy mass); row m of the (3, 9) matrix holds the (i, j) entries of vertex m.
_CUBIC_MOMENTS = np.array([[math.prod(math.factorial(int(c)) for c in np.bincount([i, j, m], minlength=3)) / 60.0
                            for i in range(3) for j in range(3)] for m in range(3)])


def _cell_factor(xp, X, tris):
    """2 pi r at each live centroid: the exact cell factor of the axisymmetric stiffness (r linear)."""
    return 2.0 * math.pi * xp.sum(X[:, 0][tris], axis=1) / 3.0


def _cell_load(xp, X, tris, area, values, axisymmetric):
    """(T, 3) element loads of per-triangle constants: |T|/3 each, or the exact moment of 2 pi r."""
    if not axisymmetric:
        return (values * area / 3.0)[:, None] * xp.ones((1, 3), dtype=xp.float64)
    r = X[:, 0][tris]
    return (2.0 * math.pi * values * area / 12.0)[:, None] * (r + xp.sum(r, axis=1)[:, None])


def _cell_mass(xp, X, tris, area, capacity, axisymmetric):
    """(T, 3, 3) consistent element masses, with the exact cubic moments of 2 pi r when axisymmetric."""
    if not axisymmetric:
        return (capacity * area / 12.0)[:, None, None] * lift(xp, np.ones((3, 3)) + np.eye(3))[None]
    moments = xp.reshape(X[:, 0][tris] @ lift(xp, _CUBIC_MOMENTS), (-1, 3, 3))
    return (2.0 * math.pi * capacity * area)[:, None, None] * moments


def _edge_load(xp, X, edges, length, value, axisymmetric):
    """(E, 2) edge loads of constants: L/2 each, or the exact moment of 2 pi r."""
    if not axisymmetric:
        return (value * length / 2.0)[:, None] * xp.ones((1, 2), dtype=xp.float64)
    r = X[:, 0][edges]
    return (2.0 * math.pi * value * length / 6.0)[:, None] * (r + xp.sum(r, axis=1)[:, None])


def _edge_mass(xp, X, edges, length, h, axisymmetric):
    """(E, 2, 2) Robin edge matrices: h L [[2, 1], [1, 2]] / 6, or with the exact moments of 2 pi r."""
    if not axisymmetric:
        return h * length[:, None, None] * lift(xp, _EDGE_MASS)[None, :, :]
    ra, rb = X[:, 0][edges[:, 0]], X[:, 0][edges[:, 1]]
    m = xp.stack([xp.stack([3.0 * ra + rb, ra + rb], axis=1), xp.stack([ra + rb, ra + 3.0 * rb], axis=1)], axis=1)
    return (2.0 * math.pi * h * length / 12.0)[:, None, None] * m


def _tags(table, name):
    """A boundary-data table as a mapping; anything else gets the solver's own refusal."""
    if table is None:
        return {}
    if not isinstance(table, Mapping):
        raise ValueError(f"{name} must map boundary edge tags to conditions")
    return table


class _CoefficientCallbackRefused(TypeError, ValueError):
    """A coefficient callback refused with a motion. A TypeError, as every other callback refused with a
    motion (sources, boundary and Dirichlet values); also a ValueError, the type these refusals had
    before 2026-11-22, so existing ``except ValueError`` handlers keep catching it."""


def _coefficient(value, name):
    if callable(value):
        raise _CoefficientCallbackRefused(f"motion: {name} is a callback; with a motion it must be a finite real "
                                          "scalar or a table of region names")
    _numpy_data(value, name, sampled=False)


def _check_neumann_balance(mesh, W, moved, labels, count, anchored, dirichlet, outward_current):
    """Refuse a motion that changes the net imposed current of a component without Dirichlet
    volts: next to t0 that problem has no solution, so it has no derivative."""
    if all(anchored[k] and any(labels[n] == k for n in dirichlet) for k in range(count)):
        return
    rate = np.zeros(count)
    scale = np.zeros(count)
    for tag, g in (outward_current or {}).items():
        edges = np.asarray(mesh.boundary_edges[tag], dtype=int)
        e = moved.nodes[edges[:, 1]] - moved.nodes[edges[:, 0]]
        de = W[edges[:, 1]] - W[edges[:, 0]]
        dlen = np.sum(e * de, axis=1) / np.hypot(e[:, 0], e[:, 1])
        np.add.at(rate, labels[edges[:, 0]], float(g) * dlen)
        np.add.at(scale, labels[edges[:, 0]], abs(float(g) * dlen))
    for k in range(count):
        if any(labels[n] == k for n in dirichlet):
            continue
        if abs(rate[k]) > 1e-12 * max(scale[k], np.finfo(float).tiny) and scale[k] > 0:
            raise ValueError(f"motion: component {k} has inward_current_density data only, and the motion changes "
                             f"its net outward current (rate {rate[k]:g} A/m per unit t); next to t the problem has "
                             "no solution, so it has no derivative. Keep the current-carrying sides' lengths, or "
                             "give that component a prescribed_electric_potential")


def _live_t(t):
    if not is_live(t):
        raise TypeError("motion: t must be a JAX or PyTorch scalar; NumPy does not differentiate. To solve on a "
                        "moved mesh without a derivative, move the nodes and solve that mesh")
    xp = namespace(t)
    require_float64(xp, "motion: t")
    if tuple(getattr(t, "shape", ())) != ():
        raise ValueError("motion: t must be a scalar")
    dtype = str(t.dtype).removeprefix("torch.")
    if dtype.startswith("complex"):
        raise TypeError(f"motion: t must be a real float64 scalar, got {dtype}; the step of a mesh motion is "
                        "real, and a complex t would lose its imaginary part")
    if dtype != "float64":
        raise TypeError(f"motion: t must be a float64 scalar, got {dtype}; galerkin needs float64 and does not "
                        "promote t, since the derivative would then be taken in another precision. "
                        "Create t as float64")
    return xp, t


def _velocity(mesh: Mesh, velocity):
    if is_live(velocity):
        raise TypeError("motion: the mesh velocity is NumPy structure; only t is live")
    W = np.asarray(velocity, dtype=float)
    dim = mesh.nodes.shape[1]           # 2 for a Mesh, 3 for a Mesh3D
    if W.shape != (mesh.num_nodes, dim):
        raise ValueError(f"motion: velocity must have shape ({mesh.num_nodes}, {dim}), got {W.shape}")
    if not np.all(np.isfinite(W)):
        raise ValueError("motion: velocity must be finite")
    return W


def _numpy_data(value, name, *, sampled=True):
    """Refuse callbacks and live values with a motion. ``sampled``: the solver would call the callback at
    coordinates (sources, boundary data); otherwise it is a value callback (coefficients, Dirichlet values)."""
    if type(value).__name__ == "ElementHeatSource":
        raise TypeError(f"motion: {name} is an ElementHeatSource; give a scalar or a region table")
    items = value.values() if is_per_region(value) else (value if isinstance(value, (tuple, list)) else (value,))
    for v in (value, *items):
        if callable(v) and sampled:
            raise TypeError(f"motion: {name} is a callback; with a moving mesh its sample points move too, which "
                            "this slice does not differentiate. Give a scalar or a region table")
        if callable(v):
            raise TypeError(f"motion: {name} is a callback; with a motion this slice takes constants only "
                            "(t is the one live input)")
    for v in items:
        if is_live(v):
            raise TypeError(f"motion: {name} is live; in this slice only the motion's t carries a derivative")


def _per_triangle(mesh, value, label, *, positive=False):
    if is_per_region(value):
        return np.asarray(region_property(mesh, value, label, positive=positive), dtype=float)
    return np.full(mesh.num_triangles, float(value))


def _moved_mesh(mesh: Mesh, W, t0: float) -> Mesh:
    from .mesh3d import Mesh3D
    if isinstance(mesh, Mesh3D):
        # copies: Mesh3D keeps its arrays and reorients tetrahedra in place
        return Mesh3D(mesh.nodes + t0 * W, mesh.tets.copy(), mesh.boundary,
                      None if mesh.regions is None else mesh.regions.copy(), mesh.region_names,
                      mesh.tagged_faces or None, mesh.interfaces or None)
    return Mesh(mesh.nodes + t0 * W, mesh.triangles, mesh.boundary, mesh.boundary_edges, mesh.regions,
                mesh.region_names, mesh.provenance_edges, mesh.selection_edges)

def _cross(u, v):
    return u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]


def _signed_area(nodes, tris):
    p = nodes[tris]
    return 0.5 * _cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])


def _live_bc(xp, X, tris, orientation):
    x, y = X[:, 0], X[:, 1]
    x0, x1, x2 = (x[tris[:, i]] for i in range(3))
    y0, y1, y2 = (y[tris[:, i]] for i in range(3))
    b = xp.stack([y1 - y2, y2 - y0, y0 - y1], axis=1)
    c = xp.stack([x2 - x1, x0 - x2, x1 - x0], axis=1)
    area = lift(xp, orientation) * 0.5 * (b[:, 0] * c[:, 1] - b[:, 1] * c[:, 0])
    return b, c, area


def _boundary_edges(xp, mesh, X, tag):
    if tag not in mesh.boundary_edges:
        raise ValueError(f"motion: boundary tag {tag!r} has no boundary_edges definition")
    edges = np.asarray(mesh.boundary_edges[tag], dtype=int)
    d = X[edges[:, 1]] - X[edges[:, 0]]
    return edges, xp.sqrt(d[:, 0] * d[:, 0] + d[:, 1] * d[:, 1])


# The motion helpers galerkin.shape shares (package-private names; it imports them under underscores).
live_t, checked_velocity, checked_step, moved_mesh, signed_area, live_bc, cross = (
    _live_t, _velocity, _checked_step, _moved_mesh, _signed_area, _live_bc, _cross)
