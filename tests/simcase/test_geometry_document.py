# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Geometry document version 1, stage 1: parsing, the 1 pm grid, the 0.2 adapters
and the layer-stack compile, with analytic checks of the 2.5D route."""

import copy
import json
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from meshine import Circle, Domain, box_sides, extrude, generate, rectangle
from simcase.examples import EXAMPLES
from simcase.geometry_document import (GeometryError, from_v02, layer_stack, parse, pm_per_unit,
                                       to_v02)

ROOT = Path(__file__).resolve().parents[2]


def _docs():
    docs = {f"builtin:{k}": v for k, v in EXAMPLES.items()}
    docs.update({p.name: json.loads(p.read_text(encoding="utf-8"))
                 for p in sorted((ROOT / "examples" / "simcase").glob("*.json"))})
    # The walk covers the 0.2 documents; version 1 examples are checked below.
    return {k: v for k, v in docs.items() if "version" not in v.get("geometry", {})}


DOCS = _docs()


def v1(units, components, parameters=None):
    g = {"version": 1, "components": components}
    if parameters is not None:
        g["parameters"] = parameters
    return {"units": units, "geometry": g}


def plate(features, **extra):
    comp = {"dimension": "2d", "domain": {"xmin": 0, "xmax": 10, "ymin": 0, "ymax": 10},
            "background": {"material": "SiO2"}, "features": features}
    comp.update(extra)
    return {"xs": comp}


# ----------------------------------------------------------------- S1-1: 0.2 round trip

def test_all_current_documents_are_walked():
    assert len(DOCS) == 51


@pytest.mark.parametrize("name", sorted(DOCS))
def test_v02_round_trip_is_exact(name):
    doc = copy.deepcopy(DOCS[name])
    model = parse({"units": doc["units"], "geometry": from_v02(doc["geometry"])})
    assert model.roundings == []
    assert to_v02(model) == doc["geometry"]


def test_v02_names_that_cannot_be_ids_get_positions():
    g = {"domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}, "background": {"material": "a"},
         "shapes": [{"name": "top", "type": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "material": "b"},
                    {"name": "my core", "type": "circle", "cx": 0.5, "cy": 0.5, "r": 0.1, "material": "c"}]}
    comp = from_v02(g)["components"]["main"]
    assert [f.get("id") for f in comp["features"]] == ["s0", "s1"]
    model = parse({"units": {"length": "um"}, "geometry": from_v02(g)})
    assert [f.name for f in model.components["main"].features] == ["top", "my core"]
    assert to_v02(model) == g


# ----------------------------------------------------------------- S1-2: the 1 pm grid

@pytest.mark.parametrize("unit, value, pm", [("nm", 0.5, 500), ("um", 0.22, 220000), ("m", 1.5e-6, 1500000),
                                             ("mm", 0.035, 35000000), ({"in_m": 1e-10}, 3, 300)])
def test_decimal_units_land_on_the_grid(unit, value, pm):
    model = parse(v1({"length": unit}, plate([{"name": "a", "type": "rect", "x": 0, "y": 0, "w": value,
                                                "h": value, "material": "Si"}])))
    assert model.components["xs"].features[0].data["w"] == pm
    assert model.roundings == []


def test_a_residue_is_rounded_once_and_reported():
    w = 0.1 + 0.2                                     # 0.30000000000000004 um
    model = parse(v1({"length": "um"}, plate([{"name": "a", "type": "rect", "x": 0, "y": 0, "w": w, "h": 1,
                                                "material": "Si"}])))
    assert model.components["xs"].features[0].data["w"] == 300000
    (r,) = model.roundings
    assert r.path == "geometry.components.xs.features[0].w" and r.written == repr(w)
    assert r.displacement_pm == Fraction(-4, 10 ** 11)


def test_an_expression_is_exact_before_the_one_rounding():
    model = parse(v1({"length": "um"}, plate([{"name": "a", "type": "rect", "x": 0, "y": 0, "w": "0.1 + 0.2",
                                                "h": 1, "material": "Si"}])))
    assert model.components["xs"].features[0].data["w"] == 300000 and model.roundings == []


@pytest.mark.parametrize("value, pm", [(0.5, 0), (1.5, 2), (2.5, 2), (-0.5, 0), (-1.5, -2)])
def test_rounding_is_half_to_even(value, pm):
    model = parse(v1({"length": "pm"}, plate([{"name": "a", "type": "circle", "cx": value, "cy": 5, "r": 1,
                                                "material": "Si"}])))
    assert model.components["xs"].features[0].data["cx"] == pm


def test_out_of_range_and_undeclared_units_are_refused():
    with pytest.raises(GeometryError, match="2\\^63"):
        parse(v1({"length": "m"}, {"xs": {"dimension": "2d", "domain": {"xmin": 0, "xmax": 1e7, "ymin": 0,
                                                                       "ymax": 1}}}))
    with pytest.raises(GeometryError, match="units.length"):
        parse(v1({}, plate([])))
    with pytest.raises(GeometryError, match="unknown length unit"):
        parse(v1({"length": "furlong"}, plate([])))
    assert pm_per_unit({"length": "um"}) == 10 ** 6


# ----------------------------------------------------------------- S1-3: expressions and kinds

def _param_doc(params, w="w"):
    return v1({"length": "nm"}, plate([{"name": "a", "type": "rect", "x": 0, "y": 0, "w": w, "h": 1,
                                         "material": "Si"}]), params)


def test_parameters_and_kinds():
    params = {"w": {"value": "base * f + 2 * pad"}, "base": {"value": 3}, "pad": {"value": "1/4"},
              "f": {"value": "4 * pad / base", "kind": "ratio"}}
    model = parse(_param_doc(params))
    assert model.parameters["f"] == (Fraction(1, 3), "ratio")
    assert model.parameters["w"] == (Fraction(3, 2), "length")
    assert model.components["xs"].features[0].data["w"] == 1500


@pytest.mark.parametrize("params, w, message", [
    ({"a": {"value": "b"}, "b": {"value": "a"}}, "a", "cycle a -> b -> a"),
    ({"a": {"value": "1 / (2 - 2)"}}, "a", "division by zero"),
    ({"a": {"value": 2}, "b": {"value": 3}}, "a * b", "length \\* length"),
    ({"a": {"value": 2}, "r": {"value": 1, "kind": "ratio"}}, "a + r", "mixes kinds"),
    ({"a": {"value": 2}}, "1 / a", "inverse length"),
    ({"a": {"value": 2}}, "sqrt(a)", "unknown parameter 'sqrt'"),
    ({"a": {"value": 2}}, "a ^ 2", "cannot read"),
    ({"a": {"value": 2, "kind": "angle"}}, "a", "reserved"),
    ({"a": {"value": 5, "range": [0, 4]}}, "a", "outside its range"),
    ({"r": {"value": 2, "kind": "ratio"}}, "r", "expected a length"),
])
def test_expression_errors_name_the_problem(params, w, message):
    with pytest.raises(GeometryError, match=message):
        parse(_param_doc(params, w))


# ----------------------------------------------------------------- S1-4: validation

@pytest.mark.parametrize("features, extra, message", [
    ([{"name": "Top", "type": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "material": "Si"}], {},
     "cannot serve as an id"),
    ([{"name": "a", "id": "LEFT", "type": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "material": "Si"}], {},
     "reserved"),
    ([{"name": "a", "type": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "material": "Si"},
      {"name": "b", "id": "A", "type": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "material": "Si"}], {},
     "used twice"),
    ([{"name": "background", "type": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "material": "Si"}], {},
     "'background' is reserved"),
    ([{"name": "a", "region": "pad", "type": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "material": "Si"},
      {"name": "b", "region": "pad", "type": "rect", "x": 2, "y": 0, "w": 1, "h": 1, "material": "Cu"}], {},
     "different materials"),
    ([{"name": "a", "type": "ellipse", "material": "Si"}], {}, "reserved"),
    ([{"name": "a", "type": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "material": "Si", "rotation": 0.1}], {},
     "rotation: reserved"),
    ([], {"periodic": True}, "periodic: reserved"),
    ([{"name": "a", "type": "polygon", "points": [[0, 0], [2, 2], [2, 0], [0, 1]], "material": "Si"}], {},
     "intersect"),
    ([{"name": "a", "type": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "material": "Si"}],
     {"selections": {"s": {"region": {"inside": "a"}}}}, "inside: reserved"),
    ([{"name": "a", "type": "rect", "x": 0, "y": 0, "w": 1, "h": 1, "material": "Si"}],
     {"boundary_tags": [{"tag": "a", "select": {"boundary": "a.top"}}]}, "also a region name"),
])
def test_validation_refuses_by_name(features, extra, message):
    with pytest.raises(GeometryError, match=message):
        parse(v1({"length": "um"}, plate(features, **extra)))


def test_a_feature_below_the_mesher_tolerance_is_refused():
    comp = {"xs": {"dimension": "2d", "domain": {"xmin": 0, "xmax": 0.1, "ymin": 0, "ymax": 0.1},
                   "background": {"material": "SiO2"},
                   "features": [{"name": "film", "type": "rect", "x": 0, "y": 0, "w": 0.1, "h": 1e-9,
                                 "material": "Si"}]}}
    with pytest.raises(GeometryError, match="'film' is 1000 pm across.*below the mesher tolerance"):
        parse(v1({"length": "m"}, comp))


def test_selections_and_tags_are_accepted():
    model = parse(v1({"length": "um"}, plate(
        [{"name": "core", "type": "rect", "x": 1, "y": 1, "w": 2, "h": 1, "material": "Si"},
         {"name": "pad", "type": "polygon", "points": [[5, 5], [7, 5], [6, 7]], "edges": ["base", "r", "l"],
          "material": "Cu"}],
        selections={"wall": {"boundary": {"between": ["core", "exterior"]}},
                    "metal": {"region": {"material": "Cu"}}},
        boundary_tags=[{"tag": "terminal", "select": {"boundary": "pad.base"}}])))
    assert model.components["xs"].region_names == ["core", "pad"]


def test_imprint_is_parsed_but_refused_by_the_02_compiler():
    model = parse(v1({"length": "um"}, plate([{"name": "a", "type": "rect", "x": 0, "y": 0, "w": 1, "h": 1,
                                                "material": "Si"}], finalize="imprint")))
    assert model.components["xs"].finalize == "imprint"
    with pytest.raises(GeometryError, match="imprint' needs the stage 2 engine"):
        to_v02(model)


def test_void_is_parsed_but_refused_by_the_02_compiler():
    model = parse(v1({"length": "um"}, plate([{"name": "hole", "type": "rect", "x": 0, "y": 0, "w": 1, "h": 1,
                                                "material": None}])))
    with pytest.raises(GeometryError, match="void .material null. needs the stage 2 engine"):
        to_v02(model)


def test_trapezoid_compiles_to_its_exact_corners():
    model = parse(v1({"length": "m"}, plate([{"name": "t", "type": "trapezoid", "cx": 5, "y": 1, "w": 3,
                                               "w_top": "2.8", "h": 0.035, "material": "Cu"}])))
    (s,) = to_v02(model)["shapes"]
    assert s["type"] == "polygon"
    assert s["points"] == [[3.5, 1.0], [6.5, 1.0], [6.4, 1.035], [3.6, 1.035]]


# ----------------------------------------------------------------- S1-5: 2.5D compile

def _chip_footprint():
    d = Domain(size=0.8)
    d.add_region("die_zone", rectangle(-2, -2, 2, 2))
    d.add_region("rest", rectangle(-5, -5, 5, 5), holes=[rectangle(-2, -2, 2, 2)])
    return generate(d, box_sides(-5, 5, -5, 5))


def test_layers_reproduce_the_extrude_example_exactly():
    footprint = _chip_footprint()
    direct = extrude(footprint, [0.0, 1.0, 1.5, 2.5],
                     {"die_zone": ["substrate", "die", "mold"], "rest": ["substrate", "mold", "mold"]}, size=0.4)
    dom = {"xmin": -5, "xmax": 5, "ymin": -5, "ymax": 5}
    doc = v1({"length": "um"}, {
        "plan": {"dimension": "2d", "domain": dom, "background": {"material": "mold"},
                 "features": [{"name": "rest", "type": "rect", "x": -5, "y": -5, "w": 10, "h": 10, "material": "mold"},
                              {"name": "die_zone", "type": "rect", "x": -2, "y": -2, "w": 4, "h": 4,
                               "material": "die"}]},
        "pkg": {"dimension": "3d", "domain": {**dom, "zmin": 0, "zmax": 2.5}, "background": {"material": None},
                "features": [{"name": "stack", "type": "layers", "z0": 0, "layers": [
                    {"name": "sub", "thickness": 1, "footprint": "plan",
                     "map": {"die_zone": "substrate", "rest": "substrate"}},
                    {"name": "mid", "thickness": 0.5, "footprint": "plan", "map": {"rest": "mold"}},
                    {"name": "cap", "thickness": 1, "footprint": "plan", "map": {"die_zone": "mold"}}]}]}})
    model = parse(doc)
    stack = layer_stack(model, "pkg")
    assert stack.levels == [0, 1000000, 1500000, 2500000]
    compiled = extrude(footprint, [model.to_unit(z) for z in stack.levels],
                       stack.table_for(footprint.region_names), size=0.4)
    np.testing.assert_array_equal(compiled.nodes, direct.nodes)
    np.testing.assert_array_equal(compiled.tetrahedra, direct.tetrahedra)
    np.testing.assert_array_equal(compiled.regions, direct.regions)
    assert compiled.region_names == direct.region_names
    assert sorted(compiled.boundary_faces) == sorted(direct.boundary_faces)
    for tag in direct.boundary_faces:
        np.testing.assert_array_equal(compiled.boundary_faces[tag], direct.boundary_faces[tag])


def test_layer_cells_take_an_explicit_region_name():
    doc = v1({"length": "um"}, {
        "plan": {"dimension": "2d", "domain": {"xmin": 0, "xmax": 4, "ymin": 0, "ymax": 4},
                 "background": {"material": "FR4"},
                 "features": [{"name": "via", "type": "circle", "cx": 2, "cy": 2, "r": 0.5, "material": "Cu"}]},
        "pkg": {"dimension": "3d", "domain": {"xmin": 0, "xmax": 4, "ymin": 0, "ymax": 4, "zmin": 0, "zmax": 2},
                "background": {"material": None},
                "features": [{"name": "stack", "type": "layers", "z0": 0, "layers": [
                    {"name": "a", "thickness": 1, "footprint": "plan",
                     "map": {"via": {"material": "Cu", "region": "via_a"}}},
                    {"name": "b", "thickness": 1, "material": "FR4", "region": "cap"}]}]}})
    stack = layer_stack(parse(doc), "pkg")
    assert stack.table == {"via": ["via_a", "cap"], "background": ["FR4", "cap"]}
    assert stack.materials == {"via_a": "Cu", "FR4": "FR4", "cap": "FR4"}


# ----------------------------------------------------------------- S1-6: analytic checks

def _heat_flow(mesh, kappa_of_region):
    from galerkin import assemble_stiffness_3d, from_mesher, solve_dirichlet
    g = from_mesher(mesh)
    kappa = np.array([kappa_of_region[n] for n in mesh.region_names])[mesh.regions]
    K = assemble_stiffness_3d(g, eps=kappa)
    bottom, top = mesh.boundary_nodes["z0"], mesh.boundary_nodes["z1"]
    T = solve_dirichlet(K, np.zeros(g.num_nodes), {tuple(bottom): 0.0, tuple(top): 1.0})
    return float((K @ T)[top].sum())


def test_series_layers_match_the_thermal_resistance():
    t = {"A": 0.3, "B": 1.2, "C": 0.5}
    k = {"A": 150.0, "B": 1.3, "C": 20.0}
    doc = v1({"length": "um"}, {
        "pkg": {"dimension": "3d", "domain": {"xmin": 0, "xmax": 2, "ymin": 0, "ymax": 1, "zmin": 0, "zmax": 2},
                "background": {"material": None},
                "features": [{"name": "stack", "type": "layers", "z0": 0, "layers": [
                    {"name": n, "thickness": t[n], "material": n} for n in "ABC"]}]}})
    stack = layer_stack(parse(doc), "pkg")
    d = Domain(size=0.5)
    d.add_region("plate", rectangle(0, 0, 2, 1))
    footprint = generate(d, box_sides(0, 2, 0, 1))
    mesh = extrude(footprint, [z / 1e6 for z in stack.levels], stack.table_for(footprint.region_names),
                   divisions=2)
    q = _heat_flow(mesh, k)
    expected = 1.0 * 2.0 / sum(t[n] / k[n] for n in "ABC")
    assert abs(q - expected) <= 1e-9 * expected


def test_a_via_in_void_matches_its_polygon_resistance():
    r, n, length, sigma = 0.15, 32, 1.0, 5.8
    doc = v1({"length": "um"}, {
        "plan": {"dimension": "2d", "domain": {"xmin": -1, "xmax": 1, "ymin": -1, "ymax": 1},
                 "background": {"material": None},
                 "features": [{"name": "via", "type": "circle", "cx": 0, "cy": 0, "r": r, "material": "Cu"}]},
        "pkg": {"dimension": "3d", "domain": {"xmin": -1, "xmax": 1, "ymin": -1, "ymax": 1, "zmin": 0, "zmax": 1},
                "background": {"material": None},
                "features": [{"name": "stack", "type": "layers", "z0": 0, "layers": [
                    {"name": "core", "thickness": length, "footprint": "plan"}]}]}})
    stack = layer_stack(parse(doc), "pkg")
    assert stack.table == {"via": ["Cu"]}
    d = Domain(size=0.2)
    hole = Circle((0, 0), r, n=n)
    d.add_region("via", hole, size=0.05)
    d.add_region("rest", rectangle(-1, -1, 1, 1), holes=[hole])
    footprint = generate(d, box_sides(-1, 1, -1, 1))
    table = stack.table_for(["via"])
    table["rest"] = [None]
    mesh = extrude(footprint, [z / 1e6 for z in stack.levels], table, divisions=3)
    tri = footprint.nodes[footprint.triangles]
    u, v = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    area = 0.5 * np.abs(u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0])
    a_poly = float(area[np.asarray(footprint.regions) == footprint.region_names.index("via")].sum())
    q = _heat_flow(mesh, {"Cu": sigma})
    expected = sigma * a_poly * 1.0 / length
    assert abs(q - expected) <= 1e-9 * expected
    # The footprint polygon, not the circle, is what the mesh carries.
    assert abs(a_poly / (np.pi * r * r) - 1) < 0.02



def test_the_reader_imports_without_the_solver_chain():
    import subprocess
    import sys
    code = ("import sys, simcase.geometry_document; "
            "print(sorted(m for m in ('shapely', 'scipy', 'galerkin', 'meshine', 'matplotlib') if m in sys.modules))")
    assert subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          check=True).stdout.split() == ["[]"]


# ----------------------------------------------------------------- 1b: documents with version 1 geometry

def _as_v1(name):
    doc = copy.deepcopy(DOCS[name])
    doc["geometry"] = from_v02(doc["geometry"])
    return doc


@pytest.mark.parametrize("name", sorted(DOCS))
def test_a_document_with_version_1_geometry_runs_the_same_input(name):
    from simcase import Document
    v1_doc = _as_v1(name)
    doc = Document.from_dict(copy.deepcopy(v1_doc))
    assert doc.data == Document.from_dict(copy.deepcopy(DOCS[name])).data
    assert doc.geometry_source == v1_doc["geometry"] and doc.geometry_roundings == []
    assert doc.to_dict()["geometry"] == v1_doc["geometry"]
    assert doc.copy().to_dict() == doc.to_dict()


def test_a_thermal_region_document_agrees_with_the_0_2_route():
    """The version 1 copy of the region heat example is meshed by the exact engine (stage 2),
    the 0.2 original by the shapely route. The loops reach meshine in a different vertex
    order, so the refined meshes differ and bitwise identity is not expected (contract,
    "Internal grid"); the results agree at discretization level. Measured 2026-11-04:
    595 vs 597 nodes, maximum temperature 6e-4 and mean temperature 4e-4 of the
    temperature rise apart."""
    from simcase import Document, run
    a = run(Document.from_dict(copy.deepcopy(DOCS["builtin:thermal_regions"])), verbose=False)
    b = run(Document.from_dict(_as_v1("builtin:thermal_regions")), verbose=False)
    rise = a.temperature_k.max() - a.temperature_k.min()
    assert abs(len(a.mesh_nodes_m) - len(b.mesh_nodes_m)) <= 0.05 * len(a.mesh_nodes_m)
    assert abs(a.temperature_k.max() - b.temperature_k.max()) <= 2e-3 * rise
    assert abs(a.temperature_k.mean() - b.temperature_k.mean()) <= 2e-3 * rise
    assert abs(a.temperature_k.min() - b.temperature_k.min()) <= 2e-3 * rise


def test_save_keeps_the_version_1_block_and_roundings_become_notes(tmp_path):
    from simcase import Document
    doc_v1 = _as_v1("builtin:soi_strip")
    feature = doc_v1["geometry"]["components"]["main"]["features"][0]
    feature["w"] = feature["w"] + 1e-13                     # a residue below 1 pm in micrometres
    doc = Document.from_dict(copy.deepcopy(doc_v1))
    assert len(doc.geometry_roundings) == 1
    assert any("onto the 1 pm grid" in n for n in doc.notes)
    doc.save(tmp_path / "m.json")
    saved = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))
    assert saved["geometry"] == doc_v1["geometry"]
    assert Document.load(tmp_path / "m.json").data == doc.data


def test_an_invalid_version_1_block_is_a_document_error():
    from simcase import Document, DocumentError
    doc = _as_v1("builtin:soi_strip")
    doc["geometry"]["components"]["main"]["features"][0]["rotation"] = 0.3
    with pytest.raises(DocumentError, match="rotation: reserved"):
        Document.from_dict(doc)


def test_the_version_1_example_reads_as_the_soi_strip_example():
    from simcase import Document
    path = ROOT / "examples" / "simcase" / "geometry_v1_soi_strip.json"
    doc = Document.load(path)
    reference = Document.load(ROOT / "examples" / "simcase" / "soi_strip.json")
    assert {k: v for k, v in doc.data.items() if k != "name"} == \
        {k: v for k, v in reference.data.items() if k != "name"}
    assert doc.geometry_roundings == [] and doc.to_dict()["geometry"]["version"] == 1
