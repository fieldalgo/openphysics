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
    tris = mesh.triangles
    p = mesh.nodes[tris]  # (T, 3, 2)
    T = len(tris)

    x = p[:, :, 0]  # (T, 3)
    y = p[:, :, 1]

    # b_i = y_j - y_k, c_i = x_k - x_j  (i, j, k cyclic)
    b = np.stack([y[:, 1] - y[:, 2], y[:, 2] - y[:, 0], y[:, 0] - y[:, 1]], axis=1)
    c = np.stack([x[:, 2] - x[:, 1], x[:, 0] - x[:, 2], x[:, 1] - x[:, 0]], axis=1)

    area = np.abs(0.5 * (b[:, 0] * c[:, 1] - b[:, 1] * c[:, 0]))

    eps = np.asarray(eps)
    if eps.ndim == 3:
        # Tensor coefficient: grad phi_i = (b_i, c_i)/(2A), hence
        #   K^e_ij = A (grad phi_i)^T Lam grad phi_j = g_i^T Lam g_j / (4A),
        #   g_i = (b_i, c_i)
        g = np.stack([b, c], axis=2)  # (T, 3, 2)
        Ke = np.einsum("tie,tef,tjf->tij", g, eps, g) / (4.0 * area)[:, None, None]
    else:
        eps = np.broadcast_to(eps, (T,))
        # Isotropic closed form: K^e = eps/(4A) * (b b^T + c c^T)
        Ke = (eps / (4.0 * area))[:, None, None] * (
            b[:, :, None] * b[:, None, :] + c[:, :, None] * c[:, None, :])

    # Scatter as COO and convert to CSR (duplicate entries are summed)
    rows = np.repeat(tris, 3, axis=1).ravel()
    cols = np.tile(tris, (1, 3)).ravel()
    K = sp.coo_matrix((Ke.ravel(), (rows, cols)),
                      shape=(mesh.num_nodes, mesh.num_nodes))
    return K.tocsr()


def assemble_mass(mesh: Mesh, coeff=1.0) -> sp.csr_matrix:
    """Mass matrix M_ij = int c phi_i phi_j dx.

    The -k^2 u term of the Helmholtz equation enters the weak form as -k^2 M.
    Exact element mass matrix for P1 triangles:
        M^e = c A/12 * [[2,1,1],[1,2,1],[1,1,2]]
    coeff: scalar or per-triangle array (T,), e.g. a refractive index n^2.
    """
    tris = mesh.triangles
    T = len(tris)
    area = mesh.areas()
    coeff = np.broadcast_to(np.asarray(coeff), (T,))

    base = np.array([[2.0, 1.0, 1.0],
                     [1.0, 2.0, 1.0],
                     [1.0, 1.0, 2.0]]) / 12.0
    Me = (coeff * area)[:, None, None] * base  # (T, 3, 3)

    rows = np.repeat(tris, 3, axis=1).ravel()
    cols = np.tile(tris, (1, 3)).ravel()
    M = sp.coo_matrix((Me.ravel(), (rows, cols)),
                      shape=(mesh.num_nodes, mesh.num_nodes))
    return M.tocsr()


def assemble_boundary_mass(mesh: Mesh, edges: np.ndarray, coeff=1.0) -> sp.csr_matrix:
    """Boundary mass matrix B_ij = int_Gamma c phi_i phi_j ds over given edges.

    A Robin/impedance/absorbing condition du/dn = gamma u enters the weak
    form as -gamma B. Exact element matrix for P1 on a segment:
        B^e = c L/6 * [[2,1],[1,2]]
    coeff: scalar (complex allowed) or per-edge array (E,).
    """
    edges = np.asarray(edges, dtype=int)
    E = len(edges)
    p = mesh.nodes[edges]                     # (E, 2, 2)
    length = np.linalg.norm(p[:, 1] - p[:, 0], axis=1)
    coeff = np.broadcast_to(np.asarray(coeff), (E,))

    base = np.array([[2.0, 1.0], [1.0, 2.0]]) / 6.0
    Be = (coeff * length)[:, None, None] * base  # (E, 2, 2)

    rows = np.repeat(edges, 2, axis=1).ravel()
    cols = np.tile(edges, (1, 2)).ravel()
    B = sp.coo_matrix((Be.ravel(), (rows, cols)),
                      shape=(mesh.num_nodes, mesh.num_nodes))
    return B.tocsr()


def assemble_load(mesh: Mesh, rho=0.0) -> np.ndarray:
    """Load vector f_i = int rho phi_i dx.

    rho: scalar, per-triangle array (T,), or a callable rho(x, y).
    For P1, a one-point centroid rule (value at the centroid times A/3 to
    each vertex) is sufficient.
    """
    tris = mesh.triangles
    area = mesh.areas()

    if callable(rho):
        centroid = mesh.nodes[tris].mean(axis=1)  # (T, 2)
        rho_e = rho(centroid[:, 0], centroid[:, 1])
    else:
        rho_e = np.broadcast_to(np.asarray(rho, dtype=float), (len(tris),))

    f = np.zeros(mesh.num_nodes)
    contrib = (rho_e * area / 3.0)
    np.add.at(f, tris[:, 0], contrib)
    np.add.at(f, tris[:, 1], contrib)
    np.add.at(f, tris[:, 2], contrib)
    return f
