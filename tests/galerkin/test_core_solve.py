# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""galerkin.core.solve: values against dense solves, gradients against independent references.

The hand-written adjoint is checked against each library's own automatic
differentiation of its dense ``linalg.solve`` (an independent derivation of the
same derivative) and against central finite differences of the NumPy solve.
JAX and PyTorch cases skip when the library is absent; the CI job that installs
them first checks that both import.
"""
import numpy as np
import pytest

from galerkin.core.solve import solve
from galerkin.core.sparse import CooMatrix


def _jax():
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    return jax


def _torch():
    return pytest.importorskip("torch")


def _system(n=7, complex_=False, seed=0):
    """A nonsymmetric sparse pattern with duplicate entries and a dominant diagonal."""
    rng = np.random.default_rng(seed)
    rows = np.concatenate([np.arange(n), rng.integers(0, n, 3 * n), [0, 0]])
    cols = np.concatenate([np.arange(n), rng.integers(0, n, 3 * n), [0, 0]])
    values = rng.standard_normal(rows.size)
    values[:n] += 2.0 * n
    b = rng.standard_normal(n)
    if complex_:
        values = values + 1j * rng.standard_normal(rows.size)
        b = b + 1j * rng.standard_normal(n)
    return rows, cols, values, b


def _dense(rows, cols, values, n):
    out = np.zeros((n, n), dtype=np.result_type(values, np.float64))
    np.add.at(out, (rows, cols), values)
    return out


@pytest.mark.parametrize("complex_", [False, True])
@pytest.mark.parametrize("columns", [None, 3])
def test_numpy_matches_dense_solve(complex_, columns):
    rows, cols, values, b = _system(complex_=complex_)
    n = b.size
    if columns:
        b = np.stack([b * (k + 1) for k in range(columns)], axis=1)
    x = solve(CooMatrix(rows, cols, values, (n, n)), b)
    expected = np.linalg.solve(_dense(rows, cols, values, n), b)
    np.testing.assert_allclose(x, expected, rtol=1e-13, atol=1e-14)


def test_numpy_real_matrix_complex_rhs():
    rows, cols, values, b = _system()
    b = b + 1j * np.arange(b.size)
    x = solve(CooMatrix(rows, cols, values, (b.size, b.size)), b)
    np.testing.assert_allclose(x, np.linalg.solve(_dense(rows, cols, values, b.size), b), rtol=1e-13, atol=1e-14)


def test_refuses_bad_shapes_and_singular_matrices():
    rows, cols, values, b = _system()
    n = b.size
    with pytest.raises(ValueError, match="square"):
        solve(CooMatrix(rows, cols, values, (n, n + 1)), b)
    with pytest.raises(ValueError, match="right-hand side"):
        solve(CooMatrix(rows, cols, values, (n, n)), np.ones(n + 1))
    with pytest.raises(ValueError, match="singular"):
        solve(CooMatrix(np.array([0, 1]), np.array([0, 0]), np.ones(2), (2, 2)), np.ones(2))


def _objective_weights(n, complex_):
    rng = np.random.default_rng(11)
    w = rng.standard_normal(n)
    return w + 1j * rng.standard_normal(n) if complex_ else w


def _numpy_objective(rows, cols, values, b, w):
    x = np.linalg.solve(_dense(rows, cols, values, b.size), b)
    return float(np.real(np.sum(w * x)) + np.sum(np.abs(x) ** 2))


@pytest.mark.parametrize("complex_", [False, True])
def test_jax_gradient_matches_dense_autodiff(complex_):
    jax = _jax()
    jnp = jax.numpy
    rows, cols, values, b = _system(complex_=complex_)
    n = b.size
    w = jnp.asarray(_objective_weights(n, complex_))

    def objective(x):
        return jnp.real(jnp.sum(w * x)) + jnp.sum(jnp.abs(x) ** 2)

    def ours(v, rhs):
        return objective(solve(CooMatrix(rows, cols, v, (n, n)), rhs))

    def reference(v, rhs):
        dense = jnp.zeros((n, n), dtype=v.dtype).at[rows, cols].add(v)
        return objective(jnp.linalg.solve(dense, rhs))

    args = (jnp.asarray(values), jnp.asarray(b))
    got, expected = jax.grad(ours, argnums=(0, 1))(*args), jax.grad(reference, argnums=(0, 1))(*args)
    for g, e in zip(got, expected):
        np.testing.assert_allclose(np.asarray(g), np.asarray(e), rtol=1e-11, atol=1e-13)
    jitted = jax.jit(jax.grad(ours, argnums=(0, 1)))(*args)
    for g, e in zip(jitted, expected):
        np.testing.assert_allclose(np.asarray(g), np.asarray(e), rtol=1e-11, atol=1e-13)


@pytest.mark.parametrize("complex_", [False, True])
def test_torch_gradient_matches_dense_autodiff(complex_):
    torch = _torch()
    rows, cols, values, b = _system(complex_=complex_)
    n = b.size
    w = torch.as_tensor(_objective_weights(n, complex_))

    def objective(x):
        return torch.real(torch.sum(w * x)) + torch.sum(torch.abs(x) ** 2)

    def leaves():
        return (torch.as_tensor(values).requires_grad_(), torch.as_tensor(b).requires_grad_())

    v, rhs = leaves()
    objective(solve(CooMatrix(rows, cols, v, (n, n)), rhs)).backward()
    v_ref, rhs_ref = leaves()
    dense = torch.zeros((n, n), dtype=v_ref.dtype).index_put((torch.as_tensor(rows), torch.as_tensor(cols)),
                                                              v_ref, accumulate=True)
    objective(torch.linalg.solve(dense, rhs_ref)).backward()
    np.testing.assert_allclose(v.grad.numpy(), v_ref.grad.numpy(), rtol=1e-11, atol=1e-13)
    np.testing.assert_allclose(rhs.grad.numpy(), rhs_ref.grad.numpy(), rtol=1e-11, atol=1e-13)


@pytest.mark.parametrize("name", ["jax", "torch"])
def test_gradient_matches_central_differences(name):
    """A real system against finite differences of the NumPy solve, no autodiff involved."""
    rows, cols, values, b = _system(seed=4)
    n = b.size
    w = _objective_weights(n, False)
    if name == "jax":
        jax = _jax()
        jnp = jax.numpy

        def ours(v, rhs):
            x = solve(CooMatrix(rows, cols, v, (n, n)), rhs)
            return jnp.sum(w * x) + jnp.sum(x ** 2)
        grad_v, grad_b = (np.asarray(g) for g in jax.grad(ours, argnums=(0, 1))(jnp.asarray(values), jnp.asarray(b)))
    else:
        torch = _torch()
        v, rhs = torch.as_tensor(values).requires_grad_(), torch.as_tensor(b).requires_grad_()
        x = solve(CooMatrix(rows, cols, v, (n, n)), rhs)
        (torch.sum(torch.as_tensor(w) * x) + torch.sum(x ** 2)).backward()
        grad_v, grad_b = v.grad.numpy(), rhs.grad.numpy()
    h = 1e-6
    for k in range(values.size):
        step = np.zeros_like(values)
        step[k] = h
        fd = (_numpy_objective(rows, cols, values + step, b, w) - _numpy_objective(rows, cols, values - step, b, w)) / (2 * h)
        assert abs(grad_v[k] - fd) <= 1e-7 * max(1.0, abs(fd))
    for k in range(n):
        step = np.zeros(n)
        step[k] = h
        fd = (_numpy_objective(rows, cols, values, b + step, w) - _numpy_objective(rows, cols, values, b - step, w)) / (2 * h)
        assert abs(grad_b[k] - fd) <= 1e-7 * max(1.0, abs(fd))


def test_jax_many_right_hand_sides_and_vmap():
    jax = _jax()
    jnp = jax.numpy
    rows, cols, values, b = _system()
    n = b.size
    B = np.stack([b, 2 * b + 1], axis=1)
    A = CooMatrix(rows, cols, jnp.asarray(values), (n, n))
    expected = np.linalg.solve(_dense(rows, cols, values, n), B)
    np.testing.assert_allclose(np.asarray(solve(A, jnp.asarray(B))), expected, rtol=1e-13, atol=1e-14)
    batched = jax.vmap(lambda rhs: solve(A, rhs), in_axes=1, out_axes=1)(jnp.asarray(B))
    np.testing.assert_allclose(np.asarray(batched), expected, rtol=1e-13, atol=1e-14)


def test_jax_forward_mode_is_refused():
    jax = _jax()
    jnp = jax.numpy
    rows, cols, values, b = _system()
    n = b.size

    def ours(v):
        return solve(CooMatrix(rows, cols, v, (n, n)), jnp.asarray(b)).sum()
    with pytest.raises(TypeError, match="custom_vjp"):
        jax.jvp(ours, (jnp.asarray(values),), (jnp.ones(values.size),))


def test_torch_second_derivative_is_refused():
    torch = _torch()
    rows, cols, values, b = _system()
    n = b.size
    v = torch.as_tensor(values).requires_grad_()
    x = solve(CooMatrix(rows, cols, v, (n, n)), torch.as_tensor(b))
    (grad,) = torch.autograd.grad((x ** 2).sum(), v, create_graph=True)
    with pytest.raises(RuntimeError, match="once_differentiable"):
        grad.sum().backward()
