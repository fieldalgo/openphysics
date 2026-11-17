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

1. rib_waveguides() — quasi-TE fundamental mode of a rib waveguide family
   (stated error < 3e-6 in n_eff). Wavelength 1.15 um. Core (rib + slab)
   index 3.44 on a substrate ("box") of index 3.40, air cover (index 1.0).
   Rib width 3 um, total core thickness 1 um; the slab thickness t is varied
   from 0 (strip waveguide) to 0.7 um. Simulation window used by femwell:
   18 um wide, 10 um substrate below, 3 um cover above.

2. dielectric_corners() — "analytically solvable" corner problems (stated error
   < 1e-8). Unit square domain, wavelength 1.5, a square core [0,0.5]^2 in the
   lower-left corner, remaining region is cladding. Perfect-conductor (PEC,
   tangential E = 0) boundaries on the listed sides; the other sides are the
   symmetry counterpart (perfect magnetic conductor).

Units and names (galerkin step, L3 commit 11e; spec D44). The published numbers are
stored as published, with their unit, in the private ``refsol._published``: the rib
lengths in micrometres, the corner problems dimensionless. The accessors return SI
records under registry names, computed at run time by a stated rule:

- ``rib_waveguides()``: each micrometre value becomes metres by the decimal rule
  m = float(Fraction(repr(value)) / 10**6), the double nearest the exact decimal
  (0.3 um -> 3e-07 m, 1.15 um -> 1.15e-06 m; the reverse rule of spec D31 gives the
  published micrometre doubles back exactly).
- ``dielectric_corners()``: the dimensionless problem read in metres (a unit square of
  side 1 m, wavelength 1.5 m): the doubles are the published ones, and the problem
  depends only on the ratios.
- ``rib_neff(*, thickness)``: the slab thickness in m, matched to a tabulated case to
  a relative 1e-12 (the former absolute 1e-12 um match on the micrometre value).

The stated errors (3e-6 and 1e-8 in n_eff) stay with the published records.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

import numpy as np

from . import _published
from ._checks import refuse_text

__all__ = ["CITATION", "RibWaveguide", "rib_waveguides", "rib_neff", "DielectricCorner", "dielectric_corners"]


CITATION = _published.HADLEY_2002


@dataclass(frozen=True, kw_only=True)
class RibWaveguide:
    """One of Hadley's rib waveguides in SI.

    thickness: (slab, core), the slab thickness t and the total core (rib) thickness, m;
    length: the rib width, m; vacuum_wavelength: m; refractive_index: (substrate, core,
    cover) by increasing height; effective_index: Hadley's quasi-TE n_eff; source: the citation.
    """
    thickness: tuple[float, float]
    length: float
    vacuum_wavelength: float
    refractive_index: tuple[float, float, float]
    effective_index: float
    source: str


def _metres(micrometres):
    """The decimal rule: the double nearest the exact decimal value times 1e-6."""
    return float(Fraction(repr(float(micrometres))) / 10 ** 6)


def rib_waveguides() -> tuple[RibWaveguide, ...]:
    """Hadley's eight rib waveguides in SI, computed from the published micrometre literals at run time."""
    record = _published.RIB_WAVEGUIDES
    assert record.unit == "um"
    core, width, wavelength = (_metres(v) for v in (record.core_thickness, record.rib_width, record.wavelength))
    return tuple(RibWaveguide(thickness=(_metres(t), core), length=width, vacuum_wavelength=wavelength,
                              refractive_index=(record.n_substrate, record.n_core, record.n_cover),
                              effective_index=neff, source=record.source)
                 for t, neff in record.table)


@dataclass(frozen=True, kw_only=True)
class DielectricCorner:
    """One of Hadley's dielectric-corner problems, read in metres (dimensionless as published).

    relative_permittivity: (core, cladding); pec_sides: the sides of the square carrying PEC;
    effective_index: Hadley's n_eff; vacuum_wavelength: m; box_size: the domain [0, W] x [0, H], m;
    upper_corner_position: the core's corner (its box is [0, cw] x [0, ch]), m; source: the citation.
    """
    relative_permittivity: tuple[float, float]
    pec_sides: tuple[str, ...]
    effective_index: float
    vacuum_wavelength: float
    box_size: tuple[float, float]
    upper_corner_position: tuple[float, float]
    source: str


def dielectric_corners() -> tuple[DielectricCorner, ...]:
    """Hadley's four corner problems; the dimensionless published numbers read in metres."""
    out = []
    for case in _published.DIELECTRIC_CORNERS:
        assert case.unit == "1"
        out.append(DielectricCorner(relative_permittivity=(case.eps_core, case.eps_clad), pec_sides=case.pec_sides,
                                    effective_index=case.neff, vacuum_wavelength=case.wavelength,
                                    box_size=case.domain, upper_corner_position=case.core_box, source=case.source))
    return tuple(out)


def rib_neff(*, thickness) -> float:
    """Reference quasi-TE effective index for one of the tabulated slab thicknesses (``thickness``, m)."""
    refuse_text(thickness=thickness)
    if np.ndim(thickness) != 0 or np.iscomplexobj(thickness) or not np.isfinite(float(thickness)):
        raise ValueError("thickness must be the slab thickness, one finite number in m")
    slab = float(thickness)
    for rw in rib_waveguides():
        if abs(rw.thickness[0] - slab) <= 1e-12 * abs(rw.thickness[0]):
            return rw.effective_index
    raise KeyError(f"no tabulated rib waveguide with slab thickness {thickness} m")
