# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady heat and electric conduction on JAX and PyTorch values.

Values must match the NumPy solve; derivatives are checked against closed forms
on slabs where P1 is exact and against central differences of the NumPy solve
for every kind of live input. The NumPy path itself is covered by the existing
suites, unchanged. JAX and PyTorch cases skip when the library is absent; the CI
job that installs them first checks that both import.
"""
import numpy as np
import pytest

from galerkin.electric import solve_steady_electric
from galerkin.heat_source import ElementHeatSource
from galerkin.mesh import layered_rectangle_mesh, rectangle_mesh
from galerkin.thermal import solve_steady_heat
from galerkin.core.backend import TracedValueError


def _jax():
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    return jax


def _torch():
    return pytest.importorskip("torch")


def _numbers(a):
    return a.detach().numpy() if hasattr(a, "detach") else np.asarray(a)


def _live(name, values):
    """Each value as a live float64 scalar of the named library (leaves for PyTorch)."""
    if name == "jax":
        jnp = _jax().numpy
        return [jnp.asarray(v, dtype=jnp.float64) for v in values]
    torch = _torch()
    return [torch.tensor(v, dtype=torch.float64, requires_grad=True) for v in values]


def _gradient(name, objective, values):
    """d objective / d values on the named library."""
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


def _wrap(name, data):
    """A NumPy array as a constant of the named library, for callbacks."""
    if name == "jax":
        return _jax().numpy.asarray(data)
    return _torch().as_tensor(np.asarray(data))


BACKENDS = ["jax", "torch"]

# -- heat ----------------------------------------------------------------------

MESH = rectangle_mesh(1.0, 0.5, 6, 4)
LEFT = [int(i) for i in MESH.boundary["left"]]


def _heat(k, q, t0, g, h, ambient, *, name=None):
    def flux(points, normals):
        x = points[:, 0] if name is None else _wrap(name, points[:, 0])
        return g * (1.0 + x)

    def source(points):
        y = points[:, 1] if name is None else _wrap(name, points[:, 1])
        return q * (2.0 - y)
    return solve_steady_heat(MESH, conductivity=k, dirichlet={i: t0 for i in LEFT}, heat_source=source,
                             outward_flux={"top": flux}, convection={"right": (h, ambient)})


HEAT = (2.0, 50.0, 300.0, 3.0, 10.0, 290.0)
HEAT_FIELDS = ("temperature", "heat_flux", "load", "reaction", "residual", "prescribed_outward_load",
               "ambient_load", "convective_outward", "system_rhs")


@pytest.mark.parametrize("name", BACKENDS)
def test_heat_values_match_numpy(name):
    reference = _heat(*HEAT)
    live = _heat(*_live(name, HEAT), name=name)
    for field in HEAT_FIELDS:
        expected = getattr(reference, field)
        got = _numbers(getattr(live, field))
        assert type(getattr(live, field)).__module__.split(".")[0] in ("jax", "jaxlib", "torch")
        np.testing.assert_allclose(got, expected, rtol=1e-12, atol=1e-12 * max(1.0, np.max(abs(expected))))


@pytest.mark.parametrize("name", BACKENDS)
def test_heat_gradients_match_central_differences(name):
    def mean_temperature(*v, live=None):
        return _heat(*v, name=live).temperature.mean()
    got = _gradient(name, lambda *v: mean_temperature(*v, live=name), HEAT)
    expected = _central(lambda *v: mean_temperature(*v), HEAT)
    np.testing.assert_allclose(got, expected, rtol=2e-6, atol=1e-9)


@pytest.mark.parametrize("name", BACKENDS)
def test_heat_slab_right_temperature_matches_closed_form(name):
    """Dirichlet T0 at x=0, convection (h, Ta) at x=L, no source: T(L) = Ta + (T0-Ta)/(h (L/k + 1/h))."""
    L, k, h, t0, ta = 1.0, 2.0, 5.0, 350.0, 300.0
    right = np.asarray(MESH.boundary["right"], dtype=int)

    def fem(k, h, t0, ta):
        r = solve_steady_heat(MESH, conductivity=k, dirichlet={i: t0 for i in LEFT}, convection={"right": (h, ta)})
        return r.temperature[right].mean()

    def closed(k, h, t0, ta):
        return ta + (t0 - ta) / (h * (L / k + 1 / h))
    values = (k, h, t0, ta)
    assert abs(float(_numbers(fem(*values))) - closed(*values)) < 1e-10 * closed(*values)
    r_total = L / k + 1 / h
    exact = [(t0 - ta) * L / (k**2 * h * r_total**2),          # d/dk
             -(t0 - ta) * L / (k * (h * r_total)**2),          # d/dh
             1 / (h * r_total),                                # d/dT0
             1 - 1 / (h * r_total)]                            # d/dTa
    np.testing.assert_allclose(_gradient(name, fem, values), exact, rtol=1e-10)


@pytest.mark.parametrize("name", BACKENDS)
def test_heat_region_conductivity_and_source_tables(name):
    mesh = layered_rectangle_mesh([0.4, 1.0], 0.5, [3, 4], 3)
    left = [int(i) for i in mesh.boundary["left"]]
    right = [int(i) for i in mesh.boundary["right"]]

    def solve(k0, k1, q0, q1, t_left):
        r = solve_steady_heat(mesh, conductivity={"layer0": k0, "layer1": k1},
                              heat_source={"layer0": q0, "layer1": q1},
                              dirichlet={**{i: t_left for i in left}, **{i: 300.0 for i in right}})
        return (r.temperature**2).mean()
    values = (1.5, 4.0, 20.0, -7.0, 320.0)
    np.testing.assert_allclose(_gradient(name, solve, values), _central(solve, values), rtol=2e-6)


@pytest.mark.parametrize("name", BACKENDS)
def test_heat_live_dirichlet_with_element_heat_source(name):
    """An ElementHeatSource stays NumPy while other inputs are live."""
    source = ElementHeatSource(MESH, np.linspace(1.0, 40.0, MESH.num_triangles))
    right = [int(i) for i in MESH.boundary["right"]]

    def solve(t0, t1):
        r = solve_steady_heat(MESH, conductivity=3.0, heat_source=source,
                              dirichlet={**{i: t0 for i in LEFT}, **{i: t1 for i in right}})
        return r.heat_flux[:, 0].sum()
    values = (310.0, 290.0)
    np.testing.assert_allclose(_gradient(name, solve, values), _central(solve, values), rtol=1e-6)


# -- electric ------------------------------------------------------------------

def _series(sigma0, sigma1, v0, v1):
    mesh = layered_rectangle_mesh([0.3, 1.0], 0.5, [2, 5], 3)
    left = {int(i): v0 for i in mesh.boundary["left"]}
    right = {int(i): v1 for i in mesh.boundary["right"]}
    return solve_steady_electric(mesh, conductivity={"layer0": sigma0, "layer1": sigma1},
                                 dirichlet=left | right)


ELECTRIC_FIELDS = ("potential", "electric_field", "current_density", "conductivity", "joule_heating",
                   "joule_load", "reaction", "prescribed_outward_load", "residual")


@pytest.mark.parametrize("name", BACKENDS)
def test_electric_values_match_numpy(name):
    values = (2.0, 7.0, 1.5, -0.5)
    reference, live = _series(*values), _series(*_live(name, values))
    for field in ELECTRIC_FIELDS:
        expected = getattr(reference, field)
        np.testing.assert_allclose(_numbers(getattr(live, field)), expected, rtol=1e-12,
                                   atol=1e-12 * max(1.0, np.max(abs(expected))))
    for field in ("joule_power_per_length", "supplied_power_per_length"):
        assert abs(float(_numbers(getattr(live, field))) - getattr(reference, field)) <= 1e-12 * getattr(reference, field)


@pytest.mark.parametrize("name", BACKENDS)
def test_series_joule_power_matches_closed_form(name):
    """Two layers in series: P = dV^2 H / (L0/s0 + L1/s1) per metre, exact for P1."""
    L0, L1, H = 0.3, 0.7, 0.5
    values = (2.0, 7.0, 1.5, -0.5)

    def closed(s0, s1, v0, v1):
        return (v0 - v1)**2 * H / (L0 / s0 + L1 / s1)
    assert abs(_series(*values).joule_power_per_length - closed(*values)) < 1e-12 * closed(*values)
    s0, s1, v0, v1 = values
    R = L0 / s0 + L1 / s1
    dv = v0 - v1
    exact = [dv**2 * H * L0 / (s0**2 * R**2), dv**2 * H * L1 / (s1**2 * R**2),
             2 * dv * H / R, -2 * dv * H / R]
    got = _gradient(name, lambda *v: _series(*v).joule_power_per_length, values)
    np.testing.assert_allclose(got, exact, rtol=1e-10)


@pytest.mark.parametrize("name", BACKENDS)
def test_electric_neumann_current_and_reference_potential(name):
    """A current-driven component: outward current callback and gauge potential are live."""
    left = int(MESH.boundary["left"][0])

    def solve(j, gauge, sigma):
        def current(points, normals):
            y = points[:, 1] if not hasattr(j, "shape") else _wrap(name, points[:, 1])
            return j * (y - 0.25)                    # zero net current on the edge
        r = solve_steady_electric(MESH, conductivity=sigma, dirichlet={},
                                  outward_current={"right": current, "left": lambda p, n: -0.0 * p[:, 0]},
                                  reference_potential={left: gauge})
        return (r.potential**2).mean() + r.joule_power_per_length
    values = (3.0, 0.2, 2.5)
    np.testing.assert_allclose(_gradient(name, solve, values), _central(solve, values), rtol=2e-6)


# -- refusals ------------------------------------------------------------------

def test_jit_is_refused_with_a_clear_error():
    jax = _jax()
    with pytest.raises(TracedValueError, match="outside jax.jit"):
        jax.jit(lambda k: _heat(k, *HEAT[1:]).temperature)(jax.numpy.asarray(2.0))


def test_single_precision_jax_is_refused():
    jax = _jax()
    jax.config.update("jax_enable_x64", False)
    try:
        k = jax.numpy.asarray(2.0)
        with pytest.raises(ValueError, match="jax_enable_x64"):
            _heat(k, *HEAT[1:])
    finally:
        jax.config.update("jax_enable_x64", True)


def test_mixing_jax_and_torch_is_refused():
    jax, torch = _jax(), _torch()
    with pytest.raises(TypeError, match="namespaces"):
        solve_steady_heat(MESH, conductivity=jax.numpy.asarray(2.0),
                          dirichlet={i: torch.tensor(300.0, dtype=torch.float64) for i in LEFT})


@pytest.mark.parametrize("name", BACKENDS)
def test_numpy_containers_and_couplings_refuse_live_values(name):
    from galerkin.joule_heating import solve_steady_joule_heat
    import galerkin.thermal_mechanical as workflow
    right = [int(i) for i in MESH.boundary["right"]]
    with pytest.raises(TypeError, match="cut the derivative"):
        ElementHeatSource(MESH, _wrap(name, np.ones(MESH.num_triangles)))
    (sigma,) = _live(name, [3.0])
    bc = {**{i: 1.0 for i in LEFT}, **{i: 0.0 for i in right}}
    with pytest.raises(TypeError, match="cut the derivative"):       # live Joule source
        solve_steady_joule_heat(MESH, electrical_result=solve_steady_electric(MESH, conductivity=sigma, dirichlet=bc),
                                conductivity=2.0, dirichlet={i: 300.0 for i in LEFT})
    (k,) = _live(name, [2.0])
    with pytest.raises(TypeError, match="cut the derivative"):       # live thermal input
        solve_steady_joule_heat(MESH, electrical_result=solve_steady_electric(MESH, conductivity=3.0, dirichlet=bc),
                                conductivity=k, dirichlet={i: 300.0 for i in LEFT})
    (q,) = _live(name, [5.0])
    with pytest.raises(workflow.WorkflowStageError, match="cut the derivative"):
        workflow.solve_steady_thermoelasticity(
            MESH, units={"length": "m", "temperature": "K"}, conductivity=10.0,
            thermal_dirichlet={i: 313.15 for i in LEFT}, heat_source=lambda p: q * _wrap(name, 1.0 + p[:, 0]),
            young_modulus=70e9, poisson_ratio=0.3, plane="strain", thermal_expansion_per_k=12e-6,
            reference_temperature_k=293.15, mechanical_dirichlet={(0, 0): 0.0, (0, 1): 0.0, (3, 1): 0.0})


@pytest.mark.parametrize("name", [None, *BACKENDS])
def test_a_singular_heat_or_electric_system_is_one_value_error(name):
    """Conductivity 5e-324: the stiffness is a few subnormal ulps (JAX flushes them to zero), too
    small for SuperLU to factor, so every library reports the same singular system."""
    k = 5e-324 if name is None else _wrap(name, 5e-324)
    with pytest.raises(ValueError, match="^singular or ill-conditioned constrained heat system$"):
        solve_steady_heat(MESH, conductivity=k, dirichlet={i: 300.0 for i in LEFT}, heat_source=1.0)
    right = [int(i) for i in MESH.boundary["right"]]
    with pytest.raises(ValueError, match="^singular or ill-conditioned electric system$"):
        solve_steady_electric(MESH, conductivity=k,
                              dirichlet={**{i: 0.0 for i in LEFT}, **{i: 1.0 for i in right}})

