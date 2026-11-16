# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent Green means, physical invariants and strict input admission."""
from dataclasses import FrozenInstanceError
import json
import math
from pathlib import Path
import numpy as np
import pytest
from galerkin.laplace_half_space import power_constant_half_space
from galerkin.laplace_corner import _graded_power_rule

DATA=json.loads((Path(__file__).parent/'two_ground/evidence/power-half-space-integrals.json').read_text())

@pytest.mark.parametrize('row',DATA['cases'],ids=lambda r:r['name'])
@pytest.mark.parametrize('operation',['identity','reflect','half-scale','double-scale'])
def test_independent_half_space_reference(row,operation,record_property):
    a,b,o=[np.array(row[k],dtype=float) for k in ('a','b','offset')];h=row['height'];p=row['p']
    if operation=='reflect':a,b,o=[v*[-1,1] for v in (a,b,o)]
    if operation.endswith('scale'):
        scale=.5 if operation=='half-scale' else 2.;a,b,o=[v*scale for v in (a,b,o)];h*=scale
    before=[v.tobytes() for v in (a,b,o)];weights={n:tuple(x.tobytes() for x in _graded_power_rule(p,n)) for n in (64,128)}
    result=power_constant_half_space(a,b,o,p,height=h);expected=float(row['reference_values'][-1])
    assert abs(result.green_mean-expected)<=1e-12*max(1,abs(expected))
    assert result.quadrature_order==64 and result.refinement_error<=1e-12
    assert before==[v.tobytes() for v in (a,b,o)]
    assert all(tuple(x.tobytes() for x in _graded_power_rule(p,n))==weights[n] for n in weights)
    record_property('half_space_reference',json.dumps(dict(case=row['name'],operation=operation,expected=expected,mean=result.green_mean,coarse=result.coarse_green_mean,error=result.refinement_error),sort_keys=True))

@pytest.mark.parametrize('p',[.5001,.625,2/3,.875,1.])
@pytest.mark.parametrize('scale',[1e-100,1.,1e100])
def test_source_reversal_scale_and_ground_translation(p,scale):
    a,b,o=np.array([.125,.0625]),np.array([.0625,-.125]),np.array([.25,.125]);h=.5
    result=power_constant_half_space(a,b,o,p,height=h)
    reversed_=power_constant_half_space(a,-b,o+b,p,height=h)
    scaled=power_constant_half_space(a*scale,b*scale,o*scale,p,height=h*scale)
    higher=power_constant_half_space(a,b,o,p,height=2*h)
    assert result.green_mean>0 and higher.green_mean>result.green_mean
    assert abs(reversed_.green_mean-result.green_mean)<=1e-12*max(1,abs(result.green_mean))
    assert abs(scaled.green_mean-result.green_mean)<=1e-12*max(1,abs(result.green_mean))

@pytest.mark.parametrize('a,b,o',[([.125,0],[0,.0625],[0,0]),([.125,0],[.125,0],[.125,0]),([.125,.0625],[.0625,-.125],[.25,.125])])
def test_constant_density_reciprocity(a,b,o):
    result=power_constant_half_space(a,b,o,1.,height=.5)
    transposed=power_constant_half_space(b,a,-np.asarray(o),1.,height=.5+o[1])
    assert abs(result.green_mean-transposed.green_mean)<=1e-12*max(1,abs(result.green_mean))

@pytest.mark.parametrize('bad',[[np.nan,0.],[np.inf,0.],[1.],[1,2,3],[True,False],['1','0'],[1+0j,0]])
@pytest.mark.parametrize('which',[0,1,2])
def test_invalid_planar_inputs(bad,which):
    args=[[1.,0.],[1.,0.],[2.,0.]];args[which]=bad
    with pytest.raises(ValueError):power_constant_half_space(*args,.75,height=1.)

@pytest.mark.parametrize('bad',[np.nan,np.inf,-np.inf,True,'1',1+0j,[1.]])
def test_invalid_height_type(bad):
    with pytest.raises(ValueError):power_constant_half_space([1,0],[1,0],[2,0],.75,height=bad)

@pytest.mark.parametrize('p',[0.,.5,1.01,np.nan,np.inf,True,'0.75',.75+0j,[.75]])
def test_invalid_power(p):
    with pytest.raises(ValueError):power_constant_half_space([1,0],[1,0],[2,0],p,height=1.)

@pytest.mark.parametrize('a,b,o,h',[
    ([1,0],[1,0],[2,0],0),([1,-1],[1,0],[2,0],1),
    ([1,0],[1,0],[2,-1],1),([1,0],[1,-1],[2,0],1),
    ([0,0],[1,0],[2,0],1),([1,0],[1e-7,0],[2,0],1),
    ([1,0],[1,0],[1e20,0],1),([1,0],[1,0],[2,0],1e-20),
    ([1,0],[1,0],[2,0],1e308),([1e308,1e308],[1e308,1e308],[0,0],1.),
])
def test_ground_and_resolution_contract(a,b,o,h):
    with pytest.raises(ValueError):power_constant_half_space(a,b,o,.75,height=h)

@pytest.mark.parametrize('a,b,o',[([1,0],[1,0],[0,0]),([1,0],[-1,0],[1,0]),([1,0],[0,1],[.5,-.5]),([1,0],[1,0],[.5,0])])
def test_overlap_and_crossing_rejected(a,b,o):
    with pytest.raises(ValueError):power_constant_half_space(a,b,o,.75,height=2.)

@pytest.mark.parametrize('relation',['gap','contact','overlap'])
def test_binary_topology_is_not_snapped(relation):
    o=1. if relation=='contact' else np.nextafter(1.,math.inf if relation=='gap' else 0.)
    if relation=='overlap':
        with pytest.raises(ValueError,match='overlapping'):power_constant_half_space([1,0],[1,0],[o,0],.75,height=1.)
    else:assert power_constant_half_space([1,0],[1,0],[o,0],.75,height=1.).refinement_error<=1e-12


def test_result_immutable_and_order_fixed():
    result=power_constant_half_space([1,0],[1,0],[1,0],.75,height=1.)
    with pytest.raises(FrozenInstanceError):result.green_mean=0.
    with pytest.raises(TypeError):power_constant_half_space([1,0],[1,0],[1,0],.75,height=1.,quadrature_order=32)


def test_failed_normalization_is_refused(monkeypatch):
    import galerkin.laplace_half_space as module
    def corrupt(p,n):
        x,w=_graded_power_rule(p,n);return x,w*1.001
    monkeypatch.setattr(module,'_graded_power_rule',corrupt)
    with pytest.raises(ValueError,match='normalization'):power_constant_half_space([1,0],[1,0],[1,0],.75,height=1.)


def test_unresolved_near_pair_is_refused():
    with pytest.raises(ValueError,match='did not converge'):power_constant_half_space([1,0],[1,0],[.5,1e-6],.75,height=1.)


@pytest.mark.parametrize('height',[1e-8,1e-10,1e-12])
def test_cancellation_does_not_return_nonpositive_green(height):
    # The exact log1p kernel is positive everywhere above the ground.
    with pytest.raises(ValueError,match='positive half-space'):
        power_constant_half_space([1,0],[1,0],[2,0],.75,height=height)
