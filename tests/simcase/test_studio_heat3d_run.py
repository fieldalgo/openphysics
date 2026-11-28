# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The Studio 3D steady-heat run (``POST /api/model3d/run``, ``/api/model3d/runs/...``).

Pre-registered checks (fixed before implementation; never loosened; decision
2026-11-27-openphysics-studio-3d-run-route):

- W6-E1 (PR): E1 (three slab layers, the meshine.extrude route) through ``POST /api/model3d/run``
  against ``meshine.extrude`` + ``galerkin.solve_steady_heat_3d`` called directly on the same
  document: SHA-256 of the nodes, tetrahedra, temperature and reaction heat rate identical.
- W6-card (PR): the ``layer-stack-3d`` card (the meshloom route) through the same route against
  ``build_mesh3d`` + ``solve_steady_heat_3d`` called directly: the same SHA-256 identical.
- W7 (PR): E1 through the route against ``refsol.thermal3d.layered_slab``: max nodal |T_h - T| <= 1e-10
  and the top heat rate (``heat_rate_by_selection.z1``) within a relative 1e-9.
- W17 (PR), through the route: the cut-plane export (``cut.csv``) of E1 at z = 1.2345 mm against the
  exact rational P1 slice of test_studio_heat3d_slice: same points, max |T - T_exact| <= 1e-12 K.
- W14 (recorded only): the time and size of the surface map and of a cut, on the card at PR; at the
  largest mesh (the card at an estimate near the limit) with ``OPENPHYSICS_STUDIO_W14=1``.
- W8 (main pushes and manual dispatch; ``OPENPHYSICS_STUDIO_W8=1``): a run whose mesh step is
  estimated at >= 60 s, cancelled 3 s after it starts, on a real Studio server: its child process has
  exited 2 s after Cancel, the run is cancelled and nothing is kept.

Also tested, without numeric thresholds: refusals before any process (the document, the kind, the
estimate limit), the 429s (a run while a run or a mesh job runs), the reuse of a kept mesh (no new
process), a connected region group with no fixed temperature refused by its region names, the
probe, the values, the exports' headers and the run record.
"""
import base64
import copy
import csv
import hashlib
import io
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from simcase.studio import app, heat3d_runs, model3d_api  # noqa: E402

STATIC = Path(model3d_api.__file__).parent / "static"
WAIT = 300.0
# E1 (tests/simcase/test_thermal_steady3d.py), restated so that this file can run from a copy
K = {"lower": 1.0, "core": 0.01, "upper": 1.0}
LEVELS_MM = [0, 1, 1.5, 2.5]


def e1(h_mm=0.8, *, physics=None, features=None):
    feats = [{"name": "stack", "type": "layers", "z0": 0, "layers": [
        {"name": "a", "thickness": 1, "material": "lower"}, {"name": "b", "thickness": 0.5, "material": "core"},
        {"name": "c", "thickness": 1, "material": "upper"}]}] + (features or [])
    return {"openphysics": "0.3", "name": "E1",
            "geometry": {"version": 1, "components": {"pkg": {
                "dimension": "3d", "length_unit": "mm",
                "domain": {"xmin": 0, "xmax": 10, "ymin": 0, "ymax": 10, "zmin": 0, "zmax": 2.5},
                "background": {"material": None}, "features": feats}}},
            "materials": {"lower": {"thermal_conductivity": "1 W/(m K)"},
                          "core": {"thermal_conductivity": "0.01 W/(m K)"},
                          "upper": {"thermal_conductivity": "1 W/(m K)"},
                          "cu": {"thermal_conductivity": "400 W/(m K)"}},
            "physics": {"heat": physics or {"type": "thermal.steady3d",
                                            "prescribed_temperature": {"z0": "300 K", "z1": "301 K"}}},
            "mesh": {"element_size": f"{h_mm} mm"}}


CARD_PHYSICS = {"type": "thermal.steady3d", "prescribed_temperature": {"z0": "300 K", "z1": "310 K"},
                "heat_source_density": {"via": "1e12 W/m^3"}}
CARD_KAPPA = {"Si": 130.0, "SiO2": 1.4, "via": 400.0}


def card(size=None):
    doc = json.loads((STATIC / "model3d-layer-stack-3d.json").read_text(encoding="utf-8"))
    doc["physics"] = {"heat": copy.deepcopy(CARD_PHYSICS)}
    if size:
        doc["mesh"]["element_size"] = size
    return doc


@pytest.fixture
def client():
    yield TestClient(app)
    model3d_api.runs.shutdown()
    model3d_api.jobs.shutdown()
    model3d_api.jobs.kept.clear()
    model3d_api.runs.runs.clear()


def wait(client, run, limit=WAIT):
    t0 = time.monotonic()
    while True:
        status = client.get(f"/api/model3d/runs/{run}").json()
        if status["status"] != "running":
            return status
        assert time.monotonic() - t0 < limit, status
        time.sleep(0.05)


def solved(client, doc):
    reply = client.post("/api/model3d/run", json={"doc": doc})
    assert reply.status_code == 200, reply.text
    status = wait(client, reply.json()["run"])
    assert status["status"] == "done", status
    return reply.json()["run"], status


def sha(nodes, tets, temperature, reaction):
    h = hashlib.sha256()
    for a in (np.asarray(nodes, dtype=float), np.asarray(tets, dtype=np.int64),
              np.asarray(temperature, dtype=float), np.asarray(reaction, dtype=float)):
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


def server_sha(run_id):
    r = model3d_api.runs.get(run_id).result
    return sha(r.mesh.nodes, r.mesh.tets, r.temperature, r.reaction_heat_rate)


def b64(view, key, dtype, width=1):
    a = np.frombuffer(base64.b64decode(view[key]), dtype=np.dtype(dtype).newbyteorder("<"))
    return a.reshape(-1, width) if width > 1 else a


# ----------------------------------------------------------------------------- W6, W7

def direct_extrude(data):
    """E1 by hand: the domain rectangle meshed by meshine, extruded through the levels, solved."""
    from galerkin import from_mesher
    from galerkin.thermal3d import solve_steady_heat_3d
    from meshine import Domain, box_sides, extrude, generate, rectangle
    h = float(Fraction(8, 10) / 1000)
    d = Domain(size=h)
    d.add_region("plate", rectangle(0.0, 0.0, 0.01, 0.01))
    footprint = generate(d, box_sides(0.0, 0.01, 0.0, 0.01))
    table = {"plate": ["lower", "core", "upper"]}
    mesh = from_mesher(extrude(footprint, [z / 1000 for z in LEVELS_MM],
                               {r: table["plate"] for r in footprint.region_names}, size=h))
    fixed = {int(n): 300.0 for n in np.unique(mesh.boundary["z0"])}
    fixed.update({int(n): 301.0 for n in np.unique(mesh.boundary["z1"])})
    solution = solve_steady_heat_3d(mesh, thermal_conductivity={r: K[r] for r in mesh.region_names},
                                    prescribed_temperature=dict(sorted(fixed.items())))
    return mesh, solution


def direct_meshloom(data):
    from galerkin.thermal3d import solve_steady_heat_3d
    from simcase import build_mesh3d
    mesh = build_mesh3d(data).mesh
    fixed = {int(n): 300.0 for n in np.unique(mesh.tagged_faces["z0"])}
    fixed.update({int(n): 310.0 for n in np.unique(mesh.tagged_faces["z1"])})
    solution = solve_steady_heat_3d(mesh, thermal_conductivity={r: CARD_KAPPA[r] for r in mesh.region_names},
                                    prescribed_temperature=dict(sorted(fixed.items())),
                                    heat_source_density={r: (1e12 if r == "via" else 0.0) for r in mesh.region_names})
    return mesh, solution


def test_w6_e1_through_the_route_equals_extrude_and_the_solver_called_directly(client):
    data = e1()
    run_id, status = solved(client, copy.deepcopy(data))
    assert status["route"] == "extrude"
    mesh, solution = direct_extrude(data)
    got, expected = server_sha(run_id), sha(mesh.nodes, mesh.tets, solution.temperature, solution.reaction_heat_rate)
    print("W6-E1", json.dumps({"route": got, "direct": expected}))
    assert got == expected


def test_w6_card_through_the_route_equals_build_mesh3d_and_the_solver_called_directly(client):
    data = card()
    run_id, status = solved(client, copy.deepcopy(data))
    assert status["route"] == "meshloom"
    mesh, solution = direct_meshloom(data)
    got, expected = server_sha(run_id), sha(mesh.nodes, mesh.tets, solution.temperature, solution.reaction_heat_rate)
    print("W6-card", json.dumps({"route": got, "direct": expected}))
    assert got == expected


def test_w7_e1_through_the_route_is_exact(client):
    from refsol.thermal3d import layered_slab
    run_id, _ = solved(client, e1())
    r = model3d_api.runs.get(run_id).result
    exact = layered_slab(r.mesh.nodes, position=[z * 1e-3 for z in LEVELS_MM], thermal_conductivity=list(K.values()),
                         prescribed_temperature=(300.0, 301.0))
    error = float(np.max(np.abs(r.temperature - exact.temperature)))
    values = client.get(f"/api/model3d/runs/{run_id}/values").json()
    rate = values["heat_rate_by_selection"]["z1"]["value"]
    expected = float(-exact.heat_flux[0, 2]) * 1e-4
    print("W7", json.dumps({"max_error_K": error, "top_rate_W": rate, "exact_W": expected,
                            "relative": abs(rate - expected) / abs(expected)}))
    assert error <= 1e-10
    assert abs(rate - expected) <= 1e-9 * abs(expected)


# ----------------------------------------------------------------------------- W17 through the route

def exact_slice(nodes, tets, T, axis, c):
    a = "xyz".index(axis)
    out = {}
    for tet in tets.tolist():
        x = [Fraction(float(nodes[n, a])) - c for n in tet]
        if not (min(x) <= 0 <= max(x)) or all(v == 0 for v in x) or (sum(v == 0 for v in x) < 3 and
                                                                     (min(x) == 0 or max(x) == 0)):
            continue
        for i in range(4):
            if x[i] == 0:
                out[tuple(Fraction(float(v)) for v in nodes[tet[i]])] = Fraction(float(T[tet[i]]))
            for j in range(i + 1, 4):
                if x[i] * x[j] < 0:
                    t = x[i] / (x[i] - x[j])
                    pi = [Fraction(float(v)) for v in nodes[tet[i]]]
                    pj = [Fraction(float(v)) for v in nodes[tet[j]]]
                    ti, tj = Fraction(float(T[tet[i]])), Fraction(float(T[tet[j]]))
                    out[tuple(pi[k] + t * (pj[k] - pi[k]) for k in range(3))] = ti + t * (tj - ti)
    return out


def test_w17_the_cut_export_is_the_exact_p1_slice(client):
    run_id, _ = solved(client, e1())
    reply = client.get(f"/api/model3d/runs/{run_id}/export/cut.csv", params={"axis": "z", "at": "1.2345"})
    assert reply.status_code == 200, reply.text
    lines = reply.text.splitlines()
    header = [line for line in lines if line.startswith("#")]
    assert header[0] == "# cut plane: z = 1.2345 mm (0.0012345 m)"
    assert header[1] == f"# run: {run_id}"
    assert header[2].startswith("# document_sha256: ") and len(header[2].split()[-1]) == 64
    rows = list(csv.reader(io.StringIO("\n".join(line for line in lines if not line.startswith("#")))))
    assert rows[0] == ["x_m", "y_m", "z_m", "temperature_K"]
    got = np.array([[float(v) for v in row] for row in rows[1:]])
    r = model3d_api.runs.get(run_id).result
    exact = exact_slice(np.asarray(r.mesh.nodes), np.asarray(r.mesh.tets), np.asarray(r.temperature), "z",
                        Fraction(float(Fraction("1.2345") / 1000)))
    keys = list(exact)
    ref = np.array([[float(v) for v in p] for p in keys])
    assert len(got) == len(keys)
    worst, seen = 0.0, set()
    for row in got:
        d = np.abs(ref - row[:3]).max(axis=1)
        i = int(np.argmin(d))
        assert d[i] <= 1e-15
        seen.add(i)
        worst = max(worst, abs(float(Fraction(float(row[3])) - exact[keys[i]])))
    print("W17-route", json.dumps({"points": len(keys), "max_error_K": worst}))
    assert len(seen) == len(keys) and worst <= 1e-12


# ----------------------------------------------------------------------------- answers

def test_values_answers_and_exports(client):
    data = card()
    run_id, status = solved(client, data)
    assert status["steps"] == ["mesh", "solve", "done"] and status["step"] == "done"
    values = client.get(f"/api/model3d/runs/{run_id}/values").json()
    r = model3d_api.runs.get(run_id).result
    assert set(values["heat_rate_by_selection"]) == {"z0", "z1"}
    total = sum(v["value"] for v in values["heat_rate_by_selection"].values())
    assert values["total_source"]["value"] == float(np.sum(r.solution.generated_heat_rate))
    assert abs(values["balance_residual"]["value"] - (-total - values["total_source"]["value"])) <= \
        1e-12 * abs(values["total_source"]["value"])
    tmax = values["temperature_max"]
    assert tmax["value"] == float(r.temperature.max())
    assert tmax["position_m"] == r.mesh.nodes[int(np.argmax(r.temperature))].tolist()
    assert tmax["region"] in CARD_KAPPA
    assert values["mesh"]["route"] == "meshloom" and values["mesh"]["tetrahedra"] == len(r.mesh.tets)
    # the surface map: float32 positions, triangles with face ids, T at the surface nodes
    surface = client.get(f"/api/model3d/runs/{run_id}/surface").json()
    pos = b64(surface, "positions", "f4", 3)
    tri = b64(surface, "indices", "u4", 3)
    t_surface = b64(surface, "temperature", "f4")
    assert len(t_surface) == len(pos) and tri.max() < len(pos)
    assert len(b64(surface, "triangle_faces", "u4")) == len(tri)
    assert not {"tetrahedra", "nodes", "tets"} & set(surface)
    origin = np.asarray(surface["origin_m"])
    k = int(np.argmax(t_surface))
    node = int(np.argmin(np.abs(r.mesh.nodes - (pos[k].astype(float) + origin)).sum(axis=1)))
    assert abs(float(t_surface[k]) - r.temperature[node]) <= 1e-4
    # the cut and the probe (document units: um)
    cut = client.post(f"/api/model3d/runs/{run_id}/cut", json={"axis": "z", "at": 505}).json()
    assert cut["ok"] and cut["axis"] == "z" and cut["at"] == 505 and cut["unit"] == "um"
    assert len(b64(cut, "temperature", "f4")) == cut["counts"]["points"]
    probe = client.post(f"/api/model3d/runs/{run_id}/probe", json={"point": [100, 100, 505]}).json()
    assert probe["ok"] and probe["region"] == "via"
    assert probe["point"] == [100, 100, 505] and probe["point_m"] == [1e-4, 1e-4, 5.05e-4]
    outside = client.post(f"/api/model3d/runs/{run_id}/probe", json={"point": [100, 100, 700]}).json()
    assert not outside["ok"] and "outside" in outside["refused"]
    # exports
    surface_csv = client.get(f"/api/model3d/runs/{run_id}/export/surface.csv")
    rows = [line for line in surface_csv.text.splitlines() if not line.startswith("#")]
    assert rows[0] == "x_m,y_m,z_m,temperature_K,face"
    run_json = client.get(f"/api/model3d/runs/{run_id}/export/run.json").json()
    assert run_json["document"] == data and run_json["values"] == values
    record = client.get(f"/api/model3d/runs/{run_id}/record").json()
    assert record["result"] == "thermal-steady3d-run-v1" and record["maps"] == "kept"
    assert record["document_sha256"] == values["document_sha256"] and record["surface"] == surface
    bare = client.get(f"/api/model3d/runs/{run_id}/record", params={"maps": "not kept"}).json()
    assert bare["maps"] == "not kept" and "surface" not in bare and bare["counts"]["surface_triangles"] == len(tri)


def test_a_kept_mesh_is_reused_without_a_process(client):
    data = card()
    first, _ = solved(client, data)
    started = model3d_api.jobs.processes_started
    again = copy.deepcopy(data)
    again["physics"]["heat"]["prescribed_temperature"]["z1"] = "320 K"     # the mesh blocks are unchanged
    reply = client.post("/api/model3d/run", json={"doc": again}).json()
    assert reply["reused"] is True
    status = wait(client, reply["run"])
    assert status["status"] == "done" and status["reused"] is True
    assert model3d_api.jobs.processes_started == started
    # a mesh made by the Mesh button is reused too, and Mesh now takes E1 (the extrude route)
    mesh = client.post("/api/model3d/mesh", json={"doc": e1()}).json()
    t0 = time.monotonic()
    while client.get(f"/api/model3d/jobs/{mesh['job']}").json()["status"] == "running":
        assert time.monotonic() - t0 < WAIT
        time.sleep(0.05)
    assert client.get(f"/api/model3d/jobs/{mesh['job']}").json()["status"] == "done"
    assert client.post("/api/model3d/run", json={"doc": e1()}).json()["reused"] is True


def test_refusals_before_any_process(client):
    started = model3d_api.jobs.processes_started
    not_heat = card()
    del not_heat["physics"]
    for doc, words in [(not_heat, "thermal.steady3d"),
                       (card("0.5 um"), "element_count_limit"),
                       ({**card(), "materials": {}}, "materials")]:
        reply = client.post("/api/model3d/run", json={"doc": doc})
        assert reply.status_code == 400, reply.text
        assert words in reply.json()["detail"], reply.json()
    assert model3d_api.jobs.processes_started == started


def test_a_group_with_no_fixed_temperature_is_refused_by_its_regions(client):
    boxes = [{"name": "A", "type": "box", "xmin": 0, "xmax": 4, "ymin": 0, "ymax": 10, "zmin": 0, "zmax": 2.5,
              "material": "lower"},
             {"name": "B", "type": "box", "xmin": 6, "xmax": 10, "ymin": 0, "ymax": 10, "zmin": 0, "zmax": 2.5,
              "material": "upper"}]
    data = e1(physics={"type": "thermal.steady3d", "prescribed_temperature": {"x0": "300 K"}})
    data["geometry"]["components"]["pkg"]["features"] = boxes
    reply = client.post("/api/model3d/run", json={"doc": data})
    assert reply.status_code == 200, reply.text
    status = wait(client, reply.json()["run"])
    assert status["status"] == "error"
    assert status["error"]["message"] == heat3d_runs.UNANCHORED.format(regions="'B'"), status


def test_one_run_at_a_time_and_ids(client):
    slow = card("11 um")
    first = client.post("/api/model3d/run", json={"doc": slow}).json()
    assert client.post("/api/model3d/run", json={"doc": e1()}).status_code == 429
    assert client.post("/api/model3d/mesh", json={"doc": e1()}).status_code == 429
    client.post(f"/api/model3d/runs/{first['run']}/cancel")
    assert wait(client, first["run"])["status"] == "cancelled"
    for run in ("nope", "h3d-0123456789ab", "h3d-../../etc"):
        assert client.get(f"/api/model3d/runs/{run}").status_code == 404
        assert client.get(f"/api/model3d/runs/{run}/values").status_code == 404


# ----------------------------------------------------------------------------- W14

def _w14(client, doc, label):
    t0 = time.perf_counter()
    run_id, status = solved(client, doc)
    run_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    surface = client.get(f"/api/model3d/runs/{run_id}/surface")
    surface_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    cut = client.post(f"/api/model3d/runs/{run_id}/cut", json={"axis": "z", "at": 505})
    cut_s = time.perf_counter() - t0
    values = client.get(f"/api/model3d/runs/{run_id}/values").json()
    record = {"case": label, "tetrahedra": values["mesh"]["tetrahedra"], "run_s": round(run_s, 3),
              "surface_s": round(surface_s, 4), "surface_bytes": len(surface.content),
              "cut_s": round(cut_s, 4), "cut_bytes": len(cut.content)}
    print("W14", json.dumps(record))
    return record


def test_w14_the_card_s_surface_and_cut_are_recorded(client):
    _w14(client, card(), "card 40 um")


if os.environ.get("OPENPHYSICS_STUDIO_W14") == "1":
    def test_w14_the_largest_mesh_s_surface_and_cut_are_recorded(client):
        # the card at the element size whose estimate is nearest below the limit (600,000)
        _w14(client, card("6.4 um"), "card 6.4 um")


# ----------------------------------------------------------------------------- W8

def _post(url, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST" if body is not None or url.endswith("/cancel") else "GET",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _children(pid: int) -> set[int]:
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


def w8_cancel_a_run_in_its_mesh_step_on_a_real_server(tmp_path):
    """W8 (run): a run whose mesh step is estimated >= 60 s, cancelled 3 s after it starts: the child
    has exited 2 s after Cancel, the run is cancelled and nothing is kept."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    log = open(tmp_path / "server.log", "w", encoding="utf-8")
    scratch = tmp_path / "tmp"
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
        doc = card("11 um")
        est = _post(base + "/api/model3d/mesh/estimate", {"doc": doc})["estimate"]
        assert est["seconds"] >= 60, est
        run = _post(base + "/api/model3d/run", {"doc": doc})["run"]
        start = time.monotonic()
        children = set()
        while time.monotonic() - start < 3.0:
            children |= _children(server.pid)
            time.sleep(0.1)
        status = _post(f"{base}/api/model3d/runs/{run}")
        assert status["status"] == "running" and status["step"] == "mesh", status
        assert len(children) == 1, children
        (child,) = children
        _post(f"{base}/api/model3d/runs/{run}/cancel")
        cancelled_at = time.monotonic()
        while _alive(child) and time.monotonic() - cancelled_at < 2.0:
            time.sleep(0.02)
        exited = not _alive(child)
        status = _post(f"{base}/api/model3d/runs/{run}")
        try:
            urllib.request.urlopen(f"{base}/api/model3d/runs/{run}/values", timeout=10)
            kept = True
        except urllib.error.HTTPError as exc:
            kept = exc.code != 409
        record = {"estimate_s": est["seconds"], "exited_within_2_s": exited, "status": status["status"],
                  "kept": kept, "files_left": sorted(p.name for p in scratch.iterdir())}
        print("W8-run", json.dumps(record))
        assert exited and status["status"] == "cancelled" and not status["has_result"] and not kept
        assert record["files_left"] == []
    finally:
        server.terminate()
        try:
            server.wait(10)
        except subprocess.TimeoutExpired:
            server.kill()
        log.close()


# W8 runs on main pushes and manual dispatch only (validate.yml's studio-mesh3d-w8 job, Linux: it reads
# /proc). Elsewhere it is not collected, rather than skipped: the installed-package runs fail on any skip.
if os.environ.get("OPENPHYSICS_STUDIO_W8") == "1":
    test_w8_cancel_a_run_in_its_mesh_step_on_a_real_server = w8_cancel_a_run_in_its_mesh_step_on_a_real_server
