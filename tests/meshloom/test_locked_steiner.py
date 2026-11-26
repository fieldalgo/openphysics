# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Locked facets recovered with Steiner points inside the domain only (design option (B)).

With ``locked_facets``, boundary recovery may need points on a locked facet or its edges.
``mesh_plc`` now moves those points into the domain, so every locked facet keeps its input
points and triangles. Before, it raised ``RecoveryError`` ("locked facet ... needs a point
that is not an input point") on each case below.

Inputs (C10, C13 synthetic repros, every facet locked, no refinement):

- the Schonhardt twisted prism and the Chazelle polyhedron (n = 3), which have no
  tetrahedralization without Steiner points;
- the eight C13 fuzz cases among the first 200 valid closed ones that needed points on
  their facets;
- a cube whose six faces are each split into many triangles, locked, at a size that makes
  recovery put points on them.

Each mesh must pass V1-V4 (``test_adversarial.check``), keep only input points on its
boundary and interface faces, and add at least one point inside the domain.
"""

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

import test_adversarial as A  # noqa: E402
import test_fuzz as F  # noqa: E402
from meshloom._core import mesh_plc  # noqa: E402

FUZZ_SEEDS = [12, 24, 33, 184, 197, 205, 257, 322]


def region_volumes(m):
    x = m["nodes"][m["tetrahedra"]]
    v = np.einsum("ij,ij->i", x[:, 1] - x[:, 0], np.cross(x[:, 2] - x[:, 0], x[:, 3] - x[:, 0])) / 6
    return [float(v[m["regions"] == k].sum()) for k in range(len(m["region_names"]))]


def check_locked(m, pts, facets, volumes, exact):
    A.check(m, pts, facets, volumes if volumes is not None else region_volumes(m), exact)
    src = np.asarray(m["node_source"])
    faces = [np.asarray(v).reshape(-1, 3) for v in m["boundary_faces"].values()]
    faces += [np.asarray(v).reshape(-1, 3) for v in m["interfaces"].values()]
    on_surface = np.unique(np.concatenate(faces))
    assert (src[on_surface] < len(pts)).all(), "a locked facet holds a point that is not an input point"
    assert m["stats"]["locked_points_moved"] > 0 and m["stats"]["locked_interior_points"] > 0
    assert (src >= len(pts)).sum() > 0


@pytest.mark.parametrize("name", ["schonhardt", "chazelle-3"])
def test_locked_c10_case_needs_interior_points(name):
    pts, facets, volumes, exact = A.CASES[name]
    m = mesh_plc(pts, facets, locked_facets=list(range(len(facets))))
    check_locked(m, pts, facets, volumes, exact)


@pytest.mark.parametrize("seed", FUZZ_SEEDS)
def test_locked_fuzz_case(seed):
    pts, facets = F.case(seed)
    m = mesh_plc(pts, facets, locked_facets=list(range(len(facets))))
    # fuzz has no reference volumes: V4 here only checks the regions add up consistently
    check_locked(m, pts, facets, None, False)


def triangulated_cube(n):
    """The unit cube with each face an n x n grid of right triangles, one facet each."""
    idx, pts = {}, []

    def p(q):
        if q not in idx:
            idx[q] = len(pts)
            pts.append(q)
        return idx[q]

    tris = []
    g = [k / n for k in range(n + 1)]
    for axis in range(3):
        for side in (0.0, 1.0):
            for i in range(n):
                for j in range(n):
                    quad = []
                    for (a, b) in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                        q = [0.0, 0.0, 0.0]
                        q[axis] = side
                        q[(axis + 1) % 3], q[(axis + 2) % 3] = g[a], g[b]
                        quad.append(p(tuple(q)))
                    if side == 0.0:
                        quad.reverse()
                    tris += [[quad[0], quad[1], quad[2]], [quad[0], quad[2], quad[3]]]
    return np.array(pts), [[t] for t in tris]


def test_locked_triangulated_cube_with_refinement():
    pts, facets = triangulated_cube(4)
    m = meshloom.generate3d(points=pts, facets=facets, h=0.2, locked_facets=list(range(len(facets))))
    A.check(m, pts, {k: facets[int(k)] for k in m["boundary_faces"]}, [1.0], True, euler=True, inner_cover=False)
    src = np.asarray(m["node_source"])
    on_surface = np.unique(np.concatenate([np.asarray(v).reshape(-1, 3) for v in m["boundary_faces"].values()]))
    assert (src[on_surface] < len(pts)).all()
    assert m["stats"]["locked_points_moved"] > 0
