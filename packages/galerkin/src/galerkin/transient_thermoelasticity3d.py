# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Quasistatic 3D elastic response to a prescribed nodal temperature history."""
from collections.abc import Sequence
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from ._public import ResultSurface, refuse_tagged_text, refuse_text
from .core.checks import real_array
from .elasticity3d import Elasticity3DResult
from .mesh3d import Mesh3D
from .thermoelasticity3d import solve_thermoelasticity_3d

__all__ = ["ThermoelasticityHistory3DResult", "solve_thermoelasticity_history_3d"]


@dataclass(frozen=True)
class ThermoelasticityHistory3DResult(ResultSurface):
    """Selected times (s), their input row indices and corresponding elastic results."""

    BASIS = "3d"
    UNITS = MappingProxyType({"time": "s"})

    time: np.ndarray
    sample_indices: tuple[int, ...]
    steps: tuple[Elasticity3DResult, ...]


def _sample_indices(value, count):
    if value is None:
        return tuple(range(count))
    if isinstance(value, np.ndarray):
        if value.ndim != 1:
            raise ValueError("sample_indices must be a one-dimensional integer sequence")
    elif not isinstance(value, Sequence):
        raise ValueError("sample_indices must be a one-dimensional integer sequence")
    if not len(value) or any(isinstance(i, (bool, np.bool_))
                             or not isinstance(i, (int, np.integer)) for i in value):
        raise ValueError("sample_indices must contain one or more integer indices")
    indices = tuple(int(i) for i in value)
    if indices[0] < 0 or indices[-1] >= count or any(a >= b for a, b in zip(indices, indices[1:])):
        raise ValueError("sample_indices must be strictly increasing and within the history")
    return indices


def solve_thermoelasticity_history_3d(
    mesh, *, time, temperature, sample_indices=None, stress_free_temperature,
    linear_expansion_coefficient, youngs_modulus, poisson_ratio, prescribed_displacement,
    body_force_density=None, traction=None,
):
    """Solve static elasticity at each selected time in a same-mesh temperature history.

    The time array (S,) holds finite, strictly increasing seconds. Temperature
    (S, N) holds finite nonnegative kelvin values in the given mesh's node order.
    By default all rows are solved, including the first. Explicit sample indices
    select exact stored rows in increasing order. Material and load arguments
    have the same meaning and SI units as in solve_thermoelasticity_3d.
    """
    for name, value in (
        ("time", time), ("temperature", temperature), ("stress_free_temperature", stress_free_temperature),
        ("linear_expansion_coefficient", linear_expansion_coefficient), ("youngs_modulus", youngs_modulus),
        ("poisson_ratio", poisson_ratio), ("prescribed_displacement", prescribed_displacement),
        ("body_force_density", body_force_density),
    ):
        refuse_text(name, value)
    refuse_tagged_text("traction", traction)
    if not isinstance(mesh, Mesh3D):
        raise TypeError("solve_thermoelasticity_history_3d takes a galerkin.Mesh3D")
    times = real_array(time, "time")
    if times.ndim != 1 or not times.size or np.any(times[1:] <= times[:-1]):
        raise ValueError("time must be a nonempty one-dimensional strictly increasing array")
    nodal = real_array(temperature, "temperature")
    if nodal.shape != (times.size, mesh.num_nodes):
        raise ValueError(f"temperature must have shape ({times.size}, {mesh.num_nodes}) in mesh node order")
    if np.any(nodal < 0):
        raise ValueError("temperature must be nonnegative in K")
    indices = _sample_indices(sample_indices, times.size)
    steps = tuple(
        solve_thermoelasticity_3d(
            mesh, temperature=nodal[index], stress_free_temperature=stress_free_temperature,
            linear_expansion_coefficient=linear_expansion_coefficient, youngs_modulus=youngs_modulus,
            poisson_ratio=poisson_ratio, prescribed_displacement=prescribed_displacement,
            body_force_density=body_force_density, traction=traction,
        )
        for index in indices
    )
    selected_times = times[list(indices)]
    selected_times.flags.writeable = False
    return ThermoelasticityHistory3DResult(selected_times, indices, steps)
