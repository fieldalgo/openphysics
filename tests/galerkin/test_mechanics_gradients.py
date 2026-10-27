# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Elasticity and thermoelasticity on JAX and PyTorch values.

Values must match the NumPy solve. Derivatives are checked against closed forms
that P1 reproduces exactly (a bar under end traction; free thermal expansion)
and against central differences of the NumPy solve for every kind of live
input. The NumPy path is covered by the existing suites, unchanged. JAX and
PyTorch cases skip when the library is absent; the CI job that installs them
first checks that both import.
"""
import numpy as np
import pytest

from galerkin.core.backend import TracedValueError
from galerkin.elasticity import solve_elasticity
from galerkin.mesh import layered_rectangle_mesh, rectangle_mesh
from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity


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


def _central(objective, values, rel=1e-5):
    out = []
    for i, v in enumerate(values):
        h = rel * abs(v)
        up, down = list(values), list(values)
        up[i] += h
        down[i] -= h
        out.append((float(objective(*up)) - float(objective(*down))) / (2 * h))
    return out


def _assert_matches(live, reference, fields):
    for field in fields:
        expected = np.asarray(getattr(reference, field))
        got = getattr(live, field)
        assert type(got).__module__.split(".")[0] in ("jax", "jaxlib", "torch"), field
        np.testing.assert_allclose(_numbers(got), expected, rtol=1e-12,
                                   atol=1e-12 * max(np.max(abs(expected)), 1e-300), err_msg=field)


BACKENDS = ["jax", "torch"]
MESH = rectangle_mesh(1.0, 0.5, 6, 4)
LEFT = [int(i) for i in MESH.boundary["left"]]
RIGHT = np.asarray(MESH.boundary["right"], dtype=int)


# -- elasticity ----------------------------------------------------------------

def _elastic(e, nu, ux, fy, tx, *, name=None):
    def body(points):
        return fy * _wrap(name, np.column_stack([np.zeros(len(points)), 1.0 + points[:, 0]]))

    def shear(points, normals):
        return tx * _wrap(name, np.column_stack([np.zeros(len(points)), points[:, 1]]))
    return solve_elasticity(MESH, young_modulus=e, poisson_ratio=nu, plane="stress",
                            dirichlet={**{(i, 0): ux for i in LEFT}, (LEFT[0], 1): 0.0},
                            body_force=body, traction={"right": [tx, 0.0], "top": shear})


ELASTIC = (2e3, 0.3, 1e-3, -5.0, 7.0)
ELASTIC_FIELDS = ("displacement", "strain", "stress", "load", "reaction", "residual")


@pytest.mark.parametrize("name", BACKENDS)
def test_elasticity_values_match_numpy(name):
    _assert_matches(_elastic(*_live(name, ELASTIC), name=name), _elastic(*ELASTIC), ELASTIC_FIELDS)


@pytest.mark.parametrize("name", BACKENDS)
def test_elasticity_gradients_match_central_differences(name):
    def objective(*v, live=None):
        r = _elastic(*v, name=live)
        return (r.displacement**2).sum() * 1e6 + (r.stress[:, 2]**2).mean()
    got = _gradient(name, lambda *v: objective(*v, live=name), ELASTIC)
    np.testing.assert_allclose(got, _central(objective, ELASTIC), rtol=1e-6)


@pytest.mark.parametrize("name", BACKENDS)
def test_bar_under_end_traction_matches_the_closed_form(name):
    """Plane stress bar, x held on the left: u_x(L) = sigma L / E and u_y = -nu sigma y / E."""
    length, corner = 1.0, int(np.flatnonzero((MESH.nodes[:, 0] == 0) & (MESH.nodes[:, 1] == 0))[0])

    def tip(e, nu, sigma):
        r = solve_elasticity(MESH, young_modulus=e, poisson_ratio=nu, plane="stress",
                             dirichlet={**{(i, 0): 0.0 for i in LEFT}, (corner, 1): 0.0},
                             traction={"right": [sigma, 0.0]})
        top_right = r.displacement[RIGHT[np.argmax(MESH.nodes[RIGHT, 1])]]
        return top_right[0] + top_right[1]          # sigma L / E - nu sigma H / E
    e, nu, sigma, height = 2e3, 0.3, 7.0, 0.5
    assert abs(float(_numbers(tip(e, nu, sigma))) - sigma * (length - nu * height) / e) < 1e-12
    exact = [-sigma * (length - nu * height) / e**2, -sigma * height / e, (length - nu * height) / e]
    np.testing.assert_allclose(_gradient(name, tip, (e, nu, sigma)), exact, rtol=1e-10)


@pytest.mark.parametrize("name", BACKENDS)
def test_elasticity_region_tables(name):
    mesh = layered_rectangle_mesh([0.4, 1.0], 0.5, [3, 4], 3)
    left = [int(i) for i in mesh.boundary["left"]]

    def objective(e0, e1, nu1, tx):
        r = solve_elasticity(mesh, young_modulus={"layer0": e0, "layer1": e1},
                             poisson_ratio={"layer0": 0.25, "layer1": nu1}, plane="strain",
                             dirichlet={**{(i, 0): 0.0 for i in left}, (left[0], 1): 0.0},
                             traction={"right": (tx, 0.5 * tx)})
        return (r.displacement**2).sum() * 1e6
    values = (2e3, 5e3, 0.35, 7.0)
    np.testing.assert_allclose(_gradient(name, objective, values), _central(objective, values), rtol=1e-6)


# -- thermoelasticity ----------------------------------------------------------

def _thermo(tref, alpha, e, nu, tx, *, regional=False, plane="strain"):
    mesh = layered_rectangle_mesh([0.4, 1.0], 0.5, [3, 4], 3) if regional else MESH
    table = (lambda a, b: {"layer0": a, "layer1": b}) if regional else (lambda a, b: a)
    snapshot = freeze_temperature(mesh, 300.0 + 40.0 * mesh.nodes[:, 0] + 10.0 * mesh.nodes[:, 1]**2)
    return solve_thermoelasticity(
        mesh, snapshot, reference_temperature_k=tref, thermal_expansion_per_k=table(alpha, 2 * alpha),
        young_modulus=table(e, 1.5 * e), poisson_ratio=nu, plane=plane,
        dirichlet={(0, 0): 0.0, (0, 1): 0.0, (3, 1): 0.0},
        body_force=(0.0, -3.0), traction={"right": [tx, 0.0]})


THERMO = (293.15, 1.2e-5, 7e4, 0.3, 50.0)
THERMO_FIELDS = ("displacement", "total_strain", "thermal_strain", "elastic_strain", "stress",
                 "sigma_zz", "epsilon_zz", "load_external", "load_thermal", "reaction", "residual",
                 "physical_elastic_energy", "load_body", "load_traction")


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("regional", [False, True])
@pytest.mark.parametrize("plane", ["strain", "stress"])
def test_thermoelasticity_values_and_gradients(name, regional, plane):
    _assert_matches(_thermo(*_live(name, THERMO), regional=regional, plane=plane),
                    _thermo(*THERMO, regional=regional, plane=plane), THERMO_FIELDS)

    def objective(*v):
        r = _thermo(*v, regional=regional, plane=plane)
        return r.physical_elastic_energy * 1e3 + (r.displacement**2).sum() * 1e6
    np.testing.assert_allclose(_gradient(name, objective, THERMO), _central(objective, THERMO),
                               rtol=2e-6)


@pytest.mark.parametrize("name", BACKENDS)
def test_free_thermal_expansion_matches_the_closed_form(name):
    """Uniform rise, rigid-body supports only, plane stress: u_x(L) = alpha (T - Tref) L, no stress."""
    corner = int(np.flatnonzero((MESH.nodes[:, 0] == 0) & (MESH.nodes[:, 1] == 0))[0])
    right_bottom = int(np.flatnonzero((MESH.nodes[:, 0] == 1) & (MESH.nodes[:, 1] == 0))[0])
    snapshot = freeze_temperature(MESH, np.full(MESH.num_nodes, 340.0))

    def tip(tref, alpha, e):
        r = solve_thermoelasticity(MESH, snapshot, reference_temperature_k=tref,
                                   thermal_expansion_per_k=alpha, young_modulus=e, poisson_ratio=0.3,
                                   plane="stress",
                                   dirichlet={(corner, 0): 0.0, (corner, 1): 0.0, (right_bottom, 1): 0.0})
        return r.displacement[right_bottom, 0]
    tref, alpha, e = 300.0, 1.2e-5, 7e4
    assert abs(float(_numbers(tip(tref, alpha, e))) - alpha * (340.0 - tref)) < 1e-15
    np.testing.assert_allclose(_gradient(name, tip, (tref, alpha, e)), [-alpha, 340.0 - tref, 0.0],
                               rtol=1e-10, atol=1e-18)


# -- refusals ------------------------------------------------------------------

def test_jit_is_refused():
    jax = _jax()
    with pytest.raises(TracedValueError):
        jax.jit(lambda e: _elastic(e, *ELASTIC[1:]).displacement)(jax.numpy.asarray(2e3))


@pytest.mark.parametrize("name", BACKENDS)
def test_temperature_snapshots_stay_numpy(name):
    """The snapshot is an immutable, hashed NumPy record: a live field is refused, not cut."""
    with pytest.raises(TypeError, match="cut the derivative"):
        freeze_temperature(MESH, _wrap(name, np.full(MESH.num_nodes, 300.0)))
