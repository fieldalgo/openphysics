# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The Studio 3D heat run's mesh step, driven directly (``heat3d_runs.Heat3DRuns``, no HTTP).

What it checks on every platform (platform-install runs this file on Linux, macOS and Windows): Cancel
during a run's mesh step terminates the mesh job's spawn child within 2 s and removes its temporary
directory, and the run keeps nothing; a run on a kept mesh starts no process and solves. The routes
are tested in test_studio_heat3d_run.py, and W8 there.
"""
import copy
import json
import time
from pathlib import Path

import pytest

import model3d_fixtures as F

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from simcase.studio import heat3d_runs, mesh3d_jobs  # noqa: E402

meshloom = pytest.importorskip("meshloom")
needs_kernel = pytest.mark.skipif(not meshloom.kernel_available(), reason="meshloom's compiled kernel is not built")
WAIT = 120.0
MATERIALS = {"silicon": {"thermal_conductivity": "130 W/(m K)"},
             "silicon_dioxide": {"thermal_conductivity": "1.4 W/(m K)"},
             "copper": {"thermal_conductivity": "400 W/(m K)"}}


@pytest.fixture
def runs():
    meshes = mesh3d_jobs.Mesh3DJobs()
    store = heat3d_runs.Heat3DRuns(meshes)
    yield store
    store.shutdown()
    meshes.shutdown()


def card(size=None):
    doc = json.loads(json.dumps(F.card()))
    doc["materials"] = copy.deepcopy(MATERIALS)
    doc["physics"] = {"heat": {"type": "thermal.steady3d", "prescribed_temperature": {"z0": "300 K", "z1": "301 K"}}}
    if size:
        doc["mesh"]["element_size"] = size
    return doc


def wait(runs, run, until, limit=WAIT):
    t0 = time.monotonic()
    while True:
        status = runs.status(run)
        if until(status):
            return status
        assert time.monotonic() - t0 < limit, status
        time.sleep(0.05)


@needs_kernel
def test_cancel_in_the_mesh_step_ends_the_child_and_keeps_nothing(runs):
    reply = runs.start(card("0.3 um"))
    job = runs.meshes.jobs[reply["mesh_job"]]
    wait(runs, reply["run"], lambda s: runs.meshes.status(job.id)["step"] == "meshing")
    assert runs.status(reply["run"])["step"] == "mesh" and job.process.is_alive()
    t0 = time.monotonic()
    answer = runs.cancel(reply["run"])
    assert answer["cancelled"] and answer["step"] == "mesh" and answer["mesh"]["exited"] is True
    assert time.monotonic() - t0 < 2.0
    assert not job.process.is_alive() and not Path(job.tmpdir).exists()
    time.sleep(0.3)
    status = runs.status(reply["run"])
    assert status["status"] == "cancelled" and not status["has_result"] and runs.meshes.kept == {}
    with pytest.raises(mesh3d_jobs.Refused) as refused:
        runs.values(reply["run"])
    assert refused.value.status == 409


@needs_kernel
def test_a_run_meshes_once_then_reuses_the_kept_mesh(runs):
    first = runs.start(card("1 um"))
    assert wait(runs, first["run"], lambda s: s["status"] != "running")["status"] == "done"
    started = runs.meshes.processes_started
    again = card("1 um")
    again["physics"]["heat"]["prescribed_temperature"]["z1"] = "305 K"
    second = runs.start(again)
    assert second["reused"] is True and second["mesh_job"] is None
    status = wait(runs, second["run"], lambda s: s["status"] != "running")
    assert status["status"] == "done" and runs.meshes.processes_started == started
    assert runs.values(second["run"])["temperature_max"]["value"] == pytest.approx(305.0, abs=1e-9)


def e1_over_by_exact_count():
    """E1 (three slab layers, 10 x 10 x 2.5 mm) at 0.14 mm with the limit at 700,000: its lower bound
    (654,600) passes the estimate, its exact count (983,040) does not."""
    layers = [{"name": n, "thickness": t, "material": n} for n, t in (("lower", 1), ("core", 0.5), ("upper", 1))]
    return {"openphysics": "0.3",
            "geometry": {"version": 1, "components": {"pkg": {
                "dimension": "3d", "length_unit": "mm",
                "domain": {"xmin": 0, "xmax": 10, "ymin": 0, "ymax": 10, "zmin": 0, "zmax": 2.5},
                "background": {"material": None},
                "features": [{"name": "stack", "type": "layers", "z0": 0, "layers": layers}]}}},
            "mesh": {"element_size": "0.14 mm", "element_count_limit": 700000}}


@needs_kernel
def test_an_extrude_mesh_over_the_limit_is_refused_in_the_child_before_extruding():
    meshes = mesh3d_jobs.Mesh3DJobs()
    try:
        reply = meshes.start(e1_over_by_exact_count(), None)
        assert reply["estimate"]["count"] == "lower bound" and reply["estimate"]["route"] == "extrude"
        job = meshes.jobs[reply["job"]]
        t0 = time.monotonic()
        while meshes.status(job.id)["status"] == "running":
            assert time.monotonic() - t0 < WAIT
            time.sleep(0.05)
        status = meshes.status(job.id)
        assert status["status"] == "error"
        assert status["error"] == {"code": "E-MESH-ESTIMATE", "message": (
            "component 'pkg': 983040 tetrahedra on the extrude route (3 x footprint triangles x sub-layers); "
            "the limit is 700000 (mesh.element_count_limit)")}
        assert meshes.kept == {} and not Path(job.tmpdir).exists() and not job.process.is_alive()
    finally:
        meshes.shutdown()


def test_an_extrude_lower_bound_over_the_limit_is_refused_before_any_process():
    meshes = mesh3d_jobs.Mesh3DJobs()
    doc = e1_over_by_exact_count()
    doc["mesh"] = {"element_size": "0.01 mm"}
    with pytest.raises(mesh3d_jobs.Refused) as refused:
        meshes.start(doc, None)
    assert refused.value.status == 400 and refused.value.extra["code"] == "E-MESH-ESTIMATE"
    assert "at least " in refused.value.message and meshes.processes_started == 0 and meshes.jobs == {}
