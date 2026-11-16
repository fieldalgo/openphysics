# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Studio's list of installed physics providers (``GET /api/providers``): data only.

The listing is compared with ``simcase.providers.providers()`` itself, for the built-in
provider alone, with a fake provider injected the way test_providers.py injects one, and
with a provider that fails to load. The escaping of what the workspace shows is checked by
studio_workspace_providers.cjs."""
import json
import logging

import pytest

from simcase import providers

from test_providers import FakeEntryPoint, FakeProvider, _inject, fresh  # noqa: F401  (fixture)

KEYS = {"name", "version", "distribution", "protocol", "status", "error", "kinds"}
UNEXPECTED = "Studio failed unexpectedly; the details are in the server log"


@pytest.fixture
def client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from simcase.studio import app
    return TestClient(app)


def _expected():
    return [{"name": p.name, "version": p.version, "distribution": p.distribution, "protocol": p.protocol,
             "status": p.status, "error": p.error, "kinds": list(p.kinds)} for p in providers.providers()]


def _listing(client):
    response = client.get("/api/providers")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert set(response.json()) == {"providers"}
    listing = response.json()["providers"]
    for entry in listing:
        assert set(entry) == KEYS
    return listing


def test_builtin_provider_alone(client, fresh):
    _inject(fresh)
    listing = _listing(client)
    assert listing == _expected()
    assert len(listing) == 1
    builtin = listing[0]
    assert builtin["name"] == providers.BUILTIN == "openphysics-fem"
    assert builtin["distribution"] == "simcase"
    assert builtin["status"] == "available" and builtin["error"] is None
    assert builtin["protocol"] == providers.PROTOCOL
    assert {"em.modes2d", "thermal.steady2d", "electric_joule", "mechanics"} <= set(builtin["kinds"])


def test_installed_listing_matches_providers(client):
    """Whatever this environment has installed, the route lists exactly ``providers()``."""
    assert _listing(client) == _expected()


def test_fake_provider_is_listed_after_the_builtin(client, fresh):
    _inject(fresh, FakeEntryPoint("test-echo", FakeProvider))
    listing = _listing(client)
    assert listing == _expected()
    assert [p["name"] for p in listing] == ["openphysics-fem", "test-echo"]
    assert listing[1] == {"name": "test-echo", "version": "1.0", "distribution": "test-echo-dist",
                          "protocol": 1, "status": "available", "error": None, "kinds": ["test.echo"]}


def test_unavailable_provider_shows_its_error(client, fresh):
    _inject(fresh, FakeEntryPoint("broken", ImportError("No module named 'broken_physics'"), dist="broken-dist"),
            FakeEntryPoint("test-echo", FakeProvider),
            FakeEntryPoint("old-protocol", lambda: FakeProvider(name="old-protocol", protocol=99), dist="old-dist"))
    listing = _listing(client)
    assert listing == _expected()
    by_name = {p["name"]: p for p in listing}
    assert by_name["broken"] == {"name": "broken", "version": None, "distribution": "broken-dist", "protocol": None,
                                 "status": "unavailable", "kinds": [],
                                 "error": "ImportError: No module named 'broken_physics'"}
    assert by_name["old-protocol"]["status"] == "unavailable"
    assert by_name["old-protocol"]["error"] == next(p.error for p in providers.providers() if p.name == "old-protocol")
    assert "protocol 99" in by_name["old-protocol"]["error"]
    # the other providers still load
    assert by_name["test-echo"]["status"] == by_name["openphysics-fem"]["status"] == "available"


def test_a_failing_listing_replies_with_the_fixed_message(client, monkeypatch, caplog):
    def explode():
        raise RuntimeError("secret detail /home/someone/site-packages")
    from simcase.studio import server
    monkeypatch.setattr(server.providers, "providers", explode)
    with caplog.at_level(logging.WARNING, logger="simcase.studio"):
        response = client.get("/api/providers")
    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"detail": UNEXPECTED}
    assert "secret detail" not in response.text and "RuntimeError" not in response.text
    assert any(record.exc_info and "secret detail" in str(record.exc_info[1]) for record in caplog.records)


def test_the_route_keeps_the_host_check(client):
    assert client.get("/api/providers", headers={"Host": "evil.example"}).status_code == 403
    assert client.post("/api/providers").status_code == 405


def test_a_lone_surrogate_in_an_error_still_lists(client, fresh):
    """An error text read with surrogateescape (a non-UTF-8 path) is still valid JSON."""
    _inject(fresh, FakeEntryPoint("odd", ImportError("bad path /tmp/\udcff/x"), dist="odd-dist"))
    response = client.get("/api/providers")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    odd = response.json()["providers"][1]
    assert odd["status"] == "unavailable" and odd["error"] == "ImportError: bad path /tmp/\udcff/x"


_SHOW = """
const [module, listing] = process.argv.slice(1);
const {readProviders, providersHtml} = await import(module);
const list = readProviders(JSON.parse(listing));
process.stdout.write(JSON.stringify({count: list.length, html: providersHtml(list)}));
"""


def test_the_workspace_reads_every_listing_the_route_sends(client, fresh):
    """Route output with empty, long and odd-but-valid entries is shown by workspace-providers.mjs
    as it ships (installed or source), not refused; skipped without node."""
    import shutil
    import subprocess
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed; studio_workspace_providers.cjs runs in the cjs suite")
    from pathlib import Path
    import simcase.studio
    module = (Path(simcase.studio.__file__).parent / "static" / "workspace-providers.mjs").as_uri()
    long = "x" * 5000
    _inject(fresh, FakeEntryPoint("", ImportError("empty name"), dist="empty-dist"),
            FakeEntryPoint("long", ImportError(long), dist="long-dist"),
            FakeEntryPoint("version", lambda: FakeProvider(name="version", version=long), dist="v-dist"),
            FakeEntryPoint("huge", lambda: FakeProvider(name="huge", protocol=2 ** 60), dist="huge-dist"),
            FakeEntryPoint("hostile", ImportError("<img src=x onerror=alert(1)>"), dist="<b>dist</b>"),
            FakeEntryPoint("test-echo", FakeProvider))
    reply = client.get("/api/providers")
    listing = reply.json()["providers"]
    assert len(listing) == 7 and listing[0]["name"] == "openphysics-fem"
    done = subprocess.run([node, "--input-type=module", "-e", _SHOW, module, reply.text],
                          capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    shown = json.loads(done.stdout)
    assert shown["count"] == 7
    assert "openphysics-fem" in shown["html"] and "test-echo" in shown["html"]
    assert "&lt;img src=x onerror=alert(1)&gt;" in shown["html"] and "<img" not in shown["html"]
    assert "&lt;b&gt;dist&lt;/b&gt;" in shown["html"] and "<b>" not in shown["html"]
