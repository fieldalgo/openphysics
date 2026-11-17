# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""``joule.temperature2d`` on named material regions of a version 1 geometry block.

Pre-registered checks T1 to T7 (HQ work record
``work/openphysics-geometry-joule-temperature-regions.md``, HQ commit 8ac66cdc, 2026-11-15,
recorded before the implementation): a series strip of two ``linear_resistivity`` materials against an independent
closed form (T1), the adapter against a direct galerkin call (T2), the power balance (T3), zero
coefficients against region ``joule.steady2d`` (T4), refusals by name (T5) and the saved and
exported result (T7). T6 (the rectangle examples' saved results unchanged against main) is a
measurement recorded with the commit, not a test.
"""
import copy
import math

import numpy as np
import pytest
from scipy.optimize import brentq

from simcase import Document, DocumentError, run

L = 1e-3                      # each half of the 2 x 1 mm strip, m
H = 1e-3                      # strip height, m
T_REF = 300.0                 # reference temperature of both models, K
T_LEFT, T_RIGHT = 300.0, 320.0
VOLTS = 0.2
SIGMA = {"A": 2.0e3, "B": 0.5e3}          # reference conductivities, S/m
ALPHA = {"A": 4e-3, "B": -3e-3}           # resistivity temperature coefficients, 1/K
KAPPA = {"A": 1.5, "B": 0.25}             # W/(m K)
RIGHT_HALF = {"name": "b", "type": "rect", "x": 1, "y": 0, "w": 1, "h": 1, "material": "B"}
SERIES = {"prescribed_electric_potential": {"left": f"{VOLTS!r} V", "right": "0 V"},
          "prescribed_temperature": {"left": f"{T_LEFT!r} K", "right": f"{T_RIGHT!r} K"},
          "initial_temperature": "300 K", "iteration": {"temperature_tolerance": "1e-9 K"}}


def linear_resistivity(sigma, alpha, valid=("250 K", "600 K"), reference=T_REF):
    return {"model": "linear_resistivity", "reference_conductivity": f"{sigma!r} S/m",
            "reference_temperature": f"{reference!r} K", "resistivity_temperature_coefficient": f"{alpha!r} 1/K",
            "valid": {"temperature": list(valid)}}


def materials(alpha=ALPHA):
    return {m: {"electrical_conductivity": linear_resistivity(SIGMA[m], alpha[m]),
                "thermal_conductivity": f"{KAPPA[m]!r} W/(m K)"} for m in ("A", "B")}


def strip(physics=SERIES, *, size=0.125, kind="joule.temperature2d", mats=None, selections=None):
    """A version 1 document in mm on a 2 x 1 mm strip: A on the left half, B on the right."""
    comp = {"dimension": "2d", "length_unit": "mm", "depth": None,
            "domain": {"xmin": 0, "xmax": 2, "ymin": 0, "ymax": 1},
            "background": {"material": "A"}, "features": [dict(RIGHT_HALF)]}
    if selections:
        comp["selections"] = selections
    return {"openphysics": "0.3", "name": "joule temperature strip",
            "geometry": {"version": 1, "components": {"xs": comp}},
            "materials": materials() if mats is None else mats,
            "physics": {"j": {"type": kind, **copy.deepcopy(physics)}},
            "mesh": {"element_size": f"{size!r} mm"}, "study": {"type": "single"},
            "results": {"save_fields": True, "plots": False}}


def _basis(m, s):
    """c(s), d(s) with c'' = -m c, d'' = -m d, c(0) = 1, c'(0) = 0, d(0) = 0, d'(0) = 1, and
    the integrals of c and d over [0, s]."""
    if m > 0:
        w = math.sqrt(m)
        c, d = math.cos(w * s), math.sin(w * s) / w
    elif m < 0:
        w = math.sqrt(-m)
        c, d = math.cosh(w * s), math.sinh(w * s) / w
    else:
        return 1.0, s, s, s * s / 2
    return c, d, d, (1.0 - c) / m


def series_solution(j):
    """The exact 1D state of the series strip for a current density ``j`` (A/m^2).

    In each material rho(T) = rho0 (1 + a (T - T_ref)) with rho0 = 1 / sigma_ref; J is constant
    along a series strip with insulated top and bottom, so the heat equation k T'' + J^2 rho(T) = 0
    reads, for theta = 1 + a (T - T_ref),

        theta'' = -m theta,   m = a J^2 rho0 / k,

    a linear ODE: theta = A c(s) + B d(s) in the local coordinate s of the material, with c, d
    trigonometric for m > 0 (a > 0), hyperbolic for m < 0 (a < 0). T(0) = T_LEFT fixes A of
    material A; T(2 L) = T_RIGHT, continuity of T = T_ref + (theta - 1) / a and of the heat flux
    k T' = k theta' / a at x = L give a 3 x 3 linear system for the other coefficients. The
    voltage is V(0) - V(2 L) = J * integral of rho = J sum rho0_i integral theta_i.
    Returns (coefficients {material: (A, B, m)}, voltage)."""
    rho0 = {k: 1.0 / v for k, v in SIGMA.items()}
    m = {k: ALPHA[k] * j * j * rho0[k] / KAPPA[k] for k in SIGMA}
    a_a = 1.0 + ALPHA["A"] * (T_LEFT - T_REF)
    c_a, d_a, _, _ = _basis(m["A"], L)
    c_b, d_b, _, _ = _basis(m["B"], L)
    # unknowns B_A, A_B, B_B
    rows = [[0.0, c_b, d_b],                                             # theta_B(L) at x = 2 L
            [d_a / ALPHA["A"], -1.0 / ALPHA["B"], 0.0],                  # T continuous at x = L
            [KAPPA["A"] * c_a / ALPHA["A"], 0.0, -KAPPA["B"] / ALPHA["B"]]]   # k T' continuous
    rhs = [1.0 + ALPHA["B"] * (T_RIGHT - T_REF),
           (1.0 - a_a * c_a) / ALPHA["A"] - 1.0 / ALPHA["B"],
           KAPPA["A"] * m["A"] * a_a * d_a / ALPHA["A"]]
    b_a, a_b, b_b = np.linalg.solve(np.array(rows), np.array(rhs))
    coefficients = {"A": (a_a, b_a, m["A"]), "B": (a_b, b_b, m["B"])}
    volts = j * sum(rho0[k] * (a * _basis(mk, L)[2] + b * _basis(mk, L)[3]) for k, (a, b, mk) in coefficients.items())
    return coefficients, volts


def series_current_density():
    """J with V(0) - V(2 L) = VOLTS, by a bracketed root around the linear estimate."""
    linear = VOLTS / (L / SIGMA["A"] + L / SIGMA["B"])
    return brentq(lambda j: series_solution(j)[1] - VOLTS, 0.5 * linear, 2.0 * linear, xtol=1e-14, rtol=1e-15)


def series_temperature(x):
    j = series_current_density()
    coefficients, _ = series_solution(j)
    out = np.empty_like(x)
    for k, lo in (("A", 0.0), ("B", L)):
        a, b, m = coefficients[k]
        inside = (x >= lo - 1e-15) & (x <= lo + L + 1e-15)
        theta = np.array([a * c + b * d for c, d in (_basis(m, s)[:2] for s in x[inside] - lo)])
        out[inside] = T_REF + (theta - 1.0) / ALPHA[k]
    return out, j


def test_the_closed_form_is_continuous_and_reduces_to_the_linear_strip():
    # interface continuity of T and k T' (independent of the solve), and V at the root
    j = series_current_density()
    coefficients, volts = series_solution(j)
    assert abs(volts - VOLTS) <= 1e-12 * VOLTS
    (a1, b1, m1), (a2, b2, m2) = coefficients["A"], coefficients["B"]
    c1, d1, _, _ = _basis(m1, L)
    t_left_of_l = T_REF + (a1 * c1 + b1 * d1 - 1) / ALPHA["A"]
    t_right_of_l = T_REF + (a2 - 1) / ALPHA["B"]
    assert abs(t_left_of_l - t_right_of_l) <= 1e-9
    flux_a = KAPPA["A"] * (-m1 * a1 * d1 + b1 * c1) / ALPHA["A"]
    flux_b = KAPPA["B"] * b2 / ALPHA["B"]
    assert abs(flux_a - flux_b) <= 1e-9 * abs(flux_a)
    t, _ = series_temperature(np.array([0.0, 2 * L]))
    np.testing.assert_allclose(t, [T_LEFT, T_RIGHT], rtol=0, atol=1e-9)


def test_t1_series_strip_converges_to_the_closed_form():
    errors, current = [], []
    for size in (0.25, 0.125, 0.0625):
        result = run(Document.from_dict(strip(size=size)), verbose=False)
        fields = result.fields
        exact, j = series_temperature(fields["node_coordinates"][:, 0])
        rise = float(np.max(exact) - np.min(exact))
        errors.append(float(np.max(np.abs(fields["temperature"] - exact))) / rise)
        outward = result.summary()["balance"]["outward_current_per_depth"]
        current.append(abs(outward["right"]["value"] - j * H) / (j * H))
        assert abs(outward["left"]["value"] + outward["right"]["value"]) <= 1e-9 * j * H
    assert errors[0] > errors[1] > errors[2], errors
    order = math.log(errors[-2] / errors[-1], 2)
    assert order >= 1.5 and errors[-1] <= 5e-3, (errors, order)
    assert current[-1] <= 5e-3, current


def _direct(raw):
    """galerkin's solve_temperature_joule_heat on the adapter's mesh, with inputs written here."""
    from galerkin.temperature_joule_heating import ConductivityModel, solve_temperature_joule_heat
    from simcase.thermal_regions import build_region_mesh, handoff_03
    doc = Document.from_dict(raw)
    mesh, region_materials, _ = build_region_mesh(handoff_03(doc))

    def law(sigma, alpha):
        return lambda t: sigma / (1. + alpha * (t - T_REF))
    models = {r: ConductivityModel(law(SIGMA[m], ALPHA[m]), (250.0, 600.0)) for r, m in region_materials.items()}
    electric = {int(n): v for side, v in (("left", VOLTS), ("right", 0.0)) for n in mesh.boundary[side]}
    thermal = {int(n): v for side, v in (("left", T_LEFT), ("right", T_RIGHT)) for n in mesh.boundary[side]}
    return mesh, solve_temperature_joule_heat(
        mesh, electrical_conductivity=models, thermal_conductivity={r: KAPPA[m] for r, m in region_materials.items()},
        prescribed_electric_potential=dict(sorted(electric.items())),
        prescribed_temperature=dict(sorted(thermal.items())),
        initial_temperature=300.0, inward_current_density={}, inward_heat_flux={}, convection={}, method="picard",
        relaxation_factor=0.5, relative_tolerance=1e-10, iteration_limit=100, temperature_tolerance=1e-9)


def test_t2_the_adapter_equals_a_direct_galerkin_call_bit_for_bit():
    raw = strip()
    mesh, direct = _direct(raw)
    result = run(Document.from_dict(raw), verbose=False)
    fields = result.fields
    np.testing.assert_array_equal(fields["node_coordinates"], mesh.nodes)
    for key, value in (("temperature", direct.coupled.thermal.temperature),
                       ("electric_potential", direct.coupled.electrical.electric_potential),
                       ("evaluation_temperature", direct.evaluation_temperature),
                       ("joule_power_density", direct.coupled.electrical.joule_power_density),
                       ("heat_flux", direct.coupled.thermal.heat_flux)):
        assert fields[key].tobytes() == np.asarray(value).tobytes(), key
    history = result.summary()["iterations"]
    assert len(history) == len(direct.history)
    assert [r["temperature_change"]["value"] for r in history] == [r.temperature_change for r in direct.history]


def test_t3_supplied_joule_and_outward_power_agree():
    summary = run(Document.from_dict(strip()), verbose=False).summary()
    d = {k: v["value"] for k, v in summary["balance"].items() if "value" in v}
    power = d["joule_power_per_depth"]
    assert power > 0
    assert abs(d["inward_electric_power_per_depth"] - power) <= 1e-9 * power
    assert abs(d["outward_heat_rate_per_depth"] - power) <= 1e-9 * power
    assert summary["status"] == "converged" and summary["iterations"][-1]["relative_residual"]["value"] <= 1e-8


@pytest.mark.parametrize("form", ["zero_coefficients", "constants"])
def test_t4_without_temperature_dependence_it_equals_region_steady_joule(form):
    if form == "zero_coefficients":
        mats = materials({"A": 0.0, "B": 0.0})
    else:
        mats = {m: {"electrical_conductivity": f"{SIGMA[m]!r} S/m", "thermal_conductivity": f"{KAPPA[m]!r} W/(m K)"}
                for m in ("A", "B")}
    steady_mats = {m: {"electrical_conductivity": f"{SIGMA[m]!r} S/m", "thermal_conductivity": f"{KAPPA[m]!r} W/(m K)"}
                   for m in ("A", "B")}
    steady_physics = {k: v for k, v in SERIES.items() if k not in ("initial_temperature", "iteration")}
    nonlinear = run(Document.from_dict(strip(mats=mats)), verbose=False).fields
    steady = run(Document.from_dict(strip(steady_physics, kind="joule.steady2d", mats=steady_mats)),
                 verbose=False).fields
    np.testing.assert_array_equal(nonlinear["node_coordinates"], steady["node_coordinates"])
    for key in ("temperature", "electric_potential"):
        scale = float(np.max(np.abs(steady[key])))
        assert float(np.max(np.abs(nonlinear[key] - steady[key]))) <= 1e-10 * scale, key


def _axisymmetric(raw):
    comp = raw["geometry"]["components"]["xs"]
    comp.update(dimension="axisymmetric")
    del comp["depth"]


def _disjoint(raw):
    raw["materials"]["A"]["electrical_conductivity"]["valid"]["temperature"] = ["250 K", "310 K"]
    raw["materials"]["B"]["electrical_conductivity"].update(reference_temperature="400 K",
                                                            valid={"temperature": ["350 K", "600 K"]})


def _narrow_b(raw):
    raw["materials"]["B"]["electrical_conductivity"]["valid"]["temperature"] = ["290 K", "310 K"]


def _model_in(kind):
    def change(raw):
        raw["physics"]["j"]["type"] = kind
        for key in ("initial_temperature", "iteration"):
            raw["physics"]["j"].pop(key)
        raw["materials"]["B"]["electrical_conductivity"] = "500 S/m"
        if kind == "electric.steady2d":
            raw["physics"]["j"].pop("prescribed_temperature")
            for m in ("A", "B"):
                raw["materials"][m].pop("thermal_conductivity")
    return change


E = "materials.A.electrical_conductivity"
REFUSALS = [
    ("physics-entry conductivity",
     lambda raw: raw["physics"]["j"].update(electrical_conductivity=linear_resistivity(2e3, 4e-3)),
     "takes electrical_conductivity from materials", "E-CONTRACT", "physics.j.electrical_conductivity"),
    ("physics-entry constant conductivity",
     lambda raw: raw["physics"]["j"].update(electrical_conductivity="2 S/m"),
     "takes electrical_conductivity from materials", "E-CONTRACT", "physics.j.electrical_conductivity"),
    ("physics-entry thermal conductivity", lambda raw: raw["physics"]["j"].update(thermal_conductivity="1 W/(m K)"),
     "takes thermal_conductivity from materials", "E-CONTRACT", "physics.j.thermal_conductivity"),
    ("model in joule.steady2d", _model_in("joule.steady2d"), "only joule.temperature2d", "E-CONTRACT", E),
    ("model in electric.steady2d", _model_in("electric.steady2d"), "only joule.temperature2d", "E-CONTRACT", E),
    ("prescribed outside the intersection", _narrow_b, "outside the intersection of the conductivity models",
     "E-OUTSIDE-VALID", "physics.j.prescribed_temperature.right"),
    ("initial outside", lambda raw: raw["physics"]["j"].update(initial_temperature="700 K"),
     "outside the intersection", "E-OUTSIDE-VALID", "physics.j.initial_temperature"),
    ("ambient outside", lambda raw: raw["physics"]["j"].update(convection={"top": {
        "heat_transfer_coefficient": "10 W/(m^2 K)", "ambient_temperature": "200 K"}}),
     "outside the intersection", "E-OUTSIDE-VALID", "physics.j.convection.top.ambient_temperature"),
    ("disjoint ranges", _disjoint, "does not overlap the valid.temperature", "E-CONTRACT",
     "materials.B.electrical_conductivity.valid.temperature"),
    ("reference outside its range",
     lambda raw: raw["materials"]["A"]["electrical_conductivity"].update(reference_temperature="700 K"),
     "reference_temperature must lie inside valid.temperature", "E-OUTSIDE-VALID", E + ".reference_temperature"),
    ("non-positive end of the range",
     lambda raw: raw["materials"]["B"]["electrical_conductivity"].update(resistivity_temperature_coefficient="-0.01 1/K"),
     "not positive and finite", "E-CONTRACT", "materials.B.electrical_conductivity.resistivity_temperature_coefficient"),
    ("zero constant", lambda raw: raw["materials"]["A"].update(electrical_conductivity="0 S/m"),
     "expected a positive conductivity", "E-DOMAIN", E),
    ("heat source", lambda raw: raw["physics"]["j"].update(heat_source_density="1 W/m^3"),
     "heated by its current only", "E-CONTRACT", "physics.j.heat_source_density"),
    ("axisymmetric", _axisymmetric, "axisymmetric component is not supported", "E-CONTRACT", "geometry.components"),
    ("missing thermal conductivity", lambda raw: raw["materials"]["B"].pop("thermal_conductivity"),
     "required by temperature-dependent Joule heating", "E-PROPERTY-MISSING", "materials.B.thermal_conductivity"),
    ("missing initial temperature", lambda raw: raw["physics"]["j"].pop("initial_temperature"),
     "initial_temperature", "E-KEY-MISSING", "physics.j.initial_temperature"),
    ("relaxation above 1", lambda raw: raw["physics"]["j"]["iteration"].update(relaxation_factor=1.5),
     "0 < relaxation_factor <= 1", "E-DOMAIN", "physics.j.iteration.relaxation_factor"),
    ("unknown model key", lambda raw: raw["materials"]["A"]["electrical_conductivity"].update(alpha="0.004 1/K"),
     "resistivity_temperature_coefficient", "E-KEY-UNKNOWN", E + ".alpha"),
]


@pytest.mark.parametrize("change, message, code, path", [row[1:] for row in REFUSALS], ids=[row[0] for row in REFUSALS])
def test_t5_refusals_name_what_is_wrong(change, message, code, path):
    raw = strip()
    change(raw)
    with pytest.raises(DocumentError, match=message) as error:
        Document.from_dict(raw)
    assert [(d.code, d.path) for d in error.value.diagnostics if d.severity == "error"] == [(code, path)]


def test_t5_a_format_0_2_document_is_refused_by_name():
    raw = strip()
    raw["openphysics"] = "0.2"
    with pytest.raises(DocumentError) as error:
        Document.from_dict(raw)
    assert [(d.code, d.path) for d in error.value.diagnostics if d.severity == "error"] == [("E-FORMAT", "openphysics")]


def test_a_constant_material_beside_a_model_material_runs_and_its_conductivity_stays_constant():
    mats = materials()
    mats["B"]["electrical_conductivity"] = "500 S/m"
    result = run(Document.from_dict(strip(mats=mats)), verbose=False)
    fields, summary = result.fields, result.summary()
    regions = summary["region_names"]
    in_b = np.array([regions[i] == "b" for i in fields["triangle_regions"]])
    assert np.all(fields["electrical_conductivity"][in_b] == 500.0)
    assert summary["regions"]["b"]["electrical_conductivity"] == {"value": 500.0, "unit": "S/m"}
    model = summary["regions"]["background"]["electrical_conductivity"]
    assert model["model"] == "linear_resistivity" and model["valid"]["temperature"][1] == {"value": 600.0, "unit": "K"}
    # the model material's conductivity follows its law at the evaluation temperature
    t = fields["evaluation_temperature"][fields["triangles"][~in_b]].mean(axis=1)
    np.testing.assert_allclose(fields["electrical_conductivity"][~in_b], SIGMA["A"] / (1 + ALPHA["A"] * (t - T_REF)),
                               rtol=1e-12)


def test_a_failed_iteration_keeps_its_history():
    from galerkin.temperature_joule_heating import JouleConvergenceError
    raw = strip()
    raw["physics"]["j"]["iteration"]["iteration_limit"] = 2
    with pytest.raises(JouleConvergenceError) as error:
        run(Document.from_dict(raw), verbose=False)
    assert error.value.reason == "maximum iterations exceeded" and len(error.value.history) == 2


def test_t7_a_saved_result_records_its_layout_and_exports_with_region_ids(tmp_path):
    from simcase.export import RETIRED_LAYOUTS, SUPPORTED_LAYOUTS, export_fields
    assert SUPPORTED_LAYOUTS[15] == "electric-joule2d-p1-node-cell-regions-v2"   # appended after it
    assert SUPPORTED_LAYOUTS[16] == "electric-joule2d-temperature-p1-node-cell-regions-v2"
    assert SUPPORTED_LAYOUTS[16] not in RETIRED_LAYOUTS
    result = run(Document.from_dict(strip()), verbose=False)
    summary = result.summary()
    assert summary["result_format"] == "joule.temperature2d-regions-result-v2"
    assert summary["physics_type"] == "joule.temperature2d"
    assert summary["field_units"]["evaluation_temperature"] == "K"
    assert summary["field_locations"]["triangle_regions"] == "triangles"
    result.save(tmp_path / "out")
    with np.load(tmp_path / "out" / "fields.npz") as data:
        assert str(data["field_layout"]) == "electric-joule2d-temperature-p1-node-cell-regions-v2"
        assert str(data["result_format"]) == "joule.temperature2d-regions-result-v2"
        assert data["triangle_regions"].shape == data["triangles"].shape[:1]
        np.testing.assert_array_equal(data["evaluation_temperature"], result.fields["evaluation_temperature"])
    reloaded = Document.from_dict(__import__("json").loads((tmp_path / "out" / "model.json").read_text()))
    assert reloaded.si == Document.from_dict(strip()).si
    meshio = pytest.importorskip("meshio")
    mesh = meshio.read(export_fields(tmp_path / "out" / "fields.npz", tmp_path / "out" / "fields.vtu"))
    np.testing.assert_array_equal(mesh.point_data["temperature"], result.fields["temperature"])
    np.testing.assert_array_equal(mesh.point_data["evaluation_temperature"], result.fields["evaluation_temperature"])
    np.testing.assert_array_equal(mesh.cell_data["triangle_regions"][0], result.fields["triangle_regions"])


def test_a_flat_regions_document_runs_like_the_version_1_block():
    raw = strip()
    raw["geometry"] = {"length_unit": "mm", "depth": None, "domain": {"xmin": 0, "xmax": 2, "ymin": 0, "ymax": 1},
                       "background": {"material": "A"}, "shapes": [dict(RIGHT_HALF)]}
    flat = run(Document.from_dict(raw), verbose=False)
    assert flat.summary()["result_format"] == "joule.temperature2d-regions-result-v2"
    fields = flat.fields
    exact, _ = series_temperature(fields["node_coordinates"][:, 0])
    # the flat form meshes on its own (another node count); T1 gives 2.0e-3 at this size
    assert np.max(np.abs(fields["temperature"] - exact)) / (np.max(exact) - np.min(exact)) <= 1e-2


def test_the_summary_text_names_the_models_and_the_layout():
    text = Document.from_dict(strip()).summary()
    assert "material A: electrical_conductivity linear_resistivity (reference_conductivity 2000.0 S/m" in text
    assert "valid.temperature [250 K, 600 K]" in text
    assert "electric-joule2d-temperature-p1-node-cell-regions-v2" in text


def _thermal(kind):
    def change(raw):
        _model_in("joule.steady2d")(raw)
        raw["physics"]["j"] = {"type": kind, "prescribed_temperature": {"left": "300 K", "right": "320 K"}}
        if kind == "thermal.transient2d":
            raw["physics"]["j"]["initial_temperature"] = "300 K"
            raw["study"] = {"type": "transient", "time": ["0 s", "1 s"]}
    return change


@pytest.mark.parametrize("change", [
    _model_in("joule.steady2d"), _model_in("electric.steady2d"), _thermal("thermal.steady2d"),
], ids=["joule.steady2d", "electric.steady2d", "thermal.steady2d"])
@pytest.mark.parametrize("model", ["complete", "incomplete", "unused material"])
def test_a_material_model_is_refused_by_name_where_the_physics_does_not_read_it(change, model):
    # the reader refuses it before reading its keys, on every material, used or not
    raw = strip()
    change(raw)
    where = "materials.A.electrical_conductivity"
    if model == "incomplete":
        raw["materials"]["A"]["electrical_conductivity"] = {"model": "linear_resistivity"}
    elif model == "unused material":
        raw["materials"]["A"]["electrical_conductivity"] = "2000 S/m"
        raw["materials"]["C"] = {"electrical_conductivity": linear_resistivity(1.0, 1e-3),
                                 "thermal_conductivity": "1 W/(m K)"}
        where = "materials.C.electrical_conductivity"
    with pytest.raises(DocumentError, match="only joule.temperature2d") as error:
        Document.from_dict(raw)
    assert [(d.code, d.path) for d in error.value.diagnostics if d.severity == "error"] == [("E-CONTRACT", where)]


def test_a_rectangle_keeps_refusing_a_constant_on_its_physics_entry():
    from simcase.examples import EXAMPLES
    raw = copy.deepcopy(EXAMPLES["joule_temperature"])
    raw["physics"]["electric"]["electrical_conductivity"] = "2 S/m"
    with pytest.raises(DocumentError, match="takes a model object here") as error:
        Document.from_dict(raw)
    assert [(d.code, d.path) for d in error.value.diagnostics if d.severity == "error"] == [
        ("E-VALUE-FORM", "physics.electric.electrical_conductivity")]
