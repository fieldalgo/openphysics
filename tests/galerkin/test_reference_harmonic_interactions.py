# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Stored structure comparisons with explicit mathematical overlap."""
from pathlib import Path
import json
import numpy as np
import pytest
import crosscheck
from reference_loader import load_reference
from galerkin import laplace_corner_harmonic_interactions as module

STORED=Path(__file__).parent/'reference_values/mpmath'


def check(ref,index,kind,record_property):
    row=ref.inputs['cases'][index]
    if kind=='far':function=module.power_panel_harmonic_far_log;args=[row[k] for k in ('first','second','offset','first_exponent','second_exponent')]
    elif kind=='vertex':function=module.power_panel_harmonic_shared_vertex_log;args=[row[k] for k in ('first','second','first_exponent','second_exponent')]
    elif kind=='separated':function=module.power_panel_harmonic_separated_log;args=[row[k] for k in ('first','second','offset','p','q')]
    else:function=module.power_panel_harmonic_constant_log_partitioned;args=[row[k] for k in ('a','b','offset','p')]
    expected=ref.arrays[f'block_{index:02d}'];assert np.all(expected!=0)
    stopwatch=crosscheck.Stopwatch()
    with stopwatch('openphysics'):
        result=function(*args) if kind=='mixed' else function(*args,quadrature_order=ref.inputs['quadrature_order'])
    error=float(np.max(abs(result.mean_log_distance-expected)/abs(expected)))
    assert error<=1e-12
    assert np.all(abs(result.mean_log_distance-result.coarse_mean_log_distance)<=1e-12*np.maximum(1,abs(result.mean_log_distance)))
    assert result.mass_error<=1e-12
    record=crosscheck.make_record(case=ref.record['case'],physics=ref.record['physics'],
        api='galerkin.laplace_corner_harmonic_interactions.'+function.__name__,
        discretization=dict(kind='physical partitioned cubic measures' if kind=='mixed' else 'physical normalized Jacobi measures',case_index=index,order=result.quadrature_order,comparison_order=2*result.quadrature_order,subintervals=result.subintervals),
        tool='mpmath',tool_discretization=ref.record['references'][0]['discretization'],
        matched=ref.record['matched'],not_matched=ref.record['not_matched'],
        observables=[crosscheck.observable('harmonic log block','1','maximum strict nonzero-entry relative difference',error,gate=1e-12)],
        analytical_acceptance='tests/galerkin/test_laplace_corner_harmonic_interactions.py; closed uniform ray integral, coordinate symmetries, physical mass and explicit refusals',stopwatch=stopwatch,stored=ref)
    assert record['wall_time_s']['reference'] is None
    crosscheck.emit(record)
    record_property('stored_harmonic_interaction',json.dumps(dict(kind=kind,index=index,content_sha256=ref.record['content_sha256'],fine=result.mean_log_distance.tolist(),coarse=result.coarse_mean_log_distance.tolist(),mass_error=result.mass_error,subintervals=result.subintervals),sort_keys=True))


@pytest.mark.parametrize('index',range(18))
def test_far_reference(index,record_property):
    check(load_reference(STORED/'harmonic_far_log.json'),index,'far',record_property)


@pytest.mark.parametrize('index',range(30))
def test_vertex_reference(index,record_property):
    check(load_reference(STORED/'harmonic_vertex_log.json'),index,'vertex',record_property)


@pytest.mark.parametrize('index',range(5))
def test_separated_reference(index,record_property):
    check(load_reference(STORED/'harmonic_separated_log.json'),index,'separated',record_property)


@pytest.mark.parametrize('index',range(18))
def test_mixed_reference(index,record_property):
    check(load_reference(STORED/'harmonic_mixed_log.json'),index,'mixed',record_property)
