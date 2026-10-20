# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The 2D mesh overlap check finds its candidates within each triangle's own reach.

The thermal and elasticity mesh checks reject overlapping triangle interiors.
With r the largest centroid-to-vertex distance of a triangle, two interiors can
overlap only if |c_i - c_k| < r_i + r_k. The checks used to query every centroid
with r_i + max(r), so one large triangle made every query cover most of the
mesh. They now query each centroid with 2*r_i and keep a pair found from either
side.

Pre-registered criteria:
  G1  after the strict filter the candidate pairs equal a chunked O(M^2) brute
      force, and include every pair the old query kept;
  G2  a crafted overlap with radius ratio 1e3 still raises, and touching
      triangles still pass the overlap test, in both checks;
  G3  on a graded annulus (M = 6400) the centroid query of each check returns
      at most 50*M indices. The old query returns about 24 million there; it
      is not run.
The old query stays below as a private reference, so nothing is stored.
"""
import numpy as np
import pytest
from scipy.spatial import Delaunay, cKDTree

import galerkin.elasticity as elasticity
import galerkin.thermal as thermal
from galerkin.elasticity import solve_elasticity
from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.thermal import solve_steady_heat

OVERLAP = "mesh triangles have overlapping interiors"


def _discs(nodes, triangles):
    # The mesh check's own expressions, so the filter below sees identical floats.
    q = np.asarray(nodes, dtype=float)[np.asarray(triangles)]
    centers = q.mean(axis=1)
    return centers, np.linalg.norm(q-centers[:, None], axis=2).max(axis=1)


def _strict(centers, radii, i, ids):
    # The mesh check's strict filter, verbatim.
    return ids[np.linalg.norm(centers[ids]-centers[i], axis=1) < radii[ids]+radii[i]]


def _new_pairs(centers, radii):
    candidates, kept = set(), set()
    for i, ids in thermal._overlap_candidates(centers, radii):
        assert np.all(ids > i) and np.all(np.diff(ids) > 0)
        candidates.update((i, int(k)) for k in ids)
        kept.update((i, int(k)) for k in _strict(centers, radii, i, ids))
    return candidates, kept


def _old_pairs(centers, radii, chunk=256):
    """The query the checks used before this change, after the strict filter.

    The same per-centroid query with radius r_i + max(r), run on blocks of
    centroids: each centroid gets the same list, with bounded memory.
    """
    tree, kept = cKDTree(centers), set()
    for start in range(0, len(centers), chunk):
        stop = min(start+chunk, len(centers))
        found = tree.query_ball_point(centers[start:stop], radii[start:stop]+radii.max())
        for i, candidates in enumerate(found, start):
            ids = np.array([k for k in candidates if k > i], dtype=int)
            if len(ids):
                kept.update((i, int(k)) for k in _strict(centers, radii, i, ids))
    return kept


def _brute_force(centers, radii, chunk=256):
    """Every pair i < k with |c_i - c_k| < r_i + r_k, one block of rows at a time.

    Same arithmetic as the strict filter: c_k - c_i, its 2-norm, r_k + r_i.
    """
    every, kept = np.arange(len(centers)), set()
    for start in range(0, len(centers), chunk):
        rows = every[start:start+chunk]
        distance = np.linalg.norm(centers[None, :, :]-centers[rows, None, :], axis=2)
        hit = (distance < radii[None, :]+radii[rows, None]) & (every[None, :] > rows[:, None])
        a, b = np.nonzero(hit)
        kept.update(zip(rows[a].tolist(), b.tolist()))
    return kept


def _delaunay(points, seed):
    # Points crowd into one corner, so sizes span orders of magnitude and the
    # convex hull adds long slivers: the case that made the old query global.
    xy = np.random.default_rng(seed).random((points, 2))**3
    return xy, Delaunay(xy).simplices


def _grid(spacing, origin):
    mesh = rectangle_mesh(30*spacing, 20*spacing, 30, 20)
    return mesh.nodes+origin, mesh.triangles


def _graded_annulus(per_ring=32, layers=100, ratio=1.1):
    """Rings of radius ratio**k, alternate rings turned by half a step."""
    angle = 2*np.pi*np.arange(per_ring)/per_ring
    nodes = np.vstack([ratio**k*np.column_stack([np.cos(angle+(k % 2)*np.pi/per_ring),
                                                 np.sin(angle+(k % 2)*np.pi/per_ring)])
                       for k in range(layers+1)])
    triangles = []
    for k in range(layers):
        a, b = k*per_ring, (k+1)*per_ring
        for j in range(per_ring):
            n = (j+1) % per_ring
            triangles += ([[a+j, a+n, b+j], [a+n, b+n, b+j]] if k % 2 == 0 else
                          [[a+j, a+n, b+n], [a+j, b+n, b+j]])
    return nodes, np.array(triangles)


MESHES = {
    "delaunay-200": lambda: _delaunay(110, 1),
    "delaunay-800": lambda: _delaunay(410, 2),
    "delaunay-2000": lambda: _delaunay(1010, 3),
    # Integer centroids: radii tie exactly and many pairs sit at exactly r_i + r_k.
    "grid-exact-ties": lambda: _grid(3., np.array([0., 0.])),
    # The same ties broken only by rounding, on both sides of the strict bound.
    "grid-rounded-ties": lambda: _grid(.1, np.array([.37, .185])),
    "graded-annulus": _graded_annulus,
}


@pytest.mark.parametrize("name", MESHES)
def test_g1_candidates_after_strict_filter_equal_brute_force(name):
    centers, radii = _discs(*MESHES[name]())
    candidates, kept = _new_pairs(centers, radii)
    brute = _brute_force(centers, radii)
    assert kept == brute
    assert brute <= candidates
    if name != "graded-annulus":  # the old query returns ~24 million indices there
        assert _old_pairs(centers, radii) <= kept
    print(f"{name}: M={len(centers)} candidates={len(candidates)} strict={len(brute)}")


def test_g1_meshes_have_the_intended_sizes():
    sizes = {name: len(build()[1]) for name, build in MESHES.items()}
    assert 150 <= sizes["delaunay-200"] <= 250
    assert 700 <= sizes["delaunay-800"] <= 900
    assert 1800 <= sizes["delaunay-2000"] <= 2200
    assert sizes["graded-annulus"] == 6400
    # Exact: integer coordinates and centroids leave nothing to round.
    assert np.ptp(_discs(*MESHES["grid-exact-ties"]())[1]) == 0
    radii = _discs(*MESHES["grid-rounded-ties"]())[1]
    assert np.ptp(radii) <= 1e-12*radii.max()


@pytest.mark.parametrize("name", ["delaunay-800", "graded-annulus"])
def test_candidates_do_not_depend_on_the_query_block(name):
    # The helper queries centroids in blocks; any block size gives the same pairs.
    centers, radii = _discs(*MESHES[name]())

    def listed(block):
        return [(i, ids.tolist()) for i, ids in
                thermal._overlap_candidates(centers, radii, block=block)]
    whole = listed(len(centers))
    for block in (1, 7, 4096):
        assert listed(block) == whole


def _big_around_small(small_first):
    # Similar right triangles, the small one inside the large one: r ratio 1e3.
    big = [[0., 0.], [1000., 0.], [0., 1000.]]
    small = [[100., 100.], [101., 100.], [100., 101.]]
    nodes = small+big if small_first else big+small
    return Mesh(nodes, [[0, 1, 2], [3, 4, 5]], {})


def _thermal(mesh):
    return solve_steady_heat(mesh, conductivity=1., dirichlet={0: 300.})


def _elasticity(mesh):
    fixed = {(node, component): 0. for node in (0, 1) for component in (0, 1)}
    return solve_elasticity(mesh, young_modulus=1e9, poisson_ratio=.3, plane="stress",
                            dirichlet=fixed, body_force=(0., -1e3))


CHECKS = {"thermal": _thermal, "elasticity": _elasticity}


@pytest.mark.parametrize("small_first", [True, False])
@pytest.mark.parametrize("check", CHECKS)
def test_g2_overlap_across_radius_ratio_1e3_still_raises(check, small_first):
    mesh = _big_around_small(small_first)
    centers, radii = _discs(mesh.nodes, mesh.triangles)
    small, big = np.argsort(radii)
    assert radii[big]/radii[small] == pytest.approx(1e3, rel=1e-12)
    # The small triangle's own query cannot reach the large centroid; only the
    # large triangle's query finds the pair.
    assert np.linalg.norm(centers[big]-centers[small]) > 2*radii[small]
    with pytest.raises(ValueError, match=OVERLAP):
        CHECKS[check](mesh)


def _sliver_on_small():
    # A 1000 m sliver shares its 1 m base with a unit equilateral triangle.
    nodes = [[0., 0.], [1., 0.], [.5, 1000.], [.5, -np.sqrt(.75)]]
    return Mesh(nodes, [[0, 1, 2], [1, 0, 3]], {})


def _small_touching_big_edge():
    # The small triangle's apex lies inside the large triangle's bottom edge.
    nodes = [[0., 0.], [1000., 0.], [0., 1000.], [500., 0.], [499.5, -.5], [500.5, -.5]]
    return Mesh(nodes, [[0, 1, 2], [3, 4, 5]], {})


@pytest.mark.parametrize("check", CHECKS)
def test_g2_touching_triangles_still_pass_the_overlap_test(check):
    shared = _sliver_on_small()
    radii = _discs(shared.nodes, shared.triangles)[1]
    assert radii.max()/radii.min() > 1e3
    CHECKS[check](shared)  # a conforming mesh: accepted and solved
    touching = _small_touching_big_edge()
    radii = _discs(touching.nodes, touching.triangles)[1]
    assert radii.max()/radii.min() > 1e3
    # Rejected, but by the later hanging-node test: the interiors only touch.
    with pytest.raises(ValueError, match="nonconforming mesh: node inside an edge"):
        CHECKS[check](touching)


def _counting_tree(returned):
    class CountingTree(cKDTree):
        def query_ball_point(self, x, r, *args, **kwargs):
            found = super().query_ball_point(x, r, *args, **kwargs)
            if np.ndim(r):  # one radius per centroid: the overlap query
                returned.append(sum(map(len, found)))
            return found
    return CountingTree


GEOMETRY = {"thermal": (thermal._mesh_geometry, [thermal]),
            "elasticity": (elasticity._mesh_data, [thermal, elasticity])}


@pytest.mark.parametrize("check", GEOMETRY)
def test_g3_graded_annulus_query_is_local(check, monkeypatch):
    nodes, triangles = _graded_annulus()
    mesh = Mesh(nodes, triangles, {})
    radii = _discs(mesh.nodes, mesh.triangles)[1]
    assert len(triangles) == 6400 and radii.max()/radii.min() > 1e4
    function, modules = GEOMETRY[check]
    returned = []
    for module in modules:
        monkeypatch.setattr(module, "cKDTree", _counting_tree(returned))
    function(mesh)  # a valid conforming mesh
    assert returned, "the centroid query was not observed"
    assert sum(returned) <= 50*len(triangles)
    print(f"{check}: M={len(triangles)} returned={sum(returned)} in {len(returned)} queries")
