# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""A 2 W heater on a ceramic substrate with a finite thermal contact resistance."""
import numpy as np

from galerkin.mesh3d import Mesh3D, box_mesh
from galerkin.thermal3d import solve_steady_heat_3d


LENGTH, WIDTH = 0.010, 0.008  # m
HEATER_THICKNESS, SUBSTRATE_THICKNESS = 0.0005, 0.0015  # m
POWER, SINK_TEMPERATURE = 2.0, 300.0  # W, K
CONTACT = ("heater_z0", "substrate_z1")


def heater_stack():
    """Build matching interface triangles with separate node IDs on each side."""
    substrate = box_mesh(LENGTH, WIDTH, SUBSTRATE_THICKNESS, 8, 6, 4)
    heater = box_mesh(LENGTH, WIDTH, HEATER_THICKNESS, 8, 6, 4)
    shift = substrate.num_nodes
    faces = {"substrate_" + tag: triangles for tag, triangles in substrate.tagged_faces.items()}
    faces.update({"heater_" + tag: triangles + shift for tag, triangles in heater.tagged_faces.items()})
    return Mesh3D(np.vstack([substrate.nodes, heater.nodes + [0, 0, SUBSTRATE_THICKNESS]]),
                  np.vstack([substrate.tets, heater.tets + shift]),
                  regions=np.repeat([0, 1], [substrate.num_tets, heater.num_tets]),
                  region_names=["substrate", "heater"], tagged_faces=faces)


def solve_heater_stack(mesh, contact_conductance):
    """Apply uniform heat generation in the heater and hold the substrate base at 300 K."""
    heater_volume = LENGTH * WIDTH * HEATER_THICKNESS
    return solve_steady_heat_3d(
        mesh, thermal_conductivity={"substrate": 25.0, "heater": 120.0},  # W/(m K)
        prescribed_temperature={node: SINK_TEMPERATURE for node in mesh.boundary["substrate_z0"]},
        heat_source_density={"substrate": 0.0, "heater": POWER / heater_volume},
        thermal_contact_conductance={CONTACT: contact_conductance},  # W/(m² K)
    )


if __name__ == "__main__":
    mesh = heater_stack()
    heater_face, substrate_face = (mesh.tagged_faces[tag] for tag in CONTACT)
    print("2 W over 80 mm², 300 K substrate base, insulated top and sides")
    print("h (W/m²/K)   1/h (m² K/W)   FE jump (K)   Q/(A h) (K)   peak (K)   heater out (W)   substrate out (W)")
    for h in (500.0, 5000.0, 50000.0):
        result = solve_heater_stack(mesh, h)
        # Equal-area triangles: averaging their vertex temperatures gives the area mean.
        jump = result.temperature[heater_face].mean() - result.temperature[substrate_face].mean()
        exact_jump = POWER / (LENGTH * WIDTH * h)
        heater_out, substrate_out = (result.contact_heat_rate[mesh.boundary[tag]].sum() for tag in CONTACT)
        print(f"{h:10.0f}   {1/h:13.2e}   {jump:11.3f}   {exact_jump:12.3f}   {result.temperature.max():8.3f}"
              f"   {heater_out:+14.6f}   {substrate_out:+17.6f}")
