# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""em.cavity3d under the units and naming rules (units batch C9): P2-4, P2-5 (with the
W-CAVITY-SCALE negative control), P2-6, P2-7/P2-8 (the G4 A4 cavity rows), P2-9, P2-11, P2-15,
P2-16 and P2-18. P2-1 is test_units_batch_equivalence.py; the kept physics references (P2-17) are
test_cavity3d_integration.py, test_cavity3d_materials.py, test_cavity3d_persistence_validation.py,
test_gallery.py and the galerkin and refsol cavity tests."""

from __future__ import annotations

import ast
import copy
import dataclasses
import json
import re
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

import physmat
import simcase
from physmat import units
from simcase import Document, DocumentError, examples, run
from simcase.cavity import FIELDS, kernel_inputs

galerkin = pytest.importorskip("galerkin")

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_FILES = ROOT / "examples" / "simcase"
FIXTURES = ROOT / "tools" / "units_batch" / "fixtures" / "v03"
#: the imported simcase package: the source tree here, the installed wheel in the installed-package run
SIMCASE = Path(simcase.__file__).resolve().parent
P = "physics.em1."
TC = "exp(-i omega t)"
CAVITIES = ("cavity_box", "cavity_lossy_slab", "gallery_box_cavity")
TEXTUAL = ("resolved_inputs", "defaults_applied", "diagnostics", "extent", "timing")


def example(name):
    if name in examples.EXAMPLES:
        return copy.deepcopy(examples.EXAMPLES[name])
    return json.loads((EXAMPLE_FILES / f"{name}.json").read_text(encoding="utf-8"))


def hexed(value):
    """A tree with every float (and each part of a complex) as float.hex, so that == is bitwise."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return hexed(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {key: hexed(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [hexed(item) for item in value]
    if isinstance(value, complex):
        return ["complex", value.real.hex(), value.imag.hex()]
    if isinstance(value, float):
        return value.hex()
    return value


DELETE = object()


def put(data, path, value):
    """Set ``value`` at a dotted path such as ``geometry.shapes[0].zmax`` (DELETE removes it)."""
    node, keys = data, re.findall(r"[^.\[\]]+|\[\d+\]", path)
    for key in keys[:-1]:
        node = node[int(key[1:-1])] if key.startswith("[") else node.setdefault(key, {})
    last = keys[-1]
    if value is DELETE:
        del node[last]
    elif last.startswith("["):
        node[int(last[1:-1])] = value
    else:
        node[last] = value


def refusal(data=None, text=None):
    with pytest.raises(DocumentError) as caught:
        Document.loads(text) if text is not None else Document.from_dict(data)
    return [d for d in caught.value.diagnostics if d.severity == "error"], str(caught.value)


def saved(data, out):
    result = run(Document.from_dict(copy.deepcopy(data)), verbose=False)
    path = result.save(out)
    summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
    with np.load(path / "fields.npz", allow_pickle=False) as archive:
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


def factor(unit, quantity):
    return units.convert(f"1 {unit}", quantity, path="factor").value


# ---- P2-4: the same value in any spelling ---------------------------------------------------------

#: (path, spelling, quantity of a menu unit or None for a spelling of the authored unit); G4 A2 on
#: cavity_lossy_slab (authored "150 MHz" and "58 MS/m"). A menu unit changes the number, so its
#: factor is first asserted to differ from the authored unit's.
SPELLINGS = [
    (P + "target_frequency", "150000000 Hz", "target_frequency"),
    (P + "target_frequency", "1.5e8 Hz", "target_frequency"),
    (P + "target_frequency", "150000 kHz", "target_frequency"),
    (P + "target_frequency", "0.15 GHz", "target_frequency"),
    (P + "target_frequency", "0.00015 THz", "target_frequency"),
    (P + "target_frequency", "1.5e2 MHz", None),
    (P + "boundary.electrical_conductivity", "58000000 S/m", "electrical_conductivity"),
    (P + "boundary.electrical_conductivity", "5.8e7 S/m", "electrical_conductivity"),
    (P + "boundary.electrical_conductivity", "58000 kS/m", "electrical_conductivity"),
    (P + "boundary.electrical_conductivity", "580000 S/cm", "electrical_conductivity"),
    (P + "boundary.electrical_conductivity", "58 MS m^-1", None),
    (P + "boundary.electrical_conductivity", "58 MS*m^-1", None),
    ("materials.lossy_dielectric.relative_permittivity", {"re": 4, "im": 0.04}, None),
]
AUTHORED = {P + "target_frequency": ("MHz", "target_frequency"),
            P + "boundary.electrical_conductivity": ("MS/m", "electrical_conductivity")}
#: character aliases: the same value, read with a spelling fix and no error
ALIASES = [(P + "target_frequency", "150 MHz"), (P + "boundary.electrical_conductivity", "58 MS/m"),
           (P + "boundary.electrical_conductivity", "58 MS·m⁻¹")]


def test_p2_4_unit_spellings_give_the_same_si_tree_kernel_doubles_arrays_and_summary(tmp_path):
    base = example("cavity_lossy_slab")
    base_doc = Document.from_dict(copy.deepcopy(base))
    base_si, base_inputs = hexed(base_doc.si), hexed(kernel_inputs(base_doc))
    _, _, base_summary, base_arrays, _ = saved(base, tmp_path / "base")
    for i, (path, value, quantity) in enumerate(SPELLINGS):
        if quantity is not None:
            authored_unit, _ = AUTHORED[path]
            assert factor(value.split(" ", 1)[1], quantity) != factor(authored_unit, quantity), (path, value)
        data = copy.deepcopy(base)
        put(data, path, value)
        doc = Document.from_dict(data)
        assert not doc.diagnostics.errors and not doc.spelling_fixes(), (path, value)
        assert hexed(doc.si) == base_si, (path, value)
        assert hexed(kernel_inputs(doc)) == base_inputs, (path, value)
        _, _, summary, arrays, _ = saved(data, tmp_path / f"v{i}")
        same_arrays(arrays, base_arrays)
        assert results_of(summary) == results_of(base_summary), (path, value)


@pytest.mark.parametrize("path,text", ALIASES)
def test_p2_4_character_aliases_carry_a_fix_and_no_error(path, text):
    base = example("cavity_lossy_slab")
    data = copy.deepcopy(base)
    put(data, path, text)
    doc = Document.from_dict(data)
    assert not doc.diagnostics.errors
    assert hexed(doc.si) == hexed(Document.from_dict(base).si)
    assert [fix["path"] for fix in doc.spelling_fixes()] == [path]


# ---- P2-5: geometry length_unit invariance ---------------------------------------------------------

UNITS = (("m", "1"), ("mm", "1000"), ("um", "1000000"), ("nm", "1000000000"))


def scaled(value, factor_text):
    return float(Fraction(str(value)) * Fraction(factor_text))


def in_unit(name, unit, factor_text):
    """The example with every shape number (domain and boxes) in ``unit``; nothing else is a length."""
    data = example(name)
    geometry = data["geometry"]
    geometry["length_unit"] = unit
    geometry["domain"] = {k: scaled(v, factor_text) for k, v in geometry["domain"].items()}
    for shape in geometry.get("shapes", []):
        for key in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"):
            shape[key] = scaled(shape[key], factor_text)
    return data


def pm_counts(doc):
    paths = [p for p in doc.resolved_inputs() if p.startswith("geometry.")]
    return {p: doc.pm(p) for p in paths}


@pytest.mark.parametrize("name", ["cavity_box", "cavity_lossy_slab"])
def test_p2_5_shape_numbers_in_any_length_unit_give_the_same_pm_solver_call_arrays_and_summary(tmp_path, name):
    base = in_unit(name, "m", "1")
    assert base == example(name)                                  # the shipped examples are in m
    base_doc = Document.from_dict(copy.deepcopy(base))
    counts, call = pm_counts(base_doc), hexed(kernel_inputs(base_doc))
    _, _, summary, arrays, _ = saved(base, tmp_path / "m")
    for unit, factor_text in UNITS[1:]:
        data = in_unit(name, unit, factor_text)
        doc = Document.from_dict(copy.deepcopy(data))
        assert not doc.diagnostics, unit                         # no W-CAVITY-SCALE: the box is the same
        assert pm_counts(doc) == counts, unit
        assert hexed(kernel_inputs(doc)) == call, unit
        _, _, other, raw, _ = saved(data, tmp_path / unit)
        same_arrays(raw, arrays)
        assert results_of(other) == results_of(summary), unit


def test_p2_5_the_gallery_box_gives_the_same_pm_and_solver_call_in_any_length_unit(tmp_path):
    """The gallery mesh (30 x 18 x 12) takes about 30 s a solve: its pm counts and solver call are
    compared at that mesh, its saved results at the gallery's own quick mesh (10 x 6 x 4)."""
    base = Document.from_dict(in_unit("gallery_box_cavity", "m", "1"))
    counts, call = pm_counts(base), hexed(kernel_inputs(base))
    quick = []
    for unit, factor_text in UNITS:
        data = in_unit("gallery_box_cavity", unit, factor_text)
        doc = Document.from_dict(copy.deepcopy(data))
        assert pm_counts(doc) == counts and hexed(kernel_inputs(doc)) == call, unit
        data["mesh"]["subdivision_count"] = [10, 6, 4]
        quick.append(saved(data, tmp_path / unit))
    for _, _, summary, arrays, _ in quick[1:]:
        same_arrays(arrays, quick[0][3])
        assert results_of(summary) == results_of(quick[0][2])


def test_p2_5_an_exact_mil_box_equals_its_millimetre_twin(tmp_path):
    """1000 x 600 x 400 mil is exactly 25.4 x 15.24 x 10.16 mm (1 mil = 25.4 um)."""
    def box(unit, sides):
        data = example("cavity_box")
        data["geometry"]["length_unit"] = unit
        data["geometry"]["domain"] = {"xmin": 0, "xmax": sides[0], "ymin": 0, "ymax": sides[1], "zmin": 0,
                                      "zmax": sides[2]}
        data["physics"]["em1"].update(target_frequency="10 GHz", mode_count=3)
        data["mesh"]["subdivision_count"] = [5, 3, 2]
        return data
    mil, mm = box("mil", [1000, 600, 400]), box("mm", [25.4, 15.24, 10.16])
    a, b = Document.from_dict(copy.deepcopy(mil)), Document.from_dict(copy.deepcopy(mm))
    assert not a.diagnostics and not b.diagnostics
    assert pm_counts(a) == pm_counts(b) and pm_counts(a)["geometry.domain.xmax"] == 25_400_000_000
    assert hexed(kernel_inputs(a)) == hexed(kernel_inputs(b))
    _, _, sa, aa, _ = saved(mil, tmp_path / "mil")
    _, _, sb, ab, _ = saved(mm, tmp_path / "mm")
    same_arrays(aa, ab)
    assert results_of(sa) == results_of(sb)


def test_p2_5_cavity_box_numbers_declared_in_mm_warn_w_cavity_scale_and_stay_valid():
    data = example("cavity_box")
    data["geometry"]["length_unit"] = "mm"                         # a 1 mm cube searched near 250 MHz
    doc = Document.from_dict(data)
    assert [(d.code, d.path, d.severity) for d in doc.diagnostics] == [("W-CAVITY-SCALE", "geometry", "warning")]
    assert "0.00083391" in doc.diagnostics[0].message and "check length_unit" in doc.diagnostics[0].message
    assert "cavity size x f/c = 0.00083391" in doc.extent_lines()[0]


# ---- P2-6: a 3D domain takes no depth ------------------------------------------------------------

@pytest.mark.parametrize("name", ["cavity_box", "cavity_lossy_slab"])
@pytest.mark.parametrize("depth,codes", [(None, ["E-KEY-UNKNOWN"]), ("1 m", ["E-KEY-UNKNOWN"]),
                                         ("0 m", ["E-DOMAIN", "E-KEY-UNKNOWN"])])   # both rules of P2-6 apply
def test_p2_6_a_depth_on_a_cavity_is_e_key_unknown(name, depth, codes):
    data = example(name)
    data["geometry"]["depth"] = depth
    errors, _ = refusal(data)
    assert [(d.code, d.path) for d in errors] == [(code, "geometry.depth") for code in codes]


def test_p2_6_cavity_results_have_no_per_depth_or_total_names(tmp_path):
    _, _, summary, arrays, metadata = saved(example("cavity_lossy_slab"), tmp_path / "out")
    names = list(summary) + list(arrays) + list(metadata["field_units"])
    assert not [n for n in names if n.endswith("_per_depth") or n == "depth"]


# ---- P2-7 / P2-8: the cavity rows of G4 A4, each with its code and path ----------------------------

S0 = "geometry.shapes[0]"
SLAB = "materials.lossy_dielectric"
#: (G4 A4 row, example, path, value, code, path of the error or None for path, text in the message)
ROWS = [
    (1, "cavity_box", P + "target_frequency", 2.5e8, "E-UNIT-MISSING", None, "no unit"),
    (1, "cavity_lossy_slab", P + "boundary.electrical_conductivity", 5.8e7, "E-UNIT-MISSING", None, "no unit"),
    (2, "cavity_box", P + "target_frequency", "1550 nm", "E-UNIT-DIMENSION", None, "needs Hz"),
    (2, "cavity_lossy_slab", P + "boundary.electrical_conductivity", "5.8e7 W/(m K)", "E-UNIT-DIMENSION", None,
     "needs S/m"),
    (3, "cavity_lossy_slab", P + "boundary.electrical_conductivity", "58 mS/m", "E-UNIT-NOT-ACCEPTED", None,
     "millisiemens per metre"),
    (3, "cavity_box", P + "target_frequency", "250 mHz", "E-UNIT-NOT-ACCEPTED", None, "millihertz"),
    (3, "cavity_box", P + "target_frequency", "250 Mhz", "E-UNIT-UNKNOWN", None, "MHz"),
    (4, "cavity_box", P + "target_frequency", "250MHz", "E-UNIT-UNKNOWN", None, "one space"),
    (5, "cavity_box", P + "target_frequency", "0 Hz", "E-DOMAIN", None, "> 0 Hz"),
    (5, "cavity_box", P + "target_frequency", "-250 MHz", "E-DOMAIN", None, "> 0 Hz"),
    (5, "cavity_lossy_slab", P + "boundary.electrical_conductivity", "0 S/m", "E-DOMAIN", None, "> 0"),
    (6, "cavity_box", P + "mode_count", 2.0, "E-DOMAIN", None, "integer"),
    (6, "cavity_box", P + "mode_count", 1.7, "E-DOMAIN", None, "whole number"),
    (6, "cavity_box", P + "mode_count", 0, "E-DOMAIN", None, "at least one mode"),
    (6, "cavity_box", "mesh.subdivision_count", [6, 6, 6.5], "E-DOMAIN", "mesh.subdivision_count[2]",
     "whole number"),
    (7, "cavity_lossy_slab", f"{SLAB}.relative_permittivity", {"re": 4.0, "im": -0.04}, "E-GAIN",
     f"{SLAB}.relative_permittivity.im", r"exp\(\+j omega t\)"),
    (7, "cavity_lossy_slab", f"{SLAB}.relative_permeability", {"re": 1.0, "im": -0.01}, "E-GAIN",
     f"{SLAB}.relative_permeability.im", r"exp\(\+j omega t\)"),
    (7, "cavity_lossy_slab", P + "allow_gain", True, "E-CONTRACT", None, "passive"),
    (8, "cavity_box", "units", {"length": "m"}, "E-KEY-UNKNOWN", None, "units travel with each value"),
    (8, "cavity_box", "openphysics", "0.2", "E-FORMAT", None, "format 0.2 em.cavity3d documents are not read"),
    (9, "cavity_box", P + "target_frequency_hz", 2.5e8, "E-KEY-UNKNOWN", None, "target_frequency"),
    (9, "cavity_box", P + "num_modes", 5, "E-KEY-UNKNOWN", None, "write mode_count"),
    (9, "cavity_lossy_slab", P + "boundary.conductivity_s_per_m", 5.8e7, "E-KEY-UNKNOWN", None,
     "write electrical_conductivity"),
    (9, "cavity_box", "mesh.subdivisions", [6, 6, 6], "E-KEY-UNKNOWN", None, "subdivision_count"),
    (9, "cavity_box", "mesh.size", 0.2, "E-KEY-UNKNOWN", None, "element_size"),
    (10, "cavity_lossy_slab", f"{SLAB}.eps_r", 4.0, "E-KEY-UNKNOWN", None, "relative_permittivity"),
    (10, "cavity_lossy_slab", P + "boundary.sigma", "58 MS/m", "E-KEY-UNKNOWN", None, "electrical_conductivity"),
    (11, "cavity_box", "geometry.length_unit", DELETE, "E-KEY-MISSING", None, "length_unit"),
    (11, "cavity_box", "geometry.background", DELETE, "E-KEY-MISSING", "geometry.background.material",
     "physmat:vacuum"),
    (11, "cavity_lossy_slab", f"{SLAB}.relative_permittivity", DELETE, "E-KEY-MISSING", None, "relative_permittivity"),
    (13, "cavity_box", "geometry.background.material", "vacuum", "E-MATERIAL-UNKNOWN", None, "physmat:vacuum"),
    (13, "cavity_box", "geometry.background.material", "physmat:air", "E-LIBRARY-UNKNOWN", None, "physmat:vacuum"),
    (14, "cavity_box", "geometry.background.material", "physmat:Si", "E-CONTRACT", None, "physmat:vacuum"),
    (14, "cavity_lossy_slab", f"{S0}.material", "physmat:vacuum", "E-CONTRACT", None, "background only"),
    (15, "cavity_box", P + "mode_cont", 5, "E-KEY-UNKNOWN", None, "Did you mean mode_count"),
    (19, "cavity_lossy_slab", f"{S0}.zmax", 0.35, "E-CONTRACT", None, "mesh grid plane"),
    (19, "cavity_box", "results.plots", True, "E-CONTRACT", None, "plotting is not supported"),
    (19, "cavity_box", "study", {"type": "sweep", "parameter": P + "target_frequency",
                                 "values": {"unit": "MHz", "values": [200, 250]}}, "E-CONTRACT", "study.type", "sweeps"),
    (19, "cavity_box", "mesh.element_size", "0.1 m", "E-CONTRACT", None, "subdivision_count"),
]


@pytest.mark.parametrize("row,name,path,value,code,where,words", ROWS)
def test_p2_8_each_refusal_names_its_code_and_path(row, name, path, value, code, where, words):
    data = example(name)
    put(data, path, value)
    errors, text = refusal(data)
    assert (errors[0].code, errors[0].path) == (code, where or path), row
    assert re.search(words, text), (row, text)


def test_p2_8_a_physics_entry_keeps_its_own_name_and_a_duplicate_key_is_refused():
    data = example("cavity_box")
    data["physics"] = {"resonator": data["physics"]["em1"]}       # G4 A4 row 15: no em1 is added
    doc = Document.from_dict(data)
    assert list(doc.si["physics"]) == ["resonator"]
    text = json.dumps(example("cavity_box"))[:-1] + ', "name": "again"}'
    errors, _ = refusal(text=text)
    assert [d.code for d in errors] == ["E-KEY-DUPLICATE"]          # G4 A4 row 18


def test_p2_8_a_version_1_box_component_reads_as_its_flat_block():
    """Spec 4.9: a box-only version 1 3d component compiles to the flat block, as before; its grid
    check names the component's path."""
    flat = example("cavity_lossy_slab")
    geometry = flat["geometry"]
    data = copy.deepcopy(flat)
    data["geometry"] = {"version": 1, "components": {"cav": {
        "dimension": "3d", "length_unit": "m", "domain": geometry["domain"], "background": geometry["background"],
        "features": copy.deepcopy(geometry["shapes"])}}}
    assert hexed(kernel_inputs(Document.from_dict(copy.deepcopy(data)))) == hexed(kernel_inputs(Document.from_dict(flat)))
    data["geometry"]["components"]["cav"]["features"][0]["zmax"] = 0.35
    errors, text = refusal(data)
    assert [(d.code, d.path) for d in errors] == [("E-CONTRACT", "geometry.components.cav.features[0].zmax")]
    assert "mesh grid plane" in text


def test_p2_8_box_grid_planes_keep_the_relative_tolerance_on_picometres():
    """G4 Q20: a box bound within 1e-9 x subdivisions of a grid plane (relative to the cell) is on it;
    the check reads the pm counts."""
    data = example("cavity_lossy_slab")                            # 8 cells of 0.075 m along z
    data["geometry"]["shapes"][0]["zmax"] = 0.30000000003          # 4e-10 of a cell off the plane
    Document.from_dict(copy.deepcopy(data))
    data["geometry"]["shapes"][0]["zmax"] = 0.3000000015           # 2e-8 of a cell off
    errors, _ = refusal(data)
    assert [(d.code, d.path) for d in errors] == [("E-CONTRACT", f"{S0}.zmax")]


# ---- P2-9: diagnostics are never lost ------------------------------------------------------------

@pytest.mark.parametrize("value,code", [(1.0000000000003, "W-PM-ROUNDING"), (1.0000000000000002, "I-PM-ROUNDING")])
def test_p2_9_cavity_diagnostics_reach_validate_the_log_the_summary_and_the_metadata(tmp_path, capsys, value, code):
    from simcase.cli import main
    data = example("cavity_box")
    data["geometry"]["domain"]["xmax"] = value
    data["mesh"]["subdivision_count"] = [3, 3, 3]
    data["physics"]["em1"]["mode_count"] = 3
    expected = [(code, "geometry.domain.xmax")]
    doc = Document.from_dict(copy.deepcopy(data))
    assert [(d.code, d.path) for d in doc.diagnostics] == expected
    doc.validate()
    kernel_inputs(doc)
    assert len(doc.diagnostics) == 1                               # the count never drops, nor doubles
    model = tmp_path / "model.json"
    model.write_text(json.dumps(data), encoding="utf-8")
    assert main(["validate", str(model)]) == 0
    assert f"{code} at geometry.domain.xmax" in capsys.readouterr().out
    assert main(["validate", "--json", str(model)]) == 0
    assert [(d["code"], d["path"]) for d in json.loads(capsys.readouterr().out)["diagnostics"]] == expected
    assert main(["run", str(model), "-o", str(tmp_path / "out")]) == 0
    printed = capsys.readouterr().out
    log = (tmp_path / "out" / "log.txt").read_text(encoding="utf-8")
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    with np.load(tmp_path / "out" / "fields.npz", allow_pickle=False) as archive:
        metadata = json.loads(str(archive["metadata_json"]))
    assert f"{code} at geometry.domain.xmax" in printed and f"{code} at geometry.domain.xmax" in log
    assert [(d["code"], d["path"]) for d in summary["diagnostics"]] == expected
    assert metadata["diagnostics"] == summary["diagnostics"]


def test_p2_9_w_cavity_scale_reaches_every_surface_and_strict_exits_3(tmp_path, capsys):
    from simcase.cli import main
    data = example("cavity_box")
    data["geometry"]["length_unit"] = "mm"
    model = tmp_path / "mm.json"
    model.write_text(json.dumps(data), encoding="utf-8")
    assert main(["validate", str(model)]) == 0
    assert "W-CAVITY-SCALE at geometry" in capsys.readouterr().out
    assert main(["validate", "--strict", str(model)]) == 3
    capsys.readouterr()
    data["physics"]["em1"]["mode_count"] = 0
    model.write_text(json.dumps(data), encoding="utf-8")
    assert main(["validate", str(model)]) == 2
    capsys.readouterr()
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from simcase.studio import app
    data["physics"]["em1"]["mode_count"] = 5
    with TestClient(app) as client:
        response = client.post("/api/validate", json={"doc": data})
    assert response.status_code == 200
    assert [(d["code"], d["path"]) for d in response.json()["diagnostics"]] == [("W-CAVITY-SCALE", "geometry")]


def test_p2_9_defaults_are_echoed_with_their_reasons(tmp_path):
    _, _, summary, _, metadata = saved(example("cavity_lossy_slab"), tmp_path / "out")
    defaults = {d["path"]: d for d in summary["defaults_applied"]}
    assert defaults[f"{SLAB}.relative_permeability"]["value"] == 1
    assert "nonmagnetic" in defaults[f"{SLAB}.relative_permeability"]["reason"]
    assert metadata["defaults_applied"] == summary["defaults_applied"]
    resolved = summary["resolved_inputs"]
    assert resolved[P + "target_frequency"] == {"authored": "150 MHz", "unit": "Hz", "value": 150000000.0}
    assert resolved["mesh.subdivision_count"]["value"] == [8, 8, 8]


# ---- P2-11: result names and units ------------------------------------------------------------------

UNIT_TOKEN = re.compile(r"_(k|m|s|w|j|um|nm|hz|v|a|deg|m2|db_cm|db_90deg|per_m|s_per_m|s_m)$")
#: arrays without a registry quantity: connectivity, wall names and the text scalars
STRUCTURAL = {"tetrahedra", "edges", "tet_edges", "edge_signs", "pec_edge_ids", "wall_names", "field_layout",
              "normalization", "search", "edge_orientation", "electric_field_location", "cluster_completeness",
              "mode_count_policy"}
#: summary keys that carry a registry quantity
SUMMARY_QUANTITIES = ("resonant_frequency", "quality_factor", "wavenumber_squared", "relative_residual",
                      "target_frequency")


def keys(tree):
    if isinstance(tree, dict):
        for key, value in tree.items():
            yield key
            if key not in ("resolved_inputs", "materials"):
                yield from keys(value)
    elif isinstance(tree, list):
        for item in tree:
            yield from keys(item)


def _complex_entries(tree, where=""):
    if isinstance(tree, dict):
        if "re" in tree and "im" in tree:
            yield where, tree
        for key, value in tree.items():
            if key != "resolved_inputs":
                yield from _complex_entries(value, f"{where}.{key}")


@pytest.mark.parametrize("name", CAVITIES)
def test_p2_11_cavity_result_names_and_units(tmp_path, name):
    from simcase.export import RETIRED_LAYOUTS, SUPPORTED_LAYOUTS
    data = example(name)
    if name == "gallery_box_cavity":
        data["mesh"]["subdivision_count"] = [10, 6, 4]           # the names, not the mesh, are checked
    _, _, summary, arrays, metadata = saved(data, tmp_path / "out")
    names = list(keys(summary)) + list(arrays) + list(metadata)
    assert not [k for k in names if UNIT_TOKEN.search(k)]
    assert not [k for k in names if k.endswith("_unit") or k in ("units", "requested_modes", "returned_modes")]
    assert not set(arrays) & {"nodes", "frequencies_hz", "eigenvalues_m2", "edge_coefficients", "electric_field",
                              "quality_factors", "relative_residuals", "tet_relative_permittivity"}
    assert set(summary["field_shapes"]) == set(arrays) - {"field_layout", "normalization", "search",
                                                          "edge_orientation", "electric_field_location",
                                                          "cluster_completeness", "mode_count_policy"}
    for array in arrays:
        if array in STRUCTURAL:
            assert array not in summary["field_units"], array
            continue
        quantity = units.quantity(FIELDS[array][0])
        assert summary["field_units"][array] == quantity.unit, array
        assert "result" in quantity.places, array
    for key in SUMMARY_QUANTITIES:
        if key in summary:
            assert summary[key]["unit"] == units.quantity(key).unit, key
    layout = summary["field_layout"]
    assert layout.endswith("-v2") and layout not in RETIRED_LAYOUTS and layout in SUPPORTED_LAYOUTS
    assert metadata["field_units"] == summary["field_units"] and metadata["field_layout"] == layout
    complex_ = [where for where, _ in _complex_entries(summary)]
    assert bool(complex_) == (layout == "cavity3d-edge-complex-v2") == ("time_convention" in summary)
    for where, entry in _complex_entries(summary):
        assert entry["time_convention"] == TC, where


def test_p2_11_the_retired_layouts_map_to_their_successors():
    from simcase.export import RETIRED_LAYOUTS, SUPPORTED_LAYOUTS
    assert RETIRED_LAYOUTS["cavity3d-edge-v1"] == "cavity3d-edge-v2"
    assert RETIRED_LAYOUTS["cavity3d-edge-complex-v1"] == "cavity3d-edge-complex-v2"
    assert not {"cavity3d-edge-v1", "cavity3d-edge-complex-v1"} & set(SUPPORTED_LAYOUTS)


# ---- P2-15: one convention at simcase's surface ------------------------------------------------------

def test_p2_15_a_lossy_cavity_decays_with_positive_q_and_names_its_convention(tmp_path):
    result, _, summary, arrays, metadata = saved(example("cavity_lossy_slab"), tmp_path / "out")
    f = arrays["resonant_frequency"]
    assert f.dtype == np.complex128 and np.all(f.imag < 0) and np.all(f.real > 0)
    q = arrays["quality_factor"]
    assert np.all(q > 0)
    np.testing.assert_array_equal(q, f.real / (-2 * f.imag))      # Q = Re f / (-2 Im f), bitwise
    np.testing.assert_array_equal(f, np.conj(result.cavity.frequencies_hz))
    assert np.all(arrays["relative_permittivity"].imag >= 0) and arrays["relative_permittivity"].imag.max() == 0.04
    assert summary["time_convention"] == metadata["time_convention"] == TC
    assert summary["resonant_frequency"]["time_convention"] == TC
    assert summary["wavenumber_squared"]["time_convention"] == TC
    assert summary["materials"]["lossy_dielectric"]["relative_permittivity"] == {
        "re": 4.0, "im": 0.04, "unit": "1", "time_convention": TC}
    assert "time convention exp(-i omega t); Q = Re f / (-2 Im f)" in (tmp_path / "out" / "log.txt").read_text(
        encoding="utf-8")


def test_p2_15_the_kernel_receives_the_format_0_2_doubles():
    """H16: the kernel takes exp(+j omega t); the boundary writes 0.0 - Im, so a real value keeps +0.0
    and a lossy one is the 0.2 input's double."""
    doc = Document.from_dict(example("cavity_lossy_slab"))
    eps, mu = kernel_inputs(doc).materials["lossy_dielectric"]
    assert hexed(eps) == hexed(4 - 0.04j) and hexed(mu) == hexed(complex(1.0, 0.0))
    assert str(mu.imag) == "0.0"                                      # +0.0, not -0.0


# ---- P2-16: library names --------------------------------------------------------------------------

def _material_refs(tree):
    if isinstance(tree, dict):
        for key, value in tree.items():
            if key == "material" and isinstance(value, str):
                yield value
            else:
                yield from _material_refs(value)
    elif isinstance(tree, list):
        for item in tree:
            yield from _material_refs(item)


def test_p2_16_every_cavity_document_names_materials_locally_or_physmat_vacuum():
    library = set(physmat.names())
    docs = {f"builtin:{k}": v for k, v in examples.EXAMPLES.items()
            if all(p.get("type") == "em.cavity3d" for p in v["physics"].values())}
    for path in sorted(EXAMPLE_FILES.glob("*.json")) + sorted(FIXTURES.glob("cavity_*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        if all(p.get("type") == "em.cavity3d" for p in d.get("physics", {}).values()):
            docs[path.name] = d
    assert len(docs) == 2 + 3 + 3
    for name, d in docs.items():
        local = set(d.get("materials", {}))
        assert not local & library, name                              # no local name is a physmat name
        for ref in _material_refs(d):
            assert ref == "physmat:vacuum" or ref in local, (name, ref)
        Document.from_dict(copy.deepcopy(d))                            # and each one reads


# ---- P2-18: export ----------------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["cavity_box", "cavity_lossy_slab"])
def test_p2_18_cavity_vtu_names_values_and_field_data(tmp_path, name):
    meshio = pytest.importorskip("meshio", reason="install the export extra: pip install 'simcase[export]'")
    from simcase.export import export_fields, read_field_data
    data = example(name)
    data["mesh"]["subdivision_count"] = [3, 3, 3]
    data["physics"]["em1"]["mode_count"] = 2
    if name == "cavity_lossy_slab":
        data["mesh"]["subdivision_count"] = [4, 4, 4]                 # the slab top lies on a plane
    _, out, summary, arrays, _ = saved(data, tmp_path / "out")
    vtu = export_fields(out / "fields.npz", tmp_path / "view.vtu")
    assert 'type="String"' not in vtu.read_text(encoding="utf-8", errors="replace")
    mesh = meshio.read(vtu)
    np.testing.assert_array_equal(mesh.points, arrays["node_coordinates"])          # metres
    block = read_field_data(vtu)
    assert {k: json.loads(bytes(v).decode("utf-8")) for k, v in mesh.field_data.items()} == block
    field = "mass_normalized_electric_field"
    for k in range(len(arrays[field])):
        if arrays[field].dtype.kind == "c":
            for part in ("real", "imag"):
                name_k = f"{field}_mode_{k}_{part}"
                np.testing.assert_array_equal(mesh.cell_data[name_k][0], getattr(arrays[field][k], part))
                assert block["units"][name_k] == summary["field_units"][field]
        else:
            np.testing.assert_array_equal(mesh.cell_data[f"{field}_mode_{k}"][0], arrays[field][k])
            assert block["units"][f"{field}_mode_{k}"] == summary["field_units"][field]
    assert set(block["units"]) == set(mesh.cell_data)
    if summary["field_layout"] == "cavity3d-edge-complex-v2":
        assert block["conventions"]["time_convention"] == TC
        assert "Im >= 0 is loss" in block["conventions"]["sign"]["relative_permittivity_imag"]
    else:
        assert "time_convention" not in block["conventions"]


def test_p2_18_the_exporter_reads_only_public_names():
    """The cavity export reads the saved arrays by their format 0.3 names."""
    tree = ast.parse((SIMCASE / "export.py").read_text(encoding="utf-8"))
    functions = {f.name: f for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)}
    for name in ("_cavity", "_cavity_complex"):
        strings = {n.value for n in ast.walk(functions[name]) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        assert not strings & {"nodes", "electric_field", "tet_relative_permittivity", "tet_relative_permeability"}, name
