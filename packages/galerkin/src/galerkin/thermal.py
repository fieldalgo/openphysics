# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady isotropic heat conduction on conforming P1 triangles.

Conductivity is scalar or piecewise constant on named regions (galerkin.materials).
Heat sources may also be mesh-bound ElementHeatSource values or coordinate callbacks. Import this submodule explicitly. See
docs/packages/galerkin/thermal_steady2d.md and
docs/packages/galerkin/multimaterial.md for SI units, boundary signs and
validation limits. No other physics module is required.

Conductivity, heat source, Dirichlet temperatures and boundary data may be JAX
or PyTorch values (callbacks may return them); the result arrays are then in
that library and carry derivatives. NumPy inputs compute exactly as before.
"""
from dataclasses import dataclass
from typing import Mapping
import warnings

import numpy as np
from scipy.sparse import coo_matrix, issparse
from scipy.sparse.linalg import MatrixRankWarning

from .mesh import Mesh
from .heat_source import ElementHeatSource
from .materials import is_per_region, region_property
from .postprocess import element_gradient
from .core import forms, kernels
from .core.backend import Backend, backend_of, is_live, lift, live_namespace, scatter_add, to_numpy
from .core.boundary import scalar_boundary_samples
from .core.checks import real_value
from .core.loads import ElementSource, source_load
from .core import solve as core_solve
from .core.sparse import CooMatrix
from .core.triangles import triangle_geometry


def _numbers(matrix):
    """A NumPy snapshot of a CooMatrix as SciPy CSR, for checks."""
    return CooMatrix(matrix.rows, matrix.cols, to_numpy(matrix.values), matrix.shape).to_scipy()


def _offsets(xp, anchors):
    """Per-component absolute temperature offsets as one array."""
    if any(is_live(a) for a in anchors):
        return xp.stack([lift(xp, a, xp.float64) for a in anchors])
    return lift(xp, np.array(anchors, dtype=float))


def _coo(xp, matrix):
    """A CooMatrix in ``xp`` from a CooMatrix or SciPy matrix.

    A canonical SciPy CSR (summed, sorted) returns from ``to_scipy`` unchanged.
    """
    if issparse(matrix):
        matrix = matrix.tocoo()
        return CooMatrix(matrix.row, matrix.col, lift(xp, matrix.data), matrix.shape)
    return CooMatrix(matrix.rows, matrix.cols, lift(xp, matrix.values), matrix.shape)


def _boundary_system(samples, n, labels, anchors, constrained):
    # Pick a useful absolute offset for Robin-only components. Any positive
    # sampled h anchors discretely; no unit-dependent artificial cutoff.
    for kind, edges, shape, weights, values in samples:
        if kind != "convection":
            continue
        h, ambient = values
        for e, q in np.argwhere(to_numpy(h) > 0):
            c = labels[edges[e, 0]]
            if not constrained[c]:
                anchors[c] = ambient[e, q]
                constrained[c] = True
    xp = live_namespace(*(v for sample in samples for v in sample[4]), *anchors)
    offsets = _offsets(xp, anchors)
    G, B, shifted_B = (xp.asarray(row) for row in np.zeros((3, n)))
    rows, cols, entries = [], [], []
    for kind, edges, shape, weights, values in samples:
        weights, shape = xp.asarray(weights), xp.asarray(shape)
        values = tuple(lift(xp, v) for v in values)
        if kind == "outward_flux":
            local = xp.einsum("eq,qa,eq->ea", weights, shape, values[0])
            G = scatter_add(xp, n, edges.ravel(), xp.reshape(local, (-1,)), base=G)
        else:
            h, ambient = values
            local_h = xp.einsum("eq,qa,qb,eq->eab", weights, shape, shape, h)
            local_b = xp.einsum("eq,qa,eq->ea", weights, shape, h*ambient)
            local_shift = xp.einsum("eq,qa,eq->ea", weights, shape,
                                    h*(ambient-offsets[labels[edges[:, 0]]][:, None]))
            B = scatter_add(xp, n, edges.ravel(), xp.reshape(local_b, (-1,)), base=B)
            shifted_B = scatter_add(xp, n, edges.ravel(), xp.reshape(local_shift, (-1,)), base=shifted_B)
            rows.append(np.repeat(edges, 2, axis=1).ravel())
            cols.append(np.tile(edges, (1, 2)).ravel())
            entries.append(xp.reshape(local_h, (-1,)))
    rows = np.concatenate(rows) if rows else np.zeros(0, dtype=int)
    cols = np.concatenate(cols) if cols else np.zeros(0, dtype=int)
    if backend_of(xp) is Backend.NUMPY:
        entries = np.concatenate(entries) if entries else np.zeros(0)
        return coo_matrix((entries, (rows, cols)), shape=(n, n)).tocsr(), G, B, shifted_B
    return CooMatrix(rows, cols, xp.concat(entries) if entries else xp.zeros(0, dtype=xp.float64),
                     (n, n)), G, B, shifted_B


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


def _element_source(heat_source, mesh):
    """An ElementHeatSource as the checked element values core.loads takes; other sources unchanged."""
    if isinstance(heat_source, ElementHeatSource):
        return ElementSource(heat_source.on_mesh(mesh))
    return heat_source


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
        k = real_value(conductivity, "conductivity")
        if tuple(k.shape) != () or to_numpy(k) <= 0:
            raise ValueError("conductivity must be a finite scalar > 0")
        k = k if is_live(k) else float(k)
    p, t, area, boundary, count, labels = triangle_geometry(mesh)
    if is_per_region(conductivity):
        k = region_property(mesh, conductivity, "conductivity", positive=True, live=True)
    if not isinstance(dirichlet, Mapping):
        raise ValueError("dirichlet must map exterior node indices to temperatures in K")
    prescribed = {}
    anchors = [0.0]*count
    constrained = np.zeros(count, dtype=bool)
    for node, value in dirichlet.items():
        if isinstance(node, (bool, np.bool_)) or not isinstance(node, (int, np.integer)):
            raise ValueError("Dirichlet node indices must be integers")
        if not 0 <= node < len(p) or node not in boundary:
            raise ValueError("Dirichlet node must lie on the exterior mesh boundary")
        value = real_value(value, "Dirichlet temperature")
        if tuple(value.shape) != ():
            raise ValueError("Dirichlet temperature must be scalar")
        prescribed[int(node)] = value if is_live(value) else float(value)
        component = labels[node]
        if not constrained[component]:
            anchors[component] = value
            constrained[component] = True
    samples = scalar_boundary_samples(mesh, p, t, prescribed, outward_flux, convection, live=True)
    H, G, B, shifted_B = _boundary_system(samples, len(p), labels, anchors, constrained)
    missing = np.flatnonzero(~constrained)
    if len(missing):
        raise ValueError(f"each connected component requires Dirichlet or positive Robin data; missing {missing.tolist()}")
    cells = np.asarray(mesh.triangles)
    stiffness = forms.matrix(cells, cells, kernels.p1_stiffness(mesh, k), (len(p), len(p)))
    load = source_load(mesh, p, t, area, _element_source(heat_source, mesh), live=True)
    # One array library for everything from here on (NumPy objects stay as they are).
    xp = live_namespace(k, load, G, B, shifted_B, None if issparse(H) else H.values,
                        *anchors, *prescribed.values())
    k, load, G, B, shifted_B = (lift(xp, a) for a in (k, load, G, B, shifted_B))
    offsets = _offsets(xp, anchors)
    stiffness, H = _coo(xp, stiffness), _coo(xp, H)
    rhs = load+B-G
    shifted_rhs = load+shifted_B-G
    K_numbers, H_numbers = _numbers(stiffness), _numbers(H)
    if not all(np.all(np.isfinite(a)) for a in
               (K_numbers.data, H_numbers.data,
                *map(to_numpy, (load, G, B, shifted_B, rhs, shifted_rhs)))):
        raise ValueError("assembled heat system exceeds floating-point range")
    shifted_bc = {(node,): value-offsets[labels[node]] for node, value in prescribed.items()}
    with warnings.catch_warnings():
        warnings.simplefilter("error", MatrixRankWarning)
        try:
            increment = core_solve.solve_dirichlet([stiffness, H], shifted_rhs, shifted_bc)
        except (RuntimeError, MatrixRankWarning, ValueError) as exc:
            raise ValueError("singular or ill-conditioned constrained heat system") from exc
    temperature = increment+offsets[labels]
    # K annihilates constants; H does not. shifted_B integrates h*(ambient-offset).
    # Evaluate derivatives and convection before restoring absolute temperature.
    convective = H.matvec(increment)-shifted_B
    residual = stiffness.matvec(increment)+convective-load+G
    flux = -(k[:, None] if getattr(k, "ndim", 0) else k)*element_gradient(mesh, increment)
    numbers = {name: to_numpy(a) for name, a in (("temperature", temperature), ("residual", residual),
               ("flux", flux), ("convective", convective), ("increment", increment),
               ("shifted_rhs", shifted_rhs), ("load", load), ("G", G))}
    if not all(np.all(np.isfinite(numbers[a])) for a in ("temperature", "residual", "flux", "convective")):
        raise ValueError("nonfinite heat solution, residual or heat flux")
    fixed = np.array(sorted(prescribed), dtype=int)
    free = np.setdiff1d(np.arange(len(p)), fixed)
    scale = max(np.linalg.norm(abs(K_numbers+H_numbers)@abs(numbers["increment"])
                               + abs(numbers["shifted_rhs"]), np.inf),
                np.finfo(float).tiny)
    if len(free) and np.linalg.norm(numbers["residual"][free], np.inf) > 1e-10*scale:
        raise ValueError("heat solve failed the normalized free residual tolerance")
    reaction = np.zeros(len(p))
    reaction[fixed] = numbers["residual"][fixed]
    for component in range(count):
        nodes = labels == component
        balance_scale = max(sum(np.sum(abs(a[nodes])) for a in
                                (numbers["load"], reaction, numbers["G"], numbers["convective"])),
                            np.finfo(float).tiny)
        if abs(np.sum((numbers["load"]+reaction-numbers["G"]-numbers["convective"])[nodes])) > 1e-10*balance_scale:
            raise ValueError("heat solve failed the normalized component heat balance tolerance")
    if is_live(residual):
        reaction = scatter_add(xp, len(p), fixed, residual[fixed])
    return SteadyHeatResult(temperature, flux, load, reaction, residual,
                            G, B, convective, rhs)
