# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Mechanics documents, format 0.3: values carry their units, each geometry its length_unit (mm)."""

ELASTIC_PLATE = {
    'openphysics': '0.3', 'name': 'Uniaxial plate under 1 MPa',
    'geometry': {'length_unit': 'mm', 'depth': None, 'domain': {'xmin': 0., 'xmax': 100., 'ymin': 0., 'ymax': 20.}},
    'materials': {}, 'mesh': {'subdivision_count': [20, 4]}, 'study': {'type': 'single'},
    'results': {'save_fields': True, 'plots': False},
    'physics': {'plate': {'type': 'mechanics.elasticity2d', 'plane': 'stress', 'youngs_modulus': '200 GPa',
                          'poisson_ratio': .3,
                          'prescribed_displacement': {'left': {'x': '0 mm'}, 'bottom': {'y': '0 mm'}},
                          'traction': {'right': ['1 MPa', '0 MPa']}}},
}

THERMOELASTIC_BAR = {
    'openphysics': '0.3', 'name': 'Confined aluminium bar with a linear temperature',
    'geometry': {'length_unit': 'mm', 'depth': None, 'domain': {'xmin': 0., 'xmax': 100., 'ymin': 0., 'ymax': 20.}},
    'materials': {}, 'mesh': {'subdivision_count': [20, 4]}, 'study': {'type': 'single'},
    'results': {'save_fields': True, 'plots': False},
    'physics': {'bar': {'type': 'mechanics.thermoelastic2d', 'plane': 'stress',
                        'thermal_conductivity': '237 W/(m K)',
                        'prescribed_temperature': {'left': '293.15 K', 'right': '353.15 K'},
                        'youngs_modulus': '70 GPa', 'poisson_ratio': .33, 'linear_expansion_coefficient': '23 ppm/K',
                        'stress_free_temperature': '293.15 K',
                        'prescribed_displacement': {'left': {'x': '0 mm', 'y': '0 mm'}, 'bottom': {'y': '0 mm'},
                                                    'top': {'y': '0 mm'}}}},
}

# Region documents (version 1 geometry; youngs_modulus, poisson_ratio, linear_expansion_coefficient
# and thermal_conductivity from materials; named boundaries).

ELASTIC_REGIONS = {
    'openphysics': '0.3', 'name': 'Quarter of a thick steel pipe under 10 MPa inner pressure',
    'geometry': {'version': 1, 'components': {'main': {
        'dimension': '2d', 'length_unit': 'mm', 'depth': None,
        'domain': {'xmin': 0., 'xmax': 9., 'ymin': 0., 'ymax': 9.}, 'background': {'material': 'steel'},
        'features': [{'name': 'outside', 'type': 'rect', 'x': 0., 'y': 0., 'w': 9., 'h': 9., 'material': None},
                     {'name': 'wall', 'type': 'circle', 'cx': 0., 'cy': 0., 'r': 9., 'material': 'steel'},
                     {'name': 'bore', 'type': 'circle', 'cx': 0., 'cy': 0., 'r': 3., 'material': None}],
        'finalize': 'later_wins',
        'boundary_tags': [{'tag': 'inner', 'select': {'boundary': {'of': 'bore'}}},
                          {'tag': 'outer_wall', 'select': {'boundary': {'between': ['wall', 'outside']}}}]}}},
    'materials': {'steel': {'youngs_modulus': '200 GPa', 'poisson_ratio': .3, 'source': 'document value'}},
    'mesh': {'element_size': '0.5 mm'}, 'study': {'type': 'single'}, 'results': {'save_fields': True, 'plots': False},
    'physics': {'pipe': {'type': 'mechanics.elasticity2d', 'plane': 'strain',
                         'prescribed_displacement': {'left': {'x': '0 mm'}, 'bottom': {'y': '0 mm'}},
                         'gauge_pressure': {'inner': '10 MPa'}}},
}

THERMOELASTIC_REGIONS = {
    'openphysics': '0.3', 'name': 'Steel-aluminium bimetal strip heated by 50 K',
    'geometry': {'version': 1, 'components': {'main': {
        'dimension': '2d', 'length_unit': 'mm', 'depth': None,
        'domain': {'xmin': 0., 'xmax': 50., 'ymin': 0., 'ymax': 2.}, 'background': {'material': 'steel'},
        'features': [{'name': 'aluminium', 'type': 'rect', 'x': 0., 'y': 1., 'w': 50., 'h': 1.,
                      'material': 'aluminium'}],
        'finalize': 'later_wins'}}},
    'materials': {'steel': {'youngs_modulus': '200 GPa', 'poisson_ratio': .3, 'linear_expansion_coefficient': '12 ppm/K',
                            'thermal_conductivity': '45 W/(m K)', 'source': 'document value'},
                  'aluminium': {'youngs_modulus': '70 GPa', 'poisson_ratio': .33,
                                'linear_expansion_coefficient': '23 ppm/K', 'thermal_conductivity': '237 W/(m K)',
                                'source': 'document value'}},
    'mesh': {'element_size': '0.25 mm'}, 'study': {'type': 'single'}, 'results': {'save_fields': True, 'plots': False},
    'physics': {'strip': {'type': 'mechanics.thermoelastic2d', 'plane': 'stress', 'stress_free_temperature': '293.15 K',
                          'prescribed_temperature': {'left': '343.15 K', 'right': '343.15 K', 'bottom': '343.15 K',
                                                     'top': '343.15 K'},
                          'prescribed_displacement': {'left': {'x': '0 mm', 'y': '0 mm'}}}},
}
