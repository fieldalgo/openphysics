# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The Studio 3D view's server answers (/api/model3d/display and /api/model3d/section).

Pre-registered checks (fixed before measuring; never loosened):

- W1: every display triangle carries the provenance of an exact surface, on E1, the card
  document and 50 seeded G1 sets: (a) triangles whose face id is missing or whose name set
  differs from the face's: 0; (b) triangle vertices off their face's exact plane or outside its
  closed polygon, and triangles whose centroid is not inside the face (exact, on the pm values
  before float32): 0.
- W2: per planar face, the area of its float32 display triangles against the exact face area of
  the complex: relative difference <= 1e-6.
- W3 (browser): the expected picks are written by model3d_pick_oracle.py; here the stored file
  is checked against a fresh run of that oracle.
- W15: the SHA-256 of the display answer is the same in 3 fresh server processes.

The reference is the complex of ``simcase.geometry_engine3d`` (``evaluate3d``; for a component
holding one layers feature, as E1, the same builder through ``_evaluate(..., through_meshloom=True)``).
"""
import base64
import hashlib
import json
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

import model3d_fixtures as F
from simcase.geometry_document import GeometryError, _pick, parse
from simcase.geometry_engine3d import _evaluate

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

from simcase.studio import app, model3d_api  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PM = 10 ** 12


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def exact_complex(doc, component=None):
    comp = _pick(parse(doc), component)
    lone = len(comp.features) == 1 and comp.features[0].type == "layers"
    return _evaluate(comp, through_meshloom=lone)


def arrays(view):
    def get(key, dtype, width):
        a = np.frombuffer(base64.b64decode(view[key]), dtype=np.dtype(dtype).newbyteorder("<"))
        return a.reshape(-1, width) if width > 1 else a
    return (get("positions", "f4", 3), get("indices", "u4", 3), get("triangle_faces", "u4", 1))


def _inside_closed(face, p):
    """-1 outside, 0 on the boundary, 1 inside the face's polygon (exact; p in pm, on its plane)."""
    others = [i for i in range(3) if i != face.axis]
    u, v = (p[i] for i in others)
    inside = False
    for loop in face.loops:
        for a, b in zip(loop, loop[1:] + loop[:1]):
            (ua, va), (ub, vb) = (a[i] for i in others), (b[i] for i in others)
            if min(ua, ub) <= u <= max(ua, ub) and min(va, vb) <= v <= max(va, vb) and \
                    (ub - ua) * (v - va) == (vb - va) * (u - ua):
                return 0
            if (va > v) != (vb > v) and u < ua + (v - va) * Fraction(ub - ua) / (vb - va):
                inside = not inside
    return 1 if inside else -1


# ---- W1 --------------------------------------------------------------------------------------

@pytest.mark.parametrize("label,doc", list(F.w1_documents()), ids=[label for label, _ in F.w1_documents()])
def test_w1_every_triangle_carries_its_exact_face(label, doc):
    cx = exact_complex(doc)
    view = model3d_api.display_view(doc)
    positions, indices, owner = arrays(view)
    # (a) the face id and its name set
    names = {f["id"]: f["names"] for f in view["faces"]}
    bad_a = sum(1 for t in owner.tolist() if t >= len(cx.faces) or names.get(t) != sorted(cx.faces[t].provenance))
    assert [f["id"] for f in view["faces"]] == [f.index for f in cx.faces]
    for f in view["faces"]:
        assert owner[f["first_triangle"]:f["first_triangle"] + f["triangle_count"]].tolist() == [f["id"]] * f["triangle_count"]
    # (b) exact: the pm triangles before float32
    bad_b = 0
    origin2 = [cx.domain[k + "min"] + cx.domain[k + "max"] for k in "xyz"]
    for face_index, vertices, triangles in model3d_api.tessellate(cx):
        face = cx.faces[face_index]
        for t in triangles:
            pts = [vertices[i] for i in t]
            bad_b += any(p[face.axis] != face.coord for p in pts)
            bad_b += any(_inside_closed(face, p) < 0 for p in pts)
            centroid = [Fraction(sum(p[i] for p in pts), 3) for i in range(3)]
            bad_b += _inside_closed(face, centroid) != 1
    # the float32 positions are those pm vertices, in metres from the domain centre
    flat = [v for _, vertices, _ in model3d_api.tessellate(cx) for v in vertices]
    expected = np.array([[float(Fraction(2 * p[i] - origin2[i], 2 * PM)) for i in range(3)] for p in flat], dtype=np.float32)
    np.testing.assert_array_equal(positions, expected)
    assert (bad_a, bad_b) == (0, 0), label


def test_w1_documents_are_the_stage5_sets():
    """The G1 copy gives the stage 5 generator's sets (that module skips without meshloom's kernel)."""
    try:
        import test_geometry_engine3d as stage5
    except pytest.skip.Exception:
        pytest.skip("test_geometry_engine3d needs meshloom's kernel")
    for seed in F.W1_SEEDS:
        assert F.g1_case(seed) == stage5.g1_case(seed)
    assert F.e1() == stage5.e1()


# ---- W2 --------------------------------------------------------------------------------------

@pytest.mark.parametrize("label,doc", list(F.w1_documents()), ids=[label for label, _ in F.w1_documents()])
def test_w2_display_areas_match_the_exact_faces(label, doc):
    cx = exact_complex(doc)
    view = model3d_api.display_view(doc)
    positions, indices, owner = arrays(view)
    p = positions.astype(np.float64)[indices]
    area = np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1) / 2
    worst = 0.0
    for f in cx.faces:
        exact = f.area / PM ** 2
        got = float(area[owner == f.index].sum())
        worst = max(worst, abs(got - exact) / exact)
    assert worst <= 1e-6, (label, worst)


# ---- W3: the stored expected picks are the oracle's ------------------------------------------

def test_w3_expected_picks_are_the_oracles():
    import model3d_pick_oracle as oracle
    stored = json.loads(oracle.OUT.read_text(encoding="utf-8"))
    assert stored == oracle.expected()
    assert len(stored["points"]) == 40


# ---- W15 -------------------------------------------------------------------------------------

_W15 = """
import hashlib, sys
from fastapi.testclient import TestClient
from simcase.studio import app
sys.stdout.write(hashlib.sha256(TestClient(app).get("/api/model3d/display").content).hexdigest())
"""


def test_w15_display_answer_is_the_same_in_three_fresh_processes():
    digests = set()
    for seed in ("1", "2", "3"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        done = subprocess.run([sys.executable, "-c", _W15], capture_output=True, text=True, cwd=ROOT, env=env,
                              timeout=120)
        assert done.returncode == 0, done.stderr
        digests.add(done.stdout.strip())
    assert len(digests) == 1, digests


# ---- the routes ------------------------------------------------------------------------------

def test_display_route_answers_the_card_and_a_posted_document(client):
    got = client.get("/api/model3d/display")
    assert got.status_code == 200 and got.headers["cache-control"] == "no-store"
    view = got.json()
    assert view["ok"] is True and view["component"] == "stack3d" and view["unit"] == "um"
    posted = client.post("/api/model3d/display", json={"doc": F.card()})
    assert posted.status_code == 200 and posted.content == got.content
    names = {n for f in view["faces"] for n in f["names"]}
    assert {"via.z1", "stack.top.bottom", "domain.z1"} <= names
    assert [r["name"] for r in view["regions"]] == ["silicon", "silicon_dioxide", "via"]
    via = next(r for r in view["regions"] if r["name"] == "via")
    assert via["material"] == "copper" and via["volume"] == pytest.approx(4.0)


def test_display_refusals_carry_the_engines_words(client):
    cyl = F.doc([{"name": "pin", "type": "cylinder", "axis": "z", "cx": 5, "cy": 5, "r": 1, "zmin": 0, "zmax": 1,
                  "material": "m"}])
    with pytest.raises(GeometryError) as engine:
        exact_complex(cyl)
    view = client.post("/api/model3d/display", json={"doc": cyl}).json()
    assert view == {"ok": False, "refused": str(engine.value)}
    assert "'pin'" in view["refused"]
    flat = {"openphysics": "0.3", "geometry": {"version": 1, "components": {"xs": {
        "dimension": "2d", "length_unit": "um", "depth": None, "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1},
        "background": {"material": "a"}, "features": []}}}}
    view = client.post("/api/model3d/display", json={"doc": flat}).json()
    assert view["ok"] is False and "'xs'" in view["refused"] and "3d" in view["refused"]
    assert client.post("/api/model3d/display", content=b"{", headers={"Content-Type": "application/json"}
                       ).status_code == 400


# ---- sections --------------------------------------------------------------------------------

@pytest.mark.parametrize("axis,at", [("z", 2.5), ("x", 5), ("y", 4), ("x", 0.5)])
def test_section_outlines_lie_on_the_plane_and_cover_the_exact_cuts(client, axis, at):
    doc = F.card()
    cx = exact_complex(doc)
    reply = client.post("/api/model3d/section", json={"doc": doc, "axis": axis, "at": at})
    assert reply.status_code == 200 and reply.headers["cache-control"] == "no-store"
    view = reply.json()
    assert view["ok"] is True and view["axis"] == axis
    a = "xyz".index(axis)
    seg = np.frombuffer(base64.b64decode(view["segments"]), dtype="<f4").reshape(-1, 2, 3).astype(np.float64)
    owner = np.frombuffer(base64.b64decode(view["segment_faces"]), dtype="<u4")
    centre = (cx.domain[axis + "min"] + cx.domain[axis + "max"]) / 2
    plane = (Fraction(str(at)) * 10 ** 6 - centre) / PM                     # um -> pm, from the centre, in m
    assert np.all(seg[:, :, a] == np.float32(float(plane)))
    # the exact cut of each face crossing the plane, by its loops: length along the plane
    at_pm = Fraction(str(at)) * 10 ** 6
    for f in cx.faces:
        if f.axis == a:
            assert not np.any(owner == f.index)
            continue
        others = [i for i in range(3) if i != f.axis]
        along = next(i for i in others if i != a)
        # the closed face meets the line coordinate[a] == at in the union of its cuts just below
        # and just above the line (even-odd over its edges across the line)
        def cut(below):
            xs = sorted(p[along] for loop in f.loops for p, q in zip(loop, loop[1:] + loop[:1])
                        if p[along] == q[along] and ((min(p[a], q[a]) < at_pm <= max(p[a], q[a])) if below
                                                     else (min(p[a], q[a]) <= at_pm < max(p[a], q[a]))))
            return list(zip(xs[::2], xs[1::2]))
        merged = []
        for lo, hi in sorted(cut(True) + cut(False)):
            if merged and lo <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
            else:
                merged.append((lo, hi))
        exact = sum(hi - lo for lo, hi in merged) / PM
        got = float(np.linalg.norm(seg[owner == f.index, 1] - seg[owner == f.index, 0], axis=1).sum())
        assert got == pytest.approx(float(exact), rel=1e-6, abs=1e-12), f.index


def test_section_refuses_a_plane_outside_the_domain(client):
    reply = client.post("/api/model3d/section", json={"doc": F.card(), "axis": "z", "at": 5}).json()
    assert reply["ok"] is False and "z = 5 um" in reply["refused"] and "domain" in reply["refused"]
    reply = client.post("/api/model3d/section", json={"doc": F.card(), "axis": "w", "at": 1})
    assert reply.status_code == 400


# ---- the view's files and the lab page -------------------------------------------------------

def test_view_assets_are_served_by_name_only(client):
    import re
    static = F.STATIC
    for name, mime in (("model3d-view.mjs", "text/javascript"), ("model3d-model.mjs", "text/javascript"),
                       ("model3d-via-stack.json", "application/json")):
        reply = client.get("/model3d-assets/" + name)
        assert reply.status_code == 200 and reply.content == (static / name).read_bytes()
        assert reply.headers["content-type"].startswith(mime)
        assert reply.headers["cache-control"] == "no-store" and reply.headers["x-content-type-options"] == "nosniff"
    for name in ("geometry-lab-app.mjs", "../server.py", "model3d-api.py", "three.module.js"):
        assert client.get("/model3d-assets/" + name).status_code == 404
    imports = {}
    for name in ("model3d-view.mjs", "model3d-model.mjs", "geometry-lab-app.mjs"):
        text = (static / name).read_text(encoding="utf-8")
        assert "http" not in text.replace("http://www.w3.org/2000/svg", "") and "import(" not in text and "eval(" not in text
        imports[name] = set(re.findall(r"""from\s*['"]([^'"]+)['"]""", text))
    assert imports["model3d-view.mjs"] == {"/vendor/three-0.186.1/three.module.js", "/model3d-assets/model3d-model.mjs"}
    assert imports["model3d-model.mjs"] == set()
    assert {"/model3d-assets/model3d-view.mjs", "/model3d-assets/model3d-model.mjs"} <= imports["geometry-lab-app.mjs"]


def test_lab_page_offers_the_card_and_the_view(client):
    page = client.get("/geometry-lab").text
    assert '<option value="model3d_via_stack">' in page and 'id="canvas3d" tabindex="0"' in page
    assert 'id="faces"' in page and 'id="names"' in page
    starter = client.get("/model3d-assets/model3d-via-stack.json").json()
    assert starter == F.card() and starter["geometry"]["components"]["stack3d"]["length_unit"] == "um"
