# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Edge contracts and physical transformations, not material laws."""
import dataclasses
import numpy as np
import pytest
import galerkin.laplace_two_ground as module


def polygons():
    return [np.array([[.00345,.00075],[.00385,.00075],[.00385,.0008],[.00345,.0008]]),
            np.array([[.00415,.0011],[.00465,.0011],[.00465,.00117],[.00415,.00117]])]


def solve(p=None, **kwargs):
    args=dict(width=.008,height=.002,panels_per_edge=32,interpolation_degree=14)
    args.update(kwargs)
    return module.solve_two_ground_rectangle_edges(polygons() if p is None else p, **args)


@pytest.fixture(scope='module')
def result():
    return solve()


def test_one_original_solve_and_exact_whole_result(monkeypatch):
    old=module.solve_two_ground_rectangle(polygons(),width=.008,height=.002,
                                         panels_per_edge=32,interpolation_degree=14)
    original=module._solve;calls=[]
    def counted(*args,**kwargs):
        calls.append(1)
        return original(*args,**kwargs)
    monkeypatch.setattr(module,'_solve',counted)
    new=solve()
    assert calls==[1]
    for field in dataclasses.fields(old):
        np.testing.assert_array_equal(getattr(new.whole,field.name),getattr(old,field.name))


def test_edges_have_physical_endpoints_and_conserved_currents(result):
    p=polygons()
    np.testing.assert_array_equal(result.edge_owners,[0]*4+[1]*4)
    np.testing.assert_allclose(result.edge_starts,np.concatenate(p),rtol=0,atol=1e-18)
    np.testing.assert_allclose(result.edge_ends,np.concatenate([np.roll(x,-1,axis=0) for x in p]),rtol=0,atol=1e-18)
    assert result.partition_error<=1e-10
    for owner in range(2):
        selected=result.edge_owners==owner
        np.testing.assert_allclose(result.edge_current_gram[selected].sum(axis=0),
                                   result.whole.current_gram[owner],rtol=1e-10,atol=0)
        np.testing.assert_allclose(result.edge_current_integrals[selected].sum(axis=0),
                                   np.eye(2)[owner],rtol=0,atol=1e-10)
    np.testing.assert_allclose(result.edge_current_gram,result.edge_current_gram.swapaxes(1,2),rtol=1e-10,atol=0)
    scale=np.max(abs(result.edge_current_gram),axis=(1,2))
    assert np.min(np.linalg.eigvalsh(result.edge_current_gram)/scale[:,None])>=-1e-10


@pytest.mark.parametrize('field',['edge_owners','edge_starts','edge_ends',
                                  'edge_current_gram','edge_current_integrals'])
def test_edges_are_immutable_snapshots(result,field):
    a=getattr(result,field)
    with pytest.raises(ValueError):a.setflags(write=True)
    with pytest.raises(ValueError):a.flat[0]=0
    with pytest.raises(dataclasses.FrozenInstanceError):setattr(result,field,a.copy())


def test_input_edit_does_not_change_edge_snapshot():
    p=polygons();value=solve(p);before=value.edge_starts.copy()
    for item in p:item[:]=0
    np.testing.assert_array_equal(value.edge_starts,before)


@pytest.mark.parametrize('operation',['scale','mirror-x','mirror-y','permutation','clockwise','cyclic'])
def test_edge_physical_transformations(result,operation):
    p=polygons();w=.008;h=.002
    if operation=='scale':p=[x*2 for x in p];w*=2;h*=2
    if operation=='mirror-x':p=[x*[-1,1]+[w,0] for x in p]
    if operation=='mirror-y':p=[x*[1,-1]+[0,h] for x in p]
    if operation=='permutation':p=p[::-1]
    if operation=='clockwise':p=[x[::-1] for x in p]
    if operation=='cyclic':p=[np.roll(x,i+1,axis=0) for i,x in enumerate(p)]
    after=solve(p,width=w,height=h)
    starts=after.edge_starts.copy();ends=after.edge_ends.copy()
    gram=after.edge_current_gram.copy();currents=after.edge_current_integrals.copy()
    owners=after.edge_owners.copy();cap=after.whole.capacitance_per_permittivity.copy()
    if operation=='scale':starts/=2;ends/=2;gram*=2
    if operation=='mirror-x':starts=starts*[-1,1]+[w,0];ends=ends*[-1,1]+[w,0]
    if operation=='mirror-y':starts=starts*[1,-1]+[0,h];ends=ends*[1,-1]+[0,h]
    if operation=='permutation':owners=1-owners;gram=gram[:,::-1,::-1];currents=currents[:,::-1];cap=cap[::-1,::-1]
    order=[]
    for owner,start,end in zip(result.edge_owners,result.edge_starts,result.edge_ends):
        matches=[]
        for j,(a,b,o) in enumerate(zip(starts,ends,owners)):
            if o!=owner:continue
            same=max(abs(a-start).max(),abs(b-end).max())<=1e-15
            reverse=max(abs(b-start).max(),abs(a-end).max())<=1e-15
            if same or reverse:matches.append(j)
        assert len(matches)==1
        order.extend(matches)
    assert len(set(order))==len(order)
    np.testing.assert_allclose(gram[order],result.edge_current_gram,rtol=1e-10,atol=0)
    np.testing.assert_allclose(currents[order],result.edge_current_integrals,rtol=0,atol=1e-10)
    np.testing.assert_allclose(cap,result.whole.capacitance_per_permittivity,rtol=1e-10,atol=0)


def test_triangle_has_three_edges_without_rectangular_assumption():
    p=np.array([[.0037,.0007],[.0043,.0007],[.004,.0013]])
    value=solve([p])
    assert value.edge_current_gram.shape==(3,1,1)
    np.testing.assert_array_equal(value.edge_owners,[0,0,0])
    np.testing.assert_allclose(value.edge_starts,p,rtol=0,atol=1e-18)
    np.testing.assert_allclose(value.edge_current_integrals.sum(axis=0),1.,rtol=0,atol=1e-10)


@pytest.mark.parametrize('field,value',[
    ('width',0),('height',True),('panels_per_edge',257),('panels_per_edge',1.5),
    ('ground_modes',63),('interpolation_degree',11)])
def test_new_api_keeps_original_early_admission(monkeypatch,field,value):
    monkeypatch.setattr(module.kernel,'panels',lambda *a,**k:pytest.fail('field solve reached'))
    with pytest.raises(ValueError):solve(**{field:value})


def test_new_api_keeps_original_ground_refinement_refusal(monkeypatch):
    original=module._factors;calls=[]
    def changed(*args,**kwargs):
        calls.append(kwargs['modes']);value=original(*args,**kwargs)
        if kwargs['modes']==256:value['ground_parts']*=1.001
        return value
    monkeypatch.setattr(module,'_factors',changed)
    with pytest.raises(ValueError,match='ground Fourier'):solve()
    assert calls==[128,256]
