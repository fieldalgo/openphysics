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

Covered: steady heat (``thermal.steady2d``) on the material regions of a version 1 ``2d``
component (whose study is ``single``: steady heat takes no other). Refused by name, as
``DocumentError``: a flat geometry block, an ``axisymmetric`` component, another physics, and
every parameter the design velocity refuses (unknown, ratio or derived parameters, a topology change at p).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from .schema import Document, DocumentError

__all__ = ["ShapeProblem", "shape_problem"]

_PHYSICS = "thermal.steady2d"


@dataclass(frozen=True)
class ShapeProblem:
    """One document, one length parameter: the mesh, its motion and the solve that differentiates.

    ``mesh`` is the galerkin mesh ``run`` solves on (metres, the same nodes in the same order);
    ``design_velocity`` is W, (N, 2), dimensionless: the nodes move as X0 + t W, t in metres of
    the parameter; ``on_curve`` marks the nodes whose W the geometry gives (the rest are
    extended); ``admissible_interval`` is (lo, hi) in metres: no element inverts for lo < t < hi;
    ``arguments`` are the keyword arguments of the galerkin solve, as ``run`` passes them.
    """

    document: Document
    parameter: str
    mesh: object
    design_velocity: np.ndarray
    on_curve: np.ndarray
    admissible_interval: tuple
    arguments: dict

    def solve(self, t):
        """The document's steady heat solve on the mesh moved to X0 + t W.

        ``t`` is a JAX or PyTorch float64 scalar (galerkin refuses anything else by name);
        the result's fields carry d/dt in t's library. Returns galerkin's result as ``run``'s
        solve does (``PlanarSteadyHeatResult``)."""
        from galerkin.shape import MeshMotion
        from galerkin.thermal import solve_steady_heat
        return solve_steady_heat(self.mesh, **self.arguments,
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

    from . import views
    from .geometry_document import GeometryError
    from .geometry_velocity import design_velocity, signature
    from .thermal_regions import (NAMES_03, component_03, handoff_03, is_axisymmetric, is_region_thermal,
                                  mesh_diagnostics_03, region_inputs, region_mesh_um)
    given = document if isinstance(document, Document) else Document.from_dict(document)
    doc = given.copy()
    doc.validate()
    name, physics = doc.sole_physics()
    if physics.get("type") != _PHYSICS:
        raise DocumentError(f"shape_problem: physics.{name} is {physics.get('type')!r}; the shape derivative of a "
                            f"document covers {_PHYSICS} on material regions so far")
    if not (is_region_thermal(doc.data) and doc.is_version_1):
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
    kwargs = region_inputs(doc, mesh, region_materials, views.region_heat_03(doc), NAMES_03)
    return ShapeProblem(doc, parameter, mesh, W, np.asarray(nv.on_curve), (float(lo), float(hi)),
                        views.galerkin_heat_arguments(kwargs))
