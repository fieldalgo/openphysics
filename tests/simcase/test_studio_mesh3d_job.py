# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The Studio 3D mesh job (/api/model3d/mesh, /api/model3d/mesh/estimate, /api/model3d/jobs/...).

Pre-registered checks (fixed before implementation; never loosened):

- W9 (PR): documents at 0.5x, 0.99x and 1.5x the limit (``mesh.element_count_limit``): the
  ``I-MESH-ESTIMATE`` estimate is answered before meshing for all three, and the 1.5x document is
  refused (``E-MESH-ESTIMATE``, the estimate's words) before a process starts. 3/3.
- W8 (main pushes and manual dispatch; ``OPENPHYSICS_STUDIO_W8=1``): a mesh job estimated at
  >= 60 s, cancelled 3 s after it starts, against a real Studio server process: the child process
  has exited 2 s after Cancel; no result is kept; the server's RSS is within 50 MB of before.

Also tested, without numeric thresholds: the 429 path, that a cancelled job keeps nothing, that
the reuse key changes with the geometry or mesh block, and the surface answer of a finished job.
The process-level behaviour (Cancel's termination, meshloom's non-return, temporary directories,
a server that exits) is in test_studio_mesh3d_process.py, which needs no HTTP client and also runs
on macOS and Windows in platform-install.
"""
import base64
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pytest

import model3d_fixtures as F
import simcase

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

from simcase.studio import app, mesh3d_jobs, model3d_api  # noqa: E402

meshloom = pytest.importorskip("meshloom")
needs_kernel = pytest.mark.skipif(not meshloom.kernel_available(), reason="meshloom's compiled kernel is not built")
#: a bound on any wait here, so a broken job fails the test instead of hanging the suite
WAIT = 120.0


@pytest.fixture
def client():
    yield TestClient(app)
    model3d_api.jobs.shutdown()
    model3d_api.jobs.kept.clear()


def with_mesh(doc, **mesh):
    out = json.loads(json.dumps(doc))
    out["mesh"] = {**out.get("mesh", {}), **mesh}
    return out


def card(size=None, **mesh):
    doc = F.card()
    return with_mesh(doc, **({"element_size": size} if size else {}), **mesh)


def wait(client, job, until, limit=WAIT):
    t0 = time.monotonic()
    while True:
        status = client.get(f"/api/model3d/jobs/{job}").json()
        if until(status):
            return status
        assert time.monotonic() - t0 < limit, status
        time.sleep(0.05)


def arrays(view, key, dtype, width=1):
    a = np.frombuffer(base64.b64decode(view[key]), dtype=np.dtype(dtype).newbyteorder("<"))
    return a.reshape(-1, width) if width > 1 else a


# ----------------------------------------------------------------------------- the estimate

def test_w9_estimate_before_meshing_and_refusal_before_a_process(client, monkeypatch):
    """W9: at 0.5x, 0.99x and 1.5x the limit the estimate is answered first; 1.5x is refused
    before any process starts."""
    started = []
    monkeypatch.setattr(model3d_api.jobs, "_start_thread", lambda target, args: started.append(args))

    class NoProcess:                       # a process that is counted but never runs anything
        def __init__(self, *a, **k):
            pass
        pid = 1
        def start(self):
            started.append("process")
        def is_alive(self):
            return False
        def join(self, *a):
            pass
    real = model3d_api.jobs.ctx
    monkeypatch.setattr(model3d_api.jobs, "ctx", type("Ctx", (), {"Process": NoProcess, "Pipe": real.Pipe})())
    t = simcase.estimate_mesh3d(card()).tetrahedra
    passed = 0
    for factor in (0.5, 0.99, 1.5):
        doc = card(element_count_limit=round(t / factor))
        est = client.post("/api/model3d/mesh/estimate", json={"doc": doc}).json()
        before = model3d_api.jobs.processes_started
        reply = client.post("/api/model3d/mesh", json={"doc": doc})
        if factor < 1:
            ok = (est["ok"] and est["estimate"]["code"] == "I-MESH-ESTIMATE"
                  and est["estimate"]["tetrahedra"] == t and est["estimate"]["limit"] == round(t / factor)
                  and est["estimate"]["seconds"] == pytest.approx(t * 6e-4)
                  and reply.status_code == 200 and reply.json()["estimate"] == est["estimate"]
                  and model3d_api.jobs.processes_started == before + 1)
            client.post(f"/api/model3d/jobs/{reply.json()['job']}/cancel")
        else:
            words = f"about {t:.0f} tetrahedra from the element sizes"
            ok = (not est["ok"] and est["code"] == "E-MESH-ESTIMATE" and words in est["refused"]
                  and reply.status_code == 400 and reply.json()["code"] == "E-MESH-ESTIMATE"
                  and reply.json()["detail"] == est["refused"]
                  and model3d_api.jobs.processes_started == before)
        passed += bool(ok)
    assert passed == 3
    assert started.count("process") == 2


def test_refused_documents_answer_the_engine_s_words(client):
    doc = card()
    doc["geometry"]["components"]["stack3d"]["features"].append({"name": "c", "type": "circle", "r": 1})
    before = model3d_api.jobs.processes_started
    reply = client.post("/api/model3d/mesh", json={"doc": doc})
    est = client.post("/api/model3d/mesh/estimate", json={"doc": doc}).json()
    assert reply.status_code == 400 and reply.json()["detail"] == est["refused"]
    assert model3d_api.jobs.processes_started == before


# ----------------------------------------------------------------------------- the reuse key

def test_reuse_key_changes_with_the_geometry_or_mesh_block():
    base = card()
    key = mesh3d_jobs.reuse_key(base)
    assert key == mesh3d_jobs.reuse_key(json.loads(json.dumps(base)))
    renamed = {**json.loads(json.dumps(base)), "name": "another name"}
    assert mesh3d_jobs.reuse_key(renamed) == key            # only the geometry and mesh blocks count
    reordered = json.loads(json.dumps(base))
    reordered["mesh"] = {"element_size": "0.5 um"}
    reordered["geometry"] = dict(reversed(list(reordered["geometry"].items())))
    assert mesh3d_jobs.reuse_key(reordered) == key          # canonical: key order does not count
    moved = json.loads(json.dumps(base))
    moved["geometry"]["components"]["stack3d"]["features"][1]["xmax"] = 6.5
    assert mesh3d_jobs.reuse_key(moved) != key
    finer = card("0.4 um")
    assert mesh3d_jobs.reuse_key(finer) != key
    limited = card(element_count_limit=500000)
    assert mesh3d_jobs.reuse_key(limited) != key
    assert len({key, mesh3d_jobs.reuse_key(moved), mesh3d_jobs.reuse_key(finer), mesh3d_jobs.reuse_key(limited)}) == 4


# ----------------------------------------------------------------------------- jobs

@needs_kernel
def test_one_job_at_a_time_and_cancel_keeps_nothing(client):
    first = client.post("/api/model3d/mesh", json={"doc": card()})
    assert first.status_code == 200 and first.json()["status"] == "running"
    job = first.json()["job"]
    tmpdir = model3d_api.jobs.jobs[job].tmpdir
    assert Path(tmpdir).is_dir() and Path(tmpdir).name.startswith("openphysics-mesh3d-")
    second = client.post("/api/model3d/mesh", json={"doc": card("0.6 um")})
    assert second.status_code == 429
    assert second.json()["detail"] == "Studio is already meshing one 3D model; wait for it or cancel it."
    wait(client, job, lambda s: s["step"] == "meshing")
    process = model3d_api.jobs.jobs[job].process
    cancel = client.post(f"/api/model3d/jobs/{job}/cancel").json()
    assert cancel == {"job": job, "status": "cancelled", "cancelled": True,
                      "message": "Meshing cancelled; nothing kept.", "exited": True}
    assert not process.is_alive() and process.exitcode is not None
    status = client.get(f"/api/model3d/jobs/{job}").json()
    assert status["status"] == "cancelled" and status["error"]["message"] == "Meshing cancelled; nothing kept."
    assert not status["has_result"]
    assert client.get(f"/api/model3d/jobs/{job}/result").status_code == 409
    assert not Path(tmpdir).exists()
    assert model3d_api.jobs.kept == {} and model3d_api.jobs.kept_for(card(), "stack3d") is None
    time.sleep(0.3)                                     # the watcher has ended and kept nothing
    assert model3d_api.jobs.kept == {} and client.get(f"/api/model3d/jobs/{job}").json()["status"] == "cancelled"
    again = client.post("/api/model3d/mesh", json={"doc": card("0.6 um")})   # the slot is free again
    assert again.status_code == 200
    client.post(f"/api/model3d/jobs/{again.json()['job']}/cancel")
    assert client.post(f"/api/model3d/jobs/{job}/cancel").json()["cancelled"] is False


@needs_kernel
def test_a_finished_job_answers_the_surface_and_is_reused(client):
    doc = card("1 um")
    reply = client.post("/api/model3d/mesh", json={"doc": doc}).json()
    job = reply["job"]
    tmpdir = model3d_api.jobs.jobs[job].tmpdir
    steps = []
    status = wait(client, job, lambda s: steps.append(s["step"]) or s["status"] != "running")
    assert status["status"] == "done" and status["step"] == "ready" and status["has_result"]
    assert [s for i, s in enumerate(steps) if i == 0 or steps[i - 1] != s][-1] == "ready"
    assert set(steps) <= set(mesh3d_jobs.STEPS)
    assert not Path(tmpdir).exists()
    view = client.get(f"/api/model3d/jobs/{job}/result").json()
    display = model3d_api.display_view(doc)
    assert "tetrahedra" not in view and view["mesh"] is True and view["key"] == mesh3d_jobs.reuse_key(doc)
    assert [(f["id"], f["names"], f["axis"], f["at"]) for f in view["faces"]] == \
        [(f["id"], f["names"], f["axis"], f["at"]) for f in display["faces"]]
    positions = arrays(view, "positions", "f4", 3)
    triangles = arrays(view, "indices", "u4", 3)
    owner = arrays(view, "triangle_faces", "u4")
    regions = arrays(view, "triangle_regions", "i4")
    assert len(triangles) == len(owner) == len(regions) == view["counts"]["triangles"] == \
        view["stats"]["surface_triangles"]
    assert np.all(np.diff(owner.astype(np.int64)) >= 0)
    for f in view["faces"]:                              # every face is meshed, on its own plane
        mine = triangles[f["first_triangle"]:f["first_triangle"] + f["triangle_count"]]
        assert f["triangle_count"] > 0 and np.all(owner[f["first_triangle"]:f["first_triangle"] + len(mine)] == f["id"])
        a = "xyz".index(f["axis"])
        plane = f["at"] * view["metres_per_unit"] - view["origin_m"][a]
        assert np.allclose(positions[mine][:, :, a], plane, atol=1e-6 * view["metres_per_unit"])
    assert set(regions.tolist()) <= set(range(len(view["region_names"])))
    edges = arrays(view, "edge_indices", "u4", 2)
    assert len(edges) == view["counts"]["edges"] and edges.max() < len(positions)
    stats = view["stats"]
    assert stats["regions"] == 3 and stats["nodes"] > 0 and stats["tetrahedra"] > 0
    assert 0 < stats["quality_min"] <= stats["quality_median"] <= 1
    kept = model3d_api.jobs.kept_for(doc, "stack3d")
    assert kept is not None and len(kept.tetrahedra) == stats["tetrahedra"]
    started = model3d_api.jobs.processes_started
    again = client.post("/api/model3d/mesh", json={"doc": doc}).json()
    assert again["status"] == "done" and again["reused"] is True and model3d_api.jobs.processes_started == started
    assert client.get(f"/api/model3d/jobs/{again['job']}/result").json() == view
    changed = client.post("/api/model3d/mesh", json={"doc": card("0.9 um")}).json()
    assert changed["reused"] is False and model3d_api.jobs.processes_started == started + 1
    client.post(f"/api/model3d/jobs/{changed['job']}/cancel")


def test_job_ids_are_server_made(client):
    for job in ("nope", "m3d-0123456789ab", "m3d-../../etc", "M3D-0123456789AB"):
        for reply in (client.get(f"/api/model3d/jobs/{job}"), client.get(f"/api/model3d/jobs/{job}/result"),
                      client.post(f"/api/model3d/jobs/{job}/cancel")):
            assert reply.status_code == 404


# ----------------------------------------------------------------------------- W8

def _rss_bytes(pid: int) -> int:
    with open(f"/proc/{pid}/status", encoding="ascii") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    raise AssertionError("no VmRSS")


def _children(pid: int) -> set[int]:
    """The server's child processes, without the spawn context's resource tracker."""
    out = set()
    for task in Path(f"/proc/{pid}/task").iterdir():
        for child in (task / "children").read_text(encoding="ascii").split():
            try:
                cmdline = Path(f"/proc/{child}/cmdline").read_bytes()
            except FileNotFoundError:
                continue
            if b"resource_tracker" not in cmdline:
                out.add(int(child))
    return out


def _alive(pid: int) -> bool:
    try:
        state = Path(f"/proc/{pid}/stat").read_text(encoding="ascii").rsplit(")", 1)[1].split()[0]
    except FileNotFoundError:
        return False
    return state != "Z"


def _post(url, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST" if body is not None or url.endswith("/cancel") else "GET",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def w8_cancel_a_long_job_on_a_real_server(tmp_path):
    """W8: a job estimated >= 60 s, cancelled 3 s after it starts: the child has exited 2 s after
    Cancel, no result is kept, and the server's RSS is within 50 MB of before."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    log = open(tmp_path / "server.log", "w", encoding="utf-8")
    scratch = tmp_path / "tmp"                          # the server's temporary directories go here
    scratch.mkdir()
    env = {**os.environ, "TMPDIR": str(scratch)}
    server = subprocess.Popen([sys.executable, "-m", "simcase.studio", "--port", str(port), "--no-browser"],
                              stdout=log, stderr=subprocess.STDOUT, env=env)
    base = f"http://127.0.0.1:{port}"
    try:
        t0 = time.monotonic()
        while True:
            try:
                urllib.request.urlopen(base + "/api/model3d/display", timeout=5).read()
                break
            except OSError:
                assert server.poll() is None and time.monotonic() - t0 < 60, "the server did not start"
                time.sleep(0.2)
        doc = card("0.28 um")
        est = _post(base + "/api/model3d/mesh/estimate", {"doc": doc})["estimate"]
        assert est["seconds"] >= 60, est
        before = _rss_bytes(server.pid)
        reply = _post(base + "/api/model3d/mesh", {"doc": doc})
        job = reply["job"]
        start = time.monotonic()
        children = set()
        while time.monotonic() - start < 3.0:
            children |= _children(server.pid)
            time.sleep(0.1)
        assert _post(f"{base}/api/model3d/jobs/{job}")["status"] == "running"
        assert len(children) == 1, children
        (child,) = children
        assert _alive(child) and [p.name[:19] for p in scratch.iterdir()] == ["openphysics-mesh3d-"]
        _post(f"{base}/api/model3d/jobs/{job}/cancel")
        cancelled_at = time.monotonic()
        while _alive(child) and time.monotonic() - cancelled_at < 2.0:
            time.sleep(0.02)
        exited = not _alive(child)
        status = _post(f"{base}/api/model3d/jobs/{job}")
        after = _rss_bytes(server.pid)
        try:
            urllib.request.urlopen(f"{base}/api/model3d/jobs/{job}/result", timeout=10)
            kept = True
        except urllib.error.HTTPError as exc:
            kept = exc.code != 409
        record = {"estimate_s": est["seconds"], "exited_within_2_s": exited,
                  "rss_before_mb": before / 2 ** 20, "rss_after_mb": after / 2 ** 20,
                  "rss_change_mb": (after - before) / 2 ** 20, "status": status["status"], "kept": kept,
                  "files_left": sorted(p.name for p in scratch.iterdir())}
        print("W8", json.dumps(record))
        assert exited and status["status"] == "cancelled" and not status["has_result"] and not kept
        assert record["files_left"] == []
        assert abs(after - before) <= 50 * 2 ** 20, record
    finally:
        server.terminate()
        try:
            server.wait(10)
        except subprocess.TimeoutExpired:
            server.kill()
        log.close()


# ----------------------------------------------------------------------------- the page

def test_mesh_view_assets_and_the_lab_page(client):
    import re
    for name in ("model3d-mesh-view.mjs", "model3d-mesh-model.mjs"):
        reply = client.get("/model3d-assets/" + name)
        assert reply.status_code == 200 and reply.content == (F.STATIC / name).read_bytes()
        assert reply.headers["content-type"].startswith("text/javascript")
        text = reply.text
        assert "http" not in text and "import(" not in text and "eval(" not in text
    imports = lambda name: set(re.findall(r"""from\s*['"]([^'"]+)['"]""", (F.STATIC / name).read_text(encoding="utf-8")))
    assert imports("model3d-mesh-model.mjs") == set()
    assert imports("model3d-mesh-view.mjs") == {"/vendor/three-0.186.1/three.module.js", "/model3d-assets/model3d-view.mjs",
                                                 "/model3d-assets/model3d-model.mjs", "/model3d-assets/model3d-mesh-model.mjs"}
    assert {"/model3d-assets/model3d-mesh-view.mjs", "/model3d-assets/model3d-mesh-model.mjs"} <= \
        imports("geometry-lab-app.mjs")
    page = client.get("/geometry-lab").text
    for needle in ('id="mesh-start" disabled', '>Cancel meshing</button>', 'id="canvas-mesh" tabindex="0"',
                   'id="mesh-steps"', 'id="mesh-stats"'):
        assert needle in page
    assert "Stop" not in page.split('id="mesh3d"')[1].split("</section>")[0]   # Cancel is the one name


# W8 runs on main pushes and manual dispatch only (the validate.yml job studio-mesh3d-w8, Linux:
# it reads /proc). Elsewhere it is not collected, rather than skipped: the installed-package runs
# fail on any skip.
if os.environ.get("OPENPHYSICS_STUDIO_W8") == "1":
    test_w8_cancel_a_long_job_on_a_real_server = needs_kernel(w8_cancel_a_long_job_on_a_real_server)
