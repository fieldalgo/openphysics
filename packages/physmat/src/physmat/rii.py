# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Reader for the refractiveindex.info database (CC0 1.0, public domain).

The database is a tree of YAML files plus a catalog. Point this module at a
local copy (``git clone https://github.com/polyanskiy/refractiveindex.info-database``
or ``Database.download()``) and look records up by shelf / book / page, e.g.
``("main", "SiO2", "Malitson")``.

Please cite the database when you use its data:
M. N. Polyanskiy, "Refractiveindex.info database of optical constants",
Sci. Data 11, 94 (2024).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .dispersion import Composite, Dispersion, RIIFormula, Tabulated

CITATION = ('M. N. Polyanskiy, "Refractiveindex.info database of optical constants", '
            "Sci. Data 11, 94 (2024). https://doi.org/10.1038/s41597-023-02898-2")
GITHUB_ZIP = "https://github.com/polyanskiy/refractiveindex.info-database/archive/refs/heads/main.zip"


@dataclass
class Record:
    dispersion: Dispersion
    references: str = ""
    comments: str = ""
    conditions: dict = field(default_factory=dict)
    path: str = ""


def _yaml():
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise ImportError("reading refractiveindex.info files needs PyYAML: pip install pyyaml") from exc
    return yaml


def _parse_table(text: str, ncols: int) -> np.ndarray:
    rows = [ln.split() for ln in text.strip().splitlines() if ln.strip()]
    arr = np.array(rows, dtype=float)
    if arr.shape[1] != ncols:
        raise ValueError(f"expected {ncols} columns, got {arr.shape[1]}")
    return arr


def load_record(path: str | Path, label: str | None = None) -> Record:
    """Parse one refractiveindex.info YAML file into a Record with a Dispersion model."""
    yaml = _yaml()
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    label = label or Path(path).stem
    n_parts: list[Dispersion] = []
    k_parts: list[Dispersion] = []
    nk_parts: list[Dispersion] = []
    for block in doc.get("DATA", []):
        typ = block["type"].strip()
        if typ.startswith("formula"):
            kind = int(typ.split()[1])
            coeffs = [float(v) for v in str(block["coefficients"]).split()]
            lo, hi = (float(v) for v in str(block["wavelength_range"]).split())
            n_parts.append(RIIFormula(kind, coeffs, (lo, hi), label))
        elif typ == "tabulated nk":
            t = _parse_table(block["data"], 3)
            nk_parts.append(Tabulated(t[:, 0], t[:, 1], t[:, 2], label))
        elif typ == "tabulated n":
            t = _parse_table(block["data"], 2)
            n_parts.append(Tabulated(t[:, 0], t[:, 1], None, label))
        elif typ == "tabulated k":
            t = _parse_table(block["data"], 2)
            k_parts.append(Tabulated(t[:, 0], np.zeros(len(t)), t[:, 1], label))
        else:
            # "formula A" etc. belong to the nonlinear-index (n2) files; ignore
            continue
    if nk_parts and not n_parts and not k_parts:
        disp = nk_parts[0]
    elif n_parts and k_parts:
        disp = Composite(n_parts[0], k_parts[0], label)
    elif n_parts:
        disp = n_parts[0]
    elif k_parts:
        disp = k_parts[0]
    else:
        raise ValueError(f"{path}: no usable DATA block (n / k / nk)")
    return Record(disp, doc.get("REFERENCES", "") or "", doc.get("COMMENTS", "") or "",
                  doc.get("CONDITIONS", {}) or {}, str(path))


@dataclass
class Entry:
    shelf: str
    book: str
    page: str
    name: str
    path: str
    book_names: tuple[str, ...] = ()       # full names / aliases from the book's about.yml


class Database:
    """Local copy of the refractiveindex.info database."""

    def __init__(self, root: str | Path | None = None):
        root = root or os.environ.get("PHYSMAT_RII_PATH") or (Path.home() / ".cache" / "physmat" / "rii")
        root = Path(root)
        # accept the repo root, the 'database' folder, or the extracted zip folder
        for cand in (root, root / "database", *root.glob("refractiveindex.info-database-*/database")):
            if (cand / "catalog-nk.yml").exists():
                root = cand
                break
        else:
            raise FileNotFoundError(f"no refractiveindex.info database at {root}; run Database.download() "
                                    f"or set PHYSMAT_RII_PATH")
        self.root = root
        self.entries: list[Entry] = self._read_catalog()

    # -- catalog -------------------------------------------------------------

    def _read_catalog(self) -> list[Entry]:
        yaml = _yaml()
        cat = yaml.safe_load((self.root / "catalog-nk.yml").read_text(encoding="utf-8"))
        out: list[Entry] = []
        for shelf in cat:
            if "SHELF" not in shelf:
                continue
            for book in shelf.get("content", []):
                if "BOOK" not in book:
                    continue
                names = self._book_names(str(shelf["SHELF"]), str(book["BOOK"]), book)
                for page in book.get("content", []):
                    if "PAGE" not in page:
                        continue
                    out.append(Entry(str(shelf["SHELF"]), str(book["BOOK"]), str(page["PAGE"]),
                                     str(page.get("name", "")), str(page["data"]), names))
        return out

    def _book_names(self, shelf: str, book: str, book_block: dict) -> tuple[str, ...]:
        names = [strip_html(str(book_block.get("name", "")))]
        about = self.root / "data" / shelf / book / "about.yml"
        if about.exists():
            try:
                doc = _yaml().safe_load(about.read_text(encoding="utf-8")) or {}
                names += [strip_html(str(n)) for n in doc.get("NAMES", [])]
            except Exception:
                pass
        return tuple(n for n in names if n)

    def search(self, *terms: str) -> list[Entry]:
        """Entries whose shelf/book/page/name contain all terms (case-insensitive)."""
        t = [s.lower() for s in terms]
        return [e for e in self.entries
                if all(any(s in v.lower() for v in (e.shelf, e.book, e.page, e.name, *e.book_names)) for s in t)]

    def books(self, shelf: str = "main") -> list[str]:
        seen: list[str] = []
        for e in self.entries:
            if e.shelf == shelf and e.book not in seen:
                seen.append(e.book)
        return seen

    def pages(self, book: str, shelf: str | None = None) -> list[Entry]:
        return [e for e in self.entries if e.book == book and (shelf is None or e.shelf == shelf)]

    # -- records -------------------------------------------------------------

    def get(self, shelf: str, book: str, page: str) -> Record:
        for e in self.entries:
            if e.shelf == shelf and e.book == book and e.page == page:
                return load_record(self.root / "data" / e.path, label=f"{book}:{page}")
        raise KeyError(f"no page {shelf}/{book}/{page}")

    def load(self, spec: str) -> Record:
        """Shortcut: ``"main/SiO2/Malitson"``."""
        parts = spec.split("/")
        if len(parts) != 3:
            raise ValueError("spec must be shelf/book/page")
        return self.get(*parts)

    # -- fetching ------------------------------------------------------------

    @staticmethod
    def download(dest: str | Path | None = None, url: str = GITHUB_ZIP) -> Path:
        """Download and extract the database zip (about 60 MB) into ``dest``."""
        import io
        import urllib.request
        import zipfile

        dest = Path(dest or Path.home() / ".cache" / "physmat" / "rii")
        dest.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url) as resp:
            data = resp.read()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(dest)
        return dest


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()
