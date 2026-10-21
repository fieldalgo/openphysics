# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Optional mesh limits for heat region documents.

A caller that runs documents it did not write, such as a server, can bound what a
region run meshes before anything is solved::

    result = run(doc, max_input_vertices=2048, max_nodes=10201, max_triangles=20000)

* ``max_input_vertices`` bounds the loop vertices the region geometry passes to meshine
  (``check_mesh_limits``). It is checked while the domain is assembled, before meshine
  builds it, and it is the only limit that bounds the work before meshing.
* ``max_nodes`` is passed to meshine as ``max_points``, so meshing stops at the first
  insertion past it; the exact node count is compared again after meshing. meshine
  checks it only after building the domain, which is O(V^2) in the loop vertices.
* ``max_triangles`` is compared with the exact triangle count after meshing.

Every check runs before the solve and raises ``MeshLimitError``. A limit left at None is
not checked, and with no limit the run is exactly the unlimited one. The limits apply to
steady and transient heat region documents only. See
docs/packages/simcase/thermal_regions2d.md, "Mesh limits for callers".
"""
from __future__ import annotations

import numbers
from dataclasses import dataclass

#: What a loop-vertex refusal adds, because the rule surprises: an isolated circle (meshed
#: as an exact meshine Circle) takes its vertex count from the global mesh.size, not from
#: its own mesh_size.
CIRCLE_RULE = 'an isolated circle uses max(16, 4*pi*r/mesh.size) loop vertices from the global mesh.size'

_NAMES = {'input_vertices': 'max_input_vertices', 'nodes': 'max_nodes', 'triangles': 'max_triangles'}


class MeshLimitError(ValueError):
    """A heat region document needs more than a mesh limit allows.

    ``quantity`` is ``'input_vertices'``, ``'nodes'`` or ``'triangles'``; ``limit`` is the
    limit that refused it; ``count`` is the exact count, or None when meshing stopped at
    meshine's cap (``max_nodes``) or when one isolated circle alone needs more loop vertices
    than the limit. The message names the quantity, the count and the limit.

    Not a DocumentError: the document is valid, and the caller's limit refuses it.
    """

    def __init__(self, quantity: str, limit: int, count: int | None = None, detail: str | None = None):
        if quantity not in _NAMES:
            raise ValueError(f'MeshLimitError: unknown quantity {quantity!r}')
        self.quantity, self.limit, self.count, self._detail = quantity, limit, count, detail
        name = _NAMES[quantity]
        if quantity == 'input_vertices':
            what = (f'the region geometry passes {count} loop vertices to the mesher' if count is not None
                    else detail or 'the region geometry needs more loop vertices')
            message = f'{what}, more than {name}={limit}; {CIRCLE_RULE}'
        elif count is None:
            message = f'the mesh needs more than {name}={limit} {quantity}; meshing stopped at that cap'
        else:
            message = f'the mesh has {count} {quantity}, more than {name}={limit}'
        super().__init__(message)

    def __reduce__(self):
        return type(self), (self.quantity, self.limit, self.count, self._detail)


@dataclass(frozen=True)
class _MeshLimits:
    """The limits of one run; None skips that check."""
    max_nodes: int | None = None
    max_triangles: int | None = None
    max_input_vertices: int | None = None


def _limit(name: str, value) -> int | None:
    """``value`` as a positive int, or None. A bool, a float or a non-positive value is an error."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, numbers.Integral) or value <= 0:
        raise ValueError(f'{name}: expected a positive int or None, got {value!r}')
    return int(value)


def _mesh_limits(max_nodes=None, max_triangles=None, max_input_vertices=None) -> _MeshLimits | None:
    """The run's limits as one object, or None when no limit is given."""
    limits = _MeshLimits(_limit('max_nodes', max_nodes), _limit('max_triangles', max_triangles),
                         _limit('max_input_vertices', max_input_vertices))
    return None if limits == _MeshLimits() else limits


def _is_region_document(data) -> bool:
    """A document whose physics kind takes mesh limits for it (the registry's
    ``PhysicsKind.accepts_mesh_limits``): a steady or transient heat region document."""
    from .registry import kind_of
    accepts = kind_of(data).accepts_mesh_limits
    return accepts is not None and bool(accepts(data))


def check_mesh_limits(doc, *, max_input_vertices: int) -> int:
    """The number of loop vertices a heat region document passes to meshine.

    ``doc`` is a ``Document``. A run validates the document and meshes its micrometre copy
    (``runner.micrometre_document``), so that copy is what is counted, and the count is the
    one ``run(..., max_input_vertices=...)`` checks. The copy is made with the length unit
    the document's validation resolved; a document whose resolved scale is not the one its
    ``units`` declare, because it was never validated (``Document(data)``,
    ``Document.copy()``) or its units changed since, is counted on a validated deep copy,
    as a run of it would validate it first. A validated document is not validated again. A loop
    vertex is one entry of a loop given to meshine's ``Domain.add_region``, outer rings and
    holes alike, after the shapes' booleans: a shape inside the background counts once as
    itself and once as the background's hole, a circle that another boundary touches or
    crosses is a 128-gon, and an isolated circle counts max(16, int(4 pi r / mesh.size))
    with the global ``mesh.size``. meshine's own T-junction splits come later and are not
    counted.

    Raises ``MeshLimitError`` (quantity ``'input_vertices'``) when the count passes
    ``max_input_vertices``; an isolated circle whose own count alone passes it is refused
    before its vertices are made, with ``count`` None and the circle's own estimate, in
    micrometres, in the message. The domain is never built and the document is not
    changed. The micrometre copy is validated, as in a run, so the shapes' booleans are
    resolved twice: in that validation and for the count. ``TypeError`` for anything that
    is not a ``Document``; ``ValueError`` for a document that is not a steady or transient
    heat region document, or a limit that is not a positive int; ``DocumentError`` for an
    unvalidated document that its validation refuses.
    """
    import copy
    from . import units
    from .schema import Document
    limit = _limit('max_input_vertices', max_input_vertices)
    if limit is None:
        raise ValueError('max_input_vertices: expected a positive int, got None')
    if not isinstance(doc, Document):
        raise TypeError(f'check_mesh_limits: expected a Document (Document.from_dict), got {type(doc).__name__}')
    if not _is_region_document(doc.data):
        raise ValueError('check_mesh_limits: expected a steady or transient heat region document '
                         '(geometry.shapes or geometry.background)')
    try:
        declared = units.resolve(doc.data.get('units'))
    except units.UnitError:
        declared = None
    if doc.scale != declared:
        # Not validated, or changed since: its numbers have no resolved length unit, and the
        # micrometre copy would be made with the wrong one. A run validates first; so do we,
        # on a copy, and leave the document as it is.
        doc = Document(copy.deepcopy(doc.data))
        doc.validate()
    from .geometry import _domain_from_regions
    from .runner import micrometre_document
    return _domain_from_regions(micrometre_document(doc), max_input_vertices=limit)[3]
