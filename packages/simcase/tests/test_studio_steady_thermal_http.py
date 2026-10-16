# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Dedicated steady Studio HTTP and resource contracts; no private solver API."""
import asyncio
import copy
from dataclasses import replace
import json
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from simcase import Document, ThermalRunResult, examples
from simcase.studio import server
from simcase.studio import thermal_api as thermal


def model(boundary=False, robin_only=False):
    p = dict(type='thermal.steady2d', conductivity_w_mk=2., heat_source_w_m3=0.,
             dirichlet_temperature_k={'left': 300., 'right': 293.})
    if boundary:
        p.update(dirichlet_temperature_k={'left': 300.}, outward_flux_w_m2={'right': 2.},
                 convection={'right': {'h_w_m2k': 4., 'ambient_temperature_k': 290.}})
    if robin_only:
        p.update(dirichlet_temperature_k={}, outward_flux_w_m2={},
                 convection={'right': {'h_w_m2k': 4., 'ambient_temperature_k': 290.}})
    return dict(openphysics='0.2', name='Studio steady control',
                units={'length': 'm', 'temperature': 'K'},
                geometry={'domain': dict(xmin=0., xmax=1., ymin=0., ymax=1.)},
                materials={}, physics={'heat1': p}, mesh={'subdivisions': [2, 2]},
                study={'type': 'single'}, results={'save_fields': True, 'plots': False})


def envelope(doc=None, revision=12, sequence=7):
    return {'doc': model() if doc is None else doc,
            'client_revision': revision, 'request_seq': sequence}


@pytest.fixture
def client(monkeypatch):
    jobs = thermal.ThermalJobs()
    monkeypatch.setattr(server, '_thermal_jobs', jobs)
    monkeypatch.setattr(server, '_start_thermal_thread', lambda target, args: target(*args))
    with TestClient(server.app) as value:
        yield value


@pytest.fixture
def lifecycle_client(client, monkeypatch):
    # Synthetic public-result interface for lifecycle tests on the pre-P2 branch.
    # Real solver positive controls above use the unmodified public dependency.
    monkeypatch.setattr(thermal, 'runtime_available', lambda: True)
    monkeypatch.setattr(server, 'run', lambda *a, **k: fake_result(legacy=True))
    return client


def post(client, route='/api/thermal/run', body=None):
    return client.post(route, json=envelope() if body is None else body)


def assert_no_active(jobs):
    assert jobs._active == jobs._reserved_bytes == jobs._pending == 0


def forbid_allocation(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('refused request reached uuid/thread/run')
    monkeypatch.setattr(server, 'uuid', SimpleNamespace(uuid4=forbidden))
    monkeypatch.setattr(server, '_start_thermal_thread', forbidden)
    monkeypatch.setattr(server, 'run', forbidden)


def test_capabilities_are_truthful_about_public_runtime(client):
    response = client.get('/api/capabilities')
    assert response.status_code == 200
    c = response.json()
    assert c['capability_format'] == 'studio-capabilities-v1'
    heat = c[thermal.KIND]
    assert heat['mesh_preview'] is False and heat['mesh_from_result'] is True
    assert heat['time_navigation'] is False
    assert heat['run_enabled'] == thermal.runtime_available()
    assert (thermal.V2[0] in heat['result_formats']) == thermal.v2_available()
    assert heat['limits']['request_bytes'] == 1048576
    assert c['thermal.transient2d']['supported'] is False
    assert c['em.cavity3d']['supported'] is False


def test_real_public_v1_validation_run_and_immutable_result(client):
    before = copy.deepcopy(envelope())
    validated = post(client, '/api/thermal/validate', before)
    assert validated.status_code == 200 and validated.json()['ok'] is True
    response = post(client, body=before)
    if not thermal.runtime_available():
        assert response.status_code == 400
        assert response.json()['error']['code'] == 'unsupported_public_api'
        assert_no_active(server._thermal_jobs)
        return  # No public positive execution claim before the P2 dependency exists.
    assert response.status_code == 200, response.text
    token = response.json()
    assert set(token) == {'kind', 'job', 'result_id', 'client_revision', 'request_seq'}
    status = client.get('/api/jobs/'+token['job']).json()
    assert status['status'] == 'done' and status['has_result']
    assert set(status) == set(token) | {'status', 'log', 'error', 'has_result'}
    result = client.get('/api/jobs/'+token['job']+'/result')
    assert result.status_code == 200, result.text
    assert result.headers['cache-control'] == 'no-store'
    data = result.json()
    assert data['payload_format'] == 'studio-thermal-steady-v1'
    assert data['result_format'] == thermal.V1[0]
    assert set(data['arrays']) == set(thermal.BASE_FIELDS)
    assert data['display_length_in_m'] == 1.
    assert 'coordinates' not in data and 'neff' not in data
    nodes = np.asarray(data['arrays']['nodes_m'])
    np.testing.assert_allclose((np.asarray(data['arrays']['temperature_k'])-(300.-7.*nodes[:, 0]))/7.,
                               0., rtol=0., atol=1e-10)
    np.testing.assert_allclose((np.asarray(data['arrays']['heat_flux_w_m2'])-[14., 0.])/14.,
                               0., rtol=0., atol=1e-10)
    encoded = result.content
    data['arrays']['temperature_k'][0] = -999.
    assert client.get('/api/jobs/'+token['job']+'/result').content == encoded
    assert before == envelope()
    assert_no_active(server._thermal_jobs)


@pytest.mark.parametrize('robin_only', [False, True])
def test_v2_public_run_or_explicit_unavailable_dependency(client, robin_only):
    body = envelope(model(boundary=True, robin_only=robin_only))
    response = post(client, body=body)
    if not thermal.v2_available():
        # Pre-P2 feature branch is deliberately v1-only, never a claimed v2 pass.
        assert response.status_code == 400
        assert response.json()['error']['code'] == 'unsupported_result_format'
        assert not server._thermal_jobs._records
        return
    assert response.status_code == 200, response.text
    token = response.json()
    status = client.get('/api/jobs/'+token['job']).json()
    assert status['status'] == 'done', status
    data = client.get('/api/jobs/'+token['job']+'/result').json()
    assert set(data['arrays']) == set(thermal.PROPERTIES)
    assert data['result_format'] == thermal.V2[0]
    if robin_only:
        assert data['arrays']['dirichlet_node_ids'] == []
        assert data['arrays']['dirichlet_temperature_k'] == []
        np.testing.assert_allclose(data['arrays']['temperature_k'], 290., rtol=0., atol=1e-10)
    else:
        s = data['summary']
        np.testing.assert_allclose(
            [s['prescribed_outward_heat_w_per_m'], s['convective_outward_heat_w_per_m'],
             s['thermostat_outward_heat_w_per_m']], [2., 12., -14.], rtol=0., atol=14e-10)
    assert_no_active(server._thermal_jobs)


@pytest.mark.parametrize('bad', [
    b'\xff', b'{"doc":{},"client_revision":0,"request_seq":0,"request_seq":1}',
    b'{"doc":{"name":"\\ud800"},"client_revision":0,"request_seq":0}',
    b'{"doc":{"a":NaN},"client_revision":0,"request_seq":0}',
    b'{"doc":{"a":1e999},"client_revision":0,"request_seq":0}',
    b'{"doc":{"a":{"x":1,"x":2}},"client_revision":0,"request_seq":0}',
    b'[]', b'{"doc":{},"client_revision":true,"request_seq":0}',
    b'{"doc":{},"client_revision":0,"request_seq":0,"extra":0}',
])
@pytest.mark.parametrize('route', ['/api/thermal/validate', '/api/thermal/run'])
def test_strict_bytes_refuse_before_allocation(client, monkeypatch, bad, route):
    forbid_allocation(monkeypatch)
    response = client.post(route, content=bad, headers={'content-type': 'application/json'})
    assert response.status_code == 400
    assert response.json()['ok'] is False
    assert_no_active(server._thermal_jobs)


@pytest.mark.parametrize('kind', ['optical', 'transient', 'cavity', 'mixed', 'mesh', 'boolean_mesh'])
def test_type_and_mesh_preflight_before_uuid_thread_run(client, monkeypatch, kind):
    data = model()
    if kind == 'optical': data = copy.deepcopy(examples.SLAB_TE_CHECK)
    elif kind == 'transient': data['physics']['heat1']['type'] = 'thermal.transient2d'
    elif kind == 'cavity': data['physics']['heat1']['type'] = 'em.cavity3d'
    elif kind == 'mixed': data['physics']['other'] = {'type': 'em.modes2d'}
    elif kind == 'mesh': data['mesh']['subdivisions'] = [100000, 100000]
    else: data['mesh']['subdivisions'] = [True, 2]
    forbid_allocation(monkeypatch)
    r = post(client, body=envelope(data))
    assert r.status_code == (413 if kind == 'mesh' else 400)
    assert not server._thermal_jobs._records
    assert_no_active(server._thermal_jobs)


def test_logical_schema_failure_is_not_transport_success(client, monkeypatch):
    data = model()
    data['physics']['heat1']['conductivity_w_mk'] = -2.
    forbid_allocation(monkeypatch)
    response = post(client, '/api/thermal/validate', envelope(data))
    assert response.status_code == 200 and response.json()['ok'] is False
    assert post(client, body=envelope(data)).status_code == 400
    assert_no_active(server._thermal_jobs)


class Chunks:
    def __init__(self, chunks, headers=None):
        self.chunks = chunks
        self.headers = {'content-type': 'application/json', **(headers or {})}
        self.read = 0

    async def stream(self):
        for chunk in self.chunks:
            self.read += 1
            yield chunk


@pytest.mark.parametrize('length', [None, '0', '999999999'])
def test_stream_limit_precedes_parse_and_stops_consuming(monkeypatch, length):
    headers = {} if length is None else {'content-length': length}
    request = Chunks([b'12345', b'67890', b'x', b'never read'], headers)
    limits = replace(thermal.ThermalLimits(), request_bytes=10)
    def forbidden(*a, **k):
        raise AssertionError('oversize request reached JSON parse')
    monkeypatch.setattr(thermal, 'json', SimpleNamespace(loads=forbidden))
    with pytest.raises(thermal.ThermalAPIError) as caught:
        asyncio.run(thermal.read_request(request, limits, for_run=True))
    assert caught.value.status == 413
    assert request.read == 3


def test_valid_stream_at_exact_byte_cap_and_wrong_media_type():
    encoded = json.dumps(envelope()).encode('utf-8')
    limits = replace(thermal.ThermalLimits(), request_bytes=len(encoded))
    spec = asyncio.run(thermal.read_request(Chunks([encoded[:9], encoded[9:]]), limits, for_run=True))
    assert spec.client_revision == 12
    request = Chunks([encoded], {'content-type': 'text/plain'})
    with pytest.raises(thermal.ThermalAPIError) as caught:
        asyncio.run(thermal.read_request(request, limits, for_run=True))
    assert caught.value.status == 415 and request.read == 0


def test_thread_start_failure_releases_once_and_is_retained(lifecycle_client, monkeypatch):
    client = lifecycle_client
    def failed(*args):
        raise OSError('injected thread start')
    monkeypatch.setattr(server, '_start_thermal_thread', failed)
    response = post(client)
    assert response.status_code == 500
    body = response.json()
    assert body['error']['code'] == 'thread_start_failed'
    status = client.get('/api/jobs/'+body['job']).json()
    assert status['status'] == 'error' and status['has_result'] is False
    assert client.get('/api/jobs/'+body['job']+'/result').status_code == 409
    assert_no_active(server._thermal_jobs)


def test_uuid_failure_releases_unattached_reservation(lifecycle_client, monkeypatch):
    client = lifecycle_client
    def failed():
        raise RuntimeError('injected UUID failure')
    monkeypatch.setattr(server, 'uuid', SimpleNamespace(uuid4=failed))
    assert post(client).status_code == 500
    assert not server._thermal_jobs._records
    assert_no_active(server._thermal_jobs)


@pytest.mark.parametrize('stage', ['solver', 'encode', 'publish', 'error_publish'])
def test_failure_paths_have_no_partial_result_or_active_leak(lifecycle_client, monkeypatch, stage):
    client = lifecycle_client
    def failed(*a, **k):
        raise ValueError('injected '+stage)
    if stage in ('solver', 'error_publish'):
        monkeypatch.setattr(server, 'run', failed)
    elif stage == 'encode':
        monkeypatch.setattr(thermal, 'capture_result', failed)
    else:
        monkeypatch.setattr(server._thermal_jobs, 'complete', failed)
    if stage == 'error_publish':
        monkeypatch.setattr(server._thermal_jobs, 'fail', failed)
    response = post(client)
    assert response.status_code == 200
    job = response.json()['job']
    status = client.get('/api/jobs/'+job).json()
    assert status['status'] == 'error' and not status['has_result']
    assert client.get('/api/jobs/'+job+'/result').status_code == 409
    assert_no_active(server._thermal_jobs)


def test_thread_started_then_raises_does_not_double_release_or_erase_done(lifecycle_client, monkeypatch):
    client = lifecycle_client
    def started_then_raised(target, args):
        target(*args)
        raise RuntimeError('after actual target')
    monkeypatch.setattr(server, '_start_thermal_thread', started_then_raised)
    response = post(client)
    assert response.status_code == 500
    job = response.json()['job']
    assert client.get('/api/jobs/'+job).json()['status'] == 'done'
    assert client.get('/api/jobs/'+job+'/result').status_code == 200
    assert_no_active(server._thermal_jobs)


def attach(jobs, index=1):
    lease = jobs.reserve()
    jobs.attach(lease, 'thermal-'+str(index), 'result-'+str(index), thermal.ThermalInput(None, 1, index))
    return lease


def test_repeated_terminal_errors_evict_oldest_and_release_exactly_once():
    now = [10.]
    jobs = thermal.ThermalJobs(clock=lambda: now[0])
    for i in range(1, 7):
        lease = attach(jobs, i)
        jobs.fail(lease, ValueError('\\x00'*100000))
        jobs.release(lease)
        jobs.release(lease)
        assert_no_active(jobs)
        assert len(jobs._records) <= jobs.limits.terminal_jobs
        encoded = jobs.status('thermal-'+str(i))
        assert len(encoded) <= jobs.limits.status_bytes
        status = json.loads(encoded)
        assert len(thermal.encode_json(status['error'], jobs.limits.error_bytes)) <= jobs.limits.error_bytes
        assert not status['has_result']
        assert jobs._retained_bytes() <= jobs.limits.terminal_bytes
    assert set(jobs._records) == {'thermal-5', 'thermal-6'}
    with pytest.raises(thermal.ThermalAPIError) as caught:
        jobs.status('thermal-1')
    assert caught.value.status == 404
    now[0] += jobs.limits.ttl_seconds
    with pytest.raises(thermal.ThermalAPIError) as caught:
        jobs.status('thermal-5')
    assert caught.value.status == 404 and not jobs._records
    lease = jobs.reserve()
    jobs.release(lease)
    assert_no_active(jobs)


def test_active_jobs_survive_ttl_without_eviction_and_reject_second():
    now = [0.]
    jobs = thermal.ThermalJobs(clock=lambda: now[0])
    lease = attach(jobs)
    now[0] = 10000.
    assert json.loads(jobs.status('thermal-1'))['status'] == 'running'
    with pytest.raises(thermal.ThermalAPIError) as caught:
        jobs.reserve()
    assert caught.value.status == 429
    jobs.release(lease)
    assert json.loads(jobs.status('thermal-1'))['status'] == 'error'
    assert_no_active(jobs)


def test_byte_reservation_evicts_terminal_without_eviction_of_active():
    limits = replace(thermal.ThermalLimits(), payload_bytes=1024, status_bytes=4096, terminal_bytes=5120)
    jobs = thermal.ThermalJobs(limits)
    lease = attach(jobs)
    payload = thermal.encode_json({'valid': 'small'}, 1024)
    jobs.complete(lease, payload, [])
    jobs.release(lease)
    next_lease = jobs.reserve()
    with pytest.raises(thermal.ThermalAPIError) as caught:
        jobs.result('thermal-1')
    assert caught.value.status == 404
    with pytest.raises(thermal.ThermalAPIError) as caught:
        jobs.reserve()
    assert caught.value.status == 429
    jobs.release(next_lease)
    assert_no_active(jobs)


def test_success_logs_are_bounded_including_json_escaping():
    jobs = thermal.ThermalJobs()
    lease = attach(jobs)
    jobs.complete(lease, b'{"ok":true}', ['\x00'*100000]*1000)
    jobs.release(lease)
    data = json.loads(jobs.status('thermal-1'))
    assert len(thermal.encode_json(data['log'], jobs.limits.log_bytes)) <= jobs.limits.log_bytes
    assert len(jobs.status('thermal-1')) <= jobs.limits.status_bytes
    assert jobs._retained_bytes() <= jobs.limits.terminal_bytes
    assert_no_active(jobs)


def fake_result(legacy=False):
    values = {
        'nodes_m': np.array([[0., 0.], [1., 0.], [0., 1.], [1., 1.]]),
        'triangles': np.array([[0, 1, 3], [0, 3, 2]], dtype=int),
        'temperature_k': np.array([300., 293., 300., 293.]),
        'heat_flux_w_m2': np.array([[14., 0.], [14., 0.]]),
        'load_w_per_m': np.zeros(4), 'reaction_w_per_m': np.array([-7., 0., -7., 0.]),
        'residual_w_per_m': np.array([-7., 0., -7., 0.]),
        'dirichlet_node_ids': np.array([0, 2], dtype=int),
        'dirichlet_temperature_k': np.array([300., 300.]),
        'prescribed_outward_load_w_per_m': np.array([0., 1., 0., 1.]),
        'ambient_load_w_per_m': np.array([0., 580., 0., 580.]),
        'convective_outward_w_per_m': np.array([0., 6., 0., 6.]),
        'system_rhs_w_per_m': np.array([0., 579., 0., 579.]),
    }
    if legacy:
        values['dirichlet_node_ids'] = np.arange(4, dtype=int)
        values['dirichlet_temperature_k'] = values['temperature_k'].copy()
        values['reaction_w_per_m'] = np.array([-7., 7., -7., 7.])
        values['residual_w_per_m'] = values['reaction_w_per_m'].copy()
    def id_getter(key):
        def read(self):
            self.id_reads[key] = self.id_reads.get(key, 0)+1
            assert self.id_reads[key] == 1, 'public ID read twice'
            return self.public_ids[key]
        return property(read)
    def getter(key):
        def read(self):
            self.reads[key] = self.reads.get(key, 0)+1
            assert self.reads[key] == 1, 'public property read twice'
            value = self.values[key]
            if key == 'system_rhs_w_per_m' and self.mutate_after_capture:
                self.values['nodes_m'][0, 0] = 99.
            return value
        return property(read)
    def summary(self):
        self.summary_reads += 1
        assert self.summary_reads == 1
        return copy.deepcopy(self.metadata)
    klass = type('OneReadResult', (ThermalRunResult,),
                 {**{prop: getter(key) for key, prop in thermal.PROPERTIES.items()}, 'summary': summary,
                  'result_format': id_getter('result_format'), 'field_layout': id_getter('field_layout')})
    obj = object.__new__(klass)
    obj.values, obj.reads, obj.summary_reads, obj.mutate_after_capture = values, {}, 0, False
    obj.doc = Document.from_dict(model())
    obj.log = ['synthetic public-result lifecycle fixture']
    pair = thermal.V1 if legacy else thermal.V2
    keys = thermal.BASE_FIELDS if legacy else tuple(thermal.PROPERTIES)
    obj.id_reads = {}
    obj.public_ids = dict(result_format=pair[0], field_layout=pair[1])
    obj.metadata = dict(physics_type=thermal.KIND, result_format=pair[0], field_layout=pair[1],
                        units={'length': 'm', 'temperature': 'K'}, mesh_length_unit='m',
                        field_shapes={k: list(values[k].shape) for k in keys},
                        field_units={k: thermal._units(k) for k in keys},
                        field_locations={k: thermal._location(k) for k in keys})
    return obj


IDENTITY = dict(kind=thermal.KIND, job='thermal-fixture', result_id='result-fixture',
                client_revision=1, request_seq=1)


def test_public_property_once_copy_survives_later_source_mutation():
    result = fake_result()
    result.mutate_after_capture = True
    encoded = thermal.capture_result(result, IDENTITY, thermal.ThermalLimits())
    payload = json.loads(encoded)
    assert payload['arrays']['nodes_m'][0][0] == 0.
    assert result.values['nodes_m'][0, 0] == 99.
    assert result.reads == {key: 1 for key in thermal.PROPERTIES}
    assert result.id_reads == {'result_format': 1, 'field_layout': 1}
    result.values['temperature_k'][:] = -999.
    assert json.loads(encoded)['arrays']['temperature_k'][0] == 300.
    assert payload['display_length_in_m'] == 1.


@pytest.mark.parametrize('fault', ['bool', 'object', 'list', 'float_index', 'index', 'clockwise',
                                  'shape', 'nan', 'missing', 'duplicate', 'unit', 'location',
                                  'meta_shape', 'pair', 'public_format', 'public_layout', 'metadata_nan'])
def test_payload_dtype_shape_layout_and_metadata_refusal(fault):
    obj = fake_result()
    if fault == 'bool': obj.values['temperature_k'] = np.ones(4, dtype=bool)
    elif fault == 'object': obj.values['temperature_k'] = np.ones(4, dtype=object)
    elif fault == 'list': obj.values['temperature_k'] = [300.]*4
    elif fault == 'float_index': obj.values['triangles'] = obj.values['triangles'].astype(float)
    elif fault == 'index': obj.values['triangles'][0, 0] = 4
    elif fault == 'clockwise': obj.values['triangles'][0] = obj.values['triangles'][0][::-1]
    elif fault == 'shape': obj.values['heat_flux_w_m2'] = np.ones(2)
    elif fault == 'nan': obj.values['load_w_per_m'][0] = np.nan
    elif fault == 'missing': obj.values['ambient_load_w_per_m'] = None
    elif fault == 'duplicate': obj.values['dirichlet_node_ids'] = np.array([0, 0])
    elif fault == 'unit': obj.metadata['field_units']['load_w_per_m'] = 'N/m'
    elif fault == 'location': obj.metadata['field_locations']['heat_flux_w_m2'] = 'nodes'
    elif fault == 'meta_shape': obj.metadata['field_shapes']['temperature_k'] = [True]
    elif fault == 'pair': obj.metadata['field_layout'] = thermal.V1[1]
    elif fault == 'public_format': obj.public_ids['result_format'] = thermal.V1[0]
    elif fault == 'public_layout': obj.public_ids['field_layout'] = thermal.V1[1]
    else: obj.metadata['extra'] = float('nan')
    with pytest.raises((thermal.ThermalAPIError, ValueError)):
        thermal.capture_result(obj, IDENTITY, thermal.ThermalLimits())


def test_v2_empty_d_and_negative_solved_temperature_remain_numeric():
    obj = fake_result()
    obj.values['dirichlet_node_ids'] = np.array([], dtype=int)
    obj.values['dirichlet_temperature_k'] = np.array([], dtype=float)
    obj.values['temperature_k'][:] -= 500.
    for key in ('dirichlet_node_ids', 'dirichlet_temperature_k'):
        obj.metadata['field_shapes'][key] = [0]
    data = json.loads(thermal.capture_result(obj, IDENTITY, thermal.ThermalLimits()))
    assert data['arrays']['dirichlet_node_ids'] == []
    assert max(data['arrays']['temperature_k']) < 0.


def test_summary_and_complete_payload_byte_budgets_include_overhead():
    obj = fake_result()
    with pytest.raises(thermal.ThermalAPIError) as caught:
        thermal.capture_result(obj, IDENTITY, replace(thermal.ThermalLimits(), metadata_bytes=16))
    assert caught.value.code == 'payload_limit_exceeded'
    obj = fake_result()
    with pytest.raises(thermal.ThermalAPIError) as caught:
        thermal.capture_result(obj, IDENTITY, replace(thermal.ThermalLimits(), payload_bytes=64))
    assert caught.value.code == 'payload_limit_exceeded'


def test_generic_optical_api_and_heat_guards_are_unchanged(client):
    optical = copy.deepcopy(examples.SLAB_TE_CHECK)
    checked = client.post('/api/validate', json={'doc': optical})
    assert checked.status_code == 200 and checked.json()['ok'] is True
    data = model()
    assert client.post('/api/validate', json={'doc': data}).json()['ok'] is False
    for route in ('/api/mesh', '/api/run'):
        r = client.post(route, json={'doc': data})
        assert r.status_code == 400 and 'headless' in r.json()['detail']
    with server._jobs_lock:
        server._jobs['optical-probe'] = {'status': 'done', 'log': ['optical'], 'error': None,
                                         'result': {'neff': [[2.]], 'optical': True}}
    try:
        assert client.get('/api/jobs/optical-probe/result').json() == {'neff': [[2.]], 'optical': True}
        status = client.get('/api/jobs/optical-probe').json()
        assert status == {'status': 'done', 'log': ['optical'], 'error': None, 'has_result': True}
    finally:
        with server._jobs_lock:
            server._jobs.pop('optical-probe', None)
    assert not server._thermal_jobs._records


@pytest.mark.parametrize('suffix', ['', '/result'])
def test_thermal_routes_refuse_time_query_and_expired_ids(lifecycle_client, suffix):
    client = lifecycle_client
    token = post(client).json()
    response = client.get('/api/jobs/'+token['job']+suffix+'?time=0')
    assert response.status_code == 400
    assert client.get('/api/jobs/thermal-unknown'+suffix).status_code == 404


@pytest.mark.parametrize('key', ['nodes_m', 'triangles', 'heat_flux_w_m2'])
def test_oversized_public_arrays_refuse_before_copy(key):
    class NoCopy(np.ndarray):
        def copy(self, *args, **kwargs):
            raise AssertionError('oversized producer was copied')
    obj = fake_result()
    limits = thermal.ThermalLimits()
    if key == 'nodes_m':
        limits = replace(limits, max_nodes=3)
    elif key == 'triangles':
        limits = replace(limits, max_triangles=1)
    else:
        obj.values[key] = np.zeros((3, 2))
    obj.values[key] = obj.values[key].view(NoCopy)
    with pytest.raises(thermal.ThermalAPIError) as caught:
        thermal.capture_result(obj, IDENTITY, limits)
    assert caught.value.code == 'invalid_result'


def test_six_lifecycle_runs_reuse_bounded_cache_without_reset_or_sleep(lifecycle_client):
    client = lifecycle_client
    tokens = []
    for seq in range(6):
        response = post(client, body=envelope(sequence=seq))
        assert response.status_code == 200, response.text
        token = response.json()
        tokens.append(token)
        status = client.get('/api/jobs/'+token['job']).json()
        assert status['status'] == 'done', status
        assert len(server._thermal_jobs._records) <= 2
        assert server._thermal_jobs._retained_bytes() <= server._thermal_jobs.limits.terminal_bytes
        assert_no_active(server._thermal_jobs)
    assert client.get('/api/jobs/'+tokens[0]['job']+'/result').status_code == 404
    assert client.get('/api/jobs/'+tokens[-1]['job']+'/result').status_code == 200


def test_public_pair_is_compared_to_summary_even_when_both_pairs_are_valid():
    obj = fake_result()
    obj.public_ids = dict(result_format=thermal.V1[0], field_layout=thermal.V1[1])
    with pytest.raises(thermal.ThermalAPIError, match='public and summary'):
        thermal.capture_result(obj, IDENTITY, thermal.ThermalLimits())
    assert obj.id_reads == {'result_format': 1, 'field_layout': 1}
    assert not obj.reads


def test_status_encoding_failure_removes_only_unpublished_own_record_and_releases(monkeypatch):
    jobs = thermal.ThermalJobs()
    first = attach(jobs, 1)
    jobs.complete(first, b'{"ok":true}', [])
    jobs.release(first)
    keep = jobs.result('thermal-1')
    second = attach(jobs, 2)
    def failed(*a, **k):
        raise ValueError('injected status publication failure')
    monkeypatch.setattr(jobs, '_status', failed)
    jobs.release(second)
    jobs.release(second)
    assert jobs.result('thermal-1') == keep
    with pytest.raises(thermal.ThermalAPIError) as caught:
        jobs.status('thermal-2')
    assert caught.value.status == 404
    assert_no_active(jobs)


@pytest.mark.parametrize('subdivisions', [None, [], [0, 2], [True, 2], [2.0, 2]])
def test_invalid_mesh_validation_is_logical_but_run_is_bad_request(client, monkeypatch, subdivisions):
    forbid_allocation(monkeypatch)
    doc = model()
    doc['mesh']['subdivisions'] = subdivisions
    for route, status in [('/api/thermal/validate', 200), ('/api/thermal/run', 400)]:
        response = post(client, route, envelope(doc))
        assert response.status_code == status
        body = response.json()
        assert body['ok'] is False
        assert body['error']['code'] == 'invalid_document'
        assert body['client_revision'] == 12
        assert body['request_seq'] == 7
    assert_no_active(server._thermal_jobs)
