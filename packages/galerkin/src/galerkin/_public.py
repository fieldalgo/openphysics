# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Helpers of galerkin's public SI functions: string refusal, inward negation, result surfaces.

Private: the public solvers take keyword-only registry names in SI units (the units
convention of the galerkin step) and call private functions that keep today's bodies
and today's outward keywords. This module holds what the thin public layer adds.

- ``refuse_text(name, value)``: a ``str`` given for a quantity raises ``TypeError``.
- ``outward_from_inward(data, name)``: a boundary mapping of inward data (positive
  enters the body), negated exactly once into the outward form the private functions
  take. A constant becomes ``0.0 - x``; a callable becomes a ``functools.wraps``
  wrapper returning ``0.0 - y`` of its checked float result (``real_array``, the
  conversion galerkin applies to every callback result, so the doubles are those of
  ``0.0 - np.asarray(y, dtype=float)``), or ``0.0 - y`` of a JAX or PyTorch result.
  ``inspect.signature`` follows the wrapper's ``__wrapped__``, so the callback forms
  of transient heat are told apart as before.
- ``ResultSurface``: ``.units`` (field -> canonical unit) and the planar,
  axisymmetric and 3D naming of the heat, electric and Joule results.
"""
from collections.abc import Mapping
from dataclasses import fields
import functools
from types import MappingProxyType

import numpy as np

from .core.backend import is_live
from .core.checks import contains_live, real_array, real_value

PER_DEPTH = "_per_depth"


def _has_text(value) -> bool:
    if isinstance(value, (str, bytes)):
        return True
    if isinstance(value, np.ndarray):
        return value.dtype.kind in "SU" or (value.dtype.kind == "O" and any(_has_text(v) for v in value.ravel()))
    if isinstance(value, Mapping):
        return any(_has_text(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_has_text(v) for v in value)
    return False


def refuse_text(name: str, value) -> None:
    """``TypeError`` when ``value`` (the argument ``name``) is or holds a ``str``: SI numbers only."""
    if _has_text(value):
        raise TypeError(f"{name}: SI numbers only; convert a text quantity first, for example with "
                        f"physmat.units.q('...', {name!r})")


def refuse_tagged_text(name: str, value) -> None:
    """``refuse_text`` for a mapping of boundary edge tags (such as ``traction``).

    Its tags are text by design and are not looked at; a value that is neither a mapping nor
    text is left for the solver to refuse ("must map boundary edge tags"), as the inward
    boundary mappings are by ``outward_from_inward``.
    """
    if value is None or isinstance(value, (Mapping, str, bytes)):
        refuse_text(name, value)


def _is_constant_number(value) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return False
    if isinstance(value, (int, float, np.integer, np.floating)):
        return True
    if isinstance(value, np.ndarray):
        return value.dtype.kind in "iuf"
    return is_live(value)


def _negated(value, name):
    """``value`` of an inward mapping in the outward form; anything else is left for the solver to refuse."""
    if callable(value):
        @functools.wraps(value)
        def outward(*args, **kwargs):
            result = value(*args, **kwargs)
            if contains_live(result):
                return 0.0 - real_value(result, f"{name} callback")
            return 0.0 - real_array(result, f"{name} callback")
        return outward
    if _is_constant_number(value):
        return 0.0 - value
    return value


def outward_from_inward(data, name):
    """``{tag: outward}`` of an inward boundary mapping, in its order (hazard H6); None stays None."""
    if data is None:
        return None
    if isinstance(data, (str, bytes)):
        refuse_text(name, data)                     # text is a TypeError, as for every quantity
    if not isinstance(data, Mapping):
        raise ValueError(f"{name} must map boundary edge tags to conditions")
    return {tag: _negated(value, f"{name}[{tag!r}]") for tag, value in data.items()}


class ResultSurface:
    """``.units`` and the planar, axisymmetric or 3D naming of a result dataclass.

    ``UNITS`` maps each quantity field to its canonical unit (registry names; structural
    fields such as node indices have none). ``BASIS`` is "planar" (nodal rates per metre
    of depth, ``*_per_depth``), "axisymmetric" (totals over the full revolution) or "3d"
    (totals).
    """

    UNITS: Mapping = MappingProxyType({})
    BASIS: str = "planar"

    @property
    def units(self):
        """{field: canonical SI unit} of every quantity field (read-only)."""
        return self.UNITS

    def __getattr__(self, name):
        # Only reached when ordinary lookup fails: explain the planar/axisymmetric naming.
        if name.startswith("__"):
            raise AttributeError(name)
        cls = type(self)
        names = {f.name for f in fields(cls)}
        if cls.BASIS != "planar" and name.endswith(PER_DEPTH) and name[:-len(PER_DEPTH)] in names:
            why = ("an axisymmetric solve integrates the full revolution" if cls.BASIS == "axisymmetric"
                   else "a 3D solve integrates the whole body")
            raise AttributeError(
                f"{cls.__name__} has no field {name!r}: {why}, so its rates are totals in W "
                f"({name[:-len(PER_DEPTH)]!r}), not per metre of depth")
        if cls.BASIS == "planar" and name + PER_DEPTH in names:
            raise AttributeError(
                f"{cls.__name__} has no field {name!r}: a planar solve gives rates per metre of depth "
                f"({name + PER_DEPTH!r}, in {cls.UNITS.get(name + PER_DEPTH, 'per metre of depth')}); "
                f"multiply by the depth for a total")
        raise AttributeError(f"{cls.__name__!r} object has no attribute {name!r}")
