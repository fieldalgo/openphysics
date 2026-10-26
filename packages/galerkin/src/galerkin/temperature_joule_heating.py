# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Temperature-dependent 2D DC heating using the existing steady solvers."""
import copy
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from .electric import ElementConductivity, solve_steady_electric
from .joule_heating import solve_steady_joule_heat, SteadyJouleHeatResult
from .materials import region_index
from .core.checks import finite_scalar, readonly_copy, real_array
from .core.triangles import triangle_geometry


@dataclass(frozen=True)
class ConductivityModel:
    """Vector sigma(T) callback in S/m and inclusive valid Kelvin interval."""
    evaluate: object
    temperature_range: tuple

    def __post_init__(self):
        if not callable(self.evaluate):
            raise ValueError("evaluate must be a deterministic vector callback")
        bounds = real_array(self.temperature_range, "temperature_range")
        if bounds.shape != (2,) or not 0 <= bounds[0] < bounds[1]:
            raise ValueError("temperature_range requires 0 <= min < max in K")
        object.__setattr__(self, "temperature_range", tuple(map(float, bounds)))


@dataclass(frozen=True)
class JouleIteration:
    iteration: int
    temperature_defect: float
    conductivity_defect: float
    minimum_temperature: float
    maximum_temperature: float
    electric_free_residual: float
    thermal_free_residual: float
    nonlinear_heat_residual: float
    current_balance: float
    supplied_power_per_length: float
    joule_power_per_length: float
    outward_heat_per_length: float
    electric_power_defect: float
    heat_power_defect: float


@dataclass(frozen=True)
class TemperatureJouleHeatResult:
    coupled: SteadyJouleHeatResult
    evaluated_temperature: np.ndarray
    history: tuple[JouleIteration, ...]


class JouleConvergenceError(RuntimeError):
    """No successful result; completed iterations and failed state are retained."""
    def __init__(self, reason, history, temperature):
        super().__init__(reason)
        self.reason = reason
        self.history = tuple(history)
        self.last_temperature = readonly_copy(temperature)


def _models(mesh, value):
    if isinstance(value, ConductivityModel):
        return [("all", np.arange(mesh.num_triangles), value)]
    if not isinstance(value, Mapping):
        raise ValueError("electrical_conductivity must be a ConductivityModel or region table")
    regions, names = region_index(mesh)
    if set(value) != set(names) or not all(isinstance(v, ConductivityModel) for v in value.values()):
        raise ValueError("conductivity models must match mesh region names exactly")
    return [(name, np.flatnonzero(regions == i), value[name]) for i, name in enumerate(names)]


def _conductivity(mesh, models, temperature):
    nodal = real_array(temperature, "temperature")
    sigma = np.empty(mesh.num_triangles)
    for name, cells, model in models:
        if not len(cells):
            continue
        values = nodal[mesh.triangles[cells]]
        lo, hi = model.temperature_range
        if np.any(values < lo) or np.any(values > hi):
            raise ValueError(f"material {name!r}: temperature [{values.min()}, {values.max()}] K "
                             f"outside [{lo}, {hi}] K")
        # Divide before summing to avoid overflow of otherwise valid Kelvin inputs.
        mean = np.sum(values/3., axis=1)
        result = real_array(model.evaluate(readonly_copy(mean)), f"sigma in material {name!r}")
        if result.shape != mean.shape or np.any(result <= 0):
            raise ValueError(f"sigma in material {name!r} must have shape {mean.shape} and be > 0")
        sigma[cells] = result
    return sigma


def _norm(a):
    return float(np.max(np.abs(a), initial=0.))


def solve_temperature_joule_heat(
        mesh, *, electrical_conductivity, thermal_conductivity,
        electric_dirichlet, thermal_dirichlet, initial_temperature,
        outward_current=None, reference_potential=None, outward_flux=None,
        convection=None, relaxation=0.5, temperature_atol=1e-8,
        relative_tolerance=1e-10, max_iterations=100):
    """Relaxed Picard coupling; see temperature_joule_heating.md for the contract.

    Temperature defects are unrelaxed. Both temperature and sigma must converge;
    nonlinear heat residual at the returned temperature must be <= 1e-8 relative
    to the Joule and thermal boundary loads. Failures raise JouleConvergenceError with history.
    """
    relaxation = finite_scalar(relaxation, "relaxation")
    atol = finite_scalar(temperature_atol, "temperature_atol")
    rtol = finite_scalar(relative_tolerance, "relative_tolerance")
    if not 0 < relaxation <= 1 or atol <= 0 or rtol <= 0:
        raise ValueError("relaxation must be in (0,1]; tolerances must be positive")
    if isinstance(max_iterations, (bool, np.bool_)) or not isinstance(max_iterations, (int, np.integer)) or max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer")
    mesh = copy.deepcopy(mesh)
    _, _, _, boundary, _, _ = triangle_geometry(mesh)
    models = _models(mesh, electrical_conductivity)
    temperature = real_array(initial_temperature, "initial_temperature")
    if temperature.shape == ():
        temperature = np.full(mesh.num_nodes, float(temperature))
    elif temperature.shape == (mesh.num_nodes,):
        temperature = temperature.copy()
    else:
        raise ValueError("initial_temperature must be scalar or shape (N,) in K")
    if not isinstance(thermal_dirichlet, Mapping):
        raise ValueError("thermal_dirichlet must map exterior node indices to K")
    thermal_dirichlet = dict(thermal_dirichlet)
    electric_dirichlet = copy.deepcopy(electric_dirichlet)
    thermal_conductivity = copy.deepcopy(thermal_conductivity)
    outward_current, reference_potential, outward_flux, convection = copy.deepcopy(
        (outward_current, reference_potential, outward_flux, convection))
    for node, value in thermal_dirichlet.items():
        if isinstance(node, (bool, np.bool_)) or not isinstance(node, (int, np.integer)) or node not in boundary:
            raise ValueError("thermal Dirichlet nodes must be exterior integer indices")
        temperature[node] = finite_scalar(value, "thermal Dirichlet temperature")
    free_t = np.setdiff1d(np.arange(mesh.num_nodes), list(thermal_dirichlet))
    history = []
    def electric(sigma):
        return solve_steady_electric(mesh, conductivity=ElementConductivity(mesh, sigma),
            dirichlet=electric_dirichlet, outward_current=outward_current,
            reference_potential=reference_potential)
    for iteration in range(1, max_iterations+1):
        failed_temperature = temperature
        try:
            sigma = _conductivity(mesh, models, temperature)
            electrical = electric(sigma)
            coupled = solve_steady_joule_heat(mesh, electrical_result=electrical,
                conductivity=thermal_conductivity, dirichlet=thermal_dirichlet,
                outward_flux=outward_flux, convection=convection)
            heat = coupled.thermal
            trial = heat.temperature
            failed_temperature = trial
            trial_sigma = _conductivity(mesh, models, trial)
            defect = _norm(trial-temperature)
            sigma_defect = _norm((trial_sigma-sigma)/np.maximum(sigma, trial_sigma))
            # Independent electrical refresh measures the nonlinear heat equation
            # at H(T_i), rather than only reporting linear subsolve residuals.
            refreshed = electric(trial_sigma)
            nonlinear = heat.residual + heat.load - refreshed.joule_load
            nonlinear_scale = max(_norm(heat.load), _norm(refreshed.joule_load),
                _norm(heat.reaction), _norm(heat.prescribed_outward_load),
                _norm(heat.convective_outward), np.finfo(float).tiny)
            nonlinear_residual = _norm(nonlinear[free_t])/nonlinear_scale
            free_e = np.setdiff1d(np.arange(mesh.num_nodes), list(electric_dirichlet))
            history.append(JouleIteration(iteration, defect, sigma_defect,
                float(trial.min()), float(trial.max()),
                _norm(electrical.residual[free_e]), _norm(heat.residual[free_t]),
                nonlinear_residual,
                float(np.sum(electrical.reaction-electrical.prescribed_outward_load)),
                electrical.supplied_power_per_length, coupled.source_power_per_length,
                coupled.outward_heat_per_length,
                electrical.supplied_power_per_length-coupled.source_power_per_length,
                coupled.outward_heat_per_length-coupled.source_power_per_length))
            if (defect <= atol + rtol*max(_norm(temperature), _norm(trial))
                    and sigma_defect <= rtol and nonlinear_residual <= 1e-8):
                return TemperatureJouleHeatResult(coupled, readonly_copy(temperature), tuple(history))
            temperature = (1-relaxation)*temperature + relaxation*trial
        except Exception as exc:
            raise JouleConvergenceError(str(exc), history, failed_temperature) from exc
    raise JouleConvergenceError("maximum iterations exceeded", history, temperature)
