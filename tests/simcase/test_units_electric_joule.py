# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Format 0.3 electric and Joule checks of the units and naming batch: the electric and Joule
rows of P2-4, P2-5, P2-6, P2-8, P2-9, P2-11, P2-14 and P2-18. The physics references of P2-17
(E1-E7, J1-J7, the resistor, slab convergence, the current-driven Robin case, the constant-model
limit and the temperature current-driven case) are test_electric_regions.py,
test_joule_regions.py and test_electric_joule.py, with their thresholds unchanged."""
import copy
import json
import re
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from physmat import units
from simcase import Document, DocumentError, examples, run

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT/"tools"/"units_batch"/"fixtures"/"v03"
#: summary keys that hold the authored text, wall times or findings, not results
TEXTUAL = ("resolved_inputs", "defaults_applied", "diagnostics", "extent", "timing")
RECTANGLES = ("electric_rectangle", "joule_rectangle", "joule_temperature")
REGION_FIXTURES = ("electric_e1_series", "electric_e2_parallel", "electric_e3_coax_0p8", "electric_current_terminal",
                   "joule_j1_series", "joule_j4_convective", "joule_current_terminal")


def example(name):
    return copy.deepcopy(examples.EXAMPLES[name])


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
    return result, path, summary, arrays


def same_arrays(a, b):
    assert set(a) == set(b)
    for key in a:
        assert a[key].dtype == b[key].dtype and a[key].shape == b[key].shape, key
        assert a[key].tobytes() == b[key].tobytes(), key


def results_of(summary, also=()):
    return hexed({key: value for key, value in summary.items() if key not in TEXTUAL + tuple(also)})


def put(data, path, value):
    """Set ``value`` at a dotted path such as ``geometry.components.xs.features[0].x``."""
    node, keys = data, re.findall(r"[^.\[\]]+|\[\d+\]", path)
    for key in keys[:-1]:
        node = node[int(key[1:-1])] if key.startswith("[") else node[key]
    last = keys[-1]
    if last.startswith("["):
        node[int(last[1:-1])] = value
    else:
        node[last] = value


def factor(unit, quantity):
    return units.convert(f"1 {unit}", quantity, path="factor").value


# ---- P2-4: unit spelling invariance -------------------------------------------------------------

E = "physics.electric."
#: (path, spelling, quantity of a menu unit or None for a spelling of the same unit): G2 A2 on
#: joule_temperature; a menu unit changes the number, so its factor is first asserted not 1
RECTANGLE_SPELLINGS = [
    (E+"electrical_conductivity.reference_conductivity", "0.002 kS/m", "reference_conductivity"),
    (E+"electrical_conductivity.reference_conductivity", "2e-6 MS/m", "reference_conductivity"),
    (E+"electrical_conductivity.reference_conductivity", "0.02 S/cm", "reference_conductivity"),
    (E+"thermal_conductivity", "1000 mW/(m K)", "thermal_conductivity"),
    (E+"thermal_conductivity", "0.01 W/(cm K)", "thermal_conductivity"),
    (E+"thermal_conductivity", "1 W/(m*K)", None), (E+"thermal_conductivity", "1 W/m/K", None),
    (E+"thermal_conductivity", "1 W m^-1 K^-1", None),
    (E+"prescribed_temperature.left", "26.85 degC", "prescribed_temperature"),
    (E+"initial_temperature", "300000 mK", "initial_temperature"),
    (E+"electrical_conductivity.reference_temperature", "26.85 degC", "reference_temperature"),
    (E+"electrical_conductivity.valid.temperature", ["16.85 degC", "126.85 degC"], "temperature"),
    (E+"electrical_conductivity.resistivity_temperature_coefficient", "10000 ppm/K",
     "resistivity_temperature_coefficient"),
    (E+"iteration.temperature_tolerance", "1e-5 mK", "temperature_tolerance"),
    (E+"prescribed_electric_potential.left", "1000 mV", "prescribed_electric_potential"),
    (E+"prescribed_electric_potential.left", "0.001 kV", "prescribed_electric_potential"),
]
J = "physics.j."
#: the same on the J1 region strip (materials, potentials, temperatures and the element size)
REGION_SPELLINGS = [
    ("materials.A.electrical_conductivity", "2 kS/m", "electrical_conductivity"),
    ("materials.B.electrical_conductivity", "5 S/cm", "electrical_conductivity"),
    ("materials.A.thermal_conductivity", "1.5 W/m/K", None),
    ("materials.B.thermal_conductivity", "0.0025 W/(cm K)", "thermal_conductivity"),
    (J+"prescribed_electric_potential.left", "100 mV", "prescribed_electric_potential"),
    (J+"prescribed_temperature.right", "26.85 degC", "prescribed_temperature"),
    ("mesh.element_size", "250 um", "element_size"),
    ("mesh.element_size", "0.025 cm", "element_size"),
]
#: character aliases: the same value, read with a spelling fix and no error
ALIASES = [("joule_rectangle", E+"prescribed_temperature.left", "26.85 ℃"),
           ("joule_rectangle", E+"prescribed_electric_potential.left", "1 V"),
           ("joule_rectangle", E+"electrical_conductivity", "2 S·m⁻¹"),
           ("joule_rectangle", E+"prescribed_electric_potential.right", "−0 V"),
           ("joule_j1_series", "mesh.element_size", "250 µm"),
           ("joule_j1_series", "mesh.element_size", "250 μm")]


def spelling_rewrites_hold(base, rewrites, tmp_path):
    _, _, base_summary, base_arrays = saved(base, tmp_path/"base")
    base_si = hexed(Document.from_dict(copy.deepcopy(base)).si)
    for i, (path, value, quantity) in enumerate(rewrites):
        if quantity is not None:
            text = value[0] if isinstance(value, list) else value
            assert factor(text.split(" ", 1)[1], quantity) != 1, (path, value)
        data = copy.deepcopy(base)
        put(data, path, value)
        doc = Document.from_dict(data)
        assert not [d for d in doc.diagnostics if d.severity == "error"]
        assert hexed(doc.si) == base_si, (path, value)
        _, _, summary, arrays = saved(data, tmp_path/f"v{i}")
        same_arrays(arrays, base_arrays)
        assert results_of(summary) == results_of(base_summary), (path, value)


def test_p2_4_joule_temperature_spellings_and_menu_units_give_the_same_si_tree_and_saved_arrays(tmp_path):
    spelling_rewrites_hold(example("joule_temperature"), RECTANGLE_SPELLINGS, tmp_path)


def test_p2_4_region_strip_spellings_and_menu_units_give_the_same_si_tree_and_saved_arrays(tmp_path):
    spelling_rewrites_hold(fixture("joule_j1_series"), REGION_SPELLINGS, tmp_path)


@pytest.mark.parametrize("name,path,text", ALIASES)
def test_p2_4_character_aliases_carry_a_fix_and_no_error(name, path, text):
    base = example(name) if name in examples.EXAMPLES else fixture(name)
    data = copy.deepcopy(base)
    put(data, path, text)
    doc = Document.from_dict(data)
    assert not [d for d in doc.diagnostics if d.severity == "error"]
    assert hexed(doc.si) == hexed(Document.from_dict(base).si)
    assert [fix["path"] for fix in doc.spelling_fixes()] == [path]


# ---- P2-5: geometry length_unit invariance ------------------------------------------------------

def scaled(value, factor_text):
    return float(Fraction(str(value))*Fraction(factor_text))


def rectangle_in(name, unit, factor_text):
    data = example(name)                        # 1 m x 0.2 m
    data["geometry"]["length_unit"] = unit
    data["geometry"]["domain"] = {k: scaled(v, factor_text) for k, v in data["geometry"]["domain"].items()}
    return data


def pm_counts(doc, prefix="geometry.domain."):
    return [doc.pm(prefix+key) for key in ("xmin", "xmax", "ymin", "ymax")]


@pytest.mark.parametrize("name", ["electric_rectangle", "joule_rectangle"])
def test_p2_5_rectangle_length_unit_rewrites_give_the_same_pm_counts_arrays_and_summary(tmp_path, name):
    base = rectangle_in(name, "m", "1")
    counts = pm_counts(Document.from_dict(base))
    _, _, summary, arrays = saved(base, tmp_path/"m")
    for unit, factor_text in (("mm", "1000"), ("um", "1000000"), ("nm", "1000000000")):
        data = rectangle_in(name, unit, factor_text)
        assert pm_counts(Document.from_dict(data)) == counts, unit
        _, _, other, raw = saved(data, tmp_path/unit)
        same_arrays(raw, arrays)
        assert results_of(other) == results_of(summary), unit


def strip_in(unit, factor_text, name="joule_j1_series"):
    """The 2 x 1 mm region strip with its shape numbers in ``unit`` (the element size is a
    quantity and keeps its own unit)."""
    data = fixture(name)
    component = data["geometry"]["components"]["xs"]
    component["length_unit"] = unit
    component["domain"] = {k: scaled(v, factor_text) for k, v in component["domain"].items()}
    for feature in component["features"]:
        for key in ("x", "y", "w", "h"):
            feature[key] = scaled(feature[key], factor_text)
    return data


#: the smallest triangle angle is measured on the triangulation in the document's own units (P2-1
#: keeps it bitwise against format 0.2), so it is the one summary value that moves by rounding
#: across length units. A stated deviation from P2-5 ("identical summary values"), not a pass of
#: it, handled as the region heat check does (test_thermal_length_canonical.py): compared to 1e-13
#: relative. Measured on these strips: um and nm 2 ulp from mm (m equal); mil 4 ulp from um.
ANGLE = "minimum_triangle_angle"


def angle_of(summary):
    return summary["mesh"][ANGLE]["value"]


def without_angle(summary):
    out = copy.deepcopy(summary)
    del out["mesh"][ANGLE]
    return results_of(out)


@pytest.mark.parametrize("name", ["electric_e1_series", "joule_j1_series"])
def test_p2_5_region_length_unit_rewrites_give_the_same_pm_counts_meshes_arrays_and_summary(tmp_path, name):
    prefix = "geometry.components.xs.domain."
    base = strip_in("mm", "1", name)
    counts = pm_counts(Document.from_dict(base), prefix)
    _, _, summary, arrays = saved(base, tmp_path/"mm")
    for unit, factor_text in (("m", "0.001"), ("um", "1000"), ("nm", "1000000")):
        data = strip_in(unit, factor_text, name)
        assert pm_counts(Document.from_dict(data), prefix) == counts, unit
        _, _, other, raw = saved(data, tmp_path/unit)
        same_arrays(raw, arrays)
        assert without_angle(other) == without_angle(summary), unit
        assert abs(angle_of(other) - angle_of(summary)) <= 1e-13 * angle_of(summary), unit


def test_p2_5_a_strip_in_mil_equals_the_strip_in_um(tmp_path):
    def strip(unit, width, height):
        data = fixture("joule_j1_series")
        component = data["geometry"]["components"]["xs"]
        component["length_unit"] = unit
        component["domain"] = {"xmin": 0, "xmax": 2*width, "ymin": 0, "ymax": height}
        component["features"][0].update(x=width, y=0, w=width, h=height)
        return data
    mil, um = strip("mil", 50, 50), strip("um", 1270, 1270)          # 100 x 50 mil = 2540 x 1270 um
    prefix = "geometry.components.xs.domain."
    assert pm_counts(Document.from_dict(mil), prefix) == pm_counts(Document.from_dict(um), prefix)
    _, _, a, arrays_mil = saved(mil, tmp_path/"mil")
    _, _, b, arrays_um = saved(um, tmp_path/"um")
    same_arrays(arrays_mil, arrays_um)
    assert without_angle(a) == without_angle(b)
    assert abs(angle_of(a) - angle_of(b)) <= 1e-13 * angle_of(b)


def test_p2_5_a_mm_strip_declared_in_metres_is_refused_before_meshing():
    data = fixture("joule_j1_series")
    data["geometry"]["components"]["xs"]["length_unit"] = "m"        # element_size stays "0.25 mm"
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    assert [(d.code, d.path) for d in caught.value.diagnostics if d.severity == "error"] == [
        ("E-MESH-ESTIMATE", "geometry.components.xs")]


# ---- P2-6: depth invariance ---------------------------------------------------------------------

def set_depth(data, depth):
    geometry = data["geometry"]
    target = next(iter(geometry["components"].values())) if "components" in geometry else geometry
    target["depth"] = depth


def per_depth_items(block):
    return {k: v for k, v in block.items() if k.endswith("_per_depth")}


@pytest.mark.parametrize("source,name", [("example", "joule_rectangle"), ("example", "joule_temperature"),
                                         ("fixture", "electric_e1_series"), ("fixture", "joule_j1_series")])
def test_p2_6_depth_changes_totals_only(tmp_path, source, name):
    runs = {}
    for depth in (None, "1 m", "40 mm"):
        data = example(name) if source == "example" else fixture(name)
        set_depth(data, depth)
        runs[depth] = saved(data, tmp_path/str(depth).replace(" ", ""))
    base_summary, base_arrays = runs[None][2], runs[None][3]
    per_depth = per_depth_items(base_summary["balance"])
    assert per_depth and not any(k[:-len("_per_depth")] in base_summary["balance"] for k in per_depth)
    for depth, metres in (("1 m", 1.0), ("40 mm", 0.04)):
        summary, arrays = runs[depth][2], runs[depth][3]
        same_arrays(arrays, base_arrays)
        assert results_of(summary, ("balance",)) == results_of(base_summary, ("balance",))
        assert set(summary["balance"]) == set(base_summary["balance"]) | {k[:-len("_per_depth")] for k in per_depth}
        for key, value in per_depth.items():
            assert hexed(summary["balance"][key]) == hexed(value), key
            total = summary["balance"][key[:-len("_per_depth")]]
            if "value" in value:
                assert total["value"].hex() == (value["value"]*metres).hex(), key
                assert total["unit"] == units.quantity(key[:-len("_per_depth")]).unit
            else:                                   # outward_current_per_depth, by terminal
                assert set(total) == set(value), key
                for tag in value:
                    assert total[tag]["value"].hex() == (value[tag]["value"]*metres).hex(), (key, tag)
                    assert total[tag]["unit"] == "A"
        for record, base_record in zip(summary["iterations"], base_summary["iterations"]):
            assert hexed(record) == hexed(base_record)            # the history stays per depth


@pytest.mark.parametrize("source,name,path", [("example", "electric_rectangle", "geometry.depth"),
                                              ("fixture", "electric_e1_series", "geometry.components.xs.depth")])
def test_p2_6_depth_refusals(source, name, path):
    data = example(name) if source == "example" else fixture(name)
    put(data, path, "0 m")
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    assert [(d.code, d.path) for d in caught.value.diagnostics if d.severity == "error"] == [("E-DOMAIN", path)]
    node = data["geometry"]
    if path != "geometry.depth":
        node = node["components"]["xs"]
    del node["depth"]
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    assert ("E-KEY-MISSING", path) in [(d.code, d.path) for d in caught.value.diagnostics]


# ---- P2-8: per-kind refusals (G2 A5 and the kept refusals of spec 4.3-4.5) ----------------------

DELETE = object()
#: (document, path, value, code, error path): one row each, the code and the path asserted
REFUSALS = [
    # bare numbers: E-UNIT-MISSING with the menu
    ("joule_rectangle", E+"electrical_conductivity", 2, "E-UNIT-MISSING", None),
    ("joule_rectangle", E+"prescribed_electric_potential.right", 0, "E-UNIT-MISSING", None),
    ("joule_rectangle", E+"inward_current_density", {"top": 5}, "E-UNIT-MISSING", E+"inward_current_density.top"),
    ("joule_temperature", E+"initial_temperature", 300, "E-UNIT-MISSING", None),
    ("joule_temperature", E+"iteration.temperature_tolerance", 1e-8, "E-UNIT-MISSING", None),
    ("joule_rectangle", "geometry.depth", 1, "E-UNIT-MISSING", None),
    ("joule_j1_series", "mesh.element_size", 0.25, "E-UNIT-MISSING", None),
    # units off the menu, of another dimension, or degC inside a compound unit
    ("joule_rectangle", E+"electrical_conductivity", "2 mS/m", "E-UNIT-NOT-ACCEPTED", None),
    ("joule_j1_series", "materials.A.electrical_conductivity", "2 mS/m", "E-UNIT-NOT-ACCEPTED", None),
    ("joule_rectangle", E+"prescribed_electric_potential.left", "1 MV", "E-UNIT-NOT-ACCEPTED", None),
    ("joule_rectangle", E+"thermal_conductivity", "5.8e7 S/m", "E-UNIT-DIMENSION", None),
    ("joule_rectangle", E+"electrical_conductivity", "398 W/(m K)", "E-UNIT-DIMENSION", None),
    ("joule_temperature", E+"electrical_conductivity.resistivity_temperature_coefficient", "0.01 1/degC",
     "E-DEGC-NOT-ABSOLUTE", None),
    ("joule_rectangle", E+"thermal_conductivity", "1 W/(m degC)", "E-DEGC-NOT-ABSOLUTE", None),
    ("joule_temperature", E+"iteration.temperature_tolerance", "1e-8 degC", "E-DEGC-NOT-ABSOLUTE", None),
    ("joule_temperature", E+"initial_temperature", "80.33 degF", "E-UNIT-NOT-ACCEPTED", None),
    # keys: units, refused aliases, old names, outward inputs
    ("joule_rectangle", "units", {"length": "m", "temperature": "K"}, "E-KEY-UNKNOWN", None),
    ("joule_rectangle", E+"conductivity", "2 S/m", "E-KEY-UNKNOWN", None),
    ("joule_temperature", E+"electrical_conductivity.alpha", "0.01 1/K", "E-KEY-UNKNOWN", None),
    ("joule_temperature", E+"electrical_conductivity.conductivity_temperature_coefficient", "0.01 1/K",
     "E-KEY-UNKNOWN", None),
    ("joule_rectangle", E+"conductivity_s_m", 2.0, "E-KEY-UNKNOWN", None),
    ("joule_rectangle", E+"thermal_conductivity_w_mk", 1.0, "E-KEY-UNKNOWN", None),
    ("joule_rectangle", E+"dirichlet_potential_v", {"left": 1.0}, "E-KEY-UNKNOWN", None),
    ("joule_rectangle", E+"dirichlet_temperature_k", {"left": 300.0}, "E-KEY-UNKNOWN", None),
    ("joule_rectangle", E+"outward_current_a_m2", {"top": 1.0}, "E-KEY-UNKNOWN", None),
    ("joule_rectangle", E+"outward_flux_w_m2", {"top": 1.0}, "E-KEY-UNKNOWN", None),
    ("joule_temperature", E+"electrical_conductivity.alpha_per_k", 0.01, "E-KEY-UNKNOWN", None),
    ("joule_temperature", E+"iteration.temperature_atol_k", 1e-8, "E-KEY-UNKNOWN", None),
    ("joule_temperature", E+"conductivity_model", {"type": "linear_resistivity"}, "E-KEY-UNKNOWN", None),
    ("joule_rectangle", E+"outward_current_density", {"top": "1 A/m^2"}, "E-KEY-UNKNOWN", None),
    ("joule_rectangle", E+"outward_heat_flux", {"top": "1 W/m^2"}, "E-KEY-UNKNOWN", None),
    ("joule_j1_series", "materials.A.electrical_conductivity_s_m", 2.0, "E-KEY-UNKNOWN", None),
    # missing keys
    ("joule_rectangle", "geometry.length_unit", DELETE, "E-KEY-MISSING", None),
    ("joule_temperature", E+"iteration.temperature_tolerance", DELETE, "E-KEY-MISSING", None),
    ("joule_temperature", E+"iteration", DELETE, "E-KEY-MISSING", None),
    ("joule_temperature", E+"initial_temperature", DELETE, "E-KEY-MISSING", None),
    # absolute temperatures, the double range and the kind's own domains
    ("joule_rectangle", E+"prescribed_temperature.left", "0 K", "E-DOMAIN", None),
    ("joule_rectangle", E+"convection", {"top": {"heat_transfer_coefficient": "4 W/(m^2 K)",
                                                 "ambient_temperature": "0 K"}},
     "E-DOMAIN", E+"convection.top.ambient_temperature"),
    ("joule_temperature", E+"initial_temperature", "0 K", "E-DOMAIN", None),
    ("joule_temperature", E+"electrical_conductivity.valid.temperature", ["0 K", "400 K"], "E-DOMAIN",
     E+"electrical_conductivity.valid.temperature[0]"),
    ("joule_rectangle", E+"electrical_conductivity", "1e400 S/m", "E-DOMAIN", None),
    ("joule_rectangle", E+"electrical_conductivity", "0 S/m", "E-DOMAIN", None),
    ("joule_temperature", E+"iteration.relaxation_factor", 1.5, "E-DOMAIN", None),
    ("joule_temperature", E+"iteration.iteration_limit", 0, "E-DOMAIN", None),
    ("joule_temperature", E+"iteration.relative_tolerance", 2, "E-DOMAIN", None),
    # the library
    ("joule_j1_series", "geometry.components.xs.background.material", "Cu", "E-MATERIAL-UNKNOWN", None),
    ("joule_j1_series", "geometry.components.xs.background.material", "physmat:cu", "E-LIBRARY-UNKNOWN", None),
    # value forms: the model in joule.temperature2d only, terminal totals and heat sources never
    ("joule_temperature", E+"electrical_conductivity", "2 S/m", "E-VALUE-FORM", None),
    ("joule_rectangle", E+"electrical_conductivity", {"model": "linear_resistivity"}, "E-CONTRACT", None),
    ("electric_rectangle", E+"electrical_conductivity", {"model": "linear_resistivity"}, "E-CONTRACT", None),
    ("joule_j1_series", "materials.A.electrical_conductivity", {"model": "linear_resistivity"}, "E-VALUE-FORM", None),
    ("joule_temperature", E+"electrical_conductivity.reference_resistivity", "0.5 ohm m", "E-CONTRACT", None),
    ("joule_temperature", E+"electrical_conductivity.valid.outside", "clamp", "E-KEY-UNKNOWN", None),
    ("joule_rectangle", E+"inward_current", {"top": "1 A/m"}, "E-CONTRACT", None),
    ("joule_rectangle", E+"inward_current_per_depth", {"top": "1 A/m"}, "E-CONTRACT", None),
    ("joule_rectangle", E+"heat_source_density", "1 W/m^3", "E-CONTRACT", None),
    ("joule_j1_series", J+"heat_source_density", "1 W/m^3", "E-CONTRACT", None),
    ("electric_rectangle", E+"thermal_conductivity", "1 W/(m K)", "E-KEY-UNKNOWN", None),
    # the valid temperature range of joule.temperature2d (E-OUTSIDE-VALID, today's refusal now coded)
    ("joule_temperature", E+"electrical_conductivity.reference_temperature", "450 K", "E-OUTSIDE-VALID", None),
    ("joule_temperature", E+"initial_temperature", "500 K", "E-OUTSIDE-VALID", None),
    ("joule_temperature", E+"prescribed_temperature.left", "450 K", "E-OUTSIDE-VALID", None),
    # boundaries
    ("joule_rectangle", E+"prescribed_electric_potential", {}, "E-CONTRACT", None),
    ("joule_rectangle", E+"prescribed_electric_potential.nowhere", "0 V", "E-SELECTION-UNKNOWN", None),
    ("joule_rectangle", E+"inward_current_density", {"left": "1 A/m^2"}, "E-CONTRACT",
     E+"inward_current_density.left"),
]


@pytest.mark.parametrize("name,path,value,code,where", REFUSALS,
                         ids=[f"{row[3]}:{row[1].rsplit('.', 1)[-1]}" for row in REFUSALS])
def test_p2_8_each_refusal_names_its_code_and_path(name, path, value, code, where):
    data = example(name) if name in examples.EXAMPLES else fixture(name)
    if value is DELETE:
        keys = path.split(".")
        node = data
        for key in keys[:-1]:
            node = node[key]
        del node[keys[-1]]
    else:
        put(data, path, value)
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    assert [(d.code, d.path) for d in caught.value.diagnostics if d.severity == "error"] == [(code, where or path)]


def refusal(name, path, value):
    data = example(name) if name in examples.EXAMPLES else fixture(name)
    put(data, path, value)
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    (found,) = [d for d in caught.value.diagnostics if d.severity == "error"]
    return found


def test_p2_8_refusal_messages_name_the_unit_the_new_key_and_the_negation():
    found = refusal("joule_rectangle", E+"electrical_conductivity", "2 mS/m")
    assert "millisiemens per metre" in found.message
    assert [s.value for s in found.suggestions] == ["2 MS/m", "0.002 S/m"] and found.fix is None
    found = refusal("joule_rectangle", E+"electrical_conductivity", 2)
    assert "S/m kS/m MS/m S/cm" in found.message
    found = refusal("joule_temperature", E+"electrical_conductivity.resistivity_temperature_coefficient",
                    "0.01 1/degC")
    assert found.fix is not None and found.fix.value == "0.01 1/K"
    found = refusal("joule_temperature", E+"iteration.temperature_tolerance", "1e-8 degC")
    assert found.fix is None and [s.value for s in found.suggestions] == ["1e-8 K"]
    found = refusal("joule_temperature", E+"initial_temperature", "80.33 degF")
    assert "degree Fahrenheit" in found.message and [s.value for s in found.suggestions] == ["300 K"]
    found = refusal("joule_rectangle", E+"conductivity", "2 S/m")
    assert "thermal_conductivity" in found.message and "electrical_conductivity" in found.message
    for old, new in (("conductivity_s_m", "electrical_conductivity"),
                     ("dirichlet_potential_v", "prescribed_electric_potential"),
                     ("dirichlet_temperature_k", "prescribed_temperature")):
        found = refusal("joule_rectangle", E+old, 1.0)
        assert f"write {new}" in found.message and "negated" not in found.message and found.fix is None
    for old, new in (("outward_current_a_m2", "inward_current_density"), ("outward_flux_w_m2", "inward_heat_flux")):
        found = refusal("joule_rectangle", E+old, {"top": 1.0})
        # the meaning changes, so the negation is a suggestion in words, never a fix
        assert f"write {new}" in found.message and "negated" in found.message and found.fix is None
    for key in ("outward_current_density", "outward_heat_flux"):
        found = refusal("joule_rectangle", E+key, {"top": "1 A/m^2"})
        assert found.message.startswith("inputs are inward_")
    found = refusal("joule_rectangle", "units", {"length": "m"})
    assert found.message.startswith("units travel with each value")
    found = refusal("joule_rectangle", E+"inward_current", {"top": "1 A/m"})
    assert "a terminal total is not supported; give inward_current_density" in found.message
    found = refusal("joule_rectangle", E+"heat_source_density", "1 W/m^3")
    assert "heated by its current only" in found.message
    found = refusal("electric_rectangle", E+"electrical_conductivity", {"model": "linear_resistivity"})
    assert "only joule.temperature2d" in found.message
    found = refusal("joule_j1_series", "geometry.components.xs.background.material", "physmat:cu")
    assert 'Did you mean "physmat:Cu"' in found.message


def test_p2_8_the_kinds_keep_their_relaxation_range_and_the_valid_range_of_every_temperature():
    # the registry allows a relaxation factor up to 2; the Picard iteration takes (0, 1]
    found = refusal("joule_temperature", E+"iteration.relaxation_factor", 1.5)
    assert "0 < relaxation_factor <= 1" in found.message
    for path, value in ((E+"convection", {"top": {"heat_transfer_coefficient": "4 W/(m^2 K)",
                                                  "ambient_temperature": "450 K"}}),
                        (E+"prescribed_temperature.right", "280 K")):
        data = example("joule_temperature")
        put(data, path, value)
        with pytest.raises(DocumentError) as caught:
            Document.from_dict(data)
        assert [d.code for d in caught.value.diagnostics if d.severity == "error"] == ["E-OUTSIDE-VALID"]


def test_p2_8_a_duplicate_key_is_refused():
    from simcase import reader
    text = json.dumps(example("joule_rectangle")).replace('"type": "joule.steady2d",',
                                                           '"type": "joule.steady2d", "type": "joule.steady2d",')
    with pytest.raises(DocumentError) as caught:
        reader.loads(text)
    assert [(d.code, d.path) for d in caught.value.diagnostics] == [("E-KEY-DUPLICATE", "physics.electric")]


def test_p2_8_a_format_0_2_document_is_refused_by_name():
    data = json.loads((FIXTURES.parent/"v02"/"joule_j1_series.json").read_text(encoding="utf-8"))
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    assert [(d.code, d.path) for d in caught.value.diagnostics] == [("E-FORMAT", "openphysics")]
    assert "format 0.2 electric and Joule documents are not read" in str(caught.value)


def test_p2_8_magnitude_warnings_are_kept():
    data = example("joule_rectangle")
    put(data, E+"electrical_conductivity", "2e9 S/m")                   # band 1e-18 to 1e8 S/m
    doc = Document.from_dict(data)
    assert ("W-MAGNITUDE", E+"electrical_conductivity") in [(d.code, d.path) for d in doc.diagnostics]
    data = example("joule_temperature")
    put(data, E+"electrical_conductivity.resistivity_temperature_coefficient", "0.00393 ppm/K")
    doc = Document.from_dict(data)
    found = [d for d in doc.diagnostics if d.code == "W-MAGNITUDE"]
    assert [d.path for d in found] == [E+"electrical_conductivity.resistivity_temperature_coefficient"]
    assert "written with ppm/K" in found[0].message


# ---- P2-9: diagnostics are never lost -----------------------------------------------------------

def noisy(acknowledged):
    """The E1 series strip with a shape number 1e-6 pm and one 0.1 pm off the 1 pm grid, an unread
    material property, an out-of-band conductivity (acknowledged or not) and two insulated sides."""
    data = fixture("electric_e1_series")
    component = data["geometry"]["components"]["xs"]
    component["features"][0]["x"] = 1.000000000000001        # about 1e-6 pm off the grid
    component["domain"]["xmax"] = 2.0000000001               # 0.1 pm: rounded with a warning
    data["materials"]["A"]["thermal_conductivity"] = "400 W/(m K)"
    data["materials"]["B"]["electrical_conductivity"] = (
        {"value": "2e9 S/m", "accept": {"W-MAGNITUDE": "a superconducting stand-in"}} if acknowledged else "2e9 S/m")
    where = "materials.B.electrical_conductivity" + (".value" if acknowledged else "")
    expected = [("I-PM-ROUNDING", "geometry.components.xs.features[0].x"),
                ("W-PM-ROUNDING", "geometry.components.xs.domain.xmax"),
                ("I-UNUSED-PROPERTY", "materials.A.thermal_conductivity"), ("W-MAGNITUDE", where),
                ("I-DEFAULT-BOUNDARY", "physics.e.inward_current_density.bottom"),
                ("I-DEFAULT-BOUNDARY", "physics.e.inward_current_density.top")]
    return data, sorted(expected)


def pairs(diagnostics):
    return sorted((d["code"], d["path"]) if isinstance(d, dict) else (d.code, d.path) for d in diagnostics)


@pytest.mark.parametrize("acknowledged", [False, True])
def test_p2_9_electric_diagnostics_reach_every_output(tmp_path, capsys, acknowledged):
    from simcase.cli import main
    data, expected = noisy(acknowledged)
    doc = Document.from_dict(copy.deepcopy(data))
    assert pairs(doc.diagnostics) == expected
    model = tmp_path/"model.json"
    model.write_text(json.dumps(data), encoding="utf-8")
    assert main(["validate", str(model)]) == 0
    text = capsys.readouterr().out
    for code, path in expected:
        assert f"{code} at {path}" in text, (code, path)
    assert main(["validate", str(model), "--json"]) == 0
    assert pairs(json.loads(capsys.readouterr().out)["diagnostics"]) == expected
    assert main(["validate", str(model), "--strict"]) == 3             # W-PM-ROUNDING stays a warning
    capsys.readouterr()
    assert main(["run", str(model), "-o", str(tmp_path/"out")]) == 0
    printed = capsys.readouterr().out
    out = tmp_path/"out"
    log = (out/"log.txt").read_text(encoding="utf-8")
    summary = json.loads((out/"summary.json").read_text(encoding="utf-8"))
    with np.load(out/"fields.npz", allow_pickle=False) as archive:
        metadata = json.loads(str(archive["metadata_json"]))
    for code, path in expected:
        assert f"{code} at {path}" in printed and f"{code} at {path}" in log, (code, path)
    assert pairs(summary["diagnostics"]) == expected
    magnitude = [d for d in summary["diagnostics"] if d["code"] == "W-MAGNITUDE"]
    assert bool(magnitude[0].get("acknowledged")) is acknowledged
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
    assert pairs(run(doc, verbose=False).summary()["diagnostics"]) == expected
    bad = copy.deepcopy(data)
    bad["materials"]["A"]["electrical_conductivity"] = "-1 S/m"
    model.write_text(json.dumps(bad), encoding="utf-8")
    assert main(["validate", str(model)]) == 2


def test_p2_9_rectangle_defaults_and_boundaries_reach_the_summary(tmp_path):
    data = example("joule_temperature")
    for key in ("relaxation_factor", "relative_tolerance", "iteration_limit"):
        del data["physics"]["electric"]["iteration"][key]
    _, _, summary, _ = saved(data, tmp_path/"out")
    assert sorted((d["path"], d["value"]) for d in summary["defaults_applied"]) == [
        (E+"iteration.iteration_limit", 100), (E+"iteration.relative_tolerance", 1e-10),
        (E+"iteration.relaxation_factor", 0.5)]
    assert pairs(summary["diagnostics"]) == sorted(
        [("I-DEFAULT-BOUNDARY", E+f"{key}.{side}") for key in ("inward_current_density", "inward_heat_flux")
         for side in ("bottom", "top")])
    assert summary["resolved_inputs"][E+"iteration.temperature_tolerance"] == {
        "authored": "1e-8 K", "value": 1e-08, "unit": "K"}
    assert summary["timing"]["wall_time"]["solve"]["unit"] == "s"
    assert summary["extent"] and "length_unit m" in summary["extent"][0]


# ---- P2-11: result names and metadata -----------------------------------------------------------

UNIT_TOKEN = re.compile(r"_(k|m|s|w|j|jk|pa|deg|m2|um|nm|hz|v|a|w_m2|w_mk|w_m3|w_m2k|j_m3k|s_m|s_per_m|n_m3|"
                        r"per_m|db_cm|db_90deg)$")
#: arrays without a unit (connectivity, node indices, region ids)
STRUCTURAL = {"triangles", "electric_prescribed_node_ids", "thermal_prescribed_node_ids", "triangle_regions"}
#: summary maps keyed by the document's own names (regions and terminals)
NAMED = ("regions", "outward_current_per_depth", "outward_current")


def keys(tree, skip=("resolved_inputs",)):
    if isinstance(tree, dict):
        for key, value in tree.items():
            yield key
            if key in skip:
                continue
            if key in NAMED and isinstance(value, dict) and "value" not in value:
                for item in value.values():
                    yield from keys(item, skip)
            else:
                yield from keys(value, skip)
    elif isinstance(tree, list):
        for item in tree:
            yield from keys(item, skip)


def quantity_keys(block):
    """Each value object of a summary block with the quantity it is named by."""
    out = []
    def walk(tree, name):
        if isinstance(tree, dict) and set(tree) == {"value", "unit"}:
            out.append((name, tree))
        elif isinstance(tree, dict):
            for k, v in tree.items():
                walk(v, name if name in NAMED else k)
        elif isinstance(tree, list):
            for item in tree:
                walk(item, name)
    walk(block, None)
    return out


CASES = [("example", n) for n in RECTANGLES] + [("fixture", n) for n in REGION_FIXTURES]


@pytest.mark.parametrize("source,name", CASES, ids=[n for _, n in CASES])
def test_p2_11_electric_result_names_and_units(tmp_path, source, name):
    from simcase.export import RETIRED_LAYOUTS, SUPPORTED_LAYOUTS
    data = example(name) if source == "example" else fixture(name)
    _, _, summary, arrays = saved(data, tmp_path/"out")
    arrays = {k: v for k, v in arrays.items() if k not in ("result_format", "field_layout")}
    names = list(keys(summary)) + list(arrays)
    assert not [k for k in names if UNIT_TOKEN.search(k)]
    assert not [k for k in names if k.endswith("_unit")]
    assert set(summary["field_shapes"]) == set(arrays)
    for array in arrays:
        if array in STRUCTURAL:
            assert array not in summary["field_units"], array
            continue
        unit = summary["field_units"][array]             # a registry name: the array is its quantity
        assert unit == units.quantity(array).unit, array
        assert units.convert(f"1 {unit}", array, path=array).value == 1.0
    # every summary quantity is a registry name with its canonical unit, placed in results
    blocks = [summary["balance"], summary["mesh"], summary["iterations"], summary.get("regions", {})]
    for key, vo in quantity_keys(blocks):
        quantity = units.quantity(key)
        assert vo["unit"] == quantity.unit and "result" in quantity.places, key
    assert summary["result_format"].endswith("-result-v2")
    assert summary["field_layout"] in SUPPORTED_LAYOUTS and summary["field_layout"].endswith("-v2")
    assert not set(RETIRED_LAYOUTS) & set(SUPPORTED_LAYOUTS)
    assert "units" not in summary and "mesh_length_unit" not in summary and "iteration_units" not in summary


# ---- P2-14: sign sanity -------------------------------------------------------------------------

def test_p2_14_a_positive_inward_current_density_enters_the_body_at_its_terminal():
    data = example("electric_rectangle")
    p = data["physics"]["electric"]
    p.update(prescribed_electric_potential={"right": "0 V"}, inward_current_density={"left": "2 A/m^2"})
    result = run(Document.from_dict(data), verbose=False)
    nodes, fields = result.fields["node_coordinates"], result.fields
    left = np.isclose(nodes[:, 0], nodes[:, 0].min(), rtol=0, atol=1e-12)
    # current flows from the left terminal to the grounded right side: the potential falls along x
    assert fields["electric_potential"][left].mean() > 0.
    total = fields["outward_prescribed_current_per_depth"][left].sum()
    assert total < 0
    np.testing.assert_allclose(total, -2.*np.ptp(nodes[:, 1]), rtol=1e-12, atol=0)


def test_p2_14_a_terminal_that_takes_current_in_reports_a_negative_outward_current():
    # potential driven: the 1 V side feeds the body, so its outward current is negative
    terminals = run(Document.from_dict(fixture("electric_e1_series")), verbose=False).summary()["balance"][
        "outward_current_per_depth"]
    assert terminals["left"]["value"] < 0 < terminals["right"]["value"]
    # current driven: a positive inward_current_density at the hole wall leaves through the rim
    summary = run(Document.from_dict(fixture("electric_current_terminal")), verbose=False).summary()
    rim = summary["balance"]["outward_current_per_depth"]["rim"]["value"]
    assert rim > 0
    np.testing.assert_allclose(rim, 10.*2*np.pi*3e-3, rtol=1e-3)                  # 192-gon perimeter


# ---- P2-18: region export -----------------------------------------------------------------------

@pytest.mark.parametrize("name", ["electric_e1_series", "joule_j1_series"])
def test_p2_18_a_region_result_exports_its_units_and_conventions(tmp_path, name):
    meshio = pytest.importorskip("meshio")
    import xml.etree.ElementTree as ET
    from simcase.export import export_fields, read_field_data
    _, out, summary, arrays = saved(fixture(name), tmp_path/"out")
    vtu = export_fields(out/"fields.npz", tmp_path/"fields.vtu")
    mesh = meshio.read(vtu)
    exported = set(mesh.point_data) | set(mesh.cell_data)
    for array in exported:
        saved_array = arrays[array]
        data = mesh.point_data[array] if array in mesh.point_data else mesh.cell_data[array][0]
        if saved_array.ndim == 2 and data.shape[1] == 3:          # a 2D vector, padded with z = 0
            assert not data[:, 2].any()
            data = data[:, :2]
        np.testing.assert_array_equal(data, saved_array)
    np.testing.assert_array_equal(mesh.points[:, :2], arrays["node_coordinates"])
    block = read_field_data(vtu)
    assert block["units"] == {array: summary["field_units"][array] for array in exported if array != "triangle_regions"}
    assert block["conventions"]["sign"]["reaction_current_per_depth"]
    assert {k: json.loads(bytes(v).decode("utf-8")) for k, v in mesh.field_data.items()} == block
    assert all(a.get("type") == "UInt8" for a in ET.parse(vtu).getroot().iter("DataArray")
               if a.get("Name") in ("units", "conventions"))
    assert b'type="String"' not in vtu.read_bytes()


@pytest.mark.parametrize("layout", ["electric2d-p1-node-cell-regions-v1", "electric-joule2d-p1-node-cell-regions-v1"])
def test_p2_18_a_retired_region_layout_is_refused_by_name(tmp_path, layout):
    from simcase.export import export_fields
    fields = tmp_path/"fields.npz"
    np.savez(fields, field_layout=np.array(layout), nodes_m=np.zeros((3, 2)), triangles=np.array([[0, 1, 2]]))
    with pytest.raises(ValueError, match=re.escape(f"(layout {layout})")):
        export_fields(fields, tmp_path/"fields.vtu")
