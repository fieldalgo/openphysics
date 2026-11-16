# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""galerkin's kernels: the assembly and solve functions and the physics modules' helpers.

Internal module, consistent units: not part of galerkin's public API (the ``__all__``
of its public modules). Nothing here is in a public ``__all__``, and no public name
equals a name of this namespace.

These functions compute in whatever consistent units their caller hands them (lengths
in the mesh's unit, coefficients in the units of the caller's physics) and keep their
names, positional coefficients and defaults: the units convention applies to the
public solvers, not here. They are re-exported here unchanged from the modules that
define them, so ``galerkin.kernels.assemble_stiffness is
galerkin.assembly.assemble_stiffness``. ``simcase`` and ``sipi`` call them directly
(an inter-package contract: both pin galerkin to one version).

This is not ``galerkin.core.kernels``: that module holds the closed-form element
matrices these assembly functions place, for galerkin's own modules.

- P1 assembly on triangles: ``assemble_stiffness(mesh, eps=1.0)``,
  ``assemble_mass(mesh, coeff=1.0)``, ``assemble_boundary_mass(mesh, edges, coeff=1.0)``
  and ``assemble_load(mesh, rho=0.0)`` (``galerkin.assembly``); on tetrahedra
  ``assemble_stiffness_3d``, ``assemble_mass_3d`` and ``tet_gradients``
  (``galerkin.assembly3d``); the Dirichlet solve ``solve_dirichlet(K, f, dirichlet)``
  (``galerkin.solver``);
- heat: the boundary system of the 2D heat solve, ``scalar_boundary_system``
  (``galerkin.thermal``); the 3D source load and face-tag Dirichlet map,
  ``source_load_3d`` and ``dirichlet_from_faces`` (``galerkin.thermal3d``); and the
  region table look-up ``region_property`` (``galerkin.materials``);
- mechanics: ``lame``, ``constitutive``, ``element_materials``,
  ``element_constitutive``, ``stiffness_and_stress``, ``stress_of``, ``body_load``,
  ``check_solution``, ``displacement``, ``at_fixed`` and ``vector_stiffness``
  (``galerkin.elasticity``); ``thermal_coefficient``, ``physical_energy`` and
  ``verify_snapshot`` (``galerkin.thermoelasticity``);
- the moving-mesh solves ``solve_steady_heat_moving``, ``solve_transient_heat_moving``,
  ``solve_steady_electric_moving``, ``solve_elasticity_moving``,
  ``solve_thermoelasticity_moving`` and ``solve_steady_thermoelasticity_moving``
  (``galerkin.shape``). The public route to them is ``motion=`` on the public solver.

The electromagnetic kernels (edge spaces, curl-curl, PML, mode systems and overlaps)
are not in this namespace yet; they are still names of galerkin's top level.
"""

from .assembly import assemble_boundary_mass, assemble_load, assemble_mass, assemble_stiffness
from .assembly3d import assemble_mass_3d, assemble_stiffness_3d, tet_gradients
from .elasticity import (at_fixed, body_load, check_solution, constitutive, displacement, element_constitutive,
                         element_materials, lame, stiffness_and_stress, stress_of, vector_stiffness)
from .materials import region_property
from .shape import (solve_elasticity_moving, solve_steady_electric_moving, solve_steady_heat_moving,
                    solve_steady_thermoelasticity_moving, solve_thermoelasticity_moving, solve_transient_heat_moving)
from .solver import solve_dirichlet
from .thermal import scalar_boundary_system
from .thermal3d import dirichlet_from_faces, source_load_3d
from .thermoelasticity import physical_energy, thermal_coefficient, verify_snapshot

__all__ = [
    # P1 assembly and the Dirichlet solve
    "assemble_stiffness", "assemble_mass", "assemble_boundary_mass", "assemble_load",
    "tet_gradients", "assemble_stiffness_3d", "assemble_mass_3d", "solve_dirichlet",
    # heat
    "scalar_boundary_system", "source_load_3d", "dirichlet_from_faces", "region_property",
    # mechanics
    "lame", "constitutive", "element_materials", "element_constitutive", "stiffness_and_stress", "stress_of",
    "body_load", "check_solution", "displacement", "at_fixed", "vector_stiffness",
    "thermal_coefficient", "physical_energy", "verify_snapshot",
    # moving-mesh solves
    "solve_steady_heat_moving", "solve_transient_heat_moving", "solve_steady_electric_moving",
    "solve_elasticity_moving", "solve_thermoelasticity_moving", "solve_steady_thermoelasticity_moving",
]
