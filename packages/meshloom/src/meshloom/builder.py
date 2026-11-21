# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Curved primitives for ``meshloom.generate3d``: spheres and z-axis cylinder vias.

Each builder returns a dict of keyword arguments for ``generate3d``: ``points``,
``facets``, ``facet_tags``, ``region_points`` and ``locked_facets``. The curved surfaces
are triangulated here, at a surface edge of about ``SURFACE_EDGE * h``. Their vertices
lie on the surface to rounding: a point is ``c + R q / |q|``, computed with +, -, *, /
and sqrt only, which IEEE 754 rounds correctly, so the points are the same on every
platform. Their triangles are listed in ``locked_facets``, so the mesher adds no point
on them (a chord midpoint would lie off the surface). The planar facets (box faces, the
via's end disks) stay open to refinement.

The triangulations are strictly Delaunay on their surfaces. The sphere is a class-I
geodesic subdivision of the icosahedron. The cylinder has rings rotated by half a
step, so no four points form a rectangle. Each triangle's diametral ball therefore
holds no other point of the surface, and boundary recovery finds every curved triangle
without adding a point. See the M7 design note.
"""

from __future__ import annotations

import math

import numpy as np

#: target surface edge over h for the curved surfaces (surface edges of about h, as the
#: baseline's MeshSizeMax = h gives its surface mesher)
SURFACE_EDGE = 1.0

_PHI = (1.0 + math.sqrt(5.0)) / 2.0
_ICO = [(0.0, 1.0, _PHI), (0.0, -1.0, _PHI), (0.0, 1.0, -_PHI), (0.0, -1.0, -_PHI),
        (1.0, _PHI, 0.0), (-1.0, _PHI, 0.0), (1.0, -_PHI, 0.0), (-1.0, -_PHI, 0.0),
        (_PHI, 0.0, 1.0), (-_PHI, 0.0, 1.0), (_PHI, 0.0, -1.0), (-_PHI, 0.0, -1.0)]
_ICO_EDGE = 2.0 / math.sqrt(_PHI * _PHI + 1.0)  # edge of the unit icosahedron, 1.0515


def _ico_faces():
    """The 20 faces of the icosahedron, as vertex index triples (edges have length 2)."""
    v = np.array(_ICO)
    faces = []
    for i in range(12):
        for j in range(i + 1, 12):
            if abs(np.sum((v[i] - v[j]) ** 2) - 4.0) > 1e-9:
                continue
            for k in range(j + 1, 12):
                if abs(np.sum((v[i] - v[k]) ** 2) - 4.0) < 1e-9 and abs(np.sum((v[j] - v[k]) ** 2) - 4.0) < 1e-9:
                    faces.append((i, j, k))
    assert len(faces) == 20
    return faces


def _check_size(h):
    if not (isinstance(h, (int, float, np.integer, np.floating)) and not isinstance(h, bool)
            and math.isfinite(h) and h > 0):
        raise ValueError(f"h must be a finite number > 0, got {h!r}")
    return float(h)


class _Points:
    """Points with bitwise identity by key: a point is computed once from its key."""

    def __init__(self):
        self.xyz: list[tuple[float, float, float]] = []
        self.index: dict = {}

    def add(self, key, make):
        i = self.index.get(key)
        if i is None:
            i = self.index[key] = len(self.xyz)
            self.xyz.append(make())
        return i


def _on_sphere(q, center, radius):
    # c + R q / |q|, component by component in a fixed order (no fused multiply-add)
    n = math.sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2])
    return tuple(center[a] + radius * (q[a] / n) for a in range(3))


def sphere_surface(pts: _Points, center, radius, h, tag):
    """Triangles (oriented outward) of a geodesic sphere; returns (triangles, frequency)."""
    n = max(1, math.ceil(_ICO_EDGE * radius / (SURFACE_EDGE * h)))
    tris = []
    for a, b, c in _ico_faces():

        def point(u, v, a=a, b=b, c=c):
            # barycentric weights n - u - v, u, v on the face's vertices a, b, c
            weights = {}
            for vert, w in ((a, n - u - v), (b, u), (c, v)):
                if w:
                    weights[vert] = weights.get(vert, 0) + w
            key = (tag, tuple(sorted(weights.items())))

            def make():
                q = [0.0, 0.0, 0.0]
                for vert, w in sorted(weights.items()):  # one fixed order for every face
                    for ax in range(3):
                        q[ax] += w * _ICO[vert][ax]
                return _on_sphere([x / n for x in q], center, radius)
            return pts.add(key, make)

        for u in range(n):
            for v in range(n - u):
                tris.append((point(u, v), point(u + 1, v), point(u, v + 1)))
                if u + v < n - 1:
                    tris.append((point(u + 1, v), point(u + 1, v + 1), point(u, v + 1)))
    return _orient_out(pts, tris, center), n


def _orient_out(pts, tris, center):
    out = []
    for t in tris:
        x = [np.array(pts.xyz[i]) for i in t]
        nrm = np.cross(x[1] - x[0], x[2] - x[0])
        out.append(t if np.dot(nrm, x[0] + x[1] + x[2] - 3 * np.array(center)) > 0 else (t[0], t[2], t[1]))
    return out


def _circle(k, half):
    """Unit directions of a circle: an octagon with edges split in k, centrally projected;
    ``half`` takes the midpoints of those pieces instead (a ring rotated by half a step)."""
    s = math.sqrt(0.5)
    octa = [(1.0, 0.0), (s, s), (0.0, 1.0), (-s, s), (-1.0, 0.0), (-s, -s), (0.0, -1.0), (s, -s)]
    out = []
    for e in range(8):
        (x0, y0), (x1, y1) = octa[e], octa[(e + 1) % 8]
        for j in range(k):
            t2 = 2 * j + (1 if half else 0)  # position in halves of a piece
            x = ((2 * k - t2) * x0 + t2 * x1) / (2 * k)
            y = ((2 * k - t2) * y0 + t2 * y1) / (2 * k)
            r = math.sqrt(x * x + y * y)
            out.append((x / r, y / r))
    return out


def via_in_slab(h, *, slab=((-1.0, -1.0, 0.0), (1.0, 1.0, 1.0)), radius=0.3, axis=(0.0, 0.0),
                names=("slab", "via")):
    """A z-axis cylinder via of ``radius`` at ``axis`` through the box ``slab``: two
    regions, the via's side locked (C4: r = 0.3 through [-1,1]^2 x [0,1])."""
    h = _check_size(h)
    (x0, y0, z0), (x1, y1, z1) = slab
    ax, ay = axis
    if not (x0 < ax - radius and ax + radius < x1 and y0 < ay - radius and ay + radius < y1 and z0 < z1):
        raise ValueError("the via must lie inside the slab")
    k = max(1, math.ceil(2 * math.pi * radius / (8 * SURFACE_EDGE * h)))
    m = 8 * k
    chord = 2 * math.pi * radius / m
    layers = max(1, round((z1 - z0) / (math.sqrt(3.0) / 2.0 * chord)))
    pts = _Points()
    rings = []
    for j in range(layers + 1):
        z = z0 + (z1 - z0) * j / layers if j < layers else z1
        dirs = _circle(k, j % 2 == 1)
        rings.append([pts.add(("ring", j, i), lambda d=d, z=z: (ax + radius * d[0], ay + radius * d[1], z))
                      for i, d in enumerate(dirs)])
    side = []
    for j in range(layers):
        lo, hi = rings[j], rings[j + 1]
        # parameters in halves of a step: even rings at 2i, odd rings at 2i + 1
        plo = [2 * i + (j % 2) for i in range(m)]
        phi = [2 * i + ((j + 1) % 2) for i in range(m)]
        for i in range(m):
            a, b = lo[i], lo[(i + 1) % m]
            if phi[i] > plo[i]:   # hi[i] lies between lo[i] and lo[i+1]
                side += [(a, b, hi[i]), (hi[i], b, hi[(i + 1) % m])]
            else:                 # hi[i+1] lies between lo[i] and lo[i+1]
                side += [(a, b, hi[(i + 1) % m]), (hi[i], a, hi[(i + 1) % m])]
    corners = {}
    for cx in (0, 1):
        for cy in (0, 1):
            for cz in (0, 1):
                corners[(cx, cy, cz)] = pts.add(("box", cx, cy, cz), lambda c=(cx, cy, cz): (
                    (x0, x1)[c[0]], (y0, y1)[c[1]], (z0, z1)[c[2]]))
    c = corners
    facets, tags, locked = [], [], []
    facets.append([[c[0, 0, 0], c[0, 1, 0], c[1, 1, 0], c[1, 0, 0]], rings[0][::-1]])
    tags.append("bottom")
    facets.append([[c[0, 0, 1], c[1, 0, 1], c[1, 1, 1], c[0, 1, 1]], rings[-1]])
    tags.append("top")
    facets += [[[c[0, 0, 0], c[1, 0, 0], c[1, 0, 1], c[0, 0, 1]]], [[c[1, 0, 0], c[1, 1, 0], c[1, 1, 1], c[1, 0, 1]]],
               [[c[1, 1, 0], c[0, 1, 0], c[0, 1, 1], c[1, 1, 1]]], [[c[0, 1, 0], c[0, 0, 0], c[0, 0, 1], c[0, 1, 1]]]]
    tags += ["y0", "x1", "y1", "x0"]
    facets.append([rings[0][::-1]])
    tags.append("via_bottom")
    facets.append([rings[-1]])
    tags.append("via_top")
    for t in side:
        locked.append(len(facets))
        facets.append([list(t)])
        tags.append("via_side")
    zc = 0.5 * (z0 + z1)
    seeds = [((ax, ay, zc), names[1]), ((x0 + 0.5 * (ax - radius - x0), y0 + 0.5 * (ay - radius - y0), zc), names[0])]
    return {"points": np.array(pts.xyz), "facets": facets, "facet_tags": tags, "region_points": seeds,
            "locked_facets": locked}


def _add_sphere(pts, facets, tags, locked, center, radius, h, tag):
    tris, _ = sphere_surface(pts, center, radius, h, tag)
    for t in tris:
        locked.append(len(facets))
        facets.append([list(t)])
        tags.append(tag)


def sphere(h, *, center=(0.0, 0.0, 0.0), radius=1.0, name="ball"):
    """A ball (C1: the unit sphere): one region, its surface locked."""
    h = _check_size(h)
    pts, facets, tags, locked = _Points(), [], [], []
    _add_sphere(pts, facets, tags, locked, center, radius, h, "sphere")
    return {"points": np.array(pts.xyz), "facets": facets, "facet_tags": tags,
            "region_points": [(tuple(center), name)], "locked_facets": locked}


def nested_spheres(h, *, center=(0.0, 0.0, 0.0), radii=(0.5, 0.75, 1.0), names=(None, "inner", "outer")):
    """Concentric spheres (C11: a = 0.5, b = 0.75, c = 1). ``names`` names the ball inside
    the first sphere and each shell; None leaves it a hole (C11's inner conductor)."""
    h = _check_size(h)
    if list(radii) != sorted(radii) or len(set(radii)) != len(radii) or radii[0] <= 0:
        raise ValueError("radii must be positive and increasing")
    if len(names) != len(radii):
        raise ValueError("one name per sphere: the ball inside the first, then each shell")
    pts, facets, tags, locked = _Points(), [], [], []
    for i, r in enumerate(radii):
        _add_sphere(pts, facets, tags, locked, center, r, h, f"sphere{i}")
    seeds = [((center[0], center[1], center[2]), names[0])]
    for i in range(1, len(radii)):
        rm = 0.5 * (radii[i - 1] + radii[i])
        seeds.append(((center[0] + rm, center[1], center[2]), names[i]))
    return {"points": np.array(pts.xyz), "facets": facets, "facet_tags": tags, "region_points": seeds,
            "locked_facets": locked}


def sphere_in_box(h, *, box=((-1.0, -1.0, -1.0), (1.0, 1.0, 1.0)), center=(0.0, 0.0, 0.0), radius=0.5,
                  names=("box", "ball")):
    """A ball inside a box (C5: r = 0.5 inside [-1,1]^3): two regions, the sphere locked."""
    h = _check_size(h)
    (x0, y0, z0), (x1, y1, z1) = box
    if not all(lo < center[a] - radius and center[a] + radius < hi
               for a, (lo, hi) in enumerate(((x0, x1), (y0, y1), (z0, z1)))):
        raise ValueError("the sphere must lie inside the box")
    pts, facets, tags, locked = _Points(), [], [], []
    c = {}
    for cx in (0, 1):
        for cy in (0, 1):
            for cz in (0, 1):
                c[(cx, cy, cz)] = pts.add(("box", cx, cy, cz), lambda k=(cx, cy, cz): (
                    (x0, x1)[k[0]], (y0, y1)[k[1]], (z0, z1)[k[2]]))
    for loop, tag in (([c[0, 0, 0], c[0, 1, 0], c[1, 1, 0], c[1, 0, 0]], "z0"),
                      ([c[0, 0, 1], c[1, 0, 1], c[1, 1, 1], c[0, 1, 1]], "z1"),
                      ([c[0, 0, 0], c[1, 0, 0], c[1, 0, 1], c[0, 0, 1]], "y0"),
                      ([c[1, 1, 0], c[0, 1, 0], c[0, 1, 1], c[1, 1, 1]], "y1"),
                      ([c[0, 1, 0], c[0, 0, 0], c[0, 0, 1], c[0, 1, 1]], "x0"),
                      ([c[1, 0, 0], c[1, 1, 0], c[1, 1, 1], c[1, 0, 1]], "x1")):
        facets.append([loop])
        tags.append(tag)
    _add_sphere(pts, facets, tags, locked, center, radius, h, "sphere")
    corner = (x0 + 0.5 * (center[0] - radius - x0), y0 + 0.5 * (center[1] - radius - y0),
              z0 + 0.5 * (center[2] - radius - z0))
    seeds = [(corner, names[0]), (tuple(center), names[1])]
    return {"points": np.array(pts.xyz), "facets": facets, "facet_tags": tags, "region_points": seeds,
            "locked_facets": locked}
