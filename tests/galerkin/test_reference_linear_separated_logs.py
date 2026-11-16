# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Direct high-precision integral references, with explicit shared mathematics."""
import json
from pathlib import Path

import numpy as np
import pytest

import crosscheck
from reference_loader import load_reference
from galerkin.laplace_corner import power_panel_linear_separated_log


@pytest.mark.parametrize("index", range(5))
def test_separated_block_against_stored_direct_integral(index, record_property):
    ref = load_reference(Path(__file__).parent / "reference_values/mpmath/linear_separated_log.json")
    row = ref.inputs["cases"][index]
    stopwatch = crosscheck.Stopwatch()
    with stopwatch("openphysics"):
        result = power_panel_linear_separated_log(
            row["first"],row["second"],row["offset"],row["p"],row["q"],
            quadrature_order=ref.inputs["quadrature_order"])
    expected = ref.arrays[f"case_{index:02d}"]
    error = np.max(abs(result.mean_log_distance-expected)/np.maximum(1,abs(expected)))
    assert error <= 1e-12
    assert np.all(abs(result.mean_log_distance-result.coarse_mean_log_distance)
                  <= 1e-12*np.maximum(1,abs(result.mean_log_distance)))
    record = crosscheck.make_record(
        case=ref.record["case"], physics=ref.record["physics"],
        api="galerkin.laplace_corner.power_panel_linear_separated_log",
        discretization={"kind":"normalized Gauss-Jacobi with analytic zero-mass centering",
                        "order":ref.inputs["quadrature_order"],"case_index":index},
        tool="mpmath",tool_discretization=ref.record["references"][0]["discretization"],
        matched=ref.record["matched"],not_matched=ref.record["not_matched"],
        observables=[crosscheck.observable(f"case_{index:02d} log block","1",
                    "maximum entrywise |difference|/max(1,|reference|)",error,gate=1e-12)],
        analytical_acceptance="tests/galerkin/test_laplace_corner_linear_separated.py: parallel unit-power closed forms",
        stopwatch=stopwatch,stored=ref)
    crosscheck.emit(record)
    record_property("linear_separated_log",json.dumps(dict(input=row,
        content_sha256=ref.record["content_sha256"],fine=result.mean_log_distance.tolist(),
        coarse=result.coarse_mean_log_distance.tolist()),sort_keys=True))
