# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Replay a dispersive, rough coupled line with explicit mismatched loads."""
from sipi import CrossSectionDocument, coupled_microstrip
from sipi.circuit_document import CircuitDocument
from sipi.dielectric import WidebandDielectric
from sipi.line_model import TransmissionLineDocument

section = coupled_microstrip(width=.5e-3, gap=.3e-3, substrate_height=1e-3,
                             thickness=50e-6, eps_r=4)
geometry = CrossSectionDocument(section, mesh=dict(edge_size=5e-6, far_size=.2e-3, grade=.1))
line = TransmissionLineDocument(geometry, [1e9, 4e9, 10e9], length=.03,
    materials={'substrate': WidebandDielectric(4, .02, 1e9)},
    conductor=dict(kind='surface', conductivity=58e6, ground_thickness=35e-6,
        relative_permeability=1, roughness=dict(kind='causal-huray',
            radii_m=[.5e-6, 1.5e-6], surface_ratios=[1.2, .3])),
    schema='sipi.transmission-line/2')
a, victim = [trace.name for trace in section.traces if not trace.ground]
circuit = CircuitDocument(dict(kind='transmission-line', document=line.to_dict()),
    excitation=dict(kind='crosstalk', aggressor='near:'+a,
                    near_victim='near:'+victim, far_victim='far:'+victim),
    terminations={'near:'+a: 40, 'near:'+victim: 55,
                  'far:'+a: {'real': 75, 'imag': 5},
                  'far:'+victim: {'real': 100, 'imag': -10}})
result = CircuitDocument.loads(circuit.dumps()).analyze()
print('frequency_Hz, NEXT_incident_voltage_ratio, FEXT_incident_voltage_ratio')
for f,n,x in zip(result.network.frequency, result.crosstalk.next_ratio, result.crosstalk.fext_ratio):
    print(f'{f:.9g}, {n:.9g}, {x:.9g}')
print('Illustrative frequency-domain model; not measured coupon or peak-time crosstalk.')
