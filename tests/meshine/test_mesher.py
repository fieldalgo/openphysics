# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Properties a finite-element solver relies on, checked against independent facts:
exact polygon areas, watertight tagged boundaries, the requested angle bound,
size control, nodes on true circles, and second-order quadrature convergence.
"""

import numpy as np
import pytest

from meshine import Circle, Domain, box_sides, generate, rectangle, shapes


def watertight(mesh):
    single = {tuple(r) for r in mesh.boundary_edge_set()}
    tagged = {tuple(sorted(r)) for arr in mesh.boundary_edges.values() for r in arr}
    return single == tagged


def test_unit_square_exact_area_and_angles():
    d = Domain(size=0.1)
    d.add_region("sq", rectangle(0, 0, 1, 1))
    m = generate(d, box_sides(0, 1, 0, 1), min_angle=30)
    assert abs(m.areas.sum() - 1.0) < 1e-12
    assert (m.areas > 0).all()
    assert m.min_angle() >= 30 - 1e-9
    assert set(m.boundary_edges) == {"left", "right", "top", "bottom"}
    assert watertight(m)


@pytest.mark.parametrize("t", [0.0, 0.3, 0.7])
def test_rib_waveguide_regions_exact_and_conforming(t):
    d, namer = shapes.rib_waveguide(slab_thickness=t, size_core=0.15, size_far=0.8)
    m = generate(d, namer, min_angle=28)
    assert m.region_names == ["core", "box", "clad"]
    assert abs(m.region_area("core") - (3.0 + 15.0 * t)) < 1e-9
    assert abs(m.region_area("box") - 180.0) < 1e-9
    assert abs(m.region_area("clad") - (54.0 - m.region_area("core"))) < 1e-9
    assert m.min_angle() >= 28 - 1e-9
    assert watertight(m)
    # every interface edge is shared by exactly two triangles of different regions
    tri_edges = {}
    for ti, tri in enumerate(m.triangles):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            tri_edges.setdefault(tuple(sorted((tri[a], tri[b]))), []).append(ti)
    for (ra, rb), edges in m.interfaces.items():
        for e in edges:
            owners = tri_edges[tuple(sorted(e))]
            assert len(owners) == 2
            assert {m.region_names[m.regions[owners[0]]], m.region_names[m.regions[owners[1]]]} == {ra, rb}


def test_size_control_per_region():
    d, namer = shapes.rib_waveguide(slab_thickness=0.3, size_core=0.1, size_far=0.8)
    m = generate(d, namer)
    L = m.edge_lengths()
    core = m.regions == m.region_names.index("core")
    box = m.regions == m.region_names.index("box")
    assert L[core].max() < 1.5 * 0.1              # circumradius bound => edges <= ~1.2 h
    deep = box & (m.nodes[m.triangles].mean(axis=1)[:, 1] < -3)
    assert np.median(L[deep]) > 0.4               # far field is really coarse
    assert L[box].max() < 1.5 * 0.8


def test_size_function_grades_the_mesh():
    d = Domain(size=0.5)
    d.add_region("sq", rectangle(-2, -2, 2, 2))
    m = generate(d, size_fn=shapes.size_graded(0.05, 0.5, 2.0))
    L = m.edge_lengths().max(axis=1)
    r = np.hypot(*m.nodes[m.triangles].mean(axis=1).T)
    assert L[r < 0.3].max() < 0.15               # h <= 0.117 there
    assert np.median(L[r > 1.8]) > 0.25


def test_fiber_nodes_lie_on_true_circles_and_area_converges():
    errs = []
    for h in (1.0, 0.5, 0.25):
        m = generate(shapes.circular_fiber(4.0, 20.0, size_core=h, size_clad=4 * h, n_core=16))
        iface = np.unique(m.interfaces[("clad", "core")])
        assert np.abs(np.hypot(*m.nodes[iface].T) - 4.0).max() < 1e-12
        assert np.abs(np.hypot(*m.nodes[m.boundary_nodes["outer"]].T) - 20.0).max() < 1e-12
        assert watertight(m)
        errs.append(abs(m.region_area("core") - np.pi * 16))
    rates = np.log2(np.array(errs[:-1]) / np.array(errs[1:]))
    assert (rates > 1.7).all()


def test_hole_and_named_boundaries():
    d = Domain(size=0.3)
    d.add_region("air", Circle((0, 0), 4.0, n=32), holes=[Circle((0, 0), 1.0, n=24)])
    m = generate(d, lambda mid: "pec" if np.hypot(*mid) < 2 else "abc")
    assert set(m.boundary_edges) == {"pec", "abc"}
    assert np.abs(np.hypot(*m.nodes[m.boundary_nodes["pec"]].T) - 1.0).max() < 1e-12
    assert abs(m.region_area("air") - 15 * np.pi) < 0.05        # polygonal error only
    assert watertight(m)
    # nothing was meshed inside the hole
    c = m.nodes[m.triangles].mean(axis=1)
    assert (np.hypot(*c.T) > 1.0 - 1e-9).all()


def test_l_shape_with_square_hole_t_junctions():
    d = Domain(size=0.1)
    d.add_region("L", [(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)], holes=[rectangle(0.25, 0.25, 0.75, 0.75)])
    m = generate(d, box_sides(0, 2, 0, 2))
    assert abs(m.areas.sum() - 2.75) < 1e-12
    assert "outer" in m.boundary_edges                          # the hole and the re-entrant edges
    assert watertight(m)
    assert m.min_angle() >= 28 - 1e-9


def test_quadrature_converges_at_second_order_on_unstructured_mesh():
    # integrate a smooth function over an L-shaped domain with the edge-midpoint rule
    f = lambda x, y: np.exp(x) * np.cos(y)
    Fx = lambda a, b: np.exp(b) - np.exp(a)
    Fy = lambda a, b: np.sin(b) - np.sin(a)
    exact = Fx(0, 2) * Fy(0, 1) + Fx(0, 1) * Fy(1, 2)
    errs = []
    for h in (0.2, 0.1, 0.05):
        d = Domain(size=h)
        d.add_region("L", [(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)])
        m = generate(d, size_fn=lambda x, y, h=h: h * (1 + 0.5 * np.sin(3 * x) ** 2))   # deliberately irregular
        p = m.nodes[m.triangles]
        mids = (p[:, [1, 2]].mean(1), p[:, [0, 2]].mean(1), p[:, [0, 1]].mean(1))
        val = sum((m.areas * f(q[:, 0], q[:, 1])).sum() for q in mids) / 3
        errs.append(abs(val - exact))
    rates = np.log2(np.array(errs[:-1]) / np.array(errs[1:]))
    assert (rates > 1.8).all()


def test_input_validation():
    with pytest.raises(ValueError):
        generate(Domain())
    with pytest.raises(ValueError):
        shapes.rib_waveguide(slab_thickness=1.0)
    with pytest.raises(ValueError):
        Circle((0, 0), -1)
    d = Domain(size=0.2)
    d.add_region("a", rectangle(0, 0, 1, 1))
    with pytest.raises(ValueError):
        generate(d, min_angle=40)


def test_same_name_regions_merge_into_one_material():
    d = Domain(size=0.3)
    d.add_region("core", rectangle(-1, 0, 1, 0.5), size=0.1)
    d.add_region("clad", [(-3, -2), (3, -2), (3, 0.5), (1, 0.5), (1, 0), (-1, 0), (-1, 0.5), (-3, 0.5)])
    d.add_region("clad", rectangle(-3, 0.5, 3, 2))
    m = generate(d, box_sides(-3, 3, -2, 2))
    assert m.region_names == ["core", "clad"]
    assert set(np.unique(m.regions)) == {0, 1}
    assert list(m.interfaces) == [("clad", "core")]
    assert abs(m.region_area("clad") - 23.0) < 1e-9
    assert watertight(m)


def test_edge_keys_do_not_overflow_int32():
    # Qhull returns int32 simplices; with > 46341 points min*n + max exceeds 2^31
    from meshine.refine import _edge_keys
    n = 60000
    simp = np.array([[59999, 59998, 1]], dtype=np.int32)
    keys = _edge_keys(simp, n)
    assert keys.dtype == np.int64
    assert 59998 * n + 59999 in keys
