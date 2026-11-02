# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Consistent-mass backward-Euler heat histories on a fixed SI P1 mesh.

Explicit submodule only. See docs/packages/galerkin/transient_heat.md; conductivity, heat
capacity and a constant source may be piecewise constant on named mesh regions
(docs/packages/galerkin/multimaterial.md). Finite Kelvin values are
mathematical inputs, not a physical material-domain or positivity certificate.

Exterior edges may carry a prescribed outward flux g and convection h*(T-T_amb)
with the steady solver's input forms and signs (docs/packages/galerkin/thermal_flux_robin.md).
Each value may also depend on time, as callback(time_s) or callback(points_m,
outward_normals, time_s); time-dependent data are sampled at the end of every
backward-Euler step, like Dirichlet and source callbacks. H is assembled once
unless h itself varies in time.

Material, source, Dirichlet, boundary and initial values may be JAX or PyTorch
values (callbacks may return them); the histories are then arrays of that
library and carry reverse-mode derivatives through every step (all steps are
kept). NumPy inputs compute exactly as before.
"""
from dataclasses import dataclass, fields
import importlib
import inspect
import sys
from typing import Mapping

import numpy as np
from scipy.sparse import issparse
from scipy.sparse.linalg import splu

from .mesh import Mesh
from .materials import is_per_region, region_index, region_property
from .core import forms, kernels
from .core import solve as core_solve
from .core.backend import Backend, backend_of, is_live, lift, live_namespace, scatter_add, to_numpy
from .core.boundary import evaluate_scalar_boundary, scalar_boundary_geometry
from .core.checks import real_array, real_value
from .core.loads import source_load
from .core.sparse import CooMatrix
from .core.triangles import triangle_geometry
from .assembly import assemble_mass, assemble_stiffness
from .postprocess import element_gradient
from .thermal import scalar_boundary_system


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


_BOUNDARY_FORMS = ("callback(time_s) -> scalar", "callback(points_m, outward_normals) -> (Q,)",
                   "callback(points_m, outward_normals, time_s) -> (Q,)")
_TIMED = ("time", "field")


def _boundary_forms(data, name):
    """Classify every value of a boundary mapping: {tag: tuple of forms}.

    A value is "constant" (not callable), "static" (callback(points_m,
    outward_normals), sampled once, as in steady heat), "time" (callback(time_s)
    -> scalar) or "field" (callback(points_m, outward_normals, time_s) -> (Q,)),
    told apart by the number of required positional parameters. A callback with
    another count, a variadic positional parameter, two parameters one of which
    is named time_s/time, or no introspectable signature is refused here, before
    any sampling.
    """
    if data is None:
        return {}
    if not isinstance(data, Mapping):
        raise ValueError(f"{name} must map boundary edge tags to conditions")
    forms = {}
    for tag, condition in data.items():
        values = condition if isinstance(condition, (tuple, list)) else (condition,)
        kinds = []
        for value in values:
            if not callable(value):
                kinds.append("constant")
                continue
            try:
                parameters = list(inspect.signature(value).parameters.values())
            except (TypeError, ValueError):
                raise ValueError(
                    f"{name}[{tag!r}] callback has no introspectable signature; accepted forms: "
                    + ", ".join(_BOUNDARY_FORMS)) from None
            required = [p for p in parameters
                        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                        and p.default is p.empty]
            variadic = any(p.kind is p.VAR_POSITIONAL for p in parameters)
            misnamed = len(required) == 2 and any(p.name in ("time_s", "time") for p in required)
            if variadic or misnamed or len(required) not in (1, 2, 3):
                raise ValueError(
                    f"{name}[{tag!r}] callback must take exactly one of the forms "
                    + ", ".join(_BOUNDARY_FORMS)
                    + " (required positional parameters decide; a two-parameter callback "
                    "receives points and normals, never time)")
            kinds.append({1: "time", 2: "static", 3: "field"}[len(required)])
        forms[tag] = tuple(kinds)
    return forms


def _bound(data, forms, name, now):
    """``data`` with its time-dependent values evaluated (scalars) or bound (fields) at ``now``."""
    out = {}
    for tag, condition in data.items():
        sequence = isinstance(condition, (tuple, list))
        values = condition if sequence else (condition,)
        bound = []
        for value, kind in zip(values, forms[tag]):
            if kind == "time":
                bound.append(_value(value(now), f"{name}[{tag!r}] callback(time_s) value"))
            elif kind == "field":
                bound.append(lambda points, normals, value=value: value(points, normals, now))
            else:
                bound.append(value)
        out[tag] = tuple(bound) if sequence else bound[0]
    return out


def _coo(xp, matrix):
    """A CooMatrix with values in ``xp`` from a CooMatrix or a SciPy matrix."""
    if issparse(matrix):
        matrix = matrix.tocoo()
        return CooMatrix(matrix.row, matrix.col, lift(xp, matrix.data), matrix.shape)
    matrix = matrix.coalesce()
    return CooMatrix(matrix.rows, matrix.cols, lift(xp, matrix.values), matrix.shape)


def _scipy(matrix):
    """SciPy CSR numbers of a CooMatrix or SciPy matrix."""
    if issparse(matrix):
        return matrix.tocsr()
    return CooMatrix(matrix.rows, matrix.cols, to_numpy(matrix.values), matrix.shape).to_scipy()


@dataclass(frozen=True, eq=False)
class TransientHeatResult:
    """Full copied read-only histories, O(Nt*(N+M)) memory, no downsampling.

    Node temperatures: K; element flux: W/m^2. All nodal rates: W/m depth.
    H is J/m, whereas quadratic V is J K/m and is NOT stored heat.
    Rates/reactions have no entry at t0. nodes_m/triangles capture the mesh.
    conductivity_w_mk and volumetric_heat_capacity_j_m3k are floats, or
    {region name: float} copies for per-region materials.
    prescribed_outward_load_w_per_m (G_n) and convective_outward_w_per_m
    (C_n = H_n*T_n-B_n) are (Nt-1,N) step rates when outward_flux or convection
    was given and None otherwise; then storage_n = f_n+reaction_n-G_n-C_n.
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
    prescribed_outward_load_w_per_m: np.ndarray | None = None
    convective_outward_w_per_m: np.ndarray | None = None

    def __post_init__(self):
        # JAX and PyTorch histories are kept as they are (they carry derivatives).
        integer = {"dirichlet_node_ids", "triangles"}
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, np.ndarray):
                dtype = np.dtype("<i8" if f.name in integer else "<f8")
                object.__setattr__(self, f.name, _owned(value, dtype))


def _live_history(xp, mesh, k, capacity, initial, bc0, load0, times, steps, fixed, labels,
                  representatives, sample, advance, record, previous, checkpoint_every,
                  natural=None):
    """Histories of a run with JAX or PyTorch inputs, in that library.

    Every step first runs on NumPy numbers (``advance``: refined and checked like
    a NumPy run). Its solution x0 then gets the adjoint correction
    x = x0 + A^{-1}(b - A x0): equal to x0 up to rounding, with exact derivatives
    with respect to every live input. That second pass has no checks, so it can
    be recomputed during the backward pass (``checkpoint_every``).
    ``natural`` is None or the Robin matrix H, assembled once (a time-dependent
    h is refused before this runs); ``sample`` then also returns the prescribed
    outward load and shifted ambient load of each step, which may vary in time.
    Returns temperature, flux, load, reaction, residual, storage, content,
    quadratic and Dirichlet histories, then with ``natural`` the prescribed
    outward load and convective outward histories.
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
        if natural is not None:
            robin = _coo(xp, natural)
    except Exception as exc:
        raise TransientHeatStepError(0, times[0]) from exc

    def centered(values):
        return values-values[representatives][labels]

    def recorded(increment, load, bc, first=False):
        absolute = initial if first else increment+offsets
        mtemp = mass.matvec(absolute)
        flux = -(k[:, None] if k.ndim else k)*element_gradient(mesh, centered(increment))
        return absolute, flux, load, bc, xp.sum(mtemp), .5*(absolute@mtemp)

    def step_live(previous, step, bc, load, x0, outward_load=None, shifted_ambient=None):
        system = CooMatrix(mass.rows, mass.cols, mass.values/step+stiffness.values, (n, n))
        rhs = load+mass.matvec(previous)/step
        if natural is not None:
            system = system+robin
            rhs = rhs+shifted_ambient-outward_load
        x0 = lift(xp, x0)
        delta = core_solve.solve_dirichlet(
            system, rhs-system.matvec(x0),
            {tuple(fixed): bc-offsets[fixed]-x0[fixed]} if len(fixed) else {})
        current = x0+delta
        stored = mass.matvec((current-previous)/step)
        residual = stored+stiffness.matvec(centered(current))-load
        if natural is None:
            return current, (*recorded(current, load, bc), stored, residual,
                             scatter_add(xp, n, fixed, residual[fixed]))
        # H does not annihilate the component offset: C = H*u-shifted_B = H*T-B.
        convective = robin.matvec(current)-shifted_ambient
        residual = residual+convective+outward_load
        return current, (*recorded(current, load, bc), stored, residual,
                         scatter_add(xp, n, fixed, residual[fixed]), outward_load, convective)

    def block(previous, sizes, bcs, loads, x0s, *naturals):
        columns = []
        for step, bc, load, x0, *extra in zip(sizes, bcs, loads, x0s, *naturals):
            previous, out = step_live(previous, step, bc, load, x0, *extra)
            columns.append(out)
        return previous, tuple(xp.stack(column) for column in zip(*columns))

    # Pass 1: NumPy numbers, checks and step errors exactly as for NumPy inputs.
    data = []
    for index, step in enumerate(steps, start=1):
        try:
            bc, load, boundary = sample(index)
            bc_n, load_n = to_numpy(bc), to_numpy(load)
            boundary_n = None if boundary is None else (
                boundary[0], to_numpy(boundary[1]), to_numpy(boundary[2]))
            current = advance(previous, bc_n, load_n, step, boundary_n)[0]
            record(index, current, load_n, bc_n)
            previous = current.copy()
            entry = (float(step), lift(xp, bc, xp.float64), lift(xp, load), current)
            if natural is not None:
                entry += (lift(xp, boundary[1]), lift(xp, boundary[2]))
            data.append(entry)
        except Exception as exc:
            raise TransientHeatStepError(index, times[index]) from exc

    # Pass 2: derivatives, in blocks of checkpoint_every steps (one block by default).
    try:
        first = recorded(initial-offsets, lift(xp, load0), lift(xp, bc0, xp.float64), first=True)
        state, blocks = initial-offsets, []
        size = checkpoint_every or max(len(data), 1)
        for start in range(0, len(data), size):
            sizes, bcs, loads, x0s, *naturals = zip(*data[start:start+size])
            run = _checkpointed(xp, block, sizes) if checkpoint_every else (
                lambda prev, b, l, x, *nat, sizes=sizes: block(prev, sizes, b, l, x, *nat))
            state, columns = run(state, list(bcs), list(loads), list(x0s),
                                 *(list(column) for column in naturals))
            blocks.append(columns)
        nodal = [xp.concat([xp.stack([first[j]]), *(b[j] for b in blocks)]) for j in range(6)]
        stepped = [xp.concat([b[j] for b in blocks]) for j in range(6, 9 if natural is None else 11)]
    except Exception as exc:
        raise TransientHeatStepError(len(times)-1, times[-1]) from exc
    temperature, flux, loads, bcs, content, quadratic = nodal
    storage, residual, reaction = stepped[:3]
    return (temperature, flux, loads, reaction, residual, storage, content, quadratic, bcs,
            *stepped[3:])


def _checkpointed(xp, block, sizes):
    """``block`` for these step sizes, recomputed in the backward pass instead of stored."""
    def run(previous, bcs, loads, x0s, *naturals):
        return block(previous, sizes, bcs, loads, x0s, *naturals)
    if backend_of(xp) is Backend.JAX:
        return sys.modules["jax"].checkpoint(run)
    checkpoint = importlib.import_module("torch.utils.checkpoint").checkpoint   # torch is loaded
    return lambda *args: checkpoint(run, *args, use_reentrant=False)


def solve_transient_heat(mesh, *, conductivity, volumetric_heat_capacity,
                         time_s, initial_temperature_k, dirichlet,
                         heat_source=0.0, outward_flux=None, convection=None,
                         checkpoint_every=None):
    """Solve c*dT/dt-div(k*grad T)=Q, BE with consistent mass, SI units.

    k>0 W/(m K), c>0 J/(m^3 K), explicit increasing nonnegative seconds,
    finite initial (N,) K. Finite negative K and signed sources are allowed;
    no clamping, maximum principle or physical temperature validity is implied.
    dirichlet: fixed exterior integer node -> scalar K or callback(time_s).
    Q: scalar W/m^3 or callback(points_m,time_s)->exactly(Q,) W/m^3.
    outward_flux maps mesh.boundary_edges tags to g (W/m^2), convection maps
    tags to (h, ambient) with h>=0 (W/(m^2 K), K): q.n = g+h*(T-ambient) as in
    galerkin.thermal.solve_steady_heat. Each of g, h and ambient is a scalar, a
    callback(points_m, outward_normals)->exactly (Q,) sampled once, a
    callback(time_s)->scalar or a callback(points_m, outward_normals, time_s)
    ->exactly (Q,); the last two are sampled at time_s[0] for validation and
    then at the END of every step (t_{n+1}, like Dirichlet and source
    callbacks). The form is decided by the number of required positional
    parameters; other signatures are refused before sampling. H is assembled
    once unless h varies in time; G and B are re-evaluated whenever any
    boundary value varies. Other edges are insulated; no anchor is required on
    a transient component. A time-dependent h is refused with JAX or PyTorch
    inputs (time-dependent g and ambient are supported there).
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
    # Boundary edge selections are copied as given, so natural-condition
    # sampling validates the caller's actual arrays, as steady heat does.
    private_mesh.boundary_edges = {tag: np.array(edges) for tag, edges in mesh.boundary_edges.items()}
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
    flux_forms = _boundary_forms(outward_flux, "outward_flux")
    convection_forms = _boundary_forms(convection, "convection")
    natural = outward_flux is not None or convection is not None
    # Static data are sampled once, exactly as before; H is reassembled per step
    # only when h itself varies in time, G and B whenever any value does.
    timed_h = any(kinds[:1] and kinds[0] in _TIMED for kinds in convection_forms.values())
    timed = timed_h or any(kind in _TIMED for forms_ in (flux_forms, convection_forms)
                           for kinds in forms_.values() for kind in kinds)
    # NumPy numbers of every live input drive the step and its checks; live values
    # only add derivatives (see _live_history).
    k_live, capacity_live, initial_live = k, capacity, initial
    k, capacity, initial = (_numbers(a) if is_live(a) else a for a in (k, capacity, initial))
    # One constant offset per component throughout the run, never a per-step
    # redefinition. K annihilates these constants; the mass derivative is zero.
    representatives = np.array([np.flatnonzero(labels == c)[0] for c in range(count)])
    natural_live = None

    def natural_system(now):
        """(H, G, shifted_B) of the boundary data sampled at ``now``, live if an input is.

        H does not annihilate the component offsets, so the ambient load is
        shifted by them as in steady heat: shifted_B integrates h*(ambient-offset
        of the component). The offsets are the initial temperatures throughout.
        """
        flux_now = None if outward_flux is None else _bound(outward_flux, flux_forms, "outward_flux", now)
        convection_now = (None if convection is None
                          else _bound(convection, convection_forms, "convection", now))
        samples = evaluate_scalar_boundary(geometry, flux_now, convection_now, live=True)
        anchors = [initial_live[r] for r in representatives]
        robin, outward, _, shifted = scalar_boundary_system(samples, len(p), labels, anchors,
                                                            np.ones(count, dtype=bool))
        return robin, outward, shifted

    try:
        mass = assemble_mass(private_mesh, capacity)
        stiffness = assemble_stiffness(private_mesh, k)
        _finite(mass.data, stiffness.data)
        if np.any(mass.diagonal() <= 0):
            raise ValueError("consistent mass lost positive diagonal at this numeric scale")
        offsets = initial[representatives][labels]
        with np.errstate(over="ignore", invalid="ignore"):
            initial_increment = initial-offsets
        _finite(initial_increment)
        if natural:
            # Edges are validated once; values are sampled here at times[0] and,
            # when they depend on time, again at the end of every step.
            geometry = scalar_boundary_geometry(private_mesh, p, t, conditions, outward_flux,
                                                convection)
            natural_live = natural_system(float(times[0]))
            robin_matrix = _scipy(natural_live[0])
            outward_load, shifted_ambient = (to_numpy(a) for a in natural_live[1:])
            _finite(robin_matrix.data, outward_load, shifted_ambient)
            boundary0 = (robin_matrix, outward_load, shifted_ambient)

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
        convective_history = np.empty((nt-1, n)) if natural else None
        prescribed_history = np.empty((nt-1, n)) if natural else None
    except Exception as exc:
        raise TransientHeatStepError(0, times[0]) from exc

    def boundary_at(index):
        """(H as NumPy CSR, G, shifted_B) for the step ending at ``times[index]``.

        Static data return the arrays sampled at times[0]; time-dependent data
        are sampled at times[index]. H is reassembled only when h varies. The
        loads are live if an input is.
        """
        if not natural:
            return None
        if not timed or index == 0:
            return boundary0
        robin, outward, shifted = natural_system(float(times[index]))
        robin = _scipy(robin) if timed_h else boundary0[0]
        _finite(robin.data, to_numpy(outward), to_numpy(shifted))
        return robin, outward, shifted

    def sample(index):
        """Dirichlet values, load and boundary data at ``times[index]``, live if an input is."""
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
        return bc, load, boundary_at(index)

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

    def natural_outward(current, boundary):
        """(convective outward C=H*u-shifted_B, total natural outward C+G) of an increment u."""
        robin_matrix, outward_load, shifted_ambient = boundary
        convective = robin_matrix@current-shifted_ambient
        return convective, convective+outward_load

    def advance(previous, bc, load, step, boundary=None):
        """One backward-Euler step on NumPy numbers, refined and checked.

        ``boundary`` is None or this step's NumPy (H, G, shifted_B). Returns
        (increment, storage, residual, reaction, convective outward or None).
        """
        # Full old M*T includes the old fixed-node contribution. Subtracting
        # full A_FC*d_new includes the new one; neither M_FC term is dropped.
        # Without natural data the system and loads are exactly the Dirichlet-only ones.
        system = mass/step+stiffness
        forcing = load
        if natural:
            robin_matrix, outward_load, shifted_ambient = boundary
            system = system+robin_matrix
            forcing = load+shifted_ambient-outward_load
        rhs = forcing+(mass@previous)/step
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
                physical_terms = (abs(mass)@abs(trial_rate)
                                  +abs(stiffness)@abs(centered(current))+abs(load))
                if natural:
                    trial_convective, trial_outward = natural_outward(current, boundary)
                    trial_residual = trial_residual+trial_outward
                    physical_terms = (physical_terms+abs(robin_matrix)@abs(current)
                                      +abs(shifted_ambient)+abs(outward_load))
                _finite(trial_rate, trial_storage, trial_spatial, trial_residual)
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
                    if natural:
                        balance += float(np.sum(trial_outward[selected]))
                        balance_scale += float(np.sum(
                            (abs(trial_convective)+abs(outward_load))[selected]))
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
        terms = abs(mass)@abs(rate)+abs(stiffness)@abs(current)+abs(load)
        convective = None
        if natural:
            convective, outward = natural_outward(current, boundary)
            residual = residual+outward
            terms = terms+abs(robin_matrix)@abs(current)+abs(shifted_ambient)+abs(outward_load)
        reaction = np.zeros(n)
        reaction[fixed] = residual[fixed]
        _finite(current, rate, stored, spatial, residual, reaction)
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
            if natural:
                balance += np.sum(outward[selected])
                balance_scale += float(np.sum((abs(convective)+abs(outward_load))[selected]))
            _finite(balance, balance_scale)
            if abs(balance) > 1e-10*balance_scale:
                raise ValueError("transient solve failed component heat balance tolerance")
        return current, stored, residual, reaction, convective

    try:
        bc, load, _ = sample(0)
        live = any(is_live(a) for a in (k_live, capacity_live, initial_live, bc, load,
                                        *(natural_live[1:] if natural else ())))
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
        if timed_h:
            raise ValueError(
                "time-dependent convection h (callback(time_s) or callback(points_m, "
                "outward_normals, time_s)) is not supported with JAX or PyTorch inputs: H would "
                "have to be reassembled inside the differentiated steps; use NumPy inputs, or "
                "keep h static and vary the ambient temperature and outward flux in time")
        history = _live_history(
            live_namespace(k_live, capacity_live, initial_live, bc, load,
                           *(natural_live[1:] if natural else ())), private_mesh,
            k_live, capacity_live, initial_live, bc, load, times, steps, fixed, labels,
            representatives, sample, advance, record, previous, checkpoint_every,
            natural_live[0] if natural else None)
        try:
            return TransientHeatResult(times, *history[:8], fixed, history[8], p, t,
                                       record_k, record_c, *history[9:])
        except Exception as exc:
            raise TransientHeatStepError(nt-1, times[-1]) from exc

    for index, step in enumerate(steps, start=1):
        try:
            bc, load, boundary = sample(index)
            if is_live(bc) or is_live(load) or (
                    natural and any(is_live(a) for a in boundary[1:])):
                raise TypeError("a callback returned a JAX or PyTorch value after NumPy values "
                                "at time index 0; return one array library throughout")
            current, stored, residual, reaction, convective = advance(previous, bc, load, step,
                                                                     boundary)
            record(index, current, load, bc)
            storage[index-1] = stored
            residuals[index-1] = residual
            reactions[index-1] = reaction
            if natural:
                convective_history[index-1] = convective
                prescribed_history[index-1] = boundary[1]
            previous = current.copy()
        except Exception as exc:
            raise TransientHeatStepError(index, times[index]) from exc

    try:
        if not natural:
            return TransientHeatResult(
                times, temperature, flux, loads, reactions, residuals, storage,
                content, quadratic, fixed, boundary_values, p, t, record_k, record_c)
        return TransientHeatResult(
            times, temperature, flux, loads, reactions, residuals, storage,
            content, quadratic, fixed, boundary_values, p, t, record_k, record_c,
            prescribed_history, convective_history)
    except Exception as exc:
        raise TransientHeatStepError(nt-1, times[-1]) from exc
