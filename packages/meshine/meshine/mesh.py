# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Triangle mesh produced by the generator, in solver-ready flat arrays."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class TriMesh:
    nodes: np.ndarray                              # (N, 2)
    triangles: np.ndarray                          # (T, 3) counter-clockwise
    regions: np.ndarray                            # (T,) index into region_names
    region_names: list[str]
    boundary_edges: dict[str, np.ndarray]          # name -> (E, 2) node pairs on the outer boundary
    boundary_nodes: dict[str, np.ndarray] = field(default_factory=dict)
    interfaces: dict[tuple[str, str], np.ndarray] = field(default_factory=dict)  # (name_a, name_b) -> (E, 2)

    # -- geometry / quality --------------------------------------------------

    @property
    def num_nodes(self) -> int:
        return len(self.nodes)

    @property
    def num_triangles(self) -> int:
        return len(self.triangles)

    @property
    def areas(self) -> np.ndarray:
        p = self.nodes[self.triangles]
        return 0.5 * ((p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 1] - p[:, 0, 1])
                      - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 1] - p[:, 0, 1]))

    def region_area(self, name: str) -> float:
        return float(self.areas[self.regions == self.region_names.index(name)].sum())

    def edge_lengths(self) -> np.ndarray:
        """(T, 3) lengths of edges opposite to local nodes 0, 1, 2."""
        p = self.nodes[self.triangles]
        return np.stack([np.linalg.norm(p[:, 2] - p[:, 1], axis=1),
                         np.linalg.norm(p[:, 0] - p[:, 2], axis=1),
                         np.linalg.norm(p[:, 1] - p[:, 0], axis=1)], axis=1)

    def angles(self) -> np.ndarray:
        """(T, 3) interior angles in degrees at local nodes 0, 1, 2."""
        L = self.edge_lengths()
        a, b, c = L[:, 0], L[:, 1], L[:, 2]
        cos0 = (b ** 2 + c ** 2 - a ** 2) / (2 * b * c)
        cos1 = (a ** 2 + c ** 2 - b ** 2) / (2 * a * c)
        cos2 = (a ** 2 + b ** 2 - c ** 2) / (2 * a * b)
        return np.degrees(np.arccos(np.clip(np.stack([cos0, cos1, cos2], axis=1), -1, 1)))

    def min_angle(self) -> float:
        return float(self.angles().min())

    def quality(self) -> np.ndarray:
        """Per-triangle radius ratio 2 r_in / r_circ in (0, 1]; 1 is equilateral."""
        L = self.edge_lengths()
        a, b, c = L[:, 0], L[:, 1], L[:, 2]
        s = 0.5 * (a + b + c)
        A = self.areas
        r_in = A / s
        r_circ = a * b * c / (4 * A)
        return 2 * r_in / r_circ

    def boundary_edge_set(self) -> np.ndarray:
        """(E, 2) sorted node pairs used by exactly one triangle (the geometric boundary)."""
        t = self.triangles
        e = np.vstack([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]])
        e.sort(axis=1)
        uniq, counts = np.unique(e, axis=0, return_counts=True)
        return uniq[counts == 1]

    def __repr__(self) -> str:
        return (f"TriMesh(nodes={self.num_nodes}, triangles={self.num_triangles}, "
                f"regions={self.region_names}, min_angle={self.min_angle():.1f} deg)")
