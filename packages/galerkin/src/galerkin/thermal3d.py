# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady heat conduction on tetrahedral meshes: P1 elements, Dirichlet and insulated faces.

-div(k grad T) = Q on a ``Mesh3D`` of the format in
docs/packages/galerkin/mesh3d_format.md. k is one thermal conductivity or one per
named region, Q one heat source density, one per region or a function of the
tetrahedron centroids; temperatures are prescribed on nodes
(``galerkin.kernels.dirichlet_from_faces`` builds the map from face tags), and every
other face is insulated (the natural condition). The 3D counterpart of ``galerkin.thermal`` without flux or Robin
data, and of the layered conduction check in tests/meshine/test_extrude.py.

The P1 source load is assembled here: with Q constant on a tetrahedron the
exact load is Q V / 4 on each of its four nodes. Flux is -k grad T per
tetrahedron (constant). Nodal heat rates are watts (totals, not per depth):
``generated_heat_rate`` the source load, ``reaction_heat_rate`` the residual
K T - load on the fixed nodes (positive injects heat into the domain),
``residual_heat_rate`` K T - load everywhere. K annihilates constants, so
sum(generated) + sum(reaction) = 0 up to roundoff; ``relative_conservation_residual``
is that sum relative to the total absolute nodal heat. NumPy only.

The public solver takes keyword-only SI quantities under registry names. The source
load and the face-tag map are internal: they live in the package-private
``galerkin._heat_kernels`` and ``galerkin.kernels`` re-exports them as
``source_load_3d`` and ``dirichlet_from_faces``.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

from .assembly3d import assemble_stiffness_3d as _assemble_stiffness_3d
from .core.checks import finite_scalar
from .core.tets import tet_gradients as _tet_gradients
from .mesh3d import Mesh3D
from .solver import solve_dirichlet as _solve_dirichlet
from ._heat_kernels import refuse_live_3d as _refuse_live, source_load_3d as _source_load_3d
from ._public import ResultSurface, refuse_text

# Public names. The source load and face-tag map are internal: galerkin.kernels re-exports them.
__all__ = ["SteadyHeat3DResult", "solve_steady_heat_3d"]

_RESIDUAL_TOLERANCE = 1e-10
_BALANCE_TOLERANCE = 1e-10


@dataclass(frozen=True, eq=False)
class SteadyHeat3DResult(ResultSurface):
    """temperature (N,) K, heat_flux (T, 3) W/m^2, the generated, reaction and residual heat rates (N,) W.

    thermal_conductivity and heat_source_density are the per-tetrahedron values used,
    in W/(m K) and W/m^3; relative_conservation_residual is |sum(generated) +
    sum(reaction)| over the total absolute nodal heat (<= 1e-10 or the solve raises);
    prescribed_node_ids are the fixed nodes. Rates are totals (W): asking for a
    ``*_per_depth`` field raises AttributeError, which says why. ``.units`` maps every
    quantity field to its SI unit.
    """
    temperature: np.ndarray
    heat_flux: np.ndarray
    generated_heat_rate: np.ndarray
    reaction_heat_rate: np.ndarray
    residual_heat_rate: np.ndarray
    thermal_conductivity: np.ndarray
    heat_source_density: np.ndarray
    relative_conservation_residual: float
    prescribed_node_ids: np.ndarray

    BASIS = "3d"
    UNITS = MappingProxyType({"temperature": "K", "heat_flux": "W/m^2", "generated_heat_rate": "W",
                              "reaction_heat_rate": "W", "residual_heat_rate": "W",
                              "thermal_conductivity": "W/(m K)", "heat_source_density": "W/m^3",
                              "relative_conservation_residual": "1"})


def _per_region(mesh, value, label, *, positive):
    """(T,) float array from a scalar or {region name: scalar}."""
    _refuse_live(value, label)
    if isinstance(value, Mapping):
        if mesh.regions is None or mesh.region_names is None:
            raise ValueError(f"{label} per region needs mesh.regions and mesh.region_names")
        names = list(mesh.region_names)
        unknown = [k for k in value if k not in names]
        missing = [n for n in names if n not in value]
        if unknown or missing:
            raise ValueError(f"{label} regions must match mesh.region_names exactly; "
                             f"missing {missing}, unknown {unknown}")
        table = [finite_scalar(value[n], f"{label}[{n!r}]") for n in names]
        if positive and any(v <= 0 for v in table):
            raise ValueError(f"{label} must be > 0 in every region")
        return mesh.by_region(np.asarray(table, dtype=float))
    scalar = finite_scalar(value, label)
    if positive and scalar <= 0:
        raise ValueError(f"{label} must be a finite scalar > 0")
    return np.full(mesh.num_tets, scalar)


def _source(mesh, heat_source):
    """(T,) W/m^3: scalar, {region: Q} or a callable of the (T, 3) centroids."""
    if callable(heat_source) and not isinstance(heat_source, Mapping):
        centroids = mesh.nodes[mesh.tets].mean(axis=1)
        centroids.flags.writeable = False
        values = heat_source(centroids)
        _refuse_live(values, "heat_source_density")
        values = np.asarray(values, dtype=float)
        if values.shape != (mesh.num_tets,) or not np.all(np.isfinite(values)):
            raise ValueError("heat_source_density callback must return finite (T,) W/m^3 at the centroids")
        return values
    return _per_region(mesh, heat_source, "heat_source_density", positive=False)


def solve_steady_heat_3d(mesh: Mesh3D, *, thermal_conductivity, prescribed_temperature,
                         heat_source_density=None) -> SteadyHeat3DResult:
    """Solve -div(k grad T) = Q with prescribed nodal temperatures; other faces insulated.

    mesh: ``galerkin.Mesh3D`` in metres (``from_mesher`` of a meshine or gmshio
        mesh, or ``box_mesh``). Face tags are needed only by
        ``galerkin.kernels.dirichlet_from_faces``.
    thermal_conductivity: finite k > 0 in W/(m K), or {region name: k} over every
        ``mesh.region_names`` entry.
    prescribed_temperature: {node index: temperature K}; every node must lie on the
        exterior boundary and every connected component of the mesh needs one.
    heat_source_density: Q in W/m^3, {region name: Q}, or a callable taking the
        (T, 3) tetrahedron centroids (read-only) and returning (T,) values; None
        (the default) is no source.

    NumPy only: JAX or PyTorch values raise TypeError, and so does a str for a
    quantity (SI numbers only). Raises ValueError on invalid input, a singular
    system, or a failed residual or heat-balance check.
    """
    for name, value in (("thermal_conductivity", thermal_conductivity),
                        ("prescribed_temperature", prescribed_temperature),
                        ("heat_source_density", heat_source_density)):
        refuse_text(name, value)
    if not isinstance(mesh, Mesh3D):
        raise TypeError("solve_steady_heat_3d takes a galerkin.Mesh3D (use from_mesher)")
    k = _per_region(mesh, thermal_conductivity, "thermal_conductivity", positive=True)
    source = _source(mesh, 0.0 if heat_source_density is None else heat_source_density)
    dirichlet = prescribed_temperature
    if not isinstance(dirichlet, Mapping):
        raise ValueError("prescribed_temperature must map exterior node indices to temperatures in K")
    boundary = set(mesh.boundary_nodes().tolist())
    prescribed = {}
    for node, value in dirichlet.items():
        if isinstance(node, (bool, np.bool_)) or not isinstance(node, (int, np.integer)):
            raise ValueError("Dirichlet node indices must be integers")
        if not 0 <= node < mesh.num_nodes or int(node) not in boundary:
            raise ValueError(f"Dirichlet node {node} must lie on the exterior mesh boundary")
        _refuse_live(value, "Dirichlet temperature")
        prescribed[int(node)] = finite_scalar(value, "Dirichlet temperature")
    fixed = np.array(sorted(prescribed), dtype=int)
    pairs = mesh.tets[:, [[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3]]].reshape(-1, 2)
    graph = sp.coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])),
                          shape=(mesh.num_nodes,) * 2)
    count, labels = connected_components(graph, directed=False)
    anchored = np.zeros(count, dtype=bool)
    anchored[labels[fixed]] = True
    if not anchored.all():
        raise ValueError("each connected component of the mesh needs a Dirichlet node; "
                         f"components {np.flatnonzero(~anchored).tolist()} have none")

    stiffness = _assemble_stiffness_3d(mesh, k).tocsr()
    load = _source_load_3d(mesh, source)
    if not (np.all(np.isfinite(stiffness.data)) and np.all(np.isfinite(load))):
        raise ValueError("assembled heat system exceeds floating-point range")
    try:
        temperature = _solve_dirichlet(stiffness, load,
                                      {(node,): value for node, value in prescribed.items()})
    except (RuntimeError, ValueError) as exc:
        raise ValueError("singular or ill-conditioned constrained heat system") from exc
    residual = stiffness @ temperature - load
    if not (np.all(np.isfinite(temperature)) and np.all(np.isfinite(residual))):
        raise ValueError("nonfinite heat solution or residual")
    free = np.setdiff1d(np.arange(mesh.num_nodes), fixed)
    scale = max(float(np.linalg.norm(abs(stiffness) @ np.abs(temperature) + np.abs(load), np.inf)),
                np.finfo(float).tiny)
    if len(free) and np.linalg.norm(residual[free], np.inf) > _RESIDUAL_TOLERANCE * scale:
        raise ValueError("heat solve failed the normalized free residual tolerance")
    reaction = np.zeros(mesh.num_nodes)
    reaction[fixed] = residual[fixed]
    balance_scale = max(float(np.sum(np.abs(load)) + np.sum(np.abs(reaction))), np.finfo(float).tiny)
    balance_error = abs(float(np.sum(load) + np.sum(reaction))) / balance_scale
    if balance_error > _BALANCE_TOLERANCE:
        raise ValueError("heat solve failed the normalized heat balance tolerance")
    gradients, _ = _tet_gradients(mesh)
    flux = -k[:, None] * np.einsum("tnd,tn->td", gradients, temperature[mesh.tets])
    return SteadyHeat3DResult(temperature, flux, load, reaction, residual, k, source,
                              balance_error, fixed)
