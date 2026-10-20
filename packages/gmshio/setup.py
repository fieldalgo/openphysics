# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Build hook: the package description is README.md with absolute repository links.

README.md uses links relative to this package directory so that they work on
GitHub. The sdist ships no docs, and on PyPI there is no repository next to
the page, so the description stored in the package metadata rewrites them to
GitHub URLs pinned to one source revision: links to blob pages, images to raw
files and bare #anchors to this README. README.md itself is not changed.

Revision: OPENPHYSICS_DOCS_REF if set (a release tag such as v0.2.0), otherwise
the checkout's commit, otherwise main. A wheel built from an unpacked sdist
reuses the sdist's PKG-INFO description, so both carry the same text.

This file is identical in every package of the repository.
"""

import os
import posixpath
import re
import subprocess
from email.parser import Parser
from pathlib import Path

from setuptools import setup

HERE = Path(__file__).resolve().parent
REPOSITORY = "fieldalgo/openphysics"
LINK = re.compile(r"(!?)\[((?:[^\[\]]|\[[^\]]*\])*)\]\(\s*<?([^)\s>]+)>?((?:\s+\"[^\"]*\")?)\s*\)")
FENCE = re.compile(r"^\s*(```|~~~)")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _git(*args):
    return subprocess.run(["git", *args], cwd=HERE, check=True,
                          capture_output=True, text=True).stdout.strip()


def absolute_links(text, ref, prefix):
    """Rewrite relative Markdown links and images outside code fences."""

    def fix(match):
        bang, label, target, title = match.groups()
        if SCHEME.match(target) or target.startswith("//"):
            return match.group(0)
        path, _, fragment = target.partition("#")
        full = posixpath.normpath(posixpath.join(prefix, path)) if path else prefix + "README.md"
        if bang:
            url = f"https://raw.githubusercontent.com/{REPOSITORY}/{ref}/{full}"
        else:
            url = f"https://github.com/{REPOSITORY}/blob/{ref}/{full}"
        if fragment:
            url += "#" + fragment
        return f"{bang}[{label}]({url}{title})"

    lines, fence = [], None
    for line in text.split("\n"):
        marker = FENCE.match(line)
        if marker:
            fence = marker.group(1) if fence is None else (None if marker.group(1) == fence else fence)
        elif fence is None:
            line = LINK.sub(fix, line)
        lines.append(line)
    return "\n".join(lines)


def description():
    pkg_info = HERE / "PKG-INFO"
    if pkg_info.is_file():  # building a wheel from an unpacked sdist
        body = Parser().parsestr(pkg_info.read_text(encoding="utf-8")).get_payload()
        if body and body.strip():
            return body
    ref = os.environ.get("OPENPHYSICS_DOCS_REF", "").strip()
    try:
        prefix = _git("rev-parse", "--show-prefix")
        ref = ref or _git("rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError):
        prefix = f"packages/{HERE.name}/"
    return absolute_links((HERE / "README.md").read_text(encoding="utf-8"), ref or "main", prefix)


if __name__ == "__main__":
    setup(long_description=description(), long_description_content_type="text/markdown")
