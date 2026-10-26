# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Numeric input checks shared by the physics modules."""
import numpy as np


def real_array(value, name):
    """A new float array of finite real numbers.

    Rejects booleans (alone or as elements of a list or tuple, before NumPy can
    coerce them to numbers), non-real dtypes, nonfinite values and values that
    overflow on conversion to float. The result never aliases ``value``.
    """
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


def finite_scalar(value, label):
    """A finite real scalar as float; booleans are rejected."""
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
