"""Installed independent consumer: python -I, explicit origins and hashes."""
import argparse
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--expected-installed-root",type=Path,required=True)
    p.add_argument("--expected-module-hashes",type=Path,required=True,
                   help="UTF-8 JSON mapping exact installed module names to source SHA256")
    args=p.parse_args()
    if not sys.flags.isolated:
        raise RuntimeError("python -I required")
    expected=json.loads(args.expected_module_hashes.read_text(encoding="utf-8"))
    if not isinstance(expected,dict) or not expected:
        raise RuntimeError("nonempty explicit source hash mapping required")
    # Bind additional adapter modules after the exact implementation is reviewed.
    for required in ("simcase.schema","simcase.transient_thermal_contract","galerkin.transient_heat"):
        if required not in expected:
            raise RuntimeError("missing required module identity: "+required)
    origins={}
    for name,digest in expected.items():
        module=importlib.import_module(name)
        path=Path(module.__file__).resolve()
        if not path.is_relative_to(args.expected_installed_root.resolve()):
            raise RuntimeError("module outside installed root: "+name)
        actual=hashlib.sha256(path.read_bytes()).hexdigest()
        if actual!=digest:
            raise RuntimeError("source/installed byte mismatch: "+name)
        origins[name]={"origin":str(path),"sha256":actual}
    here=Path(__file__).resolve().parent
    load("transient_headless_independent_oracle",here/"transient_headless_independent_oracle.py")
    cases=load("transient_headless_independent_cases",here/"transient_headless_independent_cases.py")
    print(json.dumps({"kind":"installed_independent","modules":origins,
                     "isolated":bool(sys.flags.isolated)}),flush=True)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(cases.TestTransientHeadlessIndependent)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__=="__main__":
    raise SystemExit(main())
