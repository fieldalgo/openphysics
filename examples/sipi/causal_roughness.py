# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Causal surface roughness and replayable coupled-line input, SI units."""
from sipi import CrossSectionDocument, coupled_microstrip
from sipi.line_model import TransmissionLineDocument

geometry = CrossSectionDocument(
    coupled_microstrip(width=.5e-3,gap=.3e-3,substrate_height=1e-3,
                       thickness=50e-6,eps_r=4),
    mesh=dict(edge_size=5e-6,far_size=.2e-3,grade=.1))
model = TransmissionLineDocument(
    geometry,[1e9,4e9,10e9],materials={},length=.03,
    conductor=dict(kind='surface',conductivity=58e6,ground_thickness=35e-6,
        relative_permeability=1,roughness=dict(kind='causal-huray',
            radii_m=[.5e-6,1.5e-6],surface_ratios=[1.2,.3])),
    schema='sipi.transmission-line/2')
result = TransmissionLineDocument.loads(model.dumps()).analyze()
print('frequency_Hz, R11_ohm_per_m, L_internal11_H_per_m, resistance_ratio')
for f,r,l,k in zip(result.frequency,result.R[:,0,0],
                  result.conductor.L_internal[:,0,0],result.conductor.roughness_factor):
    print(f'{f:.9g}, {r:.9g}, {l:.9g}, {k:.9g}')
print('surface_current_error:',result.conductor.factors.current_error)
print('Illustrative constitutive input; not a measured foil fit.')
