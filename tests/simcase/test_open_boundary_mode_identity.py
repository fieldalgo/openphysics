# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Slice P3: mode identity under an open boundary (PML), on the documents Studio's
optical-shapes-v9 builder writes (tests/simcase/open_boundary_fixtures.py).

The physical window of an open result is the set of triangles whose centroid lies inside its
``physical_bounds``; the TE fraction and the effective area are the closed-window formulas summed
there (simcase.mode_postprocessing), and n_g is the complex central difference of
``results.group_index`` (simcase.group_index). Registered before the results unless marked:

- V9: TE fraction on the physical window. The V1 film (220 nm Si over a 500 nm silica gap and an
  Si substrate through the bottom PML, PEC side walls, TE, target 2.85) at every element length
  x 1, 1/2, 1/4 against the exact slab limit f_TE = 1: 1 - f_TE <= 1e-3 at each level and
  strictly decreasing (x 1 measured before, 5.7e-4; the halvings blind). The template open
  against closed: |delta f_TE| <= 1e-3 for both modes (measured before, 1.7e-4).
- V10: effective area, the template open against closed: relative difference <= 1e-2 for both
  modes (measured before, 7e-4).
- V11 (n_g under the PML): tests/simcase/test_open_boundary_group_index.py.
- V12 and V13 (Studio's formulas and matching on the same samples) are added with the Studio
  change.
"""
from __future__ import annotations

import copy

import numpy as np
import pytest

from open_boundary_fixtures import ALL, CLOSED, TOP_BOTTOM, build, scaled
from simcase import Document, run


def solve(d):
    d = copy.deepcopy(d)
    d.setdefault("results", {})["plots"] = False
    return run(Document.from_dict(d), False)


def template(edges, factor=1):
    return scaled(build("template", 2, edges=edges), factor)


def te_fraction(result):
    return result.postprocessing["te_polarization_fraction"][0]


def area(result):
    return result.postprocessing["effective_area"][0]


# -- V9, V10: the template open against closed ---------------------------------------------------

@pytest.fixture(scope="module")
def template_runs():
    return solve(template(CLOSED)), solve(template(ALL))


def test_v9_v10_template_open_against_closed(template_runs):
    closed, opened = template_runs
    assert opened.open_boundary is not None and closed.open_boundary is None
    # the closed run is unchanged: the physical window of a closed run is the whole window
    assert set(closed.postprocessing) >= {"te_polarization_fraction", "effective_area", "unnormalized_mode_power"}
    df = np.abs(te_fraction(opened) - te_fraction(closed))
    da = np.abs(area(opened) / area(closed) - 1)
    print(f"\nV9 template f_TE closed {te_fraction(closed)}, open {te_fraction(opened)}, |delta| {df}")
    print(f"V10 template A_eff closed {area(closed)}, open {area(opened)}, relative {da}")
    assert np.all(df <= 1e-3), df
    assert np.all(da <= 1e-2), da
    assert set(opened.postprocessing) == {"te_polarization_fraction", "effective_area"}
    block = opened.summary()["mode_postprocessing"]
    assert list(block) == ["te_polarization_fraction", "effective_area", "integration_region"]
    assert block["integration_region"] == "physical_window"
    assert "integration_region" not in closed.summary()["mode_postprocessing"]


# -- V9: the film ----------------------------------------------------------------------------------

@pytest.mark.slow
def test_v9_film_te_fraction_converges_to_one():
    text = build("slab", 1, target=2.85, edges=TOP_BOTTOM)
    deficits = []
    for factor in (1, 0.5, 0.25):
        result = solve(scaled(text, factor))
        deficits.append(float(1 - te_fraction(result)[0]))
    print(f"\nV9 film 1 - f_TE at x 1, 1/2, 1/4: {deficits}")
    assert all(d <= 1e-3 for d in deficits), deficits
    assert deficits[0] > deficits[1] > deficits[2], deficits


