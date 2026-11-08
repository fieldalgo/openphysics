# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Geometry document version 1: design velocity V = dx/dp (stage 4, prototype).

``design_velocity(document, parameter)`` evaluates one 2D or axisymmetric component
and returns, for one independent length parameter ``p``:

- the velocity of every defining value (by JSON path), from the exact unrounded
  expressions (forward-mode derivative in rational arithmetic);
- the velocity of every vertex of the region complex, defining or derived
  (intersections of lines and circles), solved exactly from the motion of the
  curves through it (implicit differentiation, numbers ``a + b*sqrt(D)``);
- the motion of every curve: end velocities of a line, centre velocity and
  ``dr/dp`` of an arc or circle;
- the velocity of mesh nodes that lie on curves (``node_velocity``), the hand-off
  to galerkin, which moves interior nodes.

``V`` is dimensionless: x and p are both lengths in the document unit, so V does
not depend on the unit.

The derivative is refused, with the features named, when the topology of the
complex is not constant around ``p``. Two tests decide that, both exact:

1. **First order at p.** Every vertex's constraints (each curve through it, each
   defining point at it) must agree on one velocity. A touch, a shared edge, a
   T-junction or three concurrent curves persist only if the motion keeps them;
   a contradiction is a topology change. A tangent contact (the constraints fix
   only one direction) is refused.
2. **Probe at p ± delta.** The component is evaluated exactly, without rounding,
   at ``p + delta`` and ``p - delta`` (``delta`` is ``2**-20`` pm divided by the
   largest defining velocity, rounded down to a power of two), on a grid refined
   so that every perturbed defining value is an integer; the combinatorial
   signature (cells, curves with provenance, sides and end-vertex incidence,
   selections) must equal the one at ``p``.

Only the standard library is imported (NumPy lazily in ``node_velocity``).
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from fractions import Fraction

from .geometry_document import (_MISSING, GeometryError, GeometryModel, _Evaluator, _parse, _pick, _Reader,
                                _tokens, parse)
from .geometry_engine import Q2, RegionComplex, _Engine, _vertex_um, cmp

ZERO = Fraction(0)

#: The probe moves the largest defining value by this many picometres (before the power-of-two rounding).
PROBE_PM = Fraction(1, 2 ** 20)


class TopologyChange(GeometryError):
    """The topology of the complex changes at the parameter value: no derivative there.

    ``features`` lists the ids of the features involved (``domain`` for a domain side)."""

    def __init__(self, message: str, features):
        self.features = tuple(sorted(set(features)))
        super().__init__(f"{message} (features: {', '.join(self.features)})")


# ----------------------------------------------------------------------- exact derivatives of expressions

class _Dual:
    """v + d*eps with rational v and d: forward-mode derivative through the expression evaluator."""

    __slots__ = ("v", "d")

    def __init__(self, v, d=ZERO):
        self.v, self.d = Fraction(v), Fraction(d)

    @staticmethod
    def _of(o):
        return o if isinstance(o, _Dual) else _Dual(o)

    def __add__(self, o):
        o = self._of(o)
        return _Dual(self.v + o.v, self.d + o.d)

    __radd__ = __add__

    def __sub__(self, o):
        o = self._of(o)
        return _Dual(self.v - o.v, self.d - o.d)

    def __rsub__(self, o):
        return self._of(o) - self

    def __neg__(self):
        return _Dual(-self.v, -self.d)

    def __mul__(self, o):
        o = self._of(o)
        return _Dual(self.v * o.v, self.v * o.d + self.d * o.v)

    __rmul__ = __mul__

    def __truediv__(self, o):
        o = self._of(o)
        return _Dual(self.v / o.v, (self.d * o.v - self.v * o.d) / (o.v * o.v))

    def __rtruediv__(self, o):
        return self._of(o) / self

    def __eq__(self, o):
        return self.v == (o.v if isinstance(o, _Dual) else o)

    def __lt__(self, o):
        return self.v < (o.v if isinstance(o, _Dual) else o)

    def __le__(self, o):
        return self.v <= (o.v if isinstance(o, _Dual) else o)

    def __gt__(self, o):
        return self.v > (o.v if isinstance(o, _Dual) else o)

    def __ge__(self, o):
        return self.v >= (o.v if isinstance(o, _Dual) else o)

    __hash__ = None


def _seeded(seed: str, value):
    """An evaluator class whose parameter ``seed`` takes ``value`` (a Fraction or a _Dual)."""

    class _Seeded(_Evaluator):
        def parameter(self, name, path):
            if name == seed and name not in self.values:
                self.values[name] = (value, self.raw[name].get("kind", "length"))
            return super().parameter(name, path)

    return _Seeded


class _RecordingReader(_Reader):
    """Records the exact (unrounded) value of every length field and returns the base pm count."""

    def __init__(self, doc, evaluator, base: dict | None = None):
        self.exact: dict[str, object] = {}
        self._base = base
        super().__init__(doc, evaluator)

    def length(self, raw, path):
        value, kind = self.ev.value(raw, path)
        if kind == "ratio":
            raise GeometryError(f"{path}: expected a length, the expression is a ratio")
        self.exact[path] = value
        if self._base is not None:
            return self._base[path]
        v = value.v if isinstance(value, _Dual) else value
        return round(v * self.ppu)


class _TableReader(_Reader):
    """Returns precomputed integer lengths by JSON path (the probe's refined grid)."""

    def __init__(self, doc, table: dict):
        self._table = table
        super().__init__(doc)

    def length(self, raw, path):
        return self._table[path]


# ----------------------------------------------------------------------- results

@dataclass
class CurveMotion:
    """The motion of one curve of the complex.

    A line: ``va`` and ``vb``, the velocities of its end vertices (a point at fraction s
    moves with (1 - s) va + s vb). An arc or circle: ``vc``, the velocity of the centre,
    and ``dr``, dr/dp, besides the end velocities."""

    kind: str
    va: tuple
    vb: tuple
    vc: tuple | None = None
    dr: Q2 | None = None


@dataclass
class DesignVelocity:
    """V = dx/dp of one component for one length parameter (dimensionless, exact)."""

    parameter: str
    complex: RegionComplex
    defining: dict                     # JSON path -> Fraction, every length field of the document
    vertices: dict                     # vertex id -> (Q2, Q2), the vertices the curves use
    curves: dict                       # curve index -> CurveMotion
    delta_pm: Fraction                 # the probe step, in pm of the largest defining motion
    _r2: dict = field(default_factory=dict, repr=False)

    def vertex_velocity(self, v: int) -> tuple[float, float]:
        vx, vy = self.vertices[v]
        return float(vx), float(vy)

    def area_derivative(self, region: str) -> float:
        """d(area)/dp of a region (pm² per pm), from the normal velocity on its boundary."""
        rc = self.complex
        cells = set(rc.cells_of_region(region))
        if not cells:
            raise GeometryError(f"area_derivative: no region {region!r}")
        total = 0.0
        for k in rc.curves:
            for side, sign in ((k.left, 1), (k.right, -1)):
                if side in cells and not (k.left in cells and k.right in cells):
                    total += sign * self._flux(k)
        return total

    def perimeter_derivative(self, region: str) -> float:
        """d(length of the boundary of a region)/dp (dimensionless); curves between two cells of
        the region are not boundary."""
        rc = self.complex
        cells = set(rc.cells_of_region(region))
        if not cells:
            raise GeometryError(f"perimeter_derivative: no region {region!r}")
        return sum(self.length_derivative(k.index) for k in rc.curves
                   if (k.left in cells) != (k.right in cells))

    def length_derivative(self, curve: int) -> float:
        """d(length of one curve)/dp (dimensionless)."""
        k = self.complex.curves[curve]
        m = self.curves[curve]
        (ax, ay), (bx, by) = self.complex.vertices[k.a], self.complex.vertices[k.b]
        if k.kind == "line":
            dx, dy = float(bx - ax), float(by - ay)
            dvx, dvy = float(m.vb[0] - m.va[0]), float(m.vb[1] - m.va[1])
            return (dx * dvx + dy * dvy) / math.hypot(dx, dy)
        cx, cy = k.params["center"]
        r = math.sqrt(k.params["r2"])
        ta, tb, span = _angles(k, self.complex)
        tau_a = _tangential(m.va, m.vc, ta)
        tau_b = _tangential(m.vb, m.vc, tb)
        return float(m.dr) * span + tau_b - tau_a

    def _flux(self, k) -> float:
        """The integral of V . n over the curve, n the normal to the right of a -> b
        (outward for the cell on the left)."""
        m = self.curves[k.index]
        (ax, ay), (bx, by) = self.complex.vertices[k.a], self.complex.vertices[k.b]
        if k.kind == "line":
            sx, sy = (m.va[0] + m.vb[0]) * Fraction(1, 2), (m.va[1] + m.vb[1]) * Fraction(1, 2)
            return float(sx * (by - ay) - sy * (bx - ax))
        # a counter-clockwise arc: the cell on the left is inside the circle, n = outward radial
        r = math.sqrt(k.params["r2"])
        _ta, _tb, span = _angles(k, self.complex)
        rigid = m.vc[0] * (by - ay) - m.vc[1] * (bx - ax)
        return float(rigid) + float(m.dr) * r * span

    def node_velocity(self, mesh):
        """The design velocity of the mesh nodes that lie on curves (the hand-off to galerkin).

        ``mesh`` is the meshine mesh of the complex's last ``to_domain``. Returns
        ``NodeVelocity``: ``values`` (N, 2), ``curve`` (N,) the curve a node lies on (-1 for
        an interior node, whose value is zero and is galerkin's to choose), ``vertex`` (N,)
        the vertex a node sits at (-1 otherwise). On a line a node at fraction s moves with
        (1 - s) va + s vb; on an arc with vc + dr n + tau t, tau interpolated linearly in
        angle between the ends' tangential parts (zero on a whole circle)."""
        import numpy as np
        rc = self.complex
        by_curve = rc.curve_edges(mesh)
        nodes = np.asarray(mesh.nodes, dtype=float)
        lo, hi = nodes.min(axis=0), nodes.max(axis=0)
        tol = 1e-9 * float(np.hypot(*(hi - lo)))
        n = len(nodes)
        values = np.zeros((n, 2))
        curve = np.full(n, -1, dtype=int)
        vertex = np.full(n, -1, dtype=int)
        unit_pm = rc._handoff["unit_pm"]
        for k in rc.curves:
            on = np.unique(by_curve[k.index].ravel())
            if not len(on):
                continue
            m = self.curves[k.index]
            pa, pb = np.array(_vertex_um(rc, k.a)), np.array(_vertex_um(rc, k.b))
            for i in on:
                p = nodes[i]
                for v, pv in ((k.a, pa), (k.b, pb)):
                    if np.hypot(*(p - pv)) <= tol:
                        vertex[i] = v
                        values[i] = self.vertex_velocity(v)
                        curve[i] = k.index
                        break
                else:
                    curve[i] = k.index
                    values[i] = _on_curve(k, m, p, pa, pb, rc, unit_pm)
        return NodeVelocity(values, curve, vertex)


@dataclass
class NodeVelocity:
    values: object                     # (N, 2) float, dimensionless
    curve: object                      # (N,) int, -1 interior
    vertex: object                     # (N,) int, -1 when not at a vertex

    @property
    def on_curve(self):
        return self.curve >= 0


def _angles(k, rc: RegionComplex):
    cx, cy = k.params["center"]
    (ax, ay), (bx, by) = rc.vertices[k.a], rc.vertices[k.b]
    ta = math.atan2(float(ay - cy), float(ax - cx))
    tb = math.atan2(float(by - cy), float(bx - cx))
    span = (tb - ta) % (2 * math.pi)
    if span == 0.0:
        span = 2 * math.pi
    return ta, tb, span


def _tangential(v, vc, theta) -> float:
    return -math.sin(theta) * float(v[0] - vc[0]) + math.cos(theta) * float(v[1] - vc[1])


def _on_curve(k, m: CurveMotion, p, pa, pb, rc, unit_pm):
    if k.kind == "line":
        d = pb - pa
        s = float(((p - pa) @ d) / (d @ d))
        return ((1 - s) * float(m.va[0]) + s * float(m.vb[0]), (1 - s) * float(m.va[1]) + s * float(m.vb[1]))
    cx, cy = (float(c / unit_pm) for c in k.params["center"])
    th = math.atan2(p[1] - cy, p[0] - cx)
    ta, tb, span = _angles(k, rc)
    phi = ((th - ta) % (2 * math.pi)) / span
    tau = (1 - phi) * _tangential(m.va, m.vc, ta) + phi * _tangential(m.vb, m.vc, tb)
    dr = float(m.dr)
    return (float(m.vc[0]) + dr * math.cos(th) - tau * math.sin(th),
            float(m.vc[1]) + dr * math.sin(th) + tau * math.cos(th))


# ----------------------------------------------------------------------- the entry point

def design_velocity(document: dict, parameter: str, component: str | None = None) -> DesignVelocity:
    """V = dx/dp of a version 1 document's 2D or axisymmetric component for one parameter.

    ``parameter`` must be an independent length parameter: its ``value`` a number, or an
    expression without parameter names. Refused by name: an unknown, ratio or derived
    parameter; a 3d component; an arc of a ``path`` whose centre, start or end moves;
    a topology change (``TopologyChange``, which names the features).
    """
    model = parse(document)
    _check_parameter(document, parameter)
    comp = _pick(model, component)
    if comp.dimension == "3d":
        raise GeometryError(f"design velocity: component {comp.name!r} is 3d; this stage covers 2d and axisymmetric")
    p0 = model.parameters[parameter][0]
    rec = _RecordingReader(document, _seeded(parameter, _Dual(p0, 1)))
    _parse(rec, document)
    defining = {path: (x.d if isinstance(x, _Dual) else ZERO) for path, x in rec.exact.items()}
    base_exact = {path: (x.v if isinstance(x, _Dual) else x) for path, x in rec.exact.items()}
    engine = _Engine(comp)
    rc = engine.run()
    motions = _piece_motions(engine, comp, defining)
    vertices = _vertex_velocities(engine, rc, motions, comp)
    curves = _curve_motions(engine, rc, motions, vertices)
    delta = _probe_step(defining)
    if delta is not None:
        _probe(document, model, comp, rc, parameter, p0, delta, base_exact)
    return DesignVelocity(parameter, rc, defining, vertices, curves, delta)


def _check_parameter(document: dict, name: str) -> None:
    params = document["geometry"].get("parameters", {})
    if name not in params:
        raise GeometryError(f"design velocity: unknown parameter {name!r}")
    spec = params[name]
    kind = spec.get("kind", "length")
    if kind != "length":
        raise GeometryError(f"design velocity: geometry.parameters.{name} is a {kind}; the contract defines V = dx/dp "
                            "for length parameters")
    raw = spec["value"]
    if isinstance(raw, str) and any(k == "name" for k, _t in _tokens(raw, f"geometry.parameters.{name}.value")):
        raise GeometryError(f"design velocity: geometry.parameters.{name} is derived from other parameters "
                            f"({raw!r}); differentiate with respect to an independent parameter")


# ----------------------------------------------------------------------- motion of the feature boundaries

@dataclass
class _LineMotion:
    P: tuple
    Q: tuple
    VP: tuple
    VQ: tuple


@dataclass
class _CircleMotion:
    cx: int
    cy: int
    r2: int
    vc: tuple
    dr2: Fraction                       # d(r^2)/dp
    VP: tuple | None = None             # an arc's end velocities
    VQ: tuple | None = None


def _piece_motions(engine: _Engine, comp, V: dict) -> dict:
    """{id(piece): motion} for every boundary piece, in the order the engine added them."""
    base = f"geometry.components.{comp.name}"
    get = lambda path: V.get(path, ZERO)                                              # noqa: E731
    pt = lambda path: (get(f"{path}[0]"), get(f"{path}[1]"))                          # noqa: E731
    by_feature: dict[int, list] = {}
    for pc in engine.pieces:
        by_feature.setdefault(pc.feature, []).append(pc)
    out = {}
    Vx = engine.V

    def coord(v):
        return (Vx.x[v], Vx.y[v])

    def polyline(pieces, vel_points, closed):
        n = len(vel_points)
        for j, pc in enumerate(pieces):
            out[id(pc)] = _LineMotion(coord(pc.v0), coord(pc.v1), vel_points[j], vel_points[(j + 1) % n])

    dom = f"{base}.domain"
    dx0, dx1, dy0, dy1 = (get(f"{dom}.{k}") for k in ("xmin", "xmax", "ymin", "ymax"))
    polyline(by_feature[-1], [(dx0, dy0), (dx1, dy0), (dx1, dy1), (dx0, dy1)], True)
    for i, f in enumerate(comp.features):
        fp = f"{base}.features[{i}]"
        pieces = by_feature.get(i, [])
        if f.type == "rect":
            x, y, w, h = (get(f"{fp}.{k}") for k in ("x", "y", "w", "h"))
            polyline(pieces, [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], True)
        elif f.type == "trapezoid":
            cx, y, w, h = (get(f"{fp}.{k}") for k in ("cx", "y", "w", "h"))
            wt = get(f"{fp}.w_top") if f"{fp}.w_top" in V else w
            half = Fraction(1, 2)
            polyline(pieces, [(cx - w * half, y), (cx + w * half, y), (cx + wt * half, y + h), (cx - wt * half, y + h)],
                     True)
        elif f.type in ("polygon", "segment"):
            pts = [pt(f"{fp}.points[{j}]") for j in range(len(f.data["points"]))]
            polyline(pieces, pts, f.type == "polygon")
        elif f.type == "circle":
            (pc,) = pieces
            r = f.data["r"]
            out[id(pc)] = _CircleMotion(f.data["cx"], f.data["cy"], r * r, (get(f"{fp}.cx"), get(f"{fp}.cy")),
                                        2 * r * get(f"{fp}.r"))
        elif f.type == "path":
            _path_motions(f, fp, pieces, pt, coord, out)
    return out


def _path_motions(f, fp, pieces, pt, coord, out) -> None:
    cur_v, cur = pt(f"{fp}.start"), tuple(f.data["start"])
    it = iter(pieces)
    for k, s in enumerate(f.data["segments"]):
        sp = f"{fp}.segments[{k}]"
        pc = next(it)
        if "line" in s:
            to_v = pt(f"{sp}.line")
            out[id(pc)] = _LineMotion(coord(pc.v0), coord(pc.v1), cur_v, to_v)
            cur_v, cur = to_v, tuple(s["line"])
            continue
        a = s["arc"]
        cv, tv = pt(f"{sp}.arc.center"), pt(f"{sp}.arc.to")
        if any(c != 0 for c in (*cur_v, *cv, *tv)):
            raise GeometryError(f"design velocity: feature {f.name!r} segment {s.get('name') or f's{k + 1}'}: "
                                "the velocity of a moving path arc (its derived end point) is not defined in this "
                                "stage; only arcs whose start, centre and end stay fixed are taken")
        (cx, cy) = a["center"]
        r2 = (cur[0] - cx) ** 2 + (cur[1] - cy) ** 2
        out[id(pc)] = _CircleMotion(cx, cy, r2, (ZERO, ZERO), ZERO, cur_v, tv)
        cur_v, cur = tv, tuple(a["to"])
    for pc in it:                                    # the closing segment back to the start
        out[id(pc)] = _LineMotion(coord(pc.v0), coord(pc.v1), cur_v, pt(f"{fp}.start"))


# ----------------------------------------------------------------------- vertex velocities

def _qdiv(a: Q2, b: Q2) -> Q2:
    if b.D == 0:
        return a * (1 / b.a)
    n = b.a * b.a - b.b * b.b * b.D
    return a * Q2(b.a / n, -b.b / n, b.D)


def _fid(comp, pc) -> str:
    return "domain" if pc.feature < 0 else comp.features[pc.feature].id


def _vertex_velocities(engine: _Engine, rc: RegionComplex, motions: dict, comp) -> dict:
    used = sorted({v for k in rc.curves for v in (k.a, k.b)})
    supports = list(engine.lines.values()) + list(engine.circles.values())
    out = {}
    for v in used:
        x, y = engine.V.x[v], engine.V.y[v]
        points, rows = [], []
        for cu in supports:
            if v not in cu.points:
                continue
            for pc in cu.pieces:
                if not engine._on_piece(pc, x, y):
                    continue
                m = motions[id(pc)]
                if pc.v0 is not None and v in (pc.v0, pc.v1):
                    points.append((m.VP if v == pc.v0 else m.VQ, pc))
                    if isinstance(m, _CircleMotion):
                        rows.append((*_circle_row(m, x, y), pc, m))
                elif isinstance(m, _LineMotion):
                    rows.append((*_line_row(m, x, y), pc, m))
                else:
                    rows.append((*_circle_row(m, x, y), pc, m))
        out[v] = _solve(v, x, y, points, rows, comp)
    return out


def _line_row(m: _LineMotion, x: Q2, y: Q2):
    (Px, Py), (Qx, Qy) = m.P, m.Q
    ex, ey = Qx - Px, Qy - Py
    wx, wy = x - Px, y - Py
    dvx, dvy = m.VQ[0] - m.VP[0], m.VQ[1] - m.VP[1]
    gp = wy * dvx - wx * dvy + (ey * m.VP[0] - ex * m.VP[1])          # d/dp cross(Q - P, x - P), x fixed
    return (-ey, ex, -gp)                                               # n . V = -g_p, n = (-ey, ex)


def _circle_row(m: _CircleMotion, x: Q2, y: Q2):
    wx, wy = x - m.cx, y - m.cy
    return (wx * 2, wy * 2, (wx * m.vc[0] + wy * m.vc[1]) * 2 + m.dr2)


def _solve(v, x, y, points, rows, comp):
    where = f"({float(x):g}, {float(y):g}) pm"
    involved = [_fid(comp, pc) for _p, pc in points] + [_fid(comp, r[3]) for r in rows]
    if points:
        V = tuple(Q2(c) if not isinstance(c, Q2) else c for c in points[0][0])
        for P, pc in points[1:]:
            if not (V[0] == Q2(P[0]) and V[1] == Q2(P[1])):
                raise TopologyChange(f"design velocity: defining points that meet at {where} move apart", involved)
    else:
        V = None
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                det = a[0] * b[1] - a[1] * b[0]
                if not Q2._of(det).is_zero():
                    det = Q2._of(det)
                    V = (_qdiv(Q2._of(a[2] * b[1] - b[2] * a[1]), det), _qdiv(Q2._of(a[0] * b[2] - b[0] * a[2]), det))
                    break
            if V is not None:
                break
        if V is None:
            if rows and len({id(r[3].curve) for r in rows}) == 1 and rows[0][3].curve.kind == "circle":
                # a point that only splits a whole circle moves radially: V = vc + dr2 w / (2 r2)
                m, cu = rows[0][4], rows[0][3].curve
                wx, wy = x - cu.cx, y - cu.cy
                V = (Q2._of(wx * (m.dr2 / (2 * cu.r2))) + m.vc[0], Q2._of(wy * (m.dr2 / (2 * cu.r2))) + m.vc[1])
            else:
                raise TopologyChange(f"design velocity: a tangent or overlapping contact at {where} fixes the motion in "
                                     "one direction only", involved)
    for r in rows:
        resid = Q2._of(r[0] * V[0] + r[1] * V[1] - r[2])
        if not resid.is_zero():
            raise TopologyChange(f"design velocity: the curves through {where} do not move together, so the contact "
                                 "there changes", involved)
    return V


def _curve_motions(engine: _Engine, rc: RegionComplex, motions: dict, vertices: dict) -> dict:
    circ = {}
    for c in engine.circles.values():
        ms = [motions[id(pc)] for pc in c.pieces]
        circ[(c.cx, c.cy, c.r2)] = ms[0]
    out = {}
    for k in rc.curves:
        va, vb = vertices[k.a], vertices[k.b]
        if k.kind == "line":
            out[k.index] = CurveMotion("line", va, vb)
            continue
        (cx, cy), r2 = k.params["center"], k.params["r2"]
        m = circ[(cx, cy, r2)]
        dr = Q2(0, m.dr2 / (2 * r2), r2)                     # d(r^2)/(2r) = dr2 sqrt(r2) / (2 r2)
        out[k.index] = CurveMotion(k.kind, va, vb, m.vc, dr)
    return out


# ----------------------------------------------------------------------- the topology probe

def _probe_step(defining: dict):
    biggest = max((abs(d) for d in defining.values()), default=ZERO)
    if biggest == 0:
        return None
    e = math.ceil(math.log2(biggest)) if biggest > 1 else 0
    while Fraction(2) ** e < biggest:
        e += 1
    return PROBE_PM / Fraction(2) ** e


def signature(rc: RegionComplex):
    """The combinatorial signature of a complex: what the probe compares (no coordinates)."""
    def cell_key(ci):
        if ci is None:
            return ("exterior",)
        c = rc.cells[ci]
        return (c.region, c.feature, tuple(sorted(c.membership)), tuple(sorted(c.feature_indices)))

    incident: dict[int, list] = {}
    for k in rc.curves:
        for v in (k.a, k.b):
            incident.setdefault(v, []).append(tuple(sorted(k.provenance)))
    vkey = {v: tuple(sorted(ps)) for v, ps in incident.items()}
    curves = Counter((k.kind, tuple(sorted(k.provenance)), cell_key(k.left), cell_key(k.right), k.tag,
                      tuple(sorted((vkey[k.a], vkey[k.b])))) for k in rc.curves)
    cells = Counter((cell_key(c.index), tuple(len(lp) for lp in c.loops)) for c in rc.cells)
    sel = tuple(sorted((n, kind, len(ix)) for n, (kind, ix) in rc.selections.items()))
    return cells, curves, sel


def exact_complex(document: dict, parameter: str, offset, component: str | None = None):
    """The complex at ``parameter + offset`` (offset in the document unit, exact), unrounded.

    Each length field takes its base pm count (rounded once, as ``parse`` does) plus the exact
    change of its expression, on a grid ``S`` times finer than 1 pm so that every value is an
    integer. Returns ``(complex, S)``: the complex's coordinates are in pm / S. The probe and the
    finite-difference checks use it; nothing is rounded a second time."""
    model = parse(document)
    _check_parameter(document, parameter)
    p0 = model.parameters[parameter][0]
    base = _RecordingReader(document, _seeded(parameter, p0))
    _parse(base, document)
    base_exact = {path: Fraction(x) for path, x in base.exact.items()}
    return _exact_complex(document, model, _pick(model, component).name, parameter, p0, Fraction(offset), base_exact)


def _exact_complex(document, model, cname, parameter, p0, offset, base_exact):
    ppu = model.pm_per_unit
    k0 = {path: round(x * ppu) for path, x in base_exact.items()}
    rec = _RecordingReader(document, _seeded(parameter, p0 + offset), base=k0)
    _parse(rec, document)
    offsets = {path: (Fraction(rec.exact[path]) - base_exact[path]) * ppu for path in base_exact}
    S = math.lcm(1, *(o.denominator for o in offsets.values()))
    table = {path: S * k0[path] + int(S * o) for path, o in offsets.items()}
    comp = _pick(_parse(_TableReader(document, table), document), cname)
    return _Engine(comp).run(), S


def _probe(document, model: GeometryModel, comp, rc: RegionComplex, parameter: str, p0, delta_pm, base_exact) -> None:
    base_sig = signature(rc)
    step = delta_pm / model.pm_per_unit
    for s in (1, -1):
        where = f"{parameter} {'+' if s > 0 else '-'} delta"
        try:
            prc, _S = _exact_complex(document, model, comp.name, parameter, p0, s * step, base_exact)
        except GeometryError as exc:
            raise TopologyChange(f"design velocity: at {where} the component is refused ({exc})",
                                 _features_in(str(exc), comp)) from exc
        if signature(prc) != base_sig:
            raise TopologyChange(f"design velocity: the topology at {where} differs from the one at {parameter}",
                                 _changed_features(base_sig, signature(prc), comp))


def _changed_features(a, b, comp) -> list:
    diff = (a[1] - b[1]) + (b[1] - a[1])
    names = {p.split(".")[0] for key in diff for p in key[1]}
    cells = (a[0] - b[0]) + (b[0] - a[0])
    names |= {key[0][1] for key, _n in cells.items() if key[0][0] != "exterior"}
    return sorted(names) or [f.id for f in comp.features]


def _features_in(message: str, comp) -> list:
    found = [f.id for f in comp.features if repr(f.name) in message or f.id in message]
    return found or [f.id for f in comp.features]
