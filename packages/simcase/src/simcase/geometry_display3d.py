# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The display shape of a 3d component whose cylinders or spheres are in a meshloom builder shape.

``display_complex3d`` builds the exact complex of boxes and slab layers; a component with cylinders
or spheres is meshed by a meshloom builder (``geometry_builders3d``), whose exact complex of sampled
surfaces is not built. ``display_shapes3d`` gives such a component a display shape instead: faces
whose name sets are the mesh's provenance names (so a face picked in the display gives the names of
the mesh triangles it stands for), drawn by a display rule of their own, separate from the mesh
(adopted design, decision 2026-11-28-openphysics-studio-3d-e2-display, section 4.3):

- l = domain diagonal / 200;
- straight-edged planar faces are exact (two triangles per rectangle);
- a cylinder side is two rings of the inscribed n-gon, n = min(256, max(48, ceil(2 pi r / l)));
  the disc a via's end cuts from a domain face is a fan of the same n-gon, and the annulus left
  around it a strip between the n-gon and the rectangle, every vertex on the exact plane;
- a sphere is an icosahedral geodesic grid of frequency f = min(64, max(8, ceil(1.05 r / l))),
  every vertex on the sphere (radial projection);
- sections are exact: a cylinder cut by z gives the n-gon, cut by x or y two lines at
  +-sqrt(r^2 - d^2); a sphere cut at distance d < r gives a circle of rho = sqrt(r^2 - d^2), drawn
  with n from the same rule at rho.

Coordinates are float64 pm (on a plane, the axis coordinate is the face's integer pm coordinate,
exact below 2^53 pm, about 9 km). Areas (m^2) and volumes (m^3) are the exact surfaces' and bodies',
not the drawn ones. Curved faces have the outside as ``minus`` and the inside as ``plus``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .geometry_document import GeometryError, GeometryModel

PM = 10 ** 12
AXES = "xyz"
SEGMENTS = (48, 256)
FREQUENCY = (8, 64)
NOTE = "Shape drawn for display; the mesh follows it to within its size"
_SIDES = (("x", 0), ("x", 1), ("y", 0), ("y", 1), ("z", 0), ("z", 1))


@dataclass(frozen=True, eq=False)
class DisplayFace:
    """One face of a display shape (see the module's words for the rule that draws it)."""

    index: int
    shape: str                      # "plane", "cylinder" or "sphere"
    axis: int | None                # a plane's axis (0, 1, 2), else None
    coord: int | None               # a plane's coordinate (pm), else None
    names: tuple                    # the mesh's provenance names of the triangles it stands for, sorted
    tag: str | None                 # an exterior face's mesh tag: x0 ... z1, else "void"; None inside
    exterior: bool
    minus: tuple                    # region names on the side of smaller coordinate (curved: outside)
    plus: tuple                     # (curved: inside)
    area: float                     # m^2, the exact face's
    segments: int                   # n of a ring, f of a sphere; 0 for a rectangle
    vertices: np.ndarray = field(repr=False)        # (V, 3) float64 pm
    triangles: np.ndarray = field(repr=False)       # (T, 3) int64
    edges: np.ndarray = field(repr=False)           # (E, 2, 3) float64 pm: the face's outline
    _cut: tuple = field(repr=False, default=())     # what a section needs (exact pm)
    _extent: tuple = field(repr=False, default=())  # (lo, hi) pm per axis


@dataclass(frozen=True)
class DisplayRegion:
    name: str
    material: object                # a name, None for void, or the missing marker (homogeneous body)
    void: bool
    volume: float                   # m^3, the exact body's
    faces: tuple                    # ids of the faces it is on a side of


@dataclass(frozen=True, eq=False)
class Display3D:
    """``display_shapes3d``'s result: the component, its builder shape, its domain (pm), the display
    length l (pm), the faces and regions, and ``section(axis, at_pm)``."""

    component: str
    shape: str                      # the meshloom builder: via_in_slab, sphere_in_box, sphere, nested_spheres
    domain: dict                    # pm integers, xmin ... zmax
    length: float                   # l = diagonal / 200, pm
    faces: tuple
    regions: tuple
    note: str = NOTE

    def section(self, axis, at_pm: int) -> dict:
        """The outline where the plane ``axis = at_pm`` (``"x"``, ``"y"``, ``"z"`` or 0-2; pm) cuts the
        faces: ``{"segments": (S, 2, 3) float64 pm, "faces": (S,) face ids, "regions": the names of
        the non-void regions the plane meets}``. Raises ``GeometryError`` outside the domain."""
        a = AXES.index(axis) if isinstance(axis, str) else int(axis)
        lo, hi = self.domain[AXES[a] + "min"], self.domain[AXES[a] + "max"]
        if not lo <= at_pm <= hi:
            raise GeometryError(f"section {AXES[a]} = {at_pm} pm is outside the domain of {self.component!r} "
                                f"({lo} to {hi} pm)")
        segments, owner = [], []
        for f in self.faces:
            for seg in _section(f, a, at_pm, self.length):
                segments.append(seg)
                owner.append(f.index)
        void = {r.name for r in self.regions if r.void}
        met = {n for f in self.faces if f._extent[a][0] <= at_pm <= f._extent[a][1] for n in f.minus + f.plus}
        return {"segments": np.array(segments, dtype=np.float64).reshape(-1, 2, 3),
                "faces": np.array(owner, dtype=np.int64),
                "regions": [r.name for r in self.regions if r.name in met and r.name not in void]}


# ----------------------------------------------------------------------------- the rule

def ring_segments(r: float, length: float) -> int:
    """n = min(256, max(48, ceil(2 pi r / l)))."""
    return min(SEGMENTS[1], max(SEGMENTS[0], math.ceil(2 * math.pi * r / length)))


def sphere_frequency(r: float, length: float) -> int:
    """f = min(64, max(8, ceil(1.05 r / l)))."""
    return min(FREQUENCY[1], max(FREQUENCY[0], math.ceil(1.05 * r / length)))


def _ring(cu: float, cv: float, r: float, n: int) -> np.ndarray:
    """The inscribed n-gon's vertices (n, 2), angles 2 pi k / n from the +u direction."""
    t = 2 * math.pi * np.arange(n) / n
    return np.stack([cu + r * np.cos(t), cv + r * np.sin(t)], axis=1)


def _lift(uv: np.ndarray, axis: int, coord: float) -> np.ndarray:
    """2D points in a plane's (u, v) axes, u < v the other two, as 3D points on the plane."""
    ua, va = (i for i in range(3) if i != axis)
    out = np.empty((len(uv), 3), dtype=np.float64)
    out[:, axis] = float(coord)
    out[:, ua], out[:, va] = uv[:, 0], uv[:, 1]
    return out


def _loop_edges(points: np.ndarray) -> np.ndarray:
    return np.stack([points, np.roll(points, -1, axis=0)], axis=1)


def _rectangle(axis, coord, lo, hi):
    """lo, hi: (u0, v0), (u1, v1) pm."""
    uv = np.array([[lo[0], lo[1]], [hi[0], lo[1]], [hi[0], hi[1]], [lo[0], hi[1]]], dtype=np.float64)
    v = _lift(uv, axis, coord)
    return v, np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64), _loop_edges(v)


def _disc(axis, coord, centre, r, n):
    ring = _ring(centre[0], centre[1], r, n)
    v = _lift(np.vstack([np.array([centre], dtype=np.float64), ring]), axis, coord)
    k = np.arange(n)
    tris = np.stack([np.zeros(n, dtype=np.int64), 1 + k, 1 + (k + 1) % n], axis=1)
    return v, tris, _loop_edges(v[1:])


def _annulus(axis, coord, lo, hi, centre, r, n):
    """The rectangle lo-hi less the inscribed n-gon: per sector [theta_k, theta_k+1] the convex piece
    between the chord and the rectangle (the n-gon vertices' radial projections on the rectangle and
    the corners between them), fanned from the n-gon vertex p_k."""
    cu, cv = centre
    ring = _ring(cu, cv, r, n)
    t = 2 * math.pi * np.arange(n) / n
    d = np.stack([np.cos(t), np.sin(t)], axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        tu = np.where(d[:, 0] > 0, (hi[0] - cu) / d[:, 0], np.where(d[:, 0] < 0, (lo[0] - cu) / d[:, 0], np.inf))
        tv = np.where(d[:, 1] > 0, (hi[1] - cv) / d[:, 1], np.where(d[:, 1] < 0, (lo[1] - cv) / d[:, 1], np.inf))
    reach = np.minimum(tu, tv)
    outer = np.stack([cu + reach * d[:, 0], cv + reach * d[:, 1]], axis=1)
    # snap each projection onto the side it reached, so it lies on the rectangle exactly
    outer[:, 0] = np.where(tu <= tv, np.where(d[:, 0] > 0, hi[0], lo[0]), outer[:, 0])
    outer[:, 1] = np.where(tv < tu, np.where(d[:, 1] > 0, hi[1], lo[1]), outer[:, 1])
    corners = [(hi[0], hi[1]), (lo[0], hi[1]), (lo[0], lo[1]), (hi[0], lo[1])]
    tol = 1e-9 * max(hi[0] - lo[0], hi[1] - lo[1])
    in_sector: dict = {}
    for cu_, cv_ in corners:
        ang = math.atan2(cv_ - cv, cu_ - cu) % (2 * math.pi)
        k = int(ang // (2 * math.pi / n)) % n
        near = min(np.hypot(outer[k, 0] - cu_, outer[k, 1] - cv_),
                   np.hypot(outer[(k + 1) % n, 0] - cu_, outer[(k + 1) % n, 1] - cv_))
        if near > tol:
            in_sector.setdefault(k, []).append((ang, (cu_, cv_)))
    points = [tuple(p) for p in ring] + [tuple(p) for p in outer]
    tris = []
    for k in range(n):
        j = (k + 1) % n
        chain = [n + k] + [len(points) + i for i in range(len(in_sector.get(k, [])))] + [n + j]
        points += [c for _, c in sorted(in_sector.get(k, []))]
        for a, b in zip(chain, chain[1:]):
            tris.append((k, a, b))
        tris.append((k, n + j, j))
    v = _lift(np.array(points, dtype=np.float64), axis, coord)
    rect = _lift(np.array([[lo[0], lo[1]], [hi[0], lo[1]], [hi[0], hi[1]], [lo[0], hi[1]]], dtype=np.float64),
                 axis, coord)
    return v, np.array(tris, dtype=np.int64), np.concatenate([_loop_edges(v[:n]), _loop_edges(rect)])


def _cylinder_side(cx, cy, r, z0, z1, n):
    ring = _ring(cx, cy, r, n)
    v = np.vstack([np.column_stack([ring, np.full(n, float(z0))]), np.column_stack([ring, np.full(n, float(z1))])])
    k = np.arange(n)
    j = (k + 1) % n
    tris = np.concatenate([np.stack([k, j, n + j], axis=1), np.stack([k, n + j, n + k], axis=1)]).astype(np.int64)
    return v, tris, np.concatenate([_loop_edges(v[:n]), _loop_edges(v[n:])])


def _icosahedron():
    phi = (1 + math.sqrt(5)) / 2
    pts = []
    for a in (-1, 1):
        for b in (-phi, phi):
            pts += [(0, a, b), (a, b, 0), (b, 0, a)]
    pts = np.array(sorted(pts), dtype=np.float64)
    faces = []
    for i in range(12):
        for j in range(i + 1, 12):
            for k in range(j + 1, 12):
                if all(abs(np.linalg.norm(pts[p] - pts[q]) - 2) < 1e-9 for p, q in ((i, j), (j, k), (i, k))):
                    if np.dot(np.cross(pts[j] - pts[i], pts[k] - pts[i]), pts[i] + pts[j] + pts[k]) < 0:
                        j_, k_ = k, j
                    else:
                        j_, k_ = j, k
                    faces.append((i, j_, k_))
    return pts, faces


def _sphere(centre, r, f):
    """The icosahedral geodesic grid of frequency f: 10 f^2 + 2 vertices, 20 f^2 triangles, each vertex
    c + r v / |v| for v the grid point on the icosahedron's face."""
    pts, faces = _icosahedron()
    index: dict = {}
    raw = []

    def vertex(face, i, j):
        a, b, c = face
        w = {a: f - i - j, b: i, c: j}
        key = tuple(sorted((p, q) for p, q in w.items() if q))
        if key not in index:
            index[key] = len(raw)
            raw.append(sum(q * pts[p] for p, q in key) / f)
        return index[key]
    tris = []
    for face in faces:
        for i in range(f):
            for j in range(f - i):
                tris.append((vertex(face, i, j), vertex(face, i + 1, j), vertex(face, i, j + 1)))
                if j < f - i - 1:
                    tris.append((vertex(face, i + 1, j), vertex(face, i + 1, j + 1), vertex(face, i, j + 1)))
    raw = np.array(raw, dtype=np.float64)
    v = np.asarray(centre, dtype=np.float64) + r * raw / np.linalg.norm(raw, axis=1)[:, None]
    return v, np.array(tris, dtype=np.int64), np.zeros((0, 2, 3), dtype=np.float64)


# ----------------------------------------------------------------------------- sections

def _section(face: DisplayFace, a: int, at: int, length: float) -> list:
    kind = face._cut[0]
    if kind == "sphere":
        _, c, r = face._cut
        d = at - c[a]
        if abs(d) >= r:
            return []
        rho = math.sqrt(r * r - d * d)
        ua, va = (i for i in range(3) if i != a)
        ring = _lift(_ring(c[ua], c[va], rho, ring_segments(rho, length)), a, at)
        return list(_loop_edges(ring))
    if kind == "cylinder":
        _, cx, cy, r, z0, z1, n = face._cut
        if a == 2:
            if not z0 <= at <= z1:
                return []
            ring = _ring(cx, cy, r, n)
            return list(_loop_edges(np.column_stack([ring, np.full(n, float(at))])))
        c, other = (cx, cy) if a == 0 else (cy, cx)
        d = at - c
        if abs(d) > r:
            return []
        half = math.sqrt(r * r - d * d)
        out = []
        for w in sorted({other - half, other + half}):
            p, q = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
            p[a] = q[a] = float(at)
            p[1 - a] = q[1 - a] = w
            p[2], q[2] = float(z0), float(z1)
            out.append([p, q])
        return out
    # a plane: a rectangle, a disc or an annulus
    _, axis, coord, lo, hi, circle = face._cut
    if axis == a:
        return []
    ua, va = (i for i in range(3) if i != axis)
    along = va if ua == a else ua
    k_at, k_along = (0, 1) if ua == a else (1, 0)
    if not lo[k_at] <= at <= hi[k_at]:
        return []
    spans = [(float(lo[k_along]), float(hi[k_along]))]
    if circle is not None:
        kind_c, centre, r = circle
        d = at - centre[k_at]
        chord = None
        if abs(d) < r:
            half = math.sqrt(r * r - d * d)
            chord = (centre[k_along] - half, centre[k_along] + half)
        if kind_c == "disc":
            spans = [chord] if chord else []
        elif chord:
            spans = [(spans[0][0], chord[0]), (chord[1], spans[0][1])]
    out = []
    for s0, s1 in spans:
        p, q = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
        p[axis] = q[axis] = float(coord)
        p[a] = q[a] = float(at)
        p[along], q[along] = s0, s1
        out.append([p, q])
    return out


# ----------------------------------------------------------------------------- the faces of each shape

class _Faces:
    def __init__(self, comp, length):
        self.comp, self.length, self.faces = comp, length, []
        self.dom = comp.domain

    def add(self, shape, names, minus, plus, area, segments, mesh, cut, extent):
        exterior = not minus or not plus or any(self.void(n) for n in minus + plus)
        tag = None
        if exterior:
            tag = next((n.split(".", 1)[1] for n in sorted(names) if n.startswith("domain.")), "void")
        axis = cut[1] if cut[0] == "plane" else None
        coord = cut[2] if cut[0] == "plane" else None
        v, t, e = mesh
        self.faces.append(DisplayFace(len(self.faces), shape, axis, coord, tuple(sorted(names)), tag, exterior,
                                      tuple(minus), tuple(plus), area, segments, v, t, e, cut, extent))

    def void(self, region):
        return region in self.voids

    def box_extent(self):
        return tuple((self.dom[k + "min"], self.dom[k + "max"]) for k in AXES)

    def domain_sides(self, slab: str, circle=None, end_names=None):
        """The six domain faces (four with a circle cut from the z faces: their annulus and disc)."""
        dom, box = self.dom, self.box_extent()
        for k, (axis, end) in enumerate(_SIDES):
            a = AXES.index(axis)
            coord = dom[axis + ("max" if end else "min")]
            ua, va = (i for i in range(3) if i != a)
            lo = (dom[AXES[ua] + "min"], dom[AXES[va] + "min"])
            hi = (dom[AXES[ua] + "max"], dom[AXES[va] + "max"])
            area_m = (hi[0] - lo[0]) / PM * ((hi[1] - lo[1]) / PM)
            inside, outside = (slab,), ()
            minus, plus = (outside, inside) if end == 0 else (inside, outside)
            extent = tuple((coord, coord) if i == a else box[i] for i in range(3))
            name = f"domain.{axis}{end}"
            if axis == "z" and circle is not None:
                (cx, cy, r, via), n = circle, ring_segments(circle[2], self.length)
                rm = r / PM
                disc_area = math.pi * rm * rm
                self.add("plane", [name], minus, plus, area_m - disc_area, n,
                         _annulus(a, coord, lo, hi, (cx, cy), r, n),
                         ("plane", a, coord, lo, hi, ("annulus", (cx, cy), r)), extent)
                vminus, vplus = ((), (via,)) if end == 0 else ((via,), ())
                dext = ((cx - r, cx + r), (cy - r, cy + r), (coord, coord))
                self.add("plane", [name, end_names[end]], vminus, vplus, disc_area, n,
                         _disc(a, coord, (cx, cy), r, n), ("plane", a, coord, lo, hi, ("disc", (cx, cy), r)), dext)
            else:
                self.add("plane", [name], minus, plus, area_m, 0, _rectangle(a, coord, lo, hi),
                         ("plane", a, coord, lo, hi, None), extent)

    def sphere(self, feature, minus, plus):
        d = feature.data
        c, r = (d["cx"], d["cy"], d["cz"]), d["r"]
        f = sphere_frequency(r, self.length)
        rm = r / PM
        self.add("sphere", [f"{feature.id}.surface"], minus, plus, 4 * math.pi * rm * rm, f, _sphere(c, r, f),
                 ("sphere", c, r), tuple((c[i] - r, c[i] + r) for i in range(3)))


def _pick(model: GeometryModel, component: str | None):
    """The component, picked and refused in ``display_complex3d``'s words."""
    comps = model.components
    if component is None:
        three = [n for n, c in comps.items() if c.dimension == "3d"]
        if len(three) != 1:
            raise GeometryError(f"name a 3d component: the model has {len(three)} ({three}); components "
                                f"{sorted(comps)}", path="geometry.components")
        component = three[0]
    if component not in comps:
        raise GeometryError(f"geometry.components.{component}: no component {component!r}; the model has "
                            f"{sorted(comps)}", path=f"geometry.components.{component}")
    comp = comps[component]
    if comp.dimension != "3d":
        raise GeometryError(f"geometry.components.{component}: component {component!r} is {comp.dimension}; "
                            "display_shapes3d takes a 3d component (2d and axisymmetric components go through "
                            "simcase.evaluate_geometry)", path=f"geometry.components.{component}.dimension")
    return comp


def display_shapes3d(model: GeometryModel, component: str | None = None) -> Display3D:
    """The display shape of a ``3d`` component whose cylinders or spheres are in a meshloom builder shape
    (C4 ``via_in_slab``, C5 ``sphere_in_box``, C1 ``sphere``, C11 ``nested_spheres``; experimental).

    ``model`` is what ``simcase.parse_geometry`` returns; ``component`` is picked as
    ``display_complex3d`` picks it. What no builder takes is refused in
    ``geometry_builders3d.recognise``'s own words (``E-3D-COMBINATION``, naming the feature); a
    component with no cylinder or sphere is refused by name (``E-CONTRACT``): ``display_complex3d``
    draws it. It meshes nothing and changes nothing ``build_mesh3d`` does or refuses."""
    from . import geometry_builders3d as builders

    comp = _pick(model, component)
    if not builders.has_curved(comp):
        raise GeometryError(f"component {comp.name!r} holds no cylinder or sphere: display_shapes3d draws cylinders "
                            "and spheres in meshloom's builder shapes; simcase.display_complex3d draws boxes and "
                            "slab layers", path=f"geometry.components.{comp.name}", code="E-CONTRACT")
    shape, curved = builders.recognise(comp)
    dom, feats = comp.domain, comp.features
    span = [(dom[k + "max"] - dom[k + "min"]) / PM for k in AXES]
    box_m3 = span[0] * span[1] * span[2]
    diag = math.sqrt(sum((dom[k + "max"] - dom[k + "min"]) ** 2 for k in AXES))
    length = diag / 200
    out = _Faces(comp, length)
    bg = comp.background.get("material")
    regions = []                                   # (name, material, volume m^3), features first
    if shape == "via_in_slab":
        f = feats[curved[0]]
        d = f.data
        rm, lm = d["r"] / PM, (d["zmax"] - d["zmin"]) / PM
        v = math.pi * rm * rm * lm
        regions = [(f.region, f.material, v), ("background", bg, box_m3 - v)]
        out.voids = {n for n, m, _ in regions if m is None}
        out.domain_sides("background", (d["cx"], d["cy"], d["r"], f.region), (f"{f.id}.bottom", f"{f.id}.top"))
        n = ring_segments(d["r"], length)
        out.add("cylinder", [f"{f.id}.side"], ("background",), (f.region,), 2 * math.pi * rm * lm, n,
                _cylinder_side(d["cx"], d["cy"], d["r"], d["zmin"], d["zmax"], n),
                ("cylinder", d["cx"], d["cy"], d["r"], d["zmin"], d["zmax"], n),
                ((d["cx"] - d["r"], d["cx"] + d["r"]), (d["cy"] - d["r"], d["cy"] + d["r"]), (d["zmin"], d["zmax"])))
    elif shape in ("sphere_in_box", "sphere"):
        f = feats[curved[0]]
        rm = f.data["r"] / PM
        v = 4 * math.pi / 3 * rm ** 3
        regions = [(f.region, f.material, v), ("background", bg, box_m3 - v)]
        out.voids = {n for n, m, _ in regions if m is None}
        if shape == "sphere_in_box":
            out.domain_sides("background")
        out.sphere(f, ("background",), (f.region,))
    else:                                           # nested: outermost first, later wins
        radii = [feats[i].data["r"] / PM for i in curved] + [0.0]
        for k, i in enumerate(curved):
            regions.append((feats[i].region, feats[i].material, 4 * math.pi / 3 * (radii[k] ** 3 - radii[k + 1] ** 3)))
        regions.append(("background", bg, box_m3 - 4 * math.pi / 3 * radii[0] ** 3))
        out.voids = {n for n, m, _ in regions if m is None}
        for k, i in enumerate(curved):
            outside = "background" if k == 0 else feats[curved[k - 1]].region
            out.sphere(feats[i], (outside,), (feats[i].region,))
    faces = tuple(out.faces)
    shown = []
    for name, material, volume in regions:
        on = tuple(f.index for f in faces if name in f.minus or name in f.plus)
        shown.append(DisplayRegion(name, material, material is None, volume, on))
    return Display3D(comp.name, shape, dict(dom), length, faces, tuple(shown))
