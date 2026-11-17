# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded two-ground fields with interleaved physical corner-density modes."""
import math

import numpy as np
from scipy.linalg import cho_factor, cho_solve

from galerkin import laplace_two_ground as two
from galerkin._laplace_corner_field import _gram_checks, _require
from galerkin._laplace_corner_harmonic_moments import _ground_integrated, _projection, _smooth
from galerkin.dense_residual import bounded_dense_residual
from galerkin.laplace_corner_harmonic import power_panel_harmonic_gram
from ._laplace_corner_compact_harmonic_assembly import _assemble_compact_harmonic_corner_half_space as assemble_harmonic_half_space


def solve_two_ground_harmonic_corner_three_active_edges(
    polygons, *, width, height, panels_per_edge=48, ground_modes=256,
    interpolation_degree=24,
):
    """Solve a bounded two-ground static field for exactly three active conductors.

    Coordinates are metres; convex disjoint polygons are strictly interior to
    the rectangle. Upper/lower planes are grounded, side walls use the existing
    homogeneous Neumann contract. All three polygons supply independent active
    voltage bases; fixed-potential internal guards are not accepted here.

    Two static spatial density modes per physical panel retain corner powers
    and physical Gram weights. Even10..512 subdivisions leave n-6 panels per
    edge; at most512 physical panels/1024 density modes are admitted. Ground
    modes are even64..4096, interpolation degree24. The default48 subdivisions
    fits three quadrilaterals; more vertices require explicit smaller controls.

    Return dimensionless capacitance per permittivity, per-metre whole/edge
    current Grams, signed current integrals and immutable geometry snapshots.
    Numerical refinements, residual/energy/reciprocity/current/partition gates
    stay1e-10 and condition bound below1e10. These internal checks do not replace
    independent panel/outer comparisons, absolute accuracy or measurement.
    This API does not model longitudinal variation, frequency dispersion or
    grounded finite guards. Existing solvers and controls remain unchanged.
    """
    if not isinstance(polygons, (list, tuple)) or len(polygons) != 3:
        raise ValueError("harmonic field requires exactly three active conductors")
    signals = (0, 1, 2)
    width, height = two._positive(width, "width"), two._positive(height, "height")
    count = two._integer(panels_per_edge, "panels_per_edge", 10, 512)
    modes = two._integer(ground_modes, "ground_modes", 64, 4096)
    degree = two._integer(interpolation_degree, "interpolation_degree", 24, 24)
    if count % 2 or modes % 2:
        raise ValueError("panel subdivisions and ground modes must be even")
    half = assemble_harmonic_half_space(
        polygons, width=width, height=height, panels_per_edge=count
    )
    geometry = half.geometry
    starts, directions = geometry.normalized_starts, geometry.normalized_directions
    powers, owners, faces = geometry.exponents, geometry.owners, geometry.faces
    panels, conductors = geometry.panel_count, len(signals)
    boundaries = len(polygons)
    unit, w, h = geometry.length_unit_m, geometry.normalized_width, geometry.normalized_height
    images = max(8, int(np.ceil(h / w * np.log(1e14) / np.pi)) + 1)
    matrices, reciprocity = [], []
    for base, d, image_count in zip(
        (half.coarse_matrix, half.matrix), (degree - 4, degree), (images, images + 2)
    ):
        grid, project = _projection(starts, directions, powers, d)
        raw = base + _smooth(starts, directions, grid, project, w, h, image_count)
        if not np.isfinite(raw).all():
            raise ValueError("harmonic corner field matrix must be finite")
        reciprocity.append(float(np.max(abs(raw - raw.T)) / np.max(abs(raw))))
        matrices.append((raw + raw.T) / 2)
    matrix_error = float(np.max(abs(matrices[0] - matrices[1])) / np.max(abs(matrices[1])))
    _require(max(matrix_error, *reciprocity), "harmonic matrix refinement/reciprocity failed")
    matrix = matrices[1]
    factor = cho_factor(matrix)
    inverse = cho_solve(factor, np.eye(2 * panels))
    condition = float(np.linalg.norm(matrix, np.inf) * np.linalg.norm(inverse, np.inf))
    if not np.isfinite(condition) or condition >= 1e10:
        raise ValueError("harmonic corner condition bound exceeded")
    values = np.zeros((2 * panels, conductors))
    values[::2] = (owners[:, None] == np.asarray(signals)).astype(float)
    rhs = 2 * np.pi * values
    charges = cho_solve(factor, rhs)
    for _ in range(2):
        charges += cho_solve(factor, bounded_dense_residual(matrix, charges, rhs))
    residual = float(np.max(abs(bounded_dense_residual(matrix, charges, rhs))) / (2 * np.pi))
    direct = float(np.max(abs(matrix @ charges - rhs)) / (2 * np.pi))
    capacitance = values.T @ charges
    energy = two._entrywise_relative(charges.T @ matrix @ charges / (2 * np.pi), capacitance)
    cap_reciprocity = two._entrywise_relative(capacitance, capacitance.T)
    _require(max(residual, direct, energy, cap_reciprocity), "harmonic capacitance consistency failed")
    np.linalg.cholesky((capacitance + capacitance.T) / 2)
    currents = charges @ np.linalg.inv(capacitance)
    local = currents.reshape(panels, 2, conductors)
    grams = np.array([power_panel_harmonic_gram(length, power)
                      for length, power in zip(geometry.lengths_m, powers)])
    parts = np.array([[
        [math.fsum(local[k, a, i] * grams[k, a, b] * local[k, b, j]
                   for a in range(2) for b in range(2)) for j in range(conductors)]
        for i in range(conductors)] for k in range(panels)])

    def accumulated(indices):
        return np.array([[math.fsum(parts[k, i, j] for k in indices)
                          for j in range(conductors)] for i in range(conductors)])

    face_parts = np.array([accumulated(np.flatnonzero(faces == face)) for face in np.unique(faces)])
    whole_parts = np.array([accumulated(np.flatnonzero(owners == owner)) for owner in range(boundaries)])
    integrals = np.array([local[owners == owner, 0, :].sum(axis=0) for owner in range(boundaries)])
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
    current_error = max(float(np.max(abs(integrals[list(signals)] - np.eye(conductors)))),
                        float(np.max(abs(ground_integrals.sum(axis=0) + integrals.sum(axis=0)))))
    _require(max(ground_error, mode_error, current_error), "harmonic ground/current consistency failed")
    first = np.r_[0, np.flatnonzero(faces[1:] != faces[:-1]) + 1]
    last = np.r_[first[1:] - 1, len(faces) - 1]
    edge_owners = owners[first]
    combined = np.array([face_parts[edge_owners == owner].sum(axis=0) for owner in range(boundaries)])
    partition = two._entrywise_relative(combined, whole_parts)
    summed_integrals = np.array([face_integrals[edge_owners == owner].sum(axis=0)
                                 for owner in range(boundaries)])
    partition_current = float(np.max(abs(summed_integrals - integrals)))
    _require(max(partition, partition_current), "harmonic face partition failed")
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


__all__ = ["solve_two_ground_harmonic_corner_three_active_edges"]
