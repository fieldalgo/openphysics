# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady heat documents with named material regions (EM-style shapes).

The exact reference is refsol.thermal_multilayer (NumPy only); the adapter is
also compared with a direct galerkin.thermal call on the same mesh.
"""
import copy
import json

import numpy as np
import pytest

from simcase import Document, DocumentError, examples, run
from simcase.cli import main
from simcase.thermal_regions import handoff_03
from refsol.thermal_multilayer import layered_slab


def wall(size=1., unit='mm', scale=1.):
    """Steel plate 10 mm + insulation 20 mm, 5 mm high, Q only in the steel."""
    s = scale
    return {'openphysics': '0.3', 'name': 'layered wall',
            'geometry': {'length_unit': unit, 'depth': None,
                         'domain': {'xmin': 0., 'xmax': 30.*s, 'ymin': 0., 'ymax': 5.*s},
                         'background': {'material': 'insulation'},
                         'shapes': [{'name': 'steel_plate', 'type': 'rect', 'x': 0., 'y': 0., 'w': 10.*s,
                                     'h': 5.*s, 'material': 'steel'}]},
            'materials': {'steel': {'thermal_conductivity': '45 W/(m K)'},
                          'insulation': {'thermal_conductivity': '0.5 W/(m K)'}},
            'physics': {'heat1': {'type': 'thermal.steady2d', 'heat_source_density': {'steel_plate': '2e5 W/m^3'},
                                  'prescribed_temperature': {'left': '400 K', 'right': '300 K'}}},
            'mesh': {'element_size': f'{size*s!r} {unit}'}, 'study': {'type': 'single'},
            'results': {'save_fields': True, 'plots': False}}


def handoff(data):
    """The mesh hand-off of a heat region document (its geometry in the document's
    length_unit), which the geometry helpers take."""
    return handoff_03(Document.from_dict(data))


EXACT = dict(interfaces=[.01, .03], conductivities=[45., .5], left_temperature=400.,
             right_temperature=300., sources=[2e5, 0.])


def _errors(result):
    mesh = result.mesh
    layer_of = np.array([0 if n == 'steel_plate' else 1 for n in mesh.region_names])
    x, w = np.polynomial.legendre.leggauss(8)
    x, w = (x+1)/2, w/2
    a, b = np.meshgrid(x, x, indexing='ij')
    bary = np.stack([(1-a)*(1-b), a, (1-a)*b], axis=-1).reshape(-1, 3)
    weights = (2*w[:, None]*w[None, :]*(1-a)).ravel()
    points = np.einsum('qi,tij->tqj', bary, mesh.nodes[mesh.triangles])
    exact = layered_slab(points.reshape(-1, 2), **EXACT,
                         layer=np.repeat(layer_of[mesh.regions], len(weights)))
    th = np.einsum('qi,ti->tq', bary, result.temperature[mesh.triangles])
    weight = mesh.areas()[:, None]*weights[None, :]
    dt = th-exact.temperature.reshape(th.shape)
    dq = result.heat_flux[:, None, :]-exact.heat_flux.reshape(*th.shape, 2)
    return np.sqrt(np.sum(weight*dt**2)), np.sqrt(np.sum(weight[..., None]*dq**2))


@pytest.mark.slow
def test_layered_wall_document_converges_to_the_exact_series_wall():
    t_err, q_err = [], []
    for size in (2., 1., .5, .25):
        r = run(Document.from_dict(wall(size)), verbose=False)
        assert set(r.mesh.region_names) == {'steel_plate', 'background'}
        a, b = _errors(r)
        t_err.append(a)
        q_err.append(b)
        assert r.diagnostics['relative_conservation_residual'] < 1e-10
    t_orders = np.log2(np.array(t_err[:-1])/np.array(t_err[1:]))
    q_orders = np.log2(np.array(q_err[:-1])/np.array(q_err[1:]))
    print('region wall T L2', t_err, t_orders, 'q L2', q_err, q_orders)
    assert np.all(t_orders[-2:] >= 1.8)
    assert np.all(q_orders[-2:] >= .9)


def test_length_unit_changes_only_the_document_numbers():
    """Canonical meshing makes the SI mesh and solution independent of units."""
    reference = run(Document.from_dict(wall()), verbose=False)
    for unit, scale in (('mm', 1.), ('m', 1e-3), ('um', 1e3), ('nm', 1e6)):
        result = run(Document.from_dict(wall(1., unit, scale)), verbose=False)
        np.testing.assert_array_equal(result.mesh.nodes, reference.mesh.nodes)
        np.testing.assert_array_equal(result.mesh.triangles, reference.mesh.triangles)
        np.testing.assert_array_equal(result.temperature, reference.temperature)
        np.testing.assert_array_equal(result.heat_flux, reference.heat_flux)
        t, q = _errors(result)
        assert t < 1.1e-6 and q < .25


def test_region_document_equals_a_direct_engine_call_and_balances_heat():
    from galerkin.thermal import solve_steady_heat
    data = copy.deepcopy(examples.EXAMPLES['thermal_regions'])
    r = run(Document.from_dict(data), verbose=False)
    mesh = r.mesh
    k = {'plate': 45., 'heater': 400., 'background': .04}
    q = {'plate': 0., 'heater': 5e6, 'background': 0.}
    bc = {int(i): 300. for i in mesh.boundary['bottom']}
    direct = solve_steady_heat(mesh, conductivity=k, heat_source=q, dirichlet=dict(sorted(bc.items())),
                               convection={'top': (10., 295.)})
    np.testing.assert_array_equal(r.temperature, direct.temperature)
    np.testing.assert_array_equal(r.reaction_heat_rate_per_depth, direct.reaction)
    heater = mesh.regions == mesh.region_names.index('heater')
    np.testing.assert_allclose(r.diagnostics['generated_heat_rate_per_depth'], 5e6*mesh.areas()[heater].sum(), rtol=1e-12)
    # Inscribed polygon of the 2 mm circle: area within the O(h^2) chord error.
    assert abs(mesh.areas()[heater].sum()/(np.pi*4e-6)-1) < .01
    assert r.diagnostics['relative_conservation_residual'] < 1e-10
    # The heater is the hottest region and every heat path leaves through the bottom or top.
    centroid_t = r.temperature[mesh.triangles].mean(axis=1)
    assert centroid_t[heater].max() == centroid_t.max()
    np.testing.assert_allclose(r.diagnostics['outward_heat_rate_per_depth'], r.diagnostics['generated_heat_rate_per_depth'],
                               rtol=1e-10)


def test_saved_fields_summary_and_model(tmp_path):
    doc = Document.from_dict(examples.EXAMPLES['thermal_regions'])
    r = run(doc, verbose=False)
    out = r.save(tmp_path/'out')
    with np.load(out/'fields.npz', allow_pickle=False) as f:
        assert str(f['result_format']) == 'thermal.steady2d-regions-result-v2'
        assert str(f['field_layout']) == 'thermal2d-p1-node-cell-regions-v2'
        regions = f['triangle_regions']
        assert regions.dtype.kind == 'i' and regions.shape == (len(f['triangles']),)
        np.testing.assert_array_equal(regions, r.mesh.regions)
        for key in ('outward_prescribed_heat_rate_per_depth', 'outward_convective_heat_rate_per_depth',
                    'applied_heat_rate_per_depth'):
            assert f[key].shape == f['temperature'].shape
        meta = json.loads(str(f['metadata_json']))
    summary = json.loads((out/'summary.json').read_text())
    assert summary == meta
    assert summary['region_names'] == r.mesh.region_names
    assert summary['regions']['heater']['material'] == 'copper'
    assert summary['materials'] == {m: {'thermal_conductivity': {'value': v, 'unit': 'W/(m K)'},
                                        'source': 'document value'}
                                    for m, v in (('steel', 45.), ('copper', 400.), ('insulation', .04))}
    assert summary['minimum_thermal_conductivity'] == {'value': .04, 'unit': 'W/(m K)'}
    assert summary['maximum_thermal_conductivity'] == {'value': 400., 'unit': 'W/(m K)'}
    assert 'triangle_regions' not in summary['field_units'] and summary['field_locations']['triangle_regions'] == 'triangles'
    assert sum(v['area']['value'] for v in summary['regions'].values()) == pytest.approx(.04*.02, rel=1e-12)
    assert json.loads((out/'model.json').read_text()) == examples.EXAMPLES['thermal_regions']


def test_cli_validates_and_runs_the_shipped_example(tmp_path, capsys):
    path = tmp_path/'regions.json'
    path.write_text(json.dumps(examples.EXAMPLES['thermal_regions']))
    assert main(['validate', str(path)]) == 0
    assert 'named material regions' in capsys.readouterr().out
    assert main(['run', str(path), '-q', '-o', str(tmp_path/'out')]) == 0
    assert (tmp_path/'out'/'fields.npz').exists()
    assert main(['run', str(path), '-q', '-o', str(tmp_path/'out')]) == 1


def _bad(change):
    data = wall(2.)
    change(data)
    return data


#: case -> (change, code, path) of the refusal (format 0.3 names)
INVALID = {
    'conductivity in physics': (lambda d: d['physics']['heat1'].update(thermal_conductivity='1 W/(m K)'),
                                'E-CONTRACT', 'physics.heat1.thermal_conductivity'),
    'undefined material': (lambda d: d['geometry']['shapes'][0].update(material='aluminium'),
                           'E-MATERIAL-UNKNOWN', 'geometry.shapes[0].material'),
    'material without conductivity': (lambda d: d['materials']['steel'].pop('thermal_conductivity'),
                                      'E-PROPERTY-MISSING', 'materials.steel.thermal_conductivity'),
    'optical key in material': (lambda d: d['materials']['steel'].update(n=1.5), 'E-KEY-UNKNOWN',
                                'materials.steel.n'),
    'nonpositive conductivity': (lambda d: d['materials']['steel'].update(thermal_conductivity='0 W/(m K)'),
                                 'E-DOMAIN', 'materials.steel.thermal_conductivity'),
    'unknown source region': (lambda d: d['physics']['heat1'].update(heat_source_density={'core': '1 W/m^3'}),
                              'E-SELECTION-UNKNOWN', 'physics.heat1.heat_source_density.core'),
    'subdivisions': (lambda d: d['mesh'].update(subdivision_count=[4, 4]), 'E-KEY-UNKNOWN',
                     'mesh.subdivision_count'),
    'missing mesh size': (lambda d: d['mesh'].pop('element_size'), 'E-KEY-MISSING', 'mesh.element_size'),
    'reserved name': (lambda d: d['geometry']['shapes'][0].update(name='background'), 'E-ID-CLASH',
                      'geometry.shapes[0].name'),
    'duplicate name': (lambda d: d['geometry']['shapes'].append(dict(d['geometry']['shapes'][0])), 'E-ID-CLASH',
                       'geometry.shapes[1].name'),
    'self-intersecting polygon': (lambda d: d['geometry']['shapes'].append(
        {'name': 'bow', 'type': 'polygon', 'points': [[0, 0], [2, 2], [2, 0], [0, 2]], 'material': 'steel'}),
        'E-CONTRACT', 'geometry.shapes[1].points'),
    'corner conflict': (lambda d: d['physics']['heat1']['prescribed_temperature'].update(top='350 K'),
                        'E-CONTRACT', 'physics.heat1.prescribed_temperature.top'),
    'pure Neumann': (lambda d: d['physics']['heat1'].update(prescribed_temperature={},
                                                           inward_heat_flux={'left': '1 W/m^2'}),
                     'E-KEY-MISSING', 'physics.heat1.prescribed_temperature'),
    'natural on prescribed side': (lambda d: d['physics']['heat1'].update(inward_heat_flux={'left': '1 W/m^2'}),
                                   'E-CONTRACT', 'physics.heat1.left'),
    'plots': (lambda d: d['results'].update(plots=True), 'E-CONTRACT', 'results.plots'),
    'sweep': (lambda d: d.update(study={'type': 'sweep'}), 'E-CONTRACT', 'study.type'),
    'shape key': (lambda d: d['geometry']['shapes'][0].update(depth=1.), 'E-KEY-UNKNOWN',
                  'geometry.shapes[0].depth'),
    'min angle': (lambda d: d['mesh'].update(minimum_angle='40 deg'), 'E-DOMAIN', 'mesh.minimum_angle'),
    'bare temperature': (lambda d: d['physics']['heat1']['prescribed_temperature'].update(left=400),
                         'E-UNIT-MISSING', 'physics.heat1.prescribed_temperature.left'),
}


@pytest.mark.parametrize('case', sorted(INVALID))
def test_invalid_region_documents_are_refused(case):
    change, code, path = INVALID[case]
    with pytest.raises(DocumentError) as refused:
        Document.from_dict(_bad(change))
    found = refused.value.diagnostics or [refused.value]
    assert (code, path) in [(d.code, d.path) for d in found], [(d.code, d.path, str(d)) for d in found]


def test_source_on_a_fully_covered_region_is_refused_at_meshing():
    data = wall(2.)
    data['geometry']['shapes'].append({'name': 'cover', 'type': 'rect', 'x': -1., 'y': -1., 'w': 12., 'h': 7.,
                                       'material': 'insulation'})
    with pytest.raises(DocumentError, match='not in the meshed geometry'):
        run(Document.from_dict(data), verbose=False)


@pytest.mark.parametrize('shape', [
    {'name': 'spreader', 'type': 'rect', 'x': 5., 'y': 11000., 'w': 30., 'h': 1., 'material': 'steel'},
    {'name': 'speck', 'type': 'circle', 'cx': 15., 'cy': 2., 'r': 1e-6, 'material': 'steel'}])
def test_a_named_shape_that_contributes_no_material_is_refused(shape):
    """Outside the domain or below the sliver limit: refused, never dropped silently."""
    data = wall(2.)
    data['geometry']['shapes'].append(shape)
    with pytest.raises(DocumentError, match=f"{shape['name']}.*refuses a shape"):
        Document.from_dict(data)


def test_a_fully_covered_shape_is_named_in_the_log():
    data = wall(2.)
    data['geometry']['shapes'] += [
        {'name': 'hidden', 'type': 'rect', 'x': 2., 'y': 1., 'w': 2., 'h': 2., 'material': 'insulation'},
        {'name': 'cover', 'type': 'rect', 'x': 1., 'y': .5, 'w': 4., 'h': 3., 'material': 'steel'}]
    data['physics']['heat1']['heat_source_density'] = {'steel_plate': '2e5 W/m^3', 'cover': '2e5 W/m^3'}
    r = run(Document.from_dict(data), verbose=False)
    assert 'hidden' not in r.mesh.region_names
    assert "shapes fully covered by later shapes (no triangles): ['hidden']" in r.log


STRADDLE = """
import copy, json, sys
import simcase
from simcase import Document, examples, run
from simcase.geometry import resolve_regions
from simcase.thermal_regions import handoff_03
d = copy.deepcopy(examples.EXAMPLES['thermal_regions'])
d['geometry']['shapes'][1]['cy'] = 11.0          # heater crosses the plate's top edge
doc = Document.from_dict(d)
exact = [name for name, *_, circle in resolve_regions(handoff_03(doc.copy())) if circle]
r = run(doc, verbose=False)
print(json.dumps({'exact': exact, 'regions': r.mesh.region_names, 'simcase': simcase.__file__,
                  'balance': r.summary()['relative_conservation_residual']['value']}))
"""


def test_a_circle_across_another_shape_s_edge_meshes():
    """Regression: the exact circle did not coincide with the neighbours' arcs and
    refinement never finished. Run in a subprocess so a regression cannot hang the suite."""
    import os
    import pathlib
    import subprocess
    import sys
    import galerkin
    import meshine
    import physmat
    import simcase
    # The child must import the code under test, which the parent may have from sys.path
    # (conftest) rather than from an installation.
    roots = [str(pathlib.Path(m.__file__).resolve().parents[1]) for m in (simcase, galerkin, meshine, physmat)]
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join(roots+([env['PYTHONPATH']] if env.get('PYTHONPATH') else []))
    out = subprocess.run([sys.executable, '-c', STRADDLE], capture_output=True, text=True, timeout=300,
                         env=env, check=True)
    result = json.loads(out.stdout.strip().splitlines()[-1])
    assert pathlib.Path(result['simcase']).resolve() == pathlib.Path(simcase.__file__).resolve()
    assert result['exact'] == []
    assert result['regions'] == ['plate', 'heater', 'background']
    assert result['balance'] < 1e-10


SMALL_ANGLE = """
import copy, json, sys, time
import meshine, simcase
from simcase import Document, examples
from simcase.thermal_regions import build_region_mesh_03
d = copy.deepcopy(examples.EXAMPLES['thermal_regions'])
next(s for s in d['geometry']['shapes'] if s['name'] == 'heater')['cy'] = float(sys.argv[1])
start = time.perf_counter()
tri = build_region_mesh_03(Document.from_dict(d))[2]
seconds = time.perf_counter()-start
print(json.dumps({'seconds': seconds, 'tags': sorted(tri.boundary_edges), 'min_angle': tri.min_angle(),
                  'areas': {n: tri.region_area(n) for n in tri.region_names},
                  'simcase': simcase.__file__, 'meshine': meshine.__file__}))
"""


@pytest.mark.parametrize('cy,area_tol', [(2., 1e-9), (1.9, 1e-9), (1.638304, 1e-9), (1.414214, 1e-8),
                                         (13., 1e-9), (12.9, 1e-9), (12.414214, 1e-8)])
def test_a_heater_that_touches_or_crosses_an_edge_at_a_small_angle_meshes(cy, area_tol):
    """The heater (r = 2) tangent to the bottom side (cy = 2) or to the plate's top edge
    (cy = 13), or crossing the side at 18, 35 and 45 degrees and the edge at 18 and 45
    degrees. Refinement never finished on any of them; the pass criteria were fixed
    before the fix, from a prototype (measured: at most 0.8 s; the 45-degree crossings
    lose a clipped edge of 1.4e-8 of the diagonal, an area change of 3.1e-9). The angle
    reference is the smallest angle between two edges of the input meshine is given, or
    the 28-degree bound where that angle is larger. Run in a subprocess so a regression
    cannot hang the suite."""
    import os
    import pathlib
    import subprocess
    import sys
    import galerkin
    import meshine
    import physmat
    import simcase
    from simcase.geometry import build_domain, resolve_regions
    roots = [str(pathlib.Path(m.__file__).resolve().parents[1]) for m in (simcase, galerkin, meshine, physmat)]
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join(roots+([env['PYTHONPATH']] if env.get('PYTHONPATH') else []))
    try:
        out = subprocess.run([sys.executable, '-c', SMALL_ANGLE, repr(cy)], capture_output=True, text=True,
                             timeout=120, env=env)
    except subprocess.TimeoutExpired:
        pytest.fail(f'heater at cy={cy}: meshing did not finish in 120 s')
    assert out.returncode == 0, out.stderr
    result = json.loads(out.stdout.strip().splitlines()[-1])
    assert pathlib.Path(result['meshine']).resolve() == pathlib.Path(meshine.__file__).resolve()
    assert result['seconds'] < 10.
    assert result['tags'] == ['bottom', 'left', 'right', 'top']

    d = copy.deepcopy(examples.EXAMPLES['thermal_regions'])
    next(s for s in d['geometry']['shapes'] if s['name'] == 'heater')['cy'] = cy
    exact = {}
    for name, _material, geom, *_ in resolve_regions(handoff(d)):
        exact[name] = exact.get(name, 0.)+geom.area
    assert set(result['areas']) == set(exact)
    for name, area in exact.items():
        assert abs(result['areas'][name]-area) <= area_tol, name
    domain, namer, _ = build_domain(handoff(d))
    points, segments, _ = domain.build(namer)
    around = {}
    for s in segments:
        around.setdefault(s.a, []).append(s.b)
        around.setdefault(s.b, []).append(s.a)
    corner = 360.
    for v, others in around.items():
        phi = np.sort(np.degrees(np.arctan2(*(points[others]-points[v])[:, ::-1].T)))
        corner = min(corner, np.diff(np.append(phi, phi[0]+360.)).min())
    assert result['min_angle'] >= min(corner, 28.)-1e-6


def test_only_an_isolated_circle_is_meshed_as_an_exact_circle():
    from simcase.geometry import resolve_regions

    def exact(**heater):
        d = copy.deepcopy(examples.EXAMPLES['thermal_regions'])
        d['geometry']['shapes'][1].update(heater)
        return [name for name, *_, circle in resolve_regions(handoff(d)) if circle]
    assert exact() == ['heater']                      # inside the plate, clear of every edge
    assert exact(cy=2.) == []                         # tangent to the bottom side
    assert exact(cy=13.) == []                        # tangent to the plate's top edge from outside
    assert exact(cy=11.) == []                        # crosses the plate's top edge
    assert exact(cy=13.5) == ['heater']               # clear of the plate, in the background
    d = copy.deepcopy(examples.EXAMPLES['thermal_regions'])
    d['geometry']['shapes'].append({'name': 'pin', 'type': 'rect', 'x': 19.5, 'y': 7.5, 'w': 1., 'h': 1.,
                                    'material': 'steel'})
    assert [name for name, *_, c in resolve_regions(handoff(d)) if c] == []   # later shape inside


# Concave bracket: part of it overlaps the domain, part only touches the right side from
# outside, so clipping leaves a polygon plus a line piece (a GeometryCollection).
BRACKET = [[38, 2], [44, 2], [44, 10], [40, 10], [40, 6], [42, 6], [42, 4], [38, 4]]


def test_a_shape_that_clips_to_a_polygon_and_a_line_piece_meshes():
    """Regression: the line piece has no boundary ring and crashed the circle check and
    build_domain; only the polygon parts are meshed."""
    from simcase.geometry import resolve_regions
    d = copy.deepcopy(examples.EXAMPLES['thermal_regions'])
    d['geometry']['shapes'].insert(0, {'name': 'bracket', 'type': 'polygon', 'points': BRACKET,
                                       'material': 'steel'})
    doc = Document.from_dict(d)
    regions = {name: geom for name, _m, geom, *_ in resolve_regions(handoff_03(doc.copy()))}
    assert regions['bracket'].geom_type == 'Polygon' and abs(regions['bracket'].area-4.) < 1e-12
    r = run(doc, verbose=False)
    assert r.mesh.region_names == ['bracket', 'plate', 'heater', 'background']
    assert r.summary()['relative_conservation_residual']['value'] < 1e-10
    fiber = copy.deepcopy(examples.EXAMPLES['fiber'])
    dom = fiber['geometry']['domain']
    fiber['geometry']['shapes'].append({'name': 'bracket', 'type': 'polygon', 'material':
                                        fiber['geometry']['shapes'][0]['material'],
                                        'points': [[x-40+dom['xmax'], y] for x, y in BRACKET]})
    em = resolve_regions(Document.from_dict(fiber))
    assert [name for name, *_, c in em if c] == ['core']


def test_rectangle_documents_keep_their_original_contract():
    legacy = copy.deepcopy(examples.EXAMPLES['thermal_slab'])
    legacy['materials'] = {'steel': {'thermal_conductivity': '45 W/(m K)'}}
    with pytest.raises(DocumentError, match='requires an empty object'):
        Document.from_dict(legacy)
    r = run(Document.from_dict(examples.EXAMPLES['thermal_slab']), verbose=False)
    assert r.result_format == 'thermal.steady2d-result-v3'
    assert r.field_layout == 'thermal2d-p1-node-cell-v2'
    assert r.mesh.regions is None and 'triangle_regions' not in r.summary()['field_shapes']


@pytest.mark.parametrize('page', ['docs/packages/simcase/thermal_regions2d.md',
                                  'docs/locales/ko/pages/packages/simcase/thermal_regions2d.md'])
def test_the_documented_example_is_the_shipped_example(page):
    from pathlib import Path
    path = Path(__file__).resolve().parents[2]/page
    text = path.read_text(encoding='utf-8')
    block = text.split('```json\n', 1)[1].split('```', 1)[0]
    assert json.loads(block) == examples.EXAMPLES['thermal_regions']


def test_studio_validates_region_documents_without_running(monkeypatch):
    from fastapi.testclient import TestClient
    from simcase.studio import server
    def forbidden(*a, **kw):
        raise AssertionError('validating a region document must not reach the Studio worker or mesher')
    monkeypatch.setattr(server, 'run', forbidden)
    monkeypatch.setattr(server, 'build_mesh', forbidden)
    client = TestClient(server.app)
    data = examples.EXAMPLES['thermal_regions']
    assert not client.post('/api/validate', json={'doc': data}).json()['ok']
    response = client.post('/api/thermal/validate', json={'doc': data, 'client_revision': 1, 'request_seq': 1})
    assert response.status_code == 200
    body = response.json()
    assert body.get('ok') is True
    assert 'thermal_regions' not in client.get('/api/examples').json()['examples']
