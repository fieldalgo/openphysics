# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Real steady boundary documents must remain headless in Studio."""

import copy
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from simcase import Document
from simcase.studio import server

def model(kind="flux-robin", *, save_fields=True):
    physics = {
        "type": "thermal.steady2d", "conductivity_w_mk": 2,
        "heat_source_w_m3": 0, "dirichlet_temperature_k": {"left": 300, "right": 293},
    }
    if kind == "empty-flux":
        physics["outward_flux_w_m2"] = {}
    elif kind == "empty-convection":
        physics["convection"] = {}
    elif kind in ("robin-only", "flux-robin", "negative"):
        physics["dirichlet_temperature_k"] = {"left": 300} if kind == "flux-robin" else {}
        physics["convection"] = {
            "right": {"h_w_m2k": 4, "ambient_temperature_k": 290}
        }
        if kind == "flux-robin":
            physics["outward_flux_w_m2"] = {"right": 2}
        elif kind == "negative":
            physics["outward_flux_w_m2"] = {"right": 50}
            physics["convection"]["right"] = {"h_w_m2k": 2, "ambient_temperature_k": 10}
    elif kind != "legacy":
        raise AssertionError(kind)
    return {
        "openphysics": "0.2", "name": "Steady boundary \u0394 \ud55c\uae00",
        "units": {"length": "m", "temperature": "K"},
        "geometry": {"domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}},
        "materials": {}, "physics": {"heat1": physics},
        "mesh": {"subdivisions": [2, 2]}, "study": {"type": "single"},
        "results": {"save_fields": save_fields, "plots": False},
    }



@pytest.mark.parametrize("kind", ["robin-only", "flux-robin", "empty-flux", "empty-convection"])
def test_real_boundary_document_is_refused_without_job_creation(monkeypatch, kind):
    data = model(kind)
    accepted = Document.from_dict(data)
    assert accepted.sole_physics()[1]["type"] == "thermal.steady2d"

    def forbidden(*args, **kwargs):
        raise AssertionError("headless boundary document reached Studio execution")

    monkeypatch.setattr(server, "run", forbidden)
    monkeypatch.setattr(server, "build_mesh", forbidden)
    monkeypatch.setattr(server, "uuid", SimpleNamespace(uuid4=forbidden))
    name = "steady_boundary_capability_probe"
    monkeypatch.setitem(server.examples.EXAMPLES, name, copy.deepcopy(data))
    with server._jobs_lock:
        before = copy.deepcopy(server._jobs)
    with TestClient(server.app) as client:
        response = client.post("/api/validate", json={"doc": data})
        assert response.status_code == 200
        assert set(response.json()) == {"ok", "error"}
        assert response.json()["ok"] is False
        assert "thermal.steady2d" in response.json()["error"]
        assert "headless" in response.json()["error"]
        for route in ("/api/mesh", "/api/run"):
            response = client.post(route, json={"doc": data})
            assert response.status_code == 400
            assert "thermal.steady2d" in response.json()["detail"]
            assert "headless" in response.json()["detail"]
        assert name not in client.get("/api/examples").json()["examples"]
        response = client.get(f"/api/examples/{name}")
        assert response.status_code == 400
        assert "thermal.steady2d" in response.json()["detail"]
    with server._jobs_lock:
        assert server._jobs == before
