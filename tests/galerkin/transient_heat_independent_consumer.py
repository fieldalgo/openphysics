# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Isolated installed-wheel acceptance. Run with python -I; no pytest required."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("independent acceptance module unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-installed-root", type=Path, required=True)
    parser.add_argument("--expected-module-sha256", required=True)
    parser.add_argument("--suite", choices=("core", "all"), default="all")
    args = parser.parse_args()
    import galerkin.transient_heat as module
    module_path = Path(module.__file__).resolve()
    prefix = args.expected_installed_root.resolve()
    if prefix not in module_path.parents:
        raise RuntimeError("module origin is outside expected installed root")
    digest = hashlib.sha256(module_path.read_bytes()).hexdigest()
    if digest != args.expected_module_sha256:
        raise RuntimeError("installed transient_heat.py SHA256 mismatch")
    here = Path(__file__).resolve().parent
    # Explicit own oracle/cases loading; never add a source checkout to sys.path.
    oracle_path = here/"transient_heat_independent_oracle.py"
    cases_path = here/"transient_heat_independent_cases.py"
    load_file("transient_heat_independent_oracle", oracle_path)
    cases = load_file("transient_heat_independent_cases", cases_path)
    names = ["TestTransientHeatIndependentCore", "TestTransientHeatIndependentContract",
             "TestTransientHeatIndependentWrongRuntime"]
    if args.suite == "all":
        names.append("TestTransientHeatIndependentPDE")
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(getattr(cases, n))
                               for n in names)
    print(json.dumps(dict(module_origin=str(module_path), sha256=digest,
                          python=sys.version, isolated=bool(sys.flags.isolated),
                          oracle_sha256=hashlib.sha256(oracle_path.read_bytes()).hexdigest(),
                          cases_sha256=hashlib.sha256(cases_path.read_bytes()).hexdigest(),
                          selected_suite=args.suite)), flush=True)
    if not sys.flags.isolated:
        raise RuntimeError("installed consumer must run under python -I")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps(dict(tests_run=result.testsRun, failures=len(result.failures),
                          errors=len(result.errors), skips=len(result.skipped))), flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
