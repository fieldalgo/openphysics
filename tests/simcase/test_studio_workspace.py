# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Workspace transport and shipped resource contract; no new physics acceptance."""
import re
from pathlib import Path
import pytest
import simcase

WINDOW_UM = {'xmin': '-1.5 um', 'xmax': '1.5 um', 'ymin': '-1.2 um', 'ymax': '1.2 um'}
SETTINGS = {'domain': WINDOW_UM, 'boundary': 'PEC', 'mode_count': 2}


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
    # format 0.3 documents and section 5.3.4 results: the family's next adapter, quantity strings
    assert caps['schema_version']==1 and caps['adapter']=='optical-fixed-v2'
    assert caps['optical'] is True and caps['coupled'] is False
    assert caps['settings']==dict(core_height='220 nm',vacuum_wavelength='1550 nm',core_element_size='30 nm',
                                  domain=WINDOW_UM,boundary='PEC',mode_count=2)
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
    assert caps['adapter'] == 'optical-rectangle-v4'
    assert caps['core_height_range'] == ['100 nm', '500 nm']
    assert caps['coupled'] is False
    assert client.get('/api/workspace/capabilities').json()['settings']['core_height'] == '220 nm'



def test_optical_study_capability_v3_preserves_earlier_contracts(client):
    response = client.get('/api/workspace/capabilities/v3')
    caps = response.json()
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert caps['schema_version'] == 3
    assert caps['adapter'] == 'optical-rectangle-v5'
    assert caps['vacuum_wavelength_range'] == ['1400 nm', '1700 nm']
    assert caps['core_element_size_range'] == ['20 nm', '60 nm']
    assert caps['settings'] == SETTINGS
    assert caps['server_instance'] == client.get('/api/workspace/capabilities/v2').json()['server_instance']
    assert client.get('/api/workspace/capabilities/v2').json()['settings']['vacuum_wavelength'] == '1550 nm'


def test_shape_capability_v4_declares_shape_contract(client):
    response = client.get('/api/workspace/capabilities/v4')
    caps = response.json()
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert caps['schema_version'] == 4
    assert caps['adapter'] == 'optical-shapes-v6'
    assert caps['domain'] == {'xmin': '-1500 nm', 'xmax': '1500 nm', 'ymin': '-1200 nm', 'ymax': '1200 nm'}
    assert caps['max_shapes'] == 8 and caps['max_polygon_vertices'] == 12
    assert caps['shape_types'] == ['rect', 'circle', 'polygon']
    assert caps['materials'] == {'Silicon': 'physmat:Si', 'Silicon nitride': 'physmat:Si3N4',
                                 'Silica': 'physmat:SiO2', 'Air': 'physmat:vacuum'}
    assert caps['settings'] == SETTINGS
    assert caps['server_instance'] == client.get('/api/workspace/capabilities/v3').json()['server_instance']


def test_material_capability_v5_extends_v4_materials(client):
    v4 = client.get('/api/workspace/capabilities/v4').json()
    response = client.get('/api/workspace/capabilities/v5')
    caps = response.json()
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert caps['schema_version'] == 5 and caps['adapter'] == 'optical-shapes-v7'
    assert {k: v for k, v in caps['materials'].items() if k in v4['materials']} == v4['materials']
    assert caps['materials']['Lithium niobate (ordinary)'] == 'physmat:LiNbO3' and len(caps['materials']) == 10
    import physmat
    for name in caps['materials'].values():
        assert name.startswith('physmat:')                           # the exact names a document writes
        index = physmat.get(name.removeprefix('physmat:')).index([1.4, 1.55, 1.7])        # physmat's um
        assert (abs(index.imag) == 0).all() and (index.real >= 1).all()
    unchanged = {k: v for k, v in caps.items() if k not in ('schema_version', 'adapter', 'materials')}
    assert unchanged == {k: v for k, v in v4.items() if k not in ('schema_version', 'adapter', 'materials')}

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
