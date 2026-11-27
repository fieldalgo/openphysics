# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent series-resistor and heat-balance checks on one 3D mesh."""
import numpy as np

from galerkin import Mesh3D, box_mesh
from galerkin.electric3d import solve_steady_electric_3d
from galerkin.thermal3d import solve_steady_heat_3d


def test_two_material_conductor_transfers_joule_power_and_converges():
    # Two 10 mm layers in series. Five faces are thermally insulated;
    # only the far end rejects heat by convection to 300 K.
    thickness = 0.01
    area = 0.01 ** 2
    voltage = 2.0
    h = 100.0
    ambient = 300.0
    sigma = (1.0, 3.0)
    conductivity = (1.0, 2.0)
    current_density = voltage / (thickness / sigma[0] + thickness / sigma[1])
    flux = current_density * voltage
    power = area * flux
    q1, q2 = (current_density ** 2 / value for value in sigma)
    right_temperature = ambient + flux / h
    interface_temperature = right_temperature + (q1 + q2 / 2) * thickness ** 2 / conductivity[1]

    def exact_temperature(x):
        # Integrate the piecewise-linear heat flux from the insulated left end.
        u = x - thickness
        return np.where(
            x <= thickness,
            interface_temperature + q1 * (thickness ** 2 - x ** 2) / (2 * conductivity[0]),
            right_temperature + (q1 * thickness * (thickness - u)
                                 + q2 * (thickness ** 2 - u ** 2) / 2) / conductivity[1],
        )

    errors = []
    for nx in (4, 8, 16):
        grid = box_mesh(2 * thickness, 0.01, 0.01, nx, nx // 2, nx // 2)
        centers = grid.nodes[grid.tets].mean(axis=1)
        regions = (centers[:, 0] > thickness).astype(int)
        mesh = Mesh3D(grid.nodes, grid.tets, regions=regions,
                      region_names=["left", "right"], tagged_faces=grid.tagged_faces)
        electric = solve_steady_electric_3d(
            mesh, electrical_conductivity=dict(zip(mesh.region_names, sigma)),
            prescribed_electric_potential={"x0": voltage, "x1": 0.0},
        )
        heat = solve_steady_heat_3d(
            mesh, thermal_conductivity=dict(zip(mesh.region_names, conductivity)),
            prescribed_temperature={}, convection={"x1": (h, ambient)},
            heat_source_density=electric.joule_power_density,
        )
        np.testing.assert_allclose(electric.inward_current["x0"], area * current_density, rtol=1e-9)
        np.testing.assert_allclose(electric.joule_power_density, np.where(regions == 0, q1, q2), rtol=1e-9)
        np.testing.assert_array_equal(heat.heat_source_density, electric.joule_power_density)
        faces = mesh.nodes[mesh.tagged_faces["x1"]]
        face_areas = np.linalg.norm(np.cross(faces[:, 1] - faces[:, 0],
                                             faces[:, 2] - faces[:, 0]), axis=1) / 2
        face_temperatures = heat.temperature[mesh.tagged_faces["x1"]].mean(axis=1)
        surface_power = h * (face_areas @ (face_temperatures - ambient))
        powers = [electric.inward_electric_power, mesh.volumes() @ electric.joule_power_density,
                  heat.generated_heat_rate.sum(), heat.outward_convective_heat_rate.sum(), surface_power]
        np.testing.assert_allclose(powers, power, rtol=1e-9, atol=0.0)
        node_error = max(abs(heat.temperature - exact_temperature(mesh.nodes[:, 0])))
        cell_error = max(abs(heat.temperature[mesh.tets].mean(axis=1) - exact_temperature(centers[:, 0])))
        errors.append(max(node_error, cell_error))
        print(f"{mesh.num_tets} tets: terminal={powers[0]:.13g} W, "
              f"Joule={powers[1]:.13g} W, surface={surface_power:.13g} W, "
              f"Tmax={heat.temperature.max():.9f} K, max sampled error={errors[-1]:.7g} K")

    assert errors[2] < errors[1] < errors[0]
    assert errors[-1] < 0.05
