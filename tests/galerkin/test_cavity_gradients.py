# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""PEC box resonances with JAX or PyTorch box lengths.

Every result array must match the NumPy solve, on the dense and the iterative
eigensolver paths. Derivatives with respect to the lengths are checked against
an identity the discretization keeps exactly (scaling the whole box by s scales
every eigenvalue by 1/s^2, so sum_a L_a d lambda / d L_a = -2 lambda) and against
central differences of the NumPy solve for eigenvalues, frequencies, edge
coefficients and centroid fields. Degenerate modes, also a pair cut by
num_modes, give NaN derivatives and a warning while a simple mode keeps its
derivative. JAX and PyTorch cases skip when the library is absent; the CI job
that installs them first checks that both import.
"""
import warnings

import numpy as np
import pytest

from galerkin.cavity import DegenerateModeWarning, solve_cavity_box
from galerkin.core.backend import TracedValueError


def _jax():
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    return jax


def _torch():
    return pytest.importorskip("torch")


def _numbers(a):
    return a.detach().numpy() if hasattr(a, "detach") else np.asarray(a)


def _live(name, lengths):
    if name == "jax":
        return _jax().numpy.asarray(lengths, dtype=_jax().numpy.float64)
    torch = _torch()
    return torch.tensor(lengths, dtype=torch.float64, requires_grad=True)


def _gradient(name, objective, lengths):
    if name == "jax":
        return np.asarray(_jax().grad(objective)(_live("jax", lengths)))
    leaf = _live("torch", lengths)
    objective(leaf).backward()
    return leaf.grad.numpy()


def _central(objective, lengths, rel=1e-6):
    out = []
    for a in range(3):
        h = rel * lengths[a]
        up, down = list(lengths), list(lengths)
        up[a] += h
        down[a] -= h
        out.append((float(objective(up)) - float(objective(down))) / (2 * h))
    return np.array(out)


BACKENDS = ["jax", "torch"]
LENGTHS = (1.0, 0.7, 0.45)
# (subdivisions, target): 43 free edges take the dense path, 291 the iterative one.
PATHS = {"dense": ((3, 2, 2), 3.0e8), "iterative": ((5, 4, 3), 3.2e8)}
FIELDS = ("frequencies_hz", "eigenvalues_m2", "edge_coefficients", "electric_field",
          "relative_residuals")


def _solve(lengths, path, num_modes=4):
    cells, target = PATHS[path]
    return solve_cavity_box(lengths, cells, num_modes=num_modes, target_frequency_hz=target)


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("path", PATHS)
def test_values_match_numpy(name, path):
    reference = _solve(LENGTHS, path)
    live = _solve(_live(name, LENGTHS), path)
    for field in FIELDS:
        got, expected = getattr(live, field), getattr(reference, field)
        assert type(got).__module__.split(".")[0] in ("jax", "jaxlib", "torch"), field
        np.testing.assert_allclose(_numbers(got), expected, rtol=1e-12,
                                   atol=1e-12 * np.max(abs(expected)), err_msg=field)
    np.testing.assert_array_equal(live.mesh.nodes, reference.mesh.nodes)
    np.testing.assert_array_equal(live.pec_edge_ids, reference.pec_edge_ids)


@pytest.mark.parametrize("name", BACKENDS)
@pytest.mark.parametrize("path", PATHS)
def test_gradients_match_central_differences(name, path):
    def objective(lengths):
        r = _solve(lengths, path)
        return (r.eigenvalues_m2[0] + r.frequencies_hz[3] * 1e-7 + r.edge_coefficients[7, 2]
                + (r.electric_field[1, :, 0] ** 2).sum() * 1e-2)
    np.testing.assert_allclose(_gradient(name, objective, LENGTHS), _central(objective, LENGTHS),
                               rtol=1e-6)


@pytest.mark.parametrize("name", BACKENDS)
def test_scaling_identity_holds_exactly(name):
    """sum_a L_a d lambda_k / d L_a = -2 lambda_k and the same with -1 for frequencies."""
    reference = _solve(LENGTHS, "iterative")
    for k in range(4):
        dlam = _gradient(name, lambda lengths: _solve(lengths, "iterative").eigenvalues_m2[k], LENGTHS)
        dfreq = _gradient(name, lambda lengths: _solve(lengths, "iterative").frequencies_hz[k], LENGTHS)
        assert abs(dlam @ LENGTHS / (-2 * reference.eigenvalues_m2[k]) - 1) < 1e-12
        assert abs(dfreq @ LENGTHS / (-reference.frequencies_hz[k]) - 1) < 1e-12


@pytest.mark.parametrize("name", BACKENDS)
def test_lengths_may_mix_numbers_and_live_values(name):
    def objective(width):
        return solve_cavity_box([width, 0.7, 0.45], (3, 2, 2), num_modes=2,
                                target_frequency_hz=3.0e8).eigenvalues_m2[1]
    if name == "jax":
        got = float(_jax().grad(objective)(_jax().numpy.asarray(1.0)))
    else:
        torch = _torch()
        width = torch.tensor(1.0, dtype=torch.float64, requires_grad=True)
        objective(width).backward()
        got = float(width.grad)
    h = 1e-6
    assert abs(got - (objective(1.0 + h) - objective(1.0 - h)) / (2 * h)) <= 1e-6 * abs(got)


@pytest.mark.parametrize("name", BACKENDS)
def test_degenerate_modes_have_nan_derivatives_and_simple_ones_keep_theirs(name):
    """A square cross-section: the pair above the fundamental is degenerate by symmetry."""
    square, cells = (1.0, 1.0, 0.5), (4, 4, 2)

    def run(lengths, num_modes=3, target=1.5e8):
        return solve_cavity_box(lengths, cells, num_modes=num_modes, target_frequency_hz=target)
    frequencies = run(square).frequencies_hz
    assert abs(frequencies[1] - frequencies[2]) <= 1e-12 * frequencies[1]
    assert frequencies[1] - frequencies[0] > 0.1 * frequencies[0]
    with pytest.warns(DegenerateModeWarning, match=r"modes \[1, 2\]"):
        live = run(_live(name, square))
    np.testing.assert_allclose(_numbers(live.frequencies_hz), frequencies, rtol=1e-12)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DegenerateModeWarning)
        assert np.isnan(_gradient(name, lambda lengths: run(lengths).eigenvalues_m2[1], square)).all()
        assert np.isnan(_gradient(name, lambda lengths: run(lengths).electric_field[2, 0, 0],
                                  square)).all()
        simple = _gradient(name, lambda lengths: run(lengths).eigenvalues_m2[0]
                           + run(lengths).edge_coefficients[9, 0], square)
    np.testing.assert_allclose(simple, _central(lambda lengths: run(lengths).eigenvalues_m2[0]
                                                + run(lengths).edge_coefficients[9, 0], square),
                               rtol=1e-6)
    with pytest.warns(DegenerateModeWarning, match=r"modes \[0\]"):     # partner not returned
        assert np.isnan(_gradient(name, lambda lengths: run(lengths, 1, 3.3e8).eigenvalues_m2[0],
                                  square)).all()


def test_jit_is_refused():
    jax = _jax()
    with pytest.raises(TracedValueError):
        jax.jit(lambda lengths: _solve(lengths, "dense").eigenvalues_m2)(jax.numpy.asarray(LENGTHS))
