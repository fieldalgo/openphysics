# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Cross-language set of V16 (pre-registered 3D plan): the kernel's exact predicates
agree in sign with determinants evaluated in Python ``Fraction`` arithmetic on
random and adversarial inputs (near-coplanar, coplanar, cospherical, cocircular,
1-ulp perturbations, power-of-two scales over 2^-80..2^80). The perturbed insphere
is checked against the 5 x 5 lifted determinant with an explicit small perturbation.

The main V16 run (10^4 random + 10^4 adversarial cases per predicate against big
integers) is the Rust test ``exact_ref::v16_predicates_agree_with_exact_integers``,
run by ``cargo test`` in CI.
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

from meshloom._core import predicate_signs  # noqa: E402

N_RANDOM = 2000
N_ADVERSARIAL = 2000


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


def frac(points):
    return [[Fraction(x) for x in p] for p in points]


def ref_orient3d(p):
    a, b, c, d = frac(p)
    return sign(det([sub(b, a), sub(c, a), sub(d, a)]))


def ref_insphere(p):
    q = frac(p)
    rows = [sub(q[i], q[4]) + [dot(sub(q[i], q[4]), sub(q[i], q[4]))] for i in range(4)]
    return -sign(det(rows))


def ref_insphere_sos(p, ids):
    q = frac(p)
    s0 = det([x + [dot(x, x), Fraction(1)] for x in q])
    if s0:
        return -sign(s0)
    # explicit perturbation delta^(rank + 1), rank 0 for the largest id; the lifted
    # column enters linearly, so a delta below (smallest nonzero cofactor) / (2 * sum of
    # all cofactors) orders the terms by power
    rank = [sum(ids[j] > ids[i] for j in range(5)) for i in range(5)]
    cof = [abs(det([x + [Fraction(1)] for j, x in enumerate(q) if j != i])) for i in range(5)]
    delta = min(c for c in cof if c) / (2 * sum(cof) + 1)
    s = det([x + [dot(x, x) + delta ** (rank[i] + 1), Fraction(1)] for i, x in enumerate(q)])
    assert s
    return -sign(s)


def ref_incircle3d(p):
    a, b, c, d = frac(p)
    u, v, w = sub(b, a), sub(c, a), sub(d, a)
    n = cross(u, v)
    return -sign(dot(u, u) * dot(cross(v, w), n) - dot(v, v) * dot(cross(u, w), n) + dot(w, w) * dot(n, n))


def nudge(x, k):
    """x moved by |k| ulps (k = -2..2); zero stays zero, as a subnormal is outside the domain."""
    for _ in range(abs(k)):
        if x == 0:
            break
        x = math.nextafter(x, math.copysign(math.inf, k))
    return x


def scale_of(rng):
    return 2.0 ** rng.randint(-80, 80)


def point(rng):
    return [rng.uniform(-1, 1) for _ in range(3)]


SPHERE = sorted({p for p in itertools.product(range(-21, 22), repeat=3) if p[0] ** 2 + p[1] ** 2 + p[2] ** 2 == 441})


def orient_cases(rng, n, adversarial):
    out = []
    for _ in range(n):
        if not adversarial:
            out.append([point(rng) for _ in range(4)])
            continue
        s = scale_of(rng)
        kind = rng.randrange(3)
        if kind == 0:
            a, b, c = point(rng), point(rng), point(rng)
            u, v = rng.random(), rng.random()
            d = [nudge(a[k] + u * (b[k] - a[k]) + v * (c[k] - a[k]), rng.randint(-2, 2)) for k in range(3)]
            pts = [a, b, c, d]
        elif kind == 1:
            pts = []
            for _ in range(4):
                x, y = rng.randrange(64) / 8, rng.randrange(64) / 8
                pts.append([x, y, x + 2 * y])
        else:
            o = [1.0e3, -2.0e3, 0.5e3]
            pts = [o, [nudge(o[0], 1), o[1], o[2]], [o[0], nudge(o[1], 1), o[2]],
                   [o[0], o[1], nudge(o[2], rng.randint(-1, 1))]]
        out.append([[x * s for x in p] for p in pts])
    return out


def insphere_cases(rng, n, adversarial):
    out = []
    for _ in range(n):
        if not adversarial:
            out.append([point(rng) for _ in range(5)])
            continue
        s = scale_of(rng)
        kind = rng.randrange(3)
        if kind == 2:
            pts = [[float(rng.randrange(2)), rng.randrange(2) * 0.5, rng.randrange(2) * 0.25] for _ in range(5)]
        else:
            pts = [list(map(float, rng.choice(SPHERE))) for _ in range(5)]
            if kind == 1:
                k, c = rng.randrange(5), rng.randrange(3)
                pts[k][c] = nudge(pts[k][c], rng.choice((-1, 1)))
        out.append([[x * s for x in p] for p in pts])
    return out


CIRCLE = [(5, 0), (-5, 0), (0, 5), (0, -5), (3, 4), (-3, 4), (3, -4), (-3, -4), (4, 3), (-4, 3), (4, -3), (-4, -3)]


def incircle_cases(rng, n, adversarial):
    out = []
    for _ in range(n):
        o = [float(rng.randrange(16)) for _ in range(3)]

        def embed(x, y):  # conformal: e1 = (1, 2, 2), e2 = (2, 1, -2)
            return [o[0] + x + 2 * y, o[1] + 2 * x + y, o[2] + 2 * x - 2 * y]

        s = scale_of(rng)
        if not adversarial:
            pts = [embed(rng.randrange(1 << 20) / 1024, rng.randrange(1 << 20) / 1024) for _ in range(4)]
        else:
            pts = [embed(*rng.choice(CIRCLE)) for _ in range(4)]
            if rng.random() < 0.5:
                k, c = rng.randrange(4), rng.randrange(3)
                pts[k][c] = nudge(pts[k][c], 1)
        out.append([[x * s for x in p] for p in pts])
    return out


@pytest.mark.parametrize("adversarial", [False, True], ids=["random", "adversarial"])
def test_orient3d_matches_fractions(adversarial):
    rng = random.Random(1601 + adversarial)
    cases = orient_cases(rng, N_ADVERSARIAL if adversarial else N_RANDOM, adversarial)
    got = predicate_signs("orient3d", np.array(cases))
    want = [ref_orient3d(c) for c in cases]
    assert got.tolist() == want
    if adversarial:
        assert want.count(0) > len(cases) // 10


@pytest.mark.parametrize("adversarial", [False, True], ids=["random", "adversarial"])
def test_insphere_matches_fractions(adversarial):
    rng = random.Random(1611 + adversarial)
    cases = insphere_cases(rng, N_ADVERSARIAL if adversarial else N_RANDOM, adversarial)
    got = predicate_signs("insphere", np.array(cases))
    want = [ref_insphere(c) for c in cases]
    assert got.tolist() == want
    if adversarial:
        assert want.count(0) > len(cases) // 10


def test_perturbed_insphere_matches_an_explicit_perturbation():
    rng = random.Random(1621)
    cases, ids = [], []
    for c in insphere_cases(rng, 3 * N_ADVERSARIAL, True) + insphere_cases(rng, N_RANDOM // 4, False):
        if len({tuple(p) for p in c}) == 5 and ref_orient3d(c[:4]) != 0:
            cases.append(c)
            ids.append(rng.sample(range(1000), 5))
    assert len(cases) > N_ADVERSARIAL
    got = predicate_signs("insphere_sos", np.array(cases), np.array(ids))
    assert 0 not in got.tolist()
    assert got.tolist() == [ref_insphere_sos(c, i) for c, i in zip(cases, ids)]
    degenerate = sum(ref_insphere(c) == 0 for c in cases)
    assert degenerate > len(cases) // 5


@pytest.mark.parametrize("adversarial", [False, True], ids=["random", "adversarial"])
def test_incircle3d_matches_fractions(adversarial):
    rng = random.Random(1631 + adversarial)
    cases = incircle_cases(rng, N_ADVERSARIAL if adversarial else N_RANDOM, adversarial)
    got = predicate_signs("incircle3d", np.array(cases))
    want = [ref_incircle3d(c) for c in cases]
    assert got.tolist() == want
    if adversarial:
        assert want.count(0) > len(cases) // 10


def test_coordinates_outside_the_exact_domain_are_refused():
    tiny = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1e-40]]
    with pytest.raises(ValueError, match="2\\^-120"):
        predicate_signs("orient3d", np.array([tiny]))
    with pytest.raises(ValueError):
        predicate_signs("orient3d", np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, np.nan]]]))
