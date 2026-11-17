# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Guided modes of a waveguide cross-section: galerkin's public mode module.

The full-vector mode kernels ``solve_modes`` and ``assemble_mode_system`` (consistent
units, exp(+i omega t); their formulation is in the package-private
``galerkin._waveguide_kernels``) and the mode-overlap kernels are internal since the
galerkin step (L3 commit 11): ``galerkin.kernels`` re-exports them unchanged, and no
public name equals one of theirs. This module keeps the static-root tolerance of the
eigensolve and the warning of a degenerate mode's derivative.
"""

from __future__ import annotations

from ._waveguide_kernels import STATIC_ROOT_TOL
from .core.eigen import DEGENERATE_GAP, DegenerateModeWarning  # noqa: F401 (DEGENERATE_GAP is read here, as before)

__all__ = ["STATIC_ROOT_TOL", "DegenerateModeWarning"]
