# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Uniaxial plate document; all suffixed values are SI, the geometry is in millimetres."""

ELASTIC_PLATE = dict(openphysics='0.2', name='Uniaxial plate under 1 MPa',
    units={'length': 'mm'}, geometry={'domain': dict(xmin=0., xmax=100., ymin=0., ymax=20.)},
    materials={}, mesh={'subdivisions': [20, 4]}, study={'type': 'single'},
    results={'save_fields': True, 'plots': False},
    physics={'plate': dict(type='mechanics.elasticity2d', plane='stress',
                           young_modulus_pa=200e9, poisson_ratio=.3,
                           displacement_m={'left': {'x': 0.}, 'bottom': {'y': 0.}},
                           traction_pa={'right': [1e6, 0.]})})

THERMOELASTIC_BAR = dict(openphysics='0.2', name='Confined aluminium bar with a linear temperature',
    units={'length': 'mm', 'temperature': 'K'},
    geometry={'domain': dict(xmin=0., xmax=100., ymin=0., ymax=20.)},
    materials={}, mesh={'subdivisions': [20, 4]}, study={'type': 'single'},
    results={'save_fields': True, 'plots': False},
    physics={'bar': dict(type='mechanics.thermoelastic2d', plane='stress',
                         thermal_conductivity_w_mk=237., dirichlet_temperature_k={'left': 293.15, 'right': 353.15},
                         young_modulus_pa=70e9, poisson_ratio=.33, thermal_expansion_per_k=23e-6,
                         reference_temperature_k=293.15,
                         displacement_m={'left': {'x': 0., 'y': 0.}, 'bottom': {'y': 0.}, 'top': {'y': 0.}})})

# Region documents (version 1 geometry; E, nu, alpha and k from materials; named boundaries).

ELASTIC_REGIONS = dict(openphysics='0.2', name='Quarter of a thick steel pipe under 10 MPa inner pressure',
    units={'length': 'mm'},
    geometry={'version': 1, 'components': {'main': dict(
        dimension='2d', domain=dict(xmin=0., xmax=9., ymin=0., ymax=9.), background={'material': 'steel'},
        features=[dict(name='outside', type='rect', x=0., y=0., w=9., h=9., material=None),
                  dict(name='wall', type='circle', cx=0., cy=0., r=9., material='steel'),
                  dict(name='bore', type='circle', cx=0., cy=0., r=3., material=None)],
        finalize='later_wins',
        boundary_tags=[{'tag': 'inner', 'select': {'boundary': {'of': 'bore'}}},
                       {'tag': 'outer_wall', 'select': {'boundary': {'between': ['wall', 'outside']}}}])}},
    materials={'steel': {'young_modulus_pa': 200e9, 'poisson_ratio': .3, 'source': 'document value'}},
    mesh={'size': .5}, study={'type': 'single'}, results={'save_fields': True, 'plots': False},
    physics={'pipe': dict(type='mechanics.elasticity2d', plane='strain',
                          displacement_m={'left': {'x': 0.}, 'bottom': {'y': 0.}},
                          pressure_pa={'inner': 10e6})})

THERMOELASTIC_REGIONS = dict(openphysics='0.2', name='Steel-aluminium bimetal strip heated by 50 K',
    units={'length': 'mm', 'temperature': 'K'},
    geometry={'version': 1, 'components': {'main': dict(
        dimension='2d', domain=dict(xmin=0., xmax=50., ymin=0., ymax=2.), background={'material': 'steel'},
        features=[dict(name='aluminium', type='rect', x=0., y=1., w=50., h=1., material='aluminium')],
        finalize='later_wins')}},
    materials={'steel': {'young_modulus_pa': 200e9, 'poisson_ratio': .3, 'thermal_expansion_per_k': 12e-6,
                         'conductivity_w_mk': 45., 'source': 'document value'},
               'aluminium': {'young_modulus_pa': 70e9, 'poisson_ratio': .33, 'thermal_expansion_per_k': 23e-6,
                             'conductivity_w_mk': 237., 'source': 'document value'}},
    mesh={'size': .25}, study={'type': 'single'}, results={'save_fields': True, 'plots': False},
    physics={'strip': dict(type='mechanics.thermoelastic2d', plane='stress', reference_temperature_k=293.15,
                           dirichlet_temperature_k={'left': 343.15, 'right': 343.15, 'bottom': 343.15,
                                                    'top': 343.15},
                           displacement_m={'left': {'x': 0., 'y': 0.}})})
