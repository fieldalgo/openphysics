# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit DC solve then same-mesh steady heat; temperature-independent materials."""
from galerkin.electric import solve_steady_electric
from galerkin.joule_heating import solve_steady_joule_heat
from galerkin.mesh import rectangle_mesh

mesh = rectangle_mesh(.02, .01, 16, 8)  # metres
voltage = {int(i): 0. for i in mesh.boundary['left']}
voltage.update({int(i): 2. for i in mesh.boundary['right']})
electrical = solve_steady_electric(mesh, conductivity=3., dirichlet=voltage)
result = solve_steady_joule_heat(
    mesh, electrical_result=electrical, conductivity=5.,
    dirichlet={i: 300. for i in voltage})
print(f'Maximum temperature: {result.thermal.temperature.max():.6f} K')
print(f'Joule power per length: {result.source_power_per_length:.6f} W/m')
print(f'Outward heat per length: {result.outward_heat_per_length:.6f} W/m')
# A depth of 1 mm turns 6 W/m into 0.006 W; the source remains 30000 W/m³.
