# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Physical identities and explicit interaction-admission boundaries."""
import math
import numpy as np
import pytest
from galerkin import laplace_corner_harmonic_interactions as module

CASES = {
    'far': (module.power_panel_harmonic_far_log, ([1.,0.],[.3,.4],[8.,2.],.6,.875)),
    'separated': (module.power_panel_harmonic_separated_log, ([1.,0.],[1.,0.],[0.,.5],.6,.875)),
    'vertex': (module.power_panel_harmonic_shared_vertex_log, ([1.,0.],[0.,.3],.6,.875)),
    'mixed': (module.power_panel_harmonic_constant_log_partitioned, ([1.,0.],[.0001,0.],[.5,1e-8],2/3)),
}


def close(actual, expected, bound=1e-12):
    actual,expected=np.asarray(actual),np.asarray(expected)
    delta=abs(actual-expected);scale=np.maximum(abs(actual),abs(expected))
    error=np.divide(delta,scale,out=np.where(delta==0,0.,np.inf),where=scale!=0)
    assert np.isfinite(error).all() and np.max(error)<=bound


@pytest.mark.parametrize('length',[1e-100,.001,1.,1e100])
def test_opposite_uniform_rays_have_closed_integrals(length):
    result=module.power_panel_harmonic_shared_vertex_log([length,0.],[-length,0.],1.,1.)
    cross=2*math.sqrt(3)*(1-math.log(2))/3
    expected=[[math.log(length)+2*math.log(2)-1.5,cross],[cross,1.25-2*math.log(2)]]
    close(result.mean_log_distance,expected)


@pytest.mark.parametrize('kind',list(CASES))
@pytest.mark.parametrize('transform',[np.array([[-1.,0.],[0.,1.]]),np.array([[0.,-1.],[1.,0.]])])
def test_spatial_reflection_and_quarter_turn(kind,transform):
    function,args=CASES[kind];number=2 if kind=='vertex' else 3
    original=function(*args).mean_log_distance
    changed=[transform@np.array(arg) if i<number else arg for i,arg in enumerate(args)]
    close(function(*changed).mean_log_distance,original)


@pytest.mark.parametrize('kind',['far','separated','vertex'])
def test_raw_reciprocity_without_symmetry_average(kind):
    function,args=CASES[kind]
    if kind=='vertex':a,b,p,q=args;reversed_args=(b,a,q,p)
    else:a,b,o,p,q=args;reversed_args=(b,a,-np.array(o),q,p)
    close(function(*args).mean_log_distance,function(*reversed_args).mean_log_distance.T)


@pytest.mark.parametrize('kind',list(CASES))
def test_immutable_results_and_physical_mass(kind):
    function,args=CASES[kind];result=function(*args)
    assert result.mass_error<=1e-12 and 1<=result.subintervals<=128
    for value in (result.mean_log_distance,result.coarse_mean_log_distance):
        with pytest.raises(ValueError):value[0,0]=0
        with pytest.raises(ValueError):value.flags.writeable=True
        with pytest.raises(ValueError):value.base.flags.writeable=True


@pytest.mark.parametrize('kind',list(CASES))
@pytest.mark.parametrize('bad',[[0.,0.],[np.inf,0.],[np.nan,1.],[1.],[1.,0.,0.],[True,False],['1','0'],[1+0j,0j]])
def test_invalid_first_vector_before_integration(kind,bad,monkeypatch):
    function,args=CASES[kind];values=list(args);values[0]=bad
    for name in ('_centered_block','_vertex_block','_mixed_block'):
        monkeypatch.setattr(module,name,lambda *a,**k:pytest.fail('integration started'))
    with pytest.raises(ValueError):function(*values)


@pytest.mark.parametrize('kind',list(CASES))
@pytest.mark.parametrize('bad',[.5,1.01,np.inf,np.nan,True,'0.6',[.6],.6+0j])
def test_invalid_base_exponent(kind,bad):
    function,args=CASES[kind];values=list(args);values[2 if kind=='vertex' else 3]=bad
    with pytest.raises(ValueError):function(*values)


@pytest.mark.parametrize('kind',['far','separated','vertex'])
@pytest.mark.parametrize('bad',[3,65,4.5,np.inf,True,'32'])
def test_explicit_order_domain(kind,bad):
    function,args=CASES[kind]
    with pytest.raises(ValueError):function(*args,quadrature_order=bad)


@pytest.mark.parametrize('kind',['separated','vertex'])
def test_unresolved_requested_order_does_not_retry(kind,monkeypatch):
    function,args=CASES[kind];calls=[];name='_vertex_block' if kind=='vertex' else '_centered_block';original=getattr(module,name)
    def observe(*values):calls.append(values[-1]);return original(*values)
    monkeypatch.setattr(module,name,observe)
    with pytest.raises(ValueError,match='quadrature'):function(*args,quadrature_order=4)
    assert calls==[4,8]


@pytest.mark.parametrize('first,second,offset',[
    ([1.,0.],[1.,0.],[.5,0.]),
    ([1.,0.],[0.,1.],[.5,-.5]),
    ([1.,0.],[1e-7,0.],[0.,.5]),
])
def test_mixed_overlap_crossing_and_length_budget(first,second,offset,monkeypatch):
    monkeypatch.setattr(module,'_mixed_block',lambda *a,**k:pytest.fail('integration started'))
    with pytest.raises(ValueError):module.power_panel_harmonic_constant_log_partitioned(first,second,offset,2/3)


def test_mixed_partition_budget_precedes_integration(monkeypatch):
    monkeypatch.setattr(module,'_mixed_block',lambda *a,**k:pytest.fail('integration started'))
    with pytest.raises(ValueError,match='128 intervals'):
        module.power_panel_harmonic_constant_log_partitioned([1.,0.],[.0001,0.],[.5,1e-30],2/3)


@pytest.mark.parametrize('kind',list(CASES))
def test_bad_physical_mass_is_not_rescaled(kind,monkeypatch):
    module._rule.cache_clear()
    name='_cached_graded_rule' if kind=='mixed' else '_cached_power_rule';original=getattr(module,name)
    def changed(p,n):x,w=original(p,n);return x,w*1.000001
    monkeypatch.setattr(module,name,changed)
    function,args=CASES[kind]
    with pytest.raises(ValueError,match='mass'):function(*args)
    module._rule.cache_clear()


@pytest.mark.parametrize('fault',['finite_mismatch','nonfinite'])
def test_mixed_fixed_rule_refusal_has_no_hidden_retry(fault,monkeypatch):
    original=module._mixed_block;calls=[]
    def changed(*args):
        value,mass=original(*args);calls.append(args[-2])
        if args[-2]==64:value[0,0]+=1e-4 if fault=='finite_mismatch' else np.nan
        return value,mass
    monkeypatch.setattr(module,'_mixed_block',changed)
    function,args=CASES['mixed']
    with pytest.raises(ValueError,match='quadrature'):function(*args)
    assert calls==[64,128]


@pytest.mark.parametrize('kind',['far','separated','vertex'])
def test_geometric_domain_is_not_repaired(kind,monkeypatch):
    for name in ('_centered_block','_vertex_block'):
        monkeypatch.setattr(module,name,lambda *a,**k:pytest.fail('integration started'))
    if kind=='far':
        with pytest.raises(ValueError,match='far offset'):module.power_panel_harmonic_far_log([1.,0.],[1.,0.],[7.99,0.],.7,.8)
    elif kind=='separated':
        with pytest.raises(ValueError,match='separation'):module.power_panel_harmonic_separated_log([1.,0.],[1.,0.],[0.,.499],.7,.8)
    else:
        with pytest.raises(ValueError,match='overlap'):module.power_panel_harmonic_shared_vertex_log([1.,0.],[.5,0.],.7,.8)
