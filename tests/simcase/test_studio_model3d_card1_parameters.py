# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Card 1 holds the design's parameters, t_ox = 10 um and via_w = 20 um, and is the same model.

``stack.oxide`` is ``t_ox`` thick and the via box spans ``100 ∓ via_w / 2`` in x and y and ``500`` to
``500 + t_ox`` in z, so the via still crosses only the oxide, and the domain's top is
``500 + t_ox + 100`` (substrate + oxide + top silicon), so z1 stays the stack's top face. Only the document's text changes: the
check answers the same display, coverage and regions as the card written out in numbers (the card
of before), ``build_mesh3d`` meshes it bit for bit alike, and the steady solve on that mesh gives the
same temperature and reaction heat rate bit for bit. The check also answers each box's evaluated size
in the component's unit, which the tree shows ("20 × 20 × 10 µm").
"""
import hashlib
import json
import time

import numpy as np
import pytest

import simcase

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

from simcase.studio import app  # noqa: E402

CARD = __import__("pathlib").Path(simcase.__file__).parent / "studio" / "static" / "model3d-layer-stack-3d.json"
KAPPA = {"Si": 130.0, "Si (top)": 130.0, "SiO2": 1.4, "via": 400.0}


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def card():
    return json.loads(CARD.read_text(encoding="utf-8"))


def numeric():
    """Card 1 written out in numbers: the document of before it held its parameters."""
    doc = card()
    del doc["geometry"]["parameters"]
    comp = doc["geometry"]["components"]["stack3d"]
    comp["features"][0]["layers"][1]["thickness"] = 10
    comp["features"][1].update(xmin=90, xmax=110, ymin=90, ymax=110, zmin=500, zmax=510)
    comp["domain"]["zmax"] = 610
    return doc


def check(client, doc):
    reply = client.post("/api/model3d/check", json={"doc": doc})
    assert reply.status_code == 200
    return reply.json()


def test_card_1_holds_the_design_parameters_and_uses_them(client):
    doc = card()
    assert doc["geometry"]["parameters"] == {"t_ox": {"value": "10 um"}, "via_w": {"value": "20 um"}}
    comp = doc["geometry"]["components"]["stack3d"]
    assert comp["features"][0]["layers"][1]["thickness"] == "t_ox"
    via = comp["features"][1]
    assert [via[k] for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")] == [
        "100 - via_w / 2", "100 + via_w / 2", "100 - via_w / 2", "100 + via_w / 2", 500, "500 + t_ox"]
    answer = check(client, doc)
    used = {p["name"]: (p["value"], p["unit"], p["used_by"]) for p in answer["parameters"]}
    assert used["t_ox"][:2] == (1e-05, "m") and used["via_w"][:2] == (2e-05, "m")
    assert used["t_ox"][2] == ["domain.zmax", "features[0].layers[1].thickness", "features[1].zmax"]
    assert used["via_w"][2] == ["features[1].xmax", "features[1].xmin", "features[1].ymax", "features[1].ymin"]


def test_the_check_answers_each_box_s_evaluated_size(client):
    answer = check(client, card())
    assert answer["features"][1]["size"] == [20.0, 20.0, 10.0]
    assert "size" not in answer["features"][0], "a layers feature has no box size"


def test_the_evaluated_model_is_the_card_of_before(client):
    with_params, before = check(client, card()), check(client, numeric())
    for key in ("display", "regions", "run"):
        assert with_params[key] == before[key], key
    # the mesh estimate is the same; its reuse key hashes the document's text, which differs by design
    assert with_params["mesh"]["estimate"] == before["mesh"]["estimate"]
    assert with_params["mesh"]["key"] != before["mesh"]["key"]
    assert [{k: v for k, v in f.items()} for f in with_params["features"]] == before["features"]


def _mesh_sha(mesh):
    h = hashlib.sha256()
    for a in (np.asarray(mesh.nodes, float), np.asarray(mesh.tets, np.int64)):
        h.update(np.ascontiguousarray(a).tobytes())
    for name in sorted(mesh.tagged_faces):
        h.update(name.encode())
        h.update(np.ascontiguousarray(np.asarray(mesh.tagged_faces[name], np.int64)).tobytes())
    return h.hexdigest()


def _solve(mesh):
    from galerkin.thermal3d import solve_steady_heat_3d
    fixed = {int(n): 300.0 for n in np.unique(mesh.tagged_faces["z0"])}
    solution = solve_steady_heat_3d(mesh, thermal_conductivity={r: KAPPA.get(r, 400.0) for r in mesh.region_names},
                                    prescribed_temperature=dict(sorted(fixed.items())),
                                    heat_source_density={r: (1e12 if r == "Si (top)" else 0.0) for r in mesh.region_names})
    h = hashlib.sha256()
    for a in (np.asarray(solution.temperature, float), np.asarray(solution.reaction_heat_rate, float)):
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


def test_the_mesh_and_the_solve_are_the_same_bit_for_bit():
    a, b = simcase.build_mesh3d(card()).mesh, simcase.build_mesh3d(numeric()).mesh
    assert (len(a.nodes), len(a.tets)) == (1551, 6774)
    assert _mesh_sha(a) == _mesh_sha(b)
    assert _solve(a) == _solve(b)


def test_the_check_answers_the_evaluated_domain(client):
    """The domain in the component's unit with its parameters and expressions evaluated, which
    Studio's Domain row, size guards and Add feature's defaults read when a bound is not a number."""
    doc = card()
    assert doc["geometry"]["components"]["stack3d"]["domain"]["zmax"] == "500 + t_ox + 100"
    answer = check(client, doc)
    assert answer["domain"] == {"xmin": 0.0, "xmax": 200.0, "ymin": 0.0, "ymax": 200.0, "zmin": 0.0, "zmax": 610.0}
    assert check(client, numeric())["domain"] == answer["domain"]


def test_the_domain_top_follows_t_ox_so_z1_stays_the_top_face(client):
    """zmax = "500 + t_ox + 100" (substrate + oxide + top silicon): at t_ox = 5 um the stack and the
    domain end at 605 um, z1 is still the top silicon's top face, and a run with z0 = 300 K and
    z1 = 330 K completes (no void above the stack, no "z1 selects no face")."""
    doc = card()
    assert doc["geometry"]["components"]["stack3d"]["domain"]["zmax"] == "500 + t_ox + 100"
    doc["geometry"]["parameters"]["t_ox"]["value"] = "5 um"
    doc["physics"]["heat"]["prescribed_temperature"] = {"z0": "300 K", "z1": "330 K"}
    answer = check(client, doc)
    assert answer["ok"] is True and answer["run"] == {"ok": True}
    top = [f for f in answer["display"]["faces"] if f.get("tag") == "z1"]
    assert len(top) == 1 and top[0]["axis"] == "z" and top[0]["at"] == 605
    assert "stack.top.top" in top[0]["names"] and top[0]["exterior"] is True
    run = client.post("/api/model3d/run", json={"doc": doc})
    assert run.status_code == 200, run.text
    run_id = run.json()["run"]
    for _ in range(600):
        status = client.get(f"/api/model3d/runs/{run_id}").json()
        if status["status"] != "running":
            break
        time.sleep(0.2)
    assert status["status"] == "done", status
    values = client.get(f"/api/model3d/runs/{run_id}/values").json()
    assert set(values["heat_rate_by_selection"]) == {"z0", "z1"}
