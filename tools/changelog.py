# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Check and assemble changelog fragments.

A change records its changelog entry as one fragment, ``changelog.d/<slug>.md``,
instead of editing CHANGELOG.md, so concurrent changes do not conflict there::

    # Fixed

    ## English

    - `galerkin`: what changed. [Shape derivatives](docs/packages/galerkin/shape_derivative.md).

    ## 한국어

    - `galerkin`: 바뀐 내용. [형상 미분](packages/galerkin/shape_derivative.md).

The slug is lowercase letters, digits and hyphens. The ``#`` heading is one Keep a
Changelog category. Each language section holds the bullets exactly as they will
appear: English links are relative to CHANGELOG.md, Korean links to
docs/locales/ko/pages/changelog.md. changelog.d/ holds only fragments.

``--check`` fails unless every fragment is well formed and its links resolve.
``--assemble`` (in the version-change PR) inserts the bullets at the top of the
category's ``###`` subsection of ``## [Unreleased]`` in both changelogs, adding the
subsection when it is missing, fragments in slug order, then deletes the fragments.
Existing lines are not moved or rewritten; bullets at the top of ``[Unreleased]``
outside any ``###`` subsection stay there. Run it from the repository root as a
file: ``python tools/changelog.py --check``.
"""

import argparse
import os
import importlib.util
from pathlib import Path
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
FRAGMENTS = "changelog.d"
CATEGORIES = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")
# language section heading -> the changelog its bullets go into
PAGES = {"English": "CHANGELOG.md", "한국어": "docs/locales/ko/pages/changelog.md"}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
UNRELEASED = re.compile(r"^## \[Unreleased\]\s*$")

_spec = importlib.util.spec_from_file_location(
    "check_markdown_links", Path(__file__).resolve().parent / "check_markdown_links.py")
links = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(links)


def fragments(root=ROOT):
    """Every file in changelog.d/, sorted by name."""
    folder = root / FRAGMENTS
    return sorted(p for p in folder.iterdir() if p.is_file()) if folder.is_dir() else []


def parse(path):
    """Return (category, {language: bullets}, errors) for one fragment."""
    name = f"{FRAGMENTS}/{path.name}"
    if not SLUG.match(path.name):
        return None, {}, [f"{name}: name must be <slug>.md, the slug lowercase letters, digits and hyphens"]
    errors, category, sections, current, fence = [], None, {}, None, None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        marker = links.FENCE.match(line)
        if marker and fence is None:
            fence = marker.group(1)
        elif marker and marker.group(1) == fence:
            fence = None
        if fence is not None or marker:
            if current is None:
                errors.append(f"{name}: text outside a language section: {line.strip()!r}")
            else:
                sections[current].append(line.rstrip())
        elif line.startswith("# "):
            if category is not None or sections:
                errors.append(f"{name}: one '# <Category>' heading, first")
            category = line[2:].strip()
            if category not in CATEGORIES:
                errors.append(f"{name}: category {category!r} is not one of {', '.join(CATEGORIES)}")
        elif line.startswith("## "):
            current = line[3:].strip()
            if category is None:
                errors.append(f"{name}: the '# <Category>' heading comes first")
            if current not in PAGES:
                errors.append(f"{name}: section {current!r} is not one of {', '.join(PAGES)}")
            elif current in sections:
                errors.append(f"{name}: section {current!r} appears twice")
            sections.setdefault(current, [])
        elif line.lstrip().startswith("#"):
            errors.append(f"{name}: no other headings: {line.strip()!r}")
        elif current is not None:
            sections[current].append(line.rstrip())
        elif line.strip():
            errors.append(f"{name}: text outside a language section: {line.strip()!r}")
    if category is None:
        errors.append(f"{name}: no '# <Category>' heading")
    bullets = {}
    for language in PAGES:
        text = "\n".join(sections.get(language, [])).strip("\n")
        if not text:
            errors.append(f"{name}: no '## {language}' bullets")
        elif not text.startswith("- "):
            errors.append(f"{name}: '## {language}' must start with a '- ' bullet")
        else:
            bullets[language] = text
    return category, bullets, errors


def link_errors(text, page, root, where):
    """Relative links of ``text`` that do not resolve from ``page`` (as check_markdown_links)."""
    errors, cache = [], {}
    for _, line in links.strip_code(text):
        for target in links.LINK.findall(line):
            if links.SCHEME.match(target) or target.startswith("//"):
                continue
            path_part, _, fragment = target.partition("#")
            path_part = unquote(path_part.split("?", 1)[0])
            resolved = (page.parent / path_part).resolve() if path_part else page
            if not resolved.exists():
                errors.append(f"{where}: {target} (missing file, relative to {page.relative_to(root).as_posix()})")
            elif fragment and resolved.suffix.lower() == ".md" and resolved.is_file():
                if unquote(fragment).lower() not in {a.lower() for a in links.anchors(resolved, cache)}:
                    errors.append(f"{where}: {target} (missing anchor)")
    return errors


def check(root=ROOT):
    """Return (parsed fragments, errors); each fragment is (path, category, bullets)."""
    root = Path(root).resolve()
    parsed, errors = [], []
    for path in fragments(root):
        category, bullets, problems = parse(path)
        for language, text in bullets.items():
            problems += link_errors(text, root / PAGES[language], root,
                                    f"{FRAGMENTS}/{path.name} ({language})")
        errors += problems
        parsed.append((path, category, bullets))
    return parsed, errors


def insert(text, entries, page):
    """Insert {category: [bullet blocks]} at the top of each subsection of [Unreleased]."""
    lines = text.split("\n")

    def structure():  # indices of lines outside fenced code
        inside, fence = [], None
        for i, line in enumerate(lines):
            marker = links.FENCE.match(line)
            if marker:
                fence = marker.group(1) if fence is None else (None if marker.group(1) == fence else fence)
            elif fence is None:
                inside.append(i)
        return inside

    start = next((i for i in structure() if UNRELEASED.match(lines[i])), None)
    if start is None:
        raise ValueError(f"{page} has no '## [Unreleased]' section")
    for category in sorted(entries, key=CATEGORIES.index):
        block = "\n".join(entries[category]).split("\n")
        plain = [i for i in structure() if i > start]
        end = next((i for i in plain if lines[i].startswith("## ")), len(lines))
        heads = {}
        for i in plain:
            if i < end and lines[i].startswith("### "):
                heads.setdefault(lines[i][4:].strip(), i)
        if category in heads:
            at = heads[category] + 1
            while at < end and not lines[at].strip():
                at += 1
            if at == end or lines[at].startswith("### "):  # an empty subsection
                lines[heads[category] + 1:at] = ["", *block, ""]
            elif lines[at].startswith("- "):
                lines[at:at] = block
            else:  # the subsection opens with a paragraph: keep it apart
                lines[at:at] = [*block, ""]
            continue
        later = [i for name, i in heads.items() if name in CATEGORIES
                 and CATEGORIES.index(name) > CATEGORIES.index(category)]
        if later:
            at = min(later)
            lines[at:at] = [f"### {category}", "", *block, ""]
        else:  # after the last line of the section
            at = end
            while at > start + 1 and not lines[at - 1].strip():
                at -= 1
            lines[at:end] = ["", f"### {category}", "", *block, ""]
    return "\n".join(lines).rstrip("\n") + "\n"


def assemble(root=ROOT):
    """Merge the fragments into both changelogs and delete them; return the errors."""
    root = Path(root).resolve()
    parsed, errors = check(root)
    if errors:
        return errors
    updated = {}
    for language, page in PAGES.items():
        entries = {}
        for _, category, bullets in parsed:
            entries.setdefault(category, []).append(bullets[language])
        path = root / page
        if not path.is_file():
            return [f"{page} is missing"]
        try:
            updated[path] = insert(path.read_text(encoding="utf-8"), entries, page) if entries else None
        except ValueError as error:
            return [str(error)]
    staged = []
    for path, text in updated.items():
        if text is not None:
            temporary = path.with_name(path.name + ".assemble")
            with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
            staged.append((temporary, path))
    for temporary, path in staged:  # both pages are written before either is replaced
        os.replace(temporary, path)
    for path, _, _ in parsed:
        path.unlink()
    return []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="check every fragment")
    mode.add_argument("--assemble", action="store_true",
                      help="merge the fragments into [Unreleased] of both changelogs and delete them")
    args = parser.parse_args(argv)
    if args.check:
        parsed, errors = check(ROOT)
    else:
        parsed = fragments(ROOT)
        errors = assemble(ROOT)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"{len(parsed)} changelog fragments " + ("checked" if args.check else "assembled"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
