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


def _compare_with_shapely(doc, rc, holes=True):
    ref = _shapely_regions(doc)
    problems = []
    for name, g in ref.items():
        ps = _parts(g)
        a_ref = sum(p.area for p in ps)
        cells = rc.cells_of_region(name)
        a = rc.area_of_region(name) / 1e6 if cells else 0.0
        if not close(a, a_ref):
            problems.append(f"{name}: area {a!r} vs shapely {a_ref!r}")
        if len(cells) != len(ps):
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
    # touching cases are outside G2-1: areas and face counts still agree; only shapely's
    # hole-touching-shell representation differs from the engine's pinched loop
    hole_differences = 0
    for feats in touching[:300]:
        doc = v1(feats)
        rc = check_euler(run(doc))
        assert not _compare_with_shapely(doc, rc, holes=False), feats
        hole_differences += bool(_compare_with_shapely(doc, rc))
    print(f"G2-1: {len(accepted)} general-position cases agree; {min(len(touching), 300)} touching cases agree "
          f"in area and face count, {hole_differences} differ only in hole representation")


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
