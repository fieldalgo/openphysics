# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""N1 (pre-registered 2026-11-22): every callback refused together with a motion is a TypeError.

Coefficient callbacks (conductivities, heat capacity, elastic constants, expansion coefficient,
stress-free temperature) were refused with ValueError before 2026-11-22; they are now a TypeError
that is still a ValueError, so existing handlers keep catching them. Messages are unchanged.
"""

from __future__ import annotations

import numpy as np
import pytest

from galerkin.elasticity import solve_elasticity
from galerkin.electric import solve_steady_electric
from galerkin.mesh import rectangle_mesh
from galerkin.mesh3d import box_mesh
from galerkin.shape import MeshMotion
from galerkin.thermal import solve_steady_heat
from galerkin.thermal3d import solve_steady_heat_3d
from galerkin.transient_heat import solve_transient_heat


def _t():
    jax = pytest.importorskip("jax")
    jax.config.update("jax_enable_x64", True)
    return jax.numpy.asarray(0.0)


def _plane():
    m = rectangle_mesh(1.0, 0.5, 4, 2)
    W = np.zeros((m.num_nodes, 2))
    W[:, 0] = 0.1 * m.nodes[:, 0]
    left = [int(i) for i in m.boundary["left"]]
    return m, W, left


def _heat(**over):
    m, W, left = _plane()
    kw = dict(thermal_conductivity=2.0, prescribed_temperature={i: 300.0 for i in left})
    kw.update(over)
    return solve_steady_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=_t()))


def _transient(**over):
    m, W, left = _plane()
    kw = dict(thermal_conductivity=2.0, volumetric_heat_capacity=1e5, time=np.linspace(0, 1, 3),
              initial_temperature=np.full(m.num_nodes, 300.0), prescribed_temperature={i: 300.0 for i in left})
    kw.update(over)
    return solve_transient_heat(m, **kw, motion=MeshMotion(design_velocity=W, t=_t()))


def _electric(**over):
    m, W, left = _plane()
    kw = dict(electrical_conductivity=1.0, prescribed_electric_potential={i: 0.0 for i in left})
    kw.update(over)
    return solve_steady_electric(m, **kw, motion=MeshMotion(design_velocity=W, t=_t()))


def _elastic(**over):
    m, W, left = _plane()
    kw = dict(youngs_modulus=1e9, poisson_ratio=0.3, plane="stress",
              prescribed_displacement={(i, c): 0.0 for i in left for c in (0, 1)})
    kw.update(over)
    return solve_elasticity(m, **kw, motion=MeshMotion(design_velocity=W, t=_t()))


def _heat3d(**over):
    m = box_mesh(1.0, 0.5, 0.5, 2, 1, 1)
    W = np.zeros_like(m.nodes)
    W[:, 0] = 0.1 * m.nodes[:, 0]
    x0 = [int(i) for i in np.flatnonzero(np.isclose(m.nodes[:, 0], 0))]
    kw = dict(thermal_conductivity=2.0, prescribed_temperature={i: 300.0 for i in x0})
    kw.update(over)
    return solve_steady_heat_3d(m, **kw, motion=MeshMotion(design_velocity=W, t=_t()))


def _f(*args):
    return np.ones(len(args[0])) if args and hasattr(args[0], "__len__") else 1.0


COEFFICIENTS = [
    ("steady thermal_conductivity", lambda: _heat(thermal_conductivity=lambda p: np.ones(len(p)))),
    ("transient thermal_conductivity", lambda: _transient(thermal_conductivity=lambda: 1.5)),
    ("transient volumetric_heat_capacity", lambda: _transient(volumetric_heat_capacity=lambda: 1e5)),
    ("electrical_conductivity", lambda: _electric(electrical_conductivity=lambda p: np.ones(len(p)))),
    ("youngs_modulus", lambda: _elastic(youngs_modulus=lambda p: np.ones(len(p)))),
    ("3d thermal_conductivity", lambda: _heat3d(thermal_conductivity=lambda p: np.ones(len(p)))),
]
OTHERS = [
    ("steady heat_source_density", lambda: _heat(heat_source_density=_f)),
    ("steady inward_heat_flux", lambda: _heat(inward_heat_flux={"right": lambda p, n: np.ones(len(p))})),
    ("steady prescribed_temperature", lambda: _heat(prescribed_temperature={0: lambda p: 300.0})),
    ("transient heat_source_density", lambda: _transient(heat_source_density=lambda p, t: np.zeros(len(p)))),
    ("elastic body_force_density", lambda: _elastic(body_force_density=lambda p: np.zeros((len(p), 2)))),
    ("3d heat_source_density", lambda: _heat3d(heat_source_density=lambda c: np.ones(len(c)))),
]


@pytest.mark.parametrize("label,call", COEFFICIENTS, ids=[c[0] for c in COEFFICIENTS])
def test_n1_coefficient_callbacks_are_type_errors_and_still_value_errors(label, call):
    with pytest.raises(TypeError, match="is a callback") as caught:
        call()
    assert isinstance(caught.value, ValueError), label


@pytest.mark.parametrize("label,call", OTHERS, ids=[c[0] for c in OTHERS])
def test_n1_other_callbacks_are_type_errors(label, call):
    with pytest.raises(TypeError, match="callback"):
        call()


def test_n1_thermoelastic_constants():
    from galerkin._moving import _check_thermal_constants
    for args in ((lambda: 293.0, 1e-5), (293.0, lambda p: np.ones(len(p)))):
        with pytest.raises(TypeError, match="is a callback") as caught:
            _check_thermal_constants(*args)
        assert isinstance(caught.value, ValueError)
