# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Two series conductors; all geometry in metres, power per extrusion depth."""
from galerkin.mesh import layered_rectangle_mesh
from galerkin.electric import solve_steady_electric

mesh = layered_rectangle_mesh([.01, .03], .005, [4, 8], 4, ['left', 'right'])
bc = {int(i): .2 for i in mesh.boundary['left']} | {
    int(i): 0. for i in mesh.boundary['right']}
result = solve_steady_electric(mesh, electrical_conductivity={'left': 2., 'right': 8.},
                               prescribed_electric_potential=bc)
print(f'Joule power per length: {result.joule_power_per_depth:.9f} W/m')
print(f'Supplied power per length: {result.inward_electric_power_per_depth:.9f} W/m')
print(f'Injected current per length: {result.reaction_current_per_depth[mesh.boundary["left"]].sum():.9f} A/m')
# A same-mesh thermal consumer uses result.joule_power_density (W/m^3), never a region average.
