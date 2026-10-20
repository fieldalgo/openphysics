# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Constant-Q Dirichlet/Robin slab; run from the repository root."""
import numpy as np
from galerkin.mesh import rectangle_mesh
from galerkin.thermal import solve_steady_heat
from refsol.thermal_boundary import dirichlet_robin_slab


def main():
    mesh=rectangle_mesh(1.,.8,16,12)
    result=solve_steady_heat(mesh,conductivity=2.5,
        dirichlet={int(i):320. for i in mesh.boundary['left']},heat_source=5.,
        outward_flux={'right':.7},convection={'right':(10.,300.)})
    reference=dirichlet_robin_slab(length=1.,conductivity=2.5,left_temperature=320.,
                                 heat_source=5.,outward_flux=.7,h=10.,ambient=300.)
    print('Maximum nodal temperature error (K):',np.max(abs(result.temperature-reference.temperature(mesh.nodes))))
    print('Source / thermostat injection / prescribed outward / convective outward (W/m):',
          *(float(sum(x)) for x in (result.load,result.reaction,result.prescribed_outward_load,result.convective_outward)))
    imbalance=sum(result.load+result.reaction-result.prescribed_outward_load-result.convective_outward)
    print('Heat imbalance (W/m):',imbalance)


if __name__=='__main__':main()
