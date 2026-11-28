# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""U3: ``GET /api/model3d/runs/{id}/extremes`` names the regions around Tmin and Tmax's node.

The answer is ``{"run", "temperature_min": {"node", "regions"}, "temperature_max": {...}}``: the distinct
region names of the tetrahedra that share the node, in the mesh's region order, from the mesh the
server holds (an HTTP view, F5). ``/values``, the run.json export and the stored record (format
thermal-steady3d-run-v1, F3) are unchanged. A run the server does not hold (unknown, or reopened
from a file before Recompute) is refused in the run routes' words (404, "no such 3D heat run").
"""
import json
import time

import numpy as np
import pytest

import simcase

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

from simcase.studio import app, model3d_api  # noqa: E402

CARD = __import__("pathlib").Path(simcase.__file__).parent / "studio" / "static" / "model3d-layer-stack-3d.json"


@pytest.fixture(scope="module")
def client():
    yield TestClient(app)
    model3d_api.runs.shutdown()
    model3d_api.jobs.shutdown()


def solved(client, doc):
    run_id = client.post("/api/model3d/run", json={"doc": doc}).json()["run"]
    for _ in range(600):
        if client.get(f"/api/model3d/runs/{run_id}").json()["status"] != "running":
            break
        time.sleep(0.2)
    return run_id


def test_extremes_name_the_regions_around_the_nodes_of_a_held_run(client):
    doc = json.loads(CARD.read_text(encoding="utf-8"))
    doc["physics"]["heat"]["prescribed_temperature"] = {"z0": "300 K", "z1": "300 K"}   # Tmax on SiO2 / Si (top)
    run_id = solved(client, doc)
    values = client.get(f"/api/model3d/runs/{run_id}/values").json()
    extremes = client.get(f"/api/model3d/runs/{run_id}/extremes").json()
    mesh = model3d_api.runs.get(run_id).result.mesh
    assert extremes["run"] == run_id
    for key in ("temperature_min", "temperature_max"):
        node = values[key]["node"]
        ids = sorted({int(r) for r in mesh.regions[np.any(mesh.tets == node, axis=1)]})
        assert extremes[key] == {"node": node, "regions": [mesh.region_names[i] for i in ids]}
        assert values[key]["region"] in extremes[key]["regions"]
        assert "regions" not in values[key], "/values is unchanged"
    assert extremes["temperature_max"]["regions"] == ["SiO2", "Si (top)"]
    record = client.get(f"/api/model3d/runs/{run_id}/record").json()
    assert record["values"] == values, "the stored record (F3) is unchanged"


def test_a_run_the_server_does_not_hold_is_refused(client):
    for run_id in ("h3d-000000000000", "not-a-run"):
        reply = client.get(f"/api/model3d/runs/{run_id}/extremes")
        assert reply.status_code == 404 and reply.json()["detail"] == "no such 3D heat run"
