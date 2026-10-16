# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Consistent-mass backward-Euler heat histories on a fixed SI P1 mesh.

Explicit submodule only. See docs/transient_heat.md. Finite Kelvin values are
mathematical inputs, not a physical material-domain or positivity certificate.
"""
from dataclasses import dataclass, fields
from typing import Mapping

import numpy as np
from scipy.sparse.linalg import splu

from .mesh import Mesh
from .thermal import _mesh_geometry, _real as _base_real, _source_load
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


def _real(value, name):
    # Preserve explicit bool rejection before heterogeneous Python sequences can
    # coerce bools to a floating dtype. Already-normalized float arrays carry no
    # recoverable history of how their elements were constructed.
    if (isinstance(value, (bool, np.bool_))
            or (isinstance(value, (list, tuple))
                and any(isinstance(v, (bool, np.bool_)) for v in value))):
        raise ValueError(f"{name} must not contain booleans")
    return _base_real(value, name)


def _scalar(value, name, positive=False):
    a = _real(value, name)
    if a.shape != () or (positive and a <= 0):
        raise ValueError(f"{name} must be a finite {'positive ' if positive else ''}real scalar")
    return float(a)


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
    conductivity_w_mk: float
    volumetric_heat_capacity_j_m3k: float

    def __post_init__(self):
        integer = {"dirichlet_node_ids", "triangles"}
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, np.ndarray):
                dtype = np.dtype("<i8" if f.name in integer else "<f8")
                object.__setattr__(self, f.name, _owned(value, dtype))


def solve_transient_heat(mesh, *, conductivity, volumetric_heat_capacity,
                         time_s, initial_temperature_k, dirichlet,
                         heat_source=0.0):
    """Solve c*dT/dt-div(k*grad T)=Q, BE with consistent mass, SI units.

    k>0 W/(m K), c>0 J/(m^3 K), explicit increasing nonnegative seconds,
    finite initial (N,) K. Finite negative K and signed sources are allowed;
    no clamping, maximum principle or physical temperature validity is implied.
    dirichlet: fixed exterior integer node -> scalar K or callback(time_s).
    Q: scalar W/m^3 or callback(points_m,time_s)->exactly(Q,) W/m^3.
    Other edges are insulated; no anchor is required on a transient component.
    Pure callbacks/no concurrent input mutation. Time-local failures are chained
    with index/time, no partial result; external callback side effects persist.
    """
    k = _scalar(conductivity, "conductivity", True)
    capacity = _scalar(volumetric_heat_capacity, "volumetric_heat_capacity", True)
    times = _real(time_s, "time_s").copy()
    if times.ndim != 1 or len(times) < 2 or np.any(times < 0):
        raise ValueError("time_s must be nonnegative 1D seconds with at least two entries")
    with np.errstate(over="ignore", invalid="ignore"):
        steps = np.diff(times)
    if not np.all(np.isfinite(steps)) or np.any(steps <= 0):
        raise ValueError("time_s differences must be finite and strictly positive")

    p, t, area, exterior, count, labels = _mesh_geometry(mesh)
    p, t = p.copy(), t.copy()
    # Geometry is validated before Mesh can cast indices or repair orientation.
    private_mesh = Mesh(p.copy(), t.copy(), boundary={})
    initial = _real(initial_temperature_k, "initial_temperature_k").copy()
    if initial.shape != (len(p),):
        raise ValueError("initial_temperature_k must have exactly shape (N,)")
    if not isinstance(dirichlet, Mapping):
        raise ValueError("dirichlet must map exterior integer nodes to Kelvin values")
    conditions = {}
    for node, value in dirichlet.items():
        if (isinstance(node, (bool, np.bool_))
                or not isinstance(node, (int, np.integer))
                or not 0 <= node < len(p) or node not in exterior):
            raise ValueError("Dirichlet nodes must be exterior integer node indices")
        conditions[int(node)] = value if callable(value) else _scalar(value, "Dirichlet temperature")
    fixed = np.array(sorted(conditions), dtype=int)
    free = np.setdiff1d(np.arange(len(p)), fixed)
    source = heat_source if callable(heat_source) else _scalar(heat_source, "heat_source")

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
        now = float(times[index])
        bc = np.array([_scalar(conditions[int(node)](now), "Dirichlet callback")
                       if callable(conditions[int(node)]) else conditions[int(node)]
                       for node in fixed], dtype=float)
        load = _source_load(
            private_mesh, p, t, area,
            (lambda points: _real(source(points.copy(), now), "heat_source callback"))
            if callable(source) else source)
        _finite(bc, load)
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
        flux[index] = -k*element_gradient(private_mesh, centered(increment))
        loads[index] = load
        boundary_values[index] = bc
        content[index] = np.sum(mtemp)
        quadratic[index] = .5*float(absolute@mtemp)
        _finite(temperature[index], flux[index], loads[index],
                content[index], quadratic[index])

    try:
        bc, load = sample(0)
        bound = 32*np.finfo(float).eps*np.maximum(
            1., np.maximum(np.abs(initial[fixed]), np.abs(bc)))
        if np.any(np.abs(initial[fixed]-bc) > bound):
            raise ValueError("initial Dirichlet data mismatch (32 eps bound); no projection")
        previous = initial_increment.copy()
        record(0, previous, load, bc)
    except Exception as exc:
        raise TransientHeatStepError(0, times[0]) from exc

    for index, step in enumerate(steps, start=1):
        try:
            bc, load = sample(index)
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
            content, quadratic, fixed, boundary_values, p, t, k, capacity)
    except Exception as exc:
        raise TransientHeatStepError(nt-1, times[-1]) from exc
