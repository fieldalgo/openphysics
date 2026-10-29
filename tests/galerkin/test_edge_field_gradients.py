# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""eval_edge_field on JAX and PyTorch edge dofs.

The field must match the NumPy evaluation for real and complex dofs, its
derivative with respect to the dofs must match central differences of the
NumPy evaluation, and a waveguide mode solved with a live permittivity must
carry its derivative through eval_edge_field into a gauge-free quantity of the
field. JAX without double precision and dofs of the wrong length are refused.
JAX and PyTorch cases skip when the library is absent; the CI job that installs
them first checks that both import.
"""
import numpy as np
import pytest

from galerkin import EdgeSpace, eval_edge_field, rectangle_mesh, solve_modes

BACKENDS = ["jax", "torch"]
MESH = rectangle_mesh(2.0, 1.5, 6, 5)
SPACE = EdgeSpace(MESH)
RNG = np.random.default_rng(0)
DOFS_RE = RNG.standard_normal(SPACE.num_edges)
DOFS_IM = RNG.standard_normal(SPACE.num_edges)
WEIGHTS = RNG.standard_normal((MESH.num_triangles, 2))


def _jax():
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    return jax


def _torch():
    return pytest.importorskip("torch")


def _library(name):
    return _jax().numpy if name == "jax" else _torch()


def _numbers(a):
    return a.detach().numpy() if hasattr(a, "detach") else np.asarray(a)


def _lifted(name, value):
    """A NumPy constant as an array of ``name`` (PyTorch does not mix tensors with NumPy arrays)."""
    return _library(name).asarray(value)


def _live(name, values, *, grad=False):
    if name == "jax":
        jnp = _jax().numpy
        return [jnp.asarray(v, dtype=jnp.float64) for v in values]
    torch = _torch()
    return [torch.tensor(v, dtype=torch.float64, requires_grad=grad) for v in values]


def _gradient(name, objective, values):
    if name == "jax":
        return [np.asarray(g) for g in _jax().grad(lambda v: objective(*v))(_live("jax", values))]
    leaves = _live("torch", values, grad=True)
    objective(*leaves).backward()
    return [np.zeros(x.shape) if x.grad is None else x.grad.numpy() for x in leaves]   # None: unused


def _central(objective, values, rel=1e-6):
    """Central differences of ``objective`` with respect to every entry of every value."""
    out = []
    for i, v in enumerate(values):
        v = np.asarray(v, dtype=float)
        grad = np.empty(v.size)
        for k in range(v.size):
            h = rel * max(1.0, abs(v.flat[k]))
            up, down = [np.array(x, dtype=float) for x in values], [np.array(x, dtype=float) for x in values]
            up[i].flat[k] += h
            down[i].flat[k] -= h
            grad[k] = (float(objective(*up)) - float(objective(*down))) / (2 * h)
        out.append(grad.reshape(v.shape))
    return out


def _dofs(kind, re, im):
    return re if kind == "real" else re + 1j * im


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("kind", ["real", "complex"])
def test_values_match_numpy(name, kind):
    reference = eval_edge_field(SPACE, _dofs(kind, DOFS_RE, DOFS_IM))
    re, im = _live(name, [DOFS_RE, DOFS_IM])
    got = eval_edge_field(SPACE, _dofs(kind, re, im))
    assert type(got).__module__.split(".")[0] in ("jax", "jaxlib", "torch")
    assert _numbers(got).dtype == reference.dtype == (np.float64 if kind == "real" else np.complex128)
    assert tuple(got.shape) == reference.shape == (MESH.num_triangles, 2)
    np.testing.assert_allclose(_numbers(got), reference, rtol=1e-12, atol=1e-12 * np.max(abs(reference)))


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("kind", ["real", "complex"])
def test_gradients_match_central_differences(name, kind):
    """sum(|E|^2 w) with w ~ N(0, 1), with respect to every real (and imaginary) part of the dofs."""
    lib = _library(name)

    def live(re, im):
        E = eval_edge_field(SPACE, _dofs(kind, re, im))
        return lib.sum(lib.abs(E) ** 2 * _lifted(name, WEIGHTS))

    def numbers(re, im):
        E = eval_edge_field(SPACE, _dofs(kind, re, im))
        return np.sum(np.abs(E) ** 2 * WEIGHTS)
    got = _gradient(name, live, [DOFS_RE, DOFS_IM])
    expected = _central(numbers, [DOFS_RE, DOFS_IM])
    scale = max(np.max(abs(g)) for g in expected)
    for g, e, part in zip(got, expected, ("real part", "imaginary part")):
        np.testing.assert_allclose(g, e, rtol=1e-6, atol=1e-8 * scale, err_msg=part)
    if kind == "real":
        assert not np.any(got[1]), "the imaginary part is unused for real dofs"


# A waveguide with a live core permittivity: the field of its fundamental mode
# through eval_edge_field. The objective, a weighted share of |E_t|^2, does not
# depend on the mode's complex scale, so its derivative is gauge-free.
GUIDE = rectangle_mesh(2.0, 1.5, 12, 9)
GUIDE_CENTROIDS = GUIDE.nodes[GUIDE.triangles].mean(axis=1)
CORE = ((abs(GUIDE_CENTROIDS[:, 0] - 1.0) < 0.45)
        & (abs(GUIDE_CENTROIDS[:, 1] - 0.75) < 0.3)).astype(float)
SHARE = np.exp(-((GUIDE_CENTROIDS[:, 0] - 1.1) ** 2 + (GUIDE_CENTROIDS[:, 1] - 0.7) ** 2))
K0, N_TARGET = 2 * np.pi / 0.8, 1.45


def _round_trip(s, xp, name=None):
    core, share = (CORE, SHARE) if name is None else (_lifted(name, CORE), _lifted(name, SHARE))
    eps = 1.0 + 1.25 * s * core
    _, space, et, _ = solve_modes(GUIDE, eps, K0, N_TARGET, num_modes=1)
    a = xp.sum(xp.abs(eval_edge_field(space, et[0])) ** 2, axis=1)
    return xp.sum(a * share) / xp.sum(a)


@pytest.mark.parametrize("name", BACKENDS)
def test_solve_modes_field_round_trip_matches_central_differences(name):
    lib = _library(name)
    value = _round_trip(_live(name, [1.0])[0], lib, name)
    np.testing.assert_allclose(_numbers(value), _round_trip(1.0, np), rtol=1e-12)
    got = _gradient(name, lambda s: _round_trip(s, lib, name), [1.0])[0]
    expected = _central(lambda s: _round_trip(float(s), np), [1.0], rel=1e-5)[0]
    np.testing.assert_allclose(got, expected, rtol=1e-6)
    assert abs(float(expected)) > 1e-3, "the objective must depend on the permittivity"


@pytest.mark.parametrize("name", BACKENDS)
def test_single_precision_values_are_promoted(name):
    """A float32 or complex64 value is computed in float64 or complex128."""
    if name == "jax":
        jnp = _jax().numpy
        re, im = jnp.asarray(DOFS_RE, dtype=jnp.float32), jnp.asarray(DOFS_IM, dtype=jnp.float32)
    else:
        torch = _torch()
        re, im = torch.tensor(DOFS_RE, dtype=torch.float32), torch.tensor(DOFS_IM, dtype=torch.float32)
    for kind, expected in (("real", np.float64), ("complex", np.complex128)):
        got = _numbers(eval_edge_field(SPACE, _dofs(kind, re, im)))
        reference = eval_edge_field(SPACE, _dofs(kind, _numbers(re).astype(float), _numbers(im).astype(float)))
        assert got.dtype == expected, kind
        np.testing.assert_allclose(got, reference, rtol=1e-12, atol=1e-12 * np.max(abs(reference)))


def test_single_precision_jax_is_refused():
    jax = _jax()
    jax.config.update("jax_enable_x64", False)
    try:
        with pytest.raises(ValueError, match="jax_enable_x64"):
            eval_edge_field(SPACE, jax.numpy.asarray(DOFS_RE))
    finally:
        jax.config.update("jax_enable_x64", True)


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("size", [SPACE.num_edges - 1, SPACE.num_edges + 1])
def test_dofs_of_another_length_are_refused(name, size):
    """JAX would clamp an index past the end instead of failing; the length is checked first."""
    dofs = _live(name, [np.ones(size)])[0]
    with pytest.raises(ValueError, match="one value per edge"):
        eval_edge_field(SPACE, dofs)
