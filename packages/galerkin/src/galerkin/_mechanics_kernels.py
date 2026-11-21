# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Kernels of the mechanics solvers that other galerkin modules share (package-private).

The plane-stress and plane-strain constitutive helpers, the vector P1 stiffness and
loads and the constrained displacement solve of ``galerkin.elasticity``, which
``galerkin.thermoelasticity`` and the moving-mesh solves reuse, and the
thermoelastic helpers of ``galerkin.thermoelasticity``: the thermal coefficient, the
reduced physical elastic energy and the temperature snapshot's checksums and check.
They were the mechanics modules' own helpers until the galerkin step (L2 commit 8);
the mechanics modules now hold no name that left their public API, so the helpers
live here and ``galerkin.kernels`` re-exports them unchanged. Consistent units:
whatever units the caller's numbers have (SI from the solvers). The kernels keep
their positional coefficients (``young_modulus``, ``body_force``); their messages
name the public quantities (``youngs_modulus``, ``body_force_density``) the solvers
hand them.
"""
import numpy as np

from .materials import is_per_region, region_property
from .core import forms, kernels
from .core import live as live_inputs
from .core import solve as core_solve
from .core.backend import Backend, backend_of, is_live, lift, live_namespace, namespace, scatter_add, to_numpy
from .core.checks import one_of, real_value, require_finite
from .core.sparse import CooMatrix
from .core.constraints import vector_dirichlet
from .core.quadrature import triangle_product_rule

__all__ = ["PLANES", "ISOTROPIC_STRAIN", "lame", "constitutive", "element_materials", "element_constitutive",
           "stiffness_and_stress", "stress_of", "body_load", "check_solution", "displacement", "at_fixed",
           "vector_stiffness", "thermal_coefficient", "physical_energy", "payload", "fingerprint",
           "snapshot_hashes", "verify_snapshot"]


PLANES = ("stress", "strain")

# (exx, eyy, gamma_xy) of a unit isotropic in-plane strain; shared with galerkin.shape
ISOTROPIC_STRAIN = np.array([1., 1., 0.])


# ----------------------------------------------------------------------------- elasticity

def lame(e, nu, plane):
    """Lame parameters (lam, mu) in Pa of the plane-stress or plane-strain reduction.

    Elementwise arithmetic only, so e and nu may be floats, NumPy arrays or
    JAX/PyTorch arrays.
    """
    mu = e / (2 * (1 + nu))
    lam = (e * nu / ((1 + nu) * (1 - 2 * nu)) if plane == "strain"
           else e * nu / (1 - nu * nu))
    return lam, mu


def constitutive(xp, e, nu, plane):
    """Pa matrix for [exx, eyy, gamma_xy] in ``xp``: (3,3) for 0-d e and nu, (T,3,3) for (T,)."""
    lam, mu = lame(e, nu, plane)
    zero = xp.zeros_like(mu)
    rows = [[lam + 2*mu, lam, zero], [lam, lam + 2*mu, zero], [zero, zero, mu]]
    return xp.stack([xp.stack(row, axis=-1) for row in rows], axis=-2)


def element_materials(mesh, young_modulus, poisson_ratio):
    """Checked E and nu: as given for scalars, (T,) if either is a region table.

    E > 0 and -1 < nu < 0.5 in every region. JAX or PyTorch values stay live.
    """
    e = region_property(mesh, young_modulus, "youngs_modulus", positive=True, live=True)
    nu = region_property(mesh, poisson_ratio, "poisson_ratio", lower=-1., upper=.5, live=True)
    if is_per_region(young_modulus) or is_per_region(poisson_ratio):
        cells = len(mesh.triangles)
        e, nu = (v if is_live(v) else np.broadcast_to(v, (cells,)) for v in (e, nu))
        xp = live_namespace(e, nu)
        e, nu = (xp.broadcast_to(lift(xp, v, xp.float64), (cells,)) for v in (e, nu))
    return e, nu


def element_constitutive(mesh, young_modulus, poisson_ratio, *, plane):
    """Pa constitutive matrix: (3,3) for scalars, (T,3,3) for region mappings.

    Scalars return exactly galerkin.elasticity.constitutive_matrix(...). A mapping for
    either argument gives one matrix per triangle; each region must satisfy E > 0 and
    -1 < nu < 0.5.
    """
    if not (is_per_region(young_modulus) or is_per_region(poisson_ratio)):
        from .elasticity import constitutive_matrix
        return constitutive_matrix(youngs_modulus=young_modulus, poisson_ratio=poisson_ratio, plane=plane)
    one_of(plane, PLANES, "plane")
    e, nu = element_materials(mesh, young_modulus, poisson_ratio)
    xp = live_namespace(e, nu)
    d = constitutive(xp, e, nu, plane)
    require_finite(d, "constitutive parameters exceed floating-point range")
    return d


def stiffness_and_stress(b, d, area):
    """Element stiffness (T,6,6) and a strain->stress map for (3,3) or (T,3,3) d."""
    xp = namespace(d)
    return kernels.vector_p1_stiffness(b, d, area), lambda strain: stress_of(xp, d, strain)


def stress_of(xp, d, strain):
    """Element stress (T,3) from strain (T,3) and d (3,3) or (T,3,3)."""
    if d.ndim == 2:
        return strain @ d.T
    return xp.einsum("tij,tj->ti", d, strain)


def body_load(p, t, area, dofs, body_force):
    """Consistent load (2N,) of a constant (2,) or callable body force in N/m^3.

    The callable takes (Q,2) coordinates and returns exactly (Q,2). The load is
    in the library of the force (NumPy for NumPy input).
    """
    bary, weights = triangle_product_rule()
    points = np.einsum("qa,tad->tqd", bary, p[t])
    if callable(body_force):
        force = real_value(body_force(points.reshape(-1, 2)), "body_force_density")
        if tuple(force.shape) != (points.shape[0]*points.shape[1], 2):
            raise ValueError("body_force_density callable must return shape (Q, 2)")
        xp = namespace(force)
        force = xp.reshape(force, points.shape)
    else:
        force = real_value(body_force, "body_force_density")
        if tuple(force.shape) != (2,):
            raise ValueError("constant body_force_density must have shape (2,)")
        xp = namespace(force)
        force = xp.broadcast_to(force, points.shape)
    fe = xp.einsum("qa,q,tqd,t->tad", *(lift(xp, a) for a in (bary, weights)), force, lift(xp, area))
    return scatter_add(xp, 2*len(p), dofs.ravel(), xp.reshape(fe, (-1,)))


def check_solution(stiffness, u, load, fixed, what):
    """Raise ValueError for a nonfinite displacement or a free-DOF residual above 1e-9 of the load scale.

    NumPy arguments: ``stiffness`` as SciPy CSR, ``u`` and ``load`` (2N,).
    """
    residual = stiffness @ u - load
    if not np.all(np.isfinite(u)) or not np.all(np.isfinite(residual)):
        raise ValueError(f"nonfinite {what} solution; check geometry and material scaling")
    free = np.setdiff1d(np.arange(len(load)), fixed)
    scale = max(np.linalg.norm(abs(stiffness) @ abs(u)+abs(load), np.inf), np.finfo(float).tiny)
    if len(free) and np.linalg.norm(residual[free], np.inf) > 1e-9*scale:
        raise ValueError(f"constrained {what} solve failed its residual tolerance")


def displacement(xp, stiffness, load, dirichlet, p, boundary, count, labels, what):
    """Displacement (2N,) in ``xp`` and the fixed DOFs.

    One ``core.solve`` solve in the inputs' library: with JAX or PyTorch values
    the displacement carries exact derivatives to K, the load and the Dirichlet
    values. The checks read its numbers: a singular or ill-conditioned system,
    a nonfinite solution or a free-DOF residual above 1e-9 of the load scale
    raises ValueError.
    """
    fixed, values = vector_dirichlet(live_inputs.numbers(dirichlet), p, boundary, count, labels)
    if backend_of(xp) is not Backend.NUMPY and len(fixed):
        values = xp.stack([lift(xp, v, xp.float64) for v in dirichlet.values()])
    try:
        u = core_solve.solve_dirichlet(stiffness, load, {tuple(fixed): values} if len(fixed) else {})
    except (RuntimeError, ValueError) as exc:
        raise ValueError(f"singular or ill-conditioned constrained {what} system") from exc
    check_solution(_numbers(stiffness).to_scipy(), to_numpy(u), to_numpy(load), fixed, what)
    return u, fixed


def _numbers(matrix):
    return CooMatrix(matrix.rows, matrix.cols, to_numpy(matrix.values), matrix.shape)


def at_fixed(xp, residual, fixed):
    """The reaction: ``residual`` at the fixed DOFs, zero elsewhere."""
    mask = np.zeros(residual.shape[0], dtype=bool)
    mask[fixed] = True
    return xp.where(lift(xp, mask), residual, xp.zeros_like(residual))


def vector_stiffness(xp, b, dofs, d, area, size):
    """Element stiffness checked finite, assembled: a CooMatrix in ``xp`` (coalesced when live)."""
    ke = kernels.vector_p1_stiffness(b, d, area)
    if not np.all(np.isfinite(to_numpy(ke))):
        raise ValueError("element stiffness exceeds floating-point range")
    k = forms.matrix(dofs, dofs, ke, (size, size))
    return k if backend_of(xp) is Backend.NUMPY else k.coalesce()


# ----------------------------------------------------------------------------- thermoelasticity

def thermal_coefficient(young_modulus, poisson_ratio, plane):
    """Thermal stress per unit thermal strain of the plane reduction: E/(1-nu) or E/(1-2nu)."""
    return young_modulus/(1-poisson_ratio if plane == "stress" else 1-2*poisson_ratio)


def _per_cell(value):
    """A (T,) value as a column for (T, k) arithmetic; scalars as they are."""
    return value[:, None] if getattr(value, "ndim", 0) == 1 else value


_CENTROID_BARY = np.array([[2/3, 1/6, 1/6], [1/6, 2/3, 1/6], [1/6, 1/6, 2/3]])


def physical_energy(xp, total_strain, a_element_nodes, area, d, e, nu, plane):
    """Reduced physical 3D elastic energy per thickness, J/m (exact for P1 with the 3-point rule)."""
    aq = a_element_nodes @ lift(xp, _CENTROID_BARY).T
    effective = aq if plane == "stress" else _per_cell(1+nu)*aq
    delta = total_strain[:, None, :]-effective[..., None]*lift(xp, ISOTROPIC_STRAIN)
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


# ----------------------------------------------------------------------------- the temperature snapshot

#: the units of a TemperatureSnapshot: its nodes in metres, its temperature in Kelvin
SNAPSHOT_UNITS = {"nodes": "m", "temperature": "K"}


def payload(array):
    return (array.dtype.str.encode("ascii") + bytes([array.ndim])
            + np.asarray(array.shape, dtype="<u8").tobytes() + array.tobytes(order="C"))


def fingerprint(*parts):
    """Versioned reproducible FNV-1a64 checksum, not a provenance signature.

    Exact arrays are also compared; checksum collisions cannot authorize a
    mismatched mesh. Framing removes ambiguity between concatenated parts.
    """
    value = 14695981039346656037
    for part in parts:
        for byte in len(part).to_bytes(8, "little") + part:
            value = ((value ^ byte)*1099511628211) & ((1 << 64)-1)
    return f"fnv1a64:{value:016x}"


def snapshot_hashes(nodes, triangles, temperature):
    """(mesh_hash, temperature_hash, snapshot_hash) of a snapshot's canonical arrays.

    The framing byte strings are those of schema version 1 (metres and Kelvin), unchanged
    since the snapshot was introduced: simcase saves these hashes.
    """
    p, t, temp = payload(nodes), payload(triangles), payload(temperature)
    return (fingerprint(b"mesh-v1|m", p, t),
            fingerprint(b"temperature-v1|K", temp),
            fingerprint(b"temperature-snapshot-v1|nodal-P1|m|K", p, t, temp))


def verify_snapshot(snapshot, p, t):
    """Refuse a snapshot that is not a valid, unmodified TemperatureSnapshot of the nodes p and triangles t."""
    from .thermoelasticity import TemperatureSnapshot
    if not isinstance(snapshot, TemperatureSnapshot):
        raise ValueError("temperature_snapshot must be a TemperatureSnapshot from freeze_temperature")
    units = getattr(snapshot, "units", None)
    if snapshot.schema_version != 1 or not hasattr(units, "keys") or dict(units) != SNAPSHOT_UNITS:
        raise ValueError("snapshot schema/units must be nodal-P1 v1, metres and Kelvin")
    for value, dtype in ((snapshot.nodes, "<f8"), (snapshot.triangles, "<i8"),
                          (snapshot.temperature, "<f8")):
        if not isinstance(value, np.ndarray) or value.dtype != np.dtype(dtype) or value.flags.writeable:
            raise ValueError("snapshot arrays lost their immutable canonical representation")
        base = value
        while isinstance(base, np.ndarray):
            base = base.base
        if not isinstance(base, bytes):
            raise ValueError("snapshot arrays must retain their immutable bytes backing")
    if (snapshot.nodes.shape != p.shape or snapshot.triangles.shape != t.shape
            or snapshot.temperature.shape != (len(p),)
            or not np.all(np.isfinite(snapshot.temperature)) or np.any(snapshot.temperature < 0)):
        raise ValueError("invalid snapshot shape or absolute-temperature domain")
    expected = snapshot_hashes(snapshot.nodes, snapshot.triangles, snapshot.temperature)
    if expected != (snapshot.mesh_hash, snapshot.temperature_hash, snapshot.snapshot_hash):
        raise ValueError("snapshot hash mismatch: snapshot data or metadata was modified")
    current_p, current_t = np.asarray(p, dtype="<f8"), np.asarray(t, dtype="<i8")
    current_hash = fingerprint(b"mesh-v1|m", payload(current_p), payload(current_t))
    if (current_hash != snapshot.mesh_hash or not np.array_equal(p, snapshot.nodes)
            or not np.array_equal(t, snapshot.triangles)):
        raise ValueError("stale or mismatched mesh: coordinates, units/scale, connectivity or order changed")
