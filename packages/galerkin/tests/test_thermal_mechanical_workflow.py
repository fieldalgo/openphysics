# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Producer workflow contracts; independent numerical acceptance is separate."""
import copy
import json
from types import SimpleNamespace
import numpy as np
import pytest
from galerkin.mesh import rectangle_mesh
import galerkin.thermal_mechanical as workflow


def arguments(mesh,plane='strain'):
    return dict(units={'length':'m','temperature':'K'},conductivity=10.,
        thermal_dirichlet={int(i):313.15 for i in mesh.boundary['left']},
        young_modulus=70e9,poisson_ratio=.3,plane=plane,
        thermal_expansion_per_k=12e-6,reference_temperature_k=293.15,
        mechanical_dirichlet={(0,0):0.,(0,1):0.,(3,1):0.})


@pytest.mark.parametrize('plane',['stress','strain'])
def test_uniform_exact_and_manifest(plane):
    mesh=rectangle_mesh(1,1,3,3);kw=arguments(mesh,plane)
    r=workflow.solve_steady_thermoelasticity(mesh,**kw)
    factor=1 if plane=='stress' else 1.3;a=12e-6*20
    np.testing.assert_allclose(r.mechanics.displacement,factor*a*mesh.nodes,atol=a*1e-10)
    np.testing.assert_allclose(r.mechanics.stress,0,atol=70e9*a*1e-10)
    np.testing.assert_allclose(r.mechanics.sigma_zz,0 if plane=='stress' else -70e9*a,atol=70e9*a*1e-10)
    expected=0 if plane=='stress' else .5*70e9*a*a
    assert abs(r.mechanics.physical_elastic_energy-expected)<70e9*a*a*1e-10
    assert r.reference_mesh is not mesh
    assert not np.shares_memory(r.reference_mesh.nodes,mesh.nodes)
    assert r.mechanics.temperature_snapshot is r.temperature_snapshot
    np.testing.assert_array_equal(r.heat.temperature,r.temperature_snapshot.temperature_k)
    m=r.manifest;assert r.manifest_json==json.dumps(m,sort_keys=True,separators=(',',':'),allow_nan=False)
    m['units']['length']='mm';assert r.manifest['units']['length']=='m'
    assert r.manifest['origin']=='workflow_owned_heat_call' and r.manifest['authentication']=='not_certified'
    before=r.temperature_snapshot.temperature_k.copy();r.heat.temperature[:]=1
    np.testing.assert_array_equal(r.temperature_snapshot.temperature_k,before)
    assert not r.temperature_snapshot.temperature_k.flags.writeable
    mesh.nodes[:]*=2;kw['thermal_dirichlet'].clear();kw['units']['length']='mm'
    assert r.manifest['inputs']['thermal_dirichlet'] and r.manifest['units']['length']=='m'
    assert r.reference_mesh.nodes.max()==1


@pytest.mark.parametrize('units',[{}, {'length':'mm','temperature':'K'}, {'length':'m','temperature':'C'},
                                    {'length':'m','temperature':'K','time':'s'}])
def test_units_reject_before_heat(monkeypatch,units):
    mesh=rectangle_mesh(1,1,3,3);kw=arguments(mesh);kw['units']=units
    monkeypatch.setattr(workflow,'solve_steady_heat',lambda *a,**k:pytest.fail('heat called after invalid input'))
    with pytest.raises(workflow.WorkflowStageError) as e:workflow.solve_steady_thermoelasticity(mesh,**kw)
    assert e.value.stage=='input' and isinstance(e.value.__cause__,ValueError)


@pytest.mark.parametrize('kind',['fractional','clockwise','nonfinite','duplicate'])
def test_raw_mesh_not_repaired(kind):
    mesh=rectangle_mesh(1,1,3,3);kw=arguments(mesh)
    if kind=='fractional':mesh.triangles=mesh.triangles.astype(float)+.1
    elif kind=='clockwise':mesh.triangles[0]=mesh.triangles[0,::-1]
    elif kind=='nonfinite':mesh.nodes[0,0]=np.nan
    else:mesh.triangles[1]=mesh.triangles[0]
    before=mesh.triangles.copy()
    with pytest.raises(workflow.WorkflowStageError):workflow.solve_steady_thermoelasticity(mesh,**kw)
    np.testing.assert_array_equal(mesh.triangles,before)


def test_negative_heat_transfer_rejected_without_mechanics(monkeypatch):
    mesh=rectangle_mesh(1,1,3,3);kw=arguments(mesh)
    kw['thermal_dirichlet']={int(i):-1. for i in mesh.boundary['left']}
    monkeypatch.setattr(workflow,'solve_thermoelasticity',lambda *a,**k:pytest.fail('mechanics called after negative transfer'))
    with pytest.raises(workflow.WorkflowStageError,match='minimum -1.0 K at node') as e:
        workflow.solve_steady_thermoelasticity(mesh,**kw)
    assert e.value.stage=='transfer' and isinstance(e.value.__cause__,ValueError)


@pytest.mark.parametrize('damage',['nan','inf','shape','complex'])
def test_bad_temperature_transfer(damage,monkeypatch):
    mesh=rectangle_mesh(1,1,3,3);kw=arguments(mesh);t=np.full(mesh.num_nodes,300.)
    if damage=='nan':t[4]=np.nan
    elif damage=='inf':t[4]=np.inf
    elif damage=='shape':t=t[:,None]
    else:t=t+1j
    monkeypatch.setattr(workflow,'solve_steady_heat',lambda *a,**k:SimpleNamespace(temperature=t))
    monkeypatch.setattr(workflow,'solve_thermoelasticity',lambda *a,**k:pytest.fail('invalid transfer reached mechanics'))
    with pytest.raises(workflow.WorkflowStageError) as e:workflow.solve_steady_thermoelasticity(mesh,**kw)
    assert e.value.stage=='transfer'
    if damage in ('nan','inf'):assert 'node 4' in str(e.value)


@pytest.mark.parametrize('stage',['heat','mechanics'])
def test_chained_component_failure(stage,monkeypatch):
    mesh=rectangle_mesh(1,1,3,3);kw=arguments(mesh);cause=RuntimeError('original callback failure')
    def fail(*a,**k):raise cause
    monkeypatch.setattr(workflow,'solve_steady_heat' if stage=='heat' else 'solve_thermoelasticity',fail)
    with pytest.raises(workflow.WorkflowStageError) as e:workflow.solve_steady_thermoelasticity(mesh,**kw)
    assert e.value.stage==stage and e.value.__cause__ is cause


def test_original_mutation_from_callback_is_isolated():
    mesh=rectangle_mesh(1,1,3,3);kw=arguments(mesh);baseline=mesh.nodes.copy()
    def source(p):
        mesh.nodes[:]=0;kw['thermal_dirichlet'].clear()
        return np.zeros(len(p))
    kw['heat_source']=source;r=workflow.solve_steady_thermoelasticity(mesh,**kw)
    np.testing.assert_array_equal(r.reference_mesh.nodes,baseline)
    assert r.manifest['inputs']['heat_source_w_m3']=={'kind':'callable','origin':'caller_provided','fingerprinted':False}
    assert r.manifest['inputs']['thermal_dirichlet']


def test_detected_private_mesh_mutation_stops_transfer(monkeypatch):
    mesh=rectangle_mesh(1,1,3,3);kw=arguments(mesh);real=workflow.solve_steady_heat
    def changed(private,**kwargs):
        result=real(private,**kwargs);private.nodes[5,0]+=.001;return result
    monkeypatch.setattr(workflow,'solve_steady_heat',changed)
    with pytest.raises(workflow.WorkflowStageError,match='reference mesh changed') as e:
        workflow.solve_steady_thermoelasticity(mesh,**kw)
    assert e.value.stage=='heat'


@pytest.mark.parametrize('field,value',[('conductivity',0.),('conductivity',True),
    ('young_modulus',-1.),('poisson_ratio',.5),('reference_temperature_k',-1.),
    ('thermal_expansion_per_k',float('inf')),('body_force',[1.]),('plane','3d')])
def test_invalid_material_input(field,value):
    mesh=rectangle_mesh(1,1,3,3);kw=arguments(mesh);kw[field]=value
    with pytest.raises(workflow.WorkflowStageError) as e:workflow.solve_steady_thermoelasticity(mesh,**kw)
    assert e.value.stage=='input'


def test_canonical_input_order_and_callback_copies():
    mesh=rectangle_mesh(1,1,3,3);kw=arguments(mesh)
    first=workflow.solve_steady_thermoelasticity(mesh,**kw)
    kw['thermal_dirichlet']=dict(reversed(list(kw['thermal_dirichlet'].items())))
    kw['mechanical_dirichlet']=dict(reversed(list(kw['mechanical_dirichlet'].items())))
    again=workflow.solve_steady_thermoelasticity(mesh,**kw)
    assert first.manifest_json==again.manifest_json
    body=np.zeros(2);kw['body_force']=body
    def source(points):body[:]=100.;return np.zeros(len(points))
    kw['heat_source']=source;result=workflow.solve_steady_thermoelasticity(mesh,**kw)
    np.testing.assert_array_equal(result.mechanics.load_external,0.)
    assert result.manifest['inputs']['body_force_n_m3']['value']==[0.,0.]


def test_private_reference_is_identical_across_stages(monkeypatch):
    mesh=rectangle_mesh(1,1,3,3);kw=arguments(mesh);seen=[]
    heat=workflow.solve_steady_heat;freeze=workflow.freeze_temperature;mechanical=workflow.solve_thermoelasticity
    def h(private,**args):seen.append(private);return heat(private,**args)
    def t(private,temperature):seen.append(private);return freeze(private,temperature)
    def m(private,snapshot,**args):seen.append(private);return mechanical(private,snapshot,**args)
    monkeypatch.setattr(workflow,'solve_steady_heat',h);monkeypatch.setattr(workflow,'freeze_temperature',t)
    monkeypatch.setattr(workflow,'solve_thermoelasticity',m)
    r=workflow.solve_steady_thermoelasticity(mesh,**kw)
    assert len(seen)==3 and all(x is r.reference_mesh for x in seen) and r.reference_mesh is not mesh


@pytest.mark.parametrize('bad',['none','heat','mechanics'])
def test_component_constraints(bad):
    from galerkin.mesh import Mesh
    base=rectangle_mesh(1,1,2,2);n=base.num_nodes
    mesh=Mesh(np.concatenate([base.nodes,base.nodes+[2,0]]),np.concatenate([base.triangles,base.triangles+n]),
              {k:np.concatenate([v,v+n]) for k,v in base.boundary.items()})
    kw=arguments(mesh)
    kw['mechanical_dirichlet']={(o+i,c):0. for o in [0,n] for i,c in [(0,0),(0,1),(2,1)]}
    if bad=='heat':kw['thermal_dirichlet']={int(i):313.15 for i in base.boundary['left']}
    if bad=='mechanics':del kw['mechanical_dirichlet'][(n+2,1)]
    if bad=='none':
        result=workflow.solve_steady_thermoelasticity(mesh,**kw)
        np.testing.assert_allclose(result.mechanics.stress,0,atol=70e9*12e-6*20*1e-10)
    else:
        with pytest.raises(workflow.WorkflowStageError) as e:workflow.solve_steady_thermoelasticity(mesh,**kw)
        assert e.value.stage==bad


def test_manifest_failure_chained(monkeypatch):
    mesh=rectangle_mesh(1,1,3,3);kw=arguments(mesh);cause=ValueError('injected canonical JSON error')
    def fail(*a,**k):raise cause
    monkeypatch.setattr(workflow.json,'dumps',fail)
    with pytest.raises(workflow.WorkflowStageError) as e:workflow.solve_steady_thermoelasticity(mesh,**kw)
    assert e.value.stage=='manifest' and e.value.__cause__ is cause


def test_valid_numeric_temperature_is_not_authenticated_as_units_intent():
    mesh=rectangle_mesh(1,1,3,3);kw=arguments(mesh)
    kw['thermal_dirichlet']={int(i):20. for i in mesh.boundary['left']}
    r=workflow.solve_steady_thermoelasticity(mesh,**kw)
    np.testing.assert_allclose(r.temperature_snapshot.temperature_k,20.)
    assert r.manifest['authentication']=='not_certified'
