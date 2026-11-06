# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Volumetric load vectors on P1 triangles."""
from dataclasses import dataclass

import numpy as np

from . import forms, kernels
from .materials import is_per_region, region_property
from .backend import is_live, namespace, scatter_add
from .checks import real_array, real_value
from .quadrature import triangle_product_rule


@dataclass(frozen=True)
class ElementSource:
    """Per-triangle source values in W/m^3, NumPy, already checked against the mesh.

    Physics modules build it from their own mesh-bound containers (for heat,
    ``galerkin.heat_source.ElementHeatSource.on_mesh``), so this layer needs no
    knowledge of them.
    """

    values: np.ndarray


def _centroid_load(mesh, t, size, values):
    """One-point centroid load (value times A/3 at each vertex), in the values' library."""
    return forms.vector(t, kernels.p1_load(mesh, values), size, order="columns")


def source_load(mesh, p, t, area, source, *, live=False, measure=None):
    """Consistent P1 nodal load of a volumetric source (named heat_source in messages).

    ``source`` is an ElementSource, a {region name: value} mapping, a scalar,
    or a callable taking (Q,2) coordinates and returning (Q,) values. With
    live=True a JAX or PyTorch value or callback result stays in its library
    (otherwise it is refused) and so does the load; ElementSource is NumPy.
    """
    if measure is not None and measure.axisymmetric:
        return _weighted_source_load(mesh, p, t, area, source, live, measure)
    if isinstance(source, ElementSource):
        return _centroid_load(mesh, t, len(p), source.values)
    if is_per_region(source):
        values = region_property(mesh, source, "heat_source", live=live)
        return _centroid_load(mesh, t, len(p), values)
    check = real_value if live else real_array
    if not callable(source):
        value = check(source, "heat_source")
        if tuple(value.shape) != ():
            raise ValueError("constant heat_source must be scalar")
        return _centroid_load(mesh, t, len(p), value if is_live(value) else float(value))
    # Original Duffy-product rule: integrate Q*N_i, not centroid Q times A/3.
    bary, weights = triangle_product_rule()
    points = np.einsum("qa,tad->tqd", bary, p[t])
    values = check(source(points.reshape(-1, 2)), "heat_source callback")
    if tuple(values.shape) != (points.shape[0]*points.shape[1],):
        raise ValueError("heat_source callback must return exactly shape (Q,)")
    if is_live(values):
        xp = namespace(values)
        local = xp.einsum("qi,q,tq,t->ti", *(xp.asarray(a) for a in (bary, weights)),
                          xp.reshape(values, points.shape[:2]), xp.asarray(area))
        return scatter_add(xp, len(p), t.ravel(), xp.reshape(local, (-1,)))
    local = np.einsum("qi,q,tq,t->ti", bary, weights,
                      values.reshape(points.shape[:2]), area)
    load = np.zeros(len(p))
    np.add.at(load, t.ravel(), local.ravel())
    return load


def _weighted_source_load(mesh, p, t, area, source, live, measure):
    """Consistent weighted load; static quadrature, array-API values and scatter."""
    bary, weights = triangle_product_rule()
    points = np.einsum("qa,tad->tqd", bary, p[t])
    check = real_value if live else real_array
    if isinstance(source, ElementSource):
        values = source.values[:, None]
    elif is_per_region(source):
        values = region_property(mesh, source, "heat_source", live=live)[:, None]
    elif callable(source):
        values = check(source(points.reshape(-1, 2)), "heat_source callback")
        if tuple(values.shape) != (points.shape[0]*points.shape[1],):
            raise ValueError("heat_source callback must return exactly shape (Q,)")
        values = values.reshape(points.shape[:2])
    else:
        values = check(source, "heat_source")
        if tuple(values.shape) != ():
            raise ValueError("constant heat_source must be scalar")
    xp = namespace(values)
    basis = xp.broadcast_to(xp.asarray(bary)[None, :, :], (len(t), *bary.shape))
    local = forms.integrate_linear(basis, weights, area,
                                   values*xp.asarray(measure.density(points)))
    return forms.vector(t, local, len(p))
