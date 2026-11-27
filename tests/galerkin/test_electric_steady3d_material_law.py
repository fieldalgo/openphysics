# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent material-law and series-resistance checks for 3D DC."""
import numpy as np
import pytest

from galerkin._tetra_materials import conductivity_at_temperature
from galerkin.electric3d import solve_steady_electric_3d
from galerkin.mesh3d import Mesh3D, box_mesh
from galerkin.temperature_joule_heating import ConductivityModel


def layered_mesh(n):
    box = box_mesh(1., .2, .3, n, 2, 2)
    tets = box.tets[::-1].copy()
    layers = (box.nodes[tets, 0].mean(axis=1) > .5).astype(int)
    return Mesh3D(box.nodes, tets, regions=layers, region_names=["heater", "lead"],
                  tagged_faces=box.tagged_faces)


def solve(mesh, sigma):
    return solve_steady_electric_3d(mesh, electrical_conductivity=sigma,
                                    prescribed_electric_potential={"x0": 2., "x1": 0.})


@pytest.mark.parametrize("n", [2, 4, 8])
@pytest.mark.parametrize("kelvin", [300., 350., 400.])
def test_fixed_voltage_series_bar_at_material_temperatures(n, kelvin):
    mesh = layered_mesh(n)
    model = ConductivityModel(lambda t: 4 / (1 + .01 * (t - 300)), (300., 400.))
    sigma = conductivity_at_temperature(mesh, {"heater": model, "lead": 8.},
                                             np.full(mesh.num_nodes, kelvin))
    result = solve(mesh, sigma)
    heater_sigma = 4 / (1 + .01 * (kelvin - 300))
    density = 2 / (.5 / heater_sigma + .5 / 8)
    current = .2 * .3 * density
    x = mesh.nodes[:, 0]
    voltage = 2 - density * (np.minimum(x, .5) / heater_sigma + np.maximum(x - .5, 0) / 8)
    np.testing.assert_allclose(result.electric_potential, voltage, atol=1e-12, rtol=0)
    np.testing.assert_allclose(result.current_density[:, 0], density, rtol=1e-10)
    expected_source = density**2 * np.where(mesh.regions == 0, 1 / heater_sigma, 1 / 8)
    np.testing.assert_allclose(result.joule_power_density, expected_source, rtol=1e-10)
    assert result.inward_current == pytest.approx({"x0": current, "x1": -current}, rel=1e-10)
    assert result.joule_power == pytest.approx(2 * current, rel=1e-10)


def test_element_mean_and_input_ownership():
    mesh = layered_mesh(4)
    temperature = 300 + 50 * mesh.nodes[:, 0]
    original = temperature.copy()

    def evaluate(means):
        assert not means.flags.writeable
        return 1 + (means - 300) ** 2 / 100

    law = ConductivityModel(evaluate, (300., 350.))
    materials = {"lead": 8., "heater": law}
    sigma = conductivity_at_temperature(mesh, materials, temperature)
    mean = original[mesh.tets].mean(axis=1)
    expected = np.where(mesh.regions == 0, 1 + (mean - 300)**2 / 100, 8.)
    np.testing.assert_allclose(sigma, expected, rtol=1e-13)
    result = solve(mesh, sigma)
    np.testing.assert_array_equal(temperature, original)
    assert materials == {"lead": 8., "heater": law}
    sigma[:] = 1.
    np.testing.assert_allclose(result.electrical_conductivity, expected, rtol=1e-13)
    np.testing.assert_array_equal(conductivity_at_temperature(mesh, 3., temperature), 3.)
    np.testing.assert_allclose(conductivity_at_temperature(mesh, law, temperature), (1 + (mean - 300) ** 2 / 100))


@pytest.mark.parametrize("bad", [lambda n: np.ones(n - 1), lambda n: np.ones((n, 1)),
                                 lambda n: np.full(n, -1.), lambda n: np.full(n, np.inf)])
def test_invalid_element_arrays(bad):
    mesh = layered_mesh(2)
    with pytest.raises(ValueError, match="electrical_conductivity"):
        solve(mesh, bad(mesh.num_tets))


@pytest.mark.parametrize("callback", [lambda t: -np.ones_like(t), lambda t: np.full_like(t, np.nan),
                                      lambda t: 2., lambda t: np.ones((len(t), 1))])
def test_invalid_model_outputs(callback):
    mesh = layered_mesh(2)
    with pytest.raises(ValueError, match="sigma"):
        conductivity_at_temperature(mesh, ConductivityModel(callback, (299., 301.)),
                                        np.full(mesh.num_nodes, 300.))


def test_invalid_temperatures_and_region_tables():
    mesh = layered_mesh(2)
    valid = np.full(mesh.num_nodes, 300.)
    law = ConductivityModel(np.ones_like, (299., 301.))
    outlier = valid.copy()
    outlier[0] = 302.
    for temperature, message in [(outlier, "outside"), (valid[:-1], "shape"),
                                 (-valid, "nonnegative"), (valid * np.inf, "finite")]:
        with pytest.raises(ValueError, match=message):
            conductivity_at_temperature(mesh, law, temperature)
    for table in ({"heater": law}, {"heater": law, "lead": -8.},
                  {"heater": law, "lead": 8., "extra": 1.}):
        with pytest.raises(ValueError, match="electrical_conductivity"):
            conductivity_at_temperature(mesh, table, valid)
    bare = Mesh3D(mesh.nodes, mesh.tets)
    with pytest.raises(ValueError, match="named tetrahedral regions"):
        conductivity_at_temperature(bare, {"heater": law, "lead": 8.}, valid)
