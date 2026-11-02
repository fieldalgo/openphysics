# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Self-checks of the temperature-dependent Joule slab reference.

Independent physics used here: the two conservation laws integrated once
(``J = -sigma V'`` constant and ``k (T'(0) - T'(x)) = J (V_a - V(x))``), the
fields recovered by numerical quadrature of the module's own derivatives,
finite differences, the constant-conductivity closed form as the ``alpha -> 0``
limit, symmetry, and the global power balance.
"""

import math

import numpy as np
import pytest
from scipy.integrate import quad

from refsol import joule_slab as js

CASES = [
    dict(potentials=(1.0, 0.0), temperatures=(300.0, 300.0), alpha=0.5),        # symmetric, rising sigma
    dict(potentials=(0.0, 1.2), temperatures=(300.0, 340.0), alpha=0.5),        # reversed current, hot face
    dict(potentials=(3.0, 0.0), temperatures=(330.0, 300.0), alpha=0.5),        # extremum inside, unequal faces
    dict(potentials=(1.0, 0.0), temperatures=(300.0, 300.0), alpha=-0.005),     # metal-like
    dict(potentials=(0.0, 4.0), temperatures=(320.0, 300.0), alpha=-0.004),     # metal-like, reversed
    dict(potentials=(1e-3, 0.0), temperatures=(300.0, 340.0), alpha=0.5),       # tiny drop: large slopes
    dict(potentials=(1e-3, 0.0), temperatures=(300.0, 340.0), alpha=-0.01),
]
COMMON = dict(length=1.0, sigma0=1.0, reference_temperature=300.0, thermal_conductivity=1.0)


def solve(case):
    return js.voltage_driven(COMMON["length"], case["potentials"], case["temperatures"], COMMON["sigma0"],
                             case["alpha"], COMMON["reference_temperature"], COMMON["thermal_conductivity"])


@pytest.mark.parametrize("case", CASES)
def test_boundary_values_are_exact(case):
    slab = solve(case)
    ends = np.array([0.0, slab.length])
    np.testing.assert_allclose(slab.temperature(ends), case["temperatures"], rtol=0, atol=1e-12)
    np.testing.assert_allclose(slab.potential(ends), case["potentials"], rtol=0, atol=1e-14)
    assert slab.temperature_range[0] <= min(case["temperatures"]) + 1e-12
    assert slab.temperature_range[1] >= max(case["temperatures"]) - 1e-12


@pytest.mark.parametrize("case", CASES)
def test_fields_satisfy_the_integrated_conservation_laws(case):
    slab = solve(case)
    x = np.linspace(0, slab.length, 41)
    J, k = slab.current_density, slab.thermal_conductivity
    v_a = case["potentials"][0]
    # Ohm: V(x) = V_a - int_0^x J / sigma(T) dx' with the module's own sigma(T(x))
    for xi in x[1:]:
        drop = quad(lambda t: J / slab.electrical_conductivity(t), 0.0, xi, epsabs=0, epsrel=1e-12, limit=200)[0]
        assert abs(slab.potential(xi) - (v_a - drop)) <= 1e-10 * max(1.0, abs(v_a - drop))
    # heat equation integrated once: k (T'(0) - T'(x)) = J (V_a - V(x))
    lhs = k * (slab.temperature_gradient(0.0) - slab.temperature_gradient(x))
    rhs = J * (v_a - slab.potential(x))
    np.testing.assert_allclose(lhs, rhs, rtol=1e-10, atol=1e-12 * max(1.0, abs(J)))
    # T is the integral of its gradient
    for xi in x[1:]:
        rise = quad(slab.temperature_gradient, 0.0, xi, epsabs=1e-12, epsrel=1e-12, limit=200)[0]
        assert abs(slab.temperature(xi) - case["temperatures"][0] - rise) <= 1e-9
    # heat source and electric field are consistent with J
    np.testing.assert_allclose(slab.heat_source(x), J * slab.electric_field(x), rtol=1e-13)
    np.testing.assert_allclose(slab.electrical_conductivity(x) * slab.electric_field(x), J, rtol=1e-13)


@pytest.mark.parametrize("case", CASES[:5])
def test_gradient_and_second_derivative_by_finite_differences(case):
    slab = solve(case)
    x = np.linspace(0.1, 0.9, 9)
    h = 1e-3
    first = (slab.temperature(x + h) - slab.temperature(x - h)) / (2 * h)
    fine = (slab.temperature(x + h / 2) - slab.temperature(x - h / 2)) / h
    richardson = (4 * fine - first) / 3
    np.testing.assert_allclose(richardson, slab.temperature_gradient(x), rtol=1e-8, atol=1e-10)
    # k T'' + sigma V'^2 = 0 to finite-difference truncation (h^2) and rounding (eps T / h^2)
    second = (slab.temperature(x + h) - 2 * slab.temperature(x) + slab.temperature(x - h)) / h**2
    source = slab.heat_source(x)
    tolerance = 1e-5 * np.max(source) + 300 * np.finfo(float).eps / h**2 * 10
    assert np.max(abs(slab.thermal_conductivity * second + source)) < tolerance


@pytest.mark.parametrize("case", CASES)
def test_power_balance(case):
    slab = solve(case)
    v_a, v_b = case["potentials"]
    assert slab.joule_power == pytest.approx(slab.current_density * (v_a - v_b), rel=1e-14)
    outflow = slab.thermal_conductivity * (slab.temperature_gradient(0.0) - slab.temperature_gradient(slab.length))
    assert outflow == pytest.approx(slab.joule_power, rel=1e-12, abs=1e-14)
    assert slab.joule_power >= 0


def test_alpha_to_zero_recovers_the_constant_conductivity_closed_form():
    constant = js.constant_conductivity(1.0, (1.0, 0.0), (300.0, 310.0), 1.0, 1.0)
    x = np.linspace(0, 1, 21)
    expected = 300 + 10 * x + 0.5 * x * (1 - x)
    np.testing.assert_allclose(constant.temperature(x), expected, rtol=1e-14)
    assert constant.current_density == 1.0 and constant.joule_power == 1.0
    assert js.voltage_driven(1.0, (1.0, 0.0), (300.0, 310.0), 1.0, 0.0, 300.0, 1.0).temperature(x).tolist() == expected.tolist()
    # first-order departure: the difference shrinks linearly with alpha (1e-2 -> 6.3e-3 K, 1e-4 -> 6.5e-5 K)
    deviations = []
    for alpha in (1e-2, 1e-3, 1e-4):
        slab = js.voltage_driven(1.0, (1.0, 0.0), (300.0, 310.0), 1.0, alpha, 300.0, 1.0)
        deviations.append(np.max(abs(slab.temperature(x) - expected)))
    assert deviations[0] / deviations[1] == pytest.approx(10, rel=0.03)
    assert deviations[1] / deviations[2] == pytest.approx(10, rel=0.03)
    assert deviations[2] < 1e-4


def test_symmetric_case_is_symmetric_and_matches_the_one_parameter_equation():
    slab = js.voltage_driven(1.0, (1.0, 0.0), (300.0, 300.0), 2.0, 0.5, 300.0, 1.5)
    x = np.linspace(0, 1, 11)
    np.testing.assert_allclose(slab.temperature(x), slab.temperature(1 - x), rtol=1e-14)
    np.testing.assert_allclose(slab.temperature_gradient(x), -slab.temperature_gradient(1 - x), rtol=1e-12, atol=1e-13)
    assert slab.temperature_gradient(0.5) == pytest.approx(0.0, abs=1e-12)
    # for T_a = T_b the maximum u_m solves L/2 = u_m sqrt(pi/(2c)) erf(sqrt(ln u_m)), c = alpha J^2/(k sigma0)
    u_m = 1 + 0.5 * (slab.temperature(0.5) - 300.0)
    c = 0.5 * slab.current_density**2 / (1.5 * 2.0)
    assert u_m * math.sqrt(math.pi / (2 * c)) * math.erf(math.sqrt(math.log(u_m))) == pytest.approx(0.5, rel=1e-12)
    # and the drop is 2 sqrt(2 k ln u_m / (alpha sigma0)) independently of J
    assert 2 * math.sqrt(2 * 1.5 * math.log(u_m) / (0.5 * 2.0)) == pytest.approx(1.0, rel=1e-12)


def test_reflection_of_the_data_reflects_the_solution():
    a = js.voltage_driven(2.0, (0.0, 3.0), (300.0, 330.0), 1.0, 0.4, 300.0, 1.0)
    b = js.voltage_driven(2.0, (3.0, 0.0), (330.0, 300.0), 1.0, 0.4, 300.0, 1.0)
    x = np.linspace(0, 2, 13)
    np.testing.assert_allclose(a.temperature(x), b.temperature(2 - x), rtol=1e-13)
    np.testing.assert_allclose(a.potential(x), b.potential(2 - x), rtol=1e-13, atol=1e-14)
    assert a.current_density == pytest.approx(-b.current_density, rel=1e-13)


def test_current_driven_round_trip_and_fold():
    slab = js.current_driven(1.0, 0.7, (300.0, 300.0), 1.0, 0.5, 300.0, 1.0, potential_a=2.0)
    assert slab.current_density == pytest.approx(0.7, rel=1e-12)
    assert slab.potential(0.0) == 2.0 and slab.potential(1.0) < 2.0
    again = js.voltage_driven(1.0, slab.potentials, (300.0, 300.0), 1.0, 0.5, 300.0, 1.0)
    assert again.current_density == pytest.approx(0.7, rel=1e-12)
    # alpha < 0: current rises with the drop up to a fold, two states below it, none above
    j_fold, d_fold = js.fold_current(1.0, (300.0, 300.0), 1.0, -0.005, 300.0, 1.0)
    for drop in (0.5 * d_fold, 2.0 * d_fold):
        assert abs(js.voltage_driven(1.0, (drop, 0.0), (300.0, 300.0), 1.0, -0.005, 300.0, 1.0).current_density) < j_fold
    lower = js.current_driven(1.0, 3.0, (300.0, 300.0), 1.0, -0.005, 300.0, 1.0, branch="lower")
    upper = js.current_driven(1.0, 3.0, (300.0, 300.0), 1.0, -0.005, 300.0, 1.0, branch="upper")
    assert lower.current_density == pytest.approx(3.0, rel=1e-12)
    assert upper.current_density == pytest.approx(3.0, rel=1e-12)
    assert lower.potentials[1] > upper.potentials[1] and lower.temperature_range[1] < upper.temperature_range[1]
    with pytest.raises(ValueError, match="fold"):
        js.current_driven(1.0, 1.01 * j_fold, (300.0, 300.0), 1.0, -0.005, 300.0, 1.0)
    with pytest.raises(ValueError, match="alpha < 0"):
        js.fold_current(1.0, (300.0, 300.0), 1.0, 0.5, 300.0, 1.0)


def test_no_drop_means_no_current_and_a_linear_profile():
    slab = js.voltage_driven(1.0, (2.0, 2.0), (300.0, 320.0), 1.0, 0.5, 300.0, 1.0)
    x = np.linspace(0, 1, 5)
    assert slab.current_density == 0.0 and slab.joule_power == 0.0
    np.testing.assert_allclose(slab.temperature(x), 300 + 20 * x, rtol=1e-14)
    np.testing.assert_allclose(slab.electrical_conductivity(x), 1 + 0.5 * 20 * x, rtol=1e-14)


def test_invalid_inputs_are_refused():
    with pytest.raises(ValueError, match="positive at both faces"):
        js.voltage_driven(1.0, (1.0, 0.0), (300.0, 320.0), 1.0, -0.1, 300.0, 1.0)
    with pytest.raises(ValueError, match="length"):
        js.voltage_driven(0.0, (1.0, 0.0), (300.0, 300.0), 1.0, 0.5, 300.0, 1.0)
    with pytest.raises(ValueError, match="pair"):
        js.voltage_driven(1.0, (1.0,), (300.0, 300.0), 1.0, 0.5, 300.0, 1.0)
    with pytest.raises(ValueError, match="x must lie"):
        js.voltage_driven(1.0, (1.0, 0.0), (300.0, 300.0), 1.0, 0.5, 300.0, 1.0).temperature([1.5])
    with pytest.raises(ValueError, match="branch"):
        js.current_driven(1.0, 1.0, (300.0, 300.0), 1.0, 0.5, 300.0, 1.0, branch="middle")
