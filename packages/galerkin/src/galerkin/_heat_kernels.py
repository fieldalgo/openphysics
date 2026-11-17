# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Kernels of the heat solvers that other galerkin modules share (package-private).

The 2D boundary system ``scalar_boundary_system`` (with ``component_offsets``) of
``galerkin.thermal``, which ``galerkin.transient_heat`` and the Newton step of
``galerkin.temperature_joule_heating`` reuse, and the 3D source load
``source_load_3d`` and face-tag Dirichlet map ``dirichlet_from_faces`` of
``galerkin.thermal3d``. They were the heat modules' own helpers until the galerkin
step (L2 commit 6); the heat modules now hold no name that left their public API,
so the helpers live here and ``galerkin.kernels`` re-exports them unchanged.
Consistent units: whatever units the caller's numbers have (SI from the solvers).
"""
from collections.abc import Mapping

import numpy as np
from scipy.sparse import coo_matrix

from .core.backend import Backend, backend_of, is_live, lift, live_namespace, scatter_add, to_numpy
from .core.checks import contains_live, finite_scalar
from .core.sparse import CooMatrix
from .mesh3d import Mesh3D

__all__ = ["component_offsets", "scalar_boundary_system", "refuse_live_3d", "source_load_3d",
           "dirichlet_from_faces"]


def component_offsets(xp, anchors):
    """Per-component absolute temperature offsets as one array."""
    if any(is_live(a) for a in anchors):
        return xp.stack([lift(xp, a, xp.float64) for a in anchors])
    return lift(xp, np.array(anchors, dtype=float))


def scalar_boundary_system(samples, n, labels, anchors, constrained):
    """Robin matrix H, outward-flux load G, ambient load B and shifted ambient load from ``samples``.

    ``samples`` come from ``core.boundary.scalar_boundary_samples``. ``anchors`` and
    ``constrained`` (one entry per connected component, from ``labels``) are updated
    in place: a component without Dirichlet support is anchored at the ambient
    temperature of its first positive h sample. The shifted load integrates
    h*(ambient - offset of the component). H is SciPy CSR on NumPy and a CooMatrix
    of the live library otherwise; the loads are arrays of that library. Shared so
    that the Newton step of galerkin.temperature_joule_heating linearizes the
    operator this heat solve uses; internal (galerkin.kernels re-exports it).
    """
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
    offsets = component_offsets(xp, anchors)
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


def refuse_live_3d(value, name):
    if contains_live(value) or (isinstance(value, Mapping)
                                and any(contains_live(v) for v in value.values())):
        raise TypeError(f"{name}: solve_steady_heat_3d runs on NumPy and carries no derivative; "
                        "pass NumPy numbers")


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
        refuse_live_3d(value, f"temperature on {tag!r}")
        value = finite_scalar(value, f"temperature on {tag!r}")
        for node in np.unique(mesh.tagged_faces[tag]).tolist():
            if node in out and out[node] != value:
                raise ValueError(f"node {node} lies on faces with different temperatures "
                                 f"({out[node]!r} and {value!r} on {tag!r})")
            out[node] = value
    return out
