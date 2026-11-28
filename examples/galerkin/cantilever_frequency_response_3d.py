# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Sweep a clamped beam through its first bending resonance under a 1 N harmonic end load."""
import numpy as np

from galerkin.mesh3d import box_mesh
from galerkin.structural_harmonic3d import solve_structural_harmonic_3d
from galerkin.structural_modes3d import solve_structural_modes_3d


def cantilever_frequency_response(frequency=None, *, refinement=6):
    """Return the first natural frequency (Hz), solver result and mean downward tip displacement (m)."""
    length, width, thickness = 0.12, 0.018, 0.012  # m
    mesh = box_mesh(length, width, thickness, 8 * refinement, refinement, refinement)
    clamp = {(node, axis): 0.0 for node in mesh.boundary["x0"] for axis in range(3)}
    material = dict(youngs_modulus=70e9, poisson_ratio=0.0, mass_density=2700.0,
                    prescribed_displacement=clamp)
    first = solve_structural_modes_3d(mesh, **material).frequency[0]
    if frequency is None:
        frequency = first * np.array([0.0, 0.5, 0.9, 1.0, 1.1, 1.5])
    # A uniform traction on the tip face gives a net 1 N force along -z.
    # With stiffness-proportional damping, zeta_1 = beta * omega_1 / 2.
    response = solve_structural_harmonic_3d(
        mesh, **material, frequency=frequency, traction={"x1": (0.0, 0.0, -1.0 / (width * thickness))},
        stiffness_proportional_damping_coefficient=2 * 0.02 / (2 * np.pi * first),
    )
    # Each tip triangle has the same area. Its mean linear displacement is its vertex average.
    downward_tip = -response.displacement[:, mesh.tagged_faces["x1"], 2].mean(axis=(1, 2))
    return first, response, downward_tip


if __name__ == "__main__":
    first, response, tip = cantilever_frequency_response()
    print(f"First bending mode: {first:.2f} Hz, 2% modal damping")
    print("frequency (Hz)   mean tip amplitude (um)   lag behind downward load (deg)")
    # Re[U exp(-i omega t)] lags a real positive load by arg(U).
    for frequency, displacement in zip(response.frequency, tip):
        lag = f"{np.angle(displacement, deg=True):.2f}" if frequency > 0 else "static"
        print(f"{frequency:14.2f}   {1e6 * abs(displacement):23.3f}   {lag:>30}")
