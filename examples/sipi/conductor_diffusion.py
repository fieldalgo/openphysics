# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""DC/AC metal-volume extraction with explicit finite ground and magnetic box."""
from sipi import microstrip
from sipi.conductor_mesh import mesh_conductor_section

section = microstrip(width=.4e-3, substrate_height=.5e-3, thickness=.1e-3,
                     eps_r=4, air_height=.5e-3, box_width=2e-3)
volume = mesh_conductor_section(section, ground_thickness=.1e-3, padding=2e-3,
                               metal_size=25e-6, far_size=.25e-3, grade=.1)
series = volume.impedance([0, 1e3, 1e5], conductivity=58e6)
print(f'Magnetic volume mesh: {volume.mesh.num_nodes} nodes')
print('f [Hz]      R [ohm/m]     total L [H/m]    max edge / skin depth')
for f, r, inductance, ratio in zip(series.frequency, series.R[:, 0, 0],
                                  series.L[:, 0, 0], series.max_edge_over_skin_depth):
    print(f'{f:9.1f}   {r:.9g}   {inductance:.9g}   {ratio:.6g}')
print('Maximum current residual [A]:', max(series.current_error))
print('Maximum relative Joule residual:', max(series.power_error))
print('Maximum relative magnetic-energy residual:', max(series.magnetic_energy_error))
print('Refine the metal/exterior mesh and magnetic padding separately.')
print('No automatic dielectric C/G matching or volume JSON is implied.')
