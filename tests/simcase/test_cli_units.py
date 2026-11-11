# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The command line on format 0.3 documents (units batch C4, checks P2-9 and P2-13 in part).

``simcase validate`` and ``run`` print each component's extent line and every diagnostic;
``--json`` gives the same as JSON, ``--strict`` refuses unacknowledged warnings and assumed
library data; ``explain`` lists every input with its SI value; ``fix`` applies only the fixes
that keep the value, token by token. Tested on the test-only kind of ``units_toy_kind`` (no
built-in kind reads format 0.3 yet), in process: this checkout's packages need not be
installed. Also the common result helpers and the VTU unit metadata.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
from physmat import units

from simcase import export, reader, results_common
from simcase.cli import main
from simcase.resolve import resolve_text

import units_toy_kind as toy

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def toy_kind():
    with toy.registered():
        yield


def _write(tmp_path, data, name="model.json"):
    path = tmp_path / name
    path.write_text(toy.text(data), encoding="utf-8")
    return path


def _run(capsys, *argv):
    code = main([str(a) for a in argv])
    out, err = capsys.readouterr()
    return code, out, err


#: a document with every diagnostic of the shared reader that the kinds keep (P2-9)
NOISY = dict(
    geometry__shapes=[{"name": "core", "type": "rect", "x": 0.30000000000000004, "y": 5, "w": 30,
                       "h": 6.0000000001, "material": "steel"}],
    materials={"steel": {"youngs_modulus": "200 GPa", "poisson_ratio": 0.3, "thermal_conductivity": "45 W/(m K)"}},
    physics={"bar": {"type": "toy.bar", "youngs_modulus": {"value": "200 kPa", "accept": {"W-MAGNITUDE": "a foam"}},
                     "poisson_ratio": 0.3, "gauge_pressure": "95 kPa",
                     "prescribed_temperature": {"left": "300 K"}, "ambient_temperature": "25 K",
                     "boundary": {"left": "fixed"}}})
EXPECTED = [("I-PM-ROUNDING", "geometry.shapes[0].x"), ("W-PM-ROUNDING", "geometry.shapes[0].h"),
            ("W-MAGNITUDE", "physics.bar.youngs_modulus.value"), ("W-GAUGE-ATMOSPHERIC", "physics.bar.gauge_pressure"),
            ("I-UNUSED-PROPERTY", "materials.steel.thermal_conductivity"),
            ("I-DEFAULT-BOUNDARY", "physics.bar.boundary.right"),
            ("W-CELSIUS-AS-KELVIN", "physics.bar.ambient_temperature")]


def _pairs(diagnostics):
    return [(d["code"], d["path"]) if isinstance(d, dict) else (d.code, d.path) for d in diagnostics]


def test_validate_prints_extent_summary_and_every_diagnostic(toy_kind, tmp_path, capsys):
    path = _write(tmp_path, toy.document(**NOISY))
    code, out, _err = _run(capsys, "validate", path)
    assert code == 0
    lines = out.splitlines()
    assert lines[0].startswith("geometry (length_unit mm): 40 mm x 20 mm = 0.04 m x 0.02 m; depth per metre (null); "
                               "element_size 2 mm, about")
    assert lines[1] == "toy bar  (openphysics 0.3, toy.bar)"
    for code_, where in EXPECTED:
        assert any(line.startswith(f"{'info' if code_[0] == 'I' else 'warning'} {code_} at {where}") for line in lines)
    assert "  Acknowledged: a foam" in lines


def test_validate_json_has_the_five_keys(toy_kind, tmp_path, capsys):
    path = _write(tmp_path, toy.document(**NOISY))
    code, out, _err = _run(capsys, "validate", "--json", path)
    report = json.loads(out)
    assert code == 0 and set(report) == {"valid", "extent", "diagnostics", "defaults_applied", "resolved_inputs"}
    assert report["valid"] is True and len(report["extent"]) == 1
    assert sorted(_pairs(report["diagnostics"])) == sorted(EXPECTED)
    acknowledged = [d for d in report["diagnostics"] if d["acknowledged"]]
    assert _pairs(acknowledged) == [("W-MAGNITUDE", "physics.bar.youngs_modulus.value")]
    assert report["resolved_inputs"]["geometry.domain.xmax"] == {"authored": 40, "value": 0.04, "unit": "m",
                                                                 "length_unit": "mm"}


def test_the_exit_codes(toy_kind, tmp_path, capsys):
    clean = _write(tmp_path, toy.document(), "clean.json")
    noisy = _write(tmp_path, toy.document(**NOISY), "noisy.json")
    acknowledged = _write(tmp_path, toy.document(physics__bar__youngs_modulus={
        "value": "200 kPa", "accept": {"W-MAGNITUDE": "a foam"}}), "acknowledged.json")
    library = _write(tmp_path, toy.document(geometry__background={"material": "physmat:Si3N4"}), "library.json")
    broken = _write(tmp_path, toy.document(mesh={"element_size": 2}), "broken.json")
    assert _run(capsys, "validate", clean)[0] == 0
    assert _run(capsys, "validate", "--strict", clean)[0] == 0
    assert _run(capsys, "validate", noisy)[0] == 0
    assert _run(capsys, "validate", "--strict", noisy)[0] == 3
    assert _run(capsys, "validate", "--strict", acknowledged)[0] == 0
    assert _run(capsys, "validate", library)[0] == 0
    code, out, _ = _run(capsys, "validate", "--strict", library)
    assert code == 3 and "info I-DATUM-ASSUMED at geometry.background.material" in out
    code, out, _ = _run(capsys, "validate", broken)
    assert code == 2 and "error E-UNIT-MISSING at mesh.element_size" in out
    assert _run(capsys, "validate", tmp_path / "missing.json")[0] == 2
    (tmp_path / "bad.json").write_text('{"openphysics": "0.3", "name": NaN}', encoding="utf-8")
    code, out, _ = _run(capsys, "validate", tmp_path / "bad.json")
    assert code == 2 and "E-JSON" in out


def test_run_prints_and_keeps_every_diagnostic(toy_kind, tmp_path, capsys):
    path = _write(tmp_path, toy.document(**NOISY))
    out_dir = tmp_path / "out"
    code, out, err = _run(capsys, "run", path, "-o", out_dir)
    assert code == 0, err
    for code_, where in EXPECTED:
        assert f"{code_} at {where}" in out
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert sorted(_pairs(summary["diagnostics"])) == sorted(EXPECTED)
    assert summary["extent"] == [line for line in out.splitlines() if line.startswith("geometry (")]
    assert summary["timing"]["wall_time"]["mesh"] == {"value": 0.0, "unit": "s"}
    assert {d["path"] for d in summary["defaults_applied"]} >= {"mesh.minimum_angle", "physics.bar.mode_count"}
    log = (out_dir / "log.txt").read_text(encoding="utf-8").splitlines()
    assert log[0] == summary["extent"][0] and log[1].startswith("toy bar")
    for code_, where in EXPECTED:
        assert any(line.endswith(f"{code_} at {where}") for line in log)
    assert (out_dir / "model.json").read_bytes() == path.read_bytes()


def test_run_refuses_errors_and_strict_warnings(toy_kind, tmp_path, capsys):
    noisy = _write(tmp_path, toy.document(**NOISY), "noisy.json")
    code, _out, err = _run(capsys, "run", "--strict", noisy, "-o", tmp_path / "a")
    assert code == 3 and "refused under --strict" in err and not (tmp_path / "a").exists()
    broken = _write(tmp_path, toy.document(physics__bar__youngs_modulus="2000 GPa"), "broken.json")
    code, _out, err = _run(capsys, "run", broken, "-o", tmp_path / "b")
    assert code == 2 and f"error: {toy.STIFF.format(name='bar')}" in err


def test_explain_lists_every_input_once(toy_kind, tmp_path, capsys):
    path = _write(tmp_path, toy.document(**NOISY))
    code, out, _err = _run(capsys, "explain", "--json", path)
    rows = json.loads(out)
    result = resolve_text(path.read_bytes())
    inputs = result.document().resolved_inputs()
    authored = [r for r in rows if not r["default"]]
    defaults = [r for r in rows if r["default"]]
    assert code == 0 and [r["path"] for r in authored] == list(inputs)
    assert len({r["path"] for r in rows}) == len(rows)
    assert [r["path"] for r in defaults] == [d["path"] for d in result.defaults_applied]
    for row in authored:
        assert {k: v for k, v in row.items() if k not in ("default", "path")} == \
            json.loads(reader.dumps(inputs[row["path"]]))
    shapes = [r for r in authored if r["path"].startswith("geometry.domain") or r["path"].startswith("geometry.shapes")
              and r["path"].rsplit(".", 1)[1] in "xywh"]
    assert shapes and all(r["length_unit"] == "mm" and r["unit"] == "m" for r in shapes)
    angle = next(r for r in defaults if r["path"] == "mesh.minimum_angle")
    assert angle["default_value"] == "28 deg" and angle["unit"] == "rad"
    assert angle["value"] == units.convert("28 deg", "minimum_angle").value
    code, out, _err = _run(capsys, "explain", path)
    assert code == 0 and "geometry.domain.xmax: 40 = 0.04 m  (length_unit mm)" in out.splitlines()


FIXABLE = """{
  "openphysics": "0.3",
  "name": "fix me",
  "geometry": {"length_unit": "mm", "depth": null,
               "domain": {"xmin": 0, "xmax": 40, "ymin": 0, "ymax": 20}},
  "materials": {"steel": {"linear_expansion_coefficient":   "12 ppm/degC", "youngs_modulus": "200 GPa"}},
  "physics": {"bar": {"type": "toy.bar", "ambient_temperature": "25K",
                      "gauge_pressure": "10 mPa", "mode_count": 2.0}},
  "mesh": {"element_size": "1 µm", "subdivision_count": [4, 2]}
}
"""


def test_fix_applies_only_value_preserving_fixes(toy_kind, tmp_path, capsys):
    path = tmp_path / "model.json"
    raw = FIXABLE.replace("\n", "\r\n").encode("utf-8")
    path.write_bytes(raw)
    code, out, err = _run(capsys, "fix", path)
    expected = (FIXABLE.replace('"12 ppm/degC"', '"12 ppm/K"').replace('"25K"', '"25 K"')
                .replace('"1 µm"', '"1 um"').replace('"mode_count": 2.0', '"mode_count": 2')
                .replace("\n", "\r\n").encode("utf-8"))
    assert code == 0 and out.encode("utf-8").replace(b"\n", b"\r\n").replace(b"\r\r\n", b"\r\n") == expected
    assert "10 mPa" in out and "not applied: physics.bar.gauge_pressure" in err
    assert len([line for line in err.splitlines() if line.startswith("fixed ")]) == 4
    assert path.read_bytes() == raw                      # without --in-place nothing is written
    before, after = resolve_text(raw), resolve_text(expected)
    from simcase.fix import _si_leaves
    old, new = _si_leaves(before.si), _si_leaves(after.si)
    assert old and all(new[p] == v for p, v in old.items())
    assert new["physics.bar.ambient_temperature"] == float.hex(25.0)
    assert [d.code for d in after.diagnostics if d.severity == "error"] == ["E-UNIT-NOT-ACCEPTED"]
    code, out, _err = _run(capsys, "fix", "--in-place", path)
    assert code == 0 and path.read_bytes() == expected and "4 fix(es) written" in out


#: a format 0.2 document: no kind reads one since units batch C9 (em.cavity3d was the last)
V02 = ROOT / "tools" / "units_batch" / "fixtures" / "v02" / "cavity_wall_conductivity.json"


def test_fix_and_explain_refuse_a_0_2_document(tmp_path, capsys):
    for command in ("fix", "explain"):
        code, _out, err = _run(capsys, command, V02)
        assert code == 2 and "reads format 0.3 documents" in err


def test_validate_of_a_0_2_document_names_the_format(capsys):
    code, out, err = _run(capsys, "validate", V02)
    assert code == 2 and out == "" and "format 0.2 em.cavity3d documents are not read" in err
    code, out, _err = _run(capsys, "validate", "--json", V02)
    report = json.loads(out)
    assert code == 2 and report["valid"] is False
    assert [(d["code"], d["path"]) for d in report["diagnostics"]] == [("E-FORMAT", "openphysics")]


# -- the common result helpers --------------------------------------------------------------------

def test_value_objects_carry_registry_units():
    assert results_common.value_object(2e11, "youngs_modulus") == {"value": 2e11, "unit": "Pa"}
    assert results_common.value_object(math.inf, "temperature") == {"value": None, "unit": "K"}
    assert results_common.tagged_array([0, 0.5], "time") == {"unit": "s", "values": [0.0, 0.5]}
    assert results_common.complex_value(1 + 2j, "effective_index") == {
        "re": 1.0, "im": 2.0, "unit": "1", "time_convention": "exp(-i omega t)"}
    assert results_common.complex_array([1j], "effective_index")["im"] == [1.0]
    maps = results_common.field_maps({"temperature": {"quantity": "temperature", "location": "nodes", "shape": [5]},
                                      "triangles": {"quantity": None, "location": "triangles", "shape": [3, 3]},
                                      "stress": {"quantity": "stress", "location": "triangle_centroids",
                                                 "shape": [3, 3], "components": ["stress_xx", "stress_yy", "stress_xy"]}})
    assert maps["field_units"] == {"temperature": "K", "stress": "Pa"}
    assert maps["field_components"] == {"stress": ["stress_xx", "stress_yy", "stress_xy"]}
    assert json.loads(results_common.metadata_json({"b": 1, "a": [0.5]})) == {"a": [0.5], "b": 1}


def test_vtu_unit_metadata_is_uint8_and_reads_back_through_meshio(tmp_path):
    import meshio
    target = tmp_path / "fields.vtu"
    mesh = meshio.Mesh(np.array([[0.0, 0, 0], [1, 0, 0], [0, 1, 0]]), [("triangle", np.array([[0, 1, 2]]))],
                       point_data={"temperature": np.array([300.0, 301, 302])})
    meshio.vtu.write(target, mesh, binary=True, compression="zlib")
    before = target.read_bytes()
    units = {"temperature": "K"}
    conventions = {"sign": {"inward_heat_flux": "positive enters the body"}}
    export.inject_field_data(target, units, conventions)
    text = target.read_text(encoding="utf-8")
    assert 'type="String"' not in text and text.count('type="UInt8"') == 2
    assert export.read_field_data(target) == {"units": units, "conventions": conventions}
    back = meshio.read(target)
    decoded = {k: json.loads(bytes(v.astype(np.uint8)).decode("utf-8")) for k, v in back.field_data.items()}
    assert decoded == {"units": units, "conventions": conventions}
    assert np.array_equal(back.point_data["temperature"], mesh.point_data["temperature"])
    at = before.index(b"<UnstructuredGrid>") + len(b"<UnstructuredGrid>")
    after = target.read_bytes()
    assert after.startswith(before[:at]) and after.endswith(before[at:])
    with pytest.raises(ValueError):
        export.inject_field_data(target, units, conventions)


def test_a_retired_layout_is_refused_by_name(tmp_path, monkeypatch):
    fields = tmp_path / "fields.npz"
    np.savez(fields, field_layout=np.array("old-layout-v1"))
    monkeypatch.setitem(export.RETIRED_LAYOUTS, "old-layout-v1", "old-layout-v2")
    for call in (lambda: export.export_fields(fields, tmp_path / "a.vtu"),
                 lambda: export.export_time_series(fields, tmp_path / "b"),
                 lambda: export.export_sweep(fields, tmp_path / "c")):
        with pytest.raises(ValueError, match=r"saved before the units and naming batch \(layout old-layout-v1\); "
                                             "re-create the document in format 0.3 and run it"):
            call()
    # each retired identifier names the layout that replaced it: supported, or (the raw subspace layout,
    # whose VTU export is deferred) refused by name with that reason (test_export_modes)
    assert set(export.RETIRED_LAYOUTS.values()) - {"old-layout-v2"} <= \
        set(export.SUPPORTED_LAYOUTS) | {"em-modes2d-subspace-raw-v2"}
    assert not set(export.RETIRED_LAYOUTS) & set(export.SUPPORTED_LAYOUTS)
