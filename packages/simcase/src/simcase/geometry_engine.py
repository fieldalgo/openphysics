# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Geometry document version 1: the exact 2D engine (stage 2).

``evaluate`` turns one 2D or axisymmetric component of a parsed geometry block
(``simcase.geometry_document``) into the region complex that
``docs/packages/simcase/geometry_document.md`` defines: cells with a region name,
a material and the feature that owns them; curves of kind ``line``, ``arc`` or
``circle`` with exact parameters, the provenance names of every feature part
whose source curve contains them, and the cell on each side; and vertices.

Everything is exact. Defining values are integer picometres. Intersections of
lines are rational; intersections with circles are quadratic numbers a + b*sqrt(D).
Every predicate (point order along a curve, angular order around a vertex, the
orientation of a cycle, the parity of a ray against a cycle) is decided with
integer arithmetic, so a touch stays a touch whatever unit the document declares
and whatever the coordinates are. No floating point enters before the hand-off
to the mesher, where each coordinate is rounded once (``RegionComplex.to_domain``).

The algorithm is an arrangement of the feature boundaries: the supporting lines
and circles are intersected pairwise, every curve is split at its points, a
doubly connected edge list orders the edges around each vertex (tangent, then
curvature for tangent curves), the faces are walked, each face's owner comes from
the set of features that contain it (toggled while crossing edges from the
unbounded face, no sample points), and the later-wins or imprint rule decides
which curves survive. Only the standard library is imported.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from fractions import Fraction
from functools import cmp_to_key
from math import isqrt

from .geometry_document import _MISSING, Component, Feature, GeometryError, GeometryModel, _pick

ZERO = Fraction(0)

#: Vertices are bucketed by floor(coordinate * 2**BUCKET_BITS) before the exact test.
BUCKET_BITS = 8
#: Bits of precision used when an exact coordinate is approximated by a rational.
APPROX_BITS = 96

AREA_TYPES = ("rect", "circle", "polygon", "trapezoid", "path")
SIDE_TAGS = ("left", "right", "bottom", "top", "axis", "outer")


def _sgn(x) -> int:
    return (x > 0) - (x < 0)


# ----------------------------------------------------------------------- exact numbers

class Q2:
    """a + b*sqrt(D) with rational a, b and an integer D >= 0 (D == 0 means rational).

    A perfect-square D is folded into a. Arithmetic is defined between numbers of one
    field (equal D, or one of them rational); predicates that mix two fields use Q4.
    """

    __slots__ = ("a", "b", "D")

    def __init__(self, a, b=0, D=0):
        a, b, D = Fraction(a), Fraction(b), int(D)
        if b == 0 or D == 0:
            b, D = ZERO, 0
        else:
            if D < 0:
                raise ValueError("negative radicand")
            r = isqrt(D)
            if r * r == D:
                a, b, D = a + b * r, ZERO, 0
        self.a, self.b, self.D = a, b, D

    def _join(self, o: "Q2") -> int:
        if self.D == 0:
            return o.D
        if o.D == 0 or o.D == self.D:
            return self.D
        raise ArithmeticError(f"mixed fields sqrt({self.D}) and sqrt({o.D})")

    @staticmethod
    def _of(o) -> "Q2":
        return o if isinstance(o, Q2) else Q2(o)

    def __add__(self, o):
        o = self._of(o)
        return Q2(self.a + o.a, self.b + o.b, self._join(o))

    __radd__ = __add__

    def __sub__(self, o):
        o = self._of(o)
        return Q2(self.a - o.a, self.b - o.b, self._join(o))

    def __rsub__(self, o):
        return self._of(o) - self

    def __neg__(self):
        return Q2(-self.a, -self.b, self.D)

    def __mul__(self, o):
        o = self._of(o)
        D = self._join(o)
        return Q2(self.a * o.a + self.b * o.b * D, self.a * o.b + self.b * o.a, D)

    __rmul__ = __mul__

    def sign(self) -> int:
        sa, sb = _sgn(self.a), _sgn(self.b)
        if sb == 0:
            return sa
        if sa == 0 or sa == sb:
            return sb
        d = _sgn(self.a * self.a - self.b * self.b * self.D)
        return sa if d > 0 else (sb if d < 0 else 0)

    def is_zero(self) -> bool:
        return self.a == 0 and self.b == 0

    def __eq__(self, o):
        if not isinstance(o, Q2):
            return NotImplemented
        return cmp(self, o) == 0

    __hash__ = None

    def approx(self, bits: int = APPROX_BITS) -> Fraction:
        """A rational within 2**-bits of the value (exact for a rational number)."""
        if self.D == 0:
            return self.a
        S = 1 << bits
        n1 = S * self.a.numerator * self.b.denominator
        m = S * self.b.numerator * self.a.denominator
        L = self.a.denominator * self.b.denominator
        R = isqrt(self.D * m * m)
        num = n1 + (R if m > 0 else -R - 1)
        return Fraction(num, L * S)

    def floor_key(self, bits: int = BUCKET_BITS) -> int:
        """An integer within 1 of floor(value * 2**bits)."""
        return math.floor(self.approx(bits + 4) * (1 << bits))

    def __float__(self):
        return float(self.approx(80))

    def __repr__(self):
        if self.D == 0:
            return f"Q2({self.a})"
        return f"Q2({self.a} + {self.b}*sqrt({self.D}))"


def _fields(*qs) -> tuple[int, int]:
    """The one or two distinct radicands of these numbers, as (D1, D2) with D2 == 0 when one."""
    ds: list[int] = []
    for q in qs:
        if q.D and q.D not in ds:
            ds.append(q.D)
    if len(ds) > 2:
        raise ArithmeticError(f"a predicate mixed three fields {ds}")
    return (ds[0] if ds else 0, ds[1] if len(ds) > 1 else 0)


class Q4:
    """x + y*sqrt(D2) with x, y in Q(sqrt(D1)): the biquadratic field of two radicands."""

    __slots__ = ("x", "y", "D2")

    def __init__(self, x: Q2, y: Q2, D2: int):
        self.x, self.y, self.D2 = x, y, (0 if y.is_zero() else D2)

    @staticmethod
    def lift(q: Q2, D1: int, D2: int) -> "Q4":
        if q.D == 0 or q.D == D1:
            return Q4(q, Q2(0), D2)
        if q.D == D2:
            return Q4(Q2(q.a), Q2(q.b), D2)
        raise ArithmeticError("number outside the predicate's field")

    def __add__(self, o):
        return Q4(self.x + o.x, self.y + o.y, self.D2 or o.D2)

    def __sub__(self, o):
        return Q4(self.x - o.x, self.y - o.y, self.D2 or o.D2)

    def __mul__(self, o):
        D2 = self.D2 or o.D2
        return Q4(self.x * o.x + self.y * o.y * D2, self.x * o.y + self.y * o.x, D2)

    def sign(self) -> int:
        return _sign_x_plus_y_root(self.x, self.y, self.D2)


def _sign_x_plus_y_root(x: Q2, y: Q2, D2: int) -> int:
    """sign(x + y*sqrt(D2)) for x, y of one field and D2 > 0 (the y term is absent when D2 == 0)."""
    if D2 == 0 or y.is_zero():
        return x.sign()
    sx, sy = x.sign(), y.sign()
    if sx == 0 or sx == sy:
        return sy
    d = (x * x - y * y * D2).sign()
    return sx if d > 0 else (sy if d < 0 else 0)


def _sign_plus_root(u: Q4, w: Q4, e: Q4) -> int:
    """sign(u + w*sqrt(e)) for u, w, e in one biquadratic field and e > 0."""
    su, sw = u.sign(), w.sign()
    if sw == 0:
        return su
    if su == 0 or su == sw:
        return sw
    d = (u * u - w * w * e).sign()
    return su if d > 0 else (sw if d < 0 else 0)


def cmp(x: Q2, y: Q2) -> int:
    """sign(x - y) for numbers of any two fields."""
    if x.D == 0 or y.D == 0 or x.D == y.D:
        return (x - y).sign()
    return _sign_x_plus_y_root(Q2(x.a - y.a, x.b, x.D), Q2(-y.b), y.D)


def cross_sign(ux: Q2, uy: Q2, vx: Q2, vy: Q2) -> int:
    """sign(ux*vy - uy*vx), each vector in one field."""
    D1, D2 = _fields(ux, uy, vx, vy)
    if D2 == 0:
        return (ux * vy - uy * vx).sign()
    a, b, c, d = (Q4.lift(q, D1, D2) for q in (ux, uy, vx, vy))
    return (a * d - b * c).sign()


def _lex_cmp(p, q) -> int:
    """Lexicographic (x, y) order of two points."""
    c = cmp(p[0], q[0])
    return c if c else cmp(p[1], q[1])


def _upper(dx: Q2, dy: Q2) -> bool:
    """True for a direction with angle in [0, pi)."""
    s = dy.sign()
    return s > 0 or (s == 0 and dx.sign() > 0)


def _dir_cmp(d1, d2) -> int:
    """Counter-clockwise angular order of two direction vectors; 0 for the same direction."""
    u1, u2 = _upper(*d1), _upper(*d2)
    if u1 != u2:
        return -1 if u1 else 1
    return -cross_sign(d1[0], d1[1], d2[0], d2[1])


def _root_exceeds(a: Q2, E: Q2, s: int) -> bool:
    """True when s*sqrt(E) > a (E > 0)."""
    sa = a.sign()
    if sa == 0:
        return s > 0
    if sa < 0 and s > 0:
        return True
    if sa > 0 and s < 0:
        return False
    d = (a * a - E).sign()
    return (d < 0) if s > 0 else (d > 0)


# ----------------------------------------------------------------------- supporting curves

@dataclass(eq=False)
class _Line:
    """A x + B y = C with coprime integers, base point p0 and direction d = (-B, A)."""

    A: int
    B: int
    C: int
    p0: tuple[Fraction, Fraction]
    d: tuple[int, int]
    points: dict = field(default_factory=dict)     # vertex id -> parameter
    pieces: list = field(default_factory=list)

    kind = "line"

    def param(self, x: Q2, y: Q2) -> Q2:
        return (x - self.p0[0]) * self.d[0] + (y - self.p0[1]) * self.d[1]

    def x_at_y(self, y: Q2) -> Q2:
        return (Q2(self.C) - y * self.B) * Fraction(1, self.A)


@dataclass(eq=False)
class _Circle:
    cx: int
    cy: int
    r2: int
    points: set = field(default_factory=set)
    pieces: list = field(default_factory=list)

    kind = "circle"

    def radius(self) -> Q2:
        return Q2(0, 1, self.r2)


def _line_through(p, q) -> tuple[int, int, int]:
    """Coprime, sign-normalized integer coefficients of the line through rational p and q."""
    px, py, qx, qy = (Fraction(v) for v in (p[0], p[1], q[0], q[1]))
    A = qy - py
    B = px - qx
    C = A * px + B * py
    L = math.lcm(A.denominator, B.denominator, C.denominator)
    A, B, C = int(A * L), int(B * L), int(C * L)
    g = math.gcd(A, B, C)
    A, B, C = A // g, B // g, C // g
    if A < 0 or (A == 0 and B < 0):
        A, B, C = -A, -B, -C
    return A, B, C


@dataclass(eq=False)
class _Piece:
    """One boundary piece of a feature on a supporting curve."""

    feature: int                 # index in the component's features; -1 for the domain
    name: str                    # provenance name
    curve: object
    v0: int | None               # vertex ids; None, None for a whole circle
    v1: int | None
    ccw: bool | None = None      # arcs: traversal from v0 to v1 around the centre


# ----------------------------------------------------------------------- vertices

class _Vertices:
    def __init__(self):
        self.x: list[Q2] = []
        self.y: list[Q2] = []
        self.buckets: dict[tuple[int, int], list[int]] = {}

    def add(self, x: Q2, y: Q2) -> int:
        kx, ky = x.floor_key(), y.floor_key()
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for v in self.buckets.get((kx + i, ky + j), ()):
                    if cmp(self.x[v], x) == 0 and cmp(self.y[v], y) == 0:
                        return v
        v = len(self.x)
        self.x.append(x)
        self.y.append(y)
        self.buckets.setdefault((kx, ky), []).append(v)
        return v

    def __len__(self):
        return len(self.x)


# ----------------------------------------------------------------------- angles on a circle

def _acmp(c: _Circle, P, Q) -> int:
    """Angular order around the centre of two points on the circle.

    A point is ``("q2", x, y)`` or ``("root", s, E, y)`` for the point
    (cx + s*sqrt(E), y) where the circle meets the horizontal line at height y.
    """
    def upper(T):
        if T[0] == "q2":
            return _upper(T[1] - c.cx, T[2] - c.cy)
        s = (T[3] - c.cy).sign()
        return s > 0 or (s == 0 and T[1] > 0)

    uP, uQ = upper(P), upper(Q)
    if uP != uQ:
        return -1 if uP else 1
    if P[0] == "q2" and Q[0] == "q2":
        return -cross_sign(P[1] - c.cx, P[2] - c.cy, Q[1] - c.cx, Q[2] - c.cy)
    if P[0] == "root":
        return -_acmp(c, Q, P)
    # P is a plain point, Q = (cx + s*sqrt(E), y): cross(P - c, Q - c) = qx*dy - qy*s*sqrt(E)
    qx, qy = P[1] - c.cx, P[2] - c.cy
    s, E, y = Q[1], Q[2], Q[3]
    dy = y - c.cy
    D1, D2 = _fields(qx, qy, dy, E)
    U = Q4.lift(qx, D1, D2) * Q4.lift(dy, D1, D2)
    W = Q4.lift(-qy * s, D1, D2)
    return -_sign_plus_root(U, W, Q4.lift(E, D1, D2))


def _between_ccw(c: _Circle, S, E, P) -> bool:
    """P lies on the closed arc from S counter-clockwise to E."""
    if _acmp(c, S, E) < 0:
        return _acmp(c, S, P) <= 0 and _acmp(c, P, E) <= 0
    return _acmp(c, S, P) <= 0 or _acmp(c, P, E) <= 0


# ----------------------------------------------------------------------- the arrangement

@dataclass(eq=False)
class _Edge:
    """An elementary edge between two consecutive points of a supporting curve."""

    curve: object
    a: int                        # vertex ids; a circle edge runs counter-clockwise a -> b
    b: int
    provenance: frozenset
    toggles: frozenset            # feature indices whose inside flips across this edge
    segment_features: frozenset   # zero-area features whose curve carries this edge
    index: int = -1


class _Dcel:
    """Half-edges of a set of elementary edges, their cycles and orientations."""

    def __init__(self, V: _Vertices, edges: list[_Edge]):
        self.V = V
        self.edges = edges
        n = len(edges)
        self.he_edge = [e for e in edges for _ in (0, 1)]
        self.he_fwd = [True, False] * n
        self.dir_from: list = []
        self.kappa: list = []
        for e in edges:
            for fwd in (True, False):
                self.dir_from.append(self._direction(e, fwd))
                self.kappa.append(self._curvature(e, fwd))
        self.outgoing: dict[int, list[int]] = {}
        for h in range(2 * n):
            self.outgoing.setdefault(self.src(h), []).append(h)
        for hs in self.outgoing.values():
            hs.sort(key=cmp_to_key(self._he_cmp))
            for i in range(1, len(hs)):
                if self._he_cmp(hs[i - 1], hs[i]) == 0:
                    raise GeometryError("internal: two curves leave a vertex with the same tangent and curvature")
        self.next = [-1] * (2 * n)
        for h in range(2 * n):
            hs = self.outgoing[self.dst(h)]
            self.next[h] = hs[hs.index(h ^ 1) - 1]
        self.cycle_of = [-1] * (2 * n)
        self.cycles: list[list[int]] = []
        for h in range(2 * n):
            if self.cycle_of[h] >= 0:
                continue
            cyc = []
            k = h
            while self.cycle_of[k] < 0:
                self.cycle_of[k] = len(self.cycles)
                cyc.append(k)
                k = self.next[k]
            self.cycles.append(cyc)
        self.ccw = [self._orientation(cyc) for cyc in self.cycles]
        self.faces: list[tuple[int | None, list[int]]] = []     # (outer cycle or None, hole cycles)
        self.face_of: list[int] = [-1] * len(self.cycles)
        self._assign_faces()

    # -- half-edge geometry ---------------------------------------------------

    def src(self, h: int) -> int:
        e = self.he_edge[h]
        return e.a if self.he_fwd[h] else e.b

    def dst(self, h: int) -> int:
        e = self.he_edge[h]
        return e.b if self.he_fwd[h] else e.a

    def _direction(self, e: _Edge, fwd: bool):
        if e.curve.kind == "line":
            d = e.curve.d
            return (Q2(d[0]), Q2(d[1])) if fwd else (Q2(-d[0]), Q2(-d[1]))
        c = e.curve
        v = e.a if fwd else e.b
        rx, ry = self.V.x[v] - c.cx, self.V.y[v] - c.cy
        return (-ry, rx) if fwd else (ry, -rx)

    @staticmethod
    def _curvature(e: _Edge, fwd: bool):
        """(sign, r2): the sign of the signed curvature and the radius squared; (0, 0) for a line."""
        if e.curve.kind == "line":
            return (0, 0)
        return (1 if fwd else -1, e.curve.r2)

    def dir_to(self, h: int):
        d = self.dir_from[h ^ 1]
        return (-d[0], -d[1])

    def _he_cmp(self, h1: int, h2: int) -> int:
        c = _dir_cmp(self.dir_from[h1], self.dir_from[h2])
        if c:
            return c
        (s1, r1), (s2, r2) = self.kappa[h1], self.kappa[h2]
        if s1 != s2:
            return -1 if s1 < s2 else 1
        if s1 == 0 or r1 == r2:
            return 0
        # the same sign: |kappa| = 1/r grows as r shrinks; smaller signed curvature first
        return (-1 if r1 > r2 else 1) * s1

    # -- cycles ---------------------------------------------------------------

    def arc_leftmost(self, h: int):
        """The leftmost point of the arc of h when it lies strictly inside the arc."""
        e = self.he_edge[h]
        if e.curve.kind != "circle":
            return None
        c = e.curve
        L = ("q2", Q2(c.cx, -1, c.r2), Q2(c.cy))
        S = ("q2", self.V.x[e.a], self.V.y[e.a])
        E = ("q2", self.V.x[e.b], self.V.y[e.b])
        if _acmp(c, S, L) == 0 or _acmp(c, E, L) == 0:
            return None
        return (L[1], L[2]) if _between_ccw(c, S, E, L) else None

    def extreme(self, cyc: list[int]):
        """(point, half-edge, inside_arc) of the lexicographically smallest point of a cycle."""
        best, best_h, best_arc = None, None, False
        for h in cyc:
            v = self.src(h)
            p = (self.V.x[v], self.V.y[v])
            if best is None or _lex_cmp(p, best) < 0:
                best, best_h, best_arc = p, h, False
            L = self.arc_leftmost(h)
            if L is not None and _lex_cmp(L, best) < 0:
                best, best_h, best_arc = L, h, True
        return best, best_h, best_arc

    def _orientation(self, cyc: list[int]) -> bool:
        """True for a counter-clockwise cycle (a bounded face's outer boundary).

        At the lexicographically smallest point of the cycle nothing of the cycle lies to the
        left, so the face is bounded exactly when none of the cycle's passages through that
        point has the direction (-1, 0) inside its sector (the wedge from the outgoing germ
        counter-clockwise to the reversed incoming germ). A cycle pinched at that point passes
        it more than once, and every passage is tested.
        """
        best, h, inside_arc = self.extreme(cyc)
        if inside_arc:
            e = self.he_edge[h]
            # moving down at the leftmost point of the circle (counter-clockwise around the
            # centre) keeps the face to the east; a backward passage puts it to the west
            return all(self.he_fwd[k] for k in cyc if self.he_edge[k] is e)
        v = self.src(h)
        for i, k in enumerate(cyc):
            if self.src(k) != v:
                continue
            h_in = cyc[i - 1]
            t_in = self.dir_to(h_in)
            a, b = self.dir_from[k], (-t_in[0], -t_in[1])
            s_in, r_in = self.kappa[h_in]
            if self._sector_has_left(a, self.kappa[k], b, (-s_in, r_in)):
                return False
        return True

    @staticmethod
    def _sector_has_left(a, ka, b, kb) -> bool:
        """Whether the sector from germ a counter-clockwise to germ b holds the direction (-1, 0).

        Neither germ points left (the vertex is the leftmost point). Germs of one direction
        form a cusp: the sector is the thin wedge when b bends further left than a
        (larger signed curvature), else the whole turn minus that wedge.
        """
        c = _dir_cmp(a, b)
        if c == 0:
            (sa, ra), (sb, rb) = ka, kb
            if sa == sb == 0:
                return True                     # a dangling edge's free end: the face wraps around it
            if sa == 0:
                thin = sb > 0
            elif sb == 0 or sa != sb:
                thin = sb > sa
            else:
                thin = (rb < ra) if sb > 0 else (rb > ra)    # kappa = s / sqrt(r2)
                if rb == ra:
                    raise GeometryError("internal: a cusp between two germs of one circle")
            return not thin
        left = (Q2(-1), Q2(0))
        if c < 0:                               # angle(a) < angle(b): inside when a < left < b
            return _dir_cmp(a, left) < 0 and _dir_cmp(left, b) < 0
        return _dir_cmp(a, left) < 0 or _dir_cmp(left, b) < 0

    def bbox(self, cyc: list[int]):
        xs = [self.V.x[self.src(h)] for h in cyc]
        ys = [self.V.y[self.src(h)] for h in cyc]
        for h in cyc:
            e = self.he_edge[h]
            if e.curve.kind == "circle":
                c = e.curve
                S = ("q2", self.V.x[e.a], self.V.y[e.a])
                E = ("q2", self.V.x[e.b], self.V.y[e.b])
                r = c.radius()
                for P in ((Q2(c.cx) + r, Q2(c.cy)), (Q2(c.cx), Q2(c.cy) + r),
                          (Q2(c.cx) - r, Q2(c.cy)), (Q2(c.cx), Q2(c.cy) - r)):
                    if _between_ccw(c, S, E, ("q2", P[0], P[1])):
                        xs.append(P[0])
                        ys.append(P[1])
        k = cmp_to_key(cmp)
        return (min(xs, key=k), max(xs, key=k), min(ys, key=k), max(ys, key=k))

    def _assign_faces(self) -> None:
        """Group the cycles into faces: each hole goes to the innermost counter-clockwise cycle
        that contains it (bounding boxes first, then an exact ray cast); the cycles no
        counter-clockwise cycle contains bound the unbounded face."""
        outers = [k for k in range(len(self.cycles)) if self.ccw[k]]
        bbox = {k: self.bbox(self.cycles[k]) for k in outers}
        verts = {k: {self.src(h) for h in self.cycles[k]} for k in outers}
        holes: dict[int | None, list[int]] = {k: [] for k in outers}
        holes[None] = []
        for hk in range(len(self.cycles)):
            if self.ccw[hk]:
                continue
            hb = self.bbox(self.cycles[hk])
            v = self.src(self.cycles[hk][0])
            cands = [o for o in outers if _box_inside(hb, bbox[o]) and v not in verts[o]]
            if len(cands) > 1:
                cands = [o for o in cands if self.contains(self.cycles[o], v)]
            elif cands and not self.contains(self.cycles[cands[0]], v):
                cands = []
            if len(cands) > 1:
                inner = [c for c in cands if all(_box_inside(bbox[c], bbox[o]) for o in cands)]
                if len(inner) != 1:
                    raise GeometryError("internal: containing faces whose bounding boxes do not nest")
                cands = inner
            holes[cands[0] if cands else None].append(hk)
        self.faces = [(None, holes[None])] + [(o, holes[o]) for o in outers]
        for i, (outer, hs) in enumerate(self.faces):
            if outer is not None:
                self.face_of[outer] = i
            for hk in hs:
                self.face_of[hk] = i

    def face_left_of(self, h: int) -> int:
        return self.face_of[self.cycle_of[h]]

    def contains(self, cyc: list[int], v: int) -> bool:
        """Parity of a horizontal ray from vertex v (not on the cycle) to +x against the cycle.

        A dangling edge appears twice in a cycle and is counted twice, as the curve the
        cycle traces crosses the ray twice there.
        """
        px, py = self.V.x[v], self.V.y[v]
        count = sum(self._ray_hits(self.he_edge[h], px, py) for h in cyc)
        return count % 2 == 1

    def _ray_hits(self, e: _Edge, px: Q2, py: Q2) -> int:
        """Intersections of the edge with the line y = py + 0⁺ at x > px (the perturbation rule)."""
        V = self.V
        if e.curve.kind == "line":
            above_a, above_b = cmp(V.y[e.a], py) > 0, cmp(V.y[e.b], py) > 0
            if above_a == above_b:
                return 0
            return 1 if cmp(e.curve.x_at_y(py), px) > 0 else 0
        c = e.curve
        dy = py - c.cy
        E = Q2(c.r2) - dy * dy
        sE = E.sign()
        if sE < 0:
            return 0
        S = ("q2", V.x[e.a], V.y[e.a])
        T = ("q2", V.x[e.b], V.y[e.b])
        if sE == 0:
            if dy.sign() > 0:                       # tangent at the top: the arc lies below the line
                return 0
            if cmp(Q2(c.cx), px) <= 0:
                return 0
            X = ("q2", Q2(c.cx), py)                # the bottom point: two branches rise from it
            if _acmp(c, S, X) == 0 or _acmp(c, T, X) == 0:
                return 1
            return 2 if _between_ccw(c, S, T, X) else 0
        hits = 0
        a = px - c.cx
        for s in (1, -1):
            if not _root_exceeds(a, E, s):          # X = (cx + s*sqrt(E), py) must satisfy X.x > px
                continue
            X = ("root", s, E, py)
            cs, ct = _acmp(c, S, X), _acmp(c, T, X)
            if cs == 0:
                hits += 1 if s > 0 else 0           # the arc leaves its start upward only at X+
            elif ct == 0:
                hits += 1 if s < 0 else 0           # the arc arrives at its end from above only at X-
            elif _between_ccw(c, S, T, X):
                hits += 1
        return hits


# ----------------------------------------------------------------------- output types

@dataclass
class Cell:
    """A face of the region complex (several disjoint faces may share one region)."""

    index: int
    region: str
    material: object                # a name, None for void, or _MISSING for a homogeneous body
    feature: str                    # the owning feature id, or "background"
    feature_index: int              # -1 for the background
    mesh_size: int | None           # pm
    loops: list                     # [outer, hole, ...], each a list of (curve index, forward)
    area: float                     # pm^2
    membership: frozenset           # the feature indices containing the cell (-1: the domain)
    feature_indices: frozenset = frozenset()    # every feature that owns a piece of the cell (-1: background)

    @property
    def void(self) -> bool:
        return self.material is None


@dataclass
class Curve:
    """A maximal piece of one supporting curve between two vertices."""

    index: int
    kind: str                       # "line", "arc" or "circle"
    a: int                          # vertex ids; an arc runs counter-clockwise from a to b
    b: int
    params: dict                    # line: {} ; arc/circle: {"center": (cx, cy), "r2": r2}
    provenance: frozenset
    left: int | None                # cell index on the left of a -> b, None for the exterior
    right: int | None
    tag: str | None = None          # mesh tag of an exterior curve


@dataclass
class RegionComplex:
    """The evaluated component: cells, curves with provenance and the resolved selections."""

    component: str
    dimension: str
    domain: dict
    vertices: list                  # (x, y) as Q2, in pm
    cells: list
    curves: list
    selections: dict                # name -> ("region" | "boundary", frozenset of indices)
    notes: list = field(default_factory=list)
    _dcel: object = field(default=None, repr=False)
    _handoff: object = field(default=None, repr=False)      # the polylines of the last to_domain
    _component: object = field(default=None, repr=False)    # the parsed Component, for select()

    def region_names(self) -> list[str]:
        """The surviving regions in feature order, the background last (the 0.2 route's order)."""
        first: dict[str, int] = {}
        for c in self.cells:
            key = len(self.cells) + 1 if c.feature_index < 0 else c.feature_index
            first[c.region] = min(first.get(c.region, key), key)
        return sorted(first, key=first.get)

    def cells_of_region(self, region: str) -> list[int]:
        return [c.index for c in self.cells if c.region == region]

    def area_of_region(self, region: str) -> float:
        return sum(c.area for c in self.cells if c.region == region)

    def curves_with(self, provenance: str) -> list[int]:
        return [k.index for k in self.curves if provenance in k.provenance]

    def select(self, expr) -> tuple[str, frozenset]:
        """What a ``mesh.controls`` ``select`` names: ``("region", cells)`` or ``("boundary", curves)``.

        A named selection gives its own kind. Otherwise the contract's region selectors are
        tried first (a region name, a feature id, ``{"feature": ..}``, ``{"material": ..}``),
        then the boundary ones (a tag, a provenance name, ``{"provenance": ..}``, ``{"of": ..}``,
        ``{"between": ..}``). A name that is neither is refused."""
        if isinstance(expr, str) and expr in self.selections:
            return self.selections[expr]
        comp = self._component
        where = f"mesh.controls: select {expr!r}"
        try:
            return "region", frozenset(_resolve_region(self, comp, expr, where, ()))
        except GeometryError as region_error:
            try:
                return "boundary", frozenset(_resolve_boundary(self, comp, expr, where, ()))
            except GeometryError:
                raise region_error from None

    def is_exterior(self, cell: int | None) -> bool:
        """The exterior for the mesh: outside the domain, or a void cell."""
        return cell is None or self.cells[cell].void

    def exterior_curves(self) -> list[int]:
        return [k.index for k in self.curves if self.is_exterior(k.left) or self.is_exterior(k.right)]

    def euler(self) -> tuple[int, int, int, int]:
        """(V, E, F, C): used vertices, curves, faces including the exterior, components."""
        used = {k.a for k in self.curves} | {k.b for k in self.curves}
        parent = {v: v for v in used}

        def find(v):
            while parent[v] != v:
                parent[v] = parent[parent[v]]
                v = parent[v]
            return v

        for k in self.curves:
            parent[find(k.a)] = find(k.b)
        comps = len({find(v) for v in used})
        return len(used), len(self.curves), len(self.cells) + 1, comps

    def summary(self, model: GeometryModel | None = None) -> str:
        """A diagnostic listing of the cells, curves, tags and selections (not a persisted format).

        With the ``model`` the lengths and areas are given in its document unit; without it
        in picometres."""
        u = (lambda k: float(Fraction(k) / model.pm_per_unit)) if model is not None else (lambda k: float(k))
        unit = str(model.units_length) if model is not None else "pm"
        dom = self.domain
        lines = [f"component {self.component!r} ({self.dimension}): domain x {u(dom['xmin']):g}..{u(dom['xmax']):g}, "
                 f"y {u(dom['ymin']):g}..{u(dom['ymax']):g} {unit}",
                 f"{len(self.cells)} cells, {len(self.curves)} curves, {len({k.a for k in self.curves} | {k.b for k in self.curves})} vertices"]
        for c in self.cells:
            mat = "void" if c.void else ("(homogeneous)" if c.material is _MISSING else c.material)
            holes = f", {len(c.loops) - 1} hole(s)" if len(c.loops) > 1 else ""
            lines.append(f"  cell {c.index}: region {c.region!r}, material {mat}, feature {c.feature}, "
                         f"area {u(1) ** 2 * c.area:.6g} {unit}^2, {len(c.loops[0])} boundary curves{holes}")
        names = lambda cell: "exterior" if cell is None else repr(self.cells[cell].region)   # noqa: E731
        for k in self.curves:
            where = f"{names(k.left)} | {names(k.right)}"
            tag = f", tag {k.tag}" if k.tag else ""
            lines.append(f"  curve {k.index}: {k.kind} {' '.join(sorted(k.provenance))} ({where}{tag})")
        for name, (kind, chosen) in self.selections.items():
            lines.append(f"  selection {name!r}: {len(chosen)} {kind} entries {sorted(chosen)}")
        return "\n".join(lines)

    def to_domain(self, size: float, *, unit_pm=10 ** 6, mesh_sizes: bool = True, min_area: float = 0.0,
                  controls: list | None = None):
        """The meshine ``Domain``, boundary namer and {region: material} of this complex.

        Coordinates are rounded once from pm to ``unit_pm`` picometres per mesher unit
        (micrometres by default; an exact ``Fraction`` is accepted). Arcs become polylines
        whose vertices both sides share; a circle that nothing touches becomes one shared
        ``meshine.Circle``. Void cells are not added, so their border is exterior, and so
        is a cell below ``min_area`` (pm²), which is noted. ``size`` is the mesher's default
        edge length in its own unit and fixes the circle vertex counts; ``mesh_sizes``
        passes each cell's own size on. Regions are added in feature order, the
        background last, each region's cells in index order.

        ``controls`` are the contract's ``mesh.controls`` entries, already checked for form:
        ``{"select": expr, "circle_segments": n}`` sets the vertex count of every circle
        that the selection's curves lie on or that bounds one of its cells (raised, and
        noted, where a whole circle's chords would otherwise cut across a neighbouring
        curve); ``{"select": expr, "size": h}`` (``h`` in pm) sets the mesh size of the
        selection's cells, a boundary selection being refused. Later entries win.
        """
        from meshine import Circle, Domain
        return _to_domain(self, size, Fraction(unit_pm), Circle, Domain, mesh_sizes, min_area, controls or [])

    def curve_edges(self, mesh) -> dict:
        """{curve index: (E, 2) node pairs} of the mesh edges that lie on each curve.

        ``mesh`` is the meshine ``TriMesh`` generated from the last ``to_domain`` hand-off
        (its nodes in the mesher's unit). An edge belongs to a curve when both its nodes
        lie on one piece of the curve's polyline, or on the circle, within 1e-9 of the
        mesh's diagonal (meshine's own merge tolerance) and are consecutive there. Every
        mesh edge on a region boundary, an interface or an internal (imprint or segment)
        constraint is found this way; nothing is read back from the mesher.
        """
        if self._handoff is None:
            raise GeometryError("curve_edges needs the mesh of a to_domain hand-off of this complex")
        return _curve_edges(self, mesh)

    def provenance_edges(self, mesh) -> dict:
        """{provenance name: (E, 2)} over the curves that carry the name (contract, mesh tags)."""
        import numpy as np
        by_curve = self.curve_edges(mesh)
        out: dict[str, list] = {}
        for k in self.curves:
            for name in k.provenance:
                out.setdefault(name, []).extend(map(tuple, by_curve[k.index]))
        return {name: np.array(sorted(set(v)), dtype=int).reshape(-1, 2) for name, v in out.items()}

    def selection_edges(self, mesh, name: str):
        """The (E, 2) mesh edges of a boundary selection, resolved through the curves it holds."""
        import numpy as np
        kind, chosen = self.selections[name]
        if kind != "boundary":
            raise GeometryError(f"selection {name!r} selects regions, not boundaries")
        by_curve = self.curve_edges(mesh)
        pairs = sorted({tuple(e) for i in chosen for e in by_curve[i]})
        return np.array(pairs, dtype=int).reshape(-1, 2)


# ----------------------------------------------------------------------- evaluation

def evaluate(model: GeometryModel, component: str | None = None) -> RegionComplex:
    """The region complex of one 2D or axisymmetric component."""
    return evaluate_component(_pick(model, component))


def evaluate_component(comp: Component) -> RegionComplex:
    """The region complex of a parsed component (``geometry_document.Component``)."""
    if comp.dimension == "3d":
        raise GeometryError(f"component {comp.name!r}: the 2D engine takes 2d and axisymmetric components")
    return _Engine(comp).run()


class _Engine:
    def __init__(self, comp: Component):
        self.comp = comp
        self.V = _Vertices()
        self.lines: dict[tuple, _Line] = {}
        self.circles: dict[tuple, _Circle] = {}
        self.pieces: list[_Piece] = []
        self.notes: list[str] = []

    # -- feature boundaries -------------------------------------------------

    def vertex(self, x, y) -> int:
        return self.V.add(Q2(x), Q2(y))

    def line(self, p, q) -> _Line:
        key = _line_through(p, q)
        ln = self.lines.get(key)
        if ln is None:
            A, B, _C = key
            g = math.gcd(A, B)
            ln = _Line(*key, p0=(Fraction(p[0]), Fraction(p[1])), d=(-B // g, A // g))
            self.lines[key] = ln
        return ln

    def circle(self, cx: int, cy: int, r2: int) -> _Circle:
        key = (cx, cy, r2)
        c = self.circles.get(key)
        if c is None:
            c = self.circles[key] = _Circle(cx, cy, r2)
        return c

    def add_segment(self, feature: int, name: str, p, q) -> None:
        if tuple(p) == tuple(q):
            raise GeometryError(f"{name}: zero-length segment at ({float(p[0]):g}, {float(p[1]):g}) pm")
        ln = self.line(p, q)
        self.pieces.append(_Piece(feature, name, ln, self.vertex(*p), self.vertex(*q)))

    def add_polyline(self, feature: int, fid: str, points, parts, closed: bool) -> None:
        n = len(points)
        for i in range(n if closed else n - 1):
            self.add_segment(feature, f"{fid}.{parts[i]}", points[i], points[(i + 1) % n])

    def add_feature(self, i: int, f: Feature) -> None:
        d = f.data
        if f.type == "rect":
            x, y, w, h = d["x"], d["y"], d["w"], d["h"]
            pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            self.add_polyline(i, f.id, pts, ["bottom", "right", "top", "left"], True)
        elif f.type == "trapezoid":
            cx, y, w, h, wt = (Fraction(d[k]) for k in ("cx", "y", "w", "h", "w_top"))
            pts = [(cx - w / 2, y), (cx + w / 2, y), (cx + wt / 2, y + h), (cx - wt / 2, y + h)]
            self.add_polyline(i, f.id, pts, ["bottom", "right", "top", "left"], True)
        elif f.type == "polygon":
            self.add_polyline(i, f.id, d["points"], d["edges"], True)
        elif f.type == "segment":
            self.add_polyline(i, f.id, d["points"], ["line"] * len(d["points"]), False)
        elif f.type == "circle":
            c = self.circle(d["cx"], d["cy"], d["r"] * d["r"])
            self.pieces.append(_Piece(i, f"{f.id}.boundary", c, None, None, True))
        elif f.type == "path":
            self.add_path(i, f)
        else:
            raise GeometryError(f"feature {f.name!r}: a {f.type} is not a 2D feature")

    def add_path(self, i: int, f: Feature) -> None:
        d = f.data
        cur = tuple(d["start"])
        segs = d["segments"]
        corners = [cur]
        for k, s in enumerate(segs):
            name = s.get("name") or f"s{k + 1}"
            where = f"feature {f.name!r} segment {name}"
            if "line" in s:
                to = tuple(s["line"])
                self.add_segment(i, f"{f.id}.{name}", cur, to)
                cur = to
                corners.append(cur)
                continue
            a = s["arc"]
            (cx, cy), to = tuple(a["center"]), tuple(a["to"])
            r2 = (cur[0] - cx) ** 2 + (cur[1] - cy) ** 2
            if r2 == 0:
                raise GeometryError(f"{where}: the arc starts at its centre")
            if to == (cx, cy):
                raise GeometryError(f"{where}: 'to' equals the centre")
            d2 = (to[0] - cx) ** 2 + (to[1] - cy) ** 2
            if d2 != r2:
                raise GeometryError(f"{where}: 'to' is not on the arc's circle (|to - center|^2 = {d2} pm^2, "
                                    f"r^2 = {r2} pm^2); the stage 2 engine takes arcs whose end point lies on the grid")
            if to == cur:
                raise GeometryError(f"{where}: zero length (a whole circle is a circle feature)")
            c = self.circle(cx, cy, r2)
            self.pieces.append(_Piece(i, f"{f.id}.{name}", c, self.vertex(*cur), self.vertex(*to), bool(a["ccw"])))
            cur = to
            corners.append(cur)
        if cur != tuple(d["start"]):
            self.add_segment(i, f"{f.id}.s{len(segs) + 1}", cur, d["start"])
        else:
            corners.pop()
        if len(set(corners)) != len(corners):
            raise GeometryError(f"feature {f.name!r}: the path repeats a point")

    def add_domain(self) -> None:
        dom = self.comp.domain
        x0, x1, y0, y1 = dom["xmin"], dom["xmax"], dom["ymin"], dom["ymax"]
        left = "axis" if self.comp.dimension == "axisymmetric" and x0 == 0 else "left"
        self.add_polyline(-1, "domain", [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], ["bottom", "right", "top", left], True)

    # -- intersections --------------------------------------------------------

    def _on_piece(self, pc: _Piece, x: Q2, y: Q2) -> bool:
        cu = pc.curve
        if cu.kind == "line":
            t = cu.param(x, y)
            t0, t1 = cu.points[pc.v0], cu.points[pc.v1]
            if cmp(t0, t1) > 0:
                t0, t1 = t1, t0
            return cmp(t0, t) <= 0 and cmp(t, t1) <= 0
        if pc.v0 is None:
            return True
        P = ("q2", x, y)
        S = ("q2", self.V.x[pc.v0], self.V.y[pc.v0])
        E = ("q2", self.V.x[pc.v1], self.V.y[pc.v1])
        return _between_ccw(cu, S, E, P) if pc.ccw else _between_ccw(cu, E, S, P)

    def _record(self, cu1, cu2, x: Q2, y: Q2) -> None:
        """Keep an intersection point when a piece of each curve contains it."""
        on1 = [pc for pc in cu1.pieces if self._on_piece(pc, x, y)]
        if not on1:
            return
        on2 = [pc for pc in cu2.pieces if self._on_piece(pc, x, y)]
        if not on2:
            return
        v = self.V.add(x, y)
        for cu in (cu1, cu2):
            if cu.kind == "line":
                cu.points.setdefault(v, cu.param(x, y))
            else:
                cu.points.add(v)
        for p1 in on1:
            for p2 in on2:
                if p1.feature != p2.feature or p1.feature < 0:
                    continue
                end1, end2 = v in (p1.v0, p1.v1), v in (p2.v0, p2.v1)
                if not (end1 and end2):
                    f = self.comp.features[p1.feature]
                    how = "crosses" if not (end1 or end2) else "touches"
                    raise GeometryError(f"feature {f.name!r}: its boundary {how} itself at "
                                        f"({float(x):g}, {float(y):g}) pm between {p1.name} and {p2.name}")

    def _line_line(self, l1: _Line, l2: _Line) -> None:
        det = l1.A * l2.B - l2.A * l1.B
        if det == 0:
            return
        x = Fraction(l1.C * l2.B - l2.C * l1.B, det)
        y = Fraction(l1.A * l2.C - l2.A * l1.C, det)
        self._record(l1, l2, Q2(x), Q2(y))

    def _line_circle(self, ln: _Line, c: _Circle) -> None:
        for x, y in _line_circle_points(ln.p0, ln.d, c):
            self._record(ln, c, x, y)

    def _circle_circle(self, c1: _Circle, c2: _Circle) -> None:
        if (c1.cx, c1.cy) == (c2.cx, c2.cy):
            return
        A, B = 2 * (c2.cx - c1.cx), 2 * (c2.cy - c1.cy)
        C = c1.r2 - c2.r2 + c2.cx ** 2 + c2.cy ** 2 - c1.cx ** 2 - c1.cy ** 2
        p0 = (Fraction(C, A), ZERO) if A else (ZERO, Fraction(C, B))
        g = math.gcd(A, B)
        for x, y in _line_circle_points(p0, (-B // g, A // g), c1):
            self._record(c1, c2, x, y)

    def intersect_all(self) -> None:
        for ln in self.lines.values():
            for pc in ln.pieces:
                for v in (pc.v0, pc.v1):
                    ln.points[v] = ln.param(self.V.x[v], self.V.y[v])
        for c in self.circles.values():
            for pc in c.pieces:
                if pc.v0 is not None:
                    c.points.update((pc.v0, pc.v1))
        lines, circles = list(self.lines.values()), list(self.circles.values())
        lb = [self._line_bbox(ln) for ln in lines]
        cb = [self._circle_bbox(c) for c in circles]
        for i in range(len(lines)):
            for j in range(i + 1, len(lines)):
                if _boxes_meet(lb[i], lb[j]):
                    self._line_line(lines[i], lines[j])
            for j in range(len(circles)):
                if _boxes_meet(lb[i], cb[j]):
                    self._line_circle(lines[i], circles[j])
        for i in range(len(circles)):
            for j in range(i + 1, len(circles)):
                if _boxes_meet(cb[i], cb[j]):
                    self._circle_circle(circles[i], circles[j])
        for c in circles:
            if len(c.points) < 2:
                if not c.points:
                    c.points.add(self.V.add(Q2(c.cx) + c.radius(), Q2(c.cy)))
                (v,) = tuple(c.points)
                c.points.add(self.V.add(2 * c.cx - self.V.x[v], 2 * c.cy - self.V.y[v]))

    def _line_bbox(self, ln: _Line):
        xs = [float(self.V.x[v]) for pc in ln.pieces for v in (pc.v0, pc.v1)]
        ys = [float(self.V.y[v]) for pc in ln.pieces for v in (pc.v0, pc.v1)]
        return (min(xs), max(xs), min(ys), max(ys))

    @staticmethod
    def _circle_bbox(c: _Circle):
        r = math.sqrt(c.r2) * (1 + 1e-12) + 1
        return (c.cx - r, c.cx + r, c.cy - r, c.cy + r)

    # -- elementary edges ------------------------------------------------------

    def elementary_edges(self) -> list[_Edge]:
        edges: list[_Edge] = []
        for ln in self.lines.values():
            order = sorted(ln.points, key=cmp_to_key(lambda u, w, ln=ln: cmp(ln.points[u], ln.points[w])))
            pos = {v: i for i, v in enumerate(order)}
            cover = [[] for _ in range(len(order) - 1)]
            for pc in ln.pieces:
                i0, i1 = sorted((pos[pc.v0], pos[pc.v1]))
                for k in range(i0, i1):
                    cover[k].append(pc)
            for k, pcs in enumerate(cover):
                if pcs:
                    edges.append(self._edge(ln, order[k], order[k + 1], pcs))
        for c in self.circles.values():
            def acmp(u, w, c=c):
                return _acmp(c, ("q2", self.V.x[u], self.V.y[u]), ("q2", self.V.x[w], self.V.y[w]))

            order = sorted(c.points, key=cmp_to_key(acmp))
            n = len(order)
            pos = {v: i for i, v in enumerate(order)}
            cover = [[] for _ in range(n)]
            for pc in c.pieces:
                if pc.v0 is None:
                    for k in range(n):
                        cover[k].append(pc)
                    continue
                i0, i1 = (pos[pc.v0], pos[pc.v1]) if pc.ccw else (pos[pc.v1], pos[pc.v0])
                k = i0
                while True:
                    cover[k].append(pc)
                    k = (k + 1) % n
                    if k == i1:
                        break
            for k, pcs in enumerate(cover):
                if pcs:
                    edges.append(self._edge(c, order[k], order[(k + 1) % n], pcs))
        for i, e in enumerate(edges):
            e.index = i
        return edges

    def _edge(self, curve, a: int, b: int, pcs: list) -> _Edge:
        feats = [pc.feature for pc in pcs if pc.feature >= 0]
        if len(feats) != len(set(feats)):
            dup = next(x for x in feats if feats.count(x) > 1)
            f = self.comp.features[dup]
            raise GeometryError(f"feature {f.name!r}: its boundary overlaps itself along "
                                f"{sorted(pc.name for pc in pcs if pc.feature == dup)}")
        toggles, segs = set(), set()
        for pc in pcs:
            if pc.feature < 0:
                toggles.add(-1)
            elif self.comp.features[pc.feature].type == "segment":
                segs.add(pc.feature)
            else:
                toggles.add(pc.feature)
        return _Edge(curve, a, b, frozenset(pc.name for pc in pcs), frozenset(toggles), frozenset(segs))

    # -- faces, ownership, survival -------------------------------------------

    def run(self) -> RegionComplex:
        comp = self.comp
        self.add_domain()
        for i, f in enumerate(comp.features):
            self.add_feature(i, f)
        for pc in self.pieces:
            pc.curve.pieces.append(pc)
        self.intersect_all()
        edges = self.elementary_edges()
        dcel = _Dcel(self.V, edges)
        membership = self._memberships(dcel)
        owner = [self._owner(m) for m in membership]          # per face: feature index, -1 background, None exterior
        region_of_face = [self._region_name(o) for o in owner]

        def survives(e: _Edge) -> bool:
            h = 2 * e.index
            fa, fb = dcel.face_left_of(h), dcel.face_left_of(h ^ 1)
            ra, rb = region_of_face[fa], region_of_face[fb]
            if ra is None and rb is None:
                return False
            if ra is None or rb is None or ra != rb:
                return True
            if not e.segment_features:
                return comp.finalize == "imprint"            # a covered feature boundary
            # a segment survives unless a later area feature covers it from both sides
            covered = all(o >= 0 and o > s for o in (owner[fa], owner[fb]) for s in e.segment_features)
            return not covered or (comp.finalize == "imprint" and bool(e.toggles))

        kept = [e for e in edges if survives(e)]
        cell_edges = [_Edge(e.curve, e.a, e.b, e.provenance, e.toggles, e.segment_features, i)
                      for i, e in enumerate(kept)]
        d2 = _Dcel(self.V, cell_edges)
        # pass-1 faces joined across dropped edges form one cell; the cell lists every feature
        # that owns one of them, and its representative is the earliest of those
        parent = list(range(len(dcel.faces)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        kept_ids = {e.index for e in kept}
        for e in edges:
            if e.index not in kept_ids:
                h = 2 * e.index
                parent[find(dcel.face_left_of(h))] = find(dcel.face_left_of(h ^ 1))
        group_owners: dict[int, set] = {}
        for fi in range(len(dcel.faces)):
            if owner[fi] is not None:
                group_owners.setdefault(find(fi), set()).add(fi)
        cells: list[Cell] = []
        cell_of_face: dict[int, int] = {}
        for fi, (outer, holes) in enumerate(d2.faces):
            if outer is None:
                continue
            h = d2.cycles[outer][0]
            h_old = 2 * kept[d2.he_edge[h].index].index + (0 if d2.he_fwd[h] else 1)
            group = find(dcel.face_left_of(h_old))
            faces1 = group_owners.get(group)
            if not faces1:
                continue
            owners = sorted({owner[f1] for f1 in faces1})
            o = owners[0]
            rep_face = min(faces1, key=lambda f1: (owner[f1], f1))
            idx = len(cells)
            cell_of_face[fi] = idx
            loops = [[(d2.he_edge[k].index, d2.he_fwd[k]) for k in d2.cycles[cy]] for cy in (outer, *holes)]
            area = sum(self._cycle_area(d2, d2.cycles[cy]) for cy in (outer, *holes))
            if o < 0:
                cells.append(Cell(idx, "background", comp.background.get("material", _MISSING), "background", -1,
                                  comp.background.get("mesh_size"), loops, area, membership[rep_face], frozenset({-1})))
            else:
                feats = [comp.features[i] for i in owners]
                sizes = [f.mesh_size for f in feats if f.mesh_size is not None]
                cells.append(Cell(idx, feats[0].region, feats[0].material, feats[0].id, o,
                                  min(sizes) if sizes else None, loops, area, membership[rep_face], frozenset(owners)))
        whole = {key: _whole_circle(cell_edges, c) for key, c in self.circles.items()}
        curves = []
        for e in cell_edges:
            h = 2 * e.index
            left = cell_of_face.get(d2.face_left_of(h))
            right = cell_of_face.get(d2.face_left_of(h ^ 1))
            if e.curve.kind == "line":
                curves.append(Curve(e.index, "line", e.a, e.b, {}, e.provenance, left, right))
            else:
                c = e.curve
                kind = "circle" if whole[(c.cx, c.cy, c.r2)] else "arc"
                curves.append(Curve(e.index, kind, e.a, e.b, {"center": (c.cx, c.cy), "r2": c.r2}, e.provenance,
                                    left, right))
        rc = RegionComplex(comp.name, comp.dimension, dict(comp.domain), list(zip(self.V.x, self.V.y)), cells,
                           curves, {}, self.notes, d2, _component=comp)
        _default_tags(rc)
        _apply_boundary_tags(rc, comp)
        rc.selections = _resolve_selections(rc, comp)
        return rc

    @staticmethod
    def _memberships(dcel: _Dcel) -> list:
        """The set of containing features (and -1 for the domain) of every face, by crossing
        edges outward from the unbounded face (face 0) and toggling what each edge bounds."""
        member = [None] * len(dcel.faces)
        member[0] = frozenset()
        queue = [0]
        while queue:
            fi = queue.pop()
            outer, holes = dcel.faces[fi]
            for cy in ([outer] if outer is not None else []) + holes:
                for h in dcel.cycles[cy]:
                    other = dcel.face_left_of(h ^ 1)
                    m = member[fi] ^ dcel.he_edge[h].toggles
                    if member[other] is None:
                        member[other] = m
                        queue.append(other)
                    elif member[other] != m:
                        raise GeometryError("internal: inconsistent containment across an edge")
        if any(m is None for m in member):
            raise GeometryError("internal: a face the crossing walk did not reach")
        return member

    @staticmethod
    def _owner(m: frozenset):
        if -1 not in m:
            return None
        feats = [i for i in m if i >= 0]
        return max(feats) if feats else -1

    def _region_name(self, o):
        if o is None:
            return None
        return "background" if o < 0 else self.comp.features[o].region

    def _cycle_area(self, dcel: _Dcel, cyc: list[int]) -> float:
        """Signed area: the exact chord polygon plus the circular segments in floating point."""
        twice = ZERO
        seg = 0.0
        for h in cyc:
            a, b = dcel.src(h), dcel.dst(h)
            xa, ya = self.V.x[a].approx(), self.V.y[a].approx()
            xb, yb = self.V.x[b].approx(), self.V.y[b].approx()
            twice += xa * yb - xb * ya
            e = dcel.he_edge[h]
            if e.curve.kind == "circle":
                c = e.curve
                t0 = math.atan2(float(self.V.y[a] - c.cy), float(self.V.x[a] - c.cx))
                t1 = math.atan2(float(self.V.y[b] - c.cy), float(self.V.x[b] - c.cx))
                th = (t1 - t0) % (2 * math.pi) if dcel.he_fwd[h] else (t0 - t1) % (2 * math.pi)
                piece = 0.5 * c.r2 * (th - math.sin(th))
                seg += piece if dcel.he_fwd[h] else -piece
        return float(twice / 2) + seg


def _whole_circle(edges: list[_Edge], c: _Circle) -> bool:
    """True when the kept edges of this circle cover it and no other curve touches its vertices."""
    own = [e for e in edges if e.curve is c]
    verts = {e.a for e in own} | {e.b for e in own}
    if not own or len(own) != len(c.points) or len(verts) != len(c.points):
        return False
    return not any(e.curve is not c and (e.a in verts or e.b in verts) for e in edges)


def _line_circle_points(p0, d, c: _Circle):
    """Exact intersections of the line p0 + t*d (rational p0, integer d) with the circle."""
    dx, dy = d
    wx, wy = p0[0] - c.cx, p0[1] - c.cy
    A = dx * dx + dy * dy
    B = 2 * (dx * wx + dy * wy)
    Cc = wx * wx + wy * wy - c.r2
    disc = B * B - 4 * A * Cc
    if disc < 0:
        return []
    if disc == 0:
        t = Q2(Fraction(-B) / (2 * A))
        return [(Q2(p0[0]) + t * dx, Q2(p0[1]) + t * dy)]
    disc = Fraction(disc)
    root = Q2(0, Fraction(1, disc.denominator), disc.numerator * disc.denominator)      # sqrt(disc)
    out = []
    for s in (1, -1):
        t = (Q2(-B) + root * s) * Fraction(1, 2 * A)
        out.append((Q2(p0[0]) + t * dx, Q2(p0[1]) + t * dy))
    return out


def _boxes_meet(a, b) -> bool:
    return not (a[1] < b[0] or b[1] < a[0] or a[3] < b[2] or b[3] < a[2])


def _box_inside(inner, outer) -> bool:
    return (cmp(outer[0], inner[0]) <= 0 and cmp(inner[1], outer[1]) <= 0
            and cmp(outer[2], inner[2]) <= 0 and cmp(inner[3], outer[3]) <= 0)


def _box_cmp(p, q) -> int:
    """-1 when box p lies inside box q (nested candidates), 1 the other way."""
    if _box_inside(p, q):
        return -1 if not _box_inside(q, p) else 0
    return 1


# ----------------------------------------------------------------------- tags and selectors

def _default_tags(rc: RegionComplex) -> None:
    sides = {f"domain.{s}": s for s in ("left", "right", "bottom", "top", "axis")}
    for i in rc.exterior_curves():
        k = rc.curves[i]
        k.tag = next((sides[name] for name in k.provenance if name in sides), "outer")


def _apply_boundary_tags(rc: RegionComplex, comp: Component) -> None:
    exterior = set(rc.exterior_curves())
    tagged: set[int] = set()
    for entry in comp.boundary_tags:
        tag = entry["tag"]
        for i in _resolve_boundary(rc, comp, entry["select"]["boundary"], f"boundary_tags {tag!r}", ()):
            if i in exterior and i not in tagged:
                rc.curves[i].tag = tag
                tagged.add(i)


def _resolve_selections(rc: RegionComplex, comp: Component) -> dict:
    out = {}
    for name, sel in comp.selections.items():
        kind = "region" if "region" in sel else "boundary"
        resolve = _resolve_region if kind == "region" else _resolve_boundary
        chosen = resolve(rc, comp, sel[kind], f"selection {name!r}", (name,))
        if not chosen and not sel.get("optional", False):
            raise GeometryError(f"component {comp.name!r}: selection {name!r} selects nothing")
        out[name] = (kind, frozenset(chosen))
    return out


def _feature_by_id(comp: Component, fid: str):
    for i, f in enumerate(comp.features):
        if f.id == fid:
            return i, f
    return None, None


def _named(comp: Component, expr: str, kind: str, where: str, stack: tuple):
    """The selector of a named selection of this kind, or None."""
    sel = comp.selections.get(expr)
    if sel is None or kind not in sel:
        return None
    if expr in stack:
        raise GeometryError(f"{where}: selection {expr!r} refers to itself")
    return sel[kind]


def _resolve_region(rc: RegionComplex, comp: Component, expr, where: str, stack: tuple) -> set[int]:
    if isinstance(expr, str):
        hits = []
        inner = _named(comp, expr, "region", where, stack)
        if inner is not None:
            hits.append(("selection", _resolve_region(rc, comp, inner, where, stack + (expr,))))
        regions = {f.region for f in comp.features if f.type != "segment"} | {"background"}
        i, f = _feature_by_id(comp, expr)
        if expr in regions:
            hits.append(("region", {c.index for c in rc.cells if c.region == expr}))
        if f is not None and not (expr in regions and f.region == expr):
            hits.append(("feature", {c.index for c in rc.cells if i in c.feature_indices}))
        if len(hits) > 1:
            raise GeometryError(f"{where}: {expr!r} is both a {hits[0][0]} and a {hits[1][0]}")
        if not hits:
            raise GeometryError(f"{where}: {expr!r} is not a selection, a region or a feature id")
        return hits[0][1]
    (k, v), = expr.items()
    if k == "feature":
        i, f = _feature_by_id(comp, v)
        if f is None:
            raise GeometryError(f"{where}: no feature {v!r}")
        return {c.index for c in rc.cells if i in c.feature_indices}
    if k == "material":
        return {c.index for c in rc.cells if c.material == v}
    if k == "any":
        out: set[int] = set()
        for e in v:
            out |= _resolve_region(rc, comp, e, where, stack)
        return out
    raise GeometryError(f"{where}: {k!r} selects boundaries, not regions")


def _resolve_boundary(rc: RegionComplex, comp: Component, expr, where: str, stack: tuple) -> set[int]:
    if isinstance(expr, str):
        inner = _named(comp, expr, "boundary", where, stack)
        if inner is not None:
            return _resolve_boundary(rc, comp, inner, where, stack + (expr,))
        if expr in SIDE_TAGS or any(e["tag"] == expr for e in comp.boundary_tags):
            return {k.index for k in rc.curves if k.tag == expr}
        if "." in expr:
            return set(rc.curves_with(expr))
        _i, f = _feature_by_id(comp, expr)
        if f is None:
            raise GeometryError(f"{where}: {expr!r} is not a selection, a tag, a provenance name or a feature id")
        return _curves_of_feature(rc, f.id)
    (k, v), = expr.items()
    if k == "feature":
        _i, f = _feature_by_id(comp, v)
        if f is None:
            raise GeometryError(f"{where}: no feature {v!r}")
        return _curves_of_feature(rc, f.id)
    if k == "provenance":
        return set(rc.curves_with(v))
    if k == "material":
        return _boundary_of(rc, {c.index for c in rc.cells if c.material == v})
    if k == "of":
        return _boundary_of(rc, _resolve_region(rc, comp, v, where, stack))
    if k == "between":
        a, b = v
        sa = None if a == "exterior" else _resolve_region(rc, comp, a, where, stack)
        sb = None if b == "exterior" else _resolve_region(rc, comp, b, where, stack)
        out = set()
        for c in rc.curves:
            if (_side_in(c.left, sa) and _side_in(c.right, sb)) or (_side_in(c.left, sb) and _side_in(c.right, sa)):
                out.add(c.index)
        return out
    if k == "any":
        out: set[int] = set()
        for e in v:
            out |= _resolve_boundary(rc, comp, e, where, stack)
        return out
    raise GeometryError(f"{where}: unknown selector key {k!r}")


def _side_in(cell, selection) -> bool:
    if selection is None:
        return cell is None
    return cell is not None and cell in selection


def _curves_of_feature(rc: RegionComplex, fid: str) -> set[int]:
    prefix = fid + "."
    return {k.index for k in rc.curves if any(p.startswith(prefix) for p in k.provenance)}


def _boundary_of(rc: RegionComplex, cells: set[int]) -> set[int]:
    return {k.index for k in rc.curves if (k.left in cells) != (k.right in cells)}


# ----------------------------------------------------------------------- meshine hand-off

def _resolve_controls(rc: RegionComplex, controls: list) -> tuple[dict, dict]:
    """({circle key: requested vertex count}, {cell index: size in pm}) of ``mesh.controls``."""
    counts: dict[tuple, int] = {}
    sizes: dict[int, int] = {}
    for entry in controls:
        kind, chosen = rc.select(entry["select"])
        if "circle_segments" in entry:
            if kind == "region":
                curves = _boundary_of(rc, set(chosen)) | {k.index for k in rc.curves
                                                          if k.left in chosen and k.right in chosen}
            else:
                curves = set(chosen)
            for i in curves:
                k = rc.curves[i]
                if k.kind != "line":
                    counts[(k.params["center"], k.params["r2"])] = int(entry["circle_segments"])
        if "size" in entry:
            if kind != "region":
                raise GeometryError(f"mesh.controls: select {entry['select']!r} is a boundary selection; a size "
                                    "on a boundary is not implemented yet (give the size to a region)")
            for ci in chosen:
                sizes[ci] = entry["size"]
    return counts, sizes


def _to_domain(rc: RegionComplex, size: float, unit_pm: Fraction, Circle, Domain, mesh_sizes: bool,
               min_area: float, controls: list):
    V = rc._dcel.V
    scale = 1 / unit_pm
    coords: dict[int, tuple[float, float]] = {}

    def pt(v: int):
        if v not in coords:
            coords[v] = (float(V.x[v].approx() * scale), float(V.y[v].approx() * scale))
        return coords[v]

    check_handoff(rc)
    rc.notes = [n for n in rc.notes if not n.startswith(("geometry.features: a piece of", "mesh.controls:"))]
    poly: dict[int, list | None] = {}
    circle_objs: dict[tuple, object] = {}
    for k in rc.curves:
        if k.kind == "line":
            poly[k.index] = [pt(k.a), pt(k.b)]
    requested, cell_sizes = _resolve_controls(rc, controls)
    counts = _circle_vertex_counts(rc, poly, pt, unit_pm, size, requested)
    for k in rc.curves:
        if k.kind == "line":
            continue
        key = (k.params["center"], k.params["r2"])
        r = math.sqrt(k.params["r2"]) / unit_pm
        n = counts[key]
        if k.kind == "circle":
            if key not in circle_objs:
                circle_objs[key] = Circle((float(key[0][0] / unit_pm), float(key[0][1] / unit_pm)), r, n=n)
            poly[k.index] = None
            continue
        pa, pb = pt(k.a), pt(k.b)
        cx, cy = float(key[0][0] / unit_pm), float(key[0][1] / unit_pm)
        t0 = math.atan2(pa[1] - cy, pa[0] - cx)
        th = (math.atan2(pb[1] - cy, pb[0] - cx) - t0) % (2 * math.pi)
        m = max(2, math.ceil(n * th / (2 * math.pi)))
        pts = [pa] + [(cx + r * math.cos(t0 + th * i / m), cy + r * math.sin(t0 + th * i / m)) for i in range(1, m)]
        pts.append(pb)
        poly[k.index] = pts
    _check_rounded_topology(rc, poly, coords)
    rc._handoff = {"poly": poly, "circles": circle_objs, "unit_pm": unit_pm}
    d = Domain(size=size)
    materials: dict[str, object] = {}
    skipped: set[int] = set()
    for region in rc.region_names():
        for ci in rc.cells_of_region(region):
            cell = rc.cells[ci]
            if cell.void:
                continue
            if cell.area < min_area:
                skipped.add(ci)
                rc.notes.append(f"geometry.features: a piece of {cell.region!r} covers {cell.area / float(unit_pm) ** 2:g} "
                                f"square mesher units, under the sliver limit, so it is left out of the mesh")
                continue
            _add_cell(d, rc, cell, poly, circle_objs, unit_pm, mesh_sizes, cell_sizes.get(ci))
            materials[cell.region] = cell.material
    exterior_segments = []
    for k in rc.curves:
        if not (rc.is_exterior(k.left) or rc.is_exterior(k.right) or k.left in skipped or k.right in skipped):
            continue
        pts = poly[k.index]
        if pts is None:
            vs = circle_objs[(k.params["center"], k.params["r2"])].vertices()
            pts = [tuple(v) for v in vs] + [tuple(vs[0])]
        for p, q in zip(pts[:-1], pts[1:]):
            exterior_segments.append((p, q, k.tag or "outer"))

    def namer(mid):
        best, best_d = "outer", math.inf
        for p, q, tag in exterior_segments:
            dd = _point_segment_distance(mid, p, q)
            if dd < best_d:
                best, best_d = tag, dd
        return best

    return d, namer, materials


#: A circle's polygon may not need more vertices than this to keep clear of its neighbours.
MAX_CIRCLE_VERTICES = 20000


def _circle_vertex_counts(rc: RegionComplex, poly: dict, pt, unit_pm: Fraction, size: float,
                          requested: dict | None = None) -> dict:
    """The vertex count of every circle's polygon: the 0.2 rule max(16, 2 pi r / (size / 2)),
    or the count a ``circle_segments`` control asked for (``requested``, by circle key),
    raised for a whole circle so that the sagitta of its polygon's chords stays below the
    distance from the circle line to the nearest other curve. A chord that cut across a
    neighbouring feature's corner would give the mesher crossing loops; meshine projects
    inserted nodes back onto a whole circle, so the count only sets where the chords start.
    A whole circle that would need more than MAX_CIRCLE_VERTICES is refused by name."""
    requested = requested or {}
    circles: dict[tuple, float] = {}
    whole: set = set()
    for k in rc.curves:
        if k.kind != "line":
            circles.setdefault((k.params["center"], k.params["r2"]), math.sqrt(k.params["r2"]) / unit_pm)
            if k.kind == "circle":
                whole.add((k.params["center"], k.params["r2"]))
    segments = [(poly[k.index][0], poly[k.index][1]) for k in rc.curves if k.kind == "line"]
    arcs = [(k.params["center"], k.params["r2"], pt(k.a), pt(k.b)) for k in rc.curves if k.kind == "arc"]
    counts = {}
    for key, r in circles.items():
        c = (float(key[0][0] / unit_pm), float(key[0][1] / unit_pm))
        n = requested.get(key, max(16, int(2 * math.pi * r / (size / 2))))
        if key not in whole:
            # a cut circle's arcs meet other curves at vertices; a chord of theirs that crosses a
            # neighbour is caught by the crossing check of the rounded polylines
            counts[key] = n
            continue
        gap = math.inf
        for p, q in segments:
            near = _point_segment_distance(c, p, q)
            far = max(math.hypot(p[0] - c[0], p[1] - c[1]), math.hypot(q[0] - c[0], q[1] - c[1]))
            if near <= r <= far:
                gap = 0.0
            else:
                gap = min(gap, abs(near - r) if near > r else r - far)
        for centre, r2, pa, pb in arcs:
            # a kept arc of another circle: its ends, and the point of its circle nearest to
            # this circle's line when that point lies on the arc
            if (centre, r2) == key:
                continue
            o = (float(centre[0] / unit_pm), float(centre[1] / unit_pm))
            ro = math.sqrt(r2) / unit_pm
            for q in (pa, pb):
                gap = min(gap, abs(math.hypot(q[0] - c[0], q[1] - c[1]) - r))
            dist = math.hypot(o[0] - c[0], o[1] - c[1])
            if dist == 0:
                gap = min(gap, abs(ro - r))
                continue
            ux, uy = (c[0] - o[0]) / dist, (c[1] - o[1]) / dist
            t0 = math.atan2(pa[1] - o[1], pa[0] - o[0])
            span = (math.atan2(pb[1] - o[1], pb[0] - o[0]) - t0) % (2 * math.pi)
            for sgn in (1, -1):
                px, py = o[0] + sgn * ro * ux, o[1] + sgn * ro * uy
                if (math.atan2(py - o[1], px - o[0]) - t0) % (2 * math.pi) <= span:
                    gap = min(gap, abs(math.hypot(px - c[0], py - c[1]) - r))
        for other, r2 in circles.items():
            if other == key or other not in whole:
                continue
            o = (float(other[0][0] / unit_pm), float(other[0][1] / unit_pm))
            dist = math.hypot(o[0] - c[0], o[1] - c[1])
            gap = min(gap, max(dist - r - r2, r - dist - r2, r2 - dist - r, 0.0))
        if gap < math.inf and gap > 0:
            needed = math.ceil(math.pi * math.sqrt(r / (2 * gap))) + 1
            if key in requested and needed > n:
                names = sorted({p for k in rc.curves if k.kind != "line"
                                and (k.params["center"], k.params["r2"]) == key for p in k.provenance})
                rc.notes.append(f"mesh.controls: circle_segments {n} of the circle of {names} raised to {needed} "
                                "to keep its chords clear of the nearest other curve")
            n = max(n, needed)
        if n > MAX_CIRCLE_VERTICES or gap == 0.0:
            names = sorted({p for k in rc.curves if k.kind != "line" and (k.params["center"], k.params["r2"]) == key
                            for p in k.provenance})
            raise GeometryError(f"hand-off: the circle of {names} passes within {gap:g} mesher units of another "
                                f"curve; its polygon would need more than {MAX_CIRCLE_VERTICES} vertices to keep "
                                "its chords clear of that curve")
        counts[key] = n
    return counts


def _add_cell(d, rc: RegionComplex, cell: Cell, poly: dict, circle_objs: dict, unit_pm: Fraction,
              mesh_sizes: bool, size_pm=None) -> None:
    loops = []
    for loop in cell.loops:
        if all(rc.curves[i].kind == "circle" for i, _f in loop):
            loops.append(circle_objs[(rc.curves[loop[0][0]].params["center"], rc.curves[loop[0][0]].params["r2"])])
            continue
        verts = []
        for i, fwd in loop:
            pts = poly[i] if fwd else poly[i][::-1]
            verts.extend(pts[:-1])
        loops.append(verts)
    size_pm = cell.mesh_size if size_pm is None else size_pm
    d.add_region(cell.region, loops[0], holes=loops[1:],
                 size=(float(size_pm / unit_pm) if size_pm is not None and mesh_sizes else None))


def _curve_edges(rc: RegionComplex, mesh) -> dict:
    import numpy as np
    nodes = np.asarray(mesh.nodes, dtype=float)
    tris = np.asarray(mesh.triangles, dtype=int)
    pairs = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    pairs.sort(axis=1)
    mesh_edges = {tuple(e) for e in np.unique(pairs, axis=0)}
    lo, hi = nodes.min(axis=0), nodes.max(axis=0)
    tol = 1e-9 * float(np.hypot(*(hi - lo)))
    poly, circles = rc._handoff["poly"], rc._handoff["circles"]
    # every hand-off point has a node, except one that meshine may have snapped away: an end of
    # an input edge shorter than SNAP_EPS of the diagonal (meshine.geometry.SNAP_EPS = 3e-8)
    points = [p for pts in poly.values() for p in (pts or ())]
    snap = 3e-8 * float(np.hypot(*(hi - lo)))
    for p in points:
        if np.min(np.hypot(nodes[:, 0] - p[0], nodes[:, 1] - p[1])) <= tol:
            continue
        if any(q is not p and 0 < math.hypot(q[0] - p[0], q[1] - p[1]) <= 2 * snap for q in points):
            continue
        raise GeometryError("curve_edges: the mesh has no node at a hand-off vertex; it does not come from "
                            "the last to_domain of this complex (another size or unit?)")
    out = {}

    def chain(order_nodes):
        found = []
        for a, b in zip(order_nodes[:-1], order_nodes[1:]):
            e = (min(a, b), max(a, b))
            if e in mesh_edges:
                found.append(e)
        return found

    for k in rc.curves:
        found = []
        pts = poly[k.index]
        if pts is None:                                        # a whole circle: nodes on it, chained by angle
            c = circles[(k.params["center"], k.params["r2"])]
            d = nodes - c.center
            on = np.nonzero(np.abs(np.hypot(d[:, 0], d[:, 1]) - c.radius) <= tol)[0]
            if len(on) >= 2:
                ang = np.arctan2(d[on, 1], d[on, 0])
                order = [int(i) for _a, i in sorted(zip(ang, on))]
                ring = chain(order + order[:1])
                # the edge belongs to the arc (a -> b counter-clockwise) that holds its midpoint angle
                pa, pb = _vertex_um(rc, k.a), _vertex_um(rc, k.b)
                ta = math.atan2(pa[1] - c.center[1], pa[0] - c.center[0])
                span = (math.atan2(pb[1] - c.center[1], pb[0] - c.center[0]) - ta) % (2 * math.pi)
                for e in ring:
                    m = 0.5 * (nodes[e[0]] + nodes[e[1]]) - c.center
                    if (math.atan2(m[1], m[0]) - ta) % (2 * math.pi) < span:
                        found.append(e)
            out[k.index] = np.array(sorted(set(found)), dtype=int).reshape(-1, 2)
            continue
        for p, q in zip(pts[:-1], pts[1:]):
            p, q = np.asarray(p), np.asarray(q)
            dvec = q - p
            L = float(np.hypot(*dvec))
            w = nodes - p
            t = (w @ dvec) / L
            perp = np.abs(dvec[0] * w[:, 1] - dvec[1] * w[:, 0]) / L
            on = np.nonzero((perp <= tol) & (t >= -tol) & (t <= L + tol))[0]
            ordered = [int(i) for _t, i in sorted(zip(t[on], on))]
            found.extend(chain(ordered))
        out[k.index] = np.array(sorted(set(found)), dtype=int).reshape(-1, 2)
    return out


def _vertex_um(rc: RegionComplex, v: int):
    unit_pm = rc._handoff["unit_pm"]
    x, y = rc.vertices[v]
    return (float(x.approx() / unit_pm), float(y.approx() / unit_pm))


def check_handoff(rc: RegionComplex) -> None:
    """Refuse what the mesher cannot take: a curve with one cell on both sides (a segment inside a cell)."""
    for k in rc.curves:
        if k.left is not None and k.left == k.right:
            raise GeometryError(f"hand-off: curve {sorted(k.provenance)} lies inside region "
                                f"{rc.cells[k.left].region!r} with that region on both sides; meshine takes region "
                                "loops only, so a segment feature inside a region cannot be handed over")


def _point_segment_distance(m, p, q) -> float:
    dx, dy = q[0] - p[0], q[1] - p[1]
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(m[0] - p[0], m[1] - p[1])
    t = max(0.0, min(1.0, ((m[0] - p[0]) * dx + (m[1] - p[1]) * dy) / L2))
    return math.hypot(m[0] - p[0] - t * dx, m[1] - p[1] - t * dy)


def _check_rounded_topology(rc: RegionComplex, poly: dict, coords: dict) -> None:
    """Refuse a hand-off whose rounded polylines collapse or cross."""
    seen: dict[tuple, int] = {}
    for v, p in coords.items():
        if p in seen:
            raise GeometryError(f"hand-off: vertices {seen[p]} and {v} round to the same point {p}")
        seen[p] = v
    segs = []
    for i, pts in poly.items():
        if pts is None:
            continue
        for p, q in zip(pts[:-1], pts[1:]):
            if p == q:
                raise GeometryError(f"hand-off: curve {sorted(rc.curves[i].provenance)} has a zero-length piece "
                                    "after rounding")
            segs.append((min(p[0], q[0]), max(p[0], q[0]), p, q, i))
    segs.sort()
    for a in range(len(segs)):
        _x0, x1, p1, q1, i1 = segs[a]
        for b in range(a + 1, len(segs)):
            x0b, _x1b, p2, q2, i2 = segs[b]
            if x0b > x1:
                break
            if {p1, q1} & {p2, q2}:
                continue
            if _float_segments_cross(p1, q1, p2, q2):
                raise GeometryError(f"hand-off: curves {sorted(rc.curves[i1].provenance)} and "
                                    f"{sorted(rc.curves[i2].provenance)} cross after rounding")


def _float_segments_cross(p, q, r, s) -> bool:
    def orient(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return (v > 0) - (v < 0)

    d1, d2, d3, d4 = orient(r, s, p), orient(r, s, q), orient(p, q, r), orient(p, q, s)
    if d1 * d2 < 0 and d3 * d4 < 0:
        return True

    def on(a, b, c):
        return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])

    return ((d1 == 0 and on(r, s, p)) or (d2 == 0 and on(r, s, q))
            or (d3 == 0 and on(p, q, r)) or (d4 == 0 and on(p, q, s)))
