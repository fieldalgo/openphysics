# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Constant-radius bent slab waveguide: complex poles from cylindrical Bessel matching.

Optional module: it needs ``mpmath`` (BSD) for Bessel and Hankel functions of
complex order, which NumPy/SciPy do not provide. ``mpmath`` is imported lazily
on first use and is not a dependency of ``galerkin-refsol``; without it every
public function raises ``ImportError`` naming the package.

Geometry. A film of index ``n_f`` and thickness ``d`` occupies ``R <= r <= R + d``
in cylindrical coordinates, cladding ``n_clad`` fills ``r < R`` and ``r > R + d``.
Propagation is along the arc at the reference radius ``R`` (``z = R theta``), so
with ``exp(+i omega t - i nu theta)`` the angular order is ``nu = k0 R n_eff`` and
``n_eff`` is the effective index referred to ``R``, the convention of the galerkin
bend solver (``bend.radius`` at ``origin``, arc-length propagation).

Equation. The principal field ``phi`` (``E_theta``-free TE: ``E_z``; TM: ``H_z``)
solves Bessel's equation of order ``nu`` in each region with ``phi`` and
``phi'/w`` continuous (``w = 1`` TE, ``w = n^2`` TM):

    r < R:        J_nu(k0 n_clad r)                 regular on the axis
    R < r < R+d:  A J_nu(k0 n_f r) + B Y_nu(k0 n_f r)
    r > R+d:      H_nu^(2)(k0 n_clad r)             outgoing for exp(+i omega t)

The characteristic function is the logarithmic-derivative mismatch at ``R + d``
of the inner solution carried through the film against the outgoing Hankel
function. Its zeros have ``Im n_eff < 0``: the mode radiates past the caustic
radius ``R n_eff / n_clad`` where the Hankel field becomes propagating, and the
exterior field grows transversally like every leaky wave (Marcuse 1976).
Large ``R`` recovers the straight slab root of ``refsol.slab`` with the loss
vanishing exponentially in ``R``.

Sources. D. Marcuse, "Curvature loss formula for optical fibers," J. Opt. Soc.
Am. 66, 216 (1976); K. R. Hiremath, M. Hammer, R. Stoffer, L. Prkna and
J. Čtyroký, "Analytic approach to dielectric optical bent slab waveguides,"
Opt. Quantum Electron. 37, 37 (2005), whose Bessel/Hankel matching this module
reproduces independently.
"""

from __future__ import annotations

import math

from . import slab as _slab


def _mpmath():
    try:
        import mpmath
    except ImportError as error:        # pragma: no cover - exercised without the extra
        raise ImportError("refsol.bent_slab needs the optional 'mpmath' package "
                          "(python -m pip install mpmath); it is not a galerkin-refsol dependency") from error
    return mpmath


def _check(n_f, n_clad, d, radius, wavelength, pol):
    pol = pol.upper()
    if pol not in ("TE", "TM"):
        raise ValueError("pol must be 'TE' or 'TM'")
    for name, value in (("n_f", n_f), ("n_clad", n_clad), ("d", d), ("radius", radius), ("wavelength", wavelength)):
        if not (isinstance(value, (int, float)) and math.isfinite(value) and value > 0):
            raise ValueError(f"{name} must be a finite positive real number")
    if not n_f > n_clad:
        raise ValueError("the film index must exceed the cladding index")
    return pol


def _mismatch(mp, neff, n_f, n_clad, d, radius, k0, pol):
    """``(F, scale)``: the outer logarithmic-derivative mismatch and its magnitude scale."""
    nu = k0 * radius * neff

    def column(kind, index, r):
        f = {"J": mp.besselj, "Y": mp.bessely, "H": mp.hankel2}[kind]
        z = k0 * index * r
        value = f(nu, z)
        derivative = k0 * index * (f(nu - 1, z) - f(nu + 1, z)) / 2      # d/dr of f(nu, k0 n r)
        weight = index**2 if pol == "TM" else 1
        return mp.matrix([value, derivative / (k0 * weight)])

    inner = column("J", n_clad, radius)
    a, b = column("J", n_f, radius), column("Y", n_f, radius)
    coefficients = mp.lu_solve(mp.matrix([[a[0], b[0]], [a[1], b[1]]]), inner / inner[0])
    a, b = column("J", n_f, radius + d), column("Y", n_f, radius + d)
    state = coefficients[0] * a + coefficients[1] * b
    outer = column("H", n_clad, radius + d)
    ratio = outer[1] / outer[0]
    return state[1] - ratio * state[0], abs(state[1]) + abs(ratio * state[0])


def characteristic(neff, n_f, n_clad, d, radius, wavelength, pol="TE", dps=40) -> complex:
    """Characteristic function at ``neff``; zeros are the bent-slab poles."""
    pol = _check(n_f, n_clad, d, radius, wavelength, pol)
    mp = _mpmath()
    with mp.workdps(dps):
        value, _ = _mismatch(mp, mp.mpc(complex(neff)), n_f, n_clad, d, radius, 2 * math.pi / wavelength, pol)
        return complex(value)


def residual(neff, n_f, n_clad, d, radius, wavelength, pol="TE", dps=40) -> float:
    """``|F|`` relative to the magnitude of its two terms."""
    pol = _check(n_f, n_clad, d, radius, wavelength, pol)
    mp = _mpmath()
    with mp.workdps(dps):
        value, scale = _mismatch(mp, mp.mpc(complex(neff)), n_f, n_clad, d, radius, 2 * math.pi / wavelength, pol)
        return float(abs(value) / scale) if scale > 0 else math.inf


def mode(n_f, n_clad, d, radius, wavelength, pol="TE", order=0, guess=None, dps=40,
         tol=1e-12) -> complex:
    """Complex effective index (referred to ``radius``) of bent mode ``order``.

    Starts a secant iteration from the straight-slab root of that order (or
    ``guess``) and a point slightly below it in the complex plane, and raises
    ``RuntimeError`` when the normalized ``residual`` of the result exceeds
    ``tol``. The returned value has ``Im n_eff <= 0``.
    """
    pol = _check(n_f, n_clad, d, radius, wavelength, pol)
    mp = _mpmath()
    k0 = 2 * math.pi / wavelength
    if guess is None:
        straight = _slab.modes(n_f, n_clad, n_clad, d, wavelength, pol)
        if order >= len(straight):
            raise ValueError(f"the straight slab guides only {len(straight)} {pol} mode(s)")
        guess = complex(straight[order])
    guess = complex(guess)
    with mp.workdps(dps):
        def f(n):
            return _mismatch(mp, n, n_f, n_clad, d, radius, k0, pol)[0]
        starts = (mp.mpc(guess.real, guess.imag), mp.mpc(guess.real - 1e-4, guess.imag - 1e-4))
        root = mp.findroot(f, starts, solver="secant", tol=mp.mpf(10) ** (-dps + 8), maxsteps=100)
        value = complex(root)
        _, scale = _mismatch(mp, root, n_f, n_clad, d, radius, k0, pol)
        normalized = float(abs(f(root)) / scale)
    if not normalized <= tol:
        raise RuntimeError(f"no bent-slab pole near {guess}: residual {normalized:.3e} > {tol:.1e}")
    return value
