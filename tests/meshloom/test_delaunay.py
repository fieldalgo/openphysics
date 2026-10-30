# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""V17 of the pre-registered 3D plan on the C12 point sets: the kernel's Delaunay
tetrahedralization is (a) locally Delaunay on every interior face under the
index-ordered symbolic perturbation, checked exactly, and (b) the same for three
insertion orders. The exact check is the kernel's verifier, which reads only the
output arrays; small sets are also checked by an independent Python ``Fraction``
implementation. Throughput on 10^6 points is a benchmark
(``benchmarks/benchmark_delaunay.py``), not a CI test.
"""

import itertools
from fractions import Fraction

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from meshloom._core import delaunay, verify_delaunay  # noqa: E402


def canonical(tets):
    return np.unique(np.sort(tets, axis=1), axis=0)


def uniform(n, seed):
    return np.random.default_rng(seed).random((n, 3))


def lattice(m, spacing=0.02):
    g = np.arange(m) * spacing
    return np.array(list(itertools.product(g, g, g)), dtype=float)


def shells():
    """Integer points on the concentric spheres of radius 15, 21 and 25 (exactly
    cospherical sets), plus the centre."""
    pts = [(0, 0, 0)]
    r = range(-25, 26)
    for x, y, z in itertools.product(r, r, r):
        if x * x + y * y + z * z in (225, 441, 625):
            pts.append((x, y, z))
    return np.array(pts, dtype=float) / 8.0


def coplanar_layers(seed):
    """Dyadic grids on three parallel planes and random points on a tilted plane:
    many exactly coplanar and cocircular subsets."""
    rng = np.random.default_rng(seed)
    g = np.arange(12) / 16.0
    layers = [np.column_stack([x.ravel(), y.ravel(), np.full(x.size, z)])
              for z in (0.0, 0.375, 0.75) for x, y in [np.meshgrid(g, g)]]
    xy = rng.integers(0, 256, size=(300, 2)) / 256.0
    tilted = np.column_stack([xy, (xy[:, 0] + xy[:, 1]) / 2.0])
    return np.vstack(layers + [tilted])


C12 = {
    "uniform-1e3": lambda: uniform(1_000, 1),
    "uniform-1e4": lambda: uniform(10_000, 2),
    "uniform-1e5": lambda: uniform(100_000, 3),
    "lattice-50": lambda: lattice(50),
    "shells": shells,
    "coplanar-layers": lambda: coplanar_layers(4),
}


@pytest.fixture(scope="module", params=sorted(C12))
def case(request):
    pts = C12[request.param]()
    tets, vertex_of, stats = delaunay(pts)
    return request.param, pts, tets, vertex_of, stats


def test_v17a_every_interior_face_is_locally_delaunay(case):
    name, pts, tets, vertex_of, stats = case
    report = verify_delaunay(pts, tets)
    assert report["tets"] == len(tets)
    assert report["vertices"] == len(np.unique(pts, axis=0))
    assert stats["walk_fallbacks"] == 0
    assert (vertex_of == np.arange(len(pts))).all()
    # the hull volume is filled exactly once: compare with the box or ball it spans
    p = pts[tets]
    vol = np.einsum("ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0])).sum() / 6
    assert vol > 0
    if name == "lattice-50":
        assert vol == pytest.approx(0.98 ** 3, rel=1e-12)
        assert stats["insphere_sos"] > 0


def test_v17b_three_insertion_orders_give_the_same_tetrahedra(case):
    name, pts, tets, _, _ = case
    n = len(pts)
    reverse = np.arange(n)[::-1]
    shuffled = np.random.default_rng(17).permutation(n)
    want = canonical(tets)
    for order in (reverse, shuffled):
        other, _, _ = delaunay(pts, order=order)
        np.testing.assert_array_equal(canonical(other), want)


def _fraction_check(pts, tets):
    """Independent exact check: every interior face is locally Delaunay with the
    index-ordered perturbation, written from the definition (5 x 5 lifted determinant
    with an explicit perturbation small enough to order its powers)."""
    q = [[Fraction(x) for x in p] for p in pts.tolist()]

    def det(m):
        if len(m) == 1:
            return m[0][0]
        return sum((-1) ** j * m[0][j] * det([r[:j] + r[j + 1:] for r in m[1:]]) for j in range(len(m)) if m[0][j])

    def in_conflict(t, e):
        ids = list(t) + [e]
        rows = [q[i] + [sum(x * x for x in q[i]), Fraction(1)] for i in ids]
        s = det(rows)
        if s == 0:
            rank = [sum(ids[j] > ids[i] for j in range(5)) for i in range(5)]
            cof = [abs(det([q[ids[j]] + [Fraction(1)] for j in range(5) if j != i])) for i in range(5)]
            delta = min(c for c in cof if c) / (2 * sum(cof) + 1)
            s = det([r[:3] + [r[3] + delta ** (rank[i] + 1), r[4]] for i, r in enumerate(rows)])
        return -s > 0  # insphere = -det5, positive inside

    faces = {}
    for t in tets.tolist():
        for i in range(4):
            faces.setdefault(tuple(sorted(t[:i] + t[i + 1:])), []).append((t, t[i]))
    checked = 0
    for owners in faces.values():
        if len(owners) == 2:
            (t1, _), (_, e2) = owners
            assert not in_conflict(t1, e2)
            checked += 1
    return checked


@pytest.mark.parametrize("name", ["lattice", "shells-small", "uniform"])
def test_v17a_small_sets_agree_with_an_independent_fraction_check(name):
    pts = {"lattice": lattice(4, 0.25), "uniform": uniform(150, 5),
           "shells-small": np.array([p for p in shells().tolist() if sum(x * x for x in p) * 64 <= 225])}[name]
    tets, _, _ = delaunay(pts)
    verify_delaunay(pts, tets)
    assert _fraction_check(pts, tets) > 0


def test_duplicates_map_to_the_lowest_index():
    pts = uniform(200, 6)
    pts = np.vstack([pts, pts[[5, 7, 5]]])
    tets, vertex_of, stats = delaunay(pts)
    assert vertex_of[200:].tolist() == [5, 7, 5]
    assert stats["duplicates"] == 3
    assert not np.isin(tets, [200, 201, 202]).any()
    verify_delaunay(pts, tets)


@pytest.mark.parametrize("pts, message", [
    (np.zeros((5, 3)), "coincide"),
    (np.column_stack([np.arange(5.0), np.zeros(5), np.zeros(5)]), "collinear"),
    (np.column_stack([np.arange(5.0), np.arange(5.0) ** 2, np.zeros(5)]), "coplanar"),
    (np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1e300]]), "2\\^-120"),
])
def test_degenerate_or_out_of_domain_inputs_are_refused(pts, message):
    with pytest.raises(ValueError, match=message):
        delaunay(pts)


def test_verifier_rejects_a_non_delaunay_or_incomplete_mesh():
    pts = uniform(300, 8)
    tets, _, _ = delaunay(pts)
    with pytest.raises(ValueError):
        verify_delaunay(pts, tets[1:])
    flipped = tets.copy()
    flipped[0, [0, 1]] = flipped[0, [1, 0]]
    with pytest.raises(ValueError, match="positively oriented"):
        verify_delaunay(pts, flipped)
    # the Delaunay mesh of slightly moved points is a different connectivity, which is
    # not Delaunay (or not even valid) for the original points
    moved = pts.copy()
    moved[:, 0] += 0.02 * np.sin(40 * pts[:, 1])
    other, _, _ = delaunay(moved)
    assert canonical(other).tolist() != canonical(tets).tolist()
    with pytest.raises(ValueError):
        verify_delaunay(pts, other)
