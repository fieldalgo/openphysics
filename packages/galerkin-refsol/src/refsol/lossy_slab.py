# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Planar multilayer slab with complex permittivity: bound lossy and leaky modes.

Geometry. ``x`` is the layered direction and ``z`` the propagation direction.
``eps[0]`` fills the left half-space ``x < 0``, ``eps[j]`` for ``0 < j < N-1``
the layer of thickness ``thickness[j-1]`` whose left face is at
``sum(thickness[:j-1])``, and ``eps[N-1]`` the right half-space beyond the last
interface. Every material is isotropic and may be complex.

Public API (galerkin step, L3 commit 11c). The public functions take SI
keyword-only registry names: ``relative_permittivity`` one value per layer (left
half-space first), ``thickness`` one value per interior layer in m,
``vacuum_wavelength`` in m, ``effective_index`` and ``target_effective_index``;
``points`` (x in m) leads ``field``. Their complex values follow exp(-i omega t),
as the rest of refsol: a passive material has ``Im eps >= 0`` (a refractive index
``n' + i n''`` with ``n'' >= 0``) and a mode attenuated along ``+z`` has
``Im n_eff > 0``. The arithmetic below is written in exp(+i omega t), the
convention of the galerkin mode kernels, and is unchanged: each public function
converts its complex inputs with ``refsol._conventions.to_kernel`` and returns
``to_public`` of the result, the conjugate, so the formulas and the branch rules
below read with the signs of exp(+i omega t). On the public side ``"decay"`` has
``Im Q >= 0`` and a leaky mode on ``"outgoing"`` has ``Im n_eff > 0``.

Convention of the formulas below. Fields vary as ``exp(+i omega t - i beta z)`` with
``beta = k0 n_eff``, ``k0 = 2 pi / wavelength``. A passive material has
``Im eps <= 0`` (a refractive index ``n' - i n''`` with ``n'' >= 0``) and a mode
attenuated along ``+z`` has ``Im n_eff < 0``.

Equation. The principal field component ``phi`` is ``E_y`` for TE and ``H_y`` for
TM. In each layer ``phi'' + k0**2 (eps - n_eff**2) phi = 0``, and at an interface
``phi`` and ``phi' / w`` are continuous with ``w = 1`` (TE) or ``w = eps`` (TM).
With ``Q_j = sqrt(eps_j - n_eff**2)`` (``q_j = k0 Q_j`` is the transverse
wavenumber) the state ``(phi, phi' / (k0 w))`` crosses a layer of thickness ``d``
through the transfer matrix

    [[cos(k0 Q d),           (w / Q) sin(k0 Q d)],
     [-(Q / w) sin(k0 Q d),  cos(k0 Q d)       ]],

which is even in ``Q``, so interior layers need no branch choice. The left
exterior field is ``exp(+i k0 Q_0 x)`` and the right exterior field
``exp(-i k0 Q_R (x - x_R))``; the characteristic function is the right-side
impedance mismatch of the transferred left state,

    F(n_eff) = psi_R + i (Q_R / w_R) phi_R,

analytic in ``n_eff`` away from the exterior branch cuts. Its zeros are the
modes. For a lossless three-layer slab they coincide with the roots of the
``atan`` dispersion relation in ``refsol.slab`` (checked by the tests).

Branches. The exterior square roots fix which sheet a mode lives on:

``"decay"``
    ``Im Q <= 0``: the exterior field decays away from the stack. This is the
    proper (physical) sheet of a bound mode, lossless or absorbing. With the
    convention above the left field ``exp(+i k0 Q_0 x)`` and the right field
    ``exp(-i k0 Q_R (x - x_R))`` both decay for ``Im Q < 0``.
``"outgoing"``
    ``Re Q >= 0``: the exterior field carries power away from the stack
    (its phase advances toward ``-x`` on the left, ``+x`` on the right). Choose
    it for a half-space above the light line, ``Re eps > Re n_eff**2``, into
    which the mode radiates. A leaky mode found on this sheet has ``Im n_eff < 0``
    and, since then ``Im Q_R > 0``, a transversally *growing* exterior field: the
    familiar improper leaky wave (Marcuse 1974, Hu & Menyuk 2009), and the pole
    a complex-coordinate PML solver converges to.

For a lossless half-space below the light line ``Re Q = 0`` and ``"outgoing"``
cannot decide; for one above the light line ``Im Q = 0`` and ``"decay"`` cannot.
Pick the branch from the physics of each exterior.

Roots. ``solve`` refines a guess with ``scipy.optimize.root`` on the real and
imaginary parts of ``F`` and then polishes with complex Newton steps, and
rejects any result whose normalized residual exceeds ``tol``. ``continued_root``
follows one root along a path of structures; ``three_layer_modes`` starts every
guided mode from the lossless ``refsol.slab`` root and switches the imaginary
parts of the permittivities on gradually, and ``substrate_leaky_mode`` starts
from the bound mode of an isolated slab and shrinks the gap to a high-index
substrate on the outgoing sheet.

Sources. The transfer-matrix form of the slab dispersion relation and the
``exp(+i omega t)`` passivity signs follow Chew, *Waves and Fields in
Inhomogeneous Media* (IEEE Press, 1995, ch. 2) and Pozar, *Microwave
Engineering* (4th ed., Wiley, 2012). The leaky-mode branch and its growing
exterior field: D. Marcuse, *Theory of Dielectric Optical Waveguides*
(Academic Press, 1974) and J. Hu and C. R. Menyuk, "Understanding leaky
modes: slab waveguide revisited," Adv. Opt. Photon. 1, 58-106 (2009).
"""

from __future__ import annotations

import cmath
import math

import numpy as np
from scipy.optimize import root

from . import slab as _slab
from ._checks import pair, refuse_text
from ._conventions import to_kernel, to_public

__all__ = ["BRANCHES", "exterior_root", "characteristic", "residual", "solve", "continued_root",
           "three_layer_modes", "substrate_leaky_mode", "field"]

BRANCHES = ("decay", "outgoing")


def _complex_array(values, name):
    a = np.asarray(values, dtype=complex)
    if a.ndim != 1 or a.size < 2 or not np.all(np.isfinite(a)):
        raise ValueError(f"{name} must be a finite one-dimensional sequence of at least two permittivities")
    return a


def _stack(eps, thickness):
    eps = _complex_array(eps, "eps")
    d = np.asarray(thickness, dtype=float).reshape(-1)
    if d.size != eps.size - 2 or not np.all(np.isfinite(d)) or np.any(d <= 0):
        raise ValueError("thickness must hold one finite positive value per interior layer")
    return eps, d


def _weights(eps, pol):
    pol = pol.upper()
    if pol not in ("TE", "TM"):
        raise ValueError("pol must be 'TE' or 'TM'")
    return np.ones_like(eps) if pol == "TE" else eps


def _branches(branches):
    if len(branches) != 2 or any(b not in BRANCHES for b in branches):
        raise ValueError(f"branches must be a pair from {BRANCHES}")
    return tuple(branches)


def _exterior_root(eps, neff, branch) -> complex:
    """``Q = sqrt(eps - neff**2)`` of a half-space on the ``"decay"`` or ``"outgoing"`` sheet.

    ``"decay"`` returns the root with ``Im Q <= 0``; ``"outgoing"`` the root with
    ``Re Q >= 0`` (the principal square root). See the module docstring.
    """
    q = cmath.sqrt(complex(eps) - complex(neff) ** 2)
    if branch == "decay":
        return -q if q.imag > 0 else q
    if branch == "outgoing":
        return -q if q.real < 0 else q
    raise ValueError(f"branch must be one of {BRANCHES}")


def _layer_matrix(eps_j, w_j, neff, k0d):
    """Transfer matrix of one interior layer; even in Q, so any root of Q will do."""
    q = cmath.sqrt(eps_j - neff * neff)
    arg = q * k0d
    c = cmath.cos(arg)
    if abs(arg) < 1e-4:
        sinc = k0d * (1 - arg * arg / 6 + arg**4 / 120)          # sin(q k0 d) / q
    else:
        sinc = cmath.sin(arg) / q
    return np.array([[c, w_j * sinc], [-(q * q) * sinc / w_j, c]], dtype=complex)


def _transfer(neff, eps, w, d, k0, branches):
    """Left-exterior state carried to the last interface, and the right-side terms.

    Returns ``(phi_R, psi_R, Q_R / w_R, scale)`` so that ``F = psi_R + i (Q_R / w_R) phi_R``;
    ``scale`` sums the state magnitudes at every interface.
    """
    neff = complex(neff)
    q0 = _exterior_root(eps[0], neff, branches[0])
    state = np.array([1.0, 1j * q0 / w[0]], dtype=complex)
    scale = abs(state[0]) + abs(state[1])
    for j in range(1, len(eps) - 1):
        state = _layer_matrix(eps[j], w[j], neff, k0 * d[j - 1]) @ state
        scale += abs(state[0]) + abs(state[1])
    qr = _exterior_root(eps[-1], neff, branches[1])
    return state[0], state[1], qr / w[-1], scale


def _characteristic(neff, eps, thickness, wavelength, pol="TE",
                   branches=("decay", "decay")) -> complex:
    """``F(n_eff)``: the analytic characteristic function whose zeros are the modes."""
    eps, d = _stack(eps, thickness)
    w = _weights(eps, pol)
    k0 = 2 * math.pi / float(wavelength)
    phi, psi, z, _ = _transfer(neff, eps, w, d, k0, _branches(branches))
    return complex(psi + 1j * z * phi)


def _residual(neff, eps, thickness, wavelength, pol="TE", branches=("decay", "decay")) -> float:
    """``|F|`` relative to the magnitude of the quantities that formed it.

    The scale is ``(1 + |Q_R / w_R|)`` times the sum over all interfaces of the
    transferred state magnitudes ``|phi| + |psi|``. Rounding in the transfer
    product is proportional to that sum: a thick evanescent layer first grows
    the state like ``exp(k0 |Im Q| d)`` and then cancels it, so the attainable
    absolute ``|F|`` is larger there, while this backward-error measure stays
    at rounding level for an exact root.
    """
    eps, d = _stack(eps, thickness)
    w = _weights(eps, pol)
    k0 = 2 * math.pi / float(wavelength)
    phi, psi, z, scale = _transfer(neff, eps, w, d, k0, _branches(branches))
    scale *= 1 + abs(z)
    return float(abs(psi + 1j * z * phi) / scale) if scale > 0 else float("inf")


def _solve(eps, thickness, wavelength, guess, pol="TE", branches=("decay", "decay"),
          tol=1e-12, max_newton=12) -> complex:
    """Refine ``guess`` to a zero of ``F`` and verify it.

    ``scipy.optimize.root`` (hybr) acts on ``(Re F, Im F)`` as functions of
    ``(Re n, Im n)``; complex Newton steps with a central-difference derivative
    then polish the root to rounding. Raises ``RuntimeError`` when the normalized
    ``residual`` of the result exceeds ``tol``.
    """
    eps, d = _stack(eps, thickness)
    w = _weights(eps, pol)
    br = _branches(branches)
    k0 = 2 * math.pi / float(wavelength)

    def f(n):
        phi, psi, z, _ = _transfer(n, eps, w, d, k0, br)
        return psi + 1j * z * phi

    def parts(v):
        value = f(complex(v[0], v[1]))
        return [value.real, value.imag]

    start = complex(guess)
    answer = root(parts, [start.real, start.imag], method="hybr", tol=1e-13)
    n = complex(answer.x[0], answer.x[1]) if answer.success else start
    # Newton polish: F is analytic, so a complex central difference is its derivative.
    best, best_res = n, _residual(n, eps, d, wavelength, pol, br)
    for _ in range(max_newton):
        h = 1e-7 * max(1.0, abs(n))
        derivative = (f(n + h) - f(n - h)) / (2 * h)
        if derivative == 0:
            break
        n = n - f(n) / derivative
        res = _residual(n, eps, d, wavelength, pol, br)
        if res < best_res:
            best, best_res = n, res
        if res < 1e-16:
            break
    if not (best_res <= tol):
        # the message shows the caller's values: public exp(-i omega t), as every public input and output
        raise RuntimeError(f"no root near {to_public(start)}: residual {best_res:.3e} > {tol:.1e} at {to_public(best)}")
    return best


def _continued_root(path, wavelength, neff_start, pol="TE", branches=("decay", "decay"),
                   steps=8, tol=1e-12) -> complex:
    """Follow one root of ``F`` along ``path(t) -> (eps, thickness)`` from ``t=0`` to ``t=1``.

    ``neff_start`` is the root of the structure at ``t=0``. Each step takes the
    previous root (after the first step, a linear extrapolation of the last two)
    as the guess for ``solve``. Returns the root at ``t=1``.
    """
    if steps < 1:
        raise ValueError("subdivision_count must be a positive integer")
    previous, current = None, complex(neff_start)
    for i in range(1, steps + 1):
        eps, d = path(i / steps)
        guess = current if previous is None else 2 * current - previous
        found = _solve(eps, d, wavelength, guess, pol, branches, tol=tol)
        previous, current = current, found
    return current


def _passive_index(value, name):
    n = complex(value)
    if not (cmath.isfinite(n) and n.real > 0 and n.imag <= 0):
        raise ValueError(f"{name} must be finite with Re > 0 and Im <= 0 (n' - i n'', exp(+i omega t))")
    return n


def _three_layer_modes(n_f, n_s, n_c, d, wavelength, pol="TE", max_modes=50,
                      steps=8, tol=1e-12) -> list[complex]:
    """Bound modes of an absorbing slab ``n_s | n_f | n_c`` (substrate at ``x<0``), m = 0 first.

    Complex indices are ``n' - i n''`` with ``n'' >= 0``. The real-part structure
    ``sqrt(Re eps)`` must guide: its modes come from ``refsol.slab.modes`` and are
    continued as the imaginary parts of all three permittivities are scaled from
    0 to 1 on the ``"decay"`` sheet. Each result has ``Im n_eff <= 0``.
    """
    nf, ns, nc = (_passive_index(v, name) for v, name in ((n_f, "n_f"), (n_s, "n_s"), (n_c, "n_c")))
    eps = np.array([ns * ns, nf * nf, nc * nc])
    real_index = np.sqrt(eps.real)
    if not real_index[1] > max(real_index[0], real_index[2]):
        raise ValueError("Re of the film's permittivity must exceed the substrate's and the cover's: the lossless "
                         "structure must guide")
    lossless = _slab._modes(real_index[1], real_index[0], real_index[2], d, wavelength, pol, max_modes)
    if not np.any(eps.imag):
        return [complex(n) for n in lossless]

    def path(t):
        return eps.real + 1j * t * eps.imag, [d]

    return [_continued_root(path, wavelength, n, pol, ("decay", "decay"), steps, tol) for n in lossless]


def _substrate_leaky_mode(n_f, n_gap, n_sub, d, gap, wavelength, n_cover=None, pol="TE",
                         mode=0, steps=12, tol=1e-12) -> complex:
    """Leaky mode of ``cover | film d | gap material | substrate`` with ``Re n_sub > Re n_eff``.

    Layers from the left: cover half-space (``n_cover``, default ``n_gap``), the
    film of thickness ``d``, the gap layer of thickness ``gap`` and the substrate
    half-space, all passive ``n' - i n''``. The root is continued from guided
    mode ``mode`` of the isolated slab ``cover | film | gap material`` (its
    real-part structure, with imaginary parts switched on along the way) by
    shrinking the gap geometrically from ``8 / (k0 gamma)``, where ``gamma`` is
    the evanescent decay rate of that bound mode into the gap material, to
    ``gap``. Branches are ``("decay", "outgoing")``: the mode radiates into the
    substrate on the improper sheet (``Im Q_sub > 0``, growing substrate field).
    """
    nf, ng, nsub = (_passive_index(v, name) for v, name in ((n_f, "n_f"), (n_gap, "n_gap"), (n_sub, "n_sub")))
    ncov = ng if n_cover is None else _passive_index(n_cover, "n_cover")
    gap = float(gap)
    if not gap > 0:
        raise ValueError("thickness must hold a positive gap thickness")
    eps = np.array([ncov * ncov, nf * nf, ng * ng, nsub * nsub])
    real_index = np.sqrt(eps.real)
    if not real_index[1] > max(real_index[0], real_index[2]):
        raise ValueError("the lossless cover | film | gap slab must guide")
    lossless = _slab._modes(real_index[1], real_index[0], real_index[2], d, wavelength, pol)
    if mode >= len(lossless):
        raise ValueError(f"the isolated slab guides only {len(lossless)} {pol} mode(s)")
    n0 = lossless[mode]
    if not real_index[3] > n0:
        raise ValueError("the substrate's Re refractive_index must exceed the bound effective index for leakage")
    k0 = 2 * math.pi / float(wavelength)
    gamma = math.sqrt(n0 * n0 - real_index[2] ** 2)
    start_gap = max(gap, 8.0 / (k0 * gamma))

    def path(t):
        return eps.real + 1j * t * eps.imag, [d, start_gap * (gap / start_gap) ** t]

    return _continued_root(path, wavelength, n0, pol, ("decay", "outgoing"), steps, tol)


def _field(x, neff, eps, thickness, wavelength, pol="TE", branches=("decay", "decay")):
    """Principal field ``phi(x)`` (``E_y`` for TE, ``H_y`` for TM) of a root ``neff``.

    Unit amplitude at the first interface ``x = 0``; complex array of ``x``'s shape.
    Continuous with continuous ``phi'/w`` at every interface when ``neff`` is a root.
    """
    eps, d = _stack(eps, thickness)
    w = _weights(eps, pol)
    br = _branches(branches)
    k0 = 2 * math.pi / float(wavelength)
    neff = complex(neff)
    x = np.asarray(x, dtype=float)
    faces = np.concatenate([[0.0], np.cumsum(d)])
    out = np.empty(x.shape, dtype=complex)
    q0 = _exterior_root(eps[0], neff, br[0])
    state = np.array([1.0, 1j * q0 / w[0]], dtype=complex)
    left = x < 0
    out[left] = np.exp(1j * k0 * q0 * x[left])
    for j in range(1, len(eps) - 1):
        inside = (x >= faces[j - 1]) & (x < faces[j])
        if np.any(inside):
            local = x[inside] - faces[j - 1]
            q = cmath.sqrt(eps[j] - neff * neff)
            if abs(q) < 1e-12:
                out[inside] = state[0] + state[1] * w[j] * k0 * local
            else:
                out[inside] = (state[0] * np.cos(k0 * q * local)
                               + state[1] * (w[j] / q) * np.sin(k0 * q * local))
        state = _layer_matrix(eps[j], w[j], neff, k0 * d[j - 1]) @ state
    qr = _exterior_root(eps[-1], neff, br[1])
    right = x >= faces[-1]
    out[right] = state[0] * np.exp(-1j * k0 * qr * (x[right] - faces[-1]))
    return out


# -- public API: SI registry names and exp(-i omega t) ---------------------------------------------------------

def _public_permittivities(values, name="relative_permittivity"):
    """The layer permittivities as a complex array in the internal convention (``to_kernel``)."""
    if isinstance(values, (str, bytes)):
        refuse_text(**{name: values})
    return to_kernel(_complex_array(values, name))


def _public_index(value, name):
    """A passive refractive index n' + i n'' (exp(-i omega t), n'' >= 0), in the internal convention."""
    n = complex(value)
    if not (cmath.isfinite(n) and n.real > 0 and n.imag >= 0):
        raise ValueError(f"{name} must be finite with Re > 0 and Im >= 0 (n' + i n'' under exp(-i omega t))")
    return to_kernel(n)


def exterior_root(*, relative_permittivity, effective_index, branch) -> complex:
    """``Q = sqrt(eps - n_eff**2)`` of a half-space on the ``"decay"`` or ``"outgoing"`` sheet.

    exp(-i omega t): ``"decay"`` returns the root with ``Im Q >= 0``; ``"outgoing"`` the root with
    ``Re Q >= 0``. See the module docstring.
    """
    refuse_text(relative_permittivity=relative_permittivity, effective_index=effective_index)
    return to_public(_exterior_root(to_kernel(complex(relative_permittivity)), to_kernel(complex(effective_index)),
                                    branch))


def characteristic(*, effective_index, relative_permittivity, thickness, vacuum_wavelength, pol="TE",
                   branches=("decay", "decay")) -> complex:
    """``F(n_eff)``: the analytic characteristic function whose zeros are the modes (exp(-i omega t))."""
    refuse_text(effective_index=effective_index, relative_permittivity=relative_permittivity, thickness=thickness,
                vacuum_wavelength=vacuum_wavelength)
    return to_public(_characteristic(to_kernel(complex(effective_index)), _public_permittivities(relative_permittivity),
                                     thickness, vacuum_wavelength, pol, branches))


def residual(*, effective_index, relative_permittivity, thickness, vacuum_wavelength, pol="TE",
             branches=("decay", "decay")) -> float:
    """``|F|`` relative to the magnitude of the quantities that formed it (``_residual``)."""
    refuse_text(effective_index=effective_index, relative_permittivity=relative_permittivity, thickness=thickness,
                vacuum_wavelength=vacuum_wavelength)
    return _residual(to_kernel(complex(effective_index)), _public_permittivities(relative_permittivity), thickness,
                     vacuum_wavelength, pol, branches)


def solve(*, relative_permittivity, thickness, vacuum_wavelength, target_effective_index, pol="TE",
          branches=("decay", "decay"), relative_tolerance=1e-12, iteration_limit=12) -> complex:
    """Refine ``target_effective_index`` to a zero of ``F`` and verify it (exp(-i omega t)).

    ``scipy.optimize.root`` (hybr) and then at most ``iteration_limit`` complex Newton steps;
    ``RuntimeError`` when the normalized ``residual`` exceeds ``relative_tolerance``.
    """
    refuse_text(relative_permittivity=relative_permittivity, thickness=thickness, vacuum_wavelength=vacuum_wavelength,
                target_effective_index=target_effective_index, relative_tolerance=relative_tolerance,
                iteration_limit=iteration_limit)
    return to_public(_solve(_public_permittivities(relative_permittivity), thickness, vacuum_wavelength,
                            to_kernel(complex(target_effective_index)), pol, branches, tol=relative_tolerance,
                            max_newton=iteration_limit))


def continued_root(path, *, vacuum_wavelength, effective_index, pol="TE", branches=("decay", "decay"),
                   subdivision_count=8, relative_tolerance=1e-12) -> complex:
    """Follow one root of ``F`` along ``path(t) -> (relative_permittivity, thickness)`` from t=0 to t=1.

    ``effective_index`` is the root of the structure at ``t=0``; ``path`` returns permittivities in
    exp(-i omega t). The path is taken in ``subdivision_count`` steps; returns the root at t=1.
    """
    refuse_text(vacuum_wavelength=vacuum_wavelength, effective_index=effective_index,
                subdivision_count=subdivision_count, relative_tolerance=relative_tolerance)

    def internal_path(t):
        eps, d = path(t)
        return _public_permittivities(eps), d

    return to_public(_continued_root(internal_path, vacuum_wavelength, to_kernel(complex(effective_index)), pol,
                                     branches, subdivision_count, relative_tolerance))


def three_layer_modes(*, refractive_index, thickness, vacuum_wavelength, pol="TE", mode_count=50,
                      subdivision_count=8, relative_tolerance=1e-12) -> list[complex]:
    """Bound modes of an absorbing slab, m = 0 first; exp(-i omega t).

    refractive_index: (substrate, film, cover), each ``n' + i n''`` with ``n'' >= 0`` (the substrate at
    ``x < 0``); thickness: the film's, in m. The real-part structure must guide; each result has
    ``Im n_eff >= 0``. See ``_three_layer_modes`` for the continuation.
    """
    refuse_text(refractive_index=refractive_index, thickness=thickness, vacuum_wavelength=vacuum_wavelength,
                mode_count=mode_count, subdivision_count=subdivision_count, relative_tolerance=relative_tolerance)
    if isinstance(refractive_index, (str, bytes)) or np.ndim(refractive_index) != 1 or len(refractive_index) != 3:
        raise ValueError("refractive_index must hold the three indices (substrate, film, cover)")
    ns, nf, nc = (_public_index(v, f"refractive_index[{i}]") for i, v in enumerate(refractive_index))
    return [to_public(n) for n in _three_layer_modes(nf, ns, nc, thickness, vacuum_wavelength, pol, mode_count,
                                                     subdivision_count, relative_tolerance)]


def substrate_leaky_mode(*, refractive_index, thickness, vacuum_wavelength, pol="TE", mode_index=0,
                         subdivision_count=12, relative_tolerance=1e-12) -> complex:
    """Leaky mode of ``cover | film | gap material | substrate`` with ``Re n_sub > Re n_eff``; exp(-i omega t).

    refractive_index: (cover, film, gap material, substrate), each ``n' + i n''`` with ``n'' >= 0``;
    thickness: the pair (film, gap) in m. Continued from guided mode ``mode_index`` of the isolated slab
    (``_substrate_leaky_mode``); the result has ``Im n_eff > 0`` on the outgoing sheet.
    """
    refuse_text(refractive_index=refractive_index, thickness=thickness, vacuum_wavelength=vacuum_wavelength,
                mode_index=mode_index, subdivision_count=subdivision_count, relative_tolerance=relative_tolerance)
    if isinstance(refractive_index, (str, bytes)) or np.ndim(refractive_index) != 1 or len(refractive_index) != 4:
        raise ValueError("refractive_index must hold the four indices (cover, film, gap material, substrate)")
    ncov, nf, ng, nsub = (_public_index(v, f"refractive_index[{i}]") for i, v in enumerate(refractive_index))
    d, gap = pair(thickness, "thickness")
    return to_public(_substrate_leaky_mode(nf, ng, nsub, d, gap, vacuum_wavelength, ncov, pol, mode_index,
                                           subdivision_count, relative_tolerance))


def field(points, *, effective_index, relative_permittivity, thickness, vacuum_wavelength, pol="TE",
          branches=("decay", "decay")):
    """Principal field ``phi(x)`` (``E_y`` for TE, ``H_y`` for TM) of a root, at positions ``points`` in m.

    Unit amplitude at the first interface ``x = 0``; complex array of the points' shape, exp(-i omega t).
    """
    refuse_text(points=points, effective_index=effective_index, relative_permittivity=relative_permittivity,
                thickness=thickness, vacuum_wavelength=vacuum_wavelength)
    return to_public(_field(points, to_kernel(complex(effective_index)),
                            _public_permittivities(relative_permittivity), thickness, vacuum_wavelength, pol,
                            branches))
