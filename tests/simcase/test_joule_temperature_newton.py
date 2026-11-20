# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""``joule.temperature2d`` ``iteration.method``: Newton chosen by the document.

Pre-registered checks N1 to N8 (HQ work record ``work/openphysics-joule-temperature-newton.md``,
HQ commit 622cf853, 2026-11-20, recorded before the implementation). Newton and Picard share
galerkin's convergence judgment, so where both converge they agree to the tolerance of
tests/galerkin/test_temperature_joule_newton.py: temperature and potential within 2e-8 (K, V),
conductivity within 1e-10 relative (the last as in its every-boundary-kind test; the
conductivity is compared with a Picard of relative_tolerance 1e-11, ``tight``). N1 and N2: agreement on the shipped example and the region
T1 strip; N3: a strongly nonlinear rectangle (galerkin's thermistor) where the default Picard
fails; N4: the T1 closed form with Newton; N5: the adapter against a direct galerkin call;
N6: a written ``"method": "picard"`` gives the result of no method (the comparison with the
commit before is a measurement recorded with the commit); N7: refusals by name; N8: the
summary and the saved result.
"""
import copy
import json
import math

import numpy as np
import pytest

from simcase import Document, DocumentError, run
from simcase.examples import EXAMPLES
from galerkin.temperature_joule_heating import METHODS, JouleConvergenceError

from test_joule_temperature_regions import H, _direct, series_temperature, strip

T_ATOL = V_ATOL = 2e-8          # K, V: the shared Newton/Picard tolerance (galerkin tests)
SIGMA_RTOL = 1e-10


def newton(raw):
    """``raw`` with ``iteration.method: "newton"`` and no authored ``relaxation_factor``."""
    raw = copy.deepcopy(raw)
    iteration = next(iter(raw["physics"].values()))["iteration"]
    iteration.pop("relaxation_factor", None)
    iteration["method"] = "newton"
    return raw


def example():
    return copy.deepcopy(EXAMPLES["joule_temperature"])


def tight(raw):
    """``raw`` with Picard's ``relative_tolerance`` at 1e-11. Picard stops when its last relative
    conductivity step is <= 1e-10, but its remaining error is q / (1 - q) times that step (q its
    contraction a step), at or above 1e-10 once q > 0.5: N3 failed on exactly that (see N3). So
    the conductivity is compared with this tighter Picard; the threshold is unchanged."""
    raw = copy.deepcopy(raw)
    next(iter(raw["physics"].values()))["iteration"]["relative_tolerance"] = 1e-11
    return raw


def assert_agree(a, b, sigma=True):
    fa, fb = a.fields, b.fields
    np.testing.assert_array_equal(fa["node_coordinates"], fb["node_coordinates"])
    np.testing.assert_allclose(fa["temperature"], fb["temperature"], rtol=0, atol=T_ATOL)
    np.testing.assert_allclose(fa["electric_potential"], fb["electric_potential"], rtol=0, atol=V_ATOL)
    if sigma:
        np.testing.assert_allclose(fa["electrical_conductivity"], fb["electrical_conductivity"], rtol=SIGMA_RTOL)


def assert_agree_with_picard(solved, raw):
    """T and V against the Picard of ``raw`` as given, all three against its tight form."""
    assert_agree(solved, run(Document.from_dict(raw), verbose=False), sigma=False)
    assert_agree(solved, run(Document.from_dict(tight(raw)), verbose=False))


def thermistor(alpha):
    """galerkin's current-driven thermistor (tests/galerkin/test_temperature_joule_newton.py) as a
    rectangle document: rho(T) = 1 + alpha (T - 300), J = 1 A/m^2 leaving through the right side."""
    raw = example()
    raw["geometry"]["domain"].update(xmax=1.0, ymax=0.25)
    raw["mesh"]["subdivision_count"] = [16, 4]
    p = raw["physics"]["electric"]
    p["prescribed_electric_potential"] = {"left": "0 V"}
    p["inward_current_density"] = {"right": "-1 A/m^2"}
    p["electrical_conductivity"].update(reference_conductivity="1 S/m",
                                        resistivity_temperature_coefficient=f"{alpha!r} 1/K",
                                        valid={"temperature": ["300 K", "400 K"]})
    p["iteration"] = {"temperature_tolerance": "1e-8 K"}
    return raw


def test_the_methods_are_galerkins():
    from simcase.electric_joule import ITERATION_METHODS
    assert ITERATION_METHODS == METHODS


def test_n1_newton_agrees_with_picard_on_the_shipped_example():
    picard = run(Document.from_dict(example()), verbose=False)
    solved = run(Document.from_dict(newton(example())), verbose=False)
    assert_agree_with_picard(solved, example())
    assert len(solved.summary()["iterations"]) < len(picard.summary()["iterations"])


def test_n2_newton_agrees_with_picard_on_the_region_strip():
    picard = run(Document.from_dict(strip()), verbose=False)
    solved = run(Document.from_dict(newton(strip())), verbose=False)
    assert_agree_with_picard(solved, strip())
    assert len(solved.summary()["iterations"]) < len(picard.summary()["iterations"])


def test_n3_newton_converges_where_the_default_picard_does_not():
    raw = thermistor(7.0)
    with pytest.raises(JouleConvergenceError, match="maximum iterations exceeded"):
        run(Document.from_dict(raw), verbose=False)
    solved = run(Document.from_dict(newton(raw)), verbose=False)
    assert len(solved.summary()["iterations"]) <= 6
    plain = copy.deepcopy(raw)
    plain["physics"]["electric"]["iteration"].update(relaxation_factor=1.0, iteration_limit=500)
    # Deviation from the pre-registration (recorded there): against this reference as given the
    # conductivity differed by 2.56e-10 relative, above 1e-10. Picard contracts here by
    # q = 0.70 a step, so its own remaining error is q / (1 - q) times its last step, 1.8e-10;
    # Newton's last step was 4.4e-13. The threshold stays; the conductivity is compared with
    # the tight reference (3.1e-11), as in every agreement check here.
    assert_agree_with_picard(solved, plain)


def test_n3_newton_takes_fewer_iterations_on_a_mildly_nonlinear_rectangle():
    raw = thermistor(0.5)
    picard = run(Document.from_dict(raw), verbose=False)
    solved = run(Document.from_dict(newton(raw)), verbose=False)
    assert len(solved.summary()["iterations"]) <= 5 < len(picard.summary()["iterations"])
    assert_agree_with_picard(solved, raw)


def test_n4_the_series_strip_converges_to_the_closed_form_with_newton():
    errors, current = [], []
    for size in (0.25, 0.125, 0.0625):
        result = run(Document.from_dict(newton(strip(size=size))), verbose=False)
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


def test_n5_the_region_adapter_equals_a_direct_newton_call_bit_for_bit():
    raw = newton(strip())
    mesh, direct = _direct(raw, method="newton")
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


def test_n5_the_rectangle_adapter_equals_a_direct_newton_call():
    from galerkin import rectangle_mesh
    from galerkin.temperature_joule_heating import ConductivityModel, solve_temperature_joule_heat
    result = run(Document.from_dict(newton(example())), verbose=False)
    mesh = rectangle_mesh(1., .2, 24, 6)
    bc = {int(n): v for tag, v in {'left': 1., 'right': 0.}.items() for n in mesh.boundary[tag]}
    direct = solve_temperature_joule_heat(
        mesh, electrical_conductivity=ConductivityModel(lambda t: 2/(1+.01*(t-300)), (290, 400)),
        thermal_conductivity=1., prescribed_electric_potential=bc,
        prescribed_temperature={int(n): 300. for side in ('left', 'right') for n in mesh.boundary[side]},
        initial_temperature=300., temperature_tolerance=1e-8, method='newton')
    fields = result.fields
    assert len(result.summary()["iterations"]) == len(direct.history)
    for key, value in (("temperature", direct.coupled.thermal.temperature),
                       ("evaluation_temperature", direct.evaluation_temperature),
                       ("joule_power_density", direct.coupled.electrical.joule_power_density)):
        np.testing.assert_allclose(fields[key], value, rtol=1e-12, err_msg=key)
    np.testing.assert_allclose(fields["electric_potential"], direct.coupled.electrical.electric_potential,
                               rtol=0, atol=1e-12)
    np.testing.assert_allclose([r["temperature_change"]["value"] for r in result.summary()["iterations"]][:-1],
                               [r.temperature_change for r in direct.history][:-1], rtol=1e-6)


def _set(path, value):
    def change(raw):
        node = raw
        *head, last = path.split(".")
        for key in head:
            node = node[key]
        node[last] = value
    return change


def _relaxed_newton(raw):
    next(iter(raw["physics"].values()))["iteration"].update(method="newton", relaxation_factor=0.5)


REFUSALS = [(f"method {value!r}", _set("physics.j.iteration.method", value), "E-VALUE-FORM", "physics.j.iteration.method")
            for value in ("secant", "Newton", 1, None)] + [
    ("relaxation with newton", _relaxed_newton, "E-CONTRACT", "physics.j.iteration.relaxation_factor"),
    ("method outside iteration", _set("physics.j.method", "newton"), "E-KEY-UNKNOWN", "physics.j.method"),
]


@pytest.mark.parametrize("form", ["regions", "rectangle"])
@pytest.mark.parametrize("change, code, path", [r[1:] for r in REFUSALS], ids=[r[0] for r in REFUSALS])
def test_n7_refusals_name_what_is_wrong(form, change, code, path):
    raw = strip()
    if form == "rectangle":
        raw = example()
        raw["physics"] = {"j": raw["physics"]["electric"]}
    change(raw)
    with pytest.raises(DocumentError) as error:
        Document.from_dict(raw)
    assert [(d.code, d.path) for d in error.value.diagnostics if d.severity == "error"] == [(code, path)]
    if code == "E-CONTRACT":
        assert 'relaxes Picard steps only; method "newton" takes no relaxation_factor' in str(error.value)


def test_n7_picard_keeps_an_authored_relaxation():
    raw = strip()
    raw["physics"]["j"]["iteration"].update(method="picard", relaxation_factor=0.7)
    Document.from_dict(raw)


@pytest.mark.parametrize("form", ["regions", "rectangle"])
def test_n8_the_summary_records_newton_and_the_saved_result_round_trips(tmp_path, form):
    raw = strip() if form == "regions" else example()
    picard = run(Document.from_dict(raw), verbose=False).summary()
    assert "iteration_method" not in picard
    result = run(Document.from_dict(newton(raw)), verbose=False)
    summary = result.summary()
    assert summary["iteration_method"] == "newton"
    keys = list(summary)
    assert keys.index("iteration_method") == keys.index("iterations") - 1
    assert [k for k in keys if k != "iteration_method"] == list(picard)
    out = result.save(tmp_path / form)
    saved = json.loads((out / "summary.json").read_text())
    assert saved["iteration_method"] == "newton"
    with np.load(out / "fields.npz", allow_pickle=False) as data:
        assert json.loads(str(data["metadata_json"])) == saved
    restored = run(Document.load(out / "model.json"), verbose=False)
    assert restored.summary()["iteration_method"] == "newton"
    for key, array in result.fields.items():
        np.testing.assert_array_equal(restored.fields[key], array)


@pytest.mark.parametrize("form", ["regions", "rectangle"])
def test_n6_a_written_picard_gives_the_result_of_no_method(form):
    raw = strip() if form == "regions" else example()
    written = copy.deepcopy(raw)
    next(iter(written["physics"].values()))["iteration"]["method"] = "picard"
    plain, given = (run(Document.from_dict(r), verbose=False) for r in (raw, written))
    for key, array in plain.fields.items():
        assert given.fields[key].tobytes() == array.tobytes(), key
    a, b = plain.summary(), given.summary()
    a.pop("timing"), b.pop("timing")
    from simcase.results_common import dumps_summary
    assert dumps_summary(a) == dumps_summary(b)


def test_n8_the_region_texts_name_the_method():
    doc = Document.from_dict(newton(strip()))
    assert "Newton iteration: temperature_tolerance 1e-9 K" in doc.summary()
    assert "Picard iteration: temperature_tolerance 1e-9 K" in Document.from_dict(strip()).summary()
    result = run(doc, verbose=False)
    log = "\n".join(result._log)
    assert f"converged in {len(result.summary()['iterations'])} Newton iterations" in log
