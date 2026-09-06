# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Reader for the Gmsh MSH 4.1 ASCII file format.

Only the sections a finite-element code needs are parsed: ``$PhysicalNames``,
``$Entities`` (to map entities to physical groups), ``$Nodes`` and
``$Elements``. Other sections (``$Periodic``, ``$NodeData`` ...) are skipped.

Format reference: Gmsh reference manual, "MSH file format version 4.1".
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .mesh import ELEMENT_TYPES, CellBlock, Mesh


class MshFormatError(ValueError):
    pass


def read_msh(path: str | Path) -> Mesh:
    """Parse a MSH 4.1 ASCII file into a ``Mesh``."""
    text = Path(path).read_text()
    sections = _split_sections(text)

    if "MeshFormat" not in sections:
        raise MshFormatError("not a Gmsh MSH file (no $MeshFormat section)")
    version, file_type = sections["MeshFormat"][0].split()[:2]
    if not version.startswith("4.1"):
        raise MshFormatError(f"MSH version {version} not supported; export with -format msh41")
    if file_type != "0":
        raise MshFormatError("binary MSH not supported; export ASCII (gmsh -format msh41, without -bin)")

    physical_names = _parse_physical_names(sections.get("PhysicalNames", []))
    entity_physical = _parse_entities(sections.get("Entities", []))
    points, point_tags, tag_to_index = _parse_nodes(sections["Nodes"])
    blocks = _parse_elements(sections["Elements"], tag_to_index)

    return Mesh(points=points, point_tags=point_tags, blocks=blocks,
                physical_names=physical_names, entity_physical=entity_physical)


# ---------------------------------------------------------------------------

def _split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    buf: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("$End"):
            if current is None:
                raise MshFormatError(f"unexpected {line}")
            sections[current] = buf
            current, buf = None, []
        elif line.startswith("$"):
            current = line[1:]
            buf = []
        else:
            buf.append(line)
    if current is not None:
        raise MshFormatError(f"section ${current} not closed")
    return sections


def _parse_physical_names(lines: list[str]) -> dict[tuple[int, int], str]:
    if not lines:
        return {}
    n = int(lines[0])
    out: dict[tuple[int, int], str] = {}
    for line in lines[1:1 + n]:
        dim, tag, name = line.split(maxsplit=2)
        out[(int(dim), int(tag))] = name.strip().strip('"')
    return out


def _parse_entities(lines: list[str]) -> dict[tuple[int, int], tuple[int, ...]]:
    """Return {(dim, entity_tag): physical tags}."""
    if not lines:
        return {}
    counts = [int(v) for v in lines[0].split()]  # points, curves, surfaces, volumes
    out: dict[tuple[int, int], tuple[int, ...]] = {}
    idx = 1
    for dim, count in enumerate(counts):
        for _ in range(count):
            vals = lines[idx].split()
            idx += 1
            tag = int(vals[0])
            # points: tag x y z numPhys ...; others: tag min(3) max(3) numPhys ...
            pos = 4 if dim == 0 else 7
            num_phys = int(vals[pos])
            phys = tuple(int(v) for v in vals[pos + 1: pos + 1 + num_phys])
            out[(dim, tag)] = phys
    return out


def _parse_nodes(lines: list[str]):
    num_blocks, num_nodes = (int(v) for v in lines[0].split()[:2])
    tags = np.empty(num_nodes, dtype=np.int64)
    coords = np.empty((num_nodes, 3), dtype=float)
    idx, filled = 1, 0
    for _ in range(num_blocks):
        _dim, _etag, parametric, n = (int(v) for v in lines[idx].split())
        idx += 1
        if n == 0:
            continue
        tags[filled:filled + n] = [int(v) for v in lines[idx:idx + n]]
        idx += n
        for i in range(n):
            xyz = lines[idx + i].split()
            coords[filled + i] = (float(xyz[0]), float(xyz[1]), float(xyz[2]))
        idx += n
        filled += n
    if filled != num_nodes:
        raise MshFormatError(f"$Nodes announces {num_nodes} nodes, found {filled}")
    tag_to_index = np.full(int(tags.max()) + 1, -1, dtype=np.int64)
    tag_to_index[tags] = np.arange(num_nodes)
    return coords, tags, tag_to_index


def _parse_elements(lines: list[str], tag_to_index: np.ndarray) -> list[CellBlock]:
    num_blocks, num_elems = (int(v) for v in lines[0].split()[:2])
    blocks: list[CellBlock] = []
    idx, total = 1, 0
    for _ in range(num_blocks):
        dim, etag, etype, n = (int(v) for v in lines[idx].split())
        idx += 1
        if etype not in ELEMENT_TYPES:
            raise MshFormatError(f"unsupported Gmsh element type {etype}")
        name, k, tdim = ELEMENT_TYPES[etype]
        data = np.array([line.split() for line in lines[idx:idx + n]], dtype=np.int64)
        idx += n
        total += n
        if n == 0:
            continue
        if data.shape[1] != k + 1:
            raise MshFormatError(f"element type {name} expects {k} nodes, got {data.shape[1] - 1}")
        cells = tag_to_index[data[:, 1:]]
        if (cells < 0).any():
            raise MshFormatError("element references an unknown node tag")
        blocks.append(CellBlock(dim=tdim, type=name, entity_tag=etag,
                                cells=cells, element_tags=data[:, 0]))
    if total != num_elems:
        raise MshFormatError(f"$Elements announces {num_elems} elements, found {total}")
    return blocks
