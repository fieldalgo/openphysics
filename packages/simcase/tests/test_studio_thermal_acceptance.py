"""Independent HTTP physics/data acceptance for the additive steady Studio bridge.

Prepared contract: exact server binding and execution remain separate evidence.
"""
import ast
import copy
import inspect
import json
from pathlib import Path
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

import simcase
from simcase import Document, ThermalRunResult, examples, run
from simcase.studio import server

from studio_thermal_independent_fixtures import (
    FIELDS, LEGACY, audit_payload, captured_arrays, close, envelope,
    malformed_wires, model, slab, synthetic_wire)


@pytest.fixture
def client():
    with TestClient(server.app) as value:
        yield value


def submit(client, data, sequence=11):
    response=client.post("/api/thermal/run",json=envelope(data,sequence=sequence))
    assert response.status_code in (200,202),response.text
    accepted=response.json()
    assert accepted["client_revision"]==7 and accepted["request_seq"]==sequence
    assert accepted["kind"]=="thermal.steady2d"
    assert isinstance(accepted["job"],str) and accepted["job"]
    assert isinstance(accepted["result_id"],str) and accepted["result_id"]
    return accepted


def terminal(client, accepted):
    # Poll real asynchronous public state; no worker/solver replacement.
    end=time.monotonic()+60.
    while time.monotonic()<end:
        response=client.get("/api/jobs/"+accepted["job"])
        assert response.status_code==200,response.text
        state=response.json()
        for key in ("kind","job","result_id","client_revision","request_seq"):
            assert state[key]==accepted[key]
        if state["status"] in ("done","error"):
            return state
        time.sleep(.01)
    raise AssertionError("thermal job did not reach terminal state within60s")


def finished_payload(client,data,sequence=11):
    accepted=submit(client,data,sequence)
    state=terminal(client,accepted)
    assert state["status"]=="done",state
    assert state["has_result"] is True
    response=client.get("/api/jobs/"+accepted["job"]+"/result")
    assert response.status_code==200,response.text
    payload=response.json()
    for key in ("job","result_id","client_revision","request_seq"):
        assert payload[key]==accepted[key]
    return payload


def test_studio_thermal_capabilities_and_original_generic_refusal(client):
    response=client.get("/api/capabilities")
    assert response.status_code==200,response.text
    cap=response.json()
    assert cap["capability_format"]=="studio-capabilities-v1"
    heat=cap["thermal.steady2d"]
    assert heat["validate"]=="/api/thermal/validate"
    assert heat["run"]=="/api/thermal/run"
    assert heat["run_enabled"] is True
    assert heat["mesh_preview"] is False and heat["mesh_from_result"] is True
    assert heat["time_navigation"] is False
    assert cap["thermal.transient2d"]["supported"] is False
    data=model()
    response=client.post("/api/thermal/validate",json=envelope(data))
    assert response.status_code==200 and response.json()["ok"] is True,response.text
    legacy=model()
    legacy["physics"]["heat1"].pop("outward_flux_w_m2")
    legacy["physics"]["heat1"].pop("convection")
    response=client.post("/api/validate",json={"doc":legacy})
    assert response.status_code==200 and response.json()["ok"] is False
    for route in ("/api/mesh","/api/run"):
        response=client.post(route,json={"doc":legacy})
        assert response.status_code==400,response.text


@pytest.mark.parametrize("unit",("m","mm","um"))
def test_studio_thermal_linear_additive_units_and_signs(client,unit):
    data=model(unit=unit)
    payload=finished_payload(client,data)
    a=audit_payload(payload,data,"linear")
    assert len(a)==13
    # Expected fields come from analytic14W/m and original element integrals,
    # never from payload summary totals.
    close(np.array(a["prescribed_outward_load_w_per_m"].sum()),np.array(2.),14.,"G")
    close(np.array(a["convective_outward_w_per_m"].sum()),np.array(12.),14.,"C")
    close(np.array(a["reaction_w_per_m"].sum()),np.array(14.),14.,"inward R")


@pytest.mark.parametrize("case",("robin","zero_h"))
def test_studio_thermal_robin_empty_dirichlet(client,case):
    data=model(case)
    payload=finished_payload(client,data)
    a=audit_payload(payload,data,case)
    assert a["dirichlet_node_ids"].shape==(0,)
    assert a["dirichlet_temperature_k"].shape==(0,)


def test_studio_thermal_quadratic_original_spatial_gates(client):
    primary=[];quad=[]
    for i,n in enumerate((8,16,32,64)):
        data=model("quadratic",n)
        payload=finished_payload(client,data,sequence=100+i)
        a=audit_payload(payload,data,"quadratic")
        from steady_boundary_independent_oracle import Elements
        L,H,k,Q,aa,b,*_=slab("quadratic")
        e=Elements(a["nodes_m"],a["triangles"],k,Q)
        primary.append(e.errors(a["temperature_k"],L,aa,b,Q,.1,8))
        quad.append(e.errors(a["temperature_k"],L,aa,b,Q,.1,10))
        close(np.array(a["load_w_per_m"].sum()),np.array(60.),60.,"60W/m")
    primary,quad=np.asarray(primary),np.asarray(quad)
    orders=np.log2(primary[:-1]/primary[1:])
    assert np.all(orders[-2:,0]>=1.8),orders
    assert np.all(orders[-2:,1]>=.9),orders
    assert np.max(abs(primary-quad)/primary)<.01
    exact_flux_norm=np.sqrt(H*(Q**2*L**3/3-Q*k*b*L**2+(k*b)**2*L))
    assert primary[-1,1]/exact_flux_norm<=.02
    print(json.dumps({"gate":"studio_thermal_independent_PDE","errors":primary.tolist(),
                      "quadrature10":quad.tolist(),"orders":orders.tolist(),
                      "finest_relative_flux":float(primary[-1,1]/exact_flux_norm)}))


def test_studio_thermal_legacy_absence_and_v2_empty_presence(client):
    data=model()
    data["physics"]["heat1"].pop("outward_flux_w_m2")
    data["physics"]["heat1"].pop("convection")
    old=captured_arrays(finished_payload(client,data,301),version=1)
    assert set(old)==set(LEGACY)
    for i,key in enumerate(("outward_flux_w_m2","convection")):
        newer=copy.deepcopy(data);newer["physics"]["heat1"][key]={}
        new=captured_arrays(finished_payload(client,newer,302+i))
        assert len(new)==13
        for field in LEGACY:
            close(new[field],old[field],max(1.,np.max(abs(old[field]),initial=0.)),field)


def test_studio_thermal_dedicated_route_rejects_other_physics(client):
    # Real shipped optical document, without running its optical solver.
    optical=next(copy.deepcopy(d) for d in examples.EXAMPLES.values()
                 if all(p.get("type")=="em.modes2d" for p in d["physics"].values()))
    transient=model();transient["physics"]["heat1"]["type"]="thermal.transient2d"
    for data in (optical,transient):
        response=client.post("/api/thermal/run",json=envelope(data))
        assert response.status_code==400,response.text
        assert "job" not in response.json()


def test_studio_thermal_strict_envelope_preserves_rejection(client):
    for body in ('{"doc":{},"doc":{},"client_revision":1,"request_seq":1}',
                 '{"doc":{},"client_revision":true,"request_seq":1}',
                 '{"doc":{},"client_revision":1,"request_seq":NaN}',
                 '{"doc":{},"client_revision":1,"request_seq":1,"extra":1}'):
        response=client.post("/api/thermal/run",content=body,
                             headers={"content-type":"application/json"})
        assert response.status_code==400,response.text
        assert "job" not in response.json()


def test_studio_thermal_independent_wire_negative_controls():
    # Parser/control evidence only; not an actual solver/browser pass.
    assert captured_arrays(synthetic_wire())["heat_flux_w_m2"].shape==(4,2)
    for kind,payload in malformed_wires():
        with pytest.raises((AssertionError,KeyError,ValueError),match=None):
            captured_arrays(payload)


class PublicResultProbe(ThermalRunResult):
    """Deliberate malformed producer actor using only captured public properties."""
    def __init__(self,original,fault):
        names={"nodes_m":"mesh_nodes_m","triangles":"mesh_triangles"}
        self.captured={names.get(k,k):np.array(getattr(original,names.get(k,k)),copy=True)
                       for k in FIELDS}
        self.captured.update(result_format=original.result_format,field_layout=original.field_layout)
        self.doc=original.doc.copy();self.doc.validate()
        self.log=list(original.log);self.timings=dict(original.timings)
        self.metadata=copy.deepcopy(original.summary())
        if fault=="layout":
            self.captured["field_layout"]="wrong-layout"
            self.metadata["field_layout"]="wrong-layout"
        elif fault=="unit":self.metadata["field_units"]["load_w_per_m"]="W"
        elif fault=="shape":self.captured["heat_flux_w_m2"]=np.zeros((1,2))
        elif fault=="nonfinite":self.captured["temperature_k"][0]=np.nan
        elif fault=="bool":self.captured["temperature_k"]=np.ones(len(original.temperature_k),dtype=bool)
        elif fault=="index":self.captured["mesh_triangles"][0,0]=len(original.mesh_nodes_m)
        else:raise AssertionError(fault)

    def __getattribute__(self,name):
        if name not in ("captured","__dict__"):
            captured=object.__getattribute__(self,"__dict__").get("captured",{})
            if name in captured:return captured[name]
        return object.__getattribute__(self,name)

    def summary(self):
        return copy.deepcopy(self.metadata)


@pytest.mark.parametrize("fault",("layout","unit","shape","nonfinite","bool","index"))
def test_studio_thermal_malformed_public_results_never_publish(client,monkeypatch,fault):
    # Actual public physics first; the actor only corrupts transport-bound values.
    real=run(Document.from_dict(model()),False)
    malformed=PublicResultProbe(real,fault)
    monkeypatch.setattr(server,"run",lambda *a,**k:malformed)
    accepted=submit(client,model(),sequence=401)
    state=terminal(client,accepted)
    assert state["status"]=="error",state
    assert state["has_result"] is False
    response=client.get("/api/jobs/"+accepted["job"]+"/result")
    assert response.status_code==409,response.text


def test_studio_thermal_uses_exported_physics_api_only():
    exports=set(simcase.__all__)
    root=Path(inspect.getfile(server)).parent
    for path in root.glob("*.py"):
        tree=ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom) and node.module:
                if node.module=="simcase":
                    assert all(a.name in exports for a in node.names),path
                elif node.module.startswith("simcase.") and not node.module.startswith("simcase.studio"):
                    raise AssertionError("nonpublic simcase import: "+str(path))
                elif node.module.startswith(("galerkin","refsol")):
                    raise AssertionError("direct numerical implementation import: "+str(path))
            if isinstance(node,ast.Import):
                assert not any(a.name.startswith(("galerkin","refsol")) for a in node.names),path
            if isinstance(node,ast.Attribute):
                assert node.attr!="_raw_arrays",path
