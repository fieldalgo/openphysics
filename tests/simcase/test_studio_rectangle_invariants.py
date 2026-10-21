# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Rectangle thermal Studio behaviour, pinned before Studio accepts region documents.

Region support must not change a byte, a code path or an error of rectangle documents.
Every expectation below was recorded on the commit before the region route existed and
is a literal: the exact bytes of rectangle validation responses (R1), the capability
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
    'thermal_slab': {
        'ok': True,
        'doc': {
            'openphysics': '0.2',
            'name': 'Steady heat slab',
            'geometry': {'domain': {'xmin': 0.0, 'xmax': 30.0, 'ymin': 0.0, 'ymax': 20.0}},
            'materials': {},
            'physics': {
                'heat1': {
                    'type': 'thermal.steady2d',
                    'conductivity_w_mk': 12.5,
                    'heat_source_w_m3': 0.0,
                    'dirichlet_temperature_k': {'left': 280.0, 'right': 315.0},
                },
            },
            'mesh': {'subdivisions': [32, 16]},
            'study': {'type': 'single'},
            'results': {'save_fields': True, 'plots': False},
            'units': {'length': 'mm', 'temperature': 'K'},
        },
        'summary': (
            'Steady heat slab (openphysics 0.2)\n'
            '  physics heat1: thermal.steady2d, single steady heat\n'
            "  domain {'xmin': 0.0, 'xmax': 30.0, 'ymin': 0.0, 'ymax': 20.0} mm; mesh [32, 16]\n"
            '  k=12.5 W/(m K), Q=0.0 W/m^3\n'
            "  Dirichlet {'left': 280.0, 'right': 315.0} K; remaining exterior insulated\n"
            '  output: coordinates m, temperature K, flux W/m^2, nodal heat W/m of depth'
        ),
        'notes': [],
        'client_revision': 1,
        'request_seq': 1,
    },
    'thermal_boundary': {
        'ok': True,
        'doc': {
            'openphysics': '0.2',
            'name': 'Steady additive outward flux and convection',
            'geometry': {'domain': {'xmin': 0, 'xmax': 1, 'ymin': 0, 'ymax': 1}},
            'materials': {},
            'physics': {
                'heat1': {
                    'type': 'thermal.steady2d',
                    'conductivity_w_mk': 2,
                    'heat_source_w_m3': 0,
                    'dirichlet_temperature_k': {'left': 300},
                    'outward_flux_w_m2': {'right': 2},
                    'convection': {'right': {'h_w_m2k': 4, 'ambient_temperature_k': 290}},
                },
            },
            'mesh': {'subdivisions': [8, 8]},
            'study': {'type': 'single'},
            'results': {'save_fields': True, 'plots': False},
            'units': {'length': 'm', 'temperature': 'K'},
        },
        'summary': (
            'Steady additive outward flux and convection (openphysics 0.2)\n'
            '  physics heat1: thermal.steady2d, single steady heat\n'
            "  domain {'xmin': 0, 'xmax': 1, 'ymin': 0, 'ymax': 1} m; mesh [8, 8]\n"
            '  k=2 W/(m K), Q=0 W/m^3\n'
            "  Dirichlet {'left': 300} K; outward flux {'right': 2} W/m^2; convection {'right': "
            "{'h_w_m2k': 4, 'ambient_temperature_k': 290}}\n"
            '  q.n = g_out + h*(T-T_ambient); unselected natural sides insulated\n'
            '  result: thermal.steady2d-result-v2; layout: thermal2d-p1-node-cell-boundary-v2\n'
            '  output: coordinates m, temperature K, flux W/m^2, nodal heat W/m of depth'
        ),
        'notes': [],
        'client_revision': 1,
        'request_seq': 1,
    },
    'thermal_mixed': {
        'ok': True,
        'doc': {
            'openphysics': '0.2',
            'name': 'Steady heat with uniform source',
            'geometry': {'domain': {'xmin': 0.0, 'xmax': 30.0, 'ymin': 0.0, 'ymax': 20.0}},
            'materials': {},
            'physics': {
                'heat1': {
                    'type': 'thermal.steady2d',
                    'conductivity_w_mk': 12.5,
                    'heat_source_w_m3': 100000.0,
                    'dirichlet_temperature_k': {'left': 280.0, 'right': 315.0},
                },
            },
            'mesh': {'subdivisions': [32, 16]},
            'study': {'type': 'single'},
            'results': {'save_fields': True, 'plots': False},
            'units': {'length': 'mm', 'temperature': 'K'},
        },
        'summary': (
            'Steady heat with uniform source (openphysics 0.2)\n'
            '  physics heat1: thermal.steady2d, single steady heat\n'
            "  domain {'xmin': 0.0, 'xmax': 30.0, 'ymin': 0.0, 'ymax': 20.0} mm; mesh [32, 16]\n"
            '  k=12.5 W/(m K), Q=100000.0 W/m^3\n'
            "  Dirichlet {'left': 280.0, 'right': 315.0} K; remaining exterior insulated\n"
            '  output: coordinates m, temperature K, flux W/m^2, nodal heat W/m of depth'
        ),
        'notes': [],
        'client_revision': 1,
        'request_seq': 1,
    },
    'transient_thermal_uniform': {
        'ok': True,
        'kind': 'thermal.transient2d',
        'client_revision': 1,
        'request_seq': 1,
        'doc': {
            'openphysics': '0.2',
            'name': 'Insulated constant-source transient heat',
            'geometry': {'domain': {'xmin': 0, 'xmax': 1, 'ymin': 0, 'ymax': 1}},
            'materials': {},
            'physics': {
                'heat1': {
                    'type': 'thermal.transient2d',
                    'conductivity_w_mk': 2.5,
                    'volumetric_heat_capacity_j_m3k': 4.0,
                    'initial_temperature_k': 300.0,
                    'dirichlet_temperature_k': {},
                    'heat_source_w_m3': 8.0,
                },
            },
            'mesh': {'subdivisions': [4, 4]},
            'study': {'type': 'transient', 'time_s': [0.0, 0.1, 0.3]},
            'results': {'save_fields': True, 'plots': False},
            'units': {'length': 'm', 'temperature': 'K', 'time': 's'},
        },
        'summary': (
            'Insulated constant-source transient heat (openphysics 0.2)\n'
            '  physics heat1: thermal.transient2d, 3 explicit times in s\n'
            "  domain {'xmin': 0, 'xmax': 1, 'ymin': 0, 'ymax': 1} m; mesh [4, 4]\n"
            '  k=2.5 W/(m K), c=4.0 J/(m^3 K)\n'
            '  output: SI time/node/cell histories; rates at interval ends only'
        ),
        'notes': [],
    },
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
    'thermal.steady2d': {
        'supported': True,
        'run_enabled': True,
        'validate': '/api/thermal/validate',
        'run': '/api/thermal/run',
        'input': 'json',
        'mesh_preview': False,
        'mesh_from_result': True,
        'result_formats': ['thermal.steady2d-result-v1', 'thermal.steady2d-result-v2'],
        'field_layouts': ['thermal2d-p1-node-cell-v1', 'thermal2d-p1-node-cell-boundary-v2'],
        'fields': ['temperature_k', 'heat_flux_w_m2'],
        'time_navigation': False,
        'resource_policy': 'candidate-unmeasured',
        'limits': {
            'request_bytes': 1048576, 'max_nodes': 10201, 'max_triangles': 20000,
            'payload_bytes': 16777216, 'active_jobs': 1, 'terminal_jobs': 2,
            'terminal_bytes': 33554432, 'ttl_seconds': 300.0, 'log_bytes': 65536,
            'error_bytes': 4096, 'metadata_bytes': 65536, 'status_bytes': 131072,
        },
    },
    'thermal.transient2d': {
        'supported': True,
        'run_enabled': True,
        'validate': '/api/thermal/transient/validate',
        'run': '/api/thermal/transient/run',
        'input': 'json',
        'mesh_preview': False,
        'mesh_from_result': True,
        'time_navigation': True,
        'result_formats': ['thermal.transient2d-result-v1'],
        'field_layouts': ['thermal2d-transient-p1-node-cell-v1'],
        'payload_formats': [
            'studio-thermal-transient-v1', 'studio-thermal-transient-frame-v1',
            'studio-thermal-transient-history-v1',
        ],
        'fields': [
            'heat_content_j_per_m', 'heat_flux_w_m2', 'quadratic_functional_jk_per_m',
            'temperature_k',
        ],
        'resource_policy': 'candidate-unmeasured',
        'limits': {
            'request_bytes': 1048576, 'max_nodes': 10201, 'max_triangles': 20000,
            'payload_bytes': 16777216, 'active_jobs': 1, 'terminal_jobs': 2,
            'terminal_bytes': 33554432, 'ttl_seconds': 300.0, 'log_bytes': 65536,
            'error_bytes': 4096, 'metadata_bytes': 65536, 'status_bytes': 131072, 'max_times': 128,
            'raw_bytes': 16777216, 'manifest_bytes': 4194304, 'frame_page_bytes': 4194304,
            'page_rows': 16, 'read_encoding_slots': 1, 'ingress_slots': 1,
        },
    },
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
        data['mesh']['subdivisions'] = value
    return change


def set_times(value):
    def change(data):
        data['study']['time_s'] = value
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
    'steady-subdivisions_none': {
        'ok': False,
        'error': {
            'code': 'invalid_document', 'message': 'expected two positive integer subdivisions',
            'path': 'mesh.subdivisions',
        },
        'client_revision': 1,
        'request_seq': 1,
    },
    'steady-subdivisions_empty': {
        'ok': False,
        'error': {
            'code': 'invalid_document', 'message': 'expected two positive integer subdivisions',
            'path': 'mesh.subdivisions',
        },
        'client_revision': 1,
        'request_seq': 1,
    },
    'steady-subdivisions_zero': {
        'ok': False,
        'error': {
            'code': 'invalid_document', 'message': 'expected two positive integer subdivisions',
            'path': 'mesh.subdivisions',
        },
        'client_revision': 1,
        'request_seq': 1,
    },
    'steady-subdivisions_bool': {
        'ok': False,
        'error': {
            'code': 'invalid_document', 'message': 'expected two positive integer subdivisions',
            'path': 'mesh.subdivisions',
        },
        'client_revision': 1,
        'request_seq': 1,
    },
    'steady-subdivisions_float': {
        'ok': False,
        'error': {
            'code': 'invalid_document', 'message': 'expected two positive integer subdivisions',
            'path': 'mesh.subdivisions',
        },
        'client_revision': 1,
        'request_seq': 1,
    },
    'steady-subdivisions_large': {
        'ok': False,
        'error': {
            'code': 'mesh_limit_exceeded',
            'message': 'thermal mesh exceeds configured node/triangle limits',
            'path': 'mesh.subdivisions',
        },
        'client_revision': 1,
        'request_seq': 1,
    },
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
    'transient-subdivisions_none': {
        'ok': False,
        'error': {
            'code': 'invalid_document',
            'message': 'mesh.subdivisions must be two positive integers',
        },
        'kind': 'thermal.transient2d',
        'client_revision': 1,
        'request_seq': 1,
    },
    'transient-subdivisions_empty': {
        'ok': False,
        'error': {
            'code': 'invalid_document',
            'message': 'mesh.subdivisions must be two positive integers',
        },
        'kind': 'thermal.transient2d',
        'client_revision': 1,
        'request_seq': 1,
    },
    'transient-subdivisions_zero': {
        'ok': False,
        'error': {
            'code': 'invalid_document',
            'message': 'mesh.subdivisions must be two positive integers',
        },
        'kind': 'thermal.transient2d',
        'client_revision': 1,
        'request_seq': 1,
    },
    'transient-subdivisions_bool': {
        'ok': False,
        'error': {
            'code': 'invalid_document',
            'message': 'mesh.subdivisions must be two positive integers',
        },
        'kind': 'thermal.transient2d',
        'client_revision': 1,
        'request_seq': 1,
    },
    'transient-subdivisions_float': {
        'ok': False,
        'error': {
            'code': 'invalid_document',
            'message': 'mesh.subdivisions must be two positive integers',
        },
        'kind': 'thermal.transient2d',
        'client_revision': 1,
        'request_seq': 1,
    },
    'transient-subdivisions_large': {
        'ok': False,
        'error': {'code': 'mesh_limit_exceeded', 'message': 'transient mesh exceeds resource cap'},
        'kind': 'thermal.transient2d',
        'client_revision': 1,
        'request_seq': 1,
    },
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
    'transient-times_one': {
        'ok': False,
        'error': {
            'code': 'invalid_document',
            'message': 'study.time_s must contain at least two requested times',
        },
        'kind': 'thermal.transient2d',
        'client_revision': 1,
        'request_seq': 1,
    },
    'transient-times_equal': {
        'ok': False,
        'error': {
            'code': 'invalid_document',
            'message': 'requested times must be finite strictly increasing seconds',
        },
        'kind': 'thermal.transient2d',
        'client_revision': 1,
        'request_seq': 1,
    },
    'transient-times_decreasing': {
        'ok': False,
        'error': {
            'code': 'invalid_document',
            'message': 'requested times must be finite strictly increasing seconds',
        },
        'kind': 'thermal.transient2d',
        'client_revision': 1,
        'request_seq': 1,
    },
    'transient-times_bool': {
        'ok': False,
        'error': {
            'code': 'invalid_document',
            'message': 'requested times must be finite strictly increasing seconds',
        },
        'kind': 'thermal.transient2d',
        'client_revision': 1,
        'request_seq': 1,
    },
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
            'result_id': job['result_id'], 'field': 'temperature_k',
            'time_index': manifest['default_frame_index'], 'frame_seq': 1})
        history = client.get(base+'/history', params={
            'result_id': job['result_id'], 'field': 'heat_content_j_per_m',
            'start': 0, 'stop': len(manifest['time_s']), 'frame_seq': 2})
        assert frame.status_code == history.status_code == 200
        views.update(frame=frame.json(), history=history.json())
    return views


SKELETONS = {
    'thermal_slab': {
        'status': {
            'kind': 'str',
            'job': 'str',
            'result_id': 'str',
            'client_revision': 'int',
            'request_seq': 'int',
            'status': 'str',
            'log': ['str', 'str', 'str'],
            'error': 'null',
            'has_result': 'bool',
        },
        'result': {
            'payload_format': 'str',
            'kind': 'str',
            'job': 'str',
            'result_id': 'str',
            'client_revision': 'int',
            'request_seq': 'int',
            'result_format': 'str',
            'field_layout': 'str',
            'display_length_in_m': 'float',
            'summary': {
                'name': 'str',
                'physics_name': 'str',
                'physics_type': 'str',
                'result_format': 'str',
                'field_layout': 'str',
                'units': {'length': 'str', 'temperature': 'str'},
                'mesh_length_unit': 'str',
                'field_units': {
                    'nodes_m': 'str', 'triangles': 'str', 'dirichlet_node_ids': 'str',
                    'dirichlet_temperature_k': 'str', 'temperature_k': 'str',
                    'heat_flux_w_m2': 'str', 'load_w_per_m': 'str', 'reaction_w_per_m': 'str',
                    'residual_w_per_m': 'str',
                },
                'field_locations': {
                    'nodes_m': 'str', 'triangles': 'str', 'dirichlet_node_ids': 'str',
                    'dirichlet_temperature_k': 'str', 'temperature_k': 'str',
                    'heat_flux_w_m2': 'str', 'load_w_per_m': 'str', 'reaction_w_per_m': 'str',
                    'residual_w_per_m': 'str',
                },
                'field_shapes': {
                    'nodes_m': 'int[2]', 'triangles': 'int[2]', 'temperature_k': 'int[1]',
                    'heat_flux_w_m2': 'int[2]', 'load_w_per_m': 'int[1]',
                    'reaction_w_per_m': 'int[1]', 'residual_w_per_m': 'int[1]',
                    'dirichlet_node_ids': 'int[1]', 'dirichlet_temperature_k': 'int[1]',
                },
                'reaction_sign': 'str',
                'mesh': {'nodes': 'int', 'triangles': 'int', 'subdivisions': 'int[2]'},
                'study': {'type': 'str'},
                'conductivity_w_mk': 'float',
                'heat_source_w_m3': 'float',
                'dirichlet_temperature_k': {'left': 'float', 'right': 'float'},
                'dirichlet_nodes': 'int',
                'temperature_min_k': 'float',
                'temperature_max_k': 'float',
                'source_heat_w_per_m': 'float',
                'outward_heat_w_per_m': 'float',
                'heat_balance_defect_w_per_m': 'float',
                'normalized_heat_balance_defect': 'float',
                'normalized_free_residual': 'float',
                'timings_s': {'mesh': 'float', 'solve': 'float'},
            },
            'arrays': {
                'nodes_m': 'float[561,2]', 'triangles': 'int[1024,3]',
                'temperature_k': 'float[561]', 'heat_flux_w_m2': 'float[1024,2]',
                'load_w_per_m': 'float[561]', 'reaction_w_per_m': 'float[561]',
                'residual_w_per_m': 'float[561]', 'dirichlet_node_ids': 'int[34]',
                'dirichlet_temperature_k': 'float[34]',
            },
        },
    },
    'thermal_boundary': {
        'status': {
            'kind': 'str',
            'job': 'str',
            'result_id': 'str',
            'client_revision': 'int',
            'request_seq': 'int',
            'status': 'str',
            'log': ['str', 'str', 'str'],
            'error': 'null',
            'has_result': 'bool',
        },
        'result': {
            'payload_format': 'str',
            'kind': 'str',
            'job': 'str',
            'result_id': 'str',
            'client_revision': 'int',
            'request_seq': 'int',
            'result_format': 'str',
            'field_layout': 'str',
            'display_length_in_m': 'float',
            'summary': {
                'name': 'str',
                'physics_name': 'str',
                'physics_type': 'str',
                'result_format': 'str',
                'field_layout': 'str',
                'units': {'length': 'str', 'temperature': 'str'},
                'mesh_length_unit': 'str',
                'field_units': {
                    'nodes_m': 'str', 'triangles': 'str', 'dirichlet_node_ids': 'str',
                    'dirichlet_temperature_k': 'str', 'temperature_k': 'str',
                    'heat_flux_w_m2': 'str', 'load_w_per_m': 'str', 'reaction_w_per_m': 'str',
                    'residual_w_per_m': 'str', 'prescribed_outward_load_w_per_m': 'str',
                    'ambient_load_w_per_m': 'str', 'convective_outward_w_per_m': 'str',
                    'system_rhs_w_per_m': 'str',
                },
                'field_locations': {
                    'nodes_m': 'str', 'triangles': 'str', 'dirichlet_node_ids': 'str',
                    'dirichlet_temperature_k': 'str', 'temperature_k': 'str',
                    'heat_flux_w_m2': 'str', 'load_w_per_m': 'str', 'reaction_w_per_m': 'str',
                    'residual_w_per_m': 'str', 'prescribed_outward_load_w_per_m': 'str',
                    'ambient_load_w_per_m': 'str', 'convective_outward_w_per_m': 'str',
                    'system_rhs_w_per_m': 'str',
                },
                'field_shapes': {
                    'nodes_m': 'int[2]', 'triangles': 'int[2]', 'temperature_k': 'int[1]',
                    'heat_flux_w_m2': 'int[2]', 'load_w_per_m': 'int[1]',
                    'reaction_w_per_m': 'int[1]', 'residual_w_per_m': 'int[1]',
                    'dirichlet_node_ids': 'int[1]', 'dirichlet_temperature_k': 'int[1]',
                    'prescribed_outward_load_w_per_m': 'int[1]', 'ambient_load_w_per_m': 'int[1]',
                    'convective_outward_w_per_m': 'int[1]', 'system_rhs_w_per_m': 'int[1]',
                },
                'reaction_sign': 'str',
                'mesh': {'nodes': 'int', 'triangles': 'int', 'subdivisions': 'int[2]'},
                'study': {'type': 'str'},
                'conductivity_w_mk': 'int',
                'heat_source_w_m3': 'int',
                'dirichlet_temperature_k': {'left': 'int'},
                'dirichlet_nodes': 'int',
                'temperature_min_k': 'float',
                'temperature_max_k': 'float',
                'source_heat_w_per_m': 'float',
                'prescribed_outward_heat_w_per_m': 'float',
                'convective_outward_heat_w_per_m': 'float',
                'thermostat_outward_heat_w_per_m': 'float',
                'outward_heat_w_per_m': 'float',
                'heat_balance_defect_w_per_m': 'float',
                'normalized_heat_balance_defect': 'float',
                'free_residual_max_w_per_m': 'float',
                'timings_s': {'mesh': 'float', 'solve': 'float'},
                'outward_flux_w_m2': {'right': 'int'},
                'convection': {'right': {'h_w_m2k': 'int', 'ambient_temperature_k': 'int'}},
                'outward_sign': 'str',
                'load_definition': 'str',
            },
            'arrays': {
                'nodes_m': 'float[81,2]', 'triangles': 'int[128,3]', 'temperature_k': 'float[81]',
                'heat_flux_w_m2': 'float[128,2]', 'load_w_per_m': 'float[81]',
                'reaction_w_per_m': 'float[81]', 'residual_w_per_m': 'float[81]',
                'dirichlet_node_ids': 'int[9]', 'dirichlet_temperature_k': 'float[9]',
                'prescribed_outward_load_w_per_m': 'float[81]',
                'ambient_load_w_per_m': 'float[81]', 'convective_outward_w_per_m': 'float[81]',
                'system_rhs_w_per_m': 'float[81]',
            },
        },
    },
    'transient_thermal_uniform': {
        'status': {
            'kind': 'str',
            'job': 'str',
            'result_id': 'str',
            'client_revision': 'int',
            'request_seq': 'int',
            'status': 'str',
            'log': ['str', 'str', 'str'],
            'error': 'null',
            'has_result': 'bool',
        },
        'result': {
            'kind': 'str',
            'job': 'str',
            'result_id': 'str',
            'client_revision': 'int',
            'request_seq': 'int',
            'result_format': 'str',
            'field_layout': 'str',
            'display_length_in_m': 'float',
            'payload_format': 'str',
            'summary': {
                'name': 'str',
                'physics_name': 'str',
                'physics_type': 'str',
                'result_format': 'str',
                'field_layout': 'str',
                'units': {'length': 'str', 'temperature': 'str', 'time': 'str'},
                'mesh_length_unit': 'str',
                'field_units': {
                    'nodes_m': 'str', 'triangles': 'str', 'time_s': 'str', 'temperature_k': 'str',
                    'heat_flux_w_m2': 'str', 'source_load_w_per_m': 'str',
                    'reaction_w_per_m': 'str', 'residual_w_per_m': 'str',
                    'storage_rate_w_per_m': 'str', 'heat_content_j_per_m': 'str',
                    'quadratic_functional_jk_per_m': 'str', 'dirichlet_node_ids': 'str',
                    'dirichlet_temperatures_k': 'str',
                },
                'field_locations': {
                    'nodes_m': 'str', 'triangles': 'str', 'time_s': 'str', 'temperature_k': 'str',
                    'heat_flux_w_m2': 'str', 'source_load_w_per_m': 'str',
                    'reaction_w_per_m': 'str', 'residual_w_per_m': 'str',
                    'storage_rate_w_per_m': 'str', 'heat_content_j_per_m': 'str',
                    'quadratic_functional_jk_per_m': 'str', 'dirichlet_node_ids': 'str',
                    'dirichlet_temperatures_k': 'str',
                },
                'field_time_axes': {
                    'nodes_m': 'str', 'triangles': 'str', 'time_s': 'str', 'temperature_k': 'str',
                    'heat_flux_w_m2': 'str', 'source_load_w_per_m': 'str',
                    'reaction_w_per_m': 'str', 'residual_w_per_m': 'str',
                    'storage_rate_w_per_m': 'str', 'heat_content_j_per_m': 'str',
                    'quadratic_functional_jk_per_m': 'str', 'dirichlet_node_ids': 'str',
                    'dirichlet_temperatures_k': 'str',
                },
                'field_shapes': {
                    'nodes_m': 'int[2]', 'triangles': 'int[2]', 'time_s': 'int[1]',
                    'temperature_k': 'int[2]', 'heat_flux_w_m2': 'int[3]',
                    'source_load_w_per_m': 'int[2]', 'reaction_w_per_m': 'int[2]',
                    'residual_w_per_m': 'int[2]', 'storage_rate_w_per_m': 'int[2]',
                    'heat_content_j_per_m': 'int[1]', 'quadratic_functional_jk_per_m': 'int[1]',
                    'dirichlet_node_ids': 'int[1]', 'dirichlet_temperatures_k': 'int[2]',
                },
                'mesh': {'nodes': 'int', 'triangles': 'int', 'subdivisions': 'int[2]'},
                'study': {'type': 'str', 'time_s': 'float[3]'},
                'conductivity_w_mk': 'float',
                'volumetric_heat_capacity_j_m3k': 'float',
                'heat_source_w_m3': 'float',
                'dirichlet_nodes': 'int',
                'temperature_min_k': 'float[3]',
                'temperature_max_k': 'float[3]',
                'source_heat_w_per_m': 'float[3]',
                'storage_heat_w_per_m': 'float[2]',
                'outward_heat_w_per_m': 'float[2]',
                'heat_balance_defect_w_per_m': 'float[2]',
                'heat_content_j_per_m': 'float[3]',
                'quadratic_functional_jk_per_m': 'float[3]',
                'rate_time_s': 'float[2]',
                'reaction_sign': 'str',
                'balance_equation': 'str',
                'heat_content_definition': 'str',
                'quadratic_functional_definition': 'str',
                'save_fields': 'bool',
                'timings_s': {'mesh': 'float', 'solve': 'float'},
            },
            'fields': {
                'nodes_m': {
                    'shape': 'int[2]', 'unit': 'str', 'location': 'str', 'axis': 'str',
                    'available_views': 'empty[0]', 'initial_available': 'bool',
                    'ui_supported': 'bool',
                },
                'triangles': {
                    'shape': 'int[2]', 'unit': 'str', 'location': 'str', 'axis': 'str',
                    'available_views': 'empty[0]', 'initial_available': 'bool',
                    'ui_supported': 'bool',
                },
                'time_s': {
                    'shape': 'int[1]', 'unit': 'str', 'location': 'str', 'axis': 'str',
                    'available_views': 'empty[0]', 'initial_available': 'bool',
                    'ui_supported': 'bool',
                },
                'temperature_k': {
                    'shape': 'int[2]',
                    'unit': 'str',
                    'location': 'str',
                    'axis': 'str',
                    'available_views': ['str', 'str'],
                    'initial_available': 'bool',
                    'ui_supported': 'bool',
                },
                'heat_flux_w_m2': {
                    'shape': 'int[3]',
                    'unit': 'str',
                    'location': 'str',
                    'axis': 'str',
                    'available_views': ['str', 'str'],
                    'initial_available': 'bool',
                    'ui_supported': 'bool',
                },
                'source_load_w_per_m': {
                    'shape': 'int[2]',
                    'unit': 'str',
                    'location': 'str',
                    'axis': 'str',
                    'available_views': ['str', 'str'],
                    'initial_available': 'bool',
                    'ui_supported': 'bool',
                },
                'reaction_w_per_m': {
                    'shape': 'int[2]',
                    'unit': 'str',
                    'location': 'str',
                    'axis': 'str',
                    'available_views': ['str', 'str'],
                    'initial_available': 'bool',
                    'ui_supported': 'bool',
                },
                'residual_w_per_m': {
                    'shape': 'int[2]',
                    'unit': 'str',
                    'location': 'str',
                    'axis': 'str',
                    'available_views': ['str', 'str'],
                    'initial_available': 'bool',
                    'ui_supported': 'bool',
                },
                'storage_rate_w_per_m': {
                    'shape': 'int[2]',
                    'unit': 'str',
                    'location': 'str',
                    'axis': 'str',
                    'available_views': ['str', 'str'],
                    'initial_available': 'bool',
                    'ui_supported': 'bool',
                },
                'heat_content_j_per_m': {
                    'shape': 'int[1]',
                    'unit': 'str',
                    'location': 'str',
                    'axis': 'str',
                    'available_views': ['str', 'str'],
                    'initial_available': 'bool',
                    'ui_supported': 'bool',
                },
                'quadratic_functional_jk_per_m': {
                    'shape': 'int[1]',
                    'unit': 'str',
                    'location': 'str',
                    'axis': 'str',
                    'available_views': ['str', 'str'],
                    'initial_available': 'bool',
                    'ui_supported': 'bool',
                },
                'dirichlet_node_ids': {
                    'shape': 'int[1]', 'unit': 'str', 'location': 'str', 'axis': 'str',
                    'available_views': 'empty[0]', 'initial_available': 'bool',
                    'ui_supported': 'bool',
                },
                'dirichlet_temperatures_k': {
                    'shape': 'int[2]',
                    'unit': 'str',
                    'location': 'str',
                    'axis': 'str',
                    'available_views': ['str', 'str'],
                    'initial_available': 'bool',
                    'ui_supported': 'bool',
                },
            },
            'time_s': 'float[3]',
            'default_frame_index': 'int',
            'arrays': {
                'nodes_m': 'float[25,2]', 'triangles': 'int[32,3]',
                'dirichlet_node_ids': 'empty[0]',
            },
            'frame_url': 'str',
            'history_url': 'str',
        },
        'frame': {
            'kind': 'str',
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
            'time_s': 'float',
            'shape': 'int[1]',
            'arrays': {'temperature_k': 'float[25]'},
        },
        'history': {
            'kind': 'str',
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
            'time_s': 'float[3]',
            'shape': 'int[1]',
            'arrays': {'heat_content_j_per_m': 'float[3]'},
        },
    },
}


@pytest.mark.parametrize('name', ['thermal_slab', 'thermal_boundary', 'transient_thermal_uniform'])
def test_r5_completed_rectangle_views_keep_keys_types_and_shapes(client, name):
    views = completed(client, name)
    assert ordered({key: skeleton(value) for key, value in views.items()}) == ordered(SKELETONS[name])
    assert_idle(server._thermal_jobs)
