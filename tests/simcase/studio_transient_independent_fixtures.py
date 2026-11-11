# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Independent transient Studio fixtures and strict wire consumer.

Only the existing NumPy element oracle defines mathematical expectations.
"""
import copy
import numpy as np
from simcase import Document
from transient_headless_independent_cases import (
    FIELD_UNITS, FIELD_LOCATIONS, STEP_FIELDS, STATIC_FIELDS, audit_arrays,
    audit_summary, model as headless_model)
from transient_headless_independent_oracle import (
    ALGEBRA_RTOL, COORD_ATOL_M, P1, TIMES_S, UNITS, require_close)

KIND = "thermal.transient2d"
RESULT = "thermal.transient2d-result-v3"
LAYOUT = "thermal2d-transient-p1-node-cell-v2"
MANIFEST = "studio-thermal-transient-v2"
FRAME = "studio-thermal-transient-frame-v2"
HISTORY = "studio-thermal-transient-history-v2"
STATIC = set(STATIC_FIELDS) | {"time"}
DYNAMIC = set(FIELD_UNITS) - STATIC
UI = {"temperature", "heat_flux", "stored_heat_per_depth", "thermal_energy_functional_per_depth"}
IDENTITY = ("kind", "job", "result_id", "client_revision", "request_seq")


def model(case="uniform_relative", unit="m", nt2=False):
    data = headless_model(unit=unit)
    p = data["physics"]["heat1"]
    if case == "uniform_absolute":
        p["initial_temperature"] = "304 K"
    elif case == "cooling_signed":
        p["heat_source_density"] = "-1600 W/m^3"
    elif case in ("sampled_ramp", "all_fixed_support"):
        p["initial_temperature"] = "290 K"
        p["heat_source_density"] = "12 W/m^3" if case == "sampled_ramp" else "2 W/m^3"
        ramp = (290+3*(np.asarray(TIMES_S)-TIMES_S[0])).tolist()
        p["prescribed_temperature"] = {
            side: {"unit": "K", "values": list(ramp)} for side in ("left","right","bottom","top")}
        if case == "all_fixed_support":
            data["mesh"]["subdivision_count"] = [1,1]
    elif case == "affine":
        p["initial_temperature"] = {"type": "affine", "reference_temperature": "290 K",
                                    "temperature_gradient": {"unit": "K/m", "values": [5000., 0.]}}
        p["heat_source_density"] = "0 W/m^3"
        p["prescribed_temperature"] = {"left": "290 K", "right": "300 K"}
    elif case != "uniform_relative":
        raise AssertionError(case)
    if nt2:
        data["study"]["time"]["values"] = list(TIMES_S[:2])
        for value in p["prescribed_temperature"].values():
            if isinstance(value,dict):
                value["values"] = value["values"][:2]
    return data


def times(data):
    """The requested times of a document, in s (the fixtures write them in s)."""
    assert data["study"]["time"]["unit"] == "s"
    return data["study"]["time"]["values"]


def physics_si(data):
    """The SI values of the heat entry, as the public reader resolves them."""
    return Document.from_dict(copy.deepcopy(data)).si["physics"]["heat1"]


def envelope(data, sequence=11):
    return {"doc":copy.deepcopy(data),"client_revision":7,"request_seq":sequence}


def integer(value):
    assert type(value) is int and 0 <= value <= 2**53-1


def identity(payload, accepted):
    for key in IDENTITY:
        assert payload[key] == accepted[key], key
    assert payload["kind"] == KIND
    for key in ("job","result_id"):
        assert isinstance(payload[key],str) and payload[key]
    for key in ("client_revision","request_seq"):
        integer(payload[key])
    assert payload["result_format"] == RESULT
    assert payload["field_layout"] == LAYOUT


def numeric(raw, shape, integer_values=False):
    assert isinstance(shape,list) and all(type(v) is int and v >= 0 for v in shape)
    def walk(value):
        if isinstance(value,list):
            for entry in value:
                walk(entry)
        else:
            assert type(value) in ((int,) if integer_values else (int,float))
            assert np.isfinite(value)
    walk(raw)
    a = np.asarray(raw)
    assert list(a.shape) == shape, (list(a.shape),shape)
    # Empty JSON lists carry no dtype; cast only after checking every actual item.
    return np.asarray(raw,dtype=np.int64 if integer_values else float)


def metadata(data, arrays):
    nt,n,m,d = (len(times(data)),len(arrays["node_coordinates"]),len(arrays["triangles"]),
                len(arrays["prescribed_node_ids"]))
    shapes = {"node_coordinates":[n,2],"triangles":[m,3],"time":[nt],
              "temperature":[nt,n],"heat_flux":[nt,m,2],
              "generated_heat_rate_per_depth":[nt,n],"heat_storage_rate_per_depth":[nt-1,n],
              "reaction_heat_rate_per_depth":[nt-1,n],"residual_heat_rate_per_depth":[nt-1,n],
              "stored_heat_per_depth":[nt],"thermal_energy_functional_per_depth":[nt],
              "prescribed_node_ids":[d],"prescribed_temperature":[nt,d]}
    return shapes


def manifest_arrays(payload, accepted, data):
    identity(payload,accepted)
    assert payload["payload_format"] == MANIFEST
    assert set(payload["arrays"]) == {"node_coordinates","triangles","prescribed_node_ids"}
    scale = payload["display_length_in_m"]
    assert type(scale) in (int,float) and np.isfinite(scale) and scale > 0
    assert payload["length_unit"] == data["geometry"]["length_unit"]
    assert scale == UNITS[data["geometry"]["length_unit"]]
    nt = len(times(data))
    assert type(payload["default_frame_index"]) is int
    assert payload["default_frame_index"] == nt-1
    arrays = {}
    for field in ("node_coordinates","triangles","prescribed_node_ids"):
        shape = payload["fields"][field]["shape"]
        arrays[field] = numeric(payload["arrays"][field],shape,field!="node_coordinates")
    arrays["time"] = numeric(payload["time"],[nt])
    assert np.array_equal(arrays["time"],times(data))
    assert "time" not in payload["arrays"]
    shapes = metadata(data,arrays)
    assert set(payload["fields"]) == set(FIELD_UNITS)
    for field,descriptor in payload["fields"].items():
        assert descriptor["shape"] == shapes[field]
        assert all(type(v) is int for v in descriptor["shape"])
        assert descriptor["unit"] == FIELD_UNITS[field]
        assert descriptor["location"] == FIELD_LOCATIONS[field]
        axis = "static" if field in STATIC_FIELDS else "time[1:]" if field in STEP_FIELDS else "time"
        assert descriptor["axis"] == axis
        assert descriptor["initial_available"] is (field not in STEP_FIELDS)
        assert descriptor["ui_supported"] is (field in UI)
        assert set(descriptor["available_views"]) == (set() if field in STATIC else {"frame","history"})
    summary = payload["summary"]
    assert summary["result_format"] == RESULT and summary["field_layout"] == LAYOUT
    assert summary["physics_type"] == KIND
    # Positive finite-area CCW geometry and complete physical bounds are checked by audit.
    return arrays


def frame_array(payload,accepted,data,field,index,sequence,shape):
    identity(payload,accepted)
    assert payload["payload_format"] == FRAME
    assert type(payload["frame_seq"]) is int and payload["frame_seq"] == sequence
    assert type(payload["time_index"]) is int and payload["time_index"] == index
    assert payload["field"] == field and set(payload["arrays"]) == {field}
    assert payload["time"] == times(data)[index]
    assert payload["unit"] == FIELD_UNITS[field]
    assert payload["location"] == FIELD_LOCATIONS[field]
    assert type(payload["display_length_in_m"]) in (int,float)
    assert payload["display_length_in_m"] == UNITS[data["geometry"]["length_unit"]]
    assert payload["shape"] == shape and all(type(v) is int for v in payload["shape"])
    if field in STEP_FIELDS:
        assert index >= 1
        assert payload["interval_start"] == times(data)[index-1]
        assert payload["interval_end"] == times(data)[index]
    return numeric(payload["arrays"][field],shape)


def expected_arrays(a,case,data):
    x,cells,ts = a["node_coordinates"],a["triangles"],a["time"]
    assert np.max(abs(x.min(axis=0))) <= COORD_ATOL_M
    assert np.max(abs(x.max(axis=0)-[.002,.001])) <= COORD_ATOL_M
    assert np.all(cells >= 0) and np.all(cells < len(x))
    e = P1(x,cells,4.,2.5)
    require_close(np.asarray(e.area.sum()),np.asarray(2e-6),2e-6,"SI area")
    p = physics_si(data)
    q = p.get("heat_source_density", 0.0)
    if case == "affine":
        states = np.repeat((290+5000*x[:,0])[None,:],len(ts),axis=0)
        fixed = np.flatnonzero((abs(x[:,0])<=COORD_ATOL_M)|(abs(x[:,0]-.002)<=COORD_ATOL_M))
    else:
        rate = 3. if case in ("sampled_ramp","all_fixed_support") else q/4.
        states = np.repeat((p["initial_temperature"]+rate*(ts-ts[0]))[:,None],len(x),axis=1)
        fixed = np.flatnonzero((abs(x[:,0])<=COORD_ATOL_M)|(abs(x[:,0]-.002)<=COORD_ATOL_M)|
                              (abs(x[:,1])<=COORD_ATOL_M)|(abs(x[:,1]-.001)<=COORD_ATOL_M)) if p["prescribed_temperature"] else np.array([],dtype=int)
    assert np.array_equal(a["prescribed_node_ids"],fixed)
    d = e.histories(states,ts,q,fixed)
    expected = {"temperature":states,"heat_flux":d["flux"],
                "generated_heat_rate_per_depth":d["source"],"heat_storage_rate_per_depth":d["storage"],
                "reaction_heat_rate_per_depth":d["reaction"],"residual_heat_rate_per_depth":d["residual"],
                "stored_heat_per_depth":d["heat"],"thermal_energy_functional_per_depth":d["quadratic"],
                "prescribed_temperature":states[:,fixed]}
    temp_scale = max(1,float(np.max(abs(states))))
    rate_scale = max(1e-30,abs(q)*2e-6,12*2e-6,float(np.max(np.sum(abs(d["reaction"]),axis=1))))
    scales = {"temperature":temp_scale,"prescribed_temperature":300.,
              "heat_flux":max(1.,2.5*np.ptp(states)/.001),
              "stored_heat_per_depth":max(1e-30,4*2e-6*temp_scale),
              "thermal_energy_functional_per_depth":max(1e-30,2*2e-6*temp_scale**2)}
    for field,value in expected.items():
        require_close(a[field],value,scales.get(field,rate_scale),field)
    require_close(d["balance"],np.zeros(len(ts)-1),rate_scale,"independent balance")
    return expected


def audit(a,case,data,summary):
    expected_arrays(a,case,data)
    if len(a["time"]) == len(TIMES_S):
        kind = "affine" if case=="affine" else "ramp" if case in ("sampled_ramp","all_fixed_support") else "heating"
        p = physics_si(data)
        initial = p["initial_temperature"]
        audit_arrays(a,kind,p.get("heat_source_density", 0.0),
                     initial if type(initial) in (int,float) else 290.)
    audit_summary(summary,a)
    if case == "uniform_absolute":
        require_close(a["temperature"][:,0],300+2*a["time"],306.,"absolute time origin")
    if case == "cooling_signed":
        assert a["temperature"][-1,0] < 0       # a solution may go below 0 K; inputs may not
    return a
