# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Simple polygon conductors and local dielectric regions, in metres."""
from dataclasses import dataclass
from functools import cached_property
from numbers import Real

import numpy as np
from shapely import distance, points
from shapely.geometry import Polygon, LineString, box
from shapely.ops import unary_union

__all__ = ['PolygonTrace', 'DielectricRegion']


def _vertices(value):
    try:
        rows = tuple(tuple(row) for row in value)
    except TypeError as exc:
        raise ValueError('vertices must be an array of coordinate pairs') from exc
    if len(rows) < 3 or any(len(row) != 2 for row in rows):
        raise ValueError('a polygon needs at least three coordinate pairs')
    if any(isinstance(v, (bool, np.bool_)) or not isinstance(v, Real) or not np.isfinite(v)
           for row in rows for v in row):
        raise ValueError('polygon coordinates must be finite real numbers')
    rows = tuple(tuple(float(v) for v in row) for row in rows)
    if len(set(rows)) != len(rows):
        raise ValueError('polygon vertices must be distinct; omit the closing vertex')
    shape = Polygon(rows)
    if not shape.is_valid or not shape.area > 0:
        raise ValueError('polygon must be simple with positive area')
    return rows


def _name(name):
    if not isinstance(name, str) or not name.strip():
        raise ValueError('a polygon needs a nonempty name')


class _PolygonGeometry:
    @cached_property
    def _shape(self):
        return Polygon(self.vertices)

    @property
    def xmin(self):
        return self._shape.bounds[0]

    @property
    def xmax(self):
        return self._shape.bounds[2]

    @property
    def y(self):
        return self._shape.bounds[1]

    @property
    def y1(self):
        return self._shape.bounds[3]

    @property
    def thickness(self):
        return self.y1-self.y

    @property
    def minimum_dimension(self):
        """Conservative vertex/edge clearance, not a curvature validity bound."""
        return self._shape.minimum_clearance

    def corners(self):
        return np.array(self.vertices, dtype=float)

    def distance(self, x, y):
        x, y = np.broadcast_arrays(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
        return distance(self._shape, points(x, y))


@dataclass(frozen=True)
class PolygonTrace(_PolygonGeometry):
    """A finite simple conductor polygon; clockwise and concave loops are allowed.

    The closing vertex is implicit. Holes, self intersections, touching or
    overlapping conductors are not allowed. Coordinates use the section frame.
    """
    name: str
    vertices: tuple
    ground: bool = False

    def __post_init__(self):
        _name(self.name)
        if type(self.ground) is not bool:
            raise ValueError('ground must be boolean')
        object.__setattr__(self, 'vertices', _vertices(self.vertices))


@dataclass(frozen=True)
class DielectricRegion(_PolygonGeometry):
    """Local dielectric overriding the underlying layers, with metal taking priority.

    Regions may meet at edges but their interiors must not overlap. A region may
    cross layer boundaries or touch the box. It must leave positive dielectric
    area after conductor interiors are removed. No implicit clipping to the box.
    """
    name: str
    vertices: tuple
    eps_r: float = 1.0
    tan_delta: float = 0.0

    def __post_init__(self):
        _name(self.name)
        object.__setattr__(self, 'vertices', _vertices(self.vertices))
        for name, lower in (('eps_r', 1), ('tan_delta', 0)):
            v = getattr(self, name)
            if isinstance(v, (bool, np.bool_)) or not isinstance(v, Real) or not np.isfinite(v) or v < lower:
                raise ValueError(f'{name} must be finite and >= {lower}')


def trace_shape(trace):
    if isinstance(trace, PolygonTrace):
        return trace._shape
    return (LineString(trace.corners()) if trace.thickness == 0 else Polygon(trace.corners()))


def check_regions(section):
    bounds = box(-section.width/2, 0, section.width/2, section.height)
    metal = unary_union([trace_shape(t) for t in section.traces if t.thickness > 0])
    for i, region in enumerate(section.dielectric_regions):
        if not bounds.covers(region._shape):
            raise ValueError(f'dielectric region {region.name!r} must lie inside the box')
        if region._shape.difference(metal).area <= 0:
            raise ValueError(f'dielectric region {region.name!r} has no dielectric area')
        for other in section.dielectric_regions[:i]:
            if region._shape.intersection(other._shape).area > 0:
                raise ValueError('dielectric region interiors must not overlap')


def _pieces(shape):
    if shape.is_empty:
        return
    if shape.geom_type == 'Polygon':
        yield shape
    elif hasattr(shape, 'geoms'):
        for part in shape.geoms:
            yield from _pieces(part)


def _loop(ring, thin):
    # Constrain zero-thickness strips as collinear vertices on a slab boundary.
    vertices = list(ring.coords)[:-1]
    out = []
    for a, b in zip(vertices, vertices[1:]+vertices[:1]):
        out.append(a)
        if a[1] == b[1]:
            xs = {x for t in thin if t.y == a[1] for x in (t.x0, t.x1)
                  if min(a[0], b[0]) < x < max(a[0], b[0])}
            out.extend((x, a[1]) for x in sorted(xs, reverse=b[0] < a[0]))
    return out


def polygon_domain(section, far_size, *, solids=None, bounds=None, metal_size=None,
                   dielectric_interfaces=True):
    """Partition exact polygons into disjoint, conforming meshine regions.

    With solids supplied, include their interiors and padded vacuum for the
    volume-current solve. Material labels are shared with dielectric extraction.
    """
    from meshine import Domain
    domain = Domain(size=far_size)
    volume = solids is not None
    solids = section.traces if solids is None else solids
    thin = [t for t in solids if t.thickness == 0]
    metal = unary_union([trace_shape(t) for t in solids if t.thickness > 0])
    half, height = section.width/2, section.height
    interior = box(-half, 0, half, height)
    envelope = interior if bounds is None else box(*bounds)
    masks = unary_union([r._shape for r in section.dielectric_regions])
    cuts = sorted({envelope.bounds[1], envelope.bounds[3], *(t.y for t in thin)})

    def add(name, shape, size=None):
        # A thin conductor must be an internal constrained segment even when it
        # crosses a local material. Intersect every piece with the same slabs.
        for y0, y1 in zip(cuts[:-1], cuts[1:]):
            slab = box(envelope.bounds[0], y0, envelope.bounds[2], y1)
            for part in _pieces(shape.intersection(slab)):
                domain.add_region(name, _loop(part.exterior, thin),
                                  holes=[_loop(ring, thin) for ring in part.interiors], size=size)

    labels = {r.name: f'__sipi_dielectric_{i}' if volume else r.name
              for i,r in enumerate(section.materials)}
    if dielectric_interfaces:
        for layer, y0, y1 in zip(section.layers, section.interfaces()[:-1], section.interfaces()[1:]):
            add(labels[layer.name], box(-half, y0, half, y1).difference(masks).difference(metal))
        for region in section.dielectric_regions:
            add(labels[region.name], region._shape.difference(metal))
        if volume:
            add('__sipi_vacuum', envelope.difference(interior).difference(metal))
    else:
        add('__sipi_vacuum', envelope.difference(metal))
    if volume:
        for i, trace in enumerate(solids):
            add(f'__sipi_metal_{i}', trace_shape(trace), metal_size)
    return domain
