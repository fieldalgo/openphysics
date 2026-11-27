# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Backward Euler heat conduction with consistent P1 tetrahedral capacity."""
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from ._public import ResultSurface
from ._thermal3d import RATE_FIELDS, solve_transient_fields

__all__ = ["TransientHeat3DResult", "solve_transient_heat_3d"]


@dataclass(frozen=True, eq=False)
class TransientHeat3DResult(ResultSurface):
    """Read-only histories: time (S,) s, temperature (S,N) K, stored heat (S,) J.

    The six heat-rate arrays are nodal (S-1,N) in W, with one row per interval.
    Generation and reaction are positive into the body. Prescribed and convective
    rates are outward-positive. The change in stored heat is dt times the sum
    of the nodal storage rates. Reaction is zero on free nodes.
    """

    time: np.ndarray
    temperature: np.ndarray
    stored_heat: np.ndarray
    generated_heat_rate: np.ndarray
    outward_prescribed_heat_rate: np.ndarray
    outward_convective_heat_rate: np.ndarray
    reaction_heat_rate: np.ndarray
    heat_storage_rate: np.ndarray
    residual_heat_rate: np.ndarray

    BASIS = "3d"
    UNITS = MappingProxyType({"time": "s", "temperature": "K", "stored_heat": "J",
                              **dict.fromkeys(RATE_FIELDS, "W")})


def solve_transient_heat_3d(mesh, *, thermal_conductivity, volumetric_heat_capacity,
                            time, initial_temperature, prescribed_temperature=None,
                            heat_source_density=None, inward_heat_flux=None, convection=None):
    """Solve on a Mesh3D in metres with stationary coefficients and boundaries.

    Conductivity (W/(m K)) and volumetric heat capacity (J/(m^3 K)) are positive
    scalars or mappings covering the named regions. Time is a strictly
    increasing sequence of at least two finite seconds. Initial temperature
    is a nodal vector in K and matches any fixed exterior-node temperatures.
    Flux and convection use the steady solver's exterior face tags and signs.

    The source in W/m^3 is a scalar, regional map or one value per
    tetrahedron. A callable is evaluated once per interval at its midpoint
    in seconds and returns one of those forms. Include every switch time in
    the time grid. Unspecified boundaries are insulated.
    """
    fields = solve_transient_fields(
        mesh, thermal_conductivity=thermal_conductivity, volumetric_heat_capacity=volumetric_heat_capacity,
        time=time, initial_temperature=initial_temperature, prescribed_temperature=prescribed_temperature,
        heat_source_density=heat_source_density, inward_heat_flux=inward_heat_flux, convection=convection,
    )
    return TransientHeat3DResult(**fields)
