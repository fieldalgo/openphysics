# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""solve_temperature_joule_heat(method="newton"): Newton on the potential and temperature together.

The convergence judgment is the Picard one, so Newton is checked against
Picard where Picard converges, where the default Picard does not, with every
boundary kind and region models, and through its Jacobian: complex-step
element blocks and the assembled matrix against central differences of the
residual it linearizes. Analytic and scikit-fem references run both methods
in test_temperature_joule_heating.py and test_crosscheck_skfem_temperature_joule.py.
"""
import numpy as np
import pytest
from numpy.testing import assert_allclose

import galerkin.temperature_joule_heating as module
from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.electric import ElementConductivity, solve_steady_electric
from galerkin.joule_heating import solve_steady_joule_heat
from galerkin.temperature_joule_heating import (
    _DIFFERENCE_STEP, ConductivityModel, JouleConvergenceError, _conductivity, _conductivity_derivative,
    _difference, _JointNewton, _models, solve_temperature_joule_heat)


def bounded(evaluate, lo, hi):
    """sigma(T) that, like a table, exists only inside its declared range."""
    def inside(t):
        if np.any(t < lo) or np.any(t > hi):
            raise ValueError(f"sigma evaluated at [{t.min()}, {t.max()}] K, outside [{lo}, {hi}] K")
        return evaluate(t)
    return inside


def thermistor(n=16, alpha=.5, **options):
    """The analytic current-driven thermistor of the contract page: rho(T) = 1 + alpha (T - 300)."""
    mesh = rectangle_mesh(1., .25, n, max(2, n//4))
    left, right = mesh.boundary['left'], mesh.boundary['right']
    model = ConductivityModel(bounded(lambda t: 1/(1+alpha*(t-300)), 300., 400.), (300., 400.))
    args = dict(electrical_conductivity=model, thermal_conductivity=1.,
                electric_dirichlet={int(i): 0. for i in left},
                thermal_dirichlet={int(i): 300. for i in np.r_[left, right]}, initial_temperature=300.,
                outward_current={'right': 1.})
    args.update(options)
    return mesh, args


def every_boundary_kind(current=3., **options):
    """A floating electric component held by a gauge, flux and two Robin edges, two regions."""
    base = rectangle_mesh(2., 1., 16, 8)
    centers = base.nodes[base.triangles].mean(axis=1)
    mesh = Mesh(base.nodes, base.triangles, base.boundary, base.boundary_edges,
                (centers[:, 0] > 1.).astype(int), ['a', 'b'])
    left = mesh.boundary['left']
    models = {'a': ConductivityModel(bounded(lambda t: 2/(1+.01*(t-300)), 250., 900.), (250., 900.)),
              'b': ConductivityModel(bounded(lambda t: np.exp(.01*(t-300)), 250., 900.), (250., 900.))}
    args = dict(electrical_conductivity=models, thermal_conductivity={'a': 1., 'b': 2.},
                electric_dirichlet={}, reference_potential={int(left[0]): 0.},
                outward_current={'left': -current, 'right': current},
                thermal_dirichlet={int(i): 300. for i in left}, initial_temperature=300.,
                outward_flux={'bottom': 5.}, convection={'top': (3., 290.), 'right': (2., 300.)})
    args.update(options)
    return mesh, args


def test_invalid_method_and_derivative():
    mesh, args = thermistor(8)
    default = solve_temperature_joule_heat(mesh, **args)    # Picard is the default
    picard = solve_temperature_joule_heat(mesh, **args, method='picard')
    assert np.array_equal(default.coupled.thermal.temperature, picard.coupled.thermal.temperature)
    assert len(default.history) == len(picard.history)
    with pytest.raises(ValueError, match="method must be 'picard' or 'newton'"):
        solve_temperature_joule_heat(mesh, **args, method='secant')
    with pytest.raises(ValueError, match='derivative'):
        ConductivityModel(lambda t: t, (0., 400.), derivative=1.)


@pytest.mark.parametrize('alpha', [.5, 7.])
def test_newton_matches_picard_in_few_states(alpha):
    mesh, args = thermistor(alpha=alpha)
    picard = solve_temperature_joule_heat(mesh, **args, method='picard', relaxation=1., max_iterations=300)
    newton = solve_temperature_joule_heat(mesh, **args, method='newton')
    assert len(newton.history) <= 5 < len(picard.history)
    assert_allclose(newton.coupled.thermal.temperature, picard.coupled.thermal.temperature, rtol=0., atol=2e-8)
    assert_allclose(newton.coupled.electrical.potential, picard.coupled.electrical.potential, rtol=0., atol=2e-8)
    last = newton.history[-1]
    assert last.conductivity_defect <= 1e-10 and last.nonlinear_heat_residual <= 1e-8
    assert abs(last.current_balance) < 1e-10 and abs(last.heat_power_defect) < 1e-10
    assert [row.iteration for row in newton.history] == list(range(1, len(newton.history)+1))
    assert not newton.evaluated_temperature.flags.writeable


@pytest.mark.parametrize('alpha', [.5, 7.])
def test_newton_converges_quadratically_with_an_exact_derivative(alpha):
    """Below 1e-2 K each defect (K) is at most the previous one squared (1/K), down to the
    rounding floor of 300 K temperatures (taken as 1e-12 K); at least one step is checked."""
    model = ConductivityModel(bounded(lambda t: 1/(1+alpha*(t-300)), 300., 400.), (300., 400.),
                              derivative=lambda t: -alpha/(1+alpha*(t-300))**2)
    mesh, args = thermistor(alpha=alpha, electrical_conductivity=model)
    defects = [row.temperature_defect
               for row in solve_temperature_joule_heat(mesh, **args, method='newton').history]
    pairs = [(before, after) for before, after in zip(defects, defects[1:]) if before < 1e-2]
    assert pairs and all(after <= max(before**2, 1e-12) for before, after in pairs)


@pytest.mark.parametrize('alpha', [7., 9.])
def test_newton_converges_where_the_default_picard_does_not(alpha):
    mesh, args = thermistor(alpha=alpha)
    with pytest.raises(JouleConvergenceError, match='maximum iterations'):
        solve_temperature_joule_heat(mesh, **args, method='picard')
    result = solve_temperature_joule_heat(mesh, **args, method='newton')
    assert len(result.history) <= 6
    reference = solve_temperature_joule_heat(mesh, **args, method='picard', relaxation=1., max_iterations=500)
    assert_allclose(result.coupled.thermal.temperature, reference.coupled.thermal.temperature, rtol=0., atol=2e-8)


def test_newton_with_every_boundary_kind_and_region_models():
    mesh, args = every_boundary_kind()
    picard = solve_temperature_joule_heat(mesh, **args, method='picard', relaxation=1., max_iterations=300)
    newton = solve_temperature_joule_heat(mesh, **args, method='newton')
    assert len(newton.history) <= 5
    assert_allclose(newton.coupled.thermal.temperature, picard.coupled.thermal.temperature, rtol=0., atol=2e-8)
    assert_allclose(newton.coupled.electrical.potential, picard.coupled.electrical.potential, rtol=0., atol=2e-8)
    assert_allclose(newton.coupled.electrical.conductivity, picard.coupled.electrical.conductivity, rtol=1e-10)


def test_given_derivative_is_used_and_does_not_change_the_result():
    calls = []
    def derivative(t):
        calls.append(len(t))
        return -7/(1+7*(t-300))**2
    mesh, args = thermistor(alpha=7.)
    plain = solve_temperature_joule_heat(mesh, **args, method='newton')
    args['electrical_conductivity'] = ConductivityModel(lambda t: 1/(1+7*(t-300)), (300., 400.),
                                                        derivative=derivative)
    given = solve_temperature_joule_heat(mesh, **args, method='newton')
    assert calls and set(calls) == {mesh.num_triangles}
    assert len(given.history) <= min(len(plain.history), 5)
    temperature = 300+np.linspace(0., .4, mesh.num_nodes)
    mean = np.sum(temperature[mesh.triangles]/3., axis=1)
    used = _conductivity_derivative(mesh, _models(mesh, args['electrical_conductivity']), temperature)
    assert np.array_equal(used, derivative(mean))
    assert_allclose(given.coupled.thermal.temperature, plain.coupled.thermal.temperature, rtol=0., atol=2e-8)
    args['electrical_conductivity'] = ConductivityModel(lambda t: 1/(1+7*(t-300)), (300., 400.),
                                                        derivative=lambda t: t[:1])
    with pytest.raises(JouleConvergenceError, match='dsigma/dT') as exc:
        solve_temperature_joule_heat(mesh, **args, method='newton')
    assert len(exc.value.history) == 1 and isinstance(exc.value.__cause__, ValueError)


def test_the_difference_derivative_stays_in_range_and_is_second_order():
    """Without a derivative: central inside the range, second order one-sided within a step of
    an end, first order where that stencil does not fit; no point outside the range is evaluated."""
    seen = []

    def sigma(t):
        seen.append(t.copy())
        return np.exp(t/50.)
    lo, hi = 300., 400.
    h = _DIFFERENCE_STEP*lo
    mean = np.array([lo, lo+h/2, 350., hi-h/2, hi])
    error = _difference(ConductivityModel(bounded(sigma, lo, hi), (lo, hi)), mean, 'm')/(np.exp(mean/50.)/50.)-1
    # Second order: about (step/50 K)**2 = 1e-9; a first-order end would give 2e-5.
    assert np.max(np.abs(error)) <= 1e-8
    narrow = ConductivityModel(bounded(sigma, lo, lo+h), (lo, lo+h))
    assert abs(_difference(narrow, np.array([lo+h/2]), 'n')[0]/(np.exp((lo+h/2)/50.)/50.)-1) <= 1e-4
    assert min(t.min() for t in seen) >= lo and max(t.max() for t in seen) <= hi


def test_newton_failures_keep_their_evidence():
    mesh, args = thermistor(alpha=7., max_iterations=2)
    with pytest.raises(JouleConvergenceError, match='maximum iterations') as exc:
        solve_temperature_joule_heat(mesh, **args, method='newton')
    assert len(exc.value.history) == 2
    assert exc.value.last_temperature.shape == (mesh.num_nodes,)
    assert not exc.value.last_temperature.flags.writeable
    # No steady solution inside the material range: every candidate leaves it.
    mesh, args = thermistor(alpha=10.)
    with pytest.raises(JouleConvergenceError, match=r"^Newton step does not reduce the temperature defect "
                       r"\([0-9.e+-]+ K\); last candidate failed: material 'all': temperature") as exc:
        solve_temperature_joule_heat(mesh, **args, method='newton')
    assert len(exc.value.history) == 1 and isinstance(exc.value.__cause__, ValueError)
    assert f"({exc.value.history[-1].temperature_defect:.3g} K)" in exc.value.reason
    assert np.all(exc.value.last_temperature == 300.)


def test_a_step_that_no_longer_changes_t_ends_the_search(monkeypatch):
    """When the step stops moving T, as at the rounding floor, halving ends at once and the error
    names the defect of the last accepted state."""
    steps, evaluations = [], []
    newton_step = _JointNewton.step

    def step(self, *args):
        steps.append(1)
        increment = newton_step(self, *args)
        return increment if len(steps) == 1 else 0*increment
    monkeypatch.setattr(_JointNewton, 'step', step)
    joule = module.solve_steady_joule_heat
    monkeypatch.setattr(module, 'solve_steady_joule_heat',
                        lambda *args, **kwargs: evaluations.append(1) or joule(*args, **kwargs))
    mesh, args = thermistor(alpha=7.)
    with pytest.raises(JouleConvergenceError,
                       match=r"^Newton step does not reduce the temperature defect \([0-9.e+-]+ K\)$") as exc:
        solve_temperature_joule_heat(mesh, **args, method='newton')
    history = exc.value.history
    assert len(history) == 2 and f"({history[-1].temperature_defect:.3g} K)" in exc.value.reason
    assert len(evaluations) == 3   # T_1, the accepted T_2 and the unchanged T_2 at the full step


def test_a_candidate_that_passes_the_convergence_tests_is_accepted(monkeypatch):
    """The judgment decides: with the decrease test made unsatisfiable, the linear (alpha = 0)
    problem still converges in one step, because its first candidate passes the convergence tests."""
    monkeypatch.setattr(module, '_euclidean', lambda a: 1.)
    mesh, args = thermistor(alpha=0.)
    result = solve_temperature_joule_heat(mesh, **args, method='newton')
    assert len(result.history) == 2


def test_a_failed_long_candidate_is_not_reported_when_the_last_one_evaluates(monkeypatch):
    """Steps reversed and lengthened: the longest candidates leave the range, the shorter ones
    evaluate but raise the defect. The failure then names no candidate failure and no cause."""
    range_errors = []
    conductivity = module._conductivity

    def counted(*args):
        try:
            return conductivity(*args)
        except ValueError:
            range_errors.append(1)
            raise
    monkeypatch.setattr(module, '_conductivity', counted)
    newton_step = _JointNewton.step
    monkeypatch.setattr(_JointNewton, 'step', lambda self, *a: -20*newton_step(self, *a))
    mesh, args = thermistor(initial_temperature=310.)
    with pytest.raises(JouleConvergenceError,
                       match=r"^Newton step does not reduce the temperature defect \([0-9.e+-]+ K\)$") as exc:
        solve_temperature_joule_heat(mesh, **args, method='newton')
    assert range_errors and exc.value.__cause__ is None and len(exc.value.history) == 1


def _state(seed=0):
    """A nonuniform (V, T) state of the every-boundary-kind problem and its Newton system."""
    mesh, args = every_boundary_kind()
    rng = np.random.default_rng(seed)
    temperature = 300+rng.uniform(0, 60, mesh.num_nodes)
    potential = rng.uniform(-2, 2, mesh.num_nodes)
    models = _models(mesh, args['electrical_conductivity'])
    newton = _JointNewton(mesh, args['thermal_conductivity'], args['thermal_dirichlet'],
                          set(args['reference_potential']), args['outward_flux'], args['convection'])
    return mesh, models, newton, temperature, potential


def test_element_jacobian_against_central_differences():
    mesh, models, newton, temperature, potential = _state()
    sigma = _conductivity(mesh, models, temperature)
    blocks = newton.element_jacobian(sigma, _conductivity_derivative(mesh, models, temperature), potential)
    cells = mesh.triangles

    def local(v_local, t_local):
        """Element residuals (R_V, R_T rows) with sigma evaluated at the element-mean temperature."""
        sig = np.empty(mesh.num_triangles)
        for _, idx, model in models:
            sig[idx] = model.evaluate(np.sum(t_local[idx]/3., axis=1))
        r_v, load = newton.element_residuals(sig, v_local)
        return np.concatenate([r_v, -load], axis=1)

    v0, t0 = potential[cells], temperature[cells]
    for j in range(6):
        h = 1e-6*(1. if j < 3 else 300.)
        dv, dt = np.zeros_like(v0), np.zeros_like(t0)
        (dv if j < 3 else dt)[:, j % 3] = h
        central = (local(v0+dv, t0+dt)-local(v0-dv, t0-dt))/(2*h)
        scale = np.max(np.abs(central))
        assert np.max(np.abs(blocks[:, :, j]-central)) <= 1e-7*scale


def test_assembled_jacobian_against_central_differences():
    mesh, models, newton, temperature, potential = _state(1)
    n = mesh.num_nodes

    def residual(v, t):
        sig = _conductivity(mesh, models, t)
        r_v, load = newton.element_residuals(sig, v[mesh.triangles])
        electric, joule = np.zeros(n), np.zeros(n)
        np.add.at(electric, mesh.triangles, r_v)
        np.add.at(joule, mesh.triangles, load)
        return np.concatenate([electric, newton.heat_operator@t-joule-newton.heat_rhs])

    sigma = _conductivity(mesh, models, temperature)
    jacobian = newton.jacobian(sigma, _conductivity_derivative(mesh, models, temperature),
                               potential).to_scipy()
    rng = np.random.default_rng(2)
    for _ in range(3):
        d = rng.standard_normal(2*n)
        h = 1e-6
        central = (residual(potential+h*d[:n], temperature+h*d[n:])
                   - residual(potential-h*d[:n], temperature-h*d[n:]))/(2*h)
        assert np.max(np.abs(jacobian@d-central)) <= 1e-7*np.max(np.abs(central))


def test_newton_holds_the_gauge_node(monkeypatch):
    """The reference potential of a floating component is held in the Newton system."""
    held = []
    initialise = _JointNewton.__init__

    def spy(self, *args):
        initialise(self, *args)
        held.append({int(i) for i in self.fixed})
    monkeypatch.setattr(_JointNewton, '__init__', spy)
    mesh, args = every_boundary_kind()
    solve_temperature_joule_heat(mesh, **args, method='newton')
    assert held and set(args['reference_potential']) <= held[0]


def test_newton_heat_operator_is_the_heat_solve():
    """R_T at the heat solve's temperature, from the Newton operator, vanishes on free nodes."""
    mesh, args = every_boundary_kind()
    models = _models(mesh, args['electrical_conductivity'])
    sigma = _conductivity(mesh, models, np.full(mesh.num_nodes, 300.))
    electrical = solve_steady_electric(mesh, conductivity=ElementConductivity(mesh, sigma), dirichlet={},
                                       outward_current=args['outward_current'],
                                       reference_potential=args['reference_potential'])
    heat = solve_steady_joule_heat(mesh, electrical_result=electrical, conductivity=args['thermal_conductivity'],
                                   dirichlet=args['thermal_dirichlet'], outward_flux=args['outward_flux'],
                                   convection=args['convection']).thermal
    newton = _JointNewton(mesh, args['thermal_conductivity'], args['thermal_dirichlet'],
                          set(args['reference_potential']), args['outward_flux'], args['convection'])
    residual = newton.heat_operator@heat.temperature-heat.load-newton.heat_rhs
    free = np.setdiff1d(np.arange(mesh.num_nodes), list(args['thermal_dirichlet']))
    scale = max(np.max(np.abs(heat.load)), np.max(np.abs(newton.heat_rhs)))
    assert np.max(np.abs(residual[free])) <= 1e-12*scale


def test_newton_electric_residual_is_the_electric_solve():
    """R_V at (V(T), T) from the element residuals is the electric solve's own residual."""
    mesh, args = every_boundary_kind()
    models = _models(mesh, args['electrical_conductivity'])
    temperature = np.full(mesh.num_nodes, 300.)
    sigma = _conductivity(mesh, models, temperature)
    electrical = solve_steady_electric(mesh, conductivity=ElementConductivity(mesh, sigma), dirichlet={},
                                       outward_current=args['outward_current'],
                                       reference_potential=args['reference_potential'])
    newton = _JointNewton(mesh, args['thermal_conductivity'], args['thermal_dirichlet'],
                          set(args['reference_potential']), args['outward_flux'], args['convection'])
    r_v, _ = newton.element_residuals(sigma, np.asarray(electrical.potential)[mesh.triangles])
    assembled = np.zeros(mesh.num_nodes)
    np.add.at(assembled, mesh.triangles, r_v)
    assembled += electrical.prescribed_outward_load
    scale = np.max(np.abs(electrical.prescribed_outward_load))
    assert_allclose(assembled, electrical.residual, rtol=0., atol=1e-12*scale)


def test_steps_that_raise_the_defect_are_halved(monkeypatch):
    """With every Newton step made 64 times too long, six halvings restore convergence."""
    mesh, args = thermistor(alpha=7.)
    reference = solve_temperature_joule_heat(mesh, **args, method='picard', relaxation=1., max_iterations=300)
    newton_step = _JointNewton.step
    monkeypatch.setattr(_JointNewton, 'step', lambda self, *a: 64*newton_step(self, *a))
    result = solve_temperature_joule_heat(mesh, **args, method='newton')
    assert len(result.history) <= 6
    assert [row.iteration for row in result.history] == list(range(1, len(result.history)+1))
    assert_allclose(result.coupled.thermal.temperature, reference.coupled.thermal.temperature, rtol=0., atol=2e-8)
