# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Volumetric load vectors on P1 triangles."""
import numpy as np

from ..assembly import assemble_load
from ..heat_source import ElementHeatSource
from ..materials import is_per_region, region_property
from . import forms, kernels
from .backend import is_live, namespace, scatter_add
from .checks import real_array, real_value
from .quadrature import triangle_product_rule


def _live_centroid_load(mesh, t, size, values):
    return forms.vector(t, kernels.p1_load(mesh, values), size, order="columns")


def source_load(mesh, p, t, area, source, *, live=False):
    """Consistent P1 nodal load of a volumetric source (named heat_source in messages).

    ``source`` is an ElementHeatSource, a {region name: value} mapping, a scalar,
    or a callable taking (Q,2) coordinates and returning (Q,) values. With
    live=True a JAX or PyTorch value or callback result stays in its library
    (otherwise it is refused) and so does the load; ElementHeatSource is NumPy.
    """
    if isinstance(source, ElementHeatSource):
        return assemble_load(mesh, source.on_mesh(mesh))
    if is_per_region(source):
        values = region_property(mesh, source, "heat_source", live=live)
        if is_live(values):
            return _live_centroid_load(mesh, t, len(p), values)
        return assemble_load(mesh, values)
    check = real_value if live else real_array
    if not callable(source):
        value = check(source, "heat_source")
        if tuple(value.shape) != ():
            raise ValueError("constant heat_source must be scalar")
        if is_live(value):
            return _live_centroid_load(mesh, t, len(p), value)
        return assemble_load(mesh, float(value))
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
