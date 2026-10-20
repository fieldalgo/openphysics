# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Deterministic ASGI transport fixtures; no sleeps, real threads or solver stubs."""
import asyncio
import copy
import json


class Exchange:
    def __init__(self, path, *, method="POST", body=b"{", receive_mode="normal", hold_body=False, query=b""):
        self.path, self.method, self.body = path, method, body
        self.query = query
        self.receive_mode, self.hold_body = receive_mode, hold_body
        self.receive_entered = asyncio.Event()
        self.receive_release = asyncio.Event()
        self.send_entered = asyncio.Event()
        self.send_release = asyncio.Event()
        self.receive_calls = 0
        self.messages = []
        self.never = asyncio.Event()

    async def receive(self):
        self.receive_calls += 1
        if self.receive_calls > 1:
            await self.never.wait()
        self.receive_entered.set()
        if self.hold_body:
            await self.receive_release.wait()
        if self.receive_mode == "raise":
            raise RuntimeError("injected request stream failure")
        if self.receive_mode == "disconnect":
            return {"type": "http.disconnect"}
        return {"type": "http.request", "body": self.body, "more_body": False}

    async def send(self, message):
        self.messages.append(copy.deepcopy(message))
        if message["type"] == "http.response.body":
            self.send_entered.set()
            await self.send_release.wait()

    async def invoke(self, app):
        scope = {
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1", "method": self.method, "scheme": "http",
            "path": self.path, "raw_path": self.path.encode("ascii"),
            "root_path": "", "query_string": self.query,
            "headers": [(b"content-type", b"application/json")],
            "client": ("127.0.0.1", 12345), "server": ("testserver", 80),
        }
        await app(scope, self.receive, self.send)

    @property
    def status(self):
        starts = [m for m in self.messages if m["type"] == "http.response.start"]
        assert len(starts) == 1, self.messages
        return starts[0]["status"]

    def json(self):
        raw = b"".join(m.get("body", b"") for m in self.messages if m["type"] == "http.response.body")
        return json.loads(raw)

    def unblock(self):
        self.receive_release.set()
        self.send_release.set()


async def reach(task, event):
    """Wait for the observable milestone or fail on premature producer completion.

    No time delay stands in for synchronization. The milestone waiter is always
    cleaned up. Outer CI time limits are not numerical acceptance criteria.
    """
    waiter = asyncio.create_task(event.wait())
    try:
        done, _ = await asyncio.wait((task, waiter), return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            await task
        assert event.is_set(), "application completed before the expected transport milestone"
    finally:
        waiter.cancel()
        await asyncio.gather(waiter, return_exceptions=True)


async def finish(exchange, task):
    exchange.unblock()
    return await task


async def cleanup(*pairs):
    for exchange, task in pairs:
        exchange.unblock()
        if not task.done():
            task.cancel()
    await asyncio.gather(*(task for _, task in pairs), return_exceptions=True)
