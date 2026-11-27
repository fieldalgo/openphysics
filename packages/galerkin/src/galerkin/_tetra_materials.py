# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Shared material inputs for tetrahedral heat, elasticity and DC solvers."""
from collections.abc import Mapping

import numpy as np

from ._public import refuse_text
from .core.checks import contains_live, finite_scalar, positive_real, real_array
from .core.materials import evaluate_conductivity
from .mesh3d import Mesh3D


def refuse_live_3d(value, name):
    if contains_live(value) or (isinstance(value, Mapping)
                                and any(contains_live(v) for v in value.values())):
        raise TypeError(f"{name}: this solver runs on NumPy and carries no derivative; "
                        "pass NumPy numbers")


def region_property(mesh, value, label, *, positive):
    """(T,) float array from a scalar or {region name: scalar}."""
    refuse_live_3d(value, label)
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


def _region_names(mesh, values):
    names = mesh.region_names
    if names is None or mesh.regions is None:
        raise ValueError("electrical_conductivity by region requires named tetrahedral regions")
    if set(values) != set(names):
        raise ValueError("electrical_conductivity keys must match mesh.region_names exactly")
    return names


def element_conductivity(mesh, values):
    name = "electrical_conductivity"
    if isinstance(values, Mapping):
        names = _region_names(mesh, values)
        return mesh.by_region([positive_real(values[key], f"{name}[{key!r}]") for key in names])
    if isinstance(values, (list, tuple, np.ndarray)):
        sigma = real_array(values, name)
        if sigma.shape != (mesh.num_tets,) or np.any(sigma <= 0):
            raise ValueError(f"{name} must have shape (T,) and contain positive values")
        return sigma
    return np.full(mesh.num_tets, positive_real(values, name))


def conductivity_at_temperature(mesh, electrical_conductivity, temperature):
    """Evaluate the DC material law on the tetrahedral means of nodal Kelvin values."""
    from .temperature_joule_heating import ConductivityModel

    refuse_text("electrical_conductivity", electrical_conductivity)
    refuse_text("temperature", temperature)
    if not isinstance(mesh, Mesh3D):
        raise TypeError("conductivity evaluation takes a galerkin.Mesh3D")
    nodal = real_array(temperature, "temperature")
    if nodal.shape != (mesh.num_nodes,) or np.any(nodal < 0):
        raise ValueError("temperature must have shape (N,) and contain nonnegative Kelvin values")
    material = electrical_conductivity
    if isinstance(material, Mapping):
        names = _region_names(mesh, material)
        groups = ((name, mesh.regions == i, material[name]) for i, name in enumerate(names))
    else:
        groups = (("all", slice(None), material),)

    sigma = np.empty(mesh.num_tets)
    for name, cells, law in groups:
        if not isinstance(law, ConductivityModel):
            sigma[cells] = positive_real(law, f"electrical_conductivity[{name!r}]")
            continue
        values = nodal[mesh.tets[cells]]
        if not values.size:
            continue
        lo, hi = law.temperature_range
        if np.any((values < lo) | (values > hi)):
            raise ValueError(f"material {name!r}: temperature [{values.min()}, {values.max()}] K "
                             f"outside [{lo}, {hi}] K")
        sigma[cells] = evaluate_conductivity(law, np.sum(values / 4., axis=1), name)
    return sigma
