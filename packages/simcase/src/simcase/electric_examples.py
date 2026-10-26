# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Homogeneous resistor and steady Joule documents; all suffixed values are SI."""
import copy

ELECTRIC_RECTANGLE = dict(openphysics='0.2', name='Homogeneous rectangle resistor',
    units={'length': 'm'}, geometry={'domain': dict(xmin=0., xmax=1., ymin=0., ymax=.2)},
    materials={}, mesh={'subdivisions': [24, 6]}, study={'type': 'single'},
    results={'save_fields': True, 'plots': False},
    physics={'electric': dict(type='electric.steady2d', conductivity_s_m=2.,
                             dirichlet_potential_v={'left': 1., 'right': 0.})})
JOULE_RECTANGLE = copy.deepcopy(ELECTRIC_RECTANGLE)
JOULE_RECTANGLE['name'] = 'Constant-property Joule heated rectangle'
JOULE_RECTANGLE['units']['temperature'] = 'K'
JOULE_RECTANGLE['physics']['electric'].update(type='joule.steady2d', thermal_conductivity_w_mk=1.,
    dirichlet_temperature_k={'left': 300., 'right': 300.})
JOULE_TEMPERATURE = copy.deepcopy(JOULE_RECTANGLE)
JOULE_TEMPERATURE['name'] = 'Temperature-dependent Joule heated rectangle'
p = JOULE_TEMPERATURE['physics']['electric']
p.pop('conductivity_s_m')
p.update(type='joule.temperature2d', initial_temperature_k=300.,
    conductivity_model=dict(type='linear_resistivity', reference_conductivity_s_m=2.,
        reference_temperature_k=300., alpha_per_k=.01, temperature_range_k=[290., 400.]),
    iteration=dict(relaxation=.5, temperature_atol_k=1e-8, relative_tolerance=1e-10, max_iterations=100))
