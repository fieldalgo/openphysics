# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Audit retained distribution artifacts without rebuilding or running consumers.

Use the exact checkout that produced the artifacts. This is an archive/byte audit,
not a substitute for strict metadata checks, installed consumers or platform CI.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def audit(source_root, artifacts):
    source_root = source_root.resolve()
    artifacts = artifacts.resolve()
    checker_path = source_root / "tools" / "check_distributions.py"
    spec = importlib.util.spec_from_file_location("_distribution_asset_checker", checker_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("distribution checker cannot be loaded")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    if checker.ROOT != source_root:
        raise RuntimeError("checker source root mismatch")
    sdists = sorted(artifacts.glob("*.tar.gz"))
    wheels = sorted(artifacts.glob("*.whl"))
    expected = {checker.canonicalize_name(name) for name in checker.PACKAGES}
    wheel_ids = [checker.parse_wheel_filename(p.name)[:2] for p in wheels]
    sdist_ids = [checker.parse_sdist_filename(p.name) for p in sdists]
    # One sdist per package; one wheel per pure package, and one or more platform
    # wheels for a package with compiled code (checker.COMPILED).
    compiled = {checker.canonicalize_name(name) for name in checker.COMPILED}
    pure_wheels = [i for i in wheel_ids if i[0] not in compiled]
    if (len(sdists) != len(expected) or len(set(sdist_ids)) != len(expected)
            or len(pure_wheels) != len(set(pure_wheels)) or len(wheel_ids) != len(set(wheels))
            or set(wheel_ids) != set(sdist_ids)
            or {name for name, _ in wheel_ids} != expected):
        raise RuntimeError(f"expected matching wheel/sdist pairs for all {len(expected)} packages")
    actual = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in wheels + sdists}
    recorded = {}
    for line in (artifacts / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) != 2:
            raise RuntimeError("malformed checksum entry")
        digest, name = fields
        if name in recorded or name not in actual:
            raise RuntimeError("duplicate or unexpected checksum entry")
        recorded[name] = digest
    if recorded != actual:
        raise RuntimeError("artifact checksums are missing or differ")
    sdist_files = {}
    for sdist in sdists:
        sdist_files[sdist.name] = checker.check_sdist(sdist)
    shipped = {}
    for wheel in wheels:
        package = checker.parse_wheel_filename(wheel.name)[0]
        for relative, digest in checker.check_wheel(wheel).items():
            shipped[f"{package}/{relative}"] = digest
    return {
        "scope": "retained checksums; exact sdist and wheel contents against the checkout",
        "source_root": str(source_root),
        "checker_sha256": hashlib.sha256(checker_path.read_bytes()).hexdigest(),
        "artifact_sha256": actual,
        "sdist_files": sum(map(len, sdist_files.values())),
        "shipped_sha256": shipped,
        "not_performed": ["build", "twine strict", "installed consumer", "numerical test",
                          "platform execution", "source Git provenance authentication"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--report", type=Path,
                        help="new JSON report path; existing files are never overwritten")
    args = parser.parse_args()
    report = audit(args.source_root, args.artifacts)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        with args.report.open("x", encoding="utf-8") as stream:
            stream.write(payload)
    print(payload, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
