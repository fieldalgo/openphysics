# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Pre-registered gates of the ``mechanics.elasticity2d`` document (docs/packages/simcase/mechanics2d.md).

J1 document run == direct ``solve_elasticity`` on the same mesh (byte-identical arrays);
J2 refsol uniaxial and shear fields across length units; J3 mesh convergence of a
constant-body-force manufactured solution; J4 invalid documents refused without output;
J5 CLI validate/run/save, fresh output, partial-save cleanup and snapshot immutability;
J6 Studio rejects the type. ``mechanics.thermoelastic2d`` repeats them as K1 (byte-identical
steady heat + freeze_temperature + solve_thermoelasticity), K2 (refsol
``thermoelastic_traction.uniform_combined`` without shear across length units), K3 (mesh
convergence of a confined bar with a linear temperature) and K4 (refusals); J5 and J6 run
for both types. Thresholds are gates: never loosen them.

The documents are format 0.3 (units batch C7): every value carries its unit, the geometry its
length_unit; galerkin receives the same SI values as before.
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
from galerkin.thermal import solve_steady_heat
from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
from refsol import elasticity_traction as refsol
from refsol import thermoelastic_traction as thermo_refsol

UNITS = [('m', 1.), ('mm', 1e3), ('um', 1e6), ('nm', 1e9)]


KINDS = ['elastic_plate', 'thermoelastic_bar']


def data(kind='elastic_plate'):
    return copy.deepcopy(examples.EXAMPLES[kind])


def q(value, unit):
    """A quantity string with the exact double: ``repr`` digits and a unit."""
    return f'{float(value)!r} {unit}'


def displacements(sides):
    """{side: {component: metres}} -> prescribed_displacement quantity strings."""
    return {side: {c: q(v, 'm') for c, v in components.items()} for side, components in sides.items()}


def vectors(sides, unit='Pa'):
    return {side: [q(v, unit) for v in vector] for side, vector in sides.items()}


def document(unit='m', factor=1., *, plane='stress', nu=.3, size=(1., .4), subdivisions=(10, 4),
             displacement, traction=None, body_force=None, young=2e11):
    d = data()
    d['geometry']['length_unit'] = unit
    d['geometry']['domain'] = dict(xmin=0., xmax=size[0]*factor, ymin=0., ymax=size[1]*factor)
    d['mesh']['subdivision_count'] = list(subdivisions)
    p = d['physics']['plate']
    p.update(plane=plane, poisson_ratio=nu, youngs_modulus=q(young, 'Pa'),
             prescribed_displacement=displacements(displacement))
    p.pop('traction', None)
    if traction is not None:
        p['traction'] = vectors(traction)
    if body_force is not None:
        p['body_force_density'] = [q(v, 'N/m^3') for v in body_force]
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
    assert f['node_coordinates'].tobytes() == mesh.nodes.tobytes()
    assert f['triangles'].tobytes() == mesh.triangles.tobytes()
    for key, attr in (('displacement', 'displacement'), ('strain', 'strain'), ('stress', 'stress'),
                      ('applied_force_per_depth', 'load'), ('reaction_force_per_depth', 'reaction'),
                      ('residual_force_per_depth', 'residual')):
        value = np.asarray(getattr(direct, attr))
        assert f[key].shape == value.shape and f[key].dtype == value.dtype, key
        assert f[key].tobytes() == value.tobytes(), key
    summary = result.summary()
    assert summary['result_format'] == 'mechanics.elasticity2d-result-v2'
    assert summary['field_layout'] == 'mechanics2d-p1-v2'
    assert summary['field_components']['strain'] == ['strain_xx', 'strain_yy', 'engineering_shear_strain_xy']
    assert summary['field_components']['stress'] == ['stress_xx', 'stress_yy', 'stress_xy']
    assert summary['field_units']['stress'] == 'Pa' and summary['field_units']['applied_force_per_depth'] == 'N/m'
    assert summary['field_locations']['displacement'] == 'nodes'
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
    exact = refsol.uniaxial(f['node_coordinates'], applied, young_modulus=2e11, poisson_ratio=.3, plane=plane)
    centroids = f['node_coordinates'][f['triangles']].mean(axis=1)
    exact_cells = refsol.uniaxial(centroids, applied, young_modulus=2e11, poisson_ratio=.3, plane=plane)
    du = relative(f['displacement'], exact.displacement, np.max(abs(exact.displacement)))
    ds = relative(f['stress'], exact_cells.stress, applied)
    de = relative(f['strain'], exact_cells.strain, np.max(abs(exact_cells.strain)))
    print(dict(unit=unit, plane=plane, displacement_relative=du, stress_relative=ds, strain_relative=de))
    assert du <= 1e-10 and ds <= 1e-10 and de <= 1e-10
    balance = r.summary()['balance']
    assert balance['applied_force_per_depth']['values'] == pytest.approx([applied*.4, 0.], rel=1e-12,
                                                                         abs=1e-12*applied*.4)
    assert np.max(abs(np.asarray(balance['force_imbalance_per_depth']['values']))) <= 1e-10*applied*.4
    assert f'length_unit {unit}' in r.summary()['extent'][0]


@pytest.mark.parametrize('plane', ['stress', 'strain'])
@pytest.mark.parametrize('unit, factor', UNITS)
def test_j2_shear_refsol_across_length_units(unit, factor, plane):
    tau = 2e6
    d = document(unit, factor, plane=plane, displacement={'bottom': {'x': 0., 'y': 0.}},
                 traction={'top': [tau, 0.], 'left': [0., -tau], 'right': [0., tau]})
    r = run(Document.from_dict(d), verbose=False)
    f = r.fields
    exact = refsol.shear(f['node_coordinates'], tau, young_modulus=2e11, poisson_ratio=.3, plane=plane)
    centroids = f['node_coordinates'][f['triangles']].mean(axis=1)
    exact_cells = refsol.shear(centroids, tau, young_modulus=2e11, poisson_ratio=.3, plane=plane)
    du = relative(f['displacement'], exact.displacement, np.max(abs(exact.displacement)))
    ds = relative(f['stress'], exact_cells.stress, tau)
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
        x = fields['node_coordinates'][fields['triangles']].mean(axis=1)[:, 0]
        exact = np.column_stack([f/(lam+2*mu)*(length*x-x*x/2), np.zeros_like(x)])
        approx = fields['displacement'][fields['triangles']].mean(axis=1)
        errors.append(float(np.sqrt(np.mean(np.sum((approx-exact)**2, axis=1)))))
        exact_stress = np.column_stack([f*(length-x), lam/(lam+2*mu)*f*(length-x), np.zeros_like(x)])
        stress_errors.append(float(np.sqrt(np.mean(np.sum((fields['stress']-exact_stress)**2, axis=1))))/(f*length))
    orders = [float(np.log2(errors[i]/errors[i+1])) for i in range(2)]
    stress_orders = [float(np.log2(stress_errors[i]/stress_errors[i+1])) for i in range(2)]
    print(dict(plane=plane, rms_displacement_errors_m=errors, displacement_orders=orders,
               rms_stress_errors_relative=stress_errors, stress_orders=stress_orders))
    assert min(orders) >= 1.8
    assert min(stress_orders) >= .9


# J4 ------------------------------------------------------------------------------------------

PD = ('physics', 'plate', 'prescribed_displacement')
INVALID = {
    'hinge': (PD, {'bottom': {'x': '0 m'}, 'left': {'y': '0 m'}}),
    'x_only': (PD, {'left': {'x': '0 m'}}),
    'y_only': (PD, {'bottom': {'y': '0 m'}, 'top': {'y': '0 m'}}),
    'hinge_right': (PD, {'bottom': {'x': '0 m'}, 'right': {'y': '0 m'}}),
    'no_sides': (PD, {}),
    'empty_side': (PD, {'left': {}, 'bottom': {'y': '0 m'}}),
    'corner_conflict': (PD, {'left': {'x': '0 m'}, 'bottom': {'x': '0.001 m', 'y': '0 m'}}),
    'unknown_component': (PD, {'left': {'x': '0 m', 'z': '0 m'}, 'bottom': {'y': '0 m'}}),
    'boolean_value': (PD, {'left': {'x': False}, 'bottom': {'y': '0 m'}}),
    'bare_displacement': (PD, {'left': {'x': 0.}, 'bottom': {'y': 0.}}),
    'units_block': (('units',), {'length': 'mm'}),
    'missing_length_unit': (('geometry', 'length_unit'), None),
    'unknown_length_unit': (('geometry', 'length_unit'), 'parsec'),
    'bad_plane': (('physics', 'plate', 'plane'), 'axisymmetric'),
    'poisson_half': (('physics', 'plate', 'poisson_ratio'), .5),
    'poisson_minus_one': (('physics', 'plate', 'poisson_ratio'), -1.),
    'poisson_nan': (('physics', 'plate', 'poisson_ratio'), float('nan')),
    'zero_modulus': (('physics', 'plate', 'youngs_modulus'), '0 Pa'),
    'body_force_scalar': (('physics', 'plate', 'body_force_density'), '1 N/m^3'),
    'body_force_length': (('physics', 'plate', 'body_force_density'), ['1 N/m^3', '2 N/m^3', '3 N/m^3']),
    'traction_scalar': (('physics', 'plate', 'traction'), {'right': '1 MPa'}),
    'traction_unknown_side': (('physics', 'plate', 'traction'), {'front': ['1 MPa', '0 MPa']}),
    'traction_on_fixed_component': (('physics', 'plate', 'traction'), {'left': ['1 MPa', '0 MPa']}),
    'unknown_physics_key': (('physics', 'plate', 'thickness'), '1 mm'),
    'missing_modulus': (('physics', 'plate', 'youngs_modulus'), None),
    'unknown_top_key': (('mystery',), 1),
    'shapes': (('geometry', 'shapes'), []),
    'materials': (('materials', 'steel'), {}),
    'too_many_triangles': (('mesh', 'subdivision_count'), [1000, 1000]),
    'boolean_subdivision': (('mesh', 'subdivision_count'), [True, 2]),
    'sweep': (('study', 'type'), 'sweep'),
    'plots': (('results', 'plots'), True),
    'tagged_quantity': (('physics', 'plate', 'youngs_modulus'), [200, 'GPa']),
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
    np.testing.assert_allclose(f['displacement'][f['prescribed_node_ids'][f['prescribed_components'] == 0], 0], 1e-6, rtol=0, atol=1e-18)


# J5 ------------------------------------------------------------------------------------------

@pytest.mark.parametrize('kind', KINDS)
def test_j5_cli_validate_run_save_and_fresh_output(tmp_path, capsys, monkeypatch, kind):
    src = tmp_path/'input.json'
    Document.from_dict(data(kind)).save(src)
    assert main(['validate', str(src)]) == 0
    assert 'mechanics.' in capsys.readouterr().out
    out = tmp_path/'out'
    assert main(['run', str(src), '-o', str(out), '-q']) == 0
    assert sorted(p.name for p in out.iterdir()) == ['fields.npz', 'log.txt', 'model.json', 'summary.json']
    summary = json.loads((out/'summary.json').read_text(encoding='utf-8'))
    physics_type = data(kind)['physics'][next(iter(data(kind)['physics']))]['type']
    assert summary['status'] == 'solved' and summary['result_format'] == physics_type+'-result-v2'
    with np.load(out/'fields.npz', allow_pickle=False) as fields:
        assert str(fields['field_layout']) == mechanics.FIELD_LAYOUTS[physics_type]
        assert 'mesh_length_unit' not in fields.files                  # coordinates are SI metres
        assert str(fields['result_format']) == physics_type+'-result-v2'
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
    d = data(kind)
    d['results']['save_fields'] = False
    Document.from_dict(d).save(src)
    assert main(['run', str(src), '-o', str(tmp_path/'nofields'), '-q']) == 0
    assert not (tmp_path/'nofields'/'fields.npz').exists() and (tmp_path/'nofields'/'summary.json').is_file()


@pytest.mark.parametrize('kind', KINDS)
def test_j5_save_partial_failure_cleanup(tmp_path, monkeypatch, kind):
    r = run(Document.from_dict(data(kind)), verbose=False)
    def fail(*args, **kwargs):
        raise OSError('injected NPZ failure')
    monkeypatch.setattr(np, 'savez_compressed', fail)
    out = tmp_path/'out'
    with pytest.raises(OSError, match='injected'):
        r.save(out)
    assert not out.exists()


@pytest.mark.parametrize('kind', KINDS)
def test_j5_snapshot_immutability(tmp_path, kind):
    doc = Document.from_dict(data(kind))
    r = run(doc, verbose=False)
    old = r.fields['displacement']
    doc.data['name'] = 'changed caller'
    r.fields['displacement'][:] = 999.
    r.summary()['balance']['strain_energy_per_depth']['value'] = 999.
    np.testing.assert_array_equal(r.fields['displacement'], old)
    assert r.summary()['balance']['strain_energy_per_depth']['value'] != 999.
    with pytest.raises(ValueError):  # the owned arrays are read-only; fields are copies
        r._arrays['displacement'][0, 0] = 1.
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


@pytest.mark.parametrize('kind', KINDS)
def test_em_stages_reject(kind):
    doc = Document.from_dict(data(kind))
    with pytest.raises(DocumentError, match='EM stage'):
        build_mesh(doc)
    with pytest.raises(DocumentError, match='EM stage'):
        solve_point(None, doc.sole_physics()[1])


# J6 ------------------------------------------------------------------------------------------

@pytest.mark.parametrize('kind', KINDS)
def test_j6_studio_rejects_mechanics_documents(kind):
    from fastapi import HTTPException
    from simcase.studio import server
    doc = Document.from_dict(data(kind))
    response = server.validation_payload(doc.data)
    assert response['ok'] is False and 'headless' in response['error']
    with pytest.raises(HTTPException) as error:
        server._require_studio_physics(doc)
    assert error.value.status_code == 400 and 'mechanics.' in error.value.detail


# K1-K4: mechanics.thermoelastic2d --------------------------------------------------------------

MATERIAL = dict(young_modulus=70e9, poisson_ratio=.3, thermal_expansion_per_k=12e-6, reference_temperature_k=293.15)


def thermo_document(unit='m', factor=1., *, plane='stress', nu=.3, domain=(0., 1., 0., .4), subdivisions=(10, 4),
                    temperatures, displacement, traction=None, body_force=None, alpha=12e-6, tref=293.15, **heat):
    d = data('thermoelastic_bar')
    d['geometry']['length_unit'] = unit
    xmin, xmax, ymin, ymax = (v*factor for v in domain)
    d['geometry']['domain'] = dict(xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)
    d['mesh']['subdivision_count'] = list(subdivisions)
    p = d['physics']['bar']
    p.update(plane=plane, poisson_ratio=nu, youngs_modulus=q(70e9, 'Pa'), linear_expansion_coefficient=q(alpha, '1/K'),
             stress_free_temperature=q(tref, 'K'), prescribed_temperature={s: q(t, 'K') for s, t in temperatures.items()},
             prescribed_displacement=displacements(displacement), **heat)
    p.pop('traction', None)
    if traction is not None:
        p['traction'] = vectors(traction)
    if body_force is not None:
        p['body_force_density'] = [q(v, 'N/m^3') for v in body_force]
    return d


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_k1_thermoelastic_run_matches_direct_calls_byte_for_byte(plane):
    d = thermo_document('mm', 1e3, plane=plane, domain=(-.5, .5, .1, .5),
                        temperatures={'left': 293.15, 'right': 353.15},
                        convection={'top': dict(heat_transfer_coefficient='25 W/(m^2 K)', ambient_temperature='300 K')},
                        inward_heat_flux={'bottom': '-150 W/m^2'}, heat_source_density='20000 W/m^3',
                        displacement={'left': {'x': 0.}, 'bottom': {'y': 0.}}, traction={'right': [3e6, 0.], 'top': [0., -1e5]},
                        body_force=[0., -2.7e4])
    result = run(Document.from_dict(d), verbose=False)
    mesh = rectangle_mesh(1., .4, 10, 4)
    mesh.nodes += [-.5, .1]
    heat = solve_steady_heat(mesh, conductivity=237., heat_source=2e4,
                             dirichlet=dict(sorted({int(n): t for side, t in (('left', 293.15), ('right', 353.15))
                                                    for n in mesh.boundary[side]}.items())),
                             outward_flux={'bottom': 150.}, convection={'top': (25., 300.)})
    fixed = {}
    for side, component in (('left', 0), ('bottom', 1)):
        for node in mesh.boundary[side]:
            fixed[int(node), component] = 0.
    direct = solve_thermoelasticity(mesh, freeze_temperature(mesh, heat.temperature), reference_temperature_k=293.15,
                                    thermal_expansion_per_k=12e-6, young_modulus=70e9, poisson_ratio=.3, plane=plane,
                                    dirichlet=dict(sorted(fixed.items())), body_force=(0., -2.7e4),
                                    traction={'right': [3e6, 0.], 'top': [0., -1e5]})
    f = result.fields
    assert f['temperature'].tobytes() == np.asarray(heat.temperature).tobytes()
    assert f['heat_flux'].tobytes() == np.asarray(heat.heat_flux).tobytes()
    assert f['outward_convective_heat_rate_per_depth'].tobytes() == np.asarray(heat.convective_outward).tobytes()
    for key, attr in (('displacement', 'displacement'), ('strain', 'total_strain'), ('thermal_strain', 'thermal_strain'),
                      ('elastic_strain', 'elastic_strain'), ('stress', 'stress'), ('stress_zz', 'sigma_zz'),
                      ('strain_zz', 'epsilon_zz'), ('applied_force_per_depth', 'load_external'),
                      ('thermal_equivalent_force_per_depth', 'load_thermal'), ('applied_body_force_per_depth', 'load_body'),
                      ('applied_traction_force_per_depth', 'load_traction'), ('reaction_force_per_depth', 'reaction'),
                      ('residual_force_per_depth', 'residual')):
        value = np.asarray(getattr(direct, attr))
        assert f[key].shape == value.shape and f[key].dtype == value.dtype, key
        assert f[key].tobytes() == value.tobytes(), key
    summary = result.summary()
    assert summary['result_format'] == 'mechanics.thermoelastic2d-result-v2'
    assert summary['field_layout'] == 'thermoelastic2d-p1-v2'
    assert summary['temperature_snapshot']['snapshot_hash'] == direct.temperature_snapshot.snapshot_hash
    # D-30: strain_energy_per_depth is the physical elastic energy; the solver's quadratic
    # functional is stiffness_energy_functional_per_depth
    assert summary['balance']['strain_energy_per_depth']['value'] == float(direct.physical_elastic_energy)
    assert summary['balance']['stiffness_energy_functional_per_depth']['unit'] == 'J/m'
    assert 'length_unit mm' in summary['extent'][0]


def _combined(points, plane, nu):
    return thermo_refsol.uniform_combined(points, applied_stress=(8e6, -2e6, 0.), **dict(MATERIAL, plane=plane, poisson_ratio=nu))


@pytest.mark.parametrize('plane', ['stress', 'strain'])
@pytest.mark.parametrize('unit, factor', UNITS)
def test_k2_uniform_combined_refsol_across_length_units(unit, factor, plane):
    """uniform_combined with its shear component set to zero: a side-constant document can
    prescribe its affine displacement (x on the left, y on the bottom) and its normal tractions,
    and the uniform 313.15 K temperature comes from Dirichlet on all four sides. The shear
    variant has no side with a constant displacement component and is not expressible."""
    domain = (-.03, .07, .01, .05)
    corner = _combined(np.array([[domain[0], domain[2]]]), plane, .3).displacement[0]
    d = thermo_document(unit, factor, plane=plane, domain=domain,
                        temperatures={side: 313.15 for side in ('left', 'right', 'bottom', 'top')},
                        displacement={'left': {'x': float(corner[0])}, 'bottom': {'y': float(corner[1])}},
                        traction={'right': [8e6, 0.], 'top': [0., -2e6]})
    r = run(Document.from_dict(d), verbose=False)
    f = r.fields
    exact = _combined(f['node_coordinates'], plane, .3)
    cells = _combined(f['node_coordinates'][f['triangles']].mean(axis=1), plane, .3)
    stress = np.column_stack([cells.stress[:, 0, 0], cells.stress[:, 1, 1], cells.stress[:, 0, 1]])
    dt = relative(f['temperature'], exact.temperature_k, 313.15)
    du = relative(f['displacement'], exact.displacement, np.max(abs(exact.displacement)))
    ds = relative(f['stress'], stress, 8e6)
    dz = relative(f['stress_zz'], cells.stress[:, 2, 2], 8e6)
    de = relative(f['strain'], cells.total_strain[:, [0, 1, 0], [0, 1, 1]]*[1, 1, 2], np.max(abs(cells.total_strain)))
    print(dict(unit=unit, plane=plane, temperature_relative=dt, displacement_relative=du, stress_relative=ds,
               sigma_zz_relative=dz, strain_relative=de))
    assert dt <= 1e-10 and du <= 1e-10 and ds <= 1e-10 and dz <= 1e-10 and de <= 1e-10
    area = .1*.04
    energy = float(np.mean(cells.energy_density))*area
    assert r.summary()['balance']['strain_energy_per_depth']['value'] == pytest.approx(energy, rel=1e-10)


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_k3_confined_bar_with_linear_temperature_mesh_convergence(plane):
    """Left x and y fixed, y fixed on bottom and top, right free, T = T1 + G x from Dirichlet left/right
    (reproduced exactly by P1). With u_y = 0 and u_x = u(x), equilibrium gives sxx = 0, hence
    exx = k alpha theta with k = 1+nu (plane stress) or (1+nu)/(1-nu) (plane strain), and
    u_x = k alpha ((T1-Tref) x + G x^2/2). The in-plane stress comes from the independent
    refsol.thermoelastic_traction.parent_state for that strain and temperature. The quadratic
    displacement converges as h^2 (gate: order >= 1.8), the element stress as h."""
    e, nu, alpha, tref, t1, t2, length = 70e9, .3, 12e-6, 293.15, 293.15, 353.15, 1.
    k = 1+nu if plane == 'stress' else (1+nu)/(1-nu)
    g = (t2-t1)/length
    errors, stress_errors = [], []
    for n in (8, 16, 32):
        d = thermo_document('m', 1., plane=plane, domain=(0., length, 0., .25), subdivisions=(n, max(2, n//4)),
                            temperatures={'left': t1, 'right': t2},
                            displacement={'left': {'x': 0., 'y': 0.}, 'bottom': {'y': 0.}, 'top': {'y': 0.}})
        r = run(Document.from_dict(d), verbose=False)
        f = r.fields
        x = f['node_coordinates'][:, 0]
        np.testing.assert_allclose(f['temperature'], t1+g*x, rtol=0, atol=1e-9)
        centroids = f['node_coordinates'][f['triangles']].mean(axis=1)
        xc = centroids[:, 0]
        exact = np.column_stack([k*alpha*((t1-tref)*xc+g*xc*xc/2), np.zeros_like(xc)])
        approx = f['displacement'][f['triangles']].mean(axis=1)
        errors.append(float(np.sqrt(np.mean(np.sum((approx-exact)**2, axis=1)))))
        theta = t1-tref+g*xc
        stress, _, _ = thermo_refsol.parent_state(np.column_stack([k*alpha*theta, 0*theta, 0*theta]), tref+theta,
                                                   **dict(MATERIAL, plane=plane))
        exact_stress = np.column_stack([stress[:, 0, 0], stress[:, 1, 1], stress[:, 0, 1]])
        scale = np.max(abs(exact_stress))
        stress_errors.append(float(np.sqrt(np.mean(np.sum((f['stress']-exact_stress)**2, axis=1))))/scale)
        np.testing.assert_allclose(f['stress_zz'], stress[:, 2, 2], rtol=0, atol=stress_errors[-1]*scale*4)
    orders = [float(np.log2(errors[i]/errors[i+1])) for i in range(2)]
    stress_orders = [float(np.log2(stress_errors[i]/stress_errors[i+1])) for i in range(2)]
    print(dict(plane=plane, rms_displacement_errors_m=errors, displacement_orders=orders,
               rms_stress_errors_relative=stress_errors, stress_orders=stress_orders))
    assert min(orders) >= 1.8
    assert min(stress_orders) >= .9


THERMO_INVALID = {
    'units_block': (('units',), {'length': 'mm', 'temperature': 'K'}),
    'fahrenheit': (('physics', 'bar', 'stress_free_temperature'), '68 degF'),
    'missing_conductivity': (('physics', 'bar', 'thermal_conductivity'), None),
    'zero_conductivity': (('physics', 'bar', 'thermal_conductivity'), '0 W/(m K)'),
    'missing_alpha': (('physics', 'bar', 'linear_expansion_coefficient'), None),
    'nan_alpha': (('physics', 'bar', 'linear_expansion_coefficient'), float('nan')),
    'negative_reference': (('physics', 'bar', 'stress_free_temperature'), '-1 K'),
    'missing_reference': (('physics', 'bar', 'stress_free_temperature'), None),
    'pure_neumann_heat': (('physics', 'bar', 'prescribed_temperature'), {}),
    'negative_temperature': (('physics', 'bar', 'prescribed_temperature'), {'left': '-5 K'}),
    'temperature_corner_conflict': (('physics', 'bar', 'prescribed_temperature'), {'left': '293.15 K', 'bottom': '300 K'}),
    'flux_on_fixed_side': (('physics', 'bar', 'inward_heat_flux'), {'left': '-10 W/m^2'}),
    'bad_convection': (('physics', 'bar', 'convection'), {'top': {'heat_transfer_coefficient': '-1 W/(m^2 K)',
                                                                  'ambient_temperature': '300 K'}}),
    'hinge': (('physics', 'bar', 'prescribed_displacement'), {'bottom': {'x': '0 m'}, 'left': {'y': '0 m'}}),
    'conductivity_model': (('physics', 'bar', 'conductivity_model'), {}),
    'iteration': (('physics', 'bar', 'iteration'), {}),
}


@pytest.mark.parametrize('case', sorted(THERMO_INVALID))
def test_k4_invalid_thermoelastic_documents_are_refused_without_output(tmp_path, case):
    path, value = THERMO_INVALID[case]
    d = data('thermoelastic_bar')
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
    assert not out.exists()


def test_k4_elastic_document_refuses_heat_keys():
    for key, value in (('thermal_conductivity', '1 W/(m K)'), ('prescribed_temperature', {'left': '300 K'}),
                       ('linear_expansion_coefficient', '10 ppm/K'), ('stress_free_temperature', '300 K')):
        d = data()
        d['physics']['plate'][key] = value
        with pytest.raises(DocumentError, match='has no thermal stage; use mechanics.thermoelastic2d') as caught:
            Document.from_dict(d)
        assert [(e.code, e.path) for e in caught.value.diagnostics if e.severity == 'error'] == [
            ('E-CONTRACT', f'physics.plate.{key}')]
