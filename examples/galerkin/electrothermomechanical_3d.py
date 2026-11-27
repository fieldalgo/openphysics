# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""One-way 3D DC, steady heat and small-strain thermoelasticity on a single mesh."""

from galerkin import box_mesh
from galerkin.electric3d import solve_steady_electric_3d
from galerkin.thermal3d import solve_steady_heat_3d
from galerkin.thermoelasticity3d import solve_thermoelasticity_3d


def solve_electrothermal_bar(nx=16):
    """Return the mesh and the electrical and thermal results."""
    mesh = box_mesh(0.2, 0.05, 0.05, nx, 1, 1)  # metres
    electric = solve_steady_electric_3d(
        mesh, electrical_conductivity=10.0,
        prescribed_electric_potential={"x0": 2.0, "x1": 0.0},
    )
    heat = solve_steady_heat_3d(
        mesh, thermal_conductivity=2.0,
        prescribed_temperature={int(node): 300.0 for node in mesh.boundary["x0"]},
        convection={"x1": (20.0, 300.0)},  # W/(m^2 K), K
        heat_source_density=electric.joule_power_density,  # W/m^3, in mesh.tets order
    )
    return mesh, electric, heat


def solve_bar_displacement(mesh, heat):
    """Use the thermal result's nodal temperatures as input to the structural solver."""
    ends = (int(node) for tag in ("x0", "x1") for node in mesh.boundary[tag])
    fixed = {(node, 0): 0.0 for node in ends}
    fixed.update({(node, component): 0.0 for node in range(mesh.num_nodes) for component in (1, 2)})
    return solve_thermoelasticity_3d(
        mesh, temperature=heat.temperature, stress_free_temperature=300.0,
        linear_expansion_coefficient=1.2e-5, youngs_modulus=70e9, poisson_ratio=0.0,
        prescribed_displacement=fixed,
    )


def main():
    mesh, electric, heat = solve_electrothermal_bar()
    solid = solve_bar_displacement(mesh, heat)
    left = mesh.boundary["x0"]
    right = mesh.boundary["x1"]
    print(f"Electrical power: {electric.inward_electric_power:.9f} W")
    print(f"Heat rejected by convection: {heat.outward_convective_heat_rate.sum():.9f} W")
    print(f"Heat rejected through the fixed-temperature end: {-heat.reaction_heat_rate.sum():.9f} W")
    print(f"Peak temperature: {heat.temperature.max():.6f} K")
    print(f"Maximum axial displacement magnitude: {abs(solid.displacement[:, 0]).max():.6g} m")
    print(f"Mean axial stress: {mesh.volumes() @ solid.stress[:, 0, 0] / mesh.volumes().sum():.6g} Pa")
    print(f"Axial support forces (left, right): "
          f"{solid.reaction_force[left, 0].sum():.6g}, {solid.reaction_force[right, 0].sum():.6g} N")


if __name__ == "__main__":
    main()
