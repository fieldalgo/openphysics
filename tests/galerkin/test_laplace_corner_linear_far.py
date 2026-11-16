# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent analytic-series far blocks and physical transformation identities."""
from pathlib import Path
import json
from dataclasses import FrozenInstanceError
import numpy as np
import pytest
from galerkin.laplace_corner import power_panel_linear_far_log as solve,power_panel_separated_log

DATA=json.loads((Path(__file__).parent/'two_ground/evidence/linear-far-log-integrals.json').read_text())['rows']

def call(row,**kwargs):return solve(row['first'],row['second'],row['offset'],row['p'],row['q'],**kwargs)

@pytest.mark.parametrize('row',DATA,ids=[f'series-{i}' for i in range(len(DATA))])
def test_independent_analytic_moment_series(row,record_property):
    value=call(row);expected=np.asarray(row['reference'],float)
    assert np.all(abs(value.mean_log_distance-expected)<=1e-12*np.maximum(1,abs(expected)))
    assert np.all(abs(value.mean_log_distance-value.coarse_mean_log_distance)<=1e-12*np.maximum(1,abs(value.mean_log_distance)))
    assert float(row['tail_bound'])<1e-40
    record_property('linear_far_log',json.dumps(dict(input=row,fine=value.mean_log_distance.tolist(),coarse=value.coarse_mean_log_distance.tolist(),order=value.quadrature_order),sort_keys=True))

@pytest.mark.parametrize('row',DATA,ids=[f'exchange-{i}' for i in range(len(DATA))])
def test_exchange_transposes_both_basis_modes(row):
    a=call(row).mean_log_distance
    b=solve(row['second'],row['first'],-np.asarray(row['offset']),row['q'],row['p']).mean_log_distance
    np.testing.assert_allclose(a,b.T,rtol=1e-12,atol=1e-14)

@pytest.mark.parametrize('row',DATA,ids=[f'reflect-{i}' for i in range(len(DATA))])
def test_reflection_preserves_every_interaction(row):
    reflect=np.array([-1.,1.]);a=call(row).mean_log_distance
    b=solve(np.array(row['first'])*reflect,np.array(row['second'])*reflect,np.array(row['offset'])*reflect,row['p'],row['q']).mean_log_distance
    np.testing.assert_array_equal(a,b)

@pytest.mark.parametrize('exponent',[-15,15])
@pytest.mark.parametrize('row',DATA,ids=[f'scale-{i}' for i in range(len(DATA))])
def test_only_constant_mass_entry_changes_with_scale(row,exponent):
    factor=2.**exponent;a=call(row).mean_log_distance
    b=solve(np.array(row['first'])*factor,np.array(row['second'])*factor,np.array(row['offset'])*factor,row['p'],row['q']).mean_log_distance
    expected=a.copy();expected[0,0]+=np.log(factor)
    np.testing.assert_allclose(b,expected,rtol=1e-12,atol=1e-14)
    np.testing.assert_array_equal(b.ravel()[1:],a.ravel()[1:])

@pytest.mark.parametrize('row',DATA,ids=[f'constant-{i}' for i in range(len(DATA))])
def test_constant_mode_matches_existing_separated_primitive(row):
    old=power_panel_separated_log(row['first'],row['second'],row['offset'],row['p'],row['q'])
    assert call(row).mean_log_distance[0,0]==pytest.approx(old.mean_log_distance,rel=1e-12,abs=1e-12)


def test_returned_results_are_detached_and_readonly():
    a=np.array([1.,0.]);b=np.array([0.,1.]);o=np.array([8.,0.]);result=solve(a,b,o,2/3,1.)
    old=result.mean_log_distance.copy();a[:]=0;b[:]=0;o[:]=0
    np.testing.assert_array_equal(result.mean_log_distance,old)
    for matrix in (result.mean_log_distance,result.coarse_mean_log_distance):
        with pytest.raises(ValueError):matrix[0,0]=0
        with pytest.raises(ValueError):matrix.setflags(write=True)
    with pytest.raises(FrozenInstanceError):result.quadrature_order=4

@pytest.mark.parametrize('change',[
    dict(first=[0.,0.]),dict(first=[1.,0.,0.]),dict(first=[1j,0]),dict(second=[np.nan,1]),
    dict(offset=[0.,0.]),dict(offset=[7.99,0.]),dict(offset=[np.inf,0.]),dict(second=[1/65,0.]),
    dict(first_exponent=.5),dict(first_exponent=0.),dict(second_exponent=1.0001),dict(second_exponent=np.nan),
    dict(quadrature_order=3),dict(quadrature_order=65),dict(quadrature_order=4.5),dict(quadrature_order=True),
],ids=[f'invalid-{i}' for i in range(16)])
def test_explicit_far_domain_and_numerical_admission(change):
    args=dict(first=[1.,0.],second=[0.,1.],offset=[8.,0.],first_exponent=2/3,second_exponent=1.)
    args.update(change)
    with pytest.raises(ValueError):solve(**args)


def test_insufficient_order_is_refused_without_fallback():
    with pytest.raises(ValueError,match='quadrature did not converge'):
        solve([1.,0.],[0.,1.],[8.,0.],.5001,1.,quadrature_order=4)

@pytest.mark.parametrize('order',[8,16,32,64])
def test_explicit_resolved_orders_retain_the_requested_comparison(order):
    value=solve([1.,0.],[0.,1.],[8.,0.],.5001,1.,quadrature_order=order)
    assert value.quadrature_order==order
    assert np.all(abs(value.mean_log_distance-value.coarse_mean_log_distance)<=1e-12*np.maximum(1,abs(value.mean_log_distance)))
