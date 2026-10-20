# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady isotropic heat conduction on conforming P1 triangles.

Conductivity and constant heat source are one scalar or piecewise constant on
named mesh regions (galerkin.materials). Import this submodule explicitly. See
docs/packages/galerkin/thermal_steady2d.md and
docs/packages/galerkin/multimaterial.md for SI units, boundary signs and
validation limits. No other physics module is required.
"""
import itertools
from dataclasses import dataclass
from typing import Mapping

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from .mesh import Mesh
from .materials import is_per_region, region_property
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


def _overlap_candidates(centers, radii, block=4096):
    """Yield (i, ids), ids > i ascending: every pair whose interiors may overlap.

    radii are each triangle's largest centroid-to-vertex distance. Interiors can
    overlap only if |c_i - c_k| < r_i + r_k <= 2*max(r_i, r_k), so querying each
    centroid with twice its own radius finds every such pair from its larger
    triangle, and the work follows the local triangle size, not the largest
    triangle. The 1e-12 margin keeps a pair at exactly that bound, where the
    tree and numpy may round the distance differently. Centroids are queried in
    blocks and each found pair is kept only as one int64 key, so memory follows
    the number of pairs, not the tree's Python lists for the whole mesh.
    """
    count = len(centers)
    tree, keys = cKDTree(centers), [np.zeros(0, dtype=np.int64)]
    for start in range(0, count, block):
        stop = min(start+block, count)
        found = tree.query_ball_point(centers[start:stop], 2*radii[start:stop]*(1+1e-12))
        sizes = np.fromiter(map(len, found), dtype=np.int64, count=stop-start)
        rows = np.repeat(np.arange(start, stop, dtype=np.int64), sizes)
        cols = np.fromiter(itertools.chain.from_iterable(found), dtype=np.int64, count=len(rows))
        del found
        keep = rows != cols
        rows, cols = rows[keep], cols[keep]
        keys.append(np.minimum(rows, cols)*count+np.maximum(rows, cols))
    # A pair found from both sides appears twice. Sorting and dropping repeats
    # is much faster than np.unique on these keys.
    key = np.concatenate(keys)
    del keys
    key.sort()
    lo, hi = np.divmod(key[np.diff(key, prepend=-1) != 0], count)
    del key
    bounds = np.searchsorted(lo, np.arange(count+1))
    for i in np.flatnonzero(bounds[1:] > bounds[:-1]):
        yield int(i), hi[bounds[i]:bounds[i+1]]


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
    for i, ids in _overlap_candidates(centers, radii):
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
    if is_per_region(source):
        return assemble_load(mesh, region_property(mesh, source, "heat_source"))
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


def _boundary_samples(mesh, p, t, prescribed, outward_flux, convection):
    """Validate selected exterior identities before sampling four-point rules."""
    owners = {}
    for cell, tri in enumerate(t):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            owners.setdefault(tuple(sorted((int(tri[a]), int(tri[b])))), []).append(cell)
    x, w = np.polynomial.legendre.leggauss(4)
    x, w = (x+1)/2, w/2
    shape = np.column_stack((1-x, x))
    samples = []
    for kind, data in (("outward_flux", outward_flux), ("convection", convection)):
        if data is None:
            continue
        if not isinstance(data, Mapping):
            raise ValueError(f"{kind} must map boundary edge tags to conditions")
        seen = set()
        for tag, condition in data.items():
            if tag not in mesh.boundary_edges:
                raise ValueError(f"unknown boundary edge tag {tag!r}")
            edges = np.asarray(mesh.boundary_edges[tag])
            if (edges.ndim != 2 or edges.shape[1] != 2 or not len(edges)
                    or edges.dtype.kind not in "iu"):
                raise ValueError("selected boundary edges must be nonempty integer (E,2)")
            normals = []
            for a, b in edges:
                if a == b or a < 0 or b < 0 or a >= len(p) or b >= len(p):
                    raise ValueError("invalid boundary edge node indices")
                key = tuple(sorted((int(a), int(b))))
                if key in seen:
                    raise ValueError(f"duplicate {kind} edge, including reversed/tag duplicates")
                seen.add(key)
                cells = owners.get(key, [])
                if len(cells) != 1:
                    raise ValueError("selected edge must have exactly one incident triangle")
                if int(a) in prescribed and int(b) in prescribed:
                    raise ValueError("natural condition overlaps a fully Dirichlet edge")
                v = p[b]-p[a]
                length = np.linalg.norm(v)
                if not np.isfinite(length) or length <= 0:
                    raise ValueError("boundary edge must have finite positive length")
                n = np.array([v[1], -v[0]])/length
                if n@(p[t[cells[0]]].mean(axis=0)-(p[a]+p[b])/2) > 0:
                    n = -n
                normals.append(n)
            points = np.einsum("qa,ead->eqd", shape, p[edges])
            normal = np.repeat(np.asarray(normals), len(w), axis=0)
            def evaluate(value, name):
                if callable(value):
                    out = _real(value(points.reshape(-1, 2).copy(), normal.copy()), name)
                    if out.shape != (len(edges)*len(w),):
                        raise ValueError(f"{name} callback must return exactly shape (Q,)")
                    return out.reshape(len(edges), len(w))
                out = _real(value, name)
                if out.shape != ():
                    raise ValueError(f"{name} constant must be scalar")
                return np.full(points.shape[:2], float(out))
            if kind == "outward_flux":
                values = (evaluate(condition, "outward flux"),)
            else:
                if not isinstance(condition, (tuple, list)) or len(condition) != 2:
                    raise ValueError("convection condition must be a pair (h, ambient_temperature)")
                h = evaluate(condition[0], "convection h")
                ambient = evaluate(condition[1], "ambient temperature")
                if np.any(h < 0):
                    raise ValueError("convection h must be nonnegative")
                values = (h, ambient)
            length = np.linalg.norm(p[edges[:, 1]]-p[edges[:, 0]], axis=1)
            samples.append((kind, edges, shape, length[:, None]*w, values))
    return samples


def _boundary_system(samples, n, labels, anchors, constrained):
    # Pick a useful absolute offset for Robin-only components. Any positive
    # sampled h anchors discretely; no unit-dependent artificial cutoff.
    for kind, edges, shape, weights, values in samples:
        if kind != "convection":
            continue
        h, ambient = values
        for e, q in np.argwhere(h > 0):
            c = labels[edges[e, 0]]
            if not constrained[c]:
                anchors[c] = ambient[e, q]
                constrained[c] = True
    G, B, shifted_B = np.zeros((3, n))
    rows, cols, entries = [], [], []
    for kind, edges, shape, weights, values in samples:
        if kind == "outward_flux":
            local = np.einsum("eq,qa,eq->ea", weights, shape, values[0])
            np.add.at(G, edges.ravel(), local.ravel())
        else:
            h, ambient = values
            local_h = np.einsum("eq,qa,qb,eq->eab", weights, shape, shape, h)
            local_b = np.einsum("eq,qa,eq->ea", weights, shape, h*ambient)
            local_shift = np.einsum("eq,qa,eq->ea", weights, shape,
                                    h*(ambient-anchors[labels[edges[:, 0]]][:, None]))
            np.add.at(B, edges.ravel(), local_b.ravel())
            np.add.at(shifted_B, edges.ravel(), local_shift.ravel())
            rows.extend(np.repeat(edges, 2, axis=1).ravel())
            cols.extend(np.tile(edges, (1, 2)).ravel())
            entries.extend(local_h.ravel())
    H = coo_matrix((entries, (rows, cols)), shape=(n, n)).tocsr()
    return H, G, B, shifted_B


@dataclass
class SteadyHeatResult:
    """temperature (N,) K, heat_flux (M,2) W/m^2, nodal forces (N,) W/m.

    reaction is residual=(K+H)*T-system_rhs on fixed nodes, zero on free nodes.
    Positive reaction injects heat; the Dirichlet thermostat outward contribution
    is -reaction. Total outward heat also includes prescribed and convective terms.
    All nodal heat rates are per unit out-of-plane thickness, not watts.
    """
    temperature: np.ndarray
    heat_flux: np.ndarray
    load: np.ndarray
    reaction: np.ndarray
    residual: np.ndarray
    prescribed_outward_load: np.ndarray | None = None
    ambient_load: np.ndarray | None = None
    convective_outward: np.ndarray | None = None
    system_rhs: np.ndarray | None = None


def solve_steady_heat(mesh, *, conductivity, dirichlet, heat_source=0.0,
                      outward_flux=None, convection=None):
    """Solve -div(k grad T)=Q with Dirichlet, outward flux and Robin data.

    conductivity is finite scalar k>0 in W/(m K), or {region name: k} with
    every mesh.region_names entry. heat_source is scalar Q, {region name: Q},
    or a callback receiving (Q,2) metre coordinates and returning (Q,) W/m^3.
    dirichlet maps exterior integer node indices to scalar temperatures in K;
    every disconnected component requires Dirichlet or positive Robin support.
    outward_flux maps edge tags to g; convection maps tags to (h, ambient).
    q.n = g+h*(T-ambient), h>=0. Boundary scalars or callbacks
    (points_m, outward_normals)->(Q,) use W/m^2, W/(m^2 K), K respectively.
    Untagged natural edges are insulated. See docs/packages/galerkin/thermal_flux_robin.md.
    """
    if not is_per_region(conductivity):
        k = _real(conductivity, "conductivity")
        if k.shape != () or k <= 0:
            raise ValueError("conductivity must be a finite scalar > 0")
        k = float(k)
    p, t, area, boundary, count, labels = _mesh_geometry(mesh)
    if is_per_region(conductivity):
        k = region_property(mesh, conductivity, "conductivity", positive=True)
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
    samples = _boundary_samples(mesh, p, t, prescribed, outward_flux, convection)
    H, G, B, shifted_B = _boundary_system(samples, len(p), labels, anchors, constrained)
    missing = np.flatnonzero(~constrained)
    if len(missing):
        raise ValueError(f"each connected component requires Dirichlet or positive Robin data; missing {missing.tolist()}")
    stiffness = assemble_stiffness(mesh, k)
    load = _source_load(mesh, p, t, area, heat_source)
    system = stiffness+H
    rhs = load+B-G
    shifted_rhs = load+shifted_B-G
    if not all(np.all(np.isfinite(a)) for a in
               (stiffness.data, H.data, load, G, B, shifted_B, rhs, shifted_rhs)):
        raise ValueError("assembled heat system exceeds floating-point range")
    shifted_bc = {(node,): value-anchors[labels[node]] for node, value in prescribed.items()}
    try:
        increment = solve_dirichlet(system, shifted_rhs, shifted_bc)
    except RuntimeError as exc:
        raise ValueError("singular or ill-conditioned constrained heat system") from exc
    temperature = increment+anchors[labels]
    # K annihilates constants; H does not. shifted_B integrates h*(ambient-offset).
    # Evaluate derivatives and convection before restoring absolute temperature.
    convective = H@increment-shifted_B
    residual = stiffness@increment+convective-load+G
    flux = -(k[:, None] if np.ndim(k) else k)*element_gradient(mesh, increment)
    if not all(np.all(np.isfinite(a)) for a in (temperature, residual, flux, convective)):
        raise ValueError("nonfinite heat solution, residual or heat flux")
    fixed = np.array(sorted(prescribed), dtype=int)
    free = np.setdiff1d(np.arange(len(p)), fixed)
    scale = max(np.linalg.norm(abs(system)@abs(increment)+abs(shifted_rhs), np.inf),
                np.finfo(float).tiny)
    if len(free) and np.linalg.norm(residual[free], np.inf) > 1e-10*scale:
        raise ValueError("heat solve failed the normalized free residual tolerance")
    reaction = np.zeros(len(p))
    reaction[fixed] = residual[fixed]
    for component in range(count):
        nodes = labels == component
        balance_scale = max(sum(np.sum(abs(a[nodes])) for a in
                                (load, reaction, G, convective)), np.finfo(float).tiny)
        if abs(np.sum((load+reaction-G-convective)[nodes])) > 1e-10*balance_scale:
            raise ValueError("heat solve failed the normalized component heat balance tolerance")
    return SteadyHeatResult(temperature, flux, load, reaction, residual,
                            G, B, convective, rhs)
