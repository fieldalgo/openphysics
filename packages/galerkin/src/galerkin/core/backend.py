# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The one module that dispatches on the array library.

galerkin computes through the array API (``array_api_compat``), so the same
code runs on NumPy, JAX and PyTorch arrays. Everything those libraries do
differently, and that the shared code needs, lives here so it can be tested in
one place. NumPy is the default and does not differentiate; JAX and PyTorch are
optional (``galerkin[jax]``, ``galerkin[torch]``) and are imported only when a
caller passes their arrays.

Static structure (mesh connectivity, sparsity patterns, boundary selections)
stays in NumPy integer arrays; only live values (coefficients, sources,
boundary values) follow the caller's library.
"""
from enum import Enum
import sys

import array_api_compat as ac
import numpy as np


class Backend(str, Enum):
    """An array library, named as it is imported."""
    NUMPY = "numpy"
    JAX = "jax"
    TORCH = "torch"


#: Libraries whose arrays carry derivatives. NumPy computes values only.
DIFFERENTIABLE_BACKENDS = frozenset({Backend.JAX, Backend.TORCH})


class TracedValueError(ValueError):
    """A check needs concrete values but received a value traced by ``jax.jit``."""


def namespace(*arrays):
    """The array API namespace of ``arrays``; Python scalars and None are ignored.

    Mixing libraries is an error (``array_api_compat`` raises TypeError).
    With no array at all, the namespace is NumPy's.
    """
    live = [a for a in arrays if a is not None and not isinstance(a, (bool, int, float, complex))]
    return ac.array_namespace(*live) if live else ac.array_namespace(np.empty(0))


def backend_of(xp):
    """The ``Backend`` of a namespace from :func:`namespace`."""
    if ac.is_numpy_namespace(xp):
        return Backend.NUMPY
    if ac.is_jax_namespace(xp):
        return Backend.JAX
    if ac.is_torch_namespace(xp):
        return Backend.TORCH
    raise TypeError(f"unsupported array namespace {getattr(xp, '__name__', xp)!r}")


def as_array(xp, value, dtype=None):
    """``value`` in namespace ``xp`` without leaving it (a live value keeps its derivative path)."""
    return xp.asarray(value, dtype=dtype)


def is_concrete(value):
    """Whether ``value`` can be read as numbers here.

    False only for a value traced by ``jax.jit`` (or ``vmap``); eager arrays,
    PyTorch tensors that require grad and ``jax.grad`` tracers outside ``jit``
    carry their values.
    """
    jax = sys.modules.get("jax")
    if jax is None or not isinstance(value, jax.Array):
        return True
    try:
        bool(jax.numpy.all(value == value))
    except jax.errors.TracerBoolConversionError:
        return False
    except jax.errors.ConcretizationTypeError:
        return False
    return True


def check_finite(xp, name, value):
    """Raise ValueError unless every entry of ``value`` is finite; keep ``value`` in ``xp``.

    A ``jax.jit`` tracer has no values to check, so it is refused with
    :class:`TracedValueError` rather than passed unchecked.
    """
    if not is_concrete(value):
        raise TracedValueError(f"{name}: checking finiteness needs concrete values; "
                               "call this outside jax.jit or check the inputs before tracing")
    if not bool(xp.all(xp.isfinite(value))):
        raise ValueError(f"{name} must contain finite numbers")
    return value


def scatter_add(xp, size, index, values):
    """A new array ``out`` of leading length ``size`` with ``out[index[k]] += values[k]``.

    ``index`` is a 1-D integer array (static structure, NumPy or ``xp``);
    ``values`` has shape ``(len(index), *trailing)`` and may be live. Repeated
    indices add. No argument is modified, so derivatives flow through ``values``
    on JAX and PyTorch.
    """
    index = np.asarray(index)
    if index.ndim != 1 or index.dtype.kind not in "iu":
        raise ValueError("scatter_add index must be a 1-D integer array")
    if values.shape[0] != index.shape[0]:
        raise ValueError(f"scatter_add has {index.shape[0]} indices but {values.shape[0]} values")
    shape = (size, *values.shape[1:])
    backend = backend_of(xp)
    if backend is Backend.NUMPY:
        out = np.zeros(shape, dtype=np.result_type(values.dtype, np.float64))
        np.add.at(out, index, values)          # into a fresh array only this call sees
        return out
    if backend is Backend.JAX:
        return xp.zeros(shape, dtype=values.dtype).at[index].add(values)
    torch = sys.modules["torch"]
    target = torch.as_tensor(index, device=values.device)
    return torch.zeros(shape, dtype=values.dtype, device=values.device).index_add(0, target, values)
