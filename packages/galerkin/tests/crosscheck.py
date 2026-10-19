# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Comparison records for solving the same problem with galerkin and a reference tool.

A record states which tool and exact version was used, its license, which
discretization choices were matched and which were not, and the difference of
each observable. Records are code-to-code evidence only: agreement between two
tools is never used as convergence evidence, and the analytical acceptance
references of each feature are unchanged. See docs/reference-comparisons.md.

Set OPENPHYSICS_CROSSCHECK_DIR to also write each record as JSON. Set
OPENPHYSICS_REQUIRE_CROSSCHECK=1 (as CI does) to fail instead of skipping when a
reference tool is not installed.
"""

from contextlib import contextmanager
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import sys
import time

import numpy as np
import pytest

SCHEMA = "openphysics.crosscheck/1"
TOOLS = {
    # Exact versions come from the installed metadata at run time.
    "scikit-fem": {"module": "skfem", "license": "BSD-3-Clause",
                   "source": "https://github.com/kinnala/scikit-fem",
                   "use": "imported in-process from the galerkin[crosscheck] test extra"},
}
REQUIRED = ("schema", "case", "physics", "openphysics", "reference", "matched", "not_matched",
            "observables", "analytical_acceptance", "wall_time_s", "not_measured", "environment", "role")


class Stopwatch:
    """Wall time of each tool's solve, in seconds (assembly and solve, not imports)."""

    def __init__(self):
        self.seconds = {}

    @contextmanager
    def __call__(self, label):
        start = time.perf_counter()
        yield
        self.seconds[label] = self.seconds.get(label, 0.0) + time.perf_counter() - start


def require_tool(name):
    """Import a reference tool; skip locally, fail in CI, when it is missing."""
    module = TOOLS[name]["module"]
    if os.environ.get("OPENPHYSICS_REQUIRE_CROSSCHECK") == "1":
        return __import__(module)
    return pytest.importorskip(module, reason=f"install the crosscheck extra for {name}")


def relative_difference(value, reference):
    """max |value - reference| / max |reference| over all entries."""
    value, reference = np.asarray(value), np.asarray(reference)
    if value.shape != reference.shape:
        raise ValueError(f"shapes differ: {value.shape} and {reference.shape}")
    return float(np.max(np.abs(value - reference)) / np.max(np.abs(reference)))


def observable(name, unit, metric, value, gate=None):
    """One compared quantity. gate=None means reported only, not asserted."""
    return {"name": name, "unit": unit, "metric": metric, "value": float(value),
            "gate": None if gate is None else float(gate),
            "passed": None if gate is None else bool(value <= gate)}


def make_record(*, case, physics, api, discretization, tool, tool_discretization,
                matched, not_matched, observables, analytical_acceptance, stopwatch):
    info = TOOLS[tool]
    record = {
        "schema": SCHEMA,
        "case": case,
        "physics": physics,
        "openphysics": {"distribution": "galerkin", "version": metadata.version("galerkin"),
                        "api": api, "discretization": discretization},
        "reference": {"tool": tool, "version": metadata.version(tool), "license": info["license"],
                      "source": info["source"], "use": info["use"],
                      "discretization": tool_discretization},
        "matched": list(matched),
        "not_matched": list(not_matched),
        "observables": list(observables),
        # Analytical pass/fail stays in the feature's own acceptance tests.
        "analytical_acceptance": analytical_acceptance,
        "wall_time_s": {k: round(v, 4) for k, v in stopwatch.seconds.items()},
        "not_measured": ["peak memory (one shared process; not separable per tool)"],
        "environment": {"python": platform.python_version(), "platform": sys.platform,
                        "numpy": np.__version__, "scipy": metadata.version("scipy")},
        "role": "code-to-code comparison; not convergence evidence",
    }
    validate_record(record)
    return record


def validate_record(record):
    if missing := [key for key in REQUIRED if key not in record]:
        raise ValueError(f"comparison record misses {missing}")
    if record["schema"] != SCHEMA:
        raise ValueError(f"unknown schema {record['schema']!r}")
    for key in ("tool", "version", "license", "source", "discretization"):
        if not record["reference"].get(key):
            raise ValueError(f"reference.{key} is required")
    if set(record["wall_time_s"]) != {"openphysics", "reference"}:
        raise ValueError("wall_time_s needs 'openphysics' and 'reference' entries")
    if not record["observables"]:
        raise ValueError("a comparison needs at least one observable")
    for item in record["observables"]:
        if not np.isfinite(item["value"]):
            raise ValueError(f"{item['name']}: non-finite difference")


def emit(record):
    """Print the record (kept in JUnit output) and optionally write it as JSON."""
    text = json.dumps(record, indent=2, sort_keys=True)
    print(text)
    directory = os.environ.get("OPENPHYSICS_CROSSCHECK_DIR")
    if directory:
        path = Path(directory) / f"{record['case']}--{record['reference']['tool']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    failed = [o for o in record["observables"] if o["passed"] is False]
    assert not failed, f"{record['case']}: differences above their gates: {failed}"
    return record
