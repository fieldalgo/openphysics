# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Opt-in gate and stored record of the corner-field panel convergence studies.

The harmonic-corner and linear-corner field test modules each have one convergence study:
panels 32 -> 48 (harmonic) or 32 -> 64 (linear) and outer widths 8 -> 16 -> 32 mm, five or
more dense solves per case. One study takes from tens of minutes to hours on one CPU,
longer than a 45-minute test partition of validate.yml. The studies therefore run only
with ``OPENPHYSICS_PANEL_STUDIES=1``, as the dispatch-only job ``panel-studies`` of
validate.yml (input ``panel_studies=true``) does, and are marked ``slow``;
otherwise they are not defined. The regular
suite instead checks that the resolution the module's other tests already solve (its
``calculated`` default: 32 or 64 panels per edge, 8 mm width) reproduces the values
recorded with the study in ``tests/galerkin/two_ground/evidence/corner-field-studies.json``.
The study criteria themselves (panel and outer changes at most 1%) are unchanged and are
re-checked whenever that job runs.
"""
import json
import os
from pathlib import Path

import numpy as np
import pytest

ENVIRONMENT = "OPENPHYSICS_PANEL_STUDIES"
RECORD = Path(__file__).resolve().parents[1] / "galerkin" / "two_ground" / "evidence" / "corner-field-studies.json"

# Without the variable the study tests are not defined at all, so they are neither collected
# nor skipped: the installed-wheel run treats any skip as a failure and deselects nothing.
ENABLED = os.environ.get(ENVIRONMENT) == "1"


def recorded(module, index):
    """The recorded quantities of one study case, as float arrays."""
    data = json.loads(RECORD.read_text(encoding="utf-8"))
    case = data["modules"][module]["cases"][index]
    return tuple(np.asarray(case[name], dtype=float) for name in data["quantities"])


def matrix_relative(value, reference):
    """Largest entry difference relative to the largest reference entry."""
    value, reference = np.asarray(value, dtype=float), np.asarray(reference, dtype=float)
    assert value.shape == reference.shape and np.isfinite(value).all()
    scale = float(np.max(abs(reference)))
    assert scale > 0
    return float(np.max(abs(value - reference))) / scale
