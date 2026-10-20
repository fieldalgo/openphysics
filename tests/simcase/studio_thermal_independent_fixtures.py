# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Independent Studio wire expectations; numerical truth comes from analytic/P1 math."""
import copy
import math
import numpy as np

# These are unchanged independent acceptance assets, supplied by the separately
# reviewed steady boundary feature when the coordinator combines the branches.
from steady_boundary_independent_cases import FIELDS, audit, model
from steady_boundary_independent_oracle import Elements, UNITS, close, slab

WIRE_FORMAT = "studio-thermal-steady-v1"
PAIRS = {
    "thermal.steady2d-result-v1": "thermal2d-p1-node-cell-v1",
    "thermal.steady2d-result-v2": "thermal2d-p1-node-cell-boundary-v2",
}
LEGACY = tuple(FIELDS)[:9]
LOCATIONS = {key: ("triangle_connectivity" if key == "triangles" else
                  "triangle_centroids" if key == "heat_flux_w_m2" else
                  "dirichlet_nodes" if key.startswith("dirichlet_") else "nodes")
             for key in FIELDS}


def envelope(data, revision=7, sequence=11):
    return {"doc": copy.deepcopy(data), "client_revision": revision, "request_seq": sequence}


def _number_tree(value, integer=False):
    if isinstance(value, list):
        for item in value:
            _number_tree(item, integer)
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AssertionError("non-numeric/bool wire scalar")
    if not math.isfinite(value):
        raise AssertionError("nonfinite wire scalar")
    if integer and (not isinstance(value, int) or abs(value) > 2**53-1):
        raise AssertionError("unsafe/noninteger index")


def captured_arrays(payload, version=2):
    """Validate the top-level wire contract observed in the public server."""
    if payload.get("payload_format") != WIRE_FORMAT or payload.get("kind") != "thermal.steady2d":
        raise AssertionError("wire format/kind")
    fmt = "thermal.steady2d-result-v"+str(version)
    if payload.get("result_format") != fmt or payload.get("field_layout") != PAIRS[fmt]:
        raise AssertionError("result/layout pair")
    scale = payload["display_length_in_m"]
    _number_tree(scale)
    if not isinstance(scale,(int,float)) or scale <= 0:
        raise AssertionError("positive display length scale")
    if "coordinates" in payload:
        raise AssertionError("obsolete nested coordinate metadata")
    for tag in ("client_revision","request_seq"):
        value=payload[tag]
        if type(value) is not int or not 0 <= value <= 2**53-1:
            raise AssertionError("safe integer wire identity")
    for tag in ("job","result_id"):
        if not isinstance(payload[tag],str) or not payload[tag]:
            raise AssertionError("nonempty wire identity")
    source = payload["arrays"]
    if not isinstance(source,dict):
        raise AssertionError("array mapping")
    selected = tuple(FIELDS) if version == 2 else LEGACY
    if set(source) != set(selected):
        raise AssertionError("exact versioned array set")
    summary = payload["summary"]
    if not isinstance(summary,dict):
        raise AssertionError("summary mapping")
    if (summary.get("physics_type") != "thermal.steady2d" or
            summary["result_format"] != fmt or summary["field_layout"] != PAIRS[fmt]):
        raise AssertionError("summary version pair")
    declared=summary["units"]
    if (not isinstance(declared,dict) or set(declared) != {"length","temperature"}
            or declared["temperature"] != "K" or summary["mesh_length_unit"] != "m"):
        raise AssertionError("thermal SI metadata")
    length=declared["length"]
    if isinstance(length,str):
        expected_scale=UNITS[length]
    elif isinstance(length,dict) and set(length)=={"in_m"}:
        expected_scale=length["in_m"]
        _number_tree(expected_scale)
        if expected_scale <= 0:
            raise AssertionError("positive custom length")
    else:
        raise AssertionError("declared length")
    close(np.array(scale),np.array(expected_scale),expected_scale,"display declaration",1e-9)
    for meta in ("field_shapes","field_units","field_locations"):
        if not isinstance(summary[meta],dict) or set(summary[meta]) != set(selected):
            raise AssertionError("exact metadata field set")
    arrays = {}
    for key in selected:
        _number_tree(source[key], key in ("triangles", "dirichlet_node_ids"))
        value = np.asarray(source[key])
        # Empty lists infer float dtype; integer D0 remains a valid empty array.
        if key == "dirichlet_node_ids" and value.shape == (0,):
            value = np.array([], dtype=int)
        if value.dtype.kind not in "iuf":
            raise AssertionError("wire numeric dtype")
        arrays[key] = np.array(value, copy=True)
    x,t,d = arrays["nodes_m"],arrays["triangles"],arrays["dirichlet_node_ids"]
    if x.ndim != 2 or x.shape[1] != 2 or not len(x):
        raise AssertionError("node shape")
    if t.ndim != 2 or t.shape[1] != 3 or not len(t):
        raise AssertionError("cell shape")
    if np.any(t < 0) or np.any(t >= len(x)) or d.ndim != 1:
        raise AssertionError("index range")
    if np.any(d < 0) or np.any(d >= len(x)) or np.any(np.diff(d) <= 0):
        raise AssertionError("Dirichlet ordering/range")
    if version == 1 and not len(d):
        raise AssertionError("legacy D cannot be empty")
    shape = {key: (len(x),) for key in selected}
    shape.update(nodes_m=(len(x),2),triangles=(len(t),3),
                 heat_flux_w_m2=(len(t),2),dirichlet_node_ids=(len(d),),
                 dirichlet_temperature_k=(len(d),))
    for key,value in arrays.items():
        metadata_shape=summary["field_shapes"][key]
        if (not isinstance(metadata_shape,list) or any(type(v) is not int for v in metadata_shape)
                or value.shape != shape[key] or metadata_shape != list(shape[key])):
            raise AssertionError("array shape metadata: "+key)
        if summary["field_units"][key] != FIELDS[key] or summary["field_locations"][key] != LOCATIONS[key]:
            raise AssertionError("array units/location: "+key)
    # Independently check actual CCW geometry, not an asserted mesh statistic.
    Elements(x,t,1.,0.)
    for forbidden in ("neff","fields","modes","group_index","time_s","parameter","wavelength"):
        if forbidden in payload:
            raise AssertionError("optical/transient payload contamination")
    return arrays


def synthetic_wire():
    """Five-node/four-cell parser fixture; never a solver acceptance result."""
    x=np.array([[.1,.2],[1.1,.2],[1.1,1.2],[.1,1.2],[.6,.7]])
    t=np.array([[0,1,4],[1,2,4],[2,3,4],[3,0,4]])
    T=300-7*(x[:,0]-.1)
    e=Elements(x,t,2.,0.)
    G,B,HT=e.boundary(T,{"right":2.},{"right":4.},{"right":290.})
    rhs=e.f+B-G;r=e.stiffness(T)+HT-rhs
    fixed=np.array([0,3]);reaction=np.zeros(5);reaction[fixed]=r[fixed]
    arrays={"nodes_m":x,"triangles":t,"temperature_k":T,"heat_flux_w_m2":e.flux(T),
            "load_w_per_m":e.f,"reaction_w_per_m":reaction,"residual_w_per_m":r,
            "dirichlet_node_ids":fixed,"dirichlet_temperature_k":T[fixed],
            "prescribed_outward_load_w_per_m":G,"ambient_load_w_per_m":B,
            "convective_outward_w_per_m":HT-B,"system_rhs_w_per_m":rhs}
    fmt="thermal.steady2d-result-v2"
    return {"payload_format":WIRE_FORMAT,"kind":"thermal.steady2d",
            "job":"synthetic-job","result_id":"synthetic-result","client_revision":7,"request_seq":11,
            "result_format":fmt,"field_layout":PAIRS[fmt],"display_length_in_m":1.,
            "arrays":{k:v.tolist() for k,v in arrays.items()},
            "summary":{"physics_type":"thermal.steady2d","result_format":fmt,"field_layout":PAIRS[fmt],
                       "units":{"length":"m","temperature":"K"},"mesh_length_unit":"m",
                       "field_shapes":{k:list(v.shape) for k,v in arrays.items()},
                       "field_units":dict(FIELDS),"field_locations":dict(LOCATIONS)}}


def malformed_wires():
    original=synthetic_wire()
    for kind in ("layout","unit","shape","nan","infinity","bool","index","fractional","missing","extra","scale_bool","scale_zero","scale_nan","scale_units","nested_coordinates","metadata_shape_float","metadata_shape_bool",
                 "identity_float","identity_bool","identity_empty"):
        p=copy.deepcopy(original)
        if kind == "layout": p["field_layout"]="thermal2d-p1-node-cell-v1"
        elif kind == "unit": p["summary"]["field_units"]["load_w_per_m"]="W"
        elif kind == "shape": p["arrays"]["heat_flux_w_m2"]=p["arrays"]["heat_flux_w_m2"][:-1]
        elif kind in ("nan","infinity"): p["arrays"]["temperature_k"][0]=float(kind if kind=="nan" else "inf")
        elif kind == "bool": p["arrays"]["temperature_k"][0]=True
        elif kind == "index": p["arrays"]["triangles"][0][0]=999
        elif kind == "fractional": p["arrays"]["triangles"][0][0]=.5
        elif kind == "missing": p["arrays"].pop("ambient_load_w_per_m")
        elif kind == "scale_bool": p["display_length_in_m"]=True
        elif kind == "scale_zero": p["display_length_in_m"]=0.
        elif kind == "scale_nan": p["display_length_in_m"]=float("nan")
        elif kind == "scale_units": p["summary"]["units"]["length"]="mm"
        elif kind == "metadata_shape_float": p["summary"]["field_shapes"]["temperature_k"]=[5.0]
        elif kind == "metadata_shape_bool": p["summary"]["field_shapes"]["temperature_k"]=[True]
        elif kind == "identity_float": p["client_revision"]=7.0
        elif kind == "identity_bool": p["request_seq"]=True
        elif kind == "identity_empty": p["result_id"]=""
        elif kind == "nested_coordinates": p["coordinates"]={"display_length_in_m":1.}
        else: p["arrays"]["time_s"]=[0]
        yield kind,p


def audit_payload(payload, data, case, version=2):
    arrays=captured_arrays(payload,version)
    unit=data["units"]["length"]
    expected_scale=UNITS[unit] if isinstance(unit,str) else unit["in_m"]
    close(np.array(payload["display_length_in_m"]),np.array(expected_scale),expected_scale,
          "declared display length scale",1e-9)
    if version == 2:
        audit(arrays,data,case,patch=(case=="linear"))
    return arrays
