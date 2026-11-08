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
lossy_slab  multilayer slab with complex permittivity: bound absorbing and substrate-leaky
            complex effective indices, exp(+i omega t) convention, documented sheet choice
fiber       step-index optical fiber: scalar LP modes and exact vector modes
metallic    hollow metallic waveguide cutoffs, cavity resonances, coaxial potential
electrostatics  coaxial and two-layer parallel-plate capacitance per unit length
scattering  plane-wave scattering off a circular cylinder (PEC and dielectric)
benchmarks  published reference values with citations (Hadley 2002 rib waveguides, ...)
cavity      complete finite-frequency Cartesian spectrum of a vacuum PEC box
material_cavity  complex resonances and Q of uniformly or slab-loaded lossy PEC boxes
wall_loss   first-order conductor-loss Q of rectangular cavity modes, per wall
bimetal     Timoshenko (1925) bimetal strip: curvature closed forms and exact plane-stress field
thermal_convection  NAFEMS T4 convective rectangle: exact series and the published target
bent_slab   constant-radius bent slab poles by complex-order Bessel/Hankel matching (needs the
            optional mpmath package at call time; ImportError names it otherwise)
joule_slab  steady 1D Joule heating with sigma = sigma0 (1 + alpha (T - T0)): closed form in
            erf/erfi for fixed face potentials and temperatures, current-driven root, fold
thermal3d   steady heat in three dimensions: sine-product manufactured box and a layered slab along z
"""

from . import (slab, lossy_slab, fiber, metallic, electrostatics, scattering, benchmarks, cavity,
               material_cavity, wall_loss, joule_slab, bent_slab, thermal3d)

__version__ = "0.0.2"
__all__ = ["slab", "lossy_slab", "fiber", "metallic", "electrostatics", "scattering", "benchmarks",
           "cavity", "material_cavity", "wall_loss", "joule_slab", "bent_slab", "thermal3d"]
