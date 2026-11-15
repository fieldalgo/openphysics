# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent stored log-distance integrals and geometric invariants."""
import json
from pathlib import Path
import numpy as np
import pytest
from galerkin._laplace_panels import exact_double_log
import galerkin._laplace_panels as kernel

DATA = json.loads((Path(__file__).parent / 'two_ground/evidence/short-panel-integrals.json').read_text())


@pytest.mark.parametrize('row', DATA['cases'], ids=lambda row: row['case'])
@pytest.mark.parametrize('operation', ['identity', 'swap', 'reverse-first',
    'reverse-second', 'origin', 'scale-two', 'reflect'])
def test_independent_short_panel_integrals(row, operation, record_property):
    points = [np.array(row['endpoints'][key])[None] for key in ('a', 'b', 'c', 'd')]
    expected = float(row['mean_log_distance'])
    if operation == 'swap':
        points = points[2:] + points[:2]
    elif operation == 'reverse-first':
        points[0], points[1] = points[1], points[0]
    elif operation == 'reverse-second':
        points[2], points[3] = points[3], points[2]
    elif operation == 'origin':
        origin = points[0].copy()
        points = [p-origin for p in points]
    elif operation == 'scale-two':
        points = [2*p for p in points]
        expected += np.log(2.)
    elif operation == 'reflect':
        points = [p*np.array([1., -1.]) for p in points]
    observed = float(exact_double_log(*points)[0])
    record_property('short_panel_reference', json.dumps(dict(case=row['case'],
        operation=operation, observed=observed, expected=expected), sort_keys=True))
    # Original unequal-panel quadrature criterion, including its log scale.
    assert abs(observed-expected) <= 1e-12*max(1., abs(expected))


def test_failed_pair_does_not_change_a_previously_accepted_entry():
    points = [np.array(DATA['cases'][0]['endpoints'][key])[None]
              for key in ('a', 'b', 'c', 'd')]
    origin = points[0].copy()
    shifted = [p-origin for p in points]
    accepted = exact_double_log(*shifted)
    mixed = [np.concatenate((p, s)) for p, s in zip(points, shifted)]
    result = exact_double_log(*mixed)
    np.testing.assert_array_equal(result[1:], accepted)


def test_local_retry_still_refuses_unresolved_quadrature(monkeypatch):
    original = kernel.leggauss
    def inconsistent(order):
        nodes, weights = original(order)
        return nodes, weights*(1.001 if order == 32 else 1.)
    monkeypatch.setattr(kernel, 'leggauss', inconsistent)
    points = [np.array(DATA['cases'][0]['endpoints'][key])[None]
              for key in ('a', 'b', 'c', 'd')]
    with pytest.raises(ValueError, match='unequal-panel quadrature did not converge'):
        exact_double_log(*points)
