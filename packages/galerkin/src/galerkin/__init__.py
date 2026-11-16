# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""galerkin — FEM engine of the FieldAlgo project.

Milestones:
    M1      2D electrostatics (Poisson):  div(eps grad V) = -rho
    M2      2D frequency-domain waves (Helmholtz), absorbing boundaries
    M2.5    Cylindrical PML via tensor-coefficient assembly
    M3prep  Lowest-order Nedelec edge elements, waveguide eigenmodes
    M3a     Dielectric waveguide modes (mixed edge/nodal vector formulation)
    M3b     3D Maxwell: tetrahedral Nedelec elements, cavity eigenmodes

The non-electromagnetic assembly and solve functions (``assemble_stiffness``,
``assemble_mass``, ``assemble_boundary_mass``, ``assemble_load``, their 3D
counterparts, ``tet_gradients`` and ``solve_dirichlet``) and the physics modules'
helpers are in ``galerkin.kernels``: internal, consistent units, not part of this API.
"""

from .mesh import Mesh, rectangle_mesh, annulus_mesh, disk_mesh
from .mesh3d import Mesh3D, box_mesh
from .pml import radial_pml_coeffs
from .edge import (EdgeSpace, assemble_curlcurl, assemble_edge_mass,
                   assemble_edge_grad, eval_edge_field)
from .edge3d import (EdgeSpace3D, assemble_curlcurl_3d,
                     assemble_edge_mass_3d, assemble_edge_grad_3d,
                     eval_edge_field_3d)
from .gmsh import read_msh, write_msh
from .interop import from_mesher
from .waveguide import assemble_mode_system, solve_modes
from .cavity import CavityResult, solve_cavity, solve_cavity_box
from .material_cavity import (CavityMaterialRegion, MaterialCavityResult,
                              solve_material_cavity, solve_material_cavity_box)
from .postprocess import element_gradient, l2_error
from .electrostatics import (ElementPermittivity, ElectrostaticsResult,
                             solve_electrostatics, capacitance_matrix)
from .mode_overlap import (vector_power, vector_cross_power, vector_field_overlap,
                           normalize_vector, coupling_efficiency, confinement_factor,
                           overlap_matrix, centroid_field, interpolate_vector_field,
                           effective_area, scalar_power, scalar_overlap, normalize_scalar,
                           scalar_coupling_efficiency, scalar_confinement_factor,
                           scalar_effective_area)

# The public names: those imported above, then the submodules those imports bind. The kernels
# re-exported by galerkin.kernels are not among them (``from galerkin import *`` gave them
# before the galerkin step of the units convention).
__all__ = ["Mesh", "rectangle_mesh", "annulus_mesh", "disk_mesh", "Mesh3D", "box_mesh",
           "radial_pml_coeffs", "EdgeSpace", "assemble_curlcurl", "assemble_edge_mass",
           "assemble_edge_grad", "eval_edge_field", "EdgeSpace3D", "assemble_curlcurl_3d",
           "assemble_edge_mass_3d", "assemble_edge_grad_3d", "eval_edge_field_3d", "read_msh",
           "write_msh", "from_mesher", "assemble_mode_system", "solve_modes", "CavityResult",
           "solve_cavity", "solve_cavity_box", "CavityMaterialRegion", "MaterialCavityResult",
           "solve_material_cavity", "solve_material_cavity_box", "element_gradient", "l2_error",
           "ElementPermittivity", "ElectrostaticsResult", "solve_electrostatics",
           "capacitance_matrix", "vector_power", "vector_cross_power", "vector_field_overlap",
           "normalize_vector", "coupling_efficiency", "confinement_factor", "overlap_matrix",
           "centroid_field", "interpolate_vector_field", "effective_area", "scalar_power",
           "scalar_overlap", "normalize_scalar", "scalar_coupling_efficiency",
           "scalar_confinement_factor", "scalar_effective_area",
           "assembly", "cavity", "core", "coupling", "edge", "edge3d", "electrostatics", "gmsh",
           "interop", "material_cavity", "materials", "mesh", "mesh3d", "mode_overlap", "pml",
           "postprocess", "waveguide"]

__version__ = "0.0.2"
