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
