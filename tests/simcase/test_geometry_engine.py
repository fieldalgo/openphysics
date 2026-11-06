# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Geometry document version 1, stage 2: the exact 2D engine.

The pre-registered checks G2-1 to G2-7 (HQ ``work/openphysics-geometry.md``,
2026-11-04 block) are the sections below. shapely is a test reference only; the
engine itself imports nothing but the standard library.
"""

import copy
import json
import math
import random
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

import pytest
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from meshine import Circle, generate
from simcase.examples import EXAMPLES
from simcase.geometry_document import _MISSING, GeometryError, from_v02, parse
from simcase.geometry_engine import Q2, cmp, cross_sign, evaluate

ROOT = Path(__file__).resolve().parents[2]
REL = 1e-12
DOMAIN_NM2 = 100 * 100 * 1e6              # the 100 nm test plate in pm^2


def v1(features, dom=(0, 100, 0, 100), bg="SiO2", finalize="later_wins", units="nm", dimension="2d", **extra):
    comp = {"dimension": dimension, "domain": {"xmin": dom[0], "xmax": dom[1], "ymin": dom[2], "ymax": dom[3]},
            "background": {"material": bg}, "features": features, "finalize": finalize}
    comp.update(extra)
    return {"units": {"length": units}, "geometry": {"version": 1, "components": {"xs": comp}}}


def rect(name, x, y, w, h, material="m", **kw):
    return {"name": name, "type": "rect", "x": x, "y": y, "w": w, "h": h, "material": material, **kw}


def circle(name, cx, cy, r, material="m", **kw):
    return {"name": name, "type": "circle", "cx": cx, "cy": cy, "r": r, "material": material, **kw}


def polygon(name, points, material="m", **kw):
    return {"name": name, "type": "polygon", "points": [list(p) for p in points], "material": material, **kw}


def run(doc):
    return evaluate(parse(doc))


def areas_nm2(rc):
    return {r: rc.area_of_region(r) / 1e6 for r in rc.region_names()}


def close(a, b, rel=REL):
    return abs(a - b) <= rel * max(abs(a), abs(b))


def check_euler(rc):
    """G2-3 on one complex: V - E + F = 1 + C and the cells tile the domain."""
    V, E, F, C = rc.euler()
    assert V - E + F == 1 + C, (V, E, F, C)
    dom = rc.domain
    total = (dom["xmax"] - dom["xmin"]) * (dom["ymax"] - dom["ymin"])
    assert close(sum(c.area for c in rc.cells), total), (sum(c.area for c in rc.cells), total)
    for k in rc.curves:
        assert k.left is not None or k.right is not None
    return rc


# ----------------------------------------------------------------- exact numbers

def test_quadratic_numbers_compare_exactly_across_fields():
    assert cmp(Q2(0, 1, 2), Q2(0, 1, 3)) < 0
    assert cmp(Q2(0, 1, 8), Q2(0, 2, 2)) == 0                  # sqrt(8) == 2 sqrt(2)
    assert Q2(3, -2, 2).sign() > 0 and Q2(2, -1, 5).sign() < 0   # 3 - 2 sqrt 2 > 0, 2 - sqrt 5 < 0
    assert Q2(0, 1, 49).D == 0 and Q2(0, 1, 49).a == 7            # a perfect square folds
    assert cmp(Q2(1, 1, 2), Q2(1, 1, 3)) < 0 and cmp(Q2(5, -1, 2), Q2(3, 1, 3)) < 0   # 3.586 < 4.732
    assert cross_sign(Q2(0, 1, 2), Q2(1), Q2(0, 1, 3), Q2(1)) < 0                      # sqrt2 - sqrt3
    assert cross_sign(Q2(0, 1, 2), Q2(0, 1, 2), Q2(0, 1, 3), Q2(0, 1, 3)) == 0        # parallel
    assert abs(float(Q2(1, 1, 2)) - (1 + math.sqrt(2))) < 1e-15
    assert Q2(Fraction(1, 3), Fraction(1, 7), 2).approx(60) * 7 * 3 >= 0


# ----------------------------------------------------------------- basic topology

def test_one_rect_in_a_plate():
    rc = check_euler(run(v1([rect("core", 10, 10, 30, 20, "Si")])))
    assert rc.region_names() == ["core", "background"]
    assert [len(c.loops) for c in rc.cells] == [2, 1]
    assert areas_nm2(rc) == {"background": 9400.0, "core": 600.0}
    assert {k.kind for k in rc.curves} == {"line"} and len(rc.curves) == 8
    assert {k.tag for k in rc.curves if k.left is None or k.right is None} == {"left", "right", "bottom", "top"}
    core_curves = [k for k in rc.curves if "core.top" in k.provenance]
    assert len(core_curves) == 1 and {core_curves[0].left, core_curves[0].right} == {0, 1}


def test_later_feature_wins_and_covered_features_yield_no_cell():
    rc = check_euler(run(v1([rect("a", 10, 10, 30, 20, "Si"), rect("b", 30, 20, 30, 20, "Ge")])))
    assert areas_nm2(rc) == {"background": 8900.0, "a": 500.0, "b": 600.0}
    rc = check_euler(run(v1([rect("a", 10, 10, 10, 10, "Si"), rect("b", 0, 0, 50, 50, "Ge")])))
    assert rc.region_names() == ["b", "background"] and areas_nm2(rc)["b"] == 2500.0
    assert len(rc.curves) == 8                                         # a's boundary is gone


def test_imprint_keeps_covered_boundaries_as_pieces_of_one_region():
    rc = check_euler(run(v1([rect("a", 10, 10, 10, 10, "Si"), rect("b", 0, 0, 50, 50, "Ge")], finalize="imprint")))
    assert [c.region for c in rc.cells] == ["background", "b", "b"]
    assert sorted(c.area / 1e6 for c in rc.cells if c.region == "b") == [100.0, 2400.0]
    inner = [k for k in rc.curves if k.provenance == frozenset({"a.top"})]
    assert len(inner) == 1 and inner[0].left != inner[0].right and all(
        rc.cells[s].region == "b" for s in (inner[0].left, inner[0].right))
    assert all(c.material == "Ge" for c in rc.cells if c.region == "b")


def test_region_merges_features_and_drops_the_shared_edge():
    rc = check_euler(run(v1([rect("a", 10, 10, 30, 20, "Si", region="core"),
                             rect("b", 40, 10, 30, 20, "Si", region="core")])))
    assert rc.region_names() == ["core", "background"] and len(rc.curves) == 10
    assert areas_nm2(rc)["core"] == 1200.0
    rc = check_euler(run(v1([rect("a", 10, 10, 30, 20, "Si"), rect("b", 40, 10, 30, 20, "Si")])))
    assert len(rc.curves) == 11 and len(rc.cells) == 3                 # same material, still two regions


def test_void_cells_border_the_mesh_exterior():
    rc = check_euler(run(v1([circle("h", 50, 50, 10, None)])))
    hole = rc.cells[rc.cells_of_region("h")[0]]
    assert hole.void and close(hole.area / 1e6, math.pi * 100)
    assert {rc.curves[i].tag for i in rc.exterior_curves()} == {"left", "right", "bottom", "top", "outer"}
    assert {k.kind for k in rc.curves if "h.boundary" in k.provenance} == {"circle"}


def test_segments_are_internal_curves_until_a_later_feature_covers_them():
    rc = check_euler(run(v1([rect("a", 10, 10, 40, 40, "Si"), {"name": "s", "type": "segment",
                                                                 "points": [[20, 20], [30, 35]]}])))
    (k,) = [k for k in rc.curves if "s.line" in k.provenance]
    assert k.left == k.right and rc.cells[k.left].region == "a"
    rc = check_euler(run(v1([rect("a", 10, 10, 40, 40, "Si"), {"name": "s", "type": "segment",
                                                                 "points": [[0, 30], [60, 30]]}])))
    assert sorted(c.area / 1e6 for c in rc.cells if c.region == "a") == [800.0, 800.0]
    rc = check_euler(run(v1([{"name": "s", "type": "segment", "points": [[20, 20], [30, 35]]},
                             rect("a", 10, 10, 40, 40, "Si")])))
    assert not rc.curves_with("s.line")                                 # covered by a later feature


def test_axisymmetric_components_name_the_axis():
    rc = check_euler(run(v1([rect("a", 0, 10, 20, 20, "Si")], dimension="axisymmetric")))
    assert "axis" in {k.tag for k in rc.curves} and "left" not in {k.tag for k in rc.curves}
    rc = check_euler(run(v1([rect("a", 5, 10, 20, 20, "Si")], dom=(1, 100, 0, 100), dimension="axisymmetric")))
    assert "left" in {k.tag for k in rc.curves}


def test_the_engine_refuses_what_it_cannot_take():
    with pytest.raises(GeometryError, match="2d and axisymmetric"):
        run({"units": {"length": "nm"}, "geometry": {"version": 1, "components": {"c": {
            "dimension": "3d", "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1, "zmin": 0, "zmax": 1}}}}})
    path = {"name": "p", "type": "path", "start": [30, 40], "material": "Si",
            "segments": [{"line": [70, 40]}, {"arc": {"center": [70, 50], "to": [71, 60], "ccw": True}}]}
    with pytest.raises(GeometryError, match="not on the arc's circle"):
        run(v1([path]))
    bow = {"name": "p", "type": "path", "start": [10, 10], "material": "Si",
           "segments": [{"line": [50, 50]}, {"line": [50, 10]}, {"line": [10, 50]}]}
    with pytest.raises(GeometryError, match="crosses itself"):
        run(v1([bow]))
    with pytest.raises(GeometryError, match="selects nothing"):
        run(v1([rect("a", 10, 10, 10, 10)], selections={"none": {"boundary": {"between": ["a", "exterior"]}}}))
    run(v1([rect("a", 10, 10, 10, 10)], selections={"none": {"boundary": {"between": ["a", "exterior"]},
                                                              "optional": True}}))


# ----------------------------------------------------------------- selectors and tags

def test_contract_example_selections_resolve():
    doc = json.loads((ROOT / "examples" / "simcase" / "geometry_v1_soi_strip.json").read_text(encoding="utf-8"))
    rc = check_euler(run(doc))
    assert rc.region_names() == ["core", "background"]
    core_wall = {"boundary": {"between": ["core", "background"]}}
    comp = doc["geometry"]["components"]
    (cname,) = comp
    comp[cname]["selections"] = {"core_top": {"boundary": "core.top"}, "core_wall": core_wall,
                                 "si": {"region": {"material": comp[cname]["features"][0]["material"]}},
                                 "walls": {"boundary": {"of": "core"}}, "rim": {"boundary": {"between": ["background", "exterior"]}}}
    rc = run(doc)
    sel = rc.selections
    assert sel["core_top"][0] == "boundary" and len(sel["core_top"][1]) == 1
    assert len(sel["core_wall"][1]) == 4 and sel["walls"][1] == sel["core_wall"][1]
    assert sel["si"] == ("region", frozenset(rc.cells_of_region("core")))
    assert sel["rim"][1] == frozenset(rc.exterior_curves())


def test_boundary_tags_apply_in_order_to_exterior_curves_only():
    doc = v1([rect("sub", 0, 0, 100, 20, "sub"),
              {"name": "sig", "type": "trapezoid", "cx": 50, "y": 20, "w": 31, "w_top": 25, "h": 7, "material": "cu"}],
             boundary_tags=[{"tag": "gnd", "select": {"boundary": {"between": ["sub", "exterior"]}}},
                            {"tag": "port", "select": {"boundary": "sig.top"}},
                            {"tag": "never", "select": {"boundary": "bottom"}}])
    rc = check_euler(run(doc))
    assert areas_nm2(rc)["sig"] == 196.0
    tags = {k.tag for k in rc.curves if k.tag}
    assert tags == {"gnd", "left", "right", "top"}                # bottom was taken by gnd first; sig.top is interior
    assert {k.tag for k in rc.curves if "domain.bottom" in k.provenance} == {"gnd"}


def test_region_strings_follow_the_contract_order():
    doc = v1([rect("a", 10, 10, 10, 10, "Si", region="core"), rect("b", 30, 10, 10, 10, "Si", region="core")],
             selections={"c": {"region": "core"}, "fa": {"region": "a"}, "both": {"region": {"any": ["a", "b"]}}})
    rc = run(doc)
    assert rc.selections["c"][1] == frozenset(rc.cells_of_region("core"))
    assert rc.selections["fa"][1] == frozenset(c.index for c in rc.cells if c.feature == "a")
    assert rc.selections["both"][1] == rc.selections["c"][1]


# ----------------------------------------------------------------- G2-1: shapely agreement in general position

def _shapely_regions(doc):
    comp = doc["geometry"]["components"]["xs"]
    dom = comp["domain"]
    clip = box(dom["xmin"], dom["ymin"], dom["xmax"], dom["ymax"])
    polys = []
    for f in comp["features"]:
        g = box(f["x"], f["y"], f["x"] + f["w"], f["y"] + f["h"]) if f["type"] == "rect" else Polygon(f["points"])
        polys.append(g.intersection(clip))
    out = {}
    for i, f in enumerate(comp["features"]):
        g = polys[i].difference(unary_union(polys[i + 1:])) if i + 1 < len(polys) else polys[i]
        out[f["name"]] = g
    out["background"] = clip.difference(unary_union(polys))
    return out


def _parts(g):
    if g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    return [p for p in g.geoms if p.geom_type == "Polygon" and not p.is_empty]


def _feature_edges(f, dom):
    if f["type"] == "rect":
        x, y, w, h = f["x"], f["y"], f["w"], f["h"]
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    else:
        pts = [tuple(p) for p in f["points"]]
    return [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def _general_position(feats, dom):
    """No vertex on another feature's edge or the domain's edges, and no shared vertex."""
    d = [((dom[0], dom[2]), (dom[1], dom[2])), ((dom[1], dom[2]), (dom[1], dom[3])),
         ((dom[1], dom[3]), (dom[0], dom[3])), ((dom[0], dom[3]), (dom[0], dom[2]))]
    edges = [(i, e) for i, f in enumerate(feats) for e in _feature_edges(f, dom)] + [(-1, e) for e in d]
    verts = [(i, e[0]) for i, e in edges]
    for i, v in verts:
        for j, (p, q) in edges:
            if i == j:
                continue
            if (q[0] - p[0]) * (v[1] - p[1]) - (q[1] - p[1]) * (v[0] - p[0]) == 0 and \
                    min(p[0], q[0]) <= v[0] <= max(p[0], q[0]) and min(p[1], q[1]) <= v[1] <= max(p[1], q[1]):
                return False
    return True


def _random_feature(rng, i):
    if rng.random() < 0.6:
        return rect(f"f{i}", rng.randint(-10, 95), rng.randint(-10, 95), rng.randint(10, 60), rng.randint(10, 60))
    cx, cy, r = rng.randint(10, 90), rng.randint(10, 90), rng.randint(8, 40)
    angs = sorted(rng.uniform(0, 2 * math.pi) for _ in range(rng.randint(3, 7)))
    pts = [(round(cx + r * math.cos(a)), round(cy + r * math.sin(a))) for a in angs]
    if len(set(pts)) < len(pts) or not Polygon(pts).is_valid or Polygon(pts).area < 1:
        return None
    return polygon(f"f{i}", pts)


def _fuzz_cases(seed, count):
    rng = random.Random(seed)
    accepted, touching = [], []
    while len(accepted) < count:
        feats = [f for f in (_random_feature(rng, i) for i in range(rng.randint(1, 6))) if f is not None]
        if not feats:
            continue
        (accepted if _general_position(feats, (0, 100, 0, 100)) else touching).append(feats)
    return accepted, touching


def _compare_with_shapely(doc, rc, holes=True, faces=True):
    ref = _shapely_regions(doc)
    problems = []
    for name, g in ref.items():
        ps = _parts(g)
        a_ref = sum(p.area for p in ps)
        cells = rc.cells_of_region(name)
        a = rc.area_of_region(name) / 1e6 if cells else 0.0
        if not close(a, a_ref):
            problems.append(f"{name}: area {a!r} vs shapely {a_ref!r}")
        if faces and len(cells) != len(ps):
            problems.append(f"{name}: {len(cells)} faces vs shapely {len(ps)} parts")
        if holes and sum(len(rc.cells[c].loops) - 1 for c in cells) != sum(len(p.interiors) for p in ps):
            problems.append(f"{name}: hole count differs from shapely")
    return problems


def test_g2_1_general_position_fuzz_agrees_with_shapely():
    accepted, touching = _fuzz_cases(20261104, 2000)
    problems = []
    for feats in accepted:
        doc = v1(feats)
        rc = check_euler(run(doc))
        for p in _compare_with_shapely(doc, rc):
            problems.append((feats, p))
    assert not problems, problems[:5]
    # touching cases are outside G2-1: the areas still agree; a piece pinched at a vertex is one
    # ring with a repeated vertex for shapely and two faces, or an outer loop plus a hole, for
    # the engine, so face and hole counts are compared only for the record
    representation = 0
    for feats in touching[:300]:
        doc = v1(feats)
        rc = check_euler(run(doc))
        assert not _compare_with_shapely(doc, rc, holes=False, faces=False), feats
        representation += bool(_compare_with_shapely(doc, rc))
    print(f"G2-1: {len(accepted)} general-position cases agree; {min(len(touching), 300)} touching cases agree "
          f"in area, {representation} differ in how a pinched piece is represented")


# ----------------------------------------------------------------- G2-2: circles and arcs against analytic areas

def _lens(d, r1, r2):
    """Area of the intersection of two circles with centre distance d."""
    a = (d * d + r1 * r1 - r2 * r2) / (2 * d)
    b = d - a
    return (r1 * r1 * math.acos(a / r1) - a * math.sqrt(r1 * r1 - a * a)
            + r2 * r2 * math.acos(b / r2) - b * math.sqrt(r2 * r2 - b * b))


def test_g2_2_two_circle_lens():
    rc = check_euler(run(v1([circle("a", 40, 50, 20, "A"), circle("b", 60, 50, 20, "B")])))
    lens = _lens(20.0, 20.0, 20.0)
    assert close(areas_nm2(rc)["a"], math.pi * 400 - lens)
    assert close(areas_nm2(rc)["b"], math.pi * 400)
    assert {k.kind for k in rc.curves if "a.boundary" in k.provenance} == {"arc"}
    rc = check_euler(run(v1([circle("a", 40, 50, 20, "A"), circle("b", 65, 50, 15, "B")])))
    assert close(areas_nm2(rc)["a"], math.pi * 400 - _lens(25.0, 20.0, 15.0))


def test_g2_2_circle_cut_by_a_rect_leaves_a_circular_segment():
    rc = check_euler(run(v1([circle("c", 50, 50, 20, "A"), rect("r", 60, 0, 40, 100, "B")])))
    d = 10.0
    segment = 400 * math.acos(d / 20) - d * math.sqrt(400 - d * d)
    assert close(areas_nm2(rc)["c"], math.pi * 400 - segment)
    assert close(areas_nm2(rc)["r"], 4000.0)
    (k,) = [k for k in rc.curves if k.provenance == frozenset({"c.boundary", "r.left"}) or
            ("c.boundary" not in k.provenance and "r.left" in k.provenance and rc.cells[k.left].region != "background"
             and rc.cells[k.right].region != "background")]
    assert {rc.cells[k.left].region, rc.cells[k.right].region} == {"c", "r"}


def test_g2_2_concentric_annulus_and_path_arcs():
    rc = check_euler(run(v1([circle("o", 50, 50, 30, "A"), circle("i", 50, 50, 10, "B")])))
    assert close(areas_nm2(rc)["o"], math.pi * (900 - 100)) and close(areas_nm2(rc)["i"], math.pi * 100)
    outer = rc.cells[rc.cells_of_region("o")[0]]
    assert len(outer.loops) == 2 and all(rc.curves[i].kind == "circle" for lp in outer.loops for i, _ in lp)
    stadium = {"name": "p", "type": "path", "start": [30, 40], "material": "Si",
               "segments": [{"line": [70, 40]}, {"arc": {"center": [70, 50], "to": [70, 60], "ccw": True}, "name": "cap_r"},
                            {"line": [30, 60]}, {"arc": {"center": [30, 50], "to": [30, 40], "ccw": True}}]}
    rc = check_euler(run(v1([stadium])))
    assert close(areas_nm2(rc)["p"], 40 * 20 + math.pi * 100)
    assert [k.kind for k in rc.curves if "p.cap_r" in k.provenance] == ["arc"]
    assert rc.curves_with("p.s4")
    bowl = {"name": "b", "type": "path", "start": [20, 50], "material": "Si",
            "segments": [{"arc": {"center": [50, 50], "to": [80, 50], "ccw": False}}, {"line": [20, 50]}]}
    rc = check_euler(run(v1([bowl])))
    assert close(areas_nm2(rc)["b"], math.pi * 900 / 2)


# ----------------------------------------------------------------- G2-4: invariance

def _signature(rc):
    cells = sorted((c.region, c.feature, sorted(len(lp) for lp in c.loops), c.area) for c in rc.cells)
    curves = sorted((k.kind, tuple(sorted(k.provenance))) for k in rc.curves)
    return cells, curves


def _transform(doc, fn, dom):
    doc = copy.deepcopy(doc)
    comp = doc["geometry"]["components"]["xs"]
    comp["domain"] = {"xmin": dom[0], "xmax": dom[1], "ymin": dom[2], "ymax": dom[3]}
    for f in comp["features"]:
        if f["type"] == "polygon":
            f["points"] = [list(fn(*p)) for p in f["points"]]
        elif f["type"] == "circle":
            f["cx"], f["cy"] = fn(f["cx"], f["cy"])
        elif f["type"] == "path":
            f["start"] = list(fn(*f["start"]))
            for s in f["segments"]:
                if "line" in s:
                    s["line"] = list(fn(*s["line"]))
                else:
                    s["arc"]["center"] = list(fn(*s["arc"]["center"]))
                    s["arc"]["to"] = list(fn(*s["arc"]["to"]))
                    s["arc"]["ccw"] = s["arc"]["ccw"] ^ MIRROR
    return doc


MIRROR = False


def _invariance_docs():
    tri = polygon("t", [(30, 50), (40, 70), (20, 70)], "A")
    quad = polygon("q", [(25, 25), (75, 20), (80, 60), (35, 55)], "B")
    stadium = {"name": "p", "type": "path", "start": [30, 40], "material": "C",
               "segments": [{"line": [70, 40]}, {"arc": {"center": [70, 50], "to": [70, 60], "ccw": True}},
                            {"line": [30, 60]}, {"arc": {"center": [30, 50], "to": [30, 40], "ccw": True}}]}
    return [v1([quad, tri, circle("c", 60, 60, 15, "D")]), v1([stadium, circle("c", 70, 45, 12, "D"), quad]),
            v1([circle("a", 40, 50, 20, "A"), circle("b", 60, 50, 20, "B"), tri])]


@pytest.mark.parametrize("case", range(3))
def test_g2_4_translation_rotation_and_mirror_keep_topology_and_areas(case):
    global MIRROR
    doc = _invariance_docs()[case]
    base = _signature(check_euler(run(doc)))
    moved = _transform(doc, lambda x, y: (x + 123, y - 457), (123, 223, -457, -357))
    rotated = _transform(doc, lambda x, y: (-y, x), (-100, 0, 0, 100))
    MIRROR = True
    try:
        mirrored = _transform(doc, lambda x, y: (-x, y), (-100, 0, 0, 100))
    finally:
        MIRROR = False
    for other in (moved, rotated, mirrored):
        cells, curves = _signature(check_euler(run(other)))
        assert curves == base[1]
        assert [c[:3] for c in cells] == [c[:3] for c in base[0]]
        assert all(close(a[3], b[3]) for a, b in zip(cells, base[0]))


# ----------------------------------------------------------------- G2-5: degenerate inputs with hand-derived expectations

def test_g2_5_tangent_circles():
    rc = check_euler(run(v1([circle("a", 30, 50, 20, "A"), circle("b", 70, 50, 20, "B")])))   # externally tangent
    assert close(areas_nm2(rc)["a"], math.pi * 400) and close(areas_nm2(rc)["b"], math.pi * 400)
    assert len(rc.cells) == 3 and len(rc.curves) == 8
    bg = rc.cells[rc.cells_of_region("background")[0]]
    assert sorted(len(lp) for lp in bg.loops) == [4, 4]            # one pinched hole through the tangent point
    rc = check_euler(run(v1([circle("a", 50, 50, 30, "A"), circle("b", 60, 50, 20, "B")])))   # internally tangent
    assert close(areas_nm2(rc)["a"], math.pi * (900 - 400)) and close(areas_nm2(rc)["b"], math.pi * 400)
    assert len(rc.cells) == 3 and len(rc.curves) == 8
    a = rc.cells[rc.cells_of_region("a")[0]]
    assert [len(lp) for lp in a.loops] == [4]                        # outer and inner circle share the tangent vertex


def test_g2_5_overlapping_edges_and_a_vertex_on_an_edge():
    rc = check_euler(run(v1([rect("a", 10, 10, 30, 20, "A"), rect("b", 25, 30, 30, 20, "B")])))
    assert areas_nm2(rc) == {"background": 8800.0, "a": 600.0, "b": 600.0}
    assert len(rc.curves) == 13
    (shared,) = [k for k in rc.curves if k.provenance == frozenset({"a.top", "b.bottom"})]
    assert {rc.cells[shared.left].region, rc.cells[shared.right].region} == {"a", "b"}
    rc = check_euler(run(v1([rect("r", 10, 10, 40, 40, "A"), polygon("t", [(30, 50), (40, 70), (20, 70)], "B")])))
    assert areas_nm2(rc) == {"background": 8200.0, "r": 1600.0, "t": 200.0}
    assert len(rc.curves) == 12 and len(rc.curves_with("r.top")) == 2


def test_g2_5_three_curves_through_one_point_and_concentric_rings():
    rc = check_euler(run(v1([rect("a", 10, 10, 40, 40, "A"), rect("b", 50, 50, 30, 30, "B"),
                             polygon("c", [(45, 55), (65, 35), (65, 55)], "C")])))
    assert areas_nm2(rc) == {"background": 7375.0, "a": 1600.0, "b": 825.0, "c": 200.0}
    assert len(rc.cells) == 4
    corner = [v for v in rc.vertices if v[0].a == 50_000 and v[1].a == 50_000]
    assert len(corner) == 1
    rc = check_euler(run(v1([circle("o", 50, 50, 30, "A"), circle("m", 50, 50, 20, "B"), circle("i", 50, 50, 10, "C")])))
    assert all(close(areas_nm2(rc)[n], a) for n, a in (("o", math.pi * 500), ("m", math.pi * 300), ("i", math.pi * 100)))
    assert len(rc.curves) == 10


@pytest.mark.parametrize("unit, scale", [("nm", 1), ("um", 1e-3), ("m", 1e-9)])
def test_g2_5_an_8_by_8_grid_of_touching_rects_in_any_unit(unit, scale):
    feats = [rect(f"r{i}_{j}", 10 * i * scale, 10 * j * scale, 10 * scale, 10 * scale) for i in range(8) for j in range(8)]
    rc = check_euler(run(v1(feats, dom=(0, 80 * scale, 0, 80 * scale), units=unit)))
    assert len(rc.cells) == 64 and len(rc.curves) == 144 and "background" not in rc.region_names()
    assert all(c.area == 100 * 1e6 for c in rc.cells)
    assert all(len(c.loops) == 1 and len(c.loops[0]) == 4 for c in rc.cells)


# ----------------------------------------------------------------- G2-6: the current documents against the shapely route

def _current_docs():
    docs = {f"builtin:{k}": v for k, v in EXAMPLES.items()}
    docs.update({p.name: json.loads(p.read_text(encoding="utf-8"))
                 for p in sorted((ROOT / "examples" / "simcase").glob("*.json"))})
    return {k: v for k, v in docs.items() if "version" not in v.get("geometry", {})}


CURRENT = _current_docs()


@pytest.mark.parametrize("name", sorted(CURRENT))
def test_g2_6_current_documents_match_the_shapely_route(name):
    from simcase import Document
    from simcase.geometry import resolve_regions
    doc = copy.deepcopy(CURRENT[name])
    model = parse({"units": doc["units"], "geometry": from_v02(doc["geometry"])})
    g = doc["geometry"]
    if "zmin" in g["domain"]:
        with pytest.raises(GeometryError, match="2d and axisymmetric"):
            evaluate(model)
        return
    rc = check_euler(evaluate(model))
    if "background" not in g:
        (cell,) = rc.cells
        assert cell.material is _MISSING and cell.region == "background"
        return
    ref = resolve_regions(Document.from_dict(doc))
    unit = float(model.pm_per_unit)
    assert [r[0] for r in ref] == rc.region_names()
    circle_names = {s["name"] for s in g["shapes"] if s["type"] == "circle"}
    dom = g["domain"]
    sliver = 1e-12 * (dom["xmax"] - dom["xmin"]) * (dom["ymax"] - dom["ymin"])
    for rname, material, geom, _size, _exact in ref:
        cells = rc.cells_of_region(rname)
        assert all(rc.cells[c].material == material for c in cells)
        parts = [p for p in _parts(geom) if p.area > sliver]
        if len(parts) != len(_parts(geom)):
            # the 0.2 route's floating-point corner (0.47 + 2.0 = 2.4699999999999998) leaves a zero-area
            # sliver part; the exact route puts the corner at 2.47 (contract, "Internal grid")
            print(f"G2-6 {name} {rname}: the shapely route carries {len(_parts(geom)) - len(parts)} zero-area part(s)")
        assert len(cells) == len(parts)
        area = rc.area_of_region(rname) / unit ** 2
        if close(area, geom.area):
            continue
        touches_circle = rname in circle_names or any(
            rc.curves[i].kind != "line" for c in cells for lp in rc.cells[c].loops for i, _ in lp)
        assert touches_circle, (rname, area, geom.area)
        print(f"G2-6 {name} {rname}: exact area {area:.12g} vs 128-gon route {geom.area:.12g} "
              f"(relative {abs(area - geom.area) / geom.area:.2e})")


# ----------------------------------------------------------------- G2-7: time (proposed gates, confirmed after measurement)

def _studio_max_case(rng):
    feats = []
    for i in range(8):
        cx, cy, r = rng.randint(20, 80), rng.randint(20, 80), rng.randint(10, 30)
        angs = sorted(rng.uniform(0, 2 * math.pi) for _ in range(12))
        pts = [(round(cx + r * math.cos(a)), round(cy + r * math.sin(a))) for a in angs]
        if len(set(pts)) < 12 or not Polygon(pts).is_valid:
            return None
        feats.append(polygon(f"s{i}", pts))
    return v1(feats)


def _pcb_case():
    feats = [rect("plane", 0, 0, 1000, 1000, "cu")]
    for i in range(10):
        for j in range(10):
            feats.append(rect(f"pad{i}_{j}", 50 + 90 * i, 50 + 90 * j, 60, 60, "cu"))
    for i in range(10):
        for j in range(10):
            feats.append(circle(f"via{i}_{j}", 80 + 90 * i, 80 + 90 * j, 15, "drill" if (i + j) % 3 else None))
    return v1(feats[:200], dom=(0, 1000, 0, 1000), bg="fr4")


def test_g2_7_time_of_the_studio_maximum_and_a_pcb_like_plane():
    rng = random.Random(7)
    studio = next(d for d in iter(lambda: _studio_max_case(rng), 1) if d is not None)
    t = time.perf_counter()
    rc = check_euler(run(studio))
    studio_s = time.perf_counter() - t
    pcb = _pcb_case()
    t = time.perf_counter()
    rc2 = check_euler(run(pcb))
    pcb_s = time.perf_counter() - t
    print(f"G2-7: Studio maximum (8 shapes x 12 vertices) {studio_s:.3f} s, {len(rc.cells)} cells; "
          f"PCB-like 200 features {pcb_s:.2f} s, {len(rc2.cells)} cells, {len(rc2.curves)} curves")
    assert studio_s < 0.2, studio_s
    assert pcb_s < 10.0, pcb_s


# ----------------------------------------------------------------- the meshine hand-off

def _mesh(doc, size_nm=5.0):
    rc = run(doc)
    d, namer, materials = rc.to_domain(size_nm / 1000)
    mesh = generate(d, boundary_names=namer)
    return rc, d, mesh, materials


def test_hand_off_shares_arc_vertices_and_circle_objects():
    rc, d, mesh, materials = _mesh(v1([rect("r", 10, 10, 40, 40, "Si"), circle("c", 50, 30, 15, "Ge")]))
    assert set(materials) == {"background", "r", "c"} and set(mesh.region_names) == set(materials)
    assert set(mesh.boundary_edges) == {"left", "right", "bottom", "top"}
    rc, d, mesh, materials = _mesh(v1([circle("c", 50, 50, 10, "Si")]))
    circles = [cv for r in d.regions for cv in r.curves if isinstance(cv, Circle)]
    assert len(circles) == 2 and circles[0] is circles[1]
    rc, d, mesh, materials = _mesh(v1([circle("h", 50, 50, 10, None)]))
    assert set(materials) == {"background"} and "outer" in mesh.boundary_edges
    rc, d, mesh, materials = _mesh(v1([rect("a", 10, 10, 10, 10, "Si"), rect("b", 0, 0, 50, 50, "Ge")], finalize="imprint"))
    assert [r.name for r in d.regions].count("b") == 2 and set(mesh.region_names) == {"background", "b"}


def test_hand_off_refuses_a_segment_inside_a_region():
    rc = run(v1([rect("a", 10, 10, 40, 40, "Si"), {"name": "s", "type": "segment", "points": [[20, 20], [30, 35]]}]))
    with pytest.raises(GeometryError, match="segment feature inside a region"):
        rc.to_domain(0.005)


def test_hand_off_rounds_each_coordinate_once():
    rc = run(v1([polygon("t", [(10, 10), (70, 20), (40, 60)], "A"), circle("c", 40, 30, 20, "B")]))
    d, namer, _materials = rc.to_domain(0.005)
    pts, _segs, _regs = d.build(namer)
    intersections = [v for v in rc.vertices if v[0].D or v[1].D]
    assert intersections                                           # the circle meets the triangle off the grid
    for x, y in intersections:
        p = (float(x.approx() / 10 ** 6), float(y.approx() / 10 ** 6))
        assert min(math.hypot(p[0] - q[0], p[1] - q[1]) for q in pts) < 1e-12


# ----------------------------------------------------------------- the runner route of version 1 documents

def test_a_version_1_document_is_meshed_by_the_engine():
    from simcase import Document, build_domain
    from simcase.runner import micrometre_document
    raw = copy.deepcopy(EXAMPLES["soi_strip"])
    raw["geometry"] = from_v02(raw["geometry"])
    comp = raw["geometry"]["components"]["main"]
    comp["boundary_tags"] = [{"tag": "port", "select": {"boundary": {"between": ["background", "exterior"]}}}]
    doc = Document.from_dict(raw)
    assert doc.geometry_model is not None and doc.copy().geometry_model is doc.geometry_model
    canonical = micrometre_document(doc)
    assert canonical.geometry_model is doc.geometry_model
    domain, namer, materials = build_domain(canonical)
    mesh = generate(domain, namer)
    assert materials == {"core": "Si", "background": "SiO2"}
    assert set(mesh.boundary_edges) == {"port"}                   # boundary_tags reach the mesh
    assert set(mesh.region_names) == {"core", "background"}
    del comp["boundary_tags"]
    domain, namer, _materials = build_domain(micrometre_document(Document.from_dict(raw)))
    assert set(generate(domain, namer).boundary_edges) == {"left", "right", "bottom", "top"}


def test_the_0_2_route_is_untouched_for_0_2_documents():
    from simcase import Document, build_domain
    from simcase.runner import micrometre_document
    doc = Document.from_dict(copy.deepcopy(EXAMPLES["soi_strip"]))
    assert doc.geometry_model is None
    domain, namer, materials = build_domain(micrometre_document(doc))
    assert materials == {"core": "Si", "background": "SiO2"} and callable(namer)


# ----------------------------------------------------------------- mesh edges by curve, provenance and selection

def _edge_set(arrays):
    return {tuple(sorted(e)) for a in arrays for e in a}


def test_curve_edges_cover_every_boundary_and_interface_edge():
    rc, d, mesh, _materials = _mesh(v1([rect("core", 10, 10, 40, 30, "Si"), circle("c", 70, 60, 12, "Ge")],
                                       selections={"wall": {"boundary": {"between": ["core", "background"]}},
                                                   "rim": {"boundary": {"between": ["background", "exterior"]}}}))
    by_curve = rc.curve_edges(mesh)
    reported = _edge_set(mesh.boundary_edges.values()) | _edge_set(mesh.interfaces.values())
    assert _edge_set(by_curve.values()) == reported
    assert all(len(e) for e in by_curve.values())
    prov = rc.provenance_edges(mesh)
    assert _edge_set([prov["domain.left"]]) == _edge_set([mesh.boundary_edges["left"]])
    assert _edge_set([rc.selection_edges(mesh, "wall")]) == _edge_set([mesh.interfaces[("background", "core")]])
    assert _edge_set([rc.selection_edges(mesh, "rim")]) == _edge_set(mesh.boundary_edges.values())
    assert _edge_set([prov["c.boundary"]]) == _edge_set([mesh.interfaces[("background", "c")]])
    top = prov["core.top"]
    assert len(top) >= 2 and set(np.unique(top)) <= set(mesh.boundary_nodes.get("outer", [])) | set(np.unique(mesh.interfaces[("background", "core")]))


def test_internal_imprint_curves_have_mesh_edges_the_mesher_does_not_report():
    rc, d, mesh, _materials = _mesh(v1([rect("a", 10, 10, 10, 10, "Si"), rect("b", 0, 0, 50, 50, "Ge")], finalize="imprint"))
    assert ("b", "b") not in mesh.interfaces
    prov = rc.provenance_edges(mesh)
    assert len(prov["a.top"]) >= 1 and len(prov["a.left"]) >= 1
    inner = _edge_set([prov["a.top"], prov["a.bottom"], prov["a.left"], prov["a.right"]])
    assert not inner & (_edge_set(mesh.boundary_edges.values()) | _edge_set(mesh.interfaces.values()))


# ----------------------------------------------------------------- robustness fuzz with circles (not a pre-registered gate)

def _shapely_feature(f, clip):
    if f["type"] == "rect":
        g = box(f["x"], f["y"], f["x"] + f["w"], f["y"] + f["h"])
    elif f["type"] == "circle":
        g = Point(f["cx"], f["cy"]).buffer(f["r"], quad_segs=256)
    else:
        g = Polygon(f["points"])
    return g.intersection(clip)


def test_random_circles_rects_and_polygons_never_break_the_arrangement():
    """Circles make every predicate exercise the quadratic fields. shapely's 256-gon is only
    an approximation here, so the areas are compared within 1e-3 and the point of the check
    is that the engine never raises an internal error, Euler holds and the face counts agree
    (tangencies are improbable with random integer input)."""
    rng = random.Random(42)
    clip = box(0, 0, 100, 100)
    for _case in range(300):
        feats = []
        for i in range(rng.randint(1, 6)):
            if rng.random() < 0.5:
                feats.append(circle(f"f{i}", rng.randint(0, 100), rng.randint(0, 100), rng.randint(5, 40)))
            else:
                f = _random_feature(rng, i)
                if f is not None:
                    feats.append(f)
        rc = check_euler(run(v1(feats)))
        polys = [_shapely_feature(f, clip) for f in feats]
        for i, f in enumerate(feats):
            g = polys[i].difference(unary_union(polys[i + 1:])) if i + 1 < len(polys) else polys[i]
            parts = _parts(g)
            a_ref = sum(p.area for p in parts)
            cells = rc.cells_of_region(f["name"])
            a = rc.area_of_region(f["name"]) / 1e6 if cells else 0.0
            assert abs(a - a_ref) <= 1e-3 * max(a_ref, 1.0), (feats, f["name"], a, a_ref)
            assert len(cells) == len(parts), (feats, f["name"])


# ----------------------------------------------------------------- imprint and segment documents run

def _soi_v1(**component_extra):
    raw = copy.deepcopy(EXAMPLES["soi_strip"])
    raw["geometry"] = from_v02(raw["geometry"])
    raw["geometry"]["components"]["main"].update(component_extra)
    return raw


def _run_v1(raw):
    from simcase import Document, run
    return run(Document.from_dict(raw), verbose=False)


def test_an_imprint_document_loads_runs_and_keeps_the_covered_boundary():
    from simcase import Document, build_domain
    from simcase.runner import micrometre_document
    plain = _soi_v1()
    core = plain["geometry"]["components"]["main"]["features"][0]
    cover = dict(core, name="wide", id="wide", x=core["x"] - 0.1, w=core["w"] + 0.2)        # the same silicon, wider
    raw = _soi_v1(finalize="imprint")
    raw["geometry"]["components"]["main"]["features"] = [core, cover]
    doc = Document.from_dict(raw)
    assert doc.data["geometry"]["shapes"][1]["name"] == "wide" and "finalize" not in doc.data["geometry"]
    assert doc.to_dict()["geometry"]["components"]["main"]["finalize"] == "imprint"
    rc_domain, namer, materials = build_domain(micrometre_document(doc))
    mesh = generate(rc_domain, namer)
    assert set(mesh.region_names) == {"wide", "background"}                   # core is covered, as a region
    from simcase.geometry_engine import evaluate
    rc = evaluate(doc.geometry_model)
    assert [c.region for c in rc.cells].count("wide") == 3                    # left strip, the core footprint, right strip
    rc.to_domain(micrometre_document(doc)["mesh"]["size"])
    rc_domain2, namer2, _m = rc.to_domain(micrometre_document(doc)["mesh"]["size"])
    mesh2 = generate(rc_domain2, namer2)
    assert len(rc.provenance_edges(mesh2)["core.left"]) >= 1                    # the covered boundary is meshed
    merged = _soi_v1()
    merged["geometry"]["components"]["main"]["features"] = [cover]
    a, b = _run_v1(raw), _run_v1(merged)
    assert abs(float(np.asarray(a.neff)[0, 0]) - float(np.asarray(b.neff)[0, 0])) < 2e-3   # same silicon, same mode


def test_a_segment_document_loads_and_runs():
    from simcase import Document
    raw = _soi_v1()
    comp = raw["geometry"]["components"]["main"]
    comp["features"].append({"name": "cut", "type": "segment", "points": [[0, -1.2], [0, 1.2]]})
    doc = Document.from_dict(raw)
    assert [s["name"] for s in doc.data["geometry"]["shapes"]] == ["core"]
    a, b = _run_v1(raw), _run_v1(_soi_v1())
    assert abs(float(np.asarray(a.neff)[0, 0]) - float(np.asarray(b.neff)[0, 0])) < 2e-3
    from simcase.geometry_engine import evaluate
    rc = evaluate(doc.geometry_model)
    assert [c.region for c in rc.cells].count("core") == 2 and len(rc.curves_with("cut.line")) == 3


# ----------------------------------------------------------------- provenance_edges on the shared mesh

def test_meshed_models_of_version_1_documents_carry_provenance_edges():
    from simcase import Document, build_mesh
    from simcase.thermal_regions import build_region_mesh
    model = build_mesh(Document.from_dict(_soi_v1()))
    prov = model.mesh.provenance_edges
    assert prov is not None and set(prov) >= {"core.top", "core.left", "domain.bottom"}
    assert _edge_set([prov["domain.left"]]) == _edge_set([model.tri.boundary_edges["left"]])
    assert set(model.solver_mesh.provenance_edges) == set(prov)
    assert build_mesh(Document.from_dict(copy.deepcopy(EXAMPLES["soi_strip"]))).mesh.provenance_edges is None
    raw = copy.deepcopy(EXAMPLES["thermal_regions"])
    raw["geometry"] = from_v02(raw["geometry"])
    mesh, _materials, _tri = build_region_mesh(Document.from_dict(raw))
    assert set(mesh.provenance_edges) >= {"plate.top", "heater.boundary", "domain.left"}
    assert len(mesh.provenance_edges["heater.boundary"]) >= 16


# ----------------------------------------------------------------- selector coverage

def _three_regions(**extra):
    return v1([rect("sub", 0, 0, 100, 40, "glass"), rect("core", 30, 40, 40, 20, "Si"),
               circle("via", 50, 80, 8, "Cu")], **extra)


def test_boundary_selector_keys():
    doc = _three_regions(selections={
        "core_edge": {"boundary": {"of": "core"}},
        "cu_edge": {"boundary": {"material": "Cu"}},
        "core_sub": {"boundary": {"between": ["core", "sub"]}},
        "sub_out": {"boundary": {"between": ["sub", "exterior"]}},
        "top_named": {"boundary": {"provenance": "core.top"}},
        "via_feat": {"boundary": {"feature": "via"}},
        "both": {"boundary": {"any": ["core_edge", "cu_edge"]}},
        "alias": {"boundary": "core_edge"}})
    rc = check_euler(run(doc))
    sel = {k: v[1] for k, v in rc.selections.items()}
    assert len(sel["core_edge"]) == 4 and len(sel["core_sub"]) == 1 and sel["core_sub"] < sel["core_edge"]
    assert len(sel["cu_edge"]) == 2 and sel["cu_edge"] == sel["via_feat"]
    assert len(sel["sub_out"]) == 3                                     # bottom and the two sides below y = 40
    assert all(rc.curves[i].tag in ("left", "right", "bottom") for i in sel["sub_out"])
    assert sel["top_named"] == frozenset(rc.curves_with("core.top")) and len(sel["top_named"]) == 1
    assert sel["both"] == sel["core_edge"] | sel["cu_edge"] and sel["alias"] == sel["core_edge"]


def test_region_selector_keys_and_errors():
    doc = _three_regions(selections={"metal": {"region": {"material": "Cu"}}, "pair": {"region": {"any": ["core", "metal"]}},
                                     "f": {"region": {"feature": "sub"}}})
    rc = run(doc)
    sel = {k: v[1] for k, v in rc.selections.items()}
    assert sel["metal"] == frozenset(rc.cells_of_region("via")) and sel["f"] == frozenset(rc.cells_of_region("sub"))
    assert sel["pair"] == frozenset(rc.cells_of_region("core")) | sel["metal"]
    with pytest.raises(GeometryError, match="refers to itself"):
        run(_three_regions(selections={"loop": {"boundary": {"any": ["loop"]}}}))
    with pytest.raises(GeometryError, match="not a selection, a region or a feature id"):
        run(_three_regions(selections={"x": {"region": "nothing"}}))
    with pytest.raises(GeometryError, match="selects boundaries, not regions"):
        run(_three_regions(selections={"x": {"region": {"provenance": "core.top"}}}))
    with pytest.raises(GeometryError, match="no feature"):
        run(_three_regions(selections={"x": {"boundary": {"feature": "ghost"}}}))


def test_boundary_tags_first_match_wins_and_only_exterior_curves_take_tags():
    doc = _three_regions(boundary_tags=[{"tag": "floor", "select": {"boundary": {"between": ["sub", "exterior"]}}},
                                        {"tag": "walls", "select": {"boundary": "left"}},
                                        {"tag": "inner", "select": {"boundary": {"of": "core"}}}])
    rc = run(doc)
    tags = {k.tag for k in rc.curves if k.tag}
    assert tags == {"floor", "walls", "right", "top"}                  # the sub's left piece is floor, the rest walls
    assert "inner" not in tags
    assert {rc.curves[i].tag for i in rc.exterior_curves() if "domain.left" in rc.curves[i].provenance} == {"floor", "walls"}


# ----------------------------------------------------------------- the imprint rib example

def test_the_imprint_rib_example_keeps_the_etch_line_and_runs():
    from simcase import Document, build_mesh
    raw = json.loads((ROOT / "examples" / "simcase" / "geometry_v1_imprint_rib.json").read_text(encoding="utf-8"))
    doc = Document.from_dict(raw)
    from simcase.geometry_engine import evaluate
    rc = evaluate(doc.geometry_model)
    assert rc.region_names() == ["slab", "rib", "background"]
    assert len(rc.cells_of_region("rib")) == 2 and len(rc.cells_of_region("slab")) == 2
    assert len(rc.curves_with("slab.top")) == 3                       # left slab top, the imprinted line, right slab top
    inner = [k for k in rc.curves if "slab.top" in k.provenance and k.left is not None and k.right is not None
             and rc.cells[k.left].region == rc.cells[k.right].region == "rib"]
    assert len(inner) == 1
    assert rc.selections["etch_line"][1] == frozenset(rc.curves_with("slab.top"))
    assert len(rc.selections["rib_walls"][1]) == 4                      # bottom, top, and the left and right walls above the slab
    model = build_mesh(doc)
    assert set(model.tri.region_names) == {"slab", "rib", "background"}
    assert len(model.mesh.provenance_edges["slab.top"]) >= 3


# ----------------------------------------------------------------- robustness fuzz with arc paths (not a pre-registered gate)

_ON_CIRCLE = {5: [(5, 0), (3, 4), (0, 5), (-3, 4), (-5, 0), (-3, -4), (0, -5), (3, -4), (4, 3), (-4, 3), (-4, -3), (4, -3)],
              10: [(10, 0), (6, 8), (0, 10), (-6, 8), (-10, 0), (-6, -8), (0, -10), (6, -8), (8, 6), (-8, 6), (-8, -6), (8, -6)],
              13: [(13, 0), (5, 12), (12, 5), (0, 13), (-5, 12), (-12, 5), (-13, 0), (-5, -12), (-12, -5), (0, -13), (5, -12), (12, -5)]}


def _random_path(rng, name):
    """A simple closed path on integer points of one circle: chords and counter-clockwise arcs."""
    r = rng.choice(list(_ON_CIRCLE))
    cx, cy = rng.randint(20, 80), rng.randint(20, 80)
    offs = sorted(_ON_CIRCLE[r], key=lambda o: math.atan2(o[1], o[0]))
    idx = sorted(rng.sample(range(len(offs)), rng.randint(3, 6)))
    pts = [(cx + offs[i][0], cy + offs[i][1]) for i in idx]
    segs = []
    for j in range(len(pts)):
        q = pts[(j + 1) % len(pts)]
        segs.append({"arc": {"center": [cx, cy], "to": list(q), "ccw": True}} if rng.random() < 0.5 else {"line": list(q)})
    return {"name": name, "type": "path", "start": list(pts[0]), "segments": segs, "material": "m"}, (cx, cy, r)


def _shapely_path(f, n=720):
    cur = tuple(f["start"])
    coords = [cur]
    for s in f["segments"]:
        if "line" in s:
            cur = tuple(s["line"])
            coords.append(cur)
            continue
        (cx, cy), to = s["arc"]["center"], tuple(s["arc"]["to"])
        r = math.hypot(cur[0] - cx, cur[1] - cy)
        a0, a1 = math.atan2(cur[1] - cy, cur[0] - cx), math.atan2(to[1] - cy, to[0] - cx)
        d = (a1 - a0) % (2 * math.pi)
        m = max(2, int(n * d / (2 * math.pi)))
        coords.extend((cx + r * math.cos(a0 + d * i / m), cy + r * math.sin(a0 + d * i / m)) for i in range(1, m))
        coords.append(to)
        cur = to
    return Polygon(coords)


def _circle_extreme_touch(circles, feats, dom):
    """True when an axis-extreme point of a circle lies exactly on another feature's edge, the domain
    or another circle: there the exact engine keeps a touch that a polygon approximation misses."""
    edges = [e for f in feats if f["type"] in ("rect", "polygon") for e in _feature_edges(f, dom)]
    d = [((dom[0], dom[2]), (dom[1], dom[2])), ((dom[1], dom[2]), (dom[1], dom[3])),
         ((dom[1], dom[3]), (dom[0], dom[3])), ((dom[0], dom[3]), (dom[0], dom[2]))]
    for cx, cy, r in circles:
        for v in ((cx + r, cy), (cx - r, cy), (cx, cy + r), (cx, cy - r)):
            for p, q in edges + d:
                if (q[0] - p[0]) * (v[1] - p[1]) - (q[1] - p[1]) * (v[0] - p[0]) == 0 and \
                        min(p[0], q[0]) <= v[0] <= max(p[0], q[0]) and min(p[1], q[1]) <= v[1] <= max(p[1], q[1]):
                    return True
            for ox, oy, orad in circles:
                if (ox, oy, orad) != (cx, cy, r) and (v[0] - ox) ** 2 + (v[1] - oy) ** 2 == orad * orad:
                    return True
    return False


def test_random_arc_paths_never_break_the_arrangement():
    """Arc paths exercise arc-arc and arc-line intersections and the cusp and tangent rules.
    shapely's 720-gon is an approximation, so areas are compared within 2e-3; cases where a
    circle's extreme point touches another edge exactly are skipped, since there the exact
    engine rightly keeps a touch the polygon misses (a face pinched at a point)."""
    rng = random.Random(7)
    clip = box(0, 0, 100, 100)
    done = skipped = 0
    while done < 200:
        feats, circles = [], []
        for i in range(rng.randint(1, 4)):
            u = rng.random()
            if u < 0.6:
                f, c = _random_path(rng, f"p{i}")
                feats.append(f)
                circles.append(c)
            elif u < 0.8:
                f = circle(f"c{i}", rng.randint(10, 90), rng.randint(10, 90), rng.randint(5, 30))
                feats.append(f)
                circles.append((f["cx"], f["cy"], f["r"]))
            else:
                f = _random_feature(rng, i)
                if f is not None:
                    feats.append(f)
        if _circle_extreme_touch(circles, feats, (0, 100, 0, 100)) or len(set(circles)) < len(circles):
            skipped += 1                   # two features on one circle: their polygon approximations overlap in slivers
            continue
        rc = check_euler(run(v1(feats)))
        polys = [(_shapely_path(f) if f["type"] == "path" else _shapely_feature(f, clip)).intersection(clip)
                 for f in feats]
        for i, f in enumerate(feats):
            g = polys[i].difference(unary_union(polys[i + 1:])) if i + 1 < len(polys) else polys[i]
            parts = [q for q in _parts(g) if q.area > 1e-9]
            a_ref = sum(p.area for p in parts)
            cells = rc.cells_of_region(f["name"])
            a = rc.area_of_region(f["name"]) / 1e6 if cells else 0.0
            assert abs(a - a_ref) <= 2e-3 * max(a_ref, 1.0), (feats, f["name"], a, a_ref)
            assert len(cells) == len(parts), (feats, f["name"])
        done += 1
    print(f"arc-path fuzz: {done} cases agree, {skipped} exact-touch cases skipped")


# ----------------------------------------------------------------- the geometry command

def test_the_geometry_command_prints_the_complex(capsys, tmp_path):
    from simcase.cli import main
    path = ROOT / "examples" / "simcase" / "geometry_v1_imprint_rib.json"
    assert main(["geometry", str(path)]) == 0
    out = capsys.readouterr().out
    assert "component 'xs' (2d)" in out and "um" in out
    assert out.count("region 'rib'") == 2 and "slab.top" in out and "selection 'etch_line': 3 boundary entries" in out
    assert "tag left" in out and "material Si" in out
    old = tmp_path / "old.json"
    old.write_text(json.dumps(EXAMPLES["soi_strip"]), encoding="utf-8")
    assert main(["geometry", str(old)]) == 2
    assert "version 1 block" in capsys.readouterr().err


# ----------------------------------------------------------------- a tangent point off the grid stays exact

def test_a_line_tangent_to_a_circle_meets_it_at_the_exact_rational_point():
    # the edge (1, 3) -> (-5, -5) is tangent to the unit circle at (-4/5, 3/5): the parameter
    # -3/5 is not a dyadic rational, so a floating-point division would miss the point
    rc = check_euler(run(v1([polygon("t", [(1, 3), (-5, -5), (5, -5)], "A"), circle("c", 0, 0, 1, "B")],
                              dom=(-10, 10, -10, 10), units="pm")))
    tangent = [v for v in rc.vertices if v[0].D == 0 and v[1].D == 0
               and v[0].a == Fraction(-4, 5) and v[1].a == Fraction(3, 5)]
    assert len(tangent) == 1
    assert len(rc.curves) == 10 and len(rc.curves_with("t.e1")) == 2
    assert close(areas_nm2(rc)["c"] * 1e6, math.pi) and areas_nm2(rc)["t"] * 1e6 == pytest.approx(40 - math.pi, rel=1e-12)


# ----------------------------------------------------------------- review findings of 2026-11-04 (regressions)

@pytest.mark.parametrize("order", [0, 1])
def test_a_hole_pinched_at_its_leftmost_vertex_is_a_hole_in_either_feature_order(order):
    a = polygon("a", [(10, 50), (30, 30), (30, 45)], "A")
    b = polygon("b", [(10, 50), (30, 55), (30, 70)], "B")
    rc = check_euler(run(v1([a, b] if order == 0 else [b, a])))
    assert areas_nm2(rc) == {"a": 150.0, "b": 150.0, "background": 9700.0} and len(rc.curves) == 10
    bg = rc.cells[rc.cells_of_region("background")[0]]
    assert len(bg.loops) == 2 and len(bg.loops[1]) == 6                     # one pinched hole of both triangles
    rc = check_euler(run(v1([rect("a", 10, 10, 20, 20, "A"), polygon("b", [(10, 10), (30, 5), (30, 8)], "B")])))
    assert areas_nm2(rc) == {"a": 400.0, "b": 30.0, "background": 9570.0}
    seg = {"name": "s", "type": "segment", "points": [[10, 10], [30, 5]]}
    for feats in ([rect("a", 10, 10, 20, 20, "A"), seg], [seg, rect("a", 10, 10, 20, 20, "A")]):
        rc = check_euler(run(v1(feats)))
        assert areas_nm2(rc) == {"a": 400.0, "background": 9600.0} and len(rc.curves) == 9


def test_a_segment_on_the_shared_edge_of_one_region_is_kept_symmetrically():
    seg = {"name": "s", "type": "segment", "points": [[40, 10], [40, 30]]}
    left = [rect("a", 10, 10, 30, 20, "Si", region="core"), seg, rect("b", 40, 10, 30, 20, "Si", region="core")]
    right = [rect("a", 40, 10, 30, 20, "Si", region="core"), seg, rect("b", 10, 10, 30, 20, "Si", region="core")]
    for feats in (left, right):
        rc = check_euler(run(v1(feats)))
        assert len(rc.curves_with("s.line")) == 1 and len(rc.cells_of_region("core")) == 2
    covered = [seg, rect("a", 10, 10, 30, 20, "Si", region="core"), rect("b", 40, 10, 30, 20, "Si", region="core")]
    rc = check_euler(run(v1(covered)))
    assert not rc.curves_with("s.line") and len(rc.cells_of_region("core")) == 1    # later features cover it
    rc = check_euler(run(v1([{"name": "s", "type": "segment", "points": [[20, 20], [30, 35]]},
                             rect("a", 10, 10, 40, 40, "Si")], finalize="imprint")))
    assert not rc.curves_with("s.line")                                           # covered under imprint too
    rc.to_domain(0.005)


def test_merged_regions_list_every_owning_feature():
    doc = v1([rect("a", 10, 10, 30, 20, "Si", region="core", mesh_size=1), rect("b", 40, 10, 30, 20, "Si", region="core", mesh_size=7)],
             selections={"fa": {"region": {"feature": "a"}}, "fb": {"region": "b"}})
    rc = check_euler(run(doc))
    (cell,) = [rc.cells[i] for i in rc.cells_of_region("core")]
    assert cell.feature == "a" and cell.feature_indices == frozenset({0, 1}) and cell.mesh_size == 1000
    assert rc.selections["fa"][1] == rc.selections["fb"][1] == frozenset({cell.index})
    rc2 = check_euler(run(v1([rect("b", 40, 10, 30, 20, "Si", region="core", mesh_size=7),
                              rect("a", 10, 10, 30, 20, "Si", region="core", mesh_size=1)])))
    (cell2,) = [rc2.cells[i] for i in rc2.cells_of_region("core")]
    assert cell2.feature == "b" and cell2.feature_indices == frozenset({0, 1}) and cell2.mesh_size == 1000
    assert rc.region_names() == rc2.region_names() == ["core", "background"]


@pytest.mark.parametrize("size_nm", [5.0, 4.0, 3.0, 2.5])
def test_whole_circle_edges_are_read_back_at_any_vertex_count(size_nm):
    rc, d, mesh, _materials = _mesh(v1([circle("c", 50, 50, 10, "Si")]), size_nm=size_nm)
    by_curve = rc.curve_edges(mesh)
    circle_edges = _edge_set([by_curve[k.index] for k in rc.curves if k.kind == "circle"])
    assert circle_edges == _edge_set([mesh.interfaces[("background", "c")]])
    assert all(len(by_curve[k.index]) >= 1 for k in rc.curves if k.kind == "circle")
    rc, d, mesh, _materials = _mesh(v1([rect("a", 10, 10, 40, 40, "Si", region="core"), rect("b", 50, 10, 40, 40, "Si", region="core"),
                                        circle("c", 50, 30, 12, "Ge")]), size_nm=size_nm)
    prov = rc.provenance_edges(mesh)
    assert _edge_set([prov["c.boundary"]]) == _edge_set([mesh.interfaces[("c", "core")]])


# ----------------------------------------------------------------- integration review findings of 2026-11-04

def _imprint_regions_doc():
    raw = copy.deepcopy(EXAMPLES["thermal_regions"])
    raw["geometry"] = from_v02(raw["geometry"])
    comp = raw["geometry"]["components"]["main"]
    comp["finalize"] = "imprint"
    comp["features"].append({"name": "cut", "type": "segment", "points": [[0, 10], [40, 10]]})
    return raw


def test_mesh_limits_take_the_engine_route_for_version_1_documents():
    from simcase import Document, check_mesh_limits, run
    from simcase.mesh_limits import _MeshLimits
    from simcase.thermal_regions import build_region_mesh
    doc = Document.from_dict(_imprint_regions_doc())
    free, _m, _t = build_region_mesh(doc)
    limited, _m, _t = build_region_mesh(doc, _MeshLimits(max_input_vertices=10 ** 6))
    assert free.num_nodes == limited.num_nodes and limited.provenance_edges is not None
    assert len(limited.provenance_edges["cut.line"]) >= 1
    count = check_mesh_limits(doc, max_input_vertices=10 ** 6)
    from simcase.geometry import _domain_from_model
    from simcase.runner import micrometre_document
    assert count == _domain_from_model(micrometre_document(doc))[3]
    with pytest.raises(Exception, match="input_vertices"):
        check_mesh_limits(doc, max_input_vertices=3)
    result = run(doc, verbose=False, max_input_vertices=10 ** 6)
    assert len(result.temperature_k) == free.num_nodes


def test_an_em_document_whose_tags_are_not_the_four_sides_is_refused_before_the_solver():
    from simcase import Document, DocumentError, run
    tagged = _soi_v1(boundary_tags=[{"tag": "port", "select": {"boundary": {"between": ["background", "exterior"]}}}])
    with pytest.raises(DocumentError, match="four domain sides"):
        run(Document.from_dict(tagged), verbose=False)


def test_the_engine_sliver_note_reaches_the_document():
    from simcase import Document, build_mesh
    raw = _soi_v1()
    comp = raw["geometry"]["components"]["main"]
    comp["domain"] = {"xmin": -500, "xmax": 500, "ymin": -500, "ymax": 500}
    core = comp["features"][0]
    core.update({"x": 100, "y": 100, "w": 0.5, "h": 0.005})
    comp["features"].append(dict(core, name="cover", id="cover", x=100.0001, w=0.4999))
    raw["mesh"] = {"size": 100}
    doc = Document.from_dict(raw)
    from simcase import DocumentError
    with pytest.raises(DocumentError, match="four domain sides"):      # the gap the sliver leaves is 'outer'
        build_mesh(doc)
    assert any(n.startswith("geometry.features: a piece of 'core'") for n in doc.notes)


def test_the_geometry_command_shows_what_the_document_route_refuses(capsys, tmp_path):
    from simcase.cli import main
    raw = _soi_v1()
    raw["geometry"]["components"]["main"]["features"].append(circle("hole", 0, 0.9, 0.1, None))
    raw["geometry"]["components"]["plan"] = {"dimension": "2d", "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1},
                                             "background": {"material": "SiO2"}, "features": []}
    path = tmp_path / "void.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert main(["geometry", str(path), "-c", "main"]) == 0
    out = capsys.readouterr().out
    assert "material void" in out and "tag outer" in out
    assert main(["geometry", str(path)]) == 2 and "name a component" in capsys.readouterr().err


def test_curve_edges_refuse_a_mesh_from_another_hand_off():
    rc = run(v1([rect("r", 10, 10, 40, 40, "Si"), circle("c", 50, 30, 15, "Ge")]))
    domain, namer, _m = rc.to_domain(0.005)
    mesh = generate(domain, namer)
    rc.to_domain(0.002)
    with pytest.raises(GeometryError, match="last to_domain"):
        rc.curve_edges(mesh)


def test_a_selection_may_not_share_a_tag_name_and_a_dangling_segment_is_refused_at_load():
    from simcase import Document, DocumentError
    with pytest.raises(GeometryError, match="share a mesh tag"):
        run(v1([rect("a", 10, 10, 30, 20, "Si")], boundary_tags=[{"tag": "wall", "select": {"boundary": "left"}}],
               selections={"wall": {"boundary": "right"}}))
    raw = _soi_v1()
    raw["geometry"]["components"]["main"]["features"].append({"name": "cut", "type": "segment", "points": [[0, -1.2], [0, 0]]})
    with pytest.raises(DocumentError, match="segment feature inside a region"):
        Document.from_dict(raw)


# ----------------------------------------------------------------- circle polygons keep clear of neighbouring features

def test_a_circle_polygon_gets_enough_vertices_to_clear_an_inner_corner():
    # size 5 nm gives the 0.2 rule n = 25 with a chord sagitta of 0.079 nm; the rect corner sits
    # 0.03 nm inside the circle line, so the chords would cut across it
    rc, d, mesh, _materials = _mesh(v1([circle("c", 50, 50, 10, "Si"), rect("r", 42.95, 42.95, 14.1, 14.1, "Ge")]))
    circles = [cv for r in d.regions for cv in r.curves if isinstance(cv, Circle)]
    assert circles and circles[0].n > 25
    areas = {name: 0.0 for name in mesh.region_names}
    tri = mesh.nodes[mesh.triangles]
    a = 0.5 * np.abs((tri[:, 1, 0] - tri[:, 0, 0]) * (tri[:, 2, 1] - tri[:, 0, 1]) - (tri[:, 2, 0] - tri[:, 0, 0]) * (tri[:, 1, 1] - tri[:, 0, 1]))
    for i, name in enumerate(mesh.region_names):
        areas[name] = float(a[mesh.regions == i].sum()) * 1e6          # um^2 -> nm^2
    assert abs(areas["r"] - 14.1 ** 2) < 1e-6 and abs(areas["c"] - (math.pi * 100 - 14.1 ** 2)) < 0.01 * math.pi * 100


def test_a_whole_circle_that_cannot_clear_a_neighbour_is_refused(monkeypatch):
    from simcase import geometry_engine
    monkeypatch.setattr(geometry_engine, "MAX_CIRCLE_VERTICES", 30)
    with pytest.raises(GeometryError, match="keep its chords clear"):
        _mesh(v1([circle("c", 50, 50, 10, "Si"), rect("r", 42.95, 42.95, 14.1, 14.1, "Ge")]))
    _mesh(v1([circle("c", 50, 50, 10, "Si"), rect("r", 45, 45, 10, 10, "Ge")]))              # corner 2.9 nm inside


# ----------------------------------------------------------------- third review (2026-11-04)

def test_read_back_tolerates_a_vertex_the_mesher_snapped_away():
    feats = [polygon("p", [(500, 500), (500.1, 500), (500.1, 500.1), (500, 500.1), (500, 500.00002)], "Si")]
    rc = run(v1(feats, dom=(0, 1000, 0, 1000), units="um"))
    d, namer, _m = rc.to_domain(50.0)
    mesh = generate(d, namer)
    prov = rc.provenance_edges(mesh)                                  # the 20 pm edge was snapped by meshine
    assert len(prov["p.e2"]) >= 1 and len(prov["p.e1"]) >= 1


def test_a_whole_circle_ignores_the_dropped_arcs_of_a_cut_circle():
    rc, d, mesh, _m = _mesh(v1([circle("D", 75, 50, 10, "Y"), rect("E", 20, 20, 60, 60, "Y"), circle("C", 50, 50, 20, "X")]))
    assert {cv.n for r in d.regions for cv in r.curves if isinstance(cv, Circle)}       # C is still a Circle
    assert set(mesh.region_names) == {"background", "D", "E", "C"}


def test_a_segment_document_evaluates_once_and_reuses_the_complex():
    from simcase import Document, build_mesh
    raw = _soi_v1()
    raw["geometry"]["components"]["main"]["features"].append({"name": "cut", "type": "segment", "points": [[0, -1.2], [0, 1.2]]})
    doc = Document.from_dict(raw)
    assert doc.geometry_complex is not None and doc.copy().geometry_complex is doc.geometry_complex
    model = build_mesh(doc)
    from simcase.runner import micrometre_document
    assert micrometre_document(doc).geometry_complex is doc.geometry_complex
    assert "cut.line" in model.mesh.provenance_edges
