# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Pure helpers of the Studio 3D heat answers: the cut of a P1 field by an axis plane, and the probe.

Both work on the server's tetrahedra (``nodes`` (n, 3) in m, ``tets`` (m, 4)) and a nodal P1 field
``values`` (n,); neither imports the web stack.

``cut`` is the exact P1 slice: the plane ``x_axis = at`` meets a tetrahedron in a triangle or a
quadrilateral whose corners are its nodes on the plane and its edge crossings, where an edge (i, j)
with the nodes on either side is crossed at t = (at - x_i) / (x_j - x_i) and the field there is
v_i + t (v_j - v_i), the P1 field's own value. A crossing is computed once per edge, from its lower
node id, so a point shared by neighbouring tetrahedra is one point. A face lying in the plane (a
mesh face plane, or the domain's own face) is taken once: from the tetrahedron on its + side, or from
the only one it has. A quadrilateral is split on its shorter diagonal; every triangle faces +axis.

``probe`` answers the P1 interpolant at a point: the tetrahedron that holds it (barycentric
coordinates >= -1e-12; of several, the one the point is deepest in, then the lowest index), the
barycentric coordinates and the value; None outside the meshed regions.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

AXES = "xyz"
#: barycentric coordinates down to this count as inside (a point on a face or an edge)
INSIDE = -1e-12
#: tetrahedra visited per block by ``probe``
BLOCK = 65536


@dataclass(frozen=True)
class Cut:
    axis: str
    at: float
    points: np.ndarray          # (p, 3) float64, m; the axis coordinate is exactly ``at``
    triangles: np.ndarray       # (t, 3) int64 into points
    values: np.ndarray          # (p,) float64
    tetrahedra: np.ndarray      # (t,) int64: the tetrahedron each triangle lies in


@dataclass(frozen=True)
class Probe:
    point: np.ndarray
    tetrahedron: int
    barycentric: np.ndarray     # (4,) in the order of the tetrahedron's nodes
    value: float


def _axis(axis: str) -> int:
    if axis not in AXES:
        raise ValueError(f"axis must be one of x, y, z, not {axis!r}")
    return AXES.index(axis)


_EDGES = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))


def cut(nodes, tets, values, axis: str, at: float) -> Cut:
    """The exact P1 slice of ``values`` by the plane ``x_axis = at``."""
    a = _axis(axis)
    nodes = np.asarray(nodes, dtype=np.float64)
    tets = np.asarray(tets, dtype=np.int64)
    values = np.asarray(values, dtype=np.float64)
    at = float(at)
    d = nodes[:, a] - at
    s = np.sign(d).astype(np.int8)
    st = s[tets]
    pos, neg, zero = (st > 0).sum(1), (st < 0).sum(1), (st == 0).sum(1)
    crossed = np.flatnonzero((pos > 0) & (neg > 0))
    # faces in the plane: from the + side tetrahedron, else from the only one
    flat = np.flatnonzero(zero == 3)
    chosen_faces: dict[tuple, tuple[int, int]] = {}     # face -> (tet, side)
    for t in flat.tolist():
        face = tuple(sorted(int(n) for n, v in zip(tets[t], st[t]) if v == 0))
        side = 1 if pos[t] else -1
        old = chosen_faces.get(face)
        if old is None or (side > old[1]) or (side == old[1] and t < old[0]):
            chosen_faces[face] = (t, side)
    points: dict[tuple, int] = {}
    coords, vals = [], []

    def node_point(n):
        key = ("n", n)
        if key not in points:
            p = nodes[n].copy()
            p[a] = at
            points[key] = len(coords)
            coords.append(p)
            vals.append(values[n])
        return points[key]

    def edge_point(i, j):
        if i > j:
            i, j = j, i
        key = ("e", i, j)
        if key not in points:
            t = (at - nodes[i, a]) / (nodes[j, a] - nodes[i, a])
            p = nodes[i] + t * (nodes[j] - nodes[i])
            p[a] = at
            points[key] = len(coords)
            coords.append(p)
            vals.append(values[i] + t * (values[j] - values[i]))
        return points[key]

    tris, owner = [], []
    u, v = (a + 1) % 3, (a + 2) % 3

    def emit(t, corner_ids):
        if len(corner_ids) == 3:
            groups = [corner_ids]
        else:
            q = np.array([coords[k] for k in corner_ids])
            centre = q.mean(0)
            order = np.argsort(np.arctan2(q[:, v] - centre[v], q[:, u] - centre[u]))
            c = [corner_ids[k] for k in order]
            p = np.array([coords[k] for k in c])
            if np.linalg.norm(p[0] - p[2]) <= np.linalg.norm(p[1] - p[3]):
                groups = [[c[0], c[1], c[2]], [c[0], c[2], c[3]]]
            else:
                groups = [[c[0], c[1], c[3]], [c[1], c[2], c[3]]]
        for g in groups:
            p0, p1, p2 = (coords[k] for k in g)
            n = (p1[u] - p0[u]) * (p2[v] - p0[v]) - (p1[v] - p0[v]) * (p2[u] - p0[u])
            if n < 0:
                g = [g[0], g[2], g[1]]
            tris.append(g)
            owner.append(t)

    for t in crossed.tolist():
        tet, sg = tets[t], st[t]
        ids = [node_point(int(tet[k])) for k in range(4) if sg[k] == 0]
        ids += [edge_point(int(tet[i]), int(tet[j])) for i, j in _EDGES if sg[i] * sg[j] < 0]
        emit(t, ids)
    for face, (t, _side) in sorted(chosen_faces.items(), key=lambda kv: kv[1][0]):
        emit(t, [node_point(n) for n in face])
    pts = np.array(coords, dtype=np.float64).reshape(-1, 3)
    return Cut(axis, at, pts, np.array(tris, dtype=np.int64).reshape(-1, 3),
               np.array(vals, dtype=np.float64), np.array(owner, dtype=np.int64))


def probe(nodes, tets, values, point) -> Probe | None:
    """The P1 interpolant of ``values`` at ``point`` (m), or None outside every tetrahedron."""
    nodes = np.asarray(nodes, dtype=np.float64)
    tets = np.asarray(tets, dtype=np.int64)
    p = np.asarray(point, dtype=np.float64).reshape(3)
    best = None                                         # (depth, tet, barycentric)
    for start in range(0, len(tets), BLOCK):
        block = tets[start:start + BLOCK]
        c = nodes[block]
        lo, hi = c.min(1), c.max(1)
        near = np.flatnonzero(np.all((lo <= p) & (p <= hi), axis=1))
        if not len(near):
            continue
        c = c[near]
        m = np.stack([c[:, 1] - c[:, 0], c[:, 2] - c[:, 0], c[:, 3] - c[:, 0]], axis=2)   # columns
        lam = np.linalg.solve(m, (p - c[:, 0])[:, :, None])[:, :, 0]
        bary = np.column_stack([1.0 - lam.sum(1), lam])
        depth = bary.min(1)
        k = int(np.argmax(depth))
        if depth[k] >= INSIDE and (best is None or depth[k] > best[0]):
            best = (float(depth[k]), start + int(near[k]), bary[k])
    if best is None:
        return None
    _, t, bary = best
    value = float(bary @ np.asarray(values, dtype=np.float64)[tets[t]])
    return Probe(p, t, bary, value)
