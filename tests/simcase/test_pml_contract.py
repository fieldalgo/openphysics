# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import copy
import json
import numpy as np
import pytest
from decimal import Decimal
from simcase import Document, DocumentError, run, examples
from simcase.results_common import dumps_summary


def document(formulation='vector', bend=False):
    d=copy.deepcopy(examples.VECTOR_SLAB)
    d['materials']['film']={'refractive_index':{'n':3.48,'k':0.001}}
    p=d['physics']['em1']
    p.update(formulation=formulation,mode_count=1,target_effective_index=2.85,
             pml=dict(pml_thickness=dict(bottom='0.5 um',top='0.5 um')))
    if formulation=='scalar':
        p['boundary'].update(left='pmc',right='pmc')
        del p['effective_index_threshold']
    if bend: p['bend']=dict(bend_radius='5 um',axis='y',bend_origin='0 um')
    d['study']={'type':'single'}
    d['results']={'plots':False}
    return Document.from_dict(d)


@pytest.mark.parametrize('formulation',['scalar','vector'])
def test_result_diagnostics_and_archive(formulation,tmp_path):
    r=run(document(formulation,True),False)
    s=r.summary()
    dumps_summary(s)
    diag=s['open_boundary'][0]
    assert diag['stability']=='not_checked' and diag['schema']=='openphysics.pml-candidates/2'
    assert diag['physical_bounds']['unit']=='m' and 'length_unit' not in diag
    assert len(diag['candidates'])>=len(diag['selected_candidates'])==1
    assert any(not c['selected'] for c in diag['candidates'])
    for c in diag['candidates']:
        assert c['reasons'] and 'positive_imaginary_index' not in c['reasons']
        assert c['relative_residual']<1e-8
        assert c['effective_index']['time_convention']=='exp(-i omega t)'
    # dB per 90 degrees: the loss in dB/m over a quarter turn of radius 5 um (5e-6 m)
    np.testing.assert_allclose(r.bend_loss(),r.propagation_loss()*np.pi*5e-6/2)
    assert np.all(r.propagation_loss()>0) and np.all(r.bend_loss()>0)
    r.save(tmp_path)
    with np.load(tmp_path/'fields.npz') as a:
        assert json.loads(str(a['open_boundary_json']))==r.open_boundary
        assert str(a['field_representation']).startswith('pml-')


@pytest.mark.parametrize('formulation',['scalar','vector'])
def test_units_and_wavelength_tracking(formulation):
    d=document(formulation).data
    d['study']=dict(type='sweep',parameter='physics.em1.vacuum_wavelength',
                    values={'unit':'um','values':[1.549,1.55,1.551]})
    reference=run(Document.from_dict(d),False)
    assert reference.mode_tracking is not None
    assert reference.group_index() is not None
    for symbol,scale in [('nm','1000'),('m','1e-6')]:
        other=copy.deepcopy(d)
        other['geometry']['length_unit']=symbol
        exact=lambda v: float(Decimal(str(v))*Decimal(scale))      # noqa: E731
        other['geometry']['domain']={k:exact(v) for k,v in d['geometry']['domain'].items()}
        for key in ('x','y','w','h'):
            other['geometry']['shapes'][0][key]=exact(d['geometry']['shapes'][0][key])
        # the PML thickness keeps its own unit; the shape numbers moved to the other length_unit
        r=run(Document.from_dict(other),False)
        np.testing.assert_array_equal(r.effective_index,reference.effective_index)
        for point in r.open_boundary:
            assert len(point['selected_candidates'])==1
            assert sum(c['selected'] for c in point['candidates'])==1


@pytest.mark.parametrize('change,code',[
    ({'pml':{'pml_thickness':{'top':'-1 um'}}},'E-DOMAIN'),
    ({'pml':{'pml_thickness':{'top':'100 um'}}},'E-CONTRACT'),
    ({'pml':{'pml_thickness':{'top':'0.5 um'},'pml_order':True}},'E-VALUE-FORM'),
    ({'pml':{'pml_thickness':{'top':'0.5 um'},'pml_strength':float('nan')}},'E-JSON'),
    ({'pml':{'pml_thickness':{'top':'0.5 um'},'pml_minimum_physical_fraction':2}},'E-DOMAIN'),
    ({'bend':{'bend_radius':'0.1 um','axis':'y','bend_origin':'0 um'}},'E-CONTRACT'),
    # registry-domain tightenings (phase-2 spec 7.3): a side of thickness 0 and a fraction of 0
    ({'pml':{'pml_thickness':{'top':'0.5 um','bottom':'0 um'}}},'E-DOMAIN'),
    ({'pml':{'pml_thickness':{'top':'0.5 um'},'pml_minimum_physical_fraction':0}},'E-DOMAIN'),
    ({'bend':{'bend_radius':'5 um','axis':'y'}},'E-KEY-MISSING'),
])
def test_invalid_coordinates_rejected(change,code):
    d=document().data
    d['physics']['em1'].update(change)
    with pytest.raises(DocumentError) as caught: Document.from_dict(d)
    assert code in {x.code for x in caught.value.diagnostics}, [x.as_dict() for x in caught.value.diagnostics]


def test_bent_physical_fields_reconstruct_original_pencil():
    from simcase import build_mesh, solve_point
    from simcase.fields import VectorField
    from simcase.modes_document import stage_point
    from simcase.physics_em_modes2d import vector_pencil_residuals
    d=document('vector',True)
    model=build_mesh(d)
    p=d.si['physics']['em1']
    r=solve_point(model,p)
    # vector_pencil_residuals is a kernel-frame internal: micrometres and exp(+i omega t)
    k=stage_point(p)
    f=r['vector_field']
    field=VectorField(f.edges,np.conj(f.transverse)/1e-6,np.conj(f.longitudinal),np.conj(f.electric))
    residual=vector_pencil_residuals(model.solver_mesh,np.conjugate(model.relative_permittivity(p['vacuum_wavelength'])),
                                    k['wavelength'],k['boundary'],np.conj(r['effective_index']),field,pml=k['pml'],
                                    bend=k['bend'])
    assert residual.max()<1e-10


def test_open_sweep_refuses_real_subspace_method():
    from simcase import ModeTrackingError
    d=document().data
    d['study']=dict(type='sweep',parameter='physics.em1.vacuum_wavelength',values={'unit':'um','values':[1.549,1.55,1.551]},
                    tracking=dict(method='electric-l2-subspace-v1',cluster_span_tolerance=1e-5,cluster_gap_threshold=1e-3))
    with pytest.raises(ModeTrackingError,match='requires a real spectrum'):
        run(Document.from_dict(d),False)


def test_leaky_sweep_seeds_the_target_pole_not_highest_substrate_mode():
    data=document('vector').data
    data['materials']['film']={'refractive_index':3.48}
    data['geometry']['domain'].update(ymin=-2.,ymax=2.47)
    data['geometry']['shapes'].append(dict(name='substrate',type='rect',x=-.05,y=.47,w=.1,h=2.,material='film'))
    data['physics']['em1']['pml']['pml_thickness']=dict(bottom='1 um',top='1 um')
    data['mesh']['element_size']='0.02 um'
    data['mesh']['grading'].update(near='0.01 um',far='0.02 um')
    d=Document.from_dict(data)
    d.data['physics']['em1']['vacuum_wavelength']='1.549 um'
    single=run(d,False)
    d.data['study']=dict(type='sweep',parameter='physics.em1.vacuum_wavelength',
                         values={'unit':'um','values':[1.549,1.55,1.551]})
    sweep=run(d,False)
    np.testing.assert_allclose(sweep.effective_index[0],single.effective_index[0],atol=1e-10,rtol=0)
    # the leaky pole under exp(-i omega t): Im n_eff > 0 (the conjugate of the 0.2 value)
    assert abs(sweep.effective_index[1,0]-(2.8523269042892405+.0026882226051686553j))<2e-3
