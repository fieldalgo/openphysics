# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Number of modes (M4): the workspace capability v8 and its mode-count range (1 to 8), the
server's refusal of other counts, and the modes of the optical-shapes-v8 document as Studio
builds it.

Pre-registered checks (blind; tolerances fixed before any mode_count other than 2 was run):

- M4-a: with 2 modes the template's document is byte-equal to the optical-shapes-v7 document
  (``studio_session_fixtures/optical-document-template-v7.json``, written by the Studio of commit
  78b9a60), so its n_eff, TE fraction and effective area are those of that Studio's runs.
- M4-b: a run asking for 8 modes keeps the first two modes of the run asking for 2:
  |Delta Re n_eff| <= 1e-8, |Delta f_TE| <= 1e-6, |Delta A_eff| / A_eff <= 1e-6 and the field
  overlap |<E_2, E_8>|^2 / (<E_2, E_2><E_8, E_8>) >= 1 - 1e-6 on the shared mesh. Both are
  shift-invert eigenpairs of the same matrices (6 and 16 candidates), so the eigenvalues agree to
  near machine precision and the vectors to well inside 1e-6. Every returned mode is ranked by
  Re n_eff and above the threshold n = 1.45. Cases: the template strip (500 x 220 nm Si) and a
  2000 x 400 nm Si core chosen beforehand so that 8 modes may be guided.
- M4-c: the template asking for 8 finds fewer (it is a single-mode-per-polarization strip).
- M4-d: the server refuses 0, 9, 2.5, "2", true and 2.0 from a workspace request, with a message;
  1 and 8 run.
"""
import json
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
import pytest

import simcase

HERE = Path(__file__).resolve().parent
STATIC = Path(simcase.__file__).resolve().parent / "studio" / "static"
TEMPLATE_V7 = HERE / "studio_session_fixtures" / "optical-document-template-v7.json"

_DOCUMENT = r"""
const O = await import(process.argv[1]);
const [w, h, n] = process.argv.slice(2).map(Number);
const doc = O.opticalDocument({height: h, width: Math.min(w, 900), wavelength: 1550, coreMesh: 30, modeCount: n, electric: false,
  heat: false, structure: false, optics: true, shapes: [{name: 'Core', type: 'rect', material: 'Silicon', x: -w / 2, y: 0, w, h}]},
  {materials: {Core: 'Silicon', Oxide: 'Silica', Heater: ''}});
process.stdout.write(JSON.stringify(doc));
"""


def node():
    found = shutil.which("node")
    if found is None:
        pytest.skip("node is not installed; the studio_mode_count.cjs suite checks the page modules")
    return found


def document(width, height, modes):
    """The optical document Studio builds for a Si rectangle core and Modes to find."""
    done = subprocess.run([node(), "--input-type=module", "-e", _DOCUMENT, (STATIC / "workspace-optical.mjs").as_uri(),
                           str(width), str(height), str(modes)], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from simcase.studio import app
    return TestClient(app)


def instance(client):
    return {"workspace_instance": client.get("/api/workspace/capabilities/v8").json()["server_instance"]}


def run_document(client, doc):
    """The result of a document through /api/validate, /api/run and the job routes, as the page sends it."""
    q = instance(client)
    checked = client.post("/api/validate", params=q, json={"doc": doc})
    assert checked.status_code == 200 and checked.json()["ok"], checked.text
    job = client.post("/api/run", params=q, json={"doc": doc}).json()["job"]
    deadline = time.monotonic() + 600
    while (status := client.get(f"/api/jobs/{job}", params=q).json())["status"] == "running":
        assert time.monotonic() < deadline, "the optical job did not finish"
        time.sleep(0.2)
    assert status["status"] == "done", status
    return client.get(f"/api/jobs/{job}/result", params=q).json()


def test_capability_v8_drops_the_fixed_mode_count_for_its_range(client):
    v7 = client.get("/api/workspace/capabilities/v7").json()
    response = client.get("/api/workspace/capabilities/v8")
    caps = response.json()
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert caps["schema_version"] == 8 and caps["adapter"] == "optical-shapes-v8"
    assert caps["mode_count_range"] == [1, 8] and caps["mode_count_default"] == 2
    assert "mode_count" not in caps["settings"]
    assert caps["settings"] == {k: v for k, v in v7["settings"].items() if k != "mode_count"}
    same = ("schema_version", "adapter", "settings", "mode_count_range", "mode_count_default")
    assert {k: v for k, v in caps.items() if k not in same} == {k: v for k, v in v7.items() if k not in same}
    # the earlier contracts are unchanged: their fixed two modes stay
    assert v7["adapter"] == "optical-shapes-v7" and v7["settings"]["mode_count"] == 2


@pytest.mark.parametrize("value,shown", [("0", "0"), ("9", "9"), ("2.5", "2.5"), ('"2"', '"2"'), ("true", "true"),
                                         ("2.0", "2.0, written with a decimal point or an exponent"), ("null", "null")])
def test_m4d_the_server_refuses_a_workspace_mode_count_outside_1_to_8(client, value, shown):
    doc = json.loads(document(500, 220, 2))
    body = json.dumps({"doc": doc}).replace('"mode_count": 2', f'"mode_count": {value}')
    assert f'"mode_count": {value}' in body
    for endpoint in ("/api/validate", "/api/run"):
        response = client.post(endpoint, params=instance(client), content=body, headers={"content-type": "application/json"})
        assert response.status_code == 400, (endpoint, response.text)
        assert response.json()["detail"] == f"Modes to find must be a whole number from 1 to 8 (got {shown}).", endpoint


def test_m4d_requests_without_a_workspace_instance_keep_the_document_rules(client):
    """The single-page Studio sends no workspace instance: its documents are read as before (the
    engine's own rules: a mode count of 9 is a valid document)."""
    doc = json.loads(document(500, 220, 2))
    doc["physics"]["em1"]["mode_count"] = 9
    response = client.post("/api/validate", json={"doc": doc})
    assert response.status_code == 200 and response.json()["ok"], response.text


def test_m4a_two_modes_is_the_version_7_document_byte_for_byte():
    assert document(500, 220, 2) == TEMPLATE_V7.read_text(encoding="utf-8")


def _modes(result):
    """Re n_eff, the engine's f_TE and A_eff of the first study point, and the centroid field."""
    re = np.asarray(result["effective_index"]["values"][0])
    post = result["summary"]["mode_postprocessing"]
    field = result["vector_fields"][0]
    e = np.asarray(field["real"]) + 1j * np.asarray(field["imag"])        # (modes, triangles, 3)
    return re, np.asarray(post["te_polarization_fraction"]["values"][0], float), \
        np.asarray(post["effective_area"]["values"][0], float), e, result


def _areas(result):
    x = np.asarray(result["node_coordinates"])
    t = np.asarray(result["triangles"])
    p0, p1, p2 = x[t[:, 0]], x[t[:, 1]], x[t[:, 2]]
    return 0.5 * np.abs((p1[:, 0] - p0[:, 0]) * (p2[:, 1] - p0[:, 1]) - (p1[:, 1] - p0[:, 1]) * (p2[:, 0] - p0[:, 0]))


@pytest.mark.slow
@pytest.mark.parametrize("width,height,found", [(500, 220, None), (2000, 400, 8)])
def test_m4b_eight_modes_keep_the_two_lowest_and_the_guided_range(client, width, height, found):
    re2, te2, area2, e2, r2 = _modes(run_document(client, json.loads(document(width, height, 2))))
    re8, te8, area8, e8, r8 = _modes(run_document(client, json.loads(document(width, height, 8))))
    assert len(re2) == 2 and 1 <= len(re8) <= 8
    if found is not None:
        assert len(re8) == found
    assert r2["triangles"] == r8["triangles"] and r2["node_coordinates"] == r8["node_coordinates"]
    a = _areas(r2)[:, None]
    for i in range(2):
        assert abs(re8[i] - re2[i]) <= 1e-8
        assert abs(te8[i] - te2[i]) <= 1e-6
        assert abs(area8[i] - area2[i]) <= 1e-6 * area2[i]
        overlap = abs(np.sum(a * e2[i] * np.conj(e8[i]))) ** 2 / (np.sum(a * abs(e2[i]) ** 2) * np.sum(a * abs(e8[i]) ** 2))
        assert overlap >= 1 - 1e-6
    # no degenerate pair among the compared modes (the per-member values would not be defined)
    assert re8[0] - re8[1] > 1e-3
    assert np.all(np.diff(re8) <= 0) and np.all(re8 > 1.45)


@pytest.mark.slow
def test_m4c_the_template_asking_for_eight_finds_fewer(client):
    re, te, area, e, result = _modes(run_document(client, json.loads(document(500, 220, 8))))
    assert 2 <= len(re) < 8
    assert e.shape[0] == len(re) == len(te) == len(area)
    assert np.all(np.diff(re) <= 0) and np.all(re > 1.45)
    # one mode run: the lowest mode alone
    one = _modes(run_document(client, json.loads(document(500, 220, 1))))[0]
    assert len(one) == 1 and abs(one[0] - re[0]) <= 1e-8
