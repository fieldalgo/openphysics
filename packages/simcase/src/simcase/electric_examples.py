# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Homogeneous resistor and Joule documents, format 0.3: values carry their units, the geometry
its length_unit."""
import copy

ELECTRIC_RECTANGLE = {
    'openphysics': '0.3', 'name': 'Homogeneous rectangle resistor',
    'geometry': {'length_unit': 'm', 'depth': None, 'domain': {'xmin': 0., 'xmax': 1., 'ymin': 0., 'ymax': .2}},
    'materials': {}, 'mesh': {'subdivision_count': [24, 6]}, 'study': {'type': 'single'},
    'results': {'save_fields': True, 'plots': False},
    'physics': {'electric': {'type': 'electric.steady2d', 'electrical_conductivity': '2 S/m',
                             'prescribed_electric_potential': {'left': '1 V', 'right': '0 V'}}},
}
JOULE_RECTANGLE = copy.deepcopy(ELECTRIC_RECTANGLE)
JOULE_RECTANGLE['name'] = 'Constant-property Joule heated rectangle'
JOULE_RECTANGLE['physics']['electric'].update(type='joule.steady2d', thermal_conductivity='1 W/(m K)',
                                              prescribed_temperature={'left': '300 K', 'right': '300 K'})
JOULE_TEMPERATURE = copy.deepcopy(JOULE_RECTANGLE)
JOULE_TEMPERATURE['name'] = 'Temperature-dependent Joule heated rectangle'
_p = JOULE_TEMPERATURE['physics']['electric']
_p.pop('electrical_conductivity')
_p.update(type='joule.temperature2d', initial_temperature='300 K',
          electrical_conductivity={'model': 'linear_resistivity', 'reference_conductivity': '2 S/m',
                                   'reference_temperature': '300 K', 'resistivity_temperature_coefficient': '0.01 1/K',
                                   'valid': {'temperature': ['290 K', '400 K']}},
          iteration={'relaxation_factor': .5, 'temperature_tolerance': '1e-8 K', 'relative_tolerance': 1e-10,
                     'iteration_limit': 100})
del _p
