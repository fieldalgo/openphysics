# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent analytic fields and separated time/space convergence."""
import json
import numpy as np
import pytest
from galerkin.mesh import rectangle_mesh
from galerkin.transient_heat import solve_transient_heat
from galerkin.transient_thermal_mechanical import solve_transient_thermoelasticity
from refsol import thermoelasticity as reference
from refsol.transient_heat import uniform_insulated

E, NU, ALPHA, TREF = 2e9, .25, 1e-5, 300.
MATERIAL = dict(young_modulus=E, poisson_ratio=NU,
                thermal_expansion_per_k=ALPHA, reference_temperature_k=TREF)


def boundary(mesh):
    return np.unique(np.concatenate(list(mesh.boundary.values())))


def options(mesh, plane, constrained=False, alpha=ALPHA, tref=TREF):
    right = int(np.argmin(np.sum((mesh.nodes-[1., 0.])**2, axis=1)))
    supports = ({(int(i), c): 0. for i in boundary(mesh) for c in (0, 1)} if constrained
        else {(0, 0): 0., (0, 1): 0., (right, 1): 0.})
    return dict(units={'length': 'm', 'time': 's', 'temperature': 'K'},
        **{**MATERIAL, 'thermal_expansion_per_k': alpha, 'reference_temperature_k': tref},
        plane=plane, mechanical_dirichlet=supports)


@pytest.mark.parametrize('plane', ['stress', 'strain'])
@pytest.mark.parametrize('constrained', [False, True])
@pytest.mark.parametrize('source,alpha,shift', [(8., ALPHA, 0.), (-8., ALPHA, 0.),
    (8., -ALPHA, 0.), (8., 0., 0.), (8., ALPHA, 100.)])
def test_uniform_history_against_3d_analytic_fields(plane, constrained, source, alpha, shift):
    mesh = rectangle_mesh(1., 1., 4, 4)
    times = np.array([2., 2.03, 2.4, 3.])
    heat = solve_transient_heat(mesh, conductivity=2., volumetric_heat_capacity=4.,
        time_s=times, initial_temperature_k=np.full(mesh.num_nodes, TREF+shift),
        dirichlet={}, heat_source=source)
    result = solve_transient_thermoelasticity(mesh, heat,
        **options(mesh, plane, constrained, alpha, TREF+shift))
    oracle = reference.uniform_constrained if constrained else reference.uniform_free
    centroids = mesh.nodes[mesh.triangles].mean(axis=1)
    for step in result.steps:
        thermal = uniform_insulated(mesh.nodes, step.time_s, volumetric_heat_capacity=4.,
            heat_source=source, initial_temperature_k=TREF+shift, initial_time_s=times[0])
        np.testing.assert_allclose(step.temperature_snapshot.temperature_k, thermal.temperature_k, rtol=0, atol=1e-9)
        material = dict(**MATERIAL, plane=plane)
        material.update(thermal_expansion_per_k=alpha, reference_temperature_k=TREF+shift)
        exact = oracle(mesh.nodes, source*(step.time_s-times[0])/4., **material)
        cell = oracle(centroids, source*(step.time_s-times[0])/4., **material)
        mechanics = step.mechanics
        np.testing.assert_allclose(mechanics.displacement, exact.displacement, rtol=0, atol=ALPHA*20*1e-10)
        np.testing.assert_allclose(mechanics.stress, cell.stress, rtol=0, atol=E*ALPHA*20*1e-9)
        np.testing.assert_allclose(mechanics.sigma_zz, cell.sigma_zz, rtol=0, atol=E*ALPHA*20*1e-9)
        np.testing.assert_allclose(mechanics.physical_elastic_energy,
            np.dot(mesh.areas(), cell.energy_density), rtol=1e-9, atol=E*(ALPHA*20)**2*1e-10)
        if constrained:
            expected = np.zeros_like(mesh.nodes)
            stress = cell.stress[0]
            tensor = np.array([[stress[0], stress[2]], [stress[2], stress[1]]])
            for tag, normal in [('left', [-1, 0]), ('right', [1, 0]),
                                ('bottom', [0, -1]), ('top', [0, 1])]:
                for edge in mesh.boundary_edges[tag]:
                    expected[edge] += tensor@normal*np.linalg.norm(mesh.nodes[edge[1]]-mesh.nodes[edge[0]])/2
            np.testing.assert_allclose(mechanics.reaction, expected, rtol=0, atol=E*ALPHA*20*1e-9)


@pytest.mark.parametrize('plane', ['stress', 'strain'])
@pytest.mark.parametrize('constrained', [False, True])
def test_backward_euler_time_error_is_separate_from_space(plane, constrained):
    mesh = rectangle_mesh(1., 1., 2, 2)
    errors = []
    for count in (8, 16, 32):
        times = np.linspace(0., 1., count+1)
        heat = solve_transient_heat(mesh, conductivity=2., volumetric_heat_capacity=4.,
            time_s=times, initial_temperature_k=np.full(mesh.num_nodes, 300.), dirichlet={},
            heat_source=lambda points, now: np.full(len(points), 8*now))
        result = solve_transient_thermoelasticity(mesh, heat, time_indices=[count],
            **options(mesh, plane, constrained))
        step = result.steps[0]
        expected_error = np.sum(np.diff(times)**2)
        np.testing.assert_allclose(step.temperature_snapshot.temperature_k-301., expected_error, rtol=1e-9, atol=1e-11)
        oracle = reference.uniform_constrained if constrained else reference.uniform_free
        exact = oracle(mesh.nodes, 1., plane=plane, **MATERIAL)
        if constrained:
            error = np.max(abs(step.mechanics.stress-exact.stress[0]))
            predicted = E*ALPHA*expected_error/(1-NU if plane == 'stress' else 1-2*NU)
        else:
            error = np.max(abs(step.mechanics.displacement-exact.displacement))
            predicted = ALPHA*expected_error*(1 if plane == 'stress' else 1+NU)
        assert error == pytest.approx(predicted, rel=1e-8)
        errors.append(error)
    orders = np.log2(np.array(errors[:-1])/errors[1:])
    assert np.all((orders >= .99) & (orders <= 1.01))
    print(json.dumps(dict(case='temporal', plane=plane, constrained=constrained, errors=errors, orders=orders.tolist())))


def test_nonuniform_quadratic_time_error_at_every_index():
    mesh = rectangle_mesh(1., 1., 2, 2)
    times = np.array([2., 2.1, 2.3, 2.8, 3.])
    heat = solve_transient_heat(mesh, conductivity=2., volumetric_heat_capacity=4.,
        time_s=times, initial_temperature_k=np.full(mesh.num_nodes, 300.), dirichlet={},
        heat_source=lambda points, now: np.full(len(points), 8*(now-2)))
    result = solve_transient_thermoelasticity(mesh, heat, **options(mesh, 'stress'))
    accumulated = np.r_[0., np.cumsum(np.diff(times)**2)]
    for step in result.steps:
        expected = (step.time_s-2)**2 + accumulated[step.time_index]
        np.testing.assert_allclose(step.temperature_snapshot.temperature_k-300., expected, rtol=1e-9, atol=1e-10)
        np.testing.assert_allclose(step.mechanics.displacement, ALPHA*expected*mesh.nodes, rtol=1e-9, atol=1e-14)


def spatial_errors(mesh, mechanics, plane):
    # Independent Duffy integration; no production geometry/constitutive helper.
    x, w = np.polynomial.legendre.leggauss(4)
    x, w = (x+1)/2, w/2
    a, b = np.meshgrid(x, x, indexing='ij')
    bary = np.stack([1-a, a*(1-b), a*b], axis=-1).reshape(-1, 3)
    weights = (w[:, None]*w[None, :]*a).ravel()
    vertices = mesh.nodes[mesh.triangles]
    determinant = np.linalg.det(vertices[:, 1:]-vertices[:, :1])
    quadrature_points = np.einsum('qn,tnd->tqd', bary, vertices)
    gradients = np.linalg.inv(np.concatenate([np.ones((*vertices.shape[:2], 1)), vertices], axis=-1))[:, 1:, :].swapaxes(1, 2)
    u = np.einsum('qn,tnd->tqd', bary, mechanics.displacement[mesh.triangles])
    gradient = np.einsum('tni,tnj->tji', gradients, mechanics.displacement[mesh.triangles])
    strain = np.stack([gradient[:, 0, 0], gradient[:, 1, 1], gradient[:, 0, 1]+gradient[:, 1, 0]], axis=-1)
    temperature = np.einsum('qn,tn->tq', bary, mechanics.temperature_snapshot.temperature_k[mesh.triangles])
    flat_points = quadrature_points.reshape(-1, 2)
    exact = reference.linear_temperature(flat_points, offset_k=10., gradient_k_per_m=20., plane=plane, **MATERIAL)
    full_strain = np.broadcast_to(strain[:, None, :], (*temperature.shape, 3)).reshape(-1, 3)
    state = reference.state_from_3d(full_strain, temperature.ravel(), plane=plane, **MATERIAL)
    area_weight = (determinant[:, None]*weights).ravel()
    differences = [np.sum((u.reshape(-1, 2)-exact.displacement)**2, axis=1),
        np.sum((np.broadcast_to(gradient[:, None], (*temperature.shape, 2, 2)).reshape(-1, 2, 2)-exact.gradient)**2, axis=(1, 2)),
        np.sum((state.stress-exact.stress)**2*np.array([1., 1., 2.]), axis=1)+(state.sigma_zz-exact.sigma_zz)**2]
    return np.sqrt([np.dot(area_weight, delta) for delta in differences])


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_stationary_affine_heat_and_mechanical_space_convergence(plane):
    errors = []
    for count in (8, 16, 32):
        mesh = rectangle_mesh(1., 1., count, count)
        thermal = 310.+20.*mesh.nodes[:, 0]
        fixed = np.r_[mesh.boundary['left'], mesh.boundary['right']]
        heat = solve_transient_heat(mesh, conductivity=2., volumetric_heat_capacity=4.,
            time_s=[0., .07, .4], initial_temperature_k=thermal,
            dirichlet={int(i): thermal[i] for i in fixed})
        exact = reference.linear_temperature(mesh.nodes, offset_k=10., gradient_k_per_m=20., plane=plane, **MATERIAL)
        kwargs = options(mesh, plane)
        kwargs['mechanical_dirichlet'] = {(int(i), c): exact.displacement[i, c]
            for i in boundary(mesh) for c in (0, 1)}
        result = solve_transient_thermoelasticity(mesh, heat, time_indices=[0, 2], **kwargs)
        for step in result.steps:
            np.testing.assert_allclose(step.temperature_snapshot.temperature_k, thermal, rtol=0, atol=1e-9)
        # Both stages are independently evaluated, including the initial field.
        pair = [spatial_errors(mesh, step.mechanics, plane) for step in result.steps]
        errors.append(pair)
    values = np.array(errors)
    orders = np.log2(values[:-1]/values[1:])
    assert np.all(orders >= np.array([1.8, .9, .9]))
    assert np.max(values[-1, :, 0])/(ALPHA*20) < .01
    print(json.dumps(dict(case='spatial_stationary', plane=plane, errors=values.tolist(), orders=orders.tolist())))

@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_constant_body_and_nonzero_fixed_supports(plane):
    # One square with only exterior nodes: prescribed affine strain is exact,
    # constant body loads are independent triangle integrals, and reactions
    # retain applied body force on fixed components.
    mesh = rectangle_mesh(1., 1., 1, 1)
    heat = solve_transient_heat(mesh, conductivity=2., volumetric_heat_capacity=4.,
        time_s=[0., .1], initial_temperature_k=np.full(mesh.num_nodes, 320.), dirichlet={})
    displacement = 1e-4*mesh.nodes
    kwargs = options(mesh, plane)
    kwargs['mechanical_dirichlet'] = {(int(i), c): displacement[i, c]
        for i in boundary(mesh) for c in (0, 1)}
    kwargs['body_force'] = (7., -3.)
    result = solve_transient_thermoelasticity(mesh, heat, **kwargs)
    expected_load = np.zeros_like(mesh.nodes)
    for tri, area in zip(mesh.triangles, mesh.areas()):
        expected_load[tri] += area*np.array([7., -3.])/3
    state = reference.state_from_3d(np.tile([1e-4, 1e-4, 0.], (mesh.num_triangles, 1)),
        np.full(mesh.num_triangles, 320.), plane=plane, **MATERIAL)
    for step in result.steps:
        np.testing.assert_array_equal(step.mechanics.displacement, displacement)
        np.testing.assert_allclose(step.mechanics.stress, state.stress, rtol=1e-10, atol=1e-5)
        np.testing.assert_allclose(step.mechanics.load_body, expected_load, rtol=1e-12, atol=1e-12)
        np.testing.assert_allclose(step.mechanics.reaction.sum(axis=0), [-7., 3.], rtol=0, atol=1e-7)
