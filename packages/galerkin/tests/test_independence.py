# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The engine must not import its own answer key."""

import ast
import pathlib

ENGINE = pathlib.Path(__file__).resolve().parent.parent / "galerkin"


def _imported_modules(path):
    tree = ast.parse(path.read_text())
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
    allowed = {"numpy", "scipy", "galerkin", "__future__", "itertools",
               "typing", "dataclasses", "os", "math"}
    extra = set()
    for p in ENGINE.glob("*.py"):
        extra |= {m for m in _imported_modules(p)
                  if m not in allowed and not m.startswith(".")}
    assert not extra, f"unexpected engine dependency: {sorted(extra)}"
