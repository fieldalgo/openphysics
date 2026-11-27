# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Switch a DC heater on and off and follow its temperature and support loads."""

import numpy as np

from galerkin import box_mesh
from galerkin.electric3d import solve_steady_electric_3d
from galerkin.transient_heat3d import solve_transient_heat_3d
from galerkin.transient_thermoelasticity3d import solve_thermoelasticity_history_3d

LENGTH = 0.20  # m
WIDTH = 0.05  # m
VOLTAGE = 2.0  # V
ELECTRICAL_CONDUCTIVITY = 10.0  # S/m
THERMAL_CONDUCTIVITY = 2.0  # W/(m K)
VOLUMETRIC_HEAT_CAPACITY = 1000.0  # J/(m^3 K)
AMBIENT = 300.0  # K
YOUNG = 70e9  # Pa
EXPANSION = 1.2e-5  # 1/K
ON, OFF, END = 1, 3, 7  # s


def slab_reference(time, x, *, modes=401):
    """Return analytical rise (times, positions) and volume-mean rise (times), in K."""
    time = np.atleast_1d(time)
    x = np.atleast_1d(x)
    # Independent Ohm/Fourier model. This calculation does not take an FEM result.
    q = ELECTRICAL_CONDUCTIVITY * (VOLTAGE / LENGTH)**2
    odd = np.arange(1, 2 * modes, 2) * np.pi
    decay = THERMAL_CONDUCTIVITY / VOLUMETRIC_HEAT_CAPACITY * (odd / LENGTH)**2
    active_time = np.clip(time - ON, 0, OFF - ON)[:, None]
    cooling_time = np.maximum(time - OFF, 0)[:, None]
    coefficients = ((4 * q / VOLUMETRIC_HEAT_CAPACITY) / (odd * decay)
                    * -np.expm1(-active_time * decay) * np.exp(-cooling_time * decay))
    rise = coefficients @ np.sin(odd[:, None] * x / LENGTH)
    rise[:, (x == 0) | (x == LENGTH)] = 0
    return rise, coefficients @ (2 / odd)


def solve_heater_heat(nx=16, steps_per_second=16):
    """Return mesh, energized DC result and actual transient temperatures (SI)."""
    mesh = box_mesh(LENGTH, WIDTH, WIDTH, nx, 1, 1)
    electric = solve_steady_electric_3d(
        mesh, electrical_conductivity=ELECTRICAL_CONDUCTIVITY,
        prescribed_electric_potential={"x0": VOLTAGE, "x1": 0.0},
    )
    off_state = solve_steady_electric_3d(
        mesh, electrical_conductivity=ELECTRICAL_CONDUCTIVITY,
        prescribed_electric_potential={"x0": 0.0, "x1": 0.0},
    )

    def switched_source(t_mid_seconds):
        return electric.joule_power_density if ON <= t_mid_seconds < OFF else off_state.joule_power_density

    # Both integer switching times belong to this time grid for every resolution used.
    time = np.arange(END * steps_per_second + 1) / steps_per_second
    ends = np.concatenate([mesh.boundary["x0"], mesh.boundary["x1"]])
    heat = solve_transient_heat_3d(
        mesh, thermal_conductivity=THERMAL_CONDUCTIVITY,
        volumetric_heat_capacity=VOLUMETRIC_HEAT_CAPACITY, time=time,
        initial_temperature=np.full(mesh.num_nodes, AMBIENT),
        prescribed_temperature={int(node): AMBIENT for node in ends},
        heat_source_density=switched_source,
    )
    return mesh, electric, heat


def solve_heater_history(nx=16, steps_per_second=16, *, sample_indices=None):
    """Return the shared mesh, energized DC, transient heat and sampled solid histories."""
    mesh, electric, heat = solve_heater_heat(nx, steps_per_second)
    ends = np.concatenate([mesh.boundary["x0"], mesh.boundary["x1"]])
    fixed = {(int(node), 0): 0.0 for node in ends}
    fixed.update({(node, component): 0.0 for node in range(mesh.num_nodes) for component in (1, 2)})
    solid = solve_thermoelasticity_history_3d(
        mesh, time=heat.time, temperature=heat.temperature, sample_indices=sample_indices,
        stress_free_temperature=AMBIENT, linear_expansion_coefficient=EXPANSION,
        youngs_modulus=YOUNG, poisson_ratio=0.0, prescribed_displacement=fixed,
    )
    return mesh, electric, heat, solid


def axial_history(mesh, solid):
    """Return volume-mean axial stress (Pa) and left/right axial support forces (N)."""
    volumes = mesh.volumes()
    weights = volumes / volumes.sum()
    left, right = (mesh.boundary[tag] for tag in ("x0", "x1"))
    stress = np.array([weights @ state.stress[:, 0, 0] for state in solid.steps])
    reaction = np.array([[state.reaction_force[left, 0].sum(),
                          state.reaction_force[right, 0].sum()] for state in solid.steps])
    return stress, reaction


def main():
    mesh, electric, heat, solid = solve_heater_history()
    stress, reaction = axial_history(mesh, solid)
    midplane = mesh.nodes[:, 0] == LENGTH / 2
    center = heat.temperature[:, midplane].mean(axis=1) - AMBIENT
    exact_center, mean_rise = slab_reference(heat.time, [LENGTH / 2])
    exact_stress = -YOUNG * EXPANSION * mean_rise

    print(f"Energized terminal power: {electric.inward_electric_power:.9f} W")
    print(" time (s)  rise FE (K)  rise exact (K)  mean stress FE (MPa)  exact (MPa)   left (N)  right (N)")
    dt = heat.time[1] - heat.time[0]
    for t in (0, ON - dt, ON, ON + dt, OFF - dt, OFF, OFF + dt, END):
        i = int(np.flatnonzero(heat.time == t)[0])
        print(f"{t:9.5f} {center[i]:12.6f} {exact_center[i, 0]:15.6f} "
              f"{stress[i] / 1e6:21.6f} {exact_stress[i] / 1e6:12.6f} "
              f"{reaction[i, 0]:10.2f} {reaction[i, 1]:10.2f}")


if __name__ == "__main__":
    main()
