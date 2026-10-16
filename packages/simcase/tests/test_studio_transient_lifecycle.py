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
