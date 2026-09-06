# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""refsol — analytical reference solutions and published benchmarks for
electromagnetic / photonic solver validation.

Independent of any particular solver. Intended as the common "answer key"
for the FieldAlgo solvers and anyone else who wants to check a Maxwell solver
against something trustworthy.

Modules
-------
slab        planar (slab) dielectric waveguide TE/TM modes, symmetric or asymmetric
fiber       step-index optical fiber: scalar LP modes and exact vector modes
metallic    hollow metallic waveguide cutoffs, cavity resonances, coaxial potential
scattering  plane-wave scattering off a circular cylinder (PEC and dielectric)
benchmarks  published reference values with citations (Hadley 2002 rib waveguides, ...)
"""

from . import slab, fiber, metallic, scattering, benchmarks

__version__ = "0.1.0"
__all__ = ["slab", "fiber", "metallic", "scattering", "benchmarks"]
