# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Piecewise-constant material properties on named mesh regions.

A material property is either one finite real scalar or a mapping
``{region name: scalar}`` with exactly one entry for every name in
``mesh.region_names``. The implementation lives in ``galerkin.core.materials``
with the rest of the shared layer; this module keeps its public names. See
docs/packages/galerkin/multimaterial.md.
"""
from .core.materials import element_values, is_per_region, region_index, region_property

__all__ = ["element_values", "is_per_region", "region_index", "region_property"]
