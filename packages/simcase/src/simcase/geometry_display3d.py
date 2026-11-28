# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The display of a ``3d`` component with cylinders or spheres in one of meshloom's builder shapes
(``display_shapes3d``; experimental).

``display_complex3d`` draws boxes and slab layers from their exact complex; a component holding a
cylinder or a sphere has no exact complex yet (``geometry_engine3d`` refuses it), so it is drawn here
from the shapes themselves, by a display rule that is not the mesh:

- l = the domain's diagonal / 200;
- a planar face with straight edges is drawn exactly (two triangles per rectangle);
- a circle (a via's cap, the hole it leaves in a domain face, a section) is its inscribed n-gon,
  n = min(256, max(48, ceil(2 pi r / l))); a disc is a fan from its centre and an annulus the strip
  between the n-gon and the rectangle, with every vertex exactly on the face's plane;
- a cylinder side is the prism of that n-gon (two rings: the side is straight);
- a sphere is an icosahedral geodesic grid of frequency f = min(64, max(8, ceil(1.05 r / l))),
  20 f^2 triangles with every vertex on the sphere.

The faces are the mesh's surfaces, named as the mesh names them (``geometry_builders3d``): the domain
faces ``domain.x0`` ... ``domain.z1`` (a via's cap also ``<via>.bottom`` / ``<via>.top``), the side
``<via>.side`` and each sphere's ``<id>.surface``; their tags are the mesh's, ``x0`` ... ``z1``, and
``void`` on the other exterior faces. Coordinates are pm (floats; on a planar face the axis
coordinate is the face's exact integer), areas m^2 and volumes m^3 from the exact formulas.
``section(axis, at)`` gives the exact outline where the plane ``axis = at`` (pm) cuts the faces,
drawn by the same rule: segments of the planar faces, an n-gon or two lines of a cylinder, a circle of
a sphere.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .geometry_document import GeometryError, GeometryModel, _pick

__all__ = ["Display3D", "DisplayFace3D", "DisplayRegion3D", "DisplaySegment3D", "display_shapes3d",
           "DISPLAY_NOTE", "has_shapes"]

DISPLAY_NOTE = "Shape drawn for display; the mesh follows it to within its size"
AXES = "xyz"
PM = 10 ** 12


@dataclass
class DisplayFace3D:
    index: int
    shape: str                      # "plane", "cylinder" or "sphere"
    kind: str                       # "rectangle", "disc", "annulus", "cylinder" or "sphere"
    names: tuple                    # the mesh's provenance names, sorted
    tag: str | None
    exterior: bool
    minus: list                     # regions on the face's minus side (planes) or inside (cylinder, sphere)
    plus: list                      # regions on the plus side (planes) or outside
    area: float                     # exact, m^2
    vertices: np.ndarray            # (V, 3) float64 pm
    triangles: np.ndarray           # (T, 3) int64
    segments: int | None = None     # n of a circle or a cylinder, f of a sphere
    axis: int | None = None         # planes: the normal axis
    coord: int | None = None        # planes: the exact pm coordinate
    circle: tuple | None = None     # discs and annuli: ((u, v) centre in pm, r in pm)
    radius: int | None = None       # cylinders and spheres, pm
    centre: np.ndarray | None = None
    edges: list = field(default_factory=list)     # polylines, (k, 3) pm, closed when the first equals the last


@dataclass
class DisplayRegion3D:
    name: str
    material: object
    void: bool
    volume: float                   # exact, m^3
    faces: list


@dataclass(frozen=True)
class DisplaySegment3D:
    p: tuple
    q: tuple
    face: int


@dataclass
class Display3D:
    component: str
    shape: str                      # the builder shape
    domain: dict                    # pm
    ell: float                      # pm
    faces: list
    regions: list
    length_unit: str
    pm_per_unit: object
    note: str = DISPLAY_NOTE
    _cuts: list = field(default_factory=list, repr=False)    # how each face is cut, for section()

    def section(self, axis: str, at: int) -> list:
        """The exact outline where the plane ``axis = at`` (pm) cuts the faces, as segments."""
        a = AXES.index(axis)
        out = []
        for face, cut in zip(self.faces, self._cuts):
            out += [DisplaySegment3D(tuple(p), tuple(q), face.index) for p, q in cut(a, at, self.ell)]
        return out

    def section_regions(self, axis: str, at: int) -> list:
        """The regions the plane ``axis = at`` (pm) passes through, sorted."""
        a = AXES.index(axis)
        return sorted(r.name for r in self.regions if self._region_cut[r.name](a, at))


def has_shapes(comp) -> bool:
    """Whether a component holds a cylinder or a sphere (drawn here, not from the exact complex)."""
    from . import geometry_builders3d as builders
    return comp.dimension == "3d" and builders.has_curved(comp)


def n_circle(r: float, ell: float) -> int:
    return min(256, max(48, math.ceil(2 * math.pi * r / ell)))


def f_sphere(r: float, ell: float) -> int:
    return min(64, max(8, math.ceil(1.05 * r / ell)))


# ----------------------------------------------------------------------------- the pieces

def _point(axis, coord, u, v):
    ua, va = (i for i in range(3) if i != axis)
    p = [0.0, 0.0, 0.0]
    p[axis], p[ua], p[va] = coord, u, v
    return p


def _ring(c, r, n):
    """The inscribed n-gon of the circle (centre c = (u, v), radius r), counter-clockwise from angle 0."""
    t = 2 * math.pi * np.arange(n) / n
    return np.column_stack([c[0] + r * np.cos(t), c[1] + r * np.sin(t)])


def _rectangle(axis, coord, u0, u1, v0, v1):
    vs = np.array([_point(axis, coord, u, v) for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))])
    return vs, np.array([[0, 1, 2], [0, 2, 3]])


def _disc(axis, coord, c, r, n):
    ring = _ring(c, r, n)
    vs = np.array([_point(axis, coord, c[0], c[1])] + [_point(axis, coord, u, v) for u, v in ring])
    k = np.arange(n)
    return vs, np.column_stack([np.zeros(n, dtype=int), 1 + k, 1 + (k + 1) % n])


def _annulus(axis, coord, rect, c, r, n):
    """The rectangle (u0, u1, v0, v1) minus the n-gon: per sector between the rays through two
    consecutive n-gon vertices, the convex polygon of the two inner vertices, the rays' hits on the
    rectangle and the corners between them, fanned from an inner vertex."""
    u0, u1, v0, v1 = rect
    ring = _ring(c, r, n)

    def hit(t):                                     # where the ray from c at angle t leaves the rectangle
        du, dv = math.cos(t), math.sin(t)
        s = min([(u1 - c[0]) / du] if du > 0 else [(u0 - c[0]) / du] if du < 0 else [math.inf])
        s = min(s, min([(v1 - c[1]) / dv] if dv > 0 else [(v0 - c[1]) / dv] if dv < 0 else [math.inf]))
        return (c[0] + s * du, c[1] + s * dv)
    corners = [(u1, v1), (u0, v1), (u0, v0), (u1, v0)]
    angle = [math.atan2(q[1] - c[1], q[0] - c[0]) % (2 * math.pi) for q in corners]
    pts2, tris = [], []

    def add(q):
        pts2.append(q)
        return len(pts2) - 1
    inner = [add(tuple(q)) for q in ring]
    outer = [add(hit(2 * math.pi * k / n)) for k in range(n)]
    corner_ids = [add(q) for q in corners]
    for k in range(n):
        t0, t1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        between = sorted((a, i) for i, a in enumerate(angle) if t0 < a < t1 or (k == n - 1 and t0 < a))
        chain = [outer[k]] + [corner_ids[i] for _, i in between] + [outer[(k + 1) % n]]
        a = inner[k]
        for p, q in zip(chain, chain[1:]):
            tris.append([a, p, q])
        tris.append([a, outer[(k + 1) % n], inner[(k + 1) % n]])
    vs = np.array([_point(axis, coord, u, v) for u, v in pts2])
    return vs, np.array(tris)


def _side(c, r, z0, z1, n):
    ring = _ring(c, r, n)
    vs = np.array([[u, v, z0] for u, v in ring] + [[u, v, z1] for u, v in ring])
    k = np.arange(n)
    k1 = (k + 1) % n
    tris = np.concatenate([np.column_stack([k, k1, n + k1]), np.column_stack([k, n + k1, n + k])])
    return vs, tris


_PHI = (1 + 5 ** 0.5) / 2
_ICO_V = np.array([[-1, _PHI, 0], [1, _PHI, 0], [-1, -_PHI, 0], [1, -_PHI, 0], [0, -1, _PHI], [0, 1, _PHI],
                   [0, -1, -_PHI], [0, 1, -_PHI], [_PHI, 0, -1], [_PHI, 0, 1], [-_PHI, 0, -1], [-_PHI, 0, 1]],
                  dtype=float)
_ICO_F = np.array([[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11], [1, 5, 9], [5, 11, 4],
                   [11, 10, 2], [10, 7, 6], [7, 1, 8], [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
                   [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1]])


def _sphere(centre, r, f):
    """The geodesic grid: each icosahedron face split into f^2 triangles, every vertex projected
    onto the sphere."""
    vs, tris = [], []
    for a, b, c in _ICO_V[_ICO_F]:
        index = {}
        for i in range(f + 1):
            for j in range(f + 1 - i):
                p = (a * (f - i - j) + b * i + c * j) / f
                index[(i, j)] = len(vs)
                vs.append(centre + r * p / np.linalg.norm(p))
        for i in range(f):
            for j in range(f - i):
                tris.append([index[(i, j)], index[(i + 1, j)], index[(i, j + 1)]])
                if i + j < f - 1:
                    tris.append([index[(i + 1, j)], index[(i + 1, j + 1)], index[(i, j + 1)]])
    return np.array(vs), np.array(tris)


# ----------------------------------------------------------------------------- the cuts

def _no_cut(a, at, ell):
    return []


def _plane_cut(axis, coord, rect, circle, kind):
    """The cut of a planar face (a rectangle, a disc or a rectangle with a disc removed) by
    ``x_a = at``: the exact chord(s) along the face's other in-plane axis."""
    ua, va = (i for i in range(3) if i != axis)

    def cut(a, at, ell):
        if a == axis:
            return []
        other = va if a == ua else ua
        lo_a, hi_a = (rect[0], rect[1]) if a == ua else (rect[2], rect[3])
        lo_o, hi_o = (rect[2], rect[3]) if a == ua else (rect[0], rect[1])
        if circle is not None:
            (cu, cv), r = circle
            ca, co = (cu, cv) if a == ua else (cv, cu)
            d = at - ca
            half = math.sqrt(r * r - d * d) if abs(d) < r else None
        else:
            half = None
        if kind == "disc":
            if half is None:
                return []
            spans = [(co - half, co + half)]
        else:
            if not lo_a <= at <= hi_a:
                return []
            spans = [(lo_o, hi_o)] if half is None else [(lo_o, co - half), (co + half, hi_o)]

        def p(s):
            q = [0.0, 0.0, 0.0]
            q[axis], q[a], q[other] = coord, at, s
            return q
        return [(p(s0), p(s1)) for s0, s1 in spans if s1 > s0]
    return cut


def _cylinder_cut(c, r, z0, z1):
    def cut(a, at, ell):
        if a == 2:
            if not z0 <= at <= z1:
                return []
            ring = _ring(c, r, n_circle(r, ell))
            return [([*ring[k], at], [*ring[(k + 1) % len(ring)], at]) for k in range(len(ring))]
        ca, co = (c[0], c[1]) if a == 0 else (c[1], c[0])
        d = at - ca
        if abs(d) > r:
            return []
        half = math.sqrt(max(r * r - d * d, 0.0))
        out = []
        for s in ([co - half, co + half] if half > 0 else [co]):
            p, q = [0.0, 0.0, z0], [0.0, 0.0, z1]
            p[a] = q[a] = at
            p[1 - a] = q[1 - a] = s
            out.append((p, q))
        return out
    return cut


def _sphere_cut(centre, r):
    def cut(a, at, ell):
        d = at - centre[a]
        if abs(d) >= r:
            return []
        rho = math.sqrt(r * r - d * d)
        ua, va = (i for i in range(3) if i != a)
        ring = _ring((centre[ua], centre[va]), rho, n_circle(rho, ell))
        return [(_point(a, at, *ring[k]), _point(a, at, *ring[(k + 1) % len(ring)])) for k in range(len(ring))]
    return cut


# ----------------------------------------------------------------------------- the display

def display_shapes3d(model: GeometryModel, component: str | None = None) -> Display3D:
    """The display of a ``3d`` component with cylinders or spheres in a builder shape (see the module).
    ``model`` is ``simcase.parse_geometry``'s; ``component`` may be left out when the model has one
    ``3d`` component. What no builder takes is refused in slice 3's words (``E-3D-COMBINATION``); a
    component without cylinders or spheres is refused by name (``display_complex3d`` draws it)."""
    from . import geometry_builders3d as builders
    if component is None:
        three = [n for n, c in model.components.items() if c.dimension == "3d"]
        if len(three) != 1:
            raise GeometryError(f"name a 3d component: the model has {len(three)} ({three})",
                                path="geometry.components")
        component = three[0]
    comp = _pick(model, component)
    if not has_shapes(comp):
        raise GeometryError(f"component {comp.name!r} holds no cylinder or sphere; simcase.display_complex3d draws "
                            "boxes and slab layers", path=f"geometry.components.{comp.name}", code="E-CONTRACT")
    shape, curved = builders.recognise(comp)
    dom = comp.domain
    lo = [dom[f"{a}min"] for a in AXES]
    hi = [dom[f"{a}max"] for a in AXES]
    ell = math.dist(lo, hi) / 200
    m = lambda k: float(k) / PM                                        # noqa: E731
    bg = comp.background.get("material")
    feats = comp.features
    faces, cuts = [], []
    region_cut = {}

    def face(**kw):
        cut = kw.pop("cut", _no_cut)
        f = DisplayFace3D(index=len(faces), **kw)
        f.triangles = np.asarray(f.triangles, dtype=np.int64)
        f.vertices = np.asarray(f.vertices, dtype=np.float64)
        faces.append(f)
        cuts.append(cut)
        return f

    def box_sides(skip_z=False, inside=("background",)):
        inside = [r for r in inside if r]
        for a in range(3):
            if skip_z and a == 2:
                continue
            ua, va = (i for i in range(3) if i != a)
            rect = (lo[ua], hi[ua], lo[va], hi[va])
            for end, coord in ((0, lo[a]), (1, hi[a])):
                tag = f"{AXES[a]}{end}"
                vs, tris = _rectangle(a, coord, *rect)
                face(shape="plane", kind="rectangle", names=(f"domain.{tag}",), tag=tag, exterior=True,
                     minus=list(inside) if end else [], plus=[] if end else list(inside),
                     area=m(rect[1] - rect[0]) * m(rect[3] - rect[2]), vertices=vs, triangles=tris, axis=a,
                     coord=coord, edges=[np.vstack([vs, vs[:1]])], cut=_plane_cut(a, coord, rect, None, "rectangle"))

    regions: dict = {}

    def region(name, material, volume, cut):
        if name is None:
            return
        regions[name] = DisplayRegion3D(name, material, material is None, volume, [])
        region_cut[name] = cut

    if shape == "via_in_slab":
        i = curved[0]
        f, d = feats[i], feats[i].data
        c, r = (d["cx"], d["cy"]), d["r"]
        via = f.region if f.material is not None else None
        n = n_circle(r, ell)
        box_sides(skip_z=True)
        rect = (lo[0], hi[0], lo[1], hi[1])
        a_rect = m(hi[0] - lo[0]) * m(hi[1] - lo[1])
        for end, coord in ((0, lo[2]), (1, hi[2])):
            tag = f"z{end}"
            vs, tris = _annulus(2, coord, rect, c, r, n)
            outline = [np.vstack([vs[:0]] + [np.array([_point(2, coord, *q) for q in _ring(c, r, n)])])]
            outline = [np.vstack([outline[0], outline[0][:1]])]
            ring_edge = outline[0]
            box = _rectangle(2, coord, *rect)[0]
            face(shape="plane", kind="annulus", names=(f"domain.{tag}",), tag=tag, exterior=True,
                 minus=["background"] if end else [], plus=[] if end else ["background"],
                 area=a_rect - math.pi * m(r) ** 2, vertices=vs, triangles=tris, segments=n, axis=2, coord=coord,
                 circle=(c, r), edges=[np.vstack([box, box[:1]]), ring_edge],
                 cut=_plane_cut(2, coord, rect, (c, r), "annulus"))
            if via is not None:
                cap = "top" if end else "bottom"
                vs, tris = _disc(2, coord, c, r, n)
                face(shape="plane", kind="disc", names=tuple(sorted((f"{f.id}.{cap}", f"domain.{tag}"))), tag=tag,
                     exterior=True, minus=[via] if end else [], plus=[] if end else [via],
                     area=math.pi * m(r) ** 2, vertices=vs, triangles=tris, segments=n, axis=2, coord=coord,
                     circle=(c, r), edges=[ring_edge], cut=_plane_cut(2, coord, rect, (c, r), "disc"))
        vs, tris = _side(c, r, lo[2], hi[2], n)
        ring = _ring(c, r, n)
        face(shape="cylinder", kind="cylinder", names=(f"{f.id}.side",), tag=None if via else "void",
             exterior=via is None, minus=[via] if via else [], plus=["background"],
             area=2 * math.pi * m(r) * m(hi[2] - lo[2]), vertices=vs, triangles=tris, segments=n, radius=r,
             centre=np.array([c[0], c[1], lo[2]], dtype=float),
             edges=[np.array([[u, v, z] for u, v in np.vstack([ring, ring[:1]])]) for z in (lo[2], hi[2])],
             cut=_cylinder_cut(c, r, lo[2], hi[2]))
        v_via = math.pi * m(r) ** 2 * m(hi[2] - lo[2])
        inside_via = lambda a, at: (abs(at - c[a]) < r) if a < 2 else lo[2] <= at <= hi[2]   # noqa: E731
        region("background", bg, m(hi[0] - lo[0]) * m(hi[1] - lo[1]) * m(hi[2] - lo[2]) - v_via,
               lambda a, at: lo[a] <= at <= hi[a])
        region(via, f.material, v_via, inside_via)
    else:
        centre = np.array([feats[curved[0]].data[f"c{a}"] for a in AXES], dtype=float)
        order = sorted(curved, key=lambda i: feats[i].data["r"])        # innermost first
        names = [feats[i].region if feats[i].material is not None else None for i in order]
        outside_bg = bg if shape == "sphere_in_box" else None
        if shape == "sphere_in_box":
            box_sides(inside=("background",))
        radii = [feats[i].data["r"] for i in order]
        for k, i in enumerate(order):
            f, r = feats[i], radii[k]
            inside = names[k]
            outside = names[k + 1] if k + 1 < len(order) else ("background" if outside_bg is not None else None)
            if inside is None and outside is None:
                continue
            fr = f_sphere(r, ell)
            vs, tris = _sphere(centre, r, fr)
            face(shape="sphere", kind="sphere", names=(f"{f.id}.surface",),
                 tag=None if (inside and outside) else "void", exterior=not (inside and outside),
                 minus=[inside] if inside else [], plus=[outside] if outside else [],
                 area=4 * math.pi * m(r) ** 2, vertices=vs, triangles=tris, segments=fr, radius=r, centre=centre,
                 cut=_sphere_cut(centre, r))
            r_in = radii[k - 1] if k > 0 else 0
            region(inside, f.material, 4 * math.pi / 3 * (m(r) ** 3 - m(r_in) ** 3),
                   lambda a, at, r=r, r_in=r_in: r_in < r and abs(at - centre[a]) < r)
        if shape == "sphere_in_box":
            r = radii[-1]
            region("background", bg, m(hi[0] - lo[0]) * m(hi[1] - lo[1]) * m(hi[2] - lo[2])
                   - 4 * math.pi / 3 * m(r) ** 3, lambda a, at: lo[a] <= at <= hi[a])
    for f in faces:
        for name in f.minus + f.plus:
            if name in regions:
                regions[name].faces.append(f.index)
    out = Display3D(comp.name, shape, dict(dom), ell, faces, list(regions.values()), str(comp.length_unit),
                    comp.pm_per_unit, _cuts=cuts)
    out._region_cut = region_cut
    return out
