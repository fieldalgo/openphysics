# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Edge lengths of ``meshloom.generate3d`` against the frozen baseline: V8.

Rows of docs/packages/meshine/validation3d.md, with the constants of its "Frozen
baseline constants" section (Gmsh 4.15.2 with the Netgen optimizer):

- V8 on C1 and C2 at three sizes and on C3 with the die at h/2: per region, the median of
  edge length over h within +-10% of the baseline median and the 95th percentile at
  most the baseline's + 0.10 (the die's edges over h/2).


The finest sizes run with the slow studies. Rows the mesher does not meet yet are not
here; they are listed on the meshloom page under its limits. The cases and measures are
in quality_cases.py.
"""

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from quality_cases import C3_SEEDS, c2, c3, edges, generate  # noqa: E402

# V8: (median window, p95 bound) per case and size; C3 per region (substrate, die, mold)
V8_C1 = {0.2: ((1.060, 1.296), 1.771), 0.1: ((1.153, 1.409), 1.810), 0.05: ((1.191, 1.456), 1.810)}
V8_C2 = {0.12: ((0.947, 1.158), 1.684), 0.06: ((1.120, 1.369), 1.777), 0.03: ((1.166, 1.425), 1.782)}
V8_C3 = {
    0.96: (((0.687, 0.839), 1.332), ((0.827, 1.011), 1.480), ((0.688, 0.841), 1.339)),
    0.48: (((0.843, 1.031), 1.547), ((0.885, 1.081), 1.646), ((0.843, 1.030), 1.560)),
    0.24: (((0.893, 1.091), 1.604), ((1.049, 1.282), 1.766), ((0.893, 1.091), 1.623)),
}


@pytest.mark.parametrize("h", [0.12, 0.06, pytest.param(0.03, marks=pytest.mark.slow)])
def test_v8_cube_edge_lengths(h):
    (pts, facets), _ = c2()
    _, length = edges(meshloom.generate3d(pts, facets, h=h))
    (lo, hi), p95 = V8_C2[h]
    r = length / h
    assert lo <= np.median(r) <= hi, (h, float(np.median(r)))
    assert np.percentile(r, 95) <= p95, (h, float(np.percentile(r, 95)))


@pytest.mark.parametrize("h", [0.2, 0.1, pytest.param(0.05, marks=pytest.mark.slow)])
def test_v8_sphere_edge_lengths(h):
    _, length = edges(generate("C1", h))
    (lo, hi), p95 = V8_C1[h]
    r = length / h
    assert lo <= np.median(r) <= hi, (h, float(np.median(r)))
    assert np.percentile(r, 95) <= p95, (h, float(np.percentile(r, 95)))


def c3_regions(h):
    """Edge length over the region's h for C3 with the die at h/2: substrate, die, mold."""
    (pts, facets), _ = c3()
    m = meshloom.generate3d(pts, facets, h={"substrate": h, "die": h / 2, "mold": h}, region_points=C3_SEEDS)
    e, length = edges(m)
    mid = 0.5 * (m["nodes"][e[:, 0]] + m["nodes"][e[:, 1]])
    die = (mid[:, 0] >= 3) & (mid[:, 0] <= 7) & (mid[:, 1] >= 3) & (mid[:, 1] <= 7) & (mid[:, 2] >= 1) & (mid[:, 2] <= 1.5)
    r = length / np.where(die, h / 2, h)
    below = mid[:, 2] < 1
    return {"substrate": r[below & ~die], "die": r[die], "mold": r[~below & ~die]}


@pytest.mark.parametrize("h", [0.96, 0.48, pytest.param(0.24, marks=pytest.mark.slow)])
def test_v8_chip_edge_lengths_per_region(h):
    ratios = c3_regions(h)
    for (name, r), ((lo, hi), p95) in zip(ratios.items(), V8_C3[h]):
        assert lo <= np.median(r) <= hi, (h, name, float(np.median(r)))
        assert np.percentile(r, 95) <= p95, (h, name, float(np.percentile(r, 95)))
