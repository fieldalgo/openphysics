# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady homogeneous isotropic heat conduction on conforming P1 triangles.

Import this submodule explicitly. See docs/thermal_steady2d.md for SI units,
boundary signs and validation limits. No other physics module is required.
"""
from dataclasses import dataclass
from typing import Mapping

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from .mesh import Mesh
from .assembly import assemble_stiffness, assemble_load
from .postprocess import element_gradient
from .solver import solve_dirichlet


def _real(value, name):
    a = np.asarray(value)
    if a.dtype.kind not in "iuf" or not np.all(np.isfinite(a)):
        raise ValueError(f"{name} must contain finite real numbers")
    a = np.asarray(a, dtype=float)
    if not np.all(np.isfinite(a)):
        raise ValueError(f"{name} exceeds floating-point range")
    return a


def _mesh_geometry(mesh):
    if not isinstance(mesh, Mesh):
        raise ValueError("mesh must be a galerkin.mesh.Mesh")
    p, t = _real(mesh.nodes, "mesh.nodes"), np.asarray(mesh.triangles)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3:
        raise ValueError("mesh.nodes must have shape (N, 2), N >= 3")
    if t.ndim != 2 or t.shape[1] != 3 or not len(t) or t.dtype.kind not in "iu":
        raise ValueError("mesh.triangles must be a nonempty integer (M, 3) array")
    if np.any(t < 0) or np.any(t >= len(p)):
        raise ValueError("triangle index outside mesh nodes")
    if len(np.unique(t)) != len(p):
        raise ValueError("mesh contains unused nodes")
    if len(np.unique(p, axis=0)) != len(p):
        raise ValueError("mesh contains coincident nodes")
    if len(np.unique(np.sort(t, axis=1), axis=0)) != len(t):
        raise ValueError("mesh contains duplicate triangles")
    q = p[t]
    j = q[:, 1:]-q[:, :1]
    det = j[:, 0, 0]*j[:, 1, 1]-j[:, 0, 1]*j[:, 1, 0]
    scale2 = np.max(np.sum(j*j, axis=2), axis=1)
    if np.any(~np.isfinite(det)) or np.any(det <= 1e-14*scale2):
        raise ValueError("triangles must be counter-clockwise and nondegenerate")
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
            raise ValueError("nonmanifold vertex or triangles joined only at a point")
    centers = q.mean(axis=1)
    radii = np.linalg.norm(q-centers[:, None], axis=2).max(axis=1)
    tree = cKDTree(centers)
    for i, candidates in enumerate(tree.query_ball_point(centers, radii+radii.max())):
        ids = np.array([k for k in candidates if k > i], dtype=int)
        if not len(ids):
            continue
        ids = ids[np.linalg.norm(centers[ids]-centers[i], axis=1) < radii[ids]+radii[i]]
        if not len(ids):
            continue
        other, here = q[ids]-centers[i], q[i]-centers[i]
        de = np.concatenate([np.broadcast_to(np.roll(here, -1, axis=0)-here, other.shape),
                             np.roll(other, -1, axis=1)-other], axis=1)
        axes = np.stack([-de[..., 1], de[..., 0]], axis=-1)
        axes /= np.linalg.norm(axes, axis=2)[..., None]
        pa, pb = np.einsum("vd,kad->kav", here, axes), np.einsum("kvd,kad->kav", other, axes)
        overlap = np.minimum(pa.max(axis=2), pb.max(axis=2))-np.maximum(pa.min(axis=2), pb.min(axis=2))
        if np.any(np.all(overlap > 1e-12*np.maximum(radii[i], radii[ids])[:, None], axis=1)):
            raise ValueError("mesh triangles have overlapping interiors")
    node_tree = cKDTree(p)
    for a, b in edges:
        v = p[b]-p[a]
        length = np.linalg.norm(v)
        candidates = node_tree.query_ball_point((p[a]+p[b])/2, length/2*(1+1e-12))
        for node in candidates:
            if node in (a, b):
                continue
            w = p[node]-p[a]
            s = w@v/(length*length)
            if 1e-12 < s < 1-1e-12 and abs(v[0]*w[1]-v[1]*w[0]) <= 1e-12*length*length:
                raise ValueError("nonconforming mesh: node inside an edge")
    row, col = np.repeat(t, 3, axis=1).ravel(), np.tile(t, (1, 3)).ravel()
    graph = coo_matrix((np.ones(len(row)), (row, col)), shape=(len(p), len(p)))
    count, labels = connected_components(graph, directed=False)
    return p, t, det/2, boundary, count, labels


def _source_load(mesh, p, t, area, source):
    if not callable(source):
        value = _real(source, "heat_source")
        if value.shape != ():
            raise ValueError("constant heat_source must be scalar")
        return assemble_load(mesh, float(value))
    # Original Duffy-product rule: integrate Q*N_i, not centroid Q times A/3.
    x, w = np.polynomial.legendre.leggauss(6)
    x, w = (x+1)/2, w/2
    a, b = np.meshgrid(x, x, indexing="ij")
    bary = np.stack([(1-a)*(1-b), a, (1-a)*b], axis=-1).reshape(-1, 3)
    weights = (2*w[:, None]*w[None, :]*(1-a)).ravel()
    points = np.einsum("qa,tad->tqd", bary, p[t])
    values = _real(source(points.reshape(-1, 2)), "heat_source callback")
    if values.shape != (points.shape[0]*points.shape[1],):
        raise ValueError("heat_source callback must return exactly shape (Q,)")
    local = np.einsum("qi,q,tq,t->ti", bary, weights,
                      values.reshape(points.shape[:2]), area)
    load = np.zeros(len(p))
    np.add.at(load, t.ravel(), local.ravel())
    return load


@dataclass
class SteadyHeatResult:
    """temperature (N,) K, heat_flux (M,2) W/m^2, nodal forces (N,) W/m.

    reaction is residual=K*T-load on fixed nodes, zero on free nodes.
    Positive reaction injects heat; outward integrated heat is -reaction.
    All nodal heat rates are per unit out-of-plane thickness, not watts.
    """
    temperature: np.ndarray
    heat_flux: np.ndarray
    load: np.ndarray
    reaction: np.ndarray
    residual: np.ndarray


def solve_steady_heat(mesh, *, conductivity, dirichlet, heat_source=0.0):
    """Solve -div(k grad T)=Q with prescribed node->K and insulation elsewhere.

    conductivity is finite scalar k>0 in W/(m K). heat_source is scalar Q
    or a callback receiving (Q,2) metre coordinates and returning (Q,) W/m^3.
    dirichlet maps exterior integer node indices to scalar temperatures in K;
    every disconnected mesh component requires at least one prescribed node.
    """
    k = _real(conductivity, "conductivity")
    if k.shape != () or k <= 0:
        raise ValueError("conductivity must be a finite scalar > 0")
    p, t, area, boundary, count, labels = _mesh_geometry(mesh)
    if not isinstance(dirichlet, Mapping):
        raise ValueError("dirichlet must map exterior node indices to temperatures in K")
    prescribed = {}
    anchors = np.zeros(count)
    constrained = np.zeros(count, dtype=bool)
    for node, value in dirichlet.items():
        if isinstance(node, (bool, np.bool_)) or not isinstance(node, (int, np.integer)):
            raise ValueError("Dirichlet node indices must be integers")
        if not 0 <= node < len(p) or node not in boundary:
            raise ValueError("Dirichlet node must lie on the exterior mesh boundary")
        value = _real(value, "Dirichlet temperature")
        if value.shape != ():
            raise ValueError("Dirichlet temperature must be scalar")
        prescribed[int(node)] = float(value)
        component = labels[node]
        if not constrained[component]:
            anchors[component] = value
            constrained[component] = True
    missing = np.flatnonzero(~constrained)
    if len(missing):
        raise ValueError(f"each connected component requires Dirichlet data; missing {missing.tolist()}")
    stiffness = assemble_stiffness(mesh, float(k))
    load = _source_load(mesh, p, t, area, heat_source)
    if not np.all(np.isfinite(stiffness.data)) or not np.all(np.isfinite(load)):
        raise ValueError("assembled heat system exceeds floating-point range")
    shifted_bc = {(node,): value-anchors[labels[node]] for node, value in prescribed.items()}
    try:
        increment = solve_dirichlet(stiffness, load, shifted_bc)
    except RuntimeError as exc:
        raise ValueError("singular or ill-conditioned constrained heat system") from exc
    temperature = increment+anchors[labels]
    # Constant temperature is an exact null mode in each component. Evaluate
    # derivatives/residuals before adding the large absolute-temperature offset.
    residual = stiffness@increment-load
    flux = -float(k)*element_gradient(mesh, increment)
    if not all(np.all(np.isfinite(a)) for a in (temperature, residual, flux)):
        raise ValueError("nonfinite heat solution, residual or heat flux")
    fixed = np.array(sorted(prescribed), dtype=int)
    free = np.setdiff1d(np.arange(len(p)), fixed)
    scale = max(np.linalg.norm(abs(stiffness)@abs(increment)+abs(load), np.inf),
                np.finfo(float).tiny)
    if len(free) and np.linalg.norm(residual[free], np.inf) > 1e-10*scale:
        raise ValueError("heat solve failed the normalized free residual tolerance")
    reaction = np.zeros(len(p))
    reaction[fixed] = residual[fixed]
    balance_scale = max(np.sum(abs(load))+np.sum(abs(reaction)), np.finfo(float).tiny)
    if abs(np.sum(load+reaction)) > 1e-10*balance_scale:
        raise ValueError("heat solve failed the normalized heat balance tolerance")
    return SteadyHeatResult(temperature, flux, load, reaction, residual)
