# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Shared tetrahedral thermal loads, boundary assembly and implicit time integration."""
from collections.abc import Mapping
from functools import lru_cache

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu

from ._heat_kernels import source_load_3d as _source_load_3d
from ._public import refuse_text
from ._tetra_materials import refuse_live_3d, region_property
from .assembly3d import assemble_mass_3d as _assemble_mass_3d
from .assembly3d import assemble_stiffness_3d as _assemble_stiffness_3d
from .core.checks import finite_scalar, real_array
from .mesh3d import Mesh3D


RATE_FIELDS = (
    "generated_heat_rate", "outward_prescribed_heat_rate", "outward_convective_heat_rate",
    "reaction_heat_rate", "heat_storage_rate", "residual_heat_rate",
)


def element_source(mesh, heat_source):
    """(T,) W/m^3: scalar, region table, element array or centroid callback."""
    if callable(heat_source) and not isinstance(heat_source, Mapping):
        centroids = mesh.nodes[mesh.tets].mean(axis=1)
        centroids.flags.writeable = False
        values = heat_source(centroids)
        refuse_live_3d(values, "heat_source_density")
        values = np.asarray(values, dtype=float)
        if values.shape != (mesh.num_tets,) or not np.all(np.isfinite(values)):
            raise ValueError("heat_source_density callback must return finite (T,) W/m^3 at the centroids")
        return values
    refuse_live_3d(heat_source, "heat_source_density")
    if not isinstance(heat_source, Mapping) and np.ndim(heat_source) != 0:
        values = np.asarray(heat_source)
        if values.dtype.kind in "fiu" and values.shape == (mesh.num_tets,):
            values = values.astype(float)
            if np.all(np.isfinite(values)):
                return values
        raise ValueError("heat_source_density must contain one finite value per tetrahedron")
    return region_property(mesh, heat_source, "heat_source_density", positive=False)


def prescribed_nodes(mesh, exterior_faces, dirichlet):
    if not isinstance(dirichlet, Mapping):
        raise ValueError("prescribed_temperature must map exterior node indices to temperatures in K")
    boundary = set(np.unique(exterior_faces).tolist())
    prescribed = {}
    for node, value in dirichlet.items():
        if isinstance(node, (bool, np.bool_)) or not isinstance(node, (int, np.integer)):
            raise ValueError("Dirichlet node indices must be integers")
        if not 0 <= node < mesh.num_nodes or int(node) not in boundary:
            raise ValueError(f"Dirichlet node {node} must lie on the exterior mesh boundary")
        refuse_live_3d(value, "Dirichlet temperature")
        prescribed[int(node)] = finite_scalar(value, "Dirichlet temperature")
    return prescribed


def natural_faces(mesh, exterior_faces, prescribed, inward_heat_flux, convection):
    """Yield validated triangles, areas and constant data for each natural tag."""
    for name, data in (("inward_heat_flux", inward_heat_flux), ("convection", convection)):
        if data is not None and not isinstance(data, Mapping):
            raise ValueError(f"{name} must map exterior face tags to boundary values")
    if not inward_heat_flux and not convection:
        return
    exterior = {tuple(face) for face in exterior_faces}
    for kind, data in (("inward_heat_flux", inward_heat_flux), ("convection", convection)):
        used = set()
        for tag, value in (data or {}).items():
            label = f"{kind} on {tag!r}"
            if tag not in mesh.tagged_faces or not len(mesh.tagged_faces[tag]):
                raise ValueError(f"{label} needs a nonempty exterior face tag")
            faces = mesh.tagged_faces[tag]
            for face in np.sort(faces, axis=1):
                key = tuple(face)
                if key not in exterior:
                    raise ValueError(f"{label} includes a non-exterior face")
                if key in used:
                    raise ValueError(f"{label} includes a duplicate face")
                if all(node in prescribed for node in key):
                    raise ValueError(f"{label} overlaps a fully prescribed temperature face")
                used.add(key)
            refuse_live_3d(value, label)
            if kind == "inward_heat_flux":
                value = finite_scalar(value, label)
            else:
                if isinstance(value, (str, bytes, Mapping)):
                    raise ValueError(f"{label} must be a (h, ambient_temperature) pair")
                try:
                    h, ambient = value
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{label} must be a (h, ambient_temperature) pair") from exc
                h = finite_scalar(h, f"{label} coefficient")
                if h < 0:
                    raise ValueError(f"{label} coefficient must be >= 0")
                value = h, finite_scalar(ambient, f"{label} ambient temperature")
            points = mesh.nodes[faces]
            area = 0.5 * np.linalg.norm(np.cross(points[:, 1] - points[:, 0],
                                                points[:, 2] - points[:, 0]), axis=1)
            if not np.all(np.isfinite(area) & (area > 0)):
                raise ValueError(f"{label} requires finite, positive face areas")
            yield kind, faces, area, value


def boundary_system(samples, labels, offsets):
    """Exact P1 triangle integrals for constant prescribed flux and convection."""
    n = len(labels)
    outward = np.zeros(n)
    ambient = np.zeros(n)
    robin = sp.csr_matrix((n, n))
    for kind, faces, area, value in samples:
        if kind == "inward_heat_flux":
            np.add.at(outward, faces, (-value * area / 3)[:, None])
            continue
        h, temperature = value
        if h == 0:
            continue
        weighted_area = h * area
        np.add.at(ambient, faces,
                  (weighted_area * (temperature - offsets[labels[faces[:, 0]]]) / 3)[:, None])
        entries = weighted_area[:, None, None] / 12 * (np.ones((3, 3)) + np.eye(3))
        robin += sp.coo_matrix((entries.ravel(), (np.repeat(faces, 3, axis=1).ravel(),
                                                   np.tile(faces, (1, 3)).ravel())), shape=(n, n))
    return robin, outward, ambient


def solve_transient_fields(mesh, *, thermal_conductivity, volumetric_heat_capacity, time,
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
    prescribed = prescribed_nodes(mesh, exterior, {} if prescribed_temperature is None else prescribed_temperature)
    fixed = np.array(list(prescribed), dtype=int)
    if not np.array_equal(initial[fixed], list(prescribed.values())):
        raise ValueError("initial_temperature must match prescribed_temperature at fixed nodes")
    free = np.setdiff1d(np.arange(mesh.num_nodes), fixed)
    k = region_property(mesh, thermal_conductivity, "thermal_conductivity", positive=True)
    capacity = region_property(mesh, volumetric_heat_capacity, "volumetric_heat_capacity", positive=True)

    # One reference keeps a common absolute temperature out of the system.
    reference = initial[0]
    samples = natural_faces(mesh, exterior, prescribed, inward_heat_flux, convection)
    robin, outward, ambient = boundary_system(samples, np.zeros(mesh.num_nodes, dtype=int), np.array([reference]))
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
    return _source_load_3d(mesh, element_source(mesh, value))


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
    histories = {name: np.empty((len(steps), mesh.num_nodes)) for name in RATE_FIELDS}
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
        for name, values in zip(RATE_FIELDS, (load, outward, convective, reaction, storage, residual)):
            histories[name][i] = values
    # All arrays are owned by this solve, including the validated time array.
    for values in (times, temperature, stored, *histories.values()):
        values.setflags(write=False)
    return dict(time=times, temperature=temperature, stored_heat=stored, **histories)
