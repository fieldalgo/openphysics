# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Closed-form checks independent of FEM assembly and solver."""
import ast
from pathlib import Path
import numpy as np
import pytest
from numpy.testing import assert_allclose
from refsol import elasticity as ref


def test_elasticity_oracle_has_no_solver_import():
    tree = ast.parse(Path(ref.__file__).read_text())
    imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    imports += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    assert not any(x.startswith(("galerkin", "simcase")) for x in imports)


@pytest.mark.parametrize("plane,expected", [("stress", [32/15, 8/15, 8/5]),
                                               ("strain", [12/5, 4/5, 8/5])])
def test_elasticity_known_constitutive_values_and_engineering_shear(plane, expected):
    actual = ref.stress_from_strain([.01, 0, .02], young_modulus=200, poisson_ratio=.25, plane=plane)
    assert_allclose(actual, expected, rtol=1e-14)


@pytest.mark.parametrize("plane", ["stress", "strain"])
def test_elasticity_manufactured_force_is_negative_stress_divergence(plane):
    p = np.array([[.17,.31],[.41,.72],[.63,.24]])
    args = dict(young_modulus=70000, poisson_ratio=.3, plane=plane)
    h = 1e-5
    sx = (ref.sine_manufactured(p+[h,0], **args).stress-ref.sine_manufactured(p-[h,0], **args).stress)/(2*h)
    sy = (ref.sine_manufactured(p+[0,h], **args).stress-ref.sine_manufactured(p-[0,h], **args).stress)/(2*h)
    force = -np.column_stack([sx[:,0]+sy[:,2],sx[:,2]+sy[:,1]])
    assert_allclose(ref.sine_manufactured(p, **args).body_force, force, rtol=1e-8, atol=1e-8)


def test_elasticity_reference_rigid_and_boundary_fields():
    args = dict(young_modulus=200, poisson_ratio=.25, plane="stress")
    r = ref.affine([[.2,.7],[.3,.8]], [[0,-2],[2,0]], [1,2], **args)
    assert_allclose(r.strain, 0)
    assert_allclose(r.stress, 0)
    r = ref.sine_manufactured([[0,.3],[1,.4],[.5,0],[.6,1]], **args)
    assert_allclose(r.displacement, 0, atol=1e-18)


@pytest.mark.parametrize("kwargs", [{"young_modulus": 0}, {"poisson_ratio": .5},
                                       {"poisson_ratio": -1}, {"young_modulus": np.nan}, {"plane": "unknown"}])
def test_elasticity_reference_reject_material(kwargs):
    args = dict(young_modulus=200, poisson_ratio=.25, plane="stress")
    with pytest.raises(ValueError):
        ref.sine_manufactured([[.2,.3]], **{**args, **kwargs})


@pytest.mark.parametrize("points", [[1,2], [[0,np.inf]], [[1j,0]], [[1,2,3]]])
def test_elasticity_reference_reject_points(points):
    with pytest.raises(ValueError):
        ref.sine_manufactured(points, young_modulus=200, poisson_ratio=.25, plane="stress")
