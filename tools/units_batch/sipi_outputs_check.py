# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""P3-6: every output of every ``examples/sipi`` script, baseline against head (unshipped landing script).

Check P3-6 of the galerkin step (phase-3 units spec, landings L2 and L3). The galerkin
step keeps the monorepo's ``sipi`` working and its outputs byte-identical while it moves
or renames the galerkin names sipi uses. Each side runs in its own processes with its own
packages, so this is a script, not a committed test:

1. ``run --root TREE --out DIR``: runs each ``TREE/examples/sipi/*.py`` once, each in a
   fresh interpreter with only ``TREE/packages/*/src`` on ``PYTHONPATH`` (in the order of
   the root conftest), from its own fresh working directory that holds a copy of
   ``TREE/examples/sipi``. It keeps, per script, the exit code, stdout, stderr and every
   file in that working directory afterwards: the scripts' own copies and whatever the
   script wrote, wherever in the copy it wrote it. A separate interpreter with the same
   environment first checks that ``sipi``, ``galerkin``, ``meshine`` and ``physmat`` are
   imported from ``TREE/packages``.
2. ``compare --old DIR --new DIR``: the two runs must hold the same scripts, and per script
   the same exit code, the same stdout bytes and the same files with the same bytes.
   stderr is compared after each side's tree and working directory are replaced by fixed
   placeholders, because a warning names the file that raised it. It prints the counts
   and exits 1 on any difference.

Run from the repository root, with a worktree of the baseline B (the landing's merge base):

    git worktree add --detach <tmp>/base <B>
    python tools/units_batch/sipi_outputs_check.py run --root <tmp>/base --out <tmp>/sipi-old
    python tools/units_batch/sipi_outputs_check.py run --root . --out <tmp>/sipi-new
    python tools/units_batch/sipi_outputs_check.py compare --old <tmp>/sipi-old --new <tmp>/sipi-new
    git worktree remove --force <tmp>/base
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

FORMAT = "openphysics-sipi-outputs-v1"
TIMEOUT_S = 1800.0
PACKAGES = ("sipi", "galerkin", "meshine", "physmat")
ENVIRONMENT = {"MPLBACKEND": "Agg", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "PYTHONHASHSEED": "0",
               "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
ROOT_MARK, WORK_MARK = b"<root>", b"<work>"


def _sources(root: Path) -> list[Path]:
    return sorted(p / "src" for p in (root / "packages").iterdir() if (p / "src").is_dir())


def _environment(root: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env.update(ENVIRONMENT)
    env["PYTHONPATH"] = os.pathsep.join(str(p) for p in _sources(root))
    return env


def _files(directory: Path) -> dict[str, Path]:
    return {p.relative_to(directory).as_posix(): p for p in sorted(directory.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_origins(root: Path, env: dict) -> dict:
    code = ("import importlib, json, sys; "
            f"print(json.dumps({{n: importlib.import_module(n).__file__ for n in {PACKAGES!r}}}))")
    out = subprocess.run([sys.executable, "-s", "-c", code], cwd=root, env=env, capture_output=True, text=True,
                         encoding="utf-8", check=True).stdout
    origins = json.loads(out)
    packages = (root / "packages").resolve()
    for name, file in origins.items():
        if not Path(file).resolve().is_relative_to(packages):
            raise SystemExit(f"{name} was imported from {file}, not from {packages}")
    return {n: Path(f).resolve().relative_to(root.resolve()).as_posix() for n, f in origins.items()}


def run(root: Path, out: Path) -> None:
    root = root.resolve()
    scripts = sorted((root / "examples" / "sipi").glob("*.py"))
    if not scripts:
        raise SystemExit(f"no examples/sipi/*.py under {root}")
    if out.exists():
        raise SystemExit(f"{out} exists; give a new directory")
    env = _environment(root)
    manifest = {"format": FORMAT, "python": platform.python_version(), "platform": platform.platform(),
                "origins": _check_origins(root, env), "scripts": {}}
    for script in scripts:
        work = (out / script.stem).resolve()
        shutil.copytree(script.parent, work / "examples" / "sipi",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (work / "run").mkdir()
        started = time.perf_counter()
        done = subprocess.run([sys.executable, "-s", str(work / "examples" / "sipi" / script.name)],
                              cwd=work / "run", env=env, capture_output=True, timeout=TIMEOUT_S)
        seconds = time.perf_counter() - started
        (out / f"{script.stem}.stdout").write_bytes(done.stdout)
        (out / f"{script.stem}.stderr").write_bytes(done.stderr.replace(str(work).encode(), WORK_MARK)
                                                    .replace(str(root).encode(), ROOT_MARK))
        files = _files(work)
        manifest["scripts"][script.name] = {
            "returncode": done.returncode, "seconds": round(seconds, 1),
            "stdout_sha256": _sha256(done.stdout), "stdout_bytes": len(done.stdout),
            "files": {name: _sha256(path.read_bytes()) for name, path in files.items()}}
        written = sorted(set(files) - {f"examples/sipi/{p.name}" for p in scripts})
        print(f"{script.name}: exit {done.returncode}, {seconds:.1f} s, stdout {len(done.stdout)} bytes, "
              f"{len(written)} file(s) written {written}", flush=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def compare(old: Path, new: Path) -> int:
    a = json.loads((old / "manifest.json").read_text(encoding="utf-8"))
    b = json.loads((new / "manifest.json").read_text(encoding="utf-8"))
    problems = []
    for side, m in (("old", a), ("new", b)):
        if m.get("format") != FORMAT:
            problems.append(f"{side}: not a {FORMAT} manifest")
    if (a["python"], a["platform"]) != (b["python"], b["platform"]):
        problems.append(f"different interpreters: {a['python']} {a['platform']} and {b['python']} {b['platform']}")
    if set(a["scripts"]) != set(b["scripts"]):
        problems.append(f"different scripts: only old {sorted(set(a['scripts']) - set(b['scripts']))}, "
                        f"only new {sorted(set(b['scripts']) - set(a['scripts']))}")
    counts = {"scripts": 0, "exit 0": 0, "stdout bytes": 0, "files": 0, "file bytes": 0, "written files": 0,
              "stderr bytes": 0}
    for name in sorted(set(a["scripts"]) & set(b["scripts"])):
        x, y = a["scripts"][name], b["scripts"][name]
        stem = Path(name).stem
        counts["scripts"] += 1
        if x["returncode"] != y["returncode"]:
            problems.append(f"{name}: exit code {x['returncode']} -> {y['returncode']}")
        counts["exit 0"] += x["returncode"] == y["returncode"] == 0
        out_x, out_y = (old / f"{stem}.stdout").read_bytes(), (new / f"{stem}.stdout").read_bytes()
        if out_x != out_y:
            problems.append(f"{name}: stdout differs ({len(out_x)} and {len(out_y)} bytes)")
        counts["stdout bytes"] += len(out_y)
        err_x, err_y = (old / f"{stem}.stderr").read_bytes(), (new / f"{stem}.stderr").read_bytes()
        if err_x != err_y:
            problems.append(f"{name}: stderr differs after the path placeholders")
        counts["stderr bytes"] += len(err_y)
        if set(x["files"]) != set(y["files"]):
            problems.append(f"{name}: different files: only old {sorted(set(x['files']) - set(y['files']))}, "
                            f"only new {sorted(set(y['files']) - set(x['files']))}")
        for file in sorted(set(x["files"]) & set(y["files"])):
            data_x, data_y = (old / stem / file).read_bytes(), (new / stem / file).read_bytes()
            if data_x != data_y or x["files"][file] != y["files"][file]:
                problems.append(f"{name}: {file} differs")
            counts["files"] += 1
            counts["file bytes"] += len(data_y)
            counts["written files"] += not file.startswith("examples/sipi/")
    print(f"{counts['scripts']} scripts compared ({counts['exit 0']} exit 0 on both sides); stdout "
          f"{counts['stdout bytes']} bytes; {counts['files']} files, {counts['file bytes']} bytes "
          f"({counts['written files']} written by the scripts); stderr {counts['stderr bytes']} bytes")
    print(f"origins old {a['origins']}\norigins new {b['origins']}")
    for p in problems:
        print("DIFFERENT:", p)
    print("identical" if not problems else f"{len(problems)} difference(s)")
    return 1 if problems else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="run every examples/sipi script of one tree")
    r.add_argument("--root", type=Path, required=True)
    r.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("compare", help="compare two runs byte for byte")
    c.add_argument("--old", type=Path, required=True)
    c.add_argument("--new", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "run":
        run(args.root, args.out)
        return 0
    return compare(args.old, args.new)


if __name__ == "__main__":
    sys.exit(main())
