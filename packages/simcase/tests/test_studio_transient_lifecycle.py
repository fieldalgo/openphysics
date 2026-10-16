# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent transient-extension ingress and transport ownership regressions.

Uses the actual Studio app/store, not a synthetic registry implementation.
Cached steady responses are cache-layer fixtures, not physical result oracles.
Existing test_studio_thermal_lifecycle.py and its 55 gates remain unchanged.
"""
import asyncio
import copy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from simcase.studio import server
from studio_transient_lifecycle_fixtures import Exchange, cleanup, finish, reach


THERMAL_ROUTES = (
    "/api/thermal/validate", "/api/thermal/run",
    "/api/thermal/transient/validate", "/api/thermal/transient/run",
)


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value


@pytest.fixture
def isolated_store(monkeypatch):
    thermal = server.thermal
    clock = Clock()
    limits = replace(thermal.ThermalLimits(), payload_bytes=8192, status_bytes=4096,
                     terminal_bytes=8192+4096+32)
    jobs = thermal.ThermalJobs(limits=limits, clock=clock)
    monkeypatch.setattr(server, "_thermal_jobs", jobs)
    key = "optical-transient-lifecycle-sentinel"
    sentinel = {"status": "running", "log": ["owned elsewhere"], "result": None, "error": None}
    with server._jobs_lock:
        assert key not in server._jobs
        server._jobs[key] = sentinel
        before = copy.deepcopy(sentinel)
    yield SimpleNamespace(jobs=jobs, clock=clock, thermal=thermal)
    with server._jobs_lock:
        assert server._jobs.get(key) is sentinel and sentinel == before
        del server._jobs[key]  # only this test's injected key
    assert (jobs._active, jobs._pending, jobs._reserved_bytes) == (0, 0, 0)


def require_extension():
    paths = {route.path for route in server.app.routes}
    assert set(THERMAL_ROUTES) <= paths, "transient Studio extension must be installed; no skip fallback"


@pytest.fixture
def forbid_allocation(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("malformed or capacity-rejected input allocated a document/job/solver")

    monkeypatch.setattr(server.Document, "from_dict", forbidden)
    monkeypatch.setattr(server, "run", forbidden)
    monkeypatch.setattr(server, "uuid", SimpleNamespace(uuid4=forbidden))
    monkeypatch.setattr(server, "_start_thermal_thread", forbidden)
    yield calls
    assert calls == []


@pytest.mark.parametrize("owner_route", THERMAL_ROUTES)
@pytest.mark.parametrize("contender_route", THERMAL_ROUTES)
def test_shared_ingress_rejects_all_cross_routes_before_body(
        isolated_store, forbid_allocation, owner_route, contender_route):
    require_extension()

    async def scenario():
        first = Exchange(owner_route, hold_body=True)
        first.send_release.set()
        first_task = asyncio.create_task(first.invoke(server.app))
        second = Exchange(contender_route)
        second.send_release.set()
        second_task = None
        try:
            await reach(first_task, first.receive_entered)
            second_task = asyncio.create_task(second.invoke(server.app))
            await second_task
            assert second.status == 429
            assert second.json()["error"]["code"] == "ingress_capacity_exceeded"
            assert second.receive_calls == 0, "excess thermal request read body before rejection"
            assert not isolated_store.jobs._records
            assert isolated_store.jobs._active == 0
            await finish(first, first_task)
            assert first.status == 400  # invalid JSON, not logical document validation
            retry = Exchange(contender_route)
            retry.unblock()
            await retry.invoke(server.app)
            assert retry.status == 400, "failed owner did not release ingress for next explicit request"
        finally:
            pairs = [(first, first_task)]
            if second_task is not None:
                pairs.append((second, second_task))
            await cleanup(*pairs)

    asyncio.run(scenario())


@pytest.mark.parametrize("route", THERMAL_ROUTES)
@pytest.mark.parametrize("failure", ["raise", "disconnect", "cancel"])
def test_ingress_failure_releases_before_next_request(
        isolated_store, forbid_allocation, route, failure):
    require_extension()

    async def scenario():
        exchange = Exchange(route, receive_mode=failure, hold_body=True)
        exchange.send_release.set()
        task = asyncio.create_task(exchange.invoke(server.app))
        try:
            await reach(task, exchange.receive_entered)
            if failure == "cancel":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                await finish(exchange, task)
                assert exchange.status == 400
                assert exchange.json()["error"]["code"] == "request_read_failed"
            retry = Exchange(route)
            retry.unblock()
            await retry.invoke(server.app)
            assert retry.status == 400
            assert isolated_store.jobs._active == 0
            assert not isolated_store.jobs._records
        finally:
            await cleanup((exchange, task))

    asyncio.run(scenario())


def cached_steady(life):
    jobs = life.jobs
    lease = jobs.reserve()
    spec = life.thermal.ThermalInput(None, 1, 1)
    identity = jobs.attach(lease, "thermal-transport-probe", "result-probe", spec)
    # Valid JSON bytes padded to the configured cap; intentionally synthetic
    # cache storage, not a public ThermalRunResult or solver truth fixture.
    encoded = b"{}" + b" " * (jobs.limits.payload_bytes-2)
    assert jobs.complete(lease, encoded, [])
    jobs.release(lease)
    return identity


@pytest.mark.parametrize("suffix", ["", "/result"])
@pytest.mark.parametrize("termination", ["success", "send-error", "cancel"])
def test_evicted_cached_response_bytes_remain_charged_until_send_finally(
        isolated_store, suffix, termination):
    require_extension()
    life = isolated_store
    identity = cached_steady(life)

    async def scenario():
        response = Exchange("/api/jobs/" + identity["job"] + suffix, method="GET")
        original_send = response.send
        if termination == "send-error":
            async def failed_send(message):
                await original_send(message)
                if message["type"] == "http.response.body":
                    raise OSError("injected slow response send failure")
            response.send = failed_send
        task = asyncio.create_task(response.invoke(server.app))
        try:
            await reach(task, response.send_entered)
            assert response.status == 200
            life.clock.value = life.jobs.limits.ttl_seconds
            with pytest.raises(life.thermal.ThermalAPIError) as expired:
                life.jobs.status(identity["job"])
            assert expired.value.status == 404
            # Both old status (>32B) and result (8192B) pins exceed the spare32B
            # beside one max reservation12288. Eviction must not erase charge.
            with pytest.raises(life.thermal.ThermalAPIError) as blocked:
                life.jobs.reserve()
            assert blocked.value.status == 429
            if termination == "cancel":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            elif termination == "send-error":
                response.unblock()
                with pytest.raises(OSError, match="injected slow response"):
                    await task
            else:
                await finish(response, task)
            admitted = life.jobs.reserve()
            life.jobs.release(admitted)
            assert life.jobs._active == 0
        finally:
            await cleanup((response, task))

    asyncio.run(scenario())


def test_identical_cached_object_pin_charged_until_last_sender(isolated_store):
    require_extension()
    life = isolated_store
    identity = cached_steady(life)

    async def scenario():
        responses = [Exchange("/api/jobs/" + identity["job"] + "/result", method="GET")
                     for _ in range(2)]
        tasks = [asyncio.create_task(response.invoke(server.app)) for response in responses]
        try:
            for response, task in zip(responses, tasks):
                await reach(task, response.send_entered)
                assert response.status == 200
            life.clock.value = life.jobs.limits.ttl_seconds
            with pytest.raises(life.thermal.ThermalAPIError) as expired:
                life.jobs.result(identity["job"])
            assert expired.value.status == 404
            await finish(responses[0], tasks[0])
            with pytest.raises(life.thermal.ThermalAPIError) as blocked:
                life.jobs.reserve()
            assert blocked.value.status == 429
            await finish(responses[1], tasks[1])
            next_lease = life.jobs.reserve()
            life.jobs.release(next_lease)
        finally:
            await cleanup(*list(zip(responses, tasks)))

    asyncio.run(scenario())


@pytest.mark.parametrize("gate_name,code", [
    ("ingress", "ingress_capacity_exceeded"),
    ("read_encoder", "read_capacity_exceeded"),
])
def test_actual_permit_old_release_cannot_free_new_owner(isolated_store, gate_name, code):
    jobs = isolated_store.jobs
    gate = getattr(jobs, gate_name)
    first = gate.acquire()
    try:
        with pytest.raises(isolated_store.thermal.ThermalAPIError) as busy:
            gate.acquire()
        assert busy.value.status == 429 and busy.value.code == code
    finally:
        first.release()
    second = gate.acquire()
    try:
        first.release()
        # Also exercise the gate's identity check, separately from Permit's flag.
        gate._release(first)
        with pytest.raises(isolated_store.thermal.ThermalAPIError) as busy:
            gate.acquire()
        assert busy.value.status == 429 and busy.value.code == code
    finally:
        second.release()
        second.release()
    third = gate.acquire()
    third.release()


def test_actual_ingress_solver_and_read_permits_are_independent(isolated_store):
    jobs = isolated_store.jobs
    ingress = jobs.ingress.acquire()
    solver = None
    read = None
    try:
        solver = jobs.reserve()
        read = jobs.read_encoder.acquire()
        assert jobs._active == 1
        for acquire in (jobs.ingress.acquire, jobs.reserve, jobs.read_encoder.acquire):
            with pytest.raises(isolated_store.thermal.ThermalAPIError) as busy:
                acquire()
            assert busy.value.status == 429
        ingress.release()
        next_validation = jobs.ingress.acquire()
        next_validation.release()
        assert jobs._active == 1  # validation release must not release the solver
    finally:
        ingress.release()
        if read is not None:
            read.release()
        if solver is not None:
            jobs.release(solver)


def attach_cache_record(life, job="thermal-store-probe"):
    jobs = life.jobs
    lease = jobs.reserve()
    spec = life.thermal.ThermalInput(None, 7, 11)
    jobs.attach(lease, job, "result-store-probe", spec)
    return lease


@pytest.mark.parametrize("reader_count", [1, 2])
def test_running_same_status_allocation_is_not_charged_per_reader_or_twice_with_reservation(
        isolated_store, reader_count):
    life = isolated_store
    jobs = life.jobs
    lease = attach_cache_record(life)
    pins = []
    try:
        before = jobs._retained_bytes() + jobs._reserved_bytes
        assert before == lease.reservation
        for _ in range(reader_count):
            pins.append(jobs.pin("thermal-store-probe"))
        old_size = len(pins[0].payload)
        assert all(pin.payload is pins[0].payload for pin in pins)
        # These are references to the already-reserved running status allocation,
        # not new encoded copies and not additional per-reader byte allocations.
        assert jobs._retained_bytes() + jobs._reserved_bytes == before
        assert jobs.complete(lease, b"{}", [])
        jobs.release(lease)
        current = jobs._records["thermal-store-probe"]
        expected = len(current["status_bytes"]) + len(current["result"]) + old_size
        assert jobs._retained_bytes() == expected
        if reader_count == 2:
            pins[0].release()
            pins[0].release()
            assert jobs._retained_bytes() == expected
        pins[-1].release()
        assert jobs._retained_bytes() == len(current["status_bytes"]) + len(current["result"])
    finally:
        for pin in pins:
            pin.release()
        jobs.release(lease)


@pytest.mark.parametrize("result_pin", [False, True])
def test_actual_raw_and_encoded_record_pins_survive_expiry_until_last_reader(
        isolated_store, result_pin):
    import numpy as np
    life = isolated_store
    jobs = life.jobs
    lease = attach_cache_record(life)
    pins = []
    try:
        raw = {"temperature_k": np.arange(12, dtype=np.float64).reshape(3, 4)}
        assert jobs.complete_transient(lease, b"{}", raw, [], 1.0)
        jobs.release(lease)
        pins = [jobs.pin("thermal-store-probe", result=result_pin,
                         result_id="result-store-probe") for _ in range(2)]
        record = pins[0].record
        expected = len(record["status_bytes"]) + len(record["result"]) + raw["temperature_k"].nbytes
        assert pins[1].record is record
        assert jobs._retained_bytes() == expected
        del record, raw  # leave ownership exclusively with the store and its pins
        life.clock.value = jobs.limits.ttl_seconds
        with pytest.raises(life.thermal.ThermalAPIError) as expired:
            jobs.status("thermal-store-probe")
        assert expired.value.status == 404
        assert not jobs._records and jobs._retained_bytes() == expected
        pins[0].release()
        pins[0].release()
        assert jobs._retained_bytes() == expected
        pins[1].release()
        assert jobs._retained_bytes() == 0
    finally:
        for pin in pins:
            pin.release()
        jobs.release(lease)


def test_released_pin_drops_its_own_raw_and_encoded_references(isolated_store):
    import gc
    import weakref
    import numpy as np
    life = isolated_store
    jobs = life.jobs
    lease = attach_cache_record(life)
    raw = {"temperature_k": np.arange(12, dtype=np.float64).reshape(3, 4)}
    assert jobs.complete_transient(lease, b"{}", raw, [], 1.0)
    jobs.release(lease)
    pin = jobs.pin("thermal-store-probe", result=True)
    array_reference = weakref.ref(raw["temperature_k"])
    del raw
    life.clock.value = jobs.limits.ttl_seconds
    with pytest.raises(life.thermal.ThermalAPIError):
        jobs.result("thermal-store-probe")
    assert jobs._retained_bytes() > 0 and array_reference() is not None
    pin.release()
    pin.release()
    # A released transport object can itself remain referenced by a completed
    # coroutine. It must not retain uncharged payload/raw backing through record.
    assert pin.record is None and pin.payload is None
    gc.collect()
    assert array_reference() is None
    assert jobs._retained_bytes() == 0



def transient_cache_record(life, monkeypatch):
    """Immutable array/cache fixture, not capture_result or PDE acceptance."""
    import numpy as np
    from types import MappingProxyType
    # Test-specific encoder budget; production encoder and all cleanup paths run.
    monkeypatch.setattr(server.transient, "ENCODED_BYTES", 2048)
    lease = life.jobs.reserve()
    spec = SimpleNamespace(kind="thermal.transient2d",
                           tags=lambda: {"client_revision": 7, "request_seq": 11})
    identity = life.jobs.attach(lease, "thermal-transient-route-probe", "result-route-probe", spec)
    raw = {"time_s": np.array([2., 3.5]),
           "temperature_k": np.arange(8, dtype=float).reshape(2, 4)}
    for value in raw.values():
        value.flags.writeable = False
    assert life.jobs.complete_transient(lease, b"{}", MappingProxyType(raw), [], 1.)
    life.jobs.release(lease)
    return identity


def view_exchange(identity, view):
    from urllib.parse import urlencode
    query = {"result_id": identity["result_id"], "field": "temperature_k", "frame_seq": 3}
    query.update({"start": 0, "stop": 2} if view == "history" else {"time_index": 1})
    return Exchange("/api/jobs/"+identity["job"]+"/"+view, method="GET",
                    query=urlencode(query).encode("ascii"))


@pytest.mark.parametrize("view", ["frame", "history"])
@pytest.mark.parametrize("termination", ["success", "disconnect", "cancel"])
def test_actual_view_slow_send_pins_eviction_read_competition_and_final_release(
        isolated_store, monkeypatch, view, termination):
    life = isolated_store
    identity = transient_cache_record(life, monkeypatch)

    async def scenario():
        exchange = view_exchange(identity, view)
        original_send = exchange.send
        if termination == "disconnect":
            async def disconnected_send(message):
                await original_send(message)
                if message["type"] == "http.response.body":
                    raise OSError("injected ASGI send disconnect")
            exchange.send = disconnected_send
        task = asyncio.create_task(exchange.invoke(server.app))
        try:
            await reach(task, exchange.send_entered)
            assert exchange.status == 200
            payload = exchange.json()
            assert payload["frame_seq"] == 3
            assert payload["arrays"]["temperature_k"] == (
                [[0., 1., 2., 3.], [4., 5., 6., 7.]] if view == "history"
                else [4., 5., 6., 7.])
            record = life.jobs._records[identity["job"]]
            raw_size = sum(a.nbytes for a in record["raw"].values())
            owned_size = (len(record["status_bytes"])+len(record["result"])
                          +raw_size)
            encoded_size = len(b"".join(m.get("body", b"") for m in exchange.messages))
            assert life.jobs._read_workspace == 0
            assert life.jobs._retained_bytes() == owned_size+encoded_size
            # One global read owner for BOTH production frame/history routes.
            for contender_view in ("frame", "history"):
                contender = view_exchange(identity, contender_view)
                contender.unblock()
                await contender.invoke(server.app)
                assert contender.status == 429
                assert contender.json()["error"]["code"] == "read_capacity_exceeded"
                assert record["pins"] == 1
                assert life.jobs._retained_bytes() == owned_size+encoded_size
            life.clock.value = life.jobs.limits.ttl_seconds
            with pytest.raises(life.thermal.ThermalAPIError) as expired:
                life.jobs.status(identity["job"])
            assert expired.value.status == 404
            assert not life.jobs._records and life.jobs._retained_bytes() == owned_size+encoded_size
            del record
            with pytest.raises(life.thermal.ThermalAPIError) as blocked:
                life.jobs.reserve()
            assert blocked.value.status == 429
            if termination == "cancel":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            elif termination == "disconnect":
                exchange.unblock()
                with pytest.raises(OSError, match="ASGI send disconnect"):
                    await task
            else:
                await finish(exchange, task)
            assert not life.jobs._retired and not life.jobs._snapshots
            assert life.jobs._read_workspace == 0 and life.jobs._retained_bytes() == 0
            permit = life.jobs.read_encoder.acquire()
            permit.release()
            lease = life.jobs.reserve()
            life.jobs.release(lease)
        finally:
            await cleanup((exchange, task))

    asyncio.run(scenario())


@pytest.mark.parametrize("view", ["frame", "history"])
@pytest.mark.parametrize("stage", ["slice", "encode", "response"])
def test_actual_view_production_fault_releases_pin_workspace_and_permit(
        isolated_store, monkeypatch, view, stage):
    import numpy as np
    life = isolated_store
    identity = transient_cache_record(life, monkeypatch)
    record = life.jobs._records[identity["job"]]
    original_retained = life.jobs._retained_bytes()
    calls = []

    if stage == "slice":
        class FailedSlice(np.ndarray):
            def __getitem__(self, key):
                calls.append("slice")
                raise RuntimeError("injected production slice")
        # Production encode_view performs the actual frame/page indexing.
        original = record["raw"]
        record["raw"] = dict(original)
        record["raw"]["temperature_k"] = original["temperature_k"].view(FailedSlice)
    elif stage == "encode":
        original_encode = server.transient.common.encode_json
        def failed_encode(value, limit):
            if value.get("payload_format") in (server.transient.FRAME, server.transient.HISTORY):
                calls.append("encode")
                raise RuntimeError("injected production encode")
            return original_encode(value, limit)
        monkeypatch.setattr(server.transient.common, "encode_json", failed_encode)
    else:
        def failed_response(*args, **kwargs):
            calls.append("response")
            raise RuntimeError("injected production response construction")
        monkeypatch.setattr(server, "ThermalResponse", failed_response)

    async def scenario():
        exchange = view_exchange(identity, view)
        exchange.unblock()
        await exchange.invoke(server.app)
        assert exchange.status == 500
        assert exchange.json()["error"]["code"] == "view_failed"
        assert calls == [stage], "fault must occur inside the actual producer path"
        assert record["pins"] == 0
        assert life.jobs._read_workspace == 0 and not life.jobs._snapshots
        assert life.jobs._retained_bytes() == original_retained
        permit = life.jobs.read_encoder.acquire()
        permit.release()
        life.clock.value = life.jobs.limits.ttl_seconds
        with pytest.raises(life.thermal.ThermalAPIError) as expired:
            life.jobs.status(identity["job"])
        assert expired.value.status == 404
        assert life.jobs._retained_bytes() == 0 and not life.jobs._retired
    asyncio.run(scenario())
