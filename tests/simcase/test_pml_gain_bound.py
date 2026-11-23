# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The gain bound of the open-boundary filter: a candidate is rejected as gain-like
(``negative_imaginary_index``) only when Im n_eff < -b, b = max(1e-10, K f_pml) max(1, |Re n_eff|),
K = 1e-2, f_pml its PML L2 fraction (docs/packages/simcase/pml_modes.md).

Registered before the implementation from 27 measured solves (Linux): lossless guided modes have
|Im n| / (f_pml max(1, |Re n|)) <= 2.57e-3, the gain-like candidates (PML modes of the bend)
>= 5.67e-2. Checks C1 and C2 here; C3 (every P1-P3 V-check and T1 W-check unchanged), C4 (Studio's
display) and C5 (the x 1 record bytes) are the existing suites and the commit's measurements.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from open_boundary_fixtures import ALL, build, scaled
from simcase import Document, run
from simcase.physics_pml_modes import GAIN_BOUND_FACTOR, gain_bound

ROOT = Path(__file__).resolve().parents[2]


def _block(d):
    d = copy.deepcopy(d)
    d["results"] = {"plots": False}
    r = run(Document.from_dict(d), False)
    return r.effective_index[0], r.open_boundary[0]


def _index(c):
    return complex(c["effective_index"]["re"], c["effective_index"]["im"])


def _bound(c):
    z = _index(c)
    return max(1e-10, GAIN_BOUND_FACTOR * c["pml_l2_fraction"]) * max(1., abs(z.real))


def test_the_bound():
    assert GAIN_BOUND_FACTOR == 1e-2
    assert gain_bound(2.5 + 0j, 0.) == 2.5e-10                     # the former limit, unchanged
    assert gain_bound(0.5 + 0j, 0.) == 1e-10
    assert gain_bound(1.77 + 0j, 6.4e-5) == pytest.approx(1e-2 * 6.4e-5 * 1.77, rel=1e-15)
    assert gain_bound(1.77 + 0j, float("nan")) == 1.77e-10


def _check_record(block):
    """Every candidate's reason and status follow the bound (public frame: gain is Im < 0)."""
    for c in block["candidates"]:
        z, b = _index(c), _bound(c)
        floor = 1e-10 * max(1., abs(z.real))
        assert ("negative_imaginary_index" in c["reasons"]) == (z.imag < -b), c
        expected = ("numerically_unresolved" if abs(z.imag) <= floor else
                    "negative_within_pml_bound" if -b <= z.imag < -floor else "resolved_sign")
        assert c["attenuation_status"] == expected, c


def test_c2_no_gain_like_candidate_of_the_bend_becomes_eligible():
    """The bent slab's PML modes with Im n_eff < 0 (measured: 5 of 27 candidates, |Im| 0.13..0.89,
    f_pml >= 0.99) stay rejected as gain-like, whatever the fraction filter says."""
    d = json.loads((ROOT / "examples" / "simcase" / "pml_bent_slab.json").read_text(encoding="utf-8"))
    d["physics"]["em1"]["pml"]["pml_search_mode_count"] = 64
    _, block = _block(d)
    _check_record(block)
    gain = [c for c in block["candidates"] if c["effective_index"]["im"] < 0 and c["pml_l2_fraction"] >= 0.5]
    assert len(gain) >= 5, block["candidates"]
    for c in gain:
        assert "negative_imaginary_index" in c["reasons"] and not c["selected"], c
        assert abs(c["effective_index"]["im"]) / (c["pml_l2_fraction"] * max(1, abs(c["effective_index"]["re"]))) \
            >= 5 * GAIN_BOUND_FACTOR, c


def test_the_template_bound_mode_is_returned_when_asked_for():
    """At x 1 the template's bound 1.4923 mode (Im n_eff -2.67e-7, f_pml 1.7e-2, physical fraction
    0.983) was rejected as gain-like; it is now eligible, returned with 4 modes and labelled
    negative_within_pml_bound. With 2 modes the selection is unchanged (TE-like and TM-like)."""
    text = build("template", 4, edges=ALL, single=True)
    n, block = _block(json.loads(text))
    _check_record(block)
    assert len(n) == 3, n
    low = [c for c in block["candidates"] if c["selected"] and c["effective_index"]["re"] < 1.6]
    assert len(low) == 1 and low[0]["attenuation_status"] == "negative_within_pml_bound", low
    assert abs(low[0]["effective_index"]["re"] - 1.4923) <= 5e-4 and low[0]["effective_index"]["im"] < 0
    two = json.loads(text)
    two["physics"]["em1"]["mode_count"] = 2
    n2, block2 = _block(two)
    _check_record(block2)
    assert len(n2) == 2 and abs(n2[0].real - 2.4429) <= 5e-4 and abs(n2[1].real - 1.7700) <= 5e-4, n2


@pytest.mark.slow
@pytest.mark.parametrize("factor,tm", [(0.5, 1.771181), (0.25, 1.771352)])
def test_c1_the_refined_template_returns_the_tm_like_mode(factor, tm):
    """C1 as registered: at element length x 1/2 and x 1/4 (2 modes, the default target) the run
    returns TE-like and TM-like; the TM-like Im n_eff (measured -2.43e-9, -6.17e-9) is within the
    bound and labelled negative_within_pml_bound; the 1.493 mode is outside the requested count."""
    n, block = _block(scaled(build("template", 2, edges=ALL, single=True), factor))
    _check_record(block)
    assert len(n) == 2 and abs(n[0].real - 2.446) <= 1e-3 and abs(n[1].real - tm) <= 5e-4, n
    chosen = {c["candidate"]: c for c in block["candidates"]}
    status = [chosen[i]["attenuation_status"] for i in block["selected_candidates"]]
    print(f"\nC1 x {factor}: {n}, status {status}")
    assert status[1] == "negative_within_pml_bound", status
    low = [c for c in block["candidates"] if 1.49 < c["effective_index"]["re"] < 1.50 and c["physical_l2_fraction"] >= 0.9]
    assert len(low) == 1 and low[0]["reasons"] == ["outside_requested_count"], low
