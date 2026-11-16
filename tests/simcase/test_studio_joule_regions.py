# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Studio's Joule heating routes on named material regions (``/api/joule/validate``, ``/run``).

Pre-registered checks J-S1 to J-S4 (HQ work record ``work/openphysics-studio-joule-regions.md``,
2026-11-16, recorded before the implementation): the Studio result equals ``simcase.run`` on the
same document, array for array and bit for bit (J-S1); refusals reach the reply with their own
text and an unexpected failure with the fixed message (J-S2); the region limits and the shared job
slot apply (J-S3); a result that disagrees with its summary or document is refused (J-S4). The
documents are the two-material strip of tests/simcase/test_joule_temperature_regions.py (T1).
"""
import copy
import logging

import numpy as np
import pytest

pytest.importorskip("fastapi", reason="the studio extra is not installed")
from fastapi.testclient import TestClient  # noqa: E402

from simcase import Document, run  # noqa: E402
from simcase.studio import joule_regions_api as joule  # noqa: E402
from simcase.studio import server  # noqa: E402
from simcase.studio import thermal_api as thermal  # noqa: E402
from simcase.studio import thermal_regions_api as regions  # noqa: E402

FIXED = "Studio failed unexpectedly; the details are in the server log"
MARKER = "SECRET-PATH-/srv/private/joule.key"
RIGHT_HALF = {"name": "b", "type": "rect", "x": 1, "y": 0, "w": 1, "h": 1, "material": "B"}
SERIES = {"prescribed_electric_potential": {"left": "0.2 V", "right": "0 V"},
          "prescribed_temperature": {"left": "300 K", "right": "320 K"},
          "initial_temperature": "300 K", "iteration": {"temperature_tolerance": "1e-9 K"}}


def linear_resistivity(sigma, alpha):
    return {"model": "linear_resistivity", "reference_conductivity": f"{sigma!r} S/m",
            "reference_temperature": "300 K", "resistivity_temperature_coefficient": f"{alpha!r} 1/K",
            "valid": {"temperature": ["250 K", "600 K"]}}


MODELS = {"A": {"electrical_conductivity": linear_resistivity(2.0e3, 4e-3), "thermal_conductivity": "1.5 W/(m K)"},
          "B": {"electrical_conductivity": linear_resistivity(0.5e3, -3e-3), "thermal_conductivity": "0.25 W/(m K)"}}
CONSTANTS = {"A": {"electrical_conductivity": "2000 S/m", "thermal_conductivity": "1.5 W/(m K)"},
             "B": {"electrical_conductivity": "500 S/m", "thermal_conductivity": "0.25 W/(m K)"}}


def strip(kind="joule.temperature2d", *, size=0.125, features=None, materials=None, physics=None):
    """The T1 strip of #239: a version 1 document in mm, A on the left half, B on the right."""
    if physics is None:
        physics = copy.deepcopy(SERIES)
        if kind == "joule.steady2d":
            del physics["initial_temperature"], physics["iteration"]
    comp = {"dimension": "2d", "length_unit": "mm", "depth": None,
            "domain": {"xmin": 0, "xmax": 2, "ymin": 0, "ymax": 1},
            "background": {"material": "A"}, "features": copy.deepcopy(features or [RIGHT_HALF])}
    return {"openphysics": "0.3", "name": "Studio Joule strip",
            "geometry": {"version": 1, "components": {"xs": comp}},
            "materials": copy.deepcopy(materials or (MODELS if kind == "joule.temperature2d" else CONSTANTS)),
            "physics": {"j": {"type": kind, **physics}},
            "mesh": {"element_size": f"{size!r} mm"}, "study": {"type": "single"},
            "results": {"save_fields": True, "plots": False}}


def envelope(doc):
    return {"doc": doc, "client_revision": 3, "request_seq": 5}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server, "_thermal_jobs", thermal.ThermalJobs())
    monkeypatch.setattr(server, "_region_limits", regions.RegionLimits())
    monkeypatch.setattr(server, "_start_thermal_thread", lambda target, args: target(*args))
    with TestClient(server.app) as value:
        yield value


def assert_idle(jobs):
    assert jobs._active == jobs._reserved_bytes == jobs._pending == 0
    assert jobs.ingress._token is None


def finished(client, doc):
    response = client.post("/api/joule/run", json=envelope(doc))
    assert response.status_code == 200, response.text
    identity = response.json()
    status = client.get("/api/jobs/"+identity["job"]).json()
    assert status["status"] in ("done", "error"), status
    assert_idle(server._thermal_jobs)
    return identity, status


def job_error(client, doc, code):
    identity, status = finished(client, doc)
    assert status["status"] == "error" and status["has_result"] is False, status
    assert status["error"]["code"] == code, status
    assert client.get("/api/jobs/"+identity["job"]+"/result").status_code == 409
    return status["error"]["message"]


# ---- J-S1: the Studio result is simcase.run's ------------------------------------------------

@pytest.mark.parametrize("kind", joule.KINDS)
def test_js1_payload_equals_simcase_run_bit_for_bit(client, kind):
    doc = strip(kind)
    identity, status = finished(client, doc)
    assert status["status"] == "done", status
    assert identity["kind"] == kind
    payload = client.get("/api/jobs/"+identity["job"]+"/result").json()
    assert payload["payload_format"] == joule.PAYLOAD
    assert (payload["result_format"], payload["field_layout"]) == joule.PAIRS[kind]
    assert payload["length_unit"] == "mm" and payload["display_length_in_m"] == 1e-3
    reference = run(Document.from_dict(doc), verbose=False)
    fields = reference.fields
    assert set(payload["arrays"]) == set(fields)
    for key, value in fields.items():
        sent = np.array(payload["arrays"][key], dtype=value.dtype)
        assert sent.shape == value.shape and sent.tobytes() == value.tobytes(), key
    summary, expected = payload["summary"], thermal.json_value(reference.summary())
    for s in (summary, expected):
        s.pop("timing")
    assert summary == expected
    if kind == "joule.temperature2d":
        assert len(summary["iterations"]) > 1
        assert "evaluation_temperature" in payload["arrays"]
    else:
        assert summary["iterations"] == []


#: the workspace Joule application's default document (workspace-joule.mjs jouleDocument(DEFAULT_JOULE);
#: studio_workspace_joule.cjs asserts the builder writes exactly this): the strip above with the
#: documented iteration defaults written out
WORKSPACE_DEFAULT = {
    "openphysics": "0.3", "name": "Workspace Joule heating",
    "geometry": {"version": 1, "components": {"xs": {
        "dimension": "2d", "length_unit": "mm", "depth": None, "domain": {"xmin": 0, "xmax": 2, "ymin": 0, "ymax": 1},
        "background": {"material": "A"}, "features": [{"name": "b", "type": "rect", "x": 1, "y": 0, "w": 1, "h": 1,
                                                       "material": "B"}]}}},
    "materials": {m: {"electrical_conductivity": {
        "model": "linear_resistivity", "reference_conductivity": sigma, "reference_temperature": "300 K",
        "resistivity_temperature_coefficient": alpha, "valid": {"temperature": ["250 K", "600 K"]}},
        "thermal_conductivity": k} for m, sigma, alpha, k in (("A", "2000 S/m", "0.004 1/K", "1.5 W/(m K)"),
                                                              ("B", "500 S/m", "-0.003 1/K", "0.25 W/(m K)"))},
    "physics": {"j": {"type": "joule.temperature2d", "prescribed_electric_potential": {"left": "0.2 V", "right": "0 V"},
                      "prescribed_temperature": {"left": "300 K", "right": "320 K"}, "initial_temperature": "300 K",
                      "iteration": {"relaxation_factor": 0.5, "temperature_tolerance": "1e-9 K",
                                    "relative_tolerance": 1e-10, "iteration_limit": 100}}},
    "mesh": {"element_size": "0.125 mm"}, "study": {"type": "single"},
    "results": {"save_fields": True, "plots": False}}


def test_js1_the_workspace_default_document_runs_as_simcase_runs_it(client):
    identity, status = finished(client, copy.deepcopy(WORKSPACE_DEFAULT))
    assert status["status"] == "done", status
    payload = client.get("/api/jobs/"+identity["job"]+"/result").json()
    fields = run(Document.from_dict(WORKSPACE_DEFAULT), verbose=False).fields
    for key, value in fields.items():
        assert np.array_equal(np.array(payload["arrays"][key], dtype=value.dtype), value), key
    # the defaults written out change nothing: the strip without them gives the same temperatures
    strip_fields = run(Document.from_dict(strip()), verbose=False).fields
    assert fields["temperature"].tobytes() == strip_fields["temperature"].tobytes()


def test_js1_validation_returns_the_document_and_its_summary(client):
    reply = client.post("/api/joule/validate", json=envelope(strip()))
    assert reply.status_code == 200
    body = reply.json()
    assert body["ok"] is True and body["doc"] == strip() and "linear_resistivity" in body["summary"]
    assert (body["client_revision"], body["request_seq"]) == (3, 5)


def test_js1_capabilities_name_the_routes_and_the_region_limits(client):
    caps = client.get("/api/capabilities").json()
    for kind in joule.KINDS:
        block = caps[kind]
        assert block["validate"] == "/api/joule/validate" and block["run"] == "/api/joule/run"
        assert block["run_enabled"] is True and block["geometry"] == "regions"
        assert block["result_formats"] == [joule.PAIRS[kind][0]]
        limits = dict(block["limits"])
        assert limits.pop("max_iterations", None) == (joule.MAX_ITERATIONS if kind == joule.TEMPERATURE else None)
        assert limits == caps["thermal.steady2d"]["regions"]["limits"]


# ---- J-S2: refusals for users and unexpected failures ------------------------------------------

def test_js2_initial_temperature_outside_the_model_range_is_refused_by_name(client):
    doc = strip()
    doc["physics"]["j"]["initial_temperature"] = "700 K"
    validated = client.post("/api/joule/validate", json=envelope(doc))
    assert validated.status_code == 200
    error = validated.json()["error"]
    assert error["code"] == "invalid_document" and "E-OUTSIDE-VALID" in error["message"]
    assert "initial_temperature" in error["message"]
    ran = client.post("/api/joule/run", json=envelope(doc))
    assert ran.status_code == 400 and ran.json()["error"]["message"] == error["message"]
    assert_idle(server._thermal_jobs)


def test_js2_a_document_without_a_potential_is_refused_with_its_text(client):
    doc = strip()
    del doc["physics"]["j"]["prescribed_electric_potential"]
    error = client.post("/api/joule/validate", json=envelope(doc)).json()["error"]
    assert error["code"] == "invalid_document" and "prescribed_electric_potential" in error["message"]
    assert error["message"] != FIXED


def test_js2_a_floating_conductor_part_is_named_by_its_region(client):
    ring = {"name": "ring", "type": "circle", "cx": 1.0, "cy": 0.5, "r": 0.4, "material": None}
    island = {"name": "island", "type": "circle", "cx": 1.0, "cy": 0.5, "r": 0.2, "material": "B"}
    message = job_error(client, strip(features=[ring, island], size=0.1), "invalid_document")
    assert "conductor part with regions ['island'] touches no fixed potential" in message


def test_js2_picard_non_convergence_reports_the_solver_reason(client):
    doc = strip()
    doc["physics"]["j"]["iteration"]["iteration_limit"] = 1
    message = job_error(client, doc, "not_converged")
    assert message == "the Picard iteration did not converge after 1 iterations: maximum iterations exceeded"


def test_js2_an_unexpected_failure_gets_the_fixed_message_and_a_logged_traceback(client, monkeypatch, caplog):
    class HiddenFailure(KeyError):
        pass

    def fail(*args, **kwargs):
        raise HiddenFailure(MARKER)
    monkeypatch.setattr(server, "run", fail)
    with caplog.at_level(logging.WARNING, logger="simcase.studio"):
        identity, status = finished(client, strip())
    assert status["error"] == {"code": "solver_failed", "message": FIXED}
    assert MARKER not in str(status) and "HiddenFailure" not in str(status)
    logged = [r for r in caplog.records if r.exc_info and r.exc_info[0] is HiddenFailure]
    assert logged and MARKER in caplog.text


def test_js2_a_wrapped_unexpected_failure_inside_the_iteration_is_not_shown(client, monkeypatch, caplog):
    from galerkin import temperature_joule_heating as tj

    class HiddenFailure(RuntimeError):
        pass

    def fail(*args, **kwargs):
        try:
            raise HiddenFailure(MARKER)
        except HiddenFailure as exc:
            raise tj.JouleConvergenceError(str(exc), (), np.zeros(1)) from exc
    monkeypatch.setattr(tj, "solve_temperature_joule_heat", fail)
    with caplog.at_level(logging.WARNING, logger="simcase.studio"):
        _, status = finished(client, strip())
    assert status["error"]["code"] == "not_converged"
    assert MARKER not in status["error"]["message"] and FIXED in status["error"]["message"]
    assert MARKER in caplog.text


def test_js2_an_iterate_leaving_a_model_range_is_reported_with_the_solver_text(client):
    doc = strip()
    doc["physics"]["j"]["prescribed_electric_potential"]["left"] = "2 V"
    message = job_error(client, doc, "not_converged")
    assert "K outside [250.0, 600.0] K" in message and FIXED not in message


def test_js2_another_plain_value_error_inside_the_iteration_is_not_shown(client, monkeypatch, caplog):
    from galerkin import temperature_joule_heating as tj

    def fail(*args, **kwargs):
        try:
            raise ValueError(MARKER)
        except ValueError as exc:
            raise tj.JouleConvergenceError(str(exc), (), np.zeros(1)) from exc
    monkeypatch.setattr(tj, "solve_temperature_joule_heat", fail)
    with caplog.at_level(logging.WARNING, logger="simcase.studio"):
        _, status = finished(client, strip())
    assert MARKER not in status["error"]["message"] and FIXED in status["error"]["message"]
    assert MARKER in caplog.text


def test_js2_rectangle_and_other_physics_are_refused_by_name(client):
    rectangle = {"openphysics": "0.3", "name": "rect", "geometry": {"length_unit": "mm", "depth": None,
                 "domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}}, "materials": {},
                 "physics": {"j": {"type": "joule.steady2d"}}, "mesh": {"subdivision_count": [2, 2]},
                 "study": {"type": "single"}, "results": {"save_fields": True, "plots": False}}
    for action in ("validate", "run"):
        error = client.post("/api/joule/"+action, json=envelope(rectangle)).json()["error"]
        assert error == {"code": "unsupported_geometry", "message": joule.RECTANGLE, "path": "geometry"}
        heat = strip()
        heat["physics"]["j"]["type"] = "thermal.steady2d"
        error = client.post("/api/joule/"+action, json=envelope(heat)).json()["error"]
        assert error["code"] == "unsupported_physics" and error["message"] == joule.ENTRY
    assert_idle(server._thermal_jobs)


# ---- J-S3: limits ------------------------------------------------------------------------------

def test_js3_too_many_shapes_are_refused_at_submit(client, monkeypatch):
    monkeypatch.setattr(server, "_region_limits", regions.RegionLimits(max_shapes=1))
    second = dict(RIGHT_HALF, name="c", x=0.25, w=0.25)
    reply = client.post("/api/joule/run", json=envelope(strip(features=[RIGHT_HALF, second])))
    assert reply.status_code == 413 and reply.json()["error"]["code"] == "geometry_limit_exceeded"
    assert "max_shapes=1" in reply.json()["error"]["message"]
    assert_idle(server._thermal_jobs)


def test_js3_a_mesh_over_the_node_cap_fails_before_the_solve(client, monkeypatch):
    import galerkin.temperature_joule_heating as tj
    doc = strip()
    nodes = len(run(Document.from_dict(doc), verbose=False).fields["node_coordinates"])
    monkeypatch.setattr(server, "_thermal_jobs", thermal.ThermalJobs(thermal.ThermalLimits(max_nodes=nodes-1)))

    def forbidden(*args, **kwargs):
        raise AssertionError("the solve must not start")
    monkeypatch.setattr(tj, "solve_temperature_joule_heat", forbidden)
    message = job_error(client, doc, "mesh_limit_exceeded")
    assert f"max_nodes={nodes-1}" in message


HEAT = {"openphysics": "0.3", "name": "heat control",
        "geometry": {"length_unit": "m", "depth": None, "domain": {"xmin": 0., "xmax": 1., "ymin": 0., "ymax": 1.}},
        "materials": {}, "physics": {"heat1": {
            "type": "thermal.steady2d", "thermal_conductivity": "2 W/(m K)", "heat_source_density": "0 W/m^3",
            "prescribed_temperature": {"left": "300 K", "right": "293 K"}}},
        "mesh": {"subdivision_count": [2, 2]}, "study": {"type": "single"},
        "results": {"save_fields": True, "plots": False}}


@pytest.mark.parametrize("first,second", [("joule", "heat"), ("heat", "joule")])
def test_js3_heat_and_joule_share_the_one_active_job(client, monkeypatch, first, second):
    held = []
    monkeypatch.setattr(server, "_start_thermal_thread", lambda target, args: held.append((target, args)))
    routes = {"joule": ("/api/joule/run", strip()), "heat": ("/api/thermal/run", HEAT)}
    accepted = client.post(routes[first][0], json=envelope(routes[first][1]))
    assert accepted.status_code == 200, accepted.text
    refused = client.post(routes[second][0], json=envelope(routes[second][1]))
    assert refused.status_code == 429 and refused.json()["error"]["code"] == "capacity_exceeded"
    target, args = held.pop()
    target(*args)
    assert client.get("/api/jobs/"+accepted.json()["job"]).json()["status"] == "done"
    assert_idle(server._thermal_jobs)


def test_js3_iteration_limit_over_studio_cap_is_refused_before_a_job(client):
    doc = strip()
    doc["physics"]["j"]["iteration"]["iteration_limit"] = joule.MAX_ITERATIONS+1
    for action in ("validate", "run"):
        reply = client.post("/api/joule/"+action, json=envelope(doc))
        assert reply.status_code == 413, reply.text
        error = reply.json()["error"]
        assert error["code"] == "iteration_limit_exceeded" and f"max_iterations={joule.MAX_ITERATIONS}" in error["message"]
        assert error["path"] == "physics.j.iteration.iteration_limit"
    doc["physics"]["j"]["iteration"]["iteration_limit"] = joule.MAX_ITERATIONS
    assert client.post("/api/joule/validate", json=envelope(doc)).json()["ok"] is True
    assert_idle(server._thermal_jobs)


def test_js3_a_long_iteration_fits_the_result(client):
    # relaxation 0.2 needs more Picard steps than the 64 KiB metadata budget would hold records for
    doc = strip(size=0.25)
    doc["physics"]["j"]["iteration"]["relaxation_factor"] = 0.2
    identity, status = finished(client, doc)
    assert status["status"] == "done", status
    payload = client.get("/api/jobs/"+identity["job"]+"/result").json()
    assert len(payload["summary"]["iterations"]) > 60
    assert len(payload["summary"]["iterations"]) == len(run(Document.from_dict(doc), verbose=False).summary()["iterations"])


# ---- J-S4: result checks -----------------------------------------------------------------------

def tampered(change):
    original = joule.capture

    def capture(result, identity, limits, rlimits, spec):
        changed = copy.copy(result)
        change(changed)
        return original(changed, identity, limits, rlimits, spec)
    return capture


def shape(result):
    result._arrays = dict(result._arrays, temperature=result._arrays["temperature"][:-1])


def names(result):
    result._metadata = copy.deepcopy(result._metadata)
    result._metadata["region_names"] = ["background", "other"]


def pair(result):
    result._metadata = copy.deepcopy(result._metadata)
    result._metadata["field_layout"] = "electric-joule2d-p1-node-cell-regions-v2"


@pytest.mark.parametrize("change,expected", [
    (shape, "temperature: wrong metadata shape"), (names, "summary regions disagree with the names"),
    (pair, "unsupported public Joule region result/layout pair")])
def test_js4_a_result_that_disagrees_is_refused(client, monkeypatch, change, expected):
    monkeypatch.setattr(server.joule, "capture", tampered(change))
    assert job_error(client, strip(), "invalid_result") == expected
