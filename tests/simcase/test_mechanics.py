# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Pre-registered gates of the ``mechanics.elasticity2d`` document (docs/packages/simcase/mechanics2d.md).

J1 document run == direct ``solve_elasticity`` on the same mesh (byte-identical arrays);
J2 refsol uniaxial and shear fields across length units; J3 mesh convergence of a
constant-body-force manufactured solution; J4 invalid documents refused without output;
J5 CLI validate/run/save, fresh output, partial-save cleanup and snapshot immutability;
J6 Studio rejects the type. Thresholds are gates: never loosen them.
"""
import copy
import json

import numpy as np
import pytest

from simcase import Document, DocumentError, MechanicsRunResult, run, build_mesh, solve_point, examples
from simcase.cli import main
from simcase import mechanics
from galerkin import rectangle_mesh
from galerkin.elasticity import lame, solve_elasticity
from refsol import elasticity_traction as refsol

UNITS = [('m', 1.), ('mm', 1e3), ('um', 1e6), ('nm', 1e9)]


def data():
    return copy.deepcopy(examples.EXAMPLES['elastic_plate'])


def document(unit='m', factor=1., *, plane='stress', nu=.3, size=(1., .4), subdivisions=(10, 4),
             displacement, traction=None, body_force=None, young=2e11):
    d = data()
    d['units']['length'] = unit
    d['geometry']['domain'] = dict(xmin=0., xmax=size[0]*factor, ymin=0., ymax=size[1]*factor)
    d['mesh']['subdivisions'] = list(subdivisions)
    p = d['physics']['plate']
    p.update(plane=plane, poisson_ratio=nu, young_modulus_pa=young, displacement_m=displacement)
    p.pop('traction_pa', None)
    if traction is not None:
        p['traction_pa'] = traction
    if body_force is not None:
        p['body_force_n_m3'] = body_force
    return d


def relative(approx, exact, scale):
    return float(np.max(abs(np.asarray(approx)-np.asarray(exact)))/scale)


# J1 ------------------------------------------------------------------------------------------

@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_j1_document_run_matches_direct_solve_byte_for_byte(plane):
    d = document('mm', 1e3, plane=plane, displacement={'left': {'x': 0.}, 'bottom': {'y': 0.}},
                 traction={'right': [3e6, 0.], 'top': [0., -1e5]}, body_force=[0., -7.7e4])
    d['geometry']['domain'] = dict(xmin=-500., xmax=500., ymin=100., ymax=500.)
    doc = Document.from_dict(d)
    result = run(doc, verbose=False)
    assert isinstance(result, MechanicsRunResult)
    mesh = rectangle_mesh(1., .4, 10, 4)
    mesh.nodes += [-.5, .1]
    fixed = {}
    for side, component in (('left', 0), ('bottom', 1)):
        for node in mesh.boundary[side]:
            fixed[int(node), component] = 0.
    direct = solve_elasticity(mesh, young_modulus=2e11, poisson_ratio=.3, plane=plane,
                              dirichlet=dict(sorted(fixed.items())), body_force=(0., -7.7e4),
                              traction={'right': [3e6, 0.], 'top': [0., -1e5]})
    f = result.fields
    assert f['nodes_m'].tobytes() == mesh.nodes.tobytes()
    assert f['triangles'].tobytes() == mesh.triangles.tobytes()
    for key, attr in (('displacement_m', 'displacement'), ('strain', 'strain'), ('stress_pa', 'stress'),
                      ('load_n_per_m', 'load'), ('reaction_n_per_m', 'reaction'), ('residual_n_per_m', 'residual')):
        value = np.asarray(getattr(direct, attr))
        assert f[key].shape == value.shape and f[key].dtype == value.dtype, key
        assert f[key].tobytes() == value.tobytes(), key
    summary = result.summary()
    assert summary['result_format'] == 'mechanics.elasticity2d-result-v1'
    assert summary['field_layout'] == 'mechanics2d-p1-v1'
    assert summary['strain_components'] == ['exx', 'eyy', 'gxy']
    assert summary['stress_components'] == ['sxx', 'syy', 'sxy']
    assert summary['field_units']['stress_pa'] == 'Pa' and summary['field_units']['load_n_per_m'] == 'N/m'
    assert summary['field_locations']['displacement_m'] == 'nodes'
    assert summary['field_shapes']['strain'] == [mesh.num_triangles, 3]
    assert summary['status'] == 'solved'


# J2 ------------------------------------------------------------------------------------------

@pytest.mark.parametrize('plane', ['stress', 'strain'])
@pytest.mark.parametrize('unit, factor', UNITS)
def test_j2_uniaxial_refsol_across_length_units(unit, factor, plane):
    applied = 5e6
    d = document(unit, factor, plane=plane, displacement={'left': {'x': 0.}, 'bottom': {'y': 0.}},
                 traction={'right': [applied, 0.]})
    r = run(Document.from_dict(d), verbose=False)
    f = r.fields
    exact = refsol.uniaxial(f['nodes_m'], applied, young_modulus=2e11, poisson_ratio=.3, plane=plane)
    centroids = f['nodes_m'][f['triangles']].mean(axis=1)
    exact_cells = refsol.uniaxial(centroids, applied, young_modulus=2e11, poisson_ratio=.3, plane=plane)
    du = relative(f['displacement_m'], exact.displacement, np.max(abs(exact.displacement)))
    ds = relative(f['stress_pa'], exact_cells.stress, applied)
    de = relative(f['strain'], exact_cells.strain, np.max(abs(exact_cells.strain)))
    print(dict(unit=unit, plane=plane, displacement_relative=du, stress_relative=ds, strain_relative=de))
    assert du <= 1e-10 and ds <= 1e-10 and de <= 1e-10
    diag = r.summary()['diagnostics']
    assert diag['applied_load_n_per_m'] == pytest.approx([applied*.4, 0.], rel=1e-12, abs=1e-12*applied*.4)
    assert np.max(abs(np.asarray(diag['force_balance_n_per_m']))) <= 1e-10*applied*.4
    assert r.summary()['input_units'] == {'length': unit}


@pytest.mark.parametrize('plane', ['stress', 'strain'])
@pytest.mark.parametrize('unit, factor', UNITS)
def test_j2_shear_refsol_across_length_units(unit, factor, plane):
    tau = 2e6
    d = document(unit, factor, plane=plane, displacement={'bottom': {'x': 0., 'y': 0.}},
                 traction={'top': [tau, 0.], 'left': [0., -tau], 'right': [0., tau]})
    r = run(Document.from_dict(d), verbose=False)
    f = r.fields
    exact = refsol.shear(f['nodes_m'], tau, young_modulus=2e11, poisson_ratio=.3, plane=plane)
    centroids = f['nodes_m'][f['triangles']].mean(axis=1)
    exact_cells = refsol.shear(centroids, tau, young_modulus=2e11, poisson_ratio=.3, plane=plane)
    du = relative(f['displacement_m'], exact.displacement, np.max(abs(exact.displacement)))
    ds = relative(f['stress_pa'], exact_cells.stress, tau)
    print(dict(unit=unit, plane=plane, displacement_relative=du, stress_relative=ds))
    assert du <= 1e-10 and ds <= 1e-10


# J3 ------------------------------------------------------------------------------------------

@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_j3_constant_body_force_bar_mesh_convergence(plane):
    """Confined bar: u = (f/(lam+2mu)) (L x - x^2/2, 0) for body force (f, 0), x and y fixed at
    x=0, y fixed on bottom and top, free right end. Then exx = f (L-x)/(lam+2mu), eyy = gxy = 0,
    sxx = f (L-x), syy = lam exx, sxy = 0; the Navier equation and every side condition hold
    exactly. The quadratic displacement is outside the P1 space, so the centroid displacement
    error must fall as h^2 (gate: order >= 1.8) and the element stress error as h."""
    e, nu, f, length = 2e11, .3, 5e9, 1.
    lam, mu = lame(e, nu, plane)
    errors, stress_errors = [], []
    for n in (8, 16, 32):
        d = document('m', 1., plane=plane, nu=nu, young=e, size=(length, .25), subdivisions=(n, max(2, n//4)),
                     displacement={'left': {'x': 0., 'y': 0.}, 'bottom': {'y': 0.}, 'top': {'y': 0.}},
                     body_force=[f, 0.])
        r = run(Document.from_dict(d), verbose=False)
        fields = r.fields
        x = fields['nodes_m'][fields['triangles']].mean(axis=1)[:, 0]
        exact = np.column_stack([f/(lam+2*mu)*(length*x-x*x/2), np.zeros_like(x)])
        approx = fields['displacement_m'][fields['triangles']].mean(axis=1)
        errors.append(float(np.sqrt(np.mean(np.sum((approx-exact)**2, axis=1)))))
        exact_stress = np.column_stack([f*(length-x), lam/(lam+2*mu)*f*(length-x), np.zeros_like(x)])
        stress_errors.append(float(np.sqrt(np.mean(np.sum((fields['stress_pa']-exact_stress)**2, axis=1))))/(f*length))
    orders = [float(np.log2(errors[i]/errors[i+1])) for i in range(2)]
    stress_orders = [float(np.log2(stress_errors[i]/stress_errors[i+1])) for i in range(2)]
    print(dict(plane=plane, rms_displacement_errors_m=errors, displacement_orders=orders,
               rms_stress_errors_relative=stress_errors, stress_orders=stress_orders))
    assert min(orders) >= 1.8
    assert min(stress_orders) >= .9


# J4 ------------------------------------------------------------------------------------------

INVALID = {
    'hinge': (('physics', 'plate', 'displacement_m'), {'bottom': {'x': 0.}, 'left': {'y': 0.}}),
    'x_only': (('physics', 'plate', 'displacement_m'), {'left': {'x': 0.}}),
    'y_only': (('physics', 'plate', 'displacement_m'), {'bottom': {'y': 0.}, 'top': {'y': 0.}}),
    'hinge_right': (('physics', 'plate', 'displacement_m'), {'bottom': {'x': 0.}, 'right': {'y': 0.}}),
    'no_sides': (('physics', 'plate', 'displacement_m'), {}),
    'empty_side': (('physics', 'plate', 'displacement_m'), {'left': {}, 'bottom': {'y': 0.}}),
    'corner_conflict': (('physics', 'plate', 'displacement_m'), {'left': {'x': 0.}, 'bottom': {'x': 1e-3, 'y': 0.}}),
    'unknown_component': (('physics', 'plate', 'displacement_m'), {'left': {'x': 0., 'z': 0.}, 'bottom': {'y': 0.}}),
    'boolean_value': (('physics', 'plate', 'displacement_m'), {'left': {'x': False}, 'bottom': {'y': 0.}}),
    'missing_units': (('units',), {}),
    'temperature_unit': (('units', 'temperature'), 'K'),
    'unknown_length_unit': (('units', 'length'), 'parsec'),
    'bad_plane': (('physics', 'plate', 'plane'), 'axisymmetric'),
    'poisson_half': (('physics', 'plate', 'poisson_ratio'), .5),
    'poisson_minus_one': (('physics', 'plate', 'poisson_ratio'), -1.),
    'poisson_nan': (('physics', 'plate', 'poisson_ratio'), float('nan')),
    'zero_modulus': (('physics', 'plate', 'young_modulus_pa'), 0.),
    'body_force_scalar': (('physics', 'plate', 'body_force_n_m3'), 1.),
    'body_force_length': (('physics', 'plate', 'body_force_n_m3'), [1., 2., 3.]),
    'traction_scalar': (('physics', 'plate', 'traction_pa'), {'right': 1e6}),
    'traction_unknown_side': (('physics', 'plate', 'traction_pa'), {'front': [1e6, 0.]}),
    'traction_on_fixed_component': (('physics', 'plate', 'traction_pa'), {'left': [1e6, 0.]}),
    'unknown_physics_key': (('physics', 'plate', 'thickness_m'), 1e-3),
    'missing_modulus': (('physics', 'plate', 'young_modulus_pa'), None),
    'unknown_top_key': (('mystery',), 1),
    'shapes': (('geometry', 'shapes'), []),
    'materials': (('materials', 'steel'), {}),
    'too_many_triangles': (('mesh', 'subdivisions'), [1000, 1000]),
    'boolean_subdivision': (('mesh', 'subdivisions'), [True, 2]),
    'sweep': (('study', 'type'), 'sweep'),
    'plots': (('results', 'plots'), True),
    'tagged_quantity': (('physics', 'plate', 'young_modulus_pa'), [200, 'GPa']),
}


@pytest.mark.parametrize('case', sorted(INVALID))
def test_j4_invalid_documents_are_refused_without_output(tmp_path, case):
    path, value = INVALID[case]
    d = data()
    node = d
    for key in path[:-1]:
        node = node[key]
    if value is None:
        node.pop(path[-1])
    else:
        node[path[-1]] = value
    with pytest.raises(DocumentError):
        Document.from_dict(d)
    source = tmp_path/'invalid.json'
    source.write_text(json.dumps(d), encoding='utf-8')
    out = tmp_path/'out'
    assert main(['run', str(source), '-o', str(out), '-q']) == 2
    assert main(['validate', str(source)]) == 2
    assert not out.exists()


@pytest.mark.parametrize('fixed, held', [
    ({('left', 'x'), ('bottom', 'y')}, True),
    ({('right', 'x'), ('left', 'y')}, True),
    ({('bottom', 'x'), ('bottom', 'y')}, True),
    ({('top', 'y'), ('left', 'x')}, True),
    ({('bottom', 'x'), ('top', 'x'), ('left', 'y')}, True),
    ({('left', 'y'), ('right', 'y'), ('bottom', 'x')}, True),
    ({('bottom', 'x'), ('left', 'y')}, False),
    ({('top', 'x'), ('right', 'y')}, False),
    ({('bottom', 'x'), ('right', 'y')}, False),
    ({('left', 'x')}, False),
    ({('bottom', 'y'), ('top', 'y')}, False),
    (set(), False),
])
def test_j4_rigid_mode_rule_matches_the_solver_rank_test(fixed, held):
    """The documented side rule agrees with galerkin's rank test on an actual mesh."""
    assert mechanics.rigid_modes_fixed(fixed) is held
    mesh = rectangle_mesh(1., .4, 4, 2)
    dirichlet = {(int(node), 'xy'.index(c)): 0. for side, c in fixed for node in mesh.boundary[side]}
    if held:
        solve_elasticity(mesh, young_modulus=1e9, poisson_ratio=.3, plane='stress', dirichlet=dirichlet)
    else:
        with pytest.raises(ValueError, match='rigid modes'):
            solve_elasticity(mesh, young_modulus=1e9, poisson_ratio=.3, plane='stress', dirichlet=dirichlet)


def test_j4_adjacent_sides_may_share_a_corner_value_and_zero_traction_on_fixed_components():
    d = document(displacement={'left': {'x': 1e-6}, 'bottom': {'x': 1e-6, 'y': 0.}},
                 traction={'left': [0., 2e5], 'right': [1e6, 0.]})
    r = run(Document.from_dict(d), verbose=False)
    f = r.fields
    np.testing.assert_allclose(f['displacement_m'][f['dirichlet_node_ids'][f['dirichlet_components'] == 0], 0], 1e-6, rtol=0, atol=1e-18)


# J5 ------------------------------------------------------------------------------------------

def test_j5_cli_validate_run_save_and_fresh_output(tmp_path, capsys, monkeypatch):
    src = tmp_path/'input.json'
    Document.from_dict(data()).save(src)
    assert main(['validate', str(src)]) == 0
    assert 'mechanics.elasticity2d' in capsys.readouterr().out
    out = tmp_path/'out'
    assert main(['run', str(src), '-o', str(out), '-q']) == 0
    assert sorted(p.name for p in out.iterdir()) == ['fields.npz', 'log.txt', 'model.json', 'summary.json']
    summary = json.loads((out/'summary.json').read_text(encoding='utf-8'))
    assert summary['status'] == 'solved' and summary['result_format'] == 'mechanics.elasticity2d-result-v1'
    with np.load(out/'fields.npz', allow_pickle=False) as fields:
        assert str(fields['field_layout']) == 'mechanics2d-p1-v1'
        assert str(fields['mesh_length_unit']) == 'm'
        assert str(fields['result_format']) == 'mechanics.elasticity2d-result-v1'
        assert json.loads(str(fields['metadata_json'])) == summary
        restored = run(Document.load(out/'model.json'), verbose=False).fields
        for key, array in restored.items():
            np.testing.assert_array_equal(fields[key], array)
            assert summary['field_shapes'][key] == list(array.shape)
    before = (out/'summary.json').read_bytes()
    def fail(*a, **kw):
        raise AssertionError('must not solve for an existing output')
    monkeypatch.setattr('simcase.cli.run', fail)
    assert main(['run', str(src), '-o', str(out)]) == 1
    assert 'already exists' in capsys.readouterr().err
    assert (out/'summary.json').read_bytes() == before
    monkeypatch.undo()
    d = data()
    d['results']['save_fields'] = False
    Document.from_dict(d).save(src)
    assert main(['run', str(src), '-o', str(tmp_path/'nofields'), '-q']) == 0
    assert not (tmp_path/'nofields'/'fields.npz').exists() and (tmp_path/'nofields'/'summary.json').is_file()


def test_j5_save_partial_failure_cleanup(tmp_path, monkeypatch):
    r = run(Document.from_dict(data()), verbose=False)
    def fail(*args, **kwargs):
        raise OSError('injected NPZ failure')
    monkeypatch.setattr(np, 'savez_compressed', fail)
    out = tmp_path/'out'
    with pytest.raises(OSError, match='injected'):
        r.save(out)
    assert not out.exists()


def test_j5_snapshot_immutability(tmp_path):
    doc = Document.from_dict(data())
    r = run(doc, verbose=False)
    old = r.fields['displacement_m']
    doc.data['name'] = 'changed caller'
    r.fields['displacement_m'][:] = 999.
    r.summary()['diagnostics']['strain_energy_j_per_m'] = 999.
    np.testing.assert_array_equal(r.fields['displacement_m'], old)
    assert r.summary()['diagnostics']['strain_energy_j_per_m'] != 999.
    with pytest.raises(ValueError):  # the owned arrays are read-only; fields are copies
        r._arrays['displacement_m'][0, 0] = 1.
    out = tmp_path/'out'
    out.mkdir()
    (out/'keep').write_text('original', encoding='utf-8')
    with pytest.raises(FileExistsError):
        r.save(out)
    assert (out/'keep').read_text(encoding='utf-8') == 'original'
    r.doc.data['name'] = 'changed result'
    with pytest.raises(ValueError, match='changed'):
        r.save(tmp_path/'changed')
    assert not (tmp_path/'changed').exists()


def test_em_stages_reject():
    doc = Document.from_dict(data())
    with pytest.raises(DocumentError, match='EM stage'):
        build_mesh(doc)
    with pytest.raises(DocumentError, match='EM stage'):
        solve_point(None, doc.sole_physics()[1])


# J6 ------------------------------------------------------------------------------------------

def test_j6_studio_rejects_mechanics_documents():
    from fastapi import HTTPException
    from simcase.studio import server
    doc = Document.from_dict(data())
    response = server.validate(server.DocBody(doc=doc.data))
    assert response['ok'] is False and 'headless' in response['error']
    with pytest.raises(HTTPException) as error:
        server._require_studio_physics(doc)
    assert error.value.status_code == 400 and 'mechanics.elasticity2d' in error.value.detail
