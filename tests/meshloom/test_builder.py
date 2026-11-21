# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Curved primitives (``meshloom.builder``) and locked facets: V5 and the builder's own
contract.

Rows of docs/packages/meshine/validation3d.md:

- V5 on C1 (unit sphere), C4 (via r = 0.3 through [-1,1]^2 x [0,1]), C5 (sphere r = 0.5
  in [-1,1]^3) and C11 (spheres 0.5, 0.75, 1): for every node of a curved surface,
  delta(p) = |‖p - c‖² - R²| / (2R(‖c‖ + R)) (for the cylinder, the distance to the axis),
  computed exactly in rational arithmetic on the output doubles, is at most 1e-15.

The builder's contract:

- Curved triangles are strictly Delaunay. No other point of the surface lies in a
  triangle's diametral ball (exact for the points near the ball), so recovery adds no
  point on them.
- The output is deterministic.
- Locked facets: refinement adds no point to a locked facet or its edges.
"""

from fractions import Fraction

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from meshloom import builder  # noqa: E402

CASES = {
    "C1": (lambda h: builder.sphere(h), [("sphere", "sphere", (0, 0, 0), 1.0)]),
    "C4": (lambda h: builder.via_in_slab(h), [("via_side", "cylinder", (0, 0), 0.3)]),
    "C5": (lambda h: builder.sphere_in_box(h), [("sphere", "sphere", (0, 0, 0), 0.5)]),
    "C11": (lambda h: builder.nested_spheres(h), [(f"sphere{i}", "sphere", (0, 0, 0), r)
                                                   for i, r in enumerate((0.5, 0.75, 1.0))]),
}
SIZES = {"C1": (0.2, 0.1), "C4": (0.2, 0.1), "C5": (0.24, 0.12), "C11": (0.1,)}  # C11 0.05, 0.025: test_quality V24


def delta(p, kind, centre, radius):
    """V5's distance measure, exactly on the doubles of p."""
    r = Fraction(radius)
    if kind == "cylinder":
        d2 = sum((Fraction(float(p[a])) - Fraction(centre[a])) ** 2 for a in range(2))
        return abs(d2 - r * r) / (2 * r * r)
    d2 = sum((Fraction(float(p[a])) - Fraction(centre[a])) ** 2 for a in range(3))
    norm_c = float(np.linalg.norm(centre))  # |c| only scales the bound; c = 0 in every case here
    return abs(d2 - r * r) / (2 * r * (Fraction(norm_c) + r))


def curved_nodes(kw, m, tag):
    """Output nodes on the curved surface ``tag``: the nodes of its boundary faces, or (for
    an interface) the input points of its triangles, which recovery and refinement keep."""
    if tag in m["boundary_faces"]:
        return m["nodes"][np.unique(m["boundary_faces"][tag])]
    ids = sorted({v for i in kw["locked_facets"] if kw["facet_tags"][i] == tag for v in kw["facets"][i][0]})
    points = kw["points"][ids]
    # every input point is an output node, bit for bit
    found = {tuple(x) for x in m["nodes"].tolist()}
    assert all(tuple(x) in found for x in points.tolist())
    return points


@pytest.mark.parametrize("case,h", [(c, h) for c in CASES for h in SIZES[c]])
def test_v5_curved_nodes_lie_on_their_surface(case, h):
    make, surfaces = CASES[case]
    kw = make(h)
    m = meshloom.generate3d(h=h, **kw)
    for tag, kind, centre, radius in surfaces:
        nodes = curved_nodes(kw, m, tag)
        assert len(nodes) > 0
        worst = max(delta(p, kind, centre, radius) for p in nodes)
        assert worst <= Fraction(1, 10 ** 15), (case, h, tag, float(worst))


@pytest.mark.parametrize("case", list(CASES))
def test_curved_triangles_are_strictly_delaunay(case):
    kw = CASES[case][0](0.2)
    pts = kw["points"]
    for i in kw["locked_facets"]:
        a, b, c = (pts[v] for v in kw["facets"][i][0])
        # circumcentre and radius of the triangle in its plane
        u, w = b - a, c - a
        n = np.cross(u, w)
        o = a + (np.dot(u, u) * np.cross(w, n) + np.dot(w, w) * np.cross(n, u)) / (2 * np.dot(n, n))
        r2 = np.dot(a - o, a - o)
        d2 = np.sum((pts - o) ** 2, axis=1)
        tri = set(kw["facets"][i][0])
        near = [j for j in np.flatnonzero(d2 <= r2 * (1 + 1e-6)) if j not in tri]
        for j in near:  # decide the close calls exactly: |q - o|^2 > r^2 in rationals
            fa, fb, fc, fq = ([Fraction(float(x)) for x in pts[v]] for v in (*kw["facets"][i][0], j))
            fu = [fb[k] - fa[k] for k in range(3)]
            fw = [fc[k] - fa[k] for k in range(3)]
            fn = [fu[1] * fw[2] - fu[2] * fw[1], fu[2] * fw[0] - fu[0] * fw[2], fu[0] * fw[1] - fu[1] * fw[0]]
            nn = sum(x * x for x in fn)
            wn = [fw[1] * fn[2] - fw[2] * fn[1], fw[2] * fn[0] - fw[0] * fn[2], fw[0] * fn[1] - fw[1] * fn[0]]
            nu = [fn[1] * fu[2] - fn[2] * fu[1], fn[2] * fu[0] - fn[0] * fu[2], fn[0] * fu[1] - fn[1] * fu[0]]
            uu, ww = sum(x * x for x in fu), sum(x * x for x in fw)
            fo = [fa[k] + (uu * wn[k] + ww * nu[k]) / (2 * nn) for k in range(3)]
            assert sum((fq[k] - fo[k]) ** 2 for k in range(3)) > sum((fa[k] - fo[k]) ** 2 for k in range(3)), (case, i, j)


def test_the_builder_is_deterministic():
    for make, _ in CASES.values():
        a, b = make(0.2), make(0.2)
        assert a["points"].tobytes() == b["points"].tobytes()
        assert a["facets"] == b["facets"] and a["locked_facets"] == b["locked_facets"]


def test_locked_facets_get_no_point():
    # the unit cube with its bottom face locked: refinement leaves that face as recovery made it
    pts = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], float)
    facets = [[[0, 3, 2, 1]], [[4, 5, 6, 7]], [[0, 1, 5, 4]], [[2, 3, 7, 6]], [[1, 2, 6, 5]], [[0, 4, 7, 3]]]
    m = meshloom.generate3d(pts, facets, h=0.2, locked_facets=[0])
    bottom = m["boundary_faces"]["0"]
    assert len(bottom) == 2  # output nodes are renumbered: compare coordinates
    assert {tuple(x) for x in m["nodes"][np.unique(bottom)].tolist()} == {tuple(x) for x in pts[:4].tolist()}
    assert len(m["boundary_faces"]["1"]) > 2  # the open faces are refined
    with pytest.raises(ValueError, match="locked_facets"):
        meshloom.generate3d(pts, facets, h=0.2, locked_facets=[6])


def test_builder_arguments():
    with pytest.raises(ValueError):
        builder.sphere(0)
    with pytest.raises(ValueError):
        builder.sphere_in_box(0.2, radius=1.5)
    with pytest.raises(ValueError):
        builder.via_in_slab(0.2, radius=1.0)
    with pytest.raises(ValueError):
        builder.nested_spheres(0.2, radii=(1.0, 0.5))
