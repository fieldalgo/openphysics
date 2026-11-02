# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""A chip package as a layered tetrahedral mesh, without Gmsh.

Substrate 10 x 10 x 1, a 4 x 4 x 0.5 die centred on it, mold around and over
the die up to z = 2.5. meshine meshes the footprint, ``extrude`` stacks it, and
the result goes straight to galerkin, here for a steady heat solve with the die
as a poor conductor.

Run from the repository root:
      pip install -e packages/meshine -e packages/galerkin
      python3 examples/meshine/extrude_chip.py [out.msh]
"""

import sys

import numpy as np

from meshine import Domain, box_sides, check, extrude, generate, rectangle, write_msh

d = Domain(size=0.8)
d.add_region("die_zone", rectangle(-2, -2, 2, 2))
d.add_region("rest", rectangle(-5, -5, 5, 5), holes=[rectangle(-2, -2, 2, 2)])
footprint = generate(d, box_sides(-5, 5, -5, 5))

mesh = check(extrude(footprint, [0.0, 1.0, 1.5, 2.5],
                     {"die_zone": ["substrate", "die", "mold"],
                      "rest": ["substrate", "mold", "mold"]},
                     size=0.4))
print(mesh)
for name in mesh.region_names:
    print(f"  {name:10s} volume {mesh.region_volume(name):8.4f}")
print("  tags:", sorted(mesh.boundary_faces), " interfaces:", sorted(mesh.interfaces))
print(f"  min dihedral {mesh.min_dihedral():.1f} deg, mean quality {mesh.quality().mean():.3f}")

try:
    from galerkin import assemble_stiffness_3d, from_mesher, solve_dirichlet
except ImportError:
    print("galerkin not installed: skipping the heat solve")
else:
    kappa = {"substrate": 150.0, "die": 1.0, "mold": 0.8}           # W/(m K), illustrative
    g = from_mesher(mesh)
    K = assemble_stiffness_3d(g, eps=np.array([kappa[n] for n in mesh.region_names])[mesh.regions])
    T = solve_dirichlet(K, np.zeros(g.num_nodes),
                        {tuple(mesh.boundary_nodes["z0"]): 0.0, tuple(mesh.boundary_nodes["z1"]): 1.0})
    print(f"  temperature at the die centre: {T[np.argmin(np.linalg.norm(mesh.nodes - [0, 0, 1.25], axis=1))]:.4f}")

if len(sys.argv) > 1:
    print("wrote", write_msh(mesh, sys.argv[1]))
