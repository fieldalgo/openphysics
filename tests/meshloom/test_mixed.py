# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Cross-language set of V16 for points stored on segments (M4 of the pre-registered 3D
plan): the kernel's predicates over a mix of input points and S points
``a + t (b - a)`` agree in sign with determinants evaluated in Python ``Fraction``
arithmetic. The S points' coordinates are exact rationals there, as in the kernel.

Cases: random points and segments over power-of-two scales; S points exactly on a
tilted lattice plane (coplanar for any t), exactly on a sphere or a circle (integer
segments with t = 1/2 or 1/4), coinciding with an input point, and the same with one
segment end a few ulps off. The perturbed predicates are checked against an explicit
small perturbation of the lifted column, ordered by global index (input points first,
then S points). The main V16 run for mixed points (10^4 random + 10^4 adversarial
cases per predicate against big integers) is the Rust test
``exact_ref::mixed_tests::v16_mixed_predicates_agree_with_exact_integers``.
"""

import itertools
import math
import random
from fractions import Fraction

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from meshloom._core import mixed_predicate_signs, spoint_coords  # noqa: E402

N_RANDOM = 1500
N_ADVERSARIAL = 1500

SPHERE = sorted({p for p in itertools.product(range(-21, 22), repeat=3) if p[0] ** 2 + p[1] ** 2 + p[2] ** 2 == 441})
CIRCLE = [(5, 0), (-5, 0), (0, 5), (0, -5), (3, 4), (-3, 4), (3, -4), (-3, -4), (4, 3), (-4, 3), (4, -3), (-4, -3)]


def sign(x):
    return (x > 0) - (x < 0)


def det(m):
    n = len(m)
    if n == 1:
        return m[0][0]
    return sum((-1) ** j * m[0][j] * det([row[:j] + row[j + 1:] for row in m[1:]]) for j in range(n) if m[0][j])


def sub(p, q):
    return [x - y for x, y in zip(p, q)]


def dot(p, q):
    return sum(x * y for x, y in zip(p, q))


def cross(p, q):
    return [p[1] * q[2] - p[2] * q[1], p[2] * q[0] - p[0] * q[2], p[0] * q[1] - p[1] * q[0]]


def kept(axis):
    return [(1, 2), (2, 0), (0, 1)][axis]


def nudge(x, k):
    for _ in range(abs(k)):
        if x == 0:
            break
        x = math.nextafter(x, math.copysign(math.inf, k))
    return x


def embed(x, y):
    """A conformal integer embedding of the plane: e1 = (1, 2, 2), e2 = (2, 1, -2)."""
    return [x + 2 * y, 2 * x + y, 2 * x - 2 * y]


class Batch:
    """Input points, S points and query groups of many cases, with the exact points."""

    def __init__(self):
        self.points, self.seg, self.t, self.groups = [], [], [], []

    def input(self, x):
        self.points.append([float(c) for c in x])
        return len(self.points) - 1

    def case(self, members):
        """members: ("in", x) or ("s", a, b, t); returns the group as (kind, index)."""
        g = []
        for m in members:
            if m[0] == "in":
                g.append(("in", self.input(m[1])))
            else:
                a, b = self.input(m[1]), self.input(m[2])
                self.seg.append((a, b))
                self.t.append(float(m[3]))
                g.append(("s", len(self.t) - 1))
        self.groups.append(g)

    def ids(self, g):
        n = len(self.points)
        return [i if k == "in" else n + i for k, i in g]

    def exact(self, g):
        out = []
        for k, i in g:
            if k == "in":
                out.append([Fraction(c) for c in self.points[i]])
            else:
                a, b = (self.points[j] for j in self.seg[i])
                t = Fraction(self.t[i])
                out.append([Fraction(x) + t * (Fraction(y) - Fraction(x)) for x, y in zip(a, b)])
        return out

    def run(self, kind, axis=2):
        query = np.array([self.ids(g) for g in self.groups], dtype=np.int64)
        seg = np.array(self.seg, dtype=np.int64).reshape(-1, 2)
        signs, counts = mixed_predicate_signs(kind, np.array(self.points), seg, np.array(self.t), query, axis)
        return signs, counts


def random_member(rng, scale):
    if rng.random() < 0.5:
        return ("in", [rng.uniform(-1, 1) * scale for _ in range(3)])
    a = [rng.uniform(-1, 1) * scale for _ in range(3)]
    b = [rng.uniform(-1, 1) * scale for _ in range(3)]
    return ("s", a, b, random_t(rng))


def random_t(rng):
    r = rng.random()
    if r < 0.2:
        return 2.0 ** -rng.randint(1, 50)
    if r < 0.4:
        return 1.0 - 2.0 ** -rng.randint(1, 52)
    if r < 0.6:
        return rng.randint(1, 15) / 16
    return min(max(rng.random(), 2.0 ** -60), 1.0 - 2.0 ** -53)


def s_at(rng, x, d, scale):
    """An S point exactly at x: segment x -+ d with t = 1/2, or x - d .. x + 3d with t = 1/4,
    sometimes with one end a few ulps off."""
    if rng.random() < 0.5:
        a, b, t = sub(x, d), [p + q for p, q in zip(x, d)], 0.5
    else:
        a, b, t = sub(x, d), [p + 3 * q for p, q in zip(x, d)], 0.25
    a, b = [c * scale for c in a], [c * scale for c in b]
    if rng.random() < 0.25:
        j = rng.randrange(3)
        if rng.random() < 0.5:
            a[j] = nudge(a[j], rng.choice([-2, -1, 1, 2]))
        else:
            b[j] = nudge(b[j], rng.choice([-2, -1, 1, 2]))
    return ("s", a, b, t)


def adversarial_members(rng, n, kind):
    scale = 2.0 ** rng.randint(-60, 60)
    if kind == "orient":
        pos = [[x, y, x + 2 * y] for x, y in ((rng.randint(0, 63), rng.randint(0, 63)) for _ in range(n))]

        def direction():
            u, v = rng.randint(-2, 2), rng.randint(-2, 2) + 0.5
            return [u, v, u + 2 * v]
    elif kind == "sphere":
        pos = [list(rng.choice(SPHERE)) for _ in range(n)]

        def direction():
            return [rng.randint(1, 3), -2, 3]
    else:
        pos = [embed(*rng.choice(CIRCLE)) for _ in range(n)]

        def direction():
            return embed(rng.randint(-2, 2), rng.randint(-2, 2) + 0.5)
    out = []
    for k, x in enumerate(pos):
        r = rng.random()
        if r < 0.3:
            out.append(("in", [c * scale for c in x]))
        elif r < 0.4 and k > 0 and out[0][0] == "in":
            # the S point coincides with the first point of the case
            out.append(s_at(rng, [c / scale for c in out[0][1]], direction(), scale))
        else:
            m = s_at(rng, x, direction(), scale)
            if rng.random() < 0.15:
                m = (m[0], m[1], m[2], random_t(rng))  # anywhere on the segment
            out.append(m)
    return out


def batch(rng, n_random, n_adversarial, size, kind):
    b = Batch()
    for _ in range(n_random):
        scale = 2.0 ** rng.randint(-80, 80)
        b.case([random_member(rng, scale) for _ in range(size)])
    for _ in range(n_adversarial):
        b.case(adversarial_members(rng, size, kind))
    return b


def ref_orient3d(q):
    a, b, c, d = q
    return sign(det([sub(b, a), sub(c, a), sub(d, a)]))


def ref_insphere(q):
    rows = [sub(q[i], q[4]) + [dot(sub(q[i], q[4]), sub(q[i], q[4]))] for i in range(4)]
    return -sign(det(rows))


def perturbed(rows_xyz, lifted, ids, sign_of):
    """sign_of(det[x, lifted + delta^(rank + 1), 1]) for a delta small enough to order the
    powers (the lifted column enters linearly)."""
    n = len(rows_xyz)
    rank = [sum(ids[j] > ids[i] for j in range(n)) for i in range(n)]
    cof = [abs(det([x + [Fraction(1)] for j, x in enumerate(rows_xyz) if j != i])) for i in range(n)]
    delta = min(c for c in cof if c) / (2 * sum(cof) + 1)
    s = det([x + [lifted[i] + delta ** (rank[i] + 1), Fraction(1)] for i, x in enumerate(rows_xyz)])
    assert s
    return sign_of(s)


def ref_insphere_sos(q, ids):
    s0 = det([x + [dot(x, x), Fraction(1)] for x in q])
    if s0:
        return -sign(s0)
    return perturbed(q, [dot(x, x) for x in q], ids, lambda s: -sign(s))


def ref_orient2d(axis, q):
    return sign(cross(sub(q[1], q[0]), sub(q[2], q[0]))[axis])


def ref_incircle_plane(axis, q):
    i, j = kept(axis)
    return sign(det([[x[i], x[j], dot(x, x), Fraction(1)] for x in q]))


def ref_incircle_plane_sos(axis, q, ids):
    s0 = ref_incircle_plane(axis, q)
    if s0:
        return s0
    i, j = kept(axis)
    return perturbed([[x[i], x[j]] for x in q], [dot(x, x) for x in q], ids, sign)


def distinct(q):
    return all(q[i] != q[j] for i in range(len(q)) for j in range(i + 1, len(q)))


@pytest.mark.parametrize("kind,size,shape", [("orient3d", 4, "orient"), ("insphere", 5, "sphere"),
                                              ("insphere_sos", 5, "sphere")])
def test_3d_predicates_on_mixed_points_match_fractions(kind, size, shape):
    rng = random.Random(f"mixed-{kind}")
    b = batch(rng, N_RANDOM, N_ADVERSARIAL, size, shape)
    signs, counts = b.run(kind)
    zeros = checked = 0
    for g, s in zip(b.groups, signs.tolist()):
        q = b.exact(g)
        if kind == "orient3d":
            want = ref_orient3d(q)
        elif kind == "insphere":
            want = ref_insphere(q)
        else:
            if not (distinct(q) and ref_orient3d(q[:4])):
                continue  # the perturbation is defined for distinct points
            want = ref_insphere_sos(q, b.ids(g))
            assert s != 0
        assert s == want, (kind, q, b.ids(g))
        zeros += want == 0 or (kind == "insphere_sos" and ref_insphere(q) == 0)
        checked += 1
    # the adversarial half reaches exact ties and the exact path
    assert zeros > N_ADVERSARIAL // 20, zeros
    assert counts["exact"] > N_ADVERSARIAL // 20, counts
    assert checked > N_ADVERSARIAL


@pytest.mark.parametrize("kind", ["orient2d_proj", "incircle_plane", "incircle_plane_sos"])
def test_in_plane_predicates_on_mixed_points_match_fractions(kind):
    rng = random.Random(f"mixed-{kind}")
    size = 3 if kind == "orient2d_proj" else 4
    b = batch(rng, N_RANDOM, N_ADVERSARIAL, size, "circle")
    zeros = checked = 0
    for axis in range(3):
        signs, _ = b.run(kind, axis)
        for g, s in zip(b.groups, signs.tolist()):
            q = b.exact(g)
            if kind == "orient2d_proj":
                want = ref_orient2d(axis, q)
            elif kind == "incircle_plane":
                if ref_orient2d(axis, q[:3]) == 0:
                    continue
                want = ref_incircle_plane(axis, q)
            else:
                coplanar = ref_orient3d(q) == 0
                if not (coplanar and distinct(q) and ref_orient2d(axis, q[:3])):
                    continue  # the in-plane meaning holds for coplanar points
                want = ref_incircle_plane_sos(axis, q, b.ids(g))
                assert s != 0
                zeros += ref_incircle_plane(axis, q) == 0
            assert s == want, (kind, axis, q, b.ids(g))
            zeros += want == 0
            checked += 1
    assert zeros > N_ADVERSARIAL // 20, zeros
    # the perturbed test needs exactly coplanar, distinct points: most adversarial cases
    assert checked > (N_ADVERSARIAL // 2 if kind == "incircle_plane_sos" else N_ADVERSARIAL), checked


def test_s_point_output_coordinates_are_the_nearest_doubles():
    rng = random.Random("mixed-coords")
    b = Batch()
    for _ in range(3000):
        scale = 2.0 ** rng.randint(-100, 100)
        b.case([random_member(rng, scale) if rng.random() < 0.5 else
                s_at(rng, list(rng.choice(SPHERE)), [1, -2, 3], scale)])
    groups = [g[0] for g in b.groups if g[0][0] == "s"]
    out = spoint_coords(np.array(b.points), np.array(b.seg, dtype=np.int64), np.array(b.t))
    assert out.shape == (len(b.t), 3)
    for k, i in groups:
        exact = b.exact([(k, i)])[0]
        # Fraction to float is correctly rounded (ties to even)
        assert out[i].tolist() == [float(x) for x in exact]


def test_bad_s_points_and_queries_are_refused():
    pts = np.array([[0.0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]])
    ok = mixed_predicate_signs("orient3d", pts, [[0, 1]], [0.5], [[0, 2, 3, 4]])[0]
    assert ok.tolist() == [1]  # det[(0, 1, 0), (0, 0, 1), (1/2, 0, 0)] = 1/2
    for seg, t in [([[0, 0]], [0.5]), ([[0, 9]], [0.5]), ([[0, 1]], [0.0]), ([[0, 1]], [1.0]),
                   ([[0, 1]], [float("nan")])]:
        with pytest.raises(ValueError):
            mixed_predicate_signs("orient3d", pts, seg, t, [[0, 1, 2, 4]])
    with pytest.raises(ValueError, match="refers to no point"):
        mixed_predicate_signs("orient3d", pts, [[0, 1]], [0.5], [[0, 1, 2, 5]])
    with pytest.raises(ValueError, match="unknown"):
        mixed_predicate_signs("incircle3d", pts, [[0, 1]], [0.5], [[0, 1, 2, 4]])
