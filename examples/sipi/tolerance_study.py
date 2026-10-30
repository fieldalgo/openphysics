# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""A fixed-pitch coupled sweep; refine each geometry before design acceptance."""
from sipi.study import ImpedanceStudyDocument

plan = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.4e-3, gap=.3e-3, substrate_height=.5e-3, eps_r=4,
         thickness=0, air_height=1e-3, box_width=4e-3),
    sampling=dict(kind='sweep', count=3,
                  variables=[dict(name='width', lower=.35e-3, upper=.45e-3)]),
    quantity='z_diff', fixed_pitch_m=.7e-3,
    mesh=dict(edge_size=.1e-3, far_size=.4e-3, grade=.3))
restored = ImpedanceStudyDocument.loads(plan.dumps())
result = restored.analyze()
for row in result.rows:
    print('width/gap [m]:', row.parameters['width'], row.parameters['gap'],
          'Zdiff [ohm]:', row.impedance, 'error:', row.error)
print('Sample summary only; not guaranteed manufacturing bounds:', result.summary)
print('Resolved nominal mesh settings are reused; per-sample convergence is not established.')
