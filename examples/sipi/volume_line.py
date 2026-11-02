# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Reproduce matched finite-metal/dielectric RLGC from a versioned JSON input."""
from sipi import CrossSectionDocument, microstrip
from sipi.volume_line import VolumeLineDocument

section = microstrip(width=.4e-3, substrate_height=.5e-3, thickness=.1e-3,
                     eps_r=4, tan_delta=.02, air_height=.5e-3, box_width=2e-3)
doc = VolumeLineDocument(CrossSectionDocument(section), [0, 1e3, 1e5],
    materials={}, conductivity=58e6, relative_permeability=1, length=.1, z_ref=50,
    mesh=dict(ground_thickness=.1e-3, padding=2e-3, metal_size=12.5e-6,
              far_size=.125e-3, grade=.05, min_angle=28))
restored = VolumeLineDocument.loads(doc.dumps())
assert restored.to_dict() == doc.to_dict()
result = restored.analyze()
print('f [Hz], R [ohm/m], total L [H/m], G [S/m], C [F/m], S21')
for i, frequency in enumerate(result.frequency):
    print(frequency, result.R[i, 0, 0], result.L[i, 0, 0], result.G[i, 0, 0],
          result.C[i, 0, 0], result.network.s[i, 1, 0])
print('Finite dielectric box in vacuum; finite metal reference plates.')
print('Refine both meshes and outer padding for each new geometry/frequency range.')
