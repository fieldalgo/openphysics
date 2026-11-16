# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Stored direct integrals for static wedge branches; partial shared mathematics."""
import json
from pathlib import Path
import numpy as np
import pytest
import crosscheck
from reference_loader import load_reference
from galerkin.laplace_corner_harmonic import power_panel_harmonic_self_log


@pytest.mark.parametrize('index',range(12))
def test_direct_duffy_self_integral(index,record_property):
    ref=load_reference(Path(__file__).parent/'reference_values/mpmath/harmonic_self_log.json')
    inputs=ref.inputs['cases'][index]
    p,h=inputs['exponent'],inputs['length']
    expected=ref.arrays[f'self_log_{index:02d}']
    stopwatch=crosscheck.Stopwatch()
    with stopwatch('openphysics'):
        matrix=power_panel_harmonic_self_log(h,p)
    actual=matrix.ravel()[[0,1,3]];mask=np.ones(3,dtype=bool);observables=[]
    if p==1:
        assert actual[1]==0
        assert abs(expected[1])<1e-30
        mask[1]=False
        observables.append(crosscheck.observable('uniform analytic cross moment','1','absolute reference cross moment',abs(expected[1]),gate=1e-30))
    error=float(np.max(abs(actual[mask]-expected[mask])/abs(expected[mask])))
    assert error<=1e-12
    observables.append(crosscheck.observable('harmonic self log block','1','maximum nonzero-entry relative difference',error,gate=1e-12))
    record=crosscheck.make_record(case=ref.record['case'],physics=ref.record['physics'],
        api='galerkin.laplace_corner_harmonic.power_panel_harmonic_self_log',
        discretization=dict(kind='positive analytic series with unchanged scalar self moment',case_index=index),
        tool='mpmath',tool_discretization=ref.record['references'][0]['discretization'],
        matched=ref.record['matched'],not_matched=ref.record['not_matched'],observables=observables,
        analytical_acceptance='tests/galerkin/test_laplace_corner_harmonic.py; exact density-product Gram, scaling, uniform-mode and representability checks',stopwatch=stopwatch,stored=ref)
    crosscheck.emit(record)
    record_property('stored_harmonic_self_log',json.dumps(dict(input=inputs,content_sha256=ref.record['content_sha256'],value=matrix.tolist()),sort_keys=True))
