# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""meshine — a small quality triangle mesher for planar multi-material domains.

    from meshine import Domain, Circle, generate, box_sides, rectangle
    d = Domain(size=0.2)
    d.add_region("core", rectangle(-1, 0, 1, 0.5), size=0.05)
    d.add_region("clad", [(-3, -2), (3, -2), (3, 0.5), (1, 0.5), (1, 0), (-1, 0), (-1, 0.5), (-3, 0.5)])
    d.add_region("clad", rectangle(-3, 0.5, 3, 2))
    mesh = generate(d, box_sides(-3, 3, -2, 2), min_angle=28)
    mesh.nodes, mesh.triangles, mesh.regions, mesh.boundary_edges["left"]

Constrained Delaunay refinement (Ruppert) built on scipy; depends on numpy and scipy only.
``TetMesh``, ``check`` and ``write_msh`` define the tetrahedral mesh contract for 3D meshers.
"""

from . import shapes
from .geometry import Circle, Domain, box_sides, rectangle
from .mesh import TriMesh
from .mesh3d import MeshCheckError, TetMesh, check, write_msh
from .refine import MeshSizeLimitError, generate

__version__ = "0.1.0"
__all__ = ["Domain", "Circle", "TriMesh", "TetMesh", "MeshCheckError", "check", "write_msh", "generate",
           "MeshSizeLimitError", "box_sides", "rectangle", "shapes", "__version__"]
