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


def _laplacian_terms(n=6):
    """A 1-D Laplacian split into two COO terms, plus a load."""
    rows = np.concatenate([np.arange(n), np.arange(n - 1), np.arange(1, n)])
    cols = np.concatenate([np.arange(n), np.arange(1, n), np.arange(n - 1)])
    values = np.concatenate([np.full(n, 2.0), np.full(2 * (n - 1), -1.0)])
    extra = np.arange(n), np.arange(n), np.linspace(0.1, 0.6, n)
    return (CooMatrix(rows, cols, values, (n, n)), CooMatrix(*extra, (n, n)),
            np.linspace(1.0, 2.0, n))


def test_solve_dirichlet_numpy_is_galerkin_solver_bit_for_bit():
    from galerkin.core.solve import solve_dirichlet
    from galerkin.solver import solve_dirichlet as scipy_solve_dirichlet
    K, H, f = _laplacian_terms()
    bc = {(0,): 1.5, (5,): -0.25}
    expected = scipy_solve_dirichlet(K.to_scipy() + H.to_scipy(), f, bc)
    assert np.array_equal(solve_dirichlet([K, H], f, bc), expected)


@pytest.mark.parametrize("name", ["jax", "torch"])
def test_solve_dirichlet_live_values_and_gradients(name):
    from galerkin.core.solve import solve_dirichlet
    K, H, f = _laplacian_terms()
    w = np.linspace(-1.0, 1.0, 6)

    def numpy_objective(scale, g0, f2):
        load = f.copy()
        load[2] = f2
        x = solve_dirichlet([K, CooMatrix(H.rows, H.cols, scale * H.values, H.shape)], load, {(0,): g0, (5,): 0.5})
        return float(w @ x)
    values = (1.3, 1.5, 0.7)
    if name == "jax":
        jax = _jax()
        jnp = jax.numpy

        def objective(scale, g0, f2):
            load = jnp.asarray(f).at[2].set(f2)
            x = solve_dirichlet([K, CooMatrix(H.rows, H.cols, scale * jnp.asarray(H.values), H.shape)],
                                load, {(0,): g0, (5,): 0.5})
            return jnp.asarray(w) @ x
        got = jax.grad(lambda v: objective(*v))([jnp.asarray(v) for v in values])
        value = float(objective(*values))
    else:
        torch = _torch()
        leaves = [torch.tensor(v, dtype=torch.float64, requires_grad=True) for v in values]
        load = torch.cat([torch.as_tensor(f[:2]), leaves[2][None], torch.as_tensor(f[3:])])
        x = solve_dirichlet([K, CooMatrix(H.rows, H.cols, leaves[0] * torch.as_tensor(H.values), H.shape)],
                            load, {(0,): leaves[1], (5,): 0.5})
        objective = torch.as_tensor(w) @ x
        objective.backward()
        got, value = [float(t.grad) for t in leaves], float(objective.detach())
    assert abs(value - numpy_objective(*values)) < 1e-13
    h = 1e-6
    for i in range(3):
        up, down = list(values), list(values)
        up[i] += h
        down[i] -= h
        fd = (numpy_objective(*up) - numpy_objective(*down)) / (2 * h)
        assert abs(float(got[i]) - fd) <= 1e-7 * max(1.0, abs(fd))


def test_solve_dirichlet_last_value_wins_on_every_library():
    from galerkin.core.solve import solve_dirichlet
    K, H, f = _laplacian_terms()
    bc = {(0, 5): 1.0, (5,): 2.0}
    expected = solve_dirichlet(K, f, bc)
    assert expected[5] == 2.0 and expected[0] == 1.0
    jax = _jax()
    got = solve_dirichlet(K, jax.numpy.asarray(f), {(0, 5): jax.numpy.asarray(1.0), (5,): 2.0})
    np.testing.assert_allclose(np.asarray(got), expected, rtol=1e-14)


def test_jax_solve_is_built_once():
    """One traced function for every solve: a function built per call would be traced
    and cached anew at each solve, so memory would grow with the number of solves."""
    jax = _jax()
    import galerkin.core.solve as module
    rows, cols, values, b = _system()
    A = CooMatrix(rows, cols, jax.numpy.asarray(values), (b.size, b.size))
    solve(A, jax.numpy.asarray(b))
    first = module._JAX_SOLVE
    solve(A, jax.numpy.asarray(2 * b))
    assert module._JAX_SOLVE is first


def test_torch_solve_keeps_no_factor_on_the_graph():
    """The factor is computed again in backward: an attribute on the graph would stay in
    memory for every solve, even under torch.utils.checkpoint."""
    torch = _torch()
    rows, cols, values, b = _system()
    v = torch.as_tensor(values).requires_grad_()
    x = solve(CooMatrix(rows, cols, v, (b.size, b.size)), torch.as_tensor(b))
    assert not any(hasattr(x.grad_fn, name) for name in ("lu", "factor"))
    x.sum().backward()
    assert v.grad is not None


def test_a_singular_numpy_block_raises_and_the_public_solve_still_warns():
    """The physics solvers' NumPy path raises for an exactly singular block; the public
    galerkin.solve_dirichlet keeps SciPy's spsolve, which warns and returns NaN."""
    from scipy.sparse.linalg import MatrixRankWarning

    from galerkin.core.solve import solve_dirichlet
    from galerkin.solver import solve_dirichlet as public_solve_dirichlet
    K = CooMatrix(np.array([0, 0, 1, 1, 2]), np.array([0, 1, 0, 1, 2]), np.ones(5), (3, 3))
    bc = {(2,): 0.5}
    with pytest.raises(ValueError, match="^singular sparse matrix: Factor is exactly singular$"):
        solve_dirichlet(K, np.ones(3), bc)
    with pytest.warns(MatrixRankWarning):
        x = public_solve_dirichlet(K.to_scipy(), np.ones(3), bc)
    assert np.isnan(x[:2]).all() and x[2] == 0.5


@pytest.mark.parametrize("physics", ["heat", "electric", "elasticity"])
def test_overlapping_numpy_solves_leave_the_warning_filters_alone(monkeypatch, physics):
    """Two threads inside a NumPy solve at once leave ``warnings.filters`` as they found it.

    ``warnings.catch_warnings`` swaps the process-wide filter list: of two solves that
    overlap, the one that leaves last would restore a list holding the other's filter.
    The threads enter and leave in that order here.
    """
    import threading
    import warnings

    import galerkin.core.solve as core_solve
    from galerkin.elasticity import solve_elasticity
    from galerkin.electric import solve_steady_electric
    from galerkin.mesh import rectangle_mesh
    from galerkin.thermal import solve_steady_heat
    mesh = rectangle_mesh(1.0, 0.5, 4, 3)
    left = [int(i) for i in mesh.boundary["left"]]
    right = [int(i) for i in mesh.boundary["right"]]
    solves = {
        "heat": lambda: solve_steady_heat(mesh, conductivity=2.0, dirichlet={i: 300.0 for i in left},
                                          heat_source=1.0),
        "electric": lambda: solve_steady_electric(
            mesh, conductivity=2.0, dirichlet={**{i: 0.0 for i in left}, **{i: 1.0 for i in right}}),
        "elasticity": lambda: solve_elasticity(
            mesh, young_modulus=2e3, poisson_ratio=0.3, plane="stress",
            dirichlet={(i, c): 0.0 for i in left for c in (0, 1)}, traction={"right": [1.0, 0.0]}),
    }
    original = core_solve.scipy_solve_dirichlet
    first_inside, first_done = threading.Event(), threading.Event()
    both_inside = threading.Barrier(2, timeout=30)

    def held(*args, **kwargs):
        if threading.current_thread().name == "first":
            first_inside.set()
        both_inside.wait()
        if threading.current_thread().name == "second":
            first_done.wait(30)
        return original(*args, **kwargs)

    monkeypatch.setattr(core_solve, "scipy_solve_dirichlet", held)
    before, errors = list(warnings.filters), []

    def run():
        try:
            solves[physics]()
        except Exception as exc:  # reported by the assertion below
            errors.append(exc)
        finally:
            if threading.current_thread().name == "first":
                first_done.set()

    first = threading.Thread(target=run, name="first")
    first.start()
    assert first_inside.wait(30)
    second = threading.Thread(target=run, name="second")
    second.start()
    first.join(60)
    second.join(60)
    assert not errors
    assert warnings.filters == before
