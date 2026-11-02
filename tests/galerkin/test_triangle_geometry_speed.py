# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The mesh check caches its validated output by mesh content and keeps its decisions.

Pre-registered criteria of the validation-speed work (docs/packages/galerkin/overview.md,
"Mesh validation cache"):
  C1  a repeated call returns equal arrays, the same boundary set and component
      labels, as fresh copies: changing a result never changes the next one;
  C2  a mesh changed in place after a call is validated again: a now-invalid
      mesh is rejected, a shifted mesh returns the shifted coordinates;
  C3  dtype, vertex order and the orientation flag are part of the key, the
      cache holds at most GEOMETRY_CACHE_ENTRIES meshes and drops the least
      recently used one, and rejected meshes are never cached;
  C4  constructed bad meshes are rejected with the messages the solvers'
      contracts document, on every call;
  C5  the second call on a mesh is far cheaper than the first (times printed).
"""
import time

import numpy as np
import pytest

import galerkin.core.triangles as triangles
from galerkin.core.triangles import GEOMETRY_CACHE_ENTRIES, clear_geometry_cache, edge_table, triangle_geometry
from galerkin.mesh import Mesh, rectangle_mesh


@pytest.fixture(autouse=True)
def empty_cache():
    clear_geometry_cache()
    yield
    clear_geometry_cache()


def _raw(nodes, triangles):
    """A Mesh whose triangles keep the given vertex order (Mesh() reorients them)."""
    mesh = rectangle_mesh(1., 1., 1, 1)
    mesh.nodes, mesh.triangles = np.asarray(nodes), np.asarray(triangles)
    mesh.boundary, mesh.boundary_edges = {}, {}
    return mesh


def _same(a, b):
    p, t, area, boundary, count, labels = a
    q, u, brea, boundary2, count2, labels2 = b
    return (np.array_equal(p, q) and p.dtype == q.dtype and np.array_equal(t, u) and t.dtype == u.dtype
            and np.array_equal(area, brea) and boundary == boundary2 and count == count2
            and np.array_equal(labels, labels2) and labels.dtype == labels2.dtype)


def test_c1_repeated_call_returns_equal_fresh_copies():
    mesh = rectangle_mesh(1., .5, 6, 3)
    first = triangle_geometry(mesh)
    second = triangle_geometry(mesh)
    assert _same(first, second)
    assert isinstance(second[3], set)
    for a, b in zip(first, second):
        if isinstance(a, np.ndarray):
            assert a is not b and not np.shares_memory(a, b)
    assert second[1] is not mesh.triangles and not np.shares_memory(second[1], mesh.triangles)
    # A caller that changes its copies does not change what the next caller gets.
    second[0][:] = 0.
    second[1][:] = 0
    second[2][:] = -1.
    second[3].clear()
    second[5][:] = 7
    assert _same(first, triangle_geometry(mesh))


def test_c2_in_place_change_is_validated_again():
    mesh = rectangle_mesh(1., 1., 2, 2)
    before = triangle_geometry(mesh)
    # Dragging the centre node outside the square turns the right triangles over.
    mesh.nodes[4] = [1.5, .5]
    with pytest.raises(ValueError, match="counter-clockwise and nondegenerate"):
        triangle_geometry(mesh)
    mesh.nodes[4] = [.5, .5]
    assert _same(before, triangle_geometry(mesh))
    # The simcase runner shifts a mesh in place (mesh.nodes += origin).
    mesh.nodes += [10., -3.]
    shifted = triangle_geometry(mesh)
    assert np.array_equal(shifted[0], mesh.nodes) and np.array_equal(shifted[0]-[10., -3.], before[0])
    assert np.array_equal(shifted[2], before[2]) and shifted[3] == before[3]
    # Rewiring the connectivity in place is seen too.
    mesh.triangles[0] = mesh.triangles[0, [0, 2, 1]]
    with pytest.raises(ValueError, match="counter-clockwise"):
        triangle_geometry(mesh)


def test_c3_dtype_order_and_orientation_flag_are_distinct_keys():
    mesh = rectangle_mesh(2., 1., 3, 2)
    triangle_geometry(mesh)
    assert len(triangles._geometry_cache) == 1
    narrow = _raw(mesh.nodes, mesh.triangles)
    narrow.nodes = mesh.nodes.astype(np.float32)
    triangle_geometry(narrow)
    assert len(triangles._geometry_cache) == 2, "a float32 copy of the same values is another entry"
    small = _raw(mesh.nodes, mesh.triangles.astype(np.int32))
    triangle_geometry(small)
    assert len(triangles._geometry_cache) == 3
    assert triangle_geometry(small)[1].dtype == np.int32
    clockwise = _raw(mesh.nodes, mesh.triangles[:, ::-1])
    accepted = triangle_geometry(clockwise, counterclockwise=False)
    assert np.array_equal(accepted[1], mesh.triangles[:, ::-1])
    with pytest.raises(ValueError, match="counter-clockwise"):
        triangle_geometry(clockwise)                    # the flag is part of the key
    with pytest.raises(ValueError, match="counter-clockwise"):
        triangle_geometry(clockwise)                    # and a rejection is never cached
    assert len(triangles._geometry_cache) == 4
    permuted = _raw(mesh.nodes, mesh.triangles[::-1])
    assert np.array_equal(triangle_geometry(permuted)[1], mesh.triangles[::-1])
    assert len(triangles._geometry_cache) == 5


def test_c3_cache_is_bounded_and_drops_the_least_recently_used():
    meshes = [rectangle_mesh(1., 1., 1, n) for n in range(1, GEOMETRY_CACHE_ENTRIES+3)]
    for mesh in meshes:
        triangle_geometry(mesh)
    assert len(triangles._geometry_cache) == GEOMETRY_CACHE_ENTRIES
    kept = list(triangles._geometry_cache)
    triangle_geometry(meshes[-1])                       # a hit: nothing added
    assert list(triangles._geometry_cache)[-1] == kept[-1] and len(triangles._geometry_cache) == GEOMETRY_CACHE_ENTRIES
    triangle_geometry(meshes[2])                        # the oldest kept entry becomes the newest
    assert list(triangles._geometry_cache) == kept[1:]+kept[:1]
    triangle_geometry(meshes[0])                        # evicted earlier: re-validated, drops kept[1]
    assert len(triangles._geometry_cache) == GEOMETRY_CACHE_ENTRIES
    assert list(triangles._geometry_cache)[:2] == [kept[2], kept[3]]


def test_c3_live_or_non_numeric_arrays_are_not_hashed():
    assert triangles._content_key(np.zeros((3, 2), dtype=bool), np.zeros((1, 3), dtype=int), True) is None
    assert triangles._content_key(np.zeros((3, 2)), np.zeros((1, 3)), True) is None
    assert triangles._content_key(np.array([[0., 0.], [1., "a"]], dtype=object), np.zeros((1, 3), dtype=int), True) is None
    key = triangles._content_key(np.zeros((3, 2)), np.zeros((1, 3), dtype=int), True)
    assert key == triangles._content_key(np.zeros((3, 2), order="F"), np.zeros((1, 3), dtype=int), True)
    assert key != triangles._content_key(np.zeros((3, 2)), np.zeros((1, 3), dtype=int), False)


def test_c3_edge_table_is_cached_read_only_and_cleared_with_the_geometry():
    mesh = rectangle_mesh(1., 1., 2, 2)
    edges, counts, slots = edge_table(mesh.triangles, mesh.num_nodes)
    assert edges.shape == (16, 2) and np.all(edges[:, 0] < edges[:, 1])
    assert np.array_equal(np.lexsort((edges[:, 1], edges[:, 0])), np.arange(16))
    assert sorted(counts.tolist()) == [1]*8+[2]*8 and len(slots) == 24
    assert set(np.unique(edges[counts == 1]).tolist()) == triangle_geometry(mesh)[3]
    again = edge_table(mesh.triangles.copy(), mesh.num_nodes)
    assert all(a is b for a, b in zip((edges, counts, slots), again))
    assert not any(a.flags.writeable for a in again)
    assert edge_table(mesh.triangles.astype(np.int32), mesh.num_nodes)[0] is not edges
    clear_geometry_cache()
    assert not triangles._edge_cache and not triangles._geometry_cache


def _grid():
    return rectangle_mesh(1., 1., 2, 2)


BAD = {
    "two overlapping triangles": (
        lambda: Mesh([[0., 0.], [1., 0.], [0., 1.], [.2, .2], [1.2, .2], [.2, 1.2]], [[0, 1, 2], [3, 4, 5]], {}),
        "mesh triangles have overlapping interiors"),
    "node inside another triangle's edge": (
        lambda: Mesh([[0., 0.], [1000., 0.], [0., 1000.], [500., 0.], [499.5, -.5], [500.5, -.5]],
                     [[0, 1, 2], [3, 4, 5]], {}),
        "nonconforming mesh: node inside an edge"),
    "hanging node": (
        lambda: Mesh([[0., 0.], [1., 0.], [0., 1.], [.5, 0.], [.5, -.5]], [[0, 1, 2], [0, 4, 3], [3, 4, 1]], {}),
        "nonmanifold vertex or triangles joined only at a point"),
    "bow tie": (
        lambda: Mesh([[0, 0], [1, 0], [0, 1], [-1, 0], [0, -1]], [[0, 1, 2], [0, 3, 4]], {}),
        "nonmanifold vertex or triangles joined only at a point"),
    "two fans at one vertex": (
        lambda: Mesh([[0., 0.], [1., 0.], [1., 1.], [0., 1.], [-1., 1.], [-1., 0.]],
                     [[0, 1, 2], [0, 2, 3], [0, 4, 5]], {}),
        "nonmanifold vertex or triangles joined only at a point"),
    "inverted triangle": (
        lambda: _raw(_grid().nodes, np.vstack([_grid().triangles[:1, ::-1], _grid().triangles[1:]])),
        "triangles must be counter-clockwise and nondegenerate"),
    "duplicate triangle": (
        lambda: Mesh(_grid().nodes, np.vstack([_grid().triangles, _grid().triangles[:1]]), {}),
        "mesh contains duplicate triangles"),
    "three triangles on one edge": (
        lambda: Mesh([[0., 0.], [1., 0.], [0., 1.], [0., -1.], [1., 1.]], [[0, 1, 2], [0, 3, 1], [0, 1, 4]], {}),
        "nonmanifold mesh edge"),
    "unused node": (
        lambda: Mesh(np.vstack([_grid().nodes, [[5., 5.]]]), _grid().triangles, {}),
        "mesh contains unused nodes"),
    "degenerate triangle": (
        lambda: Mesh(_grid().nodes, np.vstack([_grid().triangles, [[0, 1, 2]]]), {}),
        "triangles must be counter-clockwise and nondegenerate"),
}


@pytest.mark.parametrize("name", BAD)
def test_c4_constructed_bad_meshes_are_rejected_on_every_call(name):
    build, message = BAD[name]
    mesh = build()
    for _ in range(2):
        with pytest.raises(ValueError, match=message):
            triangle_geometry(mesh)
    assert not triangles._geometry_cache


def test_c5_second_call_is_far_cheaper(capsys):
    mesh = rectangle_mesh(1., .5, 64, 32)
    start = time.perf_counter()
    first = triangle_geometry(mesh)
    cold = time.perf_counter()-start
    start = time.perf_counter()
    second = triangle_geometry(mesh)
    warm = time.perf_counter()-start
    assert _same(first, second)
    with capsys.disabled():
        print(f"\ntriangle_geometry n=32 (2145 nodes): first {cold*1e3:.1f} ms, cached {warm*1e3:.2f} ms")
    assert warm < cold/5
