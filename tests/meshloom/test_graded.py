# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""A graded size: ``h`` given as a function of position. V8 graded and the argument.

- V8 graded (docs/packages/meshine/validation3d.md): C2 with
  h(x) = min(0.2, 0.02 + 0.3 |x - (1/2, 1/2, 1/2)|); r_e = edge length / h(edge
  midpoint), with h from the formula; at least 90% of the edges have r_e / 1.281 in
  [0.5, 1.5] (1.281: the baseline median on C1 at h = 0.1).
- A constant function meshes as the same number does, bit for bit: the field is read
  through the same size bounds.
- The function is sampled once on a background octree; a function that returns the wrong
  shape, a size that is not finite and > 0, or that would need more cells than the cap is
  refused with ValueError.
"""

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

import quality_cases as Q  # noqa: E402
from test_determinism import digest  # noqa: E402

CENTRE = np.array([0.5, 0.5, 0.5])


def v8_size(x):
    return np.minimum(0.2, 0.02 + 0.3 * np.linalg.norm(np.asarray(x) - CENTRE, axis=-1))


def test_v8_graded_cube():
    (pts, facets), _ = Q.c2()
    m = meshloom.generate3d(pts, facets, h=v8_size)
    e, length = Q.edges(m)
    x = m["nodes"]
    r = length / v8_size(0.5 * (x[e[:, 0]] + x[e[:, 1]])) / 1.281
    inside = float(np.mean((r >= 0.5) & (r <= 1.5)))
    assert inside >= 0.90, inside
    # graded at all: within 0.1 of the centre h <= 0.05, beyond 0.6 h = 0.2 (a uniform
    # mesh would have the same median edge in both)
    mid = 0.5 * (x[e[:, 0]] + x[e[:, 1]])
    d = np.linalg.norm(mid - CENTRE, axis=1)
    assert np.median(length[d < 0.1]) < 0.5 * np.median(length[d > 0.6])


def test_graded_is_deterministic():
    (pts, facets), _ = Q.c2()
    a, b = (digest(meshloom.generate3d(pts, facets, h=v8_size)) for _ in range(2))
    assert a == b


@pytest.mark.parametrize("case,h", [("C2", 0.12), ("C3", 0.8), ("C5", 0.24)])
def test_a_constant_function_is_the_number(case, h):
    kw = Q.case_kwargs(case, h)
    want = digest(meshloom.generate3d(**kw))
    kw["h"] = lambda x: np.full(len(x), h)
    assert digest(meshloom.generate3d(**kw)) == want


@pytest.mark.parametrize("fn,match", [
    (lambda x: np.ones(len(x) + 1), "one size per point"),
    (lambda x: -np.ones(len(x)), "finite sizes > 0"),
    (lambda x: np.full(len(x), np.nan), "finite sizes > 0"),
    (lambda x: x[:, 0], "finite sizes > 0"),  # 0 at the corner x = 0
    (lambda x: "a", "calling it|one size per point"),
    (lambda x: np.full(len(x), 1e-9), "octree cells"),
])
def test_bad_size_functions_are_refused(fn, match):
    (pts, facets), _ = Q.c2()
    with pytest.raises(ValueError, match=match):
        meshloom.generate3d(pts, facets, h=fn)
