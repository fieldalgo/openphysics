# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Axisymmetric transient heat: independent exact solutions, balances and the Cartesian default.

Pre-registered checks G7-1 to G7-4 (HQ work record, 2026-11-08): ``solve_transient_heat(...,
coordinate_system="axisymmetric")`` integrates the full revolution with the steady solver's
measure; the consistent mass is the exact cubic moment of the linear radius.
"""
import numpy as np
import pytest
from scipy.special import j0, j1, jn_zeros

from galerkin.core.kernels import p1_mass, p1_mass_axisymmetric
from galerkin.core.quadrature import triangle_product_rule
from galerkin.mesh import rectangle_mesh
from galerkin.thermal import solve_steady_heat
from galerkin.transient_heat import solve_transient_heat

R, L, K, C, T0, TB = .003, .001, 1.114, 1.8e6, 350., 293.15
ALPHA = K/C
VOLUME = np.pi*R*R*L


def solve(mesh, **kwargs):
    return solve_transient_heat(mesh, conductivity=K, volumetric_heat_capacity=C,
                                coordinate_system="axisymmetric", **kwargs)


def cooling_cylinder(r, t, terms=60):
    """Exact cooling of a uniform cylinder, surface held at TB: the Bessel series."""
    roots = jn_zeros(0, terms)
    series = sum(2/(m*j1(m))*j0(m*r/R)*np.exp(-ALPHA*(m/R)**2*t) for m in roots)
    return TB+(T0-TB)*series


def test_weighted_mass_kernel_is_the_exact_cubic_moment():
    mesh = rectangle_mesh(R, L, 5, 3)
    mesh.nodes[:, 0] += .4e-3
    bary, w = triangle_product_rule()
    points = np.einsum("qa,tad->tqd", bary, mesh.nodes[mesh.triangles])
    exact = 2*np.pi*np.einsum("q,tq,qi,qj,t->tij", w, points[:, :, 0], bary, bary, mesh.areas())
    np.testing.assert_allclose(p1_mass_axisymmetric(mesh, 3.), 3*exact, rtol=1e-13, atol=0)
    # a constant radius reduces the cubic moments to the Cartesian mass times 2*pi*r
    radius = mesh.nodes[mesh.triangles][:, :, 0].mean(axis=1)
    np.testing.assert_allclose(p1_mass_axisymmetric(mesh, 1.).sum(axis=(1, 2)),
                               2*np.pi*radius*p1_mass(mesh, 1.).sum(axis=(1, 2)), rtol=1e-13)


def test_g7_1_cooling_cylinder_converges_to_the_bessel_series():
    """Spatial order >= 0.9 in the nodal maximum norm with dt refined as h^2; finest <= 2e-2."""
    final = .3*R*R/ALPHA
    errors = []
    for n, steps in ((8, 32), (16, 256), (32, 1024)):
        mesh = rectangle_mesh(R, L, n, max(2, n//8))
        right = mesh.boundary["right"]
        initial = np.full(mesh.num_nodes, T0)
        initial[right] = TB
        result = solve(mesh, time_s=np.linspace(0., final, steps+1), initial_temperature_k=initial,
                       dirichlet={int(i): TB for i in right})
        exact = cooling_cylinder(mesh.nodes[:, 0], final)
        errors.append(np.max(abs(result.temperature_k[-1]-exact))/(T0-TB))
        assert result.coordinate_system == "axisymmetric" and result.nodal_rate_unit == "W"
    orders = np.log2(np.asarray(errors[:-1])/np.asarray(errors[1:]))
    assert np.all(orders >= .9), (errors, orders)
    assert errors[-1] <= 2e-2, errors


@pytest.mark.parametrize("natural", [False, True])
def test_g7_2_every_step_balances_the_full_revolution(natural):
    """storage = source + reaction - prescribed - convective, step by step, within 1e-10 of the rates."""
    mesh = rectangle_mesh(R, L, 12, 4)
    right, top = mesh.boundary["right"], mesh.boundary["top"]
    kwargs = dict(outward_flux={"top": 250.}, convection={"right": (40., 280.)}) if natural else {}
    result = solve(mesh, time_s=np.linspace(0., 2., 9), initial_temperature_k=np.full(mesh.num_nodes, T0),
                   dirichlet={int(i): T0 for i in mesh.boundary["bottom"]}, heat_source=lambda p, t: 1e6*p[:, 0]/R,
                   **kwargs)
    storage = result.storage_rate_w_per_m.sum(axis=1)
    source = result.source_load_w_per_m[1:].sum(axis=1)
    reaction = result.reaction_w_per_m.sum(axis=1)
    scale = np.sum(abs(result.storage_rate_w_per_m)+abs(result.source_load_w_per_m[1:])+abs(result.reaction_w_per_m),
                   axis=1)
    outward = 0.
    if natural:
        outward = result.prescribed_outward_load_w_per_m.sum(axis=1)+result.convective_outward_w_per_m.sum(axis=1)
        scale = scale+np.sum(abs(result.prescribed_outward_load_w_per_m)+abs(result.convective_outward_w_per_m), axis=1)
        # the prescribed flux on the end face is 250 W/m^2 over pi R^2, a full revolution
        np.testing.assert_allclose(result.prescribed_outward_load_w_per_m.sum(axis=1), 250.*np.pi*R*R, rtol=1e-12)
    assert np.all(abs(storage-source-reaction+outward) <= 1e-10*scale)
    # the source integrates Q(r) = 1e6 r/R over the revolution: 2 pi 1e6/R * R^3/3 * L
    np.testing.assert_allclose(source, 2*np.pi*1e6/R*R**3/3*L, rtol=1e-12)
    # content and quadratic functional advance with the stored heat
    np.testing.assert_allclose(np.diff(result.heat_content_j_per_m)/np.diff(result.time_s), storage,
                               rtol=0, atol=1e-10*np.max(scale))


def test_g7_3_uniform_content_and_insulated_heating_are_exact():
    """H(0) = c T0 pi R^2 L within 1e-12; an insulated uniformly heated cylinder warms by Q/c per second."""
    mesh = rectangle_mesh(R, L, 10, 4)
    times = np.array([0., .5, 1.5, 4.])
    result = solve(mesh, time_s=times, initial_temperature_k=np.full(mesh.num_nodes, T0), dirichlet={},
                   heat_source=1e5)
    np.testing.assert_allclose(result.heat_content_j_per_m[0], C*T0*VOLUME, rtol=1e-12, atol=0)
    np.testing.assert_allclose(result.quadratic_functional_jk_per_m[0], .5*C*T0*T0*VOLUME, rtol=1e-12, atol=0)
    np.testing.assert_allclose(result.heat_content_j_per_m, C*VOLUME*(T0+1e5/C*times), rtol=1e-12, atol=0)
    np.testing.assert_allclose(result.temperature_k, np.broadcast_to(T0+1e5/C*times[:, None], result.temperature_k.shape), rtol=0, atol=1e-10)
    np.testing.assert_allclose(result.source_load_w_per_m.sum(axis=1), 1e5*VOLUME, rtol=1e-12)
    assert np.all(result.reaction_w_per_m == 0) and result.dirichlet_node_ids.size == 0


def test_g7_4_the_long_time_limit_is_the_steady_axisymmetric_solution():
    """Geometrically growing backward-Euler steps reach the steady solve within 1e-8 of its rise."""
    mesh = rectangle_mesh(R, L, 12, 4)
    right = mesh.boundary["right"]
    steady_kwargs = dict(heat_source=1e6, dirichlet={int(i): TB for i in mesh.boundary["bottom"]},
                         convection={"right": (120., 300.)}, outward_flux={"top": -400.})
    steady = solve_steady_heat(mesh, conductivity=K, coordinate_system="axisymmetric", **steady_kwargs)
    times = np.concatenate([[0.], np.cumsum(2.**np.arange(-4, 22))])
    result = solve(mesh, time_s=times, initial_temperature_k=np.full(mesh.num_nodes, TB), **steady_kwargs)
    rise = np.max(abs(steady.temperature-TB))
    np.testing.assert_allclose(result.temperature_k[-1], steady.temperature, rtol=0, atol=1e-8*rise)
    rate = np.max(abs(steady.load))
    np.testing.assert_allclose(result.reaction_w_per_m[-1], steady.reaction, rtol=0, atol=1e-6*rate)
    np.testing.assert_allclose(result.convective_outward_w_per_m[-1], steady.convective_outward, rtol=0,
                               atol=1e-6*rate)
    np.testing.assert_allclose(result.prescribed_outward_load_w_per_m[-1], steady.prescribed_outward_load,
                               rtol=1e-12)
    assert np.max(abs(result.storage_rate_w_per_m[-1])) <= 1e-8*rate


def test_cartesian_default_is_unchanged_and_explicit():
    mesh = rectangle_mesh(.02, .01, 6, 4)
    mesh.nodes[:, 0] += 1e-3
    kwargs = dict(conductivity=K, volumetric_heat_capacity=C, time_s=[0., .2, .5],
                  initial_temperature_k=np.full(mesh.num_nodes, T0),
                  dirichlet={int(i): T0 for i in mesh.boundary["left"]}, heat_source=3e5,
                  convection={"right": (15., 290.)})
    default = solve_transient_heat(mesh, **kwargs)
    explicit = solve_transient_heat(mesh, coordinate_system="cartesian", **kwargs)
    assert default.coordinate_system == "cartesian" and default.nodal_rate_unit == "W/m"
    for name in ("temperature_k", "heat_flux_w_m2", "source_load_w_per_m", "reaction_w_per_m",
                 "storage_rate_w_per_m", "heat_content_j_per_m", "convective_outward_w_per_m"):
        assert np.array_equal(getattr(default, name), getattr(explicit, name)), name
    # the axisymmetric interpretation of the same (offset) mesh is a different problem
    axisymmetric = solve_transient_heat(mesh, coordinate_system="axisymmetric", **kwargs)
    assert not np.allclose(axisymmetric.heat_content_j_per_m, default.heat_content_j_per_m)


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
        bc[int(mesh.boundary["left"][2])] = 0.
    elif bad == "axis_flux":
        kwargs["outward_flux"] = {"left": 1.}
    else:
        kwargs["convection"] = {"left": (1., 300.)}
    # boundary data are sampled inside the first step, so their refusal is chained to time index 0
    with pytest.raises(Exception) as info:
        solve_transient_heat(mesh, conductivity=1., volumetric_heat_capacity=1., time_s=[0., 1.],
                             initial_temperature_k=np.zeros(mesh.num_nodes), dirichlet=bc, **kwargs)
    messages = [str(info.value), str(info.value.__cause__)]
    assert any(word in m for m in messages for word in ("axis", "axisymmetric", "coordinate_system")), messages


@pytest.mark.parametrize("backend", ["jax", "torch"])
def test_axisymmetric_capacity_gradient(backend):
    from test_steady_gradients import _gradient
    mesh = rectangle_mesh(R, L, 6, 3)

    def objective(c, q):
        return solve_transient_heat(mesh, conductivity=K, volumetric_heat_capacity=c, heat_source=q,
                                    time_s=[0., 1., 3.], initial_temperature_k=np.full(mesh.num_nodes, T0),
                                    dirichlet={}, coordinate_system="axisymmetric").heat_content_j_per_m[-1]
    # H(3 s) = c T0 V + 3 q V for the insulated uniform cylinder, exactly in the discrete system
    gradient = _gradient(backend, objective, [C, 1e5])
    np.testing.assert_allclose(gradient, [T0*VOLUME, 3*VOLUME], rtol=1e-8, atol=0)
