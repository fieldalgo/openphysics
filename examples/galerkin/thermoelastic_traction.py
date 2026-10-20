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
    result=solve_thermoelasticity(mesh,freeze_temperature(mesh,np.full(mesh.num_nodes,313.15)),
        reference_temperature_k=293.15,thermal_expansion_per_k=alpha,young_modulus=e,
        poisson_ratio=nu,plane='strain',dirichlet=bc,
        traction={tag:lambda points,n:n@s.T for tag in ('right','top','bottom')})
    print(json.dumps({'max_displacement_error_m':float(np.abs(result.displacement-exact).max()),
        'external_resultant_n_per_m':result.load_external.sum(0).tolist(),
        'reaction_resultant_n_per_m':result.reaction.sum(0).tolist(),
        'support_work_j_per_m':float(np.sum(result.displacement*result.reaction)),
        'physical_elastic_energy_j_per_m':result.physical_elastic_energy,
        'sigma_zz_range_pa':[float(result.sigma_zz.min()),float(result.sigma_zz.max())]},indent=2))


if __name__=='__main__':main()
