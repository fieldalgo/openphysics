# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Two explicit public calls; SI one-way quasistatic mechanics, not dynamics."""
import numpy as np
from galerkin.mesh import rectangle_mesh
from galerkin.transient_heat import solve_transient_heat
from galerkin.transient_thermal_mechanical import solve_transient_thermoelasticity

mesh = rectangle_mesh(1., 1., 4, 4)
heat = solve_transient_heat(mesh, conductivity=2., volumetric_heat_capacity=4.,
    time_s=[0., .1, .4, 1.], initial_temperature_k=np.full(mesh.num_nodes, 300.),
    dirichlet={}, heat_source=8.)
right = int(np.argmin(np.sum((mesh.nodes-[1., 0.])**2, axis=1)))
result = solve_transient_thermoelasticity(mesh, heat,
    units={'length': 'm', 'time': 's', 'temperature': 'K'}, time_indices=[0, 2, 3],
    young_modulus=2e9, poisson_ratio=.25, plane='stress',
    thermal_expansion_per_k=1e-5, reference_temperature_k=300.,
    mechanical_dirichlet={(0, 0): 0., (0, 1): 0., (right, 1): 0.})
for step in result.steps:
    expected = 1e-5*(2*step.time_s)*mesh.nodes
    np.testing.assert_allclose(step.mechanics.displacement, expected, rtol=1e-9, atol=1e-14)
    print(f'index={step.time_index}, time_s={step.time_s}, '
          f'max_displacement_m={np.max(abs(step.mechanics.displacement)):.8g}')
