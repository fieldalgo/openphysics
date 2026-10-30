# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Build all distributions, check their contents and exercise the wheels in a fresh venv.

Each sdist holds exactly its package code, README, LICENSE, NOTICE and build files,
and each wheel exactly its package code, all byte-identical to the checkout. The one
distribution with compiled code (``COMPILED``) also ships its Rust sources in the sdist
and exactly one extension module, built from them, in each wheel. Tests,
docs and examples live outside packages/ and are never shipped: the installed checks
copy the tracked test and example files of this checkout. The package test suites run against installed
wheels in tools/run_installed_tests.py; this script runs the wheel-specific
consumers, examples and independent acceptance scripts. Run with the pinned
validation requirements installed. No upload is performed. The temporary
directory, test copies and working directory are outside the checkout so neither
editable installs nor the root conftest can supply package code.
"""

import argparse
import functools
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tarfile
import venv
import zipfile

from packaging.utils import canonicalize_name, parse_sdist_filename, parse_wheel_filename

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("galerkin", "galerkin-refsol", "meshine", "meshloom", "gmshio", "physmat", "simcase", "sipi",
            "openphysics")
# packages/<name>/ holds what its distribution ships and nothing else: the import
# package under src/ and the files below. Tests, docs, examples and tools live at
# the repository root. Nothing here is a list of individual files.
SDIST_FILES = ("LICENSE", "NOTICE", "README.md", "pyproject.toml", "setup.py")
GENERATED_SDIST_FILES = ("PKG-INFO", "setup.cfg")
UNSHIPPED_FILES = (".gitignore",)
EGG_INFO = re.compile(r"(src/)?[^/]+\.egg-info/[^/]+")
STUDIO_STATIC = "simcase/studio/static/"
# Distributions allowed to contain compiled code (decision recorded with the project owner,
# docs/third-party.md): their extra top-level build files, the folder of their Rust
# sources, and the one extension module each wheel must contain.
COMPILED = {
    "meshloom": dict(files=("Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "THIRD_PARTY_NOTICES"),
                     sources="rust", extension=re.compile(r"meshloom/_kernel\.(abi3\.so|pyd)")),
}
# Platform tags of the compiled wheels a release publishes, one wheel each
# (release.yml builds them from the sdist; --assemble checks the set).
RELEASE_PLATFORMS = ("manylinux_2_17_x86_64", "manylinux_2_17_aarch64", "macosx_11_0_x86_64",
                     "macosx_11_0_arm64", "win_amd64")


def run(*args, cwd, env=None):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True)


@functools.cache
def tracked_repository():
    """Git-tracked files of the checkout, as repository-relative POSIX paths."""
    listing = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"],
                             check=True, capture_output=True).stdout.decode("utf-8")
    return frozenset(p for p in listing.split("\0") if p)


def source_commit():
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True, encoding="utf-8").stdout.strip()


def tracked(name):
    """Git-tracked files of packages/<name>/, relative to that directory."""
    prefix = f"packages/{name}/"
    return {p[len(prefix):] for p in tracked_repository() if p.startswith(prefix)}


def shipped_code(name):
    """Tracked files of the import package(s) under packages/<name>/src/, as sdist paths.

    Every tracked top-level entry must be a known file or src/, and src/ may hold only
    import packages (folders with __init__.py), so a new kind of file has to be
    classified here instead of shipping or vanishing silently.
    """
    files = tracked(name)
    compiled = COMPILED.get(name, {})
    code = set()
    for relative in files:
        top, _, rest = relative.partition("/")
        if not rest:
            if top not in SDIST_FILES + UNSHIPPED_FILES + compiled.get("files", ()):
                raise RuntimeError(f"packages/{name}/{top}: unclassified top-level file; "
                                   "ship it as package code or move it out of packages/")
        elif top == "src":
            package, _, inner = rest.partition("/")
            if not inner or f"src/{package}/__init__.py" not in files:
                raise RuntimeError(f"packages/{name}/src/{package}: src/ holds only import packages")
            code.add(relative)
        elif top == compiled.get("sources"):
            continue                                       # Rust sources: sdist only, see build_sources
        else:
            raise RuntimeError(f"packages/{name}/{top}/: only src/ is allowed; tests, docs, examples "
                               "and tools belong at the repository root")
    for required in ("LICENSE", "NOTICE", "README.md", "pyproject.toml"):
        if required not in files:
            raise RuntimeError(f"packages/{name}/{required} is not tracked")
    return code


def build_sources(name):
    """Tracked build inputs a compiled distribution ships in its sdist but not in its wheel."""
    compiled = COMPILED.get(name)
    if not compiled:
        return set()
    files = tracked(name)
    sources = {f for f in files if f.startswith(compiled["sources"] + "/")}
    for required in compiled["files"]:
        if required not in files:
            raise RuntimeError(f"packages/{name}/{required} is not tracked")
    return sources | set(compiled["files"])


def wheel_path(relative):
    """Where a shipped file sits in the wheel: 'src/simcase/cli.py' -> 'simcase/cli.py'."""
    return relative.removeprefix("src/")


def module_name(relative):
    """Import name of a shipped Python file, e.g. 'simcase/studio/__init__.py' -> 'simcase.studio'."""
    return relative[:-3].replace("/", ".").removesuffix(".__init__")


def archive_members(sdist):
    """Regular members of an sdist keyed by their path below the distribution root."""
    with tarfile.open(sdist) as archive:
        members = archive.getmembers()
        roots = {p.name.split("/", 1)[0] for p in members}
        if len(roots) != 1:
            raise RuntimeError(f"{sdist.name} must have exactly one top-level directory")
        for member in members:
            if not (member.isfile() or member.isdir()):
                raise RuntimeError(f"{sdist.name}: {member.name} is not a regular file or directory")
        return {p.name.split("/", 1)[1]: archive.extractfile(p).read()
                for p in members if p.isfile() and "/" in p.name}


def check_sdist(sdist):
    """The sdist holds exactly the package code, its top-level files and generated metadata."""
    name, _ = parse_sdist_filename(sdist.name)
    source = ROOT / "packages" / name
    files = archive_members(sdist)
    expected = shipped_code(name) | {f for f in SDIST_FILES if f in tracked(name)} | build_sources(name)
    for relative in sorted(expected):
        if relative not in files:
            raise RuntimeError(f"{sdist.name} is missing {relative}")
        if files[relative] != (source / relative).read_bytes():
            raise RuntimeError(f"{sdist.name}: {relative} differs from the checked-out source")
    if "PKG-INFO" not in files:
        raise RuntimeError(f"{sdist.name} is missing PKG-INFO")
    unexpected = sorted(f for f in files if f not in expected and f not in GENERATED_SDIST_FILES
                        and not EGG_INFO.fullmatch(f))
    if unexpected:
        raise RuntimeError(f"{sdist.name} ships files that are not package code: {unexpected}")
    return {relative: hashlib.sha256(files[relative]).hexdigest() for relative in sorted(expected)}


def check_wheel(wheel):
    """The wheel holds exactly the package code plus its dist-info, with LICENSE and NOTICE.

    A compiled distribution also holds exactly one extension module and its
    THIRD_PARTY_NOTICES; every other distribution must be a pure ``py3-none-any`` wheel.
    """
    name, version, _, tags = parse_wheel_filename(wheel.name)
    source = ROOT / "packages" / name
    compiled = COMPILED.get(name)
    if not compiled and {str(t) for t in tags} != {"py3-none-any"}:
        raise RuntimeError(f"{wheel.name}: a distribution without compiled code must be py3-none-any")
    if compiled and any(t.abi != "abi3" for t in tags):
        raise RuntimeError(f"{wheel.name}: the compiled kernel must be built for the stable ABI (abi3)")
    code = {wheel_path(relative): relative for relative in shipped_code(name)}
    with zipfile.ZipFile(wheel) as archive:
        names = [n for n in archive.namelist() if not n.endswith("/")]
        dist_info = {n for n in names if n.split("/", 1)[0].endswith(".dist-info")}
        for path, relative in sorted(code.items()):
            if path not in names:
                raise RuntimeError(f"{wheel.name} is missing {path}")
            if archive.read(path) != (source / relative).read_bytes():
                raise RuntimeError(f"{wheel.name}: {path} differs from the checked-out source")
        extensions = {n for n in names if compiled and compiled["extension"].fullmatch(n)}
        if compiled and len(extensions) != 1:
            raise RuntimeError(f"{wheel.name} must contain exactly one compiled extension, found {sorted(extensions)}")
        if unexpected := sorted(set(names) - set(code) - dist_info - extensions):
            raise RuntimeError(f"{wheel.name} ships files that are not package code: {unexpected}")
        # Every wheel must carry the package's own LICENSE and NOTICE unchanged, and a compiled
        # one the notices of what its extension links.
        for notice in ("LICENSE", "NOTICE") + (("THIRD_PARTY_NOTICES",) if compiled else ()):
            found = [p for p in dist_info if p.endswith(f".dist-info/licenses/{notice}")]
            if len(found) != 1:
                raise RuntimeError(f"{wheel.name} is missing dist-info/licenses/{notice}")
            if archive.read(found[0]) != (source / notice).read_bytes():
                raise RuntimeError(f"{wheel.name}: {notice} differs from the checked-out source")
    return {path: hashlib.sha256((source / relative).read_bytes()).hexdigest()
            for path, relative in sorted(code.items())}


def assemble(output, kernels):
    """Replace the locally built compiled wheels in output by the release's platform wheels.

    Each wheel in ``kernels`` must belong to a COMPILED distribution at the version of its
    sdist in output, pass check_wheel and twine, and the platforms must be exactly
    RELEASE_PLATFORMS for every compiled distribution. SHA256SUMS is rewritten.
    """
    sdists = {parse_sdist_filename(p.name)[0]: parse_sdist_filename(p.name)[1] for p in output.glob("*.tar.gz")}
    for name in COMPILED:
        for local in output.glob(f"{name.replace('-', '_')}-*.whl"):
            local.unlink()
    found = {name: set() for name in COMPILED}
    copied = []
    for wheel in sorted(Path(kernels).rglob("*.whl")):
        name, version, _, tags = parse_wheel_filename(wheel.name)
        if name not in found or sdists.get(name) != version:
            raise RuntimeError(f"{wheel.name}: not a compiled distribution at its sdist's version")
        # manylinux2014_<arch> is the legacy alias of manylinux_2_17_<arch> in a compressed tag set.
        platforms = {t.platform.replace("manylinux2014_", "manylinux_2_17_") for t in tags}
        if len(platforms) != 1 or not platforms <= set(RELEASE_PLATFORMS) or platforms & found[name]:
            raise RuntimeError(f"{wheel.name}: platform {sorted(platforms)} is not one new release platform")
        found[name] |= platforms
        target = output / wheel.name
        shutil.copy2(wheel, target)
        check_wheel(target)
        copied.append(target)
    for name, platforms in found.items():
        if platforms != set(RELEASE_PLATFORMS):
            raise RuntimeError(f"{name}: missing release wheels for {sorted(set(RELEASE_PLATFORMS) - platforms)}")
    run(sys.executable, "-m", "twine", "check", "--strict", *copied, cwd=ROOT)
    artifacts = sorted(output.glob("*.whl")) + sorted(output.glob("*.tar.gz"))
    (output / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in artifacts))
    print(f"Assembled {len(artifacts)} release files ({len(copied)} compiled wheels); artifacts: {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".validation" / "dist")
    parser.add_argument("--build-only", action="store_true",
                        help="stop after building, twine check and the content checks; "
                             "the release workflow uses this to build what it uploads")
    parser.add_argument("--assemble", type=Path, metavar="KERNELS",
                        help="after a --build-only run into --output: replace the compiled wheels by the "
                             "release platform wheels found under KERNELS and rewrite SHA256SUMS")
    args = parser.parse_args()
    output = args.output.resolve()
    if args.assemble:
        assemble(output, args.assemble.resolve())
        return
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
        raise RuntimeError(f"wheel/sdist package identities and versions must match the {len(PACKAGES)} packages")
    run(sys.executable, "-m", "twine", "check", "--strict", *wheels, *sdists, cwd=ROOT)
    for sdist in sdists:
        check_sdist(sdist)
    shipped = {}  # import-relative path -> SHA-256 of every shipped file
    for wheel in wheels:
        shipped.update(check_wheel(wheel))
    if "simcase/studio/static/index.html" not in shipped:
        raise RuntimeError("simcase wheel is missing the Studio page")
    artifacts = wheels + sdists
    (output / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in artifacts))
    if args.build_only:
        print(f"Built and checked {len(wheels)} wheels and {len(sdists)} sdists; artifacts: {output}")
        return

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
        # The openphysics meta distribution resolves its six requirements and the
        # extras it forwards from these same local wheels.
        extras = {"simcase": "studio,test", "physmat": "rii", "gmshio": "gmsh",
                  "openphysics": "studio,export,rii,sipi"}
        requirements = []
        for wheel in wheels:
            name, _, _, _ = parse_wheel_filename(wheel.name)
            suffix = f"[{extras[name]}]" if name in extras else ""
            requirements.append(f"{name}{suffix} @ {wheel.as_uri()}")
        run(python, "-I", "-m", "pip", "install", "--only-binary=:all:", "--find-links", output,
            "-c", ROOT / "tools" / "requirements-py312-linux.txt", *requirements,
            cwd=work, env=env)
        run(python, "-I", "-m", "pip", "check", cwd=work, env=env)
        # The installed wheels and their resolved dependencies must match the reviewed
        # license inventory (docs/third-party.md).
        run(sys.executable, ROOT / "tools" / "check_licenses.py", "--python", python,
            "--report", output / "licenses-installed.json", cwd=ROOT)
        # Every shipped module must import from the venv with the checked-out bytes
        # before any numerical consumer runs. __main__ modules would run a CLI.
        runtime_expected = {module_name(relative): digest for relative, digest in shipped.items()
                            if relative.endswith(".py") and not relative.endswith("/__main__.py")}
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
        studio_resources = {relative: digest for relative, digest in shipped.items()
                            if relative.startswith(STUDIO_STATIC)}
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
        # Installed consumers, tests and examples come from this checkout's tracked
        # files, copied outside it; distributions carry no tests or examples.
        # Every copied byte is recorded.
        repository = tracked_repository()
        copied = {}

        def copy(source, destination):
            relative = source.relative_to(ROOT).as_posix()
            if relative not in repository:
                raise RuntimeError(f"{relative} is not a tracked file")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied[destination.relative_to(work).as_posix()] = {
                "source": relative, "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}
            return destination

        smoke = copy(ROOT / "tools" / "wheel_consumers" / "wheel_smoke.py", work / "wheel_smoke.py")
        run(python, "-I", smoke, cwd=work, env=env)
        tests = work / "tests"
        examples = work / "examples"
        # Wheel-specific consumers. The package test suites (tests/) run against
        # installed wheels in their own job, tools/run_installed_tests.py.
        for source in sorted((ROOT / "tools" / "wheel_consumers").glob("test_*_wheel.py")):
            copy(source, tests / source.name)
        # Every tracked example of galerkin and simcase, flattened into examples/.
        for relative in sorted(repository):
            folder, _, filename = relative.rpartition("/")
            if folder in ("examples/galerkin", "examples/simcase"):
                destination = examples / filename
                if destination.exists():
                    raise RuntimeError(f"two examples are named {filename}")
                copy(ROOT / relative, destination)
        traction_acceptance = work / "traction-acceptance"
        for filename in ("thermoelastic_traction_independent_oracle.py",
                         "thermoelastic_traction_independent_consumer.py"):
            copy(ROOT / "tests" / "galerkin" / filename, traction_acceptance / filename)
        # Independent consumers run as their own scripts, apart from the pytest counts.
        acceptance = work / "transient-acceptance"
        for filename in ("transient_heat_independent_oracle.py",
                         "transient_heat_independent_cases.py",
                         "transient_heat_independent_consumer.py"):
            copy(ROOT / "tests" / "galerkin" / filename, acceptance / filename)
        headless_acceptance = work / "transient-headless-acceptance"
        for filename in ("transient_headless_independent_oracle.py",
                         "transient_headless_independent_cases.py",
                         "transient_headless_independent_consumer.py"):
            copy(ROOT / "tests" / "simcase" / filename, headless_acceptance / filename)
        steady_acceptance = work / "steady-boundary-acceptance"
        for filename in ("steady_boundary_independent_oracle.py",
                         "steady_boundary_independent_cases.py",
                         "steady_boundary_independent_consumer.py"):
            copy(ROOT / "tests" / "simcase" / filename, steady_acceptance / filename)
        # The Node tests read the Studio files at ../../packages/simcase/src/simcase/studio/static;
        # mirror that layout with the installed bytes.
        node_root = work / "studio-installed-node"
        node_tests = [str(copy(ROOT / "tests" / "simcase" / filename, node_root / "tests" / "simcase" / filename))
                      for filename in ("studio_steady_thermal.cjs", "studio_transient_thermal.cjs")]
        node_tests.extend(str(copy(path, node_root / "tests" / "simcase" / path.name))
                          for path in sorted((ROOT / "tests" / "simcase").glob("studio_workspace_*.cjs")))
        # The copies are working-tree bytes; say whether they match the commit.
        sources = sorted({entry["source"] for entry in copied.values()})
        unchanged = subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", "HEAD", "--", *sources],
                                   check=False).returncode == 0
        (output / "consumer-file-hashes.json").write_text(json.dumps(
            {"commit": source_commit(), "matches_commit": unchanged, "files": copied},
            indent=2, sort_keys=True) + "\n", encoding="utf-8")
        run(python, "-I", examples / "thermal_flux_robin.py", cwd=work, env=env)
        run(python, "-I", examples / "thermal_mechanical_workflow.py", cwd=work, env=env)
        run(python, "-I", examples / "transient_thermal_mechanical.py", cwd=work, env=env)
        run(python, "-I", examples / "thermoelastic_traction.py", cwd=work, env=env)
        run(python, "-I", traction_acceptance / "thermoelastic_traction_independent_consumer.py",
            cwd=work, env=env)
        # No source conftest is copied.
        run(python, "-I", "-m", "pytest", "-q", "-ra",
            "-o", "junit_logging=all", "-o", "junit_log_passing_tests=true", "--confcutdir", tests,
            f"--junitxml={output / 'wheel-tests.xml'}", tests, cwd=work, env=env)
        run(python, "-I", acceptance / "transient_heat_independent_consumer.py",
            "--expected-installed-root", env_root,
            "--expected-module-sha256", runtime_expected["galerkin.transient_heat"],
            "--suite", "all", cwd=work, env=env)
        # Full fixed n8..n64 convergence example, not a shortened smoke or core substitute.
        run(python, "-I", examples / "transient_heat_convergence.py", cwd=work, env=env)
        # Keep headless independent cases separate from pytest counts and engine PDE all.
        document = examples / "transient_thermal_uniform.json"
        run(python, "-I", headless_acceptance / "transient_headless_independent_consumer.py",
            "--expected-installed-root", env_root,
            "--expected-module-hashes", hash_manifest, cwd=work, env=env)
        run(python, "-I", "-m", "simcase", "validate", document, cwd=work, env=env)
        run(python, "-I", "-m", "simcase", "run", document, "-q",
            "-o", work / "transient-headless-example", cwd=work, env=env)
        # Original steady-boundary independent cases run separately from pytest.
        run(python, "-I", steady_acceptance / "steady_boundary_independent_consumer.py",
            "--expected-installed-root", env_root,
            "--expected-module-hashes", hash_manifest, cwd=work, env=env)
        # Consume the steady boundary example JSON through the installed CLI.
        boundary_document = examples / "thermal_boundary.json"
        run(python, "-I", "-m", "simcase", "validate", boundary_document, cwd=work, env=env)
        run(python, "-I", "-m", "simcase", "run", boundary_document, "-q",
            "-o", work / "steady-boundary-example", cwd=work, env=env)
        # Run the original Node script against verified installed static bytes.
        # Node VM cases remain distinct from the real browser/public-API check.
        static = node_root / "packages" / "simcase" / "src" / "simcase" / "studio" / "static"
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
        run("node", ROOT / "tools/studio_browser/studio_thermal_browser.mjs",
            "--python", python, "--model", browser_model, "--transient-model", document,
            "--region-model", examples / "thermal_regions.json",
            "--transient-region-model", examples / "transient_thermal_regions.json",
            "--source-commit", source_commit(),
            "--expected-installed-root", env_root, "--expected-module-hashes", hash_manifest,
            "--output", output / "studio-browser", cwd=work, env=env)
    print(f"Validated {len(wheels)} wheels built from sdists; artifacts: {output}")


if __name__ == "__main__":
    main()
