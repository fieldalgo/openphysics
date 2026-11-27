# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The 3D builder's check with the mesh estimate (the integration of Studio 3D slices B and C).

``/api/model3d/check`` also calls ``simcase.estimate_mesh3d`` (through ``mesh3d_jobs.estimate``,
the words of ``/api/model3d/mesh/estimate``), so every edit answers the estimate or the refusal
that blocks meshing. A refusal while forming keeps its answer (``ok: false``, the shape is greyed);
a refusal before meshing comes in ``mesh`` with the shape formed (``ok: true``).

Pre-registered checks (fixed before measuring; never loosened):

- W5 (server part, extended): one document per stem the check raises before meshing: the
  rounding stem ("... round to the same coordinate", E-3D-COMBINATION at features[i]), the
  below-tolerance E-CONTRACT and E-MESH-ESTIMATE: the engine's message as written, its code and
  path, and features[i] where the path names one: 100%. circle_segments is not applicable (no
  curved feature in a 3d component the check takes).
- W9 (server part, through the check): the estimate is answered before meshing (no job is
  started by a check); at 1.5 times the limit the check refuses with E-MESH-ESTIMATE and no job
  is started; the check's estimate equals ``/api/model3d/mesh/estimate``'s: 3/3.
"""
import json
import math

import pytest

import simcase

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

from simcase.studio import app  # noqa: E402
from simcase.studio import model3d_api  # noqa: E402

CARD = __import__("pathlib").Path(simcase.__file__).parent / "studio" / "static" / "model3d-layer-stack-3d.json"
KEYS = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def card(**mesh):
    doc = json.loads(CARD.read_text(encoding="utf-8"))
    doc["mesh"].update(mesh)
    return doc


def doc3d(features, *, unit, domain, size, background="air"):
    return {"openphysics": "0.3", "materials": {"Cu": {}, "Al": {}, "m1": {}, "m2": {}, "air": {}},
            "geometry": {"version": 1, "components": {"c": {
                "dimension": "3d", "length_unit": unit, "domain": dict(zip(KEYS, domain)),
                "background": {"material": background}, "features": features}}},
            "mesh": {"element_size": size}}


def box(name, x, y, z, material):
    return {"name": name, "type": "box", "xmin": x[0], "xmax": x[1], "ymin": y[0], "ymax": y[1],
            "zmin": z[0], "zmax": z[1], "material": material}


def check(client, doc):
    reply = client.post("/api/model3d/check", json={"doc": doc})
    assert reply.status_code == 200 and reply.headers["cache-control"] == "no-store"
    return reply.json()


def rounding_doc():
    k = 5 * 10 ** 16                      # 50 km in pm: doubles are 7.3 pm apart there
    return doc3d([box("west", (0, k), (0, k), (0, k), "Cu"), box("east", (k + 1, 2 * k), (0, k), (0, k), "Al")],
                 unit="pm", domain=(0, 2 * k, 0, k, 0, k), size="10 km", background=None)


def thin_doc():
    x = float(f"{5 + 2e-8 * math.sqrt(10 ** 2 + 10 ** 2 + 2.5 ** 2):.12g}")    # a 2e-8-of-the-diagonal strip
    return doc3d([box("a", (0, 5), (0, 10), (0, 2.5), "m1"), box("b", (x, 10), (0, 10), (0, 2.5), "m2")],
                 unit="mm", domain=(0, 10, 0, 10, 0, 2.5), size="2 mm")


def engine_refusal(doc):
    with pytest.raises(simcase.GeometryError) as err:
        simcase.estimate_mesh3d(doc)
    return err.value


def test_the_check_of_the_card_answers_the_estimate_and_the_reuse_key(client):
    answer = check(client, card())
    assert answer["ok"] is True and answer["mesh"]["ok"] is True
    direct = client.post("/api/model3d/mesh/estimate", json={"doc": card()}).json()
    assert answer["mesh"]["estimate"] == direct["estimate"] and answer["mesh"]["key"] == direct["key"]
    found = simcase.estimate_mesh3d(card())
    assert answer["mesh"]["estimate"]["tetrahedra"] == found.tetrahedra
    assert answer["mesh"]["estimate"]["code"] == "I-MESH-ESTIMATE"


# W5, extended: (document, code, path, features[i] or None, a stem of the message)
W5_MESH = {
    "rounding": (rounding_doc, "E-3D-COMBINATION", "geometry.components.c.features[1]", 1,
                 "west.x1 and east.x0 round to the same coordinate 50000.0 m"),
    "below tolerance": (thin_doc, "E-CONTRACT", "geometry.components.c", None, "below the mesher tolerance 3e-08"),
    "estimate limit": (lambda: card(element_count_limit=1000), "E-MESH-ESTIMATE", "mesh.element_count_limit", None,
                       "tetrahedra"),
}


@pytest.mark.parametrize("case", list(W5_MESH))
def test_w5_a_refusal_before_meshing_comes_with_the_formed_shape(client, case):
    make, code, path, index, stem = W5_MESH[case]
    answer = check(client, make())
    expected = engine_refusal(make())
    assert answer["ok"] is True, "the shape forms: the view is not greyed"
    assert answer["display"]["faces"], "the display answer is there"
    assert answer["mesh"] == {"ok": False, "refused": str(expected), "code": code, "path": path,
                              "feature_index": index}
    assert stem in answer["mesh"]["refused"]
    assert (expected.code, expected.path) == (code, path)


def test_a_refusal_while_forming_keeps_its_answer(client):
    doc = card()
    doc["geometry"]["components"]["stack3d"]["features"].append(
        {"name": "ball", "type": "sphere", "cx": 100, "cy": 100, "cz": 300, "r": 10, "material": "Cu"})
    answer = check(client, doc)
    assert answer["ok"] is False and answer["code"] == "E-3D-COMBINATION" and answer["feature_index"] == 2
    assert "mesh" not in answer


def test_w9_the_check_starts_no_job_and_refuses_above_the_limit(client):
    jobs = model3d_api.jobs
    started, known = jobs.processes_started, set(jobs.jobs)
    # 1: the estimate is answered before meshing, and a check starts no job
    answer = check(client, card())
    assert answer["mesh"]["ok"] is True and answer["mesh"]["estimate"]["tetrahedra"] > 0
    # 2: at 1.5 times the limit the check refuses with E-MESH-ESTIMATE, and no job is started
    t = answer["mesh"]["estimate"]["tetrahedra"]
    over = check(client, card(element_count_limit=round(t / 1.5)))
    assert over["ok"] is True and over["mesh"]["ok"] is False and over["mesh"]["code"] == "E-MESH-ESTIMATE"
    assert f"about {t} tetrahedra" in over["mesh"]["refused"]
    # 3: the check's estimate equals the estimate route's
    direct = client.post("/api/model3d/mesh/estimate", json={"doc": card()}).json()
    assert answer["mesh"]["estimate"] == direct["estimate"]
    assert jobs.processes_started == started and set(jobs.jobs) == known, "a check starts no job and no process"


def test_a_document_without_a_mesh_block_still_forms(client):
    doc = card()
    del doc["mesh"]
    answer = check(client, doc)
    assert answer["ok"] is True and answer["mesh"]["ok"] is False
    assert answer["mesh"]["code"] == "E-KEY-MISSING" and answer["mesh"]["path"] == "mesh.element_size"
