# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The physics a document can declare, and what simcase does with each.

Every physics family registers one ``PhysicsKind``: the ``physics.<name>.type``
strings it claims, its contract validation, its runner, its summary and the
result types its runner returns. ``Document``, ``run``, ``build_mesh``,
``solve_point`` and the command line look the kind up here instead of testing
type strings themselves, so a new physics registers a kind and leaves them alone.

A document belongs to the first kind, in ``precedence`` order, that claims the
type of any of its physics entries. A document no kind claims -- an unknown or
missing type, or a malformed ``physics`` section -- goes to the fallback kind,
whose validator reports what is wrong with it.

The kinds come from providers (``simcase.providers``): simcase's own kinds are the built-in
provider ``openphysics-fem``, and an installed distribution can add kinds through an entry
point in the group ``openphysics.providers``. The first lookup loads the providers, the
built-in one first; a provider that fails is listed as unavailable and leaves the others.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable

#: Modules that register the built-in kinds when imported. Imported on first
#: lookup, not here: they import ``schema``, which uses this module. The built-in
#: provider ``openphysics-fem`` (``simcase.providers``) is these modules' kinds.
BUILTIN_MODULES = ("electric_joule", "mechanics", "transient_thermal", "thermal", "thermal3d", "cavity", "runner")


@dataclass(frozen=True)
class PhysicsKind:
    name: str
    #: ``physics.<name>.type`` values this kind claims
    types: frozenset[str]
    #: lower first; decides a document whose entries more than one kind claims
    precedence: int
    #: contract validation of a whole document; raises ``DocumentError``
    validate: Callable[[Any], None]
    #: ``run(doc, verbose)``: the validated document end to end; for a document
    #: ``accepts_mesh_limits`` claims, also ``run(doc, verbose, mesh_limits=...)``
    run: Callable[..., Any]
    #: the one-paragraph text ``Document.summary`` and ``simcase validate`` print
    summary: Callable[[Any], str]
    #: what ``run`` returns
    result_types: tuple[type, ...]
    #: the command line refuses an output folder that already exists
    fresh_output: bool = False
    #: refusal for ``build_mesh`` and ``solve_point``, with ``{stage}`` for the
    #: stage's name; None for the kind those stages run
    stage_refusal: str | None = None
    #: the kind of documents no other kind claims
    fallback: bool = False
    #: which of this kind's documents (their data) ``run`` takes mesh limits for
    #: (``simcase.mesh_limits``); the runner then gets them as ``mesh_limits``.
    #: None for a kind that takes them for no document
    accepts_mesh_limits: Callable[[Any], bool] | None = None
    #: whether ``run`` takes ``on_event`` (``simcase.run``): only then is the runner called as
    #: ``run(doc, verbose, on_event=...)``; a kind without it runs as before and sends no events
    accepts_on_event: bool = False
    #: the slots this kind's format 0.3 documents add to the shared ones (``simcase.slots``):
    #: data only, one dict per entry. None for a kind that does not read format 0.3 yet,
    #: whose 0.3 documents are refused with ``E-CONTRACT``
    slots: tuple[dict, ...] | None = None
    #: the geometry forms (``simcase.slots.GEOMETRY_FORMS``) whose format 0.3 documents this
    #: kind reads; None for every form. A 0.3 document of another form is refused with
    #: ``E-CONTRACT`` while the kind still reads that form in format 0.2 only
    forms_03: frozenset[str] | None = None
    #: a refusal by name, checked on the raw format 0.3 tree before its slots are walked: a
    #: ``(path, message)`` pair (``E-CONTRACT``), or ``(path, message, code)``, for a document
    #: one of this kind's types never takes (for example a geometry form), so the reader names
    #: it before asking for that type's keys; None (or a None result) for none
    refuse_03: Callable[[dict], tuple | None] | None = None
    #: how the kind takes part in a multiphysics document (``simcase.multiphysics.CouplingHook``);
    #: internal to simcase in this release. None for a kind a multiphysics document refuses
    coupling: Any = None
    #: the kind meshes ``3d`` geometry components itself (``simcase.geometry_engine3d``): the reader
    #: does not compile its 3d component to the flat box form ``em.cavity3d`` reads
    geometry_3d: bool = False


_KINDS: dict[str, PhysicsKind] = {}
#: kind name -> the name of the provider that added it (``simcase.providers``)
_OWNERS: dict[str, str] = {}
_loaded = False


def register(kind: PhysicsKind) -> PhysicsKind:
    """Add ``kind``, or replace the kind of the same name (a module reload)."""
    for other in _KINDS.values():
        if other.name == kind.name:
            continue
        if other.types & kind.types:
            raise ValueError(f"physics kind {kind.name!r} claims {sorted(other.types & kind.types)}, "
                             f"already claimed by {other.name!r}")
        if kind.fallback and other.fallback:
            raise ValueError(f"physics kinds {other.name!r} and {kind.name!r} are both the fallback")
    _KINDS[kind.name] = kind
    return kind


def _load_builtin() -> None:
    """Load the providers once: the built-in kinds, then every installed provider's."""
    global _loaded
    if not _loaded:
        _loaded = True
        importlib.import_module(f"{__package__}.providers")._load()


def kinds() -> tuple[PhysicsKind, ...]:
    """Every registered kind, in precedence order."""
    _load_builtin()
    return tuple(sorted(_KINDS.values(), key=lambda k: k.precedence))


def physics_types() -> frozenset[str]:
    """Every ``physics.<name>.type`` value some kind claims."""
    return frozenset().union(*(k.types for k in kinds()))


def kind_of_type(physics_type) -> PhysicsKind | None:
    """The kind claiming one ``physics.<name>.type`` value, or None."""
    return next((k for k in kinds() if physics_type in k.types), None)


def _envelope() -> str:
    return importlib.import_module(f"{__package__}.multiphysics").ENVELOPE


def kind_of(data) -> PhysicsKind:
    """The kind a raw or validated document's data belongs to; a multiphysics document's is
    ``simcase.multiphysics.KIND`` (each of its physics entries is its own kind's)."""
    if isinstance(data, dict) and data.get("openphysics") == _envelope():
        return importlib.import_module(f"{__package__}.multiphysics").KIND
    physics = data.get("physics") if isinstance(data, dict) else None
    entries = [p for p in physics.values() if isinstance(p, dict)] if isinstance(physics, dict) else []
    ordered = kinds()
    for kind in ordered:
        if not kind.fallback and any(p.get("type") in kind.types for p in entries):
            return kind
    return next(k for k in ordered if k.fallback)
