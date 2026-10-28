# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Waveguide modes on JAX and PyTorch values.

n_eff and both field arrays must match the NumPy solve. Eigenvalue derivatives
are checked against a closed form that the discretization satisfies exactly (a
homogeneous guide: (k0 n_eff)^2 = k0^2 eps mu - kc^2 with kc fixed by the mesh)
and, with the fields, against central differences of the NumPy solve for every
kind of live input: real and lossy materials, element arrays, coordinate
factors. Field derivatives are checked both in the returned gauge and through a
gauge-free quantity. A degenerate pair gives NaN derivatives and a warning while
the other modes keep theirs. JAX and PyTorch cases skip when the library is
absent; the CI job that installs them first checks that both import.
"""
import warnings

import numpy as np
import pytest

from galerkin import rectangle_mesh, solve_modes
from galerkin.core.backend import TracedValueError
from galerkin.mesh import Mesh
from galerkin.waveguide import DegenerateModeWarning


def _jax():
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    return jax


def _torch():
    return pytest.importorskip("torch")


def _numbers(a):
    return a.detach().numpy() if hasattr(a, "detach") else np.asarray(a)


def _library(name):
    if name is None:
        return np
    return _jax().numpy if name == "jax" else _torch()


def _live(name, values):
    if name == "jax":
        jnp = _jax().numpy
        return [jnp.asarray(v, dtype=jnp.float64) for v in values]
    torch = _torch()
    return [torch.tensor(v, dtype=torch.float64, requires_grad=True) for v in values]


def _gradient(name, objective, values):
    if name == "jax":
        return [float(g) for g in _jax().grad(lambda v: objective(*v))(_live("jax", values))]
    leaves = _live("torch", values)
    objective(*leaves).backward()
    return [float(x.grad) for x in leaves]


def _central(objective, values, rel=1e-6):
    out = []
    for i, v in enumerate(values):
        h = rel * abs(v)
        up, down = list(values), list(values)
        up[i] += h
        down[i] -= h
        out.append((float(objective(*up)) - float(objective(*down))) / (2 * h))
    return out


BACKENDS = ["jax", "torch"]
MESH = rectangle_mesh(2.0, 1.5, 12, 9)
CENTROID = MESH.nodes[MESH.triangles].mean(axis=1)
CORE = ((abs(CENTROID[:, 0] - 1.0) < 0.4) & (abs(CENTROID[:, 1] - 0.75) < 0.25)).astype(float)
# A complex stretch on the right quarter, as a PML would give, and a bend-like h.
FACTORS = np.ones((MESH.num_triangles, 3), dtype=complex)
FACTORS[CENTROID[:, 0] > 1.5, 0] = 1.0 - 0.3j
FACTORS[:, 2] = 1.0 + 0.02 * CENTROID[:, 0]


def _modes(core_index, clad_index, mu, k0, loss=0.0, *, name=None, factors=None):
    xp = _library(name)
    core = xp.asarray(CORE) if name != "torch" else xp.as_tensor(CORE)
    eps = core * (core_index**2 - 1j * loss) + (1 - core) * clad_index**2
    return solve_modes(MESH, eps, k0, 2.0, num_modes=4, mu_r=mu, coordinate_factors=factors)


def _gauge_free(result, i):
    """|E_z|^2 / |E_t|^2 in coefficient norms: independent of the field's scale and phase."""
    _, _, et, ez = result
    return (abs(ez[i])**2).sum() / (abs(et[i])**2).sum()


CASES = {"real": ((2.0, 1.44, 1.1, 2 * np.pi), None),
         "lossy": ((2.0, 1.44, 1.1, 2 * np.pi, 0.05), None),
         "factors": ((2.0, 1.44, 1.1, 2 * np.pi), FACTORS)}


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("case", CASES)
def test_values_match_numpy(name, case):
    values, factors = CASES[case]
    reference = _modes(*values, factors=factors)
    live = _modes(*_live(name, values), name=name, factors=factors)
    assert live[1] is not None and live[1].num_edges == reference[1].num_edges
    for got, expected, field in zip((live[0], live[2], live[3]), (reference[0], reference[2], reference[3]),
                                    ("n_eff", "et", "ez")):
        assert type(got).__module__.split(".")[0] in ("jax", "jaxlib", "torch"), field
        assert _numbers(got).dtype == expected.dtype, field
        np.testing.assert_allclose(_numbers(got), expected, rtol=1e-12,
                                   atol=1e-12 * np.max(abs(expected)), err_msg=field)


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("case", CASES)
def test_gradients_match_central_differences(name, case):
    """n_eff of two modes, a gauge-free field ratio and one raw component in the returned gauge."""
    values, factors = CASES[case]
    lib = _library(name)

    def objective(*v, live=None):
        r = _modes(*v, name=live, factors=factors)
        raw = r[3][0][int(np.argmax(MESH.nodes[:, 0] == 1.0))]
        return (lib.real(r[0][0]) + lib.real(r[0][1] * (1 - 10j)) + _gauge_free(r, 0) + _gauge_free(r, 1)
                + lib.real(raw) * 3 + lib.imag(raw) * 5)

    def numbers(*v):
        r = _modes(*v, factors=factors)
        raw = r[3][0][int(np.argmax(MESH.nodes[:, 0] == 1.0))]
        return (np.real(r[0][0]) + np.real(r[0][1] * (1 - 10j)) + _gauge_free(r, 0) + _gauge_free(r, 1)
                + np.real(raw) * 3 + np.imag(raw) * 5)
    got = _gradient(name, lambda *v: objective(*v, live=name), values)
    np.testing.assert_allclose(got, _central(numbers, values), rtol=2e-6, atol=1e-8)


@pytest.mark.parametrize("name", BACKENDS)
def test_element_arrays_match_a_directional_difference(name):
    """eps_r and mu_r as live per-element arrays: the gradient along a direction."""
    rng = np.random.default_rng(3)
    eps0 = CORE * 4.0 + (1 - CORE) * 1.44**2
    mu0 = np.full(MESH.num_triangles, 1.1)
    d_eps, d_mu = rng.uniform(-1, 1, (2, MESH.num_triangles))

    def objective(eps, mu, xp):
        r = solve_modes(MESH, eps, 2 * np.pi, 2.0, num_modes=3, mu_r=mu)
        return xp.real(r[0][0]) + xp.real(r[0][2]) + _gauge_free(r, 0)
    if name == "jax":
        jax = _jax()
        g_eps, g_mu = jax.grad(lambda e, m: objective(e, m, jax.numpy), argnums=(0, 1))(
            jax.numpy.asarray(eps0), jax.numpy.asarray(mu0))
    else:
        torch = _torch()
        e, m = (torch.tensor(a, requires_grad=True) for a in (eps0, mu0))
        objective(e, m, torch).backward()
        g_eps, g_mu = e.grad, m.grad
    got = float(np.dot(_numbers(g_eps), d_eps) + np.dot(_numbers(g_mu), d_mu))
    h = 1e-6
    expected = (objective(eps0 + h * d_eps, mu0 + h * d_mu, np)
                - objective(eps0 - h * d_eps, mu0 - h * d_mu, np)) / (2 * h)
    assert abs(got - expected) <= 2e-6 * abs(expected)


@pytest.mark.parametrize("name", BACKENDS)
def test_homogeneous_guide_matches_the_closed_form(name):
    """A filled PEC guide: n_eff^2 = eps mu - (kc / k0)^2 exactly, kc from the mesh alone."""
    mesh = rectangle_mesh(2.0, 1.0, 8, 5)
    eps, mu, k0 = 2.0, 1.3, 3.0
    n0 = solve_modes(mesh, eps, k0, np.sqrt(eps * mu), num_modes=3, mu_r=mu)[0]
    kc2 = k0**2 * (eps * mu - n0**2)
    for e, m, k in ((2.5, 1.0, 3.4), (1.7, 2.0, 2.1)):          # kc does not move
        n = solve_modes(mesh, e, k, np.sqrt(e * m), num_modes=3, mu_r=m)[0]
        np.testing.assert_allclose(k**2 * (e * m - n**2), kc2, rtol=1e-11)
    for i in range(3):
        def mode(e, m, k):
            return solve_modes(mesh, e, k, np.sqrt(eps * mu), num_modes=3, mu_r=m)[0][i]
        exact = [mu / (2 * n0[i]), eps / (2 * n0[i]), kc2[i] / (k0**3 * n0[i])]
        np.testing.assert_allclose(_gradient(name, mode, (eps, mu, k0)), exact, rtol=1e-9)


@pytest.mark.parametrize("eps", [2.0, 2.0 - 0.1j])
def test_complex_mu_matches_the_closed_form(eps):
    """NumPy inputs: a filled PEC guide sees only eps*mu, so a lossy mu_r counts as much as a lossy eps_r."""
    mesh = rectangle_mesh(2.0, 1.0, 8, 5)
    k0 = 3.0
    n_lossless = solve_modes(mesh, 2.6, k0, np.sqrt(2.6), num_modes=3, mu_r=1.0)[0]
    kc2 = k0**2 * (2.6 - n_lossless**2)                         # fixed by the mesh alone
    for mu in (1.3 - 0.05j, np.full(mesh.num_triangles, 1.3 - 0.05j)):
        n = solve_modes(mesh, eps, k0, np.sqrt(eps * 1.3).real, num_modes=3, mu_r=mu)[0]
        assert np.iscomplexobj(n)
        np.testing.assert_allclose(n**2, eps * (1.3 - 0.05j) - kc2 / k0**2, rtol=1e-10)


@pytest.mark.parametrize("name", BACKENDS)
def test_complex_scalars_made_from_a_live_value(name):
    """0-d complex eps_r and mu_r computed from a live real parameter: values and the closed-form derivative."""
    mesh = rectangle_mesh(2.0, 1.0, 8, 5)
    k0, t0 = 3.0, 0.7
    n_lossless = solve_modes(mesh, 2.6, k0, np.sqrt(2.6), num_modes=3, mu_r=1.0)[0]
    kc2 = k0**2 * (2.6 - n_lossless**2)

    def materials(t):
        return 2.0 - 0.1j * t, 1.3 - 0.05j * t

    def mode(t):
        eps, mu = materials(t)
        return solve_modes(mesh, eps, k0, 1.4, num_modes=3, mu_r=mu)[0]
    lib = _library(name)
    t = _live(name, [t0])[0]
    live = mode(t)
    expected = mode(t0)
    np.testing.assert_allclose(_numbers(live), expected, rtol=1e-12)
    eps, mu = materials(t0)
    np.testing.assert_allclose(expected**2, eps * mu - kc2 / k0**2, rtol=1e-10)
    for i in range(3):
        exact = (-0.1j * mu - 0.05j * eps) / (2 * expected[i])  # d n / dt from n^2 = eps mu - kc^2/k0^2
        got = _gradient(name, lambda s: lib.real(mode(s)[i]) + 3 * lib.imag(mode(s)[i]), [t0])[0]
        np.testing.assert_allclose(got, exact.real + 3 * exact.imag, rtol=1e-9)


# -- degenerate modes ----------------------------------------------------------

def _square_mesh(cells, size):
    """Each cell split into four triangles by its centre: the mesh has the square's symmetry."""
    g = np.linspace(0.0, size, cells + 1)
    corners = np.array([(x, y) for y in g for x in g])
    centres = np.array([((g[i] + g[i + 1]) / 2, (g[j] + g[j + 1]) / 2)
                        for j in range(cells) for i in range(cells)])
    triangles = []
    for j in range(cells):
        for i in range(cells):
            a, b = j * (cells + 1) + i, j * (cells + 1) + i + 1
            c, d = b + cells + 1, a + cells + 1
            centre = len(corners) + j * cells + i
            triangles += [[a, b, centre], [b, c, centre], [c, d, centre], [d, a, centre]]
    wall = np.flatnonzero((corners == 0).any(axis=1) | (corners == size).any(axis=1))
    return Mesh(np.vstack([corners, centres]), np.array(triangles), {"wall": wall})


@pytest.mark.parametrize("name", BACKENDS)
def test_degenerate_pair_has_nan_derivatives_and_others_keep_theirs(name):
    mesh = _square_mesh(10, 2.0)
    centroid = mesh.nodes[mesh.triangles].mean(axis=1)
    core = (abs(centroid - 1.0) < 0.41).all(axis=1).astype(float)
    lib = _library(name)

    def run(nc, live=None):
        c = core if live is None else (lib.asarray(core) if live == "jax" else lib.as_tensor(core))
        return solve_modes(mesh, c * nc**2 + (1 - c) * 1.44**2, 2 * np.pi, 2.0, num_modes=4)
    n_eff = run(2.0)[0]
    assert abs(n_eff[0] - n_eff[1]) <= 1e-12 * n_eff[0] and n_eff[1] - n_eff[2] > 0.1
    with pytest.warns(DegenerateModeWarning, match=r"modes \[0, 1\]"):
        live = run(*_live(name, [2.0]), live=name)
    np.testing.assert_allclose(_numbers(live[0]), n_eff, rtol=1e-12)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DegenerateModeWarning)
        assert np.isnan(_gradient(name, lambda nc: lib.real(run(nc, name)[0][0]), [2.0])[0])
        assert np.isnan(_gradient(name, lambda nc: _gauge_free(run(nc, name), 1), [2.0])[0])
        got = _gradient(name, lambda nc: lib.real(run(nc, name)[0][2]) + _gauge_free(run(nc, name), 3),
                        [2.0])
    expected = _central(lambda nc: run(nc)[0][2] + _gauge_free(run(nc), 3), [2.0])
    np.testing.assert_allclose(got, expected, rtol=2e-6)


@pytest.mark.parametrize("name", BACKENDS)
def test_a_pair_cut_by_num_modes_is_still_degenerate(name):
    """num_modes=1 returns one member of the pair: its partner, not returned, still counts."""
    mesh = _square_mesh(10, 2.0)
    core = (abs(mesh.nodes[mesh.triangles].mean(axis=1) - 1.0) < 0.41).all(axis=1).astype(float)
    lib = _library(name)

    def run(nc):
        c = lib.asarray(core) if name == "jax" else lib.as_tensor(core)
        return solve_modes(mesh, c * nc**2 + (1 - c) * 1.44**2, 2 * np.pi, 2.0, num_modes=1)
    with pytest.warns(DegenerateModeWarning, match=r"modes \[0\]"):
        assert np.isnan(_gradient(name, lambda nc: _gauge_free(run(nc), 0), [2.0])[0])


# -- refusals ------------------------------------------------------------------

@pytest.mark.parametrize("name", BACKENDS)
def test_live_coordinate_factors_are_refused(name):
    lib = _library(name)
    factors = lib.asarray(FACTORS) if name == "jax" else lib.as_tensor(FACTORS)
    with pytest.raises(TypeError, match="coordinate_factors"):
        solve_modes(MESH, 2.0, 2 * np.pi, 2.0, num_modes=2, coordinate_factors=factors)


def test_jit_is_refused():
    jax = _jax()
    with pytest.raises(TracedValueError):
        jax.jit(lambda nc: _modes(nc, 1.44, 1.0, 2 * np.pi, name="jax")[0])(jax.numpy.asarray(2.0))
