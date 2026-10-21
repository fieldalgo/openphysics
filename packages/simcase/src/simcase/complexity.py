# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""How complex a region document's geometry is, read from the raw JSON.

Validating a heat region document resolves the shapes' booleans ("later wins") with
shapely, and that cost grows with the boundaries that cross each other, even where later
shapes cover the crossings and nothing of them reaches the mesh. Two polygons whose
edges cross 64,455 times, hidden under four covering rects behind 58 small ones, make
``Document.from_dict`` alone take 18 to 32 s (two measurements on Linux, Python 3.12,
shapely 2.2.0). ``region_complexity`` reads the raw document, before
``Document.from_dict``, so a caller that accepts documents from others can refuse such a
document before paying for it: it counts shapes, circles and polygon points first and,
only when those are within the caller's maxima, the boundary crossings. See
docs/packages/simcase/thermal_regions2d.md, "Mesh limits for callers".
"""
from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np
import shapely

from .mesh_limits import _limit

#: Quarter-circle segments of a circle's polygon: the 128-gon simcase.geometry.shape_polygon
#: builds for every circle that is not meshed as an exact meshine Circle.
CIRCLE_QUAD_SEGS = 32


class RegionComplexity(NamedTuple):
    """Counts of a raw region document's ``geometry.shapes``.

    ``shapes`` is the length of the list; ``circles`` the entries of type circle;
    ``polygon_points`` the summed lengths of the polygons' ``points`` lists;
    ``boundary_crossings`` the pairs of boundary segments from different shapes that
    properly cross (their interiors meet in exactly one point), or None when a maximum
    given to ``region_complexity`` was exceeded and the crossings were not counted.
    """
    shapes: int
    circles: int
    polygon_points: int
    boundary_crossings: int | None


def region_complexity(data, *, max_shapes: int | None = None, max_circles: int | None = None,
                      max_polygon_points: int | None = None) -> RegionComplexity:
    """Count the geometry of a raw region document (a dict as JSON gives it).

    Shapes, circles and polygon points are counted first, from the lengths alone. When any
    of them exceeds the maximum given for it, ``boundary_crossings`` is None and no geometry
    is built, so the cost stays linear in the document. Otherwise every shape's boundary is
    cut into segments (a rect's 4 edges, a circle's 128-gon, a polygon's edges, closing edge
    included) and the pairs of segments from different shapes that properly cross are
    counted with one shapely STRtree query: two segments cross when their interiors meet in
    exactly one point; touching at an end point, a T-junction and a collinear overlap do
    not count. Crossings inside one shape (a self-intersecting polygon) do not count either.
    Each pair is decided by GEOS's robust orientation predicates on the coordinates as
    given, not by shapely's ``crosses``: that runs GEOS's relate, which rounds the
    intersection point it computes and can call a crossing a touch where an end point lies
    within rounding of the other segment. In exact arithmetic the two are the same test.

    Never raises on malformed data: a non-dict document or geometry, or ``shapes`` that is
    not a list, gives zeros; an entry that is not a dict, has an unknown type, a ``points``
    that is not a list of at least three [x, y] pairs, or a coordinate that is not a finite
    number (or a rect corner or circle extent that overflows) is counted (as a shape, and
    its points as points) but contributes no segment; ``Document.from_dict`` raises on such
    entries later (a ``DocumentError``, or shapely's ``GEOSException`` for a circle whose
    extent overflows). A well-formed shape with a coordinate GEOS cannot decide exactly
    (``EXACT_RANGE``) is not measured: each of its segments counts as crossing every segment
    of every other shape, an upper bound, so an extreme scale can neither hide crossings nor
    make the count fail.

    The coordinates are the document's own, the numbers ``Document.from_dict`` resolves; a
    run resolves the shapes again on the micrometre copy it meshes
    (``runner.micrometre_document``). A decimal unit factor can re-round exact contacts
    there, a touch becoming a crossing or the reverse, so the copy's crossings can differ
    from this count by such contacts. Measured: equal on 22 valid millimetre documents;
    in other units valid documents differ too (an 8 x 8 grid of touching rects written in
    metres counts 4 here and 0 on its micrometre copy).

    A maximum that is not a positive int or None is a ValueError.
    """
    maxima = (_limit('max_shapes', max_shapes), _limit('max_circles', max_circles),
              _limit('max_polygon_points', max_polygon_points))
    shapes = _shape_list(data)
    entries = [s for s in shapes if isinstance(s, dict)]
    circles = sum(1 for s in entries if s.get('type') == 'circle')
    points = sum(len(s['points']) for s in entries if s.get('type') == 'polygon' and isinstance(s.get('points'), list))
    counts = (len(shapes), circles, points)
    if any(limit is not None and count > limit for count, limit in zip(counts, maxima)):
        return RegionComplexity(*counts, None)
    return RegionComplexity(*counts, _boundary_crossings(shapes))


def _shape_list(data) -> list:
    geometry = data.get('geometry') if isinstance(data, dict) else None
    shapes = geometry.get('shapes') if isinstance(geometry, dict) else None
    return shapes if isinstance(shapes, list) else []


def _number(value) -> float | None:
    """A finite float, or None for anything else (a bool, a string, an int too large for a
    float, an infinity or a NaN)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        value = float(value)
    except OverflowError:
        return None
    return value if math.isfinite(value) else None


def _numbers(shape: dict, keys) -> list[float] | None:
    values = [_number(shape.get(key)) for key in keys]
    return None if any(v is None for v in values) else values


#: The coordinates whose crossings GEOS decides exactly: zero, or a magnitude from 2**-300
#: to 2**300 (about 5e-91 to 2e90). Its exact predicates multiply coordinate differences,
#: which overflow from about 1e100 on (it warns, or refuses with "encountered NaN/Inf
#: numbers") and underflow below about 1e-150. Every document at a physical scale is far
#: inside this range; it bounds double arithmetic, not lengths.
EXACT_RANGE = (2.0 ** -300, 2.0 ** 300)


def _in_range(values) -> bool:
    magnitude = np.abs(np.asarray(values, dtype=float))
    low, high = EXACT_RANGE
    return bool(np.all((magnitude == 0) | ((magnitude >= low) & (magnitude <= high))))


def _boundary_segments(shapes: list) -> tuple[np.ndarray, np.ndarray, dict[int, int]]:
    """(segments (E, 2, 2), owner (E,), unmeasured): the boundary segments of every
    well-formed shape whose coordinates are within ``EXACT_RANGE``, the index in ``shapes``
    of the shape each segment belongs to, and {index: segment count} of the well-formed
    shapes outside that range."""
    rings: list[tuple[int, np.ndarray]] = []
    circles: list[tuple[int, list[float]]] = []
    unmeasured: dict[int, int] = {}
    for k, s in enumerate(shapes):
        if not isinstance(s, dict):
            continue
        kind = s.get('type')
        if kind == 'rect':
            values = _numbers(s, ('x', 'y', 'w', 'h'))
            if values is None:
                continue
            x, y, w, h = values
            ring = np.array([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], dtype=float)
        elif kind == 'polygon':
            points = s.get('points')
            if not isinstance(points, list) or len(points) < 3:
                continue
            pairs = [p if isinstance(p, (list, tuple)) and len(p) == 2 else (None, None) for p in points]
            coords = [_number(v) for pair in pairs for v in pair]
            if any(v is None for v in coords):
                continue
            ring = np.array(coords, dtype=float).reshape(-1, 2)
        elif kind == 'circle':
            values = _numbers(s, ('cx', 'cy', 'r'))
            if values is None or not values[2] > 0:
                continue
            cx, cy, r = values
            extent = [cx, cy, r, abs(cx) + r, abs(cy) + r]
            if not np.isfinite(extent).all():
                continue
            if _in_range(extent):
                circles.append((k, values))
            else:
                unmeasured[k] = 4 * CIRCLE_QUAD_SEGS
            continue
        else:
            continue
        if not np.isfinite(ring).all():        # a rect corner that overflowed
            continue
        if _in_range(ring):
            rings.append((k, ring))
        else:
            unmeasured[k] = len(ring)
    if circles:
        centres = shapely.points([(cx, cy) for _k, (cx, cy, _r) in circles])
        discs = shapely.buffer(centres, [r for _k, (_cx, _cy, r) in circles], quad_segs=CIRCLE_QUAD_SEGS)
        for (k, _values), disc in zip(circles, discs):
            ring = shapely.get_coordinates(shapely.get_exterior_ring(disc))[:-1]
            if _in_range(ring):
                rings.append((k, ring))
            else:
                unmeasured[k] = 4 * CIRCLE_QUAD_SEGS
    segments = [np.stack([ring, np.roll(ring, -1, axis=0)], axis=1) for _k, ring in rings]
    owners = [np.full(len(ring), k, dtype=np.int64) for k, ring in rings]
    if not segments:
        return np.empty((0, 2, 2)), np.empty(0, dtype=np.int64), unmeasured
    return np.concatenate(segments), np.concatenate(owners), unmeasured


def _boundary_crossings(shapes: list) -> int:
    segments, owner, unmeasured = _boundary_segments(shapes)
    return _exact_crossings(segments, owner) + _bound_for_unmeasured(owner, unmeasured)


def _bound_for_unmeasured(owner: np.ndarray, unmeasured: dict[int, int]) -> int:
    """Every pair of segments from different shapes with at least one segment of a shape
    outside ``EXACT_RANGE``: an upper bound for their crossings, counted without geometry."""
    if not unmeasured:
        return 0
    measured = [int(n) for n in np.bincount(owner) if n] if len(owner) else []

    def pairs(sizes):                     # pairs of segments from different shapes
        total = sum(sizes)
        return (total * total - sum(n * n for n in sizes)) // 2
    return pairs(measured + list(unmeasured.values())) - pairs(measured)


def _exact_crossings(segments: np.ndarray, owner: np.ndarray) -> int:
    if len(segments) < 2:
        return 0
    lines = shapely.linestrings(segments)
    left, right = shapely.STRtree(lines).query(lines)          # pairs whose boxes meet
    keep = (left < right) & (owner[left] != owner[right])
    left, right = left[keep], right[keep]
    shapely.prepare(lines)
    meet = shapely.intersects(lines[left], lines[right])
    left, right = left[meet], right[meet]
    # Two straight segments that meet cross (their interiors meet in exactly one point)
    # exactly when no end point of either lies on the other: an end point on the other
    # segment is a touch or a T-junction, and a collinear overlap always puts one. Each
    # test is a GEOS orientation predicate (a floating-point filter, then double-double
    # arithmetic) on the coordinates as given; shapely's crosses would run a full relate,
    # about three times slower, which rounds the intersection point it computes and so can
    # call a crossing a touch where an end point lies within rounding of the other segment.
    start, end = shapely.points(segments[:, 0]), shapely.points(segments[:, 1])
    touch = (shapely.intersects(lines[left], start[right]) | shapely.intersects(lines[left], end[right])
             | shapely.intersects(lines[right], start[left]) | shapely.intersects(lines[right], end[left]))
    return int(np.count_nonzero(~touch))
