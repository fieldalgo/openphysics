# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Identical physical region heat problems must reach the same discrete solve.

Fixture unit changes use decimal arithmetic independently of production converters.
No tolerances are used for the cross-unit comparison (including saved arrays).
"""
import copy
from fractions import Fraction
import json

import numpy as np
import pytest

from simcase import Document, run
from simcase.thermal_regions import build_region_mesh

UNITS = [('mm', '1'), ('m', '0.001'), ('um', '1000'), ('nm', '1000000'),
         ({'in_m': 2e-5}, '50')]


def _problem(transient=False):
    data = {
        'openphysics': '0.2', 'name': 'canonical region heat',
        'units': {'length': 'mm', 'temperature': 'K'},
        'geometry': {
            'domain': {'xmin': 123.456, 'xmax': 133.456, 'ymin': -3.2, 'ymax': 2.8},
            'background': {'material': 'a', 'mesh_size': 1.5},
            'shapes': [
                {'name': 'plate', 'type': 'rect', 'material': 'b',
                 'x': 123.456, 'y': -3.2, 'w': 4., 'h': 6., 'mesh_size': 1.},
                {'name': 'disk', 'type': 'circle', 'material': 'a',
                 'cx': 125.456, 'cy': -0.2, 'r': .8, 'mesh_size': .4},
                {'name': 'patch', 'type': 'polygon', 'material': 'b',
                 'points': [[129.456, -2.2], [132.456, -2.2],
                            [132.456, 1.8], [129.456, 1.8]], 'mesh_size': .75}]},
        'materials': {'a': {'conductivity_w_mk': 2.}, 'b': {'conductivity_w_mk': 9.}},
        'physics': {'heat': {'type': 'thermal.steady2d',
                             'heat_source_w_m3': {'plate': 2e5, 'disk': 3e5},
                             'dirichlet_temperature_k': {'left': 300.},
                             'outward_flux_w_m2': {'bottom': -40.},
                             'convection': {'right': {'h_w_m2k': 25., 'ambient_temperature_k': 290.}}}},
        'mesh': {'size': 1.5}, 'study': {'type': 'single'},
        'results': {'save_fields': True, 'plots': False}}
    if transient:
        data['units']['time'] = 's'
        for material in data['materials'].values():
            material['volumetric_heat_capacity_j_m3k'] = 2e6 if material['conductivity_w_mk'] == 2 else 4e6
        p = data['physics']['heat']
        p['type'] = 'thermal.transient2d'
        p.pop('outward_flux_w_m2')
        p.pop('convection')
        p['dirichlet_temperature_k'] = {}
        p['initial_temperature_k'] = {'type': 'affine', 'origin_temperature_k': 300.,
                                      'gradient_k_per_m': [1e8, 2e8]}
        data['study'] = {'type': 'transient', 'time_s': [0., .1, .3]}
    return data


def _written_in(data, unit, factor):
    data = copy.deepcopy(data)
    def scale(v):
        return float(Fraction(str(v))*Fraction(factor))
    data['units']['length'] = unit
    g = data['geometry']
    g['domain'] = {k: scale(v) for k, v in g['domain'].items()}
    g['background']['mesh_size'] = scale(g['background']['mesh_size'])
    for shape in g['shapes']:
        for key in ('x', 'y', 'w', 'h', 'cx', 'cy', 'r', 'mesh_size'):
            if key in shape:
                shape[key] = scale(shape[key])
        if 'points' in shape:
            shape['points'] = [[scale(v) for v in point] for point in shape['points']]
    data['mesh']['size'] = scale(data['mesh']['size'])
    return data


@pytest.mark.parametrize('transient', [False, True])
def test_region_mesh_solve_and_saved_fields_are_identical_across_units(transient, tmp_path):
    reference_mesh = reference_arrays = None
    for index, (unit, factor) in enumerate(UNITS):
        data = _written_in(_problem(transient), unit, factor)
        original = copy.deepcopy(data)
        doc = Document.from_dict(data)
        validated = copy.deepcopy(doc.data)
        mesh, materials, tri = build_region_mesh(doc)
        result = run(doc, verbose=False)
        out = result.save(tmp_path / str(index))
        assert doc.data == validated and data == original
        assert json.loads((out/'model.json').read_text()) == validated
        summary = json.loads((out/'summary.json').read_text())
        assert summary['mesh_length_unit'] == 'm'
        assert summary['units']['length'] == unit
        with np.load(out/'fields.npz', allow_pickle=False) as fields:
            arrays = {k: fields[k].copy() for k in fields.files if k != 'metadata_json'}
        # Diagnostic tri remains in document units; solver and saved nodes are SI.
        assert tri.nodes[:, 0].min() == pytest.approx(doc.domain['xmin'], rel=1e-15)
        np.testing.assert_array_equal(arrays['nodes_m'], mesh.nodes)
        if transient:
            corner = np.flatnonzero(np.all(mesh.nodes == mesh.nodes.min(axis=0), axis=1))
            assert len(corner) == 1
            assert arrays['temperature_k'][0, corner[0]] == 300.
        if reference_mesh is None:
            reference_mesh, reference_arrays = mesh, arrays
            reference_materials = materials
            continue
        assert materials == reference_materials
        assert mesh.region_names == reference_mesh.region_names
        for attr in ('nodes', 'triangles', 'regions'):
            np.testing.assert_array_equal(getattr(mesh, attr), getattr(reference_mesh, attr))
        for attr in ('boundary', 'boundary_edges'):
            assert getattr(mesh, attr).keys() == getattr(reference_mesh, attr).keys()
            for side in getattr(mesh, attr):
                np.testing.assert_array_equal(getattr(mesh, attr)[side], getattr(reference_mesh, attr)[side])
        assert arrays.keys() == reference_arrays.keys()
        for key in arrays:
            np.testing.assert_array_equal(arrays[key], reference_arrays[key], err_msg=key)
