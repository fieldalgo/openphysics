# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The Studio 3D mesh job's child process, driven directly (``mesh3d_jobs.Mesh3DJobs``, no HTTP).

What it checks on every platform (platform-install runs this file on Linux, macOS and Windows):
Cancel terminates the spawn child and removes its temporary directory, keeping nothing; a job in
meshloom's non-return (two boxes with a background strip 6e-8 of the domain diagonal wide between
them) is still meshing long past twice its estimate and ends within 2 s of Cancel; a finished job
leaves no directory; a server that exits mid-job leaves no child and no directory. It needs no HTTP
client: the routes are tested in test_studio_mesh3d_job.py, and W8 there.
"""
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

import model3d_fixtures as F

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from simcase.studio import mesh3d_jobs  # noqa: E402

meshloom = pytest.importorskip("meshloom")
needs_kernel = pytest.mark.skipif(not meshloom.kernel_available(), reason="meshloom's compiled kernel is not built")
#: a bound on any wait here, so a broken job fails the test instead of hanging the suite
WAIT = 120.0


@pytest.fixture
def jobs():
    store = mesh3d_jobs.Mesh3DJobs()
    yield store
    store.shutdown()


def card(size=None):
    doc = json.loads(json.dumps(F.card()))
    if size:
        doc["mesh"]["element_size"] = size
    return doc


def thin_strip():
    """Two boxes with a background strip 6e-8 of the domain diagonal wide between them: meshloom
    does not return on it (a known meshloom defect)."""
    gap = 6e-8 * math.sqrt(10 ** 2 + 10 ** 2 + 2.5 ** 2)
    x = float(f"{5 + gap:.12g}")
    return F.doc([{"name": "a", "type": "box", "xmin": 0, "xmax": 5, "ymin": 0, "ymax": 10, "zmin": 0, "zmax": 2.5,
                   "material": "m1"},
                  {"name": "b", "type": "box", "xmin": x, "xmax": 10, "ymin": 0, "ymax": 10, "zmin": 0, "zmax": 2.5,
                   "material": "m2"}], background="bg", size="2 mm")


def wait(jobs, job, until, limit=WAIT):
    t0 = time.monotonic()
    while True:
        status = jobs.status(job)
        if until(status):
            return status
        assert time.monotonic() - t0 < limit, status
        time.sleep(0.05)


@needs_kernel
def test_cancel_ends_the_child_and_keeps_nothing(jobs):
    reply = jobs.start(card(), None)
    job = jobs.jobs[reply["job"]]
    assert Path(job.tmpdir).is_dir() and Path(job.tmpdir).name.startswith("openphysics-mesh3d-")
    wait(jobs, job.id, lambda s: s["step"] == "meshing")
    t0 = time.monotonic()
    answer = jobs.cancel_job(job.id)
    assert answer == {"job": job.id, "status": "cancelled", "cancelled": True,
                      "message": "Meshing cancelled; nothing kept.", "exited": True}
    assert time.monotonic() - t0 < 2.0
    assert not job.process.is_alive() and job.process.exitcode is not None
    assert not Path(job.tmpdir).exists()
    time.sleep(0.3)                                     # the watcher has ended and kept nothing
    assert jobs.kept == {} and jobs.status(job.id)["status"] == "cancelled"
    with pytest.raises(mesh3d_jobs.Refused) as refused:
        jobs.result(job.id)
    assert refused.value.status == 409


@needs_kernel
def test_a_job_in_meshloom_s_non_return_is_cancellable(jobs):
    """The thin-strip reproducer: still meshing long past twice its estimate, then cancelled."""
    reply = jobs.start(thin_strip(), None)
    assert reply["estimate"]["seconds"] < 1
    job = jobs.jobs[reply["job"]]
    status = wait(jobs, job.id, lambda s: s["step"] == "meshing" and s["elapsed_s"] > 8, limit=60)
    assert status["status"] == "running" and status["longer_than_estimate"] is True
    t0 = time.monotonic()
    answer = jobs.cancel_job(job.id)
    took = time.monotonic() - t0
    assert answer["cancelled"] and answer["exited"] and took < 2.0, took
    assert not job.process.is_alive() and not Path(job.tmpdir).exists() and jobs.kept == {}


@needs_kernel
def test_a_finished_job_leaves_no_directory(jobs):
    reply = jobs.start(card("1 um"), None)
    job = jobs.jobs[reply["job"]]
    status = wait(jobs, job.id, lambda s: s["status"] != "running")
    assert status["status"] == "done" and status["step"] == "ready", status
    assert not Path(job.tmpdir).exists() and not job.process.is_alive()
    kept = jobs.kept_for(card("1 um"), "stack3d")
    assert kept is not None and len(kept.tetrahedra) == jobs.result(job.id)["stats"]["tetrahedra"]


EXITING = """
import json, sys, time
from pathlib import Path
from simcase.studio import mesh3d_jobs
import model3d_fixtures as F
if __name__ == "__main__":
    doc = F.card()
    doc["mesh"]["element_size"] = "0.3 um"
    jobs = mesh3d_jobs.Mesh3DJobs()
    reply = jobs.start(doc, None)
    while jobs.status(reply["job"])["step"] != "meshing":
        time.sleep(0.05)
    print(json.dumps({"pid": jobs.jobs[reply["job"]].pid}), flush=True)
    sys.exit(0)                                 # leave with the job running
"""


@needs_kernel
def test_a_server_that_exits_leaves_no_child_and_no_directory(tmp_path):
    script = tmp_path / "exiting.py"
    script.write_text(EXITING, encoding="utf-8")
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    env = {**os.environ, "TMPDIR": str(scratch), "TEMP": str(scratch), "TMP": str(scratch),
           "PYTHONPATH": os.pathsep.join([str(Path(F.__file__).parent), *sys.path])}
    done = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True, timeout=WAIT,
                          encoding="utf-8")
    assert done.returncode == 0, done.stderr
    pid = json.loads(done.stdout.strip().splitlines()[-1])["pid"]
    assert [p.name for p in scratch.iterdir() if p.name.startswith("openphysics-mesh3d-")] == []
    t0 = time.monotonic()
    while _process_exists(pid) and time.monotonic() - t0 < 5:
        time.sleep(0.05)
    assert not _process_exists(pid)


def _process_exists(pid: int) -> bool:
    if sys.platform == "win32":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)     # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == 259                                         # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    if sys.platform.startswith("linux"):
        try:
            return Path(f"/proc/{pid}/stat").read_text(encoding="ascii").rsplit(")", 1)[1].split()[0] != "Z"
        except FileNotFoundError:
            return False
    return True


def test_quality_measure_is_one_for_the_regular_tetrahedron():
    nodes = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1], [0, 0, 0.01]], dtype=float)
    q = mesh3d_jobs._quality(nodes, np.array([[0, 1, 2, 3], [0, 1, 2, 4]]))
    assert q[0] == pytest.approx(1.0, abs=1e-12) and 0 < q[1] < 1


def test_the_child_uses_the_spawn_context_and_temporary_directories():
    jobs = mesh3d_jobs.Mesh3DJobs()
    assert jobs.ctx.get_start_method() == "spawn"
    source = Path(mesh3d_jobs.__file__).read_text(encoding="utf-8")
    assert "get_context(\"spawn\")" in source and "tempfile.mkdtemp(" in source
