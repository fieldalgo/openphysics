# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded interleaved linear-power Green matrices above one grounded line."""
from dataclasses import dataclass
import math

import numpy as np

from .laplace_corner import (
    power_panel_linear_self_log,
    power_panel_linear_separated_log,
    power_panel_linear_shared_vertex_log,
)
from .laplace_corner_assembly import _offsets
from .laplace_corner_partitioned import power_panel_linear_constant_log_partitioned
from .laplace_corner_geometry import (
    CornerPanelGeometry,
    _immutable,
    prepare_two_ground_corner_panels,
)


def _block(geometry, i, j, p, q, image=False):
    first = geometry["direction"][i]
    second = geometry["direction"][j].copy()
    offset = _offsets(geometry, i, j, image)[0]
    if image:
        second *= np.array([1.0, -1.0])
    if not image and i == j:
        value = power_panel_linear_self_log(math.hypot(*first), p)
        return value, value
    if q == 1:
        signs = np.ones(2)
        if not image and geometry["ends"][j] in (
            geometry["starts"][i], geometry["ends"][i]
        ):
            second = -second
            offset = (np.zeros(2) if geometry["ends"][j] == geometry["starts"][i]
                      else first.copy())
            signs[1] = -1
        value = power_panel_linear_constant_log_partitioned(first, second, offset, p)
        return (value.coarse_mean_log_distance * signs[None, :],
                value.mean_log_distance * signs[None, :])
    if p == 1:
        # For an image, reflection of both reversed vectors maps the pair
        # back above the grounded line without changing its mode parameters.
        coarse, fine = _block(geometry, j, i, q, p, image)
        return coarse.T, fine.T
    if not image and geometry["starts"][i] == geometry["starts"][j]:
        value = power_panel_linear_shared_vertex_log(first, second, p, q)
    else:
        value = power_panel_linear_separated_log(first, second, offset, p, q)
    return value.coarse_mean_log_distance, value.mean_log_distance


def _assemble(geometry):
    count = geometry.panel_count
    local = dict(
        anchor=geometry.normalized_anchors,
        local=geometry.normalized_local_starts,
        direction=geometry.normalized_directions,
        starts=geometry.endpoint_ids[:, 0],
        ends=geometry.endpoint_ids[:, 1],
    )
    coarse = np.empty((2 * count, 2 * count))
    fine = np.empty_like(coarse)
    for i in range(count):
        for j in range(count):
            try:
                args = (local, i, j, geometry.exponents[i], geometry.exponents[j])
                real0, real1 = _block(*args)
                image0, image1 = _block(*args, image=True)
            except ValueError as exc:
                raise ValueError(f"linear panel pair {i}/{j}: {exc}") from exc
            rows, columns = slice(2 * i, 2 * i + 2), slice(2 * j, 2 * j + 2)
            coarse[rows, columns] = image0 - real0
            fine[rows, columns] = image1 - real1
    return coarse, fine


@dataclass(frozen=True)
class LinearCornerHalfSpaceMatrix:
    """Dimensionless raw Green blocks with two modes per physical panel.

    Density index 2*i is the constant-mass mode; 2*i+1 is the zero-mass
    linear mode on geometry panel i. There is no symmetry averaging, charge
    solve, upper-plane or side-wall correction. The rectangle admits and
    normalizes geometry only; the Green function contains the y=0 ground.
    """

    geometry: CornerPanelGeometry
    coarse_matrix: np.ndarray
    matrix: np.ndarray
    quadrature_error: float
    reciprocity_error: float

    def __post_init__(self):
        for name in ("coarse_matrix", "matrix"):
            object.__setattr__(self, name, _immutable(getattr(self, name)))


def assemble_linear_corner_half_space(polygons, *, width, height, panels_per_edge=16):
    """Assemble bounded, two-mode power-panel half-space Green matrices.

    Reuse convex, disjoint, strictly interior geometry admission in metres,
    even 16..512 subdivisions, and the existing merge of the first four
    cubic intervals at each edge end. Admit at most 512 physical panels
    (1024 density modes). Upper-plane and side-wall fields are absent.

    Exact self, shared-origin, separated and explicitly partitioned mixed
    unit-source blocks keep
    physical basis masses and refinement evidence. Reversing a unit-power
    source endpoint flips its linear mode; a nonunit singularity is never
    reversed. Refuse unresolved pairs, normalized refinement or raw
    reciprocity above 1e-10, before any caller's symmetry averaging.
    Assembly checks alone do not establish field, panel-convergence or
    other-platform accuracy. Existing assemblers and solvers are unchanged.
    """
    geometry = prepare_two_ground_corner_panels(
        polygons, width=width, height=height, panels_per_edge=panels_per_edge
    )
    if geometry.panel_count > 512:
        raise ValueError("linear half-space assembly exceeds 512 physical panels")
    coarse, fine = _assemble(geometry)
    expected = (2 * geometry.panel_count,) * 2
    if (coarse.shape != expected or fine.shape != expected
            or not np.isfinite(coarse).all() or not np.isfinite(fine).all()):
        raise ValueError("linear half-space matrices must have finite two-mode shape")
    magnitude = float(np.max(abs(fine)))
    if not magnitude > 0:
        raise ValueError("linear half-space matrix scale must be positive")
    error = float(np.max(abs(fine - coarse)) / magnitude)
    reciprocity = max(
        float(np.max(abs(matrix - matrix.T)) / np.max(abs(matrix)))
        if np.max(abs(matrix)) > 0 else float("inf")
        for matrix in (coarse, fine)
    )
    if max(error, reciprocity) > 1e-10:
        raise ValueError("linear half-space quadrature or raw reciprocity failed")
    return LinearCornerHalfSpaceMatrix(geometry, coarse, fine, error, reciprocity)


__all__ = ["LinearCornerHalfSpaceMatrix", "assemble_linear_corner_half_space"]
