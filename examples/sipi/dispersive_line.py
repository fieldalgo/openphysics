# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Layered dielectric dispersion with explicit perfect-conductor assumption."""
import numpy as np
from sipi import microstrip
from sipi.dielectric import WidebandDielectric, dispersive_line

section = microstrip(width=.5e-3, substrate_height=1e-3, thickness=.05e-3, eps_r=4)
material = WidebandDielectric(4, .02, 1e9)
result = dispersive_line(section, [1e6, 1e8, 1e9, 1e10],
    materials={'substrate':material}, edge_size=10e-6, far_size=.4e-3, grade=.2)
network = result.network(length=.1, R=np.zeros((1,1)))
print('Perfect conductors; quasi-TEM; assess material validity and mesh/domain errors separately.')
print('f_Hz eps_real eps_loss C_pF_per_m G_mS_per_m abs_S21')
for i, f in enumerate(result.frequency):
    eps = result.layer_permittivity['substrate'][i]
    print(f'{f:.6g} {eps.real:.8g} {-eps.imag:.8g} {result.C[i,0,0]*1e12:.8g} '
          f'{result.G[i,0,0]*1e3:.8g} {abs(network.s[i,1,0]):.8g}')
