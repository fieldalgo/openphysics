# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The ``I-MESH-ESTIMATE`` of a ``3d`` component without meshing it (``estimate_mesh3d``).

``build_mesh3d`` checks the estimate T = 6.3 sum(V_r / h_r^3) against ``mesh.element_count_limit``
and then meshes in the same call. A caller that must know the estimate before it decides to mesh
(Studio refuses before it starts a meshing process) calls this instead. It is one call to
``geometry_engine3d._prepare``, which is everything ``build_mesh3d`` does before meshloom, so every
refusal that blocks meshing blocks the estimate too, in the same words, with no second list to keep
in step. Only the hand-off's ``estimate`` and ``max_points`` and the diagnostic are read: the
complex may be absent on other hand-off routes. A lone slab ``layers`` component, which ``build_mesh3d``
leaves to the ``meshine.extrude`` route, is counted on that route instead (``_extrude_estimate``).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import geometry_engine3d as _engine

__all__ = ["Mesh3DEstimate", "estimate_mesh3d", "SECONDS_PER_TETRAHEDRON"]

#: the expected meshing time per tetrahedron (s): the slow end of the engine's 0.4-0.6 ms
SECONDS_PER_TETRAHEDRON = 6e-4


@dataclass(frozen=True)
class Mesh3DEstimate:
    """``estimate_mesh3d``'s result: the component, the estimated tetrahedra T (rounded to an
    integer), the limit in effect (``mesh.element_count_limit``), the expected seconds at 0.6 ms per
    tetrahedron, and ``diagnostics``: the ``I-MESH-ESTIMATE`` diagnostic ``build_mesh3d`` adds.
    ``route`` is ``"meshloom"``, ``"builder"`` or ``"extrude"``; ``count`` says what ``tetrahedra``
    is: ``"estimate"`` (T = 6.3 sum(V/h^3)), ``"exact"`` or ``"lower bound"`` (the extrude route)."""

    component: str
    tetrahedra: int
    limit: int
    seconds: float
    diagnostics: tuple
    route: str = "meshloom"
    count: str = "estimate"


def estimate_mesh3d(document, component: str | None = None) -> Mesh3DEstimate:
    """The estimate of ``build_mesh3d(document, component)`` without meshing (experimental).

    Raises the ``GeometryError`` ``build_mesh3d`` raises before meshing: ``E-MESH-ESTIMATE`` above
    the limit, ``E-CONTRACT``, ``E-3D-COMBINATION`` and the others, in the same words.

    A component holding only one slab ``layers`` feature, which ``build_mesh3d`` refuses for the
    ``meshine.extrude`` route (``build_thermal3d_mesh``), gets the extrude route's own count, 3 x
    footprint triangles x solid sub-layers (``thermal3d.extrude_count``): exact (the 2D footprint
    meshed, about 30-40 ms) when the footprint's lower bound A / (0.468 h^2) is at most 10,000
    triangles, otherwise that lower bound, worded as one. The limit refuses either; when only the
    lower bound is known and it is under the limit, ``build_thermal3d_mesh`` checks the exact count
    after the footprint mesh and before extruding. The seconds are rough there (no extrude speed)."""
    from .geometry_document import _pick, parse
    from . import thermal3d
    data = getattr(document, "data", document)
    model = parse(data)
    comp = _pick(model, component)
    if comp.dimension == "3d" and thermal3d.is_extrude_route(comp):
        return _extrude_estimate(data, model, comp)
    _, comp, handoff, info = _engine._prepare(document, component)
    estimate = float(handoff.estimate)
    from . import geometry_builders3d as builders
    return Mesh3DEstimate(comp.name, round(estimate), int(handoff.max_points),
                          estimate * SECONDS_PER_TETRAHEDRON, (info,),
                          "builder" if builders.has_curved(comp) else "meshloom", "estimate")


def _extrude_estimate(data, model, comp) -> Mesh3DEstimate:
    from physmat.units import Diagnostic
    from . import thermal3d
    limit = _engine._mesh_options(data, comp)["element_count_limit"]
    found = thermal3d.extrude_count(model, comp, thermal3d._element_size(data, comp))
    n, exact = found["tetrahedra"], found["exact"]
    if n > limit:
        raise thermal3d.extrude_limit_error(comp, n, limit, exact=exact)
    seconds = n * SECONDS_PER_TETRAHEDRON
    what = (f"{n} tetrahedra on the extrude route (3 x {found['footprint_triangles']} footprint triangles x "
            f"{found['sub_layers']} sub-layers)" if exact else
            f"at least {n} tetrahedra (extrude route; the exact count is known after the footprint mesh)")
    info = Diagnostic("I-MESH-ESTIMATE", f"geometry.components.{comp.name}",
                      f"{what}; meshing takes roughly {seconds * 2 / 3:.3g}-{seconds:.3g} s (rough: 0.4-0.6 ms per "
                      "tetrahedron is the meshloom route's speed)")
    return Mesh3DEstimate(comp.name, n, int(limit), seconds, (info,), "extrude",
                          "exact" if exact else "lower bound")
