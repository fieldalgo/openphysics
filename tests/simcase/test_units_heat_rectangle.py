# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Format 0.3 heat rectangle checks of the units and naming batch (heat rows of P2-4, P2-5,
P2-6, P2-9, P2-11, P2-14 and P2-19). The region and axisymmetric rows are in
test_units_heat_regions.py."""
import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

import simcase
from physmat import units
from simcase import Document, DocumentError, examples, run

RECTANGLES = ("thermal_slab", "thermal_mixed", "thermal_boundary", "transient_thermal_uniform",
              "transient_thermal_boundary", "gallery_heated_plate")


def example(name):
    if name in examples.EXAMPLES:
        return copy.deepcopy(examples.EXAMPLES[name])
    path = Path(__file__).resolve().parents[2]/"examples"/"simcase"/(name+".json")   # a gallery document
    return json.loads(path.read_text(encoding="utf-8"))


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
    arrays = {}
    if (path/"fields.npz").exists():
        with np.load(path/"fields.npz", allow_pickle=False) as archive:
            arrays = {key: archive[key] for key in archive.files if key != "metadata_json"}
    return result, path, summary, arrays


def same_arrays(a, b):
    assert set(a) == set(b)
    for key in a:
        assert a[key].dtype == b[key].dtype and a[key].shape == b[key].shape, key
        assert a[key].tobytes() == b[key].tobytes(), key


#: summary keys that hold the authored text, wall times or findings, not results
TEXTUAL = ("resolved_inputs", "defaults_applied", "diagnostics", "extent", "timing")


def results_of(summary):
    return hexed({key: value for key, value in summary.items() if key not in TEXTUAL})


# ---- P2-4: unit spelling invariance ------------------------------------------------------

def factor(unit, quantity):
    return units.convert(f"1 {unit}", quantity, path="factor").value


HEAT = "physics.heat1."
#: (path, spelling, menu unit?) rewrites of transient_thermal_boundary; menu units change the number
SPELLINGS = [
    ("thermal_conductivity", "50 W/m/K", False), ("thermal_conductivity", "50 W m^-1 K^-1", False),
    ("thermal_conductivity", "0.5 W/(cm K)", True),
    ("volumetric_heat_capacity", "3600000 J m^-3 K^-1", False),
    ("volumetric_heat_capacity", "3.6 MJ/(m^3 K)", True), ("volumetric_heat_capacity", "3.6 J/(cm^3 K)", True),
    ("initial_temperature", "126.85 degC", True),
    ("convection.right.heat_transfer_coefficient", "500 W m^-2 K^-1", False),
    ("convection.right.heat_transfer_coefficient", "0.05 W/(cm^2 K)", True),
    ("convection.right.ambient_temperature", "26.85 degC", True),
]
#: character aliases: the same value, read with a spelling fix and no error
ALIASES = [("initial_temperature", "126.85 ℃"), ("initial_temperature", "400 K"),
           ("heat_source_density", "−0 W/m^3"), ("convection.right.ambient_temperature", "26.85 °C")]


def put(data, path, value):
    node = data["physics"]["heat1"]
    keys = path.split(".")
    for key in keys[:-1]:
        node = node[key]
    node[keys[-1]] = value


def test_p2_4_spellings_and_menu_units_give_the_same_si_tree_and_saved_arrays(tmp_path):
    base = example("transient_thermal_boundary")
    _, _, base_summary, base_arrays = saved(base, tmp_path/"base")
    base_si = hexed(Document.from_dict(copy.deepcopy(base)).si)
    rewrites = [(path, text, menu) for path, text, menu in SPELLINGS]
    rewrites.append(("study.time", {"unit": "ms", "values": [0, 10000, 20000, 40000, 80000]}, True))
    for i, (path, value, menu) in enumerate(rewrites):
        data = copy.deepcopy(base)
        if path == "study.time":
            assert factor("ms", "time") != 1
            data["study"]["time"] = value
        else:
            if menu:
                unit = value.split(" ", 1)[1]
                quantity = path.split(".")[-1]
                assert factor(unit, quantity) != 1, (path, value)
            put(data, path, value)
        doc = Document.from_dict(data)
        assert not [d for d in doc.diagnostics if d.severity == "error"]
        assert hexed(doc.si) == base_si, (path, value)
        if menu:
            _, _, summary, arrays = saved(data, tmp_path/f"v{i}")
            same_arrays(arrays, base_arrays)
            assert results_of(summary) == results_of(base_summary), (path, value)


@pytest.mark.parametrize("path,text", ALIASES)
def test_p2_4_character_aliases_carry_a_fix_and_no_error(path, text):
    base = example("transient_thermal_boundary")
    data = copy.deepcopy(base)
    put(data, path, text)
    doc = Document.from_dict(data)
    assert not [d for d in doc.diagnostics if d.severity == "error"]
    assert hexed(doc.si) == hexed(Document.from_dict(base).si)
    assert [fix["path"] for fix in doc.spelling_fixes()] == [HEAT+path]


# ---- P2-5: geometry length_unit invariance ---------------------------------------------------

def slab_in(unit, scale):
    data = example("thermal_slab")            # 30 mm x 20 mm
    data["geometry"]["length_unit"] = unit
    data["geometry"]["domain"] = {"xmin": 0, "xmax": 30*scale, "ymin": 0, "ymax": 20*scale}
    return data


def pm_counts(doc):
    return [doc.pm(f"geometry.domain.{key}") for key in ("xmin", "xmax", "ymin", "ymax")]


def test_p2_5_length_unit_rewrites_give_the_same_pm_counts_meshes_arrays_and_summary(tmp_path):
    base = slab_in("mm", 1)
    doc = Document.from_dict(base)
    _, _, summary, arrays = saved(base, tmp_path/"mm")
    for unit, scale in (("m", "0.001"), ("um", 1000), ("nm", 1000000)):
        data = example("thermal_slab")
        data["geometry"]["length_unit"] = unit
        data["geometry"]["domain"] = {"xmin": 0, "xmax": json.loads(f"{30*float(scale):.12g}"),
                                      "ymin": 0, "ymax": json.loads(f"{20*float(scale):.12g}")}
        assert pm_counts(Document.from_dict(data)) == pm_counts(doc), unit
        _, _, other, raw = saved(data, tmp_path/unit)
        same_arrays(raw, arrays)
        assert results_of(other) == results_of(summary), unit
    # exact inch and mil numbers: a plate 4 x 0.8 in is 101.6 x 20.32 mm
    plate = {"in": (4, 0.8), "mm": (101.6, 20.32), "mil": (4000, 800)}
    counts, runs = {}, {}
    for unit, (w, h) in plate.items():
        data = example("thermal_slab")
        data["geometry"]["length_unit"] = unit
        data["geometry"]["domain"] = {"xmin": 0, "xmax": w, "ymin": 0, "ymax": h}
        counts[unit] = pm_counts(Document.from_dict(data))
        runs[unit] = saved(data, tmp_path/("plate-"+unit))[3]
    assert counts["in"] == counts["mm"] == counts["mil"]
    same_arrays(runs["in"], runs["mm"])
    same_arrays(runs["mil"], runs["mm"])


def test_p2_5_transient_length_unit_conversion_is_exact(tmp_path):
    # the length-conversion half of the former runtime negative-kelvin test
    data = example("transient_thermal_uniform")
    data["mesh"]["subdivision_count"] = [2, 2]
    data["physics"]["heat1"]["heat_source_density"] = "-8 W/m^3"
    metres = saved(data, tmp_path/"m")[3]
    data["geometry"]["length_unit"] = "mm"
    data["geometry"]["domain"] = {"xmin": 0, "xmax": 1000, "ymin": 0, "ymax": 1000}
    same_arrays(saved(data, tmp_path/"mm")[3], metres)


def test_p2_5_negative_controls():
    slab = example("thermal_slab")
    slab["geometry"]["length_unit"] = "m"        # 30 m x 20 m: the mm-as-m pattern
    doc = Document.from_dict(slab)
    assert [(d.code, d.path) for d in doc.diagnostics if d.code == "W-GEOMETRY-SCALE"] == [
        ("W-GEOMETRY-SCALE", "geometry")]
    # stated residual, asserted so that it stays visible: a transient rectangle declared mm
    # (0.05 mm x 0.01 mm) raises no check yet (W-TIME-SCALE is deferred)
    boundary = example("transient_thermal_boundary")
    boundary["geometry"]["length_unit"] = "mm"
    found = list(Document.from_dict(boundary).diagnostics)
    assert [d for d in found if d.severity != "info"] == []
    assert {d.code for d in found} <= {"I-DEFAULT-BOUNDARY"}       # the insulated sides, listed


# ---- P2-6: depth invariance -------------------------------------------------------------------

@pytest.mark.parametrize("name", ["thermal_boundary", "transient_thermal_boundary"])
def test_p2_6_depth_changes_totals_only(tmp_path, name):
    runs = {}
    for depth in (None, "1 m", "40 mm"):
        data = example(name)
        data["geometry"]["depth"] = depth
        runs[depth] = saved(data, tmp_path/str(depth).replace(" ", ""))
    base_summary, base_arrays = runs[None][2], runs[None][3]
    per_depth = {k: v for k, v in base_summary.items() if k.endswith("_per_depth")}
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


def test_p2_6_depth_refusals():
    data = example("thermal_slab")
    del data["geometry"]["depth"]
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    assert ("E-KEY-MISSING", "geometry.depth") in [(d.code, d.path) for d in caught.value.diagnostics]
    data["geometry"]["depth"] = "0 m"
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    assert [(d.code, d.path) for d in caught.value.diagnostics if d.severity == "error"] == [
        ("E-DOMAIN", "geometry.depth")]


# ---- P2-9: diagnostics are never lost ----------------------------------------------------------

def magnitude(acknowledged):
    data = example("transient_thermal_uniform")
    if not acknowledged:
        data["physics"]["heat1"]["volumetric_heat_capacity"] = "4 J/(m^3 K)"
    path = "physics.heat1.volumetric_heat_capacity" + (".value" if acknowledged else "")
    return data, path


@pytest.mark.parametrize("acknowledged", [True, False])
def test_p2_9_a_magnitude_warning_reaches_every_output(tmp_path, capsys, acknowledged):
    from simcase.cli import main
    data, where = magnitude(acknowledged)
    model = tmp_path/"model.json"
    model.write_text(json.dumps(data), encoding="utf-8")
    assert main(["validate", str(model)]) == 0
    text = capsys.readouterr().out
    assert "W-MAGNITUDE" in text and where in text
    assert main(["validate", str(model), "--json"]) == 0
    found = [(d["code"], d["path"]) for d in json.loads(capsys.readouterr().out)["diagnostics"]]
    assert ("W-MAGNITUDE", where) in found
    assert main(["validate", str(model), "--strict"]) == (0 if acknowledged else 3)
    capsys.readouterr()
    assert main(["run", str(model), "-o", str(tmp_path/"out")]) == 0
    assert "W-MAGNITUDE" in capsys.readouterr().out
    out = tmp_path/"out"
    assert "W-MAGNITUDE" in (out/"log.txt").read_text(encoding="utf-8")
    summary = json.loads((out/"summary.json").read_text(encoding="utf-8"))
    entries = [d for d in summary["diagnostics"] if d["code"] == "W-MAGNITUDE"]
    assert [d["path"] for d in entries] == [where]
    assert bool(entries[0].get("acknowledged")) is acknowledged
    with np.load(out/"fields.npz", allow_pickle=False) as archive:
        assert json.loads(str(archive["metadata_json"]))["diagnostics"] == summary["diagnostics"]
    # the count never drops between reading, validating and the result
    doc = Document.from_dict(copy.deepcopy(data))
    count = len(doc.diagnostics)
    doc.validate()
    assert len(doc.diagnostics) == count
    assert len(run(doc, verbose=False).summary()["diagnostics"]) == count
    bad = copy.deepcopy(data)
    bad["physics"]["heat1"]["thermal_conductivity"] = "-1 W/(m K)"
    model.write_text(json.dumps(bad), encoding="utf-8")
    assert main(["validate", str(model)]) == 2


def test_p2_9_studio_validation_returns_the_diagnostics():
    pytest.importorskip("fastapi", reason="install the Studio extra: pip install 'simcase[studio]'")
    from fastapi.testclient import TestClient
    from simcase.studio import server
    data, where = magnitude(False)
    with TestClient(server.app) as client:
        reply = client.post("/api/thermal/transient/validate",
                            json={"doc": data, "client_revision": 1, "request_seq": 1}).json()
    assert reply["ok"] is True
    assert ("W-MAGNITUDE", where) in [(d["code"], d["path"]) for d in reply["diagnostics"]]


# ---- P2-11: result names and metadata ----------------------------------------------------------

UNIT_TOKEN = re.compile(r"_(k|m|s|w|j|jk|pa|deg|m2|um|nm|hz|v|a|w_m2|w_mk|w_m3|w_m2k|j_m3k|s_m|s_per_m|n_m3|"
                        r"per_m|db_cm|db_90deg)$")


def keys(tree, skip=("resolved_inputs",)):
    if isinstance(tree, dict):
        for key, value in tree.items():
            yield key
            if key not in skip:
                yield from keys(value, skip)
    elif isinstance(tree, list):
        for item in tree:
            yield from keys(item, skip)


@pytest.mark.parametrize("name", RECTANGLES)
def test_p2_11_heat_result_names_and_units(tmp_path, name):
    from simcase.export import RETIRED_LAYOUTS, SUPPORTED_LAYOUTS
    from simcase.thermal import FIELDS_03 as STEADY
    from simcase.transient_thermal import FIELDS_03 as TRANSIENT
    result, _, summary, arrays = saved(example(name), tmp_path/"out")
    fields = TRANSIENT if result.doc.si["physics"]["heat1"]["type"] == "thermal.transient2d" else STEADY
    names = list(keys(summary)) + list(arrays)
    assert not [k for k in names if UNIT_TOKEN.search(k)]
    assert not [k for k in names if k.endswith("_unit")]
    for array, unit in summary["field_units"].items():
        quantity = fields[array][0]
        assert unit == units.quantity(quantity).unit, array
        assert units.convert(f"1 {unit}", quantity, path=array).value == 1.0
    assert set(summary["field_units"]) == {k for k, spec in fields.items() if spec[0] is not None} & set(
        summary["field_shapes"])
    assert summary["field_layout"] in SUPPORTED_LAYOUTS and not set(RETIRED_LAYOUTS) & set(SUPPORTED_LAYOUTS)


# ---- P2-14: sign sanity ------------------------------------------------------------------------

def test_p2_14_inward_heat_flux_heats_its_side():
    data = example("thermal_boundary")
    p = data["physics"]["heat1"]
    p.update(prescribed_temperature={"left": "300 K"}, inward_heat_flux={"right": "500 W/m^2"}, convection={},
             heat_source_density="0 W/m^3")
    result = run(Document.from_dict(data), verbose=False)
    x = result.node_coordinates[:, 0]
    right = np.isclose(x, x.max(), rtol=0, atol=1e-12)
    assert result.temperature[right].mean() > 300.
    side = np.ptp(result.node_coordinates[:, 1])
    total = result.outward_prescribed_heat_rate_per_depth.sum()
    assert total < 0
    np.testing.assert_allclose(total, -500.*side, rtol=1e-12, atol=0)


# ---- P2-19: the Studio heat document builder validates in Python ------------------------------

def test_p2_19_studio_heat_builder_output_validates():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed; the cjs suite runs the builder itself")
    # the builder of the imported simcase package (the installed wheel in the installed-package run)
    module = (Path(simcase.__file__).resolve().parent/"studio"/"static"/"workspace-heat.mjs").as_uri()
    script = (f"const H=await import({json.dumps(module)});"
              "const plate=(sides,extra={})=>({...H.DEFAULT_THERMAL,...extra,sides:{...H.DEFAULT_THERMAL.sides,...sides}});"
              "console.log(JSON.stringify([H.heatDocument(H.DEFAULT_THERMAL),"
              "H.heatDocument(plate({left:{type:'flux',inward_heat_flux:500},top:{type:'convection',h:10,ambient:290}},"
              "{source:1e5}))]));")
    done = subprocess.run([node, "--input-type=module", "-e", script], capture_output=True, text=True,
                          encoding="utf-8", check=True)
    for data in json.loads(done.stdout):
        doc = Document.from_dict(data)
        assert not [d for d in doc.diagnostics if d.severity == "error"]
    mixed = Document.from_dict(json.loads(done.stdout)[1])
    assert mixed.si["physics"]["heat1"]["inward_heat_flux"] == {"left": 500.0}    # the form's inward 500 (project 6)
