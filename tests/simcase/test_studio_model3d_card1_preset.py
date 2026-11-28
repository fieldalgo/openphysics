# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""V11: card 1's note names its preset heat source, "1e12 W/m³ in Si (top) (4 W)".

The 4 W is the density in the document times the volume of the Si (top) region that the server's
check answers (exact volumes from the complex, in µm³). It is not the note's own arithmetic.
"""
import json
import re

import pytest

import simcase

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

from simcase.studio import app  # noqa: E402

STATIC = __import__("pathlib").Path(simcase.__file__).parent / "studio" / "static"


def test_the_preset_heat_source_is_4_w():
    doc = json.loads((STATIC / "model3d-layer-stack-3d.json").read_text(encoding="utf-8"))
    assert doc["physics"]["heat"]["heat_source_density"] == {"Si (top)": "1e12 W/m^3"}
    answer = TestClient(app).post("/api/model3d/check", json={"doc": doc}).json()
    assert answer["ok"] is True
    volume_um3 = {r["name"]: r["volume"] for r in answer["regions"]}["Si (top)"]
    watts = 1e12 * volume_um3 * 1e-18
    assert watts == pytest.approx(4.0, rel=1e-12)
    note = re.search(r"note:'([^']*)'", (STATIC / "workspace-model3d.mjs").read_text(encoding="utf-8")).group(1)
    assert "Preset: heat source 1e12 W/m³ in Si (top) (4 W)" in note
