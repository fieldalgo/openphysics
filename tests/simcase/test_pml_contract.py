# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import copy
import json
import numpy as np
import pytest
from simcase import Document, DocumentError, run, examples


def document(formulation='vector', bend=False):
    d=copy.deepcopy(examples.VECTOR_SLAB)
    d['materials']['film']={'n':3.48,'k':0.001}
    p=d['physics']['em1']
    p.update(formulation=formulation,num_modes=1,n_target=2.85,
             pml=dict(thickness=dict(bottom=.5,top=.5)))
    if formulation=='scalar': p['boundary'].update(left='pmc',right='pmc')
    if bend: p['bend']=dict(radius=5.,axis='y',origin=0.)
    d['study']={'type':'single'}
    d['results']={'plots':False}
    return Document.from_dict(d)


@pytest.mark.parametrize('formulation',['scalar','vector'])
def test_result_diagnostics_and_archive(formulation,tmp_path):
    r=run(document(formulation,True),False)
    s=r.summary()
    json.dumps(s,allow_nan=False)
    diag=s['open_boundary'][0]
    assert diag['stability']=='not_checked'
    assert len(diag['candidates'])>=len(diag['selected_candidates'])==1
    assert any(not c['selected'] for c in diag['candidates'])
    for c in diag['candidates']:
        assert c['reasons']
        assert c['pencil_residual']<1e-8
    np.testing.assert_allclose(r.bend_loss_db_90deg(),r.propagation_loss_db_cm()*np.pi*5e-4/2)
    r.save(tmp_path)
    with np.load(tmp_path/'fields.npz') as a:
        assert json.loads(str(a['open_boundary_json']))==r.open_boundary
        assert str(a['field_representation']).startswith('pml-')


@pytest.mark.parametrize('formulation',['scalar','vector'])
def test_units_and_wavelength_tracking(formulation):
    from test_length_canonical import _written_in
    d=document(formulation).data
    d['study']=dict(type='sweep',parameter='physics.em1.wavelength',values=[1.549,1.55,1.551])
    reference=run(Document.from_dict(d),False)
    assert reference.mode_tracking is not None
    assert reference.group_index() is not None
    for symbol,scale in [('nm','1000'),('m','1e-6')]:
        other=_written_in(d,symbol,scale)
        other['physics']['em1']['pml']['thickness']={k:v*float(scale) for k,v in d['physics']['em1']['pml']['thickness'].items()}
        r=run(Document.from_dict(other),False)
        np.testing.assert_allclose(r.neff,reference.neff,atol=1e-13,rtol=0)
        for point in r.open_boundary:
            assert len(point['selected_candidates'])==1
            assert sum(c['selected'] for c in point['candidates'])==1


@pytest.mark.parametrize('change',[
    {'pml':{'thickness':{'top':-1}}},
    {'pml':{'thickness':{'top':100}}},
    {'pml':{'thickness':{'top':.5},'order':True}},
    {'pml':{'thickness':{'top':.5},'strength':float('nan')}},
    {'pml':{'thickness':{'top':.5},'min_physical_fraction':2}},
    {'bend':{'radius':.1,'axis':'y'}},
])
def test_invalid_coordinates_rejected(change):
    d=document().data
    d['physics']['em1'].update(change)
    with pytest.raises(DocumentError): Document.from_dict(d)


def test_bent_physical_fields_reconstruct_original_pencil():
    from simcase import build_mesh, solve_point
    from simcase.physics_em_modes2d import vector_pencil_residuals
    d=document('vector',True)
    model=build_mesh(d)
    p=d.sole_physics()[1]
    r=solve_point(model,p)
    residual=vector_pencil_residuals(model.mesh,np.conjugate(model.eps_per_triangle(p['wavelength'])),
                                    p['wavelength'],p['boundary'],r['neff'],r['vector_field'],pml=p['pml'],bend=p['bend'])
    assert residual.max()<1e-10


def test_open_sweep_refuses_real_subspace_method():
    from simcase import ModeTrackingError
    d=document().data
    d['study']=dict(type='sweep',parameter='physics.em1.wavelength',values=[1.549,1.55,1.551],
                    tracking=dict(method='electric-l2-subspace-v1',cluster_span_max=1e-5,external_gap_min=1e-3))
    with pytest.raises(ModeTrackingError,match='requires a real spectrum'):
        run(Document.from_dict(d),False)


def test_leaky_sweep_seeds_the_target_pole_not_highest_substrate_mode():
    data=document('vector').data
    data['materials']['film']={'n':3.48}
    data['geometry']['domain'].update(ymin=-2.,ymax=2.47)
    data['geometry']['shapes'].append(dict(name='substrate',type='rect',x=-.05,y=.47,w=.1,h=2.,material='film'))
    data['physics']['em1']['pml']['thickness']=dict(bottom=1.,top=1.)
    data['mesh']['size']=.02
    data['mesh']['grading'].update(near=.01,far=.02)
    d=Document.from_dict(data)
    d.data['physics']['em1']['wavelength']=1.549
    single=run(d,False)
    d.data['study']=dict(type='sweep',parameter='physics.em1.wavelength',values=[1.549,1.55,1.551])
    sweep=run(d,False)
    np.testing.assert_allclose(sweep.neff[0],single.neff[0],atol=1e-10,rtol=0)
    assert abs(sweep.neff[1,0]-(2.8523269042892405-.0026882226051686553j))<2e-3
