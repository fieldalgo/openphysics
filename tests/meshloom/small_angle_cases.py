# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Synthetic closed triangle surfaces with small angles, for the free triangle-surface path.

Not a test module. Each case is the unit cube, or a wedge, given as triangles (one facet each
when meshed). Each case carries one small feature, at one of three strengths:

- ``fan``: an angle ``theta`` (degrees) at the centre of the top face, between two triangle
  edges in that face; the second edge ends on the side x = 1, close to the corner (1, 0, 1).
- ``needle``: a needle triangle in the top face whose smallest angle is ``alpha`` (degrees).
- ``fold``: the top face folded along its diagonal to a dihedral angle of 180 - ``delta``
  degrees, not exactly 180.
- ``close``: a top-face vertex at distance ``d`` times the cube's diagonal from the
  opposite edge of its triangle.
- ``wedge``: a triangular prism whose dihedral angle at one edge is ``phi`` degrees.

The strengths and the sizes were fixed with the completion criteria of the small-angle work,
before any of these surfaces was meshed. ``CASES`` lists (name, family, strength) and
``SIZES`` the mesh sizes h. ``surface(family, strength)`` returns ``(points, triangles)``:
float64 points and int triangles wound outward.
"""

import math

import numpy as np

STRENGTHS = {
    "fan": (1.0, 0.1, 0.01),
    "needle": (1.0, 0.1, 0.01),
    "fold": (0.1, 0.01, 0.001),
    "close": (1e-4, 1e-6, 1e-8),
    "wedge": (30.0, 10.0, 3.0),
}
CASES = [(f"{family}-{s:g}", family, s) for family, levels in STRENGTHS.items() for s in levels]
SIZES = (0.25, 0.1)

# unit-cube corners: index = x + 2 y + 4 z
_CUBE = np.array([(x, y, z) for z in (0.0, 1.0) for y in (0.0, 1.0) for x in (0.0, 1.0)])
# the five faces other than the top (z = 1), as quads wound outward
_BOTTOM, _FRONT, _BACK, _LEFT, _RIGHT = (0, 2, 3, 1), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)


def _quads(quads):
    return [t for a, b, c, d in quads for t in ((a, b, c), (a, c, d))]


def _fan(theta):
    """Top face (corners 4, 5, 7, 6) fanned from its centre O; Q on the edge 5–7 makes the
    angle theta at O with the ray to corner 5."""
    t = math.radians(theta)
    yq = 0.5 + 0.5 * math.tan(t - math.pi / 4)
    pts = np.vstack([_CUBE, [(0.5, 0.5, 1.0), (1.0, yq, 1.0)]])
    o, q = 8, 9
    top = [(o, 4, 5), (o, 5, q), (o, q, 7), (o, 7, 6), (o, 6, 4)]
    right = [(1, 3, 7), (1, 7, q), (1, q, 5)]  # x = 1 with Q on its top edge
    return pts, _quads([_BOTTOM, _FRONT, _BACK, _LEFT]) + right + top


def _needle(alpha):
    """A needle A, B, C in the top face, smallest angle alpha at A; the rest of the face in
    four convex pieces around it."""
    w = 2 * 0.8 * math.tan(math.radians(alpha) / 2)
    pts = np.vstack([_CUBE, [(0.1, 0.5, 1.0), (0.9, 0.5 - w / 2, 1.0), (0.9, 0.5 + w / 2, 1.0)]])
    a, b, c = 8, 9, 10
    top = [(a, b, c), (4, 5, b), (4, b, a), (5, 7, c), (5, c, b), (7, 6, a), (7, a, c), (6, 4, a)]
    return pts, _quads([_BOTTOM, _FRONT, _BACK, _LEFT, _RIGHT]) + top


def _fold(delta):
    """Corner 6 = (0, 1, 1) raised so that the top triangles 4-5-7 and 4-7-6 meet at
    180 - delta degrees along the diagonal 4-7."""
    pts = _CUBE.copy()
    pts[6, 2] = 1.0 + math.tan(math.radians(delta)) / math.sqrt(2.0)
    top = [(4, 5, 7), (4, 7, 6)]
    return pts, _quads([_BOTTOM, _FRONT, _BACK, _LEFT, _RIGHT]) + top


def _close(d):
    """A top-face vertex P at distance d * sqrt(3) from the edge 4-5 (y = 0, z = 1); the top
    face is fanned from P."""
    pts = np.vstack([_CUBE, [(0.5, d * math.sqrt(3.0), 1.0)]])
    p = 8
    top = [(p, 4, 5), (p, 5, 7), (p, 7, 6), (p, 6, 4)]
    return pts, _quads([_BOTTOM, _FRONT, _BACK, _LEFT, _RIGHT]) + top


def _wedge(phi):
    """The prism over the triangle (0, 0), (1, 0), (cos phi, sin phi) in x, z, for y in
    [0, 1]: dihedral angle phi at the edge x = z = 0."""
    c, s = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    xz = [(0.0, 0.0), (1.0, 0.0), (c, s)]
    pts = np.array([(x, y, z) for y in (0.0, 1.0) for x, z in xz])  # 0-2 at y = 0, 3-5 at y = 1
    tri = [(0, 1, 2), (3, 5, 4)] + _quads([(0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)])
    return pts, tri


_FAMILIES = {"fan": _fan, "needle": _needle, "fold": _fold, "close": _close, "wedge": _wedge}


def surface(family, strength):
    pts, tri = _FAMILIES[family](strength)
    return np.asarray(pts, dtype=float), np.asarray(tri, dtype=np.int64)
