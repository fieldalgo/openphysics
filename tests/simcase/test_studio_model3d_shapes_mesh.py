# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Builder-shaped components through the Studio 3D mesh job, the builder's check and the 3D heat run.

Pre-registered checks (decision 2026-11-28-openphysics-studio-3d-e2-display; thresholds fixed before
measuring, never loosened; a miss is a failure):
- W1(a) (PR), cases C1, C4, C5, C11 and card 2: every boundary or interface triangle of the mesh has a
  display face id (the mesh job's map: the display face whose name set equals the set of provenance
  names that hold the triangle), and that face's name set equals an independent expected table written
  here from slice 3's tag tables, applied to meshloom's own builder mesh at the same h: 0 mismatches.
- W18 (PR): card 2 (stage 5's E2) through ``POST /api/model3d/run``: e_Q = |Q_h - Q| / Q at h = 0.1 is
  <= 1e-2 (stage 5 P2's threshold), Q_h the reaction heat rate on z1 and Q = dT / L (k_v pi r^2 +
  k_s (A - pi r^2)) computed from the document; and Q_h, the nodal T and the reaction equal, by SHA-256,
  ``simcase.build_mesh3d`` + ``galerkin.solve_steady_heat_3d`` called directly on the same document.
Also tested: the builder's check (``check_view_shapes``): coverage from exact volumes, regions and the
estimate under ``mesh``; and the mesh job's answer for card 2.
"""
import copy
import hashlib
import json
import math
import time

import numpy as np
import pytest

import test_geometry_display3d as G

pytest.importorskip("fastapi", reason="the studio extra is not installed")
meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402
from meshloom import builder  # noqa: E402

from simcase import build_mesh3d, display_shapes3d, estimate_mesh3d, parse_geometry  # noqa: E402
from simcase.studio import app, mesh3d_jobs, model3d_api  # noqa: E402

WAIT = 300.0
H = {"C1": 0.2, "C4": 0.2, "C5": 0.24, "C11": 0.2, "card2": 0.1}


def with_size(doc, h):
    doc = copy.deepcopy(doc)
    doc["mesh"] = {"element_size": f"{h} m"}
    return doc


# The independent table: meshloom's builder called here on the shape's own numbers, its tags and
# interfaces named as slice 3 names them (geometry_builders3d.prepare; test_geometry_engine3d_curved).
def reference(case, h):
    lo, hi = (-1.0, -1.0, 0.0), (1.0, 1.0, 1.0)
    if case in ("C4", "card2"):
        kw = builder.via_in_slab(h, slab=(lo, hi), radius=0.3, axis=(0.0, 0.0), names=("background", "via"))
        tags = {"bottom": {"domain.z0"}, "top": {"domain.z1"}, "x0": {"domain.x0"}, "x1": {"domain.x1"},
                "y0": {"domain.y0"}, "y1": {"domain.y1"}, "via_bottom": {"via.bottom", "domain.z0"},
                "via_top": {"via.top", "domain.z1"}}
        pairs = {("background", "via"): {"via.side"}}
    elif case == "C5":
        kw = builder.sphere_in_box(h, box=((-1.0,) * 3, (1.0,) * 3), center=(0.0, 0.0, 0.0), radius=0.5,
                                   names=("background", "ball"))
        tags = {a: {f"domain.{a}"} for a in ("x0", "x1", "y0", "y1", "z0", "z1")}
        pairs = {("background", "ball"): {"ball.surface"}}
    elif case == "C11":
        kw = builder.nested_spheres(h, center=(0.0, 0.0, 0.0), radii=(0.5, 0.75, 1.0), names=(None, "sb", "sc"))
        tags = {"sphere0": {"sa.surface"}, "sphere2": {"sc.surface"}}
        pairs = {("sb", "sc"): {"sb.surface"}}
    else:
        kw = builder.sphere(h, center=(0.0, 0.0, 0.0), radius=1.0, name="ball")
        tags, pairs = {"sphere": {"ball.surface"}}, {}
    raw = meshloom.generate3d(h=h, **kw)
    expected = {}
    for tag, faces in raw["boundary_faces"].items():
        for t in np.sort(np.asarray(faces).reshape(-1, 3), axis=1).tolist():
            expected[tuple(t)] = tags[tag]
    names = list(raw["region_names"])
    for (a, b), faces in raw["interfaces"].items():
        key = (names[a], names[b]) if (names[a], names[b]) in pairs else (names[b], names[a])
        for t in np.sort(np.asarray(faces).reshape(-1, 3), axis=1).tolist():
            expected[tuple(t)] = pairs[key]
    return raw, expected


@pytest.mark.parametrize("case", list(G.CASES))
def test_w1a_every_mesh_triangle_maps_to_the_display_face_of_its_names(case):
    h = H[case]
    doc = with_size(G.CASES[case](), h)
    raw, expected = reference(case, h)
    built = build_mesh3d(doc)
    assert np.asarray(built.mesh.nodes).tobytes() == np.ascontiguousarray(raw["nodes"], dtype=float).tobytes()
    shapes = display_shapes3d(parse_geometry(doc))
    used, local, faces, _, _ = mesh3d_jobs._surface_shapes(built, shapes)
    triangles = used[local]
    got = {}
    for t, f in zip(np.sort(triangles, axis=1).tolist(), faces.tolist()):
        assert f >= 0
        got[tuple(t)] = set(shapes.faces[f].names)
    missing = set(expected) - set(got)
    mismatches = sum(1 for key, names in got.items() if expected.get(key) != names)
    print(f"W1(a) {case} h={h}: {len(got)} triangles, {len(missing)} without a face id, {mismatches} mismatches")
    assert not missing and mismatches == 0 and len(got) == len(expected)


# ----------------------------------------------------------------------------- the builder's check

@pytest.fixture
def client():
    yield TestClient(app)
    model3d_api.runs.shutdown()
    model3d_api.jobs.shutdown()
    model3d_api.jobs.kept.clear()
    model3d_api.runs.runs.clear()


def test_the_check_answers_coverage_regions_and_the_estimate(client):
    view = client.post("/api/model3d/check", json={"doc": G.card2()}).json()
    assert view["ok"] is True and view["display"]["display_note"]
    (via,) = view["features"]
    assert via["coverage"] == "full" and via["covered_by"] == [] and via["volume"] == via["owned"]
    assert via["volume"] == pytest.approx(math.pi * 0.09, rel=1e-15)
    assert [r["name"] for r in view["regions"]] == ["via", "background"]
    found = estimate_mesh3d(G.card2())
    assert view["mesh"]["ok"] is True and view["mesh"]["estimate"]["route"] == "builder"
    assert view["mesh"]["estimate"]["tetrahedra"] == found.tetrahedra
    assert view["mesh"]["key"] == mesh3d_jobs.reuse_key(G.card2())
    nested = client.post("/api/model3d/check", json={"doc": with_size(G.c11(), 0.2)}).json()
    sc, sb, sa = nested["features"]
    assert (sc["coverage"], sc["covered_by"], sc["text"]) == ("partial", [1, 2], "covered in part by 2 (sb), 3 (sa)")
    assert (sb["coverage"], sb["covered_by"]) == ("partial", [2]) and sa["coverage"] == "full"
    assert sc["owned"] == pytest.approx(4 * math.pi / 3 * (1 - 0.75 ** 3), rel=1e-14)
    assert sc["volume"] == pytest.approx(4 * math.pi / 3, rel=1e-15)
    limited = G.card2()
    limited["mesh"]["element_count_limit"] = 100
    view = client.post("/api/model3d/check", json={"doc": limited}).json()
    assert view["ok"] is True and view["mesh"]["ok"] is False and view["mesh"]["code"] == "E-MESH-ESTIMATE"


def wait(client, url, limit=WAIT):
    t0 = time.monotonic()
    while True:
        status = client.get(url).json()
        if status["status"] != "running":
            return status
        assert time.monotonic() - t0 < limit, status
        time.sleep(0.05)


def test_the_mesh_job_answers_card_2_on_its_display_faces(client):
    doc = with_size(G.card2(), 0.2)
    reply = client.post("/api/model3d/mesh", json={"doc": doc}).json()
    status = wait(client, f"/api/model3d/jobs/{reply['job']}")
    assert status["status"] == "done", status
    answer = client.get(f"/api/model3d/jobs/{reply['job']}/result").json()
    faces = np.frombuffer(__import__("base64").b64decode(answer["triangle_faces"]), dtype="<u4")
    assert answer["mesh"] is True and answer["display_note"]
    assert sorted(set(faces.tolist())) == list(range(9))
    counts = {f["id"]: f["triangle_count"] for f in answer["faces"]}
    assert sum(counts.values()) == len(faces) and all(counts.values())


# ----------------------------------------------------------------------------- W18

def sha(*arrays):
    h = hashlib.sha256()
    for a in arrays:
        h.update(np.ascontiguousarray(np.asarray(a, dtype=float)).tobytes())
    return h.hexdigest()


def test_w18_card_2_through_the_run_route(client):
    from galerkin.thermal3d import solve_steady_heat_3d
    doc = G.card2()
    comp = doc["geometry"]["components"]["c"]
    via, d = comp["features"][0], comp["domain"]
    k = {name: float(m["thermal_conductivity"].split()[0]) for name, m in doc["materials"].items()}
    t = {key: float(v.split()[0]) for key, v in doc["physics"]["heat"]["prescribed_temperature"].items()}
    area, length = (d["xmax"] - d["xmin"]) * (d["ymax"] - d["ymin"]), d["zmax"] - d["zmin"]
    r = via["r"]
    q = (t["z1"] - t["z0"]) / length * (k[via["material"]] * math.pi * r * r
                                        + k[comp["background"]["material"]] * (area - math.pi * r * r))
    reply = client.post("/api/model3d/run", json={"doc": copy.deepcopy(doc)})
    assert reply.status_code == 200, reply.text
    run_id = reply.json()["run"]
    status = wait(client, f"/api/model3d/runs/{run_id}")
    assert status["status"] == "done" and status["route"] == "builder", status
    values = client.get(f"/api/model3d/runs/{run_id}/values").json()
    q_h = values["heat_rate_by_selection"]["z1"]["value"]
    result = model3d_api.runs.get(run_id).result
    # the direct path
    mesh = build_mesh3d(doc).mesh
    fixed = {int(n): t["z0"] for n in np.unique(mesh.tagged_faces["z0"])}
    fixed.update({int(n): t["z1"] for n in np.unique(mesh.tagged_faces["z1"])})
    kappa = {"background": k[comp["background"]["material"]], "via": k[via["material"]]}
    solution = solve_steady_heat_3d(mesh, thermal_conductivity={n: kappa[n] for n in mesh.region_names},
                                    prescribed_temperature=dict(sorted(fixed.items())))
    q_direct = float(np.asarray(solution.reaction_heat_rate)[np.unique(mesh.tagged_faces["z1"])].sum())
    e_q = abs(q_h - q) / q
    route = sha([q_h], result.temperature, result.reaction_heat_rate)
    direct = sha([q_direct], solution.temperature, solution.reaction_heat_rate)
    print("W18", json.dumps({"Q_h_W": q_h, "Q_W": q, "e_Q": e_q, "Q_direct_W": q_direct, "route": route,
                             "direct": direct, "nodes": int(len(mesh.nodes)), "tetrahedra": int(len(mesh.tets))}))
    assert np.asarray(result.mesh.nodes).tobytes() == np.asarray(mesh.nodes).tobytes()
    assert e_q <= 1e-2
    assert route == direct
