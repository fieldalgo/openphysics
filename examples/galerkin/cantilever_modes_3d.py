# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""First two bending modes of a rectangular cantilever, in SI units."""
import numpy as np

from galerkin.mesh3d import box_mesh
from galerkin.structural_modes3d import solve_structural_modes_3d


def cantilever_modes(refinement):
    length, width, thickness = 0.12, 0.018, 0.012  # m
    young, density = 70e9, 2700.0  # Pa, kg/m^3
    mesh = box_mesh(length, width, thickness, 8 * refinement, refinement, refinement)
    clamp = {(node, axis): 0.0 for node in mesh.boundary["x0"] for axis in range(3)}
    modes = solve_structural_modes_3d(mesh, youngs_modulus=young, poisson_ratio=0.0,
                                      mass_density=density, prescribed_displacement=clamp, mode_count=2)
    # First root of cos(beta) cosh(beta) = -1 for a clamped-free Euler-Bernoulli beam.
    beta = 1.875104068711961
    theory = beta**2 / (2 * np.pi * length**2) * np.sqrt(young / (12 * density)) * np.array([thickness, width])
    return mesh, modes, theory


if __name__ == "__main__":
    print("tetrahedra  weak-axis Hz  strong-axis Hz  difference from beam theory (%)")
    for refinement in (3, 6, 9):
        mesh, modes, beam = cantilever_modes(refinement)
        difference = 100 * (modes.frequency / beam - 1)
        print(f"{mesh.num_tets:10d}  {modes.frequency[0]:12.3f}  {modes.frequency[1]:14.3f}"
              f"  {difference[0]:7.3f}  {difference[1]:7.3f}")
    print(f"Beam theory (Hz): {beam[0]:.3f}, {beam[1]:.3f}")
