# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The optional browser UI: its HTTP API, and the boundary it must not cross."""

import ast
import copy
import time
from pathlib import Path

import pytest

import simcase
from simcase import FORMAT, examples

STUDIO = Path(simcase.__file__).parent / "studio"


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("fastapi", reason="the studio extra is not installed")
    from fastapi.testclient import TestClient

    from simcase.studio import app
    return TestClient(app)


# ---- the boundary ----------------------------------------------------------------

def test_studio_uses_only_the_public_api():
    """studio is an ordinary consumer of simcase, so lifting it back out stays a move.

    A leak here is cheap to write and expensive to find later, so it is checked
    rather than agreed: if the UI needs something simcase does not export, the fix
    is to export it on purpose, not to reach past this test.
    """
    leaks = []
    for path in sorted(STUDIO.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                leaks += [f"{path.name}: import {a.name}" for a in node.names
                          if a.name.split(".")[0] == "simcase" and a.name != "simcase"]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                if node.module.split(".")[0] != "simcase":
                    continue
                if node.module != "simcase":
                    leaks.append(f"{path.name}: from {node.module} import ...")
                    continue
                leaks += [f"{path.name}: simcase.{a.name} is not in simcase.__all__"
                          for a in node.names if a.name not in simcase.__all__]
    assert not leaks, "studio reached into simcase internals:\n  " + "\n  ".join(leaks)


def test_the_page_is_packaged():
    assert (STUDIO / "static" / "index.html").is_file()


# ---- the API ---------------------------------------------------------------------

def test_index_and_examples(client):
    assert client.get("/").status_code == 200
    ex = client.get("/api/examples").json()["examples"]
    assert "soi_strip" in ex
    doc = client.get("/api/examples/soi_strip").json()
    assert doc["openphysics"] == FORMAT and doc["geometry"]["shapes"][0]["name"] == "core"
    assert client.get("/api/examples/nope").status_code == 404


def test_materials_and_preview(client):
    mats = client.get("/api/materials").json()["materials"]
    assert any(m["name"] == "Si" for m in mats)
    prev = client.post("/api/materials/preview", json={"name": "SiO2", "wl_min": 0.5, "wl_max": 1.6}).json()
    assert len(prev["wavelength"]) == 100 and 1.44 < prev["n"][-1] < 1.46
    assert client.post("/api/materials/preview", json={"name": "Si", "wl_min": 0.3, "wl_max": 0.4}).status_code == 400


def test_units_vocabulary_comes_from_the_engine(client):
    served = client.get("/api/units").json()
    assert served == simcase.unit_vocabulary()
    assert "length" in served["dimensions"] and "um" in served["symbols"]["length"]


def _leaves(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _leaves(v, f"{path}.{k}" if path else k)
    else:
        yield path, node


def test_the_server_never_drops_the_units_declaration(client):
    """Read the numbers out, write them back: that is where a unit system dies.

    The declaration is the only thing that says what every other number means, and
    it is the one field an editor has no reason to touch, so losing it turns a
    document that meant nanometres into one that means metres with every number
    still looking right. Commercial FEA loses units on exactly this path - the
    export and scripting route, not the solver - so the studio checks it rather
    than assuming it.
    """
    served = client.get("/api/examples/soi_strip").json()
    assert served["units"] == {"length": "um"}

    doc = dict(copy.deepcopy(examples.SLAB_TE_CHECK), units={"length": "nm"})
    back = client.post("/api/validate", json={"doc": doc}).json()
    assert back["ok"] and back["doc"]["units"] == {"length": "nm"}

    sent, returned = dict(_leaves(doc)), dict(_leaves(back["doc"]))
    assert not sent.keys() - returned.keys(), "the server dropped fields the page sent"
    assert all(returned[k] == v for k, v in sent.items()), "the server altered a value it was given"

    # The page edits whatever validate hands back and posts it again, so that loop
    # has to be a fixed point: defaults are filled in once, never re-interpreted.
    again = client.post("/api/validate", json={"doc": back["doc"]}).json()
    assert again["doc"] == back["doc"]


def test_validate_reports_errors(client):
    ok = client.post("/api/validate", json={"doc": examples.FIBER}).json()
    assert ok["ok"] and "fiber" in ok["summary"]
    bad = dict(examples.FIBER, physics={"em1": dict(examples.FIBER["physics"]["em1"], formulation="magic")})
    r = client.post("/api/validate", json={"doc": bad}).json()
    assert not r["ok"] and "formulation" in r["error"]


def test_mesh_preview(client):
    r = client.post("/api/mesh", json={"doc": examples.FIBER})
    assert r.status_code == 200
    m = r.json()
    assert m["stats"]["triangles"] == len(m["triangles"]) > 500
    assert set(m["region_names"]) == {"core", "background"}
    assert m["stats"]["min_angle"] >= 28 - 1e-6


def test_run_job_roundtrip(client):
    doc = dict(examples.SLAB_TE_CHECK)
    job = client.post("/api/run", json={"doc": doc}).json()["job"]
    for _ in range(600):
        st = client.get(f"/api/jobs/{job}").json()
        if st["status"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert st["status"] == "done", st
    res = client.get(f"/api/jobs/{job}/result").json()
    assert abs(res["neff"][0][0] - 2.8487) < 2e-3
    assert len(res["fields"][0][0]) == len(res["nodes"])
    assert any("n_eff" in line for line in st["log"])
    assert client.get("/api/jobs/zzz").status_code == 404
