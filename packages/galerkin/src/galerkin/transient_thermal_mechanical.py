# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Stored-index, one-way transient heat to small-strain quasistatic mechanics.

Heat is computed separately. No interpolation, inertia, damping or feedback.
See docs/packages/galerkin/transient_thermal_mechanical.md for the validation and memory contract.
"""
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from .mesh import Mesh
from .materials import is_per_region, region_property
from .thermal_mechanical import _isolated_mesh, _mesh_state, _check_mesh, _supports
from .thermoelasticity import (TemperatureSnapshot, ThermoelasticResult,
                              freeze_temperature, solve_thermoelasticity)
from .transient_heat import TransientHeatResult


class TransientThermoelasticError(ValueError):
    """Atomic input/transfer/mechanics failure, retaining the original cause."""

    def __init__(self, stage, *, time_index=None, time_s=None):
        self.stage = stage
        self.time_index = time_index
        self.time_s = time_s
        where = "" if time_index is None else f" at time index {time_index}, time_s={time_s!r}"
        super().__init__(f"transient thermoelasticity [{stage}]{where}")


def _real(value, name):
    if isinstance(value, (bool, np.bool_)) or (
        isinstance(value, (list, tuple))
        and any(isinstance(v, (bool, np.bool_)) for v in value)
    ):
        raise ValueError(f"{name} must not contain booleans")
    a = np.asarray(value)
    if a.dtype.kind not in "iuf" or not np.all(np.isfinite(a)):
        raise ValueError(f"{name} must contain finite real numbers")
    with np.errstate(over="ignore", invalid="ignore"):
        out = np.array(a, dtype=float, copy=True)
    if not np.all(np.isfinite(out)):
        raise ValueError(f"{name} exceeds finite numeric range")
    return out


def _scalar(value, name):
    a = _real(value, name)
    if a.shape != ():
        raise ValueError(f"{name} must be scalar")
    return float(a)


def _indices(value, count):
    if value is None:
        return tuple(range(count))
    if not isinstance(value, (list, tuple, np.ndarray)):
        raise ValueError("time_indices must be a 1D integer sequence")
    if isinstance(value, np.ndarray) and value.ndim != 1:
        raise ValueError("time_indices must be one-dimensional")
    if not len(value) or any(isinstance(i, (bool, np.bool_))
                            or not isinstance(i, (int, np.integer)) for i in value):
        raise ValueError("time_indices must be nonempty integers, not booleans")
    result = tuple(int(i) for i in value)
    if any(i < 0 or i >= count for i in result) or any(a >= b for a, b in zip(result, result[1:])):
        raise ValueError("time_indices must be strictly increasing and within the stored history")
    return result


@dataclass(frozen=True)
class TransientThermoelasticStep:
    """One exact stored index; snapshot immutable, mechanical fields mutable."""

    time_index: int
    time_s: float
    temperature_snapshot: TemperatureSnapshot
    mechanics: ThermoelasticResult


@dataclass(frozen=True)
class TransientThermoelasticResult:
    """Selected steps only; no heat-history reference or post-return certification.

    The owned reference_mesh and mechanics arrays remain mutable. Snapshots
    retain immutable geometry and temperature copies, O(S*(N+M)) total storage.
    """

    reference_mesh: Mesh
    steps: tuple[TransientThermoelasticStep, ...]

    @property
    def time_indices(self):
        return tuple(step.time_index for step in self.steps)

    @property
    def time_s(self):
        return tuple(step.time_s for step in self.steps)


def solve_transient_thermoelasticity(
    mesh, heat, *, units, time_indices=None, young_modulus, poisson_ratio,
    plane, thermal_expansion_per_k, reference_temperature_k,
    mechanical_dirichlet, body_force=(0., 0.),
):
    """Apply existing static mechanics to selected temperatures of a heat result.

    units must be exactly {'length':'m', 'time':'s', 'temperature':'K'}.
    time_indices=None selects every stored index including the initial state.
    Require identical ordered geometry/connectivity; no mesh/time interpolation.
    Supports are fixed exterior (node,component)->displacement m; body_force is
    a constant two-vector N/m^3. Natural total traction is zero. E is Pa, alpha
    1/K, Tref nonnegative K; plane is 'stress' or 'strain'. E, nu and alpha may
    each be {region name: value} over mesh.region_names. All selected Kelvin
    snapshots are validated and frozen before any mechanics call. No partial
    aggregate is returned after failure; exceptions chain the original cause.
    """
    try:
        if not isinstance(units, Mapping) or dict(units) != {
            'length': 'm', 'time': 's', 'temperature': 'K'
        }:
            raise ValueError("units must be exactly {'length':'m','time':'s','temperature':'K'}")
        if not isinstance(heat, TransientHeatResult):
            raise ValueError("heat must be a TransientHeatResult")
        owned = _isolated_mesh(mesh)
        state = _mesh_state(owned)
        nodes = _real(heat.nodes_m, "heat.nodes_m")
        triangles = np.asarray(heat.triangles)
        if (triangles.dtype.kind not in "iu"
                or not np.array_equal(nodes, owned.nodes)
                or not np.array_equal(triangles, owned.triangles)):
            raise ValueError("heat and mechanics require identical ordered nodes and triangles")
        times = _real(heat.time_s, "heat.time_s")
        with np.errstate(over="ignore", invalid="ignore"):
            differences = np.diff(times) if times.ndim == 1 else np.array([])
        if (times.ndim != 1 or len(times) < 2 or np.any(times < 0)
                or not np.all(np.isfinite(differences)) or np.any(differences <= 0)):
            raise ValueError("heat.time_s must have at least two strictly increasing nonnegative seconds")
        # Validate consumed fields only; heat diagnostics/provenance are not certified.
        temperatures = _real(heat.temperature_k, "heat.temperature_k")
        if temperatures.shape != (len(times), len(owned.nodes)):
            raise ValueError("heat.temperature_k must have shape (stored times, nodes)")
        selected = _indices(time_indices, len(times))
        def material(value, name, **bounds):
            if is_per_region(value):
                region_property(owned, value, name, **bounds)
                return {str(k): float(value[k]) for k in sorted(value)}
            return _scalar(value, name)
        e = material(young_modulus, "young_modulus", positive=True)
        nu = material(poisson_ratio, "poisson_ratio", lower=-1., upper=.5)
        alpha = material(thermal_expansion_per_k, "thermal_expansion_per_k")
        tref = _scalar(reference_temperature_k, "reference_temperature_k")
        if ((not isinstance(e, dict) and e <= 0) or (not isinstance(nu, dict) and not -1 < nu < .5)
                or tref < 0 or plane not in ("stress", "strain")):
            raise ValueError("require E>0, -1<nu<.5, Tref>=0K and plane stress/strain")
        supports = _supports(mechanical_dirichlet, vector=True)
        # Reject bool values explicitly before the shared support normalizer casts.
        for value in mechanical_dirichlet.values():
            _scalar(value, "mechanical Dirichlet displacement")
        body = _real(body_force, "body_force")
        if body.shape != (2,):
            raise ValueError("body_force must be a constant Cartesian (2,) vector")
    except Exception as exc:
        raise TransientThermoelasticError("input") from exc

    snapshots = []
    for index in selected:
        try:
            snapshots.append(freeze_temperature(owned, temperatures[index]))
        except Exception as exc:
            raise TransientThermoelasticError(
                "transfer", time_index=index, time_s=float(times[index])) from exc
    # The entire input history copy is temporary; only selected snapshots survive.
    del temperatures
    steps = []
    for index, snapshot in zip(selected, snapshots):
        try:
            mechanics = solve_thermoelasticity(
                owned, snapshot, reference_temperature_k=tref,
                thermal_expansion_per_k=alpha, young_modulus=e,
                poisson_ratio=nu, plane=plane, dirichlet=supports,
                body_force=body,
            )
            _check_mesh(owned, state)
        except Exception as exc:
            raise TransientThermoelasticError(
                "mechanics", time_index=index, time_s=float(times[index])) from exc
        steps.append(TransientThermoelasticStep(int(index), float(times[index]), snapshot, mechanics))
    return TransientThermoelasticResult(owned, tuple(steps))
