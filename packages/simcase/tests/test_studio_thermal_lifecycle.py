# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Independent thermal HTTP ingress and deterministic lifecycle test fixtures.

The request limit is the proposed policy, not a measured memory guarantee.
No solver is substituted for numerical acceptance. ASGI is not a browser.
"""

import asyncio
import copy
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
    with server._jobs_lock:
        before = copy.deepcopy(server._jobs)
    yield calls
    assert calls == []
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
