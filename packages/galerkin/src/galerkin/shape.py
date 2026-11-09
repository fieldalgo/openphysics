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
- ``MeshMotion(velocity, t)`` passed as ``motion=`` to ``thermal.solve_steady_heat``
  returns the temperature, flux, loads and reactions with their derivative with
  respect to t.

The first slice covers steady Cartesian heat with scalar or region data; the
refusals are listed in docs/packages/galerkin/shape_derivative.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .core import solve as core_solve
from .core.backend import Backend, backend_of, is_live, lift, namespace, scatter_add, to_numpy
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
    for name, value in (("conductivity", conductivity), ("heat_source", heat_source)):
        _numpy_data(value, name)
    for name, table in (("outward_flux", outward_flux), ("convection", convection)):
        for tag, value in (table or {}).items():
            _numpy_data(value, f"{name}[{tag!r}]")
    for node, value in dirichlet.items():
        _numpy_data(value, "Dirichlet temperature")
    t0 = float(to_numpy(t))
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


# ----------------------------------------------------------------------------- helpers

def _live_t(t):
    if not is_live(t):
        raise TypeError("motion: t must be a JAX or PyTorch scalar; NumPy does not differentiate. To solve on a "
                        "moved mesh without a derivative, move the nodes and solve that mesh")
    xp = namespace(t)
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


def _numpy_data(value, name):
    if callable(value):
        raise TypeError(f"motion: {name} is a callback; with a moving mesh its sample points move too, which this "
                        "slice does not differentiate. Give a scalar or a region table")
    if type(value).__name__ == "ElementHeatSource":
        raise TypeError(f"motion: {name} is an ElementHeatSource; give a scalar or a region table")
    items = value.values() if is_per_region(value) else (value if isinstance(value, tuple) else (value,))
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
    scale = max(abs(a), abs(b), abs(c))
    if abs(a) <= 1e-14 * scale:
        return [] if abs(b) <= 1e-14 * scale else [-c / b]
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
