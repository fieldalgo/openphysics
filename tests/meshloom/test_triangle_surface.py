# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""``meshloom.generate3d`` from a closed triangle surface.

With each triangle a facet: the surface is meshloom's own boundary of the unit cube at
size h, and every vertex of a face is the apex of a fan of segments, several meeting at
less than 60 degrees. Refinement splits the pieces at such an apex on concentric shells. A
shell radius outside a third to two thirds of the piece fell back to the midpoint, and the
pieces of a fan then encroached each other until their points met in doubles:
``RefineError`` ("subfacet ... is degenerate in doubles") at h = 0.34 and 0.2, and a run
past 30 minutes at h = 0.12.

``max_points`` bounds the run where a clock would make the test flaky: the cascade inserted
points without end, while the fixed run needs a few thousand.

A polygon whose first loop points lie on a rounded slanted edge checks the facet frame.
"""

import math

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from test_refine import c2  # noqa: E402


def boundary_triangles(m):
    """The faces used by one tetrahedron, re-indexed to the vertices they use."""
    t = m["tetrahedra"]
    faces = np.sort(np.concatenate([t[:, [1, 2, 3]], t[:, [0, 2, 3]], t[:, [0, 1, 3]], t[:, [0, 1, 2]]]), axis=1)
    key, count = np.unique(faces, axis=0, return_counts=True)
    tri = key[count == 1]
    used = np.unique(tri)
    lut = np.full(len(m["nodes"]), -1)
    lut[used] = np.arange(len(used))
    return m["nodes"][used], lut[tri]


def volume(m):
    x = m["nodes"][m["tetrahedra"]]
    return np.abs(np.einsum("ij,ij->i", x[:, 1] - x[:, 0], np.cross(x[:, 2] - x[:, 0], x[:, 3] - x[:, 0]))).sum() / 6


def area(points, tri):
    x = points[tri]
    return np.linalg.norm(np.cross(x[:, 1] - x[:, 0], x[:, 2] - x[:, 0]), axis=1).sum() / 2


@pytest.mark.parametrize("h", [0.34, 0.2])
def test_cube_as_triangle_facets(h):
    (points, facets), _ = c2()
    pts, tri = boundary_triangles(meshloom.generate3d(points=points, facets=facets, h=h))
    m = meshloom.generate3d(points=pts, facets=[[list(map(int, t))] for t in tri], h=h, max_points=20000)
    assert volume(m) == pytest.approx(1.0, rel=1e-9)
    faces = np.concatenate([np.asarray(f).reshape(-1, 3) for f in m["boundary_faces"].values()])
    assert len(m["boundary_faces"]) == len(tri)
    assert area(m["nodes"], faces) == pytest.approx(area(pts, tri), rel=1e-9) == pytest.approx(6.0, rel=1e-9)


def test_facet_frame_off_a_rounded_edge():
    """A 15-degree wedge whose top and bottom loops start on the slanted edge: (1, 0), the
    edge's rounded midpoint, (cos 15, sin 15). The three are not exactly collinear, so they
    were the facet's frame, but their sine is about 1e-16: the frame's s, r system was
    singular in doubles, facet points missed their facet, and refinement ran into the point
    cap. The frame is now a well-spread triple of the loop. (Found on the wedge case C7 of the
    3D plan, its triangles joined into polygons.)"""
    a = math.radians(15.0)
    c, s = math.cos(a), math.sin(a)
    xy = [(1.0, 0.0), (1.0 + 0.5 * (c - 1.0), 0.5 * s), (c, s), (0.0, 0.0)]
    n = len(xy)
    points = np.array([(x, y, 0.0) for x, y in xy] + [(x, y, 1.0) for x, y in xy])
    facets = [[list(range(n))], [list(range(n, 2 * n))]]
    facets += [[[i, (i + 1) % n, (i + 1) % n + n, i + n]] for i in range(n)]  # vertical strips, exactly planar
    m = meshloom.generate3d(points=points, facets=facets, h=0.2, max_points=5000)
    assert volume(m) == pytest.approx(0.5 * s, rel=1e-9)

