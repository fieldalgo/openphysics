# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Compare the cooling and loads of constant-voltage heaters with and without feedback."""

import numpy as np

from galerkin import box_mesh
from galerkin.temperature_joule_heating import ConductivityModel
from galerkin.transient_joule_heat3d import solve_transient_joule_heat_3d
from galerkin.transient_thermoelasticity3d import solve_thermoelasticity_history_3d
from transient_heater_3d import (
    AMBIENT, ELECTRICAL_CONDUCTIVITY, END, EXPANSION, LENGTH, OFF, ON,
    THERMAL_CONDUCTIVITY, VOLUMETRIC_HEAT_CAPACITY, VOLTAGE, WIDTH, YOUNG, axial_history,
)

BETA = 0.25  # 1/K, deliberately large so feedback is visible
TEMPERATURE_RANGE = (298.0, 320.0)  # K
CONVECTION = 40.0  # W/(m^2 K)


def resistive_conductivity(temperature):
    """Conductivity in S/m at temperature in K."""
    return ELECTRICAL_CONDUCTIVITY / (1 + BETA * (temperature - AMBIENT))


def uniform_temperature_rise(time):
    """Exact insulated constant-voltage temperature rise (K) from a cold start."""
    # P0/(C V) is sigma0*(voltage/length)^2/C. Use the stable quadratic root.
    dose = ELECTRICAL_CONDUCTIVITY * (VOLTAGE / LENGTH)**2 * np.asarray(time) / VOLUMETRIC_HEAT_CAPACITY
    return 2 * dose / (1 + np.sqrt(1 + 2 * BETA * dose))


def pulse_voltage(time):
    """Prescribed face voltages (V) at the interval midpoint (s)."""
    return {"x0": VOLTAGE if ON <= time < OFF else 0.0, "x1": 0.0}


def solve_heater(time, *, feedback=True, insulated=False, nx=12):
    """Return the mesh, coupled electrical/thermal histories and actual elastic states."""
    mesh = box_mesh(LENGTH, WIDTH, WIDTH, nx, 1, 1)
    sigma = (ConductivityModel(resistive_conductivity, TEMPERATURE_RANGE)
             if feedback else ELECTRICAL_CONDUCTIVITY)
    fixed_temperature = (None if insulated
                         else {int(node): AMBIENT for node in mesh.boundary["x0"]})
    convection = None if insulated else {"x1": (CONVECTION, AMBIENT)}
    electrical_bc = {"x0": VOLTAGE, "x1": 0.0} if insulated else pulse_voltage
    coupled = solve_transient_joule_heat_3d(
        mesh, time=time, initial_temperature=np.full(mesh.num_nodes, AMBIENT),
        electrical_conductivity=sigma, prescribed_electric_potential=electrical_bc,
        thermal_conductivity=THERMAL_CONDUCTIVITY, volumetric_heat_capacity=VOLUMETRIC_HEAT_CAPACITY,
        prescribed_temperature=fixed_temperature, convection=convection,
        temperature_tolerance=1e-10, relative_tolerance=1e-10,
    )
    ends = np.r_[mesh.boundary["x0"], mesh.boundary["x1"]]
    fixed = {(int(node), 0): 0.0 for node in ends}
    fixed.update({(node, component): 0.0 for node in range(mesh.num_nodes) for component in (1, 2)})
    solid = solve_thermoelasticity_history_3d(
        mesh, time=coupled.heat.time, temperature=coupled.heat.temperature,
        stress_free_temperature=AMBIENT, linear_expansion_coefficient=EXPANSION,
        youngs_modulus=YOUNG, poisson_ratio=0.0, prescribed_displacement=fixed,
    )
    return mesh, coupled, solid


def interval_power(coupled):
    """Electrical input in W, one value per interval aligned with heat.time[1:]."""
    return np.array([state.inward_electric_power for state in coupled.electric])


def main():
    time = np.arange(END * 16 + 1) / 16
    for label, feedback in (("temperature dependent", True), ("constant", False)):
        mesh, coupled, solid = solve_heater(time, feedback=feedback)
        heat = coupled.heat
        stress, reaction = axial_history(mesh, solid)
        power = interval_power(coupled)
        energy = np.r_[0., np.cumsum(np.diff(time) * power)]
        peak_rise = heat.temperature.max(axis=1) - AMBIENT
        print(f"\n{label}")
        print("time (s)  prior power (W)  input (J)  peak rise (K)  mean stress (MPa)  left force (N)")
        for t in (ON, ON + 1/16, OFF, OFF + 1/16, END):
            i = int(np.flatnonzero(time == t)[0])
            print(f"{t:8.4f} {power[i - 1]:16.6f} {energy[i]:10.6f} "
                  f"{peak_rise[i]:14.6f} {stress[i]/1e6:17.6f} {reaction[i, 0]:15.2f}")


if __name__ == "__main__":
    main()
