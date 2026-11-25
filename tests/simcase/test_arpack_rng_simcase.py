# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""simcase's own ARPACK call (the scalar em.modes2d solve) seeds the restart vector, check N6.

The same rule as galerkin.core.eigen.arpack_rng, in simcase's own lines (no private galerkin
name): ``rng=np.random.default_rng(0)``, created per call, when SciPy's eigs or eigsh takes
it, nothing before SciPy 1.17.
"""
import ast
from pathlib import Path

import numpy as np
import scipy.sparse.linalg as spla

import simcase
from simcase import physics_em_modes2d as modes

SOURCE = Path(simcase.__file__).resolve().parent


def test_a_solver_without_rng_gets_none():
    def old_eigsh(A, k=6, M=None, sigma=None, which="LM", v0=None, ncv=None, maxiter=None, tol=0,
                  return_eigenvectors=True, Minv=None, OPinv=None, mode="normal"):
        """eigsh as SciPy 1.16 declares it."""
    assert not modes._takes_rng(old_eigsh)


def test_scipys_solvers_get_a_new_seed_zero_generator_per_call():
    for name in ("eigs", "eigsh"):
        assert modes._TAKES_RNG[name] and modes._takes_rng(getattr(spla, name))   # SciPy 1.18.1
        first, second = modes._arpack_rng(name), modes._arpack_rng(name)
        assert set(first) == {"rng"} and first["rng"] is not second["rng"]
        assert first["rng"].bit_generator.state == np.random.default_rng(0).bit_generator.state


def test_without_rng_the_call_gets_no_keyword(monkeypatch):
    monkeypatch.setitem(modes._TAKES_RNG, "eigsh", False)
    assert modes._arpack_rng("eigsh") == {}


def test_every_simcase_arpack_call_passes_it():
    calls = []
    for path in sorted(SOURCE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) in (
                    "eigs", "eigsh", "eigensolver"):
                spread = [k.value for k in node.keywords if k.arg is None]
                passed = any(isinstance(v, ast.Call) and getattr(v.func, "id", None) == "_arpack_rng" for v in spread)
                calls.append((path.name, node.lineno, passed))
    assert calls and all(passed for *_, passed in calls), calls
