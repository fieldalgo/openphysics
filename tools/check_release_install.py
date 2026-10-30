# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Install a release the way a user does and check it, before or after upload.

The release workflow runs this on Linux, macOS and Windows with Python 3.12 and
the newest CPython it tests. Unlike tools/check_distributions.py, which installs
against the pinned validation requirements without an index, third-party
requirements are resolved from PyPI here, as ``pip install openphysics`` would.

``--wheels DIR`` installs our wheels in DIR (built by
``check_distributions.py --build-only`` and, for meshloom's compiled kernel, one wheel
per platform) by file URL, so pip can only take our packages from there; of several
wheels of one distribution it takes the one this interpreter supports.
``--from-pypi VERSION --sha256sums FILE`` first waits until
PyPI serves every distribution at VERSION, requires PyPI's SHA-256 of every
uploaded file to equal FILE, and then installs from PyPI without a cache.

Either way it installs ``openphysics[studio,export,rii,sipi]`` into a fresh venv in a
temporary directory outside the checkout, runs ``pip check``, requires every
distribution at the release version, runs tools/wheel_consumers/wheel_smoke.py
from a copy, and writes a JSON report with the resolved environment.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import venv

ROOT = Path(__file__).resolve().parents[1]
DISTRIBUTIONS = ("galerkin", "galerkin-refsol", "meshine", "meshloom", "gmshio", "physmat", "simcase", "sipi",
                 "openphysics")
EXTRAS = "studio,export,rii,sipi"
PYPI = "https://pypi.org/pypi"


def run(*args, cwd, env=None, attempts=1, delay=60):
    command = list(map(str, args))
    for attempt in range(1, attempts + 1):
        print("+", " ".join(command), flush=True)
        result = subprocess.run(command, cwd=cwd, env=env, check=False)
        if result.returncode == 0:
            return
        if attempt < attempts:
            print(f"attempt {attempt} failed with exit {result.returncode}; retrying in {delay} s", flush=True)
            time.sleep(delay)
    raise subprocess.CalledProcessError(result.returncode, command)


def wheel_name(path):
    """Canonical distribution name and version from a wheel file name."""
    name, version = path.name.split("-")[:2]
    return name.replace("_", "-").lower(), version


def local_requirements(directory, supported=None):
    """One requirement per distribution: its wheel in directory that this interpreter supports.

    A pure distribution has exactly one (py3-none-any) wheel; a compiled one may have one
    per platform, and exactly one of them must match ``supported`` (this interpreter's tags).
    """
    from packaging.tags import sys_tags
    from packaging.utils import parse_wheel_filename

    supported = set(sys_tags()) if supported is None else set(supported)
    wheels = sorted(Path(directory).resolve().glob("*.whl"))
    by_name = {}
    for w in wheels:
        by_name.setdefault(wheel_name(w)[0], []).append(w)
    if sorted(by_name) != sorted(DISTRIBUTIONS):
        raise SystemExit(f"expected wheels for each of {DISTRIBUTIONS} in {directory}, found "
                         f"{[w.name for w in wheels]}")
    found = {}
    for name, candidates in by_name.items():
        usable = [w for w in candidates if set(parse_wheel_filename(w.name)[3]) & supported]
        if len(candidates) > 1 and len(usable) != 1:
            raise SystemExit(f"expected exactly one {name} wheel for this interpreter in {directory}, "
                             f"found {[w.name for w in usable] or 'none'} of {[w.name for w in candidates]}")
        found[name] = usable[0] if len(candidates) > 1 else candidates[0]
    versions = {wheel_name(w)[1] for w in wheels}
    if len(versions) != 1:
        raise SystemExit(f"wheels carry different versions: {sorted(versions)}")
    requirements = [f"{name}[{EXTRAS}] @ {w.as_uri()}" if name == "openphysics" else f"{name} @ {w.as_uri()}"
                    for name, w in sorted(found.items())]
    return versions.pop(), requirements


def pypi_files(name, version):
    """{filename: sha256} PyPI lists for one release, or None while it is not there yet."""
    try:
        with urllib.request.urlopen(f"{PYPI}/{name}/{version}/json", timeout=30) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    return {entry["filename"]: entry["digests"]["sha256"] for entry in data["urls"]}


def wait_for_pypi(version, sha256sums, timeout_s):
    """Wait until PyPI lists every expected file and require its hashes to match ours."""
    expected = {}
    for line in Path(sha256sums).read_text(encoding="utf-8").splitlines():
        digest, filename = line.split(maxsplit=1)
        expected[filename.lstrip("*")] = digest
    deadline = time.monotonic() + timeout_s
    while True:
        listed, missing = {}, []
        for name in DISTRIBUTIONS:
            files = pypi_files(name, version)
            if files is None:
                missing.append(name)
            else:
                listed.update(files)
        if not missing and set(expected) <= set(listed):
            break
        if time.monotonic() > deadline:
            raise SystemExit(f"PyPI does not list {missing or sorted(set(expected) - set(listed))} "
                             f"at {version} after {timeout_s} s")
        print(f"waiting for PyPI: {missing or sorted(set(expected) - set(listed))}", flush=True)
        time.sleep(30)
    mismatched = sorted(f for f in expected if listed[f] != expected[f])
    extra = sorted(set(listed) - set(expected))
    if mismatched or extra:
        raise SystemExit(f"PyPI files differ from the built release: hash mismatch {mismatched}, "
                         f"not built here {extra}")
    print(f"PyPI serves the {len(expected)} built files at {version} with identical SHA-256", flush=True)
    return {f: listed[f] for f in sorted(expected)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--wheels", type=Path, help="directory with the built wheels")
    source.add_argument("--from-pypi", metavar="VERSION", help="install this version from PyPI")
    parser.add_argument("--sha256sums", type=Path, help="SHA256SUMS of the built files (with --from-pypi)")
    parser.add_argument("--wait", type=int, default=1800, help="seconds to wait for PyPI (with --from-pypi)")
    parser.add_argument("--report", type=Path, required=True, help="JSON report to write")
    args = parser.parse_args(argv)

    report = {"python": sys.version, "implementation": platform.python_implementation(),
              "platform": platform.platform(), "machine": platform.machine()}
    if args.wheels:
        version, requirements = local_requirements(args.wheels)
        report["source"] = "local wheels"
        attempts = 1
    else:
        if not args.sha256sums:
            parser.error("--from-pypi needs --sha256sums")
        version = args.from_pypi
        report["source"] = "PyPI"
        report["pypi_sha256"] = wait_for_pypi(version, args.sha256sums, args.wait)
        requirements = [f"openphysics[{EXTRAS}]=={version}"]
        # The simple index can lag the JSON API for a few minutes after upload.
        attempts = 5
    report["version"] = version

    with tempfile.TemporaryDirectory(prefix="openphysics-release-install-") as directory:
        work = Path(directory).resolve()
        if work.is_relative_to(ROOT):
            raise SystemExit("TMPDIR must be outside the checkout")
        env_root = work / "venv"
        venv.EnvBuilder(with_pip=True).create(env_root)
        bin_dir = env_root / ("Scripts" if os.name == "nt" else "bin")
        python = bin_dir / ("python.exe" if os.name == "nt" else "python")
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
        env.update(PATH=str(bin_dir) + os.pathsep + env.get("PATH", ""), PYTHONNOUSERSITE="1",
                   MPLBACKEND="Agg", MPLCONFIGDIR=str(work / "matplotlib"),
                   OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
        # Our packages only as wheels; third-party wheels preferred, as most users get them.
        run(python, "-I", "-m", "pip", "install", "--no-cache-dir", "--prefer-binary",
            "--only-binary", ",".join(DISTRIBUTIONS), *requirements,
            cwd=work, env=env, attempts=attempts)
        run(python, "-I", "-m", "pip", "check", cwd=work, env=env)
        listing = subprocess.run([python, "-I", "-m", "pip", "list", "--format", "json"], cwd=work,
                                 env=env, check=True, capture_output=True, text=True, encoding="utf-8")
        installed = {entry["name"].lower(): entry["version"] for entry in json.loads(listing.stdout)}
        report["installed"] = dict(sorted(installed.items()))
        wrong = {name: installed.get(name) for name in DISTRIBUTIONS if installed.get(name) != version}
        if wrong:
            raise SystemExit(f"expected every distribution at {version}, got {wrong}")
        smoke = work / "wheel_smoke.py"
        shutil.copy2(ROOT / "tools" / "wheel_consumers" / "wheel_smoke.py", smoke)
        report["wheel_smoke_sha256"] = hashlib.sha256(smoke.read_bytes()).hexdigest()
        run(python, "-I", smoke, cwd=work, env=env)
    report["passed"] = True
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Installed openphysics[{EXTRAS}] {version} ({report['source']}) and passed the wheel smoke check")


if __name__ == "__main__":
    main()
