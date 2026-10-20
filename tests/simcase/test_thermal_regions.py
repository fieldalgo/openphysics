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
from refsol.thermal_multilayer import layered_slab


def wall(size=1., unit='mm', scale=1.):
    """Steel plate 10 mm + insulation 20 mm, 5 mm high, Q only in the steel."""
    s = scale
    return {'openphysics': '0.2', 'name': 'layered wall', 'units': {'length': unit, 'temperature': 'K'},
            'geometry': {'domain': {'xmin': 0., 'xmax': 30.*s, 'ymin': 0., 'ymax': 5.*s},
                         'background': {'material': 'insulation'},
                         'shapes': [{'name': 'steel_plate', 'type': 'rect', 'x': 0., 'y': 0., 'w': 10.*s,
                                     'h': 5.*s, 'material': 'steel'}]},
            'materials': {'steel': {'conductivity_w_mk': 45.}, 'insulation': {'conductivity_w_mk': .5}},
            'physics': {'heat1': {'type': 'thermal.steady2d', 'heat_source_w_m3': {'steel_plate': 2e5},
                                  'dirichlet_temperature_k': {'left': 400., 'right': 300.}}},
            'mesh': {'size': size*s}, 'study': {'type': 'single'},
            'results': {'save_fields': True, 'plots': False}}


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
    th = np.einsum('qi,ti->tq', bary, result.temperature_k[mesh.triangles])
    weight = mesh.areas()[:, None]*weights[None, :]
    dt = th-exact.temperature.reshape(th.shape)
    dq = result.heat_flux_w_m2[:, None, :]-exact.heat_flux.reshape(*th.shape, 2)
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
        assert r.diagnostics['normalized_heat_balance_defect'] < 1e-10
    t_orders = np.log2(np.array(t_err[:-1])/np.array(t_err[1:]))
    q_orders = np.log2(np.array(q_err[:-1])/np.array(q_err[1:]))
    print('region wall T L2', t_err, t_orders, 'q L2', q_err, q_orders)
    assert np.all(t_orders[-2:] >= 1.8)
    assert np.all(q_orders[-2:] >= .9)


def test_length_unit_changes_only_the_document_numbers():
    """The adapter scales meshine output exactly; the mesher itself is not unit invariant.

    meshine places interior nodes differently for the same geometry written in
    mm, m or um, so the three solutions are compared through their error
    against the exact series wall rather than node for node.
    """
    from simcase.thermal_regions import build_region_mesh
    errors = {}
    for unit, scale in (('mm', 1.), ('m', 1e-3), ('um', 1e3)):
        doc = Document.from_dict(wall(1., unit, scale))
        mesh, _, tri = build_region_mesh(doc)
        np.testing.assert_array_equal(mesh.nodes, np.asarray(tri.nodes)*doc.scale.to_si(1., {'length': 1}))
        assert mesh.nodes[:, 0].max() == pytest.approx(.03, rel=1e-15)
        errors[unit] = _errors(run(doc, verbose=False))
    t = np.array([e[0] for e in errors.values()])
    q = np.array([e[1] for e in errors.values()])
    assert np.ptp(t)/t.mean() < .05 and np.ptp(q)/q.mean() < .05
    assert t.max() < 1.1e-6 and q.max() < .25


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
    np.testing.assert_array_equal(r.temperature_k, direct.temperature)
    np.testing.assert_array_equal(r.reaction_w_per_m, direct.reaction)
    heater = mesh.regions == mesh.region_names.index('heater')
    np.testing.assert_allclose(r.diagnostics['source_heat_w_per_m'], 5e6*mesh.areas()[heater].sum(), rtol=1e-12)
    # Inscribed polygon of the 2 mm circle: area within the O(h^2) chord error.
    assert abs(mesh.areas()[heater].sum()/(np.pi*4e-6)-1) < .01
    assert r.diagnostics['normalized_heat_balance_defect'] < 1e-10
    # The heater is the hottest region and every heat path leaves through the bottom or top.
    centroid_t = r.temperature_k[mesh.triangles].mean(axis=1)
    assert centroid_t[heater].max() == centroid_t.max()
    np.testing.assert_allclose(r.diagnostics['outward_heat_w_per_m'], r.diagnostics['source_heat_w_per_m'],
                               rtol=1e-10)


def test_saved_fields_summary_and_model(tmp_path):
    doc = Document.from_dict(examples.EXAMPLES['thermal_regions'])
    r = run(doc, verbose=False)
    out = r.save(tmp_path/'out')
    with np.load(out/'fields.npz', allow_pickle=False) as f:
        assert str(f['result_format']) == 'thermal.steady2d-regions-result-v1'
        assert str(f['field_layout']) == 'thermal2d-p1-node-cell-regions-v1'
        regions = f['triangle_regions']
        assert regions.dtype.kind == 'i' and regions.shape == (len(f['triangles']),)
        np.testing.assert_array_equal(regions, r.mesh.regions)
        for key in ('prescribed_outward_load_w_per_m', 'convective_outward_w_per_m', 'system_rhs_w_per_m'):
            assert f[key].shape == f['temperature_k'].shape
        meta = json.loads(str(f['metadata_json']))
    summary = json.loads((out/'summary.json').read_text())
    assert summary == meta
    assert summary['region_names'] == r.mesh.region_names
    assert summary['regions']['heater']['material'] == 'copper'
    assert summary['materials'] == doc['materials']
    assert summary['conductivity_range_w_mk'] == [.04, 400.]
    assert summary['field_units']['triangle_regions'] == '1'
    assert sum(v['area_m2'] for v in summary['regions'].values()) == pytest.approx(.04*.02, rel=1e-12)
    assert json.loads((out/'model.json').read_text()) == doc.data


def test_vtu_export_refuses_the_region_layout(tmp_path):
    """Documented limit: the export does not take region layouts yet (checked before meshio loads)."""
    from simcase.export import export_fields
    out = run(Document.from_dict(examples.EXAMPLES['thermal_regions']), verbose=False).save(tmp_path/'out')
    with pytest.raises(ValueError, match='unsupported field layout'):
        export_fields(out/'fields.npz', tmp_path/'fields.vtu')
    assert not (tmp_path/'fields.vtu').exists()


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


INVALID = {
    'conductivity in physics': lambda d: d['physics']['heat1'].update(conductivity_w_mk=1.),
    'undefined material': lambda d: d['geometry']['shapes'][0].update(material='aluminium'),
    'material without conductivity': lambda d: d['materials']['steel'].pop('conductivity_w_mk'),
    'optical key in material': lambda d: d['materials']['steel'].update(n=1.5),
    'nonpositive conductivity': lambda d: d['materials']['steel'].update(conductivity_w_mk=0.),
    'unknown source region': lambda d: d['physics']['heat1'].update(heat_source_w_m3={'core': 1.}),
    'subdivisions': lambda d: d['mesh'].update(subdivisions=[4, 4]),
    'missing mesh size': lambda d: d['mesh'].pop('size'),
    'reserved name': lambda d: d['geometry']['shapes'][0].update(name='background'),
    'duplicate name': lambda d: d['geometry']['shapes'].append(dict(d['geometry']['shapes'][0])),
    'self-intersecting polygon': lambda d: d['geometry']['shapes'].append(
        {'name': 'bow', 'type': 'polygon', 'points': [[0, 0], [2, 2], [2, 0], [0, 2]], 'material': 'steel'}),
    'corner conflict': lambda d: d['physics']['heat1']['dirichlet_temperature_k'].update(top=350.),
    'pure Neumann': lambda d: d['physics']['heat1'].update(dirichlet_temperature_k={}, outward_flux_w_m2={'left': 1.}),
    'natural on Dirichlet side': lambda d: d['physics']['heat1'].update(outward_flux_w_m2={'left': 1.}),
    'plots': lambda d: d['results'].update(plots=True),
    'sweep': lambda d: d.update(study={'type': 'sweep'}),
    'shape key': lambda d: d['geometry']['shapes'][0].update(depth=1.),
    'min angle': lambda d: d['mesh'].update(min_angle=40.),
    'no temperature unit': lambda d: d['units'].pop('temperature'),
}


@pytest.mark.parametrize('case', sorted(INVALID))
def test_invalid_region_documents_are_refused(case):
    with pytest.raises(DocumentError):
        Document.from_dict(_bad(INVALID[case]))


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
    data['physics']['heat1']['heat_source_w_m3'] = {'steel_plate': 2e5, 'cover': 2e5}
    r = run(Document.from_dict(data), verbose=False)
    assert 'hidden' not in r.mesh.region_names
    assert "shapes fully covered by later shapes (no triangles): ['hidden']" in r.log


STRADDLE = """
import copy, json, sys
import simcase
from simcase import Document, examples, run
from simcase.geometry import resolve_regions
d = copy.deepcopy(examples.EXAMPLES['thermal_regions'])
d['geometry']['shapes'][1]['cy'] = 11.0          # heater crosses the plate's top edge
doc = Document.from_dict(d)
exact = [name for name, *_, circle in resolve_regions(doc.copy()) if circle]
r = run(doc, verbose=False)
print(json.dumps({'exact': exact, 'regions': r.mesh.region_names, 'simcase': simcase.__file__,
                  'balance': r.summary()['normalized_heat_balance_defect']}))
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
from simcase.thermal_regions import build_region_mesh
d = copy.deepcopy(examples.EXAMPLES['thermal_regions'])
next(s for s in d['geometry']['shapes'] if s['name'] == 'heater')['cy'] = float(sys.argv[1])
start = time.perf_counter()
tri = build_region_mesh(Document.from_dict(d))[2]
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
    for name, _material, geom, *_ in resolve_regions(Document.from_dict(d)):
        exact[name] = exact.get(name, 0.)+geom.area
    assert set(result['areas']) == set(exact)
    for name, area in exact.items():
        assert abs(result['areas'][name]-area) <= area_tol, name
    domain, namer, _ = build_domain(Document.from_dict(d))
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
        return [name for name, *_, circle in resolve_regions(Document.from_dict(d)) if circle]
    assert exact() == ['heater']                      # inside the plate, clear of every edge
    assert exact(cy=2.) == []                         # tangent to the bottom side
    assert exact(cy=13.) == []                        # tangent to the plate's top edge from outside
    assert exact(cy=11.) == []                        # crosses the plate's top edge
    assert exact(cy=13.5) == ['heater']               # clear of the plate, in the background
    d = copy.deepcopy(examples.EXAMPLES['thermal_regions'])
    d['geometry']['shapes'].append({'name': 'pin', 'type': 'rect', 'x': 19.5, 'y': 7.5, 'w': 1., 'h': 1.,
                                    'material': 'steel'})
    assert [name for name, *_, c in resolve_regions(Document.from_dict(d)) if c] == []   # later shape inside


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
    regions = {name: geom for name, _m, geom, *_ in resolve_regions(doc.copy())}
    assert regions['bracket'].geom_type == 'Polygon' and abs(regions['bracket'].area-4.) < 1e-12
    r = run(doc, verbose=False)
    assert r.mesh.region_names == ['bracket', 'plate', 'heater', 'background']
    assert r.summary()['normalized_heat_balance_defect'] < 1e-10
    fiber = copy.deepcopy(examples.EXAMPLES['fiber'])
    dom = fiber['geometry']['domain']
    fiber['geometry']['shapes'].append({'name': 'bracket', 'type': 'polygon', 'material':
                                        fiber['geometry']['shapes'][0]['material'],
                                        'points': [[x-40+dom['xmax'], y] for x, y in BRACKET]})
    em = resolve_regions(Document.from_dict(fiber))
    assert [name for name, *_, c in em if c] == ['core']


def test_rectangle_documents_keep_their_original_contract():
    legacy = copy.deepcopy(examples.EXAMPLES['thermal_slab'])
    legacy['materials'] = {'steel': {'conductivity_w_mk': 45.}}
    with pytest.raises(DocumentError, match='requires an empty object'):
        Document.from_dict(legacy)
    r = run(Document.from_dict(examples.EXAMPLES['thermal_slab']), verbose=False)
    assert r.result_format == 'thermal.steady2d-result-v1'
    assert r.field_layout == 'thermal2d-p1-node-cell-v1'
    assert r.mesh.regions is None and 'triangle_regions' not in r.summary()['field_shapes']


@pytest.mark.parametrize('page', ['docs/packages/simcase/thermal_regions2d.md',
                                  'docs/locales/ko/pages/packages/simcase/thermal_regions2d.md'])
def test_the_documented_example_is_the_shipped_example(page):
    from pathlib import Path
    path = Path(__file__).resolve().parents[2]/page
    text = path.read_text(encoding='utf-8')
    block = text.split('```json\n', 1)[1].split('```', 1)[0]
    assert json.loads(block) == examples.EXAMPLES['thermal_regions']


def test_studio_refuses_region_documents_without_running(monkeypatch):
    from fastapi.testclient import TestClient
    from simcase.studio import server
    def forbidden(*a, **kw):
        raise AssertionError('region documents must not reach the Studio worker or mesher')
    monkeypatch.setattr(server, 'run', forbidden)
    monkeypatch.setattr(server, 'build_mesh', forbidden)
    client = TestClient(server.app)
    data = examples.EXAMPLES['thermal_regions']
    assert not client.post('/api/validate', json={'doc': data}).json()['ok']
    response = client.post('/api/thermal/validate', json={'doc': data, 'client_revision': 1, 'request_seq': 1})
    assert response.status_code in (200, 400)
    body = response.json()
    assert body.get('ok') is not True
    assert 'thermal_regions' not in client.get('/api/examples').json()['examples']
