# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Numeric input checks shared by the physics modules.

``real_array`` and ``finite_scalar`` return NumPy numbers, so they refuse JAX
and PyTorch arrays rather than silently cutting a derivative. A solver that
differentiates uses ``real_value``, which runs the same checks on a snapshot
and returns the value itself.
"""
import numpy as np

from .backend import is_live, lift, live_namespace, namespace, require_float64, to_numpy


def contains_live(value):
    """Whether ``value`` is, or a (nested) list or tuple holds, a JAX or PyTorch array."""
    if isinstance(value, (list, tuple)):
        return any(contains_live(v) for v in value)
    return is_live(value)


def _stacked(xp, value):
    if isinstance(value, (list, tuple)):
        return xp.stack([_stacked(xp, v) for v in value])
    return lift(xp, value, xp.float64)


def _leaves(value):
    if isinstance(value, (list, tuple)):
        return [leaf for v in value for leaf in _leaves(v)]
    return [value]


def refuse_live(value, name):
    """Raise TypeError if ``value`` holds a JAX or PyTorch array: the caller computes with NumPy.

    Lists and tuples are searched too: NumPy would otherwise convert their live
    elements silently.
    """
    if contains_live(value):
        raise TypeError(f"{name}: this computation runs on NumPy and would cut the derivative "
                        "of a JAX or PyTorch value; pass NumPy numbers")


def real_array(value, name):
    """A new float array of finite real numbers.

    Rejects booleans (alone or as elements of a list or tuple, before NumPy can
    coerce them to numbers), non-real dtypes, nonfinite values and values that
    overflow on conversion to float. The result never aliases ``value``.
    JAX and PyTorch arrays are refused (TypeError); see ``real_value``.
    """
    refuse_live(value, name)
    if isinstance(value, (bool, np.bool_)) or (
            isinstance(value, (list, tuple)) and any(isinstance(v, (bool, np.bool_)) for v in value)):
        raise ValueError(f"{name} must not contain booleans")
    a = np.asarray(value)
    if a.dtype.kind not in "iuf" or not np.all(np.isfinite(a)):
        raise ValueError(f"{name} must contain finite real numbers")
    with np.errstate(over="ignore", invalid="ignore"):
        out = np.array(a, dtype=float, copy=True)
    if not np.all(np.isfinite(out)):
        raise ValueError(f"{name} exceeds floating-point range")
    return out


def real_value(value, name):
    """``real_array(value, name)``, except that a JAX or PyTorch value stays live.

    A live value gets the same checks on a snapshot of its numbers and is
    returned as a float64 array in its own library, carrying its derivative.
    A list or tuple holding live elements becomes one stacked array.
    """
    if not contains_live(value):
        return real_array(value, name)
    if not is_live(value):
        xp = live_namespace(*_leaves(value))
        require_float64(xp, name)
        value = _stacked(xp, value)
    real_array(to_numpy(value), name)
    xp = namespace(value)
    require_float64(xp, name)
    return xp.astype(value, xp.float64)


def finite_scalar(value, label):
    """A finite real scalar as float; booleans and JAX or PyTorch arrays are rejected."""
    refuse_live(value, label)
    a = np.asarray(value)
    if a.shape != () or a.dtype.kind not in "iuf" or isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{label} must be a finite real scalar")
    a = float(a)
    if not np.isfinite(a):
        raise ValueError(f"{label} must be a finite real scalar")
    return a


def readonly_copy(value):
    """A read-only copy, for values handed to user callbacks."""
    out = np.array(value, copy=True)
    out.flags.writeable = False
    return out
