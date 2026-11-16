# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Closed integrals and physical transformations for disjoint linear panels."""
from dataclasses import FrozenInstanceError
import json
import math
from pathlib import Path

import numpy as np
import pytest

from galerkin.laplace_corner import (
    power_panel_linear_separated_log as solve,
    power_panel_linear_far_log,
    power_panel_separated_log,
)

CASES = [
    ([1.,0.],[1.,0.],[0.,.5],.5001,.5001),
    ([1.,0.],[0.,1.],[1.5,0.],2/3,.875),
    ([1.,0.],[-1/64,0.],[1.515625,0.],1.,.5001),
    ([.3,.4],[-.4,.3],[.6,.8],.6,1.),
    ([1.,0.],[1.,0.],[0.,2.],.875,.6),
]
FAR = json.loads((Path(__file__).parent / "two_ground/evidence/linear-far-log-integrals.json").read_text())["rows"]


@pytest.mark.parametrize("height", [.5,1.,2.])
@pytest.mark.parametrize("scale", [2.**-15,1.,2.**15])
def test_parallel_unit_power_matches_independent_closed_integrals(height, scale):
    # Integrate the difference-coordinate convolution of the two modes.
    # J_k = integral_0^1 t^k log(t^2+h^2) dt, k=0,1,3.
    h = height
    j0 = math.log1p(h*h)-2+2*h*math.atan(1/h)
    j1 = .5*((1+h*h)*math.log1p(h*h)-h*h*math.log(h*h)-1)
    j3 = .25*((1-h**4)*math.log1p(h*h)+h**4*math.log(h*h)-.5+h*h)
    expected = np.array([[math.log(scale)+j0-j1,0.],[0.,j0-3*j1+2*j3]])
    actual = solve([scale,0.],[scale,0.],[0.,h*scale],1.,1.).mean_log_distance
    assert np.all(abs(actual-expected) <= 1e-12*np.maximum(1,abs(expected)))


@pytest.mark.parametrize("case", CASES)
def test_exchange_transposes_fine_and_coarse(case):
    a,b,o,p,q = case
    first = solve(*case)
    other = solve(b,a,-np.array(o),q,p)
    for name in ("mean_log_distance","coarse_mean_log_distance"):
        np.testing.assert_allclose(getattr(first,name),getattr(other,name).T,rtol=1e-12,atol=1e-14)


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("transform", ["reflection","quarter_turn"])
def test_signed_coordinate_transform_is_bit_exact(case, transform):
    a,b,o,p,q = case
    def change(x):
        return np.array(x)*[-1.,1.] if transform == "reflection" else np.array([-x[1],x[0]])
    first = solve(*case)
    other = solve(change(a),change(b),change(o),p,q)
    for name in ("mean_log_distance","coarse_mean_log_distance"):
        np.testing.assert_array_equal(getattr(first,name),getattr(other,name))


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("exponent", [-15,15])
def test_scale_changes_only_constant_mass_entry(case, exponent):
    a,b,o,p,q = case
    scale = 2.**exponent
    first = solve(*case)
    other = solve(np.array(a)*scale,np.array(b)*scale,np.array(o)*scale,p,q)
    for name in ("mean_log_distance","coarse_mean_log_distance"):
        expected = getattr(first,name).copy()
        expected[0,0] += math.log(scale)
        np.testing.assert_allclose(getattr(other,name),expected,rtol=1e-12,atol=1e-14)
        np.testing.assert_array_equal(getattr(other,name).ravel()[1:],getattr(first,name).ravel()[1:])


@pytest.mark.parametrize("case", CASES)
def test_constant_mode_matches_original_power_primitive(case):
    expected = power_panel_separated_log(*case)
    actual = solve(*case)
    for name in ("mean_log_distance","coarse_mean_log_distance"):
        value = getattr(expected,name)
        assert abs(getattr(actual,name)[0,0]-value) <= 1e-12*max(1,abs(value))


@pytest.mark.parametrize("row", FAR)
def test_separate_api_agrees_with_qualified_far_contract(row):
    args = [row[k] for k in ("first","second","offset","p","q")]
    expected = power_panel_linear_far_log(*args)
    actual = solve(*args)
    for name in ("mean_log_distance","coarse_mean_log_distance"):
        value = getattr(expected,name)
        assert np.all(abs(getattr(actual,name)-value) <= 1e-12*np.maximum(1,abs(value)))


def test_returned_blocks_are_detached_and_immutable():
    a,b,o = np.array([1.,0.]),np.array([1.,0.]),np.array([0.,.5])
    result = solve(a,b,o,2/3,1.)
    before = result.mean_log_distance.copy()
    a[:] = 0; b[:] = 0; o[:] = 0
    np.testing.assert_array_equal(result.mean_log_distance,before)
    for block in (result.mean_log_distance,result.coarse_mean_log_distance):
        with pytest.raises(ValueError): block[0,0] = 0
        with pytest.raises(ValueError): block.setflags(write=True)
    with pytest.raises(FrozenInstanceError): result.quadrature_order = 4


@pytest.mark.parametrize("change", [
    {"first":[0.,0.]}, {"second":[0.,0.]}, {"offset":[0.,0.]},
    {"first":[1.,0.,0.]}, {"first":[1j,0.]}, {"first":[True,False]},
    {"offset":[np.inf,0.]}, {"second":[np.nan,0.]},
    {"offset":[0.,.4999]}, {"offset":[.5,0.]},
    {"second":[0.,1.],"offset":[.5,-.5]}, {"second":[1/65,0.]},
    {"first_exponent":.5}, {"second_exponent":1.0001},
    {"first_exponent":np.nan}, {"second_exponent":True},
    {"quadrature_order":3}, {"quadrature_order":65},
    {"quadrature_order":4.5}, {"quadrature_order":True},
    {"first":[1e-300,0.],"second":[1e-300,0.],"offset":[1e300,0.]},
])
def test_explicit_geometric_and_numerical_admission(change):
    inputs = dict(first=[1.,0.],second=[1.,0.],offset=[0.,.5],
                  first_exponent=2/3,second_exponent=1.)
    inputs.update(change)
    with pytest.raises(ValueError): solve(**inputs)


def test_low_requested_order_is_refused_without_retry():
    with pytest.raises(ValueError,match="quadrature did not converge"):
        solve(*CASES[0],quadrature_order=4)


@pytest.mark.parametrize("order", [16,32,64])
def test_explicit_resolved_orders_retain_fine_coarse_evidence(order):
    result = solve(*CASES[0],quadrature_order=order)
    assert result.quadrature_order == order
    assert np.all(abs(result.mean_log_distance-result.coarse_mean_log_distance)
                  <= 1e-12*np.maximum(1,abs(result.mean_log_distance)))
