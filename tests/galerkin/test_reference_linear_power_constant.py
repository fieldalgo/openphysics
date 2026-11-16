# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Adaptive source identity and block records; no reference tool runs in tests."""
import json
from pathlib import Path

import numpy as np
import pytest

import crosscheck
from reference_loader import load_reference
from galerkin.laplace_corner import power_panel_linear_constant_log, _constant_linear_segment_log


def compare(ref, index, kind, record_property):
    stopwatch = crosscheck.Stopwatch()
    with stopwatch("openphysics"):
        if kind == "source":
            point = ref.inputs["source_points"][index]
            actual = np.asarray(_constant_linear_segment_log(complex(*point)))
            expected = ref.arrays["source_first_moment"][index]
            api = "galerkin.laplace_corner._constant_linear_segment_log"
        else:
            row = ref.inputs["cases"][index]
            value = power_panel_linear_constant_log(row["first"],row["second"],row["offset"],row["p"])
            actual = value.mean_log_distance
            expected = ref.arrays[f"block_{index:02d}"]
            assert value.quadrature_order == ref.inputs["quadrature_order"]
            assert np.all(abs(actual-value.coarse_mean_log_distance) <= 1e-12*np.maximum(1,abs(actual)))
            api = "galerkin.laplace_corner.power_panel_linear_constant_log"
    error = np.max(abs(actual-expected)/np.maximum(1,abs(expected)))
    assert error <= 1e-12
    record = crosscheck.make_record(
        case=ref.record["case"],physics=ref.record["physics"],api=api,
        discretization={"kind":"exact source moments and fixed cubic-coordinate64/128 target rule",
                        "comparison":kind,"case_index":index},
        tool="mpmath",tool_discretization=ref.record["references"][0]["discretization"],
        matched=ref.record["matched"],not_matched=ref.record["not_matched"],
        observables=[crosscheck.observable(f"{kind}_{index:02d}","1",
                    "maximum entrywise |difference|/max(1,|reference|)",error,gate=1e-12)],
        analytical_acceptance="tests/galerkin/test_laplace_corner_linear_constant.py: source endpoint limits and mode transformations",
        stopwatch=stopwatch,stored=ref)
    crosscheck.emit(record)
    record_property("linear_power_constant_log",json.dumps(dict(kind=kind,index=index,
        content_sha256=ref.record["content_sha256"],actual=actual.tolist()),sort_keys=True))


@pytest.mark.parametrize("index", range(11))
def test_source_first_moment_against_direct_adaptive_integral(index, record_property):
    ref = load_reference(Path(__file__).parent / "reference_values/mpmath/linear_power_constant_log.json")
    compare(ref,index,"source",record_property)


@pytest.mark.parametrize("index", range(7))
def test_full_block_against_adaptive_target_integral(index, record_property):
    ref = load_reference(Path(__file__).parent / "reference_values/mpmath/linear_power_constant_log.json")
    compare(ref,index,"block",record_property)
