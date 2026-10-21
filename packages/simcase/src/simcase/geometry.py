# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Document geometry -> meshine Domain.

Shapes are booleans on top of each other ("later wins"), clipped to the
domain box; the background fills the remainder. shapely does the polygon
arithmetic, the result goes to meshine as polygons with holes. A circle that no
later shape overlaps and no other boundary touches is passed as a true
meshine.Circle so its nodes stay on the exact circle (see _isolated_circle).
"""

from __future__ import annotations

import math

import numpy as np
import shapely
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

from meshine import Circle, Domain, box_sides

from .mesh_limits import MeshLimitError
from .schema import Document, DocumentError

#: A sliver smaller than this fraction of the domain is not a region. Dimensionless
#: on purpose: an absolute area is a statement about the unit the document is written
#: in, and the same 220 nm film is 0.22 in micrometres and 2.2e-13 in metres. The
#: absolute form silently dropped every region of a small device written in a large
#: unit, which the units block made legal for the first time.
AREA_EPS = 1e-12


def _min_area(doc: Document) -> float:
    """The area below which a region is a sliver, in the document's own units."""
    dom = doc.domain
    return AREA_EPS * (dom["xmax"] - dom["xmin"]) * (dom["ymax"] - dom["ymin"])


def shape_polygon(s: dict) -> Polygon:
    t = s["type"]
    if t == "rect":
        return box(s["x"], s["y"], s["x"] + s["w"], s["y"] + s["h"])
    if t == "circle":
        return Point(s["cx"], s["cy"]).buffer(s["r"], quad_segs=32)
    if t == "polygon":
        return Polygon([tuple(p) for p in s["points"]])
    raise ValueError(t)


def _polygonal(geom):
    """The polygon parts of a boolean result, as a Polygon or MultiPolygon.

    Clipping or subtracting can leave zero-area line or point pieces next to the
    polygons (a shape touching the domain or another shape from outside), giving a
    GeometryCollection. Those pieces cannot be meshed and have no boundary ring.
    """
    def polygons(g):
        if g.geom_type == "Polygon":
            return [] if g.is_empty else [g]
        if hasattr(g, "geoms"):
            return [p for part in g.geoms for p in polygons(part)]
        return []
    parts = polygons(geom)
    if not parts:
        return Polygon()
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


#: Relative clearance between an exact circle and any other boundary.
CIRCLE_CLEARANCE = 1e-6


def _isolated_circle(s: dict, index: int, polys: list, clip) -> bool:
    """True when no other boundary meets or comes close to the circle line.

    The exact meshine.Circle is an n-gon with vertices on the circle, while every
    other region describes the same arc with shapely's 128-gon. The two only
    coincide when the arc is a whole hole of a surrounding region, which
    build_domain maps back to the same Circle. If a domain side or another shape's
    edge touches or crosses the circle, the two polylines cross, and refinement
    keeps splitting crossing segments without end. Such a circle is meshed as a
    polygon like every other shape.

    A ring of another shape comes too close when its nearest point (on an edge, not
    only at a vertex) is within the clearance outside the circle line and its farthest
    vertex is not more than the clearance inside it. All rings are measured in one
    vectorised shapely call and all their vertices in another, instead of a Python
    loop over every vertex.
    """
    centre, r = Point(s["cx"], s["cy"]), s["r"]
    lo, hi = r * (1 - CIRCLE_CLEARANCE), r * (1 + CIRCLE_CLEARANCE)
    if not clip.contains(centre) or clip.exterior.distance(centre) <= hi:
        return False
    others = [other for j, other in enumerate(polys) if j != index and not other.is_empty]
    if not others:
        return True
    rings = shapely.get_rings(shapely.get_parts(others))     # exteriors and interiors
    near = shapely.distance(rings, centre)
    vertices, ring = shapely.get_coordinates(rings, return_index=True)
    far = np.full(len(rings), -np.inf)
    np.maximum.at(far, ring, shapely.distance(centre, shapely.points(vertices)))
    return not np.any((near <= hi) & (far >= lo))


def resolve_regions(doc: Document) -> list[tuple[str, str, object, float | None, dict | None]]:
    """[(region_name, material, shapely geometry, mesh_size, exact_circle_spec)] after boolean resolution."""
    dom = doc.domain
    clip = box(dom["xmin"], dom["ymin"], dom["xmax"], dom["ymax"])
    shapes = doc.shapes
    polys = [_polygonal(shape_polygon(s).intersection(clip)) for s in shapes]
    min_area = _min_area(doc)
    out = []
    for i, s in enumerate(shapes):
        later = [polys[j] for j in range(i + 1, len(shapes))]
        geom = _polygonal(polys[i].difference(unary_union(later))) if later else polys[i]
        if geom.area < min_area:
            if polys[i].area < min_area:
                # It was already a sliver before any boolean: nothing occluded it, so this is
                # the document's own scale. Dropping it silently leaves a named material out of
                # a run that then converges on the wrong geometry.
                doc.notes.append(
                    f"geometry.shapes: {s['name']!r} covers {polys[i].area:g} square {doc.length_unit}, under "
                    f"{AREA_EPS:g} of the domain, so it was dropped and contributes no material. "
                    f"Check its size against the units this document declares.")
            continue
        exact = None
        if s["type"] == "circle" and abs(geom.area - polys[i].area) < AREA_EPS * polys[i].area \
                and _isolated_circle(s, i, polys, clip):
            exact = {"center": (s["cx"], s["cy"]), "r": s["r"]}
        out.append((s["name"], s["material"], geom, s.get("mesh_size"), exact))
    background = _polygonal(clip.difference(unary_union(polys))) if polys else clip
    if background.area > min_area:
        out.append(("background", doc["geometry"]["background"]["material"], background,
                    doc["geometry"]["background"].get("mesh_size"), None))
    if not out:
        raise DocumentError(
            f"geometry resolved to no regions: all {len(shapes)} shape(s) and the background are "
            f"smaller than {min_area:g} square {doc.length_unit}, which is {AREA_EPS:g} of the domain. Either the "
            f"shapes lie outside geometry.domain, or they are far smaller than the domain they sit in.")
    return out


def _rings(poly: Polygon):
    outer = list(poly.exterior.coords)[:-1]
    holes = [list(r.coords)[:-1] for r in poly.interiors]
    return outer, holes


def build_domain(doc: Document) -> tuple[Domain, callable, dict[str, str]]:
    """meshine Domain, boundary namer, and {region name: material name}."""
    return _domain_from_regions(doc)[:3]


def _circle_vertex_count(r: float, size: float) -> float:
    """The vertex count an exact Circle of radius r gets at global mesh size ``size``, before
    ``int`` and the floor of 16: 2 pi r / (size / 2), or infinity where size / 2 is zero."""
    half = size / 2
    return math.inf if half == 0 else 2 * np.pi * r / half


def _domain_from_regions(doc: Document, regions=None, max_input_vertices: int | None = None
                         ) -> tuple[Domain, callable, dict[str, str], int]:
    """build_domain, plus the number of loop vertices it passes to meshine.

    ``regions`` is ``resolve_regions(doc)``; None resolves them here, after the Domain is
    made, the order build_domain has always had. The count is the sum of the lengths of
    the loops given to ``Domain.add_region``, outer rings and holes: a shape inside the
    background counts once as its own ring and once as the background's hole, and every
    ``Circle`` occurrence counts as its ``n``. It is exact, and known before
    ``Domain.build``, which only reads the queued loops.

    With ``max_input_vertices`` (simcase.mesh_limits), a count over it raises
    MeshLimitError, and so does an exact circle whose own count alone is over it, before
    the Circle is made (a tiny global mesh.size would make it as large as memory allows,
    or overflow). With None nothing is checked and the build is exactly build_domain's.
    """
    mesh_cfg = doc["mesh"]
    d = Domain(size=mesh_cfg["size"])
    dom = doc.domain
    materials: dict[str, str] = {}
    circle_lookup: dict[tuple[float, float, float], Circle] = {}
    count = 0

    def circle_for(cx, cy, r):
        key = (round(cx, 12), round(cy, 12), round(r, 12))
        if key not in circle_lookup:
            # int(x) > limit exactly when x >= limit + 1; a 16-gon over a smaller limit is
            # left to the exact total below
            estimate = None if max_input_vertices is None else _circle_vertex_count(r, mesh_cfg["size"])
            if estimate is not None and estimate >= max_input_vertices + 1:
                unit = doc.length_unit
                raise MeshLimitError(
                    "input_vertices", max_input_vertices, None,
                    f"the isolated circle at ({cx:g}, {cy:g}) {unit} of radius {r:g} {unit} alone needs "
                    f"4*pi*r/mesh.size = {estimate:.4g} loop vertices at mesh.size {mesh_cfg['size']:g} {unit}")
            circle_lookup[key] = Circle((cx, cy), r, n=max(16, int(2 * np.pi * r / (mesh_cfg["size"] / 2))))
        return circle_lookup[key]

    if regions is None:
        regions = resolve_regions(doc)
    min_area = _min_area(doc)
    exact_circles = {(rn): ex for rn, _m, _g, _s, ex in regions if ex}

    for name, material, geom, size, exact in regions:
        materials[name] = material
        if exact:
            circle = circle_for(*exact["center"], exact["r"])
            d.add_region(name, circle, size=size)
            count += circle.n
            continue
        parts = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
        for part in parts:
            if part.area < min_area:
                continue
            outer, holes = _rings(part)
            # holes that are exact circles of other shapes must use the same Circle object
            hole_objs = []
            for h in holes:
                hp = Polygon(h)
                match = None
                for rn, ex in exact_circles.items():
                    c = Point(*ex["center"])
                    if abs(hp.area - np.pi * ex["r"] ** 2) < 0.05 * np.pi * ex["r"] ** 2 and hp.contains(c):
                        match = circle_for(*ex["center"], ex["r"])
                        break
                hole_objs.append(match if match is not None else h)
            d.add_region(name, outer, holes=hole_objs, size=size)
            count += len(outer) + sum(h.n if isinstance(h, Circle) else len(h) for h in hole_objs)
    if max_input_vertices is not None and count > max_input_vertices:
        raise MeshLimitError("input_vertices", max_input_vertices, count)
    return d, box_sides(dom["xmin"], dom["xmax"], dom["ymin"], dom["ymax"]), materials, count
