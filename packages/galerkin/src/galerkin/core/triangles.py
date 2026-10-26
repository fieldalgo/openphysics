# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Checks and element data for conforming P1 triangle meshes."""
import itertools

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from ..mesh import Mesh
from .checks import real_array


def overlap_candidates(centers, radii, block=4096):
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


def triangle_geometry(mesh, *, counterclockwise=True):
    """Check a P1 triangle mesh and return (nodes, triangles, area, boundary, components, labels).

    The mesh must be a conforming manifold without unused or coincident nodes,
    duplicate or overlapping triangles, hinges or hanging nodes. With
    ``counterclockwise`` every triangle must be counter-clockwise; otherwise
    either orientation is accepted. ``boundary`` is the set of exterior nodes,
    ``labels`` the connected component of each node.
    """
    if not isinstance(mesh, Mesh):
        raise ValueError("mesh must be a galerkin.mesh.Mesh")
    p, t = real_array(mesh.nodes, "mesh.nodes"), np.asarray(mesh.triangles)
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
    j = q[:, 1:]-q[:, :1]
    det = j[:, 0, 0]*j[:, 1, 1]-j[:, 0, 1]*j[:, 1, 0]
    scale2 = np.max(np.sum(j*j, axis=2), axis=1)
    if counterclockwise:
        if np.any(~np.isfinite(det)) or np.any(det <= 1e-14*scale2):
            raise ValueError("triangles must be counter-clockwise and nondegenerate")
    elif np.any(~np.isfinite(det)) or np.any(abs(det) <= 1e-14*scale2):
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
            raise ValueError("nonmanifold vertex or triangles joined only at a point")
    centers = q.mean(axis=1)
    radii = np.linalg.norm(q-centers[:, None], axis=2).max(axis=1)
    for i, ids in overlap_candidates(centers, radii):
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
    return p, t, abs(det)/2, boundary, count, labels


def vector_strain(nodes, triangles):
    """Strain-displacement matrices (T,3,6) for [exx, eyy, gamma_xy] and DOFs (T,6).

    Two displacement components per node, DOF 2*node+component. The triangles
    must already have passed ``triangle_geometry``.
    """
    q = nodes[triangles]
    inv = np.linalg.inv(q[:, 1:]-q[:, :1])
    grad = np.stack([-inv.sum(axis=2), inv[:, :, 0], inv[:, :, 1]], axis=1)
    bmat = np.zeros((len(triangles), 3, 6))
    bmat[:, 0, 0::2] = grad[:, :, 0]
    bmat[:, 1, 1::2] = grad[:, :, 1]
    bmat[:, 2, 0::2] = grad[:, :, 1]
    bmat[:, 2, 1::2] = grad[:, :, 0]
    dofs = (2*triangles[:, :, None]+np.arange(2)).reshape(-1, 6)
    return bmat, dofs
