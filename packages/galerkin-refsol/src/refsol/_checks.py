# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Private checks shared by refsol's modules: SI numbers only.

A quantity given as text (a ``str``, also inside a list, tuple, mapping or array) raises
``TypeError``: refsol takes SI floats under registry names and converts nothing.
"""
from collections.abc import Mapping

import numpy as np


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


def refuse_text(**values) -> None:
    """``TypeError`` naming the first argument that is or holds a ``str``."""
    for name, value in values.items():
        if _has_text(value):
            raise TypeError(f"{name}: SI numbers only; convert a text quantity first, for example with "
                            f"physmat.units.q('...', {name!r})")


def pair(value, name):
    """A two-entry value of one quantity (left/right, inner/outer, bottom/top) as a tuple of two."""
    if isinstance(value, (str, bytes)) or np.ndim(value) != 1 or len(value) != 2:
        raise ValueError(f"{name} must be a pair of two values")
    return tuple(value)
