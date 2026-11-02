# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Cavity solvers on external tetrahedral meshes (docs/packages/galerkin/cavity_solver.md,
material_cavity.md, "External meshes").

Pre-registered gates of the 3D opening, measured on Gmsh-free meshes that
``meshine.extrude`` builds from an unstructured footprint:

M1  PEC box through ``solve_cavity``: TM110, TE101, TE011 against the analytic
    rectangular cavity over three refinements, order >= 1.8, finest <= 2e-3.
M2  the same box through ``solve_cavity_box``: on the box solver's own Kuhn mesh
    the two routes agree to <= 1e-10 (same assembly, same search); on the
    extruded mesh the difference between routes decreases with refinement
    (orders reported, extrusion cannot reproduce the alternating Kuhn box).
M3  dielectric slab as an extruded layer region through ``solve_material_cavity``
    against ``solve_material_cavity_box``: finest difference <= 5e-3.
M5  refusals: unknown wall tag, live inputs, missing faces.
Plus the gradient-kernel count of ``_cavity_common.gradient_potentials`` for
partial PEC (one, two and no components), verified by the dense eigenvalue path.
"""
import sys
import types

import numpy as np
import pytest

from galerkin import (CavityMaterialRegion, Mesh3D, box_mesh, from_mesher, solve_cavity,
                      solve_cavity_box, solve_material_cavity, solve_material_cavity_box)
from galerkin._cavity_common import C0, cavity_mesh, gradient_potentials
from conftest import rate

meshine = pytest.importorskip("meshine")

A, B, D = 1.0, 0.8, 0.6                   # metres; TM110 < TE101 < TE011 < TE111/TM111


def analytic(m, n, p):
    return 0.5 * C0 * np.sqrt((m / A) ** 2 + (n / B) ** 2 + (p / D) ** 2)


LOWEST = np.sort([analytic(1, 1, 0), analytic(1, 0, 1), analytic(0, 1, 1)])   # TM110, TE101, TE011
TARGET = float(np.sqrt(np.mean(LOWEST ** 2)))


def extruded_box(h, layers=((0.0, D),), materials=None):
    from meshine import Domain, box_sides, extrude, generate, rectangle
    d = Domain(size=h)
    d.add_region("cavity", rectangle(0, 0, A, B))
    z = [layers[0][0]] + [hi for _, hi in layers]
    tet = extrude(generate(d, box_sides(0, A, 0, B)), z, materials, size=h)
    return from_mesher(tet)


# -- M1 ----------------------------------------------------------------------

@pytest.mark.slow
def test_m1_pec_box_on_extruded_meshes_converges_to_the_analytic_resonances():
    sizes = (0.2, 0.1, 0.05)
    errors = []
    for h in sizes:
        result = solve_cavity(extruded_box(h), num_modes=3, target_frequency_hz=TARGET)
        assert result.pec_face_tags == ("z0", "z1", "left", "right", "bottom", "top") or \
            set(result.pec_face_tags) == {"z0", "z1", "left", "right", "bottom", "top"}
        errors.append(np.abs(result.frequencies_hz - LOWEST) / LOWEST)
    errors = np.array(errors)                                   # (3 meshes, 3 modes)
    worst = errors.max(axis=1)
    order = np.polyfit(np.log(sizes), np.log(worst), 1)[0]
    print(f"M1 relative errors per mesh {worst.tolist()} order {order:.3f}")
    assert order >= 1.8, (order, worst)
    assert worst[-1] <= 2e-3, worst


def test_m1_pec_box_on_a_coarse_extruded_mesh_is_within_a_few_percent():
    result = solve_cavity(extruded_box(0.2), num_modes=3, target_frequency_hz=TARGET)
    assert np.all(np.abs(result.frequencies_hz - LOWEST) / LOWEST < 0.05)
    assert result.mesh.num_tets == extruded_box(0.2).num_tets
    assert result.gradient_kernel_dimension == result.mesh.num_nodes - len(result.mesh.boundary_nodes())


# -- M2 ----------------------------------------------------------------------

@pytest.mark.parametrize("cells", [(2, 2, 2), (4, 3, 3)])
def test_m2_the_box_solver_mesh_gives_the_same_result_through_both_routes(cells):
    """Same Kuhn mesh, same assembly and search: dense (2,2,2) and sparse (4,3,3) paths."""
    box = solve_cavity_box((A, B, D), cells, num_modes=3, target_frequency_hz=TARGET)
    mesh = cavity_mesh((A, B, D), cells)
    mesh = Mesh3D(mesh.nodes, mesh.tets, mesh.boundary, mesh.regions, mesh.region_names,
                  tagged_faces=mesh.tagged_faces)
    through = solve_cavity(mesh, num_modes=3, target_frequency_hz=TARGET)
    difference = np.abs(through.frequencies_hz - box.frequencies_hz) / box.frequencies_hz
    print(f"M2 same-mesh route difference {difference.max():.3e} on {cells}")
    assert difference.max() <= 1e-10
    assert np.array_equal(through.pec_edge_ids, box.pec_edge_ids)
    assert through.gradient_kernel_dimension == box.gradient_kernel_dimension == int(np.prod(np.array(cells) - 1))
    assert np.allclose(np.abs(through.edge_coefficients), np.abs(box.edge_coefficients), atol=1e-9)


@pytest.mark.slow
def test_m2_extruded_mesh_and_box_route_approach_each_other_under_refinement():
    sizes = (0.2, 0.1, 0.05)
    differences = []
    for h in sizes:
        cells = tuple(int(round(L / h)) for L in (A, B, D))
        box = solve_cavity_box((A, B, D), cells, num_modes=3, target_frequency_hz=TARGET)
        through = solve_cavity(extruded_box(h), num_modes=3, target_frequency_hz=TARGET)
        differences.append(np.max(np.abs(through.frequencies_hz - box.frequencies_hz) / box.frequencies_hz))
    orders = rate(differences)
    print(f"M2 extruded-vs-box differences {differences} orders {orders.tolist()}")
    assert differences[0] > differences[1] > differences[2]


# -- M3 ----------------------------------------------------------------------

def _slab_pair(h, walls=None):
    eps_slab = 2.2 - 0.02j
    mesh = extruded_box(h, layers=((0.0, 0.3), (0.3, D)), materials={"cavity": ["slab", "air"]})
    cells = tuple(int(round(L / h)) for L in (A, B, D))
    target = TARGET / np.sqrt(1.4)
    box = solve_material_cavity_box(
        (A, B, D), cells, num_modes=3, target_frequency_hz=target,
        regions=[CavityMaterialRegion(((0, A), (0, B), (0, 0.3)), eps_slab, 1.0)],
        wall_conductivity_s_per_m=None if walls is None else {"z0": walls})
    through = solve_material_cavity(mesh, regions={"slab": (eps_slab, 1.0), "air": 1.0},
                                    walls=None if walls is None else {"z0": walls},
                                    num_modes=3, target_frequency_hz=target)
    return box, through


@pytest.mark.slow
def test_m3_dielectric_slab_layer_matches_the_box_solver_on_refinement():
    differences = []
    for h in (0.15, 0.1, 0.05):          # 0.3 m must be a grid plane of the box route
        box, through = _slab_pair(h)
        differences.append(np.max(np.abs(through.frequencies_hz - box.frequencies_hz)
                                  / np.abs(box.frequencies_hz)))
    print(f"M3 slab differences {differences}")
    assert differences[-1] <= 5e-3
    assert differences[0] > differences[-1]


def test_m3_dielectric_slab_layer_on_a_coarse_mesh_with_a_lossy_floor():
    box, through = _slab_pair(0.15, walls=5.8e7)
    assert through.lossless is False and box.lossless is False
    assert through.wall_conductivity_s_per_m["z0"] == 5.8e7
    assert all(v is None for k, v in through.wall_conductivity_s_per_m.items() if k != "z0")
    relative = np.abs(through.frequencies_hz - box.frequencies_hz) / np.abs(box.frequencies_hz)
    print(f"M3 coarse lossy-floor difference {relative.max():.3e}, Q {through.quality_factors}")
    assert relative.max() < 0.05
    assert np.all(np.isfinite(through.quality_factors)) and np.all(through.quality_factors > 10)
    assert through.fixed_point_iterations.max() >= 1


def test_material_cavity_on_the_box_solver_mesh_gives_the_same_result():
    cells = (2, 2, 2)
    region = CavityMaterialRegion(((0, A), (0, B), (0, 0.3)), 2.2 - 0.02j, 1.0)
    box = solve_material_cavity_box((A, B, D), cells, num_modes=3, target_frequency_hz=TARGET / 1.2,
                                    regions=[region], wall_conductivity_s_per_m={"x1": 1e7})
    mesh = cavity_mesh((A, B, D), cells)
    centroid_z = mesh.nodes[mesh.tets].mean(axis=1)[:, 2]
    mesh = Mesh3D(mesh.nodes, mesh.tets, mesh.boundary, regions=(centroid_z > 0.3).astype(int),
                  region_names=["slab", "air"], tagged_faces=mesh.tagged_faces)
    through = solve_material_cavity(mesh, regions={"slab": (2.2 - 0.02j, 1.0), "air": (1.0, 1.0)},
                                    walls={"x1": 1e7}, num_modes=3, target_frequency_hz=TARGET / 1.2)
    difference = np.abs(through.frequencies_hz - box.frequencies_hz) / np.abs(box.frequencies_hz)
    print(f"material same-mesh route difference {difference.max():.3e}")
    assert difference.max() <= 1e-10
    assert np.allclose(through.quality_factors, box.quality_factors, rtol=1e-8)


# -- gradient kernel on partial PEC ----------------------------------------

@pytest.mark.parametrize("tags,expected", [
    (("x0", "x1", "y0", "y1", "z0", "z1"), lambda n, g: n - g),
    (("z0", "z1"), lambda n, g: (n - 2 * 9) + 2 - 1),
    (("z0",), lambda n, g: (n - 9) + 1 - 1),
    ((), lambda n, g: n - 1),
])
def test_gradient_kernel_count_follows_the_pec_components(tags, expected):
    """2x2x2 box: 27 nodes, 9 per wall, boundary of 26 nodes; the dense path recounts the kernel."""
    mesh = box_mesh(A, B, D, 2, 2, 2)
    unit, components, count = gradient_potentials(mesh, mesh.faces_tagged(*tags))
    assert count == expected(mesh.num_nodes, len(mesh.boundary_nodes()))
    assert len(components) == (1 if tags == ("z0", "z1") else 0)
    assert count == len(unit) + len(components)
    result = solve_cavity(mesh, pec_faces=tags, num_modes=2, target_frequency_hz=TARGET)
    assert result.gradient_kernel_dimension == count
    assert result.pec_face_tags == tuple(tags)
    assert np.all(result.frequencies_hz > 0) and np.all(result.relative_residuals <= 1e-8)


def test_pec_on_top_and_bottom_only_is_a_parallel_plate_resonator():
    """PEC z0/z1, natural (PMC) sides: E = E_z(x, y) with Neumann sides has the Neumann
    Laplacian spectrum (m pi/a)^2 + (n pi/b)^2, m + n > 0, and the TE-like modes
    sin(p pi z/d) with p >= 1 add (p pi/d)^2; the lowest is (pi/a)^2 at c/(2a)."""
    mesh = cavity_mesh((A, B, D), (6, 5, 4))
    mesh = Mesh3D(mesh.nodes, mesh.tets, mesh.boundary, mesh.regions, mesh.region_names,
                  tagged_faces=mesh.tagged_faces)
    lowest = 0.5 * C0 / A
    result = solve_cavity(mesh, pec_faces=("z0", "z1"), num_modes=2, target_frequency_hz=lowest)
    expected = np.sort([lowest, 0.5 * C0 / B])
    assert np.all(np.abs(result.frequencies_hz - expected) / expected < 2e-2)


# -- M5 ----------------------------------------------------------------------

def test_m5_unknown_wall_tags_and_missing_faces_are_refused():
    mesh = extruded_box(0.3)
    with pytest.raises(ValueError, match="unknown face tag"):
        solve_cavity(mesh, pec_faces=("z0", "lid"), num_modes=2, target_frequency_hz=TARGET)
    with pytest.raises(ValueError, match="unknown face tag"):
        solve_material_cavity(mesh, regions={"cavity": 1.0}, walls={"x0": 1e7}, num_modes=2,
                              target_frequency_hz=TARGET)
    with pytest.raises(ValueError, match="match mesh.region_names"):
        solve_material_cavity(mesh, regions={"air": 1.0}, num_modes=2, target_frequency_hz=TARGET)
    bare = Mesh3D(mesh.nodes, mesh.tets, mesh.boundary, mesh.regions, mesh.region_names)
    with pytest.raises(ValueError, match="tagged boundary faces"):
        solve_cavity(bare, num_modes=2, target_frequency_hz=TARGET)
    with pytest.raises(TypeError, match="Mesh3D"):
        solve_cavity({"nodes": mesh.nodes}, num_modes=2, target_frequency_hz=TARGET)
    broken = Mesh3D(mesh.nodes, mesh.tets, regions=mesh.regions, region_names=mesh.region_names,
                    tagged_faces={k: v for k, v in mesh.tagged_faces.items() if k != "z1"})
    with pytest.raises(ValueError, match="carry no tag"):
        solve_cavity(broken, num_modes=2, target_frequency_hz=TARGET)


def test_m5_live_inputs_are_refused_on_the_mesh_variants(monkeypatch):
    """A stand-in for jax.Array (the libraries need not be installed): is_live checks by type."""
    class Array:
        pass
    monkeypatch.setitem(sys.modules, "jax", types.SimpleNamespace(Array=Array))
    mesh = extruded_box(0.3)
    with pytest.raises(TypeError, match="carries no derivative"):
        solve_cavity(mesh, num_modes=2, target_frequency_hz=Array())
    with pytest.raises(TypeError, match="carries no derivative"):
        solve_material_cavity(mesh, regions={"cavity": 1.0}, num_modes=2, target_frequency_hz=Array())
    with pytest.raises(TypeError, match="carries no derivative"):
        solve_material_cavity(mesh, regions={"cavity": (Array(), 1.0)}, num_modes=2,
                              target_frequency_hz=TARGET)
