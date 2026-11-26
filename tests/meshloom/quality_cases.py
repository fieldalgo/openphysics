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
    from test_refine import C3_SEEDS, c2, c3, c9, grid_plc
except ImportError:
    from test_meshloom_refine import C3_SEEDS, c2, c3, c9, grid_plc


def c6():
    """Fichera corner: [-1,1]^3 minus [0,1]^3."""
    g = [-1.0, 0.0, 1.0]
    cells = {(i, j, k): "a" for i in range(2) for j in range(2) for k in range(2) if (i, j, k) != (1, 1, 1)}
    return grid_plc(g, g, g, cells)


def c7():
    """C7: the prism of length 1 over the isosceles triangle with legs 1 and a 15 degree
    apex at the origin, along z."""
    a = np.radians(15.0)
    tri = [(0.0, 0.0), (1.0, 0.0), (float(np.cos(a)), float(np.sin(a)))]
    pts = np.array([(x, y, z) for z in (0.0, 1.0) for x, y in tri])
    facets = [[[0, 2, 1]], [[3, 4, 5]], [[0, 1, 4, 3]], [[1, 2, 5, 4]], [[2, 0, 3, 5]]]
    return pts, facets


#: C8: [0,1]^2 with three layers 0.02 thick (aspect ratio 1:50), three regions; the size of
#: this thin-layer stack is fixed in the plan 5 criteria, as validation3d.md gives only the ratio
C8_LAYERS = [0.0, 0.02, 0.04, 0.06]


def c8():
    cells = {(0, 0, k): f"layer {k}" for k in range(3)}
    return grid_plc([0.0, 1.0], [0.0, 1.0], C8_LAYERS, cells), [0.02, 0.02, 0.02]


C8_SEEDS = [((0.5, 0.5, 0.01 + 0.02 * k), f"layer {k}") for k in range(3)]


def case_kwargs(case, h):
    """The arguments of ``meshloom.generate3d`` for case C1-C9 at size h."""
    if case == "C1":
        return dict(h=h, **builder.sphere(h))
    if case == "C4":
        return dict(h=h, **builder.via_in_slab(h))
    if case == "C5":
        return dict(h=h, **builder.sphere_in_box(h))
    if case in ("C2", "C3", "C8", "C9"):
        (pts, facets), _ = {"C2": c2, "C3": c3, "C8": c8, "C9": c9}[case]()
        kw = dict(points=pts, facets=facets, h=h)
        if case == "C3":
            kw["region_points"] = C3_SEEDS
        if case == "C8":
            kw["region_points"] = C8_SEEDS
        return kw
    pts, facets = {"C6": c6, "C7": c7}[case]()
    return dict(points=pts, facets=facets, h=h)


def generate(case, h):
    return meshloom.generate3d(**case_kwargs(case, h))


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
