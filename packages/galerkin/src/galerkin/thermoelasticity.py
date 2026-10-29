# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Static mechanical stage for an explicitly prescribed nodal-P1 Kelvin field.

This module does not call a heat solver or authenticate temperature provenance.
alpha, E and nu are scalars or piecewise constant on named mesh regions
(galerkin.materials, docs/packages/galerkin/multimaterial.md).
See docs/packages/galerkin/prescribed_temperature_thermoelasticity.md for units and reductions.

Tref, alpha, E, nu, Dirichlet displacements, body force and traction may be JAX
or PyTorch values (callbacks may return them); the result arrays are then in that
library and carry reverse-mode derivatives. The temperature snapshot is a NumPy
container. One body serves NumPy and live inputs, solving as galerkin.elasticity
does.
"""
from dataclasses import dataclass, field
import numpy as np

from .elasticity import (at_fixed, body_load, constitutive, displacement, element_materials,
                         lame, stress_of, vector_stiffness, PLANES)
from .core import live as live_inputs
from .core.backend import Backend, backend_of, lift, live_namespace, namespace, scatter_add, to_numpy
from .core.boundary import traction_load
from .core.checks import one_of, real_array, real_value, require_finite
from .core.triangles import triangle_geometry, vector_strain
from .materials import is_per_region, region_property

_M = np.array([1., 1., 0.])


def _immutable(array, dtype):
    a = np.asarray(array, dtype=dtype)
    if not np.all(np.isfinite(a)):
        raise ValueError("snapshot normalization exceeds finite numeric range")
    return np.frombuffer(a.tobytes(order="C"), dtype=dtype).reshape(a.shape)


def _payload(array):
    return (array.dtype.str.encode("ascii") + bytes([array.ndim])
            + np.asarray(array.shape, dtype="<u8").tobytes() + array.tobytes(order="C"))


def _fingerprint(*parts):
    """Versioned reproducible FNV-1a64 checksum, not a provenance signature.

    Exact arrays are also compared; checksum collisions cannot authorize a
    mismatched mesh. Framing removes ambiguity between concatenated parts.
    """
    value = 14695981039346656037
    for part in parts:
        for byte in len(part).to_bytes(8, "little") + part:
            value = ((value ^ byte)*1099511628211) & ((1 << 64)-1)
    return f"fnv1a64:{value:016x}"


def _hashes(nodes, triangles, temperature):
    p, t, temp = _payload(nodes), _payload(triangles), _payload(temperature)
    return (_fingerprint(b"mesh-v1|m", p, t),
            _fingerprint(b"temperature-v1|K", temp),
            _fingerprint(b"temperature-snapshot-v1|nodal-P1|m|K", p, t, temp))


@dataclass(frozen=True, eq=False)
class TemperatureSnapshot:
    """Copied immutable SI geometry/connectivity/temperature, in original order.

    Use freeze_temperature to validate the full Mesh before construction.
    Arrays are backed by immutable bytes, not just a reversible write flag.
    Fingerprints are reproducible checksums; this is not an authenticated heat
    result, cross-mesh mapping, or temperature-unit inference mechanism.
    """
    nodes: np.ndarray = field(repr=False)
    triangles: np.ndarray = field(repr=False)
    temperature_k: np.ndarray = field(repr=False)
    mesh_hash: str = field(init=False)
    temperature_hash: str = field(init=False)
    snapshot_hash: str = field(init=False)
    schema_version: int = field(default=1, init=False)
    length_unit: str = field(default="m", init=False)
    temperature_unit: str = field(default="K", init=False)

    def __post_init__(self):
        p = real_array(self.nodes, "snapshot nodes")
        t = np.asarray(self.triangles)
        temp = real_array(self.temperature_k, "temperature_k")
        if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3:
            raise ValueError("snapshot nodes must have shape (N,2), N>=3")
        if (t.ndim != 2 or t.shape[1] != 3 or not len(t) or t.dtype.kind not in "iu"
                or np.any(t < 0) or np.any(t >= len(p))):
            raise ValueError("snapshot triangles must be integer (M,3) valid node indices")
        if temp.shape != (len(p),) or np.any(temp < 0):
            raise ValueError("temperature_k must be nonnegative absolute Kelvin with shape (N,)")
        p, t, temp = _immutable(p, "<f8"), _immutable(t, "<i8"), _immutable(temp, "<f8")
        for name, value in zip(("nodes", "triangles", "temperature_k"), (p, t, temp)):
            object.__setattr__(self, name, value)
        for name, value in zip(("mesh_hash", "temperature_hash", "snapshot_hash"), _hashes(p,t,temp)):
            object.__setattr__(self, name, value)


def freeze_temperature(mesh, temperature_k):
    """Validate mesh and copy a finite nonnegative (N,) Kelvin P1 nodal field."""
    p, t, *_ = triangle_geometry(mesh, counterclockwise=False)
    return TemperatureSnapshot(p, t, temperature_k)


def _verify_snapshot(snapshot, p, t):
    if not isinstance(snapshot, TemperatureSnapshot):
        raise ValueError("temperature_snapshot must be a TemperatureSnapshot from freeze_temperature")
    if (snapshot.schema_version != 1 or snapshot.length_unit != "m"
            or snapshot.temperature_unit != "K"):
        raise ValueError("snapshot schema/units must be nodal-P1 v1, metres and Kelvin")
    for value, dtype in ((snapshot.nodes, "<f8"), (snapshot.triangles, "<i8"),
                          (snapshot.temperature_k, "<f8")):
        if not isinstance(value, np.ndarray) or value.dtype != np.dtype(dtype) or value.flags.writeable:
            raise ValueError("snapshot arrays lost their immutable canonical representation")
        base = value
        while isinstance(base, np.ndarray):
            base = base.base
        if not isinstance(base, bytes):
            raise ValueError("snapshot arrays must retain their immutable bytes backing")
    if (snapshot.nodes.shape != p.shape or snapshot.triangles.shape != t.shape
            or snapshot.temperature_k.shape != (len(p),)
            or not np.all(np.isfinite(snapshot.temperature_k)) or np.any(snapshot.temperature_k < 0)):
        raise ValueError("invalid snapshot shape or absolute-temperature domain")
    expected = _hashes(snapshot.nodes, snapshot.triangles, snapshot.temperature_k)
    if expected != (snapshot.mesh_hash, snapshot.temperature_hash, snapshot.snapshot_hash):
        raise ValueError("snapshot hash mismatch: snapshot data or metadata was modified")
    current_p, current_t = np.asarray(p, dtype="<f8"), np.asarray(t, dtype="<i8")
    current_hash = _fingerprint(b"mesh-v1|m", _payload(current_p), _payload(current_t))
    if (current_hash != snapshot.mesh_hash or not np.array_equal(p, snapshot.nodes)
            or not np.array_equal(t, snapshot.triangles)):
        raise ValueError("stale or mismatched mesh: coordinates, units/scale, connectivity or order changed")


def _thermal_coefficient(young_modulus, poisson_ratio, plane):
    return young_modulus/(1-poisson_ratio if plane == "stress" else 1-2*poisson_ratio)


def _thermal_load(area, b, dofs, q_mean, num_nodes):
    """Thermal-equivalent nodal load (2N,) of the element-mean thermal stress q_mean (T,), in its library."""
    xp = namespace(q_mean)
    local = xp.einsum("tji,j,t->ti", lift(xp, b), lift(xp, _M), lift(xp, area)*q_mean)
    return scatter_add(xp, 2*num_nodes, dofs.ravel(), xp.reshape(local, (-1,)))


def _per_cell(value):
    """A (T,) value as a column for (T, k) arithmetic; scalars as they are."""
    return value[:, None] if getattr(value, "ndim", 0) == 1 else value


_CENTROID_BARY = np.array([[2/3, 1/6, 1/6], [1/6, 2/3, 1/6], [1/6, 1/6, 2/3]])


def _physical_energy(xp, total_strain, a_element_nodes, area, d, e, nu, plane):
    """Reduced physical 3D elastic energy per thickness, J/m (exact for P1 with the 3-point rule)."""
    aq = a_element_nodes @ lift(xp, _CENTROID_BARY).T
    effective = aq if plane == "stress" else _per_cell(1+nu)*aq
    delta = total_strain[:, None, :]-effective[..., None]*lift(xp, _M)
    density = .5*(xp.einsum("tqi,ij,tqj->tq", delta, d, delta) if d.ndim == 2
                  else xp.einsum("tqi,tij,tqj->tq", delta, d, delta))
    if plane == "strain":
        density = density + .5*_per_cell(e)*aq**2
    numbers = to_numpy(density)
    if not np.all(np.isfinite(numbers)) or np.any(numbers < 0):
        raise ValueError("nonfinite or negative physical elastic energy; check numeric scaling")
    value = xp.sum(lift(xp, area)[:, None]*density)/3
    if not np.isfinite(to_numpy(value)):
        raise ValueError("integrated physical elastic energy exceeds floating-point range")
    return float(value) if backend_of(xp) is Backend.NUMPY else value


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
class ThermoelasticResult:
    """Mechanical fields for a prescribed temperature snapshot, per thickness.

    total_strain is element constant. thermal_strain, elastic_strain, stress,
    sigma_zz and epsilon_zz are sampled at triangle centroids; stress generally
    varies linearly inside a triangle. Strain order is (exx,eyy,gamma_xy).
    load_external (body + traction), load_thermal, reaction and residual are N/m
    arrays. physical_elastic_energy is the reduced physical 3D energy, J/m.
    thermal_expansion_per_k, young_modulus and poisson_ratio echo the input:
    a float, or a {region name: float} copy for per-region materials.
    """
    displacement: np.ndarray
    total_strain: np.ndarray
    thermal_strain: np.ndarray
    elastic_strain: np.ndarray
    stress: np.ndarray
    sigma_zz: np.ndarray
    epsilon_zz: np.ndarray
    load_external: np.ndarray
    load_thermal: np.ndarray
    reaction: np.ndarray
    residual: np.ndarray
    physical_elastic_energy: float
    temperature_snapshot: TemperatureSnapshot
    reference_temperature_k: float
    thermal_expansion_per_k: float | dict
    young_modulus: float | dict
    poisson_ratio: float | dict
    plane: str
    load_body: np.ndarray | None = None
    load_traction: np.ndarray | None = None

    @property
    def load_total(self):
        """External body/traction load plus thermal-equivalent load, N/m of thickness."""
        return self.load_external+self.load_thermal


def solve_thermoelasticity(mesh, temperature_snapshot, *, reference_temperature_k,
                          thermal_expansion_per_k, young_modulus, poisson_ratio,
                          plane, dirichlet, body_force=(0.,0.), traction=None):
    """Solve the static mechanical stage; no automatic heat solve or transfer.

    Absolute T/Tref: nonnegative K; alpha: signed 1/K; E: Pa. Coordinates and
    displacement: m. traction maps boundary_edges tags to global Cartesian
    Pa vectors or (points_m, outward_normals)->(Q,2) callbacks. It is TOTAL
    physical sigma*n; never adjust it by thermal traction. None/{} keeps zero
    TOTAL natural traction. Prescribed components retain applied line loads in
    reactions/support work. No dedicated scalar-pressure keyword, local-frame traction API, or follower
    geometry update is provided. A global Pa callback returning -p*normal is valid
    on the fixed reference boundary. Cross-mesh interpolation is unsupported. Near-incompressible plane-strain P1 locking remains possible.
    alpha, E and nu may each be {region name: value} over mesh.region_names.

    Tref, alpha, E, nu, Dirichlet displacements, body_force and traction may be
    JAX or PyTorch values, or callbacks returning them; the result is then in
    that library with reverse-mode derivatives
    (docs/packages/galerkin/differentiation.md). Callbacks are called once.
    """
    p, t, area, boundary, count, labels = triangle_geometry(mesh, counterclockwise=False)
    b, dofs = vector_strain(p, t)
    _verify_snapshot(temperature_snapshot, p, t)
    tref = real_value(reference_temperature_k, "reference_temperature_k")
    if tuple(tref.shape) != () or to_numpy(tref) < 0:
        raise ValueError("reference_temperature_k must be a finite nonnegative real scalar")
    regional = any(is_per_region(v) for v in (thermal_expansion_per_k, young_modulus, poisson_ratio))
    alpha = region_property(mesh, thermal_expansion_per_k, "thermal_expansion_per_k", live=True)
    one_of(plane, PLANES, "plane")
    e, nu = element_materials(mesh, young_modulus, poisson_ratio)
    body = body_load(p, t, area, dofs, body_force)
    line = traction_load(mesh, p, t, traction, live=True)
    xp = live_namespace(tref, alpha, e, nu, body, line, *live_inputs.leaves(dirichlet))
    tref, alpha, e, nu = (lift(xp, v, xp.float64) for v in (tref, alpha, e, nu))
    if regional:
        alpha, e, nu = (xp.broadcast_to(v, (len(t),)) for v in (alpha, e, nu))
    temperature = lift(xp, temperature_snapshot.temperature_k)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        d = constitutive(xp, e, nu, plane)
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
    stiffness = vector_stiffness(xp, b, dofs, d, area, n)
    body, line = lift(xp, body), lift(xp, line)
    external = body+line
    qc, ac = xp.mean(q, axis=1), xp.mean(a, axis=1)
    m_vector = lift(xp, _M)
    thermal = lift(xp, _thermal_load(area, b, dofs, qc, len(p)))
    load = external+thermal
    if not all(np.all(np.isfinite(to_numpy(v))) for v in (body, line, external, thermal, load)):
        raise ValueError("assembled external/thermal load exceeds finite numeric range")
    u, fixed = displacement(xp, stiffness, load, dirichlet, p, boundary, count, labels, "thermoelastic")
    residual = stiffness.matvec(u)-external-thermal
    strain = xp.einsum("tij,tj->ti", lift(xp, b), u[dofs])
    th = ac[:, None]*m_vector
    elastic = strain-th
    stress = stress_of(xp, d, strain)-qc[:, None]*m_vector
    trace = strain[:, 0]+strain[:, 1]
    if plane == "strain":
        zz = lame(e, nu, "strain")[0]*trace-qc
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
        *(xp.reshape(v, (-1, 2)) for v in (external, thermal, at_fixed(xp, residual, fixed), residual)),
        energy, temperature_snapshot, float(tref) if numpy else tref,
        *(_material_record(xp, v) for v in (thermal_expansion_per_k, young_modulus, poisson_ratio)),
        plane, xp.reshape(body, (-1, 2)), xp.reshape(line, (-1, 2)))
