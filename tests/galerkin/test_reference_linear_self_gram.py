# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Provenance consumer retaining original relative and analytic-zero criteria."""
import json
from pathlib import Path

import numpy as np
import pytest

import crosscheck
from reference_loader import load_reference
from galerkin.laplace_corner import power_panel_linear_gram, power_panel_linear_self_log


@pytest.mark.parametrize("index", range(5))
def test_stored_direct_self_and_gram_integrals(index, record_property):
    here = Path(__file__).parent
    ref = load_reference(here / "reference_values/mpmath/linear_self_gram.json")
    inputs = ref.inputs["cases"][index]
    p,h = inputs["exponent"],inputs["length"]
    original = json.loads((here / "two_ground/evidence/linear-corner-integrals.json").read_text())["cases"][index]
    assert inputs == {key:original[key] for key in inputs}
    expected = {key:ref.arrays[f"{key}_{index:02d}"] for key in ("gram","self_log")}
    for key,value in expected.items():
        np.testing.assert_array_equal(value,np.asarray(original["reference_values"][-1][key],dtype="<f8"))
    stopwatch = crosscheck.Stopwatch()
    with stopwatch("openphysics"):
        matrices = {"gram":power_panel_linear_gram(h,p),"self_log":power_panel_linear_self_log(h,p)}
    observables = []
    for key,matrix in matrices.items():
        actual = matrix.ravel()[[0,1,3]]
        mask = np.ones(3,dtype=bool)
        if p == 1.:
            assert actual[1] == 0  # Exact orthogonality, not numeric clipping.
            zero = abs(expected[key][1])*(h if key == "gram" else 1.)
            assert zero < 1e-30
            observables.append(crosscheck.observable(key+" analytic cross moment","1",
                               "absolute normalized reference cross moment",zero,gate=1e-30))
            mask[1] = False
        # Keep the original strict relative criterion without a denominator floor.
        error = np.max(abs(actual[mask]-expected[key][mask])/abs(expected[key][mask]))
        assert error <= 1e-12
        observables.append(crosscheck.observable(key,"1","maximum nonzero-entry relative difference",error,gate=1e-12))
    record = crosscheck.make_record(
        case=ref.record["case"],physics=ref.record["physics"],
        api="galerkin.laplace_corner.power_panel_linear_gram/power_panel_linear_self_log",
        discretization={"kind":"closed expressions","case_index":index},
        tool="mpmath",tool_discretization=ref.record["references"][0]["discretization"],
        matched=ref.record["matched"],not_matched=ref.record["not_matched"],observables=observables,
        analytical_acceptance="tests/galerkin/test_laplace_corner_linear.py; original relative and analytic-zero checks unchanged",
        stopwatch=stopwatch,stored=ref)
    crosscheck.emit(record)
    record_property("stored_linear_self_gram",json.dumps(dict(input=inputs,
        content_sha256=ref.record["content_sha256"],gram=matrices["gram"].tolist(),
        self_log=matrices["self_log"].tolist()),sort_keys=True))
