# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Mesh quality of ``meshloom.generate3d`` against the frozen baseline: V10.

Rows of docs/packages/meshine/validation3d.md, with the constants of its "Frozen
baseline constants" section (Gmsh 4.15.2 with the Netgen optimizer):

- V10 on C2 (unit cube), C3 (chip package, 3 regions), C4 (via r = 0.3 through
  [-1,1]^2 x [0,1]), C5 (sphere r = 0.5 in [-1,1]^3) and C6 (Fichera corner, [-1,1]^3
  minus [0,1]^3) at the plan's three sizes, all 15 pairs: the smallest dihedral angle
  is at least the gate, the mean q (3 inradius / circumradius) at least the floor and
  the tetrahedron count T within [0.75, 1.33] T_B. No input angle of these cases is
  below the exemption limits, so every tetrahedron counts. C4 and C5 come from
  ``meshloom.builder``.

The finest sizes run with the slow studies. Rows the mesher does not meet yet are not
here; they are listed on the meshloom page under its limits. The cases and measures are
in quality_cases.py.
"""

import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from quality_cases import dihedral_and_q, generate  # noqa: E402

# (case, h): (min dihedral gate, mean q floor, T window), from the frozen baseline table
V10 = {
    ("C2", 0.12): (15.0, 0.7906, (2721, 4823)),
    ("C2", 0.06): (15.0, 0.8274, (15919, 28229)),
    ("C2", 0.03): (15.0, 0.8429, (118695, 210484)),
    ("C3", 0.8): (13.80, 0.7337, (3248, 5758)),
    ("C3", 0.4): (12.82, 0.7782, (16189, 28708)),
    ("C3", 0.2): (12.61, 0.8176, (105384, 186880)),
    ("C4", 0.2): (15.0, 0.7642, (2343, 4154)),
    ("C4", 0.1): (15.0, 0.8130, (14309, 25373)),
    ("C4", 0.05): (12.89, 0.8369, (99630, 176677)),
    ("C5", 0.24): (15.0, 0.7768, (2834, 5024)),
    ("C5", 0.12): (15.0, 0.8185, (17035, 30208)),
    ("C5", 0.06): (15.0, 0.8385, (120495, 213676)),
    ("C6", 0.24): (15.0, 0.7794, (2807, 4976)),
    ("C6", 0.12): (15.0, 0.8203, (14852, 26336)),
    ("C6", 0.06): (15.0, 0.8403, (103604, 183723)),
}
FINEST = {("C2", 0.03), ("C3", 0.2), ("C4", 0.05), ("C5", 0.06), ("C6", 0.06)}
V10_ROWS = [pytest.param(*k, marks=pytest.mark.slow) if k in FINEST else k for k in V10]


@pytest.mark.parametrize("case,h", V10_ROWS)
def test_v10_quality_against_the_baseline(case, h):
    theta_gate, q_floor, (lo, hi) = V10[(case, h)]
    theta, q = dihedral_and_q(generate(case, h))
    assert theta.min() >= theta_gate, (case, h, float(theta.min()))
    assert q.mean() >= q_floor, (case, h, float(q.mean()))
    assert lo <= len(q) <= hi, (case, h, len(q))
