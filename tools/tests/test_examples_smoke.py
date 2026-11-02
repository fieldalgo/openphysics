# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Run every example under examples/ once, as a person would, and require exit code 0.

Each Python script runs in its own interpreter (``sys.executable``) from a
temporary working directory, and each JSON document goes through the public
``python -m simcase validate`` and ``python -m simcase run`` commands the
documentation gives. Nothing here checks numbers: the worked-tutorial tests and
the package suites do that. This test only shows that the shipped examples
still run against this checkout's code.

The whole ``examples/`` tree is copied into the temporary directory first,
because three examples save their figure next to their own file
(``Path(__file__).with_name(...)``) and would otherwise overwrite the tracked
PNGs in the checkout; sibling imports (``mesh_io.py`` imports
``cavity_modes.py``) and ``layered_wall.py``'s JSON lookup keep working in the
copy. Scripts that read the ``.npz`` another example saved run after that
example in one shared working directory; selecting one of them alone runs its
producer first.

Subprocesses do not see the root ``conftest.py``, so the package ``src/``
folders are passed on ``PYTHONPATH``, in the same order the conftest puts them
on ``sys.path``. This file runs from the source tree only:
``tools/run_installed_tests.py`` copies ``tests/``, ``examples/`` and ``docs/``
and runs ``tests/``, not ``tools/tests/``.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"
PACKAGE_SOURCES = sorted(p / "src" for p in (ROOT / "packages").iterdir() if (p / "src").is_dir())

TIMEOUT_S = 900.

# Command-line arguments. ``{out}`` is a fresh, not yet existing folder under the
# working directory, named after the example.
ARGS = {
    "galerkin/public_benchmarks.py": ["{out}", "--quick"],
    "meshine/extrude_chip.py": ["{out}.msh"],
    "simcase/gallery.py": ["{out}", "--quick"],
    "simcase/layered_wall.py": ["{out}"],
    "simcase/record_wall_run.py": ["{out}"],
}

# Scripts that load a file another script saves in the working directory.
NEEDS = {
    "galerkin/visualize.py": ["galerkin/coax_convergence.py"],
    "galerkin/visualize_cavity.py": ["galerkin/cavity_modes.py"],
    "galerkin/visualize_fiber.py": ["galerkin/fiber_modes.py"],
    "galerkin/visualize_m2.py": ["galerkin/waveguide_convergence.py"],
    "galerkin/visualize_modes.py": ["galerkin/waveguide_modes.py"],
    "galerkin/visualize_pml.py": ["galerkin/cylinder_scattering_pml.py"],
}

# Examples that run the Gmsh executable; they skip without one, like tests/gmshio.
GMSH = {"gmshio/hadley_rib_mesh.py"}

# Over about 20 s each on the pinned Linux environment (2026-11-02; the whole
# file took 10.5 min, none over 90 s), plus every script that needs one of them.
SLOW = {
    "galerkin/cavity_modes.py",              # 88 s
    "galerkin/fiber_modes.py",               # 81 s
    "galerkin/transient_heat_convergence.py",  # 80 s
    "galerkin/rib_waveguide_vector.py",      # 40 s
    "galerkin/cylinder_scattering_pml.py",   # 27 s
    "galerkin/visualize_fiber.py",           # 22 s
    "sipi/design.py",                        # 64 s
    "sipi/conductor_loss.py",                # 35 s
    "simcase/gallery_box_cavity.json",       # 32 s
}
SLOW |= {consumer for consumer, producers in NEEDS.items() if set(producers) & SLOW}


def _examples():
    scripts = sorted(p.relative_to(EXAMPLES).as_posix() for p in EXAMPLES.glob("*/*.py"))
    documents = sorted(p.relative_to(EXAMPLES).as_posix() for p in EXAMPLES.glob("simcase/*.json"))
    # Producers before the scripts that read their output, so a whole run does
    # not run any producer twice.
    ordered = []
    for name in scripts:
        for producer in NEEDS.get(name, ()):
            if producer not in ordered:
                ordered.append(producer)
        if name not in ordered:
            ordered.append(name)
    assert sorted(ordered) == scripts
    return ordered + documents


def _param(name):
    marks = [pytest.mark.slow] if name in SLOW else []
    return pytest.param(name, marks=marks, id=name)


@pytest.fixture(scope="session")
def workspace(tmp_path_factory):
    work = tmp_path_factory.mktemp("examples")
    shutil.copytree(EXAMPLES, work / "examples", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (work / "run").mkdir()
    return {"root": work, "cwd": work / "run", "done": set(), "seconds": {}}


def _environment():
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(p) for p in PACKAGE_SOURCES]
                                        + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env.update(MPLBACKEND="Agg", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
               PYTHONIOENCODING="utf-8")
    return env


def _run(workspace, *command):
    started = time.perf_counter()
    try:
        completed = subprocess.run([sys.executable, *map(str, command)], cwd=workspace["cwd"],
                                   env=_environment(), capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        pytest.fail(f"{command[0]} did not finish within {TIMEOUT_S:.0f} s\n{exc.stderr or ''}")
    seconds = time.perf_counter() - started
    print(f"{' '.join(map(str, command))}: {seconds:.1f} s")
    assert completed.returncode == 0, (f"exit code {completed.returncode}\n--- stdout ---\n"
                                       f"{completed.stdout}\n--- stderr ---\n{completed.stderr}")
    return seconds


def _run_script(workspace, name):
    """Run one example script once per session; its producers first."""
    if name in workspace["done"]:
        return workspace["seconds"][name]
    for producer in NEEDS.get(name, ()):
        _run_script(workspace, producer)
    out = workspace["cwd"] / Path(name).stem
    args = [a.format(out=out) for a in ARGS.get(name, [])]
    seconds = _run(workspace, workspace["root"] / "examples" / name, *args)
    workspace["done"].add(name)
    workspace["seconds"][name] = seconds
    return seconds


@pytest.mark.parametrize("name", [_param(n) for n in _examples()])
def test_example_runs(workspace, name):
    if name in GMSH:
        from gmshio import find_gmsh
        if find_gmsh() is None:
            pytest.skip("gmsh executable not found")
    if name.endswith(".json"):
        document = workspace["root"] / "examples" / name
        out = workspace["cwd"] / (Path(name).stem + "_results")
        _run(workspace, "-m", "simcase", "validate", document)
        _run(workspace, "-m", "simcase", "run", document, "-q", "-o", out)
        assert out.is_dir() and any(out.iterdir()), f"{name}: simcase run saved nothing"
    else:
        _run_script(workspace, name)
