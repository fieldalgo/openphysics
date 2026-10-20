# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Small input angles, the point cap, unresolvable points and sub-resolution edges.

Ruppert's termination argument needs every input angle to be at least 60 degrees.
Every input here except the cap checks and the short edges that meshed before made
refinement run without end before the small-angle rules and the safeguards in
``meshine.refine`` existed. The references
are independent of the mesher: exact polygon areas, the input angle itself (no
triangle can be sharper than the corner it fills), and the requested 28-degree
bound, which must hold everywhere except next to a small angle.

The pass criteria were fixed before this implementation, from the margins measured
on its prototype; the measured values are quoted next to them. An input that used to
hang is meshed in a child process with a timeout (``mesh_in_child``), so a
regression fails its test instead of hanging the suite.
"""

import json
import math
import os
import pickle
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

import meshine
from meshine import Circle, Domain, TriMesh, box_sides, generate, rectangle
from meshine import refine

MIN_ANGLE = 28.0
#: Seconds a child process may take. The criteria below ask for a few seconds; this
#: only turns a hang into a failure.
CHILD_TIMEOUT = 60

CHILD = """
import importlib.util, pickle, sys, time
spec = importlib.util.spec_from_file_location("small_angle_inputs", sys.argv[1])
inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inputs)
domain, kwargs = getattr(inputs, sys.argv[2])(*inputs.json.loads(sys.argv[3]))
start = time.perf_counter()
try:
    result = inputs.generate(domain, min_angle=inputs.MIN_ANGLE, **kwargs)
except Exception as exc:
    result = exc
seconds = time.perf_counter() - start
sys.stdout.buffer.write(pickle.dumps((result, seconds, inputs.meshine.__file__)))
"""


def mesh_in_child(builder, *args):
    """``generate`` on ``builder(*args)`` of this module, run in a fresh interpreter that
    imports the meshine under test: (the mesh or the exception raised, seconds)."""
    root = str(Path(meshine.__file__).resolve().parents[1])
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([root] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    try:
        out = subprocess.run([sys.executable, "-c", CHILD, str(Path(__file__).resolve()), builder,
                              json.dumps(args)], capture_output=True, timeout=CHILD_TIMEOUT, env=env)
    except subprocess.TimeoutExpired:
        pytest.fail(f"{builder}{args} did not finish in {CHILD_TIMEOUT} s")
    assert out.returncode == 0, out.stderr.decode(errors="replace")
    result, seconds, where = pickle.loads(out.stdout)
    assert Path(where).resolve() == Path(meshine.__file__).resolve()
    return result, seconds


def meshed(builder, *args):
    mesh, seconds = mesh_in_child(builder, *args)
    assert isinstance(mesh, TriMesh), f"{builder}{args}: {mesh!r}"
    return mesh, seconds


def watertight(mesh):
    single = {tuple(r) for r in mesh.boundary_edge_set()}
    tagged = {tuple(sorted(r)) for arr in mesh.boundary_edges.values() for r in arr}
    return single == tagged


def node_at(mesh, point):
    return int(np.argmin(np.linalg.norm(mesh.nodes - np.asarray(point, dtype=float), axis=1)))


def reach(mesh, node):
    """(T,) distance from the node to the farthest vertex of each triangle."""
    return np.linalg.norm(mesh.nodes[mesh.triangles] - mesh.nodes[node], axis=2).max(axis=1)


def longest_constrained_edge(mesh, node):
    edges = np.vstack([e for e in (*mesh.boundary_edges.values(), *mesh.interfaces.values()) if len(e)])
    at = edges[(edges == node).any(axis=1)]
    return float(np.linalg.norm(mesh.nodes[at[:, 0]] - mesh.nodes[at[:, 1]], axis=1).max())


def polygon_area(points):
    x, y = np.asarray(points, dtype=float).T
    return 0.5 * abs(x @ np.roll(y, -1) - y @ np.roll(x, -1))


# ---- inputs: each returns (domain, generate keyword arguments) ----------------------

def wedge(deg):
    d = Domain(size=0.1)
    d.add_region("wedge", [(0, 0), (1, 0), (1, math.tan(math.radians(deg)))])
    return d, {}


def fan():
    """Two regions that share the apex (0, 0): a 10-degree and a 15-degree wedge."""
    t10, t25 = math.tan(math.radians(10)), math.tan(math.radians(25))
    d = Domain(size=0.1)
    d.add_region("a", [(0, 0), (1, 0), (1, t10)])
    d.add_region("b", [(0, 0), (1, t10), (1, t25)])
    return d, {}


def fan_with_sizes():
    """A 10-degree wedge of size 0.01 and a 15-degree wedge of size 0.5 that share the apex
    (0, 0), in a region of size 0.1 around them."""
    t10, t25 = math.tan(math.radians(10)), math.tan(math.radians(25))
    d = Domain(size=0.1)
    d.add_region("a", [(0, 0), (1, 0), (1, t10)], size=0.01)
    d.add_region("b", [(0, 0), (1, t10), (1, t25)], size=0.5)
    d.add_region("rest", [(0, 0), (1, t25), (1, 2), (-1, 2), (-1, -1), (1, -1), (1, 0)])
    return d, {}


TRIANGLE = [(-0.3, -0.4), (0.3, -0.4), (0.05, -0.15)]       # corners of 35.5, 45 and 99.5 degrees


def triangle_in_box():
    """The 35.5-degree corner is above min_angle, but its first pieces (0.6 and 0.43
    long) never come within 1/cos(35.5) of each other by halving."""
    d = Domain(size=0.1)
    d.add_region("tri", TRIANGLE)
    d.add_region("box", rectangle(-0.5, -1.2, 0.5, 1.2), holes=[TRIANGLE])
    return d, {}


def crossing(phi, c):
    """A 4 x 2 box cut by a polyline that leaves the bottom at ``phi`` degrees with a
    first edge of length ``c`` and then turns by 2.8 degrees: what clipping a polygonal
    circle against a side leaves behind."""
    a, b = np.radians(phi), np.radians(phi + 2.8)
    q = (2 + c * np.cos(a), c * np.sin(a))
    e = (4.0, q[1] + (4 - q[0]) * np.tan(b))
    d = Domain(size=0.5)
    d.add_region("right", [(2, 0), (4, 0), e, q])
    d.add_region("left", [(0, 0), (2, 0), q, e, (4, 2), (0, 2)])
    return d, {"boundary_names": box_sides(0, 4, 0, 2)}


def exterior_corner():
    """The same triangle as a hole with nothing meshed in it: its sharp corners open
    out of the domain, and their sides still encroach each other."""
    d = Domain(size=0.05)
    d.add_region("box", rectangle(-0.5, -1.2, 0.5, 1.2), holes=[TRIANGLE])
    return d, {"boundary_names": box_sides(-0.5, 0.5, -1.2, 1.2)}


def base_triangle(alpha, beta):
    """The triangle on the base (-0.5, -0.1)-(0.5, -0.1) with base corners of ``alpha`` and
    ``beta`` degrees."""
    a, b = math.radians(alpha), math.radians(beta)
    side = math.sin(b) / math.sin(a + b)
    return [(-0.5, -0.1), (0.5, -0.1), (-0.5 + side * math.cos(a), -0.1 + side * math.sin(a))]


def two_sharp_corners(alpha, beta):
    """``base_triangle`` as a region and as the hole of a box. At 20 and 31 degrees the
    31-degree corner is halving-compatible on its input sides (1.0 and 0.440), but the
    lattice of the treated 20-degree corner puts a vertex on the base and leaves a piece
    of 0.669 there, which is not."""
    triangle = base_triangle(alpha, beta)
    d = Domain(size=0.05)
    d.add_region("box", rectangle(-1, -1, 1, 1), holes=[triangle])
    d.add_region("tri", triangle)
    return d, {"boundary_names": box_sides(-1, 1, -1, 1)}


def polygon_touching_side():
    """A 64-gon of radius 2 with one vertex on the bottom side: two 2.8-degree corners."""
    th = np.radians(-90 + np.arange(64) * 360 / 64)
    circle = [(20 + 2 * np.cos(t), 2 + 2 * np.sin(t)) for t in th]
    circle[0] = (20.0, 0.0)
    d = Domain(size=2.0)
    d.add_region("bg", [(0, 0), (20, 0), (40, 0), (40, 20), (0, 20)], holes=[circle])
    d.add_region("c", circle, size=0.5)
    return d, {"boundary_names": box_sides(0, 40, 0, 20)}


def circle_touching_side():
    """A meshine Circle whose vertex at -90 degrees lies on the bottom side, at (0, 0)."""
    c = Circle((0, 1), 1, n=32)
    d = Domain(size=0.5)
    d.add_region("bg", rectangle(-3, 0, 3, 4), holes=[c])
    d.add_region("c", c, size=0.2)
    return d, {"boundary_names": box_sides(-3, 3, 0, 4)}


def touching_circles(n=32):
    """Two meshine Circles of radius 1 that touch at (1, 0)."""
    c1, c2 = Circle((0, 0), 1, n=n), Circle((2, 0), 1, n=n)
    d = Domain(size=0.5)
    d.add_region("bg", rectangle(-3, -3, 5, 3), holes=[c1, c2])
    d.add_region("c1", c1, size=0.2)
    d.add_region("c2", c2, size=0.2)
    return d, {"boundary_names": box_sides(-3, 5, -3, 3)}


def off_edge_vertex():
    """A vertex 4e-8 above another region's edge, in a domain of extent 2.8."""
    d = Domain(size=0.2)
    d.add_region("lower", rectangle(0, 0, 2, 1))
    d.add_region("upper", [(0, 1), (2, 1), (2, 2), (1, 2), (1, 1 + 4e-8), (0.9, 2), (0, 2)])
    return d, {}


def short_edge_polygons(eps):
    """Two regions split by a line with an edge of length ``eps`` at a 45-degree corner,
    as a cut that passes a rounding error from a polygon vertex leaves behind."""
    a, b = (0.5, 0.0), (0.5 + eps * np.cos(np.pi / 4), eps * np.sin(np.pi / 4))
    t = np.radians(47.8)
    e = (b[0] + 0.5 * np.cos(t), b[1] + 0.5 * np.sin(t))
    return [(0, 0), a, b, e, (e[0], 1), (0, 1)], [a, (e[0], 0), e, b]


def short_edge(eps, snap_eps=None):
    left, right = short_edge_polygons(eps)
    d = Domain(size=0.1) if snap_eps is None else Domain(size=0.1, snap_eps=snap_eps)
    d.add_region("left", left)
    d.add_region("right", right)
    return d, {}


def short_side_edge(layout, length):
    """A unit square with one more vertex on its bottom side, ``length`` after its corner
    (``"corner"``, the square centred on the origin) or after the side's middle
    (``"middle"``): a collinear edge, which the meshine before ``SNAP_EPS`` meshed (below)."""
    d = Domain(size=0.2 if layout == "corner" else 0.1)
    if layout == "corner":
        d.add_region("sq", [(-0.5, -0.5), (-0.5 + length, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)])
        return d, {}
    d.add_region("sq", [(0, 0), (0.5, 0), (0.5 + length, 0), (1, 0), (1, 1), (0, 1)])
    return d, {"boundary_names": box_sides(0, 1, 0, 1)}


def corner_after_short_edge(eps, names):
    """The unit square listed from the vertex ``eps`` after its corner (0, 0), so that the
    short edge ends at the corner and, on its other end, at a collinear vertex."""
    d = Domain(size=0.1)
    d.add_region("sq", [(eps, 0), (0, 0), (0, 1), (1, 1), (1, 0)])
    return d, {"boundary_names": box_sides(0, 1, 0, 1) if names == "box" else names}


def short_side_vertex(layout, length):
    return (-0.5 + length, -0.5) if layout == "corner" else (0.5 + length, 0.0)


#: (layout, length) of collinear edges that the meshine before ``SNAP_EPS`` meshed, measured:
#: 4.5e-8, 5e-8, 8e-8 and 9.9e-8 of the diagonal next to the corner, and 7.1e-8, 8.5e-8 and
#: 9.9e-8 in the middle of the side. Edges of 4e-8 and less never finished in either layout.
MESHED_SHORT_EDGES = [*(("corner", rel * math.sqrt(2.0)) for rel in (4.5e-8, 5e-8, 8e-8, 9.9e-8)),
                      *(("middle", length) for length in (1e-7, 1.2e-7, 1.4e-7))]


# ---- T1-T4: corners below and above min_angle ---------------------------------------

@pytest.mark.parametrize("deg", [0.1, 1.0, 5.0, 10.0, 20.0])
def test_a_wedge_keeps_its_angle_in_one_triangle_and_the_bound_everywhere_else(deg):
    mesh, seconds = meshed("wedge", deg)
    assert seconds < 5.0                                       # measured <= 0.9 s
    assert abs(mesh.areas.sum() - 0.5 * math.tan(math.radians(deg))) <= 1e-12
    assert (mesh.areas > 0).all() and watertight(mesh)
    smallest = mesh.angles().min(axis=1)
    assert smallest.min() >= deg - 1e-9
    below = smallest < MIN_ANGLE
    assert below.sum() == 1                                    # every other triangle is >= 28
    assert (mesh.triangles[below] == node_at(mesh, (0, 0))).any()


def test_two_wedges_that_share_an_apex():
    mesh, _ = meshed("fan")
    t10, t25 = math.tan(math.radians(10)), math.tan(math.radians(25))
    assert mesh.min_angle() >= 10 - 1e-9
    below = mesh.angles().min(axis=1) < MIN_ANGLE
    assert (mesh.triangles[below] == node_at(mesh, (0, 0))).any(axis=1).all()     # measured: 2
    assert abs(mesh.region_area("a") - 0.5 * t10) <= 1e-12
    assert abs(mesh.region_area("b") - 0.5 * (t25 - t10)) <= 1e-12


def test_a_corner_above_min_angle_whose_sides_split_each_other():
    mesh, _ = meshed("triangle_in_box")
    assert mesh.min_angle() >= MIN_ANGLE
    assert abs(mesh.region_area("tri") - 0.075) <= 1e-12


@pytest.mark.parametrize("phi,c", [(35, 0.0469), (20, 0.05)])
def test_a_line_that_leaves_a_side_at_a_small_angle(phi, c):
    mesh, _ = meshed("crossing", phi, c)
    assert watertight(mesh)
    assert abs(mesh.areas.sum() - 8.0) <= 1e-12
    assert mesh.min_angle() >= min(phi, MIN_ANGLE) - 1e-9


def test_a_sharp_corner_that_opens_into_a_hole():
    mesh, _ = meshed("exterior_corner")
    assert mesh.min_angle() >= MIN_ANGLE                       # measured 30.97
    assert abs(mesh.areas.sum() - (2.4 - 0.075)) <= 1e-12


def test_a_corner_that_the_lattice_of_its_neighbour_makes_incompatible():
    """Before the trigger tested the pieces the lattice leaves, the 31-degree corner was
    left untreated, its sides split each other, and generate raised the unresolved-point
    error in 0.02 s, naming a sliver that the input does not have."""
    domain, kwargs = two_sharp_corners(20, 31)
    assert len(treated(domain, kwargs["boundary_names"])) == 2           # both base corners
    mesh, _ = meshed("two_sharp_corners", 20, 31)
    assert watertight(mesh) and set(mesh.boundary_edges) == {"left", "right", "bottom", "top"}
    assert abs(mesh.region_area("tri") - polygon_area(base_triangle(20, 31))) <= 1e-12
    assert abs(mesh.areas.sum() - 4.0) <= 1e-12
    assert mesh.min_angle() >= 20 - 1e-9                                 # measured 20.00


def test_triangles_beside_a_straight_acute_corner():
    """Measured values, not pre-registered criteria. The terminator also leaves skinny
    triangles outside the 14-degree corner, in the box, so the smallest angle is a little
    below the corner's (measured 13.70; 13.02 when the other base corner is 23 degrees).
    They stay next to an apex, as in T6 (measured within 1.23 times)."""
    mesh, _ = meshed("two_sharp_corners", 14, 20)
    assert watertight(mesh) and abs(mesh.areas.sum() - 4.0) <= 1e-12
    assert abs(mesh.region_area("tri") - polygon_area(base_triangle(14, 20))) <= 1e-12
    assert mesh.min_angle() >= 13.0
    apices = [node_at(mesh, p) for p in base_triangle(14, 20)[:2]]
    near = np.min([reach(mesh, a) / longest_constrained_edge(mesh, a) for a in apices], axis=0)
    assert (near[mesh.angles().min(axis=1) < MIN_ANGLE] <= 1.5).all()


# ---- T5: the trigger -----------------------------------------------------------------

def treated(domain, boundary_names="outer"):
    """The vertices the small-angle rules act on: the trigger's ``unit`` map."""
    P, segs, regions = domain.build(boundary_names)
    _tags, unit = refine._treated_apices(P, refine._sharp_corners(P, segs, regions), math.radians(MIN_ANGLE))
    return unit


def notch(deg):
    """Unit square with a notch cut in from the left side; its apex has an exterior gap of deg."""
    t = math.tan(math.radians(deg))
    d = Domain(size=0.1)
    d.add_region("sq", [(0, 0), (1, 0), (1, 1), (0, 1), (0.0, 0.5 + 0.7 * t * 0.4), (0.7, 0.5),
                        (0.0, 0.5 - 0.7 * t * 0.6)])
    return d, {}


def sliver_hole():
    t = math.tan(math.radians(10))
    sliver = [(0.2, 0.5), (0.8, 0.5), (0.8, 0.5 + 0.6 * t)]
    d = Domain(size=0.1)
    d.add_region("box", rectangle(0, 0, 1, 1), holes=[sliver])
    return d, {}


def simcase_documents():
    """({name: document} that meshed before, {name: document} that hung): every simcase
    example that meshes with meshine; its thermal example with the heater moved to cross a
    side at angles that meshed before and at the angles listed as hanging; and a polygon
    with a 35.5-degree corner in the slab example."""
    import copy

    from simcase import examples

    def thermal(cy):
        data = copy.deepcopy(examples.EXAMPLES["thermal_regions"])
        next(s for s in data["geometry"]["shapes"] if s["name"] == "heater")["cy"] = cy
        return data

    def meshes_with_meshine(data):
        types = {p.get("type") for p in data["physics"].values()}
        return types == {"em.modes2d"} or (bool(types & {"thermal.steady2d", "thermal.transient2d"})
                                           and "shapes" in data.get("geometry", {}))

    def bottom(t):
        return thermal(round(2 * math.cos(math.radians(t)), 6))

    def top(t):
        return thermal(round(11 + 2 * math.cos(math.radians(t)), 6))

    slab = copy.deepcopy(examples.EXAMPLES["slab_te_check"])
    slab["geometry"]["shapes"].append({"name": "tri", "type": "polygon", "material": "Si",
                                       "points": [list(p) for p in TRIANGLE]})
    before = {name: data for name, data in examples.EXAMPLES.items() if meshes_with_meshine(data)}
    assert len(before) >= 10, sorted(before)
    before.update({f"bottom {t}": bottom(t) for t in (30, 41, 50, 60)})
    before.update({f"top {t}": top(t) for t in (35, 41, 50, 60)})
    hung = {"bottom tangent": thermal(2.0), "bottom 18": thermal(1.9),
            **{f"bottom {t}": bottom(t) for t in (20, 25, 35, 45)},
            "top tangent": thermal(13.0), "top 18": thermal(12.9),
            **{f"top {t}": top(t) for t in (30, 45)}, "slab polygon": slab}
    return before, hung


def simcase_domain(data):
    """(domain, namer) exactly as simcase meshes the document."""
    from simcase import Document
    from simcase.geometry import build_domain
    from simcase.runner import micrometre_document
    doc = Document.from_dict(data)
    if {p.get("type") for p in data["physics"].values()} == {"em.modes2d"}:
        doc = micrometre_document(doc)
    return build_domain(doc)[:2]


def test_the_trigger_leaves_every_input_that_meshed_before_alone():
    for name, build in {"sliver hole 10": sliver_hole, "notch 10": lambda: notch(10),
                        "notch 35": lambda: notch(35)}.items():
        domain, _ = build()
        assert treated(domain) == {}, name
    for name, data in simcase_documents()[0].items():
        assert treated(*simcase_domain(data)) == {}, name


MESHINE_HUNG = {**{f"wedge {deg}": (wedge, deg) for deg in (0.1, 1.0, 5.0, 10.0, 20.0)},
                "fan": (fan,), "triangle in box": (triangle_in_box,), "crossing 35": (crossing, 35, 0.0469),
                "crossing 20": (crossing, 20, 0.05), "exterior corner": (exterior_corner,),
                "polygon touching side": (polygon_touching_side,),
                "circle touching side": (circle_touching_side,), "touching circles": (touching_circles,)}

@pytest.mark.parametrize("name", [
    *MESHINE_HUNG, "bottom tangent", "bottom 18", "bottom 20", "bottom 25", "bottom 35",
    "top tangent", "top 18", "top 30", "slab polygon"])
def test_the_trigger_treats_every_input_listed_as_hanging(name):
    if name in MESHINE_HUNG:
        build, *args = MESHINE_HUNG[name]
        domain, kwargs = build(*args)
        assert treated(domain, kwargs.get("boundary_names", "outer"))
    else:
        assert treated(*simcase_domain(simcase_documents()[1][name]))


@pytest.mark.parametrize("name", ["bottom 45", "top 45"])
def test_the_45_degree_crossings_hang_on_a_clipped_edge_not_on_their_angle(name):
    """The pre-registered criterion listed these with the inputs the trigger treats; that
    failed and is recorded in the package docs. Their corners are 46.41 degrees and
    halving-compatible, so no vertex is treated. They hung on a clipped edge of 1.4e-8 of
    the diagonal, which the short-edge drop removes; the simcase tests mesh them."""
    assert treated(*simcase_domain(simcase_documents()[1][name])) == {}


# ---- T6: curves that touch -----------------------------------------------------------

@pytest.mark.parametrize("builder,touch", [("polygon_touching_side", (20.0, 0.0)),
                                           ("circle_touching_side", (0.0, 0.0)),
                                           ("touching_circles", (1.0, 0.0))])
def test_curves_that_touch_a_side_or_each_other(builder, touch):
    mesh, seconds = meshed(builder)
    assert seconds < 5.0                                       # measured <= 0.32 s
    assert watertight(mesh)
    assert set(mesh.boundary_edges) == {"left", "right", "bottom", "top"}
    node = node_at(mesh, touch)
    far = reach(mesh, node)
    smallest = mesh.angles().min(axis=1)
    below = smallest < MIN_ANGLE
    assert (far[below] <= 1.5 * longest_constrained_edge(mesh, node)).all()     # measured <= 1.27
    assert (smallest[far > 0.3] >= MIN_ANGLE).all()


def test_two_wedges_of_very_different_sizes_at_one_apex():
    """Measured values under T6's criterion, not a pre-registered test: the triangles below
    28 degrees reach farthest from the apex here of all inputs measured (1.43 times the
    longest constrained edge there; at most 1.26 in T6)."""
    mesh, _ = meshed("fan_with_sizes")
    t10, t25 = math.tan(math.radians(10)), math.tan(math.radians(25))
    assert abs(mesh.region_area("a") - 0.5 * t10) <= 1e-12
    assert abs(mesh.region_area("b") - 0.5 * (t25 - t10)) <= 1e-12
    assert abs(mesh.areas.sum() - 6.0) <= 1e-12 and watertight(mesh)
    assert mesh.min_angle() >= 10 - 1e-9
    apex = node_at(mesh, (0, 0))
    below = mesh.angles().min(axis=1) < MIN_ANGLE
    assert (reach(mesh, apex)[below] <= 1.5 * longest_constrained_edge(mesh, apex)).all()


def test_coarse_touching_circles_end_with_an_error_that_names_the_cause():
    """A documented limit, not a pre-registered criterion. Two 8-gon Circles that touch
    meet at chord corners of 45 degrees: halving-compatible on the chords, so not treated,
    while each projected split turns the corner toward the true angle of 0. The sides
    split each other toward the touch point until the triangulation drops a point
    (measured: about 1 s)."""
    error, _ = mesh_in_child("touching_circles", 8)
    assert isinstance(error, RuntimeError) and "cannot resolve" in str(error), repr(error)
    assert "curved side" in str(error)


# ---- T7-T9: the safeguards -----------------------------------------------------------

@pytest.mark.parametrize("builder,args,cap", [("wedge", (1.0,), 150), ("off_edge_vertex", (), 2000)])
def test_max_points_is_a_hard_cap_in_every_round(monkeypatch, builder, args, cap):
    """The cap used to be checked only after a triangle round; the segment rounds grew
    past it. The spy fails a call past the cap at once, so a broken cap cannot hang."""
    seen = []
    triangulate = refine.Delaunay

    def spy(P, *a, **kw):
        seen.append(len(P))
        assert len(P) <= cap, f"triangulated {len(P)} points with max_points={cap}"
        return triangulate(P, *a, **kw)
    monkeypatch.setattr(refine, "Delaunay", spy)
    if builder == "off_edge_vertex":         # otherwise refused before the cap is reached (below)
        monkeypatch.setattr(refine, "_refuse_unresolved_points", lambda *a: None)
    domain, kwargs = globals()[builder](*args)
    with pytest.raises(RuntimeError, match=f"more than {cap} points"):
        generate(domain, min_angle=MIN_ANGLE, max_points=cap, **kwargs)
    assert max(seen) <= cap


def test_a_boundary_point_the_triangulation_drops_is_refused_with_its_location():
    error, seconds = mesh_in_child("off_edge_vertex")
    assert isinstance(error, RuntimeError) and "cannot resolve" in str(error), repr(error)
    named = re.search(r"\(([-+0-9.e]+), ([-+0-9.e]+)\)", str(error))
    assert named and math.hypot(float(named[1]) - 1.0, float(named[2]) - 1.0) <= 1e-7, str(error)
    assert seconds < 2.0


def test_an_edge_below_snap_eps_is_dropped_and_one_above_it_is_kept():
    diagonal = short_edge(1e-8)[0].extent()
    assert 1e-8 / diagonal < meshine.geometry.SNAP_EPS < 2e-7    # 7.7e-9 of the diagonal

    mesh, _ = meshed("short_edge", 1e-8)
    assert watertight(mesh)
    for name, polygon in zip(("left", "right"), short_edge_polygons(1e-8)):
        # dropping the vertex moves the boundary by less than the edge length
        assert abs(mesh.region_area(name) - polygon_area(polygon)) <= 1e-8 * polygon_area(polygon)
    distance = np.sort(np.linalg.norm(mesh.nodes - [0.5, 0.0], axis=1))
    assert distance[0] == 0.0 and distance[1] > 1e-3

    error, _ = mesh_in_child("short_edge", 1e-8, 0.0)
    assert isinstance(error, RuntimeError) and "cannot resolve" in str(error), repr(error)

    eps = 2e-7 * diagonal
    mesh, _ = meshed("short_edge", eps)
    end = short_edge_polygons(eps)[0][2]
    assert (mesh.nodes == end).all(axis=1).any()


def test_an_edge_that_meshed_before_the_short_edge_drop_keeps_its_vertex():
    """The drop must not reach an edge the earlier meshine meshed, or that mesh changes."""
    for layout, length in MESHED_SHORT_EDGES:
        domain, kwargs = short_side_edge(layout, length)
        points, _, _ = domain.build(kwargs.get("boundary_names", "outer"))
        assert (points == short_side_vertex(layout, length)).all(axis=1).any(), (layout, length)
    for layout, length in (("corner", 9.9e-8 * math.sqrt(2.0)), ("middle", 1e-7)):
        mesh, _ = meshed("short_side_edge", layout, length)
        assert (mesh.nodes == short_side_vertex(layout, length)).all(axis=1).any(), (layout, length)
        assert watertight(mesh) and abs(mesh.areas.sum() - 1.0) <= 1e-12
        assert mesh.min_angle() >= MIN_ANGLE


@pytest.mark.parametrize("names", ["box", "outer"])
def test_the_drop_keeps_a_corner_next_to_a_collinear_vertex(names):
    """Dropping the corner would cut it and turn the left side into a slanted 'outer' one."""
    mesh, _ = meshed("corner_after_short_edge", 1e-8, names)
    assert (mesh.nodes == (0.0, 0.0)).all(axis=1).any()
    assert watertight(mesh) and abs(mesh.areas.sum() - 1.0) <= 1e-12
    assert set(mesh.boundary_edges) == ({"left", "right", "bottom", "top"} if names == "box" else {"outer"})


def test_the_drop_keeps_a_vertex_whose_removal_would_change_a_boundary_name():
    """A chamfer of 1e-8 at a corner of a named box: either end joins two named sides."""
    d = Domain(size=0.1)
    d.add_region("sq", [(1e-8, 0), (1, 0), (1, 1), (0, 1), (0, 1e-8)])
    points, segs, _ = d.build(box_sides(0, 1, 0, 1))
    assert len(points) == 5
    assert sorted(s.name for s in segs) == ["bottom", "left", "outer", "right", "top"]
