# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The check of a builder-shape component (cylinders, spheres) answers ``run`` as ``check_view`` does.

``/api/model3d/check`` sends a component with a cylinder or sphere to ``check_view_shapes``. It also
reads the document as ``POST /api/model3d/run`` reads it (``heat3d_runs.read_document``), and answers
``{"ok": true}`` or the reader's refusal in its own words and code, the same shape as for boxes and
layers. A check starts no run, mesh job or process.
"""
import copy
import json

import pytest

import simcase

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

from simcase.studio import app  # noqa: E402
from simcase.studio import model3d_api  # noqa: E402

CARD2 = __import__("pathlib").Path(simcase.__file__).parent / "studio" / "static" / "model3d-via-slab-3d.json"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def card2():
    return json.loads(CARD2.read_text(encoding="utf-8"))


def check(client, doc):
    reply = client.post("/api/model3d/check", json={"doc": doc})
    assert reply.status_code == 200
    return reply.json()


def test_card_2_is_ready_to_run(client):
    answer = check(client, card2())
    assert answer["ok"] is True and answer["mesh"]["ok"] is True
    assert answer["run"] == {"ok": True}


def test_a_builder_shape_refusal_is_the_run_route_s_refusal(client):
    doc = card2()
    doc["physics"]["heat"]["prescribed_temperature"] = {"via.side": "300 K"}
    answer = check(client, doc)
    direct = client.post("/api/model3d/run", json={"doc": doc})
    assert direct.status_code == 400, direct.text
    assert answer["ok"] is True, "the shape forms"
    assert answer["run"] == {"ok": False, "refused": direct.json()["detail"], "code": direct.json().get("code")}
    assert answer["run"]["refused"] == "Fixed temperature needs an outer face; via.side is inside"
    assert answer["run"]["code"] == "E-CONTRACT"


def test_a_builder_shape_check_starts_no_run_and_no_mesh_job(client):
    runs, jobs = model3d_api.runs, model3d_api.jobs
    before = (set(runs.runs), jobs.processes_started, set(jobs.jobs))
    doc = card2()
    bad = copy.deepcopy(doc)
    bad["physics"]["heat"]["prescribed_temperature"] = {"via.side": "300 K"}
    for d in (doc, bad):
        check(client, d)
    assert (set(runs.runs), jobs.processes_started, set(jobs.jobs)) == before
