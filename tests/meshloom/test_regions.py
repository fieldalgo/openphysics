# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Region points of ``mesh_plc`` (regions mode): names, holes and refusals.

Boxes with dyadic corners, so every volume is exact. Each mesh is checked against V1-V4
(``test_adversarial.check``) with the expected region volumes, in the order of the
names; refusals must be ``RegionError`` (a ``ValueError``) and name the problem.
"""

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from meshloom._core import RegionError, mesh_plc  # noqa: E402

try:  # the checker of V1-V4; the installed-wheel check copies it under another name
    import test_adversarial as A  # noqa: E402
except ImportError:
    import test_meshloom_adversarial as A  # noqa: E402


def boxes(*spec):
    """Points and facets of axis-aligned boxes ((lo, hi), ...), sharing equal corners."""
    points, index, facets = [], {}, []

    def p(q):
        if q not in index:
            index[q] = len(points)
            points.append(q)
        return index[q]

    for (x0, y0, z0), (x1, y1, z1) in spec:
        for lp in ([(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)],
                   [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
                   [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
                   [(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)],
                   [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],
                   [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)]):
            facets.append([[p(tuple(float(c) for c in q)) for q in lp]])
    return np.array(points), facets


OUTER = ((0, 0, 0), (4, 4, 4))
INNER = ((1, 1, 1), (2, 2, 3))
NESTED = boxes(OUTER, INNER)


def vol(lohi):
    (x0, y0, z0), (x1, y1, z1) = lohi
    return float((x1 - x0) * (y1 - y0) * (z1 - z0))


def region_volumes(m):
    q = m["nodes"][m["tetrahedra"]]
    v = np.einsum("ij,ij->i", q[:, 1] - q[:, 0], np.cross(q[:, 2] - q[:, 0], q[:, 3] - q[:, 0])) / 6
    return [float(v[m["regions"] == r].sum()) for r in range(len(m["region_names"]))]


def test_names_follow_the_order_of_region_points():
    pts, facets = NESTED
    m = mesh_plc(pts, facets, region_points=[((3.5, 3.5, 3.5), "shell"), ((1.5, 1.5, 2), "core")])
    assert m["region_names"] == ["shell", "core"]
    A.check(m, pts, facets, [vol(OUTER) - vol(INNER), vol(INNER)], True, euler=False)  # the shell has a cavity
    assert region_volumes(m) == pytest.approx([vol(OUTER) - vol(INNER), vol(INNER)], rel=1e-14)
    assert set(m["interfaces"]) == {(0, 1)}  # between shell (0) and core (1)


def test_a_hole_is_not_meshed():
    pts, facets = NESTED
    m = mesh_plc(pts, facets, region_points=[((3, 3, 3), "shell"), ((1.5, 1.5, 2), None)])
    assert m["region_names"] == ["shell"]
    A.check(m, pts, facets, [vol(OUTER) - vol(INNER)], True, euler=False)  # a ball with a cavity
    assert not m["interfaces"]
    assert set(m["boundary_faces"]) == set(range(12))  # the hole's six facets are boundary too


def test_components_share_a_name_and_a_seed_may_sit_on_a_mesh_vertex():
    left, right = ((0, 0, 0), (1, 1, 1)), ((2, 0, 0), (3, 1, 1))
    pts, facets = boxes(left, right)
    pts = np.vstack([pts, [[0.5, 0.5, 0.5]]])  # a free point, then used as a seed
    m = mesh_plc(pts, facets, region_points=[((0.5, 0.5, 0.5), "metal"), ((2.5, 0.5, 0.5), "metal")])
    assert m["region_names"] == ["metal"]
    A.check(m, pts, facets, [vol(left) + vol(right)], True, euler=False)


@pytest.mark.parametrize("region_points, words", [
    ([((9, 9, 9), "a"), ((1.5, 1.5, 2), "b")], "convex hull"),
    ([((3, 3, 3), "a")], "has no seed"),
    ([((3, 3, 3), "a"), ((1.5, 1.5, 2), "b"), ((3.5, 0.5, 0.5), "c")], "name two regions"),
    ([((3, 3, 3), "a"), ((1.5, 1.5, 2), None), ((1.2, 1.2, 1.2), "b")], "name two regions"),
    ([((3, 3, 3), "a"), ((1.5, 1.5, 1), "b")], "on a facet"),  # on the inner box's bottom
    ([((3, 3, 3), "a"), ((2, 2, 2), "b")], "on a facet"),  # on an inner box edge
])
def test_refusals_name_the_problem(region_points, words):
    pts, facets = NESTED
    with pytest.raises(RegionError, match=words):
        mesh_plc(pts, facets, region_points=region_points)


def test_a_seed_between_closed_regions_is_outside_them():
    pts, facets = boxes(((0, 0, 0), (1, 1, 1)), ((2, 0, 0), (3, 1, 1)))
    with pytest.raises(RegionError, match="outside every closed region"):
        mesh_plc(pts, facets, region_points=[((0.5, 0.5, 0.5), "a"), ((2.5, 0.5, 0.5), "b"),
                                             ((1.5, 0.5, 0.5), "gap")])


@pytest.mark.parametrize("kwargs", [
    {"region_points": [((1, 1, 1), "a")], "domain": "parity"},
    {"region_points": []},
    {"region_points": [((1, 1), "a")]},
    {"region_points": [((1, 1, float("nan")), "a")]},
    {"region_points": [((1, 1, 1), 3)]},
    {"region_points": [(1, 1, 1)]},
])
def test_malformed_region_points(kwargs):
    pts, facets = NESTED
    with pytest.raises(ValueError):
        mesh_plc(pts, facets, **kwargs)
