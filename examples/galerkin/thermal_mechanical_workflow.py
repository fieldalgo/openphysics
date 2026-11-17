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
    result=solve_steady_thermoelasticity(mesh,thermal_conductivity=10.,prescribed_temperature=thermal,
        youngs_modulus=70e9,poisson_ratio=.3,plane='strain',linear_expansion_coefficient=12e-6,
        stress_free_temperature=293.15,
        prescribed_displacement={(0,0):0.,(0,1):0.,(n,1):0.})
    print(json.dumps({'temperature_range_k':[float(result.heat.temperature.min()),float(result.heat.temperature.max())],
        'net_outward_heat_w_per_m':float(-result.heat.reaction_heat_rate_per_depth.sum()),
        'max_displacement_m':float(np.linalg.norm(result.mechanics.displacement,axis=1).max()),
        'sigma_zz_range_pa':[float(result.mechanics.stress_zz.min()),float(result.mechanics.stress_zz.max())],
        'physical_elastic_energy_j_per_m':result.mechanics.strain_energy_per_depth,
        'stages':result.manifest['stages'],'authentication':result.manifest['authentication']},indent=2))


if __name__=='__main__':main()
