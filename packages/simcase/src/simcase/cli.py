# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Command line:  simcase run model.json [-o outdir]  |  simcase validate model.json  |  simcase example NAME"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import examples
from .runner import run
from .schema import Document, DocumentError


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="simcase", description="run a simulation model document")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a document end to end")
    r.add_argument("model")
    r.add_argument("-o", "--out", default=None, help="output folder (default: <model>_results)")
    r.add_argument("-q", "--quiet", action="store_true")
    v = sub.add_parser("validate", help="check a document and print its summary")
    v.add_argument("model")
    e = sub.add_parser("example", help="print an example document")
    e.add_argument("name", choices=sorted(examples.EXAMPLES))
    args = ap.parse_args(argv)

    if args.cmd == "example":
        print(json.dumps(examples.EXAMPLES[args.name], indent=2))
        return 0
    try:
        doc = Document.load(args.model)
    except (DocumentError, json.JSONDecodeError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.cmd == "validate":
        print(doc.summary())
        return 0
    out = Path(args.out) if args.out else Path(args.model).with_suffix("").with_name(Path(args.model).stem + "_results")
    from .thermal import is_thermal, require_fresh_output
    from .transient_thermal_contract import is_transient_thermal
    tracking = doc["study"].get("tracking") if "study" in doc.data else None
    subspace = (isinstance(tracking, dict) and tracking.get("method") == "electric-l2-subspace-v1"
                and doc["study"].get("type") == "sweep")
    if subspace and os.path.lexists(out):
        print(f"error: subspace sweep output already exists: {out}; choose a fresh output directory", file=sys.stderr)
        return 1
    from .electric_joule import is_electric_joule, failure_evidence
    from galerkin.temperature_joule_heating import JouleConvergenceError
    if is_thermal(doc.data) or is_transient_thermal(doc.data) or is_electric_joule(doc.data):
        try:
            require_fresh_output(out)
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    try:
        result = run(doc, verbose=not args.quiet)
    except JouleConvergenceError as exc:
        print(json.dumps(failure_evidence(exc), allow_nan=False), file=sys.stderr)
        return 1
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    try:
        result.save(out)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    files = ["summary.json", "log.txt", "model.json"]
    if doc["results"].get("save_fields", True):
        files.append("fields.npz")
    if doc["results"].get("plots", True):
        files.append("results.png")
    print(f"results written to {out}/  ({', '.join(files)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

