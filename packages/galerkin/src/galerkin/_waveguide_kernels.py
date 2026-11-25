# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""M3a: guided modes of a dielectric waveguide cross-section (full vector), the kernels.

Package-private: ``solve_modes`` and ``assemble_mode_system`` compute in whatever
consistent units their caller hands them (lengths in the mesh's unit, k0 in its
inverse) and in the phasor exp(+i omega t) below. ``galerkin.kernels`` re-exports
them unchanged for galerkin's own modules and simcase (route K of the galerkin
step: simcase's em.modes2d keeps its micrometre doubles). They were names of the
public ``galerkin.waveguide`` until the galerkin step (L3 commit 11), which hosts the
public SI functions; this module holds no public name.

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
multiplicity (every [0, e_z] satisfies A x = 0). Guided modes sit far away from it,
at n_clad < beta/k0 < n_core, and shift-inverting near the core index reaches them
directly. The family is exactly degenerate (nu = 1/(lambda - sigma) = -1/sigma for
all of it), so a search that asked ARPACK for its vectors converged them only
through rounding: how fast, or whether at all, depended on the last bits of the
pencil. The search therefore never asks for them. For lambda != 0 the nodal rows of
A x = lambda B x give G^T x_t + N x_z = 0 (N = K - k0^2 M on the free nodes), so
    P [x_t; x_z] = [x_t; -N^-1 G^T x_t]
keeps every other eigenvector, annihilates [0, e_z] and commutes with the
shift-invert operator; the search runs on P (A - sigma B)^-1 B from P(ones). It then
also finds roots beyond the family (|nu| |sigma| < 1); only roots nearer the shift
than the family (|nu| |sigma| > 1) are kept, the roots an undeflated search finds
before it reaches the family. Roots with |beta^2| <= STATIC_ROOT_TOL |sigma|, that is
|n_eff| <= 1e-5 |n_target|, are not returned either.

N is nearly singular when k0^2 is close to an eigenvalue of K e_z = mu M e_z on the
free nodes (a TM cutoff of the PEC box). The relative distance delta = 1/|mu_max|,
mu_max the largest eigenvalue of N^-1 (k0^2 M), is estimated first; below
STATIC_DEFLATION_MIN_CUTOFF_DISTANCE (1e-5) the search is not deflated, as before,
with a StaticFamilyNearCutoffWarning. There a search for more modes than lie closer
to the target than the family reaches it: its computed roots usually have |beta^2|
at rounding level and are not returned, but the family is ill-conditioned, its
roots can exceed the tolerance, and they are returned
(docs/packages/galerkin/waveguide_formulation.md, section 3).

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
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.linalg import eig as la_eig

from .mesh import Mesh
from .edge import EdgeSpace
from .core import eigen, forms, kernels
from .core import live as live_inputs
from .core import solve as core_solve
from .core.eigen import (DEGENERATE_GAP, DegenerateModeWarning,  # noqa: F401 (galerkin.waveguide re-exports them)
                         StaticFamilyNearCutoffWarning, arpack_rng)
from .core.backend import Backend, backend_of, lift, live_namespace, scatter_add, to_numpy
from .core.checks import contains_live, refuse_live
from .core.sparse import CooMatrix
from .core.spaces import TRI_LOCAL_EDGES

__all__ = ["STATIC_ROOT_TOL", "STATIC_DEFLATION_MIN_CUTOFF_DISTANCE", "assemble_mode_system", "solve_modes",
           "DegenerateModeWarning", "StaticFamilyNearCutoffWarning"]

#: Relative size |beta^2| / |sigma| at or below which a root belongs to the static
#: beta^2 = 0 family (module docstring). Measured static roots away from a TM
#: cutoff of the PEC box: <= 1.2e-14.
STATIC_ROOT_TOL = 1e-10

#: Relative distance |mu - k0^2| / k0^2 of k0^2 from the nearest eigenvalue mu of K e = mu M e on the
#: free nodes (a TM cutoff of the PEC box) below which the vector search is not deflated: the
#: nodal block K - k0^2 M of B, which the projector solves with, is then nearly singular
#: (module docstring).
STATIC_DEFLATION_MIN_CUTOFF_DISTANCE = 1e-5


def assemble_mode_system(mesh: Mesh, eps_r, k0: float, mu_r=1.0,
                         space: EdgeSpace | None = None, *, coordinate_factors=None):
    """Block matrices (A, B) of the mode eigenproblem A x = -beta^2 B x.

    eps_r, mu_r: scalar or per-triangle (T,) relative material parameters, real
        or complex.
    coordinate_factors: optional (T, 3) diagonal coordinate Jacobian (sx,sy,h).
    Returns (A, B, space); x = (e_t over edges, e_z over nodes), no BC applied.
    NumPy only: JAX and PyTorch values raise TypeError (solve_modes differentiates).
    """
    for name, value in (("eps_r", eps_r), ("k0", k0), ("mu_r", mu_r), ("coordinate_factors", coordinate_factors)):
        refuse_live(value, f"assemble_mode_system {name}")
    A, B, space, _ = _assembled(mesh, eps_r, k0, mu_r, space, coordinate_factors)
    return A, B, space


def _assembled(mesh, eps_r, k0, mu_r, space, coordinate_factors):
    """(A, B, space, M) of ``assemble_mode_system``, with the nodal mass block M."""
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
    return A, B, space, M


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
                num_modes: int = 6, mu_r=1.0, pec_nodes=None, *, pec_edges=None, coordinate_factors=None,
                motion=None, coordinate_bend=None):
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
    the physical longitudinal field outside PML is 1j*ez/h. With a motion they
    are the factors of the mesh at the step t, held fixed (no derivative), and
    the design velocity must be 0 on every node of an element whose factors are
    not 1.

    Returns (n_eff, space, et, ez) sorted by descending effective index:
      n_eff (m,)      beta / k0
      et    (m, n_e)  edge dofs of E_t  -> use eval_edge_field(space, et[i])
      ez    (m, n_n)  nodal values with E_z = 1j * ez[i]

    Both coefficient arrays are complex, preserving the eigensolver's full span.
    The factor of i follows the variable transformation above. For a real basis,
    the longitudinal component sits in quadrature with the transverse one; a
    complex combination of degenerate modes need not have that componentwise
    phase relation. The relative scaling, and hence |E_z|/|E_t|, is preserved.

    motion=galerkin.shape.MeshMotion(velocity, t) solves on the nodes X0 + t*velocity
    and n_eff, et and ez carry the derivative with respect to the JAX or PyTorch
    scalar t (a shape derivative; docs/packages/galerkin/shape_derivative.md).
    Degenerate modes get NaN derivatives and a DegenerateModeWarning, as above.
    With a motion, coordinate_factors are those of the mesh at the step t; an element whose
    stretch (sx, sy) is not 1 must keep every node in place. coordinate_bend=(radius, axis,
    origin) names the bend of those factors (axis "x" or "y"): the window elements then move,
    and their h = 1 + (centroid - origin) / radius follows the nodes (with a motion only).
    """
    if motion is not None:
        return _solve_modes_moving(mesh, motion, eps_r, k0, n_target, num_modes, mu_r, pec_nodes, pec_edges,
                                   coordinate_factors, coordinate_bend)
    if coordinate_bend is not None:
        raise ValueError("coordinate_bend is taken with a motion only; without one, coordinate_factors hold the bend")
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
    return _joined_system(xp, _mode_blocks(xp, space, eps_r, mu_r, coordinate_factors), space, k0)


def _joined_system(xp, blocks, space, k0):
    """(A, B) of the mode system from its six blocks, as coalesced CooMatrix in ``xp``."""
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
    n_e, n_n = space.num_edges, mesh.num_nodes
    free = _free_dofs(mesh, space, pec_nodes, pec_edges)
    position = np.full(n_e + n_n, -1)
    position[free] = np.arange(len(free))
    n = len(free)
    k0_live = lift(xp, k0, xp.float64)
    A, B = (_restricted(m, position, n) for m in _live_blocks(xp, space, eps_r, mu_r, k0_live,
                                                              coordinate_factors))
    return _refined_modes(xp, A, B, leaves, free, space, k0_live, n_eff0, et0, ez0)


def _refined_modes(xp, A, B, leaves, free, space, k0, n_eff0, et0, ez0):
    """The NumPy modes with the derivatives carried by the live restricted A and B.

    ``leaves`` are the live inputs (for NaN derivatives of degenerate modes); ``k0`` is
    a number or a live scalar (it divides beta).
    """
    complex_dtype = xp.complex128
    n_e, n_n = space.num_edges, space.mesh.num_nodes
    k0_live = k0
    A_numbers, B_numbers = eigen.scipy_matrix(A), eigen.scipy_matrix(B)
    real_problem = np.isrealobj(n_eff0)
    k0_number = float(to_numpy(k0_live))
    lam0 = -(k0_number * np.asarray(n_eff0)) ** 2
    degenerate = eigen.degenerate_modes(A_numbers, B_numbers, lam0)
    if degenerate:
        warnings.warn(f"modes {degenerate} belong to degenerate eigenvalues (relative gap <= "
                      f"{DEGENERATE_GAP:g}); their derivatives are NaN", DegenerateModeWarning,
                      stacklevel=4)
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


_MIDPOINT_LAMBDA = 0.5 * (np.ones((3, 3)) - np.eye(3))     # lambda_i at the edge midpoints q


def _solve_modes_moving(mesh, motion, eps_r, k0, n_target, num_modes, mu_r, pec_nodes, pec_edges,
                        coordinate_factors, coordinate_bend=None):
    """``solve_modes`` on X0 + t W with the derivative with respect to ``motion.t``.

    The NumPy eigensolve runs on the moved mesh; each mode then takes the bordered
    Newton step of the live-input path with A(t) and B(t) assembled from the live node
    coordinates: the same element matrices as galerkin.core.kernels, written in the
    barycentric gradients and areas of X0 + t W."""
    from .shape import motion_step

    for name, value in (("eps_r", eps_r), ("mu_r", mu_r), ("k0", k0), ("n_target", n_target)):
        if callable(value):
            raise TypeError(f"motion: {name} must be a number or a per-element array")
        if contains_live(value):
            raise TypeError(f"motion: {name} is live; in this slice only the motion's t carries a derivative")
    step = motion_step(mesh, motion)
    if coordinate_bend is not None and coordinate_factors is None:
        raise ValueError("motion: coordinate_bend needs the coordinate_factors of the bend")
    if coordinate_factors is not None:
        coordinate_factors = _fixed_coordinate_factors(mesh, step.design_velocity, coordinate_factors,
                                                       bend=coordinate_bend is not None)
    bend = None if coordinate_bend is None else _checked_bend(coordinate_bend)
    n_eff0, space, et0, ez0 = _solve_modes_numpy(step.moved, eps_r, k0, n_target, num_modes, mu_r, pec_nodes,
                                                 pec_edges=pec_edges, coordinate_factors=coordinate_factors)
    xp, A, B, free = _moving_system(mesh, step, space, eps_r, k0, mu_r, pec_nodes, pec_edges,
                                    coordinate_factors=coordinate_factors, coordinate_bend=bend)
    return _refined_modes(xp, A, B, (step.t,), free, space, float(k0), n_eff0, et0, ez0)


def _checked_bend(coordinate_bend):
    """(radius, axis index, origin) of coordinate_bend=(radius, "x" | "y", origin)."""
    try:
        radius, axis, origin = coordinate_bend
    except (TypeError, ValueError):
        raise ValueError("motion: coordinate_bend must be (radius, axis, origin)") from None
    if axis not in ("x", "y"):
        raise ValueError("motion: coordinate_bend axis must be 'x' or 'y'")
    radius, origin = float(radius), float(origin)
    if not (np.isfinite(radius) and radius > 0 and np.isfinite(origin)):
        raise ValueError("motion: coordinate_bend needs a finite positive radius and a finite origin")
    return radius, 0 if axis == "x" else 1, origin


def _fixed_coordinate_factors(mesh, W, coordinate_factors, *, bend=False):
    """Coordinate factors that a motion leaves unchanged, or a refusal by name.

    The factors are those of the moved mesh at the step t (diagonal (sx, sy, h) per element). A PML
    element (a factor other than 1) keeps its centroid, and so its factors, when every one of its nodes
    has zero design velocity; an element of the physical window has factors 1, whose derivative is 0
    (the PML profile has order >= 2, so it is flat where the window ends). The factors then carry no
    derivative, and the moving pencil keeps them as numbers."""
    f = np.asarray(coordinate_factors)
    if contains_live(coordinate_factors) or f.shape != (mesh.num_triangles, 3) or not np.isfinite(f).all() \
            or np.any(f == 0):
        raise ValueError("motion: coordinate_factors must be finite nonzero NumPy numbers (triangles, 3)")
    # with a bend every h differs from 1; only the stretch (sx, sy) marks a PML element then
    stretched = np.any((f[:, :2] if bend else f) != 1, axis=1)
    nodes = np.unique(mesh.triangles[stretched])
    moving = nodes[np.any(np.asarray(W)[nodes] != 0, axis=1)]
    if len(moving):
        raise ValueError(f"motion: the design velocity moves {len(moving)} node(s) of PML or bend elements "
                         f"(first {int(moving[0])}); with coordinate factors it must be 0 on every node of an "
                         "element whose factors are not 1")
    return f


BRANCH_TOLERANCE_LIMIT = 1e-3     # widest relative group taken as degenerate by degenerate_branch_derivatives


@dataclass(frozen=True)
class KernelBranches:
    """One group of degenerate modes and the branches a shape motion splits it into.

    ``modes`` are the indices of the group among the returned modes, ``effective_index`` their
    values at t, ``slopes`` d n_eff / dt of each branch, largest first (per unit of t), and
    ``combinations`` (len(modes), len(modes)): column k holds the coefficients of branch k in
    the returned eigenvectors of ``modes`` (the fields of the branch are those combinations).
    """
    modes: tuple
    effective_index: np.ndarray
    slopes: np.ndarray
    combinations: np.ndarray


def degenerate_branch_derivatives(mesh: Mesh, eps_r, k0: float, n_target, num_modes: int = 6, *, motion,
                                  mu_r=1.0, pec_nodes=None, pec_edges=None, tolerance=DEGENERATE_GAP):
    """The branch slopes of degenerate modes under a shape motion (NumPy numbers, kernel frame).

    The kernel of ``galerkin.waveguide.degenerate_branch_derivatives`` (public, SI, exp(-i omega t)):
    eps_r, n_target and the results are under the kernel's exp(+i omega t).

    ``solve_modes(..., motion=motion)`` gives a degenerate mode NaN derivatives: the sorted
    effective indices have a kink where branches cross. Each branch is smooth, though, and its
    slope is an eigenvalue of the motion's derivative projected onto the degenerate subspace:
    with V the returned eigenvectors of a group, M = V^T (dA/dt - lambda dB/dt) V and
    N = V^T B V, the generalized eigenvalues of (M, N) are d lambda / dt of the branches and
    the eigenvectors their combinations (no conjugate: the pencil is complex symmetric).
    dn_eff = -d lambda / (2 k0^2 n_eff). dA/dt and dB/dt are the derivative of the live
    assembly at t, taken in the library of ``motion.t`` (JAX or PyTorch).

    A group is a set of returned modes whose eigenvalues lie within ``tolerance`` (relative,
    at most BRANCH_TOLERANCE_LIMIT) of each other. ``tolerance`` larger than DEGENERATE_GAP also
    groups nearly degenerate modes (a mesh that splits a symmetric pair): their slopes are then
    those of the exactly degenerate limit, which the modes follow for steps much larger than the
    split, not d n_eff / dt at t of either returned mode (``solve_modes`` with the motion gives
    those). Refused by name: a group with a member that was not returned, or a mode with a
    degenerate partner that was not returned (ask for more modes); a group whose members chain
    beyond ``tolerance``; complex slopes on a real problem. Returns one ``KernelBranches`` per
    group, an empty list when no mode is degenerate. The same inputs as ``solve_modes`` with a
    motion: no coordinate factors, NumPy material data.
    """
    from .shape import MeshMotion, motion_step

    for name, value in (("eps_r", eps_r), ("mu_r", mu_r), ("k0", k0), ("n_target", n_target)):
        if callable(value):
            raise TypeError(f"degenerate_branch_derivatives: {name} must be a number or a per-element array")
        if contains_live(value):
            raise TypeError(f"degenerate_branch_derivatives: {name} is live; only the motion's t is")
    if isinstance(tolerance, (bool, np.bool_)) or not isinstance(tolerance, (int, float, np.integer, np.floating)):
        raise TypeError(f"degenerate_branch_derivatives: tolerance must be a real number, got {tolerance!r}")
    if not (np.isfinite(tolerance) and 0 < tolerance <= BRANCH_TOLERANCE_LIMIT):
        raise ValueError(f"degenerate_branch_derivatives: tolerance must lie in (0, {BRANCH_TOLERANCE_LIMIT:g}], "
                         f"got {tolerance!r}; a wider group is not degenerate and its slopes are not derivatives")
    if not isinstance(motion, MeshMotion):
        raise TypeError("degenerate_branch_derivatives: motion must be a MeshMotion (design velocity and live t)")
    step = motion_step(mesh, motion)
    t0 = float(to_numpy(step.t))
    k0 = float(k0)
    n_eff0, space, et0, ez0 = _solve_modes_numpy(step.moved, eps_r, k0, n_target, num_modes, mu_r, pec_nodes,
                                                 pec_edges=pec_edges)
    xp, A, B, free = _moving_system(mesh, step, space, eps_r, k0, mu_r, pec_nodes, pec_edges)
    A0, B0 = eigen.scipy_matrix(A), eigen.scipy_matrix(B)
    lam0 = -(k0 * np.asarray(n_eff0)) ** 2
    groups = _groups(lam0, tolerance)
    grouped = {i for g in groups for i in g}
    for i, lam in enumerate(lam0):
        if i not in grouped and eigen.neighbour_gap(A0, B0, lam) <= tolerance:
            raise ValueError(f"degenerate_branch_derivatives: mode {i} is degenerate with a mode that was not "
                             "returned; ask for more modes (num_modes) so that its whole group is solved")
    for group in groups:
        _check_group(A0, B0, lam0, group, tolerance)
    design_velocity = motion.design_velocity
    out = []
    for group in groups:
        V = np.stack([np.concatenate([et0[i] * (k0 * n_eff0[i]), ez0[i]])[free] for i in group], axis=1)
        lam = complex(np.mean(lam0[list(group)])) if np.iscomplexobj(lam0) else float(np.mean(lam0[list(group)]))
        m = len(group)

        def projected(s, V=V, lam=lam, m=m):
            moved = motion_step(mesh, MeshMotion(design_velocity=design_velocity, t=s))
            xs, A_s, B_s, _free = _moving_system(mesh, moved, space, eps_r, k0, mu_r, pec_nodes, pec_edges)
            Vl = lift(xs, V)
            rows = [Vl[:, j] @ (A_s.matvec(Vl[:, i]) - lam * B_s.matvec(Vl[:, i])) for j in range(m) for i in range(m)]
            entries = xs.stack(rows)
            return xs.stack([xs.real(entries), xs.imag(entries)]) if "complex" in str(entries.dtype) else entries
        derivative = _jacobian(xp, projected, t0)
        dM = (derivative[0] + 1j * derivative[1]) if derivative.ndim == 2 else derivative
        dM = dM.reshape(m, m)
        N = V.T @ (B0 @ V)
        dlam, combos = la_eig(dM, N)
        n0 = np.asarray(n_eff0)[list(group)]
        n_mean = complex(np.mean(n0)) if np.iscomplexobj(n0) else float(np.mean(n0))
        slopes = -dlam / (2.0 * k0 ** 2 * n_mean)
        if not np.iscomplexobj(n0):
            if np.max(np.abs(slopes.imag)) > 1e-8 * max(np.max(np.abs(slopes)), np.finfo(float).tiny):
                raise ValueError(f"degenerate_branch_derivatives: modes {tuple(int(i) for i in group)} of a real "
                                 "problem gave complex branch slopes (the projected B is indefinite on the group)")
            slopes = slopes.real
        order = np.argsort(-np.real(slopes))
        out.append(KernelBranches(tuple(int(i) for i in group), n0.copy(), slopes[order], combos[:, order]))
    return out


def _groups(lam0, tolerance):
    """Sets of returned eigenvalues within ``tolerance`` (relative) of each other, two or more each."""
    count = len(lam0)
    parent = list(range(count))

    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i
    for i in range(count):
        for j in range(i + 1, count):
            scale = max(abs(lam0[i]), abs(lam0[j]), np.finfo(float).tiny)
            if abs(lam0[i] - lam0[j]) <= tolerance * scale:
                parent[root(j)] = root(i)
    sets = {}
    for i in range(count):
        sets.setdefault(root(i), []).append(i)
    return [tuple(g) for g in sets.values() if len(g) >= 2]


def _check_group(A0, B0, lam0, group, tolerance):
    """Refuse a group that chains beyond ``tolerance`` or has a member that was not returned."""
    members = np.asarray(lam0)[list(group)]
    tiny = np.finfo(float).tiny
    for a in members:
        for b in members:
            if abs(a - b) > tolerance * max(abs(a), abs(b), tiny):
                raise ValueError(f"degenerate_branch_derivatives: modes {tuple(int(i) for i in group)} chain beyond "
                                 "tolerance (some pairs are farther apart than it); lower tolerance")
    nearby = eigen.nearest_eigenvalues(A0, B0, complex(np.mean(members)), len(group) + 1)
    close = [] if nearby is None else [v for v in nearby
                                       if any(abs(v - a) <= tolerance * max(abs(a), tiny) for a in members)]
    if nearby is None or len(close) > len(group):
        reason = "could not be certified complete" if nearby is None else "has a member that was not returned"
        raise ValueError(f"degenerate_branch_derivatives: the group of modes {tuple(int(i) for i in group)} "
                         f"{reason}; ask for more modes (num_modes) so that its whole group is solved")


def _jacobian(xp, function, t0):
    """d function / dt at t0 as NumPy numbers, in the library of ``xp`` (JAX or PyTorch)."""
    import sys      # the engine imports no array library: t is live, so its library is loaded already
    if backend_of(xp) is Backend.JAX:
        jax = sys.modules["jax"]
        return np.asarray(jax.jacrev(function)(xp.asarray(t0, dtype=xp.float64)))
    torch = sys.modules["torch"]
    return torch.autograd.functional.jacobian(function, torch.tensor(t0, dtype=torch.float64)).detach().numpy()


def _moving_system(mesh, step, space, eps_r, k0, mu_r, pec_nodes, pec_edges, *, coordinate_factors=None,
                   coordinate_bend=None):
    """(xp, A, B, free): the restricted pencil assembled from the live node coordinates of ``step``.

    ``coordinate_factors`` (NumPy (T, 3), sx, sy, h) weigh the blocks as in ``_mode_blocks``; a motion
    leaves them fixed (``_fixed_coordinate_factors``)."""
    from .shape import live_triangle_geometry
    xp = step.xp
    cells = space.mesh.triangles
    b, c, area = live_triangle_geometry(xp, mesh, cells, step)
    g = xp.stack([b, c], axis=2) / (2.0 * area)[:, None, None]                      # (T, 3, 2)
    signs = lift(xp, np.asarray(space.signs, dtype=float))
    count = len(cells)
    eps = np.broadcast_to(np.asarray(eps_r), (count,))
    inv_mu = np.broadcast_to(1.0 / np.asarray(mu_r), (count,))
    if not (np.any(np.iscomplex(eps)) or np.any(np.iscomplex(inv_mu))):
        eps, inv_mu = eps.real, inv_mu.real
    eps, inv_mu = lift(xp, np.array(eps)), lift(xp, np.array(inv_mu))
    pairs = list(zip(*TRI_LOCAL_EDGES))
    curls = xp.stack([2.0 * (g[:, i, 0] * g[:, j, 1] - g[:, i, 1] * g[:, j, 0]) for i, j in zip(*pairs)],
                     axis=1) * signs
    lam = _MIDPOINT_LAMBDA
    W = xp.stack([float(lam[q, i]) * g[:, j, :] - float(lam[q, j]) * g[:, i, :]
                  for i, j in zip(*pairs) for q in range(3)], axis=1)
    W = xp.reshape(W, (count, 3, 3, 2)) * signs[:, :, None, None]                   # (T, edge, q, 2)
    WW = xp.sum(W[:, :, None, :, :] * W[:, None, :, :, :], axis=(3, 4))             # (T, e, f)
    diff = xp.stack([g[:, j, :] - g[:, i, :] for i, j in zip(*pairs)], axis=1)       # (T, 3, 2)
    Gd = xp.sum(diff[:, :, None, :] * g[:, None, :, :], axis=3) * signs[:, :, None]  # (T, e, node)
    bb = b[:, :, None] * b[:, None, :] + c[:, :, None] * c[:, None, :]
    p1_mass = lift(xp, (np.ones((3, 3)) + np.eye(3)) / 12.0)
    te, n_e, n_n = space.tri_edges, space.num_edges, mesh.num_nodes
    if coordinate_factors is None:
        mass_eps, mass_mu = WW * (eps * area / 3.0)[:, None, None], WW * (inv_mu * area / 3.0)[:, None, None]
        grad = Gd * (inv_mu * area / 3.0)[:, None, None]
        stiff = (inv_mu / (4.0 * area))[:, None, None] * bb
        curl, mass = inv_mu, eps
    else:
        # J = diag(sx, sy, h): the coefficients of _mode_blocks, with the 2 x 2 diagonal tensors written
        # per component (x: the b / first components, y: the c / second ones)
        f = np.asarray(coordinate_factors)
        sx, sy, h = (lift(xp, column) for column in f.T)
        if coordinate_bend is not None:
            # window elements (sx = sy = 1) move: their h = 1 + (centroid - origin) / R follows the live
            # centroid, written as the number at the step plus the live change (exact derivative)
            radius, axis, _origin = coordinate_bend
            window = np.all(f[:, :2] == 1, axis=1)
            X = lift(xp, mesh.nodes) + step.t * lift(xp, step.design_velocity)
            centre = xp.sum(X[:, axis][cells], axis=1) / 3.0
            centre0 = step.moved.nodes[cells][:, :, axis].mean(axis=1)
            h = h + lift(xp, window.astype(float)) * (centre - lift(xp, centre0)) / radius
        dx, dy = inv_mu * sy / (sx * h), inv_mu * sx / (sy * h)

        def weighted(cx, cy):
            return (xp.sum(W[:, :, None, :, 0] * W[:, None, :, :, 0], axis=3) * cx[:, None, None]
                    + xp.sum(W[:, :, None, :, 1] * W[:, None, :, :, 1], axis=3) * cy[:, None, None])
        mass_eps = weighted(eps * sy * h / sx, eps * sx * h / sy) * (area / 3.0)[:, None, None]
        mass_mu = weighted(dx, dy) * (area / 3.0)[:, None, None]
        grad = (diff[:, :, None, 0] * g[:, None, :, 0] * dx[:, None, None]
                + diff[:, :, None, 1] * g[:, None, :, 1] * dy[:, None, None]) * signs[:, :, None] \
            * (area / 3.0)[:, None, None]
        stiff = (b[:, :, None] * b[:, None, :] * dx[:, None, None]
                 + c[:, :, None] * c[:, None, :] * dy[:, None, None]) / (4.0 * area)[:, None, None]
        curl, mass = inv_mu * h / (sx * sy), eps * sx * sy / h
    blocks = {
        "S": forms.matrix(te, te, (curl * area)[:, None, None] * curls[:, :, None] * curls[:, None, :],
                          (n_e, n_e)),
        "Mt_eps": forms.matrix(te, te, mass_eps, (n_e, n_e)),
        "Mt_mu": forms.matrix(te, te, mass_mu, (n_e, n_e)),
        "G": forms.matrix(te, cells, grad, (n_e, n_n)),
        "K": forms.matrix(cells, cells, stiff, (n_n, n_n)),
        "M": forms.matrix(cells, cells, (mass * area)[:, None, None] * p1_mass[None], (n_n, n_n)),
    }
    free = _free_dofs(step.moved, space, pec_nodes, pec_edges)
    position = np.full(n_e + n_n, -1)
    position[free] = np.arange(len(free))
    A, B = (_restricted(m, position, len(free)) for m in _joined_system(xp, blocks, space, float(k0)))
    return xp, A, B, free


def _cutoff_distance(nodal, N, Mk):
    """delta = 1 / |mu_max|, mu_max the largest eigenvalue of N^-1 Mk (N the factored nodal block
    ``nodal`` = K - k0^2 M, Mk = k0^2 M, on the free nodes): the relative distance of k0^2 from the
    nearest TM cutoff of the PEC box. 0 when the estimate does not converge."""
    m = Mk.shape[0]
    if m <= 2:
        mu = la_eig(Mk.toarray(), nodal.toarray(), right=False)
        return float(1.0 / np.max(np.abs(mu))) if np.all(np.isfinite(mu)) and np.max(np.abs(mu)) > 0 else 0.0
    dtype = np.result_type(N.L.dtype, Mk.dtype)
    operator = spla.LinearOperator((m, m), matvec=lambda x: N.solve(Mk @ x), dtype=dtype)
    mu = eigen.dominant_eigenvalue(operator, tol=1e-3)
    return float(1.0 / abs(mu)) if mu is not None and np.isfinite(mu) and mu != 0 else 0.0


def _static_projector(B, free, n_e, k0, M):
    """The projector P [x_t; x_z] = [x_t; -N^-1 G^T x_t] (N = K - k0^2 M, G^T the nodal-edge
    block of B, both on the free DOFs), or None when the search is not deflated.

    P annihilates the static family [0; e_z] and keeps every other eigenvector of the pencil:
    for lambda != 0 the nodal rows of A x = lambda B x give G^T x_t + N x_z = 0. It commutes
    with (A - sigma B)^-1 B. None when no node is free, and, with a
    StaticFamilyNearCutoffWarning, when k0^2 is within STATIC_DEFLATION_MIN_CUTOFF_DISTANCE of a
    TM cutoff or N cannot be factored.
    """
    edges = free < n_e
    nodes = ~edges
    if not nodes.any():
        return None
    node_ids = free[nodes] - n_e
    nodal = B[nodes][:, nodes].tocsc()
    try:
        N = spla.splu(nodal)
    except RuntimeError:
        delta = 0.0
    else:
        delta = _cutoff_distance(nodal, N, (k0 ** 2 * M.tocsr()[node_ids][:, node_ids]).tocsc())
    if not delta >= STATIC_DEFLATION_MIN_CUTOFF_DISTANCE:
        warnings.warn(f"k0^2 is within a relative {delta:.1e} of a TM cutoff of the PEC box (below "
                      f"{STATIC_DEFLATION_MIN_CUTOFF_DISTANCE:g}): the static beta^2 = 0 family is not "
                      f"deflated, and a search for many roots can reach it", StaticFamilyNearCutoffWarning,
                      stacklevel=4)
        return None
    Gt = B[nodes][:, edges].tocsc()

    def project(x):
        y = np.array(x, copy=True)
        y[nodes] = -N.solve(Gt @ x[edges])
        return y
    return project


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
    for name, value in (("eps_r", eps_r), ("k0", k0), ("mu_r", mu_r), ("coordinate_factors", coordinate_factors)):
        refuse_live(value, f"assemble_mode_system {name}")
    A, B, space, M = _assembled(mesh, eps_r, k0, mu_r, None, coordinate_factors)
    n_e, n_n = space.num_edges, mesh.num_nodes

    free = _free_dofs(mesh, space, pec_nodes, pec_edges)

    A, B = A[free][:, free].tocsc(), B[free][:, free].tocsc()
    n = A.shape[0]

    # Shift-invert as a standard problem: nu = 1 / (lam - sigma), lam = -beta^2
    sigma = -(k0 * n_target) ** 2
    lu = spla.splu((A - sigma * B).tocsc())
    project = _static_projector(B, free, n_e, k0, M)
    if project is None:     # no free node, or k0^2 near a TM cutoff: today's search
        op = spla.LinearOperator((n, n), matvec=lambda x: lu.solve(B @ x), dtype=lu.L.dtype)
        v0 = np.ones(n)
    else:                   # the static family is projected out of every Krylov vector
        op = spla.LinearOperator((n, n), matvec=lambda x: project(lu.solve(B @ x)), dtype=lu.L.dtype)
        v0 = project(np.ones(n, dtype=lu.L.dtype))
    nu, vecs = spla.eigs(op, k=num_modes, which="LM", v0=v0,
                         ncv=min(n, max(4 * num_modes, 40)), maxiter=20000, **arpack_rng())

    beta2 = -(sigma + 1.0 / nu)
    if coordinate_factors is not None and not np.isfinite(np.sqrt(beta2.astype(complex))).all():
        raise RuntimeError("modal coordinate search returned a nonfinite propagation root")
    # Roots of the static beta^2 = 0 family are not modes (module docstring).
    mode = ~(np.abs(beta2) <= STATIC_ROOT_TOL * abs(sigma))
    if project is not None:
        # The deflated search returns roots beyond the static family too (|nu| |sigma| < 1);
        # only those nearer the shift than the family are kept, the roots a search finds
        # before it reaches the family.
        mode &= np.abs(nu) * abs(sigma) > 1.0
    if complex_problem:
        beta = np.sqrt(beta2.astype(complex))
        if coordinate_factors is not None:
            keep = np.flatnonzero(mode)  # let the caller record every candidate and exclusion
        else:
            keep = np.flatnonzero(np.isfinite(beta) & (beta.real > 0) & mode)
        keep = keep[np.lexsort((beta[keep].imag, -beta[keep].real))]
    else:
        beta2 = beta2.real
        keep = np.where((beta2 > 0.0) & mode)[0]
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
