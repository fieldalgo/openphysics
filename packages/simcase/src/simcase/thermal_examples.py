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

# Transient region document: steel plate and insulation heated from t = 0.
TRANSIENT_THERMAL_REGIONS = {
    'openphysics': '0.2', 'name': 'Heating a steel and insulation wall',
    'units': {'length': 'mm', 'temperature': 'K', 'time': 's'},
    'geometry': {'domain': {'xmin': 0., 'xmax': 30., 'ymin': 0., 'ymax': 5.},
                 'background': {'material': 'insulation'},
                 'shapes': [{'name': 'steel_plate', 'type': 'rect', 'x': 0., 'y': 0., 'w': 10., 'h': 5.,
                             'material': 'steel'}]},
    'materials': {'steel': {'conductivity_w_mk': 45., 'volumetric_heat_capacity_j_m3k': 3.6e6,
                            'source': 'document value'},
                  'insulation': {'conductivity_w_mk': .5, 'volumetric_heat_capacity_j_m3k': 1.2e6,
                                 'source': 'document value'}},
    'physics': {'heat1': {'type': 'thermal.transient2d', 'initial_temperature_k': 300.,
                          'heat_source_w_m3': {'steel_plate': 2e5, 'background': 5e4},
                          'dirichlet_temperature_k': {'left': 300., 'right': 300.}}},
    'mesh': {'size': 2., 'min_angle': 28.},
    'study': {'type': 'transient', 'time_s': [0., 5., 10., 20., 40., 60., 90., 120., 180.]},
    'results': {'save_fields': True, 'plots': False},
}
