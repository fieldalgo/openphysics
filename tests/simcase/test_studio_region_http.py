# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Studio's path for steady and transient heat region documents: protocol, limits and capture.

The criteria S1-S15 were fixed before the implementation. Every mesh count a test relies
on (nodes, triangles, loop vertices, boundary crossings) is derived in-process from the
document, never stored. The region documents come from region_studio_fixtures.
"""
import asyncio
from collections import Counter
import copy
import dataclasses
import json
import threading
import tracemalloc
from types import SimpleNamespace

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

import region_studio_fixtures as fx
from simcase import (Document, MeshLimitError, ThermalRunResult, TransientThermalRunResult, check_mesh_limits,
                     examples, region_complexity, run)
from simcase.studio import server
from simcase.studio import thermal_api as thermal
from simcase.studio import thermal_regions_api as regions
from simcase.studio import transient_thermal_api as transient

ROUTES = {thermal.KIND: '/api/thermal/', transient.KIND: '/api/thermal/transient/'}
STEADY_BLOCK = {
    'supported': True, 'run_enabled': True,
    'result_formats': ['thermal.steady2d-regions-result-v1'],
    'field_layouts': ['thermal2d-p1-node-cell-regions-v1'],
    'payload_formats': ['studio-thermal-steady-regions-v1'],
    'limits': {'max_shapes': 64, 'max_circles': 16, 'max_polygon_points': 512,
               'max_boundary_crossings': 1024, 'max_input_vertices': 2048}}
TRANSIENT_BLOCK = {
    'supported': True, 'run_enabled': True,
    'result_formats': ['thermal.transient2d-regions-result-v1'],
    'field_layouts': ['thermal2d-transient-p1-node-cell-regions-v1'],
    'payload_formats': ['studio-thermal-transient-regions-v1', 'studio-thermal-transient-frame-v1',
                        'studio-thermal-transient-history-v1'],
    'limits': STEADY_BLOCK['limits']}


def envelope(doc, revision=3, sequence=5):
    return {'doc': doc, 'client_revision': revision, 'request_seq': sequence}


def example(name):
    return copy.deepcopy(examples.EXAMPLES[name])


def kind_of(doc):
    return next(iter(doc['physics'].values()))['type']


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server, '_thermal_jobs', thermal.ThermalJobs())
    monkeypatch.setattr(server, '_region_limits', regions.RegionLimits())
    monkeypatch.setattr(server, '_start_thermal_thread', lambda target, args: target(*args))
    with TestClient(server.app) as value:
        yield value


def post(client, doc, action, route=None):
    return client.post((route or ROUTES[kind_of(doc)])+action, json=envelope(doc))


def assert_idle(jobs):
    assert jobs._active == jobs._reserved_bytes == jobs._pending == 0
    assert jobs.ingress._token is None


def finished(client, doc):
    """Run a document; its accepted identity and terminal status."""
    response = post(client, doc, 'run')
    assert response.status_code == 200, response.text
    identity = response.json()
    status = client.get('/api/jobs/'+identity['job']).json()
    assert status['status'] in ('done', 'error'), status
    return identity, status


def forbid(monkeypatch, target, name):
    def forbidden(*args, **kwargs):
        raise AssertionError(f'{name} must not be called here')
    monkeypatch.setattr(target, name, forbidden)


# ---- S1: capabilities -----------------------------------------------------------------

def test_s1_capability_blocks_nest_regions_and_keep_the_rest(client):
    caps = client.get('/api/capabilities').json()
    limits = server._thermal_jobs.limits
    steady, moving = caps[thermal.KIND], caps[transient.KIND]
    assert steady.pop('regions') == STEADY_BLOCK
    assert moving.pop('regions') == TRANSIENT_BLOCK
    assert steady == json.loads(json.dumps(thermal.capabilities(limits)[thermal.KIND]))
    assert moving == json.loads(json.dumps(transient.capabilities(limits)))
    # The region pairs stay out of the outer lists, which the rectangle client reads.
    assert not set(STEADY_BLOCK['result_formats']) & set(steady['result_formats'])
    assert not set(TRANSIENT_BLOCK['result_formats']) & set(moving['result_formats'])


# ---- S2: validation runs in a worker thread and never meshes ---------------------------

@pytest.mark.parametrize('name', ['thermal_regions', 'transient_thermal_regions'])
def test_s2_examples_validate_off_the_event_loop_without_meshing(client, monkeypatch, name):
    import simcase.thermal_regions
    import simcase.transient_regions
    for target, attribute in ((server, 'run'), (server, 'build_mesh'),
                              (simcase.thermal_regions, 'build_region_mesh'),
                              (simcase.transient_regions, 'build_region_mesh')):
        forbid(monkeypatch, target, attribute)
    seen = {'read': set(), 'from_dict': set(), 'check_mesh_limits': set(), 'region_complexity': set()}
    original_read = regions.Route.read
    async def read(self, *args, **kwargs):
        seen['read'].add(threading.get_ident())
        return await original_read(self, *args, **kwargs)
    from_dict = Document.__dict__['from_dict'].__func__
    def recording_from_dict(cls, data):
        seen['from_dict'].add(threading.get_ident())
        return from_dict(cls, data)
    def recorder(name, function):
        def call(*args, **kwargs):
            seen[name].add(threading.get_ident())
            return function(*args, **kwargs)
        return call
    monkeypatch.setattr(regions.Route, 'read', read)
    monkeypatch.setattr(Document, 'from_dict', classmethod(recording_from_dict))
    monkeypatch.setattr(regions, 'check_mesh_limits', recorder('check_mesh_limits', check_mesh_limits))
    monkeypatch.setattr(regions, 'region_complexity', recorder('region_complexity', region_complexity))
    response = post(client, example(name), 'validate')
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['ok'] is True and body['client_revision'] == 3 and body['request_seq'] == 5
    assert set(body) == ({'ok', 'doc', 'summary', 'notes', 'client_revision', 'request_seq'}
                         | ({'kind'} if name.startswith('transient') else set()))
    assert len(seen['read']) == 1
    for key in ('from_dict', 'check_mesh_limits', 'region_complexity'):
        assert seen[key] and not seen[key] & seen['read'], key
    assert_idle(server._thermal_jobs)


# ---- S3: raw geometry caps before Document.from_dict ----------------------------------

def over_cap(which, base):
    if which == 'shapes':
        shapes = fx.spaced_rects(65)['geometry']['shapes']
    elif which == 'circles':
        shapes = fx.isolated_circles(17)['geometry']['shapes']
    elif which == 'polygon_points':
        shapes = [fx.polygon('p', fx.regular_polygon(20.0, 10.0, 5.0, 513))]
    else:
        shapes = fx.covered_crossings()['geometry']['shapes']
    return fx.with_shapes(shapes, base=base)


@pytest.mark.parametrize('which,name', [('shapes', 'max_shapes'), ('circles', 'max_circles'),
                                        ('polygon_points', 'max_polygon_points'),
                                        ('crossings', 'max_boundary_crossings')])
@pytest.mark.parametrize('kind', [thermal.KIND, transient.KIND])
def test_s3_geometry_caps_refuse_before_from_dict_and_release_ingress(client, monkeypatch, which, name, kind):
    base = fx.steady_example() if kind == thermal.KIND else fx.transient_example()
    doc = over_cap(which, base)
    counts = region_complexity(doc)
    count = {'shapes': counts.shapes, 'circles': counts.circles, 'polygon_points': counts.polygon_points,
             'crossings': counts.boundary_crossings}[which]
    limit = getattr(server._region_limits, name)
    assert count > limit
    with monkeypatch.context() as patch:
        forbid(patch, server, 'run')
        def refused(cls, data):
            raise AssertionError('a geometry cap refusal reached Document.from_dict')
        patch.setattr(Document, 'from_dict', classmethod(refused))
        for action in ('validate', 'run'):
            response = post(client, doc, action)
            assert response.status_code == 413, response.text
            body = response.json()
            assert body['error']['code'] == 'geometry_limit_exceeded'
            assert body['error']['path'] == 'geometry.shapes'
            assert str(count) in body['error']['message'] and f'{name}={limit}' in body['error']['message']
            assert body['client_revision'] == 3 and body['request_seq'] == 5
            assert not server._thermal_jobs._records
            assert_idle(server._thermal_jobs)
    valid = fx.steady_example() if kind == thermal.KIND else fx.transient_example()
    response = post(client, valid, 'validate')
    assert response.status_code == 200 and response.json()['ok'] is True


def loop_vertices(doc):
    return check_mesh_limits(Document.from_dict(doc), max_input_vertices=10**6)


# (route kind, RegionLimits field, document, its count of that quantity)
AT_LIMIT = [
    (thermal.KIND, 'max_shapes', fx.circles_rects_polygon, lambda doc: region_complexity(doc).shapes),
    (thermal.KIND, 'max_circles', fx.circles_rects_polygon, lambda doc: region_complexity(doc).circles),
    (thermal.KIND, 'max_polygon_points', fx.circles_rects_polygon, lambda doc: region_complexity(doc).polygon_points),
    (thermal.KIND, 'max_boundary_crossings', lambda: fx.covered_crossings(teeth=15),
     lambda doc: region_complexity(doc).boundary_crossings),
    (thermal.KIND, 'max_input_vertices', lambda: fx.tiny_global_size(0.025), loop_vertices),
    (transient.KIND, 'max_input_vertices', fx.transient_example, loop_vertices),
]


@pytest.mark.parametrize('kind,name,make,count_of', AT_LIMIT, ids=[f'{c[0]}-{c[1]}' for c in AT_LIMIT])
def test_s3_each_cap_accepts_its_own_count_and_refuses_one_more(client, monkeypatch, kind, name, make, count_of):
    forbid(monkeypatch, server, 'run')
    doc = make()
    count = count_of(doc)
    if name in ('max_shapes', 'max_circles', 'max_polygon_points'):
        assert count == getattr(regions.RegionLimits(), name)   # the document sits at the default cap
    for limit, accepted in ((count, True), (count-1, False)):
        monkeypatch.setattr(server, '_region_limits', regions.RegionLimits(**{name: limit}))
        response = post(client, doc, 'validate')
        if accepted:
            assert response.status_code == 200 and response.json()['ok'] is True, response.text
        else:
            assert response.status_code == 413, response.text
            error = response.json()['error']
            assert error['code'] == 'geometry_limit_exceeded' and error['path'] == 'geometry.shapes'
            assert str(count) in error['message'] and f'{name}={limit}' in error['message']
        assert_idle(server._thermal_jobs)


# ---- S4 / S4b: refusals shared with rectangle documents ---------------------------------

def with_physics(doc, change):
    doc = copy.deepcopy(doc)
    change(doc)
    return doc


def second_physics(doc):
    doc['physics']['other'] = {'type': 'em.modes2d'}


def retype(type_):
    def change(doc):
        next(iter(doc['physics'].values()))['type'] = type_
    return change


S4_CASES = [
    # (route kind, region document, rectangle document with the same defect)
    (thermal.KIND, with_physics(fx.steady_example(), second_physics),
     with_physics(example('thermal_slab'), second_physics)),
    (thermal.KIND, with_physics(fx.steady_example(), retype('em.modes2d')),
     with_physics(example('thermal_slab'), retype('em.modes2d'))),
    (thermal.KIND, fx.transient_example(), example('transient_thermal_uniform')),
    (transient.KIND, with_physics(fx.transient_example(), second_physics),
     with_physics(example('transient_thermal_uniform'), second_physics)),
    (transient.KIND, fx.steady_example(), example('thermal_slab')),
    (transient.KIND, with_physics(fx.transient_example(), retype('em.cavity3d')),
     with_physics(example('transient_thermal_uniform'), retype('em.cavity3d'))),
]


@pytest.mark.parametrize('route,region_doc,rectangle_doc', S4_CASES)
def test_s4_physics_refusals_are_byte_identical_to_rectangle_ones(client, monkeypatch, route, region_doc,
                                                                  rectangle_doc):
    forbid(monkeypatch, server, 'run')
    for action in ('validate', 'run'):
        region = post(client, region_doc, action, ROUTES[route])
        rectangle = post(client, rectangle_doc, action, ROUTES[route])
        assert region.status_code == rectangle.status_code == 400
        assert region.json()['error']['code'] == 'unsupported_physics'
        assert region.content == rectangle.content
    assert_idle(server._thermal_jobs)


@pytest.mark.parametrize('kind', [thermal.KIND, transient.KIND])
def test_s4_defensive_raw_preflight_matches_the_rectangle_preflight(kind):
    limits = thermal.ThermalLimits()
    rectangle = thermal._preflight if kind == thermal.KIND else transient.preflight
    with pytest.raises(thermal.ThermalAPIError) as region_error:
        regions.raw_preflight([1], kind, limits)
    with pytest.raises(thermal.ThermalAPIError) as rectangle_error:
        rectangle([1], limits)
    assert (region_error.value.status, region_error.value.body()) == (
        rectangle_error.value.status, rectangle_error.value.body())
    assert not regions.applies([1], kind)


@pytest.mark.parametrize('times', [[2], [2, 2], [3, 2], [2, True], list(range(129))],
                         ids=['one', 'equal', 'decreasing', 'bool', '129'])
def test_s4b_time_refusals_match_rectangle_bodies(client, monkeypatch, times):
    forbid(monkeypatch, server, 'run')
    region_doc, rectangle_doc = fx.transient_example(), example('transient_thermal_uniform')
    region_doc['study']['time_s'] = rectangle_doc['study']['time_s'] = times
    for action in ('validate', 'run'):
        region = post(client, region_doc, action)
        rectangle = post(client, rectangle_doc, action)
        assert region.status_code == rectangle.status_code
        assert region.json()['error'] == rectangle.json()['error']
        assert region.content == rectangle.content
    assert_idle(server._thermal_jobs)


# ---- S5: rectangle runs keep their worker and their run call ---------------------------

@pytest.mark.parametrize('name,worker', [('thermal_slab', '_run_thermal_job'),
                                         ('transient_thermal_uniform', '_run_transient_job'),
                                         ('thermal_regions', '_run_region_job'),
                                         ('transient_thermal_regions', '_run_region_job')])
def test_s5_each_family_runs_on_its_own_worker(client, monkeypatch, name, worker):
    calls, targets = [], []
    def started(target, args):
        targets.append(target)
        target(*args)
    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return run(*args, **kwargs)
    monkeypatch.setattr(server, '_start_thermal_thread', started)
    monkeypatch.setattr(server, 'run', spy)
    identity, status = finished(client, example(name))
    assert status['status'] == 'done', status
    assert targets == [getattr(server, worker)]
    (args, kwargs), = calls
    assert len(args) == 1 and isinstance(args[0], Document)
    if worker == '_run_region_job':
        assert set(kwargs) == {'verbose', 'max_nodes', 'max_triangles', 'max_input_vertices'}
    else:
        assert kwargs == {'verbose': False}
    assert_idle(server._thermal_jobs)


# ---- S6: loop vertices after the booleans ----------------------------------------------

def test_s6_crossing_combs_are_refused_by_crossings_then_by_loop_vertices(client, monkeypatch):
    import meshine
    forbid(monkeypatch, meshine, 'generate')
    forbid(monkeypatch, meshine.Domain, 'build')
    doc = fx.crossing_combs(63)
    crossings = region_complexity(doc).boundary_crossings
    limits = server._region_limits
    assert crossings > limits.max_boundary_crossings
    response = post(client, doc, 'validate')
    assert response.status_code == 413
    error = response.json()['error']
    assert error['code'] == 'geometry_limit_exceeded' and error['path'] == 'geometry.shapes'
    assert str(crossings) in error['message'] and 'max_boundary_crossings=1024' in error['message']
    # With the crossing cap out of the way, the loop-vertex count after the booleans refuses it.
    loops = check_mesh_limits(Document.from_dict(doc), max_input_vertices=10**6)
    assert loops > limits.max_input_vertices
    monkeypatch.setattr(server, '_region_limits', regions.RegionLimits(max_boundary_crossings=10**9))
    for action in ('validate', 'run'):
        response = post(client, doc, action)
        assert response.status_code == 413, response.text
        error = response.json()['error']
        assert error['code'] == 'geometry_limit_exceeded' and error['path'] == 'geometry.shapes'
        assert str(loops) in error['message'] and '2048' in error['message']
    assert_idle(server._thermal_jobs)


def test_s6_tiny_global_size_is_refused_by_its_isolated_circle_vertices(client, monkeypatch):
    import meshine
    forbid(monkeypatch, meshine, 'generate')
    doc = fx.tiny_global_size(0.0246)
    heater = doc['geometry']['shapes'][1]
    expected = 2*int(4*np.pi*heater['r']/doc['mesh']['size'])+12   # heater and its hole, 3 rectangles
    assert check_mesh_limits(Document.from_dict(doc), max_input_vertices=10**6) == expected > 2048
    response = post(client, doc, 'validate')
    assert response.status_code == 413
    error = response.json()['error']
    assert error['code'] == 'geometry_limit_exceeded' and str(expected) in error['message']
    assert '2048' in error['message']


# ---- S7: rectangle-only keys in a region document ---------------------------------------

@pytest.mark.parametrize('kind', [thermal.KIND, transient.KIND])
def test_s7_subdivisions_in_a_region_document(client, monkeypatch, kind):
    forbid(monkeypatch, server, 'run')
    forbid(monkeypatch, regions, '_accept')
    doc = fx.steady_example() if kind == thermal.KIND else fx.transient_example()
    doc['mesh']['subdivisions'] = [4, 4]
    for action, status in (('validate', 200), ('run', 400)):
        response = post(client, doc, action)
        assert response.status_code == status
        body = response.json()
        assert body['ok'] is False and body['error'] == {
            'code': 'invalid_document', 'message': regions.SUBDIVISIONS, 'path': 'mesh.subdivisions'}
        assert body['client_revision'] == 3 and body['request_seq'] == 5
    assert_idle(server._thermal_jobs)


@pytest.mark.parametrize('mesh', [None, [], 'size', 2.0])
def test_s7_malformed_mesh_is_a_tagged_document_error(client, monkeypatch, mesh):
    forbid(monkeypatch, server, 'run')
    doc = fx.steady_example()
    doc['mesh'] = mesh
    for action, status in (('validate', 200), ('run', 400)):
        response = post(client, doc, action)
        assert response.status_code == status
        body = response.json()
        assert body['ok'] is False and body['error']['code'] == 'invalid_document'
        assert body['client_revision'] == 3 and body['request_seq'] == 5
    assert_idle(server._thermal_jobs)


def test_s7_rectangle_document_with_a_stray_empty_shapes_list_takes_the_region_path(client, monkeypatch):
    """geometry.shapes alone makes a region document (the engine's own rule), so a
    rectangle document with a stray empty list now gets the subdivisions refusal; before
    region support it got the engine's conductivity message."""
    forbid(monkeypatch, server, 'run')
    doc = example('thermal_slab')
    doc['geometry']['shapes'] = []
    response = post(client, doc, 'validate')
    assert response.status_code == 200
    assert response.content == thermal.encode_json({
        'ok': False, 'error': {'code': 'invalid_document', 'message': regions.SUBDIVISIONS,
                               'path': 'mesh.subdivisions'},
        'client_revision': 3, 'request_seq': 5}, 1 << 20)


# ---- S8: the summary floor ------------------------------------------------------------

@pytest.mark.parametrize('kind', [thermal.KIND, transient.KIND])
def test_s8_oversized_material_text_is_refused_at_validation(client, monkeypatch, kind):
    forbid(monkeypatch, server, 'run')
    doc = fx.steady_example() if kind == thermal.KIND else fx.transient_example()
    doc['materials']['steel']['source'] = 'x'*70000
    for action in ('validate', 'run'):
        response = post(client, doc, action)
        assert response.status_code == 413, response.text
        error = response.json()['error']
        assert error['code'] == 'payload_limit_exceeded' and error['path'] == 'materials'
        assert '65536' in error['message']
    assert not server._thermal_jobs._records
    assert_idle(server._thermal_jobs)


# ---- S9 / S10: job-time node, triangle and history caps --------------------------------

def mesh_counts(doc):
    result = run(Document.from_dict(doc), verbose=False)
    return len(result.mesh_nodes_m), len(result.mesh_triangles)


def assert_job_refused(client, doc, code):
    validated = post(client, doc, 'validate')
    assert validated.status_code == 200 and validated.json()['ok'] is True, validated.text
    identity, status = finished(client, doc)
    assert status['status'] == 'error' and status['has_result'] is False, status
    assert status['error']['code'] == code, status
    assert client.get('/api/jobs/'+identity['job']+'/result').status_code == 409
    assert_idle(server._thermal_jobs)
    return status['error']['message']


@pytest.mark.parametrize('cap', ['max_triangles', 'max_nodes'])
def test_s9_steady_mesh_over_the_job_cap_fails_before_the_solve(client, monkeypatch, cap):
    import galerkin.thermal
    doc = fx.steady_example(2.0)
    n, m = mesh_counts(doc)
    limit = (m if cap == 'max_triangles' else n)-1
    monkeypatch.setattr(server, '_thermal_jobs', thermal.ThermalJobs(thermal.ThermalLimits(**{cap: limit})))
    forbid(monkeypatch, galerkin.thermal, 'solve_steady_heat')
    message = assert_job_refused(client, doc, 'mesh_limit_exceeded')
    assert f'{cap}={limit}' in message
    if cap == 'max_triangles':
        assert str(m) in message


def test_s9_transient_history_cap_fails_before_the_solve(client, monkeypatch):
    import galerkin.transient_heat
    forbid(monkeypatch, galerkin.transient_heat, 'solve_transient_heat')
    message = assert_job_refused(client, fx.transient_example(0.25, times=128), 'history_limit_exceeded')
    assert 'max_nodes=1627' in message and '128 saved times' in message


def test_s9_history_label_follows_the_cap_that_was_exceeded():
    """history_limit_exceeded only when nt set the exceeded cap. At 20 times the history sets
    the node cap but not the triangle cap, which stays the plain max_triangles."""
    limits = thermal.ThermalLimits()
    for nt in range(2, transient.MAX_TIMES+1):
        plan = regions.plan(transient.KIND, limits, nt)
        n_hist = (transient.RAW_BYTES//8-3*nt)//(10*nt+8)
        assert plan.nodes_from_history == (plan.n_cap == n_hist < limits.max_nodes), nt
        assert plan.triangles_from_history == (plan.m_cap == 2*plan.n_cap < limits.max_triangles), nt
    steady = regions.plan(thermal.KIND, limits, None)
    assert not steady.nodes_from_history and not steady.triangles_from_history

    def code(plan, quantity, count):
        limit = plan.m_cap if quantity == 'triangles' else plan.n_cap
        return regions.job_error(MeshLimitError(quantity, limit, count), plan).code
    at = {nt: regions.plan(transient.KIND, limits, nt) for nt in (2, 20, 128)}
    assert at[20].nodes_from_history and not at[20].triangles_from_history
    assert at[20].m_cap == limits.max_triangles < 2*at[20].n_cap
    assert code(at[20], 'triangles', at[20].m_cap+12) == 'mesh_limit_exceeded'
    assert code(at[20], 'nodes', None) == code(at[20], 'nodes', at[20].n_cap+1) == 'history_limit_exceeded'
    assert code(at[128], 'triangles', at[128].m_cap+1) == code(at[128], 'nodes', None) == 'history_limit_exceeded'
    assert code(at[2], 'triangles', at[2].m_cap+1) == code(at[2], 'nodes', None) == 'mesh_limit_exceeded'
    assert code(steady, 'triangles', steady.m_cap+1) == code(steady, 'nodes', None) == 'mesh_limit_exceeded'


@pytest.mark.parametrize('quantity,expected', [('triangles', 'mesh_limit_exceeded'),
                                               ('nodes', 'history_limit_exceeded')])
def test_s9_transient_job_at_20_times_labels_each_cap(client, monkeypatch, quantity, expected):
    plan = regions.plan(transient.KIND, thermal.ThermalLimits(), 20)
    def refused(document, **kwargs):
        assert (kwargs['max_nodes'], kwargs['max_triangles']) == (plan.n_cap, plan.m_cap)
        limit = kwargs['max_'+quantity]
        raise MeshLimitError(quantity, limit, limit+12 if quantity == 'triangles' else None)
    monkeypatch.setattr(server, 'run', refused)
    identity, status = finished(client, fx.transient_example(times=20))
    assert status['status'] == 'error' and status['error']['code'] == expected, status
    assert ('20 saved times' in status['error']['message']) == (expected == 'history_limit_exceeded')
    assert_idle(server._thermal_jobs)


def test_s9_thin_strip_fails_at_the_meshine_cap(client, monkeypatch):
    import galerkin.thermal
    forbid(monkeypatch, galerkin.thermal, 'solve_steady_heat')
    message = assert_job_refused(client, fx.strip(width=0.005, size=0.01), 'mesh_limit_exceeded')
    assert 'max_nodes=10201' in message


@pytest.mark.parametrize('doc,expected', [
    (fx.steady_example(), (10201, 20000, 2048)),
    (fx.transient_example(), (10201, 20000, 2048)),
    (fx.transient_example(times=128), (1627, 3254, 2048)),
], ids=['steady', 'transient-9', 'transient-128'])
def test_s10_region_jobs_pass_their_caps_to_run(client, monkeypatch, doc, expected):
    seen = []
    def spy(document, **kwargs):
        seen.append(kwargs)
        raise RuntimeError('stop after the run call')
    monkeypatch.setattr(server, 'run', spy)
    identity, status = finished(client, doc)
    assert seen == [dict(zip(('max_nodes', 'max_triangles', 'max_input_vertices'), expected), verbose=False)]
    assert status['error']['code'] == 'solver_failed'
    nt = len(doc['study']['time_s']) if 'study' in doc and 'time_s' in doc['study'] else None
    if nt == 128:
        n_hist = (transient.RAW_BYTES//8-3*nt)//(10*nt+8)
        assert expected[:2] == (n_hist, 2*n_hist)
        bound = 6*nt*n_hist+(2*nt+4)*2*n_hist+3*nt
        assert 8*bound <= transient.RAW_BYTES


# ---- S11: the region rule mirrors the engine's -----------------------------------------

def s11_fixtures(kind):
    region = fx.steady_example() if kind == thermal.KIND else fx.transient_example()
    rectangle = example('thermal_slab' if kind == thermal.KIND else 'transient_thermal_uniform')
    shapes_only = copy.deepcopy(region)
    del shapes_only['geometry']['background']
    background_only = copy.deepcopy(region)
    del background_only['geometry']['shapes']
    geometry_list = copy.deepcopy(region)
    geometry_list['geometry'] = [region['geometry']]
    no_geometry = copy.deepcopy(region)
    del no_geometry['geometry']
    physics_not_dict = copy.deepcopy(region)
    physics_not_dict['physics'] = ['heat1']
    two_physics = copy.deepcopy(region)
    two_physics['physics']['second'] = copy.deepcopy(next(iter(region['physics'].values())))
    return {'rectangle': rectangle, 'region': region, 'shapes_only': shapes_only,
            'background_only': background_only, 'geometry_list': geometry_list, 'no_geometry': no_geometry,
            'physics_not_dict': physics_not_dict, 'two_physics': two_physics}


@pytest.mark.parametrize('kind', [thermal.KIND, transient.KIND])
def test_s11_applies_agrees_with_the_engine_rule(kind):
    from simcase.thermal_regions import has_region_geometry
    decided = {name: regions.applies(doc, kind) for name, doc in s11_fixtures(kind).items()}
    assert decided == {name: has_region_geometry(doc, kind) for name, doc in s11_fixtures(kind).items()}
    assert decided == {'rectangle': False, 'region': True, 'shapes_only': True, 'background_only': True,
                       'geometry_list': False, 'no_geometry': False, 'physics_not_dict': False,
                       'two_physics': True}


# ---- S12: capture fault matrices ------------------------------------------------------

@pytest.fixture(scope='module')
def real():
    steady = run(Document.from_dict(fx.steady_example()), verbose=False)
    moving = run(Document.from_dict(fx.transient_example()), verbose=False)
    return {thermal.KIND: steady, transient.KIND: moving,
            'steady_rectangle': run(Document.from_dict(example('thermal_boundary')), verbose=False),
            'transient_rectangle': run(Document.from_dict(example('transient_thermal_uniform')), verbose=False)}


ARRAY_KEYS = {thermal.KIND: tuple(thermal.PROPERTIES.values())+('triangle_regions',),
              transient.KIND: tuple(transient.SPEC)+('region_ids',)}


def probe(result, kind, edit=None):
    """A public result subclass that serves the real result's values, possibly edited, and
    records every public read."""
    if kind == thermal.KIND:
        values = {prop: np.array(getattr(result, prop), copy=True) for prop in thermal.PROPERTIES.values()}
        values['triangle_regions'] = np.array(result.triangle_regions, copy=True)
        base = ThermalRunResult
    else:
        values = {key: np.array(getattr(result, key), copy=True) for key in transient.SPEC}
        values['region_ids'] = np.array(result.region_ids, copy=True)
        base = TransientThermalRunResult
    state = {'values': values, 'names': list(result.region_names), 'summary': copy.deepcopy(result.summary()),
             'pair': [result.result_format, result.field_layout], 'doc': result.doc}
    if edit is not None:
        edit(state)
    reads = []
    def served(key, get):
        def read(self):
            reads.append(key)
            return get()
        return property(read)
    attributes = {key: served(key, lambda key=key: state['values'][key]) for key in values}
    attributes.update(region_names=served('region_names', lambda: state['names']),
                      result_format=served('result_format', lambda: state['pair'][0]),
                      field_layout=served('field_layout', lambda: state['pair'][1]),
                      doc=served('doc', lambda: state['doc']), log=['probe'])
    def summary(self):
        reads.append('summary')
        return copy.deepcopy(state['summary'])
    attributes['summary'] = summary
    obj = object.__new__(type('RegionProbe', (base,), attributes))
    object.__setattr__(obj, 'reads', reads)
    object.__setattr__(obj, 'accepted', result.doc)   # the job's document, read without counting
    return obj


def region_spec(result, kind, n_cap=None):
    doc = result.accepted
    nt = len(doc['study']['time_s']) if kind == transient.KIND else None
    plan = regions.plan(kind, thermal.ThermalLimits(), nt)
    if n_cap is not None:
        plan = dataclasses.replace(plan, n_cap=n_cap)
    return regions.RegionInput(doc, doc, plan, kind, 0, 3, 5)


IDENTITY = {thermal.KIND: dict(kind=thermal.KIND, job='thermal-probe', result_id='result-probe',
                               client_revision=3, request_seq=5),
            transient.KIND: dict(kind=transient.KIND, job='thermal-transient-probe', result_id='result-probe',
                                 client_revision=3, request_seq=5)}


def capture(result, kind, rlimits=None, n_cap=None):
    rlimits = rlimits or regions.RegionLimits()
    spec = region_spec(result, kind, n_cap)
    limits = thermal.ThermalLimits()
    if kind == thermal.KIND:
        return regions.capture_steady(result, IDENTITY[kind], limits, rlimits, spec)
    return regions.capture_transient(result, IDENTITY[kind], limits, rlimits, spec)


def ids_key(kind):
    return 'triangle_regions' if kind == thermal.KIND else 'region_ids'


def first_region(state):
    return state['summary']['regions'][state['names'][0]]


def drop_last_triangle(kind):
    """A consistent result without its last triangle: only the domain area is short."""
    def edit(state):
        values, summary = state['values'], state['summary']
        tri_key = 'mesh_triangles' if kind == thermal.KIND else 'triangles'
        flux_axis = 0 if kind == thermal.KIND else 1
        values[tri_key] = values[tri_key][:-1]
        values['heat_flux_w_m2'] = np.delete(values['heat_flux_w_m2'], -1, axis=flux_axis)
        values[ids_key(kind)] = values[ids_key(kind)][:-1]
        m = len(values[tri_key])
        nodes = values['mesh_nodes_m' if kind == thermal.KIND else 'nodes_m']
        areas = regions._cell_areas(nodes, values[tri_key], kind)
        ids = values[ids_key(kind)]
        for i, name in enumerate(state['names']):
            summary['regions'][name].update(triangles=int(np.sum(ids == i)), area_m2=float(areas[ids == i].sum()))
        summary['mesh']['triangles'] = m
        for key in ('triangles', 'heat_flux_w_m2', 'triangle_regions'):
            summary['field_shapes'][key][0 if key != 'heat_flux_w_m2' or kind == thermal.KIND else 1] = m
    return edit


REGION_FAULTS = {
    'names_duplicate': (lambda s: (s['names'].__setitem__(1, s['names'][0]),
                                   s['summary'].__setitem__('region_names', list(s['names']))),
                        'region names must be unique'),
    'names_empty': (lambda s: (s['summary']['regions'].__setitem__('', s['summary']['regions'].pop(s['names'][0])),
                               s['names'].__setitem__(0, ''),
                               s['summary'].__setitem__('region_names', list(s['names']))),
                    'region names must be unique'),
    'names_not_a_list': (lambda s: s.__setitem__('names', 'background'), 'region names must be unique'),
    'names_not_summary': (lambda s: s['summary'].__setitem__('region_names', s['names'][::-1]),
                          'summary region names disagree'),
    'ids_out_of_range': (lambda s: s['ids'].__setitem__(0, len(s['names'])), 'triangle region ids outside'),
    'ids_negative': (lambda s: s['ids'].__setitem__(0, -1), 'triangle region ids outside'),
    'regions_missing': (lambda s: s['summary']['regions'].pop(s['names'][-1]), 'summary regions disagree'),
    'entry_extra_key': (lambda s: first_region(s).__setitem__('extra', 1), 'region entry keys'),
    'triangle_count': (lambda s: first_region(s).__setitem__('triangles', first_region(s)['triangles']+1),
                       'region triangle count disagrees'),
    'triangle_count_float': (lambda s: first_region(s).__setitem__('triangles', float(first_region(s)['triangles'])),
                             'region triangle count disagrees'),
    'area_one_ulp': (lambda s: first_region(s).__setitem__('area_m2', float(np.nextafter(first_region(s)['area_m2'],
                                                                                        np.inf))),
                     'region area disagrees'),
    'area_negative': (lambda s: first_region(s).__setitem__('area_m2', -first_region(s)['area_m2']),
                      'region area disagrees'),
    'material': (lambda s: first_region(s).__setitem__('material', 'unobtainium'), 'region material disagrees'),
    'summary_materials': (lambda s: s['summary']['materials']['steel'].__setitem__('source', 'changed'),
                          'summary materials disagree'),
    'summary_heat_source': (lambda s: s['summary'].__setitem__('heat_source_w_m3', 1.0),
                            'summary heat sources disagree'),
}


def region_fault(kind, name):
    if name == 'domain_area':
        return drop_last_triangle(kind), 'region areas do not add up to the domain'
    change, message = REGION_FAULTS[name]
    def edit(state):
        state['ids'] = state['values'][ids_key(kind)]
        change(state)
    return edit, message


@pytest.mark.parametrize('name', [*REGION_FAULTS, 'domain_area'])
@pytest.mark.parametrize('kind', [thermal.KIND, transient.KIND])
def test_s12_each_region_check_refuses_without_publishing(client, monkeypatch, real, kind, name):
    edit, message = region_fault(kind, name)
    with pytest.raises(thermal.ThermalAPIError, match=message) as caught:
        capture(probe(real[kind], kind, edit), kind)
    assert caught.value.code == 'invalid_result'
    faulty = probe(real[kind], kind, edit)
    monkeypatch.setattr(server, 'run', lambda *a, **k: faulty)
    doc = fx.steady_example() if kind == thermal.KIND else fx.transient_example()
    identity, status = finished(client, doc)
    assert status['status'] == 'error' and status['error']['code'] == 'invalid_result', status
    assert status['has_result'] is False
    assert client.get('/api/jobs/'+identity['job']+'/result').status_code == 409
    assert_idle(server._thermal_jobs)


def test_s12_too_many_region_names_for_the_limits(real):
    with pytest.raises(thermal.ThermalAPIError, match='region names must be unique'):
        capture(probe(real[thermal.KIND], thermal.KIND), thermal.KIND, rlimits=regions.RegionLimits(max_shapes=1))


@pytest.mark.parametrize('kind', [thermal.KIND, transient.KIND])
def test_s12_pair_first_and_every_public_property_read_once(real, kind):
    result = probe(real[kind], kind)
    capture(result, kind)
    counts = Counter(result.reads)
    expected = {*ARRAY_KEYS[kind], 'region_names', 'result_format', 'field_layout', 'doc', 'summary'}
    assert set(counts) == expected and set(counts.values()) == {1}
    first_array = min(result.reads.index(key) for key in ARRAY_KEYS[kind])
    assert max(result.reads.index('result_format'), result.reads.index('field_layout')) < first_array
    wrong = probe(real[kind], kind, lambda s: s['pair'].__setitem__(1, 'thermal2d-p1-node-cell-boundary-v2'))
    with pytest.raises(thermal.ThermalAPIError) as caught:
        capture(wrong, kind)
    assert caught.value.code == 'invalid_result'
    assert not set(wrong.reads) & set(ARRAY_KEYS[kind])


@pytest.mark.parametrize('fault', ['float', 'bool', 'length', 'huge_view'])
@pytest.mark.parametrize('kind', [thermal.KIND, transient.KIND])
def test_s12_region_ids_are_checked_before_they_are_copied(real, kind, fault):
    key = ids_key(kind)
    def edit(state):
        ids = state['values'][key]
        state['values'][key] = {'float': ids.astype(float), 'bool': ids.astype(bool), 'length': ids[:-1],
                                'huge_view': np.broadcast_to(np.int64(0), (10**8,))}[fault]
    result = probe(real[kind], kind, edit)
    tracemalloc.start()
    try:
        with pytest.raises(thermal.ThermalAPIError) as caught:
            capture(result, kind)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert caught.value.code == 'invalid_result'
    assert peak < 64*1024**2   # the 800 MB view was never copied


@pytest.mark.parametrize('kind', [thermal.KIND, transient.KIND])
def test_s12_more_nodes_than_the_plan_allows_is_invalid(real, kind):
    n = len(real[kind].mesh_nodes_m)
    with pytest.raises(thermal.ThermalAPIError, match='oversized') as caught:
        capture(probe(real[kind], kind), kind, n_cap=n-1)
    assert caught.value.code == 'invalid_result'
    capture(probe(real[kind], kind), kind, n_cap=n)


@pytest.mark.parametrize('posted,served', [
    ('thermal_slab', thermal.KIND), ('transient_thermal_uniform', transient.KIND),
    ('thermal_regions', 'steady_rectangle'), ('transient_thermal_regions', 'transient_rectangle')])
def test_s12_a_result_of_the_other_family_is_invalid(client, monkeypatch, real, posted, served):
    monkeypatch.setattr(server, 'run', lambda *a, **k: real[served])
    identity, status = finished(client, example(posted))
    assert status['status'] == 'error' and status['error']['code'] == 'invalid_result', status
    assert client.get('/api/jobs/'+identity['job']+'/result').status_code == 409
    assert_idle(server._thermal_jobs)


# ---- S13: transient views of a region job ---------------------------------------------

def test_s13_region_frames_and_histories_carry_the_region_pair(client):
    identity, status = finished(client, fx.transient_example())
    assert status['status'] == 'done', status
    record = server._thermal_jobs._records[identity['job']]
    raw = record['raw']
    assert 'triangle_regions' in raw and raw['triangle_regions'].dtype == np.int64
    assert record['raw_bytes'] == sum(a.nbytes for a in raw.values())
    assert record['pair'] == regions.TRANSIENT_PAIR
    manifest = client.get('/api/jobs/'+identity['job']+'/result').json()
    assert manifest['payload_format'] == regions.TRANSIENT_MANIFEST
    assert (manifest['result_format'], manifest['field_layout']) == regions.TRANSIENT_PAIR
    assert len(manifest['fields']) == 14 and set(manifest['arrays']) == {
        'nodes_m', 'triangles', 'dirichlet_node_ids', 'triangle_regions'}
    assert manifest['fields']['triangle_regions'] == {
        'shape': [len(manifest['arrays']['triangles'])], 'unit': '1', 'location': 'triangles', 'axis': 'static',
        'available_views': [], 'initial_available': True, 'ui_supported': False}
    base = '/api/jobs/'+identity['job']
    frame = client.get(base+'/frame', params={'result_id': identity['result_id'], 'field': 'temperature_k',
                                              'time_index': 2, 'frame_seq': 1})
    history = client.get(base+'/history', params={'result_id': identity['result_id'],
                                                  'field': 'heat_content_j_per_m', 'start': 0, 'stop': 4,
                                                  'frame_seq': 2})
    for view, payload_format in ((frame, transient.FRAME), (history, transient.HISTORY)):
        assert view.status_code == 200, view.text
        data = view.json()
        assert data['payload_format'] == payload_format
        assert (data['result_format'], data['field_layout']) == regions.TRANSIENT_PAIR
    refused = client.get(base+'/frame', params={'result_id': identity['result_id'], 'field': 'triangle_regions',
                                                'time_index': 2, 'frame_seq': 3})
    assert refused.status_code == 400 and refused.json()['error']['code'] == 'invalid_query'
    rectangle, status = finished(client, example('transient_thermal_uniform'))
    assert 'pair' not in server._thermal_jobs._records[rectangle['job']]
    frame = client.get('/api/jobs/'+rectangle['job']+'/frame', params={
        'result_id': rectangle['result_id'], 'field': 'temperature_k', 'time_index': 1, 'frame_seq': 1}).json()
    assert (frame['result_format'], frame['field_layout']) == transient.PAIR


# ---- S14: cancellation keeps the ingress permit until the thread returns ---------------

def test_s14_cancelled_region_validation_holds_ingress_until_its_thread_returns(monkeypatch):
    jobs = thermal.ThermalJobs()
    monkeypatch.setattr(server, '_thermal_jobs', jobs)
    entered, release, returned = threading.Event(), threading.Event(), threading.Event()
    original = regions._accept
    def blocked(*args):
        entered.set()
        try:
            assert release.wait(30), 'the test never released the validation thread'
            return original(*args)
        finally:
            returned.set()
    monkeypatch.setattr(regions, '_accept', blocked)

    async def exercise():
        transport = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(transport=transport, base_url='http://studio') as studio:
            task = asyncio.create_task(studio.post('/api/thermal/validate', json=envelope(fx.steady_example())))
            try:
                assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 30), 35)
                task.cancel()
                await asyncio.sleep(.2)
                assert not task.done() and not returned.is_set()
                assert jobs.ingress._token is not None
                probe_ = await studio.post('/api/thermal/transient/validate',
                                           json=envelope(example('transient_thermal_uniform')))
                assert probe_.status_code == 429
                assert probe_.json()['error']['code'] == 'ingress_capacity_exceeded'
            finally:
                release.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 30)
            assert returned.is_set() and jobs.ingress._token is None
            after = await studio.post('/api/thermal/validate', json=envelope(fx.steady_example()))
            assert after.status_code == 200 and after.json()['ok'] is True
    asyncio.run(exercise())


@pytest.mark.parametrize('thread_result', ['returns', 'raises'])
def test_s14b_scope_cancellation_neither_spins_nor_continues_after_the_thread(monkeypatch, thread_result):
    """Under an anyio cancel scope (middleware task groups, fail_after), anyio cancels a
    waiting task again on every loop iteration; the shielded wait sees none of that, the
    thread runs to the end, and the cancellation ends the request after it. A refusal the
    thread raised meanwhile is retrieved, so asyncio reports no unretrieved task exception."""
    import anyio
    import gc
    waits, unhandled = [], []
    original_wait = asyncio.wait
    async def counted(*args, **kwargs):
        waits.append(1)
        return await original_wait(*args, **kwargs)
    monkeypatch.setattr(asyncio, 'wait', counted)
    release, returned = threading.Event(), threading.Event()
    def validation():
        try:
            assert release.wait(30), 'the test never released the validation thread'
            if thread_result == 'raises':
                raise thermal.ThermalAPIError('invalid_document', 'refused after the request was cancelled')
            return 'accepted'
        finally:
            returned.set()

    async def exercise():
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(lambda _loop, context: unhandled.append(context))
        outcome = []
        with anyio.CancelScope() as scope:
            loop.call_later(.05, scope.cancel)
            loop.call_later(.3, release.set)
            try:
                outcome.append(await regions._wait_for_thread(validation))
            finally:
                outcome.append(returned.is_set())
        return scope, outcome
    try:
        scope, outcome = asyncio.run(exercise())
    finally:
        release.set()
    gc.collect()                    # asyncio reports an unretrieved exception when the task is freed
    assert scope.cancel_called and scope.cancelled_caught
    assert outcome == [True]        # no result: the request ended, after the thread returned
    assert len(waits) == 1          # a busy loop re-entered the wait thousands of times
    assert unhandled == []


# ---- S15: a source on a covered shape fails after meshing -------------------------------

def test_s15_heat_source_on_a_fully_covered_shape_is_a_job_document_error(client, monkeypatch):
    import galerkin.thermal
    forbid(monkeypatch, galerkin.thermal, 'solve_steady_heat')
    doc = fx.steady_example()
    doc['geometry']['shapes'] += [fx.rect('hidden', 10.0, 6.0, 2.0, 2.0), fx.rect('cover', 9.0, 5.5, 4.0, 3.0)]
    doc['physics']['heat1']['heat_source_w_m3'] = {'heater': 5e6, 'hidden': 1e5}
    message = assert_job_refused(client, doc, 'invalid_document')
    assert 'hidden' in message and 'not in the meshed geometry' in message
