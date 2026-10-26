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
