# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Command line:  simcase run model.json [-o outdir]  |  simcase validate model.json  |  simcase example NAME

Format 0.3 documents (``"openphysics": "0.3"``) also get ``simcase explain`` (every input with
its authored text and SI value) and ``simcase fix`` (apply the value-preserving fixes);
``validate`` and ``run`` print each component's extent line and every diagnostic, ``--json``
gives the same as JSON and ``--strict`` refuses warnings. Exit codes: 0 valid (and run
succeeded), 1 run failure, 2 document errors, 3 refused only because of ``--strict``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import examples
from .runner import run
from .schema import Document, DocumentError, declares_v03


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="simcase", description="run a simulation model document")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a document end to end")
    r.add_argument("model")
    r.add_argument("-o", "--out", default=None, help="output folder (default: <model>_results)")
    r.add_argument("-q", "--quiet", action="store_true")
    r.add_argument("--strict", action="store_true", help="refuse a format 0.3 document with unacknowledged warnings")
    v = sub.add_parser("validate", help="check a document and print its summary")
    v.add_argument("model")
    v.add_argument("--json", action="store_true", help="print the result as JSON")
    v.add_argument("--strict", action="store_true", help="exit 3 on unacknowledged warnings (format 0.3)")
    x = sub.add_parser("explain", help="list every input of a format 0.3 document with its SI value")
    x.add_argument("model")
    x.add_argument("--json", action="store_true", help="print the rows as JSON")
    f = sub.add_parser("fix", help="apply the value-preserving fixes of a format 0.3 document")
    f.add_argument("model")
    f.add_argument("--in-place", action="store_true", help="rewrite the file instead of printing the result")
    e = sub.add_parser("example", help="print an example document")
    e.add_argument("name", choices=sorted(examples.EXAMPLES))
    g = sub.add_parser("geometry", help="print the region complex of a version 1 geometry document (a diagnostic)")
    g.add_argument("model")
    g.add_argument("-c", "--component", default=None, help="component name (default: the only one)")
    args = ap.parse_args(argv)

    if args.cmd == "example":
        print(json.dumps(examples.EXAMPLES[args.name], indent=2))
        return 0
    if args.cmd == "geometry":
        return _geometry(args.model, args.component)
    try:
        raw = Path(args.model).read_bytes()
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if declares_v03(raw):
        return _format_03(args, raw)
    if args.cmd in ("explain", "fix"):
        print(f"error: simcase {args.cmd} reads format 0.3 documents; {args.model} is not one", file=sys.stderr)
        return 2
    try:
        doc = Document.load(args.model)
    except (DocumentError, json.JSONDecodeError, FileNotFoundError) as exc:
        if args.cmd == "validate" and args.json:
            print(json.dumps(_json_report(False, [], list(getattr(exc, "diagnostics", ())))))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.cmd == "validate":
        if args.json:
            print(json.dumps(_json_report(True, [], [])))
        else:
            print(doc.summary())
        return 0
    return _run(args, doc)


def _run(args, doc) -> int:
    out = Path(args.out) if args.out else Path(args.model).with_suffix("").with_name(Path(args.model).stem + "_results")
    from .registry import kind_of
    from .thermal import require_fresh_output
    data = doc.si if doc.si is not None else doc.data
    tracking = data["study"].get("tracking") if "study" in data else None
    subspace = (isinstance(tracking, dict) and tracking.get("method") == "electric-l2-subspace-v1"
                and data["study"].get("type") == "sweep")
    if subspace and os.path.lexists(out):
        print(f"error: subspace sweep output already exists: {out}; choose a fresh output directory", file=sys.stderr)
        return 1
    from .electric_joule import failure_evidence
    from galerkin.temperature_joule_heating import JouleConvergenceError
    if kind_of(doc.data).fresh_output:
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
    results = data.get("results", {})
    files = ["summary.json", "log.txt", "model.json"]
    if results.get("save_fields", True):
        files.append("fields.npz")
    if results.get("plots", True):
        files.append("results.png")
    print(f"results written to {out}/  ({', '.join(files)})")
    return 0


# -- format 0.3 -----------------------------------------------------------------------------------

def _json_report(valid: bool, extent, diagnostics, defaults=(), inputs=None) -> dict:
    return {"valid": valid, "extent": list(extent), "diagnostics": [d.as_dict() for d in diagnostics],
            "defaults_applied": list(defaults), "resolved_inputs": inputs or {}}


def _format_03(args, raw: bytes) -> int:
    from .diagnostics import error_lines, exit_code, render_text
    from .reader import dumps
    from .resolve import resolve_text
    if args.cmd == "fix":
        return _fix(args, raw)
    result = resolve_text(raw)
    doc = result.document()
    found = list(result.diagnostics)
    code = exit_code(found, getattr(args, "strict", False))
    if args.cmd == "validate":
        if args.json:
            print(dumps(_json_report(code == 0, result.extent, found, result.defaults_applied,
                                     doc.resolved_inputs() if doc is not None else result.inputs),
                        indent=2, ensure_ascii=False))
            return code
        for line in result.extent:
            print(line)
        if doc is not None:
            print(doc.summary())
        if found:
            print(render_text(found))
        return code
    if args.cmd == "explain":
        if doc is None:
            print(render_text(found), file=sys.stderr)
            return 2
        rows = explain_rows(result)
        if args.json:
            print(dumps(rows, indent=2, ensure_ascii=False))
        else:
            for row in rows:
                print(_explain_text(row))
        return 0
    if not args.quiet:
        for line in result.extent:
            print(line)
        if found:
            print(render_text(found))
    if code == 2:
        for line in error_lines(found):
            print(f"error: {line}", file=sys.stderr)
        return 2
    if code == 3:
        print("error: refused under --strict: the document has unacknowledged warnings (or an assumed library "
              "datum); acknowledge them with accept, or run without --strict", file=sys.stderr)
        return 3
    return _run(args, doc)


def explain_rows(result) -> list[dict]:
    """One row per input slot: every authored input, then every default the reader applied."""
    from .reader import display_path, split_path
    from .resolve import _MISSING, _lookup
    rows = [{"path": path, **entry, "default": False} for path, entry in result.inputs.items()]
    for d in result.defaults_applied:
        segments = split_path(d["path"])
        slot = result.table.match(segments, result.tree)
        quantity = slot[0].get("quantity") if slot else None
        value = _lookup(result.si, segments)
        row = {"path": display_path(segments), "authored": None, "value": None if value is _MISSING else value,
               "default": True, "reason": d["reason"], "default_value": d["value"]}
        if quantity is not None:
            from physmat.units import quantity as registry_quantity
            row["unit"] = registry_quantity(quantity).unit
        rows.append(row)
    return rows


def _explain_text(row: dict) -> str:
    value = row.get("value")
    unit = row.get("unit")
    shown = f"{value!r}" + (f" {unit}" if unit and unit != "1" else "")
    if row["default"]:
        return f"{row['path']}: default {json.dumps(row['default_value'], default=str)} = {shown}  ({row['reason']})"
    authored = row["authored"]
    written = authored if isinstance(authored, str) else json.dumps(authored, default=str)
    extra = f"  (length_unit {row['length_unit']})" if row.get("length_unit") else ""
    return f"{row['path']}: {written} = {shown}{extra}"


def _fix(args, raw: bytes) -> int:
    from .fix import apply_fixes
    report = apply_fixes(raw)
    if report.data is None:
        for problem in report.problems:
            print(f"error: {problem}", file=sys.stderr)
        return 2 if not report.readable else 1
    log = sys.stdout if args.in_place else sys.stderr
    for item in report.applied:
        print(f"fixed {item['path']}: {item['written']} -> {json.dumps(item['fix'], ensure_ascii=False)} "
              f"({item['code']})", file=log)
    for d in report.suggestions:
        shown = ", ".join(json.dumps(s.value, ensure_ascii=False) for s in d.suggestions)
        print(f"not applied: {d.path}: {d.code}, suggestion {shown} (changes the value; edit by hand)", file=log)
    if args.in_place:
        Path(args.model).write_bytes(report.data)
        print(f"{len(report.applied)} fix(es) written to {args.model}", file=log)
    else:
        sys.stdout.buffer.write(report.data) if hasattr(sys.stdout, "buffer") else \
            sys.stdout.write(report.data.decode("utf-8"))
        sys.stdout.flush()
    return 0


def _geometry(path: str, component: str | None) -> int:
    """The region complex of a version 1 geometry block, read from the file without the
    physics validation of ``Document.load`` so that every component the engine takes is shown."""
    from .geometry_document import GeometryError, parse
    from .geometry_engine import evaluate
    try:
        raw = Path(path).read_bytes()
        if declares_v03(raw):
            from .reader import loads
            data = loads(raw)
        else:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, DocumentError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    geometry = data.get("geometry") if isinstance(data, dict) else None
    if not isinstance(geometry, dict) or "version" not in geometry:
        print("error: the document has a 0.2 geometry block; the region complex needs a version 1 block "
              "(see docs/packages/simcase/geometry_document.md)", file=sys.stderr)
        return 2
    try:
        model = parse(data)
        rc = evaluate(model, component)
    except GeometryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(rc.summary(model))
    return 0


if __name__ == "__main__":
    sys.exit(main())
