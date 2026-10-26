# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""galerkin.core: the one real-number check and the shared triangle mesh check."""
import numpy as np
import pytest

from galerkin import Mesh, rectangle_mesh
from galerkin.core.checks import finite_scalar, readonly_copy, real_array
from galerkin.core.triangles import triangle_geometry
from galerkin.elasticity import solve_elasticity
from galerkin.thermal import solve_steady_heat

WIDE = np.finfo(np.longdouble).max > np.finfo(float).max
# 1e400 as a long double where that type is wider than double (the literal 1e400 is already inf).
HUGE = np.longdouble(1e300)*np.longdouble(1e100)


@pytest.mark.parametrize("value", [True, np.bool_(False), [1., True], (np.bool_(True), 2.)])
def test_real_array_rejects_booleans_alone_and_inside_sequences(value):
    with pytest.raises(ValueError, match="must not contain booleans"):
        real_array(value, "x")


@pytest.mark.parametrize("value", [np.nan, [1., np.inf], "1", [1+1j], np.array([None])])
def test_real_array_rejects_nonfinite_and_nonreal(value):
    with pytest.raises(ValueError, match="must contain finite real numbers"):
        real_array(value, "x")


@pytest.mark.skipif(not WIDE, reason="long double has the range of double on this platform")
def test_real_array_rejects_values_that_overflow_float():
    with pytest.raises(ValueError, match="exceeds floating-point range"):
        real_array(np.array([1., HUGE], dtype=np.longdouble), "x")


def test_real_array_returns_a_new_float_array():
    given = np.array([[1., 2.]])
    out = real_array(given, "x")
    assert out.dtype == float and out is not given and not np.shares_memory(out, given)
    assert real_array(3, "x").shape == () and real_array([1, 2], "x").dtype == float


def test_scalar_and_readonly_helpers():
    assert finite_scalar(np.int32(3), "s") == 3.
    for bad in (True, [1.], np.inf):
        with pytest.raises(ValueError):
            finite_scalar(bad, "s")
    a = np.ones(2)
    r = readonly_copy(a)
    assert not r.flags.writeable and not np.shares_memory(a, r)


def _held(mesh):
    return {(int(n), c): 0. for n in mesh.boundary["left"] for c in (0, 1)}


def test_elasticity_now_uses_the_strict_check():
    # Before the shared check, elasticity accepted a bool inside a list and
    # converted overflowing long doubles to infinity.
    mesh = rectangle_mesh(1., 1., 2, 2)
    kw = dict(young_modulus=1., poisson_ratio=.3, plane="stress", dirichlet=_held(mesh))
    with pytest.raises(ValueError, match="must not contain booleans"):
        solve_elasticity(mesh, body_force=[0., True], **kw)
    if WIDE:
        with pytest.raises(ValueError, match="exceeds floating-point range"):
            solve_elasticity(mesh, body_force=np.array([0., HUGE], dtype=np.longdouble), **kw)


def test_thermal_now_rejects_bools_inside_callback_values():
    mesh = rectangle_mesh(1., 1., 2, 2)
    with pytest.raises(ValueError, match="must not contain booleans"):
        solve_steady_heat(mesh, conductivity=1., dirichlet={0: 300.},
                          heat_source=lambda x: [True]*len(x))


def test_orientation_is_the_only_difference_between_the_two_mesh_checks():
    mesh = rectangle_mesh(2., 1., 3, 2)
    ccw = triangle_geometry(mesh)
    flipped = rectangle_mesh(2., 1., 3, 2)
    flipped.triangles = flipped.triangles[:, ::-1].copy()   # Mesh() itself would reorient them
    with pytest.raises(ValueError, match="counter-clockwise"):
        triangle_geometry(flipped)
    cw = triangle_geometry(flipped, counterclockwise=False)
    np.testing.assert_array_equal(cw[2], ccw[2])
    assert cw[3] == ccw[3] and cw[4] == ccw[4] == 1
    hinge = Mesh(np.array([[0, 0], [1, 0], [0, 1], [-1, 0], [0, -1]], float), np.array([[0, 1, 2], [0, 3, 4]]), {})
    for counterclockwise in (True, False):
        with pytest.raises(ValueError, match="joined only at a point"):
            triangle_geometry(hinge, counterclockwise=counterclockwise)
