# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit provenance consumers; original primitive gates and fixtures are kept."""

import json
from pathlib import Path

import numpy as np
import pytest

import crosscheck
from reference_loader import load_reference
from galerkin.laplace_corner import (
    power_panel_linear_far_log,
    power_panel_linear_shared_vertex_log,
)

HERE = Path(__file__).resolve().parent
STORED = HERE / "reference_values" / "mpmath"


def check(ref, index, kind, record_property):
    row = ref.inputs["cases"][index]
    old = json.loads((HERE / "two_ground" / "evidence" /
                      f"linear-{kind}-log-integrals.json").read_text())
    original = old["rows" if kind == "far" else "cases"][index]
    assert row == {key: original[key] for key in row}
    expected = ref.arrays[f"case_{index:02d}"]
    # Provenance cannot silently replace any original numeric reference.
    np.testing.assert_array_equal(expected, np.asarray(original["reference"], dtype="<f8"))
    assert not expected.flags.writeable
    stopwatch = crosscheck.Stopwatch()
    with stopwatch("openphysics"):
        if kind == "far":
            result = power_panel_linear_far_log(
                row["first"], row["second"], row["offset"], row["p"], row["q"],
                quadrature_order=ref.inputs["quadrature_order"])
        else:
            result = power_panel_linear_shared_vertex_log(
                row["first"], row["second"], row["p"], row["q"],
                quadrature_order=ref.inputs["quadrature_order"])
    difference = np.max(abs(result.mean_log_distance-expected) / np.maximum(1, abs(expected)))
    assert difference <= 1e-12  # Original dimensionless primitive criterion.
    assert np.all(abs(result.mean_log_distance-result.coarse_mean_log_distance)
                  <= 1e-12*np.maximum(1, abs(result.mean_log_distance)))
    record = crosscheck.make_record(
        case=ref.record["case"], physics=ref.record["physics"],
        api=f"galerkin.laplace_corner.power_panel_linear_{'far' if kind == 'far' else 'shared_vertex'}_log",
        discretization={"kind": "normalized Gauss-Jacobi", "case_index": index,
                        "order": ref.inputs["quadrature_order"], "comparison_order": 2*ref.inputs["quadrature_order"]},
        tool="mpmath", tool_discretization=ref.record["references"][0]["discretization"],
        matched=ref.record["matched"], not_matched=ref.record["not_matched"],
        observables=[crosscheck.observable(f"case_{index:02d} log block", "1",
                     "maximum entrywise |difference|/max(1,|reference|)", difference, gate=1e-12)],
        analytical_acceptance=f"tests/galerkin/test_laplace_corner_linear_{kind}.py; unchanged",
        stopwatch=stopwatch, stored=ref)
    assert record["wall_time_s"]["reference"] is None
    crosscheck.emit(record)
    record_property("stored_linear_log", json.dumps({"case": index, "kind": kind,
        "content_sha256": ref.record["content_sha256"],
        "fine": result.mean_log_distance.tolist(),
        "coarse": result.coarse_mean_log_distance.tolist()}, sort_keys=True))


@pytest.mark.parametrize("index", range(8))
def test_stored_far_structure_reference(index, record_property):
    ref = load_reference(STORED / "linear_far_log.json")
    check(ref, index, "far", record_property)


@pytest.mark.parametrize("index", range(6))
def test_stored_vertex_structure_reference(index, record_property):
    ref = load_reference(STORED / "linear_vertex_log.json")
    check(ref, index, "vertex", record_property)
