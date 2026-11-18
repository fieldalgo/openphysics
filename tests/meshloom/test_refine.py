# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Refinement in ``mesh_plc`` (``h``, ``ratio``): termination, V1-V4 and V7.

- C10: every adversarial input refines to the end at h = 1/4 of its size with ratio 2
  and the derived point cap, and the mesh passes V1-V4 (``test_adversarial.check``).
  stacked-layers, C2 at h = 0.03 and C3 at h = 0.2 take 9-90 s and run with the slow
  studies.
- V7 (docs/packages/meshine/validation3d.md): on C2 (unit cube) and C3 (chip package, 3
  regions) at the sizes of the plan, in guaranteed mode (B = 2), the largest
  radius-edge ratio (circumradius over shortest edge) is at most 2(1 + 1e-9). C9 has no
  dimensions in the plan yet and is not run. The coarser sizes also pass V1-V4 with the
  exact region volumes.
- The cap: a small ``max_points`` raises ``RefineError``; bad arguments are refused.
"""

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from meshloom._core import RefineError, mesh_plc  # noqa: E402

try:  # the checker of V1-V4; the installed-wheel check copies it under another name
    import test_adversarial as A  # noqa: E402
except ImportError:
    import test_meshloom_adversarial as A  # noqa: E402

V7_BOUND = 2 * (1 + 1e-9)
# about 90 s (19k nodes; the exact V1-V4 check takes two thirds): run with the slow studies
SLOW = {"stacked-layers"}


def grid_plc(xs, ys, zs, cells):
    """Boundary and interface rectangles of cells {(i, j, k): material} on the grid xs x ys x zs."""
    grid = (xs, ys, zs)
    index, points, facets = {}, [], []

    def pid(c):
        if c not in index:
            index[c] = len(points)
            points.append([grid[a][c[a]] for a in range(3)])
        return index[c]

    for (i, j, k), mat in sorted(cells.items()):
        for axis in range(3):
            for side in (0, 1):
                nb = [i, j, k]
                nb[axis] += 1 if side else -1
                other = cells.get(tuple(nb))
                if other == mat or (other is not None and side == 0):
                    continue
                base = [i, j, k]
                base[axis] += side
                u, v = [a for a in range(3) if a != axis]
                corners = []
                for du, dv in ((0, 0), (1, 0), (1, 1), (0, 1)):
                    c = list(base)
                    c[u] += du
                    c[v] += dv
                    corners.append(pid(tuple(c)))
                facets.append([corners])
    return np.array(points, dtype=float), facets


def c2():
    return grid_plc([0.0, 1.0], [0.0, 1.0], [0.0, 1.0], {(0, 0, 0): "a"}), [1.0]


def c3():
    """Substrate 10 x 10 x [0, 1], die 4 x 4 x 0.5 centred on top, mold 10 x 10 x [1, 2.5]."""
    g = [0.0, 3.0, 7.0, 10.0]
    cells = {(i, j, 0): "substrate" for i in range(3) for j in range(3)}
    cells.update({(i, j, k): "mold" for i in range(3) for j in range(3) for k in (1, 2)})
    cells[(1, 1, 1)] = "die"
    return grid_plc(g, g, [0.0, 1.0, 1.5, 2.5], cells), [8.0, 100.0, 142.0]


def radius_edge(m):
    x = m["nodes"][m["tetrahedra"]]
    a, b, c = x[:, 1] - x[:, 0], x[:, 2] - x[:, 0], x[:, 3] - x[:, 0]
    d = 2 * np.einsum("ij,ij->i", a, np.cross(b, c))
    o = (np.einsum("ij,ij->i", a, a)[:, None] * np.cross(b, c) + np.einsum("ij,ij->i", b, b)[:, None] * np.cross(c, a)
         + np.einsum("ij,ij->i", c, c)[:, None] * np.cross(a, b)) / d[:, None]
    e = [np.linalg.norm(x[:, i] - x[:, j], axis=1) for i in range(4) for j in range(i + 1, 4)]
    return np.linalg.norm(o, axis=1) / np.min(e, axis=0)


@pytest.mark.parametrize("name", [pytest.param(n, marks=pytest.mark.slow) if n in SLOW else n for n in sorted(A.CASES)])
def test_c10_refines_to_the_end(name):
    pts, facets, volumes, exact = A.CASES[name]
    size = np.ptp(pts, axis=0).max()
    m = mesh_plc(pts, facets, h=0.25 * size, ratio=2.0)
    A.check(m, pts, facets, volumes, False, euler=True)
    st = m["stats"]
    assert st["minimal_cavities"] <= st["segment_points"] + st["facet_points"] + st["volume_points"]


@pytest.mark.parametrize("case,h", [("C2", 0.12), ("C2", 0.06), pytest.param("C2", 0.03, marks=pytest.mark.slow),
                                    ("C3", 0.8), ("C3", 0.4), pytest.param("C3", 0.2, marks=pytest.mark.slow)])
def test_v7_guaranteed_mode(case, h):
    (pts, facets), volumes = {"C2": c2, "C3": c3}[case]()
    m = mesh_plc(pts, facets, h=h, ratio=2.0)
    rho = radius_edge(m)
    assert rho.max() <= V7_BOUND, (case, h, float(rho.max()), int((rho > V7_BOUND).sum()))
    assert m["stats"]["region_count"] == len(volumes)
    if h >= {"C2": 0.12, "C3": 0.8}[case]:  # V1-V4 from exact arithmetic on the coarsest size
        got = A.check(m, pts, facets, volumes, True, euler=True)
        assert [float(v) for v in got] == sorted(volumes)


def test_the_point_cap_is_a_typed_error():
    (pts, facets), _ = c3()
    with pytest.raises(RefineError, match="more than 50 points"):
        mesh_plc(pts, facets, h=0.2, ratio=2.0, max_points=50)


@pytest.mark.parametrize("kw", [{"h": 0.0}, {"h": -1.0}, {"h": float("nan")}, {"ratio": 0.0},
                                {"ratio": float("inf")}, {"h": 1.0, "alpha": 0.0}, {"h": 1.0, "max_points": -1},
                                {"h": 1.0, "max_points": 1.5}, {"h": "1"}])
def test_bad_arguments_are_refused(kw):
    (pts, facets), _ = c2()
    with pytest.raises(ValueError):
        mesh_plc(pts, facets, **kw)


def test_no_refinement_without_h_or_ratio():
    (pts, facets), _ = c2()
    m = mesh_plc(pts, facets)
    assert m["stats"]["segment_points"] == m["stats"]["facet_points"] == m["stats"]["volume_points"] == 0
    assert len(m["nodes"]) == 8
