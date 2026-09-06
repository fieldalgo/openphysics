# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Document geometry -> meshine Domain.

Shapes are booleans on top of each other ("later wins"), clipped to the
domain box; the background fills the remainder. shapely does the polygon
arithmetic, the result goes to meshine as polygons with holes. A circle that
nothing overlaps is passed as a true meshine.Circle so its nodes stay on the
exact circle.
"""

from __future__ import annotations

import numpy as np
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

from meshine import Circle, Domain, box_sides

from .schema import Document

MIN_AREA = 1e-12


def shape_polygon(s: dict) -> Polygon:
    t = s["type"]
    if t == "rect":
        return box(s["x"], s["y"], s["x"] + s["w"], s["y"] + s["h"])
    if t == "circle":
        return Point(s["cx"], s["cy"]).buffer(s["r"], quad_segs=32)
    if t == "polygon":
        return Polygon([tuple(p) for p in s["points"]])
    raise ValueError(t)


def resolve_regions(doc: Document) -> list[tuple[str, str, object, float | None, dict | None]]:
    """[(region_name, material, shapely geometry, mesh_size, exact_circle_spec)] after boolean resolution."""
    dom = doc.domain
    clip = box(dom["xmin"], dom["ymin"], dom["xmax"], dom["ymax"])
    shapes = doc.shapes
    polys = [shape_polygon(s).intersection(clip) for s in shapes]
    out = []
    for i, s in enumerate(shapes):
        later = [polys[j] for j in range(i + 1, len(shapes))]
        geom = polys[i].difference(unary_union(later)) if later else polys[i]
        if geom.area < MIN_AREA:
            continue
        exact = None
        if s["type"] == "circle" and abs(geom.area - polys[i].area) < 1e-12 * max(1.0, polys[i].area) \
                and clip.contains(shape_polygon(s)):
            exact = {"center": (s["cx"], s["cy"]), "r": s["r"]}
        out.append((s["name"], s["material"], geom, s.get("mesh_size"), exact))
    background = clip.difference(unary_union(polys)) if polys else clip
    if background.area > MIN_AREA:
        out.append(("background", doc["geometry"]["background"]["material"], background,
                    doc["geometry"]["background"].get("mesh_size"), None))
    return out


def _rings(poly: Polygon):
    outer = list(poly.exterior.coords)[:-1]
    holes = [list(r.coords)[:-1] for r in poly.interiors]
    return outer, holes


def build_domain(doc: Document) -> tuple[Domain, callable, dict[str, str]]:
    """meshine Domain, boundary namer, and {region name: material name}."""
    mesh_cfg = doc["mesh"]
    d = Domain(size=mesh_cfg["size"])
    dom = doc.domain
    materials: dict[str, str] = {}
    circle_lookup: dict[tuple[float, float, float], Circle] = {}

    def circle_for(cx, cy, r):
        key = (round(cx, 12), round(cy, 12), round(r, 12))
        if key not in circle_lookup:
            circle_lookup[key] = Circle((cx, cy), r, n=max(16, int(2 * np.pi * r / (mesh_cfg["size"] / 2))))
        return circle_lookup[key]

    regions = resolve_regions(doc)
    exact_circles = {(rn): ex for rn, _m, _g, _s, ex in regions if ex}

    for name, material, geom, size, exact in regions:
        materials[name] = material
        if exact:
            d.add_region(name, circle_for(*exact["center"], exact["r"]), size=size)
            continue
        parts = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
        for part in parts:
            if part.area < MIN_AREA:
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
    return d, box_sides(dom["xmin"], dom["xmax"], dom["ymin"], dom["ymax"]), materials
