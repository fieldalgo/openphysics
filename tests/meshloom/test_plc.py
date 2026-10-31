# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Exact PLC validity checks (M4 of the pre-registered 3D plan): valid multi-region
PLCs pass, and every kind of invalid input is refused with the pieces named — touching
or crossing facets, a segment through a facet, a T-junction, a segment inside a facet,
non-planar facets and coincident points. The PLCs are unions of voxels (boundary and
interface squares as facets), mapped through an integer matrix so the facets are tilted
yet exactly planar, plus hand-built boxes with holed facets.
"""

import itertools
from fractions import Fraction

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from meshloom._core import check_plc  # noqa: E402

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

            def area(idx):
                q = [[Fraction(pts[k][i]), Fraction(pts[k][j])] for k in idx]
                return abs(sum(q[a][0] * q[(a + 1) % len(q)][1] - q[(a + 1) % len(q)][0] * q[a][1]
                               for a in range(len(q))))

            assert sum(area(t) for t in tris.tolist()) == area(loops[0])
    assert out["pairs_tested"] > 0


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


def test_invalid_plcs_are_refused():
    sub, sub_f = box(0, 0, 0, 2, 2, 1)
    # the small box stands on the big box's top facet, which does not know about it:
    # coplanar facets overlap
    pts, fs = merge((sub, sub_f), box(0, 0, 1, 1, 1, 2))
    with pytest.raises(ValueError, match="intersect"):
        check_plc(pts, np.zeros((0, 2)), fs)
    # a shifted upper box: its bottom overlaps part of the top facet and its corners
    # (1, 0, 1) and (1, 2, 1) lie inside the big box's top edges (T-junctions)
    pts, fs = merge((sub, sub_f), box(1, 0, 1, 3, 2, 2))
    with pytest.raises(ValueError, match="intersect"):
        check_plc(pts, np.zeros((0, 2)), fs)
    # a pure T-junction: an outside triangle's corner on the middle of a box edge
    pts = np.array(sub + [(1, 0, 0), (1, -1, 0), (1, -1, 1)], float)
    with pytest.raises(ValueError, match="intersect"):
        check_plc(pts, np.zeros((0, 2)), sub_f + [[[8, 9, 10]]])
    # two boxes crossing each other
    pts, fs = merge((sub, sub_f), box(1, 1, 0.5, 3, 3, 1.5))
    with pytest.raises(ValueError, match="intersect"):
        check_plc(pts, np.zeros((0, 2)), fs)
    # a free segment through a facet
    pts = np.array(sub + [(1, 1, -1), (1, 1, 0.5)], float)
    with pytest.raises(ValueError, match="intersect"):
        check_plc(pts, np.array([[8, 9]]), sub_f)
    # a segment along a facet's diagonal, inside it
    with pytest.raises(ValueError, match="intersect"):
        check_plc(np.array(sub, float), np.array([[0, 3]]), sub_f)
    # a non-planar facet and coincident points
    bent = np.array(sub, float)
    bent[7, 2] = np.nextafter(1.0, 2.0)
    with pytest.raises(ValueError, match="plane"):
        check_plc(bent, np.zeros((0, 2)), sub_f)
    twice = np.array(sub + [sub[3]], float)
    with pytest.raises(ValueError, match="coincide"):
        check_plc(twice, np.zeros((0, 2)), sub_f)


def test_a_segment_along_a_box_edge_and_a_free_segment_outside_are_valid():
    sub, sub_f = box(0, 0, 0, 2, 2, 1)
    pts = np.array(sub + [(3, 3, 3), (4, 4, 4)], float)
    out = check_plc(pts, np.array([[0, 1], [8, 9]]), sub_f)
    assert len(out["segments"]) == 13
