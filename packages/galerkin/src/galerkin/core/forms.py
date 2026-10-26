# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Assembling element contributions into global matrices and vectors.

An element kernel (``galerkin.core.kernels``, or a physics module's own)
returns one small matrix or vector per cell, in the caller's array library,
with no loop over cells. These functions place them:

- ``matrix`` scatters ``(T, i, j)`` element matrices into a ``CooMatrix``
  with the cell-to-DOF tables as its static pattern;
- ``vector`` scatter-adds ``(T, i)`` element vectors;
- ``integrate_bilinear`` and ``integrate_linear`` build element matrices and
  vectors from basis values at quadrature points, for kernels that have no
  closed form.

The pattern and the order of additions are those the hand-written assembly in
``galerkin.assembly``, ``assembly3d``, ``edge`` and ``edge3d`` uses, so a
closed-form kernel assembled here reproduces those matrices bit for bit on NumPy.
"""
import numpy as np

from .backend import namespace, scatter_add
from .sparse import CooMatrix


def _dofs(dofs):
    dofs = np.asarray(dofs)
    if dofs.ndim != 2 or dofs.dtype.kind not in "iu":
        raise ValueError("a cell-to-DOF table must be a 2-D integer array (cells, local DOFs)")
    return dofs


def matrix(row_dofs, col_dofs, element, shape):
    """Global matrix from element matrices ``element[t, i, j]``.

    Entry ``(row_dofs[t, i], col_dofs[t, j])`` receives ``element[t, i, j]``;
    contributions to the same entry add.
    """
    row_dofs, col_dofs = _dofs(row_dofs), _dofs(col_dofs)
    cells, ni = row_dofs.shape
    nj = col_dofs.shape[1]
    if col_dofs.shape[0] != cells or tuple(element.shape) != (cells, ni, nj):
        raise ValueError(f"element matrices have shape {tuple(element.shape)}, "
                         f"expected {(cells, ni, nj)} from the DOF tables")
    xp = namespace(element)
    return CooMatrix(np.repeat(row_dofs, nj, axis=1).ravel(), np.tile(col_dofs, (1, ni)).ravel(),
                     xp.reshape(element, (-1,)), shape)


def vector(dofs, element, size, *, order="flat"):
    """Global vector from element vectors ``element[t, i]`` added at ``dofs[t, i]``.

    ``order`` fixes the order of floating-point additions: ``"flat"`` adds all
    contributions in cell-major order in one pass; ``"columns"`` adds local DOF 0
    of every cell, then local DOF 1, and so on (as three ``np.add.at`` calls do).
    """
    dofs = _dofs(dofs)
    if tuple(element.shape) != dofs.shape:
        raise ValueError(f"element vectors have shape {tuple(element.shape)}, expected {dofs.shape}")
    xp = namespace(element)
    if order == "flat":
        return scatter_add(xp, size, dofs.ravel(), xp.reshape(element, (-1,)))
    if order != "columns":
        raise ValueError("order must be 'flat' or 'columns'")
    out = None
    for k in range(dofs.shape[1]):              # local DOFs, never cells
        out = scatter_add(xp, size, dofs[:, k], element[:, k], base=out)
    return out


def integrate_bilinear(test, trial, weights, measure, coefficient=None):
    """Element matrices ``sum_q w_q c_tq <test_tqi, trial_tqj> measure_t``.

    ``test`` and ``trial`` are basis values or derivatives at quadrature points,
    shape ``(T, Q, i, *components)`` and ``(T, Q, j, *components)``; the
    components are contracted. ``weights`` (Q,) sum to 1 on the reference cell,
    ``measure`` (T,) is each cell's area or volume, ``coefficient`` is None, a
    scalar, (T,) or (T, Q).
    """
    xp = namespace(test, trial, coefficient)
    components = test.ndim - 3
    if trial.ndim - 3 != components:
        raise ValueError("test and trial must have the same component shape")
    t_flat = xp.reshape(test, (*test.shape[:3], -1))
    u_flat = xp.reshape(trial, (*trial.shape[:3], -1))
    pairs = xp.sum(t_flat[:, :, :, None, :] * u_flat[:, :, None, :, :], axis=-1)   # (T, Q, i, j)
    w = xp.asarray(weights)[None, :]
    if coefficient is not None:
        c = xp.asarray(coefficient)
        w = w * (c[:, None] if c.ndim == 1 else c)
    return xp.sum(w[:, :, None, None] * pairs, axis=1) * xp.asarray(measure)[:, None, None]


def integrate_linear(test, weights, measure, values):
    """Element vectors ``sum_q w_q f_tq test_tqi measure_t``; ``values`` is (T, Q) or a scalar."""
    xp = namespace(test, values)
    f = xp.asarray(values)
    w = xp.asarray(weights)[None, :] * (f if f.ndim == 2 else f[..., None] if f.ndim == 1 else f)
    return xp.sum(w[:, :, None] * test, axis=1) * xp.asarray(measure)[:, None]
