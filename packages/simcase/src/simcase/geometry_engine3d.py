# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The 3D region complex of boxes, slab layers and extrudes, and its meshloom hand-off (stage 5,
slices 1 and 2).

This module implements the stage 5 compile conditions of the geometry document contract
(``docs/packages/simcase/geometry_document.md``) for the features slices 1 and 2 take: ``box``,
the slab layers of ``layers`` features (a layer with a material and no footprint, a box over
the domain's x-y extent between its exact z levels) and ``extrude`` of a rect, trapezoid or
polygon profile. Every one is a vertical prism. The footprints of all prisms go once through the
stage 2 exact 2D engine (``simcase.geometry_engine``) with every boundary kept, so each fine 2D
cell carries the exact set of prisms whose footprint contains it; cutting the component at every
distinct z level, the region of a fine cell in a slab is that of the last prism active there
(later wins), which is the slab's 2D later-wins arrangement. Horizontal faces lie where the
regions above and below differ, vertical faces where the regions on the two sides of a fine
curve differ; faces of equal sides and provenance are merged, except that a sloped side is one
quad per fine curve (split at every 2D vertex, so no point has to be put into a sloped edge
after rounding). Derived points (trapezoid corners, intersections of sloped edges) stay exact
rationals until the hand-off.

``build_mesh3d`` hands the complex to ``meshloom.generate3d`` (rule H1: metres, each pm value
rounded once) and returns the shared ``galerkin.Mesh3D`` with the contract's default tags
(``x0``-``z1`` on the domain faces, ``void`` elsewhere) or ``boundary_tags``, the new field
``provenance_faces`` and the resolved selections. The route is **experimental** until meshloom's
own acceptance. Everything else a ``3d`` component may hold is refused by name
(``E-3D-COMBINATION``); a component holding one ``layers`` feature keeps the ``meshine.extrude``
route (``geometry_document.layer_stack``).

The complex is built with the standard library and exact rationals only; NumPy is used for the
mesh arrays after meshing.
"""

from __future__ import annotations

import bisect
import math
import re
from dataclasses import dataclass, field
from fractions import Fraction

from .geometry_document import (_MISSING, PM_PER_M, Component, Feature, GeometryError, GeometryModel, _keys,
                                _pick, _Reader, parse)

__all__ = ["Complex3D", "Cell3D", "Face3D", "Mesh3DResult", "Mesh3DError", "evaluate3d", "display_complex3d",
           "build_mesh3d",
           "SIDE_TAGS", "VOID_TAG", "TETRAHEDRA_PER_VOLUME", "DEFAULT_ELEMENT_COUNT_LIMIT"]

#: the default tags of the domain faces (contract: default tags, 3D through meshloom)
SIDE_TAGS = ("x0", "x1", "y0", "y1", "z0", "z1")
#: the default tag of every other exterior face
VOID_TAG = "void"
#: tetrahedra per h^3 of volume in the estimate T = 6.3 * sum(V_r / h_r^3)
TETRAHEDRA_PER_VOLUME = 6.3
#: ``mesh.element_count_limit`` when the document gives none (the 2D estimate's default)
DEFAULT_ELEMENT_COUNT_LIMIT = 600000
CODE = "E-3D-COMBINATION"
#: ``Face3D.axis`` of a vertical face that is not axis-aligned (a sloped extrude side)
SLOPED = 3

# rect parts of the 2D engine -> box parts (the engine names a rect's sides bottom, right, top, left)
_RECT_PART = {"bottom": "y0", "right": "x1", "top": "y1", "left": "x0"}
# the 2D engine's part names of an extrude's profile -> the extrude's side names (contract A4: a rect or
# trapezoid's bottom and top become y0 and y1; a polygon keeps its edge names)
_PROFILE_PARTS = {"rect": {"bottom": "y0", "right": "right", "top": "y1", "left": "left"},
                  "trapezoid": {"bottom": "y0", "right": "right", "top": "y1", "left": "left"},
                  "polygon": None}
#: what a 3d component takes on the meshloom route (stage 5, slice 2)
_TAKEN = "boxes, slab layers and rect, trapezoid and polygon extrudes are"


class Mesh3DError(GeometryError):
    """meshloom could not mesh the complex. ``cause`` is meshloom's error, ``facets`` the
    hand-off facets it names and ``provenance`` their provenance names."""

    def __init__(self, message, *, cause=None, facets=(), provenance=()):
        super().__init__(message)
        self.cause = cause
        self.facets = tuple(facets)
        self.provenance = tuple(provenance)


def _refuse(message: str, path: str, code: str = CODE):
    raise GeometryError(message, path=path, code=code)


# ----------------------------------------------------------------------------- prisms

@dataclass(frozen=True)
class _Prism:
    feature_index: int
    feature_id: str
    prefix: str                     # provenance prefix: the box id, or "<id>.<layer>"
    kind: str                       # "box", "slab" or "extrude"
    region: str
    material: object                # a name, or None for void
    mesh_size: int | None
    bounds: tuple                   # (x0, x1, y0, y1, z0, z1) in pm, as written (an extrude: its profile's box)
    profile: object = None          # an extrude's profile: (type, data without "type", part names edge by edge)

    def part(self, name: str) -> str:
        if self.kind == "box":
            return f"{self.prefix}.{name}"
        if self.kind == "extrude":
            if name in ("z0", "z1"):
                return f"{self.prefix}.{'bottom' if name == 'z0' else 'top'}"
            return f"{self.prefix}.{name}"
        if name in ("z0", "z1"):
            return f"{self.prefix}.{'bottom' if name == 'z0' else 'top'}"
        return f"{self.prefix}.domain.{name}"


def _feature_path(comp: Component, i: int) -> str:
    return f"geometry.components.{comp.name}.features[{i}]"


def _prisms(comp: Component, *, lone_layers: bool) -> list[_Prism]:
    dom = comp.domain
    out = []
    for i, f in enumerate(comp.features):
        path = _feature_path(comp, i)
        if f.type == "box":
            d = f.data
            out.append(_Prism(i, f.id, f.id, "box", f.region, f.material, f.mesh_size,
                              tuple(d[k] for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"))))
        elif f.type == "layers":
            layers = f.data["layers"]
            if any("footprint" in lay for lay in layers):
                if lone_layers:
                    _refuse(f"layers {f.name!r} has footprint layers; the meshloom route takes slab layers only "
                            "(a lone layers feature takes the meshine.extrude route)", path)
                _refuse(f"layers {f.name!r} has footprint layers; with other features a 3d component takes slab "
                        "layers only, until a later slice", path)
            z = f.data["z0"]
            for lay in layers:
                z1 = z + lay["thickness"]
                material = lay["material"]
                region = lay.get("region") or (material if material is not None else f"{f.id}.{lay['name']}")
                out.append(_Prism(i, f.id, f"{f.id}.{lay['name']}", "slab", region, material, f.mesh_size,
                                  (dom["xmin"], dom["xmax"], dom["ymin"], dom["ymax"], z, z1)))
                z = z1
        elif f.type == "extrude":
            prof = dict(f.data["profile"])
            t = prof.pop("type")
            if t not in _PROFILE_PARTS:
                _refuse(f"extrude {f.name!r} is not taken yet in a 3d component (an extruded circle is a cylinder); "
                        f"{_TAKEN}", path)
            pts, parts = _profile_points(t, prof)
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            out.append(_Prism(i, f.id, f.id, "extrude", f.region, f.material, f.mesh_size,
                              (min(xs), max(xs), min(ys), max(ys), f.data["zmin"], f.data["zmax"]),
                              (t, prof, parts)))
        else:
            _refuse(f"{f.type} {f.name!r} is not taken yet in a 3d component; {_TAKEN}", path)
    _check_regions(comp, out)
    return out


def _profile_points(t: str, d: dict):
    """The corners (pm, exact) and part names, edge by edge, of a rect, trapezoid or polygon profile,
    in the 2D engine's order (a rect or trapezoid: bottom, right, top, left; contract A4 names the
    bottom and top y0 and y1)."""
    if t == "rect":
        x, y, w, h = d["x"], d["y"], d["w"], d["h"]
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], ["y0", "right", "y1", "left"]
    if t == "trapezoid":
        cx, y, w, h, wt = (Fraction(d[k]) for k in ("cx", "y", "w", "h", "w_top"))
        pts = [(cx - w / 2, y), (cx + w / 2, y), (cx + wt / 2, y + h), (cx - wt / 2, y + h)]
        return [(_ex(x), _ex(y)) for x, y in pts], ["y0", "right", "y1", "left"]
    return [tuple(p) for p in d["points"]], list(d["edges"])


def _ex(q):
    """An exact rational as an int when it is one (so integer geometry keeps its integer form)."""
    q = Fraction(q)
    return int(q) if q.denominator == 1 else q


def _check_regions(comp: Component, prisms: list[_Prism]) -> None:
    """One material per region, across boxes, slab layers and the background (the contract's
    region rules; a slab layer's region is its ``region``, otherwise its material name)."""
    material_of: dict = {}
    bg = comp.background.get("material", _MISSING)
    material_of["background"] = (bg, "background")
    name_of = {f.name: f for f in comp.features if f.type != "layers"}
    for p in prisms:
        if p.kind == "slab":
            path = _feature_path(comp, p.feature_index)
            if p.region == "background":
                _refuse(f"{path}: layer {p.prefix!r} takes the region name 'background', which is reserved", path,
                        "E-CONTRACT")
            other = name_of.get(p.region)
            if other is not None and other.region != p.region:
                _refuse(f"{path}: the region {p.region!r} of layer {p.prefix!r} equals the name of feature "
                        f"{other.name!r}, which is not in that region", path, "E-CONTRACT")
        seen = material_of.setdefault(p.region, (p.material, p.prefix))
        if seen[0] != p.material:
            path = _feature_path(comp, p.feature_index)
            _refuse(f"{path}: region {p.region!r} merges {seen[1]!r} and {p.prefix!r}, whose materials differ", path,
                    "E-CONTRACT")


# ----------------------------------------------------------------------------- the complex

@dataclass
class Cell3D:
    """One volume of the complex: a fine 2D cell times one slab."""

    index: int
    region: str
    material: object                # a name, None for void, or the missing marker (homogeneous body)
    feature: str                    # owning feature id, or "background"
    feature_index: int              # -1 for the background
    provenance: str                 # "<id>" of a box, "<id>.<layer>" of a slab layer, "background"
    mesh_size: int | None           # pm
    fine: int                       # the 2D cell
    slab: int                       # z between levels[slab] and levels[slab + 1]
    volume: int                     # pm^3, exact

    @property
    def void(self) -> bool:
        return self.material is None

    @property
    def feature_indices(self) -> frozenset:
        return frozenset({self.feature_index})


@dataclass
class Face3D:
    """A planar face of the complex: a polygon in an axis-aligned plane, or a vertical quad of a
    sloped extrude side, with its two sides."""

    index: int
    axis: int                       # 0, 1, 2: the face lies in the plane coordinate[axis] == coord; SLOPED: see plane
    coord: object                   # pm (exact); None for a sloped face
    loops: list                     # [outer, hole, ...]; each a list of (x, y, z) pm points
    provenance: frozenset
    minus: frozenset                # cells on the side of smaller coordinate[axis] (empty: outside the domain)
    plus: frozenset
    exterior: bool                  # one side is outside the domain or void (a face of the mesh boundary)
    tag: str | None = None          # mesh tag of an exterior face
    area: object = 0                # pm^2, exact (a sloped face: the float of its exact area)
    plane: tuple | None = None      # a sloped face: (nx, ny, d), its plane nx*x + ny*y == d (pm, exact)

    @property
    def sides(self):
        return self.minus, self.plus


@dataclass
class Complex3D:
    component: str
    domain: dict
    levels: list                    # distinct z levels, pm
    cells: list
    faces: list
    selections: dict                # name -> ("region" | "boundary", frozenset of cell or face indices)
    prisms: list = field(repr=False, default_factory=list)
    _plan: object = field(repr=False, default=None)        # the 2D complex of the footprints
    _component: object = field(repr=False, default=None)
    _rectilinear: bool = field(repr=False, default=True)   # every fine curve is axis-aligned
    _vertex_names: list = field(repr=False, default_factory=list)   # per 2D vertex, its curves' names

    def region_names(self) -> list[str]:
        """Regions in feature order, the background last (as in 2D)."""
        first: dict = {}
        for c in self.cells:
            key = len(self.prisms) + 1 if c.feature_index < 0 else c.feature_index
            first[c.region] = min(first.get(c.region, key), key)
        return sorted(first, key=first.get)

    def volume_of_region(self, region: str) -> int:
        """Exact pm^3."""
        return sum(c.volume for c in self.cells if c.region == region)

    def faces_with(self, provenance: str) -> list[int]:
        return [f.index for f in self.faces if provenance in f.provenance]

    def exterior_faces(self) -> list[int]:
        return [f.index for f in self.faces if f.exterior]

    def select(self, expr) -> tuple[str, frozenset]:
        """``("region", cells)`` or ``("boundary", faces)`` of a ``mesh.controls`` target."""
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


def evaluate3d(model: GeometryModel, component: str | None = None) -> Complex3D:
    """The 3D region complex of a ``3d`` component of boxes and slab layers (stage 5, slice 1).

    A component holding one ``layers`` feature is refused here: it keeps the ``meshine.extrude``
    route (``simcase.geometry_document.layer_stack``)."""
    return _evaluate(_pick(model, component), through_meshloom=False)


def display_complex3d(model: GeometryModel, component: str | None = None) -> Complex3D:
    """The exact 3D complex of any ``3d`` component slice 1 takes, for display: ``evaluate3d``'s
    complex, and for a component holding one ``layers`` feature of slab layers (which is meshed on
    the ``meshine.extrude`` route) the same complex the meshloom route would build. It meshes nothing
    and does not change what ``build_mesh3d`` does or refuses.

    ``model`` is what ``simcase.parse_geometry`` returns; ``component`` names the component, and may
    be left out when the model has exactly one ``3d`` component (2d footprint components beside it
    are allowed). An unknown name, a ``2d`` or axisymmetric component, and an omitted name with no
    or several ``3d`` components are refused by name (``E-CONTRACT`` at
    ``geometry.components.<name>``)."""
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
                            "display_complex3d takes a 3d component (2d and axisymmetric components go through "
                            "simcase.evaluate_geometry)", path=f"geometry.components.{component}.dimension")
    return _evaluate(comp, through_meshloom=True)


def _evaluate(comp: Component, *, through_meshloom: bool) -> Complex3D:
    if comp.dimension != "3d":
        raise GeometryError(f"component {comp.name!r}: the 3D engine takes 3d components; 2d and axisymmetric "
                            "ones go through simcase.geometry_engine")
    lone = len(comp.features) == 1 and comp.features[0].type == "layers"
    if lone and not through_meshloom:
        path = _feature_path(comp, 0)
        _refuse(f"layers {comp.features[0].name!r} is the component's only feature: a 3d component holding one "
                "layers feature takes the meshine.extrude route (simcase.geometry_document.layer_stack)", path,
                "E-CONTRACT")
    prisms = _prisms(comp, lone_layers=lone)
    return _Builder(comp, prisms).run()


class _Builder:
    def __init__(self, comp: Component, prisms: list[_Prism]):
        self.comp = comp
        self.P = prisms
        d = comp.domain
        self.dom = (d["xmin"], d["xmax"], d["ymin"], d["ymax"], d["zmin"], d["zmax"])

    # -- the footprints through the 2D engine ------------------------------------

    def _plan(self):
        from .geometry_engine import evaluate_component
        x0, x1, y0, y1 = self.dom[:4]
        feats = [Feature(f"p{k}", f"p{k}", f"p{k}", p.profile[0], "m", None, p.profile[1]) if p.kind == "extrude"
                 else Feature(f"p{k}", f"p{k}", f"p{k}", "rect", "m", None,
                              {"x": p.bounds[0], "y": p.bounds[2], "w": p.bounds[1] - p.bounds[0],
                               "h": p.bounds[3] - p.bounds[2]}) for k, p in enumerate(self.P)]
        plan = Component(self.comp.name, "2d", {"xmin": x0, "xmax": x1, "ymin": y0, "ymax": y1}, {"material": "m"},
                         feats, "imprint", {}, [], self.comp.length_unit, self.comp.pm_per_unit)
        return evaluate_component(plan)

    def _names(self, engine_provenance, slab=None) -> frozenset:
        """The 3D provenance of a fine curve's engine names, keeping prisms active in ``slab``."""
        out = set()
        for name in engine_provenance:
            fid, part = name.split(".", 1)
            if fid == "domain":
                out.add(f"domain.{_RECT_PART[part]}")
                continue
            k = int(fid[1:])
            if slab is None or self.active(k, slab):
                p = self.P[k]
                if p.kind == "extrude":
                    table = _PROFILE_PARTS[p.profile[0]]
                    side = part if table is None else table[part]
                else:
                    side = _RECT_PART[part]
                out.add(p.part(side))
        return frozenset(out)

    def active(self, k: int, s: int) -> bool:
        b = self.P[k].bounds
        return b[4] <= self.levels[s] and b[5] >= self.levels[s + 1]

    # -- the build ---------------------------------------------------------------------

    def run(self) -> Complex3D:
        comp, P = self.comp, self.P
        zmin, zmax = self.dom[4], self.dom[5]
        levels = {zmin, zmax}
        for p in P:
            for z in p.bounds[4:]:
                if zmin < z < zmax:
                    levels.add(z)
        self.levels = L = sorted(levels)
        nslab = len(L) - 1
        rc = self._plan()
        self.rc = rc
        V = _plan_vertices(rc)
        self.V = V
        self.rectilinear = all(V[k.a][0] == V[k.b][0] or V[k.a][1] == V[k.b][1] for k in rc.curves)
        ncell = len(rc.cells)
        bg = comp.background.get("material", _MISSING)

        # owner of each (fine cell, slab): the last active prism containing the cell, or -1
        owner = [[-1] * nslab for _ in range(ncell)]
        for c in rc.cells:
            members = sorted(m for m in c.membership if m >= 0)
            for s in range(nslab):
                for k in reversed(members):
                    if self.active(k, s):
                        owner[c.index][s] = k
                        break
        self.owner = owner

        # cells
        area = self._fine_areas()
        cells: list[Cell3D] = []
        cell_at: dict = {}
        for c in rc.cells:
            for s in range(nslab):
                k = owner[c.index][s]
                if k < 0:
                    region, material, fid, fi, prov, size = ("background", bg, "background", -1, "background",
                                                             comp.background.get("mesh_size"))
                else:
                    p = P[k]
                    region, material, fid, fi, prov, size = (p.region, p.material, p.feature_id, p.feature_index,
                                                             p.prefix, p.mesh_size)
                idx = len(cells)
                cells.append(Cell3D(idx, region, material, fid, fi, prov, size, c.index, s,
                                    area[c.index] * (L[s + 1] - L[s])))
                cell_at[(c.index, s)] = idx
        self.cells, self.cell_at = cells, cell_at

        def side(ci, s):
            """(region, feature index, void) of a fine cell in a slab; None outside the domain."""
            if ci is None or s < 0 or s >= nslab:
                return None
            cell = cells[cell_at[(ci, s)]]
            return (cell.region, cell.feature_index, cell.void)

        faces: list[Face3D] = []
        self._horizontal(faces, side)
        self._vertical(faces, side)
        self.faces = faces
        cx = Complex3D(comp.name, dict(comp.domain), list(L), cells, faces, {}, list(P), rc, comp,
                       self.rectilinear, self._vertex_names())
        _default_tags(cx)
        _apply_boundary_tags(cx, comp)
        cx.selections = _resolve_selections(cx, comp)
        return cx

    def _fine_areas(self) -> list[int]:
        """Exact area of every fine cell (pm^2), by the shoelace formula over its loops."""
        out = []
        for c in self.rc.cells:
            twice = 0
            for loop in c.loops:
                for ki, fwd in loop:
                    k = self.rc.curves[ki]
                    a, b = (k.a, k.b) if fwd else (k.b, k.a)
                    (xa, ya), (xb, yb) = self.V[a], self.V[b]
                    twice += xa * yb - xb * ya
            out.append(_ex(Fraction(abs(twice), 2)))
        return out

    def _vertex_names(self) -> list:
        """The 3D provenance names of the fine curves at every 2D vertex (any slab)."""
        out = [set() for _ in self.V]
        for k in self.rc.curves:
            names = self._names(k.provenance)
            out[k.a] |= names
            out[k.b] |= names
        return [frozenset(n) for n in out]

    @staticmethod
    def _exists(sa, sb) -> bool:
        """A face lies between two sides when their regions differ (or one is outside) and one side is meshed."""
        if sa == sb:
            return False
        if (sa is None or sa[2]) and (sb is None or sb[2]):
            return False
        if sa is not None and sb is not None and sa[0] == sb[0]:
            return False
        return True

    def _cells_of(self, fines, s) -> frozenset:
        if s < 0 or s >= len(self.levels) - 1:
            return frozenset()
        return frozenset(self.cell_at[(ci, s)] for ci in fines)

    def _horizontal(self, faces: list, side) -> None:
        rc, L, P = self.rc, self.levels, self.P
        for s, z in enumerate(L):
            key = {}
            for c in rc.cells:
                below, above = side(c.index, s - 1), side(c.index, s)
                if not self._exists(below, above):
                    continue
                prov = set()
                if z == self.dom[4]:
                    prov.add("domain.z0")
                if z == self.dom[5]:
                    prov.add("domain.z1")
                for k in c.membership:
                    if k < 0:
                        continue
                    b = P[k].bounds
                    if b[4] == z:
                        prov.add(P[k].part("z0"))
                    if b[5] == z:
                        prov.add(P[k].part("z1"))
                key[c.index] = (below, above, frozenset(prov))
            for group in _groups(rc, key):
                k0 = key[group[0]]
                loops2 = _merged_loops(rc, self.V, set(group))
                cells_minus = self._cells_of(group, s - 1)
                cells_plus = self._cells_of(group, s)
                ext = k0[0] is None or k0[0][2] or k0[1] is None or k0[1][2]
                for loops in loops2:
                    pts = [[(x, y, z) for x, y in loop] for loop in loops]
                    faces.append(Face3D(len(faces), 2, z, pts, k0[2], cells_minus, cells_plus, ext,
                                        area=_loops_area(loops)))

    def _vertical(self, faces: list, side) -> None:
        rc, L, V = self.rc, self.levels, self.V
        nslab = len(L) - 1
        runs = {}           # (axis, coord, s0, s1, key) -> [(lo, hi, curve)]
        for k in rc.curves:
            (xa, ya), (xb, yb) = V[k.a], V[k.b]
            left, right = k.left, k.right
            if ya == yb:                           # along x; normal y
                axis, coord = 1, ya
                lo, hi = xa, xb
                # going +x, the left side is +y
                minus, plus = (right, left) if xa < xb else (left, right)
            elif xa == xb:                         # along y; normal x
                axis, coord = 0, xa
                lo, hi = ya, yb
                # going +y, the left side is -x
                minus, plus = (left, right) if ya < yb else (right, left)
            else:                                  # sloped: one quad per fine curve (split at every 2D vertex)
                axis, coord = SLOPED, k.index
                lo, hi = 0, 1
                minus, plus = right, left
            if lo > hi:
                lo, hi = hi, lo
            s = 0
            while s < nslab:
                sm, sp = side(minus, s), side(plus, s)
                if not self._exists(sm, sp):
                    s += 1
                    continue
                key = (sm, sp, self._names(k.provenance, s))
                t = s
                while t + 1 < nslab and (side(minus, t + 1), side(plus, t + 1),
                                          self._names(k.provenance, t + 1)) == key:
                    t += 1
                runs.setdefault((axis, coord, s, t, key), []).append((lo, hi, minus, plus))
                s = t + 1
        for (axis, coord, s0, s1, key), pieces in sorted(runs.items(), key=lambda kv: kv[0][:4]):
            pieces.sort()
            merged = []
            for lo, hi, minus, plus in pieces:
                if merged and merged[-1][1] == lo:
                    merged[-1][1] = hi
                    merged[-1][2].add(minus)
                    merged[-1][3].add(plus)
                else:
                    merged.append([lo, hi, {minus}, {plus}])
            za, zb = L[s0], L[s1 + 1]
            ext = key[0] is None or key[0][2] or key[1] is None or key[1][2]
            if axis == SLOPED:
                k = rc.curves[coord]
                (xa, ya), (xb, yb) = V[k.a], V[k.b]
                loop = [(xa, ya, za), (xb, yb, za), (xb, yb, zb), (xa, ya, zb)]
                (_, _, mins, plus), = merged
                cm = frozenset(self.cell_at[(ci, s)] for ci in mins if ci is not None for s in range(s0, s1 + 1))
                cp = frozenset(self.cell_at[(ci, s)] for ci in plus if ci is not None for s in range(s0, s1 + 1))
                nx, ny = yb - ya, xa - xb
                faces.append(Face3D(len(faces), SLOPED, None, [loop], key[2], cm, cp, ext,
                                    area=math.hypot(float(xb - xa), float(yb - ya)) * float(zb - za),
                                    plane=(nx, ny, nx * xa + ny * ya)))
                continue
            for lo, hi, mins, plus in merged:
                if axis == 1:
                    loop = [(lo, coord, za), (hi, coord, za), (hi, coord, zb), (lo, coord, zb)]
                else:
                    loop = [(coord, lo, za), (coord, hi, za), (coord, hi, zb), (coord, lo, zb)]
                cm = frozenset(self.cell_at[(ci, s)] for ci in mins if ci is not None for s in range(s0, s1 + 1))
                cp = frozenset(self.cell_at[(ci, s)] for ci in plus if ci is not None for s in range(s0, s1 + 1))
                faces.append(Face3D(len(faces), axis, coord, [loop], key[2], cm, cp, ext, area=(hi - lo) * (zb - za)))


def _plan_vertices(rc) -> list:
    """The 2D vertices (pm, exact rationals; ints where integer). The engine's vertices of lines are
    rational: profiles of straight edges only."""
    out = []
    for x, y in rc.vertices:
        if x.b or y.b:
            raise GeometryError("internal: an irrational vertex in a 3d component's footprints")
        out.append((_ex(x.a), _ex(y.a)))
    return out


def _groups(rc, key: dict) -> list[list[int]]:
    """Fine cells with one key, joined across the fine curves between them."""
    parent = {c: c for c in key}

    def find(c):
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c

    for k in rc.curves:
        a, b = k.left, k.right
        if a is not None and b is not None and a in key and b in key and key[a] == key[b]:
            parent[find(a)] = find(b)
    out: dict = {}
    for c in sorted(key):
        out.setdefault(find(c), []).append(c)
    return list(out.values())


def _direction(p, q):
    """The exact pseudo-angle of p -> q in [0, 4): 0, 1, 2, 3 along +x, +y, -x, -y, monotone in the angle."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    t = Fraction(dy) / (abs(dx) + abs(dy))
    if dx >= 0 and dy >= 0:
        return _ex(t)
    if dx < 0:
        return _ex(2 - t)
    return _ex(4 + t)


def _merged_loops(rc, V, group: set) -> list[list]:
    """The faces of a group of fine cells: ``[[outer, hole, ...], ...]`` of 2D pm points.

    One face with its holes when its boundary is simple; when the boundary meets itself at a
    vertex (a pinch), the group is split into rectangles instead (axis-aligned boundaries), or into
    its fine cells, a pinched fine cell into triangles (``_cell_faces``), so that every loop handed
    on is simple."""
    out_edges: dict = {}
    for k in rc.curves:
        inl = k.left in group if k.left is not None else False
        inr = k.right in group if k.right is not None else False
        if inl == inr:
            continue
        a, b = (k.a, k.b) if inl else (k.b, k.a)
        out_edges.setdefault(a, []).append(b)
    used = set()
    loops = []
    for a0 in sorted(out_edges):
        for b0 in out_edges[a0]:
            if (a0, b0) in used:
                continue
            loop = [a0]
            a, b = a0, b0
            used.add((a, b))
            while b != a0:
                loop.append(b)
                back = (_direction(V[a], V[b]) + 2) % 4
                cands = [c for c in out_edges[b] if (b, c) not in used]
                nxt = min(cands, key=lambda c: (back - _direction(V[b], V[c])) % 4 or 4)
                a, b = b, nxt
                used.add((a, b))
            loops.append([V[v] for v in loop])
    loops = [_simplify(lp) for lp in loops]
    seen, pinch = set(), False
    for lp in loops:
        for p in lp:
            if p in seen:
                pinch = True
            seen.add(p)
    outers = [lp for lp in loops if _signed_area2(lp) > 0]
    if pinch or len(outers) != 1:
        if all(_axis_aligned(lp) for lp in loops):
            return [[r] for r in _rectangles(loops)]
        return [face for ci in sorted(group) for face in _cell_faces(rc, V, ci)]
    holes = [lp for lp in loops if _signed_area2(lp) < 0]
    return [[outers[0], *holes]]


def _simplify(loop: list) -> list:
    """Drop the vertices of a closed loop where it goes straight on along an axis. A vertex on a sloped
    run is kept: the sloped sides are split at every 2D vertex, and a point cannot be put back into a
    sloped edge after rounding."""
    n = len(loop)
    keep = []
    for i in range(n):
        d0, d1 = _direction(loop[i - 1], loop[i]), _direction(loop[i], loop[(i + 1) % n])
        if d0 != d1 or not isinstance(d0, int):
            keep.append(loop[i])
    return keep


def _axis_aligned(loop: list) -> bool:
    n = len(loop)
    return all(loop[i][0] == loop[(i + 1) % n][0] or loop[i][1] == loop[(i + 1) % n][1] for i in range(n))


def _cell_loops(rc, V, ci: int) -> list:
    """The loops of one fine cell, as lists of 2D pm points."""
    out = []
    for loop in rc.cells[ci].loops:
        pts = []
        for ki, fwd in loop:
            k = rc.curves[ki]
            pts.append(V[k.a] if fwd else V[k.b])
        out.append(pts)
    return out


def _cell_faces(rc, V, ci: int) -> list:
    """The faces of one fine cell: the cell with its holes, or its triangles when its loops meet
    themselves or each other at a vertex."""
    loops = _cell_loops(rc, V, ci)
    pts = [p for lp in loops for p in lp]
    if len(pts) == len(set(pts)):
        return [loops]
    outer, holes = loops[0], loops[1:]
    return [[t] for t in _triangulate(outer, holes)]


def _orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _crosses(a, b, c, d) -> bool:
    """Segments ab and cd share a point other than a common end point."""
    if {a, b} & {c, d}:
        shared = ({a, b} & {c, d}).pop()
        p = a if b == shared else b
        q = c if d == shared else d
        # collinear and overlapping beyond the shared end point
        return _orient(shared, p, q) == 0 and (p[0] - shared[0]) * (q[0] - shared[0]) + \
            (p[1] - shared[1]) * (q[1] - shared[1]) > 0
    o1, o2, o3, o4 = _orient(a, b, c), _orient(a, b, d), _orient(c, d, a), _orient(c, d, b)
    if o1 * o2 < 0 and o3 * o4 < 0:
        return True

    def on(p, q, r):            # r on the closed segment pq (collinear)
        return min(p[0], q[0]) <= r[0] <= max(p[0], q[0]) and min(p[1], q[1]) <= r[1] <= max(p[1], q[1])
    return ((o1 == 0 and on(a, b, c)) or (o2 == 0 and on(a, b, d)) or (o3 == 0 and on(c, d, a))
            or (o4 == 0 and on(c, d, b)))


def _triangulate(outer: list, holes: list) -> list:
    """Triangles (counter-clockwise, on the loops' own vertices) of a polygon with holes whose loops may
    touch at vertices: holes are bridged into the outer loop, then ears are clipped (exact)."""
    if _signed_area2(outer) < 0:
        outer = outer[::-1]
    holes = [h[::-1] if _signed_area2(h) > 0 else list(h) for h in holes]
    loops_all = [outer] + holes
    edges = [(lp[i], lp[(i + 1) % len(lp)]) for lp in loops_all for i in range(len(lp))]

    def inside(p):
        return _inside_loops(p[0], p[1], loops_all)

    poly = list(outer)
    for hole in sorted(holes, key=lambda h: -max(p[0] for p in h)):
        best = None
        for hi, m in enumerate(hole):
            for pi, q in enumerate(poly):
                if m == q:
                    continue
                if any(_crosses(m, q, a, b) for a, b in edges):
                    continue
                mid = ((m[0] + q[0]) / 2, (m[1] + q[1]) / 2)
                if not inside(mid):
                    continue
                d2 = (m[0] - q[0]) ** 2 + (m[1] - q[1]) ** 2
                if best is None or d2 < best[0]:
                    best = (d2, hi, pi)
        if best is None:
            raise GeometryError("internal: no bridge from a hole to its outer loop")
        _, hi, pi = best
        ring = hole[hi:] + hole[:hi + 1]
        poly = poly[:pi + 1] + ring + poly[pi:pi + 1] + poly[pi + 1:]
        edges.append((hole[hi], poly[pi]))
    tris = []
    while len(poly) > 3:
        n = len(poly)
        for i in range(n):
            a, b, c = poly[i - 1], poly[i], poly[(i + 1) % n]
            if _orient(a, b, c) <= 0:
                continue
            corners = {a, b, c}
            if any(p not in corners and _orient(a, b, p) >= 0 and _orient(b, c, p) >= 0 and _orient(c, a, p) >= 0
                   for p in poly):
                continue
            tris.append([a, b, c])
            del poly[i]
            break
        else:
            raise GeometryError("internal: a pinched face of the complex has no ear to clip")
    if _orient(*poly) <= 0:
        raise GeometryError("internal: a pinched face of the complex leaves a degenerate triangle")
    tris.append(list(poly))
    return tris


def _signed_area2(loop: list) -> int:
    n = len(loop)
    return sum(loop[i][0] * loop[(i + 1) % n][1] - loop[(i + 1) % n][0] * loop[i][1] for i in range(n))


def _loops_area(loops: list):
    """Exact area (pm^2) of an outer loop minus its holes, whatever their orientations."""
    twice = abs(_signed_area2(loops[0])) - sum(abs(_signed_area2(lp)) for lp in loops[1:])
    return _ex(Fraction(twice, 2))


def _rectangles(loops: list) -> list[list]:
    """The region bounded by these axis-aligned loops (even-odd), as counter-clockwise rectangles:
    one per strip between consecutive vertex x values and interval inside it."""
    xs = sorted({p[0] for lp in loops for p in lp})
    horizontals = []
    for lp in loops:
        n = len(lp)
        for i in range(n):
            p, q = lp[i], lp[(i + 1) % n]
            if p[1] == q[1]:
                horizontals.append((min(p[0], q[0]), max(p[0], q[0]), p[1]))
    out = []
    for xa, xb in zip(xs, xs[1:]):
        ys = sorted(y for lo, hi, y in horizontals if lo <= xa and xb <= hi)
        for ya, yb in zip(ys[::2], ys[1::2]):
            out.append([(xa, ya), (xb, ya), (xb, yb), (xa, yb)])
    return out


# ----------------------------------------------------------------------------- tags and selectors

def _default_tags(cx: Complex3D) -> None:
    sides = {f"domain.{t}": t for t in SIDE_TAGS}
    for f in cx.faces:
        if f.exterior:
            f.tag = next((sides[n] for n in sorted(f.provenance) if n in sides), VOID_TAG)


def _apply_boundary_tags(cx: Complex3D, comp: Component) -> None:
    tagged: set = set()
    for entry in comp.boundary_tags:
        tag = entry["tag"]
        for i in _resolve_boundary(cx, comp, entry["select"]["boundary"], f"boundary_tags {tag!r}", ()):
            f = cx.faces[i]
            if f.exterior and i not in tagged:
                f.tag = tag
                tagged.add(i)


def _resolve_selections(cx: Complex3D, comp: Component) -> dict:
    out = {}
    for name, sel in comp.selections.items():
        kind = "region" if "region" in sel else "boundary"
        resolve = _resolve_region if kind == "region" else _resolve_boundary
        chosen = resolve(cx, comp, sel[kind], f"selection {name!r}", (name,))
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
    sel = comp.selections.get(expr)
    if sel is None or kind not in sel:
        return None
    if expr in stack:
        raise GeometryError(f"{where}: selection {expr!r} refers to itself")
    return sel[kind]


def _regions(cx: Complex3D, comp: Component) -> set:
    return {p.region for p in cx.prisms} | {"background"}


def _resolve_region(cx: Complex3D, comp: Component, expr, where: str, stack: tuple) -> set:
    if isinstance(expr, str):
        hits = []
        inner = _named(comp, expr, "region", where, stack)
        if inner is not None:
            hits.append(("selection", _resolve_region(cx, comp, inner, where, stack + (expr,))))
        regions = _regions(cx, comp)
        i, f = _feature_by_id(comp, expr)
        if expr in regions:
            hits.append(("region", {c.index for c in cx.cells if c.region == expr}))
        if f is not None and not (expr in regions and f.type != "layers" and f.region == expr):
            hits.append(("feature", {c.index for c in cx.cells if c.feature_index == i}))
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
        return {c.index for c in cx.cells if c.feature_index == i}
    if k == "material":
        return {c.index for c in cx.cells if c.material == v}
    if k == "any":
        out: set = set()
        for e in v:
            out |= _resolve_region(cx, comp, e, where, stack)
        return out
    raise GeometryError(f"{where}: {k!r} selects boundaries, not regions")


def _tags(comp: Component) -> set:
    return set(SIDE_TAGS) | {VOID_TAG} | {e["tag"] for e in comp.boundary_tags}


def _resolve_boundary(cx: Complex3D, comp: Component, expr, where: str, stack: tuple) -> set:
    if isinstance(expr, str):
        inner = _named(comp, expr, "boundary", where, stack)
        if inner is not None:
            return _resolve_boundary(cx, comp, inner, where, stack + (expr,))
        if expr in _tags(comp):
            return {f.index for f in cx.faces if f.tag == expr}
        if "." in expr:
            return set(cx.faces_with(expr))
        _i, f = _feature_by_id(comp, expr)
        if f is None:
            raise GeometryError(f"{where}: {expr!r} is not a selection, a tag, a provenance name or a feature id")
        return _faces_of_feature(cx, f.id)
    (k, v), = expr.items()
    if k == "feature":
        _i, f = _feature_by_id(comp, v)
        if f is None:
            raise GeometryError(f"{where}: no feature {v!r}")
        return _faces_of_feature(cx, f.id)
    if k == "provenance":
        return set(cx.faces_with(v))
    if k == "material":
        return _boundary_of(cx, {c.index for c in cx.cells if c.material == v})
    if k == "of":
        return _boundary_of(cx, _resolve_region(cx, comp, v, where, stack))
    if k == "between":
        a, b = v
        sa = None if a == "exterior" else _resolve_region(cx, comp, a, where, stack)
        sb = None if b == "exterior" else _resolve_region(cx, comp, b, where, stack)
        return {f.index for f in cx.faces
                if (_side_in(f.minus, sa) and _side_in(f.plus, sb)) or (_side_in(f.minus, sb) and _side_in(f.plus, sa))}
    if k == "any":
        out: set = set()
        for e in v:
            out |= _resolve_boundary(cx, comp, e, where, stack)
        return out
    raise GeometryError(f"{where}: unknown selector key {k!r}")


def _side_in(cells: frozenset, selection) -> bool:
    if selection is None:
        return not cells
    return bool(cells & selection)


def _boundary_of(cx: Complex3D, cells: set) -> set:
    return {f.index for f in cx.faces if bool(f.minus & cells) != bool(f.plus & cells)}


def _faces_of_feature(cx: Complex3D, fid: str) -> set:
    prefix = fid + "."
    return {f.index for f in cx.faces if any(p.startswith(prefix) for p in f.provenance)}


# ----------------------------------------------------------------------------- the meshloom hand-off

def _metres(k: int) -> float:
    """Rule H1: a pm value in metres, rounded once."""
    return float(Fraction(k, PM_PER_M))


def _check_rounding(cx: Complex3D, comp: Component) -> None:
    """Refuse two distinct defining values of one axis that round to one metre double (rule H1)."""
    dom = comp.domain
    for a, axis in enumerate("xyz"):
        lo, hi = dom[f"{axis}min"], dom[f"{axis}max"]
        named: dict = {lo: ("domain", f"domain.{axis}0", -1), hi: ("domain", f"domain.{axis}1", -1)}
        for p in cx.prisms:
            if p.kind == "extrude" and a < 2:
                continue                    # an extrude's x and y values are its profile's vertices (below)
            for j, part in ((2 * a, f"{axis}0"), (2 * a + 1, f"{axis}1")):
                v = p.bounds[j]
                if lo <= v <= hi and v not in named:
                    named[v] = (p.feature_id, p.part(part), p.feature_index)
        if a < 2 and any(p.kind == "extrude" for p in cx.prisms):
            # every 2D vertex, derived ones included (intersections of sloped edges): by the smallest
            # name among the curves through a vertex with that coordinate
            names: dict = {}
            for v, ns in zip(_plan_vertices(cx._plan), cx._vertex_names):
                if ns:
                    names[v[a]] = min(names[v[a]], min(ns)) if v[a] in names else min(ns)
            for v in sorted(names):
                if v not in named:
                    fid = names[v].split(".", 1)[0]
                    i, _f = _feature_by_id(comp, fid)
                    named[v] = (fid, names[v], -1 if i is None else i)
        values = sorted(named)
        for u, w in zip(values, values[1:]):
            if _metres(u) == _metres(w):
                (_, na, ia), (_, nb, ib) = named[u], named[w]
                later = max(ia, ib)
                path = (_feature_path(comp, later) if later >= 0 else f"geometry.components.{comp.name}.domain")
                _refuse(f"{na} and {nb} round to the same coordinate {_metres(u)!r} m", path)


@dataclass
class _Handoff:
    points: list                    # (x, y, z) pm
    facets: list                    # each [outer, hole, ...] of point indices
    face_of_facet: list             # facet -> complex face index
    region_points: list             # [((x, y, z) metres, name or None)]
    h: object                       # float or {region: float}, metres
    max_points: int
    estimate: float                 # tetrahedra


def _handoff(cx: Complex3D, comp: Component, mesh_opts: dict) -> _Handoff:
    # loops with every PLC point that lies on an edge put into the edge
    loops_of = [f.loops for f in cx.faces if _meshed(cx, f)]
    face_ids = [f.index for f in cx.faces if _meshed(cx, f)]
    allpts = sorted({p for loops in loops_of for lp in loops for p in lp})
    lines: dict = {}
    for p in allpts:
        for a in range(3):
            key = (a,) + tuple(p[b] for b in range(3) if b != a)
            lines.setdefault(key, []).append(p[a])
    for v in lines.values():
        v.sort()
    index = {p: i for i, p in enumerate(allpts)}
    facets = []
    for loops in loops_of:
        out = []
        for lp in loops:
            full = []
            n = len(lp)
            for i in range(n):
                p, q = lp[i], lp[(i + 1) % n]
                full.append(index[p])
                differ = [b for b in range(3) if p[b] != q[b]]
                if len(differ) != 1:
                    continue                  # a sloped edge: no point lies inside it (split at every 2D vertex)
                a = differ[0]
                key = (a,) + tuple(p[b] for b in range(3) if b != a)
                line = lines[key]
                lo, hi = sorted((p[a], q[a]))
                i0, i1 = bisect.bisect_right(line, lo), bisect.bisect_left(line, hi)
                between = line[i0:i1]
                if p[a] > q[a]:
                    between = between[::-1]
                for c in between:
                    r = list(p)
                    r[a] = c
                    full.append(index[tuple(r)])
            out.append(full)
        facets.append(out)
    region_points = _region_points(cx)
    h, estimate = _sizes(cx, comp, mesh_opts)
    return _Handoff(allpts, facets, face_ids, region_points, h, mesh_opts["element_count_limit"], estimate)


def _meshed(cx: Complex3D, f: Face3D) -> bool:
    return any(not cx.cells[c].void for c in f.minus | f.plus)


def _region_points(cx: Complex3D) -> list:
    """One exact interior point per bounded component of the complex (cells joined where no face
    separates them), named by its region, or None for an enclosed void."""
    rc, L = cx._plan, cx.levels
    nslab = len(L) - 1
    cells = cx.cells
    at = {(c.fine, c.slab): c.index for c in cells}
    parent = list(range(len(cells)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def joined(i, j):
        a, b = cells[i], cells[j]
        return (a.void and b.void) or (not a.void and not b.void and a.region == b.region)

    touches = [False] * len(cells)            # a void cell on the domain boundary
    for k in rc.curves:
        for s in range(nslab):
            if k.left is None or k.right is None:
                inside = k.left if k.right is None else k.right
                touches[at[(inside, s)]] = True
                continue
            i, j = at[(k.left, s)], at[(k.right, s)]
            if joined(i, j):
                parent[find(i)] = find(j)
    for c in cells:
        if c.slab == 0 or c.slab == nslab - 1:
            touches[c.index] = True
        if c.slab + 1 < nslab:
            j = at[(c.fine, c.slab + 1)]
            if joined(c.index, j):
                parent[find(c.index)] = find(j)
    comps: dict = {}
    for c in cells:
        comps.setdefault(find(c.index), []).append(c.index)
    rects = _cell_rectangles(cx) if cx._rectilinear else None
    V = _plan_vertices(rc)
    out = []
    for root in sorted(comps, key=lambda r: min(comps[r])):
        members = comps[root]
        first = cells[min(members)]
        if first.void and any(touches[i] for i in members):
            continue                               # open to the outside: not a bounded component
        if rects is not None:
            (xa, xb, ya, yb) = rects[first.fine]
            x, y = _inside(xa, xb), _inside(ya, yb)
        else:
            x, y = _cell_point(_cell_loops(rc, V, first.fine))
        point = (x, y, _inside(L[first.slab], L[first.slab + 1]))
        out.append((point, None if first.void else first.region))
    return out


def _cell_point(loops: list):
    """A point (metre doubles) strictly inside a fine cell, also after rule H1 rounds its loops: the
    middle of the widest interval of the horizontal line half-way between two vertex heights."""
    ys = sorted({p[1] for lp in loops for p in lp})
    best = None
    for ya, yb in zip(ys, ys[1:]):
        y = Fraction(ya + yb) / 2
        xs = []
        for lp in loops:
            n = len(lp)
            for i in range(n):
                (x0, y0), (x1, y1) = lp[i], lp[(i + 1) % n]
                if (y0 > y) != (y1 > y):
                    xs.append(x0 + (y - y0) * Fraction(x1 - x0) / (y1 - y0))
        xs.sort()
        for xa, xb in zip(xs[::2], xs[1::2]):
            score = min(xb - xa, yb - ya)
            if score > 0 and (best is None or score > best[0]):
                best = (score, (xa + xb) / 2, y)
    if best is None:
        raise GeometryError("internal: a fine cell of the complex has no interior")
    x, y = _metres(best[1]), _metres(best[2])
    rounded = [[(Fraction(_metres(p[0])), Fraction(_metres(p[1]))) for p in lp] for lp in loops]
    if not _inside_loops(Fraction(x), Fraction(y), rounded):
        raise GeometryError(f"no double lies inside the cell at ({x!r}, {y!r}) m; the geometry is below the "
                            "resolution of doubles there")
    return x, y


def _inside(lo: int, hi: int) -> float:
    """A double strictly between the metre doubles of two pm values."""
    a, b = _metres(lo), _metres(hi)
    m = float((Fraction(a) + Fraction(b)) / 2)
    if not a < m < b:
        raise GeometryError(f"no double lies strictly between {a!r} m and {b!r} m; the geometry is below the "
                            "resolution of doubles there")
    return m


def _cell_rectangles(cx: Complex3D) -> list:
    """For every fine cell, one grid rectangle (x0, x1, y0, y1) in pm that lies inside it (``_grid_cells``)."""
    xs, ys = _grid_lines(cx)
    grid = _grid_cells(cx, xs, ys)
    out: list = [None] * len(cx._plan.cells)
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            c = grid[i][j]
            if c is not None and out[c] is None:
                out[c] = (xs[i], xs[i + 1], ys[j], ys[j + 1])
    return out


def _grid_lines(cx: Complex3D):
    V = _plan_vertices(cx._plan)
    return sorted({v[0] for v in V}), sorted({v[1] for v in V})


def _mesh_options(document: dict, comp: Component) -> dict:
    """``mesh.element_size``, ``mesh.element_count_limit`` and ``mesh.controls`` of a format 0.3
    document, lengths in pm."""
    mesh = document.get("mesh") or {}
    if not isinstance(mesh, dict):
        raise GeometryError("mesh: expected an object", path="mesh", code="E-VALUE-FORM")
    reader = _Reader(document)
    size = None
    if "element_size" in mesh:
        size = reader.element_size(mesh["element_size"], "mesh.element_size")
        if size <= 0:
            raise GeometryError("mesh.element_size: must be positive", path="mesh.element_size", code="E-DOMAIN")
    limit = mesh.get("element_count_limit", DEFAULT_ELEMENT_COUNT_LIMIT)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise GeometryError("mesh.element_count_limit: a positive integer", path="mesh.element_count_limit",
                            code="E-VALUE-FORM")
    controls = []
    raw = mesh.get("controls") or []
    if not isinstance(raw, list):
        raise GeometryError("mesh.controls: expected a list", path="mesh.controls", code="E-VALUE-FORM")
    for i, entry in enumerate(raw):
        where = f"mesh.controls[{i}]"
        if not isinstance(entry, dict) or "select" not in entry:
            raise GeometryError(f"{where}: expected {{\"select\": ..., <one control>}}", path=where,
                                code="E-VALUE-FORM")
        if "circle_segment_count" in entry or "circle_segments" in entry:
            _refuse(f"mesh.controls: circle_segments on {entry['select']!r} is not taken for 3d surfaces yet; "
                    "use size", where)
        _keys(entry, {"select"}, {"element_size", "near", "far", "refinement_distance", "z_divisions"}, where)
        for key in ("near", "far", "refinement_distance", "z_divisions"):
            if key in entry:
                raise GeometryError(f"{where}.{key}: not taken for 3d components yet; use element_size",
                                    path=f"{where}.{key}")
        if "element_size" not in entry:
            raise GeometryError(f"{where}: give element_size", path=where, code="E-KEY-MISSING")
        controls.append({"select": entry["select"], "size": reader.element_size(entry["element_size"],
                                                                                 f"{where}.element_size"),
                         "path": where})
    return {"size": size, "element_count_limit": limit, "controls": controls}


def _sizes(cx: Complex3D, comp: Component, opts: dict):
    """meshloom's ``h`` (metres: one number, or one per region) and the estimate T = 6.3 sum(V_r / h_r^3)."""
    size_of = {}
    for c in cx.cells:
        size_of[c.index] = c.mesh_size if c.mesh_size is not None else opts["size"]
    for ctl in opts["controls"]:
        kind, chosen = cx.select(ctl["select"])
        if kind != "region":
            raise GeometryError(f"{ctl['path']}.element_size: a size on a boundary selection is not taken yet",
                                path=f"{ctl['path']}.element_size")
        for ci in chosen:
            size_of[ci] = ctl["size"]
    region_h: dict = {}
    volume: dict = {}
    for c in cx.cells:
        if c.void:
            continue
        h = size_of[c.index]
        if h is None:
            raise GeometryError(f"component {comp.name!r}: region {c.region!r} has no element size; give "
                                "mesh.element_size", path="mesh.element_size", code="E-KEY-MISSING")
        region_h[c.region] = min(region_h.get(c.region, h), h)
        volume[c.region] = volume.get(c.region, 0) + c.volume
    estimate = TETRAHEDRA_PER_VOLUME * sum(float(Fraction(volume[r], region_h[r] ** 3)) for r in volume)
    hs = {r: _metres(h) for r, h in region_h.items()}
    if len(set(hs.values())) == 1:
        return next(iter(hs.values())), estimate
    return hs, estimate


# ----------------------------------------------------------------------------- the mesh

@dataclass
class Mesh3DResult:
    """``build_mesh3d``'s result.

    ``mesh`` is the shared ``galerkin.Mesh3D`` in metres: ``tagged_faces`` by default tag
    (``x0``-``z1``, ``void``) or ``boundary_tags`` tag, ``interfaces`` by sorted region-name pair
    (wound from the first to the second), and ``mesh.provenance_faces``. ``provenance_faces`` maps
    each provenance name to the (F, 3) mesh faces of every complex face that carries it, exterior
    and interior. ``selections`` maps each named selection to ``("region", tetrahedron indices)``
    or ``("boundary", (F, 3) faces)``, and ``selection_nodes`` to its node indices. ``facet_faces``
    gives the mesh faces of every hand-off facet, ``face_of_facet`` its complex face. ``diagnostics``
    holds ``I-MESH-ESTIMATE``: the estimated tetrahedra and meshing time (0.4-0.6 ms each)."""

    mesh: object
    complex: Complex3D
    provenance_faces: dict
    selections: dict
    selection_nodes: dict
    facet_faces: list
    face_of_facet: list
    estimate: float
    handoff: object = field(repr=False, default=None)
    raw: dict = field(repr=False, default=None)
    diagnostics: list = field(default_factory=list)


def build_mesh3d(document, component: str | None = None) -> Mesh3DResult:
    """Mesh a ``3d`` component of boxes and slab layers through meshloom (stage 5; experimental).

    ``document`` is a format 0.3 document (a dict, or a ``simcase.Document``) with a version 1
    geometry block and an optional ``mesh`` block: ``element_size`` (the size of regions that give
    none), ``element_count_limit`` (default 600000; checked against the estimate
    T = 6.3 sum(V_r / h_r^3) before meshing, and passed to meshloom as its point cap) and
    ``controls`` (``element_size`` on a region selection)."""
    return _build(document, component, through_meshloom=False)


def _build(document, component=None, *, through_meshloom: bool = False) -> Mesh3DResult:
    """``build_mesh3d``; ``through_meshloom`` (tests only) sends a lone slab ``layers`` feature through
    meshloom instead of refusing it for the extrude route."""
    data = getattr(document, "data", document)
    model = parse(data)
    comp = _pick(model, component)
    opts = _mesh_options(data, comp)
    cx = _evaluate(comp, through_meshloom=through_meshloom)
    if all(c.void for c in cx.cells):
        raise GeometryError(f"component {comp.name!r} has nothing to mesh: every cell is void (material null)",
                            path=f"geometry.components.{comp.name}")
    _check_rounding(cx, comp)
    ho = _handoff(cx, comp, opts)
    from physmat.units import Diagnostic
    low, high = ho.estimate * 4e-4, ho.estimate * 6e-4
    info = Diagnostic("I-MESH-ESTIMATE", f"geometry.components.{comp.name}",
                      f"about {ho.estimate:.0f} tetrahedra from the element sizes (T = 6.3 sum(V/h^3)); meshing takes "
                      f"about {low:.3g}-{high:.3g} s at 0.4-0.6 ms per tetrahedron")
    if ho.estimate > opts["element_count_limit"]:
        raise GeometryError(f"component {comp.name!r}: about {ho.estimate:.0f} tetrahedra from the element sizes "
                            f"(T = 6.3 sum(V/h^3)); the limit is {opts['element_count_limit']} "
                            "(mesh.element_count_limit)", path="mesh.element_count_limit", code="E-MESH-ESTIMATE")
    result = _mesh(cx, comp, ho)
    result.diagnostics.append(info)
    return result


def _mesh(cx: Complex3D, comp: Component, ho: _Handoff) -> Mesh3DResult:
    import numpy as np
    import meshloom
    from galerkin.mesh3d import Mesh3D

    points = np.array([[_metres(c) for c in p] for p in ho.points], dtype=np.float64)
    tags = [f"f{i}" for i in range(len(ho.facets))]
    try:
        raw = meshloom.generate3d(points, ho.facets, h=ho.h, region_points=ho.region_points, facet_tags=tags,
                                  max_points=ho.max_points)
    except (meshloom.KernelUnavailable,) as exc:
        raise Mesh3DError(f"component {comp.name!r}: {exc}", cause=exc) from exc
    except ValueError as exc:
        raise _meshloom_error(cx, comp, ho, points, exc) from exc
    names = list(raw["region_names"])
    regions = np.asarray(raw["regions"], dtype=np.int64)
    tets = np.asarray(raw["tetrahedra"], dtype=np.int64)
    nodes = np.asarray(raw["nodes"], dtype=np.float64)
    facet_faces = [np.zeros((0, 3), dtype=np.int64) for _ in ho.facets]
    for t, faces in raw["boundary_faces"].items():
        facet_faces[int(t[1:])] = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    interfaces = {}
    plane_facets: dict = {}
    for fi, face_index in enumerate(ho.face_of_facet):
        f = cx.faces[face_index]
        key = (SLOPED, None) if f.axis == SLOPED else (f.axis, _metres(f.coord))
        plane_facets.setdefault(key, []).append(fi)
    interior: dict = {fi: [] for fi in range(len(ho.facets))}
    for (ia, ib), faces in raw["interfaces"].items():
        faces = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
        na, nb = names[ia], names[ib]
        key = tuple(sorted((na, nb)))
        interfaces[key] = faces if key == (na, nb) else faces[:, [0, 2, 1]]
        for face in faces:
            fi = _facet_of(cx, ho, plane_facets, nodes[face])
            interior[fi].append(face)
    for fi, faces in interior.items():
        if faces:
            facet_faces[fi] = np.concatenate([facet_faces[fi], np.array(faces, dtype=np.int64).reshape(-1, 3)])
    tagged: dict = {}
    for t, faces in raw["boundary_faces"].items():
        f = cx.faces[ho.face_of_facet[int(t[1:])]]
        tagged.setdefault(f.tag, []).append(np.asarray(faces, dtype=np.int64).reshape(-1, 3))
    tagged = {t: np.concatenate(v) for t, v in sorted(tagged.items())}
    provenance: dict = {}
    for fi, face_index in enumerate(ho.face_of_facet):
        for name in cx.faces[face_index].provenance:
            provenance.setdefault(name, []).append(facet_faces[fi])
    provenance = {n: np.concatenate(v) for n, v in sorted(provenance.items())}
    mesh = Mesh3D(nodes, tets, regions=regions, region_names=names, tagged_faces=tagged, interfaces=interfaces)
    mesh.provenance_faces = provenance
    selections, selection_nodes = _mesh_selections(cx, ho, mesh, facet_faces)
    return Mesh3DResult(mesh, cx, provenance, selections, selection_nodes, facet_faces, list(ho.face_of_facet),
                        ho.estimate, ho, raw)


def _facet_of(cx: Complex3D, ho: _Handoff, plane_facets: dict, xyz) -> int:
    """The facet an interior mesh face lies in: the facet of its axis-aligned plane (exact equality of
    the doubles) whose polygon holds the face's centroid (exact)."""
    for a in range(3):
        if xyz[0][a] == xyz[1][a] == xyz[2][a]:
            cands = plane_facets.get((a, float(xyz[0][a])), [])
            if len(cands) == 1:
                return cands[0]
            cen = [sum(Fraction(float(xyz[i][b])) for i in range(3)) / 3 for b in range(3)]
            u, v = [b for b in range(3) if b != a]
            for fi in cands:
                loops = cx.faces[ho.face_of_facet[fi]].loops
                if _inside_loops(cen[u], cen[v], [[(Fraction(_metres(p[u])), Fraction(_metres(p[v]))) for p in lp]
                                                  for lp in loops]):
                    return fi
    # a sloped facet: the vertical quad whose base segment (rounded) is nearest the face's centroid
    cen = [sum(float(xyz[i][b]) for i in range(3)) / 3 for b in range(3)]
    best = None
    for fi in plane_facets.get((SLOPED, None), []):
        (xa, ya, za), (xb, yb, _), (_, _, zb), _ = cx.faces[ho.face_of_facet[fi]].loops[0]
        ax, ay, bx, by = _metres(xa), _metres(ya), _metres(xb), _metres(yb)
        z0, z1 = sorted((_metres(za), _metres(zb)))
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = ((cen[0] - ax) * dx + (cen[1] - ay) * dy) / L2
        if not (-1e-9 <= t <= 1 + 1e-9 and z0 <= cen[2] <= z1):
            continue
        dist = abs((cen[0] - ax) * dy - (cen[1] - ay) * dx) / math.sqrt(L2)
        if best is None or dist < best[0]:
            best = (dist, fi, math.sqrt(L2))
    if best is not None and best[0] <= 1e-9 * best[2]:
        return best[1]
    raise GeometryError("internal: an interface face of the mesh lies in no hand-off facet")


def _inside_loops(x, y, loops) -> bool:
    inside = False
    for lp in loops:
        n = len(lp)
        for i in range(n):
            (x0, y0), (x1, y1) = lp[i], lp[(i + 1) % n]
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                inside = not inside
    return inside


def _mesh_selections(cx: Complex3D, ho: _Handoff, mesh, facet_faces):
    import numpy as np
    facets_of_face: dict = {}
    for fi, face_index in enumerate(ho.face_of_facet):
        facets_of_face.setdefault(face_index, []).append(fi)
    sel, nodes = {}, {}
    cell_of_tet = None
    for name, (kind, chosen) in cx.selections.items():
        if kind == "boundary":
            parts = [facet_faces[fi] for i in sorted(chosen) for fi in facets_of_face.get(i, [])]
            faces = np.concatenate(parts) if parts else np.zeros((0, 3), dtype=np.int64)
            sel[name] = ("boundary", faces)
            nodes[name] = np.unique(faces)
        else:
            if cell_of_tet is None:
                cell_of_tet = _locate_tets(cx, mesh)
            tets = np.flatnonzero(np.isin(cell_of_tet, sorted(chosen)))
            sel[name] = ("region", tets)
            nodes[name] = np.unique(mesh.tets[tets])
    return sel, nodes


def _locate_tets(cx: Complex3D, mesh):
    """The complex cell of every tetrahedron, from its centroid: slab by the rounded levels, fine
    cell by the grid of rounded vertex coordinates."""
    import numpy as np
    if not cx._rectilinear:
        return _locate_tets_in_cells(cx, mesh)
    xs, ys = _grid_lines(cx)
    grid = _grid_cells(cx, xs, ys)
    cen = mesh.nodes[mesh.tets].mean(axis=1)
    xi = np.searchsorted([_metres(x) for x in xs], cen[:, 0]) - 1
    yi = np.searchsorted([_metres(y) for y in ys], cen[:, 1]) - 1
    zi = np.searchsorted([_metres(z) for z in cx.levels], cen[:, 2]) - 1
    at = {(c.fine, c.slab): c.index for c in cx.cells}
    return np.array([at[(grid[i][j], s)] for i, j, s in zip(xi.tolist(), yi.tolist(), zi.tolist())],
                    dtype=np.int64)


def _locate_tets_in_cells(cx: Complex3D, mesh):
    """``_locate_tets`` for footprints with sloped curves: the fine cell of each centroid by an
    even-odd test against every fine cell's rounded loops."""
    import numpy as np
    rc = cx._plan
    V = _plan_vertices(rc)
    cen = mesh.nodes[mesh.tets].mean(axis=1)
    fine = np.full(len(cen), -1, dtype=np.int64)
    X, Y = cen[:, 0], cen[:, 1]
    for c in rc.cells:
        inside = np.zeros(len(cen), dtype=bool)
        for lp in _cell_loops(rc, V, c.index):
            pts = [(_metres(p[0]), _metres(p[1])) for p in lp]
            for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
                if y0 == y1:
                    continue
                crosses = (y0 > Y) != (y1 > Y)
                inside ^= crosses & (X < x0 + (Y - y0) * (x1 - x0) / (y1 - y0))
        fine[inside & (fine < 0)] = c.index
    if (fine < 0).any():
        raise GeometryError("internal: a tetrahedron's centroid lies in no fine cell")
    zi = np.searchsorted([_metres(z) for z in cx.levels], cen[:, 2]) - 1
    at = {(c.fine, c.slab): c.index for c in cx.cells}
    return np.array([at[(f, s)] for f, s in zip(fine.tolist(), zi.tolist())], dtype=np.int64)


def _grid_cells(cx: Complex3D, xs, ys) -> list:
    """The fine cell of every grid rectangle between consecutive vertex x and y values (None outside
    the domain). Walking up each column from below, a rectangle belongs to the cell below it unless
    a fine curve separates them; then it belongs to that curve's upper side."""
    rc = cx._plan
    V = _plan_vertices(rc)
    cover: dict = {}
    for k in rc.curves:
        (xa, ya), (xb, yb) = V[k.a], V[k.b]
        if ya != yb:
            continue
        above = k.left if xa < xb else k.right
        lo, hi = sorted((xa, xb))
        for i in range(bisect.bisect_left(xs, lo), bisect.bisect_left(xs, hi)):
            cover[(i, ya)] = above
    grid = []
    for i in range(len(xs) - 1):
        col, cell = [], None
        for j in range(len(ys) - 1):
            if (i, ys[j]) in cover:
                cell = cover[(i, ys[j])]
            col.append(cell)
        grid.append(col)
    return grid


_FACET_RE = re.compile(r"facets? (\d+)")
_POINTS_RE = re.compile(r"points (\d+) and (\d+)")
_COORD_RE = re.compile(r"\[\s*([-+0-9.eE]+),\s*([-+0-9.eE]+),\s*([-+0-9.eE]+)\s*\]")


def _meshloom_error(cx: Complex3D, comp: Component, ho: _Handoff, points, exc) -> Mesh3DError:
    """A meshloom error, re-reported with the features of the facets involved (facet -> provenance)."""
    text = str(exc)
    facets: set = set()
    witness = getattr(exc, "witness", None)
    if isinstance(witness, dict):
        for key in ("facet", "facets"):
            v = witness.get(key)
            if isinstance(v, int):
                facets.add(v)
            elif isinstance(v, (list, tuple)):
                facets.update(int(x) for x in v if isinstance(x, int))
    facets.update(int(m) for m in _FACET_RE.findall(text))
    vertices = {int(v) for m in _POINTS_RE.findall(text) for v in m if int(v) < len(ho.points)}
    if vertices:
        facets.update(fi for fi, f in enumerate(ho.facets) if vertices & {v for lp in f for v in lp})
    for m in _COORD_RE.findall(text):
        p = [float(c) for c in m]
        for fi, f in enumerate(ho.facets):
            box = points[[v for lp in f for v in lp]]
            span = float((box.max(axis=0) - box.min(axis=0)).max()) or 1.0
            if all(box[:, a].min() - 1e-9 * span <= p[a] <= box[:, a].max() + 1e-9 * span for a in range(3)):
                facets.add(fi)
    facets = sorted(fi for fi in facets if 0 <= fi < len(ho.facets))
    prov = sorted({n for fi in facets for n in cx.faces[ho.face_of_facet[fi]].provenance})
    features = sorted({n.split(".", 1)[0] for n in prov})
    where = f"; the facets involved carry {', '.join(prov)} (features {', '.join(features)})" if prov else ""
    return Mesh3DError(f"component {comp.name!r}: meshloom {type(exc).__name__}: {text}{where}", cause=exc,
                       facets=facets, provenance=prov)
