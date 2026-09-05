"""Adapter for meshes produced elsewhere.

External meshers hand back the same five things, whatever built them:

    nodes           (N, 2) or (N, 3)
    triangles       (T, 3)      2D          | tetrahedra (T, 4)   3D
    regions         (T,)  index into        | region_names        the names
    boundary_edges  {name: (E, 2)}          | boundary_faces {name: (F, 3)}

so one duck-typed adapter takes any of them. Verified against
`meshine` (pure numpy/scipy, planar) and `gmshio` (drives the Gmsh executable
as a separate process, planar and volumetric); neither is imported here, and
neither is a dependency of the engine — the adapter only reads attributes.

    from meshine import shapes, generate
    from galerkin import from_mesher
    d, namer = shapes.rib_waveguide(slab_thickness=0.3)
    mesh = from_mesher(generate(d, namer))
    eps = mesh.by_region({"core": 3.44 ** 2, "box": 3.40 ** 2, "clad": 1.0})
"""

from __future__ import annotations

import numpy as np

from .mesh import Mesh
from .mesh3d import Mesh3D

_CELLS_2D = ("triangles", "cells", "elements")
_CELLS_3D = ("tetrahedra", "tets", "cells", "elements")


def _first(obj, names, width):
    for name in names:
        value = getattr(obj, name, None)
        if value is None and isinstance(obj, dict):
            value = obj.get(name)
        if value is not None:
            value = np.asarray(value)
            if value.ndim == 2 and value.shape[1] == width:
                return value.astype(int)
    return None


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def from_mesher(source) -> Mesh | Mesh3D:
    """Convert a foreign mesh object (or a dict of arrays) into a galerkin mesh.

    Dimensionality is decided by the cells, not by the node array, because a
    planar mesh is sometimes carried with a zero z column.
    """
    nodes = np.asarray(_get(source, "nodes"), dtype=float)
    if nodes is None or nodes.ndim != 2:
        raise TypeError("source has no (N, d) 'nodes' array")

    tets = _first(source, _CELLS_3D, 4)
    tris = None if tets is not None else _first(source, _CELLS_2D, 3)
    if tets is None and tris is None:
        raise TypeError("source has neither (T, 4) tetrahedra nor (T, 3) triangles")

    regions = _get(source, "regions")
    regions = None if regions is None else np.asarray(regions, dtype=int)
    names = _get(source, "region_names")
    names = None if names is None else [str(n) for n in names]
    if regions is not None:
        cells = tets if tets is not None else tris
        if len(regions) != len(cells):
            raise ValueError(
                f"regions has {len(regions)} entries for {len(cells)} cells")
        if names is not None and regions.max(initial=-1) >= len(names):
            raise ValueError("a region index points past the end of region_names")

    if tets is not None:
        faces = _get(source, "boundary_faces") or {}
        boundary = {k: np.unique(np.asarray(v, dtype=int))
                    for k, v in faces.items()}
        if nodes.shape[1] != 3:
            raise ValueError("a tetrahedral mesh needs (N, 3) nodes")
        return Mesh3D(nodes, tets, boundary, regions=regions, region_names=names)

    edges = _get(source, "boundary_edges") or {}
    boundary_edges = {k: np.asarray(v, dtype=int) for k, v in edges.items()}
    boundary = {k: np.unique(v) for k, v in boundary_edges.items()}
    return Mesh(nodes[:, :2], tris, boundary, boundary_edges,
                regions=regions, region_names=names)
