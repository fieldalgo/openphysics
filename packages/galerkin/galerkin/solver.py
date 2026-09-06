# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Dirichlet boundary conditions and linear solve.

When boundary potentials are prescribed (V = g on Gamma_D), only interior
nodes are unknowns. Splitting K into free (F) / Dirichlet (D) blocks:

    [K_FF  K_FD] [V_F]   [f_F]
    [K_DF  K_DD] [V_D] = [f_D]   ->   K_FF V_F = f_F - K_FD g

Following the "never write your own linear algebra" rule, the sparse direct
solver of scipy (spsolve, SuperLU underneath) is used. Iterative solvers with
preconditioning will replace it when problems outgrow direct factorization.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla


def solve_dirichlet(K: sp.csr_matrix, f: np.ndarray,
                    dirichlet: dict) -> np.ndarray:
    """Solve K V = f subject to Dirichlet data {node tuple: value}.

    dirichlet: {tuple/array of node ids: value} where value is a scalar or an
               array matching the node set, e.g.
               {tuple(mesh.boundary['inner']): 1.0,
                tuple(mesh.boundary['outer']): 0.0}
    """
    n = K.shape[0]
    # Complex support: solve in complex arithmetic if K, f, or any boundary
    # value is complex.
    dtype = np.result_type(K.dtype, np.asarray(f).dtype,
                           *[np.asarray(v).dtype for v in dirichlet.values()])
    V = np.zeros(n, dtype=dtype)
    is_fixed = np.zeros(n, dtype=bool)

    for nodes, value in dirichlet.items():
        idx = np.asarray(nodes, dtype=int)
        V[idx] = value  # scalar, or an array of the same length as idx
        is_fixed[idx] = True

    free = np.where(~is_fixed)[0]
    fixed = np.where(is_fixed)[0]

    K_FF = K[free][:, free]
    K_FD = K[free][:, fixed]
    rhs = f[free] - K_FD @ V[fixed]

    V[free] = spla.spsolve(K_FF.tocsc(), rhs)
    return V
