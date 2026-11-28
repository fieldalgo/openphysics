# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""U5: the check answers each slab layer's evaluated z range, so the tree's Layers row can show it.

A layers feature's ``layers`` entry is ``[[z0, z1], ...]`` in the component's length unit, one pair per
layer from the bottom. Each pair is the layer's z0 plus its thickness, evaluated from the document
(here ``t_ox``, a parameter of 10 um). It is checked against the document's own numbers. A box keeps
``size`` and gets no ``layers``.
"""
import copy
import json

import pytest

import simcase

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

from simcase.studio import app  # noqa: E402

CARD = __import__("pathlib").Path(simcase.__file__).parent / "studio" / "static" / "model3d-layer-stack-3d.json"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def check(client, doc):
    reply = client.post("/api/model3d/check", json={"doc": doc})
    assert reply.status_code == 200
    return reply.json()


def test_layers_report_their_evaluated_z_ranges(client):
    doc = json.loads(CARD.read_text(encoding="utf-8"))
    answer = check(client, doc)
    assert answer["ok"] is True
    stack = answer["features"][0]
    assert stack["type"] == "layers"
    # z0 = 0, then 500, t_ox = 10 um and 100 (the document's thicknesses, in um)
    assert stack["layers"] == [[0.0, 500.0], [500.0, 510.0], [510.0, 610.0]]
    assert "layers" not in answer["features"][1] and "size" in answer["features"][1]


def test_layer_ranges_follow_a_parameter(client):
    doc = json.loads(CARD.read_text(encoding="utf-8"))
    doc = copy.deepcopy(doc)
    doc["geometry"]["parameters"]["t_ox"]["value"] = "12.5 um"
    answer = check(client, doc)
    assert answer["ok"] is True
    assert answer["features"][0]["layers"] == [[0.0, 500.0], [500.0, 512.5], [512.5, 612.5]]
