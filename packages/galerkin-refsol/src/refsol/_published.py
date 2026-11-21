# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Published benchmark data, stored exactly as published (private).

Each record keeps the numbers of its source and the unit they are stated in (``unit``),
never converted in place. The public accessors (``refsol.thermal_convection.nafems_t4``
and ``nafems_t4_target``; ``refsol.benchmarks.rib_waveguides``, ``rib_neff`` and
``dielectric_corners``) return SI values computed from these literals at run time by a
stated rule, so no stored literal changes (spec D44).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PublishedConvectionRectangle:
    """NAFEMS T4's rectangle as published: lengths and coefficients in SI, temperatures in ``unit``."""
    width: float
    height: float
    conductivity: float
    convection: float
    bottom_temperature: float
    ambient: float
    unit: str


@dataclass(frozen=True)
class PublishedTarget:
    """A published benchmark number with its provenance, in the unit it was published in."""
    point: tuple
    value: float
    unit: str
    quoted_precision: float
    source: str


# NAFEMS T4 ("Two-dimensional heat transfer with convection"); see refsol.thermal_convection.
NAFEMS_T4 = PublishedConvectionRectangle(width=.6, height=1., conductivity=52., convection=750.,
                                         bottom_temperature=100., ambient=0., unit="degC")
NAFEMS_T4_TARGET = PublishedTarget(
    point=(.6, .2), value=18.3, unit="degC", quoted_precision=.1,
    source="NAFEMS T4 target as quoted by DIANA FEA (2DHeatTransferConvection.pdf, "
           "citing NAFEMS 1990) and FEATool ex_heattransfer4.m (citing Cameron, "
           "Casey and Simpson, NAFEMS 1986); accessed 2026-10-22")


@dataclass(frozen=True)
class PublishedRibWaveguides:
    """Hadley's rib waveguide family as published: lengths in ``unit``, indices and n_eff dimensionless.

    ``table`` holds (slab thickness, quasi-TE n_eff) per case; the rest is the shared geometry and
    the stated error of n_eff (``uncertainty``, absolute).
    """
    table: tuple
    wavelength: float
    rib_width: float
    core_thickness: float
    n_core: float
    n_substrate: float
    n_cover: float
    uncertainty: float
    unit: str
    source: str


@dataclass(frozen=True)
class PublishedDielectricCorner:
    """One of Hadley's dielectric-corner problems as published: dimensionless (``unit`` "1": lengths in
    units of the square's side), with the stated error of n_eff (``uncertainty``, absolute)."""
    eps_core: float
    eps_clad: float
    pec_sides: tuple
    neff: float
    wavelength: float
    domain: tuple
    core_box: tuple
    uncertainty: float
    unit: str
    source: str


# G. R. Hadley (2002); see refsol.benchmarks.
HADLEY_2002 = ("G. R. Hadley, J. Lightwave Technol. 20(7), 1210-1218 (2002), "
               "doi:10.1109/JLT.2002.800370")

RIB_WAVEGUIDES = PublishedRibWaveguides(
    table=(
        (0.0, 3.412022),
        (0.1, 3.412126),
        (0.2, 3.412279),
        (0.3, 3.412492),
        (0.4, 3.412774),
        (0.5, 3.413132),
        (0.6, 3.413571),
        (0.7, 3.414100),
    ),
    wavelength=1.15, rib_width=3.0, core_thickness=1.0, n_core=3.44, n_substrate=3.40, n_cover=1.0,
    uncertainty=3e-6, unit="um", source=HADLEY_2002)

DIELECTRIC_CORNERS = tuple(
    PublishedDielectricCorner(eps_core, eps_clad, pec_sides, neff, wavelength=1.5, domain=(1.0, 1.0),
                              core_box=(0.5, 0.5), uncertainty=1e-8, unit="1", source=HADLEY_2002)
    for eps_core, eps_clad, pec_sides, neff in (
        (2.25, 1.0, ("left", "right"), 1.27627404),
        (8.0, 1.0, ("left", "right"), 2.65679692),
        (1.0, 2.25, ("left", "top"), 1.387926425),
        (1.0, 8.0, ("left", "top"), 2.761465320),
    )
)
