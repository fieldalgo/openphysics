# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Constrained Delaunay triangulation of planar facets (M4 of the pre-registered 3D
plan, the facet step behind V3), checked independently in Python ``Fraction``
arithmetic: the triangles cover the facet exactly (projected areas sum to the facet
area), keep every loop edge, wind like the outer loop, and every edge that is not a
loop edge is locally Delaunay in the facet's own metric, with ties broken by the
index-ordered perturbation. Facets lie on tilted planes (conformal and non-conformal
integer embeddings), axis-aligned planes and cocircular configurations.
"""

import itertools
import random
from fractions import Fraction

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from meshloom._core import predicate_signs, triangulate_facet  # noqa: E402

KEPT = {0: (1, 2), 1: (2, 0), 2: (0, 1)}


def embed(o, e1, e2, uv):
    return np.array([[o[k] + u * e1[k] + v * e2[k] for k in range(3)] for u, v in uv], dtype=float)


def frac(p):
    return [Fraction(x) for x in p]


def det(m):
    if len(m) == 1:
        return m[0][0]
    return sum((-1) ** j * m[0][j] * det([r[:j] + r[j + 1:] for r in m[1:]]) for j in range(len(m)) if m[0][j])


def area2(points, idx, axis):
    """Twice the signed projected area of the polygon idx (exact)."""
    i, j = KEPT[axis]
    q = [frac(points[k]) for k in idx]
    return sum(q[k][i] * q[(k + 1) % len(q)][j] - q[(k + 1) % len(q)][i] * q[k][j] for k in range(len(q)))


def in_circle(points, a, b, c, d):
    """d strictly inside the circle of a, b, c in the facet plane's own metric, ties
    broken by raising the lifted coordinate of the point with the largest index most
    (explicit perturbation of the lifted determinant, built from the definition)."""
    ids = [a, b, c, d]
    q = [frac(points[k]) for k in ids]
    # in-plane circle through a, b, c: centre on the plane, equidistant (3D metric)
    u = [x - y for x, y in zip(q[1], q[0])]
    v = [x - y for x, y in zip(q[2], q[0])]
    uu = sum(x * x for x in u)
    vv = sum(x * x for x in v)
    uv = sum(x * y for x, y in zip(u, v))
    den = 2 * (uu * vv - uv * uv)
    s = (vv * uu - uv * vv) / den
    t = (uu * vv - uv * uu) / den
    centre = [q[0][k] + s * u[k] + t * v[k] for k in range(3)]
    r2 = sum((q[0][k] - centre[k]) ** 2 for k in range(3))
    d2 = sum((q[3][k] - centre[k]) ** 2 for k in range(3))
    if d2 != r2:
        return d2 < r2
    # tie: in the plane's orthonormal frame the perturbed determinant is
    # det[s_k, t_k, |p_k|^2 + delta^(rank+1), 1]; any affine frame of the plane gives the
    # same sign up to the orientation of a, b, c, which is fixed counter-clockwise here
    n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
    w = [n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2], n[0] * u[1] - n[1] * u[0]]  # in-plane, normal to u
    coords = [[sum((p[k] - q[0][k]) * u[k] for k in range(3)), sum((p[k] - q[0][k]) * w[k] for k in range(3))]
              for p in q]
    # (u, w) is a scaled orthogonal frame with |u| != |w|: rescale w to the length of u
    scale = uu / sum(x * x for x in w)  # (|u| / |w|)^2
    rank = [sum(ids[m] > ids[k] for m in range(4)) for k in range(4)]
    lifted = [x * x / uu + y * y * scale / uu for x, y in coords]  # |p - a|^2 in the plane
    cof = [abs(det([coords[m] + [Fraction(1)] for m in range(4) if m != k])) for k in range(4)]
    delta = min(c for c in cof if c) / (2 * sum(cof) + 1) / (1 + max(lifted))
    rows = [coords[k] + [lifted[k] * uu + delta ** (rank[k] + 1), Fraction(1)] for k in range(4)]
    value = det(rows)
    orient = det([coords[m] + [Fraction(1)] for m in range(3)])
    return value * orient > 0


def check(points, loops, tris):
    tris = tris.tolist()
    # one orientation, the outer loop's, and no degenerate triangle
    axis = next(a for a in range(3) if area2(points, loops[0], a) != 0)
    outer = area2(points, loops[0], axis)
    for t in tris:
        a = area2(points, t, axis)
        assert a != 0 and (a > 0) == (outer > 0)
    # exact cover: the triangles' areas sum to the region's area
    region = abs(outer) - sum(abs(area2(points, h, axis)) for h in loops[1:])
    assert sum(abs(area2(points, t, axis)) for t in tris) == region
    # loop edges present once, other edges shared by two triangles
    cons = {frozenset((lp[k], lp[(k + 1) % len(lp)])) for lp in loops for k in range(len(lp))}
    uses = {}
    for t in tris:
        for k in range(3):
            uses.setdefault(frozenset((t[k], t[(k + 1) % 3])), []).append(t)
    for e in cons:
        assert len(uses.get(e, [])) == 1, f"loop edge {sorted(e)}"
    checked = 0
    for e, owners in uses.items():
        if e in cons:
            continue
        assert len(owners) == 2, f"edge {sorted(e)} used {len(owners)} times"
        t1, t2 = owners
        d = next(v for v in t2 if v not in e)
        a, b, c = t1 if outer > 0 else (t1[0], t1[2], t1[1])
        # make (a, b, c) counter-clockwise in the plane's orientation of the first loop
        assert not in_circle(points, a, b, c, d), f"edge {sorted(e)} is not locally Delaunay"
        checked += 1
    return checked


CONFORMAL = ((1.0, -2.0, 0.5), (1.0, 2.0, 2.0), (2.0, 1.0, -2.0))
AFFINE = ((0.25, 3.0, -1.0), (1.0, 0.0, 3.0), (0.0, 2.0, 1.0))
AXIS = ((0.0, 0.0, 1.5), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
CIRCLE = [(5, 0), (4, 3), (3, 4), (0, 5), (-3, 4), (-4, 3), (-5, 0), (-4, -3), (-3, -4), (0, -5), (3, -4), (4, -3)]


@pytest.mark.parametrize("frame", [CONFORMAL, AFFINE, AXIS], ids=["conformal", "affine", "axis"])
def test_square_with_a_hole(frame):
    uv = [(0, 0), (4, 0), (4, 4), (0, 4), (1, 1), (1, 3), (3, 3), (3, 1)]
    pts = embed(*frame, uv)
    loops = [[0, 1, 2, 3], [4, 5, 6, 7]]
    tris, _ = triangulate_facet(pts, loops)
    assert len(tris) == 8  # n + 2h - 2
    check(pts, loops, tris)
    # reversed loops give the same triangles, wound the other way
    rev, _ = triangulate_facet(pts, [lp[::-1] for lp in loops])
    assert {frozenset(t) for t in rev.tolist()} == {frozenset(t) for t in tris.tolist()}
    assert area2(pts, rev[0].tolist(), 0 if frame is not AXIS else 2) * area2(pts, tris[0].tolist(), 0 if frame is not AXIS else 2) < 0


def test_cocircular_polygon_uses_the_perturbation():
    pts = embed(*CONFORMAL, CIRCLE)  # 12 points on one circle in the tilted plane
    loop = list(range(12))
    tris, _ = triangulate_facet(pts, [loop])
    assert len(tris) == 10
    check(pts, [loop], tris)
    # the result depends on the indices, not on where the loop starts
    for start in (3, 7):
        again, _ = triangulate_facet(pts, [loop[start:] + loop[:start]])
        assert {frozenset(t) for t in again.tolist()} == {frozenset(t) for t in tris.tolist()}


def star(rng, n, radius_range, centre=(0, 0)):
    """A star-shaped polygon with n vertices, one per equal angular sector, so no edge
    spans more than two sectors and the polygon stays away from its centre."""
    angles = [360 * k // n + rng.randrange(max(1, 360 // n - 2)) for k in range(n)]
    out = []
    for deg in angles:
        r = rng.randint(*radius_range)
        # integer points near the ray keep the polygon star-shaped and exact
        a = deg * 3.141592653589793 / 180
        out.append((centre[0] + round(r * np.cos(a)), centre[1] + round(r * np.sin(a))))
    return out


@pytest.mark.parametrize("seed", range(30))
def test_random_star_polygons_with_holes(seed):
    rng = random.Random(seed)
    frame = [CONFORMAL, AFFINE, AXIS][seed % 3]
    outer = star(rng, rng.randint(10, 16), (60, 100))
    holes = [star(rng, rng.randint(3, 6), (8, 14), centre=c) for c in [(-25, 0), (25, 5)][: seed % 3]]
    uv = outer + [p for h in holes for p in h]
    if len(set(uv)) != len(uv):
        pytest.skip("rounded star points coincide")
    pts = embed(*frame, uv)
    loops, k = [list(range(len(outer)))], len(outer)
    for h in holes:
        loops.append(list(range(k, k + len(h))))
        k += len(h)
    tris, _ = triangulate_facet(pts, loops)
    assert len(tris) == len(uv) + 2 * len(holes) - 2
    check(pts, loops, tris)


@pytest.mark.parametrize("uv, loops, message", [
    ([(0, 0), (2, 0), (2, 2), (0, 2)], [[0, 2, 1, 3]], "intersect"),
    ([(0, 0), (4, 0), (4, 4), (0, 4), (0, 2), (1, 1), (1, 3)], [[0, 1, 2, 3], [4, 5, 6]], "intersect"),
    ([(0, 0), (1, 0), (2, 0)], [[0, 1, 2]], "collinear"),
    ([(0, 0), (1, 0), (1, 1)], [[0, 1, 2, 0]], "twice"),
    ([(0, 0), (1, 0), (1, 1)], [[0, 1, 5]], "does not exist"),
])
def test_invalid_loops_are_refused(uv, loops, message):
    pts = embed(*CONFORMAL, uv)
    with pytest.raises(ValueError, match=message):
        triangulate_facet(pts, loops)


def test_points_off_the_plane_are_refused():
    pts = embed(*CONFORMAL, [(0, 0), (4, 0), (4, 4), (0, 4)])
    pts[2, 2] = np.nextafter(pts[2, 2], np.inf)
    with pytest.raises(ValueError, match="plane"):
        triangulate_facet(pts, [[0, 1, 2, 3]])


def test_in_plane_predicates_match_fractions():
    rng = random.Random(41)
    cases, axes = [], []
    for _ in range(600):
        frame = rng.choice([CONFORMAL, AFFINE])
        uv = rng.sample(CIRCLE, 4) if rng.random() < 0.5 else [(rng.randint(-9, 9), rng.randint(-9, 9)) for _ in range(4)]
        cases.append(embed(*frame, uv))
        axes.append(0)
    cases = np.array(cases)
    o = predicate_signs("orient2d_proj", cases[:, :3], axis=0)
    for c, s in zip(cases, o):
        q = [frac(p) for p in c[:3]]
        n0 = (q[1][1] - q[0][1]) * (q[2][2] - q[0][2]) - (q[1][2] - q[0][2]) * (q[2][1] - q[0][1])
        assert s == (n0 > 0) - (n0 < 0)
    ic = predicate_signs("incircle_plane", cases, axis=0)
    for c, s, so in zip(cases, ic, o):
        if so == 0:
            continue
        pts = list(c)
        a, b, cc = (0, 1, 2) if so > 0 else (0, 2, 1)
        q = [frac(p) for p in pts]
        u = [x - y for x, y in zip(q[b], q[a])]
        v = [x - y for x, y in zip(q[cc], q[a])]
        uu, vv, uv = (sum(x * x for x in u), sum(x * x for x in v), sum(x * y for x, y in zip(u, v)))
        den = 2 * (uu * vv - uv * uv)
        s1, t1 = (vv * uu - uv * vv) / den, (uu * vv - uv * uu) / den
        centre = [q[a][k] + s1 * u[k] + t1 * v[k] for k in range(3)]
        r2 = sum((q[a][k] - centre[k]) ** 2 for k in range(3))
        d2 = sum((q[3][k] - centre[k]) ** 2 for k in range(3))
        # positive inside for a, b, c counter-clockwise in the projection; the kernel was
        # given them in input order, so its sign carries their orientation
        want = ((d2 < r2) - (d2 > r2)) * so
        assert s == want, (c.tolist(), s, want)
