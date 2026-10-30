# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""sipi — signal- and power-integrity analysis of PCB interconnects.

    from sipi import CrossSection, Layer, Trace
    cs = CrossSection(
        layers=[Layer("FR-4", 0.2e-3, eps_r=4.3, tan_delta=0.02),
                Layer("air", 2e-3)],
        traces=[Trace("sig", x=0.0, width=0.35e-3, y=0.2e-3, thickness=35e-6)],
        width=6e-3)
    p = cs.analyze()
    p.z0, p.eps_eff, p.L, p.C, p.G(1e9)

Signal integrity: quasi-static (quasi-TEM) cross-sections give the
per-unit-length capacitance, inductance and dielectric conductance matrices,
single-line impedance and effective permittivity, and coupled-line modes.
Uniform-line S-parameters accept explicit RLGC.

Power integrity: ``PowerPlane`` solves the DC voltage drop (IR drop) on a
copper plane fed by voltage sources and loaded by current sinks.

High-frequency conductor loss is available in ``sipi.conductor`` with explicit
skin-depth and mesh validity checks. Interior current diffusion, AC PDN impedance
and 3D structures are not implemented.
"""

from .crosssection import CrossSection, Layer, MeshedCrossSection, Trace
from .document import CrossSectionDocument
from .templates import microstrip, stripline, coupled_microstrip, grounded_coplanar
from .design import DesignEvaluation, ImpedanceDesign, GoalSeekError, seek_impedance
from .plane import (COPPER_CONDUCTIVITY, IRDropResult, PowerPlane, Sink, Source, circle, edge,
                    rectangle_outline)
from .quasistatic import LineParameters, capacitance_matrix, line_parameters

from .network import LineNetwork, rlgc_network, quasistatic_network

__version__ = "0.1.0"
__all__ = ["CrossSection", "Layer", "Trace", "MeshedCrossSection", "LineParameters",
           "LineNetwork", "rlgc_network", "quasistatic_network",
           "capacitance_matrix", "line_parameters", "CrossSectionDocument",
           "microstrip", "stripline", "coupled_microstrip", "grounded_coplanar",
           "DesignEvaluation", "ImpedanceDesign", "GoalSeekError", "seek_impedance",
           "PowerPlane", "Source", "Sink", "IRDropResult", "circle", "edge", "rectangle_outline",
           "COPPER_CONDUCTIVITY", "__version__"]
