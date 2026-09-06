# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Published numerical benchmarks with citations.

These are not closed-form solutions but high-accuracy reference values from the
literature, with the geometry fully specified so a mode solver can be run on
exactly the same problem. Values are reproduced from

    G. R. Hadley, "High-accuracy finite-difference equations for dielectric
    waveguide analysis II: dielectric corners," J. Lightwave Technol. 20(7),
    1210-1218 (2002).

The values are Hadley's own published results. They were cross-checked against
the same table in the benchmark documentation of the femwell project (GPL-3.0,
https://github.com/HelgeGehring/femwell, docs/benchmarks/); only the numerical
values are reproduced here, no femwell code or text. See NOTICE.

Two data sets:

1. RIB_WAVEGUIDES — quasi-TE fundamental mode of a rib waveguide family
   (stated error < 3e-6 in n_eff). Wavelength 1.15 um. Core (rib + slab)
   index 3.44 on a substrate ("box") of index 3.40, air cover (index 1.0).
   Rib width 3 um, total core thickness 1 um; the slab thickness t is varied
   from 0 (strip waveguide) to 0.7 um. Simulation window used by femwell:
   18 um wide, 10 um substrate below, 3 um cover above.

2. DIELECTRIC_CORNERS — "analytically solvable" corner problems (stated error
   < 1e-8). Unit square domain, wavelength 1.5, a square core [0,0.5]^2 in the
   lower-left corner, remaining region is cladding. Perfect-conductor (PEC,
   tangential E = 0) boundaries on the listed sides; the other sides are the
   symmetry counterpart (perfect magnetic conductor). Given as (eps_core,
   eps_clad, pec_sides, n_eff).
"""

from __future__ import annotations

from dataclasses import dataclass, field


CITATION = ("G. R. Hadley, J. Lightwave Technol. 20(7), 1210-1218 (2002), "
            "doi:10.1109/JLT.2002.800370")


@dataclass(frozen=True)
class RibWaveguide:
    slab_thickness_um: float
    neff_quasi_te: float
    # shared geometry
    wavelength_um: float = 1.15
    rib_width_um: float = 3.0
    core_thickness_um: float = 1.0
    n_core: float = 3.44
    n_substrate: float = 3.40
    n_cover: float = 1.0
    uncertainty: float = 3e-6
    citation: str = CITATION


RIB_WAVEGUIDES: tuple[RibWaveguide, ...] = tuple(
    RibWaveguide(t, n) for t, n in [
        (0.0, 3.412022),
        (0.1, 3.412126),
        (0.2, 3.412279),
        (0.3, 3.412492),
        (0.4, 3.412774),
        (0.5, 3.413132),
        (0.6, 3.413571),
        (0.7, 3.414100),
    ]
)


@dataclass(frozen=True)
class DielectricCorner:
    eps_core: float
    eps_clad: float
    pec_sides: tuple[str, ...]
    neff: float
    wavelength: float = 1.5
    domain: tuple[float, float] = (1.0, 1.0)
    core_box: tuple[float, float] = (0.5, 0.5)   # lower-left corner core
    uncertainty: float = 1e-8
    citation: str = CITATION


DIELECTRIC_CORNERS: tuple[DielectricCorner, ...] = (
    DielectricCorner(2.25, 1.0, ("left", "right"), 1.27627404),
    DielectricCorner(8.0, 1.0, ("left", "right"), 2.65679692),
    DielectricCorner(1.0, 2.25, ("left", "top"), 1.387926425),
    DielectricCorner(1.0, 8.0, ("left", "top"), 2.761465320),
)


def rib_neff(slab_thickness_um: float) -> float:
    """Reference quasi-TE n_eff for one of the tabulated slab thicknesses."""
    for rw in RIB_WAVEGUIDES:
        if abs(rw.slab_thickness_um - slab_thickness_um) < 1e-12:
            return rw.neff_quasi_te
    raise KeyError(f"no tabulated rib waveguide with slab thickness {slab_thickness_um}")
