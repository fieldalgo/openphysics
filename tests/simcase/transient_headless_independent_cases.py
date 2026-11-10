# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Independent serializable transient consumers; expectations are analytic."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np

from simcase import Document, run
from transient_headless_independent_oracle import (
    COORD_ATOL_M, P1, TIMES_S, UNITS, require_close, uniform_heating, uniform_ramp)

PHYSICS = "thermal.transient2d"
FORMAT = "thermal.transient2d-result-v3"
LAYOUT = "thermal2d-transient-p1-node-cell-v2"
# saved arrays (format 0.3 names) -> SI unit; None for the structural arrays, which carry none
FIELD_UNITS = {
    "node_coordinates": "m", "triangles": None, "time": "s", "temperature": "K",
    "heat_flux": "W/m^2", "generated_heat_rate_per_depth": "W/m",
    "reaction_heat_rate_per_depth": "W/m", "residual_heat_rate_per_depth": "W/m",
    "heat_storage_rate_per_depth": "W/m", "stored_heat_per_depth": "J/m",
    "thermal_energy_functional_per_depth": "J K/m",
    "prescribed_node_ids": None, "prescribed_temperature": "K",
}


FIELD_LOCATIONS = {
    "node_coordinates": "nodes", "triangles": "triangle_connectivity", "time": "requested_times",
    "temperature": "nodes", "heat_flux": "triangle_centroids",
    "generated_heat_rate_per_depth": "nodes", "reaction_heat_rate_per_depth": "nodes",
    "residual_heat_rate_per_depth": "nodes", "heat_storage_rate_per_depth": "nodes",
    "stored_heat_per_depth": "domain", "thermal_energy_functional_per_depth": "domain",
    "prescribed_node_ids": "prescribed_nodes", "prescribed_temperature": "prescribed_nodes",
}
STEP_FIELDS = {"reaction_heat_rate_per_depth", "residual_heat_rate_per_depth", "heat_storage_rate_per_depth"}
STATIC_FIELDS = {"node_coordinates", "triangles", "prescribed_node_ids"}


def kelvin(value):
    """A format 0.3 temperature: a constant as a quantity string, a 0.2-style
    ``{"values_k": [...]}`` sample list as a tagged array."""
    if isinstance(value, dict):
        return {"unit": "K", "values": list(value["values_k"])}
    return f"{value!r} K"


def initial_temperature(value):
    if isinstance(value, dict):
        return {"type": "affine", "reference_temperature": kelvin(value["origin_temperature_k"]),
                "temperature_gradient": {"unit": "K/m", "values": list(value["gradient_k_per_m"])}}
    return kelvin(value)


def model(unit="m", n=8, initial=300.0, q=8.0, bc=None):
    scale = UNITS[unit]
    return {
        "openphysics": "0.3", "name": "Independent transient rectangle",
        "geometry": {"length_unit": unit, "depth": None,
                     "domain": {"xmin": 0.0, "xmax": .002/scale, "ymin": 0.0, "ymax": .001/scale}},
        "materials": {},
        "physics": {"heat1": {"type": PHYSICS, "thermal_conductivity": "2.5 W/(m K)",
            "volumetric_heat_capacity": {"value": "4 J/(m^3 K)",
                                         "accept": {"W-MAGNITUDE": "manufactured solution"}},
            "initial_temperature": initial_temperature(copy.deepcopy(initial)),
            "prescribed_temperature": {side: kelvin(v) for side, v in ({} if bc is None else bc).items()},
            "heat_source_density": f"{float(q)!r} W/m^3"}},
        "mesh": {"subdivision_count": [n, n]},
        "study": {"type": "transient", "time": {"unit": "s", "values": list(TIMES_S)}},
        "results": {"save_fields": True, "plots": False},
    }


def read_saved(directory):
    directory = Path(directory)
    summary = json.loads((directory/"summary.json").read_text(encoding="utf-8"))
    with np.load(directory/"fields.npz", allow_pickle=False) as archive:
        arrays = {name: np.array(archive[name], copy=True) for name in archive.files}
    for name, value in arrays.items():
        if value.dtype.hasobject:
            raise AssertionError("object array: "+name)
    if str(arrays["result_format"].item()) != FORMAT:
        raise AssertionError("format identifier")
    if str(arrays["field_layout"].item()) != LAYOUT:
        raise AssertionError("layout identifier")
    if summary["physics_type"] != PHYSICS or summary["result_format"] != FORMAT:
        raise AssertionError("summary physics/format identifier")
    if summary["field_layout"] != LAYOUT:
        raise AssertionError("summary layout identifier")
    metadata = json.loads(str(arrays["metadata_json"].item()))
    if metadata != summary:
        raise AssertionError("NPZ/JSON metadata disagreement")
    for name, unit in FIELD_UNITS.items():
        a = arrays[name]
        if summary["field_units"].get(name) != unit:
            raise AssertionError("field unit: "+name)
        if list(a.shape) != summary["field_shapes"][name]:
            raise AssertionError("field shape: "+name)
        if summary["field_locations"][name] != FIELD_LOCATIONS[name]:
            raise AssertionError("field location: "+name)
        axis = None if name in STATIC_FIELDS else "time[1:]" if name in STEP_FIELDS else "time"
        if summary["field_time_axes"].get(name) != axis:
            raise AssertionError("field time axis: "+name)
        if a.dtype.kind not in "iuf" or not np.all(np.isfinite(a)):
            raise AssertionError("nonfinite/nonreal raw: "+name)
    if (directory/".incomplete").exists():
        raise AssertionError("save returned with incomplete marker")
    return summary, arrays


def audit_summary(summary, arrays):
    times = arrays["time"]
    if summary["study"]["time"]["unit"] != "s":
        raise AssertionError("summary time unit")
    require_close(np.asarray(summary["study"]["time"]["values"]), times, 3, "summary requested times")
    source = arrays["generated_heat_rate_per_depth"].sum(axis=1)
    storage = arrays["heat_storage_rate_per_depth"].sum(axis=1)
    reaction = arrays["reaction_heat_rate_per_depth"].sum(axis=1)
    scale = max(24e-6, np.max(abs(source)), np.max(abs(storage)), np.max(abs(reaction)))
    for name, unit, expected in (
        ("generated_heat_rate_per_depth", "W/m", source), ("heat_storage_rate_per_depth", "W/m", storage),
        ("outward_heat_rate_per_depth", "W/m", -reaction),
        ("heat_rate_imbalance_per_depth", "W/m", storage-source[1:]-reaction),
        ("stored_heat_per_depth", "J/m", arrays["stored_heat_per_depth"]),
        ("thermal_energy_functional_per_depth", "J K/m", arrays["thermal_energy_functional_per_depth"])):
        physical_scale = max(scale, np.max(abs(expected))) if expected.size else scale
        if summary[name]["unit"] != unit:
            raise AssertionError("summary unit: "+name)
        require_close(np.asarray(summary[name]["values"]), expected, physical_scale, "summary "+name)


def audit_arrays(a, kind, q, initial=300.0):
    x, tri, ts = a["node_coordinates"], a["triangles"], a["time"]
    n, nt, m = len(x), len(ts), len(tri)
    require_close(ts, np.asarray(TIMES_S), 3, "explicit times")
    if np.max(np.abs(x.min(axis=0))) > COORD_ATOL_M:
        raise AssertionError("SI lower-left")
    if np.max(np.abs(x.max(axis=0)-[.002, .001])) > COORD_ATOL_M:
        raise AssertionError("SI extents")
    if tri.dtype.kind not in "iu" or np.any(tri < 0) or np.any(tri >= n):
        raise AssertionError("connectivity")
    e = P1(x, tri, 4.0, 2.5)
    require_close(np.asarray(e.area.sum()), np.asarray(2e-6), 2e-6, "area")
    if kind == "heating":
        expected = uniform_heating(ts, n, initial, q, 4)
    elif kind == "ramp":
        expected = uniform_ramp(ts, n)
    elif kind == "fixed":
        expected = np.full((nt, n), initial)
    elif kind == "affine":
        expected = np.repeat((290+5000*x[:, 0])[None, :], nt, axis=0)
    else:
        raise AssertionError("unknown independent scenario")
    require_close(a["temperature"], expected, max(1, np.max(abs(expected))), "analytic temperature")
    fixed = a["prescribed_node_ids"]
    if fixed.dtype.kind not in "iu" or fixed.ndim != 1:
        raise AssertionError("fixed integer IDs")
    if kind in ("ramp", "fixed"):
        selected = np.flatnonzero((abs(x[:, 0]) <= COORD_ATOL_M)
                    | (abs(x[:, 0]-.002) <= COORD_ATOL_M)
                    | (abs(x[:, 1]) <= COORD_ATOL_M)
                    | (abs(x[:, 1]-.001) <= COORD_ATOL_M))
    elif kind == "affine":
        selected = np.flatnonzero((abs(x[:, 0]) <= COORD_ATOL_M)
                    | (abs(x[:, 0]-.002) <= COORD_ATOL_M))
    else:
        selected = np.array([], dtype=int)
    if not np.array_equal(fixed, selected):
        raise AssertionError("independent exterior Dirichlet selection")
    d = e.histories(expected, ts, q, fixed)
    shape = {"temperature": (nt, n), "heat_flux": (nt, m, 2),
             "generated_heat_rate_per_depth": (nt, n), "reaction_heat_rate_per_depth": (nt-1, n),
             "residual_heat_rate_per_depth": (nt-1, n), "heat_storage_rate_per_depth": (nt-1, n),
             "stored_heat_per_depth": (nt,), "thermal_energy_functional_per_depth": (nt,),
             "prescribed_temperature": (nt, len(fixed))}
    for key, value in shape.items():
        if a[key].shape != value:
            raise AssertionError("time/state/step shape: "+key)
    scales = {"heat": max(1e-30, 4*2e-6*np.max(abs(expected))),
              "quadratic": max(1e-30, 2*2e-6*np.max(abs(expected))**2),
              "flux": max(1.0, 2.5*np.ptp(expected)/.001)}
    rate_scale = max(1e-30, abs(q)*2e-6, 12*2e-6,
                     float(np.max(np.sum(abs(d["reaction"]), axis=1))))
    for field, key in (("generated_heat_rate_per_depth", "source"),
                       ("heat_storage_rate_per_depth", "storage"),
                       ("residual_heat_rate_per_depth", "residual"),
                       ("reaction_heat_rate_per_depth", "reaction"),
                       ("heat_flux", "flux"),
                       ("stored_heat_per_depth", "heat"),
                       ("thermal_energy_functional_per_depth", "quadratic")):
        require_close(a[field], d[key], scales.get(key, rate_scale), field)
    require_close(d["balance"], np.zeros(nt-1), rate_scale, "heat balance")
    if kind == "heating" and len(fixed):
        raise AssertionError("insulated selection")
    if kind in ("ramp", "fixed"):
        require_close(a["prescribed_temperature"], expected[:, fixed], 300, "DBC history")
    return e


def saved_run(data, out):
    # Public Document/run/save only; producer summaries never define truth.
    result = run(Document.from_dict(copy.deepcopy(data)), False)
    result.save(out)
    summary, arrays = read_saved(out)
    audit_summary(summary, arrays)
    return summary, arrays


class TestTransientHeadlessIndependent(unittest.TestCase):
    def test_uniform_units_cooling_and_history(self):
        for unit in UNITS:
            for q in (8.0, -1600.0):
                with self.subTest(unit=unit, q=q), tempfile.TemporaryDirectory() as tmp:
                    summary, a = saved_run(model(unit, q=q), Path(tmp)/"out")
                    audit_arrays(a, "heating", q)
                    if q < 0:
                        self.assertLess(a["temperature"].min(), 0)   # a solution may go below 0 K

    def test_sampled_ramp_and_nonzero_reaction(self):
        ramp = (290+3*(np.asarray(TIMES_S)-TIMES_S[0])).tolist()
        bc = {side: {"values_k": ramp} for side in ("left", "right", "bottom", "top")}
        with tempfile.TemporaryDirectory() as tmp:
            _, a = saved_run(model(initial=290, q=12, bc=bc), Path(tmp)/"ramp")
            audit_arrays(a, "ramp", 12, 290)
            _, b = saved_run(model(n=1, initial=290, q=2, bc=bc), Path(tmp)/"support")
            audit_arrays(b, "ramp", 2, 290)
            require_close(b["reaction_heat_rate_per_depth"].sum(axis=1), np.full(4, 20e-6),
                          24e-6, "nonzero support sign")

    def test_affine_initial_and_fixed_source_support(self):
        initial = {"type": "affine", "origin_temperature_k": 290,
                   "gradient_k_per_m": [5000, 0]}
        with tempfile.TemporaryDirectory() as tmp:
            _, a = saved_run(model(initial=initial, q=0, bc={"left": 290, "right": 300}),
                             Path(tmp)/"affine")
            audit_arrays(a, "affine", 0)
            bc = {s: 300 for s in ("left", "right", "bottom", "top")}
            _, b = saved_run(model(n=1, q=2, bc=bc), Path(tmp)/"fixed")
            audit_arrays(b, "fixed", 2)

    def test_strict_inputs_and_initial_boundary_mismatch(self):
        bad = []
        for value in (True, "0 J/(m^3 K)", "-1 J/(m^3 K)", float("inf")):
            d = model();d["physics"]["heat1"]["volumetric_heat_capacity"] = value
            bad.append(d)
        for times in ([0], [0, 0], [1, 0], [-1, 0], [0, True], [0, float("nan")]):
            d=model();d["study"]["time"]["values"]=times;bad.append(d)
        for value in ({"left": 301}, {"left": {"values_k": [300]}},
                      {"left": {"values_k": [300, 301, 302, 303, 304]}, "bottom": 300}):
            d=model();d["physics"]["heat1"]["prescribed_temperature"]={k: kelvin(v) for k, v in value.items()}
            bad.append(d)
        # format 0.3 carries units on the values: a units block is unknown, a time needs a time unit
        d=model();d["units"]={"length":"mm","temperature":"K","time":"s"};bad.append(d)
        d=model();d["study"]["time"]["unit"]="K";bad.append(d)
        d=model();d["physics"]["heat1"]["outward_flux"]={};bad.append(d)
        d=model();d["physics"]["heat1"]["initial_temperature"]={"unit": "K", "values": [300]*81};bad.append(d)
        d=model();d["results"]["plots"]=True;bad.append(d)
        for i, data in enumerate(bad):
            with self.subTest(case=i), self.assertRaises(ValueError):
                doc=Document.from_dict(data)
                run(doc, False)

    def test_cli_and_existing_output_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);model_path=root/"input.json";out=root/"out"
            model_path.write_text(json.dumps(model()), encoding="utf-8")
            command=[sys.executable, "-I", "-c",
                     "import sys; from simcase.cli import main; sys.exit(main(sys.argv[1:]))",
                     "run", str(model_path), "-q", "-o", str(out)]
            done=subprocess.run(command,cwd=root,capture_output=True,text=True,encoding="utf-8")
            self.assertEqual(done.returncode,0,done.stdout+done.stderr)
            _, a=read_saved(out);audit_arrays(a,"heating",8)
            before={p.name:p.read_bytes() for p in out.iterdir() if p.is_file()}
            again=subprocess.run(command,cwd=root,capture_output=True,text=True,encoding="utf-8")
            self.assertNotEqual(again.returncode,0)
            self.assertEqual(before,{p.name:p.read_bytes() for p in out.iterdir() if p.is_file()})

    def test_runtime_result_corruption_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, a=saved_run(model(),Path(tmp)/"out")
            mutations=[
                ("stored_heat_per_depth",a["thermal_energy_functional_per_depth"]),
                ("heat_storage_rate_per_depth",np.zeros_like(a["heat_storage_rate_per_depth"])),
                ("time",a["time"][1:]),
                ("temperature",a["temperature"][1:]),
                ("node_coordinates",a["node_coordinates"]*1000),
            ]
            for name,value in mutations:
                with self.subTest(field=name),self.assertRaises(AssertionError):
                    audit_arrays(dict(a,**{name:value}),"heating",8)

    def test_saved_identifier_units_and_object_arrays_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            summary,a=saved_run(model(),root/"original")
            for variant in ("format","layout","units","object"):
                out=root/variant;out.mkdir()
                metadata=copy.deepcopy(summary)
                altered={k:np.array(v,copy=True) for k,v in a.items()}
                if variant=="format":
                    altered["result_format"]=np.asarray("wrong-result-v1")
                elif variant=="layout":
                    altered["field_layout"]=np.asarray("wrong-field-layout")
                elif variant=="units":
                    metadata["field_units"]["stored_heat_per_depth"]="J K/m"
                else:
                    altered["temperature"]=np.asarray([[object()]],dtype=object)
                (out/"summary.json").write_text(json.dumps(metadata),encoding="utf-8")
                with (out/"fields.npz").open("wb") as stream:
                    np.savez(stream,**altered)
                with self.subTest(variant=variant),self.assertRaises((AssertionError,ValueError)):
                    read_saved(out)

    def test_owned_result_snapshot_and_fields_disabled(self):
        data = model()
        document = Document.from_dict(copy.deepcopy(data))
        result = run(document, False)
        saved = {name: np.array(getattr(result, name), copy=True) for name in FIELD_UNITS}
        for name in FIELD_UNITS:
            self.assertFalse(getattr(result, name).flags.writeable, name)
        document["study"]["time"]["values"][0] = 99
        document["physics"]["heat1"]["initial_temperature"] = "-900 K"
        for name, expected in saved.items():
            self.assertTrue(np.array_equal(getattr(result, name), expected), name)
        with tempfile.TemporaryDirectory() as tmp:
            result.save(Path(tmp)/"snapshot")
            _, arrays = read_saved(Path(tmp)/"snapshot")
            audit_arrays(arrays, "heating", 8)
            data["results"]["save_fields"] = False
            disabled = run(Document.from_dict(data), False)
            disabled.save(Path(tmp)/"disabled")
            self.assertFalse((Path(tmp)/"disabled"/"fields.npz").exists())
            summary = json.loads((Path(tmp)/"disabled"/"summary.json").read_text(encoding="utf-8"))
            self.assertFalse(summary["save_fields"])
            self.assertEqual(summary["field_shapes"]["reaction_heat_rate_per_depth"],
                             [4, len(disabled.node_coordinates)])

    def test_accepted_initial_roundoff_is_not_projected(self):
        eps = np.finfo(float).eps
        initial = float(300+8*eps*300)
        bc = {s: 300.0 for s in ("left","right","bottom","top")}
        data = model(n=1, initial=initial, q=0, bc=bc)
        result = run(Document.from_dict(data), False)
        self.assertTrue(np.array_equal(result.temperature[0], np.full(len(result.node_coordinates), initial)))
        expected = np.full_like(result.temperature, 300.0)
        expected[0] = initial
        e = P1(result.node_coordinates, result.triangles, 4, 2.5)
        d = e.histories(expected, np.array(TIMES_S), 0, np.arange(len(result.node_coordinates)))
        scale = max(np.max(abs(d["storage"])), np.finfo(float).tiny)
        require_close(result.heat_storage_rate_per_depth, d["storage"], scale, "accepted initial old mass")
