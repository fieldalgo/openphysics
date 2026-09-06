# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""meshine is never told what a length is.

The same device written in micrometres, nanometres, millimetres, metres or
kilometres is the same device. Every geometric tolerance in the package is a
dimensionless fraction of a length the caller supplied, so none of them means
anything different when the caller changes unit.

Assertions here are on invariants — region area fractions, the angle bound, the
boundary-name set — never on mesh connectivity, which legally differs between
scales because refinement rounds differently. Each comparison first asserts that
its scale really differs from the reference, and fails as VACUOUS if it does not:
a scale test written only at the scale it was developed at is green by
construction.
"""

import ast
import pathlib
from functools import lru_cache

import numpy as np
import pytest

from meshine import Domain, box_sides, generate, geometry, rectangle
from meshine import refine

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "meshine"

#: One device, five ways of writing it; the number is document units per micrometre.
#: Micrometres is the reference, and is also the scale at which absolute tolerances
#: happen to work, which is why every other entry has to be here.
SCALES = [("um", 1.0), ("nm", 1e3), ("mm", 1e-3), ("m", 1e-6), ("km", 1e-9)]

CORE_W, CORE_H = 0.5, 0.22        # a 500 x 220 nm silicon strip, in micrometres
WIN_W, WIN_H = 4.0, 3.0           # in the window it is usually solved in


def strip_waveguide(s: float):
    """(domain, boundary namer) for the strip written at ``s`` units per micrometre."""
    w, h = 0.5 * CORE_W * s, 0.5 * CORE_H * s
    W, H = 0.5 * WIN_W * s, 0.5 * WIN_H * s
    core = rectangle(-w, -h, w, h)
    d = Domain(size=0.4 * s)
    d.add_region("core", core, size=0.06 * s)
    d.add_region("clad", rectangle(-W, -H, W, H), holes=[core])
    return d, box_sides(-W, W, -H, H)


@lru_cache(maxsize=None)
def meshed(s: float):
    return generate(*strip_waveguide(s), min_angle=28)


def invariants(mesh, s: float) -> dict:
    """Everything about this mesh that a change of unit must not touch."""
    total = mesh.areas.sum()
    diagonal = np.hypot(WIN_W, WIN_H) * s
    return {
        "core area fraction": mesh.region_area("core") / total,
        "clad area fraction": mesh.region_area("clad") / total,
        "meshed area over diagonal squared": total / diagonal ** 2,
        "boundary names": frozenset(mesh.boundary_edges),
        "region names": tuple(mesh.region_names),
    }


# ---- the device is the same device at every scale ---------------------------------

@pytest.mark.parametrize("label,s", SCALES[1:])
def test_the_same_device_meshes_to_the_same_geometry_at_every_scale(label, s):
    """The regression: at metre scale the absolute degeneracy test dropped a quarter of
    the triangles and the core came out with zero area, silently and without an error."""
    assert s != 1.0, f"VACUOUS at {label}: the scale ratio is 1.0, so nothing was rescaled"
    ref, got = invariants(meshed(1.0), 1.0), invariants(meshed(s), s)

    assert got["region names"] == ref["region names"] == ("core", "clad")
    assert got["boundary names"] == ref["boundary names"] == {"left", "right", "top", "bottom"}
    for key in ("core area fraction", "clad area fraction", "meshed area over diagonal squared"):
        assert got[key] == pytest.approx(ref[key], rel=1e-9), f"{label}: {key} moved with the unit"
    assert got["core area fraction"] > 0.0, f"{label}: the core region vanished"
    assert meshed(s).min_angle() >= 28 - 1e-9
    # the triangle count legally differs between scales; only the band is an invariant
    assert meshed(s).num_triangles == pytest.approx(meshed(1.0).num_triangles, rel=0.1)


def test_t_junctions_resolve_at_every_scale():
    """``Domain._split`` compares a perpendicular distance and a position along a
    segment. One constant served both, so it was right for at most one of them."""
    for label, s in SCALES:
        d = Domain(size=0.3 * s)
        d.add_region("a", rectangle(0, 0, 1 * s, 1 * s))
        d.add_region("b", rectangle(1 * s, 0, 2 * s, 0.5 * s))    # meets a's right edge halfway
        d.add_region("c", rectangle(1 * s, 0.5 * s, 2 * s, 1 * s))
        m = generate(d, box_sides(0, 2 * s, 0, 1 * s))
        assert set(m.region_names) == {"a", "b", "c"}, f"{label}: a region was lost"
        assert abs(m.areas.sum() / (s * s) - 2.0) < 1e-9, f"{label}: the T-junction lost area"
        assert ("a", "b") in m.interfaces and ("a", "c") in m.interfaces, \
            f"{label}: the T-junction did not split a's right edge"


def test_box_sides_names_every_edge_at_every_scale():
    """Once the box is smaller than the tolerance, every midpoint matches the first
    test and the whole boundary is named "left" — one Dirichlet set instead of four.

    The box here is the device itself (500 x 220 nm) rather than the window around it,
    because that is the size at which a fixed distance stops separating the sides: in
    kilometres those edges are 5e-13 and 2.2e-13 apart.
    """
    for label, s in SCALES:
        w, h = 0.5 * CORE_W * s, 0.5 * CORE_H * s
        namer = box_sides(-w, w, -h, h)
        got = (namer((-w, 0.0)), namer((w, 0.0)), namer((0.0, -h)), namer((0.0, h)),
               namer((0.0, 0.0)))
        assert got == ("left", "right", "bottom", "top", "outer"), f"{label}: named {got}"


# ---- one constant, one dimension --------------------------------------------------

def test_the_merge_distance_is_a_length_and_the_parametric_bound_is_not():
    """A perpendicular distance and a normalised position along a segment are different
    quantities. The first has to scale with the input and the second must not."""
    measured = {}
    for label, s in SCALES:
        d, namer = strip_waveguide(s)
        d.build(namer)
        measured[label] = (d.extent(), d.point_tol, d.param_eps)

    ref_extent, ref_tol, ref_param = measured["um"]
    assert ref_extent == pytest.approx(np.hypot(WIN_W, WIN_H))
    for label, s in SCALES[1:]:
        assert s != 1.0, f"VACUOUS at {label}: the scale ratio is 1.0"
        extent, point_tol, param_eps = measured[label]
        assert extent == pytest.approx(ref_extent * s), f"{label}: the extent is not the input's"
        assert point_tol == pytest.approx(ref_tol * s), \
            f"{label}: the merge distance did not scale, so it is not a length"
        assert param_eps == ref_param, \
            f"{label}: a normalised position scaled with the unit, so it is not dimensionless"
        assert point_tol / extent == pytest.approx(geometry.MERGE_EPS)


def test_a_quality_mesh_has_no_degenerate_triangle_at_any_scale():
    """The degeneracy test compares a triangle's area to its own edges, so its verdict
    cannot depend on the unit or on where the triangle sits."""
    for label, s in SCALES:
        m = meshed(s)
        h2 = refine._longest_edge_squared(m.nodes[m.triangles])
        flagged = int((np.abs(2 * m.areas) <= refine.AREA_EPS * h2).sum())
        assert flagged == 0, (f"{label}: {flagged} of {m.num_triangles} triangles of a mesh whose "
                              f"smallest angle is {m.min_angle():.1f} degrees were called degenerate")


def test_no_module_hides_a_length_inside_max_of_one():
    """``max(1.0, <a length or an area>)`` returns 1.0 for every input below unit scale,
    which turns a relative tolerance into an absolute one exactly where it matters.
    Measured elsewhere in this workspace, that form let a circle lose 31.8% of its area
    and still be reported as uncut, meshing cleanly and converging on the wrong shape.

    Only a bare ``max`` is scanned: ``np.maximum(x, 1)`` is legitimate where x is a
    count, as it is for a vertex degree.
    """
    offenders = []
    for path in sorted(PACKAGE.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "max" and len(node.args) == 2
                    and any(isinstance(a, ast.Constant) and a.value == 1 for a in node.args)):
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, f"max(1, ...) hides an absolute length in {offenders}"


# ---- nothing empty leaves the stage that made it -----------------------------------

def test_an_empty_mesh_is_refused_where_it_is_made():
    """An empty mesh is a valid data structure and never a valid mesh, so no caller is
    written to check for one; returned, it surfaces frames later as a shape error out
    of numpy that names neither the mesher nor the geometry that caused it."""
    d = Domain(size=0.2)
    d.add_region("a", rectangle(0, 0, 1, 1), holes=[rectangle(0, 0, 1, 1)])   # hole eats the region
    with pytest.raises(ValueError, match="0 triangles and 0 nodes") as e:
        generate(d)
    assert "centroid inside any" in str(e.value), "the message must say which emptiness this is"


def test_a_zero_length_edge_names_the_region_and_the_distance_that_made_it_one():
    """The kilometre document died here with four words and no numbers."""
    d = Domain(size=0.2)
    d.add_region("film", rectangle(0, 0, 1, 1e-18))       # thinner than the merge distance
    with pytest.raises(ValueError, match="zero-length edge") as e:
        generate(d)
    for expected in ("film", "merge distance", "domain diagonal"):
        assert expected in str(e.value), f"the message does not mention {expected!r}"


def test_a_domain_without_extent_is_refused_before_any_tolerance_is_used():
    """Every tolerance here is a fraction of the extent, so a zero extent has to be
    caught before one of them is computed rather than after it divides by zero."""
    d = Domain(size=0.2)
    d.add_region("a", [(1.0, 1.0), (1.0, 1.0), (1.0, 1.0)])
    with pytest.raises(ValueError, match="no extent"):
        generate(d)
