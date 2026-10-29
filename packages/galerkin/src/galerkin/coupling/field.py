# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fields bound to one 2D P1 triangle mesh, and their same-mesh transfer."""
from dataclasses import dataclass

import numpy as np

from ..mesh import Mesh
from ..core.checks import refuse_live

LOCATIONS = ("node", "element")


def _frozen(value):
    result = np.array(value, copy=True)
    result.setflags(write=False)
    return result


@dataclass(frozen=True, init=False)
class MeshSignature:
    """Owned read-only copy of what makes two meshes the same for a field.

    Node coordinates, triangle connectivity in order, and optionally the
    triangle region indices and region names. Boundary tags are not part of
    the signature: boundary conditions may change between physics.
    """

    nodes: np.ndarray
    triangles: np.ndarray
    regions: np.ndarray | None
    region_names: tuple | None

    def __init__(self, mesh):
        if not isinstance(mesh, Mesh):
            raise ValueError("mesh must be a galerkin.mesh.Mesh")
        object.__setattr__(self, "nodes", _frozen(mesh.nodes))
        object.__setattr__(self, "triangles", _frozen(mesh.triangles))
        object.__setattr__(self, "regions", None if mesh.regions is None else _frozen(mesh.regions))
        object.__setattr__(self, "region_names", None if mesh.region_names is None
                           else tuple(mesh.region_names))

    def matches(self, mesh, *, regions=True):
        """Whether ``mesh`` has exactly these nodes and triangles (and regions).

        Coordinates are compared exactly, without tolerance; node and triangle
        order count. With ``regions=False`` region data is not compared.
        """
        if not isinstance(mesh, Mesh):
            raise ValueError("mesh must be a galerkin.mesh.Mesh")
        if (not np.array_equal(self.nodes, mesh.nodes)
                or not np.array_equal(self.triangles, mesh.triangles)):
            return False
        if not regions:
            return True
        regions_match = (self.regions is None and mesh.regions is None) or (
            self.regions is not None and mesh.regions is not None
            and np.array_equal(self.regions, mesh.regions))
        names = None if mesh.region_names is None else tuple(mesh.region_names)
        return regions_match and self.region_names == names


@dataclass(frozen=True, init=False)
class Field:
    """Finite real values at the nodes or triangles of one mesh, with a unit.

    ``values`` is a read-only float64 copy of shape (N,) at nodes or (M,) at
    elements (piecewise constant per triangle). ``unit`` is an SI unit string
    such as ``"K"`` or ``"W/m^3"``; it is recorded and carried by ``transfer``,
    never compared, converted or inferred. JAX and PyTorch values are refused
    (TypeError): a field carries NumPy numbers between physics. ``name`` labels
    the values in error messages.
    """

    signature: MeshSignature
    location: str
    unit: str
    values: np.ndarray

    def __init__(self, mesh, values, *, location, unit, name=None):
        if location not in LOCATIONS:
            raise ValueError(f"location must be one of {LOCATIONS}")
        if not isinstance(unit, str) or not unit:
            raise ValueError("unit must be a nonempty SI unit string")
        name = f"{location} field" if name is None else name
        signature = MeshSignature(mesh)
        refuse_live(values, name)
        data = np.asarray(values)
        node = location == "node"
        count = mesh.num_nodes if node else mesh.num_triangles
        if (data.shape != (count,) or data.dtype.kind not in "iuf"
                or not np.all(np.isfinite(data))):
            raise ValueError(f"{name} must be finite real shape ({'N' if node else 'M'},)")
        data = np.asarray(data, dtype=float)
        if not np.all(np.isfinite(data)):
            raise ValueError(f"{name} exceeds floating-point range")
        object.__setattr__(self, "signature", signature)
        object.__setattr__(self, "location", location)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "values", _frozen(data))

    def on_mesh(self, mesh, *, regions=True, message="field mesh does not match"):
        """Return ``values`` after checking that ``mesh`` is this field's mesh.

        Raises ValueError(``message``) when it is not; see ``MeshSignature.matches``.
        """
        if not self.signature.matches(mesh, regions=regions):
            raise ValueError(message)
        return self.values


def transfer(field, mesh, *, regions=True, message="field mesh does not match"):
    """Carry ``field`` onto ``mesh``: the identity for the same mesh.

    Returns a field bound to ``mesh`` with the same values, location and unit.
    A different mesh raises ValueError(``message``); there is no interpolation
    or projection between meshes.
    """
    if not isinstance(field, Field):
        raise ValueError("field must be a galerkin.coupling.Field")
    return Field(mesh, field.on_mesh(mesh, regions=regions, message=message),
                 location=field.location, unit=field.unit)
