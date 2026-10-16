# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Static mechanical stage for an explicitly prescribed nodal-P1 Kelvin field.

This module does not call a heat solver or authenticate temperature provenance.
See ../docs/prescribed_temperature_thermoelasticity.md for units and reductions.
"""
from dataclasses import dataclass, field
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import splu

from .elasticity import (_mesh_data, _constraints, _quadrature, _real,
                         constitutive_matrix, _traction_load)

_M = np.array([1., 1., 0.])


def _scalar(value, name, nonnegative=False):
    a = _real(value, name)
    if a.shape != () or not np.isfinite(a) or (nonnegative and a < 0):
        raise ValueError(f"{name} must be a finite {'nonnegative ' if nonnegative else ''}real scalar")
    return float(a)


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
        p = _real(self.nodes, "snapshot nodes")
        t = np.asarray(self.triangles)
        temp = _real(self.temperature_k, "temperature_k")
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
    p, t, *_ = _mesh_data(mesh)
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
    local = np.einsum("tji,j,t->ti", b, _M, area*q_mean)
    load = np.zeros(2*num_nodes)
    np.add.at(load, dofs.ravel(), local.ravel())
    return load


def _external_body_load(p, triangles, area, dofs, body_force):
    bary, weights = _quadrature()
    points = np.einsum("qa,tad->tqd", bary, p[triangles])
    if callable(body_force):
        force = _real(body_force(points.reshape(-1,2)), "body_force")
        if force.shape != (points.shape[0]*points.shape[1],2):
            raise ValueError("body_force callable must return shape (Q,2)")
        force = force.reshape(points.shape)
    else:
        force = _real(body_force, "body_force")
        if force.shape != (2,):
            raise ValueError("constant body_force must have shape (2,)")
        force = np.broadcast_to(force, points.shape)
    local = np.einsum("qa,q,tqd,t->tad", bary, weights, force, area)
    load = np.zeros(2*len(p))
    np.add.at(load, dofs.ravel(), local.ravel())
    return load


def _physical_energy(total_strain, a_element_nodes, area, d, e, nu, plane):
    bary = np.array([[2/3,1/6,1/6], [1/6,2/3,1/6], [1/6,1/6,2/3]])
    aq = a_element_nodes @ bary.T
    effective = aq if plane == "stress" else (1+nu)*aq
    delta = total_strain[:,None,:]-effective[...,None]*_M
    density = .5*np.einsum("tqi,ij,tqj->tq", delta, d, delta)
    if plane == "strain":
        density += .5*e*aq**2
    if not np.all(np.isfinite(density)) or np.any(density < 0):
        raise ValueError("nonfinite or negative physical elastic energy; check numeric scaling")
    value = float(np.sum(area[:,None]*density)/3)
    if not np.isfinite(value):
        raise ValueError("integrated physical elastic energy exceeds floating-point range")
    return value


@dataclass
class ThermoelasticResult:
    """Mechanical fields for a prescribed temperature snapshot, per thickness.

    total_strain is element constant. thermal_strain, elastic_strain, stress,
    sigma_zz and epsilon_zz are sampled at triangle centroids; stress generally
    varies linearly inside a triangle. Strain order is (exx,eyy,gamma_xy).
    load_external (body + traction), load_thermal, reaction and residual are N/m
    arrays. physical_elastic_energy is the reduced physical 3D energy, J/m.
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
    thermal_expansion_per_k: float
    young_modulus: float
    poisson_ratio: float
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
    """
    p,t,area,b,dofs,boundary,count,labels = _mesh_data(mesh)
    _verify_snapshot(temperature_snapshot,p,t)
    tref = _scalar(reference_temperature_k,"reference_temperature_k",True)
    alpha = _scalar(thermal_expansion_per_k,"thermal_expansion_per_k")
    e,nu = _scalar(young_modulus,"young_modulus"), _scalar(poisson_ratio,"poisson_ratio")
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        d = constitutive_matrix(e,nu,plane=plane)
        coefficient = _thermal_coefficient(e,nu,plane)
        a = alpha*(temperature_snapshot.temperature_k-tref)
        q = coefficient*a
    if not np.isfinite(coefficient) or not np.all(np.isfinite(a)) or not np.all(np.isfinite(q)):
        raise ValueError("thermal coefficient/strain/stress exceeds finite numeric range")
    fixed,values = _constraints(dirichlet,p,boundary,count,labels)
    ke = np.einsum("tji,jk,tkl,t->til",b,d,b,area)
    if not np.all(np.isfinite(ke)):
        raise ValueError("element stiffness exceeds finite numeric range")
    rows,cols = np.repeat(dofs,6,axis=1).ravel(), np.tile(dofs,(1,6)).ravel()
    k = coo_matrix((ke.ravel(),(rows,cols)),shape=(2*len(p),2*len(p))).tocsr()
    body = _external_body_load(p,t,area,dofs,body_force)
    line = _traction_load(mesh,p,t,traction)
    external = body+line
    thermal = _thermal_load(area,b,dofs,q[t].mean(axis=1),len(p))
    load = external+thermal
    if not all(np.all(np.isfinite(v)) for v in (body,line,external,thermal,load)):
        raise ValueError("assembled external/thermal load exceeds finite numeric range")
    free = np.setdiff1d(np.arange(len(load)),fixed)
    u = np.zeros_like(load)
    u[fixed] = values
    if len(free):
        rhs = load[free]-k[free][:,fixed]@values
        try:
            u[free] = splu(k[free][:,free].tocsc()).solve(rhs)
        except RuntimeError as exc:
            raise ValueError("singular or ill-conditioned constrained thermoelastic system") from exc
    residual = k@u-external-thermal
    if not np.all(np.isfinite(u)) or not np.all(np.isfinite(residual)):
        raise ValueError("nonfinite thermoelastic solution")
    scale = max(np.linalg.norm(abs(k)@abs(u)+abs(external)+abs(thermal),np.inf),np.finfo(float).tiny)
    if len(free) and np.linalg.norm(residual[free],np.inf) > 1e-9*scale:
        raise ValueError("constrained thermoelastic solve failed its residual tolerance")
    reaction = np.zeros_like(load)
    reaction[fixed] = residual[fixed]
    strain = np.einsum("tij,tj->ti",b,u[dofs])
    ac = a[t].mean(axis=1)
    qc = q[t].mean(axis=1)
    th = ac[:,None]*_M
    elastic = strain-th
    stress = strain@d.T-qc[:,None]*_M
    if plane == "strain":
        lam = e*nu/((1+nu)*(1-2*nu))
        zz = lam*(strain[:,0]+strain[:,1])-qc
        ez = np.zeros(len(t))
    else:
        zz = np.zeros(len(t))
        ez = ((1+nu)*ac-nu*(strain[:,0]+strain[:,1]))/(1-nu)
    with np.errstate(over="ignore",invalid="ignore"):
        energy = _physical_energy(strain,a[t],area,d,e,nu,plane)
    if not all(np.all(np.isfinite(v)) for v in (strain,th,elastic,stress,zz,ez)):
        raise ValueError("computed thermoelastic strain/stress exceeds finite numeric range")
    return ThermoelasticResult(u.reshape(-1,2),strain,th,elastic,stress,zz,ez,
        external.reshape(-1,2),thermal.reshape(-1,2),reaction.reshape(-1,2),
        residual.reshape(-1,2),energy,temperature_snapshot,tref,alpha,e,nu,plane,
        body.reshape(-1,2),line.reshape(-1,2))
