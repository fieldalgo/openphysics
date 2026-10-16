# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Planar domain description: named material regions bounded by polygons and circles.

A ``Domain`` is a set of regions that tile the area to be meshed. Each region
is a simple outer loop plus optional hole loops; a loop is either a polygon
(vertex list) or a ``Circle``. Regions may share edges and touch at
T-junctions — the domain resolves those into a single conforming set of
segments, which is what the mesher constrains.

Every geometric tolerance here is dimensionless and is scaled by the input's
own extent. meshine is never told what a length is: the same waveguide is 4.0
written in micrometres and 4e-6 written in metres, and an absolute tolerance
quietly means something different in each. See ``MERGE_EPS`` and ``PARAM_EPS``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np

Point2 = tuple[float, float]

#: Two points closer than ``MERGE_EPS`` times the diagonal of the input's bounding box
#: are the same point. Dimensionless on purpose: an absolute merge distance is a
#: statement about the unit the caller writes in. Measured, the absolute 1e-9 this
#: replaces was *half the domain* for a 220 nm device written in kilometres, so every
#: vertex collapsed onto one and the build died with "zero-length edge in input polygon".
MERGE_EPS = 1e-9

#: How far along a segment, as a fraction of that segment's own length, a point must sit
#: to count as strictly inside it. A separate constant from ``MERGE_EPS`` because a
#: position along a segment is dimensionless while a merge distance is a length: one
#: constant cannot carry both dimensions and still be right under a change of unit.
PARAM_EPS = 1e-9


class Circle:
    """Circular loop. Starts as an ``n``-gon; every vertex the mesher later inserts
    on one of its segments is projected back onto the true circle."""

    def __init__(self, center: Point2, radius: float, n: int = 32):
        if radius <= 0 or n < 8:
            raise ValueError("radius must be > 0 and n >= 8")
        self.center = np.asarray(center, dtype=float)
        self.radius = float(radius)
        self.n = int(n)

    def vertices(self) -> np.ndarray:
        th = np.linspace(0, 2 * np.pi, self.n, endpoint=False)
        return self.center + self.radius * np.column_stack([np.cos(th), np.sin(th)])

    def project(self, p: np.ndarray) -> np.ndarray:
        d = p - self.center
        r = np.hypot(*d)
        if r == 0:
            return self.center + np.array([self.radius, 0.0])
        return self.center + d * (self.radius / r)


@dataclass
class Region:
    name: str
    loops: list[list[int]]                  # vertex ids; loops[0] is the outer boundary
    size: float | None = None
    curves: list[Circle | None] = field(default_factory=list)


@dataclass
class Segment:
    a: int
    b: int
    curve: Circle | None
    owners: list[int]                       # region indices sharing this segment
    name: str | None = None                 # boundary name (outer segments only)

    @property
    def key(self) -> tuple[int, int]:
        return (min(self.a, self.b), max(self.a, self.b))


class Domain:
    def __init__(self, size: float = 0.1, *, merge_eps: float = MERGE_EPS,
                 param_eps: float = PARAM_EPS):
        self.default_size = float(size)
        self.merge_eps = float(merge_eps)
        self.param_eps = float(param_eps)
        self.point_tol = 0.0                # a length; ``build`` derives it from the input
        self.points: list[np.ndarray] = []
        self.regions: list[Region] = []
        self._pending: list[tuple[str, list, float | None]] = []

    # -- building ------------------------------------------------------------

    def add_region(self, name: str, outer, holes: Sequence = (), size: float | None = None) -> "Domain":
        """Add a material region. ``outer`` and each hole are a vertex sequence or a ``Circle``."""
        self._pending.append((name, [outer, *holes], size))
        return self

    @staticmethod
    def _loop_vertices(name: str, lp) -> np.ndarray:
        verts = lp.vertices() if isinstance(lp, Circle) else np.asarray(lp, dtype=float)
        if verts.ndim != 2 or verts.shape[1] != 2 or len(verts) < 3:
            raise ValueError(f"region {name!r}: a loop needs >= 3 vertices with 2 coordinates")
        return verts

    def extent(self) -> float:
        """Diagonal of the bounding box of every input vertex.

        The one length the caller supplies that every tolerance here is measured
        against. It is a property of the input, not of the unit it is written in.
        """
        lo = np.array([np.inf, np.inf])
        hi = np.array([-np.inf, -np.inf])
        for name, loops, _size in self._pending:
            for lp in loops:
                v = self._loop_vertices(name, lp)
                lo = np.minimum(lo, v.min(axis=0))
                hi = np.maximum(hi, v.max(axis=0))
        return float(np.hypot(*(hi - lo)))

    def _register(self, p) -> int:
        p = np.asarray(p, dtype=float)
        for i, q in enumerate(self.points):
            if abs(q[0] - p[0]) <= self.point_tol and abs(q[1] - p[1]) <= self.point_tol:
                return i
        self.points.append(p)
        return len(self.points) - 1

    def build(self, boundary_names: Callable[[Point2], str] | str = "outer"
              ) -> tuple[np.ndarray, list[Segment], list[Region]]:
        """Resolve shared edges and T-junctions; return points, segments, regions."""
        if not self._pending:
            raise ValueError("no regions added")
        diag = self.extent()
        if not np.isfinite(diag) or diag <= 0.0:
            raise ValueError(
                "Domain.build: the input has no extent: the bounding box of every region "
                "vertex has a zero diagonal, so every vertex is the same point. A domain "
                "needs a finite extent before any tolerance here means anything.")
        self.point_tol = self.merge_eps * diag
        self.points, self.regions = [], []
        raw_loops: list[list[tuple[list[int], Circle | None]]] = []
        for name, loops, size in self._pending:
            reg_loops = []
            for lp in loops:
                curve = lp if isinstance(lp, Circle) else None
                verts = self._loop_vertices(name, lp)
                reg_loops.append(([self._register(v) for v in verts], curve))
            raw_loops.append(reg_loops)
            self.regions.append(Region(name, [], size, []))

        pts = np.array(self.points)
        segs: dict[tuple[int, int], Segment] = {}
        for r, reg_loops in enumerate(raw_loops):
            region_name = self._pending[r][0]
            for ids, curve in reg_loops:
                chain: list[int] = []
                for k in range(len(ids)):
                    a, b = ids[k], ids[(k + 1) % len(ids)]
                    pieces = self._split(pts, a, b, region_name)
                    for s, t in pieces:
                        key = (min(s, t), max(s, t))
                        seg = segs.get(key)
                        if seg is None:
                            seg = Segment(s, t, curve, [])
                            segs[key] = seg
                        if r not in seg.owners:
                            seg.owners.append(r)
                        chain.append(s)
                self.regions[r].loops.append(chain)
                self.regions[r].curves.append(curve)

        for seg in segs.values():
            if len(seg.owners) == 1:
                mid = 0.5 * (pts[seg.a] + pts[seg.b])
                seg.name = boundary_names if isinstance(boundary_names, str) else boundary_names(tuple(mid))
            elif len(seg.owners) > 2:
                raise ValueError("a segment is shared by more than two regions; regions overlap")
        return pts, list(segs.values()), self.regions

    def _split(self, pts, a: int, b: int, region: str = "?") -> list[tuple[int, int]]:
        pa, pb = pts[a], pts[b]
        d = pb - pa
        L2 = float(d @ d)
        if L2 == 0:
            raise ValueError(
                f"Domain.build: region {region!r} has a zero-length edge. Two consecutive "
                f"vertices fell within the merge distance {self.point_tol:g} "
                f"({self.merge_eps:g} of the {self.extent():g}-unit domain diagonal) and became "
                f"one point. Either the loop repeats a vertex, or the feature is finer than "
                f"{self.merge_eps:g} of the domain that contains it.")
        inside = []
        w = pts - pa
        cross = np.abs(d[0] * w[:, 1] - d[1] * w[:, 0]) / np.sqrt(L2)
        s = (w @ d) / L2
        # ``cross`` is a perpendicular distance and takes the length tolerance; ``s`` is a
        # position along the segment as a fraction of its own length and takes the
        # dimensionless one. Using one constant for both was wrong in one of the two.
        for i in np.nonzero((cross <= self.point_tol)
                            & (s > self.param_eps) & (s < 1 - self.param_eps))[0]:
            if i not in (a, b):
                inside.append((s[i], int(i)))
        chain = [a] + [i for _, i in sorted(inside)] + [b]
        return list(zip(chain[:-1], chain[1:]))


def box_sides(xmin: float, xmax: float, ymin: float, ymax: float, eps: float = MERGE_EPS
              ) -> Callable[[Point2], str]:
    """Boundary namer for a rectangular domain: left / right / bottom / top.

    ``eps`` is a fraction of the box's own diagonal, not a distance. The same box is
    6 x 4 written in micrometres and 6e-6 x 4e-6 written in metres; a fixed distance
    names every edge of the second one "outer" and the solver loses its boundaries.
    """
    tol = eps * float(np.hypot(xmax - xmin, ymax - ymin))

    def namer(mid: Point2) -> str:
        x, y = mid
        if abs(x - xmin) <= tol:
            return "left"
        if abs(x - xmax) <= tol:
            return "right"
        if abs(y - ymin) <= tol:
            return "bottom"
        if abs(y - ymax) <= tol:
            return "top"
        return "outer"
    return namer


def rectangle(xmin: float, ymin: float, xmax: float, ymax: float) -> list[Point2]:
    return [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]


def points_in_loops(pts: np.ndarray, polys: Sequence[np.ndarray]) -> np.ndarray:
    """Even-odd test of points against a set of closed polygons (outer + holes)."""
    inside = np.zeros(len(pts), dtype=bool)
    x, y = pts[:, 0], pts[:, 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        for poly in polys:
            px, py = poly[:, 0], poly[:, 1]
            qx, qy = np.roll(px, -1), np.roll(py, -1)
            for i in range(len(poly)):
                cond = (py[i] > y) != (qy[i] > y)
                if not cond.any():
                    continue
                xs = (qx[i] - px[i]) * (y - py[i]) / (qy[i] - py[i]) + px[i]
                inside ^= cond & (x < xs)
    return inside
