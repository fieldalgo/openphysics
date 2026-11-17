# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Physical far-interaction invariants and explicit admission boundaries."""
import math
import numpy as np
import pytest
from galerkin import laplace_corner_quadratic_far as module
from galerkin.laplace_corner_harmonic_interactions import power_panel_harmonic_far_log

CASES = [([1.,0.],[.3,.4],[8.,2.],.6,.875),
         ([1.,0.],[-1.,0.],[8.,0.],1.,1.),
         ([1/64,0.],[.6,.8],[0.,8.],.6,.8),
         ([1.,0.],[0.,1.],[8.,1.],math.nextafter(.5,1),.500001)]


def close(actual,expected):
    assert np.max(abs(np.asarray(actual)-expected)/np.maximum(1,abs(expected)))<=1e-12


@pytest.mark.parametrize('args',CASES,ids=['oblique','uniform','ratio64','nearhalf'])
@pytest.mark.parametrize('order',[4,32,64])
def test_existing_subspace_physical_masses_and_immutable_results(args,order):
    out=module.power_panel_quadratic_far_log(*args,quadrature_order=order)
    old=power_panel_harmonic_far_log(*args,quadrature_order=order)
    assert out.mean_log_distance[:2,:2].tobytes()==old.mean_log_distance.tobytes()
    assert out.coarse_mean_log_distance[:2,:2].tobytes()==old.coarse_mean_log_distance.tobytes()
    assert out.mass_error<=1e-12 and out.quadrature_order==order
    for value in (out.mean_log_distance,out.coarse_mean_log_distance):
        assert value.shape==(3,3)
        with pytest.raises(ValueError):value[0,0]=0
        with pytest.raises(ValueError):value.flags.writeable=True
        with pytest.raises(ValueError):value.base.flags.writeable=True


@pytest.mark.parametrize('args',CASES,ids=['oblique','uniform','ratio64','nearhalf'])
def test_reciprocity_rigid_transforms_and_physical_logscale(args):
    a,b,o=[np.asarray(v) for v in args[:3]];p,q=args[3:]
    out=module.power_panel_quadratic_far_log(*args).mean_log_distance
    close(module.power_panel_quadratic_far_log(b,a,-o,q,p).mean_log_distance.T,out)
    for transform in [np.diag([1.,-1.]),np.array([[0.,-1.],[1.,0.]])]:
        close(module.power_panel_quadratic_far_log(transform@a,transform@b,transform@o,p,q).mean_log_distance,out)
    for exponent in [-20,20]:
        scale=2**exponent;expected=out.copy();expected[0,0]+=exponent*math.log(2)
        close(module.power_panel_quadratic_far_log(a*scale,b*scale,o*scale,p,q).mean_log_distance,expected)


@pytest.mark.parametrize('bad',[[0.,0.],[np.inf,0.],[np.nan,1.],[1.],[1.,0.,0.],[True,False],['1','0'],[1+0j,0j]])
def test_invalid_vectors_precede_new_integration(bad,monkeypatch):
    monkeypatch.setattr(module,'_block',lambda *a:pytest.fail('new integration started'))
    args=list(CASES[0]);args[0]=bad
    with pytest.raises(ValueError):module.power_panel_quadratic_far_log(*args)


@pytest.mark.parametrize('index',[3,4])
@pytest.mark.parametrize('bad',[.5,1.01,np.inf,np.nan,True,'0.6',[.6],.6+0j])
def test_invalid_exponents(index,bad,monkeypatch):
    monkeypatch.setattr(module,'_block',lambda *a:pytest.fail('new integration started'))
    args=list(CASES[0]);args[index]=bad
    with pytest.raises(ValueError):module.power_panel_quadratic_far_log(*args)


@pytest.mark.parametrize('bad',[3,65,4.5,np.inf,True,'32'])
def test_explicit_order_contract(bad):
    with pytest.raises(ValueError):module.power_panel_quadratic_far_log(*CASES[0],quadrature_order=bad)


@pytest.mark.parametrize('a,b,o',[([1.,0.],[1.,0.],[7.99,0.]),
                                  ([1.,0.],[1/65,0.],[8.,0.]),
                                  ([1.,0.],[1.,0.],[0.,0.])])
def test_geometry_not_repaired(a,b,o,monkeypatch):
    monkeypatch.setattr(module,'_block',lambda *a:pytest.fail('new integration started'))
    with pytest.raises(ValueError):module.power_panel_quadratic_far_log(a,b,o,.6,.8)


@pytest.mark.parametrize('fault',['difference','nan','infinite'])
def test_fault_injected_fine_rule_refuses_without_retry(fault,monkeypatch):
    original=module._block;calls=[]
    def changed(*args):
        block,mass=original(*args);calls.append(args[-1])
        if args[-1]==8:block[2,2]={'difference':block[2,2]+2e-12,'nan':np.nan,'infinite':np.inf}[fault]
        return block,mass
    monkeypatch.setattr(module,'_block',changed)
    with pytest.raises(ValueError,match='quadratic far interaction quadrature'):
        module.power_panel_quadratic_far_log(*CASES[0],quadrature_order=4)
    assert calls==[4,8]


def test_physical_weights_are_not_renormalized(monkeypatch):
    original=module._cached_power_rule;module._rule.cache_clear()
    def changed(p,n):
        points,weights=original(p,n)
        return points,weights*1.01 if p>2 else weights
    monkeypatch.setattr(module,'_cached_power_rule',changed)
    try:
        with pytest.raises(ValueError,match='physical masses'):
            module.power_panel_quadratic_far_log(*CASES[0])
    finally:module._rule.cache_clear()


def test_public_scope_excludes_field_solver_and_near_interactions():
    assert module.__all__==['QuadraticPanelLogResult','power_panel_quadratic_far_log']
