# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Numpy wrappers of the compiled kernel's building blocks (internal, not public API).

The exact predicates and the Delaunay tetrahedralization are the first stages of
the mesher. They are exposed here for the pre-registered checks (V16, V17) and the
benchmark; the public mesher API comes with a later release and may change them.
"""

from __future__ import annotations

from fractions import Fraction

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


def mixed_predicate_signs(kind: str, points, segments, t, query, axis: int = 2) -> tuple[np.ndarray, dict]:
    """Exact signs of one predicate over points stored on segments (S points) and input
    points.

    ``points`` (n, 3) are the input points; S point ``j`` lies on the segment
    ``segments[j]`` = (a, b) at ``points[a] + t[j] * (points[b] - points[a])``, with
    ``0 < t[j] < 1``. ``query`` (g, k) gives each group's points by global index: input
    points ``0..n``, S points ``n..n+m``, the same indices that order the perturbation
    of the ``_sos`` kinds. Kinds and conventions are those of ``predicate_signs``
    (``orient3d``, ``insphere``, ``insphere_sos``; in-plane ``orient2d_proj``,
    ``incircle_plane``, ``incircle_plane_sos`` with ``axis``). The coordinates of S
    points are never rounded: an interval filter decides most signs and exact dyadic
    big integers the rest. Returns the signs (int8) and call counters.
    """
    kernel = _require()
    p = _points(points)
    seg = np.ascontiguousarray(np.asarray(segments, dtype="<i8").reshape(-1, 2))
    tt = np.ascontiguousarray(np.asarray(t, dtype="<f8").reshape(-1))
    q = np.ascontiguousarray(np.asarray(query, dtype="<i8"))
    out, counts = kernel.mixed_signs(kind, p.tobytes(), seg.tobytes(), tt.tobytes(), q.tobytes(), axis)
    return np.frombuffer(out, dtype=np.int8).copy(), counts


def spoint_coords(points, segments, t) -> np.ndarray:
    """Output coordinates of S points (see ``mixed_predicate_signs``): each coordinate of
    ``points[a] + t * (points[b] - points[a])`` rounded once to the nearest double
    (ties to even). The predicates never use these; they are for output. Returns (m, 3).
    """
    kernel = _require()
    p = _points(points)
    seg = np.ascontiguousarray(np.asarray(segments, dtype="<i8").reshape(-1, 2))
    tt = np.ascontiguousarray(np.asarray(t, dtype="<f8").reshape(-1))
    out = kernel.spoint_coords(p.tobytes(), seg.tobytes(), tt.tobytes())
    return np.frombuffer(out, dtype="<f8").reshape(-1, 3).astype(np.float64)


def recover_segments(points, segments, max_depth: int = 60) -> dict:
    """Segment recovery (boundary recovery, first part): the Delaunay
    tetrahedralization of ``points`` (n, 3) with points added on the ``segments``
    (m, 2) until every segment is a union of edges.

    The segments must be elementary and must not cross: the ``subsegments`` of
    ``check_plc``. New points are S points on input segments (see
    ``mixed_predicate_signs``): first at acute vertices (where two segments meet at less
    than 90 degrees), then by halving every piece that is not an edge, at most
    ``max_depth`` times per piece. Returns a dict with ``tetrahedra`` (T, 4) over global
    indices (input points, then S points), ``s_segments`` (k, 2) and ``s_t`` (k,) of the
    S points, ``chains`` (one index array per segment, from its first point to its
    second through its S points) and counters. Too deep a recovery raises
    ``RuntimeError``; bad input raises ``ValueError``.
    """
    kernel = _require()
    p = _points(points)
    s = np.ascontiguousarray(np.asarray(segments, dtype="<i8").reshape(-1, 2))
    tets, sseg, st, lens, chains, stats = kernel.recover_segments(p.tobytes(), s.tobytes(), max_depth)
    flat = np.frombuffer(chains, dtype="<i8").astype(np.int64)
    cuts = np.cumsum(np.frombuffer(lens, dtype="<i8"))[:-1]
    return {"tetrahedra": np.frombuffer(tets, dtype="<i8").reshape(-1, 4).astype(np.int64),
            "s_segments": np.frombuffer(sseg, dtype="<i8").reshape(-1, 2).astype(np.int64),
            "s_t": np.frombuffer(st, dtype="<f8").astype(np.float64),
            "chains": np.split(flat, cuts) if len(lens) else [],
            "stats": stats}


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
    coincident points).

    ``witness`` names what can be checked, or is ``None``: ``{"type": 0, "reason":
    "no facets"}``, ``{"type": 1, "vertex": i}``, ``{"type": 2 or 3, "facet": f}``,
    ``{"type": 4, "facets": (f, g)}`` or ``{"type": 5, "cells": (c, d), "point": p}``,
    where ``p`` is an exact point (three ``Fraction``) in both cells that lies in no
    cell contained in both. A cell is ``("facet", f)``, or ``("segment", (u, v))`` for
    a free segment that lies in no facet; when both are facets, ``"facets": (f, g)``
    repeats them."""

    def __init__(self, message: str, witness_type: int | None, witness: dict | None = None):
        super().__init__(message)
        self.witness_type = witness_type
        self.witness = witness


def _sub(a, b):
    return [x - y for x, y in zip(a, b)]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _seg_tri_points(a, b, t):
    """Endpoints of the exact intersection of segment a-b with the closed triangle t
    (Fraction coordinates); empty when they do not meet."""
    nrm = _cross(_sub(t[1], t[0]), _sub(t[2], t[0]))
    oa, ob = _dot(nrm, _sub(a, t[0])), _dot(nrm, _sub(b, t[0]))
    k = max(range(3), key=lambda i: abs(nrm[i]))  # dropped axis
    i, j = [(1, 2), (2, 0), (0, 1)][k]

    def o2(p, q, r):
        return (q[i] - p[i]) * (r[j] - p[j]) - (q[j] - p[j]) * (r[i] - p[i])

    sigma = 1 if o2(*t) > 0 else -1

    def at(s):
        return [x + s * (y - x) for x, y in zip(a, b)]

    if oa == 0 and ob == 0:  # coplanar: clip the parameter interval by the three edges
        lo, hi = Fraction(0), Fraction(1)
        for p, q in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            f0, f1 = sigma * o2(p, q, a), sigma * o2(p, q, b)
            if f0 < 0 and f1 < 0:
                return []
            if f0 < 0:
                lo = max(lo, f0 / (f0 - f1))
            elif f1 < 0:
                hi = min(hi, f0 / (f0 - f1))
        return [] if lo > hi else [at(lo), at(hi)]
    if (oa > 0 and ob > 0) or (oa < 0 and ob < 0):
        return []
    p = at(oa / (oa - ob))
    inside = all(sigma * o2(u, v, p) >= 0 for u, v in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])))
    return [p] if inside else []


def _witness_point(kind, ids, pts):
    """The exact witness point of a type-5 refusal from the pieces the kernel names."""
    q = [[Fraction(float(c)) for c in pts[v]] for v in ids]

    def mean(ps):
        return [sum(c) / len(ps) for c in zip(*ps)] if ps else None

    if kind == "centroid":
        return mean(q)
    if kind == "segseg":
        a, b, c, d = q
        d1, d2 = _sub(b, a), _sub(d, c)
        n = _cross(d1, d2)
        s = _dot(_cross(_sub(c, a), d2), n) / _dot(n, n)
        return [x + s * y for x, y in zip(a, d1)]
    if kind == "segtri":
        return mean(_seg_tri_points(q[0], q[1], q[2:]))
    if kind == "tritri":
        t, u = q[:3], q[3:]
        ps = []
        for x, y in ((t, u), (u, t)):
            for m in range(3):
                ps += _seg_tri_points(x[m], x[(m + 1) % 3], y)
        return mean(ps)
    return None


def _witness(wtype, kind, ids, pts):
    if wtype is None or not kind:
        return None
    if kind == "no facets":
        return {"type": 0, "reason": "no facets"}
    if kind == "vertex":
        return {"type": wtype, "vertex": ids[0]}
    if kind == "facet":
        return {"type": wtype, "facet": ids[0]}
    if kind == "facets":
        return {"type": wtype, "facets": (ids[0], ids[1])}
    point = _witness_point(kind, ids[4:], pts)
    if point is None:
        return None
    cells = [("facet", b) if a == -1 else ("segment", (a, b)) for a, b in (ids[0:2], ids[2:4])]
    w = {"type": wtype, "cells": tuple(cells), "point": tuple(point)}
    if all(kind == "facet" for kind, _ in cells):
        w["facets"] = (cells[0][1], cells[1][1])
    return w


def check_plc(points, segments, facets) -> dict:
    """Exact validity check of a piecewise linear complex.

    ``segments`` (m, 2) and ``facets`` (a list of facets, each a list of loops of point
    indices, outer loop first) describe the PLC; every loop edge is an edge too. Valid
    means: distinct points in the kernel's range, exactly planar facets with simple
    loops, and every two cells (points, edges, facets) meeting in a union of cells. So
    a point may lie inside an edge or a facet (a T-junction), an edge inside a facet,
    and a facet inside a coplanar facet; crossings, piercings, partial collinear
    overlaps and coplanar overlaps that no cell of both covers are refused.

    Raises ``InvalidPLC`` naming the first violation, with a witness that can be
    checked independently. Returns the edges, the elementary
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
        if len(e.args) == 4:
            msg, wtype, kind, ids = e.args
            raise InvalidPLC(msg, wtype, _witness(wtype, kind, list(ids), p)) from None
        raise

    def pairs_of(b):
        return np.frombuffer(b, dtype="<i8").reshape(-1, 2).astype(np.int64)

    return {"segments": pairs_of(seg), "subsegments": pairs_of(sub),
            "triangles": np.frombuffer(tris, dtype="<i8").reshape(-1, 3).astype(np.int64),
            "triangle_facet": np.frombuffer(owner, dtype="<i8").astype(np.int64),
            "open_subsegments": pairs_of(opened), "pairs_tested": pairs}
