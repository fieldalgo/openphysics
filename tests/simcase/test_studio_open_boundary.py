# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The open boundary of Studio's optical document (adapter optical-shapes-v9, capabilities v9):
the capabilities, the server's refusal of other workspace PMLs, the adapter's index table against
physmat, and V7 (with every edge closed, the optical-shapes-v8 document and result). The document
builder is tests/simcase/studio_open_boundary.cjs; the validation of the documents it writes is in
tests/simcase/test_open_boundary_*.py (one file per check, so the CI parts can spread them).
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from open_boundary_fixtures import ALL, CLOSED, FIXTURES, STATIC, TOP_BOTTOM, WAVELENGTH, build, node
import subprocess

import physmat
from simcase import Document, run


# -- contract ------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from simcase.studio import app
    return TestClient(app)


def test_capabilities_v9_is_v8_with_the_open_boundary(client):
    v8 = client.get("/api/workspace/capabilities/v8").json()
    v9 = client.get("/api/workspace/capabilities/v9").json()
    assert v9.pop("open_boundary") == {
        "edges": ["left", "right", "bottom", "top"], "edge_states": ["closed", "open"], "edge_default": "closed",
        "pml_thickness_range": ["1 um", "1 um"], "pml_thickness_default": "1 um", "pml_strength": 3, "pml_order": 2,
        "pml_minimum_physical_fraction": 0.5, "pml_search_mode_count": 32, "pml_check_strength": 6,
        "pml_check_search_mode_count": 16,
        "additional_search_count": 16, "additional_search_target": "(target + n_SiO2) / 2, two decimals",
        "target_effective_index_default": "(n_max + n_SiO2) / 2 at 1550 nm, two decimals",
        "target_effective_index_bounds": "above 1.45 and below n_max"}
    assert (v9.pop("schema_version"), v9.pop("adapter")) == (9, "optical-shapes-v9")
    assert (v8.pop("schema_version"), v8.pop("adapter")) == (8, "optical-shapes-v8")
    assert v9 == v8


def test_the_index_table_is_physmat_at_1550_nm():
    script = "const B = await import(process.argv[1]); process.stdout.write(JSON.stringify(B.INDEX_1550));"
    done = subprocess.run([node(), "--input-type=module", "-e", script, (STATIC / "workspace-open-boundary.mjs").as_uri()],
                          capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
    table = json.loads(done.stdout)
    shapes = subprocess.run([node(), "--input-type=module", "-e",
                             "const S = await import(process.argv[1]); process.stdout.write(JSON.stringify(S.SHAPE_MATERIALS));",
                             (STATIC / "workspace-shapes.mjs").as_uri()], capture_output=True, text=True, encoding="utf-8")
    materials = json.loads(shapes.stdout)
    assert set(table) == set(materials)
    for display, name in materials.items():
        n = complex(physmat.material(name.removeprefix("physmat:")).refractive_index(vacuum_wavelength=WAVELENGTH))
        assert table[display] == round(n.real, 4), display


def _instance(client):
    return {"workspace_instance": client.get("/api/workspace/capabilities/v9").json()["server_instance"]}


@pytest.mark.parametrize("change", [
    # strength 6 is the PML check's (slice P2, a change of P1's contract): 4, 6.0 and 1.5 are refused
    {"pml_strength": 4}, {"pml_strength": 6.0}, {"pml_strength": 1.5}, {"pml_order": 3}, {"pml_minimum_physical_fraction": 0.1}, {"pml_search_mode_count": 6},
    {"pml_search_mode_count": 16.0}, {"pml_order": True}, {"pml_thickness": {"top": "999 nm"}},
    {"pml_search_mode_count": 8}, {"pml_thickness": {"top": "1500 nm"}}, {"pml_thickness": {"top": "2000 nm"}},
    {"pml_thickness": {"top": "1 um"}}, {"pml_thickness": {"top": "1000 nm", "bottom": "1500 nm"}},
    {"extra": 1},
    {"target_effective_index": 1.45}, {"target_effective_index": True},
    {"domain": {"xmin": -1500, "xmax": 2500, "ymin": -2200, "ymax": 2200}},
    {"domain": {"xmin": -2500, "xmax": 2500, "ymin": -2200, "ymax": 2300}},
    {"length_unit": "um"},
])
def test_the_server_refuses_another_workspace_pml(client, change):
    doc = json.loads(build("template", 2, edges=ALL))
    if "target_effective_index" in change:
        doc["physics"]["em1"].update(change)
    elif "domain" in change:
        doc["geometry"]["domain"] = change["domain"]
    elif "length_unit" in change:
        doc["geometry"]["length_unit"] = change["length_unit"]
    else:
        doc["physics"]["em1"]["pml"].update(change)
    for route in ("/api/validate", "/api/run"):
        response = client.post(route, params=_instance(client), json={"doc": doc})
        assert response.status_code == 400 and "open boundary of a workspace run" in response.text, response.text


def test_the_server_takes_the_v9_document(client):
    doc = json.loads(build("strip_substrate", 2, edges=TOP_BOTTOM))
    response = client.post("/api/validate", params=_instance(client), json={"doc": doc})
    assert response.status_code == 200 and response.json()["ok"], response.text


def test_the_server_takes_the_pml_check_document(client):
    # the PML check (slice P2): the same document with strength 6, a search of 16 and a mode's target;
    # slice T2: one search, without the run's second search (checkDocuments)
    doc = json.loads(build("template", 2, edges=ALL))
    del doc["physics"]["em1"]["pml"]["pml_additional_searches"]
    doc["physics"]["em1"]["pml"].update(pml_strength=6, pml_search_mode_count=16)
    doc["physics"]["em1"]["target_effective_index"] = 1.769996
    response = client.post("/api/validate", params=_instance(client), json={"doc": doc})
    assert response.status_code == 200 and response.json()["ok"], response.text


@pytest.mark.parametrize("strength,search", [(6, 32), (3, 16)])
def test_the_check_strength_and_search_go_together(client, strength, search):
    # strength 6 only with a search of 16 (the check), strength 3 only with 32 (the run)
    doc = json.loads(build("template", 2, edges=ALL))
    doc["physics"]["em1"]["pml"].update(pml_strength=strength, pml_search_mode_count=search)
    for route in ("/api/validate", "/api/run"):
        response = client.post(route, params=_instance(client), json={"doc": doc})
        assert response.status_code == 400 and "A PML check request (strength 6) searches 16 candidates" in response.text, response.text


# -- V7: closed window --------------------------------------------------------------------------

def _without_timing(value):
    if isinstance(value, dict):
        return {k: _without_timing(v) for k, v in value.items() if k != "timing"}
    if isinstance(value, list):
        return [_without_timing(v) for v in value]
    return value


def _saved(text, folder):
    run(Document.from_dict(json.loads(text)), False).save(folder)
    summary = _without_timing(json.loads((folder / "summary.json").read_text(encoding="utf-8")))
    with np.load(folder / "fields.npz") as archive:
        arrays = {k: archive[k].tobytes() for k in archive.files if k != "metadata_json"}
        metadata = _without_timing(json.loads(str(archive["metadata_json"])))
    return summary, metadata, arrays


@pytest.mark.parametrize("modes,fixture", [(1, "optical-document-template-v8-1.json"), (2, "optical-document-template-v7.json"),
                                           (8, "optical-document-template-v8-8.json")])
def test_v7_every_edge_closed_is_the_v8_document_and_result(tmp_path, modes, fixture):
    text = build("template", modes, edges=CLOSED)
    expected = (FIXTURES / fixture).read_text(encoding="utf-8")
    assert text == expected
    if modes == 2:
        # the same document gives the same result (wall-clock timings aside)
        assert _saved(text, tmp_path / "v9") == _saved(expected, tmp_path / "v8")


# -- W9 (slice T2): the second search of a run, and nothing else --------------------------------
RELOAD = "This page was loaded before Studio was updated; reload the page to run again."


def _post(client, doc):
    return [client.post(route, params=_instance(client), json={"doc": doc}) for route in ("/api/validate", "/api/run")]


def _with_target(doc, target, low):
    """The builder's document with Search near n_eff ``target`` and t_low ``low`` written by hand."""
    em = doc["physics"]["em1"]
    em["target_effective_index"] = target
    em["pml"].pop("pml_additional_searches", None)
    if low is not None:
        em["pml"]["pml_additional_searches"] = [{"target_effective_index": low, "pml_search_mode_count": 16}]
    return doc


@pytest.mark.parametrize("target,low", [(2.46, 1.95), (2.2, 1.82), (1.6, 1.52), (1.72, 1.58), (2.466, 1.96),
                                        (1.466, 1.46), (1.465, None), (1.451, None)])
def test_w9_the_server_takes_the_second_search_of_t_low(client, target, low):
    doc = _with_target(json.loads(build("template", 2, edges=ALL)), target, low)
    response = client.post("/api/validate", params=_instance(client), json={"doc": doc})
    assert response.status_code == 200 and response.json()["ok"], response.text
    # the same target written as an exact decimal with a trailing zero
    if low is not None:
        text = json.dumps(doc).replace(f'"target_effective_index": {low}, "pml_search_mode_count"',
                                       f'"target_effective_index": {low:.3f}, "pml_search_mode_count"')
        assert f"{low:.3f}" in text
        response = client.post("/api/validate", params=_instance(client), content='{"doc": ' + text + "}",
                               headers={"content-type": "application/json"})
        assert response.status_code == 200 and response.json()["ok"], response.text


@pytest.mark.parametrize("change", [
    {"target_effective_index": 1.94}, {"target_effective_index": 1.96}, {"target_effective_index": 1.952},
    {"pml_search_mode_count": 15}, {"pml_search_mode_count": 17}, {"pml_search_mode_count": 16.0},
    {"pml_search_mode_count": True}, {"target_effective_index": True}, {"target_effective_index": "1.95"},
    {"extra": 1}, "second entry", "not a list", "empty",
])
def test_w9_the_server_refuses_another_second_search(client, change):
    doc = json.loads(build("template", 2, edges=ALL))
    searches = doc["physics"]["em1"]["pml"]["pml_additional_searches"]
    assert searches == [{"target_effective_index": 1.95, "pml_search_mode_count": 16}]
    if change == "second entry":
        searches.append({"target_effective_index": 1.7, "pml_search_mode_count": 16})
    elif change == "not a list":
        doc["physics"]["em1"]["pml"]["pml_additional_searches"] = searches[0]
    elif change == "empty":
        searches.clear()
    else:
        searches[0].update(change)
    for response in _post(client, doc):
        assert response.status_code == 400 and "open boundary of a workspace run" in response.text, response.text


def test_w9_a_target_below_1_466_has_no_second_search(client):
    doc = _with_target(json.loads(build("template", 2, edges=ALL)), 1.465, 1.45)
    for response in _post(client, doc):
        assert response.status_code == 400 and "open boundary of a workspace run" in response.text, response.text


def test_w9_the_pml_check_has_no_second_search(client):
    doc = json.loads(build("template", 2, edges=ALL))
    doc["physics"]["em1"]["pml"].update(pml_strength=6, pml_search_mode_count=16)
    doc["physics"]["em1"]["target_effective_index"] = 1.769996
    for response in _post(client, doc):
        assert response.status_code == 400 and "open boundary of a workspace run" in response.text, response.text


@pytest.mark.parametrize("target", [2.46, 1.466])
def test_w9_a_single_search_run_asks_for_a_reload(client, target):
    """A run of P2's page (one search) whose target now has a second search: the page's modules were
    loaded before Studio was updated. Below 1.466 the same document is taken (above)."""
    doc = _with_target(json.loads(build("template", 2, edges=ALL)), target, None)
    for response in _post(client, doc):
        assert response.status_code == 400 and response.json()["detail"] == RELOAD, response.text
    # the reload words are for this case only
    doc = json.loads(build("template", 2, edges=ALL))
    doc["physics"]["em1"]["pml"]["pml_order"] = 3
    for response in _post(client, doc):
        assert response.status_code == 400 and RELOAD not in response.text, response.text
