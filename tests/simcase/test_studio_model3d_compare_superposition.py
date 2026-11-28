# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""C3-5: the analytical reference behind Studio 3D Compare. Raising every fixed temperature by 10 K
shifts the steady temperature by exactly 10 K everywhere and leaves each heat rate unchanged.

Card 2 (a copper via through a slab, 300 K on z0 and 301 K on z1) has no heat source. Steady
conduction with fixed temperatures only is linear in them, and a uniform shift of every one of them
is a constant solution of the homogeneous problem plus the original one. Run A is card 2, and run B
the same document with 310 K and 311 K, both through ``POST /api/model3d/run``.

Pre-registered thresholds (accepted before measuring):

- B reuses A's mesh. The two records share Compare's "same mesh": the geometry+mesh digest
  (``values.mesh.key``) and equal node and tetrahedron counts.
- max over the nodes of |T_B − T_A − 10 K| <= 1e-8 K (float64, the solver's own arrays).
- |q_B − q_A| <= 1e-9 |q_A| for each fixed temperature.
- The kept surface maps (float32, the run record's format) give ΔT within 2 float32 ulps at the
  surface temperatures of 10 K. This is the map Compare colours.

The measured values are printed (``-s``) for the report.
"""
import base64
import copy
import json
import time
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from simcase.studio import app, model3d_api  # noqa: E402

CARD2 = Path(model3d_api.__file__).parent / "static" / "model3d-via-slab-3d.json"
SHIFT = 10.0


@pytest.fixture
def client():
    yield TestClient(app)
    model3d_api.runs.shutdown()
    model3d_api.jobs.shutdown()
    model3d_api.jobs.kept.clear()
    model3d_api.runs.runs.clear()


def solved(client, doc):
    reply = client.post("/api/model3d/run", json={"doc": doc})
    assert reply.status_code == 200, reply.text
    run = reply.json()["run"]
    t0 = time.monotonic()
    while (status := client.get(f"/api/model3d/runs/{run}").json())["status"] == "running":
        assert time.monotonic() - t0 < 300, status
        time.sleep(0.05)
    assert status["status"] == "done", status
    return run, reply.json()


def surface_temperature(client, run):
    record = client.get(f"/api/model3d/runs/{run}/record", params={"maps": "kept"}).json()
    return record, np.frombuffer(base64.b64decode(record["surface"]["temperature"]), dtype="<f4")


def test_raising_every_fixed_temperature_by_10_k_shifts_the_field_by_10_k(client):
    a_doc = json.loads(CARD2.read_text(encoding="utf-8"))
    b_doc = copy.deepcopy(a_doc)
    fixed = b_doc["physics"]["heat"]["prescribed_temperature"]
    assert fixed == {"z0": "300 K", "z1": "301 K"} and "heat_source_density" not in b_doc["physics"]["heat"]
    b_doc["physics"]["heat"]["prescribed_temperature"] = {"z0": "310 K", "z1": "311 K"}

    run_a, _ = solved(client, a_doc)
    run_b, started = solved(client, b_doc)
    assert started["reused"] is True, "B runs on A's kept mesh"

    ra, rb = model3d_api.runs.get(run_a).result, model3d_api.runs.get(run_b).result
    assert np.array_equal(ra.mesh.nodes, rb.mesh.nodes) and np.array_equal(ra.mesh.tets, rb.mesh.tets)
    shift = np.abs(np.asarray(rb.temperature) - np.asarray(ra.temperature) - SHIFT).max()
    qa, qb = ra.heat_rates_by_boundary(), rb.heat_rates_by_boundary()
    assert set(qa) == set(qb) == {"z0", "z1"}
    rel = {k: abs(qb[k] - qa[k]) / abs(qa[k]) for k in qa}
    print(f"C3-5 max|T_B - T_A - 10 K| = {shift:.3e} K; |dq|/|q| = {rel}")
    assert shift <= 1e-8
    assert all(v <= 1e-9 for v in rel.values())

    # the records Compare reads: the same mesh by its rule, and the float32 surface maps
    rec_a, sa = surface_temperature(client, run_a)
    rec_b, sb = surface_temperature(client, run_b)
    ma, mb = rec_a["values"]["mesh"], rec_b["values"]["mesh"]
    assert (ma["key"], ma["nodes"], ma["tetrahedra"]) == (mb["key"], mb["nodes"], mb["tetrahedra"])
    assert sa.shape == sb.shape
    ulp = np.spacing(np.maximum(np.abs(sa), np.abs(sb)).astype(np.float32)).astype(np.float64)
    off = np.abs(sb.astype(np.float64) - sa.astype(np.float64) - SHIFT)
    print(f"C3-5 surface map: max|dT - 10 K| = {off.max():.3e} K ({(off / ulp).max():.2f} float32 ulps)")
    assert np.all(off <= 2 * ulp)
