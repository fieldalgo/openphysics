# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Save and restore a complete RLGC circuit, including source and load."""
from sipi.circuit_document import CircuitDocument

source = dict(kind='rlgc', frequency_hz=[0, 1e6, 1e9],
              R=[[10]], L=[[400e-9]], G=[[0]], C=[[100e-12]],
              length_m=1, reference_ohms=50, names=['signal'])
doc = CircuitDocument(source,
    excitation={'kind': 'sources', 'voltages': {'near:signal': 1}},
    terminations={'near:signal': 50, 'far:signal': 100})
saved_text = doc.dumps()  # The caller may write this text to its chosen file.
restored = CircuitDocument.loads(saved_text)
result = restored.analyze()
assert restored.dumps() == saved_text
print('Port order:', result.network.port_names)
for f, voltage, current in zip(result.network.frequency, result.response.voltage, result.response.current):
    print(f'{f:g} Hz: V={voltage}, I_into_network={current}')
print('DC network dissipation (W):', result.response.network_power[0])
