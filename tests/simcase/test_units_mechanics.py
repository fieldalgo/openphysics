# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Format 0.3 mechanics checks of the units and naming batch: the mechanics rows of P2-4, P2-5,
P2-6, P2-8, P2-9, P2-11, P2-14 and P2-18 (G3 M2 to M8). The physics references of P2-17 (J1-J7,
K1-K4, R0-R7, R5b and the bimetal against Timoshenko) are test_mechanics.py and
test_mechanics_regions.py, with their thresholds unchanged."""
import copy
import json
import re
from decimal import Decimal
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
RECTANGLES = ("elastic_plate", "thermoelastic_bar")
REGIONS = ("elastic_regions", "thermoelastic_regions")
P, B, R, S = "physics.plate.", "physics.bar.", "physics.pipe.", "physics.strip."
MAIN = "geometry.components.main."


def example(name):
    return copy.deepcopy(examples.EXAMPLES[name])


def fixture(name):
    return json.loads((FIXTURES/(name+".json")).read_text(encoding="utf-8"))


def source(name):
    return example(name) if name in examples.EXAMPLES else fixture(name)


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


DELETE = object()


def put(data, path, value):
    """Set ``value`` at a dotted path such as ``geometry.components.main.features[0].x``."""
    node, keys = data, re.findall(r"[^.\[\]]+|\[\d+\]", path)
    for key in keys[:-1]:
        node = node[int(key[1:-1])] if key.startswith("[") else node[key]
    last = keys[-1]
    if value is DELETE:
        del node[last]
    elif last.startswith("["):
        node[int(last[1:-1])] = value
    else:
        node[last] = value


def factor(unit, quantity):
    return units.convert(f"1 {unit}", quantity, path="factor").value


# ---- P2-4: unit spelling invariance (G3 M2) -----------------------------------------------------

def plate_base():
    """elastic_plate with a body force, so that its spellings are covered too."""
    data = example("elastic_plate")
    data["physics"]["plate"]["body_force_density"] = ["100000 N/m^3", "0 N/m^3"]
    return data


def strip_base():
    """thermoelastic_regions with a gauge pressure on the free right end."""
    data = example("thermoelastic_regions")
    data["physics"]["strip"]["gauge_pressure"] = {"right": "10 MPa"}
    return data


#: (path, spelling, quantity of a menu unit or None for the canonical unit or a spelling of the
#: same unit); a menu unit changes the number, so its factor is first asserted not 1
PLATE_SPELLINGS = [
    (P+"youngs_modulus", "200000 MPa", "youngs_modulus"),
    (P+"youngs_modulus", "2e8 kPa", "youngs_modulus"),
    (P+"youngs_modulus", "2e11 Pa", None),
    (P+"traction.right", ["1000 kPa", "0 kPa"], "traction"),
    (P+"traction.right", ["1000000 Pa", "0 Pa"], None),
    (P+"traction.right", {"unit": "MPa", "values": [1, 0]}, None),
    (P+"prescribed_displacement.left.x", "0 um", "prescribed_displacement"),
    (P+"prescribed_displacement.bottom.y", "0 nm", "prescribed_displacement"),
    (P+"body_force_density", ["100 kN/m^3", "0 kN/m^3"], "body_force_density"),
    (P+"body_force_density", ["1e-4 N/mm^3", "0 N/mm^3"], "body_force_density"),
]
STRIP_SPELLINGS = [
    ("materials.steel.youngs_modulus", "200000 MPa", "youngs_modulus"),
    ("materials.steel.youngs_modulus", "2e8 kPa", "youngs_modulus"),
    ("materials.aluminium.youngs_modulus", "70000 MPa", "youngs_modulus"),
    ("materials.aluminium.linear_expansion_coefficient", "2.3e-5 1/K", None),
    ("materials.aluminium.linear_expansion_coefficient", "23 um/(m K)", "linear_expansion_coefficient"),
    ("materials.steel.linear_expansion_coefficient", "1.2e-5 1/K", None),
    ("materials.aluminium.thermal_conductivity", "237000 mW/(m K)", "thermal_conductivity"),
    ("materials.aluminium.thermal_conductivity", "2.37 W/(cm K)", "thermal_conductivity"),
    ("materials.aluminium.thermal_conductivity", "237 W/(m*K)", None),
    ("materials.aluminium.thermal_conductivity", "237 W/m/K", None),
    (S+"stress_free_temperature", "20 degC", "stress_free_temperature"),
    (S+"stress_free_temperature", "293150 mK", "stress_free_temperature"),
    (S+"prescribed_temperature.left", "70 degC", "prescribed_temperature"),
    (S+"gauge_pressure.right", "100 bar", "gauge_pressure"),
    (S+"gauge_pressure.right", "100 barg", "gauge_pressure"),
    (S+"gauge_pressure.right", "10000 kPa", "gauge_pressure"),
    (S+"gauge_pressure.right", "0.01 GPa", "gauge_pressure"),
    (S+"prescribed_displacement.left.x", "0 um", "prescribed_displacement"),
    ("mesh.element_size", "250 um", "element_size"),
]
#: the heat inputs on the K1 rectangle fixture (a source, a flux and a convection side)
HEAT_SPELLINGS = [
    (B+"heat_source_density", "0.02 W/cm^3", "heat_source_density"),
    (B+"inward_heat_flux.bottom", "-0.15 kW/m^2", "inward_heat_flux"),
    (B+"convection.top.heat_transfer_coefficient", "0.025 kW/(m^2 K)", "heat_transfer_coefficient"),
    (B+"convection.top.ambient_temperature", "26.85 degC", "ambient_temperature"),
    (B+"thermal_conductivity", "2.37 W/(cm K)", "thermal_conductivity"),
    (B+"youngs_modulus", "70 GPa", "youngs_modulus"),
    (B+"linear_expansion_coefficient", "12 ppm/K", "linear_expansion_coefficient"),
    (B+"traction.right", ["3 MPa", "0 MPa"], "traction"),
    (B+"body_force_density", ["-0 kN/m^3", "-27 kN/m^3"], "body_force_density"),
]
#: character aliases: the same value, read with a spelling fix and no error
ALIASES = [("thermoelastic_regions", S+"stress_free_temperature", "20 ℃"),
           ("mechanics_k1_strain", B+"inward_heat_flux.bottom", "−150 W/m^2"),
           ("elastic_plate", P+"youngs_modulus", "200 GPa"),
           ("thermoelastic_regions", "mesh.element_size", "250 µm"),
           ("thermoelastic_regions", "mesh.element_size", "250 μm"),
           ("thermoelastic_regions", "mesh.element_size", "250000 ㎚")]


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


def test_p2_4_elastic_plate_spellings_and_menu_units_give_the_same_si_tree_and_saved_arrays(tmp_path):
    spelling_rewrites_hold(plate_base(), PLATE_SPELLINGS, tmp_path)


def test_p2_4_imperial_moduli_are_one_exact_value(tmp_path):
    base = plate_base()
    put(base, P+"youngs_modulus", "29000 ksi")
    spelling_rewrites_hold(base, [(P+"youngs_modulus", "29000000 psi", "youngs_modulus")], tmp_path)


def test_p2_4_thermoelastic_regions_spellings_and_menu_units_give_the_same_si_tree_and_saved_arrays(tmp_path):
    spelling_rewrites_hold(strip_base(), STRIP_SPELLINGS, tmp_path)


def test_p2_4_heat_input_spellings_on_the_k1_rectangle(tmp_path):
    spelling_rewrites_hold(fixture("mechanics_k1_strain"), HEAT_SPELLINGS, tmp_path)


def test_p2_4_the_default_minimum_angle_is_28_deg_written_out(tmp_path):
    base = strip_base()
    _, _, base_summary, base_arrays = saved(base, tmp_path/"base")
    data = copy.deepcopy(base)
    data["mesh"]["minimum_angle"] = "28 deg"
    _, _, summary, arrays = saved(data, tmp_path/"written")
    same_arrays(arrays, base_arrays)
    assert results_of(summary) == results_of(base_summary)
    assert "mesh.minimum_angle" in [d["path"] for d in base_summary["defaults_applied"]]
    assert "mesh.minimum_angle" not in [d["path"] for d in summary["defaults_applied"]]


@pytest.mark.parametrize("name,path,text", ALIASES)
def test_p2_4_character_aliases_carry_a_fix_and_no_error(name, path, text):
    base = source(name)
    data = copy.deepcopy(base)
    put(data, path, text)
    doc = Document.from_dict(data)
    assert not [d for d in doc.diagnostics if d.severity == "error"]
    assert hexed(doc.si) == hexed(Document.from_dict(base).si)
    assert [fix["path"] for fix in doc.spelling_fixes()] == [path]


# ---- P2-5: geometry length_unit invariance (G3 M3) ----------------------------------------------

def scaled(value, factor_text):
    return float(Fraction(repr(float(value)))*Fraction(factor_text))


def rectangle_in(name, unit, factor_text):
    data = example(name)                        # 100 mm x 20 mm
    data["geometry"]["length_unit"] = unit
    data["geometry"]["domain"] = {k: scaled(v, factor_text) for k, v in data["geometry"]["domain"].items()}
    return data


def pm_counts(doc, prefix="geometry.domain."):
    return [doc.pm(prefix+key) for key in ("xmin", "xmax", "ymin", "ymax")]


@pytest.mark.parametrize("name", RECTANGLES)
def test_p2_5_rectangle_length_unit_rewrites_give_the_same_pm_counts_arrays_and_summary(tmp_path, name):
    base = rectangle_in(name, "mm", "1")
    counts = pm_counts(Document.from_dict(base))
    _, _, summary, arrays = saved(base, tmp_path/"mm")
    for unit, factor_text in (("m", "0.001"), ("um", "1000"), ("nm", "1000000")):
        data = rectangle_in(name, unit, factor_text)
        assert pm_counts(Document.from_dict(data)) == counts, unit
        _, _, other, raw = saved(data, tmp_path/unit)
        same_arrays(raw, arrays)
        assert results_of(other) == results_of(summary), unit


def test_p2_5_a_plate_in_inches_equals_the_plate_in_millimetres(tmp_path):
    def plate(unit, width, height):
        data = example("elastic_plate")
        data["geometry"]["length_unit"] = unit
        data["geometry"]["domain"] = {"xmin": 0, "xmax": width, "ymin": 0, "ymax": height}
        return data
    inch, mm = plate("in", 4, 0.8), plate("mm", 101.6, 20.32)
    assert pm_counts(Document.from_dict(inch)) == pm_counts(Document.from_dict(mm))
    _, _, a, arrays_in = saved(inch, tmp_path/"in")
    _, _, b, arrays_mm = saved(mm, tmp_path/"mm")
    same_arrays(arrays_in, arrays_mm)
    assert results_of(a) == results_of(b)


LENGTH_KEYS = ("x", "y", "w", "h", "cx", "cy", "r")


def region_in(name, unit, factor_text):
    """A region example with its shape numbers and its element size in ``unit`` (M3)."""
    data = example(name)
    component = data["geometry"]["components"]["main"]
    component["length_unit"] = unit
    component["domain"] = {k: scaled(v, factor_text) for k, v in component["domain"].items()}
    for feature in component["features"]:
        for key in LENGTH_KEYS:
            if key in feature:
                feature[key] = scaled(feature[key], factor_text)
    number, written = data["mesh"]["element_size"].split(" ")
    assert written == "mm"
    data["mesh"]["element_size"] = f"{Decimal(number)*Decimal(factor_text)} {unit}"     # exact decimal text
    return data


#: the smallest triangle angle is measured on the triangulation of the micrometre hand-off in the
#: document's own numbers (P2-1 keeps it bitwise against format 0.2), so it is the one summary value
#: that moves by rounding across length units. A stated deviation from P2-5 ("identical summary
#: values"), not a pass of it, handled as the heat, electric and Joule region checks do: compared
#: to 1e-13 relative. Measured on these examples against mm: elastic_regions m 10, um 8, nm 4 ulp;
#: thermoelastic_regions m 61 ulp (1.2e-14 relative), um 2, nm 0.
ANGLE = "minimum_triangle_angle"


def angle_of(summary):
    return summary["mesh"][ANGLE]["value"]


def without_angle(summary):
    out = copy.deepcopy(summary)
    del out["mesh"][ANGLE]
    return results_of(out)


@pytest.mark.parametrize("name", REGIONS)
def test_p2_5_region_length_unit_rewrites_give_the_same_pm_counts_meshes_arrays_and_summary(tmp_path, name):
    prefix = MAIN + "domain."
    base = region_in(name, "mm", "1")
    counts = pm_counts(Document.from_dict(base), prefix)
    _, _, summary, arrays = saved(base, tmp_path/"mm")
    for unit, factor_text in (("m", "0.001"), ("um", "1000"), ("nm", "1000000")):
        data = region_in(name, unit, factor_text)
        assert pm_counts(Document.from_dict(data), prefix) == counts, unit
        _, _, other, raw = saved(data, tmp_path/unit)
        same_arrays(raw, arrays)
        assert without_angle(other) == without_angle(summary), unit
        assert abs(angle_of(other) - angle_of(summary)) <= 1e-13 * angle_of(summary), unit


@pytest.mark.parametrize("name,estimate", [("elastic_regions", "about 6.5e+08 triangles"),
                                           ("thermoelastic_regions", "about 3.2e+09 triangles")])
def test_p2_5_mm_regions_declared_in_metres_are_refused_before_meshing(name, estimate):
    """Negative controls. The specification's 4.5e8 for elastic_regions is the quarter annulus's
    area over the element area; the estimator takes the 9 x 9 extent, 6.5e8: over the limit either way."""
    data = example(name)
    data["geometry"]["components"]["main"]["length_unit"] = "m"           # element_size stays in mm
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    errors = [d for d in caught.value.diagnostics if d.severity == "error"]
    assert [(d.code, d.path) for d in errors] == [("E-MESH-ESTIMATE", "geometry.components.main")]
    assert estimate in errors[0].message and "the limit is 600000" in errors[0].message


@pytest.mark.parametrize("name", RECTANGLES)
def test_p2_5_mm_rectangles_declared_in_metres_warn(name):
    data = example(name)
    data["geometry"]["length_unit"] = "m"
    doc = Document.from_dict(data)
    found = [d for d in doc.diagnostics if d.code == "W-GEOMETRY-SCALE"]
    assert [(d.code, d.path) for d in found] == [("W-GEOMETRY-SCALE", "geometry")]
    assert "millimetres written with length_unit m" in found[0].message


# ---- P2-6: depth invariance (G3 M4) -------------------------------------------------------------

def set_depth(data, depth):
    geometry = data["geometry"]
    target = next(iter(geometry["components"].values())) if "components" in geometry else geometry
    target["depth"] = depth


def per_depth_items(block):
    return {k: v for k, v in block.items() if k.endswith("_per_depth")}


@pytest.mark.parametrize("name", RECTANGLES + REGIONS)
def test_p2_6_depth_changes_totals_only(tmp_path, name):
    runs = {}
    for depth in (None, "1 m", "10 mm", "40 mm"):
        data = example(name)
        set_depth(data, depth)
        runs[depth] = saved(data, tmp_path/str(depth).replace(" ", ""))
    base_summary, base_arrays = runs[None][2], runs[None][3]
    per_depth = per_depth_items(base_summary["balance"])
    assert per_depth and not any(k[:-len("_per_depth")] in base_summary["balance"] for k in per_depth)
    assert {"strain_energy_per_depth", "reaction_force_per_depth", "applied_force_per_depth"} <= set(per_depth)
    for depth, metres in (("1 m", 1.0), ("10 mm", 0.01), ("40 mm", 0.04)):
        summary, arrays = runs[depth][2], runs[depth][3]
        same_arrays(arrays, base_arrays)
        assert results_of(summary, ("balance",)) == results_of(base_summary, ("balance",))
        assert set(summary["balance"]) == set(base_summary["balance"]) | {k[:-len("_per_depth")] for k in per_depth}
        for key, value in per_depth.items():
            assert hexed(summary["balance"][key]) == hexed(value), key
            total = summary["balance"][key[:-len("_per_depth")]]
            assert total["unit"] == units.quantity(key[:-len("_per_depth")]).unit, key
            if "value" in value:
                assert total["value"].hex() == (value["value"]*metres).hex(), key
            else:                                   # an [x, y] force
                assert [v.hex() for v in total["values"]] == [(v*metres).hex() for v in value["values"]], key


@pytest.mark.parametrize("name,path", [("elastic_plate", "geometry.depth"),
                                       ("thermoelastic_regions", MAIN + "depth")])
def test_p2_6_depth_refusals(name, path):
    data = example(name)
    put(data, path, "0 m")
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    assert [(d.code, d.path) for d in caught.value.diagnostics if d.severity == "error"] == [("E-DOMAIN", path)]
    put(data, path, DELETE)
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    assert ("E-KEY-MISSING", path) in [(d.code, d.path) for d in caught.value.diagnostics]


# ---- P2-8: per-kind refusals (G3 M5 and the kept refusals of spec 4.6-4.7) -----------------------

EP, TB, ER, TR = "elastic_plate", "thermoelastic_bar", "elastic_regions", "thermoelastic_regions"
#: (document, path, value, code, error path): one row each, the code and the path asserted
REFUSALS = [
    # bare numbers: E-UNIT-MISSING with the menu
    (EP, P+"youngs_modulus", 200e9, "E-UNIT-MISSING", None),
    (ER, R+"prescribed_displacement.left.x", 0, "E-UNIT-MISSING", None),
    (EP, P+"traction.right", [1e6, "0 Pa"], "E-UNIT-MISSING", P+"traction.right[0]"),
    (ER, R+"gauge_pressure.inner", 1e7, "E-UNIT-MISSING", None),
    (EP, P+"body_force_density", ["0 N/m^3", -77000], "E-UNIT-MISSING", P+"body_force_density[1]"),
    (TB, B+"stress_free_temperature", 293.15, "E-UNIT-MISSING", None),
    (TB, B+"linear_expansion_coefficient", 2.3e-5, "E-UNIT-MISSING", None),
    (TB, B+"thermal_conductivity", 237, "E-UNIT-MISSING", None),
    (ER, "mesh.element_size", 0.5, "E-UNIT-MISSING", None),
    (ER, MAIN+"depth", 1, "E-UNIT-MISSING", None),
    (ER, "mesh.minimum_angle", 28, "E-UNIT-MISSING", None),
    # units off the menu, unknown spellings, other dimensions, degC in a compound unit, degF
    (EP, P+"youngs_modulus", "200 mPa", "E-UNIT-NOT-ACCEPTED", None),
    (ER, R+"gauge_pressure.inner", "10 mPa", "E-UNIT-NOT-ACCEPTED", None),
    (EP, P+"youngs_modulus", "200 Mpa", "E-UNIT-UNKNOWN", None),
    (EP, P+"youngs_modulus", "200GPa", "E-UNIT-UNKNOWN", None),
    (EP, P+"youngs_modulus", "1 mm", "E-UNIT-DIMENSION", None),
    (EP, P+"poisson_ratio", "200 GPa", "E-UNIT-DIMENSION", None),
    (EP, P+"body_force_density", ["5 MPa", "0 N/m^3"], "E-UNIT-DIMENSION", P+"body_force_density[0]"),
    (EP, P+"body_force_density", ["9.81 m/s^2", "0 N/m^3"], "E-UNIT-DIMENSION", P+"body_force_density[0]"),
    (EP, P+"poisson_ratio", "0.3", "E-UNIT-UNKNOWN", None),
    (EP, P+"poisson_ratio", "30 %", "E-UNIT-NOT-ACCEPTED", None),
    (TB, B+"linear_expansion_coefficient", "12 ppm/degC", "E-DEGC-NOT-ABSOLUTE", None),
    (TB, B+"thermal_conductivity", "237 W/(m degC)", "E-DEGC-NOT-ABSOLUTE", None),
    (TB, B+"convection", {"top": {"heat_transfer_coefficient": "25 W/(m^2 degC)", "ambient_temperature": "300 K"}},
     "E-DEGC-NOT-ABSOLUTE", B+"convection.top.heat_transfer_coefficient"),
    (TB, B+"stress_free_temperature", "68 degF", "E-UNIT-NOT-ACCEPTED", None),
    (TB, B+"prescribed_temperature.left", "20 degF", "E-UNIT-NOT-ACCEPTED", None),
    # absolute temperatures and the kinds' domains
    (TB, B+"stress_free_temperature", "0 K", "E-DOMAIN", None),
    (TB, B+"prescribed_temperature.left", "0 K", "E-DOMAIN", None),
    (TB, B+"convection", {"top": {"heat_transfer_coefficient": "25 W/(m^2 K)", "ambient_temperature": "0 K"}},
     "E-DOMAIN", B+"convection.top.ambient_temperature"),
    (EP, P+"poisson_ratio", 0.5, "E-DOMAIN", None),
    (EP, P+"poisson_ratio", -1, "E-DOMAIN", None),
    (EP, P+"youngs_modulus", "0 Pa", "E-DOMAIN", None),
    (EP, P+"youngs_modulus", "1e400 Pa", "E-DOMAIN", None),
    # pressures: an absolute pressure is not a load
    (EP, P+"absolute_pressure", {"right": "1 MPa"}, "E-ABSOLUTE-AS-LOAD", None),
    (ER, R+"absolute_pressure", {"inner": "1 MPa"}, "E-ABSOLUTE-AS-LOAD", None),
    (ER, R+"gauge_pressure.inner", "10 bara", "E-ABSOLUTE-AS-LOAD", None),
    (ER, R+"gauge_pressure.inner", "10 psia", "E-ABSOLUTE-AS-LOAD", None),
    (ER, R+"gauge_pressure.inner", "1 atm", "E-UNIT-NOT-ACCEPTED", None),
    # keys: the units block, the old names, near misses and the outward input
    (EP, "units", {"length": "mm"}, "E-KEY-UNKNOWN", None),
    (EP, P+"young_modulus_pa", 2e11, "E-KEY-UNKNOWN", None),
    (TB, B+"thermal_expansion_per_k", 2.3e-5, "E-KEY-UNKNOWN", None),
    (TB, B+"reference_temperature_k", 293.15, "E-KEY-UNKNOWN", None),
    (EP, P+"displacement_m", {"left": {"x": 0.0}}, "E-KEY-UNKNOWN", None),
    (EP, P+"traction_pa", {"right": [1e6, 0.0]}, "E-KEY-UNKNOWN", None),
    (ER, R+"pressure_pa", {"inner": 1e7}, "E-KEY-UNKNOWN", None),
    (EP, P+"body_force_n_m3", [0.0, 0.0], "E-KEY-UNKNOWN", None),
    (TB, B+"thermal_conductivity_w_mk", 237.0, "E-KEY-UNKNOWN", None),
    (TR, "materials.steel.conductivity_w_mk", 45.0, "E-KEY-UNKNOWN", None),
    (TB, B+"dirichlet_temperature_k", {"left": 293.15}, "E-KEY-UNKNOWN", None),
    (TB, B+"outward_flux_w_m2", {"top": 1.0}, "E-KEY-UNKNOWN", None),
    (TB, B+"heat_source_w_m3", 0.0, "E-KEY-UNKNOWN", None),
    (EP, "mesh.subdivisions", [20, 4], "E-KEY-UNKNOWN", None),
    (ER, "mesh.size", 0.5, "E-KEY-UNKNOWN", None),
    (ER, "mesh.min_angle", 28.0, "E-KEY-UNKNOWN", None),
    (EP, P+"young_modulus", "200 GPa", "E-KEY-UNKNOWN", None),
    (EP, P+"E", "200 GPa", "E-KEY-UNKNOWN", None),
    (TB, B+"alpha", "23 ppm/K", "E-KEY-UNKNOWN", None),
    (TB, B+"thermal_expansion", "23 ppm/K", "E-KEY-UNKNOWN", None),
    (ER, R+"pressure", {"inner": "10 MPa"}, "E-KEY-UNKNOWN", None),
    (TB, B+"reference_temperature", "293.15 K", "E-KEY-UNKNOWN", None),
    (TB, B+"outward_heat_flux", {"top": "1 W/m^2"}, "E-KEY-UNKNOWN", None),
    # not read in this release, refused by name
    (TB, B+"mean_linear_expansion_coefficient", "23 ppm/K", "E-CONTRACT", None),
    (TB, B+"volumetric_expansion_coefficient", "69 ppm/K", "E-CONTRACT", None),
    (ER, "materials.steel.shear_modulus", "80 GPa", "E-CONTRACT", None),
    (ER, "materials.steel.bulk_modulus", "160 GPa", "E-CONTRACT", None),
    (ER, "materials.steel.elasticity_tensor", "1 GPa", "E-CONTRACT", None),
    (TR, "materials.steel.mean_linear_expansion_coefficient", "12 ppm/K", "E-CONTRACT", None),
    (TR, "materials.steel.volumetric_expansion_coefficient", "36 ppm/K", "E-CONTRACT", None),
    (EP, P+"gravitational_acceleration", "9.81 m/s^2", "E-CONTRACT", None),
    (EP, P+"force", {"right": "1 N"}, "E-CONTRACT", None),
    (EP, P+"force_per_depth", {"right": "1 N/m"}, "E-CONTRACT", None),
    (EP, P+"gauge_pressure", {"right": "1 MPa"}, "E-CONTRACT", None),
    (EP, P+"stress_free_temperature", "293.15 K", "E-CONTRACT", None),
    (EP, P+"prescribed_temperature", {"left": "293.15 K"}, "E-CONTRACT", None),
    (ER, R+"youngs_modulus", "200 GPa", "E-CONTRACT", None),
    (ER, R+"poisson_ratio", 0.3, "E-CONTRACT", None),
    (TR, S+"linear_expansion_coefficient", "12 ppm/K", "E-CONTRACT", None),
    (TR, S+"thermal_conductivity", "45 W/(m K)", "E-CONTRACT", None),
    # value forms
    (EP, P+"traction.right", ["1 MPa"], "E-VALUE-FORM", None),
    (EP, P+"traction.right", ["1 MPa", "0 MPa", "0 MPa"], "E-VALUE-FORM", None),
    (EP, P+"traction.right", {"x": "1 MPa", "y": "0 MPa"}, "E-VALUE-FORM", None),
    (EP, P+"traction.right", "1 MPa", "E-VALUE-FORM", None),
    (EP, P+"body_force_density", ["1 N/m^3", "0 N/m^3", "0 N/m^3"], "E-VALUE-FORM", None),
    (EP, P+"prescribed_displacement.left", "fixed", "E-VALUE-FORM", None),
    (ER, "materials.steel.youngs_modulus", [200, "GPa"], "E-VALUE-FORM", None),
    (ER, "materials.steel.youngs_modulus", "200 bara", "E-UNIT-NOT-ACCEPTED", None),
    (EP, P+"prescribed_displacement.left.z", "0 mm", "E-KEY-UNKNOWN", None),
    (EP, P+"prescribed_displacement.left.r", "0 mm", "E-KEY-UNKNOWN", None),
    # missing keys
    (EP, "geometry.length_unit", DELETE, "E-KEY-MISSING", None),
    (ER, MAIN+"length_unit", DELETE, "E-KEY-MISSING", None),
    (TB, B+"stress_free_temperature", DELETE, "E-KEY-MISSING", None),
    (EP, P+"prescribed_displacement", DELETE, "E-KEY-MISSING", None),
    # the library: unknown names, and properties the library does not hold for these kinds
    (ER, MAIN+"background.material", "physmat:Steel", "E-LIBRARY-UNKNOWN", None),
    (ER, MAIN+"background.material", "physmat:si", "E-LIBRARY-UNKNOWN", None),
    (ER, MAIN+"background.material", "physmat:Si", "E-CONTRACT", None),
    # the kept refusals (today's J4, K4 and R6 under the new names)
    (EP, P+"prescribed_displacement", {"bottom": {"x": "0 mm"}, "left": {"y": "0 mm"}}, "E-CONTRACT", None),
    (EP, P+"prescribed_displacement", {"left": {"x": "0 mm"}}, "E-CONTRACT", None),
    (EP, P+"prescribed_displacement", {"left": {"x": "0 mm"}, "bottom": {"x": "1 mm", "y": "0 mm"}}, "E-CONTRACT",
     P+"prescribed_displacement.bottom.x"),
    (EP, P+"prescribed_displacement.left", {}, "E-KEY-MISSING", None),
    (EP, P+"prescribed_displacement.front", {"x": "0 mm"}, "E-SELECTION-UNKNOWN", None),
    (EP, P+"traction.left", ["1 MPa", "0 MPa"], "E-CONTRACT", None),
    (EP, P+"traction.front", ["1 MPa", "0 MPa"], "E-SELECTION-UNKNOWN", None),
    (ER, R+"traction", {"inner": ["1 MPa", "0 MPa"]}, "E-CONTRACT", R+"gauge_pressure.inner"),
    (EP, "mesh.subdivision_count", [1000, 1000], "E-DOMAIN", None),
    (EP, "results.plots", True, "E-CONTRACT", None),
    (EP, "study", {"type": "sweep"}, "E-CONTRACT", "study.type"),
    (EP, "materials", {"steel": {"youngs_modulus": "200 GPa"}}, "E-CONTRACT", None),
    (TB, B+"prescribed_temperature", {}, "E-KEY-MISSING", None),
    (TB, B+"prescribed_temperature", {"left": "293.15 K", "bottom": "300 K"}, "E-CONTRACT",
     B+"prescribed_temperature.bottom"),
    (TB, B+"inward_heat_flux", {"left": "1 W/m^2"}, "E-CONTRACT", "physics.bar"),
    (TB, B+"heat_source_density", {"alu": "1 W/m^3"}, "E-CONTRACT", None),
]


@pytest.mark.parametrize("name,path,value,code,where", REFUSALS,
                         ids=[f"{row[3]}:{row[1].rsplit('.', 1)[-1]}" for row in REFUSALS])
def test_p2_8_each_refusal_names_its_code_and_path(name, path, value, code, where):
    data = source(name)
    put(data, path, value)
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    assert [(d.code, d.path) for d in caught.value.diagnostics if d.severity == "error"] == [(code, where or path)]


def refusal(name, path, value):
    data = source(name)
    put(data, path, value)
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    (found,) = [d for d in caught.value.diagnostics if d.severity == "error"]
    return found


def test_p2_8_refusal_messages_name_the_unit_the_new_key_and_the_reason():
    found = refusal(EP, P+"youngs_modulus", "200 mPa")
    assert "millipascal" in found.message
    found = refusal(EP, P+"youngs_modulus", 200e9)
    assert "Pa kPa MPa GPa psi ksi" in found.message
    found = refusal(EP, P+"youngs_modulus", "200 Mpa")
    assert [s.value for s in found.suggestions] == ["200 MPa"]
    found = refusal(EP, P+"youngs_modulus", "200GPa")
    assert "needs one space" in found.message
    found = refusal(TB, B+"linear_expansion_coefficient", "12 ppm/degC")
    assert found.fix is not None and found.fix.value == "12 ppm/K"
    found = refusal(TB, B+"stress_free_temperature", "68 degF")
    assert "degree Fahrenheit" in found.message
    found = refusal(ER, R+"gauge_pressure.inner", "1 atm")
    assert "standard atmosphere" in found.message
    for old, new in (("young_modulus_pa", "youngs_modulus"), ("displacement_m", "prescribed_displacement"),
                     ("traction_pa", "traction"), ("body_force_n_m3", "body_force_density"),
                     ("reference_temperature_k", "stress_free_temperature"),
                     ("thermal_expansion_per_k", "linear_expansion_coefficient"),
                     ("dirichlet_temperature_k", "prescribed_temperature")):
        name = TB if old in ("reference_temperature_k", "thermal_expansion_per_k", "dirichlet_temperature_k") else EP
        found = refusal(name, (B if name == TB else P)+old, 1.0)
        assert new in found.message and found.fix is None, old
    found = refusal(ER, R+"pressure_pa", {"inner": 1e7})
    assert "gauge_pressure" in found.message and "negated" not in found.message
    found = refusal(TB, B+"outward_flux_w_m2", {"top": 1.0})
    # the meaning changes, so the negation is a suggestion in words, never a fix
    assert "write inward_heat_flux" in found.message and "negated" in found.message and found.fix is None
    found = refusal(TB, B+"outward_heat_flux", {"top": "1 W/m^2"})
    assert found.message.startswith("inputs are inward_")
    for name, path, new in ((EP, P+"young_modulus", "youngs_modulus"), (EP, P+"E", "youngs_modulus"),
                            (TB, B+"alpha", "linear_expansion_coefficient"),
                            (TB, B+"thermal_expansion", "linear_expansion_coefficient"),
                            (ER, R+"pressure", "gauge_pressure"),
                            (TB, B+"reference_temperature", "stress_free_temperature")):
        assert f"Did you mean {new}" in refusal(name, path, "1 Pa").message, path
    found = refusal(EP, P+"gauge_pressure", {"right": "1 MPa"})
    assert "give a traction, or use a region document" in found.message
    found = refusal(EP, P+"traction.right", ["1 MPa"])
    assert "a global [x, y] vector" in found.message and "use gauge_pressure" in found.message
    found = refusal(EP, P+"absolute_pressure", {"right": "1 MPa"})
    assert "give the gauge_pressure" in found.message
    found = refusal(ER, R+"youngs_modulus", "200 GPa")
    assert "takes youngs_modulus from materials" in found.message
    found = refusal(EP, P+"stress_free_temperature", "293.15 K")
    assert "has no thermal stage; use mechanics.thermoelastic2d" in found.message


def test_p2_8_a_format_0_2_document_is_refused_by_name():
    for name in ("mechanics_r1_elastic_strain", "mechanics_k1_strain"):
        data = json.loads((FIXTURES.parent/"v02"/(name+".json")).read_text(encoding="utf-8"))
        with pytest.raises(DocumentError) as caught:
            Document.from_dict(data)
        assert [(d.code, d.path) for d in caught.value.diagnostics] == [("E-FORMAT", "openphysics")]
        assert "format 0.2 mechanics documents are not read" in str(caught.value)


def test_p2_8_an_axisymmetric_component_is_refused_as_today():
    data = example("thermoelastic_regions")
    component = data["geometry"]["components"]["main"]
    component["dimension"] = "axisymmetric"
    del component["depth"]
    with pytest.raises(DocumentError, match="takes 2d components only") as caught:
        Document.from_dict(data)
    assert [(d.code, d.path) for d in caught.value.diagnostics if d.severity == "error"] == [
        ("E-CONTRACT", "geometry.components")]


def test_p2_8_a_duplicate_key_is_refused():
    from simcase import reader
    text = json.dumps(example("elastic_plate")).replace('"plane": "stress",', '"plane": "stress", "plane": "strain",')
    with pytest.raises(DocumentError) as caught:
        reader.loads(text)
    assert [(d.code, d.path) for d in caught.value.diagnostics] == [("E-KEY-DUPLICATE", "physics.plate")]


def test_p2_8_the_registry_tightenings_are_refusals_now():
    # 0.2 accepted a reference temperature and prescribed or ambient temperatures of 0 K
    # (nonnegative); format 0.3 reads them as absolute temperatures above 0 K (registry domain)
    for name, path, value in ((TB, B+"stress_free_temperature", "0 K"), (TB, B+"prescribed_temperature.left", "0 K"),
                              (TR, S+"prescribed_temperature.left", "0 K")):
        assert refusal(name, path, value).code == "E-DOMAIN"


# ---- P2-9: diagnostics are never lost (G3 M6) ---------------------------------------------------

def noisy(acknowledged):
    """elastic_regions with a shape number 1e-6 pm and one 0.1 pm off the 1 pm grid, an unread
    material property, a Poisson ratio outside its band (acknowledged or not), a gauge pressure
    near one atmosphere and two traction-free sides."""
    data = example("elastic_regions")
    component = data["geometry"]["components"]["main"]
    component["features"][2]["r"] = 3.0000000000000004             # about 4e-4 pm off the grid
    component["domain"]["xmax"] = 9.0000000001                      # 0.1 pm: rounded with a warning
    steel = data["materials"]["steel"]
    steel["thermal_conductivity"] = "45 W/(m K)"
    steel["poisson_ratio"] = ({"value": 0.495, "accept": {"W-MAGNITUDE": "a nearly incompressible stand-in"}}
                              if acknowledged else 0.495)
    data["physics"]["pipe"]["gauge_pressure"]["inner"] = "100 kPa"
    where = "materials.steel.poisson_ratio" + (".value" if acknowledged else "")
    expected = [("I-PM-ROUNDING", MAIN+"features[2].r"), ("W-PM-ROUNDING", MAIN+"domain.xmax"),
                ("I-UNUSED-PROPERTY", "materials.steel.thermal_conductivity"), ("W-MAGNITUDE", where),
                ("W-GAUGE-ATMOSPHERIC", R+"gauge_pressure.inner"),
                ("I-DEFAULT-BOUNDARY", R+"traction.right"), ("I-DEFAULT-BOUNDARY", R+"traction.top")]
    return data, sorted(expected)


def pairs(diagnostics):
    return sorted((d["code"], d["path"]) if isinstance(d, dict) else (d.code, d.path) for d in diagnostics)


@pytest.mark.parametrize("acknowledged", [False, True])
def test_p2_9_mechanics_diagnostics_reach_every_output(tmp_path, capsys, acknowledged):
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
    assert main(["validate", str(model), "--strict"]) == 3
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
    bad["materials"]["steel"]["youngs_modulus"] = "-1 Pa"
    model.write_text(json.dumps(bad), encoding="utf-8")
    assert main(["validate", str(model)]) == 2


@pytest.mark.parametrize("path,value", [(P+"youngs_modulus", "200000 Pa"), (P+"poisson_ratio", 0.495),
                                        (P+"poisson_ratio", -0.2)])
def test_p2_9_rectangle_magnitude_warnings_are_kept(tmp_path, path, value):
    data = example("elastic_plate")
    put(data, path, value)
    _, _, summary, _ = saved(data, tmp_path/"out")
    assert ("W-MAGNITUDE", path) in pairs(summary["diagnostics"])


@pytest.mark.parametrize("value", ["12 1/K", "1.2e-5 ppm/K"])
def test_p2_9_expansion_coefficients_outside_the_band_warn(value):
    data = example("thermoelastic_bar")
    put(data, B+"linear_expansion_coefficient", value)
    assert ("W-MAGNITUDE", B+"linear_expansion_coefficient") in pairs(Document.from_dict(data).diagnostics)


@pytest.mark.parametrize("value", ["1 bar", "100 kPa", "14.5 psi"])
def test_p2_9_a_gauge_pressure_near_one_atmosphere_warns(value):
    data = example("elastic_regions")
    put(data, R+"gauge_pressure.inner", value)
    found = [d for d in Document.from_dict(data).diagnostics if d.code == "W-GAUGE-ATMOSPHERIC"]
    assert [d.path for d in found] == [R+"gauge_pressure.inner"]


def test_p2_9_rectangle_defaults_and_boundaries_reach_the_summary(tmp_path):
    _, _, summary, _ = saved(example("thermoelastic_bar"), tmp_path/"out")
    assert sorted((d["path"], d["value"], d["reason"]) for d in summary["defaults_applied"]) == [
        (B+"body_force_density", None, "absent: no body force (no value is assumed)"),
        (B+"heat_source_density", None, "absent: no volumetric heat source (no value is assumed)")]
    assert pairs(summary["diagnostics"]) == sorted(
        [("I-DEFAULT-BOUNDARY", B+"traction.right"), ("I-DEFAULT-BOUNDARY", B+"inward_heat_flux.bottom"),
         ("I-DEFAULT-BOUNDARY", B+"inward_heat_flux.top")])
    assert "body_force_density" not in summary and "heat_source_density" not in summary        # hazard H9
    assert summary["resolved_inputs"][B+"youngs_modulus"] == {"authored": "70 GPa", "value": 7e10, "unit": "Pa"}
    assert summary["timing"]["wall_time"]["solve"]["unit"] == "s"
    assert summary["extent"] and "length_unit mm" in summary["extent"][0]


# ---- P2-11: result names and metadata -----------------------------------------------------------

UNIT_TOKEN = re.compile(r"_(k|m|s|w|j|jk|pa|deg|m2|um|nm|hz|v|a|w_m2|w_mk|w_m3|w_m2k|j_m3k|s_m|s_per_m|n_m3|"
                        r"per_m|db_cm|db_90deg)$")
#: arrays without a unit (connectivity, node and DOF indices, region ids)
STRUCTURAL = {"triangles", "triangle_regions", "prescribed_node_ids", "prescribed_components",
              "thermal_prescribed_node_ids"}
#: summary maps keyed by the document's own names (regions, materials, boundaries, components)
NAMED = ("regions", "materials", "prescribed_displacement", "traction", "gauge_pressure", "prescribed_temperature",
         "inward_heat_flux", "convection", "heat_source_density", "field_units", "field_locations", "field_shapes",
         "field_components", "temperature_snapshot")


def keys(tree, skip=("resolved_inputs",)):
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


def is_quantity(key):
    try:
        units.quantity(key)
    except units.UnitError:
        return False
    return True


def quantity_objects(summary):
    """Each value object or tagged array of a summary with the quantity it is named by: the
    nearest key on its path that is a registry name (``regions.alu.area`` -> area,
    ``prescribed_displacement.left.x`` -> prescribed_displacement)."""
    out = []

    def walk(tree, path):
        if isinstance(tree, dict) and set(tree) in ({"value", "unit"}, {"values", "unit"}):
            out.append((next(k for k in reversed(path) if is_quantity(k)), tree))
        elif isinstance(tree, dict):
            for k, v in tree.items():
                walk(v, path + [k])
        elif isinstance(tree, list):
            for item in tree:
                walk(item, path)
    for key, value in summary.items():
        if key not in TEXTUAL + ("field_units", "field_locations", "field_shapes", "field_components"):
            walk(value, [key])
    return out


CASES = [("example", n) for n in RECTANGLES + REGIONS] + [
    ("fixture", n) for n in ("mechanics_k1_strain", "mechanics_r1_elastic_strain", "mechanics_r1_thermoelastic_stress",
                             "mechanics_r4_bore_0p5", "mechanics_r5b")]


@pytest.mark.parametrize("kind,name", CASES, ids=[n for _, n in CASES])
def test_p2_11_mechanics_result_names_and_units(tmp_path, kind, name):
    from simcase.export import RETIRED_LAYOUTS, SUPPORTED_LAYOUTS
    data = example(name) if kind == "example" else fixture(name)
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
        if unit != "1":                                  # a dimensionless array takes bare numbers
            assert units.convert(f"1 {unit}", array, path=array).value == 1.0
    for array, components in summary["field_components"].items():
        for component in components:
            if component not in ("x", "y"):          # strain_xx, stress_xy, ...: registry names (R-18)
                assert units.quantity(component).unit == summary["field_units"][array], component
    # every summary quantity is a registry name with its canonical unit, placed in results (R-31)
    found = quantity_objects(summary)
    assert found
    for key, vo in found:
        quantity = units.quantity(key)
        assert vo["unit"] == quantity.unit and "result" in quantity.places, key
    assert "poisson_ratio" not in summary or isinstance(summary["poisson_ratio"], float)       # bare
    assert summary["result_format"].endswith("-result-v2")
    assert summary["field_layout"].endswith("-v2")
    if "regions" not in summary:
        assert summary["field_layout"] in SUPPORTED_LAYOUTS
    assert not set(RETIRED_LAYOUTS) & set(SUPPORTED_LAYOUTS)
    assert "units" not in summary and "mesh_length_unit" not in summary and "input_units" not in summary
    assert not {"displacement_components", "strain_components", "stress_components"} & set(summary)


#: the energies' tolerance (relative; no absolute slack)
REL_ENERGY = 1e-11


def _recomputed_physical_energy(doc, fields):
    """The physical elastic energy per metre of depth (D-30, ``strain_energy_per_depth``) of a
    plane-stress thermoelastic result, recomputed from its saved arrays (node coordinates,
    triangles, displacement, nodal temperature) and the document's materials, geometry and
    stress-free temperature, with the P1 algebra written here (no galerkin or simcase assembly
    or energy function): the integral of the 3D elastic energy density
    1/2 (lambda tr(e)^2 + 2 mu e:e) of the elastic strain e = total strain - alpha (T - Tref) in
    the plane, with e_zz from sigma_zz = 0. The density is quadratic over a triangle (alpha
    (T - Tref) is linear there), so the edge-midpoint rule integrates it exactly; galerkin uses
    the reduced 2D form and an interior three-point rule."""
    assert doc["physics"]["strip"]["plane"] == "stress"
    materials, physics = doc.si["materials"], doc.si["physics"]["strip"]
    component = doc["geometry"]["components"]["main"]
    assert component["length_unit"] == "mm" and component["finalize"] == "later_wins"
    (feature,) = component["features"]
    assert feature["type"] == "rect"
    x, t, u = fields["node_coordinates"], fields["triangles"], fields["displacement"]
    temperature = fields["temperature"]
    p = x[t]                                                        # (T, 3, 2), m
    centroid = p.mean(axis=1)
    # the document's later-wins rule: the rect's material inside it, the background's elsewhere
    x0, y0, w, h = (float(feature[k])*1e-3 for k in ("x", "y", "w", "h"))   # mm, as written
    inside = ((centroid[:, 0] >= x0) & (centroid[:, 0] <= x0 + w) & (centroid[:, 1] >= y0) & (centroid[:, 1] <= y0 + h))
    for region in np.unique(fields["triangle_regions"]):            # the saved regions agree
        assert len(set(inside[fields["triangle_regions"] == region])) == 1
    names = np.where(inside, feature["material"], component["background"]["material"])
    e = np.array([materials[n]["youngs_modulus"] for n in names])
    nu = np.array([materials[n]["poisson_ratio"] for n in names])
    alpha = np.array([materials[n]["linear_expansion_coefficient"] for n in names])
    # P1 strains (exx, eyy, gamma_xy), constant per triangle
    xa, ya = p[:, :, 0], p[:, :, 1]
    b = np.stack([ya[:, 1] - ya[:, 2], ya[:, 2] - ya[:, 0], ya[:, 0] - ya[:, 1]], axis=1)
    c = np.stack([xa[:, 2] - xa[:, 1], xa[:, 0] - xa[:, 2], xa[:, 1] - xa[:, 0]], axis=1)
    twice = xa[:, 0]*b[:, 0] + xa[:, 1]*b[:, 1] + xa[:, 2]*b[:, 2]           # signed 2 * area
    area = np.abs(twice)/2
    ux, uy = u[t, 0], u[t, 1]
    exx, eyy = (b*ux).sum(axis=1)/twice, (c*uy).sum(axis=1)/twice
    gxy = (c*ux + b*uy).sum(axis=1)/twice
    # the 3D elastic energy density at the three edge midpoints, weight area/3 each
    lam, mu = e*nu/((1 + nu)*(1 - 2*nu)), e/(2*(1 + nu))
    nodal = alpha[:, None]*(temperature[t] - physics["stress_free_temperature"])     # (T, 3)
    physical = 0.0
    for i, j in ((0, 1), (1, 2), (2, 0)):
        a = 0.5*(nodal[:, i] + nodal[:, j])
        xx, yy = exx - a, eyy - a
        zz = -nu/(1 - nu)*(xx + yy)                                 # sigma_zz = 0
        trace = xx + yy + zz
        density = 0.5*(lam*trace**2 + 2*mu*(xx**2 + yy**2 + zz**2 + 0.5*gxy**2))
        physical += float(np.sum(area/3*density))
    return physical


def _defined_stiffness_functional(fields):
    """``stiffness_energy_functional_per_depth`` by its documented definition
    (docs/packages/simcase/mechanics2d.md: the solver's 1/2 u^T K u), 1/2 sum u (load + residual)
    with load = applied + thermal-equivalent force, evaluated here from the saved arrays
    (galerkin's residual is K u - load)."""
    load = fields["applied_force_per_depth"] + fields["thermal_equivalent_force_per_depth"]
    return float(0.5*np.sum(fields["displacement"]*(load + fields["residual_force_per_depth"])))


def test_p2_11_the_thermoelastic_energies_take_their_registry_meanings():
    """D-30: strain_energy_per_depth is the physical elastic energy; the solver's quadratic
    functional (which includes the thermal load term) is stiffness_energy_functional_per_depth.

    strain_energy_per_depth is recomputed independently from the result's saved arrays and the
    document (``_recomputed_physical_energy``) and compared within REL_ENERGY on whatever mesh
    this machine makes. stiffness_energy_functional_per_depth is compared within REL_ENERGY with
    its documented definition, 1/2 sum u (load + residual), re-evaluated from the saved arrays
    (``_defined_stiffness_functional``): this check ties the name to its definition and is not
    independent. An independent 1/2 u^T K u is not compared at REL_ENERGY because the summary's
    functional is accurate only to about 2e-11 relative here: the saved load + residual
    reproduces K u only up to galerkin's rounding of a strongly cancelling K u (the bending
    strip's displacement is mostly near-rigid motion). Measured against an independent
    1/2 sum area eps^T D eps: 6.2e-12 (default), 7.4e-12 (OpenBLAS Haswell), 2.0e-11 (OpenBLAS
    Sandybridge), 1.2e-11 (numpy limited to AVX2, Haswell).

    This replaces two pinned numbers (format 0.2's physical_elastic_energy_j_per_m and
    strain_energy_j_per_m of the batch baseline, within 1e-11): they assumed a CPU-independent
    mesh, but meshine's mesh of this example depends on numpy's SIMD level (on an AVX2 CPU 42 of
    its 3414 nodes move, by up to 0.12 mm), and the functional also moves by 4.3e-11 relative
    with the OpenBLAS kernel on the same mesh. That this code gives the baseline's two numbers
    bitwise stays the job of P2-1, whose thermoelastic maps include both energies."""
    doc = Document.from_dict(example("thermoelastic_regions"))
    result = run(doc, verbose=False)
    balance = result.summary()["balance"]
    physical = _recomputed_physical_energy(doc, result.fields)
    functional = _defined_stiffness_functional(result.fields)
    assert balance["strain_energy_per_depth"]["value"] == pytest.approx(physical, rel=REL_ENERGY, abs=0)
    assert balance["stiffness_energy_functional_per_depth"]["value"] == pytest.approx(functional, rel=REL_ENERGY,
                                                                                         abs=0)
    assert abs(functional - physical) > 1e-3*max(functional, physical)    # a swap of the names fails
    elastic = run(Document.from_dict(example("elastic_plate")), verbose=False).summary()["balance"]
    assert "stiffness_energy_functional_per_depth" not in elastic and "strain_energy_per_depth" in elastic


# ---- P2-14: sign sanity -------------------------------------------------------------------------

def test_p2_14_a_positive_gauge_pressure_in_the_bore_pushes_the_wall_outward():
    result = run(Document.from_dict(example("elastic_regions")), verbose=False)
    nodes, u = result.fields["node_coordinates"], result.fields["displacement"]
    r = np.hypot(nodes[:, 0], nodes[:, 1])
    bore = np.isclose(r, 3e-3, rtol=0, atol=1e-9)
    assert bore.sum() >= 3
    radial = (u[bore] * nodes[bore]).sum(axis=1) / r[bore]
    assert np.all(radial > 0)
    summary = result.summary()
    assert summary["gauge_pressure"]["inner"] == {"value": 1e7, "unit": "Pa"}
    assert summary["gauge_pressure_sign"] == ("traction = −gauge_pressure · n, n the outward normal; "
                                              "positive pushes into the body")


# ---- P2-18: export ------------------------------------------------------------------------------

@pytest.mark.parametrize("name", RECTANGLES)
def test_p2_18_a_mechanics_result_exports_its_units_and_conventions(tmp_path, name):
    meshio = pytest.importorskip("meshio")
    import xml.etree.ElementTree as ET
    from simcase.export import export_fields, read_field_data
    _, out, summary, arrays = saved(example(name), tmp_path/"out")
    vtu = export_fields(out/"fields.npz", tmp_path/"fields.vtu")
    mesh = meshio.read(vtu)
    split = {component: (array, k) for array, components in summary["field_components"].items()
             if arrays[array].ndim == 2 and arrays[array].shape[1] == 3 for k, component in enumerate(components)}
    exported = set(mesh.point_data) | set(mesh.cell_data)
    unit_of = {}
    for name_ in exported:
        data = mesh.point_data[name_] if name_ in mesh.point_data else mesh.cell_data[name_][0]
        if name_ in split:                                  # a named component of a (T, 3) array
            array, k = split[name_]
            np.testing.assert_array_equal(data, arrays[array][:, k])
            unit_of[name_] = summary["field_units"][array]
            continue
        saved_array = arrays[name_]
        if saved_array.ndim == 2 and data.shape[1] == 3:    # a 2D vector, padded with z = 0
            assert not data[:, 2].any()
            data = data[:, :2]
        np.testing.assert_array_equal(data, saved_array)
        unit_of[name_] = summary["field_units"][name_]
    np.testing.assert_array_equal(mesh.points[:, :2], arrays["node_coordinates"])
    block = read_field_data(vtu)
    assert block["units"] == unit_of
    assert block["conventions"]["sign"]["reaction_force_per_depth"]
    assert {k: json.loads(bytes(v).decode("utf-8")) for k, v in mesh.field_data.items()} == block
    assert all(a.get("type") == "UInt8" for a in ET.parse(vtu).getroot().iter("DataArray")
               if a.get("Name") in ("units", "conventions"))
    assert b'type="String"' not in vtu.read_bytes()


@pytest.mark.parametrize("layout", ["mechanics2d-p1-v1", "thermoelastic2d-p1-v1"])
def test_p2_18_a_retired_layout_is_refused_by_name(tmp_path, layout):
    from simcase.export import export_fields
    fields = tmp_path/"fields.npz"
    np.savez(fields, field_layout=np.array(layout), nodes_m=np.zeros((3, 2)), triangles=np.array([[0, 1, 2]]))
    with pytest.raises(ValueError, match=re.escape(f"(layout {layout})")):
        export_fields(fields, tmp_path/"fields.vtu")


@pytest.mark.parametrize("name", REGIONS)
def test_p2_18_region_mechanics_export_is_still_refused(tmp_path, name):
    from simcase.export import export_fields
    _, out, summary, _ = saved(example(name), tmp_path/"out")
    with pytest.raises(ValueError, match=f"unsupported field layout '{summary['field_layout']}'"):
        export_fields(out/"fields.npz", tmp_path/"fields.vtu")
    assert not (tmp_path/"fields.vtu").exists()
