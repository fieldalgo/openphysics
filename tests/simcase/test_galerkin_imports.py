# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""simcase uses galerkin through its public API, never its private names or ``galerkin.core``.

simcase is an ordinary consumer of galerkin. ``galerkin.core`` is the layer
galerkin builds its physics on and its underscore names are private, so galerkin
can reorganize both without editing simcase only if simcase stays off them. Read
from the source, so a new reach fails here rather than at the next galerkin change.
The one allowed reach is listed in ``ALLOWED`` with its closing condition.

Checked: every import form (``import galerkin.core``, ``from galerkin.core import
...``, ``from galerkin import core``, ``import galerkin._x``, ``from galerkin.x
import _y``), ``importlib.import_module`` and ``__import__`` with a literal module
name, and attribute reads and ``getattr`` with a literal name on a name an import
from galerkin binds or an attribute chain from one (``galerkin.core.forms``,
``g._x``, ``Mesh._y``, ``getattr(galerkin.waveguide, "_y")``). An AST check cannot
see a module or attribute name that is computed at run time.
"""
import ast
from pathlib import Path

import pytest

import simcase

# The imported package: the source tree in a checkout, site-packages in the installed-wheel run.
PACKAGE = Path(simcase.__file__).resolve().parent

# (module path relative to the package's parent, dotted target) -> why it is allowed.
ALLOWED = {
    ("simcase/steady_boundary_contract.py", "galerkin.core.triangles.triangle_geometry"):
        # Closing condition: remove when galerkin offers a public mesh check.
        "rectangle mesh validation reuses galerkin's triangle geometry check",
}


def _forbidden(parts):
    """True when dotted galerkin parts (after ``galerkin``) name core or an underscore name."""
    return bool(parts) and (parts[0] == "core"
                            or any(p.startswith("_") and not p.startswith("__") for p in parts))


def _name_chain(node):
    """(root name, attribute names) for ``a.b.c``, or (None, []) when the chain does not start at a name."""
    chain = []
    while isinstance(node, ast.Attribute):
        chain.insert(0, node.attr)
        node = node.value
    return (node.id, chain) if isinstance(node, ast.Name) else (None, [])


def _literal(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _galerkin_reaches(text):
    """(line, target) for every reach into ``galerkin.core`` or a galerkin underscore name in ``text``."""
    tree = ast.parse(text)
    # Local name -> the galerkin parts it stands for (``import galerkin as g`` -> g: []).
    bound = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                parts = a.name.split(".")
                if parts[0] == "galerkin":
                    # ``import galerkin.x`` binds ``galerkin``; ``import galerkin.x as y`` binds y to galerkin.x.
                    bound[a.asname or "galerkin"] = parts[1:] if a.asname else []
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and (node.module or "").split(".")[0] == "galerkin":
            for a in node.names:
                bound[a.asname or a.name] = node.module.split(".")[1:] + [a.name]
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(node.lineno, a.name) for a in node.names
                    if a.name.split(".")[0] == "galerkin" and _forbidden(a.name.split(".")[1:])]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and (node.module or "").split(".")[0] == "galerkin":
            parts = node.module.split(".")[1:]
            out += [(node.lineno, f"{node.module}.{a.name}") for a in node.names
                    if _forbidden(parts + [a.name])]
        elif isinstance(node, ast.Attribute):
            root, chain = _name_chain(node)
            if root in bound:
                full = bound[root] + chain
                # Report each reach once, on the attribute that makes it forbidden.
                if _forbidden(full) and not _forbidden(full[:-1]):
                    out.append((node.lineno, ".".join(["galerkin", *full])))
        elif isinstance(node, ast.Call) and node.args:
            func = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
            name = _literal(node.args[0])
            if func in ("import_module", "__import__") and name and name.split(".")[0] == "galerkin":
                if _forbidden(name.split(".")[1:]):
                    out.append((node.lineno, name))
            elif func == "getattr" and isinstance(node.func, ast.Name) and len(node.args) >= 2:
                root, chain = _name_chain(node.args[0])
                attr = _literal(node.args[1])
                if root in bound and attr is not None:
                    full = bound[root] + chain + [attr]
                    if _forbidden(full) and not _forbidden(full[:-1]):
                        out.append((node.lineno, ".".join(["galerkin", *full])))
    return out


def _source_reaches():
    files = sorted(p for p in PACKAGE.rglob("*.py") if "__pycache__" not in p.parts)
    assert len(files) > 30
    return [(path.relative_to(PACKAGE.parent).as_posix(), line, target)
            for path in files for line, target in _galerkin_reaches(path.read_text(encoding="utf-8"))]


def test_simcase_reaches_galerkin_internals_only_where_allowed():
    bad = [hit for hit in _source_reaches() if (hit[0], hit[2]) not in ALLOWED]
    assert not bad, f"simcase reaches galerkin.core or galerkin private names: {bad}"


def test_every_allowed_reach_is_still_there():
    """An entry whose import is gone or changed is removed, so the list only shrinks."""
    used = {(path, target) for path, _, target in _source_reaches()}
    stale = sorted(set(ALLOWED) - used)
    assert not stale, f"allowed galerkin internals no longer imported; remove them from ALLOWED: {stale}"


@pytest.mark.parametrize("code,target", [
    ("import galerkin.core", "galerkin.core"),
    ("import galerkin.core.forms as forms", "galerkin.core.forms"),
    ("from galerkin.core import forms", "galerkin.core.forms"),
    ("from galerkin.core.kernels import p1_mass", "galerkin.core.kernels.p1_mass"),
    ("from galerkin import core", "galerkin.core"),
    ("import galerkin._cavity_common", "galerkin._cavity_common"),
    ("from galerkin._cavity_common import box_mesh", "galerkin._cavity_common.box_mesh"),
    ("from galerkin.waveguide import _free_dofs", "galerkin.waveguide._free_dofs"),
    ("from galerkin import _private", "galerkin._private"),
    ("import galerkin\ngalerkin.core.kernels.p1_mass", "galerkin.core"),
    ("import galerkin as g\ng.waveguide._free_dofs", "galerkin.waveguide._free_dofs"),
    ("import galerkin.waveguide\ngalerkin._private", "galerkin._private"),
    ("import galerkin.waveguide as wg\nwg._free_dofs", "galerkin.waveguide._free_dofs"),
    ("from galerkin import waveguide\nwaveguide._free_dofs", "galerkin.waveguide._free_dofs"),
    ("from galerkin import Mesh\nMesh._edges", "galerkin.Mesh._edges"),
    ("import galerkin\ngetattr(galerkin, '_mode_blocks')", "galerkin._mode_blocks"),
    ("import galerkin\ngetattr(galerkin, 'core')", "galerkin.core"),
    ("import galerkin\ngetattr(galerkin.waveguide, '_free_dofs')", "galerkin.waveguide._free_dofs"),
    ("import importlib\nimportlib.import_module('galerkin.core.forms')", "galerkin.core.forms"),
    ("from importlib import import_module\nimport_module('galerkin._cavity_common')", "galerkin._cavity_common"),
    ("__import__('galerkin.core')", "galerkin.core"),
])
def test_each_form_of_reaching_galerkin_internals_is_seen(code, target):
    assert [t for _, t in _galerkin_reaches(code)] == [target]


@pytest.mark.parametrize("code", [
    "from galerkin import Mesh, assemble_mass",
    "from galerkin import Mesh\nMesh.__name__",
    "from galerkin.waveguide import solve_modes",
    "from galerkin.temperature_joule_heating import JouleConvergenceError",
    "import galerkin\ngalerkin.__version__",
    "import galerkin\ngetattr(galerkin, 'solve_cavity_box', None)",
    "from . import _private\nfrom .core import x",
    "import numpy as np\nnp.core",
    "import importlib\nimportlib.import_module('galerkin.waveguide')",
    "import importlib\nimportlib.import_module(f'{__package__}._registry')",
    "__import__('numpy.core')",
    "import galerkin\ngetattr(galerkin.waveguide, 'solve_modes')",
])
def test_public_galerkin_names_and_other_packages_pass(code):
    assert _galerkin_reaches(code) == []
