# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""``pml.pml_search_mode_count``: the open-boundary candidates searched before the physical-fraction
filter. Absent, the search is max(2 mode_count, 6) as before; the result format does not change."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

import refsol.lossy_slab
from simcase import Document, DocumentError, run
from simcase.physics_pml_modes import search_count

ROOT = Path(__file__).resolve().parents[2]
P = "physics.em1."


def leaky(**pml):
    data = json.loads((ROOT / "examples" / "simcase" / "pml_leaky_slab.json").read_text(encoding="utf-8"))
    data["physics"]["em1"]["pml"].update(pml)
    return data


def without_timing(value):
    """A result with its wall-clock timings left out: the one part two runs of one document do not share."""
    if isinstance(value, dict):
        return {k: without_timing(v) for k, v in value.items() if k != "timing"}
    if isinstance(value, list):
        return [without_timing(v) for v in value]
    return value


def saved(document, folder):
    run(Document.from_dict(document), False).save(folder)
    summary = without_timing(json.loads((folder / "summary.json").read_text(encoding="utf-8")))
    with np.load(folder / "fields.npz") as archive:
        arrays = {k: archive[k] for k in archive.files}
    metadata = without_timing(json.loads(str(arrays.pop("metadata_json"))))
    return summary, metadata, arrays


def test_kernel_default_is_the_count_before_the_setting():
    assert [search_count({}, m) for m in (1, 2, 3, 4, 8)] == [6, 6, 6, 8, 16]
    assert search_count({"search_count": 16}, 2) == 16


def test_absent_key_is_not_recorded_and_an_explicit_default_gives_the_same_result(tmp_path):
    absent = Document.from_dict(leaky())
    assert not any("pml_search_mode_count" in entry["path"] for entry in absent.defaults_applied)
    a = saved(leaky(), tmp_path / "absent")
    b = saved(leaky(pml_search_mode_count=6), tmp_path / "explicit")
    # the summary echoes what was written: the authored count is the one entry the absent key lacks
    echoed = b[0]["resolved_inputs"].pop(P + "pml.pml_search_mode_count")
    assert echoed["authored"] == echoed["value"] == 6
    assert a[0] == b[0]
    assert b[1]["resolved_inputs"].pop(P + "pml.pml_search_mode_count") == echoed
    assert a[1] == b[1]
    assert a[2].keys() == b[2].keys()
    for key in a[2]:
        if key != "open_boundary_json":
            assert a[2][key].dtype == b[2][key].dtype and a[2][key].tobytes() == b[2][key].tobytes(), key
    assert json.loads(str(a[2]["open_boundary_json"])) == json.loads(str(b[2]["open_boundary_json"]))
    assert len(a[0]["open_boundary"][0]["candidates"]) == 6


def test_a_wider_search_returns_the_same_leaky_pole_within_one_percent_of_the_reference():
    """V3: the engine leaky slab (n = 3.48 over 1.444, 250 nm gap) against refsol, in dB/cm."""
    expected = refsol.lossy_slab.substrate_leaky_mode(refractive_index=(1.444, 3.48, 1.444, 3.48),
                                                      thickness=(0.22e-6, 0.25e-6), vacuum_wavelength=1.55e-6)
    reference_db = 4 * np.pi * expected.imag / 1.55e-6 * 10 * np.log10(np.e)
    six = run(Document.from_dict(leaky()), False)
    sixteen = run(Document.from_dict(leaky(pml_search_mode_count=16)), False)
    diagnostics = sixteen.open_boundary[0]
    assert len(diagnostics["candidates"]) == 16 and diagnostics["selected_candidates"]
    np.testing.assert_allclose(sixteen.effective_index, six.effective_index, rtol=0, atol=1e-10)
    for result in (six, sixteen):
        loss = float(result.propagation_loss()[0, 0])               # dB/m
        assert abs(loss / reference_db - 1) <= 0.01
        assert abs(result.effective_index[0, 0].real - expected.real) <= 1e-3


@pytest.mark.parametrize("value,code", [
    (0, "E-DOMAIN"), (65, "E-DOMAIN"), (2.5, "E-DOMAIN"), (True, "E-VALUE-FORM"), ("16", "E-UNIT-UNKNOWN"),
])
def test_the_range_is_refused(value, code):
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(leaky(pml_search_mode_count=value))
    found = {(x.code, x.path) for x in caught.value.diagnostics}
    assert (code, P + "pml.pml_search_mode_count") in found, [x.as_dict() for x in caught.value.diagnostics]


def test_fewer_candidates_than_mode_count_are_refused():
    data = leaky(pml_search_mode_count=3)
    data["physics"]["em1"]["mode_count"] = 4
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(data)
    assert {(x.code, x.path) for x in caught.value.diagnostics} == {("E-CONTRACT", P + "pml.pml_search_mode_count")}
    data["physics"]["em1"]["pml"]["pml_search_mode_count"] = 4
    Document.from_dict(data)


@pytest.mark.parametrize("formulation", ["vector", "scalar"])
def test_a_sweep_needs_the_tracker_search_count(formulation):
    data = leaky(pml_search_mode_count=4)
    em = data["physics"]["em1"]
    em["formulation"] = formulation
    if formulation == "scalar":
        del em["effective_index_threshold"]
        em["boundary"].update(left="pmc", right="pmc")
    data["study"] = {"type": "sweep", "parameter": P + "vacuum_wavelength",
                     "values": {"unit": "um", "values": [1.549, 1.55, 1.551]}}
    # mode_count 1 tracks with max(2, 1 + 4) = 5 searched modes per point
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(copy.deepcopy(data))
    assert {(x.code, x.path) for x in caught.value.diagnostics} == {("E-CONTRACT", P + "pml.pml_search_mode_count")}
    em["pml"]["pml_search_mode_count"] = 5
    Document.from_dict(data)


def test_the_kernel_refuses_a_search_below_the_requested_modes():
    from simcase.pml_contract import validate
    p = dict(pml=dict(thickness=dict(top=1.), search_count=2), n_target=2., boundary=dict(top="pec"), num_modes=3)
    with pytest.raises(ValueError, match="search_count must be at least num_modes"):
        validate(p, dict(xmin=0, xmax=1, ymin=0, ymax=4), "modes", ValueError)
    for bad in (0, 65, 2.0, True):
        p["pml"]["search_count"] = bad
        with pytest.raises(ValueError, match="integer from 1 to 64"):
            validate(p, dict(xmin=0, xmax=1, ymin=0, ymax=4), "modes", ValueError)
