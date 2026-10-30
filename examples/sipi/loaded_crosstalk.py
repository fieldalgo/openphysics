# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Synthetic coupled RLGC example; explicit source and victim terminations."""
import numpy as np
from sipi import rlgc_network
from sipi.termination import loaded_crosstalk

net = rlgc_network([1e6, 1e8, 1e9], R=[[4, .4], [.4, 4]],
                   L=np.array([[300, 60], [60, 300]])*1e-9,
                   G=[[.004, -.001], [-.001, .004]],
                   C=np.array([[120, -30], [-30, 120]])*1e-12, length=.2)
result = loaded_crosstalk(net, aggressor='near:1', near_victim='near:2', far_victim='far:2',
                          terminations={'near:1': 25+10j, 'near:2': 50, 'far:1': 50, 'far:2': 100})
print('Synthetic input RLGC; ratios relative to actual aggressor incident voltage')
for f, near, far in zip(net.frequency, result.next_ratio, result.fext_ratio):
    print(f'{f:g} Hz: NEXT={near:.8g}, FEXT={far:.8g}')
print('Maximum normalized KVL residual:', max(result.response.kvl_residual))
print('Maximum power-balance error (W):', max(abs(result.response.source_power
      - result.response.network_power-result.response.termination_power)))
