# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""PCB cross-section templates with rectangular or tapered signal conductors. All lengths are in metres."""

from __future__ import annotations

import math
from numbers import Real

from .crosssection import CrossSection, Layer, Trace

__all__ = ['microstrip', 'stripline', 'coupled_microstrip', 'grounded_coplanar', 'coated_microstrip']


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
