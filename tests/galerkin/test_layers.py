# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Imports inside galerkin point downward: base, core, the public assembly facades and coupling.

See docs/architecture.md ("Inside galerkin"). Read from the source, so a new
import across a layer fails here rather than in a later import cycle.
"""
import ast
from pathlib import Path

import pytest

import galerkin

# The imported package: the source tree in a checkout, site-packages in the installed-wheel run.
PACKAGE = Path(galerkin.__file__).resolve().parent
BASE = {"mesh", "mesh3d"}
# The public assembly modules sit on core: they keep their names for callers and
# take element data and solves from core, never the other way round.
FACADES = {"assembly", "assembly3d", "edge", "edge3d", "solver"}


def _galerkin_imports(path):
    """The galerkin modules ``path`` imports, as dotted names relative to the package."""
    here = path.relative_to(PACKAGE).with_suffix("").parts[:-1]
    out = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.level:
            parts = list(here[:len(here) - (node.level - 1)]) + (node.module or "").split(".")
            parts = [p for p in parts if p]
            names = [parts] if node.module else [parts + [a.name] for a in node.names]
            out.update(".".join(n) for n in names)
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("galerkin"):
            out.add(node.module.removeprefix("galerkin").lstrip("."))
        elif isinstance(node, ast.Import):
            out.update(a.name.removeprefix("galerkin").lstrip(".") for a in node.names
                       if a.name.startswith("galerkin"))
    return out


def _files(layer):
    if layer == "base":
        return sorted(PACKAGE / f"{name}.py" for name in BASE)
    if layer == "facades":
        return sorted(PACKAGE / f"{name}.py" for name in FACADES)
    return sorted((PACKAGE / layer).glob("*.py"))


@pytest.mark.parametrize("layer,allowed", [
    ("base", BASE),
    ("core", BASE | {"core"}),
    ("facades", BASE | {"core"} | FACADES),
    ("coupling", BASE | {"core", "coupling"}),
])
def test_layer_imports_only_the_layers_below(layer, allowed):
    files = _files(layer)
    assert files and all(path.exists() for path in files)
    for path in files:
        bad = sorted(name for name in _galerkin_imports(path)
                     if name and name.split(".")[0] not in allowed)
        assert not bad, f"{path.name} imports {bad}"
