# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Studio refuses other web pages: Host and Origin checks, body caps, CSP, job limits.

The browser half (both pages work same-origin under the policy with no violation, and a
crafted model runs no script in the classic editor) was checked by hand in Chromium with
Playwright when these checks were added.
"""

import base64
import hashlib
import json
import re
import threading
from pathlib import Path

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
    # A body at the cap reaches the route (and fails as JSON there, not at the guard): a document
    # route reads the bytes with simcase.reader (E-JSON, 400), the material preview with pydantic.
    r = client.post(path, content=b" " * cap, headers={"content-type": "application/json"})
    if path == "/api/materials/preview":
        assert r.status_code == 422
    else:
        assert r.status_code == 400 and [d["code"] for d in r.json()["diagnostics"]] == ["E-JSON"]


# ---- S3b document bytes (units and naming batch, P2-19) ----------------------------
# Every route that takes a document reads the request's raw bytes with simcase.reader: a duplicate
# key, NaN, Infinity, malformed JSON, text that is not UTF-8 and an escaped unpaired surrogate are
# refused with their code, and a leading UTF-8 byte order mark is accepted. pydantic once parsed these bodies, kept the last of
# two equal keys and turned every number into a double.

DOCUMENT_ROUTES = ["/api/validate", "/api/mesh", "/api/run", "/api/geometry-lab/evaluate"]
GEOMETRY_DOC = json.loads((Path(__file__).resolve().parents[2] / "examples" / "simcase"
                           / "geometry_v1_soi_strip.json").read_text(encoding="utf-8"))
THERMAL_ROUTES = {"/api/thermal/validate": "thermal_slab", "/api/thermal/run": "thermal_slab",
                  "/api/thermal/transient/validate": "transient_thermal_uniform",
                  "/api/thermal/transient/run": "transient_thermal_uniform"}
JSON_TYPE = {"content-type": "application/json"}


def _compact(value) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


UNREADABLE = {
    "NaN": b'{"doc":{"openphysics":"0.3","x":NaN}}',
    "Infinity": b'{"doc":{"openphysics":"0.3","x":Infinity}}',
    "-Infinity": b'{"doc":{"openphysics":"0.3","x":-Infinity}}',
    "malformed": b'{"doc":{"openphysics":"0.3",',
    "not UTF-8": b'{"doc":{"openphysics":"0.3","name":"\xff"}}',
    "UTF-16": '{"doc":{"openphysics":"0.3"}}'.encode("utf-16"),
    # not Unicode text, so no UTF-8 reply could write it back (the heat routes refused it already)
    "unpaired surrogate": b'{"doc":{"openphysics":"0.3","name":"x\\ud800"}}',
    "unpaired surrogate key": b'{"doc":{"openphysics":"0.3","\\udfffname":"x"}}',
}


@pytest.mark.parametrize("path", DOCUMENT_ROUTES)
@pytest.mark.parametrize("case", sorted(UNREADABLE))
def test_document_routes_refuse_unreadable_bytes(client, no_jobs, path, case):
    r = client.post(path, content=UNREADABLE[case], headers=JSON_TYPE)
    assert r.status_code == 400, r.text
    assert [d["code"] for d in r.json()["diagnostics"]] == ["E-JSON"]
    assert r.json()["detail"].startswith("the request is not readable JSON: ")


@pytest.mark.parametrize("path", DOCUMENT_ROUTES)
def test_document_routes_refuse_a_duplicate_envelope_key(client, no_jobs, path):
    doc = _compact(DOC)
    r = client.post(path, content=f'{{"doc":{doc},"doc":{doc}}}'.encode(), headers=JSON_TYPE)
    assert r.status_code == 400, r.text
    found = r.json()["diagnostics"]
    assert [(d["code"], d["path"]) for d in found] == [("E-KEY-DUPLICATE", "")]
    assert '"doc" appears more than once' in found[0]["message"]


@pytest.mark.parametrize("path", DOCUMENT_ROUTES)
def test_document_routes_refuse_a_duplicate_document_key(client, no_jobs, path):
    source = GEOMETRY_DOC if path == "/api/geometry-lab/evaluate" else DOC
    text = _compact(source)
    assert text.count('"type":"rect"') >= 1
    twice = text.replace('"type":"rect"', '"type":"circle","type":"rect"', 1)  # json.loads would keep "rect"
    r = client.post(path, content=('{"doc":' + twice + '}').encode(), headers=JSON_TYPE)
    duplicate = "\"type\" appears more than once in geometry."
    if path in ("/api/mesh", "/api/run"):
        assert r.status_code == 400 and duplicate in r.json()["detail"] and "E-KEY-DUPLICATE" in r.json()["detail"]
        return
    assert r.status_code == 200, r.text
    reply = r.json()
    assert reply["ok"] is False
    found = [d for d in reply["diagnostics"] if d["code"] == "E-KEY-DUPLICATE"]
    assert len(found) == 1 and found[0]["path"].startswith("geometry.") and duplicate in found[0]["message"]


def test_a_surrogate_pair_is_text_and_comes_back_as_its_character(client, no_jobs):
    text = _compact(DOC).replace(f'"name":{json.dumps(DOC["name"])}', '"name":"core \\ud83d\\ude00"', 1)
    assert "\\ud83d" in text
    r = client.post("/api/validate", content=('{"doc":' + text + '}').encode(), headers=JSON_TYPE)
    assert r.status_code == 200 and r.json()["ok"] is True, r.text
    assert r.json()["doc"]["name"] == "core \U0001F600" and '"name":"core \U0001F600"'.encode() in r.content


@pytest.mark.parametrize("path", ["/api/validate", "/api/geometry-lab/evaluate"])
def test_document_routes_accept_a_utf8_byte_order_mark(client, no_jobs, path):
    source = GEOMETRY_DOC if path == "/api/geometry-lab/evaluate" else DOC
    body = '{"doc":' + _compact(source) + '}'
    plain = client.post(path, content=body.encode("utf-8"), headers=JSON_TYPE)
    marked = client.post(path, content=b"\xef\xbb\xbf" + body.encode("utf-8"), headers=JSON_TYPE)
    assert marked.status_code == plain.status_code == 200, marked.text
    assert marked.json()["ok"] is True and marked.content == plain.content


def _thermal_body(name, doc_text=None, tail='"client_revision":1,"request_seq":1'):
    doc_text = doc_text if doc_text is not None else _compact(examples.EXAMPLES[name])
    return ('{"doc":' + doc_text + ',' + tail + '}').encode("utf-8")


@pytest.mark.parametrize("path", sorted(THERMAL_ROUTES))
def test_thermal_routes_refuse_duplicates_and_non_finite_numbers(client, no_jobs, path):
    name = THERMAL_ROUTES[path]
    text = _compact(examples.EXAMPLES[name])
    cases = {
        "duplicate document key": (_thermal_body(name, text.replace('{"openphysics":', '{"name":"x","openphysics":', 1)),
                                   "duplicate JSON key"),
        "duplicate envelope key": (_thermal_body(name, tail='"client_revision":1,"request_seq":1,"request_seq":2'),
                                   "duplicate JSON key"),
        "NaN": (_thermal_body(name, text.replace('{"openphysics":', '{"x":NaN,"openphysics":', 1)),
                "JSON numbers must be finite"),
        "Infinity": (_thermal_body(name, tail='"client_revision":1,"request_seq":Infinity'),
                     "JSON numbers must be finite"),
        "beyond a double": (_thermal_body(name, text.replace('{"openphysics":', '{"x":1e999,"openphysics":', 1)),
                            "JSON numbers must be finite"),
        "UTF-16": ('{"doc":{}}'.encode("utf-16"), "malformed finite UTF-8 JSON"),
    }
    for case, (body, message) in cases.items():
        r = client.post(path, content=body, headers=JSON_TYPE)
        assert r.status_code == 400, (case, r.text)
        assert r.json()["error"]["code"] == "invalid_json" and r.json()["error"]["message"] == message, case


@pytest.mark.parametrize("path", ["/api/thermal/validate", "/api/thermal/transient/validate"])
def test_thermal_validation_accepts_a_utf8_byte_order_mark(client, no_jobs, path):
    body = _thermal_body(THERMAL_ROUTES[path])
    plain = client.post(path, content=body, headers=JSON_TYPE)
    marked = client.post(path, content=b"\xef\xbb\xbf" + body, headers=JSON_TYPE)
    assert marked.status_code == plain.status_code == 200, marked.text
    assert marked.json()["ok"] is True and marked.content == plain.content


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
    # Cut the one inline block out of the served bytes by plain search, independently of
    # the parser that built the header, and hash it.
    head, _, rest = served.content.partition(b"<script>")
    inline, _, tail = rest.partition(b"</script>")
    assert head and tail and b"<script>" not in tail
    expected = "'sha256-" + base64.b64encode(hashlib.sha256(inline).digest()).decode() + "'"
    assert re.findall(r"'sha256-[^']+'", served.headers["content-security-policy"]) == [expected]
    workspace = client.get("/workspace").text
    assert security.inline_scripts(workspace) == []  # only external and module scripts
    assert len(security.inline_scripts(served.text)) == 1


@pytest.mark.parametrize("page", ["index.html", "workspace.html"])
def test_shipped_pages_have_no_inline_handlers(page):
    from html.parser import HTMLParser

    handlers = []

    class Attrs(HTMLParser):
        def handle_starttag(self, tag, attrs):
            handlers.extend((tag, name) for name, _ in attrs if name.startswith("on"))
    Attrs().feed((server.STATIC / page).read_text(encoding="utf-8"))
    assert handlers == []


def test_inline_script_parser_matches_any_case_and_skips_src():
    html = '<SCRIPT>a\r\nb</SCRIPT ><script src="/x.js"></script><Script type="module">c</script>'
    assert security.inline_scripts(html) == ["a\r\nb", "c"]


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
