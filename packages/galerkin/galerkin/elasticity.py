# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Small-strain, homogeneous isotropic P1 triangle elasticity in SI units.

Import this submodule explicitly; see ../docs/elasticity2d.md for the contract.
No scalar or edge finite-element space is used here.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
import warnings

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import MatrixRankWarning, spsolve
from scipy.spatial import cKDTree

from .mesh import Mesh


def _real(value, name):
    a = np.asarray(value)
    if a.dtype.kind not in "iuf" or not np.all(np.isfinite(a)):
        raise ValueError(f"{name} must be finite real numbers")
    return np.asarray(a, dtype=float)


def constitutive_matrix(young_modulus, poisson_ratio, *, plane):
    """Return Pa matrix for [exx, eyy, gamma_xy], gamma_xy=2*exy.

    E > 0 and -1 < nu < 0.5 (stable 3D isotropic parent material).
    ``plane`` is required and must be 'stress' or 'strain'.
    """
    e, nu = _real(young_modulus, "young_modulus"), _real(poisson_ratio, "poisson_ratio")
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


def _mesh_data(mesh):
    if not isinstance(mesh, Mesh):
        raise ValueError("mesh must be a galerkin.mesh.Mesh")
    p, t = _real(mesh.nodes, "mesh.nodes"), np.asarray(mesh.triangles)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3:
        raise ValueError("mesh.nodes must have shape (N, 2), N >= 3")
    if t.ndim != 2 or t.shape[1] != 3 or not len(t) or t.dtype.kind not in "iu":
        raise ValueError("mesh.triangles must be a nonempty integer (T, 3) array")
    if np.any(t < 0) or np.any(t >= len(p)):
        raise ValueError("triangle index outside mesh nodes")
    if len(np.unique(t)) != len(p):
        raise ValueError("mesh contains unused nodes")
    if len(np.unique(p, axis=0)) != len(p):
        raise ValueError("mesh contains coincident nodes")
    if len(np.unique(np.sort(t, axis=1), axis=0)) != len(t):
        raise ValueError("mesh contains duplicate triangles")
    q = p[t]
    j = q[:, 1:] - q[:, :1]
    det = j[:, 0, 0]*j[:, 1, 1] - j[:, 0, 1]*j[:, 1, 0]
    scale2 = np.max(np.sum(j*j, axis=2), axis=1)
    if np.any(~np.isfinite(det)) or np.any(abs(det) <= 1e-14*scale2):
        raise ValueError("degenerate or numerically singular triangles")
    edges = {}
    incident = [[] for _ in p]
    neighbors = [set() for _ in t]
    for i, tri in enumerate(t):
        for node in tri:
            incident[node].append(i)
        for a, b in ((0, 1), (1, 2), (2, 0)):
            edges.setdefault(tuple(sorted((int(tri[a]), int(tri[b])))), []).append(i)
    boundary = set()
    for edge, owners in edges.items():
        if len(owners) > 2:
            raise ValueError("nonmanifold mesh edge")
        if len(owners) == 1:
            boundary.update(edge)
        else:
            a, b = owners
            neighbors[a].add(b)
            neighbors[b].add(a)
    for cells in incident:
        allowed = set(cells)
        reached, stack = {cells[0]}, [cells[0]]
        while stack:
            new = neighbors[stack.pop()] & allowed - reached
            reached.update(new)
            stack.extend(new)
        if len(reached) != len(cells):
            raise ValueError("nonmanifold vertex or triangles connected only at a hinge")
    # A separating-axis test rejects overlapping interiors, including hanging
    # nodes with triangles on the same side. Touching boundaries remain allowed.
    centers = q.mean(axis=1)
    radii = np.linalg.norm(q - centers[:, None], axis=2).max(axis=1)
    tree = cKDTree(centers)
    for i, candidates in enumerate(tree.query_ball_point(centers, radii + radii.max())):
        ids = np.array([k for k in candidates if k > i], dtype=int)
        if not len(ids):
            continue
        ids = ids[np.linalg.norm(centers[ids]-centers[i], axis=1) < radii[ids]+radii[i]]
        if not len(ids):
            continue
        other = q[ids] - centers[i]
        here = q[i] - centers[i]
        de = np.concatenate([np.broadcast_to(np.roll(here, -1, axis=0)-here,
                                              other.shape), np.roll(other, -1, axis=1)-other], axis=1)
        axes = np.stack([-de[..., 1], de[..., 0]], axis=-1)
        axes /= np.linalg.norm(axes, axis=2)[..., None]
        a = np.einsum("vd,kad->kav", here, axes)
        b = np.einsum("kvd,kad->kav", other, axes)
        overlap = np.minimum(a.max(axis=2), b.max(axis=2))-np.maximum(a.min(axis=2), b.min(axis=2))
        tol = 1e-12 * np.maximum(radii[i], radii[ids])
        if np.any(np.all(overlap > tol[:, None], axis=1)):
            raise ValueError("mesh triangles have overlapping interiors")
    # Detect a vertex strictly inside another edge (nonconforming T junction).
    node_tree = cKDTree(p)
    for a, b in edges:
        v = p[b]-p[a]
        length = np.linalg.norm(v)
        candidates = node_tree.query_ball_point((p[a]+p[b])/2, length/2*(1+1e-12))
        for k in candidates:
            if k in (a, b):
                continue
            w = p[k]-p[a]
            s = w @ v / (length*length)
            if 1e-12 < s < 1-1e-12 and abs(v[0]*w[1]-v[1]*w[0]) <= 1e-12*length*length:
                raise ValueError("nonconforming mesh: node inside an edge")
    inv = np.linalg.inv(j)
    grad = np.stack([-inv.sum(axis=2), inv[:, :, 0], inv[:, :, 1]], axis=1)
    bmat = np.zeros((len(t), 3, 6))
    bmat[:, 0, 0::2] = grad[:, :, 0]
    bmat[:, 1, 1::2] = grad[:, :, 1]
    bmat[:, 2, 0::2] = grad[:, :, 1]
    bmat[:, 2, 1::2] = grad[:, :, 0]
    row = np.repeat(t, 3, axis=1).ravel()
    col = np.tile(t, (1, 3)).ravel()
    graph = coo_matrix((np.ones(len(row)), (row, col)), shape=(len(p), len(p)))
    count, labels = connected_components(graph, directed=False)
    dofs = (2*t[:, :, None]+np.arange(2)).reshape(-1, 6)
    return p, t, abs(det)/2, bmat, dofs, boundary, count, labels


def _constraints(dirichlet, p, boundary, count, labels):
    if not isinstance(dirichlet, Mapping):
        raise ValueError("dirichlet must map (node, component) to displacement in metres")
    fixed, values = [], []
    for key, value in dirichlet.items():
        if (not isinstance(key, tuple) or len(key) != 2
                or any(isinstance(k, (bool, np.bool_)) or not isinstance(k, (int, np.integer)) for k in key)):
            raise ValueError("Dirichlet keys must be integer (node, component) tuples")
        node, component = key
        if not 0 <= node < len(p) or component not in (0, 1):
            raise ValueError("Dirichlet node/component index out of range")
        if node not in boundary:
            raise ValueError("Dirichlet nodes must lie on the exterior mesh boundary")
        v = _real(value, "Dirichlet displacement")
        if v.shape != ():
            raise ValueError("each Dirichlet displacement must be scalar")
        fixed.append(2*node+component)
        values.append(float(v))
    fixed = np.asarray(fixed, dtype=int)
    values = np.asarray(values)
    for c in range(count):
        nodes = np.flatnonzero(labels == c)
        local = fixed[labels[fixed//2] == c]
        xy = p[local//2]-p[nodes].mean(axis=0)
        xy /= np.ptp(p[nodes], axis=0).max()
        rigid = np.column_stack([local % 2 == 0, local % 2 == 1,
                                 np.where(local % 2 == 0, -xy[:, 1], xy[:, 0])])
        if len(local) < 3 or np.linalg.matrix_rank(rigid, tol=1e-10) < 3:
            raise ValueError(f"insufficient Dirichlet constraints: rigid modes in component {c}")
    return fixed, values


def _quadrature():
    # Duffy product rule on the unit triangle, 6x6 Gauss points. Weights sum to 1.
    x, w = np.polynomial.legendre.leggauss(6)
    x, w = (x+1)/2, w/2
    a, b = np.meshgrid(x, x, indexing="ij")
    bary = np.stack([(1-a)*(1-b), a, (1-a)*b], axis=-1).reshape(-1, 3)
    weights = (2*w[:, None]*w[None, :]*(1-a)).ravel()
    return bary, weights


@dataclass
class ElasticityResult:
    """Nodal displacement (m), element engineering strain and stress (Pa).

    load and reaction have shape (N,2), units N/m of out-of-plane thickness.
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
                     body_force=(0., 0.)):
    """Solve -div(sigma)=body_force with zero unconstrained traction.

    body_force: constant (2,) or callable accepting (Q,2) coordinates in m
    and returning exactly (Q,2), in N/m^3. Dirichlet: mapping from
    (node, component=0|1) to scalar displacement in m. E and nu are homogeneous.
    Nodes/triangles must form a conforming, nonoverlapping manifold mesh.
    Plane strain P1 displacement elements lock as nu approaches 0.5.
    """
    d = constitutive_matrix(young_modulus, poisson_ratio, plane=plane)
    p, t, area, b, dofs, boundary, count, labels = _mesh_data(mesh)
    fixed, values = _constraints(dirichlet, p, boundary, count, labels)
    ke = np.einsum("tji,jk,tkl,t->til", b, d, b, area)
    if not np.all(np.isfinite(ke)):
        raise ValueError("element stiffness exceeds floating-point range")
    rows = np.repeat(dofs, 6, axis=1).ravel()
    cols = np.tile(dofs, (1, 6)).ravel()
    k = coo_matrix((ke.ravel(), (rows, cols)), shape=(2*len(p), 2*len(p))).tocsr()
    bary, weights = _quadrature()
    points = np.einsum("qa,tad->tqd", bary, p[t])
    if callable(body_force):
        force = _real(body_force(points.reshape(-1, 2)), "body_force")
        if force.shape != (points.shape[0]*points.shape[1], 2):
            raise ValueError("body_force callable must return shape (Q, 2)")
        force = force.reshape(points.shape)
    else:
        force = _real(body_force, "body_force")
        if force.shape != (2,):
            raise ValueError("constant body_force must have shape (2,)")
        force = np.broadcast_to(force, points.shape)
    fe = np.einsum("qa,q,tqd,t->tad", bary, weights, force, area)
    load = np.zeros(2*len(p))
    np.add.at(load, dofs.ravel(), fe.ravel())
    if not np.all(np.isfinite(load)):
        raise ValueError("assembled body force exceeds floating-point range")
    free = np.setdiff1d(np.arange(len(load)), fixed)
    u = np.zeros_like(load)
    u[fixed] = values
    if len(free):
        rhs = load[free]-k[free][:, fixed] @ values
        with warnings.catch_warnings():
            warnings.simplefilter("error", MatrixRankWarning)
            try:
                u[free] = spsolve(k[free][:, free], rhs)
            except (MatrixRankWarning, RuntimeError) as exc:
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
    stress = strain @ d.T
    if not np.all(np.isfinite(strain)) or not np.all(np.isfinite(stress)):
        raise ValueError("computed strain/stress exceeds floating-point range")
    return ElasticityResult(u.reshape(-1, 2), strain, stress, load.reshape(-1, 2),
                            reaction.reshape(-1, 2), residual.reshape(-1, 2), plane)
