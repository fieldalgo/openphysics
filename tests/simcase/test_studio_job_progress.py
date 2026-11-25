# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The step of a running optical job (job progress, slice S2): ``GET /api/jobs/{job}`` returns
``step``, the latest ``search_started`` event of ``simcase.run``'s ``on_event``.

Pre-registered check J7 of the job-progress design (lab notes/studio/job-progress-draft.md): ``step``
is null at the start, every step seen is one of the run's events in the order of the work, ``step`` is
null once the job is done, and the result is the same as without the callback. J7's frozen document is
a 3.5 minute open run; here a coarser open document with the group index (the same shapes, PML and two
searches) stands in for it, and the frozen run is a measured check recorded in the commit that adds
this file.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from simcase.studio import server  # noqa: E402

FIXTURES = Path(__file__).parent / "studio_session_fixtures"


def _open_document():
    """The Studio open document with two searches on a coarse mesh, with the group index on."""
    tree = json.loads((FIXTURES / "optical-document-strip-substrate-open-searches.json").read_text())
    for shape in tree["geometry"]["shapes"]:
        shape["element_size"] = "90 nm"
    tree["mesh"].update(element_size="600 nm", grading={**tree["mesh"]["grading"], "near": "90 nm", "far": "400 nm"})
    tree["results"]["group_index"] = {"wavelength_step": "1 nm"}
    return tree


def _closed_document():
    return json.loads((FIXTURES / "optical-document-template-v8-1.json").read_text())


@pytest.fixture(scope="module")
def client():
    return TestClient(server.app)


def _instance(client):
    return {"workspace_instance": client.get("/api/workspace/capabilities/v8").json()["server_instance"]}


def _follow(client, doc, interval=0.2):
    """(every status reply while running, the last status, the result) of a document's job."""
    q = _instance(client)
    job = client.post("/api/run", params=q, json={"doc": doc}).json()["job"]
    seen, deadline = [], time.monotonic() + 600
    while (status := client.get(f"/api/jobs/{job}", params=q).json())["status"] == "running":
        assert time.monotonic() < deadline, "the optical job did not finish"
        seen.append(status)
        time.sleep(interval)
    return seen, status, client.get(f"/api/jobs/{job}/result", params=q).json()


def _without_timing(result):
    result = json.loads(json.dumps(result))
    result.pop("timings", None)
    result["summary"].pop("timing", None)
    return result


EXPECTED = [{"event": "search_started", "point": 1, "points": 1, "solve": solve, "solves": 3,
             "solve_kind": "study_point" if solve == 1 else "group_index", "search": search, "searches": 2}
            for solve in (1, 2, 3) for search in (1, 2)]


def test_a_running_job_reports_its_step_and_none_once_done(client, monkeypatch):
    """J7: null before the first event (held by a gate), the run's events in order, null when done;
    the result is the result of the same job without the callback."""
    gate, real_run = threading.Event(), server.run

    def gated(doc, verbose=True, **kwargs):
        assert gate.wait(60)
        return real_run(doc, verbose=verbose, **kwargs)
    monkeypatch.setattr(server, "run", gated)
    q = _instance(client)
    job = client.post("/api/run", params=q, json={"doc": _open_document()}).json()["job"]
    first = client.get(f"/api/jobs/{job}", params=q).json()
    assert first == {"status": "running", "log": [], "error": None, "step": None, "has_result": False}
    gate.set()
    seen, deadline = [], time.monotonic() + 600
    while (status := client.get(f"/api/jobs/{job}", params=q).json())["status"] == "running":
        assert time.monotonic() < deadline
        seen.append(status["step"])
        time.sleep(0.2)
    assert status["status"] == "done" and status["step"] is None and status["has_result"] is True
    steps = [s for s in seen if s is not None]
    assert steps, "no step was seen while the job ran"
    positions = [EXPECTED.index(s) for s in steps]          # every step is one of the run's events
    assert positions == sorted(positions)                   # in the order of the work
    result = client.get(f"/api/jobs/{job}/result", params=q).json()

    # the same document without the callback: the result the server would give before this change
    monkeypatch.setattr(server, "run", lambda doc, verbose=True, on_event=None: real_run(doc, verbose=verbose))
    plain_seen, plain_status, plain = _follow(client, _open_document())
    assert all(s["step"] is None for s in plain_seen) and plain_status["step"] is None
    assert _without_timing(result) == _without_timing(plain)


def test_a_failed_job_has_no_step(client, monkeypatch):
    real_run = server.run

    def failing(doc, verbose=True, on_event=None):
        on_event({"event": "search_started", "point": 1, "points": 1, "solve": 1, "solves": 1,
                  "solve_kind": "study_point", "search": 1, "searches": 1})
        raise RuntimeError("the solver failed")
    monkeypatch.setattr(server, "run", failing)
    _, status, _ = _follow(client, _closed_document())
    assert status["status"] == "error" and status["step"] is None and status["has_result"] is False
    monkeypatch.setattr(server, "run", real_run)


def test_a_closed_job_reports_its_one_step_and_ends_with_none(client):
    seen, status, result = _follow(client, _closed_document(), interval=0.01)
    assert status["status"] == "done" and status["step"] is None
    for s in seen:
        assert s["step"] in (None, {"event": "search_started", "point": 1, "points": 1, "solve": 1, "solves": 1,
                                    "solve_kind": "study_point", "search": 1, "searches": 1})
    assert result["effective_index"]
