# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""M3a: guided modes of a dielectric waveguide cross-section (full vector).

Physics
-------
A guide that does not change along z carries fields of the form

    E(x, y, z) = [E_t(x, y) + zhat E_z(x, y)] exp(-i beta z)

and the question is which propagation constants beta the cross-section supports.
Unlike the PEC waveguide of M3-prep there is no metal wall here: the mode is held
in by total internal reflection, so E_z cannot be dropped and the problem is
genuinely vectorial. The eigenvalue sought is beta, not a cutoff k_c.

Formulation
-----------
Put the ansatz into curl((1/mu_r) curl E) = k0^2 eps_r E, where the operator
splits as grad = grad_t - i beta zhat, and rescale the unknowns

    e_t = beta E_t     transverse   -> H(curl): Nedelec edge elements
    e_z = -i E_z       longitudinal -> H1:      nodal P1 elements

The scaling clears beta out of the interior of the curl term, leaving a *linear*
generalized eigenvalue problem in beta^2 with real symmetric matrices:

    [ S(1/mu) - k0^2 Mt(eps)   0 ] [e_t]            [ Mt(1/mu)  G(1/mu)              ] [e_t]
    [ 0                        0 ] [e_z]  =  -beta^2[ G(1/mu)^T K(1/mu) - k0^2 M(eps)] [e_z]

    S   curl-curl edge matrix   int (1/mu_r) (curl W_e)(curl W_f)
    Mt  edge mass               int c W_e . W_f          (c = eps_r or 1/mu_r)
    G   edge-nodal coupling     int (1/mu_r) W_e . grad phi_n
    K   nodal stiffness         int (1/mu_r) grad phi_m . grad phi_n
    M   nodal mass              int eps_r phi_m phi_n

Using the right space for each component is the entire point. Across a dielectric
interface E_t is only tangentially continuous (edge elements enforce exactly that)
while E_z is fully continuous (nodal elements). Mixing the pairing up is what
manufactures spurious modes.

The left matrix is singular: varying the functional with respect to e_z yields a
constraint, not an eigenvalue equation, so beta^2 = 0 is an eigenvalue of high
multiplicity. Guided modes sit far away from it, at n_clad < beta/k0 < n_core, and
shift-inverting near the core index reaches them directly.

Solving it
----------
The right-hand matrix is symmetric but *indefinite*, which ARPACK's generalized
drivers assume away (scipy requires a positive semi-definite mass matrix). So the
shift-invert operator (A - sigma B)^-1 B is formed explicitly and handed over as an
ordinary standard eigenproblem, which carries no such assumption.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .mesh import Mesh
from .assembly import assemble_stiffness, assemble_mass
from .edge import (EdgeSpace, assemble_curlcurl, assemble_edge_mass,
                   assemble_edge_grad)


def assemble_mode_system(mesh: Mesh, eps_r, k0: float, mu_r=1.0,
                         space: EdgeSpace | None = None):
    """Block matrices (A, B) of the mode eigenproblem A x = -beta^2 B x.

    eps_r, mu_r: scalar or per-triangle (T,) relative material parameters.
    Returns (A, B, space); x = (e_t over edges, e_z over nodes), no BC applied.
    """
    space = space or EdgeSpace(mesh)
    inv_mu = 1.0 / np.asarray(mu_r, dtype=float)

    S = assemble_curlcurl(space, inv_mu)
    Mt_eps = assemble_edge_mass(space, eps_r)
    Mt_mu = assemble_edge_mass(space, inv_mu)
    G = assemble_edge_grad(space, inv_mu)
    K = assemble_stiffness(mesh, inv_mu)
    M = assemble_mass(mesh, eps_r)

    n_e, n_n = space.num_edges, mesh.num_nodes
    zero_en = sp.csr_matrix((n_e, n_n))
    zero_nn = sp.csr_matrix((n_n, n_n))

    A = sp.bmat([[S - k0 ** 2 * Mt_eps, zero_en],
                 [zero_en.T,            zero_nn]]).tocsr()
    B = sp.bmat([[Mt_mu, G],
                 [G.T,   K - k0 ** 2 * M]]).tocsr()
    return A, B, space


def solve_modes(mesh: Mesh, eps_r, k0: float, n_target: float,
                num_modes: int = 6, mu_r=1.0, pec_nodes=None):
    """Guided modes with effective index near n_target.

    n_target: shift-invert target for beta/k0 — the core index is the natural
              choice, since guided modes lie just below it.
    pec_nodes: nodes carrying n x E = 0; defaults to every boundary node. An open
              guide is truncated by putting this wall out where the evanescent
              cladding field has already died.

    Returns (n_eff, space, et, ez) sorted by descending effective index:
      n_eff (m,)      beta / k0
      et    (m, n_e)  edge dofs of E_t  -> use eval_edge_field(space, et[i])
      ez    (m, n_n)  nodal values with E_z = 1j * ez[i]

    The factor of i is physical, not bookkeeping: in a guided mode the longitudinal
    component sits in quadrature with the transverse one. The relative magnitude of
    et and ez is scaled correctly, so |E_z|/|E_t| is meaningful.
    """
    A, B, space = assemble_mode_system(mesh, eps_r, k0, mu_r)
    n_e, n_n = space.num_edges, mesh.num_nodes

    if pec_nodes is None:
        pec_nodes = np.unique(np.concatenate(
            [mesh.boundary[k] for k in mesh.boundary]))
    pec_nodes = np.asarray(pec_nodes, dtype=int)
    fixed = np.unique(np.concatenate(
        [space.boundary_edge_ids(pec_nodes), n_e + pec_nodes]))
    free = np.setdiff1d(np.arange(n_e + n_n), fixed)

    A, B = A[free][:, free].tocsc(), B[free][:, free].tocsc()
    n = A.shape[0]

    # Shift-invert as a standard problem: nu = 1 / (lam - sigma), lam = -beta^2
    sigma = -(k0 * n_target) ** 2
    lu = spla.splu((A - sigma * B).tocsc())
    op = spla.LinearOperator((n, n), matvec=lambda x: lu.solve(B @ x), dtype=float)
    nu, vecs = spla.eigs(op, k=num_modes, which="LM", v0=np.ones(n),
                         ncv=min(n, max(4 * num_modes, 40)), maxiter=20000)

    beta2 = -(sigma + 1.0 / nu).real
    keep = np.where(beta2 > 0.0)[0]
    keep = keep[np.argsort(beta2[keep])[::-1]]

    n_eff = np.sqrt(beta2[keep]) / k0
    et = np.zeros((len(keep), n_e))
    ez = np.zeros((len(keep), n_n))
    for i, j in enumerate(keep):
        v = vecs[:, j]
        v = v * np.exp(-1j * np.angle(v[np.argmax(np.abs(v))]))  # fix ARPACK's phase
        x = np.zeros(n_e + n_n)
        x[free] = v.real
        et[i] = x[:n_e] / np.sqrt(beta2[j])   # e_t = beta E_t  ->  E_t
        ez[i] = x[n_e:]
    return n_eff, space, et, ez
