# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""First transient heat calculation: uniform heating of an insulated square."""
import numpy as np
from galerkin.mesh import rectangle_mesh
from galerkin.transient_heat import solve_transient_heat

mesh = rectangle_mesh(1., 1., 4, 4)  # metres
result = solve_transient_heat(
    mesh, conductivity=2.5, volumetric_heat_capacity=4.,
    time_s=np.array([0., .1, .3]),
    initial_temperature_k=np.full(mesh.num_nodes, 300.),
    dirichlet={}, heat_source=8.)
print('Time (s):', result.time_s)
print('Mean temperature (K):', result.temperature_k.mean(axis=1))
print('Heat content change (J/m):',
      result.heat_content_j_per_m - result.heat_content_j_per_m[0])
print('Stored power after each step (W/m):',
      result.storage_rate_w_per_m.sum(axis=1))
print('Maximum flux magnitude (W/m^2):',
      np.linalg.norm(result.heat_flux_w_m2, axis=2).max())
print('Maximum boundary reaction (W/m):', abs(result.reaction_w_per_m).max())
