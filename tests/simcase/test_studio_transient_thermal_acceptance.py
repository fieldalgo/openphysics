# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Independent public HTTP acceptance for saved transient thermal Studio data."""
import copy
import json
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from simcase import Document, TransientThermalRunResult, run
from simcase.studio import server
from studio_transient_independent_fixtures import (
    DYNAMIC, FIELD_UNITS, FRAME, HISTORY, IDENTITY, KIND, STEP_FIELDS,
    audit, envelope, expected_arrays, frame_array, identity, manifest_arrays, metadata, model, numeric,
    require_close)


@pytest.fixture
def client():
    with TestClient(server.app) as value:
        yield value


def submit(client,data,sequence=11):
    response = client.post("/api/thermal/transient/run",json=envelope(data,sequence))
    assert response.status_code in (200,202), response.text
    accepted = response.json()
    assert accepted["kind"] == KIND
    assert type(accepted["client_revision"]) is int and accepted["client_revision"] == 7
    assert type(accepted["request_seq"]) is int and accepted["request_seq"] == sequence
    for key in ("job","result_id"):
        assert isinstance(accepted[key],str) and accepted[key]
    return accepted


def terminal(client,accepted):
    deadline = time.monotonic()+60.
    while time.monotonic() < deadline:
        response = client.get("/api/jobs/"+accepted["job"])
        assert response.status_code == 200,response.text
        state = response.json()
        for key in IDENTITY:
            assert state[key] == accepted[key],key
        if state["status"] in ("done","error"):
            return state
        time.sleep(.01)
    raise AssertionError("transient job did not finish within60s")


def finished(client,data,sequence=11):
    accepted = submit(client,data,sequence)
    state = terminal(client,accepted)
    assert state["status"] == "done" and state["has_result"] is True,state
    response = client.get("/api/jobs/"+accepted["job"]+"/result")
    assert response.status_code == 200,response.text
    manifest = response.json()
    arrays = manifest_arrays(manifest,accepted,data)
    return accepted,manifest,arrays


def frame(client,accepted,field,index,sequence):
    return client.get("/api/jobs/"+accepted["job"]+"/frame",params={
        "result_id":accepted["result_id"],"field":field,
        "time_index":index,"frame_seq":sequence})


def history(client,accepted,field,start,stop,sequence):
    return client.get("/api/jobs/"+accepted["job"]+"/history",params={
        "result_id":accepted["result_id"],"field":field,
        "start":start,"stop":stop,"frame_seq":sequence})


def collect(client,accepted,manifest,a,data):
    shapes = metadata(data,a)
    nt = len(a["time_s"])
    for field in sorted(DYNAMIC):
        first = 1 if field in STEP_FIELDS else 0
        values = []
        for index in range(first,nt):
            sequence = 100+index
            response = frame(client,accepted,field,index,sequence)
            assert response.status_code == 200,response.text
            value = frame_array(response.json(),accepted,data,field,index,sequence,shapes[field][1:])
            values.append(value)
            # Complete query identity, including frame_seq, determines stable bytes.
            again = frame(client,accepted,field,index,sequence)
            assert again.status_code == 200 and again.content == response.content
        a[field] = np.asarray(values)
        response = history(client,accepted,field,first,nt,301)
        assert response.status_code == 200,response.text
        payload = response.json()
        identity(payload,accepted)
        assert payload["payload_format"] == HISTORY
        assert type(payload["frame_seq"]) is int and payload["frame_seq"] == 301
        assert payload["field"] == field and set(payload["arrays"]) == {field}
        assert type(payload["start"]) is int and payload["start"] == first
        assert type(payload["stop"]) is int and payload["stop"] == nt
        assert payload["time_indices"] == list(range(first,nt))
        assert all(type(v) is int for v in payload["time_indices"])
        assert payload["time_s"] == data["study"]["time_s"][first:nt]
        assert payload["unit"] == FIELD_UNITS[field]
        assert payload["location"] == manifest["fields"][field]["location"]
        assert payload["display_length_in_m"] == manifest["display_length_in_m"]
        shape = [nt-first]+shapes[field][1:]
        assert payload["shape"] == shape
        assert all(type(v) is int for v in payload["shape"])
        assert type(payload["display_length_in_m"]) in (int,float)
        page = numeric(payload["arrays"][field],shape)
        assert np.array_equal(page,a[field]),field
        if field in STEP_FIELDS:
            assert payload["interval_start_s"] == data["study"]["time_s"][first-1:nt-1]
            assert payload["interval_end_s"] == data["study"]["time_s"][first:nt]
    assert set(a) == set(FIELD_UNITS)
    return a


def public_arrays(data):
    # A second actual public solve is a consistency check, never the analytic oracle.
    result = run(Document.from_dict(copy.deepcopy(data)),False)
    return {name:np.array(getattr(result,name),copy=True) for name in FIELD_UNITS}


@pytest.mark.parametrize("unit",("m","mm","um"))
@pytest.mark.parametrize("case",("uniform_relative","uniform_absolute","cooling_signed",
                                  "sampled_ramp","all_fixed_support","affine"))
def test_studio_transient_independent_all13_physical_frames_and_history(client,unit,case):
    data = model(case,unit)
    accepted,manifest,a = finished(client,data)
    collect(client,accepted,manifest,a,data)
    audit(a,case,data,manifest["summary"])
    expected = expected_arrays(a,case,data)
    print(json.dumps({"gate":"studio_transient_independent_exact","case":case,"unit":unit,
                      "time_s":a["time_s"].tolist(),
                      "max_absolute_error":{key:float(np.max(abs(a[key]-value),initial=0.))
                                            for key,value in expected.items()},
                      "heat_content_j_per_m":a["heat_content_j_per_m"].tolist(),
                      "quadratic_functional_jk_per_m":a["quadratic_functional_jk_per_m"].tolist()},
                     allow_nan=False))
    original = public_arrays(data)
    for field in FIELD_UNITS:
        # This is secondary equality; independent P1/analytic gates above are mandatory.
        assert np.array_equal(a[field],original[field]),field
    for field in STEP_FIELDS:
        response = frame(client,accepted,field,0,901)
        assert response.status_code == 422,response.text
        assert response.json()["error"]["code"] == "unavailable_initial_rate"


def test_studio_transient_independent_nt2_scalar_frames(client):
    data = model("uniform_absolute",nt2=True)
    accepted,manifest,a = finished(client,data,sequence=20)
    collect(client,accepted,manifest,a,data)
    audit(a,"uniform_absolute",data,manifest["summary"])
    assert a["storage_rate_w_per_m"].shape == (1,len(a["nodes_m"]))
    for field in ("heat_content_j_per_m","quadratic_functional_jk_per_m"):
        response = frame(client,accepted,field,0,902)
        assert response.status_code == 200,response.text
        payload = response.json()
        assert payload["shape"] == [] and type(payload["arrays"][field]) in (int,float)


def test_studio_transient_independent_capability_and_input_refusal(client):
    response = client.get("/api/capabilities")
    assert response.status_code == 200,response.text
    cap = response.json()[KIND]
    assert cap["supported"] is True and cap["run_enabled"] is True
    assert cap["validate"] == "/api/thermal/transient/validate"
    assert cap["run"] == "/api/thermal/transient/run"
    valid = model()
    response = client.post(cap["validate"],json=envelope(valid))
    assert response.status_code == 200 and response.json()["ok"] is True
    bad = []
    for times in ([2],[2,2],[3,2],[2,True]):
        d = copy.deepcopy(valid);d["study"]["time_s"] = times;bad.append(d)
    for change,value in (("initial_temperature_k",True),
                         ("dirichlet_temperature_k",{"left":301}),
                         ("volumetric_heat_capacity_j_m3k",0)):
        d = copy.deepcopy(valid);d["physics"]["heat1"][change] = value;bad.append(d)
    for unit,key in (("ms","time"),("C","temperature")):
        d = copy.deepcopy(valid);d["units"][key] = unit;bad.append(d)
    for data in bad:
        response = client.post(cap["validate"],json=envelope(data))
        assert response.status_code == 200 and response.json()["ok"] is False,response.text
        response = client.post(cap["run"],json=envelope(data))
        assert response.status_code == 400 and "job" not in response.json(),response.text
    for raw in ('{"doc":{},"doc":{},"client_revision":7,"request_seq":11}',
                '{"doc":{},"client_revision":true,"request_seq":11}',
                '{"doc":{},"client_revision":7,"request_seq":NaN}'):
        response = client.post(cap["run"],content=raw,headers={"content-type":"application/json"})
        assert response.status_code == 400 and "job" not in response.json(),response.text


def test_studio_transient_independent_query_and_identity_refusal(client):
    accepted,manifest,a = finished(client,model(),sequence=30)
    base = {"result_id":accepted["result_id"],"field":"temperature_k","time_index":1,"frame_seq":1}
    path = "/api/jobs/"+accepted["job"]+"/frame"
    for changed,status in (({"time_index":"true"},400),({"time_index":1.5},400),
                           ({"time_index":-1},422),({"time_index":5},422),
                           ({"field":"missing"},400),({"extra":1},400),
                           ({"result_id":"different-result"},409)):
        query = dict(base,**changed)
        response = client.get(path,params=query)
        assert response.status_code == status,response.text
    missing = dict(base);missing.pop("result_id")
    assert client.get(path,params=missing).status_code == 400
    duplicate = list(base.items())+[("time_index",2)]
    assert client.get(path,params=duplicate).status_code == 400
    for start,stop,status in ((0,0,422),(-1,2,422),(0,6,422)):
        assert history(client,accepted,"heat_content_j_per_m",start,stop,4).status_code == status
    assert history(client,accepted,"storage_rate_w_per_m",0,2,4).status_code == 422


class PublicTransientProbe(TransientThermalRunResult):
    """Actual public result corrupted at the adapter boundary, not a fake solution."""
    def __init__(self,result,fault):
        object.__setattr__(self,"captured",{name:np.array(getattr(result,name),copy=True)
                                           for name in FIELD_UNITS})
        object.__setattr__(self,"doc",result.doc.copy())
        object.__setattr__(self,"log",list(result.log))
        object.__setattr__(self,"timings",dict(result.timings))
        object.__setattr__(self,"metadata",copy.deepcopy(result.summary()))
        if fault == "layout":
            self.metadata["field_layout"] = "wrong-layout"
        elif fault == "unit":
            self.metadata["field_units"]["heat_content_j_per_m"] = "J K/m"
        elif fault == "shape":
            self.captured["heat_flux_w_m2"] = self.captured["heat_flux_w_m2"][1:]
        elif fault == "nonfinite":
            self.captured["temperature_k"][0,0] = np.nan
        elif fault == "bool":
            self.captured["temperature_k"] = np.ones_like(self.captured["temperature_k"],dtype=bool)
        elif fault == "index":
            self.captured["triangles"][0,0] = len(self.captured["nodes_m"])
        elif fault == "time":
            self.captured["time_s"][0] += .001
        elif fault == "rate_axis":
            x = self.captured["storage_rate_w_per_m"]
            self.captured["storage_rate_w_per_m"] = np.concatenate((x[:1],x))
        else:
            raise AssertionError(fault)

    def __getattribute__(self,name):
        if name not in ("captured","__dict__"):
            values = object.__getattribute__(self,"__dict__").get("captured",{})
            if name in values:
                return values[name]
        return object.__getattribute__(self,name)

    def summary(self):
        return copy.deepcopy(self.metadata)


@pytest.mark.parametrize("fault",("layout","unit","shape","nonfinite","bool","index","time","rate_axis"))
def test_studio_transient_independent_malformed_producer_no_publication(client,monkeypatch,fault):
    data = model()
    result = run(Document.from_dict(copy.deepcopy(data)),False)
    malformed = PublicTransientProbe(result,fault)
    monkeypatch.setattr(server,"run",lambda *args,**kwargs:malformed)
    accepted = submit(client,data,sequence=40)
    state = terminal(client,accepted)
    assert state["status"] == "error" and state["has_result"] is False,state
    assert client.get("/api/jobs/"+accepted["job"]+"/result").status_code == 409


def test_studio_transient_independent_real_history_page_boundaries(client):
    data = model("uniform_absolute")
    data["study"]["time_s"] = [2+i/16 for i in range(17)]
    accepted,manifest,a = finished(client,data,sequence=50)
    for field in ("heat_content_j_per_m","quadratic_functional_jk_per_m"):
        for start,stop in ((0,16),(16,17)):
            response = history(client,accepted,field,start,stop,500+start)
            assert response.status_code == 200,response.text
            p = response.json()
            identity(p,accepted)
            assert p["payload_format"] == HISTORY
            assert p["field"] == field and set(p["arrays"]) == {field}
            assert type(p["start"]) is int and p["start"] == start
            assert type(p["stop"]) is int and p["stop"] == stop
            assert type(p["frame_seq"]) is int and p["frame_seq"] == 500+start
            assert p["time_indices"] == list(range(start,stop))
            assert all(type(i) is int for i in p["time_indices"])
            times = np.asarray(data["study"]["time_s"][start:stop])
            assert p["time_s"] == times.tolist()
            assert p["shape"] == [stop-start] and type(p["shape"][0]) is int
            assert p["unit"] == FIELD_UNITS[field] and p["location"] == "domain"
            temperature = 300+2*times
            expected = 8e-6*temperature if field=="heat_content_j_per_m" else 4e-6*temperature**2
            actual = numeric(p["arrays"][field],[stop-start])
            require_close(actual,expected,float(np.max(abs(expected))),field)
    assert history(client,accepted,"heat_content_j_per_m",0,17,700).status_code == 422


@pytest.mark.parametrize("fault",("heat_vs_quadratic","storage_zero","source_sign",
                                  "temperature_origin","flux_sign","support_sign","initial_rate"))
def test_studio_transient_independent_oracle_rejects_wrong_runtime_arrays(fault):
    # Actual public run followed by deliberate corruption: not synthetic PDE success.
    case = "affine" if fault=="flux_sign" else "all_fixed_support" if fault=="support_sign" else "uniform_absolute"
    data = model(case)
    result = run(Document.from_dict(copy.deepcopy(data)),False)
    a = {name:np.array(getattr(result,name),copy=True) for name in FIELD_UNITS}
    summary = result.summary()
    audit(a,case,data,summary)
    if fault=="heat_vs_quadratic":
        a["heat_content_j_per_m"] = a["quadratic_functional_jk_per_m"].copy()
    elif fault=="storage_zero":
        a["storage_rate_w_per_m"] *= 0
    elif fault=="source_sign":
        a["source_load_w_per_m"] *= -1
    elif fault=="temperature_origin":
        a["temperature_k"] -= 4
    elif fault=="flux_sign":
        a["heat_flux_w_m2"] *= -1
    elif fault=="support_sign":
        a["reaction_w_per_m"] *= -1
    else:
        x = a["storage_rate_w_per_m"]
        a["storage_rate_w_per_m"] = np.concatenate((np.zeros_like(x[:1]),x))
    with pytest.raises(AssertionError):
        audit(a,case,data,summary)
