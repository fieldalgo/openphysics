# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent stored physical self integrals for three radial modes."""
import json
from pathlib import Path
import numpy as np
import pytest
import crosscheck
from reference_loader import load_reference
from galerkin.laplace_corner_quadratic import power_panel_quadratic_gram,power_panel_quadratic_self_log


@pytest.mark.parametrize('index',range(27))
@pytest.mark.parametrize('kind',['gram','self_log'])
def test_stored_three_mode_physical_integral(index,kind,record_property):
    ref=load_reference(Path(__file__).parent/'reference_values/mpmath/quadratic_self.json')
    case=ref.inputs['cases'][index];p,h=case['exponent'],case['length']
    expected=ref.arrays[f'{kind}_{index:02d}']
    function=power_panel_quadratic_gram if kind=='gram' else power_panel_quadratic_self_log
    stopwatch=crosscheck.Stopwatch()
    with stopwatch('openphysics'):matrix=function(h,p)
    actual=matrix[np.triu_indices(3)]
    error=float(np.max(abs(actual-expected)/np.maximum(1,abs(expected))))
    assert error<=1e-12
    observables=[crosscheck.observable('three-mode physical self integral','1','maximum scaled entry difference using max(1,abs(reference))',error,gate=1e-12)]
    if p!=1:
        indices=[2,4] if kind=='gram' else [4]
        assert np.all(actual[indices]!=0) and np.all(expected[indices]!=0)
        relative=float(np.max(abs((actual[indices]-expected[indices])/expected[indices])))
        assert relative<=1e-12
        observables.append(crosscheck.observable('nonzero near-uniform cross moment','1','maximum selected nonzero-entry relative difference',relative,gate=1e-12))
    record=crosscheck.make_record(case=ref.record['case'],physics=ref.record['physics'],api='galerkin.laplace_corner_quadratic.'+function.__name__,discretization=dict(kind='analytic physical Gram and64term self-log series',case_index=index,quantity=kind),tool='mpmath',tool_discretization=ref.record['references'][0]['discretization'],matched=ref.record['matched'],not_matched=ref.record['not_matched'],observables=observables,analytical_acceptance='tests/galerkin/test_laplace_corner_quadratic.py; independent physical integrals, uniform polynomials, exact old subspace and scale',stopwatch=stopwatch,stored=ref)
    crosscheck.emit(record)
    record_property('stored_quadratic_self',json.dumps(dict(input=case,kind=kind,content_sha256=ref.record['content_sha256'],value=matrix.tolist()),sort_keys=True))
