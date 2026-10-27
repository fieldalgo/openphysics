# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Derivatives of eigenpairs that a NumPy eigensolver has already found.

An eigensolver returns numbers. ``refine`` attaches derivatives to one simple
eigenpair (lambda0, x0) of A x = lambda B x, normalized x0^T B x0 = 1, by one
Newton step on the eigenproblem bordered by that normalization,

    [x; lambda] = [x0; lambda0] - J^{-1} F,
    J = [[A - lambda0 B, -B x0], [-x0^T B, 0]],
    F = [(A - lambda0 B) x0, (1 - x0^T B x0) / 2],

solved with the live A and B through the adjoint sparse solve: the values stay
those of the eigensolver up to its residual, the derivatives are the exact
implicit ones. J is singular exactly when lambda0 is multiple, so
``neighbour_gap`` measures the distance to the nearest other eigenvalue of the
whole pencil, also one the eigensolver did not return.
"""
import numpy as np
import scipy.linalg as la
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from . import solve as core_solve
from .backend import lift, to_numpy
from .sparse import CooMatrix

DEGENERATE_GAP = 1e-8
_DENSE_LIMIT = 300


class DegenerateModeWarning(RuntimeWarning):
    """A returned eigenvalue is multiple (to DEGENERATE_GAP): its derivatives are NaN."""


def scipy_matrix(matrix):
    """The numbers of a CooMatrix as a SciPy CSC matrix."""
    return sp.coo_matrix((to_numpy(matrix.values), (matrix.rows, matrix.cols)),
                         shape=matrix.shape).tocsc()


def neighbour_gap(a, b, lam0):
    """Relative distance from lam0 to the nearest other eigenvalue of a x = lam b x.

    a and b are SciPy sparse matrices of numbers. Small pencils are solved
    densely; larger ones by shift-invert Arnoldi next to lam0, which finds the
    two eigenvalues nearest to it whether or not a solver returned them. If the
    neighbour cannot be found, the gap is reported as 0 (not certified).
    """
    n = a.shape[0]
    scale = abs(lam0) if lam0 != 0 else 1.0
    if n <= _DENSE_LIMIT:
        values = la.eigvals(a.toarray(), b.toarray())
        distance = np.sort(np.abs(values - lam0))
        return float(distance[1] / scale) if len(distance) > 1 else np.inf
    sigma = lam0 + 1e-10 * scale
    dtype = np.result_type(a.dtype, b.dtype, np.complex128 if np.iscomplexobj(lam0) else np.float64)
    try:
        lu = spla.splu((a - sigma * b).tocsc().astype(dtype))
        operator = spla.LinearOperator((n, n), matvec=lambda v: lu.solve(b @ v), dtype=dtype)
        nu = spla.eigs(operator, k=2, which="LM", v0=np.random.default_rng(0).standard_normal(n),
                       return_eigenvectors=False, tol=1e-12)
    except (RuntimeError, spla.ArpackError):
        return 0.0
    with np.errstate(divide="ignore"):
        values = sigma + 1.0 / nu
    distance = np.sort(np.abs(values - lam0))
    return float(distance[1] / scale)


def degenerate_modes(a, b, eigenvalues):
    """Indices of the returned eigenvalues that are multiple to DEGENERATE_GAP."""
    eigenvalues = np.asarray(eigenvalues)
    out = []
    for i, lam in enumerate(eigenvalues):
        scale = abs(lam) if lam != 0 else 1.0
        among_returned = any(j != i and abs(lam - other) <= DEGENERATE_GAP * max(scale, abs(other))
                             for j, other in enumerate(eigenvalues))
        if among_returned or neighbour_gap(a, b, lam) <= DEGENERATE_GAP:
            out.append(i)
    return out


def refine(xp, a, b, x0, lam0):
    """The eigenpair (x0, lam0) with derivatives: one bordered Newton step (module docstring).

    a and b are live CooMatrix; x0 holds numbers with x0^T B x0 = 1 (no
    conjugate). Returns live (x, lam).
    """
    n = a.shape[0]
    lam0 = complex(lam0) if np.iscomplexobj(lam0) else float(lam0)
    dtype = xp.complex128 if (np.iscomplexobj(x0) or np.iscomplexobj(lam0)
                              or "complex" in str(a.values.dtype) + str(b.values.dtype)) else xp.float64
    x0 = lift(xp, np.asarray(x0, dtype=complex if dtype == xp.complex128 else float))
    bx = b.matvec(x0)
    residual = xp.concat([a.matvec(x0) - lam0 * bx, xp.reshape(0.5 * (1 - x0 @ bx), (1,))])
    rows = np.concatenate([a.rows, b.rows, np.arange(n), np.full(n, n)])
    cols = np.concatenate([a.cols, b.cols, np.full(n, n), np.arange(n)])
    bordered = CooMatrix(rows, cols, xp.concat([xp.astype(a.values, dtype),
                                                xp.astype(-lam0 * b.values, dtype),
                                                xp.astype(-bx, dtype), xp.astype(-bx, dtype)]),
                         (n + 1, n + 1))
    step = core_solve.solve(bordered, xp.astype(residual, dtype))
    return x0 - step[:n], lam0 - step[n]
