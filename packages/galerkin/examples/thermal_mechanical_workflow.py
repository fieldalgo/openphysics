# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit SI linear conduction then same-mesh plane-strain expansion."""
import json
import numpy as np
from galerkin.mesh import rectangle_mesh
from galerkin.thermal_mechanical import solve_steady_thermoelasticity


def main():
    n=8;mesh=rectangle_mesh(1.,1.,n,n)
    thermal={int(i):303.15 for i in mesh.boundary['left']}
    thermal.update({int(i):323.15 for i in mesh.boundary['right']})
    result=solve_steady_thermoelasticity(mesh,units={'length':'m','temperature':'K'},
        conductivity=10.,thermal_dirichlet=thermal,young_modulus=70e9,
        poisson_ratio=.3,plane='strain',thermal_expansion_per_k=12e-6,
        reference_temperature_k=293.15,
        mechanical_dirichlet={(0,0):0.,(0,1):0.,(n,1):0.})
    print(json.dumps({'temperature_range_k':[float(result.heat.temperature.min()),float(result.heat.temperature.max())],
        'net_outward_heat_w_per_m':float(-result.heat.reaction.sum()),
        'max_displacement_m':float(np.linalg.norm(result.mechanics.displacement,axis=1).max()),
        'sigma_zz_range_pa':[float(result.mechanics.sigma_zz.min()),float(result.mechanics.sigma_zz.max())],
        'physical_elastic_energy_j_per_m':result.mechanics.physical_elastic_energy,
        'stages':result.manifest['stages'],'authentication':result.manifest['authentication']},indent=2))


if __name__=='__main__':main()
