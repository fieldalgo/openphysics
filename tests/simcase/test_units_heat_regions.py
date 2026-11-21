# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Format 0.3 heat region and axisymmetric checks of the units and naming batch (the region
rows of P2-4, P2-6, P2-9 and P2-11; P2-5 is in test_thermal_length_canonical.py, P2-18 in
test_export_regions.py). The rectangle rows are in test_units_heat_rectangle.py."""
import copy
import json
import re
from pathlib import Path

import numpy as np
import pytest

from physmat import units
from simcase import Document, DocumentError, examples, run

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT/"tools"/"units_batch"/"fixtures"/"v03"
#: summary keys that hold the authored text, wall times or findings, not results
TEXTUAL = ("resolved_inputs", "defaults_applied", "diagnostics", "extent", "timing")


def example(name):
    if name in examples.EXAMPLES:
        return copy.deepcopy(examples.EXAMPLES[name])
    return json.loads((ROOT/"examples"/"simcase"/(name+".json")).read_text(encoding="utf-8"))


def fixture(name):
    return json.loads((FIXTURES/(name+".json")).read_text(encoding="utf-8"))


def hexed(value):
    """A tree with every float as its float.hex text, so that == is bitwise."""
    if isinstance(value, dict):
        return {key: hexed(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [hexed(item) for item in value]
    if isinstance(value, float):
        return value.hex()
    return value


def saved(data, out):
    result = run(Document.from_dict(copy.deepcopy(data)), verbose=False)
    path = result.save(out)
    summary = json.loads((path/"summary.json").read_text(encoding="utf-8"))
    with np.load(path/"fields.npz", allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files if key != "metadata_json"}
        metadata = json.loads(str(archive["metadata_json"]))
    return result, path, summary, arrays, metadata


def same_arrays(a, b):
    assert set(a) == set(b)
    for key in a:
        assert a[key].dtype == b[key].dtype and a[key].shape == b[key].shape, key
        assert a[key].tobytes() == b[key].tobytes(), key


def results_of(summary):
    return hexed({key: value for key, value in summary.items() if key not in TEXTUAL})


def put(data, path, value):
    """Set ``value`` at a dotted path such as ``geometry.shapes[1].element_size``."""
    node, keys = data, re.findall(r"[^.\[\]]+|\[\d+\]", path)
    for key in keys[:-1]:
        node = node[int(key[1:-1])] if key.startswith("[") else node[key]
    last = keys[-1]
    if last.startswith("["):
        node[int(last[1:-1])] = value
    else:
        node[last] = value


# ---- P2-4: unit spelling invariance (thermal_regions) -------------------------------------------

#: (path, text, quantity of a menu unit or None for a spelling of the same unit)
SPELLINGS = [
    ("materials.steel.thermal_conductivity", "45 W/m/K", None),
    ("materials.steel.thermal_conductivity", "45 W m^-1 K^-1", None),
    ("materials.steel.thermal_conductivity", "0.45 W/(cm K)", "thermal_conductivity"),
    ("materials.insulation.thermal_conductivity", "0.0004 W/(cm K)", "thermal_conductivity"),
    ("physics.heat1.heat_source_density.heater", "5e6 W m^-3", None),
    ("physics.heat1.heat_source_density.heater", "5 W/cm^3", "heat_source_density"),
    ("physics.heat1.prescribed_temperature.bottom", "26.85 degC", "prescribed_temperature"),
    ("physics.heat1.convection.top.heat_transfer_coefficient", "10 W m^-2 K^-1", None),
    ("physics.heat1.convection.top.heat_transfer_coefficient", "0.001 W/(cm^2 K)", "heat_transfer_coefficient"),
    ("physics.heat1.convection.top.ambient_temperature", "21.85 degC", "ambient_temperature"),
    ("mesh.element_size", "0.2 cm", "element_size"),
    ("mesh.element_size", "2000 um", "element_size"),
    ("geometry.shapes[1].element_size", "500 um", "element_size"),
]
#: character aliases: the same value, read with a spelling fix and no error
ALIASES = [("geometry.shapes[1].element_size", "500 µm"), ("geometry.shapes[1].element_size", "500 μm"),
           ("physics.heat1.prescribed_temperature.bottom", "26.85 ℃"),
           ("physics.heat1.convection.top.ambient_temperature", "295 K")]


def test_p2_4_region_spellings_and_menu_units_give_the_same_si_tree_and_saved_arrays(tmp_path):
    base = example("thermal_regions")
    _, _, base_summary, base_arrays, _ = saved(base, tmp_path/"base")
    base_si = hexed(Document.from_dict(copy.deepcopy(base)).si)
    for i, (path, text, quantity) in enumerate(SPELLINGS):
        if quantity is not None:      # a menu unit: its factor is not 1, so the number changes
            unit = text.split(" ", 1)[1]
            assert units.convert(f"1 {unit}", quantity, path="factor").value != 1, (path, text)
        data = copy.deepcopy(base)
        put(data, path, text)
        doc = Document.from_dict(data)
        assert not [d for d in doc.diagnostics if d.severity == "error"]
        assert hexed(doc.si) == base_si, (path, text)
        _, _, summary, arrays, _ = saved(data, tmp_path/f"v{i}")
        same_arrays(arrays, base_arrays)
        assert results_of(summary) == results_of(base_summary), (path, text)


@pytest.mark.parametrize("path,text", ALIASES)
def test_p2_4_region_character_aliases_carry_a_fix_and_no_error(path, text):
    base = example("thermal_regions")
    data = copy.deepcopy(base)
    put(data, path, text)
    doc = Document.from_dict(data)
    assert not [d for d in doc.diagnostics if d.severity == "error"]
    assert hexed(doc.si) == hexed(Document.from_dict(base).si)
    assert [fix["path"] for fix in doc.spelling_fixes()] == [path]


# ---- P2-6: depth invariance ---------------------------------------------------------------------

@pytest.mark.parametrize("name", ["thermal_regions", "transient_thermal_regions"])
def test_p2_6_region_depth_changes_totals_only(tmp_path, name):
    runs = {}
    for depth in (None, "1 m", "40 mm"):
        data = example(name)
        data["geometry"]["depth"] = depth
        runs[depth] = saved(data, tmp_path/str(depth).replace(" ", ""))
    base_summary, base_arrays = runs[None][2], runs[None][3]
    per_depth = {k: v for k, v in base_summary.items() if k.endswith("_per_depth")}
    # null: per-depth values only, no plain integrated name
    assert per_depth and not any(k[:-len("_per_depth")] in base_summary for k in per_depth)
    for depth, metres in (("1 m", 1.0), ("40 mm", 0.04)):
        summary, arrays = runs[depth][2], runs[depth][3]
        same_arrays(arrays, base_arrays)
        for key, value in per_depth.items():
            assert hexed(summary[key]) == hexed(value), key
            total = summary[key[:-len("_per_depth")]]
            if "value" in value:
                assert total["value"].hex() == (value["value"]*metres).hex(), key
            else:
                assert [v.hex() for v in total["values"]] == [(v*metres).hex() for v in value["values"]], key


@pytest.mark.parametrize("name", ["heat_axisymmetric_cylinder", "heat_axisymmetric_cylinder_transient"])
def test_p2_6_axisymmetric_results_have_no_per_depth_name_and_refuse_a_depth(tmp_path, name):
    data = fixture(name)
    _, _, summary, arrays, _ = saved(data, tmp_path/"out")
    names = list(keys(summary)) + list(arrays)
    assert not [k for k in names if "_per_depth" in k]
    assert summary["coordinate_system"] == "axisymmetric" and "depth" not in summary
    component = next(iter(data["geometry"]["components"]))
    for where, path in ((("geometry", "components", component), f"geometry.components.{component}.depth"),
                        (("geometry",), "geometry.depth")):
        bad = copy.deepcopy(data)
        node = bad
        for key in where:
            node = node[key]
        node["depth"] = "1 m"
        with pytest.raises(DocumentError) as caught:
            Document.from_dict(bad)
        assert [(d.code, d.path) for d in caught.value.diagnostics if d.severity == "error"] == [
            ("E-KEY-UNKNOWN", path)]


def test_p2_6_region_depth_refusals():
    data = example("thermal_regions")
    del data["geometry"]["depth"]
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    assert ("E-KEY-MISSING", "geometry.depth") in [(d.code, d.path) for d in caught.value.diagnostics]
    data["geometry"]["depth"] = "0 m"
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    assert [(d.code, d.path) for d in caught.value.diagnostics if d.severity == "error"] == [
        ("E-DOMAIN", "geometry.depth")]


# ---- P2-9: diagnostics are never lost ------------------------------------------------------------

def noisy():
    """The steady region example with a shape number 1e-4 pm and one 0.1 pm off the 1 pm grid, an
    unread material property and two sides without a condition."""
    data = example("thermal_regions")
    plate = data["geometry"]["shapes"][0]
    plate["x"] = 5.000000000000001         # the next double above 5 mm: about 9e-7 pm off the grid
    plate["h"] = 6.0000000001              # 0.1 pm: rounded to the grid with a warning
    data["materials"]["steel"]["electrical_conductivity"] = "1e6 S/m"
    return data


EXPECTED = [("I-PM-ROUNDING", "geometry.shapes[0].x"), ("W-PM-ROUNDING", "geometry.shapes[0].h"),
            ("I-UNUSED-PROPERTY", "materials.steel.electrical_conductivity"),
            ("I-DEFAULT-BOUNDARY", "physics.heat1.inward_heat_flux.left"),
            ("I-DEFAULT-BOUNDARY", "physics.heat1.inward_heat_flux.right")]


def pairs(diagnostics):
    return sorted((d["code"], d["path"]) if isinstance(d, dict) else (d.code, d.path) for d in diagnostics)


def test_p2_9_region_diagnostics_reach_every_output(tmp_path, capsys):
    from simcase.cli import main
    data = noisy()
    doc = Document.from_dict(copy.deepcopy(data))
    assert pairs(doc.diagnostics) == sorted(EXPECTED)
    model = tmp_path/"model.json"
    model.write_text(json.dumps(data), encoding="utf-8")
    assert main(["validate", str(model)]) == 0
    text = capsys.readouterr().out
    for code, path in EXPECTED:
        assert f"{code} at {path}" in text, (code, path)
    assert main(["validate", str(model), "--json"]) == 0
    assert pairs(json.loads(capsys.readouterr().out)["diagnostics"]) == sorted(EXPECTED)
    assert main(["validate", str(model), "--strict"]) == 3      # W-PM-ROUNDING is a warning
    capsys.readouterr()
    assert main(["run", str(model), "-o", str(tmp_path/"out")]) == 0
    printed = capsys.readouterr().out
    out = tmp_path/"out"
    log = (out/"log.txt").read_text(encoding="utf-8")
    summary = json.loads((out/"summary.json").read_text(encoding="utf-8"))
    with np.load(out/"fields.npz", allow_pickle=False) as archive:
        metadata = json.loads(str(archive["metadata_json"]))
    for code, path in EXPECTED:
        assert f"{code} at {path}" in printed and f"{code} at {path}" in log, (code, path)
    assert pairs(summary["diagnostics"]) == sorted(EXPECTED)
    assert metadata["diagnostics"] == summary["diagnostics"]
    # the count never drops: reading, validating, the micrometre hand-off, meshing and the result
    from simcase.thermal_regions import build_region_mesh_03, handoff_03
    doc = Document.from_dict(copy.deepcopy(data))
    count = len(doc.diagnostics)
    doc.validate()
    assert len(doc.diagnostics) == count
    handoff_03(doc)
    build_region_mesh_03(doc)
    assert len(doc.diagnostics) == count
    assert pairs(run(doc, verbose=False).summary()["diagnostics"]) == sorted(EXPECTED)
    bad = copy.deepcopy(data)
    bad["materials"]["steel"]["thermal_conductivity"] = "-1 W/(m K)"
    model.write_text(json.dumps(bad), encoding="utf-8")
    assert main(["validate", str(model)]) == 2


@pytest.mark.parametrize("route,name", [("/api/thermal/validate", "thermal_regions"),
                                        ("/api/thermal/transient/validate", "transient_thermal_regions")])
def test_p2_9_studio_region_validation_returns_the_diagnostics(route, name):
    pytest.importorskip("fastapi", reason="install the Studio extra: pip install 'simcase[studio]'")
    from fastapi.testclient import TestClient
    from simcase.studio import server
    if name == "thermal_regions":
        data, expected = noisy(), sorted(EXPECTED)
    else:      # the transient example: its insulated top and bottom
        data = example(name)
        expected = [("I-DEFAULT-BOUNDARY", f"physics.heat1.inward_heat_flux.{side}") for side in ("bottom", "top")]
    with TestClient(server.app) as client:
        reply = client.post(route, json={"doc": data, "client_revision": 1, "request_seq": 1}).json()
    assert reply["ok"] is True
    assert pairs(reply["diagnostics"]) == expected


# ---- P2-11: result names and metadata ------------------------------------------------------------

UNIT_TOKEN = re.compile(r"_(k|m|s|w|j|jk|pa|deg|m2|um|nm|hz|v|a|w_m2|w_mk|w_m3|w_m2k|j_m3k|s_m|s_per_m|n_m3|"
                        r"per_m|db_cm|db_90deg)$")
#: arrays without a unit (connectivity, node indices, region ids)
STRUCTURAL = {"triangles", "prescribed_node_ids", "triangle_regions"}
REGIONS = [("example", "thermal_regions"), ("example", "transient_thermal_regions"), ("example", "layered_wall"),
           ("fixture", "heat_v1_interior_dirichlet"), ("fixture", "heat_transient_regions_sampled"),
           ("fixture", "heat_axisymmetric_core_shell"), ("fixture", "heat_axisymmetric_core_shell_transient")]


#: summary maps keyed by the document's own names (materials, regions, sides, selections)
NAMED = ("materials", "regions", "heat_source_density", "prescribed_temperature", "inward_heat_flux", "convection")


def keys(tree, skip=("resolved_inputs",)):
    """Every key of a summary tree, except the document's own names (their values are walked)."""
    if isinstance(tree, dict):
        for key, value in tree.items():
            yield key
            if key in skip:
                continue
            if key in NAMED and isinstance(value, dict) and "value" not in value and "values" not in value:
                for item in value.values():
                    yield from keys(item, skip)
            else:
                yield from keys(value, skip)
    elif isinstance(tree, list):
        for item in tree:
            yield from keys(item, skip)


@pytest.mark.parametrize("source,name", REGIONS, ids=[n for _, n in REGIONS])
def test_p2_11_region_result_names_and_units(tmp_path, source, name):
    from simcase.export import RETIRED_LAYOUTS, SUPPORTED_LAYOUTS
    data = example(name) if source == "example" else fixture(name)
    _, _, summary, arrays, _ = saved(data, tmp_path/"out")
    arrays = {k: v for k, v in arrays.items() if k not in ("result_format", "field_layout")}
    names = list(keys(summary)) + list(arrays)
    assert not [k for k in names if UNIT_TOKEN.search(k)]
    assert not [k for k in names if k.endswith("_unit")]
    assert set(summary["field_shapes"]) == set(arrays)
    for array in arrays:
        if array in STRUCTURAL:
            assert array not in summary["field_units"], array
            continue
        unit = summary["field_units"][array]          # a registry name: the array is its quantity
        assert unit == units.quantity(array).unit, array
        assert units.convert(f"1 {unit}", array, path=array).value == 1.0
    axisymmetric = summary.get("coordinate_system") == "axisymmetric"
    assert axisymmetric == ("axisymmetric" in name)
    assert axisymmetric == (not [k for k in names if k.endswith("_per_depth")])
    assert summary["field_layout"] in SUPPORTED_LAYOUTS and summary["field_layout"].endswith("-regions-v2")
    assert not set(RETIRED_LAYOUTS) & set(SUPPORTED_LAYOUTS)
