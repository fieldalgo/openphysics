# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Run from the repository root with the existing package environment installed."""
import numpy as np
from galerkin.mesh import rectangle_mesh
from galerkin.thermal import solve_steady_heat
from refsol.thermal import slab

mesh = rectangle_mesh(2., .7, 8, 5)
boundary = {int(i): 350. for i in mesh.boundary['left']}
boundary.update({int(i): 300. for i in mesh.boundary['right']})
result = solve_steady_heat(mesh, conductivity=12., dirichlet=boundary)
exact = slab(mesh.nodes, length=2., conductivity=12.,
             left_temperature=350., right_temperature=300.)
print('Maximum temperature error (K):', np.max(abs(result.temperature-exact.temperature)))
print('Mean heat flux (W/m^2):', result.heat_flux.mean(axis=0))
print('Left/right heat input (W/m of thickness):',
      result.reaction[mesh.boundary['left']].sum(),
      result.reaction[mesh.boundary['right']].sum())
print('Heat imbalance (W/m of thickness):', np.sum(result.load+result.reaction))
