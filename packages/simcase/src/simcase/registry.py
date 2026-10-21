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
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable

#: Modules that register the built-in kinds when imported. Imported on first
#: lookup, not here: they import ``schema``, which uses this module.
BUILTIN_MODULES = ("electric_joule", "transient_thermal", "thermal", "cavity", "runner")


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
    #: document defaults that ``Document.from_dict`` merges the input into;
    #: None keeps ``schema.DEFAULTS``
    defaults: Callable[[], dict] | None = None
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


_KINDS: dict[str, PhysicsKind] = {}
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
    global _loaded
    if not _loaded:
        _loaded = True
        for module in BUILTIN_MODULES:
            importlib.import_module(f"{__package__}.{module}")


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


def kind_of(data) -> PhysicsKind:
    """The kind a raw or validated document's data belongs to."""
    physics = data.get("physics") if isinstance(data, dict) else None
    entries = [p for p in physics.values() if isinstance(p, dict)] if isinstance(physics, dict) else []
    ordered = kinds()
    for kind in ordered:
        if not kind.fallback and any(p.get("type") in kind.types for p in entries):
            return kind
    return next(k for k in ordered if k.fallback)
