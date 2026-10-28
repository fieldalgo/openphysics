# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Run a NumPy solver on the numbers of JAX or PyTorch inputs, then add derivatives.

A solver that differentiates this way first calls its unchanged NumPy body on
``numbers(...)`` of every input, with each callback wrapped in ``Recorded``:
the NumPy body sees NumPy numbers and runs all its checks; the wrapper keeps
what the callback really returned. The live pass then recomputes the outputs in
the input's library from those kept values (``Recorded.replay``), so callbacks
run once. Inputs that hold no live value are passed through as the very same
objects, so a NumPy call is unchanged.
"""
from typing import Mapping

import numpy as np

from .backend import is_live, to_numpy
from .checks import contains_live


def numbers(value):
    """``value`` with JAX and PyTorch arrays replaced by NumPy numbers.

    Mappings, lists and tuples are converted entry by entry; a 0-d array becomes
    a float, or a complex number when it is complex. A value holding no live
    array is returned as the same object.
    """
    if isinstance(value, Mapping):
        if not any(contains_live(v) for v in value.values()):
            return value
        return {k: numbers(v) for k, v in value.items()}
    if not contains_live(value):
        return value
    if isinstance(value, (list, tuple)):
        a = np.array([numbers(v) for v in value])
        return a if np.iscomplexobj(a) else a.astype(float)
    a = to_numpy(value)
    if a.ndim:
        return a
    return complex(a) if np.iscomplexobj(a) else float(a)


class Recorded:
    """A callback that hands NumPy numbers to the solver and keeps what it returned."""

    def __init__(self, function):
        self.function = function
        self.results = []

    def __call__(self, *args):
        out = self.function(*args)
        self.results.append(out)
        return numbers(out)

    @property
    def live(self):
        return any(contains_live(r) for r in self.results)

    def replay(self):
        """A callback returning the kept results in call order (no new calls)."""
        results = iter(self.results)
        return lambda *args: next(results)


def recorded(value):
    """``value`` with every callable (also inside a mapping) wrapped in ``Recorded``."""
    if callable(value):
        return Recorded(value)
    if isinstance(value, Mapping) and any(callable(v) for v in value.values()):
        return {k: recorded(v) for k, v in value.items()}
    return value


def replayed(value):
    """The inverse view of ``recorded``: each ``Recorded`` becomes its replay."""
    if isinstance(value, Recorded):
        return value.replay()
    if isinstance(value, Mapping):
        return {k: replayed(v) for k, v in value.items()}
    return value


def is_live_input(value):
    """Whether ``value`` holds a live array or a ``Recorded`` callback that returned one."""
    if isinstance(value, Recorded):
        return value.live
    if isinstance(value, Mapping):
        return any(is_live_input(v) for v in value.values())
    return contains_live(value)


def leaves(*values):
    """Every live array held by ``values`` (recorded callback results included)."""
    out = []
    for value in values:
        if isinstance(value, Recorded):
            out += leaves(*value.results)
        elif isinstance(value, Mapping):
            out += leaves(*value.values())
        elif isinstance(value, (list, tuple)):
            out += leaves(*value)
        elif is_live(value):
            out.append(value)
    return out
