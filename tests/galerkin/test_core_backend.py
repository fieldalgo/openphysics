# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""galerkin.core.backend and core.sparse on every array library.

JAX and PyTorch are optional extras. Their cases skip when the library is
absent; the CI job that installs them first checks that both import, so a skip
there cannot pass silently.
"""
import numpy as np
import pytest
import scipy.sparse as sp

from galerkin.core.backend import (DIFFERENTIABLE_BACKENDS, Backend, TracedValueError, backend_of,
                                   check_finite, is_concrete, namespace, scatter_add)
from galerkin.core.sparse import CooMatrix


def _jax():
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    return jax


def _torch():
    return pytest.importorskip("torch")


def _numpy_array(a):
    return np.asarray(a)


def _jax_array(a):
    return _jax().numpy.asarray(a)


def _torch_array(a):
    return _torch().as_tensor(np.asarray(a))


MAKERS = {"numpy": _numpy_array, "jax": _jax_array, "torch": _torch_array}


def _to_numpy(a):
    return a.detach().numpy() if hasattr(a, "detach") else np.asarray(a)


@pytest.mark.parametrize("name", MAKERS)
def test_namespace_and_backend(name):
    a = MAKERS[name]([1., 2.])
    assert backend_of(namespace(a, 3.0, None)) is Backend(name)
    assert (Backend(name) in DIFFERENTIABLE_BACKENDS) == (name != "numpy")


def test_namespace_without_arrays_is_numpy():
    assert backend_of(namespace(1.0, None)) is Backend.NUMPY


@pytest.mark.parametrize("name", ["jax", "torch"])
def test_mixing_libraries_is_refused(name):
    with pytest.raises(TypeError):
        namespace(np.ones(2), MAKERS[name]([1.]))


@pytest.mark.parametrize("name", MAKERS)
@pytest.mark.parametrize("dtype", [np.float64, np.complex128])
def test_scatter_add_matches_numpy_add_at(name, dtype):
    rng = np.random.default_rng(3)
    index = rng.integers(0, 7, size=40)
    values = (rng.standard_normal((40, 3)) + (1j * rng.standard_normal((40, 3)) if dtype is np.complex128 else 0)).astype(dtype)
    expected = np.zeros((7, 3), dtype=dtype)
    np.add.at(expected, index, values)
    live = MAKERS[name](values)
    out = scatter_add(namespace(live), 7, index, live)
    np.testing.assert_allclose(_to_numpy(out), expected, rtol=1e-15, atol=1e-15)
    np.testing.assert_array_equal(_to_numpy(live), values)          # input untouched


def test_scatter_add_numpy_is_bitwise_add_at():
    rng = np.random.default_rng(4)
    index, values = rng.integers(0, 5, size=200), rng.standard_normal(200)
    expected = np.zeros(5)
    np.add.at(expected, index, values)
    assert np.array_equal(scatter_add(np, 5, index, values), expected)


def test_scatter_add_validates_index():
    with pytest.raises(ValueError, match="1-D integer"):
        scatter_add(namespace(np.ones(2)), 3, np.array([0.5, 1.]), np.ones(2))
    with pytest.raises(ValueError, match="2 indices but 3 values"):
        scatter_add(namespace(np.ones(3)), 3, np.array([0, 1]), np.ones(3))


def test_scatter_add_differentiates_on_jax():
    jax = _jax()
    index = np.array([0, 2, 0, 1])
    weights = jax.numpy.array([1., 2., 3., 4.])

    def total(v):
        return (scatter_add(jax.numpy, 3, index, v) * weights[:3]).sum()
    values = jax.numpy.array([1., 1., 1., 1.])
    np.testing.assert_allclose(jax.grad(total)(values), [1., 3., 1., 2.])
    np.testing.assert_allclose(jax.jit(jax.grad(total))(values), [1., 3., 1., 2.])


def test_scatter_add_differentiates_on_torch():
    torch = _torch()
    index = np.array([0, 2, 0, 1])
    values = torch.ones(4, dtype=torch.float64, requires_grad=True)
    out = scatter_add(namespace(values), 3, index, values)
    (out * torch.tensor([1., 2., 3.], dtype=torch.float64)).sum().backward()
    np.testing.assert_allclose(values.grad.numpy(), [1., 3., 1., 2.])


@pytest.mark.parametrize("name", MAKERS)
def test_check_finite(name):
    good, bad = MAKERS[name]([1., 2.]), MAKERS[name]([1., np.inf])
    assert check_finite(namespace(good), "x", good) is good
    with pytest.raises(ValueError, match="x must contain finite numbers"):
        check_finite(namespace(bad), "x", bad)


def test_check_finite_refuses_jit_tracers_but_reads_grad_tracers():
    jax = _jax()
    jnp = jax.numpy

    def checked(x):
        return check_finite(jnp, "x", x).sum()
    assert float(jax.grad(lambda x: checked(x) * 2.)(jnp.ones(2))[0]) == 2.
    with pytest.raises(TracedValueError, match="outside jax.jit"):
        jax.jit(checked)(jnp.ones(2))
    assert is_concrete(jnp.ones(2)) and is_concrete(np.ones(2))


@pytest.mark.parametrize("name", MAKERS)
def test_coo_matrix_dense_adds_duplicates(name):
    rows, cols = np.array([0, 1, 0, 2]), np.array([0, 1, 0, 2])
    values = MAKERS[name]([1., 2., 3., 4.])
    dense = CooMatrix(rows, cols, values, (3, 3)).to_dense()
    np.testing.assert_array_equal(_to_numpy(dense), np.diag([4., 2., 4.]))


def test_coo_matrix_to_scipy_matches_scipy():
    rng = np.random.default_rng(5)
    rows, cols, values = rng.integers(0, 6, 50), rng.integers(0, 4, 50), rng.standard_normal(50)
    ours = CooMatrix(rows, cols, values, (6, 4))
    expected = sp.coo_matrix((values, (rows, cols)), shape=(6, 4)).tocsr()
    assert (ours.to_scipy() != expected).nnz == 0
    np.testing.assert_allclose(ours.to_dense(), expected.toarray(), rtol=1e-15, atol=1e-15)


@pytest.mark.parametrize("name", ["jax", "torch"])
def test_coo_matrix_to_scipy_refuses_live_values(name):
    with pytest.raises(TypeError, match="cut their derivatives"):
        CooMatrix(np.array([0]), np.array([0]), MAKERS[name]([1.]), (1, 1)).to_scipy()


@pytest.mark.parametrize("kwargs, match", [
    (dict(rows=np.array([0, 1]), cols=np.array([0]), values=np.ones(2), shape=(2, 2)), "equal length"),
    (dict(rows=np.array([0.]), cols=np.array([0]), values=np.ones(1), shape=(2, 2)), "integer"),
    (dict(rows=np.array([0]), cols=np.array([0]), values=np.ones(2), shape=(2, 2)), "one entry per"),
    (dict(rows=np.array([2]), cols=np.array([0]), values=np.ones(1), shape=(2, 2)), "outside the matrix"),
])
def test_coo_matrix_validates(kwargs, match):
    with pytest.raises(ValueError, match=match):
        CooMatrix(**kwargs)
