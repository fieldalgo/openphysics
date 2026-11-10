# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The experimental geometry lab (/geometry-lab): the exact engine's answer, shown as is.

The checks GL-1 to GL-4 and GL-7 were registered before the page was written; GL-5
(real browser) is tools/studio_browser/geometry_lab_browser.mjs and GL-6 (pure helpers)
is studio_geometry_lab.cjs.
"""
import ast
import copy
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import pytest

import simcase
from simcase.geometry_document import parse
from simcase.geometry_engine import evaluate

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(simcase.__file__).parent / "studio" / "static"
EXAMPLES = {name: ROOT / "examples" / "simcase" / f"{name}.json"
            for name in ("geometry_v1_soi_strip", "geometry_v1_imprint_rib")}


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("fastapi", reason="the studio extra is not installed")
    from fastapi.testclient import TestClient
    from simcase.studio import app
    return TestClient(app)


def lab(client, doc, component=None):
    response = client.post("/api/geometry-lab/evaluate", json={"doc": doc, "component": component})
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    return response.json()


def engine_view(doc, component=None):
    """What the page must show, computed here from the engine directly."""
    model = parse(doc)
    rc = evaluate(model, component)
    # format 0.2: one unit for the document; format 0.3: each component's own length_unit
    unit_pm = model.pm_per_unit if model.pm_per_unit is not None else \
        model.components[component or next(iter(model.components))].pm_per_unit
    scale = float(unit_pm)
    return {
        "regions": rc.region_names(),
        "selections": [[name, kind, sorted(chosen)] for name, (kind, chosen) in rc.selections.items()],
        "curves": [[k.kind, sorted(k.provenance), k.left, k.right, k.tag] for k in rc.curves],
        "cells": [[c.region, c.area / scale ** 2, [[[i, bool(f)] for i, f in loop] for loop in c.loops]] for c in rc.cells],
        "vertices": sorted({(float(rc.vertices[v][0]) / scale, float(rc.vertices[v][1]) / scale)
                            for k in rc.curves for v in (k.a, k.b)}),
        "summary": rc.summary(model),
    }


def page_view(view):
    return {
        "regions": [r["name"] for r in view["regions"]],
        "selections": [[s["name"], s["kind"], s["entries"]] for s in view["selections"]],
        "curves": [[k["kind"], k["provenance"], k["left"], k["right"], k["tag"]] for k in view["curves"]],
        "cells": [[c["region"], c["area"], c["loops"]] for c in view["cells"]],
        "vertices": sorted({tuple(p) for k in view["curves"] for p in (k["points"][0], k["points"][-1])}),
        "summary": view["summary"],
    }


# ---- GL-1: the same names as `simcase geometry` ------------------------------------------

@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_gl1_names_equal_the_cli_and_the_engine(client, name):
    doc = json.loads(EXAMPLES[name].read_text(encoding="utf-8"))
    view = lab(client, doc)
    assert view["ok"] is True
    cli = subprocess.run([sys.executable, "-m", "simcase", "geometry", str(EXAMPLES[name])],
                         capture_output=True, text=True, check=True, cwd=ROOT)
    assert view["summary"] + "\n" == cli.stdout
    assert page_view(view) == engine_view(doc)
    tags = {}
    for k in view["curves"]:
        if k["tag"]:
            tags.setdefault(k["tag"], []).append(k["index"])
    assert view["tags"] == [{"tag": t, "curves": c} for t, c in tags.items()]


def test_gl1_starters_are_the_shipped_examples():
    text = (STATIC / "geometry-lab-starters.mjs").read_text(encoding="utf-8")
    body = text[text.index("export const STARTERS={") + len("export const STARTERS="):text.rindex("};") + 1]
    starters = json.loads(re.sub(r"^\s*(\w+):", r'"\1":', body.replace(",\n}", "\n}"), flags=re.M))
    assert starters == {name: json.loads(path.read_text(encoding="utf-8")) for name, path in EXAMPLES.items()}


# ---- GL-2: parameter edits re-evaluate exactly ------------------------------------------

@pytest.mark.parametrize("name", sorted(EXAMPLES))
@pytest.mark.parametrize("w", ["0.3", "0.61", "0.9"])
def test_gl2_parameter_edits_equal_a_fresh_engine_run(client, name, w):
    from fractions import Fraction
    doc = json.loads(EXAMPLES[name].read_text(encoding="utf-8"))
    lo, hi = doc["geometry"]["parameters"]["w"]["range"]               # format 0.3: "0.3 um", "0.9 um"
    assert Fraction(lo.removesuffix(" um")) <= Fraction(w) <= Fraction(hi.removesuffix(" um"))
    doc["geometry"]["parameters"]["w"]["value"] = f"{w} um"
    view = lab(client, doc)
    assert view["ok"] is True
    assert page_view(view) == engine_view(copy.deepcopy(doc))      # floats compared with ==
    shown = next(p for p in view["parameters"] if p["name"] == "w")
    assert shown["unit"] == "m" and shown["value"] == float(Fraction(w) / 10 ** 6)     # SI, from the exact value


def test_gl2_an_expression_is_evaluated_by_the_engine(client):
    doc = json.loads(EXAMPLES["geometry_v1_soi_strip"].read_text(encoding="utf-8"))
    doc["geometry"]["parameters"]["gap"] = {"value": "0.1 um"}     # a bare 0.1 has no unit outside a component
    doc["geometry"]["parameters"]["w"]["value"] = "2 * t + gap"
    view = lab(client, doc)
    assert next(p for p in view["parameters"] if p["name"] == "w") == {
        "name": "w", "kind": "length", "value": 5.4e-07, "written": "2 * t + gap", "range": ["0.3 um", "0.9 um"],
        "unit": "m"}
    assert page_view(view) == engine_view(doc)


# ---- GL-3: refusals by name -------------------------------------------------------------

def _doc(features, params=None, selections=None, dimension="2d"):
    comp = {"dimension": dimension, "domain": {"xmin": -3, "xmax": 3, "ymin": -3, "ymax": 3},
            "background": {"material": "a"}, "features": features}
    if dimension == "3d":
        comp["domain"].update(zmin=0, zmax=1)
    if selections:
        comp["selections"] = selections
    geometry = {"version": 1, "components": {"xs": comp}}
    if params:
        geometry["parameters"] = params
    return {"units": {"length": "um"}, "geometry": geometry}


REFUSED = {
    "path crosses itself": (_doc([{"name": "bow", "type": "path", "material": "b", "start": [0, 0],
                                   "segments": [{"line": [1, 1]}, {"line": [1, 0]}, {"line": [0, 1]}]}]), "'bow'"),
    "arc end off its circle": (_doc([{"name": "lens", "type": "path", "material": "b", "start": [0, 0],
                                      "segments": [{"arc": {"center": [1, 0], "to": [2, 0.5], "ccw": True}},
                                                   {"line": [1, -1]}]}]), "'lens' segment s1"),
    "3d component": (_doc([{"name": "blk", "type": "box", "material": "b", "xmin": 0, "xmax": 1, "ymin": 0,
                            "ymax": 1, "zmin": 0, "zmax": 1}], dimension="3d"), "'xs'"),
    "empty selection": (_doc([{"name": "core", "type": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "material": "b"}],
                             selections={"gold": {"region": {"material": "Gold"}}}), "'gold'"),
    "parameter cycle": (_doc([{"name": "core", "type": "rect", "x": 0, "y": 0, "w": "p", "h": 1, "material": "b"}],
                             params={"p": {"value": "q"}, "q": {"value": "p"}}), "p -> q -> p"),
}


@pytest.mark.parametrize("case", sorted(REFUSED))
def test_gl3_refusals_carry_the_engines_message(client, case):
    doc, name = REFUSED[case]
    with pytest.raises(simcase.GeometryError) as engine:
        evaluate(parse(doc))
    view = lab(client, doc)
    assert view == {"ok": False, "refused": str(engine.value)}
    assert name in view["refused"]


def test_gl3_a_02_block_is_refused_with_the_cli_words(client, tmp_path):
    doc = simcase.examples.EXAMPLES["soi_strip"]
    path = tmp_path / "soi.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    cli = subprocess.run([sys.executable, "-m", "simcase", "geometry", str(path)],
                         capture_output=True, text=True, cwd=ROOT)
    assert cli.returncode == 2
    assert lab(client, doc) == {"ok": False, "refused": cli.stderr.strip().removeprefix("error: ")}


def test_gl3_a_component_is_named_or_the_first_2d_one_is_shown(client):
    doc = _doc([{"name": "core", "type": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "material": "b"}])
    doc["geometry"]["components"]["b3"] = _doc([{"name": "blk", "type": "box", "material": "b", "xmin": 0, "xmax": 1,
                                                 "ymin": 0, "ymax": 1, "zmin": 0, "zmax": 1}],
                                               dimension="3d")["geometry"]["components"]["xs"]
    shown = lab(client, doc)
    assert shown["component"] == "xs" and shown["components"] == ["xs", "b3"]
    refused = lab(client, doc, "b3")
    assert refused["ok"] is False and "'b3'" in refused["refused"]
    assert lab(client, doc, "nope") == {"ok": False, "refused": "no component 'nope'"}


# ---- GL-4: the saved document round-trips -----------------------------------------------

def test_gl4_saved_json_round_trips_through_the_reader(client):
    doc = json.loads(EXAMPLES["geometry_v1_imprint_rib"].read_text(encoding="utf-8"))
    doc["geometry"]["parameters"]["w"]["value"] = "0.42 um"
    doc["geometry"]["parameters"]["slab"]["value"] = "t / 2"
    saved = json.dumps(doc, indent=2) + "\n"       # serializeDocument: two-space JSON and a newline
    again = json.loads(saved)
    assert again == doc
    assert evaluate(parse(again)).summary(parse(again)) == lab(client, doc)["summary"]
    assert parse(again).parameters == parse(doc).parameters


# ---- GL-7: the pilot page and the public API boundary -----------------------------------

def test_gl7_the_lab_is_its_own_page_with_a_strict_policy(client):
    for path in ("/geometry-lab", "/geometry-lab/"):
        page = client.get(path)
        assert page.status_code == 200 and page.content == (STATIC / "geometry-lab.html").read_bytes()
        policy = page.headers["content-security-policy"]
        assert "script-src 'self'" in policy and "default-src 'none'" in policy and "unsafe" not in policy
        assert page.headers["cache-control"] == "no-store"
    html = (STATIC / "geometry-lab.html").read_text(encoding="utf-8")
    assert "<script>" not in html and " style=" not in html and "http" not in html.replace("http-equiv", "")
    assert re.findall(r'<script[^>]*src="([^"]+)"', html) == ["/geometry-lab-assets/geometry-lab-app.mjs"]


def test_gl7_lab_assets_are_shipped_and_served_with_explicit_mime(client):
    files = sorted(STATIC.glob("geometry-lab-*.mjs"))
    assert [f.name for f in files] == ["geometry-lab-app.mjs", "geometry-lab-model.mjs", "geometry-lab-starters.mjs"]
    for path in files:
        response = client.get("/geometry-lab-assets/" + path.name)
        assert response.content == path.read_bytes()
        assert response.headers["content-type"].startswith("text/javascript")
        assert response.headers["x-content-type-options"] == "nosniff"
        text = response.text
        assert "import(" not in text and "http" not in text.replace("http://www.w3.org/2000/svg", "")
        for dependency in re.findall(r"from ['\"]\./([^'\"]+)['\"]", text):
            assert dependency.startswith("geometry-lab-") and (STATIC / dependency).is_file()
    assert client.get("/geometry-lab-assets/geometry-lab.css").headers["content-type"].startswith("text/css")
    for name in ("workspace-app.mjs", "workspace.css", "geometry-lab.html", "geometry_api.py", "nope.mjs"):
        assert client.get("/geometry-lab-assets/" + name).status_code == 404
    assert client.get("/workspace-assets/geometry-lab-app.mjs").status_code == 404


def test_gl7_the_pilot_pages_do_not_link_or_load_the_lab(client):
    for path in ("/", "/workspace"):
        assert "geometry-lab" not in client.get(path).text
    for path in STATIC.glob("workspace*"):
        assert "geometry-lab" not in path.read_text(encoding="utf-8")


def test_gl7_the_lab_module_imports_only_public_simcase_names():
    tree = ast.parse((Path(simcase.__file__).parent / "studio" / "geometry_api.py").read_text(encoding="utf-8"))
    names = [a.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module == "simcase"
             for a in node.names]
    assert names == ["GeometryError", "evaluate_geometry", "parse_geometry"]
    assert set(names) <= set(simcase.__all__)
    assert simcase.parse_geometry is parse and simcase.evaluate_geometry is evaluate


# ---- drawing data checked against the document itself, not the engine's formulas --------

def _shoelace(points):
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]))


def _loop_points(view, loop):
    pts = []
    for index, forward in loop:
        run = view["curves"][index]["points"]
        run = run if forward else run[::-1]
        pts += run[1:] if pts else run
    return pts[:-1]


def test_arcs_and_circles_are_drawn_on_their_circles_counter_clockwise(client):
    doc = {"units": {"length": "nm"}, "geometry": {"version": 1, "components": {"xs": {
        "dimension": "2d", "domain": {"xmin": -3000, "xmax": 3000, "ymin": -3000, "ymax": 3000},
        "background": {"material": "a"},
        "features": [
            {"name": "disc", "type": "circle", "cx": -1500, "cy": 0, "r": 1000, "material": "b"},
            {"name": "bar", "type": "rect", "x": -1700, "y": -2000, "w": 400, "h": 4000, "material": "c"},
            {"name": "ring", "type": "circle", "cx": 1500, "cy": 1500, "r": 700, "material": "b"},
            {"name": "half", "type": "path", "material": "c", "start": [500, -1500],
             "segments": [{"arc": {"center": [1500, -1500], "to": [2500, -1500], "ccw": False}}]}]}}}}
    view = lab(client, doc)
    assert view["ok"] is True
    circles = {"disc": ((-1500, 0), 1000), "ring": ((1500, 1500), 700), "half": ((1500, -1500), 1000)}
    curved = [k for k in view["curves"] if k["kind"] != "line"]
    assert curved
    for k in curved:
        (cx, cy), r = next(circles[f.split(".")[0]] for f in k["provenance"] if f.split(".")[0] in circles)
        pts = k["points"]
        assert len(pts) >= 3
        for x, y in pts:
            assert abs(((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 - r) <= 1e-9 * r
        turns = [(x0 - cx) * (y1 - cy) - (x1 - cx) * (y0 - cy) for (x0, y0), (x1, y1) in zip(pts, pts[1:])]
        assert min(turns) > 0                       # counter-clockwise from vertex a to b
    # The drawn loops enclose the engine's areas up to the sampling of the curves.
    for cell in view["cells"]:
        drawn = _shoelace(_loop_points(view, cell["loops"][0])) - sum(
            abs(_shoelace(_loop_points(view, hole))) for hole in cell["loops"][1:])
        assert drawn == pytest.approx(cell["area"], rel=2e-3)
    areas = {r["name"]: r["area"] for r in view["regions"]}
    assert areas["ring"] == pytest.approx(math.pi * 700 ** 2, rel=1e-12)
    assert areas["half"] == pytest.approx(math.pi * 1000 ** 2 / 2, rel=1e-12)
    assert areas["bar"] == 400 * 4000 and view["unit"] == "nm"     # whole rect, exact in nm


def test_lengths_and_areas_are_in_the_document_unit(client):
    def rect_doc(unit, scale):
        return {"units": {"length": unit}, "geometry": {"version": 1, "components": {"xs": {
            "dimension": "2d", "domain": {"xmin": -2 * scale, "xmax": 2 * scale, "ymin": -1 * scale, "ymax": 1 * scale},
            "background": {"material": "a"},
            "features": [{"name": "r", "type": "rect", "x": -0.25 * scale, "y": -0.5 * scale, "w": 0.5 * scale,
                          "h": 0.75 * scale, "material": "b"}]}}}}
    for unit, scale in (("um", 1), ("nm", 1000), ("mm", 0.001)):
        view = lab(client, rect_doc(unit, scale))
        assert view["domain"] == {"xmin": -2 * scale, "xmax": 2 * scale, "ymin": -1 * scale, "ymax": 1 * scale}
        r = next(x for x in view["regions"] if x["name"] == "r")
        assert r["area"] == pytest.approx(0.375 * scale ** 2, rel=1e-15)
        corners = {tuple(p) for k in view["curves"] if "r.left" in k["provenance"] for p in k["points"]}
        assert corners == {(-0.25 * scale, -0.5 * scale), (-0.25 * scale, 0.25 * scale)}


def test_only_engine_refusals_reach_the_page_never_a_traceback(monkeypatch):
    """A refusal carries the reader's or engine's message, which is built from the submitted
    document; anything else is the server's generic 500 with no exception text. This keeps
    holding if Studio is ever served beyond the local machine."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from simcase.studio import app, geometry_api
    quiet = TestClient(app, raise_server_exceptions=False)
    # a units string was a reader bug (AttributeError) until 2026-11-09; it is now a refusal
    doc = {"units": "um", "geometry": {"version": 1, "components": {}}}
    response = quiet.post("/api/geometry-lab/evaluate", json={"doc": doc})
    assert response.status_code == 200 and response.json()["refused"].startswith("units: expected an object")

    def bug(*args, **kwargs):                                                # any other exception
        raise AttributeError("'str' object has no attribute 'get' in geometry_document.py")
    monkeypatch.setattr(geometry_api, "evaluate_view", bug)
    response = quiet.post("/api/geometry-lab/evaluate", json={"doc": {"units": {"length": "um"}}})
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert "Traceback" not in response.text and "AttributeError" not in response.text and ".py" not in response.text
    source = (Path(simcase.__file__).parent / "studio" / "geometry_api.py").read_text(encoding="utf-8")
    assert source.count("except ") == 1 and "except GeometryError as exc:" in source
