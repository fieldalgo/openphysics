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
from simcase.thermal_regions import build_region_mesh_03, handoff_03

#: length_unit and the factor of the shape numbers (tagged element sizes keep their own unit)
UNITS = [('mm', '1'), ('m', '0.001'), ('um', '1000'), ('nm', '1000000')]
#: summary keys that hold the authored text, wall times or findings, not results
TEXTUAL = ('resolved_inputs', 'defaults_applied', 'diagnostics', 'extent', 'timing')


def _problem(transient=False):
    data = {
        'openphysics': '0.3', 'name': 'canonical region heat',
        'geometry': {
            'length_unit': 'mm', 'depth': None,
            'domain': {'xmin': 123.456, 'xmax': 133.456, 'ymin': -3.2, 'ymax': 2.8},
            'background': {'material': 'a', 'element_size': '1.5 mm'},
            'shapes': [
                {'name': 'plate', 'type': 'rect', 'material': 'b',
                 'x': 123.456, 'y': -3.2, 'w': 4., 'h': 6., 'element_size': '1 mm'},
                {'name': 'disk', 'type': 'circle', 'material': 'a',
                 'cx': 125.456, 'cy': -0.2, 'r': .8, 'element_size': '0.4 mm'},
                {'name': 'patch', 'type': 'polygon', 'material': 'b',
                 'points': [[129.456, -2.2], [132.456, -2.2],
                            [132.456, 1.8], [129.456, 1.8]], 'element_size': '0.75 mm'}]},
        'materials': {'a': {'thermal_conductivity': '2 W/(m K)'}, 'b': {'thermal_conductivity': '9 W/(m K)'}},
        'physics': {'heat': {'type': 'thermal.steady2d',
                             'heat_source_density': {'plate': '2e5 W/m^3', 'disk': '3e5 W/m^3'},
                             'prescribed_temperature': {'left': '300 K'},
                             'inward_heat_flux': {'bottom': '40 W/m^2'},
                             'convection': {'right': {'heat_transfer_coefficient': '25 W/(m^2 K)',
                                                      'ambient_temperature': '290 K'}}}},
        'mesh': {'element_size': '1.5 mm'}, 'study': {'type': 'single'},
        'results': {'save_fields': True, 'plots': False}}
    if transient:
        for name, material in data['materials'].items():
            material['volumetric_heat_capacity'] = '2e6 J/(m^3 K)' if name == 'a' else '4e6 J/(m^3 K)'
        p = data['physics']['heat']
        p['type'] = 'thermal.transient2d'
        p.pop('inward_heat_flux')
        p.pop('convection')
        p['prescribed_temperature'] = {}
        p['initial_temperature'] = {'type': 'affine', 'reference_temperature': '300 K',
                                    'temperature_gradient': {'unit': 'K/m', 'values': [1e8, 2e8]}}
        data['study'] = {'type': 'transient', 'time': {'unit': 's', 'values': [0., .1, .3]}}
    return data


def _written_in(data, unit, factor):
    """The same problem with its shape numbers in ``unit``; the element sizes are quantities."""
    data = copy.deepcopy(data)
    def scale(v):
        return float(Fraction(str(v))*Fraction(factor))
    g = data['geometry']
    g['length_unit'] = unit
    g['domain'] = {k: scale(v) for k, v in g['domain'].items()}
    for shape in g['shapes']:
        for key in ('x', 'y', 'w', 'h', 'cx', 'cy', 'r'):
            if key in shape:
                shape[key] = scale(shape[key])
        if 'points' in shape:
            shape['points'] = [[scale(v) for v in point] for point in shape['points']]
    return data


def _hexed(value):
    if isinstance(value, dict):
        return {k: _hexed(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_hexed(v) for v in value]
    return value.hex() if isinstance(value, float) else value


@pytest.mark.parametrize('transient', [False, True])
def test_region_mesh_solve_and_saved_fields_are_identical_across_units(transient, tmp_path):
    """P2-5 (region heat rows): the shape numbers in mm, m, um and nm give the same mesh, the
    same saved arrays and the same summary values, bit for bit."""
    reference_mesh = reference_arrays = None
    for index, (unit, factor) in enumerate(UNITS):
        data = _written_in(_problem(transient), unit, factor)
        original = copy.deepcopy(data)
        doc = Document.from_dict(data)
        validated = doc.canonical_json()
        mesh, materials, tri = build_region_mesh_03(doc)
        result = run(doc, verbose=False)
        out = result.save(tmp_path / str(index))
        assert doc.canonical_json() == validated and data == original
        assert json.loads((out/'model.json').read_text()) == original
        summary = json.loads((out/'summary.json').read_text())
        assert 'mesh_length_unit' not in summary and 'units' not in summary
        assert summary['resolved_inputs']['geometry.domain.xmin']['length_unit'] == unit
        # The achieved smallest angle is measured on the triangulation in the document's own
        # units, as before the units batch (P2-1 keeps it bitwise against format 0.2), so it is
        # the one summary value that moves by rounding across length units: compared to 1e-13
        # relative. This is a stated deviation from P2-5 ("identical summary values"), not a pass
        # of it: measured at most 335 ulp (m against mm; 1.9e-14 rad, 3.8e-14 relative) on this
        # problem. P2-1 and P2-5 cannot both be bitwise for this value until the mesher step
        # measures the angle on one frame.
        angle = summary.get('minimum_triangle_angle', {}).get('value', 0.0)   # steady only
        values = _hexed({k: v for k, v in summary.items() if k not in TEXTUAL + ('minimum_triangle_angle',)})
        with np.load(out/'fields.npz', allow_pickle=False) as fields:
            arrays = {k: fields[k].copy() for k in fields.files if k != 'metadata_json'}
        # Diagnostic tri remains in document units; solver and saved nodes are SI.
        assert tri.nodes[:, 0].min() == pytest.approx(handoff_03(doc).domain['xmin'], rel=1e-15)
        np.testing.assert_array_equal(arrays['node_coordinates'], mesh.nodes)
        if transient:
            corner = np.flatnonzero(np.all(mesh.nodes == mesh.nodes.min(axis=0), axis=1))
            assert len(corner) == 1
            assert arrays['temperature'][0, corner[0]] == 300.
        if reference_mesh is None:
            reference_mesh, reference_arrays, reference_values, reference_angle = mesh, arrays, values, angle
            reference_materials = materials
            continue
        assert values == reference_values
        assert abs(angle - reference_angle) <= 1e-13 * reference_angle
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
