# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Axisymmetric scalar measure: independent exact solutions and weighted norms."""
import numpy as np
import pytest

from galerkin.core.kernels import triangle_gradients
from galerkin.core.quadrature import triangle_product_rule
from galerkin.heat_source import ElementHeatSource
from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.thermal import solve_steady_heat


def solve(mesh, **kwargs):
    return solve_steady_heat(mesh, coordinate_system="axisymmetric", **kwargs)


@pytest.mark.parametrize("source_kind", ["scalar", "callback", "element", "region"])
def test_cylinder_source_and_energy(source_kind):
    R, L, k, Q, Tb = .003, .001, 1.114, 1e7, 293.15
    mesh = rectangle_mesh(R, L, 64, 32)
    mesh.regions = np.zeros(mesh.num_triangles, dtype=int)
    mesh.region_names = ["glass"]
    source = {"scalar": Q, "callback": lambda p: np.full(len(p), Q),
              "element": ElementHeatSource(mesh, np.full(mesh.num_triangles, Q)),
              "region": {"glass": Q}}[source_kind]
    result = solve(mesh, thermal_conductivity=k, heat_source_density=source,
                   prescribed_temperature={int(i): Tb for i in mesh.boundary["right"]})
    exact = Q*(R*R-mesh.nodes[:, 0]**2)/(4*k)
    np.testing.assert_allclose(result.temperature-Tb, exact, atol=.02, rtol=0)
    power = Q*np.pi*R*R*L
    assert abs(result.generated_heat_rate.sum()/power-1) < 1e-12
    assert abs((result.reaction_heat_rate.sum()+power)/power) < 1e-10
    assert result.coordinate_system == "axisymmetric"
    assert result.units["generated_heat_rate"] == "W"


@pytest.mark.parametrize("curved", [False, True])
def test_manufactured_convergence(curved):
    R, L, Rc, k, Q = .003, .001, .050669, 1.114, 1e7
    bary, w = triangle_product_rule()
    errors = []
    for nr in (16, 32, 64, 128):
        mesh = rectangle_mesh(R, L, nr, nr//2)
        if curved:
            r = mesh.nodes[:, 0]
            mesh.nodes[:, 1] *= (L-r*r/(Rc+np.sqrt(Rc*Rc-r*r)))/L
        result = solve(mesh, thermal_conductivity=k, heat_source_density=Q,
                       prescribed_temperature={int(i): 0. for i in mesh.boundary["right"]},
                       inward_heat_flux={"top": lambda p,n: -(Q*p[:, 0]*n[:, 0]/2)} if curved else None)
        points = np.einsum("qa,tad->tqd", bary, mesh.nodes[mesh.triangles])
        v = np.einsum("qa,ta->tq", bary, result.temperature[mesh.triangles])
        exact = Q*(R*R-points[:, :, 0]**2)/(4*k)
        measure = 2*np.pi*points[:, :, 0]*mesh.areas()[:, None]*w
        l2 = np.sqrt(np.sum(measure*(v-exact)**2)/np.sum(measure*exact**2))
        grads, _ = triangle_gradients(mesh)
        dv = np.einsum("tai,ta->ti", grads, result.temperature[mesh.triangles])
        exact_dr = -Q*points[:, :, 0]/(2*k)
        h1 = np.sqrt(np.sum(measure*((dv[:, None, 0]-exact_dr)**2+dv[:, None, 1]**2))
                     /np.sum(measure*exact_dr**2))
        errors.append((l2, h1))
        balance = result.generated_heat_rate.sum()+result.reaction_heat_rate.sum()-result.outward_prescribed_heat_rate.sum()
        assert abs(balance/result.generated_heat_rate.sum()) < 1e-10
    orders = np.log2(np.asarray(errors[:-1])/np.asarray(errors[1:]))
    assert np.all((orders[:, 0] >= 1.8) & (orders[:, 0] <= 2.2)), orders
    assert np.all((orders[:, 1] >= .9) & (orders[:, 1] <= 1.2)), orders
    assert errors[-1][0] < .005


@pytest.mark.parametrize("boundary", ["flux", "robin"])
def test_exact_axial_linear_boundary(boundary):
    R, L, k, a, Tb, h = .003, .001, 2., 100., 300., 200.
    mesh = rectangle_mesh(R, L, 8, 5)
    kwargs = {"inward_heat_flux": {"top": k*a}} if boundary == "flux" else {
        "convection": {"top": (h, Tb+a*L+k*a/h)}}
    result = solve(mesh, thermal_conductivity=k,
                   prescribed_temperature={int(i): Tb for i in mesh.boundary["bottom"]}, **kwargs)
    np.testing.assert_allclose(result.temperature, Tb+a*mesh.nodes[:, 1], atol=1e-11, rtol=0)
    assert abs(result.reaction_heat_rate.sum()/(-k*a*np.pi*R*R)-1) < 1e-10
    assert abs((result.reaction_heat_rate-result.outward_prescribed_heat_rate-result.outward_convective_heat_rate).sum()) < 1e-12


def test_robin_only_cylinder():
    R, L, k, Q, h, Tb = .003, .001, 1.114, 1e5, 200., 293.15
    mesh = rectangle_mesh(R, L, 128, 64)
    result = solve(mesh, thermal_conductivity=k, heat_source_density=Q, prescribed_temperature={},
                   convection={"right": (h, Tb)})
    exact = Tb+Q*R/(2*h)+Q*(R*R-mesh.nodes[:, 0]**2)/(4*k)
    np.testing.assert_allclose(result.temperature, exact, atol=6e-5, rtol=0)
    assert abs((result.outward_convective_heat_rate.sum()/result.generated_heat_rate.sum())-1) < 1e-10


def test_null_and_cartesian_default():
    mesh = rectangle_mesh(.003, .001, 8, 4)
    bc = {int(i): 293.15 for i in mesh.boundary["right"]}
    axis = solve(mesh, thermal_conductivity=1., prescribed_temperature=bc)
    np.testing.assert_array_equal(axis.temperature, np.full(mesh.num_nodes, 293.15))
    cart = solve_steady_heat(mesh, thermal_conductivity=1., prescribed_temperature=bc, heat_source_density=1.)
    explicit = solve_steady_heat(mesh, thermal_conductivity=1., prescribed_temperature=bc, heat_source_density=1., coordinate_system="cartesian")
    np.testing.assert_array_equal(cart.temperature, explicit.temperature)
    assert cart.units["generated_heat_rate_per_depth"] == "W/m"


def test_constant_element_source_exact_weighted_moments():
    R, L, Q = .003, .001, 17.
    mesh = Mesh(np.array([[0., 0.], [R, 0.], [0., L]]), np.array([[0, 1, 2]]), {})
    result = solve(mesh, thermal_conductivity=1., heat_source_density=ElementHeatSource(mesh, [Q]),
                   prescribed_temperature={0: 300., 1: 300., 2: 300.})
    # int_triangle N_i*r dA = A*(sum(r_vertices)+r_i)/12.
    exact = Q*2*np.pi*(R*L/2)*R/12*np.array([1., 2., 1.])
    np.testing.assert_allclose(result.generated_heat_rate, exact, rtol=1e-13, atol=0)


@pytest.mark.parametrize("scale", [1e-3, 1e3])
def test_full_revolution_length_scaling(scale):
    def case(s):
        mesh = rectangle_mesh(.003*s, .001*s, 12, 6)
        return solve(mesh, thermal_conductivity=1., heat_source_density=1e5/s**2,
                     prescribed_temperature={int(i): 300. for i in mesh.boundary["right"]})
    base, scaled = case(1.), case(scale)
    np.testing.assert_allclose(scaled.temperature, base.temperature, rtol=0, atol=1e-10)
    np.testing.assert_allclose(scaled.generated_heat_rate, scale*base.generated_heat_rate, rtol=1e-12, atol=0)
    assert abs(scaled.reaction_heat_rate.sum()/(scale*base.reaction_heat_rate.sum())-1) < 1e-10


def test_annulus_logarithmic_solution():
    a, b, L, k, delta = .001, .003, .002, 1.5, 2.
    mesh = rectangle_mesh(b-a, L, 128, 16)
    mesh.nodes[:, 0] += a
    bc = {int(i): 300. for i in mesh.boundary["left"]}
    bc.update({int(i): 300.+delta for i in mesh.boundary["right"]})
    result = solve(mesh, thermal_conductivity=k, prescribed_temperature=bc)
    exact = 300.+delta*np.log(mesh.nodes[:, 0]/a)/np.log(b/a)
    np.testing.assert_allclose(result.temperature, exact, rtol=0, atol=1e-4)
    power = 2*np.pi*k*L*delta/np.log(b/a)
    assert abs(result.reaction_heat_rate[mesh.boundary["right"]].sum()/power-1) < 1e-4


@pytest.mark.parametrize("bad", ["negative_radius", "mode", "axis_dirichlet", "axis_flux", "axis_robin"])
def test_invalid_axis_conditions(bad):
    mesh = rectangle_mesh(1., 1., 4, 4)
    bc = {int(i): 0. for i in mesh.boundary["right"]}
    kwargs = {"coordinate_system": "axisymmetric"}
    if bad == "negative_radius":
        mesh.nodes[:, 0] -= .1
    elif bad == "mode":
        kwargs["coordinate_system"] = "cylindrical-maybe"
    elif bad == "axis_dirichlet":
        bc[int(mesh.boundary["left"][2])] = 1.
    elif bad == "axis_flux":
        kwargs["inward_heat_flux"] = {"left": -1.}
    else:
        kwargs["convection"] = {"left": (1., 300.)}
    with pytest.raises(ValueError):
        solve_steady_heat(mesh, thermal_conductivity=1., prescribed_temperature=bc, **kwargs)


@pytest.mark.parametrize("backend", ["jax", "torch"])
def test_axisymmetric_coefficient_gradient(backend):
    from test_steady_gradients import _gradient
    mesh = rectangle_mesh(.003, .001, 8, 4)
    bc = {int(i): 0. for i in mesh.boundary["right"]}
    def objective(k, q):
        return solve(mesh, thermal_conductivity=k, heat_source_density=q, prescribed_temperature=bc).temperature.sum()
    value = float(objective(1.3, 1e5))
    gradient = _gradient(backend, objective, [1.3, 1e5])
    np.testing.assert_allclose(gradient, [-value/1.3, value/1e5], rtol=1e-6, atol=1e-12)
