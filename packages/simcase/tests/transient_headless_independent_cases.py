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
FORMAT = "thermal.transient2d-result-v1"
LAYOUT = "thermal2d-transient-p1-node-cell-v1"
FIELD_UNITS = {
    "nodes_m": "m", "triangles": "1", "time_s": "s", "temperature_k": "K",
    "heat_flux_w_m2": "W/m^2", "source_load_w_per_m": "W/m",
    "reaction_w_per_m": "W/m", "residual_w_per_m": "W/m",
    "storage_rate_w_per_m": "W/m", "heat_content_j_per_m": "J/m",
    "quadratic_functional_jk_per_m": "J K/m",
    "dirichlet_node_ids": "1", "dirichlet_temperatures_k": "K",
}


def model(unit="m", n=8, initial=300.0, q=8.0, bc=None):
    scale = UNITS[unit]
    return {
        "openphysics": "0.2", "name": "Independent transient rectangle",
        "units": {"length": unit, "temperature": "K", "time": "s"},
        "geometry": {"domain": {"xmin": 0.0, "xmax": .002/scale,
                                 "ymin": 0.0, "ymax": .001/scale}},
        "materials": {},
        "physics": {"heat1": {"type": PHYSICS, "conductivity_w_mk": 2.5,
            "volumetric_heat_capacity_j_m3k": 4.0,
            "initial_temperature_k": copy.deepcopy(initial),
            "dirichlet_temperature_k": copy.deepcopy({} if bc is None else bc),
            "heat_source_w_m3": q}},
        "mesh": {"subdivisions": [n, n]},
        "study": {"type": "transient", "time_s": list(TIMES_S)},
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
        if summary["field_units"][name] != unit:
            raise AssertionError("field unit: "+name)
        if list(a.shape) != summary["field_shapes"][name]:
            raise AssertionError("field shape: "+name)
        if name not in summary["field_locations"]:
            raise AssertionError("missing field location: "+name)
        if a.dtype.kind not in "iuf" or not np.all(np.isfinite(a)):
            raise AssertionError("nonfinite/nonreal raw: "+name)
    if (directory/".incomplete").exists():
        raise AssertionError("save returned with incomplete marker")
    return summary, arrays


def audit_arrays(a, kind, q, initial=300.0):
    x, tri, ts = a["nodes_m"], a["triangles"], a["time_s"]
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
    require_close(a["temperature_k"], expected, max(1, np.max(abs(expected))), "analytic temperature")
    fixed = a["dirichlet_node_ids"]
    d = e.histories(expected, ts, q, fixed)
    shape = {"temperature_k": (nt, n), "heat_flux_w_m2": (nt, m, 2),
             "source_load_w_per_m": (nt, n), "reaction_w_per_m": (nt-1, n),
             "residual_w_per_m": (nt-1, n), "storage_rate_w_per_m": (nt-1, n),
             "heat_content_j_per_m": (nt,), "quadratic_functional_jk_per_m": (nt,),
             "dirichlet_temperatures_k": (nt, len(fixed))}
    for key, value in shape.items():
        if a[key].shape != value:
            raise AssertionError("time/state/step shape: "+key)
    scales = {"heat": max(1e-30, 4*2e-6*np.max(abs(expected))),
              "quadratic": max(1e-30, 2*2e-6*np.max(abs(expected))**2),
              "flux": max(1.0, 2.5*np.ptp(expected)/.001)}
    rate_scale = max(1e-30, abs(q)*2e-6, 12*2e-6,
                     float(np.max(np.sum(abs(d["reaction"]), axis=1))))
    for field, key in (("source_load_w_per_m", "source"),
                       ("storage_rate_w_per_m", "storage"),
                       ("residual_w_per_m", "residual"),
                       ("reaction_w_per_m", "reaction"),
                       ("heat_flux_w_m2", "flux"),
                       ("heat_content_j_per_m", "heat"),
                       ("quadratic_functional_jk_per_m", "quadratic")):
        require_close(a[field], d[key], scales.get(key, rate_scale), field)
    require_close(d["balance"], np.zeros(nt-1), rate_scale, "heat balance")
    if kind == "heating" and len(fixed):
        raise AssertionError("insulated selection")
    if kind in ("ramp", "fixed"):
        require_close(a["dirichlet_temperatures_k"], expected[:, fixed], 300, "DBC history")
    return e


def saved_run(data, out):
    # Public Document/run/save only; producer summaries never define truth.
    result = run(Document.from_dict(copy.deepcopy(data)), False)
    result.save(out)
    return read_saved(out)


class TestTransientHeadlessIndependent(unittest.TestCase):
    def test_uniform_units_cooling_and_history(self):
        for unit in UNITS:
            for q in (8.0, -1600.0):
                with self.subTest(unit=unit, q=q), tempfile.TemporaryDirectory() as tmp:
                    summary, a = saved_run(model(unit, q=q), Path(tmp)/"out")
                    audit_arrays(a, "heating", q)
                    if q < 0:
                        self.assertLess(a["temperature_k"].min(), 0)

    def test_sampled_ramp_and_nonzero_reaction(self):
        ramp = (290+3*(np.asarray(TIMES_S)-TIMES_S[0])).tolist()
        bc = {side: {"values_k": ramp} for side in ("left", "right", "bottom", "top")}
        with tempfile.TemporaryDirectory() as tmp:
            _, a = saved_run(model(initial=290, q=12, bc=bc), Path(tmp)/"ramp")
            audit_arrays(a, "ramp", 12, 290)
            _, b = saved_run(model(n=1, initial=290, q=2, bc=bc), Path(tmp)/"support")
            audit_arrays(b, "ramp", 2, 290)
            require_close(b["reaction_w_per_m"].sum(axis=1), np.full(4, 20e-6),
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
        for value in (True, 0, -1, float("inf")):
            d = model();d["physics"]["heat1"]["volumetric_heat_capacity_j_m3k"] = value
            bad.append(d)
        for times in ([0], [0, 0], [1, 0], [-1, 0], [0, True], [0, float("nan")]):
            d=model();d["study"]["time_s"]=times;bad.append(d)
        for value in ({"left": 301}, {"left": {"values_k": [300]}},
                      {"left": {"values_k": [300, 301, 302, 303, 304]}, "bottom": 300}):
            d=model();d["physics"]["heat1"]["dirichlet_temperature_k"]=value;bad.append(d)
        for units in ({"length":"mm","temperature":"C","time":"s"},
                      {"length":"mm","temperature":"K","time":"ms"}):
            d=model();d["units"]=units;bad.append(d)
        d=model();d["physics"]["heat1"]["outward_flux"]={};bad.append(d)
        d=model();d["physics"]["heat1"]["initial_temperature_k"]=[300]*81;bad.append(d)
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
                ("heat_content_j_per_m",a["quadratic_functional_jk_per_m"]),
                ("storage_rate_w_per_m",np.zeros_like(a["storage_rate_w_per_m"])),
                ("time_s",a["time_s"][1:]),
                ("temperature_k",a["temperature_k"][1:]),
                ("nodes_m",a["nodes_m"]*1000),
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
                    metadata["field_units"]["heat_content_j_per_m"]="J K/m"
                else:
                    altered["temperature_k"]=np.asarray([[object()]],dtype=object)
                (out/"summary.json").write_text(json.dumps(metadata),encoding="utf-8")
                with (out/"fields.npz").open("wb") as stream:
                    np.savez(stream,**altered)
                with self.subTest(variant=variant),self.assertRaises((AssertionError,ValueError)):
                    read_saved(out)
