# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Prescribed-temperature mechanical stage: no heat equation is solved."""
import numpy as np
from galerkin.mesh import rectangle_mesh
from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity


def main():
    mesh = rectangle_mesh(1., 1., 8, 8)
    snapshot = freeze_temperature(mesh, temperature=np.full(mesh.num_nodes, 313.15))
    result = solve_thermoelasticity(
        mesh, snapshot, stress_free_temperature=293.15,
        linear_expansion_coefficient=12e-6, youngs_modulus=70e9,
        poisson_ratio=.3, plane='strain',
        prescribed_displacement={(0, 0): 0., (0, 1): 0., (8, 1): 0.})
    np.testing.assert_allclose(result.displacement, 1.3*12e-6*20*mesh.nodes, atol=1e-14)
    np.testing.assert_allclose(result.stress_zz, -16.8e6, atol=1e-5)
    np.testing.assert_allclose(result.strain_energy_per_depth, 2016., rtol=1e-12)
    print('Prescribed P1 temperature mechanical stage; no heat solve')
    print('physical elastic energy [J/m]:', result.strain_energy_per_depth)
    print('centroid sigma_zz [Pa]:', result.stress_zz[0])


if __name__ == '__main__':
    main()
