# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""``results.group_index``: the group index of a single study by a wavelength central difference.

Pre-registered before the implementation (docs/packages/simcase/group_index.md):

V8 (not blind: the reference and today's three-point sweep on this mesh family were measured
before registration, errors 3.7e-3, 8.9e-4, 2.3e-4). A 220 nm physmat:Si film spanning the
PEC window in physmat:SiO2, lambda0 1.55 um, step 10 nm; the reference is the central
difference of refsol.slab TE n_eff at 1.54, 1.55 and 1.56 um with physmat's indices. Every
element size scales with h (film h, background 5h, grading h to 5h; the grading distance is
a fixed 1 um). Error <= 3e-3 at h = 0.006 um and strictly decreasing over h = 0.024, 0.012,
0.006 um.

V9: the option equals the middle point of today's sweep over lambda0 -+ step to 1e-12
relative: a tracked vector sweep, and an untracked scalar sweep whose mode count is the
option's search_mode_count (so the side solves are the same solves). Changed after the first
result: the registered scalar fixture kept the vector fixture's pec side walls, on which the
scalar field of the 0.1 um window is cut off (n_eff = 0 at every point; the sweep returned
n_g = 0, the option null with a near-degenerate reason). The scalar case now has pmc side
walls, as SLAB_TE_CHECK; the vector case and the bound are unchanged.

V10 (blind): a round fibre with the Sellmeier core of refsol's fibre tests and cladding 0.9
times the core, a = 1.3 um; TE01 within 2e-3 relative of refsol.fiber's implicit
dispersive group index at h = 0.04 um, strictly decreasing over h = 0.16, 0.08, 0.04 um
(core h, background 4h); the HE11 pair null with a reason or within the same bound.

M5-f: format refusals, unchanged results without the option, null with a reason.
"""

import copy
import json

import numpy as np
import pytest

import physmat
from refsol import fiber, slab
from simcase import Document, DocumentError, examples, run
from simcase.cli import main
import simcase.group_index as group_index_module
import simcase.runner as runner


def um(x):
    return f"{x!r} um"


def si_slab(h=0.012, formulation="vector", study=None, group_index=None, mode_count=1):
    d = copy.deepcopy(examples.VECTOR_SLAB)
    d["geometry"]["background"]["material"] = "physmat:SiO2"
    d["geometry"]["shapes"][0]["material"] = "physmat:Si"
    d.pop("materials")
    d["geometry"]["shapes"][0]["element_size"] = um(h)
    d["mesh"]["element_size"] = um(5 * h)
    d["mesh"]["grading"].update(near=um(h), far=um(5 * h))
    d["physics"]["em1"].update(formulation=formulation, mode_count=mode_count)
    if formulation == "scalar":
        # the scalar field vanishes on pec walls; pmc side walls keep the film a slab (SLAB_TE_CHECK)
        del d["physics"]["em1"]["effective_index_threshold"]
        d["physics"]["em1"]["boundary"].update(left="pmc", right="pmc")
    if study is not None:
        d["study"] = study
    d["results"] = {} if group_index is None else {"group_index": group_index}
    return d


def wavelength_sweep(values):
    return {"type": "sweep", "parameter": "physics.em1.vacuum_wavelength", "values": {"unit": "um", "values": values}}


def _index(name, wavelength):
    return float(physmat.material(name).refractive_index(vacuum_wavelength=wavelength * 1e-6).real)


def slab_reference(step=0.01, wavelength=1.55):
    def neff(wl):
        nc, nf = _index("SiO2", wl), _index("Si", wl)
        return slab.modes(refractive_index=(nc, nf, nc), thickness=0.22, vacuum_wavelength=wl, pol="TE")[0]
    return neff(wavelength) - wavelength * (neff(wavelength + step) - neff(wavelength - step)) / (2 * step)


def test_slab_reference_value():
    assert slab_reference() == pytest.approx(3.70670, abs=5e-6)


# -- V8 ---------------------------------------------------------------------------------------------

def _v8_error(h):
    result = run(Document.from_dict(si_slab(h, group_index={"wavelength_step": "10 nm"})), False)
    return abs(result.group_index()[0, 0] - slab_reference())


def test_v8_slab_group_index_meets_the_budget_on_the_finest_mesh():
    assert _v8_error(0.006) <= 3e-3


@pytest.mark.slow
def test_v8_slab_group_index_error_decreases_with_the_scaled_mesh():
    errors = [_v8_error(h) for h in (0.024, 0.012, 0.006)]
    assert errors[0] > errors[1] > errors[2]
    assert errors[2] <= 3e-3


# -- V9 ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("step", [0.001, 0.01])
def test_v9_vector_option_equals_the_tracked_sweep(step):
    option = run(Document.from_dict(si_slab(group_index={"wavelength_step": f"{step * 1e3:g} nm"})), False)
    sweep = run(Document.from_dict(si_slab(study=wavelength_sweep([1.55 - step, 1.55, 1.55 + step]))), False)
    assert sweep.mode_tracking["method"] == option.summary()["group_index_method"]["tracking"]
    np.testing.assert_allclose(option.group_index()[0], sweep.group_index()[1], rtol=1e-12, atol=0)


def test_v9_scalar_option_equals_the_sweep_with_the_same_solves():
    option = run(Document.from_dict(si_slab(formulation="scalar", group_index={})), False)
    # mode_count 1 searches max(2, 5) = 5 candidates at each side wavelength
    sweep = run(Document.from_dict(si_slab(formulation="scalar", mode_count=5,
                                           study=wavelength_sweep([1.549, 1.55, 1.551]))), False)
    assert option.summary()["group_index_method"]["tracking"] == "scalar-l2-assignment-v1"
    np.testing.assert_allclose(option.group_index()[0, 0], sweep.group_index()[1, 0], rtol=1e-12, atol=0)


# -- V10 --------------------------------------------------------------------------------------------

RADIUS = 1.3


def _sellmeier(wl, scale=1.0):
    """Core 1 + 1.1 l^2/(l^2 - 0.01) as in refsol's fibre tests; the cladding is 0.9 times it."""
    n = scale * np.sqrt(1 + 1.1 * wl ** 2 / (wl ** 2 - 0.01))
    dn = -scale * 1.1 * 0.01 * wl / (np.sqrt(1 + 1.1 * wl ** 2 / (wl ** 2 - 0.01)) * (wl ** 2 - 0.01) ** 2)
    return n, dn


def _fibre(h):
    half = 5 * RADIUS
    material = {"core": 1.0, "clad": 0.9}
    return {
        "openphysics": "0.3",
        "name": "dispersive round fibre, TE01 group index",
        "geometry": {"length_unit": "um", "depth": None,
                     "domain": {"xmin": -half, "xmax": half, "ymin": -half, "ymax": half},
                     "background": {"material": "clad"},
                     "shapes": [{"name": "core", "type": "circle", "cx": 0.0, "cy": 0.0, "r": RADIUS,
                                 "material": "core", "element_size": um(h)}]},
        "materials": {name: {"refractive_index": {
            "model": "sellmeier", "constant": s ** 2,
            "terms": [{"strength": 1.1 * s ** 2, "resonance_wavelength_squared": "0.01 um^2"}],
            "reference_medium": "vacuum"}} for name, s in material.items()},
        "physics": {"em1": {"type": "em.modes2d", "formulation": "vector", "vacuum_wavelength": "1.55 um",
                            "mode_count": 3, "effective_index_threshold": 1.31,
                            "boundary": {"left": "pec", "right": "pec", "top": "pec", "bottom": "pec"}}},
        "mesh": {"element_size": um(4 * h)},
        "study": {"type": "single"},
        "results": {"group_index": {}},
    }


def _fibre_exact(label):
    (n1, dn1), (n2, dn2) = _sellmeier(1.55), _sellmeier(1.55, 0.9)
    # the dispersive form is private (rule R(2): the index derivative has no registry name, only tests pass it)
    return fiber._vector_group_index(RADIUS, n1, n2, 1.55, label, dn1, dn2)


def _v10(h):
    result = run(Document.from_dict(_fibre(h)), False)
    method = result.summary()["group_index_method"]
    exact_te, exact_he = _fibre_exact("TE01")[1], _fibre_exact("HE11")[1]
    ng = result.group_index()[0]
    assert method["reasons"][2] is None, method["reasons"]
    for mode in (0, 1):
        assert (np.isnan(ng[mode]) and method["reasons"][mode]) or abs(ng[mode] / exact_he - 1) <= 2e-3
    return abs(ng[2] / exact_te - 1)


@pytest.mark.slow
def test_v10_fibre_te01_group_index_converges_to_the_exact_dispersive_value():
    errors = [_v10(h) for h in (0.16, 0.08, 0.04)]
    assert errors[0] > errors[1] > errors[2]
    assert errors[2] <= 2e-3


def test_v10_fixture_mode_order():
    labels = [m.label for m in fiber._vector_modes(RADIUS, _sellmeier(1.55)[0], _sellmeier(1.55, 0.9)[0], 1.55,
                                                    l_max=3)]
    assert labels[:2] == ["HE11", "TE01"]


# -- M5-f -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("study", [wavelength_sweep([1.54, 1.55, 1.56]),
                                   {"type": "sweep", "parameter": "physics.em1.mode_count", "values": [1, 2]}])
def test_the_option_is_refused_for_sweeps(study):
    d = si_slab(formulation="scalar", study=study, group_index={})
    with pytest.raises(DocumentError, match="results.group_index: read by a single study only") as info:
        Document.from_dict(d).validate()
    assert info.value.path == "results.group_index"


@pytest.mark.parametrize("key", ["pml", "bend"])
def test_the_option_is_refused_with_open_boundaries(key):
    d = copy.deepcopy(examples.VECTOR_SLAB)
    p = d["physics"]["em1"]
    p.update(target_effective_index=2.8, pml={"pml_thickness": {"top": "0.5 um"}})
    if key == "bend":
        p["bend"] = {"bend_radius": "10 um", "bend_origin": "0 um"}
    d["results"] = {"group_index": {}}
    with pytest.raises(DocumentError, match=f"results.group_index: not read with physics.em1.{key}"):
        Document.from_dict(d).validate()


@pytest.mark.parametrize("step, ok", [("1 pm", True), ("0.999 pm", False), ("77.5 nm", True), ("77.6 nm", False),
                                      ("0.0775 um", True), ("0 nm", False), ("-1 nm", False)])
def test_wavelength_step_range(step, ok):
    d = si_slab(group_index={"wavelength_step": step})
    if ok:
        Document.from_dict(d).validate()
    else:
        with pytest.raises(DocumentError) as info:
            Document.from_dict(d).validate()
        assert info.value.path == "results.group_index.wavelength_step"


def test_wavelength_step_default_is_recorded():
    doc = Document.from_dict(si_slab(group_index={}))
    doc.validate()
    assert {"path": "results.group_index.wavelength_step", "value": "1 nm",
            "reason": "length default: a 1 nm central-difference step"} in doc.defaults_applied


@pytest.mark.parametrize("group_index, where", [({"step": "1 nm"}, "results.group_index.step"),
                                                ({"wavelength_step": "1 nm", "order": 2}, "results.group_index.order")])
def test_unknown_keys_are_refused_by_name(group_index, where):
    with pytest.raises(DocumentError) as info:
        Document.from_dict(si_slab(group_index=group_index))
    assert ("E-KEY-UNKNOWN", where) in [(d.code, d.path) for d in info.value.diagnostics]


def test_a_coupled_document_refuses_the_option():
    from multiphysics_fixtures import heated_slab
    d = heated_slab()
    d["results"] = {"group_index": {}}
    with pytest.raises(DocumentError) as info:
        Document.from_dict(d)
    assert ("E-KEY-UNKNOWN", "results.group_index") in [(x.code, x.path) for x in info.value.diagnostics]


def test_lossy_materials_are_refused_at_run_time():
    d = si_slab(formulation="scalar", group_index={})
    d["geometry"]["shapes"][0]["material"] = "film"
    d["materials"] = {"film": {"refractive_index": {"n": 3.48, "k": 1e-4}}}
    with pytest.raises(DocumentError, match="results.group_index: the materials are lossy"):
        run(Document.from_dict(d), False)


def _without_timing(summary):
    out = copy.deepcopy(summary)
    out.pop("timing")
    return out


def test_results_without_the_option_are_unchanged():
    """The lambda0 solve is the run's own solve: the option adds group_index, its method block,
    its field-map entries and the default it applied, and changes nothing else."""
    off = run(Document.from_dict(si_slab()), False)
    on = run(Document.from_dict(si_slab(group_index={})), False)
    plain, extended = _without_timing(off.summary()), _without_timing(on.summary())
    assert "group_index" not in plain and "group_index_method" not in plain
    assert set(extended) - set(plain) == {"group_index", "group_index_method"}
    for key, value in plain.items():
        if key.startswith("field_") and isinstance(value, dict) and key != "field_layout":
            assert {k: v for k, v in extended[key].items() if k != "group_index"} == value, key
            assert "group_index" in extended[key] or key == "field_components", key
        elif key == "defaults_applied":
            assert [d for d in extended[key] if not d["path"].startswith("results.group_index")] == value
        else:
            assert extended[key] == value, key
    off_arrays, on_arrays = off.arrays(), on.arrays()
    assert "group_index" not in off_arrays and set(on_arrays) - set(off_arrays) == {"group_index"}
    for name, value in off_arrays.items():
        np.testing.assert_array_equal(on_arrays[name], value, strict=True)
    assert on_arrays["group_index"].shape == on_arrays["effective_index"].shape


def test_group_index_method_block():
    method = run(Document.from_dict(si_slab(group_index={"wavelength_step": "2 nm"})), False).summary()[
        "group_index_method"]
    assert method == {"method": "central_difference", "wavelength_step": {"value": 2e-9, "unit": "m"},
                      "tracking": "electric-l2-assignment-v1", "reasons": [None]}


def _fibre_degenerate():
    d = copy.deepcopy(examples.VECTOR_FIBER)
    d["physics"]["em1"]["mode_count"] = 1
    d["results"] = {"group_index": {}}
    return d


def test_an_unmatched_mode_is_null_with_a_reason_and_the_run_succeeds(tmp_path):
    """HE11 has a degenerate partner: the sweep path refuses the whole sweep
    (test_vector_sweep); here only its value is null."""
    model = tmp_path / "fibre.json"
    Document.from_dict(_fibre_degenerate()).save(model)
    output = tmp_path / "out"
    assert main(["run", str(model), "-q", "-o", str(output)]) == 0
    summary = json.loads((output / "summary.json").read_text())
    assert summary["group_index"]["values"] == [[None]]
    [reason] = summary["group_index_method"]["reasons"]
    assert "near-degenerate" in reason and "vacuum_wavelength 1.549 um" in reason, reason
    assert summary["effective_index"]["values"][0][0] > 1.44
    with np.load(output / "fields.npz", allow_pickle=False) as arrays:
        assert np.isnan(arrays["group_index"]).all()


def test_a_failed_side_solve_is_null_with_a_reason(monkeypatch):
    original = runner._kernel_solve

    def failing(model, physics):
        if physics["wavelength"] > 1.55:
            raise RuntimeError("factor is exactly singular")
        return original(model, physics)

    monkeypatch.setattr(runner, "_kernel_solve", failing)
    result = run(Document.from_dict(si_slab(group_index={})), False)
    assert np.isnan(result.group_index()).all()
    [reason] = result.summary()["group_index_method"]["reasons"]
    assert reason == "vacuum_wavelength 1.551 um: the solve failed (factor is exactly singular)"


def test_three_solves_at_the_exact_side_wavelengths(monkeypatch):
    seen = []
    original = runner._kernel_solve

    def recording(model, physics):
        seen.append((physics["wavelength"], physics["num_modes"]))
        return original(model, physics)

    monkeypatch.setattr(runner, "_kernel_solve", recording)
    run(Document.from_dict(si_slab(mode_count=2, group_index={"wavelength_step": "10 nm"})), False)
    assert seen == [(1.55, 2), (1.54, 6), (1.56, 6)]
    assert group_index_module.VECTOR_TRACKING == "electric-l2-assignment-v1"


# -- match_modes against ModeTracker.step on synthetic scalar fields (identity mass) --------------

def _tracker(requested, reference, search_modes=6):
    import scipy.sparse as sp
    from simcase.tracking import ModeTracker, tracking_settings
    tracker = object.__new__(ModeTracker)
    tracker.num_modes, tracker.scalar, tracker.seed_target = requested, True, None
    tracker.settings = tracking_settings(requested) | {"search_modes": search_modes}
    tracker.node_mass = sp.identity(reference.shape[0], format="csr")
    tracker.previous = reference
    return tracker


def _unit(*weights, size=8):
    v = np.zeros(size)
    v[:len(weights)] = weights
    return v


def _columns(*vectors):
    return np.stack(vectors, axis=1)


def _both(requested, reference, neff, field, search_modes=6):
    from simcase.tracking import ModeTrackingError, match_modes
    columns, reasons = match_modes(_tracker(requested, reference, search_modes), reference, neff, field, "here")
    try:
        _tracker(requested, reference, search_modes).step(neff, field, "here")
        raised = None
    except ModeTrackingError as exc:
        raised = str(exc)
    return list(columns), reasons, raised


def test_match_modes_agrees_with_step_on_a_clean_swap():
    reference = _columns(_unit(1), _unit(0, 1))
    field = _columns(_unit(0, 1), _unit(1), _unit(0, 0, 1))
    columns, reasons, raised = _both(2, reference, np.array([2.0, 1.9, 1.5]), field)
    assert columns == [1, 0] and reasons == [None, None] and raised is None


def test_match_modes_weak_overlap_is_per_mode():
    reference = _columns(_unit(1), _unit(0, 1))
    field = _columns(_unit(1), _unit(0, 0.6, 0.8), _unit(0, 0.8, -0.6, 0, 0, 0))
    columns, reasons, raised = _both(2, reference, np.array([2.0, 1.9, 1.5]), field)
    assert "weak overlap" in raised and "mode 2" in raised
    assert columns == [0, -1] and reasons[0] is None and "weak overlap 0.64" in reasons[1]


def test_match_modes_ambiguous_margin():
    reference = _columns(_unit(1))
    field = _columns(_unit(np.sqrt(0.85), np.sqrt(0.15)), _unit(np.sqrt(0.82), 0, np.sqrt(0.18)), _unit(0, 0, 0, 1))
    columns, reasons, raised = _both(1, reference, np.array([2.0, 1.9, 1.5]), field)
    assert "ambiguous assignment margin" in raised
    assert columns == [-1] and "ambiguous assignment margin 0.03" in reasons[0]


def test_match_modes_search_boundary():
    reference = _columns(_unit(0, 0, 1))
    field = _columns(_unit(1), _unit(0, 1), _unit(0, 0, 1))
    columns, reasons, raised = _both(1, reference, np.array([2.0, 1.9, 1.5]), field, search_modes=3)
    assert "search boundary" in raised
    assert columns == [-1] and "last candidate of the search" in reasons[0]


def test_match_modes_fewer_candidates_than_modes():
    reference = _columns(_unit(1), _unit(0, 1), _unit(0, 0, 1))
    field = _columns(_unit(1), _unit(0, 0, 1))
    columns, reasons, raised = _both(3, reference, np.array([2.0, 1.5]), field)
    assert "found only 2" in raised
    assert columns == [0, -1, 1] and reasons[0] is None and reasons[2] is None
    assert "found only 2 candidates for 3 modes" in reasons[1]


def test_match_modes_degenerate_candidate():
    reference = _columns(_unit(1))
    field = _columns(_unit(1), _unit(0, 1), _unit(0, 0, 1))
    columns, reasons, raised = _both(1, reference, np.array([2.0, 2.0 - 5e-6, 1.5]), field)
    assert "near-degenerate" in raised
    assert columns == [-1] and "near-degenerate within n_eff tolerance" in reasons[0]
