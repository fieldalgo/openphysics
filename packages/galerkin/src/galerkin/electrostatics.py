# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""2D electrostatics with conductors as node sets and a Maxwell capacitance matrix.

Solves ``-div(eps0 eps_r grad V) = rho`` on conforming P1 triangles per unit
length along z; see docs/packages/galerkin/electrostatics.md for the SI
contract. Conductors are node sets held at a potential (zero-thickness traces
are interior node lines), the exterior boundary away from a conductor is
insulated (zero normal D) and conductor charges are read from the assembled
reactions, so the energy and charge forms of the capacitance agree to solver
precision and are checked against each other.

The relative permittivity (scalar or region table), conductor potentials,
reference potentials and the charge density may be JAX or PyTorch values; the
results are then in that library and carry derivatives. A complex permittivity
``eps' (1 - j tan d)`` with ``Im <= 0`` is accepted on the NumPy path only.
"""
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from scipy.constants import epsilon_0

from .materials import element_values, region_index, region_property
from .mesh import Mesh
from .coupling import Field
from .postprocess import element_gradient
from .core import forms, kernels
from .core import solve as core_solve
from .core.backend import (Backend, backend_of, is_live, lift, live_namespace, namespace,
                           require_float64, scatter_add, to_numpy)
from .core.checks import readonly_copy, real_value
from .core.sparse import CooMatrix
from .core.triangles import triangle_geometry

__all__ = ["ElementPermittivity", "ElectrostaticsResult", "solve_electrostatics",
           "capacitance_matrix"]

_MESH_MISMATCH = "element permittivity mesh geometry, ordering or regions do not match"
_ROUTE_TOLERANCE = 1e-10


@dataclass(frozen=True, init=False)
class ElementPermittivity:
    """Positive finite relative permittivity per element, bound to an exact mesh geometry and order.

    The values are held in an element ``galerkin.coupling.Field`` (unit ``"1"``);
    they are real, so a lossy dielectric is given as a scalar or region table.
    """
    _field: Field

    def __init__(self, mesh, values):
        field = Field(mesh, values, location="element", unit="1", name="element permittivity")
        if np.any(field.values <= 0):
            raise ValueError("element permittivity must be strictly positive")
        object.__setattr__(self, "_field", field)

    @property
    def values(self):
        return self._field.values

    def on_mesh(self, mesh):
        return self._field.on_mesh(mesh, message=_MESH_MISMATCH)


@dataclass(frozen=True)
class ElectrostaticsResult:
    """Nodal volts, element V/m and C/m², and per-unit-length charges (C/m) and energy (J/m).

    Arrays are independent read-only snapshots in the returned mesh's order (or
    JAX/PyTorch arrays carrying derivatives). ``reaction`` is the charge at
    conductor nodes only, never at reference-potential gauges; ``charge`` sums
    it per conductor (``"ground"`` included when a ground was given). With a
    complex permittivity the potential, fields, charges and energy are complex.
    """
    mesh: Mesh
    potential: np.ndarray
    electric_field: np.ndarray
    displacement: np.ndarray
    relative_permittivity: np.ndarray
    energy_per_length: float
    load: np.ndarray
    reaction: np.ndarray
    residual: np.ndarray
    conductors: dict
    charge: dict
    total_free_charge: float


def _snapshot(mesh):
    copy = Mesh(mesh.nodes.copy(), mesh.triangles.copy(),
                {k: v.copy() for k, v in mesh.boundary.items()},
                {k: v.copy() for k, v in mesh.boundary_edges.items()},
                None if mesh.regions is None else mesh.regions.copy(), mesh.region_names)
    for a in [copy.nodes, copy.triangles, copy.regions,
              *copy.boundary.values(), *copy.boundary_edges.values()]:
        if a is not None:
            a.flags.writeable = False
    return copy


def _frozen(value):
    """A read-only NumPy copy; a JAX or PyTorch result is returned as it is."""
    return value if is_live(value) else readonly_copy(value)


def _number(value):
    """A 0-d NumPy result as a Python float or complex; a live value as it is."""
    if is_live(value):
        return value
    value = np.asarray(value)
    return complex(value) if value.dtype.kind == "c" else float(value)


def _is_index(key):
    return isinstance(key, (int, np.integer)) and not isinstance(key, (bool, np.bool_))


# -- permittivity ---------------------------------------------------------------

def _permittivity_scalar(value, label):
    """One relative permittivity: float, complex with Im <= 0, or a live float64 0-d array."""
    if is_live(value):
        xp = namespace(value)
        if xp.isdtype(value.dtype, "complex floating"):
            raise TypeError(f"{label}: a complex permittivity is computed on NumPy only; "
                            "a JAX or PyTorch permittivity must be real")
        if tuple(value.shape) != ():
            raise ValueError(f"{label} must be a scalar")
        numbers = to_numpy(value)
        if not np.isfinite(numbers) or not numbers > 0:
            raise ValueError(f"{label} must be a finite real scalar > 0")
        require_float64(xp, label)
        return xp.astype(value, xp.float64)
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{label} must not be a boolean")
    a = np.asarray(value)
    if a.shape != () or a.dtype.kind not in "iufc" or not np.isfinite(a):
        raise ValueError(f"{label} must be a finite scalar with Re > 0 and Im <= 0")
    if a.dtype.kind == "c":
        c = complex(a)
        if not c.real > 0 or c.imag > 0:
            raise ValueError(f"{label} must have Re > 0 and Im <= 0 (eps' (1 - j tan d))")
        return c
    f = float(a)
    if not f > 0:
        raise ValueError(f"{label} must be a finite scalar with Re > 0 and Im <= 0")
    return f


def _relative_permittivity(mesh, value):
    """(M,) relative permittivity: NumPy float64 or complex128, or a live float64 array."""
    count = len(mesh.triangles)
    if isinstance(value, ElementPermittivity):
        return value.on_mesh(mesh)
    if isinstance(value, Mapping):
        regions, names = region_index(mesh)
        unknown = [k for k in value if k not in names]
        missing = [n for n in names if n not in value]
        if unknown or missing:
            raise ValueError("permittivity regions must match mesh.region_names exactly; "
                             f"missing {missing}, unknown {unknown}")
        entries = [_permittivity_scalar(value[n], f"permittivity in region {n!r}") for n in names]
        if any(is_live(e) for e in entries):
            xp = live_namespace(*entries)
            return xp.stack([lift(xp, e, xp.float64) for e in entries])[regions]
        return np.array(entries)[regions]
    scalar = _permittivity_scalar(value, "permittivity")
    if is_live(scalar):
        return namespace(scalar).broadcast_to(scalar, (count,))
    return np.broadcast_to(np.asarray(scalar), (count,))


def _stiffness(mesh, eps_r, xp):
    """``int eps0 eps_r grad phi_j . grad phi_i`` as a CooMatrix in ``xp``, and its NumPy CSR."""
    cells = np.asarray(mesh.triangles)
    stiffness = forms.matrix(cells, cells, kernels.p1_stiffness(mesh, lift(xp, eps_r) * epsilon_0),
                             (len(mesh.nodes), len(mesh.nodes)))
    numbers = CooMatrix(stiffness.rows, stiffness.cols, to_numpy(stiffness.values),
                        stiffness.shape).to_scipy()
    if not np.all(np.isfinite(numbers.data)):
        raise ValueError("assembled electrostatic stiffness exceeds floating-point range")
    return stiffness, numbers


# -- conductors, gauges and charge ----------------------------------------------

def _node_set(nodes, n, label):
    idx = np.asarray(nodes)
    if not idx.size:
        raise ValueError(f"{label} has no mesh nodes")
    if idx.dtype.kind not in "iu" or idx.ndim > 1:
        raise ValueError(f"{label} must be a one-dimensional set of integer node indices")
    idx = np.unique(idx.reshape(-1))
    if idx.min() < 0 or idx.max() >= n:
        raise ValueError(f"{label} refers to nodes outside the mesh")
    return idx.astype(int)


def _volts(value, label):
    v = real_value(value, label)
    if tuple(v.shape) != ():
        raise ValueError(f"{label} must be scalar volts")
    return v if is_live(v) else float(v)


def _conductors(conductors, ground, n):
    """``{name: (sorted node ids, volts)}``: names for node sets, node ids for a Dirichlet mapping."""
    if not isinstance(conductors, Mapping):
        raise ValueError("conductors must map names to (node ids, volts) pairs "
                         "or node indices to volts")
    keys = list(conductors)
    sets = {}
    if keys and all(isinstance(k, str) for k in keys):
        for name, item in conductors.items():
            try:
                nodes, volts = item
            except (TypeError, ValueError):
                raise ValueError(f"conductor {name!r} must be a (node ids, volts) pair") from None
            sets[name] = (_node_set(nodes, n, f"conductor {name!r}"),
                          _volts(volts, f"conductor {name!r} potential"))
    elif keys and all(_is_index(k) for k in keys):
        for node, volts in conductors.items():
            sets[int(node)] = (_node_set([node], n, f"conductor node {int(node)}"),
                               _volts(volts, f"conductor node {int(node)} potential"))
    elif keys:
        raise ValueError("conductors must be either all names with (node ids, volts) pairs "
                         "or all node indices with volts")
    if ground is not None:
        if "ground" in sets:
            raise ValueError("a conductor named 'ground' and the ground argument cannot both be given")
        sets["ground"] = (_node_set(ground, n, "ground"), 0.0)
    seen = np.zeros(n, dtype=bool)
    for name, (nodes, _) in sets.items():
        if np.any(seen[nodes]):
            raise ValueError(f"conductor {name!r} shares mesh nodes with another conductor "
                             "or the ground; conductors must not touch")
        seen[nodes] = True
    return sets


def _gauges(reference_potential, n):
    if reference_potential is None:
        return {}
    if not isinstance(reference_potential, Mapping):
        raise ValueError("reference_potential must map node indices to scalar volts")
    out = {}
    for node, value in reference_potential.items():
        if not _is_index(node) or not 0 <= node < n:
            raise ValueError("reference_potential node indices must be integers within the mesh")
        out[int(node)] = _volts(value, "reference_potential")
    return out


def _charge_load(mesh, charge_density):
    """Consistent P1 load ``int rho phi_i`` (C/m), centroid rule, NumPy or live."""
    count = len(mesh.triangles)
    if callable(charge_density):
        centroid = mesh.nodes[mesh.triangles].mean(axis=1)
        rho = real_value(charge_density(centroid[:, 0], centroid[:, 1]), "charge_density")
        if tuple(rho.shape) not in ((), (count,)):
            raise ValueError("charge_density callback must return a scalar or one value per triangle")
    else:
        rho = region_property(mesh, charge_density, "charge_density", live=True)
    rho = element_values(mesh, rho)
    cells = np.asarray(mesh.triangles)
    return forms.vector(cells, kernels.p1_load(mesh, rho), len(mesh.nodes), order="columns")


# -- solve ----------------------------------------------------------------------

def solve_electrostatics(mesh, *, permittivity, conductors, ground=None, charge_density=0.0,
                         reference_potential=None):
    """Solve ``-div(eps0 eps_r grad V) = rho`` on a conforming 2D P1 mesh in metres.

    permittivity: relative permittivity eps_r: a scalar, an exact region-name
        table or a mesh-bound ElementPermittivity. Real values are > 0; complex
        values ``eps' (1 - j tan d)`` need Re > 0 and Im <= 0 and are accepted
        on the NumPy path only. Bare element arrays remain invalid.
    conductors: ``{name: (node ids, volts)}`` node sets (any mesh nodes, so a
        zero-thickness trace is an interior node line), or a plain
        ``{node: volts}`` Dirichlet mapping whose charges are then reported
        per node. Conductors must not share nodes.
    ground: node ids held at 0 V, reported as conductor ``"ground"``.
    charge_density: free charge rho in C/m³: scalar, region table or a callback
        ``(x, y) -> rho`` evaluated at the triangle centroids.
    reference_potential: node -> volts, exactly one gauge per connected
        component without a conductor; such a component must carry zero net
        free charge to 1e-12 relative to ``sum(abs(load))``.
    Exterior boundary not on a conductor is insulated (zero normal D).
    """
    p, t, area, boundary, count, labels = triangle_geometry(mesh)
    n = len(p)
    eps_r = _relative_permittivity(mesh, permittivity)
    sets = _conductors(conductors, ground, n)
    gauges = _gauges(reference_potential, n)
    load = _charge_load(mesh, charge_density)
    prescribed = {int(node): volts for nodes, volts in sets.values() for node in nodes}
    for node in gauges:
        if node in prescribed:
            raise ValueError("reference_potential is unnecessary on a conductor node")
    anchored = np.zeros(count, dtype=bool)
    offsets = [0.0]*count
    for node, value in prescribed.items():
        if not anchored[labels[node]]:
            offsets[labels[node]] = value
            anchored[labels[node]] = True
    xp = live_namespace(eps_r, load, *prescribed.values(), *gauges.values())
    load_numbers = to_numpy(load)
    if not np.all(np.isfinite(load_numbers)):
        raise ValueError("assembled free charge exceeds floating-point range")
    for component in range(count):
        selected = [node for node in gauges if labels[node] == component]
        if anchored[component]:
            if selected:
                raise ValueError("reference_potential is unnecessary on a conductor component")
        else:
            nodes = labels == component
            if abs(np.sum(load_numbers[nodes])) > 1e-12*np.sum(np.abs(load_numbers[nodes])):
                raise ValueError(f"incompatible net free charge on component {component} "
                                 "without a conductor")
            if len(selected) != 1:
                raise ValueError("exactly one reference_potential node is required per component "
                                 "without a conductor")
            offsets[component] = gauges[selected[0]]
    if any(is_live(o) for o in offsets):
        offsets = xp.stack([lift(xp, o, xp.float64) for o in offsets])
    else:
        offsets = lift(xp, np.array(offsets, dtype=float))
    stiffness, K_numbers = _stiffness(mesh, eps_r, xp)
    bc = {(node,): value-offsets[labels[node]]
          for node, value in (prescribed | gauges).items()}
    try:
        increment = core_solve.solve_dirichlet(stiffness, lift(xp, load), bc)
    except (RuntimeError, ValueError) as exc:
        raise ValueError("singular or ill-conditioned electrostatic system") from exc
    potential = increment+offsets[labels]
    residual = stiffness.matvec(increment)-lift(xp, load)
    fixed = np.array(sorted(prescribed), dtype=int)
    free = np.setdiff1d(np.arange(n), fixed)  # Includes gauges: no hidden charge.
    increment_numbers, residual_numbers = to_numpy(increment), to_numpy(residual)
    scale = max(np.max(abs(K_numbers)@abs(increment_numbers)+abs(load_numbers)), np.finfo(float).tiny)
    if not np.all(np.isfinite(to_numpy(potential))) or not np.all(np.isfinite(residual_numbers)):
        raise ValueError("nonfinite electrostatic solution or residual")
    if len(free) and np.max(abs(residual_numbers[free])) > 1e-10*scale:
        raise ValueError("electrostatic solve failed the normalized free residual tolerance")
    reaction = np.zeros(n, dtype=residual_numbers.dtype)
    reaction[fixed] = residual_numbers[fixed]
    for component in range(count):
        nodes = labels == component
        balance_scale = max(np.sum(abs(reaction[nodes])+abs(load_numbers[nodes])), np.finfo(float).tiny)
        if abs(np.sum(reaction[nodes])+np.sum(load_numbers[nodes])) > 1e-10*balance_scale:
            raise ValueError("electrostatic solve failed component charge balance")
    if is_live(residual):
        reaction = scatter_add(xp, n, fixed, residual[fixed])
    electric = -element_gradient(mesh, increment)
    eps_abs = lift(xp, eps_r)*epsilon_0
    displacement = eps_abs[:, None]*electric
    energy = 0.5*(increment@(residual+lift(xp, load)))
    total = xp.sum(lift(xp, load))
    if not all(np.all(np.isfinite(to_numpy(v))) for v in (electric, displacement, energy)):
        raise ValueError("electrostatic fields or energy exceed floating-point range")
    charge = {name: _number(xp.sum(reaction[nodes])) for name, (nodes, _) in sets.items()}
    conductor_nodes = {name: readonly_copy(nodes) for name, (nodes, _) in sets.items()}
    return ElectrostaticsResult(
        _snapshot(mesh), *map(_frozen, (potential, electric, displacement, eps_r)),
        _number(energy), *map(_frozen, (load, reaction, residual)), conductor_nodes, charge,
        _number(total))


# -- capacitance ----------------------------------------------------------------

def capacitance_matrix(mesh, *, permittivity, conductors, ground):
    """Maxwell capacitance matrix (F/m) of the named conductors against ``ground``.

    conductors: ``{name: node ids}`` in matrix order; ground: node ids at 0 V
    (required, nonempty). Column j is the solve with conductor j at 1 V and
    every other conductor and the ground at 0 V; entry (i, j) is the charge on
    conductor i (the reaction sum). The energy form ``V_i^T K V_j`` is computed
    as well and must agree with it to ``1e-10`` of the largest charge entry
    (ValueError otherwise); the charge matrix is then symmetrised,
    ``(C + C^T)/2``, and returned. A complex permittivity ``eps' (1 - j tan d)``
    (NumPy only) gives a complex matrix whose loss matrix ``-Im C`` is positive
    semidefinite (negative diagonal of ``Im C``); a live real
    permittivity (JAX or PyTorch) gives a matrix carrying its derivative.
    """
    if (not isinstance(conductors, Mapping) or not conductors
            or not all(isinstance(k, str) for k in conductors)):
        raise ValueError("conductors must map at least one conductor name to its node ids")
    if "ground" in conductors:
        raise ValueError("'ground' is the name of the ground argument; rename that conductor")
    if ground is None:
        raise ValueError("capacitance_matrix needs ground node ids")
    names = list(conductors)
    results = []
    for excited in names:
        spec = {name: (nodes, 1.0 if name == excited else 0.0) for name, nodes in conductors.items()}
        results.append(solve_electrostatics(mesh, permittivity=permittivity, conductors=spec,
                                            ground=ground))
    eps_r = _relative_permittivity(mesh, permittivity)
    xp = live_namespace(eps_r)
    stiffness, K_numbers = _stiffness(mesh, eps_r, xp)
    potentials = xp.stack([lift(xp, r.potential) for r in results], axis=1)
    if backend_of(xp) is Backend.NUMPY:
        products = K_numbers@potentials
    else:
        products = xp.stack([stiffness.matvec(potentials[:, j]) for j in range(len(names))], axis=1)
    energy = xp.einsum("ni,nj->ij", potentials, products)
    charge = xp.stack([xp.stack([lift(xp, xp.asarray(r.charge[name])) for name in names])
                       for r in results], axis=1)
    energy_numbers, charge_numbers = to_numpy(energy), to_numpy(charge)
    scale = max(np.max(np.abs(charge_numbers)), np.finfo(float).tiny)
    if np.max(np.abs(energy_numbers-charge_numbers)) > _ROUTE_TOLERANCE*scale:
        raise ValueError("capacitance energy and charge routes disagree beyond 1e-10 of the "
                         "largest entry")
    return 0.5*(charge+xp.matrix_transpose(charge))
