# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""U1: an E-MESH-ESTIMATE refusal answers what Studio needs for a plain message.

The check's ``mesh`` refusal keeps the engine's words (``refused``, ``code``, ``path``) and adds
``tetrahedra`` (the estimate of this document), ``limit`` (its element_count_limit) and
``suggested_size``: the smallest mesh element size, on a grid of three significant digits in the
component's unit, that ``simcase.estimate_mesh3d`` accepts. The test takes every number from the
estimate at test time (nothing pinned): N is accepted, and the grid value just below N is refused.
"""
import copy
import json
import math

import pytest

import simcase

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

from simcase.studio import app  # noqa: E402

CARD = __import__("pathlib").Path(simcase.__file__).parent / "studio" / "static" / "model3d-layer-stack-3d.json"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def card(size):
    doc = json.loads(CARD.read_text(encoding="utf-8"))
    doc["mesh"]["element_size"] = size
    return doc


def accepted(doc):
    try:
        simcase.estimate_mesh3d(doc)
        return True
    except simcase.GeometryError as exc:
        assert exc.code == "E-MESH-ESTIMATE", exc
        return False


def test_an_estimate_refusal_answers_the_count_the_limit_and_the_smallest_size(client):
    doc = card("1 um")
    mesh = client.post("/api/model3d/check", json={"doc": doc}).json()["mesh"]
    assert mesh["ok"] is False and mesh["code"] == "E-MESH-ESTIMATE"
    raised = copy.deepcopy(doc)
    raised["mesh"]["element_count_limit"] = 10 ** 12
    assert mesh["tetrahedra"] == simcase.estimate_mesh3d(raised).tetrahedra
    assert mesh["limit"] == 600000
    n = mesh["suggested_size"]
    step = 10 ** (math.floor(math.log10(n)) - 2)
    assert n == float(f"{n:.3g}"), "three significant digits"
    assert accepted(card(f"{n} um")), "N is accepted by the same estimate"
    below = round(n - step, 12)
    assert not accepted(card(f"{below} um")), "the grid value below N is refused"


def test_other_mesh_refusals_are_unchanged(client):
    doc = card("40 um")
    answer = client.post("/api/model3d/check", json={"doc": doc}).json()
    assert answer["mesh"]["ok"] is True and "suggested_size" not in answer["mesh"]


def estimate(size):
    doc = card(size)
    doc["mesh"]["element_count_limit"] = 10 ** 12
    return simcase.estimate_mesh3d(doc)


def test_v3_the_refusal_also_answers_a_size_that_meshes_in_about_a_minute(client):
    """V3: ``suggested_minute`` is the smallest grid size whose estimate (seconds, the engine's 0.6 ms
    per tetrahedron) is at most 60 s and within the limit; at the grid value below it the estimate is
    over 60 s (or the limit). Both sizes come with their estimates. All numbers are the engine's at test
    time; the engine's own keys are unchanged."""
    mesh = client.post("/api/model3d/check", json={"doc": card("2 um")}).json()["mesh"]
    assert mesh["code"] == "E-MESH-ESTIMATE"
    assert set(mesh) == {"ok", "refused", "code", "path", "feature_index", "tetrahedra", "limit", "suggested_size",
                         "suggested_tetrahedra", "suggested_seconds", "suggested_minute", "minute_tetrahedra",
                         "minute_seconds"}
    n, m = mesh["suggested_size"], mesh["suggested_minute"]
    at_n, at_m = estimate(f"{n} um"), estimate(f"{m} um")
    assert (mesh["suggested_tetrahedra"], mesh["suggested_seconds"]) == (at_n.tetrahedra, at_n.seconds)
    assert (mesh["minute_tetrahedra"], mesh["minute_seconds"]) == (at_m.tetrahedra, at_m.seconds)
    assert at_m.seconds <= 60 and at_m.tetrahedra <= mesh["limit"] and m >= n
    assert m == float(f"{m:.3g}"), "three significant digits"
    below = round(m - 10 ** (math.floor(math.log10(m)) - 2), 12)
    under = estimate(f"{below} um")
    assert under.seconds > 60 or under.tetrahedra > mesh["limit"], "the grid value below is over a minute"
