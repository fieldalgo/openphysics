# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Pass 3D Joule heating from a DC conductor to a convection-cooled thermal solve."""
from galerkin import box_mesh
from galerkin.electric3d import solve_steady_electric_3d
from galerkin.thermal3d import solve_steady_heat_3d

mesh = box_mesh(0.02, 0.01, 0.01, 16, 8, 8)  # metres
electric = solve_steady_electric_3d(
    mesh, electrical_conductivity=2.0, prescribed_electric_potential={"x0": 2.0, "x1": 0.0},
)
heat = solve_steady_heat_3d(
    mesh, thermal_conductivity=3.0, prescribed_temperature={}, convection={"x1": (100.0, 300.0)},
    heat_source_density=electric.joule_power_density,  # one W/m^3 value per tetrahedron
)
print(f"Terminal power: {electric.inward_electric_power:.9f} W")
print(f"Total Joule heating: {heat.generated_heat_rate.sum():.9f} W")
print(f"Heat rejected by convection: {heat.outward_convective_heat_rate.sum():.9f} W")
print(f"Peak temperature: {heat.temperature.max():.6f} K")
