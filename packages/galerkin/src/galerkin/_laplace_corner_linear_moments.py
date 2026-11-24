# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Internal physical moments for admitted interleaved corner-density modes."""
import math

import numpy as np

from . import _laplace_panels as kernel
from . import laplace_two_ground as two
from ._laplace_corner_field import mixed_difference as _mixed_difference
from .laplace_corner import power_panel_quadrature

__all__ = []


def _projection(starts, directions, powers, degree):
    ends = starts + directions
    points = np.concatenate((starts, ends))
    lower, upper = points.min(axis=0), points.max(axis=0)
    grid, _ = kernel.tensor_basis((starts + ends) / 2, lower, upper, degree)
    result = np.zeros((2 * len(starts), degree**2))
    for exponent in np.unique(powers):
        indices = np.flatnonzero(powers == exponent)
        nodes, weights = power_panel_quadrature(float(exponent), degree)
        _, anchor = kernel.tensor_basis(starts[indices], lower, upper, degree)
        linear = math.sqrt(exponent * (exponent + 2)) * ((exponent + 1) / exponent * nodes - 1)
        for parameter, weight, mode in zip(nodes, weights, linear):
            _, basis = kernel.tensor_basis(
                starts[indices] + parameter * directions[indices], lower, upper, degree
            )
            result[2 * indices] += weight * basis
            result[2 * indices + 1] += weight * mode * (basis - anchor)
    masses = np.tile([1.0, 0.0], len(starts))
    if not np.isfinite(result).all() or np.max(abs(result.sum(axis=1) - masses)) > 1e-12:
        raise ValueError("linear interpolation mass is unresolved")
    return grid, result


def _centered_projection(project, matrix, left, right, anchor):
    masses = np.tile([1.0, 0.0], len(project) // 2)
    mixed = _mixed_difference(matrix, left, right, anchor)
    result = project @ mixed @ project.T
    result += (project @ (left - anchor))[:, None] * masses[None, :]
    result += masses[:, None] * (project @ (right - anchor))[None, :]
    result += anchor * masses[:, None] * masses[None, :]
    if not np.isfinite(result).all():
        raise ValueError("linear smooth projection is nonfinite")
    return result


def _smooth(starts, directions, grid, project, width, height, images):
    points = np.concatenate((starts, starts + directions))
    center = (points.min(axis=0) + points.max(axis=0)) / 2
    matrix = two.smooth(grid, grid, width, height, images)
    left = two.smooth(grid, center[None], width, height, images)[:, 0]
    right = two.smooth(center[None], grid, width, height, images)[0]
    anchor = float(two.smooth(center[None], center[None], width, height, images)[0, 0])
    return _centered_projection(project, matrix, left, right, anchor)


def _ground_integrated(starts, directions, powers, width, height, modes, order):
    wave_numbers = np.arange(1, modes + 1) * np.pi / width
    result = np.zeros((2, modes + 1, 2 * len(starts)))

    def values(points):
        x, y = points.T
        k = wave_numbers[:, None]
        common = 2 / width * np.cos(k * x) / (1 - np.exp(-2 * k * height))
        return np.array([
            common * np.exp(-k * y) * (1 - np.exp(-2 * k * (height - y))),
            common * np.exp(-k * (height - y)) * (1 - np.exp(-2 * k * y)),
        ])

    for exponent in np.unique(powers):
        indices = np.flatnonzero(powers == exponent)
        nodes, weights = power_panel_quadrature(float(exponent), order)
        anchor = values(starts[indices])
        local = np.zeros((2, modes, len(indices), 2))
        linear = math.sqrt(exponent * (exponent + 2)) * ((exponent + 1) / exponent * nodes - 1)
        for parameter, weight, mode in zip(nodes, weights, linear):
            value = values(starts[indices] + parameter * directions[indices])
            local[:, :, :, 0] += weight * value
            local[:, :, :, 1] += weight * mode * (value - anchor)
        result[:, 1:, 2 * indices] = local[:, :, :, 0]
        result[:, 1:, 2 * indices + 1] = local[:, :, :, 1]
        mean = exponent / (exponent + 1)
        first_moment = math.sqrt(exponent) / ((exponent + 1) * math.sqrt(exponent + 2))
        y, dy = starts[indices, 1], directions[indices, 1]
        result[0, 0, 2 * indices] = (1 - (y + mean * dy) / height) / width
        result[1, 0, 2 * indices] = (y + mean * dy) / (height * width)
        result[0, 0, 2 * indices + 1] = -dy * first_moment / (height * width)
        result[1, 0, 2 * indices + 1] = dy * first_moment / (height * width)
    if not np.isfinite(result).all():
        raise ValueError("linear ground moments are nonfinite")
    return result


# Public names of helpers shared with other galerkin panel modules (tests/galerkin/test_layers.py).
ground_integrated = _ground_integrated
projection = _projection
smooth = _smooth
