# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Voltage-driven Joule heat coupled implicitly to tetrahedral heat conduction."""
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from ._public import ResultSurface, refuse_text
from .core.checks import positive_integer, positive_real
from .electric3d import SteadyElectric3DResult, _conductivity_at_temperature_3d, solve_steady_electric_3d
from .transient_heat3d import TransientHeat3DResult, _solve_transient_heat_3d

__all__ = ["TransientJouleHeat3DResult", "solve_transient_joule_heat_3d"]


@dataclass(frozen=True, eq=False)
class TransientJouleHeat3DResult(ResultSurface):
    """Thermal history and one electric solve and iteration count per interval."""

    heat: TransientHeat3DResult
    electric: tuple[SteadyElectric3DResult, ...]
    iteration_count: np.ndarray

    BASIS = "3d"
    UNITS = MappingProxyType({"iteration_count": "1"})


def solve_transient_joule_heat_3d(
    mesh, *, time, initial_temperature, electrical_conductivity, prescribed_electric_potential,
    thermal_conductivity, volumetric_heat_capacity, temperature_tolerance, relative_tolerance=1e-8,
    iteration_limit=50, relaxation_factor=1.0, prescribed_temperature=None,
    inward_heat_flux=None, convection=None,
):
    """Couple interval-end temperature (K) to Joule generation (W/m³).

    Supply electrode potentials in V by face tag, or a callback of the interval
    midpoint in seconds. The callback runs once per interval. Include voltage
    switch times in the time grid. Positive inward electric power supplies Joule
    heat. Thermal boundary conditions use the transient heat solver's convention.
    Electrical conductivity in S/m is a constant, a ConductivityModel with a
    valid Kelvin interval, or a material region mapping of those values.

    Convergence requires the maximum undamped temperature update to meet
    temperature_tolerance in K and the maximum symmetric relative change in
    conductivity to meet relative_tolerance. An invalid state or exhausted
    iteration limit raises ValueError with its interval index.
    """
    for name, value in (
        ("electrical_conductivity", electrical_conductivity),
        ("prescribed_electric_potential", prescribed_electric_potential),
        ("temperature_tolerance", temperature_tolerance), ("relative_tolerance", relative_tolerance),
        ("relaxation_factor", relaxation_factor), ("iteration_limit", iteration_limit),
    ):
        refuse_text(name, value)
    temperature_limit = positive_real(temperature_tolerance, "temperature_tolerance")
    relative_limit = positive_real(relative_tolerance, "relative_tolerance")
    iterations = positive_integer(iteration_limit, "iteration_limit")
    damping = positive_real(relaxation_factor, "relaxation_factor")
    if damping > 1:
        raise ValueError("relaxation_factor must be <= 1")

    electric = []
    counts = []

    def conductivity(temperature):
        return _conductivity_at_temperature_3d(mesh, electrical_conductivity, temperature)

    def coupled_step(index, midpoint, previous_temperature, trial):
        try:
            voltages = (prescribed_electric_potential(midpoint)
                        if callable(prescribed_electric_potential) else prescribed_electric_potential)
            if not isinstance(voltages, Mapping):
                raise ValueError("prescribed_electric_potential must supply a mapping of face tags to volts")
            voltages = dict(voltages)
            guess = previous_temperature
            sigma = conductivity(guess)
            for count in range(1, iterations + 1):
                solution = solve_steady_electric_3d(mesh, electrical_conductivity=sigma,
                                                   prescribed_electric_potential=voltages)
                candidate, heat_step = trial(solution.joule_power_density)
                sigma_end = conductivity(candidate)
                temp_change = np.max(np.abs(candidate - guess))
                sigma_change = np.max(np.abs(sigma_end - sigma) / np.maximum(sigma_end, sigma))
                if temp_change <= temperature_limit and sigma_change <= relative_limit:
                    electric.append(solution)
                    counts.append(count)
                    return heat_step
                if damping == 1:
                    guess, sigma = candidate, sigma_end
                else:
                    guess = (1 - damping) * guess + damping * candidate
                    sigma = conductivity(guess)
        except (TypeError, ValueError) as exc:
            error = TypeError if isinstance(exc, TypeError) else ValueError
            raise error(f"Joule heat interval {index} (midpoint {midpoint} s): {exc}") from exc
        raise ValueError(f"Joule heat did not converge on interval {index} (midpoint {midpoint} s) "
                         f"after {iterations} iterations (temperature change {temp_change:.6g} K, "
                         f"relative conductivity change {sigma_change:.6g})")

    heat = _solve_transient_heat_3d(
        mesh, time=time, initial_temperature=initial_temperature, thermal_conductivity=thermal_conductivity,
        volumetric_heat_capacity=volumetric_heat_capacity, prescribed_temperature=prescribed_temperature,
        inward_heat_flux=inward_heat_flux, convection=convection, heat_source_density=None,
        coupled_step=coupled_step,
    )
    iteration_count = np.asarray(counts, dtype=int)
    iteration_count.flags.writeable = False
    return TransientJouleHeat3DResult(heat, tuple(electric), iteration_count)
