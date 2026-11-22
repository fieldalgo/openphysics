# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Shared cases and measures of the meshloom quality tests (``test_quality_*.py``).

Not a test module. The quality gates are split over several files so that the CI shards,
which take whole files, can spread them; each file imports what it needs from here after
its own check that meshloom's kernel is built.
"""

import meshloom
import numpy as np
from meshloom import builder

try:  # the box assembly of the refinement tests; the installed-wheel check renames it
    from test_refine import C3_SEEDS, c2, c3, grid_plc
except ImportError:
    from test_meshloom_refine import C3_SEEDS, c2, c3, grid_plc


def c6():
    """Fichera corner: [-1,1]^3 minus [0,1]^3."""
    g = [-1.0, 0.0, 1.0]
    cells = {(i, j, k): "a" for i in range(2) for j in range(2) for k in range(2) if (i, j, k) != (1, 1, 1)}
    return grid_plc(g, g, g, cells)


def generate(case, h):
    if case == "C2":
        (pts, facets), _ = c2()
        return meshloom.generate3d(pts, facets, h=h)
    if case == "C3":
        (pts, facets), _ = c3()
        return meshloom.generate3d(pts, facets, h=h, region_points=C3_SEEDS)
    if case == "C4":
        return meshloom.generate3d(h=h, **builder.via_in_slab(h))
    if case == "C5":
        return meshloom.generate3d(h=h, **builder.sphere_in_box(h))
    if case == "C1":
        return meshloom.generate3d(h=h, **builder.sphere(h))
    pts, facets = c6()
    return meshloom.generate3d(pts, facets, h=h)


def dihedral_and_q(m):
    """Smallest dihedral angle (degrees) and q = 3 inradius / circumradius per tetrahedron."""
    x = m["nodes"][m["tetrahedra"]]
    a, b, c = x[:, 1] - x[:, 0], x[:, 2] - x[:, 0], x[:, 3] - x[:, 0]
    v6 = np.abs(np.einsum("ij,ij->i", a, np.cross(b, c)))
    area = sum(0.5 * np.linalg.norm(np.cross(x[:, j] - x[:, i], x[:, k] - x[:, i]), axis=1)
               for i, j, k in ((1, 2, 3), (0, 2, 3), (0, 1, 3), (0, 1, 2)))
    rin = 0.5 * v6 / area
    num = (np.einsum("ij,ij->i", a, a)[:, None] * np.cross(b, c) + np.einsum("ij,ij->i", b, b)[:, None] * np.cross(c, a)
           + np.einsum("ij,ij->i", c, c)[:, None] * np.cross(a, b))
    rc = np.linalg.norm(num, axis=1) / (2 * v6)
    angles = []
    for i, j, k, l in ((0, 1, 2, 3), (0, 2, 1, 3), (0, 3, 1, 2), (1, 2, 0, 3), (1, 3, 0, 2), (2, 3, 0, 1)):
        e = x[:, j] - x[:, i]
        n1, n2 = np.cross(e, x[:, k] - x[:, i]), np.cross(e, x[:, l] - x[:, i])
        cos = np.einsum("ij,ij->i", n1, n2) / np.linalg.norm(n1, axis=1) / np.linalg.norm(n2, axis=1)
        angles.append(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))
    return np.min(angles, axis=0), 3 * rin / rc


def edges(m):
    t = m["tetrahedra"]
    e = np.unique(np.sort(np.concatenate([t[:, [i, j]] for i in range(4) for j in range(i + 1, 4)]), axis=1), axis=0)
    return e, np.linalg.norm(m["nodes"][e[:, 0]] - m["nodes"][e[:, 1]], axis=1)
