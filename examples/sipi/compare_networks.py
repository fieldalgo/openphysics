# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Synthetic file import and complex-S comparison; no measured coupon claim."""
from sipi import LineNetwork,rlgc_network
from sipi.touchstone import loads_touchstone,compare_networks

model=rlgc_network([0,1e6,1e9],R=[[2]],L=[[400e-9]],G=[[.001]],C=[[100e-12]],length=.1)
synthetic=LineNetwork(model.frequency,model.s*(1-.01j),model.z_ref,model.port_names)
loaded=loads_touchstone(synthetic.touchstone(),port_names=model.port_names)
comparison=compare_networks(loaded,model)
print('Synthetic comparison: model minus imported S')
print('Port order:',model.port_names)
print('Maximum absolute complex-S difference:',comparison.max_abs_error)
print('Frequency [Hz], S21 residual')
for f,residual in zip(model.frequency,comparison.delta_s[:,1,0]):
    print(f,residual)
