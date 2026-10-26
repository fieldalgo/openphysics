# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit elementwise volumetric heat sources, bound to one mesh ordering."""
from dataclasses import dataclass

import numpy as np

from .mesh import Mesh
from .core.checks import refuse_live


def _copy(value):
    result = np.array(value, copy=True)
    result.setflags(write=False)
    return result


@dataclass(frozen=True, init=False)
class ElementHeatSource:
    """Piecewise constant Q in W/m³, with an owned SI mesh snapshot.

    ``values`` has exactly one finite real value per triangle. Signed sources
    are allowed (negative means cooling). Coordinates, connectivity and region
    ordering must match when consumed; boundary conditions may change.
    Construct a new source after changing a mesh. No interpolation is done.
    Values are NumPy: JAX and PyTorch arrays are refused (TypeError).
    """

    values: np.ndarray
    _nodes: np.ndarray
    _triangles: np.ndarray
    _regions: np.ndarray | None
    _region_names: tuple | None

    def __init__(self, mesh, values):
        if not isinstance(mesh, Mesh):
            raise ValueError("mesh must be a galerkin.mesh.Mesh")
        refuse_live(values, "element heat source")
        data = np.asarray(values)
        if (data.shape != (mesh.num_triangles,) or data.dtype.kind not in "iuf"
                or not np.all(np.isfinite(data))):
            raise ValueError("element heat source must be finite real shape (M,)")
        data = np.asarray(data, dtype=float)
        if not np.all(np.isfinite(data)):
            raise ValueError("element heat source exceeds floating-point range")
        for name, value in (("values", data), ("_nodes", mesh.nodes),
                            ("_triangles", mesh.triangles)):
            object.__setattr__(self, name, _copy(value))
        object.__setattr__(self, "_regions", None if mesh.regions is None else _copy(mesh.regions))
        object.__setattr__(self, "_region_names", None if mesh.region_names is None
                           else tuple(mesh.region_names))

    def on_mesh(self, mesh):
        """Return the element values after checking exact mesh correspondence."""
        if not isinstance(mesh, Mesh):
            raise ValueError("mesh must be a galerkin.mesh.Mesh")
        regions_match = (self._regions is None and mesh.regions is None) or (
            self._regions is not None and mesh.regions is not None
            and np.array_equal(self._regions, mesh.regions))
        names = None if mesh.region_names is None else tuple(mesh.region_names)
        if (not np.array_equal(self._nodes, mesh.nodes)
                or not np.array_equal(self._triangles, mesh.triangles)
                or not regions_match or self._region_names != names):
            raise ValueError("element heat source mesh geometry, ordering or regions do not match")
        return self.values
