# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""ARPACK's restart vector is seeded (galerkin.core.eigen.arpack_rng), check N6.

When its Krylov space breaks down, as in a search that reaches the static family of the
vector mode pencil, ARPACK asks for a random start vector; SciPy fills it from ``rng``, and
with ``rng=None`` (and before SciPy 1.17, which has no ``rng``) from operating-system
entropy. Every galerkin ARPACK call passes ``rng=np.random.default_rng(0)``, created per
call, when SciPy's eigs or eigsh takes it, and nothing otherwise.
"""
import ast
from pathlib import Path

import numpy as np
import scipy.sparse.linalg as spla

import galerkin
import galerkin._waveguide_kernels as waveguide
from galerkin.core import eigen
from galerkin.kernels import solve_modes
from test_waveguide_static_roots import N_TARGET, slab
from test_pml_modes import K0

SOURCE = Path(galerkin.__file__).resolve().parent


def seed_zero_state():
    return np.random.default_rng(0).bit_generator.state


def test_a_solver_without_rng_gets_none():
    def old_eigs(A, k=6, M=None, sigma=None, which="LM", v0=None, ncv=None, maxiter=None, tol=0,
                 return_eigenvectors=True, Minv=None, OPinv=None, OPpart=None):
        """eigs as SciPy 1.16 declares it."""
    assert eigen.arpack_rng(old_eigs) == {}


def test_scipys_solvers_get_a_new_seed_zero_generator_per_call():
    for name in ("eigs", "eigsh"):
        assert eigen._takes_rng(getattr(spla, name))          # the pinned SciPy (1.18.1) takes it
        first, second = eigen.arpack_rng(name), eigen.arpack_rng(name)
        assert set(first) == {"rng"} and isinstance(first["rng"], np.random.Generator)
        assert first["rng"] is not second["rng"]
        assert first["rng"].bit_generator.state == seed_zero_state()


def test_the_answer_is_scipys_even_when_a_test_replaces_eigs(monkeypatch):
    monkeypatch.setattr(spla, "eigs", lambda *args, **kwargs: None)
    assert set(eigen.arpack_rng("eigs")) == {"rng"}


def test_the_mode_search_passes_it(monkeypatch):
    mesh, eps, walls, coords = slab()
    seen = []
    original = spla.eigs

    def eigs(*args, **kwargs):
        seen.append(kwargs.get("rng"))
        return original(*args, **kwargs)
    monkeypatch.setattr(waveguide.spla, "eigs", eigs)
    solve_modes(mesh, eps, K0, N_TARGET, num_modes=6, pec_nodes=walls, coordinate_factors=coords.factors)
    assert len(seen) == 1 and isinstance(seen[0], np.random.Generator)


def test_every_galerkin_arpack_call_passes_arpack_rng():
    calls = []
    for path in sorted(SOURCE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in ("eigs", "eigsh"):
                spread = [k.value for k in node.keywords if k.arg is None]
                passed = any(isinstance(v, ast.Call) and getattr(v.func, "id", None) == "arpack_rng" for v in spread)
                calls.append((path.name, node.lineno, node.func.attr, passed))
    assert len(calls) >= 6, calls
    assert all(passed for *_, passed in calls), [c for c in calls if not c[3]]
