# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Power, overlap, normalisation, coupling efficiency and confinement of modes.

Post-processing for the fields that ``galerkin.waveguide.solve_modes`` returns
(edge line integrals ``et`` of E_t and nodal ``ez`` with E_z = 1j * ez, in the
phasor exp(+i omega t - i beta z), arbitrary amplitude) and for scalar P1 mode
functions ``phi`` on a ``Mesh``. The formulation and the measured validation are
in docs/packages/galerkin/mode_overlap.md.

Formulation
-----------
Faraday's law in the phasor above gives the transverse magnetic field of a mode
from its electric field alone,

    H_t = (beta / (omega mu)) zhat x E_t + (1 / (i omega mu)) zhat x grad_t E_z,

and with (a x (zhat x b)) . zhat = a . b for transverse a, b the complex
Poynting integral of one mode's E against another's H is

    P_ab = 1/2 int (E_a x H_b^*) . zhat dA
         = (1 / (2 omega mu0)) int conj(1/mu_r) [ conj(beta_b) E_ta . E_tb^* + i E_ta . grad_t E_zb^* ] dA.

Re P_aa is the time-averaged power a mode carries in +z; for a lossless mode
P_aa is real. With E_t = sum_e et_e W_e (Whitney edge functions) and
E_z = i sum_n ez_n phi_n (P1 hat functions) the integrals are exactly

    P_ab = (1 / (2 omega mu0)) [ conj(beta_b) et_b^H M_e(c) et_a + ez_b^H G(c)^T et_a ],   c = conj(1/mu_r),

where M_e(c) = int c W_e . W_f is the edge mass (``assemble_edge_mass``) and
G(c) = int c W_e . grad phi_n the edge-nodal coupling (``assemble_edge_grad``);
both are exact for the piecewise-polynomial integrands. omega mu0 = k0 c mu0
with k0 in inverse mesh units. The field overlap is

    <E_a, E_b> = int E_a^* . E_b dA = et_a^H M_e(1) et_b + ez_a^H M(1) ez_b,

with M(1) the P1 mass (``assemble_mass``), and the energy confinement in a set
of triangles R is Gamma = int_R eps_r |E|^2 / int eps_r |E|^2 with the same two
mass matrices carrying the coefficient Re(eps_r) restricted to R. The scalar
functions use the P1 mass alone.

The effective area A_eff = (int |E|^2 dA)^2 / int |E|^4 dA takes its numerator
from the same mass matrices and its denominator from a fixed symmetric
triangle rule (Dunavant's 6-point degree-4 rule, ``triangle_symmetric_rule``)
applied to the Whitney/P1 interpolant: both E_t and E_z are linear on each
triangle, so |E|^4 is a polynomial of degree 4 there and the rule is exact.

Units
-----
With the mesh in metres and E in V/m, ``vector_power`` is in watts. With the mesh
in another length unit L (metres per mesh unit) and k0 in the matching inverse
unit, the result is in watts when E is in volts per mesh unit; for E in V/m
multiply by L^2. Field overlaps carry (field unit)^2 (mesh unit)^2; efficiencies
and confinement factors are dimensionless.

Limitations
-----------
NumPy only: JAX and PyTorch values raise TypeError (``refuse_live``), since these
integrals would otherwise cut the derivative silently. The power definition is
the lossless-waveguide one (Re of the complex Poynting integral); for lossy or
leaky modes it is still the +z power of the given field, but modes are then not
power-orthogonal and the imaginary part is reactive. No Studio exposure (simcase
saves power, confinement, overlaps and Gaussian coupling with closed-window
``em.modes2d`` results: ``simcase.mode_postprocessing``).
"""

from __future__ import annotations

import numpy as np
from scipy.constants import c as _C_LIGHT, mu_0 as _MU_0

from .assembly import assemble_mass
from .core import kernels
from .core.checks import one_of, positive_real, refuse_live
from .core.quadrature import triangle_symmetric_rule
from .core.spaces import TRI_LOCAL_EDGES
from .edge import EdgeSpace, assemble_edge_grad, assemble_edge_mass, eval_edge_field
from .mesh import Mesh

__all__ = ["vector_power", "vector_cross_power", "vector_field_overlap", "normalize_vector",
           "coupling_efficiency", "confinement_factor", "overlap_matrix", "centroid_field",
           "interpolate_vector_field", "effective_area", "scalar_power", "scalar_overlap",
           "normalize_scalar", "scalar_coupling_efficiency", "scalar_confinement_factor",
           "scalar_effective_area"]

_GAUSS2 = (0.5 - 0.5 / np.sqrt(3.0), 0.5 + 0.5 / np.sqrt(3.0))


# -- input checks --------------------------------------------------------------

def _vector(value, size, name, *, allow_2d=False):
    """``value`` as a complex array of shape (size,) or, if allowed, (m, size)."""
    refuse_live(value, name)
    a = np.asarray(value)
    if a.dtype.kind not in "iufc":
        raise ValueError(f"{name} must be a numeric array")
    a = a.astype(complex, copy=False)
    if a.shape != (size,) and not (allow_2d and a.ndim == 2 and a.shape[1] == size):
        expected = f"({size},)" + (f" or (m, {size})" if allow_2d else "")
        raise ValueError(f"{name} has shape {a.shape}, expected {expected}")
    if not np.isfinite(a).all():
        raise ValueError(f"{name} must be finite")
    return a


def _edge_dofs(space, et, name, allow_2d=False):
    return _vector(et, space.num_edges, name, allow_2d=allow_2d)


def _nodal(mesh, ez, name, allow_2d=False):
    return _vector(ez, mesh.num_nodes, name, allow_2d=allow_2d)


def _coefficient(mesh, value, name):
    """Scalar or per-triangle (T,) coefficient as a (T,) array; complex allowed."""
    refuse_live(value, name)
    a = np.asarray(value)
    if a.dtype.kind not in "iufc" or not np.isfinite(a).all():
        raise ValueError(f"{name} must be finite numbers")
    if a.shape not in ((), (mesh.num_triangles,)):
        raise ValueError(f"{name} must be a scalar or a per-triangle array of shape "
                         f"({mesh.num_triangles},), got {a.shape}")
    return np.broadcast_to(a, (mesh.num_triangles,))


def _mask(mesh, triangles, name="triangles"):
    """A boolean mask (T,) from a boolean mask or an index array of triangles."""
    refuse_live(triangles, name)
    t = np.asarray(triangles)
    n = mesh.num_triangles
    if t.dtype == bool:
        if t.shape != (n,):
            raise ValueError(f"{name} mask has shape {t.shape}, expected ({n},)")
        return t
    if t.dtype.kind not in "iu" or t.ndim != 1:
        raise ValueError(f"{name} must be a boolean mask (T,) or a 1-D integer index array")
    if t.size and (t.min() < 0 or t.max() >= n):
        raise ValueError(f"{name} indices must lie in [0, {n})")
    mask = np.zeros(n, dtype=bool)
    mask[t] = True
    return mask


def _wavenumber(k0):
    return positive_real(k0, "k0")


def _effective_index(n_eff):
    refuse_live(n_eff, "n_eff")
    a = np.asarray(n_eff)
    if a.shape != () or a.dtype.kind not in "iufc" or not np.isfinite(a):
        raise ValueError("n_eff must be a finite scalar (real or complex)")
    return complex(a)


def _omega_mu0(k0):
    """omega mu0 = k0 c mu0 for k0 in inverse mesh units (SI: 1/m -> ohm/m)."""
    return k0 * _C_LIGHT * _MU_0


# -- vector modes --------------------------------------------------------------

def _poynting_matrices(space, mu_r):
    c = np.conj(1.0 / _coefficient(space.mesh, mu_r, "mu_r"))
    if np.isrealobj(np.asarray(mu_r)):
        c = c.real
    return assemble_edge_mass(space, c), assemble_edge_grad(space, c)


def _cross_power(me, g, k0, et_a, ez_a, et_b, ez_b, n_eff_b):
    """P_ab of the module docstring from assembled M_e(c), G(c); a carries E, b carries H^*."""
    beta_b = k0 * n_eff_b
    transverse = np.conj(beta_b) * (np.conj(et_b) @ (me @ et_a))
    longitudinal = np.conj(ez_b) @ (g.T @ et_a)
    return complex((transverse + longitudinal) / (2.0 * _omega_mu0(k0)))


def vector_power(space: EdgeSpace, et, ez, n_eff, k0, mu_r=1.0) -> complex:
    """Complex Poynting integral P = 1/2 int (E_t x H_t^*) . zhat dA of one mode.

    et (n_e,) and ez (n_n,) as ``solve_modes`` returns them (E_z = 1j * ez),
    n_eff = beta / k0 of that mode (complex allowed), k0 in inverse mesh units
    and mu_r a scalar or per-triangle relative permeability. ``Re P`` is the
    time-averaged power in +z; for a lossless mode the imaginary part is zero
    up to roundoff. Units: watts with the mesh in metres and E in V/m (module
    docstring for other length units). NumPy only.
    """
    et = _edge_dofs(space, et, "et")
    ez = _nodal(space.mesh, ez, "ez")
    k0, n_eff = _wavenumber(k0), _effective_index(n_eff)
    me, g = _poynting_matrices(space, mu_r)
    return _cross_power(me, g, k0, et, ez, et, ez, n_eff)


def vector_cross_power(space: EdgeSpace, et_a, ez_a, et_b, ez_b, n_eff_b, k0, mu_r=1.0) -> complex:
    """Cross Poynting term P_ab = 1/2 int (E_a x H_b^*) . zhat dA.

    H_b is the magnetic field of mode b, which needs its effective index
    ``n_eff_b``; for a = b this is ``vector_power``. Exact modes of a lossless
    guide with distinct beta have P_ab = 0; the discrete modes approach that at
    the convergence order of the fields (docs/packages/galerkin/mode_overlap.md).
    NumPy only.
    """
    et_a, et_b = (_edge_dofs(space, v, n) for v, n in ((et_a, "et_a"), (et_b, "et_b")))
    ez_a, ez_b = (_nodal(space.mesh, v, n) for v, n in ((ez_a, "ez_a"), (ez_b, "ez_b")))
    k0, n_eff_b = _wavenumber(k0), _effective_index(n_eff_b)
    me, g = _poynting_matrices(space, mu_r)
    return _cross_power(me, g, k0, et_a, ez_a, et_b, ez_b, n_eff_b)


def _field_overlap(me, mn, et_a, ez_a, et_b, ez_b):
    out = np.conj(et_a) @ (me @ et_b)
    if ez_a is not None:
        out = out + np.conj(ez_a) @ (mn @ ez_b)
    return complex(out)


def vector_field_overlap(space: EdgeSpace, et_a, ez_a, et_b, ez_b, include_longitudinal=True) -> complex:
    """<E_a, E_b> = int E_a^* . E_b dA with the exact edge and nodal mass matrices.

    include_longitudinal=False drops the E_z term (``ez_a``, ``ez_b`` may then
    be None). Units (field unit)^2 (mesh unit)^2. NumPy only.
    """
    et_a, et_b = (_edge_dofs(space, v, n) for v, n in ((et_a, "et_a"), (et_b, "et_b")))
    me = assemble_edge_mass(space, 1.0)
    if not include_longitudinal:
        return _field_overlap(me, None, et_a, None, et_b, None)
    ez_a, ez_b = (_nodal(space.mesh, v, n) for v, n in ((ez_a, "ez_a"), (ez_b, "ez_b")))
    return _field_overlap(me, assemble_mass(space.mesh, 1.0), et_a, ez_a, et_b, ez_b)


def centroid_field(space: EdgeSpace, et, ez=None) -> np.ndarray:
    """E = (E_x, E_y, E_z) at triangle centroids, (T, 3) complex.

    E_t from ``eval_edge_field`` and E_z = 1j * (mean of the three nodal ez);
    E_z is zero when ``ez`` is None. NumPy only.
    """
    et = _edge_dofs(space, et, "et")
    mesh = space.mesh
    out = np.zeros((mesh.num_triangles, 3), dtype=complex)
    out[:, :2] = eval_edge_field(space, et)
    if ez is not None:
        out[:, 2] = 1j * _nodal(mesh, ez, "ez")[mesh.triangles].mean(axis=1)
    return out


def normalize_vector(space: EdgeSpace, et, ez, n_eff=None, k0=None, mu_r=1.0,
                     convention: str = "power"):
    """(et, ez) scaled to one of three conventions; the phase is left unchanged.

    "power": Re ``vector_power`` = 1 (needs ``n_eff`` and ``k0``; Re P must be
             positive, so a backward or nonphysical candidate raises ValueError);
    "mass":  int |E|^2 dA = 1 (``vector_field_overlap`` of the mode with itself);
    "peak":  max centroid |E| = 1, the simcase vector convention
             (``centroid_field``).
    NumPy only.
    """
    convention = one_of(convention, ("power", "mass", "peak"), "convention")
    et = _edge_dofs(space, et, "et")
    ez = _nodal(space.mesh, ez, "ez")
    if convention == "power":
        if n_eff is None or k0 is None:
            raise ValueError("convention 'power' needs n_eff and k0")
        p = vector_power(space, et, ez, n_eff, k0, mu_r).real
        if not p > 0:
            raise ValueError(f"the mode carries no positive +z power (Re P = {p:.3g}); "
                             "power normalisation needs Re P > 0")
        scale = np.sqrt(p)
    elif convention == "mass":
        scale = np.sqrt(vector_field_overlap(space, et, ez, et, ez).real)
    else:
        scale = np.linalg.norm(centroid_field(space, et, ez), axis=1).max()
    if not np.isfinite(scale) or scale == 0:
        raise ValueError("the field is zero or nonfinite and cannot be normalised")
    return et / scale, ez / scale


def _projection_efficiency(gram, cross, self_in):
    """|<m, in>|^2 / (<m, m> <in, in>), or for several modes the share of ``in`` in their span.

    gram (m, m) = <m_i, m_j>, cross (m,) = <m_i, in>, self_in = <in, in>:
    eta = cross^H gram^{-1} cross / self_in.
    """
    if not self_in > 0:
        raise ValueError("the input field has zero norm")
    gram = np.atleast_2d(gram)
    cross = np.atleast_1d(cross)
    if gram.shape == (1, 1):
        if not gram[0, 0].real > 0:
            raise ValueError("the mode field has zero norm")
        return float(abs(cross[0]) ** 2 / (gram[0, 0].real * self_in))
    try:
        coefficients = np.linalg.solve(gram, cross)
    except np.linalg.LinAlgError:
        raise ValueError("the mode fields are linearly dependent") from None
    return float(np.real(np.conj(cross) @ coefficients) / self_in)


def coupling_efficiency(space: EdgeSpace, et_mode, ez_mode, et_in, ez_in=None) -> float:
    """eta = |<E_mode, E_in>|^2 / (<E_mode, E_mode> <E_in, E_in>) with the field overlap.

    The longitudinal component enters only when ``ez_in`` is given; a transverse
    input (``ez_in`` None) is compared with E_t of the mode alone. ``et_mode``
    (and ``ez_mode``) may hold several modes, shape (m, n_e) (and (m, n_n)):
    eta is then the share of the input in their span, ||P E_in||^2 / ||E_in||^2
    with the orthogonal projector of the field overlap, which is how a
    degenerate pair is handled. An input known as a function is interpolated
    with ``interpolate_vector_field``. NumPy only.
    """
    et_mode = _edge_dofs(space, et_mode, "et_mode", allow_2d=True)
    et_in = _edge_dofs(space, et_in, "et_in")
    modes = np.atleast_2d(et_mode)
    me = assemble_edge_mass(space, 1.0)
    gram = np.conj(modes) @ (me @ modes.T)
    cross = np.conj(modes) @ (me @ et_in)
    self_in = (np.conj(et_in) @ (me @ et_in)).real
    if ez_in is not None:
        mesh = space.mesh
        ez_mode = _nodal(mesh, ez_mode, "ez_mode", allow_2d=True)
        ez_in = _nodal(mesh, ez_in, "ez_in")
        ez_modes = np.atleast_2d(ez_mode)
        if ez_modes.shape[0] != modes.shape[0]:
            raise ValueError("et_mode and ez_mode must hold the same number of modes")
        mn = assemble_mass(mesh, 1.0)
        gram = gram + np.conj(ez_modes) @ (mn @ ez_modes.T)
        cross = cross + np.conj(ez_modes) @ (mn @ ez_in)
        self_in = self_in + (np.conj(ez_in) @ (mn @ ez_in)).real
    return _projection_efficiency(gram, cross, self_in)


def confinement_factor(space: EdgeSpace, et, ez, eps_r, triangles) -> float:
    """Gamma = int_R Re(eps_r) |E|^2 dA / int Re(eps_r) |E|^2 dA, energy weighting.

    eps_r: scalar or per-triangle (T,); only its real part weights the field.
    triangles: boolean mask (T,) or index array naming the region R. Both E_t
    (edge mass) and E_z (nodal mass) count. NumPy only.
    """
    et = _edge_dofs(space, et, "et")
    ez = _nodal(space.mesh, ez, "ez")
    eps = _coefficient(space.mesh, eps_r, "eps_r").real
    mask = _mask(space.mesh, triangles)

    def energy(coefficient):
        return (np.conj(et) @ (assemble_edge_mass(space, coefficient) @ et)).real + \
               (np.conj(ez) @ (assemble_mass(space.mesh, coefficient) @ ez)).real
    total = energy(eps)
    if not total > 0:
        raise ValueError("the field carries no energy; cannot form a confinement factor")
    return float(energy(np.where(mask, eps, 0.0)) / total)


def overlap_matrix(space: EdgeSpace, et, ez, kind: str = "field", n_eff=None, k0=None, mu_r=1.0) -> np.ndarray:
    """Pairwise overlaps of a set of modes, et (m, n_e) and ez (m, n_n): (m, m) complex.

    kind="field": O_ab = <E_a, E_b> = int E_a^* . E_b dA (Hermitian).
    kind="power": O_ab = P_ab = 1/2 int (E_a x H_b^*) . zhat dA, which needs the
                  effective indices n_eff (m,) and k0; the diagonal is
                  ``vector_power`` of each mode. NumPy only.
    """
    kind = one_of(kind, ("field", "power"), "kind")
    et = np.atleast_2d(_edge_dofs(space, et, "et", allow_2d=True))
    ez = np.atleast_2d(_nodal(space.mesh, ez, "ez", allow_2d=True))
    if et.shape[0] != ez.shape[0]:
        raise ValueError("et and ez must hold the same number of modes")
    if kind == "field":
        me, mn = assemble_edge_mass(space, 1.0), assemble_mass(space.mesh, 1.0)
        return np.conj(et) @ (me @ et.T) + np.conj(ez) @ (mn @ ez.T)
    if n_eff is None or k0 is None:
        raise ValueError("kind 'power' needs n_eff and k0")
    refuse_live(n_eff, "n_eff")
    n = np.asarray(n_eff)
    if n.shape != (et.shape[0],) or n.dtype.kind not in "iufc" or not np.isfinite(n).all():
        raise ValueError(f"n_eff must hold one finite value per mode, shape ({et.shape[0]},)")
    k0 = _wavenumber(k0)
    me, g = _poynting_matrices(space, mu_r)
    m = et.shape[0]
    out = np.empty((m, m), dtype=complex)
    for a in range(m):
        for b in range(m):
            out[a, b] = _cross_power(me, g, k0, et[a], ez[a], et[b], ez[b], complex(n[b]))
    return out


def interpolate_vector_field(space: EdgeSpace, field):
    """(et, ez) of a field given as a function, in the gauge of ``solve_modes``.

    ``field(x, y)`` takes two (N,) coordinate arrays and returns (N, 2) or
    (N, 3) values (E_x, E_y[, E_z]), real or complex. et_e is the tangential
    line integral of E_t along edge e in its global direction (low node id to
    high), by two-point Gauss quadrature (exact for a cubic variation along
    the edge): the lowest-order Nedelec interpolant. ez = -1j * E_z at the
    nodes, so that E_z = 1j * ez; ez is None for a two-component field.

    A centroid-sampled (T, 2) field cannot be mapped onto edge dofs exactly:
    the centroid values of the Whitney functions are linearly dependent on
    each triangle (the constant-curl bubble vanishes there), so that map has a
    kernel on common structured meshes and a least-squares fit is not unique.
    Sample the field as a function instead. NumPy only.
    """
    mesh = space.mesh
    p = mesh.nodes[space.edges]                     # (E, 2 ends, 2)
    d = p[:, 1] - p[:, 0]
    et = np.zeros(space.num_edges, dtype=complex)
    components = None
    for s in _GAUSS2:
        q = p[:, 0] + s * d
        values = field(q[:, 0], q[:, 1])
        refuse_live(values, "interpolate_vector_field field values")  # before np.asarray hides the library
        values = np.asarray(values)
        if values.ndim != 2 or values.shape[0] != space.num_edges or values.shape[1] not in (2, 3):
            raise ValueError(f"field must return (N, 2) or (N, 3) values for N points, got {values.shape}")
        components = values.shape[1]
        et += 0.5 * np.einsum("ed,ed->e", values[:, :2], d)
    if components == 2:
        return et, None
    values = field(mesh.nodes[:, 0], mesh.nodes[:, 1])
    refuse_live(values, "interpolate_vector_field field values")
    values = np.asarray(values)
    if values.shape != (mesh.num_nodes, 3):
        raise ValueError(f"field must return (N, 3) values at the {mesh.num_nodes} nodes, got {values.shape}")
    return et, -1j * values[:, 2].astype(complex)


# -- effective area --------------------------------------------------------------

_QUARTIC_RULE = 4   # degree of the symmetric triangle rule for int |E|^4; exact for the linear interpolants


def _quartic_integral(mesh, density_at, degree):
    """int (|E|^2)^2 dA by the symmetric rule of ``degree``; ``density_at(bary) -> (T, Q)`` gives |E|^2."""
    bary, weights = triangle_symmetric_rule(degree)
    density = density_at(bary)
    return float(np.einsum("t,tq,q->", mesh.areas(), density ** 2, weights))


def _vector_density(space, et, ez):
    """|E|^2 of the Whitney (and P1) interpolant at barycentric points, as a function of ``bary`` (Q, 3)."""
    mesh = space.mesh
    g, _ = kernels.triangle_gradients(mesh)                     # (T, 3, 2)
    coefficients = space.signs * et[space.tri_edges]            # (T, 3)

    def density(bary):
        e_t = np.zeros((mesh.num_triangles, len(bary), 2), dtype=complex)
        for e, (i, j) in enumerate(TRI_LOCAL_EDGES):
            w = bary[None, :, i, None] * g[:, None, j, :] - bary[None, :, j, None] * g[:, None, i, :]
            e_t += coefficients[:, e, None, None] * w
        out = np.sum(np.abs(e_t) ** 2, axis=-1)
        if ez is not None:
            out = out + np.abs(np.einsum("qk,tk->tq", bary, ez[mesh.triangles])) ** 2
        return out
    return density


def _scalar_density(mesh, phi):
    def density(bary):
        return np.abs(np.einsum("qk,tk->tq", bary, phi[mesh.triangles])) ** 2
    return density


def _effective_area(mesh, power, quartic):
    if not quartic > 0:
        raise ValueError("the field is zero; cannot form an effective area")
    return float(power ** 2 / quartic)


def effective_area(space: EdgeSpace, et, ez, include_longitudinal=False) -> float:
    """A_eff = (int |E|^2 dA)^2 / int |E|^4 dA of one vector mode, in (mesh unit)^2.

    The numerator is the exact field overlap of the mode with itself
    (``vector_field_overlap``); the denominator integrates (|E|^2)^2 of the
    Whitney/P1 interpolant with Dunavant's 6-point degree-4 symmetric triangle
    rule, which is exact because E_t and E_z are linear on each triangle. By
    default |E|^2 = |E_t|^2, the usual transverse definition; with
    include_longitudinal=True it is |E_t|^2 + |E_z|^2 (``ez`` may be None
    otherwise). Scale free. NumPy only.
    """
    et = _edge_dofs(space, et, "et")
    if include_longitudinal:
        ez = _nodal(space.mesh, ez, "ez")
    else:
        ez = None
    power = _field_overlap(assemble_edge_mass(space, 1.0), None if ez is None else assemble_mass(space.mesh, 1.0),
                           et, ez, et, ez).real
    return _effective_area(space.mesh, power, _quartic_integral(space.mesh, _vector_density(space, et, ez),
                                                                _QUARTIC_RULE))


# -- scalar modes --------------------------------------------------------------

def scalar_power(mesh: Mesh, phi) -> float:
    """int |phi|^2 dA with the exact P1 mass matrix (the scalar mode "power").

    phi: nodal values (n_n,), real or complex. NumPy only.
    """
    phi = _nodal(mesh, phi, "phi")
    return float((np.conj(phi) @ (assemble_mass(mesh, 1.0) @ phi)).real)


def scalar_overlap(mesh: Mesh, a, b) -> complex:
    """<a, b> = int a^* b dA of two nodal P1 fields with the exact mass matrix. NumPy only."""
    a, b = _nodal(mesh, a, "a"), _nodal(mesh, b, "b")
    return complex(np.conj(a) @ (assemble_mass(mesh, 1.0) @ b))


def normalize_scalar(mesh: Mesh, phi, convention: str = "power"):
    """phi scaled to "power" (int |phi|^2 = 1, phase unchanged) or "peak".

    "peak" divides by the value at the node of largest |phi|, so that peak is
    exactly 1 (a complex field loses its arbitrary phase there), as the
    simcase scalar solver does. NumPy only.
    """
    convention = one_of(convention, ("power", "peak"), "convention")
    phi = _nodal(mesh, phi, "phi")
    if convention == "power":
        scale = np.sqrt(scalar_power(mesh, phi))
    else:
        scale = phi[np.argmax(np.abs(phi))]
    if not np.isfinite(scale) or scale == 0:
        raise ValueError("the field is zero or nonfinite and cannot be normalised")
    return phi / scale


def scalar_coupling_efficiency(mesh: Mesh, mode, field) -> float:
    """eta = |<mode, field>|^2 / (<mode, mode> <field, field>) with the P1 mass.

    ``mode`` may hold several modes, shape (m, n_n): eta is then the share of
    the field in their span (orthogonal projection in the mass inner product).
    NumPy only.
    """
    mode = np.atleast_2d(_nodal(mesh, mode, "mode", allow_2d=True))
    field = _nodal(mesh, field, "field")
    m = assemble_mass(mesh, 1.0)
    gram = np.conj(mode) @ (m @ mode.T)
    cross = np.conj(mode) @ (m @ field)
    return _projection_efficiency(gram, cross, (np.conj(field) @ (m @ field)).real)


def scalar_confinement_factor(mesh: Mesh, phi, triangles) -> float:
    """Gamma = int_R |phi|^2 dA / int |phi|^2 dA, the P1 mass restricted to the triangles R.

    triangles: boolean mask (T,) or index array. NumPy only.
    """
    phi = _nodal(mesh, phi, "phi")
    mask = _mask(mesh, triangles)
    total = scalar_power(mesh, phi)
    if not total > 0:
        raise ValueError("the field is zero; cannot form a confinement factor")
    inside = (np.conj(phi) @ (assemble_mass(mesh, mask.astype(float)) @ phi)).real
    return float(inside / total)


def scalar_effective_area(mesh: Mesh, phi) -> float:
    """A_eff = (int |phi|^2 dA)^2 / int |phi|^4 dA of a nodal P1 field, in (mesh unit)^2.

    The numerator is ``scalar_power`` (exact P1 mass); the denominator uses the
    degree-4 symmetric triangle rule on the P1 interpolant, exact since |phi|^4
    is a quartic on each triangle. Scale free. NumPy only.
    """
    phi = _nodal(mesh, phi, "phi")
    return _effective_area(mesh, scalar_power(mesh, phi),
                           _quartic_integral(mesh, _scalar_density(mesh, phi), _QUARTIC_RULE))
