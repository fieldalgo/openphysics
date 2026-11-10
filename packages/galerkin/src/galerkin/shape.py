# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Shape derivatives: derivatives with respect to a design parameter that moves the mesh.

A design parameter t moves every node: X(t) = X0 + t W, with a fixed NumPy mesh
velocity W of shape (N, 2) (metres of node motion per unit of t). Only t is live:
a JAX or PyTorch scalar whose number is the step at which the solve runs (usually
0, the mesh as given). The connectivity, tags and regions stay fixed, so the
derivative is the exact derivative of the discrete solution on the moving mesh.

- ``extend_velocity`` builds W from the velocities of the nodes on the geometry's
  curves (``simcase.geometry_velocity.DesignVelocity.node_velocity``): every other
  node moves by a harmonic extension of them.
- ``admissible_interval`` is the exact range of t over which no element inverts.
- ``MeshMotion(velocity, t)`` passed as ``motion=`` to a supported solver returns its
  result fields with their derivative with respect to t.

``motion=`` is taken by ``thermal.solve_steady_heat`` (Cartesian),
``electric.solve_steady_electric``, ``elasticity.solve_elasticity``,
``transient_heat.solve_transient_heat`` (Cartesian),
``thermoelasticity.solve_thermoelasticity`` and
``thermal_mechanical.solve_steady_thermoelasticity`` with scalar or region data and
constant loads; the refusals are listed in docs/packages/galerkin/shape_derivative.md.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from .core import solve as core_solve
from .core.backend import Backend, backend_of, is_live, lift, namespace, require_float64, scatter_add, to_numpy
from .core.materials import is_per_region, region_property
from .core.sparse import CooMatrix
from .mesh import Mesh

_EDGE_MASS = np.array([[2.0, 1.0], [1.0, 2.0]]) / 6.0


@dataclass(frozen=True)
class MeshMotion:
    """Nodes at X0 + t * velocity; ``t`` is a JAX or PyTorch scalar (the design parameter step)."""

    velocity: object
    t: object


class ElementInversion(ValueError):
    """The motion inverts an element at the requested step."""


def admissible_interval(mesh: Mesh, velocity) -> tuple[float, float]:
    """(t_lo, t_hi), t_lo < 0 < t_hi: the open interval of t in which every element of
    X0 + t W keeps its orientation. Each signed area is a quadratic in t; its nearest
    root on each side bounds the interval (inf when an element never inverts)."""
    W = _velocity(mesh, velocity)
    e1, e2, f1, f2 = _edges(mesh.nodes, W, mesh.triangles)
    a0 = _cross(e1, e2)
    a1 = _cross(e1, f2) + _cross(f1, e2)
    a2 = _cross(f1, f2)
    lo, hi = -math.inf, math.inf
    for c0, c1, c2 in zip(a0, a1, a2):
        for r in _real_roots(c2, c1, c0):
            if r > 0:
                hi = min(hi, r)
            elif r < 0:
                lo = max(lo, r)
    return lo, hi


def extend_velocity(mesh: Mesh, values, known, *, method: str = "harmonic"):
    """The (N, 2) mesh velocity that equals ``values`` on the ``known`` nodes.

    ``known`` is a boolean (N,) mask (the nodes on curves) and ``values`` an (N, 2)
    array (read on known nodes only). Every other node takes, per component, the
    solution of a Laplace problem on the mesh with those Dirichlet values:
    ``"harmonic"`` uses unit diffusivity; ``"stiffened"`` divides it by the element
    area, so small elements near curves move more rigidly. Known nodes must touch
    every connected component."""
    from scipy.sparse import coo_matrix

    from .core import kernels
    from .core.solve import scipy_solve_dirichlet

    values = np.asarray(values, dtype=float)
    known = np.asarray(known, dtype=bool)
    n = mesh.num_nodes
    if values.shape != (n, 2) or known.shape != (n,):
        raise ValueError(f"extend_velocity: values must be ({n}, 2) and known ({n},)")
    if not np.all(np.isfinite(values[known])):
        raise ValueError("extend_velocity: known values must be finite")
    if method == "harmonic":
        eps = 1.0
    elif method == "stiffened":
        area = mesh.areas()
        eps = float(np.mean(area)) / area
    else:
        raise ValueError(f"extend_velocity: method must be 'harmonic' or 'stiffened', not {method!r}")
    element = kernels.p1_stiffness(mesh, eps)
    rows = np.repeat(mesh.triangles, 3, axis=1).ravel()
    cols = np.tile(mesh.triangles, (1, 3)).ravel()
    K = coo_matrix((np.asarray(element).ravel(), (rows, cols)), shape=(n, n)).tocsr()
    fixed = np.flatnonzero(known)
    if not len(fixed):
        raise ValueError("extend_velocity: no known node")
    from scipy.sparse.csgraph import connected_components
    _count, labels = connected_components(K, directed=False)
    unanchored = sorted(set(labels.tolist()) - set(labels[fixed].tolist()))
    if unanchored:
        nodes = np.flatnonzero(np.isin(labels, unanchored))
        raise ValueError(f"extend_velocity: {len(unanchored)} connected component(s) have no known node "
                         f"(for example node {int(nodes[0])}); give every component at least one known node")
    out = np.empty((n, 2))
    for k in range(2):
        out[:, k] = scipy_solve_dirichlet(K, np.zeros(n), {(int(i),): values[i, k] for i in fixed})
    return out


# ----------------------------------------------------------------------------- steady heat

def solve_steady_heat_moving(mesh: Mesh, motion: MeshMotion, *, conductivity, dirichlet, heat_source=0.0,
                             outward_flux=None, convection=None, coordinate_system="cartesian"):
    """``thermal.solve_steady_heat`` on X0 + t W with the derivative with respect to ``motion.t``.

    The numbers come from the ordinary solve on the moved mesh, with all its checks;
    the derivative is attached by one more live solve of the system assembled from
    the live node coordinates: T = T0 + A(t)^-1 (b(t) - A(t) T0), equal to T0 up to
    rounding."""
    from . import thermal

    xp, t = _live_t(motion.t)
    W = _velocity(mesh, motion.velocity)
    if coordinate_system != "cartesian":
        raise ValueError("motion: shape derivatives cover Cartesian heat in this slice; axisymmetric is refused")
    _coefficient(conductivity, "conductivity")
    _numpy_data(heat_source, "heat_source")
    for name, table in (("outward_flux", outward_flux), ("convection", convection)):
        for tag, value in _tags(table, name).items():
            _numpy_data(value, f"{name}[{tag!r}]")
    if not isinstance(dirichlet, Mapping):
        raise ValueError("dirichlet must map node indices to temperatures in K")
    for node, value in dirichlet.items():
        _numpy_data(value, "Dirichlet temperature", sampled=False)
    t0 = float(to_numpy(t))
    if not math.isfinite(t0):
        raise ValueError(f"motion: t must be finite, got {t0!r}")
    lo, hi = admissible_interval(mesh, W)
    if not lo < t0 < hi:
        raise ElementInversion(f"motion: the step t = {t0:g} inverts an element (admissible interval "
                               f"({lo:g}, {hi:g}))")
    moved = _moved_mesh(mesh, W, t0)
    base = thermal.solve_steady_heat(moved, conductivity=conductivity, dirichlet=dirichlet, heat_source=heat_source,
                                     outward_flux=outward_flux, convection=convection)
    n = mesh.num_nodes
    X = lift(xp, mesh.nodes) + t * lift(xp, W)
    tris = mesh.triangles
    b, c, area = _live_bc(xp, X, tris, np.sign(_signed_area(moved.nodes, tris)))
    k = _per_triangle(mesh, conductivity, "conductivity", positive=True)
    Q = _per_triangle(mesh, heat_source, "heat_source")
    kk = lift(xp, k)[:, None, None]
    element = kk * (b[:, :, None] * b[:, None, :] + c[:, :, None] * c[:, None, :]) / (4.0 * area)[:, None, None]
    K = CooMatrix(np.repeat(tris, 3, axis=1).ravel(), np.tile(tris, (1, 3)).ravel(),
                  xp.reshape(element, (-1,)), (n, n))
    load = scatter_add(xp, n, tris.ravel(), xp.reshape((lift(xp, Q) * area / 3.0)[:, None] * xp.ones((1, 3),
                                                       dtype=xp.float64), (-1,)))
    H_terms, B, G = [], None, None
    for tag, g in (outward_flux or {}).items():
        edges, length = _boundary_edges(xp, mesh, X, tag)
        G = scatter_add(xp, n, edges.ravel(), xp.reshape((float(g) * length / 2.0)[:, None]
                                                          * xp.ones((1, 2), dtype=xp.float64), (-1,)), base=G)
    for tag, (h, ambient) in (convection or {}).items():
        edges, length = _boundary_edges(xp, mesh, X, tag)
        local = float(h) * length[:, None, None] * lift(xp, _EDGE_MASS)[None, :, :]
        H_terms.append(CooMatrix(np.repeat(edges, 2, axis=1).ravel(), np.tile(edges, (1, 2)).ravel(),
                                 xp.reshape(local, (-1,)), (n, n)))
        B = scatter_add(xp, n, edges.ravel(), xp.reshape((float(h) * float(ambient) * length / 2.0)[:, None]
                                                         * xp.ones((1, 2), dtype=xp.float64), (-1,)), base=B)
    zero = xp.zeros(n, dtype=xp.float64)
    G = zero if G is None else G
    B = zero if B is None else B
    rhs = load + B - G
    terms = [K, *H_terms]
    T0 = lift(xp, base.temperature)
    A_T0 = sum((term.matvec(T0) for term in terms[1:]), terms[0].matvec(T0))
    fixed = {(int(node),): 0.0 for node in dirichlet}
    delta = core_solve.solve_dirichlet(terms, rhs - A_T0, fixed)
    temperature = T0 + delta
    A_T = sum((term.matvec(temperature) for term in terms[1:]), terms[0].matvec(temperature))
    residual = A_T - rhs
    convective = (sum((term.matvec(temperature) for term in terms[1:]), zero) - B) if H_terms else zero
    fixed_nodes = np.array(sorted(int(i) for i in dirichlet), dtype=int)
    reaction = scatter_add(xp, n, fixed_nodes, residual[fixed_nodes])
    grad_x = xp.sum(b * temperature[tris], axis=1) / (2.0 * area)
    grad_y = xp.sum(c * temperature[tris], axis=1) / (2.0 * area)
    flux = -lift(xp, k)[:, None] * xp.stack([grad_x, grad_y], axis=1)
    return thermal.SteadyHeatResult(temperature, flux, load, reaction, residual, G, B, convective, rhs,
                                    "cartesian", base.nodal_heat_rate_unit)


# ----------------------------------------------------------------------------- steady electric

def solve_steady_electric_moving(mesh: Mesh, motion: MeshMotion, *, conductivity, dirichlet, outward_current=None,
                                 reference_potential=None):
    """``electric.solve_steady_electric`` on X0 + t W with the derivative with respect to ``motion.t``.

    As for heat: the ordinary solve on the moved mesh gives the numbers and all checks,
    and one live solve of the system assembled from the live coordinates attaches the
    derivative to every result field."""
    from . import electric

    xp, t = _live_t(motion.t)
    W = _velocity(mesh, motion.velocity)
    if type(conductivity).__name__ == "ElementConductivity":
        raise TypeError("motion: conductivity is an ElementConductivity; give a scalar or a region table")
    _coefficient(conductivity, "conductivity")
    for tag, value in _tags(outward_current, "outward_current").items():
        _numpy_data(value, f"outward_current[{tag!r}]")
    for name, table in (("dirichlet", dirichlet), ("reference_potential", reference_potential or {})):
        if not isinstance(table, Mapping):
            raise ValueError(f"{name} must map node indices to scalar volts")
        for value in table.values():
            _numpy_data(value, name, sampled=False)
    t0 = float(to_numpy(t))
    if not math.isfinite(t0):
        raise ValueError(f"motion: t must be finite, got {t0!r}")
    lo, hi = admissible_interval(mesh, W)
    if not lo < t0 < hi:
        raise ElementInversion(f"motion: the step t = {t0:g} inverts an element (admissible interval "
                               f"({lo:g}, {hi:g}))")
    moved = _moved_mesh(mesh, W, t0)
    base = electric.solve_steady_electric(moved, conductivity=conductivity, dirichlet=dirichlet,
                                          outward_current=outward_current, reference_potential=reference_potential)
    n = mesh.num_nodes
    X = lift(xp, mesh.nodes) + t * lift(xp, W)
    tris = mesh.triangles
    b, c, area = _live_bc(xp, X, tris, np.sign(_signed_area(moved.nodes, tris)))
    sigma = lift(xp, _per_triangle(mesh, conductivity, "conductivity", positive=True))
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
    I0 = lift(xp, np.asarray(base.potential) - offsets[labels])
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

def solve_elasticity_moving(mesh: Mesh, motion: MeshMotion, *, young_modulus, poisson_ratio, plane, dirichlet,
                            body_force=(0.0, 0.0), traction=None):
    """``elasticity.solve_elasticity`` on X0 + t W with the derivative with respect to ``motion.t``.

    The ordinary solve on the moved mesh gives the numbers and all checks; one live solve
    of the system assembled from the live coordinates (P1 strain matrices, element areas,
    the constant body force and the constant tractions on moving edges) attaches the
    derivative to the displacement, strain, stress, load, reaction and residual."""
    from . import elasticity

    xp, t = _live_t(motion.t)
    W = _velocity(mesh, motion.velocity)
    _check_elastic_data(young_modulus, poisson_ratio, body_force, traction, dirichlet)
    moved = _checked_step(mesh, W, t)
    base = elasticity.solve_elasticity(moved, young_modulus=young_modulus, poisson_ratio=poisson_ratio, plane=plane,
                                       dirichlet=dirichlet, body_force=body_force, traction=traction)
    live = _elastic_live(xp, mesh, moved, t, W, young_modulus, poisson_ratio, plane, body_force, traction)
    load = live.body + live.line
    u, residual, reaction = _corrected(xp, live, base.displacement, load, dirichlet)
    strain = xp.einsum("tij,tj->ti", live.B, u[live.dofs])
    stress = strain @ live.d.T if live.d.ndim == 2 else xp.einsum("tij,tj->ti", live.d, strain)
    return elasticity.ElasticityResult(xp.reshape(u, (-1, 2)), strain, stress, xp.reshape(load, (-1, 2)),
                                       xp.reshape(reaction, (-1, 2)), xp.reshape(residual, (-1, 2)), plane)


# ----------------------------------------------------------------------------- transient heat

def solve_transient_heat_moving(mesh: Mesh, motion: MeshMotion, *, conductivity, volumetric_heat_capacity, time_s,
                                initial_temperature_k, dirichlet, heat_source=0.0, outward_flux=None, convection=None,
                                checkpoint_every=None, coordinate_system="cartesian"):
    """``transient_heat.solve_transient_heat`` on X0 + t W with the derivative with respect to ``motion.t``.

    The ordinary solve on the moved mesh gives the numbers and every step check. The
    initial temperatures and Dirichlet values stay attached to their nodes. Each
    backward-Euler step then gets one live correction x_n = x0_n + A(t)^-1 (b_n(t) - A(t) x0_n),
    with the mass, stiffness, Robin matrix and loads assembled from the live coordinates,
    so every history carries the derivative (decision 2026-11-10 for attached nodal data)."""
    from . import transient_heat
    from .core.triangles import triangle_geometry

    xp, t = _live_t(motion.t)
    W = _velocity(mesh, motion.velocity)
    if coordinate_system != "cartesian":
        raise ValueError("motion: shape derivatives cover Cartesian transient heat in this slice; axisymmetric "
                         "is refused")
    if checkpoint_every is not None:
        raise ValueError("motion: checkpoint_every is not supported with a motion in this slice; every step is "
                         "kept")
    _coefficient(conductivity, "conductivity")
    _coefficient(volumetric_heat_capacity, "volumetric_heat_capacity")
    _numpy_data(heat_source, "heat_source")
    if is_live(initial_temperature_k) or (isinstance(initial_temperature_k, (list, tuple))
                                          and any(is_live(v) for v in initial_temperature_k)):
        raise TypeError("motion: initial_temperature_k is live; in this slice only the motion's t carries a "
                        "derivative")
    if not isinstance(dirichlet, Mapping):
        raise ValueError("dirichlet must map integer nodes to Kelvin values")
    for node, value in dirichlet.items():
        _time_only(value, "Dirichlet temperature")
    tables = {}
    for name, table in (("outward_flux", outward_flux), ("convection", convection)):
        for tag, condition in _tags(table, name).items():
            values = condition if isinstance(condition, (tuple, list)) else (condition,)
            for value in values:
                _time_only(value, f"{name}[{tag!r}]")
        tables[name] = _tags(table, name)
    moved = _checked_step(mesh, W, t)
    base = transient_heat.solve_transient_heat(
        moved, conductivity=conductivity, volumetric_heat_capacity=volumetric_heat_capacity, time_s=time_s,
        initial_temperature_k=initial_temperature_k, dirichlet=dirichlet, heat_source=heat_source,
        outward_flux=outward_flux, convection=convection)
    if is_live(base.temperature_k):
        raise TypeError("motion: a callback returned a JAX or PyTorch value; with a motion, callbacks of time "
                        "must return NumPy numbers (t is the one live input)")

    n = mesh.num_nodes
    tris = mesh.triangles
    times = np.asarray(base.time_s, dtype=float)
    fixed = np.asarray(base.dirichlet_node_ids, dtype=int)
    bc_history = np.asarray(base.dirichlet_temperatures_k, dtype=float)
    initial = np.asarray(base.temperature_k[0], dtype=float)
    _p, _t, _area, _exterior, count, labels = triangle_geometry(mesh)
    representatives = np.array([np.flatnonzero(labels == c)[0] for c in range(count)])
    offsets = initial[representatives][labels]

    X = lift(xp, mesh.nodes) + t * lift(xp, W)
    b, c, area = _live_bc(xp, X, tris, np.sign(_signed_area(moved.nodes, tris)))
    k = _per_triangle(mesh, conductivity, "conductivity", positive=True)
    capacity = _per_triangle(mesh, volumetric_heat_capacity, "volumetric_heat_capacity", positive=True)
    Q = _per_triangle(mesh, heat_source, "heat_source")
    rows, cols = np.repeat(tris, 3, axis=1).ravel(), np.tile(tris, (1, 3)).ravel()
    stiff_e = lift(xp, k)[:, None, None] * (b[:, :, None] * b[:, None, :] + c[:, :, None] * c[:, None, :]) \
        / (4.0 * area)[:, None, None]
    mass_e = (lift(xp, capacity) * area / 12.0)[:, None, None] * lift(xp, np.ones((3, 3)) + np.eye(3))[None]
    K = CooMatrix(rows, cols, xp.reshape(stiff_e, (-1,)), (n, n))
    M = CooMatrix(rows, cols, xp.reshape(mass_e, (-1,)), (n, n))
    load = scatter_add(xp, n, tris.ravel(), xp.reshape((lift(xp, Q) * area / 3.0)[:, None]
                                                       * xp.ones((1, 3), dtype=xp.float64), (-1,)))
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
            G = scatter_add(xp, n, edges.ravel(), xp.reshape((at(g, now) * length / 2.0)[:, None]
                                                             * xp.ones((1, 2), dtype=xp.float64), (-1,)), base=G)
        for tag, (h, ambient) in tables["convection"].items():
            edges, length = edges_of[tag]
            h_now, ambient_now = at(h, now), at(ambient, now)
            local = h_now * length[:, None, None] * lift(xp, _EDGE_MASS)[None, :, :]
            H_terms.append(CooMatrix(np.repeat(edges, 2, axis=1).ravel(), np.tile(edges, (1, 2)).ravel(),
                                     xp.reshape(local, (-1,)), (n, n)))
            shift = h_now * (ambient_now - offsets[edges[:, 0]])
            shifted = scatter_add(xp, n, edges.ravel(), xp.reshape((lift(xp, shift) * length / 2.0)[:, None]
                                                                   * xp.ones((1, 2), dtype=xp.float64), (-1,)),
                                  base=shifted)
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
        x0 = lift(xp, np.asarray(base.temperature_k[index], dtype=float) - offsets)
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
    return transient_heat.TransientHeatResult(
        times, stack(history["T"]), stack(history["flux"]), loads, stack(history["reaction"]),
        stack(history["residual"]), stack(history["storage"]), stack(history["content"]),
        stack(history["quadratic"]), fixed, bc_history, np.asarray(base.nodes_m), np.asarray(base.triangles),
        base.conductivity_w_mk, base.volumetric_heat_capacity_j_m3k, *extra,
        coordinate_system="cartesian", nodal_rate_unit=base.nodal_rate_unit)


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
                        "too, which this slice does not differentiate. Give a constant or a callback(time_s)")
    if required is None or len(required) != 1 or any(p.kind is p.VAR_POSITIONAL for p in parameters):
        raise TypeError(f"motion: {name} must be a constant or a callback(time_s) with one positional parameter")


# ----------------------------------------------------------------------------- thermoelasticity

def solve_thermoelasticity_moving(mesh: Mesh, temperature_snapshot, motion: MeshMotion, *, reference_temperature_k,
                                  thermal_expansion_per_k, young_modulus, poisson_ratio, plane, dirichlet,
                                  body_force=(0.0, 0.0), traction=None):
    """``thermoelasticity.solve_thermoelasticity`` on X0 + t W with the derivative with respect to ``motion.t``.

    The snapshot belongs to the mesh as given (X0) and is checked against it. Its nodal
    temperatures stay attached to their nodes as they move, as Dirichlet displacements do,
    so the derivative comes from the geometry alone (decision 2026-11-10)."""
    from . import thermoelasticity
    from .core.triangles import triangle_geometry

    xp, t = _live_t(motion.t)
    W = _velocity(mesh, motion.velocity)
    _check_thermal_constants(reference_temperature_k, thermal_expansion_per_k)
    _check_elastic_data(young_modulus, poisson_ratio, body_force, traction, dirichlet)
    p, tris, *_ = triangle_geometry(mesh, counterclockwise=False)
    thermoelasticity.verify_snapshot(temperature_snapshot, p, tris)
    moved = _checked_step(mesh, W, t)
    base = thermoelasticity.solve_thermoelasticity(
        moved, thermoelasticity.freeze_temperature(moved, temperature_snapshot.temperature_k),
        reference_temperature_k=reference_temperature_k, thermal_expansion_per_k=thermal_expansion_per_k,
        young_modulus=young_modulus, poisson_ratio=poisson_ratio, plane=plane, dirichlet=dirichlet,
        body_force=body_force, traction=traction)
    return _thermoelastic_live(xp, mesh, moved, t, W, base, lift(xp, np.array(temperature_snapshot.temperature_k)),
                               dirichlet, body_force, traction)


def solve_steady_thermoelasticity_moving(mesh: Mesh, motion: MeshMotion, *, units, conductivity, thermal_dirichlet,
                                         heat_source=0.0, young_modulus, poisson_ratio, plane,
                                         thermal_expansion_per_k, reference_temperature_k, mechanical_dirichlet,
                                         body_force=(0.0, 0.0)):
    """``thermal_mechanical.solve_steady_thermoelasticity`` on X0 + t W, derivative with respect to ``motion.t``.

    The ordinary workflow on the moved mesh gives the numbers, every stage check and the
    manifest. The heat stage is then solved again on the moving mesh (shape derivative of
    steady heat) and its live temperature drives the live mechanical stage, so the
    derivative includes the change of the temperature field (decision 2026-11-10)."""
    from . import thermal_mechanical
    from ._thermal_mechanical_common import dirichlet_supports

    xp, t = _live_t(motion.t)
    W = _velocity(mesh, motion.velocity)
    _coefficient(conductivity, "conductivity")
    _numpy_data(heat_source, "heat_source")
    _check_thermal_constants(reference_temperature_k, thermal_expansion_per_k)
    _check_elastic_data(young_modulus, poisson_ratio, body_force, None, mechanical_dirichlet)
    if not isinstance(thermal_dirichlet, Mapping):
        raise ValueError("thermal_dirichlet must map node indices to temperatures in K")
    for value in thermal_dirichlet.values():
        _numpy_data(value, "Dirichlet temperature", sampled=False)
    moved = _checked_step(mesh, W, t)
    base = thermal_mechanical.solve_steady_thermoelasticity(
        moved, units=units, conductivity=conductivity, thermal_dirichlet=thermal_dirichlet, heat_source=heat_source,
        young_modulus=young_modulus, poisson_ratio=poisson_ratio, plane=plane,
        thermal_expansion_per_k=thermal_expansion_per_k, reference_temperature_k=reference_temperature_k,
        mechanical_dirichlet=mechanical_dirichlet, body_force=body_force)
    # The heat stage is solved once more here (the workflow's own heat result is NumPy); both solves take the
    # same inputs and agree to rounding. The snapshot and manifest stay those of the workflow above.
    heat = solve_steady_heat_moving(mesh, motion, conductivity=conductivity,
                                    dirichlet=dirichlet_supports(thermal_dirichlet), heat_source=heat_source)
    mechanics = _thermoelastic_live(xp, mesh, moved, t, W, base.mechanics, heat.temperature,
                                    dirichlet_supports(mechanical_dirichlet, vector=True), body_force, None)
    return thermal_mechanical.SteadyThermoelasticResult(base.reference_mesh, heat, base.temperature_snapshot,
                                                        mechanics, base.manifest_json)


def _thermoelastic_live(xp, mesh, moved, t, W, base, temperature, dirichlet, body_force, traction):
    """The live mechanical stage for a nodal temperature (NumPy or live), corrected from ``base``."""
    from . import elasticity, thermoelasticity

    e = base.young_modulus
    nu = base.poisson_ratio
    alpha = base.thermal_expansion_per_k
    tref = float(base.reference_temperature_k)
    plane = base.plane
    live = _elastic_live(xp, mesh, moved, t, W, e, nu, plane, body_force, traction)
    cells = mesh.num_triangles
    e_t, nu_t = (np.asarray(v, dtype=float) for v in elasticity.element_materials(mesh, e, nu))
    alpha_t = _per_triangle(mesh, alpha, "thermal_expansion_per_k")
    coefficient = np.broadcast_to(thermoelasticity.thermal_coefficient(e_t, nu_t, plane), (cells,))
    a = lift(xp, alpha_t)[:, None] * (temperature[mesh.triangles] - tref)        # (T, 3) nodal values per element
    q = lift(xp, np.array(coefficient))[:, None] * a
    ac, qc = xp.mean(a, axis=1), xp.mean(q, axis=1)
    m_vector = lift(xp, thermoelasticity.ISOTROPIC_STRAIN)
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
        zz = elasticity.lame(e_l, nu_l, "strain")[0] * trace - qc
        ez = xp.zeros_like(qc)
    else:
        zz = xp.zeros_like(qc)
        ez = ((1 + nu_l) * ac - nu_l * trace) / (1 - nu_l)
    energy = thermoelasticity.physical_energy(xp, strain, a, live.area, live.d, e_l, nu_l, plane)
    return thermoelasticity.ThermoelasticResult(
        xp.reshape(u, (-1, 2)), strain, th, elastic, stress, zz, ez,
        *(xp.reshape(v, (-1, 2)) for v in (external, thermal, reaction, residual)),
        energy, base.temperature_snapshot, base.reference_temperature_k, base.thermal_expansion_per_k,
        base.young_modulus, base.poisson_ratio, plane, xp.reshape(live.body, (-1, 2)), xp.reshape(live.line, (-1, 2)))


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
    from . import elasticity

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
    e, nu = elasticity.element_materials(mesh, young_modulus, poisson_ratio)
    d = lift(xp, np.asarray(elasticity.constitutive(np, np.asarray(e, dtype=float), np.asarray(nu, dtype=float),
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
    for name, value in (("young_modulus", young_modulus), ("poisson_ratio", poisson_ratio)):
        _coefficient(value, name)
    if callable(body_force):
        raise TypeError("motion: body_force is a callback; with a moving mesh its sample points move too, which "
                        "this slice does not differentiate. Give a constant (2,) vector")
    if is_live(body_force) or (isinstance(body_force, (tuple, list)) and any(is_live(v) for v in body_force)):
        raise TypeError("motion: body_force is live; in this slice only the motion's t carries a derivative")
    for tag, value in _tags(traction, "traction").items():
        if callable(value):
            raise TypeError(f"motion: traction[{tag!r}] is a callback; with a moving mesh its sample points move "
                            "too, which this slice does not differentiate. Give a constant (2,) vector")
        if is_live(value) or (isinstance(value, (tuple, list)) and any(is_live(v) for v in value)):
            raise TypeError(f"motion: traction[{tag!r}] is live; in this slice only the motion's t carries a "
                            "derivative")
    if not isinstance(dirichlet, Mapping):
        raise ValueError("dirichlet must map (node, component) to displacement in metres")
    for value in dirichlet.values():
        _numpy_data(value, "Dirichlet displacement", sampled=False)


def _check_thermal_constants(reference_temperature_k, thermal_expansion_per_k):
    if callable(reference_temperature_k):
        raise ValueError("motion: reference_temperature_k is a callback; with a motion it must be a finite "
                         "nonnegative real scalar")
    if is_live(reference_temperature_k):
        raise TypeError("motion: reference_temperature_k is live; in this slice only the motion's t carries a "
                        "derivative")
    _coefficient(thermal_expansion_per_k, "thermal_expansion_per_k")


def _checked_step(mesh, W, t):
    """The moved NumPy mesh at the step t, refused when t is not finite or an element inverts."""
    t0 = float(to_numpy(t))
    if not math.isfinite(t0):
        raise ValueError(f"motion: t must be finite, got {t0!r}")
    lo, hi = admissible_interval(mesh, W)
    if not lo < t0 < hi:
        raise ElementInversion(f"motion: the step t = {t0:g} inverts an element (admissible interval "
                               f"({lo:g}, {hi:g}))")
    return _moved_mesh(mesh, W, t0)


# ----------------------------------------------------------------------------- helpers

def _tags(table, name):
    """A boundary-data table as a mapping; anything else gets the solver's own refusal."""
    if table is None:
        return {}
    if not isinstance(table, Mapping):
        raise ValueError(f"{name} must map boundary edge tags to conditions")
    return table


def _coefficient(value, name):
    if callable(value):
        raise ValueError(f"motion: {name} is a callback; with a motion it must be a finite real scalar or a table "
                         "of region names")
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
            raise ValueError(f"motion: component {k} has current data only, and the motion changes its net "
                             f"imposed current (rate {rate[k]:g} A/m per unit t); next to t the problem has no "
                             "solution, so it has no derivative. Keep the current-carrying sides' lengths, or "
                             "fix a Dirichlet volt on that component")


def _live_t(t):
    if not is_live(t):
        raise TypeError("motion: t must be a JAX or PyTorch scalar; NumPy does not differentiate. To solve on a "
                        "moved mesh without a derivative, move the nodes and solve that mesh")
    xp = namespace(t)
    require_float64(xp, "motion: t")
    if tuple(getattr(t, "shape", ())) != ():
        raise ValueError("motion: t must be a scalar")
    return xp, xp.astype(t, xp.float64) if backend_of(xp) is not Backend.NUMPY else t


def _velocity(mesh: Mesh, velocity):
    if is_live(velocity):
        raise TypeError("motion: the mesh velocity is NumPy structure; only t is live")
    W = np.asarray(velocity, dtype=float)
    if W.shape != (mesh.num_nodes, 2):
        raise ValueError(f"motion: velocity must have shape ({mesh.num_nodes}, 2), got {W.shape}")
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
    return Mesh(mesh.nodes + t0 * W, mesh.triangles, mesh.boundary, mesh.boundary_edges, mesh.regions,
                mesh.region_names, mesh.provenance_edges, mesh.selection_edges)


def _cross(u, v):
    return u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]


def _edges(nodes, W, tris):
    p, w = nodes[tris], W[tris]
    return p[:, 1] - p[:, 0], p[:, 2] - p[:, 0], w[:, 1] - w[:, 0], w[:, 2] - w[:, 0]


def _signed_area(nodes, tris):
    p = nodes[tris]
    return 0.5 * _cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])


def _real_roots(a, b, c):
    """Real roots of a t^2 + b t + c (c, the area at t = 0, is nonzero)."""
    # no relative threshold on a: a, b and c carry different powers of t, and the stable
    # formula below gives both roots accurately however small a is (review 2026-11-09)
    if a == 0:
        return [] if b == 0 else [-c / b]
    disc = b * b - 4 * a * c
    if disc < 0:
        return []
    s = math.sqrt(disc)
    q = -0.5 * (b + math.copysign(s, b))
    return [q / a, c / q] if q != 0 else [0.0]


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
