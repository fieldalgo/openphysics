# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Headless-only homogeneous steady heat examples; thermal constants use SI."""
import copy

THERMAL_SLAB = {
    'openphysics': '0.2', 'name': 'Steady heat slab',
    'units': {'length': 'mm', 'temperature': 'K'},
    'geometry': {'domain': {'xmin': 0., 'xmax': 30., 'ymin': 0., 'ymax': 20.}},
    'materials': {},
    'physics': {'heat1': {'type': 'thermal.steady2d', 'conductivity_w_mk': 12.5,
                          'heat_source_w_m3': 0., 'dirichlet_temperature_k': {'left': 280., 'right': 315.}}},
    'mesh': {'subdivisions': [32, 16]}, 'study': {'type': 'single'},
    'results': {'save_fields': True, 'plots': False},
}
THERMAL_MIXED = copy.deepcopy(THERMAL_SLAB)
THERMAL_MIXED['name'] = 'Steady heat with uniform source'
THERMAL_MIXED['physics']['heat1']['heat_source_w_m3'] = 1e5

# Named material regions (EM-style shapes); conductivity comes from materials.
THERMAL_REGIONS = {
    'openphysics': '0.2', 'name': 'Heated steel plate in insulation',
    'units': {'length': 'mm', 'temperature': 'K'},
    'geometry': {'domain': {'xmin': 0., 'xmax': 40., 'ymin': 0., 'ymax': 20.},
                 'background': {'material': 'insulation'},
                 'shapes': [{'name': 'plate', 'type': 'rect', 'x': 5., 'y': 5., 'w': 30., 'h': 6.,
                             'material': 'steel'},
                            {'name': 'heater', 'type': 'circle', 'cx': 20., 'cy': 8., 'r': 2.,
                             'material': 'copper', 'mesh_size': .5}]},
    'materials': {'steel': {'conductivity_w_mk': 45., 'source': 'document value'},
                  'copper': {'conductivity_w_mk': 400., 'source': 'document value'},
                  'insulation': {'conductivity_w_mk': .04, 'source': 'document value'}},
    'physics': {'heat1': {'type': 'thermal.steady2d', 'heat_source_w_m3': {'heater': 5e6},
                          'dirichlet_temperature_k': {'bottom': 300.},
                          'convection': {'top': {'h_w_m2k': 10., 'ambient_temperature_k': 295.}}}},
    'mesh': {'size': 2., 'min_angle': 28.}, 'study': {'type': 'single'},
    'results': {'save_fields': True, 'plots': False},
}
