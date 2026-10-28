# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""M3a: guided modes of a dielectric waveguide cross-section (full vector).

Physics
-------
A guide that does not change along z carries fields of the form

    E(x, y, z, t) = [E_t(x, y) + zhat E_z(x, y)] exp(+i omega t-i beta z)

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
generalized eigenvalue problem in beta^2 with transpose-symmetric matrices
(complex symmetric, not Hermitian, when the permittivity is complex):

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

Derivatives
-----------
eps_r, mu_r and k0 may be JAX or PyTorch values: solve_modes then returns n_eff,
et and ez in that library with reverse-mode derivatives of the eigenvalues and of
the fields (docs/packages/galerkin/differentiation.md). The NumPy eigensolve runs
on their numbers first; each returned pair (lambda0, x0) then takes one Newton
step on the eigenproblem bordered by the normalization x^T B x = 1,

    [x; lambda] = [x0; lambda0] - J^{-1} F,   J = [[A - lambda0 B, -B x0], [-x0^T B, 0]],

with the live A and B (galerkin.core.eigen): the values stay those of the NumPy
solve up to its residual and the derivatives are the exact implicit ones. The
returned gauge (unit 2-norm, largest entry real and positive) is then applied
again, so field derivatives follow it; quantities that do not depend on the
gauge (overlaps, power ratios) have gauge-free derivatives. A degenerate
eigenvalue has no derivative: a mode whose eigenvalue lies within a relative
DEGENERATE_GAP of another eigenvalue of the pencil, returned or not, gets NaN
derivatives and a DegenerateModeWarning.
"""

from __future__ import annotations

import warnings

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .mesh import Mesh
from .edge import EdgeSpace
from .core import eigen, forms, kernels
from .core import live as live_inputs
from .core import solve as core_solve
from .core.eigen import DEGENERATE_GAP, DegenerateModeWarning  # noqa: F401 (public here)
from .core.backend import Backend, backend_of, lift, live_namespace, scatter_add, to_numpy
from .core.checks import contains_live
from .core.sparse import CooMatrix


def assemble_mode_system(mesh: Mesh, eps_r, k0: float, mu_r=1.0,
                         space: EdgeSpace | None = None, *, coordinate_factors=None):
    """Block matrices (A, B) of the mode eigenproblem A x = -beta^2 B x.

    eps_r, mu_r: scalar or per-triangle (T,) relative material parameters, real
        or complex.
    coordinate_factors: optional (T, 3) diagonal coordinate Jacobian (sx,sy,h).
    Returns (A, B, space); x = (e_t over edges, e_z over nodes), no BC applied.
    """
    space = space or EdgeSpace(mesh)
    blocks = {name: m.to_scipy() for name, m in _mode_blocks(np, space, eps_r, mu_r, coordinate_factors).items()}
    S, Mt_eps, Mt_mu, G, K, M = (blocks[n] for n in ("S", "Mt_eps", "Mt_mu", "G", "K", "M"))
    n_e, n_n = space.num_edges, mesh.num_nodes
    zero_en = sp.csr_matrix((n_e, n_n))
    zero_nn = sp.csr_matrix((n_n, n_n))

    A = sp.bmat([[S - k0 ** 2 * Mt_eps, zero_en],
                 [zero_en.T,            zero_nn]]).tocsr()
    B = sp.bmat([[Mt_mu, G],
                 [G.T,   K - k0 ** 2 * M]]).tocsr()
    return A, B, space


def _mode_blocks(xp, space, eps_r, mu_r, coordinate_factors):
    """The six blocks S, Mt_eps, Mt_mu, G, K, M of the mode system as CooMatrix in ``xp``.

    J = diag(sx, sy, h) maps eps' = eps det(J) J^-1 J^-T (likewise mu); the
    transverse curl rotates axes, so beta and grad use (1/mu_y, 1/mu_x).
    """
    mesh = space.mesh
    t = mesh.num_triangles
    eps = xp.broadcast_to(lift(xp, eps_r), (t,))
    inv_mu = xp.broadcast_to(1.0 / (np.asarray(mu_r) if backend_of(xp) is Backend.NUMPY
                                     else lift(xp, mu_r)), (t,))
    if coordinate_factors is None:
        curl, mass_eps, mass_mu, grad = inv_mu, eps, inv_mu, inv_mu
        stiff, mass = inv_mu, eps
    else:
        f = np.asarray(coordinate_factors)
        if f.shape != (t, 3) or not np.isfinite(f).all() or np.any(f == 0):
            raise ValueError("coordinate_factors must be finite nonzero (triangles, 3)")
        sx, sy, h = (lift(xp, c) for c in f.T)

        def diagonal(a, b):
            zero = xp.zeros_like(a)
            return xp.stack([xp.stack([a, zero], axis=-1), xp.stack([zero, b], axis=-1)], axis=-2)
        d = diagonal(inv_mu * sy/(sx*h), inv_mu * sx/(sy*h))
        curl, mass_eps = inv_mu*h/(sx*sy), diagonal(eps*sy*h/sx, eps*sx*h/sy)
        mass_mu, grad, stiff, mass = d, d, d, eps*sx*sy/h
    te, tn = space.tri_edges, mesh.triangles
    n_e, n_n = space.num_edges, mesh.num_nodes
    return {"S": forms.matrix(te, te, kernels.nedelec_curlcurl(space, curl), (n_e, n_e)),
            "Mt_eps": forms.matrix(te, te, kernels.nedelec_mass(space, mass_eps), (n_e, n_e)),
            "Mt_mu": forms.matrix(te, te, kernels.nedelec_mass(space, mass_mu), (n_e, n_e)),
            "G": forms.matrix(te, tn, kernels.nedelec_grad(space, grad), (n_e, n_n)),
            "K": forms.matrix(tn, tn, kernels.p1_stiffness(mesh, stiff), (n_n, n_n)),
            "M": forms.matrix(tn, tn, kernels.p1_mass(mesh, mass), (n_n, n_n))}


def _free_dofs(mesh, space, pec_nodes, pec_edges):
    """Unconstrained DOFs of (e_t edges, e_z nodes) for the PEC nodes and edges."""
    n_e = space.num_edges
    if pec_nodes is None:
        pec_nodes = np.unique(np.concatenate(
            [mesh.boundary[k] for k in mesh.boundary]))
    pec_nodes = np.asarray(pec_nodes, dtype=int)
    if pec_edges is None:
        pec_edges = space.boundary_edge_ids(pec_nodes)
    pec_edges = np.asarray(pec_edges, dtype=int)
    fixed = np.unique(np.concatenate(
        [pec_edges, n_e + pec_nodes]))
    return np.setdiff1d(np.arange(n_e + mesh.num_nodes), fixed)


def solve_modes(mesh: Mesh, eps_r, k0: float, n_target: float | complex,
                num_modes: int = 6, mu_r=1.0, pec_nodes=None, *, pec_edges=None, coordinate_factors=None):
    """Guided modes with effective index near n_target.

    eps_r, mu_r and k0 may be JAX or PyTorch values; n_eff, et and ez are then
    in that library with derivatives (see the module docstring for the method,
    the field gauge and degenerate modes). coordinate_factors must be NumPy;
    n_target only selects the modes and carries no derivative.

    Complex eps_r and mu_r are expressed in the exp(+i omega t) convention:
    passive absorption has Im eps_r < 0 (Im mu_r < 0) and the forward root has
    Im n_eff < 0.
    n_target may be complex. Lossy candidates keep their complex eigenvalues
    and are ordered by descending Re n_eff; a finite PEC window and a shift
    do not establish confinement or completeness. The real-material path is
    retained. Returned fields have arbitrary amplitude, not unit power.

    n_target: shift-invert target for beta/k0 — the core index is the natural
              choice, since guided modes lie just below it.
    pec_nodes: nodes carrying n x E = 0; defaults to every boundary node. An open
              guide is truncated by putting this wall out where the evanescent
              cladding field has already died.
    pec_edges: explicit global EdgeSpace edge ids for tangential E constraints.
              If omitted, boundary edges with both endpoints in pec_nodes are
              fixed, preserving the original API. Supply explicit ids for mixed
              walls: a one-edge PMC wall can have two PEC corner nodes without
              being a PEC edge. pec_nodes still constrains the nodal E_z values.

    coordinate_factors: optional per-element diagonal coordinate Jacobian.
    Returned fields then are covariant computational components; for a bend
    the physical longitudinal field outside PML is 1j*ez/h.

    Returns (n_eff, space, et, ez) sorted by descending effective index:
      n_eff (m,)      beta / k0
      et    (m, n_e)  edge dofs of E_t  -> use eval_edge_field(space, et[i])
      ez    (m, n_n)  nodal values with E_z = 1j * ez[i]

    Both coefficient arrays are complex, preserving the eigensolver's full span.
    The factor of i follows the variable transformation above. For a real basis,
    the longitudinal component sits in quadrature with the transverse one; a
    complex combination of degenerate modes need not have that componentwise
    phase relation. The relative scaling, and hence |E_z|/|E_t|, is preserved.
    """
    if contains_live(coordinate_factors):
        raise TypeError("coordinate_factors: derivatives with respect to modal coordinates are "
                        "not provided; pass NumPy factors")
    numeric = _solve_modes_numpy(mesh, live_inputs.numbers(eps_r), live_inputs.numbers(k0),
                                 live_inputs.numbers(n_target), num_modes, live_inputs.numbers(mu_r),
                                 pec_nodes, pec_edges=pec_edges, coordinate_factors=coordinate_factors)
    if not any(contains_live(v) for v in (eps_r, k0, mu_r)):
        return numeric
    return _live_modes(mesh, eps_r, k0, mu_r, pec_nodes, pec_edges, coordinate_factors, *numeric)


def _live_blocks(xp, space, eps_r, mu_r, k0, coordinate_factors):
    """(A, B) of ``assemble_mode_system`` in ``xp`` as coalesced CooMatrix, from ``_mode_blocks``."""
    blocks = _mode_blocks(xp, space, eps_r, mu_r, coordinate_factors)
    n_e, n_n = space.num_edges, space.mesh.num_nodes
    g = blocks["G"]
    blocks_a = [(blocks["S"], 0, 0, 1.0), (blocks["Mt_eps"], 0, 0, -k0**2)]
    blocks_b = [(blocks["Mt_mu"], 0, 0, 1.0), (g, 0, n_e, 1.0),
                (CooMatrix(g.cols, g.rows, g.values, (n_n, n_e)), n_e, 0, 1.0),
                (blocks["K"], n_e, n_e, 1.0), (blocks["M"], n_e, n_e, -k0**2)]

    def joined(parts):
        return CooMatrix(np.concatenate([b.rows + r for b, r, _, _ in parts]),
                         np.concatenate([b.cols + c for b, _, c, _ in parts]),
                         xp.concat([lift(xp, b.values) * scale for b, _, _, scale in parts]),
                         (n_e + n_n, n_e + n_n)).coalesce()
    return joined(blocks_a), joined(blocks_b)


def _pivot(v):
    """The entry the NumPy solve made real and positive.

    It is the largest in magnitude; symmetric modes often have several equally
    large entries, and the one the solve chose is the one left with zero phase.
    """
    size = np.abs(v)
    candidates = np.flatnonzero(size >= size.max() * (1 - 1e-12))
    return int(candidates[np.argmin(np.abs(np.angle(v[candidates])))])


def _restricted(matrix, position, size):
    keep = np.flatnonzero((position[matrix.rows] >= 0) & (position[matrix.cols] >= 0))
    return CooMatrix(position[matrix.rows[keep]], position[matrix.cols[keep]],
                     matrix.values[keep], (size, size))


def _live_modes(mesh, eps_r, k0, mu_r, pec_nodes, pec_edges, coordinate_factors,
                n_eff0, space, et0, ez0):
    """The NumPy modes with derivatives: a bordered Newton step per mode (module docstring)."""
    leaves = live_inputs.leaves(eps_r, k0, mu_r)
    xp = live_namespace(*leaves)
    complex_dtype = xp.complex128
    n_e, n_n = space.num_edges, mesh.num_nodes
    free = _free_dofs(mesh, space, pec_nodes, pec_edges)
    position = np.full(n_e + n_n, -1)
    position[free] = np.arange(len(free))
    n = len(free)
    k0_live = lift(xp, k0, xp.float64)
    A, B = (_restricted(m, position, n) for m in _live_blocks(xp, space, eps_r, mu_r, k0_live,
                                                              coordinate_factors))
    A_numbers, B_numbers = eigen.scipy_matrix(A), eigen.scipy_matrix(B)
    real_problem = np.isrealobj(n_eff0)
    k0_number = float(to_numpy(k0_live))
    lam0 = -(k0_number * np.asarray(n_eff0)) ** 2
    degenerate = eigen.degenerate_modes(A_numbers, B_numbers, lam0)
    if degenerate:
        warnings.warn(f"modes {degenerate} belong to degenerate eigenvalues (relative gap <= "
                      f"{DEGENERATE_GAP:g}); their derivatives are NaN", DegenerateModeWarning,
                      stacklevel=3)
    n_eff, et, ez = [], [], []
    for i in range(len(lam0)):
        beta0 = k0_number * n_eff0[i]
        v = np.concatenate([et0[i] * beta0, ez0[i]])[free]
        if i in degenerate:
            n_eff.append(core_solve.nan_derivative(xp, np.asarray(n_eff0[i]), leaves))
            et.append(core_solve.nan_derivative(xp, et0[i], leaves))
            ez.append(core_solve.nan_derivative(xp, ez0[i], leaves))
            continue
        x, lam = eigen.refine(xp, A, B, v / np.sqrt(v @ (B_numbers @ v)), lam0[i])  # x0^T B x0 = 1
        beta = xp.sqrt(-lam)
        pivot = _pivot(v)
        x = x * xp.conj(x[pivot]) / (xp.abs(x[pivot]) * xp.sqrt(xp.sum(xp.abs(x) ** 2)))
        full = scatter_add(xp, n_e + n_n, free, x)
        n_eff.append(xp.real(beta) / k0_live if real_problem else beta / k0_live)
        et.append(full[:n_e] / beta)
        ez.append(full[n_e:])
    if not n_eff:
        empty = (xp.zeros(0, dtype=xp.float64 if real_problem else complex_dtype),
                 xp.zeros((0, n_e), dtype=complex_dtype), xp.zeros((0, n_n), dtype=complex_dtype))
        return empty[0], space, empty[1], empty[2]
    return xp.stack(n_eff), space, xp.stack(et), xp.stack(ez)


def _solve_modes_numpy(mesh: Mesh, eps_r, k0: float, n_target: float | complex,
                       num_modes: int = 6, mu_r=1.0, pec_nodes=None, *, pec_edges=None,
                       coordinate_factors=None):
    """The NumPy eigensolve of ``solve_modes`` (NumPy inputs only)."""
    eps_r, mu_r = np.asarray(eps_r), np.asarray(mu_r)
    if not np.isfinite(eps_r).all():
        raise ValueError("eps_r must be finite")
    if not np.isfinite(mu_r).all():
        raise ValueError("mu_r must be finite")
    complex_problem = (bool(np.any(eps_r.imag != 0) or np.any(mu_r.imag != 0))
                       or coordinate_factors is not None)
    if not complex_problem:
        eps_r, mu_r = eps_r.real, mu_r.real
    A, B, space = assemble_mode_system(mesh, eps_r, k0, mu_r, coordinate_factors=coordinate_factors)
    n_e, n_n = space.num_edges, mesh.num_nodes

    free = _free_dofs(mesh, space, pec_nodes, pec_edges)

    A, B = A[free][:, free].tocsc(), B[free][:, free].tocsc()
    n = A.shape[0]

    # Shift-invert as a standard problem: nu = 1 / (lam - sigma), lam = -beta^2
    sigma = -(k0 * n_target) ** 2
    lu = spla.splu((A - sigma * B).tocsc())
    op = spla.LinearOperator((n, n), matvec=lambda x: lu.solve(B @ x), dtype=lu.L.dtype)
    nu, vecs = spla.eigs(op, k=num_modes, which="LM", v0=np.ones(n),
                         ncv=min(n, max(4 * num_modes, 40)), maxiter=20000)

    beta2 = -(sigma + 1.0 / nu)
    if complex_problem:
        beta = np.sqrt(beta2.astype(complex))
        if coordinate_factors is not None:
            if not np.isfinite(beta).all() or np.any(beta == 0):
                raise RuntimeError("modal coordinate search returned a nonfinite or zero propagation root")
            keep = np.arange(len(beta))  # let the caller record every candidate and exclusion
        else:
            keep = np.flatnonzero(np.isfinite(beta) & (beta.real > 0))
        keep = keep[np.lexsort((beta[keep].imag, -beta[keep].real))]
    else:
        beta2 = beta2.real
        keep = np.where(beta2 > 0.0)[0]
        keep = keep[np.argsort(beta2[keep])[::-1]]
        beta = np.sqrt(np.maximum(beta2, 0.0))

    n_eff = beta[keep] / k0
    et = np.zeros((len(keep), n_e), dtype=complex)
    ez = np.zeros((len(keep), n_n), dtype=complex)
    for i, j in enumerate(keep):
        v = vecs[:, j]
        pivot = v[np.argmax(np.abs(v))]
        v = v * (pivot.conjugate() / abs(pivot))  # fix ARPACK's phase
        # A real pencil can return complex bases of a degenerate eigenspace.
        # Taking real parts column by column can collapse independent directions.
        # Preserve each eigenvector; do not mix nearby, distinct eigenpairs.
        x = np.zeros(n_e + n_n, dtype=complex)
        x[free] = v
        et[i] = x[:n_e] / beta[j]   # e_t = beta E_t  ->  E_t
        ez[i] = x[n_e:]
    return n_eff, space, et, ez
