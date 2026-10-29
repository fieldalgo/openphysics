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

from .core.checks import refuse_live
from .core.solve import scipy_solve_dirichlet


def solve_dirichlet(K: sp.csr_matrix, f: np.ndarray,
                    dirichlet: dict) -> np.ndarray:
    """Solve K V = f subject to Dirichlet data {node tuple: value}.

    dirichlet: {tuple/array of node ids: value} where value is a scalar or an
               array matching the node set, e.g.
               {tuple(mesh.boundary['inner']): 1.0,
                tuple(mesh.boundary['outer']): 0.0}
    NumPy only: JAX and PyTorch values raise TypeError.
    """
    refuse_live(f, "solve_dirichlet f")
    refuse_live(list(dirichlet.values()), "solve_dirichlet Dirichlet values")
    return scipy_solve_dirichlet(K, f, dirichlet)
