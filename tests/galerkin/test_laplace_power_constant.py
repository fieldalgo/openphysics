# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent endpoint-contact integrals and fixed high-order target rules."""
import json
import math
from pathlib import Path
import numpy as np
import pytest
from galerkin.laplace_corner import (power_panel_constant_log,
    power_panel_shared_vertex_log, _graded_power_rule, _constant_segment_log)

EVIDENCE = Path(__file__).parent/'two_ground/evidence'
DATA = json.loads((EVIDENCE/'power-constant-integrals.json').read_text())
SOURCES = json.loads((EVIDENCE/'constant-segment-log.json').read_text())


@pytest.mark.parametrize('power', [.5001, .625, 2/3, .875, 1.])
@pytest.mark.parametrize('order', [64, 128])
def test_fixed_graded_rule_moments(power, order):
    x, w = _graded_power_rule(power, order)
    assert np.all(w > 0) and np.all((x > 0) & (x < 1))
    for k in range(9):
        assert abs(w@x**k-power/(power+k)) <= 1e-12*power/(power+k)


@pytest.mark.parametrize('row', SOURCES['cases'])
def test_independent_complex_constant_source(row):
    z = complex(*row['z']); expected = float(row['mean_log_distance'])
    for point in (z, z.conjugate(), -1-z):
        value = float(_constant_segment_log(np.array([point]))[0])
        assert abs(value-expected) <= 1e-12*max(1., abs(expected))


def test_exact_constant_source_endpoint_and_midpoint():
    assert np.max(abs(_constant_segment_log(np.array([0., -1., -.5]))-
        np.array([-1., -1., -1-math.log(2.)]))) <= 1e-12


@pytest.mark.parametrize('row', DATA['cases'], ids=lambda row: row['case'])
@pytest.mark.parametrize('operation', ['identity', 'rotate', 'reflect', 'scale', 'reverse-source'])
def test_independent_contact_and_near_integrals(row, operation, record_property):
    a, b, offset = [np.array(row[k]) for k in ('a', 'b', 'offset')]
    exponent = row['exponents'][0]; expected = float(row['mean_log_distance'])
    if operation == 'rotate': a, b, offset = [v[::-1]*[-1.,1.] for v in (a,b,offset)]
    if operation == 'reflect': a, b, offset = [v*[1.,-1.] for v in (a,b,offset)]
    if operation == 'scale':
        a, b, offset = [2*v for v in (a,b,offset)]; expected += math.log(2.)
    if operation == 'reverse-source': offset, b = offset+b, -b
    before = [v.copy() for v in (a,b,offset)]
    result = power_panel_constant_log(a,b,offset,exponent)
    assert all(np.array_equal(x,y) for x,y in zip(before,(a,b,offset)))
    assert result.quadrature_order == 64 and result.refinement_error <= 1e-12
    assert abs(result.mean_log_distance-expected) <= 1e-12*max(1.,abs(expected))
    record_property('power_constant_reference', json.dumps(dict(case=row['case'],
        operation=operation, expected=expected, mean=result.mean_log_distance,
        coarse=result.coarse_mean_log_distance, error=result.refinement_error), sort_keys=True))


@pytest.mark.parametrize('power', [.5001, .625, 2/3, 1.])
def test_shared_singular_vertex_agrees_with_duffy_formula(power):
    a, b = [1e-3, 0.], [0., 1e-3]
    direct = power_panel_constant_log(a,b,[0.,0.],power)
    duffy = power_panel_shared_vertex_log(a,b,power,1.)
    assert abs(direct.mean_log_distance-duffy.mean_log_distance) <= 1e-12*max(1.,abs(duffy.mean_log_distance))


@pytest.mark.parametrize('scale', [1e-100, 1e100])
def test_physical_length_scale(scale):
    a,b,o = np.array([1.,0.]),np.array([1.,0.]),np.array([1.,0.])
    base = power_panel_constant_log(a,b,o,.75)
    scaled = power_panel_constant_log(scale*a,scale*b,scale*o,.75)
    assert abs(scaled.mean_log_distance-base.mean_log_distance-math.log(scale)) <= 1e-12


@pytest.mark.parametrize('a,b,o', [([1.,0.],[0.,1.],[.5,-.5]),
    ([1.,0.],[1.,0.],[0.,0.]), ([1.,0.],[1.,0.],[.5,0.]),
    ([1.,0.],[-1.,0.],[.5,0.]), ([1.,0.],[-1.,0.],[1.,0.])])
def test_overlap_and_crossing_refused(a,b,o):
    with pytest.raises(ValueError): power_panel_constant_log(a,b,o,.75)


@pytest.mark.parametrize('bad', [[np.nan,0.], [np.inf,0.], [1.], [1.,2.,3.],
                               [True,False], ['1','0'], [1.+0j,0.]])
def test_invalid_vectors(bad):
    with pytest.raises(ValueError): power_panel_constant_log([1.,0.],bad,[2.,2.],.75)


def test_fixed_order_and_declared_length_budget():
    with pytest.raises(TypeError):
        power_panel_constant_log([1.,0.],[1.,0.],[1.,0.],.75,quadrature_order=32)
    with pytest.raises(ValueError,match='length ratio'):
        power_panel_constant_log([1.,0.],[0.,1/1000001],[2.,2.],.75)
    with pytest.raises(ValueError):
        power_panel_constant_log([0.,0.],[1.,0.],[2.,2.],.75)


@pytest.mark.parametrize('scale', [1e-100, 1., 1e100])
@pytest.mark.parametrize('relation', ['gap', 'contact', 'overlap'])
def test_one_ulp_gap_is_distinct_from_overlap(scale, relation):
    endpoint = scale if relation == 'contact' else np.nextafter(
        scale, math.inf if relation == 'gap' else 0.)
    if relation == 'overlap':
        with pytest.raises(ValueError, match='overlapping'):
            power_panel_constant_log([scale,0.],[scale,0.],[endpoint,0.],.75)
    else:
        result = power_panel_constant_log([scale,0.],[scale,0.],[endpoint,0.],.75)
        assert result.refinement_error <= 1e-12


def test_unresolved_near_interior_pair_is_refused():
    with pytest.raises(ValueError, match='did not converge'):
        power_panel_constant_log([1.,0.],[1.,0.],[.5,1e-6],.75)


def test_constant_source_far_branch_matches_closed_form_at_boundary():
    expected = 3*math.log(3.)-2*math.log(2.)-1.
    for z in (2., np.nextafter(2., math.inf), -3., np.nextafter(-3., -math.inf)):
        assert abs(float(_constant_segment_log(np.array([z]))[0])-expected) <= 1e-12
