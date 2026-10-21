# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Repository provenance audit and adversarial v1 contract probes."""

import ast
import copy
import json
from pathlib import Path
import re
import subprocess

import numpy as np
import pytest

from reference_loader import (content_digest, file_digest, load_reference, values_digest)

ROOT = Path(__file__).resolve().parents[2]
AUDIT = "tools/tests/test_reference_values.py"


def audit_record(path, root, inventory, tracked):
    ref = load_reference(path)
    record = ref.record
    entries = {**inventory["distributions"], **inventory.get("external_tools", {})}
    for tool in record["references"]:
        if tool["tool"] not in entries or entries[tool["tool"]]["spdx"] != tool["license"]:
            raise ValueError("reference license differs from inventory")
    generator = record["generator"]
    if generator["path"] != "private research repository":
        if generator["path"] not in tracked:
            raise ValueError("generator is not tracked")
        if generator["sha256"] is not None and file_digest(root / generator["path"], text=True) != generator["sha256"]:
            raise ValueError("generator hash mismatch")
    for consumer in record["consumers"]:
        if consumer not in tracked or not re.fullmatch(r"tests/.*/test_(reference|crosscheck)_.*\.py", consumer):
            raise ValueError("invalid reference consumer")
        tree = ast.parse((root / consumer).read_text(encoding="utf-8"))
        loads = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and
                 ((isinstance(n.func, ast.Name) and n.func.id == "load_reference") or
                  (isinstance(n.func, ast.Attribute) and n.func.attr == "load_reference"))]
        if not any(any(isinstance(n, ast.Constant) and isinstance(n.value, str)
                       and Path(n.value).name == path.name
                       for arg in call.args for n in ast.walk(arg)) for call in loads):
            raise ValueError("consumer must explicitly name and load the record")
    return ref


def audit_tree(root, tracked, inventory):
    records = [p for p in tracked if re.fullmatch(r"tests/[^/]+/reference_values/[^/]+/[^/]+\.json", p)
               and isinstance(json.loads((root / p).read_text(encoding="utf-8")), dict)
               and "schema" in json.loads((root / p).read_text(encoding="utf-8"))]
    payloads = set()
    for name in records:
        ref = audit_record(root / name, root, inventory, tracked)
        if "payload" in ref.record:
            payloads.add((Path(name).parent / ref.record["payload"]["file"]).as_posix())
    data = {p for p in tracked if "/reference_values/" in p and Path(p).suffix in {".json", ".npz"}}
    if data != set(records) | payloads:
        raise ValueError(f"orphan reference payload: {data - set(records) - payloads}")
    if sum((root / p).stat().st_size for p in data) > 10 * 1024 * 1024:
        raise ValueError("repository reference size limit exceeded")
    for path in tracked:
        if not path.endswith(".py") or path in {AUDIT, "tests/_support/reference_loader.py"}:
            continue
        tree = ast.parse((root / path).read_text(encoding="utf-8"))
        imports = any((isinstance(n, ast.ImportFrom) and n.module == "reference_loader") or
                      (isinstance(n, ast.Import) and any(a.name == "reference_loader" for a in n.names)) or
                      (isinstance(n, ast.Call) and any(isinstance(a, ast.Constant) and a.value == "reference_loader" for a in n.args))
                      for n in ast.walk(tree))
        if imports and not re.fullmatch(r"tests/.*/test_(reference|crosscheck)_.*\.py", path):
            raise ValueError(f"loader import in non-consumer: {path}")
        if path in {"tools/check_platform_install.py", "tools/check_distributions.py"}:
            strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            if any(re.search(r"test_(reference|crosscheck)_.*\.py", s) for s in strings):
                raise ValueError("flat copy tool selects a reference consumer")


def test_repository_references():
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")[:-1]
    inventory = json.loads((ROOT / "tools/third_party_licenses.json").read_text())
    for tool, entry in inventory.get("external_tools", {}).items():
        assert entry["spdx"] and entry["url"]
        reference = entry["reference"]
        assert set(reference) >= {"mode", "execution", "modules", "imported_by", "values", "generators", "light"}
        assert reference["mode"] == ["stored"], tool
    audit_tree(ROOT, tracked, inventory)


def test_shared_hash_vector():
    arrays = {"x": np.array([0.1, 0.2], dtype="<f8"), "z": np.array([1 + 2j], dtype="<c16")}
    digest = values_digest(arrays)
    assert digest == "5b1e6695fa1d3df431519ed94c7096a82b5d1ca875872559f67e1cab86e1ce2e"
    assert content_digest({"eps": {"real": 4.0, "imag": -0.04}, "modes": 2}, digest) == "63ad3eaeaed8bee68b8cc4ff62997c2fddd92f443327e07d926189d5fde7dea0"


@pytest.fixture
def good(tmp_path):
    directory = tmp_path / "tests/galerkin/reference_values/synthetic"
    directory.mkdir(parents=True)
    path = directory / "case.json"
    generator = directory / "generate_case.py"
    generator.write_text("# synthetic generator, no solver\n")
    consumer = tmp_path / "tests/galerkin/test_reference_example.py"
    consumer.write_text('from reference_loader import load_reference\ndef test_case():\n    load_reference("case.json")\n')
    record = {
        "schema": "openphysics.reference-values/1", "case": "synthetic", "physics": "test",
        "comparison": "same-discretization", "role": "synthetic contract test; not physics evidence",
        "references": [{"tool": "synthetic", "version": "1.0", "build": "test",
            "modified": {"value": False, "description": "unmodified"}, "license": "MIT",
            "source": "https://example.org/reference", "install": {"kind": "synthetic", "command": "none", "lock": "none"},
            "settings": {}, "discretization": {"kind": "synthetic"}, "arrays": ["x"],
            "execution": "separate-process", "independence": {"product_loaded": False, "inputs_from_product": False}}],
        "generator": {"path": generator.relative_to(tmp_path).as_posix(), "sha256": file_digest(generator, text=True),
                      "command": "python generate_case.py", "product_commit": "0" * 40, "clean": True},
        "generated_utc": "2026-10-21T00:00:00Z",
        "environment": {"python": "3.12", "numpy": "2.5.3", "os": "synthetic", "cpu": "synthetic", "dtype": "float64", "backend/device": "cpu"},
        "cost": {"compile_s": 0, "compute_s": 0, "wall_time_s": 0, "peak_rss_mb": 0, "threads": 1, "not_measured": []},
        "inputs": {"x": 1}, "matched": [], "not_matched": [], "reference_self_check": [], "failed_or_discarded": [], "not_run": [],
        "values": [{"name": "x", "unit": "1", "dtype": "<f8", "shape": [1], "data": [1.0]}],
        "consumers": [consumer.relative_to(tmp_path).as_posix()], "provenance_status": "complete", "not_recorded": {}, "regeneration": [],
    }
    record["values_sha256"] = values_digest({"x": np.array([1.0], dtype="<f8")})
    record["content_sha256"] = content_digest(record["inputs"], record["values_sha256"])
    inventory = {"distributions": {"synthetic": {"spdx": "MIT"}}}
    tracked = [p.relative_to(tmp_path).as_posix() for p in (path, generator, consumer)]
    return path, record, inventory, tracked


def write_good(good):
    path, record, _, _ = good
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def test_good_record(good, tmp_path):
    path = write_good(good)
    ref = audit_record(path, tmp_path, good[2], good[3])
    assert ref.inputs == {"x": 1}
    np.testing.assert_array_equal(ref.arrays["x"], [1.0])
    assert not ref.arrays["x"].flags.writeable
    audit_tree(tmp_path, good[3], good[2])


@pytest.mark.parametrize("probe", list("abcdefghijklmnopq"))
def test_bad_records(good, tmp_path, probe):
    path, r, inventory, tracked = good
    if probe == "a": r["values_sha256"] = "0" * 64
    if probe == "b": r["values"][0]["data"] = [float(np.nextafter(1.0, 2.0))]
    if probe == "c": r["values"][0]["data"] = [float("nan")]
    if probe == "d": r["generator"]["command"] = "python /home/user/generate.py"
    if probe == "e": r["role"] = "x" * (1024 * 1024)
    if probe in {"f", "n"}:
        r["regeneration"] = [{"date": "2026-10-21", "mode": "restamp", "reason": "" if probe == "f" else "metadata",
                              "previous_content_sha256": "0" * 64, "content_sha256": r["content_sha256"],
                              "tool_version": "1.0", "review": "reviewed", "approval": "maintainer"}]
    if probe == "g": r["environment"]["cpu"] = None
    if probe == "h": r["generator"]["sha256"] = "0" * 64
    if probe == "i": r["references"][0]["license"] = "BSD-3-Clause"
    if probe == "j": r["schema"] = "openphysics.reference-values/2"
    if probe == "k": r["content_sha256"] = "0" * 64
    if probe == "l": r["inputs"]["gate"] = 1e-3
    if probe == "m":
        extra = path.with_name("orphan.npz"); extra.write_bytes(b"orphan")
        tracked.append(extra.relative_to(tmp_path).as_posix())
    if probe == "o": r["role"] = "see work/private.md"
    if probe == "p": r["references"].append(copy.deepcopy(r["references"][0]))
    if probe == "q":
        r["references"][0].update(license="AGPL-3.0-only", modified={"value": True, "description": "changed"})
        inventory["distributions"]["synthetic"]["spdx"] = "AGPL-3.0-only"
    write_good(good)
    with pytest.raises(ValueError):
        audit_tree(tmp_path, tracked, inventory)


@pytest.mark.parametrize("path,body", [
    ("tests/galerkin/test_example.py", "from reference_loader import load_reference"),
    ("tools/check_platform_install.py", 'FILES = ["test_reference_example.py"]'),
    ("tools/check_distributions.py", 'FILES = ["test_crosscheck_example.py"]'),
])
def test_flat_copy_protection(tmp_path, path, body):
    file = tmp_path / path; file.parent.mkdir(parents=True); file.write_text(body)
    with pytest.raises(ValueError):
        audit_tree(tmp_path, [path], {"distributions": {}})


@pytest.mark.parametrize("value", ["https://claude.ai/code/session_private", "notes/private.md", "C:\\private\\file", "~/private/file", "openphysics-lab"])
def test_private_strings(good, value):
    good[1]["role"] = value
    with pytest.raises(ValueError): load_reference(write_good(good))


def test_missing_array_coverage(good):
    good[1]["references"][0]["arrays"] = ["other"]
    with pytest.raises(ValueError): load_reference(write_good(good))


@pytest.mark.parametrize("format", ["json", "npz"])
def test_payload_and_tampering(good, format):
    path, record, _, _ = good
    payload = path.with_name("values." + format)
    values = record.pop("values")
    if format == "json": payload.write_text(json.dumps(values))
    else: np.savez(payload, x=np.array([1.0], dtype="<f8"))
    record["payload"] = {"file": payload.name, "format": format, "file_sha256": file_digest(payload, text=format == "json"), "arrays": ["x"]}
    load_reference(write_good(good))
    payload.write_bytes(payload.read_bytes() + b" ")
    with pytest.raises(ValueError, match="file hash"): load_reference(path)


def test_unrelated_load_is_not_a_consumer(good, tmp_path):
    consumer = tmp_path / good[1]["consumers"][0]
    consumer.write_text('from reference_loader import load_reference\nNAME = "case.json"\nload_reference("other.json")\n')
    with pytest.raises(ValueError, match="explicitly"):
        audit_record(write_good(good), tmp_path, good[2], good[3])


def test_valid_reconstructed_provenance_and_restamp(good):
    record = good[1]
    record["environment"]["cpu"] = None
    record["provenance_status"] = "reconstructed"
    record["not_recorded"] = {"environment.cpu": "not recorded in the original run log"}
    record["regeneration"] = [{"date": "2026-10-21", "mode": "restamp", "reason": "add provenance",
        "previous_content_sha256": record["content_sha256"], "content_sha256": record["content_sha256"],
        "tool_version": "1.0", "review": "reviewed change", "approval": "approved by the maintainer, 2026-10-21"}]
    load_reference(write_good(good))


def test_complex_inline(good):
    record = good[1]
    record["values"] = [{"name": "x", "unit": "1", "dtype": "<c16", "shape": [1], "real": [1], "imag": [2]}]
    record["values_sha256"] = values_digest({"x": np.array([1+2j], dtype="<c16")})
    record["content_sha256"] = content_digest(record["inputs"], record["values_sha256"])
    assert load_reference(write_good(good)).arrays["x"][0] == 1+2j
