# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Uniform uniaxial edge traction, per out-of-plane thickness in SI units."""
import numpy as np
from galerkin.mesh import rectangle_mesh
from galerkin.elasticity import solve_elasticity


def main():
    mesh = rectangle_mesh(1.2, .7, 12, 7)
    bc = {(int(i), 0): 0. for i in mesh.boundary["left"]}
    bc.update({(int(i), 1): 0. for i in mesh.boundary["bottom"]})
    for plane in ("stress", "strain"):
        r = solve_elasticity(mesh, young_modulus=70000., poisson_ratio=.3,
                             plane=plane, dirichlet=bc, traction={"right": (123., 0.)})
        energy = .5*np.sum(mesh.areas()*np.sum(r.strain*r.stress, axis=1))
        work = .5*np.sum(r.displacement*(r.load+r.reaction))
        print(plane, "max ux (m):", r.displacement[:, 0].max())
        print("load / reaction per thickness (N/m):", r.load.sum(axis=0), r.reaction.sum(axis=0))
        print("energy / proportional external work per thickness (J/m):", energy, work)


if __name__ == "__main__":
    main()
