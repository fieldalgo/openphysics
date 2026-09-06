# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""End-to-end tests: write .geo -> run gmsh -> read .msh -> FEM arrays.

Skipped when no gmsh executable is available. The checks are the ones a
solver relies on: exact areas/volumes of polygonal regions, consistent
orientation, watertight boundaries, and nodes that really sit on curved
interfaces.
"""

import numpy as np
import pytest

from gmshio import find_gmsh, generate, geo, to_fem2d, to_fem3d

pytestmark = pytest.mark.skipif(find_gmsh() is None, reason="gmsh executable not found")


def _boundary_matches_single_use_edges(fem):
    e = np.vstack([fem.triangles[:, [0, 1]], fem.triangles[:, [1, 2]], fem.triangles[:, [2, 0]]])
    e.sort(axis=1)
    uniq, counts = np.unique(e, axis=0, return_counts=True)
    assert set(counts) <= {1, 2}                      # manifold: no edge in 3 triangles
    single = {tuple(r) for r in uniq[counts == 1]}
    tagged = {tuple(sorted(r)) for arr in fem.boundary_edges.values() for r in arr}
    assert single == tagged                           # tagged boundary == geometric boundary


@pytest.mark.parametrize("t", [0.0, 0.3, 0.7])
def test_rib_waveguide_regions_are_exact(t):
    fem = to_fem2d(generate(geo.rib_waveguide(slab_thickness=t, lc_core=0.15, lc_far=0.8), dim=2, verbosity=0))
    assert fem.region_names == ["core", "box", "clad"]
    assert (fem.regions >= 0).all()
    assert (fem.areas > 0).all()
    assert abs(fem.region_area("core") - (3.0 * 1.0 + (18.0 - 3.0) * t)) < 1e-9
    assert abs(fem.region_area("box") - 18.0 * 10.0) < 1e-9
    assert abs(fem.region_area("clad") - (18.0 * 3.0 - fem.region_area("core"))) < 1e-9
    assert set(fem.boundary_edges) == {"left", "right", "top", "bottom"}
    _boundary_matches_single_use_edges(fem)


def test_rib_mesh_is_refined_in_the_core():
    fem = to_fem2d(generate(geo.rib_waveguide(slab_thickness=0.3, lc_core=0.1, lc_far=0.8), dim=2, verbosity=0))
    core = fem.regions == fem.region_names.index("core")
    box = fem.regions == fem.region_names.index("box")
    equilateral = np.sqrt(3) / 4
    assert np.median(fem.areas[core]) < 1.5 * equilateral * 0.1 ** 2     # core at lc_core
    assert fem.areas[box].max() > 0.5 * equilateral * 0.8 ** 2          # far field at lc_far


def test_fiber_core_nodes_lie_on_the_circle_and_area_converges():
    a, R = 4.0, 20.0
    errs = []
    for lc in (1.0, 0.5):
        fem = to_fem2d(generate(geo.circular_fiber(a, R, lc_core=lc, lc_clad=4 * lc), dim=2, verbosity=0))
        assert (fem.areas > 0).all()
        _boundary_matches_single_use_edges(fem)
        # nodes shared by core and clad triangles are on the interface -> on the true circle
        core_nodes = set(fem.triangles[fem.regions == fem.region_names.index("core")].ravel())
        clad_nodes = set(fem.triangles[fem.regions == fem.region_names.index("clad")].ravel())
        iface = np.array(sorted(core_nodes & clad_nodes))
        r = np.hypot(*fem.nodes[iface].T)
        assert np.abs(r - a).max() < 1e-9
        errs.append(abs(fem.region_area("core") - np.pi * a ** 2))
    rate = np.log2(errs[0] / errs[1])
    assert rate > 1.7                                 # polygonal area error is O(h^2)


def test_box_cavity_volume_and_watertight_boundary():
    a, b, d = 1.0, 0.5, 0.75
    fem = to_fem3d(generate(geo.box_cavity(a, b, d, lc=0.2), dim=3, verbosity=0))
    assert fem.region_names == ["cavity"]
    assert (fem.volumes > 0).all()
    assert abs(fem.region_volume("cavity") - a * b * d) < 1e-9
    # faces of tets: boundary faces appear once, interior faces twice
    T = fem.tetrahedra
    f = np.vstack([T[:, [0, 1, 2]], T[:, [0, 1, 3]], T[:, [0, 2, 3]], T[:, [1, 2, 3]]])
    f.sort(axis=1)
    uniq, counts = np.unique(f, axis=0, return_counts=True)
    assert set(counts) == {1, 2}
    single = {tuple(r) for r in uniq[counts == 1]}
    tagged = {tuple(sorted(r)) for r in fem.boundary_faces["pec"]}
    assert single == tagged
    # boundary nodes really are on the box surface
    p = fem.nodes[fem.boundary_nodes["pec"]]
    on = (np.abs(p) < 1e-9) | (np.abs(p - [a, b, d]) < 1e-9)
    assert on.any(axis=1).all()


def test_second_order_is_rejected_by_fem_conversion():
    m = generate(geo.box_cavity(1, 1, 1, lc=0.5), dim=3, order=2, verbosity=0)
    assert "tetra10" in m.cell_types()
    with pytest.raises(ValueError):
        to_fem3d(m)
