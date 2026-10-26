# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Run the whole tests/ folder against wheels installed outside the checkout.

Builds every package (each wheel from its sdist) and installs the wheels, with
all of their extras, into a fresh venv in a temporary directory outside the
checkout. The tracked files under tests/, examples/ and docs/ and the root
pyproject.toml are copied next to it; nothing under packages/ is copied.
pytest then runs every test with `python -I`, so only the installed packages
can be imported. No test is selected by name: a test that cannot run against
the installed packages fails here.

The run fails if a first-party module does not import from the venv, if any
test is skipped or expected to fail (xfail), or if a test file produced no
results. Run it with Gmsh and the pinned RII data (PHYSMAT_RII_PATH) available:
tests that need them skip otherwise, and a skip fails the run.
"""

import argparse
import hashlib
from email.parser import BytesParser
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv
import xml.etree.ElementTree as ET
import zipfile

from packaging.utils import parse_wheel_filename

import check_distributions as distributions

ROOT = distributions.ROOT
COPIED_ROOTS = ("tests/", "examples/", "docs/")


def wheel_extras(wheel):
    """Names of the optional extras a wheel declares."""
    with zipfile.ZipFile(wheel) as archive:
        name = next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
        metadata = BytesParser().parsebytes(archive.read(name))
    return sorted(metadata.get_all("Provides-Extra") or [])


def copied_sources():
    """Tracked files the installed run needs: tests, examples, docs and the pytest config."""
    return ["pyproject.toml", *sorted(p for p in distributions.tracked_repository()
                                      if p.startswith(COPIED_ROOTS))]


def collected_files(tests):
    """Files pytest collects by default (test_*.py and *_test.py)."""
    return sorted({*tests.rglob("test_*.py"), *tests.rglob("*_test.py")})


def check_results(junit, tests):
    """Every test file produced results, and nothing was skipped or xfailed."""
    root = ET.parse(junit).getroot()
    cases = list(root.iter("testcase"))
    # pytest writes both skips and xfails as <skipped>.
    skipped = [f"{c.get('classname')}::{c.get('name')}" for c in cases if c.find("skipped") is not None]
    if skipped:
        raise RuntimeError(f"{len(skipped)} tests were skipped or xfailed against the installed "
                           f"packages: {skipped[:20]}")
    if not cases:
        raise RuntimeError("no test results")
    reported = {c.get("classname", "") for c in cases}
    silent = []
    for path in collected_files(tests):
        module = path.relative_to(tests.parent).with_suffix("").as_posix().replace("/", ".")
        if not any(name == module or name.startswith(module + ".") for name in reported):
            silent.append(path.relative_to(tests.parent).as_posix())
    if silent:
        raise RuntimeError(f"test files with no results: {silent}")
    return len(cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".validation" / "installed")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        parser.error("output must be empty")
    dist = output / "dist"
    for name in distributions.PACKAGES:
        distributions.run(sys.executable, "-m", "build", "--no-isolation", "--outdir", dist,
                          ROOT / "packages" / name, cwd=ROOT)
    for sdist in sorted(dist.glob("*.tar.gz")):
        distributions.check_sdist(sdist)
    wheels = sorted(dist.glob("*.whl"))
    if len(wheels) != len(distributions.PACKAGES):
        raise RuntimeError("expected one wheel per package")
    import_names = sorted({relative.split("/", 1)[0] for wheel in wheels
                           for relative in distributions.check_wheel(wheel)})

    with tempfile.TemporaryDirectory(prefix="openphysics-installed-tests-") as directory:
        work = Path(directory).resolve()
        if work.is_relative_to(ROOT):
            raise RuntimeError("TMPDIR must be outside the checkout")
        env_root = work / "venv"
        venv.EnvBuilder(with_pip=True).create(env_root)
        bin_dir = env_root / ("Scripts" if os.name == "nt" else "bin")
        python = bin_dir / ("python.exe" if os.name == "nt" else "python")
        env = os.environ.copy()
        # python -I ignores PYTHON* variables but not pytest's own; nothing may deselect tests.
        for name in ("PYTHONPATH", "PYTHONHOME", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
            env.pop(name, None)
        # The tests run in a temporary folder; keep caller-relative output and data paths.
        for name in ("OPENPHYSICS_CROSSCHECK_DIR", "PHYSMAT_RII_PATH"):
            if env.get(name):
                env[name] = str(Path(env[name]).resolve())
        env.update(PATH=str(bin_dir) + os.pathsep + env.get("PATH", ""), PYTHONNOUSERSITE="1",
                   MPLBACKEND="Agg", MPLCONFIGDIR=str(work / "matplotlib"),
                   OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
        # Every first-party wheel with all of its extras, resolved against the pins.
        requirements = []
        for wheel in wheels:
            name = parse_wheel_filename(wheel.name)[0]
            extras = wheel_extras(wheel)
            suffix = f"[{','.join(extras)}]" if extras else ""
            requirements.append(f"{name}{suffix} @ {wheel.as_uri()}")
        # galerkin[torch] is tested with the CPU build of torch, installed first from the
        # PyTorch index (the PyPI Linux wheel pulls CUDA packages); the pins then hold it.
        backends = ROOT / "tools" / "requirements-py312-linux-backends.txt"
        torch_pin = next(line.strip() for line in backends.read_text(encoding="utf-8").splitlines()
                         if line.startswith("torch=="))
        distributions.run(python, "-I", "-m", "pip", "install", "--only-binary=:all:",
                          "--index-url", "https://download.pytorch.org/whl/cpu", torch_pin, cwd=work, env=env)
        distributions.run(python, "-I", "-m", "pip", "install", "--only-binary=:all:",
                          "--find-links", dist, "-c", ROOT / "tools" / "requirements-py312-linux.txt",
                          "-c", backends, *requirements, cwd=work, env=env)
        distributions.run(python, "-I", "-m", "pip", "check", cwd=work, env=env)
        distributions.run(sys.executable, ROOT / "tools" / "check_licenses.py", "--python", python,
                          "--report", output / "licenses-installed.json", cwd=ROOT)

        # Tests, examples and docs come from this checkout's tracked files; no package code.
        suite = work / "suite"
        copied = {}
        for relative in copied_sources():
            destination = suite / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
            copied[relative] = hashlib.sha256(destination.read_bytes()).hexdigest()
        for name in import_names:
            if any(suite.rglob(f"{name}/__init__.py")):
                raise RuntimeError(f"package code {name} must not be copied next to the tests")
        unchanged = subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", "HEAD", "--", *copied],
                                   check=False).returncode == 0
        (output / "suite-file-hashes.json").write_text(json.dumps(
            {"commit": distributions.source_commit(), "matches_commit": unchanged, "files": copied},
            indent=2, sort_keys=True) + "\n", encoding="utf-8")

        # Every first-party module must come from the venv, never from the suite folder.
        probe = work / "installed_origins.py"
        probe.write_text(
            "import importlib, json, sys\nfrom pathlib import Path\n"
            + "names, suite = " + repr(import_names) + ", Path(sys.argv[2]).resolve()\n"
            + "if not sys.flags.isolated: raise RuntimeError('isolated Python required')\n"
            + "prefix, report = Path(sys.prefix).resolve(), {}\n"
            + "for name in names:\n"
            + "    origin = Path(importlib.import_module(name).__file__).resolve()\n"
            + "    if not origin.is_relative_to(prefix) or origin.is_relative_to(suite):\n"
            + "        raise RuntimeError(f'{name} imports from {origin}, not the installed venv')\n"
            + "    report[name] = str(origin)\n"
            + "Path(sys.argv[1]).write_text(json.dumps(report, indent=2) + '\\n', encoding='utf-8')\n",
            encoding="utf-8")
        distributions.run(python, "-I", probe, output / "installed-origins.json", suite,
                          cwd=suite, env=env)

        junit = output / "installed-tests.xml"
        # Keep what passing tests print (numerical diagnostics) in the JUnit file.
        distributions.run(python, "-I", "-m", "pytest", "-q", "-ra", "-p", "no:cacheprovider",
                          "-o", "junit_logging=all", "-o", "junit_log_passing_tests=true",
                          "--confcutdir", suite / "tests", f"--junitxml={junit}", "tests",
                          cwd=suite, env=env)
        count = check_results(junit, suite / "tests")
    print(f"{count} tests passed against {len(wheels)} installed wheels; artifacts: {output}")


if __name__ == "__main__":
    main()
