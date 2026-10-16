# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Producer regression coverage for shared thermal admission and transport pins."""
from dataclasses import replace
import pytest
from simcase.studio import thermal_api as thermal


def attached(jobs, job="thermal-one"):
    lease = jobs.reserve()
    jobs.attach(lease, job, "result-one", thermal.ThermalInput(None, 1, 2))
    return lease


def test_ingress_permit_is_nonblocking_and_old_release_is_harmless():
    gate = thermal.AdmissionGate("ingress_capacity_exceeded")
    first = gate.acquire()
    with pytest.raises(thermal.ThermalAPIError) as error:
        gate.acquire()
    assert error.value.status == 429
    first.release()
    second = gate.acquire()
    first.release()
    with pytest.raises(thermal.ThermalAPIError):
        gate.acquire()
    second.release()


def test_running_status_snapshot_stays_pinned_when_terminal_replaces_status():
    jobs = thermal.ThermalJobs()
    lease = attached(jobs)
    pin = jobs.pin("thermal-one")
    original = pin.payload
    assert b'"running"' in original
    assert sum(len(s["payload"]) for s in jobs._snapshots.values()) == len(original)
    jobs.complete(lease, b"{}", [])
    jobs.release(lease)
    assert b'"done"' in jobs.status("thermal-one")
    assert pin.payload == original
    assert sum(len(s["payload"]) for s in jobs._snapshots.values()) == len(original)
    pin.release()
    pin.release()
    assert not jobs._snapshots


def test_evicted_terminal_pin_retains_byte_charge_until_reader_release():
    jobs = thermal.ThermalJobs()
    lease = attached(jobs)
    jobs.complete(lease, b"{}", [])
    jobs.release(lease)
    pin = jobs.pin("thermal-one", result=True)
    size = jobs._record_bytes(pin.record)
    with jobs._lock:
        jobs._discard("thermal-one")
    assert not jobs._records
    assert jobs._retained_bytes() == size
    assert pin.payload == b"{}"
    pin.release()
    assert jobs._retained_bytes() == 0


def test_pinned_bytes_can_prevent_new_admission_without_early_release():
    limits = replace(thermal.ThermalLimits(), terminal_bytes=thermal.ThermalLimits().payload_bytes
                     + thermal.ThermalLimits().status_bytes, terminal_jobs=2)
    jobs = thermal.ThermalJobs(limits)
    lease = attached(jobs)
    jobs.complete(lease, b"x"*limits.payload_bytes, [])
    jobs.release(lease)
    pin = jobs.pin("thermal-one", result=True)
    with pytest.raises(thermal.ThermalAPIError) as error:
        jobs.reserve()
    assert error.value.status == 429
    assert jobs._retained_bytes() > 0
    pin.release()
    next_lease = jobs.reserve()
    jobs.release(next_lease)
    assert jobs._active == jobs._pending == jobs._reserved_bytes == 0


def test_running_pins_deduplicate_backing_and_current_status_is_reserved():
    jobs = thermal.ThermalJobs()
    lease = attached(jobs)
    one = jobs.pin("thermal-one")
    two = jobs.pin("thermal-one")
    assert one.payload is two.payload
    assert len(jobs._snapshots) == 1
    assert next(iter(jobs._snapshots.values()))["refs"] == 2
    assert jobs._retained_bytes() == 0
    old_size = len(one.payload)
    jobs.complete(lease, b"{}", [])
    jobs.release(lease)
    terminal_size = jobs._record_bytes(jobs._records["thermal-one"])
    assert jobs._retained_bytes() == terminal_size+old_size
    one.release()
    assert one.payload is None and one.record is None
    assert jobs._retained_bytes() == terminal_size+old_size
    two.release()
    assert jobs._retained_bytes() == terminal_size


def test_released_terminal_pin_drops_its_strong_payload_and_record_references():
    jobs = thermal.ThermalJobs()
    lease = attached(jobs)
    jobs.complete(lease, b"{}", [])
    jobs.release(lease)
    pin = jobs.pin("thermal-one", result=True)
    jobs._discard("thermal-one")
    pin.release()
    assert pin.payload is pin.record is pin.jobs is None
    assert not jobs._retired


# Public HTTP tests below require the ordinary configured simcase test environment.
import asyncio
import json
import numpy as np
from fastapi.testclient import TestClient
from simcase.studio import server
from simcase.studio import transient_thermal_api as transient


def transient_model():
    return {"openphysics": "0.2", "name": "Transient server control",
            "units": {"length": "m", "temperature": "K", "time": "s"},
            "geometry": {"domain": {"xmin": 0., "xmax": 1., "ymin": 0., "ymax": 1.}},
            "materials": {}, "physics": {"heat1": {"type": "thermal.transient2d",
                "conductivity_w_mk": 2., "volumetric_heat_capacity_j_m3k": 4.,
                "initial_temperature_k": 300., "dirichlet_temperature_k": {},
                "heat_source_w_m3": 8.}},
            "mesh": {"subdivisions": [2, 2]}, "study": {"type": "transient", "time_s": [2., 3.]},
            "results": {"save_fields": True, "plots": False}}


def request_body(data=None):
    return {"doc": transient_model() if data is None else data, "client_revision": 7, "request_seq": 11}


@pytest.fixture
def http_client(monkeypatch):
    monkeypatch.setattr(server, "_thermal_jobs", thermal.ThermalJobs())
    monkeypatch.setattr(server, "_start_thermal_thread", lambda target, args: target(*args))
    with TestClient(server.app) as client:
        yield client


def accepted_job(client):
    response = client.post("/api/thermal/transient/run", json=request_body())
    assert response.status_code == 200, response.text
    accepted = response.json()
    state = client.get("/api/jobs/"+accepted["job"]).json()
    assert state["status"] == "done", state
    return accepted


def test_public_transient_uniform_run_manifest_frame_history_and_initial_rate(http_client):
    response = http_client.post("/api/thermal/transient/validate", json=request_body())
    assert response.status_code == 200 and response.json()["ok"]
    identity = accepted_job(http_client)
    manifest = http_client.get("/api/jobs/"+identity["job"]+"/result").json()
    assert manifest["payload_format"] == transient.MANIFEST
    assert manifest["time_s"] == [2., 3.] and manifest["default_frame_index"] == 1
    assert len(manifest["fields"]) == 13
    assert manifest["arrays"]["dirichlet_node_ids"] == []
    url = "/api/jobs/"+identity["job"]
    query = {"result_id": identity["result_id"], "field": "temperature_k",
             "time_index": 1, "frame_seq": 3}
    frame = http_client.get(url+"/frame", params=query)
    assert frame.status_code == 200, frame.text
    data = frame.json()
    np.testing.assert_allclose(data["arrays"]["temperature_k"], 302., atol=1e-9, rtol=0)
    assert data["client_revision"] == 7 and data["request_seq"] == 11 and data["frame_seq"] == 3
    assert data["time_s"] == 3. and data["shape"] == [9]
    assert http_client.get(url+"/frame", params=query).content == frame.content
    history = http_client.get(url+"/history", params={"result_id": identity["result_id"],
        "field": "heat_content_j_per_m", "start": 0, "stop": 2, "frame_seq": 4})
    assert history.status_code == 200, history.text
    assert history.json()["time_s"] == [2., 3.]
    np.testing.assert_allclose(history.json()["arrays"]["heat_content_j_per_m"],
                               [1200., 1208.], atol=1e-8, rtol=0)
    query.update(field="storage_rate_w_per_m", time_index=0)
    refusal = http_client.get(url+"/frame", params=query)
    assert refusal.status_code == 422
    assert refusal.json()["error"]["code"] == "unavailable_initial_rate"
    query["time_index"] = 1
    rate = http_client.get(url+"/frame", params=query)
    assert rate.status_code == 200
    assert rate.json()["interval_start_s"] == 2. and rate.json()["interval_end_s"] == 3.


@pytest.mark.parametrize("route,status", [("validate", 200), ("run", 400)])
def test_transient_invalid_document_status_has_no_job(http_client, route, status):
    model = transient_model()
    model["mesh"]["subdivisions"] = [True, 2]
    response = http_client.post("/api/thermal/transient/"+route, json=request_body(model))
    assert response.status_code == status
    assert response.json()["ok"] is False
    assert not server._thermal_jobs._records


@pytest.mark.parametrize("fault", ["missing", "duplicate", "fractional", "stale", "range"])
def test_transient_query_identity_and_integer_negatives(http_client, fault):
    identity = accepted_job(http_client)
    query = {"result_id": identity["result_id"], "field": "temperature_k",
             "time_index": 1, "frame_seq": 1}
    expected = 400
    if fault == "missing": del query["result_id"]
    elif fault == "fractional": query["time_index"] = .5
    elif fault == "stale": query["result_id"] = "result-different"; expected = 409
    elif fault == "range": query["time_index"] = 2; expected = 422
    if fault == "duplicate":
        query = list(query.items())+[("time_index", 0)]
    response = http_client.get("/api/jobs/"+identity["job"]+"/frame", params=query)
    assert response.status_code == expected, response.text
    assert server._thermal_jobs.read_encoder._token is None
    assert server._thermal_jobs._read_workspace == 0


def test_read_workspace_transfers_to_bytes_and_cleans_on_send_cancel():
    jobs = thermal.ThermalJobs()
    allocation = jobs.begin_read(1024)
    assert jobs._retained_bytes() == 1024
    allocation.publish(b"view")
    assert jobs._retained_bytes() == 4
    response = server.ThermalResponse(allocation.payload, allocation)
    async def exercise():
        async def receive(): return {"type": "http.disconnect"}
        async def send(message): raise asyncio.CancelledError()
        with pytest.raises(asyncio.CancelledError):
            await response({"type": "http"}, receive, send)
    asyncio.run(exercise())
    assert response.body == b"" and response._leases == ()
    assert allocation.payload is None and jobs._retained_bytes() == 0
    assert jobs.read_encoder._token is None


def test_response_construction_failure_releases_pins(monkeypatch):
    jobs = thermal.ThermalJobs()
    lease = attached(jobs)
    jobs.complete(lease, b"{}", [])
    jobs.release(lease)
    pin = jobs.pin("thermal-one", result=True)
    def broken(*args, **kwargs): raise RuntimeError("response construction failure")
    monkeypatch.setattr(server.Response, "__init__", broken)
    with pytest.raises(RuntimeError, match="construction"):
        server.ThermalResponse(pin.payload, pin)
    assert pin.released and pin.payload is pin.record is None


def test_read_slot_blocks_other_encoding_until_send_finishes():
    jobs = thermal.ThermalJobs()
    first = jobs.begin_read(1024)
    first.publish(b"view")
    with pytest.raises(thermal.ThermalAPIError) as error:
        jobs.begin_read(1024)
    assert error.value.status == 429
    first.release()
    second = jobs.begin_read(1024)
    second.release()
    assert jobs._read_workspace == 0


def test_ingress_shared_cross_route_and_cancel_release(monkeypatch):
    jobs = thermal.ThermalJobs()
    monkeypatch.setattr(server, "_thermal_jobs", jobs)
    class HeldBody:
        headers = {"content-type": "application/json"}
        def __init__(self, entered, resume): self.entered, self.resume = entered, resume
        async def stream(self):
            self.entered.set()
            await self.resume.wait()
            yield json.dumps(request_body()).encode()
    async def exercise():
        entered, resume = asyncio.Event(), asyncio.Event()
        first = asyncio.create_task(server.validate_transient(HeldBody(entered, resume)))
        await entered.wait()
        rejected = await server.validate_thermal(HeldBody(entered, resume))
        assert rejected.status_code == 429
        first.cancel()
        with pytest.raises(asyncio.CancelledError): await first
        assert jobs.ingress._token is None
    asyncio.run(exercise())
