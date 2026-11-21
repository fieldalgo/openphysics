# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Independent complex resonances of PEC boxes with dielectric/magnetic loading.

Public API (galerkin step, L3 commit 12). The public functions take SI keyword-only
registry names: ``box_size`` (a, b, c) and ``thickness`` in m, ``frequency_limit`` in Hz,
``relative_permittivity`` and ``relative_permeability`` (for the slab-loaded box one value
per region, the slab first), ``wavenumber_squared`` (k0**2, 1/m**2), ``resonant_frequency``
(Hz) and ``loss_tangent``. Their complex values follow exp(-i omega t), as the rest of
refsol: a passive material has ``Im >= 0`` (``eps' + i eps''``, likewise ``mu_r``), a decaying
resonance has ``Im(resonant_frequency) < 0`` and ``Im(wavenumber_squared) < 0``, and the
quality factor is ``Q = Re f / (-2 Im f)`` (the registry's sign sentence). The arithmetic
below is written in exp(+j omega t) and is unchanged: each public function converts its
complex inputs with ``refsol._conventions.to_kernel`` and returns ``to_public`` of its complex
results, the conjugates. Real results (a quality factor, the lossless roots) are the same in
both conventions.

Convention of the formulas below. Fields vary as ``exp(+j*omega*t)``. A passive material
has ``eps_r = eps' - j*eps''`` with ``eps'' >= 0`` (likewise ``mu_r``), and a decaying
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

import numpy as np

from ._checks import pair, refuse_text
from ._conventions import to_kernel, to_public
from .cavity import C0

__all__ = ["quality_factor", "complex_frequency_from_eigenvalue", "uniformly_filled_eigenvalue",
           "dielectric_loss_quality_factor", "SlabCavityMode", "slab_loaded_cavity_modes"]


def _positive(value, name):
    if (isinstance(value, bool) or not isinstance(value, Real)
            or not math.isfinite(value) or value <= 0):
        raise ValueError(f"{name} must be a finite positive real number")
    return float(value)


def _material(value, name):
    """A passive complex constant in exp(-i omega t) (Re > 0, Im >= 0), returned in exp(+j omega t)."""
    if isinstance(value, bool) or not isinstance(value, Complex):
        raise ValueError(f"{name} must be a finite complex number")
    value = complex(value)
    if not (cmath.isfinite(value) and value.real > 0 and value.imag >= 0):
        raise ValueError(f"{name} must be finite with positive real part and non-negative imaginary part "
                         "(passive under exp(-i omega t): a loss is Im >= 0)")
    return to_kernel(value)


def _complex_number(value, name):
    """A finite complex scalar (a real one included) as a Python complex."""
    if isinstance(value, bool) or not isinstance(value, Complex) or not cmath.isfinite(complex(value)):
        raise ValueError(f"{name} must be a finite complex number")
    return complex(value)


def _quality_factor(complex_frequency):
    """``Re(f)/(2 Im(f))`` of an exp(+j omega t) frequency; infinity for a real one."""
    f = complex(complex_frequency)
    return math.inf if f.imag == 0 else f.real / (2 * f.imag)


def _complex_frequency_from_eigenvalue(eigenvalue):
    """Principal ``c0*sqrt(k0**2)/(2*pi)`` in exp(+j omega t); passive spectra have ``Re > 0``."""
    return C0 * cmath.sqrt(complex(eigenvalue)) / (2 * math.pi)


def quality_factor(*, resonant_frequency) -> float:
    """``Q = Re f / (-2 Im f)`` of a complex ``resonant_frequency`` (Hz, exp(-i omega t)).

    Infinity for a real (lossless) frequency; a decaying resonance (Im f < 0) has Q > 0.
    """
    refuse_text(resonant_frequency=resonant_frequency)
    return _quality_factor(to_kernel(_complex_number(resonant_frequency, "resonant_frequency")))


def complex_frequency_from_eigenvalue(*, wavenumber_squared) -> complex:
    """The principal ``c0 sqrt(k0**2) / (2 pi)`` (Hz) of ``wavenumber_squared`` (1/m**2), both exp(-i omega t).

    A passive spectrum has ``Re > 0``; a decaying resonance has ``Im < 0``.
    """
    refuse_text(wavenumber_squared=wavenumber_squared)
    eigenvalue = to_kernel(_complex_number(wavenumber_squared, "wavenumber_squared"))
    return to_public(_complex_frequency_from_eigenvalue(eigenvalue))


def uniformly_filled_eigenvalue(*, wavenumber_squared, relative_permittivity,
                                relative_permeability=1.0) -> complex:
    """Exact ``k0**2 = k_vac**2 / (eps_r * mu_r)`` (1/m**2, exp(-i omega t)) for a homogeneous PEC cavity.

    ``wavenumber_squared`` is the vacuum mode's real ``k_vac**2`` (1/m**2). Every vacuum mode
    keeps its field and only its eigenvalue is rescaled. For ``eps_r = eps'(1 + i*tan_delta)``
    and ``mu_r = 1`` the quality factor is ``(1 + sqrt(1 + tan_delta**2)) / (2 * tan_delta)``,
    close to ``1/tan_delta``.
    """
    refuse_text(wavenumber_squared=wavenumber_squared, relative_permittivity=relative_permittivity,
                relative_permeability=relative_permeability)
    vacuum = _positive(wavenumber_squared, "wavenumber_squared")
    eps = _material(relative_permittivity, "relative_permittivity")
    mu = _material(relative_permeability, "relative_permeability")
    return to_public(vacuum / (eps * mu))


def dielectric_loss_quality_factor(*, loss_tangent) -> float:
    """Exact Q of a uniformly filled cavity with ``eps' (1 + i*tan_delta)`` (exp(-i omega t)), mu_r real."""
    refuse_text(loss_tangent=loss_tangent)
    t = _positive(loss_tangent, "loss_tangent")
    return (1 + math.sqrt(1 + t * t)) / (2 * t)


@dataclass(frozen=True)
class SlabCavityMode:
    """One TE-to-z or TM-to-z resonance of a slab-loaded box (exp(-i omega t)).

    ``indices`` are the transverse (m, n) standing-wave indices along x and y;
    ``order`` counts lossless roots of that family and (m, n) from zero.
    ``wavenumber_squared`` is the complex ``k0**2`` (1/m**2) and ``resonant_frequency``
    the complex frequency (Hz), each with ``Im <= 0`` on passive materials;
    ``quality_factor`` is ``Re f / (-2 Im f)``. ``_lossless_wavenumber_squared`` is the
    real lossless root ``k0**2`` the mode is continued from (internal: no registry name).
    """

    family: str
    indices: tuple[int, int]
    order: int
    wavenumber_squared: complex
    resonant_frequency: complex
    quality_factor: float
    _lossless_wavenumber_squared: float


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


def _count(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def slab_loaded_cavity_modes(*, box_size, thickness, frequency_limit, relative_permittivity,
                             relative_permeability=(1.0, 1.0), scan_samples=4000, subdivision_count=16):
    """Resonances of an ``a x b x c`` PEC box (``box_size``, m) with a slab filling ``0 <= z <= d``.

    ``thickness`` is the slab's d in m and ``frequency_limit`` the ceiling in Hz.
    ``relative_permittivity`` and ``relative_permeability`` are the pairs (slab, background),
    each value passive under exp(-i omega t) (``Im >= 0``); the background fills ``d < z < c``.
    The slab covers the full ``a x b`` cross-section. Transverse fields are the
    rectangular standing waves ``kx = m*pi/a``, ``ky = n*pi/b``. TE-to-z modes
    (``Ez = 0``) need ``m + n > 0``; TM-to-z modes (``Hz = 0``) need ``m, n >= 1``.

    Lossless roots are found as sign changes of the real characteristic function
    on a uniform scan of ``k0**2`` below the ceiling (``scan_samples`` intervals
    per family and (m, n)) and refined by bisection. A root pair closer than one
    scan interval can be missed; the scan is a reference enumeration, not a
    certificate. Each lossless root is then continued to the complex materials
    in ``subdivision_count`` linear homotopy steps of the imaginary parts, with
    a complex secant iteration at each step. The ceiling applies to the lossless
    (real-part) frequency. Modes are sorted by the real part of ``k0**2``; each
    passive lossy mode has ``Im(resonant_frequency) < 0``.
    """
    refuse_text(box_size=box_size, thickness=thickness, frequency_limit=frequency_limit,
                relative_permittivity=relative_permittivity, relative_permeability=relative_permeability,
                scan_samples=scan_samples, subdivision_count=subdivision_count)
    try:
        lengths = tuple(box_size)
    except TypeError as exc:
        raise ValueError("box_size must contain three positive lengths in m") from exc
    if len(lengths) != 3:
        raise ValueError("box_size must contain three positive lengths in m")
    a, b, c = (_positive(v, "box_size") for v in lengths)
    d = _positive(thickness, "thickness")
    if d >= c:
        raise ValueError("thickness must be smaller than the z length box_size[2]")
    ceiling = _positive(frequency_limit, "frequency_limit")
    permittivity = pair(relative_permittivity, "relative_permittivity (slab, background)")
    permeability = pair(relative_permeability, "relative_permeability (slab, background)")
    lossy = tuple((_material(permittivity[i], f"relative_permittivity[{i}]"),
                   _material(permeability[i], f"relative_permeability[{i}]")) for i in (0, 1))
    roots = _slab_loaded_cavity_modes(a, b, c, d, ceiling, lossy, _count(scan_samples, "scan_samples"),
                                      _count(subdivision_count, "subdivision_count"))
    return [SlabCavityMode(family, indices, order, to_public(value), to_public(frequency), q, root)
            for family, indices, order, value, frequency, q, root in roots]


def _slab_loaded_cavity_modes(a, b, c, d, ceiling, lossy, scan_samples, continuation_steps):
    """The resonances as (family, indices, order, k0**2, f, Q, lossless k0**2) in exp(+j omega t), sorted."""
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
                    frequency = _complex_frequency_from_eigenvalue(value)
                    modes.append((family, (m, n), order, value, frequency, _quality_factor(frequency), root))
    return sorted(modes, key=lambda mode: (mode[3].real, mode[0], mode[1]))
