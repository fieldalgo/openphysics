# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The engine must not import its own answer key."""

import ast
import pathlib
import sys

import pytest

ENGINE = pathlib.Path(__file__).resolve().parent.parent / "galerkin"


def _imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module.split(".")[0])
    return out


def test_engine_never_imports_refsol():
    offenders = {p.name for p in ENGINE.glob("*.py")
                 if "refsol" in _imported_modules(p)}
    assert not offenders, (
        f"the engine imports its own grader in {sorted(offenders)}; refsol belongs "
        "to the tests only")


def test_engine_dependencies_are_only_numpy_scipy():
    # Python >=3.10 is required by this package; classify stdlib by Python itself.
    allowed = {"numpy", "scipy", "galerkin"} | sys.stdlib_module_names
    extra = set()
    for p in ENGINE.glob("*.py"):
        extra |= {m for m in _imported_modules(p)
                  if m not in allowed and not m.startswith(".")}
    assert not extra, f"unexpected engine dependency: {sorted(extra)}"


def test_dependency_guard_accepts_standard_library(tmp_path, monkeypatch):
    (tmp_path / "probe.py").write_text("import json\nimport collections\n", encoding="utf-8")
    monkeypatch.setitem(globals(), "ENGINE", tmp_path)
    test_engine_dependencies_are_only_numpy_scipy()
    test_engine_never_imports_refsol()


@pytest.mark.parametrize("module", ["httpx", "requests", "refsol"])
def test_dependency_guard_rejects_unapproved_import(tmp_path, monkeypatch, module):
    (tmp_path / "probe.py").write_text(f"import {module}\n", encoding="utf-8")
    monkeypatch.setitem(globals(), "ENGINE", tmp_path)
    with pytest.raises(AssertionError, match=module):
        test_engine_dependencies_are_only_numpy_scipy()
    if module == "refsol":
        with pytest.raises(AssertionError, match="own grader"):
            test_engine_never_imports_refsol()
