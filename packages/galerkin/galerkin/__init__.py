"""galerkin — FEM engine of the FieldAlgo project.

Milestones:
    M1      2D electrostatics (Poisson):  div(eps grad V) = -rho
    M2      2D frequency-domain waves (Helmholtz), absorbing boundaries
    M2.5    Cylindrical PML via tensor-coefficient assembly
    M3prep  Lowest-order Nedelec edge elements, waveguide eigenmodes
    M3a     Dielectric waveguide modes (mixed edge/nodal vector formulation)
    M3b     3D Maxwell: tetrahedral Nedelec elements, cavity eigenmodes
"""

from .mesh import Mesh, rectangle_mesh, annulus_mesh, disk_mesh
from .mesh3d import Mesh3D, box_mesh
from .assembly import (assemble_stiffness, assemble_mass,
                       assemble_boundary_mass, assemble_load)
from .solver import solve_dirichlet
from .pml import radial_pml_coeffs
from .edge import (EdgeSpace, assemble_curlcurl, assemble_edge_mass,
                   assemble_edge_grad, eval_edge_field)
from .assembly3d import (tet_gradients, assemble_stiffness_3d,
                         assemble_mass_3d)
from .edge3d import (EdgeSpace3D, assemble_curlcurl_3d,
                     assemble_edge_mass_3d, assemble_edge_grad_3d,
                     eval_edge_field_3d)
from .gmsh import read_msh, write_msh
from .interop import from_mesher
from .waveguide import assemble_mode_system, solve_modes
from .postprocess import element_gradient, l2_error

__version__ = "0.1.0"
