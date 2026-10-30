# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""High-frequency smooth-metal loss, including the reference-plane return."""
import numpy as np
from sipi import coupled_microstrip
from sipi.conductor import surface_conductor_loss

section = coupled_microstrip(width=.5e-3, gap=.3e-3, substrate_height=1e-3,
                            thickness=50e-6, eps_r=4)
mesh = dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05)
frequency = np.array([1e9, 4e9, 10e9])
loss = surface_conductor_loss(section, frequency, conductivity=58e6,
                             ground_thickness=35e-6, **mesh)
dielectric = section.analyze(**mesh)
network = loss.network(C=dielectric.C, G=np.zeros((2, 2)), length=.03)
print('Smooth metal, constant lossless dielectric; high-frequency perturbation')
print(f'Integrated-current maximum discrepancy: {loss.factors.current_error:.4%}')
print('GHz       R11 ohm/m    R12 ohm/m    internal L11 nH/m    |S(far1,near1)|')
for index, frequency_hz in enumerate(frequency):
    print(f'{frequency_hz/1e9:4.1f} {loss.R[index,0,0]:14.7g} {loss.R[index,0,1]:12.7g}'
          f' {loss.L_internal[index,0,0]*1e9:21.7g} {abs(network.s[index,2,0]):17.8g}')
