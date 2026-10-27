# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Consistent-mass backward-Euler heat histories on a fixed SI P1 mesh.

Explicit submodule only. See docs/packages/galerkin/transient_heat.md; conductivity, heat
capacity and a constant source may be piecewise constant on named mesh regions
(docs/packages/galerkin/multimaterial.md). Finite Kelvin values are
mathematical inputs, not a physical material-domain or positivity certificate.

Material, source, Dirichlet and initial values may be JAX or PyTorch values
(callbacks may return them); the histories are then arrays of that library and
carry reverse-mode derivatives through every step (all steps are kept). NumPy
inputs compute exactly as before.
"""
from dataclasses import dataclass, fields
import importlib
import sys
from typing import Mapping

import numpy as np
from scipy.sparse.linalg import splu

from .mesh import Mesh
from .materials import is_per_region, region_index, region_property
from .core import forms, kernels
from .core import solve as core_solve
from .core.backend import Backend, backend_of, is_live, lift, live_namespace, scatter_add, to_numpy
from .core.checks import real_array, real_value
from .core.loads import source_load
from .core.sparse import CooMatrix
from .core.triangles import triangle_geometry
from .assembly import assemble_mass, assemble_stiffness
from .postprocess import element_gradient


class TransientHeatStepError(ValueError):
    """A chained sampling/solve/history failure; no successful partial result."""

    def __init__(self, time_index, time_s):
        self.time_index = int(time_index)
        self.time_s = float(time_s)
        super().__init__(
            f"transient heat failed at time index {self.time_index}, "
            f"time_s={self.time_s!r}")


def _scalar(value, name, positive=False):
    a = real_array(value, name)
    if a.shape != () or (positive and a <= 0):
        raise ValueError(f"{name} must be a finite {'positive ' if positive else ''}real scalar")
    return float(a)


def _value(value, name, positive=False):
    """``_scalar``, except that a JAX or PyTorch value stays live (as a 0-d array)."""
    if not is_live(value):
        return _scalar(value, name, positive)
    a = real_value(value, name)
    if tuple(a.shape) != () or (positive and to_numpy(a) <= 0):
        raise ValueError(f"{name} must be a finite {'positive ' if positive else ''}real scalar")
    return a


def _numbers(value):
    """NumPy numbers of a live value: a float for a scalar, else an array."""
    a = to_numpy(value)
    return float(a) if a.ndim == 0 else a


def _recorded(value):
    return value if is_live(value) else float(value)


def _finite(*arrays):
    if not all(np.all(np.isfinite(a)) for a in arrays):
        raise ValueError("derived transient heat data exceed finite numeric range")


def _owned(value, dtype):
    a = np.asarray(value, dtype=dtype)
    # Bytes backing owns a copy; no caller array or mutable mesh is retained.
    return np.frombuffer(a.tobytes(order="C"), dtype=dtype).reshape(a.shape)


@dataclass(frozen=True, eq=False)
class TransientHeatResult:
    """Full copied read-only histories, O(Nt*(N+M)) memory, no downsampling.

    Node temperatures: K; element flux: W/m^2. All nodal rates: W/m depth.
    H is J/m, whereas quadratic V is J K/m and is NOT stored heat.
    Rates/reactions have no entry at t0. nodes_m/triangles capture the mesh.
    conductivity_w_mk and volumetric_heat_capacity_j_m3k are floats, or
    {region name: float} copies for per-region materials.
    Read-only arrays are not a cryptographic tamper/provenance guarantee.
    """
    time_s: np.ndarray
    temperature_k: np.ndarray
    heat_flux_w_m2: np.ndarray
    source_load_w_per_m: np.ndarray
    reaction_w_per_m: np.ndarray
    residual_w_per_m: np.ndarray
    storage_rate_w_per_m: np.ndarray
    heat_content_j_per_m: np.ndarray
    quadratic_functional_jk_per_m: np.ndarray
    dirichlet_node_ids: np.ndarray
    dirichlet_temperatures_k: np.ndarray
    nodes_m: np.ndarray
    triangles: np.ndarray
    conductivity_w_mk: float | dict
    volumetric_heat_capacity_j_m3k: float | dict

    def __post_init__(self):
        # JAX and PyTorch histories are kept as they are (they carry derivatives).
        integer = {"dirichlet_node_ids", "triangles"}
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, np.ndarray):
                dtype = np.dtype("<i8" if f.name in integer else "<f8")
                object.__setattr__(self, f.name, _owned(value, dtype))


def _live_history(xp, mesh, k, capacity, initial, bc0, load0, times, steps, fixed, labels,
                  representatives, sample, advance, record, previous, checkpoint_every):
    """Histories of a run with JAX or PyTorch inputs, in that library.

    Every step first runs on NumPy numbers (``advance``: refined and checked like
    a NumPy run). Its solution x0 then gets the adjoint correction
    x = x0 + A^{-1}(b - A x0): equal to x0 up to rounding, with exact derivatives
    with respect to every live input. That second pass has no checks, so it can
    be recomputed during the backward pass (``checkpoint_every``).
    Returns temperature, flux, load, reaction, residual, storage, content,
    quadratic and Dirichlet histories.
    """
    n, cells = len(labels), np.asarray(mesh.triangles)
    try:
        def lifted(matrix):
            matrix = matrix.coalesce()
            return CooMatrix(matrix.rows, matrix.cols, lift(xp, matrix.values), matrix.shape)
        mass = lifted(forms.matrix(cells, cells, kernels.p1_mass(mesh, capacity), (n, n)))
        stiffness = lifted(forms.matrix(cells, cells, kernels.p1_stiffness(mesh, k), (n, n)))
        if not (np.array_equal(mass.rows, stiffness.rows) and np.array_equal(mass.cols, stiffness.cols)):
            raise ValueError("mass and stiffness patterns differ")
        k, initial = lift(xp, k), lift(xp, initial)
        offsets = initial[representatives][labels]
    except Exception as exc:
        raise TransientHeatStepError(0, times[0]) from exc

    def centered(values):
        return values-values[representatives][labels]

    def recorded(increment, load, bc, first=False):
        absolute = initial if first else increment+offsets
        mtemp = mass.matvec(absolute)
        flux = -(k[:, None] if k.ndim else k)*element_gradient(mesh, centered(increment))
        return absolute, flux, load, bc, xp.sum(mtemp), .5*(absolute@mtemp)

    def step_live(previous, step, bc, load, x0):
        system = CooMatrix(mass.rows, mass.cols, mass.values/step+stiffness.values, (n, n))
        rhs = load+mass.matvec(previous)/step
        x0 = lift(xp, x0)
        delta = core_solve.solve_dirichlet(
            system, rhs-system.matvec(x0),
            {tuple(fixed): bc-offsets[fixed]-x0[fixed]} if len(fixed) else {})
        current = x0+delta
        stored = mass.matvec((current-previous)/step)
        residual = stored+stiffness.matvec(centered(current))-load
        return current, (*recorded(current, load, bc), stored, residual,
                         scatter_add(xp, n, fixed, residual[fixed]))

    def block(previous, sizes, bcs, loads, x0s):
        columns = []
        for step, bc, load, x0 in zip(sizes, bcs, loads, x0s):
            previous, out = step_live(previous, step, bc, load, x0)
            columns.append(out)
        return previous, tuple(xp.stack(column) for column in zip(*columns))

    # Pass 1: NumPy numbers, checks and step errors exactly as for NumPy inputs.
    data = []
    for index, step in enumerate(steps, start=1):
        try:
            bc, load = sample(index)
            bc_n, load_n = to_numpy(bc), to_numpy(load)
            current, _, _, _ = advance(previous, bc_n, load_n, step)
            record(index, current, load_n, bc_n)
            previous = current.copy()
            data.append((float(step), lift(xp, bc, xp.float64), lift(xp, load), current))
        except Exception as exc:
            raise TransientHeatStepError(index, times[index]) from exc

    # Pass 2: derivatives, in blocks of checkpoint_every steps (one block by default).
    try:
        first = recorded(initial-offsets, lift(xp, load0), lift(xp, bc0, xp.float64), first=True)
        state, blocks = initial-offsets, []
        size = checkpoint_every or max(len(data), 1)
        for start in range(0, len(data), size):
            sizes, bcs, loads, x0s = zip(*data[start:start+size])
            run = _checkpointed(xp, block, sizes) if checkpoint_every else (
                lambda prev, b, l, x, sizes=sizes: block(prev, sizes, b, l, x))
            state, columns = run(state, list(bcs), list(loads), list(x0s))
            blocks.append(columns)
        nodal = [xp.concat([xp.stack([first[j]]), *(b[j] for b in blocks)]) for j in range(6)]
        stepped = [xp.concat([b[j] for b in blocks]) for j in range(6, 9)]
    except Exception as exc:
        raise TransientHeatStepError(len(times)-1, times[-1]) from exc
    temperature, flux, loads, bcs, content, quadratic = nodal
    storage, residual, reaction = stepped
    return temperature, flux, loads, reaction, residual, storage, content, quadratic, bcs


def _checkpointed(xp, block, sizes):
    """``block`` for these step sizes, recomputed in the backward pass instead of stored."""
    def run(previous, bcs, loads, x0s):
        return block(previous, sizes, bcs, loads, x0s)
    if backend_of(xp) is Backend.JAX:
        return sys.modules["jax"].checkpoint(run)
    checkpoint = importlib.import_module("torch.utils.checkpoint").checkpoint   # torch is loaded
    return lambda *args: checkpoint(run, *args, use_reentrant=False)


def solve_transient_heat(mesh, *, conductivity, volumetric_heat_capacity,
                         time_s, initial_temperature_k, dirichlet,
                         heat_source=0.0, checkpoint_every=None):
    """Solve c*dT/dt-div(k*grad T)=Q, BE with consistent mass, SI units.

    k>0 W/(m K), c>0 J/(m^3 K), explicit increasing nonnegative seconds,
    finite initial (N,) K. Finite negative K and signed sources are allowed;
    no clamping, maximum principle or physical temperature validity is implied.
    dirichlet: fixed exterior integer node -> scalar K or callback(time_s).
    Q: scalar W/m^3 or callback(points_m,time_s)->exactly(Q,) W/m^3.
    Other edges are insulated; no anchor is required on a transient component.
    k, c and a constant Q may each be {region name: value} over mesh.region_names.
    Pure callbacks/no concurrent input mutation. Time-local failures are chained
    with index/time, no partial result; external callback side effects persist.

    JAX or PyTorch inputs keep every step for the reverse pass by default.
    checkpoint_every=m (int >= 1) keeps only every m-th state and recomputes the
    steps between during the backward pass: less memory, more time. It does not
    change values and has no effect on NumPy inputs.
    """
    if checkpoint_every is not None and (
            isinstance(checkpoint_every, (bool, np.bool_))
            or not isinstance(checkpoint_every, (int, np.integer)) or checkpoint_every < 1):
        raise ValueError("checkpoint_every must be None or an integer >= 1")
    regional = [is_per_region(v) for v in (conductivity, volumetric_heat_capacity, heat_source)]
    k = conductivity if regional[0] else _value(conductivity, "conductivity", True)
    capacity = (volumetric_heat_capacity if regional[1]
                else _value(volumetric_heat_capacity, "volumetric_heat_capacity", True))
    times = real_array(time_s, "time_s").copy()
    if times.ndim != 1 or len(times) < 2 or np.any(times < 0):
        raise ValueError("time_s must be nonnegative 1D seconds with at least two entries")
    with np.errstate(over="ignore", invalid="ignore"):
        steps = np.diff(times)
    if not np.all(np.isfinite(steps)) or np.any(steps <= 0):
        raise ValueError("time_s differences must be finite and strictly positive")

    p, t, area, exterior, count, labels = triangle_geometry(mesh)
    p, t = p.copy(), t.copy()
    # Geometry is validated before Mesh can cast indices or repair orientation.
    record_k, record_c = k, capacity
    if any(regional):
        regions, names = region_index(mesh)
        private_mesh = Mesh(p.copy(), t.copy(), boundary={}, regions=regions.copy(),
                            region_names=list(names))
        # Validate before recording, so a bad value gets the labelled message.
        if regional[0]:
            k = region_property(private_mesh, conductivity, "conductivity", positive=True,
                                live=True)
            record_k = {str(n): _recorded(conductivity[n]) for n in names}
        if regional[1]:
            capacity = region_property(private_mesh, volumetric_heat_capacity,
                                       "volumetric_heat_capacity", positive=True, live=True)
            record_c = {str(n): _recorded(volumetric_heat_capacity[n]) for n in names}
        if regional[2]:
            region_property(private_mesh, heat_source, "heat_source", live=True)
    else:
        private_mesh = Mesh(p.copy(), t.copy(), boundary={})
    initial = real_value(initial_temperature_k, "initial_temperature_k")
    initial = initial if is_live(initial) else initial.copy()
    if tuple(initial.shape) != (len(p),):
        raise ValueError("initial_temperature_k must have exactly shape (N,)")
    if not isinstance(dirichlet, Mapping):
        raise ValueError("dirichlet must map exterior integer nodes to Kelvin values")
    conditions = {}
    for node, value in dirichlet.items():
        if (isinstance(node, (bool, np.bool_))
                or not isinstance(node, (int, np.integer))
                or not 0 <= node < len(p) or node not in exterior):
            raise ValueError("Dirichlet nodes must be exterior integer node indices")
        conditions[int(node)] = value if callable(value) else _value(value, "Dirichlet temperature")
    fixed = np.array(sorted(conditions), dtype=int)
    free = np.setdiff1d(np.arange(len(p)), fixed)
    source = (heat_source if callable(heat_source) or regional[2]
              else _value(heat_source, "heat_source"))
    # NumPy numbers of every live input drive the step and its checks; live values
    # only add derivatives (see _live_history).
    k_live, capacity_live, initial_live = k, capacity, initial
    k, capacity, initial = (_numbers(a) if is_live(a) else a for a in (k, capacity, initial))

    try:
        mass = assemble_mass(private_mesh, capacity)
        stiffness = assemble_stiffness(private_mesh, k)
        _finite(mass.data, stiffness.data)
        if np.any(mass.diagonal() <= 0):
            raise ValueError("consistent mass lost positive diagonal at this numeric scale")
        # One constant offset per component throughout the run, never a per-step
        # redefinition. K annihilates these constants; the mass derivative is zero.
        representatives = np.array([np.flatnonzero(labels == c)[0] for c in range(count)])
        offsets = initial[representatives][labels]
        with np.errstate(over="ignore", invalid="ignore"):
            initial_increment = initial-offsets
        _finite(initial_increment)

        nt, n, cells = len(times), len(p), len(t)
        temperature = np.empty((nt, n))
        flux = np.empty((nt, cells, 2))
        loads = np.empty((nt, n))
        reactions = np.empty((nt-1, n))
        residuals = np.empty((nt-1, n))
        storage = np.empty((nt-1, n))
        content = np.empty(nt)
        quadratic = np.empty(nt)
        boundary_values = np.empty((nt, len(fixed)))
    except Exception as exc:
        raise TransientHeatStepError(0, times[0]) from exc

    def sample(index):
        """Dirichlet values and load at ``times[index]``, live if an input is."""
        now = float(times[index])
        values = [_value(conditions[int(node)](now), "Dirichlet callback")
                  if callable(conditions[int(node)]) else conditions[int(node)]
                  for node in fixed]
        if any(is_live(v) for v in values):
            xp = live_namespace(*values)
            bc = xp.stack([lift(xp, v, xp.float64) for v in values])
        else:
            bc = np.array(values, dtype=float)
        load = source_load(
            private_mesh, p, t, area,
            (lambda points: real_value(source(points.copy(), now), "heat_source callback"))
            if callable(source) else source, live=True)
        _finite(to_numpy(bc), to_numpy(load))
        return bc, load

    def centered(values):
        # Operator evaluation only: state and mass derivative retain their fixed
        # initial baseline. K and grad annihilate each component's constant.
        return values-values[representatives][labels]

    def record(index, increment, load, bc):
        absolute = increment+offsets
        # Preserve the caller's exact initial field, with no implicit projection.
        if index == 0:
            absolute = initial.copy()
        mtemp = mass@absolute
        temperature[index] = absolute
        flux[index] = -(k[:, None] if np.ndim(k) else k)*element_gradient(
            private_mesh, centered(increment))
        loads[index] = load
        boundary_values[index] = bc
        content[index] = np.sum(mtemp)
        quadratic[index] = .5*float(absolute@mtemp)
        _finite(temperature[index], flux[index], loads[index],
                content[index], quadratic[index])

    def advance(previous, bc, load, step):
        """One backward-Euler step on NumPy numbers, refined and checked."""
        # Full old M*T includes the old fixed-node contribution. Subtracting
        # full A_FC*d_new includes the new one; neither M_FC term is dropped.
        system = mass/step+stiffness
        rhs = load+(mass@previous)/step
        current = np.empty(n)
        current[fixed] = bc-offsets[fixed]
        _finite(system.data, rhs, current[fixed])
        if len(free):
            reduced_rhs = rhs[free]-system[free][:, fixed]@current[fixed]
            _finite(reduced_rhs)
            factor = splu(system[free][:, free].tocsc())
            current[free] = factor.solve(reduced_rhs)
            # Refine the same full BE equation with fixed boundary
            # correction zero. Do not stop on the wide original K|u| scale.
            # Retain the best physical residual of six fixed evaluations;
            # no exact-scenario substitution or mean overwrite is used.
            best = current.copy()
            best_score = np.inf
            for refinement in range(6):
                trial_rate = (current-previous)/step
                trial_storage = mass@trial_rate
                trial_spatial = stiffness@centered(current)
                trial_residual = trial_storage+trial_spatial-load
                _finite(trial_rate, trial_storage, trial_spatial, trial_residual)
                physical_terms = (abs(mass)@abs(trial_rate)
                                  +abs(stiffness)@abs(centered(current))+abs(load))
                _finite(physical_terms)
                physical_scale = max(float(np.max(physical_terms)), np.finfo(float).tiny)
                score = float(np.max(abs(trial_residual[free])))/physical_scale
                for component in range(count):
                    selected = labels == component
                    trial_reaction = np.zeros(n)
                    trial_reaction[fixed] = trial_residual[fixed]
                    balance = float(np.sum((trial_storage-load-trial_reaction)[selected]))
                    balance_scale = max(float(np.sum(
                        (abs(trial_storage)+abs(load)+abs(trial_reaction))[selected])),
                        np.finfo(float).tiny)
                    _finite(balance, balance_scale)
                    score = max(score, abs(balance)/balance_scale)
                _finite(score)
                if score < best_score:
                    best_score = score
                    best = current.copy()
                if refinement != 5:
                    correction = factor.solve(-trial_residual[free])
                    _finite(correction)
                    current[free] += correction
                    _finite(current)
            current = best
        rate = (current-previous)/step
        stored = mass@rate
        spatial = stiffness@centered(current)
        residual = stored+spatial-load
        reaction = np.zeros(n)
        reaction[fixed] = residual[fixed]
        _finite(current, rate, stored, spatial, residual, reaction)
        terms = abs(mass)@abs(rate)+abs(stiffness)@abs(current)+abs(load)
        _finite(terms)
        scale = max(float(np.max(terms)), np.finfo(float).tiny)
        if len(free) and np.max(np.abs(residual[free])) > 1e-10*scale:
            raise ValueError("transient solve failed normalized free residual tolerance")
        for component in range(count):
            selected = labels == component
            balance = np.sum((stored-load-reaction)[selected])
            balance_scale = max(float(np.sum(
                (abs(stored)+abs(load)+abs(reaction))[selected])),
                np.finfo(float).tiny)
            _finite(balance, balance_scale)
            if abs(balance) > 1e-10*balance_scale:
                raise ValueError("transient solve failed component heat balance tolerance")
        return current, stored, residual, reaction

    try:
        bc, load = sample(0)
        live = any(is_live(a) for a in (k_live, capacity_live, initial_live, bc, load))
        if not live:
            bc, load = to_numpy(bc), to_numpy(load)
        bound = 32*np.finfo(float).eps*np.maximum(
            1., np.maximum(np.abs(initial[fixed]), np.abs(to_numpy(bc))))
        if np.any(np.abs(initial[fixed]-to_numpy(bc)) > bound):
            raise ValueError("initial Dirichlet data mismatch (32 eps bound); no projection")
        previous = initial_increment.copy()
        record(0, previous, to_numpy(load), to_numpy(bc))
    except Exception as exc:
        raise TransientHeatStepError(0, times[0]) from exc
    if live:
        history = _live_history(
            live_namespace(k_live, capacity_live, initial_live, bc, load), private_mesh,
            k_live, capacity_live, initial_live, bc, load, times, steps, fixed, labels,
            representatives, sample, advance, record, previous, checkpoint_every)
        try:
            return TransientHeatResult(times, *history[:8], fixed, history[8], p, t,
                                       record_k, record_c)
        except Exception as exc:
            raise TransientHeatStepError(nt-1, times[-1]) from exc

    for index, step in enumerate(steps, start=1):
        try:
            bc, load = sample(index)
            if is_live(bc) or is_live(load):
                raise TypeError("a callback returned a JAX or PyTorch value after NumPy values "
                                "at time index 0; return one array library throughout")
            current, stored, residual, reaction = advance(previous, bc, load, step)
            record(index, current, load, bc)
            storage[index-1] = stored
            residuals[index-1] = residual
            reactions[index-1] = reaction
            previous = current.copy()
        except Exception as exc:
            raise TransientHeatStepError(index, times[index]) from exc

    try:
        return TransientHeatResult(
            times, temperature, flux, loads, reactions, residuals, storage,
            content, quadratic, fixed, boundary_values, p, t, record_k, record_c)
    except Exception as exc:
        raise TransientHeatStepError(nt-1, times[-1]) from exc
