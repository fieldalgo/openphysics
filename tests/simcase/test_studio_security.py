# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Studio refuses other web pages: Host and Origin checks, body caps, CSP, job limits.

The browser half (both pages work same-origin under the policy with no violation, and a
crafted model runs no script in the classic editor) was checked by hand in Chromium with
Playwright when these checks were added.
"""

import base64
import hashlib
import re
import threading

import pytest

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

from simcase import examples  # noqa: E402
from simcase.studio import security, server  # noqa: E402

DOC = examples.EXAMPLES["soi_strip"]
ORIGIN = "http://testserver"


@pytest.fixture
def client():
    return TestClient(server.app)


@pytest.fixture
def no_jobs(monkeypatch):
    """Any optical job start during a refused request is a failure."""
    started = []
    monkeypatch.setattr(server, "run", lambda *a, **k: started.append(a))
    monkeypatch.setattr(server, "_start_thermal_thread", lambda *a, **k: started.append(a))
    jobs = server.thermal.ThermalJobs()
    monkeypatch.setattr(server, "_thermal_jobs", jobs)
    before = dict(server._jobs)
    yield started
    assert started == [] and not jobs._records
    assert server._jobs == before


# ---- S1 Host ---------------------------------------------------------------------

@pytest.mark.parametrize("host", ["evil.example", "evil.example:80", "127.0.0.1.nip.io",
                                  "localhost.evil.example", "0.0.0.0", "192.168.1.5"])
@pytest.mark.parametrize("method,path", [("GET", "/"), ("GET", "/workspace"),
                                         ("GET", "/static/thermal.js"), ("GET", "/api/examples"),
                                         ("POST", "/api/run")])
def test_foreign_host_is_refused_before_any_route(client, no_jobs, host, method, path):
    r = client.request(method, path, headers={"host": host}, json={"doc": DOC})
    assert r.status_code == 403, r.text
    assert "host" in r.json()["detail"]
    assert "content-security-policy" in r.headers


@pytest.mark.parametrize("host", ["testserver", "127.0.0.1", "localhost", "[::1]", "LOCALHOST"])
def test_loopback_and_connection_hosts_are_served(client, host):
    assert client.get("/api/examples", headers={"host": host}).status_code == 200


def test_host_port_must_be_the_bound_port(client):
    # TestClient reports server port 80; a rebinding page uses whatever port the attacker serves.
    assert client.get("/api/examples", headers={"host": "127.0.0.1:80"}).status_code == 200
    r = client.get("/api/examples", headers={"host": "127.0.0.1:8765"})
    assert r.status_code == 403 and "port" in r.json()["detail"]


@pytest.mark.parametrize("host", ["", "a b", "evil.example/x", "user@127.0.0.1", "[::1", "::1", "127.0.0.1:x",
                                  "127.0.0.1:\u00b2".encode("latin-1"), "127.0.0.1:"])
def test_malformed_host_is_refused(client, host):
    assert client.get("/api/examples", headers={"host": host}).status_code in (400, 403)


def test_explicit_host_is_allowed(client):
    assert client.get("/api/examples", headers={"host": "studio.lan"}).status_code == 403
    server._extra_hosts.add("studio.lan")
    try:
        assert client.get("/api/examples", headers={"host": "studio.lan"}).status_code == 200
    finally:
        server._extra_hosts.discard("studio.lan")


# ---- S2 Origin -------------------------------------------------------------------

@pytest.mark.parametrize("headers", [
    {"origin": "http://evil.example"},
    {"origin": "null"},
    {"origin": "http://localhost:3000"},
    {"origin": "https://testserver"},
    {"origin": "http://127.0.0.1"},          # same machine, another origin than the Host
    {"referer": "http://evil.example/page"},
    {"referer": "not a url"},
    {"sec-fetch-site": "cross-site"},
    {"sec-fetch-site": "same-site"},
])
@pytest.mark.parametrize("path", ["/api/run", "/api/validate", "/api/mesh", "/api/thermal/run",
                                  "/api/thermal/transient/run", "/api/materials/preview"])
def test_cross_origin_state_change_is_refused(client, no_jobs, headers, path):
    r = client.post(path, headers=headers, json={"doc": DOC})
    assert r.status_code == 403, r.text
    assert "other web pages" in r.json()["detail"]


@pytest.mark.parametrize("headers", [
    {}, {"origin": ORIGIN}, {"origin": "HTTP://TESTSERVER"}, {"referer": ORIGIN + "/"},
    {"sec-fetch-site": "same-origin"}, {"sec-fetch-site": "none"},
])
def test_same_origin_and_non_browser_requests_still_work(client, headers):
    r = client.post("/api/validate", headers=headers, json={"doc": DOC})
    assert r.status_code == 200 and r.json()["ok"] is True


def test_safe_methods_ignore_origin(client):
    # A cross-site GET cannot read the answer (no CORS); refusing it would only break links.
    assert client.get("/api/examples", headers={"origin": "http://evil.example"}).status_code == 200


# ---- S3 optical bodies and jobs --------------------------------------------------

@pytest.mark.parametrize("path", sorted(security.OPTICAL_BODY_ROUTES))
@pytest.mark.parametrize("ctype", ["text/plain", "application/x-www-form-urlencoded",
                                   "multipart/form-data; boundary=x", None])
def test_optical_routes_need_json_and_do_not_echo(client, no_jobs, path, ctype):
    marker = "<script>secret-marker</script>"
    headers = {"content-type": ctype} if ctype else {}
    r = client.post(path, content=('{"doc": "%s"}' % marker).encode(), headers=headers)
    assert r.status_code == 415, r.text
    assert "secret-marker" not in r.text


@pytest.mark.parametrize("path", sorted(security.OPTICAL_BODY_ROUTES))
def test_optical_body_cap(client, no_jobs, path):
    cap = security.OPTICAL_BODY_BYTES
    r = client.post(path, content=b" " * (cap + 1), headers={"content-type": "application/json"})
    assert r.status_code == 413
    # A body at the cap reaches the route (and fails as JSON there, not at the guard).
    r = client.post(path, content=b" " * cap, headers={"content-type": "application/json"})
    assert r.status_code == 422


def test_non_ascii_content_length_is_refused_not_crashed():
    import asyncio
    messages = []

    async def send(message):
        messages.append(message)

    async def receive():
        return {"type": "http.request", "body": b"{}", "more_body": False}

    guard = security.StudioGuard(None, csp="default-src 'none'", extra_hosts=set())
    scope = {"type": "http", "method": "POST", "path": "/api/run", "server": ("127.0.0.1", 8765),
             "headers": [(b"host", b"127.0.0.1:8765"), (b"content-type", b"application/json"),
                         (b"content-length", "\u00b2".encode("latin-1"))]}
    asyncio.run(guard(scope, receive, send))
    assert messages[0]["status"] == 413


def test_refusals_carry_the_full_header_set(client):
    r = client.get("/", headers={"host": "evil.example"})
    assert r.status_code == 403
    for name in ("content-security-policy", "x-content-type-options", "x-frame-options",
                 "referrer-policy", "cross-origin-resource-policy"):
        assert name in r.headers


def test_optical_body_cap_without_content_length():
    """A chunked body is counted while it is read, not trusted from a header."""
    import asyncio

    chunks = [b" " * (security.OPTICAL_BODY_BYTES // 2)] * 3
    messages = []

    async def receive():
        body = chunks.pop(0)
        return {"type": "http.request", "body": body, "more_body": bool(chunks)}

    async def send(message):
        messages.append(message)

    async def app(scope, receive, send):  # pragma: no cover - must not run
        raise AssertionError("route reached")

    guard = security.StudioGuard(app, csp="default-src 'none'", extra_hosts=set())
    scope = {"type": "http", "method": "POST", "path": "/api/run", "server": ("127.0.0.1", 8765),
             "headers": [(b"host", b"127.0.0.1:8765"), (b"content-type", b"application/json")]}
    asyncio.run(guard(scope, receive, send))
    assert messages[0]["status"] == 413


def test_optical_running_job_cap_and_finished_jobs_are_freed(client, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(server, "_jobs", {})

    def slow_job(job_id, doc):
        release.wait(10)
        with server._jobs_lock:
            server._jobs[job_id].update(status="done", result={})
    monkeypatch.setattr(server, "_run_job", slow_job)
    try:
        ids = [client.post("/api/run", json={"doc": DOC}).json()["job"] for _ in range(server._MAX_RUNNING_JOBS)]
        r = client.post("/api/run", json={"doc": DOC})
        assert r.status_code == 429
    finally:
        release.set()
    for job_id in ids:
        for _ in range(200):
            if client.get(f"/api/jobs/{job_id}").json()["status"] == "done":
                break
            threading.Event().wait(0.02)
    monkeypatch.setattr(server, "_run_job", lambda job_id, doc: server._jobs[job_id].update(status="done"))
    for _ in range(server._MAX_FINISHED_JOBS + 5):
        client.post("/api/run", json={"doc": DOC})
    threading.Event().wait(0.2)
    assert len(server._jobs) <= server._MAX_FINISHED_JOBS + 1
    assert ids[0] not in server._jobs


def test_failed_job_status_has_no_traceback(client, monkeypatch):
    def boom(doc, verbose=False):
        raise RuntimeError("solver exploded")
    monkeypatch.setattr(server, "run", boom)
    job = client.post("/api/run", json={"doc": DOC}).json()["job"]
    for _ in range(200):
        status = client.get(f"/api/jobs/{job}").json()
        if status["status"] != "running":
            break
        threading.Event().wait(0.02)
    assert status["status"] == "error" and status["error"] == "RuntimeError: solver exploded"
    assert "traceback" not in status and "File \"" not in str(status)


# ---- S6 headers and CSP ----------------------------------------------------------

@pytest.mark.parametrize("path", ["/", "/workspace", "/static/thermal.js",
                                  "/workspace-assets/workspace.css", "/api/examples", "/nope"])
def test_every_response_carries_the_policy(client, path):
    r = client.get(path)
    csp = r.headers["content-security-policy"]
    directives = dict(d.strip().split(" ", 1) for d in csp.split(";"))
    assert directives["default-src"] == "'none'"
    assert directives["frame-ancestors"] == "'none'"
    assert "'unsafe-inline'" not in directives["script-src"]
    assert "'unsafe-eval'" not in directives["script-src"]
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cross-origin-resource-policy"] == "same-origin"


def test_policy_hashes_exactly_the_inline_classic_script(client):
    served = client.get("/")
    page = served.text
    inline = re.findall(rb"<script>(.*?)</script>", served.content, flags=re.S)
    assert len(inline) == 1
    # Hash the served bytes independently of the code that built the header.
    expected = "'sha256-" + base64.b64encode(hashlib.sha256(inline[0]).digest()).decode() + "'"
    assert re.findall(r"'sha256-[^']+'", served.headers["content-security-policy"]) == [expected]
    # workspace.html has no inline script at all
    assert not re.findall(r"<script>(.*?)</script>", client.get("/workspace").text, flags=re.S)
    assert not re.search(r"\son[a-z]+=", page + client.get("/workspace").text)


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/docs/oauth2-redirect"])
def test_cdn_api_docs_are_off(client, path):
    assert client.get(path).status_code == 404


# ---- S7 --host -------------------------------------------------------------------

@pytest.mark.parametrize("host,warns,url", [
    ("127.0.0.1", False, "http://127.0.0.1:9/"), ("localhost", False, "http://localhost:9/"),
    ("::1", False, "http://[::1]:9/"), ("0.0.0.0", True, "http://127.0.0.1:9/"),
    ("::", True, "http://[::1]:9/"), ("192.168.1.5", True, "http://192.168.1.5:9/"),
])
def test_host_option_warns_and_allows(client, monkeypatch, capsys, host, warns, url):
    import uvicorn
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: calls.append(kw))
    before = set(server._extra_hosts)
    try:
        server.main(["--host", host, "--port", "9", "--no-browser"])
        out = capsys.readouterr()
        assert ("warning:" in out.err) is warns
        assert url in out.out
        assert calls == [{"host": host, "port": 9, "log_level": "warning"}]
        # The running guard itself must now admit the explicit host (port 80 in TestClient).
        name = f"[{host}]" if ":" in host else host
        expected = 403 if host in ("0.0.0.0", "::") else 200
        assert client.get("/api/examples", headers={"host": name}).status_code == expected
    finally:
        server._extra_hosts.intersection_update(before)
