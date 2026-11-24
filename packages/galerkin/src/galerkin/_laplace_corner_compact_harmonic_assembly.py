# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Private bounded compact half-space assembly; original public API is unchanged."""
import numpy as np
from ._laplace_corner_compact_geometry import prepare_compact_corner_panels as _prepare_compact_corner_panels
from .laplace_corner_harmonic_assembly import HarmonicCornerHalfSpaceMatrix, assemble as _assemble

__all__ = []


def _assemble_compact_harmonic_corner_half_space(polygons, *, width, height, panels_per_edge=16):
    """Private compact geometry with unchanged raw physical blocks and numerical gates.

    Even10..512 subdivisions leave n-6 physical panels per edge. Admit at most
    512physical panels/1024density modes. No field or accuracy qualification
    follows from these raw half-space blocks. Existing public controls remain.
    """
    geometry = _prepare_compact_corner_panels(
        polygons, width=width, height=height, panels_per_edge=panels_per_edge
    )
    if geometry.panel_count > 512:
        raise ValueError("harmonic half-space assembly exceeds 512 physical panels")
    coarse, fine = _assemble(geometry)
    expected = (2 * geometry.panel_count,) * 2
    if (coarse.shape != expected or fine.shape != expected
            or not np.isfinite(coarse).all() or not np.isfinite(fine).all()):
        raise ValueError("harmonic half-space matrices must have finite two-mode shape")
    magnitude = float(np.max(abs(fine)))
    if not magnitude > 0:
        raise ValueError("harmonic half-space matrix scale must be positive")
    error = float(np.max(abs(fine - coarse)) / magnitude)
    reciprocity = max(
        float(np.max(abs(matrix - matrix.T)) / np.max(abs(matrix)))
        if np.max(abs(matrix)) > 0 else float("inf")
        for matrix in (coarse, fine)
    )
    if max(error, reciprocity) > 1e-10:
        raise ValueError("harmonic half-space quadrature or raw reciprocity failed")
    return HarmonicCornerHalfSpaceMatrix(geometry, coarse, fine, error, reciprocity)


# Public names of helpers shared with other galerkin panel modules (tests/galerkin/test_layers.py).
assemble_compact_harmonic_corner_half_space = _assemble_compact_harmonic_corner_half_space
