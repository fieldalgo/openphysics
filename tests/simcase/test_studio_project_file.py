# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Project file version 1 (V-P2): each model's ``bytes`` and ``digest`` are the UTF-8 length and
SHA-256 of its session text as the file holds it, computed here with Python's hashlib, independent
of Studio's JavaScript SHA-256. The fixture is what ``writeProject`` writes today
(tests/simcase/studio_project_file.cjs checks that, byte for byte)."""

import hashlib
import json
from pathlib import Path

FIXTURE = Path(__file__).parent / "studio_session_fixtures" / "project-v1.json"


def _sessions(text):
    """The raw text of each entry's session, located by the JSON grammar (raw_decode)."""
    decoder, doc, spans, at = json.JSONDecoder(), json.loads(text), [], 0
    for model in doc["models"]:
        at = text.index('"session":', text.index(json.dumps(model["digest"]), at)) + len('"session":')
        _, end = decoder.raw_decode(text, at)
        spans.append(text[at:end])
        at = end
    return doc, spans


def test_project_entry_sizes_and_digests_equal_hashlib():
    raw = FIXTURE.read_bytes()
    text = raw.decode("utf-8")
    doc, spans = _sessions(text)
    assert list(doc) == ["format", "version", "name", "savedAt", "studio", "active", "models"]
    assert doc["format"] == "openphysics-studio-project" and doc["version"] == 1
    assert [m["kind"] for m in doc["models"]] == ["workspace", "multiphysics"]
    for model, span in zip(doc["models"], spans, strict=True):
        data = span.encode("utf-8")
        assert model["bytes"] == len(data)
        assert model["digest"] == "sha256:" + hashlib.sha256(data).hexdigest()
        assert json.loads(span) == model["session"]
    # the multiphysics entry is the version 8 session fixture, byte for byte
    session = (FIXTURE.parent / "multiphysics-v8.json").read_bytes()
    assert spans[1].encode("utf-8") == session
