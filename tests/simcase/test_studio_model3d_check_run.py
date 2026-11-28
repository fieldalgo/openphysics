# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The 3D builder's check answers whether Run would take the document (Studio 3D slice D, UI).

``/api/model3d/check`` also reads the document as the ``thermal.steady3d`` kind reads it, through
the same function ``POST /api/model3d/run`` calls before it starts anything
(``heat3d_runs.read_document``), and answers ``run``: ``{"ok": true}`` or the reader's refusal in its
own words. So Run's reason is known on every edit; no run, mesh job or process is started by a check.
The unanchored-group refusal needs the mesh, so it comes from a run, not from the check.
"""
import json

import pytest

import simcase

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

from simcase.studio import app  # noqa: E402
from simcase.studio import model3d_api  # noqa: E402

CARD = __import__("pathlib").Path(simcase.__file__).parent / "studio" / "static" / "model3d-layer-stack-3d.json"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def card(**heat):
    doc = json.loads(CARD.read_text(encoding="utf-8"))
    if heat:
        doc["physics"] = {"heat": {"type": "thermal.steady3d", **heat}}
    return doc


def check(client, doc):
    reply = client.post("/api/model3d/check", json={"doc": doc})
    assert reply.status_code == 200
    return reply.json()


def run_refusal(client, doc):
    """What POST /api/model3d/run answers for a document it refuses before starting (400)."""
    reply = client.post("/api/model3d/run", json={"doc": doc})
    assert reply.status_code == 400, reply.text
    return reply.json()


NO_PHYSICS = "Run takes a thermal.steady3d document (one physics entry of type 'thermal.steady3d')"


def test_a_document_without_heat_physics_is_not_run_in_the_run_route_s_words(client):
    doc = json.loads(CARD.read_text(encoding="utf-8"))
    doc.pop("physics", None)
    answer = check(client, doc)
    assert answer["ok"] is True and answer["mesh"]["ok"] is True
    assert answer["run"] == {"ok": False, "refused": NO_PHYSICS, "code": None}
    assert run_refusal(client, doc)["detail"] == NO_PHYSICS


def test_a_document_the_kind_takes_is_ready_to_run(client):
    answer = check(client, card(prescribed_temperature={"z0": "300 K"}, heat_source_density={"via": "1e12 W/m^3"}))
    assert answer["run"] == {"ok": True}


@pytest.mark.parametrize("heat, code, words", [
    ({"prescribed_temperature": {"via.z1": "300 K"}}, "E-CONTRACT", "Fixed temperature needs an outer face; via.z1 is inside"),
    ({"prescribed_temperature": {"z0": "300 K"}, "heat_source_density": {"stack.top": "1e12 W/m^3"}},
     "E-SELECTION-UNKNOWN", "no meshed region of that name; expected one of ['Si', 'SiO2', 'via']"),
    ({"prescribed_temperature": {"z0": "300 K"}, "convection": {"z1": "10 W/(m^2 K)"}}, "E-KEY-UNKNOWN", "convection"),
])
def test_the_kind_s_refusal_is_the_run_route_s_refusal(client, heat, code, words):
    doc = card(**heat)
    answer = check(client, doc)
    direct = run_refusal(client, doc)
    assert answer["ok"] is True, "the shape forms"
    assert answer["run"] == {"ok": False, "refused": direct["detail"], "code": direct.get("code")}
    assert answer["run"]["code"] == code and words in answer["run"]["refused"]


def test_a_check_starts_no_run_and_no_mesh_job(client):
    runs, jobs = model3d_api.runs, model3d_api.jobs
    before = (set(runs.runs), jobs.processes_started, set(jobs.jobs))
    for doc in (card(prescribed_temperature={"z0": "300 K"}), card(prescribed_temperature={"via.z1": "300 K"})):
        check(client, doc)
    assert (set(runs.runs), jobs.processes_started, set(jobs.jobs)) == before


def test_a_refusal_while_forming_answers_no_run_part(client):
    doc = card(prescribed_temperature={"z0": "300 K"})
    doc["geometry"]["components"]["stack3d"]["features"].append(
        {"name": "ball", "type": "sphere", "cx": 100, "cy": 100, "cz": 300, "r": 10, "material": "Cu"})
    answer = check(client, doc)
    assert answer["ok"] is False and "run" not in answer
