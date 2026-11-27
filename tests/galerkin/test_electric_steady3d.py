# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Analytical and coupling acceptance for steady 3D DC conduction."""

import numpy as np
import pytest

from galerkin import Mesh3D, box_mesh
from galerkin.electric3d import solve_steady_electric_3d
from galerkin.thermal3d import solve_steady_heat_3d


def _solve(mesh, conductivity):
    return solve_steady_electric_3d(
        mesh, electrical_conductivity=conductivity,
        prescribed_electric_potential={"x0": 6., "x1": 1.},
    )


@pytest.mark.parametrize("n", [1, 2, 4])
def test_uniform_box(n):
    mesh = box_mesh(.4, .2, .3, n, n, n)
    result = _solve(mesh, 8.)
    resistance = .4 / (8. * .2 * .3)
    current = 5. / resistance
    expected_field = np.tile([5. / .4, 0., 0.], (mesh.num_tets, 1))
    np.testing.assert_allclose(result.electric_potential, 6. - 5. * mesh.nodes[:, 0] / .4,
                               atol=1e-11, rtol=0)
    np.testing.assert_allclose(result.electric_field, expected_field, atol=1e-10, rtol=0)
    np.testing.assert_allclose(result.current_density, 8. * expected_field, atol=1e-9, rtol=0)
    np.testing.assert_allclose(result.joule_power_density, 8. * (5. / .4)**2, rtol=1e-10)
    assert result.inward_current == pytest.approx({"x0": current, "x1": -current}, rel=1e-10)
    assert result.inward_electric_power == pytest.approx(5. * current, rel=1e-10)
    assert result.joule_power == pytest.approx(5. * current, rel=1e-10)


def test_series_materials_and_thermal_handoff():
    box = box_mesh(.4, .2, .3, 4, 2, 2)
    # Reverse the elements and use the reordered values throughout the handoff.
    cells = box.tets[::-1].copy()
    right = box.nodes[cells, 0].mean(axis=1) > .1
    mesh = Mesh3D(box.nodes, cells, regions=right.astype(int),
                  region_names=["a", "b"], tagged_faces=box.tagged_faces)
    result = _solve(mesh, {"a": 2., "b": 8.})
    area = .2 * .3
    flux = 5. / (.1 / 2. + .3 / 8.)
    x = mesh.nodes[:, 0]
    expected_potential = 6. - flux * (np.minimum(x, .1) / 2. + np.maximum(x - .1, 0.) / 8.)
    expected_sigma = np.where(right, 8., 2.)
    np.testing.assert_allclose(result.electric_potential, expected_potential, atol=1e-11, rtol=0)
    np.testing.assert_array_equal(result.electrical_conductivity, expected_sigma)
    np.testing.assert_allclose(result.electric_field[:, 0], flux / expected_sigma, rtol=1e-10)
    np.testing.assert_allclose(result.current_density[:, 0], flux, rtol=1e-10)
    np.testing.assert_allclose(result.current_density[:, 1:], 0., atol=1e-9, rtol=0)
    np.testing.assert_allclose(result.joule_power_density, flux**2 / expected_sigma, rtol=1e-10)
    assert result.inward_current == pytest.approx({"x0": flux * area, "x1": -flux * area}, rel=1e-10)
    assert result.inward_electric_power == pytest.approx(5. * flux * area, rel=1e-10)
    assert result.joule_power == pytest.approx(result.joule_power_density @ mesh.volumes(), rel=1e-10)
    thermal = solve_steady_heat_3d(
        mesh, thermal_conductivity=4.,
        prescribed_temperature={int(i): 300. for i in mesh.boundary["x0"]},
        heat_source_density=lambda centroids: result.joule_power_density,
    )
    np.testing.assert_array_equal(thermal.heat_source_density, result.joule_power_density)
    assert thermal.generated_heat_rate.sum() == pytest.approx(result.inward_electric_power, rel=1e-10)


def test_layered_approximation_converges_to_graded_bar():
    # Piecewise constant midpoint samples of sigma(x)=2+x on slabs.
    exact_current = 5. * .2 * .3 / np.log(3. / 2.)
    errors = []
    for n in (2, 4, 8, 16):
        box = box_mesh(1., .2, .3, n, 2, 2)
        slabs = (n * box.nodes[box.tets, 0].mean(axis=1)).astype(int)
        names = [str(i) for i in range(n)]
        mesh = Mesh3D(box.nodes, box.tets.copy(), regions=slabs, region_names=names,
                      tagged_faces=box.tagged_faces)
        result = _solve(mesh, {name: 2. + (i + .5) / n for i, name in enumerate(names)})
        errors.append(abs(result.inward_current["x0"] - exact_current) / exact_current)
    assert errors[-1] < 6e-5
    assert np.all(np.asarray(errors[:-1]) / errors[1:] > 3.9)


def test_single_terminal_constant_and_large_voltage_offset():
    mesh = box_mesh(1., 1., 1., 3, 2, 2)
    solve = solve_steady_electric_3d
    constant = solve(mesh, electrical_conductivity=1., prescribed_electric_potential={"x0": 3.})
    np.testing.assert_array_equal(constant.electric_potential, 3.)
    np.testing.assert_array_equal(constant.joule_power_density, 0.)
    shift = 2.**40
    shifted = solve(mesh, electrical_conductivity=8.,
                    prescribed_electric_potential={"x0": shift + 6., "x1": shift + 1.})
    base = _solve(mesh, 8.)
    np.testing.assert_array_equal(shifted.electric_potential, base.electric_potential + shift)
    np.testing.assert_array_equal(shifted.electric_field, base.electric_field)
    assert shifted.inward_current == base.inward_current
    assert shifted.inward_electric_power == base.inward_electric_power


@pytest.mark.parametrize("sigma", [0., -1., np.inf, np.nan, True, 1.j, {"bad": 1.}])
def test_invalid_conductivity(sigma):
    with pytest.raises(ValueError, match="electrical_conductivity"):
        _solve(box_mesh(1., 1., 1., 1, 1, 1), sigma)


@pytest.mark.parametrize("volts, message", [
    ({}, "at least one"), ({"missing": 1.}, "face tag"),
    ({"x0": 0., "y0": 0.}, "shares nodes"), ({"x0": np.nan}, "finite"),
])
def test_invalid_terminals(volts, message):
    with pytest.raises(ValueError, match=message):
        solve_steady_electric_3d(box_mesh(1., 1., 1., 1, 1, 1),
                                electrical_conductivity=1., prescribed_electric_potential=volts)


def test_unanchored_component():
    box = box_mesh(1., 1., 1., 1, 1, 1)
    count = box.num_nodes
    mesh = Mesh3D(np.vstack([box.nodes, box.nodes + [2., 0., 0.]]),
                  np.vstack([box.tets, box.tets + count]),
                  tagged_faces={**box.tagged_faces,
                                **{tag + "b": faces + count for tag, faces in box.tagged_faces.items()}})
    with pytest.raises(ValueError, match="each connected mesh component"):
        _solve(mesh, 1.)
    result = solve_steady_electric_3d(
        mesh, electrical_conductivity=1.,
        prescribed_electric_potential={"x0": 2., "x1": 0., "x0b": 1e10 + 1., "x1b": 1e10},
    )
    assert result.inward_current == pytest.approx({"x0": 2., "x1": -2., "x0b": 1., "x1b": -1.})
    assert result.inward_electric_power == pytest.approx(5.)
