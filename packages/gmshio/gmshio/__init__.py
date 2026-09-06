# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""gmshio — drive Gmsh as an external process and read its meshes into numpy.

    from gmshio import geo, generate, to_fem2d
    mesh = generate(geo.rib_waveguide(slab_thickness=0.3), dim=2)
    fem = to_fem2d(mesh)          # nodes, CCW triangles, region ids, boundary edges
"""

from . import fem, geo
from .fem import FemMesh2D, FemMesh3D, to_fem2d, to_fem3d
from .mesh import ELEMENT_TYPES, CellBlock, Mesh
from .msh import MshFormatError, read_msh
from .run import GmshNotFound, find_gmsh, generate, gmsh_version

__version__ = "0.1.0"
__all__ = ["geo", "fem", "generate", "read_msh", "to_fem2d", "to_fem3d", "Mesh", "CellBlock",
           "FemMesh2D", "FemMesh3D", "ELEMENT_TYPES", "MshFormatError", "GmshNotFound",
           "find_gmsh", "gmsh_version", "__version__"]
