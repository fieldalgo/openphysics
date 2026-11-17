# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Stored independent complex series for three-mode far interactions."""
import json
from pathlib import Path
import numpy as np
import pytest
import crosscheck
from reference_loader import load_reference
from galerkin.laplace_corner_quadratic_far import power_panel_quadratic_far_log


@pytest.mark.parametrize('index',range(8))
def test_independent_complex_series(index,record_property):
    ref=load_reference(Path(__file__).parent/'reference_values/mpmath/quadratic_far.json')
    case=ref.inputs['cases'][index];expected=ref.arrays[f'far_{index:02d}'].reshape(3,3)
    stopwatch=crosscheck.Stopwatch()
    with stopwatch('openphysics'):
        result=power_panel_quadratic_far_log(*[case[k] for k in ['first','second','offset','p','q']])
    error=float(np.max(abs(result.mean_log_distance-expected)/np.maximum(1,abs(expected))))
    assert error<=1e-12
    record=crosscheck.make_record(case=ref.record['case'],physics=ref.record['physics'],api='galerkin.laplace_corner_quadratic_far.power_panel_quadratic_far_log',discretization=dict(kind='physical Jacobi measures and zero-mass centered far block',quadrature_orders=[32,64],case_index=index),tool='mpmath',tool_discretization=ref.record['references'][0]['discretization'],matched=ref.record['matched'],not_matched=ref.record['not_matched'],observables=[crosscheck.observable('three-mode far logarithmic block','1','maximum scaled entry difference using max(1,abs(reference))',error,gate=1e-12)],analytical_acceptance='tests/galerkin/test_laplace_corner_quadratic_far.py; exact old subspace, reciprocity, rigid transforms and physical logscale',stopwatch=stopwatch,stored=ref)
    crosscheck.emit(record)
    record_property('stored_quadratic_far',json.dumps(dict(input=case,content_sha256=ref.record['content_sha256'],value=result.mean_log_distance.tolist()),sort_keys=True))
