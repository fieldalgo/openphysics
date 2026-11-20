# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Refinement in ``mesh_plc`` (``h``, ``ratio``): V18, V7, V26, the cap and the arguments.

Rows of docs/packages/meshine/validation3d.md:

- V18: every C10 input refines to the end at h = 1/2, 1/4 and 1/8 of its size with
  ratio 2 and the derived point cap, and the mesh passes V1-V4
  (``test_adversarial.check``); the Steiner counts are recorded as test properties.
  stacked-layers gives the same mesh at the three sizes (its refinement is driven by
  the ratio), so it runs once, with the slow studies (about 90 s).
- V7: on C2 (unit cube) and C3 (chip package, 3 regions) at the sizes of the plan, in
  guaranteed mode (B = 2), every tetrahedron has radius-edge ratio (circumradius over
  shortest edge) at most 2(1 + 1e-9), decided exactly in rational arithmetic on the
  output doubles for every tetrahedron whose ratio in doubles exceeds 0.95 of the bound
  (below that the rounding error of the double evaluation cannot reach it). C9 has no
  dimensions in the plan yet and is not run. The coarsest sizes also pass V1-V4 with
  the exact region volumes. C2 at h = 0.03 and C3 at h = 0.2 run with the slow studies.
- V26 (part): refinement is deterministic: C2 at h = 0.1, C3 at h = 0.8 and two C10
  inputs give byte-identical arrays in 3 fresh processes and 2 runs in this process.
- Sizes per region: C3 with the die at h/2 (V8's die case) refines the die and
  keeps V7; a mapping of sizes needs every region name.
- ``meshloom.generate3d``: the documented cube example (V1-V4), facet tags, and the
  practical and guaranteed bounds on C3 at h = 0.4.
- The cap: a small ``max_points`` raises ``RefineError``; bad arguments are refused.
"""

import hashlib
from fractions import Fraction
from pathlib import Path
import subprocess
import sys

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
V18_SIZES = (0.5, 0.25, 0.125)
# the same mesh at every size, about 90 s (19k nodes; the exact V1-V4 check takes two
# thirds): once, with the slow studies
ONCE_SLOW = {"stacked-layers"}


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


def v18_params():
    for name in sorted(A.CASES):
        if name in ONCE_SLOW:
            yield pytest.param(name, 0.25, marks=pytest.mark.slow)
        else:
            for k in V18_SIZES:
                yield name, k


@pytest.mark.parametrize("name,k", list(v18_params()))
def test_v18_c10_refines_to_the_end(name, k, record_property):
    pts, facets, volumes, exact = A.CASES[name]
    size = np.ptp(pts, axis=0).max()
    m = mesh_plc(pts, facets, h=k * size, ratio=2.0)
    A.check(m, pts, facets, volumes, False, euler=True)
    st = m["stats"]
    for key in ("segment_points", "facet_points", "volume_points", "minimal_cavities"):
        record_property(key, st[key])
    assert st["minimal_cavities"] <= st["segment_points"] + st["facet_points"] + st["volume_points"]


def exactly_within(m, rho, bound):
    """Indices of the tetrahedra whose radius-edge ratio exceeds ``bound``, decided exactly
    on the output doubles for those whose ratio in doubles exceeds 0.95 bound."""
    b2 = Fraction(bound) ** 2
    over = []
    for t in np.flatnonzero(rho > 0.95 * bound):
        p = [[Fraction(float(c)) for c in m["nodes"][v]] for v in m["tetrahedra"][t]]
        a = [[p[i][j] - p[0][j] for j in range(3)] for i in (1, 2, 3)]
        r = [sum(x * x for x in row) / 2 for row in a]  # circumcentre o - p0 solves a (o - p0) = r

        def det(m3):
            return (m3[0][0] * (m3[1][1] * m3[2][2] - m3[1][2] * m3[2][1])
                    - m3[0][1] * (m3[1][0] * m3[2][2] - m3[1][2] * m3[2][0])
                    + m3[0][2] * (m3[1][0] * m3[2][1] - m3[1][1] * m3[2][0]))

        d = det(a)
        o = [det([[r[i] if j == c else a[i][j] for j in range(3)] for i in range(3)]) / d for c in range(3)]
        r2 = sum(x * x for x in o)
        l2 = min(sum((p[i][j] - p[k][j]) ** 2 for j in range(3)) for i in range(4) for k in range(i + 1, 4))
        if r2 > b2 * l2:
            over.append(int(t))
    return over


@pytest.mark.parametrize("case,h", [("C2", 0.12), ("C2", 0.06), pytest.param("C2", 0.03, marks=pytest.mark.slow),
                                    ("C3", 0.8), ("C3", 0.4), pytest.param("C3", 0.2, marks=pytest.mark.slow)])
def test_v7_guaranteed_mode(case, h):
    (pts, facets), volumes = {"C2": c2, "C3": c3}[case]()
    m = mesh_plc(pts, facets, h=h, ratio=2.0)
    rho = radius_edge(m)
    over = exactly_within(m, rho, V7_BOUND)
    assert not over, (case, h, len(over), float(rho.max()))
    assert m["stats"]["region_count"] == len(volumes)
    if h >= {"C2": 0.12, "C3": 0.8}[case]:  # V1-V4 from exact arithmetic on the coarsest size
        got = A.check(m, pts, facets, volumes, True, euler=True)
        assert [float(v) for v in got] == sorted(volumes)


def test_the_exact_ratio_check():
    # (0,0,0), (1,0,0), (0,1,0), (0,0,t): R = sqrt(1/2 + t^2/4), shortest edge t
    for t, flagged in ((0.25, True), (0.375, False), (0.75, False)):
        m = {"nodes": np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, t]], dtype=float),
             "tetrahedra": np.array([[0, 1, 2, 3]])}
        rho = radius_edge(m)
        assert rho[0] == pytest.approx((0.5 + t * t / 4) ** 0.5 / t)
        assert exactly_within(m, rho, V7_BOUND) == ([0] if flagged else [])


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


def _canonical_digest(m):
    h = hashlib.sha256()
    for key in ("nodes", "tetrahedra", "regions", "node_source"):
        h.update(np.ascontiguousarray(m[key]).tobytes())
    for facet in sorted(m["boundary_faces"]):
        h.update(np.int64(facet).tobytes() + np.ascontiguousarray(m["boundary_faces"][facet]).tobytes())
    for pair in sorted(m["interfaces"]):
        h.update(np.array(pair, dtype=np.int64).tobytes() + np.ascontiguousarray(m["interfaces"][pair]).tobytes())
    return h.hexdigest()


V26_CASES = (("C2", 0.1), ("C3", 0.8), ("schonhardt", 0.25), ("near-coplanar-quads", 0.25))


def v26_digests():
    out = []
    for name, h in V26_CASES:
        if name in ("C2", "C3"):
            (pts, facets), _ = {"C2": c2, "C3": c3}[name]()
            m = mesh_plc(pts, facets, h=h, ratio=2.0)
        else:
            pts, facets, _, _ = A.CASES[name]
            m = mesh_plc(pts, facets, h=h * np.ptp(pts, axis=0).max(), ratio=2.0)
        out.append(_canonical_digest(m))
    return out


def test_v26_refinement_is_deterministic():
    here = Path(__file__).resolve()
    code = (f"import sys; sys.path.insert(0, {str(here.parent)!r}); "
            f"import {here.stem} as T; print(' '.join(T.v26_digests()))")
    fresh = [subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                            cwd=here.parent).stdout.split() for _ in range(3)]
    inproc = [v26_digests() for _ in range(2)]
    assert all(len(d) == len(V26_CASES) for d in fresh + inproc)
    assert all(d == inproc[0] for d in fresh + inproc), fresh + inproc


C3_SEEDS = [((5.0, 5.0, 0.5), "substrate"), ((5.0, 5.0, 1.25), "die"), ((1.0, 1.0, 2.0), "mold")]


def test_sizes_per_region():
    (pts, facets), _ = c3()

    def median_edges(m):
        x = m["nodes"][m["tetrahedra"]]
        e = np.linalg.norm(x[:, 1] - x[:, 0], axis=1)
        return [float(np.median(e[m["regions"] == r])) for r in range(3)]

    uniform = mesh_plc(pts, facets, h=0.8, ratio=2.0, region_points=C3_SEEDS)
    die = mesh_plc(pts, facets, h={"substrate": 0.8, "die": 0.4, "mold": 0.8}, ratio=2.0, region_points=C3_SEEDS)
    assert die["region_names"] == ["substrate", "die", "mold"]
    u, d = median_edges(uniform), median_edges(die)
    assert d[1] < 0.75 * u[1], (u, d)  # the die is finer (at h = 0.8 its 0.5 height already limits it)
    assert 0.9 < d[0] / u[0] < 1.1 and 0.9 < d[2] / u[2] < 1.1, (u, d)
    assert not exactly_within(die, radius_edge(die), V7_BOUND)
    got = A.check(die, pts, facets, [100.0, 8.0, 142.0], True, euler=True)
    assert sorted(float(v) for v in got) == [8.0, 100.0, 142.0]
    with pytest.raises(ValueError, match="missing"):
        mesh_plc(pts, facets, h={"substrate": 0.4, "die": 0.2}, ratio=2.0, region_points=C3_SEEDS)
    with pytest.raises(ValueError, match="region_points"):
        mesh_plc(pts, facets, h={"die": 0.2}, ratio=2.0)


def test_generate3d():
    cube = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], float)
    faces = [[[0, 3, 2, 1]], [[4, 5, 6, 7]], [[0, 1, 5, 4]], [[2, 3, 7, 6]], [[1, 2, 6, 5]], [[0, 4, 7, 3]]]
    m = meshloom.generate3d(cube, faces, h=0.1)  # the example of the meshloom page
    assert sorted(m["boundary_faces"], key=int) == [str(i) for i in range(6)]  # facet tags, by default str(i)
    by_index = dict(m, boundary_faces={int(k): v for k, v in m["boundary_faces"].items()},
                    boundary_nodes={int(k): v for k, v in m["boundary_nodes"].items()})
    A.check(by_index, cube, faces, [1.0], True, euler=True)
    tagged = meshloom.generate3d(cube, faces, h=0.1, facet_tags=["bottom", "top"] + ["side"] * 4)
    assert sorted(tagged["boundary_faces"]) == ["bottom", "side", "top"]
    assert len(tagged["boundary_faces"]["side"]) == sum(len(m["boundary_faces"][str(i)]) for i in range(2, 6))
    with pytest.raises(ValueError, match="facet_tags"):
        meshloom.generate3d(cube, faces, h=0.1, facet_tags=["a"])
    (pts, facets), _ = c3()
    for quality, bound in (("practical", meshloom.PRACTICAL_RATIO), ("guaranteed", meshloom.GUARANTEED_RATIO)):
        m = meshloom.generate3d(pts, facets, h=0.4, quality=quality, region_points=C3_SEEDS)
        assert m["region_names"] == ["substrate", "die", "mold"]
        assert not exactly_within(m, radius_edge(m), bound * (1 + 1e-9)), quality
    with pytest.raises(meshloom.RefineError):
        meshloom.generate3d(pts, facets, h=0.2, max_points=50)
