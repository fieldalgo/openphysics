# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Backward Euler heat conduction with consistent P1 tetrahedral capacity."""
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType

import numpy as np
from scipy.sparse.linalg import splu

from ._heat_kernels import source_load_3d as _source_load_3d
from ._public import ResultSurface, refuse_text
from .assembly3d import assemble_mass_3d as _assemble_mass_3d
from .assembly3d import assemble_stiffness_3d as _assemble_stiffness_3d
from .core.checks import real_array
from .mesh3d import Mesh3D
from .thermal3d import _boundary_system, _natural_faces, _per_region, _prescribed_nodes, _source

__all__ = ["TransientHeat3DResult", "solve_transient_heat_3d"]

_RATES = ("generated_heat_rate", "outward_prescribed_heat_rate", "outward_convective_heat_rate",
          "reaction_heat_rate", "heat_storage_rate", "residual_heat_rate")


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
                              **dict.fromkeys(_RATES, "W")})


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
    return _solve_transient_heat_3d(
        mesh, thermal_conductivity=thermal_conductivity, volumetric_heat_capacity=volumetric_heat_capacity,
        time=time, initial_temperature=initial_temperature, prescribed_temperature=prescribed_temperature,
        heat_source_density=heat_source_density, inward_heat_flux=inward_heat_flux, convection=convection,
    )


def _solve_transient_heat_3d(mesh, *, thermal_conductivity, volumetric_heat_capacity, time,
                             initial_temperature, prescribed_temperature, heat_source_density,
                             inward_heat_flux, convection, coupled_step=None):
    for name, value in (("thermal_conductivity", thermal_conductivity),
                        ("volumetric_heat_capacity", volumetric_heat_capacity), ("time", time),
                        ("initial_temperature", initial_temperature),
                        ("prescribed_temperature", prescribed_temperature),
                        ("heat_source_density", heat_source_density),
                        ("inward_heat_flux", inward_heat_flux), ("convection", convection)):
        refuse_text(name, value)
    if not isinstance(mesh, Mesh3D):
        raise TypeError("solve_transient_heat_3d takes a galerkin.Mesh3D")
    mesh.check()
    if not mesh.num_tets or np.unique(mesh.tets).size != mesh.num_nodes:
        raise ValueError("mesh must contain tetrahedra and every node must belong to a tetrahedron")
    volumes = mesh.volumes()
    if not np.all(np.isfinite(volumes) & (volumes > 0)):
        raise ValueError("mesh tetrahedra must have finite positive volumes")

    times = real_array(time, "time")
    if times.ndim != 1 or times.size < 2:
        raise ValueError("time must contain at least two sample times in seconds")
    with np.errstate(over="ignore"):
        steps = np.diff(times)
    if not np.all(np.isfinite(steps) & (steps > 0)):
        raise ValueError("time intervals must be finite and strictly positive")
    initial = real_array(initial_temperature, "initial_temperature")
    if initial.shape != (mesh.num_nodes,):
        raise ValueError("initial_temperature must have shape (N,)")
    exterior = mesh.boundary_faces()
    prescribed = _prescribed_nodes(mesh, exterior, {} if prescribed_temperature is None else prescribed_temperature)
    fixed = np.array(list(prescribed), dtype=int)
    if not np.array_equal(initial[fixed], list(prescribed.values())):
        raise ValueError("initial_temperature must match prescribed_temperature at fixed nodes")
    free = np.setdiff1d(np.arange(mesh.num_nodes), fixed)
    k = _per_region(mesh, thermal_conductivity, "thermal_conductivity", positive=True)
    capacity = _per_region(mesh, volumetric_heat_capacity, "volumetric_heat_capacity", positive=True)

    # One reference keeps a common absolute temperature out of the system.
    reference = initial[0]
    samples = _natural_faces(mesh, exterior, prescribed, inward_heat_flux, convection)
    robin, outward, ambient = _boundary_system(samples, np.zeros(mesh.num_nodes, dtype=int), np.array([reference]))
    stiffness = _assemble_stiffness_3d(mesh, k) + robin
    mass = _assemble_mass_3d(mesh, capacity)
    if not all(np.all(np.isfinite(a)) for a in (stiffness.data, mass.data, outward, ambient)):
        raise ValueError("assembled heat system exceeds floating-point range")
    return _integrate(mesh, times, steps, initial, reference, free, fixed, mass, stiffness,
                      robin, outward, ambient, 0.0 if heat_source_density is None else heat_source_density,
                      coupled_step)


def _source_load(mesh, value):
    if callable(value):
        raise TypeError("heat_source_density(t) must return a scalar, region map or element array")
    refuse_text("heat_source_density", value)
    return _source_load_3d(mesh, _source(mesh, value))


def _integrate(mesh, times, steps, initial, reference, free, fixed, mass, stiffness,
               robin, outward, ambient, source, coupled_step):
    @lru_cache(maxsize=8)
    def factor(dt):
        matrix = (mass_free / dt + stiffness_free).tocsc()
        if not np.all(np.isfinite(matrix.data)):
            raise ValueError("time interval produces a nonfinite heat matrix")
        try:
            return splu(matrix)
        except RuntimeError as exc:
            raise ValueError("singular transient heat system") from exc

    mass_free, stiffness_free = mass[free][:, free], stiffness[free][:, free]
    absolute_mass, absolute_stiffness = abs(mass), abs(stiffness)
    dynamic = callable(source)
    load = None if dynamic or coupled_step is not None else _source_load(mesh, source)
    temperature = np.empty((len(times), mesh.num_nodes))
    temperature[0] = initial
    stored = np.empty(len(times))
    stored[0] = (mass @ initial).sum()
    if not np.isfinite(stored[0]):
        raise ValueError("initial stored heat exceeds floating-point range")
    histories = {name: np.empty((len(steps), mesh.num_nodes)) for name in _RATES}
    shifted = initial - reference
    for i, dt in enumerate(steps):
        midpoint = float(times[i] + dt / 2)
        conducted = stiffness @ shifted

        def solve_increment(load):
            rhs = load - outward + ambient - conducted
            if not np.all(np.isfinite(rhs)):
                raise ValueError(f"nonfinite heat load on interval {i}")
            delta = np.zeros(mesh.num_nodes)
            if free.size:
                delta[free] = factor(float(dt)).solve(rhs[free])
            return delta, rhs

        if coupled_step is None:
            if dynamic:
                load = _source_load(mesh, source(midpoint))
            delta, rhs = solve_increment(load)
        else:
            def trial(density):
                trial_load = _source_load(mesh, density)
                trial_delta, trial_rhs = solve_increment(trial_load)
                next_temperature = shifted + trial_delta + reference
                next_temperature[fixed] = initial[fixed]
                return next_temperature, (trial_load, trial_delta, trial_rhs)

            load, delta, rhs = coupled_step(i, midpoint, temperature[i], trial)
        storage = (mass @ delta) / dt
        residual = storage + stiffness @ delta - rhs
        shifted += delta
        temperature[i + 1] = shifted + reference
        temperature[i + 1, fixed] = initial[fixed]
        stored[i + 1] = stored[i] + dt * storage.sum()
        convective = robin @ shifted - ambient
        if not all(np.all(np.isfinite(a)) for a in (temperature[i + 1], stored[i + 1], residual, convective)):
            raise ValueError(f"nonfinite transient heat solution on interval {i}")
        scale = np.max(absolute_mass @ np.abs(delta) / dt
                       + absolute_stiffness @ np.abs(delta) + np.abs(rhs))
        if not np.isfinite(scale) or np.max(np.abs(residual[free]), initial=0.) > 1e-10 * scale:
            raise ValueError(f"transient heat solve failed the free residual tolerance on interval {i}")
        reaction = np.zeros(mesh.num_nodes)
        reaction[fixed] = residual[fixed]
        for name, values in zip(_RATES, (load, outward, convective, reaction, storage, residual)):
            histories[name][i] = values
    # All arrays are owned by this solve, including the validated time array.
    for values in (times, temperature, stored, *histories.values()):
        values.setflags(write=False)
    return TransientHeat3DResult(times, temperature, stored, **histories)
