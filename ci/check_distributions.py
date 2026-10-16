# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Build all distributions and exercise their wheels in an isolated temporary venv.

Run with the pinned validation requirements installed. No upload is performed.
The temporary directory, test copies and working directory are outside the checkout
so neither editable installs nor the root conftest can supply package code.
"""

import argparse
import hashlib
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
DOCUMENT_ASSETS = {'galerkin': ('galerkin/thermoelasticity.py',
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
 'galerkin-refsol': ('refsol/thermoelastic_traction.py',
                     'tests/test_thermoelastic_traction_reference.py',
                     'refsol/elasticity.py',
                     'refsol/thermal.py',
                     'refsol/elasticity_traction.py',
                     'refsol/thermoelasticity.py',
                     'docs/overview.md', 'docs/locales/ko/pages/overview.md',
                     'refsol/thermal_boundary.py'),
 'simcase': ('docs/cavity3d.md',
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
        smoke = work / "wheel_smoke.py"
        shutil.copy2(ROOT / "ci" / "wheel_smoke.py", smoke)
        run(python, "-I", smoke, cwd=work, env=env)
        tests = work / "tests"
        tests.mkdir()
        for package, filename in (("simcase", "test_studio.py"), ("gmshio", "test_generate.py")):
            shutil.copy2(ROOT / "packages" / package / "tests" / filename, tests / filename)
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
        # Execute the verified archived example, not a source-tree copy.
        examples = work / "examples"
        examples.mkdir()
        galerkin_sdist = next(p for p in sdists if parse_sdist_filename(p.name)[0] == "galerkin")
        with tarfile.open(galerkin_sdist) as archive:
            for filename in ("elasticity2d.py", "thermal_steady2d.py", "elasticity_traction.py",
                             "prescribed_temperature_thermoelasticity.py", "thermal_flux_robin.py",
                             "thermal_mechanical_workflow.py", "thermoelastic_traction.py"):
                member = next(p for p in archive.getmembers()
                              if p.isfile() and p.name.split("/", 1)[-1] == f"examples/{filename}")
                (examples / filename).write_bytes(archive.extractfile(member).read())
            # Preserve new original acceptance files from the verified archive.
            for filename in ("test_thermoelastic_traction.py",
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
        run(python, "-I", examples / "thermoelastic_traction.py", cwd=work, env=env)
        run(python, "-I", tests / "thermoelastic_traction_independent_consumer.py", cwd=work, env=env)
        # No source conftest is copied; test_studio finds static files via simcase.__file__.
        run(python, "-I", "-m", "pytest", "-q", "-ra", "--confcutdir", tests,
            f"--junitxml={output / 'wheel-tests.xml'}", tests, cwd=work, env=env)
    print(f"Validated {len(wheels)} wheels built from sdists; artifacts: {output}")


if __name__ == "__main__":
    main()
