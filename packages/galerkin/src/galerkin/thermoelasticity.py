# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Static mechanical stage for an explicitly prescribed nodal-P1 Kelvin field.

This module does not call a heat solver or authenticate temperature provenance.
linear_expansion_coefficient, youngs_modulus and poisson_ratio are scalars or piecewise
constant on named mesh regions (galerkin.materials, docs/packages/galerkin/multimaterial.md).
See docs/packages/galerkin/prescribed_temperature_thermoelasticity.md for units and reductions.
Quantities are keyword-only registry names in SI units (the units convention of the
galerkin step); a str for a quantity raises TypeError.

stress_free_temperature, linear_expansion_coefficient, youngs_modulus, poisson_ratio,
the prescribed displacements, body_force_density and traction may be JAX or PyTorch
values (callbacks may return them); the result arrays are then in that library and
carry reverse-mode derivatives. The temperature snapshot is a NumPy container. One
body serves NumPy and live inputs, solving as galerkin.elasticity does.
"""
from dataclasses import dataclass, field
from types import MappingProxyType

import numpy as np

from .elasticity import PLANES
from .core import live as live_inputs
from .core.backend import Backend, backend_of, lift, live_namespace, namespace, scatter_add, to_numpy
from .core.boundary import traction_load
from .core.checks import one_of, real_array, real_value, require_finite
from .core.triangles import triangle_geometry, vector_strain
from .materials import is_per_region, region_property
from ._mechanics_kernels import (ISOTROPIC_STRAIN, SNAPSHOT_UNITS as _SNAPSHOT_UNITS, at_fixed as _at_fixed,
                                 body_load as _body_load, constitutive as _constitutive,
                                 displacement as _displacement, element_materials as _element_materials,
                                 lame as _lame, physical_energy as _physical_energy,
                                 snapshot_hashes as _snapshot_hashes, stress_of as _stress_of,
                                 thermal_coefficient as _thermal_coefficient, verify_snapshot as _verify_snapshot,
                                 vector_stiffness as _vector_stiffness)
from ._public import ResultSurface, refuse_tagged_text, refuse_text

# Public names. The helpers verify_snapshot, thermal_coefficient and physical_energy are
# internal: they live in the package-private galerkin._mechanics_kernels (L2 commit 8), and
# galerkin.kernels re-exports them.
__all__ = ["ISOTROPIC_STRAIN", "TemperatureSnapshot", "freeze_temperature", "ThermoelasticResult",
           "solve_thermoelasticity"]


def _immutable(array, dtype):
    a = np.asarray(array, dtype=dtype)
    if not np.all(np.isfinite(a)):
        raise ValueError("snapshot normalization exceeds finite numeric range")
    return np.frombuffer(a.tobytes(order="C"), dtype=dtype).reshape(a.shape)


@dataclass(frozen=True, eq=False)
class TemperatureSnapshot:
    """Copied immutable SI geometry/connectivity/temperature, in original order.

    Use freeze_temperature to validate the full Mesh before construction.
    Arrays are backed by immutable bytes, not just a reversible write flag.
    Fingerprints are reproducible checksums; this is not an authenticated heat
    result, cross-mesh mapping, or temperature-unit inference mechanism.
    ``units`` is the read-only map {"nodes": "m", "temperature": "K"}; the checksums
    keep their schema-1 framing, so they are the same as before the galerkin step.
    """
    nodes: np.ndarray = field(repr=False)
    triangles: np.ndarray = field(repr=False)
    temperature: np.ndarray = field(repr=False, kw_only=True)
    mesh_hash: str = field(init=False)
    temperature_hash: str = field(init=False)
    snapshot_hash: str = field(init=False)
    schema_version: int = field(default=1, init=False)
    units: object = field(init=False, repr=False)

    def __post_init__(self):
        refuse_text("temperature", self.temperature)
        p = real_array(self.nodes, "snapshot nodes")
        t = np.asarray(self.triangles)
        temp = real_array(self.temperature, "temperature")
        if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3:
            raise ValueError("snapshot nodes must have shape (N,2), N>=3")
        if (t.ndim != 2 or t.shape[1] != 3 or not len(t) or t.dtype.kind not in "iu"
                or np.any(t < 0) or np.any(t >= len(p))):
            raise ValueError("snapshot triangles must be integer (M,3) valid node indices")
        if temp.shape != (len(p),) or np.any(temp < 0):
            raise ValueError("temperature must be nonnegative absolute Kelvin with shape (N,)")
        p, t, temp = _immutable(p, "<f8"), _immutable(t, "<i8"), _immutable(temp, "<f8")
        for name, value in zip(("nodes", "triangles", "temperature"), (p, t, temp)):
            object.__setattr__(self, name, value)
        for name, value in zip(("mesh_hash", "temperature_hash", "snapshot_hash"), _snapshot_hashes(p, t, temp)):
            object.__setattr__(self, name, value)
        object.__setattr__(self, "units", MappingProxyType(dict(_SNAPSHOT_UNITS)))


def freeze_temperature(mesh, *, temperature):
    """Validate mesh and copy a finite nonnegative (N,) Kelvin P1 nodal ``temperature``."""
    refuse_text("temperature", temperature)
    p, t, *_ = triangle_geometry(mesh, counterclockwise=False)
    return TemperatureSnapshot(p, t, temperature=temperature)


def _thermal_load(area, b, dofs, q_mean, num_nodes):
    """Thermal-equivalent nodal load (2N,) of the element-mean thermal stress q_mean (T,), in its library."""
    xp = namespace(q_mean)
    local = xp.einsum("tji,j,t->ti", lift(xp, b), lift(xp, ISOTROPIC_STRAIN), lift(xp, area)*q_mean)
    return scatter_add(xp, 2*num_nodes, dofs.ravel(), xp.reshape(local, (-1,)))


def _material_record(xp, value):
    """The input as echoed in the result.

    NumPy: a Python float, or a plain {region name: float} copy. With JAX or
    PyTorch values: a {region name: value} copy, or the scalar as a float64
    array of that library.
    """
    numpy = backend_of(xp) is Backend.NUMPY
    if is_per_region(value):
        return {str(k): float(v) if numpy else v for k, v in value.items()}
    return float(real_array(value, "material")) if numpy else lift(xp, real_value(value, "material"), xp.float64)


@dataclass
class ThermoelasticResult(ResultSurface):
    """Mechanical fields for a prescribed temperature snapshot, planar: per metre of depth.

    strain is element constant. thermal_strain, elastic_strain, stress, stress_zz and
    strain_zz are sampled at triangle centroids; stress generally varies linearly
    inside a triangle. Strain order is (exx,eyy,gamma_xy).
    applied_force_per_depth (body + traction), thermal_equivalent_force_per_depth,
    reaction_force_per_depth and residual_force_per_depth are N/m arrays.
    strain_energy_per_depth is the reduced physical 3D elastic energy, J/m.
    linear_expansion_coefficient, youngs_modulus and poisson_ratio echo the input:
    a float, or a {region name: float} copy for per-region materials.
    ``.units`` maps each quantity field to its canonical unit.
    """
    UNITS = MappingProxyType({
        "displacement": "m", "strain": "1", "thermal_strain": "1", "elastic_strain": "1", "stress": "Pa",
        "stress_zz": "Pa", "strain_zz": "1", "applied_force_per_depth": "N/m",
        "thermal_equivalent_force_per_depth": "N/m", "reaction_force_per_depth": "N/m",
        "residual_force_per_depth": "N/m", "strain_energy_per_depth": "J/m", "stress_free_temperature": "K",
        "linear_expansion_coefficient": "1/K", "youngs_modulus": "Pa", "poisson_ratio": "1",
        "applied_body_force_per_depth": "N/m", "applied_traction_force_per_depth": "N/m"})
    BASIS = "planar"

    displacement: np.ndarray
    strain: np.ndarray
    thermal_strain: np.ndarray
    elastic_strain: np.ndarray
    stress: np.ndarray
    stress_zz: np.ndarray
    strain_zz: np.ndarray
    applied_force_per_depth: np.ndarray
    thermal_equivalent_force_per_depth: np.ndarray
    reaction_force_per_depth: np.ndarray
    residual_force_per_depth: np.ndarray
    strain_energy_per_depth: float
    temperature_snapshot: TemperatureSnapshot
    stress_free_temperature: float
    linear_expansion_coefficient: float | dict
    youngs_modulus: float | dict
    poisson_ratio: float | dict
    plane: str
    applied_body_force_per_depth: np.ndarray | None = None
    applied_traction_force_per_depth: np.ndarray | None = None


#: the quantity parameters of solve_thermoelasticity, refused as text (SI numbers only)
_QUANTITIES = ("stress_free_temperature", "linear_expansion_coefficient", "youngs_modulus", "poisson_ratio",
               "prescribed_displacement", "body_force_density", "traction")


def solve_thermoelasticity(mesh, temperature_snapshot, *, stress_free_temperature,
                          linear_expansion_coefficient, youngs_modulus, poisson_ratio,
                          plane, prescribed_displacement, body_force_density=None, traction=None, motion=None):
    """Solve the static mechanical stage; no automatic heat solve or transfer.

    Absolute T and stress_free_temperature: nonnegative K; linear_expansion_coefficient:
    signed 1/K; youngs_modulus: Pa. Coordinates and displacement: m; body_force_density:
    None (no body force), a constant (2,) or a callable, N/m^3. traction maps
    boundary_edges tags to global Cartesian Pa vectors or (points, outward_normals)->(Q,2)
    callbacks. It is TOTAL physical sigma*n; never adjust it by thermal traction.
    None/{} keeps zero TOTAL natural traction. Prescribed components retain applied line
    loads in reactions/support work. No dedicated scalar-pressure keyword, local-frame
    traction API, or follower geometry update is provided. A global Pa callback returning
    -p*normal is valid on the fixed reference boundary. Cross-mesh interpolation is
    unsupported. Near-incompressible plane-strain P1 locking remains possible.
    linear_expansion_coefficient, youngs_modulus and poisson_ratio may each be
    {region name: value} over mesh.region_names.

    stress_free_temperature, linear_expansion_coefficient, youngs_modulus, poisson_ratio,
    the prescribed displacements, body_force_density and traction may be JAX or PyTorch
    values, or callbacks returning them; the result is then in that library with
    reverse-mode derivatives (docs/packages/galerkin/differentiation.md). Callbacks are
    called once. A str for a quantity raises TypeError (SI numbers only).

    motion=galerkin.shape.MeshMotion(design_velocity=W, t=t) solves on the nodes X0 +
    t*W; the snapshot belongs to the mesh as given, and its nodal temperatures move with
    their nodes. Every result carries the derivative with respect to the JAX or PyTorch
    scalar t (docs/packages/galerkin/shape_derivative.md).
    """
    for name, value in zip(_QUANTITIES, (stress_free_temperature, linear_expansion_coefficient, youngs_modulus,
                                         poisson_ratio, prescribed_displacement, body_force_density, traction)):
        (refuse_tagged_text if name == "traction" else refuse_text)(name, value)
    reference_temperature_k, thermal_expansion_per_k = stress_free_temperature, linear_expansion_coefficient
    young_modulus, dirichlet = youngs_modulus, prescribed_displacement
    body_force = (0., 0.) if body_force_density is None else body_force_density
    if motion is not None:
        from ._moving import solve_thermoelasticity_moving
        return solve_thermoelasticity_moving(
            mesh, temperature_snapshot, motion, stress_free_temperature=stress_free_temperature,
            linear_expansion_coefficient=linear_expansion_coefficient, youngs_modulus=youngs_modulus,
            poisson_ratio=poisson_ratio, plane=plane, prescribed_displacement=prescribed_displacement,
            body_force_density=body_force, traction=traction)
    p, t, area, boundary, count, labels = triangle_geometry(mesh, counterclockwise=False)
    b, dofs = vector_strain(p, t)
    _verify_snapshot(temperature_snapshot, p, t)
    tref = real_value(reference_temperature_k, "stress_free_temperature")
    if tuple(tref.shape) != () or to_numpy(tref) < 0:
        raise ValueError("stress_free_temperature must be a finite nonnegative real scalar")
    regional = any(is_per_region(v) for v in (thermal_expansion_per_k, young_modulus, poisson_ratio))
    alpha = region_property(mesh, thermal_expansion_per_k, "linear_expansion_coefficient", live=True)
    one_of(plane, PLANES, "plane")
    e, nu = _element_materials(mesh, young_modulus, poisson_ratio)
    body = _body_load(p, t, area, dofs, body_force)
    line = traction_load(mesh, p, t, traction, live=True)
    xp = live_namespace(tref, alpha, e, nu, body, line, *live_inputs.leaves(dirichlet))
    tref, alpha, e, nu = (lift(xp, v, xp.float64) for v in (tref, alpha, e, nu))
    if regional:
        alpha, e, nu = (xp.broadcast_to(v, (len(t),)) for v in (alpha, e, nu))
    temperature = lift(xp, temperature_snapshot.temperature)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        d = _constitutive(xp, e, nu, plane)
        coefficient = _thermal_coefficient(e, nu, plane)
        if regional:
            a = alpha[:, None]*(temperature[t]-tref)       # (T,3) nodal values per element
            q = coefficient[:, None]*a
        else:
            a = alpha*(temperature-tref)                   # nodal (N,)
            q = coefficient*a
            a, q = a[t], q[t]
    if not all(np.all(np.isfinite(to_numpy(v))) for v in (coefficient, a, q)):
        raise ValueError("thermal coefficient/strain/stress exceeds finite numeric range")
    require_finite(d, "constitutive parameters exceed floating-point range")
    n = 2*len(p)
    stiffness = _vector_stiffness(xp, b, dofs, d, area, n)
    body, line = lift(xp, body), lift(xp, line)
    external = body+line
    qc, ac = xp.mean(q, axis=1), xp.mean(a, axis=1)
    m_vector = lift(xp, ISOTROPIC_STRAIN)
    thermal = lift(xp, _thermal_load(area, b, dofs, qc, len(p)))
    load = external+thermal
    if not all(np.all(np.isfinite(to_numpy(v))) for v in (body, line, external, thermal, load)):
        raise ValueError("assembled external/thermal load exceeds finite numeric range")
    u, fixed = _displacement(xp, stiffness, load, dirichlet, p, boundary, count, labels, "thermoelastic")
    residual = stiffness.matvec(u)-external-thermal
    strain = xp.einsum("tij,tj->ti", lift(xp, b), u[dofs])
    th = ac[:, None]*m_vector
    elastic = strain-th
    stress = _stress_of(xp, d, strain)-qc[:, None]*m_vector
    trace = strain[:, 0]+strain[:, 1]
    if plane == "strain":
        zz = _lame(e, nu, "strain")[0]*trace-qc
        ez = xp.zeros_like(qc)
    else:
        zz = xp.zeros_like(qc)
        ez = ((1+nu)*ac-nu*trace)/(1-nu)
    with np.errstate(over="ignore", invalid="ignore"):
        energy = _physical_energy(xp, strain, a, area, d, e, nu, plane)
    if not all(np.all(np.isfinite(to_numpy(v))) for v in (strain, th, elastic, stress, zz, ez)):
        raise ValueError("computed thermoelastic strain/stress exceeds finite numeric range")
    numpy = backend_of(xp) is Backend.NUMPY
    return ThermoelasticResult(
        xp.reshape(u, (-1, 2)), strain, th, elastic, stress, zz, ez,
        *(xp.reshape(v, (-1, 2)) for v in (external, thermal, _at_fixed(xp, residual, fixed), residual)),
        energy, temperature_snapshot, float(tref) if numpy else tref,
        *(_material_record(xp, v) for v in (thermal_expansion_per_k, young_modulus, poisson_ratio)),
        plane, xp.reshape(body, (-1, 2)), xp.reshape(line, (-1, 2)))
