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
- heat: the boundary system of the 2D heat solve, ``scalar_boundary_system``; the 3D
  source load and face-tag Dirichlet map, ``source_load_3d`` and ``dirichlet_from_faces``
  (all three from the package-private ``galerkin._heat_kernels`` since L2 commit 6, so
  that the clean public heat modules hold no removed name); and the region table
  look-up ``region_property`` (``galerkin.materials``);
- mechanics: ``lame``, ``constitutive``, ``element_materials``,
  ``element_constitutive``, ``stiffness_and_stress``, ``stress_of``, ``body_load``,
  ``check_solution``, ``displacement``, ``at_fixed`` and ``vector_stiffness`` (the
  helpers of ``galerkin.elasticity``); ``thermal_coefficient``, ``physical_energy`` and
  ``verify_snapshot`` (those of ``galerkin.thermoelasticity``); all from the
  package-private ``galerkin._mechanics_kernels`` since L2 commit 8, so that the clean
  public mechanics modules hold no removed name;
- the moving-mesh solves ``solve_steady_heat_moving``, ``solve_transient_heat_moving``,
  ``solve_steady_electric_moving``, ``solve_elasticity_moving``,
  ``solve_thermoelasticity_moving`` and ``solve_steady_thermoelasticity_moving`` (the
  package-private ``galerkin._moving`` since L2 commit 8; they were names of
  ``galerkin.shape``). The public route to them is ``motion=`` on the public solver,
  which negates inward data first: the heat mirrors take today's outward heat flux, as
  ``outward_heat_flux``, and the electric mirror the outward current density, as
  ``outward_current_density`` (A/m^2, positive leaves the body; the registry has no
  outward density name, and this internal keyword is not scanned), with registry names
  for the other quantities (the mechanics mirrors take ``youngs_modulus``,
  ``prescribed_displacement``, ``body_force_density``, ``stress_free_temperature``,
  ``linear_expansion_coefficient``, ...; mechanics has no inward or outward sign).

- electromagnetics (L3 commit 11; they were names of galerkin's top level, or of the
  internal ``galerkin.mode_coordinates``): the 2D edge kernels ``assemble_curlcurl``,
  ``assemble_edge_mass``, ``assemble_edge_grad`` and ``eval_edge_field``
  (``galerkin.edge``) and their 3D counterparts ``assemble_curlcurl_3d``,
  ``assemble_edge_mass_3d``, ``assemble_edge_grad_3d`` and ``eval_edge_field_3d``
  (``galerkin.edge3d``); the mode solve ``solve_modes`` and its pencil
  ``assemble_mode_system`` (the package-private ``galerkin._waveguide_kernels``); the
  modal PML and bend coordinates ``mode_coordinates`` and the scalar mode solve in them,
  ``scalar_coordinate_system`` and ``solve_scalar_coordinates``
  (``galerkin.mode_coordinates``); the 16 power, overlap, normalisation, coupling,
  confinement and effective-area functions of ``galerkin.mode_overlap``; and the radial
  PML ``radial_pml_coeffs`` (``galerkin.pml``). The mesh and the edge spaces they work on
  (``Mesh``, ``Mesh3D``, ``EdgeSpace``, ``EdgeSpace3D``) stay public.

  Complex values: these kernels compute in exp(+i omega t) (a passive loss is
  Im eps_r < 0 and a forward lossy mode has Im n_eff < 0; the field ``ez`` has
  E_z = 1j * ez), except ``radial_pml_coeffs``, which already follows exp(-i omega t)
  (its stretch is 1 + i sigma/k and the outgoing wave e^{ikr}). galerkin's public em
  functions convert in one place, ``galerkin._conventions``: a public complex output is
  ``to_public(kernel(to_kernel(x)))``, and the public path never conjugates
  ``radial_pml_coeffs``. Lengths are the mesh's unit and k0 its inverse: simcase hands
  ``solve_modes`` micrometre meshes scaled by the wavelength, with k0 = 2 pi.
"""

from .assembly import assemble_boundary_mass, assemble_load, assemble_mass, assemble_stiffness
from .assembly3d import assemble_mass_3d, assemble_stiffness_3d, tet_gradients
from .edge import assemble_curlcurl, assemble_edge_grad, assemble_edge_mass, eval_edge_field
from .edge3d import assemble_curlcurl_3d, assemble_edge_grad_3d, assemble_edge_mass_3d, eval_edge_field_3d
from .mode_coordinates import mode_coordinates, scalar_coordinate_system, solve_scalar_coordinates
from .mode_overlap import (centroid_field, confinement_factor, coupling_efficiency, effective_area,
                           interpolate_vector_field, normalize_scalar, normalize_vector, overlap_matrix,
                           scalar_confinement_factor, scalar_coupling_efficiency, scalar_effective_area,
                           scalar_overlap, scalar_power, vector_cross_power, vector_field_overlap, vector_power)
from .pml import radial_pml_coeffs
from .materials import region_property
from .solver import solve_dirichlet
from ._heat_kernels import dirichlet_from_faces, scalar_boundary_system, source_load_3d
from ._mechanics_kernels import (at_fixed, body_load, check_solution, constitutive, displacement,
                                 element_constitutive, element_materials, lame, physical_energy,
                                 stiffness_and_stress, stress_of, thermal_coefficient, vector_stiffness,
                                 verify_snapshot)
from ._moving import (solve_elasticity_moving, solve_steady_electric_moving, solve_steady_heat_moving,
                      solve_steady_thermoelasticity_moving, solve_thermoelasticity_moving,
                      solve_transient_heat_moving)
from ._waveguide_kernels import assemble_mode_system, solve_modes

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
    # electromagnetics: edge elements, mode solve and coordinates, mode overlaps, radial PML
    "assemble_curlcurl", "assemble_edge_mass", "assemble_edge_grad", "eval_edge_field",
    "assemble_curlcurl_3d", "assemble_edge_mass_3d", "assemble_edge_grad_3d", "eval_edge_field_3d",
    "solve_modes", "assemble_mode_system", "mode_coordinates", "scalar_coordinate_system",
    "solve_scalar_coordinates",
    "vector_power", "vector_cross_power", "vector_field_overlap", "normalize_vector", "coupling_efficiency",
    "confinement_factor", "overlap_matrix", "centroid_field", "interpolate_vector_field", "effective_area",
    "scalar_power", "scalar_overlap", "normalize_scalar", "scalar_coupling_efficiency",
    "scalar_confinement_factor", "scalar_effective_area",
    "radial_pml_coeffs",
]
