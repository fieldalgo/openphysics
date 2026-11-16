# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded two-ground fields with interleaved physical corner-density modes."""
import math

import numpy as np
from scipy.linalg import cho_factor, cho_solve

from . import laplace_two_ground as two
from ._laplace_corner_field import _gram_checks, _require
from ._laplace_corner_linear_moments import _ground_integrated, _projection, _smooth
from .dense_residual import bounded_dense_residual
from .laplace_corner import power_panel_linear_gram
from .laplace_corner_linear_assembly import assemble_linear_corner_half_space


def solve_two_ground_linear_corner_rectangle_edges(
    polygons, *, width, height, panels_per_edge=64, ground_modes=256,
    interpolation_degree=24,
):
    """Solve one or two all-active convex conductors in a homogeneous rectangle.

    Coordinates and rectangle dimensions are metres. Reuse the existing
    geometry admission, grounded bottom/top planes and zero side normal
    flux. Conductor voltage bases define the normalized current responses.
    All supplied conductors are active; there is no fixed-ground or floating selection.
    Even 16..512 subdivisions give n-6 physical panels per polygon edge;
    at most 512 physical panels (1024 density modes) are admitted. Each panel
    has a constant-mass and a zero-mass linear power mode.

    Explicit partitioned mixed blocks, smooth20/24 and ground16/32 rules
    retain physical weights. Normalize solved charges before exact physical
    squared-density Gram products. Residual, energy, reciprocity, current,
    partition and numerical refinement checks retain1e-10; require condition
    bound below1e10. Ground modes are even64..4096, with half/full comparison;
    interpolation degree is fixed24. There are no retries or coarser fallbacks.

    Return the existing immutable TwoGroundRectangleEdgesResult contract.
    Its whole.panel_count counts physical panels; density DOF is twice that
    number. Current Gram has units1/m and integrated currents are unitless.
    Faces follow admitted CCW order. No finite-resolution result alone proves
    panel/outer convergence or physical accuracy. The medium is homogeneous;
    dielectric-interface corners and finite-metal diffusion are absent.
    Existing solvers are unchanged.
    """
    if not isinstance(polygons, (list, tuple)) or not 1 <= len(polygons) <= 2:
        raise ValueError("linear corner field requires one or two all-active conductors")
    width, height = two._positive(width, "width"), two._positive(height, "height")
    count = two._integer(panels_per_edge, "panels_per_edge", 16, 512)
    modes = two._integer(ground_modes, "ground_modes", 64, 4096)
    degree = two._integer(interpolation_degree, "interpolation_degree", 24, 24)
    if count % 2 or modes % 2:
        raise ValueError("panel subdivisions and ground modes must be even")
    half = assemble_linear_corner_half_space(
        polygons, width=width, height=height, panels_per_edge=count
    )
    geometry = half.geometry
    starts, directions = geometry.normalized_starts, geometry.normalized_directions
    powers, owners, faces = geometry.exponents, geometry.owners, geometry.faces
    panels, conductors = geometry.panel_count, len(polygons)
    unit, w, h = geometry.length_unit_m, geometry.normalized_width, geometry.normalized_height
    images = max(8, int(np.ceil(h / w * np.log(1e14) / np.pi)) + 1)
    matrices, reciprocity = [], []
    for base, d, image_count in zip(
        (half.coarse_matrix, half.matrix), (degree - 4, degree), (images, images + 2)
    ):
        grid, project = _projection(starts, directions, powers, d)
        raw = base + _smooth(starts, directions, grid, project, w, h, image_count)
        if not np.isfinite(raw).all():
            raise ValueError("linear corner field matrix must be finite")
        reciprocity.append(float(np.max(abs(raw - raw.T)) / np.max(abs(raw))))
        matrices.append((raw + raw.T) / 2)
    matrix_error = float(np.max(abs(matrices[0] - matrices[1])) / np.max(abs(matrices[1])))
    _require(max(matrix_error, *reciprocity), "linear matrix refinement/reciprocity failed")
    matrix = matrices[1]
    factor = cho_factor(matrix)
    inverse = cho_solve(factor, np.eye(2 * panels))
    condition = float(np.linalg.norm(matrix, np.inf) * np.linalg.norm(inverse, np.inf))
    if not np.isfinite(condition) or condition >= 1e10:
        raise ValueError("linear corner condition bound exceeded")
    values = np.zeros((2 * panels, conductors))
    values[::2] = (owners[:, None] == np.arange(conductors)).astype(float)
    rhs = 2 * np.pi * values
    charges = cho_solve(factor, rhs)
    for _ in range(2):
        charges += cho_solve(factor, bounded_dense_residual(matrix, charges, rhs))
    residual = float(np.max(abs(bounded_dense_residual(matrix, charges, rhs))) / (2 * np.pi))
    direct = float(np.max(abs(matrix @ charges - rhs)) / (2 * np.pi))
    capacitance = values.T @ charges
    energy = two._entrywise_relative(charges.T @ matrix @ charges / (2 * np.pi), capacitance)
    cap_reciprocity = two._entrywise_relative(capacitance, capacitance.T)
    _require(max(residual, direct, energy, cap_reciprocity), "linear capacitance consistency failed")
    np.linalg.cholesky((capacitance + capacitance.T) / 2)
    currents = charges @ np.linalg.inv(capacitance)
    local = currents.reshape(panels, 2, conductors)
    grams = np.array([power_panel_linear_gram(length, power)
                      for length, power in zip(geometry.lengths_m, powers)])
    parts = np.array([[
        [math.fsum(local[k, a, i] * grams[k, a, b] * local[k, b, j]
                   for a in range(2) for b in range(2)) for j in range(conductors)]
        for i in range(conductors)] for k in range(panels)])

    def accumulated(indices):
        return np.array([[math.fsum(parts[k, i, j] for k in indices)
                          for j in range(conductors)] for i in range(conductors)])

    face_parts = np.array([accumulated(np.flatnonzero(faces == face)) for face in np.unique(faces)])
    whole_parts = np.array([accumulated(np.flatnonzero(owners == owner)) for owner in range(conductors)])
    integrals = np.array([local[owners == owner, 0, :].sum(axis=0) for owner in range(conductors)])
    face_integrals = np.array([local[faces == face, 0, :].sum(axis=0) for face in np.unique(faces)])
    coefficients = [-_ground_integrated(starts, directions, powers, w, h, modes, order) @ currents
                    for order in (16, 32)]

    def ground_parts(coefficient):
        return w / unit * (
            np.einsum("bi,bj->bij", coefficient[:, 0], coefficient[:, 0])
            + .5 * np.einsum("bni,bnj->bij", coefficient[:, 1:], coefficient[:, 1:])
        )

    planes = ground_parts(coefficients[1])
    ground_error = two._entrywise_relative(ground_parts(coefficients[0]), planes)
    mode_error = two._entrywise_relative(ground_parts(coefficients[1][:, :modes // 2 + 1]), planes)
    ground_integrals = w * coefficients[1][:, 0]
    current_error = max(float(np.max(abs(integrals - np.eye(conductors)))),
                        float(np.max(abs(ground_integrals.sum(axis=0) + integrals.sum(axis=0)))))
    _require(max(ground_error, mode_error, current_error), "linear ground/current consistency failed")
    first = np.r_[0, np.flatnonzero(faces[1:] != faces[:-1]) + 1]
    last = np.r_[first[1:] - 1, len(faces) - 1]
    edge_owners = owners[first]
    combined = np.array([face_parts[edge_owners == owner].sum(axis=0) for owner in range(conductors)])
    partition = two._entrywise_relative(combined, whole_parts)
    summed_integrals = np.array([face_integrals[edge_owners == owner].sum(axis=0)
                                 for owner in range(conductors)])
    partition_current = float(np.max(abs(summed_integrals - integrals)))
    _require(max(partition, partition_current), "linear face partition failed")
    all_parts = np.concatenate((whole_parts, planes))
    symmetry, minimum = _gram_checks(np.concatenate((all_parts, face_parts)))
    whole = two.TwoGroundRectangleResult(
        capacitance, all_parts, np.concatenate((integrals, ground_integrals)),
        panels, condition, max(*reciprocity, cap_reciprocity, symmetry),
        max(residual, direct, energy), max(current_error, partition_current),
        max(matrix_error, half.quadrature_error), max(ground_error, mode_error), minimum,
    )
    return two.TwoGroundRectangleEdgesResult(
        whole, edge_owners, geometry.normalized_anchors[first] * unit,
        geometry.normalized_anchors[last] * unit, face_parts, face_integrals, partition,
    )


__all__ = ["solve_two_ground_linear_corner_rectangle_edges"]
