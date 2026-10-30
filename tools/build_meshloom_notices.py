# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Write or check packages/meshloom/THIRD_PARTY_NOTICES.

meshloom's compiled extension statically links Rust crates and the Rust
standard library. Their license texts must ship with every wheel, and they must
all be permissive. This script lists:

* the crates Cargo links into the extension on the wheel targets (normal,
  non-proc-macro dependencies of ``meshloom-kernel``), each with its own license
  file, and
* the standard-library crates that std, core and alloc can link on those
  targets, from the toolchain's ``rust-src`` component, with their license files.

It refuses any license expression that does not offer a permissive choice
(``PERMISSIVE``). ``--check`` compares the result with the committed file, so a
``Cargo.lock`` or toolchain change cannot leave the notices stale. Requires
``cargo`` and the ``rust-src`` component (``rustup component add rust-src``).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages/meshloom"
NOTICES = PACKAGE / "THIRD_PARTY_NOTICES"
TARGETS = ("x86_64-unknown-linux-gnu", "aarch64-unknown-linux-gnu", "x86_64-apple-darwin",
           "aarch64-apple-darwin", "x86_64-pc-windows-msvc")
PERMISSIVE = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Zlib", "0BSD", "Unicode-3.0",
              "Unlicense", "BSL-1.0", "Apache-2.0 WITH LLVM-exception"}
# Standard-library crates that cannot be linked on TARGETS (SGX, UEFI, WASI, Hermit, VEX, Motor OS,
# wasm allocators) and build-time or test-only crates of the library workspace.
STD_EXCLUDED = ("fortanix-sgx-abi", "r-efi", "r-efi-alloc", "wasip1", "wasip2", "wasip3", "wit-bindgen",
                "hermit-abi", "vex-sdk", "moto-rt", "dlmalloc", "cc", "shlex", "getopts", "rand", "rand_core",
                "rand_xorshift", "rustc-literal-escaper", "unwinding")
STD_IN_TREE = ("core", "alloc", "std", "std_detect", "unwind", "panic_unwind", "panic_abort")
LICENSE_FILE = re.compile(r"^(licen[cs]e|copying|copyright|notice)", re.I)


def run(*cmd: str, cwd: Path | None = None) -> str:
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8").stdout


def permissive_choice(expression: str) -> bool:
    """True when the SPDX expression can be satisfied with permissive licenses only.

    A small evaluator: ``OR`` needs one permissive side, ``AND`` needs both,
    ``X WITH exception`` is one license term, and ``/`` is the old spelling of ``OR``.
    """
    tokens = re.findall(r"\(|\)|[A-Za-z0-9.+\-]+", expression.replace("/", " OR "))
    pos = 0

    def term() -> bool:
        nonlocal pos
        if tokens[pos] == "(":
            pos += 1
            value = disjunction()
            pos += 1                                                   # ")"
            return value
        name = tokens[pos]
        pos += 1
        if pos < len(tokens) and tokens[pos] == "WITH":
            name = f"{name} WITH {tokens[pos + 1]}"
            pos += 2
        return name in PERMISSIVE

    def conjunction() -> bool:
        nonlocal pos
        value = term()
        while pos < len(tokens) and tokens[pos] == "AND":
            pos += 1
            value = term() and value
        return value

    def disjunction() -> bool:
        nonlocal pos
        value = conjunction()
        while pos < len(tokens) and tokens[pos] == "OR":
            pos += 1
            value = conjunction() or value
        return value

    try:
        result = disjunction()
    except IndexError:
        return False
    return result and pos == len(tokens)


def license_texts(directory: Path) -> list[tuple[str, str]]:
    files = sorted(p for p in directory.iterdir() if p.is_file() and LICENSE_FILE.match(p.name))
    return [(p.name, p.read_text(encoding="utf-8", errors="replace").strip()) for p in files]


def linked_crates() -> list[dict]:
    """Normal, non-proc-macro dependencies of the kernel on any wheel target."""
    found = {}
    for target in TARGETS:
        meta = json.loads(run("cargo", "metadata", "--format-version", "1", "--locked", "--filter-platform", target,
                              cwd=PACKAGE))
        packages = {p["id"]: p for p in meta["packages"]}
        nodes = {n["id"]: n for n in meta["resolve"]["nodes"]}
        root = meta["resolve"]["root"]
        stack, seen = [root], set()
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            for dep in nodes[node]["deps"]:
                kinds = {k["kind"] for k in dep["dep_kinds"]}
                pkg = packages[dep["pkg"]]
                is_macro = any("proc-macro" in t["kind"] for t in pkg["targets"])
                if kinds & {None, "normal"} and not is_macro:
                    stack.append(dep["pkg"])
        for node in seen - {root}:
            pkg = packages[node]
            found[(pkg["name"], pkg["version"])] = pkg
    return [found[k] for k in sorted(found)]


def std_components(sysroot: Path) -> list[tuple[str, str, Path]]:
    library = sysroot / "lib/rustlib/src/rust/library"
    if not library.is_dir():
        raise SystemExit("the rust-src component is missing: rustup component add rust-src")
    out = []
    for name in STD_IN_TREE:
        manifest = (library / name / "Cargo.toml").read_text(encoding="utf-8")
        out.append((name, re.search(r'^license\s*=\s*"([^"]+)"', manifest, re.M).group(1), library / name))
    builtins = library / "compiler-builtins/compiler-builtins"
    out.append(("compiler_builtins",
                re.search(r'^license\s*=\s*"([^"]+)"', (builtins / "Cargo.toml").read_text(encoding="utf-8"),
                          re.M).group(1), library / "compiler-builtins"))
    for crate in sorted((library / "vendor").iterdir()):
        name = crate.name.rsplit("-", 1)[0]
        if name in STD_EXCLUDED:
            continue
        manifest = (crate / "Cargo.toml").read_text(encoding="utf-8")
        out.append((crate.name, re.search(r'^license\s*=\s*"([^"]+)"', manifest, re.M).group(1), crate))
    return out


def render() -> str:
    _PRINTED.clear()
    sysroot = Path(run("rustc", "--print", "sysroot", cwd=PACKAGE).strip())
    toolchain = run("rustc", "--version", cwd=PACKAGE).strip()
    errors, parts = [], []
    parts.append("Third-party notices for meshloom's compiled extension\n"
                 "=====================================================\n\n"
                 "The extension (meshloom/_kernel.*) statically links the Rust crates and the\n"
                 "Rust standard library components listed below. meshloom's own code is under the\n"
                 "Apache License 2.0 (LICENSE, NOTICE). Where a component offers a choice of\n"
                 "licenses, the license files it ships are all reproduced.\n\n"
                 f"Generated by tools/build_meshloom_notices.py with {toolchain}.\n"
                 f"Targets: {', '.join(TARGETS)}.\n")
    for pkg in linked_crates():
        expr = pkg["license"] or "?"
        if not permissive_choice(expr):
            errors.append(f"{pkg['name']} {pkg['version']}: license {expr!r} offers no permissive choice")
        texts = license_texts(Path(pkg["manifest_path"]).parent)
        if not texts:
            errors.append(f"{pkg['name']} {pkg['version']}: no license file in the crate")
        parts.append(_section(f"{pkg['name']} {pkg['version']} (crate)", expr, pkg.get("repository") or "", texts))
    unicode = sysroot / "share/doc/rust/licenses/Unicode-3.0.txt"
    for name, expr, directory in std_components(sysroot):
        if not permissive_choice(expr):
            errors.append(f"std component {name}: license {expr!r} offers no permissive choice")
        texts = license_texts(directory)
        if not texts and name in STD_IN_TREE:
            texts = [("std license (MIT, chosen)", "Copyright (c) The Rust Project Developers "
                      "(see https://thanks.rust-lang.org)\n\n" + _mit_body(sysroot))]
        if name == "core" and unicode.is_file():
            texts.append(("Unicode data (library/core/src/unicode/unicode_data.rs)",
                          unicode.read_text(encoding="utf-8").strip()))
        parts.append(_section(f"{name} (Rust standard library)", expr, "https://github.com/rust-lang/rust", texts))
    if errors:
        raise SystemExit("non-permissive or undocumented components:\n- " + "\n- ".join(errors))
    return "\n".join(parts).rstrip() + "\n"


def _mit_body(sysroot: Path) -> str:
    text = (sysroot / "share/doc/rust/licenses/MIT.txt").read_text(encoding="utf-8")
    return text.split("\n", 3)[-1].strip() if text.startswith("MIT License") else text.strip()


_PRINTED: dict[str, str] = {}


def _section(title: str, expr: str, source: str, texts: list[tuple[str, str]]) -> str:
    """One component; a license text identical to one printed earlier is referenced, not repeated."""
    out = [f"\n{'-' * 78}\n{title}\nLicense: {expr}\n" + (f"Source: {source}\n" if source else "")]
    for name, body in texts:
        key = " ".join(body.split())
        if key in _PRINTED:
            out.append(f"\n[{name}] identical to the text printed under {_PRINTED[key]}\n")
        else:
            _PRINTED[key] = f"{title} [{name}]"
            out.append(f"\n[{name}]\n\n{body}\n")
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if the committed file differs")
    a = ap.parse_args()
    text = render()
    if a.check:
        current = NOTICES.read_text(encoding="utf-8") if NOTICES.is_file() else ""
        if current != text:
            print(f"{NOTICES.relative_to(ROOT)} is stale: run python tools/build_meshloom_notices.py", file=sys.stderr)
            return 1
        print(f"{NOTICES.relative_to(ROOT)} is current")
        return 0
    NOTICES.write_text(text, encoding="utf-8")
    print(f"wrote {NOTICES.relative_to(ROOT)} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
