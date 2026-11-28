# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Studio's 3D view, Mesh and Run on cylinders and spheres in builder shapes, and card 2 (``via-slab-3d``).

Pre-registered check (adopted design 8; decision 2026-11-28-openphysics-studio-3d-e2-display; never
loosened):

- W18 (PR): card 2 (E2 of stage 5: a via r = 0.3 m with k_v = 100 W/(m K) through a slab [-1, 1]^2 x
  [0, 1] m with k_s = 1, T = 300 K on z0 and 301 K on z1, sides insulated, h = 0.1 m) through
  ``POST /api/model3d/run``: e_Q = |Q_h - Q| / Q <= 1e-2, Q_h the heat rate on z1 and Q = dT / L (k_v pi
  r^2 + k_s (A - pi r^2)) computed from the document (stage 5 P2's threshold); and Q_h, the nodal
  temperature and the reaction heat rate equal, bit for bit (SHA-256), to ``build_mesh3d`` +
  ``galerkin.solve_steady_heat_3d`` called directly on the same document.

Also tested, without numeric thresholds: the display, section and check answers keep every field of
slice A's and B's (curved faces with ``axis`` and ``at`` null and ``shape``, ``display_note``); a
non-builder cylinder stays refused in the same words; the mesh view maps every mesh triangle to the
display face of its name set, so a pick gives the mesh names; card 2 is served as a view asset.
"""
import base64
import copy
import hashlib
import json
import math
import time

import numpy as np
import pytest

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from simcase import Document, build_mesh3d, parse_geometry, quantities  # noqa: E402
from simcase.studio import app, model3d_api  # noqa: E402

import test_geometry_display3d as D  # noqa: E402

WAIT = 300.0
FACE_KEYS = {"id", "axis", "at", "names", "alone", "minus", "plus", "exterior", "tag", "area", "first_triangle",
             "triangle_count"}
ANSWER_KEYS = {"ok", "component", "unit", "components", "metres_per_unit", "origin_m", "domain", "half_extent_m",
               "regions", "faces", "selections", "tags", "counts", "positions", "indices", "triangle_faces", "edges",
               "edge_faces", "summary"}


@pytest.fixture
def client():
    yield TestClient(app)
    model3d_api.runs.shutdown()
    model3d_api.jobs.shutdown()
    model3d_api.jobs.kept.clear()
    model3d_api.runs.runs.clear()


def b64(view, key, dtype, width=1):
    a = np.frombuffer(base64.b64decode(view[key]), dtype=np.dtype(dtype).newbyteorder("<"))
    return a.reshape(-1, width) if width > 1 else a


@pytest.mark.parametrize("name", list(D.CASES))
def test_the_display_answer_keeps_slice_a_s_fields(client, name):
    view = client.post("/api/model3d/display", json={"doc": D.CASES[name]()}).json()
    assert view["ok"], view
    assert ANSWER_KEYS <= set(view) and view["display_note"] == "Shape drawn for display; the mesh follows it to within its size"
    owner = b64(view, "triangle_faces", "u4")
    assert len(owner) == view["counts"]["triangles"] == sum(f["triangle_count"] for f in view["faces"])
    for f in view["faces"]:
        assert FACE_KEYS | {"shape"} == set(f)
        assert (f["axis"] is None) == (f["at"] is None) == (f["shape"] != "plane")
        assert np.all(owner[f["first_triangle"]:f["first_triangle"] + f["triangle_count"]] == f["id"])
    assert sorted(frozenset(f["names"]) for f in view["faces"]) == sorted(D.EXPECTED[name])


def test_section_and_check_answer_builder_shapes(client):
    sec = client.post("/api/model3d/section", json={"doc": D.c4(), "axis": "z", "at": 0.5}).json()
    assert sec["ok"] and sec["regions"] == ["background", "via"]
    seg = b64(sec, "segments", "f4", 6)
    assert len(seg) == len(b64(sec, "segment_faces", "u4")) > 0
    out = client.post("/api/model3d/section", json={"doc": D.c4(), "axis": "z", "at": 2}).json()
    assert not out["ok"] and "outside the domain" in out["refused"]
    check = client.post("/api/model3d/check", json={"doc": D.c11()}).json()
    assert check["ok"] and check["mesh"]["ok"] and check["mesh"]["estimate"]["route"] == "builder"
    cov = {f["id"]: (f["coverage"], f["covered_by"]) for f in check["features"]}
    assert cov == {"sc": ("partial", [1, 2]), "sb": ("partial", [2]), "sa": ("full", [])}
    sc = check["features"][0]
    assert sc["owned"] == pytest.approx(4 / 3 * math.pi * (1 - 0.75 ** 3), rel=1e-12)
    assert {r["name"] for r in check["regions"]} == {"sb", "sc"}


def test_a_cylinder_no_builder_takes_stays_refused_in_the_same_words(client):
    short = D.doc([{"name": "pin", "type": "cylinder", "cx": 0, "cy": 0, "r": 0.3, "zmin": 0, "zmax": 0.5,
                    "material": "Cu"}], (-1, 1, -1, 1, 0, 1), "FR4")
    view = client.post("/api/model3d/display", json={"doc": short}).json()
    assert not view["ok"]
    # the words main gives for it (before cylinders and spheres were drawn)
    assert view["refused"] == ("cylinder 'pin' is not taken yet in a 3d component; "
                               "boxes and slab layers are, and cylinders and spheres in meshloom's builder shapes "
                               "only (one cylinder through the whole slab, one sphere, concentric spheres)")


def test_card_2_is_a_view_asset(client):
    served = client.get("/model3d-assets/model3d-via-slab-3d.json")
    assert served.status_code == 200 and served.json() == D.card2()


def _wait(client, path, limit=WAIT):
    t0 = time.monotonic()
    while True:
        status = client.get(path).json()
        if status["status"] != "running":
            return status
        assert time.monotonic() - t0 < limit, status
        time.sleep(0.05)


def test_the_mesh_view_maps_every_triangle_to_its_named_face(client):
    reply = client.post("/api/model3d/mesh", json={"doc": D.card2()}).json()
    status = _wait(client, f"/api/model3d/jobs/{reply['job']}")
    assert status["status"] == "done", status
    view = client.get(f"/api/model3d/jobs/{reply['job']}/result").json()
    owner = b64(view, "triangle_faces", "u4")
    built = build_mesh3d(D.card2())
    held = {}
    for name, tris in built.provenance_faces.items():
        for t in np.asarray(tris).reshape(-1, 3):
            held.setdefault(tuple(sorted(t.tolist())), set()).add(name)
    assert len(owner) == len(held)
    counts = {frozenset(f["names"]): f["triangle_count"] for f in view["faces"]}
    expected = {}
    for names in held.values():
        expected[frozenset(names)] = expected.get(frozenset(names), 0) + 1
    assert counts == expected


# ----------------------------------------------------------------------------- W18

def _sha(nodes, tets, temperature, reaction):
    h = hashlib.sha256()
    for a in (np.asarray(nodes, dtype=float), np.asarray(tets, dtype=np.int64),
              np.asarray(temperature, dtype=float), np.asarray(reaction, dtype=float)):
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


def expected_q(data):
    """Q = dT / L (k_v pi r^2 + k_s (A - pi r^2)), from the document's own values."""
    comp = next(iter(data["geometry"]["components"].values()))
    dom, via = comp["domain"], comp["features"][0]
    k = {m: quantities.q(v["thermal_conductivity"], "thermal_conductivity") for m, v in data["materials"].items()}
    k_s, k_v = k[comp["background"]["material"]], k[via["material"]]
    fixed = data["physics"]["heat"]["prescribed_temperature"]
    d_t = quantities.q(fixed["z1"], "temperature") - quantities.q(fixed["z0"], "temperature")
    area = (dom["xmax"] - dom["xmin"]) * (dom["ymax"] - dom["ymin"])
    disc = math.pi * via["r"] ** 2
    return d_t / (dom["zmax"] - dom["zmin"]) * (k_v * disc + k_s * (area - disc))


def test_w18_card_2_through_the_run_route(client):
    from galerkin.thermal3d import solve_steady_heat_3d
    data = D.card2()
    reply = client.post("/api/model3d/run", json={"doc": copy.deepcopy(data)})
    assert reply.status_code == 200, reply.text
    status = _wait(client, f"/api/model3d/runs/{reply.json()['run']}")
    assert status["status"] == "done" and status["route"] == "builder", status
    run_id = reply.json()["run"]
    values = client.get(f"/api/model3d/runs/{run_id}/values").json()
    q_h = values["heat_rate_by_selection"]["z1"]["value"]
    q = expected_q(data)
    e_q = abs(abs(q_h) - q) / q
    r = model3d_api.runs.get(run_id).result
    mesh = build_mesh3d(data).mesh
    fixed = {int(n): 300.0 for n in np.unique(mesh.tagged_faces["z0"])}
    fixed.update({int(n): 301.0 for n in np.unique(mesh.tagged_faces["z1"])})
    kappa = {"background": 1.0, "via": 100.0}
    direct = solve_steady_heat_3d(mesh, thermal_conductivity={n: kappa[n] for n in mesh.region_names},
                                  prescribed_temperature=dict(sorted(fixed.items())))
    q_direct = float(np.asarray(direct.reaction_heat_rate)[np.unique(mesh.tagged_faces["z1"])].sum())
    got = _sha(r.mesh.nodes, r.mesh.tets, r.temperature, r.reaction_heat_rate)
    want = _sha(mesh.nodes, mesh.tets, direct.temperature, direct.reaction_heat_rate)
    print("W18", json.dumps({"Q_h_W": q_h, "Q_W": q, "e_Q": e_q, "tetrahedra": int(len(r.mesh.tets)),
                             "route": got, "direct": want, "Q_direct_W": q_direct}))
    assert e_q <= 1e-2
    assert got == want and q_h == q_direct
