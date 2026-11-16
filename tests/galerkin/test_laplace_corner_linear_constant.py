# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Orientation, endpoint and physical-mass contracts for mixed linear blocks."""
from dataclasses import FrozenInstanceError
import math

import numpy as np
import pytest

from galerkin.laplace_corner import (
    power_panel_linear_constant_log as solve,
    power_panel_constant_log,
    power_panel_linear_shared_vertex_log,
    power_panel_linear_far_log,
    _constant_linear_segment_log,
)

CASES = [
    ([1.,0.],[1.,0.],[1.,0.],2/3),
    ([1.,0.],[-1.,0.],[0.,0.],2/3),
    ([1.,0.],[0.,1.],[0.,0.],.5001),
    ([.3,.4],[-.4,.3],[0.,0.],.6),
    ([1.,0.],[1.,0.],[0.,.5],.875),
    ([1.,0.],[1/64,0.],[1.,0.],1.),
    ([1.,0.],[1.,0.],[8.,1.],2/3),
]


@pytest.mark.parametrize("case", CASES)
def test_constant_mode_preserves_original_power_constant_integral(case):
    expected = power_panel_constant_log(*case)
    actual = solve(*case)
    assert actual.quadrature_order == 64
    for name in ("mean_log_distance","coarse_mean_log_distance"):
        value = getattr(expected,name)
        assert abs(getattr(actual,name)[0,0]-value) <= 1e-12*max(1,abs(value))


@pytest.mark.parametrize("case", CASES[1:4])
def test_common_origin_matches_separate_duffy_primitive(case):
    a,b,o,p = case
    expected = power_panel_linear_shared_vertex_log(a,b,p,1.,quadrature_order=64)
    actual = solve(*case)
    assert np.all(abs(actual.mean_log_distance-expected.mean_log_distance)
                  <= 1e-12*np.maximum(1,abs(expected.mean_log_distance)))


def test_far_overlap_preserves_both_source_modes():
    a,b,o,p = CASES[-1]
    expected = power_panel_linear_far_log(a,b,o,p,1.)
    actual = solve(*CASES[-1])
    assert np.all(abs(actual.mean_log_distance-expected.mean_log_distance)
                  <= 1e-12*np.maximum(1,abs(expected.mean_log_distance)))


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("transform", ["reflection","quarter_turn"])
def test_signed_coordinate_transform_preserves_integrals(case, transform):
    a,b,o,p = case
    def change(x):
        return np.array(x)*[-1.,1.] if transform == "reflection" else np.array([-x[1],x[0]])
    expected = solve(*case)
    actual = solve(change(a),change(b),change(o),p)
    for name in ("mean_log_distance","coarse_mean_log_distance"):
        np.testing.assert_array_equal(getattr(actual,name),getattr(expected,name))


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("exponent", [-15,15])
def test_physical_scale_affects_only_constant_mass_block(case, exponent):
    a,b,o,p = case; scale = 2.**exponent
    before = solve(*case)
    actual = solve(np.array(a)*scale,np.array(b)*scale,np.array(o)*scale,p)
    for name in ("mean_log_distance","coarse_mean_log_distance"):
        expected = getattr(before,name).copy(); expected[0,0] += math.log(scale)
        np.testing.assert_allclose(getattr(actual,name),expected,rtol=1e-12,atol=1e-14)
        np.testing.assert_array_equal(getattr(actual,name).ravel()[1:],getattr(before,name).ravel()[1:])


@pytest.mark.parametrize("case", CASES)
def test_source_reversal_flips_only_linear_source_mode(case):
    a,b,o,p = case
    before = solve(*case)
    actual = solve(a,-np.array(b),np.array(o)+b,p)
    for name in ("mean_log_distance","coarse_mean_log_distance"):
        expected = getattr(before,name)*np.array([1.,-1.])[None,:]
        np.testing.assert_allclose(getattr(actual,name),expected,rtol=1e-12,atol=1e-14)


@pytest.mark.parametrize("case", CASES)
def test_unit_power_target_reversal_flips_only_its_linear_mode(case):
    a,b,o,_ = case
    before = solve(a,b,o,1.)
    actual = solve(-np.array(a),b,np.array(o)-a,1.)
    expected = np.array([1.,-1.])[:,None]*before.mean_log_distance
    np.testing.assert_allclose(actual.mean_log_distance,expected,rtol=1e-12,atol=1e-14)


@pytest.mark.parametrize("case", CASES)
def test_unit_power_exchange_transposes_block(case):
    a,b,o,_ = case
    expected = solve(a,b,o,1.)
    actual = solve(b,a,-np.array(o),1.)
    np.testing.assert_allclose(actual.mean_log_distance,expected.mean_log_distance.T,rtol=1e-12,atol=1e-14)


@pytest.mark.parametrize("z,expected", [(0.,.5),(-1.,-.5),(-.5,0.)])
def test_source_endpoint_limits_and_center_symmetry(z, expected):
    assert float(_constant_linear_segment_log(z)) == expected


def test_returned_blocks_are_detached_and_immutable():
    a,b,o = np.array([1.,0.]),np.array([1.,0.]),np.array([1.,0.])
    result = solve(a,b,o,2/3); before = result.mean_log_distance.copy()
    a[:] = 0; b[:] = 0; o[:] = 0
    np.testing.assert_array_equal(result.mean_log_distance,before)
    for block in (result.mean_log_distance,result.coarse_mean_log_distance):
        with pytest.raises(ValueError): block[0,0] = 0
        with pytest.raises(ValueError): block.setflags(write=True)
    with pytest.raises(FrozenInstanceError): result.quadrature_order = 32


@pytest.mark.parametrize("change", [
    {"a":[0.,0.]}, {"b":[0.,0.]}, {"a":[1.,0.,0.]}, {"b":[1j,0.]},
    {"a":[True,False]}, {"offset":[np.inf,0.]}, {"a":[np.nan,0.]},
    {"offset":[0.,0.]}, {"offset":[.5,0.]},
    {"b":[0.,1.],"offset":[.5,-.5]},
    {"b":[1e-7,0.]}, {"exponent":.5}, {"exponent":1.0001},
    {"exponent":np.inf}, {"exponent":True},
    {"a":[1e-300,0.],"b":[1e-300,0.],"offset":[1e300,0.]},
])
def test_exact_topology_and_input_admission(change):
    inputs = dict(a=[1.,0.],b=[1.,0.],offset=[1.,0.],exponent=2/3)
    inputs.update(change)
    with pytest.raises(ValueError): solve(**inputs)


@pytest.mark.parametrize("length", [1/64,1e-3,1e-4])
def test_localized_unresolved_interaction_is_refused_without_retry(length):
    with pytest.raises(ValueError,match="quadrature did not converge"):
        solve([1.,0.],[length,0.],[.5,.001],2/3)
