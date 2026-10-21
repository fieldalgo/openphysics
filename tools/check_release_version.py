# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Check that the seven distributions agree on one release version.

All seven distributions release in lockstep. This check fails unless

- every packages/<name>/pyproject.toml declares the same version,
- every import package's ``__version__`` (read from its source, not imported)
  equals that version,
- every requirement between our own distributions, runtime or extra, admits
  that version and stops before the next minor series, and
- CHANGELOG.md has a ``## [Unreleased]`` section or a section for that version.

With ``--tag vX.Y.Z`` (a release), the tag must name that version and
CHANGELOG.md must have a dated ``## [X.Y.Z] - YYYY-MM-DD`` section. Run it from
the repository root as a file: ``python tools/check_release_version.py``.
"""

import argparse
import ast
from pathlib import Path
import re
import sys
import tomllib

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
SECTION = re.compile(r"^## \[(?P<name>[^\]]+)\](?: - (?P<date>\d{4}-\d{2}-\d{2}))?\s*$", re.M)


def pyprojects(root):
    return {path.parent.name: tomllib.loads(path.read_text(encoding="utf-8"))
            for path in sorted((root / "packages").glob("*/pyproject.toml"))}


def source_version(init):
    """The string assigned to ``__version__`` at module level of an __init__.py."""
    for node in ast.parse(init.read_text(encoding="utf-8")).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and getattr(node.targets[0], "id", None) == "__version__"
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
            return node.value.value
    return None


def check(root=ROOT, tag=None):
    """Return (version, errors); errors is empty when everything agrees."""
    errors = []
    projects = pyprojects(root)
    if not projects:
        return None, ["no packages/*/pyproject.toml found"]
    versions = {name: data["project"]["version"] for name, data in projects.items()}
    distinct = sorted(set(versions.values()))
    if len(distinct) != 1:
        errors.append(f"pyproject versions differ: {versions}")
        return None, errors
    version = distinct[0]
    parsed = Version(version)
    if str(parsed) != version:
        errors.append(f"version {version!r} is not in normalized form ({parsed})")
    next_series = Version(f"{parsed.major}.{parsed.minor + 1}")

    for name in projects:
        for init in sorted((root / "packages" / name / "src").glob("*/__init__.py")):
            found = source_version(init)
            relative = init.relative_to(root).as_posix()
            if found is None:
                errors.append(f"{relative}: no __version__ string")
            elif found != version:
                errors.append(f"{relative}: __version__ {found!r} != {version!r}")

    ours = {canonicalize_name(name) for name in projects}
    for name, data in projects.items():
        project = data["project"]
        groups = {"dependencies": project.get("dependencies", [])}
        for extra, requirements in project.get("optional-dependencies", {}).items():
            groups[f"optional-dependencies.{extra}"] = requirements
        for group, requirements in groups.items():
            for text in requirements:
                requirement = Requirement(text)
                if canonicalize_name(requirement.name) not in ours:
                    continue
                where = f"packages/{name}/pyproject.toml {group}: {text!r}"
                if not requirement.specifier.contains(parsed, prereleases=True):
                    errors.append(f"{where} does not admit {version}")
                if requirement.specifier.contains(next_series, prereleases=True):
                    errors.append(f"{where} admits {next_series}; bound it below the next minor series")

    changelog = root / "CHANGELOG.md"
    if not changelog.is_file():
        errors.append("CHANGELOG.md is missing")
        return version, errors
    sections = {m["name"]: m["date"] for m in SECTION.finditer(changelog.read_text(encoding="utf-8"))}
    if tag is not None:
        if tag != f"v{version}":
            errors.append(f"tag {tag!r} does not name version {version!r}; expected v{version}")
        if not sections.get(version):
            errors.append(f"CHANGELOG.md has no dated '## [{version}] - YYYY-MM-DD' section")
    elif "Unreleased" not in sections and version not in sections:
        errors.append(f"CHANGELOG.md has neither '## [Unreleased]' nor '## [{version}]'")
    return version, errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tag", help="release tag, for example v0.1.0")
    args = parser.parse_args(argv)
    version, errors = check(ROOT, args.tag)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"all distributions at {version}" + (f", tag {args.tag}" if args.tag else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
