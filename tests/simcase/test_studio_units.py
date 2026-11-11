# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""P2-19 (units and naming batch): Studio reads every document from the request's raw bytes and
writes it back as authored.

- an unchanged authored document (every shipped example a Studio route accepts, none of which
  spells a string escape) comes back with every key, string and number as written: the reply's
  document is the file's text without its insignificant whitespace, byte for byte;
- a number keeps its written digits, beyond what a double holds;
- ``/api/validate`` returns every diagnostic ``simcase.reader.check`` gives (errors, warnings and
  notes), for an accepted and for a refused document;
- the output of every JS document builder (dumped by ``studio_document_builders.cjs``) validates
  in Python with zero errors.

The route-boundary refusals (duplicate keys, ``NaN``, ``Infinity``, malformed and non-UTF-8 text,
the UTF-8 byte order mark) are in ``test_studio_security.py``. Saved projects (versions 1-5
refused by name), sessions (version 6, coordinates as quantity strings) and the CSV tables
(``name [unit]`` headers, SI values) are checked by the cjs suite
(``studio_workspace_height.cjs``, ``studio_workspace_heat.cjs``, ``studio_workspace_notebook.cjs``,
``studio_workspace_shapes.cjs``, ``studio_workspace_profile.cjs``,
``studio_workspace_optical_study.cjs``).
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="install the Studio extra: pip install 'simcase[studio]'")
from fastapi.testclient import TestClient  # noqa: E402

import simcase  # noqa: E402
from simcase import evaluate_geometry, parse_geometry, reader  # noqa: E402
from simcase.studio import server  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples" / "simcase"
JSON_BODY = {"content-type": "application/json"}
HEADLESS = {"electric.steady2d", "joule.steady2d", "joule.temperature2d", "mechanics.elasticity2d",
            "mechanics.thermoelastic2d"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server, "run", lambda *a, **k: pytest.fail("a check started a solve"))
    return TestClient(server.app)


def _without_whitespace(text: str) -> str:
    """JSON text without the whitespace between tokens (strings unchanged)."""
    out, inside, i = [], False, 0
    while i < len(text):
        ch = text[i]
        if inside:
            out.append(ch)
            if ch == "\\":
                out.append(text[i + 1])
                i += 1
            elif ch == '"':
                inside = False
        elif ch == '"':
            inside = True
            out.append(ch)
        elif ch not in " \t\r\n":
            out.append(ch)
        i += 1
    return "".join(out)


def _route(tree):
    """The Studio validation route of a document and its envelope, or None for a headless type."""
    types = {p.get("type") for p in tree["physics"].values()}
    if types & HEADLESS:
        return None
    if "thermal.steady2d" in types:
        return "/api/thermal/validate", True
    if "thermal.transient2d" in types:
        return "/api/thermal/transient/validate", True
    return "/api/validate", False


def _post(client, path, doc_bytes: bytes, tagged: bool):
    tail = b',"client_revision":1,"request_seq":1}' if tagged else b"}"
    return client.post(path, content=b'{"doc":' + doc_bytes + tail, headers=JSON_BODY)


def _studio_examples():
    out = []
    for path in sorted(EXAMPLES.glob("*.json")):
        tree, found = reader.parse(path.read_bytes())
        assert tree is not None and not found, path.name
        if _route(tree) is not None:
            out.append(path.name)
    return out


STUDIO_EXAMPLES = _studio_examples()
OPTICAL_EXAMPLES = [name for name in STUDIO_EXAMPLES
                    if _route(reader.parse((EXAMPLES / name).read_bytes())[0])[0] == "/api/validate"]


def test_the_round_trip_covers_the_studio_examples():
    # every em.modes2d, em.cavity3d and heat example has a Studio validation route
    assert len(STUDIO_EXAMPLES) == 25 and len(OPTICAL_EXAMPLES) == 16, STUDIO_EXAMPLES
    assert {"soi_strip.json", "cavity_box.json", "thermal_regions.json",
            "transient_thermal_uniform.json"} <= set(STUDIO_EXAMPLES)


@pytest.mark.parametrize("name", STUDIO_EXAMPLES)
def test_an_unchanged_authored_document_round_trips_byte_identical(client, name):
    raw = (EXAMPLES / name).read_bytes()
    tree, _ = reader.parse(raw)
    path, tagged = _route(tree)
    r = _post(client, path, raw, tagged)                   # the file as authored, whitespace and all
    assert r.status_code in (200, 400), r.text
    reply, found = reader.parse(r.content)
    assert not found
    if not reply["ok"]:
        # Studio's transient page shows prescribed-temperature and insulated sides only
        assert name == "transient_thermal_boundary.json" and reply["error"]["code"] == "unsupported_physics"
        return
    authored = _without_whitespace(raw.decode("utf-8"))
    assert ('"doc":' + authored + ',"diagnostics":').encode("utf-8") in r.content
    assert reply["doc"] == tree


def test_a_number_keeps_its_written_digits(client):
    text = (EXAMPLES / "soi_strip.json").read_text(encoding="utf-8")
    assert text.count('"effective_index_threshold": 1.45,') == 1
    written = "1.4500000000000000000000001"                   # no double holds these digits
    text = text.replace('"effective_index_threshold": 1.45,', f'"effective_index_threshold": {written},')
    r = _post(client, "/api/validate", text.encode("utf-8"), False)
    assert r.status_code == 200 and r.json()["ok"] is True, r.text
    assert f'"effective_index_threshold":{written},'.encode() in r.content
    assert reader.parse(r.content)[0]["doc"] == reader.parse(text.encode("utf-8"))[0]


@pytest.mark.parametrize("name", OPTICAL_EXAMPLES)
def test_validate_returns_every_diagnostic_of_an_accepted_document(client, name):
    raw = (EXAMPLES / name).read_bytes()
    tree, _ = reader.parse(raw)
    doc, expected = reader.check(tree)
    assert doc is not None
    reply = _post(client, "/api/validate", raw, False).json()
    assert reply["ok"] is True
    assert reply["diagnostics"] == json.loads(json.dumps([d.as_dict() for d in expected]))


def test_validate_returns_every_diagnostic_of_a_refused_document(client):
    tree, _ = reader.parse((EXAMPLES / "soi_strip.json").read_bytes())
    tree["physics"]["em1"]["vacuum_wavelength"] = "1.55 K"            # a dimension error
    tree["physics"]["em1"]["mode_cuont"] = 2                           # an unknown key
    tree["geometry"]["shapes"][0]["w"] = 0.5000001                    # off the pm grid: a warning
    tree["geometry"]["shapes"][0]["material"] = "physmat:Si3N4"         # an assumed datum: a note
    doc, expected = reader.check(tree)
    assert doc is None
    assert sorted(d.severity for d in expected) == ["error", "error", "info", "warning"], expected
    body = reader.dumps({"doc": tree}, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    reply = client.post("/api/validate", content=body, headers=JSON_BODY).json()
    assert reply["ok"] is False and "doc" not in reply
    assert reply["diagnostics"] == json.loads(json.dumps([d.as_dict() for d in expected]))
    for d in expected:
        if d.severity == "error":
            assert d.message in reply["error"]


def _builder_documents(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed; the cjs suite runs the builders itself")
    dump = tmp_path / "builders.json"
    static = Path(simcase.__file__).resolve().parent / "studio" / "static"     # the imported package's
    env = {**os.environ, "OPENPHYSICS_STUDIO_BUILDER_DUMP": str(dump), "OPENPHYSICS_STUDIO_STATIC": str(static)}
    done = subprocess.run([node, "--test", str(ROOT / "tests" / "simcase" / "studio_document_builders.cjs")],
                          capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT)
    assert done.returncode == 0, done.stdout + done.stderr
    return json.loads(dump.read_text(encoding="utf-8"))


def test_every_js_builder_output_validates_in_python(tmp_path):
    docs = _builder_documents(tmp_path)
    # the heat plate (3), the optical study (3) and the geometry lab (new, 2 starters, 2 edits)
    assert len(docs) == 11, sorted(docs)
    for label, text in docs.items():
        doc, found = reader.check(text)                    # the text as the page sends it
        errors = [d for d in found if d.severity == "error"]
        if label in ("geometry lab new document", "geometry lab edited number"):
            # the lab's own new document is geometry only (the lab runs no physics, geometry_lab.md):
            # the geometry reader that `python -m simcase geometry` and the lab's route use refuses
            # nothing, and the whole-document reader names only the physics block it leaves out
            evaluate_geometry(parse_geometry(reader.parse(text)[0]))
            assert [(d.code, d.path) for d in errors] == [("E-KEY-MISSING", "physics")], label
            continue
        assert doc is not None and errors == [], (label, errors)
