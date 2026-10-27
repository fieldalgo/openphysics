# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Transient heat on JAX and PyTorch values: histories and reverse-mode derivatives.

Values must match the NumPy solve. Derivatives are checked against the exact
discrete solution of an insulated, uniformly heated body (backward Euler then
reproduces T0 + Q t / c exactly) and against central differences of the NumPy
solve for every kind of live input. The NumPy path is covered by the existing
suites, unchanged. JAX and PyTorch cases skip when the library is absent; the CI
job that installs them first checks that both import.
"""
import numpy as np
import pytest

from galerkin.core.backend import TracedValueError
from galerkin.mesh import layered_rectangle_mesh, rectangle_mesh
from galerkin.transient_heat import TransientHeatStepError, solve_transient_heat


def _jax():
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    return jax


def _torch():
    return pytest.importorskip("torch")


def _numbers(a):
    return a.detach().numpy() if hasattr(a, "detach") else np.asarray(a)


def _live(name, values):
    if name == "jax":
        jnp = _jax().numpy
        return [jnp.asarray(v, dtype=jnp.float64) for v in values]
    torch = _torch()
    return [torch.tensor(v, dtype=torch.float64, requires_grad=True) for v in values]


def _wrap(name, data):
    if name is None:
        return np.asarray(data)
    if name == "jax":
        return _jax().numpy.asarray(data)
    return _torch().as_tensor(np.asarray(data))


def _gradient(name, objective, values):
    if name == "jax":
        return [float(g) for g in _jax().grad(lambda v: objective(*v))(_live("jax", values))]
    leaves = _live("torch", values)
    objective(*leaves).backward()
    return [float(x.grad) for x in leaves]


def _central(objective, values, rel=1e-6):
    out = []
    for i, v in enumerate(values):
        h = rel * max(1.0, abs(v))
        up, down = list(values), list(values)
        up[i] += h
        down[i] -= h
        out.append((float(objective(*up)) - float(objective(*down))) / (2 * h))
    return out


BACKENDS = ["jax", "torch"]
MESH = rectangle_mesh(1.0, 0.5, 6, 4)
LEFT = [int(i) for i in MESH.boundary["left"]]
X = MESH.nodes[:, 0]
TIMES = [0.0, 0.05, 0.1, 0.2, 0.35]


def _run(k, c, q, t_left, t0, slope, *, name=None):
    def wall(s, t_left=t_left, t0=t0):
        return t0 + (t_left - t0) * min(s / 0.1, 1.0)

    def source(points, s):
        return q * (1.0 + _wrap(name, points[:, 0]) * s)
    return solve_transient_heat(MESH, conductivity=k, volumetric_heat_capacity=c, time_s=TIMES,
                                initial_temperature_k=t0 + slope * _wrap(name, X),
                                dirichlet={i: wall for i in LEFT}, heat_source=source)


VALUES = (2.0, 3.0, 40.0, 320.0, 300.0, 10.0)
FIELDS = ("temperature_k", "heat_flux_w_m2", "source_load_w_per_m", "reaction_w_per_m",
          "residual_w_per_m", "storage_rate_w_per_m", "heat_content_j_per_m",
          "quadratic_functional_jk_per_m", "dirichlet_temperatures_k")


@pytest.mark.parametrize("name", BACKENDS)
def test_histories_match_numpy(name):
    reference = _run(*VALUES)
    live = _run(*_live(name, VALUES), name=name)
    for field in FIELDS:
        expected = getattr(reference, field)
        assert type(getattr(live, field)).__module__.split(".")[0] in ("jax", "jaxlib", "torch")
        np.testing.assert_allclose(_numbers(getattr(live, field)), expected, rtol=1e-12,
                                   atol=1e-12 * max(1.0, np.max(abs(expected))))
    np.testing.assert_array_equal(live.time_s, reference.time_s)
    np.testing.assert_array_equal(live.dirichlet_node_ids, reference.dirichlet_node_ids)


@pytest.mark.parametrize("name", BACKENDS)
def test_gradients_match_central_differences(name):
    def objective(*v, live=None):
        r = _run(*v, name=live)
        return (r.temperature_k[-1]**2).mean() + r.heat_content_j_per_m[2] * 1e-3
    got = _gradient(name, lambda *v: objective(*v, live=name), VALUES)
    np.testing.assert_allclose(got, _central(objective, VALUES), rtol=2e-6, atol=1e-8)


@pytest.mark.parametrize("name", BACKENDS)
def test_insulated_uniform_heating_matches_the_exact_discrete_solution(name):
    """No Dirichlet nodes, uniform T0 and Q: backward Euler gives T(t) = T0 + Q t / c exactly."""
    t_end = TIMES[-1]

    def final(k, c, q, t0):
        r = solve_transient_heat(MESH, conductivity=k, volumetric_heat_capacity=c, time_s=TIMES,
                                 initial_temperature_k=t0 + 0.0 * _wrap(name if hasattr(t0, "shape") else None, X),
                                 dirichlet={}, heat_source=q)
        return r.temperature_k[-1].mean()
    values = (2.0, 3.0, 40.0, 300.0)
    k, c, q, t0 = values
    assert abs(float(_numbers(final(*values))) - (t0 + q * t_end / c)) < 1e-12 * t0
    exact = [0.0, -q * t_end / c**2, t_end / c, 1.0]
    np.testing.assert_allclose(_gradient(name, final, values), exact, rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize("name", BACKENDS)
def test_region_tables_and_constant_dirichlet(name):
    mesh = layered_rectangle_mesh([0.4, 1.0], 0.5, [3, 4], 3)
    left = [int(i) for i in mesh.boundary["left"]]

    def objective(k0, k1, c0, c1, q1, t_left):
        r = solve_transient_heat(mesh, conductivity={"layer0": k0, "layer1": k1},
                                 volumetric_heat_capacity={"layer0": c0, "layer1": c1},
                                 time_s=[0.0, 0.1, 0.3], initial_temperature_k=np.full(mesh.num_nodes, 300.0),
                                 dirichlet={i: t_left for i in left},
                                 heat_source={"layer0": 0.0, "layer1": q1})
        return (r.temperature_k[-1] * r.temperature_k[1]).mean()
    values = (1.5, 4.0, 2.0, 5.0, 30.0, 300.0)
    # t_left must equal the initial temperature on its nodes at t0, so it is not varied.
    got = _gradient(name, lambda *v: objective(*v[:5], 300.0), values[:5])
    np.testing.assert_allclose(got, _central(lambda *v: objective(*v, 300.0), values[:5]), rtol=2e-6)


def test_jit_is_refused():
    """Inputs are checked before stepping (a direct error) and step data inside it (a step error)."""
    jax = _jax()
    for traced in ("initial", "source"):
        def history(q):
            if traced == "initial":                  # initial field traced: input check
                return _run(2.0, 3.0, 40.0, 320.0, 300.0, q, name="jax").temperature_k
            return _run(2.0, 3.0, q, 320.0, 300.0, 10.0).temperature_k   # source only: step 0
        expected = TracedValueError if traced == "initial" else TransientHeatStepError
        with pytest.raises(expected) as error:
            jax.jit(history)(jax.numpy.asarray(40.0))
        if traced == "source":
            assert error.value.time_index == 0 and isinstance(error.value.__cause__, TracedValueError)


def test_live_callback_after_numpy_start_is_refused():
    jax = _jax()

    def wall(s):
        return 300.0 if s == 0.0 else jax.numpy.asarray(310.0)
    with pytest.raises(TransientHeatStepError) as error:
        solve_transient_heat(MESH, conductivity=2.0, volumetric_heat_capacity=3.0, time_s=TIMES,
                             initial_temperature_k=np.full(MESH.num_nodes, 300.0),
                             dirichlet={i: wall for i in LEFT})
    assert error.value.time_index == 1
    assert isinstance(error.value.__cause__, TypeError) and "one array library" in str(error.value.__cause__)


@pytest.mark.parametrize("name", BACKENDS)
def test_transient_mechanics_refuses_a_live_heat_history(name):
    """The mechanical stage computes with NumPy, so a live history is refused, not cut."""
    import galerkin.transient_thermal_mechanical as workflow
    heat = _run(*_live(name, VALUES), name=name)
    with pytest.raises(workflow.TransientThermoelasticError) as caught:
        workflow.solve_transient_thermoelasticity(
            MESH, heat, units={"length": "m", "time": "s", "temperature": "K"},
            young_modulus=70e9, poisson_ratio=0.3, plane="strain", thermal_expansion_per_k=12e-6,
            reference_temperature_k=293.15, mechanical_dirichlet={(0, 0): 0.0, (0, 1): 0.0, (3, 1): 0.0})
    assert isinstance(caught.value.__cause__, TypeError)
    assert "cut the derivative" in str(caught.value.__cause__)


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("every", [1, 3])
def test_checkpointing_gives_the_same_values_and_gradients(name, every):
    """Blocks of 1 and 3 of the 4 steps (a shorter last block) against keeping every step."""
    def objective(*v, checkpoint_every=None):
        r = solve_transient_heat(MESH, conductivity=v[0], volumetric_heat_capacity=v[1], time_s=TIMES,
                                 initial_temperature_k=v[4] + 10.0 * _wrap(name, X),
                                 dirichlet={i: v[3] for i in LEFT},
                                 heat_source=lambda points, s: v[2] * (1.0 + _wrap(name, points[:, 0])),
                                 checkpoint_every=checkpoint_every)
        return (r.temperature_k[-1]**2).mean() + r.reaction_w_per_m.sum() + r.quadratic_functional_jk_per_m[-1]
    values = (2.0, 3.0, 40.0, 300.0, 300.0)
    kept = _gradient(name, objective, values)
    recomputed = _gradient(name, lambda *v: objective(*v, checkpoint_every=every), values)
    np.testing.assert_allclose(recomputed, kept, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(float(_numbers(objective(*_live(name, values), checkpoint_every=every))),
                               float(_numbers(objective(*_live(name, values)))), rtol=1e-14)


@pytest.mark.parametrize("bad", [0, -1, 1.5, True, "2"])
def test_checkpoint_every_is_validated(bad):
    with pytest.raises(ValueError, match="checkpoint_every"):
        solve_transient_heat(
            MESH, conductivity=2.0, volumetric_heat_capacity=3.0, time_s=TIMES,
            initial_temperature_k=np.full(MESH.num_nodes, 300.0), dirichlet={}, checkpoint_every=bad)


def test_checkpoint_every_does_not_change_numpy_results():
    def run(every):
        return solve_transient_heat(MESH, conductivity=2.0, volumetric_heat_capacity=3.0, time_s=TIMES,
                                    initial_temperature_k=300.0 + 10.0 * X,
                                    dirichlet={i: 300.0 for i in LEFT}, heat_source=40.0,
                                    checkpoint_every=every)
    a, b = run(None), run(2)
    for field in FIELDS:
        assert np.array_equal(getattr(a, field), getattr(b, field))
