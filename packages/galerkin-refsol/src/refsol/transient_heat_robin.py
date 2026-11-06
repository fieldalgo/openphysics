# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Transient slab references with a convective or a prescribed-flux face.

Both problems are one-dimensional heat conduction in the slab 0 < x < L with
constant conductivity k [W/(m K)] and volumetric heat capacity c [J/(m^3 K)],
diffusivity alpha = k/c, uniform initial temperature T0 and an insulated face
at x = 0. They are the classical separation-of-variables series for the slab
in H. S. Carslaw and J. C. Jaeger, *Conduction of Heat in Solids*, 2nd ed.,
Clarendon Press, Oxford (1959), chapter III (linear flow of heat in the slab):
the "radiation" (Newton cooling) boundary condition and the constant surface
flux. The series are derived here independently and only the mathematical
results are used; no text is reproduced.

Convective face: -k dT/dx = h (T - T_a) at x = L, h > 0. With theta = T - T_a,
beta_n the positive roots of beta tan(beta) = Bi = h L / k (one in each
interval (n pi, n pi + pi/2)), xi = x / L and Fo = alpha t / L^2,

    theta(x, t) = theta_0 sum_n  2 sin(beta_n) / (beta_n + sin(beta_n) cos(beta_n))
                                 cos(beta_n xi) exp(-beta_n^2 Fo).

Prescribed face: outward flux density g [W/m^2] at x = L (q.n = -k dT/dx = g,
positive g removes heat), insulated at x = 0:

    T(x, t) = T0 - (g L / k) [ Fo + (3 xi^2 - 1) / 6
                               - (2 / pi^2) sum_{n>=1} (-1)^n / n^2 exp(-n^2 pi^2 Fo) cos(n pi xi) ].

Two time-dependent boundary data follow. Periodic ambient temperature
T_a(t) = T_m + A sin(omega t) at the convective face: the periodic steady state
(the solution after the initial transient, which decays as
exp(-beta_1^2 alpha t / L^2), has died out) is

    T_ps(x, t) = T_m + Im[ Theta(x) exp(i omega t) ],
    Theta(x)   = A h cosh(q x) / (h cosh(q L) + k q sinh(q L)),
    q          = sqrt(i omega / alpha) = (1 + i) sqrt(omega / (2 alpha)),

    derived by writing T - T_m = Im[Theta(x) e^{i omega t}] in the heat
    equation (i omega Theta = alpha Theta''), the insulated face (Theta'(0) = 0,
    so Theta = C cosh(q x)) and the convective face (-k Theta'(L) = h (Theta(L)
    - A)). |Theta(x)| is the amplitude and arg Theta(x) the phase of the
    temperature at x relative to the ambient oscillation. The backward-Euler
    time-discrete problem with step dt and the ambient sampled at the end of
    each step, (T_{n+1} - T_n) / dt = alpha T_{n+1}'' with -k T_{n+1}'(L) =
    h (T_{n+1}(L) - T_a(t_{n+1})), has the same periodic steady state with

    q_d^2 = (1 - exp(-i omega dt)) / (alpha dt)

    in place of q^2 = i omega / alpha (ansatz T_n = T_m + Im[Theta_d(x) z^n],
    z = exp(i omega dt)); it isolates the spatial error of a backward-Euler
    discretization, as q_d -> q when dt -> 0.

Ramped outward flux g(t) = g0 t / tau at x = L, insulated at x = 0, uniform
initial T0: Duhamel's integral of the constant-flux step response above,
T - T0 = (g0 / tau) integral_0^t S(x, u) du with S the unit-step response,
gives with Fo = alpha t / L^2 and xi = x / L

    T(x, t) = T0 - (g0 L / k) (L^2 / (alpha tau)) [ Fo^2 / 2 + Fo (3 xi^2 - 1) / 6
              - (2 / pi^4) sum_{n>=1} (-1)^n / n^4 (1 - exp(-n^2 pi^2 Fo)) cos(n pi xi) ],

and with the closed form sum_{n>=1} (-1)^n cos(n pi xi) / n^4 = -pi^4 (15 xi^4
- 30 xi^2 + 7) / 720 (twice the integral of the n^-2 sum behind the step
response, with f'(0) = 0 and f(0) = -7 pi^4 / 720) the bracket is

    Fo^2 / 2 + Fo (3 xi^2 - 1) / 6 + (15 xi^4 - 30 xi^2 + 7) / 360
    + (2 / pi^4) sum_{n>=1} (-1)^n / n^4 exp(-n^2 pi^2 Fo) cos(n pi xi),

whose series decays exponentially and is the one summed.

Each series is summed until a stated tail bound falls below a relative
tolerance of the temperature scale (|T0 - T_a|, |g| L / k or the ramp's
|g0| L / k (L^2 / (alpha tau)) Fo^2 / 2); the truncation bound is returned with
the temperature. At t = 0 the exact initial value is returned (the series
converge slowly there). NumPy and SciPy's ``brentq`` only; no FEM, assembly or
solver import. SI units throughout.
"""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq


def _finite_scalar(value, name, positive=False, nonnegative=False):
    a = np.asarray(value)
    if a.shape != () or a.dtype.kind not in "iuf" or not np.isfinite(a):
        raise ValueError(f"{name} must be a finite real scalar")
    v = float(a)
    if positive and v <= 0:
        raise ValueError(f"{name} must be positive")
    if nonnegative and v < 0:
        raise ValueError(f"{name} must be nonnegative")
    return v


def _coordinates(x, length):
    a = np.asarray(x, dtype=float)
    if a.dtype.kind not in "f" or not np.all(np.isfinite(a)):
        raise ValueError("x must be finite real metres")
    if np.any(a < -1e-12*length) or np.any(a > length*(1+1e-12)):
        raise ValueError("x must lie in the slab 0 <= x <= L")
    return np.clip(a, 0., length)


def _terms(bound, tolerance, maximum):
    """Smallest N >= 1 with bound(N) <= tolerance; refuses to exceed ``maximum`` terms."""
    n = 1
    while bound(n) > tolerance:
        n += 1
        if n > maximum:
            raise ValueError("series truncation bound not met within the term limit; "
                             "use a larger time or tolerance")
    return n


@dataclass(frozen=True)
class SlabTemperature:
    """Temperature (same shape as x), the series length and its truncation bound [K]."""
    temperature_k: np.ndarray
    terms: int
    truncation_bound_k: float


@dataclass(frozen=True)
class ConvectiveSlab:
    """Slab 0<x<L, insulated at x=0, convective at x=L, uniform initial temperature."""
    length: float
    conductivity: float
    volumetric_heat_capacity: float
    convection: float
    ambient: float
    initial_temperature: float

    def __post_init__(self):
        _finite_scalar(self.length, "length", positive=True)
        _finite_scalar(self.conductivity, "conductivity", positive=True)
        _finite_scalar(self.volumetric_heat_capacity, "volumetric_heat_capacity", positive=True)
        _finite_scalar(self.convection, "convection", positive=True)
        _finite_scalar(self.ambient, "ambient")
        _finite_scalar(self.initial_temperature, "initial_temperature")

    @property
    def biot(self):
        return self.convection*self.length/self.conductivity

    @property
    def diffusivity(self):
        return self.conductivity/self.volumetric_heat_capacity

    def eigenvalues(self, terms):
        """The first ``terms`` positive roots beta_n of beta tan(beta) = Bi, increasing.

        f(beta) = beta sin(beta) - Bi cos(beta) has no poles and changes sign once
        in every (n pi, n pi + pi/2), so each root is bracketed and found by brentq.
        """
        if not isinstance(terms, (int, np.integer)) or isinstance(terms, bool) or terms < 1:
            raise ValueError("terms must be a positive integer")
        bi = self.biot
        f = lambda beta: beta*np.sin(beta)-bi*np.cos(beta)
        roots = []
        for n in range(terms):
            lo, hi = n*np.pi, (n+.5)*np.pi
            width = hi-lo
            roots.append(brentq(f, lo+1e-13*max(1., hi), hi-1e-13*max(1., hi),
                                xtol=1e-15*max(1., hi), rtol=4*np.finfo(float).eps, maxiter=200))
        roots = np.asarray(roots)
        if np.any(np.diff(roots) <= 0) or np.any(roots <= 0):
            raise ValueError("eigenvalue bracketing failed")
        return roots

    def tail_bound(self, terms, fourier):
        """Bound of the omitted terms n >= terms, in K, for Fourier number fourier > 0.

        |A_n| <= 2 |theta_0| / (beta_n - 1/2) <= 2 |theta_0| / (N pi - 1/2) and
        exp(-beta_n^2 Fo) <= exp(-n^2 pi^2 Fo); the geometric bound uses
        n^2 - N^2 >= (n - N)(2N + 1).
        """
        rise = abs(self.initial_temperature-self.ambient)
        n = terms
        lead = np.exp(-(n*np.pi)**2*fourier)
        ratio = np.exp(-(2*n+1)*np.pi**2*fourier)
        return 2*rise/(n*np.pi-.5)*lead/(1-ratio)

    def temperature(self, x, t, *, tolerance=1e-13, maximum_terms=20000):
        """T(x, t) with the series tail bounded by tolerance*|T0 - T_a|."""
        x = _coordinates(x, self.length)
        t = _finite_scalar(t, "t", nonnegative=True)
        rise = self.initial_temperature-self.ambient
        if t == 0 or rise == 0:
            return SlabTemperature(np.full(x.shape, self.initial_temperature), 0, 0.)
        fourier = self.diffusivity*t/self.length**2
        terms = _terms(lambda n: self.tail_bound(n, fourier), tolerance*abs(rise), maximum_terms)
        beta = self.eigenvalues(terms)
        amplitude = 2*np.sin(beta)/(beta+np.sin(beta)*np.cos(beta))
        xi = x/self.length
        series = np.sum(amplitude*np.cos(np.multiply.outer(xi, beta))*np.exp(-beta**2*fourier),
                        axis=-1)
        return SlabTemperature(self.ambient+rise*series, terms, float(self.tail_bound(terms, fourier)))

    def surface_outward_w_m2(self, t, **options):
        """Convective outward flux density h (T(L, t) - T_a) at x = L."""
        return self.convection*(self.temperature(self.length, t, **options).temperature_k-self.ambient)


@dataclass(frozen=True)
class FluxSlab:
    """Slab 0<x<L, insulated at x=0, constant outward flux g at x=L, uniform initial temperature."""
    length: float
    conductivity: float
    volumetric_heat_capacity: float
    outward_flux: float
    initial_temperature: float

    def __post_init__(self):
        _finite_scalar(self.length, "length", positive=True)
        _finite_scalar(self.conductivity, "conductivity", positive=True)
        _finite_scalar(self.volumetric_heat_capacity, "volumetric_heat_capacity", positive=True)
        _finite_scalar(self.outward_flux, "outward_flux")
        _finite_scalar(self.initial_temperature, "initial_temperature")

    @property
    def diffusivity(self):
        return self.conductivity/self.volumetric_heat_capacity

    @property
    def temperature_scale(self):
        """|g| L / k, the magnitude of the steady temperature difference across the slab."""
        return abs(self.outward_flux)*self.length/self.conductivity

    def tail_bound(self, terms, fourier):
        """Bound of the omitted terms n >= terms, in K: (2 scale / pi^2) sum exp(-n^2 pi^2 Fo) / n^2."""
        n = terms
        lead = np.exp(-(n*np.pi)**2*fourier)
        ratio = np.exp(-(2*n+1)*np.pi**2*fourier)
        return 2*self.temperature_scale/(np.pi**2*n**2)*lead/(1-ratio)

    def temperature(self, x, t, *, tolerance=1e-13, maximum_terms=20000):
        """T(x, t) with the series tail bounded by tolerance*|g| L / k."""
        x = _coordinates(x, self.length)
        t = _finite_scalar(t, "t", nonnegative=True)
        if t == 0 or self.outward_flux == 0:
            return SlabTemperature(np.full(x.shape, self.initial_temperature), 0, 0.)
        fourier = self.diffusivity*t/self.length**2
        terms = _terms(lambda n: self.tail_bound(n, fourier), tolerance*self.temperature_scale,
                       maximum_terms)
        n = np.arange(1, terms+1)
        xi = x/self.length
        series = np.sum((-1.)**n/n**2*np.exp(-(n*np.pi)**2*fourier)*np.cos(np.pi*np.multiply.outer(xi, n)),
                        axis=-1)
        bracket = fourier+(3*xi**2-1)/6-2/np.pi**2*series
        scale = self.outward_flux*self.length/self.conductivity
        return SlabTemperature(self.initial_temperature-scale*bracket, terms,
                               float(self.tail_bound(terms, fourier)))

    def mean_temperature(self, t):
        """Exact slab mean T0 - g t / (c L): the stored heat changes only through x = L."""
        t = _finite_scalar(t, "t", nonnegative=True)
        return self.initial_temperature-self.outward_flux*t/(self.volumetric_heat_capacity*self.length)


@dataclass(frozen=True)
class PeriodicAmbientSlab:
    """Slab 0<x<L, insulated at x=0, convective at x=L with T_a(t) = T_m + A sin(omega t).

    ``temperature`` is the periodic steady state (module docstring), not the
    solution from a given initial field: the difference decays as
    exp(-beta_1^2 alpha t / L^2) with beta_1 the first root of ConvectiveSlab.
    """
    length: float
    conductivity: float
    volumetric_heat_capacity: float
    convection: float
    mean_ambient: float
    amplitude: float
    angular_frequency: float

    def __post_init__(self):
        _finite_scalar(self.length, "length", positive=True)
        _finite_scalar(self.conductivity, "conductivity", positive=True)
        _finite_scalar(self.volumetric_heat_capacity, "volumetric_heat_capacity", positive=True)
        _finite_scalar(self.convection, "convection", positive=True)
        _finite_scalar(self.mean_ambient, "mean_ambient")
        _finite_scalar(self.amplitude, "amplitude")
        _finite_scalar(self.angular_frequency, "angular_frequency", positive=True)

    @property
    def diffusivity(self):
        return self.conductivity/self.volumetric_heat_capacity

    @property
    def period(self):
        return 2*np.pi/self.angular_frequency

    @property
    def wavenumber(self):
        """q = sqrt(i omega / alpha) = (1 + i) sqrt(omega / (2 alpha)), 1/m."""
        return (1+1j)*np.sqrt(self.angular_frequency/(2*self.diffusivity))

    def transient_decay_time(self):
        """L^2 / (alpha beta_1^2): the e-folding time of the slowest transient mode."""
        slab = ConvectiveSlab(self.length, self.conductivity, self.volumetric_heat_capacity,
                              self.convection, self.mean_ambient, self.mean_ambient+1.0)
        return self.length**2/(self.diffusivity*slab.eigenvalues(1)[0]**2)

    def discrete_wavenumber(self, time_step):
        """q_d = sqrt((1 - exp(-i omega dt)) / (alpha dt)) of backward Euler with step dt, 1/m."""
        dt = _finite_scalar(time_step, "time_step", positive=True)
        return np.sqrt((1-np.exp(-1j*self.angular_frequency*dt))/(self.diffusivity*dt))

    def complex_amplitude(self, x, time_step=None):
        """Theta(x) = A h cosh(q x) / (h cosh(q L) + k q sinh(q L)), K (complex).

        With ``time_step`` the backward-Euler wavenumber q_d replaces q: the
        periodic steady state of the time-discrete problem (module docstring).
        """
        x = _coordinates(x, self.length)
        q = self.wavenumber if time_step is None else self.discrete_wavenumber(time_step)
        h, k = self.convection, self.conductivity
        return self.amplitude*h*np.cosh(q*x)/(h*np.cosh(q*self.length)+k*q*np.sinh(q*self.length))

    def ambient(self, t):
        """T_a(t) = T_m + A sin(omega t)."""
        t = _finite_scalar(t, "t")
        return self.mean_ambient+self.amplitude*np.sin(self.angular_frequency*t)

    def temperature(self, x, t):
        """Periodic steady state T_m + Im[Theta(x) exp(i omega t)] (same shape as x)."""
        t = _finite_scalar(t, "t")
        theta = self.complex_amplitude(x)
        return self.mean_ambient+np.imag(theta*np.exp(1j*self.angular_frequency*t))

    def surface_outward_w_m2(self, t):
        """Convective outward flux density h (T(L, t) - T_a(t)) in the periodic steady state."""
        t = _finite_scalar(t, "t")
        theta = self.complex_amplitude(np.asarray(self.length))
        return self.convection*np.imag((theta-self.amplitude)*np.exp(1j*self.angular_frequency*t))


@dataclass(frozen=True)
class RampedFluxSlab:
    """Slab 0<x<L, insulated at x=0, outward flux g0 t / tau at x=L, uniform initial temperature."""
    length: float
    conductivity: float
    volumetric_heat_capacity: float
    outward_flux_rate: float      # g0 / tau, W/(m^2 s)
    initial_temperature: float

    def __post_init__(self):
        _finite_scalar(self.length, "length", positive=True)
        _finite_scalar(self.conductivity, "conductivity", positive=True)
        _finite_scalar(self.volumetric_heat_capacity, "volumetric_heat_capacity", positive=True)
        _finite_scalar(self.outward_flux_rate, "outward_flux_rate")
        _finite_scalar(self.initial_temperature, "initial_temperature")

    @property
    def diffusivity(self):
        return self.conductivity/self.volumetric_heat_capacity

    def outward_flux(self, t):
        """g(t) = (g0 / tau) t, W/m^2."""
        return self.outward_flux_rate*_finite_scalar(t, "t", nonnegative=True)

    def temperature_scale(self, t):
        """|g0 / tau| t^2 / (2 c L): the magnitude of the exact mean temperature change at t."""
        t = _finite_scalar(t, "t", nonnegative=True)
        return abs(self.outward_flux_rate)*t**2/(2*self.volumetric_heat_capacity*self.length)

    def tail_bound(self, terms, fourier):
        """Bound of the omitted terms n >= terms, in K: prefactor (2/pi^4) sum exp(-n^2 pi^2 Fo) / n^4."""
        prefactor = abs(self.outward_flux_rate)*self.length**3/(self.conductivity*self.diffusivity)
        n = terms
        lead = np.exp(-(n*np.pi)**2*fourier)
        ratio = np.exp(-(2*n+1)*np.pi**2*fourier)
        return prefactor*2/(np.pi**4*n**4)*lead/(1-ratio)

    def temperature(self, x, t, *, tolerance=1e-13, maximum_terms=20000):
        """T(x, t) with the series tail bounded by tolerance*temperature_scale(t)."""
        x = _coordinates(x, self.length)
        t = _finite_scalar(t, "t", nonnegative=True)
        if t == 0 or self.outward_flux_rate == 0:
            return SlabTemperature(np.full(x.shape, self.initial_temperature), 0, 0.)
        fourier = self.diffusivity*t/self.length**2
        terms = _terms(lambda n: self.tail_bound(n, fourier), tolerance*self.temperature_scale(t),
                       maximum_terms)
        n = np.arange(1, terms+1)
        xi = x/self.length
        series = np.sum((-1.)**n/n**4*np.exp(-(n*np.pi)**2*fourier)*np.cos(np.pi*np.multiply.outer(xi, n)),
                        axis=-1)
        bracket = fourier**2/2+fourier*(3*xi**2-1)/6+(15*xi**4-30*xi**2+7)/360+2/np.pi**4*series
        prefactor = self.outward_flux_rate*self.length**3/(self.conductivity*self.diffusivity)
        return SlabTemperature(self.initial_temperature-prefactor*bracket, terms,
                               float(self.tail_bound(terms, fourier)))

    def mean_temperature(self, t):
        """Exact slab mean T0 - (g0 / tau) t^2 / (2 c L)."""
        t = _finite_scalar(t, "t", nonnegative=True)
        return self.initial_temperature-self.outward_flux_rate*t**2/(2*self.volumetric_heat_capacity*self.length)
