# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Checks and element data for conforming P1 triangle meshes.

``triangle_geometry`` keeps its validated output in a small cache keyed by the
mesh content (see ``GEOMETRY_CACHE_ENTRIES``), so the solvers that check the
same mesh repeatedly validate it once.
"""
import hashlib
import itertools
import threading
from collections import OrderedDict

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from ..mesh import Mesh
from .backend import is_live
from .checks import real_array

# Validated geometries kept, least recently used first. One entry holds copies
# of the node and triangle arrays, the areas, the boundary set and the labels: a
# few MB for a mesh of 30k nodes. Eight entries cover the meshes a coupled
# workflow or a test module alternates between without holding every mesh of a
# convergence study.
GEOMETRY_CACHE_ENTRIES = 8
_geometry_cache = OrderedDict()
_edge_cache = OrderedDict()
_geometry_lock = threading.Lock()


def clear_geometry_cache():
    """Forget every cached ``triangle_geometry`` result."""
    with _geometry_lock:
        _geometry_cache.clear()
        _edge_cache.clear()


def _content_key(nodes, triangles, extra):
    """Key of a mesh's content, or None when the arrays must go through the checks first.

    The SHA-256 of each array's dtype, shape and C-order bytes, with ``extra``
    (the orientation flag, or the node count of an edge table) beside it: two
    meshes share a key exactly when their coordinates and connectivity are
    byte-identical, so a mesh changed in place (``mesh.nodes += origin``) is
    validated afresh and a mesh of another dtype never reuses a result.
    JAX/PyTorch arrays, booleans and non-numeric dtypes are left to the checks,
    which refuse them.
    """
    if is_live(nodes) or is_live(triangles):
        return None
    try:
        nodes, triangles = np.asarray(nodes), np.asarray(triangles)
    except (TypeError, ValueError):
        return None
    if nodes.dtype.kind not in "iuf" or triangles.dtype.kind not in "iu":
        return None
    digest = hashlib.sha256()
    for array in (nodes, triangles):
        digest.update(repr((array.dtype.str, array.shape)).encode("ascii"))
        digest.update(np.ascontiguousarray(array).tobytes())
    return digest.digest(), extra


def overlap_pairs(centers, radii, block=4096):
    """Arrays (lo, hi), lo < hi, sorted by lo then hi: every pair whose interiors may overlap.

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
    return np.divmod(key[np.diff(key, prepend=-1) != 0], count)


def overlap_candidates(centers, radii, block=4096):
    """Yield (i, ids), ids > i ascending: the pairs of ``overlap_pairs`` grouped by their lower index."""
    lo, hi = overlap_pairs(centers, radii, block=block)
    bounds = np.searchsorted(lo, np.arange(len(centers)+1))
    for i in np.flatnonzero(bounds[1:] > bounds[:-1]):
        yield int(i), hi[bounds[i]:bounds[i+1]]


def _interiors_overlap(q, centers, radii, chunk=1 << 16):
    """Whether any two triangles' interiors overlap: a separating-axis test on every candidate pair.

    A pair (i, k) is kept when the centroid distance is below r_i + r_k, then the
    six edge normals of both triangles, taken relative to centroid i, are tried
    as separating axes; the interiors overlap when the projections overlap on
    every axis by more than 1e-12 of the larger radius. The pairs are processed
    in chunks so memory stays a few MB whatever the mesh size.
    """
    lo, hi = overlap_pairs(centers, radii)
    keep = np.linalg.norm(centers[hi]-centers[lo], axis=1) < radii[hi]+radii[lo]
    lo, hi = lo[keep], hi[keep]
    for start in range(0, len(lo), chunk):
        i, k = lo[start:start+chunk], hi[start:start+chunk]
        here, other = q[i]-centers[i][:, None], q[k]-centers[i][:, None]
        de = np.concatenate([np.roll(here, -1, axis=1)-here, np.roll(other, -1, axis=1)-other], axis=1)
        axes = np.stack([-de[..., 1], de[..., 0]], axis=-1)
        axes /= np.linalg.norm(axes, axis=2)[..., None]
        pa, pb = np.einsum("pvd,pad->pav", here, axes), np.einsum("pvd,pad->pav", other, axes)
        overlap = np.minimum(pa.max(axis=2), pb.max(axis=2))-np.maximum(pa.min(axis=2), pb.min(axis=2))
        if np.any(np.all(overlap > 1e-12*np.maximum(radii[i], radii[k])[:, None], axis=1)):
            return True
    return False


def edge_table(triangles, nodes):
    """The edges of a (T, 3) triangle array: (edges, counts, slots), cached by content.

    The boundary samplers look selected edges up here instead of rebuilding an
    owner table over every triangle, so the table is kept under the content of
    ``triangles`` (and ``nodes``) in a cache bounded like the geometry cache and
    returned read-only; ``clear_geometry_cache`` empties it too.

    ``edges`` (E, 2) lists each distinct edge once as (low, high) node, sorted
    by low*nodes+high; ``counts`` (E,) is the number of triangles that contain
    it; ``slots`` (3T,) the flat index 3*triangle+local edge of every
    occurrence, grouped by edge in that order (local edge e joins vertices e and
    e+1 mod 3, so the vertex opposite slot k is triangle k//3's vertex
    (k%3+2)%3). Within a group the triangles ascend: ``slots[first]//3`` is the
    lowest triangle containing an edge, its only one on the boundary.
    """
    t = np.asarray(triangles)
    key = _content_key(np.zeros(0), t, nodes) if t.dtype.kind in "iu" else None
    if key is not None:
        with _geometry_lock:
            found = _edge_cache.get(key)
            if found is not None:
                _edge_cache.move_to_end(key)
                return found
    first, second = t, np.roll(t, -1, axis=1)
    flat = (np.minimum(first, second)*nodes+np.maximum(first, second)).ravel()
    unique, inverse, counts = np.unique(flat, return_inverse=True, return_counts=True)
    table = np.column_stack(np.divmod(unique, nodes)), counts, np.argsort(inverse.ravel(), kind="stable")
    for array in table:
        array.flags.writeable = False
    if key is not None:
        with _geometry_lock:
            _edge_cache[key] = table
            _edge_cache.move_to_end(key)
            while len(_edge_cache) > GEOMETRY_CACHE_ENTRIES:
                _edge_cache.popitem(last=False)
    return table


def _fans_connected(t, counts, slots, nodes):
    """Whether the triangles at every vertex form one fan joined through shared edges.

    Each triangle corner (triangle, vertex) is a node of a graph; an interior
    edge links the corners its two triangles have at each of its endpoints.
    Corners of different vertices are never linked, so the fans are connected
    exactly when the graph has one component per mesh vertex. Two triangles
    both containing a vertex and sharing an edge share an edge at that vertex
    (otherwise they would be the same triangle), so this is the depth-first
    search over each vertex's incident triangles, restricted to its own edges.
    """
    corner = np.arange(3*len(t)).reshape(len(t), 3)
    ahead = np.roll(corner, -1, axis=1)
    low_first = t <= np.roll(t, -1, axis=1)
    low = np.where(low_first, corner, ahead).ravel()
    high = np.where(low_first, ahead, corner).ravel()
    shared = slots[np.repeat(counts == 2, counts)].reshape(-1, 2)
    rows = np.concatenate([low[shared[:, 0]], high[shared[:, 0]]])
    cols = np.concatenate([low[shared[:, 1]], high[shared[:, 1]]])
    graph = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(3*len(t), 3*len(t)))
    components, _ = connected_components(graph, directed=False)
    return components == nodes


def _splits_edge(p, a, b, node):
    """The scalar test: ``node`` lies strictly inside the segment from ``a`` to ``b``."""
    v = p[b]-p[a]
    length = np.linalg.norm(v)
    w = p[node]-p[a]
    s = w@v/(length*length)
    return 1e-12 < s < 1-1e-12 and abs(v[0]*w[1]-v[1]*w[0]) <= 1e-12*length*length


def _node_inside_edge(p, edges, band=1e-9):
    """Whether some node lies strictly inside some edge: a hanging node of a nonconforming mesh.

    One ball query finds, for every edge, the nodes within half its length of its
    midpoint (with the 1e-12 margin); the edge's own ends are dropped. A node is
    inside when its parameter s along the edge is in (1e-12, 1-1e-12) and its
    cross product with the edge is at most 1e-12 of the squared length. These
    values are computed for all candidates at once; where one is within
    ``band`` of its threshold the scalar expressions decide, so the vectorised
    arithmetic (which may differ from the scalar one in the last bit) never
    changes a decision.
    """
    a, b = edges[:, 0], edges[:, 1]
    v = p[b]-p[a]
    length = np.linalg.norm(v, axis=1)
    found = cKDTree(p).query_ball_point((p[a]+p[b])/2, length/2*(1+1e-12))
    sizes = np.fromiter(map(len, found), dtype=np.int64, count=len(found))
    edge = np.repeat(np.arange(len(edges)), sizes)
    node = np.fromiter(itertools.chain.from_iterable(found), dtype=np.int64, count=len(edge))
    del found
    keep = (node != a[edge]) & (node != b[edge])
    edge, node = edge[keep], node[keep]
    w, ve, l2 = p[node]-p[a[edge]], v[edge], (length*length)[edge]
    s = (w[:, 0]*ve[:, 0]+w[:, 1]*ve[:, 1])/l2
    cross = np.abs(ve[:, 0]*w[:, 1]-ve[:, 1]*w[:, 0])
    inside = (1e-12 < s) & (s < 1-1e-12) & (cross <= 1e-12*l2)
    near = (np.abs(s-1e-12) <= band) | (np.abs(s-(1-1e-12)) <= band) | (np.abs(cross-1e-12*l2) <= band*l2)
    if np.any(inside & ~near):
        return True
    return any(_splits_edge(p, a[e], b[e], k) for e, k in zip(edge[near], node[near]))


def triangle_geometry(mesh, *, counterclockwise=True):
    """Check a P1 triangle mesh and return (nodes, triangles, area, boundary, components, labels).

    The mesh must be a conforming manifold without unused or coincident nodes,
    duplicate or overlapping triangles, hinges or hanging nodes. With
    ``counterclockwise`` every triangle must be counter-clockwise; otherwise
    either orientation is accepted. ``boundary`` is the set of exterior nodes,
    ``labels`` the connected component of each node.

    A result is cached under the content of ``mesh.nodes`` and ``mesh.triangles``
    (``GEOMETRY_CACHE_ENTRIES`` meshes, least recently used dropped), so the
    same mesh is checked once however many solver calls it enters. Every call
    returns its own copies: changing them never changes a later result.
    """
    if not isinstance(mesh, Mesh):
        raise ValueError("mesh must be a galerkin.mesh.Mesh")
    key = _content_key(mesh.nodes, mesh.triangles, bool(counterclockwise))
    if key is not None:
        with _geometry_lock:
            found = _geometry_cache.get(key)
            if found is not None:
                _geometry_cache.move_to_end(key)
        if found is not None:
            return _copies(found)
    result = _validated_geometry(mesh, counterclockwise)
    if key is not None:
        with _geometry_lock:
            _geometry_cache[key] = result
            _geometry_cache.move_to_end(key)
            while len(_geometry_cache) > GEOMETRY_CACHE_ENTRIES:
                _geometry_cache.popitem(last=False)
    return _copies(result)


def _copies(result):
    p, t, area, boundary, count, labels = result
    return p.copy(), t.copy(), area.copy(), set(boundary), count, labels.copy()


def _validated_geometry(mesh, counterclockwise):
    """The checks behind ``triangle_geometry``, on a mesh not seen before."""
    p, t = real_array(mesh.nodes, "mesh.nodes"), np.array(mesh.triangles)
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
    edges, counts, slots = edge_table(t, len(p))
    if counts.max() > 2:
        raise ValueError("nonmanifold mesh edge")
    boundary = frozenset(np.unique(edges[counts == 1]).tolist())
    if not _fans_connected(t, counts, slots, len(p)):
        raise ValueError("nonmanifold vertex or triangles joined only at a point")
    centers = q.mean(axis=1)
    radii = np.linalg.norm(q-centers[:, None], axis=2).max(axis=1)
    if _interiors_overlap(q, centers, radii):
        raise ValueError("mesh triangles have overlapping interiors")
    if _node_inside_edge(p, edges):
        raise ValueError("nonconforming mesh: node inside an edge")
    row, col = np.repeat(t, 3, axis=1).ravel(), np.tile(t, (1, 3)).ravel()
    graph = coo_matrix((np.ones(len(row)), (row, col)), shape=(len(p), len(p)))
    count, labels = connected_components(graph, directed=False)
    return p, t, abs(det)/2, frozenset(boundary), count, labels


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
