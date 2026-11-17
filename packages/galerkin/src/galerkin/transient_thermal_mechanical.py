# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Stored-index, one-way transient heat to small-strain quasistatic mechanics.

Heat is computed separately. No interpolation, inertia, damping or feedback.
See docs/packages/galerkin/transient_thermal_mechanical.md for the validation and memory contract.
Quantities are keyword-only registry names in SI units (the units convention of the
galerkin step); a str for a quantity raises TypeError.
"""
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from .mesh import Mesh
from .core.checks import real_array, real_scalar
from .coupling import Field, OneWayChain, transfer
from ._thermal_mechanical_common import check_mesh_unchanged, dirichlet_supports, isolated_mesh, mesh_state
from .materials import is_per_region, region_property
from .thermoelasticity import (TemperatureSnapshot, ThermoelasticResult,
                              freeze_temperature, solve_thermoelasticity)
from .transient_heat import TransientHeatResult
from ._public import ResultSurface, refuse_text

__all__ = ["TransientThermoelasticError", "TransientThermoelasticStep",
           "TransientThermoelasticResult", "solve_transient_thermoelasticity"]


class TransientThermoelasticError(ValueError):
    """Atomic input/transfer/mechanics failure, retaining the original cause."""

    def __init__(self, stage, *, time_index=None, time=None):
        refuse_text("time", time)
        self.stage = stage
        self.time_index = time_index
        self.time = time
        where = "" if time_index is None else f" at time index {time_index}, time={time!r}"
        super().__init__(f"transient thermoelasticity [{stage}]{where}")


def _stage_error(stage, exc, **context):
    return TransientThermoelasticError(stage, **context)


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
class TransientThermoelasticStep(ResultSurface):
    """One exact stored index; snapshot immutable, mechanical fields mutable.

    ``time`` is the stored heat time in s; ``.units`` maps it to its canonical unit.
    """
    UNITS = MappingProxyType({"time": "s"})
    BASIS = "planar"

    time_index: int
    time: float
    temperature_snapshot: TemperatureSnapshot
    mechanics: ThermoelasticResult


@dataclass(frozen=True)
class TransientThermoelasticResult(ResultSurface):
    """Selected steps only; no heat-history reference or post-return certification.

    The owned reference_mesh and mechanics arrays remain mutable. Snapshots
    retain immutable geometry and temperature copies, O(S*(N+M)) total storage.
    Its fields are objects (``.units`` is empty); ``time`` gives the steps' times in s.
    """
    UNITS = MappingProxyType({})
    BASIS = "planar"

    reference_mesh: Mesh
    steps: tuple[TransientThermoelasticStep, ...]

    @property
    def time_indices(self):
        return tuple(step.time_index for step in self.steps)

    @property
    def time(self):
        """The selected steps' stored times in s."""
        return tuple(step.time for step in self.steps)


#: the quantity parameters of solve_transient_thermoelasticity, refused as text (SI numbers only)
_QUANTITIES = ("youngs_modulus", "poisson_ratio", "linear_expansion_coefficient", "stress_free_temperature",
               "prescribed_displacement", "body_force_density")


def solve_transient_thermoelasticity(
    mesh, heat, *, time_indices=None, youngs_modulus, poisson_ratio,
    plane, linear_expansion_coefficient, stress_free_temperature,
    prescribed_displacement, body_force_density=None,
):
    """Apply existing static mechanics to selected temperatures of a heat result.

    SI only: heat is a planar TransientHeatResult in m, s and K.
    time_indices=None selects every stored index including the initial state.
    Require identical ordered geometry/connectivity; no mesh/time interpolation.
    prescribed_displacement maps fixed exterior (node, component) to displacement in m;
    body_force_density is None (no body force) or a constant two-vector N/m^3. Natural
    total traction is zero. youngs_modulus is Pa, linear_expansion_coefficient 1/K,
    stress_free_temperature nonnegative K; plane is 'stress' or 'strain'.
    youngs_modulus, poisson_ratio and linear_expansion_coefficient may each be
    {region name: value} over mesh.region_names. All selected Kelvin snapshots are
    validated and frozen before any mechanics call. No partial aggregate is returned
    after failure; exceptions chain the original cause. A str for a quantity raises
    TypeError.
    """
    for name, value in zip(_QUANTITIES, (youngs_modulus, poisson_ratio, linear_expansion_coefficient,
                                         stress_free_temperature, prescribed_displacement, body_force_density)):
        refuse_text(name, value)
    body_force = (0., 0.) if body_force_density is None else body_force_density
    chain = OneWayChain(_stage_error)
    with chain.stage("input"):
        if not isinstance(heat, TransientHeatResult):
            raise ValueError("heat must be a TransientHeatResult")
        owned = isolated_mesh(mesh)
        state = mesh_state(owned)
        nodes = real_array(heat.node_coordinates, "heat.node_coordinates")
        triangles = np.asarray(heat.triangles)
        if (triangles.dtype.kind not in "iu"
                or not np.array_equal(nodes, owned.nodes)
                or not np.array_equal(triangles, owned.triangles)):
            raise ValueError("heat and mechanics require identical ordered nodes and triangles")
        times = real_array(heat.time, "heat.time")
        with np.errstate(over="ignore", invalid="ignore"):
            differences = np.diff(times) if times.ndim == 1 else np.array([])
        if (times.ndim != 1 or len(times) < 2 or np.any(times < 0)
                or not np.all(np.isfinite(differences)) or np.any(differences <= 0)):
            raise ValueError("heat.time must have at least two strictly increasing nonnegative seconds")
        # Validate consumed fields only; heat diagnostics/provenance are not certified.
        temperatures = real_array(heat.temperature, "heat.temperature")
        if temperatures.shape != (len(times), len(owned.nodes)):
            raise ValueError("heat.temperature must have shape (stored times, nodes)")
        selected = _indices(time_indices, len(times))
        def material(value, name, **bounds):
            if is_per_region(value):
                region_property(owned, value, name, **bounds)
                return {str(k): float(value[k]) for k in sorted(value)}
            return real_scalar(value, name)
        e = material(youngs_modulus, "youngs_modulus", positive=True)
        nu = material(poisson_ratio, "poisson_ratio", lower=-1., upper=.5)
        alpha = material(linear_expansion_coefficient, "linear_expansion_coefficient")
        tref = real_scalar(stress_free_temperature, "stress_free_temperature")
        if ((not isinstance(e, dict) and e <= 0) or (not isinstance(nu, dict) and not -1 < nu < .5)
                or tref < 0 or plane not in ("stress", "strain")):
            raise ValueError("require youngs_modulus > 0, -1 < poisson_ratio < 0.5, stress_free_temperature >= 0 K "
                             "and plane 'stress' or 'strain'")
        supports = dirichlet_supports(prescribed_displacement, vector=True)
        # Reject bool values explicitly before the shared support normalizer casts.
        for value in prescribed_displacement.values():
            real_scalar(value, "prescribed_displacement")
        body = real_array(body_force, "body_force_density")
        if body.shape != (2,):
            raise ValueError("body_force_density must be a constant Cartesian (2,) vector")

    snapshots = []
    for index in selected:
        with chain.stage("transfer", time_index=index, time=float(times[index])):
            # Same-mesh identity transfer of the stored nodal Kelvin field.
            nodal = transfer(Field(owned, temperatures[index], location="node", unit="K",
                                   name="heat.temperature"), owned)
            snapshots.append(freeze_temperature(owned, temperature=nodal.values))
    # The entire input history copy is temporary; only selected snapshots survive.
    del temperatures
    steps = []
    for index, snapshot in zip(selected, snapshots):
        with chain.stage("mechanics", time_index=index, time=float(times[index])):
            mechanics = solve_thermoelasticity(
                owned, snapshot, stress_free_temperature=tref,
                linear_expansion_coefficient=alpha, youngs_modulus=e,
                poisson_ratio=nu, plane=plane, prescribed_displacement=supports,
                body_force_density=body,
            )
            check_mesh_unchanged(owned, state)
        steps.append(TransientThermoelasticStep(int(index), float(times[index]), snapshot, mechanics))
    return TransientThermoelasticResult(owned, tuple(steps))
