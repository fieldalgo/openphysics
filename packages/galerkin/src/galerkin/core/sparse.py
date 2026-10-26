# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Sparse matrices whose values may be live while their pattern is static.

A ``CooMatrix`` keeps row and column indices as NumPy integer arrays (the
sparsity pattern, fixed by the mesh) and its entries in the caller's array
library, so an entry can carry a derivative. Repeated (row, column) pairs add,
as in SciPy's COO format. Solvers convert to SciPy only at the solve.
"""
from dataclasses import dataclass

import numpy as np

from .backend import Backend, backend_of, namespace, scatter_add


@dataclass(frozen=True)
class CooMatrix:
    rows: np.ndarray
    cols: np.ndarray
    values: object
    shape: tuple

    def __post_init__(self):
        rows, cols = np.asarray(self.rows), np.asarray(self.cols)
        if rows.ndim != 1 or cols.shape != rows.shape or rows.dtype.kind not in "iu" or cols.dtype.kind not in "iu":
            raise ValueError("rows and cols must be 1-D integer arrays of equal length")
        if len(self.shape) != 2 or self.values.shape != rows.shape:
            raise ValueError("values must be 1-D with one entry per (row, col) pair, shape must be 2-D")
        if len(rows) and (rows.min() < 0 or cols.min() < 0
                          or rows.max() >= self.shape[0] or cols.max() >= self.shape[1]):
            raise ValueError("row or column index outside the matrix shape")
        object.__setattr__(self, "rows", rows)
        object.__setattr__(self, "cols", cols)
        object.__setattr__(self, "shape", (int(self.shape[0]), int(self.shape[1])))

    @property
    def xp(self):
        return namespace(self.values)

    def to_dense(self):
        """The dense matrix in the values' library (duplicates added)."""
        n, m = self.shape
        flat = scatter_add(self.xp, n * m, self.rows * m + self.cols, self.values)
        return self.xp.reshape(flat, (n, m))

    def to_scipy(self):
        """A SciPy CSR matrix. NumPy values only: SciPy cannot carry a derivative."""
        if backend_of(self.xp) is not Backend.NUMPY:
            raise TypeError("to_scipy needs NumPy values; converting JAX or PyTorch values "
                            "would cut their derivatives")
        import scipy.sparse as sp
        return sp.coo_matrix((self.values, (self.rows, self.cols)), shape=self.shape).tocsr()
