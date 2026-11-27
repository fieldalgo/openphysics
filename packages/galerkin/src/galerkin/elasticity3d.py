# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Small-strain isotropic linear elasticity with P1 tetrahedra in SI units."""
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from . import _elasticity3d
from ._public import ResultSurface

__all__ = ["Elasticity3DResult", "solve_elasticity_3d"]


@dataclass(frozen=True, eq=False)
class Elasticity3DResult(ResultSurface):
    """Nodal displacement (N, 3) and total element strain and stress (T, 3, 3).

    Force arrays are (N, 3) in N. Applied force includes body and surface loads.
    Residual force is internal minus applied force, and reaction force is its
    restriction to prescribed components, with zero at all other components.
    """

    displacement: np.ndarray
    strain: np.ndarray
    stress: np.ndarray
    applied_force: np.ndarray
    reaction_force: np.ndarray
    residual_force: np.ndarray

    BASIS = "3d"
    UNITS = MappingProxyType({"displacement": "m", "strain": "1", "stress": "Pa",
                              "applied_force": "N", "reaction_force": "N", "residual_force": "N"})


def solve_elasticity_3d(mesh, *, youngs_modulus, poisson_ratio, prescribed_displacement,
                        body_force_density=None, traction=None):
    """Solve static 3D elasticity on a Mesh3D in metres.

    Give E in Pa and Poisson ratio in (-1, 0.5), as scalars or mappings from
    region names. Prescribe displacement with {(node, component): metres},
    where the Cartesian components are indexed 0, 1, 2. Each disconnected
    component must have all six rigid modes constrained. Body force density
    is a constant Cartesian vector in N/m^3. Traction maps exterior face
    tags to constant Cartesian vectors in Pa. All quantities are SI numbers.
    """
    fields = _elasticity3d.solve_fields(
        mesh, youngs_modulus=youngs_modulus, poisson_ratio=poisson_ratio,
        prescribed_displacement=prescribed_displacement, body_force_density=body_force_density,
        traction=traction)
    return Elasticity3DResult(**fields)
