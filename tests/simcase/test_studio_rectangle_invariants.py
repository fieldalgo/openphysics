# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Rectangle thermal Studio behaviour, pinned before Studio accepts region documents.

Region support must not change a byte, a code path or an error of rectangle documents.
Every expectation below is a literal, recorded on the commit before the region route existed
and recorded again when rectangle documents moved to format 0.3 (the units and naming batch:
renamed keys, arrays and identifiers, coded diagnostics; no other change): the exact bytes of rectangle validation responses (R1), the capability
blocks without their nested ``regions`` key (R2), the exact error bodies of the
rectangle refusal matrix (R3), the exact run identity and running status (R4), and the
key order, JSON value types and array shapes of completed results, manifests, frames
and history pages (R5). No solver float is compared: R1-R4 responses contain none and
R5 records only types and shapes.
"""
import copy
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from simcase import examples
from simcase.studio import server
from simcase.studio import thermal_api as thermal
from simcase.studio import transient_thermal_api as transient

ROUTES = {'steady': '/api/thermal/', 'transient': '/api/thermal/transient/'}
TOKEN = '0123456789abcdef0123456789abcdef'


def compact(value):
    """The bytes Studio sends for a JSON value (thermal_api.encode_json)."""
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')


def envelope(doc, revision=1, sequence=1):
    return {'doc': doc, 'client_revision': revision, 'request_seq': sequence}


def example(name):
    return copy.deepcopy(examples.EXAMPLES[name])


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server, '_thermal_jobs', thermal.ThermalJobs())
    monkeypatch.setattr(server, '_start_thermal_thread', lambda target, args: target(*args))
    with TestClient(server.app) as value:
        yield value


def assert_idle(jobs):
    assert jobs._active == jobs._reserved_bytes == jobs._pending == 0
    assert jobs.ingress._token is None


# ---- R1: validation bytes -------------------------------------------------------------

VALIDATE = {
    'thermal_slab': {'ok': True,
     'doc': {'openphysics': '0.3',
             'name': 'Steady heat slab',
             'geometry': {'length_unit': 'mm',
                          'depth': None,
                          'domain': {'xmin': 0.0, 'xmax': 30.0, 'ymin': 0.0, 'ymax': 20.0}},
             'materials': {},
             'physics': {'heat1': {'type': 'thermal.steady2d',
                                   'thermal_conductivity': '12.5 W/(m K)',
                                   'heat_source_density': '0 W/m^3',
                                   'prescribed_temperature': {'left': '280 K', 'right': '315 K'}}},
             'mesh': {'subdivision_count': [32, 16]},
             'study': {'type': 'single'},
             'results': {'save_fields': True, 'plots': False}},
     'diagnostics': [{'code': 'I-DEFAULT-BOUNDARY',
                      'severity': 'info',
                      'path': 'physics.heat1.inward_heat_flux.bottom',
                      'message': "side 'bottom' has no condition: it is insulated (inward_heat_flux 0 W/m^2)",
                      'fix': None,
                      'suggestions': [],
                      'acknowledged': None},
                     {'code': 'I-DEFAULT-BOUNDARY',
                      'severity': 'info',
                      'path': 'physics.heat1.inward_heat_flux.top',
                      'message': "side 'top' has no condition: it is insulated (inward_heat_flux 0 W/m^2)",
                      'fix': None,
                      'suggestions': [],
                      'acknowledged': None}],
     'summary': 'Steady heat slab (openphysics 0.3)\n'
                '  physics heat1: thermal.steady2d, single steady heat\n'
                '  domain xmin 0.0, xmax 30.0, ymin 0.0, ymax 20.0 (mm); subdivision_count [32, 16]\n'
                '  thermal_conductivity 12.5 W/(m K), heat_source_density 0 W/m^3\n'
                "  prescribed_temperature {'left': '280 K', 'right': '315 K'}; remaining exterior insulated\n"
                '  result: thermal.steady2d-result-v3; layout: thermal2d-p1-node-cell-v2\n'
                '  output: SI (node_coordinates m, temperature K, heat_flux W/m^2, nodal heat rates W/m of '
                'depth)',
     'client_revision': 1,
     'request_seq': 1},
    'thermal_boundary': {'ok': True,
     'doc': {'openphysics': '0.3',
             'name': 'Steady additive outward flux and convection',
             'geometry': {'length_unit': 'm',
                          'depth': None,
                          'domain': {'xmin': 0, 'xmax': 1, 'ymin': 0, 'ymax': 1}},
             'materials': {},
             'physics': {'heat1': {'type': 'thermal.steady2d',
                                   'thermal_conductivity': '2 W/(m K)',
                                   'heat_source_density': '0 W/m^3',
                                   'prescribed_temperature': {'left': '300 K'},
                                   'inward_heat_flux': {'right': '-2 W/m^2'},
                                   'convection': {'right': {'heat_transfer_coefficient': '4 W/(m^2 K)',
                                                            'ambient_temperature': '290 K'}}}},
             'mesh': {'subdivision_count': [8, 8]},
             'study': {'type': 'single'},
             'results': {'save_fields': True, 'plots': False}},
     'diagnostics': [{'code': 'I-DEFAULT-BOUNDARY',
                      'severity': 'info',
                      'path': 'physics.heat1.inward_heat_flux.bottom',
                      'message': "side 'bottom' has no condition: it is insulated (inward_heat_flux 0 W/m^2)",
                      'fix': None,
                      'suggestions': [],
                      'acknowledged': None},
                     {'code': 'I-DEFAULT-BOUNDARY',
                      'severity': 'info',
                      'path': 'physics.heat1.inward_heat_flux.top',
                      'message': "side 'top' has no condition: it is insulated (inward_heat_flux 0 W/m^2)",
                      'fix': None,
                      'suggestions': [],
                      'acknowledged': None}],
     'summary': 'Steady additive outward flux and convection (openphysics 0.3)\n'
                '  physics heat1: thermal.steady2d, single steady heat\n'
                '  domain xmin 0, xmax 1, ymin 0, ymax 1 (m); subdivision_count [8, 8]\n'
                '  thermal_conductivity 2 W/(m K), heat_source_density 0 W/m^3\n'
                "  prescribed_temperature {'left': '300 K'}; inward_heat_flux {'right': '-2 W/m^2'}; "
                "convection {'right': {'heat_transfer_coefficient': '4 W/(m^2 K)', 'ambient_temperature': '290 "
                "K'}}\n"
                '  q.n = -inward_heat_flux + h (T - ambient_temperature); unselected natural sides insulated\n'
                '  result: thermal.steady2d-result-v4; layout: thermal2d-p1-node-cell-boundary-v3\n'
                '  output: SI (node_coordinates m, temperature K, heat_flux W/m^2, nodal heat rates W/m of '
                'depth)',
     'client_revision': 1,
     'request_seq': 1},
    'thermal_mixed': {'ok': True,
     'doc': {'openphysics': '0.3',
             'name': 'Steady heat with uniform source',
             'geometry': {'length_unit': 'mm',
                          'depth': None,
                          'domain': {'xmin': 0.0, 'xmax': 30.0, 'ymin': 0.0, 'ymax': 20.0}},
             'materials': {},
             'physics': {'heat1': {'type': 'thermal.steady2d',
                                   'thermal_conductivity': '12.5 W/(m K)',
                                   'heat_source_density': '100000 W/m^3',
                                   'prescribed_temperature': {'left': '280 K', 'right': '315 K'}}},
             'mesh': {'subdivision_count': [32, 16]},
             'study': {'type': 'single'},
             'results': {'save_fields': True, 'plots': False}},
     'diagnostics': [{'code': 'I-DEFAULT-BOUNDARY',
                      'severity': 'info',
                      'path': 'physics.heat1.inward_heat_flux.bottom',
                      'message': "side 'bottom' has no condition: it is insulated (inward_heat_flux 0 W/m^2)",
                      'fix': None,
                      'suggestions': [],
                      'acknowledged': None},
                     {'code': 'I-DEFAULT-BOUNDARY',
                      'severity': 'info',
                      'path': 'physics.heat1.inward_heat_flux.top',
                      'message': "side 'top' has no condition: it is insulated (inward_heat_flux 0 W/m^2)",
                      'fix': None,
                      'suggestions': [],
                      'acknowledged': None}],
     'summary': 'Steady heat with uniform source (openphysics 0.3)\n'
                '  physics heat1: thermal.steady2d, single steady heat\n'
                '  domain xmin 0.0, xmax 30.0, ymin 0.0, ymax 20.0 (mm); subdivision_count [32, 16]\n'
                '  thermal_conductivity 12.5 W/(m K), heat_source_density 100000 W/m^3\n'
                "  prescribed_temperature {'left': '280 K', 'right': '315 K'}; remaining exterior insulated\n"
                '  result: thermal.steady2d-result-v3; layout: thermal2d-p1-node-cell-v2\n'
                '  output: SI (node_coordinates m, temperature K, heat_flux W/m^2, nodal heat rates W/m of '
                'depth)',
     'client_revision': 1,
     'request_seq': 1},
    'transient_thermal_uniform': {'ok': True,
     'kind': 'thermal.transient2d',
     'client_revision': 1,
     'request_seq': 1,
     'doc': {'openphysics': '0.3',
             'name': 'Insulated constant-source transient heat',
             'geometry': {'length_unit': 'm',
                          'depth': None,
                          'domain': {'xmin': 0, 'xmax': 1, 'ymin': 0, 'ymax': 1}},
             'materials': {},
             'physics': {'heat1': {'type': 'thermal.transient2d',
                                   'thermal_conductivity': '2.5 W/(m K)',
                                   'volumetric_heat_capacity': {'value': '4 J/(m^3 K)',
                                                                'accept': {'W-MAGNITUDE': 'manufactured '
                                                                                          'solution'}},
                                   'initial_temperature': '300 K',
                                   'prescribed_temperature': {},
                                   'heat_source_density': '8 W/m^3'}},
             'mesh': {'subdivision_count': [4, 4]},
             'study': {'type': 'transient', 'time': {'unit': 's', 'values': [0.0, 0.1, 0.3]}},
             'results': {'save_fields': True, 'plots': False}},
     'diagnostics': [{'code': 'W-MAGNITUDE',
                      'severity': 'warning',
                      'path': 'physics.heat1.volumetric_heat_capacity.value',
                      'message': '"4 J/(m^3 K)" is 4 J/(m^3 K), outside the usual range of '
                                 'volumetric_heat_capacity (|value| 1e3 J/(m^3 K) to 1e7 J/(m^3 K)). If the '
                                 'value is right, acknowledge it on the value with a reason: {"value": ..., '
                                 '"accept": {"W-MAGNITUDE": "<reason>"}}.',
                      'fix': None,
                      'suggestions': [{'value': '4 J/(cm^3 K)',
                                       'si_before': 4.0,
                                       'si_after': 4000000.0,
                                       'unit': 'J/(m^3 K)'}],
                      'acknowledged': 'manufactured solution'},
                     {'code': 'I-DEFAULT-BOUNDARY',
                      'severity': 'info',
                      'path': 'physics.heat1.inward_heat_flux.left',
                      'message': "side 'left' has no condition: it is insulated (inward_heat_flux 0 W/m^2)",
                      'fix': None,
                      'suggestions': [],
                      'acknowledged': None},
                     {'code': 'I-DEFAULT-BOUNDARY',
                      'severity': 'info',
                      'path': 'physics.heat1.inward_heat_flux.right',
                      'message': "side 'right' has no condition: it is insulated (inward_heat_flux 0 W/m^2)",
                      'fix': None,
                      'suggestions': [],
                      'acknowledged': None},
                     {'code': 'I-DEFAULT-BOUNDARY',
                      'severity': 'info',
                      'path': 'physics.heat1.inward_heat_flux.bottom',
                      'message': "side 'bottom' has no condition: it is insulated (inward_heat_flux 0 W/m^2)",
                      'fix': None,
                      'suggestions': [],
                      'acknowledged': None},
                     {'code': 'I-DEFAULT-BOUNDARY',
                      'severity': 'info',
                      'path': 'physics.heat1.inward_heat_flux.top',
                      'message': "side 'top' has no condition: it is insulated (inward_heat_flux 0 W/m^2)",
                      'fix': None,
                      'suggestions': [],
                      'acknowledged': None}],
     'summary': 'Insulated constant-source transient heat (openphysics 0.3)\n'
                '  physics heat1: thermal.transient2d, 3 explicit times\n'
                '  domain xmin 0, xmax 1, ymin 0, ymax 1 (m); subdivision_count [4, 4]\n'
                '  thermal_conductivity 2.5 W/(m K), heat_source_density 8 W/m^3\n'
                '  prescribed_temperature {}; remaining exterior insulated\n'
                '  volumetric_heat_capacity 4 J/(m^3 K); initial_temperature 300 K; study.time [0.0, 0.1, 0.3] '
                's\n'
                '  rates at interval ends only\n'
                '  result: thermal.transient2d-result-v3; layout: thermal2d-transient-p1-node-cell-v2\n'
                '  output: SI (node_coordinates m, temperature K, heat_flux W/m^2, nodal heat rates W/m of '
                'depth)'},
}


@pytest.mark.parametrize('name', ['thermal_slab', 'thermal_boundary', 'thermal_mixed',
                                  'transient_thermal_uniform'])
def test_r1_rectangle_validation_bytes(client, name):
    route = ROUTES['transient' if name.startswith('transient') else 'steady']+'validate'
    response = client.post(route, json=envelope(example(name)))
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.content == compact(VALIDATE[name])
    assert_idle(server._thermal_jobs)


# ---- R2: capabilities -----------------------------------------------------------------

CAPABILITIES = {
    'capability_format': 'studio-capabilities-v1',
    'thermal.steady2d': {'supported': True,
     'run_enabled': True,
     'validate': '/api/thermal/validate',
     'run': '/api/thermal/run',
     'input': 'json',
     'mesh_preview': False,
     'mesh_from_result': True,
     'result_formats': ['thermal.steady2d-result-v3', 'thermal.steady2d-result-v4'],
     'field_layouts': ['thermal2d-p1-node-cell-v2', 'thermal2d-p1-node-cell-boundary-v3'],
     'fields': ['temperature', 'heat_flux'],
     'time_navigation': False,
     'resource_policy': 'candidate-unmeasured',
     'limits': {'request_bytes': 1048576,
                'max_nodes': 10201,
                'max_triangles': 20000,
                'payload_bytes': 16777216,
                'active_jobs': 1,
                'terminal_jobs': 2,
                'terminal_bytes': 33554432,
                'ttl_seconds': 300.0,
                'log_bytes': 65536,
                'error_bytes': 4096,
                'metadata_bytes': 65536,
                'status_bytes': 131072}},
    'thermal.transient2d': {'supported': True,
     'run_enabled': True,
     'validate': '/api/thermal/transient/validate',
     'run': '/api/thermal/transient/run',
     'input': 'json',
     'mesh_preview': False,
     'mesh_from_result': True,
     'time_navigation': True,
     'result_formats': ['thermal.transient2d-result-v3'],
     'field_layouts': ['thermal2d-transient-p1-node-cell-v2'],
     'payload_formats': ['studio-thermal-transient-v2',
                         'studio-thermal-transient-frame-v2',
                         'studio-thermal-transient-history-v2'],
     'fields': ['heat_flux', 'stored_heat_per_depth', 'temperature', 'thermal_energy_functional_per_depth'],
     'resource_policy': 'candidate-unmeasured',
     'limits': {'request_bytes': 1048576,
                'max_nodes': 10201,
                'max_triangles': 20000,
                'payload_bytes': 16777216,
                'active_jobs': 1,
                'terminal_jobs': 2,
                'terminal_bytes': 33554432,
                'ttl_seconds': 300.0,
                'log_bytes': 65536,
                'error_bytes': 4096,
                'metadata_bytes': 65536,
                'status_bytes': 131072,
                'max_times': 128,
                'raw_bytes': 16777216,
                'manifest_bytes': 4194304,
                'frame_page_bytes': 4194304,
                'page_rows': 16,
                'read_encoding_slots': 1,
                'ingress_slots': 1}},
    'em.cavity3d': {'supported': False},
}


def test_r2_capabilities_without_nested_regions(client):
    caps = client.get('/api/capabilities').json()
    for kind in (thermal.KIND, transient.KIND):
        caps[kind].pop('regions', None)
    assert caps == CAPABILITIES
    assert list(caps) == list(CAPABILITIES)
    for kind, block in CAPABILITIES.items():
        assert list(caps[kind]) == list(block), kind


# ---- R3: refusal matrix ---------------------------------------------------------------

def mutated(name, change):
    data = example(name)
    change(data)
    return data


def set_physics(type_):
    def change(data):
        next(iter(data['physics'].values()))['type'] = type_
    return change


def add_physics(data):
    data['physics']['other'] = {'type': 'em.modes2d'}


def set_subdivisions(value):
    def change(data):
        data['mesh']['subdivision_count'] = value
    return change


def set_times(value):
    def change(data):
        data['study']['time']['values'] = value
    return change


def over_raw_history(data):
    """Within the node and cell caps, but 128 times of 101 x 101 nodes exceed the raw history cap."""
    set_subdivisions([100, 100])(data)
    set_times(list(range(128)))(data)


def json_body(doc):
    return compact(envelope(doc))


OVERSIZED = b'{"doc":"'+b'x'*1048576+b'"}'

#: (route family, label, request bytes, content type, validate status, run status)
REFUSALS = [
    ('steady', 'not_object', json_body([1]), 'application/json', 400, 400),
    ('steady', 'optical', json_body(example('slab_te_check')), 'application/json', 400, 400),
    ('steady', 'transient_type', json_body(mutated('thermal_slab', set_physics('thermal.transient2d'))),
     'application/json', 400, 400),
    ('steady', 'cavity_type', json_body(mutated('thermal_slab', set_physics('em.cavity3d'))),
     'application/json', 400, 400),
    ('steady', 'two_physics', json_body(mutated('thermal_slab', add_physics)), 'application/json', 400, 400),
    *[('steady', 'subdivisions_'+label, json_body(mutated('thermal_slab', set_subdivisions(value))),
       'application/json', 200, 400)
      for label, value in [('none', None), ('empty', []), ('zero', [0, 2]), ('bool', [True, 2]),
                           ('float', [2.0, 2])]],
    ('steady', 'subdivisions_large', json_body(mutated('thermal_slab', set_subdivisions([101, 101]))),
     'application/json', 413, 413),
    ('steady', 'oversized', OVERSIZED, 'application/json', 413, 413),
    ('steady', 'malformed', b'{"doc":', 'application/json', 400, 400),
    ('steady', 'extra_key', compact({**envelope(example('thermal_slab')), 'extra': 0}),
     'application/json', 400, 400),
    ('steady', 'media_type', json_body(example('thermal_slab')), 'text/plain', 415, 415),
    ('transient', 'not_object', json_body([1]), 'application/json', 400, 400),
    ('transient', 'optical', json_body(example('slab_te_check')), 'application/json', 400, 400),
    ('transient', 'steady_type',
     json_body(mutated('transient_thermal_uniform', set_physics('thermal.steady2d'))), 'application/json', 400, 400),
    ('transient', 'cavity_type',
     json_body(mutated('transient_thermal_uniform', set_physics('em.cavity3d'))), 'application/json', 400, 400),
    ('transient', 'two_physics', json_body(mutated('transient_thermal_uniform', add_physics)),
     'application/json', 400, 400),
    *[('transient', 'subdivisions_'+label, json_body(mutated('transient_thermal_uniform', set_subdivisions(value))),
       'application/json', 200, 400)
      for label, value in [('none', None), ('empty', []), ('zero', [0, 2]), ('bool', [True, 2]),
                           ('float', [2.0, 2])]],
    ('transient', 'subdivisions_large',
     json_body(mutated('transient_thermal_uniform', set_subdivisions([101, 101]))),
     'application/json', 413, 413),
    ('transient', 'raw_history', json_body(mutated('transient_thermal_uniform', over_raw_history)),
     'application/json', 413, 413),
    *[('transient', 'times_'+label, json_body(mutated('transient_thermal_uniform', set_times(value))),
       'application/json', status, status_run)
      for label, value, status, status_run in [
          ('one', [2], 200, 400), ('equal', [2, 2], 200, 400), ('decreasing', [3, 2], 200, 400),
          ('bool', [2, True], 200, 400), ('129', list(range(129)), 413, 413)]],
    ('transient', 'oversized', OVERSIZED, 'application/json', 413, 413),
    ('transient', 'malformed', b'{"doc":', 'application/json', 400, 400),
    ('transient', 'extra_key', compact({**envelope(example('transient_thermal_uniform')), 'extra': 0}),
     'application/json', 400, 400),
    ('transient', 'media_type', json_body(example('transient_thermal_uniform')), 'text/plain', 415, 415),
]

REFUSAL_BODIES = {
    'steady-not_object': {
        'ok': False,
        'error': {'code': 'invalid_envelope', 'message': 'doc must be an object', 'path': 'doc'},
        'client_revision': 1,
        'request_seq': 1,
    },
    'steady-optical': {
        'ok': False,
        'error': {
            'code': 'unsupported_physics',
            'message': 'thermal Studio accepts one thermal.steady2d entry', 'path': 'physics',
        },
        'client_revision': 1,
        'request_seq': 1,
    },
    'steady-transient_type': {
        'ok': False,
        'error': {
            'code': 'unsupported_physics',
            'message': 'thermal Studio accepts one thermal.steady2d entry', 'path': 'physics',
        },
        'client_revision': 1,
        'request_seq': 1,
    },
    'steady-cavity_type': {
        'ok': False,
        'error': {
            'code': 'unsupported_physics',
            'message': 'thermal Studio accepts one thermal.steady2d entry', 'path': 'physics',
        },
        'client_revision': 1,
        'request_seq': 1,
    },
    'steady-two_physics': {
        'ok': False,
        'error': {
            'code': 'unsupported_physics',
            'message': 'thermal Studio accepts one thermal.steady2d entry', 'path': 'physics',
        },
        'client_revision': 1,
        'request_seq': 1,
    },
    'steady-subdivisions_none': {'ok': False,
     'error': {'code': 'invalid_document',
               'message': 'expected two positive integer subdivision counts',
               'path': 'mesh.subdivision_count'},
     'client_revision': 1,
     'request_seq': 1},
    'steady-subdivisions_empty': {'ok': False,
     'error': {'code': 'invalid_document',
               'message': 'expected two positive integer subdivision counts',
               'path': 'mesh.subdivision_count'},
     'client_revision': 1,
     'request_seq': 1},
    'steady-subdivisions_zero': {'ok': False,
     'error': {'code': 'invalid_document',
               'message': 'expected two positive integer subdivision counts',
               'path': 'mesh.subdivision_count'},
     'client_revision': 1,
     'request_seq': 1},
    'steady-subdivisions_bool': {'ok': False,
     'error': {'code': 'invalid_document',
               'message': 'expected two positive integer subdivision counts',
               'path': 'mesh.subdivision_count'},
     'client_revision': 1,
     'request_seq': 1},
    'steady-subdivisions_float': {'ok': False,
     'error': {'code': 'invalid_document',
               'message': 'expected two positive integer subdivision counts',
               'path': 'mesh.subdivision_count'},
     'client_revision': 1,
     'request_seq': 1},
    'steady-subdivisions_large': {'ok': False,
     'error': {'code': 'mesh_limit_exceeded',
               'message': 'thermal mesh exceeds configured node/triangle limits',
               'path': 'mesh.subdivision_count'},
     'client_revision': 1,
     'request_seq': 1},
    'steady-oversized': {
        'ok': False,
        'error': {
            'code': 'request_limit_exceeded',
            'message': 'thermal request exceeds configured byte limit',
        },
    },
    'steady-malformed': {
        'ok': False,
        'error': {'code': 'invalid_json', 'message': 'malformed finite UTF-8 JSON'},
    },
    'steady-extra_key': {
        'ok': False,
        'error': {
            'code': 'invalid_envelope',
            'message': 'expected exactly doc, client_revision and request_seq',
        },
    },
    'steady-media_type': {
        'ok': False,
        'error': {
            'code': 'unsupported_media_type',
            'message': 'thermal requests require application/json',
        },
    },
    'transient-not_object': {
        'ok': False,
        'error': {'code': 'invalid_envelope', 'message': 'doc must be an object'},
        'kind': 'thermal.transient2d',
        'client_revision': 1,
        'request_seq': 1,
    },
    'transient-optical': {
        'ok': False,
        'error': {
            'code': 'unsupported_physics',
            'message': 'transient route accepts one thermal.transient2d entry',
        },
        'kind': 'thermal.transient2d',
        'client_revision': 1,
        'request_seq': 1,
    },
    'transient-steady_type': {
        'ok': False,
        'error': {
            'code': 'unsupported_physics',
            'message': 'transient route accepts one thermal.transient2d entry',
        },
        'kind': 'thermal.transient2d',
        'client_revision': 1,
        'request_seq': 1,
    },
    'transient-cavity_type': {
        'ok': False,
        'error': {
            'code': 'unsupported_physics',
            'message': 'transient route accepts one thermal.transient2d entry',
        },
        'kind': 'thermal.transient2d',
        'client_revision': 1,
        'request_seq': 1,
    },
    'transient-two_physics': {
        'ok': False,
        'error': {
            'code': 'unsupported_physics',
            'message': 'transient route accepts one thermal.transient2d entry',
        },
        'kind': 'thermal.transient2d',
        'client_revision': 1,
        'request_seq': 1,
    },
    'transient-subdivisions_none': {'ok': False,
     'error': {'code': 'invalid_document',
               'message': 'expected two positive integer subdivision counts',
               'path': 'mesh.subdivision_count'},
     'kind': 'thermal.transient2d',
     'client_revision': 1,
     'request_seq': 1},
    'transient-subdivisions_empty': {'ok': False,
     'error': {'code': 'invalid_document',
               'message': 'expected two positive integer subdivision counts',
               'path': 'mesh.subdivision_count'},
     'kind': 'thermal.transient2d',
     'client_revision': 1,
     'request_seq': 1},
    'transient-subdivisions_zero': {'ok': False,
     'error': {'code': 'invalid_document',
               'message': 'expected two positive integer subdivision counts',
               'path': 'mesh.subdivision_count'},
     'kind': 'thermal.transient2d',
     'client_revision': 1,
     'request_seq': 1},
    'transient-subdivisions_bool': {'ok': False,
     'error': {'code': 'invalid_document',
               'message': 'expected two positive integer subdivision counts',
               'path': 'mesh.subdivision_count'},
     'kind': 'thermal.transient2d',
     'client_revision': 1,
     'request_seq': 1},
    'transient-subdivisions_float': {'ok': False,
     'error': {'code': 'invalid_document',
               'message': 'expected two positive integer subdivision counts',
               'path': 'mesh.subdivision_count'},
     'kind': 'thermal.transient2d',
     'client_revision': 1,
     'request_seq': 1},
    'transient-subdivisions_large': {'ok': False,
     'error': {'code': 'mesh_limit_exceeded',
               'message': 'thermal mesh exceeds configured node/triangle limits',
               'path': 'mesh.subdivision_count'},
     'kind': 'thermal.transient2d',
     'client_revision': 1,
     'request_seq': 1},
    'transient-raw_history': {
        'ok': False,
        'error': {
            'code': 'history_limit_exceeded',
            'message': 'combined transient history exceeds raw cap',
        },
        'kind': 'thermal.transient2d',
        'client_revision': 1,
        'request_seq': 1,
    },
    'transient-times_one': {'ok': False,
     'error': {'code': 'invalid_document',
               'message': 'study.time must be a tagged array of at least two requested times'},
     'kind': 'thermal.transient2d',
     'client_revision': 1,
     'request_seq': 1},
    'transient-times_equal': {'ok': False,
     'error': {'code': 'invalid_document',
               'message': 'requested times must be finite strictly increasing values'},
     'kind': 'thermal.transient2d',
     'client_revision': 1,
     'request_seq': 1},
    'transient-times_decreasing': {'ok': False,
     'error': {'code': 'invalid_document',
               'message': 'requested times must be finite strictly increasing values'},
     'kind': 'thermal.transient2d',
     'client_revision': 1,
     'request_seq': 1},
    'transient-times_bool': {'ok': False,
     'error': {'code': 'invalid_document',
               'message': 'requested times must be finite strictly increasing values'},
     'kind': 'thermal.transient2d',
     'client_revision': 1,
     'request_seq': 1},
    'transient-times_129': {
        'ok': False,
        'error': {'code': 'history_limit_exceeded', 'message': 'too many requested times'},
        'kind': 'thermal.transient2d',
        'client_revision': 1,
        'request_seq': 1,
    },
    'transient-oversized': {
        'ok': False,
        'error': {
            'code': 'request_limit_exceeded',
            'message': 'thermal request exceeds configured byte limit',
        },
        'kind': 'thermal.transient2d',
    },
    'transient-malformed': {
        'ok': False,
        'error': {'code': 'invalid_json', 'message': 'malformed finite UTF-8 JSON'},
        'kind': 'thermal.transient2d',
    },
    'transient-extra_key': {
        'ok': False,
        'error': {
            'code': 'invalid_envelope',
            'message': 'expected exactly doc, client_revision and request_seq',
        },
        'kind': 'thermal.transient2d',
    },
    'transient-media_type': {
        'ok': False,
        'error': {
            'code': 'unsupported_media_type',
            'message': 'thermal requests require application/json',
        },
        'kind': 'thermal.transient2d',
    },
}


def forbid_allocation(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('a refused rectangle request reached uuid, the worker or run')
    monkeypatch.setattr(server, 'uuid', SimpleNamespace(uuid4=forbidden))
    monkeypatch.setattr(server, '_start_thermal_thread', forbidden)
    monkeypatch.setattr(server, 'run', forbidden)


@pytest.mark.parametrize('family,label,content,media,validate_status,run_status', REFUSALS,
                         ids=[f'{case[0]}-{case[1]}' for case in REFUSALS])
def test_r3_rectangle_refusal_bodies(client, monkeypatch, family, label, content, media,
                                     validate_status, run_status):
    forbid_allocation(monkeypatch)
    expected = compact(REFUSAL_BODIES[family+'-'+label])
    for action, status in (('validate', validate_status), ('run', run_status)):
        response = client.post(ROUTES[family]+action, content=content, headers={'content-type': media})
        assert response.status_code == status, (action, response.text)
        assert response.headers['cache-control'] == 'no-store'
        assert response.content == expected, action
    assert not server._thermal_jobs._records
    assert_idle(server._thermal_jobs)


# ---- R4: run identity and running status ----------------------------------------------

IDENTITIES = {
    'thermal_slab': {
        'identity': {
            'kind': 'thermal.steady2d', 'job': 'thermal-0123456789abcdef0123456789abcdef',
            'result_id': 'result-0123456789abcdef0123456789abcdef', 'client_revision': 1,
            'request_seq': 1,
        },
        'status': {
            'kind': 'thermal.steady2d',
            'job': 'thermal-0123456789abcdef0123456789abcdef',
            'result_id': 'result-0123456789abcdef0123456789abcdef',
            'client_revision': 1,
            'request_seq': 1,
            'status': 'running',
            'log': [],
            'error': None,
            'has_result': False,
        },
        'not_ready': {
            'ok': False,
            'error': {'code': 'result_not_ready', 'message': 'thermal result is not available'},
            'kind': 'thermal.steady2d',
            'job': 'thermal-0123456789abcdef0123456789abcdef',
            'result_id': 'result-0123456789abcdef0123456789abcdef',
            'client_revision': 1,
            'request_seq': 1,
        },
    },
    'transient_thermal_uniform': {
        'identity': {
            'kind': 'thermal.transient2d',
            'job': 'thermal-transient-0123456789abcdef0123456789abcdef',
            'result_id': 'result-0123456789abcdef0123456789abcdef', 'client_revision': 1,
            'request_seq': 1,
        },
        'status': {
            'kind': 'thermal.transient2d',
            'job': 'thermal-transient-0123456789abcdef0123456789abcdef',
            'result_id': 'result-0123456789abcdef0123456789abcdef',
            'client_revision': 1,
            'request_seq': 1,
            'status': 'running',
            'log': [],
            'error': None,
            'has_result': False,
        },
        'not_ready': {
            'ok': False,
            'error': {'code': 'result_not_ready', 'message': 'thermal result is not available'},
            'kind': 'thermal.transient2d',
            'job': 'thermal-transient-0123456789abcdef0123456789abcdef',
            'result_id': 'result-0123456789abcdef0123456789abcdef',
            'client_revision': 1,
            'request_seq': 1,
        },
    },
}


@pytest.mark.parametrize('name', ['thermal_slab', 'transient_thermal_uniform'])
def test_r4_run_identity_and_running_status_bytes(client, monkeypatch, name):
    monkeypatch.setattr(server, 'uuid', SimpleNamespace(uuid4=lambda: SimpleNamespace(hex=TOKEN)))
    monkeypatch.setattr(server, '_start_thermal_thread', lambda target, args: None)
    family = 'transient' if name.startswith('transient') else 'steady'
    response = client.post(ROUTES[family]+'run', json=envelope(example(name)))
    assert response.status_code == 200
    assert response.content == compact(IDENTITIES[name]['identity'])
    job = IDENTITIES[name]['identity']['job']
    status = client.get('/api/jobs/'+job)
    assert status.status_code == 200
    assert status.content == compact(IDENTITIES[name]['status'])
    assert client.get('/api/jobs/'+job+'/result').content == compact(IDENTITIES[name]['not_ready'])


# ---- R5: completed results, types and shapes only -------------------------------------

def leaf(value):
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'bool'
    return {int: 'int', float: 'float', str: 'str'}[type(value)]


def numeric_shape(value):
    """(shape, leaf types) of a nested list of numbers, or None."""
    if not isinstance(value, list):
        number = isinstance(value, (int, float)) and not isinstance(value, bool)
        return ((), {leaf(value)}) if number else None
    if not value:
        return (0,), set()
    parts = [numeric_shape(v) for v in value]
    if any(p is None for p in parts) or len({p[0] for p in parts}) != 1:
        return None
    return (len(value),)+parts[0][0], set().union(*(p[1] for p in parts))


def skeleton(value):
    """JSON value types and array shapes of a decoded JSON value, in its key order.

    A nested list of numbers becomes its leaf type and shape, as 'float[561,2]'
    ('empty[0]' for an empty list); a dict keeps its keys in order."""
    if isinstance(value, dict):
        return {key: skeleton(item) for key, item in value.items()}
    if isinstance(value, list):
        numbers = numeric_shape(value)
        if numbers is not None:
            types = '|'.join(sorted(numbers[1])) or 'empty'
            return types+'['+','.join(map(str, numbers[0]))+']'
        return [skeleton(item) for item in value]
    return leaf(value)


def ordered(value):
    """Dicts as (key, value) lists, so that == also compares key order."""
    if isinstance(value, dict):
        return [(key, ordered(item)) for key, item in value.items()]
    if isinstance(value, list):
        return [ordered(item) for item in value]
    return value


def completed(client, name):
    family = 'transient' if name.startswith('transient') else 'steady'
    response = client.post(ROUTES[family]+'run', json=envelope(example(name)))
    assert response.status_code == 200, response.text
    job = response.json()
    status = client.get('/api/jobs/'+job['job'])
    assert status.json()['status'] == 'done', status.text
    views = {'status': status.json(), 'result': client.get('/api/jobs/'+job['job']+'/result').json()}
    if family == 'transient':
        manifest = views['result']
        base = '/api/jobs/'+job['job']
        frame = client.get(base+'/frame', params={
            'result_id': job['result_id'], 'field': 'temperature',
            'time_index': manifest['default_frame_index'], 'frame_seq': 1})
        history = client.get(base+'/history', params={
            'result_id': job['result_id'], 'field': 'stored_heat_per_depth',
            'start': 0, 'stop': len(manifest['time']), 'frame_seq': 2})
        assert frame.status_code == history.status_code == 200
        views.update(frame=frame.json(), history=history.json())
    return views


SKELETONS = {
    'thermal_slab': {'status': {'kind': 'str',
                'job': 'str',
                'result_id': 'str',
                'client_revision': 'int',
                'request_seq': 'int',
                'status': 'str',
                'log': ['str', 'str', 'str', 'str', 'str'],
                'error': 'null',
                'has_result': 'bool'},
     'result': {'payload_format': 'str',
                'kind': 'str',
                'job': 'str',
                'result_id': 'str',
                'client_revision': 'int',
                'request_seq': 'int',
                'result_format': 'str',
                'field_layout': 'str',
                'length_unit': 'str',
                'display_length_in_m': 'float',
                'summary': {'name': 'str',
                            'physics_name': 'str',
                            'physics_type': 'str',
                            'result_format': 'str',
                            'field_layout': 'str',
                            'diagnostics': [{'code': 'str',
                                             'severity': 'str',
                                             'path': 'str',
                                             'message': 'str',
                                             'fix': 'null',
                                             'suggestions': 'empty[0]',
                                             'acknowledged': 'null'},
                                            {'code': 'str',
                                             'severity': 'str',
                                             'path': 'str',
                                             'message': 'str',
                                             'fix': 'null',
                                             'suggestions': 'empty[0]',
                                             'acknowledged': 'null'}],
                            'defaults_applied': 'empty[0]',
                            'resolved_inputs': {'geometry.depth': {'authored': 'null',
                                                                   'value': 'null',
                                                                   'unit': 'str'},
                                                'geometry.domain.xmin': {'authored': 'float',
                                                                         'value': 'float',
                                                                         'unit': 'str',
                                                                         'length_unit': 'str'},
                                                'geometry.domain.xmax': {'authored': 'float',
                                                                         'value': 'float',
                                                                         'unit': 'str',
                                                                         'length_unit': 'str'},
                                                'geometry.domain.ymin': {'authored': 'float',
                                                                         'value': 'float',
                                                                         'unit': 'str',
                                                                         'length_unit': 'str'},
                                                'geometry.domain.ymax': {'authored': 'float',
                                                                         'value': 'float',
                                                                         'unit': 'str',
                                                                         'length_unit': 'str'},
                                                'physics.heat1.thermal_conductivity': {'authored': 'str',
                                                                                       'value': 'float',
                                                                                       'unit': 'str'},
                                                'physics.heat1.heat_source_density': {'authored': 'str',
                                                                                      'value': 'float',
                                                                                      'unit': 'str'},
                                                'physics.heat1.prescribed_temperature.left': {'authored': 'str',
                                                                                              'value': 'float',
                                                                                              'unit': 'str'},
                                                'physics.heat1.prescribed_temperature.right': {'authored': 'str',
                                                                                               'value': 'float',
                                                                                               'unit': 'str'},
                                                'mesh.subdivision_count': {'authored': 'int[2]',
                                                                           'value': 'int[2]',
                                                                           'unit': 'str'}},
                            'extent': ['str'],
                            'timing': {'wall_time': {'mesh': {'value': 'float', 'unit': 'str'},
                                                     'solve': {'value': 'float', 'unit': 'str'}}},
                            'field_units': {'node_coordinates': 'str',
                                            'temperature': 'str',
                                            'heat_flux': 'str',
                                            'generated_heat_rate_per_depth': 'str',
                                            'reaction_heat_rate_per_depth': 'str',
                                            'residual_heat_rate_per_depth': 'str',
                                            'prescribed_temperature': 'str'},
                            'field_locations': {'node_coordinates': 'str',
                                                'triangles': 'str',
                                                'temperature': 'str',
                                                'heat_flux': 'str',
                                                'generated_heat_rate_per_depth': 'str',
                                                'reaction_heat_rate_per_depth': 'str',
                                                'residual_heat_rate_per_depth': 'str',
                                                'prescribed_node_ids': 'str',
                                                'prescribed_temperature': 'str'},
                            'field_shapes': {'node_coordinates': 'int[2]',
                                             'triangles': 'int[2]',
                                             'temperature': 'int[1]',
                                             'heat_flux': 'int[2]',
                                             'generated_heat_rate_per_depth': 'int[1]',
                                             'reaction_heat_rate_per_depth': 'int[1]',
                                             'residual_heat_rate_per_depth': 'int[1]',
                                             'prescribed_node_ids': 'int[1]',
                                             'prescribed_temperature': 'int[1]'},
                            'field_components': {'node_coordinates': ['str', 'str'],
                                                 'heat_flux': ['str', 'str']},
                            'reaction_sign': 'str',
                            'mesh': {'nodes': 'int', 'triangles': 'int'},
                            'study': {'type': 'str'},
                            'thermal_conductivity': {'value': 'float', 'unit': 'str'},
                            'heat_source_density': {'value': 'float', 'unit': 'str'},
                            'prescribed_temperature': {'left': {'value': 'float', 'unit': 'str'},
                                                       'right': {'value': 'float', 'unit': 'str'}},
                            'prescribed_nodes': 'int',
                            'minimum_temperature': {'value': 'float', 'unit': 'str'},
                            'maximum_temperature': {'value': 'float', 'unit': 'str'},
                            'generated_heat_rate_per_depth': {'value': 'float', 'unit': 'str'},
                            'outward_heat_rate_per_depth': {'value': 'float', 'unit': 'str'},
                            'heat_rate_imbalance_per_depth': {'value': 'float', 'unit': 'str'},
                            'relative_conservation_residual': {'value': 'float', 'unit': 'str'},
                            'relative_residual': {'value': 'float', 'unit': 'str'}},
                'arrays': {'node_coordinates': 'float[561,2]',
                           'triangles': 'int[1024,3]',
                           'temperature': 'float[561]',
                           'heat_flux': 'float[1024,2]',
                           'generated_heat_rate_per_depth': 'float[561]',
                           'reaction_heat_rate_per_depth': 'float[561]',
                           'residual_heat_rate_per_depth': 'float[561]',
                           'prescribed_node_ids': 'int[34]',
                           'prescribed_temperature': 'float[34]'}}},
    'thermal_boundary': {'status': {'kind': 'str',
                'job': 'str',
                'result_id': 'str',
                'client_revision': 'int',
                'request_seq': 'int',
                'status': 'str',
                'log': ['str', 'str', 'str', 'str', 'str'],
                'error': 'null',
                'has_result': 'bool'},
     'result': {'payload_format': 'str',
                'kind': 'str',
                'job': 'str',
                'result_id': 'str',
                'client_revision': 'int',
                'request_seq': 'int',
                'result_format': 'str',
                'field_layout': 'str',
                'length_unit': 'str',
                'display_length_in_m': 'float',
                'summary': {'name': 'str',
                            'physics_name': 'str',
                            'physics_type': 'str',
                            'result_format': 'str',
                            'field_layout': 'str',
                            'diagnostics': [{'code': 'str',
                                             'severity': 'str',
                                             'path': 'str',
                                             'message': 'str',
                                             'fix': 'null',
                                             'suggestions': 'empty[0]',
                                             'acknowledged': 'null'},
                                            {'code': 'str',
                                             'severity': 'str',
                                             'path': 'str',
                                             'message': 'str',
                                             'fix': 'null',
                                             'suggestions': 'empty[0]',
                                             'acknowledged': 'null'}],
                            'defaults_applied': 'empty[0]',
                            'resolved_inputs': {'geometry.depth': {'authored': 'null',
                                                                   'value': 'null',
                                                                   'unit': 'str'},
                                                'geometry.domain.xmin': {'authored': 'int',
                                                                         'value': 'float',
                                                                         'unit': 'str',
                                                                         'length_unit': 'str'},
                                                'geometry.domain.xmax': {'authored': 'int',
                                                                         'value': 'float',
                                                                         'unit': 'str',
                                                                         'length_unit': 'str'},
                                                'geometry.domain.ymin': {'authored': 'int',
                                                                         'value': 'float',
                                                                         'unit': 'str',
                                                                         'length_unit': 'str'},
                                                'geometry.domain.ymax': {'authored': 'int',
                                                                         'value': 'float',
                                                                         'unit': 'str',
                                                                         'length_unit': 'str'},
                                                'physics.heat1.thermal_conductivity': {'authored': 'str',
                                                                                       'value': 'float',
                                                                                       'unit': 'str'},
                                                'physics.heat1.heat_source_density': {'authored': 'str',
                                                                                      'value': 'float',
                                                                                      'unit': 'str'},
                                                'physics.heat1.prescribed_temperature.left': {'authored': 'str',
                                                                                              'value': 'float',
                                                                                              'unit': 'str'},
                                                'physics.heat1.inward_heat_flux.right': {'authored': 'str',
                                                                                         'value': 'float',
                                                                                         'unit': 'str'},
                                                'physics.heat1.convection.right.heat_transfer_coefficient': {'authored': 'str',
                                                                                                             'value': 'float',
                                                                                                             'unit': 'str'},
                                                'physics.heat1.convection.right.ambient_temperature': {'authored': 'str',
                                                                                                       'value': 'float',
                                                                                                       'unit': 'str'},
                                                'mesh.subdivision_count': {'authored': 'int[2]',
                                                                           'value': 'int[2]',
                                                                           'unit': 'str'}},
                            'extent': ['str'],
                            'timing': {'wall_time': {'mesh': {'value': 'float', 'unit': 'str'},
                                                     'solve': {'value': 'float', 'unit': 'str'}}},
                            'field_units': {'node_coordinates': 'str',
                                            'temperature': 'str',
                                            'heat_flux': 'str',
                                            'generated_heat_rate_per_depth': 'str',
                                            'reaction_heat_rate_per_depth': 'str',
                                            'residual_heat_rate_per_depth': 'str',
                                            'prescribed_temperature': 'str',
                                            'outward_prescribed_heat_rate_per_depth': 'str',
                                            'ambient_convective_heat_rate_per_depth': 'str',
                                            'outward_convective_heat_rate_per_depth': 'str',
                                            'applied_heat_rate_per_depth': 'str'},
                            'field_locations': {'node_coordinates': 'str',
                                                'triangles': 'str',
                                                'temperature': 'str',
                                                'heat_flux': 'str',
                                                'generated_heat_rate_per_depth': 'str',
                                                'reaction_heat_rate_per_depth': 'str',
                                                'residual_heat_rate_per_depth': 'str',
                                                'prescribed_node_ids': 'str',
                                                'prescribed_temperature': 'str',
                                                'outward_prescribed_heat_rate_per_depth': 'str',
                                                'ambient_convective_heat_rate_per_depth': 'str',
                                                'outward_convective_heat_rate_per_depth': 'str',
                                                'applied_heat_rate_per_depth': 'str'},
                            'field_shapes': {'node_coordinates': 'int[2]',
                                             'triangles': 'int[2]',
                                             'temperature': 'int[1]',
                                             'heat_flux': 'int[2]',
                                             'generated_heat_rate_per_depth': 'int[1]',
                                             'reaction_heat_rate_per_depth': 'int[1]',
                                             'residual_heat_rate_per_depth': 'int[1]',
                                             'prescribed_node_ids': 'int[1]',
                                             'prescribed_temperature': 'int[1]',
                                             'outward_prescribed_heat_rate_per_depth': 'int[1]',
                                             'ambient_convective_heat_rate_per_depth': 'int[1]',
                                             'outward_convective_heat_rate_per_depth': 'int[1]',
                                             'applied_heat_rate_per_depth': 'int[1]'},
                            'field_components': {'node_coordinates': ['str', 'str'],
                                                 'heat_flux': ['str', 'str']},
                            'reaction_sign': 'str',
                            'mesh': {'nodes': 'int', 'triangles': 'int'},
                            'study': {'type': 'str'},
                            'thermal_conductivity': {'value': 'float', 'unit': 'str'},
                            'heat_source_density': {'value': 'float', 'unit': 'str'},
                            'prescribed_temperature': {'left': {'value': 'float', 'unit': 'str'}},
                            'prescribed_nodes': 'int',
                            'minimum_temperature': {'value': 'float', 'unit': 'str'},
                            'maximum_temperature': {'value': 'float', 'unit': 'str'},
                            'generated_heat_rate_per_depth': {'value': 'float', 'unit': 'str'},
                            'outward_prescribed_heat_rate_per_depth': {'value': 'float', 'unit': 'str'},
                            'outward_convective_heat_rate_per_depth': {'value': 'float', 'unit': 'str'},
                            'outward_reaction_heat_rate_per_depth': {'value': 'float', 'unit': 'str'},
                            'outward_heat_rate_per_depth': {'value': 'float', 'unit': 'str'},
                            'heat_rate_imbalance_per_depth': {'value': 'float', 'unit': 'str'},
                            'relative_conservation_residual': {'value': 'float', 'unit': 'str'},
                            'maximum_residual_heat_rate_per_depth': {'value': 'float', 'unit': 'str'},
                            'inward_heat_flux': {'right': {'value': 'float', 'unit': 'str'}},
                            'convection': {'right': {'heat_transfer_coefficient': {'value': 'float',
                                                                                   'unit': 'str'},
                                                     'ambient_temperature': {'value': 'float', 'unit': 'str'}}},
                            'outward_sign': 'str',
                            'load_definition': 'str'},
                'arrays': {'node_coordinates': 'float[81,2]',
                           'triangles': 'int[128,3]',
                           'temperature': 'float[81]',
                           'heat_flux': 'float[128,2]',
                           'generated_heat_rate_per_depth': 'float[81]',
                           'reaction_heat_rate_per_depth': 'float[81]',
                           'residual_heat_rate_per_depth': 'float[81]',
                           'prescribed_node_ids': 'int[9]',
                           'prescribed_temperature': 'float[9]',
                           'outward_prescribed_heat_rate_per_depth': 'float[81]',
                           'ambient_convective_heat_rate_per_depth': 'float[81]',
                           'outward_convective_heat_rate_per_depth': 'float[81]',
                           'applied_heat_rate_per_depth': 'float[81]'}}},
    'transient_thermal_uniform': {'status': {'kind': 'str',
                'job': 'str',
                'result_id': 'str',
                'client_revision': 'int',
                'request_seq': 'int',
                'status': 'str',
                'log': ['str', 'str', 'str', 'str'],
                'error': 'null',
                'has_result': 'bool'},
     'result': {'kind': 'str',
                'job': 'str',
                'result_id': 'str',
                'client_revision': 'int',
                'request_seq': 'int',
                'result_format': 'str',
                'field_layout': 'str',
                'length_unit': 'str',
                'display_length_in_m': 'float',
                'payload_format': 'str',
                'summary': {'name': 'str',
                            'physics_name': 'str',
                            'physics_type': 'str',
                            'result_format': 'str',
                            'field_layout': 'str',
                            'diagnostics': [{'code': 'str',
                                             'severity': 'str',
                                             'path': 'str',
                                             'message': 'str',
                                             'fix': 'null',
                                             'suggestions': [{'value': 'str',
                                                              'si_before': 'float',
                                                              'si_after': 'float',
                                                              'unit': 'str'}],
                                             'acknowledged': 'str'},
                                            {'code': 'str',
                                             'severity': 'str',
                                             'path': 'str',
                                             'message': 'str',
                                             'fix': 'null',
                                             'suggestions': 'empty[0]',
                                             'acknowledged': 'null'},
                                            {'code': 'str',
                                             'severity': 'str',
                                             'path': 'str',
                                             'message': 'str',
                                             'fix': 'null',
                                             'suggestions': 'empty[0]',
                                             'acknowledged': 'null'},
                                            {'code': 'str',
                                             'severity': 'str',
                                             'path': 'str',
                                             'message': 'str',
                                             'fix': 'null',
                                             'suggestions': 'empty[0]',
                                             'acknowledged': 'null'},
                                            {'code': 'str',
                                             'severity': 'str',
                                             'path': 'str',
                                             'message': 'str',
                                             'fix': 'null',
                                             'suggestions': 'empty[0]',
                                             'acknowledged': 'null'}],
                            'defaults_applied': 'empty[0]',
                            'resolved_inputs': {'geometry.depth': {'authored': 'null',
                                                                   'value': 'null',
                                                                   'unit': 'str'},
                                                'geometry.domain.xmin': {'authored': 'int',
                                                                         'value': 'float',
                                                                         'unit': 'str',
                                                                         'length_unit': 'str'},
                                                'geometry.domain.xmax': {'authored': 'int',
                                                                         'value': 'float',
                                                                         'unit': 'str',
                                                                         'length_unit': 'str'},
                                                'geometry.domain.ymin': {'authored': 'int',
                                                                         'value': 'float',
                                                                         'unit': 'str',
                                                                         'length_unit': 'str'},
                                                'geometry.domain.ymax': {'authored': 'int',
                                                                         'value': 'float',
                                                                         'unit': 'str',
                                                                         'length_unit': 'str'},
                                                'physics.heat1.thermal_conductivity': {'authored': 'str',
                                                                                       'value': 'float',
                                                                                       'unit': 'str'},
                                                'physics.heat1.volumetric_heat_capacity.value': {'authored': {'value': 'str',
                                                                                                              'accept': {'W-MAGNITUDE': 'str'}},
                                                                                                 'value': 'float',
                                                                                                 'unit': 'str'},
                                                'physics.heat1.initial_temperature': {'authored': 'str',
                                                                                      'value': 'float',
                                                                                      'unit': 'str'},
                                                'physics.heat1.heat_source_density': {'authored': 'str',
                                                                                      'value': 'float',
                                                                                      'unit': 'str'},
                                                'mesh.subdivision_count': {'authored': 'int[2]',
                                                                           'value': 'int[2]',
                                                                           'unit': 'str'},
                                                'study.time': {'authored': {'unit': 'str',
                                                                            'values': 'float[3]'},
                                                               'value': 'float[3]',
                                                               'unit': 'str'}},
                            'extent': ['str'],
                            'timing': {'wall_time': {'mesh': {'value': 'float', 'unit': 'str'},
                                                     'solve': {'value': 'float', 'unit': 'str'}}},
                            'field_units': {'node_coordinates': 'str',
                                            'time': 'str',
                                            'temperature': 'str',
                                            'heat_flux': 'str',
                                            'generated_heat_rate_per_depth': 'str',
                                            'reaction_heat_rate_per_depth': 'str',
                                            'residual_heat_rate_per_depth': 'str',
                                            'heat_storage_rate_per_depth': 'str',
                                            'stored_heat_per_depth': 'str',
                                            'thermal_energy_functional_per_depth': 'str',
                                            'prescribed_temperature': 'str'},
                            'field_locations': {'node_coordinates': 'str',
                                                'triangles': 'str',
                                                'time': 'str',
                                                'temperature': 'str',
                                                'heat_flux': 'str',
                                                'generated_heat_rate_per_depth': 'str',
                                                'reaction_heat_rate_per_depth': 'str',
                                                'residual_heat_rate_per_depth': 'str',
                                                'heat_storage_rate_per_depth': 'str',
                                                'stored_heat_per_depth': 'str',
                                                'thermal_energy_functional_per_depth': 'str',
                                                'prescribed_node_ids': 'str',
                                                'prescribed_temperature': 'str'},
                            'field_shapes': {'node_coordinates': 'int[2]',
                                             'triangles': 'int[2]',
                                             'time': 'int[1]',
                                             'temperature': 'int[2]',
                                             'heat_flux': 'int[3]',
                                             'generated_heat_rate_per_depth': 'int[2]',
                                             'reaction_heat_rate_per_depth': 'int[2]',
                                             'residual_heat_rate_per_depth': 'int[2]',
                                             'heat_storage_rate_per_depth': 'int[2]',
                                             'stored_heat_per_depth': 'int[1]',
                                             'thermal_energy_functional_per_depth': 'int[1]',
                                             'prescribed_node_ids': 'int[1]',
                                             'prescribed_temperature': 'int[2]'},
                            'field_time_axes': {'time': 'str',
                                                'temperature': 'str',
                                                'heat_flux': 'str',
                                                'generated_heat_rate_per_depth': 'str',
                                                'reaction_heat_rate_per_depth': 'str',
                                                'residual_heat_rate_per_depth': 'str',
                                                'heat_storage_rate_per_depth': 'str',
                                                'stored_heat_per_depth': 'str',
                                                'thermal_energy_functional_per_depth': 'str',
                                                'prescribed_temperature': 'str'},
                            'field_components': {'node_coordinates': ['str', 'str'],
                                                 'heat_flux': ['str', 'str']},
                            'mesh': {'nodes': 'int', 'triangles': 'int'},
                            'study': {'type': 'str', 'time': {'unit': 'str', 'values': 'float[3]'}},
                            'thermal_conductivity': {'value': 'float', 'unit': 'str'},
                            'volumetric_heat_capacity': {'value': 'float', 'unit': 'str'},
                            'heat_source_density': {'value': 'float', 'unit': 'str'},
                            'prescribed_nodes': 'int',
                            'minimum_temperature': {'unit': 'str', 'values': 'float[3]'},
                            'maximum_temperature': {'unit': 'str', 'values': 'float[3]'},
                            'generated_heat_rate_per_depth': {'unit': 'str', 'values': 'float[3]'},
                            'heat_storage_rate_per_depth': {'unit': 'str', 'values': 'float[2]'},
                            'outward_heat_rate_per_depth': {'unit': 'str', 'values': 'float[2]'},
                            'heat_rate_imbalance_per_depth': {'unit': 'str', 'values': 'float[2]'},
                            'stored_heat_per_depth': {'unit': 'str', 'values': 'float[3]'},
                            'thermal_energy_functional_per_depth': {'unit': 'str', 'values': 'float[3]'},
                            'reaction_sign': 'str',
                            'balance_equation': 'str',
                            'heat_content_definition': 'str',
                            'quadratic_functional_definition': 'str',
                            'save_fields': 'bool'},
                'fields': {'node_coordinates': {'shape': 'int[2]',
                                                'unit': 'str',
                                                'location': 'str',
                                                'axis': 'str',
                                                'available_views': 'empty[0]',
                                                'initial_available': 'bool',
                                                'ui_supported': 'bool'},
                           'triangles': {'shape': 'int[2]',
                                         'unit': 'null',
                                         'location': 'str',
                                         'axis': 'str',
                                         'available_views': 'empty[0]',
                                         'initial_available': 'bool',
                                         'ui_supported': 'bool'},
                           'time': {'shape': 'int[1]',
                                    'unit': 'str',
                                    'location': 'str',
                                    'axis': 'str',
                                    'available_views': 'empty[0]',
                                    'initial_available': 'bool',
                                    'ui_supported': 'bool'},
                           'temperature': {'shape': 'int[2]',
                                           'unit': 'str',
                                           'location': 'str',
                                           'axis': 'str',
                                           'available_views': ['str', 'str'],
                                           'initial_available': 'bool',
                                           'ui_supported': 'bool'},
                           'heat_flux': {'shape': 'int[3]',
                                         'unit': 'str',
                                         'location': 'str',
                                         'axis': 'str',
                                         'available_views': ['str', 'str'],
                                         'initial_available': 'bool',
                                         'ui_supported': 'bool'},
                           'generated_heat_rate_per_depth': {'shape': 'int[2]',
                                                             'unit': 'str',
                                                             'location': 'str',
                                                             'axis': 'str',
                                                             'available_views': ['str', 'str'],
                                                             'initial_available': 'bool',
                                                             'ui_supported': 'bool'},
                           'reaction_heat_rate_per_depth': {'shape': 'int[2]',
                                                            'unit': 'str',
                                                            'location': 'str',
                                                            'axis': 'str',
                                                            'available_views': ['str', 'str'],
                                                            'initial_available': 'bool',
                                                            'ui_supported': 'bool'},
                           'residual_heat_rate_per_depth': {'shape': 'int[2]',
                                                            'unit': 'str',
                                                            'location': 'str',
                                                            'axis': 'str',
                                                            'available_views': ['str', 'str'],
                                                            'initial_available': 'bool',
                                                            'ui_supported': 'bool'},
                           'heat_storage_rate_per_depth': {'shape': 'int[2]',
                                                           'unit': 'str',
                                                           'location': 'str',
                                                           'axis': 'str',
                                                           'available_views': ['str', 'str'],
                                                           'initial_available': 'bool',
                                                           'ui_supported': 'bool'},
                           'stored_heat_per_depth': {'shape': 'int[1]',
                                                     'unit': 'str',
                                                     'location': 'str',
                                                     'axis': 'str',
                                                     'available_views': ['str', 'str'],
                                                     'initial_available': 'bool',
                                                     'ui_supported': 'bool'},
                           'thermal_energy_functional_per_depth': {'shape': 'int[1]',
                                                                   'unit': 'str',
                                                                   'location': 'str',
                                                                   'axis': 'str',
                                                                   'available_views': ['str', 'str'],
                                                                   'initial_available': 'bool',
                                                                   'ui_supported': 'bool'},
                           'prescribed_node_ids': {'shape': 'int[1]',
                                                   'unit': 'null',
                                                   'location': 'str',
                                                   'axis': 'str',
                                                   'available_views': 'empty[0]',
                                                   'initial_available': 'bool',
                                                   'ui_supported': 'bool'},
                           'prescribed_temperature': {'shape': 'int[2]',
                                                      'unit': 'str',
                                                      'location': 'str',
                                                      'axis': 'str',
                                                      'available_views': ['str', 'str'],
                                                      'initial_available': 'bool',
                                                      'ui_supported': 'bool'}},
                'time': 'float[3]',
                'default_frame_index': 'int',
                'arrays': {'node_coordinates': 'float[25,2]',
                           'triangles': 'int[32,3]',
                           'prescribed_node_ids': 'empty[0]'},
                'frame_url': 'str',
                'history_url': 'str'},
     'frame': {'kind': 'str',
               'job': 'str',
               'result_id': 'str',
               'client_revision': 'int',
               'request_seq': 'int',
               'result_format': 'str',
               'field_layout': 'str',
               'display_length_in_m': 'float',
               'frame_seq': 'int',
               'field': 'str',
               'unit': 'str',
               'location': 'str',
               'payload_format': 'str',
               'time_index': 'int',
               'time': 'float',
               'shape': 'int[1]',
               'arrays': {'temperature': 'float[25]'}},
     'history': {'kind': 'str',
                 'job': 'str',
                 'result_id': 'str',
                 'client_revision': 'int',
                 'request_seq': 'int',
                 'result_format': 'str',
                 'field_layout': 'str',
                 'display_length_in_m': 'float',
                 'frame_seq': 'int',
                 'field': 'str',
                 'unit': 'str',
                 'location': 'str',
                 'payload_format': 'str',
                 'start': 'int',
                 'stop': 'int',
                 'time_indices': 'int[3]',
                 'time': 'float[3]',
                 'shape': 'int[1]',
                 'arrays': {'stored_heat_per_depth': 'float[3]'}}},
}


@pytest.mark.parametrize('name', ['thermal_slab', 'thermal_boundary', 'transient_thermal_uniform'])
def test_r5_completed_rectangle_views_keep_keys_types_and_shapes(client, name):
    views = completed(client, name)
    assert ordered({key: skeleton(value) for key, value in views.items()}) == ordered(SKELETONS[name])
    assert_idle(server._thermal_jobs)
