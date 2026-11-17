# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The one place refsol converts a complex value between its public and its internal convention.

Private (rule 5 and D8 of the galerkin step). refsol's public complex values follow exp(-i omega t):
a passive loss is Im(relative_permittivity) >= 0 (a refractive index n' + i n''), and a forward mode
that decays along +z has Im(effective_index) >= 0. Modules whose closed forms are written in
exp(+i omega t) (``refsol.lossy_slab``, ``refsol.bent_slab``) keep that internal arithmetic and
convert here only: a public complex output is ``to_public(internal(to_kernel(x)))``, never re-derived.
refsol computes with NumPy and Python numbers only.

- ``to_kernel(x)``: a Python or NumPy complex scalar becomes ``complex(x.real, 0.0 - x.imag)``; a NumPy
  complex array ``out`` with ``out.real = x.real`` and ``out.imag = 0.0 - x.imag`` (a -0.0 real part is
  kept, a zero imaginary part becomes +0.0), as ``galerkin._conventions.to_kernel``.
- ``to_public(y)``: ``np.conj(y)`` for a NumPy array or scalar (a Python complex stays a Python complex).

Anything that is not complex (a real number or array, None, a sequence, an object) is returned as it
is, so real values keep their exact doubles and types.
"""
import numpy as np

__all__ = ["to_kernel", "to_public"]


def _complex_scalar(value) -> bool:
    return isinstance(value, (complex, np.complexfloating))


def _complex_array(value) -> bool:
    return isinstance(value, np.ndarray) and value.dtype.kind == "c"


def to_kernel(x):
    """``x`` (exp(-i omega t)) in the internal exp(+i omega t) convention: Im negated as ``0.0 - Im``."""
    if _complex_scalar(x):
        return complex(x.real, 0.0 - x.imag)
    if _complex_array(x):
        out = np.empty(x.shape, complex)
        out.real = x.real
        out.imag = 0.0 - x.imag
        return out
    return x


def to_public(y):
    """``y`` (an internal exp(+i omega t) value) in the public exp(-i omega t) convention: ``conj``."""
    if type(y) is complex:
        return complex(np.conj(y))
    if _complex_scalar(y) or _complex_array(y):
        return np.conj(y)
    return y
