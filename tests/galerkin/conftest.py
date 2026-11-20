# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Shared helpers for the validation suite.

Every test here grades galerkin against `refsol`, a separate package holding the
closed-form and published reference solutions. The packages share a repository,
but the reference implementation never imports the engine it grades. The engine
also never imports the answer key; tests/galerkin/test_independence.py checks that boundary.
"""

import pathlib
import sys

import numpy as np
import pytest

# The examples carry their own analytical solutions, written independently of
# refsol. Tests below check the two against each other so they cannot drift.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "examples" / "galerkin"))


def rate(errors, refinement=2.0):
    """Observed convergence order between successive refinements.

    refinement may be a scalar (uniform halving) or one ratio per step.
    """
    e = np.asarray(errors, dtype=float)
    r = np.broadcast_to(np.asarray(refinement, dtype=float), (len(e) - 1,))
    return np.log(e[:-1] / e[1:]) / np.log(r)


def assert_second_order(errors, refinement=2.0, floor=1.8, name="quantity"):
    r = rate(errors, refinement)
    assert r[-1] > floor, (
        f"{name}: convergence order {r[-1]:.2f} below {floor} "
        f"(errors {np.array2string(np.asarray(errors), precision=3)})")
    return r


@pytest.fixture(scope="session")
def refsol():
    return pytest.importorskip(
        "refsol", reason="install the answer key: pip install -e packages/galerkin-refsol")


# A motion's t must be a real float64 JAX or PyTorch scalar. Each case is a t that
# is refused by name, and the message that names it (shape-derivative files, *8).
_BAD_MOTION_T = {
    "jax-complex128": ("jax", "complex128", r"real float64 scalar, got complex128; .*imaginary part"),
    "torch-complex128": ("torch", "complex128", r"real float64 scalar, got complex128; .*imaginary part"),
    "jax-float32-x64-on": ("jax", "float32", r"float64 scalar, got float32; .*does not promote t"),
    "torch-float32": ("torch", "float32", r"float64 scalar, got float32; .*does not promote t"),
    "torch-float16": ("torch", "float16", r"float64 scalar, got float16; .*does not promote t"),
    "torch-bfloat16": ("torch", "bfloat16", r"float64 scalar, got bfloat16; .*does not promote t"),
}


@pytest.fixture(params=sorted(_BAD_MOTION_T))
def bad_motion_t(request):
    """(t, message pattern): a motion t of the wrong dtype and its refusal."""
    backend, dtype, pattern = _BAD_MOTION_T[request.param]
    if backend == "jax":
        jax = pytest.importorskip("jax")
        jax.config.update("jax_enable_x64", True)
        t = jax.numpy.asarray(0.0, dtype=getattr(jax.numpy, dtype))
    else:
        torch = pytest.importorskip("torch")
        t = torch.tensor(0.0, dtype=getattr(torch, dtype), requires_grad=True)
    return t, pattern
