# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Check installed distribution licenses against the reviewed inventory.

Reads metadata and RECORD file lists with importlib.metadata only, so no
license tool is needed. Every installed distribution must have a reviewed entry
in ci/third_party_licenses.json. The entry's SPDX expression must be allowed for
the strictest way the environment reaches the distribution:

- runtime: a base requirement of a first-party package (transitively)
- optional: a non-test extra of a first-party package
- test: a test-only extra of a first-party package (policy ``test_extras``)
- tool: installed but not required by first-party packages (CI tools)

Runtime and optional dependencies must be permissive. Weak copyleft (LGPL, MPL,
CeCILL-C) is accepted only for test/tool entries marked ``test_only``. GPL is accepted
only for ``external_process`` entries, and first-party code must not import
them. AGPL, SSPL and the other network-copyleft families under ``never_families``
are always rejected, also as external processes: any identifier of the family
(deprecated ids such as ``AGPL-3.0``, ``+`` forms and LicenseRef- names
included) in the inventory or in installed metadata fails. Installed metadata
that names a different expression, or a copyleft family the entry does not
record, also fails.

Bundled native files: every shared library (.so, .dylib, .dll) that a
third-party distribution installs, other than its own Python extension modules,
must match a ``bundled_files`` glob of its entry (fnmatch on the POSIX path
relative to site-packages, as listed in RECORD) recorded for the current OS.
Records whose SPDX expression is copyleft, or is not satisfied by ``permissive``
plus the reviewed ``bundled_permissive`` ids (proprietary and non-standard
terms such as LicenseRef- ids, FTL or Qhull), need a ``review``. These libraries
load into the Python process that runs OpenPhysics, so unless the owning entry
is an ``external_process`` tool, a GPL term must offer another option
(``FTL OR GPL-2.0-or-later``) or carry a runtime exception listed under
``runtime_exceptions`` (``WITH GCC-exception-3.1``). Statically linked code is
not visible this way and is reviewed by hand. First-party distributions must
contain no native files at all.

Use ``--python`` to inspect another interpreter's environment, e.g. a fresh
venv holding the installed wheels.
"""

import argparse
import ast
from collections import deque
import fnmatch
import importlib.metadata as metadata
import json
from pathlib import Path
import re
import subprocess
import sys

from packaging.markers import Marker
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "ci" / "third_party_licenses.json"
DOCS = (ROOT / "docs" / "third-party.md", ROOT / "docs" / "locales" / "ko" / "pages" / "third-party.md")
RANK = {"runtime": 0, "optional": 1, "test": 2, "tool": 3}
COPYLEFT = re.compile(r"\b(A?GPL|LGPL|MPL|EUPL|EPL|CDDL|SSPL|OSL|CPAL|RPL|CECILL|GENERAL PUBLIC|MOZILLA PUBLIC|AFFERO)",
                      re.IGNORECASE)
# GPL and AGPL identifiers (not LGPL): plain, deprecated, '+' and LicenseRef- forms.
STRONG_COPYLEFT = re.compile(r"(?:^|[^A-Za-z])A?GPL", re.IGNORECASE)
TOKEN = re.compile(r"\(|\)|[A-Za-z0-9.+:-]+")
# Shared libraries, and the Python extension modules that are not counted as bundled libraries.
SHARED_LIBRARY = re.compile(r"\.(so(\.[0-9]+)*|dylib|dll)$", re.IGNORECASE)
EXTENSION_MODULE = re.compile(r"(\.cpython-[^/]*\.so|\.abi3\.so|\.pyd)$", re.IGNORECASE)
COMPILED = re.compile(r"\.(so(\.[0-9]+)*|dylib|dll|pyd)$", re.IGNORECASE)
PLATFORMS = ("linux", "macos", "windows")
BUNDLED_FIELDS = {"glob", "spdx", "linkage", "platforms"}


def parse_expression(text):
    """Parse an SPDX expression into nested ('AND'|'OR', [...]) tuples or an id string."""
    tokens = TOKEN.findall(text)
    position = 0

    def peek():
        return tokens[position] if position < len(tokens) else None

    def take():
        nonlocal position
        position += 1
        return tokens[position - 1]

    def primary():
        token = take()
        if token == "(":
            node = disjunction()
            if take() != ")":
                raise ValueError(f"unbalanced SPDX expression: {text}")
        else:
            node = token
        if peek() == "WITH":
            take()
            node = f"{node} WITH {take()}"
        return node

    def chain(operator, operand):
        items = [operand()]
        while peek() == operator:
            take()
            items.append(operand())
        return items[0] if len(items) == 1 else (operator, items)

    def disjunction():
        return chain("OR", lambda: chain("AND", primary))

    node = disjunction()
    if position != len(tokens):
        raise ValueError(f"cannot parse SPDX expression: {text}")
    return node


def identifiers(node):
    if isinstance(node, str):
        return {node.split(" WITH ")[0]}
    return set().union(*(identifiers(item) for item in node[1]))


def satisfies(node, allowed):
    """OR needs one allowed branch; AND needs every term allowed."""
    if isinstance(node, str):
        return node.split(" WITH ")[0] in allowed
    test = any if node[0] == "OR" else all
    return test(satisfies(item, allowed) for item in node[1])


def environment_paths(python):
    if python is None:
        return list(sys.path)
    output = subprocess.run([str(python), "-I", "-c", "import json, sys; print(json.dumps(sys.path))"],
                            check=True, capture_output=True, text=True, encoding="utf-8").stdout
    return json.loads(output)


def declared_license(dist):
    md = dist.metadata
    expression = md.get("License-Expression")
    text = (md.get("License") or "").strip()
    short = text if text and "\n" not in text and len(text) <= 80 else ""
    classifiers = [c for c in md.get_all("Classifier") or [] if c.startswith("License ::")]
    return expression, short, classifiers


def reachability(dists, first_party, test_extras=frozenset({"test"})):
    """Strictest use class of every installed distribution reached from first-party packages."""
    by_name = {canonicalize_name(d.metadata["Name"]): d for d in dists}
    use = {}
    queue = deque()
    for name in first_party:
        if name in by_name:
            queue.append((name, frozenset(), "runtime", True))
    seen = set()
    while queue:
        name, extras, klass, is_first_party = queue.popleft()
        key = (name, extras, klass)
        if key in seen or name not in by_name:
            continue
        seen.add(key)
        if not is_first_party and RANK[klass] < RANK[use.get(name, "tool")]:
            use[name] = klass
        dist = by_name[name]
        provided = {canonicalize_name(e) for e in dist.metadata.get_all("Provides-Extra") or []}
        # A first-party package exposes every extra; dependencies only the ones requested.
        active = provided if is_first_party else extras
        for line in dist.requires or []:
            requirement = Requirement(line)
            marker = requirement.marker or Marker("python_version >= '0'")
            reached = None
            for extra in [""] + sorted(active):
                if marker.evaluate({"extra": extra}):
                    level = klass
                    if extra and is_first_party:
                        level = max(klass, "test" if extra in test_extras else "optional", key=RANK.get)
                    if reached is None or RANK[level] < RANK[reached]:
                        reached = level
            if reached is None:
                continue
            target = canonicalize_name(requirement.name)
            queue.append((target, frozenset(canonicalize_name(e) for e in requirement.extras), reached,
                          target in first_party))
    return use


def first_party_imports(modules):
    """Return first-party source and test files that import any of the given top-level modules."""
    offenders = []
    for path in sorted([*(ROOT / "packages").rglob("*.py"), *(ROOT / "tests").rglob("*.py")]):
        if any(part in {"build", ".eggs"} or part.endswith(".egg-info") for part in path.parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            if any(name.split(".")[0] in modules for name in names):
                offenders.append(path.relative_to(ROOT).as_posix())
                break
    return offenders


def current_platform():
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform in ("win32", "cygwin"):
        return "windows"
    return sys.platform


def never_pattern(families):
    """Match any identifier or metadata text of a never-allowed license family.

    A family name preceded by the start or a non-letter matches, so deprecated ids
    (AGPL-3.0), '+' forms, LicenseRef- names and classifier text are all caught.
    """
    names = "|".join(re.escape(family) for family in families)
    return re.compile(rf"(?:^|[^A-Za-z])(?:{names})", re.IGNORECASE)


def never_ids(ids, never):
    return sorted(i for i in ids if never.search(i))


def in_process_allowed(node, exceptions):
    """False when the expression leaves no option but a GPL term without a listed runtime exception."""
    if isinstance(node, str):
        identifier, _, exception = node.partition(" WITH ")
        return not STRONG_COPYLEFT.search(identifier) or exception in exceptions
    test = any if node[0] == "OR" else all
    return test(in_process_allowed(item, exceptions) for item in node[1])


def bundled_entry_errors(name, entry, policy):
    """Structure and license rules of one distribution's bundled_files records."""
    never = never_pattern(policy["never_families"])
    exceptions = set(policy["runtime_exceptions"])
    plain = set(policy["permissive"]) | set(policy["bundled_permissive"])
    errors = []
    globs = set()
    for item in entry.get("bundled_files", []):
        where = f"{name} bundled_files {item.get('glob')!r}"
        if missing := sorted(BUNDLED_FIELDS - item.keys()):
            errors.append(f"{where}: missing {missing}")
            continue
        if item["glob"] in globs:
            errors.append(f"{where}: duplicate glob")
        globs.add(item["glob"])
        try:
            tree = parse_expression(item["spdx"])
        except (ValueError, IndexError) as error:
            errors.append(f"{where}: {error}")
            continue
        if bad := never_ids(identifiers(tree), never):
            errors.append(f"{where}: {bad} is never allowed, also when bundled")
        elif "external_process" not in entry and not in_process_allowed(tree, exceptions):
            errors.append(f"{where}: {item['spdx']!r} is GPL without a listed runtime exception or another "
                          "option, and the library loads in-process; only an external_process entry may bundle it")
        if item["linkage"] != "dynamic":
            errors.append(f"{where}: separate library files are dynamic; record static code in 'bundled'")
        if not item["platforms"] or set(item["platforms"]) - set(PLATFORMS):
            errors.append(f"{where}: platforms must be a non-empty subset of {list(PLATFORMS)}")
        if not str(item.get("review", "")).strip():
            if COPYLEFT.search(item["spdx"]):
                errors.append(f"{where}: copyleft {item['spdx']!r} needs a review")
            elif not satisfies(tree, plain):
                errors.append(f"{where}: {item['spdx']!r} is not on the permissive lists and needs a review")
    return errors


def native_files(dist, pattern):
    """POSIX paths (relative to the distribution's base, as in RECORD) whose names match pattern."""
    return sorted(f.as_posix() for f in dist.files or () if pattern.search(f.name))


def bundled_libraries(dist):
    """Shared libraries a distribution installed, other than its own Python extension modules."""
    return [path for path in native_files(dist, SHARED_LIBRARY) if not EXTENSION_MODULE.search(path)]


def check_bundled(name, dist, items, platform):
    """Match every bundled shared library against the entry's reviewed bundled_files globs."""
    errors, matched = [], []
    if dist.files is None:
        return [f"{name} {dist.version}: no RECORD file list, so bundled native files cannot be checked"], matched
    for path in bundled_libraries(dist):
        hits = [item for item in items if fnmatch.fnmatchcase(path, item.get("glob", ""))]
        if not hits:
            errors.append(f"{name} {dist.version}: unrecorded bundled native library {path}; add a reviewed "
                          "bundled_files entry to the inventory")
            continue
        item = hits[0]
        if platform not in item.get("platforms", ()):
            errors.append(f"{name} {dist.version}: {path} matches {item['glob']!r}, recorded for "
                          f"{item.get('platforms')}, but is installed on {platform}; review and update it")
        matched.append({"file": path, "glob": item["glob"], "spdx": item.get("spdx")})
    return errors, matched


def check(paths, inventory, check_docs=True, platform=None):
    policy = inventory["policy"]
    permissive = set(policy["permissive"])
    weak = set(policy["weak_copyleft"])
    never = never_pattern(policy["never_families"])
    first_party = {canonicalize_name(n) for n in inventory["first_party"]}
    entries = {canonicalize_name(k): v for k, v in inventory["distributions"].items()}
    dists = {}
    for dist in metadata.distributions(path=paths):
        name = canonicalize_name(dist.metadata["Name"])
        dists.setdefault(name, dist)  # first on the path wins, as for imports
    test_extras = {canonicalize_name(e) for e in policy.get("test_extras", ["test"])}
    use = reachability(list(dists.values()), first_party, test_extras)
    platform = platform or current_platform()
    errors, report = [], {}
    for name, entry in sorted(entries.items()):
        errors += bundled_entry_errors(name, entry, policy)
    for name, dist in sorted(dists.items()):
        expression, short, classifiers = declared_license(dist)
        record = {"version": dist.version, "license_expression": expression, "license": short or None,
                  "classifiers": classifiers}
        if name in first_party:
            declared = expression or short
            if declared != "Apache-2.0":
                errors.append(f"{name}: first-party metadata must declare Apache-2.0, found {declared!r}")
            if compiled := native_files(dist, COMPILED):
                errors.append(f"{name}: first-party distribution contains native files {compiled}; "
                              "compiled code needs a license review first")
            report[name] = {**record, "use": "first-party", "spdx": "Apache-2.0"}
            continue
        entry = entries.get(name)
        klass = use.get(name, "tool")
        record["use"] = klass
        report[name] = record
        if entry is None:
            errors.append(f"{name} {dist.version}: no reviewed entry in {INVENTORY.relative_to(ROOT).as_posix()}")
            continue
        bundled_errors, bundled = check_bundled(name, dist, entry.get("bundled_files", []), platform)
        errors += bundled_errors
        if bundled:
            record["bundled_files"] = bundled
        record["spdx"] = entry["spdx"]
        try:
            tree = parse_expression(entry["spdx"])
        except (ValueError, IndexError) as error:
            errors.append(f"{name}: {error}")
            continue
        ids = identifiers(tree)
        if expression and expression.replace(" ", "") != entry["spdx"].replace(" ", ""):
            errors.append(f"{name} {dist.version}: metadata declares {expression!r}, inventory records "
                          f"{entry['spdx']!r}; review the change")
        declared_text = " ".join(filter(None, [expression, short, *classifiers]))
        recorded_copyleft = any(COPYLEFT.search(i) for i in ids)
        if COPYLEFT.search(declared_text) and not recorded_copyleft and "metadata_review" not in entry:
            errors.append(f"{name} {dist.version}: metadata mentions a copyleft license ({declared_text!r}) "
                          "but the inventory records none; review it")
        if never.search(declared_text):
            errors.append(f"{name} {dist.version}: metadata names a never-allowed license ({declared_text!r})")
        if bad := never_ids(ids, never):
            errors.append(f"{name}: {bad} in {entry['spdx']!r} is never allowed")
            continue
        if "external_process" in entry:
            record["use"] = "external-process"
            modules = set(entry["external_process"]["forbidden_imports"])
            if offenders := first_party_imports(modules):
                errors.append(f"{name} is external-process only but is imported by {offenders}")
            if klass == "runtime":
                errors.append(f"{name}: an external-process tool cannot be a base runtime requirement")
            continue
        allowed = permissive if klass in ("runtime", "optional") else (
            permissive | weak if entry.get("test_only") else permissive)
        if not satisfies(tree, allowed):
            errors.append(f"{name} {dist.version}: {entry['spdx']} is not allowed for {klass} use")
    if check_docs:
        for doc in DOCS:
            text = doc.read_text(encoding="utf-8")
            listed = {canonicalize_name(m) for m in re.findall(r"`([A-Za-z0-9._-]+)`", text)}
            if missing := sorted(set(entries) - listed):
                errors.append(f"{doc.relative_to(ROOT).as_posix()} does not list {missing}")
    return errors, report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--python", type=Path, help="interpreter whose environment to inspect")
    parser.add_argument("--report", type=Path, help="write the per-distribution report as JSON")
    parser.add_argument("--skip-docs", action="store_true", help="do not require the docs to list every entry")
    args = parser.parse_args()
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    errors, report = check(environment_paths(args.python), inventory, check_docs=not args.skip_docs)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    counts = {}
    for record in report.values():
        counts[record["use"]] = counts.get(record["use"], 0) + 1
    bundled = sum(len(record.get("bundled_files", ())) for record in report.values())
    print(f"Checked {len(report)} installed distributions: "
          + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
          + f"; {bundled} bundled shared libraries matched reviewed records")
    for error in errors:
        print("LICENSE CHECK FAILED:", error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
