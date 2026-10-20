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
