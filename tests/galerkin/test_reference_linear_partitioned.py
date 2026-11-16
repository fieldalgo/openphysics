# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Stored adaptive mixed-block comparisons, without executing a reference tool."""
import json
from pathlib import Path

import numpy as np
import pytest

import crosscheck
from reference_loader import load_reference
from galerkin.laplace_corner_partitioned import power_panel_linear_constant_log_partitioned


@pytest.mark.parametrize('index',range(11))
def test_adaptive_target_reference(index,record_property):
    ref=load_reference(Path(__file__).parent/'reference_values/mpmath/linear_partitioned_log.json')
    row=ref.inputs['cases'][index];stopwatch=crosscheck.Stopwatch()
    with stopwatch('openphysics'):
        result=power_panel_linear_constant_log_partitioned(row['a'],row['b'],row['offset'],row['p'])
    expected=ref.arrays[f'block_{index:02d}'];actual=result.mean_log_distance
    error=float(np.max(abs(actual-expected)/np.maximum(1,abs(expected))))
    assert error<=1e-12
    assert result.quadrature_order==ref.inputs['quadrature_order']
    assert result.subintervals<=ref.inputs['maximum_subintervals']
    record=crosscheck.make_record(case=ref.record['case'],physics=ref.record['physics'],
        api='galerkin.laplace_corner_partitioned.power_panel_linear_constant_log_partitioned',
        discretization=dict(kind='physical power density on graded dyadic intervals with64/128 cubic rules',
                            subintervals=result.subintervals,case_index=index),
        tool='mpmath',tool_discretization=ref.record['references'][0]['discretization'],
        matched=ref.record['matched'],not_matched=ref.record['not_matched'],
        observables=[crosscheck.observable(f'block_{index:02d}','1',
                    'maximum entrywise |difference|/max(1,|reference|)',error,gate=1e-12)],
        analytical_acceptance='tests/galerkin/test_laplace_corner_partitioned.py: physical moments, scaling, reciprocity and mode signs',
        stopwatch=stopwatch,stored=ref)
    crosscheck.emit(record)
    record_property('linear_partitioned_reference',json.dumps(dict(index=index,
        content_sha256=ref.record['content_sha256'],actual=actual.tolist(),
        subintervals=result.subintervals,mass_error=result.mass_error),sort_keys=True))
