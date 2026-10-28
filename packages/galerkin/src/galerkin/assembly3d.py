# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""P1 (linear tetrahedron) assembly: stiffness and mass.

The 3D counterpart of assembly.py. On a linear tetrahedron the barycentric
gradients are constant, so both element matrices are closed forms:

    K^e_mn = V (grad lambda_m)^T Lam (grad lambda_n)
    M^e_mn = c V (1 + delta_mn) / 20          from  int_T lam_a lam_b dV = V(1+delta)/20

The 1/20 is the only thing that changes from the triangle's 1/12; everything else
is the same algebra one dimension up.
"""

from __future__ import annotations

import scipy.sparse as sp

from .core import forms, kernels
from .core.checks import refuse_live
from .core.tets import tet_gradients  # noqa: F401 (public here)
from .mesh3d import Mesh3D


def assemble_stiffness_3d(mesh: Mesh3D, eps=1.0) -> sp.csr_matrix:
    """K_mn = int (eps grad phi_n) . grad phi_m dV.

    eps: scalar, per-tetrahedron (T,), or per-tetrahedron 3x3 tensors (T, 3, 3).
    """
    refuse_live(eps, "assemble_stiffness_3d eps")
    t = mesh.tets
    return forms.matrix(t, t, kernels.tet_stiffness(mesh, eps), (mesh.num_nodes,) * 2).to_scipy()


def assemble_mass_3d(mesh: Mesh3D, coeff=1.0) -> sp.csr_matrix:
    """M_mn = int c phi_m phi_n dV, exact: M^e = c V/20 * (1 + delta_mn)."""
    refuse_live(coeff, "assemble_mass_3d coeff")
    t = mesh.tets
    return forms.matrix(t, t, kernels.tet_mass(mesh, coeff), (mesh.num_nodes,) * 2).to_scipy()
