# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Consumer checks executed by check_distributions.py outside the checkout."""

import importlib
from importlib import metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys


for name in ("galerkin", "refsol", "meshine", "gmshio", "physmat", "simcase"):
    module = importlib.import_module(name)
    path = Path(module.__file__).resolve()
    assert path.is_relative_to(Path(sys.prefix).resolve()), (name, path, sys.prefix)
    print(f"Installed import: {name} -> {path}", flush=True)

for name in ("galerkin", "galerkin-refsol", "meshine", "gmshio", "physmat", "simcase", "openphysics"):
    dist = metadata.distribution(name)
    direct = json.loads(dist.read_text("direct_url.json") or "{}")
    assert not direct.get("dir_info", {}).get("editable"), name
    assert dist.read_text("LICENSE") or any(str(p).endswith("/LICENSE") for p in dist.files), name
# The openphysics meta distribution ships no code and requires exactly the six
# packages, in the same release series, plus the extras it forwards. packaging
# is installed here as a matplotlib requirement.
from packaging.requirements import Requirement  # noqa: E402

meta = {}
for requirement in map(Requirement, metadata.requires("openphysics")):
    extra = str(requirement.marker).split('"')[1] if requirement.marker else ""
    assert str(requirement.specifier) == "<0.2,>=0.1.0", requirement
    meta.setdefault(extra, set()).add((requirement.name, frozenset(requirement.extras)))
assert meta == {
    "": {(name, frozenset()) for name in
         ("galerkin", "galerkin-refsol", "meshine", "gmshio", "physmat", "simcase")},
    "studio": {("simcase", frozenset({"studio"}))},
    "export": {("simcase", frozenset({"export"}))},
    "rii": {("physmat", frozenset({"rii"}))},
}, meta
assert importlib.util.find_spec("openphysics") is None
assert not [f for f in metadata.distribution("openphysics").files if str(f).endswith(".py")]

for command in ("simcase", "simcase-run", "simcase-studio"):
    executable = shutil.which(command)
    assert executable and Path(executable).resolve().is_relative_to(Path(sys.prefix).resolve())
    subprocess.run([executable, "--help"], check=True)
subprocess.run([sys.executable, "-I", "-m", "simcase", "--help"], check=True)
subprocess.run([sys.executable, "-I", "-m", "simcase.studio", "--help"], check=True)

cli = shutil.which("simcase")
document = subprocess.check_output([cli, "example", "slab_te_check"], text=True)
Path("slab.json").write_text(document)
subprocess.run([cli, "validate", "slab.json"], check=True)
subprocess.run([cli, "run", "slab.json", "-q", "-o", "results"], check=True)
summary = json.loads(Path("results/summary.json").read_text())
assert abs(summary["neff"][0][0] - 2.8487) < 2e-3, summary
assert summary["units"] == {"length": "um"}, summary
for filename in ("fields.npz", "results.png", "log.txt", "model.json"):
    assert Path("results", filename).stat().st_size > 0, filename
print("Wheel CLI, entry points, imports, metadata and saved output passed.")
