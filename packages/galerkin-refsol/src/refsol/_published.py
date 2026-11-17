# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Published benchmark data, stored exactly as published (private).

Each record keeps the numbers of its source and the unit they are stated in (``unit``),
never converted in place. The public accessors (``refsol.thermal_convection.nafems_t4``
and ``nafems_t4_target``) return SI values computed from these literals at run time by
a stated rule, so no stored literal changes (spec D44).
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
