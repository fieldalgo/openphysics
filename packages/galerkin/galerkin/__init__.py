"""galerkin — FEM engine of the FieldAlgo project.

Milestones:
    M1      2D electrostatics (Poisson):  div(eps grad V) = -rho
    M2      2D frequency-domain waves (Helmholtz), absorbing boundaries
    M2.5    Cylindrical PML via tensor-coefficient assembly
    M3prep  Lowest-order Nedelec edge elements, waveguide eigenmodes
"""

from .mesh import Mesh, rectangle_mesh, annulus_mesh
from .assembly import (assemble_stiffness, assemble_mass,
                       assemble_boundary_mass, assemble_load)
from .solver import solve_dirichlet
from .pml import radial_pml_coeffs
from .edge import (EdgeSpace, assemble_curlcurl, assemble_edge_mass,
                   eval_edge_field)
from .postprocess import element_gradient, l2_error

__version__ = "0.1.0"
