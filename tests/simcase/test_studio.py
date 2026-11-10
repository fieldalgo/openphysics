# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The optional browser UI: its HTTP API, and the boundary it must not cross."""

import ast
import copy
import time
from pathlib import Path

import numpy as np
import pytest

import simcase
from simcase import examples

STUDIO = Path(simcase.__file__).parent / "studio"


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("fastapi", reason="the studio extra is not installed")
    from fastapi.testclient import TestClient

    from simcase.studio import app
    return TestClient(app)


# ---- the boundary ----------------------------------------------------------------

def test_studio_uses_only_the_public_api():
    """studio is an ordinary consumer of simcase, so lifting it back out stays a move.

    A leak here is cheap to write and expensive to find later, so it is checked
    rather than agreed: if the UI needs something simcase does not export, the fix
    is to export it on purpose, not to reach past this test.
    """
    leaks = []
    for path in sorted(STUDIO.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                leaks += [f"{path.name}: import {a.name}" for a in node.names
                          if a.name.split(".")[0] == "simcase" and a.name != "simcase"]
            elif isinstance(node, ast.ImportFrom) and node.level > 1:
                # A relative import above studio/ reaches simcase without naming it.
                leaks.append(f"{path.name}:{node.lineno}: from {'.' * node.level}{node.module or ''} import ...")
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                if node.module.split(".")[0] != "simcase":
                    continue
                if node.module != "simcase":
                    leaks.append(f"{path.name}: from {node.module} import ...")
                    continue
                leaks += [f"{path.name}: simcase.{a.name} is not in simcase.__all__"
                          for a in node.names if a.name not in simcase.__all__]
    assert not leaks, "studio reached into simcase internals:\n  " + "\n  ".join(leaks)


def test_the_page_is_packaged():
    assert (STUDIO / "static" / "index.html").is_file()


# ---- the API ---------------------------------------------------------------------

def test_index_and_examples(client):
    assert client.get("/").status_code == 200
    ex = client.get("/api/examples").json()["examples"]
    assert "soi_strip" in ex
    doc = client.get("/api/examples/soi_strip").json()
    assert doc["openphysics"] == "0.3" and doc["geometry"]["shapes"][0]["name"] == "core"
    assert client.get("/api/examples/nope").status_code == 404


def test_materials_and_preview(client):
    """Library materials under the names a format 0.3 document writes, no aliases, ranges in m."""
    mats = {m["name"]: m for m in client.get("/api/materials").json()["materials"]}
    assert "physmat:Si" in mats and "Si" not in mats and all("aliases" not in m for m in mats.values())
    assert mats["physmat:Si"]["valid"]["vacuum_wavelength"]["unit"] == "m"
    lo, hi = mats["physmat:Si"]["valid"]["vacuum_wavelength"]["values"]
    assert 1e-7 < lo < 1.55e-6 < hi < 1e-4
    prev = client.post("/api/materials/preview", json={"name": "physmat:SiO2", "vacuum_wavelength_minimum": 5e-7,
                                                       "vacuum_wavelength_maximum": 1.6e-6}).json()
    assert prev["vacuum_wavelength"]["unit"] == "m" and len(prev["vacuum_wavelength"]["values"]) == 100
    assert 1.44 < prev["refractive_index"]["n"][-1] < 1.46 and prev["refractive_index"]["k"][-1] == 0
    assert client.post("/api/materials/preview", json={"name": "physmat:Si", "vacuum_wavelength_minimum": 3e-7,
                                                       "vacuum_wavelength_maximum": 4e-7}).status_code == 400
    assert client.post("/api/materials/preview", json={"name": "Si"}).status_code == 404     # not a library name


def test_quantities_come_from_the_registry(client):
    """/api/quantities (was /api/units, units batch C10): every registry quantity with its canonical
    unit and its menu, from simcase.quantities."""
    served = client.get("/api/quantities").json()
    assert set(served["quantities"]) == set(simcase.quantities.names())
    for name, entry in served["quantities"].items():
        assert entry == {"unit": simcase.quantities.quantity(name).unit,
                         "menu": list(simcase.quantities.menu(name))}, name
    assert served["quantities"]["vacuum_wavelength"] == {"unit": "m", "menu": ["nm", "um", "m"]}
    assert served["length_units"] == list(simcase.quantities.LENGTH_UNITS)
    assert client.get("/api/units").status_code == 404


def _leaves(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _leaves(v, f"{path}.{k}" if path else k)
    else:
        yield path, node


def _in_nm(doc):
    """SLAB_TE_CHECK with its shape numbers written in nm (exact decimals; tagged sizes keep um)."""
    from decimal import Decimal
    d = copy.deepcopy(doc)
    g = d["geometry"]
    g["length_unit"] = "nm"
    g["domain"] = {k: float(Decimal(repr(v)) * 1000) for k, v in g["domain"].items()}
    for shape in g["shapes"]:
        for k in ("x", "y", "w", "h"):
            shape[k] = float(Decimal(repr(shape[k])) * 1000)
    return d


def test_the_server_never_drops_the_length_unit(client):
    """Read the numbers out, write them back: that is where a unit system dies.

    The length_unit is the only thing that says what the shape numbers mean, and it is
    the one field an editor has no reason to touch, so losing it turns a document that
    meant nanometres into one that means micrometres with every number still looking
    right. Commercial FEA loses units on exactly this path - the export and scripting
    route, not the solver - so the studio checks it rather than assuming it.
    """
    served = client.get("/api/examples/soi_strip").json()
    assert served["geometry"]["length_unit"] == "um" and "units" not in served

    doc = _in_nm(examples.SLAB_TE_CHECK)
    back = client.post("/api/validate", json={"doc": doc}).json()
    assert back["ok"] and back["doc"]["geometry"]["length_unit"] == "nm"
    assert "(length_unit nm)" in back["summary"] and back["diagnostics"] == []

    sent, returned = dict(_leaves(doc)), dict(_leaves(back["doc"]))
    assert not sent.keys() - returned.keys(), "the server dropped fields the page sent"
    assert all(returned[k] == v for k, v in sent.items()), "the server altered a value it was given"

    # The page edits whatever validate hands back and posts it again, so that loop
    # has to be a fixed point: nothing is re-interpreted.
    again = client.post("/api/validate", json={"doc": back["doc"]}).json()
    assert again["doc"] == back["doc"]
    # a scale slip is reported with its code, and the document stays valid
    slip = copy.deepcopy(examples.SLAB_TE_CHECK)
    slip["geometry"]["length_unit"] = "nm"
    warned = client.post("/api/validate", json={"doc": slip}).json()
    assert warned["ok"] and [d["code"] for d in warned["diagnostics"]] == ["W-GEOMETRY-SCALE"]


def test_validate_reports_errors(client):
    ok = client.post("/api/validate", json={"doc": examples.FIBER}).json()
    assert ok["ok"] and "fiber" in ok["summary"]
    bad = dict(examples.FIBER, physics={"em1": dict(examples.FIBER["physics"]["em1"], formulation="magic")})
    r = client.post("/api/validate", json={"doc": bad}).json()
    assert not r["ok"] and "formulation" in r["error"]


def test_mesh_preview(client):
    r = client.post("/api/mesh", json={"doc": examples.FIBER})
    assert r.status_code == 200
    m = r.json()
    assert "units" not in m and m["field_units"] == {"node_coordinates": "m"}
    assert m["display"] == {"length_unit": "um", "metres_per_length_unit": 1e-6}
    assert m["diagnostics"] == []
    nodes = np.array(m["node_coordinates"])
    assert np.abs(nodes).max() == pytest.approx(20e-6, rel=1e-12)            # the 40 um window, in metres
    assert m["stats"]["triangles"] == len(m["triangles"]) > 500
    assert set(m["region_names"]) == {"core", "background"}
    assert m["stats"]["min_angle"] >= 28 - 1e-6


def test_run_job_roundtrip(client):
    doc = dict(examples.SLAB_TE_CHECK)
    job = client.post("/api/run", json={"doc": doc}).json()["job"]
    for _ in range(600):
        st = client.get(f"/api/jobs/{job}").json()
        if st["status"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert st["status"] == "done", st
    res = client.get(f"/api/jobs/{job}/result").json()
    assert "units" not in res["summary"] and res["field_units"] == {"node_coordinates": "m"}
    assert res["vacuum_wavelength"] == {"unit": "m", "values": [1.55e-6]} == res["summary"]["vacuum_wavelength"]
    assert res["effective_index"]["unit"] == "1"
    assert abs(res["effective_index"]["values"][0][0] - 2.8487) < 2e-3
    field = res["unnormalized_mode_field"][0]
    assert field["imag"] is None and len(field["real"][0]) == len(res["node_coordinates"])
    assert any("n_eff" in line for line in st["log"])
    assert client.get("/api/jobs/zzz").status_code == 404


def _done(client, job, rounds=300, pause=0.05):
    for _ in range(rounds):
        status = client.get(f"/api/jobs/{job}").json()
        if status["status"] in ("done", "error"):
            return status
        time.sleep(pause)
    pytest.fail("job did not complete")


def test_vector_job_preserves_complex_components_and_uses_element_samples(client):
    doc = copy.deepcopy(examples.VECTOR_SLAB)
    doc["physics"]["em1"]["boundary"].update(left="pmc", right="pmc")
    assert client.post("/api/validate", json={"doc": doc}).json()["ok"]
    job = client.post("/api/run", json={"doc": doc}).json()["job"]
    status = _done(client, job)
    assert status["status"] == "done", status
    res = client.get(f"/api/jobs/{job}/result").json()
    assert res["unnormalized_mode_field"] == [] and res["group_index"] is None
    assert res["summary"]["formulation"] == "vector"
    field = res["vector_fields"][0]
    assert field["name"] == "unnormalized_electric_field" and field["components"] == ["x", "y", "z"]
    assert field["location"] == "triangle_centroids" and field["unit"] == "1"
    assert field["time_convention"] == "exp(-i omega t)" and "amplitude_unit" not in field
    E = np.array(field["real"]) + 1j * np.array(field["imag"])
    assert E.shape == (1, len(res["triangles"]), 3)
    assert np.max(abs(E[:, :, 2].imag)) > 0.1
    assert abs(res["effective_index"]["values"][0][0] - 2.0562883300990773) < 1e-3
    doc["study"] = dict(type="sweep", parameter="physics.em1.vacuum_wavelength",
                        values={"unit": "um", "values": [1.5, 1.6]})
    rejected = client.post("/api/run", json={"doc": doc})
    assert rejected.status_code == 400 and "at least 3" in rejected.json()["detail"]


def test_sellmeier_json_edit_roundtrip_and_validation(client):
    doc = _in_nm(examples.SLAB_TE_CHECK)
    doc["materials"] = {"glass": {"refractive_index": {
        "model": "sellmeier", "terms": [{"strength": 1.0, "resonance_wavelength_squared": "10000 nm^2"}],
        "valid": {"vacuum_wavelength": ["500 nm", "2000 nm"]}, "reference_medium": "vacuum"}}}
    doc["geometry"]["background"] = {"material": "glass"}
    back = client.post("/api/validate", json={"doc": doc}).json()
    assert back["ok"], back
    assert back["doc"]["materials"] == doc["materials"]
    assert client.post("/api/validate", json={"doc": back["doc"]}).json()["doc"] == back["doc"]
    doc["materials"]["glass"]["refractive_index"]["terms"].append({"strength": 1.0})
    bad = client.post("/api/validate", json={"doc": doc}).json()
    assert not bad["ok"] and "materials.glass.refractive_index.terms[1].resonance_wavelength_squared" in bad["error"]
    assert client.post("/api/run", json={"doc": doc}).status_code == 400
    assert client.post("/api/mesh", json={"doc": doc}).status_code == 400


def _finished_job(client, doc):
    response = client.post("/api/run", json={"doc": doc})
    assert response.status_code == 200, response.json()
    job = response.json()["job"]
    return job, _done(client, job, 600)


@pytest.mark.parametrize("formulation", ["scalar", "vector"])
def test_absorbing_modes_preserve_complex_results_in_studio(client, formulation):
    doc = copy.deepcopy(examples.VECTOR_SLAB)
    doc["materials"]["film"] = {"refractive_index": {"n": 3.48, "k": .01}}
    doc["physics"]["em1"]["formulation"] = formulation
    if formulation == "scalar":
        doc["physics"]["em1"]["boundary"].update(left="pmc", right="pmc")
        del doc["physics"]["em1"]["effective_index_threshold"]
    job, status = _finished_job(client, doc)
    assert status["status"] == "done", status
    payload = client.get(f"/api/jobs/{job}/result").json()
    assert payload["summary"]["mode_result_schema"] == "openphysics.modes2d/3"
    index = payload["effective_index"]
    assert index["time_convention"] == "exp(-i omega t)" and index["im"][0][0] > 0     # loss: Im n_eff > 0
    assert payload["propagation_loss"]["unit"] == "dB/m" and payload["propagation_loss"]["values"][0][0] > 0
    assert index == payload["summary"]["effective_index"]
    if formulation == "scalar":
        assert payload["unnormalized_mode_field"][0]["imag"]


def test_tracked_vector_sweep_api_returns_branches_fields_and_group_indices(client):
    doc = copy.deepcopy(examples.VECTOR_SLAB_SWEEP)
    doc["physics"]["em1"]["mode_count"] = 2
    doc["study"]["values"] = {"unit": "um", "values": [1.20, 1.25, 1.30]}
    job, status = _finished_job(client, doc)
    assert status["status"] == "done", status
    result = client.get(f"/api/jobs/{job}/result").json()
    assert np.shape(result["effective_index"]["values"]) == np.shape(result["group_index"]["values"]) == (3, 2)
    assert np.isfinite(result["group_index"]["values"]).all()
    assert len(result["vector_fields"]) == 3 and result["unnormalized_mode_field"] == []
    points = result["summary"]["mode_tracking"]["points"]
    assert points[0]["overlaps"] is None
    assert all(len(p["candidate_ranks"]) == 2 for p in points)
    assert min(points[1]["overlaps"]) > 0.8
    assert abs(result["effective_index"]["values"][1][0] - 2.9965406807) < 0.002


@pytest.mark.parametrize("failure", ["degenerate", "cutoff"])
def test_vector_tracking_errors_have_wavelength_and_no_result(client, failure):
    doc = copy.deepcopy(examples.VECTOR_FIBER if failure == "degenerate" else examples.VECTOR_SLAB)
    doc["physics"]["em1"]["mode_count"] = 1 if failure == "degenerate" else 2
    doc["study"] = dict(type="sweep", parameter="physics.em1.vacuum_wavelength",
                        values={"unit": "um", "values": [1.5, 1.55, 1.6] if failure == "degenerate"
                                else [1.25, 1.35, 1.45]})
    job, status = _finished_job(client, doc)
    assert status["status"] == "error" and not status["has_result"]
    assert failure in status["error"] and "vacuum_wavelength" in status["error"] and "um" in status["error"]
    assert client.get(f"/api/jobs/{job}/result").status_code == 409


def test_vector_sweep_rejects_path_beyond_numeric_leaf_with_http_400(client):
    doc = copy.deepcopy(examples.VECTOR_SLAB_SWEEP)
    doc["study"]["parameter"] = "physics.em1.vacuum_wavelength.extra"
    response = client.post("/api/run", json={"doc": doc})
    assert response.status_code == 400
    assert "names no value under physics" in response.json()["detail"]


def test_pml_studio_returns_candidate_diagnostics_and_bend_loss(client):
    import json
    from test_pml_contract import document
    doc = json.loads(document('vector', True).canonical_json())
    response = client.post('/api/run', json={'doc': doc})
    assert response.status_code == 200
    status = _done(client, response.json()['job'], 400, .025)
    assert status['status'] == 'done', status
    summary = client.get(f"/api/jobs/{response.json()['job']}/result").json()['summary']
    assert summary['open_boundary'][0]['stability'] == 'not_checked'
    assert summary['bend_loss']['unit'] == 'dB/(90 deg)' and summary['bend_loss']['values'][0][0] > 0
    assert summary['field_representation'] == 'pml-vector-edge-nodal-v2'


def test_subspace_job_returns_cluster_means_under_the_new_names(client):
    job, status = _finished_job(client, copy.deepcopy(examples.VECTOR_FIBER_SUBSPACE_SWEEP))
    assert status["status"] == "done", status
    result = client.get(f"/api/jobs/{job}/result").json()
    sub = result["subspace"]
    assert sub["field_representation"] == "vector-subspace-edge-nodal-v2"
    assert result["effective_index"] is None and result["unnormalized_mode_field"] == []
    assert np.shape(sub["effective_index"]) == (5, 2) and np.shape(sub["mean_effective_index"]) == (5, 1)
    assert sub["mean_effective_index"] == result["summary"]["mean_effective_index"]["values"]
    assert sub["mean_group_index"] == result["summary"]["mean_group_index"]["values"]
    assert len(sub["density"]) == 5 and len(sub["density"][0][0]) == len(result["triangles"])


def test_the_openphysics_command_opens_the_workspace_and_simcase_studio_the_classic_page():
    from simcase.studio.server import _arguments
    assert _arguments([], product=True).path == "/workspace"
    assert _arguments(["--classic"], product=True).path == "/"
    assert _arguments([], product=False).path == "/"
    assert _arguments(["--workspace"], product=False).path == "/workspace"
    with pytest.raises(SystemExit):
        _arguments(["--workspace"], product=True)          # the product command has no such flag


@pytest.mark.parametrize("product, argv, line", [
    (True, [], "OpenPhysics Studio at http://127.0.0.1:8765/workspace (stop with Ctrl+C)"),
    (False, [], "simcase studio at http://127.0.0.1:8765/"),          # unchanged for simcase-studio
    (False, ["--workspace"], "simcase studio at http://127.0.0.1:8765/workspace"),
])
def test_each_command_prints_its_address(monkeypatch, capsys, product, argv, line):
    import uvicorn

    from simcase.studio import server
    served = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: served.append(kwargs))
    server.main([*argv, "--no-browser"], product=product)
    assert capsys.readouterr().out.strip() == line
    assert served == [{"host": "127.0.0.1", "port": 8765, "log_level": "warning"}]
