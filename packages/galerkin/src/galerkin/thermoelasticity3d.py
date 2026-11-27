# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Small-strain isotropic thermoelasticity from prescribed Mesh3D temperatures."""
from collections.abc import Mapping

import numpy as np

from ._public import refuse_tagged_text, refuse_text
from .core.checks import finite_scalar, real_array
from .elasticity3d import _solve_elasticity_3d
from .mesh3d import Mesh3D

__all__ = ["solve_thermoelasticity_3d"]


def solve_thermoelasticity_3d(
    mesh, *, temperature, stress_free_temperature, linear_expansion_coefficient,
    youngs_modulus, poisson_ratio, prescribed_displacement, body_force_density=None, traction=None,
):
    """Solve the 3D elastic problem with isotropic free expansion on P1 tetrahedra.

    Temperatures are nonnegative K in mesh node order, with a scalar reference.
    Expansion (1/K), Young's modulus (Pa) and Poisson's ratio can be scalars or
    tables keyed by material region name. The elastic solver takes component
    displacements in m, body-force densities in N/m³ and total tractions in Pa.
    Its result carries the total strain, physical stress and support reactions.
    """
    for name, value in (
        ("temperature", temperature), ("stress_free_temperature", stress_free_temperature),
        ("linear_expansion_coefficient", linear_expansion_coefficient),
        ("youngs_modulus", youngs_modulus), ("poisson_ratio", poisson_ratio),
        ("prescribed_displacement", prescribed_displacement), ("body_force_density", body_force_density),
    ):
        refuse_text(name, value)
    refuse_tagged_text("traction", traction)
    if not isinstance(mesh, Mesh3D):
        raise TypeError("solve_thermoelasticity_3d takes a galerkin.Mesh3D")

    nodal = real_array(temperature, "temperature")
    if nodal.shape != (mesh.num_nodes,):
        raise ValueError(f"temperature must have shape ({mesh.num_nodes},) in mesh node order")
    reference = finite_scalar(stress_free_temperature, "stress_free_temperature")
    if reference < 0 or np.any(nodal < 0):
        raise ValueError("temperature and stress_free_temperature must be nonnegative in K")

    label = "linear_expansion_coefficient"
    if isinstance(linear_expansion_coefficient, Mapping):
        names = mesh.region_names
        if names is None or mesh.regions is None or set(names) != set(linear_expansion_coefficient):
            raise ValueError(f"{label} region keys must match mesh.region_names exactly")
        alpha = mesh.by_region([finite_scalar(linear_expansion_coefficient[name], f"{label}[{name!r}]")
                                for name in names])
    else:
        alpha = finite_scalar(linear_expansion_coefficient, label)

    with np.errstate(over="ignore", invalid="ignore"):
        mean_delta = np.sum((nodal[mesh.tets] - reference) / 4.0, axis=1)
        thermal_strain = alpha * mean_delta
    if not np.all(np.isfinite(thermal_strain)):
        raise ValueError("thermal expansion strain exceeds floating-point range")

    return _solve_elasticity_3d(
        mesh, youngs_modulus=youngs_modulus, poisson_ratio=poisson_ratio,
        prescribed_displacement=prescribed_displacement, body_force_density=body_force_density,
        traction=traction, thermal_strain=thermal_strain,
    )
