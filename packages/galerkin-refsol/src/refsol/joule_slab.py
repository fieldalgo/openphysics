# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Steady one-dimensional Joule heating with linearly temperature-dependent conductivity.

A slab ``0 <= x <= L`` carries a DC current between fixed potentials and fixed
temperatures at its two faces; the lateral faces are insulated, so every field
depends on ``x`` only. The coupled equations are

    (sigma(T) V')' = 0,     k T'' + sigma(T) V'^2 = 0,
    V(0) = V_a, V(L) = V_b, T(0) = T_a, T(L) = T_b,

with constant thermal conductivity ``k`` and the linear isotropic model

    sigma(T) = sigma0 (1 + alpha (T - T0)),

the form a ``galerkin.temperature_joule_heating.ConductivityModel`` callback
``lambda t: sigma0 * (1 + alpha * (t - T0))`` evaluates; that solver's valid
temperature range must contain ``temperature_range`` of the returned solution.
``alpha > 0`` is a conductivity rising with temperature (semiconductor-like),
``alpha < 0`` a metal-like one; ``alpha = 0`` is the constant-conductivity
closed form. SI units: m, K, V, S/m, W/(m K), A/m^2, W/m^2 (any consistent set
works).

Inputs are keyword-only SI registry names: ``length``, the face pairs
``prescribed_electric_potential`` ``(V_a, V_b)`` and ``prescribed_temperature``
``(T_a, T_b)``, ``reference_conductivity`` (sigma0), ``conductivity_temperature_coefficient``
(alpha), ``reference_temperature`` (T0), ``thermal_conductivity`` (k) and, for a
prescribed current, ``current_density`` (J). The returned ``JouleSlab`` carries the
same names and evaluates its fields at the x coordinates ``points``. A str for a
quantity raises TypeError.

Derivation. The current density ``J = -sigma V'`` is constant. With
``u = sigma / sigma0 = 1 + alpha (T - T0)`` the heat equation becomes

    u'' = -c / u,        c = alpha J^2 / (k sigma0),

whose first integral ``u'^2 = 2 c ln(u_m / u)`` singles out the extremum ``u_m``
(a maximum for ``c > 0``, a minimum for ``c < 0``). With the scaled slope
``s = u' / sqrt(2|c|)``,

    u = u_m exp(-s^2),  x = x_m - u_m sqrt(pi/(2c)) erf(s)      (c > 0),
    u = u_m exp(+s^2),  x = x_m + u_m sqrt(pi/(2|c|)) erfi(s)   (c < 0),

because ``dx/ds = -(u/c) sqrt(2|c|)``; ``s`` is monotone in ``x``. The potential
follows from ``V' = -J / (sigma0 u) = k u'' / (alpha J)``:

    V(x) - V_a = k (u'(x) - u'(0)) / (alpha J),

so the drop ``V_a - V_b = k (u'(0) - u'(L)) / (alpha J)`` equals
``sqrt(2k/(|alpha| sigma0)) |s_a - s_b|`` independently of ``J``: the end slopes
are fixed by the voltage alone. Together with ``s_a^2 - s_b^2 = ln(u_b/u_a)``
(``c > 0``; the signs swap for ``c < 0``) both end slopes are closed-form, and
the length condition ``L = x(s_b) - x(s_a)`` then gives ``c``, hence ``J``. The
voltage-driven problem is therefore explicit; the current-driven one needs a
scalar root in the voltage (``current_driven``). For ``alpha > 0`` the
voltage-driven solution exists and is unique for every drop (``u'' = f(u)``
with ``f`` increasing); for ``alpha < 0`` it exists for every drop as well, while
a prescribed current admits two steady states below a fold current and none
above it (thermal runaway of a positive-resistivity-coefficient conductor).

Quantities are evaluated with the scaled functions ``erfcx`` and ``dawsn`` so
that a nearly linear solution (small drop with unequal face temperatures, where
``s_a`` and ``s_b`` are large) does not overflow. The ``alpha -> 0`` limit is
``T = T_a + (T_b - T_a) x/L + sigma0 (V_a - V_b)^2 x (L - x) / (2 k L^2)``.

Sources. The constant-conductivity closed form and the first integral of
``u'' = f(u)`` are textbook material (Carslaw & Jaeger, *Conduction of Heat in
Solids*, 2nd ed., Oxford 1959, ch. 1 and 4); the thermistor fold (two branches
below a maximal current, none above) follows Fowler, Frigaard & Howison,
"Temperature surges in current-limiting circuit devices," SIAM J. Appl. Math.
52, 998 (1992). The erf/erfi quadrature above is elementary.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.optimize import brentq, minimize_scalar
from scipy.special import dawsn, erf, erfcx

from ._checks import refuse_text

__all__ = ["JouleSlab", "constant_conductivity", "voltage_driven", "drop_scale", "fold_current",
           "current_driven"]

_ROOT_PI_HALF = math.sqrt(math.pi) / 2


def _scalar(value, name, positive=False):
    a = np.asarray(value)
    if a.shape != () or a.dtype.kind not in "iuf" or not np.isfinite(a):
        raise ValueError(f"{name} must be a finite real scalar")
    v = float(a)
    if positive and not v > 0:
        raise ValueError(f"{name} must be positive")
    return v


def _pair(values, name):
    try:
        a, b = values
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a pair (face 0, face L)") from None
    return _scalar(a, name), _scalar(b, name)



@dataclass(frozen=True)
class _Scaled:
    """Oriented closed-form solution: face ``a`` has the smaller ``u`` (``ln(u_b/u_a) >= 0``).

    The running variable is ``delta = |s - s_a|`` in ``[0, drop]``, ``drop = |s_a - s_b|``,
    so that ``s_a^2 - s^2 = delta (2 s_a - sign delta)`` is formed without cancellation
    when the slopes are large (small drop, unequal face temperatures).
    """

    sign: int                 # sign of c = sign of alpha
    s_a: float
    s_b: float
    drop: float               # |s_a - s_b|
    u_a: float
    root_2c: float            # sqrt(2|c|)
    reflected: bool           # the oriented face a is the physical face x = L

    def s(self, delta):
        return self.s_a - self.sign * np.asarray(delta, dtype=float)

    def u(self, delta):
        delta = np.asarray(delta, dtype=float)
        return self.u_a * np.exp(delta * (2 * self.s_a - self.sign * delta))

    def _difference(self, delta):
        """Unnormalized ``x(s)`` (zero at ``delta = 0``, increasing)."""
        delta = np.asarray(delta, dtype=float)
        s = self.s(delta)
        if self.sign > 0:
            # e^{s_a^2}(erf s_a - erf s) = erfcx(s) e^{s_a^2 - s^2} - erfcx(s_a) for s >= 0
            out = np.empty_like(s)
            pos = s >= 0
            out[pos] = erfcx(s[pos]) * np.exp(delta[pos] * (2 * self.s_a - delta[pos])) - erfcx(self.s_a)
            if np.any(~pos):      # then s_a is moderate (needs ln(u_b/u_a) < drop^2)
                out[~pos] = math.exp(self.s_a**2) * (erf(self.s_a) - erf(s[~pos]))
            return out
        # (sqrt(pi)/2) e^{-s_b^2}(erfi s - erfi s_a), erfi(s) = (2/sqrt(pi)) e^{s^2} dawsn(s),
        # with s^2 - s_b^2 = -(drop - delta)(s + s_b) and s_a^2 - s_b^2 = -drop (s_a + s_b)
        return (np.exp(-(self.drop - delta) * (s + self.s_b)) * dawsn(s)
                - math.exp(-self.drop * (self.s_a + self.s_b)) * dawsn(self.s_a))

    def total(self):
        return float(self._difference(np.array([self.drop]))[0])

    def position(self, delta):
        """``x / L`` at ``delta``: zero at ``s_a``, one at ``s_b``, monotone."""
        return self._difference(delta) / self.total()

    def delta(self, fraction):
        """``delta`` at ``x/L = fraction`` by bracketed root finding on ``position``."""
        fraction = np.asarray(fraction, dtype=float)
        out = np.empty_like(fraction)
        for index, value in np.ndenumerate(fraction):
            if value <= 0.0:
                out[index] = 0.0
            elif value >= 1.0:
                out[index] = self.drop
            else:
                out[index] = brentq(lambda d: float(self.position(np.array([d]))[0]) - value, 0.0,
                                    self.drop, xtol=1e-16 * self.drop, rtol=4 * np.finfo(float).eps,
                                    maxiter=200)
        return out

    def extremum_fraction(self):
        """``x_m / L`` of the stationary point ``s = 0``, or None when outside the slab."""
        lo, hi = sorted((self.s_a, self.s_b))
        if not lo < 0 < hi:
            return None
        value = float(self.position(np.array([abs(self.s_a)]))[0])
        return 1.0 - value if self.reflected else value


@dataclass(frozen=True)
class JouleSlab:
    """Exact fields of one slab; see the module docstring.

    ``prescribed_electric_potential`` and ``prescribed_temperature`` are the face
    pairs (x = 0, x = L); ``reference_conductivity``,
    ``conductivity_temperature_coefficient`` and ``reference_temperature`` the
    conductivity law. ``current_density`` is ``J = -sigma V'`` (positive toward
    ``+x``). ``_joule_power`` is the dissipated power per unit face area,
    ``J (V_a - V_b) = k (T'(0) - T'(L))`` in W/m^2: private (rule R(2) of the
    galerkin step: no registry name, and no shipped code reads it).
    ``temperature_range`` bounds ``T`` on ``[0, L]`` (faces and interior stationary
    point): the interval a bounded conductivity model must cover.
    """

    length: float
    prescribed_electric_potential: tuple[float, float]
    prescribed_temperature: tuple[float, float]
    reference_conductivity: float
    conductivity_temperature_coefficient: float
    reference_temperature: float
    thermal_conductivity: float
    current_density: float
    _joule_power: float
    temperature_range: tuple[float, float]
    _scaled: _Scaled | None

    def _points(self, x):
        a = np.asarray(x, dtype=float)
        tolerance = 1e-12 * self.length
        if not np.all(np.isfinite(a)) or np.any(a < -tolerance) or np.any(a > self.length + tolerance):
            raise ValueError("points must lie in [0, length]")
        return np.clip(a, 0.0, self.length)

    def _deltas(self, x):
        fraction = x / self.length
        if self._scaled.reflected:
            fraction = 1.0 - fraction
        return self._scaled.delta(fraction)

    def temperature(self, points):
        """``T(x)`` in K at the x coordinates ``points``."""
        x = self._points(points)
        if self._scaled is None:
            t_a, t_b = self.prescribed_temperature
            return t_a + (t_b - t_a) * x / self.length + self._heating() * x * (self.length - x)
        return (self.reference_temperature
                + (self._scaled.u(self._deltas(x)) - 1.0) / self.conductivity_temperature_coefficient)

    def temperature_gradient(self, points):
        """``dT/dx`` in K/m at the x coordinates ``points``."""
        x = self._points(points)
        if self._scaled is None:
            t_a, t_b = self.prescribed_temperature
            return (t_b - t_a) / self.length + self._heating() * (self.length - 2 * x)
        gradient = self._scaled.root_2c * self._scaled.s(self._deltas(x)) / self.conductivity_temperature_coefficient
        return -gradient if self._scaled.reflected else gradient

    def heat_flux(self, points):
        """``q = -k dT/dx`` in W/m^2, positive toward ``+x``, at the x coordinates ``points``."""
        return -self.thermal_conductivity * self.temperature_gradient(points)

    def electrical_conductivity(self, points):
        """``sigma(T(x))`` in S/m at the x coordinates ``points``."""
        return self.reference_conductivity * (1.0 + self.conductivity_temperature_coefficient
                                              * (self.temperature(points) - self.reference_temperature))

    def electric_potential(self, points):
        """``V(x)`` in V: ``V_a + (V_b - V_a) R(x)/R(L)`` with ``R(x) = int_0^x dx'/sigma``, at the x
        coordinates ``points``."""
        x = self._points(points)
        v_a, v_b = self.prescribed_electric_potential
        if self._scaled is None:
            return v_a + (v_b - v_a) * x / self.length
        # R(x) = (u'(0) - u'(x)) / c in the oriented frame: the fraction |s_a - s| / |s_a - s_b|
        fraction = self._deltas(x) / self._scaled.drop
        if self._scaled.reflected:
            fraction = 1.0 - fraction
        return v_a + (v_b - v_a) * fraction

    def electric_field(self, points):
        """``E = -dV/dx = J / sigma`` in V/m at the x coordinates ``points``."""
        return self.current_density / self.electrical_conductivity(points)

    def joule_power_density(self, points):
        """``Q = sigma E^2 = J^2 / sigma`` in W/m^3 at the x coordinates ``points``."""
        return self.current_density**2 / self.electrical_conductivity(points)

    def _heating(self):
        """Constant-conductivity parabola coefficient ``sigma0 (V_a - V_b)^2 / (2 k L^2)``."""
        v_a, v_b = self.prescribed_electric_potential
        return self.reference_conductivity * (v_a - v_b) ** 2 / (2 * self.thermal_conductivity * self.length**2)


def _finish(slab, extremum_fraction):
    """Attach the temperature extrema on [0, L]: faces and the interior stationary point."""
    candidates = [0.0, slab.length]
    if extremum_fraction is not None and 0.0 < extremum_fraction < 1.0:
        candidates.append(extremum_fraction * slab.length)
    values = slab.temperature(np.array(candidates))
    return JouleSlab(slab.length, slab.prescribed_electric_potential, slab.prescribed_temperature,
                     slab.reference_conductivity, slab.conductivity_temperature_coefficient,
                     slab.reference_temperature, slab.thermal_conductivity, slab.current_density,
                     slab._joule_power, (float(values.min()), float(values.max())), slab._scaled)


def constant_conductivity(*, length, prescribed_electric_potential, prescribed_temperature, electrical_conductivity,
                          thermal_conductivity, reference_temperature=None) -> JouleSlab:
    """Closed form for a constant ``electrical_conductivity`` sigma: linear ``V`` and a parabolic Joule term in ``T``.

    ``T = T_a + (T_b - T_a) x/L + sigma (V_a - V_b)^2 x (L - x) / (2 k L^2)``. The
    returned slab records sigma as its ``reference_conductivity`` with a zero
    coefficient; ``reference_temperature`` (None: ``T_a``) is recorded only.
    """
    refuse_text(length=length, prescribed_electric_potential=prescribed_electric_potential,
                prescribed_temperature=prescribed_temperature, electrical_conductivity=electrical_conductivity,
                thermal_conductivity=thermal_conductivity, reference_temperature=reference_temperature)
    L = _scalar(length, "length", positive=True)
    v_a, v_b = _pair(prescribed_electric_potential, "prescribed_electric_potential")
    t_a, t_b = _pair(prescribed_temperature, "prescribed_temperature")
    sigma = _scalar(electrical_conductivity, "electrical_conductivity", positive=True)
    k = _scalar(thermal_conductivity, "thermal_conductivity", positive=True)
    t0 = t_a if reference_temperature is None else _scalar(reference_temperature, "reference_temperature")
    current = sigma * (v_a - v_b) / L
    slab = JouleSlab(L, (v_a, v_b), (t_a, t_b), sigma, 0.0, t0, k, current, current * (v_a - v_b),
                     (0.0, 0.0), None)
    heating = slab._heating()
    extremum = None
    if heating > 0:
        extremum = 0.5 + (t_b - t_a) / (2 * L * L * heating)
    return _finish(slab, extremum)


def voltage_driven(*, length, prescribed_electric_potential, prescribed_temperature, reference_conductivity,
                   conductivity_temperature_coefficient, reference_temperature, thermal_conductivity) -> JouleSlab:
    """Exact solution for fixed face potentials ``(V_a, V_b)`` and temperatures ``(T_a, T_b)``.

    ``sigma(T) = sigma0 (1 + alpha (T - T0))`` with sigma0 the
    ``reference_conductivity``, alpha the ``conductivity_temperature_coefficient``
    and T0 the ``reference_temperature`` must be positive at both faces. Closed form
    in ``erf``/``erfi`` (module docstring); raises ``ValueError`` when the drop is so
    large that the scaled slopes overflow.
    """
    refuse_text(length=length, prescribed_electric_potential=prescribed_electric_potential,
                prescribed_temperature=prescribed_temperature, reference_conductivity=reference_conductivity,
                conductivity_temperature_coefficient=conductivity_temperature_coefficient,
                reference_temperature=reference_temperature, thermal_conductivity=thermal_conductivity)
    L = _scalar(length, "length", positive=True)
    v_a, v_b = _pair(prescribed_electric_potential, "prescribed_electric_potential")
    t_a, t_b = _pair(prescribed_temperature, "prescribed_temperature")
    sigma0 = _scalar(reference_conductivity, "reference_conductivity", positive=True)
    alpha = _scalar(conductivity_temperature_coefficient, "conductivity_temperature_coefficient")
    t0 = _scalar(reference_temperature, "reference_temperature")
    k = _scalar(thermal_conductivity, "thermal_conductivity", positive=True)
    u_a, u_b = 1 + alpha * (t_a - t0), 1 + alpha * (t_b - t0)
    if u_a <= 0 or u_b <= 0:
        raise ValueError("sigma(T) must be positive at both faces")
    if alpha == 0.0:
        return constant_conductivity(length=L, prescribed_electric_potential=(v_a, v_b),
                                     prescribed_temperature=(t_a, t_b), electrical_conductivity=sigma0,
                                     thermal_conductivity=k, reference_temperature=t0)
    if v_a == v_b:
        # no current, no heating: T is linear and sigma(T) varies along it
        return _finish(JouleSlab(L, (v_a, v_b), (t_a, t_b), sigma0, alpha, t0, k, 0.0, 0.0, (0.0, 0.0), None), None)
    reflected = u_b < u_a
    if reflected:
        u_a, u_b = u_b, u_a
    r = math.log(u_b / u_a)                                   # >= 0 after orientation
    drop = math.sqrt(abs(alpha) * sigma0 / (2 * k)) * abs(v_a - v_b)   # |s_a - s_b|
    if alpha > 0:
        s_a, s_b = (drop + r / drop) / 2, (r / drop - drop) / 2
    else:
        s_b, s_a = (drop + r / drop) / 2, (r / drop - drop) / 2
    scaled = _Scaled(1 if alpha > 0 else -1, s_a, s_b, drop, u_a, 0.0, reflected)
    total = scaled.total()
    if not (np.isfinite(total) and total > 0):
        raise ValueError("voltage drop too large for the scaled closed form")
    if alpha > 0:
        lam = L / (u_a * total)                              # sqrt(pi/(2c)); u_m lam (erf s_a - erf s_b) = L
    else:
        # u_m lam (erfi s_b - erfi s_a) = L with u_m = u_a e^{-s_a^2} and
        # erfi s_b - erfi s_a = (2/sqrt(pi)) e^{s_b^2} total
        lam = L * _ROOT_PI_HALF / (u_a * math.exp(drop * (s_a + s_b)) * total)
    c = math.pi / (2 * lam * lam)                            # |c|
    current = math.sqrt(c * k * sigma0 / abs(alpha))
    scaled = _Scaled(scaled.sign, s_a, s_b, drop, u_a, math.sqrt(2 * c), reflected)
    signed = current if v_a > v_b else -current
    slab = JouleSlab(L, (v_a, v_b), (t_a, t_b), sigma0, alpha, t0, k, signed, signed * (v_a - v_b),
                     (0.0, 0.0), scaled)
    return _finish(slab, scaled.extremum_fraction())


def drop_scale(*, reference_conductivity, conductivity_temperature_coefficient, thermal_conductivity) -> float:
    """Voltage drop ``sqrt(2k/(|alpha| sigma0))`` at which ``|s_a - s_b| = 1``."""
    refuse_text(reference_conductivity=reference_conductivity,
                conductivity_temperature_coefficient=conductivity_temperature_coefficient,
                thermal_conductivity=thermal_conductivity)
    return math.sqrt(2 * _scalar(thermal_conductivity, "thermal_conductivity", True)
                     / (abs(_scalar(conductivity_temperature_coefficient, "conductivity_temperature_coefficient"))
                        * _scalar(reference_conductivity, "reference_conductivity", True)))


def fold_current(*, length, prescribed_temperature, reference_conductivity, conductivity_temperature_coefficient,
                 reference_temperature, thermal_conductivity):
    """``conductivity_temperature_coefficient < 0`` only: ``(J_fold, drop_fold)``, the largest current
    density a steady voltage-driven state carries and the drop at which the current-voltage curve folds."""
    refuse_text(length=length, prescribed_temperature=prescribed_temperature,
                reference_conductivity=reference_conductivity,
                conductivity_temperature_coefficient=conductivity_temperature_coefficient,
                reference_temperature=reference_temperature, thermal_conductivity=thermal_conductivity)
    alpha = _scalar(conductivity_temperature_coefficient, "conductivity_temperature_coefficient")
    if not alpha < 0:
        raise ValueError("the current folds only for conductivity_temperature_coefficient < 0")
    scale = drop_scale(reference_conductivity=reference_conductivity, conductivity_temperature_coefficient=alpha,
                       thermal_conductivity=thermal_conductivity)
    law = dict(prescribed_temperature=prescribed_temperature, reference_conductivity=reference_conductivity,
               conductivity_temperature_coefficient=alpha, reference_temperature=reference_temperature,
               thermal_conductivity=thermal_conductivity)

    def current(drop):
        return abs(voltage_driven(length=length, prescribed_electric_potential=(drop, 0.0), **law).current_density)

    answer = minimize_scalar(lambda d: -current(d), bounds=(1e-6 * scale, 50 * scale),
                             method="bounded", options=dict(xatol=1e-12 * scale))
    return float(current(answer.x)), float(answer.x)


def current_driven(*, length, current_density, prescribed_temperature, reference_conductivity,
                   conductivity_temperature_coefficient, reference_temperature, thermal_conductivity,
                   prescribed_electric_potential, branch="lower") -> JouleSlab:
    """Slab carrying ``current_density`` J (A/m^2, positive toward ``+x``) between fixed temperatures.

    Finds the voltage drop whose ``voltage_driven`` solution carries ``J`` and
    returns that solution with ``V(0) = prescribed_electric_potential`` (V, the
    potential of the face x = 0; the other face's follows). For
    ``conductivity_temperature_coefficient < 0`` the current-voltage curve folds at
    ``fold_current``: ``branch="lower"`` returns the state with the smaller drop
    (and smaller temperature rise), ``"upper"`` the other one; ``|J|`` above the
    fold raises ``ValueError``.
    """
    refuse_text(length=length, current_density=current_density, prescribed_temperature=prescribed_temperature,
                reference_conductivity=reference_conductivity,
                conductivity_temperature_coefficient=conductivity_temperature_coefficient,
                reference_temperature=reference_temperature, thermal_conductivity=thermal_conductivity,
                prescribed_electric_potential=prescribed_electric_potential)
    J = _scalar(current_density, "current_density")
    L = _scalar(length, "length", positive=True)
    alpha = _scalar(conductivity_temperature_coefficient, "conductivity_temperature_coefficient")
    v_a = _scalar(prescribed_electric_potential, "prescribed_electric_potential")
    if branch not in ("lower", "upper"):
        raise ValueError("branch must be 'lower' or 'upper'")
    law = dict(prescribed_temperature=prescribed_temperature, reference_conductivity=reference_conductivity,
               conductivity_temperature_coefficient=alpha, reference_temperature=reference_temperature,
               thermal_conductivity=thermal_conductivity)
    if J == 0.0:
        return voltage_driven(length=L, prescribed_electric_potential=(v_a, v_a), **law)

    def magnitude(drop):
        return abs(voltage_driven(length=L, prescribed_electric_potential=(drop, 0.0), **law).current_density)

    if alpha == 0.0:
        drop = abs(J) * L / _scalar(reference_conductivity, "reference_conductivity", True)
    elif alpha > 0:
        scale = drop_scale(reference_conductivity=reference_conductivity, conductivity_temperature_coefficient=alpha,
                           thermal_conductivity=thermal_conductivity)
        lo, hi = 1e-9 * scale, scale
        while magnitude(hi) < abs(J):
            lo, hi = hi, 2 * hi
            if hi > 1e6 * scale:
                raise ValueError("no voltage drop within range carries this current")
        drop = brentq(lambda d: magnitude(d) - abs(J), lo, hi, xtol=1e-15 * scale,
                      rtol=4 * np.finfo(float).eps, maxiter=200)
    else:
        j_fold, d_fold = fold_current(length=L, **law)
        if abs(J) > j_fold:
            raise ValueError(f"no steady state: |J| = {abs(J):.6g} exceeds the fold current {j_fold:.6g}")
        if branch == "lower":
            lo, hi = 1e-9 * d_fold, d_fold
        else:
            lo, hi = d_fold, 2 * d_fold
            while magnitude(hi) > abs(J):
                lo, hi = hi, 2 * hi
                if hi > 1e6 * d_fold:
                    raise ValueError("no upper-branch voltage drop within range carries this current")
        drop = brentq(lambda d: magnitude(d) - abs(J), lo, hi, xtol=1e-15 * d_fold,
                      rtol=4 * np.finfo(float).eps, maxiter=200)
    v_b = v_a - drop if J > 0 else v_a + drop
    return voltage_driven(length=L, prescribed_electric_potential=(v_a, v_b), **law)
