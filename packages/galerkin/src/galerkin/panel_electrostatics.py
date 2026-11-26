# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Homogeneous 2D Laplace boundary panels in a rectangle: galerkin's public panel API, in SI.

Nine solvers for convex closed conductors inside an axis-aligned rectangle
[0, width] x [0, height], one per wall condition:

- ``solve_grounded_rectangle``: grounded bottom, zero normal flux on the other walls;
- ``solve_two_ground_rectangle`` and ``solve_two_ground_rectangle_edges``: grounded bottom
  and top, zero normal flux on the side walls; ``solve_two_ground_corner_rectangle_edges``,
  ``solve_two_ground_linear_corner_rectangle_edges`` and the three
  ``solve_two_ground_harmonic_corner_*`` solvers add corner-power densities;
- ``solve_open_rectangle``: zero normal flux on all four walls, with conductors held at
  zero potential (``ground_indices``) as the reference.

Units and names
---------------
The one quantity is ``box_size``, keyword-only: the rectangle's two side lengths
(width, height) in m; the rectangle starts at the origin, as ``box_size`` of
``galerkin.cavity`` does in 3D. ``polygons`` holds each conductor's vertices in m (a
positional data argument). ``panels_per_edge``, ``ground_modes`` and
``interpolation_degree`` are discretization counts; ``ground_indices``,
``signal_indices`` and ``signal_index`` select conductors by their index in
``polygons``. Text for ``box_size`` raises ``TypeError``.

The functions are thin: they read ``box_size`` and call the internal solvers of
``galerkin.laplace_boundary``, ``galerkin.laplace_two_ground``,
``galerkin.laplace_open_box`` and ``galerkin.laplace_corner_*_field`` with the
same numbers, so each result is the internal solver's result object, bit for bit.
Those modules stay internal and keep their names (``width``, ``height``,
``grounds``, ``signals``, ``signal``); refusals here name the public arguments.

Results
-------
The four result classes are the internal modules' own frozen records, re-exported
unchanged. ``capacitance_per_permittivity`` is the capacitance matrix per unit
depth divided by the absolute permittivity of the homogeneous medium, which is
dimensionless; multiply by the permittivity in F/m for a capacitance per length.
Their field names are kept as they are (the result-surface check, P3-11, is later).
See docs/packages/galerkin/panel_electrostatics.md.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from numbers import Real

import numpy as np

from . import laplace_boundary as _boundary
from . import laplace_corner_harmonic_field as _harmonic_field
from . import laplace_corner_harmonic_guard_field as _guard_field
from . import laplace_corner_harmonic_single_active_field as _single_active_field
from . import laplace_corner_linear_field as _linear_field
from . import laplace_open_box as _open_box
from . import laplace_two_ground as _two_ground
from ._public import refuse_text
from .laplace_boundary import RectangleBoundaryResult
from .laplace_open_box import OpenRectangleResult
from .laplace_two_ground import TwoGroundRectangleEdgesResult, TwoGroundRectangleResult

__all__ = [
    "RectangleBoundaryResult", "TwoGroundRectangleResult", "TwoGroundRectangleEdgesResult", "OpenRectangleResult",
    "solve_grounded_rectangle", "solve_two_ground_rectangle", "solve_two_ground_rectangle_edges",
    "solve_two_ground_corner_rectangle_edges", "solve_two_ground_linear_corner_rectangle_edges",
    "solve_two_ground_harmonic_corner_three_active_edges", "solve_two_ground_harmonic_corner_guard_edges",
    "solve_two_ground_harmonic_corner_single_active_edges", "solve_open_rectangle",
]

#: the internal solvers' messages name their own arguments; these patterns give the public names instead
_BOX_NAMES = ((r"^width/height must lie in", "box_size: width/height must lie in"),
              (r"^(width|height) must be", r"box_size \1 must be"))


def _side_lengths(box_size):
    """``box_size`` as the (width, height) the internal solvers take, unchanged."""
    refuse_text("box_size", box_size)
    if isinstance(box_size, np.ndarray):
        if box_size.shape != (2,):
            raise ValueError("box_size must hold two side lengths (width, height) in m")
        box_size = box_size.tolist()
    if not isinstance(box_size, Sequence) or len(box_size) != 2:
        raise ValueError("box_size must hold two side lengths (width, height) in m")
    width, height = box_size
    for value in (width, height):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not np.isfinite(float(value)) \
                or float(value) <= 0:
            raise ValueError("box_size must hold two finite positive side lengths (width, height) in m")
    return width, height


def _call(solver, polygons, box_size, renames=(), **kwargs):
    width, height = _side_lengths(box_size)
    try:
        return solver(polygons, width=width, height=height, **kwargs)
    except ValueError as error:
        message = str(error)
        for pattern, public in (*_BOX_NAMES, *renames):
            message = re.sub(pattern, public, message)
        if message == str(error):
            raise
        raise ValueError(message) from error


def solve_grounded_rectangle(polygons, *, box_size, panels_per_edge=32, ground_modes=512,
                             interpolation_degree=10) -> RectangleBoundaryResult:
    """Solve convex closed conductors over a grounded bottom in a rectangle.

    polygons: 1..16 strictly convex, disjoint conductor boundaries strictly inside the
        rectangle, each an (n, 2) array of vertices in m without a closing duplicate.
    box_size: the rectangle's (width, height) in m; it starts at the origin.

    The bottom wall is grounded; the other three walls have zero normal flux. See
    ``galerkin.laplace_boundary.solve_grounded_rectangle`` for the admitted geometry, the
    discretization limits and the consistency gates, which this function applies unchanged.
    """
    return _call(_boundary.solve_grounded_rectangle, polygons, box_size, panels_per_edge=panels_per_edge,
                 ground_modes=ground_modes, interpolation_degree=interpolation_degree)


def solve_two_ground_rectangle(polygons, *, box_size, panels_per_edge=32, ground_modes=128,
                               interpolation_degree=12) -> TwoGroundRectangleResult:
    """Solve convex closed conductors between a grounded bottom and a grounded top.

    box_size: the rectangle's (width, height) in m; the height is the separation of the two
    grounded planes, and the side walls have zero normal flux. Otherwise as
    ``galerkin.laplace_two_ground.solve_two_ground_rectangle``.
    """
    return _call(_two_ground.solve_two_ground_rectangle, polygons, box_size, panels_per_edge=panels_per_edge,
                 ground_modes=ground_modes, interpolation_degree=interpolation_degree)


def solve_two_ground_rectangle_edges(polygons, *, box_size, panels_per_edge=32, ground_modes=128,
                                     interpolation_degree=12) -> TwoGroundRectangleEdgesResult:
    """``solve_two_ground_rectangle`` with the currents of each straight conductor edge.

    As ``galerkin.laplace_two_ground.solve_two_ground_rectangle_edges``.
    """
    return _call(_two_ground.solve_two_ground_rectangle_edges, polygons, box_size, panels_per_edge=panels_per_edge,
                 ground_modes=ground_modes, interpolation_degree=interpolation_degree)


def solve_two_ground_corner_rectangle_edges(polygons, *, box_size, panels_per_edge=128, ground_modes=256,
                                            interpolation_degree=24) -> TwoGroundRectangleEdgesResult:
    """Two grounded planes, one or two all-active conductors, corner-power densities.

    As ``galerkin.laplace_two_ground.solve_two_ground_corner_rectangle_edges``.
    """
    return _call(_two_ground.solve_two_ground_corner_rectangle_edges, polygons, box_size,
                 panels_per_edge=panels_per_edge, ground_modes=ground_modes,
                 interpolation_degree=interpolation_degree)


def solve_two_ground_linear_corner_rectangle_edges(polygons, *, box_size, panels_per_edge=64, ground_modes=256,
                                                   interpolation_degree=24) -> TwoGroundRectangleEdgesResult:
    """Two grounded planes, linear corner-power densities on every conductor edge.

    As ``galerkin.laplace_corner_linear_field.solve_two_ground_linear_corner_rectangle_edges``.
    """
    return _call(_linear_field.solve_two_ground_linear_corner_rectangle_edges, polygons, box_size,
                 panels_per_edge=panels_per_edge, ground_modes=ground_modes,
                 interpolation_degree=interpolation_degree)


def solve_two_ground_harmonic_corner_three_active_edges(polygons, *, box_size, panels_per_edge=48, ground_modes=256,
                                                        interpolation_degree=24) -> TwoGroundRectangleEdgesResult:
    """Two grounded planes, exactly three active conductors, harmonic corner densities.

    As ``galerkin.laplace_corner_harmonic_field.solve_two_ground_harmonic_corner_three_active_edges``.
    """
    return _call(_harmonic_field.solve_two_ground_harmonic_corner_three_active_edges, polygons, box_size,
                 panels_per_edge=panels_per_edge, ground_modes=ground_modes,
                 interpolation_degree=interpolation_degree)


def solve_two_ground_harmonic_corner_guard_edges(polygons, *, signal_indices, box_size, panels_per_edge=48,
                                                 ground_modes=256,
                                                 interpolation_degree=24) -> TwoGroundRectangleEdgesResult:
    """Two grounded planes, two active conductors and one guard held at zero potential.

    signal_indices: two distinct ordered indices in 0..2 of the active conductors; the
        third conductor is the guard.

    As ``galerkin.laplace_corner_harmonic_guard_field.solve_two_ground_harmonic_corner_guard_edges``
    with ``signals=signal_indices``.
    """
    renames = ((r"^signals must", "signal_indices must"), (r"^signal index must", "signal_indices entries must"),
               (r"^signal indices must", "signal_indices must"))
    return _call(_guard_field.solve_two_ground_harmonic_corner_guard_edges, polygons, box_size, renames,
                 signals=signal_indices, panels_per_edge=panels_per_edge, ground_modes=ground_modes,
                 interpolation_degree=interpolation_degree)


def solve_two_ground_harmonic_corner_single_active_edges(polygons, *, signal_index, box_size, panels_per_edge=48,
                                                         ground_modes=256,
                                                         interpolation_degree=24) -> TwoGroundRectangleEdgesResult:
    """Two grounded planes, one active conductor and two guards held at zero potential.

    signal_index: the index in 0..2 of the active conductor.

    As ``galerkin.laplace_corner_harmonic_single_active_field.solve_two_ground_harmonic_corner_single_active_edges``
    with ``signal=signal_index``.
    """
    renames = ((r"^signal index must", "signal_index must"),)
    return _call(_single_active_field.solve_two_ground_harmonic_corner_single_active_edges, polygons, box_size,
                 renames, signal=signal_index, panels_per_edge=panels_per_edge, ground_modes=ground_modes,
                 interpolation_degree=interpolation_degree)


def solve_open_rectangle(polygons, *, box_size, ground_indices, panels_per_edge=32,
                         interpolation_degree=12) -> OpenRectangleResult:
    """Solve convex closed conductors in a rectangle whose four walls have zero normal flux.

    ground_indices: the indices of the conductors held at zero potential (at least one,
        and at least one conductor stays a signal).

    As ``galerkin.laplace_open_box.solve_open_rectangle`` with ``grounds=ground_indices``.
    """
    renames = ((r"^grounds must", "ground_indices must"),)
    return _call(_open_box.solve_open_rectangle, polygons, box_size, renames, grounds=ground_indices,
                 panels_per_edge=panels_per_edge, interpolation_degree=interpolation_degree)
