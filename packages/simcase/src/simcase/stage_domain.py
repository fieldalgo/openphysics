# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""``simcase.build_domain``: the public geometry stage of the stage API.

It takes a validated format 0.3 document of a kind whose run meshes with meshine (material
regions of heat, electric conduction, steady Joule heating and mechanics, and every
``em.modes2d`` form) and returns ``(Domain, namer, materials)``: the meshine ``Domain``, its
boundary namer and ``{region name: material name}``, exactly as ``run`` hands them to
``meshine.generate``. The domain is in the micrometre meshing frame, which is what meshine
receives whatever ``length_unit`` the document declares.

The entry composes the steps ``run`` itself takes (the document's kernel hand-off, then the
internal domain builder), so the two cannot drift apart. The mesher's findings
(``W-PIECE-DROPPED``, ``I-MESH-CONTROL-RAISED``) are reported by ``build_mesh`` and ``run``.
A rectangle or box document, which galerkin meshes on its structured grid, is refused by
name, as is a document that is not format 0.3.
"""

from __future__ import annotations

from .diagnostics import DocumentError


def build_domain(doc):
    """``(meshine.Domain, namer, {region: material})`` that a run of ``doc`` meshes, in micrometres.

    ``doc`` is a format 0.3 ``Document`` (``Document.from_dict``); it is validated first, as
    ``build_mesh`` validates it. ``DocumentError`` with ``E-FORMAT`` for another format, and
    with ``E-CONTRACT`` for a document that meshine does not mesh (a rectangle or a cavity box);
    ``TypeError`` for anything that is not a ``Document``.
    """
    from . import modes_document, views
    from .geometry import build_domain as kernel_domain
    from .mesh_limits import _is_region_document
    from .registry import kind_of
    from .schema import Document, not_read
    if not isinstance(doc, Document):
        raise TypeError(f"build_domain: expected a Document (Document.from_dict), got {type(doc).__name__}")
    if doc.si is None:
        raise not_read(doc.data)                    # E-FORMAT: only a format 0.3 document is read
    doc.validate()
    if _is_region_document(doc.data):
        # the region runners: build_region_mesh(handoff_03(doc)) meshes views.region_mesh's copy
        from .thermal_regions import handoff_03
        return kernel_domain(views.region_mesh(handoff_03(doc)).canonical)
    kind = kind_of(doc.data)
    if kind.name == "em.modes2d":
        # runner.build_mesh: the micrometre kernel hand-off, as views.modes_mesh hands it on
        return kernel_domain(views.modes_mesh(modes_document.kernel_document(doc)).canonical)
    name, entry = next(iter(doc.data["physics"].items()))
    mesh = "box mesh" if kind.name == "em.cavity3d" else "rectangle mesh"
    raise DocumentError(f"build_domain: this {entry.get('type')} document is meshed on galerkin's structured {mesh} "
                        "(mesh.subdivision_count), not by meshine; build_domain takes the documents meshine "
                        "meshes: material regions of heat, electric conduction, steady Joule heating and "
                        "mechanics, and em.modes2d", path=f"physics.{name}.type", code="E-CONTRACT")
