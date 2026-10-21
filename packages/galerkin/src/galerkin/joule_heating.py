# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit one-way transfer of a steady electric result to steady heat."""
import copy
from dataclasses import dataclass

import numpy as np

from .electric import SteadyElectricResult
from .heat_source import ElementHeatSource
from .thermal import SteadyHeatResult, solve_steady_heat


@dataclass
class SteadyJouleHeatResult:
    """Owned electrical/thermal snapshots; integrated rates are W/m, not W."""

    electrical: SteadyElectricResult
    thermal: SteadyHeatResult
    source_power_per_length: float
    outward_heat_per_length: float


def _agree(actual, expected, name, *, balance_scale=0.):
    actual = np.asarray(actual)
    expected = np.asarray(expected)
    if (actual.shape != expected.shape or actual.dtype.kind not in "iuf"
            or not np.all(np.isfinite(actual)) or not np.all(np.isfinite(expected))
            or not np.isfinite(balance_scale)):
        raise ValueError(f"electrical {name} must be finite real with the expected shape")
    scale = max(float(np.max(abs(expected))), balance_scale, np.finfo(float).tiny)
    if np.max(abs(actual-expected)) > 1e-10*scale:
        raise ValueError(f"electrical {name} disagrees with integrated Joule source")


def solve_steady_joule_heat(mesh, *, electrical_result, conductivity, dirichlet,
                          outward_flux=None, convection=None):
    """Transfer actual electric Q to heat on the same SI mesh, without iteration.

    First call ``galerkin.electric.solve_steady_electric`` explicitly. Pass its
    result here along with the same mesh (an exactly matching copy is accepted).
    Coordinates are metres; thermal conductivity is W/(m K), temperatures K.
    Thermal boundary signs and units are those of ``solve_steady_heat``.
    Material conductivities must be temperature-independent constants, either
    scalar or by named region. No extra heat source or thickness is implicit.
    Geometry, element order and region correspondence must match the electrical
    snapshot. No spatial interpolation or averaging of Joule sources is done.
    """
    if not isinstance(electrical_result, SteadyElectricResult):
        raise ValueError("electrical_result must be a SteadyElectricResult")
    electric = copy.deepcopy(electrical_result)
    # deepcopy owns the buffers but resets NumPy's writeable flag. Preserve
    # the electrical result's public read-only-array contract in this snapshot.
    for value in [*vars(electric).values(), electric.mesh.nodes, electric.mesh.triangles,
                  electric.mesh.regions, *electric.mesh.boundary.values(),
                  *electric.mesh.boundary_edges.values()]:
        if isinstance(value, np.ndarray):
            value.setflags(write=False)
    source = ElementHeatSource(electric.mesh, electric.joule_heating)
    source.on_mesh(mesh)
    if np.any(source.values < 0):
        raise ValueError("Joule heating must be nonnegative")
    owned_mesh = copy.deepcopy(mesh)
    heat = solve_steady_heat(owned_mesh, conductivity=conductivity, dirichlet=dirichlet,
                             heat_source=source, outward_flux=outward_flux,
                             convection=convection)
    # The heat assembly independently integrates the electric element field.
    # Check both the nodal distribution and total power; totals alone can hide
    # incorrect element-to-node correspondence.
    power = float(np.sum(heat.load))
    _agree(electric.joule_load, heat.load, "joule_load")
    _agree(electric.joule_power_per_length, power, "joule_power_per_length")
    _agree(electric.supplied_power_per_length, power, "supplied_power_per_length")
    outward = float(np.sum(-heat.reaction + heat.prescribed_outward_load
                           + heat.convective_outward))
    boundary_scale = float(np.sum(abs(heat.reaction) + abs(heat.prescribed_outward_load)
                                  + abs(heat.convective_outward)))
    _agree(outward, power, "thermal outward power", balance_scale=boundary_scale)
    return SteadyJouleHeatResult(electric, heat, power, outward)
