# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Check relative links and #anchors in the repository's Markdown files.

Every inline link or image whose target is not a URL must name an existing file
or directory, and a #fragment pointing into a Markdown file must match one of its
headings (GitHub slug rules) or an explicit HTML id/name. Links inside code
blocks and inline code are ignored. External URLs are not fetched.

Usage: python tools/check_markdown_links.py [--root DIR]
Exits 1 and lists each broken link when any is found.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

LINK = re.compile(r"!?\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^)]*[\"'])?\s*\)")
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"(`+)(?:(?!\1).)+?\1")
HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
HTML_ID = re.compile(r"""<[^>]+\b(?:id|name)\s*=\s*["']([^"']+)["']""")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def strip_code(text: str, inline: bool = True) -> list[tuple[int, str]]:
    """Return (line number, line) pairs outside fenced code, optionally without inline code."""
    lines, fence = [], None
    for number, line in enumerate(text.splitlines(), 1):
        match = FENCE.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            continue
        if fence is None:
            lines.append((number, INLINE_CODE.sub("", line) if inline else line))
    return lines


def slug(heading: str) -> str:
    """GitHub-style anchor for a heading's text."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)  # keep link text only
    text = re.sub(r"<[^>]+>", "", text).replace("`", "").strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(path: Path, cache: dict[Path, set[str]]) -> set[str]:
    if path not in cache:
        found, counts = set(), {}
        text = path.read_text(encoding="utf-8")
        for _, line in strip_code(text, inline=False):
            heading = HEADING.match(line)
            if heading:
                base = slug(heading.group(2))
                n = counts.get(base, 0)
                found.add(base if n == 0 else f"{base}-{n}")
                counts[base] = n + 1
            found.update(HTML_ID.findall(line))
        cache[path] = found
    return cache[path]


def markdown_files(root: Path) -> list[Path]:
    # Tracked files only when root is a repository's top level; otherwise walk the tree.
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root, check=True,
                             capture_output=True, text=True).stdout.strip()
        if Path(top).resolve() != root:
            raise ValueError(top)
        out = subprocess.run(["git", "ls-files", "-z", "--", "*.md"], cwd=root,
                             check=True, capture_output=True).stdout.decode("utf-8")
        files = [root / name for name in out.split("\0") if name]
    except (OSError, ValueError, subprocess.CalledProcessError):
        files = [p for p in root.rglob("*.md") if ".git" not in p.relative_to(root).parts]
    return sorted(p for p in files if p.is_file())


def check(root: Path) -> tuple[int, list[str]]:
    root = root.resolve()
    cache: dict[Path, set[str]] = {}
    broken, count = [], 0
    for md in markdown_files(root):
        for number, line in strip_code(md.read_text(encoding="utf-8")):
            for target in LINK.findall(line):
                if SCHEME.match(target) or target.startswith("//"):
                    continue
                count += 1
                path_part, _, fragment = target.partition("#")
                path_part = unquote(path_part.split("?", 1)[0])
                resolved = (md.parent / path_part).resolve() if path_part else md
                where = f"{md.relative_to(root).as_posix()}:{number}: {target}"
                if not resolved.exists():
                    broken.append(f"{where} (missing file)")
                elif fragment and resolved.suffix.lower() == ".md" and resolved.is_file():
                    if unquote(fragment).lower() not in {a.lower() for a in anchors(resolved, cache)}:
                        broken.append(f"{where} (missing anchor)")
    return count, broken


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    count, broken = check(args.root)
    for item in broken:
        print(item)
    print(f"{count} relative Markdown links checked, {len(broken)} broken")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
