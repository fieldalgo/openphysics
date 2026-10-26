# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Headless API/CLI acceptance, independent slab formulas and failure evidence."""
import copy
import json

import numpy as np
import pytest

from simcase import Document, DocumentError, run, build_mesh, solve_point, examples
from simcase.cli import main
from simcase.electric_joule import ElectricJouleRunResult
from galerkin.electric import solve_steady_electric
from galerkin.joule_heating import solve_steady_joule_heat
from galerkin.temperature_joule_heating import JouleConvergenceError


def data(kind='joule_rectangle'):
    return copy.deepcopy(examples.EXAMPLES[kind])


@pytest.mark.parametrize('kind', ['electric_rectangle', 'joule_rectangle', 'joule_temperature'])
def test_public_roundtrip_and_direct_api(tmp_path, kind):
    d = data(kind)
    doc = Document.from_dict(d)
    result = run(doc, verbose=False)
    assert isinstance(result, ElectricJouleRunResult)
    arrays = result.fields
    from galerkin import rectangle_mesh
    mesh = rectangle_mesh(1., .2, 24, 6)
    bc = {int(n): v for tag, v in {'left': 1., 'right': 0.}.items() for n in mesh.boundary[tag]}
    if kind == 'joule_temperature':
        from galerkin.temperature_joule_heating import ConductivityModel, solve_temperature_joule_heat
        direct = solve_temperature_joule_heat(mesh,
            electrical_conductivity=ConductivityModel(lambda t: 2/(1+.01*(t-300)), (290,400)),
            thermal_conductivity=1., electric_dirichlet=bc,
            thermal_dirichlet={int(n):300. for side in ('left','right') for n in mesh.boundary[side]},
            initial_temperature=300.)
        electric, heat = direct.coupled.electrical, direct.coupled.thermal
        assert len(result.summary()['iterations']) == len(direct.history)
        np.testing.assert_allclose(arrays['evaluated_temperature_k'], direct.evaluated_temperature, rtol=1e-12)
    else:
        electric = solve_steady_electric(mesh, conductivity=2., dirichlet=bc)
        heat = solve_steady_joule_heat(mesh, electrical_result=electric, conductivity=1.,
            dirichlet={int(n):300. for side in ('left','right') for n in mesh.boundary[side]}).thermal
    np.testing.assert_allclose(arrays['potential_v'], electric.potential, atol=1e-12)
    np.testing.assert_allclose(arrays['joule_heating_w_m3'], electric.joule_heating, rtol=1e-12)
    if kind != 'electric_rectangle':
        np.testing.assert_allclose(arrays['temperature_k'], heat.temperature, rtol=1e-12)
    out = result.save(tmp_path/kind)
    summary = json.loads((out/'summary.json').read_text())
    assert summary['status'] == 'converged'
    assert summary['result_format'] == doc.sole_physics()[1]['type']+'-result-v1'
    assert not (out/'.incomplete').exists()
    with np.load(out/'fields.npz', allow_pickle=False) as fields:
        for key, array in arrays.items():
            np.testing.assert_array_equal(fields[key], array)
            assert summary['field_shapes'][key] == list(array.shape)
        assert json.loads(str(fields['metadata_json'])) == summary
    restored = run(Document.load(out/'model.json'), verbose=False)
    for key in arrays:
        np.testing.assert_array_equal(restored.fields[key], arrays[key])


@pytest.mark.parametrize('unit, factor', [('m',1.), ('mm',1e3), ('um',1e6), ('nm',1e9)])
def test_resistor_analytic_and_length_units(unit, factor):
    d = data('electric_rectangle')
    d['units']['length'] = unit
    d['geometry']['domain'] = {k:v*factor for k,v in d['geometry']['domain'].items()}
    result = run(Document.from_dict(d), verbose=False)
    f, diag = result.fields, result.summary()['diagnostics']
    np.testing.assert_allclose(f['potential_v'], 1-f['nodes_m'][:,0], atol=2e-12)
    np.testing.assert_allclose(f['current_density_a_m2'][:,0], 2., atol=2e-11)
    np.testing.assert_allclose(f['current_density_a_m2'][:,1], 0., atol=2e-11)
    assert diag['joule_power_w_per_m'] == pytest.approx(.4, rel=1e-12)
    assert abs(diag['current_balance_a_per_m']) < 1e-11
    assert abs(diag['electric_power_defect_w_per_m']) < 1e-11


def test_current_driven_robin_and_flux():
    d = data()
    p = d['physics']['electric']
    p['dirichlet_potential_v'] = {'right': 0.}
    p['outward_current_a_m2'] = {'left': -2.}
    p['dirichlet_temperature_k'] = {}
    p['convection'] = {side:dict(h_w_m2k=4.,ambient_temperature_k=300.) for side in ('left','right')}
    p['outward_flux_w_m2'] = {'left': .2, 'right': .2}
    r = run(Document.from_dict(d), verbose=False)
    f, diag = r.fields, r.summary()['diagnostics']
    # Q=2, equal ends: Q L/2 = .2 + 4*(Tend-300), Tend=300.2.
    expected = 300.2+f['nodes_m'][:,0]*(1-f['nodes_m'][:,0])
    np.testing.assert_allclose(f['temperature_k'], expected, atol=3e-3)
    assert diag['outward_heat_w_per_m'] == pytest.approx(.4, abs=1e-11)
    assert abs(diag['heat_power_defect_w_per_m']) < 1e-11


def test_slab_mesh_convergence():
    errors = []
    for n in (8,16,32):
        d = data()
        d['mesh']['subdivisions'] = [n, max(2,n//4)]
        r = run(Document.from_dict(d), verbose=False)
        f = r.fields
        # Compare piecewise linear temperature at triangle centroids with analytic slab.
        x = f['nodes_m'][f['triangles'],0].mean(axis=1)
        exact = 300+x*(1-x)
        approx = f['temperature_k'][f['triangles']].mean(axis=1)
        errors.append(float(np.sqrt(np.mean((approx-exact)**2))))
        assert abs(r.summary()['diagnostics']['heat_power_defect_w_per_m']) < 1e-11
    order = np.log2(errors[-2]/errors[-1])
    print(dict(slab_rms_errors_k=errors, final_order=order))
    assert order > 1.8
    assert errors[-1] < 3e-4


def test_constant_model_limit():
    a = run(Document.from_dict(data()), verbose=False)
    d = data('joule_temperature')
    d['physics']['electric']['conductivity_model']['alpha_per_k'] = 0.
    b = run(Document.from_dict(d), verbose=False)
    for key in a.fields:
        np.testing.assert_allclose(a.fields[key], b.fields[key], atol=1e-12, rtol=1e-12)


@pytest.mark.parametrize('path,value', [
    (('mystery',), 1), (('geometry','shapes'), []), (('materials','copper'), {}),
    (('mesh','subdivisions'), [1000,1000]), (('mesh','subdivisions'), [True,2]),
    (('units','temperature'), 'C'), (('study','type'), 'sweep'), (('results','plots'), True),
    (('physics','electric','conductivity_s_m'), 1.),
    (('physics','electric','initial_temperature_k'), 500.),
    (('physics','electric','dirichlet_potential_v'), {}),
    (('physics','electric','dirichlet_potential_v'), {'left':1.,'top':0.}),
    (('physics','electric','outward_current_a_m2'), {'left': 1.}),
    (('physics','electric','iteration','relaxation'), 1.1),
    (('physics','electric','iteration','max_iterations'), 2.5),
    (('physics','electric','iteration','temperature_atol_k'), 0.),
    (('physics','electric','conductivity_model','alpha_per_k'), -.02),
    (('physics','electric','conductivity_model','reference_conductivity_s_m'), float('nan')),
    (('physics','electric','conductivity_model','expression'), '__import__("os")'),
])
def test_invalid_document(path,value):
    d = data('joule_temperature')
    node = d
    for key in path[:-1]: node = node[key]
    node[path[-1]] = value
    with pytest.raises(DocumentError): Document.from_dict(d)


@pytest.mark.parametrize('failure', ['iterations','range'])
def test_failed_solve_cli_evidence(tmp_path,capsys,failure):
    d = data('joule_temperature')
    p = d['physics']['electric']
    if failure == 'iterations':
        p['iteration'].update(relaxation=1e-12,max_iterations=2)
    else:
        p['conductivity_model']['temperature_range_k'] = [290.,300.1]
    doc = Document.from_dict(d)
    with pytest.raises(JouleConvergenceError) as error: run(doc,verbose=False)
    assert len(error.value.last_temperature) == 175
    source = tmp_path/'input.json'; doc.save(source)
    out = tmp_path/'out'
    assert main(['run',str(source),'-o',str(out),'-q']) == 1
    evidence = json.loads(capsys.readouterr().err)
    assert evidence['status'] == 'failed'
    assert len(evidence['last_temperature_k']) == 175
    assert len(evidence['iterations']) == (2 if failure == 'iterations' else 0)
    assert not out.exists()


def test_snapshot_and_fresh_output(tmp_path):
    d = data()
    doc = Document.from_dict(d)
    r = run(doc,verbose=False)
    old = r.fields['potential_v']
    doc.data['name'] = 'changed caller'
    r.fields['potential_v'][:] = 999
    r.summary()['diagnostics']['joule_power_w_per_m'] = 999
    np.testing.assert_array_equal(r.fields['potential_v'],old)
    out = tmp_path/'out'; out.mkdir(); (out/'keep').write_text('original')
    with pytest.raises(FileExistsError): r.save(out)
    assert (out/'keep').read_text() == 'original'
    r.doc.data['name'] = 'changed result'
    with pytest.raises(ValueError,match='changed'): r.save(tmp_path/'changed')
    assert not (tmp_path/'changed').exists()


def test_save_partial_failure_cleanup(tmp_path,monkeypatch):
    r = run(Document.from_dict(data()),verbose=False)
    def fail(*args,**kwargs): raise OSError('injected NPZ failure')
    monkeypatch.setattr(np,'savez_compressed',fail)
    out = tmp_path/'out'
    with pytest.raises(OSError,match='injected'): r.save(out)
    assert not out.exists()


def test_cli_validate_save_and_existing_preflight(tmp_path,capsys,monkeypatch):
    d = data(); d['results']['save_fields'] = False
    src = tmp_path/'input.json'; Document.from_dict(d).save(src)
    assert main(['validate',str(src)]) == 0
    out = tmp_path/'out'
    assert main(['run',str(src),'-o',str(out),'-q']) == 0
    assert (out/'summary.json').is_file() and not (out/'fields.npz').exists()
    def fail(*a,**kw): raise AssertionError('must not solve for an existing output')
    monkeypatch.setattr('simcase.cli.run',fail)
    assert main(['run',str(src),'-o',str(out)]) == 1
    assert 'already exists' in capsys.readouterr().err


def test_em_stages_reject():
    doc = Document.from_dict(data())
    with pytest.raises(DocumentError,match='EM stage'): build_mesh(doc)
    with pytest.raises(DocumentError,match='EM stage'): solve_point(None,doc.sole_physics()[1])


def test_temperature_current_driven_analytic():
    d = data('joule_temperature')
    d['mesh']['subdivisions'] = [32,8]
    p = d['physics']['electric']
    p['dirichlet_potential_v'] = {'right':0.}
    p['outward_current_a_m2'] = {'left':-1.}
    p['conductivity_model'].update(reference_conductivity_s_m=1.,alpha_per_k=1.)
    p['conductivity_model']['temperature_range_k'] = [300.,400.]
    r = run(Document.from_dict(d),verbose=False)
    f = r.fields
    x = f['nodes_m'][:,0]
    # J=1, rho0=1, k=1, alpha=1: beta=1. Solve T''+beta²(T-300)=-1.
    exact = 300.+np.cos(x-.5)/np.cos(.5)-1.
    np.testing.assert_allclose(f['temperature_k'],exact,atol=1e-4,rtol=0.)
    power = 2*np.tan(.5)*.2
    assert r.summary()['diagnostics']['joule_power_w_per_m'] == pytest.approx(power,rel=3e-4)


@pytest.mark.parametrize('kind',['electric_rectangle','joule_rectangle','joule_temperature'])
def test_studio_rejects_headless_documents(kind):
    from fastapi import HTTPException
    from simcase.studio import server
    doc = Document.from_dict(data(kind))
    response = server.validate(server.DocBody(doc=doc.data))
    assert response['ok'] is False and 'headless' in response['error']
    with pytest.raises(HTTPException) as error:
        server._require_studio_physics(doc)
    assert error.value.status_code == 400
