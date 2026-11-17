# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The slab series and periodic states satisfy their PDE, boundary and initial conditions; no product imports."""
import numpy as np
import pytest

from refsol.transient_heat_robin import ConvectiveSlab, FluxSlab, PeriodicAmbientSlab
from refsol.transient_heat_robin import _RampedFluxSlab as RampedFluxSlab     # private: rule R(2), tests only

SLAB = dict(length=1.0, thermal_conductivity=2.5, volumetric_heat_capacity=4.0)
CONVECTIVE = ConvectiveSlab(**SLAB, heat_transfer_coefficient=5.0, ambient_temperature=300.0, initial_temperature=350.0)
FLUX = FluxSlab(**SLAB, inward_heat_flux=100.0, initial_temperature=300.0)       # outward -100 W/m^2
PERIODIC = PeriodicAmbientSlab(**SLAB, heat_transfer_coefficient=5.0, ambient_temperature=300.0,
                               temperature_difference=20.0, angular_frequency=2*np.pi/1.6)
RAMP = RampedFluxSlab(1.0, 2.5, 4.0, -100.0/0.2, 300.0)


def test_eigenvalues_solve_beta_tan_beta_equals_biot_in_their_brackets():
    beta = CONVECTIVE.eigenvalues(40)
    assert np.allclose(beta*np.tan(beta), CONVECTIVE.biot, rtol=1e-9, atol=1e-9)
    n = np.arange(40)
    assert np.all(beta > n*np.pi) and np.all(beta < (n+.5)*np.pi)
    with pytest.raises(ValueError):
        CONVECTIVE.eigenvalues(0)


@pytest.mark.parametrize("series", [CONVECTIVE, FLUX])
@pytest.mark.parametrize("t", [0.01, 0.2, 1.0])
def test_series_satisfy_the_heat_equation_and_both_faces(series, t):
    x = np.linspace(0.02, 0.98, 9)
    dx, dt = 2.5e-4, 1e-5
    T = lambda xx, tt: series.temperature(xx, time=tt).temperature
    alpha = series.diffusivity
    time_derivative = (T(x, t+dt)-T(x, t-dt))/(2*dt)
    space_second = (T(x+dx, t)-2*T(x, t)+T(x-dx, t))/dx**2
    scale = abs(time_derivative).max()
    np.testing.assert_allclose(time_derivative, alpha*space_second, rtol=0, atol=1e-5*scale)
    k, L = series.thermal_conductivity, series.length
    # Second-order one-sided differences at both faces (error O(dx^2)).
    at = lambda *xs: np.array([T(np.array([xx]), t)[0] for xx in xs])
    left_gradient = (-3*at(0.0)+4*at(dx)-at(2*dx))/(2*dx)
    right_gradient = (3*at(L)-4*at(L-dx)+at(L-2*dx))/(2*dx)
    if isinstance(series, ConvectiveSlab):
        expected = -series.heat_transfer_coefficient*(at(L)-series.ambient_temperature)/k
    else:
        expected = -(0.0-series.inward_heat_flux)/k                      # the outward flux g = 0.0 - inward
    assert abs(left_gradient[0]) <= 1e-4*abs(expected)
    np.testing.assert_allclose(right_gradient, expected, rtol=1e-4)


def test_initial_values_long_time_limits_and_truncation():
    x = np.linspace(0, 1, 11)
    assert np.all(CONVECTIVE.temperature(x, time=0.0).temperature == 350.0)
    assert np.all(FLUX.temperature(x, time=0.0).temperature == 300.0)
    small = CONVECTIVE.temperature(x[:-1], time=1e-5)
    assert small.truncation_bound <= 1e-13*50 and np.allclose(small.temperature, 350.0, atol=1e-6)
    late = CONVECTIVE.temperature(x, time=50.0)
    assert np.allclose(late.temperature, 300.0, atol=1e-9) and late.terms <= 2
    # Mean of the flux slab follows the exact heat balance T0 - g t / (c L).
    fine = np.linspace(0, 1, 4001)
    for t in (0.05, 0.5):
        mean = np.trapezoid(FLUX.temperature(fine, time=t).temperature, fine)
        assert abs(mean-FLUX.mean_temperature(time=t)) <= 1e-6
    far = FLUX.temperature(x, time=20.0).temperature
    np.testing.assert_allclose(far, FLUX.mean_temperature(time=20.0)+40.0*(3*x**2-1)/6, rtol=0, atol=1e-9)
    tight = CONVECTIVE.temperature(x, time=0.02, relative_tolerance=1e-15)
    loose = CONVECTIVE.temperature(x, time=0.02, relative_tolerance=1e-8)
    assert tight.terms > loose.terms
    assert np.max(abs(tight.temperature-loose.temperature)) <= loose.truncation_bound
    assert CONVECTIVE.outward_heat_flux(time=0.2) > 0


@pytest.mark.parametrize("bad", [dict(length=0.0), dict(thermal_conductivity=-1.0), dict(heat_transfer_coefficient=0.0),
                                 dict(ambient_temperature=np.nan), dict(initial_temperature=1j)])
def test_invalid_parameters(bad):
    values = dict(length=1.0, thermal_conductivity=2.5, volumetric_heat_capacity=4.0, heat_transfer_coefficient=5.0,
                  ambient_temperature=300.0, initial_temperature=350.0) | bad
    with pytest.raises(ValueError):
        ConvectiveSlab(**values)
    with pytest.raises(ValueError):
        CONVECTIVE.temperature([1.5], time=0.1)
    with pytest.raises(ValueError):
        CONVECTIVE.temperature([0.5], time=-1.0)


def _faces(T, t, dx=2.5e-4, L=1.0):
    """Second-order one-sided gradients at x=0 and x=L of T(x, t)."""
    at = lambda *xs: np.array([T(np.array([xx]), t)[0] for xx in xs])
    left = (-3*at(0.0)+4*at(dx)-at(2*dx))/(2*dx)
    right = (3*at(L)-4*at(L-dx)+at(L-2*dx))/(2*dx)
    return left[0], right[0], at(L)[0]


@pytest.mark.parametrize("t", [0.3, 3.3, 7.77])
def test_periodic_state_satisfies_heat_equation_insulated_and_convective_faces(t):
    x = np.linspace(0.02, 0.98, 9)
    dx, dt = 2.5e-4, 1e-5
    T = lambda xx, tt: PERIODIC.temperature(xx, time=tt)
    time_derivative = (T(x, t+dt)-T(x, t-dt))/(2*dt)
    space_second = (T(x+dx, t)-2*T(x, t)+T(x-dx, t))/dx**2
    np.testing.assert_allclose(time_derivative, PERIODIC.diffusivity*space_second, rtol=0,
                               atol=1e-5*abs(time_derivative).max())
    left, right, surface = _faces(T, t)
    expected = -PERIODIC.heat_transfer_coefficient*(surface-PERIODIC.ambient(time=t))/PERIODIC.thermal_conductivity
    assert abs(left) <= 1e-6*PERIODIC.temperature_difference
    np.testing.assert_allclose(right, expected, rtol=1e-4)
    np.testing.assert_allclose(PERIODIC.outward_heat_flux(time=t),
                               PERIODIC.heat_transfer_coefficient*(surface-PERIODIC.ambient(time=t)), rtol=1e-12)
    # Periodic in time, amplitude below the ambient amplitude, lagging and decaying inward.
    np.testing.assert_allclose(T(x, t+PERIODIC.period), T(x, t), rtol=0, atol=1e-10)
    theta = PERIODIC.complex_amplitude(np.array([0.0, 0.5, 1.0]))
    assert np.all(np.diff(abs(theta)) > 0) and abs(theta[-1]) < PERIODIC.temperature_difference
    assert np.all(np.angle(theta) < 0) and np.all(np.diff(np.angle(theta)) > 0)


@pytest.mark.parametrize("steps_per_period", [32, 128])
def test_discrete_amplitude_is_the_backward_euler_periodic_state(steps_per_period):
    dt = PERIODIC.period/steps_per_period
    z = np.exp(1j*PERIODIC.angular_frequency*dt)
    theta = lambda x: PERIODIC.complex_amplitude(x, time_step=dt)
    T = lambda x, n: PERIODIC.ambient_temperature+np.imag(theta(x)*z**n)
    x = np.linspace(0.02, 0.98, 9)
    dx = 2.5e-4
    for n in (3, 10):
        # (T_{n+1}-T_n)/dt = alpha T_{n+1}'' with the ambient at t_{n+1}.
        rate = (T(x, n+1)-T(x, n))/dt
        second = (T(x+dx, n+1)-2*T(x, n+1)+T(x-dx, n+1))/dx**2
        np.testing.assert_allclose(rate, PERIODIC.diffusivity*second, rtol=0, atol=1e-5*abs(rate).max())
        left, right, surface = _faces(lambda xx, _: T(xx, n+1), None)
        ambient = PERIODIC.ambient(time=(n+1)*dt)
        assert abs(left) <= 1e-6*PERIODIC.temperature_difference
        np.testing.assert_allclose(right, -PERIODIC.heat_transfer_coefficient*(surface-ambient)/PERIODIC.thermal_conductivity,
                                   rtol=1e-4)
    # First-order approach to the analytic amplitude as dt -> 0.
    exact = PERIODIC.complex_amplitude(np.array([0.0, 1.0]))
    coarse = abs(theta(np.array([0.0, 1.0]))-exact).max()
    fine = abs(PERIODIC.complex_amplitude(np.array([0.0, 1.0]), time_step=dt/2)-exact).max()
    assert 0.9 <= np.log2(coarse/fine) <= 1.1


@pytest.mark.parametrize("t", [0.01, 0.2, 1.0])
def test_ramped_flux_series_satisfies_heat_equation_and_both_faces(t):
    x = np.linspace(0.02, 0.98, 9)
    dx, dt = 2.5e-4, 1e-5
    T = lambda xx, tt: RAMP.temperature(xx, tt).temperature
    time_derivative = (T(x, t+dt)-T(x, t-dt))/(2*dt)
    space_second = (T(x+dx, t)-2*T(x, t)+T(x-dx, t))/dx**2
    np.testing.assert_allclose(time_derivative, RAMP.diffusivity*space_second, rtol=0,
                               atol=1e-5*abs(time_derivative).max())
    left, right, _ = _faces(T, t)
    assert abs(left) <= 1e-6*abs(RAMP.outward_flux(t))/RAMP.conductivity
    np.testing.assert_allclose(-RAMP.conductivity*right, RAMP.outward_flux(t), rtol=1e-4)
    fine = np.linspace(0, 1, 8001)
    values = T(fine, t)
    assert abs(np.trapezoid(values, fine)-RAMP.mean_temperature(t)) <= 1e-7*abs(values-RAMP.initial_temperature).max()


def test_ramped_flux_is_the_duhamel_integral_of_the_step_response():
    t = 0.2
    unit = FluxSlab(**SLAB, inward_heat_flux=-1.0, initial_temperature=0.0)     # unit outward flux
    u = np.linspace(0.0, t, 8001)
    x = np.array([0.0, 0.3, 1.0])
    step = np.array([unit.temperature(x, time=uu).temperature for uu in u])
    duhamel = RAMP.initial_temperature+RAMP.outward_flux_rate*np.trapezoid(step, u, axis=0)
    np.testing.assert_allclose(RAMP.temperature(x, t).temperature, duhamel, rtol=0, atol=1e-5)
    assert np.all(RAMP.temperature(x, 0.0).temperature == 300.0)
    small = RAMP.temperature(x, 1e-6)
    assert small.truncation_bound <= 1e-13*RAMP.temperature_scale(1e-6)
    np.testing.assert_allclose(small.temperature, 300.0, atol=1e-6)
    with pytest.raises(ValueError):
        RampedFluxSlab(1.0, 2.5, 4.0, np.nan, 300.0)
    with pytest.raises(ValueError):
        PeriodicAmbientSlab(**SLAB, heat_transfer_coefficient=5.0, ambient_temperature=300.0,
                            temperature_difference=20.0, angular_frequency=0.0)
    with pytest.raises(ValueError):
        PERIODIC.complex_amplitude(np.array([0.5]), time_step=-1.0)
