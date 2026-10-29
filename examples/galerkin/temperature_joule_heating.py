# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Current-driven thermistor; fixed 2D mesh and temperature-independent k."""
import numpy as np
from galerkin.mesh import rectangle_mesh
from galerkin.temperature_joule_heating import ConductivityModel, solve_temperature_joule_heat

mesh = rectangle_mesh(1., .25, 16, 4)
left, right = mesh.boundary['left'], mesh.boundary['right']
model = ConductivityModel(lambda t: 1/(1+.5*(t-300)), (300., 400.))
result = solve_temperature_joule_heat(
    mesh, method='picard', electrical_conductivity=model, thermal_conductivity=1.,
    electric_dirichlet={int(i): 0. for i in left}, outward_current={'right': 1.},
    thermal_dirichlet={int(i): 300. for i in np.r_[left, right]},
    initial_temperature=300., relaxation=1.)
print(f'Maximum temperature: {result.coupled.thermal.temperature.max():.9f} K')
print(f'Joule power: {result.coupled.source_power_per_length:.9f} W/m')
print(f'Iterations: {len(result.history)}')
print(f'Unrelaxed defect: {result.history[-1].temperature_defect:.3e} K')
print(f'Nonlinear heat residual: {result.history[-1].nonlinear_heat_residual:.3e}')
