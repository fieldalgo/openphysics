# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Analytical diffusion, interval energy and voltage-driven heating across split faces."""
import numpy as np
import pytest

from galerkin.mesh3d import Mesh3D, box_mesh
from galerkin.temperature_joule_heating import ConductivityModel
from galerkin.transient_heat3d import solve_transient_heat_3d
from galerkin.transient_joule_heat3d import solve_transient_joule_heat_3d


CONTACT = ("left_x1", "right_x0")
AREA = 0.25**2
MATERIAL = {"left": 2.0, "right": 4.0}


def slab_pair(nx, ny):
    slab = box_mesh(1, 0.25, 0.25, nx, ny, ny)
    faces = {"left_" + tag: tris for tag, tris in slab.tagged_faces.items()}
    faces.update({"right_" + tag: tris + slab.num_nodes for tag, tris in slab.tagged_faces.items()})
    return Mesh3D(np.vstack([slab.nodes, slab.nodes + [1, 0, 0]]),
                  np.vstack([slab.tets, slab.tets + slab.num_nodes]),
                  regions=np.repeat([0, 1], slab.num_tets), region_names=["left", "right"], tagged_faces=faces)


def check_body_energy(mesh, heat):
    dt = np.diff(heat.time)
    for region, material in enumerate(mesh.region_names):
        cells = mesh.tets[mesh.regions == region]
        volumes = mesh.volumes()[mesh.regions == region]
        nodes = np.unique(cells)
        # Integral of c*T over each tetrahedron is c*V times the vertex mean.
        energy = MATERIAL[material] * (heat.temperature[:, cells].mean(axis=2) @ volumes)
        storage = heat.heat_storage_rate[:, nodes].sum(axis=1)
        outward = heat.contact_heat_rate[:, nodes].sum(axis=1)
        generated = heat.generated_heat_rate[:, nodes].sum(axis=1)
        np.testing.assert_allclose(np.diff(energy), dt * storage, atol=2e-12)
        np.testing.assert_allclose(storage, generated - outward, rtol=1e-10, atol=2e-13)


def diffusion_mode(mesh, time):
    # Unit length on either side, insulated ends and k/c=1 m²/s in both slabs.
    # The interface values are +10 cos(mu) and -5 cos(mu) above the mean;
    # k_left*10 = k_right*5 matches the fluxes. The jump law then fixes h.
    mu = np.pi / 4
    x = mesh.nodes[:, 0]
    left, right = np.split(x, 2)
    shape = np.r_[10 * np.cos(mu * left), -5 * np.cos(mu * (2 - right))]
    h = 2 * 10 * mu * np.tan(mu) / (10 + 5)
    result = solve_transient_heat_3d(
        mesh, time=time, initial_temperature=300 + shape, thermal_conductivity=MATERIAL,
        volumetric_heat_capacity=MATERIAL, thermal_contact_conductance={CONTACT: h},
    )
    return result, shape, mu**2


@pytest.mark.parametrize("h", [0.0, 1.5])
def test_equilibration_of_two_insulated_bodies_with_initial_jump(h):
    mesh = slab_pair(3, 1)
    initial = np.repeat([330.0, 300.0], mesh.num_nodes // 2)
    time = [0, 0.05, 0.2, 1, 4, 20, 100, 500, 2500, 10000]
    heat = solve_transient_heat_3d(mesh, time=time, initial_temperature=initial, thermal_conductivity=MATERIAL,
                                   volumetric_heat_capacity=MATERIAL, thermal_contact_conductance={CONTACT: h})
    check_body_energy(mesh, heat)
    np.testing.assert_array_equal(heat.temperature[0], initial)
    heater, receiver = (mesh.tagged_faces[tag] for tag in CONTACT)
    jump = (heat.temperature[1:, heater] - heat.temperature[1:, receiver]).mean(axis=(1, 2))
    rate = heat.contact_heat_rate[:, mesh.boundary[CONTACT[0]]].sum(axis=1)
    np.testing.assert_allclose(rate, h * AREA * jump, rtol=1e-10, atol=1e-13)
    if h == 0:
        np.testing.assert_allclose(heat.temperature, np.broadcast_to(initial, heat.temperature.shape),
                                   rtol=0, atol=1e-11)
        np.testing.assert_array_equal(heat.contact_heat_rate, 0)
    else:
        # The equal-volume slabs settle at their capacity-weighted temperature.
        np.testing.assert_allclose(heat.temperature[-1], (2*330 + 4*300) / 6, rtol=0, atol=1e-7)
        assert 0 < rate[0] < h * AREA * 30


def test_contact_diffusion_mode_converges_in_time():
    mesh = slab_pair(24, 2)
    stop = 1 / (np.pi / 4)**2
    errors = []
    for steps in (8, 16, 32):
        time = np.linspace(0, stop, steps + 1)
        heat, shape, decay = diffusion_mode(mesh, time)
        exact = 300 + np.exp(-decay * stop) * shape
        errors.append(np.sqrt(np.mean((heat.temperature[-1] - exact)**2)))
        check_body_energy(mesh, heat)
        trace = mesh.boundary[CONTACT[0]]
        # Cross-sectional power for the continuous mode at time t.
        exact_power = AREA * 2 * 10 * (np.pi / 4) * np.sin(np.pi / 4) * np.exp(-decay * stop)
        if steps == 32:
            assert heat.contact_heat_rate[-1, trace].sum() == pytest.approx(exact_power, rel=0.025)
    assert np.all(np.array(errors[:-1]) / errors[1:] > 1.85), errors


def test_heat_reaches_diagonal_body_through_two_weak_contacts():
    cube = box_mesh(1, 1, 1, 2, 2, 2)
    blocks = [(0, 0), (0, 1), (1, 0), (1, 1)]
    nodes = np.vstack([cube.nodes + [i, j, 0] for i, j in blocks])
    tets = np.vstack([cube.tets + n * cube.num_nodes for n in range(4)])
    faces = {f"{i}{j}_{tag}": tris + n * cube.num_nodes for n, (i, j) in enumerate(blocks)
             for tag, tris in cube.tagged_faces.items()}
    mesh = Mesh3D(nodes, tets, tagged_faces=faces)
    pairs = [("00_x1", "10_x0"), ("01_x1", "11_x0"), ("00_y1", "01_y0"), ("10_y1", "11_y0")]
    h, capacity, generation = 1e-20, 2.0, 20.0
    time = np.arange(5) / 4
    heat = solve_transient_heat_3d(
        mesh, time=time, initial_temperature=np.full(mesh.num_nodes, 300.0),
        thermal_conductivity=1.0, volumetric_heat_capacity=capacity, thermal_contact_conductance=dict.fromkeys(pairs, h),
        heat_source_density=np.repeat([generation, 0.0, 0.0, 0.0], cube.num_tets),
    )
    shape = (len(time) - 1, len(blocks), cube.num_nodes)
    outward = heat.contact_heat_rate.reshape(shape).sum(axis=2)
    storage = heat.heat_storage_rate.reshape(shape).sum(axis=2)
    # The heated cube rises by Q*t/c to leading order. Each neighboring cube
    # receives h*A times that rise, with unit interface area and unit volume.
    direct = h * generation * time[1:] / capacity
    np.testing.assert_allclose(outward[:, :3], direct[:, None] * [2, -1, -1], rtol=1e-10, atol=0)
    assert np.all(np.abs(outward.sum(axis=1)) <= 8 * np.finfo(float).eps * direct)
    np.testing.assert_allclose(storage[:, 1:], -outward[:, 1:], rtol=1e-10, atol=0)
    # A second transfer is smaller by order h*A*t/(c*V). Temperatures round
    # to 300 K on the three unheated bodies, while their heat rates remain representable.
    far_gain = -outward[:, 3]
    assert np.all((0 < far_gain) & (far_gain < 4 * direct * h * time[1:] / capacity))


def test_contact_diffusion_mode_converges_in_space_with_unequal_steps():
    errors = []
    time = np.array([0.0, 0.1, 0.45, 1.0])
    for n in (1, 2, 4):
        mesh = slab_pair(4*n, n)
        heat, shape, decay = diffusion_mode(mesh, time)
        # Backward Euler applied to the continuum eigenfunction isolates spatial error.
        factor = np.prod(1 / (1 + decay * np.diff(time)))
        errors.append(np.sqrt(np.mean((heat.temperature[-1] - (300 + factor * shape))**2)))
        check_body_energy(mesh, heat)
        np.testing.assert_allclose(heat.stored_heat, heat.stored_heat[0], rtol=0, atol=2e-12)
        left, right = (heat.contact_heat_rate[:, mesh.boundary[tag]].sum(axis=1) for tag in CONTACT)
        np.testing.assert_allclose(left, -right, atol=1e-13)
        assert np.all(left > 0)
    assert np.all(np.array(errors[:-1]) / errors[1:] > 3), errors


def tetra_pair():
    # Two unit tetrahedra with a matching yz contact triangle of area 1/2.
    face = np.array([[0, 0, 0], [0, 1, 0], [0, 0, 1]])
    nodes = np.vstack([face, [-1, 0, 0], face, [1, 0, 0]])
    mesh = Mesh3D(nodes, np.arange(8).reshape(2, 4), regions=[0, 1], region_names=["left", "right"])
    exterior = mesh.outward_boundary_faces()
    interface = np.all(nodes[exterior, 0] == 0, axis=1)
    tags = {CONTACT[0]: exterior[interface & (exterior[:, 0] < 4)],
            CONTACT[1]: exterior[interface & (exterior[:, 0] >= 4)], "outside": exterior[~interface]}
    return Mesh3D(nodes, mesh.tets, regions=mesh.regions, region_names=mesh.region_names, tagged_faces=tags)


def test_fully_prescribed_contact_exchange_and_reservoir_reactions():
    mesh = tetra_pair()
    h = 4.0
    temperature = np.repeat([310.0, 300.0], 4)
    heat = solve_transient_heat_3d(
        mesh, time=[0.0, 0.1, 0.5], initial_temperature=temperature,
        prescribed_temperature=dict(enumerate(temperature)), thermal_conductivity=MATERIAL,
        volumetric_heat_capacity=MATERIAL, thermal_contact_conductance={CONTACT: h},
    )
    # Each of three face nodes receives one third of the uniform transfer h*A*ΔT.
    nodal_rate = h * 0.5 * 10 / 3 * np.array([1, 1, 1, 0, -1, -1, -1, 0])
    for field in (heat.contact_heat_rate, heat.reaction_heat_rate):
        np.testing.assert_allclose(field, np.broadcast_to(nodal_rate, field.shape), rtol=1e-13, atol=1e-14)
    np.testing.assert_array_equal(heat.temperature, np.broadcast_to(temperature, heat.temperature.shape))
    np.testing.assert_array_equal(heat.heat_storage_rate, 0)


@pytest.mark.parametrize(("h", "source"), [(0.0, 12.0), (1e-10, 12.0), (4.0, 12.0), (1e16, 12.0),
                                           pytest.param(1e16, 0.0, id="strong-unforced")])
def test_two_coordinate_contact_decay_and_rate_on_each_node(h, source):
    mesh = tetra_pair()
    initial = np.full(8, 300.0)
    initial[[1, 5]] += [8, -2]
    time = np.array([0.0, 0.01, 0.05, 0.13])
    options = dict(time=time, initial_temperature=initial, thermal_conductivity=MATERIAL,
                   volumetric_heat_capacity=MATERIAL, heat_source_density={"left": source, "right": 0.0},
                   prescribed_temperature=dict.fromkeys([0, 2, 3, 4, 6, 7], 300.0))
    heat = solve_transient_heat_3d(mesh, **options, thermal_contact_conductance={CONTACT: h})
    # For N=y, K_ii=kV, M_ii=cV/10 and H_ii=hA/6. Mean and jump are exact
    # independent scalar decay modes of the constrained two-temperature system.
    volume, area = 1/6, 1/2
    mass = np.array([2., 4.]) * volume / 10
    rate_mean = 10.0
    rate_jump = rate_mean + h * area / 6 * np.sum(1 / mass)
    load = source * volume / 4
    steady_mean = load / (mass.sum() * rate_mean)
    steady_jump = load / (mass[0] * rate_jump)
    initial_mean = (mass @ [8, -2]) / mass.sum()
    mean = steady_mean + (initial_mean - steady_mean) * np.cumprod(1 / (1 + rate_mean * np.diff(time)))
    jump = steady_jump + (10 - steady_jump) * np.cumprod(1 / (1 + rate_jump * np.diff(time)))
    expected = 300 + mean[:, None] + jump[:, None] * np.array([mass[1], -mass[0]]) / mass.sum()
    np.testing.assert_allclose(heat.temperature[1:, [1, 5]], expected, rtol=0, atol=1e-11)
    # Integrals of N_i N_free on a triangular face are A/6 at the free
    # vertex and A/12 at the other vertices, including on prescribed nodes.
    weights = area / 12 * np.array([1, 2, 1, 0, -1, -2, -1, 0])
    expected_rates = (h * jump)[:, None] * weights
    if source == 0:
        np.testing.assert_allclose(heat.contact_heat_rate[0], expected_rates[0], rtol=5e-10, atol=1e-16)
        # The unforced maximum falls from 22 W to 1.5e-14 W and then below 1e-29 W.
        # Grade that tail at absolute roundoff on the finite first-step power scale.
        floor = 8 * np.finfo(float).eps * np.max(np.abs(expected_rates[0]))
        np.testing.assert_allclose(heat.contact_heat_rate[1:], expected_rates[1:], rtol=0, atol=floor)
    else:
        # A constant left-hand source sustains a finite power even after the rapid transient.
        np.testing.assert_allclose(heat.contact_heat_rate, expected_rates, rtol=5e-10, atol=1e-16)
    assert not heat.contact_heat_rate.flags.writeable
    if h == 0:
        omitted = solve_transient_heat_3d(mesh, **options)
        assert omitted.contact_heat_rate is None
        np.testing.assert_allclose(heat.temperature, omitted.temperature, rtol=0, atol=1e-12)


@pytest.mark.parametrize("contact", [{CONTACT: -1}, {CONTACT: np.nan}, {("outside", "missing"): 1.0}])
def test_invalid_transient_contact(contact):
    mesh = tetra_pair()
    with pytest.raises(ValueError):
        solve_transient_heat_3d(mesh, time=[0, 1], initial_temperature=np.full(8, 300.0),
                                thermal_conductivity=1.0, volumetric_heat_capacity=1.0,
                                thermal_contact_conductance=contact)


def test_nonlinear_voltage_pulse_accounted_for_on_each_body():
    mesh = slab_pair(3, 1)
    model = ConductivityModel(lambda t: 4 / (1 + 0.1 * (t - 300)), (290, 320))
    coupled = solve_transient_joule_heat_3d(
        mesh, time=[0, 0.2, 0.5, 0.8], initial_temperature=np.full(mesh.num_nodes, 300.0),
        thermal_conductivity=MATERIAL, volumetric_heat_capacity=MATERIAL,
        electrical_conductivity={"left": model, "right": 1.0},
        prescribed_electric_potential=lambda t: {"left_x0": 1.0 if t < 0.5 else 0.0,
                                                 "left_x1": 0.0, "right_x1": 0.0},
        thermal_contact_conductance={CONTACT: 4.0}, temperature_tolerance=1e-11, relative_tolerance=1e-11,
    )
    heat = coupled.heat
    check_body_energy(mesh, heat)
    power = np.array([step.inward_electric_power for step in coupled.electric])
    assert power[0] > power[1] > power[2] == 0
    assert np.all(coupled.iteration_count[:2] > 1)
    assert np.all(heat.contact_heat_rate[:, mesh.boundary[CONTACT[0]]].sum(axis=1) > 0)
    np.testing.assert_allclose(heat.generated_heat_rate.sum(axis=1), power, rtol=1e-11, atol=1e-15)
    left = mesh.regions == 0
    for step, temperature in zip(coupled.electric, heat.temperature[1:]):
        np.testing.assert_allclose(step.electrical_conductivity[left],
                                   model.evaluate(temperature[mesh.tets[left]].mean(axis=1)), rtol=1e-11)
