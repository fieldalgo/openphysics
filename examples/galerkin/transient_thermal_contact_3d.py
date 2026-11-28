# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Run a one-second voltage pulse on a heater in finite thermal contact with a ceramic substrate."""
import numpy as np

from galerkin.transient_joule_heat3d import solve_transient_joule_heat_3d

if __package__:
    from .thermal_contact_3d import CONTACT, LENGTH, SINK_TEMPERATURE, WIDTH, heater_stack, solve_heater_stack
else:
    from thermal_contact_3d import CONTACT, LENGTH, SINK_TEMPERATURE, WIDTH, heater_stack, solve_heater_stack


CONTACT_CONDUCTANCE = 5000.0  # W/(m² K)
VOLUMETRIC_HEAT_CAPACITY = {"substrate": 3.0e6, "heater": 1.65e6}  # J/(m³ K)
SWITCH_OFF = 1.0  # s


def solve_heater_pulse(time):
    """Return the split-node mesh and coupled histories; include 1 s in the supplied time grid."""
    mesh = heater_stack()

    def voltage(midpoint):
        # The substrate has its own zero-potential reference and carries no current.
        return {"substrate_x0": 0.0, "heater_x0": 1.0 if midpoint < SWITCH_OFF else 0.0, "heater_x1": 0.0}

    coupled = solve_transient_joule_heat_3d(
        mesh, time=time, initial_temperature=np.full(mesh.num_nodes, SINK_TEMPERATURE),
        electrical_conductivity={"substrate": 1.0, "heater": 5000.0},  # S/m
        prescribed_electric_potential=voltage, thermal_conductivity={"substrate": 25.0, "heater": 120.0},
        volumetric_heat_capacity=VOLUMETRIC_HEAT_CAPACITY, thermal_contact_conductance={CONTACT: CONTACT_CONDUCTANCE},
        prescribed_temperature=dict.fromkeys(mesh.boundary["substrate_z0"], SINK_TEMPERATURE),
        temperature_tolerance=1e-10,
    )
    return mesh, coupled


if __name__ == "__main__":
    time = np.arange(33) / 16  # s, dt = 1/16 s
    mesh, coupled = solve_heater_pulse(time)
    heat = coupled.heat
    power = np.array([step.inward_electric_power for step in coupled.electric])
    energy = np.cumsum(np.diff(time) * power)
    # All contact triangles have equal area. Average their three vertex temperatures.
    heater_face, substrate_face = (mesh.tagged_faces[tag] for tag in CONTACT)
    heater = heat.temperature[1:, heater_face].mean(axis=(1, 2))
    substrate = heat.temperature[1:, substrate_face].mean(axis=(1, 2))
    rate = heat.contact_heat_rate[:, mesh.boundary[CONTACT[0]]].sum(axis=1)
    print("1 V for 1 s, then 0 V; h = 5000 W/(m² K), substrate base at 300 K")
    print("end (s)  input (W)  input (J)  heater face (K)  substrate face (K)  contact out (W)  mean flux (W/m²)")
    for i in (0, 7, 15, 16, 23, 31):
        print(f"{time[i+1]:7.4f}  {power[i]:9.4f}  {energy[i]:9.4f}  {heater[i]:15.5f}  {substrate[i]:18.5f}"
              f"  {rate[i]:15.6f}  {rate[i]/(LENGTH*WIDTH):16.3f}")
    steady = solve_heater_stack(mesh, CONTACT_CONDUCTANCE)
    jump = steady.temperature[heater_face].mean() - steady.temperature[substrate_face].mean()
    print(f"With sustained 2 W input, the steady contact jump is {jump:.3f} K.")
