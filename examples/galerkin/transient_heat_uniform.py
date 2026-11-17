# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""First transient heat calculation: uniform heating of an insulated square."""
import numpy as np
from galerkin.mesh import rectangle_mesh
from galerkin.transient_heat import solve_transient_heat

mesh = rectangle_mesh(1., 1., 4, 4)  # metres
result = solve_transient_heat(
    mesh, thermal_conductivity=2.5, volumetric_heat_capacity=4.,
    time=np.array([0., .1, .3]),
    initial_temperature=np.full(mesh.num_nodes, 300.),
    prescribed_temperature={}, heat_source_density=8.)
print('Time (s):', result.time)
print('Mean temperature (K):', result.temperature.mean(axis=1))
print('Heat content change (J/m):',
      result.stored_heat_per_depth - result.stored_heat_per_depth[0])
print('Stored power after each step (W/m):',
      result.heat_storage_rate_per_depth.sum(axis=1))
print('Maximum flux magnitude (W/m^2):',
      np.linalg.norm(result.heat_flux, axis=2).max())
print('Maximum boundary reaction (W/m):', abs(result.reaction_heat_rate_per_depth).max())
