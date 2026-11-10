# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Version 1 geometry blocks in format 0.3 (units batch C4, critique K8; C11a).

A format 0.3 block declares ``length_unit`` per component (and ``depth`` on a 2d one), its
geometry parameters carry their unit, and element sizes are quantity strings. The kernel
hand-off's own reading of its unit-declared tree (``parse_handoff``) gives the same picometre
model as the format 0.3 reading; the design velocity does not depend on the length unit;
every refusal carries its diagnostic code and path. Since C11a the public readers (``parse``,
``design_velocity``, the geometry lab and ``simcase geometry``) refuse a format 0.2 document
by name (``E-FORMAT``).
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


#: the geometry of the two version 1 examples as format 0.2 wrote them (examples/simcase before the
#: units batch converted their documents to format 0.3; the geometry readers are compared here)
GEOMETRY_02 = {
    "geometry_v1_soi_strip": {
        "openphysics": "0.2", "units": {"length": "um"},
        "geometry": {"version": 1, "parameters": {"w": {"value": 0.5, "range": [0.3, 0.9]}, "t": {"value": 0.22}},
                     "components": {"xs": {
                         "dimension": "2d", "domain": {"xmin": -1.5, "xmax": 1.5, "ymin": -1.2, "ymax": 1.2},
                         "background": {"material": "SiO2"},
                         "features": [{"name": "core", "type": "rect", "x": "-w/2", "y": 0.0, "w": "w", "h": "t",
                                       "material": "Si", "mesh_size": 0.02}],
                         "finalize": "later_wins"}}}},
    "geometry_v1_imprint_rib": {
        "openphysics": "0.2", "units": {"length": "um"},
        "geometry": {"version": 1, "parameters": {"w": {"value": 0.5, "range": [0.3, 0.9]}, "t": {"value": 0.22},
                                                  "slab": {"value": 0.09}},
                     "components": {"xs": {
                         "dimension": "2d", "domain": {"xmin": -1.5, "xmax": 1.5, "ymin": -1.2, "ymax": 1.2},
                         "background": {"material": "SiO2"},
                         "features": [{"name": "slab", "type": "rect", "x": -1.5, "y": 0.0, "w": 3.0, "h": "slab",
                                       "material": "Si", "mesh_size": 0.04},
                                      {"name": "rib", "type": "rect", "x": "-w/2", "y": 0.0, "w": "w", "h": "t",
                                       "material": "Si", "mesh_size": 0.02}],
                         "finalize": "imprint",
                         "selections": {"rib_walls": {"boundary": {"between": ["rib", "background"]}},
                                        "etch_line": {"boundary": "slab.top"},
                                        "silicon": {"region": {"material": "Si"}}}}}}},
}


def _example(name):
    return copy.deepcopy(GEOMETRY_02[name])


def test_the_shipped_examples_hold_the_same_geometry():
    """The format 0.3 examples keep these features; only material names changed (physmat: names, and
    D-24 local records in the imprint rib)."""
    names = {"geometry_v1_soi_strip": {"Si": "physmat:Si", "SiO2": "physmat:SiO2"},
             "geometry_v1_imprint_rib": {"Si": "silicon", "SiO2": "oxide"}}
    for name, renamed in names.items():
        shipped = gd.parse(read(json.loads((ROOT / "examples" / "simcase" / f"{name}.json").read_text(encoding="utf-8"))))
        frozen = gd.parse(as_v03(_example(name)))
        for cname, c in frozen.components.items():
            s = shipped.components[cname]
            assert s.domain == c.domain and s.background == {**c.background,
                                                             "material": renamed[c.background["material"]]}
            assert [(f.id, f.type, f.mesh_size, f.data) for f in s.features] == \
                   [(f.id, f.type, f.mesh_size, f.data) for f in c.features]
            assert [f.material for f in s.features] == [renamed[f.material] for f in c.features]
        assert shipped.parameters == frozen.parameters


#: "h" would be a unit symbol (the hour) in format 0.3, which refuses it as a parameter name
RECT02 = {"openphysics": "0.2", "units": {"length": "um"},
          "geometry": {"version": 1, "parameters": {"w": {"value": 4}, "t": {"value": 2.5}},
                       "components": {"xs": {"dimension": "2d", "domain": {"xmin": 0, "xmax": 10, "ymin": 0, "ymax": 10},
                                             "background": {"material": "air"},
                                             "features": [{"name": "core", "type": "rect", "x": 2, "y": 3, "w": "w",
                                                           "h": "t", "material": "Si"}]}}}}


@pytest.mark.parametrize("name", EXAMPLES)
def test_the_same_geometry_gives_the_same_picometre_model(name):
    """The kernel hand-off's unit-declared reading and the format 0.3 reading agree."""
    old = _example(name)
    m2, m3 = gd.parse_handoff(old), gd.parse(as_v03(old))
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


def _in_nanometres(doc03: dict) -> dict:
    """The same format 0.3 geometry written in nanometres (numbers x 1000, parameters in nm)."""
    out = copy.deepcopy(doc03)
    for spec in out["geometry"]["parameters"].values():
        spec["value"] = f"{Fraction(str(spec['value']).removesuffix(' um')) * 1000} nm"
    for comp in out["geometry"]["components"].values():
        comp["length_unit"] = "nm"
        comp["domain"] = {k: Decimal(str(v)) * 1000 for k, v in comp["domain"].items()}
        for f in comp["features"]:
            for k in ("x", "y"):
                f[k] = Decimal(str(f[k])) * 1000
    return out


def test_design_velocity_is_the_same_number():
    """V = dx/dp is a ratio of picometres: the same geometry in micrometres and in nanometres gives
    the same exact velocities, and an offset as a quantity string or as picometres the same complex.
    (Before C11a the reference was the format 0.2 document; the 0.2 reading is retired.)"""
    new = as_v03(RECT02)
    nm = _in_nanometres(new)
    assert gd.parse(nm).components["xs"].features[0].data == gd.parse(new).components["xs"].features[0].data
    for p in ("w", "t"):
        v_nm, v3 = design_velocity(nm, p), design_velocity(new, p)
        assert v3.vertices == v_nm.vertices and v3.curves.keys() == v_nm.curves.keys()
        assert all(vars(v3.curves[k]) == vars(v_nm.curves[k]) for k in v_nm.curves)
        assert v3.defining == {k: v for k, v in v_nm.defining.items()}
        assert v3.delta_pm == v_nm.delta_pm
    rc_nm, s_nm = exact_complex(nm, "w", "1 nm")
    rc3, s3 = exact_complex(new, "w", "0.001 um")
    assert signature(rc3) == signature(rc_nm) and rc3.vertices == rc_nm.vertices and s3 == s_nm
    rc3b, _ = exact_complex(new, "w", Fraction(1000))                    # pm
    assert rc3b.vertices == rc3.vertices
    with pytest.raises(gd.GeometryError) as caught:                    # the format 0.2 reading is retired
        design_velocity(RECT02, "w")
    assert (caught.value.code, caught.value.path) == ("E-FORMAT", "openphysics")


def test_the_geometry_lab_reports_the_component_unit_and_si_parameters():
    pytest.importorskip("fastapi")
    from simcase.studio.geometry_api import evaluate_view
    new = as_v03(_example("geometry_v1_soi_strip"))
    v3 = evaluate_view(new)
    p3 = v3.pop("parameters")
    model = gd.parse(new)
    assert v3["unit"] == "um" and v3["summary"] == evaluate(model).summary(model)
    assert [p["value"] for p in p3] == [5e-07, 2.2e-07] and [p["unit"] for p in p3] == ["m", "m"]
    with pytest.raises(gd.GeometryError) as caught:                    # the format 0.2 reading is retired
        evaluate_view(_example("geometry_v1_soi_strip"))
    assert (caught.value.code, caught.value.path) == ("E-FORMAT", "openphysics")


def test_simcase_geometry_prints_a_0_3_file(tmp_path, capsys):
    old = _example("geometry_v1_imprint_rib")
    (tmp_path / "old.json").write_text(json.dumps(old), encoding="utf-8")
    new = as_v03(old)
    (tmp_path / "new.json").write_text(_dumps(new), encoding="utf-8")
    assert main(["geometry", str(tmp_path / "new.json")]) == 0
    model = gd.parse(read(json.loads((tmp_path / "new.json").read_text(encoding="utf-8"))))
    assert capsys.readouterr().out == evaluate(model).summary(model) + "\n"
    assert main(["geometry", str(tmp_path / "old.json")]) == 2           # the format 0.2 reading is retired
    assert 'openphysics is "0.2"; this reader reads the format "0.3"' in capsys.readouterr().err


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
