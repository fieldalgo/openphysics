# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Clamped rectangle under gravity-like body force; run from the repo root."""
from galerkin.mesh import rectangle_mesh
from galerkin.elasticity import solve_elasticity


def main():
    mesh = rectangle_mesh(.1, .02, 20, 4)  # metres
    fixed = {(int(i), component): 0. for i in mesh.boundary["left"] for component in (0, 1)}
    result = solve_elasticity(mesh, young_modulus=70e9, poisson_ratio=.3,
                              plane="stress", dirichlet=fixed, body_force=(0., -2700*9.81))
    print("Minimum vertical displacement (m):", result.displacement[:, 1].min())
    print("Body load per thickness (N/m):", result.load.sum(axis=0))
    print("Support reaction per thickness (N/m):", result.reaction.sum(axis=0))
    print("Force imbalance per thickness (N/m):", (result.load+result.reaction).sum(axis=0))


if __name__ == "__main__":
    main()
