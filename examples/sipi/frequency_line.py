# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""One saved model for dielectric dispersion, metal loss and network propagation."""
import numpy as np
from sipi import CrossSectionDocument, coupled_microstrip
from sipi.dielectric import WidebandDielectric
from sipi.line_model import TransmissionLineDocument

geometry = CrossSectionDocument(
    coupled_microstrip(width=.5e-3,gap=.3e-3,substrate_height=1e-3,
                       thickness=50e-6,eps_r=4),
    mesh=dict(edge_size=5e-6,far_size=.2e-3,grade=.1))
model = TransmissionLineDocument(geometry,[1e9,4e9,10e9],
    materials={'substrate':WidebandDielectric(4,.02,1e9)},
    conductor=dict(kind='surface',conductivity=58e6,ground_thickness=35e-6,
                   relative_permeability=1,roughness_rms=1e-6),
    length=.03,z_ref=50)
result = TransmissionLineDocument.loads(model.dumps()).analyze()
print('Illustrative material and high-frequency metal model; SI matrices per metre')
print('GHz      R11 ohm/m     L11 nH/m     G11 S/m     C11 pF/m    Sdd21 loss dB')
mixed = result.network.mixed_mode()
for index,f in enumerate(result.frequency):
    print(f'{f/1e9:4.1f} {result.R[index,0,0]:14.7g} {result.L[index,0,0]*1e9:13.7g}'
          f' {result.G[index,0,0]:11.7g} {result.C[index,0,0]*1e12:12.7g}'
          f' {-20*np.log10(abs(mixed.s[index,1,0])):16.7g}')
print(f'Integrated-current discrepancy: {result.conductor.factors.current_error:.4%}')
