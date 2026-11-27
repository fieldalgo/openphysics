# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The ``I-MESH-ESTIMATE`` of a ``3d`` component without meshing it (``estimate_mesh3d``).

``build_mesh3d`` checks the estimate T = 6.3 sum(V_r / h_r^3) against ``mesh.element_count_limit``
and then meshes in the same call. A caller that must know the estimate before it decides to mesh
(Studio refuses before it starts a meshing process) calls this instead. It is one call to
``geometry_engine3d._prepare``, which is everything ``build_mesh3d`` does before meshloom, so every
refusal that blocks meshing blocks the estimate too, in the same words, with no second list to keep
in step. Only the hand-off's ``estimate`` and ``max_points`` and the diagnostic are read: the
complex may be absent on other hand-off routes.
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
    tetrahedron, and ``diagnostics``: the ``I-MESH-ESTIMATE`` diagnostic ``build_mesh3d`` adds."""

    component: str
    tetrahedra: int
    limit: int
    seconds: float
    diagnostics: tuple


def estimate_mesh3d(document, component: str | None = None) -> Mesh3DEstimate:
    """The estimate of ``build_mesh3d(document, component)`` without meshing (experimental).

    Raises the ``GeometryError`` ``build_mesh3d`` raises before meshing: ``E-MESH-ESTIMATE`` above
    the limit, ``E-CONTRACT``, ``E-3D-COMBINATION`` and the others, in the same words."""
    _, comp, handoff, info = _engine._prepare(document, component)
    estimate = float(handoff.estimate)
    return Mesh3DEstimate(comp.name, round(estimate), int(handoff.max_points),
                          estimate * SECONDS_PER_TETRAHEDRON, (info,))
