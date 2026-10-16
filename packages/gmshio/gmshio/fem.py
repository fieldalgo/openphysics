# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Convert a ``Mesh`` into the flat arrays a finite-element code wants.

The output deliberately has no methods and no dependency on any particular
solver: node coordinates, element connectivity with consistent orientation,
one integer region id per element, and boundary facets grouped by physical
name. A solver wraps these in its own mesh class.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .mesh import Mesh

#: A mesh counts as planar when its largest |z| is under ``PLANE_EPS`` times its own
#: in-plane extent. Dimensionless: the form it replaces, ``plane_tol * max(1.0, ...)``,
#: collapsed to a flat 1e-9 for any mesh smaller than one unit, so a 220 nm device
#: written in metres was judged against a tolerance four orders of magnitude wider
#: than the device itself and nothing could ever be non-planar.
PLANE_EPS = 1e-9


def _extent(points: np.ndarray) -> float:
    """Diagonal of the bounding box of ``points`` — the length tolerances are measured against."""
    if len(points) == 0:
        return 0.0
    return float(np.linalg.norm(points.max(axis=0) - points.min(axis=0)))


@dataclass
class FemMesh2D:
    nodes: np.ndarray                      # (N, 2)
    triangles: np.ndarray                  # (T, 3) counter-clockwise
    regions: np.ndarray                    # (T,) index into region_names
    region_names: list[str]
    boundary_edges: dict[str, np.ndarray]  # name -> (E, 2) node pairs
    boundary_nodes: dict[str, np.ndarray] = field(default_factory=dict)  # name -> node ids

    @property
    def areas(self) -> np.ndarray:
        p = self.nodes[self.triangles]
        return 0.5 * ((p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 1] - p[:, 0, 1])
                      - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 1] - p[:, 0, 1]))

    def region_area(self, name: str) -> float:
        return float(self.areas[self.regions == self.region_names.index(name)].sum())


@dataclass
class FemMesh3D:
    nodes: np.ndarray                      # (N, 3)
    tetrahedra: np.ndarray                 # (T, 4) positive orientation
    regions: np.ndarray                    # (T,)
    region_names: list[str]
    boundary_faces: dict[str, np.ndarray]  # name -> (F, 3) node triples
    boundary_nodes: dict[str, np.ndarray] = field(default_factory=dict)

    @property
    def volumes(self) -> np.ndarray:
        p = self.nodes[self.tetrahedra]
        d1, d2, d3 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]
        return np.einsum("ij,ij->i", d1, np.cross(d2, d3)) / 6.0

    def region_volume(self, name: str) -> float:
        return float(self.volumes[self.regions == self.region_names.index(name)].sum())


def to_fem2d(mesh: Mesh, plane_eps: float = PLANE_EPS) -> FemMesh2D:
    """Linear triangles in the z=0 plane -> ``FemMesh2D``.

    Region ids follow the physical-surface names in tag order; triangles whose
    entity has no physical group get region id -1. Boundary edges come from
    physical curves. Nodes not used by any triangle are dropped.

    ``plane_eps`` is a fraction of the mesh's own in-plane extent, not a distance.
    """
    tris = mesh.cells("triangle")
    if len(tris) == 0:
        raise ValueError("mesh has no linear triangles (was it generated with dim=2, order=1?)")
    if mesh.cells("triangle6").size or mesh.cells("quad").size:
        raise ValueError("only first-order triangles are supported by to_fem2d")
    extent = _extent(mesh.points[:, :2])
    if not np.isfinite(extent) or extent <= 0.0:
        raise ValueError(
            f"to_fem2d: the {len(mesh.points)} mesh points have no extent in the xy plane, so "
            f"there is no length to measure planarity against. The mesh is a point or a "
            f"vertical line, not a planar geometry.")
    out_of_plane = float(np.abs(mesh.points[:, 2]).max())
    if out_of_plane > plane_eps * extent:
        raise ValueError(
            f"mesh is not planar (z != 0): the largest |z| is {out_of_plane:g}, which is "
            f"{out_of_plane / extent:g} of the {extent:g}-unit in-plane extent, above the "
            f"{plane_eps:g} allowed.")

    region_names = mesh.names(2)
    tag_to_region = {mesh.physical_tag(n, 2): i for i, n in enumerate(region_names)}
    regions = np.array([tag_to_region.get(t, -1) for t in mesh.physical_tags("triangle")], dtype=int)

    nodes, tris, remap = _compact(mesh.points[:, :2], tris)
    tris = _orient_ccw(nodes, tris)

    boundary_edges: dict[str, np.ndarray] = {}
    boundary_nodes: dict[str, np.ndarray] = {}
    for name in mesh.names(1):
        e = mesh.cells_in(name, "line")
        e = remap[e]
        if (e < 0).any():
            raise ValueError(f"boundary curve {name!r} references nodes not in any triangle")
        boundary_edges[name] = e
        boundary_nodes[name] = np.unique(e)
    return FemMesh2D(nodes, tris, regions, region_names, boundary_edges, boundary_nodes)


def to_fem3d(mesh: Mesh) -> FemMesh3D:
    """Linear tetrahedra -> ``FemMesh3D`` (same conventions as ``to_fem2d``)."""
    tets = mesh.cells("tetra")
    if len(tets) == 0:
        raise ValueError("mesh has no linear tetrahedra (was it generated with dim=3, order=1?)")
    if mesh.cells("tetra10").size or mesh.cells("hexahedron").size:
        raise ValueError("only first-order tetrahedra are supported by to_fem3d")

    region_names = mesh.names(3)
    tag_to_region = {mesh.physical_tag(n, 3): i for i, n in enumerate(region_names)}
    regions = np.array([tag_to_region.get(t, -1) for t in mesh.physical_tags("tetra")], dtype=int)

    nodes, tets, remap = _compact(mesh.points, tets)
    tets = _orient_positive(nodes, tets)

    boundary_faces: dict[str, np.ndarray] = {}
    boundary_nodes: dict[str, np.ndarray] = {}
    for name in mesh.names(2):
        f = remap[mesh.cells_in(name, "triangle")]
        if (f < 0).any():
            raise ValueError(f"boundary surface {name!r} references nodes not in any tetrahedron")
        boundary_faces[name] = f
        boundary_nodes[name] = np.unique(f)
    return FemMesh3D(nodes, tets, regions, region_names, boundary_faces, boundary_nodes)


# ---------------------------------------------------------------------------

def _compact(points: np.ndarray, cells: np.ndarray):
    used = np.unique(cells)
    remap = np.full(len(points), -1, dtype=int)
    remap[used] = np.arange(len(used))
    return points[used].copy(), remap[cells], remap


def _orient_ccw(nodes: np.ndarray, tris: np.ndarray) -> np.ndarray:
    p = nodes[tris]
    area2 = ((p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 1] - p[:, 0, 1])
             - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 1] - p[:, 0, 1]))
    if (area2 == 0).any():
        raise ValueError("degenerate (zero-area) triangle in mesh")
    tris = tris.copy()
    flip = area2 < 0
    tris[flip, 1], tris[flip, 2] = tris[flip, 2], tris[flip, 1]
    return tris


def _orient_positive(nodes: np.ndarray, tets: np.ndarray) -> np.ndarray:
    p = nodes[tets]
    vol6 = np.einsum("ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]))
    if (vol6 == 0).any():
        raise ValueError("degenerate (zero-volume) tetrahedron in mesh")
    tets = tets.copy()
    flip = vol6 < 0
    tets[flip, 2], tets[flip, 3] = tets[flip, 3], tets[flip, 2]
    return tets
