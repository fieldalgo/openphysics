# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit one-way transfer of a steady electric result to steady heat."""
import copy
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from .core.checks import refuse_live
from .coupling import Field, transfer
from .electric import SteadyElectricResult
from .heat_source import MESH_MISMATCH, ElementHeatSource
from .thermal import PlanarSteadyHeatResult, solve_steady_heat_outward
from ._public import ResultSurface, outward_from_inward, refuse_text

# Public names. Internal: solve_steady_joule_heat_outward, the outward-form body that galerkin's own callers
# use (outside __all__).
__all__ = ["SteadyJouleHeatResult", "solve_steady_joule_heat"]


@dataclass(frozen=True)
class SteadyJouleHeatResult(ResultSurface):
    """Owned electrical and thermal snapshots of a planar Joule solve.

    ``electrical`` is the SteadyElectricResult and ``thermal`` the
    PlanarSteadyHeatResult of the heat stage; generated_heat_rate_per_depth is the
    Joule power the heat stage received and outward_heat_rate_per_depth the heat
    leaving the body, both in W per metre of depth (not W). ``.units`` maps the two
    rates to W/m.
    """

    electrical: SteadyElectricResult
    thermal: PlanarSteadyHeatResult
    generated_heat_rate_per_depth: float
    outward_heat_rate_per_depth: float

    BASIS = "planar"
    UNITS = MappingProxyType({"generated_heat_rate_per_depth": "W/m", "outward_heat_rate_per_depth": "W/m"})


def _agree(actual, expected, name, *, balance_scale=0.):
    actual = np.asarray(actual)
    expected = np.asarray(expected)
    if (actual.shape != expected.shape or actual.dtype.kind not in "iuf"
            or not np.all(np.isfinite(actual)) or not np.all(np.isfinite(expected))
            or not np.isfinite(balance_scale)):
        raise ValueError(f"{name} must be finite real with the expected shape")
    scale = max(float(np.max(abs(expected))), balance_scale, np.finfo(float).tiny)
    if np.max(abs(actual-expected)) > 1e-10*scale:
        raise ValueError(f"{name} disagrees with integrated Joule source")


def solve_steady_joule_heat(mesh, *, electrical_result, thermal_conductivity, prescribed_temperature,
                            inward_heat_flux=None, convection=None):
    """Transfer actual electric Q to heat on the same SI mesh, without iteration, in SI.

    First call ``galerkin.electric.solve_steady_electric`` explicitly. Pass its
    result here along with the same mesh (an exactly matching copy is accepted).
    Coordinates are metres; thermal_conductivity is W/(m K), prescribed_temperature
    maps nodes to K. inward_heat_flux (W/m^2, positive in) and convection take the
    signs and units of ``galerkin.thermal.solve_steady_heat``. Thermal
    conductivities must be temperature-independent constants, either scalar or by
    named region. No extra heat source or thickness is implicit. Geometry, element
    order and region correspondence must match the electrical snapshot. No spatial
    interpolation or averaging of Joule sources is done. Returns a
    SteadyJouleHeatResult (rates per metre of depth).

    A str for a quantity raises TypeError (SI numbers only). The inward heat flux is
    negated once, as 0.0 - x (a callback's checked float result likewise), and the
    outward-form transfer runs exactly as before; see galerkin._public.
    """
    outward_flux = outward_from_inward(inward_heat_flux, "inward_heat_flux")     # a non-mapping: ValueError
    for name, value in (("thermal_conductivity", thermal_conductivity),
                        ("prescribed_temperature", prescribed_temperature), ("inward_heat_flux", inward_heat_flux),
                        ("convection", convection)):
        refuse_text(name, value)
    return solve_steady_joule_heat_outward(mesh, electrical_result=electrical_result,
                                           conductivity=thermal_conductivity, dirichlet=prescribed_temperature,
                                           outward_flux=outward_flux, convection=convection)


def solve_steady_joule_heat_outward(mesh, *, electrical_result, conductivity, dirichlet,
                                    outward_flux=None, convection=None):
    """Transfer actual electric Q to heat on the same SI mesh, without iteration (the outward form).

    The body of solve_steady_joule_heat before the galerkin step, for galerkin's own callers.

    First call ``galerkin.electric.solve_steady_electric`` explicitly. Pass its
    result here along with the same mesh (an exactly matching copy is accepted).
    Coordinates are metres; thermal conductivity is W/(m K), temperatures K.
    Thermal boundary signs and units are those of ``solve_steady_heat_outward``.
    Material conductivities must be temperature-independent constants, either
    scalar or by named region. No extra heat source or thickness is implicit.
    Geometry, element order and region correspondence must match the electrical
    snapshot. No spatial interpolation or averaging of Joule sources is done.
    """
    if not isinstance(electrical_result, SteadyElectricResult):
        raise ValueError("electrical_result must be a SteadyElectricResult")
    refuse_live(electrical_result.joule_power_density, "solve_steady_joule_heat electrical_result")
    electric = copy.deepcopy(electrical_result)
    # deepcopy owns the buffers but resets NumPy's writeable flag. Preserve
    # the electrical result's public read-only-array contract in this snapshot.
    for value in [*vars(electric).values(), electric.mesh.nodes, electric.mesh.triangles,
                  electric.mesh.regions, *electric.mesh.boundary.values(),
                  *electric.mesh.boundary_edges.values()]:
        if isinstance(value, np.ndarray):
            value.setflags(write=False)
    # The Joule field lives on the electrical mesh; the identity transfer
    # refuses any other thermal mesh. No interpolation or averaging.
    joule = Field(electric.mesh, electric.joule_power_density, location="element", unit="W/m^3",
                  name="element heat source")
    joule = transfer(joule, mesh, message=MESH_MISMATCH)
    source = ElementHeatSource(mesh, joule.values)
    if np.any(source.values < 0):
        raise ValueError("Joule heating must be nonnegative")
    owned_mesh = copy.deepcopy(mesh)
    # galerkin's own caller: the private outward-form heat solve (rule 6: the public function negated once).
    heat = solve_steady_heat_outward(owned_mesh, conductivity=conductivity, dirichlet=dirichlet,
                              heat_source=source, outward_flux=outward_flux,
                              convection=convection)
    # This transfer computes with NumPy; a live thermal input would lose its derivative here.
    refuse_live(heat.temperature, "solve_steady_joule_heat thermal inputs")
    # The heat assembly independently integrates the electric element field.
    # Check both the nodal distribution and total power; totals alone can hide
    # incorrect element-to-node correspondence.
    power = float(np.sum(heat.generated_heat_rate_per_depth))
    _agree(electric.generated_heat_rate_per_depth, heat.generated_heat_rate_per_depth,
           "electrical_result.generated_heat_rate_per_depth")
    _agree(electric.joule_power_per_depth, power, "electrical_result.joule_power_per_depth")
    _agree(electric.inward_electric_power_per_depth, power, "electrical_result.inward_electric_power_per_depth")
    outward = float(np.sum(-heat.reaction_heat_rate_per_depth + heat.outward_prescribed_heat_rate_per_depth
                           + heat.outward_convective_heat_rate_per_depth))
    boundary_scale = float(np.sum(abs(heat.reaction_heat_rate_per_depth)
                                  + abs(heat.outward_prescribed_heat_rate_per_depth)
                                  + abs(heat.outward_convective_heat_rate_per_depth)))
    _agree(outward, power, "outward_heat_rate_per_depth", balance_scale=boundary_scale)
    return SteadyJouleHeatResult(electric, heat, power, outward)
