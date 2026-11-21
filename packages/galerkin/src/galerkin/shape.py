# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Shape derivatives: derivatives with respect to a design parameter that moves the mesh.

A design parameter t moves every node: X(t) = X0 + t W, with a fixed NumPy design
velocity W of shape (N, 2) (``design_velocity``: metres of node motion per unit of the
dimensionless t). Only t is live:
a JAX or PyTorch scalar whose number is the step at which the solve runs (usually
0, the mesh as given). The connectivity, tags and regions stay fixed, so the
derivative is the exact derivative of the discrete solution on the moving mesh.

- ``extend_velocity`` builds W from the velocities of the nodes on the geometry's
  curves (``simcase.geometry_velocity.DesignVelocity.node_velocity``): every other
  node moves by a harmonic extension of them.
- ``admissible_interval`` is the exact range of t over which no element inverts.
- ``MeshMotion(design_velocity=W, t=t)`` passed as ``motion=`` to a supported solver
  returns its result fields with their derivative with respect to t.

``motion=`` is taken by ``thermal.solve_steady_heat`` (Cartesian and axisymmetric),
``electric.solve_steady_electric``, ``elasticity.solve_elasticity``,
``transient_heat.solve_transient_heat`` (Cartesian and axisymmetric),
``thermal3d.solve_steady_heat_3d`` (a ``Mesh3D`` with an (N, 3) velocity), ``waveguide.solve_modes``
(with coordinate factors when the motion leaves every stretched element in place),
``thermoelasticity.solve_thermoelasticity`` and
``thermal_mechanical.solve_steady_thermoelasticity`` with scalar or region data and
constant loads; the refusals are listed in docs/packages/galerkin/shape_derivative.md.
The moving-mesh solves behind ``motion=`` are internal: they live in the package-private
``galerkin._moving`` (L2 commit 8), and ``galerkin.kernels`` re-exports them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .core.backend import lift
from .mesh import Mesh
from ._public import refuse_text
from ._moving import (checked_step as _checked_step, checked_velocity as _velocity, cross as _cross,
                      live_bc as _live_bc, live_t as _live_t, signed_area as _signed_area)

# Public names. The moving-mesh solves (solve_*_moving) are internal: galerkin.kernels re-exports
# them from galerkin._moving, and the public route to them is motion= on the public solver.
__all__ = ["MeshMotion", "ElementInversion", "admissible_interval", "extend_velocity", "MotionStep",
           "motion_step", "live_triangle_geometry"]


@dataclass(frozen=True, kw_only=True)
class MeshMotion:
    """Nodes at X0 + t * design_velocity; ``t`` is a JAX or PyTorch scalar (the design parameter step).

    ``design_velocity`` is the (N, 2) NumPy node velocity (N, 3 on a ``Mesh3D``) in metres per
    unit of the dimensionless t. Both are keyword-only; a str for design_velocity raises
    TypeError.
    """

    design_velocity: object
    t: object

    def __post_init__(self):
        refuse_text("design_velocity", self.design_velocity)


class ElementInversion(ValueError):
    """The motion inverts an element at the requested step."""


def admissible_interval(mesh: Mesh, *, design_velocity) -> tuple[float, float]:
    """(t_lo, t_hi), t_lo < 0 < t_hi: the open interval of t in which every element of
    X0 + t W keeps its orientation (W = design_velocity, (N, 2) m per unit of t, or (N, 3) on a
    ``Mesh3D``). Each signed area is a quadratic in t, each tetrahedron volume a cubic; its
    nearest real root on each side bounds the interval (inf when an element never inverts)."""
    from .mesh3d import Mesh3D

    refuse_text("design_velocity", design_velocity)
    W = _velocity(mesh, design_velocity)
    if isinstance(mesh, Mesh3D):
        return _tet_interval(mesh.nodes, W, mesh.tets)
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
    """The (N, 2) mesh velocity ((N, 3) on a ``Mesh3D``) that equals ``values`` on the ``known`` nodes.

    ``known`` is a boolean (N,) mask (the nodes on curves or surfaces) and ``values`` an
    (N, 2) or (N, 3) array (read on known nodes only). Every other node takes, per
    component, the solution of a Laplace problem on the mesh with those Dirichlet values:
    ``"harmonic"`` uses unit diffusivity; ``"stiffened"`` divides it by the element area
    (volume in 3D), so small elements near curves move more rigidly. Known nodes must touch
    every connected component."""
    from scipy.sparse import coo_matrix

    from .core import kernels
    from .core.solve import scipy_solve_dirichlet
    from .mesh3d import Mesh3D

    values = np.asarray(values, dtype=float)
    known = np.asarray(known, dtype=bool)
    n = mesh.num_nodes
    dim = mesh.nodes.shape[1]
    if values.shape != (n, dim) or known.shape != (n,):
        raise ValueError(f"extend_velocity: values must be ({n}, {dim}) and known ({n},)")
    if not np.all(np.isfinite(values[known])):
        raise ValueError("extend_velocity: known values must be finite")
    sizes = mesh.volumes() if isinstance(mesh, Mesh3D) else mesh.areas()
    if method == "harmonic":
        eps = 1.0
    elif method == "stiffened":
        eps = float(np.mean(sizes)) / sizes
    else:
        raise ValueError(f"extend_velocity: method must be 'harmonic' or 'stiffened', not {method!r}")
    if isinstance(mesh, Mesh3D):
        from .assembly3d import assemble_stiffness_3d
        K = assemble_stiffness_3d(mesh, np.broadcast_to(np.asarray(eps, dtype=float), (mesh.num_tets,))).tocsr()
    else:
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
    out = np.empty((n, dim))
    for k in range(dim):
        out[:, k] = scipy_solve_dirichlet(K, np.zeros(n), {(int(i),): values[i, k] for i in fixed})
    return out


# ----------------------------------------------------------------------------- public helpers for solver modules

@dataclass(frozen=True, kw_only=True)
class MotionStep:
    """A checked motion: the live namespace ``xp`` and float64 ``t``, the NumPy design velocity
    (``design_velocity``, (N, 2) metres per unit of t, (N, 3) on a ``Mesh3D``) and the moved mesh
    (a ``Mesh`` or ``Mesh3D``, as given). Keyword-only."""

    xp: object
    t: object
    design_velocity: np.ndarray
    moved: Mesh

    def __post_init__(self):
        refuse_text("design_velocity", self.design_velocity)


def motion_step(mesh: Mesh, motion: MeshMotion) -> MotionStep:
    """Check ``motion`` against ``mesh`` (live float64 t, finite velocity, no inverted element) and move it.

    For solver modules that assemble their own live system on X0 + t W; ``mesh`` is a ``Mesh`` or a
    ``Mesh3D`` (velocity (N, 2) or (N, 3)). ``live_triangle_geometry`` takes the 2D steps only."""
    xp, t = _live_t(motion.t)
    W = _velocity(mesh, motion.design_velocity)
    return MotionStep(xp=xp, t=t, design_velocity=W, moved=_checked_step(mesh, W, t))


def live_triangle_geometry(xp, mesh: Mesh, triangles, step: MotionStep):
    """Live P1 coefficients b, c (T, 3) and positive areas (T,) of ``triangles`` on X0 + t W.

    grad lambda_i = (b_i, c_i) / (2 area); the orientation is taken from the moved mesh."""
    triangles = np.asarray(triangles, dtype=int)
    X = lift(xp, mesh.nodes) + step.t * lift(xp, step.design_velocity)
    return _live_bc(xp, X, triangles, np.sign(_signed_area(step.moved.nodes, triangles)))


# ----------------------------------------------------------------------------- helpers

def _edges(nodes, W, tris):
    p, w = nodes[tris], W[tris]
    return p[:, 1] - p[:, 0], p[:, 2] - p[:, 0], w[:, 1] - w[:, 0], w[:, 2] - w[:, 0]


def _tet_interval(nodes, W, tets):
    """The admissible interval of a tetrahedral motion: 6 V(t) = det(E + t F) is a cubic in t.

    Vectorized over the tetrahedra. Simple real roots are polished by Newton steps; a cluster of
    roots (a double or triple root, e.g. a uniform scaling) splits under rounding into a real root
    and a nearly real complex pair, so the real parts of roots within 1e-5 of the real axis are
    candidates too. The interval is then exact for simple roots and conservative (inside the true
    one) near clustered roots; _checked_step also tests the moved volumes directly."""
    p, w = nodes[tets], W[tets]
    e = [p[:, i] - p[:, 0] for i in (1, 2, 3)]
    f = [w[:, i] - w[:, 0] for i in (1, 2, 3)]

    def det(a, b, c):
        return np.einsum("td,td->t", a, np.cross(b, c))
    c0 = det(*e)
    c1 = det(f[0], e[1], e[2]) + det(e[0], f[1], e[2]) + det(e[0], e[1], f[2])
    c2 = det(e[0], f[1], f[2]) + det(f[0], e[1], f[2]) + det(f[0], f[1], e[2])
    c3 = det(*f)
    candidates = [np.empty(0)]
    cubic = c3 != 0
    if np.any(cubic):
        a, b, c, d = c3[cubic], c2[cubic], c1[cubic], c0[cubic]
        companion = np.zeros((len(a), 3, 3))
        companion[:, 0, :] = -np.stack([b / a, c / a, d / a], axis=1)
        companion[:, 1, 0] = companion[:, 2, 1] = 1.0
        roots = np.linalg.eigvals(companion)                                       # (K, 3)
        size = np.maximum(np.abs(roots), 1e-300)
        real = np.abs(roots.imag) <= 1e-9 * size
        x = roots.real.copy()
        coefficients = [np.broadcast_to(v[:, None], x.shape) for v in (a, b, c, d)]
        for _ in range(4):                                                         # polish the real roots
            value = ((coefficients[0] * x + coefficients[1]) * x + coefficients[2]) * x + coefficients[3]
            slope = (3 * coefficients[0] * x + 2 * coefficients[1]) * x + coefficients[2]
            with np.errstate(divide="ignore", invalid="ignore"):
                step = np.where(real & (slope != 0), value / slope, 0.0)
            x = x - step
        candidates.append(x[np.abs(roots.imag) <= 1e-5 * size])
    quadratic = ~cubic & (c2 != 0)
    if np.any(quadratic):
        a, b, c = c2[quadratic], c1[quadratic], c0[quadratic]
        disc = b * b - 4 * a * c
        ok = disc >= 0
        q = -0.5 * (b[ok] + np.copysign(np.sqrt(disc[ok]), b[ok]))
        with np.errstate(divide="ignore", invalid="ignore"):
            candidates += [q / a[ok], np.where(q != 0, c[ok] / q, 0.0)]
    linear = ~cubic & (c2 == 0) & (c1 != 0)
    candidates.append(-c0[linear] / c1[linear])
    roots = np.concatenate(candidates)
    roots = roots[np.isfinite(roots)]
    positive, negative = roots[roots > 0], roots[roots < 0]
    return (float(negative.max()) if len(negative) else -math.inf,
            float(positive.min()) if len(positive) else math.inf)


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
