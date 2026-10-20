# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Installed public two-stage API, independent uniform thermal expansion."""
from pathlib import Path
import sys
import numpy as np
import pytest
import galerkin.transient_thermal_mechanical as workflow
from galerkin.mesh import rectangle_mesh
from galerkin.transient_heat import solve_transient_heat


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_installed_transient_thermomechanical_closed_form(plane):
    assert Path(workflow.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    mesh = rectangle_mesh(1., 1., 3, 3)
    heat = solve_transient_heat(mesh, conductivity=2., volumetric_heat_capacity=4.,
        time_s=[2., 2.1, 2.4, 3.], initial_temperature_k=np.full(mesh.num_nodes, 300.),
        dirichlet={}, heat_source=8.)
    right = int(np.argmin(np.sum((mesh.nodes-[1., 0.])**2, axis=1)))
    result = workflow.solve_transient_thermoelasticity(mesh, heat,
        units={'length': 'm', 'time': 's', 'temperature': 'K'}, time_indices=[0, 2, 3],
        young_modulus=2e9, poisson_ratio=.25, plane=plane,
        thermal_expansion_per_k=1e-5, reference_temperature_k=300.,
        mechanical_dirichlet={(0, 0): 0., (0, 1): 0., (right, 1): 0.})
    assert result.time_indices == (0, 2, 3)
    assert result.time_s == (2., 2.4, 3.)
    for step in result.steps:
        theta = 2*(step.time_s-2)
        np.testing.assert_allclose(step.temperature_snapshot.temperature_k, 300+theta, rtol=0, atol=1e-9)
        np.testing.assert_allclose(step.mechanics.displacement,
            (1 if plane == 'stress' else 1.25)*1e-5*theta*mesh.nodes, rtol=0, atol=2e-14)
        np.testing.assert_allclose(step.mechanics.stress, 0., rtol=0, atol=4e-4)
        np.testing.assert_allclose(step.mechanics.sigma_zz,
            0. if plane == 'stress' else -2e9*1e-5*theta, rtol=0, atol=4e-4)
