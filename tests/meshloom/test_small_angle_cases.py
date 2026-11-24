# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The synthetic small-angle surfaces of ``small_angle_cases.py`` are what they claim.

Each case is a closed surface whose triangles are wound outward (every directed edge used
once, in one direction), encloses the volume of its body, and carries its feature at the
stated strength. No meshing here: these checks hold the inputs fixed before the
small-angle work measures anything on them.
"""

import math

import numpy as np
import pytest

from small_angle_cases import CASES, surface


def signed_volume(pts, tri):
    x = pts[tri]
    return np.einsum("ij,ij->i", x[:, 0], np.cross(x[:, 1], x[:, 2])).sum() / 6


def angle(u, v):
    return math.degrees(math.atan2(np.linalg.norm(np.cross(u, v)), np.dot(u, v)))


def volume_of(family, s):
    if family == "fold":
        return 1.0 + math.tan(math.radians(s)) / math.sqrt(2.0) / 6
    if family == "wedge":
        return 0.5 * math.sin(math.radians(s))
    return 1.0


@pytest.mark.parametrize("name, family, s", CASES)
def test_closed_outward_and_exact_volume(name, family, s):
    pts, tri = surface(family, s)
    directed = [(int(t[i]), int(t[(i + 1) % 3])) for t in tri for i in range(3)]
    assert len(set(directed)) == len(directed)
    assert all((b, a) in set(directed) for a, b in directed)
    assert len(np.unique(tri)) == len(pts)
    assert signed_volume(pts, tri) == pytest.approx(volume_of(family, s), rel=1e-12)


@pytest.mark.parametrize("name, family, s", CASES)
def test_feature_strength(name, family, s):
    pts, tri = surface(family, s)
    if family == "fan":
        o, c, q = pts[8], pts[5], pts[9]
        assert angle(c - o, q - o) == pytest.approx(s, rel=1e-6)
    elif family == "needle":
        a, b, c = pts[8], pts[9], pts[10]
        assert angle(b - a, c - a) == pytest.approx(s, rel=1e-6)
    elif family == "fold":
        n1 = np.cross(pts[5] - pts[4], pts[7] - pts[4])
        n2 = np.cross(pts[7] - pts[4], pts[6] - pts[4])
        assert 180.0 - angle(n1, n2) == pytest.approx(180.0 - s, rel=1e-9)
        assert angle(n1, n2) > 0.0
    elif family == "close":
        p, a, b = pts[8], pts[4], pts[5]
        dist = np.linalg.norm(np.cross(b - a, p - a)) / np.linalg.norm(b - a)
        assert dist / math.sqrt(3.0) == pytest.approx(s, rel=1e-9)
    else:
        bottom, slant = pts[1] - pts[0], pts[2] - pts[0]
        assert angle(bottom, slant) == pytest.approx(s, rel=1e-9)
