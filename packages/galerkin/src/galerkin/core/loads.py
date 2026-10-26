# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Volumetric load vectors on P1 triangles."""
import numpy as np

from ..assembly import assemble_load
from ..heat_source import ElementHeatSource
from ..materials import is_per_region, region_property
from .checks import real_array
from .quadrature import triangle_product_rule


def source_load(mesh, p, t, area, source):
    """Consistent P1 nodal load of a volumetric source (named heat_source in messages).

    ``source`` is an ElementHeatSource, a {region name: value} mapping, a scalar,
    or a callable taking (Q,2) coordinates and returning (Q,) values.
    """
    if isinstance(source, ElementHeatSource):
        return assemble_load(mesh, source.on_mesh(mesh))
    if is_per_region(source):
        return assemble_load(mesh, region_property(mesh, source, "heat_source"))
    if not callable(source):
        value = real_array(source, "heat_source")
        if value.shape != ():
            raise ValueError("constant heat_source must be scalar")
        return assemble_load(mesh, float(value))
    # Original Duffy-product rule: integrate Q*N_i, not centroid Q times A/3.
    bary, weights = triangle_product_rule()
    points = np.einsum("qa,tad->tqd", bary, p[t])
    values = real_array(source(points.reshape(-1, 2)), "heat_source callback")
    if values.shape != (points.shape[0]*points.shape[1],):
        raise ValueError("heat_source callback must return exactly shape (Q,)")
    local = np.einsum("qi,q,tq,t->ti", bary, weights,
                      values.reshape(points.shape[:2]), area)
    load = np.zeros(len(p))
    np.add.at(load, t.ravel(), local.ravel())
    return load
