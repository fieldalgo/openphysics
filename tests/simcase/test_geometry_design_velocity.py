# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Design velocity V = dx/dp of the geometry engine (stage 4 prototype).

D1-D8 are the checks pre-registered before the implementation; their tolerances are
fixed there and are not loosened here.
"""

from __future__ import annotations

import copy
import json
import math
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from physmat.units import is_quantity_text
from simcase.geometry_document import GeometryError, parse
from simcase.geometry_engine import Q2, evaluate
from simcase.geometry_velocity import TopologyChange, design_velocity, exact_complex, signature

ROOT = Path(__file__).resolve().parents[2]
UM = 10 ** 6                                             # pm per micrometre


def doc(features, params, domain=(0, 10, 0, 10), dimension="2d", **extra):
    """A format 0.3 document: one component in micrometres, length parameters as quantity strings."""
    comp = {"dimension": dimension, "length_unit": "um", **({"depth": None} if dimension == "2d" else {}),
            "domain": dict(zip(("xmin", "xmax", "ymin", "ymax"), domain)),
            "background": {"material": "air"}, "features": features, **extra}
    return {"openphysics": "0.3", "geometry": {"version": 1, "parameters": params, "components": {"xs": comp}}}


def um(x) -> str:
    """A length parameter value in micrometres."""
    return f"{x!r} um"


def rel(a, b):
    return abs(a - b) / max(abs(b), 1e-300)


def vertex_at(rc, x_pm, y_pm):
    for v, (x, y) in enumerate(rc.vertices):
        if x == Q2(x_pm) and y == Q2(y_pm):
            return v
    raise AssertionError(f"no vertex at ({x_pm}, {y_pm})")


def exact_v(dv, v):
    vx, vy = dv.vertices[v]
    assert vx.D == 0 and vy.D == 0
    return (vx.a, vy.a)


# ---------------------------------------------------------------- D1 closed forms

#: the height parameter is "t": "h" is a unit symbol (the hour), which format 0.3 refuses as a parameter name
RECT = doc([{"name": "core", "type": "rect", "x": 2, "y": 3, "w": "w", "h": "t", "material": "Si"}],
           {"w": {"value": "4 um"}, "t": {"value": "2.5 um"}})


def test_d1_rect_area_and_perimeter():
    dw = design_velocity(RECT, "w")
    dh = design_velocity(RECT, "t")
    assert rel(dw.area_derivative("core"), 2.5 * UM) <= 1e-12          # dA/dw = h (pm^2 per pm)
    assert rel(dh.area_derivative("core"), 4 * UM) <= 1e-12            # dA/dt = w
    assert rel(dw.perimeter_derivative("core"), 2.0) <= 1e-12          # dP/dw = 2
    assert rel(dh.perimeter_derivative("core"), 2.0) <= 1e-12
    rc = dw.complex
    assert exact_v(dw, vertex_at(rc, 6 * UM, 3 * UM)) == (1, 0)
    assert exact_v(dw, vertex_at(rc, 6 * UM, Fraction(55, 10) * UM)) == (1, 0)
    assert exact_v(dw, vertex_at(rc, 2 * UM, 3 * UM)) == (0, 0)
    assert exact_v(dh, vertex_at(rc, 6 * UM, Fraction(55, 10) * UM)) == (0, 1)
    # the background loses what the core gains
    assert rel(dw.area_derivative("background"), -2.5 * UM) <= 1e-12


def test_d1_trapezoid_corners():
    d = doc([{"name": "t", "type": "trapezoid", "cx": "c", "y": 2, "w": "w", "h": 3, "material": "Si"}],
            {"c": {"value": "5 um"}, "w": {"value": "4 um"}})
    dw = design_velocity(d, "w")
    rc = dw.complex
    for x, y, want in ((3, 2, (Fraction(-1, 2), 0)), (7, 2, (Fraction(1, 2), 0)),
                       (7, 5, (Fraction(1, 2), 0)), (3, 5, (Fraction(-1, 2), 0))):     # w_top defaults to w
        assert exact_v(dw, vertex_at(rc, x * UM, y * UM)) == want
    dc = design_velocity(d, "c")
    assert all(exact_v(dc, vertex_at(rc, x * UM, y * UM)) == (1, 0) for x, y in ((3, 2), (7, 2), (7, 5), (3, 5)))
    top = copy.deepcopy(d)
    top["geometry"]["components"]["xs"]["features"][0]["w_top"] = 2
    dt = design_velocity(top, "w")
    assert exact_v(dt, vertex_at(dt.complex, 4 * UM, 5 * UM)) == (0, 0)
    assert exact_v(dt, vertex_at(dt.complex, 7 * UM, 2 * UM)) == (Fraction(1, 2), 0)
    # area of a trapezoid (w + w_top) h / 2: dA/dw = h / 2
    assert rel(dt.area_derivative("t"), 1.5 * UM) <= 1e-12


def test_d1_polygon_with_expressions():
    d = doc([{"name": "tri", "type": "polygon", "points": [[1, 1], ["1 + a", 1], ["1 + a", "1 + a/2"]],
              "material": "Si"}], {"a": {"value": "6 um"}})
    dv = design_velocity(d, "a")
    rc = dv.complex
    assert exact_v(dv, vertex_at(rc, 7 * UM, 1 * UM)) == (1, 0)
    assert exact_v(dv, vertex_at(rc, 7 * UM, 4 * UM)) == (1, Fraction(1, 2))
    assert rel(dv.area_derivative("tri"), 6 * UM / 2) <= 1e-12          # A = a^2 / 4


def test_d1_circle_area_and_perimeter():
    d = doc([{"name": "c", "type": "circle", "cx": "cx", "cy": 5, "r": "r", "material": "Si"}],
            {"r": {"value": "2 um"}, "cx": {"value": "5 um"}})
    dr = design_velocity(d, "r")
    assert rel(dr.area_derivative("c"), 2 * math.pi * 2 * UM) <= 1e-12   # dA/dr = 2 pi r
    assert rel(dr.perimeter_derivative("c"), 2 * math.pi) <= 1e-12       # dP/dr = 2 pi
    k = next(k for k in dr.complex.curves if k.kind == "circle")
    assert dr.curves[k.index].vc == (0, 0) and dr.curves[k.index].dr == Q2(1)
    dc = design_velocity(d, "cx")
    assert abs(dc.area_derivative("c")) <= 1e-12 * 2 * UM                # a translation keeps the area
    assert abs(dc.perimeter_derivative("c")) <= 1e-12
    assert all(exact_v(dc, v) == (1, 0) for k in dc.complex.curves if k.kind == "circle" for v in (k.a, k.b))


# ---------------------------------------------------------------- D2 derived points

def test_d2_line_line_intersection():
    # the hypotenuse y = H x / a of a triangle crosses the top (y = 5) and left (x = 1) sides of a rect
    d = doc([{"name": "tri", "type": "polygon", "points": [[0, 0], ["a", 0], ["a", 8]], "material": "Si"},
             {"name": "box", "type": "rect", "x": 1, "y": 0.5, "w": 6, "h": 4.5, "material": "Ge"}],
            {"a": {"value": "8 um"}}, domain=(0, 10, 0, 10))
    dv = design_velocity(d, "a")
    rc = dv.complex
    # top: x = 5 a / 8 -> dx/da = 5/8; left: y = 8 / a -> dy/da = -8 / a^2 = -1/8
    assert exact_v(dv, vertex_at(rc, 5 * UM, 5 * UM)) == (Fraction(5, 8), 0)
    assert exact_v(dv, vertex_at(rc, 1 * UM, 1 * UM)) == (0, Fraction(-1, 8))


def test_d2_line_circle_intersection():
    # the top y = 6 of a rect cuts the circle (5, 5), r: x = 5 +- sqrt(r^2 - 1) -> dx/dr = +- r / sqrt(r^2 - 1)
    d = doc([{"name": "c", "type": "circle", "cx": 5, "cy": 5, "r": "r", "material": "Si"},
             {"name": "lid", "type": "rect", "x": 0, "y": 6, "w": 10, "h": 4, "material": "Ge"}],
            {"r": {"value": "2 um"}})
    dv = design_velocity(d, "r")
    want = 2 / math.sqrt(3)
    found = 0
    for v, (x, y) in enumerate(dv.complex.vertices):
        if y == Q2(6 * UM) and v in dv.vertices and 0 < float(x) < 10 * UM:
            vx, vy = dv.vertex_velocity(v)
            assert rel(abs(vx), want) <= 1e-12 and vy == 0.0
            assert math.copysign(1, vx) == math.copysign(1, float(x) - 5 * UM)
            found += 1
    assert found == 2


# ---------------------------------------------------------------- D3 exact finite differences

def _vertex_by_position(rc, S, approx_pm, tol_pm=0.01):
    best = min(range(len(rc.vertices)), key=lambda v: math.hypot(float(rc.vertices[v][0]) / S - approx_pm[0],
                                                                 float(rc.vertices[v][1]) / S - approx_pm[1]))
    x, y = rc.vertices[best]
    assert math.hypot(float(x) / S - approx_pm[0], float(y) / S - approx_pm[1]) < tol_pm
    return best


def _exact_fd(d, param, v_pos, h_um):
    plus, Sp = exact_complex(d, param, Fraction(h_um) * UM)          # the offset in exact pm
    minus, Sm = exact_complex(d, param, -Fraction(h_um) * UM)
    vp = plus.vertices[_vertex_by_position(plus, Sp, v_pos, tol_pm=abs(h_um) * UM * 2 + 0.01)]
    vm = minus.vertices[_vertex_by_position(minus, Sm, v_pos, tol_pm=abs(h_um) * UM * 2 + 0.01)]
    h = Fraction(h_um) * UM
    return tuple((Fraction(vp[i].approx(200)) / Sp - Fraction(vm[i].approx(200)) / Sm) / (2 * h) for i in (0, 1))


D2_DOC = doc([{"name": "tri", "type": "polygon", "points": [[0, 0], ["a", 0], ["a", 8]], "material": "Si"},
              {"name": "box", "type": "rect", "x": 1, "y": 0.5, "w": 6, "h": 4.5, "material": "Ge"}],
             {"a": {"value": "8 um"}})


def test_d3_exact_fd_linear_is_exact():
    dv = design_velocity(D2_DOC, "a")
    v = vertex_at(dv.complex, 5 * UM, 5 * UM)
    for h in (Fraction(1, 2), Fraction(1, 64), Fraction(1, 4096)):
        assert _exact_fd(D2_DOC, "a", (5 * UM, 5 * UM), h) == exact_v(dv, v)


def test_d3_exact_fd_nonlinear_order():
    dv = design_velocity(D2_DOC, "a")
    want = exact_v(dv, vertex_at(dv.complex, 1 * UM, 1 * UM))[1]         # dy/da = -1/8
    errors = []
    hs = [Fraction(1, 2 ** k) for k in range(2, 18, 2)]
    for h in hs:
        fd = _exact_fd(D2_DOC, "a", (1 * UM, 1 * UM), h)
        assert fd[0] == 0
        errors.append(abs(float(fd[1] - want)) / abs(float(want)))
    orders = [math.log(errors[i] / errors[i + 1]) / math.log(float(hs[i] / hs[i + 1])) for i in range(len(hs) - 1)]
    assert min(orders) >= 1.9, (errors, orders)
    assert errors[-1] <= 1e-9, errors


def test_d3_exact_fd_ratio_expression():
    # x = a * (a / L): nonlinear through a ratio sub-expression; dx/da = 2 a / L
    d = doc([{"name": "r", "type": "rect", "x": 1, "y": 1, "w": "a * (a / L)", "h": 2, "material": "Si"}],
            {"a": {"value": "4 um"}, "L": {"value": "8 um"}})
    dv = design_velocity(d, "a")
    v = vertex_at(dv.complex, 3 * UM, 1 * UM)
    assert exact_v(dv, v) == (1, 0)
    errors = []
    hs = [Fraction(1, 2 ** k) for k in (3, 5, 7)]
    for h in hs:
        fd = _exact_fd(d, "a", (3 * UM, 1 * UM), h)
        errors.append(abs(float(fd[0]) - 1.0))
    # central differences of a quadratic are exact
    assert errors == [0.0, 0.0, 0.0]


# ---------------------------------------------------------------- D4 finite differences on the rounded document

def test_d4_rounded_area_fd_study():
    # a circle whose top is cut off by a later rect: the remaining area is nonlinear in r
    base = doc([{"name": "c", "type": "circle", "cx": 5, "cy": 5, "r": "r", "material": "Si"},
                {"name": "lid", "type": "rect", "x": 0, "y": 6, "w": 10, "h": 4, "material": "Ge"}],
               {"r": {"value": "3 um"}})
    dv = design_velocity(base, "r")
    want = dv.area_derivative("c")
    # closed form: A(r) = pi r^2 - segment above y = 6 (distance 1): dA/dr = 2 r (pi - acos(1 / r))
    r = 3.0
    closed = 2 * r * UM * (math.pi - math.acos(1 / r))
    assert rel(want, closed) <= 1e-12
    study = {}
    for h in (1.0, 0.1, 0.01, 0.001):
        areas = []
        for s in (1, -1):
            d = copy.deepcopy(base)
            d["geometry"]["parameters"]["r"]["value"] = um(r + s * h)
            areas.append(evaluate(parse(d)).area_of_region("c"))
        study[h] = rel((areas[0] - areas[1]) / (2 * h * UM), want)
    assert min(study.values()) <= 1e-6, study


# ---------------------------------------------------------------- D5 topology changes

def _refused(d, p):
    with pytest.raises(TopologyChange) as exc:
        design_velocity(d, p)
    return exc.value


def test_d5a_touching_rects_refused():
    d = doc([{"name": "a", "type": "rect", "x": 2, "y": 3, "w": "w", "h": 2, "material": "Si"},
             {"name": "b", "type": "rect", "x": 6, "y": 3, "w": 2, "h": 2, "material": "Ge"}], {"w": {"value": "4 um"}})
    e = _refused(d, "w")
    assert {"a", "b"} <= set(e.features) and "a" in str(e) and "b" in str(e)


def test_d5b_corner_leaves_domain_side():
    d = doc([{"name": "a", "type": "rect", "x": "x0", "y": 3, "w": 2, "h": 2, "material": "Si"}], {"x0": {"value": "0 um"}})
    e = _refused(d, "x0")
    assert {"a", "domain"} <= set(e.features)


def test_d5c_tangent_circles_refused():
    d = doc([{"name": "c1", "type": "circle", "cx": 3, "cy": 5, "r": 2, "material": "Si"},
             {"name": "c2", "type": "circle", "cx": 7, "cy": 5, "r": "r", "material": "Ge"}], {"r": {"value": "2 um"}})
    e = _refused(d, "r")
    assert {"c1", "c2"} <= set(e.features)


def test_d5d_three_concurrent_curves_broken():
    # a segment through the corner (5, 5) of a rect; moving its far end breaks the concurrency
    d = doc([{"name": "a", "type": "rect", "x": 2, "y": 2, "w": 3, "h": 3, "material": "Si"},
             {"name": "cut", "type": "segment", "points": [[3, 3], [8, "q"]]}], {"q": {"value": "8 um"}})
    e = _refused(d, "q")
    assert {"a", "cut"} <= set(e.features)


def test_d5e_linked_touch_is_not_refused():
    d = doc([{"name": "a", "type": "rect", "x": 2, "y": 3, "w": "w", "h": 2, "material": "Si"},
             {"name": "b", "type": "rect", "x": "2 + w", "y": 3, "w": 2, "h": 2, "material": "Ge"}],
            {"w": {"value": "4 um"}})
    dv = design_velocity(d, "w")
    assert rel(dv.area_derivative("a"), 2 * UM) <= 1e-12
    assert abs(dv.area_derivative("b")) <= 1e-12 * UM
    assert rel(dv.area_derivative("background"), -2 * UM) <= 1e-12


def test_d5_far_parameter_is_zero():
    d = doc([{"name": "a", "type": "rect", "x": 2, "y": 3, "w": 2, "h": 2, "material": "Si"}],
            {"w": {"value": "4 um"}})
    dv = design_velocity(d, "w")
    assert dv.delta_pm is None and all(v == (Q2(0), Q2(0)) or (v[0].is_zero() and v[1].is_zero())
                                       for v in dv.vertices.values())


# ---------------------------------------------------------------- D6 unchanged outputs

def _v1_documents():
    out = []
    for path in sorted((ROOT / "examples").rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and isinstance(data.get("geometry"), dict) and data["geometry"].get("version") == 1:
            out.append((path.name, data))
    return out


def _complex_fingerprint(rc):
    return (signature(rc), [(x, y) for x, y in rc.vertices], [c.area for c in rc.cells],
            [(k.a, k.b, k.params, k.provenance, k.left, k.right, k.tag) for k in rc.curves])


def test_d6_unchanged_without_derivative():
    docs = _v1_documents() + [("rect", RECT), ("d2", D2_DOC)]
    assert len(docs) >= 3
    for name, d in docs:
        model = parse(d)
        for cname, comp in model.components.items():
            if comp.dimension == "3d":
                continue
            before = _complex_fingerprint(evaluate(model, cname))
            for p, spec in model.parameters.items():
                if spec[1] == "length" and is_quantity_text(d["geometry"]["parameters"][p]["value"]):
                    try:
                        dv = design_velocity(d, p, cname)
                    except GeometryError:
                        continue
                    assert _complex_fingerprint(dv.complex) == before, (name, cname, p)
            assert parse(d) == model, name
            assert _complex_fingerprint(evaluate(parse(d), cname)) == before, (name, cname)


# ---------------------------------------------------------------- D7 refusals

def test_d7_refusals():
    with pytest.raises(GeometryError, match="unknown parameter 'nope'"):
        design_velocity(RECT, "nope")
    ratio = doc([{"name": "r", "type": "rect", "x": 1, "y": 1, "w": "w0 * k", "h": 2, "material": "Si"}],
                {"w0": {"value": "4 um"}, "k": {"value": 0.5, "kind": "ratio"}})
    with pytest.raises(GeometryError, match="is a ratio; the contract defines V = dx/dp for length parameters"):
        design_velocity(ratio, "k")
    derived = doc([{"name": "r", "type": "rect", "x": 1, "y": 1, "w": "w2", "h": 2, "material": "Si"}],
                  {"w": {"value": "2 um"}, "w2": {"value": "2 * w"}})
    with pytest.raises(GeometryError, match="w2 is derived from other parameters"):
        design_velocity(derived, "w2")
    assert rel(design_velocity(derived, "w").area_derivative("r"), 4 * UM) <= 1e-12     # dA/dw = 2 h
    arc = doc([{"name": "p", "type": "path", "start": [2, 2],
                "segments": [{"line": [8, 2]}, {"arc": {"center": ["c", 2], "to": [2, 2], "ccw": True}}],
                "material": "Si"}], {"c": {"value": "5 um"}})
    with pytest.raises(GeometryError, match="moving path arc"):
        design_velocity(arc, "c")
    # moving the start of a closed path opens a closing segment: a topology change, refused by name
    opened = copy.deepcopy(arc)
    opened["geometry"]["parameters"] = {"x0": {"value": "2 um"}, "c": {"value": "5 um"}}    # "s" is a unit symbol
    opened["geometry"]["components"]["xs"]["features"][0]["start"] = ["x0", 2]
    opened["geometry"]["components"]["xs"]["features"][0]["segments"][1]["arc"]["to"] = [2, 2]
    with pytest.raises(TopologyChange, match="features: p"):
        design_velocity(opened, "x0")
    three = {"openphysics": "0.3",
             "geometry": {"version": 1, "parameters": {"t": {"value": "1 um"}}, "components": {"box": {
                 "dimension": "3d", "length_unit": "um", "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1, "zmin": 0, "zmax": "t"},
                 "background": {"material": "air"}}}}}
    with pytest.raises(GeometryError, match="is 3d"):
        design_velocity(three, "t")


def test_d7_static_arc_taken():
    d = doc([{"name": "p", "type": "path", "start": [2, 2],
              "segments": [{"line": [8, 2]}, {"arc": {"center": [5, 2], "to": [2, 2], "ccw": True}}],
              "material": "Si"},
             {"name": "post", "type": "rect", "x": "x0", "y": 6, "w": 1, "h": 1, "material": "Ge"}],
            {"x0": {"value": "4.5 um"}})
    dv = design_velocity(d, "x0")
    # a translation keeps both areas; the arc's vertices stay put
    assert abs(dv.area_derivative("post")) <= 1e-12 * UM
    assert abs(dv.area_derivative("p")) <= 1e-12 * UM
    k = next(k for k in dv.complex.curves if k.kind == "arc")
    assert dv.curves[k.index].dr.is_zero() and dv.vertex_velocity(k.a) == (0.0, 0.0)


# ---------------------------------------------------------------- D8 node provenance

def test_d8_node_velocity():
    from meshine import generate
    d = doc([{"name": "c", "type": "circle", "cx": 5, "cy": 5, "r": "r", "material": "Si"},
             {"name": "pad", "type": "rect", "x": 1, "y": 1, "w": 2, "h": 2, "material": "Ge"}],
            {"r": {"value": "2 um"}})
    dv = design_velocity(d, "r")
    domain, namer = dv.complex.to_domain(0.5)[:2]
    mesh = generate(domain, namer)
    nv = dv.node_velocity(mesh)
    nodes = np.asarray(mesh.nodes, dtype=float)
    on_circle = [i for i in range(len(nodes)) if nv.curve[i] >= 0
                 and dv.complex.curves[nv.curve[i]].kind == "circle"]
    assert len(on_circle) >= 16
    for i in on_circle:
        n = (nodes[i] - (5, 5)) / np.hypot(*(nodes[i] - (5, 5)))
        assert abs(nv.values[i] @ n - 1.0) <= 1e-12
        assert abs(nv.values[i] @ (-n[1], n[0])) <= 1e-12
    # nodes on the pad and the domain do not move; interior nodes are galerkin's to choose
    for i in np.nonzero(nv.on_curve)[0]:
        if dv.complex.curves[nv.curve[i]].kind == "line":
            assert np.all(nv.values[i] == 0.0)
    assert np.all(nv.values[~nv.on_curve] == 0.0) and np.any(~nv.on_curve)
    for i in np.nonzero(nv.vertex >= 0)[0]:
        assert tuple(nv.values[i]) == dv.vertex_velocity(nv.vertex[i])


def test_d8_line_nodes_interpolate():
    from meshine import generate
    d = doc([{"name": "tri", "type": "polygon", "points": [[1, 1], ["1 + a", 1], ["1 + a", "1 + a/2"]],
              "material": "Si"}], {"a": {"value": "6 um"}})
    dv = design_velocity(d, "a")
    domain, namer = dv.complex.to_domain(0.5)[:2]
    mesh = generate(domain, namer)
    nv = dv.node_velocity(mesh)
    nodes = np.asarray(mesh.nodes, dtype=float)
    # the hypotenuse from (1, 1) [V = 0] to (7, 4) [V = (1, 1/2)]: V = s (1, 1/2)
    hyp = [i for i in range(len(nodes)) if nv.curve[i] >= 0 and nv.vertex[i] < 0
           and abs((nodes[i][1] - 1) - (nodes[i][0] - 1) / 2) < 1e-9 and 1 < nodes[i][0] < 7]
    assert hyp
    for i in hyp:
        s = (nodes[i][0] - 1) / 6
        assert np.allclose(nv.values[i], (s, s / 2), rtol=0, atol=1e-12)


# ---------------------------------------------------------------- review regressions (2026-11-08)

def _rounded_fd_best(d, param, region, want, perimeter=False):
    """Best relative error of central differences of the rounded document (the D4 study)."""
    p0 = float(d["geometry"]["parameters"][param]["value"].removesuffix(" um"))
    best = math.inf
    for h in (0.1, 0.01, 0.001):
        vals = []
        for s in (1, -1):
            dd = copy.deepcopy(d)
            dd["geometry"]["parameters"][param]["value"] = um(p0 + s * h)
            rc = evaluate(parse(dd))
            if perimeter:
                cells = set(rc.cells_of_region(region))
                vals.append(sum(_curve_length(rc, k) for k in rc.curves if (k.left in cells) != (k.right in cells)))
            else:
                vals.append(rc.area_of_region(region))
        fd = (vals[0] - vals[1]) / (2 * h * UM)          # pm (area) or dimensionless (length) per pm
        best = min(best, rel(fd, want))
    return best


def _curve_length(rc, k):
    (ax, ay), (bx, by) = (tuple(map(float, rc.vertices[v])) for v in (k.a, k.b))
    if k.kind == "line":
        return math.hypot(bx - ax, by - ay)
    cx, cy = k.params["center"]
    span = (math.atan2(by - cy, bx - cx) - math.atan2(ay - cy, ax - cx)) % (2 * math.pi) or 2 * math.pi
    return math.sqrt(k.params["r2"]) * span


def test_mixed_fields_on_one_curve():
    # the top of rect b is cut by two circles of different radicands; circle c is cut by two others
    d = doc([{"name": "b", "type": "rect", "x": 1, "y": 1, "w": 8, "h": "t", "material": "Si"},
             {"name": "c1", "type": "circle", "cx": 3, "cy": 5, "r": 1.5, "material": "Ge"},
             {"name": "c2", "type": "circle", "cx": 7, "cy": 5, "r": 1.7, "material": "Ge"}], {"t": {"value": "4.2 um"}})
    dv = design_velocity(d, "t")
    assert _rounded_fd_best(d, "t", "b", dv.area_derivative("b")) <= 1e-6
    assert _rounded_fd_best(d, "t", "b", dv.perimeter_derivative("b"), perimeter=True) <= 1e-6
    d2 = doc([{"name": "c", "type": "circle", "cx": 5, "cy": 5, "r": "r", "material": "Si"},
              {"name": "a1", "type": "circle", "cx": 3, "cy": 5, "r": 1.3, "material": "Ge"},
              {"name": "a2", "type": "circle", "cx": 7.1, "cy": 5.3, "r": 1.7, "material": "Ge"}], {"r": {"value": "2 um"}})
    dv2 = design_velocity(d2, "r")
    assert _rounded_fd_best(d2, "r", "c", dv2.area_derivative("c")) <= 1e-6
    assert _rounded_fd_best(d2, "r", "c", dv2.perimeter_derivative("c"), perimeter=True) <= 1e-6


def test_range_does_not_limit_the_probe():
    # w2 = 2 w sits at the end of its range; the derivative with respect to w is still given
    d = doc([{"name": "a", "type": "rect", "x": 1, "y": 1, "w": "w2", "h": 2, "material": "Si"}],
            {"w": {"value": "2 um", "range": ["1 um", "2 um"]}, "w2": {"value": "2 * w", "range": ["1 um", "4 um"]}})
    dv = design_velocity(d, "w")
    assert rel(dv.area_derivative("a"), 4 * UM) <= 1e-12


def test_refusal_names_features_only():
    d = doc([{"name": "c", "type": "circle", "cx": 5, "cy": 5, "r": 2, "material": "Si"},
             {"name": "b", "type": "rect", "x": "xb", "y": 7, "w": 1, "h": 1, "material": "Ge"}], {"xb": {"value": "5 um"}})
    e = _refused(d, "xb")
    assert "background" not in e.features and {"b", "c"} <= set(e.features)
