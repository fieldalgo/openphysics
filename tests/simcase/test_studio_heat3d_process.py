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
