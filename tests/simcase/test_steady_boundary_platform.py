# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Standalone steady boundary API/CLI/save consumers, including Windows I/O.

Copy this file outside the checkout for installed python -I execution.
Replacement fixtures must actually complete; no OS behavior is mocked.
"""

from concurrent.futures import ThreadPoolExecutor
import copy
import json
import shutil
import subprocess
import sys
import threading

import numpy as np
import pytest

from simcase import Document, run
from simcase.thermal import _OwnedOutput


V1 = ("thermal.steady2d-result-v1", "thermal2d-p1-node-cell-v1")
V2 = ("thermal.steady2d-result-v2", "thermal2d-p1-node-cell-boundary-v2")
BASE_FIELDS = {
    "nodes_m", "triangles", "temperature_k", "heat_flux_w_m2",
    "load_w_per_m", "reaction_w_per_m", "residual_w_per_m",
    "dirichlet_node_ids", "dirichlet_temperature_k",
}
BOUNDARY_FIELDS = {
    "prescribed_outward_load_w_per_m", "ambient_load_w_per_m",
    "convective_outward_w_per_m", "system_rhs_w_per_m",
}
METADATA = {"result_format", "field_layout", "mesh_length_unit", "metadata_json"}


def model(kind="flux-robin", *, save_fields=True):
    physics = {
        "type": "thermal.steady2d", "conductivity_w_mk": 2,
        "heat_source_w_m3": 0, "dirichlet_temperature_k": {"left": 300, "right": 293},
    }
    if kind == "empty-flux":
        physics["outward_flux_w_m2"] = {}
    elif kind == "empty-convection":
        physics["convection"] = {}
    elif kind in ("robin-only", "flux-robin", "negative"):
        physics["dirichlet_temperature_k"] = {"left": 300} if kind == "flux-robin" else {}
        physics["convection"] = {
            "right": {"h_w_m2k": 4, "ambient_temperature_k": 290}
        }
        if kind == "flux-robin":
            physics["outward_flux_w_m2"] = {"right": 2}
        elif kind == "negative":
            physics["outward_flux_w_m2"] = {"right": 50}
            physics["convection"]["right"] = {"h_w_m2k": 2, "ambient_temperature_k": 10}
    elif kind != "legacy":
        raise AssertionError(kind)
    return {
        "openphysics": "0.2", "name": "Steady boundary \u0394 \ud55c\uae00",
        "units": {"length": "m", "temperature": "K"},
        "geometry": {"domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}},
        "materials": {}, "physics": {"heat1": physics},
        "mesh": {"subdivisions": [2, 2]}, "study": {"type": "single"},
        "results": {"save_fields": save_fields, "plots": False},
    }


def read_summary(out):
    return json.loads((out / "summary.json").read_text(encoding="utf-8"))


def assert_no_pins(parent):
    assert not list(parent.glob(".simcase-pin-*"))


def assert_metadata(summary, fields, n, m, d):
    assert set(summary["field_shapes"]) == fields
    assert set(summary["field_units"]) == fields
    assert set(summary["field_locations"]) == fields
    shapes = {key: [n] for key in fields}
    shapes.update(nodes_m=[n, 2], triangles=[m, 3], heat_flux_w_m2=[m, 2],
                  dirichlet_node_ids=[d], dirichlet_temperature_k=[d])
    assert summary["field_shapes"] == shapes
    assert summary["mesh_length_unit"] == "m"
    assert summary["field_units"]["temperature_k"] == "K"
    assert summary["field_units"]["heat_flux_w_m2"] == "W/m^2"
    assert summary["field_locations"]["temperature_k"] == "nodes"
    assert summary["field_locations"]["heat_flux_w_m2"] == "triangle_centroids"
    for key in BOUNDARY_FIELDS & fields:
        assert summary["field_units"][key] == "W/m"
        assert summary["field_locations"][key] == "nodes"


@pytest.mark.parametrize("kind", [
    "legacy", "empty-flux", "empty-convection", "robin-only", "flux-robin", "negative",
])
def test_boundary_public_save_versions_and_numeric_fields(tmp_path, kind):
    data = model(kind)
    before = copy.deepcopy(data)
    result = run(Document.from_dict(data), verbose=False)
    out = tmp_path / ("boundary-\u0394-\ud55c\uae00-" + kind)
    result.save(out)
    summary = read_summary(out)
    version = V1 if kind == "legacy" else V2
    assert (summary["result_format"], summary["field_layout"]) == version
    assert json.loads((out / "model.json").read_text(encoding="utf-8"))["physics"] == before["physics"]
    assert data == before
    fields = BASE_FIELDS if kind == "legacy" else BASE_FIELDS | BOUNDARY_FIELDS
    with np.load(out / "fields.npz", allow_pickle=False) as arrays:
        assert set(arrays.files) == fields | METADATA
        assert all(not arrays[key].dtype.hasobject for key in arrays.files)
        assert str(arrays["result_format"]) == version[0]
        assert str(arrays["field_layout"]) == version[1]
        assert str(arrays["mesh_length_unit"]) == "m"
        assert json.loads(str(arrays["metadata_json"])) == summary
        for key in fields:
            assert arrays[key].dtype.kind in "iuf"
            assert np.isfinite(arrays[key]).all()
        n, m = len(arrays["nodes_m"]), len(arrays["triangles"])
        d = len(arrays["dirichlet_node_ids"])
        assert_metadata(summary, fields, n, m, d)
        if kind in ("robin-only", "negative"):
            assert d == 0 and arrays["dirichlet_temperature_k"].shape == (0,)
            assert arrays["dirichlet_node_ids"].dtype.kind in "iu"
            expected = 290 if kind == "robin-only" else -15
            np.testing.assert_allclose(arrays["temperature_k"], expected, rtol=1e-10, atol=1e-9)
            np.testing.assert_allclose(arrays["reaction_w_per_m"], 0, atol=1e-9)
        if kind != "legacy":
            np.testing.assert_allclose(
                arrays["system_rhs_w_per_m"],
                arrays["load_w_per_m"] + arrays["ambient_load_w_per_m"]
                - arrays["prescribed_outward_load_w_per_m"], rtol=1e-10, atol=1e-9,
            )
            total = np.sum(arrays["prescribed_outward_load_w_per_m"]
                           + arrays["convective_outward_w_per_m"] - arrays["reaction_w_per_m"])
            np.testing.assert_allclose(total, arrays["load_w_per_m"].sum(), rtol=1e-10, atol=1e-9)
        if kind == "flux-robin":
            # T=300-7x, qx=14: right flux2 + convection12, left reaction14.
            np.testing.assert_allclose(arrays["temperature_k"], 300 - 7*arrays["nodes_m"][:, 0],
                                       rtol=1e-10, atol=1e-9)
            np.testing.assert_allclose(arrays["heat_flux_w_m2"], np.tile([14, 0], (m, 1)),
                                       rtol=1e-10, atol=1e-9)
            for key, expected in (("prescribed_outward_load_w_per_m", 2),
                                  ("ambient_load_w_per_m", 1160),
                                  ("convective_outward_w_per_m", 12),
                                  ("reaction_w_per_m", 14)):
                np.testing.assert_allclose(arrays[key].sum(), expected, rtol=1e-10, atol=1e-9)
    assert not (out / ".incomplete").exists()
    assert not (out / "results.png").exists()
    assert_no_pins(tmp_path)
    moved = tmp_path / ("closed-" + kind)
    out.rename(moved)
    (moved / "summary.json").rename(moved / "renamed-summary.json")
    shutil.rmtree(moved)


@pytest.mark.parametrize("kind", ["robin-only", "flux-robin"])
def test_boundary_fields_false_keeps_v2_metadata_without_npz(tmp_path, kind):
    result = run(Document.from_dict(model(kind, save_fields=False)), verbose=False)
    out = tmp_path / "metadata-only"
    result.save(out)
    summary = read_summary(out)
    assert (summary["result_format"], summary["field_layout"]) == V2
    assert set(summary["field_shapes"]) == BASE_FIELDS | BOUNDARY_FIELDS
    assert summary["field_shapes"]["dirichlet_node_ids"] == ([0] if kind == "robin-only" else [3])
    assert not (out / "fields.npz").exists()
    assert not (out / ".incomplete").exists()
    assert_no_pins(tmp_path)


@pytest.mark.parametrize("kind", ["file", "empty-directory", "nonempty-directory"])
def test_boundary_api_and_cli_preserve_existing_target(tmp_path, kind):
    data = model("robin-only")
    result = run(Document.from_dict(data), verbose=False)
    target = tmp_path / "existing"
    if kind == "file":
        target.write_bytes(b"foreign file")
    else:
        target.mkdir()
        if kind == "nonempty-directory":
            (target / "foreign.txt").write_bytes(b"foreign contents")

    def snapshot():
        if target.is_file():
            return {"file": target.read_bytes()}
        return {str(p.relative_to(target)): p.read_bytes()
                for p in target.rglob("*") if p.is_file()}

    before = snapshot()
    with pytest.raises(FileExistsError):
        result.save(target)
    document = tmp_path / "model.json"
    document.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    child = subprocess.run(
        [sys.executable, "-I", "-X", "utf8", "-m", "simcase", "run", str(document), "-q", "-o", str(target)],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
    )
    assert child.returncode == 1, (child.stdout, child.stderr)
    assert "Traceback" not in child.stderr
    assert snapshot() == before
    assert_no_pins(tmp_path)


@pytest.mark.parametrize("mode", [
    "before-marker", "ordinary", "foreign", "file-replaced", "directory-replaced",
])
def test_boundary_partial_failure_preserves_ownership(tmp_path, monkeypatch, mode):
    result = run(Document.from_dict(model()), verbose=False)
    out, moved = tmp_path / "boundary", tmp_path / "moved-boundary"
    original = _OwnedOutput.write
    stages = []

    def fail(self, name, writer):
        if mode == "before-marker":
            stages.append("injected")
            raise OSError("injected boundary save")
        answer = original(self, name, writer)
        if name == "fields.npz":
            stages.append("NPZ written")
            if mode == "foreign":
                (out / "foreign.txt").write_bytes(b"foreign")
                stages.append("foreign created")
            elif mode == "file-replaced":
                replacement = tmp_path / "replacement.json"
                replacement.write_bytes(b"foreign replacement")
                replacement.replace(out / "model.json")
                assert (out / "model.json").read_bytes() == b"foreign replacement"
                stages.append("file replaced")
            elif mode == "directory-replaced":
                out.rename(moved)
                out.mkdir()
                (out / "foreign.txt").write_bytes(b"foreign directory")
                stages.append("directory replaced")
            stages.append("injected")
            raise OSError("injected boundary save")
        return answer

    monkeypatch.setattr(_OwnedOutput, "write", fail)
    with pytest.raises(OSError) as caught:
        result.save(out)
    diagnostic = {"mode": mode, "stages": stages, "error": str(caught.value),
                  "errno": caught.value.errno, "winerror": getattr(caught.value, "winerror", None)}
    print("STEADY_BOUNDARY_OWNERSHIP " + json.dumps(diagnostic), flush=True)
    assert str(caught.value) == "injected boundary save", diagnostic
    assert stages[-1] == "injected", diagnostic
    if mode in ("before-marker", "ordinary"):
        assert not out.exists()
    elif mode == "directory-replaced":
        assert "directory replaced" in stages
        assert (out / "foreign.txt").read_bytes() == b"foreign directory"
        assert (moved / ".incomplete").exists()
        assert not (moved / "summary.json").exists()
    else:
        assert (out / ".incomplete").exists() and not (out / "summary.json").exists()
        expected = b"foreign" if mode == "foreign" else b"foreign replacement"
        assert (out / ("foreign.txt" if mode == "foreign" else "model.json")).read_bytes() == expected
    assert_no_pins(tmp_path)


@pytest.mark.parametrize("mutation", ["name", "results", "flux", "ambient", "geometry", "subdivisions"])
def test_boundary_v2_metadata_snapshot_refuses_relabelling(tmp_path, mutation):
    result = run(Document.from_dict(model()), verbose=False)
    data = result.doc.data
    if mutation == "name":
        data["name"] = "changed"
    elif mutation == "results":
        data["results"]["save_fields"] = False
    elif mutation == "flux":
        data["physics"]["heat1"]["outward_flux_w_m2"]["right"] = 3
    elif mutation == "ambient":
        data["physics"]["heat1"]["convection"]["right"]["ambient_temperature_k"] = 291
    elif mutation == "geometry":
        data["geometry"]["domain"]["xmax"] = 2
    else:
        data["mesh"]["subdivisions"] = [3, 2]
    with pytest.raises(ValueError):
        result.summary()
    out = tmp_path / "changed"
    with pytest.raises(ValueError):
        result.save(out)
    assert not out.exists()
    assert_no_pins(tmp_path)


def test_boundary_snapshot_ignores_key_order_and_isolates_caller(tmp_path):
    source = Document.from_dict(model())
    result = run(source, verbose=False)
    source.data["name"] = "caller changed"
    data = result.doc.data
    reversed_items = list(data.items())[::-1]
    data.clear()
    data.update(reversed_items)
    out = tmp_path / "stable"
    result.save(out)
    saved = json.loads((out / "model.json").read_text(encoding="utf-8"))
    assert saved["name"] == model()["name"]
    assert read_summary(out)["name"] == model()["name"]
    assert_no_pins(tmp_path)


@pytest.mark.parametrize("kind", ["robin-only", "flux-robin"])
def test_boundary_isolated_cli_validates_and_saves_v2(tmp_path, kind):
    data = model(kind)
    document = tmp_path / "model.json"
    document.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    for command in (
        [sys.executable, "-I", "-X", "utf8", "-m", "simcase", "validate", str(document)],
        [sys.executable, "-I", "-X", "utf8", "-m", "simcase", "run", str(document), "-q", "-o", str(tmp_path / "cli-result")],
    ):
        child = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
        assert child.returncode == 0, (child.stdout, child.stderr)
        assert "Traceback" not in child.stderr
    summary = read_summary(tmp_path / "cli-result")
    assert (summary["result_format"], summary["field_layout"]) == V2
    with np.load(tmp_path / "cli-result" / "fields.npz", allow_pickle=False) as arrays:
        assert set(arrays.files) == BASE_FIELDS | BOUNDARY_FIELDS | METADATA
        assert all(not arrays[key].dtype.hasobject for key in arrays.files)
    assert_no_pins(tmp_path)


def test_boundary_concurrent_writers_preserve_winner(tmp_path, monkeypatch):
    result = run(Document.from_dict(model("robin-only")), verbose=False)
    out = tmp_path / "boundary"
    barrier = threading.Barrier(2)
    original = _OwnedOutput.__init__

    def together(self, path):
        barrier.wait()
        return original(self, path)

    monkeypatch.setattr(_OwnedOutput, "__init__", together)

    def save():
        try:
            result.save(out)
            return "winner"
        except FileExistsError:
            return "loser"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: save(), range(2)))
    assert sorted(outcomes) == ["loser", "winner"]
    assert read_summary(out)["result_format"] == V2[0]
    assert not (out / ".incomplete").exists()
    with np.load(out / "fields.npz", allow_pickle=False) as arrays:
        assert arrays["dirichlet_node_ids"].shape == (0,)
        assert set(arrays.files) == BASE_FIELDS | BOUNDARY_FIELDS | METADATA
    assert_no_pins(tmp_path)
