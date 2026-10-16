# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Build all distributions and exercise their wheels in an isolated temporary venv.

Run with the pinned validation requirements installed. No upload is performed.
The temporary directory, test copies and working directory are outside the checkout
so neither editable installs nor the root conftest can supply package code.
"""

import argparse
import hashlib
import json
import os
import posixpath
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tarfile
import venv
import zipfile
from urllib.parse import unquote, urlsplit

from packaging.utils import canonicalize_name, parse_sdist_filename, parse_wheel_filename

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("galerkin", "galerkin-refsol", "meshine", "gmshio", "physmat", "simcase", "openphysics")
RUNTIME_MODULE_ASSETS = {"galerkin": ("galerkin/transient_heat.py", "galerkin/thermal.py",
                         "galerkin/transient_thermal_mechanical.py"),
                         "galerkin-refsol": ("refsol/transient_heat.py",),
                         "simcase": ("simcase/steady_boundary_contract.py",
                                     "simcase/schema.py", "simcase/transient_thermal_contract.py",
                                     "simcase/transient_thermal.py", "simcase/runner.py",
                                     "simcase/cli.py", "simcase/examples.py", "simcase/__init__.py",
                                     "simcase/thermal.py", "simcase/studio/server.py",
                                     "simcase/studio/thermal_api.py",
                                     "simcase/studio/transient_thermal_api.py") }
STUDIO_RESOURCE_ASSETS = ("simcase/studio/static/index.html",
                          "simcase/studio/static/thermal.js",
                          "simcase/studio/static/transient_thermal.js")
DOCUMENT_ASSETS = {'galerkin': (
              'galerkin/transient_thermal_mechanical.py',
              'docs/transient_thermal_mechanical.md',
              'docs/locales/ko/pages/transient_thermal_mechanical.md',
              'examples/transient_thermal_mechanical.py',
              'tests/test_transient_thermal_mechanical.py',
              'tests/test_transient_thermal_mechanical_physics.py',
              'galerkin/thermal.py',
              'galerkin/transient_heat.py',
              'docs/transient_heat.md',
              'docs/locales/ko/pages/transient_heat.md',
              'docs/transient_heat_validation.md',
              'docs/locales/ko/pages/transient_heat_validation.md',
              'docs/transient_heat_independent_validation.md',
              'docs/locales/ko/pages/transient_heat_independent_validation.md',
              'examples/transient_heat_convergence.py',
              'tests/test_transient_heat.py',
               'tests/test_transient_heat_tiny_domain.py',
               'tests/test_transient_heat_general_state.py',
              'tests/test_transient_heat_independent_validation.py',
              'tests/transient_heat_independent_oracle.py',
              'tests/transient_heat_independent_cases.py',
              'tests/transient_heat_independent_consumer.py',
              'galerkin/thermoelasticity.py',
              'docs/thermoelastic_traction.md',
              'docs/locales/ko/pages/thermoelastic_traction.md',
              'examples/thermoelastic_traction.py',
              'tests/test_thermoelastic_traction.py',
              'tests/test_thermoelastic_traction_convergence.py',
              'docs/thermoelastic_traction_independent_validation.md',
              'docs/locales/ko/pages/thermoelastic_traction_independent_validation.md',
              'tests/test_thermoelastic_traction_independent_validation.py',
              'tests/thermoelastic_traction_independent_oracle.py',
              'tests/thermoelastic_traction_independent_consumer.py',
              'docs/thermal_mechanical_independent_validation.md',
              'docs/locales/ko/pages/thermal_mechanical_independent_validation.md',
              'tests/test_thermal_mechanical_independent_validation.py',
              'tests/thermal_mechanical_independent_oracle.py',
              'galerkin/thermal_mechanical.py',
              'docs/thermal_mechanical_workflow.md',
              'docs/locales/ko/pages/thermal_mechanical_workflow.md',
              'examples/thermal_mechanical_workflow.py',
              'tests/test_thermal_mechanical_workflow.py',
              'tests/test_thermal_mechanical_workflow_physics.py',
              'tests/thermal_mechanical_workflow_oracle.py',
              'docs/cavity_solver.md',
              'docs/eigenspace_reliability.md',
              'docs/elasticity2d.md',
              'docs/elasticity2d_independent_validation.md',
              'examples/elasticity2d.py',
              'tests/eigenspace_reliability_oracle.py',
              'tests/elasticity2d_independent_oracle.py',
              'tests/test_elasticity2d_independent_validation.py',
              'docs/thermal_steady2d.md',
              'examples/thermal_steady2d.py',
              'docs/elasticity_traction.md',
              'examples/elasticity_traction.py',
              'docs/elasticity_traction_independent_validation.md',
              'tests/traction_independent_oracle.py',
              'tests/test_traction_independent_validation.py',
              'docs/thermal_independent_validation.md',
              'docs/thermal_independent_validation_manifest.json',
              'tests/thermal_independent_oracle.py',
              'tests/test_thermal_independent_validation.py',
              'docs/prescribed_temperature_thermoelasticity.md',
              'examples/prescribed_temperature_thermoelasticity.py',
              'docs/prescribed_temperature_thermoelasticity_independent_validation.md',
              'tests/thermoelasticity_independent_oracle.py',
              'tests/test_thermoelasticity_independent_validation.py',
              'docs/overview.md', 'docs/locales/ko/pages/overview.md',
              'docs/locales/ko/pages/cavity_solver.md',
              'docs/locales/ko/pages/eigenspace_reliability.md',
              'docs/locales/ko/pages/elasticity2d.md',
              'docs/locales/ko/pages/elasticity2d_independent_validation.md',
              'docs/locales/ko/pages/elasticity_traction.md',
              'docs/locales/ko/pages/elasticity_traction_independent_validation.md',
              'docs/locales/ko/pages/prescribed_temperature_thermoelasticity.md',
              'docs/locales/ko/pages/prescribed_temperature_thermoelasticity_independent_validation.md',
              'docs/locales/ko/pages/thermal_flux_robin.md',
              'docs/locales/ko/pages/thermal_flux_robin_independent_validation.md',
              'docs/locales/ko/pages/thermal_independent_validation.md',
              'docs/locales/ko/pages/thermal_steady2d.md',
              'docs/thermal_flux_robin.md',
              'docs/thermal_flux_robin_independent_validation.md',
              'examples/thermal_flux_robin.py',
              'tests/thermal_flux_robin_independent_oracle.py',
              'tests/test_thermal_flux_robin_independent_validation.py'),
 'galerkin-refsol': (
              'refsol/transient_heat.py',
              'tests/test_transient_heat_reference.py',
              'refsol/thermoelastic_traction.py',
                     'tests/test_thermoelastic_traction_reference.py',
                     'refsol/elasticity.py',
                     'refsol/thermal.py',
                     'refsol/elasticity_traction.py',
                     'refsol/thermoelasticity.py',
                     'docs/overview.md', 'docs/locales/ko/pages/overview.md',
                     'refsol/thermal_boundary.py'),
 'simcase': (
              'simcase/studio/thermal_api.py',
              'simcase/studio/static/index.html',
              'simcase/studio/static/thermal.js',
              'tests/studio_steady_thermal.cjs',
              'tests/test_studio_steady_thermal_http.py',
              'tests/test_studio_thermal_acceptance.py',
              'tests/studio_thermal_independent_fixtures.py',
              'tests/test_studio_thermal_lifecycle.py',
              'tests/test_studio_transient_server_http.py',
              'tests/studio_transient_lifecycle_fixtures.py',
              'tests/test_studio_transient_lifecycle.py',
              'simcase/studio/static/transient_thermal.js',
              'simcase/studio/transient_thermal_api.py',
              'tests/studio_transient_thermal.cjs',
              'tests/studio_transient_independent_fixtures.py',
              'tests/test_studio_transient_thermal_acceptance.py',
              'docs/thermal_transient_studio.md',
              'docs/studio_transient_thermal_independent_validation.md',
              'docs/locales/ko/pages/studio_transient_thermal_independent_validation.md',
              'docs/locales/ko/pages/thermal_transient_studio.md',
              'docs/thermal_studio.md',
              'docs/locales/ko/pages/thermal_studio.md',
              'docs/studio_thermal_independent_validation.md',
              'docs/locales/ko/pages/studio_thermal_independent_validation.md',
              'tests/test_steady_boundary_schema.py',
              'tests/test_steady_boundary_runtime.py',
              'examples/thermal_boundary.json',
              'tests/test_steady_boundary_platform.py',
              'tests/test_studio_steady_boundary.py',
              'tests/studio_steady_boundary.cjs',
              'docs/thermal_steady_boundary2d.md',
              'docs/locales/ko/pages/thermal_steady_boundary2d.md',
              'docs/steady_boundary_independent_validation.md',
              'docs/locales/ko/pages/steady_boundary_independent_validation.md',
              'tests/steady_boundary_independent_oracle.py',
              'tests/steady_boundary_independent_cases.py',
              'tests/steady_boundary_independent_consumer.py',
              'tests/test_steady_boundary_independent_validation.py',
              'simcase/steady_boundary_contract.py',
              'tests/test_steady_boundary_contract.py',
              'simcase/schema.py',
              'simcase/transient_thermal_contract.py',
              'simcase/transient_thermal.py',
              'simcase/runner.py',
              'simcase/cli.py',
              'simcase/examples.py',
              'simcase/__init__.py',
              'simcase/thermal.py',
              'simcase/studio/server.py',
              'docs/thermal_transient2d.md',
              'docs/locales/ko/pages/thermal_transient2d.md',
              'examples/transient_thermal_uniform.json',
              'tests/test_transient_thermal_contract.py',
              'tests/test_transient_thermal_runtime.py',
              'tests/test_studio_transient.py',
              'tests/test_transient_headless_windows.py',
              'tests/test_transient_headless_independent_validation.py',
              'tests/transient_headless_independent_oracle.py',
              'tests/transient_headless_independent_cases.py',
              'tests/transient_headless_independent_consumer.py',
              'docs/cavity3d.md',
             'examples/cavity_box.json',
             'docs/geometry.png',
             'docs/results.png',
             'docs/thermal_steady2d.md',
             'examples/thermal_slab.json',
             'examples/thermal_mixed.json',
             'tests/studio_thermal.cjs',
             'docs/overview.md', 'docs/locales/ko/pages/overview.md',
             'docs/locales/ko/pages/cavity3d.md',
             'docs/locales/ko/pages/thermal_steady2d.md',
             'docs/locales/ko/pages/thermal_simcase_independent_validation.md',
             'docs/thermal_simcase_independent_validation.md',
             'tests/thermal_simcase_independent_oracle.py',
             'tests/test_thermal_simcase_independent_validation.py',
             'tests/thermal_simcase_independent_stale.cjs'),
 'meshine': ('docs/overview.md', 'docs/locales/ko/pages/overview.md',),
 'gmshio': ('docs/overview.md', 'docs/locales/ko/pages/overview.md',),
 'physmat': ('docs/overview.md', 'docs/locales/ko/pages/overview.md',),
 'openphysics': ('docs/overview.md', 'docs/locales/ko/pages/overview.md',)}


def run(*args, cwd, env=None):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True)


def check_sdist_assets(sdist):
    """Require usable README links/examples, with the exact checked-out contents."""
    name, _ = parse_sdist_filename(sdist.name)
    with tarfile.open(sdist) as archive:
        # Strip the distribution-root component; no filesystem extraction occurs.
        files = {p.name.split("/", 1)[1]: p for p in archive.getmembers()
                 if p.isfile() and "/" in p.name}
        required = {"LICENSE", "README.md", "pyproject.toml", "PKG-INFO"}
        if name != "openphysics":
            required.add("NOTICE")
        if name == "simcase":
            required.add("simcase/studio/static/index.html")
        document_assets = DOCUMENT_ASSETS.get(name, ())
        required.update(document_assets)
        if missing := required - files.keys():
            raise RuntimeError(f"{sdist.name} is missing {sorted(missing)}")
        for relative in document_assets:
            source = ROOT / "packages" / name / relative
            if archive.extractfile(files[relative]).read() != source.read_bytes():
                raise RuntimeError(f"{sdist.name}: {relative} differs from the checked-out source")
        for relative, member in files.items():
            if not relative.endswith(".md"):
                continue
            text = archive.extractfile(member).read().decode("utf-8")
            # Current package docs use inline links/images with unspaced targets.
            # This is an archive-path check, not a general Markdown/network validator.
            for destination in re.findall(r"!?\[[^\]]*\]\(([^\s)]+)\)", text):
                url = urlsplit(destination)
                if url.scheme or url.netloc or not url.path:
                    continue
                target = posixpath.normpath(posixpath.join(
                    posixpath.dirname(relative), unquote(url.path)))
                if target not in files:
                    raise RuntimeError(
                        f"{sdist.name}: {relative} links to missing archive file {destination}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".validation" / "dist")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        parser.error("output must be empty to prevent stale distributions from passing validation")
    for name in PACKAGES:
        # The default build makes an sdist, then builds its wheel from that sdist.
        run(sys.executable, "-m", "build", "--no-isolation", "--outdir", output,
            ROOT / "packages" / name, cwd=ROOT)
    wheels = sorted(output.glob("*.whl"))
    sdists = sorted(output.glob("*.tar.gz"))
    if len(wheels) != len(PACKAGES) or len(sdists) != len(PACKAGES):
        raise RuntimeError("expected one sdist and one wheel per package")
    expected = {canonicalize_name(name) for name in PACKAGES}
    wheel_ids = {parse_wheel_filename(p.name)[:2] for p in wheels}
    sdist_ids = {parse_sdist_filename(p.name) for p in sdists}
    if wheel_ids != sdist_ids or {name for name, _ in wheel_ids} != expected:
        raise RuntimeError("wheel/sdist package identities and versions must match the seven packages")
    run(sys.executable, "-m", "twine", "check", "--strict", *wheels, *sdists, cwd=ROOT)
    for sdist in sdists:
        check_sdist_assets(sdist)
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            package_name = parse_wheel_filename(wheel.name)[0]
            for relative in RUNTIME_MODULE_ASSETS.get(package_name, ()):
                expected_bytes = (ROOT / "packages" / package_name / relative).read_bytes()
                if archive.read(relative) != expected_bytes:
                    raise RuntimeError(f"{wheel.name}: runtime module differs: {relative}")
            if package_name == "simcase":
                for relative in STUDIO_RESOURCE_ASSETS:
                    if archive.read(relative) != (ROOT / "packages/simcase" / relative).read_bytes():
                        raise RuntimeError(f"{wheel.name}: Studio resource differs: {relative}")
            if not any(p.endswith("/LICENSE") for p in names):
                raise RuntimeError(f"{wheel.name} is missing LICENSE")
            if not wheel.name.startswith("openphysics-") and not any(p.endswith("/NOTICE") for p in names):
                raise RuntimeError(f"{wheel.name} is missing NOTICE")
            if wheel.name.startswith("simcase-") and "simcase/studio/static/index.html" not in names:
                raise RuntimeError("simcase wheel is missing the Studio page")
    artifacts = wheels + sdists
    (output / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in artifacts))

    with tempfile.TemporaryDirectory(prefix="openphysics-wheel-check-") as directory:
        work = Path(directory).resolve()
        if work.is_relative_to(ROOT):
            raise RuntimeError("TMPDIR must be outside the checkout")
        env_root = work / "venv"
        venv.EnvBuilder(with_pip=True).create(env_root)
        bin_dir = env_root / ("Scripts" if os.name == "nt" else "bin")
        python = bin_dir / ("python.exe" if os.name == "nt" else "python")
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        env.update(PATH=str(bin_dir) + os.pathsep + env.get("PATH", ""), PYTHONNOUSERSITE="1",
                   MPLBACKEND="Agg", MPLCONFIGDIR=str(work / "matplotlib"),
                   OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
        # First resolve just the runtime/optional requirements from our local wheels.
        # Constraints pin versions without pre-installing undeclared dependencies.
        extras = {"simcase": "studio,test", "physmat": "rii", "gmshio": "gmsh"}
        requirements = []
        for wheel in wheels:
            name, _, _, _ = parse_wheel_filename(wheel.name)
            suffix = f"[{extras[name]}]" if name in extras else ""
            requirements.append(f"{name}{suffix} @ {wheel.as_uri()}")
        run(python, "-I", "-m", "pip", "install", "--only-binary=:all:", "--find-links", output,
            "-c", ROOT / "ci" / "requirements-py312-linux.txt", *requirements,
            cwd=work, env=env)
        run(python, "-I", "-m", "pip", "check", cwd=work, env=env)
        # Verify the new explicit submodules before any numerical consumer runs.
        runtime_expected = {
            relative[:-3].replace("/", ".").removesuffix(".__init__"):
                hashlib.sha256((ROOT / "packages" / package / relative).read_bytes()).hexdigest()
            for package, relatives in RUNTIME_MODULE_ASSETS.items() for relative in relatives
        }
        hash_manifest = output / "installed-module-hashes.json"
        hash_manifest.write_text(json.dumps(runtime_expected, indent=2) + "\n", encoding="utf-8")
        origin_probe = work / "transient_module_origins.py"
        origin_probe.write_text(
            "import hashlib, importlib, json, sys\nfrom pathlib import Path\n"
            + "expected = " + repr(runtime_expected) + "\n"
            + "report = {}\n"
            + "if not sys.flags.isolated: raise RuntimeError('isolated Python required')\n"
            + "for name, digest in expected.items():\n"
            + "    path = Path(importlib.import_module(name).__file__).resolve()\n"
            + "    actual = hashlib.sha256(path.read_bytes()).hexdigest()\n"
            + "    if not path.is_relative_to(Path(sys.prefix).resolve()): raise RuntimeError('module outside installed venv')\n"
            + "    if actual != digest: raise RuntimeError('installed runtime byte mismatch')\n"
            + "    report[name] = {'origin': str(path), 'sha256': actual}\n"
            + "Path(sys.argv[1]).write_text(json.dumps(report, indent=2) + '\\n', encoding='utf-8')\n"
            + "print(json.dumps(report), flush=True)\n", encoding="utf-8")
        run(python, "-I", origin_probe, output / "transient-module-origins.json", cwd=work, env=env)
        # Verify installed static resources as well as Python module origins.
        studio_resources = {relative: hashlib.sha256(
            (ROOT / "packages/simcase" / relative).read_bytes()).hexdigest()
            for relative in STUDIO_RESOURCE_ASSETS}
        resource_probe = work / "studio_resource_origins.py"
        resource_probe.write_text(
            "import hashlib, json, sys, simcase\nfrom pathlib import Path\n"
            + "expected = " + repr(studio_resources) + "\n"
            + "root = Path(simcase.__file__).resolve().parent.parent\n"
            + "if not sys.flags.isolated or not root.is_relative_to(Path(sys.prefix).resolve()): raise RuntimeError('installed resource root required')\n"
            + "report = {}\n"
            + "for relative, digest in expected.items():\n"
            + "    path = root / relative\n"
            + "    actual = hashlib.sha256(path.read_bytes()).hexdigest()\n"
            + "    if actual != digest: raise RuntimeError('installed Studio resource mismatch')\n"
            + "    report[relative] = {'origin': str(path), 'sha256': actual}\n"
            + "Path(sys.argv[1]).write_text(json.dumps(report, indent=2)+'\\n', encoding='utf-8')\n",
            encoding="utf-8")
        run(python, "-I", resource_probe, output / "studio-resource-origins.json", cwd=work, env=env)
        smoke = work / "wheel_smoke.py"
        shutil.copy2(ROOT / "ci" / "wheel_smoke.py", smoke)
        run(python, "-I", smoke, cwd=work, env=env)
        tests = work / "tests"
        tests.mkdir()
        for package, filename in (("simcase", "test_studio.py"), ("gmshio", "test_generate.py")):
            shutil.copy2(ROOT / "packages" / package / "tests" / filename, tests / filename)
        shutil.copy2(ROOT / "ci" / "test_transient_thermomechanical_wheel.py", tests / "test_transient_thermomechanical_wheel.py")
        shutil.copy2(ROOT / "ci" / "test_cavity_wheel.py", tests / "test_cavity_wheel.py")
        shutil.copy2(ROOT / "ci" / "test_multiphysics_wheel.py", tests / "test_multiphysics_wheel.py")
        shutil.copy2(ROOT / "ci" / "test_thermal_traction_wheel.py", tests / "test_thermal_traction_wheel.py")
        shutil.copy2(ROOT / "ci" / "test_thermoelasticity_wheel.py", tests / "test_thermoelasticity_wheel.py")
        shutil.copy2(ROOT / "ci" / "test_thermal_simcase_wheel.py", tests / "test_thermal_simcase_wheel.py")
        # Preserve the independent acceptance files verbatim in the installed suite.
        for package, filenames in (
            ("simcase", ("thermal_simcase_independent_oracle.py",
                         "test_thermal_simcase_independent_validation.py")),
            ("galerkin", ("thermal_mechanical_independent_oracle.py",
                          "test_thermal_mechanical_independent_validation.py",
                          "thermal_flux_robin_independent_oracle.py",
                          "test_thermal_flux_robin_independent_validation.py")),
        ):
            for filename in filenames:
                shutil.copy2(ROOT / "packages" / package / "tests" / filename, tests / filename)
        # Preserve producer contract/reference tests; independent all runs separately below.
        for package, filename in (("galerkin", "test_transient_heat.py"),
                                  ("galerkin-refsol", "test_transient_heat_reference.py")):
            shutil.copy2(ROOT / "packages" / package / "tests" / filename, tests / filename)
        # Run original headless contract/runtime/Studio/save tests from the verified sdist.
        simcase_sdist = next(p for p in sdists if parse_sdist_filename(p.name)[0] == "simcase")
        with tarfile.open(simcase_sdist) as archive:
            for filename in ("test_steady_boundary_schema.py", "test_steady_boundary_runtime.py",
                             "test_steady_boundary_platform.py", "test_studio_steady_boundary.py",
                             "test_steady_boundary_contract.py",
                             "test_transient_thermal_contract.py", "test_transient_thermal_runtime.py",
                             "test_studio_transient.py", "test_transient_headless_windows.py",
                             "test_studio_steady_thermal_http.py", "test_studio_thermal_acceptance.py",
                             "studio_thermal_independent_fixtures.py", "test_studio_thermal_lifecycle.py",
                             "test_studio_transient_server_http.py",
                             "studio_transient_lifecycle_fixtures.py",
                             "test_studio_transient_lifecycle.py",
                             "studio_transient_independent_fixtures.py",
                             "test_studio_transient_thermal_acceptance.py",
                             "transient_headless_independent_cases.py",
                             "transient_headless_independent_oracle.py",
                             "steady_boundary_independent_cases.py", "steady_boundary_independent_oracle.py"):
                member = next(p for p in archive.getmembers()
                              if p.isfile() and p.name.split("/", 1)[-1] == f"tests/{filename}")
                (tests / filename).write_bytes(archive.extractfile(member).read())
        # Hash the verified archived Studio consumer and its complete oracle closure.
        studio_consumer_files = ["studio_transient_independent_fixtures.py","test_studio_transient_thermal_acceptance.py","transient_headless_independent_cases.py","transient_headless_independent_oracle.py"]
        (output / "transient-studio-consumer-assets.json").write_text(
            json.dumps({name: hashlib.sha256((tests / name).read_bytes()).hexdigest()
                        for name in studio_consumer_files}, indent=2) + "\n", encoding="utf-8")
        # Execute the verified archived example, not a source-tree copy.
        examples = work / "examples"
        examples.mkdir()
        galerkin_sdist = next(p for p in sdists if parse_sdist_filename(p.name)[0] == "galerkin")
        with tarfile.open(galerkin_sdist) as archive:
            for filename in ("elasticity2d.py", "thermal_steady2d.py", "elasticity_traction.py",
                             "prescribed_temperature_thermoelasticity.py", "thermal_flux_robin.py",
                             "thermal_mechanical_workflow.py", "thermoelastic_traction.py",
                             "transient_heat_convergence.py", "transient_thermal_mechanical.py"):
                member = next(p for p in archive.getmembers()
                              if p.isfile() and p.name.split("/", 1)[-1] == f"examples/{filename}")
                (examples / filename).write_bytes(archive.extractfile(member).read())
            # Preserve new original acceptance files from the verified archive.
            for filename in ("test_transient_heat_tiny_domain.py",
                             "test_transient_heat_general_state.py",
                             "test_thermoelastic_traction.py",
                             "test_thermoelastic_traction_convergence.py",
                             "test_thermoelastic_traction_independent_validation.py",
                             "thermoelastic_traction_independent_oracle.py",
                             "thermoelastic_traction_independent_consumer.py"):
                member = next(p for p in archive.getmembers()
                              if p.isfile() and p.name.split("/", 1)[-1] == f"tests/{filename}")
                (tests / filename).write_bytes(archive.extractfile(member).read())
        refsol_sdist = next(p for p in sdists if parse_sdist_filename(p.name)[0] == "galerkin-refsol")
        with tarfile.open(refsol_sdist) as archive:
            filename = "test_thermoelastic_traction_reference.py"
            member = next(p for p in archive.getmembers()
                          if p.isfile() and p.name.split("/", 1)[-1] == f"tests/{filename}")
            (tests / filename).write_bytes(archive.extractfile(member).read())
        simcase_sdist = next(p for p in sdists if parse_sdist_filename(p.name)[0] == "simcase")
        with tarfile.open(simcase_sdist) as archive:
            for filename in ("thermal_slab.json", "thermal_mixed.json"):
                member = next(p for p in archive.getmembers()
                              if p.isfile() and p.name.split("/", 1)[-1] == f"examples/{filename}")
                (examples / filename).write_bytes(archive.extractfile(member).read())
        run(python, "-I", examples / "thermal_flux_robin.py", cwd=work, env=env)
        run(python, "-I", examples / "thermal_mechanical_workflow.py", cwd=work, env=env)
        run(python, "-I", examples / "transient_thermal_mechanical.py", cwd=work, env=env)
        run(python, "-I", examples / "thermoelastic_traction.py", cwd=work, env=env)
        run(python, "-I", tests / "thermoelastic_traction_independent_consumer.py", cwd=work, env=env)
        # No source conftest is copied; test_studio finds static files via simcase.__file__.
        run(python, "-I", "-m", "pytest", "-q", "-ra",
            "-o", "junit_logging=all", "-o", "junit_log_passing_tests=true", "--confcutdir", tests,
            f"--junitxml={output / 'wheel-tests.xml'}", tests, cwd=work, env=env)
        # Use only byte-verified sdist acceptance files outside the checkout.
        acceptance = work / "transient-acceptance"
        acceptance.mkdir()
        with tarfile.open(galerkin_sdist) as archive:
            for filename in ("transient_heat_independent_oracle.py",
                             "transient_heat_independent_cases.py",
                             "transient_heat_independent_consumer.py"):
                member = next(p for p in archive.getmembers()
                              if p.isfile() and p.name.split("/", 1)[-1] == f"tests/{filename}")
                (acceptance / filename).write_bytes(archive.extractfile(member).read())
        run(python, "-I", acceptance / "transient_heat_independent_consumer.py",
            "--expected-installed-root", env_root,
            "--expected-module-sha256", runtime_expected["galerkin.transient_heat"],
            "--suite", "all", cwd=work, env=env)
        # Full fixed n8..n64 convergence example, not a shortened smoke or core substitute.
        run(python, "-I", examples / "transient_heat_convergence.py", cwd=work, env=env)
        # Keep headless independent cases separate from pytest counts and engine PDE all.
        headless_acceptance = work / "transient-headless-acceptance"
        headless_acceptance.mkdir()
        with tarfile.open(simcase_sdist) as archive:
            for filename in ("transient_headless_independent_oracle.py",
                             "transient_headless_independent_cases.py",
                             "transient_headless_independent_consumer.py"):
                member = next(p for p in archive.getmembers()
                              if p.isfile() and p.name.split("/", 1)[-1] == f"tests/{filename}")
                (headless_acceptance / filename).write_bytes(archive.extractfile(member).read())
            filename = "transient_thermal_uniform.json"
            member = next(p for p in archive.getmembers()
                          if p.isfile() and p.name.split("/", 1)[-1] == f"examples/{filename}")
            document = examples / filename
            document.write_bytes(archive.extractfile(member).read())
        run(python, "-I", headless_acceptance / "transient_headless_independent_consumer.py",
            "--expected-installed-root", env_root,
            "--expected-module-hashes", hash_manifest, cwd=work, env=env)
        run(python, "-I", "-m", "simcase", "validate", document, cwd=work, env=env)
        run(python, "-I", "-m", "simcase", "run", document, "-q",
            "-o", work / "transient-headless-example", cwd=work, env=env)
        # Original steady-boundary independent cases run separately from pytest.
        steady_acceptance = work / "steady-boundary-acceptance"
        steady_acceptance.mkdir()
        with tarfile.open(simcase_sdist) as archive:
            for filename in ("steady_boundary_independent_oracle.py",
                             "steady_boundary_independent_cases.py",
                             "steady_boundary_independent_consumer.py"):
                member = next(p for p in archive.getmembers()
                              if p.isfile() and p.name.split("/", 1)[-1] == f"tests/{filename}")
                (steady_acceptance / filename).write_bytes(archive.extractfile(member).read())
        run(python, "-I", steady_acceptance / "steady_boundary_independent_consumer.py",
            "--expected-installed-root", env_root,
            "--expected-module-hashes", hash_manifest, cwd=work, env=env)
        # Consume the exact shipped steady boundary JSON through the installed CLI.
        with tarfile.open(simcase_sdist) as archive:
            member = next(p for p in archive.getmembers()
                          if p.isfile() and p.name.split("/", 1)[-1] == "examples/thermal_boundary.json")
            boundary_document = examples / "thermal_boundary.json"
            boundary_document.write_bytes(archive.extractfile(member).read())
        run(python, "-I", "-m", "simcase", "validate", boundary_document, cwd=work, env=env)
        run(python, "-I", "-m", "simcase", "run", boundary_document, "-q",
            "-o", work / "steady-boundary-example", cwd=work, env=env)
        # Run the original Node script against verified installed static bytes.
        # Node VM cases remain distinct from the real browser/public-API check.
        node_root = work / "studio-installed-node"
        (node_root / "tests").mkdir(parents=True)
        static = node_root / "simcase" / "studio" / "static"
        static.mkdir(parents=True)
        copy_resources = work / "copy_installed_studio_resources.py"
        copy_resources.write_text(
            "import hashlib, json, sys, simcase\nfrom pathlib import Path\n"
            + "expected = " + repr(studio_resources) + "\n"
            + "root = Path(simcase.__file__).resolve().parent.parent\n"
            + "target = Path(sys.argv[1])\n"
            + "if not sys.flags.isolated or not root.is_relative_to(Path(sys.prefix).resolve()): raise RuntimeError('installed resource root required')\n"
            + "for relative, digest in expected.items():\n"
            + "    data = (root / relative).read_bytes()\n"
            + "    if hashlib.sha256(data).hexdigest() != digest: raise RuntimeError('installed resource changed')\n"
            + "    (target / Path(relative).name).write_bytes(data)\n",
            encoding="utf-8")
        run(python, "-I", copy_resources, static, cwd=work, env=env)
        node_tests = []
        with tarfile.open(simcase_sdist) as archive:
            for filename in ("studio_steady_thermal.cjs", "studio_transient_thermal.cjs"):
                relative = "tests/" + filename
                member = next(p for p in archive.getmembers()
                              if p.isfile() and p.name.split("/", 1)[-1] == relative)
                node_test = node_root / relative
                node_test.write_bytes(archive.extractfile(member).read())
                node_tests.append(str(node_test))
        with (output / "studio-installed-node.tap").open("w", encoding="utf-8") as log:
            subprocess.run(["node", "--test", *node_tests], cwd=work, env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        # Small real-browser E2E uses these installed wheels, never source imports.
        browser_model = work / "studio-browser-model.json"
        browser_model.write_text(json.dumps({
            "openphysics": "0.2", "name": "Studio browser acceptance",
            "units": {"length": "m", "temperature": "K"},
            "geometry": {"domain": {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1}},
            "materials": {}, "physics": {"heat1": {"type": "thermal.steady2d",
                "conductivity_w_mk": 2, "heat_source_w_m3": 0,
                "dirichlet_temperature_k": {"left": 300, "right": 293}}},
            "mesh": {"subdivisions": [2, 2]}, "study": {"type": "single"},
            "results": {"save_fields": True, "plots": False}
        }, allow_nan=False), encoding="utf-8")
        run("node", ROOT / "ci/tools/studio_thermal_browser.mjs",
            "--python", python, "--model", browser_model, "--transient-model", document,
            "--source-commit", subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip(),
            "--expected-installed-root", env_root, "--expected-module-hashes", hash_manifest,
            "--output", output / "studio-browser", cwd=work, env=env)
    print(f"Validated {len(wheels)} wheels built from sdists; artifacts: {output}")


if __name__ == "__main__":
    main()
