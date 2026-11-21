# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Studio region documents through the wire: exact analytical references and transport identity.

Studio adds no physics, so acceptance is (A1-A3) closed-form references that P1 reproduces
exactly, checked only on the decoded HTTP arrays, (A4) equality of every wire array with
a direct ``simcase.run`` of the same document in this process, and (A5) the node cap at
exactly the mesh's node count. Mesh convergence stays with the engine's own region tests
(test_thermal_regions.py, test_transient_thermal_regions.py). Thresholds were fixed before
the implementation; node counts are derived in-process.
"""
import copy

import numpy as np
import pytest
from fastapi.testclient import TestClient

import region_studio_fixtures as fx
from simcase import Document, run
from simcase.studio import server
from simcase.studio import thermal_api as thermal
from simcase.studio import thermal_regions_api as regions
from simcase.studio import transient_thermal_api as transient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server, '_thermal_jobs', thermal.ThermalJobs())
    monkeypatch.setattr(server, '_region_limits', regions.RegionLimits())
    monkeypatch.setattr(server, '_start_thermal_thread', lambda target, args: target(*args))
    with TestClient(server.app) as value:
        yield value


def envelope(doc):
    return {'doc': doc, 'client_revision': 4, 'request_seq': 9}


def submit(client, doc):
    """Validate and run on the route of the document's physics; the identity and the result body."""
    route = '/api/thermal/transient/' if 'time' in doc['study'] else '/api/thermal/'
    validated = client.post(route+'validate', json=envelope(doc))
    assert validated.status_code == 200 and validated.json()['ok'] is True, validated.text
    accepted = client.post(route+'run', json=envelope(doc))
    assert accepted.status_code == 200, accepted.text
    identity = accepted.json()
    status = client.get('/api/jobs/'+identity['job']).json()
    assert status['status'] == 'done', status
    result = client.get('/api/jobs/'+identity['job']+'/result')
    assert result.status_code == 200, result.text
    return identity, result.json()


def frame(client, identity, field, index):
    response = client.get('/api/jobs/'+identity['job']+'/frame', params={
        'result_id': identity['result_id'], 'field': field, 'time_index': index, 'frame_seq': index})
    assert response.status_code == 200, response.text
    return np.asarray(response.json()['arrays'][field])


def history(client, identity, field, count):
    rows = []
    for start in range(0, count, transient.PAGE_ROWS):
        stop = min(count, start+transient.PAGE_ROWS)
        response = client.get('/api/jobs/'+identity['job']+'/history', params={
            'result_id': identity['result_id'], 'field': field, 'start': start, 'stop': stop, 'frame_seq': 1})
        assert response.status_code == 200, response.text
        rows.extend(response.json()['arrays'][field])
    return np.asarray(rows)


def region_areas(arrays):
    """Per-region area from the wire mesh: one positive half determinant per triangle."""
    nodes, tri = np.asarray(arrays['node_coordinates']), np.asarray(arrays['triangles'])
    ids = np.asarray(arrays['triangle_regions'])
    v = nodes[tri][:, 1:]-nodes[tri][:, :1]
    area = .5*(v[:, 0, 0]*v[:, 1, 1]-v[:, 0, 1]*v[:, 1, 0])
    return np.bincount(ids, weights=area), ids, area


# ---- A1: two-layer slab ---------------------------------------------------------------

def two_layer(size):
    return {'openphysics': '0.3', 'name': 'two-layer slab',
            'geometry': {'length_unit': 'mm', 'depth': None,
                         'domain': {'xmin': 0., 'xmax': 30., 'ymin': 0., 'ymax': 10.},
                         'background': {'material': 'filler'},
                         'shapes': [fx.rect('layer_a', 0., 0., 10., 10., 'metal')]},
            'materials': {'metal': {'thermal_conductivity': '45 W/(m K)', 'source': 'document value'},
                          'filler': {'thermal_conductivity': '1.5 W/(m K)', 'source': 'document value'}},
            'physics': {'heat1': {'type': 'thermal.steady2d', 'heat_source_density': '0 W/m^3',
                                  'prescribed_temperature': {'left': '400 K', 'right': '300 K'}}},
            'mesh': {'element_size': fx.mm(size)}, 'study': {'type': 'single'},
            'results': {'save_fields': True, 'plots': False}}


@pytest.mark.parametrize('size', [2., 1.])
def test_a1_two_layer_slab_is_exact_through_the_wire(client, size):
    q = 100./(.01/45.+.02/1.5)
    _, payload = submit(client, two_layer(size))
    assert payload['payload_format'] == regions.STEADY_PAYLOAD
    arrays = payload['arrays']
    nodes = np.asarray(arrays['node_coordinates'])
    x = nodes[:, 0]
    exact = np.where(x <= .01, 400.-q*x/45., 400.-q*.01/45.-q*(x-.01)/1.5)
    assert np.max(abs(np.asarray(arrays['temperature'])-exact))/100. <= 1e-9
    flux = np.asarray(arrays['heat_flux'])
    assert np.max(abs(flux[:, 0]-q))/q <= 1e-9
    assert np.max(abs(flux[:, 1])) <= 1e-9*q
    tri = np.asarray(arrays['triangles'])
    ids = np.asarray(arrays['triangle_regions'])
    layer = payload['summary']['region_names'].index('layer_a')
    centroid_x = nodes[tri][:, :, 0].mean(axis=1)
    np.testing.assert_array_equal(ids == layer, centroid_x < .01)
    reaction = np.asarray(arrays['reaction_heat_rate_per_depth'])
    np.testing.assert_allclose(reaction[x == 0.].sum(), q*.01, rtol=1e-9)


# ---- A2: the steady example ------------------------------------------------------------

def test_a2_steady_example_balances_its_heater_through_the_wire(client):
    _, payload = submit(client, fx.steady_example())
    arrays, summary = payload['arrays'], payload['summary']
    areas, _, _ = region_areas(arrays)
    heater = areas[summary['region_names'].index('heater')]
    np.testing.assert_allclose(np.sum(arrays['generated_heat_rate_per_depth']), 5e6*heater, rtol=1e-12)
    np.testing.assert_allclose(heater, summary['regions']['heater']['area']['value'], rtol=1e-12)
    assert abs(heater/(np.pi*4e-6)-1) < .01
    assert summary['relative_conservation_residual']['value'] < 1e-10
    np.testing.assert_allclose(summary['outward_heat_rate_per_depth']['value'],
                               summary['generated_heat_rate_per_depth']['value'], rtol=1e-10)


# ---- A3: uniform heating rate in the transient example --------------------------------

def test_a3_transient_uniform_heating_rate_is_exact_through_the_wire(client):
    doc = fx.transient_example()
    rate = .01
    capacity = {}
    for name, m in (('steel_plate', 'steel'), ('background', 'insulation')):
        value, unit = doc['materials'][m]['volumetric_heat_capacity'].split(' ', 1)
        assert unit == 'J/(m^3 K)'
        capacity[name] = float(value)
    doc['physics']['heat1'].update(prescribed_temperature={},
                                   heat_source_density={name: f'{rate*c!r} W/m^3' for name, c in capacity.items()})
    identity, manifest = submit(client, doc)
    assert manifest['payload_format'] == regions.TRANSIENT_MANIFEST
    times = np.asarray(manifest['time'])
    for index, t in enumerate(times):
        assert np.max(abs(frame(client, identity, 'temperature', index)-(300.+rate*t))) <= 1e-10*300.
        assert np.max(abs(frame(client, identity, 'heat_flux', index))) <= 1e-9
    areas, _, _ = region_areas(manifest['arrays'])
    names = manifest['summary']['region_names']
    heat = sum(capacity[name]*areas[i] for i, name in enumerate(names))*(300.+rate*times)
    np.testing.assert_allclose(history(client, identity, 'stored_heat_per_depth', len(times)), heat, rtol=1e-10)
    dom = doc['geometry']['domain']
    np.testing.assert_allclose(areas.sum(), (dom['xmax']-dom['xmin'])*(dom['ymax']-dom['ymin'])*1e-6, rtol=1e-12)


# ---- A4: transport identity -------------------------------------------------------------

def test_a4_steady_wire_arrays_equal_a_direct_run(client):
    doc = fx.steady_example()
    _, payload = submit(client, doc)
    direct = run(Document.from_dict(copy.deepcopy(doc)), verbose=False)
    expected = {key: getattr(direct, prop) for key, prop in thermal.PROPERTIES.items()}
    expected['triangle_regions'] = direct.triangle_regions
    assert set(payload['arrays']) == set(expected)
    for key, value in expected.items():
        assert np.array_equal(np.asarray(payload['arrays'][key]), value), key
    assert payload['summary']['region_names'] == direct.region_names


def test_a4_transient_wire_arrays_frames_and_pages_equal_a_direct_run(client):
    doc = fx.transient_example()
    identity, manifest = submit(client, doc)
    direct = run(Document.from_dict(copy.deepcopy(doc)), verbose=False)
    static = {'node_coordinates': direct.node_coordinates, 'triangles': direct.triangles,
              'prescribed_node_ids': direct.prescribed_node_ids, 'triangle_regions': direct.region_ids}
    assert set(manifest['arrays']) == set(static)
    for key, value in static.items():
        assert np.array_equal(np.asarray(manifest['arrays'][key]), value), key
    assert np.array_equal(np.asarray(manifest['time']), direct.time)
    for index in range(len(direct.time)):
        assert np.array_equal(frame(client, identity, 'temperature', index), direct.temperature[index])
        assert np.array_equal(frame(client, identity, 'heat_flux', index), direct.heat_flux[index])
    for field in ('stored_heat_per_depth', 'thermal_energy_functional_per_depth'):
        assert np.array_equal(history(client, identity, field, len(direct.time)), getattr(direct, field)), field
    assert manifest['summary']['region_names'] == list(direct.region_names)


# ---- A5: the node cap at the mesh's node count -----------------------------------------

def test_a5_node_cap_at_and_below_the_mesh_node_count(client, monkeypatch):
    import galerkin.thermal
    doc = fx.steady_example(2.0)
    nodes = len(run(Document.from_dict(copy.deepcopy(doc)), verbose=False).node_coordinates)
    monkeypatch.setattr(server, '_thermal_jobs', thermal.ThermalJobs(thermal.ThermalLimits(max_nodes=nodes)))
    _, payload = submit(client, doc)
    assert len(payload['arrays']['node_coordinates']) == nodes
    monkeypatch.setattr(server, '_thermal_jobs', thermal.ThermalJobs(thermal.ThermalLimits(max_nodes=nodes-1)))
    def forbidden(*args, **kwargs):
        raise AssertionError('a mesh over the node cap reached the solver')
    monkeypatch.setattr(galerkin.thermal, 'solve_steady_heat', forbidden)
    accepted = client.post('/api/thermal/run', json=envelope(doc))
    assert accepted.status_code == 200, accepted.text
    status = client.get('/api/jobs/'+accepted.json()['job']).json()
    assert status['status'] == 'error' and status['error']['code'] == 'mesh_limit_exceeded', status
    assert f'max_nodes={nodes-1}' in status['error']['message']
    assert server._thermal_jobs._active == 0
