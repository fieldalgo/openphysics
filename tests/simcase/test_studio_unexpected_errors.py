# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""An unexpected failure replies with a fixed message; its detail stays in the server log.

Each test injects an exception whose type and text appear nowhere in Studio, on one path where a
failure reaches a reply, a job status or a view. The reply carries the fixed message with the
code and status the path always had, and neither the exception's text nor its type name; the
``simcase.studio`` log holds both, with the traceback. On the same path, a refusal written for
users (``bodies.USER_FACING``) keeps its text exactly, meshine's own explanations included. The
geometry lab's generic 500 is tested in test_studio_geometry_lab.py.
"""

import copy
import logging
import threading

import pytest

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

import region_studio_fixtures as fx  # noqa: E402
from simcase import Document, DocumentError, MeshLimitError, ModeTrackingError, examples  # noqa: E402
from simcase.studio import server  # noqa: E402
from simcase.studio import thermal_api as thermal  # noqa: E402
from simcase.studio import thermal_regions_api as regions  # noqa: E402
from simcase.studio import transient_thermal_api as transient  # noqa: E402

MARKER = "SECRET-PATH-/srv/private/studio.key"
#: ``bodies.UNEXPECTED``, written out: the words are part of the reply contract
FIXED = "Studio failed unexpectedly; the details are in the server log"
OPTICAL = examples.EXAMPLES["soi_strip"]


class HiddenFailure(RuntimeError):
    """A failure no Studio path expects (its name must not reach a reply)."""


class HiddenValueFailure(ValueError):
    """The same, for a path that catches ``ValueError``."""


class HiddenTypeFailure(TypeError):
    """The same, for a path that catches ``TypeError``."""


def raising(error):
    def fail(*args, **kwargs):
        raise error
    return fail


def steady_model():
    return {"openphysics": "0.3", "name": "Studio unexpected-error control",
            "geometry": {"length_unit": "m", "depth": None, "domain": {"xmin": 0., "xmax": 1., "ymin": 0., "ymax": 1.}},
            "materials": {}, "physics": {"heat1": {
                "type": "thermal.steady2d", "thermal_conductivity": "2 W/(m K)", "heat_source_density": "0 W/m^3",
                "prescribed_temperature": {"left": "300 K", "right": "293 K"}}},
            "mesh": {"subdivision_count": [2, 2]}, "study": {"type": "single"},
            "results": {"save_fields": True, "plots": False}}


def transient_model():
    return {"openphysics": "0.3", "name": "Studio unexpected-error transient control",
            "geometry": {"length_unit": "m", "depth": None, "domain": {"xmin": 0., "xmax": 1., "ymin": 0., "ymax": 1.}},
            "materials": {}, "physics": {"heat1": {
                "type": "thermal.transient2d", "thermal_conductivity": "2 W/(m K)",
                "volumetric_heat_capacity": {"value": "4 J/(m^3 K)", "accept": {"W-MAGNITUDE": "control case"}},
                "initial_temperature": "300 K", "prescribed_temperature": {}, "heat_source_density": "8 W/m^3"}},
            "mesh": {"subdivision_count": [2, 2]},
            "study": {"type": "transient", "time": {"unit": "s", "values": [2., 3.]}},
            "results": {"save_fields": True, "plots": False}}


def envelope(doc):
    return {"doc": doc, "client_revision": 4, "request_seq": 9}


ROUTES = {"steady": ("/api/thermal/", steady_model), "transient": ("/api/thermal/transient/", transient_model),
          "region": ("/api/thermal/", fx.steady_example)}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server, "_thermal_jobs", thermal.ThermalJobs())
    monkeypatch.setattr(server, "_region_limits", regions.RegionLimits())
    monkeypatch.setattr(server, "_start_thermal_thread", lambda target, args: target(*args))
    with TestClient(server.app) as value:
        yield value


@pytest.fixture
def log(caplog):
    caplog.set_level(logging.WARNING, logger="simcase.studio")
    return caplog


def assert_hidden(text, name="HiddenFailure"):
    """The reply text names neither the injected exception nor its message."""
    assert MARKER not in text and name not in text and "Traceback" not in text, text


def assert_logged(log, name="HiddenFailure", count=None):
    """The server log holds the injected exception: its type, its message and a traceback."""
    records = [r for r in log.records if r.name == "simcase.studio" and r.exc_info and MARKER in str(r.exc_info[1])]
    assert records, log.text
    if count is not None:
        assert len(records) == count, log.text
    assert MARKER in log.text and name in log.text and "Traceback (most recent call last)" in log.text


def assert_idle(jobs):
    assert jobs._active == jobs._reserved_bytes == jobs._pending == 0
    assert jobs.ingress._token is None


# -- optical routes -------------------------------------------------------------------------------

def test_mesh_preview_hides_an_unexpected_failure_and_keeps_a_document_refusal(client, monkeypatch, log):
    for error in (HiddenFailure(MARKER), HiddenValueFailure(MARKER)):
        monkeypatch.setattr(server, "build_mesh", raising(error))
        response = client.post("/api/mesh", json={"doc": OPTICAL})
        assert response.status_code == 400 and response.json() == {"detail": FIXED}
        assert_hidden(response.text, type(error).__name__)
        assert_logged(log, type(error).__name__)
    refusal = DocumentError("geometry.domain: a refusal written for the user", path="geometry.domain")
    monkeypatch.setattr(server, "build_mesh", raising(refusal))
    response = client.post("/api/mesh", json={"doc": OPTICAL})
    assert response.status_code == 400 and response.json() == {"detail": str(refusal)}


def finished_optical(client):
    job = client.post("/api/run", json={"doc": OPTICAL}).json()["job"]
    for _ in range(500):
        status = client.get(f"/api/jobs/{job}").json()
        if status["status"] != "running":
            return status
        threading.Event().wait(0.02)
    raise AssertionError("optical job did not finish")


def test_optical_job_hides_an_unexpected_failure_and_keeps_a_tracking_refusal(client, monkeypatch, log):
    monkeypatch.setattr(server, "run", raising(HiddenFailure(MARKER)))
    status = finished_optical(client)
    assert status["status"] == "error" and status["error"] == FIXED and not status["has_result"]
    assert "open_boundary" not in status
    assert_hidden(str(status))
    assert_logged(log)
    refusal = ModeTrackingError("vector sweep at vacuum_wavelength=1.5 um: a refusal written for the user")
    monkeypatch.setattr(server, "run", raising(refusal))
    status = finished_optical(client)
    assert status["status"] == "error" and status["error"] == f"ModeTrackingError: {refusal}"


# -- thermal requests -----------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["steady", "transient"])
def test_thermal_validation_hides_an_unexpected_failure(client, monkeypatch, log, kind):
    route, model = ROUTES[kind]
    monkeypatch.setattr(thermal if kind == "steady" else transient, "validation_payload",
                        raising(HiddenFailure(MARKER)))
    response = client.post(route+"validate", json=envelope(model()))
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == {"code": "invalid_document", "message": FIXED}
    assert body["client_revision"] == 4 and body["request_seq"] == 9
    assert_hidden(response.text)
    assert_logged(log)
    assert_idle(server._thermal_jobs)


@pytest.mark.parametrize("kind", ["steady", "transient"])
@pytest.mark.parametrize("route", ["validate", "run"])
def test_rectangle_document_reading_hides_an_unexpected_failure_and_keeps_a_refusal(client, monkeypatch, log,
                                                                                  kind, route):
    path, model = ROUTES[kind]
    status = 200 if route == "validate" else 400
    with monkeypatch.context() as patch:
        patch.setattr(thermal, "Document", type("Broken", (), {"from_dict": raising(HiddenTypeFailure(MARKER))}))
        response = client.post(path+route, json=envelope(model()))
    assert response.status_code == status
    assert response.json()["error"] == {"code": "invalid_document", "message": FIXED}
    assert_hidden(response.text, "HiddenTypeFailure")
    assert_logged(log, "HiddenTypeFailure")
    doc = model()
    doc["physics"]["heat1"]["thermal_conductivity"] = "2 W/(m furlong)"
    with pytest.raises(DocumentError) as refused:
        Document.from_dict(copy.deepcopy(doc))
    response = client.post(path+route, json=envelope(doc))
    assert response.status_code == status
    assert response.json()["error"] == {"code": "invalid_document",
                                        "message": thermal.limited_text(str(refused.value), 1024)}


@pytest.mark.parametrize("kind", ["steady", "transient"])
def test_run_request_hides_an_unexpected_failure_before_its_job(client, monkeypatch, log, kind):
    route, model = ROUTES[kind]

    async def broken(*args, **kwargs):
        raise HiddenFailure(MARKER)
    monkeypatch.setattr(thermal if kind == "steady" else transient, "read_request", broken)
    response = client.post(route+"run", json=envelope(model()))
    assert response.status_code == 400
    assert response.json()["error"] == {"code": "invalid_document", "message": FIXED}
    assert_hidden(response.text)
    assert_logged(log, count=1)
    assert not server._thermal_jobs._records
    assert_idle(server._thermal_jobs)


@pytest.mark.parametrize("kind", ["steady", "transient", "region"])
def test_thread_start_failure_hides_its_text_in_reply_and_job(client, monkeypatch, log, kind):
    route, model = ROUTES[kind]
    monkeypatch.setattr(server, "_start_thermal_thread", raising(HiddenFailure(MARKER)))
    response = client.post(route+"run", json=envelope(model()))
    assert response.status_code == 500
    body = response.json()
    assert body["error"] == {"code": "thread_start_failed", "message": FIXED}
    assert body["job"].startswith("thermal-") and body["client_revision"] == 4
    assert_hidden(response.text)
    status = client.get("/api/jobs/"+body["job"])
    assert status.status_code == 200
    assert status.json()["status"] == "error" and status.json()["has_result"] is False
    assert status.json()["error"] == {"code": "thread_start_failed", "message": FIXED}
    assert_hidden(status.text)
    assert_logged(log, count=1)      # one record for the job and the reply
    assert_idle(server._thermal_jobs)


# -- thermal jobs ---------------------------------------------------------------------------------

def finished(client, kind):
    route, model = ROUTES[kind]
    response = client.post(route+"run", json=envelope(model()))
    assert response.status_code == 200, response.text
    status = client.get("/api/jobs/"+response.json()["job"])
    assert status.status_code == 200
    return status


@pytest.mark.parametrize("kind", ["steady", "transient", "region"])
def test_job_failure_hides_an_unexpected_failure_and_keeps_a_refusal(client, monkeypatch, log, kind):
    monkeypatch.setattr(server, "run", raising(HiddenFailure(MARKER)))
    status = finished(client, kind)
    assert status.json()["status"] == "error" and status.json()["has_result"] is False
    assert status.json()["error"] == {"code": "solver_failed", "message": FIXED}
    assert_hidden(status.text)
    assert_logged(log, count=1)
    assert_idle(server._thermal_jobs)
    if kind == "region":    # a limit refusal of the region run keeps its words
        refusal = MeshLimitError("nodes", 10201, 10500)
        expected = {"code": "mesh_limit_exceeded", "message": str(refusal)}
    else:                   # a document refusal of the run keeps its type and words
        refusal = DocumentError("physics.heat1: a stage refusal written for the user", path="physics.heat1")
        expected = {"code": "solver_failed", "message": f"DocumentError: {refusal}"}
    monkeypatch.setattr(server, "run", raising(refusal))
    assert finished(client, kind).json()["error"] == expected


def test_result_capture_failure_hides_an_unexpected_failure(client, monkeypatch, log):
    monkeypatch.setattr(thermal, "capture_result", raising(HiddenFailure(MARKER)))
    status = finished(client, "steady")
    assert status.json()["error"] == {"code": "invalid_result", "message": FIXED}
    assert_hidden(status.text)
    assert_logged(log, count=1)


# -- region validation ----------------------------------------------------------------------------

@pytest.mark.parametrize("stage", ["Document.from_dict", "after reading"])
@pytest.mark.parametrize("route", ["validate", "run"])
def test_region_validation_hides_an_unexpected_failure_and_keeps_a_refusal(client, monkeypatch, log, stage, route):
    if stage == "Document.from_dict":
        monkeypatch.setattr(regions, "Document", type("Broken", (), {"from_dict": raising(HiddenTypeFailure(MARKER))}))
        name = "HiddenTypeFailure"
    else:
        monkeypatch.setattr(regions, "check_mesh_limits", raising(HiddenFailure(MARKER)))
        name = "HiddenFailure"
    status = 200 if route == "validate" else 400
    response = client.post("/api/thermal/"+route, json=envelope(fx.steady_example()))
    assert response.status_code == status
    assert response.json()["error"] == {"code": "invalid_document", "message": FIXED}
    assert_hidden(response.text, name)
    assert_logged(log, name)
    assert not server._thermal_jobs._records
    refusal = DocumentError("geometry.shapes[0]: a refusal written for the user", path="geometry.shapes[0]")
    if stage == "Document.from_dict":
        monkeypatch.setattr(regions, "Document", type("Refusing", (), {"from_dict": raising(refusal)}))
    else:
        monkeypatch.setattr(regions, "check_mesh_limits", raising(refusal))
    response = client.post("/api/thermal/"+route, json=envelope(fx.steady_example()))
    assert response.status_code == status
    assert response.json()["error"] == {"code": "invalid_document", "message": str(refusal)}


# -- transient views ------------------------------------------------------------------------------

@pytest.mark.parametrize("view", ["frame", "history"])
def test_transient_view_hides_an_unexpected_failure_and_keeps_a_query_refusal(client, monkeypatch, log, view):
    response = client.post("/api/thermal/transient/run", json=envelope(transient_model()))
    assert response.status_code == 200, response.text
    identity = response.json()
    assert client.get("/api/jobs/"+identity["job"]).json()["status"] == "done"
    query = {"result_id": identity["result_id"], "field": "temperature", "frame_seq": 1,
             **({"start": 0, "stop": 2} if view == "history" else {"time_index": 1})}
    url = "/api/jobs/"+identity["job"]+"/"+view
    with monkeypatch.context() as patch:
        patch.setattr(transient, "encode_view", raising(HiddenFailure(MARKER)))
        failed = client.get(url, params=query)
    assert failed.status_code == 500
    body = failed.json()
    assert body["error"] == {"code": "view_failed", "message": FIXED}
    assert body["job"] == identity["job"] and body["kind"] == transient.KIND
    assert_hidden(failed.text)
    assert_logged(log, count=1)
    refused = client.get(url, params={**query, "extra": 1})
    assert refused.status_code == 400
    assert refused.json()["error"] == {"code": "invalid_query", "message": "unexpected, missing or duplicate query"}


# -- meshine's explanations -------------------------------------------------------------------

def meshine_refusal(kind):
    """``(mesher, message)``: a stand-in for meshing that has meshine itself refuse an input, a
    boundary point the triangulation cannot resolve (``MeshingError``, the off-edge vertex of
    tests/meshine) or a domain without regions (``MeshInputError``), and that refusal's text."""
    from meshine import Domain, generate, rectangle

    def mesher(*args, **kwargs):
        d = Domain(size=0.2)
        if kind == "MeshingError":
            d.add_region("lower", rectangle(0, 0, 2, 1))
            d.add_region("upper", [(0, 1), (2, 1), (2, 2), (1, 2), (1, 1 + 4e-8), (0.9, 2), (0, 2)])
        generate(d)
    with pytest.raises(Exception) as caught:
        mesher()
    assert type(caught.value).__name__ == kind, repr(caught.value)
    return mesher, str(caught.value)


@pytest.mark.parametrize("kind", ["MeshingError", "MeshInputError"])
def test_mesh_preview_shows_meshine_s_explanation_and_hides_a_plain_runtime_error(client, monkeypatch, log, kind):
    mesher, message = meshine_refusal(kind)
    monkeypatch.setattr(server, "build_mesh", mesher)
    response = client.post("/api/mesh", json={"doc": OPTICAL})
    assert response.status_code == 400 and response.json() == {"detail": message}
    monkeypatch.setattr(server, "build_mesh", raising(RuntimeError(MARKER)))
    response = client.post("/api/mesh", json={"doc": OPTICAL})
    assert response.status_code == 400 and response.json() == {"detail": FIXED}
    assert_hidden(response.text, "RuntimeError")
    assert_logged(log, "RuntimeError", count=1)


@pytest.mark.parametrize("kind", ["MeshingError", "MeshInputError"])
def test_heat_job_shows_meshine_s_explanation_and_hides_a_plain_runtime_error(client, monkeypatch, log, kind):
    mesher, message = meshine_refusal(kind)
    monkeypatch.setattr(server, "run", mesher)
    status = finished(client, "region")
    bound = server._thermal_jobs.limits.error_bytes//8      # the job error's text bound, as before
    expected = thermal.limited_text(f"{kind}: "+thermal.limited_text(message, bound), bound)
    assert status.json()["error"] == {"code": "solver_failed", "message": expected}
    assert not log.records
    monkeypatch.setattr(server, "run", raising(RuntimeError(MARKER)))
    status = finished(client, "region")
    assert status.json()["error"] == {"code": "solver_failed", "message": FIXED}
    assert_hidden(status.text, "RuntimeError")
    assert_logged(log, "RuntimeError", count=1)
    assert_idle(server._thermal_jobs)
