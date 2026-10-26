# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Uniform-temperature controls: free in-plane expansion and blocked expansion."""
import numpy as np
from galerkin import rectangle_mesh
from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity


def main():
    n = 8
    mesh = rectangle_mesh(1., 1., n, n)
    snapshot = freeze_temperature(mesh, np.full(mesh.num_nodes, 313.15))
    minimal = {(0, 0): 0., (0, 1): 0., (n, 1): 0.}
    boundary = np.unique(np.concatenate(list(mesh.boundary.values())))
    blocked = {(int(node), component): 0. for node in boundary for component in (0, 1)}
    results = {}
    for name, plane, supports in (
        ('free_plane_stress', 'stress', minimal),
        ('free_plane_strain', 'strain', minimal),
        ('blocked_plane_strain', 'strain', blocked),
    ):
        r = solve_thermoelasticity(
            mesh, snapshot, reference_temperature_k=293.15,
            thermal_expansion_per_k=12e-6, young_modulus=70e9,
            poisson_ratio=.3, plane=plane, dirichlet=supports)
        results[name] = r
        force = r.reaction.sum(axis=0)
        moment = np.sum(mesh.nodes[:, 0] * r.reaction[:, 1]
                        - mesh.nodes[:, 1] * r.reaction[:, 0])
        print(name)
        print('  max displacement (m):', np.linalg.norm(r.displacement, axis=1).max())
        print('  mean stress xx, yy, xy (Pa):', r.stress.mean(axis=0))
        print('  mean sigma_zz (Pa):', r.sigma_zz.mean())
        print('  elastic energy (J/m):', r.physical_elastic_energy)
        print('  net support force (N/m):', force)
        print('  net support moment per depth (N):', moment)
    return mesh, results


if __name__ == '__main__':
    main()
