# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""A sparse linear solve that JAX and PyTorch can differentiate.

``solve(A, b)`` solves ``A x = b`` for a square ``CooMatrix`` with SciPy's
sparse LU on every array library, so the forward result is the NumPy one. JAX
and PyTorch cannot differentiate SciPy, so the derivative is supplied by hand
(the adjoint): for a cotangent ``g`` of ``x``,

    lam = A^{-T} g,   gradient for b = lam,   gradient for A[r, c] = -lam[r] x[c],

one more solve with the same matrix, whatever the number of parameters. Only
the entries in A's pattern get a gradient, which is all a CooMatrix has.

Complex systems follow each library's convention: JAX passes cotangents through
the transpose (``A^{-T}``), PyTorch through the conjugate transpose
(``A^{-H}``, gradient ``-lam[r] conj(x[c])``). A real input fed into a complex
solve receives the real part of its gradient, as both libraries define it.

First derivatives in reverse mode only. JAX forward mode (``jvp``, ``jacfwd``)
through this solve is refused by ``jax.custom_vjp`` itself, and a second
PyTorch backward pass is refused by ``once_differentiable``; neither returns a
silently wrong number.
"""
import sys

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu

from .backend import Backend, backend_of, namespace
from .sparse import CooMatrix


def _factor(rows, cols, values, shape):
    matrix = sp.coo_matrix((np.asarray(values), (rows, cols)), shape=shape).tocsc()
    try:
        return splu(matrix)
    except RuntimeError as exc:
        raise ValueError(f"singular sparse matrix: {exc}") from exc


def _apply(lu, rhs, trans="N"):
    """``lu.solve`` that also takes a complex right-hand side for a real factor."""
    rhs = np.asarray(rhs)
    complex_lu = lu.L.dtype.kind == "c"
    if complex_lu:
        return lu.solve(rhs.astype(lu.L.dtype, copy=False), trans=trans)
    if np.iscomplexobj(rhs):
        return lu.solve(np.ascontiguousarray(rhs.real), trans=trans) \
            + 1j * lu.solve(np.ascontiguousarray(rhs.imag), trans=trans)
    return lu.solve(rhs.astype(np.float64, copy=False), trans=trans)


def _check(A, b):
    n, m = A.shape
    if n != m:
        raise ValueError(f"solve needs a square matrix, got {A.shape}")
    if b.ndim not in (1, 2) or b.shape[0] != n:
        raise ValueError(f"right-hand side must have shape ({n},) or ({n}, k), got {tuple(b.shape)}")


def solve(A: CooMatrix, b):
    """``x`` with ``A x = b``; ``b`` has shape (n,) or (n, k) in the library of ``A.values``.

    Duplicate (row, col) entries add, as in :meth:`CooMatrix.to_dense`. A
    singular matrix raises ValueError.
    """
    _check(A, b)
    backend = backend_of(namespace(A.values, b))
    if backend is Backend.NUMPY:
        return _apply(_factor(A.rows, A.cols, A.values, A.shape), b)
    if backend is Backend.JAX:
        return _jax_solve(A.rows, A.cols, A.shape, A.values, b)
    return _torch_function().apply(A.rows, A.cols, A.shape, A.values, b)


# -- JAX -----------------------------------------------------------------------

def _jax_solve(rows, cols, shape, values, b):
    jax = sys.modules["jax"]
    jnp = jax.numpy
    dtype = jnp.result_type(values.dtype, b.dtype)

    def host(trans):
        def call(v, rhs):
            return _apply(_factor(rows, cols, v, shape), rhs, trans).astype(dtype)
        return call

    def run(v, rhs, trans):
        return jax.pure_callback(host(trans), jax.ShapeDtypeStruct(rhs.shape, dtype),
                                 v, rhs, vmap_method="sequential")

    # The pattern (rows, cols, shape) is closed over: only values and b are traced.
    @jax.custom_vjp
    def inner(v, rhs):
        return run(v, rhs, "N")

    def forward(v, rhs):
        x = run(v, rhs, "N")
        return x, (v, x)

    def backward(residuals, g):
        v, x = residuals
        lam = run(v, g, "T")                                     # A^T lam = g
        lam2, x2 = (lam, x) if lam.ndim == 2 else (lam[:, None], x[:, None])
        grad_values = -jnp.sum(lam2[rows] * x2[cols], axis=1)
        return _jax_like(jnp, grad_values, values.dtype), _jax_like(jnp, lam, b.dtype)

    inner.defvjp(forward, backward)
    return inner(values, b)


def _jax_like(jnp, grad, dtype):
    if jnp.iscomplexobj(grad) and not jnp.issubdtype(dtype, jnp.complexfloating):
        grad = jnp.real(grad)
    return grad.astype(dtype)


# -- PyTorch -------------------------------------------------------------------

_TORCH_FUNCTION = None


def _torch_function():
    global _TORCH_FUNCTION
    if _TORCH_FUNCTION is not None:
        return _TORCH_FUNCTION
    torch = sys.modules["torch"]
    once_differentiable = torch.autograd.function.once_differentiable

    def like(grad, dtype):
        if grad.is_complex() and not dtype.is_complex:
            grad = grad.real
        return grad.to(dtype)

    class SparseSolve(torch.autograd.Function):
        @staticmethod
        def forward(ctx, rows, cols, shape, values, b):
            lu = _factor(rows, cols, values.detach().cpu().numpy(), shape)
            dtype = torch.promote_types(values.dtype, b.dtype)
            x = torch.as_tensor(_apply(lu, b.detach().cpu().numpy()), device=b.device).to(dtype)
            ctx.lu, ctx.rows, ctx.cols = lu, rows, cols
            ctx.dtypes = (values.dtype, b.dtype)
            ctx.save_for_backward(x)
            return x

        @staticmethod
        @once_differentiable
        def backward(ctx, g):
            (x,) = ctx.saved_tensors
            lam = torch.as_tensor(_apply(ctx.lu, g.detach().cpu().numpy(), "H"), device=g.device)
            lam2, x2 = (lam, x) if lam.ndim == 2 else (lam[:, None], x[:, None])
            rows = torch.as_tensor(ctx.rows, device=g.device)
            cols = torch.as_tensor(ctx.cols, device=g.device)
            grad_values = -torch.sum(lam2[rows] * x2[cols].conj(), dim=1)
            value_dtype, rhs_dtype = ctx.dtypes
            return None, None, None, like(grad_values, value_dtype), like(lam, rhs_dtype)

    _TORCH_FUNCTION = SparseSolve
    return _TORCH_FUNCTION
