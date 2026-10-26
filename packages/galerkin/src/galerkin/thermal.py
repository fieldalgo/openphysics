# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady isotropic heat conduction on conforming P1 triangles.

Conductivity is scalar or piecewise constant on named regions (galerkin.materials).
Heat sources may also be mesh-bound ElementHeatSource values or coordinate callbacks. Import this submodule explicitly. See
docs/packages/galerkin/thermal_steady2d.md and
docs/packages/galerkin/multimaterial.md for SI units, boundary signs and
validation limits. No other physics module is required.
"""
from dataclasses import dataclass
from typing import Mapping

import numpy as np
from scipy.sparse import coo_matrix

from .mesh import Mesh
from .heat_source import ElementHeatSource
from .materials import is_per_region, region_property
from .assembly import assemble_stiffness
from .postprocess import element_gradient
from .solver import solve_dirichlet
from .core.boundary import scalar_boundary_samples
from .core.checks import real_array
from .core.loads import source_load
from .core.triangles import triangle_geometry


def _boundary_system(samples, n, labels, anchors, constrained):
    # Pick a useful absolute offset for Robin-only components. Any positive
    # sampled h anchors discretely; no unit-dependent artificial cutoff.
    for kind, edges, shape, weights, values in samples:
        if kind != "convection":
            continue
        h, ambient = values
        for e, q in np.argwhere(h > 0):
            c = labels[edges[e, 0]]
            if not constrained[c]:
                anchors[c] = ambient[e, q]
                constrained[c] = True
    G, B, shifted_B = np.zeros((3, n))
    rows, cols, entries = [], [], []
    for kind, edges, shape, weights, values in samples:
        if kind == "outward_flux":
            local = np.einsum("eq,qa,eq->ea", weights, shape, values[0])
            np.add.at(G, edges.ravel(), local.ravel())
        else:
            h, ambient = values
            local_h = np.einsum("eq,qa,qb,eq->eab", weights, shape, shape, h)
            local_b = np.einsum("eq,qa,eq->ea", weights, shape, h*ambient)
            local_shift = np.einsum("eq,qa,eq->ea", weights, shape,
                                    h*(ambient-anchors[labels[edges[:, 0]]][:, None]))
            np.add.at(B, edges.ravel(), local_b.ravel())
            np.add.at(shifted_B, edges.ravel(), local_shift.ravel())
            rows.extend(np.repeat(edges, 2, axis=1).ravel())
            cols.extend(np.tile(edges, (1, 2)).ravel())
            entries.extend(local_h.ravel())
    H = coo_matrix((entries, (rows, cols)), shape=(n, n)).tocsr()
    return H, G, B, shifted_B


@dataclass
class SteadyHeatResult:
    """temperature (N,) K, heat_flux (M,2) W/m^2, nodal forces (N,) W/m.

    reaction is residual=(K+H)*T-system_rhs on fixed nodes, zero on free nodes.
    Positive reaction injects heat; the Dirichlet thermostat outward contribution
    is -reaction. Total outward heat also includes prescribed and convective terms.
    All nodal heat rates are per unit out-of-plane thickness, not watts.
    """
    temperature: np.ndarray
    heat_flux: np.ndarray
    load: np.ndarray
    reaction: np.ndarray
    residual: np.ndarray
    prescribed_outward_load: np.ndarray | None = None
    ambient_load: np.ndarray | None = None
    convective_outward: np.ndarray | None = None
    system_rhs: np.ndarray | None = None


def solve_steady_heat(mesh, *, conductivity, dirichlet, heat_source=0.0,
                      outward_flux=None, convection=None):
    """Solve -div(k grad T)=Q with Dirichlet, outward flux and Robin data.

    conductivity is finite scalar k>0 in W/(m K), or {region name: k} with
    every mesh.region_names entry. heat_source is scalar Q, {region name: Q},
    a callback receiving (Q,2) metre coordinates and returning (Q,) W/m^3,
    or ElementHeatSource(mesh, values) with (M,) W/m^3 in exact cell order.
    dirichlet maps exterior integer node indices to scalar temperatures in K;
    every disconnected component requires Dirichlet or positive Robin support.
    outward_flux maps edge tags to g; convection maps tags to (h, ambient).
    q.n = g+h*(T-ambient), h>=0. Boundary scalars or callbacks
    (points_m, outward_normals)->(Q,) use W/m^2, W/(m^2 K), K respectively.
    Untagged natural edges are insulated. See docs/packages/galerkin/thermal_flux_robin.md.
    """
    if not is_per_region(conductivity):
        k = real_array(conductivity, "conductivity")
        if k.shape != () or k <= 0:
            raise ValueError("conductivity must be a finite scalar > 0")
        k = float(k)
    p, t, area, boundary, count, labels = triangle_geometry(mesh)
    if is_per_region(conductivity):
        k = region_property(mesh, conductivity, "conductivity", positive=True)
    if not isinstance(dirichlet, Mapping):
        raise ValueError("dirichlet must map exterior node indices to temperatures in K")
    prescribed = {}
    anchors = np.zeros(count)
    constrained = np.zeros(count, dtype=bool)
    for node, value in dirichlet.items():
        if isinstance(node, (bool, np.bool_)) or not isinstance(node, (int, np.integer)):
            raise ValueError("Dirichlet node indices must be integers")
        if not 0 <= node < len(p) or node not in boundary:
            raise ValueError("Dirichlet node must lie on the exterior mesh boundary")
        value = real_array(value, "Dirichlet temperature")
        if value.shape != ():
            raise ValueError("Dirichlet temperature must be scalar")
        prescribed[int(node)] = float(value)
        component = labels[node]
        if not constrained[component]:
            anchors[component] = value
            constrained[component] = True
    samples = scalar_boundary_samples(mesh, p, t, prescribed, outward_flux, convection)
    H, G, B, shifted_B = _boundary_system(samples, len(p), labels, anchors, constrained)
    missing = np.flatnonzero(~constrained)
    if len(missing):
        raise ValueError(f"each connected component requires Dirichlet or positive Robin data; missing {missing.tolist()}")
    stiffness = assemble_stiffness(mesh, k)
    load = source_load(mesh, p, t, area, heat_source)
    system = stiffness+H
    rhs = load+B-G
    shifted_rhs = load+shifted_B-G
    if not all(np.all(np.isfinite(a)) for a in
               (stiffness.data, H.data, load, G, B, shifted_B, rhs, shifted_rhs)):
        raise ValueError("assembled heat system exceeds floating-point range")
    shifted_bc = {(node,): value-anchors[labels[node]] for node, value in prescribed.items()}
    try:
        increment = solve_dirichlet(system, shifted_rhs, shifted_bc)
    except RuntimeError as exc:
        raise ValueError("singular or ill-conditioned constrained heat system") from exc
    temperature = increment+anchors[labels]
    # K annihilates constants; H does not. shifted_B integrates h*(ambient-offset).
    # Evaluate derivatives and convection before restoring absolute temperature.
    convective = H@increment-shifted_B
    residual = stiffness@increment+convective-load+G
    flux = -(k[:, None] if np.ndim(k) else k)*element_gradient(mesh, increment)
    if not all(np.all(np.isfinite(a)) for a in (temperature, residual, flux, convective)):
        raise ValueError("nonfinite heat solution, residual or heat flux")
    fixed = np.array(sorted(prescribed), dtype=int)
    free = np.setdiff1d(np.arange(len(p)), fixed)
    scale = max(np.linalg.norm(abs(system)@abs(increment)+abs(shifted_rhs), np.inf),
                np.finfo(float).tiny)
    if len(free) and np.linalg.norm(residual[free], np.inf) > 1e-10*scale:
        raise ValueError("heat solve failed the normalized free residual tolerance")
    reaction = np.zeros(len(p))
    reaction[fixed] = residual[fixed]
    for component in range(count):
        nodes = labels == component
        balance_scale = max(sum(np.sum(abs(a[nodes])) for a in
                                (load, reaction, G, convective)), np.finfo(float).tiny)
        if abs(np.sum((load+reaction-G-convective)[nodes])) > 1e-10*balance_scale:
            raise ValueError("heat solve failed the normalized component heat balance tolerance")
    return SteadyHeatResult(temperature, flux, load, reaction, residual,
                            G, B, convective, rhs)
