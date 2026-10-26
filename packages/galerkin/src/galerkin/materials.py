# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Piecewise-constant material properties on named mesh regions.

A material property is either one finite real scalar (one homogeneous
material, the original contract) or a mapping ``{region name: scalar}`` with
exactly one entry for every name in ``mesh.region_names``. Region names come
from ``Mesh.region_names`` (``disk_mesh``, ``layered_*_mesh``, gmsh physical
groups through gmshio). Bare per-triangle arrays are not accepted by the
physics APIs: a sequence of length M is ambiguous with a vector or tensor
input, so per-triangle data is always built from names. Values keep their SI
units; no unit conversion happens here. See docs/packages/galerkin/multimaterial.md.
"""
from collections.abc import Mapping

import numpy as np

from .core.backend import is_live, lift, live_namespace, namespace, require_float64, to_numpy
from .core.checks import finite_scalar


def region_index(mesh):
    """Validated (M,) region ids and names of a mesh, or raise ValueError."""
    regions, names = getattr(mesh, "regions", None), getattr(mesh, "region_names", None)
    if regions is None or names is None:
        raise ValueError("a per-region material needs mesh.regions and mesh.region_names")
    regions = np.asarray(regions)
    names = list(names)
    if regions.shape != (len(mesh.triangles),) or regions.dtype.kind not in "iu":
        raise ValueError("mesh.regions must be one integer region id per triangle")
    if not names or len(set(names)) != len(names) or not all(isinstance(n, str) for n in names):
        raise ValueError("mesh.region_names must be unique nonempty strings")
    if len(regions) and (regions.min() < 0 or regions.max() >= len(names)):
        raise ValueError("mesh.regions holds an id outside mesh.region_names")
    return regions, names


def is_per_region(value):
    return isinstance(value, Mapping)


def region_property(mesh, value, label, *, positive=False, lower=None, upper=None, live=False):
    """Scalar float or (M,) per-triangle float array for a material property.

    value: finite real scalar, or a mapping with exactly the mesh region names
    as keys and finite real scalars as values. positive requires > 0; lower and
    upper are exclusive bounds. Scalars return float so that homogeneous
    callers keep their original floating-point path bit for bit.

    live=True lets a JAX or PyTorch value through (refused otherwise): it gets
    the same checks on a snapshot and stays a float64 array in its own library,
    and a table holding one becomes an (M,) array of that library.
    """
    def check(v, where):
        if live and is_live(v):
            check(to_numpy(v), where)
            xp = namespace(v)
            require_float64(xp, f"{label}{where}")
            return xp.astype(v, xp.float64)
        v = finite_scalar(v, f"{label}{where}")
        if positive and v <= 0:
            raise ValueError(f"{label}{where} must be a finite real scalar > 0")
        if lower is not None and not v > lower:
            raise ValueError(f"{label}{where} must be > {lower}")
        if upper is not None and not v < upper:
            raise ValueError(f"{label}{where} must be < {upper}")
        return v
    if not is_per_region(value):
        return check(value, "")
    regions, names = region_index(mesh)
    keys = list(value)
    unknown = [k for k in keys if k not in names]
    missing = [n for n in names if n not in value]
    if unknown or missing:
        raise ValueError(f"{label} regions must match mesh.region_names exactly; "
                         f"missing {missing}, unknown {unknown}")
    entries = [check(value[n], f" in region {n!r}") for n in names]
    if any(is_live(e) for e in entries):
        xp = live_namespace(*entries)
        return xp.stack([lift(xp, e, xp.float64) for e in entries])[regions]
    table = np.array(entries)
    return table[regions]


def element_values(mesh, value):
    """Broadcast a region_property result to one value per triangle."""
    if is_live(value):
        return namespace(value).broadcast_to(value, (len(mesh.triangles),))
    return np.broadcast_to(np.asarray(value, dtype=float), (len(mesh.triangles),))
