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
  recovery put points on them;
- the boundary and interface triangles of meshloom's own C3 mesh at h = 0.8, every
  triangle a locked facet tagged by its region pair (as V14's locked rows give them).
  Main 6a5b88e8 (2026-11-27) panicked on it: the relocation's point set took the
  recovered S points without their interval coordinates, so S point 0 was given the
  coordinates of the next point pushed, a predicate took a wrong sign and a polygon
  around a moved point was clipped to two vertices.

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


def surface_groups(m):
    """The boundary and interface triangles of a mesh (sorted vertex triples), with the
    regions on each side (-1 outside)."""
    t, reg = np.asarray(m["tetrahedra"]), np.asarray(m["regions"])
    faces = np.sort(np.concatenate([t[:, [1, 2, 3]], t[:, [0, 2, 3]], t[:, [0, 1, 3]], t[:, [0, 1, 2]]]), axis=1)
    owner = np.tile(np.arange(len(t)), 4)
    order = np.lexsort(faces.T[::-1])
    faces, owner = faces[order], owner[order]
    first = np.ones(len(faces), bool)
    first[1:] = np.any(faces[1:] != faces[:-1], axis=1)
    starts = np.flatnonzero(first)
    counts = np.diff(np.append(starts, len(faces)))
    out = []
    for s, c in zip(starts, counts):
        ra, rb = reg[owner[s]], (reg[owner[s + 1]] if c == 2 else -1)
        if c == 1 or ra != rb:
            out.append((faces[s], min(ra, rb) if rb >= 0 else ra, max(ra, rb)))
    return out


def tet_and_region_volumes(m):
    x = np.asarray(m["nodes"])[np.asarray(m["tetrahedra"])]
    v = np.einsum("ij,ij->i", x[:, 1] - x[:, 0], np.cross(x[:, 2] - x[:, 0], x[:, 3] - x[:, 0])) / 6
    return v, np.array([v[np.asarray(m["regions"]) == r].sum() for r in range(len(m["region_names"]))])


def test_locked_surface_of_a_three_region_mesh():
    import quality_cases as Q
    src = Q.generate("C3", 0.8)
    groups = surface_groups(src)
    used = np.unique(np.array([f for f, _, _ in groups]))
    lut = np.full(len(src["nodes"]), -1)
    lut[used] = np.arange(len(used))
    pts = np.asarray(src["nodes"])[used]
    pairs = sorted({(int(a), int(b)) for _, a, b in groups})
    facets = [[[int(v) for v in lut[f]]] for f, _, _ in groups]
    tags = [f"g{pairs.index((int(a), int(b)))}" for _, a, b in groups]
    m = meshloom.generate3d(points=pts, facets=facets, h=0.8, facet_tags=tags,
                            locked_facets=list(range(len(facets))), region_points=Q.C3_SEEDS)
    assert m["stats"]["locked_points_moved"] > 0  # the path that failed
    v, vol = tet_and_region_volumes(m)
    assert (v > 0).all()
    _, want = tet_and_region_volumes(src)
    assert sorted(m["region_names"]) == sorted(src["region_names"])
    order = [list(m["region_names"]).index(n) for n in src["region_names"]]
    assert np.allclose(vol[order], want, rtol=1e-12, atol=0)
    on_surface = np.unique(np.concatenate([np.asarray(f).reshape(-1, 3) for f in m["boundary_faces"].values()]))
    assert (np.asarray(m["node_source"])[on_surface] < len(pts)).all()
