# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Small-strain isotropic P1 triangle elasticity in SI units.

E and nu are one homogeneous material or piecewise constant on named mesh
regions (galerkin.materials, docs/packages/galerkin/multimaterial.md).
Import this submodule explicitly; see docs/packages/galerkin/elasticity2d.md for the contract.
No scalar or edge finite-element space is used here.

E, nu, Dirichlet displacements, body force and traction may be JAX or PyTorch
values (callbacks may return them); the result arrays are then in that library
and carry reverse-mode derivatives. One body serves both: the formulas run in
the inputs' library, the checks read their numbers, and the linear system is
solved on NumPy numbers first and then once more with the live matrix and load
(``displacement``), which keeps the values and gives the exact derivatives.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse.linalg import splu

from .materials import is_per_region, region_property
from .core import forms, kernels
from .core import live as live_inputs
from .core import solve as core_solve
from .core.backend import Backend, backend_of, is_live, lift, live_namespace, namespace, scatter_add, to_numpy
from .core.boundary import traction_load
from .core.checks import real_array, real_value
from .core.sparse import CooMatrix
from .core.constraints import vector_dirichlet
from .core.quadrature import triangle_product_rule
from .core.triangles import triangle_geometry, vector_strain


def lame(e, nu, plane):
    """Lame parameters (lam, mu) in Pa of the plane-stress or plane-strain reduction.

    Elementwise arithmetic only, so e and nu may be floats, NumPy arrays or
    JAX/PyTorch arrays.
    """
    mu = e / (2 * (1 + nu))
    lam = (e * nu / ((1 + nu) * (1 - 2 * nu)) if plane == "strain"
           else e * nu / (1 - nu * nu))
    return lam, mu


def constitutive(xp, e, nu, plane):
    """Pa matrix for [exx, eyy, gamma_xy] in ``xp``: (3,3) for 0-d e and nu, (T,3,3) for (T,)."""
    lam, mu = lame(e, nu, plane)
    zero = xp.zeros_like(mu)
    rows = [[lam + 2*mu, lam, zero], [lam, lam + 2*mu, zero], [zero, zero, mu]]
    return xp.stack([xp.stack(row, axis=-1) for row in rows], axis=-2)


def _check_plane(plane):
    if plane not in ("stress", "strain"):
        raise ValueError("plane must be 'stress' or 'strain'")


def _check_finite(d, what):
    if not np.all(np.isfinite(to_numpy(d))):
        raise ValueError(f"{what} exceed floating-point range")


def constitutive_matrix(young_modulus, poisson_ratio, *, plane):
    """Return Pa matrix for [exx, eyy, gamma_xy], gamma_xy=2*exy.

    E > 0 and -1 < nu < 0.5 (stable 3D isotropic parent material).
    ``plane`` is required and must be 'stress' or 'strain'.
    """
    e, nu = real_array(young_modulus, "young_modulus"), real_array(poisson_ratio, "poisson_ratio")
    if e.shape != () or nu.shape != () or e <= 0 or not -1 < nu < .5:
        raise ValueError("require scalar E > 0 and -1 < nu < 0.5")
    _check_plane(plane)
    d = constitutive(np, np.float64(e), np.float64(nu), plane)
    _check_finite(d, "constitutive parameters")
    return d


def element_materials(mesh, young_modulus, poisson_ratio):
    """Checked E and nu: as given for scalars, (T,) if either is a region table.

    E > 0 and -1 < nu < 0.5 in every region. JAX or PyTorch values stay live.
    """
    e = region_property(mesh, young_modulus, "young_modulus", positive=True, live=True)
    nu = region_property(mesh, poisson_ratio, "poisson_ratio", lower=-1., upper=.5, live=True)
    if is_per_region(young_modulus) or is_per_region(poisson_ratio):
        cells = len(mesh.triangles)
        e, nu = (v if is_live(v) else np.broadcast_to(v, (cells,)) for v in (e, nu))
        xp = live_namespace(e, nu)
        e, nu = (xp.broadcast_to(lift(xp, v, xp.float64), (cells,)) for v in (e, nu))
    return e, nu


def element_constitutive(mesh, young_modulus, poisson_ratio, *, plane):
    """Pa constitutive matrix: (3,3) for scalars, (T,3,3) for region mappings.

    Scalars return exactly constitutive_matrix(...). A mapping for either
    argument gives one matrix per triangle; each region must satisfy E > 0 and
    -1 < nu < 0.5.
    """
    if not (is_per_region(young_modulus) or is_per_region(poisson_ratio)):
        return constitutive_matrix(young_modulus, poisson_ratio, plane=plane)
    _check_plane(plane)
    e, nu = element_materials(mesh, young_modulus, poisson_ratio)
    xp = live_namespace(e, nu)
    d = constitutive(xp, e, nu, plane)
    _check_finite(d, "constitutive parameters")
    return d


def stiffness_and_stress(b, d, area):
    """Element stiffness (T,6,6) and a strain->stress map for (3,3) or (T,3,3) d."""
    xp = namespace(d)
    return kernels.vector_p1_stiffness(b, d, area), lambda strain: stress_of(xp, d, strain)


def stress_of(xp, d, strain):
    """Element stress (T,3) from strain (T,3) and d (3,3) or (T,3,3)."""
    if d.ndim == 2:
        return strain @ d.T
    return xp.einsum("tij,tj->ti", d, strain)


def body_load(p, t, area, dofs, body_force):
    """Consistent load (2N,) of a constant (2,) or callable body force in N/m^3.

    The callable takes (Q,2) coordinates and returns exactly (Q,2). The load is
    in the library of the force (NumPy for NumPy input).
    """
    bary, weights = triangle_product_rule()
    points = np.einsum("qa,tad->tqd", bary, p[t])
    if callable(body_force):
        force = real_value(body_force(points.reshape(-1, 2)), "body_force")
        if tuple(force.shape) != (points.shape[0]*points.shape[1], 2):
            raise ValueError("body_force callable must return shape (Q, 2)")
        xp = namespace(force)
        force = xp.reshape(force, points.shape)
    else:
        force = real_value(body_force, "body_force")
        if tuple(force.shape) != (2,):
            raise ValueError("constant body_force must have shape (2,)")
        xp = namespace(force)
        force = xp.broadcast_to(force, points.shape)
    fe = xp.einsum("qa,q,tqd,t->tad", *(lift(xp, a) for a in (bary, weights)), force, lift(xp, area))
    return scatter_add(xp, 2*len(p), dofs.ravel(), xp.reshape(fe, (-1,)))


def constrained_solve(stiffness, load, fixed, values, what):
    """NumPy u with u[fixed] = values and K u = load on the free DOFs, and its residual K u - load.

    Raises ValueError for a singular or ill-conditioned system, a nonfinite
    solution or a free-DOF residual above 1e-9 of the load scale.
    """
    k = stiffness.to_scipy()
    free = np.setdiff1d(np.arange(len(load)), fixed)
    u = np.zeros_like(load)
    u[fixed] = values
    if len(free):
        rhs = load[free]-k[free][:, fixed] @ values
        try:
            u[free] = splu(k[free][:, free].tocsc()).solve(rhs)
        except RuntimeError as exc:
            raise ValueError(f"singular or ill-conditioned constrained {what} system") from exc
    residual = k @ u-load
    if not np.all(np.isfinite(u)) or not np.all(np.isfinite(residual)):
        raise ValueError(f"nonfinite {what} solution; check geometry and material scaling")
    scale = max(np.linalg.norm(abs(k) @ abs(u)+abs(load), np.inf), np.finfo(float).tiny)
    if len(free) and np.linalg.norm(residual[free], np.inf) > 1e-9*scale:
        raise ValueError(f"constrained {what} solve failed its residual tolerance")
    return u


def displacement(xp, stiffness, load, dirichlet, p, boundary, count, labels, what):
    """Displacement (2N,) in ``xp`` and the fixed DOFs.

    The checked NumPy solve gives u0; with JAX or PyTorch values, one more
    solve u0 + K^{-1}(f - K u0) with the live K, f and Dirichlet values keeps
    u0 up to rounding and gives the exact derivatives.
    """
    fixed, values = vector_dirichlet(live_inputs.numbers(dirichlet), p, boundary, count, labels)
    u0 = constrained_solve(_numbers(stiffness), to_numpy(load), fixed, values, what)
    if backend_of(xp) is Backend.NUMPY:
        return u0, fixed
    prescribed = (xp.stack([lift(xp, v, xp.float64) for v in dirichlet.values()]) if len(fixed)
                  else xp.zeros(0, dtype=xp.float64))
    u0 = lift(xp, u0)
    delta = core_solve.solve_dirichlet(stiffness, load - stiffness.matvec(u0),
                                       {tuple(fixed): prescribed - u0[fixed]} if len(fixed) else {})
    return u0 + delta, fixed


def _numbers(matrix):
    return CooMatrix(matrix.rows, matrix.cols, to_numpy(matrix.values), matrix.shape)


def at_fixed(xp, residual, fixed):
    """The reaction: ``residual`` at the fixed DOFs, zero elsewhere."""
    mask = np.zeros(residual.shape[0], dtype=bool)
    mask[fixed] = True
    return xp.where(lift(xp, mask), residual, xp.zeros_like(residual))


def vector_stiffness(xp, b, dofs, d, area, size):
    """Element stiffness checked finite, assembled: a CooMatrix in ``xp`` (coalesced when live)."""
    ke = kernels.vector_p1_stiffness(b, d, area)
    if not np.all(np.isfinite(to_numpy(ke))):
        raise ValueError("element stiffness exceeds floating-point range")
    k = forms.matrix(dofs, dofs, ke, (size, size))
    return k if backend_of(xp) is Backend.NUMPY else k.coalesce()


@dataclass
class ElasticityResult:
    """Nodal displacement (m), element engineering strain and stress (Pa).

    load (body plus boundary traction) and reaction have shape (N,2),
    units N/m of out-of-plane thickness.
    reaction is zero at free DOFs, and K*u-load at prescribed DOFs.
    residual is K*u-load at ALL DOFs, with the same units.
    """
    displacement: np.ndarray
    strain: np.ndarray
    stress: np.ndarray
    load: np.ndarray
    reaction: np.ndarray
    residual: np.ndarray
    plane: str


def solve_elasticity(mesh, *, young_modulus, poisson_ratio, plane, dirichlet,
                     body_force=(0., 0.), traction=None):
    """Solve -div(sigma)=body_force with optional prescribed boundary traction.

    E, nu, Dirichlet displacements, body_force and traction may be JAX or
    PyTorch values, or callbacks returning them; the result is then in that
    library with reverse-mode derivatives (docs/packages/galerkin/differentiation.md).
    Callbacks are called once.


    body_force: constant (2,) or callable accepting (Q,2) coordinates in m
    and returning exactly (Q,2), in N/m^3. Dirichlet: mapping from
    (node, component=0|1) to scalar displacement in m. E (Pa) and nu are
    scalars or {region name: value} mappings over mesh.region_names.
    traction: {boundary_edges tag: global (2,) vector in Pa, or
    callable(points, outward_normals)->(Q,2)}. None/{} keeps zero traction.
    All line loads, including those on prescribed displacement components,
    enter load; their support reactions are computed from the original K*u-load.
    Duplicate selected edges and interior edges are rejected. See
    docs/packages/galerkin/elasticity_traction.md for overlap, quadrature and units.
    Nodes/triangles must form a conforming, nonoverlapping manifold mesh.
    Plane strain P1 displacement elements lock as nu approaches 0.5.
    """
    _check_plane(plane)
    p, t, area, boundary, count, labels = triangle_geometry(mesh, counterclockwise=False)
    b, dofs = vector_strain(p, t)
    e, nu = element_materials(mesh, young_modulus, poisson_ratio)
    body = body_load(p, t, area, dofs, body_force)
    line = traction_load(mesh, p, t, traction, live=True)
    xp = live_namespace(e, nu, body, line, *live_inputs.leaves(dirichlet))
    d = constitutive(xp, *(lift(xp, v, xp.float64) for v in (e, nu)), plane)
    _check_finite(d, "constitutive parameters")
    n = 2*len(p)
    stiffness = vector_stiffness(xp, b, dofs, d, area, n)
    body = lift(xp, body)
    if not np.all(np.isfinite(to_numpy(body))):
        raise ValueError("assembled body force exceeds floating-point range")
    load = body + lift(xp, line)
    if not np.all(np.isfinite(to_numpy(load))):
        raise ValueError("total body and traction load exceeds floating-point range")
    u, fixed = displacement(xp, stiffness, load, dirichlet, p, boundary, count, labels, "elasticity")
    residual = stiffness.matvec(u) - load
    strain = xp.einsum("tij,tj->ti", lift(xp, b), u[dofs])
    stress = stress_of(xp, d, strain)
    if not np.all(np.isfinite(to_numpy(strain))) or not np.all(np.isfinite(to_numpy(stress))):
        raise ValueError("computed strain/stress exceeds floating-point range")
    return ElasticityResult(xp.reshape(u, (-1, 2)), strain, stress,
                            *(xp.reshape(a, (-1, 2)) for a in (load, at_fixed(xp, residual, fixed), residual)),
                            plane)
