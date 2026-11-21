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
counterparts, ``tet_gradients`` and ``solve_dirichlet``), the physics modules'
helpers and the electromagnetic kernels (the edge-element assembly and evaluation,
``solve_modes``, ``assemble_mode_system``, the mode coordinates, the 16 mode-overlap
functions and ``radial_pml_coeffs``) are in ``galerkin.kernels``: internal,
consistent units, not part of this API.
"""

from .mesh import Mesh, rectangle_mesh, annulus_mesh, disk_mesh
from .mesh3d import Mesh3D, box_mesh
from .edge import EdgeSpace
from .edge3d import EdgeSpace3D
from .gmsh import read_msh, write_msh
from .interop import from_mesher
from .waveguide import (ModalPML, Bend, WaveguideModes, solve_waveguide_modes, mode_power, cross_power,
                        field_overlap, mode_coupling_efficiency, mode_confinement_factor, mode_effective_area)
from .cavity import CavityResult, solve_cavity, solve_cavity_box
from .material_cavity import (CavityMaterialRegion, MaterialCavityResult,
                              solve_material_cavity, solve_material_cavity_box)
from .postprocess import element_gradient, l2_error
from .electrostatics import (ElementPermittivity, ElectrostaticsResult,
                             solve_electrostatics, capacitance_matrix)

# The public names: those imported above, then the submodules those imports bind. The kernels
# re-exported by galerkin.kernels are not among them (``from galerkin import *`` gave them
# before the galerkin step of the units convention: the non-em kernels left in L2 commit 4, the
# em kernels in L3 commit 11), and neither is the submodule mode_coordinates, which
# galerkin.waveguide binds: its name is a kernel's (D7).
__all__ = ["Mesh", "rectangle_mesh", "annulus_mesh", "disk_mesh", "Mesh3D", "box_mesh",
           "EdgeSpace", "EdgeSpace3D", "read_msh", "write_msh", "from_mesher", "ModalPML", "Bend",
           "WaveguideModes", "solve_waveguide_modes", "mode_power", "cross_power", "field_overlap",
           "mode_coupling_efficiency", "mode_confinement_factor", "mode_effective_area", "CavityResult",
           "solve_cavity", "solve_cavity_box", "CavityMaterialRegion", "MaterialCavityResult",
           "solve_material_cavity", "solve_material_cavity_box", "element_gradient", "l2_error",
           "ElementPermittivity", "ElectrostaticsResult", "solve_electrostatics",
           "capacitance_matrix",
           "assembly", "cavity", "core", "coupling", "edge", "edge3d", "electrostatics", "gmsh", "interop",
           "material_cavity", "materials", "mesh", "mesh3d", "mode_overlap", "postprocess", "waveguide"]

__version__ = "0.0.2"
