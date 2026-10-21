# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Exercise stored comparisons in both source and installed-wheel suites.

Synthetic records exist only in temporary directories, never as physics oracles.
"""
import json
import numpy as np
import pytest
from reference_loader import content_digest, file_digest, load_reference, values_digest
from crosscheck import Stopwatch, emit, make_record

@pytest.fixture
def good(tmp_path):
    directory = tmp_path / "tests/galerkin/reference_values/synthetic"
    directory.mkdir(parents=True)
    path = directory / "case.json"
    generator = directory / "generate_case.py"
    generator.write_text("# synthetic generator, no solver\n")
    consumer = tmp_path / "tests/galerkin/test_reference_example.py"
    consumer.write_text('from reference_loader import load_reference\ndef test_case():\n    load_reference("case.json")\n')
    record = {
        "schema": "openphysics.reference-values/1", "case": "synthetic", "physics": "test",
        "comparison": "same-discretization", "role": "synthetic contract test; not physics evidence",
        "references": [{"tool": "synthetic", "version": "1.0", "build": "test",
            "modified": {"value": False, "description": "unmodified"}, "license": "MIT",
            "source": "https://example.org/reference", "install": {"kind": "synthetic", "command": "none", "lock": "none"},
            "settings": {}, "discretization": {"kind": "synthetic"}, "arrays": ["x"],
            "execution": "separate-process", "independence": {"product_loaded": False, "inputs_from_product": False}}],
        "generator": {"path": generator.relative_to(tmp_path).as_posix(), "sha256": file_digest(generator, text=True),
                      "command": "python generate_case.py", "product_commit": "0" * 40, "clean": True},
        "generated_utc": "2026-10-21T00:00:00Z",
        "environment": {"python": "3.12", "numpy": "2.5.3", "os": "synthetic", "cpu": "synthetic", "dtype": "float64", "backend/device": "cpu"},
        "cost": {"compile_s": 0, "compute_s": 0, "wall_time_s": 0, "peak_rss_mb": 0, "threads": 1, "not_measured": []},
        "inputs": {"x": 1}, "matched": [], "not_matched": [], "reference_self_check": [], "failed_or_discarded": [], "not_run": [],
        "values": [{"name": "x", "unit": "1", "dtype": "<f8", "shape": [1], "data": [1.0]}],
        "consumers": [consumer.relative_to(tmp_path).as_posix()], "provenance_status": "complete", "not_recorded": {}, "regeneration": [],
    }
    record["values_sha256"] = values_digest({"x": np.array([1.0], dtype="<f8")})
    record["content_sha256"] = content_digest(record["inputs"], record["values_sha256"])
    inventory = {"distributions": {"synthetic": {"spdx": "MIT"}}}
    tracked = [p.relative_to(tmp_path).as_posix() for p in (path, generator, consumer)]
    return path, record, inventory, tracked


def write_good(good):
    path, record, _, _ = good
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def test_stored_comparison_without_reference_install(good, monkeypatch):
    import crosscheck
    real_version = crosscheck.metadata.version
    def version(name):
        assert name != "synthetic", "stored reference must not query installed tool metadata"
        return real_version(name)
    monkeypatch.setattr(crosscheck.metadata, "version", version)
    ref = load_reference(write_good(good))
    stopwatch = Stopwatch()
    with stopwatch("openphysics"):
        observed = ref.inputs["x"]
    record = make_record(case="synthetic", physics="test", api="synthetic", discretization={},
        tool="synthetic", tool_discretization={"kind": "synthetic"}, matched=[], not_matched=[],
        observables=[crosscheck.observable("x", "1", "absolute", abs(observed - ref.arrays["x"][0]), 1e-9)],
        analytical_acceptance="synthetic contract check only", stopwatch=stopwatch, stored=ref)
    emit(record)
    assert record["reference"]["version"] == "1.0"
    assert record["wall_time_s"]["reference"] is None
    assert record["stored_reference"]["content_sha256"] == ref.record["content_sha256"]


def test_different_discretization_is_report_only(good):
    good[1]["comparison"] = "different-discretization"
    ref = load_reference(write_good(good))
    sw = Stopwatch(); sw.seconds["openphysics"] = 0
    with pytest.raises(ValueError, match="report-only"):
        make_record(case="synthetic", physics="test", api="test", discretization={},
            tool="synthetic", tool_discretization={"kind": "synthetic"}, matched=[], not_matched=[],
            observables=[{"gate": 1e-9}], analytical_acceptance="separate", stopwatch=sw, stored=ref)


@pytest.mark.parametrize("field", ["values_sha256", "content_sha256"])
def test_runtime_hash_validation(good, field):
    good[1][field] = "0" * 64
    with pytest.raises(ValueError, match="hash mismatch"):
        load_reference(write_good(good))
