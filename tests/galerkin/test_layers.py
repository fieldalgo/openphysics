# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Imports inside galerkin point downward: core over the base modules, coupling over core.

See docs/architecture.md ("Inside galerkin"). Read from the source, so a new
import across a layer fails here rather than in a later import cycle.
"""
import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "packages" / "galerkin" / "src" / "galerkin"
BASE = {"mesh", "mesh3d", "assembly", "assembly3d", "edge", "edge3d", "solver"}


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


@pytest.mark.parametrize("layer,allowed", [
    ("core", {"core"}),
    ("coupling", {"coupling", "core"}),
])
def test_layer_imports_only_the_layers_below(layer, allowed):
    files = sorted((PACKAGE / layer).glob("*.py"))
    assert files
    for path in files:
        bad = sorted(name for name in _galerkin_imports(path)
                     if name and name.split(".")[0] not in BASE | allowed)
        assert not bad, f"{path.name} imports {bad}"
