# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Studio capability guards remain independent of headless schema expansion."""

import copy

import pytest
from fastapi.testclient import TestClient

from simcase import Document, examples
from simcase.studio import server


class AcceptedDocument(dict):
    """A future schema-accepted document, without invoking a solver."""

    @property
    def data(self):
        return self

    notes = ()

    def summary(self):
        return "accepted headless document"


@pytest.mark.parametrize("physics_type", ["thermal.steady2d", "thermal.transient2d"])
@pytest.mark.parametrize("mixed", [False, True])
def test_headless_type_refused_after_schema_acceptance(monkeypatch, physics_type, mixed):
    # Isolate the Studio capability boundary from the evolving JSON contract:
    # a schema accepting a new type must never implicitly enable the UI.
    data = {"physics": {"heat": {"type": physics_type}}}
    if mixed:
        data["physics"]["optical"] = {"type": "em.modes2d"}
    monkeypatch.setattr(server.Document, "from_dict", lambda raw: AcceptedDocument(raw))

    def forbidden(*args, **kwargs):
        raise AssertionError("headless request entered Studio mesher/worker/job allocation")

    monkeypatch.setattr(server, "build_mesh", forbidden)
    monkeypatch.setattr(server, "run", forbidden)
    monkeypatch.setattr(server.uuid, "uuid4", forbidden)
    with server._jobs_lock:
        before = copy.deepcopy(server._jobs)
    client = TestClient(server.app)
    response = client.post("/api/validate", json={"doc": data})
    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert physics_type in response.json()["error"]
    assert "headless" in response.json()["error"]
    for route in ("/api/mesh", "/api/run"):
        response = client.post(route, json={"doc": data})
        assert response.status_code == 400
        assert physics_type in response.json()["detail"]
        assert "headless" in response.json()["detail"]
    with server._jobs_lock:
        assert server._jobs == before


def test_transient_example_is_not_exposed_by_studio(monkeypatch):
    name = "transient_capability_probe"
    data = {"physics": {"heat": {"type": "thermal.transient2d"}}}
    monkeypatch.setitem(server.examples.EXAMPLES, name, data)
    monkeypatch.setattr(server.Document, "from_dict", lambda raw: AcceptedDocument(raw))
    client = TestClient(server.app)
    assert name not in client.get("/api/examples").json()["examples"]
    response = client.get(f"/api/examples/{name}")
    assert response.status_code == 400
    assert "thermal.transient2d" in response.json()["detail"]


def test_optical_validation_still_uses_real_document_schema():
    client = TestClient(server.app)
    data = copy.deepcopy(examples.SLAB_TE_CHECK)
    response = client.post("/api/validate", json={"doc": data})
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert Document.from_dict(response.json()["doc"])["physics"]["em1"]["type"] == "em.modes2d"


@pytest.mark.parametrize(
    "example_name,sampled",
    [("thermal_slab", False), ("thermal_mixed", False),
     ("transient_thermal_uniform", False), ("transient_thermal_uniform", True)],
)
def test_real_headless_documents_rejected_without_schema_stub(monkeypatch, example_name, sampled):
    data = copy.deepcopy(examples.EXAMPLES[example_name])
    if sampled:
        physics = next(iter(data["physics"].values()))
        physics["dirichlet_temperature_k"] = {
            "left": {"values_k": [
                physics["initial_temperature_k"] + i
                for i in range(len(data["study"]["time_s"]))
            ]}
        }
    # The real public parser must accept the document before testing UI refusal.
    accepted = Document.from_dict(data)
    physics_type = accepted.sole_physics()[1]["type"]
    assert physics_type in ("thermal.steady2d", "thermal.transient2d")

    def forbidden(*args, **kwargs):
        raise AssertionError("valid headless document reached Studio execution")

    monkeypatch.setattr(server, "run", forbidden)
    monkeypatch.setattr(server, "build_mesh", forbidden)
    # Replace the server's module reference, not uuid functions used by the client.
    from types import SimpleNamespace
    monkeypatch.setattr(server, "uuid", SimpleNamespace(uuid4=forbidden))
    with server._jobs_lock:
        before = copy.deepcopy(server._jobs)
    client = TestClient(server.app)
    response = client.post("/api/validate", json={"doc": data})
    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert set(response.json()) == {"ok", "error"}
    assert physics_type in response.json()["error"]
    assert "headless" in response.json()["error"]
    for route in ("/api/mesh", "/api/run"):
        response = client.post(route, json={"doc": data})
        assert response.status_code == 400
        assert physics_type in response.json()["detail"]
        assert "headless" in response.json()["detail"]
    assert example_name not in client.get("/api/examples").json()["examples"]
    response = client.get(f"/api/examples/{example_name}")
    assert response.status_code == 400
    assert physics_type in response.json()["detail"]
    with server._jobs_lock:
        assert server._jobs == before
