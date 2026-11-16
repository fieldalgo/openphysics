# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Analytical moments, independent integrals and power-panel invariants."""
import json
import math
from pathlib import Path
import numpy as np
import pytest
from galerkin.laplace_corner import (power_panel_quadrature, power_panel_gram,
    power_panel_self_log, power_panel_shared_vertex_log)


@pytest.mark.parametrize('power', [.5001, .6, 2/3, .875, 1.])
@pytest.mark.parametrize('order', [4, 8, 32, 64, 128])
def test_exact_weighted_polynomial_moments(power, order):
    x, w = power_panel_quadrature(power, order)
    assert np.all((x > 0) & (x < 1)) and np.all(w > 0)
    for degree in range(2*order):
        assert abs(w@x**degree-power/(power+degree)) <= 1e-12*power/(power+degree)
    for array in (x, w):
        with pytest.raises(ValueError): array.setflags(write=True)


@pytest.mark.parametrize('length', [1e-9, .001, 1., 1e6])
def test_constant_panel_analytic_reduction(length):
    assert power_panel_gram(length, 1.) == 1./length
    assert abs(power_panel_self_log(length, 1.)-(math.log(length)-1.5)) <= 1e-14*max(1., abs(math.log(length)))
    # Adjacent collinear constant unit panels: double mean log(u+v).
    result = power_panel_shared_vertex_log([length, 0.], [-length, 0.], 1., 1.)
    exact = math.log(length)+2*math.log(2)-1.5
    assert abs(result.mean_log_distance-exact) <= 1e-12*max(1., abs(exact))
    assert result.refinement_error <= 1e-12


def test_convex_right_corner_squared_current():
    # Exterior wedge angle 3*pi/2 gives exponent 2/3.
    assert power_panel_gram(.002, 2/3) == pytest.approx(4/(3*.002), rel=1e-14)
    # Integrable density still has divergent squared current at exponent 1/2.
    with pytest.raises(ValueError, match='squared current'):
        power_panel_gram(.002, .5)


@pytest.mark.parametrize('power,constant', [
    (.75, 3*math.log(2)-math.pi/2-2),
    (2/3, 1.5*math.log(3)-math.pi/(2*math.sqrt(3))-2.25),
])
def test_nonconstant_self_integrals_against_elementary_closed_forms(power, constant):
    # Quarter- and third-power logarithmic moments expressed without digamma.
    for length in (1., .002):
        assert abs(power_panel_self_log(length, power)-math.log(length)-constant) <= 1e-12


@pytest.mark.parametrize('power', [.5001, .625, 2/3, 1.])
def test_self_log_scale_and_gram_units(power):
    for scale in (2., 1e-6, 1e6):
        assert abs(power_panel_self_log(.003*scale, power)-power_panel_self_log(.003, power)-math.log(scale)) <= 1e-12
        assert power_panel_gram(.003*scale, power)*scale == pytest.approx(power_panel_gram(.003, power), rel=1e-14)


@pytest.mark.parametrize('row_name', ['constant-right', 'power-right', 'power-skew', 'power-opposed'])
@pytest.mark.parametrize('operation', ['identity', 'swap', 'reflect', 'rotate', 'scale'])
def test_independent_reference(row_name, operation, record_property):
    data = json.loads((Path(__file__).parent/'two_ground/evidence/corner-panel-integrals.json').read_text())
    row = next(r for r in data['cases'] if r['case'] == row_name)
    a, b = (np.array(row[k]) for k in ('a', 'b'))
    p, q = row['exponents']; expected = float(row['mean_log_distance'])
    if operation == 'swap': a, b, p, q = b, a, q, p
    if operation == 'reflect': a, b = a*[1., -1.], b*[1., -1.]
    if operation == 'rotate': a, b = a[::-1]*[-1., 1.], b[::-1]*[-1., 1.]
    if operation == 'scale': a, b = 2*a, 2*b; expected += math.log(2.)
    before_a, before_b = a.copy(), b.copy()
    result = power_panel_shared_vertex_log(a, b, p, q)
    assert np.array_equal(a, before_a) and np.array_equal(b, before_b)
    assert abs(result.mean_log_distance-expected) <= 1e-12*max(1., abs(expected))
    record_property('power_panel_reference', json.dumps(dict(case=row_name,
        operation=operation, expected=expected, mean=result.mean_log_distance,
        coarse=result.coarse_mean_log_distance, error=result.refinement_error), sort_keys=True))


@pytest.mark.parametrize('power', [0., .5, -1., 1.01, np.nan, np.inf, True, '0.75', .75+0j, [.75]])
def test_invalid_exponent(power):
    for function, args in ((power_panel_gram, (.001, power)),
                           (power_panel_self_log, (.001, power)),
                           (power_panel_quadrature, (power,))):
        with pytest.raises(ValueError): function(*args)


@pytest.mark.parametrize('length', [0., -1., np.nan, np.inf, True, '1', [1.], 1+0j])
def test_invalid_length(length):
    for function in (power_panel_gram, power_panel_self_log):
        with pytest.raises(ValueError): function(length, .75)


@pytest.mark.parametrize('order', [0, 3, 129, 4.5, True, '32', np.inf])
def test_invalid_order(order):
    with pytest.raises(ValueError): power_panel_quadrature(.75, order)


@pytest.mark.parametrize('a,b', [([0.,0.],[1.,0.]), ([1.,0.],[1.,0.]),
    ([1.,0.],[2.,0.]), ([1.,0.],[1e-4,0.01]), ([1.,0.],[0.,1/65]),
    ([np.inf,0.],[0.,1.]), ([1.],[0.,1.]), ([1.,0.],[0.,1.,2.]),
    ([1.+0j,0.],[0.,1.]), ([True,False],[0.,1.])])
def test_invalid_geometry(a, b):
    with pytest.raises(ValueError): power_panel_shared_vertex_log(a,b,.75,.75)


def test_unrepresentable_gram_and_unresolved_quadrature_are_rejected():
    with pytest.raises(ValueError, match='representable'):
        power_panel_gram(1e-320, .5001)
    with pytest.raises(ValueError, match='quadrature'):
        power_panel_shared_vertex_log([1.,0.],[1.,.01],.75,.75,quadrature_order=4)
    with pytest.raises(ValueError, match='quadrature_order'):
        power_panel_shared_vertex_log([1.,0.],[0.,1.],.75,.75,quadrature_order=65)
