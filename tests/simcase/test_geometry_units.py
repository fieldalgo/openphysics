# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Version 1 geometry blocks in format 0.3 (units batch C4, critique K8).

A format 0.3 block declares ``length_unit`` per component (and ``depth`` on a 2d one), its
geometry parameters carry their unit, and element sizes are quantity strings. The same
geometry written in 0.2 and in 0.3 must give the same picometre model, the same design
velocity, the same region-complex summary and the same geometry-lab view; every refusal
carries its diagnostic code and path. The 0.2 parse is unchanged (its own tests).
"""

from __future__ import annotations

import copy
import json
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from simcase import geometry_document as gd
from simcase.cli import main
from simcase.geometry_engine import evaluate
from simcase.geometry_velocity import design_velocity, exact_complex, signature
from simcase.reader import read
from simcase.resolve import resolve_text
from simcase.schema import Document

import units_toy_kind as toy

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ("geometry_v1_soi_strip", "geometry_v1_imprint_rib")


def as_v03(doc02: dict) -> dict:
    """The format 0.3 geometry of a 0.2 version 1 document: the same numbers, tagged where 0.3 tags."""
    unit = doc02["units"]["length"]
    g = copy.deepcopy(doc02["geometry"])
    for spec in g.get("parameters", {}).values():
        if spec.get("kind", "length") == "length":
            for key in ("value",):
                if isinstance(spec[key], (int, float)):
                    spec[key] = f"{spec[key]!r} {unit}"
            if "range" in spec:
                spec["range"] = [f"{v!r} {unit}" if isinstance(v, (int, float)) else v for v in spec["range"]]
    for comp in g["components"].values():
        comp["length_unit"] = unit
        if comp["dimension"] == "2d":
            comp["depth"] = None
        for owner in [comp.get("background", {})] + comp.get("features", []):
            if "mesh_size" in owner:
                owner["element_size"] = f"{owner.pop('mesh_size')!r} {unit}"
    return read({"openphysics": "0.3", "geometry": g})


def _example(name):
    return json.loads((ROOT / "examples" / "simcase" / f"{name}.json").read_text(encoding="utf-8"))


#: "h" would be a unit symbol (the hour) in format 0.3, which refuses it as a parameter name
RECT02 = {"openphysics": "0.2", "units": {"length": "um"},
          "geometry": {"version": 1, "parameters": {"w": {"value": 4}, "t": {"value": 2.5}},
                       "components": {"xs": {"dimension": "2d", "domain": {"xmin": 0, "xmax": 10, "ymin": 0, "ymax": 10},
                                             "background": {"material": "air"},
                                             "features": [{"name": "core", "type": "rect", "x": 2, "y": 3, "w": "w",
                                                           "h": "t", "material": "Si"}]}}}}


@pytest.mark.parametrize("name", EXAMPLES)
def test_the_same_geometry_gives_the_same_picometre_model(name):
    old = _example(name)
    m2, m3 = gd.parse(old), gd.parse(as_v03(old))
    assert (m2.format, m3.format) == ("0.2", "0.3")
    assert m3.pm_per_unit is None and m3.units_length is None
    for cname, c2 in m2.components.items():
        c3 = m3.components[cname]
        assert (c3.length_unit, c3.pm_per_unit, c3.depth) == ("um", Fraction(10 ** 6), None)
        assert (c2.length_unit, c2.pm_per_unit) == ("um", Fraction(10 ** 6))
        assert c3.domain == c2.domain and c3.background == c2.background
        assert [(f.id, f.type, f.material, f.mesh_size, f.data) for f in c3.features] == \
               [(f.id, f.type, f.material, f.mesh_size, f.data) for f in c2.features]
    for pname, (value, kind) in m2.parameters.items():
        assert m3.parameters[pname] == (value * 10 ** 6, kind)          # exact pm
    assert evaluate(m3).summary(m3) == evaluate(m2).summary(m2)


def test_each_component_reads_its_own_unit():
    one = {"dimension": "2d", "length_unit": "um", "depth": None, "domain": {"xmin": 0, "xmax": 3, "ymin": 0, "ymax": 2},
           "background": {"material": "a"},
           "features": [{"name": "c", "type": "circle", "cx": 1.5, "cy": 1, "r": "r + 0.25", "material": "b"}]}
    other = copy.deepcopy(one)
    other.update(length_unit="nm", domain={"xmin": 0, "xmax": 3000, "ymin": 0, "ymax": 2000})
    other["features"][0].update(cx=1500, cy=1000, r="r + 250")
    model = gd.parse(read({"openphysics": "0.3", "geometry": {"version": 1, "parameters": {"r": {"value": "0.5 um"}},
                                                               "components": {"a": one, "b": other}}}))
    a, b = model.components["a"], model.components["b"]
    assert (a.pm_per_unit, b.pm_per_unit) == (10 ** 6, 10 ** 3)
    assert a.domain == b.domain and a.features[0].data == b.features[0].data == {"cx": 1500000, "cy": 1000000,
                                                                                "r": 750000}
    assert evaluate(model, "a").summary(model).split("\n")[0].endswith("um")
    assert evaluate(model, "b").summary(model).split("\n")[0].endswith("nm")


def test_design_velocity_is_the_same_number():
    new = as_v03(RECT02)
    for p in ("w", "t"):
        v2, v3 = design_velocity(RECT02, p), design_velocity(new, p)
        assert v3.vertices == v2.vertices and v3.curves.keys() == v2.curves.keys()
        assert all(vars(v3.curves[k]) == vars(v2.curves[k]) for k in v2.curves)
        assert {k: v for k, v in v3.defining.items()} == v2.defining
        assert v3.delta_pm == v2.delta_pm
    rc2, s2 = exact_complex(RECT02, "w", Fraction(1, 1000))
    rc3, s3 = exact_complex(new, "w", "0.001 um")
    assert signature(rc3) == signature(rc2) and rc3.vertices == rc2.vertices and s3 == s2
    rc3b, _ = exact_complex(new, "w", Fraction(1000))                    # pm
    assert rc3b.vertices == rc3.vertices


def test_the_geometry_lab_reports_the_component_unit_and_si_parameters():
    pytest.importorskip("fastapi")
    from simcase.studio.geometry_api import evaluate_view
    old = _example("geometry_v1_soi_strip")
    v2, v3 = evaluate_view(old), evaluate_view(as_v03(old))
    p2, p3 = v2.pop("parameters"), v3.pop("parameters")
    assert v3 == v2 and v3["unit"] == "um"
    assert [p["value"] for p in p3] == [5e-07, 2.2e-07] and [p["unit"] for p in p3] == ["m", "m"]
    assert [p["value"] for p in p2] == [0.5, 0.22]


def test_simcase_geometry_prints_a_0_3_file(tmp_path, capsys):
    old = _example("geometry_v1_imprint_rib")
    (tmp_path / "old.json").write_text(json.dumps(old), encoding="utf-8")
    new = as_v03(old)
    (tmp_path / "new.json").write_text(_dumps(new), encoding="utf-8")
    assert main(["geometry", str(tmp_path / "old.json")]) == 0
    old_out = capsys.readouterr().out
    assert main(["geometry", str(tmp_path / "new.json")]) == 0
    assert capsys.readouterr().out == old_out


def _dumps(tree) -> str:
    from simcase.reader import dumps
    return dumps(tree, indent=2)


def _refusal(geometry, *, code, path):
    with pytest.raises(gd.GeometryError) as caught:
        gd.parse(read({"openphysics": "0.3", "geometry": geometry}))
    assert (caught.value.code, caught.value.path) == (code, path), str(caught.value)
    return str(caught.value)


def _block(**changes):
    g = copy.deepcopy(as_v03(RECT02)["geometry"])
    comp = g["components"]["xs"]
    for key, value in changes.items():
        target = g if key == "parameters" else comp
        if value is toy.DELETE:
            target.pop(key)
        else:
            target[key] = value
    return g


@pytest.mark.parametrize("changes, code, path", [
    (dict(parameters={"w": {"value": 4}, "t": {"value": "2.5 um"}}), "E-UNIT-MISSING", "geometry.parameters.w.value"),
    (dict(parameters={"nm": {"value": "4 um"}}), "E-ID-CLASH", "geometry.parameters.nm"),
    (dict(parameters={"w": {"value": "4 um"}, "h": {"value": "2.5 um"}}), "E-ID-CLASH", "geometry.parameters.h"),
    (dict(parameters={"w": {"value": "t + 1"}, "t": {"value": "2.5 um"}}), "E-UNIT-MISSING",
     "geometry.parameters.w.value"),
    (dict(parameters={"w": {"value": "4 um", "range": ["1 um", "3 um"]}, "t": {"value": "2.5 um"}}), "E-DOMAIN",
     "geometry.parameters.w.value"),
    (dict(depth=toy.DELETE), "E-KEY-MISSING", "geometry.components.xs.depth"),
    (dict(length_unit=toy.DELETE), "E-KEY-MISSING", "geometry.components.xs.length_unit"),
    (dict(length_unit="km"), "E-UNIT-NOT-ACCEPTED", "geometry.components.xs.length_unit"),
    (dict(length_unit={"in_m": 1e-6}), "E-VALUE-FORM", "geometry.components.xs.length_unit"),
    (dict(dimension="axisymmetric"), "E-KEY-UNKNOWN", "geometry.components.xs.depth"),
    (dict(background={"material": "air", "mesh_size": 0.5}), "E-KEY-UNKNOWN",
     "geometry.components.xs.background.mesh_size"),
])
def test_refusals_carry_their_code_and_path(changes, code, path):
    _refusal(_block(**changes), code=code, path=path)


@pytest.mark.parametrize("value, code", [("w/10", "E-UNIT-UNKNOWN"), (Decimal("0.5"), "E-UNIT-MISSING"),
                                         ("0 um", "E-DOMAIN")])
def test_an_element_size_is_a_quantity_string(value, code):
    g = _block()
    g["components"]["xs"]["features"][0]["element_size"] = value
    _refusal(g, code=code, path="geometry.components.xs.features[0].element_size")


def test_a_unit_inside_an_expression_asks_for_a_parameter():
    g = _block()
    g["components"]["xs"]["features"][0]["x"] = "220 nm + w"
    message = _refusal(g, code="E-EXPRESSION-KIND", path="geometry.components.xs.features[0].x")
    assert "declare a parameter" in message
    g["components"]["xs"]["features"][0]["x"] = "0.5 um"
    _refusal(g, code="E-VALUE-FORM", path="geometry.components.xs.features[0].x")
    g = _block()
    g["length_unit"] = "um"
    _refusal(g, code="E-KEY-UNKNOWN", path="geometry.length_unit")


def test_to_v02_carries_the_unit_and_depth():
    homogeneous = _block(features=[], background={})
    flat = gd.to_v02(gd.parse(read({"openphysics": "0.3", "geometry": homogeneous})))
    assert flat == {"length_unit": "um", "depth": None, "domain": {"xmin": 0.0, "xmax": 10.0, "ymin": 0.0, "ymax": 10.0}}
    back = gd.from_v02({"length_unit": "mm", "depth": "40 mm", "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}})
    assert back["components"]["main"]["length_unit"] == "mm" and back["components"]["main"]["depth"] == "40 mm"


@pytest.fixture
def toy_kind():
    with toy.registered():
        yield


def _v1_toy(**geometry_changes):
    data = toy.document()
    data["geometry"] = json.loads(_dumps(_block(**geometry_changes)))
    data["geometry"]["components"]["xs"]["background"] = {"material": "steel"}
    data["geometry"]["components"]["xs"]["features"][0]["material"] = "steel"
    return data


def test_a_version_1_document_resolves_to_metres(toy_kind):
    data = _v1_toy()
    data["geometry"]["components"]["xs"]["features"][0]["y"] = 0.30000000000000004
    result = resolve_text(json.dumps(data))
    doc = result.document()
    assert doc is not None, [str(d) for d in result.diagnostics]
    feature = doc.si["geometry"]["components"]["xs"]["features"][0]
    assert (feature["x"], feature["y"], feature["w"]) == (2e-06, 3e-07, 4e-06)
    assert doc.pm("geometry.components.xs.features[0].w") == 4 * 10 ** 6
    assert doc.si["geometry"]["parameters"]["w"]["value"] == 4e-06
    inputs = doc.resolved_inputs()
    assert inputs["geometry.components.xs.domain.xmax"] == {"authored": 10, "value": 1e-05, "unit": "m",
                                                            "length_unit": "um"}
    assert inputs["geometry.parameters.w.value"] == {"authored": "4 um", "value": 4e-06, "unit": "m"}
    assert [(d.code, d.path) for d in doc.diagnostics if d.code.endswith("PM-ROUNDING")] == [
        ("I-PM-ROUNDING", "geometry.components.xs.features[0].y")]
    assert doc.extent_lines()[0].startswith("geometry.components.xs (length_unit um, 2d): 10 um x 10 um = "
                                            "1e-05 m x 1e-05 m; depth per metre (null)")
    assert doc.is_version_1 and doc.geometry_model.format == "0.3"


def test_version_1_refusals_surface_with_code_and_path(toy_kind):
    result = resolve_text(json.dumps(_v1_toy(parameters={"w": {"value": 4}, "t": {"value": "2.5 um"}})))
    assert [(d.code, d.path) for d in result.diagnostics if d.severity == "error"] == [
        ("E-UNIT-MISSING", "geometry.parameters.w.value")]
    result = resolve_text(json.dumps(_v1_toy(colour="red")))
    assert [(d.code, d.path) for d in result.diagnostics if d.severity == "error"] == [
        ("E-KEY-UNKNOWN", "geometry.components.xs.colour")]


def test_a_homogeneous_component_keeps_its_flat_compilation(toy_kind):
    data = _v1_toy()
    comp = data["geometry"]["components"]["xs"]
    comp.pop("features")
    comp["background"] = {}
    doc = Document.from_dict(data)
    assert doc.geometry_flat == {"length_unit": "um", "depth": None,
                                 "domain": {"xmin": 0.0, "xmax": 10.0, "ymin": 0.0, "ymax": 10.0}}
    assert not doc.is_version_1
