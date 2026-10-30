# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""PCB cross-section templates with rectangular or tapered signal conductors. All lengths are in metres."""

from __future__ import annotations

import math
from numbers import Real

from .crosssection import CrossSection, Layer, Trace

__all__ = ['microstrip', 'stripline', 'coupled_microstrip', 'grounded_coplanar', 'coated_microstrip',
           'offset_stripline', 'coupled_stripline', 'broadside_stripline', 'with_surface_mask']


def _positive(name, value, *, zero=False):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite real number')
    if value < 0 or (value == 0 and not zero):
        raise ValueError(f'{name} must be {">= 0" if zero else "> 0"}')
    return float(value)


def _surface(width, substrate_height, eps_r, thickness, tan_delta, air_height, box_width):
    w = _positive('width', width)
    h = _positive('substrate_height', substrate_height)
    t = _positive('thickness', thickness, zero=True)
    air = 10*h + t if air_height is None else _positive('air_height', air_height)
    box = max(20*h, 4*w) if box_width is None else _positive('box_width', box_width)
    layers = [Layer('substrate', h, _positive('eps_r', eps_r),
                    _positive('tan_delta', tan_delta, zero=True)), Layer('air', air)]
    return w, h, t, box, layers


def microstrip(*, width, substrate_height, eps_r, thickness=0.0, tan_delta=0.0,
               air_height=None, box_width=None, top_width=None):
    """One surface trace above a grounded substrate; open top and side walls."""
    w, h, t, box, layers = _surface(width, substrate_height, eps_r, thickness,
                                   tan_delta, air_height, box_width)
    return CrossSection(layers, [Trace('signal', 0.0, w, h, t, top_width=top_width)], box)


def stripline(*, width, plane_spacing, eps_r, thickness=0.0, tan_delta=0.0,
              box_width=None, top_width=None):
    """Trace centred between two ground planes in a homogeneous dielectric.

    plane_spacing is the full distance between the planes, including copper.
    """
    w = _positive('width', width)
    b = _positive('plane_spacing', plane_spacing)
    t = _positive('thickness', thickness, zero=True)
    box = max(12*b, 4*w) if box_width is None else _positive('box_width', box_width)
    return CrossSection([Layer('dielectric', b, _positive('eps_r', eps_r),
                               _positive('tan_delta', tan_delta, zero=True))],
                        [Trace('signal', 0.0, w, (b-t)/2, t, top_width=top_width)], box, top='ground')


def coupled_microstrip(*, width, gap, substrate_height, eps_r, thickness=0.0,
                       tan_delta=0.0, air_height=None, box_width=None, top_width=None):
    """Equal-width surface pair with edge-to-edge gap and a bottom ground."""
    gap = _positive('gap', gap)
    w, h, t, box, layers = _surface(width, substrate_height, eps_r, thickness,
                                   tan_delta, air_height, box_width)
    if box_width is None:
        box = max(box, 4*(2*w+gap))
    offset = (w+gap)/2
    return CrossSection(layers, [Trace('positive', -offset, w, h, t, top_width=top_width),
                                Trace('negative', offset, w, h, t, top_width=top_width)], box)


def grounded_coplanar(*, width, gap, ground_width, substrate_height, eps_r,
                     thickness=0.0, tan_delta=0.0, air_height=None, box_width=None, top_width=None):
    """Surface signal with finite coplanar grounds and a bottom ground plane.

    gap is the edge-to-edge signal/ground spacing on each side. ground_width
    is finite and must be enlarged separately to check ground truncation.
    """
    gap = _positive('gap', gap)
    gw = _positive('ground_width', ground_width)
    w, h, t, box, layers = _surface(width, substrate_height, eps_r, thickness,
                                   tan_delta, air_height, box_width)
    if box_width is None:
        box = max(box, w+2*gap+2*gw+4*h)
    offset = (w+gw)/2+gap
    return CrossSection(layers, [Trace('signal', 0.0, w, h, t, top_width=top_width),
                                Trace('ground_left', -offset, gw, h, t, ground=True),
                                Trace('ground_right', offset, gw, h, t, ground=True)], box)


def coated_microstrip(*, width, substrate_height, eps_r, coating_height,
                      coating_eps_r, thickness=0.0, tan_delta=0.0,
                      coating_tan_delta=0.0, air_height=None, box_width=None,
                      top_width=None):
    """Surface trace in a planar dielectric coating, with air above it.

    coating_height is measured from the substrate surface and must exceed the
    conductor thickness. Thus the coating fills both sides and the space above
    the trace up to a flat surface. It is not a conformal or meniscus mask model.
    """
    w, h, t, box, layers = _surface(width, substrate_height, eps_r, thickness,
                                   tan_delta, air_height, box_width)
    height = _positive('coating_height', coating_height)
    if height <= t:
        raise ValueError('coating_height must exceed the conductor thickness')
    coating = Layer('coating', height, _positive('coating_eps_r', coating_eps_r),
                    _positive('coating_tan_delta', coating_tan_delta, zero=True))
    return CrossSection([layers[0], coating, layers[1]],
                        [Trace('signal', 0.0, w, h, t, top_width=top_width)], box)


def offset_stripline(*, width, plane_spacing, trace_height, eps_r, thickness=0.0,
                     tan_delta=0.0, box_width=None, top_width=None):
    """One trace between ground planes, with explicit bottom-face height."""
    base = stripline(width=width, plane_spacing=plane_spacing, eps_r=eps_r,
                    thickness=thickness, tan_delta=tan_delta, box_width=box_width,
                    top_width=top_width)
    y = _positive('trace_height', trace_height)
    return CrossSection(base.layers, [Trace('signal', 0, width, y, thickness, top_width=top_width)],
                        base.width, top='ground')


def coupled_stripline(*, width, gap, plane_spacing, eps_r, thickness=0.0,
                     tan_delta=0.0, box_width=None, top_width=None, trace_height=None):
    """Edge-coupled equal-width pair between two planes; gap is at the bottom face."""
    gap = _positive('gap', gap)
    base = stripline(width=width, plane_spacing=plane_spacing, eps_r=eps_r,
                    thickness=thickness, tan_delta=tan_delta, box_width=box_width,
                    top_width=top_width)
    y = base.traces[0].y if trace_height is None else _positive('trace_height', trace_height)
    offset = (width+gap)/2
    box_width = max(base.width, 4*(2*width+gap)) if box_width is None else base.width
    return CrossSection(base.layers,
        [Trace('positive', -offset, width, y, thickness, top_width=top_width),
         Trace('negative', offset, width, y, thickness, top_width=top_width)], box_width, top='ground')


def broadside_stripline(*, width, gap, plane_spacing, eps_r, thickness,
                       offset=0.0, tan_delta=0.0, box_width=None):
    """Vertical pair centred between planes; gap is metal-to-metal, offset is signed.

    The lower/upper traces are named positive/negative. Rectangular conductors
    have equal positive thickness. The entire box has one homogeneous dielectric.
    """
    gap = _positive('gap', gap)
    t = _positive('thickness', thickness)
    if isinstance(offset, bool) or not isinstance(offset, Real) or not math.isfinite(offset):
        raise ValueError('offset must be a finite real number')
    base = stripline(width=width, plane_spacing=plane_spacing, eps_r=eps_r,
                    thickness=t, tan_delta=tan_delta, box_width=box_width)
    box_width = max(base.width, 4*(width+abs(offset))) if box_width is None else base.width
    return CrossSection(base.layers,
        [Trace('positive', -offset/2, width, plane_spacing/2-gap/2-t, t),
         Trace('negative', offset/2, width, plane_spacing/2+gap/2, t)], box_width, top='ground')


def with_surface_mask(section, *, thickness, eps_r, tan_delta=0.0, gap_fill_height=0.0):
    """Add a polygonal mask to coplanar finite rectangular/tapered surface traces.

    Offset top and side faces by thickness, with straight mitred corners (mitre
    limit 5). Clip only below the common bottom face. Optional gap_fill_height
    fills the whole box width from that face upwards. No curvature, meniscus or
    manufacturing prediction is implied. Regions are named mask, or mask_1,...
    ordered left to right when disconnected. Ground traces are coated too.
    Existing local regions are preserved and must not overlap the new mask.
    """
    from shapely.geometry import box
    from shapely.ops import unary_union
    from .polygons import DielectricRegion, trace_shape, _pieces
    if not isinstance(section, CrossSection):
        raise TypeError('section must be a CrossSection')
    t = _positive('thickness', thickness)
    fill = _positive('gap_fill_height', gap_fill_height, zero=True)
    if any(not isinstance(trace, Trace) or trace.thickness <= 0 for trace in section.traces):
        raise ValueError('surface mask requires finite rectangular or tapered traces')
    y = section.traces[0].y
    if any(trace.y != y for trace in section.traces):
        raise ValueError('surface mask traces must share one bottom face height')
    if y not in section.interfaces():
        raise ValueError('surface mask requires a layer interface at the trace bottom')
    half = section.width/2
    coatings = [trace_shape(trace).buffer(t, join_style='mitre', mitre_limit=5)
                for trace in section.traces]
    if fill > 0:
        coatings.append(box(-half, y, half, y+fill))
    shape = unary_union(coatings)
    # Retain the entire lateral/top extent so the section validator rejects
    # out-of-box coatings instead of silently cutting their physical thickness.
    xmin, _, xmax, ymax = shape.bounds
    shape = shape.intersection(box(xmin, y, xmax, ymax))
    parts = sorted(_pieces(shape), key=lambda p:p.bounds)
    if any(part.interiors for part in parts):
        raise ValueError('mask topology contains holes; supply explicit simple regions')
    regions = [DielectricRegion('mask' if len(parts)==1 else f'mask_{i+1}',
                                list(part.exterior.coords)[:-1], eps_r, tan_delta)
               for i,part in enumerate(parts)]
    return CrossSection(section.layers, section.traces, section.width,
                        bottom=section.bottom, top=section.top, sides=section.sides,
                        dielectric_regions=(*section.dielectric_regions, *regions))
