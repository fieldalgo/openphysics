# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Repair of what rounding to doubles makes flat or inverted, in ``mesh_plc``.

Seeded inputs that make rounding invert tetrahedra: a prism (an n-gon, n = 3 to 9)
under a rational rotation, its quadrilateral sides split into two triangles that are
almost coplanar, with 5 to 60 free points within 1e-15 to 1e-13 of a facet (mostly
inside). Points on segments and facets are rounded once; tetrahedra near such a facet
come out flat or inverted. The rotation and the polygon use only rational arithmetic in
doubles in a fixed order (no cos or sin, no BLAS), so the inputs are the same bits on
every platform, and so are the outcomes (the kernel is exact and deterministic).

Every result must be either a mesh that passes V1-V4 (``test_adversarial.check``,
exact volume included; V3(a) from the faces tagged to each facet, as the input is one
shell) or a ``RoundingError``; no other outcome. Most cases must mesh,
and the repair must be exercised (flips, facet flips and cavity fills).
"""

from fractions import Fraction
import math
import random

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

try:  # the checker of V1-V4; the installed-wheel check copies it under another name
    import test_adversarial as A  # noqa: E402
except ImportError:
    import test_meshloom_adversarial as A  # noqa: E402

CASES = 60
# Measured on 2026-11-11 (inputs SHA-256 over the 400 seeds' points 424cb260...): the
# first 60 seeds give 42 valid meshes and 18 RoundingError (main before this repair: 18
# meshes, 42 RoundingError). Of 400 seeds, 285 valid, 114 RoundingError and one mesh over
# the V3(a) area bound (seed 227: 1.2e-12 relative on a facet of area 8e-7, from rounding
# points on that facet); the bound is not lowered.
MIN_MESHED = 42


def rotation(rng):
    """A rotation matrix from a random integer quaternion (rational entries)."""
    while True:
        a, b, c, d = (rng.randint(-9, 9) for _ in range(4))
        n = a * a + b * b + c * c + d * d
        if n:
            break
    return [[(a * a + b * b - c * c - d * d) / n, 2 * (b * c - a * d) / n, 2 * (b * d + a * c) / n],
            [2 * (b * c + a * d) / n, (a * a - b * b + c * c - d * d) / n, 2 * (c * d - a * b) / n],
            [2 * (b * d - a * c) / n, 2 * (c * d + a * b) / n, (a * a - b * b - c * c + d * d) / n]]


def apply(R, p):
    """R p in plain double arithmetic, in a fixed order (no BLAS: the same bits everywhere)."""
    return [R[i][0] * p[0] + R[i][1] * p[1] + R[i][2] * p[2] for i in range(3)]


def case(seed):
    rng = random.Random(seed)
    n = rng.randint(3, 9)
    R = rotation(rng)
    # n points on the unit circle at rational parameters: ((1 - s^2) / (1 + s^2), 2 s / (1 + s^2))
    ts = sorted({Fraction(rng.randint(-40, 40), 8) for _ in range(4 * n)})[:n]
    if len(ts) < 3:
        ts = [Fraction(-1), Fraction(0), Fraction(1)]
    ring = [(float((1 - s * s) / (1 + s * s)), float(2 * s / (1 + s * s))) for s in ts]
    ring.sort(key=lambda p: math.atan2(p[1], p[0]))  # the order only; the angles are far apart
    n = len(ring)
    h = rng.uniform(0.3, 2.0)
    P = [apply(R, [x, y, 0.0]) for x, y in ring] + [apply(R, [x, y, h]) for x, y in ring]
    quads = [list(range(n - 1, -1, -1)), list(range(n, 2 * n))] + [[k, (k + 1) % n, (k + 1) % n + n, k + n]
                                                                     for k in range(n)]
    tris = [[f[0], f[k], f[k + 1]] for f in quads for k in range(1, len(f) - 1)]
    pts = list(P)
    for _ in range(rng.randint(5, 60)):  # free points a few ulps from a facet
        a, b, c = (pts[i] for i in rng.choice(tris))
        u, v = rng.random(), rng.random()
        if u + v > 1:
            u, v = 1 - u, 1 - v
        e, g = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        nrm = [e[1] * g[2] - e[2] * g[1], e[2] * g[0] - e[0] * g[2], e[0] * g[1] - e[1] * g[0]]
        ln = math.sqrt(nrm[0] * nrm[0] + nrm[1] * nrm[1] + nrm[2] * nrm[2])
        off = rng.uniform(1e-15, 1e-13) * rng.choice([1, 1, 1, -1]) / ln
        pts.append([a[i] + u * e[i] + v * g[i] - nrm[i] * off for i in range(3)])
    return np.array(pts), [[t] for t in tris]


def volume(points, facets):
    P = [[Fraction(x) for x in p] for p in points.tolist()]
    s = Fraction(0)
    for (t,) in facets:
        a, b, c = (P[i] for i in t)
        s += a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])
    return abs(float(s / 6))


def test_rounding_repair_keeps_every_mesh_valid():
    from meshloom._core import RoundingError, mesh_plc
    meshed, refused, used = 0, 0, {}
    for seed in range(CASES):
        pts, facets = case(seed)
        try:
            m = mesh_plc(pts, facets, domain="parity")
        except RoundingError:
            refused += 1
            continue
        A.check(m, pts, facets, [volume(pts, facets)], False, euler=True, inner_cover=False)
        src = m["node_source"]
        assert ((src >= 0) | (src == -1)).all() and (src == -1).sum() == m["stats"]["points_added"]
        meshed += 1
        for k in ("flips23", "flips32", "edge_removals", "facet_flips", "cavity_fills"):
            used[k] = used.get(k, 0) + m["stats"][k]
    assert meshed + refused == CASES
    assert meshed >= MIN_MESHED, (meshed, refused, used)
    assert used["facet_flips"] > 0 and used["edge_removals"] + used["flips23"] + used["flips32"] > 0, used
