# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The generator of the boundary-recovery readiness set (``cdt_inputs.py``).

Small builds of every category must be valid closed surfaces: float32 coordinates,
every edge on exactly two triangles, accepted by the exact PLC check, and the features
their category promises.
"""

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

import cdt_inputs as C  # noqa: E402
from meshloom._core import check_plc  # noqa: E402


@pytest.mark.parametrize("category", C.CATEGORIES)
def test_small_build_is_a_valid_closed_surface(category):
    P, T, info = C.build(category, 2000, seed=1)
    assert np.array_equal(P, P.astype(np.float32).astype(np.float64))
    assert len(np.unique(P, axis=0)) == len(P)
    e = np.sort(np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]), axis=1)
    _, count = np.unique(e, axis=0, return_counts=True)
    assert (count == 2).all()
    check_plc(P, np.zeros((0, 2), dtype=np.int64), [[list(map(int, t))] for t in T])
    if category in ("needle", "mixed"):
        assert info["min_angle_deg"] < 1.0  # down to about 0.01 at readiness sizes
    if category == "fan":
        assert info["fan_k"] > 0 and info["min_angle_deg"] <= 360.0 / info["fan_k"] + 1e-9
    if category in ("touch", "mixed"):
        assert 0.0 < info["gaps"][0] < 1e-5


def test_builds_are_deterministic():
    a = C.build("mixed", 3000, seed=4)
    b = C.build("mixed", 3000, seed=4)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])
