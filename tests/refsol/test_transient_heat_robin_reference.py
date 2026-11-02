# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The slab series satisfy their PDE, boundary and initial conditions; no product imports."""
import numpy as np
import pytest

from refsol.transient_heat_robin import ConvectiveSlab, FluxSlab

CONVECTIVE = ConvectiveSlab(1.0, 2.5, 4.0, 5.0, 300.0, 350.0)
FLUX = FluxSlab(1.0, 2.5, 4.0, -100.0, 300.0)


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
    T = lambda xx, tt: series.temperature(xx, tt).temperature_k
    alpha = series.diffusivity
    time_derivative = (T(x, t+dt)-T(x, t-dt))/(2*dt)
    space_second = (T(x+dx, t)-2*T(x, t)+T(x-dx, t))/dx**2
    scale = abs(time_derivative).max()
    np.testing.assert_allclose(time_derivative, alpha*space_second, rtol=0, atol=1e-5*scale)
    k, L = series.conductivity, series.length
    # Second-order one-sided differences at both faces (error O(dx^2)).
    at = lambda *xs: np.array([T(np.array([xx]), t)[0] for xx in xs])
    left_gradient = (-3*at(0.0)+4*at(dx)-at(2*dx))/(2*dx)
    right_gradient = (3*at(L)-4*at(L-dx)+at(L-2*dx))/(2*dx)
    if isinstance(series, ConvectiveSlab):
        expected = -series.convection*(at(L)-series.ambient)/k
    else:
        expected = -series.outward_flux/k
    assert abs(left_gradient[0]) <= 1e-4*abs(expected)
    np.testing.assert_allclose(right_gradient, expected, rtol=1e-4)


def test_initial_values_long_time_limits_and_truncation():
    x = np.linspace(0, 1, 11)
    assert np.all(CONVECTIVE.temperature(x, 0.0).temperature_k == 350.0)
    assert np.all(FLUX.temperature(x, 0.0).temperature_k == 300.0)
    small = CONVECTIVE.temperature(x[:-1], 1e-5)
    assert small.truncation_bound_k <= 1e-13*50 and np.allclose(small.temperature_k, 350.0, atol=1e-6)
    late = CONVECTIVE.temperature(x, 50.0)
    assert np.allclose(late.temperature_k, 300.0, atol=1e-9) and late.terms <= 2
    # Mean of the flux slab follows the exact heat balance T0 - g t / (c L).
    fine = np.linspace(0, 1, 4001)
    for t in (0.05, 0.5):
        mean = np.trapezoid(FLUX.temperature(fine, t).temperature_k, fine)
        assert abs(mean-FLUX.mean_temperature(t)) <= 1e-6
    far = FLUX.temperature(x, 20.0).temperature_k
    np.testing.assert_allclose(far, FLUX.mean_temperature(20.0)+40.0*(3*x**2-1)/6, rtol=0, atol=1e-9)
    tight = CONVECTIVE.temperature(x, 0.02, tolerance=1e-15)
    loose = CONVECTIVE.temperature(x, 0.02, tolerance=1e-8)
    assert tight.terms > loose.terms
    assert np.max(abs(tight.temperature_k-loose.temperature_k)) <= loose.truncation_bound_k
    assert CONVECTIVE.surface_outward_w_m2(0.2) > 0


@pytest.mark.parametrize("bad", [dict(length=0.0), dict(conductivity=-1.0), dict(convection=0.0),
                                 dict(ambient=np.nan), dict(initial_temperature=1j)])
def test_invalid_parameters(bad):
    values = dict(length=1.0, conductivity=2.5, volumetric_heat_capacity=4.0, convection=5.0,
                  ambient=300.0, initial_temperature=350.0) | bad
    with pytest.raises(ValueError):
        ConvectiveSlab(**values)
    with pytest.raises(ValueError):
        CONVECTIVE.temperature([1.5], 0.1)
    with pytest.raises(ValueError):
        CONVECTIVE.temperature([0.5], -1.0)
