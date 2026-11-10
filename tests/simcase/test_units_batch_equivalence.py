# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The equivalence harness of the units and naming batch (``tools/units_batch``, never shipped).

Check P2-1 of the batch: every shipped example and every frozen fixture, as a 0.2 document on
the baseline code, gives the same solver and mesher inputs and the same saved bytes as its
0.3 twin on this code, under the closed transforms of ``tools/units_batch/compare.py``. Until a
kind's commit converts it, a kind is compared in identity mode (its 0.2 documents on both
sides), which is P2-3.

- ``test_the_harness_is_not_shipped`` runs everywhere, the installed-package run included.
- The other checks need the ``tools/`` folder, which the installed-package run does not copy
  (and where a skip would fail the run), so they are defined in a source checkout only. The
  harness self-checks run every time: a one-ulp change is detected, layout maps are applied
  and closed, and the converter reproduces the converted examples of the specification.
- ``test_units_batch_equivalence`` runs only when ``OPENPHYSICS_BATCH_BASELINE`` names the
  baseline commit (the merge base with main); otherwise it is skipped and reported as not run.
  The dispatch-only ``units-batch-equivalence`` job of ``.github/workflows/validate.yml`` sets it.
  ``OPENPHYSICS_BATCH_REPORT`` names a folder for the comparison report and both manifests.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tools" / "units_batch"
IMPORT_PACKAGES = ("galerkin", "refsol", "meshine", "meshloom", "gmshio", "physmat", "simcase", "sipi")
HARNESS_MODULES = ("units_batch", "record", "compare", "convert_v02", "tools.units_batch.record",
                   "tools.units_batch.compare", "tools.units_batch.convert_v02")


def _package_dirs():
    dirs = []
    for name in IMPORT_PACKAGES:
        spec = importlib.util.find_spec(name)
        if spec is not None and spec.submodule_search_locations:
            dirs += [Path(p) for p in spec.submodule_search_locations]
    return dirs


def test_the_harness_is_not_shipped():
    """No shipped package mentions the harness, and from the folders the packages are imported
    from (and the standard library and site-packages) no harness module can be imported."""
    dirs = _package_dirs()
    assert {d.name for d in dirs} >= {"galerkin", "meshine", "physmat", "simcase"}
    for folder in dirs:
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix in (".py", ".json", ".txt", ".toml", ".cfg", ".mjs", ".js", ".html"):
                assert "units_batch" not in path.read_text(encoding="utf-8", errors="replace"), path
    roots = sorted({str(d.parent) for d in dirs})
    code = ("import importlib.util, json, sys; sys.path[:0] = json.loads(sys.argv[1]); out = {}\n"
            "for name in json.loads(sys.argv[2]):\n"
            "    try: spec = importlib.util.find_spec(name)\n"
            "    except ModuleNotFoundError: spec = None\n"
            "    out[name] = None if spec is None else str(spec.origin)\n"
            "print(json.dumps(out))")
    done = subprocess.run([sys.executable, "-I", "-c", code, json.dumps(roots), json.dumps(HARNESS_MODULES)],
                          capture_output=True, text=True, encoding="utf-8", check=True, cwd=dirs[0].parent)
    found = json.loads(done.stdout)
    assert all(origin is None or "units_batch" not in origin for origin in found.values()), found


if HARNESS.is_dir():

    def _module(name):
        spec = importlib.util.spec_from_file_location(f"_units_batch_{name}", HARNESS / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _env():
        env = os.environ.copy()
        env.update(MPLBACKEND="Agg", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
                   PYTHONIOENCODING="utf-8")
        return env

    def _record(root: Path, out: Path, documents: list[str], timeout=3600):
        done = subprocess.run([sys.executable, "-I", str(HARNESS / "record.py"), "--root", str(root),
                               "--out", str(out), *documents], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=_env(), timeout=timeout)
        assert done.returncode == 0, done.stdout + done.stderr
        return done.stdout

    def _compare(old: Path, new: Path, *mode, report: Path | None = None):
        command = [sys.executable, str(HARNESS / "compare.py"), "--old", str(old), "--new", str(new), *mode]
        if report is not None:
            command += ["--report", str(report)]
        return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env=_env())

    def test_the_harness_folder_follows_the_tools_rules():
        """tools/README.md: no __init__.py or conftest.py; fixtures are named apart from the examples."""
        assert not list(HARNESS.rglob("__init__.py")) and not list(HARNESS.rglob("conftest.py"))
        fixtures = {p.stem for p in (HARNESS / "fixtures" / "v02").glob("*.json")}
        examples = {p.stem for p in (ROOT / "examples" / "simcase").glob("*.json")}
        assert fixtures and not fixtures & examples
        corpus = json.loads((HARNESS / "maps" / "corpus.json").read_text(encoding="utf-8"))
        for path in (HARNESS / "fixtures" / "v02").glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["openphysics"] == "0.2", path.name
            (kind,) = {p["type"] for p in data["physics"].values()}
            assert kind in corpus["modes"], path.name

    @pytest.fixture(scope="module")
    def slab_recording(tmp_path_factory):
        """thermal_slab recorded on this checkout twice, and once with its conductivity one ulp up."""
        import numpy as np
        work = tmp_path_factory.mktemp("units_batch")
        source = ROOT / "examples" / "simcase" / "thermal_slab.json"
        nudged = json.loads(source.read_text(encoding="utf-8"))
        k = float(nudged["physics"]["heat1"]["thermal_conductivity"].split()[0])
        nudged["physics"]["heat1"]["thermal_conductivity"] = f"{float(np.nextafter(k, np.inf))!r} W/(m K)"
        (work / "ulp").mkdir()
        (work / "ulp" / "thermal_slab.json").write_text(json.dumps(nudged), encoding="utf-8")
        for side, doc in (("a", source), ("b", source), ("ulp", work / "ulp" / "thermal_slab.json")):
            _record(ROOT, work / f"rec_{side}", [str(doc)], timeout=600)
        return work

    def test_the_comparator_passes_a_repeat_and_detects_a_one_ulp_change(slab_recording):
        same = _compare(slab_recording / "rec_a", slab_recording / "rec_b", "--identity")
        assert same.returncode == 0, same.stdout + same.stderr
        assert "1 documents compared: 1 equal, 0 different" in same.stdout
        nudged = _compare(slab_recording / "rec_a", slab_recording / "rec_ulp", "--identity")
        assert nudged.returncode == 1, nudged.stdout
        assert "galerkin.thermal.solve_steady_heat" in nudged.stdout      # the solver input
        assert "fields.npz temperature" in nudged.stdout                  # and a saved array
        assert "0x1.9000000000001p+3" in nudged.stdout                    # 12.5 one ulp up

    def test_layout_maps_are_applied_and_closed(slab_recording, tmp_path):
        """A synthetic layout change: renamed arrays under =, neg and L1 pass; one flipped bit,
        an unmapped array and an unlisted added array each fail."""
        import numpy as np
        old = slab_recording / "rec_a"
        new = tmp_path / "rec_new"
        shutil.copytree(slab_recording / "rec_b", new)
        fields = new / "thermal_slab" / "result" / "fields.npz"
        with np.load(fields, allow_pickle=False) as data:
            arrays = {k: data[k] for k in data.files}
        layout = str(arrays["field_layout"])
        renamed = {"temperature": ("temperature_renamed", "="), "generated_heat_rate_per_depth": ("negated", "neg"),
                   "node_coordinates": ("node_coordinates_um_as_m", "L1")}
        moved = dict(arrays)
        for old_key, (new_key, f) in renamed.items():
            value = moved.pop(old_key)
            moved[new_key] = {"=": value, "neg": np.subtract(0.0, value), "L1": value * 1e-6}[f]
        np.savez_compressed(fields, **moved)
        rules = [{"old": k, "new": renamed.get(k, (k, "="))[0], "f": renamed.get(k, (k, "="))[1]}
                 for k in arrays if k not in ("metadata_json", "field_layout", "result_format")]
        meshio = pytest.importorskip("meshio")
        vtu = meshio.read(old / "thermal_slab" / "export" / "fields.vtu")
        layout_map = {"format": "openphysics-units-batch-map-v1", "old_layout": layout, "new_layout": layout,
                      "arrays": rules, "summary": [{"old": "**", "new": "**", "f": "="}],
                      "identifiers": ["result_format", "field_layout"],
                      "vtu": [{"old": n, "new": n, "f": "="} for n in (*vtu.point_data, *vtu.cell_data)]}
        maps = tmp_path / "maps"
        maps.mkdir()
        (maps / f"{layout}.json").write_text(json.dumps(layout_map), encoding="utf-8")
        plan = tmp_path / "plan.json"
        plan.write_text(json.dumps({"thermal_slab": "layout"}), encoding="utf-8")
        ok = _compare(old, new, "--plan", str(plan), "--maps", str(maps))
        assert ok.returncode == 0, ok.stdout + ok.stderr
        # one bit of one mapped array
        flipped = dict(moved)
        flipped["temperature_renamed"] = moved["temperature_renamed"].copy()
        flipped["temperature_renamed"][3] = np.nextafter(flipped["temperature_renamed"][3], np.inf)
        np.savez_compressed(fields, **flipped)
        bad = _compare(old, new, "--plan", str(plan), "--maps", str(maps))
        assert bad.returncode == 1 and "temperature -> temperature_renamed (=)" in bad.stdout, bad.stdout
        # an array the new side adds without the map listing it
        np.savez_compressed(fields, **moved, extra_array=np.zeros(3))
        added = _compare(old, new, "--plan", str(plan), "--maps", str(maps))
        assert added.returncode == 1 and "extra_array: added" in added.stdout, added.stdout
        # an old array the map neither maps nor removes
        np.savez_compressed(fields, **moved)
        layout_map["arrays"] = [r for r in rules if r["old"] != "residual_heat_rate_per_depth"]
        (maps / f"{layout}.json").write_text(json.dumps(layout_map), encoding="utf-8")
        unmapped = _compare(old, new, "--plan", str(plan), "--maps", str(maps))
        assert unmapped.returncode == 1 and "residual_heat_rate_per_depth: not in map" in unmapped.stdout, \
            unmapped.stdout
        # a transform outside the closed list is refused
        layout_map["arrays"] = rules + [{"old": "x", "new": "y", "f": "times2"}]
        (maps / f"{layout}.json").write_text(json.dumps(layout_map), encoding="utf-8")
        refused = _compare(old, new, "--plan", str(plan), "--maps", str(maps))
        assert refused.returncode != 0 and "times2" in (refused.stdout + refused.stderr)

    def test_an_absent_default_passes_only_for_a_zero_with_its_default_listed():
        """absent_default (units batch C7): the 0.2 echo of a zero the reader filled in may be
        missing on the new side only when it is +0.0 and the new summary lists the default; a
        given value is compared as usual, and the rule is refused on anything but '='."""
        compare = _module("compare")
        layout_map = compare.LayoutMap({
            "format": "openphysics-units-batch-map-v1", "old_layout": "old", "new_layout": "new",
            "summary": [{"old": "body_force_n_m3.[]", "new": "body_force_density.values.[]", "f": "=",
                         "absent_default": "body_force_density"}],
            "summary_added": ["body_force_density.unit"]}, "test")
        listed = {"defaults_applied": [{"path": "physics.plate.body_force_density", "value": None, "reason": "r"}]}

        def failures(old, new):
            result = compare.Result("doc", "layout")
            compare.compare_trees_layout(old, new, layout_map, {}, "summary.json", result)
            return result.failures, result.counts["absent_defaults"]
        assert failures({"body_force_n_m3": [0.0, 0.0]}, listed) == ([], 2)
        assert failures({"body_force_n_m3": [0.0, 5.0]}, listed)[0]                       # a nonzero is lost
        assert failures({"body_force_n_m3": [-0.0, 0.0]}, listed)[0]                      # -0.0 is not +0.0
        assert failures({"body_force_n_m3": [0.0, 0.0]}, {"defaults_applied": []})[0]   # no default listed
        given = {"body_force_density": {"unit": "N/m^3", "values": [0.0, 5.0]}, **listed}
        assert failures({"body_force_n_m3": [0.0, 5.0]}, given) == ([], 0)
        assert failures({"body_force_n_m3": [0.0, 4.0]}, given)[0]
        with pytest.raises(ValueError, match="absent_default"):
            compare.LayoutMap({"format": "openphysics-units-batch-map-v1", "old_layout": "o",
                               "summary": [{"old": "a", "new": "b", "f": "neg", "absent_default": "b"}]}, "test")

    def test_the_exceptions_are_the_preregistered_ones_within_4_ulp():
        compare = _module("compare")
        assert set(compare.EXCEPTIONS) == {"propagation_loss", "bend_loss", "group_index_length_frame"}
        assert compare.ULP_LIMIT == 4
        assert compare.ulp_distance(1.0, float.fromhex("0x1.0000000000004p+0")) == 4
        assert compare.ulp_distance(-0.0, 0.0) == 0 and compare.ulp_distance(1.0, -1.0) > 4

    #: the em maps' exceptions (README "The em.modes2d commit"): (map, where, pattern, kind)
    EM_EXCEPTIONS = {
        ("em-modes2d-p1-node-centroid-v1", "summary", "propagation_loss.values.[].[]", "propagation_loss"),
        ("em-modes2d-p1-node-centroid-v1", "summary", "bend_loss.values.[].[]", "bend_loss"),
        ("em-modes2d-subspace-raw-v1", "array", "mean_group_index", "group_index_length_frame"),
        ("em-modes2d-subspace-raw-v1", "summary", "mean_group_index.values.[].[]", "group_index_length_frame")}
    #: the summary families each exception may match (the spec's losses and group index, l.1746-1748)
    EM_EXCEPTION_FAMILIES = {"propagation_loss": ("propagation_loss", "values"), "bend_loss": ("bend_loss", "values"),
                             "group_index_length_frame": ("mean_group_index", "values")}

    def _em_maps():
        compare = _module("compare")
        return compare, {name: compare.LayoutMap.load(HARNESS / "maps", name)
                         for name in ("em-modes2d-p1-node-centroid-v1", "em-modes2d-subspace-raw-v1")}

    def test_the_em_exception_patterns_are_the_spec_ones():
        """Every exception of the em maps is listed in EM_EXCEPTIONS (and the README), and each
        summary pattern matches the new path of exactly the rule it was written for."""
        compare, maps = _em_maps()
        found = set()
        for name, lmap in maps.items():
            for where, target, rule in lmap.exceptions:
                found.add((name, where, rule["new"], rule["kind"]))
                if where != "summary":
                    assert target == EM_EXCEPTION_FAMILIES[rule["kind"]][0]
                    continue
                hits = [new for _old, news, f, _r in lmap.summary if f != "removed" for new in news if new == target]
                assert len(hits) == 1, (name, rule["new"], hits)
                assert [v for k, v in target if k == "lit"] == list(EM_EXCEPTION_FAMILIES[rule["kind"]])
        assert found == EM_EXCEPTIONS
        readme = (HARNESS / "README.md").read_text(encoding="utf-8")
        for name, where, pattern, kind in EM_EXCEPTIONS:
            assert f"| `{name}` | {where} | `{pattern}` | `{kind}` |" in readme

    def test_the_em_rules_alternatives_and_array_leaves():
        """Alternatives: exactly one new path is present. An array leaf equals its saved array's
        entry on each side; the arrays themselves are compared by their own rule."""
        import numpy as np
        compare = _module("compare")
        lmap = compare.LayoutMap({
            "format": "openphysics-units-batch-map-v1", "old_layout": "old", "new_layout": "new",
            "summary": [{"old": "neff.[]", "new": ["n.values.[]", "n.re.[]"], "f": "="},
                        {"old": "p.value.[]", "f": "array", "part": "real", "old_array": "p",
                         "new": ["q.re.[]", "r.values.[]"], "new_array": ["q", "r"]},
                        {"old": "p.imag.[]", "f": "array", "part": "imag", "old_array": "p", "new": "q.im.[]",
                         "new_array": "q"}],
            "summary_added": ["n.unit", "q.unit"]}, "test")

        def failures(old, new, arrays=None):
            result = compare.Result("doc", "layout")
            compare.compare_trees_layout(old, new, lmap, {}, "summary.json", result, arrays)
            return result.failures
        assert failures({"neff": [1.5]}, {"n": {"unit": "1", "values": [1.5]}}) == []
        assert failures({"neff": [1.5]}, {"n": {"unit": "1", "re": [1.5]}}) == []
        assert failures({"neff": [1.5]}, {"n": {"unit": "1", "values": [1.5], "re": [1.5]}})   # both forms
        old_p = np.array([2.0 + 0.0j, -3.0 + 0.0j])
        new_q = np.conj(old_p) * 1e-12
        arrays = ({"p": old_p}, {"q": new_q})
        tree_old = {"p": {"value": [2.0, -3.0], "imag": [0.0, 0.0]}}
        tree_new = {"q": {"unit": "W", "re": new_q.real.tolist(), "im": new_q.imag.tolist()}}
        assert failures(tree_old, tree_new, arrays) == []
        assert failures(tree_old, {"q": {"unit": "W", "re": [2e-12, -3e-12], "im": [9.0, 0.0]}}, arrays)
        assert failures(tree_old, tree_new, ({"p": old_p}, {"q": new_q * 2}))
        assert failures(tree_old, tree_new)                                   # no arrays: refused
        with pytest.raises(ValueError, match="array rule"):
            compare.LayoutMap({"format": "openphysics-units-batch-map-v1", "old_layout": "o",
                               "summary": [{"old": "a", "new": "b", "f": "array"}]}, "test")

    def test_the_em_call_rules_vtu_and_collection():
        """D-24 renames material names only for the old document's local materials; D-22 maps the
        scalar solve's n_cladding to None and leaves a vector solve alone; imag-conj is a VTU-only
        transform; the collection transform applies to old wavelength sweeps only."""
        import numpy as np
        compare = _module("compare")
        material = ["physmat.Material", "SiO2", ["object", "physmat.dispersion.Constant",
                                                 [["n0", ["num", "float", "0x1.71a9fbe76c8b4p+0"]],
                                                  ["label", "SiO2"]]]]
        renamed = compare._d24_material_names(material, {"SiO2"})
        assert renamed[1] == "oxide" and renamed[2][2][1] == ["label", "oxide"]
        assert compare._d24_material_names(material, set()) == material                 # library SiO2 stays
        rule = {"function": "simcase.physics_em_modes2d.solve", "index": 6, "when": {"index": 5, "equals": "scalar"},
                "new": None}
        scalar = {"function": rule["function"], "args": ["list", ["m", "e", 1, "b", 1, "scalar", 1.444]]}
        vector = {"function": rule["function"], "args": ["list", ["m", "e", 1, "b", 1, "vector", 1.444]]}
        out = compare._apply_call_rules([scalar, vector], {"arguments": [rule]}, ())
        assert out[0]["args"][1][6] is None and out[1]["args"][1][6] == 1.444
        assert scalar["args"][1][6] == 1.444                                              # the record is not changed
        base = {"format": "openphysics-units-batch-map-v1", "old_layout": "o"}
        assert compare.LayoutMap({**base, "vtu": [{"old": "a", "new": "b", "f": "imag-conj"}]}, "t").vtu["a"][1] \
            == "imag-conj"
        with pytest.raises(ValueError, match="closed list"):
            compare.LayoutMap({**base, "arrays": [{"old": "a", "new": "b", "f": "imag-conj"}]}, "t")
        with pytest.raises(ValueError, match="collection"):
            compare.LayoutMap({**base, "collection": "L2"}, "t")
        assert np.negative(np.array([0.0, -2.0])).tobytes() == np.conj(np.array([0j, -2j])).imag.tobytes()

    # The converted examples of the phase-2 specification (section 4.10). Spellings may
    # differ from the converter's (decision D-15); every value must have the same exact value.
    SPEC_EXAMPLES = {
        "thermal_regions": {
            "openphysics": "0.3", "name": "Heated steel plate in insulation",
            "geometry": {"length_unit": "mm", "depth": None,
                         "domain": {"xmin": 0.0, "xmax": 40.0, "ymin": 0.0, "ymax": 20.0},
                         "background": {"material": "insulation"},
                         "shapes": [{"name": "plate", "type": "rect", "x": 5.0, "y": 5.0, "w": 30.0, "h": 6.0,
                                     "material": "steel"},
                                    {"name": "heater", "type": "circle", "cx": 20.0, "cy": 8.0, "r": 2.0,
                                     "material": "copper", "element_size": "0.5 mm"}]},
            "materials": {"steel": {"thermal_conductivity": "45 W/(m K)", "source": "document value"},
                          "copper": {"thermal_conductivity": "400 W/(m K)", "source": "document value"},
                          "insulation": {"thermal_conductivity": "0.04 W/(m K)", "source": "document value"}},
            "physics": {"heat1": {"type": "thermal.steady2d", "heat_source_density": {"heater": "5e6 W/m^3"},
                                  "prescribed_temperature": {"bottom": "300 K"},
                                  "convection": {"top": {"heat_transfer_coefficient": "10 W/(m^2 K)",
                                                         "ambient_temperature": "295 K"}}}},
            "mesh": {"element_size": "2 mm", "minimum_angle": "28 deg"},
            "study": {"type": "single"}, "results": {"save_fields": True, "plots": False}},
        "joule_temperature": {
            "openphysics": "0.3", "name": "Temperature-dependent Joule heated rectangle",
            "geometry": {"length_unit": "m", "depth": None,
                         "domain": {"xmin": 0.0, "xmax": 1.0, "ymin": 0.0, "ymax": 0.2}},
            "materials": {}, "mesh": {"subdivision_count": [24, 6]}, "study": {"type": "single"},
            "results": {"save_fields": True, "plots": False},
            "physics": {"electric": {
                "type": "joule.temperature2d", "prescribed_electric_potential": {"left": "1 V", "right": "0 V"},
                "thermal_conductivity": "1 W/(m K)", "prescribed_temperature": {"left": "300 K", "right": "300 K"},
                "initial_temperature": "300 K",
                "electrical_conductivity": {"model": "linear_resistivity", "reference_conductivity": "2 S/m",
                                            "reference_temperature": "300 K",
                                            "resistivity_temperature_coefficient": "0.01 1/K",
                                            "valid": {"temperature": ["290 K", "400 K"]}},
                "iteration": {"relaxation_factor": 0.5, "temperature_tolerance": "1e-8 K",
                              "relative_tolerance": 1e-10, "iteration_limit": 100}}}},
        "soi_strip": {
            "openphysics": "0.3", "name": "SOI strip waveguide 500 x 220 nm",
            "geometry": {"length_unit": "um", "depth": None,
                         "domain": {"xmin": -1.5, "xmax": 1.5, "ymin": -1.2, "ymax": 1.2},
                         "background": {"material": "physmat:SiO2"},
                         "shapes": [{"name": "core", "type": "rect", "x": -0.25, "y": 0.0, "w": 0.5, "h": 0.22,
                                     "material": "physmat:Si", "element_size": "0.02 um"}]},
            "physics": {"em1": {"type": "em.modes2d", "formulation": "vector", "vacuum_wavelength": "1.55 um",
                                "mode_count": 2, "effective_index_threshold": 1.45,
                                "boundary": {"left": "pec", "right": "pec", "top": "pec", "bottom": "pec"}}},
            "mesh": {"element_size": "0.25 um",
                     "grading": {"position": ["0 um", "0.11 um"], "near": "0.02 um", "far": "0.16 um",
                                 "refinement_distance": "1 um"}},
            "study": {"type": "sweep", "parameter": "physics.em1.vacuum_wavelength",
                      "values": {"unit": "um", "values": [1.4, 1.45, 1.5, 1.55, 1.6, 1.65, 1.7]}}},
    }

    #: soi_strip.json before the units batch (format 0.2; converted by units batch C8)
    SOI_STRIP_02 = {
        "openphysics": "0.2", "name": "SOI strip waveguide 500 x 220 nm", "units": {"length": "um"},
        "geometry": {"domain": {"xmin": -1.5, "xmax": 1.5, "ymin": -1.2, "ymax": 1.2},
                     "background": {"material": "SiO2"},
                     "shapes": [{"name": "core", "type": "rect", "x": -0.25, "y": 0.0, "w": 0.5, "h": 0.22,
                                 "material": "Si", "mesh_size": 0.02}]},
        "physics": {"em1": {"type": "em.modes2d", "formulation": "vector", "wavelength": 1.55, "num_modes": 2,
                            "n_cladding": 1.45,
                            "boundary": {"left": "pec", "right": "pec", "top": "pec", "bottom": "pec"}}},
        "mesh": {"size": 0.25, "grading": {"center": [0.0, 0.11], "near": 0.02, "far": 0.16, "distance": 1.0}},
        "study": {"type": "sweep", "parameter": "physics.em1.wavelength",
                  "values": [1.4, 1.45, 1.5, 1.55, 1.6, 1.65, 1.7]}}

    #: elastic_regions.json before the units batch (format 0.2; converted by units batch C7)
    ELASTIC_REGIONS_02 = {
        "openphysics": "0.2", "name": "Quarter of a thick steel pipe under 10 MPa inner pressure",
        "units": {"length": "mm"},
        "geometry": {"version": 1, "components": {"main": {
            "dimension": "2d", "domain": {"xmin": 0.0, "xmax": 9.0, "ymin": 0.0, "ymax": 9.0},
            "background": {"material": "steel"},
            "features": [{"name": "outside", "type": "rect", "x": 0.0, "y": 0.0, "w": 9.0, "h": 9.0, "material": None},
                         {"name": "wall", "type": "circle", "cx": 0.0, "cy": 0.0, "r": 9.0, "material": "steel"},
                         {"name": "bore", "type": "circle", "cx": 0.0, "cy": 0.0, "r": 3.0, "material": None}],
            "finalize": "later_wins",
            "boundary_tags": [{"tag": "inner", "select": {"boundary": {"of": "bore"}}},
                              {"tag": "outer_wall", "select": {"boundary": {"between": ["wall", "outside"]}}}]}}},
        "materials": {"steel": {"young_modulus_pa": 200000000000.0, "poisson_ratio": 0.3, "source": "document value"}},
        "mesh": {"size": 0.5}, "study": {"type": "single"}, "results": {"save_fields": True, "plots": False},
        "physics": {"pipe": {"type": "mechanics.elasticity2d", "plane": "strain",
                             "displacement_m": {"left": {"x": 0.0}, "bottom": {"y": 0.0}},
                             "pressure_pa": {"inner": 10000000.0}}}}

    def _spec_elastic_regions():
        data = copy.deepcopy(ELASTIC_REGIONS_02)
        data["openphysics"] = "0.3"
        del data["units"]
        main = data["geometry"]["components"]["main"]
        data["geometry"]["components"]["main"] = {"dimension": "2d", "length_unit": "mm", "depth": None,
                                                  **{k: v for k, v in main.items() if k != "dimension"}}
        data["materials"] = {"steel": {"youngs_modulus": "200 GPa", "poisson_ratio": 0.3, "source": "document value"}}
        data["mesh"] = {"element_size": "0.5 mm"}
        data["physics"] = {"pipe": {"type": "mechanics.elasticity2d", "plane": "strain",
                                    "prescribed_displacement": {"left": {"x": "0 mm"}, "bottom": {"y": "0 mm"}},
                                    "gauge_pressure": {"inner": "10 MPa"}}}
        return data

    def _spec_cavity_lossy_slab():
        data = json.loads((ROOT / "examples" / "simcase" / "cavity_lossy_slab.json").read_text(encoding="utf-8"))
        data["openphysics"] = "0.3"
        del data["units"]
        data["geometry"] = {"length_unit": "m", **data["geometry"]}
        data["geometry"]["background"] = {"material": "physmat:vacuum"}
        data["materials"]["lossy_dielectric"]["relative_permittivity"] = {"re": 4.0, "im": 0.04}
        data["physics"]["em1"] = {"type": "em.cavity3d", "boundary": {"electrical_conductivity": "58 MS/m"},
                                  "search": "near_target", "target_frequency": "150 MHz", "mode_count": 3}
        data["mesh"] = {"subdivision_count": [8, 8, 8]}
        return data

    def _same_document(expected, actual, quantities, path=""):
        """Equal structure; a quantity string equal by exact value in its quantity (D-15)."""
        import physmat.units as units
        if isinstance(expected, dict) and set(expected) == {"unit", "values"} and isinstance(actual, dict):
            factor = lambda u: units.convert(f"1 {u}", "length").exact                       # noqa: E731
            assert [Fraction(repr(v)) * factor(expected["unit"]) for v in expected["values"]] == \
                [Fraction(repr(v)) * factor(actual["unit"]) for v in actual["values"]], path
            return
        if isinstance(expected, dict):
            assert isinstance(actual, dict) and set(expected) == set(actual), (path, sorted(expected), actual)
            for k in expected:
                _same_document(expected[k], actual[k], quantities, f"{path}.{k}" if path else k)
        elif isinstance(expected, list):
            assert isinstance(actual, list) and len(expected) == len(actual), path
            for i, (x, y) in enumerate(zip(expected, actual)):
                _same_document(x, y, quantities, f"{path}[{i}]")
        elif isinstance(expected, str) and path in quantities:
            a, b = units.convert(expected, quantities[path]), units.convert(actual, quantities[path])
            assert a.ok and b.ok and a.exact == b.exact, (path, expected, actual)
        else:
            assert expected == actual and type(expected) is type(actual), (path, expected, actual)

    #: joule_temperature.json before the units batch (format 0.2; converted by units batch C6)
    JOULE_TEMPERATURE_02 = {
        "openphysics": "0.2", "name": "Temperature-dependent Joule heated rectangle",
        "units": {"length": "m", "temperature": "K"},
        "geometry": {"domain": {"xmin": 0.0, "xmax": 1.0, "ymin": 0.0, "ymax": 0.2}}, "materials": {},
        "mesh": {"subdivisions": [24, 6]}, "study": {"type": "single"},
        "results": {"save_fields": True, "plots": False},
        "physics": {"electric": {
            "type": "joule.temperature2d", "dirichlet_potential_v": {"left": 1.0, "right": 0.0},
            "thermal_conductivity_w_mk": 1.0, "dirichlet_temperature_k": {"left": 300.0, "right": 300.0},
            "initial_temperature_k": 300.0,
            "conductivity_model": {"type": "linear_resistivity", "reference_conductivity_s_m": 2.0,
                                   "reference_temperature_k": 300.0, "alpha_per_k": 0.01,
                                   "temperature_range_k": [290.0, 400.0]},
            "iteration": {"relaxation": 0.5, "temperature_atol_k": 1e-08, "relative_tolerance": 1e-10,
                          "max_iterations": 100}}}}

    #: thermal_regions.json before the units batch (format 0.2; converted by units batch C5b)
    THERMAL_REGIONS_02 = {
        "openphysics": "0.2", "name": "Heated steel plate in insulation", "units": {"length": "mm", "temperature": "K"},
        "geometry": {"domain": {"xmin": 0.0, "xmax": 40.0, "ymin": 0.0, "ymax": 20.0},
                     "background": {"material": "insulation"},
                     "shapes": [{"name": "plate", "type": "rect", "x": 5.0, "y": 5.0, "w": 30.0, "h": 6.0,
                                 "material": "steel"},
                                {"name": "heater", "type": "circle", "cx": 20.0, "cy": 8.0, "r": 2.0,
                                 "material": "copper", "mesh_size": 0.5}]},
        "materials": {"steel": {"conductivity_w_mk": 45.0, "source": "document value"},
                      "copper": {"conductivity_w_mk": 400.0, "source": "document value"},
                      "insulation": {"conductivity_w_mk": 0.04, "source": "document value"}},
        "physics": {"heat1": {"type": "thermal.steady2d", "heat_source_w_m3": {"heater": 5000000.0},
                              "dirichlet_temperature_k": {"bottom": 300.0},
                              "convection": {"top": {"h_w_m2k": 10.0, "ambient_temperature_k": 295.0}}}},
        "mesh": {"size": 2.0, "min_angle": 28.0}, "study": {"type": "single"},
        "results": {"save_fields": True, "plots": False}}

    @pytest.mark.parametrize("name", ["thermal_regions", "joule_temperature", "soi_strip", "elastic_regions",
                                      "cavity_lossy_slab"])
    def test_the_converter_reproduces_the_converted_examples_of_the_specification(name):
        convert = _module("convert_v02")
        expected = (SPEC_EXAMPLES.get(name) or {"elastic_regions": _spec_elastic_regions,
                                                  "cavity_lossy_slab": _spec_cavity_lossy_slab}[name]())
        frozen = {"thermal_regions": THERMAL_REGIONS_02, "joule_temperature": JOULE_TEMPERATURE_02,
                  "elastic_regions": ELASTIC_REGIONS_02, "soi_strip": SOI_STRIP_02}
        old = copy.deepcopy(frozen[name]) if name in frozen else \
            json.loads((ROOT / "examples" / "simcase" / f"{name}.json").read_text(encoding="utf-8"))
        new, writer = convert.convert(old)
        assert convert.check(writer) == []
        quantities = {path: quantity for path, _text, quantity, _ in writer.expected}
        _same_document(expected, new, quantities)

    def _documents_02():
        """Every 0.2 document of the corpus: the examples still in 0.2 and the 0.2 fixtures. A
        converted example's 0.2 source is checked at the baseline (``test_converted_documents_
        resolve_to_the_converter_output``)."""
        examples = [p for p in sorted((ROOT / "examples" / "simcase").glob("*.json"))
                    if json.loads(p.read_text(encoding="utf-8"))["openphysics"] == "0.2"]
        return examples + sorted((HARNESS / "fixtures" / "v02").glob("*.json"))

    def test_the_converter_resolves_every_example_and_fixture_to_its_old_values():
        """Every written quantity reads back through physmat.units to the old value (the SI double
        of a unit-suffixed key, the exact old length), counts are integers, and the only accept is
        the manufactured c = 4 J/(m^3 K) of the sampled rectangle fixture (transient_thermal_uniform,
        the other one, is in format 0.3 since units batch C5a)."""
        convert = _module("convert_v02")
        accepted = []
        for path in _documents_02():
            new, writer = convert.convert(json.loads(path.read_text(encoding="utf-8")))
            assert new["openphysics"] == "0.3" and "units" not in new
            assert convert.check(writer) == [], path.name
            accepted += [(path.stem, note) for note in writer.notes if "accept" in note]
        assert sorted(accepted) == [(stem, "physics.heat1.volumetric_heat_capacity: 4 J/(m^3 K) is outside "
                                            "the plausibility band; written with accept")
                                    for stem in ("heat_transient_rectangle_sampled",)]

    #: thermal_boundary.json before the units batch (format 0.2), for the converter's sign rule
    THERMAL_BOUNDARY_02 = {
        "openphysics": "0.2", "name": "Steady additive outward flux and convection",
        "units": {"length": "m", "temperature": "K"},
        "geometry": {"domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}}, "materials": {},
        "physics": {"heat1": {"type": "thermal.steady2d", "conductivity_w_mk": 2, "heat_source_w_m3": 0,
                              "dirichlet_temperature_k": {"left": 300}, "outward_flux_w_m2": {"right": 2},
                              "convection": {"right": {"h_w_m2k": 4, "ambient_temperature_k": 290}}}},
        "mesh": {"subdivisions": [8, 8]}, "study": {"type": "single"},
        "results": {"save_fields": True, "plots": False}}

    def test_the_converter_negates_the_outward_inputs_and_conjugates_the_cavity():
        convert = _module("convert_v02")
        boundary = copy.deepcopy(THERMAL_BOUNDARY_02)
        new, _ = convert.convert(boundary)
        assert new["physics"]["heat1"]["inward_heat_flux"] == {"right": "-2 W/m^2"}
        assert "outward_flux_w_m2" not in new["physics"]["heat1"]
        fixture = HARNESS / "fixtures" / "v02" / "electric_current_terminal.json"
        new, _ = convert.convert(json.loads(fixture.read_text(encoding="utf-8")))
        assert new["physics"]["e"]["inward_current_density"] == {"inner": "10 A/m^2"}
        fixture = HARNESS / "fixtures" / "v02" / "cavity_complex_permeability.json"
        new, _ = convert.convert(json.loads(fixture.read_text(encoding="utf-8")))
        assert new["materials"]["lossy_dielectric"]["relative_permeability"] == {"re": 1.5, "im": 0.01}
        fixture = HARNESS / "fixtures" / "v02" / "em_sellmeier_open_lower_bound.json"
        new, _ = convert.convert(json.loads(fixture.read_text(encoding="utf-8")))
        assert new["materials"]["glass"]["refractive_index"]["valid"] == {"vacuum_wavelength": [None, "6.7 um"]}
        with pytest.raises(convert.ConversionError, match="not in the conversion table"):
            convert.convert({**boundary, "physics": {"heat1": {**boundary["physics"]["heat1"], "colour": "red"}}})

    def _git(*args, cwd=ROOT) -> str:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                              check=True).stdout.strip()

    def _kind(path: Path) -> str:
        data = json.loads(path.read_text(encoding="utf-8"))
        (kind,) = {p["type"] for p in data["physics"].values()}
        return kind

    def _mode(corpus: dict, path: Path) -> str:
        """The corpus mode of a 0.2 document: per physics type, or per geometry form of that type."""
        mode = corpus["modes"][_kind(path)]
        if isinstance(mode, dict):
            geometry = json.loads(path.read_text(encoding="utf-8"))["geometry"]
            form = ("v1" if "version" in geometry else
                    "regions" if "background" in geometry or "shapes" in geometry else "rect")
            mode = mode[form]
        return mode

    def test_the_corpus_modes_name_every_form():
        corpus = json.loads((HARNESS / "maps" / "corpus.json").read_text(encoding="utf-8"))
        for kind, mode in corpus["modes"].items():
            modes = mode.values() if isinstance(mode, dict) else [mode]
            assert set(modes) <= {"identity", "layout"}, kind
            if isinstance(mode, dict):
                assert set(mode) == {"rect", "regions", "v1"}, kind

    def _si_tree(document):
        """The resolved SI tree of a 0.3 document: float.hex of every number, pm of every shape number."""
        from simcase.resolve import resolve_tree

        def canonical(node):
            if isinstance(node, dict):
                return {k: canonical(v) for k, v in node.items()}
            if isinstance(node, list):
                return [canonical(v) for v in node]
            if isinstance(node, float):
                return float.hex(node)
            return node
        result = resolve_tree(document)
        assert not result.diagnostics.errors, [d.as_dict() for d in result.diagnostics.errors]
        return canonical(result.si), dict(result.pm)

    @pytest.mark.skipif(not os.environ.get("OPENPHYSICS_BATCH_BASELINE"),
                        reason="not run: P2-2 runs only when OPENPHYSICS_BATCH_BASELINE names the baseline commit "
                               "(the merge base with main); see tools/units_batch/README.md")
    def test_converted_documents_resolve_to_the_converter_output():
        """P2-2: every document compared in layout mode, as committed, resolves to the SI tree (float.hex
        of every value, pm of every shape number) of convert_v02 of its 0.2 source: the example at the
        baseline, or the fixtures/v02 document. The accept annotation is the only allowed difference
        (D-15 spellings resolve to the same values)."""
        baseline = _git("rev-parse", "--verify", os.environ["OPENPHYSICS_BATCH_BASELINE"] + "^{commit}")
        corpus = json.loads((HARNESS / "maps" / "corpus.json").read_text(encoding="utf-8"))
        convert = _module("convert_v02")
        pairs = []
        for path in sorted((ROOT / "examples" / "simcase").glob("*.json")):
            old = json.loads(_git("show", f"{baseline}:examples/simcase/{path.name}"))
            stem = path.stem
            pairs.append((stem, old, json.loads(path.read_text(encoding="utf-8"))))
        for path in sorted((HARNESS / "fixtures" / "v02").glob("*.json")):
            twin = HARNESS / "fixtures" / "v03" / path.name
            pairs.append((path.stem, json.loads(path.read_text(encoding="utf-8")),
                          json.loads(twin.read_text(encoding="utf-8")) if twin.is_file() else None))
        checked = 0
        for stem, old, new in pairs:
            kind = {p["type"] for p in old["physics"].values()}.pop()
            mode = corpus["modes"][kind]
            if isinstance(mode, dict):
                g = old["geometry"]
                mode = mode["v1" if "version" in g else "regions" if "background" in g or "shapes" in g else "rect"]
            if mode != "layout":
                continue
            converted, writer = convert.convert(old)
            assert convert.check(writer) == [], stem
            assert _si_tree(new) == _si_tree(converted), stem
            checked += 1
        print(f"P2-2: {checked} documents resolve to the converter output")
        assert checked > 0

    #: The eight nanometre and metre em fixtures and their micrometre twins. They are compared
    #: under the pre-registered rules and reported as different: their old run post-processed in
    #: the document unit, the new one in the micrometre kernel frame (spec §3.8). This stated
    #: deviation (README) is checked by the substitute checks below, never counted as a pass.
    NM_M_TWINS = {f"em_length_{unit}_{name}": twin for unit in ("nm", "m")
                  for name, twin in (("fiber", "fiber"), ("sellmeier_rib", "em_sellmeier_range"),
                                     ("vector_slab", "vector_slab"),
                                     ("subspace_sweep", "vector_fiber_subspace_sweep"))}
    #: (v) the only differences the eight may show, old against new: the post-processing calls
    #: and the arrays, summary leaves and VTU points that depend on the document unit
    NM_M_ALLOWED = (
        r"calls\[\d+\] galerkin\.mode_overlap\.\w+\.",
        r"calls\[\d+\] galerkin\.assembly\.assemble_mass\.",
        r"export (fields\.vtu|sweep/fields_\d+\.vtu) points differ$",
        r"fields\.npz (confinement -> confinement_factor|field_overlap -> unnormalized_field_overlap"
        r"|mode_power -> unnormalized_mode_(power|field_square_integral)|nodes -> node_coordinates"
        r"|values -> vacuum_wavelength|(vector|raw)_transverse -> unnormalized_electric_field_line_integral) \(",
        r"fields\.npz mean_group_index \(group_index_length_frame\): \d+ ulp",
        r"summary\.json (cluster_mean_group_index|mode_postprocessing\.confinement\.value|study\.values)\[")

    def _postprocessing_free(calls):
        """The recorded calls without the post-processing ones (``galerkin.mode_overlap.*`` and the
        calls they make, recorded after them at a greater depth)."""
        out, skip_below = [], None
        for call in calls:
            if skip_below is not None and call["depth"] > skip_below:
                continue
            skip_below = None
            if call["function"].startswith("galerkin.mode_overlap."):
                skip_below = call["depth"]
                continue
            out.append(call)
        return out

    def _nm_m_substitute_checks(rec_old: Path, rec_new: Path, report: dict) -> list[str]:
        """The substitute checks of the stated deviation (README): (i) to (v). Returns the
        measured maxima, old against new, reported and never turned into a bound."""
        import re
        import numpy as np
        compare = _module("compare")
        compare.MAX_FAILURES = 10 ** 6
        status = {d["id"]: d["status"] for d in report["documents"]}
        lines = []
        for doc, twin in sorted(NM_M_TWINS.items()):
            old_record = json.loads((rec_old / doc / "record.json").read_text(encoding="utf-8"))
            new_record = json.loads((rec_new / doc / "record.json").read_text(encoding="utf-8"))
            # (i) mesher, material, kernel-solve, eigensolver and tracker calls, bitwise
            result = compare.Result(doc, "layout")
            compare.compare_calls({"calls": _postprocessing_free(old_record["calls"])},
                                  {"calls": _postprocessing_free(new_record["calls"])}, result)
            assert result.equal, (doc, "(i)", result.failures[:5])
            # (ii) node_coordinates: the recorded micrometre mesher nodes times 1e-6 (spec l.1749)
            kernel = np.load(rec_old / doc / "mesher_outputs.npz")
            last = max(int(k.split("_")[1]) for k in kernel.files if k.startswith("nodes_"))
            new_arrays = dict(np.load(rec_new / doc / "result" / "fields.npz"))
            assert (kernel[f"nodes_{last}"] * 1e-6).tobytes() == new_arrays["node_coordinates"].tobytes(), (doc, "(ii)")
            # (iii) the new run equals the new run of its micrometre twin, array by array
            twin_arrays = dict(np.load(rec_new / twin / "result" / "fields.npz"))
            assert set(new_arrays) == set(twin_arrays), (doc, "(iii)")
            for key in new_arrays:
                if key != "metadata_json":
                    a, b = new_arrays[key], twin_arrays[key]
                    assert a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes(), (doc, key)
            skip = {"name", "resolved_inputs", "extent", "diagnostics", "defaults_applied"}
            trees = [json.loads((rec_new / d / "result" / "summary.json").read_text(encoding="utf-8")) for d in (doc, twin)]
            trees += [json.loads(str(new_arrays["metadata_json"])), json.loads(str(twin_arrays["metadata_json"]))]
            for x, y in ((trees[0], trees[1]), (trees[2], trees[3])):
                a = {p: v for p, v in compare.leaves(x).items() if p[0] not in skip}
                b = {p: v for p, v in compare.leaves(y).items() if p[0] not in skip}
                assert a.keys() == b.keys() and all(compare._hex(a[p]) == compare._hex(b[p]) if
                                                    compare._hex(a[p]) is not None else a[p] == b[p] for p in a), \
                    (doc, "(iii) summary")
            twin_record = json.loads((rec_new / twin / "record.json").read_text(encoding="utf-8"))
            assert new_record["export"] == twin_record["export"], (doc, "(iii) VTU")
            # (iv) the twin passes the comparison
            assert status[twin] == "equal", (twin, "(iv)")
            # (v) every difference from the old run is on the listed set
            found = compare.compare_document(doc, rec_old / doc, rec_new / doc, "layout", HARNESS / "maps")
            assert not found.equal
            stray = [f for f in found.failures if not any(re.match(p, f) for p in NM_M_ALLOWED)]
            assert not stray, (doc, "(v)", stray[:5])
            # the measured differences, old against new (reported only)
            old_arrays = dict(np.load(rec_old / doc / "result" / "fields.npz"))
            unit = float(old_arrays["length_unit_to_m"])
            measured = []
            for old_key, new_key, power in (("vector_transverse", "unnormalized_electric_field_line_integral", 1),
                                            ("raw_transverse", "unnormalized_electric_field_line_integral", 1),
                                            ("mode_power", "unnormalized_mode_power", 2),
                                            ("mode_power", "unnormalized_mode_field_square_integral", 2),
                                            ("field_overlap", "unnormalized_field_overlap", 2)):
                if old_key in old_arrays and new_key in new_arrays:
                    old_si, new = np.conj(old_arrays[old_key]) * unit ** power, new_arrays[new_key]
                    measured.append(f"{old_key} {np.max(np.abs(old_si - new)) / np.max(np.abs(new)):.2e} relative")
            for old_key, new_key in (("confinement", "confinement_factor"),
                                     ("cluster_mean_group_index", "mean_group_index")):
                if old_key in old_arrays:
                    pairs = zip(old_arrays[old_key].ravel(), new_arrays[new_key].ravel())
                    ulps = max((compare.ulp_distance(float(x), float(y)) for x, y in pairs
                                if np.isfinite(x) and np.isfinite(y)), default=0)
                    measured.append(f"{old_key} {ulps:.0f} ulp")
            measured.append(f"values {float(old_arrays['values'][0])!r} (document unit) against "
                            f"{float(new_arrays['vacuum_wavelength'][0])!r} m")
            lines.append(f"{doc}: " + "; ".join(measured))
        return lines

    @pytest.mark.skipif(not os.environ.get("OPENPHYSICS_BATCH_BASELINE"),
                        reason="not run: P2-1 runs only when OPENPHYSICS_BATCH_BASELINE names the baseline commit "
                               "(the merge base with main); see tools/units_batch/README.md")
    def test_units_batch_equivalence(tmp_path):
        baseline = _git("rev-parse", "--verify", os.environ["OPENPHYSICS_BATCH_BASELINE"] + "^{commit}")
        head = _git("rev-parse", "HEAD")
        corpus = json.loads((HARNESS / "maps" / "corpus.json").read_text(encoding="utf-8"))
        base = tmp_path / "base"
        _git("worktree", "add", "--detach", str(base), baseline)
        try:
            old_examples = {p.stem: p for p in sorted((base / "examples" / "simcase").glob("*.json"))}
            new_examples = {p.stem: p for p in sorted((ROOT / "examples" / "simcase").glob("*.json"))}
            assert sorted(old_examples) == sorted(new_examples), "the examples differ between baseline and head"
            old_docs, new_docs, plan = [], [], {}
            for stem, path in old_examples.items():
                mode = _mode(corpus, path)
                old_docs.append(f"{stem}={path}")
                new_docs.append(f"{stem}={new_examples[stem]}")
                plan[stem] = mode
            for path in sorted((HARNESS / "fixtures" / "v02").glob("*.json")):
                mode = _mode(corpus, path)
                twin = HARNESS / "fixtures" / "v03" / path.name if mode == "layout" else path
                assert twin.is_file(), f"{path.stem}: its kind is compared by layout but has no fixtures/v03 twin"
                old_docs.append(f"{path.stem}={path}")
                new_docs.append(f"{path.stem}={twin}")
                plan[path.stem] = mode
            lists = {}
            for side, docs in (("old", old_docs), ("new", new_docs)):
                lists[side] = tmp_path / f"{side}.txt"
                lists[side].write_text("\n".join(docs) + "\n", encoding="utf-8")
            (tmp_path / "plan.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
            for side, root in (("old", base), ("new", ROOT)):
                done = subprocess.run([sys.executable, "-I", str(HARNESS / "record.py"), "--root", str(root),
                                       "--out", str(tmp_path / f"rec_{side}"), "--docs", str(lists[side])],
                                      capture_output=True, text=True, encoding="utf-8", errors="replace",
                                      env=_env(), timeout=4 * 3600)
                print(done.stdout)
                assert done.returncode == 0, done.stdout + done.stderr
            report = tmp_path / "report.json"
            result = _compare(tmp_path / "rec_old", tmp_path / "rec_new", "--plan", str(tmp_path / "plan.json"),
                              report=report)
            print(f"baseline {baseline}, head {head}, {len(plan)} documents")
            print(result.stdout)
            evidence = os.environ.get("OPENPHYSICS_BATCH_REPORT")
            if evidence:
                folder = Path(evidence)
                folder.mkdir(parents=True, exist_ok=True)
                shutil.copy2(report, folder / "report.json")
                shutil.copy2(tmp_path / "plan.json", folder / "plan.json")
                for side in ("old", "new"):
                    shutil.copy2(tmp_path / f"rec_{side}" / "manifest.json", folder / f"manifest_{side}.json")
                (folder / "compare.txt").write_text(f"baseline {baseline}\nhead {head}\n" + result.stdout,
                                                    encoding="utf-8")
            # every document compares equal except the eight nanometre and metre em fixtures of
            # the stated deviation, which are reported as different and checked by substitutes
            data = json.loads(report.read_text(encoding="utf-8"))
            assert not data["problems"], data["problems"]
            different = sorted(d["id"] for d in data["documents"] if d["status"] != "equal")
            assert different == sorted(NM_M_TWINS), result.stdout
            total = len(data["documents"])
            assert f"{total} documents compared: {total - 8} equal, 8 different" in result.stdout, result.stdout
            measured = _nm_m_substitute_checks(tmp_path / "rec_old", tmp_path / "rec_new", data)
            print("stated deviation, nanometre and metre em fixtures (substitute checks i-v passed); measured, "
                  "old against new:\n" + "\n".join(measured))
            # the exception patterns match only the spec's leaves in the em corpus
            compare, maps = _em_maps()
            for d in data["documents"]:
                record = json.loads((tmp_path / "rec_new" / d["id"] / "record.json").read_text(encoding="utf-8"))
                summary = tmp_path / "rec_new" / d["id"] / "result" / "summary.json"
                if record.get("load", {}).get("kind") != "em.modes2d" or not summary.exists():
                    continue
                for path in compare.leaves(json.loads(summary.read_text(encoding="utf-8"))):
                    for lmap in maps.values():
                        for where, target, rule in lmap.exceptions:
                            if where == "summary" and compare.match(target, path) is not None:
                                assert path[:2] == EM_EXCEPTION_FAMILIES[rule["kind"]], (d["id"], path)
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(base)], cwd=ROOT, capture_output=True)
            subprocess.run(["git", "worktree", "prune"], cwd=ROOT, capture_output=True)
