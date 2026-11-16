# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Selected high-precision blocks; stored product-derived geometry is explicit."""
from functools import lru_cache
import json
from pathlib import Path

import numpy as np
import pytest

import crosscheck
from reference_loader import load_reference
from galerkin.laplace_corner_linear_assembly import assemble_linear_corner_half_space


@lru_cache(maxsize=1)
def calculated(serialized_inputs):
    inputs=json.loads(serialized_inputs)
    return assemble_linear_corner_half_space(inputs['polygons'],width=inputs['width'],
        height=inputs['height'],panels_per_edge=inputs['panels_per_edge'])


@pytest.mark.parametrize('index',range(7))
def test_selected_real_image_blocks(index,record_property):
    ref=load_reference(Path(__file__).parent/'reference_values/mpmath/linear_half_space.json')
    stopwatch=crosscheck.Stopwatch()
    with stopwatch('openphysics'):
        result=calculated(json.dumps(dict(ref.inputs),sort_keys=True))
        i,j=ref.inputs['entries'][index]['indices']
        actual=result.matrix[2*i:2*i+2,2*j:2*j+2]
    expected=ref.arrays[f'block_{index:02d}']
    error=float(np.max(abs(actual-expected)/np.maximum(1,abs(expected))))
    assert error<=1e-12
    record=crosscheck.make_record(case=ref.record['case'],physics=ref.record['physics'],
        api='galerkin.laplace_corner_linear_assembly.assemble_linear_corner_half_space',
        discretization=dict(kind='two interleaved physical power modes per panel',
                            physical_panels=result.geometry.panel_count,selected_indices=[i,j]),
        tool='mpmath',tool_discretization=ref.record['references'][0]['discretization'],
        matched=ref.record['matched'],not_matched=ref.record['not_matched'],
        observables=[crosscheck.observable(f'block_{index:02d}','1',
                    'maximum entrywise |difference|/max(1,|reference|)',error,gate=1e-12)],
        analytical_acceptance='tests/galerkin/test_laplace_corner_linear_assembly.py: energy, transformation and P0 subspace identities',
        stopwatch=stopwatch,stored=ref)
    crosscheck.emit(record)
    record_property('linear_half_space_reference',json.dumps(dict(index=index,
        content_sha256=ref.record['content_sha256'],actual=actual.tolist()),sort_keys=True))
