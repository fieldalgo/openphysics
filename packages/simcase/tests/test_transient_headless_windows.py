# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Small transient save consumers for the Windows job and other platforms.

Copy this file outside the checkout to exercise installed wheels with python -I.
No native behavior is mocked: replacement fixtures must actually complete.
"""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading

import numpy as np
import pytest

from simcase import Document, run
from simcase.thermal import _OwnedOutput


def model():
    return {
        "openphysics": "0.2", "name": "Transient \u0394 \ud55c\uae00",
        "units": {"length": "mm", "temperature": "K", "time": "s"},
        "geometry": {"domain": {"xmin": 0, "xmax": 2, "ymin": 0, "ymax": 1}},
        "materials": {},
        "physics": {"heat1": {
            "type": "thermal.transient2d", "conductivity_w_mk": 2,
            "volumetric_heat_capacity_j_m3k": 1000,
            "initial_temperature_k": 300,
            "dirichlet_temperature_k": {"left": 300}, "heat_source_w_m3": 2,
        }},
        "mesh": {"subdivisions": [2, 2]},
        "study": {"type": "transient", "time_s": [0, 0.01, 0.025]},
        "results": {"save_fields": True, "plots": False},
    }


@pytest.mark.parametrize("save_fields", [False, True])
def test_transient_saved_history_and_closed_handles(tmp_path, save_fields):
    data = model()
    data["results"]["save_fields"] = save_fields
    result = run(Document.from_dict(data), verbose=False)
    out = tmp_path / "history-\u0394-\ud55c\uae00"
    result.save(out)
    assert json.loads((out / "model.json").read_text(encoding="utf-8"))["name"] == data["name"]
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["result_format"] == "thermal.transient2d-result-v1"
    assert summary["field_layout"] == "thermal2d-transient-p1-node-cell-v1"
    assert summary["study"]["time_s"] == data["study"]["time_s"]
    assert summary["rate_time_s"] == data["study"]["time_s"][1:]
    assert summary["save_fields"] is save_fields
    assert not (out / ".incomplete").exists()
    assert not list(tmp_path.glob(".simcase-pin-*"))
    if save_fields:
        with np.load(out / "fields.npz", allow_pickle=False) as arrays:
            assert all(not arrays[key].dtype.hasobject for key in arrays.files)
            np.testing.assert_array_equal(arrays["temperature_k"], result.temperature_k)
            np.testing.assert_array_equal(arrays["time_s"], data["study"]["time_s"])
            assert arrays["temperature_k"].shape[0] == 3
            assert arrays["storage_rate_w_per_m"].shape[0] == 2
            assert arrays["reaction_w_per_m"].shape[0] == 2
    else:
        assert not (out / "fields.npz").exists()
    # Open handles must not keep a successful Windows output from moving/deleting.
    moved = tmp_path / "moved-history"
    out.rename(moved)
    summary_file = moved / "summary.json"
    renamed = moved / "renamed-summary.json"
    summary_file.rename(renamed)
    renamed.rename(summary_file)
    shutil.rmtree(moved)
    assert not moved.exists()


@pytest.mark.parametrize("kind", ["file", "empty-directory", "nonempty-directory"])
def test_transient_api_and_cli_preserve_existing_target(tmp_path, kind):
    data = model()
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
        return {str(p.relative_to(target)): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    before = snapshot()
    with pytest.raises(FileExistsError):
        result.save(target)
    document = tmp_path / "model.json"
    document.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    child = subprocess.run(
        [sys.executable, "-I", "-m", "simcase", "run", str(document), "-q", "-o", str(target)],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
    )
    assert child.returncode == 1, (child.stdout, child.stderr)
    assert "Traceback" not in child.stderr
    assert snapshot() == before
    assert not list(tmp_path.glob(".simcase-pin-*"))


def test_transient_isolated_cli_writes_fresh_history(tmp_path):
    data = model()
    document = tmp_path / "model.json"
    document.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "cli-history"
    child = subprocess.run(
        [sys.executable, "-I", "-m", "simcase", "run", str(document), "-q", "-o", str(out)],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
    )
    assert child.returncode == 0, (child.stdout, child.stderr)
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["physics_type"] == "thermal.transient2d"
    assert summary["study"]["time_s"] == data["study"]["time_s"]
    assert not (out / ".incomplete").exists()
    assert not (out / "results.png").exists()
    assert not list(tmp_path.glob(".simcase-pin-*"))
    with np.load(out / "fields.npz", allow_pickle=False) as arrays:
        assert arrays["temperature_k"].shape[0] == 3
        assert arrays["reaction_w_per_m"].shape[0] == 2
        assert all(not arrays[key].dtype.hasobject for key in arrays.files)
    moved = tmp_path / "moved-cli-history"
    out.rename(moved)
    shutil.rmtree(moved)


@pytest.mark.parametrize("mode", ["before-marker", "ordinary", "foreign", "file-replaced", "directory-replaced"])
def test_transient_partial_failure_preserves_ownership(tmp_path, monkeypatch, mode):
    result = run(Document.from_dict(model()), verbose=False)
    out, moved = tmp_path / "history", tmp_path / "moved-history"
    original = _OwnedOutput.write
    stages = []

    def fail(self, name, writer):
        if mode == "before-marker":
            stages.append("injected")
            raise OSError("injected transient save")
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
            raise OSError("injected transient save")
        return answer

    monkeypatch.setattr(_OwnedOutput, "write", fail)
    with pytest.raises(OSError) as caught:
        result.save(out)
    diagnostic = {"mode": mode, "stages": stages, "error": str(caught.value),
                  "errno": caught.value.errno, "winerror": getattr(caught.value, "winerror", None)}
    print("TRANSIENT_OWNERSHIP_DIAGNOSTIC " + json.dumps(diagnostic), flush=True)
    # A fixture permission/rename failure cannot masquerade as the injected fault.
    assert str(caught.value) == "injected transient save", diagnostic
    assert stages[-1] == "injected", diagnostic
    if mode in ("before-marker", "ordinary"):
        assert not out.exists()
    elif mode == "directory-replaced":
        assert "directory replaced" in stages
        assert (out / "foreign.txt").read_bytes() == b"foreign directory"
        assert (moved / ".incomplete").exists()
        assert not (moved / "summary.json").exists()
    else:
        assert (out / ".incomplete").exists()
        assert not (out / "summary.json").exists()
        if mode == "foreign":
            assert (out / "foreign.txt").read_bytes() == b"foreign"
        else:
            assert "file replaced" in stages
            assert (out / "model.json").read_bytes() == b"foreign replacement"
    assert not list(tmp_path.glob(".simcase-pin-*"))


def test_transient_concurrent_writers_preserve_winner(tmp_path, monkeypatch):
    result = run(Document.from_dict(model()), verbose=False)
    out = tmp_path / "history"
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
    assert not (out / ".incomplete").exists()
    assert (out / "summary.json").is_file()
    with np.load(out / "fields.npz", allow_pickle=False) as arrays:
        np.testing.assert_array_equal(arrays["temperature_k"], result.temperature_k)
    assert not list(tmp_path.glob(".simcase-pin-*"))
