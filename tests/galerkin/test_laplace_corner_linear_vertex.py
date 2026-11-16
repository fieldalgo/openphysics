# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Closed-form and adaptive references for linear shared-vertex log blocks."""
from pathlib import Path
import json,math
from dataclasses import FrozenInstanceError
import numpy as np
import pytest
from galerkin.laplace_corner import power_panel_linear_shared_vertex_log as solve,power_panel_shared_vertex_log

DATA=json.loads((Path(__file__).parent/'two_ground/evidence/linear-vertex-log-integrals.json').read_text())['cases']

def call(row,order=64):return solve(row['first'],row['second'],row['p'],row['q'],quadrature_order=order)

@pytest.mark.parametrize('row',DATA,ids=[f'adaptive-{i}' for i in range(len(DATA))])
def test_stored_adaptive_reference_and_original_entrywise_gate(row,record_property):
    value=call(row);expected=np.array(row['reference'],float)
    assert np.all(abs(value.mean_log_distance-expected)<=1e-12*np.maximum(1,abs(expected)))
    assert np.all(abs(value.mean_log_distance-value.coarse_mean_log_distance)<=1e-12*np.maximum(1,abs(value.mean_log_distance)))
    assert value.quadrature_order==64
    record_property('linear_vertex_log',json.dumps(dict(input=row,fine=value.mean_log_distance.tolist(),coarse=value.coarse_mean_log_distance.tolist(),order=value.quadrature_order),sort_keys=True))

@pytest.mark.parametrize('length',[2.**-15,.001,1.,2.,2.**15])
def test_equal_opposite_unit_power_matches_closed_form(length):
    actual=solve([length,0.],[-length,0.],1.,1.).mean_log_distance
    off=2*math.sqrt(3)*(1-math.log(2))/3
    exact=np.array([[math.log(length)+2*math.log(2)-1.5,off],[off,1.25-2*math.log(2)]])
    assert np.all(abs(actual-exact)<=1e-12*np.maximum(1,abs(exact)))

@pytest.mark.parametrize('row',DATA,ids=[f'exchange-{i}' for i in range(len(DATA))])
def test_exchange_transposes_all_four_mode_integrals(row):
    other=solve(row['second'],row['first'],row['q'],row['p'],quadrature_order=64)
    np.testing.assert_allclose(call(row).mean_log_distance,other.mean_log_distance.T,rtol=1e-12,atol=1e-14)

@pytest.mark.parametrize('row',DATA,ids=[f'reflect-{i}' for i in range(len(DATA))])
def test_reflection_is_bit_exact(row):
    r=np.array([-1.,1.]);other=solve(np.array(row['first'])*r,np.array(row['second'])*r,row['p'],row['q'],quadrature_order=64)
    np.testing.assert_array_equal(call(row).mean_log_distance,other.mean_log_distance)

@pytest.mark.parametrize('exponent',[-15,15])
@pytest.mark.parametrize('row',DATA,ids=[f'scale-{i}' for i in range(len(DATA))])
def test_scale_only_changes_constant_mass_entry(row,exponent):
    factor=2.**exponent;old=call(row).mean_log_distance
    value=solve(np.array(row['first'])*factor,np.array(row['second'])*factor,row['p'],row['q'],quadrature_order=64).mean_log_distance
    expected=old.copy();expected[0,0]+=math.log(factor)
    np.testing.assert_allclose(value,expected,rtol=1e-12,atol=1e-14)
    np.testing.assert_array_equal(old.ravel()[1:],value.ravel()[1:])

@pytest.mark.parametrize('row',DATA,ids=[f'constant-{i}' for i in range(len(DATA))])
def test_constant_mode_matches_original_shared_vertex_primitive(row):
    old=power_panel_shared_vertex_log(row['first'],row['second'],row['p'],row['q'],quadrature_order=64)
    assert call(row).mean_log_distance[0,0]==pytest.approx(old.mean_log_distance,rel=1e-12,abs=1e-12)


def test_accepted_domain_can_refuse_unresolved_order_without_retry():
    row=DATA[4]
    with pytest.raises(ValueError,match='quadrature did not converge'):call(row,order=32)
    assert call(row,order=64).quadrature_order==64


def test_result_arrays_are_detached_and_immutable():
    a=np.array([1.,0.]);b=np.array([0.,1.]);value=solve(a,b,2/3,2/3);old=value.mean_log_distance.copy();a[:]=0;b[:]=0
    np.testing.assert_array_equal(value.mean_log_distance,old)
    for matrix in (value.mean_log_distance,value.coarse_mean_log_distance):
        with pytest.raises(ValueError):matrix[0,0]=0
        with pytest.raises(ValueError):matrix.setflags(write=True)
    with pytest.raises(FrozenInstanceError):value.quadrature_order=4

@pytest.mark.parametrize('change',[
    dict(first=[0.,0.]),dict(first=[1.,0.,0.]),dict(first=[1j,0]),dict(second=[np.nan,1]),
    dict(second=[1.,0.]),dict(second=[.5,0.]),dict(first=[np.inf,0.]),dict(second=[0.,1/65]),
    dict(first_exponent=.5),dict(first_exponent=0.),dict(second_exponent=1.0001),dict(second_exponent=np.nan),
    dict(quadrature_order=3),dict(quadrature_order=65),dict(quadrature_order=4.5),dict(quadrature_order=True),
],ids=[f'invalid-{i}' for i in range(16)])
def test_nonoverlap_finite_power_and_order_admission(change):
    args=dict(first=[1.,0.],second=[0.,1.],first_exponent=2/3,second_exponent=1.)
    args.update(change)
    with pytest.raises(ValueError):solve(**args)
