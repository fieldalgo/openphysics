# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Command line:  simdoc run model.json [-o outdir]  |  simdoc validate model.json  |  simdoc example NAME"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import examples
from .runner import run
from .schema import Document, DocumentError


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="simdoc", description="run a simulation model document")
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
    result = run(doc, verbose=not args.quiet)
    result.save(out)
    print(f"results written to {out}/  (summary.json, fields.npz, results.png, log.txt, model.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
