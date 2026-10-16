# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Independent thermal HTTP ingress and deterministic lifecycle test fixtures.

The request limit is the proposed policy, not a measured memory guarantee.
No solver is substituted for numerical acceptance. ASGI is not a browser.
"""

import asyncio
import copy
import json
from dataclasses import replace
from types import SimpleNamespace

from fastapi.testclient import TestClient
from dataclasses import dataclass, field

import pytest

from simcase.studio import server


# Initial accepted design proposal; align with the published capabilities before
# integration. Equality is intentionally tested separately from overflow.
REQUEST_LIMIT = 1024 * 1024
ROUTES = ("/api/thermal/validate", "/api/thermal/run")


@dataclass
class Clock:
    now: float = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        assert seconds >= 0
        self.now += seconds


@dataclass
class ThreadGate:
    """A deterministic thread factory; no daemon, sleep, or process is started."""

    failure: str | None = None
    pending: list = field(default_factory=list)
    starts: int = 0

    def __call__(self, *, target, args=(), kwargs=None, daemon=None, **options):
        if self.failure == "construct":
            raise RuntimeError("injected thread construction failure")
        gate = self

        class Thread:
            def start(self):
                gate.starts += 1
                if gate.failure == "start":
                    raise RuntimeError("injected thread start failure")
                gate.pending.append(lambda: target(*args, **(kwargs or {})))

        return Thread()

    def finish_one(self):
        assert self.pending, "no queued worker"
        return self.pending.pop(0)()


@dataclass
class Exchange:
    chunks: list[bytes]
    headers: list[tuple[bytes, bytes]] = field(default_factory=list)
    reads: int = 0
    messages: list = field(default_factory=list)

    async def invoke(self, app, path):
        async def receive():
            # Reading after the supplied body is a test failure, rather than a
            # fabricated disconnect that could conceal an unbounded body read.
            assert self.reads < len(self.chunks), "application read past request body"
            index = self.reads
            self.reads += 1
            return {"type": "http.request", "body": self.chunks[index],
                    "more_body": self.reads < len(self.chunks)}

        async def send(message):
            self.messages.append(copy.deepcopy(message))

        scope = {
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": "POST", "scheme": "http",
            "path": path, "raw_path": path.encode("ascii"), "root_path": "",
            "query_string": b"", "headers": [(b"content-type", b"application/json"), *self.headers],
            "client": ("127.0.0.1", 12345), "server": ("testserver", 80),
        }
        await app(scope, receive, send)
        starts = [m for m in self.messages if m["type"] == "http.response.start"]
        assert len(starts) == 1
        body = b"".join(m.get("body", b"") for m in self.messages
                        if m["type"] == "http.response.body")
        return starts[0]["status"], body

    def request(self, path):
        return asyncio.run(self.invoke(server.app, path))


@pytest.fixture
def no_execution(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("invalid thermal request reached public solver")

    monkeypatch.setattr(server, "run", forbidden)
    monkeypatch.setattr(server, "_start_thermal_thread", forbidden)
    monkeypatch.setattr(server, "uuid", SimpleNamespace(uuid4=forbidden))
    jobs = server.thermal.ThermalJobs()
    monkeypatch.setattr(server, "_thermal_jobs", jobs)
    with server._jobs_lock:
        before = copy.deepcopy(server._jobs)
    yield calls
    assert calls == []
    assert not jobs._records
    assert (jobs._active, jobs._pending, jobs._reserved_bytes) == (0, 0, 0)
    with server._jobs_lock:
        assert server._jobs == before, "invalid input changed existing jobs"


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("raw", [
    b"", b"{", b"[]", b"null", b'{"doc":',
    b'{"doc":{},"doc":{}}',
    b'{"doc":{"name":NaN}}',
    b'{"doc":{"name":Infinity}}',
    b'{"doc":{"name":"\\xff"}}'.replace(b"\\xff", b"\xff"),
])
def test_thermal_malformed_stream_never_allocates_or_runs(route, raw, no_execution):
    exchange = Exchange([raw])
    status, body = exchange.request(route)
    assert status == 400, (status, body)
    assert exchange.reads == 1


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("delta,expected", [(-1, 400), (0, 400), (1, 413)])
def test_thermal_request_exact_byte_boundary(route, delta, expected, no_execution):
    # Whitespace is invalid JSON but its byte length is exact: cap-equal reaches
    # decoding and fails400; cap+1 must fail413 before JSON parsing.
    raw = b" " * (REQUEST_LIMIT + delta)
    exchange = Exchange([raw])
    status, body = exchange.request(route)
    assert status == expected, (status, body)


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("declared", [None, b"0", b"1"])
def test_thermal_stream_overflow_ignores_forged_small_length(route, declared, no_execution):
    headers = [] if declared is None else [(b"content-length", declared)]
    # A tail that must remain unread distinguishes bounded streaming from
    # reading an unbounded request and checking len only afterward.
    exchange = Exchange([b" " * REQUEST_LIMIT, b" ", b"unread tail"], headers)
    status, body = exchange.request(route)
    assert status == 413, (status, body)
    assert exchange.reads == 2, "server consumed data after crossing the byte cap"


def test_lifecycle_fixture_clock_and_thread_are_explicit():
    clock = Clock(10.0)
    gate = ThreadGate()
    observed = []
    gate(target=lambda: observed.append(clock())).start()
    assert gate.starts == 1 and observed == []
    clock.advance(300.0)
    gate.finish_one()
    assert observed == [310.0] and not gate.pending


@pytest.mark.parametrize("stage", ["construct", "start"])
def test_lifecycle_thread_fixture_failure_is_not_worker_completion(stage):
    gate = ThreadGate(failure=stage)
    with pytest.raises(RuntimeError, match="injected thread"):
        gate(target=lambda: pytest.fail("worker must not execute")).start()
    assert not gate.pending
    assert gate.starts == (0 if stage == "construct" else 1)


def steady_model():
    return {
        "openphysics": "0.2", "name": "Thermal lifecycle \\u0394",
        "units": {"length": "m", "temperature": "K"},
        "geometry": {"domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}},
        "materials": {}, "physics": {"heat1": {
            "type": "thermal.steady2d", "conductivity_w_mk": 2,
            "heat_source_w_m3": 0, "dirichlet_temperature_k": {"left": 300, "right": 293}}},
        "mesh": {"subdivisions": [2, 2]}, "study": {"type": "single"},
        "results": {"save_fields": True, "plots": False},
    }


@pytest.fixture
def lifecycle(monkeypatch):
    thermal = server.thermal
    clock, gate = Clock(), ThreadGate()
    limits = replace(thermal.ThermalLimits(), payload_bytes=16384, status_bytes=4096,
                     terminal_bytes=40960, metadata_bytes=8192,
                     log_bytes=512, error_bytes=512)
    jobs = thermal.ThermalJobs(limits=limits, clock=clock)
    monkeypatch.setattr(server, "_thermal_jobs", jobs)
    monkeypatch.setattr(server, "_start_thermal_thread",
                        lambda target, args: gate(target=target, args=args).start())
    with server._jobs_lock:
        optical_before = copy.deepcopy(server._jobs)
    releases = []
    release = jobs.release

    def tracked(lease):
        releases.append(lease)
        return release(lease)

    monkeypatch.setattr(jobs, "release", tracked)
    with TestClient(server.app) as client:
        yield SimpleNamespace(client=client, jobs=jobs, clock=clock, gate=gate,
                              releases=releases, release=release, thermal=thermal)
    assert not gate.pending, "test left an uncompleted controlled worker"
    assert (jobs._active, jobs._pending, jobs._reserved_bytes) == (0, 0, 0)
    with server._jobs_lock:
        assert server._jobs == optical_before, "thermal lifecycle changed optical jobs"


def submit(life, seq=1):
    return life.client.post("/api/thermal/run", json={
        "doc": steady_model(), "client_revision": 7, "request_seq": seq})


def assert_released_once(life):
    assert len(life.releases) == 1
    lease = life.releases[0]
    assert lease.released
    assert (life.jobs._active, life.jobs._pending, life.jobs._reserved_bytes) == (0, 0, 0)
    # Idempotence must not drive accounting negative or create spare capacity.
    life.release(lease)
    assert (life.jobs._active, life.jobs._pending, life.jobs._reserved_bytes) == (0, 0, 0)


@pytest.mark.parametrize("stage", [
    "thread-construct", "thread-start", "run", "capture", "publication", "status-encode",
])
def test_thermal_failure_releases_reservation_once(lifecycle, monkeypatch, stage):
    life = lifecycle

    def broken(*args, **kwargs):
        raise RuntimeError("injected lifecycle failure " + stage)

    if stage.startswith("thread-"):
        life.gate.failure = stage.removeprefix("thread-")
        response = submit(life)
        assert response.status_code == 500
    else:
        response = submit(life)
        assert response.status_code == 200, response.text
        with monkeypatch.context() as fault:
            if stage == "run":
                fault.setattr(server, "run", broken)
            elif stage == "capture":
                fault.setattr(life.thermal, "capture_result", broken)
            elif stage == "publication":
                fault.setattr(life.jobs, "complete", broken)
            else:
                fault.setattr(life.thermal, "encode_json", broken)
            life.gate.finish_one()
        result = life.client.get("/api/jobs/" + response.json()["job"] + "/result")
        assert result.status_code in (404, 409), result.text
    assert_released_once(life)
    life.gate.failure = None
    # A fresh job after any failed stage must be admitted immediately.
    next_response = submit(life, seq=2)
    assert next_response.status_code == 200, next_response.text
    life.gate.finish_one()
    assert life.client.get("/api/jobs/" + next_response.json()["job"] + "/result").status_code == 200
    assert len(life.releases) == 2


def test_thermal_success_cached_bytes_and_fixed_top_level_wire(lifecycle, monkeypatch):
    life = lifecycle
    response = submit(life)
    assert response.status_code == 200, response.text
    identity = response.json()
    life.gate.finish_one()
    assert_released_once(life)
    url = "/api/jobs/" + identity["job"] + "/result"
    first = life.client.get(url)
    assert first.status_code == 200
    payload = first.json()
    assert payload["display_length_in_m"] == 1.0
    assert "coordinates" not in payload
    assert set(payload) == {
        "payload_format", "kind", "job", "result_id", "client_revision", "request_seq",
        "result_format", "field_layout", "display_length_in_m", "summary", "arrays"}
    for key, value in identity.items():
        assert payload[key] == value

    def forbidden(*args, **kwargs):
        raise AssertionError("cached read reran or reserialized the result")

    with monkeypatch.context() as fault:
        fault.setattr(server, "run", forbidden)
        fault.setattr(life.thermal, "capture_result", forbidden)
        fault.setattr(life.thermal, "encode_json", forbidden)
        for _ in range(4):
            again = life.client.get(url)
            assert again.status_code == 200 and again.content == first.content
            assert life.client.get("/api/jobs/" + identity["job"]).status_code == 200


def test_thermal_third_run_evicts_oldest_terminal_without_five_minute_block(lifecycle):
    life = lifecycle
    ids = []
    for seq in range(1, 5):
        response = submit(life, seq)
        assert response.status_code == 200, response.text
        ids.append(response.json()["job"])
        life.gate.finish_one()
        assert len(life.jobs._records) <= life.jobs.limits.terminal_jobs
        assert life.jobs._retained_bytes() <= life.jobs.limits.terminal_bytes
    assert life.clock() == 0  # No TTL wait is needed to make capacity.
    for job in ids[:-2]:
        assert life.client.get("/api/jobs/" + job + "/result").status_code == 404
    for job in ids[-2:]:
        assert life.client.get("/api/jobs/" + job + "/result").status_code == 200


def test_thermal_ttl_is_maximum_and_active_job_survives(lifecycle):
    life = lifecycle
    first = submit(life).json()["job"]
    life.gate.finish_one()
    life.clock.advance(life.jobs.limits.ttl_seconds - 0.5)
    assert life.client.get("/api/jobs/" + first + "/result").status_code == 200
    second_response = submit(life, 2)
    assert second_response.status_code == 200
    second = second_response.json()["job"]
    life.clock.advance(0.5)
    assert life.client.get("/api/jobs/" + first + "/result").status_code == 404
    life.clock.advance(1000)
    status = life.client.get("/api/jobs/" + second)
    assert status.status_code == 200 and status.json()["status"] == "running"
    assert life.client.get("/api/jobs/" + second + "/result").status_code == 409
    blocked = submit(life, 3)
    assert blocked.status_code == 429
    assert life.gate.starts == 2
    life.gate.finish_one()
    assert life.client.get("/api/jobs/" + second + "/result").status_code == 200


@pytest.mark.parametrize("terminal", ["done", "error"])
def test_thermal_cache_byte_pressure_evicts_terminal_and_never_active(lifecycle, terminal):
    life = lifecycle
    jobs = life.jobs
    # Large terminal data forces byte-pressure eviction independently of count.
    jobs.limits = replace(jobs.limits, terminal_jobs=10,
                          terminal_bytes=jobs.limits.payload_bytes + jobs.limits.status_bytes + 100)
    spec = life.thermal.ThermalInput(None, 1, 1)
    first = jobs.reserve()
    jobs.attach(first, "thermal-old", "result-old", spec)
    if terminal == "done":
        jobs.complete(first, b"x" * jobs.limits.payload_bytes, ["log" * 1000])
    else:
        jobs.fail(first, RuntimeError("failure" * 10000))
    jobs.release(first)
    second = jobs.reserve()
    with pytest.raises(life.thermal.ThermalAPIError) as expired:
        jobs.status("thermal-old")
    assert expired.value.status == 404
    jobs.attach(second, "thermal-active", "result-active", spec)
    # active_jobs=1: no terminal eviction may turn this into a second active slot.
    with pytest.raises(life.thermal.ThermalAPIError) as error:
        jobs.reserve()
    assert error.value.status == 429
    assert jobs.status("thermal-active")
    jobs.fail(second, RuntimeError("stop"))
    jobs.release(second)
    third = jobs.reserve()
    jobs.attach(third, "thermal-next", "result-next", spec)
    jobs.fail(third, RuntimeError("stop"))
    jobs.release(third)
    assert jobs._retained_bytes() <= jobs.limits.terminal_bytes


def test_thermal_error_log_and_status_metadata_stay_bounded(lifecycle):
    life = lifecycle
    jobs = life.jobs
    spec = life.thermal.ThermalInput(None, 1, 1)
    for index in range(8):
        lease = jobs.reserve()
        job = "thermal-bounded-" + str(index)
        jobs.attach(lease, job, "result-" + str(index), spec)
        if index % 2:
            jobs.fail(lease, RuntimeError("\\u0394" * 50000))
        else:
            jobs.complete(lease, b"{}", ["\\u0394" * 10000] * 100)
        jobs.release(lease)
        encoded = jobs.status(job)
        status = json.loads(encoded)
        assert len(encoded) <= jobs.limits.status_bytes
        assert len(json.dumps(status["log"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")) <= jobs.limits.log_bytes
        if status["error"] is not None:
            assert len(json.dumps(status["error"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")) <= jobs.limits.error_bytes
        assert set(status) == {
            "kind", "job", "result_id", "client_revision", "request_seq",
            "status", "log", "error", "has_result"}
        assert len(jobs._records) <= jobs.limits.terminal_jobs
        assert jobs._retained_bytes() <= jobs.limits.terminal_bytes


def test_thermal_capability_enabled_does_not_claim_measured_capacity(lifecycle):
    response = lifecycle.client.get("/api/capabilities")
    assert response.status_code == 200
    capability = response.json()["thermal.steady2d"]
    assert capability["run_enabled"] is True
    assert capability["resource_policy"] == "candidate-unmeasured"


@pytest.mark.parametrize("budget", ["metadata_bytes", "payload_bytes"])
def test_thermal_encoding_budget_failure_has_no_result_and_releases(lifecycle, budget):
    life = lifecycle
    life.jobs.limits = replace(life.jobs.limits, **{budget: 128})
    response = submit(life)
    assert response.status_code == 200, response.text
    life.gate.finish_one()
    job = response.json()["job"]
    status = life.client.get("/api/jobs/" + job)
    assert status.status_code == 200 and status.json()["status"] == "error"
    assert status.json()["has_result"] is False
    assert life.client.get("/api/jobs/" + job + "/result").status_code == 409
    assert_released_once(life)


@pytest.mark.parametrize("stage", ["uuid", "attach"])
def test_thermal_reserved_admission_failure_releases_pending_once(lifecycle, monkeypatch, stage):
    life = lifecycle

    def broken(*args, **kwargs):
        raise RuntimeError("injected reserved admission " + stage)

    with monkeypatch.context() as fault:
        if stage == "uuid":
            fault.setattr(server, "uuid", SimpleNamespace(uuid4=broken))
        else:
            fault.setattr(life.jobs, "attach", broken)
        response = submit(life)
    assert response.status_code == 500
    assert life.gate.starts == 0 and not life.jobs._records
    assert_released_once(life)
    response = submit(life, 2)
    assert response.status_code == 200
    life.gate.finish_one()
    assert life.client.get("/api/jobs/" + response.json()["job"] + "/result").status_code == 200


def test_thermal_failed_success_and_error_publication_still_release(lifecycle, monkeypatch):
    life = lifecycle
    response = submit(life)
    assert response.status_code == 200

    def broken(*args, **kwargs):
        raise RuntimeError("injected publication failure")

    with monkeypatch.context() as fault:
        fault.setattr(life.jobs, "complete", broken)
        fault.setattr(life.jobs, "fail", broken)
        life.gate.finish_one()
    assert_released_once(life)
    status = life.client.get("/api/jobs/" + response.json()["job"])
    assert status.status_code == 200 and status.json()["status"] == "error"
    assert status.json()["has_result"] is False
    assert life.client.get("/api/jobs/" + response.json()["job"] + "/result").status_code == 409
    following = submit(life, 2)
    assert following.status_code == 200
    life.gate.finish_one()


def test_thermal_double_release_cannot_release_a_different_active_lease(lifecycle):
    life = lifecycle
    jobs = life.jobs
    spec = life.thermal.ThermalInput(None, 1, 1)
    old = jobs.reserve()
    jobs.attach(old, "thermal-released", "result-released", spec)
    jobs.fail(old, RuntimeError("first"))
    jobs.release(old)
    active = jobs.reserve()
    jobs.attach(active, "thermal-current", "result-current", spec)
    accounting = (jobs._active, jobs._pending, jobs._reserved_bytes)
    jobs.release(old)
    assert accounting == (jobs._active, jobs._pending, jobs._reserved_bytes)
    assert jobs._active == 1
    with pytest.raises(life.thermal.ThermalAPIError) as blocked:
        jobs.reserve()
    assert blocked.value.status == 429
    assert json.loads(jobs.status("thermal-current"))["status"] == "running"
    jobs.fail(active, RuntimeError("finish"))
    jobs.release(active)


def test_thermal_eviction_uses_terminal_time_not_admission_or_last_read(lifecycle):
    life = lifecycle
    jobs = life.jobs
    jobs.limits = replace(jobs.limits, active_jobs=2, terminal_jobs=2,
                          terminal_bytes=2*(jobs.limits.payload_bytes+jobs.limits.status_bytes))
    spec = life.thermal.ThermalInput(None, 1, 1)
    admitted_first = jobs.reserve()
    jobs.attach(admitted_first, "thermal-first", "result-first", spec)
    admitted_second = jobs.reserve()
    jobs.attach(admitted_second, "thermal-second", "result-second", spec)
    jobs.fail(admitted_second, RuntimeError("completed earlier"))
    jobs.release(admitted_second)
    life.clock.advance(1)
    jobs.complete(admitted_first, b"{}", [])
    jobs.release(admitted_first)
    # Reading the older terminal does not promise another TTL or make it newest.
    assert jobs.status("thermal-second")
    third = jobs.reserve()
    with pytest.raises(life.thermal.ThermalAPIError) as evicted:
        jobs.status("thermal-second")
    assert evicted.value.status == 404
    assert jobs.result("thermal-first") == b"{}"
    jobs.attach(third, "thermal-third", "result-third", spec)
    jobs.fail(third, RuntimeError("done"))
    jobs.release(third)


def test_thermal_error_terminal_expires_at_exact_maximum_without_read_refresh(lifecycle):
    life = lifecycle
    jobs = life.jobs
    spec = life.thermal.ThermalInput(None, 1, 1)
    lease = jobs.reserve()
    jobs.attach(lease, "thermal-error-ttl", "result-error-ttl", spec)
    jobs.fail(lease, RuntimeError("error"))
    jobs.release(lease)
    life.clock.advance(jobs.limits.ttl_seconds - 0.25)
    assert json.loads(jobs.status("thermal-error-ttl"))["status"] == "error"
    life.clock.advance(0.25)
    for getter in (jobs.status, jobs.result):
        with pytest.raises(life.thermal.ThermalAPIError) as expired:
            getter("thermal-error-ttl")
        assert expired.value.status == 404


def test_thermal_release_fallback_never_exceeds_configured_error_bytes(lifecycle, monkeypatch):
    life = lifecycle
    life.jobs.limits = replace(life.jobs.limits, error_bytes=32)
    response = submit(life)
    assert response.status_code == 200

    def broken(*args, **kwargs):
        raise RuntimeError("large failure " * 100)

    with monkeypatch.context() as fault:
        fault.setattr(server, "run", broken)
        life.gate.finish_one()
    assert_released_once(life)
    job = response.json()["job"]
    status = life.client.get("/api/jobs/" + job)
    # If even the fallback cannot fit, dropping this own unpublished record is
    # fail-closed. Retaining an error larger than its budget is not acceptable.
    if status.status_code == 404:
        assert life.client.get("/api/jobs/" + job + "/result").status_code == 404
    else:
        assert status.status_code == 200
        value = status.json()
        assert value["status"] == "error" and value["has_result"] is False
        encoded_error = json.dumps(value["error"], ensure_ascii=False,
                                   separators=(",", ":")).encode("utf-8")
        assert len(encoded_error) <= life.jobs.limits.error_bytes
        assert life.client.get("/api/jobs/" + job + "/result").status_code == 409
