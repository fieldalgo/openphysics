# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Physical masses, transformations, old-method overlap and bounded refusals."""
import math

import numpy as np
import pytest

from galerkin.laplace_corner import power_panel_linear_constant_log
from galerkin.laplace_corner_partitioned import power_panel_linear_constant_log_partitioned as solve
from galerkin import laplace_corner_partitioned as module

CASES = [([1.,0.],[1.,0.],[1.,0.],2/3),
         ([1.,0.],[-1.,0.],[0.,0.],2/3),
         ([1.,0.],[0.,1.],[0.,0.],.5001),
         ([.3,.4],[-.4,.3],[0.,0.],.6),
         ([1.,0.],[1.,0.],[0.,.5],.875),
         ([1.,0.],[1/64,0.],[1.,0.],1.),
         ([1.,0.],[1.,0.],[8.,1.],2/3)]


def close(actual, expected):
    assert np.all(abs(actual-expected) <= 1e-12*np.maximum(1,abs(expected)))


@pytest.mark.parametrize('args',CASES)
def test_existing_unpartitioned_overlap_keeps_physical_modes(args):
    result=solve(*args);old=power_panel_linear_constant_log(*args)
    close(result.mean_log_distance,old.mean_log_distance)
    close(result.coarse_mean_log_distance,result.mean_log_distance)
    assert result.quadrature_order==64 and 1<=result.subintervals<=128
    assert result.mass_error<=1e-12


@pytest.mark.parametrize('args',CASES)
@pytest.mark.parametrize('scale',[2.**-15,2.**15])
def test_physical_scaling_adds_log_only_to_constant_mass_entry(args,scale):
    a,b,o,p=args;expected=solve(a,b,o,p).mean_log_distance.copy()
    expected[0,0]+=math.log(scale)
    changed=solve(np.array(a)*scale,np.array(b)*scale,np.array(o)*scale,p)
    close(changed.mean_log_distance,expected)


@pytest.mark.parametrize('args',CASES)
def test_source_reversal_and_rigid_reflection_preserve_mode_sign(args):
    a,b,o,p=args;a,b,o=map(np.array,(a,b,o));base=solve(a,b,o,p)
    reversed_source=solve(a,-b,o+b,p)
    close(reversed_source.mean_log_distance,base.mean_log_distance*[1,-1])
    reflected=solve(a*[-1,1],b*[-1,1],o*[-1,1],p)
    close(reflected.mean_log_distance,base.mean_log_distance)


@pytest.mark.parametrize('offset',[[0.,.5],[1.,0.],[.5,.001]])
def test_uniform_target_reversal_and_reciprocity(offset):
    a=np.array([1.,0.]);b=np.array([.25,0.]);o=np.array(offset)
    result=solve(a,b,o,1.)
    close(solve(-a,b,o-a,1.).mean_log_distance,
          result.mean_log_distance*np.array([1,-1])[:,None])
    close(solve(b,a,-o,1.).mean_log_distance,result.mean_log_distance.T)


@pytest.mark.parametrize('source_length',[1/64,.001,.0001])
@pytest.mark.parametrize('separation',[.001,1e-5,1e-8])
def test_localized_source_is_explicitly_resolved_while_old_method_stays_refused(source_length,separation):
    args=([1.,0.],[source_length,0.],[.5,separation],2/3)
    with pytest.raises(ValueError,match='quadrature'):power_panel_linear_constant_log(*args)
    result=solve(*args)
    assert result.mass_error<=1e-12 and result.subintervals<=128
    close(result.coarse_mean_log_distance,result.mean_log_distance)


@pytest.mark.parametrize('p',[.5001,4/7,2/3,.875,1.])
@pytest.mark.parametrize('order',[64,128])
def test_partitioned_physical_measure_keeps_analytic_moments(p,order):
    cuts=module._partition(np.array([-1.,0.]),np.array([-.2,.2]),np.array([-.142857142857143,.142857142857142]))
    moments=[]
    for degree in range(3):
        terms=[]
        for left,right in zip(cuts,cuts[1:]):
            span=right-left
            if left==0:
                t,w=module._graded_power_rule(p,order);u=span*t;weights=w*span**p
            else:
                t,w=module._graded_power_rule(1.,order);u=left+span*t;weights=w*p*u**(p-1)*span
            terms.extend(weights*u**degree)
        moments.append(math.fsum(terms))
    np.testing.assert_allclose(moments,[p/(p+k) for k in range(3)],rtol=1e-12,atol=0)
    assert cuts[0]==0 and cuts[-1]==1 and np.all(np.diff(cuts)>0)
    assert all(right<=2*left for left,right in zip(cuts,cuts[1:]) if left>0)


def test_immutable_outputs_do_not_alias_input_arrays():
    a=np.array([1.,0.]);result=solve(a,[1.,0.],[0.,.5],2/3)
    before=result.mean_log_distance.copy();a[:]=0
    assert np.array_equal(before,result.mean_log_distance)
    for value in (result.mean_log_distance,result.coarse_mean_log_distance):
        with pytest.raises(ValueError):value.flat[0]=0
        with pytest.raises(ValueError):value.flags.writeable=True


@pytest.mark.parametrize('p',[.5,0,1.01,np.nan,np.inf,True,1j,[.6]])
def test_invalid_exponent_refused(p):
    with pytest.raises(ValueError):solve([1.,0.],[1.,0.],[0.,1.],p)


@pytest.mark.parametrize('position',range(3))
@pytest.mark.parametrize('value',[[1.],[[1.,0.]],[np.nan,0.],[np.inf,0.],[True,False],[1j,0.],['1','0']])
def test_invalid_planar_vector_refused(position,value):
    args=[[1.,0.],[1.,0.],[0.,1.]];args[position]=value
    with pytest.raises(ValueError):solve(*args,2/3)


@pytest.mark.parametrize('a,b,o',[([0.,0.],[1.,0.],[0.,1.]),
    ([1.,0.],[1e-7,0.],[0.,1.]),([1.,0.],[1.,0.],[.5,0.]),
    ([1.,0.],[0.,1.],[.5,-.5])])
def test_zero_length_ratio_overlap_and_crossing_are_refused(a,b,o):
    with pytest.raises(ValueError):solve(a,b,o,2/3)


def test_dyadic_budget_is_finite_without_a_distance_floor():
    with pytest.raises(ValueError,match='128 intervals'):
        solve([1.,0.],[.0001,0.],[.5,1e-30],2/3)


def test_physical_mass_failure_is_not_renormalized(monkeypatch):
    original=module._graded_power_rule
    def changed(p,n):
        x,w=original(p,n);return x,w*1.000001
    monkeypatch.setattr(module,'_graded_power_rule',changed)
    with pytest.raises(ValueError,match='mass'):solve([1.,0.],[1.,0.],[0.,.5],2/3)


@pytest.mark.parametrize('fault',['refinement','nonfinite'])
def test_explicit_refinement_failure_has_no_retry(monkeypatch,fault):
    original=module._integrate;calls=[]
    def changed(*args):
        calls.append(args[-2]);matrix,mass=original(*args)
        if args[-2]==64:matrix[0,0]+=1e-4 if fault=='refinement' else np.nan
        return matrix,mass
    monkeypatch.setattr(module,'_integrate',changed)
    with pytest.raises(ValueError,match='quadrature'):solve([1.,0.],[1.,0.],[0.,.5],2/3)
    assert calls==[64,128]
