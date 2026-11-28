# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Analytical fields, side-by-side power balances and geometry checks for thermal contact."""
import numpy as np
import pytest

from galerkin.mesh3d import Mesh3D, box_mesh
from galerkin.thermal3d import solve_steady_heat_3d


LEFT, RIGHT, WIDTH, DEPTH = 0.5, 0.75, 0.5, 0.25  # m
AREA = WIDTH * DEPTH
CONDUCTIVITY = {"left": 2.5, "right": 8.0}  # W/(m K)
CONTACT = ("left_x1", "right_x0")


def two_slabs(n=2, *, gap=0.0, flip_diagonal=False):
    left = box_mesh(LEFT, WIDTH, DEPTH, n, n, n)
    right = box_mesh(RIGHT, WIDTH, DEPTH, n, n, n)
    # Mirror the numbering on the second slab and permute the face representation.
    # Matching triangles and shape functions by their array position would be wrong.
    right_nodes = right.nodes[::-1].copy()
    right_nodes[:, 0] += LEFT + gap
    right_ids = left.num_nodes + np.arange(right.num_nodes)[::-1]
    faces = {"left_" + tag: tris for tag, tris in left.tagged_faces.items()}
    for tag, tris in right.tagged_faces.items():
        reordered = np.roll(tris[::-1], 1, axis=1)
        faces["right_" + tag] = right_ids[reordered[:, ::-1] if flip_diagonal else reordered]
    if flip_diagonal:
        right_nodes[:, 1] = WIDTH - right_nodes[:, 1]
    return Mesh3D(np.vstack([left.nodes, right_nodes]), np.vstack([left.tets, right_ids[right.tets]]),
                  regions=np.repeat([0, 1], [left.num_tets, right.num_tets]),
                  region_names=["left", "right"], tagged_faces=faces)


def end_temperatures(mesh, left, right):
    return {node: value for tag, value in [("left_x0", left), ("right_x1", right)]
            for node in mesh.boundary[tag]}


@pytest.mark.parametrize(("h", "left_end", "right_end"), [
    (1e-10, 320.0, 300.0), (1e-6, 320.0, 300.0), (0.01, 320.0, 300.0), (6.0, 320.0, 300.0),
    (10000.0, 320.0, 300.0), (6.0, 300.0, 320.0),
])
def test_series_resistance_fields_and_power(h, left_end, right_end):
    mesh = two_slabs()
    result = solve_steady_heat_3d(
        mesh, thermal_conductivity=CONDUCTIVITY, prescribed_temperature=end_temperatures(mesh, left_end, right_end),
        thermal_contact_conductance={CONTACT: h},
    )
    k_left, k_right = CONDUCTIVITY["left"], CONDUCTIVITY["right"]
    flux = (left_end - right_end) / (LEFT / k_left + 1 / h + RIGHT / k_right)
    left_nodes = np.unique(mesh.tets[mesh.regions == 0])
    right_nodes = np.unique(mesh.tets[mesh.regions == 1])
    x = mesh.nodes[:, 0]
    np.testing.assert_allclose(result.temperature[left_nodes], left_end - flux * x[left_nodes] / k_left,
                               rtol=0, atol=2e-9)
    np.testing.assert_allclose(result.temperature[right_nodes],
                               right_end + flux * (LEFT + RIGHT - x[right_nodes]) / k_right, rtol=0, atol=2e-9)
    np.testing.assert_allclose(result.heat_flux[:, 0], flux, rtol=1e-9, atol=1e-9)
    np.testing.assert_allclose(result.heat_flux[:, 1:], 0.0, atol=1e-8)
    left_trace, right_trace = (mesh.boundary[tag] for tag in CONTACT)
    jump = result.temperature[left_trace].mean() - result.temperature[right_trace].mean()
    assert jump == pytest.approx(flux / h, rel=1e-8)
    assert result.contact_heat_rate[left_trace].sum() == pytest.approx(AREA * flux, rel=2e-9)
    assert result.contact_heat_rate[right_trace].sum() == pytest.approx(-AREA * flux, rel=2e-9)
    other_nodes = np.setdiff1d(np.arange(mesh.num_nodes), np.r_[left_trace, right_trace])
    np.testing.assert_array_equal(result.contact_heat_rate[other_nodes], 0)
    for nodes in (left_nodes, right_nodes):
        assert result.reaction_heat_rate[nodes].sum() == pytest.approx(result.contact_heat_rate[nodes].sum(),
                                                                     rel=2e-9)
    assert result.relative_conservation_residual <= 1e-10


def test_linear_temperature_jump_integrated_on_each_triangle():
    mesh = two_slabs(1)
    left = np.unique(mesh.tets[mesh.regions == 0])
    y, z = mesh.nodes[:, 1:].T
    jump = 2.0 + 4.0*y - 3.0*z
    temperature = 300 + y - 0.2*z
    temperature[left] += jump[left]
    # All nodes on this mesh are exterior. Prescribing the two traces independently
    # lets us measure all entries of the nodal heat-rate vector for a varying jump.
    h = 5.0
    result = solve_steady_heat_3d(mesh, thermal_conductivity=CONDUCTIVITY,
                                 prescribed_temperature=dict(enumerate(temperature)),
                                 thermal_contact_conductance={CONTACT[::-1]: h})
    expected = np.zeros(mesh.num_nodes)
    for tag, sign in zip(CONTACT, (1, -1)):
        for triangle in mesh.tagged_faces[tag]:
            # Each triangle on the one-cell rectangular end has half the contact area.
            # P1 integrals of N_i N_j are A/6 on the diagonal and A/12 off it.
            local = jump[triangle]
            expected[triangle] += sign * h * (AREA / 2) * (local.sum() + local) / 12
    np.testing.assert_allclose(result.contact_heat_rate, expected, rtol=1e-12, atol=1e-13)


def test_large_conductance_preserves_heat_rate_below_temperature_resolution():
    mesh = two_slabs()
    h = 1e16
    flux = 20 / (LEFT / CONDUCTIVITY["left"] + 1 / h + RIGHT / CONDUCTIVITY["right"])
    assert flux / h < np.spacing(300.0)
    result = solve_steady_heat_3d(mesh, thermal_conductivity=CONDUCTIVITY,
                                 prescribed_temperature=end_temperatures(mesh, 320.0, 300.0),
                                 thermal_contact_conductance={CONTACT: h})
    np.testing.assert_allclose(result.heat_flux[:, 0], flux, rtol=1e-10)
    for tag, sign in zip(CONTACT, (1, -1)):
        assert result.contact_heat_rate[mesh.boundary[tag]].sum() == pytest.approx(sign * AREA * flux, rel=1e-10)


@pytest.mark.parametrize("h_y", [0.25, 2048.0])
def test_four_body_contact_junction(h_y):
    # Four unit cubes share a central edge. Each central point has four temperatures.
    cube = box_mesh(1, 1, 1, 2, 2, 2)
    blocks = [(0, 0), (0, 1), (1, 0), (1, 1)]
    nodes = np.vstack([cube.nodes + [i, j, 0] for i, j in blocks])
    tets = np.vstack([cube.tets + n * cube.num_nodes for n in range(len(blocks))])
    faces = {f"{i}{j}_{tag}": tris + n * cube.num_nodes for n, (i, j) in enumerate(blocks)
             for tag, tris in cube.tagged_faces.items()}
    mesh = Mesh3D(nodes, tets, tagged_faces=faces)
    h_x = 1024.0
    contact = {("00_x1", "10_x0"): h_x, ("01_x1", "11_x0"): h_x,
               ("00_y1", "01_y0"): h_y, ("10_y1", "11_y0"): h_y}
    x, y, z = nodes.T
    # Unit conductivity and this affine slope give q=(-2,-3,0). The offsets across
    # vertical and horizontal contact faces enforce their two distinct jump laws.
    offsets = np.repeat([2*i/h_x + 3*j/h_y for i, j in blocks], cube.num_nodes)
    exact = 300 + 2*x + 3*y + offsets
    fixed = (x == 0) | (x == 2) | (y == 0) | (y == 2)
    # At the central midpoint, prescribe both sides of two contacts and solve for
    # the fourth body's temperature. The outer walls anchor the rest of each cube.
    center = np.flatnonzero((x == 1) & (y == 1) & (z == 0.5))
    fixed[center[[0, 1, 3]]] = True
    result = solve_steady_heat_3d(mesh, thermal_conductivity=1.0,
                                 prescribed_temperature=dict(zip(np.flatnonzero(fixed), exact[fixed])),
                                 thermal_contact_conductance=contact)
    np.testing.assert_allclose(result.temperature, exact, rtol=0, atol=1e-10)
    np.testing.assert_allclose(result.heat_flux, np.broadcast_to([-2, -3, 0], result.heat_flux.shape), atol=1e-10)
    # Each cube has two unit-area interfaces. Their outward normals differ by cube.
    outward = result.contact_heat_rate.reshape(len(blocks), cube.num_nodes).sum(axis=1)
    np.testing.assert_allclose(outward, [-5, 1, -1, 5], rtol=1e-10, atol=1e-10)


def test_zero_contact_insulates_and_cannot_anchor_a_floating_body():
    mesh = two_slabs()
    fixed = end_temperatures(mesh, 320.0, 300.0)
    # The left slab has a heat source and a sink. The unheated right slab stays at 300 K.
    parameters = dict(thermal_conductivity=CONDUCTIVITY, prescribed_temperature=fixed,
                      heat_source_density={"left": 2.0, "right": 0.0})
    no_contact = solve_steady_heat_3d(mesh, **parameters)
    insulated = solve_steady_heat_3d(mesh, **parameters, thermal_contact_conductance={CONTACT: 0.0})
    assert no_contact.contact_heat_rate is None
    np.testing.assert_array_equal(insulated.contact_heat_rate, 0.0)
    np.testing.assert_allclose(insulated.temperature, no_contact.temperature, rtol=0, atol=1e-10)
    np.testing.assert_allclose(insulated.temperature[np.unique(mesh.tets[mesh.regions == 1])], 300.0,
                               rtol=0, atol=1e-10)
    parameters["prescribed_temperature"] = {node: 300.0 for node in mesh.boundary["right_x1"]}
    with pytest.raises(ValueError, match="component"):
        solve_steady_heat_3d(mesh, **parameters, thermal_contact_conductance={CONTACT: 0.0})
    parameters["prescribed_temperature"] = {}
    with pytest.raises(ValueError, match="component"):
        solve_steady_heat_3d(mesh, **parameters, thermal_contact_conductance={CONTACT: 4.0})


@pytest.mark.parametrize("inward", [0.0, 2e-9])
def test_small_positive_conductance_anchors_a_body_through_contact(inward):
    mesh = two_slabs()
    h, sink = 1e-10, 318.25
    result = solve_steady_heat_3d(
        mesh, thermal_conductivity=CONDUCTIVITY, prescribed_temperature=dict.fromkeys(mesh.boundary["left_x0"], sink),
        thermal_contact_conductance={CONTACT: h}, inward_heat_flux={"right_x1": inward},
    )
    x = mesh.nodes[:, 0]
    right = np.unique(mesh.tets[mesh.regions == 1])
    expected = sink + inward * x / CONDUCTIVITY["left"]
    expected[right] = sink + inward * (LEFT / CONDUCTIVITY["left"] + 1/h + (x[right] - LEFT) / CONDUCTIVITY["right"])
    np.testing.assert_allclose(result.temperature, expected, rtol=0, atol=1e-11)
    np.testing.assert_allclose(result.heat_flux[:, 0], -inward, rtol=1e-8, atol=1e-18)
    assert result.contact_heat_rate[mesh.boundary["left_x1"]].sum() == pytest.approx(-AREA * inward, abs=1e-18)


def test_heated_contact_pair_converges_with_a_single_convective_sink():
    # q(x) grows through the heated left slab and stays constant through the right.
    # At the interface q = h(T_left - T_right). Only the right slab has an anchor.
    source, inward, h, film, ambient = 60.0, 12.0, 6.0, 10.0, 300.0
    interface_flux = inward + LEFT * source
    sink_temperature = ambient + interface_flux / film
    left_interface = sink_temperature + interface_flux * (RIGHT / CONDUCTIVITY["right"] + 1 / h)
    errors = []
    sizes = (3, 6, 12)
    for n in sizes:
        mesh = two_slabs(n)
        result = solve_steady_heat_3d(
            mesh, thermal_conductivity=CONDUCTIVITY, prescribed_temperature={},
            heat_source_density={"left": source, "right": 0.0}, inward_heat_flux={"left_x0": inward},
            convection={"right_x1": (film, ambient)}, thermal_contact_conductance={CONTACT: h},
        )
        left = np.unique(mesh.tets[mesh.regions == 0])
        x = mesh.nodes[:, 0]
        exact = sink_temperature + interface_flux * (LEFT + RIGHT - x) / CONDUCTIVITY["right"]
        integrated_flux = inward * (LEFT - x[left]) + source * (LEFT**2 - x[left]**2) / 2
        exact[left] = left_interface + integrated_flux / CONDUCTIVITY["left"]
        centers = mesh.nodes[mesh.tets, 0].mean(axis=1)
        exact_flux = np.where(mesh.regions == 0, inward + source * centers, interface_flux)
        errors.append([np.sqrt(np.mean((result.temperature - exact)**2)),
                       np.sqrt(np.average((result.heat_flux[:, 0] - exact_flux)**2, weights=mesh.volumes()))])
        transfer = interface_flux * AREA
        for tag, sign in zip(CONTACT, (1, -1)):
            assert result.contact_heat_rate[mesh.boundary[tag]].sum() == pytest.approx(sign * transfer, rel=1e-10)
        assert result.outward_convective_heat_rate.sum() == pytest.approx(transfer, rel=1e-10)
        assert result.generated_heat_rate.sum() == pytest.approx(source * LEFT * AREA, rel=1e-12)
        assert result.outward_prescribed_heat_rate.sum() == pytest.approx(-inward * AREA, rel=1e-12)
        assert result.relative_conservation_residual <= 1e-10
    temperature_order, flux_order = np.polyfit(-np.log(sizes), np.log(errors), 1)[0]
    assert temperature_order >= 1.8, (temperature_order, errors)
    assert flux_order >= 0.9, (flux_order, errors)


@pytest.mark.parametrize("contact", [
    {CONTACT: -1.0}, {CONTACT: np.nan}, {CONTACT: np.inf}, {CONTACT: True}, {CONTACT[0]: 2.0},
    {("left_x1", "missing"): 2.0}, {("left_x1", "left_x1"): 2.0}, {CONTACT: 2.0, CONTACT[::-1]: 2.0},
])
def test_invalid_contact_specification(contact):
    mesh = two_slabs()
    with pytest.raises(ValueError):
        solve_steady_heat_3d(mesh, thermal_conductivity=CONDUCTIVITY,
                             prescribed_temperature=end_temperatures(mesh, 320.0, 300.0),
                             thermal_contact_conductance=contact)


@pytest.mark.parametrize("mesh_options", [{"gap": 0.001}, {"flip_diagonal": True}])
def test_requires_matching_triangles_even_with_matching_corner_points(mesh_options):
    mesh = two_slabs(**mesh_options)
    with pytest.raises(ValueError):
        solve_steady_heat_3d(mesh, thermal_conductivity=CONDUCTIVITY,
                             prescribed_temperature=end_temperatures(mesh, 320.0, 300.0),
                             thermal_contact_conductance={CONTACT: 2.0})


def test_coincident_surfaces_must_face_each_other():
    mesh = two_slabs(1)
    # Reflect the entire right solid across the contact plane. Both independently
    # valid boundaries now face +x and their interiors are on the same side.
    right = np.unique(mesh.tets[mesh.regions == 1])
    nodes = mesh.nodes.copy()
    nodes[right, 0] = 2 * LEFT - nodes[right, 0]
    faces = {tag: (tris[:, ::-1] if tag.startswith("right_") else tris) for tag, tris in mesh.tagged_faces.items()}
    overlap = Mesh3D(nodes, mesh.tets.copy(), regions=mesh.regions, region_names=mesh.region_names,
                     tagged_faces=faces)
    overlap.check()
    with pytest.raises(ValueError, match="opposite"):
        solve_steady_heat_3d(overlap, thermal_conductivity=CONDUCTIVITY,
                             prescribed_temperature=end_temperatures(overlap, 320.0, 300.0),
                             thermal_contact_conductance={CONTACT: 2.0})


@pytest.mark.parametrize("natural", [{"inward_heat_flux": {"left_x1": 1.0}},
                                      {"convection": {"right_x0": (2.0, 300.0)}}])
def test_contact_and_external_boundary_conditions_cannot_reuse_triangles(natural):
    mesh = two_slabs()
    with pytest.raises(ValueError, match="overlap"):
        solve_steady_heat_3d(mesh, thermal_conductivity=CONDUCTIVITY,
                             prescribed_temperature=end_temperatures(mesh, 320.0, 300.0),
                             thermal_contact_conductance={CONTACT: 2.0}, **natural)
