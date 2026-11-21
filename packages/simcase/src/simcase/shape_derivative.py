# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The shape derivative of a document with respect to one geometry parameter, in one call.

    from simcase.shape_derivative import shape_problem

    problem = shape_problem(document, "a")          # a format 0.3 document and a length parameter
    value, slope = problem.derivative(lambda r: r.reaction_heat_rate_per_depth[problem.mesh.boundary["inner"]].sum())
    # slope = d value / d a, per metre of a

``shape_problem`` meshes the document as ``run`` does and joins three stages that otherwise
need the node identity between them:

1. the design velocity of the mesh nodes on the geometry's curves
   (``simcase.geometry_velocity``, stage 4: V = dx/dp, dimensionless);
2. the motion of the interior nodes (``galerkin.shape.extend_velocity``, harmonic);
3. the solve on the moving mesh (``motion=`` of the galerkin solver), which carries
   d/dt through JAX or PyTorch.

The design variable t is the change of the parameter in metres: the galerkin mesh is in
metres and V is dimensionless, so d/dt is the derivative per metre of the parameter,
whatever unit the document writes it in. ``admissible_interval`` bounds t: outside it an
element inverts and galerkin refuses the step. galerkin never remeshes; to take a larger
step, change the parameter in the document and call ``shape_problem`` again.

Covered, on the material regions of a version 1 ``2d`` component (``run``'s region path):

- ``thermal.steady2d``: ``galerkin.thermal.solve_steady_heat``;
- ``thermal.transient2d``: ``galerkin.transient_heat.solve_transient_heat``;
- ``electric.steady2d``: ``galerkin.electric.solve_steady_electric``;
- ``mechanics.elasticity2d``: ``galerkin.elasticity.solve_elasticity``;
- ``mechanics.thermoelastic2d``: ``galerkin.thermal_mechanical.solve_steady_thermoelasticity``,
  which solves the heat stage again on the moving mesh (the temperature moves with the
  geometry). It takes Dirichlet temperatures and insulation only, so a document with an
  inward heat flux, a convection or a traction is refused.

Refused by name, as ``DocumentError``: a flat geometry block, an ``axisymmetric`` component,
another physics (waveguide modes have their own runner), and every parameter the design
velocity refuses (unknown, ratio or derived parameters, a topology change at p).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from .schema import Document, DocumentError

__all__ = ["ShapeProblem", "shape_problem"]

STEADY_HEAT, TRANSIENT_HEAT, ELECTRIC = "thermal.steady2d", "thermal.transient2d", "electric.steady2d"
ELASTICITY, THERMOELASTIC = "mechanics.elasticity2d", "mechanics.thermoelastic2d"
_COVERED = (STEADY_HEAT, TRANSIENT_HEAT, ELECTRIC, ELASTICITY, THERMOELASTIC)


@dataclass(frozen=True)
class ShapeProblem:
    """One document, one length parameter: the mesh, its motion and the solve that differentiates.

    ``mesh`` is the galerkin mesh ``run`` solves on (metres, the same nodes in the same order);
    ``design_velocity`` is W, (N, 2), dimensionless: the nodes move as X0 + t W, t in metres of
    the parameter; ``on_curve`` marks the nodes whose W the geometry gives (the rest are
    extended); ``admissible_interval`` is (lo, hi) in metres: no element inverts for lo < t < hi;
    ``arguments`` are the keyword arguments of the galerkin solve, as ``run`` passes them;
    ``physics`` is the document's physics type, which picks the solver.
    """

    document: Document
    parameter: str
    physics: str
    mesh: object
    design_velocity: np.ndarray
    on_curve: np.ndarray
    admissible_interval: tuple
    arguments: dict

    def solve(self, t):
        """The document's solve on the mesh moved to X0 + t W.

        ``t`` is a JAX or PyTorch float64 scalar (galerkin refuses anything else by name); the
        result's fields carry d/dt in t's library. Returns the galerkin solver's result: steady
        or transient heat, steady electric conduction, elasticity, or the steady
        heat-to-mechanics workflow (see the module docstring)."""
        from galerkin.shape import MeshMotion
        return _solver(self.physics)(self.mesh, **self.arguments,
                                     motion=MeshMotion(design_velocity=self.design_velocity, t=t))

    def derivative(self, objective, *, backend="jax", t=0.0):
        """(objective, d objective / d t) at ``t``, on the mesh moved to X0 + t W.

        At ``t = 0`` (the default) this is the derivative with respect to the parameter, per
        metre. At another t it is the derivative along the fixed linear motion, which is not the
        document's derivative at p + t: derived vertices, arc nodes and interior nodes do not
        follow the exact geometry there. ``objective`` takes the result of ``solve`` and returns
        a scalar in t's library. ``backend`` is ``"jax"`` (``jax_enable_x64``
        must be on: galerkin computes in float64) or ``"torch"``."""
        if backend == "jax":
            import jax
            import jax.numpy as jnp
            value, slope = jax.value_and_grad(lambda s: objective(self.solve(s)))(jnp.asarray(t, dtype=jnp.float64))
            return float(value), float(slope)
        if backend == "torch":
            import torch
            leaf = torch.tensor(float(t), dtype=torch.float64, requires_grad=True)
            value = objective(self.solve(leaf))
            (slope,) = torch.autograd.grad(value, leaf)
            return float(value.detach()), float(slope)
        raise ValueError(f"shape_problem: backend must be 'jax' or 'torch', got {backend!r}")


def shape_problem(document, parameter: str) -> ShapeProblem:
    """The shape problem of ``document`` (a ``Document`` or its dict) for the length parameter
    ``parameter`` of its version 1 geometry; see the module docstring for what is covered."""
    from galerkin.shape import admissible_interval, extend_velocity

    from .geometry_document import GeometryError
    from .geometry_velocity import design_velocity, signature
    from .thermal_regions import component_03, handoff_03, is_axisymmetric, is_region_thermal, mesh_diagnostics_03, \
        region_mesh_um
    from .electric_regions import is_region_electric
    from .mechanics_regions import is_region_mechanics
    from .transient_regions import is_transient_region_thermal
    given = document if isinstance(document, Document) else Document.from_dict(document)
    doc = given.copy()
    doc.validate()
    name, physics = doc.sole_physics()
    kind = physics.get("type")
    if kind not in _COVERED:
        raise DocumentError(f"shape_problem: physics.{name} is {kind!r}; the shape derivative of a document covers "
                            f"{', '.join(_COVERED)} on material regions so far")
    regions = {STEADY_HEAT: is_region_thermal, TRANSIENT_HEAT: is_transient_region_thermal,
               ELECTRIC: is_region_electric, ELASTICITY: is_region_mechanics, THERMOELASTIC: is_region_mechanics}
    if not (regions[kind](doc.data) and doc.is_version_1):
        raise DocumentError("shape_problem: the geometry is not a version 1 block of material regions; a design "
                            "parameter is a geometry.parameters entry of a version 1 component")
    h = handoff_03(doc)
    if is_axisymmetric(h):
        raise DocumentError("shape_problem: the component is axisymmetric; galerkin refuses a motion in "
                            "axisymmetric coordinates")
    try:
        dv = design_velocity(doc.data, parameter)
    except GeometryError as exc:
        raise DocumentError(f"shape_problem: {exc}") from None
    mesh, region_materials, tri, canonical = region_mesh_um(h)
    # the mesher's findings reach the caller's document as coded diagnostics, as in run()
    for target in (given, doc):
        mesh_diagnostics_03(target, component_03(doc)[0], h.notes)
    meshed = canonical.geometry_complex

    def curves(rc):
        return [(k.index, k.kind, k.a, k.b, k.params) for k in rc.curves]
    if (signature(meshed) != signature(dv.complex) or meshed.vertices != dv.complex.vertices
            or curves(meshed) != curves(dv.complex)):
        raise DocumentError("shape_problem: the meshed geometry and the geometry of the design velocity differ "
                            "(a defect of simcase, please report it)")
    # node_velocity reads the curves of the complex that was handed to the mesher
    nv = replace(dv, complex=meshed).node_velocity(tri)
    W = extend_velocity(mesh, nv.values, nv.on_curve)
    lo, hi = admissible_interval(mesh, design_velocity=W)
    arguments = _arguments(kind, name, doc, mesh, region_materials)
    return ShapeProblem(doc, parameter, kind, mesh, W, np.asarray(nv.on_curve), (float(lo), float(hi)), arguments)


def _solver(kind):
    if kind == STEADY_HEAT:
        from galerkin.thermal import solve_steady_heat
        return solve_steady_heat
    if kind == TRANSIENT_HEAT:
        from galerkin.transient_heat import solve_transient_heat
        return solve_transient_heat
    if kind == ELECTRIC:
        from galerkin.electric import solve_steady_electric
        return solve_steady_electric
    if kind == ELASTICITY:
        from galerkin.elasticity import solve_elasticity
        return solve_elasticity
    from galerkin.thermal_mechanical import solve_steady_thermoelasticity
    return solve_steady_thermoelasticity


def _arguments(kind, name, doc, mesh, region_materials):
    """The galerkin keyword arguments of the document's solve, built as ``run`` builds them."""
    from . import views
    from .thermal_regions import NAMES_03, component_03, region_inputs
    if kind == STEADY_HEAT:
        return views.galerkin_heat_arguments(region_inputs(doc, mesh, region_materials, views.region_heat_03(doc),
                                                           NAMES_03))
    if kind == TRANSIENT_HEAT:
        from .transient_regions import transient_region_inputs
        inputs = transient_region_inputs(doc, mesh, region_materials, views.transient_region_heat_03(doc),
                                         views.region_origin_03(doc, component_03(doc)[0]), NAMES_03)
        return views.galerkin_heat_arguments(inputs)
    if kind == ELECTRIC:
        from .electric_regions import region_inputs as electric_inputs
        return views.galerkin_electric_arguments(electric_inputs(doc, mesh, region_materials)[0])
    from .mechanics_regions import region_mechanics_inputs
    inputs = region_mechanics_inputs(doc, mesh, region_materials)
    if kind == ELASTICITY:
        return inputs
    heat = views.galerkin_heat_arguments(region_inputs(doc, mesh, region_materials, views.region_heat_03(doc),
                                                       NAMES_03))
    refused = [key for key, given in (("inward_heat_flux", heat.get("inward_heat_flux")),
                                      ("convection", heat.get("convection")),
                                      ("traction", inputs.get("traction"))) if given]
    if refused:
        raise DocumentError(f"shape_problem: physics.{name} has {' and '.join(refused)}; the shape derivative of "
                            f"{THERMOELASTIC} solves heat and mechanics again on the moving mesh "
                            "(galerkin.thermal_mechanical.solve_steady_thermoelasticity), which takes Dirichlet "
                            "temperatures and insulation, prescribed displacements and a body force only")
    mechanics = {k: v for k, v in inputs.items() if k != "traction"}
    return dict(thermal_conductivity=heat["thermal_conductivity"], prescribed_temperature=heat["prescribed_temperature"],
                heat_source_density=heat["heat_source_density"], **mechanics)
