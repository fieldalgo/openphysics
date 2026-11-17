# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Current-driven thermistor; fixed 2D mesh and temperature-independent k."""
import numpy as np
from galerkin.mesh import rectangle_mesh
from galerkin.temperature_joule_heating import ConductivityModel, solve_temperature_joule_heat

mesh = rectangle_mesh(1., .25, 16, 4)
left, right = mesh.boundary['left'], mesh.boundary['right']
model = ConductivityModel(lambda t: 1/(1+.5*(t-300)), (300., 400.))
# 1 A/m^2 leaves through the right edge: the inward current density is -1 A/m^2.
result = solve_temperature_joule_heat(
    mesh, method='picard', electrical_conductivity=model, thermal_conductivity=1.,
    prescribed_electric_potential={int(i): 0. for i in left}, inward_current_density={'right': -1.},
    prescribed_temperature={int(i): 300. for i in np.r_[left, right]},
    initial_temperature=300., temperature_tolerance=1e-8, relaxation_factor=1.)
print(f'Maximum temperature: {result.coupled.thermal.temperature.max():.9f} K')
print(f'Joule power: {result.coupled.generated_heat_rate_per_depth:.9f} W/m')
print(f'Iterations: {len(result.history)}')
print(f'Unrelaxed defect: {result.history[-1].temperature_change:.3e} K')
print(f'Nonlinear heat residual: {result.history[-1].relative_residual:.3e}')
