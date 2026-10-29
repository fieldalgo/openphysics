# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Temperature-dependent 2D DC heating using the existing steady solvers.

Two methods share one convergence judgment: relaxed Picard iteration (the
default) and Newton's method on the potential and the temperature together
(``method="newton"``), whose Jacobian is sparse. See
docs/packages/galerkin/temperature_joule_heating.md for the contract.
"""
import copy
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from .electric import ElementConductivity, solve_steady_electric
from .joule_heating import solve_steady_joule_heat, SteadyJouleHeatResult
from .materials import region_index, region_property
from .core import forms, kernels
from .core import solve as core_solve
from .core.backend import is_live
from .core.boundary import scalar_boundary_samples
from .core.checks import finite_scalar, one_of, readonly_copy, real_array, refuse_live
from .core.sparse import CooMatrix
from .core.triangles import triangle_geometry
from .thermal import scalar_boundary_system

METHODS = ("picard", "newton")
# Difference step for dsigma/dT, relative to max(1 K, |T|): eps**(1/3), about
# 1.8e-3 K at 300 K. The relative truncation error grows as (step/L)**2, with L
# the temperature over which sigma changes: about 3e-10 for L = 100 K; for the
# steepest contract thermistor (L = 1/9 K) about 3e-4 central and 5e-4 at the
# one-sided start from 300 K. A model's derivative avoids it.
_DIFFERENCE_STEP = float(np.cbrt(np.finfo(float).eps))
# Complex step for the element Jacobian: no subtraction, so any tiny step is exact.
_COMPLEX_STEP = 1e-30
# A Newton step is halved at most this many times (to 2**-30 of its length).
_HALVINGS = 30


@dataclass(frozen=True)
class ConductivityModel:
    """Vector sigma(T) callback in S/m and inclusive valid Kelvin interval.

    ``derivative`` is an optional vector callback dsigma/dT in S/(m K) on the same
    element-mean temperatures. Only ``method="newton"`` uses it, and only to form
    its step: without it, differences of ``evaluate`` at the element mean and at
    points inside the material range are used. It never enters the convergence
    tests or the returned result.
    """
    evaluate: object
    temperature_range: tuple
    derivative: object = None

    def __post_init__(self):
        if not callable(self.evaluate):
            raise ValueError("evaluate must be a deterministic vector callback")
        if self.derivative is not None and not callable(self.derivative):
            raise ValueError("derivative must be None or a deterministic vector callback")
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


def _live_leaves(value):
    """The JAX and PyTorch arrays in ``value``, searching mapping values, lists and tuples.

    ``core.checks.contains_live`` does not look inside mappings, and boundary
    data here are tables such as ``{node: volts}`` and ``{tag: (h, ambient)}``.
    """
    if isinstance(value, Mapping):
        return [leaf for v in value.values() for leaf in _live_leaves(v)]
    if isinstance(value, (list, tuple)):
        return [leaf for v in value for leaf in _live_leaves(v)]
    return [value] if is_live(value) else []


def _refuse_live_inputs(**inputs):
    """TypeError for any input holding a JAX or PyTorch value, before anything copies or checks it.

    Both methods find their solution by iteration and return NumPy numbers; a
    derivative needs the implicit derivative of the coupled residual
    (docs/packages/galerkin/differentiation.md#iterative-solvers), which this
    solver does not provide. Values a callback returns (conductivity or
    boundary condition) are seen only when it runs, inside the iteration.
    """
    for name, value in inputs.items():
        refuse_live(_live_leaves(value), f"solve_temperature_joule_heat {name}")


def _models(mesh, value):
    if isinstance(value, ConductivityModel):
        return [("all", np.arange(mesh.num_triangles), value)]
    if not isinstance(value, Mapping):
        raise ValueError("electrical_conductivity must be a ConductivityModel or region table")
    regions, names = region_index(mesh)
    if set(value) != set(names) or not all(isinstance(v, ConductivityModel) for v in value.values()):
        raise ValueError("conductivity models must match mesh region names exactly")
    return [(name, np.flatnonzero(regions == i), value[name]) for i, name in enumerate(names)]


def _sigma(model, mean, name):
    """Checked ``model.evaluate`` at element-mean temperatures."""
    result = real_array(model.evaluate(readonly_copy(mean)), f"sigma in material {name!r}")
    if result.shape != mean.shape or np.any(result <= 0):
        raise ValueError(f"sigma in material {name!r} must have shape {mean.shape} and be > 0")
    return result


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
        sigma[cells] = _sigma(model, mean, name)
    return sigma


def _conductivity_derivative(mesh, models, temperature):
    """dsigma/dT at the element-mean temperatures, S/(m K).

    The model's ``derivative`` when given. Otherwise differences of ``evaluate``:
    central, second-order one-sided where the mean lies within a step of a range
    end, and first order where that two-step stencil does not fit in the range
    (ranges narrower than three steps). Apart from the element mean, every point
    lies inside the range.
    """
    out = np.empty(mesh.num_triangles)
    for name, cells, model in models:
        if not len(cells):
            continue
        mean = np.sum(temperature[mesh.triangles[cells]]/3., axis=1)
        if model.derivative is not None:
            values = real_array(model.derivative(readonly_copy(mean)), f"dsigma/dT in material {name!r}")
            if values.shape != mean.shape:
                raise ValueError(f"dsigma/dT in material {name!r} must have shape {mean.shape}")
        else:
            values = _difference(model, mean, name)
            if not np.all(np.isfinite(values)):
                raise ValueError(f"dsigma/dT in material {name!r} exceeds floating-point range")
        out[cells] = values
    return out


def _difference(model, mean, name):
    """dsigma/dT by differences of ``model.evaluate``; apart from ``mean``, every point is in range."""
    lo, hi = model.temperature_range
    step = _DIFFERENCE_STEP*np.maximum(1., np.abs(mean))
    up, down = np.minimum(mean+step, hi), np.maximum(mean-step, lo)
    values = (_sigma(model, up, name)-_sigma(model, down, name))/(up-down)
    # Within a step of an end: (-3 s(T) + 4 s(T+h) - s(T+2h))/(2h), mirrored at the top.
    for side, ends in ((1., (mean-step < lo) & (mean+2*step <= hi)),
                       (-1., (mean+step > hi) & (mean-2*step >= lo))):
        if np.any(ends):
            at, h = mean[ends], side*step[ends]
            values[ends] = (-3*_sigma(model, at, name)+4*_sigma(model, at+h, name)
                            - _sigma(model, at+2*h, name))/(2*h)
    return values


def _norm(a):
    return float(np.max(np.abs(a), initial=0.))


def _euclidean(a):
    """The line search's merit: the Euclidean norm of a temperature defect."""
    return float(np.linalg.norm(a))


class _JointNewton:
    """Newton steps for R(V, T) = 0, the electric and heat equations of this workflow together.

    R_V = K_e(sigma(T)) V + outward and R_T = (K_t + H) T - Q(V, T) - (B - G),
    with Q the Joule load, on the nodes free of electric Dirichlet or gauge and
    thermal Dirichlet values. Element blocks of the Jacobian come from a complex
    step through ``core.kernels`` (sigma extended to first order by dsigma/dT,
    as sigma depends on the mean of the three nodal temperatures); the heat
    operator K_t + H is the one the heat solve uses. One sparse direct solve
    per step. NumPy only.
    """

    def __init__(self, mesh, thermal_conductivity, thermal_dirichlet, electric_fixed,
                 outward_flux, convection):
        p, t, _, _, count, labels = triangle_geometry(mesh)
        n = mesh.num_nodes
        samples = scalar_boundary_samples(mesh, p, t, thermal_dirichlet, outward_flux, convection)
        H, G, B, _ = scalar_boundary_system(samples, n, labels, [0.]*count, np.zeros(count, dtype=bool))
        k = region_property(mesh, thermal_conductivity, "conductivity", positive=True)
        cells = np.asarray(mesh.triangles)
        heat = forms.matrix(cells, cells, kernels.p1_stiffness(mesh, k), (n, n)).to_scipy()+H
        self.mesh, self.n, self.cells = mesh, n, cells
        self.heat_operator = heat.tocsr()
        self.heat_rhs = np.asarray(B)-np.asarray(G)
        self.gradients, _ = kernels.triangle_gradients(mesh)
        coo = self.heat_operator.tocoo()
        self.heat_block = CooMatrix(n+coo.row, n+coo.col, coo.data, (2*n, 2*n))
        self.dofs = np.concatenate([cells, n+cells], axis=1)
        fixed = sorted({int(i) for i in electric_fixed} | {n+int(i) for i in thermal_dirichlet})
        self.fixed = np.array(fixed, dtype=int)

    def element_residuals(self, sigma, local):
        """Element electric residuals K_e V_e and Joule loads, (T, 3) each, from element potentials (T, 3).

        Analytic in sigma and the potentials (no absolute value or conjugate).
        """
        r_electric = np.einsum("tij,tj->ti", kernels.p1_stiffness(self.mesh, sigma), local)
        field = -np.einsum("tad,ta->td", self.gradients, local)
        _, _, load = kernels.p1_joule(self.mesh, sigma, field)
        return r_electric, load

    def element_jacobian(self, sigma, dsigma, potential):
        """(T, 6, 6): rows (R_V, R_T) of each element, columns (V, T) of its nodes; complex step."""
        h = _COMPLEX_STEP
        out = np.empty((len(self.cells), 6, 6))
        local = potential[self.cells].astype(complex)
        for j in range(3):
            moved = local.copy()
            moved[:, j] += 1j*h
            r_v, load = self.element_residuals(sigma.astype(complex), moved)
            out[:, :3, j], out[:, 3:, j] = r_v.imag/h, -load.imag/h
        # sigma depends on the mean of the element's three nodal temperatures:
        # moving any one of them moves the mean by a third, so the T columns agree.
        r_v, load = self.element_residuals(sigma+1j*h*dsigma/3., local)
        for j in range(3, 6):
            out[:, :3, j], out[:, 3:, j] = r_v.imag/h, -load.imag/h
        return out

    def jacobian(self, sigma, dsigma, potential):
        """The joint Jacobian (2N, 2N) as a CooMatrix (duplicates add)."""
        blocks = self.element_jacobian(sigma, dsigma, potential)
        return forms.matrix(self.dofs, self.dofs, blocks, (2*self.n, 2*self.n))+self.heat_block

    def step(self, temperature, sigma, dsigma, electrical, heat_load):
        """Temperature increment of one Newton step from (V(T), T); zero at thermal Dirichlet nodes.

        ``electrical`` is the electric solve at sigma(T) and ``heat_load`` the
        Joule load the heat solve used, so R_V vanishes up to that solve and
        R_T is the heat residual of T itself.
        """
        potential = np.asarray(electrical.potential)
        residual = np.concatenate([np.asarray(electrical.residual),
                                   self.heat_operator@temperature-heat_load-self.heat_rhs])
        jacobian = self.jacobian(sigma, dsigma, potential)
        try:
            update = core_solve.solve_dirichlet(jacobian, -residual, {tuple(self.fixed): 0.})
        except (RuntimeError, ValueError) as exc:
            raise ValueError("singular or ill-conditioned Newton system") from exc
        if not np.all(np.isfinite(update)):
            raise ValueError("nonfinite Newton step")
        return update[self.n:]


def solve_temperature_joule_heat(
        mesh, *, electrical_conductivity, thermal_conductivity,
        electric_dirichlet, thermal_dirichlet, initial_temperature,
        outward_current=None, reference_potential=None, outward_flux=None,
        convection=None, relaxation=0.5, temperature_atol=1e-8,
        relative_tolerance=1e-10, max_iterations=100, method="picard"):
    """Coupled solve by relaxed Picard or by Newton; see temperature_joule_heating.md for the contract.

    ``method`` defaults to ``"picard"``; the contract page says when to choose ``"newton"``.

    Temperature defects are unrelaxed. Both temperature and sigma must converge;
    nonlinear heat residual at the returned temperature must be <= 1e-8 relative
    to the Joule and thermal boundary loads. Failures raise JouleConvergenceError with history.
    method="newton" takes Newton steps of the potential and temperature together,
    halving a step whose candidate fails to evaluate, or neither converges nor
    reduces the temperature defect; relaxation applies to Picard only. The same
    tests decide convergence.

    NumPy only: a JAX or PyTorch value in any input raises TypeError before
    anything is copied or solved; one returned by a callback surfaces as a
    JouleConvergenceError caused by that TypeError.
    """
    _refuse_live_inputs(
        thermal_conductivity=thermal_conductivity, electric_dirichlet=electric_dirichlet,
        thermal_dirichlet=thermal_dirichlet, initial_temperature=initial_temperature,
        outward_current=outward_current, reference_potential=reference_potential,
        outward_flux=outward_flux, convection=convection, relaxation=relaxation,
        temperature_atol=temperature_atol, relative_tolerance=relative_tolerance,
        max_iterations=max_iterations)
    one_of(method, METHODS, "method")
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

    def evaluate(iteration, temperature):
        """The convergence judgment at T_i: sigma(T_i), H(T_i), its history row and test.

        Failures raise JouleConvergenceError with the completed history and the
        trial heat solution once it exists, otherwise T_i.
        """
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
            row = JouleIteration(iteration, defect, sigma_defect,
                float(trial.min()), float(trial.max()),
                _norm(electrical.residual[free_e]), _norm(heat.residual[free_t]),
                nonlinear_residual,
                float(np.sum(electrical.reaction-electrical.prescribed_outward_load)),
                electrical.supplied_power_per_length, coupled.source_power_per_length,
                coupled.outward_heat_per_length,
                electrical.supplied_power_per_length-coupled.source_power_per_length,
                coupled.outward_heat_per_length-coupled.source_power_per_length)
            converged = (defect <= atol + rtol*max(_norm(temperature), _norm(trial))
                         and sigma_defect <= rtol and nonlinear_residual <= 1e-8)
            return sigma, electrical, coupled, trial, row, converged
        except Exception as exc:
            raise JouleConvergenceError(str(exc), history, failed_temperature) from exc

    if method == "picard":
        for iteration in range(1, max_iterations+1):
            _, _, coupled, trial, row, converged = evaluate(iteration, temperature)
            history.append(row)
            if converged:
                return TemperatureJouleHeatResult(coupled, readonly_copy(temperature), tuple(history))
            temperature = (1-relaxation)*temperature + relaxation*trial
        raise JouleConvergenceError("maximum iterations exceeded", history, temperature)

    sigma, electrical, coupled, trial, row, converged = evaluate(1, temperature)
    history.append(row)
    newton = None
    while not converged:
        if len(history) >= max_iterations:
            raise JouleConvergenceError("maximum iterations exceeded", history, temperature)
        try:
            if newton is None:
                newton = _JointNewton(mesh, thermal_conductivity, thermal_dirichlet,
                                      set(electric_dirichlet) | set(reference_potential or {}),
                                      outward_flux, convection)
            dsigma = _conductivity_derivative(mesh, models, temperature)
            increment = newton.step(temperature, sigma, dsigma, electrical, coupled.thermal.load)
        except Exception as exc:
            raise JouleConvergenceError(str(exc), history, temperature) from exc
        merit = _euclidean(trial-temperature)
        failure, accepted = None, None
        for halving in range(_HALVINGS+1):
            alpha = .5**halving
            candidate = temperature + alpha*increment
            if halving and np.array_equal(candidate, temperature):
                break   # shorter steps no longer change T
            try:
                state = evaluate(len(history)+1, candidate)
            except JouleConvergenceError as exc:
                failure = exc   # e.g. a material range or a subsolve gate at the candidate
                continue
            failure = None
            # state[5]: the convergence judgment; state[3]: H(candidate).
            if state[5] or _euclidean(state[3]-candidate) <= (1-1e-4*alpha)*merit:
                accepted = candidate, state
                break
        if accepted is None:
            reason = (f"Newton step does not reduce the temperature defect "
                      f"({history[-1].temperature_defect:.3g} K)")
            if failure is not None:
                reason += f"; last candidate failed: {failure.reason}"
            raise JouleConvergenceError(reason, history, temperature) from (
                failure.__cause__ if failure is not None else None)
        temperature, state = accepted
        sigma, electrical, coupled, trial, row, converged = state
        history.append(row)
    return TemperatureJouleHeatResult(coupled, readonly_copy(temperature), tuple(history))
