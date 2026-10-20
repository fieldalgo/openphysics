# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""gmshio is never told what a length is.

A .geo script is written in whatever unit its author chose, and the same device is
0.22 in micrometres and 2.2e-13 in metres. Every geometric tolerance here is a
dimensionless fraction of a length the caller supplied.

Assertions are on invariants — the resolved topology, the boundary-name grouping,
the planarity verdict — and each comparison first asserts that its scale really
differs from the reference, failing as VACUOUS if it does not.

``Geo.box_sides`` is a deliberate twin of ``meshine.box_sides``: gmshio must not
import meshine, so the same bug lived in both copies and both are pinned, each in
its own package, because each publishes separately.
"""

import ast
import pathlib
import re

import numpy as np
import pytest

import gmshio
from gmshio import geo, to_fem2d
from gmshio.fem import PLANE_EPS
from gmshio.mesh import CellBlock, Mesh

PACKAGE = pathlib.Path(gmshio.__file__).resolve().parent

#: One geometry, five ways of writing it; the number is document units per micrometre.
SCALES = [("um", 1.0), ("nm", 1e3), ("mm", 1e-3), ("m", 1e-6), ("km", 1e-9)]

CORE_W, CORE_H = 0.5, 0.22        # a 500 x 220 nm strip, in micrometres


def _count(pattern, text):
    return len(re.findall(pattern, text))


def tiling(s: float) -> str:
    """Two regions meeting at a T-junction, written at ``s`` units per micrometre."""
    g = geo.Geo()
    g.add_region("a", [(0, 0), (1 * s, 0), (1 * s, 1 * s), (0, 1 * s)])
    g.add_region("b", [(1 * s, 0), (2 * s, 0), (2 * s, 0.5 * s), (1 * s, 0.5 * s)])
    return g.render()


# ---- the geometry is the same geometry at every scale ------------------------------

@pytest.mark.parametrize("label,s", SCALES[1:])
def test_the_same_tiling_resolves_to_the_same_topology_at_every_scale(label, s):
    """Point merging and T-junction splitting are the two places a length is compared,
    and the resolved topology is what both produce. It cannot depend on the unit."""
    assert s != 1.0, f"VACUOUS at {label}: the scale ratio is 1.0, so nothing was rescaled"
    ref, got = tiling(1.0), tiling(s)
    for pattern, expected in ((r"Point\(\d+\)", 7),        # (1,0) is shared by a and b
                              (r"Line\(\d+\)", 8),         # a's right edge splits in two
                              (r"Plane Surface", 2)):
        assert _count(pattern, got) == _count(pattern, ref) == expected, \
            f"{label}: {pattern} resolved to {_count(pattern, got)}, not {expected}"
    outer = re.search(r'Physical Curve\("outer"\) = \{([^}]*)\};', got)
    assert outer and len(outer.group(1).split(",")) == 7, f"{label}: outer boundary is wrong"


def test_box_sides_names_every_edge_at_every_scale():
    """Once the box is smaller than the tolerance every midpoint matches the first test
    and the whole boundary becomes one physical curve named "left"."""
    for label, s in SCALES:
        w, h = 0.5 * CORE_W * s, 0.5 * CORE_H * s
        namer = geo.box_sides(-w, w, -h, h)
        got = (namer((-w, 0.0)), namer((w, 0.0)), namer((0.0, -h)), namer((0.0, h)),
               namer((0.0, 0.0)))
        assert got == ("left", "right", "bottom", "top", "outer"), f"{label}: named {got}"


def test_the_merge_distance_is_a_length_and_the_parametric_bound_is_not():
    """A perpendicular distance scales with the input; a position along a segment,
    being a fraction of that segment's own length, must not."""
    measured = {}
    for label, s in SCALES:
        g = geo.Geo()
        g.add_region("a", [(0, 0), (1 * s, 0), (1 * s, 1 * s), (0, 1 * s)])
        g.render()
        measured[label] = (g.extent(), g.point_tol, g.param_eps)

    ref_extent, ref_tol, ref_param = measured["um"]
    assert ref_extent == pytest.approx(np.hypot(1.0, 1.0))
    for label, s in SCALES[1:]:
        assert s != 1.0, f"VACUOUS at {label}: the scale ratio is 1.0"
        extent, point_tol, param_eps = measured[label]
        assert extent == pytest.approx(ref_extent * s), f"{label}: the extent is not the input's"
        assert point_tol == pytest.approx(ref_tol * s), \
            f"{label}: the merge distance did not scale, so it is not a length"
        assert param_eps == ref_param, \
            f"{label}: a normalised position scaled with the unit, so it is not dimensionless"
        assert point_tol / extent == pytest.approx(geo.MERGE_EPS)


# ---- planarity is a ratio, not a distance ------------------------------------------

def square_mesh(s: float, z: float) -> Mesh:
    """Two triangles tiling a square of side ``s``, lifted off the z=0 plane by ``z``."""
    points = np.array([[0.0, 0.0, 0.0], [s, 0.0, 0.0], [s, s, z], [0.0, s, 0.0]])
    return Mesh(
        points=points,
        point_tags=np.arange(1, 5),
        blocks=[CellBlock(2, "triangle", 1, np.array([[0, 1, 2], [0, 2, 3]]), np.array([1, 2])),
                CellBlock(1, "line", 2, np.array([[0, 1]]), np.array([3]))],
        physical_names={(2, 1): "mat", (1, 2): "edge"},
        entity_physical={(2, 1): (1,), (1, 2): (2,)},
    )


@pytest.mark.parametrize("label,s", SCALES)
def test_planarity_is_judged_against_the_mesh_own_extent(label, s):
    """``plane_tol * max(1.0, ...)`` collapses to a flat 1e-9 for any mesh smaller than
    one unit, so a 220 nm device written in metres was judged against a tolerance four
    orders of magnitude wider than the device and nothing could ever be non-planar."""
    threshold = PLANE_EPS * np.hypot(s, s)              # a fraction of the mesh's own extent
    to_fem2d(square_mesh(s, 0.25 * threshold))          # comfortably planar, at every scale
    with pytest.raises(ValueError, match="not planar"):
        to_fem2d(square_mesh(s, 4.0 * threshold))       # comfortably not, at every scale


def test_a_mesh_with_no_extent_in_the_plane_is_refused():
    """Every tolerance here is a fraction of the extent, so a zero extent has to be
    caught before one of them is computed."""
    with pytest.raises(ValueError, match="no extent in the xy plane"):
        to_fem2d(square_mesh(0.0, 1.0))


# ---- nothing empty, and no length in disguise --------------------------------------

def test_a_zero_length_edge_names_the_region_and_the_distance_that_made_it_one():
    g = geo.Geo()
    g.add_region("film", [(0, 0), (1, 0), (1, 1e-18), (0, 1e-18)])   # under the merge distance
    with pytest.raises(ValueError, match="zero-length edge") as e:
        g.render()
    for expected in ("film", "merge distance", "bounding-box diagonal"):
        assert expected in str(e.value), f"the message does not mention {expected!r}"


def test_a_geometry_without_extent_is_refused_before_any_tolerance_is_used():
    g = geo.Geo()
    g.add_region("a", [(1.0, 1.0), (1.0, 1.0), (1.0, 1.0)])
    with pytest.raises(ValueError, match="no extent"):
        g.render()


def test_no_module_hides_a_length_inside_max_of_one():
    """``max(1.0, <a length or an area>)`` returns 1.0 for every input below unit scale,
    which turns a relative tolerance into an absolute one exactly where it matters.

    Only a bare ``max`` is scanned: ``np.maximum(x, 1)`` is legitimate where x is a count.
    """
    offenders = []
    assert len(list(PACKAGE.glob("*.py"))) > 1, f"no package modules found in {PACKAGE}"
    for path in sorted(PACKAGE.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "max" and len(node.args) == 2
                    and any(isinstance(a, ast.Constant) and a.value == 1 for a in node.args)):
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, f"max(1, ...) hides an absolute length in {offenders}"
