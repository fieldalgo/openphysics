# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Mesh container returned by the MSH reader.

Everything is plain numpy: node coordinates, one ``CellBlock`` per
(geometric entity, element type) pair exactly as Gmsh stores them, plus the
physical-group bookkeeping needed to recover material regions and boundary
tags. Node indices in ``CellBlock.cells`` are 0-based positions into
``Mesh.points`` (Gmsh's own 1-based, possibly non-contiguous node tags are
kept in ``Mesh.point_tags`` for reference only).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Gmsh element type id -> (name, number of nodes, topological dimension)
ELEMENT_TYPES: dict[int, tuple[str, int, int]] = {
    15: ("vertex", 1, 0),
    1: ("line", 2, 1),
    8: ("line3", 3, 1),
    2: ("triangle", 3, 2),
    9: ("triangle6", 6, 2),
    3: ("quad", 4, 2),
    16: ("quad8", 8, 2),
    10: ("quad9", 9, 2),
    4: ("tetra", 4, 3),
    11: ("tetra10", 10, 3),
    5: ("hexahedron", 8, 3),
    17: ("hexahedron20", 20, 3),
    12: ("hexahedron27", 27, 3),
    6: ("wedge", 6, 3),
    7: ("pyramid", 5, 3),
}


@dataclass
class CellBlock:
    dim: int                 # topological dimension of the elements
    type: str                # element type name, see ELEMENT_TYPES
    entity_tag: int          # Gmsh geometric entity the block belongs to
    cells: np.ndarray        # (M, k) 0-based node indices
    element_tags: np.ndarray # (M,) Gmsh element tags

    def __len__(self) -> int:
        return len(self.cells)


@dataclass
class Mesh:
    points: np.ndarray                                  # (N, 3)
    point_tags: np.ndarray                              # (N,) Gmsh node tags
    blocks: list[CellBlock] = field(default_factory=list)
    physical_names: dict[tuple[int, int], str] = field(default_factory=dict)
    entity_physical: dict[tuple[int, int], tuple[int, ...]] = field(default_factory=dict)

    # ---- basic queries -------------------------------------------------

    @property
    def num_points(self) -> int:
        return len(self.points)

    def cell_types(self) -> list[str]:
        seen: list[str] = []
        for b in self.blocks:
            if b.type not in seen:
                seen.append(b.type)
        return seen

    def cells(self, cell_type: str) -> np.ndarray:
        """All cells of one type, concatenated over entities. (M, k) int array."""
        parts = [b.cells for b in self.blocks if b.type == cell_type]
        if not parts:
            k = next((n for _, (name, n, _) in ELEMENT_TYPES.items() if name == cell_type), 0)
            return np.zeros((0, k), dtype=int)
        return np.vstack(parts)

    def physical_tags(self, cell_type: str) -> np.ndarray:
        """Physical tag of every cell of ``cell_type`` (0 when the entity has none).

        Same ordering as ``cells(cell_type)``. If an entity belongs to several
        physical groups, the first one is used.
        """
        out = []
        for b in self.blocks:
            if b.type != cell_type:
                continue
            phys = self.entity_physical.get((b.dim, b.entity_tag), ())
            out.append(np.full(len(b), phys[0] if phys else 0, dtype=int))
        return np.concatenate(out) if out else np.zeros(0, dtype=int)

    def physical_tag(self, name: str, dim: int | None = None) -> int:
        """Look up a physical group's integer tag by name (optionally restricted to a dimension)."""
        hits = [(d, t) for (d, t), n in self.physical_names.items()
                if n == name and (dim is None or d == dim)]
        if not hits:
            raise KeyError(f"no physical group named {name!r}" + (f" of dim {dim}" if dim is not None else ""))
        if len(hits) > 1:
            raise KeyError(f"physical name {name!r} is used in several dimensions; pass dim=")
        return hits[0][1]

    def cells_in(self, name: str, cell_type: str) -> np.ndarray:
        """Cells of ``cell_type`` whose entity carries the physical group ``name``."""
        dim = ELEMENT_TYPES[[k for k, v in ELEMENT_TYPES.items() if v[0] == cell_type][0]][2]
        tag = self.physical_tag(name, dim)
        parts = [b.cells for b in self.blocks
                 if b.type == cell_type and tag in self.entity_physical.get((b.dim, b.entity_tag), ())]
        if not parts:
            return np.zeros((0, self.cells(cell_type).shape[1]), dtype=int)
        return np.vstack(parts)

    def names(self, dim: int) -> list[str]:
        """Physical group names of a given dimension, in tag order."""
        return [n for (d, t), n in sorted(self.physical_names.items()) if d == dim]

    def __repr__(self) -> str:
        counts = {t: len(self.cells(t)) for t in self.cell_types()}
        return f"Mesh(points={self.num_points}, cells={counts}, physical={list(self.physical_names.values())})"
