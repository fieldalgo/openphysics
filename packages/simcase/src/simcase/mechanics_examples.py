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
