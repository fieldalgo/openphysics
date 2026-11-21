# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Independent Studio wire expectations; numerical truth comes from analytic/P1 math."""
import copy
import math
import numpy as np

# These are unchanged independent acceptance assets, supplied by the separately
# reviewed steady boundary feature when the coordinator combines the branches.
from steady_boundary_independent_cases import FIELDS, IDENTIFIERS, LOCATIONS as _PLACES, audit, model
from steady_boundary_independent_oracle import Elements, UNITS, close, slab

WIRE_FORMAT = "studio-thermal-steady-v2"
PAIRS = dict(IDENTIFIERS.values())       # result format -> field layout (plain v3, boundary v4)
LEGACY = tuple(FIELDS)[:9]               # the arrays of a result without boundary keys
STRUCTURAL = ("triangles", "prescribed_node_ids")
LOCATIONS = {key: _PLACES.get(key, "nodes") for key in FIELDS}


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
    """Validate the top-level wire contract observed in the public server (version 2: the
    boundary pair, version 1: the plain pair)."""
    if payload.get("payload_format") != WIRE_FORMAT or payload.get("kind") != "thermal.steady2d":
        raise AssertionError("wire format/kind")
    fmt = IDENTIFIERS[version][0]
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
    if "units" in summary or "mesh_length_unit" in summary:
        raise AssertionError("format 0.2 unit metadata")
    # the document's length_unit, as the summary's resolved inputs carry it
    length=payload.get("length_unit")
    if (length not in UNITS
            or summary["resolved_inputs"]["geometry.domain.xmin"].get("length_unit") != length):
        raise AssertionError("declared length_unit")
    expected_scale=UNITS[length]
    close(np.array(scale),np.array(expected_scale),expected_scale,"display declaration",1e-9)
    for meta in ("field_shapes","field_locations"):
        if not isinstance(summary[meta],dict) or set(summary[meta]) != set(selected):
            raise AssertionError("exact metadata field set")
    if set(summary["field_units"]) != set(selected)-set(STRUCTURAL):
        raise AssertionError("exact unit field set")
    arrays = {}
    for key in selected:
        _number_tree(source[key], key in STRUCTURAL)
        value = np.asarray(source[key])
        # Empty lists infer float dtype; integer D0 remains a valid empty array.
        if key == "prescribed_node_ids" and value.shape == (0,):
            value = np.array([], dtype=int)
        if value.dtype.kind not in "iuf":
            raise AssertionError("wire numeric dtype")
        arrays[key] = np.array(value, copy=True)
    x,t,d = arrays["node_coordinates"],arrays["triangles"],arrays["prescribed_node_ids"]
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
    shape.update(node_coordinates=(len(x),2),triangles=(len(t),3),
                 heat_flux=(len(t),2),prescribed_node_ids=(len(d),),
                 prescribed_temperature=(len(d),))
    for key,value in arrays.items():
        metadata_shape=summary["field_shapes"][key]
        if (not isinstance(metadata_shape,list) or any(type(v) is not int for v in metadata_shape)
                or value.shape != shape[key] or metadata_shape != list(shape[key])):
            raise AssertionError("array shape metadata: "+key)
        if summary["field_units"].get(key) != FIELDS[key] or summary["field_locations"][key] != LOCATIONS[key]:
            raise AssertionError("array units/location: "+key)
    # Independently check actual CCW geometry, not an asserted mesh statistic.
    Elements(x,t,1.,0.)
    for forbidden in ("neff","fields","modes","group_index","time","time_s","parameter","wavelength"):
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
    arrays={"node_coordinates":x,"triangles":t,"temperature":T,"heat_flux":e.flux(T),
            "generated_heat_rate_per_depth":e.f,"reaction_heat_rate_per_depth":reaction,
            "residual_heat_rate_per_depth":r,"prescribed_node_ids":fixed,"prescribed_temperature":T[fixed],
            "outward_prescribed_heat_rate_per_depth":G,"ambient_convective_heat_rate_per_depth":B,
            "outward_convective_heat_rate_per_depth":HT-B,"applied_heat_rate_per_depth":rhs}
    fmt=IDENTIFIERS[2][0]
    return {"payload_format":WIRE_FORMAT,"kind":"thermal.steady2d",
            "job":"synthetic-job","result_id":"synthetic-result","client_revision":7,"request_seq":11,
            "result_format":fmt,"field_layout":PAIRS[fmt],"length_unit":"m","display_length_in_m":1.,
            "arrays":{k:v.tolist() for k,v in arrays.items()},
            "summary":{"physics_type":"thermal.steady2d","result_format":fmt,"field_layout":PAIRS[fmt],
                       "resolved_inputs":{"geometry.domain.xmin":{"authored":.1,"value":.1,"unit":"m",
                                                                  "length_unit":"m"}},
                       "field_shapes":{k:list(v.shape) for k,v in arrays.items()},
                       "field_units":{k:u for k,u in FIELDS.items() if u is not None},
                       "field_locations":dict(LOCATIONS)}}


def malformed_wires():
    original=synthetic_wire()
    for kind in ("layout","unit","shape","nan","infinity","bool","index","fractional","missing","extra","scale_bool","scale_zero","scale_nan","scale_units","nested_coordinates","metadata_shape_float","metadata_shape_bool",
                 "identity_float","identity_bool","identity_empty"):
        p=copy.deepcopy(original)
        if kind == "layout": p["field_layout"]="thermal2d-p1-node-cell-boundary-v2"   # retired
        elif kind == "unit": p["summary"]["field_units"]["generated_heat_rate_per_depth"]="W"
        elif kind == "shape": p["arrays"]["heat_flux"]=p["arrays"]["heat_flux"][:-1]
        elif kind in ("nan","infinity"): p["arrays"]["temperature"][0]=float(kind if kind=="nan" else "inf")
        elif kind == "bool": p["arrays"]["temperature"][0]=True
        elif kind == "index": p["arrays"]["triangles"][0][0]=999
        elif kind == "fractional": p["arrays"]["triangles"][0][0]=.5
        elif kind == "missing": p["arrays"].pop("ambient_convective_heat_rate_per_depth")
        elif kind == "scale_bool": p["display_length_in_m"]=True
        elif kind == "scale_zero": p["display_length_in_m"]=0.
        elif kind == "scale_nan": p["display_length_in_m"]=float("nan")
        elif kind == "scale_units": p["length_unit"]="mm"
        elif kind == "metadata_shape_float": p["summary"]["field_shapes"]["temperature"]=[5.0]
        elif kind == "metadata_shape_bool": p["summary"]["field_shapes"]["temperature"]=[True]
        elif kind == "identity_float": p["client_revision"]=7.0
        elif kind == "identity_bool": p["request_seq"]=True
        elif kind == "identity_empty": p["result_id"]=""
        elif kind == "nested_coordinates": p["coordinates"]={"display_length_in_m":1.}
        else: p["arrays"]["time"]=[0]
        yield kind,p


def audit_payload(payload, data, case, version=2):
    arrays=captured_arrays(payload,version)
    expected_scale=UNITS[data["geometry"]["length_unit"]]
    close(np.array(payload["display_length_in_m"]),np.array(expected_scale),expected_scale,
          "declared display length scale",1e-9)
    if version == 2:
        audit(arrays,data,case,patch=(case=="linear"))
    return arrays
