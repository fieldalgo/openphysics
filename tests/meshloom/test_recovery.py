# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Segment recovery (M4 of the pre-registered 3D plan): after the PLC check, every
elementary segment becomes a union of edges of the tetrahedralization, with new points
only on segments (S points). Each result is checked from the arrays with the exact
mixed predicates: every tetrahedron positive, every interior face shared by two
tetrahedra and locally Delaunay under the index-ordered perturbation, every point a
vertex, the volume equal to the convex hull's, and every segment a chain of edges
through its own S points with increasing parameter.

Inputs: voxel PLCs (the chip package and the Fichera corner, axis-aligned and tilted by
an integer matrix), a geodesic sphere (nearly cospherical points), a twisted
(Schonhardt) prism, an acute fan, and long segments through a point cloud.
"""

import itertools
import math
import random

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from meshloom._core import check_plc, mixed_predicate_signs, recover_segments  # noqa: E402

TILT = np.array([[2, 1, 0], [-1, 2, 1], [0, 1, 3]], dtype=float)


def voxel_plc(cells, transform=None, h=0.25):
    """Boundary and interface squares of a voxel set {(i, j, k): material}."""
    index, points, facets = {}, [], []

    def pid(c):
        if c not in index:
            index[c] = len(points)
            points.append(c)
        return index[c]

    for (i, j, k), mat in cells.items():
        for axis in range(3):
            for side in (0, 1):
                nb = [i, j, k]
                nb[axis] += 1 if side else -1
                other = cells.get(tuple(nb))
                if other == mat or (other is not None and side == 0):
                    continue
                base = [i, j, k]
                base[axis] += side
                u, v = [a for a in range(3) if a != axis]
                corners = []
                for du, dv in ((0, 0), (1, 0), (1, 1), (0, 1)):
                    c = list(base)
                    c[u] += du
                    c[v] += dv
                    corners.append(pid(tuple(c)))
                facets.append([corners])
    pts = np.array(points, dtype=float) * h
    if transform is not None:
        pts = pts @ transform.T
    return pts, facets


def chip():
    cells = {(i, j, 0): "substrate" for i in range(4) for j in range(4)}
    cells.update({(i, j, 1): "mold" for i in range(4) for j in range(4)})
    cells.update({(i, j, 1): "die" for i in (1, 2) for j in (1, 2)})
    cells.update({(i, j, 2): "mold" for i in range(4) for j in range(4)})
    return cells


def fichera():
    return {c: "a" for c in itertools.product((0, 1), repeat=3) if c != (1, 1, 1)}


def geodesic_sphere(freq):
    """A frequency-`freq` geodesic subdivision of the icosahedron, on the unit sphere."""
    t = (1 + 5 ** 0.5) / 2
    ico = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
           (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
             (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5),
             (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    index, points, tris = {}, [], []

    def pid(key, p):
        if key not in index:
            n = math.sqrt(sum(c * c for c in p))
            index[key] = len(points)
            points.append([c / n for c in p])
        return index[key]

    for a, b, c in faces:
        A, B, C = (np.array(ico[i], float) for i in (a, b, c))
        grid = {}
        for i in range(freq + 1):
            for j in range(freq + 1 - i):
                k = freq - i - j
                # a canonical key for points shared by neighbouring faces: the exact
                # barycentric combination of the icosahedron vertices
                key = tuple(sorted(((a, i), (b, j), (c, k)), key=lambda x: x[0]))
                key = tuple(x for x in key if x[1])
                grid[i, j] = pid(key, (i * A + j * B + k * C) / freq)
        for i in range(freq):
            for j in range(freq - i):
                tris.append([grid[i, j], grid[i + 1, j], grid[i, j + 1]])
                if i + j < freq - 1:
                    tris.append([grid[i + 1, j], grid[i + 1, j + 1], grid[i, j + 1]])
    return np.array(points), [[t] for t in tris]


def twisted_prism():
    pts = []
    for h, rot in ((0.0, 0.0), (1.0, 30.0)):
        for k in range(3):
            a = math.radians(120 * k + rot)
            pts.append([math.cos(a), math.sin(a), h])
    facets = [[[0, 2, 1]], [[3, 4, 5]], [[0, 1, 4]], [[0, 4, 3]], [[1, 2, 5]], [[1, 5, 4]], [[2, 0, 3]],
              [[2, 3, 5]]]
    return np.array(pts), facets


def recover_checked(points, facets=(), segments=None):
    if facets:
        plc = check_plc(points, np.zeros((0, 2)) if segments is None else segments, list(facets))
        subs = plc["subsegments"]
    else:
        subs = np.asarray(segments, dtype=np.int64)
    r = recover_segments(points, subs)
    n, k = len(points), len(r["s_t"])
    tets, sseg, st = r["tetrahedra"], r["s_segments"], r["s_t"]
    assert sorted(np.unique(tets).tolist()) == list(range(n + k)), "every point is a vertex"
    signs, _ = mixed_predicate_signs("orient3d", points, sseg, st, tets)
    assert (signs == 1).all(), "every tetrahedron is positive"
    faces = {}
    for ti, v in enumerate(tets.tolist()):
        for i in range(4):
            faces.setdefault(tuple(sorted(v[:i] + v[i + 1:])), []).append((ti, i))
    pairs = []
    for owners in faces.values():
        assert len(owners) <= 2
        if len(owners) == 2:
            (t1, _), (t2, i2) = owners
            pairs.append(tets[t1].tolist() + [int(tets[t2][i2])])
    s, _ = mixed_predicate_signs("insphere_sos", points, sseg, st, np.array(pairs))
    assert (s < 0).all(), "every interior face is locally Delaunay"
    # the volume of the tetrahedra (rounded S points; a tiny tolerance) equals the hull's
    xyz = np.vstack([points, points[sseg[:, 0]] + st[:, None] * (points[sseg[:, 1]] - points[sseg[:, 0]])]) \
        if k else points
    a, b, c, d = (xyz[tets[:, i]] for i in range(4))
    vol = np.einsum("ij,ij->i", b - a, np.cross(c - a, d - a)).sum() / 6
    scipy_spatial = pytest.importorskip("scipy.spatial")
    hull = scipy_spatial.ConvexHull(points).volume
    assert abs(vol - hull) <= 1e-9 * max(1.0, abs(hull)), (vol, hull)
    # chains: segments as unions of edges through their own S points
    edges = {tuple(sorted((v[i], v[j]))) for v in tets.tolist() for i in range(4) for j in range(i + 1, 4)}
    seen = set()
    for (a, b), chain in zip(subs.tolist(), r["chains"]):
        chain = chain.tolist()
        assert chain[0] == a and chain[-1] == b
        for x, y in zip(chain, chain[1:]):
            assert tuple(sorted((x, y))) in edges
        ts = [st[c - n] for c in chain[1:-1]]
        assert all(sseg[c - n].tolist() == [a, b] for c in chain[1:-1])
        assert all(0 < t < 1 for t in ts) and ts == sorted(ts) and len(set(ts)) == len(ts)
        seen.update(chain[1:-1])
    assert len(seen) == k
    return r


@pytest.mark.parametrize("cells", [chip, fichera], ids=["chip", "fichera"])
@pytest.mark.parametrize("transform", [None, TILT], ids=["axis", "tilted"])
def test_voxel_plcs_are_recovered(cells, transform):
    pts, facets = voxel_plc(cells(), transform)
    recover_checked(pts, facets)


def test_a_geodesic_sphere_is_recovered():
    pts, facets = geodesic_sphere(6)
    assert len(pts) == 362
    recover_checked(pts, facets)


def test_a_twisted_prism_is_recovered():
    pts, facets = twisted_prism()
    r = recover_checked(pts, facets)
    assert r["stats"]["protected_vertices"] == 6


def test_an_acute_fan_and_long_segments_through_a_cloud():
    rng = random.Random(4)
    pts = [[0.0, 0.0, 0.0]] + [[math.cos(math.radians(d)), math.sin(math.radians(d)), 0.0] for d in (0, 1, 5, 30)]
    pts += [[rng.uniform(-0.5, 1.5), rng.uniform(-1, 1), rng.uniform(-0.1, 0.1)] for _ in range(300)]
    segs = [[0, 1], [0, 2], [0, 3], [0, 4]]
    r = recover_checked(np.array(pts), segments=segs)
    assert r["stats"]["protection_points"] == 4
    # two long skew segments that miss every other segment (crossings are invalid input):
    # their z = 0 points lie at -18 and 65 degrees, away from the fan
    pts += [[-0.6, -1.1, -0.2], [1.6, 1.1, 0.25], [1.4, -1.1, 0.12], [-0.6, 1.1, -0.07]]
    segs += [[len(pts) - 4, len(pts) - 3], [len(pts) - 2, len(pts) - 1]]
    r = recover_checked(np.array(pts), segments=segs)
    assert r["stats"]["bisection_points"] > 0


def test_bad_input_and_too_deep_recovery_are_refused():
    pts = np.array([[0.0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 1]])
    with pytest.raises(ValueError, match="equal ends"):
        recover_segments(pts, [[1, 1]])
    with pytest.raises(ValueError, match="does not exist"):
        recover_segments(pts, [[1, 9]])
    with pytest.raises(ValueError, match="coincide"):
        recover_segments(np.vstack([pts, pts[2]]), [[0, 1]])
    rng = random.Random(1)
    cloud = np.array([[rng.random() for _ in range(3)] for _ in range(300)] + [[-0.1] * 3, [1.1] * 3])
    with pytest.raises(RuntimeError, match="halvings"):
        recover_segments(cloud, [[300, 301]], max_depth=1)


def exact_points(points, sseg, st):
    """Exact coordinates (Fraction) of the input points followed by the S points."""
    from fractions import Fraction as F
    out = [[F(c) for c in p] for p in points.tolist()]
    for (a, b), t in zip(sseg.tolist(), st.tolist()):
        out.append([F(x) + F(t) * (F(y) - F(x)) for x, y in zip(points[a].tolist(), points[b].tolist())])
    return out


def projected_area(q, idx, axis):
    i, j = [(1, 2), (2, 0), (0, 1)][axis]
    pts = [q[k] for k in idx]
    return sum(pts[m][i] * pts[(m + 1) % len(pts)][j] - pts[(m + 1) % len(pts)][i] * pts[m][j]
               for m in range(len(pts))) / 2


@pytest.mark.parametrize("case", ["chip", "fichera-tilted", "prism", "interface"])
def test_subfacets_tile_their_facets_with_the_segment_points(case):
    from meshloom._core import recover_plc
    if case == "chip":
        pts, facets = voxel_plc(chip())
    elif case == "fichera-tilted":
        pts, facets = voxel_plc(fichera(), TILT)
    elif case == "prism":
        pts, facets = twisted_prism()
    else:
        # two stacked cells and their interface, crowded by points on both sides
        pts, facets = voxel_plc({(0, 0, 0): "a", (0, 0, 1): "b"})
        rng = random.Random(9)
        extra = [[0.02 + 0.21 * rng.random(), 0.02 + 0.21 * rng.random(),
                  0.25 + (1 if k % 2 else -1) * (0.0005 + 0.01 * rng.random())] for k in range(40)]
        pts = np.vstack([pts, extra])
    r = recover_plc(pts, np.zeros((0, 2)), facets)
    q = exact_points(pts, r["s_segments"], r["s_t"])
    n = len(pts)
    plc = check_plc(pts, np.zeros((0, 2)), facets)
    subs = {tuple(sorted(s)) for s in plc["subsegments"].tolist()}
    for f, loops in enumerate(facets):
        tris = r["subfacets"][r["subfacet_facet"] == f].tolist()
        assert tris
        # the facet's points: its own, and S points on its sub-segments (in its plane)
        a, b, c = (q[v] for v in loops[0][:3])
        normal = [(b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]),
                  (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]),
                  (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])]
        for t in tris:
            for v in t:
                assert sum(x * (y - z) for x, y, z in zip(normal, q[v], a)) == 0, "subfacet vertex off the plane"
                if v >= n:
                    s = tuple(sorted(r["s_segments"][v - n].tolist()))
                    assert s in subs
        axis = max(range(3), key=lambda k: abs(normal[k]))
        want = abs(sum(projected_area(q, lp, axis) for lp in loops[:1])) - \
            sum(abs(projected_area(q, lp, axis)) for lp in loops[1:])
        got = [projected_area(q, t, axis) for t in tris]
        assert all(g != 0 for g in got) and len({g > 0 for g in got}) == 1, "consistently wound, no slivers"
        assert abs(sum(got)) == want, f"facet {f}: the subfacets do not tile it"
    # missing = subfacets that are not faces of the tetrahedralization
    faces = {tuple(sorted(v[:i] + v[i + 1:])) for v in r["tetrahedra"].tolist() for i in range(4)}
    absent = [k for k, t in enumerate(r["subfacets"].tolist()) if tuple(sorted(t)) not in faces]
    assert absent == r["missing"].tolist()
    if case == "interface":
        assert len(absent) > 0  # the work left to facet recovery
