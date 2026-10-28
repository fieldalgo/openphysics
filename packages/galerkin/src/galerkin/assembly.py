# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""P1 (linear triangle) element assembly: stiffness, mass, boundary, load.

Model problem (electrostatics):
    div(eps grad V) = -rho   in Omega,   V = g  on Gamma_D

Weak form (test function w, V in H1):
    int_Omega eps grad V . grad w dx = int_Omega rho w dx

With P1 elements, V(x,y) = sum_j V_j phi_j(x,y) where phi_j is the linear
"hat" function that is 1 at node j and 0 at the others. On one triangle the
gradient of phi_i is constant, so the element stiffness matrix has the
closed form

    K^e_ij = eps_e (b_i b_j + c_i c_j) / (4A)

where A is the triangle area and (cyclically)
    b_1 = y_2 - y_3,   c_1 = x_3 - x_2.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from .core import forms, kernels
from .core.checks import refuse_live
from .mesh import Mesh


def assemble_stiffness(mesh: Mesh, eps=1.0) -> sp.csr_matrix:
    """Global stiffness K_ij = int (eps grad phi_j) . grad phi_i dx.

    eps:
      - scalar or per-triangle array (T,)      -> isotropic material
      - per-triangle 2x2 tensors (T, 2, 2)     -> anisotropic material / PML
        (complex allowed)

    A PML is a fictitious anisotropic absorbing material produced by complex
    coordinate stretching, so one tensor-coefficient code path serves both
    anisotropic media and PMLs.
    """
    refuse_live(eps, "assemble_stiffness eps")
    t = mesh.triangles
    return forms.matrix(t, t, kernels.p1_stiffness(mesh, eps), (mesh.num_nodes,) * 2).to_scipy()


def assemble_mass(mesh: Mesh, coeff=1.0) -> sp.csr_matrix:
    """Mass matrix M_ij = int c phi_i phi_j dx.

    The -k^2 u term of the Helmholtz equation enters the weak form as -k^2 M.
    Exact element mass matrix for P1 triangles:
        M^e = c A/12 * [[2,1,1],[1,2,1],[1,1,2]]
    coeff: scalar or per-triangle array (T,), e.g. a refractive index n^2.
    """
    refuse_live(coeff, "assemble_mass coeff")
    t = mesh.triangles
    return forms.matrix(t, t, kernels.p1_mass(mesh, coeff), (mesh.num_nodes,) * 2).to_scipy()


def assemble_boundary_mass(mesh: Mesh, edges: np.ndarray, coeff=1.0) -> sp.csr_matrix:
    """Boundary mass matrix B_ij = int_Gamma c phi_i phi_j ds over given edges.

    A Robin/impedance/absorbing condition du/dn = gamma u enters the weak
    form as -gamma B. Exact element matrix for P1 on a segment:
        B^e = c L/6 * [[2,1],[1,2]]
    coeff: scalar (complex allowed) or per-edge array (E,).
    """
    refuse_live(coeff, "assemble_boundary_mass coeff")
    edges = np.asarray(edges, dtype=int)
    return forms.matrix(edges, edges, kernels.p1_boundary_mass(mesh, edges, coeff),
                        (mesh.num_nodes,) * 2).to_scipy()


def assemble_load(mesh: Mesh, rho=0.0) -> np.ndarray:
    """Load vector f_i = int rho phi_i dx.

    rho: scalar, per-triangle array (T,), or a callable rho(x, y).
    For P1, a one-point centroid rule (value at the centroid times A/3 to
    each vertex) is sufficient.
    """
    if not callable(rho):
        refuse_live(rho, "assemble_load rho")
    f = forms.vector(mesh.triangles, kernels.p1_load(mesh, rho), mesh.num_nodes, order="columns")
    refuse_live(f, "assemble_load rho callback")
    return f
