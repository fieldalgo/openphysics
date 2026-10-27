# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit elementwise volumetric heat sources, bound to one mesh ordering."""
from dataclasses import dataclass

from .coupling import Field

MESH_MISMATCH = "element heat source mesh geometry, ordering or regions do not match"


@dataclass(frozen=True, init=False)
class ElementHeatSource:
    """Piecewise constant Q in W/m³, with an owned SI mesh snapshot.

    ``values`` has exactly one finite real value per triangle. Signed sources
    are allowed (negative means cooling). Coordinates, connectivity and region
    ordering must match when consumed; boundary conditions may change.
    Construct a new source after changing a mesh. No interpolation is done.
    Values are NumPy: JAX and PyTorch arrays are refused (TypeError).
    The source is an element ``galerkin.coupling.Field`` in W/m^3 (``field``).
    """

    field: Field

    def __init__(self, mesh, values):
        object.__setattr__(self, "field", Field(mesh, values, location="element", unit="W/m^3",
                                                name="element heat source"))

    @property
    def values(self):
        return self.field.values

    def on_mesh(self, mesh):
        """Return the element values after checking exact mesh correspondence."""
        return self.field.on_mesh(mesh, message=MESH_MISMATCH)
