# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Build sdists, rebuild wheels, and audit a fresh installed consumer on this OS."""
import argparse
from email.parser import BytesParser
import hashlib
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import venv
import zipfile

from packaging.utils import canonicalize_name, parse_wheel_filename

PACKAGES = {"galerkin": "galerkin", "galerkin-refsol": "refsol", "meshine": "meshine",
            "gmshio": "gmshio", "physmat": "physmat", "simcase": "simcase"}
ROOT = Path(__file__).resolve().parents[2]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".validation-platform")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "environment.json").write_text(json.dumps({
        "platform": platform.platform(), "python": sys.version,
        "commit": os.environ.get("GITHUB_SHA"),
        "scope": "six installed packages; external Gmsh not executed",
    }, indent=2)+"\n", encoding="utf-8")
    commands = []
    env = {**os.environ, "MPLBACKEND": "Agg", "OPENBLAS_NUM_THREADS": "1",
           "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}

    def run(*argv, cwd):
        index = len(commands)
        record = {"argv": list(map(str, argv)), "cwd": str(cwd), "exit": None}
        commands.append(record)
        try:
            with (output / f"command-{index:02d}.log").open("w", encoding="utf-8") as log:
                result = subprocess.run(list(map(str, argv)), cwd=cwd, env=env,
                                        stdout=log, stderr=subprocess.STDOUT)
            record["exit"] = result.returncode
            if result.returncode:
                raise RuntimeError(f"command {index} failed with exit {result.returncode}")
        finally:
            (output / "commands.json").write_text(json.dumps(commands, indent=2)+"\n", encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="openphysics-platform-") as directory:
        work = Path(directory).resolve()
        assert not work.is_relative_to(ROOT)
        sdists, wheels = output / "sdists", output / "wheels"
        sdists.mkdir()
        wheels.mkdir()
        expected = {}
        wheel_owners = {}
        manifest = {"packages": {}, "files": {}, "scope": "six installed packages; no external Gmsh execution"}
        for package, module in PACKAGES.items():
            source = ROOT / "packages" / package
            project = tomllib.loads((source / "pyproject.toml").read_text(encoding="utf-8"))["project"]
            before_wheels = set(wheels.glob("*.whl"))
            run(sys.executable, "-I", "-X", "utf8", "-m", "build", "--sdist",
                "--no-isolation", "--outdir", sdists, source, cwd=work)
            archives = [p for p in sdists.glob("*.tar.gz") if p not in expected]
            assert len(archives) == 1
            archive_path = archives[0]
            expected[archive_path] = digest(archive_path.read_bytes())
            with tarfile.open(archive_path) as archive:
                members = archive.getmembers()
                prefixes = {p.name.split("/")[0] for p in members}
                assert len(prefixes) == 1
                prefix = prefixes.pop()
                metadata = BytesParser().parsebytes(archive.extractfile(prefix + "/PKG-INFO").read())
                assert canonicalize_name(metadata["Name"]) == canonicalize_name(project["name"])
                assert metadata["Version"] == project["version"]
                for member in members:
                    assert not member.issym() and not member.islnk()
                for path in sorted((source / module).rglob("*")):
                    if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                        continue
                    relative = path.relative_to(source).as_posix()
                    data = path.read_bytes()
                    member = archive.getmember(prefix + "/" + relative)
                    assert archive.extractfile(member).read() == data, relative
                    manifest["files"][relative] = digest(data)
                extraction = work / package
                extraction.mkdir()
                archive.extractall(extraction, filter="data")
            run(sys.executable, "-I", "-X", "utf8", "-m", "build", "--wheel",
                "--no-isolation", "--outdir", wheels, extraction / prefix, cwd=work)
            created = set(wheels.glob("*.whl")) - before_wheels
            assert len(created) == 1, package
            wheel_path = created.pop()
            wheel_name, wheel_version, _, _ = parse_wheel_filename(wheel_path.name)
            assert wheel_name == canonicalize_name(project["name"])
            assert str(wheel_version) == project["version"]
            with zipfile.ZipFile(wheel_path) as wheel_archive:
                metadata_names = [n for n in wheel_archive.namelist() if n.endswith(".dist-info/METADATA")]
                assert len(metadata_names) == 1, wheel_path.name
                metadata = BytesParser().parsebytes(wheel_archive.read(metadata_names[0]))
                assert canonicalize_name(metadata["Name"]) == wheel_name
                assert metadata["Version"] == project["version"]
            wheel_owners[wheel_path.name] = module
            manifest["packages"][module] = package
        wheel_files = sorted(wheels.glob("*.whl"))
        assert len(wheel_files) == len(PACKAGES) == 6
        wheel_entries = {}
        for wheel in wheel_files:
            with zipfile.ZipFile(wheel) as archive:
                names = archive.namelist()
                assert any(n.endswith("/LICENSE") for n in names), wheel.name
                assert any(n.endswith("/NOTICE") for n in names), wheel.name
                for relative in manifest["files"]:
                    if relative in names:
                        assert relative.split("/")[0] == wheel_owners[wheel.name], relative
                        data = archive.read(relative)
                        assert digest(data) == manifest["files"][relative], relative
                        assert relative not in wheel_entries, relative
                        wheel_entries[relative] = digest(data)
        assert wheel_entries == manifest["files"], "missing package code or bundled asset in wheel"
        (output / "package-byte-manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
        (output / "SHA256SUMS").write_text("".join(
            digest(p.read_bytes())+"  "+p.relative_to(output).as_posix()+"\n"
            for p in [*sorted(sdists.glob("*.tar.gz")), *wheel_files]), encoding="utf-8")

        venv.EnvBuilder(with_pip=True).create(work / "venv")
        python = work / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        # Exact existing validation pins, without the Linux-only external Gmsh
        # executable/keyring stack. No new runtime dependency is introduced.
        pins = ROOT / "ci" / "requirements-py312-windows-thermal.txt"
        run(python, "-I", "-X", "utf8", "-m", "pip", "install", "-r", pins, cwd=work)
        run(python, "-I", "-X", "utf8", "-m", "pip", "install", "--no-index", "--no-deps",
            *wheel_files, cwd=work)
        run(python, "-I", "-m", "pip", "check", cwd=work)
        run(python, "-I", "-m", "pip", "freeze", "--all", cwd=work)
        tests = work / "tests"
        tests.mkdir()
        copies = {
            ROOT / "ci" / "test_transient_thermomechanical_wheel.py": tests / "test_transient_thermomechanical_wheel.py",
            ROOT / "ci" / "test_platform_install.py": tests / "test_platform_install.py",
            ROOT / "ci" / "test_thermal_simcase_wheel.py": tests / "test_thermal_simcase_wheel.py",
            ROOT / "packages/simcase/tests/test_simcase.py": tests / "original_scalar.py",
            ROOT / "packages/gmshio/tests/test_msh.py": tests / "test_msh.py"}
        for source, destination in copies.items():
            shutil.copy2(source, destination)
        shutil.copytree(ROOT / "packages/gmshio/tests/data", tests / "data")
        (work / "examples").mkdir()
        for name in ("thermal_slab.json", "thermal_mixed.json"):
            shutil.copy2(ROOT / "packages/simcase/examples" / name, work / "examples" / name)
        # These consumers and fixtures come from this exact checkout, not from
        # the rebuilt package archives. Record every copied byte explicitly.
        copied = {p.relative_to(work).as_posix(): digest(p.read_bytes())
                  for directory in (tests, work / "examples")
                  for p in sorted(directory.rglob("*")) if p.is_file()}
        (output / "consumer-test-hashes.json").write_text(json.dumps({
            "source": "checkout test/fixture copies", "files": copied,
        }, indent=2)+"\n", encoding="utf-8")
        env["OPENPHYSICS_INSTALL_MANIFEST"] = str(output / "package-byte-manifest.json")
        env["OPENPHYSICS_INSTALL_REPORT"] = str(output / "installed-origins.json")
        run(python, "-I", "-X", "utf8", tests / "test_platform_install.py", cwd=work)
        run(python, "-I", "-X", "utf8", "-m", "pytest", "-q", "-ra",
            "--confcutdir", tests, "--basetemp", output / "consumer-files",
            "--junitxml=" + str(output / "installed-tests.xml"),
            tests / "test_thermal_simcase_wheel.py",
            tests / "test_transient_thermomechanical_wheel.py",
            tests / "test_msh.py",
            str(tests / "original_scalar.py")+"::test_slab_te_matches_refsol_through_the_whole_chain",
            cwd=work)


if __name__ == "__main__":
    main()
