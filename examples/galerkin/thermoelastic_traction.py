# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit prescribed Kelvin field and TOTAL Cartesian traction, no heat solve."""
import json
import numpy as np
from galerkin.mesh import rectangle_mesh
from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity


def main():
    mesh=rectangle_mesh(1.,1.,8,8)
    e,nu,alpha,theta=70e9,.3,12e-6,20.
    s=np.array([[8e6,3e6],[3e6,-2e6]])
    em=(1+nu)/e*np.array([(1-nu)*s[0,0]-nu*s[1,1],
                              (1-nu)*s[1,1]-nu*s[0,0],2*s[0,1]])
    strain=em+(1+nu)*alpha*theta*np.array([1.,1.,0.])
    exact=np.column_stack([strain[0]*mesh.nodes[:,0]+strain[2]*mesh.nodes[:,1],
                           strain[1]*mesh.nodes[:,1]])+[2e-5,-1e-5]
    bc={(int(i),j):exact[i,j] for i in mesh.boundary['left'] for j in (0,1)}
    result=solve_thermoelasticity(mesh,freeze_temperature(mesh,temperature=np.full(mesh.num_nodes,313.15)),
        stress_free_temperature=293.15,linear_expansion_coefficient=alpha,youngs_modulus=e,
        poisson_ratio=nu,plane='strain',prescribed_displacement=bc,
        traction={tag:lambda points,n:n@s.T for tag in ('right','top','bottom')})
    print(json.dumps({'max_displacement_error_m':float(np.abs(result.displacement-exact).max()),
        'external_resultant_n_per_m':result.applied_force_per_depth.sum(0).tolist(),
        'reaction_resultant_n_per_m':result.reaction_force_per_depth.sum(0).tolist(),
        'support_work_j_per_m':float(np.sum(result.displacement*result.reaction_force_per_depth)),
        'physical_elastic_energy_j_per_m':result.strain_energy_per_depth,
        'sigma_zz_range_pa':[float(result.stress_zz.min()),float(result.stress_zz.max())]},indent=2))


if __name__=='__main__':main()
