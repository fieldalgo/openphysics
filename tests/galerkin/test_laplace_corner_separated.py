# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent separated power-panel integrals and geometric admission."""
import json
import math
from pathlib import Path
import numpy as np
import pytest
from galerkin.laplace_corner import power_panel_separated_log

DATA = json.loads((Path(__file__).parent/
    'two_ground/evidence/corner-separated-integrals.json').read_text())


@pytest.mark.parametrize('row', DATA['cases'], ids=lambda row: row['case'])
@pytest.mark.parametrize('operation', ['identity', 'swap', 'rotate', 'reflect', 'scale'])
def test_independent_direct_integral(row, operation, record_property):
    a, b, offset = [np.array(row[k]) for k in ('a', 'b', 'offset')]
    p, q = row['exponents']; expected = float(row['mean_log_distance'])
    if operation == 'swap': a, b, offset, p, q = b, a, -offset, q, p
    if operation == 'rotate': a, b, offset = [v[::-1]*[-1., 1.] for v in (a, b, offset)]
    if operation == 'reflect': a, b, offset = [v*[1., -1.] for v in (a, b, offset)]
    if operation == 'scale':
        a, b, offset = [2*v for v in (a, b, offset)]; expected += math.log(2.)
    saved = [v.copy() for v in (a, b, offset)]
    result = power_panel_separated_log(a, b, offset, p, q)
    assert all(np.array_equal(x, y) for x, y in zip(saved, (a, b, offset)))
    assert abs(result.mean_log_distance-expected) <= 1e-12*max(1., abs(expected))
    assert result.refinement_error <= 1e-12
    record_property('separated_power_reference', json.dumps(dict(case=row['case'],
        operation=operation, mean=result.mean_log_distance, expected=expected,
        coarse=result.coarse_mean_log_distance, error=result.refinement_error), sort_keys=True))


@pytest.mark.parametrize('p,q', [(1., 1.), (.5001, .875), (2/3, .75)])
def test_positive_weight_log_distance_bounds_and_exact_admission_boundary(p, q):
    # Parallel unit segments separated by 1/2 have distances in [1/2,sqrt(5/4)].
    value = power_panel_separated_log([1.,0.], [1.,0.], [0.,.5], p, q)
    assert math.log(.5) <= value.mean_log_distance <= math.log(math.sqrt(1.25))
    with pytest.raises(ValueError, match='separation'):
        power_panel_separated_log([1.,0.], [1.,0.], [0.,np.nextafter(.5,0.)], p, q)


@pytest.mark.parametrize('a,b,offset', [
    ([1.,0.],[0.,1.],[.5,-.5]),  # Interior intersection.
    ([1.,0.],[1.,0.],[.5,0.]),   # Collinear overlap.
    ([1.,0.],[1.,0.],[1.,0.]),   # Endpoint contact.
    ([1.,0.],[-1.,0.],[1.25,0.]),
    ([1.,0.],[0.,1.],[1.25,0.]),
    ([1.,0.],[1.,0.],[0.,0.]),
])
def test_nonseparated_pairs_refused(a, b, offset):
    with pytest.raises(ValueError, match='separation'):
        power_panel_separated_log(a,b,offset,.75,.625)


def test_endpoint_density_orientation_is_explicit():
    # Reversing a nonconstant power panel moves its singularity: not an invariant.
    forward = power_panel_separated_log([1.,0.],[1.,0.],[2.,.5],.625,1.)
    reversed_first = power_panel_separated_log([-1.,0.],[1.,0.],[1.,.5],.625,1.)
    assert abs(forward.mean_log_distance-reversed_first.mean_log_distance) > .01
    # The constant density is invariant under this reversal and origin shift.
    forward = power_panel_separated_log([1.,0.],[1.,0.],[2.,.5],1.,1.)
    reversed_first = power_panel_separated_log([-1.,0.],[1.,0.],[1.,.5],1.,1.)
    assert abs(forward.mean_log_distance-reversed_first.mean_log_distance) <= 1e-12


@pytest.mark.parametrize('size', [1e-250, 1e250])
def test_representable_scale_extremes(size):
    before = power_panel_separated_log([1.,0.],[0.,1.],[2.,2.],.75,1.)
    after = power_panel_separated_log([size,0.],[0.,size],[2*size,2*size],.75,1.)
    assert abs(after.mean_log_distance-before.mean_log_distance-math.log(size)) <= 1e-12


def test_distant_small_panels_have_checked_log_bounds():
    result = power_panel_separated_log([1e-100,0.],[0.,1e-100],[1e100,0.],.75,.625)
    assert abs(result.mean_log_distance-math.log(1e100)) <= 1e-12


@pytest.mark.parametrize('bad', [[0.], [1.,2.,3.], [np.nan,0.], [np.inf,0.],
                               [True,False], [1.+0j,0.], ['1','0']])
def test_invalid_offset(bad):
    with pytest.raises(ValueError):
        power_panel_separated_log([1.,0.],[0.,1.],bad,.75,.75)


def test_invalid_length_ratio_norm_and_unresolved_rule():
    with pytest.raises(ValueError, match='length ratio'):
        power_panel_separated_log([1.,0.],[0.,1/65],[2.,2.],.75,.75)
    with pytest.raises(ValueError, match='representable'):
        power_panel_separated_log([1.,0.],[0.,1.],[1.7e308,1.7e308],.75,.75)
    with pytest.raises(ValueError, match='quadrature'):
        power_panel_separated_log([1.,0.],[1.,0.],[0.,.5],.75,.625,quadrature_order=4)
