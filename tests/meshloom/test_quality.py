# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Mesh quality and size of ``meshloom.generate3d`` against the frozen baseline: V10 and V8.

Rows of docs/packages/meshine/validation3d.md, with the constants of its "Frozen
baseline constants" section (Gmsh 4.15.2 with the Netgen optimizer):

- V10 on C2 (unit cube), C3 (chip package, 3 regions) and C6 (Fichera corner,
  [-1,1]^3 minus [0,1]^3) at the plan's three sizes: the smallest dihedral angle is at
  least the gate, the mean q (3 inradius / circumradius) at least the floor and the
  tetrahedron count T within [0.75, 1.33] T_B. No input angle of these cases is below
  the exemption limits, so every tetrahedron counts. C4 and C5 (curved surfaces) wait
  for curved input; the rows of this module are the ones measured so far.
- V8 on C2 at three sizes and on C3 with the die at h/2: per region, the median of
  edge length over h within +-10% of the baseline median and the 95th percentile at
  most the baseline's + 0.10 (the die's edges over h/2).

The finest sizes run with the slow studies. Rows the mesher does not meet yet are not
here; they are listed on the meshloom page under its limits.
"""

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

try:  # the box assembly of the refinement tests; the installed-wheel check renames it
    from test_refine import C3_SEEDS, c2, c3, grid_plc  # noqa: E402
except ImportError:
    from test_meshloom_refine import C3_SEEDS, c2, c3, grid_plc  # noqa: E402


def c6():
    """Fichera corner: [-1,1]^3 minus [0,1]^3."""
    g = [-1.0, 0.0, 1.0]
    cells = {(i, j, k): "a" for i in range(2) for j in range(2) for k in range(2) if (i, j, k) != (1, 1, 1)}
    return grid_plc(g, g, g, cells)


def generate(case, h):
    if case == "C2":
        (pts, facets), _ = c2()
        return meshloom.generate3d(pts, facets, h=h)
    if case == "C3":
        (pts, facets), _ = c3()
        return meshloom.generate3d(pts, facets, h=h, region_points=C3_SEEDS)
    pts, facets = c6()
    return meshloom.generate3d(pts, facets, h=h)


def dihedral_and_q(m):
    """Smallest dihedral angle (degrees) and q = 3 inradius / circumradius per tetrahedron."""
    x = m["nodes"][m["tetrahedra"]]
    a, b, c = x[:, 1] - x[:, 0], x[:, 2] - x[:, 0], x[:, 3] - x[:, 0]
    v6 = np.abs(np.einsum("ij,ij->i", a, np.cross(b, c)))
    area = sum(0.5 * np.linalg.norm(np.cross(x[:, j] - x[:, i], x[:, k] - x[:, i]), axis=1)
               for i, j, k in ((1, 2, 3), (0, 2, 3), (0, 1, 3), (0, 1, 2)))
    rin = 0.5 * v6 / area
    num = (np.einsum("ij,ij->i", a, a)[:, None] * np.cross(b, c) + np.einsum("ij,ij->i", b, b)[:, None] * np.cross(c, a)
           + np.einsum("ij,ij->i", c, c)[:, None] * np.cross(a, b))
    rc = np.linalg.norm(num, axis=1) / (2 * v6)
    angles = []
    for i, j, k, l in ((0, 1, 2, 3), (0, 2, 1, 3), (0, 3, 1, 2), (1, 2, 0, 3), (1, 3, 0, 2), (2, 3, 0, 1)):
        e = x[:, j] - x[:, i]
        n1, n2 = np.cross(e, x[:, k] - x[:, i]), np.cross(e, x[:, l] - x[:, i])
        cos = np.einsum("ij,ij->i", n1, n2) / np.linalg.norm(n1, axis=1) / np.linalg.norm(n2, axis=1)
        angles.append(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))
    return np.min(angles, axis=0), 3 * rin / rc


def edges(m):
    t = m["tetrahedra"]
    e = np.unique(np.sort(np.concatenate([t[:, [i, j]] for i in range(4) for j in range(i + 1, 4)]), axis=1), axis=0)
    return e, np.linalg.norm(m["nodes"][e[:, 0]] - m["nodes"][e[:, 1]], axis=1)


# (case, h): (min dihedral gate, mean q floor, T window), from the frozen baseline table
V10 = {
    ("C2", 0.12): (15.0, 0.7906, (2721, 4823)),
    ("C2", 0.06): (15.0, 0.8274, (15919, 28229)),
    ("C2", 0.03): (15.0, 0.8429, (118695, 210484)),
    ("C3", 0.8): (13.80, 0.7337, (3248, 5758)),
    ("C3", 0.4): (12.82, 0.7782, (16189, 28708)),
    ("C3", 0.2): (12.61, 0.8176, (105384, 186880)),
    ("C6", 0.24): (15.0, 0.7794, (2807, 4976)),
    ("C6", 0.12): (15.0, 0.8203, (14852, 26336)),
    ("C6", 0.06): (15.0, 0.8403, (103604, 183723)),
}
FINEST = {("C2", 0.03), ("C3", 0.2), ("C6", 0.06)}
V10_ROWS = [pytest.param(*k, marks=pytest.mark.slow) if k in FINEST else k for k in V10]


@pytest.mark.parametrize("case,h", V10_ROWS)
def test_v10_quality_against_the_baseline(case, h):
    theta_gate, q_floor, (lo, hi) = V10[(case, h)]
    theta, q = dihedral_and_q(generate(case, h))
    assert theta.min() >= theta_gate, (case, h, float(theta.min()))
    assert q.mean() >= q_floor, (case, h, float(q.mean()))
    assert lo <= len(q) <= hi, (case, h, len(q))


# V8: (median window, p95 bound) per case and size; C3 per region (substrate, die, mold)
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
