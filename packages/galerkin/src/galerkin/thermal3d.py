# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady heat conduction on tetrahedral meshes: P1 elements, Dirichlet and insulated faces.

-div(k grad T) = Q on a ``Mesh3D`` of the format in
docs/packages/galerkin/mesh3d_format.md. k is one conductivity or one per named
region, Q one source, one per region or a function of the tetrahedron
centroids; temperatures are prescribed on nodes (``dirichlet_from_faces`` builds
the map from face tags), and every other face is insulated (the natural
condition). The 3D counterpart of ``galerkin.thermal`` without flux or Robin
data, and of the layered conduction check in tests/meshine/test_extrude.py.

The P1 source load is assembled here: with Q constant on a tetrahedron the
exact load is Q V / 4 on each of its four nodes. Flux is -k grad T per
tetrahedron (constant). Nodal heat rates are watts: ``load`` the source load,
``reaction`` the residual K T - load on the fixed nodes (positive injects
heat into the domain), ``residual`` K T - load everywhere. K annihilates
constants, so sum(load) + sum(reaction) = 0 up to roundoff; ``balance_error``
is that sum relative to the total absolute nodal heat. NumPy only.
"""
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

from .assembly3d import assemble_stiffness_3d
from .core.checks import contains_live, finite_scalar
from .core.tets import tet_gradients
from .mesh3d import Mesh3D
from .solver import solve_dirichlet

_RESIDUAL_TOLERANCE = 1e-10
_BALANCE_TOLERANCE = 1e-10


@dataclass
class SteadyHeat3DResult:
    """temperature (N,) K, heat_flux (T, 3) W/m^2, load/reaction/residual (N,) W.

    conductivity and heat_source are the per-tetrahedron values used, in
    W/(m K) and W/m^3; balance_error is |sum(load) + sum(reaction)| over the
    total absolute nodal heat (<= 1e-10 or the solve raises).
    """
    temperature: np.ndarray
    heat_flux: np.ndarray
    load: np.ndarray
    reaction: np.ndarray
    residual: np.ndarray
    conductivity: np.ndarray
    heat_source: np.ndarray
    balance_error: float
    dirichlet_nodes: np.ndarray


def _refuse_live(value, name):
    if contains_live(value) or (isinstance(value, Mapping)
                                and any(contains_live(v) for v in value.values())):
        raise TypeError(f"{name}: solve_steady_heat_3d runs on NumPy and carries no derivative; "
                        "pass NumPy numbers")


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
        _refuse_live(values, "heat_source")
        values = np.asarray(values, dtype=float)
        if values.shape != (mesh.num_tets,) or not np.all(np.isfinite(values)):
            raise ValueError("heat_source callback must return finite (T,) W/m^3 at the centroids")
        return values
    return _per_region(mesh, heat_source, "heat_source", positive=False)


def source_load_3d(mesh: Mesh3D, heat_source) -> np.ndarray:
    """(N,) W nodal load of a per-tetrahedron (T,) W/m^3 source: Q V / 4 per node."""
    values = np.asarray(heat_source, dtype=float)
    if values.shape != (mesh.num_tets,):
        raise ValueError("heat_source must hold one value per tetrahedron")
    local = (values * mesh.volumes() / 4.0)[:, None] * np.ones((1, 4))
    load = np.zeros(mesh.num_nodes)
    np.add.at(load, mesh.tets, local)
    return load


def dirichlet_from_faces(mesh: Mesh3D, temperatures: Mapping) -> dict:
    """{node: T} from {face tag: T}; a node on two tags must get the same value."""
    if not isinstance(temperatures, Mapping):
        raise ValueError("temperatures must map face tags to Kelvin values")
    out = {}
    for tag, value in temperatures.items():
        if tag not in mesh.tagged_faces:
            raise ValueError(f"unknown face tag {tag!r}; this mesh carries {sorted(mesh.tagged_faces)}")
        _refuse_live(value, f"temperature on {tag!r}")
        value = finite_scalar(value, f"temperature on {tag!r}")
        for node in np.unique(mesh.tagged_faces[tag]).tolist():
            if node in out and out[node] != value:
                raise ValueError(f"node {node} lies on faces with different temperatures "
                                 f"({out[node]!r} and {value!r} on {tag!r})")
            out[node] = value
    return out


def solve_steady_heat_3d(mesh: Mesh3D, *, conductivity, dirichlet, heat_source=0.0) -> SteadyHeat3DResult:
    """Solve -div(k grad T) = Q with prescribed nodal temperatures; other faces insulated.

    mesh: ``galerkin.Mesh3D`` in metres (``from_mesher`` of a meshine or gmshio
        mesh, or ``box_mesh``). Face tags are needed only by ``dirichlet_from_faces``.
    conductivity: finite k > 0 in W/(m K), or {region name: k} over every
        ``mesh.region_names`` entry.
    dirichlet: {node index: temperature K}; every node must lie on the exterior
        boundary and every connected component of the mesh needs one.
    heat_source: Q in W/m^3, {region name: Q}, or a callable taking the (T, 3)
        tetrahedron centroids (read-only) and returning (T,) values.

    NumPy only: JAX or PyTorch values raise TypeError. Raises ValueError on
    invalid input, a singular system, or a failed residual or heat-balance check.
    """
    if not isinstance(mesh, Mesh3D):
        raise TypeError("solve_steady_heat_3d takes a galerkin.Mesh3D (use from_mesher)")
    k = _per_region(mesh, conductivity, "conductivity", positive=True)
    source = _source(mesh, heat_source)
    if not isinstance(dirichlet, Mapping):
        raise ValueError("dirichlet must map exterior node indices to temperatures in K")
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

    stiffness = assemble_stiffness_3d(mesh, k).tocsr()
    load = source_load_3d(mesh, source)
    if not (np.all(np.isfinite(stiffness.data)) and np.all(np.isfinite(load))):
        raise ValueError("assembled heat system exceeds floating-point range")
    try:
        temperature = solve_dirichlet(stiffness, load,
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
    gradients, _ = tet_gradients(mesh)
    flux = -k[:, None] * np.einsum("tnd,tn->td", gradients, temperature[mesh.tets])
    return SteadyHeat3DResult(temperature, flux, load, reaction, residual, k, source,
                              balance_error, fixed)
