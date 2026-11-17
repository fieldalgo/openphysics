# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Small-strain isotropic P1 triangle elasticity in SI units.

youngs_modulus and poisson_ratio are one homogeneous material or piecewise constant
on named mesh regions (galerkin.materials, docs/packages/galerkin/multimaterial.md).
Import this submodule explicitly; see docs/packages/galerkin/elasticity2d.md for the contract.
No scalar or edge finite-element space is used here. Quantities are keyword-only
registry names in SI units (the units convention of the galerkin step).

youngs_modulus, poisson_ratio, the prescribed displacements, body_force_density and
traction may be JAX or PyTorch values (callbacks may return them); the result arrays
are then in that library and carry reverse-mode derivatives. One body serves both:
the formulas run in the inputs' library, the checks read their numbers, and the
linear system is solved once with ``core.solve`` in that library, whose adjoint
gives the exact derivatives.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from .core import live as live_inputs
from .core.backend import live_namespace, lift, to_numpy
from .core.boundary import traction_load
from .core.checks import one_of, real_array, require_finite
from .core.triangles import triangle_geometry, vector_strain
from ._mechanics_kernels import (PLANES, at_fixed as _at_fixed, body_load as _body_load,
                                 constitutive as _constitutive, displacement as _displacement,
                                 element_materials as _element_materials, stress_of as _stress_of,
                                 vector_stiffness as _vector_stiffness)
from ._public import ResultSurface, refuse_tagged_text, refuse_text

# Public names. The helpers lame, constitutive, element_materials, element_constitutive,
# stiffness_and_stress, stress_of, body_load, check_solution, displacement, at_fixed and
# vector_stiffness are internal: they live in the package-private galerkin._mechanics_kernels
# (L2 commit 8), and galerkin.kernels re-exports them.
__all__ = ["PLANES", "constitutive_matrix", "ElasticityResult", "solve_elasticity"]


def constitutive_matrix(*, youngs_modulus, poisson_ratio, plane):
    """Return Pa matrix for [exx, eyy, gamma_xy], gamma_xy=2*exy.

    youngs_modulus > 0 and -1 < poisson_ratio < 0.5 (stable 3D isotropic parent
    material), both scalars. ``plane`` is required and must be 'stress' or 'strain'.
    """
    refuse_text("youngs_modulus", youngs_modulus)
    refuse_text("poisson_ratio", poisson_ratio)
    e, nu = real_array(youngs_modulus, "youngs_modulus"), real_array(poisson_ratio, "poisson_ratio")
    if e.shape != () or nu.shape != () or e <= 0 or not -1 < nu < .5:
        raise ValueError("require scalar youngs_modulus > 0 and -1 < poisson_ratio < 0.5")
    one_of(plane, PLANES, "plane")
    d = _constitutive(np, np.float64(e), np.float64(nu), plane)
    require_finite(d, "constitutive parameters exceed floating-point range")
    return d


@dataclass(frozen=True)
class ElasticityResult(ResultSurface):
    """Nodal displacement (m), element engineering strain and stress (Pa); planar.

    applied_force_per_depth (body plus boundary traction) and reaction_force_per_depth
    have shape (N,2), in N/m: per metre of out-of-plane depth.
    reaction_force_per_depth is zero at free DOFs, and K*u-load at prescribed DOFs.
    residual_force_per_depth is K*u-load at ALL DOFs, with the same units.
    ``.units`` maps each quantity field to its canonical unit.
    """
    UNITS = MappingProxyType({"displacement": "m", "strain": "1", "stress": "Pa",
                              "applied_force_per_depth": "N/m", "reaction_force_per_depth": "N/m",
                              "residual_force_per_depth": "N/m"})
    BASIS = "planar"

    displacement: np.ndarray
    strain: np.ndarray
    stress: np.ndarray
    applied_force_per_depth: np.ndarray
    reaction_force_per_depth: np.ndarray
    residual_force_per_depth: np.ndarray
    plane: str


#: the quantity parameters of solve_elasticity, refused as text (SI numbers only)
_QUANTITIES = ("youngs_modulus", "poisson_ratio", "prescribed_displacement", "body_force_density", "traction")


def solve_elasticity(mesh, *, youngs_modulus, poisson_ratio, plane, prescribed_displacement,
                     body_force_density=None, traction=None, motion=None):
    """Solve -div(sigma)=body_force_density with optional prescribed boundary traction.

    youngs_modulus, poisson_ratio, the prescribed displacements, body_force_density and
    traction may be JAX or PyTorch values, or callbacks returning them; the result is then
    in that library with reverse-mode derivatives (docs/packages/galerkin/differentiation.md).
    Callbacks are called once. A str for a quantity raises TypeError (SI numbers only).

    body_force_density: None (no body force), a constant (2,) or a callable accepting
    (Q,2) coordinates in m and returning exactly (Q,2), in N/m^3.
    prescribed_displacement: mapping from (node, component=0|1) to scalar displacement
    in m. youngs_modulus (Pa) and poisson_ratio are scalars or {region name: value}
    mappings over mesh.region_names.
    traction: {boundary_edges tag: global (2,) vector in Pa, or
    callable(points, outward_normals)->(Q,2)}. None/{} keeps zero traction.
    All line loads, including those on prescribed displacement components,
    enter the applied force; their support reactions are computed from the original K*u-load.
    Duplicate selected edges and interior edges are rejected. See
    docs/packages/galerkin/elasticity_traction.md for overlap, quadrature and units.
    Nodes/triangles must form a conforming, nonoverlapping manifold mesh.
    Plane strain P1 displacement elements lock as poisson_ratio approaches 0.5.
    motion=galerkin.shape.MeshMotion(design_velocity=W, t=t) solves on the nodes X0 +
    t*W and every result carries the derivative with respect to the JAX
    or PyTorch scalar t (a shape derivative); see docs/packages/galerkin/shape_derivative.md.
    """
    for name, value in zip(_QUANTITIES, (youngs_modulus, poisson_ratio, prescribed_displacement,
                                         body_force_density, traction)):
        (refuse_tagged_text if name == "traction" else refuse_text)(name, value)
    young_modulus, dirichlet = youngs_modulus, prescribed_displacement
    body_force = (0., 0.) if body_force_density is None else body_force_density
    if motion is not None:
        from ._moving import solve_elasticity_moving
        return solve_elasticity_moving(mesh, motion, youngs_modulus=youngs_modulus, poisson_ratio=poisson_ratio,
                                       plane=plane, prescribed_displacement=prescribed_displacement,
                                       body_force_density=body_force, traction=traction)
    one_of(plane, PLANES, "plane")
    p, t, area, boundary, count, labels = triangle_geometry(mesh, counterclockwise=False)
    b, dofs = vector_strain(p, t)
    e, nu = _element_materials(mesh, young_modulus, poisson_ratio)
    body = _body_load(p, t, area, dofs, body_force)
    line = traction_load(mesh, p, t, traction, live=True)
    xp = live_namespace(e, nu, body, line, *live_inputs.leaves(dirichlet))
    d = _constitutive(xp, *(lift(xp, v, xp.float64) for v in (e, nu)), plane)
    require_finite(d, "constitutive parameters exceed floating-point range")
    n = 2*len(p)
    stiffness = _vector_stiffness(xp, b, dofs, d, area, n)
    body = lift(xp, body)
    if not np.all(np.isfinite(to_numpy(body))):
        raise ValueError("assembled body force exceeds floating-point range")
    load = body + lift(xp, line)
    if not np.all(np.isfinite(to_numpy(load))):
        raise ValueError("total body and traction load exceeds floating-point range")
    u, fixed = _displacement(xp, stiffness, load, dirichlet, p, boundary, count, labels, "elasticity")
    residual = stiffness.matvec(u) - load
    strain = xp.einsum("tij,tj->ti", lift(xp, b), u[dofs])
    stress = _stress_of(xp, d, strain)
    if not np.all(np.isfinite(to_numpy(strain))) or not np.all(np.isfinite(to_numpy(stress))):
        raise ValueError("computed strain/stress exceeds floating-point range")
    return ElasticityResult(xp.reshape(u, (-1, 2)), strain, stress,
                            *(xp.reshape(a, (-1, 2)) for a in (load, _at_fixed(xp, residual, fixed), residual)),
                            plane)
