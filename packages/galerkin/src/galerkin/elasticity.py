# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Small-strain isotropic P1 triangle elasticity in SI units.

E and nu are one homogeneous material or piecewise constant on named mesh
regions (galerkin.materials, docs/packages/galerkin/multimaterial.md).
Import this submodule explicitly; see docs/packages/galerkin/elasticity2d.md for the contract.
No scalar or edge finite-element space is used here.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import splu

from .materials import is_per_region, region_property
from .core.boundary import traction_load
from .core.checks import real_array
from .core.constraints import vector_dirichlet
from .core.quadrature import triangle_product_rule
from .core.triangles import triangle_geometry, vector_strain


def constitutive_matrix(young_modulus, poisson_ratio, *, plane):
    """Return Pa matrix for [exx, eyy, gamma_xy], gamma_xy=2*exy.

    E > 0 and -1 < nu < 0.5 (stable 3D isotropic parent material).
    ``plane`` is required and must be 'stress' or 'strain'.
    """
    e, nu = real_array(young_modulus, "young_modulus"), real_array(poisson_ratio, "poisson_ratio")
    if e.shape != () or nu.shape != () or e <= 0 or not -1 < nu < .5:
        raise ValueError("require scalar E > 0 and -1 < nu < 0.5")
    if plane not in ("stress", "strain"):
        raise ValueError("plane must be 'stress' or 'strain'")
    e, nu = float(e), float(nu)
    mu = e / (2 * (1 + nu))
    lam = (e * nu / ((1 + nu) * (1 - 2 * nu)) if plane == "strain"
           else e * nu / (1 - nu * nu))
    d = np.array([[lam + 2*mu, lam, 0], [lam, lam + 2*mu, 0], [0, 0, mu]])
    if not np.all(np.isfinite(d)):
        raise ValueError("constitutive parameters exceed floating-point range")
    return d


def element_constitutive(mesh, young_modulus, poisson_ratio, *, plane):
    """Pa constitutive matrix: (3,3) for scalars, (T,3,3) for region mappings.

    Scalars return exactly constitutive_matrix(...). A mapping for either
    argument gives one matrix per triangle; each region must satisfy E > 0 and
    -1 < nu < 0.5.
    """
    if not (is_per_region(young_modulus) or is_per_region(poisson_ratio)):
        return constitutive_matrix(young_modulus, poisson_ratio, plane=plane)
    if plane not in ("stress", "strain"):
        raise ValueError("plane must be 'stress' or 'strain'")
    e = region_property(mesh, young_modulus, "young_modulus", positive=True)
    nu = region_property(mesh, poisson_ratio, "poisson_ratio", lower=-1., upper=.5)
    e = np.broadcast_to(e, (len(mesh.triangles),))
    nu = np.broadcast_to(nu, e.shape)
    mu = e / (2 * (1 + nu))
    lam = (e * nu / ((1 + nu) * (1 - 2 * nu)) if plane == "strain"
           else e * nu / (1 - nu * nu))
    d = np.zeros((len(e), 3, 3))
    d[:, 0, 0] = d[:, 1, 1] = lam + 2*mu
    d[:, 0, 1] = d[:, 1, 0] = lam
    d[:, 2, 2] = mu
    if not np.all(np.isfinite(d)):
        raise ValueError("constitutive parameters exceed floating-point range")
    return d


def stiffness_and_stress(b, d, area):
    """Element stiffness (T,6,6) and a strain->stress map for (3,3) or (T,3,3) d."""
    if d.ndim == 2:
        return (np.einsum("tji,jk,tkl,t->til", b, d, b, area),
                lambda strain: strain @ d.T)
    return (np.einsum("tji,tjk,tkl,t->til", b, d, b, area),
            lambda strain: np.einsum("tij,tj->ti", d, strain))


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
    per_region = is_per_region(young_modulus) or is_per_region(poisson_ratio)
    if not per_region:
        d = constitutive_matrix(young_modulus, poisson_ratio, plane=plane)
    elif plane not in ("stress", "strain"):
        raise ValueError("plane must be 'stress' or 'strain'")
    p, t, area, boundary, count, labels = triangle_geometry(mesh, counterclockwise=False)
    b, dofs = vector_strain(p, t)
    if per_region:
        d = element_constitutive(mesh, young_modulus, poisson_ratio, plane=plane)
    fixed, values = vector_dirichlet(dirichlet, p, boundary, count, labels)
    ke, stress_of = stiffness_and_stress(b, d, area)
    if not np.all(np.isfinite(ke)):
        raise ValueError("element stiffness exceeds floating-point range")
    rows = np.repeat(dofs, 6, axis=1).ravel()
    cols = np.tile(dofs, (1, 6)).ravel()
    k = coo_matrix((ke.ravel(), (rows, cols)), shape=(2*len(p), 2*len(p))).tocsr()
    bary, weights = triangle_product_rule()
    points = np.einsum("qa,tad->tqd", bary, p[t])
    if callable(body_force):
        force = real_array(body_force(points.reshape(-1, 2)), "body_force")
        if force.shape != (points.shape[0]*points.shape[1], 2):
            raise ValueError("body_force callable must return shape (Q, 2)")
        force = force.reshape(points.shape)
    else:
        force = real_array(body_force, "body_force")
        if force.shape != (2,):
            raise ValueError("constant body_force must have shape (2,)")
        force = np.broadcast_to(force, points.shape)
    fe = np.einsum("qa,q,tqd,t->tad", bary, weights, force, area)
    load = np.zeros(2*len(p))
    np.add.at(load, dofs.ravel(), fe.ravel())
    if not np.all(np.isfinite(load)):
        raise ValueError("assembled body force exceeds floating-point range")
    load += traction_load(mesh, p, t, traction)
    if not np.all(np.isfinite(load)):
        raise ValueError("total body and traction load exceeds floating-point range")
    free = np.setdiff1d(np.arange(len(load)), fixed)
    u = np.zeros_like(load)
    u[fixed] = values
    if len(free):
        rhs = load[free]-k[free][:, fixed] @ values
        try:
            u[free] = splu(k[free][:, free].tocsc()).solve(rhs)
        except RuntimeError as exc:
            raise ValueError("singular or ill-conditioned constrained elasticity system") from exc
    residual = k @ u-load
    if not np.all(np.isfinite(u)) or not np.all(np.isfinite(residual)):
        raise ValueError("nonfinite elasticity solution; check geometry and material scaling")
    scale = max(np.linalg.norm(abs(k) @ abs(u)+abs(load), np.inf),
                np.finfo(float).tiny)
    if len(free) and np.linalg.norm(residual[free], np.inf) > 1e-9*scale:
        raise ValueError("constrained elasticity solve failed its residual tolerance")
    reaction = np.zeros_like(load)
    reaction[fixed] = residual[fixed]
    strain = np.einsum("tij,tj->ti", b, u[dofs])
    stress = stress_of(strain)
    if not np.all(np.isfinite(strain)) or not np.all(np.isfinite(stress)):
        raise ValueError("computed strain/stress exceeds floating-point range")
    return ElasticityResult(u.reshape(-1, 2), strain, stress, load.reshape(-1, 2),
                            reaction.reshape(-1, 2), residual.reshape(-1, 2), plane)
