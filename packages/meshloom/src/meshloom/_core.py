# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Numpy wrappers of the compiled kernel's building blocks (internal, not public API).

The exact predicates and the Delaunay tetrahedralization are the first stages of
the mesher. They are exposed here for the pre-registered checks (V16, V17) and the
benchmark; the public mesher API comes with a later release and may change them.
"""

from __future__ import annotations

import numpy as np

from . import KernelUnavailable, _IMPORT_ERROR, _kernel

_GROUP = {"orient2d_proj": 3, "orient3d": 4, "incircle3d": 4, "incircle_plane": 4, "incircle_plane_sos": 4,
          "insphere": 5, "insphere_sos": 5}


def _require():
    if _kernel is None:
        raise KernelUnavailable(f"meshloom's compiled kernel is not available here: {_IMPORT_ERROR}")
    return _kernel


def _points(points) -> np.ndarray:
    p = np.ascontiguousarray(points, dtype="<f8")
    if p.ndim != 2 or p.shape[1] != 3:
        raise ValueError(f"points must have shape (n, 3), got {p.shape}")
    return p


def predicate_signs(kind: str, coords, ids=None, axis: int = 2) -> np.ndarray:
    """Exact signs of one predicate over a batch.

    ``coords`` has shape (n, k, 3) with k = 4 for ``orient3d`` and ``incircle3d`` and
    k = 5 for ``insphere`` and ``insphere_sos``; ``ids`` (n, 5) gives the global point
    indices that order the perturbation of ``insphere_sos``. Returns n int8 values in
    {-1, 0, 1}. Conventions: orient3d(a, b, c, d) = det[b - a, c - a, d - a];
    insphere > 0 when e is inside the sphere through a positively oriented a, b, c, d;
    incircle3d > 0 when coplanar d is inside the circle through a, b, c.

    In-plane kinds take ``axis``, the coordinate dropped for the projection:
    ``orient2d_proj`` (k = 3) is component ``axis`` of (b - a) x (c - a);
    ``incircle_plane`` (k = 4) is positive when coplanar d is inside the circle through
    a, b, c given counter-clockwise in that projection, and ``incircle_plane_sos``
    breaks its ties with the same index-ordered perturbation (``ids`` n x 4).
    """
    kernel = _require()
    k = _GROUP.get(kind)
    if k is None:
        raise ValueError(f"unknown predicate {kind!r}")
    c = np.ascontiguousarray(coords, dtype="<f8")
    if c.ndim != 3 or c.shape[1:] != (k, 3):
        raise ValueError(f"{kind} takes coordinates of shape (n, {k}, 3), got {c.shape}")
    i = None
    if ids is not None:
        i = np.ascontiguousarray(ids, dtype="<i8")
        if i.shape != c.shape[:2]:
            raise ValueError(f"ids must have shape {c.shape[:2]}, got {i.shape}")
        i = i.tobytes()
    out = kernel.predicate_signs(kind, c.tobytes(), i, axis)
    return np.frombuffer(out, dtype=np.int8).copy()


def delaunay(points, order=None) -> tuple[np.ndarray, np.ndarray, dict]:
    """Delaunay tetrahedralization of ``points`` (n, 3).

    Returns ``(tetrahedra, vertex_of, stats)``: positively oriented tetrahedra (T, 4)
    int64 indexing ``points``; for each point the index of the equal point that is
    the vertex (the lowest index of its group), and the kernel counters. Ties of
    cospherical points are broken by a symbolic perturbation ordered by point index,
    so the result does not depend on the insertion order. ``order`` (a permutation of
    the indices) fixes the insertion order; by default a biased randomized order
    with Hilbert rounds is used.
    """
    kernel = _require()
    p = _points(points)
    o = None if order is None else np.ascontiguousarray(order, dtype="<i8").tobytes()
    tets, vertex_of, stats = kernel.delaunay(p.tobytes(), o)
    # astype copies into a writable native int64 array (the bytes are read-only)
    return (np.frombuffer(tets, dtype="<i8").reshape(-1, 4).astype(np.int64),
            np.frombuffer(vertex_of, dtype="<i8").astype(np.int64), stats)


def verify_delaunay(points, tetrahedra) -> dict:
    """Check that ``tetrahedra`` is the Delaunay tetrahedralization of the distinct
    ``points`` under the index-ordered perturbation, from the arrays alone, with exact
    predicates. Raises ``ValueError`` naming the first violation; returns counts."""
    kernel = _require()
    p = _points(points)
    t = np.ascontiguousarray(tetrahedra, dtype="<i8")
    if t.ndim != 2 or t.shape[1] != 4:
        raise ValueError(f"tetrahedra must have shape (T, 4), got {t.shape}")
    return kernel.verify_delaunay(p.tobytes(), t.tobytes())


def triangulate_facet(points, loops) -> tuple[np.ndarray, int]:
    """Constrained Delaunay triangulation of one planar facet.

    ``loops`` lists index arrays into ``points``: the outer loop first, then holes,
    combined by the even-odd rule. The points must be exactly coplanar; loops must be
    simple and must not touch. Returns triangles (T, 3) wound like the outer loop, and
    the coordinate axis dropped for the in-plane predicates. Ties of cocircular points
    are broken by the same index-ordered perturbation as ``delaunay``.
    """
    kernel = _require()
    p = _points(points)
    lp = [np.ascontiguousarray(x, dtype="<i8").tobytes() for x in loops]
    tris, axis = kernel.triangulate_facet(p.tobytes(), lp)
    return np.frombuffer(tris, dtype="<i8").reshape(-1, 3).astype(np.int64), axis


class InvalidPLC(ValueError):
    """A refused PLC. ``witness_type`` is the type of the import validity rule the
    refusal is a witness of (0 no facets, 1 a coordinate outside the kernel's range,
    2 a repeated vertex in a facet, 3 a degenerate, non-planar or non-simple facet,
    4 two facets with the same vertices, 5 two cells whose intersection is not a union
    of cells), or ``None`` for malformed arrays (an index that does not exist,
    coincident points)."""

    def __init__(self, message: str, witness_type: int | None):
        super().__init__(message)
        self.witness_type = witness_type


def check_plc(points, segments, facets) -> dict:
    """Exact validity check of a piecewise linear complex.

    ``segments`` (m, 2) and ``facets`` (a list of facets, each a list of loops of point
    indices, outer loop first) describe the PLC; every loop edge is an edge too. Valid
    means: distinct points in the kernel's range, exactly planar facets with simple
    loops, and every two cells (points, edges, facets) meeting in a union of cells. So
    a point may lie inside an edge or a facet (a T-junction), an edge inside a facet,
    and a facet inside a coplanar facet; crossings, piercings, partial collinear
    overlaps and coplanar overlaps that no cell of both covers are refused.

    Raises ``InvalidPLC`` naming the first violation. Returns the edges, the elementary
    sub-segments (edges split at the points on them), the facet triangles (each facet
    triangulated with the points and sub-segments on it) with the facet of each, the
    sub-segments on the boundary of an odd number of facets (empty when the PLC is
    closed) and the number of candidate pairs tested.
    """
    kernel = _require()
    p = _points(points)
    s = np.ascontiguousarray(np.asarray(segments, dtype="<i8").reshape(-1, 2))
    f = [[np.ascontiguousarray(lp, dtype="<i8").tobytes() for lp in facet] for facet in facets]
    try:
        seg, sub, tris, owner, opened, pairs = kernel.check_plc(p.tobytes(), s.tobytes(), f)
    except ValueError as e:
        if len(e.args) == 2:
            raise InvalidPLC(*e.args) from None
        raise

    def pairs_of(b):
        return np.frombuffer(b, dtype="<i8").reshape(-1, 2).astype(np.int64)

    return {"segments": pairs_of(seg), "subsegments": pairs_of(sub),
            "triangles": np.frombuffer(tris, dtype="<i8").reshape(-1, 3).astype(np.int64),
            "triangle_facet": np.frombuffer(owner, dtype="<i8").astype(np.int64),
            "open_subsegments": pairs_of(opened), "pairs_tested": pairs}
