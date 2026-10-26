# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Workspace transport and shipped resource contract; no new physics acceptance."""
import re
from pathlib import Path
import pytest
import simcase

@pytest.fixture(scope="module")
def client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from simcase.studio import app
    return TestClient(app)

def test_workspace_is_separate_and_has_no_local_proxy_links(client):
    classic=client.get("/")
    assert classic.status_code==200
    assert 'href="/workspace"' in classic.text
    for path in ("/workspace", "/workspace/"):
        response=client.get(path)
        assert response.status_code==200
        assert '/workspace-assets/workspace-app.mjs' in response.text
        assert '127.0.0.1' not in response.text
        assert response.headers['cache-control']=='no-store'

def test_workspace_capabilities_preserve_existing_thermal_contract(client):
    response=client.get('/api/workspace/capabilities')
    caps=response.json()
    assert response.headers['cache-control']=='no-store'
    assert caps['simcase_version']==simcase.__version__
    assert caps['schema_version']==1 and caps['adapter']=='optical-fixed-v1'
    assert caps['optical'] is True and caps['coupled'] is False
    assert caps['settings']==dict(height_nm=220,wavelength_nm=1550,core_mesh_nm=30,window_um=[-1.5,1.5,-1.2,1.2],boundary='PEC',candidates=2)
    old=client.get('/api/capabilities').json()
    assert 'thermal.transient2d' in old
    assert 'schema_version' not in old

def test_every_workspace_import_is_shipped_and_served_with_explicit_mime(client):
    static=Path(simcase.__file__).parent/'studio'/'static'
    files=sorted(static.glob('workspace-*.mjs'))
    assert len(files)>=10
    for path in files:
        response=client.get('/workspace-assets/'+path.name)
        assert response.status_code==200
        assert response.content==path.read_bytes()
        assert response.headers['content-type'].startswith('text/javascript')
        assert response.headers['x-content-type-options']=='nosniff'
        for dependency in re.findall(r"from ['\"]\./([^'\"]+)['\"]",response.text):
            assert (static/dependency).is_file()
    assert client.get('/workspace-assets/workspace.css').headers['content-type'].startswith('text/css')
    for name in ('server.py','workspace-project.test.mjs','unknown.mjs','workspace.html'):
        assert client.get('/workspace-assets/'+name).status_code==404


def test_rectangle_capability_v2_preserves_v1(client):
    response = client.get('/api/workspace/capabilities/v2')
    caps = response.json()
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert caps['schema_version'] == 2
    assert caps['adapter'] == 'optical-rectangle-v2'
    assert caps['height_range_nm'] == [100, 500]
    assert caps['coupled'] is False
    assert client.get('/api/workspace/capabilities').json()['settings']['height_nm'] == 220



def test_optical_study_capability_v3_preserves_earlier_contracts(client):
    response = client.get('/api/workspace/capabilities/v3')
    caps = response.json()
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert caps['schema_version'] == 3
    assert caps['adapter'] == 'optical-rectangle-v3'
    assert caps['wavelength_range_nm'] == [1400, 1700]
    assert caps['core_mesh_range_nm'] == [20, 60]
    assert caps['settings'] == {'window_um': [-1.5, 1.5, -1.2, 1.2], 'boundary': 'PEC', 'candidates': 2}
    assert caps['server_instance'] == client.get('/api/workspace/capabilities/v2').json()['server_instance']
    assert client.get('/api/workspace/capabilities/v2').json()['settings']['wavelength_nm'] == 1550

def test_workspace_instance_is_stable_for_server_lifetime(client):
    caps = client.get('/api/workspace/capabilities/v2').json()
    assert re.fullmatch(r'[a-f0-9]{32}', caps['server_instance'])
    assert client.get('/api/workspace/capabilities/v2').json()['server_instance'] == caps['server_instance']


def test_workspace_job_requests_refuse_restarted_server(client):
    caps = client.get('/api/workspace/capabilities/v2').json()
    wrong = '0' * 32 if caps['server_instance'] != '0' * 32 else '1' * 32
    for endpoint in ('/api/jobs/1234abcd', '/api/jobs/1234abcd/result'):
        response = client.get(endpoint, params={'workspace_instance': wrong})
        assert response.status_code == 409
        assert 'restarted' in response.json()['detail']
        assert client.get(endpoint, params={'workspace_instance': caps['server_instance']}).status_code == 404
        assert client.get(endpoint).status_code == 404


@pytest.mark.parametrize("endpoint", ["/api/validate", "/api/mesh", "/api/run"])
def test_workspace_submission_rejects_restart_before_document_or_job_work(client, monkeypatch, endpoint):
    from simcase.studio import server
    calls = []
    monkeypatch.setattr(server.Document, "from_dict", lambda doc: calls.append(doc))
    response = client.post(endpoint, params={"workspace_instance": "stale-instance"}, json={"doc": {}})
    assert response.status_code == 409
    assert "restarted" in response.json()["detail"]
    assert calls == []


@pytest.mark.parametrize("extra,path,opens_browser", [
    ([], "/", True),
    (["--workspace"], "/workspace", True),
    (["--workspace", "--no-browser"], "/workspace", False),
])
def test_launcher_selects_landing_page_without_changing_server_routes(monkeypatch, capsys, extra, path, opens_browser):
    from simcase.studio import server
    import uvicorn
    import webbrowser

    opened, served = [], []

    class ImmediateTimer:
        def __init__(self, delay, callback):
            self.callback = callback

        def start(self):
            self.callback()

    monkeypatch.setattr(server.threading, "Timer", ImmediateTimer)
    monkeypatch.setattr(webbrowser, "open", opened.append)
    monkeypatch.setattr(uvicorn, "run", lambda app, **options: served.append((app, options)))
    server.main(["--host", "127.0.0.1", "--port", "9876", *extra])
    url = "http://127.0.0.1:9876" + path
    assert opened == ([url] if opens_browser else [])
    assert url in capsys.readouterr().out
    assert served == [(server.app, {"host": "127.0.0.1", "port": 9876, "log_level": "warning"})]
