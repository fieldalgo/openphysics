# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""What the box cavity solvers share: the speed of light, numerical gates and the box mesh.

Package-private: galerkin.cavity and galerkin.material_cavity import these
names so that neither imports the other's private helpers.
"""
import numpy as np

from .mesh3d import Mesh3D, box_mesh

C0 = 299792458.0
RESIDUAL_LIMIT = 1e-8
GRADIENT_LIMIT = 1e-9
DENSE_LIMIT = 256


def cavity_mesh(lengths, cells):
    """Alternate Kuhn diagonals without changing cells, vertices or tet shapes.

    Reflect local coordinates along axis a whenever the cell index on a is odd.
    Two cells sharing a face have the same tangential parities, hence the same
    face diagonal: this is a conforming triangulation. Even subdivision counts
    restore coordinate-reflection symmetry across the box. No refinement or
    spectral information enters the mesh construction.
    """
    base = box_mesh(*lengths, *cells)
    shape = tuple(n + 1 for n in cells)
    grid = np.stack(np.unravel_index(base.tets, shape), axis=-1)
    lower = grid.min(axis=1)[:, None, :]
    local = grid - lower
    reflected = lower + np.where(lower % 2, 1 - local, local)
    tets = (reflected[:, :, 0] * shape[1] + reflected[:, :, 1]) * shape[2] + reflected[:, :, 2]
    return Mesh3D(base.nodes, tets, base.boundary, base.regions, base.region_names)
