# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Constant-Q Dirichlet/Robin slab; run from the repository root."""
import numpy as np
from galerkin.mesh import rectangle_mesh
from galerkin.thermal import solve_steady_heat
from refsol.thermal_boundary import dirichlet_robin_slab


def main():
    mesh=rectangle_mesh(1.,.8,16,12)
    result=solve_steady_heat(mesh,thermal_conductivity=2.5,
        prescribed_temperature={int(i):320. for i in mesh.boundary['left']},heat_source_density=5.,
        inward_heat_flux={'right':-.7},convection={'right':(10.,300.)})
    reference=dirichlet_robin_slab(length=1.,thermal_conductivity=2.5,prescribed_temperature=320.,
                                 heat_source_density=5.,inward_heat_flux=-.7,heat_transfer_coefficient=10.,
                                 ambient_temperature=300.)
    print('Maximum nodal temperature error (K):',np.max(abs(result.temperature-reference.temperature(mesh.nodes))))
    rates=(result.generated_heat_rate_per_depth,result.reaction_heat_rate_per_depth,
           result.outward_prescribed_heat_rate_per_depth,result.outward_convective_heat_rate_per_depth)
    print('Source / thermostat injection / prescribed outward / convective outward (W/m):',
          *(float(sum(x)) for x in rates))
    imbalance=sum(rates[0]+rates[1]-rates[2]-rates[3])
    print('Heat imbalance (W/m):',imbalance)


if __name__=='__main__':main()
