# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Studio routes of multiphysics models (D2): capabilities, the template, validate, run with
progress, results, stop and refusals; engine diagnostics mapped into the workspace's words.

The coupled results are the engine's: a Studio run of a document gives exactly the numbers
``simcase.multiphysics.run`` gives for that document. Cycles and loops use the test-local relay
kinds of the engine tests (no installed kind forms a cycle)."""
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

import numpy as np
import pytest

import simcase
from simcase import Document, multiphysics, reader, registry

from multiphysics_fixtures import relay_document, relay_kind

STATIC = Path(simcase.__file__).parent / "studio" / "static"


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from simcase.studio import app
    return TestClient(app)


@pytest.fixture
def api():
    from simcase.studio import multiphysics_api
    return multiphysics_api


@pytest.fixture
def relays(monkeypatch, api):
    """The engine tests' relay kinds, registered for one test, and let through Studio's run gate."""
    registry.kinds()
    for kind in (relay_kind("test.relay"), relay_kind("test.relaymk", unit="mK")):
        monkeypatch.setitem(registry._KINDS, kind.name, kind)
    monkeypatch.setitem(api.STUDIO_TYPES, "test.relay", {"label": "Relay", "prefix": "relay",
                                                        "entry": {"type": "test.relay"}})


def template():
    return json.loads((STATIC / "multiphysics-template.json").read_text(encoding="utf-8"))


def wait(client, job, timeout=120):
    end = time.time() + timeout
    events = []
    while time.time() < end:
        s = client.get(f"/api/multiphysics/jobs/{job}", params={"after": len(events)}).json()
        events += s["events"]
        assert s["event_count"] == len(events)
        if s["status"] != "running":
            return s, events
        time.sleep(0.05)
    raise AssertionError("job did not finish")


# -- capabilities and the template --------------------------------------------------------------

def test_capabilities_list_the_installed_kinds_and_what_studio_adds(client):
    reply = client.get("/api/multiphysics/capabilities")
    assert reply.status_code == 200 and reply.headers["cache-control"] == "no-store"
    caps = reply.json()
    assert caps["envelope"] == multiphysics.ENVELOPE and caps["result"] == multiphysics.RESULT_FORMAT
    assert caps["transfers"] == ["same_mesh"]
    types = {t["type"]: t for p in caps["providers"] for t in p["types"]}
    assert {t for t, v in types.items() if v["addable"]} == {"thermal.steady2d", "em.modes2d"}
    assert types["joule.temperature2d"]["reason"].startswith("solves its own coupling")
    assert types["mechanics.thermoelastic2d"]["reason"].startswith("solves its own coupling")
    assert types["electric.steady2d"]["reason"] == "is not part of multiphysics models in Studio in this release"
    heat = {p["name"]: p for p in types["thermal.steady2d"]["ports"]}
    assert heat["temperature"] == {"name": "temperature", "direction": "output", "quantity": "temperature",
                                   "unit": "K", "location": "node"}
    modes = {p["name"]: p for p in types["em.modes2d"]["ports"]}
    assert modes["temperature"] == {"name": "temperature", "direction": "input", "quantity": "temperature",
                                    "unit": "K", "location": "element", "combine": "single"}
    assert "<" not in reply.text                  # data only: no code, no markup


def test_the_workspace_constants_agree_with_physmat():
    """The thermo-optic data the Settings show and Fill from physmat copies are physmat's."""
    import physmat
    text = (STATIC / "workspace-multiphysics.mjs").read_text(encoding="utf-8")
    for name, value in (("Si", 1.8e-4), ("SiO2", 1.0e-5)):
        assert float(physmat.material(name).properties["thermo_optic_dn_dT"].value) == value
        assert f"'physmat:{name}':Object.freeze({{label:" in text and f"coefficient:{value:.1e}".replace("e-0", "e-") in text
    assert multiphysics.LIBRARY_REFERENCE_TEMPERATURE == 300.0


def test_the_template_round_trips_and_validates_clean(client):
    raw = client.get("/api/multiphysics/template")
    assert raw.status_code == 200 and raw.content == (STATIC / "multiphysics-template.json").read_bytes()
    tree = raw.json()
    assert tree["openphysics"] == multiphysics.ENVELOPE
    reply = client.post("/api/multiphysics/validate", json={"doc": tree})
    assert reply.status_code == 200
    body = reply.json()
    assert body["ok"] is True and body["run_refusal"] is None
    assert body["solve_order"] == [["heat1"], ["modes1"]]
    assert [d for d in body["diagnostics"] if d["severity"] != "info"] == []
    # the document comes back as sent, digits and all
    parsed, found = reader.parse(raw.content)
    assert found == [] and reader.dumps(json.loads(reply.content)["doc"]) == reader.dumps(json.loads(raw.content))
    assert json.loads(reply.content)["doc"] == tree
    # geometry of the design: a 500 x 220 nm core, a 2 um x 100 nm heater 1.1 um above it, 6 x 4.5 um
    xs = tree["geometry"]["components"]["xs"]
    core, heater = xs["features"]
    assert (core["w"], core["h"], core["material"]) == (0.5, 0.22, "physmat:Si")
    assert (heater["w"], heater["h"], heater["y"] - (core["y"] + core["h"])) == (2, 0.1, pytest.approx(1.1))
    assert (xs["domain"]["xmax"] - xs["domain"]["xmin"], xs["domain"]["ymax"] - xs["domain"]["ymin"]) == (6, 4.5)
    assert xs["background"]["material"] == "physmat:SiO2"
    assert tree["physics"]["heat1"]["prescribed_temperature"] == {"bottom": "300 K"}
    assert tree["physics"]["modes1"]["vacuum_wavelength"] == "1550 nm"


# -- running ------------------------------------------------------------------------------------

def test_a_studio_run_gives_the_engines_numbers_with_progress_events(client):
    tree = template()
    reply = client.post("/api/multiphysics/run", json={"doc": tree})
    assert reply.status_code == 200
    started = reply.json()
    assert started["job"].startswith("mp-") and started["solve_order"] == [["heat1"], ["modes1"]]
    status, events = wait(client, started["job"])
    assert status["status"] == "done" and status["error"] is None and status["has_result"] is True
    assert [(e["event"], e["physics"]) for e in events] == [
        ("physics_started", "heat1"), ("physics_finished", "heat1"),
        ("physics_started", "modes1"), ("physics_finished", "modes1")]
    result = client.get(f"/api/multiphysics/jobs/{started['job']}/result").json()
    engine = multiphysics.run(Document.from_dict(template()), verbose=False)
    summary = engine.summary()
    assert result["result"] == "multiphysics-run-v1"
    assert result["solve_order"] == summary["solve_order"]
    assert result["couplings"] == summary["couplings"]
    assert result["couplings"]["heat1_to_modes1"]["max_abs_difference"] == {"value": 0.0, "unit": "K"}
    # the same engine on the same document: exactly equal
    assert result["physics"]["modes1"]["effective_index"]["values"] == \
        np.asarray(engine.results["modes1"].effective_index).tolist()
    coupled = engine.results["modes1"].coupled_inputs
    assert result["physics"]["modes1"]["coupled"]["temperature"]["values"] == coupled["temperature"].tolist()
    assert result["physics"]["modes1"]["coupled"]["refractive_index"]["n"] == np.real(coupled["refractive_index"][0]).tolist()
    assert result["physics"]["heat1"]["temperature"]["values"] == np.asarray(engine.results["heat1"].temperature).tolist()
    mesh = result["mesh"]
    assert len(mesh["triangles"]) == len(coupled["temperature"])
    assert mesh["region_names"] == list(engine.results["modes1"].region_names)
    # n - n0 = (dn/dT)(T - T_ref) per triangle: Si 1.8e-4 1/K in the core, the heater's 0 1/K
    change = result["physics"]["modes1"]["coupled"]["index_change"]
    for t, r, dn in zip(coupled["temperature"], mesh["regions"], change):
        name = mesh["region_names"][r]
        expected = {"core": 1.8e-4 * (t - 300.0), "heater": 0.0, "background": 1.0e-5 * (t - 300.0)}[name]
        assert dn == pytest.approx(expected, rel=1e-12, abs=1e-18)
    # and the engine's n moved by exactly that much from n0 in the heater (dn/dT 0): n = 1.444
    heater = mesh["region_names"].index("heater")
    assert {n for n, r in zip(result["physics"]["modes1"]["coupled"]["refractive_index"]["n"], mesh["regions"])
            if r == heater} == {1.444}
    # the heater warms the core: every core triangle is above 300 K
    core = mesh["region_names"].index("core")
    assert min(t for t, r in zip(coupled["temperature"], mesh["regions"]) if r == core) > 300.0


def test_one_physics_runs_as_format_0_3_in_the_same_layout(client):
    tree = template()
    del tree["physics"]["heat1"], tree["couplings"]
    tree["openphysics"] = "0.3"
    for record in tree["materials"].values():
        record.pop("thermo_optic_coefficient"), record.pop("reference_temperature")
    status, events = wait(client, client.post("/api/multiphysics/run", json={"doc": tree}).json()["job"])
    assert status["status"] == "done", status
    assert [e["event"] for e in events] == ["physics_started", "physics_finished"]
    result = client.get(f"/api/multiphysics/jobs/{status['job']}/result").json()
    assert result["solve_order"] == [["modes1"]] and result["couplings"] == {}
    engine = simcase.run(Document.from_dict(tree), verbose=False)
    assert result["physics"]["modes1"]["effective_index"]["values"] == np.asarray(engine.effective_index).tolist()
    assert "coupled" not in result["physics"]["modes1"]


def test_an_accepted_loop_reports_its_iterations_and_a_diverging_one_keeps_no_result(client, relays):
    loop = {"physics": ["a", "b"], "method": "fixed_point",
            "tolerance": {"port": "a.y", "norm": "max_abs", "value": "1e-10 K"}, "max_iterations": 300,
            "relaxation": 0.5}
    doc = relay_document({"a": ("test.relay", 0.5, 1), "b": ("test.relay", 0.5, 2)},
                         {"ab": ("a.y", "b.x"), "ba": ("b.y", "a.x")}, loops=[loop])
    status, events = wait(client, client.post("/api/multiphysics/run", json={"doc": doc}).json()["job"])
    assert status["status"] == "done", status
    kinds = [e["event"] for e in events]
    assert kinds[0] == "loop_started" and kinds[-1] == "loop_finished" and set(kinds[1:-1]) == {"loop_iteration"}
    assert events[-1]["iterations"] == len(kinds) - 1
    assert all(e["unit"] == "K" for e in events[1:-1])
    result = client.get(f"/api/multiphysics/jobs/{status['job']}/result").json()
    assert result["loops"][0]["converged"] is True and result["solve_order"] == [["a", "b"]]
    # gain 2 diverges: the job fails with the engine's history and has no result
    doc["physics"]["a"]["gain"] = doc["physics"]["b"]["gain"] = 2.0
    doc["study"]["loops"][0].update(max_iterations=8, relaxation=1.0)
    status, events = wait(client, client.post("/api/multiphysics/run", json={"doc": doc}).json()["job"])
    assert status["status"] == "error" and status["has_result"] is False
    error = status["error"]
    assert error["code"] == "E-LOOP-DIVERGED" and error["physics"] == ["a", "b"] and error["unit"] == "K"
    assert len(error["residuals"]) == 7 == sum(e["event"] == "loop_iteration" for e in events)
    assert "did not converge in 8 iterations" in error["message"]
    assert client.get(f"/api/multiphysics/jobs/{status['job']}/result").status_code == 409


def test_a_failure_names_the_physics_and_an_unexpected_one_keeps_its_details_in_the_log(client, api, monkeypatch, caplog):
    real = multiphysics.run

    def failing(doc, verbose=True, *, on_event=None):
        def emit(event):
            on_event(event)
            if event["event"] == "physics_started" and event["physics"] == "modes1":
                raise RuntimeError("secret internal detail")
        return real(doc, verbose, on_event=emit)

    monkeypatch.setattr(api.multiphysics, "run", failing)
    with caplog.at_level("WARNING", logger="simcase.studio"):
        status, events = wait(client, client.post("/api/multiphysics/run", json={"doc": template()}).json()["job"])
    assert status["status"] == "error"
    from simcase.studio.bodies import UNEXPECTED
    assert status["error"] == {"physics": "modes1", "message": UNEXPECTED}
    assert "secret internal detail" not in json.dumps(status)
    assert "secret internal detail" in caplog.text
    assert [e["event"] for e in events] == ["physics_started", "physics_finished", "physics_started"]


def test_a_job_whose_thread_does_not_start_holds_no_slot(api):
    jobs = api.Jobs()

    def refuse(target, args):
        raise RuntimeError("cannot start a thread")

    for _ in range(api.MAX_RUNNING + 1):
        with pytest.raises(RuntimeError):
            jobs.start(template(), [], refuse)
    assert jobs.jobs == {}


def test_stop_ends_a_run_at_its_next_step_and_keeps_nothing(api):
    jobs = api.Jobs()
    held = []
    reply = jobs.start(template(), [], lambda target, args: held.append((target, args)))
    assert jobs.stop(reply["job"]) == {"job": reply["job"], "status": "running", "stopping": True}
    target, args = held[0]
    target(*args)                                   # the worker, run here: it stops at its first event
    status = jobs.status(reply["job"])
    assert status["status"] == "stopped" and status["has_result"] is False
    assert status["error"] == {"message": "Run stopped. No result was kept."}
    with pytest.raises(api.Refused) as caught:
        jobs.result(reply["job"])
    assert caught.value.status == 409


# -- refusals -----------------------------------------------------------------------------------

def test_refusals_are_named(client, api, monkeypatch):
    # unreadable bodies, as on every document route
    bad = client.post("/api/multiphysics/validate", content=b'{"doc": {"a": 1, "a": 2}}',
                      headers={"content-type": "application/json"})
    assert bad.status_code == 200 and bad.json()["ok"] is False
    assert bad.json()["diagnostics"][0]["code"] == "E-KEY-DUPLICATE"
    assert client.post("/api/multiphysics/run", content=b'{"doc": NaN}',
                       headers={"content-type": "application/json"}).status_code == 400
    assert client.post("/api/multiphysics/run", content=b'{"doc": {"a": 1, "a": 2}}',
                       headers={"content-type": "application/json"}).status_code == 400
    assert client.post("/api/multiphysics/run", content=b"x", headers={"content-type": "text/plain"}).status_code == 415
    # a sweep is checked, and running it is refused with its message
    sweep = template()
    sweep["study"] = {"type": "sweep", "parameter": "physics.modes1.vacuum_wavelength",
                      "values": {"unit": "nm", "values": [1540, 1550, 1560]}}
    checked = client.post("/api/multiphysics/validate", json={"doc": sweep}).json()
    assert checked["ok"] is True and checked["run_refusal"] == api.SWEEP_REFUSAL
    refused = client.post("/api/multiphysics/run", json={"doc": sweep})
    assert refused.status_code == 400 and refused.json()["detail"].startswith("Sweeps of coupled models cannot run")
    # a one-physics sweep: this view runs one point
    single = template()
    del single["physics"]["heat1"], single["couplings"]
    single["openphysics"] = "0.3"
    for record in single["materials"].values():
        record.pop("thermo_optic_coefficient"), record.pop("reference_temperature")
    single["study"] = sweep["study"]
    assert client.post("/api/multiphysics/validate", json={"doc": single}).json()["run_refusal"] == api.SINGLE_SWEEP_REFUSAL
    assert client.post("/api/multiphysics/run", json={"doc": single}).status_code == 400
    # a kind Studio does not run
    other = template()
    other["physics"]["electric1"] = {"type": "electric.steady2d"}
    refused = client.post("/api/multiphysics/run", json={"doc": other})
    assert refused.status_code == 400 and "electric.steady2d" in refused.json()["detail"]
    # an invalid document: the engine's refusal text
    broken = template()
    broken["couplings"]["heat1_to_modes1"]["from"] = "heat9.temperature"
    refused = client.post("/api/multiphysics/run", json={"doc": broken})
    assert refused.status_code == 400 and "heat9" in refused.json()["detail"]
    # jobs: unknown, a result too early, the cap, another server instance
    assert client.get("/api/multiphysics/jobs/mp-unknown").status_code == 404
    assert client.post("/api/multiphysics/jobs/mp-unknown/stop").status_code == 404
    assert client.get("/api/multiphysics/jobs/mp-unknown/result").status_code == 404
    assert client.get("/api/multiphysics/jobs/x", params={"workspace_instance": "0" * 32}).status_code == 409
    from simcase.studio import server
    jobs = api.Jobs()
    monkeypatch.setattr(server, "_multiphysics_jobs", jobs)
    monkeypatch.setattr(server, "_start_thermal_thread", lambda target, args: None)    # jobs stay running
    first = [client.post("/api/multiphysics/run", json={"doc": template()}) for _ in range(api.MAX_RUNNING)]
    assert all(r.status_code == 200 for r in first)
    assert client.get(f"/api/multiphysics/jobs/{first[0].json()['job']}/result").status_code == 409
    over = client.post("/api/multiphysics/run", json={"doc": template()})
    assert over.status_code == 429 and "wait for one to finish" in over.json()["detail"]


def test_an_order_shows_while_a_coupling_is_wrong(client, relays):
    doc = relay_document({"a": ("test.relay", 0.5, 1), "b": ("test.relay", 0.5, 2), "c": ("test.relay", 0.5, 0)},
                         {"ab": ("a.y", "b.x"), "ba": ("b.y", "a.x"), "bad": ("c.y", "z.x")})
    body = client.post("/api/multiphysics/validate", json={"doc": doc}).json()
    assert body["ok"] is False and body["solve_order"] == [["a", "b"], ["c"]]


# -- the workspace's words for real engine diagnostics ------------------------------------------

_MAP = r"""
const [module, payload] = process.argv.slice(1);
const m = await import(module);
const cases = JSON.parse(payload);
const out = cases.map(({doc, caps, diagnostics}) => m.mapDiagnostics(doc, m.kindCatalog(caps), diagnostics)
  .map(x => ({node: x.node, text: x.text, fix: x.fix, code: x.code})));
process.stdout.write(JSON.stringify(out));
"""

RELAY_TYPES = [{"type": t, "label": t, "field": "heat", "addable": True, "prefix": "r", "entry": {"type": t},
                "ports": [{"name": "x", "direction": "input", "quantity": "temperature", "unit": u, "location": "node",
                           "combine": "sum"},
                          {"name": "y", "direction": "output", "quantity": "temperature", "unit": u, "location": "node"}]} for t, u in (("test.relay", "K"), ("test.relaymk", "mK"))]


def _map(client, cases):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed; studio_workspace_multiphysics.cjs runs in the cjs suite")
    caps = client.get("/api/multiphysics/capabilities").json()
    caps["providers"].append({"name": "test-relays", "version": "1", "status": "available", "error": None,
                              "types": RELAY_TYPES})
    payload = []
    for doc in cases:
        body = client.post("/api/multiphysics/validate", json={"doc": doc}).json()
        payload.append({"doc": doc, "caps": caps, "diagnostics": body["diagnostics"]})
    done = subprocess.run([node, "--input-type=module", "-e", _MAP, (STATIC / "workspace-multiphysics.mjs").as_uri(),
                           json.dumps(payload)], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    return json.loads(done.stdout)


def test_engine_diagnostics_reach_the_workspace_in_the_designs_words(client, relays):
    def variant(change):
        tree = template()
        change(tree)
        return tree

    def second_heat(t):
        t["physics"]["heat2"] = {"type": "thermal.steady2d", "prescribed_temperature": {"bottom": "300 K"}}
        t["couplings"]["heat2_to_modes1"] = {"from": "heat2.temperature", "to": "modes1.temperature",
                                             "transfer": "same_mesh"}

    cases = [
        variant(lambda t: t["couplings"]["heat1_to_modes1"].update({"from": "heat9.temperature"})),
        variant(lambda t: t["couplings"]["heat1_to_modes1"].update({"from": "heat1.temp"})),
        variant(lambda t: t["couplings"]["heat1_to_modes1"].update({"from": "heat1.heat_flux"})),
        variant(lambda t: t["couplings"]["heat1_to_modes1"].update({"transfer": "nearest"})),
        variant(lambda t: t["mesh"].update({"grading": {"position": ["0 um", "0.11 um"], "near": "0.01 um", "far": "0.08 um", "refinement_distance": "1 um"}})),
        variant(second_heat),
        variant(lambda t: t["materials"]["heater"].pop("thermo_optic_coefficient")),
        relay_document({"a": ("test.relay", 0.5, 1)}, {"self": ("a.y", "a.x")}),
        relay_document({"a": ("test.relay", 0.5, 1), "m": ("test.relaymk", 0.5, 1)}, {"x": ("a.y", "m.x")}),
        relay_document({"a": ("test.relay", 0.5, 1), "b": ("test.relay", 0.5, 2)},
                       {"ab": ("a.y", "b.x"), "ba": ("b.y", "a.x")}),
    ]
    shown = _map(client, cases)
    first = [next((x for x in s if x["code"].startswith("E-")), None) for s in shown]   # the relays' gains warn
    expected = [
        ("coupling:heat1_to_modes1", "Coupling heat1_to_modes1 names a physics “heat9” that is not in this model. "
                                     "Choose one of Heat 1 and Modes 1, or remove the coupling.", "remove-coupling"),
        ("coupling:heat1_to_modes1", "Coupling heat1_to_modes1: Heat 1 has no output “temp”. Its outputs are "
                                     "temperature and heat flux. Choose one, or remove the coupling.", "remove-coupling"),
        ("coupling:heat1_to_modes1", "Coupling Heat 1 heat flux → Modes 1 temperature: Heat 1 does not send heat flux "
                                     "to couplings in this release. Its coupled outputs are temperature. Choose one, "
                                     "or remove the coupling.", "remove-coupling"),
        ("coupling:heat1_to_modes1", "Coupling heat1_to_modes1 uses transfer “nearest”, which this release does not "
                                     "have. Use “Same mesh”: both physics use Mesh 1.", "use-same-mesh"),
        ("mesh", "Heat 1 and Modes 1 would build different meshes: mesh grading is read only by Modes 1. Remove mesh "
                 "grading so both use the same mesh.", "remove-mesh-key"),
        ("physics:modes1", "Modes 1 temperature takes one source but receives two: from Heat 1 and from Heat 2. "
                           "Remove one of the couplings.", None),
        ("material:heater", "Heater gives a reference temperature but no thermo-optic coefficient; the thermo-optic "
                            "model n = n₀ + (dn/dT)(T − T_ref) needs both. Add the thermo-optic coefficient in "
                            "Materials > Heater.", "fill-physmat"),
        ("coupling:self", "Coupling self connects a to itself. A physics cannot feed its own input; remove this "
                          "coupling.", "remove-coupling"),
        ("coupling:x", "Coupling a y → m x: units differ. a sends temperature in K; m expects mK. Couplings do not "
                       "convert units. Connect a temperature output in mK, or remove this coupling.", "remove-coupling"),
        ("study", "a and b depend on each other. b needs the temperature from a, and a needs the temperature from b. "
                  "Solve them together with an iteration step: fixed point, stop when a y changes by at most 1e-6 K, "
                  "up to 30 iterations, relaxation 0.5.", "accept-loop"),
    ]
    for got, (node, text, fix) in zip(first, expected):
        assert got is not None
        assert got["node"] == node, got
        if text is not None:
            assert got["text"] == text
        assert (got["fix"] or {}).get("action") == fix
    # the heater keeps one of its two keys: an E-KEY-MISSING at the material, shown there
    assert first[6]["code"] == "E-KEY-MISSING"
    # Accept iteration step writes the engine's proposal, and the document then runs
    proposal = first[9]["fix"]["proposal"]
    assert proposal == {"physics": ["a", "b"], "method": "fixed_point",
                        "tolerance": {"port": "a.y", "norm": "max_abs", "value": "1e-6 K"},
                        "max_iterations": 30, "relaxation": 0.5}
    accepted = cases[9]
    accepted["study"] = {"type": "single", "loops": [proposal]}
    assert client.post("/api/multiphysics/validate", json={"doc": accepted}).json()["ok"] is True


def test_a_missing_thermo_optic_model_offers_fill_from_physmat(client):
    tree = template()
    for key in ("thermo_optic_coefficient", "reference_temperature"):
        tree["materials"]["heater"].pop(key)
    (shown,) = _map(client, [tree])
    (message,) = shown
    assert message["node"] == "material:heater" and message["code"] == "E-PROPERTY-MISSING"
    assert message["text"] == ("Heater has no thermo-optic data, but Modes 1 takes its temperature from Heat 1, so every "
                               "optical material needs a thermo-optic coefficient (1/K) and a reference temperature "
                               "(K). Add them in Materials > Heater.")
    assert message["fix"] == {"action": "fill-physmat", "material": "heater", "ref": "physmat:SiO2",
                              "label": "Fill from physmat:SiO2 (1.0e-5 1/K at 300 K)"}
