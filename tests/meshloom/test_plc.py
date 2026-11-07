# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Exact PLC validity checks (M4 of the pre-registered 3D plan) under the import
validity rule: every two cells must meet in a union of cells. Valid multi-region PLCs
pass, including T-junctions, a segment inside a facet, a facet inside a coplanar facet
and a coplanar overlap tiled by a common facet; crossings, piercings, partial collinear
overlaps, an untiled coplanar overlap, duplicate facets, non-planar facets, coordinates
outside the kernel's range and empty input are refused with their witness type. The PLCs
are unions of voxels (boundary and interface squares as facets), mapped through an
integer matrix so the facets are tilted yet exactly planar, plus hand-built boxes with
holed facets.
"""

import itertools
from fractions import Fraction

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from meshloom._core import InvalidPLC, check_plc  # noqa: E402

TILT = np.array([[2, 1, 0], [-1, 2, 1], [0, 1, 3]], dtype=float)  # det 14: tilted, exact


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
                    continue  # inside one material, or an interface emitted from the other side
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


def fichera():
    return {c: "a" for c in itertools.product((0, 1), repeat=3) if c != (1, 1, 1)}


def chip():
    cells = {(i, j, 0): "substrate" for i in range(4) for j in range(4)}
    cells.update({(i, j, 1): "mold" for i in range(4) for j in range(4)})
    cells.update({(i, j, 1): "die" for i in (1, 2) for j in (1, 2)})
    cells.update({(i, j, 2): "mold" for i in range(4) for j in range(4)})
    return cells


@pytest.mark.parametrize("cells", [fichera, chip], ids=["fichera", "chip"])
@pytest.mark.parametrize("transform", [None, TILT], ids=["axis", "tilted"])
def test_voxel_plcs_are_valid(cells, transform):
    pts, facets = voxel_plc(cells(), transform)
    out = check_plc(pts, np.zeros((0, 2)), facets)
    assert len(out["triangles"]) == 2 * len(facets)
    # every square is covered exactly by its two triangles (projected areas, exact)
    for f, loops in enumerate(facets):
        tris = out["triangles"][out["triangle_facet"] == f]
        assert len(tris) == 2
        for axis in range(3):
            i, j = [(1, 2), (2, 0), (0, 1)][axis]

            def area(idx, i=i, j=j):
                q = [[Fraction(pts[k][i]), Fraction(pts[k][j])] for k in idx]
                return abs(sum(q[a][0] * q[(a + 1) % len(q)][1] - q[(a + 1) % len(q)][0] * q[a][1]
                               for a in range(len(q))))

            assert sum(area(t) for t in tris.tolist()) == area(loops[0])
    assert out["pairs_tested"] > 0
    if cells is fichera:
        assert len(out["open_subsegments"]) == 0  # a closed surface


def box(x0, y0, z0, x1, y1, z1, start=0):
    pts = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    f = [[0, 2, 3, 1], [4, 5, 7, 6], [0, 1, 5, 4], [2, 6, 7, 3], [0, 4, 6, 2], [1, 3, 7, 5]]
    return pts, [[[start + v for v in lp]] for lp in f]


def test_box_on_box_with_a_holed_facet_is_valid():
    # substrate [0,4]^2 x [0,1]; die [1,3]^2 x [1,2] standing on it; the substrate's top
    # is a square with the die's footprint as a hole, and the footprint is the interface
    sub, _ = box(0, 0, 0, 4, 4, 1)
    die, die_f = box(1, 1, 1, 3, 3, 2, start=8)
    pts = np.array(sub + die, dtype=float)
    sub_f = [[[0, 2, 3, 1]], [[0, 1, 5, 4]], [[2, 6, 7, 3]], [[0, 4, 6, 2]], [[1, 3, 7, 5]],
             [[4, 5, 7, 6], [8, 9, 11, 10]]]
    out = check_plc(pts, np.zeros((0, 2)), sub_f + die_f)
    assert len(out["triangles"]) == 5 * 2 + 8 + 6 * 2


def merge(*parts):
    """Points of several (points, facets) parts, with equal points shared."""
    index, points, facets = {}, [], []
    for pts, fs in parts:
        local = []
        for p in pts:
            if p not in index:
                index[p] = len(points)
                points.append(p)
            local.append(index[p])
        start = min(v for f in fs for lp in f for v in lp)
        facets += [[[local[v - start] for v in lp] for lp in f] for f in fs]
    return np.array(points, float), facets


def refused(witness, pts, segments, facets, match=None):
    with pytest.raises(InvalidPLC, match=match) as e:
        check_plc(pts, np.asarray(segments).reshape(-1, 2), facets)
    assert e.value.witness_type == witness, str(e.value)


def test_cells_inside_cells_are_valid():
    sub, sub_f = box(0, 0, 0, 2, 2, 1)
    # a small box standing inside the big box's top facet, which does not know about it:
    # its corners lie inside the facet and its bottom is a facet inside a coplanar facet
    pts, fs = merge((sub, sub_f), box(0.5, 0.5, 1, 1.5, 1.5, 2))
    out = check_plc(pts, np.zeros((0, 2)), fs)
    assert len(out["open_subsegments"]) == 0
    # a small box in the corner: its bottom edges lie inside the big top's edges, whose
    # middle points (1, 0, 1) and (0, 1, 1) are T-junctions
    pts, fs = merge((sub, sub_f), box(0, 0, 1, 1, 1, 2))
    out = check_plc(pts, np.zeros((0, 2)), fs)
    segs = set(map(tuple, out["segments"].tolist()))
    subs = set(map(tuple, out["subsegments"].tolist()))
    assert {(4, 5), (4, 6)} <= segs and not {(4, 5), (4, 6)} & subs  # split at the T-junctions
    assert len(out["open_subsegments"]) == 0
    # a triangle's corner on the middle of a box edge (a T-junction)
    pts = np.array(sub + [(1, 0, 0), (1, -1, 0), (1, -1, 1)], float)
    check_plc(pts, np.zeros((0, 2)), sub_f + [[[8, 9, 10]]])
    # a segment along a facet's diagonal, inside it, and a fin standing on that diagonal
    check_plc(np.array(sub, float), np.array([[0, 3]]), sub_f)
    pts = np.array(sub + [(1, 1, -1)], float)
    check_plc(pts, np.zeros((0, 2)), sub_f + [[[0, 3, 8]]])
    # a segment ending inside a facet
    pts = np.array(sub + [(1, 1, 0), (1, 1, -1)], float)
    check_plc(pts, np.array([[8, 9]]), sub_f)
    # a segment along a box edge and a free segment outside
    pts = np.array(sub + [(3, 3, 3), (4, 4, 4)], float)
    out = check_plc(pts, np.array([[0, 1], [8, 9]]), sub_f)
    assert len(out["segments"]) == 13


def test_coplanar_overlaps_need_a_common_tile():
    # rectangles A = [0,2]x[0,1] and B = [0,1]x[0,2] in the plane z = 0 overlap in the
    # unit square; with the square C as a facet (its corner (1, 1) on the edges of both)
    # the overlap is a union of cells, without it it is not
    q = [(0, 0, 0), (2, 0, 0), (2, 1, 0), (0, 1, 0), (1, 0, 0), (1, 1, 0), (1, 2, 0), (0, 2, 0)]
    pts = np.array(q, float) @ TILT.T
    a, b, c = [[0, 4, 1, 2, 5, 3]], [[0, 4, 5, 6, 7, 3]], [[0, 4, 5, 3]]
    out = check_plc(pts, np.zeros((0, 2)), [a, b, c])
    assert len(out["open_subsegments"]) > 0  # three open sheets
    refused(5, pts, [], [a, b], match="intersect")
    # A and C alone: C inside A
    check_plc(pts, np.zeros((0, 2)), [a, c])


def test_invalid_plcs_are_refused():
    sub, sub_f = box(0, 0, 0, 2, 2, 1)
    # a shifted upper box: its bottom overlaps part of the top facet, and the part is
    # covered by no facet of both
    pts, fs = merge((sub, sub_f), box(1, 0, 1, 3, 2, 2))
    refused(5, pts, [], fs, match="intersect")
    # two boxes crossing each other
    pts, fs = merge((sub, sub_f), box(1, 1, 0.5, 3, 3, 1.5))
    refused(5, pts, [], fs, match="intersect")
    # a free segment through a facet
    pts = np.array(sub + [(1, 1, -1), (1, 1, 0.5)], float)
    refused(5, pts, [[8, 9]], sub_f, match="intersect")
    # a segment overlapping half of a box edge and running past it
    pts = np.array(sub + [(1, 0, 0), (3, 0, 0)], float)
    refused(5, pts, [[8, 9]], sub_f, match="intersect")
    # a segment starting inside a facet and leaving through its edge
    pts = np.array(sub + [(1, 1, 0), (3, 1, 0)], float)
    refused(5, pts, [[8, 9]], sub_f, match="intersect")
    # a facet given twice (type 4), a repeated vertex (type 2), a non-planar facet and a
    # collinear triangle (type 3)
    refused(4, np.array(sub, float), [], sub_f + [[[0, 1, 3, 2]]], match="same vertices")
    refused(2, np.array(sub, float), [], sub_f[:-1] + [[[1, 3, 7, 3, 5]]], match="twice")
    bent = np.array(sub, float)
    bent[7, 2] = np.nextafter(1.0, 2.0)
    refused(3, bent, [], sub_f, match="plane")
    pts = np.array(sub + [(1, 0, 0)], float)
    refused(3, pts, [], [[[0, 8, 1]]])
    # a coordinate outside the kernel's range (type 1), named by its point
    tiny = np.array(sub, float)
    tiny[5, 1] = 1e-200
    refused(1, tiny, [], sub_f, match="5")
    # no facets (type 0); coincident points are malformed arrays, not a witness
    refused(0, np.array(sub, float), [], [], match="no facets")
    twice = np.array(sub + [sub[3]], float)
    refused(None, twice, [], sub_f, match="coincide")
