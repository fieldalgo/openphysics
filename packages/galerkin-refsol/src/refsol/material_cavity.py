# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Independent complex resonances of PEC boxes with dielectric/magnetic loading.

Time convention: fields vary as ``exp(+j*omega*t)``. A passive material has
``eps_r = eps' - j*eps''`` with ``eps'' >= 0`` (likewise ``mu_r``), and a decaying
resonance has ``Im(omega) > 0``. The quality factor is

    Q = Re(omega) / (2 * Im(omega)),

the ratio of the energy decay rate to the oscillation phase rate. The complex
wave number is ``k0 = omega / c0``; ``k0**2`` is the eigenvalue.

This module uses no mesh, FEM solver or numerical eigenproblem. Uniform filling
is a closed-form rescaling of the vacuum spectrum. A slab filling the full
cross-section ``0 <= z <= d`` is solved from the TE-to-z and TM-to-z transcendental
equations with pure-Python bisection and complex secant continuation.
"""

from __future__ import annotations

from dataclasses import dataclass
import cmath
import math
from numbers import Complex, Real

from .cavity import C0


def _positive(value, name):
    if (isinstance(value, bool) or not isinstance(value, Real)
            or not math.isfinite(value) or value <= 0):
        raise ValueError(f"{name} must be a finite positive real number")
    return float(value)


def _material(value, name):
    """Finite passive complex constant: Re > 0, Im <= 0 under exp(+j*omega*t)."""
    if isinstance(value, bool) or not isinstance(value, Complex):
        raise ValueError(f"{name} must be a finite complex number")
    value = complex(value)
    if not (cmath.isfinite(value) and value.real > 0 and value.imag <= 0):
        raise ValueError(f"{name} must be finite with positive real part and "
                         "non-positive imaginary part (passive, exp(+j*omega*t))")
    return value


def quality_factor(complex_frequency_hz) -> float:
    """``Re(f)/(2 Im(f))``; infinity for a lossless real frequency."""
    f = complex(complex_frequency_hz)
    return math.inf if f.imag == 0 else f.real / (2 * f.imag)


def complex_frequency_from_eigenvalue(eigenvalue_m2) -> complex:
    """Principal ``c0*sqrt(k0**2)/(2*pi)``; passive spectra have ``Re > 0``."""
    return C0 * cmath.sqrt(complex(eigenvalue_m2)) / (2 * math.pi)


def uniformly_filled_eigenvalue(vacuum_eigenvalue_m2, relative_permittivity,
                                relative_permeability=1.0) -> complex:
    """Exact ``k0**2 = k_vac**2 / (eps_r * mu_r)`` for a homogeneous PEC cavity.

    Every vacuum mode keeps its field and only its eigenvalue is rescaled.
    For ``eps_r = eps'(1 - j*tan_delta)`` and ``mu_r = 1`` the quality factor is
    ``(1 + sqrt(1 + tan_delta**2)) / (2 * tan_delta)``, close to ``1/tan_delta``.
    """
    vacuum = _positive(vacuum_eigenvalue_m2, "vacuum_eigenvalue_m2")
    eps = _material(relative_permittivity, "relative_permittivity")
    mu = _material(relative_permeability, "relative_permeability")
    return vacuum / (eps * mu)


def dielectric_loss_quality_factor(loss_tangent) -> float:
    """Exact Q of a uniformly filled cavity with ``eps' (1 - j*tan_delta)``, mu_r real."""
    t = _positive(loss_tangent, "loss_tangent")
    return (1 + math.sqrt(1 + t * t)) / (2 * t)


@dataclass(frozen=True)
class SlabCavityMode:
    """One TE-to-z or TM-to-z resonance of a slab-loaded box.

    ``indices`` are the transverse (m, n) standing-wave indices along x and y;
    ``order`` counts lossless roots of that family and (m, n) from zero.
    ``eigenvalue_m2`` is complex ``k0**2`` and ``frequency_hz`` complex.
    """

    family: str
    indices: tuple[int, int]
    order: int
    eigenvalue_m2: complex
    frequency_hz: complex
    quality_factor: float
    lossless_eigenvalue_m2: float


def _sinc_term(u, length):
    """``sin(k*L)/k`` with ``k**2 = u``: even in k, so independent of the branch."""
    k = cmath.sqrt(u)
    x = k * length
    if abs(x) < 1e-4:
        return length * (1 - x * x / 6 + x**4 / 120)
    return cmath.sin(x) / k


def _cos_term(u, length):
    return cmath.cos(cmath.sqrt(u) * length)


def _dispersion(family, eigenvalue, transverse, slab, rest, materials):
    """Entire characteristic function in k0**2; zeros are exactly the resonances.

    Region 1 is the slab ``0<z<d`` and region 2 the remainder ``d<z<c``, with
    ``kz_i**2 = eps_i mu_i k0**2 - kt**2``. Dividing the classical forms by kz
    factors leaves no spurious zero where ``kz_i = 0``:

    TE-to-z: (cos1 S2)/mu1 + (S1 cos2)/mu2 = 0
    TM-to-z: kz1**2 (S1 cos2)/eps1 + kz2**2 (S2 cos1)/eps2 = 0

    with ``S_i = sin(kz_i L_i)/kz_i`` and ``cos_i = cos(kz_i L_i)``.
    """
    (eps1, mu1), (eps2, mu2) = materials
    u1 = eps1 * mu1 * eigenvalue - transverse
    u2 = eps2 * mu2 * eigenvalue - transverse
    s1, c1 = _sinc_term(u1, slab), _cos_term(u1, slab)
    s2, c2 = _sinc_term(u2, rest), _cos_term(u2, rest)
    if family == "TE_z":
        return c1 * s2 / mu1 + s1 * c2 / mu2
    return u1 * s1 * c2 / eps1 + u2 * s2 * c1 / eps2


def _real_roots(function, upper, samples):
    """All sign changes of a real function on (0, upper], refined by bisection."""
    roots = []
    step = upper / samples
    left, f_left = step * 1e-6, function(step * 1e-6)
    for i in range(1, samples + 1):
        right = step * i
        f_right = function(right)
        if f_left == 0:
            roots.append(left)
        elif f_left * f_right < 0:
            a, b, fa = left, right, f_left
            for _ in range(200):
                mid = 0.5 * (a + b)
                fm = function(mid)
                if fm == 0 or b - a <= 4e-16 * b:
                    break
                if fa * fm < 0:
                    b = mid
                else:
                    a, fa = mid, fm
            roots.append(0.5 * (a + b))
        left, f_left = right, f_right
    return roots


def _secant(function, start, scale):
    x0, x1 = start, start * (1 + 1e-7) + 1e-7 * scale
    f0, f1 = function(x0), function(x1)
    for _ in range(200):
        if f1 == f0:
            break
        x2 = x1 - f1 * (x1 - x0) / (f1 - f0)
        x0, f0, x1 = x1, f1, x2
        f1 = function(x1)
        if abs(x1 - x0) <= 1e-15 * abs(x1):
            return x1
    if abs(x1 - x0) <= 1e-12 * abs(x1):
        return x1
    raise RuntimeError("complex secant continuation did not converge")


def slab_loaded_cavity_modes(lengths_m, slab_thickness_m, max_frequency_hz, *,
                             slab_permittivity, slab_permeability=1.0,
                             background_permittivity=1.0, background_permeability=1.0,
                             scan_samples=4000, continuation_steps=16):
    """Resonances of an ``a x b x c`` PEC box with a slab filling ``0 <= z <= d``.

    The slab covers the full ``a x b`` cross-section. Transverse fields are the
    rectangular standing waves ``kx = m*pi/a``, ``ky = n*pi/b``. TE-to-z modes
    (``Ez = 0``) need ``m + n > 0``; TM-to-z modes (``Hz = 0``) need ``m, n >= 1``.

    Lossless roots are found as sign changes of the real characteristic function
    on a uniform scan of ``k0**2`` below the ceiling (``scan_samples`` intervals
    per family and (m, n)) and refined by bisection. A root pair closer than one
    scan interval can be missed; the scan is a reference enumeration, not a
    certificate. Each lossless root is then continued to the complex materials
    in ``continuation_steps`` linear homotopy steps of the imaginary parts, with
    a complex secant iteration at each step. The ceiling applies to the lossless
    (real-part) frequency. Modes are sorted by the real part of ``k0**2``.
    """
    try:
        lengths = tuple(lengths_m)
    except TypeError as exc:
        raise ValueError("lengths_m must contain three positive lengths") from exc
    if len(lengths) != 3:
        raise ValueError("lengths_m must contain three positive lengths")
    a, b, c = (_positive(v, "lengths_m") for v in lengths)
    d = _positive(slab_thickness_m, "slab_thickness_m")
    if d >= c:
        raise ValueError("slab_thickness_m must be smaller than the z length")
    ceiling = _positive(max_frequency_hz, "max_frequency_hz")
    lossy = ((_material(slab_permittivity, "slab_permittivity"),
              _material(slab_permeability, "slab_permeability")),
             (_material(background_permittivity, "background_permittivity"),
              _material(background_permeability, "background_permeability")))
    lossless = tuple((complex(e.real), complex(m.real)) for e, m in lossy)
    upper = (2 * math.pi * ceiling / C0) ** 2
    # Real parts set the lossless spectrum, so the largest real eps*mu bounds kt.
    index_bound = max(e.real * m.real for e, m in lossless)
    modes = []
    for m in range(int(math.sqrt(upper * index_bound) * a / math.pi) + 2):
        for n in range(int(math.sqrt(upper * index_bound) * b / math.pi) + 2):
            transverse = (m * math.pi / a) ** 2 + (n * math.pi / b) ** 2
            if transverse > upper * index_bound * (1 + 1e-12):
                continue
            families = []
            if m + n > 0:
                families.append("TE_z")
            if m > 0 and n > 0:
                families.append("TM_z")
            for family in families:
                def real_function(x, family=family, transverse=transverse):
                    return _dispersion(family, x, transverse, d, c - d, lossless).real
                for order, root in enumerate(_real_roots(real_function, upper, scan_samples)):
                    value = complex(root)
                    for step in range(1, continuation_steps + 1):
                        t = step / continuation_steps
                        materials = tuple((complex(e0.real, t * e.imag),
                                           complex(m0.real, t * mu.imag))
                                          for (e0, m0), (e, mu) in zip(lossless, lossy))
                        value = _secant(
                            lambda x: _dispersion(family, x, transverse, d, c - d, materials),
                            value, root)
                    frequency = complex_frequency_from_eigenvalue(value)
                    modes.append(SlabCavityMode(family, (m, n), order, value, frequency,
                                                quality_factor(frequency), root))
    return sorted(modes, key=lambda mode: (mode.eigenvalue_m2.real, mode.family, mode.indices))
