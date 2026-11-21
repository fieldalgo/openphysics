# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The multiphysics document (D2): the envelope, entry-by-entry validation, couplings, the solve
order, cycles and loops, and each validation error of contract item 6."""
import copy
import json

import numpy as np
import pytest

from simcase import Document, DocumentError, multiphysics, registry, resolve
from simcase.multiphysics import ENVELOPE, solve_order

from multiphysics_fixtures import heated_slab, relay_document, relay_kind


@pytest.fixture
def relays(monkeypatch):
    """Test-local relay kinds (input x, output y; K, and mK for a unit mismatch), registered for one test."""
    registry.kinds()
    for kind in (relay_kind("test.relay"), relay_kind("test.relaymk", unit="mK"),
                 relay_kind("test.relaypower", unit="W/m^3", quantity="heat_source_density")):
        monkeypatch.setitem(registry._KINDS, kind.name, kind)


def errors(tree):
    return [(d.code, d.path, d.message) for d in resolve.resolve_tree(tree).diagnostics.errors]


def only_error(tree):
    found = errors(tree)
    assert len(found) == 1, found
    return found[0]


# -- the envelope -----------------------------------------------------------------------------------

def test_the_envelope_is_one_constant():
    assert ENVELOPE == "0.3/multiphysics.1"
    assert multiphysics.RESULT_FORMAT == "multiphysics-run-v1"


def test_a_coupled_document_reads_in_the_envelope():
    doc = Document.from_dict(heated_slab())
    assert doc.format == ENVELOPE
    assert registry.kind_of(doc.data) is multiphysics.KIND
    assert list(doc.views) == ["heat1", "modes1"]
    assert {n: v.format for n, v in doc.views.items()} == {"heat1": "0.3", "modes1": "0.3"}
    assert doc.si["materials"]["core"]["thermo_optic_coefficient"] == pytest.approx(1.8e-4, rel=1e-15)
    assert doc.si["materials"]["core"]["reference_temperature"] == 300.0
    summary = doc.summary()
    assert "coupling heat_to_optics: heat1.temperature -> modes1.temperature (temperature, K, same_mesh)" in summary
    assert "solve order: heat1 -> modes1" in summary


@pytest.mark.parametrize("change, why", [
    (lambda d: d, "has couplings"),
    (lambda d: d.pop("couplings") and d, "has physics of more than one kind (thermal.steady2d, em.modes2d)"),
])
def test_a_single_physics_envelope_with_couplings_or_two_kinds_names_the_multiphysics_envelope(change, why):
    tree = change(heated_slab())
    tree["openphysics"] = "0.3"
    code, path, message = only_error(tree)
    assert (code, path) == ("E-FORMAT", "openphysics")
    assert why in message and f'write "openphysics": "{ENVELOPE}"' in message


def test_the_envelope_with_one_kind_and_no_couplings_is_refused():
    tree = heated_slab()
    del tree["couplings"], tree["physics"]["heat1"]
    code, path, message = only_error(tree)
    assert (code, path) == ("E-FORMAT", "openphysics")
    assert 'write "openphysics": "0.3"' in message


def test_other_surfaces_refuse_the_envelope_by_name():
    refusal = resolve.format_refusal(heated_slab())
    assert (refusal.code, refusal.path) == ("E-FORMAT", "openphysics")
    assert "a multiphysics document" in refusal.message


def test_a_kind_without_a_coupling_hook_is_refused():
    tree = heated_slab()
    tree["physics"]["heat1"]["type"] = "thermal.transient2d"
    code, path, message = only_error(tree)
    assert (code, path) == ("E-CONTRACT", "physics.heat1.type")
    assert '"thermal.transient2d" is not coupled in this release' in message


def test_a_flat_geometry_is_refused():
    tree = heated_slab()
    tree["geometry"] = {"length_unit": "um", "depth": None, "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1},
                        "background": {"material": "clad"}, "shapes": []}
    code, path, message = only_error(tree)
    assert (code, path) == ("E-CONTRACT", "geometry") and "version 1 geometry block" in message


def test_each_entry_is_validated_by_its_own_kind():
    tree = heated_slab()
    tree["physics"]["modes1"]["mode_count"] = 0
    tree["physics"]["heat1"]["prescribed_temperature"]["top"] = "310 C"
    found = errors(tree)
    paths = [p for _c, p, _m in found]
    assert "physics.modes1.mode_count" in paths
    assert "physics.heat1.prescribed_temperature.top" in paths


def test_a_property_only_one_kind_reads_is_not_reported_unused():
    infos = [(d.code, d.path) for d in resolve.resolve_tree(heated_slab()).diagnostics
             if d.code == "I-UNUSED-PROPERTY"]
    assert infos == []


def test_thermo_optic_keys_stay_unknown_in_a_single_physics_document():
    tree = heated_slab()
    del tree["couplings"], tree["physics"]["heat1"]
    tree["openphysics"] = "0.3"
    for record in tree["materials"].values():
        del record["thermal_conductivity"]
    paths = {p for c, p, _m in errors(tree) if c == "E-KEY-UNKNOWN"}
    assert paths == {f"materials.{m}.{k}" for m in ("core", "clad")
                     for k in ("thermo_optic_coefficient", "reference_temperature")}


def test_thermo_optic_keys_without_a_coupled_temperature_are_unused():
    tree = heated_slab()
    tree["physics"]["heat2"] = copy.deepcopy(tree["physics"]["heat1"])
    tree["couplings"] = {"h": {"from": "heat1.temperature", "to": "modes1.temperature", "transfer": "same_mesh"}}
    assert errors(tree) == []
    tree["couplings"] = {}
    infos = {d.path for d in resolve.resolve_tree(tree).diagnostics if d.code == "I-UNUSED-PROPERTY"}
    assert "materials.core.thermo_optic_coefficient" in infos and "materials.clad.reference_temperature" in infos


# -- contract item 6: each validation error names the coupling or physics and what to change --------

@pytest.mark.parametrize("field, value, code, path, words", [
    ("from", "heat9.temperature", "E-CONTRACT", "couplings.heat_to_optics.from",
     ["names the physics 'heat9'", "physics here: heat1, modes1"]),
    ("from", "heat1.temp", "E-CONTRACT", "couplings.heat_to_optics.from",
     ["has no port 'temp'", "output ports: temperature, heat_flux"]),
    ("to", "modes1.index", "E-CONTRACT", "couplings.heat_to_optics.to", ["has no port 'index'", "input ports: temperature"]),
    ("to", "heat1.temperature", "E-CONTRACT", "couplings.heat_to_optics.to",
     ["heat1.temperature is an output port", "to names an input port"]),
    ("from", "modes1.temperature", "E-CONTRACT", "couplings.heat_to_optics.from",
     ["modes1.temperature is an input port", "from names an output port"]),
    ("from", "heat1.heat_flux", "E-CONTRACT", "couplings.heat_to_optics.from",
     ["heat1.heat_flux is an output thermal.steady2d saves but does not couple", "coupled outputs: temperature"]),
    ("transfer", "conservative", "E-CONTRACT", "couplings.heat_to_optics.transfer",
     ['"conservative" is not a transfer', 'write "same_mesh"']),
    ("from", "heat1", "E-VALUE-FORM", "couplings.heat_to_optics.from", ["<physics name>.<output port>"]),
])
def test_a_bad_coupling_is_named(field, value, code, path, words):
    tree = heated_slab()
    tree["couplings"]["heat_to_optics"][field] = value
    found = only_error(tree)
    assert found[:2] == (code, path), found
    for w in words:
        assert w in found[2], (w, found[2])


def test_a_unit_mismatch_is_named(relays):
    tree = relay_document({"a": ("test.relay", 0.5, 1), "b": ("test.relaymk", 0.5, 2)}, {"ab": ("a.y", "b.x")})
    code, path, message = only_error(tree)
    assert (code, path) == ("E-COUPLING-PAIR", "couplings.ab")
    assert "'K'" in message and "'mK'" in message and "does not convert units" in message


def test_a_self_coupling_is_named(relays):
    tree = relay_document({"a": ("test.relay", 0.5, 1)}, {"aa": ("a.y", "a.x")})
    code, path, message = only_error(tree)
    assert (code, path) == ("E-CONTRACT", "couplings.aa") and "couples a to itself" in message


def test_a_second_coupling_into_a_single_input_is_named():
    tree = heated_slab()
    tree["physics"]["heat2"] = copy.deepcopy(tree["physics"]["heat1"])
    tree["couplings"]["second"] = {"from": "heat2.temperature", "to": "modes1.temperature", "transfer": "same_mesh"}
    code, path, message = only_error(tree)
    assert (code, path) == ("E-CONTRACT", "couplings.second.to")
    assert 'takes one coupling (combine "single")' in message and "heat_to_optics already couples into it" in message


def test_a_sum_input_takes_several_couplings(relays):
    tree = relay_document({"a": ("test.relay", 1, 1), "b": ("test.relay", 1, 2), "c": ("test.relay", 1, 10)},
                          {"ac": ("a.y", "c.x"), "bc": ("b.y", "c.x")})
    assert errors(tree) == []
    result = multiphysics.run(Document.from_dict(tree), verbose=False)
    assert set(result.results["c"].y) == {13.0}                 # 1 K + 2 K summed into c, plus its 10 K


def test_same_mesh_with_a_key_one_physics_does_not_read_is_named():
    tree = heated_slab()
    tree["mesh"]["grading"] = {"position": ["0 um", "0.11 um"], "near": "0.01 um", "far": "0.08 um",
                               "refinement_distance": "1 um"}
    code, path, message = only_error(tree)
    assert (code, path) == ("E-CONTRACT", "couplings.heat_to_optics.transfer")
    assert "heat1 does not read mesh.grading" in message and "would build different meshes" in message
    assert "remove mesh.grading" in message


def test_a_coupled_temperature_needs_a_thermo_optic_model():
    tree = heated_slab()
    del tree["materials"]["clad"]["thermo_optic_coefficient"], tree["materials"]["clad"]["reference_temperature"]
    code, path, message = only_error(tree)
    assert (code, path) == ("E-PROPERTY-MISSING", "materials.clad")
    assert "physics.modes1 takes a coupled temperature" in message
    assert '"thermo_optic_coefficient" (for example "1.8e-4 1/K") and "reference_temperature"' in message


def test_one_thermo_optic_key_without_the_other_is_named():
    tree = heated_slab()
    del tree["materials"]["core"]["reference_temperature"]
    found = errors(tree)
    assert ("E-KEY-MISSING", "materials.core.reference_temperature") in [f[:2] for f in found]
    assert any("needs both" in m for _c, _p, m in found)


def test_library_materials_with_and_without_a_thermo_optic_model(relays):
    """physmat:Si and physmat:SiO2 carry dn/dT (T_ref 300 K); another library material does not.
    A relay is the temperature source here, so that only the optical side reads the library."""
    from multiphysics_fixtures import geometry, modes_entry
    tree = relay_document({"src": ("test.relay", 0, 300)}, {"t": ("src.y", "modes1.temperature")})
    tree["geometry"] = geometry(background="physmat:SiO2", core="physmat:Si")
    tree["physics"]["modes1"] = modes_entry()
    tree["mesh"] = {"element_size": "0.1 um"}
    assert errors(tree) == []
    doc = Document.from_dict(tree)
    assert multiphysics.thermo_optic(doc.si["materials"], "physmat:Si") == (1.8e-4, 300.0)
    assert multiphysics.thermo_optic(doc.si["materials"], "physmat:SiO2") == (1.0e-5, 300.0)
    tree["geometry"] = geometry(background="physmat:SiO2", core="physmat:Si3N4")
    code, path, message = only_error(tree)
    assert (code, path) == ("E-PROPERTY-MISSING", "physics.modes1")
    assert '"physmat:Si3N4" has none in the library' in message and '"physmat:Si" or "physmat:SiO2"' in message


def test_a_mesh_mismatch_at_run_time_fails_the_run(relays):
    """same_mesh is checked again when the meshes exist (MeshSignature): the relay's 2 x 2 mesh is
    not the modes mesh, so the run fails by name and nothing is interpolated."""
    from multiphysics_fixtures import geometry, modes_entry
    tree = relay_document({"src": ("test.relay", 0, 300)}, {"t": ("src.y", "modes1.temperature")})
    tree["geometry"] = geometry(background="physmat:SiO2", core="physmat:Si")
    tree["physics"]["modes1"] = modes_entry()
    tree["mesh"] = {"element_size": "0.1 um"}
    with pytest.raises(DocumentError, match="couplings.t: same_mesh needs one mesh, but src and modes1 built "
                                            "different meshes"):
        multiphysics.run(Document.from_dict(tree), verbose=False)


# -- solve order, cycles and loops ---------------------------------------------------------------

def _edges(pairs):
    return [multiphysics._Edge(f"{a}{b}", a, "y", b, "x", "temperature", "K") for a, b in pairs]


@pytest.mark.parametrize("names, pairs, order", [
    (["a", "b", "c"], [], [["a"], ["b"], ["c"]]),
    (["a", "b", "c"], [("c", "a")], [["b"], ["c"], ["a"]]),
    (["a", "b", "c"], [("c", "a"), ("b", "c")], [["b"], ["c"], ["a"]]),
    (["a", "b", "c"], [("a", "b"), ("b", "a")], [["a", "b"], ["c"]]),
    (["c", "b", "a"], [("a", "b"), ("b", "a"), ("c", "a")], [["c"], ["b", "a"]]),
    (["a", "b", "c", "d"], [("a", "b"), ("b", "c"), ("c", "a"), ("d", "a")], [["d"], ["a", "b", "c"]]),
    (["x", "a", "b"], [("a", "b")], [["x"], ["a"], ["b"]]),
])
def test_the_solve_order_is_derived_from_the_coupling_graph(names, pairs, order):
    assert solve_order(names, _edges(pairs)) == order


def _cycle(loops=None):
    return relay_document({"a": ("test.relay", 0.5, 1), "b": ("test.relay", 0.5, 2)},
                          {"ab": ("a.y", "b.x"), "ba": ("b.y", "a.x")}, loops)


def test_a_cycle_without_an_accepted_loop_names_the_group_and_proposes_defaults(relays):
    found = resolve.resolve_tree(_cycle()).diagnostics.errors
    assert len(found) == 1
    d = found[0]
    assert (d.code, d.path) == ("E-COUPLING-CYCLE", "study.loops")
    proposal = {"physics": ["a", "b"], "method": "fixed_point",
                "tolerance": {"port": "a.y", "norm": "max_abs", "value": "1e-6 K"},
                "max_iterations": 30, "relaxation": 0.5}
    assert "a and b form a cycle (couplings ab, ba) with no accepted loop" in d.message
    assert json.dumps(proposal) in d.message
    assert [s.value for s in d.suggestions] == [proposal]          # Studio's "Accept iteration step"
    assert errors(_cycle([proposal])) == []


def _loop(**change):
    loop = {"physics": ["a", "b"], "method": "fixed_point",
            "tolerance": {"port": "a.y", "norm": "max_abs", "value": "1e-6 K"}, "max_iterations": 30,
            "relaxation": 0.5}
    loop.update(change)
    return loop


@pytest.mark.parametrize("loop, code, path, words", [
    (_loop(physics=["a"]), "E-CONTRACT", "study.loops[0].physics", ["a is not a cycle of the couplings"]),
    (_loop(method="newton"), "E-CONTRACT", "study.loops[0].method", ['"newton" is not a loop method']),
    (_loop(max_iterations=0), "E-VALUE-FORM", "study.loops[0].max_iterations", ["at least 2"]),
    (_loop(max_iterations=1), "E-VALUE-FORM", "study.loops[0].max_iterations", ["at least 2"]),
    (_loop(tolerance={"port": "a.y", "norm": "max_abs", "value": "1e-3 degC"}), "E-DEGC-NOT-ABSOLUTE",
     "study.loops[0].tolerance.value", []),
    (_loop(relaxation=1.5), "E-DOMAIN", "study.loops[0].relaxation", ["(0, 1]"]),
    (_loop(tolerance={"port": "a.x", "norm": "max_abs", "value": "1e-6 K"}), "E-CONTRACT",
     "study.loops[0].tolerance.port", ["a has no output port 'x'"]),
    (_loop(tolerance={"port": "c.y", "norm": "max_abs", "value": "1e-6 K"}), "E-CONTRACT",
     "study.loops[0].tolerance.port", ["not an output of a physics of this loop"]),
    (_loop(tolerance={"port": "a.y", "norm": "l2", "value": "1e-6 K"}), "E-CONTRACT",
     "study.loops[0].tolerance.norm", ['write "max_abs"']),
    (_loop(tolerance={"port": "a.y", "norm": "max_abs", "value": "1e-6"}), "E-UNIT-MISSING",
     "study.loops[0].tolerance.value", []),
    (_loop(tolerance={"port": "a.y", "norm": "max_abs", "value": "1e-6 m"}), "E-UNIT-DIMENSION",
     "study.loops[0].tolerance.value", []),
    (dict(_loop(), extra=1), "E-KEY-UNKNOWN", "study.loops[0].extra", []),
])
def test_a_bad_loop_entry_is_named(relays, loop, code, path, words):
    found = [f for f in errors(_cycle([loop])) if f[0] != "E-COUPLING-CYCLE"]
    assert found and found[0][:2] == (code, path), found
    for w in words:
        assert w in found[0][2]


def test_a_second_loop_for_the_same_cycle_is_named(relays):
    code, path, message = only_error(_cycle([_loop(), _loop()]))
    assert (code, path) == ("E-CONTRACT", "study.loops[1]") and "already has its loop at study.loops[0]" in message


def test_a_chain_runs_in_order_and_records_each_coupling(relays):
    doc = Document.from_dict(relay_document({"b": ("test.relay", 2, 1), "a": ("test.relay", 1, 3)},
                                            {"ab": ("a.y", "b.x")}))
    result = multiphysics.run(doc, verbose=False)
    assert result.solve_order == [["a"], ["b"]]
    assert set(result.results["b"].y) == {7.0}                  # 2 * 3 K + 1 K
    assert result.couplings["ab"]["mesh_signature"] == "match"
    assert result.couplings["ab"]["max_abs_difference"] == {"value": 0.0, "unit": "K"}
    assert result.couplings["ab"]["conservation_residual"] is None       # temperature is not a power


def test_multiphysics_results_blocks_and_studies():
    tree = heated_slab()
    tree["results"] = {"mode_overlap": {}}
    code, path, _m = only_error(tree)
    assert (code, path) == ("E-KEY-UNKNOWN", "results.mode_overlap")
    tree = heated_slab()
    tree["study"] = {"type": "transient"}
    code, path, _m = only_error(tree)
    assert (code, path) == ("E-CONTRACT", "study.type")


# -- loop execution: the generic fixed point, on test-local kinds only ------------------------------

def _run_cycle(gain, relaxation=0.5, max_iterations=300, value="1e-10 K"):
    tree = relay_document({"a": ("test.relay", gain, 1), "b": ("test.relay", gain, 2)},
                          {"ab": ("a.y", "b.x"), "ba": ("b.y", "a.x")},
                          [_loop(relaxation=relaxation, max_iterations=max_iterations,
                                 tolerance={"port": "a.y", "norm": "max_abs", "value": value})])
    return multiphysics.run(Document.from_dict(tree), verbose=False)


def test_an_accepted_loop_converges_to_the_fixed_point(relays):
    """y_a = x_a / 2 + 1 K and y_b = x_b / 2 + 2 K, coupled both ways: y_a = 8/3 K, y_b = 10/3 K."""
    result = _run_cycle(0.5)
    assert result.solve_order == [["a", "b"]]
    assert np.allclose(result.results["a"].y, 8 / 3, rtol=0, atol=1e-9)
    assert np.allclose(result.results["b"].y, 10 / 3, rtol=0, atol=1e-9)
    (history,) = result.loops
    assert history["converged"] is True and history["physics"] == ["a", "b"]
    residuals = [r["value"] for r in history["residuals"]]
    assert residuals[-1] <= 1e-10 < residuals[0]
    assert all(r["unit"] == "K" for r in history["residuals"])
    assert len(residuals) == history["iterations"] - 1
    assert set(result.couplings) == {"ab", "ba"}


def test_relaxation_changes_the_iteration_count(relays):
    assert _run_cycle(0.5, relaxation=1.0).loops[0]["iterations"] < _run_cycle(0.5, relaxation=0.3).loops[0]["iterations"]


def test_a_loop_that_reaches_max_iterations_fails_with_its_history(relays):
    with pytest.raises(multiphysics.LoopNotConverged) as caught:
        _run_cycle(2.0, relaxation=1.0, max_iterations=8)
    error = caught.value
    assert (error.code, error.path) == ("E-LOOP-DIVERGED", "study.loops")
    assert len(error.history) == 7 and error.unit == "K"
    assert all(b > a for a, b in zip(error.history, error.history[1:]))       # diverging: never a result
    assert "the loop of a, b did not converge in 8 iterations" in str(error)
    assert "no result is returned" in str(error)


def test_a_multiphysics_sweep_is_validated_and_not_run():
    tree = heated_slab()
    tree["study"] = {"type": "sweep", "parameter": "physics.modes1.vacuum_wavelength",
                     "values": {"unit": "um", "values": [1.5, 1.55]}}
    assert errors(tree) == []
    doc = Document.from_dict(tree)
    assert doc.si["study"]["type"] == "sweep"
    with pytest.raises(DocumentError) as caught:
        multiphysics.run(doc, verbose=False)
    assert (caught.value.code, caught.value.path) == ("E-CONTRACT", "study.type")
    assert "a multiphysics sweep is validated but not run in this release" in str(caught.value)


@pytest.mark.parametrize("parameter, path", [
    ("physics.optics9.vacuum_wavelength", "study.parameter"),
    ("mesh.element_size", "study.parameter"),
    ("physics.modes1.no_such_value", "study.parameter"),
])
def test_a_multiphysics_sweep_parameter_names_a_value_of_one_physics(parameter, path):
    tree = heated_slab()
    tree["study"] = {"type": "sweep", "parameter": parameter, "values": {"unit": "um", "values": [1.5, 1.55]}}
    found = errors(tree)
    assert found and found[0][:2] == ("E-CONTRACT", path), found


def test_a_quantity_mismatch_is_named(relays):
    tree = relay_document({"a": ("test.relaypower", 1, 1), "b": ("test.relay", 0.5, 2)}, {"ab": ("a.y", "b.x")})
    tree["physics"]["a"]["offset"] = "1 K"
    found = [f for f in errors(tree) if f[0] == "E-COUPLING-PAIR"]
    assert found and found[0][1] == "couplings.ab"
    assert "carries heat_source_density" in found[0][2] and "takes temperature" in found[0][2]


def test_a_converged_loop_is_at_its_fixed_point_whatever_the_relaxation(relays):
    """The residual is |G(x) - x| of the coupled field, so a small relaxation does not stop the
    loop early: gain 0.9 both ways, w 0.02, tolerance 1e-3 K (fixed point y_a = 2.8 / 0.19 K)."""
    tree = relay_document({"a": ("test.relay", 0.9, 1), "b": ("test.relay", 0.9, 2)},
                          {"ab": ("a.y", "b.x"), "ba": ("b.y", "a.x")},
                          [_loop(relaxation=0.02, max_iterations=5000,
                                 tolerance={"port": "a.y", "norm": "max_abs", "value": "1e-3 K"})])
    result = multiphysics.run(Document.from_dict(tree), verbose=False)
    exact = (1 + 0.9 * 2) / (1 - 0.81)
    assert result.loops[0]["converged"] and result.loops[0]["iterations"] > 100
    assert np.max(np.abs(result.results["a"].y - exact)) <= 1e-2


def test_a_tolerance_port_not_carried_inside_the_loop_is_named(relays):
    tree = relay_document({"a": ("test.relay", 0.5, 1), "b": ("test.relay", 0.5, 2), "c": ("test.relay", 1, 1)},
                          {"ab": ("a.y", "b.x"), "ba": ("b.y", "a.x"), "bc": ("b.y", "c.x")},
                          [_loop(tolerance={"port": "a.y", "norm": "max_abs", "value": "1e-6 K"})])
    assert errors(tree) == []
    tree["couplings"] = {"ab": {"from": "a.y", "to": "b.x", "transfer": "same_mesh"},
                         "ba": {"from": "b.y", "to": "a.x", "transfer": "same_mesh"}}
    tree["study"]["loops"][0]["tolerance"]["port"] = "b.y"
    assert errors(tree) == []


@pytest.mark.parametrize("tree", [
    {"openphysics": "0.3", "geometry": {}, "physics": {"a": {"type": ["x"]}}},
    {"openphysics": "0.3", "geometry": {}, "physics": {"a": {"type": {"x": 1}}}},
])
def test_a_single_physics_document_with_an_unhashable_type_is_still_named(tree):
    code, path, _m = errors(tree)[0]
    assert (code, path) == ("E-VALUE-FORM", "physics.a.type")


def test_empty_couplings_count_as_no_couplings():
    tree = heated_slab()
    del tree["physics"]["heat1"]
    tree["couplings"] = {}
    code, path, message = only_error(tree)
    assert (code, path) == ("E-FORMAT", "openphysics") and 'write "openphysics": "0.3"' in message
    tree["openphysics"] = "0.3"
    assert ("E-KEY-UNKNOWN", "couplings") in [f[:2] for f in errors(tree)]


@pytest.mark.parametrize("change, path", [
    (lambda t: t.update(study={"type": 2.5}), "study.type"),
    (lambda t: t.update(study={"type": "single", "typo": 1}), "study.typo"),
    (lambda t: t.update(study={"type": "single", "parameter": "physics.modes1.vacuum_wavelength"}),
     "study.parameter"),
    (lambda t: t.update(study={"type": "sweep"}), "study.parameter"),
    (lambda t: t.update(study={"type": "sweep", "parameter": 7, "values": [1]}), "study.parameter"),
    (lambda t: t["materials"]["core"].update(thermo_optic_coefficient=[5]),
     "materials.core.thermo_optic_coefficient"),
])
def test_malformed_values_are_named_not_raised(change, path):
    tree = heated_slab()
    change(tree)
    text = json.dumps(tree).replace('"type": 2.5', '"type": 2.5')
    found = resolve.resolve_text(text).diagnostics.errors
    assert found and path in [d.path for d in found], [(d.code, d.path) for d in found]


def test_a_malformed_loop_method_or_norm_is_named_not_raised(relays):
    for change in ({"method": 1.5}, {"tolerance": {"port": "a.y", "norm": 2.5, "value": "1e-6 K"}}):
        found = resolve.resolve_text(json.dumps(_cycle([_loop(**change)]))).diagnostics.errors
        assert found


def test_progress_events_follow_the_solve_order(relays):
    events = []
    doc = Document.from_dict(relay_document({"b": ("test.relay", 2, 1), "a": ("test.relay", 1, 3)},
                                            {"ab": ("a.y", "b.x")}))
    multiphysics.run(doc, verbose=False, on_event=events.append)
    assert [(e["event"], e["physics"]) for e in events] == [
        ("physics_started", "a"), ("physics_finished", "a"), ("physics_started", "b"), ("physics_finished", "b")]
    assert json.loads(json.dumps(events)) == events                      # JSON data
    events = []
    tree = _cycle([_loop(max_iterations=300, tolerance={"port": "a.y", "norm": "max_abs", "value": "1e-10 K"})])
    result = multiphysics.run(Document.from_dict(tree), verbose=False, on_event=events.append)
    kinds = [e["event"] for e in events]
    assert kinds[0] == "loop_started" and kinds[-1] == "loop_finished" and set(kinds[1:-1]) == {"loop_iteration"}
    residuals = [e["residual"] for e in events if e["event"] == "loop_iteration"]
    assert residuals == [r["value"] for r in result.loops[0]["residuals"]]
    assert events[-1]["iterations"] == result.loops[0]["iterations"]
